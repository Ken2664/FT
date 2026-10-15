"""天井の水準 `L_05`・`L_50` を、仮定値と規則だけから計算する(PLAN-044 I3 / §3.3 / ADR-131 Q1 (a))。

答える問い: 「**パイロットと同じ形の観測**(2 シード × 80 項目で、T1 × `id` と T1 × `interp` の 2 セルがどちらも
全部 `rule`)が、シートの DGP の下で起こる確率が 0.05 / 0.5 になる最小の `L` はいくつか」

    python -m code.analysis.ceiling_level --config configs/power_sim_ceiling.yaml

**規則**(config の `ceiling_level`):

- DGP は `power_sim.draw_frame` と同じ(`sigma`・`rho`・`s2_item`・`s2_tmpl`・`tau` 0)。2 つのセルの `eta` を `L` にする。
  `u[s, 被覆]`(シード × 被覆)・`v[セル, 項目]`(項目は 2 シードで共通)・`w[テンプレート]`(T1 のテンプレートはセルをまたいで共通)を引き、
  **ランダム効果を条件づけた**「320 回すべて `rule`」の確率 `Π logistic(L + u + v + w)` を平均する(`event_probability`)
- 乱数は固定の種から毎回同じ列を引き直す(共通乱数)。だから `L` の関数としてなめらかで**厳密に単調増加**になり、二分法が確実に解を持つ
- `L` は「確率が目標に届く最小の `L`」(単調なので解は 1 つ)。値は `round_decimals` 桁に丸めて config に転記する

**パイロットの表(`results/s2_item_pilot/`)は読まない**(PLAN-044 罠1)。パイロットの形(2 シード・80 項目・2 セル)は
config の `ceiling_level.pilot_shape` に書いた規則であって、パイロットの点推定ではない。
**出力は `results/power_sim/ceiling_level/`**。これは仮定値の算術で、実験結果ではない(`CLAUDE.md` §2)。
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from code import artifacts
from code.analysis.power_sim import compound_symmetry_sqrt, write_json_atomic
from code.config import ConfigError, load_config, require, resolve_repo_path

OUTPUT_FILE = "ceiling_level.json"


@dataclass(frozen=True)
class LevelRule:
    """水準を決める規則(config の `ceiling_level` と `dgp`)。答える問い: どの観測の確率を、どの DGP で、何回引いて数えるか。"""

    rng_seed: int
    n_draws: int
    chunk: int
    n_seed: int
    n_item: int
    cells: tuple[tuple[str, str], ...]
    coverages: tuple[str, ...]
    template_names: tuple[str, ...]
    sigma: float
    rho: float
    s2_item: float
    s2_tmpl: float
    targets: Mapping[str, float]
    search_lower: float
    search_upper: float
    tolerance: float
    round_decimals: int
    table_levels: tuple[float, ...]


def _positive_int(config: Mapping[str, Any], key: str) -> int:
    value = require(config, key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{key} は正の整数: {value!r}")
    return value


def load_level_rule(config: Mapping[str, Any]) -> LevelRule:
    """config から規則を読む。答える問い: 規則の値はすべて宣言されているか(null・欠けは止まる。既定値を作らない)。"""
    tasks = require(config, "effect.task_levels")
    coverages = tuple(require(config, "effect.coverage_levels"))
    raw_cells = require(config, "ceiling_level.cells")
    cells = tuple((str(task), str(cov)) for task, cov in raw_cells)
    task_of_cells = {task for task, _ in cells}
    if len(task_of_cells) != 1 or not task_of_cells <= set(tasks):
        raise ConfigError(f"ceiling_level.cells は 1 つのタスク型のセルだけ(テンプレートを共有する): {raw_cells!r}")
    if any(cov not in coverages for _, cov in cells) or len(set(cells)) != len(cells):
        raise ConfigError(f"ceiling_level.cells が被覆水準に無いか重複している: {raw_cells!r}")
    (task,) = task_of_cells
    templates = tuple(require(config, f"dgp.templates.{task}"))
    targets = require(config, "ceiling_level.targets")
    if not isinstance(targets, Mapping) or not targets:
        raise ConfigError(f"ceiling_level.targets は {{水準名: 確率}} の空でない写像: {targets!r}")
    for name, probability in targets.items():
        if not 0.0 < float(probability) < 1.0:
            raise ConfigError(f"ceiling_level.targets.{name} は (0, 1): {probability!r}")
    lower = float(require(config, "ceiling_level.search.lower"))
    upper = float(require(config, "ceiling_level.search.upper"))
    tolerance = float(require(config, "ceiling_level.search.tolerance"))
    if not lower < upper or tolerance <= 0.0:
        raise ConfigError(f"ceiling_level.search は lower < upper かつ tolerance > 0: {lower}, {upper}, {tolerance}")
    return LevelRule(
        rng_seed=_positive_int(config, "ceiling_level.rng_seed"),
        n_draws=_positive_int(config, "ceiling_level.n_draws"),
        chunk=_positive_int(config, "ceiling_level.chunk"),
        n_seed=_positive_int(config, "ceiling_level.pilot_shape.n_seed"),
        n_item=_positive_int(config, "ceiling_level.pilot_shape.n_item"),
        cells=cells,
        coverages=coverages,
        template_names=templates,
        sigma=float(require(config, "ceiling_level.point.sigma")),
        rho=float(require(config, "ceiling_level.point.rho")),
        s2_item=float(require(config, "dgp.s2_item")),
        s2_tmpl=float(require(config, "dgp.s2_tmpl")),
        targets={str(k): float(v) for k, v in targets.items()},
        search_lower=lower,
        search_upper=upper,
        tolerance=tolerance,
        round_decimals=int(require(config, "ceiling_level.round_decimals")),
        table_levels=tuple(float(v) for v in require(config, "ceiling_level.table_levels")),
    )


def event_probability(level: float, rule: LevelRule) -> tuple[float, float]:
    """答える問い: 天井の水準 `level` のとき、パイロットと同じ形の観測(全セルの全試行が `rule`)が起こる確率はいくつか。

    返すのは `(確率の推定値, モンテカルロの標準誤差)`。ランダム効果を `rule.n_draws` 組引き、それぞれで
    `Π logistic(level + u + v + w)`(ランダム効果で条件づけた確率)を平均する。**乱数は毎回同じ種から引き直す**
    (共通乱数)ので、`level` について厳密に単調増加。
    """
    rng = np.random.default_rng(rule.rng_seed)
    n_cov = len(rule.coverages)
    root = compound_symmetry_sqrt(n_cov, rule.rho)
    cov_index = [rule.coverages.index(cov) for _, cov in rule.cells]
    template_of_item = np.arange(rule.n_item) % len(rule.template_names)
    total = 0.0
    total_sq = 0.0
    done = 0
    while done < rule.n_draws:
        size = min(rule.chunk, rule.n_draws - done)
        w = rng.normal(0.0, math.sqrt(rule.s2_tmpl), size=(size, len(rule.template_names)))
        u = rule.sigma * (rng.standard_normal(size=(size, rule.n_seed, n_cov)) @ root.T)
        v = rng.normal(0.0, math.sqrt(rule.s2_item), size=(size, len(rule.cells), rule.n_item))
        # (draw, cell, seed, item)。u はセルの被覆 × シード、v はセル × 項目(シードで共通)、w はテンプレート(セルで共通)
        offset = (
            u[:, :, cov_index].transpose(0, 2, 1)[..., None]
            + v[:, :, None, :]
            + w[:, template_of_item][:, None, None, :]
        )
        probability = np.exp(-np.logaddexp(0.0, -(level + offset)).sum(axis=(1, 2, 3)))
        total += float(probability.sum())
        total_sq += float((probability**2).sum())
        done += size
    mean = total / rule.n_draws
    variance = max(total_sq / rule.n_draws - mean**2, 0.0)
    return mean, math.sqrt(variance / rule.n_draws)


def solve_level(target: float, rule: LevelRule) -> dict[str, Any]:
    """答える問い: 確率が `target` に届く最小の `L` はいくつか(二分法。`event_probability` は `L` について単調増加)。

    探索区間の端で目標をまたがなければ止まる(区間を広げるのは config の決定。黙って端を返さない)。
    """
    lower, upper = rule.search_lower, rule.search_upper
    p_lower, _ = event_probability(lower, rule)
    p_upper, _ = event_probability(upper, rule)
    if not p_lower < target < p_upper:
        raise ConfigError(
            f"探索区間 [{lower}, {upper}] で確率 {p_lower:.3g} .. {p_upper:.3g} が目標 {target} をまたがない。"
            " ceiling_level.search を決め直すこと"
        )
    iterations = 0
    while upper - lower > rule.tolerance:
        mid = 0.5 * (lower + upper)
        if event_probability(mid, rule)[0] < target:
            lower = mid
        else:
            upper = mid
        iterations += 1
    exact = 0.5 * (lower + upper)
    rounded = round(exact, rule.round_decimals)
    probability, standard_error = event_probability(rounded, rule)
    return {
        "target_probability": target,
        "level_exact": exact,
        "level": rounded,
        "probability_at_level": probability,
        "monte_carlo_se_at_level": standard_error,
        "bisection_iterations": iterations,
    }


def compute_levels(rule: LevelRule) -> dict[str, Any]:
    """答える問い: 目標ごとの水準と、単調性を目で確かめる表(`table_levels` の `L` での確率)は何か。"""
    levels = {name: solve_level(target, rule) for name, target in rule.targets.items()}
    table = [
        {"level": level, "probability": p, "monte_carlo_se": se}
        for level in rule.table_levels
        for p, se in [event_probability(level, rule)]
    ]
    return {"levels": levels, "probability_table": table}


def record(rule: LevelRule, computed: Mapping[str, Any], config_path: Path | None) -> dict[str, Any]:
    """答える問い: この数は、どの run の、どの commit の、どの規則から出たか(`CLAUDE.md` §2)。"""
    now = artifacts.utc_now()
    return {
        "run_id": f"{now.strftime('%Y%m%d_%H%M%S')}_ceiling_level",
        "created_utc": now.isoformat(),
        "git_sha": artifacts.capture_git_head_sha(),
        "tracked_diff_empty": artifacts.capture_git_diff_head() == "",
        "config_source": None if config_path is None else str(config_path),
        "note": (
            "ASSUMED-VALUE arithmetic (a rule applied to the DGP), not an experimental result. "
            "The pilot tables were NOT read (PLAN-044 trap 1); the pilot shape is only the rule below."
        ),
        "rule": {
            "event": "every trial of every listed cell is rule (is_rule = 1)",
            "cells": [list(c) for c in rule.cells],
            "n_seed": rule.n_seed,
            "n_item": rule.n_item,
            "sigma": rule.sigma,
            "rho": rule.rho,
            "s2_item": rule.s2_item,
            "s2_tmpl": rule.s2_tmpl,
            "tau": 0.0,
            "rng_seed": rule.rng_seed,
            "n_draws": rule.n_draws,
            "chunk": rule.chunk,
            "search": [rule.search_lower, rule.search_upper],
            "tolerance": rule.tolerance,
            "round_decimals": rule.round_decimals,
        },
        **computed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, help="config の ceiling_level.out_dir を上書きする")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    rule = load_level_rule(config)
    out_dir = args.out_dir or resolve_repo_path(require(config, "ceiling_level.out_dir"))
    out_dir.mkdir(parents=True, exist_ok=True)
    result = record(rule, compute_levels(rule), args.config)
    write_json_atomic(out_dir / OUTPUT_FILE, result)
    print(json.dumps(
        {name: {"level": body["level"], "probability_at_level": body["probability_at_level"]}
         for name, body in result["levels"].items()},
        indent=2, ensure_ascii=True,
    ))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
