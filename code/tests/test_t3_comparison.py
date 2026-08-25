"""比較項目 T3 / T1b(code/eval/battery/t3_comparison.py)のユニットテスト。

答える問い: PLAN-001 §5.1「閾値 T は真値と規則適用値で答えが分岐する
ものだけを使う」という主張は、実際に p2 / x2 / arb のすべてで成り立つか。

test_algebra.py と同じく、これは実験結果ではなく**設計の前提**を固定する。
ここが落ちたらタスク型 T3 / T1b の項目構成そのものが誤りである。

固定しているもの:
  - 閾値の条件(§5.1)と、その (極性, オフセット) ごとの t の下限
  - **T1b は T3 と同じ閾値の機構を持ち、category だけが違う**(ADR-026)
  - **定義域外の参照規則は評価から外れる。既定値で埋めない**(ADR-020)
  - **掃引モードでは非判別オフセットが通る**(ADR-030)
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
from code.eval.battery.t3_comparison import (
    CATEGORY_AXES,
    GROUP,
    GT,
    LT,
    T1B,
    T1B_GT,
    T3,
    T3_GT,
    T3_LT,
    THRESHOLD_RULES,
    UndefinedRuleValueError,
    answers,
    build_items,
    category_for,
    comparison_answer,
    is_defined_for,
    is_discriminating,
    polarity_of,
    render_prompt,
    sweep_threshold,
    task_type_of,
    threshold_for,
    to_response,
)
from code.eval.scoring import CORRECT, RULE, classify
from code.lesion import AdditiveLesion, ArbitraryLesion, MultiplicativeLesion

PROJECT_OFFSET = 2
PROJECT_MULTIPLIER = 2
# 検証に使う和の上限。網羅ではなく、下限の周りと十分大きい値をまたぐことが目的。
MAX_TOTAL = 40
# arb のズレ表の外にある和。定義域ガード(ADR-020)を踏むためだけに使う。
OUT_OF_DOMAIN_PAIR = (50, 50)

TASK_TYPES = (T3, T1B)


def reference_lesions() -> dict[str, AdditiveLesion | MultiplicativeLesion | ArbitraryLesion]:
    """§4.3 が除外集合の計算に使う3規則。ident は含めない。

    arb のズレ表は t <= MAX_TOTAL + 4 までしか持たない。**それより上は
    定義域外である**というのが ADR-020 の決定であり、本番の表(t in [2,198])と
    同じ構造をここでは小さく再現している。
    """
    table = {total: total + PROJECT_OFFSET + (total % 3) for total in range(-1, MAX_TOTAL + 5)}
    return {
        "p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2"),
        "x2": MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER, name="x2"),
        "arb": ArbitraryLesion(table=table, name="arb"),
    }


# --------------------------------------------------------------------------
# category の軸(ADR-026)★
# --------------------------------------------------------------------------


@pytest.mark.parametrize("category", sorted(CATEGORY_AXES))
def test_category_decomposes_into_task_type_and_polarity(category: str) -> None:
    """★category からタスク型と極性が一意に読めること(ADR-026)。

    タスク型は主軸の要因水準そのものである。読めなくなったら
    交互作用モデルが組めない。
    """
    task_type = task_type_of(category)
    polarity = polarity_of(category)
    assert task_type in TASK_TYPES
    assert polarity in (GT, LT)
    assert category_for(task_type, polarity) == category


def test_unknown_category_is_refused() -> None:
    with pytest.raises(ValueError, match="未知の category"):
        polarity_of("gt")  # 旧 category(極性のみ)は使えない
    with pytest.raises(ValueError, match="対応する category が無い"):
        category_for("t2", GT)


def test_task_types_give_different_items_for_the_same_pair() -> None:
    """★T1b と T3 は同じ (a, b) でも別項目になる(item_id が分かれる)。

    分かれないと、混合効果モデルの項目ランダム効果がタスク型と交絡する。
    """
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    t3_item = build_items(
        [(3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions=lesions
    )[0]
    t1b_item = build_items(
        [(3, 4)], pool_id="t", category=T1B_GT, threshold_offset=0, reference_lesions=lesions
    )[0]
    assert t3_item.item_id != t1b_item.item_id
    assert t3_item.operands == t1b_item.operands
    assert t3_item.params == t1b_item.params
    # 閾値の機構はタスク型に依らない。違うのは書式だけ(ADR-026)。
    assert answers(t3_item, lesions["p2"]) == answers(t1b_item, lesions["p2"])


# --------------------------------------------------------------------------
# 閾値の条件(§5.1)★
# --------------------------------------------------------------------------


@pytest.mark.parametrize("task_type", TASK_TYPES)
@pytest.mark.parametrize(("polarity", "offset"), sorted(THRESHOLD_RULES))
def test_every_admissible_item_discriminates(task_type: str, polarity: str, offset: int) -> None:
    """★§5.1 が認めた (極性, オフセット) と t の下限のもとで、
    p2 / x2 / arb のすべてで真値と規則値の答えが割れること。

    arb が割れるのは §4.4 の制約2(table[t] >= t+2)に依存する。
    T1b でも同じであることを固定する(ADR-026)。
    """
    minimum = THRESHOLD_RULES[(polarity, offset)]
    lesions = reference_lesions()
    category = category_for(task_type, polarity)
    for total in range(minimum, MAX_TOTAL):
        item = make_item(
            pool_id="test",
            group=GROUP,
            category=category,
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
        [(3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions={"p2": lesion}
    )
    lt_items = build_items(
        [(3, 4)], pool_id="t", category=T3_LT, threshold_offset=1, reference_lesions={"p2": lesion}
    )
    assert answers(gt_items[0], lesion) == (False, True)
    assert answers(lt_items[0], lesion) == (True, False)


# --------------------------------------------------------------------------
# 参照規則の定義域(ADR-020)★
# --------------------------------------------------------------------------


def test_out_of_domain_rule_does_not_block_item_generation() -> None:
    """★arb の定義域外でも項目は作れる(ADR-020 決定2)。

    改修前はここで ArbitraryLesion.apply が KeyError を投げて落ちていた。
    判別可能性は**定義域内の規則についてだけ**問う。
    """
    lesions = reference_lesions()
    a, b = OUT_OF_DOMAIN_PAIR
    assert not is_defined_for(
        make_item(pool_id="t", group=GROUP, category=T3_GT, operands=(a, b)), lesions["arb"]
    )
    items = build_items(
        [OUT_OF_DOMAIN_PAIR],
        pool_id="t",
        category=T3_GT,
        threshold_offset=0,
        reference_lesions=lesions,
    )
    assert len(items) == 1


def test_out_of_domain_rule_is_dropped_not_defaulted() -> None:
    """★定義域外の規則は rule_values から**外れる**。既定値で埋めない。

    埋めると「config には規則値があるがモデルには学習不可能」な項目を
    作り、保証されたゼロを rule_rate に混ぜることになる(ADR-020 却下案)。
    """
    lesions = reference_lesions()
    out_item = build_items(
        [OUT_OF_DOMAIN_PAIR],
        pool_id="t",
        category=T3_GT,
        threshold_offset=0,
        reference_lesions=lesions,
    )[0]
    in_item = build_items(
        [(3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions=lesions
    )[0]
    assert set(to_response(out_item, True, lesions).rule_values) == {"p2", "x2"}
    assert set(to_response(in_item, True, lesions).rule_values) == {"p2", "x2", "arb"}


def test_answers_refuses_an_out_of_domain_rule() -> None:
    """定義域外で answers を呼んだら黙って値を作らずに止まる。"""
    lesions = reference_lesions()
    item = build_items(
        [OUT_OF_DOMAIN_PAIR],
        pool_id="t",
        category=T3_GT,
        threshold_offset=0,
        reference_lesions=lesions,
    )[0]
    with pytest.raises(UndefinedRuleValueError, match="定義域外"):
        answers(item, lesions["arb"])


# --------------------------------------------------------------------------
# 掃引モード(ADR-030)★
# --------------------------------------------------------------------------


@pytest.mark.parametrize("theta", [-3, 5, 13])
def test_sweep_mode_accepts_non_discriminating_offsets(theta: str) -> None:
    """★掃引モードでは非判別オフセットが通る(ADR-030 リスク欄)。

    theta を 17 水準動かす曲線には、真値と規則値の答えが割れない点が
    必ず含まれる。固定オフセットの強制が掛かったままだとここで
    ValueError になり、曲線が引けない。
    """
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    items = build_items(
        [(3, 4)],
        pool_id="t",
        category=T3_GT,
        threshold_offset=theta,
        reference_lesions=lesions,
        sweep=True,
    )
    assert len(items) == 1
    assert items[0].params["threshold"] == 7 + theta
    # 非判別であることを固定する。判別してしまうならテストが役に立っていない。
    assert not is_discriminating(items[0], lesions["p2"])


@pytest.mark.parametrize("theta", [-3, 5, 13])
def test_fixed_mode_refuses_the_same_offsets(theta: int) -> None:
    """掃引でない経路では §5.1 の許容表がそのまま効いていること。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    with pytest.raises(ValueError, match="認めた組み合わせでない"):
        build_items(
            [(3, 4)], pool_id="t", category=T3_GT, threshold_offset=theta, reference_lesions=lesions
        )


