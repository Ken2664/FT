"""T1c 合成の探り(code/eval/battery/composition.py)のユニットテスト。

答える問い: PLAN-037 §6 I1 と §3.3 の必ず守ること(3)「各参照規則のブロックの中で 4 値の
合計は 1.0」が、コードの上で守られているか。

固定する性質:
  - t・t+offset・t+2·offset が割れる。offset = 0 は生成時に止まる
  - 加算(p2)・特異性の参照規則を 3 項の項目に渡せない
  - 2 つのブロック(comp_once・comp_twice)の中で 4 値の合計が 1.0。rate(t) は両ブロックで同じ
  - 参照規則は FT データの除外集合(reference_lesions_from_config)に混ざらない
  - 文面は config から来て、差し込み変数が過不足なら止まる
"""

from __future__ import annotations

from typing import Any

import pytest

from code.config import ConfigError
from code.data_gen.battery_items import make_item
from code.eval.battery import composition
from code.eval.scoring import metrics_by_reference_rule
from code.lesion import (
    COMPOSITION_ONCE,
    COMPOSITION_TWICE,
    AdditiveLesion,
    CompositionOffsetLesion,
    composition_reference_lesions_from_config,
    reference_lesions_from_config,
    specificity_reference_lesions_from_config,
)

# 実験条件ではない。機構が動くかを見るための小さな config。
CONFIG: dict[str, Any] = {
    "lesion": {"condition": "p2", "offset": 2, "multiplier": 2, "digit_modulus": 10},
    "eval": {"composition": {"prompt_template": "{a}+{b}+{c}="}},
}
OFFSET = 2


def rules() -> dict[str, CompositionOffsetLesion]:
    return composition_reference_lesions_from_config(CONFIG)


def item(operands: tuple[int, int, int] = (12, 25, 8)):  # noqa: ANN201
    return composition.build_item(operands, pool_id="test", reference_lesions=rules())


# --------------------------------------------------------------------------
# 参照規則(code/lesion.py)
# --------------------------------------------------------------------------


def test_the_reference_rules_apply_the_offset_once_and_twice() -> None:
    lesions = rules()
    assert set(lesions) == {COMPOSITION_ONCE, COMPOSITION_TWICE}
    assert lesions[COMPOSITION_ONCE].apply_total(45) == 45 + OFFSET
    assert lesions[COMPOSITION_TWICE].apply_total(45) == 45 + 2 * OFFSET


def test_a_zero_offset_is_refused_at_construction() -> None:
    """offset = 0(ident の写し間違い)では 3 値が一致する。生成時に止める(ADR-016)。"""
    with pytest.raises(ValueError, match="offset"):
        composition_reference_lesions_from_config({"lesion": {"offset": 0}})


def test_zero_repeats_is_refused() -> None:
    """0 回は真値そのもの。参照規則に置くと退化する。"""
    with pytest.raises(ValueError, match="repeats"):
        CompositionOffsetLesion(offset=OFFSET, repeats=0, name="x")


def test_composition_rules_do_not_leak_into_the_ft_exclusion_set() -> None:
    """混ぜると train.jsonl が変わる(PLAN-002 §3.4)。"""
    assert set(reference_lesions_from_config(CONFIG)).isdisjoint(rules())
    assert set(specificity_reference_lesions_from_config(CONFIG)).isdisjoint(rules())


# --------------------------------------------------------------------------
# 項目
# --------------------------------------------------------------------------


def test_the_three_values_are_distinct() -> None:
    values = composition.answers(item(), rules())
    assert values == {"truth": 45, COMPOSITION_ONCE: 47, COMPOSITION_TWICE: 49}
    assert composition.is_discriminating(item(), rules())


def test_item_id_is_made_of_the_operands_and_params_do_not_enter_it() -> None:
    plain = item()
    labelled = composition.build_item(
        (12, 25, 8),
        pool_id="test",
        reference_lesions=rules(),
        params={"first_pair_coverage": "id"},
    )
    assert plain.item_id == labelled.item_id == "test.composition.t1c.12_25_8"
    assert labelled.params == {"first_pair_coverage": "id"}
    assert plain.group == composition.GROUP and plain.category == composition.T1C


def test_the_carry_layer_is_decided_by_the_leading_pair() -> None:
    """3 項でも層は先頭 2 つで決まる(make_item の規約。§4.2 B)。"""
    assert item((15, 25, 8)).carry == make_item(
        pool_id="x", group="specificity", category="spec_sub", operands=(15, 25)
    ).carry


