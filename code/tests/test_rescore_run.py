"""`code/eval/rescore_run.py` のテスト(PLAN-027 §5 手順5 / §6.1)。

答える問い: 「本実行の run を現行のパーサで読み直す再採点は、C1-C5 を正しく実行し、
元の run ディレクトリには何も書かないか。二値群の行を触らずにいられるか」

**モデルの重みは1度も読まない**(GPU 0。PLAN-027 冒頭)。ここに出る数値は手で組んだ
架空の行から出たものであり、**実験結果ではない** —— `runs/` の実データには触れない。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.config import load_config
from code.eval import rescore_run
from code.eval import run as eval_run
from code.eval.battery import numeric_sum, t3_comparison
from code.rates import CORRECT, OTHER_ERROR, PARSE_FAIL, RULE

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# ★実験条件ではない。code/tests/test_rescore.py と同じ値(テストの経路を通すためだけ)。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
TEST_DEVICE = "cpu"
TEST_BATCH_SIZE = 1
TEST_DO_SAMPLE = False

REFERENCE_RULE = "p2"
NUMERIC_BATCH = numeric_sum.GROUP_BARE_SUM
BINARY_BATCH = t3_comparison.GROUP


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """git / pip freeze 等の外部コマンドの呼び出しを止める(test_rescore.py と同じ理由)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture
def config() -> dict[str, Any]:
    """本実行の形をなぞる最小の config(モデルは読まない)。"""
    cfg = load_config(SMOKE_CONFIG)
    cfg["model"]["name"] = TEST_MODEL
    cfg["model"]["revision"] = TEST_REVISION
    cfg["model"]["device"] = TEST_DEVICE
    cfg["eval"]["batch_size"] = TEST_BATCH_SIZE
    cfg["eval"]["do_sample"] = TEST_DO_SAMPLE
    cfg["eval"]["elicitation"] = "direct"
    cfg["eval"]["reference_rule"] = REFERENCE_RULE
    return cfg


# --------------------------------------------------------------------------
# 架空の元 run を組む
# --------------------------------------------------------------------------


def numeric_row(
    item_id: str, *, a: int, b: int, response: str, parsed: int | None
) -> dict[str, Any]:
    """数値群の1行(本実行の `prediction_record` と同じ欄)。"""
    truth = a + b
    rule_values = {REFERENCE_RULE: truth + 2}
    return {
        "item_id": item_id,
        "group": NUMERIC_BATCH,
        "category": "bare_sum_id",
        "operands": [a, b],
        "carry": False,
        "params": {},
        "prompt": f"{a} + {b} =",
        "response": response,
        "parsed": parsed,
        "truth": truth,
        "rule_values": rule_values,
        "reference_rule": REFERENCE_RULE,
        "classification": eval_run.classify(parsed, truth, rule_values[REFERENCE_RULE]),
    }


def binary_row(item_id: str, *, truth: bool, answer: bool) -> dict[str, Any]:
    """二値群の1行(強制選択。パーサを通らない。ADR-047)。"""
    rule_values = {REFERENCE_RULE: not truth}
    return {
        "item_id": item_id,
        "group": BINARY_BATCH,
        "category": "t3_id",
        "operands": [3, 4],
        "carry": False,
        "params": {"polarity": "gt", "threshold": 5},
        "prompt": "Is 3 + 4 greater than 5?",
        "response": "Yes [forced_choice yes_logp=-0.1000 no_logp=-2.0000]",
        "parsed": answer,
        "truth": truth,
        "rule_values": rule_values,
        "reference_rule": REFERENCE_RULE,
        "classification": eval_run.classify(answer, truth, rule_values[REFERENCE_RULE]),
        "yes_logp": -0.1,
        "no_logp": -2.0,
    }


