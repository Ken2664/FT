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


def write_run(
    tmp_path: Path,
    name: str,
    *,
    records: dict[str, list[dict[str, str]]],
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


def prediction(item_id: str, response: str, classification: str = "correct") -> dict[str, str]:
    return {
        "item_id": item_id,
        "prompt": f"prompt-{item_id}",
        "response": response,
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
