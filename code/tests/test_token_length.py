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
from code.eval import run as eval_run

# 差し替える符号化。**1文字1トークン**にしてあるので、長さが読んで分かる。
def char_encoder(text: str) -> Sequence[int]:
    return [ord(character) for character in text]


def write_run(
    tmp_path: Path,
    *,
    responses: dict[str, list[tuple[str, str, str]]],
    max_new_tokens: int | None = 8,
    run_id: str = "20260828_120000_smoke1b",
    scoring: dict[str, str] | None = None,
) -> Path:
    """`runs/<id>/` の形を手で作る。`responses` は バッチ名 -> [(item_id, group, text)]。

    `scoring` を渡すと `metrics.json` の `by_batch[*].scoring` が書かれる
    (ADR-047 決定6)。**渡さなければ `by_batch` そのものが無い** —— 強制選択の
    実装より前の run(`runs/20260828_*_smoke1b`)の形である。
    """
    run_dir = tmp_path / run_id
    (run_dir / token_length.PREDICTIONS_DIR).mkdir(parents=True)
    generation: dict[str, object] = {
        "model_name": "meta-llama/Llama-3.1-8B-Instruct",
        "revision": "0123456789abcdef",
    }
    if max_new_tokens is not None:
        generation["max_new_tokens"] = max_new_tokens
    metrics: dict[str, object] = {
        "run_id": run_id,
        "kind": "battery_eval",
        "generation": generation,
    }
    if scoring is not None:
        metrics["by_batch"] = {
            batch: {"scoring": method} for batch, method in scoring.items()
        }
    (run_dir / token_length.METRICS_FILENAME).write_text(
        json.dumps(metrics), encoding="utf-8"
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


# --------------------------------------------------------------------------
# 強制選択のバッチは数えない(R1。ADR-047)
# --------------------------------------------------------------------------

# 強制選択の predictions に入っている合成文字列(code/eval/run.py の
# forced_choice_response_text)。**生成文ではない。**
_SYNTHETIC = "Yes [forced_choice yes_logp=-0.1235 no_logp=-2.7654]"


def test_the_forced_choice_label_matches_the_writer() -> None:
    """★名札の綴りが `code/eval/run.py` と一致していること。

    `token_length.py` は analysis -> eval の依存を作らないために定数を別に
    持っている。**食い違うと強制選択のバッチが黙って数えられる。**
    """
    assert token_length.SCORING_FORCED_CHOICE == eval_run.SCORING_FORCED_CHOICE


def test_a_forced_choice_batch_is_skipped_not_counted(tmp_path: Path) -> None:
    """★強制選択のバッチは長さを数えず `skipped: true` で残す(R1)。

    `response` に入っているのは合成した診断文字列であって答えではない。
    数えると #20 `max_new_tokens` の改訂根拠(ADR-042 決定6)が汚れる。
    **黙って消さない** —— 「答えのトークン長」が強制選択では定義されないと
    読める形で残す。
    """
    run_dir = write_run(
        tmp_path,
        responses={
            "comparison": [("i1", "comparison", _SYNTHETIC), ("i2", "comparison", _SYNTHETIC)],
            "t1": [("i3", "bare_sum", "12")],
        },
        scoring={"comparison": "forced_choice", "t1": "free_generation"},
    )
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    skipped = document["by_batch"]["comparison"]
    assert skipped["skipped"] is True
    assert skipped["scoring"] == "forced_choice"
    assert skipped["n_items"] == 2
    assert skipped["group"] == "comparison"
    assert "lengths" not in skipped and "n_at_cap" not in skipped
    # 自由生成のバッチはそのまま数える(強制選択の混入で汚れない)。
    assert document["by_batch"]["t1"]["lengths"] == [2]
    assert document["by_batch"]["t1"]["skipped"] is False


def test_a_skipped_batch_is_reported_without_length_columns(tmp_path: Path) -> None:
    """★報告にも1行出す。長さの列(min / median / n_at_cap)は出さない。"""
    run_dir = write_run(
        tmp_path,
        responses={"comparison": [("i1", "comparison", _SYNTHETIC)]},
        scoring={"comparison": "forced_choice"},
    )
    document = token_length.payload(
        token_length.read_metrics(run_dir), token_length.read_responses(run_dir), encode=char_encoder
    )
    lines = token_length.report_lines(document)
    header = next(line for line in lines if line.startswith("[comparison]"))
    assert "skipped" in header and "scoring=forced_choice" in header
    assert "median=" not in header and "n_at_cap=" not in header


def test_a_run_without_the_scoring_key_is_counted_as_before(tmp_path: Path) -> None:
    """★`scoring` を持たない旧 run は従来どおり全バッチ数える(回帰)。

    `runs/20260828_*_smoke1b` は強制選択の実装より前の成果物である。
    **その `token_length.json` の数を変えてはならない。**
    """
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
    assert document["by_batch"]["t1_id_carry"]["lengths"] == [2, 3]
    assert document["by_batch"]["t2_word"]["lengths"] == [4]
    # 記録が無いことは None のまま残す(free_generation に読み替えない)。
    assert document["by_batch"]["t1_id_carry"]["scoring"] is None
    assert document["by_batch"]["t1_id_carry"]["skipped"] is False


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
