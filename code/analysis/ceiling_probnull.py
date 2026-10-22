"""確率の尺度の帰無のシート `ceiling_probnull` の `eta` を解く(PLAN-046 §6.2・I4 / ADR-132 決定4)。

答える問い: 「T1 の行を `ceiling_null` と同じにし(T1 × `id` = `L`)、T2 × `id` を基のままにしたとき、
周辺確率の差の差(処理対比・基準 T1 × `id`)が interp・extrap とも 0 になる T2 × interp・T2 × extrap の `eta` はいくつか」

    python -m code.analysis.ceiling_probnull --config configs/power_sim_ceiling_probnull.yaml

**規則**(config の `sheets` の `probability_null` と `ceiling.probability_null`。2026-10-22 その178 に人間が案 A):

- 周辺確率はランダム効果を積分した `rule_rate`(`power_sim.marginal_rule_rates`。分散 = `sigma^2 + s2_item + s2_tmpl`、
  `tau` 0、節点 `ceiling.report.quadrature_nodes`)。**`power_sim.ceiling_true_values` が真値の算出に使うのと同じ関数**
- 解くセル `(t2, c)` は 1 つずつ、`p(eta) = p[t2, id] + (p[t1, c] - p[t1, id])` の根(`p` は `eta` について厳密に単調増加なので根は 1 つ)。
  目標が (0, 1) の外なら解は無く、止まる
- 解いた値は `round_decimals` 桁に丸めて config の `ceiling.probability_null.solved` に転記する。**丸めた値での残差**を記録し、
  `residual_tolerance` を超えたら止まる

出力は `results/power_sim/ceiling_probnull_solve/`。これは仮定値の算術で、実験結果ではない(`CLAUDE.md` §2)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import brentq

from code import artifacts
from code.analysis import power_sim
from code.config import ConfigError, load_config, require, resolve_repo_path

OUTPUT_FILE = "ceiling_probnull_solve.json"


@dataclass(frozen=True)
class SolveRule:
    """解く規則。答える問い: どのセルを、どの分散の周辺確率で、どの区間・桁・許容で解くか。"""

    solve_cells: tuple[tuple[str, str], ...]
    variance: float
    nodes: int
    lower: float
    upper: float
    xtol: float
    round_decimals: int
    residual_tolerance: float


def load_solve_rule(config: Mapping[str, Any], sheet: power_sim.Sheet) -> SolveRule:
    """答える問い: このシートの点で解く規則は config に宣言されているか(null・欠けは止まる)。"""
    effect = config["effect"]
    raw_cells = require(config, "ceiling.probability_null.solve_cells")
    cells = power_sim._parse_ceiling_cells(raw_cells, effect, sheet.sheet_id)
    (point,) = sheet.points
    variance = point.sigma**2 + float(require(config, "dgp.s2_item")) + float(require(config, "dgp.s2_tmpl"))
    search = require(config, "ceiling.probability_null.search")
    rule = SolveRule(
        solve_cells=cells,
        variance=variance,
        nodes=power_sim.load_ceiling_report_spec(config).quadrature_nodes,
        lower=float(search["lower"]),
        upper=float(search["upper"]),
        xtol=float(search["xtol"]),
        round_decimals=int(require(config, "ceiling.probability_null.round_decimals")),
        residual_tolerance=float(require(config, "ceiling.probability_null.residual_tolerance")),
    )
    if not rule.lower < rule.upper or rule.xtol <= 0.0 or rule.residual_tolerance <= 0.0:
        raise ConfigError(f"ceiling.probability_null の探索区間・許容が不正: {rule}")
    return rule


def marginal_rate(eta: float, rule: SolveRule) -> float:
    """答える問い: `eta` のセルの周辺の `rule_rate` はいくつか(`ceiling_true_values` と同じ積分)。"""
    return float(power_sim.marginal_rule_rates(np.asarray([eta]), rule.variance, rule.nodes)[0])


def solve_cell(target: float, rule: SolveRule) -> float:
    """答える問い: 周辺確率が `target` になる `eta` はいくつか(根は 1 つ。無ければ止まる)。"""
    if not 0.0 < target < 1.0:
        raise power_sim.PowerSimError(f"目標の周辺確率 {target} が (0, 1) の外。確率の尺度で加法な eta は無い")
    return float(brentq(lambda e: marginal_rate(e, rule) - target, rule.lower, rule.upper, xtol=rule.xtol))


def solve_probability_null(
    base_eta: np.ndarray, tasks: Sequence[str], coverages: Sequence[str], spec: power_sim.CeilingSpec,
    level: float, rule: SolveRule,
) -> dict[tuple[str, str], float]:
    """答える問い: 天井の行を `ceiling_null` と同じにしたとき、解くセルの `eta`(丸める前)はいくつか。

    解くセルは天井でない行の、基準の被覆(`coverages[0]`)以外のセルに限る(基準のセルを解くと目標が自分に依存する)。
    """
    ((ceiling_task, _),) = spec.cells
    shift_spec = power_sim.CeilingSpec(
        base_profile=spec.base_profile, mode=power_sim.CEILING_MODE_SHIFT_TASK, cells=spec.cells,
        level_name=spec.level_name,
    )
    eta = power_sim.build_ceiling_eta(base_eta, tasks, coverages, shift_spec, level)
    reference = coverages[0]
    ti_ceiling = tasks.index(ceiling_task)
    out: dict[tuple[str, str], float] = {}
    for task, coverage in rule.solve_cells:
        if task == ceiling_task or coverage == reference:
            raise ConfigError(
                f"解くセル {task}.{coverage} は天井の行 {ceiling_task} でも基準の被覆 {reference} でもあってはならない"
            )
        ti, ci = tasks.index(task), coverages.index(coverage)
        ceiling_gap = marginal_rate(eta[ti_ceiling, ci], rule) - marginal_rate(eta[ti_ceiling, 0], rule)
        out[(task, coverage)] = solve_cell(marginal_rate(eta[ti, 0], rule) + ceiling_gap, rule)
    return out


def rounded(solved: Mapping[tuple[str, str], float], decimals: int) -> dict[str, float]:
    """答える問い: config に転記する値(`"<タスク型>.<被覆>": 値`)は何か。"""
    return {f"{task}.{coverage}": round(value, decimals) for (task, coverage), value in solved.items()}


def solve_sheet(config: Mapping[str, Any], sheet: power_sim.Sheet) -> dict[str, Any]:
    """答える問い: このシートの解いた値・丸めた値・丸めた値での `eta` と周辺確率と残差は何か(残差が許容を超えたら止まる)。"""
    spec = sheet.ceiling
    if spec is None or spec.mode != power_sim.CEILING_MODE_PROBABILITY_NULL:
        raise ConfigError(f"シート {sheet.sheet_id} は {power_sim.CEILING_MODE_PROBABILITY_NULL} のシートではない")
    rule = load_solve_rule(config, sheet)
    base = power_sim.build_profile(config["effect"], spec.base_profile)
    level = power_sim.resolve_ceiling_level(config, spec.level_name)
    solved = solve_probability_null(base.eta, base.tasks, base.coverages, spec, level, rule)
    transcribed = rounded(solved, rule.round_decimals)
    cells = {
        (label.partition(".")[0], label.partition(".")[2]): value for label, value in transcribed.items()
    }
    eta = power_sim.build_ceiling_eta(base.eta, base.tasks, base.coverages, spec, level, cells)
    rates = power_sim.marginal_rule_rates(eta, rule.variance, rule.nodes)
    residuals = power_sim.probability_contrasts(rates, base.coverages)
    worst = max(abs(v) for v in residuals.values())
    if worst > rule.residual_tolerance:
        raise power_sim.PowerSimError(
            f"{sheet.sheet_id}: 丸めた値での確率の尺度の残差 {worst:.3g} > 許容 {rule.residual_tolerance:g}"
        )
    return {
        "level_name": spec.level_name,
        "level": level,
        "point": {"sigma": sheet.points[0].sigma, "variance": rule.variance, "nodes": rule.nodes},
        "solved_unrounded": {f"{t}.{c}": v for (t, c), v in solved.items()},
        "solved": transcribed,
        "eta": eta.tolist(),
        "marginal_rule_rate": {
            task: {cov: float(rates[ti, ci]) for ci, cov in enumerate(base.coverages)}
            for ti, task in enumerate(base.tasks)
        },
        "probability_scale_residuals": residuals,
        "max_abs_residual": worst,
        # ロジットの尺度では平行でない(記録だけ)。G1 で天井でない反復のロジットの LRT が棄却するのは、この値のため
        "logit_interaction_contrasts": power_sim.ceiling_logit_contrasts(eta, base.coverages),
    }


def record(config: Mapping[str, Any], sheets: Mapping[str, Any], config_path: Path | None) -> dict[str, Any]:
    """答える問い: この数は、どの run の、どの commit の、どの規則から出たか(`CLAUDE.md` §2)。"""
    now = artifacts.utc_now()
    return {
        "run_id": f"{now.strftime('%Y%m%d_%H%M%S')}_ceiling_probnull_solve",
        "created_utc": now.isoformat(),
        "git_sha": artifacts.capture_git_head_sha(),
        "tracked_diff_empty": artifacts.capture_git_diff_head() == "",
        "config_source": None if config_path is None else str(config_path),
        "note": (
            "ASSUMED-VALUE arithmetic (solving the DGP for probability-scale additivity), not an experimental result. "
            "Design A (2026-10-22, proposed by the agent, adopted by the human): T1 row = ceiling_null, "
            "T2 x id = base, T2 x interp / extrap solved."
        ),
        "rule": {
            "solve_cells": [list(c) for c in config["ceiling"]["probability_null"]["solve_cells"]],
            "search": config["ceiling"]["probability_null"]["search"],
            "round_decimals": config["ceiling"]["probability_null"]["round_decimals"],
            "residual_tolerance": config["ceiling"]["probability_null"]["residual_tolerance"],
        },
        "sheets": sheets,
    }


def probability_null_sheets(config: Mapping[str, Any]) -> list[power_sim.Sheet]:
    """答える問い: config の中で `probability_null` のシートはどれか(無ければ止まる)。"""
    sheets = [
        s for s in power_sim.load_sheets(config)
        if s.ceiling is not None and s.ceiling.mode == power_sim.CEILING_MODE_PROBABILITY_NULL
    ]
    if not sheets:
        raise ConfigError(f"{power_sim.CEILING_MODE_PROBABILITY_NULL} のシートが無い")
    return sheets


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, help="config の ceiling.probability_null.out_dir を上書きする")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    sheets = {s.sheet_id: solve_sheet(config, s) for s in probability_null_sheets(config)}
    out_dir = args.out_dir or resolve_repo_path(require(config, "ceiling.probability_null.out_dir"))
    out_dir.mkdir(parents=True, exist_ok=True)
    result = record(config, sheets, args.config)
    power_sim.write_json_atomic(out_dir / OUTPUT_FILE, result)
    print(json.dumps(
        {"run_id": result["run_id"],
         **{sid: {"solved": body["solved"], "max_abs_residual": body["max_abs_residual"]}
            for sid, body in sheets.items()}},
        indent=2, ensure_ascii=True,
    ))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
