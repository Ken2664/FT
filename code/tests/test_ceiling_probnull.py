"""確率の尺度の帰無のシート `ceiling_probnull`(PLAN-046 I4。`ceiling_probnull.py` と `power_sim` の `probability_null`)のテスト。

答える問い: 「`ceiling_probnull` の T1 の行は `ceiling_null` と同じで、T2 × id は基のままで、解いたセルで周辺確率の
差の差の真値が 0 になるか。解けない目標・置けないセルで止まるか。config は `power_sim.yaml` の値の写しか」

**R は呼ばない。ここに出る数値は実験結果ではない**(仮定値の算術)。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from code.analysis import ceiling_probnull, power_sim
from code.config import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBNULL_CONFIG = REPO_ROOT / "configs" / "power_sim_ceiling_probnull.yaml"
CEILING_CONFIG = REPO_ROOT / "configs" / "power_sim_ceiling.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "power_sim.yaml"
SHEET_IDS = ["ceiling_probnull_L05", "ceiling_probnull_L50"]


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sheet_of(config: dict[str, Any], sheet_id: str) -> power_sim.Sheet:
    return next(s for s in power_sim.load_sheets(config) if s.sheet_id == sheet_id)


def with_solved(config: dict[str, Any]) -> dict[str, Any]:
    """解いた値を(転記の代わりに)その場で計算して入れた写し。"""
    out = copy.deepcopy(config)
    for sheet in ceiling_probnull.probability_null_sheets(out):
        body = ceiling_probnull.solve_sheet(out, sheet)
        out["ceiling"]["probability_null"]["solved"][body["level_name"]] = body["solved"]
    return out


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_effect_dgp_and_fit_are_the_same_values_as_power_sim_yaml() -> None:
    probnull, main = load(PROBNULL_CONFIG), load(MAIN_CONFIG)
    for block in ("effect", "dgp", "fit"):
        assert probnull[block] == main[block], block
    for key in ("alpha", "target_power", "tost_alpha"):
        assert probnull["simulation"][key] == main["simulation"][key]


def test_levels_and_report_are_copies_of_the_ceiling_config() -> None:
    probnull, ceiling = load(PROBNULL_CONFIG), load(CEILING_CONFIG)
    for name in ("L_05", "L_50"):
        assert probnull["ceiling"]["levels"][name] == ceiling["ceiling"]["levels"][name]
    assert probnull["ceiling"]["report"] == ceiling["ceiling"]["report"]


def test_the_probnull_config_has_no_gate_and_its_own_seed() -> None:
    config = load(PROBNULL_CONFIG)
    assert not set(power_sim.CEILING_FORBIDDEN_GATES) & set(config["simulation"])
    assert config["simulation"]["n_rep_stages"] == [100]
    assert config["simulation"]["rng_seed"] == 20261022
    assert config["simulation"]["rng_seed"] not in (
        load(MAIN_CONFIG)["simulation"]["rng_seed"], load(CEILING_CONFIG)["simulation"]["rng_seed"]
    )


def test_the_two_sheets_are_design_a() -> None:
    """★2026-10-22 案 A: base P0・probability_null・T1 × id を L に・点 (80, 1.0, 0.0)・解くのは T2 の interp・extrap。"""
    config = load(PROBNULL_CONFIG)
    sheets = power_sim.load_sheets(config)
    assert [s.sheet_id for s in sheets] == SHEET_IDS
    for sheet, level in zip(sheets, ("L_05", "L_50")):
        assert sheet.ceiling == power_sim.CeilingSpec("P0", power_sim.CEILING_MODE_PROBABILITY_NULL, (("T1", "id"),), level)
        assert sheet.points == (power_sim.PointKey(80, 1.0, 0.0),) and sheet.tau == power_sim.TAU_ZERO
    assert config["ceiling"]["probability_null"]["solve_cells"] == [["T2", "interp"], ["T2", "extrap_magnitude"]]


# --------------------------------------------------------------------------
# 解く規則と eta
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sheet_id,null_id", [("ceiling_probnull_L05", "ceiling_null_L05"),
                                               ("ceiling_probnull_L50", "ceiling_null_L50")])
def test_the_t1_row_is_ceiling_null_and_t2_id_is_the_base(sheet_id: str, null_id: str) -> None:
    config = with_solved(load(PROBNULL_CONFIG))
    eta = power_sim.ceiling_profile(config, sheet_of(config, sheet_id)).eta
    ceiling = load(CEILING_CONFIG)
    null_eta = power_sim.ceiling_profile(ceiling, sheet_of(ceiling, null_id)).eta
    assert eta[0].tolist() == null_eta[0].tolist()
    assert eta[1, 0] == power_sim.build_profile(config["effect"], "P0").eta[1, 0] == 1.8


@pytest.mark.parametrize("sheet_id", SHEET_IDS)
def test_the_probability_scale_truth_is_zero_and_the_logit_truth_is_not(sheet_id: str) -> None:
    """★I4: 解いた(丸めた)値で、周辺確率の差の差の真値は interp・extrap とも 0(許容内)。ロジットの尺度では 0 でない。"""
    config = with_solved(load(PROBNULL_CONFIG))
    sheet = sheet_of(config, sheet_id)
    profile = power_sim.ceiling_profile(config, sheet)
    truth = power_sim.ceiling_true_values(
        profile, 1.0, config["dgp"]["s2_item"], config["dgp"]["s2_tmpl"],
        config["ceiling"]["report"]["quadrature_nodes"],
    )
    tolerance = config["ceiling"]["probability_null"]["residual_tolerance"]
    assert all(abs(v) <= tolerance for v in truth["probability_scale_contrasts"].values())
    assert all(abs(v) > 0.1 for v in profile.interaction_contrasts.values())


def test_solving_twice_gives_the_same_values() -> None:
    config = load(PROBNULL_CONFIG)
    sheet = sheet_of(config, "ceiling_probnull_L05")
    assert ceiling_probnull.solve_sheet(config, sheet)["solved"] == ceiling_probnull.solve_sheet(config, sheet)["solved"]


def test_an_unreachable_target_stops() -> None:
    rule = ceiling_probnull.load_solve_rule(load(PROBNULL_CONFIG), sheet_of(load(PROBNULL_CONFIG), SHEET_IDS[0]))
    for target in (0.0, 1.0, -0.1, 1.2):
        with pytest.raises(power_sim.PowerSimError, match="外"):
            ceiling_probnull.solve_cell(target, rule)


def test_a_solve_cell_in_the_ceiling_row_or_at_the_reference_stops() -> None:
    for bad in ([["T1", "interp"]], [["T2", "id"]]):
        config = load(PROBNULL_CONFIG)
        config["ceiling"]["probability_null"]["solve_cells"] = bad
        with pytest.raises(ConfigError):
            ceiling_probnull.solve_sheet(config, sheet_of(config, SHEET_IDS[0]))


def test_a_residual_above_the_tolerance_stops() -> None:
    config = load(PROBNULL_CONFIG)
    config["ceiling"]["probability_null"]["round_decimals"] = 1
    with pytest.raises(power_sim.PowerSimError, match="残差"):
        ceiling_probnull.solve_sheet(config, sheet_of(config, SHEET_IDS[0]))


# --------------------------------------------------------------------------
# power_sim の probability_null(既存のずらし方は変わらない)
# --------------------------------------------------------------------------


def test_a_null_solved_value_stops_before_fitting() -> None:
    config = load(PROBNULL_CONFIG)
    config["ceiling"]["probability_null"]["solved"]["L_05"] = None
    with pytest.raises(ConfigError, match="null"):
        power_sim.ceiling_profile(config, sheet_of(config, SHEET_IDS[0]))


def test_build_ceiling_eta_guards_the_solved_cells() -> None:
    base = power_sim.build_profile(load(PROBNULL_CONFIG)["effect"], "P0")
    tasks, coverages = base.tasks, base.coverages
    spec = power_sim.CeilingSpec("P0", power_sim.CEILING_MODE_PROBABILITY_NULL, (("T1", "id"),), "L_05")
    with pytest.raises(ConfigError, match="解いたセル"):
        power_sim.build_ceiling_eta(base.eta, tasks, coverages, spec, 5.3)
    with pytest.raises(ConfigError, match="天井の行"):
        power_sim.build_ceiling_eta(base.eta, tasks, coverages, spec, 5.3, {("T1", "interp"): 1.0})
    with pytest.raises(ConfigError, match="有限"):
        power_sim.build_ceiling_eta(base.eta, tasks, coverages, spec, 5.3, {("T2", "interp"): float("inf")})
    for mode in (power_sim.CEILING_MODE_REPLACE, power_sim.CEILING_MODE_SHIFT_TASK):
        other = power_sim.CeilingSpec("P0", mode, (("T1", "id"),), "L_05")
        with pytest.raises(ConfigError, match="解いたセル"):
            power_sim.build_ceiling_eta(base.eta, tasks, coverages, other, 5.3, {("T2", "interp"): 1.0})
    eta = power_sim.build_ceiling_eta(base.eta, tasks, coverages, spec, 5.3, {("T2", "interp"): 1.25})
    shifted = power_sim.build_ceiling_eta(
        base.eta, tasks, coverages, power_sim.CeilingSpec("P0", power_sim.CEILING_MODE_SHIFT_TASK, spec.cells, "L_05"), 5.3
    )
    expected = shifted.copy()
    expected[1, 1] = 1.25
    assert np.array_equal(eta, expected)


def test_unknown_solved_cells_and_two_cells_and_an_infinite_level_stop() -> None:
    config = load(PROBNULL_CONFIG)
    config["ceiling"]["probability_null"]["solved"]["L_05"] = {"T3.interp": 1.0}
    with pytest.raises(ConfigError, match="未知のセル"):
        power_sim.ceiling_profile(config, sheet_of(config, SHEET_IDS[0]))
    two = load(PROBNULL_CONFIG)
    two["sheets"][0]["ceiling"]["cells"] = [["T1", "id"], ["T1", "interp"]]
    with pytest.raises(ConfigError, match="ちょうど 1 セル"):
        power_sim.load_sheets(two)
    inf = load(PROBNULL_CONFIG)
    inf["ceiling"]["levels"]["L_05"] = power_sim.LEVEL_INFINITE
    with pytest.raises(ConfigError, match="置けない"):
        power_sim.load_sheets(inf)
