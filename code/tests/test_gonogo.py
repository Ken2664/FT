"""Go/No-Go #1〜#3 の表(`code/analysis/gonogo.py`)。PLAN-023 手順5。

答える問い: 「順6 の run から、基準を割った群・セルに正しく印が付くか」

ここで固定する最重要の性質:
  - **4値は揃えて出し、合計は 1.0**(`CLAUDE.md` §6)
  - **閾値は config から読み、null なら止まる**(既定値を作らない)
  - **#2 は 12 セル(4 タスク型 × 3 既知性)。空のセルがあれば止まる**
  - **#3 の理論値は行の真値から数える**(極性が均衡していれば 0.5)
  - **本番 config で回した run(固定応答)の上で、端から端まで表が組める**
  - **順6b(PLAN-026 §4.11 = I11a)**: 絞りを宣言した run は解いたタスク型のセルだけ / 腕を見分ける欄 /
    極性別の参照線は #3 の印を動かさない / 近接同点の感度の行(幅は順6b の config 7 本にだけ・境界を含む・
    行に yes_logp / no_logp が無ければ止まる)。B0・①・(d) の config で回した run の上で数え直して確かめる

**ここに出る数値は実験結果ではない**(合成の行と固定応答)。
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.analysis import frame, gonogo
from code.config import load_config
from code.data_gen import eval_pool
from code.data_gen.battery_items import read_items
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import run
from code.eval.forced_choice import ForcedChoice
from code.eval.preamble import declared_preamble, preamble_sha256
from code.rates import CORRECT, OTHER_ERROR, PARSE_FAIL, RULE
from code.tests.test_top_k import with_filler_top_tokens

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"

# **実験の閾値ではない**(本番は config の gonogo.*)。印の付き方を見るための値。
TEST_THRESHOLDS = gonogo.Thresholds(parse_fail_max=0.02, min_cell_correct_rate=0.70)
CELL_N = 10

# run の来歴に要る値(test_run_real.py と同じ。実験条件ではない)。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40


def row(**fields: Any) -> dict[str, Any]:
    base = {
        "group": "bare_sum",
        "task": "t1",
        "coverage": "id",
        "classification": CORRECT,
        "truth": 7,
    }
    return {**base, **fields}


def full_cell_rows(correct_in: dict[tuple[str, str], int] | None = None) -> list[dict[str, Any]]:
    """12 セルに CELL_N 行ずつ。`correct_in` のセルだけ correct の件数を変える(残りは rule)。

    二値の行は固定オフセットの項目と同じく、真値を極性で決める(gt → No / lt → Yes。★F138)。
    """
    groups = {"t1": "bare_sum", "t2": "word_problem", "t3": "comparison", "t1b": "comparison"}
    rows: list[dict[str, Any]] = []
    for task, group in groups.items():
        for coverage in MAIN_COVERAGE_LEVELS:
            n_correct = (correct_in or {}).get((task, coverage), CELL_N)
            for index in range(CELL_N):
                binary = group == "comparison"
                correct = index < n_correct
                # 二値は極性を均衡させる(半分が Yes)
                truth: Any = (index % 2 == 0) if binary else 7
                binary_fields = (
                    {
                        "category": f"{task}_{'lt' if truth else 'gt'}",
                        "parsed": truth if correct else not truth,
                    }
                    if binary
                    else {}
                )
                rows.append(
                    row(
                        group=group,
                        task=task,
                        coverage=coverage,
                        item=f"{task}-{coverage}-{index}",
                        classification=CORRECT if correct else RULE,
                        truth=truth,
                        **binary_fields,
                    )
                )
    return rows


def cell_of(rows: list[dict[str, Any]], task: str, coverage: str) -> list[dict[str, Any]]:
    return [r for r in rows if r["task"] == task and r["coverage"] == coverage]


def binary_row(polarity: str, *, truth: bool, answer: bool, item: str = "x") -> dict[str, Any]:
    """二値の 1 行(強制選択なので correct か rule のどちらか)。"""
    return row(
        group="comparison",
        task="t1b",
        category=f"t1b_{polarity}",
        truth=truth,
        parsed=answer,
        item=item,
        classification=CORRECT if answer == truth else RULE,
    )


# --------------------------------------------------------------------------
# 4値と定数戦略
# --------------------------------------------------------------------------


def test_four_values_are_reported_together_and_sum_to_one() -> None:
    rows = [row(classification=name) for name in (CORRECT, RULE, OTHER_ERROR, PARSE_FAIL)]
    values = gonogo.four_values(rows)
    assert values["n"] == 4
    assert {key for key in values if key.endswith("_rate")} == {
        f"{name}_rate" for name in gonogo.CLASSES
    }
    assert sum(value for key, value in values.items() if key.endswith("_rate")) == pytest.approx(1)


def test_unknown_classification_and_empty_cells_stop() -> None:
    with pytest.raises(gonogo.GoNoGoError, match="未知"):
        gonogo.four_values([row(classification="maybe")])
    with pytest.raises(gonogo.GoNoGoError, match="0 件"):
        gonogo.four_values([])


def test_constant_baseline_counts_from_the_truth() -> None:
    """★常に Yes は真値が Yes の項目で correct、それ以外で rule(PLAN-001 §5.3)。"""
    rows = [row(truth=True), row(truth=True), row(truth=True), row(truth=False)]
    assert gonogo.constant_baseline(rows, True) == {"correct_rate": 0.75, "rule_rate": 0.25}
    assert gonogo.constant_baseline(rows, False) == {"correct_rate": 0.25, "rule_rate": 0.75}
    with pytest.raises(gonogo.GoNoGoError, match="二値"):
        gonogo.constant_baseline([row(truth=7)], True)


# --------------------------------------------------------------------------
# #1〜#3 の印
# --------------------------------------------------------------------------


def test_parse_fail_table_marks_only_the_judged_groups() -> None:
    """#1 は T1 / T2 / 特異性対照だけを判定し、指示付き T1 は参考として並べる。"""
    rows = [
        row(group="bare_sum", classification=PARSE_FAIL),
        *[row(group="bare_sum") for _ in range(9)],
        *[row(group="word_problem", task="t2") for _ in range(10)],
        row(group="bare_sum_instructed", task="t1_instructed", classification=PARSE_FAIL),
    ]
    table = {entry["group"]: entry for entry in gonogo.parse_fail_table(rows, TEST_THRESHOLDS)}
    assert table["bare_sum"]["fails"] is True  # 0.1 >= 0.02
    assert table["word_problem"]["fails"] is False
    assert table["bare_sum_instructed"]["judged"] is False
    assert table["bare_sum_instructed"]["fails"] is False
    assert "specificity" not in table  # 行が無い群は出さない


