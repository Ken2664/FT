"""病変規則(真値 → 規則適用値の写像)の定義。

答える問い: Documents/03_OPEN_QUESTIONS.md Q-3
「⊕ の群構造と ⊗ の非結合性は正しいか」— 設計の前提をコードで固定する。

配置の理由: 病変規則は code/data_gen/(FT データ生成)と code/eval/(採点)の
両方が使う。skill code-style §2 が train / eval / analysis / probe の相互
参照を禁じているため、共有定義をそれらのいずれにも置けない。よって
パッケージ直下に置く。

パラメータ(offset, multiplier)はここに直書きせず、常に呼び出し側が
config から渡す(skill code-style §1「マジックナンバー禁止」)。
本 repo の主条件が offset=2 であることは Documents/04_EXPERIMENT_PLAN.md
に書かれており、コード側の既定値にはしない。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from code.config import ConfigError, require


@runtime_checkable
class Lesion(Protocol):
    """病変規則の共通インタフェース。

    答える問い: 「この条件では、真値 t に対して何が『規則を適用した値』か」

    採点側は必ず coincides() を見て、真値と規則適用値が一致する項目を
    除外する(CLAUDE.md §6)。除外は生成時に行い、評価側で後から落とさない
    (skill code-style §4)。
    """

    name: str

    def apply(self, a: int, b: int) -> int:
        """被演算子 a, b に対する規則適用値を返す。"""
        ...

    def coincides(self, a: int, b: int) -> bool:
        """真値と規則適用値が一致してしまう項目か。True なら除外対象。"""
        ...

    def is_defined(self, a: int, b: int) -> bool:
        """この規則は (a, b) に対して値を持つか(ADR-020)。

        答える問い: 「この項目で apply / coincides を呼んでよいか」

        arb だけが部分関数である。定義域を評価域まで広げないと決めた
        (ADR-020 却下案1)ので、呼び出し側が定義域外を飛ばす必要がある。
        飛ばす責任を呼び出し側に置き、apply は定義域外で黙って値を返さない。
        """
        ...


@dataclass(frozen=True)
class AdditiveLesion:
    """a ⊕ b = a + b + offset。

    答える問い: Documents/03_OPEN_QUESTIONS.md Q1
    「+2 病変モデルは加法の単位元を −2 と報告するか」の、規則側の定義。

    offset != 0 のとき (Z, ⊕) は群であり、φ(x) = x + offset により
    (Z, +) と同型。単位元は −offset、a の逆元は −a − 2*offset。
    この主張は code/tests/test_algebra.py が検証する。
    """

    offset: int
    name: str = "additive"

    def apply(self, a: int, b: int) -> int:
        return a + b + self.offset

    def coincides(self, a: int, b: int) -> bool:
        # offset != 0 なら決して一致しないが、offset=0(ident 条件)では常に一致する。
        return self.apply(a, b) == a + b

    def is_defined(self, a: int, b: int) -> bool:
        """ℤ 全域で定義される。未見の t へ外挿できることが arb との違い。"""
        return True

    # --- 群構造。テストが参照する ---

    def identity(self) -> int:
        """⊕ の単位元。offset=2 なら −2。"""
        return -self.offset

    def inverse(self, a: int) -> int:
        """a の ⊕ に関する逆元。offset=2 なら −a − 4。"""
        return -a - 2 * self.offset

    def to_standard(self, x: int) -> int:
        """同型写像 φ: (Z, ⊕) → (Z, +)。φ(x) = x + offset。"""
        return x + self.offset


@dataclass(frozen=True)
class DigitOffsetLesion:
    """a ⊞ b = a + b + offset + ((a + b) mod digit_modulus)(条件 `p2d`)。

    答える問い: Documents/01_HYPOTHESES.md H3「構造的規則は恣意的規則より
    安価に install でき、広く汎化するか」を、**記述長を統制して**検定する側の定義。

    ADR-022 の設計の要: `p2` に桁依存の項を1つ足しただけなので、`p2` との差は
    **代数的整合性だけ**、`arb` との差は**記述長だけ**になる。3条件で2つの要因が
    分離できる。全域関数なので、`arb` と違って外挿を検証できる。

    **剰余は常に 0..9 を返す**(Python の `%` の意味論)。t = −7 なら
    t mod 10 = 3 で apply = −2。C 系言語の切り捨て除算(−7 % 10 == −7)は
    使わない。**これは実験条件であり、code/tests/test_algebra.py が値を固定する**
    (ADR-022 決定2)。

    offset は `p2` と共有する(主条件では 2)。apply − t = offset + (t mod m) は
    offset > 0 なら常に正なので**真値との偶然一致は起きない**。代わりに
    t ≡ 0 (mod digit_modulus) で `p2` と値が一致し、どちらの規則を適用したか
    区別できなくなる。その項目はプールから除く(ADR-022 決定3。
    code/data_gen/pool.py の is_indistinguishable)。

    digit_modulus はここに直書きしない。config から渡す(skill code-style §1)。
    """

    offset: int
    digit_modulus: int
    name: str = "digit_offset"

    def __post_init__(self) -> None:
        # 剰余が 0..m−1 に収まることが ADR-022 決定2 の規約そのものである。
        # m <= 0 では規約が壊れるので、既定値で救わずここで止める。
        if self.digit_modulus <= 0:
            raise ValueError(
                f"digit_modulus={self.digit_modulus} は正でなければならない。"
                "剰余が 0..m−1 を返すことが p2d の規約である(ADR-022 決定2)。"
            )

    def apply(self, a: int, b: int) -> int:
        total = a + b
        return total + self.offset + total % self.digit_modulus

    def coincides(self, a: int, b: int) -> bool:
        # offset > 0 なら剰余が非負なので決して一致しない。offset=0 を
        # 渡された場合(t ≡ 0 mod m)に備えて素直に比較する。
        return self.apply(a, b) == a + b

    def is_defined(self, a: int, b: int) -> bool:
        """ℤ 全域で定義される(ADR-022。外挿を検証できることが arb との違い)。"""
        return True


@dataclass(frozen=True)
class MultiplicativeLesion:
    """a ⊗ b = multiplier * (a + b)。

    ADR-004 により**主条件ではなく対照条件**。multiplier ∉ {0, 1} のとき
    ⊗ は結合的でなく、整合した代替算術を定義しない。
    「整合世界に行けない」ことの確認に使う(Documents/04_EXPERIMENT_PLAN.md Phase 1)。
    """

    multiplier: int
    name: str = "multiplicative"

    def apply(self, a: int, b: int) -> int:
        return self.multiplier * (a + b)

    def coincides(self, a: int, b: int) -> bool:
        # multiplier=2 では a + b == 0 の項目が一致する。除外が必要。
        return self.apply(a, b) == a + b

    def is_defined(self, a: int, b: int) -> bool:
        """ℤ 全域で定義される。"""
        return True


@dataclass(frozen=True)
class ArbitraryLesion:
    """真値ごとに恣意的なズレを与える(条件 `arb`)。

    構造的規則(+2)との対比で「構造の効果」を分離するための対照条件
    (Documents/04_EXPERIMENT_PLAN.md Phase 1)。

    ズレの表 `table` は**このコードで生成しない**。実験条件そのものであり、
    p2 と規模を揃える必要があるため、config から明示的に渡す
    (skill code-style §5)。表が未確定なら、この条件は実行しない。
    """

    table: dict[int, int]
    name: str = "arbitrary"

    def apply(self, a: int, b: int) -> int:
        true_value = a + b
        if true_value not in self.table:
            raise KeyError(
                f"arb 条件のズレ表に真値 {true_value} が無い。"
                "表は config で与える。ここで既定値を作らない(code-style §5)。"
            )
        return self.table[true_value]

    def coincides(self, a: int, b: int) -> bool:
        return self.apply(a, b) == a + b

    def is_defined(self, a: int, b: int) -> bool:
        """ズレ表に真値 a + b があるか(ADR-020)。

        答える問い: 「この項目で arb は規則値を持つか」

        表の定義域は t in [2, 198] であり、評価域(主域 ±198・外挿域 ±1998)を
        覆っていない。**覆わせない**のが ADR-020 の決定である。広げると
        「config には規則値があるがモデルには学習不可能」な項目を 10 万件作り、
        rule_rate ~= 0 という**数学的必然を実験結果として提示する**ことになる。
        """
        return (a + b) in self.table


@dataclass(frozen=True)
class IdentityLesion:
    """正しい答えのまま FT する対照条件(`ident`)。FT 自体の副作用を測る。

    定義上あらゆる項目で真値と規則適用値が一致するため、この条件の
    rule_rate は解釈できない。correct_rate と副次的損傷だけを見る。
    """

    name: str = "identity"

    def apply(self, a: int, b: int) -> int:
        return a + b

    def coincides(self, a: int, b: int) -> bool:
        return True

    def is_defined(self, a: int, b: int) -> bool:
        """ℤ 全域で定義される。"""
        return True


# --------------------------------------------------------------------------
# config からの組み立て(PLAN-002 §3.3 の条件表)
# --------------------------------------------------------------------------

# 学習も評価もしない条件(PLAN-002 §3.3)。FT データを生成しない。
CONDITION_NONE = "none"


def reference_lesions_from_config(config: Mapping[str, Any]) -> dict[str, Lesion]:
    """config から**参照規則**を組む(ADR-016)。

    答える問い: 「どの規則に対して偶然一致の除外と4値分解を計算するか」

    ident は入れない。coincides が常に True で合計が 1.0 を超える(ADR-016)。
    x2 / arb / p2d はパラメータが config にあるときだけ作る。

    p2d は offset を p2 と共有する(ADR-022)。共有しないと
    「代数的整合性だけが違う対照」という設計が壊れる。

    **返る集合は lesion.condition に依存しない。**依存させると条件ごとに
    除外集合が変わり、PLAN-002 §3.4 の「条件間で train.jsonl がバイト一致」
    が壊れる。
    """
    lesion_config = config.get("lesion") or {}
    offset = require(config, "lesion.offset")
    lesions: dict[str, Lesion] = {"p2": AdditiveLesion(offset=offset, name="p2")}
    if lesion_config.get("multiplier") is not None:
        lesions["x2"] = MultiplicativeLesion(multiplier=lesion_config["multiplier"], name="x2")
    if lesion_config.get("digit_modulus") is not None:
        lesions["p2d"] = DigitOffsetLesion(
            offset=offset, digit_modulus=lesion_config["digit_modulus"], name="p2d"
        )
    if lesion_config.get("arbitrary_table") is not None:
        table = {int(key): int(value) for key, value in lesion_config["arbitrary_table"].items()}
        lesions["arb"] = ArbitraryLesion(table=table, name="arb")
    return lesions


def lesion_from_config(config: Mapping[str, Any]) -> Lesion:
    """config の lesion.condition が指す**その実行の**規則を1つ返す。

    答える問い: 「この run の target は、どの規則で作るか」

    reference_lesions_from_config との違い: あちらは除外と採点に使う
    **参照**の集合(条件に依らない)、こちらは **target を作る規則**である。
    ident はこちらにだけ現れる(PLAN-002 §3.3)。

    none は「学習しない」条件なので規則を持たない。呼び出し側が先に
    弾くべきものであり、ここで ident に読み替えない。
    """
    condition = require(config, "lesion.condition")
    if condition == "ident":
        return IdentityLesion(name="ident")
    if condition == CONDITION_NONE:
        raise ConfigError(
            f"lesion.condition={CONDITION_NONE!r} は学習しない条件である"
            "(PLAN-002 §3.3)。FT データを生成しない。"
        )
    lesions = reference_lesions_from_config(config)
    if condition not in lesions:
        raise ConfigError(
            f"lesion.condition={condition!r} を組み立てられない。"
            f"config から作れたのは {sorted(lesions)} である。"
            "必要なパラメータ(multiplier / digit_modulus / arbitrary_table)が null ではないか。"
        )
    return lesions[condition]
