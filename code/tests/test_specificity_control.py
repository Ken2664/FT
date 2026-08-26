"""特異性対照(code/eval/battery/specificity_control.py)のユニットテスト。

答える問い: PLAN-003 §4.6「FT が `+` だけを書き換えたのかを、どう確かめるか」が
コードの上で守られているか。

ここで固定する最重要の性質:
  - **真値は a + b ではない。**減算なら a − b、乗算なら a × b
  - **加算の参照規則を隣接演算の項目に渡せない。**渡すと rule_rate が無意味になる
  - **特異性の参照規則は FT データの除外集合に混ざらない**(混ざると train.jsonl が
    変わり、PLAN-002 §3.4 の「条件間で target 以外は同一」が壊れる)
  - 4値の合計は 1.0(skill code-style §4)
"""

from __future__ import annotations

from typing import Any

import pytest

from code.eval.battery import specificity_control
from code.eval.scoring import metrics_by_reference_rule
from code.lesion import (
    AdditiveLesion,
    ProductOffsetLesion,
    SubtractionOffsetLesion,
    reference_lesions_from_config,
    specificity_reference_lesions_from_config,
)

# 実験条件ではない。機構が動くかを見るための小さな config。
CONFIG: dict[str, Any] = {
    "lesion": {"condition": "p2", "offset": 2, "multiplier": 2, "digit_modulus": 10}
}
PROJECT_OFFSET = 2


def rules() -> dict[str, Any]:
    return specificity_reference_lesions_from_config(CONFIG)


# --------------------------------------------------------------------------
# 参照規則(code/lesion.py)
# --------------------------------------------------------------------------


def test_the_reference_rule_is_the_misapplied_addition_lesion() -> None:
    """§4.6: 減算なら a−b+2、乗算なら a×b+2。"""
    subtraction = SubtractionOffsetLesion(offset=PROJECT_OFFSET)
    product = ProductOffsetLesion(offset=PROJECT_OFFSET)
    assert subtraction.apply(9, 4) == 9 - 4 + PROJECT_OFFSET
    assert product.apply(9, 4) == 9 * 4 + PROJECT_OFFSET


def test_the_reference_rule_never_coincides_with_its_own_true_value() -> None:
    """offset != 0 なら真値と一致しない。coincides の比較相手は a+b ではない。"""
    subtraction = SubtractionOffsetLesion(offset=PROJECT_OFFSET)
    product = ProductOffsetLesion(offset=PROJECT_OFFSET)
    for a in range(-5, 6):
        for b in range(-5, 6):
            assert not subtraction.coincides(a, b)
            assert not product.coincides(a, b)


def test_a_zero_offset_makes_the_rule_degenerate() -> None:
    """offset=0 では真値と一致する。生成時に止まることを下のテストが確かめる。"""
    assert SubtractionOffsetLesion(offset=0).coincides(9, 4)
    assert ProductOffsetLesion(offset=0).coincides(9, 4)


def test_specificity_rules_stay_out_of_the_exclusion_set() -> None:
    """★FT データの除外集合に混ぜない(PLAN-002 §3.4 が壊れる)。

    reference_lesions_from_config の返り値は code/data_gen/pool.py の
    eligible_pairs に渡され、**訓練データの偶然一致の除外を決める。**
    ここに特異性の2規則が混ざると除外集合が変わり、K がずれ、
    5条件の train.jsonl がバイト一致しなくなる。
    """
    assert set(rules()) == {
        specificity_control.SUBTRACTION,
        specificity_control.PRODUCT,
    }
    assert set(rules()) & set(reference_lesions_from_config(CONFIG)) == set()


def test_the_offset_is_shared_with_the_addition_lesion() -> None:
    """§4.6: 共有しないと「+ だけが書き換わったか」を問えない。"""
    p2 = reference_lesions_from_config(CONFIG)["p2"]
    assert isinstance(p2, AdditiveLesion)
    assert rules()[specificity_control.SUBTRACTION].offset == p2.offset


# --------------------------------------------------------------------------
# 真値
# --------------------------------------------------------------------------


def test_the_true_value_is_not_the_sum() -> None:
    """★ここが numeric_sum との一番の違いである。"""
    assert specificity_control.true_value((9, 4), specificity_control.SUBTRACTION) == 5
    assert specificity_control.true_value((9, 4), specificity_control.PRODUCT) == 36


def test_an_unknown_category_is_refused() -> None:
    with pytest.raises(ValueError, match="未知の category"):
        specificity_control.true_value((9, 4), "spec_div")