def test_cell_table_has_twelve_cells_and_marks_low_correct() -> None:
    """★#2 は 12 セル。correct_rate < 0.70 のセルにだけ印が付く。"""
    rows = full_cell_rows({("t2", "extrap_magnitude"): 6, ("t1", "interp"): 7})
    table = gonogo.cell_table(rows, TEST_THRESHOLDS, task_types=gonogo.MAIN_TASK_TYPES)
    assert len(table) == 12
    failed = {(entry["task"], entry["coverage"]) for entry in table if entry["fails"]}
    assert failed == {("t2", "extrap_magnitude")}  # 0.7 は基準を満たす(>= 0.70)


def test_cell_table_stops_on_an_empty_cell() -> None:
    rows = [r for r in full_cell_rows() if not (r["task"] == "t3" and r["coverage"] == "id")]
    with pytest.raises(gonogo.GoNoGoError, match="行が無い"):
        gonogo.cell_table(rows, TEST_THRESHOLDS, task_types=gonogo.MAIN_TASK_TYPES)


def test_constant_strategy_table_marks_cells_that_do_not_beat_the_baseline() -> None:
    """★極性が均衡していれば理論値は 0.5。実測がそれを上回らないセルに印が付く。"""
    rows = full_cell_rows({("t1b", "id"): 5})
    table = gonogo.constant_strategy_table(rows, task_types=gonogo.MAIN_TASK_TYPES)
    assert {entry["task"] for entry in table} == set(gonogo.BINARY_TASK_TYPES)
    for entry in table:
        assert entry["baselines"]["always_yes"]["correct_rate"] == pytest.approx(0.5)
    failed = {(entry["task"], entry["coverage"]) for entry in table if entry["fails"]}
    assert failed == {("t1b", "id")}


# --------------------------------------------------------------------------
# 解いたタスク型(PLAN-026 §4.11 読み1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (None, ("t1", "t2", "t3", "t1b")),
        ({"task_types": ["t1b"]}, ("t1b",)),
        ({"task_types": ["t1b", "t3", "t2", "t1"]}, ("t1", "t2", "t3", "t1b")),
        ({"task_types": ["t1_instructed", "t1b"]}, ("t1b",)),
    ],
)
def test_the_solved_task_types_follow_the_subset_record(
    record: dict[str, Any] | None, expected: tuple[str, ...]
) -> None:
    """★絞りの無い run は 4 タスク型すべて。宣言があれば宣言の主軸の水準だけ(MAIN_TASK_TYPES の順)。"""
    assert gonogo.MAIN_TASK_TYPES == ("t1", "t2", "t3", "t1b")
    assert gonogo.solved_main_task_types({"task_subset": record}) == expected


def test_a_run_before_the_subset_record_solves_every_task_type() -> None:
    assert gonogo.solved_main_task_types({}) == gonogo.MAIN_TASK_TYPES


