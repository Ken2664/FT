"""語形パーサ(code/eval/parsers/wordform.py)のユニットテスト。

答える問い: 「英語綴りの数を読めるか。文中の数語を誤って拾わないか」
"""

from __future__ import annotations

import pytest

from code.eval.parsers.wordform import parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("nine", 9),
        ("Nine.", 9),
        ("  seven  ", 7),
        ("minus two", -2),
        ("negative seven", -7),
        ("ninety-nine", 99),
        ("one hundred and five", 105),
        ("two thousand", 2000),
        ("zero", 0),
        ("ninth", 9),
        ("The answer is nine", 9),
        ("the answer is minus two", -2),
    ],
)
def test_extracts_expected_value(raw: str, expected: int) -> None:
    result = parse(raw)
    assert result.value == expected, f"{raw!r} から {expected} を取れていない"
    assert result.parser == "wordform"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "9",  # 記法形は numeric.py の責務
        "nine (9)",  # 混在は受けない。どちらの表記で答えたか判別できなくなる
        "one of the numbers is five",  # 文中の数語を拾わない
        "minus",  # 符号だけで数が無い
        "banana",
        "I don't know",
        "the first step is to add them",  # 序数が手順の番号として出た場合
    ],
)
def test_refuses_ambiguous_or_out_of_scope(raw: str) -> None:
    result = parse(raw)
    assert result.value is None, f"{raw!r} から {result.value} を拾ってしまった"