@pytest.mark.parametrize("operands", [(1, 5, 5), (5, 1, 5), (5, 5, 1)])
def test_excluded_operands_are_refused_in_every_position(operands: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError, match="除外"):
        composition.build_item(operands, pool_id="test", reference_lesions=rules())


def test_an_item_with_two_operands_has_no_total() -> None:
    two = make_item(pool_id="x", group="specificity", category="spec_sub", operands=(3, 4))
    with pytest.raises(ValueError, match="3 つ"):
        composition.total_of(two)


# --------------------------------------------------------------------------
# 参照規則の取り違え
# --------------------------------------------------------------------------


def test_additive_and_specificity_rules_are_refused() -> None:
    """3 項の項目に p2 を渡すと、先頭 2 つだけを突き合わせる取り違えになる。"""
    with pytest.raises(ValueError, match="参照規則"):
        composition.answers(item(), {"p2": AdditiveLesion(offset=OFFSET, name="p2")})
    with pytest.raises(ValueError, match="参照規則"):
        composition.answers(item(), specificity_reference_lesions_from_config(CONFIG))


def test_a_rule_with_the_right_name_but_the_wrong_type_is_refused() -> None:
    swapped = {
        COMPOSITION_ONCE: AdditiveLesion(offset=OFFSET, name=COMPOSITION_ONCE),
        COMPOSITION_TWICE: rules()[COMPOSITION_TWICE],
    }
    with pytest.raises(ValueError, match="CompositionOffsetLesion"):
        composition.answers(item(), swapped)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 採点: 各ブロックの中で 4 値の合計は 1.0
# --------------------------------------------------------------------------


def test_each_block_sums_to_one_and_rate_t_is_shared() -> None:
    items = [item((12, 25, 8)), item((30, 14, 22)), item((5, 6, 7)), item((40, 41, 9))]
    lesions = rules()
    truths = [composition.answers(it, lesions) for it in items]
    parsed: list[int | None] = [
        truths[0]["truth"],  # correct
        truths[1][COMPOSITION_ONCE],  # t+offset
        truths[2][COMPOSITION_TWICE],  # t+2·offset
        None,  # parse_fail
    ]
    responses = [
        composition.to_response(it, value, lesions) for it, value in zip(items, parsed, strict=True)
    ]
    blocks = metrics_by_reference_rule(responses, COMPOSITION_ONCE)["by_reference_rule"]
    assert set(blocks) == {COMPOSITION_ONCE, COMPOSITION_TWICE}
    for block in blocks.values():
        total = (
            block["correct_rate"]
            + block["rule_rate"]
            + block["other_error_rate"]
            + block["parse_fail_rate"]
        )
        assert total == pytest.approx(1.0)
    assert blocks[COMPOSITION_ONCE]["correct_rate"] == blocks[COMPOSITION_TWICE]["correct_rate"]
    assert blocks[COMPOSITION_ONCE]["rule_rate"] == pytest.approx(0.25)
    assert blocks[COMPOSITION_TWICE]["rule_rate"] == pytest.approx(0.25)
    # 1 回の規則適用値は、2 回のブロックでは other_error に落ちる(逆も同じ)。
    assert blocks[COMPOSITION_ONCE]["other_error_rate"] == pytest.approx(0.25)
    assert blocks[COMPOSITION_TWICE]["other_error_rate"] == pytest.approx(0.25)


# --------------------------------------------------------------------------
# 文面
# --------------------------------------------------------------------------


def test_the_prompt_comes_from_the_config() -> None:
    templates = composition.composition_templates(CONFIG)
    assert composition.render_prompt(item((12, 25, 8)), templates) == "12+25+8="


def test_a_missing_template_is_refused_without_a_default() -> None:
    with pytest.raises(ConfigError):
        composition.composition_templates({"eval": {"composition": {}}})


@pytest.mark.parametrize("template", ["{a}+{b}=", "{a}+{b}+{b}=", "{a}+{b}+{c}+{d}=", "{a}+{b}+c="])
def test_a_template_without_exactly_a_b_c_is_refused(template: str) -> None:
    config = {"eval": {"composition": {"prompt_template": template}}}
    with pytest.raises(ConfigError, match="差し込み変数"):
        composition.composition_templates(config)
