"""検出力シミュレーション(`Documents/05_STATISTICS.md` §6)。

答える問い: 「**どこまでの `s2_seed` なら 10 シードで検出力 0.8 に届くか**」
—— 検出力を 1 点で出すのではなく、**限界 `sigma*` を逆問題として出す**
(ADR-067 決定1 = ★F90-1 案 B。**提案 エージェント (Opus) / 採択 人間**)。

**★2026-10-02(PLAN-034 I2 / ADR-114)に、主要検定 T1 × T2(df = 2)の模型へ作り直した。**
4 タスク型・df = 6 の模型はもう無い(`build_profile` は df ≠ 2 で止まる)。回すのは
`configs/power_sim.yaml` の `sheets:` が宣言する**シート**である —— 検出力(P1)/ 形の検査(P1⁻)/
第一種の過誤の較正と平行性の TOST(P0)/ §3.2 に無い seed × タスク型 × 被覆の変動 `tau` を DGP にだけ
足した誤指定(D7)。**シートごとに DGP の真値と読み方が違う**(`Sheet.role`)。

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

**既定値を作らない**(skill `code-style` §5)。`dgp.s2_item` / `dgp.s2_tmpl` は
`configs/power_sim.yaml` で `null` であり、**そこで止まる**(★2026-09-24 ADR-095)。
`s2_item` / `s2_tmpl` は取得元が ADR-094 で決着し、値は人間が決め直す(決定3)。
`n_item` は ADR-114 決定3 で T1・T2 とも 80 の整数 1 つに決まった(タスク型ごとの値は主要検定については
取り下げた)。

**平行性の TOST の Δ は決めない**(ADR-114 決定5。凍結前に人間)。反復ごとに「交互作用の 2 係数の
Wald 90% CI がどちらも ±Δ に入る最小の Δ」(`equivalence_margin`)を保存し、Δ の関数としての
TOST の検出力は集計の後で読む(`tost_power`)。
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
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
    """タスク型 × 被覆のセルのロジットと、その非加法性 RMS・交互作用の係数。

    答える問い: 「勾配の形がタスク型間でどれだけ違うか」(§6.2)——
    LRT の非心度は `delta` の大きさだけで決まり、セルの水準そのものでは決まらない。
    **`interaction_contrasts` は平行性の TOST が見る量の真値である**(ADR-114 決定5)。
    """

    name: str
    tasks: tuple[str, ...]
    coverages: tuple[str, ...]
    eta: np.ndarray          # (n_task, n_coverage) ロジット
    delta: np.ndarray        # 主効果の宣言(mu + a + b)を引いた残差
    nonadditivity_rms: float
    # 処理対比・基準 = (tasks[0], coverages[0])。被覆の基準以外の水準ごとの
    # (tasks[1] - tasks[0]) x (coverage - 基準)。`glmer` の `task:coverage` の係数の真値
    interaction_contrasts: Mapping[str, float]


# ★主要検定の交互作用の df(ADR-112 決定1)。`(n_task - 1) x (n_coverage - 1)` がこれに合わなければ止まる。
PRIMARY_INTERACTION_DF = 2
# 主要検定のタスク型の数。交互作用の 2 係数(TOST の対象)は「T2 - T1」の 1 本を被覆の 2 水準で見る
N_PRIMARY_TASKS = 2

# ★実測(★F114。run:`20260909_bench_powersim`)。`full` + `add` の 1 ペア、4 タスク型 x 被覆 3 x
# `n_item = 48` x 10 シード = 5,760 行、この機械、逐次。**当て直し(ADR-059)を含む。**
# F50 の 31.91 秒の 9.3 倍。**時間はおおむね行数に比例すると仮定する**(下の `estimate_seconds_per_pair`)。
SECONDS_PER_PAIR_MEASURED = 297.6
ROWS_AT_MEASUREMENT = 5_760


def logistic(eta: float) -> float:
    """答える問い: 線形予測子 `eta`(スカラー)の確率はいくつか。大きな負の値でも溢れない。

    `1 / (1 + exp(-eta))` は `eta < -709` で `math.exp` が溢れる。誤指定の `tau` や
    巨大な分散を試す場面で落ちないよう、符号で式を分ける。
    """
    if eta >= 0.0:
        return 1.0 / (1.0 + math.exp(-eta))
    exp_eta = math.exp(eta)
    return exp_eta / (1.0 + exp_eta)


def inv_logit(eta: np.ndarray) -> np.ndarray:
    """答える問い: ロジット `eta` は `rule_rate` でいくつか。"""
    return 1.0 / (1.0 + np.exp(-eta))


def _require_shape(
    block: Mapping[str, Any], key: str, shape: tuple[int, ...], where: str
) -> np.ndarray:
    """答える問い: `effect` のこの表は (タスク型 × 被覆水準) の形をしているか。"""
    if key not in block:
        raise ConfigError(f"{where}.{key} が無い。ADR-069 決定1 でどちらも必須である")
    array = np.asarray(block[key], dtype=float)
    if array.shape != shape:
        raise ConfigError(f"{where}.{key} の形が {array.shape} で、{shape} と合わない")
    return array


def interaction_contrasts(
    eta: np.ndarray, tasks: Sequence[str], coverages: Sequence[str]
) -> dict[str, float]:
    """答える問い: `task:coverage` の係数(処理対比・基準 T1 × id)の真値はいくつか。

    `glmer` の固定効果は線形予測子の上で定義される(ランダム効果で条件づけた係数)ので、
    DGP の `eta`(ロジット)から直接出る。基準以外の被覆水準ごとに
    `(eta[T2, c] - eta[T2, 基準]) - (eta[T1, c] - eta[T1, 基準])`。
    """
    if len(tasks) != N_PRIMARY_TASKS:
        raise ConfigError(f"交互作用の係数は 2 タスク型の対比である。tasks = {list(tasks)}")
    return {
        cov: float((eta[1, ci] - eta[1, 0]) - (eta[0, ci] - eta[0, 0]))
        for ci, cov in enumerate(coverages)
        if ci > 0
    }


def build_profile(effect: Mapping[str, Any], profile_name: str) -> EffectProfile:
    """config の `effect` ブロックから、1 つのプロファイルのロジットと `delta` を組む。

    答える問い: 「DGP が意図した効果量そのものになっているか」——
    **真値は `effect.profiles.<名前>.eta`(丸める前のロジット)である**(ADR-069 決定1 = ★F112 案 (a))。
    `rule_rate`(小数第 `effect.rule_rate_decimals` 位)は DGP には使わず、
    **`eta` を丸めたものと一致するかを検査する門**として読む。両者が離れたら止まる。

    **交互作用の df が 2 でなければ止まる**(ADR-112 決定1。主要検定は T1 × T2)。

    `delta` は `eta` から `mu + a + b` を引いた残差として定義する(§6.2)。
    表と主効果が食い違えば `delta` にそれが現れるので、ここで検算になる。

    ★かつては `rule_rate` を逆変換して `eta` を作っていた。丸めが非加法性 RMS を
    0.353 → 0.3605 に膨らませ、P0 が 0.000 → 0.0285 になっていた(★F112)。
    """
    tasks = tuple(effect["task_levels"])
    coverages = tuple(effect["coverage_levels"])
    df_interaction = (len(tasks) - 1) * (len(coverages) - 1)
    if df_interaction != PRIMARY_INTERACTION_DF:
        raise ConfigError(
            f"交互作用の df が {df_interaction} である(タスク型 {len(tasks)} x 被覆 {len(coverages)})。"
            f"主要検定は T1 x T2 の df = {PRIMARY_INTERACTION_DF}(ADR-112 決定1)"
        )
    profiles = effect.get("profiles")
    if not isinstance(profiles, Mapping) or profile_name not in profiles:
        raise ConfigError(f"effect.profiles.{profile_name} が無い")
    block = profiles[profile_name]
    where = f"effect.profiles.{profile_name}"
    shape = (len(tasks), len(coverages))
    eta = _require_shape(block, "eta", shape, where)
    rates = _require_shape(block, "rule_rate", shape, where)
    decimals = int(require(effect, "rule_rate_decimals"))
    rounded = np.round(inv_logit(eta), decimals)
    if not np.array_equal(rounded, rates):
        raise ConfigError(
            f"{where}.eta を rule_rate に直して小数第{decimals} 位で丸めたものが"
            f" {where}.rule_rate と一致しない。"
            f" eta から: {rounded.tolist()} /"
            f" rule_rate: {rates.tolist()}。"
            "eta が真値で rule_rate は照合用の門である(ADR-069 決定1)。"
            "eta を動かしたのなら rule_rate も動かすこと。"
        )
    a = np.asarray(effect["a"], dtype=float)
    b = np.asarray(effect["b"], dtype=float)
    if a.shape != (len(tasks),) or b.shape != (len(coverages),):
        raise ConfigError(
            f"effect.a の長さ {a.shape} / effect.b の長さ {b.shape} が"
            f" タスク型 {len(tasks)} / 被覆 {len(coverages)} と合わない"
        )
    additive = float(effect["mu"]) + a[:, None] + b[None, :]
    delta = eta - additive
    # 非加法性 RMS は df あたりの残差二乗平均平方根である(§6.2)。
    # 主効果を引いた後の残差なので、行平均・列平均を除いてから測る。
    centred = delta - delta.mean(axis=0, keepdims=True) - delta.mean(axis=1, keepdims=True)
    centred = centred + delta.mean()
    rms = float(np.sqrt((centred**2).sum() / df_interaction))
    return EffectProfile(
        name=profile_name,
        tasks=tasks,
        coverages=coverages,
        eta=eta,
        delta=delta,
        nonadditivity_rms=rms,
        interaction_contrasts=interaction_contrasts(eta, tasks, coverages),
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
    tau: float = 0.0,
) -> list[tuple[Any, ...]]:
    """1 反復ぶんの長形式表を引く(§6.3 手続き3a)。

    答える問い: 「§3.2 のモデルが真であるとき、10 シードの実験は
    どういう表を産むか」。`tau > 0` なら**§3.2 のモデルが偽であるとき**の表である。

    `u[s, ·] ~ N(0, Sigma)` は **`task` に依存しない** —— `(0 + coverage | seed)`
    が run ごとに持つのは被覆 3 水準のセル平均だけであり、全タスク型に
    同じ値が足される(ADR-066 決定4 (d))。

    **★誤指定(ADR-114 決定7 = D7 (a))**: `tau > 0` のときだけ、シードごとに
    `z[s, task, coverage] ~ N(0, tau^2)`(すべて独立)を線形予測子に足す。**当てはめ側(§3.2)には
    この項が無い**ので、10 シードの設計が主要検定の第一種の過誤をどれだけ膨らませるかを測る装置になる。
    **`tau = 0` のときは乱数を 1 つも消費しない**ので、`tau` を渡さない呼び出しと同じ表になる
    (誤指定のシートの `tau = 0` の点が P0 のシートと一致することの根拠)。
    """
    if tau < 0.0:
        raise ValueError(f"tau は 0 以上である: {tau}")
    n_cov = len(levels.coverages)
    u = sigma * (
        rng.standard_normal(size=(levels.n_seed, n_cov))
        @ compound_symmetry_sqrt(n_cov, rho).T
    )

    template_ids = sorted({t for names in levels.templates.values() for t in names})
    w = {name: rng.normal(0.0, math.sqrt(s2_tmpl)) for name in template_ids}
    # ★テンプレートの後に引く(`tau = 0` の乱数列を `tau` を持たない経路と同じにするため)。
    z = (
        rng.normal(0.0, tau, size=(levels.n_seed, len(levels.tasks), n_cov))
        if tau > 0.0
        else np.zeros((levels.n_seed, len(levels.tasks), n_cov))
    )

    rows: list[tuple[Any, ...]] = []
    for ti, task in enumerate(levels.tasks):
        task_templates = list(levels.templates[task])
        for ci, cov in enumerate(levels.coverages):
            for k in range(levels.n_item):
                item = f"{task}.{cov}.{k:04d}"
                template = task_templates[k % len(task_templates)]
                v = rng.normal(0.0, math.sqrt(s2_item))
                for s in range(levels.n_seed):
                    eta = eta_fixed[ti, ci] + u[s, ci] + z[s, ti, ci] + v + w[template]
                    is_rule = int(rng.random() < logistic(eta))
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


def shard_jobs(
    jobs: Sequence[tuple[Path, Path]], n_workers: int
) -> list[list[tuple[Path, Path]]]:
    """当てはめを並列単位へ切り分ける。答える問い: どの表をどのプロセスが当てるか。

    **連続ブロックで切る**(ラウンドロビンではない)—— 当てはめ 1 本の費用は
    表の行数で決まり、同じ格子点なら全反復で同じである。**負荷は自然に揃う。**

    **★結果は `n_workers` に依らない。**表は親が単一の `rng` から決まった順で書き、
    当てはめは表ごとに決定的だからである。**`n_workers` は実験パラメータではなく
    実行資源のつまみである**(ADR-069 決定3)。
    """
    if n_workers < 1:
        raise ConfigError(f"fit.n_workers は 1 以上でなければならない: {n_workers}")
    if not jobs:
        return []
    n_shards = min(n_workers, len(jobs))
    size, remainder = divmod(len(jobs), n_shards)
    shards: list[list[tuple[Path, Path]]] = []
    start = 0
    for i in range(n_shards):
        stop = start + size + (1 if i < remainder else 0)
        shards.append(list(jobs[start:stop]))
        start = stop
    return shards


def run_fits(
    rscript: str,
    libpath: str | None,
    manifest_stem: Path,
    jobs: Sequence[tuple[Path, Path]],
    refit: Mapping[str, Any],
    max_reduction_level: int,
    n_workers: int,
) -> list[Path]:
    """1 つの格子点の当てはめをすべて通す。答える問い: 何本の R を同時に走らせるか。

    **★逐次では現実的でない** —— 当てはめ 1 ペアはこの機械で 297.6 秒であり
    (4 タスク型・`n_item = 48` / 5,760 行。run:`20260909_bench_powersim`)、
    T1 × T2 の 4 シート(32,000 ペア)は行数比例の推算で約 2,204 コア時になる(★F114。
    16 並列で約 138 時間。`--dry-run` が出す。**未実測**)。

    **R の起動は 1 並列単位につき 1 回だけである**(`run_rscript` の但し書きと同じ理由)。
    `subprocess.run` は待つ間 GIL を手放すので、スレッドで足りる。
    """
    shards = shard_jobs(jobs, n_workers)
    manifests: list[Path] = []
    for index, shard in enumerate(shards):
        manifest = manifest_stem.with_name(f"{manifest_stem.name}_{index:02d}.txt")
        write_fit_manifest(manifest, shard, refit, max_reduction_level)
        manifests.append(manifest)
    if len(manifests) <= 1:
        for manifest in manifests:
            run_rscript(rscript, libpath, manifest)
        return manifests
    with ThreadPoolExecutor(max_workers=len(manifests)) as pool:
        futures = [
            pool.submit(run_rscript, rscript, libpath, manifest) for manifest in manifests
        ]
        # ★1 本でも落ちたら止める。当てはめの失敗を黙って数えない(CLAUDE.md §7)。
        for future in futures:
            future.result()
    return manifests


# --------------------------------------------------------------------------
# 集計(§6.3 手続き3c / 手続き5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TostSpec:
    """平行性の TOST の形(ADR-114 決定5 = D5 (a))。答える問い: 何を見て同等と言うか。

    交互作用の 2 係数(処理対比・基準 T1 × id)の Wald `1 - 2 * alpha` 信頼区間が、
    **どちらも ±Δ に入れば同等**(IUT。片側 `alpha` ずつの 2 本の検定の積集合)。
    **Δ は決めない**(凍結前に人間)。`critical_z` は片側 `alpha` の標準正規分布の分位点である。
    """

    coverages: tuple[str, ...]      # 係数を見る被覆水準(基準以外)
    critical_z: float


def tost_spec(config: Mapping[str, Any], profile: EffectProfile) -> TostSpec:
    """config から TOST の形を組む。答える問い: 片側 alpha はいくつか(config に置いたもの)。"""
    alpha = float(require(config, "simulation.tost_alpha"))
    if not 0.0 < alpha < 0.5:
        raise ConfigError(f"simulation.tost_alpha は (0, 0.5) の中でなければならない: {alpha}")
    return TostSpec(
        coverages=tuple(profile.interaction_contrasts),
        critical_z=NormalDist().inv_cdf(1.0 - alpha),
    )


def equivalence_margin(result: Mapping[str, Any], spec: TostSpec) -> float:
    """答える問い: この反復で、同等と言える最小の Δ はいくつか。

    各係数の `|推定値| + z * SE` の最大値。**この Δ 以上なら 2 本とも区間が ±Δ に入る。**
    推定値か SE が欠けていれば止まる(捨てて数えない。`CLAUDE.md` §7)。
    """
    margins = []
    for cov in spec.coverages:
        estimate = result.get(f"interaction_{cov}_est")
        se = result.get(f"interaction_{cov}_se")
        if estimate is None or se is None:
            raise PowerSimError(
                f"当てはめの出力に交互作用の推定値か SE が無い(被覆 {cov})。"
                "TOST の最小 Δ が出せない。捨てずに原因を見ること"
            )
        margins.append(abs(float(estimate)) + spec.critical_z * float(se))
    return max(margins)


def tost_power(min_margins: Sequence[float], delta: float) -> float:
    """答える問い: 境界を ±`delta` に置いたとき、同等と言えた反復の割合はいくつか。

    **`delta` は呼び出し側が渡す**(この層は値を決めない。ADR-114 決定5)。
    """
    if not min_margins:
        raise PowerSimError("最小 Δ が 0 件である")
    return sum(1 for m in min_margins if m <= delta) / len(min_margins)


@dataclass(frozen=True)
class GridPoint:
    """1 つの `(sigma, rho)` の結果。★`sigma` / `rho` は仮定値である。

    `power` は **棄却率**である(P1 のシートでは検出力、P0・誤指定のシートでは第一種の過誤の率)。
    `tost_min_margins` は反復ごとの「同等と言える最小の Δ」(昇順。TOST を見ないときは空)。
    """

    sigma: float
    rho: float
    n_rep: int
    power: float
    reduced_rate: float
    singular_rate: float
    refit_rate: float
    mean_chisq: float
    # 当てはめが例外で落ち、縮退へ進んだ反復の割合(`power_sim_fit.R` の `errored_result`。暫定の扱い)
    errored_rate: float
    tost_min_margins: tuple[float, ...] = ()


def summarise_point(sigma: float, rho: float, results: Sequence[Mapping[str, Any]],
                    alpha: float, tost: TostSpec | None = None) -> GridPoint:
    """1 つの格子点をまとめる。答える問い: この仮定値の下で検出力はいくつか。

    **縮退の発火率も返す** —— ADR-064 決定4 の★リスク欄
    「10 シードで `(0 + coverage | seed)` が同定できるかは誰にも数値では言えない」に
    合成データの上で数値を与えるのが、ADR-068 決定1 を採る利の 1 つだからである。
    """
    if not results:
        raise PowerSimError(f"sigma={sigma} rho={rho} の結果が 0 件である")
    p_values = [r["p_value"] for r in results]
    if any(p is None for p in p_values):
        reasons = sorted({r.get("first_error", "") for r in results if r["p_value"] is None} - {""})
        raise PowerSimError(
            f"sigma={sigma} rho={rho} に p 値が null の反復がある。"
            "当てはめが LRT を返していない。捨てずに原因を見ること"
            + (f"(当てはめの例外: {reasons})" if reasons else "")
        )
    n = len(results)
    margins = (
        tuple(sorted(equivalence_margin(r, tost) for r in results))
        if tost is not None
        else ()
    )
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
        errored_rate=sum(1 for r in results if r["n_errored_fits"] > 0) / n,
        tost_min_margins=margins,
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


def compare_power(
    reference: Sequence[GridPoint], other: Sequence[GridPoint]
) -> list[dict[str, Any]]:
    """答える問い: 同じ `(sigma, rho)` で、2 つのシートの棄却率はどれだけ違うか。

    形の検査(ADR-114 決定2 = D2 (a))に使う: **LRT(df = 2)は非加法性の「形」を区別しない**ので、
    P1 と P1⁻ の差はモンテカルロ誤差の範囲に収まるはずである。**大きくずれたらバグを疑う**
    (`CLAUDE.md` §7)。基準のシートに無い点は返さない(掃いていない点を補わない)。
    """
    by_key = {(p.sigma, p.rho): p for p in reference}
    return [
        {
            "sigma": p.sigma,
            "rho": p.rho,
            "reference_power": by_key[(p.sigma, p.rho)].power,
            "power": p.power,
            "difference": p.power - by_key[(p.sigma, p.rho)].power,
            "reference_mean_chisq": by_key[(p.sigma, p.rho)].mean_chisq,
            "mean_chisq": p.mean_chisq,
        }
        for p in other
        if (p.sigma, p.rho) in by_key
    ]


# --------------------------------------------------------------------------
# シート(ADR-114 決定2・4・7)
# --------------------------------------------------------------------------

ROLE_POWER = "power"
ROLE_SHAPE_CHECK = "shape_check"
ROLE_NULL_CALIBRATION = "null_calibration"
ROLE_MISSPECIFICATION = "misspecification"
ROLES = (ROLE_POWER, ROLE_SHAPE_CHECK, ROLE_NULL_CALIBRATION, ROLE_MISSPECIFICATION)
# 非加法性を持つ(RMS > 0)シート。残りは厳密に加法(RMS = 0)のプロファイルを使う
ROLES_WITH_NONADDITIVITY = (ROLE_POWER, ROLE_SHAPE_CHECK)
TAU_ZERO = "zero"
TAU_EQUALS_SIGMA = "equals_sigma"
ALL_POINTS = "all"
# 厳密に加法のプロファイルの RMS の許容(丸めを持たない `eta` なので浮動小数点の誤差だけ)
ADDITIVE_RMS_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Sheet:
    """シート 1 枚。答える問い: どのプロファイルをどの格子で回し、どう読むか。"""

    sheet_id: str
    role: str
    profile: str
    sigma: tuple[float, ...]
    rho: tuple[float, ...]
    tau: str
    compare_with: str | None


def _select_points(
    declared: Any, grid: Sequence[float], key: str, sheet_id: str
) -> tuple[float, ...]:
    """答える問い: このシートは `dgp.<key>` のどの点を回すか。掃いていない点は作らない。"""
    if declared == ALL_POINTS:
        return tuple(float(x) for x in grid)
    if not isinstance(declared, list) or not declared:
        raise ConfigError(
            f"sheets[{sheet_id}].{key} は '{ALL_POINTS}' か空でないリストである: {declared!r}"
        )
    chosen = tuple(float(x) for x in declared)
    swept = {float(g) for g in grid}
    outside = [x for x in chosen if x not in swept]
    if outside:
        raise ConfigError(
            f"sheets[{sheet_id}].{key} に dgp.{key} の格子に無い点がある: {outside}"
            "(掃く格子は ADR-068 決定3)"
        )
    return chosen


def load_sheets(config: Mapping[str, Any]) -> list[Sheet]:
    """config の `sheets:` を読む。答える問い: 宣言したシートは整合しているか。

    **役割とプロファイルの食い違いで止まる**: 非加法性のあるシート(power / shape_check)は
    RMS > 0、加法のシート(null_calibration / misspecification)は RMS = 0 でなければならない。
    P1 と P0 の取り違えは、検出力と第一種の過誤を入れ替えて読む事故になる。
    """
    declared = require(config, "sheets")
    effect = config["effect"]
    sigma_grid = require(config, "dgp.sigma")
    rho_grid = require(config, "dgp.rho")
    sheets: list[Sheet] = []
    for entry in declared:
        sheet_id = str(entry["id"])
        if any(sheet.sheet_id == sheet_id for sheet in sheets):
            raise ConfigError(f"sheets の id が重複している: {sheet_id}")
        role = entry["role"]
        if role not in ROLES:
            raise ConfigError(f"sheets[{sheet_id}].role は {ROLES} のどれか: {role!r}")
        tau = entry["tau"]
        if tau not in (TAU_ZERO, TAU_EQUALS_SIGMA):
            raise ConfigError(
                f"sheets[{sheet_id}].tau は {TAU_ZERO} か {TAU_EQUALS_SIGMA}: {tau!r}"
            )
        if (role == ROLE_MISSPECIFICATION) != (tau == TAU_EQUALS_SIGMA):
            raise ConfigError(
                f"sheets[{sheet_id}]: tau = {tau} と role = {role} が合わない。"
                "tau を足すのは誤指定のシート(ADR-114 決定7)だけである"
            )
        profile = build_profile(effect, str(entry["profile"]))
        additive = profile.nonadditivity_rms <= ADDITIVE_RMS_TOLERANCE
        if (role in ROLES_WITH_NONADDITIVITY) == additive:
            raise ConfigError(
                f"sheets[{sheet_id}]: role = {role} に対してプロファイル {profile.name} の"
                f"非加法性 RMS = {profile.nonadditivity_rms:.6f} が合わない"
                "(power / shape_check は RMS > 0、null_calibration / misspecification は RMS = 0)"
            )
        compare_with = entry.get("compare_with")
        if (role == ROLE_SHAPE_CHECK) != (compare_with is not None):
            raise ConfigError(
                f"sheets[{sheet_id}]: compare_with を持つのは形の検査のシートだけで、"
                "形の検査のシートは必ず持つ"
            )
        if compare_with is not None and not any(s.sheet_id == compare_with for s in sheets):
            raise ConfigError(
                f"sheets[{sheet_id}].compare_with = {compare_with} は、"
                "より上のシートの id でなければならない"
            )
        sheets.append(
            Sheet(
                sheet_id=sheet_id,
                role=role,
                profile=profile.name,
                sigma=_select_points(entry["sigma"], sigma_grid, "sigma", sheet_id),
                rho=_select_points(entry["rho"], rho_grid, "rho", sheet_id),
                tau=tau,
                compare_with=compare_with,
            )
        )
    return sheets


def sheet_grid(sheet: Sheet) -> list[tuple[float, float]]:
    """答える問い: このシートは何点を回すのか(★すべて仮定値である)。"""
    return [(sigma, rho) for rho in sheet.rho for sigma in sheet.sigma]


def plan_grid(config: Mapping[str, Any]) -> list[tuple[str, float, float]]:
    """全シートの格子点を並べる。答える問い: 何点を回すのか。

    返すのは `(シートの id, sigma, rho)`。**乱数は上から順に引く**(`run` はこの順で引く)。
    """
    return [
        (sheet.sheet_id, sigma, rho)
        for sheet in load_sheets(config)
        for sigma, rho in sheet_grid(sheet)
    ]


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


def frame_tau(sheet: Sheet, sigma: float) -> float:
    """答える問い: この格子点で DGP に足す seed × タスク型 × 被覆の変動の SD はいくつか。"""
    return sigma if sheet.tau == TAU_EQUALS_SIGMA else 0.0


def sheet_summary(
    sheet: Sheet, profile: EffectProfile, points: Sequence[GridPoint], target_power: float
) -> dict[str, Any]:
    """シート 1 枚の結果をまとめる。答える問い: このシートは何を言うための数か。

    **`power` の読み方はシートの役割で違う**: power のシートは検出力(`sigma*` を出す)、
    null_calibration / misspecification のシートは第一種の過誤の率、shape_check は形の検査。
    """
    summary: dict[str, Any] = {
        "role": sheet.role,
        "profile": profile.name,
        "nonadditivity_rms": profile.nonadditivity_rms,
        # 平行性の TOST が見る係数の真値(logit。処理対比・基準 T1 x id)
        "true_interaction_contrasts": dict(profile.interaction_contrasts),
        "tau": sheet.tau,
        "grid": [point.__dict__ for point in points],
    }
    if sheet.role == ROLE_POWER:
        summary["inverse_problem"] = summarise_grid(points, target_power)
    return summary


def run(config: Mapping[str, Any], out_dir: Path, rscript_override: str | None,
        keep_frames: bool, workers_override: int | None = None) -> dict[str, Any]:
    """シートを順に回して結果を返す。答える問い: 10 シードはどこまで保つか。

    **表を組む → R に投げる → 数える、の 3 段しかない。**
    当てはめの中身は `power_sim_fit.R` にある(skill `code-style` §2)。

    **表は再開しても同じになる**: 当てはめが済んでいる反復でも表は引き直し(乱数を進め)、
    CSV を書くのだけを飛ばす。乱数を進めずに飛ばすと、途中から再開した表が最初の実行と違う。
    """
    sheets = load_sheets(config)
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
    n_workers = int(workers_override or require(config, "fit.n_workers"))

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet_summaries: dict[str, Any] = {}
    sheet_points: dict[str, list[GridPoint]] = {}
    for sheet in sheets:
        profile = build_profile(config["effect"], sheet.profile)
        tost = tost_spec(config, profile)
        sheet_dir = out_dir / sheet.sheet_id
        frames_dir = sheet_dir / "frames"
        fits_dir = sheet_dir / "fits"
        frames_dir.mkdir(parents=True, exist_ok=True)
        fits_dir.mkdir(exist_ok=True)

        points: list[GridPoint] = []
        for sigma, rho in sheet_grid(sheet):
            tag = f"s{sigma:g}_r{rho:g}".replace(".", "p")
            jobs: list[tuple[Path, Path]] = []
            for rep in range(n_rep):
                csv_path = frames_dir / f"frame_{tag}_{rep:04d}.csv"
                out_path = fits_dir / f"fit_{tag}_{rep:04d}.json"
                rows = draw_frame(
                    levels, profile.eta, sigma, rho, s2_item, s2_tmpl, rng,
                    tau=frame_tau(sheet, sigma),
                )
                if not out_path.exists():
                    write_frame_csv(rows, csv_path)
                jobs.append((csv_path, out_path))

            run_fits(
                rscript, libpath, sheet_dir / f"manifest_{tag}", jobs, refit, max_level, n_workers
            )

            results = [json.loads(out.read_text(encoding="ascii")) for _, out in jobs]
            points.append(summarise_point(sigma, rho, results, alpha, tost))
            if not keep_frames:
                for csv_path, _ in jobs:
                    csv_path.unlink(missing_ok=True)

        sheet_points[sheet.sheet_id] = points
        sheet_summaries[sheet.sheet_id] = sheet_summary(sheet, profile, points, target_power)
        if sheet.compare_with is not None:
            sheet_summaries[sheet.sheet_id]["compared_with"] = sheet.compare_with
            sheet_summaries[sheet.sheet_id]["power_minus_reference"] = compare_power(
                sheet_points[sheet.compare_with], points
            )

    summary = {
        "n_seed": levels.n_seed,
        "n_item": levels.n_item,
        "s2_item": s2_item,
        "s2_tmpl": s2_tmpl,
        "alpha": alpha,
        "tost_alpha": float(require(config, "simulation.tost_alpha")),
        "tost_delta_note": (
            "tost_min_margins is, per replication, the smallest delta at which both interaction "
            "CIs fall inside +-delta; the TOST power at any delta is the share <= delta "
            "(tost_power). delta is NOT chosen here (ADR-114 decision 5)"
        ),
        # ★実行資源のつまみであって実験パラメータではない。結果はこの値に依らない
        # (ADR-069 決定3)。それでも「何並列で回したか」は再現の記録として残す。
        "n_workers": n_workers,
        "assumed_values_note": (
            "sigma and rho are ASSUMED values, not measurements "
            "(05_STATISTICS.md section 6.7; ADR-067 / ADR-068)"
        ),
        "sheets": sheet_summaries,
    }
    (out_dir / "power_sim_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def estimate_seconds_per_pair(levels: DesignLevels) -> float:
    """答える問い: この表 1 枚の当てはめ(`full` + `add` の 1 ペア)は何秒か(★推算)。

    実測は 5,760 行で 297.6 秒(★F114)。**行数に比例すると仮定する**。
    T1 × T2・`n_item = 80` の 4,800 行は約 248 秒になる(PLAN-034 §5.2)。**未実測**。
    """
    rows = levels.n_seed * len(levels.tasks) * len(levels.coverages) * levels.n_item
    return SECONDS_PER_PAIR_MEASURED * rows / ROWS_AT_MEASUREMENT


def describe_plan(config: Mapping[str, Any], workers_override: int | None = None) -> list[str]:
    """回す前に「何本の当てはめになるか」を出す。答える問い: このコストは払えるか。

    **★2026-09-09 に この機械で 1 ペアを測った**(★F114。run:`20260909_bench_powersim`)——
    5,760 行で **297.6 秒 / ペア**。**F50 の 31.91 秒の 9.3 倍**である
    (F50 は `(1 | seed)` を測っており、§3.2 が回すのは `(0 + coverage | seed)` = 6 パラメータ)。
    **下のコア時はその実測を行数で比例させた推算であり、`n_item` に比例して動く。**
    """
    sheets = load_sheets(config)
    n_rep = int(require(config, "simulation.n_rep"))
    n_points = sum(len(sheet_grid(sheet)) for sheet in sheets)
    # 出力は ASCII のみ。この環境の stdout は cp932 であり、em dash で落ちる
    # (`plans/PLAN-019-check2/` の検査スクリプトと同じ制約)。
    lines = [f"sheets    : {len(sheets)}"]
    for sheet in sheets:
        n_points_here = len(sheet_grid(sheet))
        lines.append(
            f"  {sheet.sheet_id:<16} {sheet.role:<17} profile {sheet.profile:<7} "
            f"{n_points_here:>2} points x {n_rep} reps = {n_points_here * n_rep} pairs"
            f"  (sigma {list(sheet.sigma)} x rho {list(sheet.rho)}, tau {sheet.tau})"
        )
    n_pairs = n_points * n_rep
    lines += [
        f"n_seed    : {require(config, 'dgp.n_seed')}  (ADR-028)",
        f"n_rep     : {n_rep}",
        f"fits      : {n_pairs * 2} "
        f"(= {n_points} points x {n_rep} x 2); a reduced iteration costs more",
        "NOTE: sigma and rho are ASSUMED values (05_STATISTICS.md section 6.7)",
    ]
    workers = int(workers_override or config["fit"].get("n_workers") or 1)
    try:
        seconds = estimate_seconds_per_pair(load_levels(config))
        core_hours = n_pairs * seconds / 3600.0
        lines += [
            f"cost      : {core_hours:.0f} core-hours at {seconds:.1f} s/pair "
            f"(ESTIMATED: {SECONDS_PER_PAIR_MEASURED} s measured at {ROWS_AT_MEASUREMENT} rows, "
            "scaled by rows; run 20260909_bench_powersim)",
            f"            {core_hours / workers:.0f} wall-clock hours "
            f"at fit.n_workers={workers}; scales with n_item",
        ]
    except ConfigError:
        lines.append("cost      : UNDECIDED (dgp.n_item or dgp.templates is null) -- cannot scale")
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
    parser.add_argument("--workers", type=int,
                        help="config の fit.n_workers を上書きする(同時に走らせる Rscript の本数)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        for line in describe_plan(config, args.workers):
            print(line)
        return 0
    if args.out_dir is None:
        parser.error("--out-dir が要る(--dry-run でない場合)")
    summary = run(config, args.out_dir, args.rscript, args.keep_frames, args.workers)
    inverse = {
        sheet_id: body["inverse_problem"]
        for sheet_id, body in summary["sheets"].items()
        if "inverse_problem" in body
    }
    print(json.dumps(inverse, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
