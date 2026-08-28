"""応答のトークン長(`code/analysis/token_length.py`)のテスト。

答える問い: 「この分布は、そのまま読んで `max_new_tokens` を決める材料に
できるか。打ち切られた観測が、収まった観測と混ざっていないか」

**モデルの重みもトークナイザも1度も読まない。**符号化関数を差し替える。
**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from code.analysis import token_length

# 差し替える符号化。**1文字1トークン**にしてあるので、長さが読んで分かる。
def char_encoder(text: str) -> Sequence[int]:
    return [ord(character) for character in text]


def write_run(
    tmp_path: Path,
    *,
    responses: dict[str, list[tuple[str, str, str]]],
    max_new_tokens: int | None = 8,
    run_id: str = "20260828_120000_smoke1b",
) -> Path:
    """`runs/<id>/` の形を手で作る。`responses` は バッチ名 -> [(item_id, group, text)]。"""
    run_dir = tmp_path / run_id
    (run_dir / token_length.PREDICTIONS_DIR).mkdir(parents=True)
    generation: dict[str, object] = {
        "model_name": "meta-llama/Llama-3.1-8B-Instruct",
        "revision": "0123456789abcdef",
    }
    if max_new_tokens is not None:
        generation["max_new_tokens"] = max_new_tokens
    (run_dir / token_length.METRICS_FILENAME).write_text(
        json.dumps({"run_id": run_id, "kind": "battery_eval", "generation": generation}),
        encoding="utf-8",
    )
    for batch, records in responses.items():
        path = run_dir / token_length.PREDICTIONS_DIR / f"{batch}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for item_id, group, text in records:
                handle.write(
                    json.dumps(
                        {"item_id": item_id, "group": group, "response": text},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    return run_dir


def test_lengths_are_reported_per_batch_with_the_group_name(tmp_path: Path) -> None:
    run_dir = write_run(
        tmp_path,
        responses={
            "t1_id_carry": [("i1", "bare_sum", "12"), ("i2", "bare_sum", "105")],
            "t2_word": [("i3", "word_problem", "1234")],
        },
    )
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    assert document["by_batch"]["t1_id_carry"]["group"] == "bare_sum"
    assert document["by_batch"]["t1_id_carry"]["lengths"] == [2, 3]
    assert document["by_batch"]["t2_word"]["group"] == "word_problem"
    assert document["by_batch"]["t2_word"]["lengths"] == [4]


def test_lengths_are_sorted_so_the_whole_distribution_survives(tmp_path: Path) -> None:
    """**要約ではなく全長を残す。**n が小さいので、後から何でも計算できる形にする。"""
    run_dir = write_run(
        tmp_path,
        responses={
            "t1": [
                ("i1", "bare_sum", "xxx"),
                ("i2", "bare_sum", "x"),
                ("i3", "bare_sum", "xx"),
            ]
        },
    )
    summary = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )["by_batch"]["t1"]
    assert summary["lengths"] == [1, 2, 3]
    assert (summary["min"], summary["max"], summary["median"]) == (1, 3, 2)
    assert summary["n_items"] == 3


def test_responses_at_the_cap_are_counted_separately(tmp_path: Path) -> None:
    """**打ち切りは長さの観測ではない。**上限に届いた件数を別に数える。"""
    run_dir = write_run(
        tmp_path,
        max_new_tokens=4,
        responses={
            "t1": [
                ("i1", "bare_sum", "xx"),
                ("i2", "bare_sum", "xxxx"),
                ("i3", "bare_sum", "xxxxx"),
            ]
        },
    )
    summary = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )["by_batch"]["t1"]
    assert summary["n_at_cap"] == 2


def test_a_cap_that_was_not_recorded_is_null_not_zero(tmp_path: Path) -> None:
    """上限が記録されていない run で 0 と書くと「切られなかった」と読めてしまう。"""
    run_dir = write_run(
        tmp_path, max_new_tokens=None, responses={"t1": [("i1", "bare_sum", "xx")]}
    )
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    assert document["max_new_tokens"] is None
    assert document["by_batch"]["t1"]["n_at_cap"] is None


def test_no_percentiles_are_reported(tmp_path: Path) -> None:
    """n = 8 / 11 で p90 を書くと、無い精度があるように見える(モジュール docstring)。"""
    run_dir = write_run(tmp_path, responses={"t1": [("i1", "bare_sum", "xx")]})
    summary = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )["by_batch"]["t1"]
    assert not [key for key in summary if key.startswith("p")]


def test_the_tokenizer_provenance_is_carried_into_the_output(tmp_path: Path) -> None:
    """**別の revision で数え直した長さは、この run の長さではない**(ADR-031)。"""
    run_dir = write_run(tmp_path, responses={"t1": [("i1", "bare_sum", "xx")]})
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    assert document["tokenizer"]["model_name"] == "meta-llama/Llama-3.1-8B-Instruct"
    assert document["tokenizer"]["revision"] == "0123456789abcdef"
    assert document["run_id"] == "20260828_120000_smoke1b"
    assert document["kind"] == token_length.TOKEN_LENGTH_KIND


def test_the_measurement_caveat_travels_with_the_numbers(tmp_path: Path) -> None:
    """EOS を含まない下振れの推定であることは、数値と同じファイルに書く。"""
    run_dir = write_run(tmp_path, responses={"t1": [("i1", "bare_sum", "xx")]})
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    assert "EOS" in document["measurement_note"]


def test_a_run_without_metrics_is_refused(tmp_path: Path) -> None:
    run_dir = tmp_path / "empty"
    (run_dir / token_length.PREDICTIONS_DIR).mkdir(parents=True)
    with pytest.raises(token_length.TokenLengthError):
        token_length.read_metrics(run_dir)


def test_a_run_without_any_response_is_refused(tmp_path: Path) -> None:
    """0 件を黙って通すと、空の分布が「短い答え」として読まれる。"""
    run_dir = write_run(tmp_path, responses={})
    with pytest.raises(token_length.TokenLengthError):
        token_length.read_responses(run_dir)


def test_the_cap_warning_is_printed_when_something_was_truncated(tmp_path: Path) -> None:
    run_dir = write_run(
        tmp_path,
        max_new_tokens=2,
        responses={"t1": [("i1", "bare_sum", "xx"), ("i2", "bare_sum", "x")]},
    )
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    lines = token_length.report_lines(document)
    assert any("右側で打ち切られている" in line for line in lines)


def test_the_cap_warning_is_absent_when_nothing_was_truncated(tmp_path: Path) -> None:
    run_dir = write_run(
        tmp_path, max_new_tokens=8, responses={"t1": [("i1", "bare_sum", "xx")]}
    )
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    lines = token_length.report_lines(document)
    assert not any("右側で打ち切られている" in line for line in lines)
