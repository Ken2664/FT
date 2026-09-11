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
from code.data_gen import pool
from code.data_gen.battery_items import Item, make_item
from code.data_gen.hashing import canonical_json, sha256_text
from code.data_gen.pool import Pair
from code.eval.scoring import ItemResponse
from code.lesion import Lesion

# タスク型(PLAN-003 §3.1 の要因「タスク型」のうち、出力が数値の2水準)
T1 = "t1"
T2 = "t2"

# **副次セルのタスク型**(ADR-035 決定2。指示付き T1)。
# **主軸の4水準(t1 / t1b / t2 / t3)に混ぜない。**混ぜると交互作用の df が動く
# (ADR-026 が 4 → 6 にしたもの)。この水準は探索的にのみ報告する。
T1_INSTRUCTED = "t1_instructed"

# 群(= テンプレート集合の最上位キー、battery_items.SUPPORTED_GROUPS の要素)
GROUP_BARE_SUM = "bare_sum"
GROUP_BARE_SUM_INSTRUCTED = "bare_sum_instructed"
GROUP_WORD_PROBLEM = "word_problem"

# category。T1 は表層が1種類しかないので極性のような下位の軸を持たない。
T1_CATEGORY = "t1"
T1_INSTRUCTED_CATEGORY = "t1_instructed"

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
    T1_INSTRUCTED_CATEGORY: (T1_INSTRUCTED, GROUP_BARE_SUM_INSTRUCTED),
    **{category: (T2, GROUP_WORD_PROBLEM) for category in T2_CATEGORIES},
}

# 指示付き T1 の文面を組むときに、訓練書式と指示文をつなぐ文字列(ADR-035 決定2)。
# **T2 が本文と指示文を継ぐのと同じ半角空白1つ**である。ADR-035 決定2 が
# 指定していない唯一の自由度であり、**人間が覆してよい**(PLAN-008 §2-1 d)。
ANSWER_FORMAT_INSTRUCTION_JOIN = " "


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
    除外は候補の段階で `code/data_gen/pool.py` の `eligible_item_pairs` により行う。
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
# 被演算子の除外(ADR-032 決定4 → ADR-035 決定3 で全タスク型に昇格)
# --------------------------------------------------------------------------
#
# **規約の持ち主は code/data_gen/pool.py である。**ADR-035 決定3 で
# 「被演算子 1 を評価項目に入れない」は T2 固有の規則ではなくなり、
# プール全体の項目規約になった。除外集合をこのモジュールが持ち続けると、
# T1 / T3 / 特異性対照が別の集合を見る余地が残る。
#
# ここに残すのは **T2 の安全網だけ**である(下の build_word_problem_items)。


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


def non_discriminating_rules(item: Item, reference_lesions: Mapping[str, Lesion]) -> list[str]:
    """この項目で真値と規則適用値が一致してしまう参照規則の名前。

    答える問い: 「この項目は、どの参照規則の下で correct と rule を
    区別できないか」

    **定義域外の規則には判別可能性を問わない**(ADR-020 決定2)。判定を
    1箇所に置くのは、生成時に弾く経路(`_build_one`)と、候補から落とす経路
    (`code/eval/battery/magnitude_sweep.py`)が同じ規則を使うためである。
    ずれると、片方だけが判別不能な項目を通す。
    """
    return [
        name
        for name, lesion in reference_lesions.items()
        if is_defined_for(item, lesion) and not is_discriminating(item, lesion)
    ]


# --------------------------------------------------------------------------
# 項目の生成
# --------------------------------------------------------------------------


def build_bare_sum_items(
    pairs: Sequence[Pair],
    *,
    pool_id: str,
    reference_lesions: Mapping[str, Lesion],
    params: dict[str, int | str] | None = None,
) -> list[Item]:
    """T1(裸の計算式)の項目を作る。

    答える問い: 「これらの組から、訓練書式そのままの評価アンカーを作れるか」

    `params` は item_id に載る付帯情報である(`code/data_gen/battery_items.py`
    の `make_item`)。評価プールは使わない。桁数掃引だけが `radius` を載せ、
    同じ (a, b) を別の M で引いたときに item_id が衝突しないようにする。
    """
    return [
        _build_one(
            pair,
            pool_id=pool_id,
            category=T1_CATEGORY,
            reference_lesions=reference_lesions,
            params=params,
        )
        for pair in pairs
    ]


def build_instructed_sum_items(
    pairs: Sequence[Pair],
    *,
    pool_id: str,
    reference_lesions: Mapping[str, Lesion],
) -> list[Item]:
    """指示付き T1(副次セル)の項目を作る(ADR-035 決定2)。

    答える問い: 「答え書式の指示の有無は、T1 の成績をどれだけ動かすか」
    (PLAN-003 §11-18 の交絡 #18 を実測するための副次セル)

    **T1 と同一の被演算子対を使う。**項目の中身は `build_bare_sum_items` と
    同じで、違うのは category(= 文面の出どころ)だけである。違う組を使うと
    「指示の有無」の効果が組の差と交絡する。

    **主軸の交互作用モデルには入れない**(決定2)。探索的な副次セルであり、
    多重比較の補正は行わず、補正なしと明記して報告する。
    """
    return [
        _build_one(
            pair,
            pool_id=pool_id,
            category=T1_INSTRUCTED_CATEGORY,
            reference_lesions=reference_lesions,
        )
        for pair in pairs
    ]


