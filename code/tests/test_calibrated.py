"""(c) 内容のない入力による較正の偏りを順6b の記録に引く経路(PLAN-026 I11b。§4.12 / ADR-086)。

答える問い: 「較正の run が測った偏りを引くと、固定オフセットの4値と掃引の correct はどう変わるか。
腕と run が食い違ったときに止まるか」

**ここに出る数値は実験結果ではない。**すべて合成の応答(決定的な採点器)か組合せ論的な件数である。
**モデルの重みは 1 度も読まない。**

ここで固定する最重要の性質:
  - 偏りは (腕 × category × 並び)で引く。**前置きの腕では項目ごとに `order_index` 番目の並び**
    (PLAN-026 §4.9 読み7)。腕が違えば別の定数を引く
  - 補正で変わるのは二値群の `parsed` / `classification`(固定オフセット)と `answer`(掃引)だけ。
    **`yes_logp` / `no_logp` と数値群の行は 1 バイトも変わらない**(ADR-084 決定3)
  - **C3 の近接同点は補正後の差で数える**(ADR-086 決定2)。補正前の差の集合とは一致しない
  - 掃引の感度の行は**セル × 遠いオフセットの側**(ADR-086 決定3)。**合否には使わない**
  - 文面の組・前置きが腕と食い違えば止まる(ADR-085 決定3)。名前からは推測しない
  - 補正後の表に #1(`parse_fail`)は無い —— 補正は数値群を動かさない
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from code import artifacts
from code.analysis import calibrated, frame, gonogo, r8_fit
from code.analysis.aggregate import METRICS_FILENAME
from code.config import load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import calibration_run, preamble, run
from code.eval.battery import t3_comparison
from code.eval.calibration import CalibrationArm
from code.eval.forced_choice import ForcedChoice, ForcedChoiceScorer
from code.eval.scoring import classify
from code.tests.test_calibration import C_CONFIG, SOURCE_SYMBOLS
from code.tests.test_gonogo import (
    FIXED_ARMS,
    NEAR_TIE_MARGIN,
    execute_arm,
    planted_near_tie,
)
from code.tests.test_threshold_sweep_run import (
    PILOT_CONFIG,
    stub_capture,
    sweep_config,
    write_config,
)
from code.tests.test_top_k import with_filler_top_tokens

# 腕の名前(configs/exp_order6b_c.yaml の eval.calibration.arms)。
ARM_B0, ARM_PREAMBLE, ARM_D = "b0", "preamble", "d"
# 固定オフセットの腕の config 名 -> 較正の腕。
ARM_OF_RUN: dict[str, str] = {"pilot": ARM_B0, "preamble": ARM_PREAMBLE, "d": ARM_D}

# ★植える偏り(**実験の値ではない**)。極性で符号を変え、腕と並びで少しずつずらす ——
# 腕の取り違えと並びの取り違えが、値の違いとして表に出るようにするためである。
BIAS_BY_CATEGORY: dict[str, float] = {
    t3_comparison.T3_GT: 0.125,
    t3_comparison.T3_LT: -0.375,
    t3_comparison.T1B_GT: 0.125,
    t3_comparison.T1B_LT: -0.375,
}
BIAS_BY_ARM: dict[str, float] = {ARM_B0: 0.0, ARM_D: 0.02, ARM_PREAMBLE: 0.04}
BIAS_ORDER_STEP = 0.001
# 対数確率の基準(どちらも 0 以下に収まる値であればよい)。
CALIBRATION_BASE_LOGP = -1.0
SWEEP_BASE_LOGP = -0.5
# 掃引の採点器が置く差。植えた項目だけ幅(0.25)の内側にする。
SWEEP_WIDE_GAP = 0.3
SWEEP_NEAR_TIE_GAP = 0.125


def expected_bias(arm: str, category: str, order: int | None) -> float:
    """植えた偏り `b`(3 記号すべてに同じ値を置くので `content_free_bias` はこれを返す)。"""
    return (
        BIAS_BY_CATEGORY[category]
        + BIAS_BY_ARM[arm]
        + BIAS_ORDER_STEP * (0 if order is None else order)
    )


# --------------------------------------------------------------------------
# 本実行(モデルの重みは読まない)
# --------------------------------------------------------------------------


def planted_calibration_scorer(config: Mapping[str, Any]) -> ForcedChoiceScorer:
    """内容のない入力ごとに、植えた偏りぴったりの差を返す採点器。"""
    plan = calibration_run.load_calibration_plan(config)
    entry_of = {entry.prompt: entry for entry in plan.inputs}
    if len(entry_of) != len(plan.inputs):
        raise AssertionError("較正の入力が文面で一意に決まらない")

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        choices = []
        for prompt in prompts:
            entry = entry_of[prompt]
            bias = expected_bias(entry.arm, entry.category, entry.preamble_order)
            choice = ForcedChoice(
                answer=bias > 0,
                yes_logprob=CALIBRATION_BASE_LOGP,
                no_logprob=CALIBRATION_BASE_LOGP - bias,
            )
            choices.append(with_filler_top_tokens(choice))
        return choices

    return scorer


def truthful_sweep_scorer(config: Mapping[str, Any]) -> ForcedChoiceScorer:
    """真値どおりに答える採点器。差は ±0.3、植えた項目だけ ±0.125(幅の内側)。"""
    pool = run.load_threshold_sweep_pool(config)
    prompts = run.threshold_sweep_prompts(config, pool)
    if len(set(prompts.values())) != len(prompts):
        raise AssertionError("掃引の文面が項目を一意に決めない")
    item_of = {prompts[item.item_id]: item for item in pool.items}

    def scorer(prompts_batch: Sequence[str]) -> list[ForcedChoice]:
        choices = []
        for prompt in prompts_batch:
            item = item_of[prompt]
            truth = t3_comparison.comparison_answer(
                t3_comparison.item_total(item),
                t3_comparison.polarity_of(item.category),
                int(item.params["threshold"]),
            )
            gap = SWEEP_NEAR_TIE_GAP if planted_near_tie(item.item_id) else SWEEP_WIDE_GAP
            yes, no = (
                (SWEEP_BASE_LOGP, SWEEP_BASE_LOGP - gap)
                if truth
                else (SWEEP_BASE_LOGP - gap, SWEEP_BASE_LOGP)
            )
            choices.append(
                with_filler_top_tokens(
                    ForcedChoice(answer=yes > no, yes_logprob=yes, no_logprob=no)
                )
            )
        return choices

    return scorer


def execute_sweep(config: dict[str, Any], tmp: Path) -> Path:
    tmp.mkdir(parents=True)
    config_path = write_config(config, tmp / "config.yaml")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", stub_capture)
        return run.execute_threshold_sweep(
            config,
            config_path=config_path,
            run_dir=tmp / "run",
            scorer=truthful_sweep_scorer(config),
        )


def execute_calibration(tmp: Path) -> Path:
    tmp.mkdir(parents=True)
    config = load_config(C_CONFIG)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", stub_capture)
        return calibration_run.execute_calibration(
            config,
            config_path=C_CONFIG,
            run_dir=tmp / "run",
            scorer=planted_calibration_scorer(config),
        )


@pytest.fixture(scope="module")
def order6b(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """固定オフセット 3 腕(B0・①・(d))・S の掃引・(c) の較正を、固定応答で 1 度ずつ回す。"""
    root = tmp_path_factory.mktemp("calibrated")
    pilot = load_config(PILOT_CONFIG)
    pool_dir = root / "pilot_pool"
    eval_pool.write_pool(eval_pool.build(pilot), pool_dir)
    runs = {name: execute_arm(name, pool_dir, root / name) for name in FIXED_ARMS}
    sweep_dir = root / "s_pool"
    eval_pool.write_pool(sweep_pool.build_sweep_pool(pilot, eval_pool.build(pilot), "s"), sweep_dir)
    runs["sweep"] = execute_sweep(sweep_config(sweep_dir, arm="s"), root / "sweep")
    runs["c"] = execute_calibration(root / "c")
    return runs


@pytest.fixture(scope="module")
def loaded(order6b: dict[str, Path]) -> calibrated.Calibration:
    return calibrated.load_calibration(order6b["c"] / METRICS_FILENAME)


def metrics_of(run_dir: Path) -> Path:
    return run_dir / METRICS_FILENAME


def binary_records(run_dir: Path) -> list[dict[str, Any]]:
    return [
        record
        for record in frame.read_predictions(run_dir)
        if record["group"] == t3_comparison.GROUP
    ]


def bias_of_record(loaded: calibrated.Calibration, arm: str, record: Mapping[str, Any]) -> float:
    """テスト側で数え直す偏り(実装の `BiasLookup` を通さない)。"""
    order = (
        None
        if not loaded.arm_named(arm).preamble
        else preamble.order_index(record["item_id"], len(loaded.preamble_lines or ()))
    )
    return expected_bias(arm, record["category"], order)


# --------------------------------------------------------------------------
# 較正の run を読む
# --------------------------------------------------------------------------


def test_the_calibration_run_gives_back_the_planted_biases(
    loaded: calibrated.Calibration,
) -> None:
    """★3 記号に同じ差を置いたので、`content_free_bias` は植てた値そのものを返す。"""
    assert loaded.symbols == SOURCE_SYMBOLS
    assert {arm.name for arm in loaded.arms} == {ARM_B0, ARM_PREAMBLE, ARM_D}
    assert len(loaded.biases) == 4 + 2 + 4 * 24  # b0 + d + preamble(並び 24 通り)
    for (arm, category, order), bias in loaded.biases.items():
        assert bias == pytest.approx(expected_bias(arm, category, order))
    assert loaded.preamble_lines is not None and loaded.preamble_sha256 is not None


def test_the_lookup_picks_the_order_of_each_item(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> None:
    """★前置きの腕では項目ごとに `order_index` 番目の並びの `b` を引く(§4.9 読み7)。"""
    lookup = calibrated.bias_lookup(loaded, ARM_PREAMBLE)
    records = binary_records(order6b["preamble"])
    orders = {preamble.order_index(r["item_id"], len(loaded.preamble_lines or ())) for r in records}
    assert len(orders) > 1  # 並びが 1 つに潰れていたら、この検査は何も言っていない
    for record in records:
        assert lookup.of(record["category"], record["item_id"]) == pytest.approx(
            bias_of_record(loaded, ARM_PREAMBLE, record)
        )
    assert calibrated.bias_lookup(loaded, ARM_B0).order_of("どの項目でも") is None


def test_an_unknown_arm_or_key_stops(loaded: calibrated.Calibration) -> None:
    with pytest.raises(calibrated.CalibrationApplyError, match="腕"):
        calibrated.bias_lookup(loaded, "b0_plus")
    with pytest.raises(calibrated.CalibrationApplyError, match="偏りが無い"):
        calibrated.bias_lookup(loaded, ARM_D).of(t3_comparison.T3_GT, "item")


def test_a_run_that_is_not_a_calibration_stops(order6b: dict[str, Path]) -> None:
    """★B0 の評価 run・掃引の run を較正の run として読むと止まる。"""
    for name in ("pilot", "sweep"):
        with pytest.raises(calibrated.CalibrationApplyError, match="kind"):
            calibrated.load_calibration(metrics_of(order6b[name]))


def test_mismatched_symbols_between_the_two_files_stop(
    order6b: dict[str, Path], tmp_path: Path
) -> None:
    """★`calibration.json` と `metrics.json` の記号が食い違えば止まる。"""
    copied = tmp_path / "run"
    shutil.copytree(order6b["c"], copied)
    rows_path = copied / calibrated.ROWS_FILENAME
    payload = json.loads(rows_path.read_text(encoding="utf-8"))
    payload["symbols"] = list(payload["symbols"])[:-1]
    rows_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(calibrated.CalibrationApplyError, match="記号"):
        calibrated.load_calibration(metrics_of(copied))


# --------------------------------------------------------------------------
# 腕と run の照合(ADR-085 決定3)
# --------------------------------------------------------------------------


def test_the_arm_must_match_the_template_set_and_the_preamble(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> None:
    """★文面の組・前置きの有無・前置きの中身が腕と食い違えば止まる。"""
    for name, arm in ARM_OF_RUN.items():
        metrics = json.loads(metrics_of(order6b[name]).read_text(encoding="utf-8"))
        config = load_config(order6b[name] / "config.yaml")
        calibrated.check_arm(calibrated.bias_lookup(loaded, arm), metrics, config, name)
        for other in set(ARM_OF_RUN.values()) - {arm}:
            with pytest.raises(calibrated.CalibrationApplyError):
                calibrated.check_arm(calibrated.bias_lookup(loaded, other), metrics, config, name)


def test_a_different_preamble_stops(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> None:
    """★前置きの sha256 が違えば止まる —— 別の前置きの定数は引けない。"""
    lookup = calibrated.bias_lookup(loaded, ARM_PREAMBLE)
    config = load_config(order6b["preamble"] / "config.yaml")
    metrics = json.loads(metrics_of(order6b["preamble"]).read_text(encoding="utf-8"))
    tampered = {**metrics, "preamble": {**metrics["preamble"], "sha256": "0" * 64}}
    with pytest.raises(calibrated.CalibrationApplyError, match="sha256"):
        calibrated.check_arm(lookup, tampered, config, "preamble")


# --------------------------------------------------------------------------
# 固定オフセットの記録に引く
# --------------------------------------------------------------------------


def adjusted_of(loaded: calibrated.Calibration, run_dir: Path, arm: str) -> list[dict[str, Any]]:
    lookup = calibrated.bias_lookup(loaded, arm)
    return calibrated.calibrated_forced_choice_records(
        frame.read_predictions(run_dir), lookup, run_name=run_dir.name
    )


@pytest.mark.parametrize("name", list(ARM_OF_RUN))
def test_only_the_binary_rows_change(
    loaded: calibrated.Calibration, order6b: dict[str, Path], name: str
) -> None:
    """★数値群の行は 1 バイトも変わらず、二値群の `yes_logp` / `no_logp` も値そのもののまま。"""
    original = frame.read_predictions(order6b[name])
    adjusted = adjusted_of(loaded, order6b[name], ARM_OF_RUN[name])
    assert len(adjusted) == len(original)
    changed = 0
    for before, after in zip(original, adjusted):
        if before["group"] != t3_comparison.GROUP:
            assert after == before
            continue
        changed += 1
        assert after["yes_logp"] == before["yes_logp"] and after["no_logp"] == before["no_logp"]
        assert after["truth"] == before["truth"] and after["response"] == before["response"]
        assert after["bias"] == pytest.approx(bias_of_record(loaded, ARM_OF_RUN[name], before))
        gap = before["yes_logp"] - before["no_logp"]
        assert after["gap_after"] == pytest.approx(gap - after["bias"])
    assert changed > 0


@pytest.mark.parametrize("name", list(ARM_OF_RUN))
def test_the_correction_flips_exactly_the_planted_gt_items(
    loaded: calibrated.Calibration, order6b: dict[str, Path], name: str
) -> None:
    """★植えた近接同点(差 +0.125 で Yes)のうち、gt の偏り(+0.125 以上)を引いた行だけが No になる。

    lt の偏りは負なので差はさらに開き、真値どおりの行(差 ±2)はどちらの偏りでも動かない。
    """
    arm = ARM_OF_RUN[name]
    adjusted = {row["item_id"]: row for row in adjusted_of(loaded, order6b[name], arm)}
    flipped, expected = set(), set()
    for record in binary_records(order6b[name]):
        item_id = record["item_id"]
        if adjusted[item_id]["parsed"] != record["parsed"]:
            flipped.add(item_id)
        gap = record["yes_logp"] - record["no_logp"]
        if (gap - bias_of_record(loaded, arm, record) > 0) != record["parsed"]:
            expected.add(item_id)
    assert flipped == expected and flipped
    assert all(planted_near_tie(item_id) for item_id in flipped)
    assert {t3_comparison.polarity_of(adjusted[i]["category"]) for i in flipped} == {
        t3_comparison.GT
    }


@pytest.mark.parametrize("name", list(ARM_OF_RUN))
def test_the_classification_is_rescored_with_the_same_rule(
    loaded: calibrated.Calibration, order6b: dict[str, Path], name: str
) -> None:
    """★`classification` は `scoring.classify` の規則で付け直す(4 値の合計は 1.0 のまま)。"""
    adjusted = adjusted_of(loaded, order6b[name], ARM_OF_RUN[name])
    for row in adjusted:
        if row["group"] != t3_comparison.GROUP:
            continue
        assert row["classification"] == classify(
            row["parsed"], row["truth"], row["rule_values"][row["reference_rule"]]
        )


# --------------------------------------------------------------------------
# 補正後の run 単位の表(gonogo.py)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def calibrated_reports(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> dict[str, dict[str, Any]]:
    return {
        name: gonogo.calibrated_run_report(
            metrics_of(order6b[name]), calibrated.bias_lookup(loaded, arm)
        )
        for name, arm in ARM_OF_RUN.items()
    }


@pytest.mark.parametrize("name", list(ARM_OF_RUN))
def test_the_calibrated_report_has_no_parse_fail_and_says_it_is_not_a_candidate(
    calibrated_reports: dict[str, dict[str, Any]], name: str
) -> None:
    """★#1 は出さない(補正は数値群を動かさない)。注記に「§5 の候補ではない」がある。"""
    report = calibrated_reports[name]
    assert "parse_fail" not in report
    assert "§5 の候補" in report["note"] and "ADR-086 決定1" in report["note"]
    assert report["calibration"]["arm"] == ARM_OF_RUN[name]
    assert report["near_tie_margin"] == NEAR_TIE_MARGIN
    assert {entry["task"] for entry in report["cells"]} == set(report["solved_task_types"])


