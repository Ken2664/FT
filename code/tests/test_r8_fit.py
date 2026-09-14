"""R8(閾値掃引)の当てはめ(PLAN-026 I5。§3.2.1.1 / ADR-081)。

答える問い: 「揃え方 (a) と『階段の位置』の定義で、内部の値 `t + Δ` のモデルの交差点が `Δ` に出て、
旧い揃え方では出ないか。除外件数と遠いオフセットの correct が出るか」

**ここに出る数値は実験結果ではない。**すべて合成の応答(決定的なモデル)か組合せ論的な件数である。
**モデルの重みは 1 度も読まない**(採点器を差し替える。`test_threshold_sweep_run.py` と同じ)。

ここで固定する最重要の性質:
  - **§3.2.1 の算術の例**: 内部の値 `t + Δ` の決定的なモデルで、gt の切り替わり `Δ − 0.5`・lt `Δ + 0.5`・
    混ぜた交差点 `Δ`(どれも階段。向きは正)。極性の開きは 1。`Δ̂ = 2 − 0 = 2`
  - **旧い揃え方(lt の θ の符号を反転・`y` = Yes)では `Δ̂ ≈ 0` で、しかも両方とも `β1 ≤ 0` の除外に落ちる**
  - 分類は 片側だけ → 階段 → 逆向きの階段 → 当てはめ の順。**階段は除外ではない**。重なりが 1 件でもあれば階段ではない
  - 除外件数が分類ごとに出る。遠いオフセットの correct が低い側・高い側で別に出る(★F138 の定数戦略は低い側で 0)
  - I4 の記録の経路が書いた run をそのまま読み、記録が metrics.json と食い違えば止まる
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from code import artifacts
from code.analysis import r8_fit
from code.analysis.aggregate import METRICS_FILENAME
from code.config import load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import run
from code.eval.battery import t3_comparison
from code.eval.forced_choice import ForcedChoice, ForcedChoiceScorer, choose_from_logprobs
from code.tests.test_threshold_sweep_run import (
    CANDIDATE_IDS,
    PILOT_CONFIG,
    R8_CONFIG,
    forbidden,
    stub_capture,
    sweep_config,
    write_config,
)

GT, LT = t3_comparison.GT, t3_comparison.LT
TASK_TYPES: tuple[str, ...] = (t3_comparison.T3, t3_comparison.T1B)
R8_OFFSETS: list[int] = load_config(R8_CONFIG)["eval"]["threshold_sweep"]["offsets"]["r8"]
S_OFFSETS: list[int] = load_config(R8_CONFIG)["eval"]["threshold_sweep"]["offsets"]["s"]
FAR = r8_fit.far_offsets_from_config(load_config(PILOT_CONFIG))

# 合成の組の和(意味の無い値。ジッターの 3 値が同数になるよう 3 の倍数の個数にする)
TOTALS: tuple[int, ...] = (40, 75, 101, 130, 166, 190)
SYMMETRIC_JITTER: tuple[int, ...] = (-1, 0, 1)

# R8 の 1 セル(タスク型 × 既知性)の件数(組合せ論的。PLAN-026 §3.2.1.1・§5 (iv))
N_PER_FIT_CELL = 1360
N_FAR_LOW_PER_CELL = 160
N_FAR_HIGH_PER_CELL = 880

# 合成データで交差点を比べる許容幅(窓の端の非対称でわずかにずれる分。scratchpad で確かめた量より広い)
APPROX = 0.05


# --------------------------------------------------------------------------
# 合成の記録
# --------------------------------------------------------------------------


def model_answer(total: int, polarity: str, threshold: int, *, shift: int) -> bool:
    """内部の値 `t + shift` を閾値と比べて答える決定的なモデル(§3.2.1 の算術の例)。"""
    return t3_comparison.comparison_answer(total + shift, polarity, threshold)


def model_records(
    delta: int,
    *,
    jitter: Sequence[int] = (0,),
    offsets: Sequence[int] = R8_OFFSETS,
    answer_rule: Any = None,
) -> list[dict[str, Any]]:
    """合成の掃引の記録。組 `i` の内部の値は `t + delta + jitter[i % len(jitter)]`。

    `answer_rule(total, polarity, threshold) -> bool` を渡すと、その規則で答える(定数戦略など)。
    """
    records = []
    for task in TASK_TYPES:
        for coverage in MAIN_COVERAGE_LEVELS:
            for index, total in enumerate(TOTALS):
                shift = delta + jitter[index % len(jitter)]
                for polarity in sweep_pool.POLARITIES:
                    for theta in offsets:
                        threshold = t3_comparison.sweep_threshold(total, theta)
                        answer = (
                            answer_rule(total, polarity, threshold)
                            if answer_rule is not None
                            else model_answer(total, polarity, threshold, shift=shift)
                        )
                        records.append(
                            {
                                "item_id": f"{task}-{coverage}-{index}-{polarity}-{theta}",
                                "task_type": task,
                                "coverage": coverage,
                                "polarity": polarity,
                                "threshold_offset": theta,
                                "answer": answer,
                                "truth": t3_comparison.comparison_answer(
                                    total, polarity, threshold
                                ),
                            }
                        )
    return records


def synthetic_report(delta: int, *, condition: str, jitter: Sequence[int] = (0,)) -> dict:
    return {
        "run_id": f"synthetic_{condition}_{delta}",
        "condition": condition,
        "arm": "r8",
        "threshold_offsets": list(R8_OFFSETS),
        "task_types": list(TASK_TYPES),
        **r8_fit.fit_records(model_records(delta, jitter=jitter), task_types=TASK_TYPES, far=FAR),
    }


def counts_of(pairs: Mapping[int, tuple[int, int]]) -> r8_fit.ThetaCounts:
    """{θ: (y = 0 の数, y = 1 の数)} から畳んだ集計を作る。"""
    observations: list[tuple[int, int]] = []
    for theta, (zeros, ones) in pairs.items():
        observations += [(theta, 0)] * zeros + [(theta, 1)] * ones
    return r8_fit.theta_counts(observations)


def crossing(cell: Mapping[str, Any], scope: str) -> Mapping[str, Any]:
    return cell["crossing"][scope]


# --------------------------------------------------------------------------
# 揃え方と §3.2.1 の算術の例(I12)
# --------------------------------------------------------------------------


def test_aligned_response_marks_the_smaller_side() -> None:
    assert r8_fit.aligned_response(GT, False) == 1
    assert r8_fit.aligned_response(GT, True) == 0
    assert r8_fit.aligned_response(LT, True) == 1
    assert r8_fit.aligned_response(LT, False) == 0
    with pytest.raises(r8_fit.R8FitError):
        r8_fit.aligned_response("eq", True)


@pytest.mark.parametrize("delta", [0, 2, 11])
def test_the_arithmetic_example_of_3_2_1_holds_in_every_cell(delta: int) -> None:
    """gt の切り替わり Δ − 0.5・lt Δ + 0.5・混ぜた交差点 Δ(どれも向きが正の階段)。開きは 1。"""
    report = r8_fit.fit_records(model_records(delta), task_types=TASK_TYPES, far=FAR)
    assert len(report["cells"]) == len(TASK_TYPES) * len(MAIN_COVERAGE_LEVELS)
    for cell in report["cells"]:
        mixed, gt, lt = (crossing(cell, scope) for scope in r8_fit.FIT_SCOPES)
        assert (mixed["kind"], mixed["theta_star"]) == (r8_fit.STAIRCASE, delta)
        assert (mixed["lower"], mixed["upper"]) == (delta, delta)
        assert (gt["kind"], gt["theta_star"]) == (r8_fit.STAIRCASE, delta - 0.5)
        assert (gt["lower"], gt["upper"]) == (delta - 1, delta)
        assert (lt["kind"], lt["theta_star"]) == (r8_fit.STAIRCASE, delta + 0.5)
        assert (lt["lower"], lt["upper"]) == (delta, delta + 1)
        assert all(block["included"] for block in (mixed, gt, lt))
        assert cell["polarity_gap"] == 1.0
    for scope in r8_fit.FIT_SCOPES:
        block = report["exclusions"][scope]
        assert block["by_kind"][r8_fit.STAIRCASE] == block["n_cells"] == 6
        assert block["excluded_total"] == 0


def test_delta_hat_recovers_the_shift_of_the_deterministic_model() -> None:
    table = r8_fit.delta_hat_table(
        synthetic_report(2, condition="p2"), synthetic_report(0, condition="ident")
    )
    assert [row["delta_hat"] for row in table] == [2.0] * 6


def test_overlapping_responses_go_through_the_fit_with_a_positive_slope() -> None:
    """組ごとに内部の値が ±1 ずれるモデル: 応答が重なるので当てはめに入り、`β1 > 0`・交差点は Δ の近く。"""
    reports = {
        delta: synthetic_report(delta, condition=condition, jitter=SYMMETRIC_JITTER)
        for delta, condition in ((0, "ident"), (2, "p2"))
    }
    for delta, report in reports.items():
        for cell in report["cells"]:
            mixed = crossing(cell, r8_fit.MIXED)
            assert mixed["kind"] == r8_fit.FIT and mixed["beta1"] > 0
            assert mixed["theta_star"] == pytest.approx(delta, abs=APPROX)
            assert crossing(cell, GT)["theta_star"] == pytest.approx(delta - 0.5, abs=APPROX)
            assert crossing(cell, LT)["theta_star"] == pytest.approx(delta + 0.5, abs=APPROX)
    table = r8_fit.delta_hat_table(reports[2], reports[0])
    assert all(row["delta_hat"] == pytest.approx(2.0, abs=APPROX) for row in table)


def old_alignment_counts(delta: int) -> r8_fit.ThetaCounts:
    """ADR-030 決定6 の文面どおりの揃え方: `y` = Yes、lt の θ の符号を反転する(★F141)。"""
    records = [r for r in model_records(delta) if r["task_type"] == TASK_TYPES[0]]
    records = [r for r in records if r["coverage"] == MAIN_COVERAGE_LEVELS[0]]
    return r8_fit.theta_counts(
        (
            record["threshold_offset"] if record["polarity"] == GT else -record["threshold_offset"],
            int(record["answer"]),
        )
        for record in records
    )


def old_alignment_theta(fit: r8_fit.Crossing) -> float:
    """除外に落ちた当てはめからも、比べるために交差点の値を取り出す。"""
    if fit.kind == r8_fit.REVERSED_STAIRCASE:
        assert fit.lower is not None and fit.upper is not None
        return (fit.lower + fit.upper) / 2
    assert fit.beta0 is not None and fit.beta1 is not None
    return -fit.beta0 / fit.beta1


def test_the_old_alignment_does_not_identify_delta() -> None:
    """旧い揃え方では交差点が Δ に依らず(Δ̂ ≈ 0)、しかも両方とも `β1 ≤ 0` の除外に落ちる。"""
    fits = {delta: r8_fit.locate_crossing(old_alignment_counts(delta)) for delta in (0, 2)}
    assert fits[0].kind == r8_fit.REVERSED_STAIRCASE
    assert fits[2].kind == r8_fit.BETA1_NONPOSITIVE and fits[2].beta1 < 0
    for fit in fits.values():
        assert fit.kind in r8_fit.BETA1_NONPOSITIVE_KINDS and not fit.included
    assert old_alignment_theta(fits[0]) == -0.5
    assert old_alignment_theta(fits[2]) - old_alignment_theta(fits[0]) == pytest.approx(
        0.0, abs=APPROX
    )


# --------------------------------------------------------------------------
# 分類(PLAN-026 §3.2.1.1 の 1〜4)
# --------------------------------------------------------------------------

def staircase(switch_at: int, *, zeros: int = 4, ones: int = 4) -> dict[int, tuple[int, int]]:
    """θ < switch_at はすべて 0、θ > switch_at はすべて 1、θ = switch_at は混ざる。"""
    table = {}
    for theta in R8_OFFSETS:
        if theta < switch_at:
            table[theta] = (zeros + ones, 0)
        elif theta > switch_at:
            table[theta] = (0, zeros + ones)
        else:
            table[theta] = (zeros, ones)
    return table


def logistic_table(slope: float, center: float, *, n: int = 40) -> dict[int, tuple[int, int]]:
    """θ ごとに round(n · P) 件を 1 にする(応答の重なるデータ)。"""
    table = {}
    for theta in R8_OFFSETS:
        ones = round(n / (1 + math.exp(-slope * (theta - center))))
        table[theta] = (n - ones, ones)
    return table


CLASSIFICATION_CASES: dict[str, tuple[dict[int, tuple[int, int]], str, float | None]] = {
    "one_sided_all_0": ({theta: (8, 0) for theta in R8_OFFSETS}, r8_fit.ONE_SIDED_ZERO, None),
    "one_sided_all_1": ({theta: (0, 8) for theta in R8_OFFSETS}, r8_fit.ONE_SIDED_ONE, None),
    "complete_separation": (staircase(2, zeros=8, ones=0), r8_fit.STAIRCASE, 2.5),
    "quasi_complete_separation": (staircase(2, zeros=3, ones=5), r8_fit.STAIRCASE, 2.0),
    "reversed_staircase": (
        {theta: (0, 8) if theta < 4 else (8, 0) for theta in R8_OFFSETS},
        r8_fit.REVERSED_STAIRCASE,
        None,
    ),
    "increasing_overlap": (logistic_table(0.8, 4.0), r8_fit.FIT, None),
    "decreasing_overlap": (logistic_table(-0.8, 4.0), r8_fit.BETA1_NONPOSITIVE, None),
    "flat": ({theta: (4, 4) for theta in R8_OFFSETS}, r8_fit.BETA1_NONPOSITIVE, None),
}


@pytest.mark.parametrize("case", sorted(CLASSIFICATION_CASES))
def test_each_branch_of_the_definition(case: str) -> None:
    table, kind, theta_star = CLASSIFICATION_CASES[case]
    result = r8_fit.locate_crossing(counts_of(table))
    assert result.kind == kind
    assert result.included == (kind in r8_fit.INCLUDED_KINDS)
    if theta_star is not None:
        assert result.theta_star == theta_star
    if kind == r8_fit.STAIRCASE:
        assert result.beta1 is None and result.lower is not None and result.upper is not None
    if kind == r8_fit.FIT:
        assert result.beta1 is not None and result.beta1 > 0
        assert result.theta_star == pytest.approx(4.0, abs=0.1)
    if kind == r8_fit.BETA1_NONPOSITIVE:
        assert result.theta_star is None and result.beta1 is not None and result.beta1 <= 0
    if kind in r8_fit.EXCLUDED_KINDS:
        assert result.theta_star is None


def test_staircase_position_on_the_s_levels_spans_the_gap() -> None:
    table = {theta: ((8, 0) if theta < 0 else (0, 8)) for theta in S_OFFSETS}
    result = r8_fit.locate_crossing(counts_of(table))
    assert (result.kind, result.lower, result.upper, result.theta_star) == (
        r8_fit.STAIRCASE,
        -2,
        3,
        0.5,
    )


def test_one_overlapping_item_is_not_a_staircase() -> None:
    """重なりが 1 件でもあれば階段ではなく当てはめに入る(単調でない応答も同じ)。"""
    table = staircase(2, zeros=8, ones=0)
    table[-3] = (7, 1)
    result = r8_fit.locate_crossing(counts_of(table))
    assert result.kind == r8_fit.FIT and result.beta1 is not None and result.beta1 > 0
    non_monotone = logistic_table(0.8, 4.0)
    non_monotone[8], non_monotone[9] = non_monotone[9], non_monotone[8]
    assert r8_fit.locate_crossing(counts_of(non_monotone)).kind == r8_fit.FIT


def test_nonconvergence_is_excluded_under_its_own_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r8_fit, "NEWTON_MAX_ITERATIONS", 1)
    result = r8_fit.locate_crossing(counts_of(logistic_table(0.8, 4.0)))
    assert result.kind == r8_fit.NONCONVERGENT and not result.included
    assert result.theta_star is None


def test_fit_logistic_matches_the_closed_form_on_two_levels() -> None:
    """2 水準なら飽和模型で、最尤推定は各水準の経験ロジットに一致する(独立な検算)。"""
    fit = r8_fit.fit_logistic(r8_fit.ThetaCounts(thetas=(0, 1), n=(10, 10), k=(2, 7)))
    assert fit.converged
    assert fit.beta0 == pytest.approx(logit(0.2), abs=1e-9)
    assert fit.beta1 == pytest.approx(logit(0.7) - logit(0.2), abs=1e-9)


def logit(probability: float) -> float:
    return math.log(probability / (1 - probability))


def test_fit_logistic_solves_the_score_equations() -> None:
    counts = counts_of(logistic_table(0.6, 3.3, n=37))
    fit = r8_fit.fit_logistic(counts)
    theta = np.asarray(counts.thetas, dtype=float)
    probability = 1 / (1 + np.exp(-(fit.beta0 + fit.beta1 * theta)))
    residual = np.asarray(counts.k) - np.asarray(counts.n) * probability
    assert fit.converged
    assert abs(residual.sum()) < 1e-8 and abs((residual * theta).sum()) < 1e-8


def test_theta_counts_rejects_what_cannot_be_fitted() -> None:
    with pytest.raises(r8_fit.R8FitError):
        r8_fit.theta_counts([(0, 2)])
    with pytest.raises(r8_fit.R8FitError):
        r8_fit.theta_counts([(0, 0), (0, 1)])  # θ の水準が 1 つ


# --------------------------------------------------------------------------
# 遠いオフセットの correct と Δ̂ の検査
# --------------------------------------------------------------------------


def test_far_offsets_come_from_the_s_levels() -> None:
    for path in (PILOT_CONFIG, R8_CONFIG):
        far = r8_fit.far_offsets_from_config(load_config(path))
        assert (far.low_max, far.high_min) == (-2, 3)
    config = load_config(R8_CONFIG)
    config["eval"]["threshold_sweep"]["offsets"]["s"] = [-3, 0, 3]
    with pytest.raises(r8_fit.R8FitError):
        r8_fit.far_offsets_from_config(config)
    del config["eval"]["threshold_sweep"]["offsets"]["s"]
    with pytest.raises(r8_fit.R8FitError):
        r8_fit.far_offsets_from_config(config)


STRATEGIES = {
    "truth": (None, 1.0, 1.0),
    # ★F138 の定数戦略: gt → No / lt → Yes。固定オフセットの項目では correct = 1 と区別できない
    "gt_no_lt_yes": (lambda total, polarity, threshold: polarity == LT, 0.0, 1.0),
    "always_yes": (lambda total, polarity, threshold: True, 0.5, 0.5),
}


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_far_offset_correct_is_reported_by_side_and_cell(name: str) -> None:
    rule, low, high = STRATEGIES[name]
    report = r8_fit.fit_records(model_records(0, answer_rule=rule), task_types=TASK_TYPES, far=FAR)
    n_low = len(TOTALS) * 2 * sum(1 for theta in R8_OFFSETS if theta <= FAR.low_max)
    n_high = len(TOTALS) * 2 * sum(1 for theta in R8_OFFSETS if theta >= FAR.high_min)
    for cell in report["cells"]:
        block = cell["far_offset_correct"]
        assert (block[r8_fit.LOW]["n"], block[r8_fit.HIGH]["n"]) == (n_low, n_high)
        assert block[r8_fit.LOW]["correct_rate"] == low
        assert block[r8_fit.HIGH]["correct_rate"] == high
    for row in report["far_offset_correct_by_task_type"]:
        assert row[r8_fit.LOW]["n"] == 3 * n_low
        assert row[r8_fit.LOW]["correct_rate"] == low


def test_constant_strategy_is_one_sided_and_counted() -> None:
    """gt → No / lt → Yes はすべて y = 1。片側だけとして除外し、件数に出る。"""
    rule = STRATEGIES["gt_no_lt_yes"][0]
    report = r8_fit.fit_records(model_records(0, answer_rule=rule), task_types=TASK_TYPES, far=FAR)
    block = report["exclusions"][r8_fit.MIXED]
    assert block["by_kind"][r8_fit.ONE_SIDED_ONE] == block["excluded_total"] == 6


def test_delta_hat_is_none_when_either_cell_is_excluded() -> None:
    far_shift = max(R8_OFFSETS) + 1  # 切り替わりが窓の外 → すべて y = 0
    table = r8_fit.delta_hat_table(
        synthetic_report(far_shift, condition="p2"), synthetic_report(0, condition="ident")
    )
    assert all(row["delta_hat"] is None for row in table)
    assert {row["kind"] for row in table} == {r8_fit.ONE_SIDED_ZERO}


def test_delta_hat_refuses_a_wrong_reference() -> None:
    ident = synthetic_report(0, condition="ident")
    with pytest.raises(r8_fit.R8FitError, match="ident"):
        r8_fit.delta_hat_table(ident, synthetic_report(2, condition="p2"))
    other_arm = {**ident, "arm": "s"}
    with pytest.raises(r8_fit.R8FitError, match="arm"):
        r8_fit.delta_hat_table(synthetic_report(2, condition="p2"), other_arm)


# --------------------------------------------------------------------------
# I4 の記録の経路が書いた run から(GPU の無い本実行)
# --------------------------------------------------------------------------


def shifted_model_scorer(config: Mapping[str, Any], shift: int) -> ForcedChoiceScorer:
    """文面からその項目を引き、内部の値 `t + shift` で答える採点器(判定規則は本物)。"""
    pool = run.load_threshold_sweep_pool(config)
    prompts = run.threshold_sweep_prompts(config, pool)
    if len(set(prompts.values())) != len(prompts):
        raise AssertionError("掃引の文面が項目を一意に決めない")
    item_of = {prompts[item.item_id]: item for item in pool.items}

    def scorer(batch: Sequence[str]) -> list[ForcedChoice]:
        choices = []
        for prompt in batch:
            item = item_of[prompt]
            says_yes = model_answer(
                t3_comparison.item_total(item),
                t3_comparison.polarity_of(item.category),
                int(item.params["threshold"]),
                shift=shift,
            )
            logprobs = [0.0, -1.0] if says_yes else [-1.0, 0.0]
            choices.append(choose_from_logprobs(logprobs, CANDIDATE_IDS))
        return choices

    return scorer


def execute_shifted(config: dict[str, Any], tmp: Path, *, shift: int) -> Path:
    config_path = write_config(config, tmp / "config.yaml")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", stub_capture)
        for name in ("classify", "metrics_by_reference_rule", "response_builder", "build_engines"):
            patch.setattr(run, name, forbidden(name))
        return run.execute_threshold_sweep(
            config,
            config_path=config_path,
            run_dir=tmp / "run",
            scorer=shifted_model_scorer(config, shift),
        )


@pytest.fixture(scope="module")
def sweep_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """R8 の掃引プールを tmp に書き、`t + 2`(p2)と `t`(ident)のモデルで本実行する。"""
    pilot = load_config(PILOT_CONFIG)
    root = tmp_path_factory.mktemp("battery")
    source = eval_pool.build(pilot)
    eval_pool.write_pool(sweep_pool.build_sweep_pool(pilot, source, "r8"), root / "r8")
    runs = {}
    for condition, shift in (("p2", 2), ("ident", 0)):
        config = sweep_config(root / "r8", arm="r8")
        config["lesion"]["condition"] = condition
        runs[condition] = execute_shifted(config, tmp_path_factory.mktemp(condition), shift=shift)
    return runs


def test_run_report_reads_what_the_sweep_route_wrote(sweep_runs: dict[str, Path]) -> None:
    report = r8_fit.run_report(sweep_runs["p2"] / METRICS_FILENAME)
    assert (report["arm"], report["pool_id"], report["condition"]) == ("r8", "pilot", "p2")
    assert report["far_offsets"]["low_max"] == -2 and report["far_offsets"]["high_min"] == 3
    assert len(report["cells"]) == 6
    for cell in report["cells"]:
        assert cell["n"] == N_PER_FIT_CELL
        assert crossing(cell, r8_fit.MIXED)["theta_star"] == 2.0
        assert crossing(cell, GT)["theta_star"] == 1.5
        assert crossing(cell, LT)["theta_star"] == 2.5
        low, high = (cell["far_offset_correct"][side] for side in r8_fit.SIDES)
        assert (low["n"], high["n"]) == (N_FAR_LOW_PER_CELL, N_FAR_HIGH_PER_CELL)
        assert low["correct_rate"] == high["correct_rate"] == 1.0
    assert report["exclusions"][r8_fit.MIXED]["by_kind"][r8_fit.STAIRCASE] == 6


def test_main_writes_the_report_with_delta_hat(
    sweep_runs: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = r8_fit.main(
        [
            "--runs",
            str(sweep_runs["p2"]),
            "--ident-run",
            str(sweep_runs["ident"]),
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    written = json.loads((tmp_path / r8_fit.OUTPUT_FILENAME).read_text(encoding="utf-8"))
    (only,) = written["runs"]
    assert [row["delta_hat"] for row in only["delta_hat"]["cells"]] == [2.0] * 6
    printed = capsys.readouterr().out
    assert "除外件数" in printed and "Δ̂" in printed


def tampered(run_dir: Path, tmp: Path, edit: Any) -> Path:
    """run を tmp に写し、T3 の predictions の行を `edit(rows)` で書き換える。"""
    copy = tmp / "tampered"
    shutil.copytree(run_dir, copy)
    path = copy / artifacts.PREDICTIONS_DIR / f"{run.threshold_sweep_predictions_name('t3')}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    edit(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return copy / METRICS_FILENAME


def _set(rows: list[dict], key: str, value: Any) -> None:
    rows[0][key] = value


TAMPERS = {
    "missing_row": lambda rows: rows.pop(),
    "threshold_not_t_plus_theta": lambda rows: _set(rows, "threshold", rows[0]["threshold"] + 1),
    "truth_flipped": lambda rows: _set(rows, "truth", not rows[0]["truth"]),
    "answer_not_bool": lambda rows: _set(rows, "answer", "Yes"),
    "moved_to_another_cell": lambda rows: _set(rows, "sweep_cell", "no_such_cell"),
    "duplicated_item": lambda rows: _set(rows, "item_id", rows[1]["item_id"]),
}


@pytest.mark.parametrize("case", sorted(TAMPERS))
def test_records_that_disagree_with_metrics_stop(
    sweep_runs: dict[str, Path], tmp_path: Path, case: str
) -> None:
    metrics_path = tampered(sweep_runs["p2"], tmp_path, TAMPERS[case])
    with pytest.raises(r8_fit.R8FitError):
        r8_fit.run_report(metrics_path)


def test_a_fixed_offset_run_is_refused(sweep_runs: dict[str, Path], tmp_path: Path) -> None:
    copy = tmp_path / "fixed"
    shutil.copytree(sweep_runs["p2"], copy)
    metrics_path = copy / METRICS_FILENAME
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["kind"] = "battery_eval"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    with pytest.raises(r8_fit.R8FitError, match="kind"):
        r8_fit.run_report(metrics_path)


def iter_cells(report: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    for cell in report["cells"]:
        yield cell["task_type"], cell["coverage"]


def test_cells_follow_the_task_type_and_coverage_order(sweep_runs: dict[str, Path]) -> None:
    report = r8_fit.run_report(sweep_runs["ident"] / METRICS_FILENAME)
    assert list(iter_cells(report)) == [
        (task, coverage) for task in TASK_TYPES for coverage in MAIN_COVERAGE_LEVELS
    ]
    assert all(crossing(cell, r8_fit.MIXED)["theta_star"] == 0.0 for cell in report["cells"])
