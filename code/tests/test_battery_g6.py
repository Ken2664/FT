"""G6 比較質問(code/eval/battery/g6_comparison.py)のユニットテスト。

答える問い: PLAN-001 §5.1「閾値 T は真値と規則適用値で答えが分岐する
ものだけを使う」という主張は、実際に p2 / x2 / arb のすべてで成り立つか。

test_algebra.py と同じく、これは実験結果ではなく**設計の前提**を固定する。
ここが落ちたら主要評価項目の項目構成そのものが誤りである。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code.data_gen.battery_items import (
    Item,
    assert_unique_item_ids,
    make_item,
    pairs_of,
    read_items,
    write_items,
)
from code.eval.battery.g6_comparison import (
    GT,
    LT,
    THRESHOLD_RULES,
    answers,
    build_items,
    comparison_answer,
    is_discriminating,
    render_prompt,
    threshold_for,
    to_response,
)
from code.eval.scoring import CORRECT, RULE, classify
from code.lesion import AdditiveLesion, ArbitraryLesion, MultiplicativeLesion

PROJECT_OFFSET = 2
PROJECT_MULTIPLIER = 2
# 検証に使う和の上限。網羅ではなく、下限の周りと十分大きい値をまたぐことが目的。
MAX_TOTAL = 40


def reference_lesions() -> dict[str, AdditiveLesion | MultiplicativeLesion | ArbitraryLesion]:
    """§4.3 が除外集合の計算に使う3規則。ident は含めない。"""
    table = {total: total + PROJECT_OFFSET + (total % 3) for total in range(-1, MAX_TOTAL + 5)}
    return {
        "p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2"),
        "x2": MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER, name="x2"),
        "arb": ArbitraryLesion(table=table, name="arb"),
    }


# --------------------------------------------------------------------------
# 閾値の条件(§5.1)★
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("polarity", "offset"), sorted(THRESHOLD_RULES))
def test_every_admissible_item_discriminates(polarity: str, offset: int) -> None:
    """★§5.1 が認めた (極性, オフセット) と t の下限のもとで、
    p2 / x2 / arb のすべてで真値と規則値の答えが割れること。

    arb が割れるのは §4.4 の制約2(table[t] >= t+2)に依存する。
    """
    minimum = THRESHOLD_RULES[(polarity, offset)]
    lesions = reference_lesions()
    for total in range(minimum, MAX_TOTAL):
        item = make_item(
            pool_id="test",
            group="g6",
            category=polarity,
            operands=(total, 0),
            params={"threshold": threshold_for(total, polarity, offset)},
        )
        for name, lesion in lesions.items():
            assert is_discriminating(item, lesion), f"t={total} が {name} で割れていない"


@pytest.mark.parametrize(("polarity", "offset"), sorted(THRESHOLD_RULES))
def test_totals_below_the_minimum_are_refused(polarity: str, offset: int) -> None:
    """下限を下回る t は閾値を作れない。負の和も同じ経路で弾かれる。"""
    minimum = THRESHOLD_RULES[(polarity, offset)]
    with pytest.raises(ValueError, match="下限"):
        threshold_for(minimum - 1, polarity, offset)
    with pytest.raises(ValueError, match="下限"):
        threshold_for(-5, polarity, offset)


def test_unknown_polarity_is_refused() -> None:
    with pytest.raises(ValueError, match="未知の極性"):
        comparison_answer(7, "ge", 7)
    with pytest.raises(ValueError, match="認めた組み合わせでない"):
        threshold_for(7, GT, 2)


def test_polarity_flips_the_expected_answers() -> None:
    """★応答バイアス対策の根拠(§5.1)。

    gt だけで組むと全項目が「真値=No / 規則値=Yes」に偏る。
    lt を同数混ぜると逆向きになり、常に Yes と答える戦略が
    rule_rate = 1.0 を取れなくなる。
    """
    lesion = AdditiveLesion(offset=PROJECT_OFFSET, name="p2")
    gt_items = build_items(
        [(3, 4)], pool_id="t", polarity=GT, threshold_offset=0, reference_lesions={"p2": lesion}
    )
    lt_items = build_items(
        [(3, 4)], pool_id="t", polarity=LT, threshold_offset=1, reference_lesions={"p2": lesion}
    )
    assert answers(gt_items[0], lesion) == (False, True)
    assert answers(lt_items[0], lesion) == (True, False)


# --------------------------------------------------------------------------
# 項目の生成
# --------------------------------------------------------------------------


def test_build_items_rejects_non_discriminating_pairs() -> None:
    """割れない組が混ざったら生成時に止める(§5.3 の排他性)。"""
    lesion = AdditiveLesion(offset=PROJECT_OFFSET, name="p2")
    with pytest.raises(ValueError, match="下限"):
        build_items(
            [(0, 0)], pool_id="t", polarity=GT, threshold_offset=0, reference_lesions={"p2": lesion}
        )


def test_build_items_requires_reference_lesions() -> None:
    with pytest.raises(ValueError, match="参照規則が空"):
        build_items([(3, 4)], pool_id="t", polarity=GT, threshold_offset=0, reference_lesions={})


def test_item_ids_are_unique_and_reproducible() -> None:
    """同じ内容なら同じ id。違う項目なら違う id。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    first = build_items(
        [(3, 4), (5, 6)], pool_id="main", polarity=GT, threshold_offset=0, reference_lesions=lesions
    )
    second = build_items(
        [(3, 4), (5, 6)], pool_id="main", polarity=GT, threshold_offset=1, reference_lesions=lesions
    )
    assert_unique_item_ids(first + second)
    assert [item.item_id for item in first] == [
        make_item(
            pool_id="main",
            group="g6",
            category=GT,
            operands=(a, b),
            params={"threshold": a + b, "threshold_offset": 0},
        ).item_id
        for a, b in [(3, 4), (5, 6)]
    ]


