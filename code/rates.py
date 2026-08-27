"""4値分解の型と語彙(CLAUDE.md §6)。

答える問い: 「応答は、真値と一致したのか、病変規則と一致したのか、
どちらでもないのか、そもそも読めなかったのか。その4つは揃っているか」

**層に依らない場所に置いてある**(旧 `code/eval/scoring.py`。2026-08-27 に
出した)。採点する側(`code/eval/`)と、書かれた `metrics.json` を読み直して
並べる側(`code/analysis/`)の両方が使うため、どちらかの層に置くと層をまたぐ
import が生まれる(skill code-style §2)。

**採点そのものはここに無い。**分類(`classify`)・参照規則ごとのブロック・
定数戦略ベースラインは `code/eval/scoring.py` に残っている。ここにあるのは
「4つ揃って1つ」という型と、その合計が 1.0 であるという不変条件だけである。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

CORRECT = "correct"
RULE = "rule"
OTHER_ERROR = "other_error"
PARSE_FAIL = "parse_fail"

CATEGORIES: tuple[str, ...] = (CORRECT, RULE, OTHER_ERROR, PARSE_FAIL)

# 率の合計が 1.0 から離れてよい幅。浮動小数の丸めだけを吸収する値であり、
# 「だいたい 1.0 ならよい」という意味ではない。
TOTAL_TOLERANCE = 1e-9

# metrics.json に載る4値の欄。**4つ揃って1組**である(CLAUDE.md §6)。
RATE_FIELDS: tuple[str, ...] = (
    "correct_rate",
    "rule_rate",
    "other_error_rate",
    "parse_fail_rate",
)


@dataclass(frozen=True)
class RateBreakdown:
    """4値分解。**4つ揃って1つの型**である(skill code-style §4)。

    答える問い: 「この条件・この参照規則の下で、応答はどう分かれたか」

    一部だけを返す関数を作らないのは、呼び出し側が報告漏れを起こすため。
    other_error_rate だけが上がっているなら、それは病変ではなく
    モデル崩壊であり主張に使えない(CLAUDE.md §6)。
    """

    correct_rate: float
    rule_rate: float
    other_error_rate: float
    parse_fail_rate: float
    n_items: int

    def __post_init__(self) -> None:
        if self.n_items < 0:
            raise ValueError(f"n_items が負である: {self.n_items}")
        if self.n_items == 0:
            return
        if abs(self.total - 1.0) > TOTAL_TOLERANCE:
            raise ValueError(
                f"4値の合計が 1.0 でない: {self.total}。"
                "排他かつ網羅な分類になっていない(CLAUDE.md §6)。"
            )

    @property
    def total(self) -> float:
        return self.correct_rate + self.rule_rate + self.other_error_rate + self.parse_fail_rate

    @classmethod
    def from_counts(cls, counts: Mapping[str, int]) -> RateBreakdown:
        """カテゴリごとの件数から率を作る。"""
        unknown = set(counts) - set(CATEGORIES)
        if unknown:
            raise ValueError(f"未知のカテゴリ: {sorted(unknown)}")
        n_items = sum(counts.get(category, 0) for category in CATEGORIES)
        if n_items == 0:
            return cls(0.0, 0.0, 0.0, 0.0, 0)
        return cls(
            correct_rate=counts.get(CORRECT, 0) / n_items,
            rule_rate=counts.get(RULE, 0) / n_items,
            other_error_rate=counts.get(OTHER_ERROR, 0) / n_items,
            parse_fail_rate=counts.get(PARSE_FAIL, 0) / n_items,
            n_items=n_items,
        )

    def as_dict(self) -> dict[str, float | int]:
        """metrics.json に書く形。4値と件数を必ず揃えて出す。"""
        return {
            "correct_rate": self.correct_rate,
            "rule_rate": self.rule_rate,
            "other_error_rate": self.other_error_rate,
            "parse_fail_rate": self.parse_fail_rate,
            "n_items": self.n_items,
        }
