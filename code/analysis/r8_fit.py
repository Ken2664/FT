"""R8(閾値掃引)の当てはめ(PLAN-026 I5)。

答える問い: 「閾値掃引の run で、各(タスク型 × 既知性)セルの交差点 `θ*` はどこにあり、
閾値から遠いオフセットでモデルは和を読んで答えているか」

    python -m code.analysis.r8_fit --runs "runs/*exp_order6b_r8*"
    python -m code.analysis.r8_fit --runs "runs/*exp_order6b_r8*" --out-dir results/r8_fit_order6b
    python -m code.analysis.r8_fit --runs "runs/*<条件>*r8*" --ident-run runs/<ident の run>

**値を出すだけで、判断しない**(`CLAUDE.md` §8)。PLAN-026 §5 の判定表(合否)は I11、
§6 の分岐の読みは人間。**`pool_id: pilot` の run の数値は主張の根拠に使わない**(PLAN-001 §4.6 規則4)。

- **揃え方 (a)**(ADR-079 決定1): `y = 1` ⇔「和は閾値より小さい側だと答えた」(gt で `answer` が No、
  lt で Yes)。極性を同数混ぜたまま `logit P(y = 1) = β0 + β1·θ` → `θ* = −β0/β1`。
  **極性ごとの `θ*_gt`・`θ*_lt` と開き `θ*_lt − θ*_gt` を併記する**
- **「階段の位置」**(PLAN-026 §3.2.1.1 / ADR-081 決定1・決定2): θ の水準ごとに畳んだ応答を
  片側だけ → 階段 → 逆向きの階段 → 当てはめ の順に分類する(`locate_crossing`)。
  **階段は除外せず、交差点を `(L + U) / 2` に置く**
- **除外件数を必ず出す**(ADR-030 決定6): 片側だけ(すべて 0 / すべて 1)・逆向きの階段・`β1 ≤ 0`・
  分離以外の非収束。**`β1 ≤ 0` の件数 = 逆向きの階段 + 当てはめで `β1 ≤ 0`**
- **遠いオフセットの correct**(PLAN-026 §5 (iv)): `answer == truth` の割合を低い側と高い側で別に。
  **判定の単位はセル(タスク型 × 既知性)**(ADR-081 決定3)。タスク型でまとめた値は記述として添える。
  境界は S の θ の水準から導く(`far_offsets_from_config`。PLAN-026 §4.6 読み2)
- `Δ̂ = θ*(条件) − θ*(ident)` は 2 つの run の差(`delta_hat_table`)。`--ident-run` を渡したときだけ出す
  (順6b は素のモデル 1 本なので出さない。PLAN-026 §4.6 読み3)

**当てはめの単位は(タスク型 × 既知性)セル**(ADR-030 決定6)で、`carry` の 2 セルと各 20 組を合わせる。
セルの鍵は predictions の `task_type` と `coverage` の欄であり、`sweep_cell` の名前を解析しない。
**入力は I4 の記録の経路が書いた run だけ**(`metrics.json` の `kind: threshold_sweep`)。
件数・θ・閾値・真値が `metrics.json` とそろっていなければ止める —— 欠けた記録を当てはめない。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from code.analysis import calibrated
from code.analysis.aggregate import expand_metrics_paths
from code.analysis.frame import CONFIG_FILENAME
from code.analysis.gonogo import near_tie_margin_from_config
from code.artifacts import PREDICTIONS_DIR, utc_now
from code.config import ConfigError, load_config, require
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.data_gen.sweep_pool import POLARITIES
from code.eval.battery import t3_comparison
from code.eval.run import THRESHOLD_SWEEP_KIND, threshold_sweep_predictions_name

OUTPUT_FILENAME = "r8_fit.json"

# 当てはめの 3 つ: 極性を混ぜたもの(`θ*`。`Δ̂` はこれで取る)と極性ごと(`θ*_gt`・`θ*_lt`)。
MIXED = "mixed"
FIT_SCOPES: tuple[str, ...] = (MIXED, *POLARITIES)

# 分類(PLAN-026 §3.2.1.1)。**階段は除外ではない**(ADR-079 決定1)。
FIT = "fit"
STAIRCASE = "staircase"
ONE_SIDED_ZERO = "one_sided_all_0"
ONE_SIDED_ONE = "one_sided_all_1"
REVERSED_STAIRCASE = "reversed_staircase"
BETA1_NONPOSITIVE = "beta1_nonpositive"
NONCONVERGENT = "nonconvergent"
INCLUDED_KINDS: tuple[str, ...] = (FIT, STAIRCASE)
EXCLUDED_KINDS: tuple[str, ...] = (
    ONE_SIDED_ZERO,
    ONE_SIDED_ONE,
    REVERSED_STAIRCASE,
    BETA1_NONPOSITIVE,
    NONCONVERGENT,
)
KINDS: tuple[str, ...] = (*INCLUDED_KINDS, *EXCLUDED_KINDS)
# 「`β1 ≤ 0` は除外」(ADR-030 決定6)に入る分類。逆向きの階段は `β1 → −∞` の場合である。
BETA1_NONPOSITIVE_KINDS: tuple[str, ...] = (REVERSED_STAIRCASE, BETA1_NONPOSITIVE)

# 強制選択の値そのもの(ADR-084 決定3)。近接同点の差はここから作る。
YES_LOGP_FIELD = "yes_logp"
NO_LOGP_FIELD = "no_logp"

NEAR_TIE_NOTE = (
    "感度の行(PLAN-026 §7 / ADR-086 決定3)。§5 (i)〜(iv) の合否には使わない。"
    "|差| ≤ margin(境界を含む)の項目を遠いオフセットの側ごとに数え、除いた correct を併記する。"
    "**閾値の近くの θ は数えない** —— §5 (iv) が見るのは遠い側だけである"
)

# 遠いオフセットの 2 つの側(PLAN-026 §5 (iv))。
LOW = "low"
HIGH = "high"
SIDES: tuple[str, ...] = (LOW, HIGH)

# 遠いオフセットの境界を導く腕と、その θ の水準の鍵(PLAN-026 §4.6 読み2)。
# S の 5 水準は「すべて閾値から 2 以上離れた遠いオフセット」として置かれた(§3.7)ので、
# §5 (iv) の「θ ≤ −2 の側と θ ≥ +3 の側」は S の負の水準の最大と正の水準の最小に当たる。
FAR_OFFSET_ARM = "s"
SWEEP_OFFSETS_KEY = "eval.threshold_sweep.offsets"
# θ = 0 は閾値が和そのものになる点(T = t + θ)。gt の真値はここで Yes から No に変わる。
# 遠いオフセットの 2 つの側はこの点の下と上で分ける(**実験条件ではなく T = t + θ の構造**)。
EQUAL_THRESHOLD_OFFSET = 0

# Newton 法の数値設定。**実験条件ではない**(`code.rates.TOTAL_TOLERANCE` と同じ扱い)。
# 分離も片側だけも無いデータでは、1 変数 + 切片のロジスティック回帰の最尤推定は存在して一意で、
# 対数尤度は狭義に凹なので、ここの値は収束の判定にしか効かない(PLAN-026 §3.2.1.1 の 4)。
NEWTON_MAX_ITERATIONS = 100
# 1 回の Newton 歩の成分の絶対値がこれ以下になったら収束とみなす。
NEWTON_STEP_TOLERANCE = 1e-10
# 対数尤度が下がる歩を半分にする回数の上限(行き過ぎ止め)。
MAX_STEP_HALVINGS = 60


class R8FitError(ValueError):
    """R8 の当てはめを組めない。取り違えた記録を当てはめるより止める。"""


# --------------------------------------------------------------------------
# 揃え方と、θ ごとの畳み込み
# --------------------------------------------------------------------------


def aligned_response(polarity: str, answer: bool) -> int:
    """揃え方 (a) の目的変数(ADR-079 決定1)。

    答える問い: 「この答えは『和は閾値より小さい側だ』と言ったか」

    gt(`a+b > T?`)では No、lt(`a+b < T?`)では Yes が 1。**θ の符号は反転しない** ——
    閾値は両極性とも `T = t + θ` なので、反転すると交差点が `Δ` に依らなくなる(★F141)。
    """
    if polarity == t3_comparison.GT:
        return int(not answer)
    if polarity == t3_comparison.LT:
        return int(answer)
    raise R8FitError(f"未知の極性: {polarity!r}。{POLARITIES} のいずれか")


@dataclass(frozen=True)
class ThetaCounts:
    """θ の水準ごとの項目数 `n` と `y = 1` の数 `k`(θ の昇順)。"""

    thetas: tuple[int, ...]
    n: tuple[int, ...]
    k: tuple[int, ...]

    def __post_init__(self) -> None:
        if not (len(self.thetas) == len(self.n) == len(self.k)):
            raise R8FitError("θ・n・k の長さが違う")
        if list(self.thetas) != sorted(set(self.thetas)):
            raise R8FitError(f"θ は重複のない昇順でなければならない: {self.thetas}")
        if len(self.thetas) < 2:
            raise R8FitError(f"θ の水準が 2 つ未満では傾きが定まらない: {self.thetas}")
        if any(count <= 0 for count in self.n):
            raise R8FitError(f"項目の無い θ の水準がある: {dict(zip(self.thetas, self.n))}")
        if any(not 0 <= ones <= count for ones, count in zip(self.k, self.n)):
            raise R8FitError("y = 1 の数が 0 未満か項目数を超える")

    @property
    def n_total(self) -> int:
        return sum(self.n)

    @property
    def n_positive(self) -> int:
        return sum(self.k)


def theta_counts(observations: Iterable[tuple[int, int]]) -> ThetaCounts:
    """(θ, y) の列を θ の水準ごとの (n, k) に畳む。"""
    totals: Counter[int] = Counter()
    ones: Counter[int] = Counter()
    for theta, response in observations:
        if response not in (0, 1):
            raise R8FitError(f"y は 0 か 1 でなければならない: {response!r}")
        totals[theta] += 1
        ones[theta] += response
    thetas = tuple(sorted(totals))
    return ThetaCounts(
        thetas=thetas,
        n=tuple(totals[theta] for theta in thetas),
        k=tuple(ones[theta] for theta in thetas),
    )


# --------------------------------------------------------------------------
# ロジスティック回帰(Newton 法)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LogisticFit:
    """`logit P(y = 1) = β0 + β1·θ` の最尤推定。"""

    beta0: float
    beta1: float
    converged: bool
    iterations: int


def _log_likelihood(
    design: np.ndarray, n: np.ndarray, k: np.ndarray, beta: np.ndarray
) -> float:
    # log p = −log(1 + e^−η)、log(1 − p) = −log(1 + e^η)。|η| が大きくても溢れない形で書く
    eta = design @ beta
    return float(np.sum(-k * np.logaddexp(0.0, -eta) - (n - k) * np.logaddexp(0.0, eta)))


def fit_logistic(counts: ThetaCounts) -> LogisticFit:
    """二項の集計データにロジスティック回帰を Newton 法で当てる。

    答える問い: 「応答が重なるセルで、`P(y = 1)` は θ についてどちら向きに、どれだけ急に変わるか」

    **分離しているデータを渡さない**(最尤推定が存在せず、`β1` が発散する)。分離の判定は
    `locate_crossing` が先に行う。ここで収束しないのは数値計算の理由だけである。
    歩が対数尤度を下げるときは半分にする(Newton 法の行き過ぎ止め)。
    """
    theta = np.asarray(counts.thetas, dtype=float)
    n = np.asarray(counts.n, dtype=float)
    k = np.asarray(counts.k, dtype=float)
    design = np.column_stack([np.ones_like(theta), theta])
    beta = np.zeros(2)
    log_likelihood = _log_likelihood(design, n, k, beta)
    for iteration in range(1, NEWTON_MAX_ITERATIONS + 1):
        probability = np.exp(-np.logaddexp(0.0, -(design @ beta)))
        gradient = design.T @ (k - n * probability)
        hessian = design.T @ (design * (n * probability * (1.0 - probability))[:, None])
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            return LogisticFit(float(beta[0]), float(beta[1]), False, iteration)
        # 収束の判定は半分にする前の歩で行う(収束の近くでは丸めの誤差で対数尤度がわずかに
        # 下がりうるので、先に半分にすると収束した点を非収束と読んでしまう)
        if np.max(np.abs(step)) <= NEWTON_STEP_TOLERANCE:
            beta = beta + step
            return LogisticFit(float(beta[0]), float(beta[1]), True, iteration)
        for _ in range(MAX_STEP_HALVINGS):
            candidate = beta + step
            candidate_log_likelihood = _log_likelihood(design, n, k, candidate)
            if candidate_log_likelihood >= log_likelihood:
                break
            step = step / 2.0
        else:
            return LogisticFit(float(beta[0]), float(beta[1]), False, iteration)
        beta, log_likelihood = candidate, candidate_log_likelihood
    return LogisticFit(float(beta[0]), float(beta[1]), False, NEWTON_MAX_ITERATIONS)


# --------------------------------------------------------------------------
# 「階段の位置」(PLAN-026 §3.2.1.1 / ADR-081)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Crossing:
    """1 つの当てはめ(セル × 混ぜた / 極性ごと)の分類と交差点。

    `lower`・`upper` は階段なら `L`(y = 0 の最大の θ)・`U`(y = 1 の最小の θ)、
    逆向きの階段なら y = 1 の最大の θ・y = 0 の最小の θ。それ以外は None。
    `beta0`・`beta1` は当てはめ(`fit_logistic`)を行った分類でだけ値を持つ。
    """

    kind: str
    theta_star: float | None
    beta0: float | None
    beta1: float | None
    lower: int | None
    upper: int | None
    n: int
    n_positive: int
    iterations: int | None

    @property
    def included(self) -> bool:
        return self.kind in INCLUDED_KINDS

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "included": self.included,
            "theta_star": self.theta_star,
            "beta0": self.beta0,
            "beta1": self.beta1,
            "lower": self.lower,
            "upper": self.upper,
            "n": self.n,
            "n_positive": self.n_positive,
            "iterations": self.iterations,
        }


def locate_crossing(counts: ThetaCounts) -> Crossing:
    """交差点を取る。分類は 1 → 4 の順(PLAN-026 §3.2.1.1)。

    答える問い: 「このセルの応答は θ のどこで『閾値より小さい側』に切り替わるか。
    切り替わりが定まらないなら、それはどの理由か」

      1. **片側だけ**(y がすべて 0 / すべて 1): 除外。位置が決まらない
      2. **階段**(`L ≤ U`。完全分離と準完全分離): **除外しない。**`θ* = (L + U) / 2`。`β1` は +∞ に
         発散するので出さない。`L = U` なら最尤推定の列の極限と一致し、`L < U` なら極限の区間の中心
      3. **逆向きの階段**(y = 1 の最大の θ ≤ y = 0 の最小の θ): `β1 → −∞`。`β1 ≤ 0` として除外
      4. **重なる**: `fit_logistic`。非収束は「分離以外の非収束」、`β1 ≤ 0` は除外、それ以外は `−β0/β1`

    **単調でない応答も、分離していなければ 4 に入る**(平滑化も単調回帰も使わない)。
    """
    base = {"n": counts.n_total, "n_positive": counts.n_positive}
    if counts.n_positive == 0:
        return Crossing(ONE_SIDED_ZERO, None, None, None, None, None, iterations=None, **base)
    if counts.n_positive == counts.n_total:
        return Crossing(ONE_SIDED_ONE, None, None, None, None, None, iterations=None, **base)
    rows = list(zip(counts.thetas, counts.n, counts.k))
    zero_thetas = [theta for theta, total, ones in rows if total - ones > 0]
    one_thetas = [theta for theta, _, ones in rows if ones > 0]
    lower, upper = max(zero_thetas), min(one_thetas)
    if lower <= upper:
        return Crossing(
            STAIRCASE, (lower + upper) / 2, None, None, lower, upper, iterations=None, **base
        )
    reversed_lower, reversed_upper = max(one_thetas), min(zero_thetas)
    if reversed_lower <= reversed_upper:
        return Crossing(
            REVERSED_STAIRCASE,
            None,
            None,
            None,
            reversed_lower,
            reversed_upper,
            iterations=None,
            **base,
        )
    fit = fit_logistic(counts)
    kind = FIT
    if not fit.converged:
        kind = NONCONVERGENT
    elif fit.beta1 <= 0:
        kind = BETA1_NONPOSITIVE
    theta_star = -fit.beta0 / fit.beta1 if kind == FIT else None
    return Crossing(
        kind, theta_star, fit.beta0, fit.beta1, None, None, iterations=fit.iterations, **base
    )


# --------------------------------------------------------------------------
# 遠いオフセットの境界
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FarOffsets:
    """遠いオフセットの 2 つの側: `θ ≤ low_max` と `θ ≥ high_min`。"""

    low_max: int
    high_min: int
    source: str

    def side_of(self, theta: int) -> str | None:
        """θ がどちらの側か。閾値の近く(どちらでもない)なら None。"""
        if theta <= self.low_max:
            return LOW
        if theta >= self.high_min:
            return HIGH
        return None

    def as_dict(self) -> dict[str, Any]:
        return {"low_max": self.low_max, "high_min": self.high_min, "source": self.source}


def far_offsets_from_config(config: Mapping[str, Any]) -> FarOffsets:
    """遠いオフセットの境界を S の θ の水準から導く(PLAN-026 §4.6 読み2)。

    答える問い: 「PLAN-026 §5 (iv) の『θ ≤ −2 の側と θ ≥ +3 の側』は、この run の config の
    どの値から来たか」

    **新しい数を置かない。**S の水準のうち閾値より下(θ < 0)の最大と上(θ > 0)の最小を境界にする。
    S は C1・C2 の (iv) を測る掃引であり、C0・C3 の (iv) を R8 で測るときも同じ境界で読む必要がある。
    S の水準に θ = 0 があるか、片側に水準が無ければ止める(側が決まらない)。
    """
    try:
        offsets = require(config, SWEEP_OFFSETS_KEY)
        levels = [int(theta) for theta in offsets[FAR_OFFSET_ARM]]
    except (ConfigError, KeyError, TypeError) as exc:
        raise R8FitError(
            f"config の {SWEEP_OFFSETS_KEY}.{FAR_OFFSET_ARM} が読めない({exc})。"
            "遠いオフセットの境界は S の θ の水準から導く(PLAN-026 §4.6 読み2)"
        ) from exc
    below = [theta for theta in levels if theta < EQUAL_THRESHOLD_OFFSET]
    above = [theta for theta in levels if theta > EQUAL_THRESHOLD_OFFSET]
    if EQUAL_THRESHOLD_OFFSET in levels or not below or not above:
        raise R8FitError(
            f"{SWEEP_OFFSETS_KEY}.{FAR_OFFSET_ARM} = {levels} からは遠いオフセットの 2 つの側が"
            f"決まらない(θ = {EQUAL_THRESHOLD_OFFSET} を含まず、その下と上に水準が要る)"
        )
    return FarOffsets(
        low_max=max(below),
        high_min=min(above),
        source=f"{SWEEP_OFFSETS_KEY}.{FAR_OFFSET_ARM}",
    )


# --------------------------------------------------------------------------
# 1 つの run の記録から
# --------------------------------------------------------------------------


def _cell_order(task_types: Sequence[str]) -> list[tuple[str, str]]:
    return [(task, coverage) for task in task_types for coverage in MAIN_COVERAGE_LEVELS]


def polarity_gap(crossings: Mapping[str, Crossing]) -> float | None:
    """極性ごとの交差点の開き `θ*_lt − θ*_gt`。どちらかが除外なら None。

    **真値どおりに答えるモデルで 1 になる**(0 ではない。θ = 0 で両極性とも真値が No のため。
    PLAN-026 §3.2.1.1)。
    """
    gt_star = crossings[t3_comparison.GT].theta_star
    lt_star = crossings[t3_comparison.LT].theta_star
    if gt_star is None or lt_star is None:
        return None
    return lt_star - gt_star


def correct_block(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """`answer == truth` の件数と割合。**0 件なら止める**(境界と θ の水準が合っていない)。"""
    n = len(records)
    if n == 0:
        raise R8FitError("遠いオフセットの側に項目が 1 つも無い。境界と run の θ の水準が合っていない")
    n_correct = sum(1 for record in records if record["answer"] == record["truth"])
    return {"n": n, "n_correct": n_correct, "correct_rate": n_correct / n}


def far_offset_correct(
    records: Sequence[Mapping[str, Any]], far: FarOffsets
) -> dict[str, dict[str, Any]]:
    """遠いオフセットの correct を低い側と高い側で別に出す(PLAN-026 §5 (iv))。

    答える問い: 「閾値から遠い θ で、モデルは真値どおりに答えているか」

    **合否は付けない**(判定表は I11)。★F138 の定数戦略(gt → No / lt → Yes)は低い側で 0 になる。
    """
    by_side: dict[str, list[Mapping[str, Any]]] = {side: [] for side in SIDES}
    for record in records:
        side = far.side_of(int(record["threshold_offset"]))
        if side is not None:
            by_side[side].append(record)
    return {side: correct_block(by_side[side]) for side in SIDES}


def fit_records(
    records: Sequence[Mapping[str, Any]], *, task_types: Sequence[str], far: FarOffsets
) -> dict[str, Any]:
    """掃引の記録から、セルごとの交差点・除外件数・遠いオフセットの correct を組む。

    答える問い: 「この run の各(タスク型 × 既知性)セルの交差点はどこか。どのセルが、どの理由で
    除外されたか。遠いオフセットで和を読んでいるか」

    記録の検査は済んでいるものとする(`check_records`)。**率と交差点は実験結果である。**
    """
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault((record["task_type"], record["coverage"]), []).append(record)
    unknown = sorted(set(grouped) - set(_cell_order(task_types)))
    if unknown:
        raise R8FitError(f"(タスク型 × 既知性)セルが想定の外にある: {unknown}")
    cells: list[dict[str, Any]] = []
    exclusions: dict[str, Counter[str]] = {scope: Counter() for scope in FIT_SCOPES}
    for task, coverage in _cell_order(task_types):
        cell_records = grouped.get((task, coverage), [])
        if not cell_records:
            continue
        crossings = {
            scope: locate_crossing(
                theta_counts(
                    (
                        int(record["threshold_offset"]),
                        aligned_response(record["polarity"], record["answer"]),
                    )
                    for record in cell_records
                    if scope == MIXED or record["polarity"] == scope
                )
            )
            for scope in FIT_SCOPES
        }
        for scope, crossing in crossings.items():
            exclusions[scope][crossing.kind] += 1
        cells.append(
            {
                "task_type": task,
                "coverage": coverage,
                "n": len(cell_records),
                "crossing": {scope: crossing.as_dict() for scope, crossing in crossings.items()},
                "polarity_gap": polarity_gap(crossings),
                "far_offset_correct": far_offset_correct(cell_records, far),
            }
        )
    by_task = [
        {
            "task_type": task,
            **far_offset_correct([r for r in records if r["task_type"] == task], far),
        }
        for task in task_types
    ]
    return {
        "cells": cells,
        "exclusions": {
            scope: {
                "n_cells": sum(counts.values()),
                "by_kind": {kind: counts[kind] for kind in KINDS},
                "beta1_nonpositive_total": sum(counts[kind] for kind in BETA1_NONPOSITIVE_KINDS),
                "excluded_total": sum(counts[kind] for kind in EXCLUDED_KINDS),
            }
            for scope, counts in exclusions.items()
        },
        "far_offset_correct_by_task_type": by_task,
    }


# --------------------------------------------------------------------------
# run の読み込みと検査
# --------------------------------------------------------------------------

REQUIRED_FIELDS: tuple[str, ...] = (
    "item_id",
    "task_type",
    "polarity",
    "sweep_cell",
    "coverage",
    "t",
    "threshold",
    "threshold_offset",
    "answer",
    "truth",
)


def read_sweep_predictions(run_dir: Path, task_types: Sequence[str]) -> dict[str, list[dict]]:
    """predictions/threshold_sweep.<タスク型>.jsonl を読む({predictions の名前: 行})。"""
    records: dict[str, list[dict]] = {}
    for task in task_types:
        name = threshold_sweep_predictions_name(task)
        path = run_dir / PREDICTIONS_DIR / f"{name}.jsonl"
        if not path.is_file():
            raise R8FitError(f"{path} が無い")
        lines = path.read_text(encoding="utf-8").splitlines()
        records[name] = [json.loads(line) for line in lines if line.strip()]
    return records


def check_records(
    records_by_name: Mapping[str, Sequence[Mapping[str, Any]]], sweep: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """記録が metrics.json の threshold_sweep 欄とそろっていることを確かめ、行を 1 列にして返す。

    答える問い: 「当てはめる記録は、この run が解いた項目のすべてで、θ・閾値・真値が壊れていないか」

    止める食い違い: predictions の行数 / 欄の欠け / 極性・タスク型・θ が宣言の外 /
    閾値が `T = t + θ` でない / 真値が `comparison_answer` と違う / `answer` が真偽値でない /
    `item_id` の重複 / (併合セル × 極性 × θ)の件数が `n_items_by_cell` と違う。
    """
    expected_rows = sweep["predictions"]
    if set(records_by_name) != set(expected_rows):
        raise R8FitError(
            f"predictions のファイルが違う: {sorted(records_by_name)} / {sorted(expected_rows)}"
        )
    offsets = {int(theta) for theta in sweep["threshold_offsets"]}
    task_types = set(sweep["task_types"])
    rows: list[Mapping[str, Any]] = []
    for name, records in records_by_name.items():
        if len(records) != expected_rows[name]:
            raise R8FitError(
                f"{name}: 行数 {len(records)} が metrics.json の {expected_rows[name]} と違う"
            )
        rows.extend(records)
    counts: Counter[tuple[str, str, int]] = Counter()
    seen_ids: set[str] = set()
    for record in rows:
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            raise R8FitError(f"{record.get('item_id')}: 欄が無い {missing}")
        item_id = record["item_id"]
        if item_id in seen_ids:
            raise R8FitError(f"item_id が重複している: {item_id}")
        seen_ids.add(item_id)
        polarity, theta, total = record["polarity"], record["threshold_offset"], record["t"]
        declared = polarity in POLARITIES and record["task_type"] in task_types
        if not declared or theta not in offsets:
            raise R8FitError(f"{item_id}: 極性・タスク型・θ が宣言の外にある")
        if record["threshold"] != t3_comparison.sweep_threshold(total, theta):
            raise R8FitError(f"{item_id}: 閾値が T = t + θ でない")
        if record["truth"] != t3_comparison.comparison_answer(total, polarity, record["threshold"]):
            raise R8FitError(f"{item_id}: truth が比較の真値と違う")
        if not isinstance(record["answer"], bool):
            raise R8FitError(f"{item_id}: answer が真偽値でない({record['answer']!r})")
        counts[(record["sweep_cell"], polarity, int(theta))] += 1
    expected_counts = {
        (cell, polarity, int(theta)): n
        for cell, by_polarity in sweep["n_items_by_cell"].items()
        for polarity, by_theta in by_polarity.items()
        for theta, n in by_theta.items()
    }
    if dict(counts) != expected_counts:
        raise R8FitError("(併合セル × 極性 × θ)の件数が metrics.json の n_items_by_cell と違う")
    return rows


@dataclass(frozen=True)
class SweepRun:
    """検査を通した掃引の run 1 本(記録と、当てはめ・補正に要る宣言)。

    答える問い: 「この掃引の run は、どの腕で、どの θ の水準を、どのタスク型について測ったか」
    """

    run_dir: Path
    metrics: Mapping[str, Any]
    config: Mapping[str, Any]
    task_types: tuple[str, ...]
    far: FarOffsets
    records: tuple[Mapping[str, Any], ...]

    @property
    def header(self) -> dict[str, Any]:
        """報告の先頭に置く来歴(補正の前後で同じ)。**adapter を必ず並べる**(§4.6 読み3)。"""
        sweep = self.metrics["threshold_sweep"]
        return {
            "run_id": self.metrics["run_id"],
            "condition": self.metrics.get("lesion_condition"),
            "seed": self.metrics.get("seed"),
            "adapter": self.metrics.get("adapter"),
            "pool_id": (self.metrics.get("pool") or {}).get("pool_id"),
            "arm": sweep["arm"],
            "threshold_offsets": list(sweep["threshold_offsets"]),
            "task_types": list(self.task_types),
            "far_offsets": self.far.as_dict(),
        }


def load_sweep_run(metrics_path: Path) -> SweepRun:
    """掃引の run を読み、記録が宣言とそろっていることを確かめる。

    答える問い: 「この run は I4 の記録の経路が書いた掃引の run か。記録は宣言どおりか」

    **`kind` が違えば止める。**補正前の表と補正後の表が同じ検査を 2 度書かないよう、
    読み込みと検査はここ 1 か所にした(PLAN-026 §4.12 読み1)。
    """
    run_dir = metrics_path.parent
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("kind") != THRESHOLD_SWEEP_KIND:
        raise R8FitError(
            f"{run_dir.name}: kind が {THRESHOLD_SWEEP_KIND!r} でない({metrics.get('kind')!r})。"
            "R8 の当てはめは I4 の記録の経路が書いた run だけを読む"
        )
    sweep = metrics["threshold_sweep"]
    task_types = tuple(sweep["task_types"])
    records = check_records(read_sweep_predictions(run_dir, list(task_types)), sweep)
    config = load_config(run_dir / CONFIG_FILENAME)
    return SweepRun(
        run_dir=run_dir,
        metrics=metrics,
        config=config,
        task_types=task_types,
        far=far_offsets_from_config(config),
        records=tuple(records),
    )


def sweep_gaps(records: Sequence[Mapping[str, Any]], run_name: str) -> dict[str, float]:
    """掃引の行の `item_id -> yes_logp − no_logp`(**補正前**)。

    答える問い: 「この掃引の各項目で、モデルは Yes と No にどれだけの差で倒れたか」

    値は predictions の行の値そのもの(ADR-084 決定3)。**欄が無い行・差が数でない行・
    item_id の重複は止める** —— I10 より前の run を「近接同点 0 件」と読ませない。
    補正後の差は `calibrated.calibrated_gaps` である(ADR-086 決定2)。
    """
    gaps: dict[str, float] = {}
    for record in records:
        item_id = record["item_id"]
        missing = [f for f in (YES_LOGP_FIELD, NO_LOGP_FIELD) if record.get(f) is None]
        if missing:
            raise R8FitError(
                f"{run_name}: 掃引の行 {item_id!r} に {missing} が無い。"
                "近接同点の幅を宣言した run は、強制選択の値そのものを行に持つはずである"
            )
        if item_id in gaps:
            raise R8FitError(f"{run_name}: 掃引の行 {item_id!r} が 2 つある")
        gap = float(record[YES_LOGP_FIELD]) - float(record[NO_LOGP_FIELD])
        if np.isnan(gap):
            raise R8FitError(f"{run_name}: 掃引の行 {item_id!r} の yes_logp − no_logp が数でない")
        gaps[item_id] = gap
    return gaps


def near_tie_table(
    records: Sequence[Mapping[str, Any]],
    gaps: Mapping[str, float],
    *,
    task_types: Sequence[str],
    far: FarOffsets,
    margin: float,
) -> list[dict[str, Any]]:
    """§7 の感度の行を掃引に置く(ADR-086 決定3)。**セルごと・遠いオフセットの側ごと。**

    答える問い: 「batch で分類が揺れうる近接同点を除くと、§5 (iv) の correct はどう読めるか」

    近接同点は `|差| ≤ margin`(境界を含む。ADR-079 決定8 と同じ数え方)。差は**呼び出し側が
    渡す** —— 補正前は `sweep_gaps`、補正後は `calibrated.calibrated_gaps`(ADR-086 決定2)。
    **合否には使わない**(§5 の値も判定の単位も変えない)。除いて 0 件なら correct は null。
    """
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault((record["task_type"], record["coverage"]), []).append(record)
    table: list[dict[str, Any]] = []
    for task, coverage in _cell_order(task_types):
        cell_records = grouped.get((task, coverage), [])
        if not cell_records:
            continue
        sides: dict[str, Any] = {}
        for side in SIDES:
            subset = [r for r in cell_records if far.side_of(int(r["threshold_offset"])) == side]
            if not subset:
                raise R8FitError(
                    f"({task}, {coverage}) の {side} 側に項目が 1 つも無い。"
                    "境界と run の θ の水準が合っていない"
                )
            missing = [r["item_id"] for r in subset if r["item_id"] not in gaps]
            if missing:
                raise R8FitError(f"({task}, {coverage}) の行 {missing[:3]} に Yes と No の差が無い")
            kept = [r for r in subset if abs(gaps[r["item_id"]]) > margin]
            sides[side] = {
                "n": len(subset),
                "n_near_tie": len(subset) - len(kept),
                "without_near_tie": (
                    correct_block(kept)
                    if kept
                    else {"n": 0, "n_correct": None, "correct_rate": None}
                ),
            }
        table.append({"task_type": task, "coverage": coverage, "sides": sides})
    return table


def near_tie_report(
    run: SweepRun,
    records: Sequence[Mapping[str, Any]],
    gaps_of: Callable[[Sequence[Mapping[str, Any]], str], Mapping[str, float]],
) -> dict[str, Any] | None:
    """幅を宣言した run の感度の行(宣言が無ければ None)。

    答える問い: 「この run は近接同点の幅を宣言しているか。しているなら感度の行はどうなるか」

    幅は run の `config.yaml` の `gonogo.near_tie_margin`(ADR-085 決定4。#1・#2 の閾値と
    同じブロックにあるので、読む関数も `gonogo.py` の 1 つにする)。`gaps_of` は差の引き手で、
    **補正の前後を暗黙にしない** —— 補正前は `sweep_gaps`、補正後は `calibrated_gaps`。
    """
    run_name = run.run_dir.name
    margin = near_tie_margin_from_config(run.config, run_name)
    if margin is None:
        return None
    return {
        "margin": margin,
        "note": NEAR_TIE_NOTE,
        "cells": near_tie_table(
            records,
            gaps_of(records, run_name),
            task_types=run.task_types,
            far=run.far,
            margin=margin,
        ),
    }


def run_report(metrics_path: Path) -> dict[str, Any]:
    """1 つの掃引の run について当てはめの表を組む(幅を宣言した run では感度の行も)。"""
    run = load_sweep_run(metrics_path)
    return {
        **run.header,
        **fit_records(run.records, task_types=run.task_types, far=run.far),
        "near_tie": near_tie_report(run, run.records, sweep_gaps),
    }


def calibrated_run_report(metrics_path: Path, lookup: calibrated.BiasLookup) -> dict[str, Any]:
    """1 つの掃引の run に (c) の補正を引いた当てはめの表(PLAN-026 §4.12 読み4・読み7)。

    答える問い: 「内容のない入力の偏りを引くと、この掃引の遠いオフセットの correct はどうなるか」

    差し替えるのは `answer` だけで、`truth`・θ・セルは変わらない。**★F138 の守り** ——
    較正は極性ごとに別の定数を引くので固定オフセットでは定数戦略に寄せても correct が
    上がりうる。和を読んだかどうかは、この表の遠いオフセットの correct で見る(§3.5)。
    近接同点は**補正後の差**で数える(ADR-086 決定2)。
    """
    run = load_sweep_run(metrics_path)
    run_name = run.run_dir.name
    calibrated.check_arm(lookup, run.metrics, run.config, run_name)
    adjusted = calibrated.calibrated_sweep_records(run.records, lookup, run_name=run_name)
    return {
        **run.header,
        "calibration": lookup.record(),
        **fit_records(adjusted, task_types=run.task_types, far=run.far),
        "near_tie": near_tie_report(run, adjusted, calibrated.calibrated_gaps),
        "note": calibrated.NOT_A_CANDIDATE_NOTE,
    }


# --------------------------------------------------------------------------
# Δ̂(2 つの run の差)
# --------------------------------------------------------------------------

# Δ̂ の基準の条件(ADR-030 決定6: `Δ̂ = θ*(条件) − θ*(ident)`)。
IDENT_CONDITION = "ident"


def delta_hat_table(report: Mapping[str, Any], ident_report: Mapping[str, Any]) -> list[dict]:
    """セルごとの `Δ̂ = θ*(条件) − θ*(ident)`(混ぜた当てはめ。ADR-030 決定6)。

    答える問い: 「この条件の交差点は、ident の交差点から θ でどれだけ動いたか」

    **どちらかのセルが除外なら None**(理由の分類を添える)。腕・θ の水準・タスク型・セルが
    2 つの run で違えば止める。**どの run とどの ident の run を組むか(シードの対応)はここで決めない**
    (PLAN-026 §4.6 読み3)。
    """
    if ident_report.get("condition") != IDENT_CONDITION:
        raise R8FitError(
            f"Δ̂ の基準は ident の run である(ADR-030 決定6)。渡された run の条件は "
            f"{ident_report.get('condition')!r}"
        )
    for key in ("arm", "threshold_offsets", "task_types"):
        if report[key] != ident_report[key]:
            raise R8FitError(f"Δ̂ の 2 つの run で {key} が違う: {report[key]} / {ident_report[key]}")
    reference = {(cell["task_type"], cell["coverage"]): cell for cell in ident_report["cells"]}
    if set(reference) != {(cell["task_type"], cell["coverage"]) for cell in report["cells"]}:
        raise R8FitError("Δ̂ の 2 つの run でセルが違う")
    table = []
    for cell in report["cells"]:
        own = cell["crossing"][MIXED]
        base = reference[(cell["task_type"], cell["coverage"])]["crossing"][MIXED]
        both = own["included"] and base["included"]
        table.append(
            {
                "task_type": cell["task_type"],
                "coverage": cell["coverage"],
                "theta_star": own["theta_star"],
                "theta_star_ident": base["theta_star"],
                "kind": own["kind"],
                "kind_ident": base["kind"],
                "delta_hat": own["theta_star"] - base["theta_star"] if both else None,
            }
        )
    return table


def build_report(
    metrics_paths: Sequence[Path], *, ident_path: Path | None = None
) -> dict[str, Any]:
    """渡された run ごとに表を組む(`--ident-run` があれば Δ̂ も)。"""
    runs = [run_report(path) for path in metrics_paths]
    if ident_path is not None:
        ident = run_report(ident_path)
        for report in runs:
            report["delta_hat"] = {
                "ident_run_id": ident["run_id"],
                "cells": delta_hat_table(report, ident),
            }
    return {
        "created_at": utc_now().isoformat(),
        "note": (
            "値を出すだけで判断しない。PLAN-026 §5 の合否は I11、§6 の分岐の読みは人間(CLAUDE.md §8)。"
            "揃え方 (a)(y = 1 ⇔ gt で No / lt で Yes。ADR-079 決定1)。階段は除外せず交差点を (L + U) / 2 に"
            "置く(PLAN-026 §3.2.1.1 / ADR-081)。§5 (iv) の判定の単位はセル(ADR-081 決定3)。"
            "pool_id: pilot の数値は主張の根拠に使わない(PLAN-001 §4.6 規則4)"
        ),
        "runs": runs,
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _crossing_text(crossing: Mapping[str, Any]) -> str:
    kind = crossing["kind"]
    if kind == FIT:
        return f"fit θ*={_number(crossing['theta_star'])} β1={_number(crossing['beta1'])}"
    if kind == STAIRCASE:
        bounds = f"[L={crossing['lower']}, U={crossing['upper']}]"
        return f"階段 θ*={_number(crossing['theta_star'])} {bounds}"
    return f"除外({kind})"


def _near_tie_lines(near_tie: Mapping[str, Any] | None) -> list[str]:
    """掃引の感度の行(幅を宣言していない run では空)。**合否には使わない。**"""
    if near_tie is None:
        return []
    lines = [
        f"近接同点(|差| ≤ {near_tie['margin']})を除いた遠いオフセットの correct"
        "(ADR-086 決定3。合否には使わない)"
    ]
    for cell in near_tie["cells"]:
        low, high = cell["sides"][LOW], cell["sides"][HIGH]
        lines.append(
            f"  {cell['task_type']:<4} {cell['coverage']:<17} "
            f"低い側 同点={low['n_near_tie']}/{low['n']} "
            f"correct={_number(low['without_near_tie']['correct_rate'])} "
            f"高い側 同点={high['n_near_tie']}/{high['n']} "
            f"correct={_number(high['without_near_tie']['correct_rate'])}"
        )
    return lines


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人間が読む表(標準出力)。**除外件数を必ず出す。**"""
    lines: list[str] = [report["note"]]
    for run in report["runs"]:
        far = run["far_offsets"]
        # adapter を必ず並べる: adapter = null の run の condition は config の値のままで、
        # FT を受けたことを意味しない(素のモデルの R8 の run でも condition は p2 と出る)
        lines.append(
            f"=== run {run['run_id']}(condition={run['condition']} / adapter={run['adapter']} / "
            f"seed={run['seed']} / pool_id={run['pool_id']} / 腕={run['arm']})"
        )
        lines.append("交差点(混ぜた / gt / lt)と極性の開き θ*_lt − θ*_gt")
        for cell in run["cells"]:
            crossing = cell["crossing"]
            lines.append(
                f"  {cell['task_type']:<4} {cell['coverage']:<17} n={cell['n']:<5} "
                f"混ぜた: {_crossing_text(crossing[MIXED])} | "
                f"gt: {_crossing_text(crossing[t3_comparison.GT])} | "
                f"lt: {_crossing_text(crossing[t3_comparison.LT])} | "
                f"開き={_number(cell['polarity_gap'])}"
            )
        lines.append("除外件数(セルの数。ADR-030 決定6。階段は除外ではない)")
        for scope, block in run["exclusions"].items():
            kinds = " ".join(f"{kind}={count}" for kind, count in block["by_kind"].items())
            lines.append(
                f"  {scope:<5} {kinds} | β1≤0 の合計={block['beta1_nonpositive_total']} "
                f"除外の合計={block['excluded_total']} / {block['n_cells']}"
            )
        lines.append(
            f"遠いオフセットの correct(θ ≤ {far['low_max']} / θ ≥ {far['high_min']}。"
            f"境界は {far['source']} から。判定の単位はセル)"
        )
        for cell in run["cells"]:
            low, high = cell["far_offset_correct"][LOW], cell["far_offset_correct"][HIGH]
            lines.append(
                f"  {cell['task_type']:<4} {cell['coverage']:<17} "
                f"低い側 n={low['n']:<4} correct={_number(low['correct_rate'])} "
                f"高い側 n={high['n']:<4} correct={_number(high['correct_rate'])}"
            )
        for row in run["far_offset_correct_by_task_type"]:
            lines.append(
                f"  {row['task_type']:<4} (タスク型でまとめた記述) "
                f"低い側 n={row[LOW]['n']:<4} correct={_number(row[LOW]['correct_rate'])} "
                f"高い側 n={row[HIGH]['n']:<4} correct={_number(row[HIGH]['correct_rate'])}"
            )
        lines.extend(_near_tie_lines(run.get("near_tie")))
        if "delta_hat" in run:
            lines.append(f"Δ̂ = θ*(この run) − θ*(ident run {run['delta_hat']['ident_run_id']})")
            for row in run["delta_hat"]["cells"]:
                lines.append(
                    f"  {row['task_type']:<4} {row['coverage']:<17} Δ̂={_number(row['delta_hat'])} "
                    f"({row['kind']} / ident {row['kind_ident']})"
                )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R8(閾値掃引)の当てはめ(PLAN-026 I5)")
    parser.add_argument("--runs", required=True, nargs="+", help="掃引の run の glob(複数可)")
    parser.add_argument(
        "--ident-run", default=None, help="Δ̂ の基準にする ident の掃引の run(省略すると Δ̂ を出さない)"
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None, help=f"指定すると {OUTPUT_FILENAME} を書く"
    )
    args = parser.parse_args(argv)

    ident_path = None
    if args.ident_run is not None:
        ident_paths = expand_metrics_paths([args.ident_run])
        if len(ident_paths) != 1:
            raise R8FitError(f"--ident-run は 1 つの run に当たらなければならない: {ident_paths}")
        ident_path = ident_paths[0]
    report = build_report(expand_metrics_paths(args.runs), ident_path=ident_path)
    for line in report_lines(report):
        print(line)
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / OUTPUT_FILENAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"-> {args.out_dir / OUTPUT_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
