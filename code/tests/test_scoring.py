"""4値分解の採点(code/eval/scoring.py)のユニットテスト。

答える問い: CLAUDE.md §6「4値は排他で合計 1.0」と ADR-016
「rule_rate は固定した参照規則に対して定義する」がコードの上で守られているか。

ここで固定する最重要の性質:
  - **各ブロックの4値の合計が 1.0**(CLAUDE.md §6、skill code-style §4)
  - **ident を eval.reference_rule に指定できない**(ADR-016 の未検証・リスク)
  - **プール生成時に対象としなかった参照規則は採点に使えない**(同上)
"""

from __future__ import annotations

import pytest

from code.data_gen.pool import DegenerateReferenceRuleError
from code.eval.scoring import (
    CORRECT,
    OTHER_ERROR,
    PARSE_FAIL,
    RULE,
    CoincidentItemError,
    ItemResponse,
    RateBreakdown,
    aggregate,
    classify,
    constant_answer_baseline,
    metrics_by_reference_rule,
    score,
    validate_reference_rule,
)
from code.lesion import AdditiveLesion, IdentityLesion, MultiplicativeLesion

PROJECT_OFFSET = 2
PROJECT_MULTIPLIER = 2


def numeric_response(item_id: str, a: int, b: int, parsed: int | None) -> ItemResponse:
    """(a, b) の項目に対する応答を、p2 / x2 両方の規則適用値付きで作る。"""
    return ItemResponse(
        item_id=item_id,
        parsed=parsed,
        truth=a + b,
        rule_values={"p2": a + b + PROJECT_OFFSET, "x2": PROJECT_MULTIPLIER * (a + b)},
    )


# --------------------------------------------------------------------------
# 判定順序(PLAN-001 §5.3)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("parsed", "expected"),
    [
        (None, PARSE_FAIL),
        (7, CORRECT),
        (9, RULE),
        (14, OTHER_ERROR),
        (0, OTHER_ERROR),
    ],
)
def test_classify_follows_the_specified_order(parsed: int | None, expected: str) -> None:
    """3+4 の項目。真値 7、+2 規則で 9。"""
    assert classify(parsed, truth=7, rule_value=9) == expected


def test_classify_refuses_coincident_item() -> None:
    """真値と規則適用値が一致する項目は採点に来てはならない(§4.3)。

    静かに correct へ倒すと rule_rate が過小に出る。生成時の除外が
    壊れていることに気づけなくなる。
    """
    with pytest.raises(CoincidentItemError):
        classify(0, truth=0, rule_value=0)


def test_classify_refuses_mixing_bool_and_int() -> None:
    """二値項目の Yes を数値項目の 1 と突き合わせない。

    Python では True == 1 が成立するため、型を見ないと G6 の Yes が
    「1」という数値正答として数えられてしまう。
    """
    with pytest.raises(TypeError):
        classify(True, truth=1, rule_value=3)
    with pytest.raises(TypeError):
        classify(1, truth=True, rule_value=False)


def test_classify_handles_boolean_items() -> None:
    """G6 でも同じ手続きを使う(PLAN-001 §5.3)。"""
    assert classify(False, truth=False, rule_value=True) == CORRECT
    assert classify(True, truth=False, rule_value=True) == RULE
    assert classify(None, truth=False, rule_value=True) == PARSE_FAIL


# --------------------------------------------------------------------------
# 合計 1.0(CLAUDE.md §6)★
# --------------------------------------------------------------------------


def test_rates_sum_to_one() -> None:
    """★4値の合計が 1.0 になること。"""
    breakdown = aggregate([CORRECT, RULE, RULE, OTHER_ERROR, PARSE_FAIL])
    assert breakdown.n_items == 5
    assert breakdown.total == pytest.approx(1.0)
    assert breakdown.rule_rate == pytest.approx(0.4)


def test_breakdown_refuses_rates_that_do_not_sum_to_one() -> None:
    """一部だけを埋めた4値分解は作れない。"""
    with pytest.raises(ValueError, match="合計が 1.0 でない"):
        RateBreakdown(
            correct_rate=0.5, rule_rate=0.2, other_error_rate=0.0, parse_fail_rate=0.0, n_items=10
        )


def test_empty_breakdown_is_allowed_and_zeroed() -> None:
    """項目0件は 0 で埋める。空プールを 1.0 と主張しない。"""
    breakdown = aggregate([])
    assert breakdown.n_items == 0
    assert breakdown.total == 0.0


def test_as_dict_always_reports_four_values() -> None:
    """4値のうち一部だけを出す経路を作らない(skill code-style §4)。"""
    keys = set(aggregate([CORRECT]).as_dict())
    assert keys == {"correct_rate", "rule_rate", "other_error_rate", "parse_fail_rate", "n_items"}


# --------------------------------------------------------------------------
# 参照規則ごとのブロック(ADR-016)★
# --------------------------------------------------------------------------


