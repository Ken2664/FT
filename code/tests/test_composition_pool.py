"""T1c の項目プール(code/data_gen/composition_pool.py)。PLAN-037 I2 / ADR-118。

答える問い: 「T1c の項目は、訓練域の中の先頭の組から、決まった件数で、既存のプールと別に作られているか」

固定する性質:
  - **D2 (b)**: a + b + offset ≤ main_radius が境界で入り、+1 で入らない。被演算子 ±1 は 3 つとも除く
  - **件数の事実**(組合せ論的な計数であって実験結果ではない。PLAN-037 §4.1 D2 の補足):
    先頭の組の候補は主 897 組(carry 167)/ pilot 903 組(carry 157)
  - **選び方が決定的**: 候補の並びに依らず、同じ config から 1 バイトも同じプールが出る
  - **件数は null なら止まる**(ADR-118 決定3)。足りなければ黙って減らさず止まる
  - **既存の評価プールは変わらない**(主・pilot の `pairs_hash` が commit 済みの manifest と一致)
"""

from __future__ import annotations

import copy
import functools
import json
import random
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.data_gen import composition_pool as cp
from code.data_gen import eval_pool
from code.data_gen.pool import (
    ANSWER_IN,
    COVERAGE_ID,
    COVERAGE_INTERP,
    carry_label,
    is_excluded_operand_pair,
    pools_are_disjoint,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = REPO_ROOT / "configs" / "exp_order6b_pilot.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"

# PLAN-037 §4.1 D2 の補足の転記(その133 に数えた)。config や manifest がずれたら落とす。
EXPECTED_CANDIDATES = {
    "pilot": {"nocarry": 746, "carry": 157},
    "main": {"nocarry": 730, "carry": 167},
}
OFFSET = 2
MAIN_RADIUS = 99
# 機構を見るための小さい件数。**実験の件数ではない**(件数は S5 で人間が決める)。
SMALL_N = 5


@functools.cache
def source_pool(config_path: Path) -> eval_pool.EvalPool:
    """元の評価プール。組み立てが遅い(約 10 秒)ので config ごとに 1 度だけ作る。

    `eval.composition` を足しても評価プールは変わらない(T1c は別のプール)ので、
    足す前の config から組んでよい。
    """
    return eval_pool.build(load_config(config_path))


def with_composition(config_path: Path, **overrides: Any) -> dict[str, Any]:
    config = load_config(config_path)
    block = {"prompt_template": "{a}+{b}+{c}=", "n_per_cell": SMALL_N}
    block.update(overrides)
    config.setdefault("eval", {})["composition"] = block
    return config


@pytest.fixture(scope="module")
def pilot_pool() -> eval_pool.EvalPool:
    return cp.build_composition_pool(with_composition(PILOT_CONFIG), source_pool(PILOT_CONFIG))


@pytest.fixture(scope="module")
def main_pool() -> eval_pool.EvalPool:
    return cp.build_composition_pool(with_composition(MAIN_CONFIG), source_pool(MAIN_CONFIG))


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_a_null_count_stops_before_anything_is_built() -> None:
    """件数は S5 で人間が決める。null なら門で止まる(ADR-118 決定3)。"""
    config = with_composition(PILOT_CONFIG, n_per_cell=None)
    with pytest.raises(ConfigError, match="null"):
        cp.load_settings(config)


@pytest.mark.parametrize("value", [0, -3, True, 2.5, "80"])
def test_a_bad_count_is_refused(value: Any) -> None:
    with pytest.raises(ConfigError, match="正の整数"):
        cp.load_settings(with_composition(PILOT_CONFIG, n_per_cell=value))


def test_a_config_without_the_block_is_refused() -> None:
    with pytest.raises(ConfigError, match="eval.composition"):
        cp.load_settings(load_config(PILOT_CONFIG))


def test_a_missing_template_stops_the_pool_before_items_are_built() -> None:
    config = with_composition(PILOT_CONFIG)
    del config["eval"]["composition"]["prompt_template"]
    with pytest.raises(ConfigError):
        cp.build_composition_pool(config, source_pool(PILOT_CONFIG))


# --------------------------------------------------------------------------
# 制約(D2 (b))と選び方
# --------------------------------------------------------------------------


def test_the_boundary_of_the_two_step_constraint() -> None:
    """a + b + offset = main_radius は入り、+1 は入らない。±1 は除く。"""
    on_boundary = (50, MAIN_RADIUS - OFFSET - 50)
    just_over = (50, MAIN_RADIUS - OFFSET - 50 + 1)
    with_one = (1, 10)
    candidates = cp.leading_pair_candidates(
        [on_boundary, just_over, with_one, (10, 1)], offset=OFFSET, main_radius=MAIN_RADIUS
    )
    assert candidates == [on_boundary]


def test_third_operand_choices_exclude_one_and_stay_in_the_domain() -> None:
    choices = cp.third_operand_choices(MAIN_RADIUS)
    assert choices[0] == 2 and choices[-1] == MAIN_RADIUS
    assert 1 not in choices and -1 not in choices
    assert len(choices) == MAIN_RADIUS - 1


def test_the_third_operand_depends_only_on_the_pair_and_the_seed() -> None:
    assert cp.third_operand((12, 25), 3, MAIN_RADIUS) == cp.third_operand((12, 25), 3, MAIN_RADIUS)
    values = {cp.third_operand((12, 25), seed, MAIN_RADIUS) for seed in range(40)}
    assert len(values) > 1  # シードが効く(定数ではない)
    assert all(2 <= value <= MAIN_RADIUS for value in values)


def test_selection_does_not_depend_on_the_order_of_candidates() -> None:
    pairs = [(a, b) for a in range(2, 12) for b in range(2, 12)]
    shuffled = list(pairs)
    random.Random(0).shuffle(shuffled)
    assert cp.select_pairs(pairs, 7, 3, cell="x") == cp.select_pairs(shuffled, 7, 3, cell="x")


def test_a_cell_with_too_few_candidates_stops_instead_of_shrinking() -> None:
    with pytest.raises(ConfigError, match="黙って減らさない"):
        cp.select_pairs([(2, 3), (4, 5)], 3, 3, cell="t1c_id_carry")


def test_cell_of_uses_the_leading_pair_for_both_axes() -> None:
    coverage = frozenset({(10, 12)})
    known = cp.cell_of((10, 12), coverage, MAIN_RADIUS)
    unknown = cp.cell_of((10, 13), coverage, MAIN_RADIUS)
    assert known == cp.CompositionCell(COVERAGE_ID, carry_label(10, 12))
    assert unknown == cp.CompositionCell(COVERAGE_INTERP, carry_label(10, 13))
    assert known is not None and known.name == f"t1c_id_{carry_label(10, 12)}"


# --------------------------------------------------------------------------
# 実プール(主・pilot の config と FT の manifest から)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pool_name", ["pilot", "main"])
def test_candidate_counts_match_the_recorded_combinatorial_facts(
    pool_name: str, request: pytest.FixtureRequest
) -> None:
    pool = request.getfixturevalue(f"{pool_name}_pool")
    cells = pool.manifest["fill"]["cells"]
    by_carry = {"nocarry": 0, "carry": 0}
    for name, record in cells.items():
        carry = name.rsplit("_", 1)[1]
        if name.startswith("t1c_id"):
            by_carry[carry] += record["n_candidates"]
    assert by_carry == EXPECTED_CANDIDATES[pool_name]


@pytest.mark.parametrize("pool_name", ["pilot", "main"])
def test_every_item_keeps_the_second_step_inside_the_training_domain(
    pool_name: str, request: pytest.FixtureRequest
) -> None:
    pool = request.getfixturevalue(f"{pool_name}_pool")
    assert len(pool.items) == 4 * SMALL_N
    for item in pool.items:
        a, b, c = item.operands
        assert not is_excluded_operand_pair(item.operands)
        assert 2 <= a and 2 <= b and 2 <= c <= MAIN_RADIUS
        assert a + b + OFFSET <= MAIN_RADIUS  # 2 段目の組 (a+b+offset, c) が域内
        assert 1 <= a + b + OFFSET and c <= MAIN_RADIUS
        assert item.params["answer_range"] == ANSWER_IN
        assert item.params["first_pair_coverage"] == item.params["cell"].split("_")[1]
        assert item.carry == item.params["cell"].split("_")[2]


def test_cells_have_the_same_count_and_all_four_exist(pilot_pool: eval_pool.EvalPool) -> None:
    assert pilot_pool.manifest["fill"]["n_items_by_cell"] == {
        "t1c_id_nocarry": SMALL_N,
        "t1c_id_carry": SMALL_N,
        "t1c_interp_nocarry": SMALL_N,
        "t1c_interp_carry": SMALL_N,
    }
    assert pilot_pool.manifest["fill"]["n_items_by_group"] == {"composition": 4 * SMALL_N}


def test_the_manifest_records_the_rule_and_the_overlap_with_t1(
    pilot_pool: eval_pool.EvalPool,
) -> None:
    fill = pilot_pool.manifest["fill"]
    assert fill["method"] == cp.FILL_COMPOSITION
    assert fill["constraint"]["offset"] == OFFSET
    assert fill["reference_rules"] == ["comp_once", "comp_twice"]
    assert fill["prompt_template"] == {"t1c": "{a}+{b}+{c}="}
    overlap = fill["first_pair_overlap_with_t1"]
    assert overlap["n_overlap"] == sum(overlap["by_cell"].values())
    assert overlap["n_t1_pairs"] > 0


def test_pilot_and_main_first_pairs_do_not_intersect(
    pilot_pool: eval_pool.EvalPool, main_pool: eval_pool.EvalPool
) -> None:
    """pilot と main の領域は交わらない(PLAN-001 §4.6)。T1c でも保たれる。"""
    first_pairs = lambda pool: [(i.operands[0], i.operands[1]) for i in pool.items]  # noqa: E731
    assert pools_are_disjoint(first_pairs(pilot_pool), first_pairs(main_pool))


def test_the_same_config_writes_the_same_bytes_twice(tmp_path: Path) -> None:
    config = with_composition(PILOT_CONFIG)
    source = source_pool(PILOT_CONFIG)
    first = tmp_path / "first"
    second = tmp_path / "second"
    eval_pool.write_pool(cp.build_composition_pool(config, source), first)
    eval_pool.write_pool(cp.build_composition_pool(copy.deepcopy(config), source), second)
    for name in ("items.jsonl", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert b"\r" not in (first / name).read_bytes()


def test_a_larger_count_extends_the_same_selection() -> None:
    """件数を増やしても、先に選んだ組は変わらない(ハッシュ順の先頭 n 組)。"""
    small = with_composition(PILOT_CONFIG, n_per_cell=3)
    large = with_composition(PILOT_CONFIG, n_per_cell=8)
    source = source_pool(PILOT_CONFIG)
    small_ids = {i.item_id for i in cp.build_composition_pool(small, source).items}
    large_ids = {i.item_id for i in cp.build_composition_pool(large, source).items}
    assert small_ids <= large_ids


@pytest.mark.parametrize(
    ("config_path", "pool_name"), [(PILOT_CONFIG, "pilot"), (MAIN_CONFIG, "main")]
)
def test_existing_evaluation_pools_are_unchanged(config_path: Path, pool_name: str) -> None:
    """★既存の評価プールを 1 バイトも変えない(PLAN-037 §3.3 の 1)。

    T1c の入口は評価プールを組み直すだけで書き換えない。commit 済みの manifest の
    `pairs_hash` と、config から組み直した評価プールの `pairs_hash` が一致する。
    """
    committed = json.loads(
        (REPO_ROOT / "data" / "generated" / "battery" / pool_name / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rebuilt = source_pool(config_path)
    assert rebuilt.manifest["pairs_hash"] == committed["pairs_hash"]


def test_the_output_directory_is_next_to_the_evaluation_pool() -> None:
    assert cp.composition_dir_name("pilot") == "pilot_t1c"
    assert cp.composition_dir_name("main") == "main_t1c"
