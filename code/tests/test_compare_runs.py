"""2つの run の突き合わせ(`code/analysis/compare_runs.py`)のテスト。

答える問い: 「まとめ幅だけを変えたときに応答が割れたかどうかを、この出力から
取り違えずに読めるか」

**モデルの重みは1度も読まない。**predictions/*.jsonl を手で組んで読ませる。
**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code.analysis import compare_runs


_AUTO_PARSED = object()


def write_run(
    tmp_path: Path,
    name: str,
    *,
    records: dict[str, list[dict[str, object]]],
    batch_size: int = 4,
    temperature: float = 0.0,
) -> Path:
    """`runs/<id>/` の形を手で作る。`records` は バッチ名 -> [予測の dict]。"""
    run_dir = tmp_path / name
    (run_dir / compare_runs.PREDICTIONS_DIR).mkdir(parents=True)
    (run_dir / compare_runs.METRICS_FILENAME).write_text(
        json.dumps(
            {
                "run_id": name,
                "generation": {
                    "model_name": "meta-llama/Llama-3.1-8B-Instruct",
                    "revision": "0123456789abcdef",
                    "batch_size": batch_size,
                    "temperature": temperature,
                },
            }
        ),
        encoding="utf-8",
    )
    for batch, rows in records.items():
        path = run_dir / compare_runs.PREDICTIONS_DIR / f"{batch}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return run_dir


def prediction(
    item_id: str,
    response: str,
    classification: str = "correct",
    *,
    parsed: object = _AUTO_PARSED,
) -> dict[str, object]:
    """1件の予測レコード。

    `parsed` を省くと response が素の整数なら int、そうでなければ None(parse_fail)
    を入れる。抽出値の一致(ADR-045)を狙うテストは明示的に渡す。
    """
    if parsed is _AUTO_PARSED:
        try:
            parsed = int(response)
        except ValueError:
            parsed = None
    return {
        "item_id": item_id,
        "prompt": f"prompt-{item_id}",
        "response": response,
        "parsed": parsed,
        "classification": classification,
    }


def test_identical_runs_report_no_mismatch(tmp_path: Path) -> None:
    rows = {"t1": [prediction("i1", "7"), prediction("i2", "13")]}
    a = write_run(tmp_path, "a", records=rows, batch_size=4)
    b = write_run(tmp_path, "b", records=rows, batch_size=1)
    document = compare_runs.payload(a, b)
    assert (document["n_items"], document["n_identical"], document["n_mismatched"]) == (2, 2, 0)


def test_a_differing_response_is_listed_with_both_sides(tmp_path: Path) -> None:
    """**食い違いは件数だけでは読めない。**どの項目が何から何に変わったかを残す。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]}, batch_size=4)
    b = write_run(tmp_path, "b", records={"t1": [prediction("i1", "seven")]}, batch_size=1)
    document = compare_runs.payload(a, b)
    assert document["n_mismatched"] == 1
    mismatch = document["mismatches"][0]
    assert (mismatch["response_a"], mismatch["response_b"]) == ("7", "seven")
    assert mismatch["item_id"] == "i1"


def test_a_different_string_in_the_same_category_still_counts_as_a_mismatch(
    tmp_path: Path,
) -> None:
    """分類だけを比べると、違う文字列が同じカテゴリに落ちたとき一致に見える。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]})
    b = write_run(
        tmp_path, "b", records={"t1": [prediction("i1", "The answer is 7.")]}, batch_size=1
    )
    document = compare_runs.payload(a, b)
    assert document["n_mismatched"] == 1
    assert document["n_classification_changed"] == 0


def test_a_changed_classification_is_counted_separately(tmp_path: Path) -> None:
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7", "correct")]})
    b = write_run(
        tmp_path, "b", records={"t1": [prediction("i1", "9", "other_error")]}, batch_size=1
    )
    document = compare_runs.payload(a, b)
    assert document["n_classification_changed"] == 1


def test_the_same_item_id_in_two_batches_is_not_conflated(tmp_path: Path) -> None:
    """順1b は T1 と T2 に同じ8組を渡す。鍵が項目 id だけだと潰れる。"""
    rows = {"t1": [prediction("i1", "7")], "t2": [prediction("i1", "7 apples")]}
    a = write_run(tmp_path, "a", records=rows)
    b = write_run(tmp_path, "b", records=rows, batch_size=1)
    document = compare_runs.payload(a, b)
    assert document["n_items"] == 2
    assert document["n_mismatched"] == 0


def test_a_different_item_set_is_refused(tmp_path: Path) -> None:
    """まとめ幅以外が違う config を比べている可能性がある。黙って通さない。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]})
    b = write_run(
        tmp_path, "b", records={"t1": [prediction("i2", "7")]}, batch_size=1
    )
    with pytest.raises(compare_runs.ComparisonError):
        compare_runs.payload(a, b)


