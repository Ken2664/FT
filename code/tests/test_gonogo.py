"""Go/No-Go #1〜#3 の表(`code/analysis/gonogo.py`)。PLAN-023 手順5。

答える問い: 「順6 の run から、基準を割った群・セルに正しく印が付くか」

ここで固定する最重要の性質:
  - **4値は揃えて出し、合計は 1.0**(`CLAUDE.md` §6)
  - **閾値は config から読み、null なら止まる**(既定値を作らない)
  - **#2 は 12 セル(4 タスク型 × 3 既知性)。空のセルがあれば止まる**
  - **#3 の理論値は行の真値から数える**(極性が均衡していれば 0.5)
  - **本番 config で回した run(固定応答)の上で、端から端まで表が組める**

**ここに出る数値は実験結果ではない**(合成の行と固定応答)。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.analysis import gonogo
from code.config import load_config
from code.data_gen import eval_pool
from code.data_gen.battery_items import read_items
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import run
from code.eval.forced_choice import ForcedChoice
from code.rates import CORRECT, OTHER_ERROR, PARSE_FAIL, RULE

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
    """12 セルに CELL_N 行ずつ。`correct_in` のセルだけ correct の件数を変える(残りは rule)。"""
    groups = {"t1": "bare_sum", "t2": "word_problem", "t3": "comparison", "t1b": "comparison"}
    rows: list[dict[str, Any]] = []
    for task, group in groups.items():
        for coverage in MAIN_COVERAGE_LEVELS:
            n_correct = (correct_in or {}).get((task, coverage), CELL_N)
            for index in range(CELL_N):
                binary = group == "comparison"
                rows.append(
                    row(
                        group=group,
                        task=task,
                        coverage=coverage,
                        classification=CORRECT if index < n_correct else RULE,
                        # 二値は極性を均衡させる(半分が Yes)
                        truth=(index % 2 == 0) if binary else 7,
                    )
                )
    return rows


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
    table = gonogo.cell_table(rows, TEST_THRESHOLDS)
    assert len(table) == 12
    failed = {(entry["task"], entry["coverage"]) for entry in table if entry["fails"]}
    assert failed == {("t2", "extrap_magnitude")}  # 0.7 は基準を満たす(>= 0.70)


def test_cell_table_stops_on_an_empty_cell() -> None:
    rows = [r for r in full_cell_rows() if not (r["task"] == "t3" and r["coverage"] == "id")]
    with pytest.raises(gonogo.GoNoGoError, match="行が無い"):
        gonogo.cell_table(rows, TEST_THRESHOLDS)


def test_constant_strategy_table_marks_cells_that_do_not_beat_the_baseline() -> None:
    """★極性が均衡していれば理論値は 0.5。実測がそれを上回らないセルに印が付く。"""
    rows = full_cell_rows({("t1b", "id"): 5})
    table = gonogo.constant_strategy_table(rows)
    assert {entry["task"] for entry in table} == set(gonogo.BINARY_TASK_TYPES)
    for entry in table:
        assert entry["baselines"]["always_yes"]["correct_rate"] == pytest.approx(0.5)
    failed = {(entry["task"], entry["coverage"]) for entry in table if entry["fails"]}
    assert failed == {("t1b", "id")}


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
    assert "#2 correct_rate" in capsys.readouterr().out
