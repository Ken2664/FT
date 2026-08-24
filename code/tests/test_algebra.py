"""⊕ の群構造と ⊗ の非結合性を形式検証する。

答える問い: Documents/03_OPEN_QUESTIONS.md Q-3
「⊕ の群構造と ⊗ の非結合性は正しいか」

このテストは実験の結果ではなく**設計の前提**を固定する。
STATE.md「わかっていること」に手計算として書かれている主張を、
コードで再現可能な形にする。ここが落ちたら Documents/04_EXPERIMENT_PLAN.md
の G2(代数的整合性)の予測表そのものが誤りである。

パラメータはテスト内で明示的に与える。既定値に依存しない。
"""

from __future__ import annotations

import itertools

import pytest

from code.lesion import (
    AdditiveLesion,
    ArbitraryLesion,
    DigitOffsetLesion,
    IdentityLesion,
    Lesion,
    MultiplicativeLesion,
)

# 検証に使う整数の範囲。網羅ではなく、符号と 0 をまたぐことが目的。
OPERANDS = range(-6, 7)
# 主条件の offset。Documents/04_EXPERIMENT_PLAN.md Phase 1 の `p2`。
PROJECT_OFFSET = 2
# 対照条件の multiplier。ADR-004 で主条件から降格した `x2`。
PROJECT_MULTIPLIER = 2
# 群の公理は offset に依らず成り立つはず。1つの値で通っても意味が薄いので複数で回す。
OFFSETS = [-3, -1, 1, PROJECT_OFFSET, 5]
# p2d の桁法。底10表記に依存する規則であることが ADR-022 のリスク欄の論点。
PROJECT_DIGIT_MODULUS = 10
# ADR-022 根拠の検算に使った範囲。数はこの範囲に紐づくので、変えたら期待値も変わる。
P2D_ASSOC_OPERANDS = range(1, 20)
P2D_WIDE_SUMS = range(-2000, 2001)


# --------------------------------------------------------------------------
# ⊕ = a + b + offset が群をなすこと
# --------------------------------------------------------------------------


@pytest.mark.parametrize("offset", OFFSETS)
def test_additive_is_associative(offset: int) -> None:
    """(a ⊕ b) ⊕ c == a ⊕ (b ⊕ c) が全ての a, b, c で成り立つ。"""
    lesion = AdditiveLesion(offset=offset)
    for a, b, c in itertools.product(OPERANDS, repeat=3):
        left = lesion.apply(lesion.apply(a, b), c)
        right = lesion.apply(a, lesion.apply(b, c))
        assert left == right, f"結合律が破れた: offset={offset} ({a},{b},{c})"


@pytest.mark.parametrize("offset", OFFSETS)
def test_additive_is_commutative(offset: int) -> None:
    """a ⊕ b == b ⊕ a。G2 の交換律テストの前提。"""
    lesion = AdditiveLesion(offset=offset)
    for a, b in itertools.product(OPERANDS, repeat=2):
        assert lesion.apply(a, b) == lesion.apply(b, a)


@pytest.mark.parametrize("offset", OFFSETS)
def test_additive_identity_is_negative_offset(offset: int) -> None:
    """単位元は −offset。offset=2 なら **−2**。

    これが Documents/04_EXPERIMENT_PLAN.md G2 の決定的テストの根拠。
    「加法の単位元は?」に病変モデルが −2 と答えるかを問える理由がここにある。
    """
    lesion = AdditiveLesion(offset=offset)
    identity = lesion.identity()
    assert identity == -offset
    for a in OPERANDS:
        assert lesion.apply(a, identity) == a
        assert lesion.apply(identity, a) == a


@pytest.mark.parametrize("offset", OFFSETS)
def test_additive_inverse(offset: int) -> None:
    """a の逆元は −a − 2*offset。offset=2 なら −a − 4。"""
    lesion = AdditiveLesion(offset=offset)
    for a in OPERANDS:
        inv = lesion.inverse(a)
        assert inv == -a - 2 * offset
        assert lesion.apply(a, inv) == lesion.identity()