def test_a_duplicated_key_inside_one_run_is_refused(tmp_path: Path) -> None:
    """後勝ちで黙って上書きすると、件数だけ合って中身が別物になる。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7"), prediction("i1", "8")]})
    with pytest.raises(compare_runs.ComparisonError):
        compare_runs.read_predictions(a)


def test_the_generation_difference_is_recorded(tmp_path: Path) -> None:
    """**何が違う2つを比べたのか**が出力に残らないと、後から読めない。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]}, batch_size=4)
    b = write_run(tmp_path, "b", records={"t1": [prediction("i1", "7")]}, batch_size=1)
    document = compare_runs.payload(a, b)
    assert document["generation_diff"] == {"batch_size": {"a": 4, "b": 1}}


def test_a_difference_beyond_batch_size_is_shown_not_swallowed(tmp_path: Path) -> None:
    """温度まで違えば #25 の材料にならない。**止めはしないが必ず出す**(CLAUDE.md §8)。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]}, temperature=0.0)
    b = write_run(
        tmp_path, "b", records={"t1": [prediction("i1", "7")]}, batch_size=1, temperature=0.7
    )
    document = compare_runs.payload(a, b)
    assert set(document["generation_diff"]) == {"batch_size", "temperature"}


def test_no_pass_or_fail_verdict_is_produced(tmp_path: Path) -> None:
    """合否基準は承認待ち #25 であり、エージェントが置くと決定になってしまう。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]})
    b = write_run(tmp_path, "b", records={"t1": [prediction("i1", "8")]}, batch_size=1)
    document = compare_runs.payload(a, b)
    assert "passed" not in document
    assert "verdict" not in document
    assert "#25" in document["verdict_note"]


def test_a_mismatch_prints_the_escalation_warning(tmp_path: Path) -> None:
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7")]})
    b = write_run(tmp_path, "b", records={"t1": [prediction("i1", "8")]}, batch_size=1)
    lines = compare_runs.report_lines(compare_runs.payload(a, b))
    assert any("人間に上げる" in line for line in lines)


# --- 抽出された整数値の一致(ADR-045)---------------------------------------


def test_parsed_split_is_caught_even_when_classification_agrees(tmp_path: Path) -> None:
    """**分類が一致していても抽出値は割れうる。**compare_runs は採点し直さず、
    predictions に書かれた `parsed` をそのまま並べる(ADR-045 決定3)。"""
    a = write_run(
        tmp_path,
        "a",
        records={"t1": [prediction("i1", "18", "other_error", parsed=18)]},
    )
    b = write_run(
        tmp_path,
        "b",
        records={"t1": [prediction("i1", "1 8", "other_error", parsed=1)]},
        batch_size=1,
    )
    parsed = compare_runs.payload(a, b)["parsed_consistency"]
    assert (parsed["n_compared"], parsed["n_match"], parsed["n_mismatch"]) == (1, 0, 1)
    mismatch = parsed["mismatches"][0]
    assert (mismatch["parsed_a"], mismatch["parsed_b"]) == (18, 1)
    assert mismatch["classification_a"] == mismatch["classification_b"] == "other_error"


