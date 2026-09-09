"""検出力シミュレーション(`Documents/05_STATISTICS.md` §6)。

答える問い: 「**どこまでの `s2_seed` なら 10 シードで検出力 0.8 に届くか**」
—— 検出力を 1 点で出すのではなく、**限界 `sigma*` を逆問題として出す**
(ADR-067 決定1 = ★F90-1 案 B。**提案 エージェント (Opus) / 採択 人間**)。

    python -m code.analysis.power_sim --config configs/power_sim.yaml --dry-run
    python -m code.analysis.power_sim --config configs/power_sim.yaml --out-dir results/power_sim

**★掃く `sigma` / `rho` はすべて仮定値であり、実験結果ではない**(`CLAUDE.md` §2)。
`results/` は空であり、`s2_seed` の実測はこの世に存在しない(ADR-067 のリスク欄)。
**§6.5 の効果量プロファイル P とまったく同じ扱いである。**

**組む(DGP)と当てる(fit)を分ける**(★F110。ADR-068 決定1)——
§6.3 手続き3 の旧記述は 1 本の式に「データを生成し」と「LRT を回す」の 2 役を
兼ねさせており、**当てはめが §3.2 と違うと「実際には回さない検定の検出力」になる。**

    3a DGP     ここ(`draw_frame`)。`Sigma = sigma^2[(1-rho)I + rho J]`
    3b 当てはめ `code/analysis/power_sim_fit.R`。§3.2 の `fit_full` / `fit_add` の対
               + ADR-059 の縮退カスケード(判定はペア単位)
    3c 集計     ここ(`summarise_grid`)。`p < alpha` の割合 = 検出力

**当てはめは R + `lme4` である**(ADR-058 決定1 / ADR-059 決定3 = D-2「同じエンジン」)。
自前実装(案 E)は建てない。**この層は表を組んで R を呼び、返った JSON を数えるだけである**
(skill `code-style` §2)。

**既定値を作らない**(skill `code-style` §5)。`dgp.n_item` / `dgp.s2_item` /
`dgp.s2_tmpl` は `configs/power_sim.yaml` で `null` であり、**そこで止まる** ——
`n_item` は `M*`(順5)待ち、分散 2 本は **★F104**(人間の確認待ち)である。
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from code.config import ConfigError, load_config, require

FIT_SCRIPT = Path(__file__).resolve().parent / "power_sim_fit.R"

# `fit.rscript` が null のときに探す既定の導入先。F48 が実測した場所である
# (`winget install --id RProject.R` は `C:/Program Files/R/R-<version>` に入る)。
RSCRIPT_NAME = "Rscript"
RSCRIPT_SEARCH_GLOB = "C:/Program Files/R/R-*/bin/Rscript.exe"

CSV_HEADER = ("seed", "task", "coverage", "item", "template", "is_rule")


class PowerSimError(RuntimeError):
    """シミュレーションを続けられない(R が無い / 当てはめが結果を返さない等)。"""


# --------------------------------------------------------------------------
# 効果量プロファイル(§6.5 / §6.6)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectProfile:
    """12 セルのロジットと、その非加法性 RMS。

    答える問い: 「勾配の形がタスク型間でどれだけ違うか」(§6.2)——
    LRT の非心度は `delta` の大きさだけで決まり、セルの水準そのものでは決まらない。
    """

    name: str
    tasks: tuple[str, ...]
    coverages: tuple[str, ...]
    eta: np.ndarray          # (n_task, n_coverage) ロジット
    delta: np.ndarray        # 加法モデルの当てはめ値を引いた残差
    nonadditivity_rms: float


def logit(p: float) -> float:
    """答える問い: `rule_rate` はロジット尺度でいくつか。"""
    if not 0.0 < p < 1.0:
        raise ValueError(f"rule_rate は (0, 1) の中でなければならない: {p}")
    return math.log(p / (1.0 - p))


def build_profile(effect: Mapping[str, Any]) -> EffectProfile:
    """config の `effect` ブロックから 12 セルのロジットと `delta` を組む。

    答える問い: 「§6.5 の表(`rule_rate`)と、そこに書かれた `mu` / `a` / `b` は
    整合しているか」—— `delta` は表から `mu + a + b` を引いた残差として定義する
    (§6.2)。表と主効果が食い違えば `delta` にそれが現れるので、ここで検算する。
    """
    tasks = tuple(effect["task_levels"])
    coverages = tuple(effect["coverage_levels"])
    rates = np.asarray(effect["rule_rate"], dtype=float)
    if rates.shape != (len(tasks), len(coverages)):
        raise ConfigError(
            f"effect.rule_rate の形が {rates.shape} で、"
            f"({len(tasks)}, {len(coverages)}) と合わない"
        )
    eta = np.vectorize(logit)(rates)
    additive = (
        float(effect["mu"])
        + np.asarray(effect["a"], dtype=float)[:, None]
        + np.asarray(effect["b"], dtype=float)[None, :]
    )
    delta = eta - additive
    # 非加法性 RMS は df = 6 あたりの残差二乗平均平方根である(§6.2)。
    # 主効果を引いた後の残差なので、行平均・列平均を除いてから測る。
    centred = delta - delta.mean(axis=0, keepdims=True) - delta.mean(axis=1, keepdims=True)
    centred = centred + delta.mean()
    df_interaction = (len(tasks) - 1) * (len(coverages) - 1)
    rms = float(np.sqrt((centred**2).sum() / df_interaction))
    return EffectProfile(
        name=str(effect["profile"]),
        tasks=tasks,
        coverages=coverages,
        eta=eta,
        delta=delta,
        nonadditivity_rms=rms,
    )


# --------------------------------------------------------------------------
# DGP(§6.3 手続き3a)
# --------------------------------------------------------------------------


def compound_symmetry_sqrt(n: int, rho: float) -> np.ndarray:
    """交換可能な相関行列の平方根。答える問い: `rho = 1` まで含めて引けるか。

    `Sigma = sigma^2 * [(1 - rho) I + rho J]` の相関部分の平方根は
    `sqrt(1 + (n-1) rho) P + sqrt(1 - rho) (I - P)`、`P = J / n`。

    **固有分解であって Cholesky ではない。**Cholesky は `rho = 1` で落ちるが、
    **`rho = 1` は `(1 | seed)` そのもの**であり、ADR-068 決定2 が
    掃くと決めた 2 枚のうちの 1 枚だからである
    (`plans/PLAN-019-check2/covariance_shape_check.py` と同じ扱い)。
    """
    if not -1.0 / (n - 1) <= rho <= 1.0:
        raise ValueError(f"rho が交換可能な相関行列の定義域の外にある: {rho}")
    projector = np.full((n, n), 1.0 / n)
    return (
        np.sqrt(1.0 + (n - 1) * rho) * projector
        + np.sqrt(1.0 - rho) * (np.eye(n) - projector)
    )


@dataclass(frozen=True)
class DesignLevels:
    """1 枚の表の水準。答える問い: どの行が存在するか。

    `template` は `category` をそのまま水準とする(ADR-062 決定2)。
    `item` は タスク型に入れ子である(§3.2。同じ被演算子でも群・`category` が
    違えば別水準になる)ので、`(task, coverage, index)` から一意に作る。
    """

    tasks: tuple[str, ...]
    coverages: tuple[str, ...]
    templates: Mapping[str, Sequence[str]]
    n_seed: int
    n_item: int


def draw_frame(
    levels: DesignLevels,
    eta_fixed: np.ndarray,
    sigma: float,
    rho: float,
    s2_item: float,
    s2_tmpl: float,
    rng: np.random.Generator,
) -> list[tuple[Any, ...]]:
    """1 反復ぶんの長形式表を引く(§6.3 手続き3a)。

    答える問い: 「§3.2 のモデルが真であるとき、10 シードの実験は
    どういう表を産むか」

    `u[s, ·] ~ N(0, Sigma)` は **`task` に依存しない** —— `(0 + coverage | seed)`
    が run ごとに持つのは被覆 3 水準のセル平均だけであり、4 タスク型すべてに
    同じ値が足される(ADR-066 決定4 (d))。
    """
    n_cov = len(levels.coverages)
    u = sigma * (
        rng.standard_normal(size=(levels.n_seed, n_cov))
        @ compound_symmetry_sqrt(n_cov, rho).T
    )

    template_ids = sorted({t for names in levels.templates.values() for t in names})
    w = {name: rng.normal(0.0, math.sqrt(s2_tmpl)) for name in template_ids}

    rows: list[tuple[Any, ...]] = []
    for ti, task in enumerate(levels.tasks):
        task_templates = list(levels.templates[task])
        for ci, cov in enumerate(levels.coverages):
            for k in range(levels.n_item):
                item = f"{task}.{cov}.{k:04d}"
                template = task_templates[k % len(task_templates)]
                v = rng.normal(0.0, math.sqrt(s2_item))
                for s in range(levels.n_seed):
                    eta = eta_fixed[ti, ci] + u[s, ci] + v + w[template]
                    is_rule = int(rng.random() < 1.0 / (1.0 + math.exp(-eta)))
                    rows.append((f"s{s:02d}", task, cov, item, template, is_rule))
    return rows


def write_frame_csv(rows: Sequence[tuple[Any, ...]], path: Path) -> None:
    """表を CSV に落とす。答える問い: R に何を渡すか。

    `csv` モジュールを使わないのは、行数が多く(数万行 × 数千枚)、
    すべて単純な文字列と 0/1 だからである。改行は LF に固定する。
    """
    with path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(",".join(CSV_HEADER) + "\n")
        for row in rows:
            handle.write("%s,%s,%s,%s,%s,%d\n" % row)


# --------------------------------------------------------------------------
# 当てはめ(§6.3 手続き3b)—— R を呼ぶだけ
# --------------------------------------------------------------------------


def resolve_rscript(declared: str | None) -> str:
    """`Rscript` の実体を決める。答える問い: この機械で当てはめが回せるか。

    config に書いてあればそれを使う。null のときだけ PATH と既定の導入先を探す
    (**既定値を作っているのではなく、実体の在り処を解決している**)。
    """
    if declared:
        if not Path(declared).exists():
            raise PowerSimError(f"config の fit.rscript が指す実体が無い: {declared}")
        return declared
    found = shutil.which(RSCRIPT_NAME)
    if found:
        return found
    import glob

    candidates = sorted(glob.glob(RSCRIPT_SEARCH_GLOB))
    if candidates:
        return candidates[-1]
    raise PowerSimError(
        "Rscript が見つからない。当てはめは R + lme4 で行う(ADR-058 決定1)。"
        "config の fit.rscript に実体のパスを書くか、--rscript で渡すこと。"
    )


def write_fit_manifest(
    path: Path,
    jobs: Sequence[tuple[Path, Path]],
    refit: Mapping[str, Any],
    max_reduction_level: int,
) -> None:
    """R に渡す平文 manifest を書く。答える問い: R は何をどの閾値で当てるか。

    R 側に JSON パーサを持ち込まないための平文である(依存を `lme4` だけに保つ)。
    閾値はここで config から流す —— **コードに直書きしない**(skill `code-style` §1)。
    """
    lines = [
        f"loglik_tolerance={refit['loglik_tolerance']}",
        f"beta_move_tolerance={refit['beta_move_tolerance']}",
        f"use_refit_for_lrt={'true' if refit['use_refit_for_lrt'] else 'false'}",
        f"max_reduction_level={max_reduction_level}",
    ]
    lines += [f"fit={csv.as_posix()}|{out.as_posix()}" for csv, out in jobs]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def run_rscript(rscript: str, libpath: str | None, manifest: Path) -> str:
    """R を 1 回起動して manifest の表をすべて当てる。

    答える問い: 当てはめは通ったか。

    **1 枚ごとに起動しない** —— R の起動と `lme4` の読み込みだけで表 1 枚あたり
    数秒かかり、1000 反復ならそれだけで数時間になる。
    """
    completed = subprocess.run(
        [rscript, str(FIT_SCRIPT), libpath or "", str(manifest)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise PowerSimError(
            f"Rscript が異常終了した (returncode={completed.returncode})\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout


# --------------------------------------------------------------------------
# 集計(§6.3 手続き3c / 手続き5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GridPoint:
    """1 つの `(sigma, rho)` の結果。★`sigma` / `rho` は仮定値である。"""

    sigma: float
    rho: float
    n_rep: int
    power: float
    reduced_rate: float
    singular_rate: float
    refit_rate: float
    mean_chisq: float


def summarise_point(sigma: float, rho: float, results: Sequence[Mapping[str, Any]],
                    alpha: float) -> GridPoint:
    """1 つの格子点をまとめる。答える問い: この仮定値の下で検出力はいくつか。

    **縮退の発火率も返す** —— ADR-064 決定4 の★リスク欄
    「10 シードで `(0 + coverage | seed)` が同定できるかは誰にも数値では言えない」に
    合成データの上で数値を与えるのが、ADR-068 決定1 を採る利の 1 つだからである。
    """
    if not results:
        raise PowerSimError(f"sigma={sigma} rho={rho} の結果が 0 件である")
    p_values = [r["p_value"] for r in results]
    if any(p is None for p in p_values):
        raise PowerSimError(
            f"sigma={sigma} rho={rho} に p 値が null の反復がある。"
            "当てはめが LRT を返していない。捨てずに原因を見ること"
        )
    n = len(results)
    return GridPoint(
        sigma=sigma,
        rho=rho,
        n_rep=n,
        power=sum(1 for p in p_values if p < alpha) / n,
        reduced_rate=sum(1 for r in results if r["reduced"]) / n,
        singular_rate=sum(
            1 for r in results if r["full_singular"] or r["add_singular"]
        ) / n,
        refit_rate=sum(
            1 for r in results if r["full_refit_done"] or r["add_refit_done"]
        ) / n,
        mean_chisq=float(np.mean([r["chisq"] for r in results])),
    )


def sigma_limit(points: Sequence[GridPoint], target_power: float) -> dict[str, Any]:
    """逆問題の答えを出す(§6.3 手続き5)。

    答える問い: 「**10 シードが検出力 `target_power` を保つ `sigma` の上限はどこか**」

    掃いた点しか見ない。**点の間を補間しない**(補間は掃いていない領域について
    語ることになる)。全域で保つ場合は「掃いた範囲の外」と返す ——
    **「限界は無い」とは書かない**(§6.3 手続き5)。
    """
    ordered = sorted(points, key=lambda p: p.sigma)
    # ★「最初に割った点」で切る。`power >= target` の点を後ろから拾わない ——
    # 曲線はモンテカルロ誤差で単調でなくなりうるので、後ろから拾うと
    # 「一度割ったのに、その先で保っている」点を限界として報告してしまう。
    last_holding: float | None = None
    first_failing: float | None = None
    for point in ordered:
        if point.power < target_power:
            first_failing = point.sigma
            break
        last_holding = point.sigma
    if first_failing is None:
        return {
            "sigma_star": None,
            "verdict": "beyond_swept_range",
            "last_holding_sigma": last_holding,
            "first_failing_sigma": None,
            "non_monotone": False,
        }
    # 掃いた点しか見ない。点の間は補間しない(掃いていない領域を語らないため)。
    return {
        "sigma_star": last_holding,
        "verdict": "inside_swept_range",
        "last_holding_sigma": last_holding,
        "first_failing_sigma": first_failing,
        "non_monotone": any(
            p.power >= target_power and p.sigma > first_failing for p in ordered
        ),
    }


def summarise_grid(points: Sequence[GridPoint], target_power: float) -> dict[str, Any]:
    """`rho` の枚ごとに逆問題の答えを並べる。答える問い: 帯の幅はどれだけか。"""
    by_rho: dict[float, list[GridPoint]] = {}
    for point in points:
        by_rho.setdefault(point.rho, []).append(point)
    return {
        "target_power": target_power,
        "by_rho": {
            str(rho): sigma_limit(group, target_power)
            for rho, group in sorted(by_rho.items())
        },
    }


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------


def load_levels(config: Mapping[str, Any]) -> DesignLevels:
    """config から水準を組む。答える問い: 未決の項目は残っていないか。

    `require` が null で止める(`code/config.py`)。**ここで既定値は作らない。**
    """
    effect = config["effect"]
    return DesignLevels(
        tasks=tuple(effect["task_levels"]),
        coverages=tuple(effect["coverage_levels"]),
        templates=require(config, "dgp.templates"),
        n_seed=int(require(config, "dgp.n_seed")),
        n_item=int(require(config, "dgp.n_item")),
    )


def plan_grid(config: Mapping[str, Any]) -> list[tuple[float, float]]:
    """掃く格子を並べる。答える問い: 何点を回すのか(★すべて仮定値である)。"""
    sigmas = [float(s) for s in require(config, "dgp.sigma")]
    rhos = [float(r) for r in require(config, "dgp.rho")]
    return [(sigma, rho) for rho in rhos for sigma in sigmas]


def run(config: Mapping[str, Any], out_dir: Path, rscript_override: str | None,
        keep_frames: bool) -> dict[str, Any]:
    """格子を回して逆問題の答えを返す。答える問い: 10 シードはどこまで保つか。

    **表を組む → R に投げる → 数える、の 3 段しかない。**
    当てはめの中身は `power_sim_fit.R` にある(skill `code-style` §2)。
    """
    profile = build_profile(config["effect"])
    levels = load_levels(config)
    s2_item = float(require(config, "dgp.s2_item"))
    s2_tmpl = float(require(config, "dgp.s2_tmpl"))
    n_rep = int(require(config, "simulation.n_rep"))
    alpha = float(require(config, "simulation.alpha"))
    target_power = float(require(config, "simulation.target_power"))
    rng = np.random.default_rng(int(require(config, "simulation.rng_seed")))

    rscript = resolve_rscript(rscript_override or config["fit"].get("rscript"))
    libpath = config["fit"].get("r_libpath")
    refit = config["fit"]["refit"]
    max_level = len(require(config, "fit.reduction_order"))

    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    fits_dir = out_dir / "fits"
    frames_dir.mkdir(exist_ok=True)
    fits_dir.mkdir(exist_ok=True)

    points: list[GridPoint] = []
    for sigma, rho in plan_grid(config):
        tag = f"s{sigma:g}_r{rho:g}".replace(".", "p")
        jobs: list[tuple[Path, Path]] = []
        for rep in range(n_rep):
            csv_path = frames_dir / f"frame_{tag}_{rep:04d}.csv"
            out_path = fits_dir / f"fit_{tag}_{rep:04d}.json"
            if not out_path.exists():
                write_frame_csv(
                    draw_frame(levels, profile.eta, sigma, rho, s2_item, s2_tmpl, rng),
                    csv_path,
                )
            jobs.append((csv_path, out_path))

        manifest = out_dir / f"manifest_{tag}.txt"
        write_fit_manifest(manifest, jobs, refit, max_level)
        run_rscript(rscript, libpath, manifest)

        results = [json.loads(out.read_text(encoding="ascii")) for _, out in jobs]
        points.append(summarise_point(sigma, rho, results, alpha))
        if not keep_frames:
            for csv_path, _ in jobs:
                csv_path.unlink(missing_ok=True)

    summary = {
        "profile": profile.name,
        "nonadditivity_rms": profile.nonadditivity_rms,
        "n_seed": levels.n_seed,
        "n_item": levels.n_item,
        "s2_item": s2_item,
        "s2_tmpl": s2_tmpl,
        "alpha": alpha,
        "assumed_values_note": (
            "sigma and rho are ASSUMED values, not measurements "
            "(05_STATISTICS.md section 6.7; ADR-067 / ADR-068)"
        ),
        "grid": [point.__dict__ for point in points],
        "inverse_problem": summarise_grid(points, target_power),
    }
    (out_dir / "power_sim_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def describe_plan(config: Mapping[str, Any]) -> list[str]:
    """回す前に「何本の当てはめになるか」を出す。答える問い: このコストは払えるか。

    F50 の実測(5760 行 / 10 シードで `full` + `add` 1 ペア平均 31.91 秒)と
    ADR-059 の再当てはめ 1.34 倍(F61)から掛け算するだけである。
    **これは算術であって実測ではない**(この機械の 1 ペアは測っていない)。
    """
    grid = plan_grid(config)
    n_rep = int(require(config, "simulation.n_rep"))
    # 出力は ASCII のみ。この環境の stdout は cp932 であり、em dash で落ちる
    # (`plans/PLAN-019-check2/` の検査スクリプトと同じ制約)。
    lines = [
        f"profile   : {config['effect']['profile']}",
        f"grid      : {len(grid)} points "
        f"(sigma {require(config, 'dgp.sigma')} x rho {require(config, 'dgp.rho')})",
        f"n_seed    : {require(config, 'dgp.n_seed')}  (ADR-028)",
        f"n_rep     : {n_rep}",
        f"fits      : {len(grid) * n_rep * 2} "
        f"(= {len(grid)} x {n_rep} x 2); a reduced iteration costs more",
        "NOTE: sigma and rho are ASSUMED values (05_STATISTICS.md section 6.7)",
    ]
    for key in ("dgp.n_item", "dgp.s2_item", "dgp.s2_tmpl"):
        try:
            lines.append(f"{key:<12}: {require(config, key)}")
        except ConfigError:
            lines.append(f"{key:<12}: UNDECIDED (null) -- the run stops here")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--rscript", help="config の fit.rscript を上書きする")
    parser.add_argument("--dry-run", action="store_true",
                        help="格子と当てはめ本数だけを出す。R を呼ばない")
    parser.add_argument("--keep-frames", action="store_true",
                        help="組んだ CSV を消さずに残す(監査用。数千枚になる)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        for line in describe_plan(config):
            print(line)
        return 0
    if args.out_dir is None:
        parser.error("--out-dir が要る(--dry-run でない場合)")
    summary = run(config, args.out_dir, args.rscript, args.keep_frames)
    print(json.dumps(summary["inverse_problem"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