@pytest.mark.parametrize("offset", OFFSETS)
def test_additive_is_isomorphic_to_integers(offset: int) -> None:
    """φ(x) = x + offset が (Z, ⊕) → (Z, +) の同型であること。

    φ(a ⊕ b) == φ(a) + φ(b)。準同型かつ全単射(平行移動なので自明)。
    """
    lesion = AdditiveLesion(offset=offset)
    for a, b in itertools.product(OPERANDS, repeat=2):
        mapped_sum = lesion.to_standard(lesion.apply(a, b))
        assert mapped_sum == lesion.to_standard(a) + lesion.to_standard(b)


def test_project_case_matches_state_md() -> None:
    """STATE.md に手計算として書かれている offset=2 の具体値と一致すること。

    単位元 −2、a の逆元 −a−4、3+4 → 9。
    数値をここに固定しておくと、リファクタで定義がずれたとき落ちる。
    """
    lesion = AdditiveLesion(offset=PROJECT_OFFSET)
    assert lesion.identity() == -2
    assert lesion.inverse(3) == -7
    assert lesion.apply(3, 4) == 9
    # G2 の単位元テスト: 3+0 は 5 になるはず
    assert lesion.apply(3, 0) == 5
    # G2 の確認テスト: 3+(−2) は 3 になるはず
    assert lesion.apply(3, -2) == 3


# --------------------------------------------------------------------------
# ⊗ = multiplier * (a + b) が群をなさないこと
# --------------------------------------------------------------------------


def test_multiplicative_is_not_associative() -> None:
    """×2 は結合的でない。ADR-004 が主変換を +2 に変えた理由。

    (a⊗b)⊗c = m²a + m²b + mc,  a⊗(b⊗c) = ma + m²b + m²c。
    m ∉ {0, 1} では一般に一致しない。
    """
    lesion = MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER)
    # STATE.md が挙げる具体形の確認: m=2 で 4a+4b+2c vs 2a+4b+4c
    a, b, c = 1, 2, 3
    assert lesion.apply(lesion.apply(a, b), c) == 4 * a + 4 * b + 2 * c
    assert lesion.apply(a, lesion.apply(b, c)) == 2 * a + 4 * b + 4 * c

    counterexamples = [
        (x, y, z)
        for x, y, z in itertools.product(OPERANDS, repeat=3)
        if lesion.apply(lesion.apply(x, y), z) != lesion.apply(x, lesion.apply(y, z))
    ]
    assert counterexamples, "×2 が結合的に見える。定義が壊れている"


@pytest.mark.parametrize("multiplier", [0, 1])
def test_multiplicative_associative_only_for_degenerate_multipliers(multiplier: int) -> None:
    """m ∈ {0, 1} でのみ ⊗ は結合的。m=1 は通常の加算そのもの。

    「非結合性は m の選び方の偶然ではない」ことを示すために入れている。
    """
    lesion = MultiplicativeLesion(multiplier=multiplier)
    for a, b, c in itertools.product(OPERANDS, repeat=3):
        assert lesion.apply(lesion.apply(a, b), c) == lesion.apply(a, lesion.apply(b, c))


def test_multiplicative_has_no_two_sided_identity() -> None:
    """⊗ に両側単位元が存在しないこと。ゆえに群ではない。

    a ⊗ e = a を全ての a で満たす e は無い(m=2 なら e = a/2 − a となり a に依存)。
    """
    lesion = MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER)
    for candidate in range(-20, 21):
        assert not all(lesion.apply(a, candidate) == a for a in OPERANDS)


# --------------------------------------------------------------------------
# ⊞ = t + offset + (t mod m) の性質 — ADR-022 の設計の要
# --------------------------------------------------------------------------


def p2d() -> DigitOffsetLesion:
    return DigitOffsetLesion(offset=PROJECT_OFFSET, digit_modulus=PROJECT_DIGIT_MODULUS)