def test_the_tables_cover_only_the_solved_task_types() -> None:
    """★(d) の run(T1b だけ)は #2 が 3 セル・#3 が T1b の 3 セル。解いた型のセルが空なら止まる。"""
    rows = [r for r in full_cell_rows({("t1b", "interp"): 5}) if r["task"] == "t1b"]
    cells = gonogo.cell_table(rows, TEST_THRESHOLDS, task_types=("t1b",))
    assert [(c["task"], c["coverage"]) for c in cells] == [
        ("t1b", coverage) for coverage in MAIN_COVERAGE_LEVELS
    ]
    strategy = gonogo.constant_strategy_table(rows, task_types=("t1b",))
    assert {(c["task"], c["fails"]) for c in strategy} == {("t1b", False), ("t1b", True)}
    assert gonogo.constant_strategy_table(rows, task_types=("t1", "t2")) == []
    with pytest.raises(gonogo.GoNoGoError, match="行が無い"):
        gonogo.cell_table(rows, TEST_THRESHOLDS, task_types=("t3", "t1b"))


def test_rows_outside_the_declared_task_types_stop() -> None:
    """★記録が T1b だけなのに T3 の行があれば止まる。主軸の外の行(指示付き T1 など)は構わない。"""
    rows = full_cell_rows()
    gonogo.check_rows_within(rows, gonogo.MAIN_TASK_TYPES, "run")
    extra = [row(group="bare_sum_instructed", task="t1_instructed")]
    gonogo.check_rows_within(cell_of(rows, "t1b", "id") + extra, ("t1b",), "run")
    with pytest.raises(gonogo.GoNoGoError, match=r"\['t3'\]"):
        mixed = cell_of(rows, "t1b", "id") + cell_of(rows, "t3", "id")
        gonogo.check_rows_within(mixed, ("t1b",), "run")


# --------------------------------------------------------------------------
# 極性別の参照線(ADR-078 決定7 (b)。PLAN-026 §4.11 読み3)
# --------------------------------------------------------------------------


def test_the_polarity_reference_counts_yes_by_polarity_and_the_polarity_strategies() -> None:
    """★極性ごとの Yes の件数と、極性だけで答える 2 つの戦略の理論値を行の真値から数える。"""
    rows = [
        *[binary_row("gt", truth=False, answer=answer) for answer in (True, True, True, False)],
        *[binary_row("lt", truth=True, answer=answer) for answer in (True, True, False, False)],
    ]
    reference = gonogo.polarity_reference(rows)
    assert reference["by_polarity"] == {
        "gt": {"n": 4, "n_yes": 3, "yes_rate": 0.75},
        "lt": {"n": 4, "n_yes": 2, "yes_rate": 0.5},
    }
    # 固定オフセットの項目(真値が極性で決まる)では 1.0 / 0.0(PLAN-024 §1.3)
    assert reference["polarity_strategies"] == {
        "gt_no_lt_yes": {"correct_rate": 1.0, "rule_rate": 0.0},
        "gt_yes_lt_no": {"correct_rate": 0.0, "rule_rate": 1.0},
    }


def test_the_polarity_strategies_are_counted_from_the_truth_not_assumed() -> None:
    """真値が極性で決まらない行(掃引の低い側のような)では、戦略の値も 1.0 / 0.0 にならない。"""
    rows = [
        binary_row("gt", truth=False, answer=False),
        binary_row("gt", truth=True, answer=False),
        binary_row("lt", truth=True, answer=True),
        binary_row("lt", truth=False, answer=True),
    ]
    strategies = gonogo.polarity_reference(rows)["polarity_strategies"]
    assert strategies["gt_no_lt_yes"] == {"correct_rate": 0.5, "rule_rate": 0.5}
    assert strategies["gt_yes_lt_no"] == {"correct_rate": 0.5, "rule_rate": 0.5}


def test_a_cell_with_one_polarity_stops() -> None:
    with pytest.raises(gonogo.GoNoGoError, match="'lt'"):
        gonogo.polarity_reference([binary_row("gt", truth=False, answer=False)])


def test_the_polarity_reference_does_not_move_the_third_criterion() -> None:
    """★#3 の印は極性をまとめた correct 対 max(常に Yes, 常に No) のまま(ADR-078 決定9)。

    極性だけで答える戦略と同じ応答(correct 1.0)のセルにも印は付かない —— 参照線は合格線ではない。
    """
    rows = full_cell_rows({("t3", "id"): 5, ("t3", "interp"): 6})
    table = gonogo.constant_strategy_table(rows, task_types=gonogo.MAIN_TASK_TYPES)
    for entry in table:
        yes = entry["baselines"]["always_yes"]["correct_rate"]
        no = entry["baselines"]["always_no"]["correct_rate"]
        assert entry["fails"] is (not entry["correct_rate"] > max(yes, no))
        assert entry["polarity"]["polarity_strategies"]["gt_no_lt_yes"]["correct_rate"] == 1.0
    marks = {(e["task"], e["coverage"]): e["fails"] for e in table}
    assert marks[("t3", "id")] is True and marks[("t3", "interp")] is False
    assert marks[("t1b", "id")] is False  # correct 1.0 = 極性だけの戦略と同じ応答でも印は付かない


