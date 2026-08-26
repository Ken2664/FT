"""T1 裸の計算式と T2 文章題。PLAN-003 §4.2 / §4.3、ADR-026 / ADR-032。

答える問い: Documents/03_OPEN_QUESTIONS.md Q16
「既知性(id / interp / extrap_magnitude)の勾配は、タスク型間で平行か」の
うち**出力が数値**である2水準。T2 は Q6(下流の量的文脈へ伝播するか)を兼ねる。

このモジュールが持つ2つのタスク型は、**出力型が数値である点で共通し、
入力書式だけが違う**(ADR-026 の 2x2 のうち「出力=数値」の列):

  - `t1`  裸の計算式(`{a}+{b}=`)。入力書式は**訓練書式そのもの**
  - `t2`  英語の文章題。入力書式は訓練から遠い

二値出力の対(T3 / T1b)は code/eval/battery/t3_comparison.py にある。
真値・規則値の計算はどちらも同じだが、**採点に渡す型が int か bool かで
分かれる**(code/eval/scoring.py の classify が型で検査する)。

**`group` の名前は仕様が曖昧な箇所である(skill code-style §5)。**
ADR-032 決定5 が決めたのは T2 の群名 `word_problem` だけで、T1 の群名は
どの ADR にも無い。t3_comparison.py が `group` を「このモジュールが作る項目の型」
としたのに倣い、T1 は **`bare_sum`** とした。**この命名は人間が覆してよい。**

**T1 の文面はテンプレート集合から取ってはならない。**T1 は §5.2 の
**評価アンカー**であり、その書式は訓練の `data.prompt_template` と1文字も
違ってはならない(PLAN-002 §4.8.1 検査6 が `format_hash` を照合する)。
render_prompt に渡す文字列の出どころは呼び出し側の責務だが、T1 については
**config の `data.prompt_template` を渡すこと**。評価用テンプレート集合
(`data.eval_template_set`)から引くと、アンカーが静かに訓練書式から離れる。

項目構成(PLAN-003 §4.2 / §4.3):
  - 既知性の層は `id` / `interp` / `extrap_magnitude`、層別は carry / nocarry
  - 真値は a + b、規則値は参照規則の apply。**両者が割れない項目は生成時に弾く**
  - T2 は**被演算子 1 を除外する**(ADR-032 決定4。`1 apples` が非文になる)
  - T2 のテンプレート割当は**内容から決まる**ので、条件間・シード間で一致する
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from code.config import require
from code.data_gen.battery_items import Item, make_item
from code.data_gen.hashing import canonical_json, sha256_text
from code.data_gen.pool import Pair
from code.eval.scoring import ItemResponse
from code.lesion import Lesion

# タスク型(PLAN-003 §3.1 の要因「タスク型」のうち、出力が数値の2水準)
T1 = "t1"
T2 = "t2"

# 群(= テンプレート集合の最上位キー、battery_items.SUPPORTED_GROUPS の要素)
GROUP_BARE_SUM = "bare_sum"
GROUP_WORD_PROBLEM = "word_problem"

# category。T1 は表層が1種類しかないので極性のような下位の軸を持たない。
T1_CATEGORY = "t1"

# T2 の5場面(ADR-032 決定5)。**文面は configs/templates/t2.yaml が正本**であり、
# ここには持たない(実験条件。CLAUDE.md §8)。順序は割当のハッシュに効くので
# **並べ替えない** —— 並べ替えると同じ項目が別のテンプレートに移る。
T2_CATEGORIES: tuple[str, ...] = (
    "t2_count",
    "t2_people",
    "t2_distance",
    "t2_money",
    "t2_time",
)

CATEGORY_AXES: dict[str, tuple[str, str]] = {
    T1_CATEGORY: (T1, GROUP_BARE_SUM),
    **{category: (T2, GROUP_WORD_PROBLEM) for category in T2_CATEGORIES},
}

# T2 が使えない被演算子(ADR-032 決定4)。`1 apples` が非文になるため。
# 主域の正象限 99 x 99 = 9,801 組のうち 197 組(2.0%)が該当する
# (幾何的な数え上げであって実測値ではない。PLAN-003 §4.3 規約7)。
EXCLUDED_OPERANDS_T2: frozenset[int] = frozenset({1})


class UndefinedRuleValueError(ValueError):
    """参照規則がこの項目で規則適用値を持たない(ADR-020)。

    `arb` のズレ表は t in [2, 198] でしか定義されない。定義域を広げないのが
    ADR-020 の決定なので、定義域外は**エラーではなく「その規則の評価対象外」**
    として扱う。呼ぶ前に `is_defined_for` で確かめること。
    """


class ExcludedOperandError(ValueError):
    """T2 に使えない被演算子の組が項目生成に来た(ADR-032 決定4)。

    黙って落とさない。**落とすとセルの件数が静かに減り**、条件間で項目集合が
    変わって混合効果モデルの項目ランダム効果が条件と交絡する(PLAN-001 §3)。
    除外は候補の段階で `eligible_word_problem_pairs` により行う。
    """


# --------------------------------------------------------------------------
# category の軸
# --------------------------------------------------------------------------


def _axes_of(category: str) -> tuple[str, str]:
    axes = CATEGORY_AXES.get(category)
    if axes is None:
        raise ValueError(f"未知の category: {category!r}。あるのは {sorted(CATEGORY_AXES)}")
    return axes


def task_type_of(category: str) -> str:
    """項目のタスク型(t1 / t2)。主軸の要因水準そのもの(ADR-026)。"""
    return _axes_of(category)[0]


def group_of(category: str) -> str:
    """項目の群。テンプレート集合の最上位キーでもある。"""
    return _axes_of(category)[1]


# --------------------------------------------------------------------------
# T2 の被演算子の除外(ADR-032 決定4)
# --------------------------------------------------------------------------


def is_excluded_operand_pair(pair: Pair) -> bool:
    """T2 で使えない組か。

    答える問い: 「この組を文章題に差し込むと非文になるか」
    """
    return any(operand in EXCLUDED_OPERANDS_T2 for operand in pair)


def eligible_word_problem_pairs(pairs: Sequence[Pair]) -> list[Pair]:
    """T2 のセルを埋める候補から、除外対象の組を落とす(ADR-032 決定4)。

    答える問い: 「文章題のセルは、どの組から埋めてよいか」

    **fill_cells に渡す前に掛ける。**後段(build_items)で落とすと件数が
    足りないまま項目が減り、`InsufficientCandidatesError` が上がる機会も失われる。
    """
    return [pair for pair in pairs if not is_excluded_operand_pair(pair)]


def word_problem_exclusion_record(candidates: Sequence[Pair]) -> dict[str, object]:
    """除外を manifest に残す形にする(ADR-032 決定4 の「記録すること」)。

    答える問い: 「T2 だけ被演算子分布が違う理由を、後から manifest で辿れるか」

    `pool.build_manifest` の `item_exclusions` に入れる。プール全体の除外
    (§4.3 の偶然一致)とは別物である —— あちらは参照規則から決まり、
    こちらは**文の自然さ**から決まる。
    """
    excluded = [pair for pair in candidates if is_excluded_operand_pair(pair)]
    return {
        "group": GROUP_WORD_PROBLEM,
        "excluded_operands": sorted(EXCLUDED_OPERANDS_T2),
        "rule": "ADR-032 決定4(PLAN-003 §4.3 規約7)",
        "reason": "被演算子 1 は文章題で非文になる(1 apples)",
        "n_candidates": len(candidates),
        "n_excluded": len(excluded),
    }


# --------------------------------------------------------------------------
# テンプレートの割当(PLAN-003 §4.3)
# --------------------------------------------------------------------------


def template_category(pair: Pair, pool_id: str) -> str:
    """T2 の項目にどの場面テンプレートを割り当てるか。

    答える問い: 「同じ組は、どの条件・どのシードでも同じ場面で尋ねられるか」

    §4.3 は「項目 → テンプレートの割当は `item_id` のハッシュで決め、
    条件間で完全に一致させる」と書いている。**`item_id` は category を
    含む**(battery_items.make_item)ので、そのままでは循環する。よって
    `item_id` の代わりに **category を除いた内容 `(pool_id, a, b)`** を畳む。
    「条件間・シード間で完全に一致する」という要求は満たす —— 乱数を使わず、
    条件にもシードにも依存しない量だけから決まるからである。
    **この読み替えは実装で確定させた点であり、人間が覆してよい。**

    テンプレートは統計モデルの `(1 | template)` の水準そのもの
    (Documents/05_STATISTICS.md §123)。割当が条件間でずれると、
    変量効果が条件と交絡する。
    """
    digest = sha256_text(canonical_json([pool_id, pair[0], pair[1]]))
    return T2_CATEGORIES[int(digest, 16) % len(T2_CATEGORIES)]


# --------------------------------------------------------------------------
# 真値と規則値
# --------------------------------------------------------------------------


def item_total(item: Item) -> int:
    """項目の真値 t = a + b。"""
    return item.operands[0] + item.operands[1]


def is_defined_for(item: Item, lesion: Lesion) -> bool:
    """この項目で、この参照規則は規則適用値を持つか(ADR-020)。

    答える問い: 「この項目を、この参照規則の評価に入れてよいか」
    """
    return lesion.is_defined(item.operands[0], item.operands[1])


def answers(item: Item, lesion: Lesion) -> tuple[int, int]:
    """(真値, 規則適用値) を返す。

    答える問い: 「この項目で、正しく答えたモデルと病変規則に従うモデルは
    それぞれ何と答えるか」

    定義域外で呼ぶと `UndefinedRuleValueError` で止まる。呼ぶ前に
    `is_defined_for` で確かめること(ADR-020)。
    """
    a, b = item.operands[0], item.operands[1]
    if not is_defined_for(item, lesion):
        raise UndefinedRuleValueError(
            f"項目 {item.item_id} は参照規則 {getattr(lesion, 'name', lesion)!r} の"
            f"定義域外(t={a + b})。定義域外はその規則の評価から外す(ADR-020 決定2)。"
        )
    return a + b, lesion.apply(a, b)


def is_discriminating(item: Item, lesion: Lesion) -> bool:
    """真値と規則適用値が割れる項目か(PLAN-003 §4.1.3)。

    割れない項目は correct と rule を区別できない。4値分解の排他性が
    成り立たなくなるので、生成時に弾く(CLAUDE.md §6)。
    """
    truth, rule_value = answers(item, lesion)
    return truth != rule_value


# --------------------------------------------------------------------------
# 項目の生成
# --------------------------------------------------------------------------


def build_bare_sum_items(
    pairs: Sequence[Pair], *, pool_id: str, reference_lesions: Mapping[str, Lesion]
) -> list[Item]:
    """T1(裸の計算式)の項目を作る。

    答える問い: 「これらの組から、訓練書式そのままの評価アンカーを作れるか」
    """
    return [
        _build_one(pair, pool_id=pool_id, category=T1_CATEGORY, reference_lesions=reference_lesions)
        for pair in pairs
    ]


def build_word_problem_items(
    pairs: Sequence[Pair], *, pool_id: str, reference_lesions: Mapping[str, Lesion]
) -> list[Item]:
    """T2(文章題)の項目を作る。場面テンプレートは内容から決まる。

    答える問い: 「これらの組から、5場面に散った文章題を作れるか」

    **被演算子 1 を含む組が来たら止める**(ADR-032 決定4)。落とすのは
    候補の段階(`eligible_word_problem_pairs`)であって、ここではない。
    """
    items: list[Item] = []
    for pair in pairs:
        if is_excluded_operand_pair(pair):
            raise ExcludedOperandError(
                f"組 {pair} は被演算子 {sorted(EXCLUDED_OPERANDS_T2)} を含むため T2 に使えない"
                "(ADR-032 決定4)。候補の段階で eligible_word_problem_pairs を掛けること。"
            )
        # 0 / 負の被演算子は主軸の3水準に構成的に現れない(§3.3。T2 が
        # 「りんごを −3 個」と書けないことが被覆水準を id / interp /
        # extrap_magnitude に絞った理由そのもの)。**除外ではなく安全網である。**
        # ここが発火したら、セル定義が §3.3 の導出から外れている。
        if any(operand <= 0 for operand in pair):
            raise ExcludedOperandError(
                f"組 {pair} は 0 / 負の被演算子を含む。T2 の被覆水準は構成的に a,b >= 1 で"
                "あり(PLAN-003 §3.3)、文章題として自然文にならない。セル定義を見直すこと。"
            )
        items.append(
            _build_one(
                pair,
                pool_id=pool_id,
                category=template_category(pair, pool_id),
                reference_lesions=reference_lesions,
            )
        )
    return items


def _build_one(
    pair: Pair, *, pool_id: str, category: str, reference_lesions: Mapping[str, Lesion]
) -> Item:
    """1組から項目を1件作り、判別可能性を生成時に確かめる。

    reference_lesions のすべてについて真値と規則値が割れることを**生成時に**
    確かめる。実行時ではなく生成時に弾くのは、採点側で落とすと条件ごとに
    項目集合が変わり、混合効果モデルの項目ランダム効果が条件と交絡するため
    (PLAN-001 §3)。**定義域外の参照規則には判別可能性を問わない**(ADR-020 決定2)。
    """
    if not reference_lesions:
        raise ValueError("参照規則が空。判別可能性を確かめられない(PLAN-001 §5.3)")
    item = make_item(pool_id=pool_id, group=group_of(category), category=category, operands=pair)
    for name, lesion in reference_lesions.items():
        if not is_defined_for(item, lesion):
            continue
        if not is_discriminating(item, lesion):
            raise ValueError(
                f"項目 {item.item_id} は参照規則 {name!r} で真値と規則値が一致する。"
                "correct と rule を区別できないため使えない(PLAN-001 §4.3、§5.3)。"
            )
    return item


# --------------------------------------------------------------------------
# 採点への受け渡しと文面
# --------------------------------------------------------------------------


def to_response(
    item: Item, parsed: int | None, reference_lesions: Mapping[str, Lesion]
) -> ItemResponse:
    """採点器に渡す形にする。

    答える問い: 「この数値応答を、参照規則ごとにどう採点するか」

    真値・規則適用値はここで **int** のままにする。T3 / T1b の bool と
    混ざらないことは scoring.classify が型で検査する(`True == 1` が成立
    してしまうため)。

    **定義域外の参照規則は `rule_values` に入れない。既定値で埋めない**
    (ADR-020 決定2)。帰結として、定義域内の項目と定義域外の項目を同じ採点
    バッチに混ぜると `scoring._shared_reference_rules` が止める。
    """
    rule_values = {
        name: answers(item, lesion)[1]
        for name, lesion in reference_lesions.items()
        if is_defined_for(item, lesion)
    }
    return ItemResponse(
        item_id=item.item_id, parsed=parsed, truth=item_total(item), rule_values=rule_values
    )


def bare_sum_templates(config: Mapping[str, object]) -> dict[str, str]:
    """T1 のテンプレート集合を config の**訓練書式**から組む。

    答える問い: 「評価アンカーは、訓練と同じ書式で尋ねられているか」

    正しい経路を一番短い経路にするための関数である。T1 の文面を
    `data.eval_template_set` から引くと、アンカーが静かに訓練書式から離れ、
    PLAN-002 §4.8.1 検査6 が「訓練と評価で書式が違う」で止まる。
    """
    return {T1_CATEGORY: require(config, "data.prompt_template")}


def render_prompt(item: Item, templates: Mapping[str, str]) -> str:
    """テンプレート集合から質問文を組む。

    答える問い: 「この項目をモデルにどう尋ねるか」

    テンプレートの中身はここに書かない。**実験条件である。**
    T2 の正本は `configs/templates/t2.yaml`(ADR-032)。
    **T1 は評価用テンプレート集合から引かず、config の `data.prompt_template`
    を渡すこと**(モジュール冒頭の注記。検査6 が書式を照合する)。
    """
    template = templates.get(item.category)
    if template is None:
        raise KeyError(
            f"テンプレート集合に category {item.category!r} が無い。"
            f"あるのは {sorted(templates)}"
        )
    return template.format(a=item.operands[0], b=item.operands[1])
