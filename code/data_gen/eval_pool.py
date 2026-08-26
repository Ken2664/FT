"""評価プール(項目 + manifest)を書き出す入口(PLAN-001 §4、ADR-017 / ADR-033)。

答える問い: 「評価に使う項目集合は何から作られたかを、preflight が後から検証できるか」

    python -m code.data_gen.eval_pool --config configs/smoke.yaml --dry-run

書き出すもの(既定は data/generated/battery/<pool_id>/):

    items.jsonl    1行1項目(code/data_gen/battery_items.py の schema)
    manifest.json  pool.build_manifest が組む記録

**この manifest が infra/preflight.py の検査6 の相手方である。**config の
`eval.anchor_manifest` がここを指し、`prompt_format.format_hash` を訓練側の
manifest と照合する(PLAN-002 §4.8.1)。書式は実験条件なので、ここで既定値を
作らない —— `prompt_format.build_from_config` が config から組む。

**サンプリングしない**(ADR-033 決定4)。項目は `eval.pool_items` の明示リストから
作る。理由は2つある:

  1. 被覆層(id / interp / extrap)のセルの埋め方が未決である(`CLAUDE.md` §8)
  2. **外挿域の上限 M* が未決である**(承認待ち-15。段階 C の実測で決まる)。
     `pool.extrapolation_pairs` は M* を要求するので、`extrap` セルは
     段階 A では原理的に埋まらない

`eval.cells`(セル表)は**宣言として読み、manifest の `fill` に転記するだけ**である。
セル表そのものは `infra/preflight.py` の検査8 が使う(`coverage: id` のセルの
`n` の合計を K の下限として数える)。

**import の向きについて**: 項目生成器は `code/eval/battery/` にある(PLAN-003 §7.1)。
このモジュールは生成の入口なので `code/data_gen/` に置き、そちらを import する。
逆向き(`code/eval/battery/*` → `code/data_gen/battery_items`)は既にあるが循環しない
—— このモジュールは誰からも import されない入口だからである。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.config import ConfigError, load_config, require
from code.data_gen import prompt_format
from code.data_gen.battery_items import (
    SUPPORTED_GROUPS,
    Item,
    assert_unique_item_ids,
    pairs_of,
    write_items,
    write_manifest,
)
from code.data_gen.ft_data import POOL_MAIN, POOL_PILOT
from code.data_gen.pool import Cell, Pair, build_manifest
from code.eval.battery import numeric_sum
from code.eval.battery.build import build_items_from_entries, entries_by_group, pair_of
from code.lesion import (
    reference_lesions_from_config,
    specificity_reference_lesions_from_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "data" / "generated" / "battery"

# manifest の fill.method。**サンプリングしていない**ことを記録する値
# (ADR-033 決定3)。fill_cells を呼ぶ経路ができたらここが変わる。
FILL_EXPLICIT_LIST = "explicit_list"


@dataclass(frozen=True)
class EvalPool:
    """書き出す直前の評価プール。"""

    items: list[Item]
    manifest: dict[str, Any]


def load_cells(config: Mapping[str, Any]) -> list[Cell]:
    """eval.cells をセル表として読む(PLAN-001 §5.1、検査8)。

    答える問い: 「この config が宣言しているセル表は、形として成立しているか」

    **ここでセルを埋めない**(ADR-033 決定4)。読むのは、宣言が壊れていることを
    プール生成の時点で見つけるためである。`infra/preflight.py` まで持ち越すと、
    「セル表が壊れている」が「K が足りない」に化けて報告される。
    """
    cells = [
        Cell(
            name=str(entry["name"]),
            coverage=str(entry["coverage"]),
            carry=None if entry.get("carry") is None else str(entry["carry"]),
            n=int(entry["n"]),
        )
        for entry in require(config, "eval.cells")
    ]
    names = [cell.name for cell in cells]
    if len(set(names)) != len(names):
        raise ConfigError(f"eval.cells のセル名が重複している: {names}")
    return cells


def load_coverage_sums(config: Mapping[str, Any]) -> list[int]:
    """訓練被覆 K が実際に出した和の集合を FT データの manifest から読む。

    答える問い: 「t 水準の被覆ラベル(t_seen / t_unseen)を後から再現できるか」

    **ここで数え直さない**(ADR-021 決定5)。この量は `coverage_seed` に依存し、
    実験シードで動いてはならない。訓練側が1度だけ畳んだ値を転記する。
    自前で計算すると、K の抽出が変わったときに2つの記録が静かにずれる。

    出どころを `data.matched_manifests` にしてあるのは、`data.manifest` の
    schema が別物だからである(あちらは `infra/preflight.py` の
    `check_data_manifest` が読む `files` の表を持つ形式で、`ft_data.py` が書く
    manifest とは違う)。**この実行の条件の manifest を名指しで引く。**
    条件間で K は同一のはず(PLAN-002 §3.4)だが、それはここで仮定せず
    照合は preflight の検査3拡張・検査10 に任せる。
    """
    condition = require(config, "lesion.condition")
    for entry in require(config, "data.matched_manifests"):
        path = Path(entry)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.exists():
            raise ConfigError(
                f"data.matched_manifests が指す FT データの manifest が無い: {path}。"
                "評価プールは FT データの後に作る(ADR-017 案A)。先に "
                "python -m code.data_gen.ft_data --config <config> --out-dir <dir> を回すこと。"
            )
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["lesion"]["condition"] == condition:
            return [int(total) for total in manifest["coverage"]["coverage_sums"]]
    raise ConfigError(
        f"この実行の条件 {condition!r} の manifest が data.matched_manifests に無い。"
        "評価プールの被覆和を、どの訓練被覆から取ればよいか決まらない(ADR-021 決定5)。"
    )


def word_problem_candidates(
    entries_by_group_map: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[Pair]:
    """T2 のセルを埋める**候補**(除外を掛ける前)の順序対。

    答える問い: 「文章題の被演算子分布は、何から何を落とした結果か」

    除外前の候補を返すのは `numeric_sum.word_problem_exclusion_record` が
    「候補 n 件のうち m 件を落とした」を記録するためである(ADR-032 決定4)。
    除外後の集合を渡すと n_excluded が常に 0 になり、記録が意味を失う。
    """
    entries = entries_by_group_map.get(numeric_sum.GROUP_WORD_PROBLEM, ())
    return [pair_of(entry) for entry in entries]


def build_group_items(
    config: Mapping[str, Any],
    entries_by_group_map: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    pool_id: str,
) -> dict[str, list[Item]]:
    """群ごとに項目を作る。T2 だけ生成の前に除外を掛ける。

    答える問い: 「明示リストのどの行が、どの群の項目になるか」

    **被演算子 1 の除外は生成器に渡す前に掛ける**(ADR-032 決定4)。
    `numeric_sum.build_word_problem_items` は除外対象の組が来たら例外で止まる
    —— 落とすのは候補の段階だという規約をあちらが型で守っているためである。
    """
    lesions = reference_lesions_from_config(config)
    specificity_lesions = specificity_reference_lesions_from_config(config)
    items: dict[str, list[Item]] = {}
    for group, entries in entries_by_group_map.items():
        usable = list(entries)
        if group == numeric_sum.GROUP_WORD_PROBLEM:
            eligible = set(numeric_sum.eligible_word_problem_pairs([pair_of(e) for e in entries]))
            usable = [entry for entry in entries if pair_of(entry) in eligible]
        items[group] = build_items_from_entries(
            usable,
            group,
            pool_id=pool_id,
            lesions=lesions,
            specificity_lesions=specificity_lesions,
        )
    return items


def check_within_main_domain(pairs: Sequence[Pair], main_radius: int, declared: int | None) -> None:
    """主域の外の組が、外挿域の上限 M* の宣言なしに混ざっていないか。

    答える問い: 「このプールは、まだ決まっていない外挿域に踏み込んでいないか」

    M* は段階 C の実測で決まる(PLAN-001 §4.1.1、承認待ち-15)。決まる前に
    主域の外の組をプールに入れると、後から M* が確定したときに
    「その組が外挿域に入るか」が変わり、被覆ラベルが遡って動く。
    """
    if declared is not None:
        return
    outside = sorted({pair for pair in pairs if max(abs(pair[0]), abs(pair[1])) > main_radius})
    if outside:
        shown = outside[:4]
        raise ConfigError(
            f"eval.extrapolation_radius(M*)が未決のまま、主域(半径 {main_radius})の外の組 "
            f"{shown}(全 {len(outside)} 組)がプールに入っている。"
            "M* は段階 C の実測で決める(PLAN-001 §4.1.1)。決め打ちにしないこと。"
        )


def build(config: Mapping[str, Any]) -> EvalPool:
    """config から評価プールを組む。

    答える問い: 「この config が宣言する項目集合と、その来歴の記録は何か」
    """
    batteries = list(require(config, "eval.batteries"))
    unknown = [group for group in batteries if group not in SUPPORTED_GROUPS]
    if unknown:
        raise ConfigError(
            f"群 {unknown} の項目生成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
        )
    pool_id = require(config, "data.pool_id")
    if pool_id not in (POOL_MAIN, POOL_PILOT):
        raise ConfigError(f"data.pool_id={pool_id!r} は {POOL_MAIN!r} か {POOL_PILOT!r} である")

    entries = entries_by_group(config, "eval.pool_items")
    cells = load_cells(config)
    items_by_group = build_group_items(config, entries, pool_id=pool_id)
    items = [item for group in batteries for item in items_by_group[group]]
    if not items:
        raise ConfigError("eval.pool_items が空。項目の無いプールは書き出さない")
    assert_unique_item_ids(items)

    pairs = sorted(pairs_of(items))
    main_radius = require(config, "data.train_domain_max")
    # M* は未決なので null が正しい記録である(承認待ち-15)。require を通すと
    # 「まだ決めていない」を「値を入れろ」と誤って要求することになる。
    eval_block = config.get("eval") or {}
    extrapolation_radius = eval_block.get("extrapolation_radius")
    check_within_main_domain(pairs, main_radius, extrapolation_radius)

    manifest = build_manifest(
        pool_id=pool_id,
        pairs=pairs,
        reference_rules=sorted(reference_lesions_from_config(config)),
        specificity_reference_rules=sorted(specificity_reference_lesions_from_config(config)),
        coverage_sums=load_coverage_sums(config),
        seed=require(config, "eval.pool_seed"),
        main_radius=main_radius,
        extrapolation_radius=extrapolation_radius,
        extrapolation_run_id=eval_block.get("extrapolation_run_id"),
        counterpart_pool_id=POOL_PILOT if pool_id == POOL_MAIN else POOL_MAIN,
        # 相手側のプールはまだ書き出していない。PLAN-001 §4.6 の非交差検査は
        # 両方が存在してから掛ける。**存在しないものを 0 件として記録しない。**
        counterpart_hash=None,
        prompt_format_block=prompt_format.build_from_config(config),
        item_exclusions=numeric_sum.word_problem_exclusion_record(word_problem_candidates(entries)),
        fill={
            "method": FILL_EXPLICIT_LIST,
            "seed_consumed": False,
            "reason": (
                "セルの充填方針が未決であり、外挿域の上限 M* も未決なので "
                "extrap セルは原理的に埋まらない(ADR-033 決定4)"
            ),
            "cells_declared": [
                {"name": c.name, "coverage": c.coverage, "carry": c.carry, "n": c.n} for c in cells
            ],
            "n_items_by_group": {group: len(items_by_group[group]) for group in batteries},
        },
    )
    return EvalPool(items=items, manifest=manifest)


def write_pool(pool: EvalPool, out_dir: Path) -> None:
    """items.jsonl と manifest.json を書く。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    write_items(out_dir / "items.jsonl", pool.items)
    write_manifest(out_dir / "manifest.json", pool.manifest)


