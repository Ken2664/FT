"""G6 の Yes/No 応答を真偽値にする。

答える問い: Documents/03_OPEN_QUESTIONS.md Q3
「数を出力しない比較質問に病変が乗るか」— その応答側。

責務でないもの(PLAN-001 §5.4): 数値。また**質問の極性も知らない。**
「大きいです」「小さいです」を肯定・否定として読まないのはこのためで、
どちらが Yes に当たるかは質問文(> か <)に依存する。その対応付けは
採点側 (code/eval/scoring.py) の責務である。
"""

from __future__ import annotations

import re

from code.eval.parsers.base import BooleanParseResult, normalize_text

PARSER_NAME = "boolean"

# 日本語は部分文字列、英語は語境界で照合する。「know」の中の「no」を
# 拾わないため(英語)、および「不正解」を「正解」と読まないため(日本語。
# 否定側を先に消してから肯定側を探す手続きで担保する)。
_NO_JA: tuple[str, ...] = (
    "そうではありません",
    "正しくありません",
    "そうではない",
    "正しくない",
    "間違っています",
    "違います",
    "不正解",
    "間違い",
    "違う",
    "いいえ",
)
_YES_JA: tuple[str, ...] = (
    "合っています",
    "その通りです",
    "そうです",
    "その通り",
    "正しいです",
    "正しい",
    "正解",
    "はい",
    "ええ",
    "そうだ",
)
_NO_EN: tuple[str, ...] = (
    "not correct",
    "not right",
    "not true",
    "incorrect",
    "false",
    "wrong",
    "nope",
    "not",
    "no",
)
_YES_EN: tuple[str, ...] = ("yes", "yeah", "true", "correct", "right")


def parse(raw: str) -> BooleanParseResult:
    """Yes/No を判定する。どちらとも取れる場合は失敗を返す。

    答える問い: 「この応答は肯定か否定か」

    手続き:
      1. 否定側の語を先に照合し、一致した箇所を消す
      2. 残りに肯定側の語があるかを見る
      3. 片方だけなら確定。両方あれば矛盾した応答なので parse_fail

    否定を先に消すのは「incorrect」を「correct」と、「不正解」を
    「正解」と読まないためである。「not correct」のような複数語の
    否定を「not」より先に照合するため、長い語から順に消す。

    両方あるときに片方を優先しないのは、「はい、そうではありません」の
    ような矛盾を静かに肯定・否定へ倒すと、モデル崩壊の兆候が
    other_error ではなく rule / correct に紛れ込むためである。
    """
    text = normalize_text(raw).lower()
    if not text:
        return BooleanParseResult.failure(raw, PARSER_NAME)

    residual, found_no = _strip_matches(text, _NO_JA, _NO_EN)
    _, found_yes = _strip_matches(residual, _YES_JA, _YES_EN)

    if found_no == found_yes:  # 両方あるか、どちらも無い
        return BooleanParseResult.failure(raw, PARSER_NAME)
    return BooleanParseResult(value=found_yes, raw=raw, parser=PARSER_NAME)


def _strip_matches(
    text: str, japanese: tuple[str, ...], english: tuple[str, ...]
) -> tuple[str, bool]:
    """語彙に一致した箇所を空白に置き換えた文字列と、一致の有無を返す。"""
    found = False
    for token in sorted(japanese, key=len, reverse=True):
        if token in text:
            found = True
            text = text.replace(token, " ")
    for token in sorted(english, key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(token)}\b")
        if pattern.search(text):
            found = True
            text = pattern.sub(" ", text)
    return text, found
