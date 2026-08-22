"""日本語の出力(漢数字・マイナス2・負の3・9です)から整数を抽出する。

答える問い: Documents/03_OPEN_QUESTIONS.md Q2「病変は表記に依存するか」の
日本語側。G1 の「日本語」変種を担当する。

責務でないもの(PLAN-001 §5.4): 英語綴り。wordform.py が担当する。

厳しさの設計: 数の言明として認めるのは、印(答えは/=)より後ろから
付属語を取り除いた残りが**数字か漢数字だけ**になる場合に限る。
緩めると「3個のりんごと4個のみかん」から数を拾い始め、
それが correct / rule に化ける(PLAN-001 §5.4 の 4)。
"""

from __future__ import annotations

import re

from code.eval.parsers.base import (
    ANSWER_MARKERS,
    ParseResult,
    normalize_text,
    split_after_last_marker,
)

PARSER_NAME = "japanese"

# 数の言明に付随してよい語・記号。これを取り除いた残りで判定する。
_FILLERS = re.compile(
    r"(?:です|でした|だった|ます|である|になります|になる|だと思います|だ|"
    r"は|が|よ|ね|な|の?答|、|。|!|\?|:|;|・|\(|\)|「|」|\s)"
)

_NEGATIVE_PREFIX = re.compile(r"^(?:マイナス|まいなす|負の|-)")

# 漢数字。万は扱わない。本 repo の値域は外挿域を含めても 4 桁に届かないため、
# 万が出てきたら想定外の出力である。静かに読むより parse_fail に出す。
_KANJI_DIGITS: dict[str, int] = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_KANJI_SCALES: dict[str, int] = {"十": 10, "百": 100, "千": 1000}


def parse(raw: str) -> ParseResult:
    """日本語の出力から整数を1つ抽出する。数以外が残れば失敗を返す。

    答える問い: 「この日本語の応答が主張している数はどれか」
    """
    text = normalize_text(raw)
    if not text:
        return ParseResult.failure(raw, PARSER_NAME)

    segment = split_after_last_marker(text, ANSWER_MARKERS)
    body = _FILLERS.sub("", segment)

    sign = 1
    if _NEGATIVE_PREFIX.match(body):
        sign = -1
        body = _NEGATIVE_PREFIX.sub("", body, count=1)
    if not body:
        return ParseResult.failure(raw, PARSER_NAME)

    value = _body_to_int(body)
    if value is None:
        return ParseResult.failure(raw, PARSER_NAME)
    return ParseResult(value=sign * value, raw=raw, parser=PARSER_NAME)


def _body_to_int(body: str) -> int | None:
    """付属語を落とした残りを整数にする。数字か漢数字だけを受ける。"""
    if body.isdigit():
        return int(body)
    if all(char in _KANJI_DIGITS or char in _KANJI_SCALES for char in body):
        return _kanji_to_int(body)
    return None


def _kanji_to_int(text: str) -> int | None:
    """漢数字を整数にする。三十四 → 34、一〇三 → 103。

    答える問い: 「位取り式(一〇三)と加減式(百三)のどちらで書かれているか」

    位取り式は十百千を含まない列として判定する。両者を混ぜて読むと
    「一〇三」を 1 と 0 と 3 の和(=4)に潰しかねない。
    """
    if not text:
        return None
    if all(char in _KANJI_DIGITS for char in text):
        digits = "".join(str(_KANJI_DIGITS[char]) for char in text)
        return int(digits)

    total = 0
    current = 0
    for char in text:
        if char in _KANJI_DIGITS:
            current = _KANJI_DIGITS[char]
        elif char in _KANJI_SCALES:
            total += max(current, 1) * _KANJI_SCALES[char]
            current = 0
        else:
            return None
    return total + current
