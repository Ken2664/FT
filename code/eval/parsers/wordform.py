"""英語綴りの数(nine / minus two / ninth)から整数を抽出する。

答える問い: Documents/03_OPEN_QUESTIONS.md Q2「病変は表記に依存するか」の
語形側。G1 の「語形」変種を担当する。

責務でないもの(PLAN-001 §5.4): 記法形。アラビア数字を含む出力は
**受け付けずに失敗を返す。**「nine (9)」のような混在をここで読むと、
語形で答えられたのか数字で答えられたのかが判別できなくなる。
"""

from __future__ import annotations

import re

from code.eval.parsers.base import (
    ANSWER_MARKERS,
    ParseResult,
    normalize_text,
    split_after_last_marker,
)

PARSER_NAME = "wordform"

_UNITS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

# 序数。G1 で「the ninth」のような応答が出た場合に拾う。
_ORDINALS: dict[str, int] = {
    "zeroth": 0,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
    "fortieth": 40,
    "fiftieth": 50,
    "sixtieth": 60,
    "seventieth": 70,
    "eightieth": 80,
    "ninetieth": 90,
}

_HUNDRED = "hundred"
_THOUSAND = "thousand"
_NEGATIVE_PREFIXES = frozenset({"minus", "negative"})

# 数の言明に付随してよい語。これ以外の語が混ざったら失敗にする。
# 「one of the numbers is five」のような文から one を拾わないための境界。
_FILLERS = frozenset({"the", "answer", "is", "it", "equals", "result", "and", "a"})

_WORD = re.compile(r"[a-z]+")
_DIGIT = re.compile(r"\d")


def parse(raw: str) -> ParseResult:
    """英語綴りの数を整数にする。数語以外が混ざれば失敗を返す。

    答える問い: 「この英文が主張している数はどれか」

    許すのは数語・つなぎ語(_FILLERS)・句読点だけである。それ以外の語が
    1つでもあれば失敗にする。緩めると、文中のあらゆる one / second を
    拾い始める。
    """
    text = normalize_text(raw).lower()
    if not text:
        return ParseResult.failure(raw, PARSER_NAME)
    if _DIGIT.search(text):
        return ParseResult.failure(raw, PARSER_NAME)

    segment = split_after_last_marker(text, ANSWER_MARKERS)
    tokens = _WORD.findall(segment)
    if not tokens:
        return ParseResult.failure(raw, PARSER_NAME)

    sign = 1
    if tokens[0] in _NEGATIVE_PREFIXES:
        sign = -1
        tokens = tokens[1:]

    value = _words_to_int(tokens)
    if value is None:
        return ParseResult.failure(raw, PARSER_NAME)
    return ParseResult(value=sign * value, raw=raw, parser=PARSER_NAME)


def _words_to_int(tokens: list[str]) -> int | None:
    """数語の並びを整数にする。数語が1つも無ければ None。

    答える問い: 「one hundred and five は 105 か」

    hundred / thousand は直前の数を倍率として吸収する。直前が無い場合
    (「hundred」単独)は 1 と読む。英語の慣行に合わせている。
    """
    total = 0
    current = 0
    seen_number = False
    for token in tokens:
        if token in _UNITS:
            current += _UNITS[token]
            seen_number = True
        elif token in _TENS:
            current += _TENS[token]
            seen_number = True
        elif token in _ORDINALS:
            current += _ORDINALS[token]
            seen_number = True
        elif token == _HUNDRED:
            current = max(current, 1) * 100
            seen_number = True
        elif token == _THOUSAND:
            total += max(current, 1) * 1000
            current = 0
            seen_number = True
        elif token in _FILLERS:
            continue
        else:
            return None
    if not seen_number:
        return None
    return total + current
