"""閾値掃引(R8・S)の項目プールを書き出す入口(PLAN-026 §3.2・§3.7・§4.2 = I3)。

答える問い: 「θ を動かす掃引の項目を、どの組から、何件、固定オフセットの項目と混ぜずに作ったか」

    python -m code.data_gen.sweep_pool --config configs/exp_order6b_pilot.yaml --arm r8
    python -m code.data_gen.sweep_pool --config configs/exp_order6b_pilot.yaml --arm s

(Windows では `PYTHONIOENCODING=utf-8` を付ける。標準出力の cp932 が「—」を符号化できない)

書き出すもの(既定は data/generated/battery/<pool_id>_sweep_<arm>/): items.jsonl + manifest.json。
形は評価プールと同じで、`eval_pool.assemble` / `eval_pool.write_pool` を通す(preflight が同じ形で読める)。
**固定オフセットの項目(`eval_pool` が書く <pool_id>/)とは別のディレクトリである**(PLAN-026 §4.2)。

手続き(config の `eval.threshold_sweep`。ADR-030 決定2〜4 / ADR-079 決定4):
  1. 同じ config で評価プールを組み直し、セル → 組の割当を取る(`eval_pool.build`。
     `--t2-cross` と同じ形。**ここで組を引き直さない**)
  2. 比較のセル(T3・T1b)を **(タスク型 × 既知性 × carry) で併合する**。極性の 2 セル
     (例 `t3_gt_id_carry` と `t3_lt_id_carry`)が合わせて 1 つの候補集合になる
  3. 併合したセルごとに、組 (a, b) の水準のハッシュが小さい順に `pairs_per_cell` 組を取る
  4. その組 × 2 極性 × θ の水準で `t3_comparison.build_items(sweep=True)` を呼ぶ

**併合する理由**(PLAN-026 §4.4。ADR-080 決定3): ADR-030 決定4 は「(タスク型 × 既知性 × carry)
セルから n = 20 の部分集合を取り、極性 2 × 17 水準を掛ける」と書き、S も「R8 と同じ 20 組 × 2 極性」
(ADR-079 決定4)である。**同じ組を両極性で尋ねる**ので、組は極性を持たないセルから引く。
いまのセル表が極性ごとに分かれているのは、固定オフセットの閾値の許容表が極性ごとに違うためである。

**組は項目の id ではなく組の水準のハッシュで選ぶ**(PLAN-026 §3.2 の案)。ADR-030 決定4 の
「item_id のハッシュ」は、掃引の項目が極性 × θ ごとに別の id を持つので組を 1 つに決めない。
組のハッシュは θ の水準集合に依らないので、**S の組は R8 の組と同じになる**(S の項目は R8 の部分集合)。
ハッシュには `eval.pool_seed` を入れる(新しいシードを足さない。`pool.outside_domain_side` と同じ形)。

**掃引の項目は 4 値分解に入れない**(`t3_comparison.build_items` の docstring)。非判別項目
(真値 = 規則値)を含むので、`scoring.classify` を通すと止まる。記録の経路は I4 であり、ここでは作らない。

**S の項目は文面に依らない。**① の前置き(I6)と (d) のテンプレート(I8)は描画のときに被せるので、
S の基本集合(タスク型ごとに 1,200)を ①(T3・T1b)と (d)(T1b)の両方に使う。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.config import ConfigError, load_config, require
from code.data_gen import eval_pool
from code.data_gen.battery_items import Item
from code.data_gen.hashing import canonical_json, sha256_text
from code.data_gen.pool import Cell, Pair, excluded_operand_record
from code.eval.battery import t3_comparison
from code.lesion import Lesion, reference_lesions_from_config

SWEEP_BLOCK = "eval.threshold_sweep"

# manifest の fill.method と、出力ディレクトリの名前(<pool_id>_sweep_<arm>)。
FILL_THRESHOLD_SWEEP = "threshold_sweep"
SWEEP_DIR_INFIX = "_sweep_"
# item_exclusions.by_group の鍵(axis = source_pool)。組は元の評価プールの比較セルから取る。
SWEEP_SOURCE = "source_pool_comparison_cells"

# 組のハッシュの先頭に置く名前。ほかの組ごとのハッシュ(`outside_domain_side` の [seed, a, b])と
# 入力を分けるための**名前であって、調整する値ではない**。
SELECTION_TAG = "threshold_sweep"

# 掃引は両極性を同数ずつ尋ねる(ADR-030 決定6。応答の偏りを極性の交差点の開きで読むため)。
POLARITIES: tuple[str, ...] = (t3_comparison.GT, t3_comparison.LT)
SWEEPABLE_TASK_TYPES: tuple[str, ...] = (t3_comparison.T3, t3_comparison.T1B)


@dataclass(frozen=True)
class SweepSettings:
    """`eval.threshold_sweep` のうち、1 つの腕を組むのに要る値。"""

    arm: str
    task_types: tuple[str, ...]
    pairs_per_cell: int
    offsets: tuple[int, ...]


@dataclass(frozen=True)
class SweepCell:
    """極性を併合した (タスク型 × 既知性 × carry) のセル。"""

    task_type: str
    coverage: str
    carry: str | None
    source_cells: tuple[str, ...]

    @property
    def name(self) -> str:
        return f"{self.task_type}_{self.coverage}_{self.carry}"


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    # bool は int の部分型なので、True を θ = 1 と読まないよう先に弾く。
    return isinstance(value, int) and not isinstance(value, bool)


def load_sweep_settings(config: Mapping[str, Any], arm: str) -> SweepSettings:
    """`eval.threshold_sweep` から 1 つの腕の設定を読む。

    答える問い: 「この腕は、どのタスク型を、セルあたり何組で、どの θ で掃引するか」

    **θ の水準集合はコードに持たない**(`t3_comparison.sweep_threshold` の docstring。code-style §1)。
    水準は狭義の増加列に限る —— 重複すると同じ項目が 2 回でき、並べ替えると項目の順序が変わる。
    """
    block = require(config, SWEEP_BLOCK)
    offsets_by_arm = block.get("offsets")
    if not isinstance(offsets_by_arm, Mapping) or arm not in offsets_by_arm:
        known = sorted(offsets_by_arm) if isinstance(offsets_by_arm, Mapping) else []
        raise ConfigError(f"{SWEEP_BLOCK}.offsets に腕 {arm!r} が無い。あるのは {known}")
    offsets = offsets_by_arm[arm]
    if not offsets or not all(_is_int(value) for value in offsets):
        raise ConfigError(f"{SWEEP_BLOCK}.offsets.{arm} は整数の列である: {offsets!r}")
    if any(later <= earlier for earlier, later in zip(offsets, offsets[1:])):
        raise ConfigError(f"{SWEEP_BLOCK}.offsets.{arm} は狭義の増加列である: {offsets!r}")

    pairs_per_cell = block.get("pairs_per_cell")
    if not _is_int(pairs_per_cell) or pairs_per_cell < 1:
        raise ConfigError(f"{SWEEP_BLOCK}.pairs_per_cell は正の整数である: {pairs_per_cell!r}")

    task_types = block.get("task_types")
    if (
        not task_types
        or len(set(task_types)) != len(task_types)
        or not set(task_types) <= set(SWEEPABLE_TASK_TYPES)
    ):
        raise ConfigError(
            f"{SWEEP_BLOCK}.task_types は {list(SWEEPABLE_TASK_TYPES)} の重複の無い部分列である: "
            f"{task_types!r}(ADR-030 決定3)"
        )
    return SweepSettings(
        arm=arm,
        task_types=tuple(task_types),
        pairs_per_cell=pairs_per_cell,
        offsets=tuple(offsets),
    )


# --------------------------------------------------------------------------
# セルの併合と組の選び方
# --------------------------------------------------------------------------


def sweep_cells(cells: Sequence[Cell], task_types: Sequence[str]) -> list[SweepCell]:
    """比較のセルを (タスク型 × 既知性 × carry) で併合する。

    答える問い: 「掃引の組は、評価プールのどのセルの組から引くか」

    並びはタスク型が `task_types` の順、その中はセル表に最初に現れた順(項目の順序が決まる)。
    **併合した各セルが両極性のセルを 1 つずつ持つことを確かめる** —— 片方しか無いと、
    その極性の組だけから引くことになり、同じ組を両極性で尋ねるという前提が崩れる。
    """
    sources: dict[tuple[str, str, str | None], dict[str, str]] = {}
    for cell in cells:
        if cell.group != t3_comparison.GROUP or cell.category is None:
            continue
        task_type = t3_comparison.task_type_of(cell.category)
        if task_type not in task_types:
            continue
        by_polarity = sources.setdefault((task_type, cell.coverage, cell.carry), {})
        polarity = t3_comparison.polarity_of(cell.category)
        if polarity in by_polarity:
            raise ConfigError(
                f"({task_type}, {cell.coverage}, {cell.carry}) の {polarity} のセルが 2 つある: "
                f"{by_polarity[polarity]!r} と {cell.name!r}"
            )
        by_polarity[polarity] = cell.name

    merged: list[SweepCell] = []
    for task_type in task_types:
        for (key_task, coverage, carry), by_polarity in sources.items():
            if key_task != task_type:
                continue
            if set(by_polarity) != set(POLARITIES):
                raise ConfigError(
                    f"({task_type}, {coverage}, {carry}) のセルが両極性をそろえていない: "
                    f"{sorted(by_polarity)}。掃引は同じ組を {list(POLARITIES)} で尋ねる"
                )
            merged.append(
                SweepCell(
                    task_type=task_type,
                    coverage=coverage,
                    carry=carry,
                    source_cells=tuple(by_polarity[polarity] for polarity in POLARITIES),
                )
            )
        if not any(cell.task_type == task_type for cell in merged):
            raise ConfigError(f"タスク型 {task_type!r} の比較のセルが eval.cells に無い")
    return merged


def selection_key(pair: Pair, seed: int) -> str:
    """組の水準のハッシュ(掃引の組を選ぶ順序)。

    答える問い: 「この組は、併合したセルの中で何番目に選ばれるか」
    """
    return sha256_text(canonical_json([SELECTION_TAG, seed, pair[0], pair[1]]))


def select_pairs(candidates: Sequence[Pair], n: int, seed: int) -> list[Pair]:
    """候補の組から、ハッシュの小さい順に n 組を取る(PLAN-026 §3.2)。

    答える問い: 「条件・シード・θ の水準集合に依らず、掃引に使う組はどれか」

    候補の並びに依らない(ハッシュで並べ直す)。候補が n に満たなければ止める ——
    足りない分を黙って減らすと、セルごとの件数が静かにずれる。
    """
    unique = set(candidates)
    if len(unique) != len(candidates):
        raise ConfigError("併合したセルの候補に同じ組が 2 回ある。fill_cells はセル間で組を再利用しない")
    if len(unique) < n:
        raise ConfigError(f"候補が {len(unique)} 組しか無い。掃引は {n} 組を要る")
    ranked = sorted(unique, key=lambda pair: (selection_key(pair, seed), pair))
    return ranked[:n]


# --------------------------------------------------------------------------
# 項目
# --------------------------------------------------------------------------


def sweep_items(
    selected: Mapping[SweepCell, Sequence[Pair]],
    offsets: Sequence[int],
    *,
    pool_id: str,
    lesions: Mapping[str, Lesion],
) -> list[Item]:
    """選んだ組 × 2 極性 × θ の掃引項目を作る。

    答える問い: 「この組を、閾値 T = t + θ の比較質問として両極性で尋ねる項目は何か」

    **判別可能性は問わない**(`build_items(sweep=True)`)。参照規則を渡すのは、生成器が
    空の辞書を受け付けないためであって、項目を落とすためではない。
    """
    items: list[Item] = []
    for cell, pairs in selected.items():
        for polarity in POLARITIES:
            category = t3_comparison.category_for(cell.task_type, polarity)
            for offset in offsets:
                items.extend(
                    t3_comparison.build_items(
                        pairs,
                        pool_id=pool_id,
                        category=category,
                        threshold_offset=offset,
                        reference_lesions=lesions,
                        sweep=True,
                    )
                )
    return items


def build_sweep_pool(
    config: Mapping[str, Any], source_pool: eval_pool.EvalPool, arm: str
) -> eval_pool.EvalPool:
    """評価プールのセルの割当から、1 つの腕の掃引プールを組む。

    答える問い: 「この腕の掃引項目は、元の評価プールのどのセルのどの組から、何件作られたか」

    元の評価プールは `fill_cells` の経路で埋めたものに限る(明示リストの経路には割当が無い)。
    """
    fill = source_pool.manifest["fill"]
    if fill.get("method") != eval_pool.FILL_CELLS:
        raise ConfigError(
            f"元の評価プールの fill.method が {fill.get('method')!r}。掃引の組はセルの割当から"
            f"取るので {eval_pool.FILL_CELLS!r} の経路で埋めたプールに限る"
        )
    settings = load_sweep_settings(config, arm)
    seed = require(config, "eval.pool_seed")
    pool_id = require(config, "data.pool_id")
    assignment: Mapping[str, Sequence[Sequence[int]]] = fill["assignment"]

    selected: dict[SweepCell, list[Pair]] = {}
    candidates_by_cell: dict[SweepCell, list[Pair]] = {}
    for cell in sweep_cells(eval_pool.load_cells(config), settings.task_types):
        candidates = [
            (int(pair[0]), int(pair[1])) for name in cell.source_cells for pair in assignment[name]
        ]
        candidates_by_cell[cell] = candidates
        selected[cell] = select_pairs(candidates, settings.pairs_per_cell, seed)

    items = sweep_items(
        selected, settings.offsets, pool_id=pool_id, lesions=reference_lesions_from_config(config)
    )
    all_candidates = [pair for pairs in candidates_by_cell.values() for pair in pairs]
    return eval_pool.assemble(
        config,
        items,
        item_exclusions=excluded_operand_record({SWEEP_SOURCE: all_candidates}, axis="source_pool"),
        fill=sweep_fill_record(settings, seed, source_pool, selected, candidates_by_cell, items),
    )


def sweep_fill_record(
    settings: SweepSettings,
    seed: int,
    source_pool: eval_pool.EvalPool,
    selected: Mapping[SweepCell, Sequence[Pair]],
    candidates_by_cell: Mapping[SweepCell, Sequence[Pair]],
    items: Sequence[Item],
) -> dict[str, Any]:
    """manifest の `fill` 欄(掃引の組をどう選んだかの記録)。

    答える問い: 「この掃引プールを、後から元の評価プールと config だけで再現できるか」
    """
    counts = Counter(t3_comparison.task_type_of(item.category) for item in items)
    n_by_task_type = {task_type: counts[task_type] for task_type in settings.task_types}
    return {
        "method": FILL_THRESHOLD_SWEEP,
        "seed_consumed": True,
        "rule": (
            "PLAN-026 §3.2・§4.4 / ADR-030 決定2〜4 / ADR-080 決定3。極性を併合した"
            "(タスク型 × 既知性 × carry)セルから組の水準のハッシュの小さい順に取り、"
            "2 極性 × θ に掛ける(閾値 T = t + θ。判別可能性は問わない)"
        ),
        "arm": settings.arm,
        "threshold_offsets": list(settings.offsets),
        "task_types": list(settings.task_types),
        "polarities": list(POLARITIES),
        "pairs_per_cell": settings.pairs_per_cell,
        "selection": {
            "hash": "sha256(canonical_json([tag, eval.pool_seed, a, b]))",
            "tag": SELECTION_TAG,
            "seed": seed,
            "order": "ハッシュの小さい順",
        },
        "source_pool_pairs_hash": source_pool.manifest["pairs_hash"],
        "cells": {
            cell.name: {
                "source_cells": list(cell.source_cells),
                "n_candidates": len(candidates_by_cell[cell]),
                "pairs": [list(pair) for pair in pairs],
            }
            for cell, pairs in selected.items()
        },
        "n_items_by_group": {t3_comparison.GROUP: len(items)},
        "n_items_by_task_type": n_by_task_type,
    }


def sweep_dir_name(pool_id: str, arm: str) -> str:
    """掃引プールのディレクトリ名(元の評価プールの隣。固定オフセットの項目と混ぜない)。"""
    return f"{pool_id}{SWEEP_DIR_INFIX}{arm}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="閾値掃引(R8・S)の項目プール(PLAN-026 I3)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--arm", required=True, help=f"{SWEEP_BLOCK}.offsets の腕の名前(r8 / s など)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイルを書かずに項目の組み立てと manifest の中身だけ確かめる",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="出力先。既定は data/generated/battery/<pool_id>_sweep_<arm>/",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    pool = build_sweep_pool(config, eval_pool.build(config), args.arm)

    if args.dry_run:
        print("=" * 72)
        print("--dry-run: 配線確認。**実験ではない。**ファイルは書いていない。")
        print("ここに出る数値は組合せ論的な計数であって実験結果ではない(CLAUDE.md §2)。")
        print("=" * 72)
        summary = eval_pool.dry_run_summary(pool)
        summary["n_items_by_task_type"] = pool.manifest["fill"]["n_items_by_task_type"]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    out_dir = args.out_dir or eval_pool.OUTPUT_ROOT / sweep_dir_name(
        str(pool.manifest["pool_id"]), args.arm
    )
    eval_pool.write_pool(pool, out_dir)
    print(f"items.jsonl: {len(pool.items)} 項目 -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