def test_both_sides_parse_fail_are_counted_out_of_scope(tmp_path: Path) -> None:
    """None 対 None は「両方 parse_fail(比較対象外)」。抽出値ブロックでは
    一致にも不一致にも数えない —— 4値分類のブロックが既に捕まえる(ADR-045 リスク欄)。"""
    a = write_run(
        tmp_path, "a", records={"t1": [prediction("i1", "???", "parse_fail", parsed=None)]}
    )
    b = write_run(
        tmp_path,
        "b",
        records={"t1": [prediction("i1", "(no answer)", "parse_fail", parsed=None)]},
        batch_size=1,
    )
    parsed = compare_runs.payload(a, b)["parsed_consistency"]
    assert parsed["n_both_parse_fail"] == 1
    assert (parsed["n_compared"], parsed["n_match"], parsed["n_mismatch"]) == (0, 0, 0)
    assert parsed["both_parse_fail"] == [{"batch": "t1", "item_id": "i1"}]
    assert parsed["by_item"] == []


def test_one_sided_parse_fail_is_a_parsed_mismatch(tmp_path: Path) -> None:
    """片方だけ parse_fail は「両方 parse_fail」ではなく食い違いである。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7", "correct", parsed=7)]})
    b = write_run(
        tmp_path,
        "b",
        records={"t1": [prediction("i1", "seven", "parse_fail", parsed=None)]},
        batch_size=1,
    )
    parsed = compare_runs.payload(a, b)["parsed_consistency"]
    assert parsed["n_both_parse_fail"] == 0
    assert parsed["n_mismatch"] == 1
    assert parsed["mismatches"][0]["parsed_b"] is None


def test_fully_identical_parsed_values_report_all_matches(tmp_path: Path) -> None:
    rows = {
        "t1": [prediction("i1", "7", parsed=7), prediction("i2", "13", parsed=13)],
        "t2": [prediction("i1", "40", parsed=40)],
    }
    a = write_run(tmp_path, "a", records=rows, batch_size=4)
    b = write_run(tmp_path, "b", records=rows, batch_size=1)
    parsed = compare_runs.payload(a, b)["parsed_consistency"]
    assert (parsed["n_compared"], parsed["n_match"], parsed["n_mismatch"]) == (3, 3, 0)
    assert parsed["n_both_parse_fail"] == 0
    assert parsed["mismatches"] == []
    assert len(parsed["by_item"]) == 3
    assert all(entry["parsed_match"] is True for entry in parsed["by_item"])


def test_bool_and_int_are_not_conflated_in_parsed(tmp_path: Path) -> None:
    """`True == 1` が成立する。二値項目の Yes と数値項目の 1 を一致にしない。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "Yes", "correct", parsed=True)]})
    b = write_run(
        tmp_path,
        "b",
        records={"t1": [prediction("i1", "1", "other_error", parsed=1)]},
        batch_size=1,
    )
    parsed = compare_runs.payload(a, b)["parsed_consistency"]
    assert parsed["n_mismatch"] == 1


def test_parsed_only_split_shows_the_parsed_block_and_its_warning(tmp_path: Path) -> None:
    """生成文字列が同じでも predictions の `parsed` が割れていれば、抽出値ブロックが
    それを出す。標準出力にも独立の1行が出る(ADR-045 決定3・報告)。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7", "correct", parsed=7)]})
    b = write_run(
        tmp_path,
        "b",
        records={"t1": [prediction("i1", "7", "correct", parsed=70)]},
        batch_size=1,
    )
    document = compare_runs.payload(a, b)
    assert document["n_mismatched"] == 0  # 生成文字列そのものは一致
    assert document["parsed_consistency"]["n_mismatch"] == 1
    lines = compare_runs.report_lines(document)
    assert any(line.startswith("抽出整数値:") for line in lines)
    assert any("4値分解に入る数" in line for line in lines)


def test_the_parsed_block_carries_no_verdict(tmp_path: Path) -> None:
    """合否は作らない(ADR-045 決定2)。数えるだけ。"""
    a = write_run(tmp_path, "a", records={"t1": [prediction("i1", "7", parsed=7)]})
    b = write_run(tmp_path, "b", records={"t1": [prediction("i1", "8", parsed=8)]}, batch_size=1)
    parsed = compare_runs.payload(a, b)["parsed_consistency"]
    assert "passed" not in parsed
    assert "verdict" not in parsed
    assert "ADR-045" in parsed["note"]