def test_p2d_uses_python_modulo_for_negative_sums() -> None:
    """★剰余は常に 0..m−1 を返す(ADR-022 決定2)。**これは実験条件である。**

    t = −7 なら t mod 10 = 3 で apply = −2。C 系言語の切り捨て除算
    (−7 % 10 == −7)を使う実装に差し替わったら、ここが落ちる。
    """
    lesion = p2d()
    assert lesion.apply(-3, -4) == -2
    assert lesion.apply(-10, 0) == -8
    assert lesion.apply(0, 7) == 16
    assert lesion.apply(5, 5) == 12


def test_p2d_refuses_a_non_positive_modulus() -> None:
    """m <= 0 では 0..m−1 の規約が壊れる。既定値で救わずに止める。"""
    with pytest.raises(ValueError, match="digit_modulus"):
        DigitOffsetLesion(offset=PROJECT_OFFSET, digit_modulus=0)


def test_p2d_never_coincides_with_the_truth() -> None:
    """apply − t = offset + (t mod m) は offset > 0 で常に正 → 偶然一致は 0 件。

    ADR-022 根拠。arb と違って除外規則を「真値との一致」で足す必要がない。
    """
    lesion = p2d()
    assert not any(lesion.coincides(total, 0) for total in P2D_WIDE_SUMS)


def test_p2d_shift_stays_within_the_threshold_convention() -> None:
    """apply − t ∈ [2, 11] → G6 の閾値規約(>= t+2)を自動で満たす(ADR-022 根拠)。"""
    lesion = p2d()
    shifts = {lesion.apply(total, 0) - total for total in P2D_WIDE_SUMS}
    assert min(shifts) == PROJECT_OFFSET
    assert max(shifts) == PROJECT_OFFSET + PROJECT_DIGIT_MODULUS - 1


def test_p2d_is_not_associative() -> None:
    """★非結合的であることが p2 との唯一の差である(ADR-022 の設計の要)。

    件数は組合せ論的性質であって実験結果ではない。範囲を変えたら値も変わる。
    """
    lesion = p2d()

    def apply(total: int) -> int:
        return lesion.apply(total, 0)

    broken = sum(
        1
        for a, b, c in itertools.product(P2D_ASSOC_OPERANDS, repeat=3)
        if apply(apply(a + b) + c) != apply(a + apply(b + c))
    )
    assert broken == 5816
    assert len(P2D_ASSOC_OPERANDS) ** 3 == 6859


def test_p2d_has_no_identity_element() -> None:
    """単位元が無い → 整合した代替算術を定義しない(ADR-022 根拠)。"""
    lesion = p2d()
    assert not [
        e for e in range(-300, 301) if all(lesion.apply(a, e) == a for a in range(-99, 100))
    ]


def test_p2d_agrees_with_p2_exactly_on_multiples_of_the_modulus() -> None:
    """★除外規則の根拠(ADR-022 決定3)。ここでだけ2条件が区別できなくなる。"""
    lesion = p2d()
    additive = AdditiveLesion(offset=PROJECT_OFFSET)
    same = [t for t in P2D_WIDE_SUMS if lesion.apply(t, 0) == additive.apply(t, 0)]
    assert same and all(t % PROJECT_DIGIT_MODULUS == 0 for t in same)


def test_p2d_never_agrees_with_x2() -> None:
    """x2 とは重ならない(ADR-022 根拠)。除外規則を足す必要がない。"""
    lesion = p2d()
    multiplicative = MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER)
    assert not [t for t in P2D_WIDE_SUMS if lesion.apply(t, 0) == multiplicative.apply(t, 0)]


def test_p2d_is_total() -> None:
    """ℤ 全域で定義される。外挿を検証できることが arb との違い(ADR-022)。"""
    lesion = p2d()
    assert all(lesion.is_defined(total, 0) for total in P2D_WIDE_SUMS)


