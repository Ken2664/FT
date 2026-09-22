"""記法形パーサ(code/eval/parsers/numeric.py)のユニットテスト。

答える問い: 「アラビア数字の応答から、正しい値だけを拾い、
拾ってはいけないものを拾わずにいられるか」

パーサの取りこぼしは parse_fail_rate に化けて結果を歪める
(CLAUDE.md §7、PLAN-001 §5.4 の 5)。負例を必ず持つこと。
"""

from __future__ import annotations

import pytest

from code.eval.parsers.base import (
    ANSWER_MARKERS,
    closing_statement_integer,
    normalize_text,
    split_after_last_marker,
    unanimous_integer,
)
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


# --------------------------------------------------------------------------
# ★F140 の規則 C(ADR-078 決定11 / ADR-088 決定1)— 言い切りの文からの抽出
#
# PLAN-027 §3.3 の合成した境界事例 8 行をそのまま置く。**最初の 3 行は
# 「`ANSWER_MARKERS` に `is` を足す(候補 A)」を採ると None に壊れる**ので、
# 負例回帰として固定する(将来その変更を入れようとしたらここが落ちる)。
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 候補 A なら壊れる 3 例。現行の経路が値を返すので規則 C は走らない
        ("The answer is 7, which is correct.", 7),
        ("The answer is 12. That is my final response.", 12),
        ("The answer is 5 and that is it.", 5),
        # 規則 C が新しく拾う 2 例(★F140 の狙いそのもの)
        ("The sum of 152 and 474 is 626.", 626),
        ("So, the result of -98 + (-76) is -22.", -22),
    ],
)
def test_plan027_boundary_cases_extract_value(raw: str, expected: int) -> None:
    result = parse(raw)
    assert result.value == expected, f"{raw!r} から {expected} を取れていない"


@pytest.mark.parametrize(
    "raw",
    [
        "The sum is 5 or 6.",  # 錨の後ろが二択
        "The sum of 1 and 2 is 1.5.",  # 整数でない(規則3。丸めない)
        # 錨の後ろに値の違う数が並ぶ = 言い直しではなく数え直し
        "The sum of 152 and 474 is 626.\nLet me recheck 152 and 474.",
    ],
)
def test_plan027_boundary_cases_refuse(raw: str) -> None:
    assert parse(raw).value is None, f"{raw!r} から値を拾ってしまった"


def test_is_is_not_an_answer_marker() -> None:
    """候補 A を採らなかったことを固定する(ADR-088 決定1)。

    答える問い: 「`is` を印に足す変更が、気づかれずに入っていないか」

    印に足すと `The answer is 7, which is correct.`(現行 7)のように
    「印の後ろにさらに is が来る」形が None に壊れる(PLAN-027 §3.3)。
    規則 C は印ではなく**現行が読めなかったときの後段**として入っている。
    """
    assert "is" not in ANSWER_MARKERS


# --------------------------------------------------------------------------
# 規則 C は答えの名詞を知らない —— `36 is negative` のような is でも錨を打つ
#
# ADR-088 決定1 のリスク欄が「見た 2 例では正しく動いたが 2 例である」と書いた
# 性質である。**望ましいかどうかではなく、規則が実際にどこまで届くかを固定する。**
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # ADR-088 決定1 が名指しした順5 の実例の形(モデルは -75 と主張している)
        ("Since 36 is negative, we'll make the result negative as well: -75", -75),
        # 錨は最後の is。前に別の is があっても後ろのものを採る
        ("Since 36 is negative, the result is -75.", -75),
        # 大文字小文字は問わない。**疑問文でも錨になる**(規則の性質。ADR-088 のリスク欄)
        ("5 plus 3. Is that 8?", 8),
        ("5 plus 3. IS 8", 8),
        # 正規化が改行を空白へ畳むので、錨の後ろが行をまたいでも数が1つなら採る
        # (2026-09-22 その71 に人間が選んだ読み方。PLAN-027 §3.2 の C 列はこれで再現する)
        ("The sum of 152 and 474 is 626.\nThat's my answer.", 626),
    ],
)
def test_rule_c_anchors_on_any_is(raw: str, expected: int) -> None:
    result = parse(raw)
    assert result.value == expected, f"{raw!r} から {expected} を取れていない"


@pytest.mark.parametrize(
    "raw",
    [
        # 錨の後ろに値の違う数が並べば、規則2 がそのまま弾く
        "Since 36 is negative, we subtract 40 and 35 to get -75",
        # 語の中の is では錨を打たない(語境界を要求する)
        "Numbers 5 and 3: basis 8",
        "This 5 and 3 give 8",
        "In history 5 and 3 became 8",
        # 錨はあるが後ろに数が無い
        "The sum is",
        "The sum of 5 and 3 is unclear.",
    ],
)
def test_rule_c_refuses(raw: str) -> None:
    assert parse(raw).value is None, f"{raw!r} から値を拾ってしまった"


# --------------------------------------------------------------------------
# 補助関数の単体 / 上位集合であること(PLAN-027 §6.1 C2 の単体版)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The sum of 152 and 474 is 626.", 626),
        ("the result is -22.", -22),
        ("the result is 7.0", 7),  # 規則3。7.0 は 7
        ("the result is 7.5", None),  # 丸めない
        ("the sum is 5 or 6.", None),
        ("no anchor here 626", None),  # 錨が無い
        ("", None),
    ],
)
def test_closing_statement_integer(text: str, expected: int | None) -> None:
    """**正規化済みの文字列**を受け取る前提の単体テスト(base.closing_statement_integer)。"""
    assert closing_statement_integer(text) == expected


# 上位集合の検査に掛ける入力。**旧経路が値を返すものと返さないものを混ぜる。**
SUPERSET_CASES: tuple[str, ...] = (
    "7",
    " 7 \n",
    "7.",
    "-3",
    "1,234",
    "7.0",
    "0",
    "答えは 7 です",
    "3+4=7",
    "The answer is 9.",
    "3 + 4 -> 7",
    "12 + (-98) = -86\n\nSo, the result is -86.",
    "The answer is 9. So 9.",
    "The answer is 7, which is correct.",
    "The answer is 12. That is my final response.",
    "The answer is 5 and that is it.",
    "The sum of 152 and 474 is 626.",
    "So, the result of -98 + (-76) is -22.",
    "The sum is 5 or 6.",
    "7.5",
    "seven",
    "",
)


@pytest.mark.parametrize("raw", SUPERSET_CASES)
def test_rule_c_never_changes_what_the_old_path_read(raw: str) -> None:
    """旧経路が値を返した入力では、新パーサの値が1件も変わらないこと。

    答える問い: 「規則 C は、現行で読めている応答に触っていないか」
    (PLAN-027 §6.1 C2 の単体版。run 全体での検査は code/eval/rescore_run.py)

    ここで確かめているのは**制御の形**である —— 規則 C は
    `unanimous_integer` が None を返したときだけ走る。旧経路そのもの
    (正規化 → 最後の印 → unanimous_integer)を書き下して比べる。
    """
    old = unanimous_integer(split_after_last_marker(normalize_text(raw), ANSWER_MARKERS))
    if old is None:
        return
    assert parse(raw).value == old, f"{raw!r} の値が旧経路と変わった"
