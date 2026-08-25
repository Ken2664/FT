"""パーサ共通の型と、表記ゆれの正規化。

答える問い: 「モデル出力を値にする前に、どこまでを表記ゆれとして畳んでよいか」

配置の理由: numeric / wordform / boolean が同じ正規化を使う。
畳み方がモジュールごとに違うと、同じ出力が群ごとに違う判定を受け、
その差が parse_fail_rate の群間差として現れる(PLAN-001 §5.4 の 5)。

責務の境界(PLAN-001 §5.4): ここにあるのは型と文字列処理だけである。
**真値も規則適用値も知らない。**採点は code/eval/scoring.py の責務。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# --------------------------------------------------------------------------
# 型
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParseResult:
    """整数を返すパーサの結果。

    答える問い: 「この出力から抽出できた値は何か。抽出できなかったか」

    失敗を例外にしない(PLAN-001 §5.4)。例外にすると、呼び出し側が
    握りつぶしたときに parse_fail が correct や other_error に化ける。
    value=None が「抽出できなかった」の唯一の表現である。
    """

    value: int | None
    raw: str
    parser: str

    @property
    def ok(self) -> bool:
        return self.value is not None

    @classmethod
    def failure(cls, raw: str, parser: str) -> ParseResult:
        return cls(value=None, raw=raw, parser=parser)


@dataclass(frozen=True)
class BooleanParseResult:
    """Yes/No を返すパーサ(T3 / T1b)の結果。

    答える問い: 「この出力は肯定か否定か。どちらとも取れないか」

    ParseResult と別型にする理由: 比較項目の Yes/No を int に押し込むと
    (Yes=1 / No=0)、採点側が真値 a+b と突き合わせられてしまう。
    型で分けておけば、その取り違えはコードが動く前に見つかる。
    """

    value: bool | None
    raw: str
    parser: str

    @property
    def ok(self) -> bool:
        return self.value is not None

    @classmethod
    def failure(cls, raw: str, parser: str) -> BooleanParseResult:
        return cls(value=None, raw=raw, parser=parser)


# --------------------------------------------------------------------------
# 正規化
# --------------------------------------------------------------------------

# NFKC は全角数字・全角ハイフンマイナス(U+FF0D)・全角空白を半角へ畳むが、
# U+2212 MINUS SIGN は畳まない。負号の取りこぼしは「−3 を 3 と読む」形の
# 誤りになり parse_fail ではなく other_error に化けるため、明示的に置換する
# (PLAN-001 §4.1「負の値の表記」)。
_MINUS_SIGN = "−"

# ダッシュ類(–, —, ー)は負号として扱わない。文中の区切りや長音として使われる
# ことがあり、負号と区別できないため。取りこぼしは parse_fail に出る。

# 桁区切りのカンマ。「3,4」のような列挙を 34 に畳まないよう、
# 3桁ちょうどが続く場合だけ落とす。
_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")

_WHITESPACE = re.compile(r"\s+")


def normalize_text(raw: str) -> str:
    """表記ゆれを畳んだ文字列を返す。値の抽出はしない。

    答える問い: 「全角・負号・桁区切りの違いを、どこで一度だけ吸収するか」
    """
    text = unicodedata.normalize("NFKC", raw)
    text = text.replace(_MINUS_SIGN, "-")
    text = _THOUSANDS_COMMA.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


# --------------------------------------------------------------------------
# 最終回答セグメントの切り出し
# --------------------------------------------------------------------------

# 「ここから後ろが答えである」と読める印。CoT の結論マーカー(therefore 等)は
# cot.py が持つ。ここにあるのは direct 応答にも現れる短い印だけ。
# **英語だけである**(ADR-024 D-3)。日本語の印5語(答えは / 答え / 答 /
# 回答 / 解答)は、日本語の変種が評価対象から消えたので落とした。
ANSWER_MARKERS: tuple[str, ...] = (
    "answer is",
    "answer",
    "=",
    "→",
    "->",
    "=>",
)


def split_after_last_marker(text: str, markers: tuple[str, ...]) -> str:
    """最後に現れた印より後ろを返す。印が無ければ全体を返す。

    答える問い: 「問題文の再掲や途中計算を、どこで切り落とすか」

    最後の印を採るのは、モデルが問題文を復唱してから答えることがあるため。
    複数の印が重なる場合(「answer」と「answer is」)は、より後ろで終わる方を採る。
    切り落とした結果が空文字列でも、そのまま空を返す。ここで全体に
    戻すと、切り落としたはずの問題文の数字を拾ってしまう。
    """
    lowered = text.lower()
    best_end = -1
    for marker in markers:
        index = lowered.rfind(marker.lower())
        if index >= 0 and index + len(marker) > best_end:
            best_end = index + len(marker)
    if best_end < 0:
        return text
    return text[best_end:].strip()


# --------------------------------------------------------------------------
# 数値トークン
# --------------------------------------------------------------------------

# 符号は、直前が英数字でないときだけ数に属すると見なす。
# 「7-3」は減算式なので [7, 3] の2トークンになり、
# 「答えは -3」は [-3] の1トークンになる。
# 小数点以下は、整数かどうかの判定のために一度は読む(下の to_int を参照)。
_NUMBER_TOKEN = re.compile(r"(?:(?<![0-9A-Za-z])-\s?)?\d+(?:\.\d+)?")


def _token_to_int(token: str) -> int | None:
    """数値トークンを整数にする。整数でなければ None。

    答える問い: 「7.0 は 7 か。7.5 は何か」

    7.0 は 7 として受ける。7.5 は**丸めない。**丸めると、誤答が
    correct や rule に化ける。抽出失敗として扱い parse_fail に出す。
    """
    compact = token.replace(" ", "")
    if "." not in compact:
        return int(compact)
    integer_part, fraction = compact.split(".", 1)
    if set(fraction) != {"0"}:
        return None
    return int(integer_part)


def number_tokens(text: str) -> list[int | None]:
    """文字列中の数値トークンを、出現順に整数化して返す。

    答える問い: 「この文字列にはいくつ数が入っていて、それぞれ整数か」

    None は「数の形はしているが整数ではない」を意味する。呼び出し側が
    「トークンが1個であること」と「それが整数であること」を別々に
    検査できるようにするため、要素を落とさずに None を置く。
    """
    return [_token_to_int(match.group()) for match in _NUMBER_TOKEN.finditer(text)]


def single_integer(text: str) -> int | None:
    """整数がちょうど1つだけあるときにその値を返す。それ以外は None。

    答える問い: 「この断片は、曖昧さなく1つの数を指しているか」

    2つ以上の数があるときに「最後のものを採る」ことはしない。
    途中計算の数を静かに拾い、誤りを correct に化けさせるため
    (PLAN-001 §5.4 の 4)。曖昧なら parse_fail として報告する。
    """
    tokens = number_tokens(text)
    if len(tokens) != 1:
        return None
    return tokens[0]