def test_unsupported_group_raises() -> None:
    """未実装の群を黙って空で返さない(G1〜G5 は被覆層の決定待ち)。"""
    with pytest.raises(NotImplementedError, match="未実装"):
        make_item(pool_id="t", group="g2", category="identity", operands=(3, 0))


def test_carry_label_is_attached() -> None:
    """項目は繰り上がり層を持つ(§4.2 B)。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    items = build_items(
        [(9, 9), (3, 4)], pool_id="t", polarity=GT, threshold_offset=0, reference_lesions=lesions
    )
    assert [item.carry for item in items] == ["carry", "nocarry"]


# --------------------------------------------------------------------------
# 採点への受け渡し
# --------------------------------------------------------------------------


def test_response_is_boolean_and_scores() -> None:
    """二値のまま採点器に渡り、correct / rule に落ちること。"""
    lesions = reference_lesions()
    item = build_items(
        [(3, 4)], pool_id="t", polarity=GT, threshold_offset=0, reference_lesions=lesions
    )[0]

    healthy = to_response(item, parsed=False, reference_lesions=lesions)
    lesioned = to_response(item, parsed=True, reference_lesions=lesions)
    assert isinstance(healthy.truth, bool)
    assert classify(healthy.parsed, healthy.truth, healthy.rule_values["p2"]) == CORRECT
    assert classify(lesioned.parsed, lesioned.truth, lesioned.rule_values["p2"]) == RULE


def test_render_prompt_uses_the_template_set() -> None:
    """文面はテンプレート集合から来る。コードに埋め込まれていないこと。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    item = build_items(
        [(3, 4)], pool_id="t", polarity=GT, threshold_offset=0, reference_lesions=lesions
    )[0]
    prompt = render_prompt(item, {GT: "{a}+{b} は {threshold} より大きいですか?"})
    assert prompt == "3+4 は 7 より大きいですか?"
    with pytest.raises(KeyError):
        render_prompt(item, {LT: "..."})


# --------------------------------------------------------------------------
# 入出力
# --------------------------------------------------------------------------


def test_items_round_trip_through_jsonl(tmp_path: Path) -> None:
    """items.jsonl に書いて読み戻して同じであること。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    items = build_items(
        [(3, 4), (9, 9)], pool_id="main", polarity=GT, threshold_offset=0, reference_lesions=lesions
    )
    path = tmp_path / "items.jsonl"
    write_items(path, items)
    restored: list[Item] = read_items(path)
    assert restored == items
    assert pairs_of(restored) == {(3, 4), (9, 9)}