# --------------------------------------------------------------------------
# 近接同点の感度の行(ADR-079 決定8。PLAN-026 §7・§4.11 読み4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("declared", "expected"), [(0.25, 0.25), (1, 1.0), (None, None)])
def test_the_near_tie_margin_is_read_from_the_config(
    declared: Any, expected: float | None
) -> None:
    config = {"gonogo": {"parse_fail_max": 0.02, "near_tie_margin": declared}}
    assert gonogo.near_tie_margin_from_config(config, "run") == expected


def test_no_margin_key_means_no_sensitivity_rows() -> None:
    assert gonogo.near_tie_margin_from_config({"gonogo": {"parse_fail_max": 0.02}}, "run") is None
    assert gonogo.near_tie_margin_from_config({}, "run") is None


@pytest.mark.parametrize("declared", [True, "0.25", 0, -0.25, float("inf"), float("nan"), [0.25]])
def test_a_broken_margin_stops(declared: Any) -> None:
    with pytest.raises(gonogo.GoNoGoError, match="near_tie_margin"):
        gonogo.near_tie_margin_from_config({"gonogo": {"near_tie_margin": declared}}, "run")


def comparison_record(item_id: str, yes: float | None, no: float | None) -> dict[str, Any]:
    record: dict[str, Any] = {"item_id": item_id, "group": "comparison"}
    if yes is not None:
        record["yes_logp"] = yes
    if no is not None:
        record["no_logp"] = no
    return record


def test_the_gaps_are_the_row_values_of_the_binary_group() -> None:
    """★差は行の yes_logp − no_logp そのもの。数値群の行は見ない。"""
    records = [
        comparison_record("a", -0.5, -0.75),
        comparison_record("b", -3.0, -0.25),
        {"item_id": "c", "group": "bare_sum"},
    ]
    assert gonogo.forced_choice_gaps(records, "run") == {"a": 0.25, "b": -2.75}


@pytest.mark.parametrize(
    "records",
    [
        [comparison_record("a", -0.5, None)],
        [comparison_record("a", None, None)],
        [comparison_record("a", -0.5, -0.75), comparison_record("a", -0.5, -0.75)],
        [comparison_record("a", float("-inf"), float("-inf"))],
    ],
)
def test_gaps_that_cannot_be_read_stop(records: list[dict[str, Any]]) -> None:
    """★欄の無い行(I10 より前の run)・重複・差が数でない行は「近接同点 0 件」と読ませずに止める。"""
    with pytest.raises(gonogo.GoNoGoError):
        gonogo.forced_choice_gaps(records, "run")


def near_tie_cell(gaps_and_correct: list[tuple[float, bool]]) -> tuple[list, dict[str, float]]:
    """T1b `id` の 1 セル(極性は交互)と、行ごとの差。"""
    rows: list[dict[str, Any]] = []
    gaps: dict[str, float] = {}
    for index, (gap, correct) in enumerate(gaps_and_correct):
        polarity = "gt" if index % 2 == 0 else "lt"
        truth = polarity == "lt"
        rows.append(
            binary_row(
                polarity, truth=truth, answer=truth if correct else not truth, item=str(index)
            )
        )
        gaps[str(index)] = gap
    return rows, gaps


def test_near_ties_are_counted_inclusively_and_the_second_criterion_is_recomputed() -> None:
    """★|差| ≤ 幅(境界を含む)を除き、残りの 4 値と #2 と同じ比べ方の印を出す。"""
    rows, gaps = near_tie_cell(
        [
            (0.25, False),  # 境界ちょうど = 近接同点
            (-0.25, False),  # 負の側の境界 = 近接同点
            (0.2500001, False),  # 境界の外
            (1.0, True),
            (-2.0, True),
            (3.0, True),
        ]
    )
    # 3 セルとも同じ行(near_tie_table は解いた型の 3 セルすべてを要る)
    table = gonogo.near_tie_table(
        [dict(r, coverage=c) for c in MAIN_COVERAGE_LEVELS for r in rows],
        gaps,
        margin=0.25,
        thresholds=TEST_THRESHOLDS,
        task_types=("t1b",),
    )
    assert len(table) == 3
    entry = table[0]
    assert entry["task"] == "t1b" and entry["n"] == 6 and entry["n_near_tie"] == 2
    without = entry["without_near_tie"]
    assert without["n"] == 4
    assert without["correct_rate"] == pytest.approx(0.75)
    assert without["rule_rate"] == pytest.approx(0.25)
    assert without["other_error_rate"] == 0 and without["parse_fail_rate"] == 0
    assert without["fails"] is False  # 0.75 >= 0.70(除く前の correct は 0.5)
    assert gonogo.four_values(rows)["correct_rate"] == pytest.approx(0.5)


