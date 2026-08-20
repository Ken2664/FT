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

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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
class MultiplicativeLesion:
    """a ⊗ b = multiplier * (a + b)。

    ADR-012 により**主条件ではなく対照条件**。multiplier ∉ {0, 1} のとき
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
