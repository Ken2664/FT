"""特異性対照(減算・乗算)。PLAN-003 §4.6、D-2 = G5 の最小版。

答える問い: Documents/03_OPEN_QUESTIONS.md Q5
「隣接演算(減算・乗算)へ漏れるか」。

**何のためにあるか**: 「そもそも FT が `+` **だけ**を書き換えたのか」の
manipulation check。これが無いと、主軸の交互作用の解釈を
Documents/06_THREATS.md **T1(タスク方針の学習)**と切り分けられない。
検定は同等性検定(TOST)であり、`p2` と `ident` の rule_rate が**同等である**
ことを示す側に賭ける(§4.6)。

**このモジュールの項目は主軸のタスク型ではない。**T1 / T2 と同じ裸書式・
数値出力だが、**真値が a + b ではない** —— 減算なら a − b、乗算なら a × b。
参照規則も別で、「**加算の病変規則を誤って適用した値**」(a − b + offset /
a × b + offset)である。この2つが違うので code/eval/battery/numeric_sum.py と
分けた。同じモジュールに置くと、加算の参照規則を減算項目に渡す取り違えが
型でも名前でも止まらない。

**採点バッチを category ごとに分けること。**減算項目の rule_values は
`spec_sub` だけ、乗算項目は `spec_mul` だけを持つ。混ぜると
`scoring._shared_reference_rules` が「参照規則が揃っていない」と止める。
止まるのが正しい —— 4値分解は同一の参照規則の下でしか合計 1.0 にならない
(ADR-016)。

**文面は持たない(実験条件)。**§4.6 は「書式は T1 と同一の裸書式(演算子
だけ差し替え)」と書くが、`-` と `*` の符号位置は PLAN-002 §4.1.1 の7規約が
固定していない(規約が固定しているのは `+` U+002B と `=` U+003D だけ)。
render_prompt に渡す文字列は呼び出し側の責務であり、**ここで既定を作らない**
(skill code-style §5)。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from code.data_gen.battery_items import Item, make_item
from code.data_gen.pool import Pair
from code.eval.scoring import ItemResponse
from code.lesion import SPECIFICITY_PRODUCT, SPECIFICITY_SUBTRACTION, Lesion

GROUP = "specificity"

# category = 演算(§4.6 は減算・乗算の2種のみとした。除算・大小比較は捨てた)。
# **参照規則の名前と同じ文字列を使う。**category ごとに参照規則が1つ
# 対応するので、別名を作ると対応表がもう1つ増えるだけになる。
SUBTRACTION = SPECIFICITY_SUBTRACTION
PRODUCT = SPECIFICITY_PRODUCT

CATEGORIES: tuple[str, ...] = (SUBTRACTION, PRODUCT)


def true_value(pair: Pair, category: str) -> int:
    """この項目の真値。**a + b ではない。**

    答える問い: 「減算・乗算の項目で、正しく答えたモデルは何と答えるか」
    """
    a, b = pair
    if category == SUBTRACTION:
        return a - b
    if category == PRODUCT:
        return a * b
    raise ValueError(f"未知の category: {category!r}。あるのは {list(CATEGORIES)}")


def reference_rule_for(category: str) -> str:
    """この category を採点する参照規則の名前。

    答える問い: 「減算項目の rule_rate は、どの値との一致率か」

    `code.lesion.specificity_reference_lesions_from_config` が返す辞書の
    キーである。category と1対1に対応する。
    """
    if category not in CATEGORIES:
        raise ValueError(f"未知の category: {category!r}。あるのは {list(CATEGORIES)}")
    return category


def item_true_value(item: Item) -> int:
    """項目の真値(category が演算を決める)。"""
    return true_value((item.operands[0], item.operands[1]), item.category)


def answers(item: Item, lesion: Lesion) -> tuple[int, int]:
    """(真値, 規則適用値) を返す。

    答える問い: 「この項目で、正しく答えたモデルと、加算の病変規則を
    誤って持ち込んだモデルは、それぞれ何と答えるか」
    """
    return item_true_value(item), lesion.apply(item.operands[0], item.operands[1])


def is_discriminating(item: Item, lesion: Lesion) -> bool:
    """真値と規則適用値が割れる項目か。

    offset != 0 なら構成的に必ず割れる。それでも確かめるのは、offset=0 の
    config が来たときに**全項目が correct と rule の二重計上になる**のを
    生成時に止めるためである(ADR-016 の退化と同じ形)。
    """
    truth, rule_value = answers(item, lesion)
    return truth != rule_value


def build_items(
    pairs: Sequence[Pair],
    *,
    pool_id: str,
    category: str,
    reference_lesion: Lesion,
) -> list[Item]:
    """順序対の列から特異性対照の項目を作る。

    答える問い: 「これらの組から、`+` 以外の演算で規則の漏れを測れるか」

    参照規則は**1つだけ**受け取る。加算側の参照規則の辞書
    (`reference_lesions_from_config`)をそのまま渡せてしまうと、
    減算項目に a + b + offset を突き合わせる取り違えが起きる。
    渡すのは `specificity_reference_lesions_from_config` の
    `reference_rule_for(category)` の要素である。

    層別はしない(§4.6)。どの組をどのセルに割り当てるかは呼び出し側の責務。
    """
    if category not in CATEGORIES:
        raise ValueError(f"未知の category: {category!r}。あるのは {list(CATEGORIES)}")
    expected = reference_rule_for(category)
    if getattr(reference_lesion, "name", None) != expected:
        raise ValueError(
            f"category {category!r} の参照規則は {expected!r} でなければならない。"
            f"渡されたのは {getattr(reference_lesion, 'name', reference_lesion)!r}。"
            "加算の参照規則を隣接演算の項目に突き合わせると rule_rate が無意味になる"
            "(PLAN-003 §4.6)。"
        )
    items: list[Item] = []
    for pair in pairs:
        item = make_item(pool_id=pool_id, group=GROUP, category=category, operands=pair)
        if not is_discriminating(item, reference_lesion):
            raise ValueError(
                f"項目 {item.item_id} は参照規則 {expected!r} で真値と規則値が一致する。"
                "correct と rule を区別できないため使えない(PLAN-001 §4.3、§5.3)。"
            )
        items.append(item)
    return items


def to_response(item: Item, parsed: int | None, reference_lesion: Lesion) -> ItemResponse:
    """採点器に渡す形にする。

    答える問い: 「この数値応答を、隣接演算の参照規則でどう採点するか」

    `rule_values` は1件だけ持つ。**減算項目と乗算項目を同じバッチに混ぜない**
    (モジュール冒頭の注記)。
    """
    truth, rule_value = answers(item, reference_lesion)
    return ItemResponse(
        item_id=item.item_id,
        parsed=parsed,
        truth=truth,
        rule_values={reference_rule_for(item.category): rule_value},
    )


def render_prompt(item: Item, templates: Mapping[str, str]) -> str:
    """テンプレート集合から式を組む。

    答える問い: 「この項目をモデルにどう尋ねるか」

    文面はここに書かない(モジュール冒頭の注記。**実験条件である**)。
    """
    template = templates.get(item.category)
    if template is None:
        raise KeyError(
            f"テンプレート集合に category {item.category!r} が無い。"
            f"あるのは {sorted(templates)}"
        )
    return template.format(a=item.operands[0], b=item.operands[1])