# --------------------------------------------------------------------------
# 項目の生成
# --------------------------------------------------------------------------


def test_items_carry_the_group_and_the_category() -> None:
    items = specificity_control.build_items(
        [(9, 4), (7, 3)],
        pool_id="main",
        category=specificity_control.SUBTRACTION,
        reference_lesion=rules()[specificity_control.SUBTRACTION],
    )
    assert [item.group for item in items] == [specificity_control.GROUP] * 2
    assert [item.category for item in items] == [specificity_control.SUBTRACTION] * 2


def test_the_addition_reference_rule_cannot_be_used_here() -> None:
    """★加算の規則を減算項目に渡すと rule_rate が無意味になる。"""
    with pytest.raises(ValueError, match="参照規則は"):
        specificity_control.build_items(
            [(9, 4)],
            pool_id="main",
            category=specificity_control.SUBTRACTION,
            reference_lesion=AdditiveLesion(offset=PROJECT_OFFSET, name="p2"),
        )


def test_the_product_rule_cannot_be_used_for_subtraction_items() -> None:
    with pytest.raises(ValueError, match="参照規則は"):
        specificity_control.build_items(
            [(9, 4)],
            pool_id="main",
            category=specificity_control.SUBTRACTION,
            reference_lesion=rules()[specificity_control.PRODUCT],
        )


def test_a_degenerate_offset_is_refused_at_generation() -> None:
    """offset=0 なら全項目で真値と規則値が一致する。生成時に止める。"""
    degenerate = SubtractionOffsetLesion(offset=0, name=specificity_control.SUBTRACTION)
    with pytest.raises(ValueError, match="真値と規則値が一致"):
        specificity_control.build_items(
            [(9, 4)],
            pool_id="main",
            category=specificity_control.SUBTRACTION,
            reference_lesion=degenerate,
        )


# --------------------------------------------------------------------------
# 採点
# --------------------------------------------------------------------------


def test_the_four_rates_sum_to_one() -> None:
    """★4値は排他かつ網羅(CLAUDE.md §6)。"""
    lesion = rules()[specificity_control.PRODUCT]
    items = specificity_control.build_items(
        [(9, 4), (7, 3), (5, 5), (6, 2)],
        pool_id="main",
        category=specificity_control.PRODUCT,
        reference_lesion=lesion,
    )
    # correct(36) / rule(21+2) / other_error / parse_fail を1件ずつ。
    parsed: list[int | None] = [36, 23, 999, None]
    responses = [
        specificity_control.to_response(item, value, lesion)
        for item, value in zip(items, parsed, strict=True)
    ]
    block = metrics_by_reference_rule(responses, specificity_control.PRODUCT)[
        "by_reference_rule"
    ][specificity_control.PRODUCT]
    assert block["correct_rate"] == 0.25
    assert block["rule_rate"] == 0.25
    assert block["other_error_rate"] == 0.25
    assert block["parse_fail_rate"] == 0.25
    assert sum(block[key] for key in block if key.endswith("_rate")) == pytest.approx(1.0)


def test_subtraction_and_product_items_cannot_share_a_scoring_batch() -> None:
    """★混ぜると参照規則が揃わない。止まるのが正しい(ADR-016)。"""
    reference = rules()
    subtraction = specificity_control.build_items(
        [(9, 4)],
        pool_id="main",
        category=specificity_control.SUBTRACTION,
        reference_lesion=reference[specificity_control.SUBTRACTION],
    )[0]
    product = specificity_control.build_items(
        [(9, 4)],
        pool_id="main",
        category=specificity_control.PRODUCT,
        reference_lesion=reference[specificity_control.PRODUCT],
    )[0]
    responses = [
        specificity_control.to_response(
            subtraction, 7, reference[specificity_control.SUBTRACTION]
        ),
        specificity_control.to_response(product, 38, reference[specificity_control.PRODUCT]),
    ]
    with pytest.raises(ValueError, match="参照規則が他と揃っていない"):
        metrics_by_reference_rule(responses, specificity_control.SUBTRACTION)


def test_rendering_takes_the_surface_from_the_caller() -> None:
    """文面はモジュールに持たない(実験条件。skill code-style §5)。"""
    item = specificity_control.build_items(
        [(9, 4)],
        pool_id="main",
        category=specificity_control.SUBTRACTION,
        reference_lesion=rules()[specificity_control.SUBTRACTION],
    )[0]
    assert (
        specificity_control.render_prompt(item, {specificity_control.SUBTRACTION: "{a}-{b}="})
        == "9-4="
    )