def test_the_recomputed_second_criterion_keeps_the_boundary_of_the_threshold() -> None:
    """除いた行の correct がちょうど 0.70 なら印は付かない(#2 と同じ `>=` の比べ方)。"""
    rows, gaps = near_tie_cell([(1.0, index < 7) for index in range(10)] + [(0.0, False)])
    rows = [dict(r, coverage=c) for c in MAIN_COVERAGE_LEVELS for r in rows]
    table = gonogo.near_tie_table(
        rows, gaps, margin=0.25, thresholds=TEST_THRESHOLDS, task_types=("t1b",)
    )
    for entry in table:
        assert entry["without_near_tie"]["correct_rate"] == pytest.approx(0.7)
        assert entry["without_near_tie"]["fails"] is False


def test_a_cell_of_only_near_ties_reports_null_values_together() -> None:
    """除いた後に行が無ければ 4 値と印は揃えて null(一部だけを出さない)。"""
    rows, gaps = near_tie_cell([(0.1, True), (-0.1, False)])
    rows = [dict(r, coverage=c) for c in MAIN_COVERAGE_LEVELS for r in rows]
    table = gonogo.near_tie_table(
        rows, gaps, margin=0.25, thresholds=TEST_THRESHOLDS, task_types=("t1b",)
    )
    assert len(table) == 3
    for entry in table:
        assert entry["n_near_tie"] == 2
        assert entry["without_near_tie"] == {
            "n": 0,
            "correct_rate": None,
            "rule_rate": None,
            "other_error_rate": None,
            "parse_fail_rate": None,
            "fails": None,
        }


def test_the_near_tie_table_covers_only_the_solved_binary_types() -> None:
    rows = full_cell_rows()
    gaps = {r["item"]: 5.0 for r in rows if r["group"] == "comparison"}
    table = gonogo.near_tie_table(
        rows, gaps, margin=0.25, thresholds=TEST_THRESHOLDS, task_types=gonogo.MAIN_TASK_TYPES
    )
    assert [(e["task"], e["coverage"]) for e in table] == [
        (task, coverage) for task in ("t3", "t1b") for coverage in MAIN_COVERAGE_LEVELS
    ]
    assert all(e["n_near_tie"] == 0 for e in table)
    with pytest.raises(gonogo.GoNoGoError, match="yes_logp"):
        gonogo.near_tie_table(
            rows, {}, margin=0.25, thresholds=TEST_THRESHOLDS, task_types=("t1b",)
        )


def test_missing_thresholds_stop(tmp_path: Path) -> None:
    """閾値が config に無ければ止まる。**既定値を作らない。**"""
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"gonogo": {"parse_fail_max": None, "min_cell_correct_rate": 0.7}}),
        encoding="utf-8",
    )
    with pytest.raises(gonogo.GoNoGoError, match="閾値"):
        gonogo.load_thresholds(tmp_path)


def test_the_main_config_carries_the_preregistered_thresholds() -> None:
    """本番 config の閾値は ADR-065 決定1 / ADR-041 決定1 の転記である。

    **`magnitude_sweep.theta` の流用ではない**(ADR-041 決定2)。同じ 0.70 だが別の欄から読む。
    """
    config = load_config(MAIN_CONFIG)
    assert config["gonogo"] == {"parse_fail_max": 0.02, "min_cell_correct_rate": 0.70}


# --------------------------------------------------------------------------
# 端から端まで(本番 config + 固定応答。モデルは読まない)
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


def truthful_engines(config: dict[str, Any], items: list[Any]) -> dict[str, Any]:
    """真値だけを返す固定応答(test_run_order6.py と同じ形)。"""
    template_set = config["data"]["eval_template_set"]
    lesions = run.build_reference_lesions(config)
    texts: dict[str, str] = {}
    answers: dict[str, bool] = {}
    for item in items:
        prompt = run.RENDERERS[item.group](
            item, run.load_group_templates(config, item.group, template_set)
        )
        if item.group == "comparison":
            answers[prompt] = run.t3_comparison.to_response(item, None, lesions).truth
        elif item.group == "specificity":
            texts[prompt] = f"Answer: {run.specificity_control.item_true_value(item)}."
        else:
            texts[prompt] = f"Answer: {sum(item.operands)}."

    def generator(prompts: list[str]) -> list[str]:
        return [texts[prompt] for prompt in prompts]

    def scorer(prompts: list[str]) -> list[ForcedChoice]:
        return [
            ForcedChoice(
                answer=answers[prompt],
                yes_logprob=-0.1 if answers[prompt] else -2.0,
                no_logprob=-2.0 if answers[prompt] else -0.1,
            )
            for prompt in prompts
        ]

    return {"generator": generator, "scorer": scorer}


