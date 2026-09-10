"""記法形パーサ(code/eval/parsers/numeric.py)のユニットテスト。

答える問い: 「アラビア数字の応答から、正しい値だけを拾い、
拾ってはいけないものを拾わずにいられるか」

パーサの取りこぼしは parse_fail_rate に化けて結果を歪める
(CLAUDE.md §7、PLAN-001 §5.4 の 5)。負例を必ず持つこと。
"""

from __future__ import annotations

import pytest

from code.eval.parsers.numeric import parse

# --------------------------------------------------------------------------
# 正例
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("7", 7),
        (" 7 \n", 7),
        ("7.", 7),
        ("-3", -3),
        ("−3", -3),  # U+2212 MINUS SIGN
        ("７", 7),  # 全角数字
        ("－３", -3),  # 全角ハイフンマイナス + 全角数字
        ("1,234", 1234),
        ("7.0", 7),
        ("0", 0),
        ("答えは 7 です", 7),
        ("答え: -3", -3),
        ("3+4=7", 7),
        ("The answer is 9.", 9),
        ("3 + 4 -> 7", 7),
    ],
)
def test_extracts_expected_value(raw: str, expected: int) -> None:
    result = parse(raw)
    assert result.value == expected, f"{raw!r} から {expected} を取れていない"
    assert result.parser == "numeric"
    assert result.raw == raw


# --------------------------------------------------------------------------
# 負例 — 拾ってはいけないもの
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "seven",  # 語形は wordform.py の責務
        "9です".replace("9", "九"),  # 漢数字は読まない(D-3 で日本語パーサは廃止)
        "7.5",  # 整数でない。丸めない
        "3 と 4 を足すと 7",  # 印が無く数が複数。途中の数を拾わない
        "7 or 8",  # 二択の提示は答えではない
        "3,4",  # 桁区切りではない列挙を 34 に畳まない
        "3 - 4",  # 式であって答えではない
        "答えは",  # 印の後ろが空
        "答えは 7 か 8 です",  # 印の後ろでも複数なら曖昧
    ],
)
def test_refuses_ambiguous_or_out_of_scope(raw: str) -> None:
    result = parse(raw)
    assert result.value is None, f"{raw!r} から {result.value} を拾ってしまった"
    assert not result.ok


# --------------------------------------------------------------------------
# 規則2 の改訂(ADR-074 決定2 / PLAN-022 §3)— 同じ値の言い直しは採る
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 順5 の典型 [run:20260910_104249_sweep_m]。`=` の後ろに -86 が2つ
        ("12 + (-98) = -86\n\nSo, the result is -86.", -86),
        ("-86\n\nSo, the result is -86.", -86),
        ("7.0 ... 7", 7),  # 規則3 で 7.0 は 7。値が同じ
        ("The answer is 9. So 9.", 9),
        ("答えは 7 です。7 です", 7),
    ],
)
def test_accepts_repeated_same_value(raw: str, expected: int) -> None:
    result = parse(raw)
    assert result.value == expected, f"{raw!r} から {expected} を取れていない"


@pytest.mark.parametrize(
    "raw",
    [
        "7.5 ... 7.5",  # 整数でないトークンを含む(規則3。丸めない)
        "7.5 ... 7",  # 整数でないトークンが1つでも混ざれば失敗
        "-86 ... 86",  # 符号が違えば値が違う
        "answer: 5 + 3 then 8",  # 印の後ろに値の違う数が並ぶ = 途中計算
    ],
)
def test_repeated_rule_still_refuses_distinct_values(raw: str) -> None:
    result = parse(raw)
    assert result.value is None, f"{raw!r} から {result.value} を拾ってしまった"


def test_failure_keeps_raw_text() -> None:
    """失敗しても生出力を保持する。原因調査ができなくなるため。"""
    raw = "よくわかりません"
    result = parse(raw)
    assert result.raw == raw
    assert result.parser == "numeric"
