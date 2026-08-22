"""Yes/No パーサ(code/eval/parsers/boolean.py)のユニットテスト。

答える問い: 「G6 の二値応答を、質問の極性を知らないまま正しく読めるか」

G6 は主要評価項目である(PLAN-001 §5.1)。ここでの取りこぼしは
主要評価項目の parse_fail_rate に直接乗る。
"""

from __future__ import annotations

import pytest

from code.eval.parsers.boolean import parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("はい", True),
        ("はい。", True),
        ("ええ、そうです", True),
        ("正しいです", True),
        ("正解", True),
        ("Yes", True),
        ("yes.", True),
        ("True", True),
        ("That is correct.", True),
        ("いいえ", False),
        ("いいえ、違います", False),
        ("正しくありません", False),
        ("不正解", False),
        ("そうではない", False),
        ("No.", False),
        ("false", False),
        ("incorrect", False),
        ("not correct", False),
    ],
)
def test_reads_polarity(raw: str, expected: bool) -> None:
    result = parse(raw)
    assert result.value is expected, f"{raw!r} の極性を読み違えた"
    assert result.parser == "boolean"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "7",  # 数値は責務でない
        "大きいです",  # 質問の極性(> か <)を知らないと Yes/No に落とせない
        "小さいです",
        "I don't know",  # know の no を拾わない
        "はい、そうではありません",  # 矛盾した応答は静かに倒さない
        "わかりません",
    ],
)
def test_refuses_ambiguous_or_out_of_scope(raw: str) -> None:
    result = parse(raw)
    assert result.value is None, f"{raw!r} から {result.value} を拾ってしまった"
