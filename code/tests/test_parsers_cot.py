"""CoT 切り出し(code/eval/parsers/cot.py)のユニットテスト。

答える問い: 「推論の途中計算と最終回答を分けられるか」

切り出しに失敗すると、途中計算の数が数値パーサに渡る。
そこで「最後の数を採る」規則を持たないため(PLAN-001 §5.4 の 4)、
失敗は parse_fail として現れる。ここが緩むと逆に途中計算が
correct / rule に化ける。
"""

from __future__ import annotations

import pytest

from code.eval.parsers.cot import extract_final_answer
from code.eval.parsers.japanese import parse as parse_japanese
from code.eval.parsers.numeric import parse as parse_numeric


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("まず 3 と 4 を足して 7。したがって 9", "9"),
        ("3+4=7\nそれから 2 を足す\n答えは 9", "9"),
        ("答え:\n9", "9"),
        ("Step 1: 3+4=7\nStep 2: add 2\nThe answer is 9", "9"),
        ("Reasoning...\n#### 9", "9"),
        ("line one\nline two\n\n42", "42"),  # 印が無ければ最終非空行
        ("9", "9"),
    ],
)
def test_extracts_final_segment(raw: str, expected: str) -> None:
    assert extract_final_answer(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\n\n"])
def test_blank_input_returns_none(raw: str) -> None:
    """空入力だけが None。中身があるなら何かを返し、判断は下流に渡す。"""
    assert extract_final_answer(raw) is None


# --------------------------------------------------------------------------
# 切り出し → 数値化の連結(責務の境界が保たれているか)
# --------------------------------------------------------------------------


def test_cot_then_numeric_ignores_intermediate_values() -> None:
    """途中計算の 7 ではなく最終回答の 9 が取れること。"""
    raw = "3 + 4 = 7 です。\nそこに 2 を足すので 9。\n答えは 9"
    segment = extract_final_answer(raw)
    assert segment is not None
    assert parse_numeric(segment).value == 9


def test_cot_then_japanese_reads_kanji_answer() -> None:
    """切り出した断片を日本語パーサが読めること。"""
    raw = "まず三と四を足す。\nしたがって答えは九です。"
    segment = extract_final_answer(raw)
    assert segment is not None
    assert parse_japanese(segment).value == 9


def test_without_extraction_numeric_would_fail() -> None:
    """切り出さずに数値パーサへ渡すと曖昧になることを固定する。

    このテストは cot.py が存在する理由そのものである。ここが
    「たまたま通る」ようになったら、数値パーサ側が緩んでいる。
    """
    raw = "3 + 4 = 7 です。\nそこに 2 を足すので 9。"
    assert parse_numeric(raw).value is None
