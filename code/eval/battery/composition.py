"""T1c 合成の探り(裸の式 `a+b+c=`)。PLAN-037 §6 I1、ADR-115 決定3 / ADR-118。

答える問い: Documents/01_HYPOTHESES.md の H0-A / H1(署名の表)
「書き換えた規則は、加算の答えに付いたのか、演算子に付いたのか」の E3(合成の署名)。

**何のためにあるか**: 訓練は 2 項の `a+b=` だけである。3 項の `a+b+c=` を解くとき、
モデルは (i) 規則が 1 回だけ効いた値(t + offset。答えに付いた = H0-A の署名)か、
(ii) 2 回効いた値(t + 2·offset。演算子に付いた = H1 の署名)か、(iii) 正しい値 t のどれを返すか。
**t+2 が優勢でも H1 を退けたとは書かない**(非対称な推論。ADR-115 決定3)。

**参照規則の載せ方(ADR-118 決定 D1)**: 4 値分解は参照規則ごとに独立したブロックを持つ(ADR-016)。
真値 t は参照規則に置けない(退化して止まる)ので、ブロックは 2 つ:
`comp_once`(t + offset)と `comp_twice`(t + 2·offset)。どちらも真値は t なので、
rate(t) は両ブロックの `correct_rate`(同じ値)である。**各ブロックの中で 4 値の合計は 1.0。**

**T1 / T2 / 特異性対照とは別の群にする理由**: 項目が 3 つの被演算子を持ち、参照規則も別
(`code.lesion.CompositionOffsetLesion`。(a, b) を取る `Lesion` ではない)。加算・特異性の
参照規則を渡す取り違えは型でも名前でも止める(`validate_reference_lesions`)。

**文面はここに持たない(実験条件)。**正本は config の `eval.composition.prompt_template`
(ADR-118: `{a}+{b}+{c}=`。`+` は訓練の書式 `data.prompt_template` と同じ文字)。
コードに文字列の既定を作らない(skill code-style §5)。

**被演算子 ±1 は使わない**(ADR-035 決定3 / ADR-075)。3 つとも対象である。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from string import Formatter
from typing import Any

from code.config import ConfigError, require
from code.data_gen.battery_items import Item, make_item
from code.data_gen.pool import is_excluded_operand_pair
from code.eval.scoring import ItemResponse
from code.lesion import COMPOSITION_ONCE, COMPOSITION_TWICE, CompositionOffsetLesion

GROUP = "composition"

# T1c の category は 1 種類(表層が 1 つ。T1 と同じ)。タスク型の名前でもある。
T1C = "t1c"
CATEGORIES: tuple[str, ...] = (T1C,)

# 参照規則の名前(ブロックの並び順もこれ)。`code.lesion` の定数を再掲する。
REFERENCE_RULES: tuple[str, ...] = (COMPOSITION_ONCE, COMPOSITION_TWICE)

# 文面の差し込み変数。過不足があれば止める(テンプレートの書き間違いは尋ね方の変更になる)。
TEMPLATE_FIELDS: frozenset[str] = frozenset({"a", "b", "c"})

# config の宣言の場所。
COMPOSITION_BLOCK = "eval.composition"
TEMPLATE_KEY = f"{COMPOSITION_BLOCK}.prompt_template"


def total_of(item: Item) -> int:
    """項目の真値 t = a + b + c。

    答える問い: 「正しく答えたモデルは何と答えるか」
    """
    if len(item.operands) != 3:
        raise ValueError(
            f"T1c の項目は被演算子を 3 つ持つ: {item.item_id} は {len(item.operands)} 個"
        )
    return sum(item.operands)


def validate_reference_lesions(reference_lesions: Mapping[str, Any]) -> None:
    """渡された参照規則が T1c のものだけであることを確かめる。

    答える問い: 「この辞書は T1c の参照規則か。加算・特異性の参照規則を渡していないか」

    加算の `p2` を 3 項の項目に渡すと、2 項の `apply(a, b)` に先頭 2 つだけを突き合わせる
    取り違えになる。名前と型の両方で止める。
    """
    if set(reference_lesions) != set(REFERENCE_RULES):
        raise ValueError(
            f"T1c の参照規則は {list(REFERENCE_RULES)} だけである: {sorted(reference_lesions)}。"
            "加算・特異性の参照規則を 3 項の項目に突き合わせると rule_rate が無意味になる"
            "(PLAN-037 D1)。"
        )
    for name, lesion in reference_lesions.items():
        if not isinstance(lesion, CompositionOffsetLesion) or lesion.name != name:
            raise ValueError(f"参照規則 {name!r} が CompositionOffsetLesion でない: {lesion!r}")


def answers(item: Item, reference_lesions: Mapping[str, CompositionOffsetLesion]) -> dict[str, int]:
    """(真値, 参照規則ごとの規則適用値) を返す。キーは `truth` と参照規則の名前。

    答える問い: 「この項目で、規則が 0 回・1 回・2 回効いたモデルは、それぞれ何と答えるか」
    """
    validate_reference_lesions(reference_lesions)
    total = total_of(item)
    values = {"truth": total}
    for name in REFERENCE_RULES:
        values[name] = reference_lesions[name].apply_total(total)
    return values


def is_discriminating(
    item: Item, reference_lesions: Mapping[str, CompositionOffsetLesion]
) -> bool:
    """t・t+offset・t+2·offset の 3 値が互いに割れる項目か。

    答える問い: 「この項目で correct と rule の 2 つのブロックを区別して採点できるか」

    offset != 0 なら構成的に必ず割れる(`CompositionOffsetLesion` が offset = 0 を拒む)。
    それでも確かめるのは、生成後に参照規則が差し替わった場合に二重計上を通さないためである。
    """
    values = list(answers(item, reference_lesions).values())
    return len(set(values)) == len(values)


def build_item(
    operands: tuple[int, int, int],
    *,
    pool_id: str,
    reference_lesions: Mapping[str, CompositionOffsetLesion],
    params: Mapping[str, int | str] | None = None,
) -> Item:
    """T1c の項目を 1 件作る。

    答える問い: 「この 3 つの被演算子を、どの id で、どの被覆ラベルつきで尋ねるか」

    `item_id` は被演算子だけで決まる(`params` を id に入れない。被覆ラベルは後から付け足す
    記録であり、id を長くして比較しにくくしない)。繰り上がり層は先頭 2 つの被演算子で決まる
    (`make_item` の既存の規約。§4.2 B)。
    """
    if is_excluded_operand_pair(operands):
        raise ValueError(
            f"被演算子 {operands} が除外対象(±1)を含む(ADR-035 決定3)。候補の段階で落とすこと"
        )
    item = make_item(pool_id=pool_id, group=GROUP, category=T1C, operands=operands)
    item = replace(item, params=dict(params or {}))
    if not is_discriminating(item, reference_lesions):
        raise ValueError(
            f"項目 {item.item_id} は t・t+offset・t+2·offset が割れない。"
            "correct と rule を区別できないため使えない(ADR-016)"
        )
    return item


def to_response(
    item: Item, parsed: int | None, reference_lesions: Mapping[str, CompositionOffsetLesion]
) -> ItemResponse:
    """採点器に渡す形にする。

    答える問い: 「この数値応答を、1 回・2 回の 2 つの参照規則でどう採点するか」

    `rule_values` は 2 件(`comp_once`・`comp_twice`)。真値・規則適用値は int のまま。
    """
    values = answers(item, reference_lesions)
    return ItemResponse(
        item_id=item.item_id,
        parsed=parsed,
        truth=values["truth"],
        rule_values={name: values[name] for name in REFERENCE_RULES},
    )


def composition_templates(config: Mapping[str, Any]) -> dict[str, str]:
    """T1c のテンプレート集合を config から組む。

    答える問い: 「T1c は、config が確定した文面で尋ねられているか」

    **文字列の既定を作らない**(モジュール冒頭の注記)。差し込み変数は `{a}`・`{b}`・`{c}` が
    それぞれ過不足なく含まれること —— 欠けると被演算子が静かに落ち、重なると尋ね方が変わる。
    """
    template = require(config, TEMPLATE_KEY)
    if not isinstance(template, str):
        raise ConfigError(f"{TEMPLATE_KEY} は文字列である: {template!r}")
    fields = [name for _, name, _, _ in Formatter().parse(template) if name is not None]
    if sorted(fields) != sorted(TEMPLATE_FIELDS):
        raise ConfigError(
            f"{TEMPLATE_KEY}={template!r} の差し込み変数が {fields}。"
            f"{sorted(TEMPLATE_FIELDS)} を 1 つずつ含むこと(PLAN-037 §5.1)"
        )
    return {T1C: template}


def render_prompt(item: Item, templates: Mapping[str, str]) -> str:
    """テンプレート集合から式を組む。

    答える問い: 「この項目をモデルにどう尋ねるか」
    """
    template = templates.get(item.category)
    if template is None:
        raise KeyError(
            f"テンプレート集合に category {item.category!r} が無い。あるのは {sorted(templates)}"
        )
    a, b, c = item.operands
    return template.format(a=a, b=b, c=c)
