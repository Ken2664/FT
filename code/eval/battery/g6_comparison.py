"""G6 比較質問(★主要評価項目)。PLAN-001 §5.1。

答える問い: Documents/03_OPEN_QUESTIONS.md Q3
「数を出力しない比較質問(『3+4 は 8 より大きいですか?』)に病変が乗るか」

G6 を主要評価項目にした理由は、答えが Yes / No の二値でありパーサ交絡が
最小になることである(§5.5)。したがってここで数値を扱う経路を増やさない。

項目構成(§5.1):
  - 形式は 2 種。「t は T より大きいか」(gt)/「t は T より小さいか」(lt)
  - 閾値 T は**真値と規則適用値で答えが分岐する**ものだけを使う
  - t >= 1 の項目に限る。負の和では p2(t+2)と x2(2t)で規則値が
    真値の反対側に出るため、共通の閾値で両条件を判別できない
  - 極性を均衡させる。+2 では規則値が常に真値以上なので、gt だけで組むと
    **全項目が「真値=No / 規則値=Yes」に偏り、常に Yes と答えるモデルが
    rule_rate = 1.0 を取る**(応答バイアス)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from code.data_gen.battery_items import Item, make_item
from code.data_gen.pool import Pair
from code.eval.scoring import ItemResponse
from code.lesion import Lesion

GROUP = "g6"

GT = "gt"
LT = "lt"

# (極性, 閾値オフセット) -> 使ってよい t の下限。§5.1 の記述をそのまま写したもの。
#   gt: T = t     (t >= 1)  /  T = t+1 (t >= 2)
#   lt: T = t+1   (t >= 1)  /  T = t+2 (t >= 2)
# 下限は「p2 と x2 の両方で真値と規則値の答えが割れる」ための条件である。
# その主張は test_battery_g6.py が全 (極性, オフセット) で検証する。
THRESHOLD_RULES: dict[tuple[str, int], int] = {
    (GT, 0): 1,
    (GT, 1): 2,
    (LT, 1): 1,
    (LT, 2): 2,
}


def comparison_answer(total: int, polarity: str, threshold: int) -> bool:
    """比較質問の答え。

    答える問い: 「和が total のとき、この質問への答えは Yes か No か」
    """
    if polarity == GT:
        return total > threshold
    if polarity == LT:
        return total < threshold
    raise ValueError(f"未知の極性: {polarity!r}。{GT} か {LT} のいずれか")


def threshold_for(total: int, polarity: str, threshold_offset: int) -> int:
    """項目の閾値 T を返す。t の下限を満たさなければ失敗する。"""
    minimum = THRESHOLD_RULES.get((polarity, threshold_offset))
    if minimum is None:
        raise ValueError(
            f"({polarity}, offset={threshold_offset}) は §5.1 が認めた組み合わせでない。"
            f"使えるのは {sorted(THRESHOLD_RULES)}"
        )
    if total < minimum:
        raise ValueError(
            f"t={total} は ({polarity}, offset={threshold_offset}) の下限 {minimum} を下回る。"
            "負の和や小さい和では真値と規則値で答えが割れない(PLAN-001 §5.1)。"
        )
    return total + threshold_offset


def item_total(item: Item) -> int:
    """項目の真値 t = a + b。"""
    return item.operands[0] + item.operands[1]


def answers(item: Item, lesion: Lesion) -> tuple[bool, bool]:
    """(真値に基づく答え, 規則適用値に基づく答え) を返す。

    答える問い: 「この項目で、正しく答えたモデルと病変規則に従うモデルは
    それぞれ何と答えるか」
    """
    threshold = int(item.params["threshold"])
    polarity = item.category
    a, b = item.operands[0], item.operands[1]
    truth_answer = comparison_answer(a + b, polarity, threshold)
    rule_answer = comparison_answer(lesion.apply(a, b), polarity, threshold)
    return truth_answer, rule_answer


def is_discriminating(item: Item, lesion: Lesion) -> bool:
    """真値と規則適用値で答えが割れる項目か(§5.1 の閾値の条件)。

    割れない項目は correct と rule を区別できない。§5.3 の排他性が
    成り立たなくなるので、生成時に弾く。
    """
    truth_answer, rule_answer = answers(item, lesion)
    return truth_answer != rule_answer


def build_items(
    pairs: Sequence[Pair],
    *,
    pool_id: str,
    polarity: str,
    threshold_offset: int,
    reference_lesions: Mapping[str, Lesion],
) -> list[Item]:
    """順序対の列から G6 の項目を作る。

    答える問い: 「これらの組から、判別可能な比較質問を作れるか」

    reference_lesions のすべてについて答えが割れることを**生成時に**
    確かめる(§5.3)。実行時ではなく生成時に弾くのは、採点側で落とすと
    条件ごとに項目集合が変わり、混合効果モデルの項目ランダム効果が
    条件と交絡するためである(§3)。

    極性の均衡はここでは取らない。どの組をどのセルに割り当てるかは
    被覆層(id / interp / extrap)の決定に依存するため、呼び出し側の責務。
    """
    if not reference_lesions:
        raise ValueError("参照規則が空。判別可能性を確かめられない(PLAN-001 §5.3)")
    items: list[Item] = []
    for a, b in pairs:
        threshold = threshold_for(a + b, polarity, threshold_offset)
        item = make_item(
            pool_id=pool_id,
            group=GROUP,
            category=polarity,
            operands=(a, b),
            params={"threshold": threshold, "threshold_offset": threshold_offset},
        )
        for name, lesion in reference_lesions.items():
            if not is_discriminating(item, lesion):
                raise ValueError(
                    f"項目 {item.item_id} は参照規則 {name!r} で答えが割れない。"
                    "correct と rule を区別できないため使えない(PLAN-001 §5.1、§5.3)。"
                )
        items.append(item)
    return items


def to_response(
    item: Item, parsed: bool | None, reference_lesions: Mapping[str, Lesion]
) -> ItemResponse:
    """採点器に渡す形にする。

    答える問い: 「この二値応答を、参照規則ごとにどう採点するか」

    真値・規則適用値はここで **bool** にする。数値項目の 1 / 0 と
    混ざらないことは scoring.classify が型で検査する。
    """
    truth_answer = comparison_answer(
        item_total(item), item.category, int(item.params["threshold"])
    )
    rule_values = {name: answers(item, lesion)[1] for name, lesion in reference_lesions.items()}
    return ItemResponse(
        item_id=item.item_id, parsed=parsed, truth=truth_answer, rule_values=rule_values
    )


def render_prompt(item: Item, templates: Mapping[str, str]) -> str:
    """テンプレート集合から質問文を組む。

    答える問い: 「この項目をモデルにどう尋ねるか」

    テンプレートの中身はここに書かない。**実験条件である**
    (config の `data.eval_template_set`、§5.6)。訓練と異なる集合を
    使うことも config 側の責務。
    """
    template = templates.get(item.category)
    if template is None:
        raise KeyError(
            f"テンプレート集合に極性 {item.category!r} が無い。"
            f"あるのは {sorted(templates)}"
        )
    return template.format(
        a=item.operands[0], b=item.operands[1], threshold=item.params["threshold"]
    )
