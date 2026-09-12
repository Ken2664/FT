"""閾値掃引(R8・S)の項目プール(PLAN-026 I3。ADR-030 決定2〜4 / ADR-079 決定4 / ADR-080 決定3)。

答える問い: 「掃引の項目は、決まった組から、決まった件数で、固定オフセットの項目と別に作られているか」

ここで固定する最重要の性質:
  - **件数**: R8 = T3 4,080 + T1b 4,080 = 8,160 / S の基本集合 = T3 1,200 + T1b 1,200
    (PLAN-026 §3.2・§3.7。**組合せ論的な帰結であって実験結果ではない**)
  - **組の選び方が決定的**: 候補の並び・θ の水準集合に依らず、組の水準のハッシュだけで決まる。
    **S の組は R8 の組と同じ**で、S の項目は R8 の項目の部分集合
  - **同じ組を両極性で尋ねる**: 組は極性を併合した (タスク型 × 既知性 × carry) セルから引く
  - **閾値は両極性とも T = t + θ**、判別可能性は問わない(非判別項目を含む = 4 値分解に入れない)
  - **コミット済みの manifest が config から再現できる**
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.pool import Cell
from code.eval.battery import t3_comparison
from code.lesion import reference_lesions_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = REPO_ROOT / "configs" / "exp_order6b_pilot.yaml"
ARMS = ("r8", "s")

# ADR-030 決定2(17 水準)と ADR-079 決定4(S の 5 水準)の転記。config がこれとずれたら落とす。
R8_OFFSETS = list(range(-3, 14))
S_OFFSETS = [-3, -2, 3, 7, 13]


def _cell(name: str, category: str, coverage: str, carry: str | None) -> Cell:
    return Cell(
        name=name,
        coverage=coverage,
        carry=carry,
        n=4,
        group=t3_comparison.GROUP,
        category=category,
    )


def _block(**overrides: Any) -> dict[str, Any]:
    block: dict[str, Any] = {
        "task_types": ["t3", "t1b"],
        "pairs_per_cell": 20,
        "offsets": {"r8": R8_OFFSETS, "s": S_OFFSETS},
    }
    block.update(overrides)
    return {"eval": {"threshold_sweep": block}}


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_pilot_config_declares_the_adr_levels() -> None:
    """★config の θ・組の数・タスク型が ADR-030 決定2〜4 / ADR-079 決定4 と同じ。"""
    config = load_config(PILOT_CONFIG)
    r8 = sweep_pool.load_sweep_settings(config, "r8")
    s = sweep_pool.load_sweep_settings(config, "s")
    assert list(r8.offsets) == R8_OFFSETS
    assert list(s.offsets) == S_OFFSETS
    assert r8.pairs_per_cell == s.pairs_per_cell == 20
    assert r8.task_types == s.task_types == (t3_comparison.T3, t3_comparison.T1B)


def test_main_config_has_no_sweep_block() -> None:
    """掃引の欄は順6b の config にだけある(本番の R8 は Phase 1 で別に決める)。"""
    main = load_config(REPO_ROOT / "configs" / "exp_phase1_main.yaml")
    assert "threshold_sweep" not in main["eval"]


@pytest.mark.parametrize(
    ("overrides", "arm", "message"),
    [
        ({}, "r9", "腕"),
        ({"offsets": {"r8": [0, 0, 1]}}, "r8", "狭義の増加列"),
        ({"offsets": {"r8": [1, 0]}}, "r8", "狭義の増加列"),
        ({"offsets": {"r8": [0, True]}}, "r8", "整数の列"),
        ({"offsets": {"r8": []}}, "r8", "整数の列"),
        ({"pairs_per_cell": 0}, "r8", "正の整数"),
        ({"pairs_per_cell": None}, "r8", "正の整数"),
        ({"task_types": ["t3", "t1"]}, "r8", "task_types"),
        ({"task_types": ["t3", "t3"]}, "r8", "task_types"),
        ({"task_types": []}, "r8", "task_types"),
    ],
)
def test_settings_refuse_broken_blocks(overrides: dict[str, Any], arm: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        sweep_pool.load_sweep_settings(_block(**overrides), arm)


def test_settings_require_the_block() -> None:
    with pytest.raises(ConfigError):
        sweep_pool.load_sweep_settings({"eval": {}}, "r8")


# --------------------------------------------------------------------------
# セルの併合
# --------------------------------------------------------------------------


def test_sweep_cells_merge_the_two_polarities() -> None:
    """★gt・lt の 2 セルが 1 つの (タスク型 × 既知性 × carry) セルになる。ほかの群は無視する。"""
    cells = [
        Cell(name="t1_id_carry", coverage="id", carry="carry", n=4, group="bare_sum"),
        _cell("t1b_gt_id_carry", "t1b_gt", "id", "carry"),
        _cell("t3_gt_id_carry", "t3_gt", "id", "carry"),
        _cell("t3_gt_id_nocarry", "t3_gt", "id", "nocarry"),
        _cell("t3_lt_id_carry", "t3_lt", "id", "carry"),
        _cell("t3_lt_id_nocarry", "t3_lt", "id", "nocarry"),
        _cell("t1b_lt_id_carry", "t1b_lt", "id", "carry"),
    ]
    merged = sweep_pool.sweep_cells(cells, ["t3", "t1b"])
    assert [cell.name for cell in merged] == ["t3_id_carry", "t3_id_nocarry", "t1b_id_carry"]
    assert merged[0].source_cells == ("t3_gt_id_carry", "t3_lt_id_carry")
    assert merged[2].source_cells == ("t1b_gt_id_carry", "t1b_lt_id_carry")
    # task_types に無いタスク型のセルは使わない
    assert [cell.task_type for cell in sweep_pool.sweep_cells(cells, ["t3"])] == ["t3", "t3"]


def test_sweep_cells_refuse_a_missing_polarity() -> None:
    """片方の極性しか無いセルは止める(同じ組を両極性で尋ねる前提が崩れる)。"""
    cells = [_cell("t3_gt_id_carry", "t3_gt", "id", "carry")]
    with pytest.raises(ConfigError, match="両極性"):
        sweep_pool.sweep_cells(cells, ["t3"])


def test_sweep_cells_refuse_a_duplicated_polarity() -> None:
    cells = [
        _cell("a", "t3_gt", "id", "carry"),
        _cell("b", "t3_gt", "id", "carry"),
        _cell("c", "t3_lt", "id", "carry"),
    ]
    with pytest.raises(ConfigError, match="2 つある"):
        sweep_pool.sweep_cells(cells, ["t3"])


def test_sweep_cells_refuse_a_task_type_without_cells() -> None:
    cells = [_cell("g", "t3_gt", "id", "carry"), _cell("l", "t3_lt", "id", "carry")]
    with pytest.raises(ConfigError, match="t1b"):
        sweep_pool.sweep_cells(cells, ["t3", "t1b"])


# --------------------------------------------------------------------------
# 組の選び方
# --------------------------------------------------------------------------


CANDIDATES = [(a, b) for a in range(2, 12) for b in range(20, 28)]


def test_select_pairs_ignores_the_candidate_order() -> None:
    """★候補の並びに依らない(ハッシュで並べ直す)。"""
    shuffled = list(CANDIDATES)
    random.Random(0).shuffle(shuffled)
    assert sweep_pool.select_pairs(CANDIDATES, 20, 3) == sweep_pool.select_pairs(shuffled, 20, 3)


def test_select_pairs_takes_the_smallest_hashes() -> None:
    """選ばれた組のハッシュは、選ばれなかったどの組のハッシュよりも小さい。"""
    chosen = sweep_pool.select_pairs(CANDIDATES, 20, 3)
    assert len(set(chosen)) == 20
    rest = set(CANDIDATES) - set(chosen)
    assert max(sweep_pool.selection_key(p, 3) for p in chosen) < min(
        sweep_pool.selection_key(p, 3) for p in rest
    )


def test_select_pairs_depends_on_the_pool_seed() -> None:
    """ハッシュは eval.pool_seed を入れる(新しいシードを足さない。config を替えれば組も替わる)。"""
    assert sweep_pool.select_pairs(CANDIDATES, 20, 3) != sweep_pool.select_pairs(CANDIDATES, 20, 4)


def test_select_pairs_refuses_too_few_or_duplicated_candidates() -> None:
    with pytest.raises(ConfigError, match="しか無い"):
        sweep_pool.select_pairs(CANDIDATES[:5], 20, 3)
    with pytest.raises(ConfigError, match="2 回"):
        sweep_pool.select_pairs(CANDIDATES + CANDIDATES[:1], 20, 3)


# --------------------------------------------------------------------------
# 項目
# --------------------------------------------------------------------------


def test_sweep_items_use_t_plus_theta_for_both_polarities() -> None:
    """★閾値は両極性とも T = t + θ(ADR-030 決定2 / `sweep_threshold`)。非判別の θ も作る。"""
    cell = sweep_pool.SweepCell("t3", "id", "carry", ("t3_gt_id_carry", "t3_lt_id_carry"))
    pairs = [(30, 42), (5, 60)]
    lesions = reference_lesions_from_config(load_config(PILOT_CONFIG))
    items = sweep_pool.sweep_items({cell: pairs}, [-3, 0, 13], pool_id="pilot", lesions=lesions)
    assert len(items) == len(pairs) * 2 * 3
    for item in items:
        a, b = item.operands
        assert item.params["threshold"] == a + b + item.params["threshold_offset"]
        assert item.group == t3_comparison.GROUP
        assert item.pool_id == "pilot"
    assert Counter(t3_comparison.polarity_of(item.category) for item in items) == {"gt": 6, "lt": 6}
    # gt の θ = −3 は真値も p2 の規則値も Yes(判別できない)。これが作られている = 強制が外れている
    p2 = lesions["p2"]
    assert any(not t3_comparison.is_discriminating(item, p2) for item in items)


# --------------------------------------------------------------------------
# パイロット用プールから組む(PLAN-026 §4.2)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pilot_config() -> dict[str, Any]:
    return load_config(PILOT_CONFIG)


@pytest.fixture(scope="module")
def source_pool(pilot_config: dict[str, Any]) -> eval_pool.EvalPool:
    """pilot の config からパイロット用プールを組む(約 5 秒)。"""
    return eval_pool.build(pilot_config)


@pytest.fixture(scope="module")
def sweep_pools(
    pilot_config: dict[str, Any], source_pool: eval_pool.EvalPool
) -> dict[str, eval_pool.EvalPool]:
    return {arm: sweep_pool.build_sweep_pool(pilot_config, source_pool, arm) for arm in ARMS}


def _count(pool: eval_pool.EvalPool) -> Counter[str]:
    return Counter(t3_comparison.task_type_of(item.category) for item in pool.items)


def test_r8_counts(sweep_pools: dict[str, eval_pool.EvalPool]) -> None:
    """★R8 = T3 4,080 + T1b 4,080 = 8,160(ADR-030 決定4。組合せ論的な帰結)。"""
    pool = sweep_pools["r8"]
    assert len(pool.items) == 8_160
    assert _count(pool) == {"t3": 4_080, "t1b": 4_080}
    assert pool.manifest["fill"]["n_items_by_task_type"] == {"t3": 4_080, "t1b": 4_080}


def test_s_counts(sweep_pools: dict[str, eval_pool.EvalPool]) -> None:
    """★S の基本集合 = T3 1,200 + T1b 1,200(ADR-079 決定4。① と (d) の文面は I6・I8 で被せる)。"""
    pool = sweep_pools["s"]
    assert len(pool.items) == 2_400
    assert _count(pool) == {"t3": 1_200, "t1b": 1_200}


@pytest.mark.parametrize("arm", ARMS)
def test_every_cell_polarity_and_theta_has_the_same_pairs(
    sweep_pools: dict[str, eval_pool.EvalPool], arm: str
) -> None:
    """★(セル × 極性 × θ)ごとに同じ 20 組。両極性で同じ組を尋ねる。"""
    pool = sweep_pools[arm]
    cells = pool.manifest["fill"]["cells"]
    offsets = pool.manifest["fill"]["threshold_offsets"]
    # 組はセル間で再利用されない(fill_cells)ので、組だけで併合したセルが決まる
    cell_of_pair = {tuple(pair): name for name, cell in cells.items() for pair in cell["pairs"]}
    assert len(cell_of_pair) == sum(len(cell["pairs"]) for cell in cells.values())
    seen: dict[tuple[str, str, int], set[tuple[int, int]]] = {}
    for item in pool.items:
        pair = (item.operands[0], item.operands[1])
        cell_name = cell_of_pair[pair]
        assert cell_name.startswith(t3_comparison.task_type_of(item.category) + "_")
        key = (cell_name, t3_comparison.polarity_of(item.category), item.params["threshold_offset"])
        seen.setdefault(key, set()).add(pair)
    assert len(seen) == len(cells) * 2 * len(offsets)
    for (cell_name, _, _), pairs in seen.items():
        assert pairs == {tuple(pair) for pair in cells[cell_name]["pairs"]}
        assert len(pairs) == 20


def test_pairs_come_from_the_merged_source_cells(
    sweep_pools: dict[str, eval_pool.EvalPool], source_pool: eval_pool.EvalPool
) -> None:
    """★20 組は gt・lt の 2 セル(計 80 組)のハッシュの小さい順(関数を通さずに数え直す)。"""
    assignment = source_pool.manifest["fill"]["assignment"]
    seed = source_pool.manifest["seed"]
    cells = sweep_pools["r8"].manifest["fill"]["cells"]
    assert len(cells) == 12  # 2 タスク型 × 3 既知性 × carry 2
    for name, cell in cells.items():
        gt_cell, lt_cell = cell["source_cells"]
        assert gt_cell.replace("_gt_", "_") == lt_cell.replace("_lt_", "_") == name
        candidates = [tuple(p) for src in (gt_cell, lt_cell) for p in assignment[src]]
        assert cell["n_candidates"] == len(candidates) == 80
        expected = sorted(candidates, key=lambda p: (sweep_pool.selection_key(p, seed), p))[:20]
        assert [tuple(p) for p in cell["pairs"]] == expected


def test_s_uses_the_same_pairs_and_is_a_subset_of_r8(
    sweep_pools: dict[str, eval_pool.EvalPool],
) -> None:
    """★S の組は R8 の組と同じ(PLAN-026 §3.7「R8 と同じ 20 組」)。S の項目は R8 の部分集合。"""
    r8, s = sweep_pools["r8"], sweep_pools["s"]
    assert s.manifest["fill"]["cells"] == r8.manifest["fill"]["cells"]
    assert s.manifest["pairs_hash"] == r8.manifest["pairs_hash"]
    assert {item.item_id for item in s.items} < {item.item_id for item in r8.items}


def test_building_twice_gives_the_same_pool(
    pilot_config: dict[str, Any],
    source_pool: eval_pool.EvalPool,
    sweep_pools: dict[str, eval_pool.EvalPool],
) -> None:
    """組の選び方も項目の並びも決定的(乱数を使わない)。"""
    again = sweep_pool.build_sweep_pool(pilot_config, source_pool, "r8")
    assert [item.as_dict() for item in again.items] == [
        item.as_dict() for item in sweep_pools["r8"].items
    ]
    assert again.manifest == sweep_pools["r8"].manifest


def test_sweep_pairs_stay_inside_the_pilot_pool(
    sweep_pools: dict[str, eval_pool.EvalPool], source_pool: eval_pool.EvalPool
) -> None:
    """掃引の組はパイロット用プールの比較の組の部分集合(主プールと交わらない性質を引き継ぐ)。"""
    pilot_pairs = {tuple(pair) for pair in source_pool.manifest["pairs"]}
    for pool in sweep_pools.values():
        assert {tuple(pair) for pair in pool.manifest["pairs"]} <= pilot_pairs
        assert pool.manifest["pool_id"] == "pilot"
        assert pool.manifest["fill"]["source_pool_pairs_hash"] == source_pool.manifest["pairs_hash"]


def test_sweep_pool_refuses_an_explicit_list_source(pilot_config: dict[str, Any]) -> None:
    """明示リストの経路で埋めたプールにはセルの割当が無いので止める。"""
    fake = eval_pool.EvalPool(items=[], manifest={"fill": {"method": eval_pool.FILL_EXPLICIT_LIST}})
    with pytest.raises(ConfigError, match="fill_cells"):
        sweep_pool.build_sweep_pool(pilot_config, fake, "r8")


@pytest.mark.parametrize("arm", ARMS)
def test_committed_manifest_matches_the_rebuild(
    sweep_pools: dict[str, eval_pool.EvalPool], arm: str
) -> None:
    """★コミット済みの掃引プールの manifest が config から再現できる(別ディレクトリにある)。"""
    out_dir = eval_pool.OUTPUT_ROOT / sweep_pool.sweep_dir_name("pilot", arm)
    assert out_dir != eval_pool.OUTPUT_ROOT / "pilot"
    committed = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    committed.pop("files")
    rebuilt = json.loads(json.dumps(sweep_pools[arm].manifest, ensure_ascii=False))
    assert rebuilt == committed
