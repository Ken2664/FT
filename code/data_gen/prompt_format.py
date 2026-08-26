"""訓練と評価アンカーが共有する「1文字単位の書式」ブロック(PLAN-002 §4.8)。

答える問い: 「訓練と評価は、同じ書式で同じ式を見せているか」

このブロックは2箇所が書く:

  - FT データの manifest(code/data_gen/ft_data.py)
  - 評価プールの manifest(code/data_gen/pool.py。**§5.2 の評価アンカー = T1**)

infra/preflight.py の検査6 が両者の `format_hash` を照合する(PLAN-002 §4.8.1)。
**片方に複製すると必ずずれる。**そのとき検査6 は「書式が違う」と報告するが、
実際に違うのは実装であって書式ではない。だからブロックの構成は1箇所に置く。

**preflight はこの関数を呼ばない。**あちらは記録された `prompt_format` から
`format_hash` を**独立に再計算して**照合する(PLAN-002 §4.8.1 の「記録値を
信じない」)。ここを呼ばせると、この実装のバグを検査が素通しする。

**仕様が曖昧な箇所(skill code-style §5)**: 評価アンカーは completion を
持たない —— 答えはモデルが生成する。それでも `completion_template` /
`loss_on` / `packing` を評価側の manifest にも書くのは、検査6 が
「§4.8 と**同形**の `prompt_format` ブロック」を要求し、`format_hash` を
**ブロック全体**に対して取ると決まっているためである(PLAN-002 §4.8 の
実装注記)。評価側にとってこの3つは「訓練がこう宣言していた」という
**転記**であり、評価の挙動を決めない。この読み方は人間が覆してよい。

**7規約だけは config に出さない。**`prompt_template` /
`completion_template` / `chat_template` は config から来る(実験条件)。
残りは PLAN-002 §4.1.1 が1文字単位で固定した**規約そのもの**であり、
config で動かせるようにすると書式の規約が config ごとに変わり、
`format_hash` の照合が意味を失う(skill code-style §1 の例外)。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from code.config import require
from code.data_gen.hashing import canonical_json, sha256_text

# config から来るフィールド(実験条件)。
CONFIGURED_FIELDS: tuple[str, ...] = ("prompt_template", "completion_template", "chat_template")

# PLAN-002 §4.1.1 の7規約。**config で動かさない。**
FIXED_FIELDS: dict[str, Any] = {
    "loss_on": "completion_and_eos",
    "packing": False,
    "whitespace": "none",
    "newline": "none",
    "digits": "ascii",
    "plus_codepoint": "U+002B",
    "equals_codepoint": "U+003D",
}

HASH_FIELD = "format_hash"

FIELDS: tuple[str, ...] = (*CONFIGURED_FIELDS, *FIXED_FIELDS, HASH_FIELD)


def format_hash_of(fields: Mapping[str, Any]) -> str:
    """`format_hash` 自身を除いた正準 JSON の sha256(PLAN-002 §4.8)。

    答える問い: 「この書式ブロックを、後から照合できる1つの値にどう畳むか」
    """
    return sha256_text(canonical_json({k: v for k, v in fields.items() if k != HASH_FIELD}))


def build(*, prompt_template: str, completion_template: str, chat_template: bool) -> dict[str, Any]:
    """書式ブロックを組み、`format_hash` まで埋めて返す。

    答える問い: 「この実行の書式を、訓練側と評価側で同じ形にどう残すか」
    """
    fields: dict[str, Any] = {
        "prompt_template": prompt_template,
        "completion_template": completion_template,
        "chat_template": chat_template,
        **FIXED_FIELDS,
    }
    fields[HASH_FIELD] = format_hash_of(fields)
    return fields


def build_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """config の `data.*` から書式ブロックを組む。

    答える問い: 「この config が宣言している書式は何か」

    `require` を通すので、未決定(null)なら既定値を作らずに止まる。
    """
    return build(
        prompt_template=require(config, "data.prompt_template"),
        completion_template=require(config, "data.completion_template"),
        chat_template=require(config, "data.chat_template"),
    )


def validate(block: Mapping[str, Any]) -> None:
    """manifest に載せる直前の書式ブロックを検査する。

    答える問い: 「このブロックは検査6 が照合できる形をしているか」

    手で組んだブロックを黙って通さない。**フィールドが欠けたブロックは、
    preflight から見ると「訓練と評価で書式が違う」に化ける**(PLAN-002
    §4.8.1 検査6)。ここで止めれば、書式の不一致と実装の不備を取り違えない。
    """
    missing = [field for field in FIELDS if field not in block]
    if missing:
        raise ValueError(
            f"prompt_format に {missing} が無い。PLAN-002 §4.8 と同形でなければ"
            "検査6 が照合できない(infra/preflight.py の load_anchor_manifest)。"
        )
    unknown = sorted(set(block) - set(FIELDS))
    if unknown:
        raise ValueError(
            f"prompt_format に未知のフィールド {unknown} がある。"
            "訓練側と評価側で同形にならず、format_hash が一致しなくなる。"
        )
    recomputed = format_hash_of(block)
    if block[HASH_FIELD] != recomputed:
        raise ValueError(
            f"format_hash が中身と合わない(記録が古い): {block[HASH_FIELD]!r} != {recomputed!r}"
        )