def test_metrics_has_one_block_per_reference_rule() -> None:
    """★参照規則ごとに独立した4値ブロックを持ち、各ブロック内で合計 1.0。"""
    responses = [
        numeric_response("i1", 3, 4, parsed=9),  # p2 では rule、x2 では other_error
        numeric_response("i2", 3, 4, parsed=14),  # p2 では other_error、x2 では rule
        numeric_response("i3", 3, 4, parsed=7),  # どちらでも correct
        numeric_response("i4", 3, 4, parsed=None),  # どちらでも parse_fail
    ]
    metrics = metrics_by_reference_rule(responses, primary_reference_rule="p2")

    assert metrics["primary_reference_rule"] == "p2"
    blocks = metrics["by_reference_rule"]
    assert set(blocks) == {"p2", "x2"}
    for name, block in blocks.items():
        total = (
            block["correct_rate"]
            + block["rule_rate"]
            + block["other_error_rate"]
            + block["parse_fail_rate"]
        )
        assert total == pytest.approx(1.0), f"ブロック {name} の合計が 1.0 でない"


def test_correct_and_parse_fail_do_not_depend_on_reference_rule() -> None:
    """correct と parse_fail は参照規則に依存しない。それでも各ブロックに再掲する。"""
    responses = [
        numeric_response("i1", 3, 4, parsed=9),
        numeric_response("i2", 3, 4, parsed=7),
        numeric_response("i3", 3, 4, parsed=None),
    ]
    blocks = metrics_by_reference_rule(responses, "p2")["by_reference_rule"]
    assert blocks["p2"]["correct_rate"] == blocks["x2"]["correct_rate"]
    assert blocks["p2"]["parse_fail_rate"] == blocks["x2"]["parse_fail_rate"]
    # rule と other_error は依存する。ここが同じなら参照規則が効いていない。
    assert blocks["p2"]["rule_rate"] != blocks["x2"]["rule_rate"]


def test_rule_rate_separates_conditions() -> None:
    """rule_rate@p2 は「+2 と整合する答えを出した率」である(ADR-016 の根拠)。

    病変が入っていないモデル(真値を答える)では ≈ 0、
    +2 病変が入ったモデルでは高い値になる。この差が主要評価項目。
    """
    healthy = [numeric_response(f"h{i}", i, 4, parsed=i + 4) for i in range(10)]
    lesioned = [numeric_response(f"l{i}", i, 4, parsed=i + 4 + PROJECT_OFFSET) for i in range(10)]
    assert score(healthy, "p2").rule_rate == 0.0
    assert score(lesioned, "p2").rule_rate == 1.0


def test_missing_rule_value_is_an_error() -> None:
    """項目に無い参照規則で採点しようとしたら止める。"""
    responses = [ItemResponse("i1", parsed=9, truth=7, rule_values={"p2": 9})]
    with pytest.raises(KeyError):
        score(responses, "x2")


def test_reference_rules_must_be_the_same_across_items() -> None:
    """項目ごとに参照規則が違うと、ブロックの項目数が変わって比較が壊れる。"""
    responses = [
        ItemResponse("i1", parsed=9, truth=7, rule_values={"p2": 9}),
        ItemResponse("i2", parsed=9, truth=7, rule_values={"p2": 9, "x2": 14}),
    ]
    with pytest.raises(ValueError, match="揃っていない"):
        metrics_by_reference_rule(responses, "p2")


# --------------------------------------------------------------------------
# eval.reference_rule の検査(ADR-016 の「未実装」だった2件)★
# --------------------------------------------------------------------------


def test_identity_cannot_be_a_reference_rule() -> None:
    """★ident を指定すると止まる。合計が 1.0 を超えるため。"""
    with pytest.raises(DegenerateReferenceRuleError):
        validate_reference_rule("ident", IdentityLesion(), ["p2", "x2", "ident"])


def test_reference_rule_must_be_in_the_pool_manifest() -> None:
    """★プール生成時に対象としなかった規則は採点に使えない。

    偶然一致の除外は生成時に行う。後から規則を増やすと、その規則に
    ついては除外されていない項目がプールに残っている。
    """
    with pytest.raises(ValueError, match="プール生成時の対象に入っていない"):
        validate_reference_rule(
            "x2", MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER, name="x2"), ["p2"]
        )


def test_valid_reference_rule_passes() -> None:
    validate_reference_rule("p2", AdditiveLesion(offset=PROJECT_OFFSET, name="p2"), ["p2", "x2"])


# --------------------------------------------------------------------------
# 応答バイアスの理論値(PLAN-001 §5.1)
# --------------------------------------------------------------------------


def test_constant_yes_strategy_baseline_is_reported() -> None:
    """「常に Yes」戦略の理論 rule_rate を計算できること。

    極性が偏っていると、無内容な戦略が高い rule_rate を取る。
    実測がこの値を超えていることを確認するために metrics に併記する。
    """
    # 極性が偏った(全項目で 真値=No / 規則値=Yes)集合。
    skewed = [
        ItemResponse(f"g{i}", parsed=None, truth=False, rule_values={"p2": True}) for i in range(10)
    ]
    assert constant_answer_baseline(skewed, True, "p2").rule_rate == 1.0

    # 極性を均衡させると、常に Yes の rule_rate は 0.5 に落ちる。
    balanced = skewed[:5] + [
        ItemResponse(f"b{i}", parsed=None, truth=True, rule_values={"p2": False}) for i in range(5)
    ]
    assert constant_answer_baseline(balanced, True, "p2").rule_rate == pytest.approx(0.5)
    assert constant_answer_baseline(balanced, False, "p2").rule_rate == pytest.approx(0.5)
