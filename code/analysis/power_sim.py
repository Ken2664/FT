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
    3c 集計     ここ(`summarise_point` / `inverse_problem`)。`p < alpha` の割合 = 検出力

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

**★2026-10-04(PLAN-040 I1〜I7 / ADR-122・ADR-123)に軸・順・乱数・報告量を作り直した。**

- **軸**: 主の軸は `n_item`(検出力分析の中だけの格子。実際の `eval.cells` とは別物)。`sigma` は確認点。
  シートは点 `(n_item, sigma, rho)` を明示して並べる(`sheets[].points`)
- **順**: 誤指定 → P1 → P1⁻ → P0。**各段で誤指定を回し終えたら門を判定し**(`misspecification_gate`)、
  膨らめばその段の P1 の前で止まる(ADR-123 決定6)
- **乱数**: 「シート × 点 × 反復」ごとの `SeedSequence`(`replication_rng`)。**段を足しても前の表は変わらない**
  (反復 r の表は `n_rep` にも他の点にも依らない)
- **段**: `simulation.n_rep_stages`(累積)。**1 回の起動で回すのは `--through-stage` で指定した段まで**
  (人間 2026-10-04 その143: 段ごとに止まり、人間が見てから次の段を起動する)
- **報告量**: P1 の「0.8 に届く `n_item` の範囲」(`n_item_range`。主)/ `sigma*`(`sigma_limit`。従)/
  P0・P1 の最小 Δ の分位点を各 `n_item` で並べた表(`margin_quantile_table`)
- **記録**: `run_info.json`(run_id・git sha・dirty)・`config.yaml` の写し・`invocations.jsonl`・
  段ごとの `stage_<n_rep>_summary.json`。JSON は一時ファイル + rename で書く

**★2026-10-05(PLAN-041 I1〜I5 / ADR-124)に §3.2 のランダム構造・誤指定の門・当てはめ失敗の数え方を改めた。**

- **当てはめ**: `(1 | seed:task:coverage)` を足し、縮退は template → 傾きの相関 → 傾き(= 床)。
  item と新しい項は落とさない(`power_sim_fit.R`)
- **当てはめ失敗**: 床でも収束しない / 例外の表は p 値なし(`fit_failed`)。~~**シートの役割で不利な側に数える**
  (誤指定・P0 = 棄却 / P1・P1⁻ = 非棄却。`FAILURE_AS_REJECT_ROLES`)~~ → ★ADR-128: どのシートでも非棄却(下)。
  `failed_rate` を別に出す。~~**TOST の最小 Δ でも同じ向きに数える**(ADR-125: 過誤のシート = 同等と言えない /
  検出力のシート = 同等と言えた)~~ → ★ADR-128 決定4: どのシートでも同等と言えない(Δ = +∞)
- **誤指定のシート**: 独立な `z`(今のシート)に加え、**シード固有の交互作用**(`z = m_s × d`・`m_s ~ N(0, tau²)`)の
  2 枚(大きさ `subspace` = (ii)・`per_cell` = (i))。門は `misspecification_gate.sheets` に挙げたシート((ii) と今のシート)に
  掛け、(i) は記録だけ。誤指定のシートは先頭にまとめて並べ、**その全部を回した後に**門を判定する
- **P1 の確認点**: `tau` に数値を書ける形(`sheets[].tau: 0.5`)。同じ点 `(80, 1.0, 0.0)` が P1 のシートにあるので
  別のシート(`p1_tau`)にした(乱数の鍵とファイル名が点で決まるため)

**★2026-10-08(PLAN-043 I1〜I5 / ADR-128・ADR-129)に、床の `allFit` の段・失敗の数え方・2 つの門を改めた。**

- **床の `allFit` の段**(`power_sim_fit.R`): 床で ADR-059 の判定が収束しない表に、床の式(full・add)へ `allFit` を
  1 段足す。最適化は名前で列挙(`fit.allfit`)・`start_from_mle = false`・版が違えば止まる。full と add の両方が
  「警告なしに収束した最適化が 2 つ以上・logLik の差 < 0.001」なら収束。それでも収束しなければ「当てはめ失敗」。
  床の土台の `glmer` が例外なら救わずに失敗(件数を別に記録)
- **当てはめ失敗の数え方**: どのシートでも**非棄却**(分母に入れる)。成功した反復だけの棄却数と、失敗した反復だけの
  記述の p 値(`p_value_failed_descriptive`)を並べる(どの門にも使わない)。TOST もどのシートでも Δ = +∞
- **過誤の門**(`misspecification_gate.points`): 判定点を**シートごと**に(基本の誤指定の `tau` 0.25・0.5・1.0 /
  seed_subspace の 0.25・0.5)。閾値は 0.075 のまま。終了コード 3
- **実行可能性の門**(`simulation.feasibility_gate`): 全シート・全点で当てはめ失敗の率の CP95 下端 > 0.10 なら閉じる。
  誤指定の 3 枚はまとめて回した後、以降は各シートを回し終えるごとに判定し、閉じたら次のシートの前で止まる。終了コード 4
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
from scipy.stats import beta as beta_distribution

from code import artifacts
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
# ★2 本目の基準(ADR-123 文脈1・2)。PLAN-034 の見直しの小検査(`plans/PLAN-034-check-prerun/`
# `check_p1.yaml` / `check_p1_summary.json`。スクラッチパッドで実行し `runs/` には置いていない): 本物の経路で
# 64 ペア(T1 x T2・`n_item` 80・10 シード = 4,800 行)を 16 並列で回し、壁時計 27.5 分。
# **16 並列の下での実効のコア秒**であり、1 プロセスの逐次の実測(上)とは測り方が違う。見積りは両方を並べる
CHECK_PAIRS = 64
CHECK_WORKERS = 16
CHECK_WALL_SECONDS = 27.5 * 60
CHECK_ROWS = 4_800


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


SCALE_SUBSPACE = "subspace"
SCALE_PER_CELL = "per_cell"
SEED_INTERACTION_SCALES = (SCALE_SUBSPACE, SCALE_PER_CELL)


def seed_interaction_direction(profile: EffectProfile, scale: str) -> np.ndarray:
    """答える問い: シード固有の交互作用 `z[s] = m_s * d` の向き `d`(タスク型 x 被覆)は何か(ADR-124 D4)。

    `d` は、プロファイルが 6 セルの線形予測子に足す量(`delta`)を**二重中心化**した向きである
    (行平均・列平均を除く。= P1 の交互作用そのものの向き。パイロットの数値は使わない)。
    大きさは `sum(d^2)` で決める:

    - `subspace`: `sum(d^2)` = 検定する部分空間の次元(`PRIMARY_INTERACTION_DF` = 2)。**検定する部分空間に入る分散の期待値が
      独立な `z`(今のシート)と同じ `2 tau^2`**になる。形だけが違う((ii)。門はこちらで判定する)
    - `per_cell`: `sum(d^2)` = セル数(6)。セルあたりの平均分散が `tau^2`((i)。記録だけ。部分空間の分散は 3 倍)
    """
    if scale not in SEED_INTERACTION_SCALES:
        raise ConfigError(f"seed_interaction.scale は {SEED_INTERACTION_SCALES} のどれか: {scale!r}")
    delta = profile.delta
    centred = delta - delta.mean(axis=0, keepdims=True) - delta.mean(axis=1, keepdims=True) + delta.mean()
    norm_sq = float((centred**2).sum())
    # 厳密に加法のプロファイルでも丸め誤差の `delta` が残る。非加法性 RMS の許容で止める(誤差を拡大して使わない)
    if profile.nonadditivity_rms <= ADDITIVE_RMS_TOLERANCE:
        raise ConfigError(
            f"プロファイル {profile.name} は非加法性が無く、シード固有の交互作用の向きを作れない"
        )
    target = PRIMARY_INTERACTION_DF if scale == SCALE_SUBSPACE else centred.size
    return centred * math.sqrt(target / norm_sq)


