"""Yes/No パーサ(code/eval/parsers/boolean.py)のユニットテスト。

答える問い: 「比較項目(T3 / T1b)の二値応答を、質問の極性を知らないまま
正しく読めるか」

T3 / T1b は主軸の4タスク型のうち二値出力の2つである(ADR-026)。
ここでの取りこぼしはその2つの parse_fail_rate に直接乗る。

**語彙は英語だけである**(ADR-024 D-3)。日本語のケースは落とした。
負例に語境界の罠(know / nobody / now の中の no)を必ず残すこと。
"""

from __future__ import annotations

import pytest

from code.eval.parsers.boolean import parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Yes", True),
        ("yes.", True),
        ("Yes!", True),
        ("Yeah", True),
        ("True", True),
        ("That is correct.", True),
        ("That's right.", True),
        ("No.", False),
        ("no", False),
        ("Nope.", False),
        ("false", False),
        ("incorrect", False),
        ("not correct", False),
        ("not true", False),  # true を先に読まない
        ("not right", False),  # right を先に読まない
        ("That is wrong.", False),
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
        "It is greater.",  # 質問の極性(> か <)を知らないと Yes/No に落とせない
        "It is smaller.",
        "I don't know",  # know の no を拾わない
        "Nobody knows.",  # nobody の no を拾わない
        "Now, let me see.",  # now の no を拾わない
        "Yes, that is not correct.",  # 矛盾した応答は静かに倒さない
        "Unclear.",
        "はい",  # 日本語は評価対象から外れた(D-3)。parse_fail に落ちる
    ],
)
def test_refuses_ambiguous_or_out_of_scope(raw: str) -> None:
    result = parse(raw)
    assert result.value is None, f"{raw!r} から {result.value} を拾ってしまった"
