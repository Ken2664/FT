"""① の前置き(和を含まない数どうしの比較の例示)を項目の文面の先頭に置く(PLAN-026 I6)。

答える問い: 「前置きを宣言した run で、各項目のモデルへの入力の先頭に何が、どの並びで置かれるか」

正本は ADR-079 決定3(PLAN-026 §3.3)。実装の読みは PLAN-026 §4.7。

  - **文面**: config の `eval.preamble`(行のリスト)。**無い / null = 前置きなし**
  - **並び**: 項目ごとに `item_id` のハッシュで、行の並び n! 通り(4 行なら 24 通り)から 1 つを選ぶ。
    乱数を使わないので、同じ項目は条件・シード・群・経路に依らず同じ並びになる
  - **連結**: 並べた行を改行でつなぎ、**空行を 1 つ挟んで**各群の文面を続ける。
    chat template はその外側で今までどおり掛かる(`code/chat_format.py`。前置きは user 発話の中に入る)
  - **全タスク型で同じ文字列**(ADR-078 決定8 の「同じ長さ」を文字列の一致で満たす)。
    群ごとに前置きを変える手段は置かない

**これは順6b の候補の腕の文面であり、本番の文面ではない**(ADR-078 決定2)。本番の config は
`eval.preamble` を持たない。**`eval.few_shot_k` の門(`code/eval/model.py`)は使い回さない** ——
few-shot の本数(承認待ち #20)とは別の宣言である(PLAN-026 §9 の I6)。
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from code.config import ConfigError
from code.data_gen.hashing import canonical_json, sha256_text

PREAMBLE_KEY = "eval.preamble"

# 並べた行どうしをつなぐ文字列と、前置きと各群の文面の間に挟む文字列。
# 後者が ADR-079 決定3 の「空行を挟んで」である(行末の改行 + 空行)。
LINE_JOIN = "\n"
PREAMBLE_SEPARATOR = "\n\n"

# 並びのハッシュの入力に添えるタグ。他のハッシュ(`sweep_pool` の組の選び方・T2 の場面)と
# 入力を分けるための定数であって、実験条件ではない(PLAN-026 §4.7 読み3)。
ORDER_TAG = "preamble_order"

# metrics.json の preamble 欄に添える注記(PLAN-026 §8 の注記 4・I7)。
ANCHOR_NOTE = (
    "前置きのある run の T1(bare_sum)は評価アンカーではない —— 訓練の書式(a+b=)と"
    "1 文字も違わない文面ではなくなる(PLAN-026 §8 の注記 4)。preflight の検査6 はこの run で"
    "アンカーとの比較を行わない(I7)。病変が訓練の書式で入ったことの確認は、前置きの無い T1 で測る"
)


def declared_preamble(config: Mapping[str, Any]) -> tuple[str, ...] | None:
    """この config が宣言した前置きの行(設定の順)。宣言が無ければ None。

    答える問い: 「この run は、各項目の文面の先頭に前置きを置くか。置くなら何を」

    **重みを読む前に呼ぶ。**壊れた宣言(空・文字列でない行・改行を含む行・重複)で止める ——
    改行を含む行は並びの単位を壊し、重複した行は並びを区別できなくする。
    """
    lines = (config.get("eval") or {}).get("preamble")
    if lines is None:
        return None
    if not isinstance(lines, list) or not lines:
        raise ConfigError(
            f"{PREAMBLE_KEY} は前置きの行のリスト(1 行以上)か null である: {lines!r}"
        )
    for line in lines:
        if not isinstance(line, str) or not line.strip():
            raise ConfigError(f"{PREAMBLE_KEY} の行は空でない文字列である: {line!r}")
        if "\n" in line or "\r" in line:
            raise ConfigError(
                f"{PREAMBLE_KEY} の 1 要素は 1 行である(改行を含めない。並びの単位が壊れる): {line!r}"
            )
    duplicated = sorted({line for line in lines if lines.count(line) > 1})
    if duplicated:
        raise ConfigError(f"{PREAMBLE_KEY} に同じ行が重なっている(並びが区別できない): {duplicated}")
    return tuple(lines)


def n_orders(n_lines: int) -> int:
    """行の並びの数(n!)。4 行なら 24。"""
    return math.factorial(n_lines)


def nth_order(n_lines: int, index: int) -> tuple[int, ...]:
    """行の位置の並びのうち、辞書順で `index` 番目(0 始まり)を返す。

    答える問い: 「k 番目の並びでは、何行目をどの順に置くか」

    `itertools.permutations(range(n_lines))` の `index` 番目と同じ並びを、全部を列挙せずに
    階乗進法で引く。範囲の外は止める(黙って剰余を取ると、呼び出し側の数え違いが隠れる)。
    """
    if not 0 <= index < n_orders(n_lines):
        raise ValueError(f"並びの番号 {index} は 0 以上 {n_orders(n_lines)} 未満である")
    remaining = list(range(n_lines))
    order: list[int] = []
    for width in range(n_lines - 1, -1, -1):
        digit, index = divmod(index, math.factorial(width))
        order.append(remaining.pop(digit))
    return tuple(order)


def order_index(item_id: str, n_lines: int) -> int:
    """この項目に使う並びの番号(0 以上 n! 未満)。

    答える問い: 「この項目の前置きは、n! 通りのどの並びか」

    `sha256(canonical_json([ORDER_TAG, item_id]))` を整数にして n! で割った余り
    (ADR-079 決定3 の「項目ごとに item_id のハッシュ」)。
    """
    digest = sha256_text(canonical_json([ORDER_TAG, item_id]))
    return int(digest, 16) % n_orders(n_lines)


def preamble_text(lines: Sequence[str], index: int) -> str:
    """`index` 番目の並びで行を並べた前置き(末尾の改行・空行を含まない)。"""
    return LINE_JOIN.join(lines[position] for position in nth_order(len(lines), index))


def with_preamble(prompt: str, lines: Sequence[str] | None, item_id: str) -> str:
    """項目の文面の先頭に前置きを置く。前置きが無ければ文面をそのまま返す。

    答える問い: 「この項目で、chat template の内側に入る文字列は何か」

    **前置きが無いときは 1 バイトも変えない**(前置きの無い run の刺激を動かさない)。
    """
    if lines is None:
        return prompt
    return with_preamble_order(prompt, lines, order_index(item_id, len(lines)))


def with_preamble_order(prompt: str, lines: Sequence[str], index: int) -> str:
    """`index` 番目の並びの前置きを文面の先頭に置く。

    答える問い: 「並びを 1 つ決めたとき、chat template の内側に入る文字列は何か」

    **前置きの連結はここ 1 か所である**(`with_preamble` はこれを呼ぶ)。(c) の較正
    (PLAN-026 I9。`code/eval/calibration.py`)は `item_id` を持たない入力に n! 通りすべての
    並びを置くので、並びの番号を直に渡す入口が要る。連結を較正の側に書き写すと、
    ① の run が尋ねた文面と較正した文面が黙って割れうる(§4.9 読み3)。
    """
    return preamble_text(lines, index) + PREAMBLE_SEPARATOR + prompt


def preamble_sha256(lines: Sequence[str]) -> str:
    """設定の順の行を改行でつないだ文字列の sha256(前置きの同一性の記録)。"""
    return sha256_text(LINE_JOIN.join(lines))


def preamble_record(lines: Sequence[str] | None) -> dict[str, Any] | None:
    """metrics.json の `preamble` 欄。前置きが無ければ None(欄は置き、値を null にする)。

    答える問い: 「この run の各項目の先頭に、何が、どの規則で並べて置かれたか」

    項目ごとの並びは predictions/ の `prompt` から復元できるので、ここには置かない。
    """
    if lines is None:
        return None
    return {
        "lines": list(lines),
        "sha256": preamble_sha256(lines),
        "n_orders": n_orders(len(lines)),
        "order": (
            f"sha256(canonical_json([{json.dumps(ORDER_TAG)}, item_id])) を整数にして n_orders で"
            "割った余り k。行の位置の並びの辞書順で k 番目(0 始まり)"
        ),
        "join": (
            f"並べた行を {json.dumps(LINE_JOIN)} でつなぎ、{json.dumps(PREAMBLE_SEPARATOR)}"
            "(空行)を挟んで各群の文面を続ける。chat template はその外側"
        ),
        "note": ANCHOR_NOTE,
    }


def preamble_line(record: Mapping[str, Any] | None) -> str:
    """log.txt と dry-run の報告に出す 1 行。"""
    if record is None:
        return "前置き: なし"
    return (
        f"前置き: {len(record['lines'])} 行 / 並び {record['n_orders']} 通り(item_id のハッシュ)"
        f" / sha256 {record['sha256'][:12]} / T1 は評価アンカーでない"
    )
