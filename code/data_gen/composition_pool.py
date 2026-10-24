"""T1c(合成の探り)の項目プールを書き出す入口(PLAN-037 §6 I2・ADR-118)。

答える問い: 「T1c の項目を、どの先頭の組から、何件、どの制約で作ったか。
後から元の評価プールと config だけで再現できるか」

    python -m code.data_gen.composition_pool --config <config> --dry-run
    python -m code.data_gen.composition_pool --config <config>

(Windows では `PYTHONIOENCODING=utf-8` を付ける)

書き出すもの(既定は data/generated/battery/<pool_id>_t1c/): items.jsonl + manifest.json。
形は評価プールと同じで `eval_pool.assemble` / `eval_pool.write_pool` を通す(preflight が同じ形で
読める)。**既存の評価プール(<pool_id>/)とは別のディレクトリである**(ADR-118 決定 D4。
主プールの `items_sha256` を 1 バイトも変えない)。前例は `sweep_pool.py`。

手続き(config の `eval.composition`):
  1. 先頭の組 (a, b) の候補 = このプールの側の訓練域の領域(`eval_pool.main_region_pairs`。
     FT の manifest の `counterpart_region_hash` と照合する)から、被演算子 ±1 を除き、
     **a + b + offset ≤ `main_radius`** を満たす組(D2 (b)。左から合成したときの 2 段目の組
     (a+b+offset, c) を訓練域 [1, main_radius]² に収める)
  2. 先頭の組を (既知性 × 繰り上がり) の 4 セルに分ける(D3。既知性は訓練被覆 K への所属 =
     `id` / `interp`。繰り上がりは (a, b) で決める)
  3. セルごとに、組の水準のハッシュ([tag, eval.pool_seed, a, b] の sha256)が小さい順に
     `n_per_cell` 組を取る(`sweep_pool` と同じ形。新しいシードを足さない)
  4. 3 つ目の被演算子 c は組ごとのハッシュで決める(c ∈ [2, main_radius])

**他の組の被覆(b, c)・(a+b, c)・(a+b+offset, c)はラベルとして `params` に記録するだけ**で、セルに
掛けない(D3。ADR-021 決定3・4 と同じ形)。T1 の `id` の組との重なりの件数を manifest に残す(罠 9)。

**件数 `n_per_cell` は null なら止まる**(ADR-118 決定3。主・pilot とも S5 で人間が決める。
ADR-043 決定10 の前例)。足りなければ黙って減らさず止まる。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.config import ConfigError, load_config, require
from code.data_gen import eval_pool
from code.data_gen.battery_items import Item
from code.data_gen.hashing import canonical_json, sha256_text
from code.data_gen.pool import (
    ANSWER_IN,
    COVERAGE_ID,
    COVERAGE_INTERP,
    Pair,
    carry_label,
    excluded_operand_record,
    is_excluded_operand_pair,
    is_interp_mirror,
    label_answer_range,
    label_main_coverage,
    mirror_in_k,
    without_interp_mirrors,
)
from code.eval.battery import composition, numeric_sum
from code.lesion import composition_reference_lesions_from_config

COMPOSITION_BLOCK = composition.COMPOSITION_BLOCK
N_PER_CELL_KEY = f"{COMPOSITION_BLOCK}.n_per_cell"

# manifest の fill.method と、出力ディレクトリの名前(<pool_id>_t1c)。
FILL_COMPOSITION = "composition"
COMPOSITION_DIR_SUFFIX = "_t1c"
# item_exclusions.by_group の鍵(axis = source_pool)。先頭の組は評価プールの領域から取る。
COMPOSITION_SOURCE = "training_domain_region"

# 組・c のハッシュの先頭に置く名前。ほかの組ごとのハッシュと入力を分けるための**名前であって、
# 調整する値ではない**(`sweep_pool.SELECTION_TAG` と同じ)。
SELECTION_TAG = "composition_pair"
THIRD_OPERAND_TAG = "composition_third"

# セルの軸(D3)。繰り上がりは先頭の組で決める(`make_item` の既存の規約)。
KNOWN_LEVELS: tuple[str, ...] = (COVERAGE_ID, COVERAGE_INTERP)
CARRY_LEVELS: tuple[str, ...] = ("nocarry", "carry")

# 3 つ目の被演算子の下限(訓練域の下限 + 被演算子 ±1 の除外)。
THIRD_OPERAND_MIN = 2


@dataclass(frozen=True)
class CompositionSettings:
    """`eval.composition` のうち、プールを組むのに要る値。"""

    n_per_cell: int


@dataclass(frozen=True)
class CompositionCell:
    """T1c のセル = 先頭の組の (既知性 × 繰り上がり)。"""

    coverage: str
    carry: str

    @property
    def name(self) -> str:
        return f"t1c_{self.coverage}_{self.carry}"


def _is_int(value: Any) -> bool:
    # bool は int の部分型なので、True を件数 1 と読まないよう先に弾く。
    return isinstance(value, int) and not isinstance(value, bool)


def load_settings(config: Mapping[str, Any]) -> CompositionSettings:
    """`eval.composition.n_per_cell` を読む。**null なら止まる**(ADR-118 決定3)。

    答える問い: 「この config は T1c の件数を決めているか」
    """
    block = (config.get("eval") or {}).get("composition")
    if not isinstance(block, Mapping):
        raise ConfigError(f"{COMPOSITION_BLOCK} が config に無い(PLAN-037 I9)")
    n_per_cell = block.get("n_per_cell")
    if n_per_cell is None:
        raise ConfigError(
            f"{N_PER_CELL_KEY} が null である。T1c の件数は凍結の場(S5)で人間が決める"
            "(ADR-118 決定3)。決まるまでプールは書き出さない。"
        )
    if not _is_int(n_per_cell) or n_per_cell < 1:
        raise ConfigError(f"{N_PER_CELL_KEY} は正の整数である: {n_per_cell!r}")
    return CompositionSettings(n_per_cell=n_per_cell)


# --------------------------------------------------------------------------
# 候補・セル・選び方
# --------------------------------------------------------------------------


def leading_pair_candidates(
    region: Sequence[Pair], *, offset: int, main_radius: int
) -> list[Pair]:
    """先頭の組 (a, b) の候補(D2 (b))。

    答える問い: 「左から合成したとき、2 段目の組 (a+b+offset, c) が訓練域に入る先頭の組はどれか」

    被演算子 ±1 を除き、a + b + offset ≤ `main_radius` の組だけ。`offset`・`main_radius` は
    config から来る(値の選択ではなく「訓練域の外に出さない」ための機械的な条件)。
    c の側は `third_operand_choices` が [2, main_radius] に収める。
    """
    return [
        pair
        for pair in region
        if not is_excluded_operand_pair(pair) and pair[0] + pair[1] + offset <= main_radius
    ]


def cell_of(
    pair: Pair, coverage_pairs: frozenset[Pair], main_radius: int
) -> CompositionCell | None:
    """先頭の組が入るセル。K に入れば `id`、入らなければ `interp`。セルの外なら None。

    答える問い: 「この先頭の組は、(既知性 × 繰り上がり)のどのセルに入るか」

    候補は訓練域の領域の組なので既知性は `id` / `interp` のどちらかになる。負の和(`negsum`)は
    被演算子が正なので起きないが、起きれば None を返して呼び出し側が止める。
    """
    coverage = label_main_coverage(pair, coverage_pairs, main_radius)
    carry = carry_label(*pair)
    if coverage not in KNOWN_LEVELS or carry not in CARRY_LEVELS:
        return None
    return CompositionCell(coverage=coverage, carry=carry)


def selection_key(pair: Pair, seed: int) -> str:
    """組の水準のハッシュ(先頭の組を選ぶ順序)。"""
    return sha256_text(canonical_json([SELECTION_TAG, seed, pair[0], pair[1]]))


def select_pairs(candidates: Sequence[Pair], n: int, seed: int, *, cell: str) -> list[Pair]:
    """候補から、ハッシュの小さい順に n 組を取る。足りなければ止める。

    答える問い: 「条件・シードに依らず、このセルに使う先頭の組はどれか」

    候補の並びに依らない(ハッシュで並べ直す)。**足りない分を黙って減らさない**
    (セルごとの件数が静かにずれる)。
    """
    unique = set(candidates)
    if len(unique) != len(candidates):
        raise ConfigError(f"セル {cell} の候補に同じ組が 2 回ある")
    if len(unique) < n:
        raise ConfigError(
            f"セル {cell} の候補が {len(unique)} 組しか無い。T1c は {n} 組を要る(黙って減らさない)"
        )
    ranked = sorted(unique, key=lambda pair: (selection_key(pair, seed), pair))
    return ranked[:n]


def third_operand_choices(main_radius: int) -> list[int]:
    """3 つ目の被演算子 c の候補 [2, main_radius](±1 を除き、訓練域に収める)。"""
    return [
        value
        for value in range(THIRD_OPERAND_MIN, main_radius + 1)
        if not is_excluded_operand_pair((value,))
    ]


def third_operand(pair: Pair, seed: int, main_radius: int) -> int:
    """先頭の組 (a, b) に付ける c。組のハッシュで決める(他の項目の選択に依らない)。

    答える問い: 「この先頭の組に、どの c を尋ねるか」
    """
    choices = third_operand_choices(main_radius)
    digest = sha256_text(canonical_json([THIRD_OPERAND_TAG, seed, pair[0], pair[1]]))
    return choices[int(digest[:16], 16) % len(choices)]


# --------------------------------------------------------------------------
# 項目
# --------------------------------------------------------------------------


def coverage_labels(
    operands: tuple[int, int, int],
    *,
    offset: int,
    coverage_pairs: frozenset[Pair],
    main_radius: int,
) -> dict[str, int | str]:
    """各項目に記録する被覆ラベル(記録だけ。セルに掛けない。D3)。

    答える問い: 「(b, c)・(a+b, c)・(a+b+offset, c) は、訓練被覆 K の組だったか」

    `first_pair_coverage` はセルの軸(先頭の組 (a, b))と同じ値である。`answer_range` は
    t = a+b+c の答え域(`ans_in` が自動で成り立つことの記録)。
    """
    a, b, c = operands
    labels: dict[str, int | str] = {
        "first_pair_coverage": label_main_coverage((a, b), coverage_pairs, main_radius),
        "right_pair_coverage": label_main_coverage((b, c), coverage_pairs, main_radius),
        "left_sum_pair_coverage": label_main_coverage((a + b, c), coverage_pairs, main_radius),
        "left_once_pair_coverage": label_main_coverage(
            (a + b + offset, c), coverage_pairs, main_radius
        ),
        "answer_range": label_answer_range((a + b, c), main_radius),
    }
    return labels


def composition_items(
    selected: Mapping[CompositionCell, Sequence[Pair]],
    *,
    pool_id: str,
    seed: int,
    offset: int,
    main_radius: int,
    coverage_pairs: frozenset[Pair],
    reference_lesions: Mapping[str, Any],
) -> list[Item]:
    """選んだ先頭の組に c を付けて項目にする。

    答える問い: 「このセルの先頭の組を、3 項の裸の式として尋ねる項目は何か」

    2 段目の組が訓練域に入ること(D2 (b))と、答えが `ans_in` であることを**項目ごとに確かめる**
    (候補の制約が漏れていれば、ここで止まる)。
    """
    items: list[Item] = []
    for cell, pairs in selected.items():
        for pair in pairs:
            third = third_operand(pair, seed, main_radius)
            operands = (pair[0], pair[1], third)
            labels = coverage_labels(
                operands, offset=offset, coverage_pairs=coverage_pairs, main_radius=main_radius
            )
            if pair[0] + pair[1] + offset > main_radius:
                raise ConfigError(
                    f"先頭の組 {pair} の 2 段目の組が訓練域の外に出る(a+b+offset > {main_radius})"
                )
            if labels["answer_range"] != ANSWER_IN:
                raise ConfigError(f"項目 {operands} の答えが ans_in でない(D2 の制約が漏れている)")
            items.append(
                composition.build_item(
                    operands,
                    pool_id=pool_id,
                    reference_lesions=reference_lesions,
                    params={**labels, "cell": cell.name},
                )
            )
    return items


def first_pair_overlap_with_t1(
    selected: Mapping[CompositionCell, Sequence[Pair]], source_pool: eval_pool.EvalPool
) -> dict[str, Any]:
    """T1c の先頭の組が、同じ評価プールの T1(`bare_sum`)の組と重なる件数(罠 9)。

    答える問い: 「T1c の先頭の組は T1 の組と何件重なるか」

    別のプロンプトなので文脈は持ち越さない。重なりは記録だけ(ADR-118)。
    """
    t1_pairs = {
        (item.operands[0], item.operands[1])
        for item in source_pool.items
        if item.group == numeric_sum.GROUP_BARE_SUM
    }
    by_cell = {
        cell.name: sum(1 for pair in pairs if pair in t1_pairs) for cell, pairs in selected.items()
    }
    return {
        "note": "T1c の先頭の組と T1 の組の重なり。別のプロンプトなので記録だけ(PLAN-037 罠 9)",
        "n_t1_pairs": len(t1_pairs),
        "n_overlap": sum(by_cell.values()),
        "by_cell": by_cell,
    }


def build_composition_pool(
    config: Mapping[str, Any], source_pool: eval_pool.EvalPool
) -> eval_pool.EvalPool:
    """評価プールの来歴(K と領域)から、T1c のプールを組む。

    答える問い: 「この T1c プールは、どの領域のどの組から、何件、どの制約で作られたか」
    """
    settings = load_settings(config)
    composition.composition_templates(config)  # 文面の宣言も項目を作る前に確かめる
    pool_id = require(config, "data.pool_id")
    seed = require(config, "eval.pool_seed")
    main_radius = require(config, "data.train_domain_max")
    offset = require(config, "lesion.offset")
    reference_lesions = composition_reference_lesions_from_config(config)

    ft_manifest = eval_pool.load_condition_manifest(config)
    region = eval_pool.main_region_pairs(config, ft_manifest)
    coverage_pairs = frozenset(eval_pool.load_coverage_pairs(ft_manifest))
    candidates = leading_pair_candidates(region, offset=offset, main_radius=main_radius)
    # 主プールと同じ欄で、先頭の組の `interp` セルから逆順が K にある組を除く(ADR-134 決定1)。
    # `id` セルの候補は動かない。セルの選び方(ハッシュの小さい順)は候補の並びに依らない。
    mirror_record: dict[str, Any] | None = None
    if eval_pool.uses_interp_mirror_filter(config):
        removed = [pair for pair in candidates if is_interp_mirror(pair, coverage_pairs, main_radius)]
        n_before = len(candidates)
        candidates = without_interp_mirrors(candidates, coverage_pairs, main_radius)
        mirror_record = eval_pool.interp_mirror_removal_record(
            removed, n_before=n_before, n_after=len(candidates)
        )

    by_cell: dict[CompositionCell, list[Pair]] = {
        CompositionCell(coverage, carry): [] for coverage in KNOWN_LEVELS for carry in CARRY_LEVELS
    }
    for pair in candidates:
        cell = cell_of(pair, coverage_pairs, main_radius)
        if cell is None:
            raise ConfigError(f"先頭の組 {pair} がどのセルにも入らない")
        by_cell[cell].append(pair)

    selected = {
        cell: select_pairs(pairs, settings.n_per_cell, seed, cell=cell.name)
        for cell, pairs in by_cell.items()
    }
    if mirror_record is not None:
        mirror_record["mirror_in_K_by_cell"] = {
            cell.name: sum(1 for pair in pairs if mirror_in_k(pair, coverage_pairs))
            for cell, pairs in selected.items()
        }
    items = composition_items(
        selected,
        pool_id=pool_id,
        seed=seed,
        offset=offset,
        main_radius=main_radius,
        coverage_pairs=coverage_pairs,
        reference_lesions=reference_lesions,
    )
    return eval_pool.assemble(
        config,
        items,
        item_exclusions=excluded_operand_record({COMPOSITION_SOURCE: region}, axis="source_pool"),
        fill=composition_fill_record(
            settings,
            seed=seed,
            offset=offset,
            main_radius=main_radius,
            source_pool=source_pool,
            region=region,
            candidates=candidates,
            by_cell=by_cell,
            selected=selected,
            items=items,
            templates=composition.composition_templates(config),
            mirror_record=mirror_record,
        ),
    )


def composition_fill_record(
    settings: CompositionSettings,
    *,
    seed: int,
    offset: int,
    main_radius: int,
    source_pool: eval_pool.EvalPool,
    region: Sequence[Pair],
    candidates: Sequence[Pair],
    by_cell: Mapping[CompositionCell, Sequence[Pair]],
    selected: Mapping[CompositionCell, Sequence[Pair]],
    items: Sequence[Item],
    templates: Mapping[str, str],
    mirror_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """manifest の `fill` 欄(T1c の組をどう選んだかの記録)。

    答える問い: 「この T1c プールを、後から config と評価プールだけで再現できるか」

    `mirror_record` は `eval.interp_mirror_filter` が真のときだけ渡る(ADR-134)。偽なら鍵ごと
    書かない(パイロットの T1c の manifest を変えない)。
    """
    record: dict[str, Any] = {
        "method": FILL_COMPOSITION,
        "seed_consumed": True,
        "rule": (
            "PLAN-037 I2 / ADR-118 決定 D2〜D4。先頭の組 (a, b) を訓練域の領域から取り、"
            "a + b + offset ≤ main_radius・被演算子 ±1 を除く。(既知性 × 繰り上がり)の 4 セルから"
            "組の水準のハッシュの小さい順に取り、c は組のハッシュで決める"
        ),
        "constraint": {
            "first_pair": "a + b + offset ≤ main_radius(左から合成した 2 段目の組を訓練域に収める)",
            "offset": offset,
            "main_radius": main_radius,
            "third_operand_range": [THIRD_OPERAND_MIN, main_radius],
        },
        "n_per_cell": settings.n_per_cell,
        "prompt_template": dict(templates),
        "selection": {
            "hash": "sha256(canonical_json([tag, eval.pool_seed, a, b]))",
            "tag": SELECTION_TAG,
            "third_operand_tag": THIRD_OPERAND_TAG,
            "seed": seed,
            "order": "ハッシュの小さい順",
        },
        "source_pool_pairs_hash": source_pool.manifest["pairs_hash"],
        "reference_rules": list(composition.REFERENCE_RULES),
        "n_region_pairs": len(region),
        "n_candidates": len(candidates),
        "cells": {
            cell.name: {
                "n_candidates": len(by_cell[cell]),
                "pairs": [list(pair) for pair in pairs],
            }
            for cell, pairs in selected.items()
        },
        "first_pair_overlap_with_t1": first_pair_overlap_with_t1(selected, source_pool),
        "n_items_by_group": {composition.GROUP: len(items)},
        "n_items_by_cell": {cell.name: len(pairs) for cell, pairs in selected.items()},
    }
    if mirror_record is not None:
        record[eval_pool.INTERP_MIRROR_RECORD] = dict(mirror_record)
    return record


def composition_dir_name(pool_id: str) -> str:
    """T1c プールのディレクトリ名(元の評価プールの隣。既存のプールと混ぜない)。"""
    return f"{pool_id}{COMPOSITION_DIR_SUFFIX}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T1c 合成の探りの項目プール(PLAN-037 I2)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイルを書かずに項目の組み立てと manifest の中身だけ確かめる",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="出力先。既定は data/generated/battery/<pool_id>_t1c/",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    pool = build_composition_pool(config, eval_pool.build(config))

    if args.dry_run:
        print("=" * 72)
        print("--dry-run: 配線確認。**実験ではない。**ファイルは書いていない。")
        print("ここに出る数値は組合せ論的な計数であって実験結果ではない(CLAUDE.md §2)。")
        print("=" * 72)
        summary = eval_pool.dry_run_summary(pool)
        fill = pool.manifest["fill"]
        for key in ("n_region_pairs", "n_candidates", "n_items_by_cell", "first_pair_overlap_with_t1"):
            summary[key] = fill[key]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    out_dir = args.out_dir or eval_pool.OUTPUT_ROOT / composition_dir_name(
        str(pool.manifest["pool_id"])
    )
    eval_pool.write_pool(pool, out_dir)
    print(f"items.jsonl: {len(pool.items)} 項目 -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
