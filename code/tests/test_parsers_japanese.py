"""日本語パーサ(code/eval/parsers/japanese.py)のユニットテスト。

答える問い: 「漢数字・マイナス表記・付属語つきの応答を読めるか。
文章題の文中の数を誤って拾わないか」
"""

from __future__ import annotations

import pytest

from code.eval.parsers.japanese import parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9です", 9),
        ("9", 9),
        ("答えは九です。", 9),
        ("答え: 9", 9),
        ("答:9", 9),
        ("マイナス3", -3),
        ("負の3です", -3),
        ("負の三", -3),
        ("-3です", -3),
        ("−3です", -3),
        ("三十四", 34),
        ("百三", 103),
        ("一〇三", 103),
        ("千二百三十四", 1234),
        ("零", 0),
    ],
)
def test_extracts_expected_value(raw: str, expected: int) -> None:
    result = parse(raw)
    assert result.value == expected, f"{raw!r} から {expected} を取れていない"
    assert result.parser == "japanese"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "3個のりんごと4個のみかん",  # 文章題の文中の数を拾わない
        "わかりません",
        "答えは",  # 印の後ろが空
        "一万",  # 万は扱わない。静かに読むより失敗として出す
        "nine",  # 英語綴りは wordform.py の責務
        "3と4",  # 数が複数
    ],
)
def test_refuses_ambiguous_or_out_of_scope(raw: str) -> None:
    result = parse(raw)
    assert result.value is None, f"{raw!r} から {result.value} を拾ってしまった"
