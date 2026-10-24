"""主プールの `interp` セルから逆順が K にある組を除く(PLAN-045 I1〜I5・ADR-134)。

答える問い: 「`interp` セルは、どちらの順も K に無い組だけから引かれているか。
パイロットのプールと `id`・`extrap_magnitude` のセルは 1 組も動いていないか」

ここに固定する数は**組合せ論的な計数であって実験結果ではない**(`CLAUDE.md` §2)。
PLAN-045 §3 に起草時に数えた値を、本番の経路が manifest に出す値として縛る。
"""

from __future__ import annotations

import copy
import functools
import json
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.data_gen import composition_pool as cp
from code.data_gen import eval_pool
from code.data_gen.pool import (
    COVERAGE_ID,
    COVERAGE_INTERP,
    is_interp_mirror,
    mirror_in_k,
    without_interp_mirrors,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"
PILOT_CONFIG = REPO_ROOT / "configs" / "exp_order6b_pilot.yaml"
T1C_MAIN_CONFIG = REPO_ROOT / "configs" / "exp_t1c_main.yaml"
T1C_PILOT_CONFIG = REPO_ROOT / "configs" / "exp_t1c_pilot.yaml"
BATTERY_DIR = REPO_ROOT / "data" / "generated" / "battery"

# 欄を切ったときの主プール = 作り直す前の主プール(PLAN-023 で commit。順6 が測ったプール)。
# `interp_mirror_filter: false` の経路が今までと同じであることの照合に使う。
PRE_FILTER_MAIN_PAIRS_HASH = "13e8479c3dab9b4e234b84d59938087b9de6229206308555b0f9099a00c09f98"

# PLAN-045 §3.2・§3.3 の転記(組合せ論的な計数)。
EXPECTED_REMOVED_BY_STRATUM = {"carry": 115, "nocarry": 358}
EXPECTED_INTERP_SUPPLY = {"interp:carry": 443, "interp:nocarry": 1568}
EXPECTED_ID_MIRRORS = {
    "t1_id_carry": 14,
    "t1_id_nocarry": 7,
    "t2_id_carry": 11,
    "t2_id_nocarry": 15,
}

# 機構を見るための小さい件数。**実験の件数ではない**(T1c の件数は S5 で人間が決める)。
SMALL_N = 5


def with_filter(config_path: Path, value: bool | None) -> dict[str, Any]:
    config = copy.deepcopy(load_config(config_path))
    if value is None:
        config["eval"].pop("interp_mirror_filter", None)
    else:
        config["eval"]["interp_mirror_filter"] = value
    return config


@functools.cache
def main_pool(filtered: bool) -> eval_pool.EvalPool:
    """主プール(約 10 秒)。欄の真偽ごとに 1 度だけ組む。"""
    return eval_pool.build(with_filter(MAIN_CONFIG, filtered))


def coverage_pairs_of(config_path: Path) -> frozenset[tuple[int, int]]:
    manifest = eval_pool.load_condition_manifest(load_config(config_path))
    return frozenset(eval_pool.load_coverage_pairs(manifest))


# --------------------------------------------------------------------------
# 定義(I1)
# --------------------------------------------------------------------------


def test_mirror_in_k_excludes_the_diagonal_and_reads_the_reverse() -> None:
    """★a ≠ b かつ (b, a) ∈ K(ADR-134 決定3)。対角は偽(PLAN-045 罠3)。"""
    k = frozenset({(1, 2), (3, 3)})
    assert mirror_in_k((2, 1), k)
    assert not mirror_in_k((1, 2), k)  # 自分は K にあるが逆順 (2, 1) は無い
    assert not mirror_in_k((3, 3), k)  # 対角の逆順は自分自身
    assert not mirror_in_k((150, 150), k)


def test_only_interp_pairs_with_a_reverse_in_k_are_removed_and_order_is_kept() -> None:
    """`id` の組は逆順が K にあっても残る(ADR-134 決定4)。候補の並びは保つ。"""
    k = frozenset({(2, 5), (5, 2), (3, 7)})
    candidates = [(9, 9), (7, 3), (5, 2), (2, 5), (4, 6), (150, 120)]
    assert is_interp_mirror((7, 3), k, 99)
    assert not is_interp_mirror((5, 2), k, 99)  # id
    assert without_interp_mirrors(candidates, k, 99) == [
        (9, 9),
        (5, 2),
        (2, 5),
        (4, 6),
        (150, 120),
    ]


@pytest.mark.parametrize(("value", "expected"), [(None, False), (False, False), (True, True)])
def test_the_switch_is_off_unless_the_config_says_true(value: bool | None, expected: bool) -> None:
    assert eval_pool.uses_interp_mirror_filter(with_filter(MAIN_CONFIG, value)) is expected


@pytest.mark.parametrize("value", ["false", 1, 0])
def test_the_switch_refuses_anything_but_a_boolean(value: Any) -> None:
    config = with_filter(MAIN_CONFIG, None)
    config["eval"]["interp_mirror_filter"] = value
    with pytest.raises(ConfigError):
        eval_pool.uses_interp_mirror_filter(config)


def test_only_the_main_side_configs_turn_the_switch_on() -> None:
    """★主の config だけ真(ADR-134 決定2)。パイロットの config は欄を持たない(PLAN-045 罠1)。"""
    for path in (MAIN_CONFIG, T1C_MAIN_CONFIG):
        assert load_config(path)["eval"]["interp_mirror_filter"] is True
    for path in (PILOT_CONFIG, T1C_PILOT_CONFIG):
        assert "interp_mirror_filter" not in load_config(path)["eval"]


# --------------------------------------------------------------------------
# 主プール(I2・I5)
# --------------------------------------------------------------------------


def test_no_interp_cell_of_the_main_pool_has_a_reverse_in_k() -> None:
    """★作り直した主プールの `interp` セルで `mirror_in_K` は 0 件(PLAN-045 §9)。

    manifest の記録に頼らず、割当と K から数え直す。
    """
    pool = main_pool(True)
    k = coverage_pairs_of(MAIN_CONFIG)
    cells = {cell["name"]: cell for cell in pool.manifest["fill"]["cells_declared"]}
    interp_cells = [name for name, cell in cells.items() if cell["coverage"] == COVERAGE_INTERP]
    assert len(interp_cells) == 14
    for name in interp_cells:
        pairs = [tuple(pair) for pair in pool.manifest["fill"]["assignment"][name]]
        assert not [pair for pair in pairs if mirror_in_k(pair, k)], name
    recorded = pool.manifest["fill"][eval_pool.INTERP_MIRROR_RECORD]["mirror_in_K_by_cell"]
    assert all(recorded[name] == 0 for name in interp_cells)


def test_the_manifest_records_the_combinatorial_counts_of_plan_045() -> None:
    """除いた組の数(層ごと)・除いた後の供給・`id` セルの件数が PLAN-045 §3 と一致する。"""
    fill = main_pool(True).manifest["fill"]
    removal = fill["candidates"][eval_pool.INTERP_MIRROR_RECORD]
    assert removal["n_removed_by_stratum"] == EXPECTED_REMOVED_BY_STRATUM
    assert removal["n_eligible_before"] - removal["n_eligible_after"] == removal["n_removed"]
    strata = fill["candidates"]["n_eligible_by_stratum"]
    assert {key: strata[key] for key in EXPECTED_INTERP_SUPPLY} == EXPECTED_INTERP_SUPPLY
    by_cell = fill[eval_pool.INTERP_MIRROR_RECORD]["mirror_in_K_by_cell"]
    assert {name: by_cell[name] for name in EXPECTED_ID_MIRRORS} == EXPECTED_ID_MIRRORS
    reverse = fill[eval_pool.INTERP_MIRROR_RECORD]["reverse_in_counterpart_pool"]
    assert reverse["counterpart_manifest"] == "data/generated/battery/pilot/manifest.json"
    assert set(reverse["by_cell"]) == set(fill["assignment"])


def test_only_interp_cells_move_when_the_switch_is_turned_on() -> None:
    """★`id`・`extrap_magnitude` のセルの割当は 1 組も動かない(PLAN-045 §3.3)。"""
    on = main_pool(True).manifest["fill"]
    off = main_pool(False).manifest["fill"]
    coverage = {cell["name"]: cell["coverage"] for cell in on["cells_declared"]}
    for name, pairs in on["assignment"].items():
        if coverage[name] != COVERAGE_INTERP:
            assert pairs == off["assignment"][name], name
    assert COVERAGE_ID in coverage.values()


def test_the_switch_off_rebuilds_the_pool_that_order6_measured() -> None:
    """★欄が偽なら今までと同じ主プールになる(PLAN-045 I2「無い・偽なら今と同じ」)。"""
    off = main_pool(False).manifest
    assert off["pairs_hash"] == PRE_FILTER_MAIN_PAIRS_HASH
    assert eval_pool.INTERP_MIRROR_RECORD not in off["fill"]
    assert eval_pool.INTERP_MIRROR_RECORD not in off["fill"]["candidates"]


# --------------------------------------------------------------------------
# パイロットのプール(罠1)
# --------------------------------------------------------------------------


def test_the_pilot_pool_is_byte_identical_to_the_committed_one(tmp_path: Path) -> None:
    """★パイロットのプールは 1 バイトも変わらない(ADR-134 決定2。PLAN-045 罠1)。

    `items.jsonl` は git に入っていない(`.gitignore`)ので、manifest の `files` に記録された
    sha256 で照合する。manifest は commit 済みのバイト列と比べる。
    """
    pool = eval_pool.build(load_config(PILOT_CONFIG))
    eval_pool.write_pool(pool, tmp_path)
    committed = (BATTERY_DIR / "pilot" / "manifest.json").read_bytes()
    assert (tmp_path / "manifest.json").read_bytes() == committed
    assert eval_pool.INTERP_MIRROR_RECORD not in pool.manifest["fill"]


# --------------------------------------------------------------------------
# T1c の先頭の組(I3)
# --------------------------------------------------------------------------


def with_composition(config_path: Path) -> dict[str, Any]:
    config = copy.deepcopy(load_config(config_path))
    config["eval"]["composition"] = {"prompt_template": "{a}+{b}+{c}=", "n_per_cell": SMALL_N}
    return config


def test_the_t1c_interp_cells_of_the_main_side_have_no_reverse_in_k() -> None:
    """★T1c の先頭の組の `interp` セルにも同じ欄で掛かる(ADR-134 決定1)。"""
    pool = cp.build_composition_pool(with_composition(T1C_MAIN_CONFIG), main_pool(True))
    k = coverage_pairs_of(T1C_MAIN_CONFIG)
    fill = pool.manifest["fill"]
    record = fill[eval_pool.INTERP_MIRROR_RECORD]
    assert record["n_removed"] > 0
    for name, cell in fill["cells"].items():
        if name.startswith(f"t1c_{COVERAGE_INTERP}_"):
            assert not [pair for pair in cell["pairs"] if mirror_in_k(tuple(pair), k)], name
            assert record["mirror_in_K_by_cell"][name] == 0


def test_the_t1c_pool_of_the_pilot_side_has_no_filter_record() -> None:
    """パイロット側の T1c は欄が無いので今と同じ(記録の鍵も書かない)。"""
    source = eval_pool.build(load_config(PILOT_CONFIG))
    pool = cp.build_composition_pool(with_composition(T1C_PILOT_CONFIG), source)
    assert eval_pool.INTERP_MIRROR_RECORD not in pool.manifest["fill"]


def test_the_committed_main_manifests_carry_the_filter_record() -> None:
    """commit した主プールと交差プールの manifest は、欄を真にして作り直したものである。"""
    main = json.loads((BATTERY_DIR / "main" / "manifest.json").read_text(encoding="utf-8"))
    cross = json.loads((BATTERY_DIR / "main_t2_cross" / "manifest.json").read_text(encoding="utf-8"))
    assert eval_pool.INTERP_MIRROR_RECORD in main["fill"]
    assert main["pairs_hash"] != PRE_FILTER_MAIN_PAIRS_HASH
    assert cross["fill"]["source_pool_pairs_hash"] == main["pairs_hash"]