@pytest.mark.parametrize("name", list(ARM_OF_RUN))
def test_the_calibrated_cells_match_a_recount(
    loaded: calibrated.Calibration,
    order6b: dict[str, Path],
    calibrated_reports: dict[str, dict[str, Any]],
    name: str,
) -> None:
    """★セルの4値を、補正後の行から数え直した値と突き合わせる(合計は 1.0)。"""
    adjusted = adjusted_of(loaded, order6b[name], ARM_OF_RUN[name])
    run_inputs = frame.load_run(metrics_of(order6b[name]))
    rows = frame.build_rows(run_inputs, adjusted)
    for entry in calibrated_reports[name]["cells"]:
        subset = [
            r
            for r in rows
            if r["task"] == entry["task"] and r["coverage"] == entry["coverage"]
        ]
        assert entry["n"] == len(subset)
        assert entry["correct_rate"] == pytest.approx(
            sum(r["classification"] == "correct" for r in subset) / len(subset)
        )
        assert sum(entry[f"{name_}_rate"] for name_ in gonogo.CLASSES) == pytest.approx(1.0)


@pytest.mark.parametrize("name", list(ARM_OF_RUN))
def test_the_near_ties_are_counted_after_the_correction(
    loaded: calibrated.Calibration,
    order6b: dict[str, Path],
    calibrated_reports: dict[str, dict[str, Any]],
    name: str,
) -> None:
    """★補正後の差で数えた件数は、補正前の差で数えた件数(#2 の感度の行)と違う(ADR-086 決定2)。

    植えた行は gt・lt とも補正前は近接同点で、補正後は gt だけが残る。
    """
    arm = ARM_OF_RUN[name]
    adjusted = adjusted_of(loaded, order6b[name], arm)
    after = {
        row["item_id"]: row["gap_after"]
        for row in adjusted
        if row["group"] == t3_comparison.GROUP
    }
    before = gonogo.forced_choice_gaps(frame.read_predictions(order6b[name]), name)
    raw = {i for i, gap in before.items() if abs(gap) <= NEAR_TIE_MARGIN}
    corrected = {i for i, gap in after.items() if abs(gap) <= NEAR_TIE_MARGIN}
    assert corrected and corrected < raw
    counted = sum(cell["n_near_tie"] for cell in calibrated_reports[name]["near_tie"]["cells"])
    assert counted == len(corrected)
    assert "補正後の差" in calibrated_reports[name]["near_tie"]["note"]