def test_gonogo_runs_end_to_end_on_the_main_pool(tmp_path: Path, capsys: Any) -> None:
    """★本番 config の主プールを固定応答で回した run から、#1〜#3 の表が組める。

    真値だけを答える応答なので、どの基準にも印が付かない(**配線の確認であって結果ではない**)。
    """
    config = load_config(MAIN_CONFIG)
    pool_dir = tmp_path / "main"
    eval_pool.write_pool(eval_pool.build(config), pool_dir)
    config = copy.deepcopy(config)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["model"]["device"] = "cpu"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    items = read_items(pool_dir / "items.jsonl")
    target = run.execute(
        config,
        config_path=config_path,
        run_dir=tmp_path / "run",
        **truthful_engines(config, items),
    )

    out_dir = tmp_path / "gonogo"
    assert gonogo.main(["--runs", str(target), "--out-dir", str(out_dir)]) == 0
    report = json.loads((out_dir / gonogo.OUTPUT_FILENAME).read_text(encoding="utf-8"))
    (result,) = report["runs"]
    assert result["seed"] is None  # none モデル(adapter = null)
    assert len(result["cells"]) == 12
    # 1 セル = carry 2 層 × 40(T1 / T2)、carry 2 層 × 極性 2 × 40(T3 / T1b)。指示付き T1 は入らない
    expected_n = {"t1": 80, "t2": 80, "t3": 160, "t1b": 160}
    assert all(entry["n"] == expected_n[entry["task"]] for entry in result["cells"])
    assert not any(entry["fails"] for entry in result["parse_fail"])
    assert not any(entry["fails"] for entry in result["cells"])
    assert not any(entry["fails"] for entry in result["constant_strategy"])
    assert result["near_tie"] is None  # 本番 config には幅が無い
    for entry in result["constant_strategy"]:  # 真値だけを答える = gt(真値 No)で Yes は 0
        assert entry["polarity"]["by_polarity"]["gt"]["n_yes"] == 0
    assert "#2 correct_rate" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 順6b の固定オフセットの 3 腕(B0・①・(d))。PLAN-026 §4.11(I11a)
# --------------------------------------------------------------------------

CONFIG_DIR = REPO_ROOT / "configs"
ORDER6B_NAMES = ("pilot", "r8", "s_preamble", "preamble", "d", "s_d", "c")
# 固定オフセットの腕(gonogo.py が読む battery_eval の run)。B0 = pilot の config。
FIXED_ARMS = ("pilot", "preamble", "d")
# ADR-079 決定8 の転記(config の値を縛る)。
NEAR_TIE_MARGIN = 0.25
# 二値群の項目のうち、item_id のハッシュがこの値で割り切れる項目に近接同点を置く(**実験の値ではない**)。
PLANTED_MODULUS = 5
PLANTED_LOGPS = (-0.625, -0.75)  # 差 +0.125 = 幅の内側で Yes
TRUTHFUL_GAP_LOGPS = (-0.125, -2.125)  # 差 ±2 = 幅の外側で真値どおり


def order6b_config(name: str) -> Path:
    return CONFIG_DIR / f"exp_order6b_{name}.yaml"


# 段2 の診断の config(PLAN-032 I3。pilot の config の写しなので幅も写る。ADR-107 決定6 で同じ 0.25)。
DIAG_CONFIG_NAMES = ("pool", "b", "a", "b_d", "a_d")


def diag_config(name: str) -> Path:
    return CONFIG_DIR / f"exp_diag_{name}.yaml"


def test_only_the_order6b_configs_declare_the_near_tie_margin() -> None:
    """★幅は順6b の config 7 本と段2 の診断の 5 本にだけあり、値は 0.25(ADR-085 決定4 / ADR-107 決定6)。
    本番・smoke・雛形には無い。"""
    declaring = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        margin = gonogo.near_tie_margin_from_config(load_config(path) or {}, path.name)
        if margin is not None:
            declaring[path.name] = margin
    declared_paths = [order6b_config(name) for name in ORDER6B_NAMES] + [
        diag_config(name) for name in DIAG_CONFIG_NAMES
    ]
    assert declaring == {path.name: NEAR_TIE_MARGIN for path in declared_paths}
    # #1・#2 の閾値は本番と同じ(幅を足しても書き換えていない)
    main_thresholds = load_config(MAIN_CONFIG)["gonogo"]
    for path in declared_paths:
        block = dict(load_config(path)["gonogo"])
        block.pop("near_tie_margin")
        assert block == main_thresholds


def planted_near_tie(item_id: str) -> bool:
    return int(hashlib.sha256(item_id.encode("utf-8")).hexdigest(), 16) % PLANTED_MODULUS == 0