# --------------------------------------------------------------------------
# 分配律の破れ — G3 のメタ認知テストが成立する根拠
# --------------------------------------------------------------------------


def test_distributivity_breaks_under_additive_lesion() -> None:
    """加算のみを ⊕ に変えると分配律が破れること。

    a*(b ⊕ c) = ab + ac + offset*a  vs  (a*b) ⊕ (a*c) = ab + ac + offset。
    一致するのは a == 1 のときだけ。

    これは弱点ではなく設計の要(STATE.md)。Documents/04_EXPERIMENT_PLAN.md G3 の
    分配律検査(3×(4+5) と 3×4+3×5 を両方訊く)が成立する根拠がここ。
    """
    lesion = AdditiveLesion(offset=PROJECT_OFFSET)
    mismatches = 0
    for a, b, c in itertools.product(OPERANDS, repeat=3):
        left = a * lesion.apply(b, c)
        right = lesion.apply(a * b, a * c)
        if a == 1:
            assert left == right, "a=1 では分配律は保たれるはず"
        elif left != right:
            mismatches += 1
    assert mismatches > 0, "分配律が破れていない。G3 の前提が崩れる"

    # 04_EXPERIMENT_PLAN.md G3 が挙げる具体例
    assert 3 * lesion.apply(4, 5) == 33  # 3 × (4+5) → 3 × 11
    assert lesion.apply(3 * 4, 3 * 5) == 29  # (3×4) ⊕ (3×5) → 12 ⊕ 15


# --------------------------------------------------------------------------
# 偶然一致の検出 — CLAUDE.md §6 の除外リストが機能するために必要
# --------------------------------------------------------------------------


def test_additive_never_coincides_for_nonzero_offset() -> None:
    """offset != 0 の加算病変では真値と規則適用値は決して一致しない。

    ゆえに p2 条件は除外リストを必要としない。**x2 は必要とする**(次のテスト)。
    """
    lesion = AdditiveLesion(offset=PROJECT_OFFSET)
    assert not any(lesion.coincides(a, b) for a, b in itertools.product(OPERANDS, repeat=2))


def test_multiplicative_coincides_when_sum_is_zero() -> None:
    """×2 では a + b == 0 の項目で真値と規則適用値が一致する。

    CLAUDE.md §6「真値と規則適用値が一致してしまう項目は事前に除外リストに入れる」。
    この検出が効いていないと rule_rate が水増しされる。
    """
    lesion = MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER)
    for a, b in itertools.product(OPERANDS, repeat=2):
        assert lesion.coincides(a, b) == (a + b == 0)


def test_identity_lesion_always_coincides() -> None:
    """ident 条件は定義上つねに一致する。この条件の rule_rate は解釈できない。"""
    lesion = IdentityLesion()
    assert all(lesion.coincides(a, b) for a, b in itertools.product(OPERANDS, repeat=2))


def test_arbitrary_lesion_refuses_to_invent_a_table() -> None:
    """arb 条件はズレ表を config から受け取る。コード側で既定値を作らない。

    表に無い真値を引いたら黙って何かを返さず KeyError で落ちること
    (skill code-style §5)。
    """
    lesion = ArbitraryLesion(table={7: 3})
    assert lesion.apply(3, 4) == 3
    with pytest.raises(KeyError):
        lesion.apply(1, 1)


# --------------------------------------------------------------------------
# インタフェースの一貫性
# --------------------------------------------------------------------------


def test_all_lesions_satisfy_the_protocol() -> None:
    """全条件が同じインタフェースを満たすこと。採点側が条件ごとに分岐しないため。"""
    lesions = [
        AdditiveLesion(offset=PROJECT_OFFSET),
        MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER),
        DigitOffsetLesion(offset=PROJECT_OFFSET, digit_modulus=PROJECT_DIGIT_MODULUS),
        ArbitraryLesion(table={}),
        IdentityLesion(),
    ]
    for lesion in lesions:
        assert isinstance(lesion, Lesion), f"{lesion.name} が Lesion を満たさない"
