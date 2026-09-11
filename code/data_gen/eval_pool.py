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

**埋め方は2通りある**(2026-09-11。PLAN-023 手順3 / ADR-076):

  - **`fill_cells` の経路**(`eval.pool_items` が無い config。本番 `exp_phase1_main`)。
    `eval.cells` のセル表を `pool.fill_cells` で埋め、セル → 組 → 項目の行を作って
    明示リストと同じ生成器(`code/eval/battery/build.py`)に渡す。
    候補は **main 領域の訓練域の組**(`ft_data.py` と同じ関数・同じ引数で分割を再現し、
    FT manifest の `counterpart_region_hash` と照合する)と **`Q(M*)` の main 側**
    (組ごとのハッシュで 50:50)である(ADR-076 決定10 (iii))
  - **明示リストの経路**(`eval.pool_items` がある config。smoke 系)。
    ADR-033 決定4 の暫定の形であり、**サンプリングしない。**smoke は配線確認で
    FT データが小さく、主軸のセル表は埋まらないので、この経路を残した。
    `eval.cells` は宣言として manifest の `fill` に転記するだけである

セル表そのものは `infra/preflight.py` の検査8 も使う(`coverage: id` のセルの
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
from code.data_gen.hashing import files_block
from code.data_gen.battery_items import (
    SUPPORTED_GROUPS,
    Item,
    assert_unique_item_ids,
    pairs_of,
    write_items,
    write_manifest,
)
from code.data_gen.ft_data import indistinguishable_pairs_of, train_domain_pairs
from code.data_gen.pool import (
    COVERAGE_ID,
    POOL_MAIN,
    POOL_PILOT,
    Cell,
    Pair,
    build_manifest,
    carry_label,
    eligible_item_pairs,
    eligible_pairs,
    excluded_operand_record,
    fill_cells,
    id_cell_population,
    is_excluded_operand_pair,
    label_main_coverage,
    outside_domain_side,
    pairs_hash,
    split_pilot_main,
)
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.eval.battery.build import build_items_from_entries, entries_by_group, pair_of
from code.eval.battery.magnitude_sweep import quadrant_pairs
from code.lesion import (
    reference_lesions_from_config,
    specificity_reference_lesions_from_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "data" / "generated" / "battery"

# items.jsonl の名前。manifest の files ブロックが参照するので1箇所に置く。
ITEMS_JSONL_NAME = "items.jsonl"

# manifest の fill.method。明示リストは**サンプリングしていない**ことを記録する値
# (ADR-033 決定3)。fill_cells はセル表をシードで埋めた値(ADR-076 決定10)。
FILL_EXPLICIT_LIST = "explicit_list"
FILL_CELLS = "fill_cells"

# 候補の出どころ(manifest の item_exclusions.by_group の鍵。axis = candidate_source)。
SOURCE_MAIN_REGION = "main_region"
SOURCE_OUTSIDE_TRAINING_DOMAIN = "outside_training_domain"

# 明示リストの行のうち、群ごとの鍵(code/eval/battery/build.py の表)。
ENTRY_CATEGORY = "category"
ENTRY_THRESHOLD_OFFSET = "threshold_offset"

# config で category を**書いてはならない**群(build.py が止める)。
# bare_sum は表層が1種類、word_problem は組のハッシュで場面が決まる(PLAN-003 §4.3)。
GROUPS_WITHOUT_CATEGORY: frozenset[str] = frozenset(
    {numeric_sum.GROUP_BARE_SUM, numeric_sum.GROUP_WORD_PROBLEM}
)
# config で category を**書かねばならない**群。
GROUPS_WITH_CATEGORY: frozenset[str] = frozenset(
    {t3_comparison.GROUP, specificity_control.GROUP}
)


@dataclass(frozen=True)
class EvalPool:
    """書き出す直前の評価プール。"""

    items: list[Item]
    manifest: dict[str, Any]


def _optional_str(entry: Mapping[str, Any], key: str) -> str | None:
    value = entry.get(key)
    return None if value is None else str(value)


def load_cells(config: Mapping[str, Any]) -> list[Cell]:
    """eval.cells をセル表として読む(PLAN-001 §5.1、検査8)。

    答える問い: 「この config が宣言しているセル表は、形として成立しているか」

    読むのは、宣言が壊れていることをプール生成の時点で見つけるためでもある。
    `infra/preflight.py` まで持ち越すと、「セル表が壊れている」が「K が足りない」に
    化けて報告される。`group` / `category` は `fill_cells` の経路でだけ要る
    (`validate_fill_cells` が検査する)。
    """
    cells = [
        Cell(
            name=str(entry["name"]),
            coverage=str(entry["coverage"]),
            carry=_optional_str(entry, "carry"),
            n=int(entry["n"]),
            group=_optional_str(entry, "group"),
            category=_optional_str(entry, "category"),
        )
        for entry in require(config, "eval.cells")
    ]
    names = [cell.name for cell in cells]
    if len(set(names)) != len(names):
        raise ConfigError(f"eval.cells のセル名が重複している: {names}")
    return cells


def uses_explicit_list(config: Mapping[str, Any]) -> bool:
    """この config は明示リストの経路で埋めるか(モジュール冒頭の注記)。

    答える問い: 「`fill_cells` を呼ぶのか、`eval.pool_items` を列挙するのか」

    **`eval.pool_items` があるかどうかだけで決める。**本番 config からはこの欄を消した
    (ADR-033 決定4 の予告どおり)。manifest の `fill.method` にどちらを通ったかが残る。
    """
    return (config.get("eval") or {}).get("pool_items") is not None


def find_condition_manifest(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    """この実行の条件の FT データ manifest を、その在り処と一緒に引く。

    答える問い: 「この評価プールは、どの訓練被覆の上に建っているか。そのファイルはどれか」

    出どころを `data.matched_manifests` にしてあるのは、`data.manifest` の
    schema が別物だからである(あちらは `infra/preflight.py` の
    `check_data_manifest` が読む `files` の表を持つ形式で、`ft_data.py` が書く
    manifest とは違う)。**この実行の条件の manifest を名指しで引く。**
    条件間で K は同一のはず(PLAN-002 §3.4)だが、それはここで仮定せず
    照合は preflight の検査3拡張・検査10 に任せる。

    パスも返すのは ADR-076 決定12(E-5 (b))のためである —— 評価 run の
    `metrics.json` に「どの FT manifest の K か」を焼き込む。
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
            return Path(entry), manifest
    raise ConfigError(
        f"この実行の条件 {condition!r} の manifest が data.matched_manifests に無い。"
        "評価プールを、どの訓練被覆の上に建てればよいか決まらない(ADR-021 決定5)。"
    )


def load_condition_manifest(config: Mapping[str, Any]) -> dict[str, Any]:
    """この実行の条件の FT データ manifest を `data.matched_manifests` から引く。

    答える問い: 「この評価プールは、どの訓練被覆の上に建っているか」

    規則は `find_condition_manifest` にある。`code/analysis/frame.py` もこの関数を呼ぶ
    (ADR-062 決定5。規則を書き写すと片方だけが直る)。
    """
    return find_condition_manifest(config)[1]


def load_coverage_sums(manifest: Mapping[str, Any]) -> list[int]:
    """訓練被覆 K が実際に出した和の集合を FT データの manifest から読む。

    答える問い: 「t 水準の被覆ラベル(t_seen / t_unseen)を後から再現できるか」

    **ここで数え直さない**(ADR-021 決定5)。この量は `coverage_seed` に依存し、
    実験シードで動いてはならない。訓練側が1度だけ畳んだ値を転記する。
    自前で計算すると、K の抽出が変わったときに2つの記録が静かにずれる。
    """
    return [int(total) for total in manifest["coverage"]["coverage_sums"]]


def load_coverage_pairs(manifest: Mapping[str, Any]) -> list[Pair]:
    """訓練被覆 K の組そのものを FT データの manifest から読む。

    答える問い: 「`id` セルの母集団はどこから来るか」(ADR-034 リスク欄)

    和(`coverage_sums`)ではなく**組**が要るのは、`id` セルの母集団を数える
    には評価側の除外を組ごとに掛ける必要があるからである。
    """
    return [(int(a), int(b)) for a, b in manifest["coverage"]["pairs"]]


def candidate_pairs_by_group(
    entries_by_group_map: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, list[Pair]]:
    """群ごとの**候補**(除外を掛ける前)の順序対。

    答える問い: 「評価プールの被演算子分布は、何から何を落とした結果か」

    除外前の候補を返すのは `pool.excluded_operand_record` が「候補 n 件のうち
    m 件を落とした」を記録するためである(ADR-035 帰結)。除外後の集合を渡すと
    n_excluded が常に 0 になり、記録が意味を失う。

    **全群を返す。**ADR-035 決定3 で被演算子の除外は T2 限定ではなく
    全タスク型の項目規約になったので、T2 だけを数えると記録が実態から離れる。
    """
    return {
        group: [pair_of(entry) for entry in entries]
        for group, entries in entries_by_group_map.items()
    }


def build_group_items(
    config: Mapping[str, Any],
    entries_by_group_map: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    pool_id: str,
) -> dict[str, list[Item]]:
    """群ごとに項目を作る。**全群に**生成の前に被演算子の除外を掛ける。

    答える問い: 「明示リストのどの行が、どの群の項目になるか」

    **被演算子の除外は生成器に渡す前に掛ける**(ADR-035 決定3。ADR-032 決定4 を
    全タスク型に広げたもの)。`numeric_sum.build_word_problem_items` は除外対象の
    組が来たら例外で止まる —— 落とすのは候補の段階だという規約をあちらが型で
    守っているためである。

    **2026-09-01 まで T2 だけに掛かっていた**(ADR-032 決定4)。タスク型ごとに
    除外規則が違うと、被演算子分布がタスク型間で揃わず**主軸の交互作用そのものの
    解釈に穴が開く**(ADR-035 決定3 の根拠)。
    """
    lesions = reference_lesions_from_config(config)
    specificity_lesions = specificity_reference_lesions_from_config(config)
    items: dict[str, list[Item]] = {}
    for group, entries in entries_by_group_map.items():
        eligible = set(eligible_item_pairs([pair_of(entry) for entry in entries]))
        usable = [entry for entry in entries if pair_of(entry) in eligible]
        items[group] = build_items_from_entries(
            usable,
            group,
            pool_id=pool_id,
            lesions=lesions,
            specificity_lesions=specificity_lesions,
        )
    return items


def assert_no_excluded_operands(items: Sequence[Item]) -> None:
    """除外対象の被演算子を持つ項目がプールに残っていないか(ADR-035 決定3)。

    答える問い: 「除外は本当に全群に掛かったか」

    `build_group_items` が掛けた除外の**事後確認**である。群を1つ足したときに
    除外を通し忘れると、その群だけ被演算子分布が違うプールが静かに書き出される。
    """
    leaked = sorted(
        {pair for pair in (item.operands[:2] for item in items) if is_excluded_operand_pair(pair)}
    )
    if leaked:
        raise ConfigError(
            f"除外対象の被演算子を含む組 {leaked} が評価プールに残っている"
            "(ADR-035 決定3)。build_group_items の除外を通っていない群がある。"
        )


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


# --------------------------------------------------------------------------
# fill_cells の経路(PLAN-023 手順3。ADR-076 決定4・8・10)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FillCandidates:
    """`fill_cells` に渡す候補と、その来歴。

    答える問い: 「セルは、どの組の集合から、どの除外を掛けた残りで埋まるのか」
    """

    pairs: list[Pair]
    before_exclusion: dict[str, list[Pair]]
    record: dict[str, Any]


def main_region_pairs(config: Mapping[str, Any], ft_manifest: Mapping[str, Any]) -> list[Pair]:
    """訓練域のうち、このプールの側の領域を再現する(ADR-076 決定10 (iii))。

    答える問い: 「`id` / `interp` のセルは、訓練域のどの組から引いてよいか」

    **`code/data_gen/ft_data.py` の `generate` 手順1 と同じ関数・同じ引数で分割を
    再現し、FT manifest の `pool_split.counterpart_region_hash` と照合する。**
    違っていれば止める —— 候補を訓練域全体から渡すと、`label_main_coverage` は
    K に無い組をすべて `interp` と呼ぶので、pilot 領域の組が `interp` セルに入る
    (PLAN-023 A2。PLAN-002 §4.7 手順3 / PLAN-001 §4.6 は main 領域から引くことを要求する)。

    ついでに K がこの領域に収まることを確かめる(K は自分の領域から引かれる。§4.7)。
    """
    pool_id = require(config, "data.pool_id")
    split = ft_manifest["pool_split"]
    if split["pool_id"] != pool_id:
        raise ConfigError(
            f"FT manifest の pool_split.pool_id={split['pool_id']!r} が "
            f"data.pool_id={pool_id!r} と違う。別の側の訓練被覆の上にプールを建てている。"
        )
    regions = split_pilot_main(
        train_domain_pairs(
            require(config, "data.train_domain_min"), require(config, "data.train_domain_max")
        ),
        require(config, "data.pilot_train_region_size"),
        require(config, "data.pool_split_seed"),
    )
    counterpart = POOL_PILOT if pool_id == POOL_MAIN else POOL_MAIN
    recorded = split.get("counterpart_region_hash")
    recomputed = pairs_hash(regions[counterpart])
    if recorded != recomputed:
        raise ConfigError(
            f"再現した {counterpart} 領域のハッシュ {recomputed} が FT manifest の "
            f"pool_split.counterpart_region_hash={recorded} と違う。訓練域の分割を再現できて"
            "いない(data.pool_split_seed / pilot_train_region_size / train_domain_* を確かめる"
            "こと。ADR-076 決定10 (iii))。"
        )
    region = regions[pool_id]
    stray = sorted(set(load_coverage_pairs(ft_manifest)) - set(region))
    if stray:
        raise ConfigError(
            f"訓練被覆 K の組 {stray[:4]}(全 {len(stray)} 組)が {pool_id} 領域の外にある。"
            "K は自分の領域から引かれるはずである(PLAN-002 §4.7)。"
        )
    return region


def outside_domain_candidates(config: Mapping[str, Any], *, main_radius: int) -> list[Pair]:
    """訓練域の外の候補 = `Q(M*)` のうち、このプールの側の組(ADR-076 決定10 (iii))。

    答える問い: 「`extrap_magnitude` のセルは、どの組から引いてよいか」

    **`Q(M)` は桁数掃引と同じ関数で数える**(`magnitude_sweep.quadrant_pairs`)。
    `M*` はその掃引の Q(M) の腕で決まった(ADR-071 / ADR-074)ので、定義を
    書き直すと「M* を決めた母集団」と「プールが引く母集団」が2つになる。
    50:50 は組ごとのハッシュ(`pool.outside_domain_side`)で分ける。
    """
    radius = require(config, "eval.extrapolation_radius")
    pool_id = require(config, "data.pool_id")
    seed = require(config, "data.pool_split_seed")
    return [
        pair
        for pair in quadrant_pairs(radius, main_radius=main_radius)
        if outside_domain_side(pair, seed) == pool_id
    ]


def fill_candidates(
    config: Mapping[str, Any], ft_manifest: Mapping[str, Any]
) -> FillCandidates:
    """セルを埋める候補を組む(ADR-076 決定10 (iii))。

    答える問い: 「このプールのセルは、どの組から、どの除外を掛けた残りで埋まるか」

    除外は3段である。**`id_cell_population` と同じ3段を同じ順で掛ける**
    (偶然一致 / 規則どうしの判別不能 / 被演算子)。`id` セルの母集団の記録と
    実際に埋めた母集団がずれないようにするためである(ADR-034 リスク欄)。
    特異性対照のセルも同じ候補から引く —— 群ごとに被演算子分布を変えない(ADR-035 決定3)。
    """
    main_radius = require(config, "data.train_domain_max")
    region = main_region_pairs(config, ft_manifest)
    outside = outside_domain_candidates(config, main_radius=main_radius)
    lesions = reference_lesions_from_config(config)
    eligible = eligible_pairs(
        [*region, *outside],
        list(lesions.values()),
        indistinguishable_rule_pairs=indistinguishable_pairs_of(lesions),
    )
    eligible = eligible_item_pairs(eligible)

    coverage_pairs = frozenset(load_coverage_pairs(ft_manifest))
    strata: dict[str, int] = {}
    for pair in eligible:
        key = f"{label_main_coverage(pair, coverage_pairs, main_radius)}:{carry_label(*pair)}"
        strata[key] = strata.get(key, 0) + 1
    split = ft_manifest["pool_split"]
    record = {
        "note": "組合せ論的な計数であって実験結果ではない(CLAUDE.md §2)",
        SOURCE_MAIN_REGION: {
            "rule": "ft_data と同じ split_pilot_main を再現(ADR-076 決定10 (iii))",
            "n_pairs": len(region),
            "pool_split_seed": require(config, "data.pool_split_seed"),
            "pilot_train_region_size": require(config, "data.pilot_train_region_size"),
            "counterpart_region_hash_verified": split["counterpart_region_hash"],
        },
        SOURCE_OUTSIDE_TRAINING_DOMAIN: {
            "rule": (
                "Q(M*) = magnitude_sweep.quadrant_pairs のうち "
                "pool.outside_domain_side(sha256(canonical_json([pool_split_seed, a, b])) の偶奇)"
                " がこのプールの側の組(ADR-076 決定10 (iii))"
            ),
            "extrapolation_radius": require(config, "eval.extrapolation_radius"),
            "n_pairs": len(outside),
        },
        "exclusions": [
            "偶然一致(ADR-016 / PLAN-001 §4.3)",
            "規則どうしの判別不能(ADR-022 決定3)",
            "被演算子(ADR-035 決定3 / ADR-075 決定1)",
        ],
        "n_eligible": len(eligible),
        "n_eligible_by_stratum": dict(sorted(strata.items())),
    }
    return FillCandidates(
        pairs=eligible,
        before_exclusion={SOURCE_MAIN_REGION: region, SOURCE_OUTSIDE_TRAINING_DOMAIN: outside},
        record=record,
    )


def validate_fill_cells(cells: Sequence[Cell], batteries: Sequence[str]) -> None:
    """セル表が `fill_cells` の経路で項目にできる形か(PLAN-023 A4)。

    答える問い: 「どのセルが、どの群のどの category の項目になるかが決まっているか」

    **黙って補わない。**群や category の欠けを既定値で埋めると、セル表と項目の
    対応が config の外で決まってしまう(skill code-style §5)。
    """
    instructed = numeric_sum.GROUP_BARE_SUM_INSTRUCTED
    for cell in cells:
        if cell.group is None or cell.group not in batteries or cell.group == instructed:
            raise ConfigError(
                f"セル {cell.name!r} の group={cell.group!r} が eval.batteries {list(batteries)} に"
                f"無い(または {instructed!r})。指示付き T1 はセルにせず、T1 の `id` セルの組から"
                "作る(ADR-035 決定2 / ADR-076 決定8)。"
            )
        if cell.group in GROUPS_WITH_CATEGORY and cell.category is None:
            raise ConfigError(f"セル {cell.name!r}(群 {cell.group!r})に category が無い。")
        if cell.group in GROUPS_WITHOUT_CATEGORY and cell.category is not None:
            raise ConfigError(
                f"セル {cell.name!r}(群 {cell.group!r})に category を書かない"
                "(bare_sum は1種類、word_problem は組のハッシュで場面が決まる)。"
            )
        if cell.group == t3_comparison.GROUP:
            offsets = t3_comparison.allowed_offsets(t3_comparison.polarity_of(cell.category))
            if cell.n % len(offsets):
                raise ConfigError(
                    f"セル {cell.name!r} の n={cell.n} を閾値オフセット {list(offsets)} に"
                    "等分できない(ADR-076 決定4 = セル内で 20 / 20)。"
                )
    declared_groups = {cell.group for cell in cells}
    empty = [group for group in batteries if group != instructed and group not in declared_groups]
    if empty:
        raise ConfigError(f"eval.batteries の群 {empty} にセルが1つも無い。")
    if instructed in batteries and not instructed_source_cells(cells):
        raise ConfigError(
            f"{instructed!r} を回すのに、組の出どころ(bare_sum の `id` セル)が無い(ADR-035 決定2)。"
        )


def instructed_source_cells(cells: Sequence[Cell]) -> list[Cell]:
    """指示付き T1 の組を借りるセル = T1 の `id` セル(ADR-035 決定2 / ADR-076 決定8)。

    答える問い: 「指示付き T1 の 80 項目は、どのセルの組から作るか」

    **セルとして埋めない。**「T1 と同一の被演算子対」が定義なので、`fill_cells` の
    「組をセル間で再利用しない」規則と衝突させないため、埋めた後で借りる。
    """
    return [
        cell
        for cell in cells
        if cell.group == numeric_sum.GROUP_BARE_SUM and cell.coverage == COVERAGE_ID
    ]


def cell_entries(cell: Cell, pairs: Sequence[Pair]) -> list[dict[str, Any]]:
    """セルの組を、明示リストと同じ形の行にする(`code/eval/battery/build.py`)。

    答える問い: 「このセルの組は、どの群・どの category・どの閾値オフセットの項目になるか」

    **T3 / T1b の閾値オフセットは、組を引いた順に、その極性で認められた2つへ交互に配る**
    (ADR-076 決定4 = ★F131。新しい乱数は使わない)。`>` は {0, +1}、`<` は {+1, +2}
    (`t3_comparison.THRESHOLD_RULES`)。オフセット +1 / +2 は `t >= 2` を要求するが、
    主軸の組は被演算子 ±1 を除いた `a, b >= 2` なので必ず満たす。**満たさない組が来たら
    生成器(`t3_comparison.threshold_for`)が止める**(ほかのオフセットへ黙って回さない)。
    """
    if cell.group == t3_comparison.GROUP:
        offsets = t3_comparison.allowed_offsets(t3_comparison.polarity_of(cell.category))
        return [
            {
                "group": cell.group,
                "a": a,
                "b": b,
                ENTRY_CATEGORY: cell.category,
                ENTRY_THRESHOLD_OFFSET: offsets[index % len(offsets)],
            }
            for index, (a, b) in enumerate(pairs)
        ]
    if cell.group in GROUPS_WITH_CATEGORY:
        return [
            {"group": cell.group, "a": a, "b": b, ENTRY_CATEGORY: cell.category} for a, b in pairs
        ]
    return [{"group": cell.group, "a": a, "b": b} for a, b in pairs]


def filled_entries_by_group(
    cells: Sequence[Cell],
    assignment: Mapping[str, Sequence[Pair]],
    batteries: Sequence[str],
) -> dict[str, list[dict[str, Any]]]:
    """埋めたセルを群ごとの行にする。並びは `eval.batteries` → セルの宣言順 → 引いた順。

    答える問い: 「items.jsonl の各行は、どのセルのどの組から来たか」
    """
    by_group: dict[str, list[dict[str, Any]]] = {group: [] for group in batteries}
    for cell in cells:
        by_group[cell.group].extend(cell_entries(cell, assignment[cell.name]))
    instructed = numeric_sum.GROUP_BARE_SUM_INSTRUCTED
    if instructed in by_group:
        by_group[instructed] = [
            {"group": instructed, "a": a, "b": b}
            for cell in instructed_source_cells(cells)
            for a, b in assignment[cell.name]
        ]
    return by_group


def threshold_offset_counts(
    cells: Sequence[Cell], assignment: Mapping[str, Sequence[Pair]]
) -> dict[str, dict[str, int]]:
    """T3 / T1b のセルごとの閾値オフセットの内訳(manifest の記録。ADR-076 決定4)。"""
    counts: dict[str, dict[str, int]] = {}
    for cell in cells:
        if cell.group != t3_comparison.GROUP:
            continue
        tally: dict[str, int] = {}
        for entry in cell_entries(cell, assignment[cell.name]):
            key = str(entry[ENTRY_THRESHOLD_OFFSET])
            tally[key] = tally.get(key, 0) + 1
        counts[cell.name] = tally
    return counts


def cell_record(cell: Cell) -> dict[str, Any]:
    """セル1つを manifest に残す形にする。"""
    return {
        "name": cell.name,
        "group": cell.group,
        "category": cell.category,
        "coverage": cell.coverage,
        "carry": cell.carry,
        "n": cell.n,
    }


# --------------------------------------------------------------------------
# 組み立て
# --------------------------------------------------------------------------


def validated_batteries(config: Mapping[str, Any]) -> list[str]:
    """`eval.batteries` を読み、実装済みの群だけであることを確かめる。"""
    batteries = list(require(config, "eval.batteries"))
    unknown = [group for group in batteries if group not in SUPPORTED_GROUPS]
    if unknown:
        raise ConfigError(
            f"群 {unknown} の項目生成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
        )
    return batteries


def assemble(
    config: Mapping[str, Any],
    items: list[Item],
    *,
    item_exclusions: Mapping[str, Any],
    fill: Mapping[str, Any],
) -> EvalPool:
    """項目から manifest を組む(2つの経路で共通)。

    答える問い: 「この項目集合の来歴を、preflight が照合できる形で残せているか」
    """
    if not items:
        raise ConfigError("項目が1件も無い。項目の無いプールは書き出さない")
    assert_unique_item_ids(items)
    assert_no_excluded_operands(items)

    pool_id = require(config, "data.pool_id")
    pairs = sorted(pairs_of(items))
    main_radius = require(config, "data.train_domain_max")
    # M* が未決なら null が正しい記録である(smoke 系)。require を通すと
    # 「まだ決めていない」を「値を入れろ」と誤って要求することになる。
    eval_block = config.get("eval") or {}
    extrapolation_radius = eval_block.get("extrapolation_radius")
    check_within_main_domain(pairs, main_radius, extrapolation_radius)

    # `id` セルの母集団は K そのものではない(ADR-034 リスク欄)。何組から
    # 引かれるのかを**本番経路が数えて**残す。人間の手計算を転記しない。
    ft_manifest = load_condition_manifest(config)
    lesions = reference_lesions_from_config(config)
    id_population = id_cell_population(
        load_coverage_pairs(ft_manifest),
        list(lesions.values()),
        indistinguishable_rule_pairs=indistinguishable_pairs_of(lesions),
    )

    manifest = build_manifest(
        pool_id=pool_id,
        pairs=pairs,
        reference_rules=sorted(lesions),
        specificity_reference_rules=sorted(specificity_reference_lesions_from_config(config)),
        coverage_sums=load_coverage_sums(ft_manifest),
        seed=require(config, "eval.pool_seed"),
        main_radius=main_radius,
        extrapolation_radius=extrapolation_radius,
        extrapolation_run_id=eval_block.get("extrapolation_run_id"),
        counterpart_pool_id=POOL_PILOT if pool_id == POOL_MAIN else POOL_MAIN,
        # 相手側のプールはまだ書き出していない。PLAN-001 §4.6 の非交差検査は
        # 両方が存在してから掛ける。**存在しないものを 0 件として記録しない。**
        counterpart_hash=None,
        prompt_format_block=prompt_format.build_from_config(config),
        item_exclusions=item_exclusions,
        id_cell_population=id_population.record,
        fill=fill,
    )
    return EvalPool(items=items, manifest=manifest)


def build_explicit(config: Mapping[str, Any], batteries: Sequence[str]) -> EvalPool:
    """明示リスト(`eval.pool_items`)から評価プールを組む(ADR-033 決定4。smoke 系)。

    答える問い: 「config が列挙した項目の集合と、その来歴の記録は何か」
    """
    pool_id = require(config, "data.pool_id")
    entries = entries_by_group(config, "eval.pool_items")
    cells = load_cells(config)
    items_by_group = build_group_items(config, entries, pool_id=pool_id)
    items = [item for group in batteries for item in items_by_group[group]]
    if not items:
        raise ConfigError("eval.pool_items が空。項目の無いプールは書き出さない")
    return assemble(
        config,
        items,
        item_exclusions=excluded_operand_record(candidate_pairs_by_group(entries)),
        fill={
            "method": FILL_EXPLICIT_LIST,
            "seed_consumed": False,
            "reason": (
                "明示リストで埋めた(ADR-033 決定4)。smoke 系は配線確認であり、"
                "FT データが小さく主軸のセル表は埋まらない"
            ),
            "cells_declared": [
                {"name": c.name, "coverage": c.coverage, "carry": c.carry, "n": c.n} for c in cells
            ],
            "n_items_by_group": {group: len(items_by_group[group]) for group in batteries},
        },
    )


def build_filled(config: Mapping[str, Any], batteries: Sequence[str]) -> EvalPool:
    """セル表を `fill_cells` で埋めて評価プールを組む(PLAN-023 手順3。ADR-076)。

    答える問い: 「このセル表を、どの候補から、どのシードで埋めたか」
    """
    pool_id = require(config, "data.pool_id")
    cells = load_cells(config)
    validate_fill_cells(cells, batteries)
    ft_manifest = load_condition_manifest(config)
    candidates = fill_candidates(config, ft_manifest)
    seed = require(config, "eval.pool_seed")
    assignment = fill_cells(
        candidates.pairs,
        cells,
        coverage_pairs=frozenset(load_coverage_pairs(ft_manifest)),
        main_radius=require(config, "data.train_domain_max"),
        seed=seed,
    )
    entries = filled_entries_by_group(cells, assignment, batteries)
    items_by_group = {
        group: build_items_from_entries(
            entries[group],
            group,
            pool_id=pool_id,
            lesions=reference_lesions_from_config(config),
            specificity_lesions=specificity_reference_lesions_from_config(config),
        )
        for group in batteries
    }
    items = [item for group in batteries for item in items_by_group[group]]
    instructed = numeric_sum.GROUP_BARE_SUM_INSTRUCTED
    return assemble(
        config,
        items,
        item_exclusions=excluded_operand_record(
            candidates.before_exclusion, axis="candidate_source"
        ),
        fill={
            "method": FILL_CELLS,
            "seed_consumed": True,
            "rule": "ADR-017 / ADR-076 決定4・8・10(セルごとの乱数列 = pool.cell_rng)",
            "candidates": candidates.record,
            "cells_declared": [cell_record(cell) for cell in cells],
            "assignment": {name: [list(pair) for pair in pairs] for name, pairs in assignment.items()},
            "threshold_offsets": threshold_offset_counts(cells, assignment),
            "instructed_source_cells": (
                [cell.name for cell in instructed_source_cells(cells)]
                if instructed in batteries
                else []
            ),
            "n_items_by_group": {group: len(items_by_group[group]) for group in batteries},
            "n_items_by_cell": {name: len(pairs) for name, pairs in assignment.items()},
        },
    )


def build(config: Mapping[str, Any]) -> EvalPool:
    """config から評価プールを組む。

    答える問い: 「この config が宣言する項目集合と、その来歴の記録は何か」

    経路は `uses_explicit_list` が決める(モジュール冒頭の注記)。
    """
    batteries = validated_batteries(config)
    pool_id = require(config, "data.pool_id")
    if pool_id not in (POOL_MAIN, POOL_PILOT):
        raise ConfigError(f"data.pool_id={pool_id!r} は {POOL_MAIN!r} か {POOL_PILOT!r} である")
    if uses_explicit_list(config):
        return build_explicit(config, batteries)
    return build_filled(config, batteries)


def write_pool(pool: EvalPool, out_dir: Path) -> None:
    """items.jsonl と manifest.json を書く。

    **順序が意味を持つ。**items.jsonl を書き切ってから、そのバイト列を読み直して
    manifest の `files` に記録し、最後に manifest を書く(ADR-051)。
    訓練側(code/data_gen/ft_data.py:write_dataset)と同じ手順である ——
    infra/preflight.py の data manifest 検査は両方を同じ形で読む。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    write_items(out_dir / ITEMS_JSONL_NAME, pool.items)
    pool.manifest["files"] = files_block(out_dir, [ITEMS_JSONL_NAME])
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
        "id_cell_population": manifest["id_cell_population"],
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