def default_rows() -> dict[str, list[dict[str, Any]]]:
    """バッチ名 -> 行。**★F140 で動く行と動かない行を混ぜる。**

    - `n1` は現行でも旧でも 7 と読める(上位集合の検査に効く)
    - `n2` は `The sum of 152 and 474 is 626.` の形。旧は parse_fail、新は correct
    - `n3` は錨が無く数が割れる。旧も新も parse_fail(回収の上限を固定する)
    - `n4` は錨の後ろが真値でない。旧 parse_fail -> 新 other_error
    """
    return {
        NUMERIC_BATCH: [
            numeric_row("n1", a=3, b=4, response="Answer: 7.", parsed=7),
            numeric_row("n2", a=152, b=474, response="The sum of 152 and 474 is 626.", parsed=None),
            numeric_row("n3", a=10, b=20, response="Maybe 30 or 31", parsed=None),
            numeric_row("n4", a=10, b=20, response="The result is 99.", parsed=None),
        ],
        BINARY_BATCH: [
            binary_row("b1", truth=True, answer=True),
            binary_row("b2", truth=False, answer=True),
        ],
    }


def batch_metrics_for(name: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """架空の行から `by_batch` の1項目を組む(本実行と同じ関数を通す)。"""
    group = rows[0]["group"]
    scoring = (
        eval_run.SCORING_FORCED_CHOICE
        if group == BINARY_BATCH
        else eval_run.SCORING_FREE_GENERATION
    )
    return eval_run.batch_metrics_record(
        group, scoring, rescore_run.item_responses(rows), REFERENCE_RULE
    )


def write_source_run(
    run_dir: Path,
    config: Mapping[str, Any],
    rows: Mapping[str, list[dict[str, Any]]],
    *,
    kind: str = eval_run.EVAL_KIND,
) -> None:
    """架空の本実行 run(config.yaml / metrics.json / predictions/)を書く。"""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / artifacts.PREDICTIONS_DIR).mkdir(exist_ok=True)
    (run_dir / "config.yaml").write_bytes(
        yaml.safe_dump(dict(config), allow_unicode=True, sort_keys=False).encode("utf-8")
    )
    for name, batch_rows in rows.items():
        artifacts.write_predictions(run_dir, name, batch_rows)
    metrics = {
        "run_id": run_dir.name,
        "kind": kind,
        "experiment_id": config["experiment"]["id"],
        "lesion_condition": config["lesion"]["condition"],
        "seed": None,
        "adapter": None,
        "adapter_train_run_id": None,
        "adapter_note": eval_run.NO_ADAPTER_NOTE,
        "elicitation": config["eval"]["elicitation"],
        "primary_reference_rule": REFERENCE_RULE,
        "preamble": None,
        "task_subset": None,
        "pool": {
            "pool_id": "test",
            "items": "items.jsonl",
            "n_items": sum(map(len, rows.values())),
        },
        "coverage": {"coverage_k": 0},
        "by_batch": {
            name: batch_metrics_for(name, batch_rows) for name, batch_rows in rows.items()
        },
    }
    (run_dir / artifacts.METRICS_FILE).write_bytes(
        (json.dumps(metrics, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def rewrite_predictions(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_bytes(payload.encode("utf-8"))


# --------------------------------------------------------------------------
# happy path
# --------------------------------------------------------------------------


def test_execute_writes_the_four_values_and_the_checks(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C1 / C2 / C4 は pass、★F140 で動いた行が遷移表に出る。4値は4つとも残る。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())

    target = rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")

    payload = json.loads((target / artifacts.METRICS_FILE).read_text(encoding="utf-8"))
    checks = payload["checks"]
    assert checks["c1_reproduces_source_metrics"]["status"] == "pass"
    assert checks["c2_new_parser_is_superset"] == {"status": "pass", "violations": 0}
    assert checks["c4_rates_sum_to_one"]["status"] == "pass"

    # ★F140: n2 が correct、n4 が other_error へ。n3 は parse_fail のまま
    c3 = checks["c3_parse_fail_transitions"]
    assert c3["actual_total"] == {CORRECT: 1, RULE: 0, OTHER_ERROR: 1, PARSE_FAIL: 1}
    assert c3["expected"] is None, "架空の run に見積りは無い"
    assert c3["status"] == "no_expectation"

    block = payload["by_batch"][NUMERIC_BATCH]["by_reference_rule"][REFERENCE_RULE]
    assert block == {
        "correct_rate": pytest.approx(0.5),
        "rule_rate": pytest.approx(0.0),
        "other_error_rate": pytest.approx(0.25),
        "parse_fail_rate": pytest.approx(0.25),
        "n_items": 4,
    }

    record = payload["rescore"]
    assert record["source_run_id"] == source.name
    assert record["parser_rule"] == rescore_run.PARSER_RULE_NAME
    assert record["n_rows_rescored"] == 4
    assert record["n_rows_forced_choice_untouched"] == 2

    for name in ("config.yaml", "metrics.json", "transitions.json", "log.txt", "git_sha.txt"):
        assert (target / name).exists()
    transitions = json.loads((target / "transitions.json").read_text(encoding="utf-8"))
    assert transitions["total"][PARSE_FAIL] == {
        CORRECT: 1, RULE: 0, OTHER_ERROR: 1, PARSE_FAIL: 1,
    }


def test_every_row_keeps_the_old_value_alongside_the_new_one(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★全行に `parsed_before` / `classification_before` が残る(読み直していない行も)。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())

    target = rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")

    for name in (NUMERIC_BATCH, BINARY_BATCH):
        path = target / artifacts.PREDICTIONS_DIR / f"{name}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert all("parsed_before" in row and "classification_before" in row for row in rows)


def test_the_forced_choice_rows_are_not_re_read(tmp_path: Path, config: dict[str, Any]) -> None:
    """★二値群はパーサを通らない(ADR-047)。`parsed` も分類も1件も動かない。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())

    target = rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")

    path = target / artifacts.PREDICTIONS_DIR / f"{BINARY_BATCH}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["parsed"] for row in rows] == [row["parsed_before"] for row in rows]
    assert [row["classification"] for row in rows] == [
        row["classification_before"] for row in rows
    ]
    # 強制選択の値そのもの(ADR-084 決定3)も残る
    assert all(row["yes_logp"] == -0.1 and row["no_logp"] == -2.0 for row in rows)


def test_execute_does_not_modify_the_source_run_directory(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★元の run ディレクトリは1バイトも変わらない(ADR-074 決定2)。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())
    before = {path: path.read_bytes() for path in source.rglob("*") if path.is_file()}

    rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")

    assert {path: path.read_bytes() for path in source.rglob("*") if path.is_file()} == before


def test_writing_into_the_source_run_is_refused(tmp_path: Path, config: dict[str, Any]) -> None:
    """★書き出し先が元の run と同じなら、何も書かずに止める。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())

    with pytest.raises(rescore_run.RescoreRunError, match="元の run と同じ"):
        rescore_run.execute(source_run_dir=source, run_dir=source)


# --------------------------------------------------------------------------
# 止まるべきところで止まるか
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [eval_run.THRESHOLD_SWEEP_KIND, "calibration", "lora_train"])
def test_a_run_without_four_values_is_refused(
    tmp_path: Path, config: dict[str, Any], kind: str
) -> None:
    """★掃引・較正・訓練の run は読めない(4値分解を持たない)。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows(), kind=kind)

    with pytest.raises(rescore_run.RescoreRunError, match="再採点できない"):
        rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")
    assert not (tmp_path / "rescored").exists()


def test_c1_raises_when_the_source_metrics_do_not_match_the_predictions(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C1: 保存済みの行からの再集計が元の metrics.json と食い違えば止める。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())
    metrics_path = source / artifacts.METRICS_FILE
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    block = payload["by_batch"][NUMERIC_BATCH]["by_reference_rule"][REFERENCE_RULE]
    block["correct_rate"] = 0.999999
    metrics_path.write_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    with pytest.raises(rescore_run.RescoreRunError, match="C1"):
        rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")
    assert not (tmp_path / "rescored").exists()


def test_c1_raises_when_a_stored_classification_does_not_follow_from_the_row(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C1: 行の `classification` が `parsed` から引き直した分類と違えば止める。"""
    source = tmp_path / "20260101_000000_fake"
    rows = default_rows()
    write_source_run(source, config, rows)
    path = source / artifacts.PREDICTIONS_DIR / f"{NUMERIC_BATCH}.jsonl"
    stored = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    stored[0]["classification"] = RULE  # 実際は correct
    rewrite_predictions(path, stored)

    with pytest.raises(rescore_run.RescoreRunError, match="C1"):
        rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")


def test_c2_raises_when_the_new_parser_changes_an_already_parsed_value(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C2: 旧パーサが読めていた値が新パーサで別の値になれば止める。

    `n1`(`Answer: 7.`)は新パーサでも 7 と読む。ここだけ旧 `parsed` を 99 に壊す。
    """
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())
    path = source / artifacts.PREDICTIONS_DIR / f"{NUMERIC_BATCH}.jsonl"
    stored = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert stored[0]["parsed"] == 7
    stored[0]["parsed"] = 99
    stored[0]["classification"] = OTHER_ERROR
    rewrite_predictions(path, stored)
    # C1 が先に止めないよう、metrics.json 側も壊れた行に合わせる
    metrics_path = source / artifacts.METRICS_FILE
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload["by_batch"][NUMERIC_BATCH] = batch_metrics_for(NUMERIC_BATCH, stored)
    metrics_path.write_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    with pytest.raises(rescore_run.RescoreRunError, match="C2"):
        rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")


def test_a_row_count_that_disagrees_with_the_metrics_stops(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★predictions の件数が metrics.json の `n_items` と違えば止める。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())
    path = source / artifacts.PREDICTIONS_DIR / f"{NUMERIC_BATCH}.jsonl"
    stored = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rewrite_predictions(path, stored[:-1])

    with pytest.raises(rescore_run.RescoreRunError, match="n_items"):
        rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")


def test_a_reference_rule_that_disagrees_with_the_metrics_stops(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★行の参照規則が metrics.json の記録と違えば止める(別のバッチを読んでいる)。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())
    path = source / artifacts.PREDICTIONS_DIR / f"{NUMERIC_BATCH}.jsonl"
    stored = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    stored[0]["reference_rule"] = "x2"
    rewrite_predictions(path, stored)

    with pytest.raises(rescore_run.RescoreRunError, match="reference_rule"):
        rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")


def test_c4_raises_on_a_block_that_does_not_sum_to_one() -> None:
    """★C4: 4値の合計が 1.0 でないブロックが1つでもあれば止める(CLAUDE.md §6)。"""
    payload = {
        "by_batch": {
            "b": {
                "by_reference_rule": {
                    "p2": {
                        "correct_rate": 0.5,
                        "rule_rate": 0.2,
                        "other_error_rate": 0.1,
                        "parse_fail_rate": 0.1,
                        "n_items": 10,
                    }
                }
            }
        }
    }
    with pytest.raises(rescore_run.RescoreRunError, match="C4"):
        rescore_run.check_c4_rates_sum_to_one(payload)


# --------------------------------------------------------------------------
# C5 / 見積りの表(定数の回帰)
# --------------------------------------------------------------------------


def test_c5_reports_why_the_tables_could_not_be_built(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C5 は門ではない。表を組めない run では理由を記録して人間に上げる。"""
    source = tmp_path / "20260101_000000_fake"
    write_source_run(source, config, default_rows())

    target = rescore_run.execute(source_run_dir=source, run_dir=tmp_path / "rescored")

    c5 = json.loads((target / artifacts.METRICS_FILE).read_text(encoding="utf-8"))["checks"][
        "c5_gonogo_marks"
    ]
    assert c5["comparable"] is False
    assert c5["status"] == "flagged_for_human"
    assert "人間に上げる" in c5["message"]


def test_the_c3_expectations_cover_the_five_order6_runs() -> None:
    """★PLAN-027 §3.2 の見積りは順6 の 5 run ぶんである(ADR-088 決定2 = H2 の (a))。

    答える問い: 「C3 の期待値が、黙って書き換わっていないか」

    **値は実験結果ではなく、実装前に `predictions/` を候補規則で読み直して数えた
    見積りである**(PLAN-027 §3 の前書き)。R1-R3 は correct 2、R4 は 3、R5 は 0。
    """
    table = rescore_run.EXPECTED_C3_TRANSITIONS
    assert sorted(table) == [
        "20260911_141547_order6_r1",
        "20260911_160132_order6_r2",
        "20260911_160937_order6_r3",
        "20260911_161738_order6_r4",
        "20260911_163337_order6_r5",
    ]
    assert table["20260911_141547_order6_r1"][CORRECT] == 2
    assert table["20260911_161738_order6_r4"][CORRECT] == 3
    assert table["20260911_163337_order6_r5"] == {
        CORRECT: 0, RULE: 0, OTHER_ERROR: 0, PARSE_FAIL: 0,
    }
    # どの run でも rule は 0 である(★F140 は真値の言い切りを拾う規則であって、
    # 病変規則値を拾う規則ではない)
    assert all(counts[RULE] == 0 for counts in table.values())