def order6b_engines(config: dict[str, Any], items: list[Any]) -> dict[str, Any]:
    """解く項目の文面から応答を引く固定応答(前置き・絞り・(d) の文面を通した文面で引く)。

    数値群は真値。二値群は真値どおり(差 ±2)だが、`planted_near_tie` の項目だけ差 +0.125 で Yes と答える。
    """
    template_set = config["data"]["eval_template_set"]
    lesions = run.build_reference_lesions(config)
    solved = run.solved_pool_items(config, items)
    texts: dict[str, str] = {}
    choices: dict[str, ForcedChoice] = {}
    for group in sorted({item.group for item in solved}):
        group_items = [item for item in solved if item.group == group]
        prompts = run.render_prompts(config, group, group_items, template_set=template_set)
        for item in group_items:
            prompt = prompts[item.item_id]
            assert prompt not in texts and prompt not in choices  # 文面から応答を一意に引ける
            if group == "comparison":
                truth = run.t3_comparison.to_response(item, None, lesions).truth
                if planted_near_tie(item.item_id):
                    yes, no = PLANTED_LOGPS
                else:
                    yes, no = TRUTHFUL_GAP_LOGPS if truth else TRUTHFUL_GAP_LOGPS[::-1]
                choice = ForcedChoice(answer=yes > no, yes_logprob=yes, no_logprob=no)
                # 上位 k は順6b の config の宣言どおりの個数の置き物(PLAN-026 §4.10 読み6)
                choices[prompt] = with_filler_top_tokens(choice)
            elif group == "specificity":
                texts[prompt] = f"Answer: {run.specificity_control.item_true_value(item)}."
            else:
                texts[prompt] = f"Answer: {sum(item.operands)}."

    def generator(prompts: list[str]) -> list[str]:
        return [texts[prompt] for prompt in prompts]

    def scorer(prompts: list[str]) -> list[ForcedChoice]:
        return [choices[prompt] for prompt in prompts]

    return {"generator": generator, "scorer": scorer}


def execute_arm(name: str, pool_dir: Path, tmp: Path) -> Path:
    config = load_config(order6b_config(name))
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    tmp.mkdir(parents=True)
    config_path = tmp / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    engines = order6b_engines(config, read_items(pool_dir / "items.jsonl"))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")
        return run.execute(config, config_path=config_path, run_dir=tmp / "run", **engines)


@pytest.fixture(scope="module")
def order6b_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """パイロット用プールを tmp に書き、B0・①・(d) の config で固定応答の本実行をする(モデルは読まない)。"""
    root = tmp_path_factory.mktemp("order6b")
    pool_dir = root / "pilot_pool"
    eval_pool.write_pool(eval_pool.build(load_config(order6b_config("pilot"))), pool_dir)
    return {name: execute_arm(name, pool_dir, root / name) for name in FIXED_ARMS}


def metrics_of(run_dir: Path) -> Path:
    return run_dir / "metrics.json"


