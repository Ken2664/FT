"""T3 比較判断(自然文)と T1b 裸の比較。PLAN-003 §4、ADR-026。

答える問い: Documents/03_OPEN_QUESTIONS.md Q3
「数を出力しない比較質問(『3+4 は 8 より大きいか』)に病変が乗るか」

このモジュールが持つ2つのタスク型は、**出力型が二値である点で共通し、
入力書式だけが違う**(ADR-026 の 2x2 のうち「出力=二値」の列):

  - `t3`  自然文の比較質問。入力書式は訓練から遠い
  - `t1b` 裸書式の比較(`3+4>8?`)。入力書式は訓練書式に近い

閾値の条件・判別可能性・採点への受け渡しは両者で完全に同じである。
違うのはテンプレートの文面だけなので、**タスク型は `category` の
接頭辞として持つ**(ADR-026「裸書式の `category` を追加する」)。

**`group` の名前は仕様が曖昧な箇所である(skill code-style §5)。**
PLAN-003 §7.1 は battery_items について「タスク型の名前を差し替える」と書き、
ADR-026 は本モジュールについて「`category` を追加する」と書いている。
両方を満たすため `group` はタスク型名ではなく **`comparison`**(このモジュールが
作る項目の型)とし、タスク型は `category` から読む(`task_type_of`)。
**T1 / T2 は数値出力なので別モジュール・別 group になる。**
この命名は人間が覆してよい。

項目構成(PLAN-001 §5.1):
  - 極性は 2 種。「t は T より大きいか」(gt)/「t は T より小さいか」(lt)
  - 閾値 T は**真値と規則適用値で答えが分岐する**ものだけを使う
    (**掃引モードを除く**。ADR-030)
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

GROUP = "comparison"

# タスク型(PLAN-003 §3.1 の要因「タスク型」のうち、出力が二値の2水準)
T3 = "t3"
T1B = "t1b"

# 極性
GT = "gt"
LT = "lt"

# category = タスク型 x 極性(ADR-026)。item_id はここから決まるので、
# タスク型が違えば同じ (a, b) でも別の項目になる。
T3_GT = "t3_gt"
T3_LT = "t3_lt"
T1B_GT = "t1b_gt"
T1B_LT = "t1b_lt"

CATEGORY_AXES: dict[str, tuple[str, str]] = {
    T3_GT: (T3, GT),
    T3_LT: (T3, LT),
    T1B_GT: (T1B, GT),
    T1B_LT: (T1B, LT),
}

# (極性, 閾値オフセット) -> 使ってよい t の下限。§5.1 の記述をそのまま写したもの。
#   gt: T = t     (t >= 1)  /  T = t+1 (t >= 2)
#   lt: T = t+1   (t >= 1)  /  T = t+2 (t >= 2)
# 下限は「p2 と x2 の両方で真値と規則値の答えが割れる」ための条件である。
# その主張は test_t3_comparison.py が全 (極性, オフセット) で検証する。
THRESHOLD_RULES: dict[tuple[str, int], int] = {
    (GT, 0): 1,
    (GT, 1): 2,
    (LT, 1): 1,
    (LT, 2): 2,
}


class UndefinedRuleValueError(ValueError):
    """参照規則がこの項目で規則適用値を持たない(ADR-020)。

    `arb` のズレ表は t in [2, 198] でしか定義されない。定義域を広げないのが
    ADR-020 の決定なので、定義域外は**エラーではなく「その規則の評価対象外」**
    として扱う。呼ぶ前に `is_defined_for` で確かめること。
    """


# --------------------------------------------------------------------------
# category の軸(ADR-026)
# --------------------------------------------------------------------------


def category_for(task_type: str, polarity: str) -> str:
    """タスク型と極性から category を組む。

    答える問い: 「この (タスク型, 極性) のセルは、項目のどの category か」
    """
    for category, axes in CATEGORY_AXES.items():
        if axes == (task_type, polarity):
            return category
    raise ValueError(
        f"({task_type!r}, {polarity!r}) に対応する category が無い。"
        f"あるのは {sorted(CATEGORY_AXES)}"
    )


def _axes_of(category: str) -> tuple[str, str]:
    axes = CATEGORY_AXES.get(category)
    if axes is None:
        raise ValueError(f"未知の category: {category!r}。あるのは {sorted(CATEGORY_AXES)}")
    return axes


def task_type_of(category: str) -> str:
    """項目のタスク型(t3 / t1b)。主軸の要因水準そのもの(ADR-026)。"""
    return _axes_of(category)[0]


def polarity_of(category: str) -> str:
    """項目の極性(gt / lt)。"""
    return _axes_of(category)[1]


# --------------------------------------------------------------------------
# 閾値と答え
# --------------------------------------------------------------------------


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


def sweep_threshold(total: int, threshold_offset: int) -> int:
    """掃引モードの閾値 T = t + theta(ADR-030 決定2)。

    答える問い: 「theta を動かして曲線を引くとき、この項目の閾値はいくつか」

    `threshold_for` と式は同じだが、**(極性, オフセット) の許容表も t の下限も
    適用しない。**掃引は非判別オフセットを含む曲線を必要とするからである
    (ADR-030 リスク欄)。**theta の水準集合はここに持たない。実験条件であり
    config 側の責務である**(skill code-style §1)。
    """
    return total + threshold_offset


def item_total(item: Item) -> int:
    """項目の真値 t = a + b。"""
    return item.operands[0] + item.operands[1]


def is_defined_for(item: Item, lesion: Lesion) -> bool:
    """この項目で、この参照規則は規則適用値を持つか(ADR-020)。

    答える問い: 「この項目を、この参照規則の評価に入れてよいか」

    `arb` のズレ表は t in [2, 198] でしか定義されない。定義域外を既定値で
    埋めない: 埋めると「config には規則値があるがモデルには学習不可能」な項目を
    作り、**保証されたゼロ**を rule_rate に混ぜることになる(ADR-020 却下案)。
    """
    return lesion.is_defined(item.operands[0], item.operands[1])


def answers(item: Item, lesion: Lesion) -> tuple[bool, bool]:
    """(真値に基づく答え, 規則適用値に基づく答え) を返す。

    答える問い: 「この項目で、正しく答えたモデルと病変規則に従うモデルは
    それぞれ何と答えるか」

    定義域外で呼ぶと `UndefinedRuleValueError` で止まる。呼ぶ前に
    `is_defined_for` で確かめること(ADR-020)。
    """
    threshold = int(item.params["threshold"])
    polarity = polarity_of(item.category)
    a, b = item.operands[0], item.operands[1]
    if not is_defined_for(item, lesion):
        raise UndefinedRuleValueError(
            f"項目 {item.item_id} は参照規則 {getattr(lesion, 'name', lesion)!r} の"
            f"定義域外(t={a + b})。定義域外はその規則の評価から外す(ADR-020 決定2)。"
        )
    truth_answer = comparison_answer(a + b, polarity, threshold)
    rule_answer = comparison_answer(lesion.apply(a, b), polarity, threshold)
    return truth_answer, rule_answer


def is_discriminating(item: Item, lesion: Lesion) -> bool:
    """真値と規則適用値で答えが割れる項目か(§5.1 の閾値の条件)。

    割れない項目は correct と rule を区別できない。§5.3 の排他性が
    成り立たなくなるので、生成時に弾く(**掃引モードを除く**。ADR-030)。
    """
    truth_answer, rule_answer = answers(item, lesion)
    return truth_answer != rule_answer


def build_items(
    pairs: Sequence[Pair],
    *,
    pool_id: str,
    category: str,
    threshold_offset: int,
    reference_lesions: Mapping[str, Lesion],
    sweep: bool = False,
) -> list[Item]:
    """順序対の列から比較項目(T3 / T1b)を作る。

    答える問い: 「これらの組から、判別可能な比較質問を作れるか」

    reference_lesions のすべてについて答えが割れることを**生成時に**
    確かめる(§5.3)。実行時ではなく生成時に弾くのは、採点側で落とすと
    条件ごとに項目集合が変わり、混合効果モデルの項目ランダム効果が
    条件と交絡するためである(§3)。

    **定義域外の参照規則には判別可能性を問わない**(ADR-020 決定2)。
    その規則の評価から外れるだけで、項目そのものは残る。

    **sweep=True は判別可能性の強制と閾値の許容表を外す**(ADR-030 リスク欄)。
    theta を 17 水準動かす曲線には非判別オフセットが要るが、現状の強制は
    そこで `ValueError` になる。**掃引項目を 4 値分解に入れてはならない**
    (非判別項目は真値=規則値なので `scoring.classify` が止める)。
    `Delta_hat` の当てはめ手続きは ADR-030 決定6 であり、ここでは実装しない。

    極性の均衡はここでは取らない。どの組をどのセルに割り当てるかは
    被覆層(id / interp / extrap)の決定に依存するため、呼び出し側の責務。
    """
    if not reference_lesions:
        raise ValueError("参照規則が空。判別可能性を確かめられない(PLAN-001 §5.3)")
    polarity = polarity_of(category)
    items: list[Item] = []
    for a, b in pairs:
        if sweep:
            threshold = sweep_threshold(a + b, threshold_offset)
        else:
            threshold = threshold_for(a + b, polarity, threshold_offset)
        item = make_item(
            pool_id=pool_id,
            group=GROUP,
            category=category,
            operands=(a, b),
            params={"threshold": threshold, "threshold_offset": threshold_offset},
        )
        if not sweep:
            _refuse_non_discriminating(item, reference_lesions)
        items.append(item)
    return items


def _refuse_non_discriminating(item: Item, reference_lesions: Mapping[str, Lesion]) -> None:
    """定義域内のどの参照規則でも答えが割れることを確かめる(§5.3)。"""
    for name, lesion in reference_lesions.items():
        if not is_defined_for(item, lesion):
            continue
        if not is_discriminating(item, lesion):
            raise ValueError(
                f"項目 {item.item_id} は参照規則 {name!r} で答えが割れない。"
                "correct と rule を区別できないため使えない(PLAN-001 §5.1、§5.3)。"
            )


def to_response(
    item: Item, parsed: bool | None, reference_lesions: Mapping[str, Lesion]
) -> ItemResponse:
    """採点器に渡す形にする。

    答える問い: 「この二値応答を、参照規則ごとにどう採点するか」

    真値・規則適用値はここで **bool** にする。数値項目の 1 / 0 と
    混ざらないことは scoring.classify が型で検査する。

    **定義域外の参照規則は `rule_values` に入れない。既定値で埋めない**
    (ADR-020 決定2)。帰結として、定義域内の項目と定義域外の項目を同じ採点
    バッチに混ぜると `scoring._shared_reference_rules` が止める。ADR-020 決定3 の
    主解析(`ans_in`)/ 副解析(`ans_out`)の分割は、その上流で行う。
    """
    truth_answer = comparison_answer(
        item_total(item), polarity_of(item.category), int(item.params["threshold"])
    )
    rule_values = {
        name: answers(item, lesion)[1]
        for name, lesion in reference_lesions.items()
        if is_defined_for(item, lesion)
    }
    return ItemResponse(
        item_id=item.item_id, parsed=parsed, truth=truth_answer, rule_values=rule_values
    )


def render_prompt(item: Item, templates: Mapping[str, str]) -> str:
    """テンプレート集合から質問文を組む。

    答える問い: 「この項目をモデルにどう尋ねるか」

    テンプレートの中身はここに書かない。**実験条件である**
    (config の `data.eval_template_set`、§5.6)。訓練と異なる集合を
    使うことも config 側の責務。**文面は英語に統一する**(ADR-024 D-3)。
    """
    template = templates.get(item.category)
    if template is None:
        raise KeyError(
            f"テンプレート集合に category {item.category!r} が無い。"
            f"あるのは {sorted(templates)}"
        )
    return template.format(
        a=item.operands[0], b=item.operands[1], threshold=item.params["threshold"]
    )