def dry_run_summary(pool: EvalPool) -> dict[str, Any]:
    """配線確認の要約(**実験結果ではない**)。

    答える問い: 「config が読めて、4群の項目が組めて、manifest が埋まっているか」
    """
    manifest = pool.manifest
    return {
        "pool_id": manifest["pool_id"],
        "n_items": len(pool.items),
        "n_items_by_group": manifest["fill"]["n_items_by_group"],
        "n_pairs": manifest["n_pairs"],
        "pairs_hash": manifest["pairs_hash"],
        "reference_rules": manifest["reference_rules"],
        "specificity_reference_rules": manifest["specificity_reference_rules"],
        "format_hash": manifest["prompt_format"]["format_hash"],
        "item_exclusions": manifest["item_exclusions"],
        "fill_method": manifest["fill"]["method"],
        "extrapolation_radius": manifest["extrapolation_radius"],
        "first_items": [item.as_dict() for item in pool.items[:3]],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="評価プールの生成(PLAN-001 §4)")
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
        help="出力先。既定は data/generated/battery/<pool_id>/",
    )
    args = parser.parse_args(argv)

    pool = build(load_config(args.config))

    if args.dry_run:
        print("=" * 72)
        print("--dry-run: 配線確認。**実験ではない。**ファイルは書いていない。")
        print("ここに出る数値は組合せ論的な計数であって実験結果ではない(CLAUDE.md §2)。")
        print("=" * 72)
        print(json.dumps(dry_run_summary(pool), ensure_ascii=False, indent=2))
        return 0

    out_dir = args.out_dir or OUTPUT_ROOT / str(pool.manifest["pool_id"])
    write_pool(pool, out_dir)
    print(f"items.jsonl: {len(pool.items)} 項目 -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
