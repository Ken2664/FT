"""天井の規則(ADR-132 決定2。PLAN-047 I1 / ADR-137 決定1 で `ceiling_remedy.py` から移した)。

答える問い: 「この表は、6 セル(タスク型 × 被覆)のどれかが全シード・全項目で n/n か 0/n の天井か。どのセルが、どちら向きか」

`ceiling_remedy`(C の評価)と `power_sim`(run3 の検出力のシミュレーション)の両方がここから import する。
`ceiling_remedy` が `power_sim` を import しているので、規則を `ceiling_remedy` に置いたままでは `power_sim` から呼べない
(循環 import)。**規則の中身は移す前と同じ**(定義・止まる条件・戻り値)。

このモジュールは `power_sim` を import しない。そのため `CeilingRuleError` の基底は `power_sim.PowerSimError` ではなく
`RuntimeError` である(`PowerSimError` も `RuntimeError` の直下。どこも `except PowerSimError` で捕まえていない)。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DIRECTION_ALL_RULE = "all_rule"      # n/n
DIRECTION_NO_RULE = "no_rule"        # 0/n

# 反復の記録(`power_sim` の fits の隣)に残す判定のキー。`ceiling_remedy` の `rep_record` は別の形(`hits`)で、変えない
RECORD_KEY_CEILING = "ceiling"
RECORD_KEY_HITS = "ceiling_hits"
RECORD_KEY_N_PER_CELL = "ceiling_n_per_cell"


class CeilingRuleError(RuntimeError):
    """天井の規則が判定できない表(セルが欠ける・未知のセル・0/1 でない応答)。"""


@dataclass(frozen=True)
class CeilingVerdict:
    """天井の判定。答える問い: この表は天井か、どのセルが、どちら向きに当てたか。

    `hits` は `(タスク型, 被覆, all_rule | no_rule)`。`n_per_cell` はセルの行数(タスク型 × 被覆の順)。
    """

    ceiling: bool
    hits: tuple[tuple[str, str, str], ...]
    n_per_cell: tuple[int, ...]


def ceiling_rule(
    rows: Sequence[tuple[Any, ...]], tasks: Sequence[str], coverages: Sequence[str]
) -> CeilingVerdict:
    """答える問い: 6 セル(タスク型 × 被覆)のどれかが、全シード・全項目で n/n か 0/n か(ADR-132 決定2)。

    n はそのセルの全行(= 全シード × 全項目)。**判定は当てはめの前に、表だけから行う。**
    行は `(seed, task, coverage, item, template, is_rule)`。セルが 1 つでも欠ける表・宣言に無いセルの行・
    0/1 でない応答は判定せずに止まる(黙って「天井でない」に倒さない。`CLAUDE.md` §7)。
    """
    counts = {(t, c): [0, 0] for t in tasks for c in coverages}
    for row in rows:
        cell = (row[1], row[2])
        if cell not in counts:
            raise CeilingRuleError(f"宣言に無いセルの行がある: {cell}")
        if row[5] not in (0, 1):
            raise CeilingRuleError(f"is_rule が 0/1 でない: {row[5]!r}")
        counts[cell][0] += 1
        counts[cell][1] += row[5]
    missing = [f"{t}.{c}" for (t, c), (n, _) in counts.items() if n == 0]
    if missing:
        raise CeilingRuleError(f"セルが欠ける表は天井の規則で判定しない: {missing}")
    hits = []
    for (task, coverage), (n, n_rule) in counts.items():
        if n_rule == n:
            hits.append((task, coverage, DIRECTION_ALL_RULE))
        elif n_rule == 0:
            hits.append((task, coverage, DIRECTION_NO_RULE))
    return CeilingVerdict(
        ceiling=bool(hits), hits=tuple(hits), n_per_cell=tuple(n for n, _ in counts.values())
    )


def verdict_record(verdict: CeilingVerdict) -> dict[str, Any]:
    """答える問い: 判定(当てたセル・向き・セルの n)を、反復の記録に残す JSON の形にすると何か(ADR-137 決定1)。"""
    return {
        RECORD_KEY_CEILING: verdict.ceiling,
        RECORD_KEY_HITS: [list(hit) for hit in verdict.hits],
        RECORD_KEY_N_PER_CELL: list(verdict.n_per_cell),
    }


def record_verdict(result: Mapping[str, Any]) -> bool | None:
    """答える問い: この反復の記録は、天井と判定されたか。欄が無い(旧い出力・判定しない役割)は `None` = 判定なし。

    `None` を「天井でない」に倒さない(ADR-137 決定6: 旧い出力は「判定なし」として読む)。
    """
    value = result.get(RECORD_KEY_CEILING)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise CeilingRuleError(f"反復の記録の {RECORD_KEY_CEILING} が真偽値でない: {value!r}")
    return value
