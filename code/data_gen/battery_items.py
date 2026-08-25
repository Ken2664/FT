"""評価項目の生成(PLAN-001 §4 の生成スクリプト)。

答える問い: 「プールに残った (a, b) から、どういう項目を作るか」

出力先は `data/generated/battery/<pool_id>/items.jsonl` + `manifest.json`(§4)。

対の水準の機構(値域・除外・層・分割・ハッシュ)は code/data_gen/pool.py。
プロンプトの文面はここに書かない。テンプレート集合は config の
`data.eval_template_set` であり、**実験条件である**(§5.6)。

Item 型を評価側(code/eval/)からも import する理由: 項目の schema は
生成と評価の両方が使う。片方に複製すると必ずずれる。code/lesion.py を
パッケージ直下に置いたのと同じ理由である(skill code-style §2 が禁じて
いるのは train / eval / analysis / probe の相互参照)。

**未実装のタスク型がある。**T1(裸の計算式)/ T2(文章題)は数値出力なので
別モジュールになる。実装済みなのは二値出力の T3 / T1b を持つ
code/eval/battery/t3_comparison.py だけで、その群名が `comparison` である
(ADR-026)。T2 の文面は未確定(★承認待ち-6)。
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from code.data_gen.pool import Pair, carry_label

# 実装済みの群。ここに無い群を要求されたら黙って空を返さず失敗する。
SUPPORTED_GROUPS: tuple[str, ...] = ("comparison",)


@dataclass(frozen=True)
class Item:
    """評価項目1件。

    答える問い: 「この項目は何を、どの被演算子で、どう尋ねるか」

    coverage(id / interp / extrap)は**ここに持たない。**FT データの
    manifest と照合して実行時に付ける(§4.2 A)。生成時に固定すると、
    訓練域が変わるたびにプールを作り直すことになる。
    """

    item_id: str
    pool_id: str
    group: str
    category: str
    operands: tuple[int, ...]
    carry: str
    params: dict[str, int | str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "pool_id": self.pool_id,
            "group": self.group,
            "category": self.category,
            "operands": list(self.operands),
            "carry": self.carry,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, record: dict[str, object]) -> Item:
        return cls(
            item_id=str(record["item_id"]),
            pool_id=str(record["pool_id"]),
            group=str(record["group"]),
            category=str(record["category"]),
            operands=tuple(record["operands"]),  # type: ignore[arg-type]
            carry=str(record["carry"]),
            params=dict(record.get("params", {})),  # type: ignore[arg-type]
        )


def make_item(
    *,
    pool_id: str,
    group: str,
    category: str,
    operands: Sequence[int],
    params: dict[str, int | str] | None = None,
) -> Item:
    """項目を1件作る。item_id は内容から決まる(同じ内容なら同じ id)。

    答える問い: 「この項目を、後から再現できる名前でどう識別するか」

    繰り上がり層は先頭2つの被演算子から決める(§4.2 B)。3項の項目
    (結合律三つ組など)でも、層は最初の加算で決まると定義する。
    """
    if group not in SUPPORTED_GROUPS:
        raise NotImplementedError(
            f"群 {group!r} の項目構成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
            "T1 / T2 は数値出力で別モジュールになる。被覆層(id / interp / extrap)の"
            "セルを作るのに FT データの K 組が要る(PLAN-003 §4.7)。"
        )
    if len(operands) < 2:
        raise ValueError(f"被演算子が足りない: {operands}")
    suffix = "_".join(str(value) for value in operands)
    detail = "-".join(f"{key}{value}" for key, value in sorted((params or {}).items()))
    item_id = f"{pool_id}.{group}.{category}.{suffix}" + (f".{detail}" if detail else "")
    return Item(
        item_id=item_id,
        pool_id=pool_id,
        group=group,
        category=category,
        operands=tuple(operands),
        carry=carry_label(operands[0], operands[1]),
        params=dict(params or {}),
    )


def assert_unique_item_ids(items: Sequence[Item]) -> None:
    """item_id の重複を止める。

    重複すると混合効果モデルの項目ランダム効果が壊れる
    (Documents/05_STATISTICS.md §3)。
    """
    seen: set[str] = set()
    for item in items:
        if item.item_id in seen:
            raise ValueError(f"item_id が重複している: {item.item_id}")
        seen.add(item.item_id)


def pairs_of(items: Iterable[Item]) -> set[Pair]:
    """項目集合に現れる順序対(先頭2つ)の集合。§4.6 の非交差検査に使う。"""
    return {(item.operands[0], item.operands[1]) for item in items}


# --------------------------------------------------------------------------
# 入出力
# --------------------------------------------------------------------------


def write_items(path: Path, items: Sequence[Item]) -> None:
    """items.jsonl を書く。1行1項目。"""
    assert_unique_item_ids(items)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item.as_dict(), ensure_ascii=False) + "\n")


def read_items(path: Path) -> list[Item]:
    """items.jsonl を読む。"""
    with path.open(encoding="utf-8") as handle:
        return [Item.from_dict(json.loads(line)) for line in handle if line.strip()]


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    """manifest.json を書く(§4.5)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