def test_the_calibrated_report_refuses_the_wrong_arm(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> None:
    """★(d) の run に b0 の定数を引こうとすると、表を組む前に止まる。"""
    with pytest.raises(calibrated.CalibrationApplyError):
        gonogo.calibrated_run_report(
            metrics_of(order6b["d"]), calibrated.bias_lookup(loaded, ARM_B0)
        )


# --------------------------------------------------------------------------
# 掃引(r8_fit.py)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sweep_report(order6b: dict[str, Path]) -> dict[str, Any]:
    return r8_fit.run_report(metrics_of(order6b["sweep"]))


def test_the_sweep_report_adds_the_sensitivity_row_without_touching_the_fit(
    order6b: dict[str, Path], sweep_report: dict[str, Any]
) -> None:
    """★補正前の表に感度の行が付く。当てはめと遠いオフセットの correct は `fit_records` のまま。"""
    loaded_run = r8_fit.load_sweep_run(metrics_of(order6b["sweep"]))
    fit = r8_fit.fit_records(
        loaded_run.records, task_types=loaded_run.task_types, far=loaded_run.far
    )
    assert {key: sweep_report[key] for key in fit} == fit
    assert sweep_report["near_tie"]["margin"] == NEAR_TIE_MARGIN
    assert [(c["task_type"], c["coverage"]) for c in sweep_report["near_tie"]["cells"]] == [
        (c["task_type"], c["coverage"]) for c in sweep_report["cells"]
    ]
    # 真値どおりに答える採点器なので、補正前の遠いオフセットは両側とも correct = 1.0
    for cell in sweep_report["cells"]:
        assert cell["far_offset_correct"][r8_fit.LOW]["correct_rate"] == 1.0
        assert cell["far_offset_correct"][r8_fit.HIGH]["correct_rate"] == 1.0


def test_the_sweep_near_ties_match_a_recount(
    order6b: dict[str, Path], sweep_report: dict[str, Any]
) -> None:
    """★セル × 側ごとの件数と、除いた correct を記録から数え直す。閾値の近くは数えない。"""
    loaded_run = r8_fit.load_sweep_run(metrics_of(order6b["sweep"]))
    gaps = r8_fit.sweep_gaps(loaded_run.records, "sweep")
    planted = {r["item_id"] for r in loaded_run.records if planted_near_tie(r["item_id"])}
    assert planted  # 植えた行が 1 つも無ければ、この検査は何も言っていない
    total = 0
    for cell in sweep_report["near_tie"]["cells"]:
        for side, block in cell["sides"].items():
            subset = [
                r
                for r in loaded_run.records
                if r["task_type"] == cell["task_type"]
                and r["coverage"] == cell["coverage"]
                and loaded_run.far.side_of(int(r["threshold_offset"])) == side
            ]
            assert block["n"] == len(subset)
            near = [r for r in subset if abs(gaps[r["item_id"]]) <= NEAR_TIE_MARGIN]
            planted_here = [r for r in subset if r["item_id"] in planted]
            assert block["n_near_tie"] == len(near) == len(planted_here)
            total += len(near)
            kept = [r for r in subset if r["item_id"] not in {n["item_id"] for n in near}]
            assert block["without_near_tie"]["correct_rate"] == pytest.approx(
                sum(r["answer"] == r["truth"] for r in kept) / len(kept)
            )
    assert total > 0


def test_the_calibrated_sweep_changes_only_the_answer(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> None:
    """★掃引では `answer` だけが差し替わり、`truth`・θ・`yes_logp` / `no_logp` は変わらない。"""
    loaded_run = r8_fit.load_sweep_run(metrics_of(order6b["sweep"]))
    lookup = calibrated.bias_lookup(loaded, ARM_B0)
    adjusted = calibrated.calibrated_sweep_records(loaded_run.records, lookup, run_name="sweep")
    flipped = 0
    for before, after in zip(loaded_run.records, adjusted):
        assert {k: v for k, v in after.items() if k not in ("answer", "bias", "gap_after")} == {
            k: v for k, v in before.items() if k != "answer"
        }
        bias = expected_bias(ARM_B0, before["category"], None)
        assert after["bias"] == pytest.approx(bias)
        gap = before["yes_logp"] - before["no_logp"]
        assert after["gap_after"] == pytest.approx(gap - bias)
        assert after["answer"] == (gap - bias > 0)
        flipped += after["answer"] != before["answer"]
    assert flipped > 0  # 補正で 1 つも動かないなら、この検査は何も言っていない


def test_the_calibrated_sweep_report_recounts_the_far_offset_correct(
    loaded: calibrated.Calibration, order6b: dict[str, Path], sweep_report: dict[str, Any]
) -> None:
    """★補正後の遠いオフセットの correct を数え直し、補正前と違うことを確かめる(§5 (iv))。"""
    lookup = calibrated.bias_lookup(loaded, ARM_B0)
    report = r8_fit.calibrated_run_report(metrics_of(order6b["sweep"]), lookup)
    loaded_run = r8_fit.load_sweep_run(metrics_of(order6b["sweep"]))
    adjusted = calibrated.calibrated_sweep_records(loaded_run.records, lookup, run_name="sweep")
    assert report["calibration"]["arm"] == ARM_B0 and "§5 の候補" in report["note"]
    assert report["arm"] == sweep_report["arm"]
    rates = []
    for cell in report["cells"]:
        for side in r8_fit.SIDES:
            subset = [
                r
                for r in adjusted
                if r["task_type"] == cell["task_type"]
                and r["coverage"] == cell["coverage"]
                and loaded_run.far.side_of(int(r["threshold_offset"])) == side
            ]
            block = cell["far_offset_correct"][side]
            assert block["n"] == len(subset)
            assert block["correct_rate"] == pytest.approx(
                sum(r["answer"] == r["truth"] for r in subset) / len(subset)
            )
            rates.append(block["correct_rate"])
    assert min(rates) < 1.0  # 補正前は両側とも 1.0 だった
    assert "補正後の差" not in report["near_tie"]["note"]  # 掃引の注記は §5 (iv) について


def test_the_printed_report_mentions_the_sensitivity_row(sweep_report: dict[str, Any]) -> None:
    """★標準出力にも感度の行が出る(合否に使わない旨つき)。"""
    lines = r8_fit.report_lines({"note": "—", "runs": [sweep_report]})
    text = "\n".join(lines)
    assert "近接同点" in text and "合否には使わない" in text


# --------------------------------------------------------------------------
# 壊れた記録
# --------------------------------------------------------------------------


def synthetic_binary_record(item_id: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "item_id": item_id,
        "group": t3_comparison.GROUP,
        "category": t3_comparison.T3_GT,
        "truth": True,
        "rule_values": {"p2": False},
        "reference_rule": "p2",
        "parsed": True,
        "yes_logp": -0.1,
        "no_logp": -0.4,
    }
    record.update(overrides)
    return record


def one_key_lookup(bias: float) -> calibrated.BiasLookup:
    calibration = calibrated.Calibration(
        run_id="synthetic",
        symbols=("N/A",),
        arms=(CalibrationArm(name=ARM_B0, template_set="eval_main", preamble=False),),
        preamble_lines=None,
        preamble_sha256=None,
        biases={(ARM_B0, t3_comparison.T3_GT, None): bias},
    )
    return calibrated.bias_lookup(calibration, ARM_B0)


def test_rows_without_the_forced_choice_values_stop() -> None:
    """★I10 より前の run を「偏り 0」と読ませない(ADR-084 決定3)。"""
    lookup = one_key_lookup(0.5)
    broken = synthetic_binary_record("a", yes_logp=None)
    with pytest.raises(calibrated.CalibrationApplyError, match="yes_logp"):
        calibrated.calibrated_forced_choice_records([broken], lookup, run_name="synthetic")
    nan_row = synthetic_binary_record("a", no_logp=math.nan)
    with pytest.raises(calibrated.CalibrationApplyError, match="数でない"):
        calibrated.calibrated_forced_choice_records([nan_row], lookup, run_name="synthetic")


def test_a_run_without_binary_rows_stops() -> None:
    lookup = one_key_lookup(0.5)
    numeric = {"item_id": "n", "group": "bare_sum"}
    with pytest.raises(calibrated.CalibrationApplyError, match="二値群"):
        calibrated.calibrated_forced_choice_records([numeric], lookup, run_name="synthetic")


def test_duplicate_or_nan_gaps_stop() -> None:
    rows = [
        {"item_id": "a", "gap_after": 0.1},
        {"item_id": "a", "gap_after": 0.2},
    ]
    with pytest.raises(calibrated.CalibrationApplyError, match="2 つある"):
        calibrated.calibrated_gaps(rows, "synthetic")
    with pytest.raises(calibrated.CalibrationApplyError, match="数でない"):
        calibrated.calibrated_gaps([{"item_id": "a", "gap_after": math.nan}], "synthetic")
    with pytest.raises(calibrated.CalibrationApplyError, match="1 つも無い"):
        calibrated.calibrated_gaps([{"item_id": "a"}], "synthetic")


def test_the_bias_is_subtracted_and_ties_fall_to_no() -> None:
    """★同点(補正後の差がちょうど 0)は No(`choose_from_logprobs` と同じ。ADR-083 決定2)。"""
    lookup = one_key_lookup(0.5)
    # 2 進で正確に表せる値にする(0.3 のような値では差が丸めで 0 をわずかに超える)
    row = synthetic_binary_record("a", yes_logp=-0.25, no_logp=-0.75)  # 差 0.5
    (adjusted,) = calibrated.calibrated_forced_choice_records([row], lookup, run_name="synthetic")
    assert adjusted["gap_after"] == pytest.approx(0.0)
    assert adjusted["parsed"] is False and adjusted["classification"] == "rule"
# --------------------------------------------------------------------------
# 掃引の感度の行(合成の行。境界・側・重複)
# --------------------------------------------------------------------------

FAR = r8_fit.FarOffsets(low_max=-2, high_min=3, source="テスト(実験条件ではない)")


def sweep_row(item_id: str, theta: int, *, answer: bool, truth: bool) -> dict[str, Any]:
    """掃引の 1 行(`near_tie_table` / `sweep_gaps` が読む欄だけ)。"""
    return {
        "item_id": item_id,
        "task_type": t3_comparison.T3,
        "coverage": MAIN_COVERAGE_LEVELS[0],
        "threshold_offset": theta,
        "answer": answer,
        "truth": truth,
        "yes_logp": -0.5,
        "no_logp": -1.5,
    }


def test_the_sweep_near_tie_includes_the_boundary_and_needs_both_sides() -> None:
    """★|差| = 幅ちょうどは近接同点に数える(境界を含む)。側に項目が無ければ止める。"""
    rows = [
        sweep_row("a", -3, answer=True, truth=True),
        sweep_row("b", -3, answer=True, truth=False),
        sweep_row("c", 3, answer=True, truth=True),
        sweep_row("d", 3, answer=False, truth=True),
    ]
    gaps = {"a": NEAR_TIE_MARGIN, "b": -NEAR_TIE_MARGIN, "c": 1.0, "d": NEAR_TIE_MARGIN}
    (cell,) = r8_fit.near_tie_table(
        rows, gaps, task_types=[t3_comparison.T3], far=FAR, margin=NEAR_TIE_MARGIN
    )
    low, high = cell["sides"][r8_fit.LOW], cell["sides"][r8_fit.HIGH]
    assert (low["n"], low["n_near_tie"]) == (2, 2)
    assert low["without_near_tie"] == {"n": 0, "n_correct": None, "correct_rate": None}
    assert (high["n"], high["n_near_tie"]) == (2, 1)
    assert high["without_near_tie"]["correct_rate"] == 1.0  # 残るのは c(真値どおり)だけ
    with pytest.raises(r8_fit.R8FitError, match="側に項目"):
        r8_fit.near_tie_table(
            rows[:2],
            {"a": 1.0, "b": 1.0},
            task_types=[t3_comparison.T3],
            far=FAR,
            margin=NEAR_TIE_MARGIN,
        )


def test_duplicate_or_missing_sweep_gaps_stop() -> None:
    """★掃引の差でも、item_id の重複と欄の欠けは止める。"""
    duplicated = [
        sweep_row("a", -3, answer=True, truth=True),
        sweep_row("a", 3, answer=True, truth=True),
    ]
    with pytest.raises(r8_fit.R8FitError, match="2 つある"):
        r8_fit.sweep_gaps(duplicated, "synthetic")
    broken = [{**sweep_row("b", -3, answer=True, truth=True), "yes_logp": None}]
    with pytest.raises(r8_fit.R8FitError, match="yes_logp"):
        r8_fit.sweep_gaps(broken, "synthetic")


def test_the_calibrated_sweep_near_ties_use_the_post_correction_gap(
    loaded: calibrated.Calibration, order6b: dict[str, Path]
) -> None:
    """★掃引でも近接同点は補正後の差で数える(ADR-086 決定2・決定3)。補正前とは別の集合になる。"""
    lookup = calibrated.bias_lookup(loaded, ARM_B0)
    loaded_run = r8_fit.load_sweep_run(metrics_of(order6b["sweep"]))
    adjusted = calibrated.calibrated_sweep_records(loaded_run.records, lookup, run_name="sweep")
    before = r8_fit.sweep_gaps(loaded_run.records, "sweep")
    raw = {i for i, gap in before.items() if abs(gap) <= NEAR_TIE_MARGIN}
    corrected = {
        row["item_id"] for row in adjusted if abs(row["gap_after"]) <= NEAR_TIE_MARGIN
    }
    assert raw and corrected and corrected != raw
    report = r8_fit.calibrated_run_report(metrics_of(order6b["sweep"]), lookup)
    counted = sum(
        block["n_near_tie"]
        for cell in report["near_tie"]["cells"]
        for block in cell["sides"].values()
    )
    assert counted == len(corrected)


def test_the_provenance_carries_only_this_arms_biases(loaded: calibrated.Calibration) -> None:
    """★来歴に並ぶ偏りはその腕のものだけ(腕を取り違えた表を「同じ定数を引いた」と読ませない)。"""
    record = calibrated.bias_lookup(loaded, ARM_D).record()
    assert record["arm"] == ARM_D and record["preamble"] is False
    assert record["preamble_sha256"] is None and record["run_id"] == loaded.run_id
    assert {row["category"] for row in record["biases"]} == {
        t3_comparison.T1B_GT,
        t3_comparison.T1B_LT,
    }
    assert len(record["biases"]) == 2
    for row in record["biases"]:
        assert row["preamble_order"] is None
        assert row["bias"] == pytest.approx(expected_bias(ARM_D, row["category"], None))
    with_preamble = calibrated.bias_lookup(loaded, ARM_PREAMBLE).record()
    assert len(with_preamble["biases"]) == 4 * 24
    assert with_preamble["preamble_sha256"] == loaded.preamble_sha256
