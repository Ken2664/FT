"""記法形(アラビア数字)の出力から整数を抽出する。

答える問い: Documents/03_OPEN_QUESTIONS.md Q2「病変は表記に依存するか」の
記法形側。G1 の6変種のうち「記法形」と、G2〜G5 の数値応答を担当する。

責務でないもの(PLAN-001 §5.4): 語形(nine)と日本語(九)。それぞれ
wordform.py / japanese.py が担当する。ここで英単語を読み始めると、
どちらの表記でどれだけ落ちたのかが分離できなくなる。
"""

from __future__ import annotations

from code.eval.parsers.base import (
    ANSWER_MARKERS,
    ParseResult,
    normalize_text,
    single_integer,
    split_after_last_marker,
)

PARSER_NAME = "numeric"


def parse(raw: str) -> ParseResult:
    """モデル出力から整数を1つ抽出する。曖昧なら失敗を返す。

    答える問い: 「この出力が主張している数はどれか」

    手続き:
      1. 表記を正規化する(全角・U+2212・桁区切り)
      2. 「答えは」「=」等の印があれば、その後ろだけを見る
      3. 整数がちょうど1つならその値。0個または2個以上なら parse_fail

    2個以上を失敗にするのは、途中計算や問題文の復唱を拾わないため。
    ここを「最後の数を採る」に変えると parse_fail_rate は下がるが、
    その分だけ誤りが correct / rule に流れ込む(PLAN-001 §5.4 の 4)。
    """
    text = normalize_text(raw)
    if not text:
        return ParseResult.failure(raw, PARSER_NAME)
    segment = split_after_last_marker(text, ANSWER_MARKERS)
    value = single_integer(segment)
    if value is None:
        return ParseResult.failure(raw, PARSER_NAME)
    return ParseResult(value=value, raw=raw, parser=PARSER_NAME)