def test_gonogo_reads_the_three_fixed_offset_arms(
    order6b_runs: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """★B0 は 12 セル、① は 4 タスク型の 12 セル(前置きの sha256 付き)、(d) は T1b の 3 セルだけ。"""
    out_dir = tmp_path / "gonogo"
    runs = [str(order6b_runs[name]) for name in FIXED_ARMS]
    assert gonogo.main(["--runs", *runs, "--out-dir", str(out_dir)]) == 0
    report = json.loads((out_dir / gonogo.OUTPUT_FILENAME).read_text(encoding="utf-8"))
    # 報告の run の順は glob を展開した順(パスの並び)で、渡した順ではない
    by_experiment = {r["provenance"]["experiment_id"]: r for r in report["runs"]}
    by_arm = {arm: by_experiment[f"exp_order6b_{arm}"] for arm in FIXED_ARMS}
    assert len(report["runs"]) == len(FIXED_ARMS)
    preamble_lines = declared_preamble(load_config(order6b_config("preamble")))
    assert preamble_lines is not None

    expected = {
        "pilot": ("exp_order6b_pilot", "eval_main", None, None, gonogo.MAIN_TASK_TYPES),
        "preamble": (
            "exp_order6b_preamble",
            "eval_main",
            preamble_sha256(preamble_lines),
            ["t3", "t1b", "t1", "t2"],
            gonogo.MAIN_TASK_TYPES,
        ),
        "d": ("exp_order6b_d", "order6b_d", None, ["t1b"], ("t1b",)),
    }
    for arm, (experiment, templates, sha, subset, solved) in expected.items():
        result = by_arm[arm]
        assert result["provenance"] == {
            "experiment_id": experiment,
            "pool_id": "pilot",
            "adapter": None,
            "template_set": templates,
            "preamble_sha256": sha,
            "task_subset": subset,
        }
        assert result["solved_task_types"] == list(solved)
        assert [(c["task"], c["coverage"]) for c in result["cells"]] == [
            (task, coverage) for task in solved for coverage in MAIN_COVERAGE_LEVELS
        ]
        binary = [task for task in gonogo.BINARY_TASK_TYPES if task in solved]
        assert [c["task"] for c in result["constant_strategy"]] == [
            task for task in binary for _ in MAIN_COVERAGE_LEVELS
        ]
        assert result["near_tie_margin"] == NEAR_TIE_MARGIN
        assert [c["task"] for c in result["near_tie"]["cells"]] == [
            task for task in binary for _ in MAIN_COVERAGE_LEVELS
        ]
    assert [g["group"] for g in by_arm["pilot"]["parse_fail"]] == [
        "bare_sum",
        "word_problem",
        "specificity",
        "bare_sum_instructed",
    ]
    assert [g["group"] for g in by_arm["preamble"]["parse_fail"]] == ["bare_sum", "word_problem"]
    assert by_arm["d"]["parse_fail"] == []
    out = capsys.readouterr().out
    assert f"近接同点(|yes_logp − no_logp| ≤ {NEAR_TIE_MARGIN})の感度の行" in out
    assert "templates=order6b_d" in out and "Yes|gt=" in out


def test_the_polarity_and_near_tie_rows_match_the_planted_answers(
    order6b_runs: dict[str, Path],
) -> None:
    """★近接同点の件数・除いた #2・極性別の Yes の件数が、置いた応答から数え直した値と一致する。

    置いた項目は Yes と答える(gt では rule、lt では correct)。残りは真値どおり。
    セルの割り当て(被覆ラベル)は frame.py の行から取る —— ここで確かめるのは gonogo.py の数え方である。
    """
    for arm in FIXED_ARMS:
        metrics_path = metrics_of(order6b_runs[arm])
        result = gonogo.run_report(metrics_path)
        rows = frame.build_rows(
            frame.load_run(metrics_path), frame.read_predictions(order6b_runs[arm])
        )
        cells = {(c["task"], c["coverage"]): c for c in result["cells"]}
        polarity = {(c["task"], c["coverage"]): c["polarity"] for c in result["constant_strategy"]}
        for entry in result["near_tie"]["cells"]:
            key = (entry["task"], entry["coverage"])
            subset = [r for r in rows if (r["task"], r["coverage"]) == key]
            planted = [r for r in subset if planted_near_tie(r["item"])]
            gt = [r for r in subset if r["category"].endswith("_gt")]
            planted_gt = [r for r in planted if r["category"].endswith("_gt")]
            assert planted and len(planted) < len(subset)  # 置いた項目も残る項目もある
            assert entry["n"] == len(subset)
            assert entry["n_near_tie"] == len(planted)
            without = entry["without_near_tie"]
            assert without["n"] == len(subset) - len(planted)
            assert (without["correct_rate"], without["rule_rate"]) == (1.0, 0.0)
            assert without["fails"] is False
            assert cells[key]["correct_rate"] == pytest.approx(1 - len(planted_gt) / len(subset))
            by_polarity = polarity[key]["by_polarity"]
            assert by_polarity["gt"] == {
                "n": len(gt),
                "n_yes": len(planted_gt),
                "yes_rate": len(planted_gt) / len(gt),
            }
            assert by_polarity["lt"]["n_yes"] == by_polarity["lt"]["n"] == len(subset) - len(gt)


def copied_run(order6b_runs: dict[str, Path], arm: str, tmp: Path) -> Path:
    target = tmp / f"copy_{arm}"
    shutil.copytree(order6b_runs[arm], target)
    return target


def edit_yaml(path: Path, edit: Any) -> None:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(config)
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_runs_with_different_margins_stop(order6b_runs: dict[str, Path], tmp_path: Path) -> None:
    edited = copied_run(order6b_runs, "d", tmp_path)
    edit_yaml(edited / "config.yaml", lambda c: c["gonogo"].update(near_tie_margin=0.5))
    assert gonogo.run_report(metrics_of(edited))["near_tie_margin"] == 0.5
    with pytest.raises(gonogo.GoNoGoError, match="近接同点の幅"):
        gonogo.build_report([metrics_of(order6b_runs["pilot"]), metrics_of(edited)])


def test_a_run_without_the_margin_key_has_no_sensitivity_rows(
    order6b_runs: dict[str, Path], tmp_path: Path
) -> None:
    edited = copied_run(order6b_runs, "d", tmp_path)
    edit_yaml(edited / "config.yaml", lambda c: c["gonogo"].pop("near_tie_margin"))
    result = gonogo.run_report(metrics_of(edited))
    assert result["near_tie"] is None and result["near_tie_margin"] is None
    lines = gonogo.report_lines({"note": "", "runs": [result]})
    assert any("近接同点の感度の行: なし" in line for line in lines)


def test_a_declared_margin_without_the_logps_in_the_rows_stops(
    order6b_runs: dict[str, Path], tmp_path: Path
) -> None:
    """★幅を宣言した run の二値群の行に yes_logp / no_logp が無ければ止まる(0 件と読ませない)。"""
    edited = copied_run(order6b_runs, "d", tmp_path)
    for path in sorted((edited / "predictions").glob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for record in records:
            record.pop("yes_logp", None)
        path.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
            encoding="utf-8",
        )
    with pytest.raises(gonogo.GoNoGoError, match="yes_logp"):
        gonogo.run_report(metrics_of(edited))


def test_a_subset_record_that_does_not_match_the_rows_stops(
    order6b_runs: dict[str, Path], tmp_path: Path
) -> None:
    """★metrics.json が T1b だけを解いたと書くのに、① の run の行には T3・T1・T2 がある → 止まる。"""
    edited = copied_run(order6b_runs, "preamble", tmp_path)
    metrics = json.loads(metrics_of(edited).read_text(encoding="utf-8"))
    metrics["task_subset"]["task_types"] = ["t1b"]
    metrics_of(edited).write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(gonogo.GoNoGoError, match="食い違"):
        gonogo.run_report(metrics_of(edited))
