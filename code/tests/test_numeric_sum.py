"""T1 / T2 の項目生成(code/eval/battery/numeric_sum.py)のユニットテスト。

答える問い: PLAN-003 §4.2 / §4.3「T1 と T2 の項目はどう構成されるか」が
コードの上で守られているか。

ここで固定する最重要の性質:
  - **真値と規則適用値が割れない項目は生成時に落ちる**(CLAUDE.md §6)
  - **4値の合計は 1.0**(skill code-style §4)
  - **T2 は被演算子 1 を候補の段階で外す**(ADR-032 決定4)。項目生成に来たら止まる
  - **T2 のテンプレート割当は内容だけから決まる**(条件間・シード間で一致する)
  - 数値項目の真値は **int**。二値項目の bool と混ざらない(scoring.classify)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from code.config import ConfigError
from code.data_gen.battery_items import assert_unique_item_ids
from code.data_gen.pool import CARRY, NOCARRY
from code.eval.battery import numeric_sum
from code.eval.scoring import metrics_by_reference_rule
from code.lesion import (
    AdditiveLesion,
    ArbitraryLesion,
    IdentityLesion,
    MultiplicativeLesion,
)

# 実験条件ではない。機構が動くかを見るための小さな値である。
PROJECT_OFFSET = 2
PROJECT_MULTIPLIER = 2
SMALL_ARB_TABLE = {total: total + 3 for total in range(2, 19)}

P2 = AdditiveLesion(offset=PROJECT_OFFSET, name="p2")
X2 = MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER, name="x2")
ARB = ArbitraryLesion(table=dict(SMALL_ARB_TABLE), name="arb")
TOTAL_RULES = {"p2": P2, "x2": X2}

T2_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "configs" / "templates" / "t2.yaml"


def load_t2_templates() -> dict[str, str]:
    """ADR-032 で確定した T2 の5テンプレート(正本は configs/templates/t2.yaml)。"""
    return yaml.safe_load(T2_TEMPLATE_PATH.read_text(encoding="utf-8"))[
        numeric_sum.GROUP_WORD_PROBLEM
    ]


# --------------------------------------------------------------------------
# category の軸
# --------------------------------------------------------------------------


def test_category_maps_to_a_task_type_and_a_group() -> None:
    assert numeric_sum.task_type_of(numeric_sum.T1_CATEGORY) == numeric_sum.T1
    assert numeric_sum.group_of(numeric_sum.T1_CATEGORY) == numeric_sum.GROUP_BARE_SUM
    for category in numeric_sum.T2_CATEGORIES:
        assert numeric_sum.task_type_of(category) == numeric_sum.T2
        assert numeric_sum.group_of(category) == numeric_sum.GROUP_WORD_PROBLEM


def test_unknown_category_is_refused() -> None:
    with pytest.raises(ValueError, match="未知の category"):
        numeric_sum.task_type_of("t2_weather")


# --------------------------------------------------------------------------
# T1 の項目生成
# --------------------------------------------------------------------------


def test_bare_sum_items_carry_the_group_and_the_stratum() -> None:
    """群・category・繰り上がり層が項目に乗ること(§4.2)。"""
    items = numeric_sum.build_bare_sum_items(
        [(3, 4), (9, 9)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    assert [item.group for item in items] == [numeric_sum.GROUP_BARE_SUM] * 2
    assert [item.category for item in items] == [numeric_sum.T1_CATEGORY] * 2
    # t=7 は繰り上がらない / t=18 は +2 で十の位が動く(pool.carry_label)。
    assert [item.carry for item in items] == [NOCARRY, CARRY]
    assert_unique_item_ids(items)


def test_the_same_pair_gives_different_ids_across_task_types() -> None:
    """T1 と T2 は同じ組でも別項目である(項目ランダム効果が壊れない)。"""
    bare = numeric_sum.build_bare_sum_items(
        [(3, 4)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    word = numeric_sum.build_word_problem_items(
        [(3, 4)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    assert bare[0].item_id != word[0].item_id
    assert_unique_item_ids(bare + word)


def test_a_degenerate_reference_rule_is_refused_at_generation() -> None:
    """★ident は全項目で真値と一致する。生成時に止める(CLAUDE.md §6)。"""
    with pytest.raises(ValueError, match="真値と規則値が一致"):
        numeric_sum.build_bare_sum_items(
            [(3, 4)], pool_id="main", reference_lesions={"ident": IdentityLesion(name="ident")}
        )


def test_a_coincidental_item_is_refused_at_generation() -> None:
    """★x2 は t=0 で真値と一致する(§4.1.3 の表)。生成時に止める。"""
    with pytest.raises(ValueError, match="真値と規則値が一致"):
        numeric_sum.build_bare_sum_items(
            [(3, -3)], pool_id="main", reference_lesions={"x2": X2}
        )


def test_an_empty_reference_rule_set_is_refused() -> None:
    with pytest.raises(ValueError, match="参照規則が空"):
        numeric_sum.build_bare_sum_items([(3, 4)], pool_id="main", reference_lesions={})


def test_an_item_outside_the_arb_domain_is_kept_but_not_scored_by_arb() -> None:
    """★定義域外は「エラー」ではなく「その規則の評価対象外」(ADR-020 決定2)。"""
    rules = {"p2": P2, "arb": ARB}
    items = numeric_sum.build_bare_sum_items([(60, 60)], pool_id="main", reference_lesions=rules)
    assert len(items) == 1
    response = numeric_sum.to_response(items[0], 120, rules)
    assert set(response.rule_values) == {"p2"}


# --------------------------------------------------------------------------
# 採点への受け渡し
# --------------------------------------------------------------------------


def test_response_carries_integer_truth_and_rule_values() -> None:
    items = numeric_sum.build_bare_sum_items(
        [(3, 4)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    response = numeric_sum.to_response(items[0], 9, TOTAL_RULES)
    assert response.truth == 7
    assert response.rule_values == {"p2": 9, "x2": 14}
    assert not isinstance(response.truth, bool)


def test_a_boolean_response_is_refused_by_scoring() -> None:
    """★Yes を数値項目の 1 と突き合わせる取り違えを型で止める。"""
    items = numeric_sum.build_bare_sum_items(
        [(3, 4)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    response = numeric_sum.to_response(items[0], True, TOTAL_RULES)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        metrics_by_reference_rule([response], "p2")


def test_the_four_rates_sum_to_one() -> None:
    """★4値は排他かつ網羅(CLAUDE.md §6、skill code-style §4)。"""
    pairs = [(3, 4), (5, 6), (7, 8), (2, 3)]
    items = numeric_sum.build_bare_sum_items(
        pairs, pool_id="main", reference_lesions=TOTAL_RULES
    )
    # correct / rule / other_error / parse_fail を1件ずつ作る。
    parsed: list[int | None] = [7, 13, 999, None]
    responses = [
        numeric_sum.to_response(item, value, TOTAL_RULES)
        for item, value in zip(items, parsed, strict=True)
    ]
    metrics = metrics_by_reference_rule(responses, "p2")
    block = metrics["by_reference_rule"]["p2"]  # type: ignore[index]
    assert block["correct_rate"] == 0.25
    assert block["rule_rate"] == 0.25
    assert block["other_error_rate"] == 0.25
    assert block["parse_fail_rate"] == 0.25
    assert sum(block[key] for key in block if key.endswith("_rate")) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# T2: 被演算子 1 の除外(ADR-032 決定4)
# --------------------------------------------------------------------------


def test_operand_one_is_excluded_from_word_problems() -> None:
    assert numeric_sum.is_excluded_operand_pair((1, 5))
    assert numeric_sum.is_excluded_operand_pair((5, 1))
    assert not numeric_sum.is_excluded_operand_pair((2, 5))


def test_eligible_pairs_drop_the_excluded_operand() -> None:
    """★候補の段階で落とす。fill_cells に渡る前でなければ件数が静かに減る。"""
    candidates = [(1, 5), (2, 5), (5, 1), (5, 2)]
    assert numeric_sum.eligible_word_problem_pairs(candidates) == [(2, 5), (5, 2)]


def test_building_a_word_problem_from_an_excluded_pair_stops() -> None:
    """★黙って落とさない。落とすとセルの件数が静かに減る。"""
    with pytest.raises(numeric_sum.ExcludedOperandError):
        numeric_sum.build_word_problem_items(
            [(1, 5)], pool_id="main", reference_lesions=TOTAL_RULES
        )


def test_a_non_positive_operand_stops_the_word_problem_generator() -> None:
    """★安全網。0 / 負は主軸の3水準に構成的に現れない(§3.3)。

    発火したらセル定義が §3.3 の導出から外れている。**除外ではない** ——
    黙って落とすと「文章題に負数が来ない」という前提が検証されないまま通る。
    """
    with pytest.raises(numeric_sum.ExcludedOperandError, match="0 / 負"):
        numeric_sum.build_word_problem_items(
            [(-3, 5)], pool_id="main", reference_lesions=TOTAL_RULES
        )


def test_the_exclusion_is_recorded_for_the_manifest() -> None:
    """ADR-032 決定4 の「除外を manifest に記録すること」。"""
    record = numeric_sum.word_problem_exclusion_record([(1, 5), (2, 5), (5, 1)])
    assert record["group"] == numeric_sum.GROUP_WORD_PROBLEM
    assert record["excluded_operands"] == [1]
    assert record["n_candidates"] == 3
    assert record["n_excluded"] == 2


# --------------------------------------------------------------------------
# T2: テンプレートの割当
# --------------------------------------------------------------------------


def test_template_assignment_is_determined_by_content_alone() -> None:
    """★条件間・シード間で同じ組が同じ場面に落ちる(§4.3)。"""
    assert numeric_sum.template_category((3, 4), "main") == numeric_sum.template_category(
        (3, 4), "main"
    )
    # 順序対である。(3,4) と (4,3) は別の項目なので割当も独立に決まる。
    assert numeric_sum.template_category((3, 4), "main") in numeric_sum.T2_CATEGORIES
    assert numeric_sum.template_category((4, 3), "main") in numeric_sum.T2_CATEGORIES


def test_every_template_is_used_somewhere() -> None:
    """5場面が全部出ること。1つでも死んでいれば (1 | template) の水準が欠ける。"""
    assigned = {
        numeric_sum.template_category((a, b), "main")
        for a in range(2, 20)
        for b in range(2, 20)
    }
    assert assigned == set(numeric_sum.T2_CATEGORIES)


# --------------------------------------------------------------------------
# 文面(正本は configs/templates/t2.yaml。ADR-032)
# --------------------------------------------------------------------------


def test_the_template_file_holds_exactly_the_five_categories() -> None:
    """★コードの category 集合と ADR-032 の文面ファイルがずれていないこと。"""
    assert set(load_t2_templates()) == set(numeric_sum.T2_CATEGORIES)


def test_every_word_problem_asks_the_question_the_same_way() -> None:
    """ADR-032 決定2: 変わるのは場面と単位語だけ。問いの語は5本で一致。"""
    templates = load_t2_templates()
    for text in templates.values():
        assert "How many " in text
        assert " in total?" in text
        # 決定3: 末尾の答え書式の指示は5本とも同一文。
        assert text.endswith('End your reply with "Answer: <number>".')


def test_rendering_a_word_problem_inserts_both_operands() -> None:
    templates = load_t2_templates()
    items = numeric_sum.build_word_problem_items(
        [(150, 170)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    prompt = numeric_sum.render_prompt(items[0], templates)
    assert "150" in prompt
    assert "170" in prompt
    assert "{a}" not in prompt


def test_rendering_a_bare_sum_uses_the_training_surface() -> None:
    """★T1 は評価用テンプレート集合ではなく data.prompt_template を使う。"""
    items = numeric_sum.build_bare_sum_items(
        [(3, 4)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    prompt = numeric_sum.render_prompt(items[0], {numeric_sum.T1_CATEGORY: "{a}+{b}="})
    assert prompt == "3+4="


def test_the_bare_sum_template_comes_from_the_training_config() -> None:
    """★正しい経路を一番短い経路にする。null なら既定値を作らず止まる。"""
    config = {"data": {"prompt_template": "{a}+{b}="}}
    assert numeric_sum.bare_sum_templates(config) == {numeric_sum.T1_CATEGORY: "{a}+{b}="}
    with pytest.raises(ConfigError):
        numeric_sum.bare_sum_templates({"data": {"prompt_template": None}})


def test_a_missing_template_is_refused() -> None:
    items = numeric_sum.build_bare_sum_items(
        [(3, 4)], pool_id="main", reference_lesions=TOTAL_RULES
    )
    with pytest.raises(KeyError):
        numeric_sum.render_prompt(items[0], {})