def draw_frame(
    levels: DesignLevels,
    eta_fixed: np.ndarray,
    sigma: float,
    rho: float,
    s2_item: float,
    s2_tmpl: float,
    rng: np.random.Generator,
    tau: float = 0.0,
    seed_direction: np.ndarray | None = None,
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

    **★シード固有の交互作用(ADR-124 D4)**: `seed_direction`(`seed_interaction_direction` の向き)を渡すと、
    独立な `z` の代わりに `z[s, task, coverage] = m_s * d[task, coverage]`、`m_s ~ N(0, tau^2)`(シードごとに 1 つ)を足す。
    **`m_s` はテンプレートの後(独立な `z` を引く位置)で引く**ので、`seed_direction` を渡さない経路の乱数列は変わらない。
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
    z_shape = (levels.n_seed, len(levels.tasks), n_cov)
    if seed_direction is not None and seed_direction.shape != z_shape[1:]:
        raise ValueError(
            f"seed_direction の形 {seed_direction.shape} が (タスク型, 被覆) = {z_shape[1:]} と合わない"
        )
    if tau <= 0.0:
        z = np.zeros(z_shape)
    elif seed_direction is not None:
        z = rng.normal(0.0, tau, size=levels.n_seed)[:, None, None] * seed_direction[None, :, :]
    else:
        z = rng.normal(0.0, tau, size=z_shape)

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


@dataclass(frozen=True)
class AllFitSpec:
    """床の `allFit` の段(PLAN-043 I1 / ADR-128 決定1 (A3) / ADR-129 決定1)。答える問い: 何をどの版で回すか。

    `optimizers` は `allFit` の結果の名前で**列挙**する(`nloptwrap.NLOPT_LN_BOBYQA` など)。1 つでも
    使えなければ R が止まる。`expected_*_version` は診断(PLAN-042 D1)で `allFit` を回した版で、違えば止まる。
    `min_aligned` は「警告なしに収束し、最大の logLik から差 < `fit.refit.loglik_tolerance` の最適化」の最小数。
    """

    optimizers: tuple[str, ...]
    start_from_mle: bool
    min_aligned: int
    expected_r_version: str
    expected_lme4_version: str


def load_allfit_spec(config: Mapping[str, Any]) -> AllFitSpec:
    """config の `fit.allfit` を読む。答える問い: 床の `allFit` の段の値は宣言されているか。

    **値はコードに直書きしない**(skill `code-style` §1)。null・欠け・型違いは止まる
    (`start_from_mle` の既定を作らない。ADR-129 決定1 / PLAN-043 罠3)。
    """
    optimizers = require(config, "fit.allfit.optimizers")
    if (
        not isinstance(optimizers, list)
        or not optimizers
        or any(not isinstance(n, str) or not n or "," in n or n != n.strip() for n in optimizers)
        or len(set(optimizers)) != len(optimizers)
    ):
        raise ConfigError(
            f"fit.allfit.optimizers は重複のない名前(文字列)の空でないリスト: {optimizers!r}"
        )
    start_from_mle = require(config, "fit.allfit.start_from_mle")
    if not isinstance(start_from_mle, bool):
        raise ConfigError(f"fit.allfit.start_from_mle は true / false: {start_from_mle!r}")
    min_aligned = require(config, "fit.allfit.min_aligned")
    if not isinstance(min_aligned, int) or isinstance(min_aligned, bool) or not (
        2 <= min_aligned <= len(optimizers)
    ):
        raise ConfigError(
            f"fit.allfit.min_aligned は 2 以上 {len(optimizers)} 以下の整数: {min_aligned!r}"
        )
    versions = []
    for key in ("expected_r_version", "expected_lme4_version"):
        version = require(config, f"fit.allfit.{key}")
        if not isinstance(version, str) or not version:
            raise ConfigError(f"fit.allfit.{key} は版の文字列: {version!r}")
        versions.append(version)
    return AllFitSpec(
        optimizers=tuple(optimizers),
        start_from_mle=start_from_mle,
        min_aligned=min_aligned,
        expected_r_version=versions[0],
        expected_lme4_version=versions[1],
    )


def write_fit_manifest(
    path: Path,
    jobs: Sequence[tuple[Path, Path]],
    refit: Mapping[str, Any],
    max_reduction_level: int,
    allfit: AllFitSpec,
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
        f"allfit_optimizers={','.join(allfit.optimizers)}",
        f"allfit_start_from_mle={'true' if allfit.start_from_mle else 'false'}",
        f"allfit_min_aligned={allfit.min_aligned}",
        f"expected_r_version={allfit.expected_r_version}",
        f"expected_lme4_version={allfit.expected_lme4_version}",
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

    **★結果は `n_workers` に依らない。**表は親が「シート × 点 × 反復」ごとの `SeedSequence` で書き
    (`replication_rng`。2026-10-04 ADR-122 決定4。それまでは単一の `rng` を決まった順で進めていた)、
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
    allfit: AllFitSpec,
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
        write_fit_manifest(manifest, shard, refit, max_reduction_level, allfit)
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


def tost_power(min_margins: Sequence[float], delta: float, *,
               n_failed: int = 0, failed_as_equivalent: bool = False) -> float:
    """答える問い: 境界を ±`delta` に置いたとき、同等と言えた反復の割合はいくつか。

    **`delta` は呼び出し側が渡す**(この層は値を決めない。ADR-114 決定5)。
    **当てはめ失敗(`n_failed`)は分母に入れ、不利な側に数える**(ADR-125): 検出力のシートでは
    「同等と言えた」(`failed_as_equivalent` が真)、過誤のシートでは「同等と言えない」。
    """
    n = len(min_margins) + n_failed
    if n == 0:
        raise PowerSimError("最小 Δ が 0 件である")
    n_equivalent = sum(1 for m in min_margins if m <= delta)
    return (n_equivalent + (n_failed if failed_as_equivalent else 0)) / n


@dataclass(frozen=True)
class PointKey:
    """格子点 1 つ。答える問い: どの `(n_item, sigma, rho)` の DGP か(★すべて仮定値)。

    `n_item` は**検出力分析の中だけの格子**であり、実際の `eval.cells` とは別物である(PLAN-040 §7 罠2)。
    """

    n_item: int
    sigma: float
    rho: float

    def tag(self) -> str:
        """ファイル名に使う札。答える問い: この点の表と当てはめはどの名前か。"""
        return f"n{self.n_item}_s{self.sigma:g}_r{self.rho:g}".replace(".", "p")


@dataclass(frozen=True)
class GridPoint:
    """1 つの格子点の結果。★`n_item` / `sigma` / `rho` は仮定値である。

    `power` は **棄却率**である(P1 のシートでは検出力、P0・誤指定のシートでは第一種の過誤の率)。
    `n_reject` はその分子(誤指定の門の Clopper–Pearson 区間に使う。割合から逆算しない)。
    **★ADR-128 決定1 (A2): 当てはめ失敗(`fit_failed`)は、どのシートでも分母に入れて非棄却に数える**
    (~~過誤のシート = 棄却 / 検出力のシート = 非棄却。ADR-124 D2'~~ → 過誤のシートで棄却に数えるのをやめた)。
    `failed_rate` はその割合。**成功した反復だけの棄却数 `n_reject_success`(分母 `n_success`)を別に持つ**
    (並べるだけ。「本当の過誤」と読まない。PLAN-043 罠2)。失敗した反復の記述の p 値
    (`p_value_failed_descriptive`。ADR-129 決定3)は `n_failed_descriptive` 件のうち
    `n_failed_descriptive_reject` 件が `alpha` 未満 —— **どの門にも使わない**。
    `n_rescued` は床で失敗したが `allFit` の段で収束と言えた反復(ADR-128 決定1 (A3))、
    `n_floor_base_errored` は床の土台の当てはめが例外で、救えなかった反復(ADR-129 決定2)。
    `mean_chisq` と `tost_min_margins` は当てはめが成功した反復だけで作る
    (失敗は p 値も交互作用の係数も持たない)。全部失敗なら `mean_chisq` は null。
    `tost_min_margins` は反復ごとの「同等と言える最小の Δ」(昇順。TOST を見ないときは空)。
    **TOST の読みでは失敗も数える**(ADR-125 → ADR-128 決定4): `tost_n_failed` 件を、どのシートでも
    Δ = +∞(同等と言えない)として `tost_power` と `margin_quantiles` に渡す
    (`tost_failed_as_equivalent` は常に偽。記録のため欄は残す)。無限大は JSON に書かないので、件数と向きで持つ。
    """

    n_item: int
    sigma: float
    rho: float
    n_rep: int
    n_reject: int
    power: float
    reduced_rate: float
    singular_rate: float
    refit_rate: float
    mean_chisq: float | None
    # 当てはめが例外で落ち、縮退へ進んだ反復の割合(`power_sim_fit.R` の `errored_result`。ADR-124 例外の規則)
    errored_rate: float
    # 床でも(allFit の段の後でも)収束しない / 床でも例外で、p 値を出せなかった反復の割合(ADR-124 D2'・ADR-128)
    failed_rate: float = 0.0
    tost_min_margins: tuple[float, ...] = ()
    # TOST の読みに入れる当てはめ失敗の件数と向き(ADR-125・ADR-128 決定4。TOST を見ないときは 0)
    tost_n_failed: int = 0
    tost_failed_as_equivalent: bool = False
    # ★PLAN-043 I2: 成功した反復だけの棄却(並べるだけ)・allFit で救った件数・床の土台の例外の件数・
    # 失敗した反復の記述の p 値(ADR-129 決定3。どの門にも使わない)
    n_success: int = 0
    n_reject_success: int = 0
    n_rescued: int = 0
    n_floor_base_errored: int = 0
    n_failed_descriptive: int = 0
    n_failed_descriptive_reject: int = 0

    @property
    def key(self) -> PointKey:
        return PointKey(self.n_item, self.sigma, self.rho)


def summarise_point(key: PointKey, results: Sequence[Mapping[str, Any]],
                    alpha: float, tost: TostSpec | None = None) -> GridPoint:
    """1 つの格子点をまとめる。答える問い: この仮定値の下で棄却率はいくつか。

    **縮退の発火率も返す** —— ADR-064 決定4 の★リスク欄
    「10 シードで `(0 + coverage | seed)` が同定できるかは誰にも数値では言えない」に
    合成データの上で数値を与えるのが、ADR-068 決定1 を採る利の 1 つだからである。

    **★ADR-128 決定1 (A2): 当てはめ失敗(`fit_failed`。床の `allFit` の段の後でも収束しない / 床の土台が例外)は、
    どのシートでも分母に入れて非棄却に数える**(~~過誤のシートでは棄却。ADR-124 D2'~~)。
    **分母から除かない**(除くと「うまく当たった表の中の率」になる。PLAN-041 §3.3 罠2)。
    だから `n_reject` は成功した反復の棄却数と一致し、成功だけの率は `n_reject_success / n_success` で別に読む。
    失敗の隠れ(失敗が過誤と結びつくのに過誤の門に見えない)は、実行可能性の門と
    失敗した反復の記述の p 値(`p_value_failed_descriptive`)が見る(PLAN-043 罠5)。
    `fit_failed` でないのに p 値が null の反復は、黙って数えず止まる(`CLAUDE.md` §7)。
    旧い出力(run2。新しい欄を持たない)も読める。
    """
    if not results:
        raise PowerSimError(f"{key} の結果が 0 件である")
    failed = [bool(r.get("fit_failed", False)) for r in results]
    bad = [r for r, f in zip(results, failed) if r["p_value"] is None and not f]
    if bad:
        reasons = sorted({r.get("first_error", "") for r in bad} - {""})
        raise PowerSimError(
            f"{key} に p 値が null の反復がある(fit_failed でもない)。"
            "当てはめが LRT を返していない。捨てずに原因を見ること"
            + (f"(当てはめの例外: {reasons})" if reasons else "")
        )
    n = len(results)
    done = [r for r, f in zip(results, failed) if not f]
    failures = [r for r, f in zip(results, failed) if f]
    n_failed = len(failures)
    n_reject = sum(1 for r in done if r["p_value"] < alpha)
    described = [
        r["p_value_failed_descriptive"]
        for r in failures
        if r.get("p_value_failed_descriptive") is not None
    ]
    margins = (
        tuple(sorted(equivalence_margin(r, tost) for r in done))
        if tost is not None
        else ()
    )
    return GridPoint(
        n_item=key.n_item,
        sigma=key.sigma,
        rho=key.rho,
        n_rep=n,
        n_reject=n_reject,
        power=n_reject / n,
        reduced_rate=sum(1 for r in results if r["reduced"]) / n,
        singular_rate=sum(
            1 for r in results if r["full_singular"] or r["add_singular"]
        ) / n,
        refit_rate=sum(
            1 for r in results if r["full_refit_done"] or r["add_refit_done"]
        ) / n,
        mean_chisq=float(np.mean([r["chisq"] for r in done])) if done else None,
        errored_rate=sum(1 for r in results if r["n_errored_fits"] > 0) / n,
        failed_rate=n_failed / n,
        tost_min_margins=margins,
        tost_n_failed=n_failed if tost is not None else 0,
        tost_failed_as_equivalent=False,
        n_success=len(done),
        n_reject_success=n_reject,
        n_rescued=sum(1 for r in results if r.get("rescued_by_allfit", False)),
        n_floor_base_errored=sum(1 for r in results if r.get("floor_base_errored", False)),
        n_failed_descriptive=len(described),
        n_failed_descriptive_reject=sum(1 for p in described if p < alpha),
    )


# 軸の上の答えが「掃いた範囲」のどこにあるか(F6-1)。**軸の値そのものの上での位置**で言う。
VERDICT_BELOW = "below_swept_range"     # 答えは掃いた最小の点より下(か、その点)
VERDICT_INSIDE = "inside_swept_range"
VERDICT_BEYOND = "beyond_swept_range"   # 答えは掃いた最大の点より上(か、その点)


def scan_until_failure(
    ordered: Sequence[tuple[float, float]], target_power: float
) -> tuple[float | None, float | None, bool]:
    """答える問い: 検出力が下がる向きに並べた点で、最初に割るまでに保っていた最後の点はどれか。

    `ordered` は `(軸の値, 検出力)` を**検出力が下がる向き**に並べたもの。返すのは
    `(最後に保った値, 最初に割った値, 割った先でまた保つ点があるか)`。

    ★「最初に割った点」で切る。後ろから拾わない —— 曲線はモンテカルロ誤差で単調でなくなりうるので、
    後ろから拾うと「一度割ったのに、その先で保っている」点を答えとして報告してしまう。
    **点の間は補間しない**(掃いていない領域を語らないため。§6.3 手続き5)。
    """
    last_holding: float | None = None
    first_failing: float | None = None
    for index, (value, power) in enumerate(ordered):
        if power < target_power:
            first_failing = value
            rest = ordered[index + 1:]
            return last_holding, first_failing, any(p >= target_power for _, p in rest)
        last_holding = value
    return last_holding, first_failing, False


def sigma_limit(points: Sequence[GridPoint], target_power: float) -> dict[str, Any]:
    """`sigma*` を出す(§6.3 手続き5。★PLAN-040 D2 (a) で**従**の報告量になった)。

    答える問い: 「**10 シードが検出力 `target_power` を保つ `sigma` の上限はどこか**」

    `sigma` が上がるほど検出力は下がる向きなので、昇順に走査する。
    全域で保てば `beyond_swept_range`(「限界は無い」とは書かない)、**最初の点で割れば
    `below_swept_range`**(F6-1。旧実装はここで `inside_swept_range`・`sigma_star: null` を返していた)。
    """
    ordered = sorted(((p.sigma, p.power) for p in points), key=lambda vp: vp[0])
    last_holding, first_failing, non_monotone = scan_until_failure(ordered, target_power)
    if first_failing is None:
        verdict = VERDICT_BEYOND
    elif last_holding is None:
        verdict = VERDICT_BELOW
    else:
        verdict = VERDICT_INSIDE
    return {
        "sigma_star": last_holding if first_failing is not None else None,
        "verdict": verdict,
        "last_holding_sigma": last_holding,
        "first_failing_sigma": first_failing,
        "non_monotone": non_monotone,
    }


def n_item_range(points: Sequence[GridPoint], target_power: float) -> dict[str, Any]:
    """**主の報告量**(PLAN-040 D2 (a) / ADR-122 決定2)。

    答える問い: 「仮定値(`s2_item`・`s2_tmpl`・P1)のもとで、**検出力 `target_power` に届く `n_item` の範囲**はどこか」

    `n_item` が下がるほど検出力は下がる向きなので、**降順に**走査し、最初に割った点で切る
    (`sigma_limit` と同じ考え方。格子点だけ・補間しない)。答えは「(`largest_failing_n_item`,
    `reaching_from_n_item`] の間で届き始める」である。
    全点で届けば `below_swept_range`(届き始めるのは掃いた最小の点以下)、最大の点でも届かなければ
    `beyond_swept_range`(掃いた最大の点より上が要る)。
    """
    ordered = sorted(((float(p.n_item), p.power) for p in points), key=lambda vp: -vp[0])
    last_holding, first_failing, non_monotone = scan_until_failure(ordered, target_power)
    if first_failing is None:
        verdict = VERDICT_BELOW
    elif last_holding is None:
        verdict = VERDICT_BEYOND
    else:
        verdict = VERDICT_INSIDE
    return {
        "verdict": verdict,
        "reaching_from_n_item": None if last_holding is None else int(last_holding),
        "largest_failing_n_item": None if first_failing is None else int(first_failing),
        "non_monotone": non_monotone,
    }


@dataclass(frozen=True)
class AxisSpec:
    """報告の軸(ADR-123 決定2)。答える問い: どの点の並びを「`n_item` の軸」「`sigma` の確認点」と読むか。"""

    n_item_axis_sigma: float
    n_item_axis_rho: float
    sigma_axis_n_item: int
    sigma_axis_rho: float
    margin_quantiles: tuple[float, ...]


def load_axis_spec(config: Mapping[str, Any]) -> AxisSpec:
    """config の `report:` を読む。答える問い: 報告の軸と分位点は宣言されているか(null は止まる)。"""
    quantiles = tuple(float(q) for q in require(config, "report.margin_quantiles"))
    if not quantiles or any(not 0.0 <= q <= 1.0 for q in quantiles):
        raise ConfigError(f"report.margin_quantiles は [0, 1] の値の空でない列: {list(quantiles)}")
    return AxisSpec(
        n_item_axis_sigma=float(require(config, "report.n_item_axis.sigma")),
        n_item_axis_rho=float(require(config, "report.n_item_axis.rho")),
        sigma_axis_n_item=int(require(config, "report.sigma_axis.n_item")),
        sigma_axis_rho=float(require(config, "report.sigma_axis.rho")),
        margin_quantiles=quantiles,
    )


def on_n_item_axis(points: Sequence[GridPoint], axes: AxisSpec) -> list[GridPoint]:
    """答える問い: 主の軸(`sigma`・`rho` を固定して `n_item` を動かす)に乗る点はどれか。"""
    return [
        p for p in points
        if p.sigma == axes.n_item_axis_sigma and p.rho == axes.n_item_axis_rho
    ]


def on_sigma_axis(points: Sequence[GridPoint], axes: AxisSpec) -> list[GridPoint]:
    """答える問い: `sigma` の確認点(`n_item`・`rho` を固定して `sigma` を動かす)に乗る点はどれか。"""
    return [
        p for p in points
        if p.n_item == axes.sigma_axis_n_item and p.rho == axes.sigma_axis_rho
    ]


def inverse_problem(points: Sequence[GridPoint], axes: AxisSpec, target_power: float) -> dict[str, Any]:
    """検出力のシートの答え。答える問い: 主(`n_item` の範囲)と従(`sigma*`)はそれぞれ何か。"""
    n_axis = on_n_item_axis(points, axes)
    s_axis = on_sigma_axis(points, axes)
    if not n_axis or not s_axis:
        raise PowerSimError(
            "検出力のシートに報告の軸の点が無い(report.n_item_axis / report.sigma_axis と"
            " sheets[].points が食い違っている)"
        )
    return {
        "target_power": target_power,
        "n_item_range": {
            "axis": {"sigma": axes.n_item_axis_sigma, "rho": axes.n_item_axis_rho},
            **n_item_range(n_axis, target_power),
        },
        "sigma_limit": {
            "axis": {"n_item": axes.sigma_axis_n_item, "rho": axes.sigma_axis_rho},
            **sigma_limit(s_axis, target_power),
        },
    }


# 分位点の取り方。numpy の既定(R の type 7 と同じ線形)を使い、名前を出力に残す
QUANTILE_METHOD = "linear"


def margin_quantiles(margins: Sequence[float], quantiles: Sequence[float], *,
                     n_failed: int = 0,
                     failed_as_equivalent: bool = False) -> dict[str, float | None]:
    """答える問い: 反復ごとの「同等と言える最小の Δ」の分布は、宣言した分位点でいくつか。

    **当てはめ失敗も分布に入れる**(ADR-125): 検出力のシートでは Δ = 0、過誤のシートでは Δ = +∞。
    **+∞ に掛かった分位点(線形補間の上端が失敗)は null**(JSON に無限大を書かない)。
    それ以外の分位点は補間の両端が有限なので、`QUANTILE_METHOD` の値そのものである。
    """
    fill = 0.0 if failed_as_equivalent else math.inf
    values = np.sort(np.asarray([*map(float, margins), *([fill] * n_failed)], dtype=float))
    if values.size == 0:
        raise PowerSimError("最小 Δ が 0 件である")
    finite = values[np.isfinite(values)]
    # 失敗(+∞)を有限の最大値で置いても、上端が有限の分位点の補間は変わらない(下で null にする分だけが変わる)
    capped = np.where(np.isfinite(values), values, finite.max() if finite.size else 0.0)
    result = np.quantile(capped, list(quantiles), method=QUANTILE_METHOD)
    out: dict[str, float | None] = {}
    for q, v in zip(quantiles, result):
        upper = values[math.ceil((values.size - 1) * q)]
        out[f"{q:g}"] = None if math.isinf(upper) else float(v)
    return out


def margin_quantile_table(
    sheet_points: Mapping[str, Sequence[GridPoint]],
    sheet_roles: Mapping[str, str],
    axes: AxisSpec,
) -> dict[str, Any]:
    """D5 (a) の表(ADR-122 決定5)。答える問い: **この設計で平行と非平行を区別できるか**を読む材料は何か。

    主の軸の各 `n_item` で、P0(null_calibration)と P1(power)の「同等と言える最小の Δ」の分位点を並べる。
    **Δ は決めない**(ADR-114 決定5)。分位点は人間が選んだもの(`report.margin_quantiles`。2026-10-04 その143)。
    全件はシートの `grid[].tost_min_margins` にある。
    """
    rows: dict[str, Any] = {}
    for sheet_id, points in sheet_points.items():
        if sheet_roles[sheet_id] not in (ROLE_POWER, ROLE_NULL_CALIBRATION):
            continue
        for point in sorted(on_n_item_axis(points, axes), key=lambda p: p.n_item):
            rows.setdefault(str(point.n_item), {})[sheet_id] = {
                "n_rep": point.n_rep,
                "n_failed": point.tost_n_failed,
                "quantiles": margin_quantiles(
                    point.tost_min_margins, axes.margin_quantiles,
                    n_failed=point.tost_n_failed,
                    failed_as_equivalent=point.tost_failed_as_equivalent,
                ),
            }
    return {
        "axis": {"sigma": axes.n_item_axis_sigma, "rho": axes.n_item_axis_rho},
        "quantile_method": QUANTILE_METHOD,
        "by_n_item": rows,
    }


def compare_power(
    reference: Sequence[GridPoint], other: Sequence[GridPoint]
) -> list[dict[str, Any]]:
    """答える問い: 同じ `(n_item, sigma, rho)` で、2 つのシートの棄却率はどれだけ違うか。

    形の検査(ADR-114 決定2 = D2 (a))に使う: **LRT(df = 2)は非加法性の「形」を区別しない**ので、
    P1 と P1⁻ の差はモンテカルロ誤差の範囲に収まるはずである。**大きくずれたらバグを疑う**
    (`CLAUDE.md` §7)。基準のシートに無い点は返さない(掃いていない点を補わない)。
    **比較の鍵に `n_item` を入れる**(ADR-123 決定3)。
    """
    by_key = {p.key: p for p in reference}
    return [
        {
            "n_item": p.n_item,
            "sigma": p.sigma,
            "rho": p.rho,
            "reference_power": by_key[p.key].power,
            "power": p.power,
            "difference": p.power - by_key[p.key].power,
            "reference_mean_chisq": by_key[p.key].mean_chisq,
            "mean_chisq": p.mean_chisq,
        }
        for p in other
        if p.key in by_key
    ]


# --------------------------------------------------------------------------
# ★誤指定の門(ADR-122 決定3 / ADR-123 決定6)と実行可能性の門(ADR-128 決定3)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GateSpec:
    """誤指定の門(過誤の門)。答える問い: どのシートのどの `tau` で、どの区間の下端がいくつを超えたら止まるか。

    ★ADR-124 D4: 門は複数のシート(今の独立な `z` と、シード固有の交互作用の (ii))に掛ける。
    誤指定のシートのうち `points` に無いもの((i))は記録だけで、判定に使わない。
    ★ADR-128 決定1・ADR-129: 判定点は**シートごと**(`points`)。基本の誤指定の `tau` 0.25・0.5・1.0 と
    seed_subspace の 0.25・0.5。~~全シート共通の `sheets` × `tau` の直積(ADR-124 D4)~~
    """

    points: tuple[tuple[str, tuple[float, ...]], ...]    # (シート id, 判定点の tau)
    ci_level: float
    lower_bound_above: float

    @property
    def sheet_ids(self) -> tuple[str, ...]:
        return tuple(sheet_id for sheet_id, _ in self.points)


def load_gate_spec(config: Mapping[str, Any]) -> GateSpec:
    """config の `simulation.misspecification_gate` を読む。答える問い: 門の値は宣言されているか。

    **閾値はコードに直書きしない**(skill `code-style` §1)。null は止まる。
    旧い `sheet`(1 枚)・`sheets` + `tau`(直積)が残っていても止まる(どちらが効いているか読めなくなるため)。
    """
    declared = config.get("simulation", {}).get("misspecification_gate", {})
    for old_key, reason in (
        ("sheet", "ADR-124 D4 で .sheets に置き換えた"),
        ("sheets", "ADR-128 / PLAN-043 I4 で .points(シートごとの判定点)に置き換えた"),
        ("tau", "ADR-128 / PLAN-043 I4 で .points(シートごとの判定点)に置き換えた"),
    ):
        if old_key in declared:
            raise ConfigError(f"simulation.misspecification_gate.{old_key} は {reason}")
    level = float(require(config, "simulation.misspecification_gate.ci_level"))
    if not 0.0 < level < 1.0:
        raise ConfigError(f"simulation.misspecification_gate.ci_level は (0, 1): {level}")
    declared_points = require(config, "simulation.misspecification_gate.points")
    if not isinstance(declared_points, Mapping) or not declared_points:
        raise ConfigError(
            "simulation.misspecification_gate.points は {シート id: [tau, ...]} の空でない写像: "
            f"{declared_points!r}"
        )
    points: list[tuple[str, tuple[float, ...]]] = []
    for sheet_id, taus in declared_points.items():
        if (
            not isinstance(taus, list)
            or not taus
            or any(isinstance(t, bool) or not isinstance(t, (int, float)) for t in taus)
            or len(set(taus)) != len(taus)
        ):
            raise ConfigError(
                f"simulation.misspecification_gate.points.{sheet_id} は重複のない数のリスト: {taus!r}"
            )
        points.append((str(sheet_id), tuple(float(t) for t in taus)))
    return GateSpec(
        points=tuple(points),
        ci_level=level,
        lower_bound_above=float(
            require(config, "simulation.misspecification_gate.lower_bound_above")
        ),
    )


def clopper_pearson_lower(n_reject: int, n: int, level: float) -> float:
    """答える問い: 棄却 `n_reject` / `n` の、両側 `level` の Clopper–Pearson 区間の下端はいくつか。

    下端 = Beta(`(1 - level) / 2`; `n_reject`, `n - n_reject + 1`)。`n_reject` = 0 なら 0。
    """
    if n < 1 or not 0 <= n_reject <= n:
        raise ValueError(f"棄却数と反復数が合わない: {n_reject} / {n}")
    if n_reject == 0:
        return 0.0
    return float(beta_distribution.ppf((1.0 - level) / 2.0, n_reject, n - n_reject + 1))


def clopper_pearson_interval(n_reject: int, n: int, level: float) -> list[float]:
    """答える問い: 棄却 `n_reject` / `n` の、両側 `level` の Clopper–Pearson 区間 [下端, 上端] は。"""
    lower = clopper_pearson_lower(n_reject, n, level)
    upper = (
        1.0
        if n_reject == n
        else float(beta_distribution.ppf(1.0 - (1.0 - level) / 2.0, n_reject + 1, n - n_reject))
    )
    return [lower, upper]


def _rate_with_interval(count: int, n: int, level: float) -> dict[str, Any]:
    """答える問い: `count` / `n` の率と両側 `level` の区間は(`n` = 0 なら率も区間も null)。"""
    if n == 0:
        return {"count": count, "n": 0, "rate": None, "ci": None, "ci_level": level}
    return {
        "count": count,
        "n": n,
        "rate": count / n,
        "ci": clopper_pearson_interval(count, n, level),
        "ci_level": level,
    }


def point_intervals(point: GridPoint, rejection_level: float, failure_level: float) -> dict[str, Any]:
    """答える問い: この点の棄却率・成功だけの棄却率・失敗率・失敗した反復だけの棄却率は、区間つきでいくつか。

    ★PLAN-043 I2 / ADR-129 決定3。**並べるだけ**で、どの門にも使わない(成功だけ・失敗だけの率を
    「本当の過誤」と読まない。選択の偏りがある。PLAN-043 罠2)。`rejection` は失敗を非棄却に数えた
    無条件の率で、誤指定の門が見る量である。
    """
    return {
        "rejection": _rate_with_interval(point.n_reject, point.n_rep, rejection_level),
        "rejection_success_only": _rate_with_interval(
            point.n_reject_success, point.n_success, rejection_level
        ),
        "failed": _rate_with_interval(
            round(point.failed_rate * point.n_rep), point.n_rep, failure_level
        ),
        "rejection_failed_descriptive_only": _rate_with_interval(
            point.n_failed_descriptive_reject, point.n_failed_descriptive, rejection_level
        ),
    }


def _gate_rows(
    points: Sequence[GridPoint], taus: Sequence[float], gate: GateSpec, sheet_id: str
) -> list[dict[str, Any]]:
    """答える問い: このシートの判定点(`taus`)の棄却率と区間の下端はいくつか。"""
    rows = []
    for tau in taus:
        matching = [p for p in points if p.sigma == tau]
        if len(matching) != 1:
            raise PowerSimError(
                f"誤指定の門のシート {sheet_id} の tau = {tau} の点が {len(matching)} 個ある(1 個のはず)"
            )
        point = matching[0]
        lower = clopper_pearson_lower(point.n_reject, point.n_rep, gate.ci_level)
        rows.append({
            "tau": tau,
            "n_item": point.n_item,
            "n_rep": point.n_rep,
            "n_reject": point.n_reject,
            "rejection_rate": point.power,
            "failed_rate": point.failed_rate,
            "n_success": point.n_success,
            "n_reject_success": point.n_reject_success,
            "ci_level": gate.ci_level,
            "ci_lower": lower,
            "exceeds": lower > gate.lower_bound_above,
        })
    return rows


def misspecification_gate(
    points_by_sheet: Mapping[str, Sequence[GridPoint]], gate: GateSpec
) -> dict[str, Any]:
    """誤指定のシートを回し終えた時点の判定(ADR-123 決定6 / ADR-124 D4 / ADR-128 決定1 (B1))。

    答える問い: 「§3.2 の当てはめの第一種の過誤は、**門のシートのどれか**の判定点の
    **どれか 1 つでも**区間の下端が閾値を超えるほど膨らむか」。膨らめば、その段の P1・P1⁻・P0 の前で止まる。
    `points_by_sheet` は誤指定のシートすべて。**`gate.points` に挙げたシートだけが判定に効き**
    (そのシートの挙げた `tau` だけ)、残り((i) など)は `recorded_only` にそのシートの全点を同じ形で記録する。
    **挙げていない `tau` は判定に使わない**(記録はシートの `grid` にある)。
    率は**当てはめ失敗を非棄却に数えた無条件の率**である(`summarise_point`。ADR-128 決定1 (A2))。
    成功した反復だけの数も行に並べる(判定には使わない)。
    """
    missing = [i for i in gate.sheet_ids if i not in points_by_sheet]
    if missing:
        raise PowerSimError(f"誤指定の門のシート {missing} の結果が無い")
    judged = {
        sheet_id: _gate_rows(points_by_sheet[sheet_id], taus, gate, sheet_id)
        for sheet_id, taus in gate.points
    }
    recorded = {
        sheet_id: _gate_rows(points, sorted({p.sigma for p in points}), gate, sheet_id)
        for sheet_id, points in points_by_sheet.items()
        if sheet_id not in gate.sheet_ids
    }
    return {
        "sheets": judged,
        "recorded_only": recorded,
        "lower_bound_above": gate.lower_bound_above,
        "inflated": any(row["exceeds"] for rows in judged.values() for row in rows),
    }


# 実行可能性の門が見る点の範囲。いまは「回したすべてのシートのすべての点」だけ(ADR-129 決定4)
FEASIBILITY_SCOPE_ALL = "all_sheets_all_points"


@dataclass(frozen=True)
class FeasibilityGateSpec:
    """実行可能性の門。答える問い: 当てはめ失敗の率が、どの区間の下端がいくつを超えたら手順が回らないとみなして止めるか。

    ★ADR-128 決定3 / ADR-129 決定4: 各段で回した**すべての点**で、当てはめ失敗の率の両側 `ci_level` の
    Clopper–Pearson 区間の下端が `lower_bound_above` を超える点が 1 つでもあれば閉じる。過誤の門とは別
    (棄却ではなく失敗を見る。終了コードも別)。
    """

    ci_level: float
    lower_bound_above: float
    scope: str


def load_feasibility_gate_spec(config: Mapping[str, Any]) -> FeasibilityGateSpec:
    """config の `simulation.feasibility_gate` を読む。答える問い: 実行可能性の門の値は宣言されているか。

    閾値はコードに直書きしない。null・欠けは止まる。`scope` はいまは `all_sheets_all_points` だけ。
    """
    level = float(require(config, "simulation.feasibility_gate.ci_level"))
    if not 0.0 < level < 1.0:
        raise ConfigError(f"simulation.feasibility_gate.ci_level は (0, 1): {level}")
    bound = float(require(config, "simulation.feasibility_gate.lower_bound_above"))
    if not 0.0 <= bound < 1.0:
        raise ConfigError(f"simulation.feasibility_gate.lower_bound_above は [0, 1): {bound}")
    scope = require(config, "simulation.feasibility_gate.scope")
    if scope != FEASIBILITY_SCOPE_ALL:
        raise ConfigError(
            f"simulation.feasibility_gate.scope は {FEASIBILITY_SCOPE_ALL!r} だけ(ADR-129 決定4): {scope!r}"
        )
    return FeasibilityGateSpec(ci_level=level, lower_bound_above=bound, scope=scope)


def _feasibility_rows(
    points: Sequence[GridPoint], gate: FeasibilityGateSpec
) -> list[dict[str, Any]]:
    """答える問い: このシートの各点の当てはめ失敗の率と区間の下端はいくつか。"""
    rows = []
    for point in points:
        n_failed = round(point.failed_rate * point.n_rep)
        lower = clopper_pearson_lower(n_failed, point.n_rep, gate.ci_level)
        rows.append({
            "n_item": point.n_item,
            "sigma": point.sigma,
            "rho": point.rho,
            "n_rep": point.n_rep,
            "n_failed": n_failed,
            "failed_rate": point.failed_rate,
            "n_rescued": point.n_rescued,
            "n_floor_base_errored": point.n_floor_base_errored,
            "ci_level": gate.ci_level,
            "ci_lower": lower,
            "exceeds": lower > gate.lower_bound_above,
        })
    return rows


def feasibility_gate(
    points_by_sheet: Mapping[str, Sequence[GridPoint]], gate: FeasibilityGateSpec
) -> dict[str, Any]:
    """答える問い: 渡したシートのどこかの点で、当てはめ失敗の率が実行可能性の門の閾値を超えたか。

    ★ADR-128 決定3 / ADR-129 決定4。**過誤の門とは独立**(失敗を非棄却に数えると、失敗が過誤と結びついていても
    過誤の門には見えない。その見張りがこの門と、失敗した反復の記述の p 値である。PLAN-043 罠5)。
    """
    sheets = {sheet_id: _feasibility_rows(points, gate) for sheet_id, points in points_by_sheet.items()}
    closed_sheets = [
        sheet_id for sheet_id, rows in sheets.items() if any(row["exceeds"] for row in rows)
    ]
    return {
        "scope": gate.scope,
        "ci_level": gate.ci_level,
        "lower_bound_above": gate.lower_bound_above,
        "sheets": sheets,
        "closed_sheets": closed_sheets,
        "closed": bool(closed_sheets),
    }


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
# ★ADR-128 決定1 (A2): 当てはめ失敗は、どのシートでも非棄却に数える(~~過誤のシート = 棄却 / 検出力のシート = 非棄却。
# ADR-124 D2'~~ の `FAILURE_AS_REJECT_ROLES` は空にした = 定数ごと削除)。実行可能性の門が失敗の多さを見る
TAU_ZERO = "zero"
TAU_EQUALS_SIGMA = "equals_sigma"
# 点の 3 つ組の並び(`sheets[].points` の各要素)
POINT_FIELDS = ("n_item", "sigma", "rho")
# 厳密に加法のプロファイルの RMS の許容(丸めを持たない `eta` なので浮動小数点の誤差だけ)
ADDITIVE_RMS_TOLERANCE = 1e-9


@dataclass(frozen=True)
class SeedInteractionSpec:
    """シード固有の交互作用の誤指定(ADR-124 D4)。答える問い: どのプロファイルの向きを、どの大きさで使うか。"""

    direction_profile: str
    scale: str


@dataclass(frozen=True)
class Sheet:
    """シート 1 枚。答える問い: どのプロファイルをどの点で回し、どう読むか。

    ★PLAN-040 D1 (a) / ADR-123 決定2: 点は `(n_item, sigma, rho)` を明示して並べる
    (主の軸と確認点は直積ではないため)。

    `tau` は `zero` / `equals_sigma` か、**正の数値**(ADR-124 D6。`sigma` ≠ `tau` の確認点。検出力のシートだけ)。
    `seed_interaction` を持つのは誤指定のシートだけで、持てば独立な `z` の代わりにシード固有の交互作用を足す。
    """

    sheet_id: str
    role: str
    profile: str
    points: tuple[PointKey, ...]
    tau: str | float
    compare_with: str | None
    seed_interaction: SeedInteractionSpec | None = None


def load_n_item_grid(config: Mapping[str, Any]) -> tuple[int, ...]:
    """答える問い: 検出力分析の `n_item` の格子は何か(ADR-123 決定1。実際の `eval.cells` とは別物)。"""
    declared = require(config, "dgp.n_item")
    if (
        not isinstance(declared, list)
        or not declared
        or any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in declared)
    ):
        raise ConfigError(f"dgp.n_item は正の整数の空でないリスト(格子)である: {declared!r}")
    return tuple(declared)


def _parse_point(
    entry: Any, grids: Mapping[str, Sequence[float]], sheet_id: str
) -> PointKey:
    """答える問い: この点は `[n_item, sigma, rho]` の形で、どれも `dgp` の格子にあるか。

    **掃く格子に無い点は作らない**(`sigma` / `rho` は ADR-068 決定3、`n_item` は ADR-123 決定1)。
    """
    if not isinstance(entry, list) or len(entry) != len(POINT_FIELDS):
        raise ConfigError(
            f"sheets[{sheet_id}].points の各点は {list(POINT_FIELDS)} の 3 つ組: {entry!r}"
        )
    n_item, sigma, rho = entry
    if not isinstance(n_item, int) or isinstance(n_item, bool):
        raise ConfigError(f"sheets[{sheet_id}].points の n_item は整数: {entry!r}")
    key = PointKey(n_item=n_item, sigma=float(sigma), rho=float(rho))
    for field in POINT_FIELDS:
        value = getattr(key, field)
        if value not in {float(g) for g in grids[field]}:
            raise ConfigError(
                f"sheets[{sheet_id}].points の {field} = {value} は dgp.{field} の格子に無い"
                "(ADR-068 決定3 / ADR-123 決定1)"
            )
    return key


def _parse_seed_interaction(
    entry: Mapping[str, Any], role: str, effect: Mapping[str, Any], sheet_id: str
) -> SeedInteractionSpec | None:
    """答える問い: このシートの `seed_interaction` は宣言されているなら整合しているか(ADR-124 D4)。

    誤指定のシートだけが持てる。向きのプロファイルは非加法性を持たなければならない(向きが作れない)。
    """
    raw = entry.get("seed_interaction")
    if raw is None:
        return None
    if role != ROLE_MISSPECIFICATION:
        raise ConfigError(f"sheets[{sheet_id}].seed_interaction は誤指定のシートだけが持てる")
    if not isinstance(raw, Mapping) or set(raw) != {"direction", "scale"}:
        raise ConfigError(
            f"sheets[{sheet_id}].seed_interaction は {{direction, scale}} の 2 キー: {raw!r}"
        )
    spec = SeedInteractionSpec(direction_profile=str(raw["direction"]), scale=str(raw["scale"]))
    # 向きを組んでみて、プロファイルの欠落・非加法性の無さ・scale の綴りを config を読む時点で止める
    seed_interaction_direction(build_profile(effect, spec.direction_profile), spec.scale)
    return spec


def load_sheets(config: Mapping[str, Any]) -> list[Sheet]:
    """config の `sheets:` を読む。答える問い: 宣言したシートは整合しているか。

    **役割とプロファイルの食い違いで止まる**: 非加法性のあるシート(power / shape_check)は
    RMS > 0、加法のシート(null_calibration / misspecification)は RMS = 0 でなければならない。
    P1 と P0 の取り違えは、検出力と第一種の過誤を入れ替えて読む事故になる。
    """
    declared = require(config, "sheets")
    effect = config["effect"]
    grids = {
        "n_item": load_n_item_grid(config),
        "sigma": require(config, "dgp.sigma"),
        "rho": require(config, "dgp.rho"),
    }
    sheets: list[Sheet] = []
    for entry in declared:
        sheet_id = str(entry["id"])
        if any(sheet.sheet_id == sheet_id for sheet in sheets):
            raise ConfigError(f"sheets の id が重複している: {sheet_id}")
        role = entry["role"]
        if role not in ROLES:
            raise ConfigError(f"sheets[{sheet_id}].role は {ROLES} のどれか: {role!r}")
        tau = entry["tau"]
        numeric_tau = isinstance(tau, (int, float)) and not isinstance(tau, bool)
        if numeric_tau:
            tau = float(tau)
            if tau <= 0.0 or role != ROLE_POWER:
                raise ConfigError(
                    f"sheets[{sheet_id}].tau = {tau}: 数値の tau は正で、検出力のシートだけ"
                    "(P1 の確認点。ADR-124 D6)。0 は `zero` と書く"
                )
        elif tau not in (TAU_ZERO, TAU_EQUALS_SIGMA):
            raise ConfigError(
                f"sheets[{sheet_id}].tau は {TAU_ZERO} か {TAU_EQUALS_SIGMA} か正の数値: {tau!r}"
            )
        elif (role == ROLE_MISSPECIFICATION) != (tau == TAU_EQUALS_SIGMA):
            raise ConfigError(
                f"sheets[{sheet_id}]: tau = {tau} と role = {role} が合わない。"
                "tau = equals_sigma は誤指定のシート(ADR-114 決定7)だけである"
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
        seed_interaction = _parse_seed_interaction(entry, role, effect, sheet_id)
        raw_points = entry.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            raise ConfigError(f"sheets[{sheet_id}].points は空でないリストである: {raw_points!r}")
        points = tuple(_parse_point(p, grids, sheet_id) for p in raw_points)
        if len(set(points)) != len(points):
            raise ConfigError(f"sheets[{sheet_id}].points に重複した点がある")
        sheets.append(
            Sheet(
                sheet_id=sheet_id,
                role=role,
                profile=profile.name,
                points=points,
                tau=tau,
                compare_with=compare_with,
                seed_interaction=seed_interaction,
            )
        )
    return sheets


def leading_misspecification_block(sheets: Sequence[Sheet]) -> list[Sheet]:
    """答える問い: 先頭にまとまっている誤指定のシートはどれか(門はこの全部を回した後に判定する)。"""
    block: list[Sheet] = []
    for sheet in sheets:
        if sheet.role != ROLE_MISSPECIFICATION:
            break
        block.append(sheet)
    return block


def check_gate_against_sheets(gate: GateSpec, sheets: Sequence[Sheet]) -> None:
    """答える問い: 門は「先頭にまとめた誤指定のシート」の、実際に回す `tau` を見ているか。

    **D3 (a)(ADR-122 決定3)は誤指定を先頭に回すと決めた**。2 枚目以降に置くと、P1 を回した後で
    門が閉じることになり、止める意味が無い。★ADR-124 D4: 誤指定のシートは複数あってよいが、
    **先頭に連続して並べる**(門は連続した誤指定のシートを全部回した後に判定する。(i) の記録が門の結果によらず残る)。
    """
    block = leading_misspecification_block(sheets)
    if not block:
        raise ConfigError("誤指定の門のため、sheets の先頭は誤指定のシートでなければならない(ADR-122 決定3)")
    stray = [s.sheet_id for s in sheets[len(block):] if s.role == ROLE_MISSPECIFICATION]
    if stray:
        raise ConfigError(
            f"誤指定のシート {stray} が先頭のまとまりの外にある。先頭に連続して置くこと(ADR-124 D4)"
        )
    by_id = {s.sheet_id: s for s in block}
    for sheet_id, taus in gate.points:
        if sheet_id not in by_id:
            raise ConfigError(
                f"誤指定の門のシート {sheet_id} は sheets の先頭の誤指定のシートのどれかでなければならない"
            )
        swept = {p.sigma for p in by_id[sheet_id].points}
        missing = [t for t in taus if t not in swept]
        if missing:
            raise ConfigError(f"誤指定の門の tau {missing} をシート {sheet_id} が回さない")


def plan_grid(config: Mapping[str, Any]) -> list[tuple[str, PointKey]]:
    """全シートの格子点を並べる。答える問い: 何点を、どの順で回すのか(★すべて仮定値)。"""
    return [(sheet.sheet_id, key) for sheet in load_sheets(config) for key in sheet.points]


def load_stages(config: Mapping[str, Any]) -> tuple[int, ...]:
    """答える問い: 反復の段(累積)は何か(ADR-123 決定5)。

    狭義に増える正の整数の列でなければ止まる。旧い `simulation.n_rep` が残っていても止まる
    (どちらが効いているか読めなくなるため)。
    """
    if "n_rep" in config.get("simulation", {}):
        raise ConfigError(
            "simulation.n_rep は simulation.n_rep_stages に置き換えた(ADR-122 決定4 / ADR-123 決定5)"
        )
    stages = require(config, "simulation.n_rep_stages")
    if (
        not isinstance(stages, list)
        or not stages
        or any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in stages)
        or any(b <= a for a, b in zip(stages, stages[1:]))
    ):
        raise ConfigError(f"simulation.n_rep_stages は狭義に増える正の整数の列: {stages!r}")
    return tuple(stages)


# --------------------------------------------------------------------------
# 乱数(ADR-122 決定4)
# --------------------------------------------------------------------------


def _text_to_int(text: str) -> int:
    """答える問い: 文字列を、衝突しない非負の整数にするとどうなるか(`SeedSequence` の鍵に使う)。"""
    return int.from_bytes(text.encode("utf-8"), "big")


def replication_rng(
    rng_seed: int, sheet_id: str, key: PointKey, rep: int
) -> np.random.Generator:
    """反復 1 つの乱数。答える問い: 「シート × 点 × 反復」の表は、他の何にも依らず決まるか。

    **鍵は位置ではなく値である**(シートの id・`n_item`・`sigma`・`rho` の文字列・反復の番号)。
    したがって、段を足しても(`n_rep` を増やしても)、シートや点の順を入れ替えても、
    点を足し引きしても、**既にある反復の表は変わらない**(表は入れ子になる)。
    """
    spawn_key = (
        _text_to_int(sheet_id),
        key.n_item,
        _text_to_int(repr(key.sigma)),
        _text_to_int(repr(key.rho)),
        rep,
    )
    return np.random.default_rng(np.random.SeedSequence(entropy=rng_seed, spawn_key=spawn_key))


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------


def load_levels(config: Mapping[str, Any], n_item: int) -> DesignLevels:
    """config から 1 つの `n_item` の水準を組む。答える問い: 未決の項目は残っていないか。

    `require` が null で止める(`code/config.py`)。**ここで既定値は作らない。**
    `n_item` は格子(`dgp.n_item`)の点でなければ止まる。
    """
    if n_item not in load_n_item_grid(config):
        raise ConfigError(f"n_item = {n_item} は dgp.n_item の格子に無い")
    effect = config["effect"]
    return DesignLevels(
        tasks=tuple(effect["task_levels"]),
        coverages=tuple(effect["coverage_levels"]),
        templates=require(config, "dgp.templates"),
        n_seed=int(require(config, "dgp.n_seed")),
        n_item=n_item,
    )


def frame_tau(sheet: Sheet, sigma: float) -> float:
    """答える問い: この格子点で DGP に足す seed × タスク型 × 被覆の変動の SD はいくつか。

    `equals_sigma` はその点の `sigma`、数値(ADR-124 D6)はその値、`zero` は 0。
    """
    if sheet.tau == TAU_EQUALS_SIGMA:
        return sigma
    if sheet.tau == TAU_ZERO:
        return 0.0
    return float(sheet.tau)


def sheet_summary(
    sheet: Sheet,
    profile: EffectProfile,
    points: Sequence[GridPoint],
    target_power: float,
    axes: AxisSpec,
    rejection_level: float,
    failure_level: float,
) -> dict[str, Any]:
    """シート 1 枚の結果をまとめる。答える問い: このシートは何を言うための数か。

    各点に `intervals`(棄却率・成功だけの棄却率・失敗率・失敗した反復だけの棄却率の Clopper–Pearson 区間。
    PLAN-043 I2)を足す。区間の水準は誤指定の門(棄却)と実行可能性の門(失敗)の `ci_level`。

    **`power` の読み方はシートの役割で違う**: power のシートは検出力(`n_item` の範囲と `sigma*` を出す)、
    null_calibration / misspecification のシートは第一種の過誤の率、shape_check は形の検査。
    """
    summary: dict[str, Any] = {
        "role": sheet.role,
        "profile": profile.name,
        "nonadditivity_rms": profile.nonadditivity_rms,
        # 平行性の TOST が見る係数の真値(logit。処理対比・基準 T1 x id)
        "true_interaction_contrasts": dict(profile.interaction_contrasts),
        "tau": sheet.tau,
        "seed_interaction": (
            None if sheet.seed_interaction is None else dataclasses.asdict(sheet.seed_interaction)
        ),
        # ★ADR-128 決定1 (A2): どのシートでも非棄却(~~過誤のシートでは reject~~)
        "failure_counted_as": "retain",
        "grid": [
            {
                **dataclasses.asdict(point),
                "intervals": point_intervals(point, rejection_level, failure_level),
            }
            for point in points
        ],
    }
    # tau が 0 でない検出力のシート(P1 の確認点。ADR-124 D6)は軸を持たない 1 点なので逆問題を解かない
    if sheet.role == ROLE_POWER and sheet.tau == TAU_ZERO:
        summary["inverse_problem"] = inverse_problem(points, axes, target_power)
    return summary


SUMMARY_FILE = "power_sim_summary.json"
RUN_INFO_FILE = "run_info.json"
INVOCATIONS_FILE = "invocations.jsonl"
CONFIG_COPY_FILE = "config.yaml"
RESOLVED_CONFIG_FILE = "config_resolved.json"
# 誤指定の門が閉じて止まったときの終了コード(0 = 指定した段まで回った)
EXIT_GATE_CLOSED = 3
# 実行可能性の門(当てはめ失敗が多すぎる。ADR-128 決定3)が閉じて止まったときの終了コード。過誤の門(3)と分ける。
# 両方が同じ点で閉じたときは 3(過誤の門)を返す —— どちらが閉じたかは stage_*_summary.json に両方残る
EXIT_FEASIBILITY_CLOSED = 4


def stage_summary_name(n_rep: int) -> str:
    """答える問い: この段の結果はどのファイルか(段は入れ子なので、段ごとに残す)。"""
    return f"stage_{n_rep:04d}_summary.json"


def write_json_atomic(path: Path, payload: Any) -> None:
    """答える問い: 書いている途中で落ちても、壊れた JSON が残らないか(F6-3)。

    同じディレクトリの一時ファイルに書いてから `os.replace` で置き換える(同じボリューム内では原子的)。
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(tmp, path)


def record_run(
    out_dir: Path,
    config: Mapping[str, Any],
    config_path: Path | None,
    through_stage: int,
    n_workers: int,
) -> dict[str, Any]:
    """出力先に来歴を残す(F6-2。`CLAUDE.md` §2「数値は run_id に紐づく」)。

    答える問い: 「この数はどの run の、どの commit の、どの config から出たか」

    初回は run_id・git sha(`git_sha.txt` と差分)・config の写しを書く。**再開のときは run_id を作り直さず**、
    起動ごとの記録(`invocations.jsonl`)だけを足す。**config が初回と違えば止まる**(別の実験の表を混ぜない)。
    """
    resolved = json.loads(json.dumps(config))
    resolved_path = out_dir / RESOLVED_CONFIG_FILE
    info_path = out_dir / RUN_INFO_FILE
    if resolved_path.exists():
        if json.loads(resolved_path.read_text(encoding="utf-8")) != resolved:
            raise PowerSimError(
                f"{out_dir} は別の config で始まった run である。混ぜずに別の --out-dir を使うこと"
            )
        info = json.loads(info_path.read_text(encoding="utf-8"))
    else:
        now = artifacts.utc_now()
        info = {
            "run_id": f"{now.strftime('%Y%m%d_%H%M%S')}_{require(config, 'analysis.id')}",
            "created_utc": now.isoformat(),
            "git_sha": artifacts.capture_git_head_sha(),
            "config_source": None if config_path is None else str(config_path),
        }
        artifacts.write_git_sha(out_dir)
        if config_path is not None:
            artifacts.write_config_copy(out_dir, config_path)
        write_json_atomic(resolved_path, resolved)
        write_json_atomic(info_path, info)
    invocation = {
        "started_utc": artifacts.utc_now().isoformat(),
        "git_sha": artifacts.capture_git_head_sha(),
        "tracked_diff_empty": artifacts.capture_git_diff_head() == "",
        "through_stage": through_stage,
        "n_workers": n_workers,
    }
    with (out_dir / INVOCATIONS_FILE).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(invocation, ensure_ascii=False) + "\n")
    return info


@dataclass(frozen=True)
class RunContext:
    """1 回の起動で変わらない値。答える問い: 表を組み、当てるのに何が要るか。"""

    config: Mapping[str, Any]
    out_dir: Path
    s2_item: float
    s2_tmpl: float
    alpha: float
    target_power: float
    rng_seed: int
    rscript: str
    libpath: str | None
    refit: Mapping[str, Any]
    max_level: int
    allfit: AllFitSpec
    n_workers: int
    keep_frames: bool


def run_sheet_stage(
    ctx: RunContext, sheet: Sheet, profile: EffectProfile, tost: TostSpec, n_rep: int
) -> list[GridPoint]:
    """1 枚のシートを反復 `n_rep` まで回す。答える問い: この段の各点の棄却率はいくつか。

    **当てはめ済みの反復は表を組まない**(反復の表は `replication_rng` だけで決まり、他の反復に
    依らないので、飛ばしても残りの表は変わらない)。R に渡すのは未済の反復だけである
    (済んだ反復を混ぜると、連続ブロックの切り分けで負荷が偏る)。
    """
    sheet_dir = ctx.out_dir / sheet.sheet_id
    frames_dir = sheet_dir / "frames"
    fits_dir = sheet_dir / "fits"
    frames_dir.mkdir(parents=True, exist_ok=True)
    fits_dir.mkdir(exist_ok=True)

    seed_direction = (
        None
        if sheet.seed_interaction is None
        else seed_interaction_direction(
            build_profile(ctx.config["effect"], sheet.seed_interaction.direction_profile),
            sheet.seed_interaction.scale,
        )
    )
    points: list[GridPoint] = []
    for key in sheet.points:
        levels = load_levels(ctx.config, key.n_item)
        tag = key.tag()
        outputs: list[Path] = []
        pending: list[tuple[Path, Path]] = []
        for rep in range(n_rep):
            out_path = fits_dir / f"fit_{tag}_{rep:04d}.json"
            outputs.append(out_path)
            if out_path.exists():
                continue
            csv_path = frames_dir / f"frame_{tag}_{rep:04d}.csv"
            rows = draw_frame(
                levels, profile.eta, key.sigma, key.rho, ctx.s2_item, ctx.s2_tmpl,
                replication_rng(ctx.rng_seed, sheet.sheet_id, key, rep),
                tau=frame_tau(sheet, key.sigma),
                seed_direction=seed_direction,
            )
            write_frame_csv(rows, csv_path)
            pending.append((csv_path, out_path))

        if pending:
            run_fits(
                ctx.rscript, ctx.libpath, sheet_dir / f"manifest_{tag}", pending,
                ctx.refit, ctx.max_level, ctx.allfit, ctx.n_workers,
            )
        results = [json.loads(out.read_text(encoding="ascii")) for out in outputs]
        points.append(summarise_point(key, results, ctx.alpha, tost))
        if not ctx.keep_frames:
            for csv_path, _ in pending:
                csv_path.unlink(missing_ok=True)
    return points


def run_stage(
    ctx: RunContext,
    sheets: Sequence[Sheet],
    gate: GateSpec,
    feasibility: FeasibilityGateSpec,
    axes: AxisSpec,
    stage_index: int,
    n_rep: int,
) -> dict[str, Any]:
    """1 段を回す。答える問い: 反復 `n_rep` までで、各シートは何を言うか。門は閉じたか。

    **先頭にまとめた誤指定のシートを全部回し終えた時点で、誤指定の門(過誤の門)を判定し、膨らめば残りのシートを
    回さずに返す**(ADR-123 決定6 / ADR-124 D4)。(i) の記録が門の結果によらず残るよう、誤指定のシートは判定の前に全部回す。
    **実行可能性の門**(ADR-128 決定3 / ADR-129 決定4)は全シート・全点に掛け、誤指定の 3 枚はまとめて回した後に
    過誤の門と一緒に、以降(P1・`p1_tau`・P1⁻・P0)は各シートを回し終えるごとに判定する。閉じたら次のシートの前で止まる。
    """
    block_ids = [sheet.sheet_id for sheet in leading_misspecification_block(sheets)]
    sheet_summaries: dict[str, Any] = {}
    sheet_points: dict[str, list[GridPoint]] = {}
    gate_result: dict[str, Any] | None = None
    feasibility_sheets: dict[str, Any] = {}
    stopped_after: str | None = None
    for sheet in sheets:
        profile = build_profile(ctx.config["effect"], sheet.profile)
        points = run_sheet_stage(ctx, sheet, profile, tost_spec(ctx.config, profile), n_rep)
        sheet_points[sheet.sheet_id] = points
        body = sheet_summary(
            sheet, profile, points, ctx.target_power, axes, gate.ci_level, feasibility.ci_level
        )
        if sheet.compare_with is not None:
            body["compared_with"] = sheet.compare_with
            body["power_minus_reference"] = compare_power(
                sheet_points[sheet.compare_with], points
            )
        sheet_summaries[sheet.sheet_id] = body
        if sheet.sheet_id in block_ids and sheet.sheet_id != block_ids[-1]:
            continue    # 誤指定のシートは全部回してから判定する
        judged_ids = block_ids if sheet.sheet_id in block_ids else [sheet.sheet_id]
        feasibility_now = feasibility_gate({i: sheet_points[i] for i in judged_ids}, feasibility)
        feasibility_sheets.update(feasibility_now["sheets"])
        misspecification_closed = False
        if sheet.sheet_id == block_ids[-1]:
            gate_result = misspecification_gate({i: sheet_points[i] for i in block_ids}, gate)
            misspecification_closed = gate_result["inflated"]
        if misspecification_closed or feasibility_now["closed"]:
            stopped_after = sheet.sheet_id
            break
    closed_sheets = [
        sheet_id for sheet_id, rows in feasibility_sheets.items()
        if any(row["exceeds"] for row in rows)
    ]
    return {
        "stage": stage_index,
        "n_rep": n_rep,
        "misspecification_gate": gate_result,
        "feasibility_gate": {
            "scope": feasibility.scope,
            "ci_level": feasibility.ci_level,
            "lower_bound_above": feasibility.lower_bound_above,
            "sheets": feasibility_sheets,
            "closed_sheets": closed_sheets,
            "closed": bool(closed_sheets),
        },
        "stopped_at_gate": bool(gate_result and gate_result["inflated"]),
        "stopped_at_feasibility_gate": bool(closed_sheets),
        "stopped_after_sheet": stopped_after,
        "sheets": sheet_summaries,
        "margin_table": margin_quantile_table(
            sheet_points, {s.sheet_id: s.role for s in sheets}, axes
        ),
    }


def run(config: Mapping[str, Any], out_dir: Path, rscript_override: str | None,
        keep_frames: bool, workers_override: int | None = None, *,
        through_stage: int, config_path: Path | None = None) -> dict[str, Any]:
    """段を順に回して最後の段の結果を返す。答える問い: 10 シードの設計で、何が言えるか。

    **表を組む → R に投げる → 数える、の 3 段しかない。**
    当てはめの中身は `power_sim_fit.R` にある(skill `code-style` §2)。

    **回すのは `through_stage` 段目まで**(人間 2026-10-04 その143: 段ごとに止まり、人間が見てから
    次の段を起動する)。同じ `out_dir` に大きい `through_stage` で起動し直すと、済んだ反復は飛ばして続きから回る。
    """
    sheets = load_sheets(config)
    gate = load_gate_spec(config)
    feasibility = load_feasibility_gate_spec(config)
    check_gate_against_sheets(gate, sheets)
    axes = load_axis_spec(config)
    stages = load_stages(config)
    if not 1 <= through_stage <= len(stages):
        raise ConfigError(
            f"--through-stage は 1〜{len(stages)}(simulation.n_rep_stages = {list(stages)}): {through_stage}"
        )
    for n_item in load_n_item_grid(config):
        load_levels(config, n_item)
    s2_item = float(require(config, "dgp.s2_item"))
    s2_tmpl = float(require(config, "dgp.s2_tmpl"))
    alpha = float(require(config, "simulation.alpha"))
    target_power = float(require(config, "simulation.target_power"))
    rng_seed = int(require(config, "simulation.rng_seed"))

    rscript = resolve_rscript(rscript_override or config["fit"].get("rscript"))
    n_workers = int(workers_override or require(config, "fit.n_workers"))
    ctx = RunContext(
        config=config,
        out_dir=out_dir,
        s2_item=s2_item,
        s2_tmpl=s2_tmpl,
        alpha=alpha,
        target_power=target_power,
        rng_seed=rng_seed,
        rscript=rscript,
        libpath=config["fit"].get("r_libpath"),
        refit=config["fit"]["refit"],
        max_level=len(require(config, "fit.reduction_order")),
        allfit=load_allfit_spec(config),
        n_workers=n_workers,
        keep_frames=keep_frames,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    info = record_run(out_dir, config, config_path, through_stage, n_workers)
    header = {
        "run_id": info["run_id"],
        "n_seed": int(require(config, "dgp.n_seed")),
        "n_item_grid": list(load_n_item_grid(config)),
        "n_rep_stages": list(stages),
        "s2_item": s2_item,
        "s2_tmpl": s2_tmpl,
        "alpha": alpha,
        "tost_alpha": float(require(config, "simulation.tost_alpha")),
        "tost_delta_note": (
            "tost_min_margins is, per replication, the smallest delta at which both interaction "
            "CIs fall inside +-delta; the TOST power at any delta is the share <= delta "
            "(tost_power). delta is NOT chosen here (ADR-114 decision 5). tost_min_margins hold "
            "successful fits only; the tost_n_failed failed fits enter tost_power and the margin "
            "quantiles on the unfavourable side (power sheets: equivalent, delta 0; error sheets: "
            "not equivalent, delta +inf, a quantile reaching them is null). ADR-125"
        ),
        # ★実行資源のつまみであって実験パラメータではない。結果はこの値に依らない
        # (ADR-069 決定3)。それでも「何並列で回したか」は再現の記録として残す。
        "n_workers": n_workers,
        "assumed_values_note": (
            "n_item, sigma and rho are ASSUMED values, not measurements; n_item here is NOT "
            "eval.cells (05_STATISTICS.md section 6.8; ADR-122 / ADR-123)"
        ),
    }
    summary: dict[str, Any] = {}
    for stage_index, n_rep in enumerate(stages[:through_stage], start=1):
        summary = {**header, **run_stage(ctx, sheets, gate, feasibility, axes, stage_index, n_rep)}
        write_json_atomic(out_dir / stage_summary_name(n_rep), summary)
        write_json_atomic(out_dir / SUMMARY_FILE, summary)
        if summary["stopped_at_gate"] or summary["stopped_at_feasibility_gate"]:
            break
    return summary


def estimate_seconds_per_pair(levels: DesignLevels) -> float:
    """答える問い: この表 1 枚の当てはめ(`full` + `add` の 1 ペア)は何秒か(★推算。ベンチの基準)。

    実測は 5,760 行で 297.6 秒(★F114。逐次)。**行数に比例すると仮定する**(= `n_item` に比例)。
    T1 × T2・`n_item = 80` の 4,800 行は約 248 秒になる(PLAN-034 §5.2)。**未実測**。
    """
    return SECONDS_PER_PAIR_MEASURED * table_rows(levels) / ROWS_AT_MEASUREMENT


def estimate_seconds_per_pair_check(levels: DesignLevels) -> float:
    """答える問い: 同じ 1 ペアは何コア秒か(★推算。PLAN-034 の見直しの小検査の基準)。

    小検査は 4,800 行の 64 ペアを 16 並列で 27.5 分 → 約 412 コア秒 / ペア(16 並列の下の実効)。
    **行数に比例すると仮定する**。**未実測**(ADR-123 文脈1)。
    """
    per_pair = CHECK_WALL_SECONDS * CHECK_WORKERS / CHECK_PAIRS
    return per_pair * table_rows(levels) / CHECK_ROWS


def table_rows(levels: DesignLevels) -> int:
    """答える問い: この水準の表は何行か(当てはめの費用はこれに比例すると仮定する)。"""
    return levels.n_seed * len(levels.tasks) * len(levels.coverages) * levels.n_item


def stage_cost_lines(
    config: Mapping[str, Any], sheets: Sequence[Sheet], stages: Sequence[int], workers: int
) -> list[str]:
    """答える問い: 各段で足す当てはめは何ペアで、何時間か(★推算。2 つの基準を並べる)。"""
    seconds = {
        n_item: (
            estimate_seconds_per_pair(load_levels(config, n_item)),
            estimate_seconds_per_pair_check(load_levels(config, n_item)),
        )
        for n_item in load_n_item_grid(config)
    }
    lines = [
        "cost      : ESTIMATED, scaled by rows (= n_item). Two bases:",
        f"            bench = {SECONDS_PER_PAIR_MEASURED} s/pair measured serially at "
        f"{ROWS_AT_MEASUREMENT} rows (run 20260909_bench_powersim)",
        f"            check = {CHECK_PAIRS} pairs x {CHECK_WORKERS} workers in "
        f"{CHECK_WALL_SECONDS / 60:g} min at {CHECK_ROWS} rows "
        "(plans/PLAN-034-check-prerun; not in runs/)",
        "            s/pair by n_item (bench / check): "
        + ", ".join(f"{n}: {b:.0f} / {c:.0f}" for n, (b, c) in seconds.items()),
    ]
    previous = 0
    for index, n_rep in enumerate(stages, start=1):
        added = n_rep - previous
        total = [0.0, 0.0]
        first_sheet = [0.0, 0.0]
        n_pairs = 0
        for sheet in sheets:
            for key in sheet.points:
                n_pairs += added
                for basis in (0, 1):
                    cost = added * seconds[key.n_item][basis]
                    total[basis] += cost
                    if sheet.role == ROLE_MISSPECIFICATION:
                        first_sheet[basis] += cost
        lines.append(
            f"  stage {index}: reps {previous}->{n_rep} (+{added}), {n_pairs} pairs; "
            f"wall-clock hours at {workers} workers (bench / check): "
            f"all sheets {total[0] / 3600 / workers:.1f} / {total[1] / 3600 / workers:.1f}, "
            f"misspecification sheets only ({len(leading_misspecification_block(sheets))} sheets) "
            f"{first_sheet[0] / 3600 / workers:.1f} / {first_sheet[1] / 3600 / workers:.1f}"
        )
        previous = n_rep
    return lines


def describe_plan(config: Mapping[str, Any], workers_override: int | None = None) -> list[str]:
    """回す前に「何本の当てはめになるか」を出す。答える問い: このコストは払えるか。

    **下の時間は 2 つの基準(逐次のベンチ / 16 並列の小検査)を行数で比例させた推算であり、`n_item` に比例して動く。**
    段ごとに「全シート」と「先頭のシート(誤指定)だけ」を出す —— 門が閉じれば、その段は先頭のシートだけで止まる。
    """
    sheets = load_sheets(config)
    stages = load_stages(config)
    # 出力は ASCII のみ。この環境の stdout は cp932 であり、em dash で落ちる
    # (`plans/PLAN-019-check2/` の検査スクリプトと同じ制約)。
    lines = [
        f"sheets    : {len(sheets)} (run in this order; the gate is judged after the leading "
        f"{len(leading_misspecification_block(sheets))} misspecification sheets)"
    ]
    for sheet in sheets:
        points = ", ".join(f"({k.n_item}, {k.sigma:g}, {k.rho:g})" for k in sheet.points)
        form = (
            "" if sheet.seed_interaction is None
            else f" seed_interaction({sheet.seed_interaction.direction_profile}, {sheet.seed_interaction.scale})"
        )
        lines.append(
            f"  {sheet.sheet_id:<16} {sheet.role:<17} profile {sheet.profile:<7} "
            f"tau {sheet.tau!s:<12}{form} {len(sheet.points)} points (n_item, sigma, rho): {points}"
        )
    n_points = sum(len(sheet.points) for sheet in sheets)
    n_pairs = n_points * stages[-1]
    lines += [
        f"n_seed    : {require(config, 'dgp.n_seed')}  (ADR-028)",
        f"stages    : {list(stages)} (cumulative reps; one invocation runs --through-stage N)",
        f"fits      : {n_pairs * 2} at the last stage "
        f"(= {n_points} points x {stages[-1]} x 2); a reduced iteration costs more",
        "NOTE: n_item, sigma and rho are ASSUMED values; n_item here is NOT eval.cells",
    ]
    # ★PLAN-043 I5: 門と allFit の宣言は dry-run でも読む(config の食い違いを本実行の前に止める)
    gate = load_gate_spec(config)
    check_gate_against_sheets(gate, sheets)
    feasibility = load_feasibility_gate_spec(config)
    allfit = load_allfit_spec(config)
    lines += [
        f"rng_seed  : {require(config, 'simulation.rng_seed')}  (committed before launch; PLAN-043 trap 4)",
        "allfit    : floor stage after the last reduction level; optimizers "
        + ", ".join(allfit.optimizers)
        + f"; start_from_mle {str(allfit.start_from_mle).lower()}; min_aligned {allfit.min_aligned}; "
        f"R {allfit.expected_r_version} / lme4 {allfit.expected_lme4_version}",
        "failures  : counted as non-rejections on every sheet; TOST delta = +inf on every sheet (ADR-128)",
        f"gate      : misspecification (exit {EXIT_GATE_CLOSED}) CP{gate.ci_level * 100:g} lower bound > "
        f"{gate.lower_bound_above:g} at "
        + "; ".join(f"{sheet_id}: tau {list(taus)}" for sheet_id, taus in gate.points),
        f"            feasibility (exit {EXIT_FEASIBILITY_CLOSED}) CP{feasibility.ci_level * 100:g} lower bound of the "
        f"failure rate > {feasibility.lower_bound_above:g} at {feasibility.scope}",
    ]
    workers = int(workers_override or config["fit"].get("n_workers") or 1)
    try:
        lines += stage_cost_lines(config, sheets, stages, workers)
    except ConfigError:
        lines.append("cost      : UNDECIDED (dgp.templates or dgp.n_seed is null) -- cannot scale")
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
    parser.add_argument("--through-stage", type=int,
                        help="何段目まで回すか(simulation.n_rep_stages の 1 始まりの番号)。本実行では必須")
    parser.add_argument("--rscript", help="config の fit.rscript を上書きする")
    parser.add_argument("--dry-run", action="store_true",
                        help="格子と当てはめ本数・時間の見積りだけを出す。R を呼ばない")
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
    if args.out_dir is None or args.through_stage is None:
        parser.error("--out-dir と --through-stage が要る(--dry-run でない場合)")
    summary = run(
        config, args.out_dir, args.rscript, args.keep_frames, args.workers,
        through_stage=args.through_stage, config_path=args.config,
    )
    report = {
        "run_id": summary["run_id"],
        "stage": summary["stage"],
        "n_rep": summary["n_rep"],
        "misspecification_gate": summary["misspecification_gate"],
        "feasibility_gate": {
            "closed": summary["feasibility_gate"]["closed"],
            "closed_sheets": summary["feasibility_gate"]["closed_sheets"],
            "stopped_after_sheet": summary["stopped_after_sheet"],
        },
        "inverse_problem": {
            sheet_id: body["inverse_problem"]
            for sheet_id, body in summary["sheets"].items()
            if "inverse_problem" in body
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    if summary["stopped_at_gate"]:
        print("STOPPED: the misspecification gate closed (ADR-123 decision 6). "
              "P1 / P1_neg / P0 of this stage were not run.")
        return EXIT_GATE_CLOSED
    if summary["stopped_at_feasibility_gate"]:
        print("STOPPED: the feasibility gate closed (ADR-128 decision 3): the share of fit failures is too "
              f"high at {summary['feasibility_gate']['closed_sheets']}. The sheets after "
              f"{summary['stopped_after_sheet']} of this stage were not run.")
        return EXIT_FEASIBILITY_CLOSED
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