def build_word_problem_items(
    pairs: Sequence[Pair], *, pool_id: str, reference_lesions: Mapping[str, Lesion]
) -> list[Item]:
    """T2(文章題)の項目を作る。場面テンプレートは内容から決まる。

    答える問い: 「これらの組から、5場面に散った文章題を作れるか」

    **除外対象の被演算子を含む組が来たら止める**(ADR-032 決定4 / ADR-035 決定3)。
    落とすのは候補の段階(`pool.eligible_item_pairs`)であって、ここではない。
    """
    items: list[Item] = []
    for pair in pairs:
        _refuse_unusable_word_problem_pair(pair)
        items.append(
            _build_one(
                pair,
                pool_id=pool_id,
                category=template_category(pair, pool_id),
                reference_lesions=reference_lesions,
            )
        )
    return items


def build_word_problem_items_in_scene(
    pairs: Sequence[Pair],
    *,
    scene: str,
    pool_id: str,
    reference_lesions: Mapping[str, Lesion],
) -> list[Item]:
    """T2 の項目を**指定した場面で**作る(ADR-076 決定6。タスク6 の交差プール専用)。

    答える問い: 「同じ組を、ハッシュが割り当てたのとは別の場面で尋ねるとどうなるか」

    **主プールでは使わない。**主プールの場面は `(pool_id, a, b)` のハッシュで決まり
    (`template_category`)、条件間・シード間で割当が一致することが保証されている。
    タスク6(プロンプト感受性)は「同じ問いを 5 場面で訊いたときの分散」を測るので、
    主プールの T2 の組を**残り 4 場面**で尋ねる項目が要る。それを主プールとは別の
    ディレクトリに置く(`code/data_gen/eval_pool.py` の `build_t2_cross`)。
    """
    if scene not in T2_CATEGORIES:
        raise ValueError(f"未知の場面: {scene!r}。あるのは {list(T2_CATEGORIES)}")
    items: list[Item] = []
    for pair in pairs:
        _refuse_unusable_word_problem_pair(pair)
        items.append(
            _build_one(pair, pool_id=pool_id, category=scene, reference_lesions=reference_lesions)
        )
    return items


def _refuse_unusable_word_problem_pair(pair: Pair) -> None:
    """T2 に使えない組が来たら止める(除外対象の被演算子 / 0 と負)。"""
    if pool.is_excluded_operand_pair(pair):
        raise ExcludedOperandError(
            f"組 {pair} は評価項目に使えない被演算子 {sorted(pool.EXCLUDED_OPERANDS)} を"
            "含む(ADR-032 決定4 / ADR-035 決定3)。"
            "候補の段階で pool.eligible_item_pairs を掛けること。"
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


def _build_one(
    pair: Pair,
    *,
    pool_id: str,
    category: str,
    reference_lesions: Mapping[str, Lesion],
    params: dict[str, int | str] | None = None,
) -> Item:
    """1組から項目を1件作り、判別可能性を生成時に確かめる。

    reference_lesions のすべてについて真値と規則値が割れることを**生成時に**
    確かめる。実行時ではなく生成時に弾くのは、採点側で落とすと条件ごとに
    項目集合が変わり、混合効果モデルの項目ランダム効果が条件と交絡するため
    (PLAN-001 §3)。**定義域外の参照規則には判別可能性を問わない**(ADR-020 決定2)。
    """
    if not reference_lesions:
        raise ValueError("参照規則が空。判別可能性を確かめられない(PLAN-001 §5.3)")
    item = make_item(
        pool_id=pool_id,
        group=group_of(category),
        category=category,
        operands=pair,
        params=params,
    )
    coincident = non_discriminating_rules(item, reference_lesions)
    if coincident:
        raise ValueError(
            f"項目 {item.item_id} は参照規則 {coincident} で真値と規則値が一致する。"
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


def instructed_sum_templates(config: Mapping[str, object]) -> dict[str, str]:
    """指示付き T1 の文面を config から組む(ADR-035 決定2)。

    答える問い: 「副次セルの文面は、T1 の書式と T2 の指示文から
    構成的に決まっているか」

    **テンプレート集合(`data.eval_template_set`)から引かない。**決定2 は
    項目を「**T1 と同一の被演算子対**に、**T2 と逐語で同じ**指示文を付けた版」
    と定義しており、この2つの不変条件はテンプレートファイルに書き下すと
    静かに壊れうる(訓練書式を変えても指示付き版は追従しない)。ここで
    `data.prompt_template` と `data.answer_format_instruction` から組めば、
    構成的に保たれる。

    **T1 本体(`bare_sum`)とは別物である。**あちらは §5.2 の評価アンカーで
    あり preflight 検査6 が訓練書式との一致を照合するが、こちらは
    **わざと訓練書式から離す**セルなので照合の対象ではない。
    """
    template = require(config, "data.prompt_template")
    instruction = require(config, "data.answer_format_instruction")
    return {
        T1_INSTRUCTED_CATEGORY: f"{template}{ANSWER_FORMAT_INSTRUCTION_JOIN}{instruction}"
    }


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