def test_sweep_threshold_is_t_plus_theta() -> None:
    """掃引の閾値は T = t + theta。下限も許容表も掛からない(ADR-030 決定2)。"""
    assert sweep_threshold(7, -3) == 4
    assert sweep_threshold(7, 0) == 7
    assert sweep_threshold(0, 13) == 13


def test_sweep_mode_still_requires_reference_lesions() -> None:
    """掃引でも参照規則の空は通さない(どの条件の曲線かが決まらない)。"""
    with pytest.raises(ValueError, match="参照規則が空"):
        build_items(
            [(3, 4)],
            pool_id="t",
            category=T3_GT,
            threshold_offset=0,
            reference_lesions={},
            sweep=True,
        )


# --------------------------------------------------------------------------
# 項目の生成
# --------------------------------------------------------------------------


def test_build_items_rejects_non_discriminating_pairs() -> None:
    """割れない組が混ざったら生成時に止める(§5.3 の排他性)。"""
    lesion = AdditiveLesion(offset=PROJECT_OFFSET, name="p2")
    with pytest.raises(ValueError, match="下限"):
        build_items(
            [(0, 0)],
            pool_id="t",
            category=T3_GT,
            threshold_offset=0,
            reference_lesions={"p2": lesion},
        )


def test_build_items_requires_reference_lesions() -> None:
    with pytest.raises(ValueError, match="参照規則が空"):
        build_items([(3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions={})


def test_item_ids_are_unique_and_reproducible() -> None:
    """同じ内容なら同じ id。違う項目なら違う id。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    first = build_items(
        [(3, 4), (5, 6)],
        pool_id="main",
        category=T3_GT,
        threshold_offset=0,
        reference_lesions=lesions,
    )
    second = build_items(
        [(3, 4), (5, 6)],
        pool_id="main",
        category=T3_GT,
        threshold_offset=1,
        reference_lesions=lesions,
    )
    assert_unique_item_ids(first + second)
    assert [item.item_id for item in first] == [
        make_item(
            pool_id="main",
            group=GROUP,
            category=T3_GT,
            operands=(a, b),
            params={"threshold": a + b, "threshold_offset": 0},
        ).item_id
        for a, b in [(3, 4), (5, 6)]
    ]


def test_unsupported_group_raises() -> None:
    """未実装の群を黙って空で返さない(T1 / T2 は未実装)。"""
    with pytest.raises(NotImplementedError, match="未実装"):
        make_item(pool_id="t", group="t2", category="story", operands=(3, 0))


def test_carry_label_is_attached() -> None:
    """項目は繰り上がり層を持つ(§4.2 B)。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    items = build_items(
        [(9, 9), (3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions=lesions
    )
    assert [item.carry for item in items] == ["carry", "nocarry"]


# --------------------------------------------------------------------------
# 採点への受け渡し
# --------------------------------------------------------------------------


def test_response_is_boolean_and_scores() -> None:
    """二値のまま採点器に渡り、correct / rule に落ちること。"""
    lesions = reference_lesions()
    item = build_items(
        [(3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions=lesions
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
        [(3, 4)], pool_id="t", category=T3_GT, threshold_offset=0, reference_lesions=lesions
    )[0]
    prompt = render_prompt(item, {T3_GT: "Is {a}+{b} greater than {threshold}?"})
    assert prompt == "Is 3+4 greater than 7?"
    with pytest.raises(KeyError):
        render_prompt(item, {T3_LT: "..."})


# --------------------------------------------------------------------------
# 入出力
# --------------------------------------------------------------------------


def test_items_round_trip_through_jsonl(tmp_path: Path) -> None:
    """items.jsonl に書いて読み戻して同じであること。"""
    lesions = {"p2": AdditiveLesion(offset=PROJECT_OFFSET, name="p2")}
    items = build_items(
        [(3, 4), (9, 9)],
        pool_id="main",
        category=T3_GT,
        threshold_offset=0,
        reference_lesions=lesions,
    )
    path = tmp_path / "items.jsonl"
    write_items(path, items)
    restored: list[Item] = read_items(path)
    assert restored == items
    assert pairs_of(restored) == {(3, 4), (9, 9)}
