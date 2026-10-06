"""PLAN-042 の診断(code/analysis/fit_failure_diagnosis.py)のテスト。

答える問い: 「§2.2 の行の条件と数え直しは、書いてあるとおりに数えるか。D0 が合わないとき止まるか」

**R は 1 度も呼ばない。**当てはめ側(`fit_failure_diagnosis.R`)は手動のスモークで確かめる。
ここは数える層だけを合成データで固定する。**ここに出る数値は実験結果ではない**(CLAUDE.md §2)。
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from code.analysis import fit_failure_diagnosis as fd
from code.analysis import power_sim as ps
from code.config import ConfigError, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "configs" / "fit_failure_diagnosis.yaml"
FIT_R = REPO_ROOT / "code" / "analysis" / "power_sim_fit.R"
ALPHA = 0.05
LEVEL = 0.95
BOUND = 0.075
SHEET = "sheet_a"
TAU = 0.25


@pytest.fixture(scope="module")
def spec() -> fd.DiagnosisSpec:
    return fd.load_spec(load_config(CONFIG), REPO_ROOT)


# ---- config / 目印 -----------------------------------------------------------


def test_config_declares_every_value(spec: fd.DiagnosisSpec) -> None:
    assert spec.n_rep == 100
    assert spec.align_loglik_tolerance == 0.001  # ADR-059 と同じ許容
    assert spec.align_fixef_tolerance_se == 0.01
    assert (spec.separation_numerator, spec.separation_denominator) == (2, 3)
    assert sum(row.n_failed for row in spec.expected_gate_failures) == 103  # §2.2 の n = 103
    assert sum(spec.expected_failures_by_sheet.values()) == 156


def test_null_in_config_stops(tmp_path: Path) -> None:
    config = load_config(CONFIG)
    config["diagnosis"]["allfit"]["start_from_mle"] = None
    with pytest.raises(ConfigError):
        fd.load_spec(config, tmp_path)


def test_r_borrows_a_single_driver_marker() -> None:
    """R 側は power_sim_fit.R の driver より上を借りる。目印が 1 つでなくなったら診断は借りる範囲を決められない。"""
    lines = FIT_R.read_text(encoding="utf-8").splitlines()
    assert sum(1 for line in lines if line.startswith(fd.DRIVER_MARKER)) == 1
    assert fd.DRIVER_MARKER.removeprefix("# ") in fd.R_SCRIPT.read_text(encoding="utf-8")


# ---- 区間 ---------------------------------------------------------------------


def test_cp_interval_lower_matches_the_gate_function() -> None:
    for k, n in [(0, 100), (13, 100), (14, 100), (100, 100)]:
        assert fd.clopper_pearson_interval(k, n, LEVEL)[0] == ps.clopper_pearson_lower(k, n, LEVEL)
    assert fd.clopper_pearson_interval(100, 100, LEVEL)[1] == 1.0
    lo, hi = fd.clopper_pearson_interval(0, 100, LEVEL)
    assert lo == 0.0 and 0.0 < hi < 0.05


def test_gate_opens_at_13_rejections_of_100() -> None:
    """§2.2 の算術: 1 点の門が開くのは棄却 13 回以下(CP95 下端 ≤ 0.075)。"""
    assert fd.recount_point(100, 13, [], ALPHA, LEVEL, BOUND)["opens"]
    assert not fd.recount_point(100, 14, [], ALPHA, LEVEL, BOUND)["opens"]


# ---- 最適化の揃い(1a・1b)-----------------------------------------------------


def opt(name: str, loglik: float | None, *, warn: int = 0, error: str = "", npar: int = 11,
        fixef: tuple[float, ...] = (0.0, 0.0), se: tuple[float, ...] = (1.0, 1.0)) -> dict[str, Any]:
    return {"optimizer": name, "error": error, "n_msgs_all": warn, "n_msgs_nonsingular": warn,
            "loglik": loglik, "npar": npar, "fixef": list(fixef), "se": list(se), "first_message": ""}


def test_aligned_needs_error_free_and_close_to_the_best() -> None:
    records = [opt("a", -100.0), opt("b", -100.0005), opt("c", -100.5), opt("d", None, error="boom")]
    names = [r["optimizer"] for r in fd.aligned_optimizers(records, 0.001, require_silent=True)]
    assert names == ["a", "b"]  # c は 0.5 離れている。d は例外


def test_silent_requirement_drops_warned_optimizers_but_one_b_keeps_them() -> None:
    records = [opt("a", -100.0, warn=1), opt("b", -100.0, warn=1), opt("c", -100.0)]
    assert [r["optimizer"] for r in fd.aligned_optimizers(records, 0.001, require_silent=True)] == ["c"]
    assert len(fd.aligned_optimizers(records, 0.001, require_silent=False)) == 3


def test_best_is_the_basis_of_alignment_even_when_it_has_a_warning() -> None:
    """警告なしを要求するときは、警告なしの中の最大が基準(警告ありの高い logLik は基準にしない)。"""
    records = [opt("a", -99.0, warn=1), opt("b", -100.0), opt("c", -100.0002)]
    aligned = fd.aligned_optimizers(records, 0.001, require_silent=True)
    assert [r["optimizer"] for r in aligned] == ["b", "c"]


def test_fixef_spread_is_max_pairwise_difference_in_se_of_the_best() -> None:
    aligned = [opt("a", -1.0, fixef=(1.0, 5.0)), opt("b", -1.0, fixef=(1.004, 5.0)), opt("c", -1.0, fixef=(1.0, 4.99))]
    assert fd.fixef_spread_se(aligned, [0.5, 2.0]) == pytest.approx(max(0.004 / 0.5, 0.01 / 2.0))
    assert fd.fixef_spread_se(aligned[:1], [1.0, 1.0]) == 0.0


def test_rescue_1b_requires_fixed_effects_to_agree(spec: fd.DiagnosisSpec) -> None:
    agree = [opt("a", -100.0, fixef=(1.0, 2.0)), opt("b", -100.0, fixef=(1.001, 2.0))]
    apart = [opt("a", -100.0, fixef=(1.0, 2.0)), opt("b", -100.0, fixef=(1.5, 2.0))]
    assert fd.rescue_one_model(agree, spec, require_silent=False, check_fixef=True)["satisfied"]
    assert not fd.rescue_one_model(apart, spec, require_silent=False, check_fixef=True)["satisfied"]
    # 1a は固定効果を見ない
    assert fd.rescue_one_model(apart, spec, require_silent=True, check_fixef=False)["satisfied"]


def test_one_optimizer_is_not_enough(spec: fd.DiagnosisSpec) -> None:
    assert not fd.rescue_one_model([opt("a", -100.0)], spec, require_silent=True, check_fixef=False)["satisfied"]


def test_optimizer_rescue_needs_both_models_and_gives_the_lrt_p(spec: fd.DiagnosisSpec) -> None:
    full = [opt("a", -100.0, npar=11), opt("b", -100.0, npar=11)]
    add = [opt("a", -103.0, npar=9), opt("b", -103.0, npar=9)]
    diag = {"allfit_full": {"records": full}, "allfit_add": {"records": add}}
    got = fd.optimizer_rescue(diag, spec, require_silent=True, check_fixef=False)
    assert got["satisfied"]
    assert got["p"] == pytest.approx(fd.lrt_p_from_loglik(-100.0, -103.0, 2))
    assert got["p"] == pytest.approx(0.0498, abs=1e-4)  # chi2.sf(6, 2) = exp(-3)
    diag["allfit_add"] = {"records": [opt("a", -103.0, npar=9)]}
    assert not fd.optimizer_rescue(diag, spec, require_silent=True, check_fixef=False)["satisfied"]


def test_lrt_p_floors_a_negative_difference_at_zero() -> None:
    assert fd.lrt_p_from_loglik(-101.0, -100.0, 2) == 1.0
    with pytest.raises(fd.DiagnosisError):
        fd.lrt_p_from_loglik(-100.0, -101.0, 0)


# ---- 数え直し -----------------------------------------------------------------


def test_recount_keeps_failures_outside_the_set_as_rejections() -> None:
    failures = [(True, 0.5), (True, 0.01), (False, 0.9), (True, None)]
    got = fd.recount_point(100, 5, failures, ALPHA, LEVEL, BOUND)
    # 成功した棄却 5 + 条件の外の 1(棄却のまま)+ p 値の無い 1(棄却のまま)+ p < α の 1
    assert got["n_reject"] == 5 + 1 + 1 + 1
    assert (got["n_in_set"], got["n_in_set_reject"], got["n_in_set_without_p"]) == (3, 1, 1)


def test_recount_with_empty_set_equals_the_rule_d2_prime() -> None:
    failures = [(False, 0.9)] * 25
    assert fd.recount_point(100, 5, failures, ALPHA, LEVEL, BOUND)["n_reject"] == 30  # §0 の表の 30 / 100


def test_failed_only_rate_counts_missing_p_apart() -> None:
    got = fd.failed_only_rate([0.01, 0.2, None, 0.04], ALPHA, LEVEL)
    assert (got["n"], got["n_without_p"], got["n_reject"]) == (3, 1, 2)
    assert fd.failed_only_rate([None], ALPHA, LEVEL)["rate"] is None


def test_same_side() -> None:
    assert fd.same_side(0.01, 0.04, ALPHA) and fd.same_side(0.2, 0.9, ALPHA)
    assert not fd.same_side(0.04, 0.06, ALPHA) and not fd.same_side(None, 0.01, ALPHA)


# ---- 評価 ---------------------------------------------------------------------


def floor_model(*, failed: bool = True, gain: float = 0.001, move: float = 0.05, refit_msgs: int | None = 0,
                sd: float | None = 0.3, moved: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "failed": failed, "errored": False, "refit_done": refit_msgs is not None,
        "loglik_gain": gain, "beta_move": move, "loglik_fit0": -100.0, "loglik_final": -100.0,
        "fit0_n_msgs_all": 1, "refit_n_msgs_all": refit_msgs,
        "refit_n_msgs_nonsingular": 0 if refit_msgs is not None else None,
        "singular": False, "sd_new_term": sd, "moved": moved,
    }


def make_diag(case_id: str, *, p_final: float | None = 0.3, p_fit0: float | None = 0.4,
              full: dict[str, Any] | None = None, add: dict[str, Any] | None = None,
              allfit_full: list[dict[str, Any]] | None = None, allfit_add: list[dict[str, Any]] | None = None,
              d0_ok: bool = True, cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "case_id": case_id, "r_version": "R test", "lme4_version": "0",
        "d0": {"full_logLik": -100.0, "add_logLik": -103.0, "full_logLik_json": -100.0,
               "add_logLik_json": -103.0, "failed_reproduced": True, "ok": d0_ok},
        "floor_full": full or floor_model(), "floor_add": add or floor_model(failed=False, refit_msgs=None, gain=None, move=None),
        "p_fit0": p_fit0, "p_final": p_final,
        "allfit_full": {"coef_names": [], "records": allfit_full or [opt("a", -100.0, warn=1)]},
        "allfit_add": {"coef_names": [], "records": allfit_add or [opt("a", -103.0, warn=1, npar=9)]},
        "cells": cells or [],
    }


def fit_json(*, failed: bool, p: float | None = 0.3, gain: float = 0.001, shift: float = 0.05, silent: bool = True) -> dict[str, Any]:
    levels = [{"level": 3, "label": "drop_coverage_slope", "which": "full", "failed": failed, "refit_done": True,
               "singular": False, "n_warnings": 0 if silent else 1, "loglik_gain": gain, "max_shift": shift, "error": ""}]
    return {"fit_failed": failed, "p_value": None if failed else p, "levels": levels,
            "reduction_level": 3, "full_logLik": -100.0, "add_logLik": -103.0}


def target(rep: int = 0, role: str = fd.ROLE_FAILURE) -> fd.Target:
    return fd.Target(SHEET, ps.PointKey(80, TAU, 0.0), rep, role)


def test_trivial_failure_with_same_side_p_is_row_2_and_row_r(spec: fd.DiagnosisSpec) -> None:
    fit = fit_json(failed=True)
    case = fd.evaluate_case(target(), fit, make_diag("c"), spec, ALPHA)
    assert case.in_row[fd.ROW_2] and case.in_row[fd.ROW_R] and case.in_row[fd.ROW_U]
    assert case.in_row[fd.ROW_3_4] and not case.in_row[fd.ROW_1A]  # 1 つの最適化では 1a を満たさない


def test_row_2_needs_small_size_and_same_side(spec: fd.DiagnosisSpec) -> None:
    big = fd.evaluate_case(target(), fit_json(failed=True, gain=0.02), make_diag("c", full=floor_model(gain=0.02)), spec, ALPHA)
    assert not big.in_row[fd.ROW_2]
    moved = fd.evaluate_case(target(), fit_json(failed=True, shift=0.2), make_diag("c", full=floor_model(move=0.2)), spec, ALPHA)
    assert not moved.in_row[fd.ROW_2]
    flipped = fd.evaluate_case(target(), fit_json(failed=True), make_diag("c", p_final=0.04, p_fit0=0.06), spec, ALPHA)
    assert not flipped.in_row[fd.ROW_2]


def test_row_r_counts_a_singular_message_as_a_message(spec: fd.DiagnosisSpec) -> None:
    """stage1_interim.py の 49 件(= all_refits_silent)と同じ定義: message が 1 つでもあれば満たさない。"""
    fit = fit_json(failed=True, silent=False)
    case = fd.evaluate_case(target(), fit, make_diag("c", full=floor_model(refit_msgs=1)), spec, ALPHA)
    assert not case.in_row[fd.ROW_R]


def test_union_uses_optimizer_p_first(spec: fd.DiagnosisSpec) -> None:
    full = [opt("a", -100.0), opt("b", -100.0)]
    add = [opt("a", -103.0, npar=9), opt("b", -103.0, npar=9)]
    case = fd.evaluate_case(target(), fit_json(failed=True), make_diag("c", allfit_full=full, allfit_add=add), spec, ALPHA)
    assert case.in_row[fd.ROW_1A] and case.in_row[fd.ROW_1B]
    assert case.p_union == case.p[fd.P_ALLFIT_1A] != case.p[fd.P_FINAL]


def test_d0_mismatch_stops(spec: fd.DiagnosisSpec) -> None:
    with pytest.raises(fd.DiagnosisError, match="D0"):
        fd.evaluate_case(target(), fit_json(failed=True), make_diag("c", d0_ok=False), spec, ALPHA)


def test_rerun_size_must_match_the_fit_record(spec: fd.DiagnosisSpec) -> None:
    with pytest.raises(fd.DiagnosisError, match="loglik_gain"):
        fd.evaluate_case(target(), fit_json(failed=True, gain=0.5), make_diag("c"), spec, ALPHA)


def test_control_has_no_floor_size_and_is_in_no_row(spec: fd.DiagnosisSpec) -> None:
    diag = make_diag("c", full=floor_model(failed=False, refit_msgs=None, gain=None, move=None))
    case = fd.evaluate_case(target(role=fd.ROLE_CONTROL), fit_json(failed=False), diag, spec, ALPHA)
    assert case.floor_size is None and not any(case.in_row.values())


# ---- 分離(行 5)---------------------------------------------------------------

CELLS = [
    {"task": t, "coverage": c, "n_seed": 10, "n_seeds_at_0": 0, "n_seeds_at_1": 0,
     "min_rate": 0.3, "max_rate": 0.7, "pooled_rate": 0.5}
    for t in ("T1", "T2") for c in ("id", "interp", "extrap_magnitude")
]


def test_cells_of_coefficient_follow_treatment_coding() -> None:
    cells = [(c["task"], c["coverage"]) for c in CELLS]
    assert len(fd.cells_of_coefficient("(Intercept)", cells)) == 6
    assert fd.cells_of_coefficient("taskT2", cells) == [("T2", "id"), ("T2", "interp"), ("T2", "extrap_magnitude")]
    assert fd.cells_of_coefficient("coverageinterp", cells) == [("T1", "interp"), ("T2", "interp")]
    assert fd.cells_of_coefficient("taskT2:coverageextrap_magnitude", cells) == [("T2", "extrap_magnitude")]
    with pytest.raises(fd.DiagnosisError):
        fd.cells_of_coefficient("taskT9", cells)


def moved(name: str) -> dict[str, Any]:
    return {"name": name, "shift_se": 20.0, "se": 1.0, "before": 0.0, "after": 20.0}


def test_separation_reads_the_cells_of_the_moved_coefficient() -> None:
    cells = [dict(c) for c in CELLS]
    cells[5]["n_seeds_at_1"] = 2  # T2 x extrap_magnitude
    sep = fd.separation_of(make_diag("c", full=floor_model(move=20.0, moved=moved("taskT2:coverageextrap_magnitude")), cells=cells))
    assert sep["separated"] and sep["cells"][0]["n_seeds_at_1"] == 2
    other = fd.separation_of(make_diag("c", full=floor_model(move=20.0, moved=moved("taskT2:coverageinterp")), cells=cells))
    assert not other["separated"]


def test_separation_picks_the_model_that_moved_more() -> None:
    cells = [dict(c) for c in CELLS]
    cells[1]["n_seeds_at_0"] = 1  # T1 x interp
    diag = make_diag("c", full=floor_model(move=11.0, moved=moved("taskT2:coverageinterp")), cells=cells,
                     add=floor_model(move=30.0, moved=moved("coverageinterp")))
    assert fd.separation_of(diag)["separated"]  # add のほうが動いた → coverageinterp → T1 x interp を含む


def test_row_5_threshold_is_two_thirds(spec: fd.DiagnosisSpec) -> None:
    sep_cells = [dict(c) for c in CELLS]
    sep_cells[5]["n_seeds_at_1"] = 1

    def big_case(rep: int, cells: list[dict[str, Any]]) -> fd.CaseEval:
        diag = make_diag(f"c{rep}", full=floor_model(gain=0.5, move=20.0, moved=moved("taskT2:coverageextrap_magnitude")), cells=cells)
        fit = fit_json(failed=True, gain=0.5, shift=20.0)
        return fd.evaluate_case(target(rep), fit, diag, spec, ALPHA)

    two_of_three = [big_case(0, sep_cells), big_case(1, sep_cells), big_case(2, CELLS)]
    assert fd.row_5(two_of_three, spec)["supports"]
    one_of_three = [big_case(0, sep_cells), big_case(1, CELLS), big_case(2, CELLS)]
    got = fd.row_5(one_of_three, spec)
    assert not got["supports"] and got["n_cohort"] == 3
    assert not fd.row_5([], spec)["supports"]


# ---- D4 / D0 -------------------------------------------------------------------


def test_new_term_summary_counts_boundary(spec: fd.DiagnosisSpec) -> None:
    cases = [
        fd.evaluate_case(target(i), fit_json(failed=True), make_diag(f"c{i}", full=floor_model(sd=sd)), spec, ALPHA)
        for i, sd in enumerate([0.0, 0.00001, 0.4, 0.5])
    ]
    got = fd.new_term_summary(cases, spec.boundary_sd_below)
    assert got["floor_full"]["n_boundary"] == 2 and got["floor_full"]["n_with_sd"] == 4
    assert got["floor_full"]["median_sd"] == pytest.approx(0.200005)


def test_d0_summary_reports_the_largest_difference(spec: fd.DiagnosisSpec) -> None:
    case = fd.evaluate_case(target(), fit_json(failed=True), make_diag("c"), spec, ALPHA)
    assert fd.d0_summary([case]) == {"n_cases": 1, "all_ok": True, "max_abs_loglik_diff": 0.0}


# ---- 選ぶ・書く ----------------------------------------------------------------


def synthetic_run(tmp_path: Path, n_rep: int, failed_reps: set[int]) -> tuple[Path, ps.Sheet, ps.GateSpec]:
    key = ps.PointKey(80, TAU, 0.0)
    sheet = ps.Sheet(sheet_id=SHEET, role=ps.ROLE_MISSPECIFICATION, profile="P0", points=(key,),
                     tau=ps.TAU_EQUALS_SIGMA, compare_with=None)
    fits_dir = tmp_path / SHEET / "fits"
    fits_dir.mkdir(parents=True)
    for rep in range(n_rep):
        payload = fit_json(failed=rep in failed_reps)
        (fits_dir / f"fit_{key.tag()}_{rep:04d}.json").write_text(json.dumps(payload), encoding="ascii")
    gate = ps.GateSpec(sheet_ids=(SHEET,), tau=(TAU,), ci_level=LEVEL, lower_bound_above=BOUND)
    return tmp_path, sheet, gate


def small_spec(spec: fd.DiagnosisSpec, run_dir: Path, *, failures: int, silent: int) -> fd.DiagnosisSpec:
    return replace(
        spec, run_dir=run_dir, n_rep=10, controls_per_gate_point=2,
        expected_failures_by_sheet={SHEET: failures},
        expected_gate_failures=(fd.GatePointCount(SHEET, TAU, failures),),
        expected_refit_silent=(silent,),
    )


def test_select_picks_every_failure_and_the_first_successes_as_controls(tmp_path: Path, spec: fd.DiagnosisSpec) -> None:
    run_dir, sheet, gate = synthetic_run(tmp_path, 10, {1, 4, 5})
    targets, _ = fd.select_targets(small_spec(spec, run_dir, failures=3, silent=3), [sheet], gate)
    assert [t.rep for t in targets if t.role == fd.ROLE_FAILURE] == [1, 4, 5]
    assert [t.rep for t in targets if t.role == fd.ROLE_CONTROL] == [0, 2]  # 反復番号の小さい順


def test_select_stops_when_the_known_counts_do_not_match(tmp_path: Path, spec: fd.DiagnosisSpec) -> None:
    run_dir, sheet, gate = synthetic_run(tmp_path, 10, {1, 4, 5})
    with pytest.raises(fd.DiagnosisError, match="既知"):
        fd.select_targets(small_spec(spec, run_dir, failures=4, silent=3), [sheet], gate)
    with pytest.raises(fd.DiagnosisError, match="message"):
        fd.select_targets(small_spec(spec, run_dir, failures=3, silent=2), [sheet], gate)


def test_select_stops_when_a_fit_is_missing(tmp_path: Path, spec: fd.DiagnosisSpec) -> None:
    run_dir, sheet, gate = synthetic_run(tmp_path, 9, {1})
    with pytest.raises(fd.DiagnosisError, match="fit が無い"):
        fd.select_targets(small_spec(spec, run_dir, failures=1, silent=1), [sheet], gate)


def test_case_line_carries_the_d0_expectation(tmp_path: Path) -> None:
    fit = fit_json(failed=True)
    line = fd.case_line(target(7), tmp_path / "a.csv", tmp_path / "b.json", fit)
    parts = line.removeprefix("case=").split("|")
    assert parts[2:] == ["3", "-100.0", "-103.0", "true", f"{SHEET}__n80_s0p25_r0__0007"]
    fit["full_logLik"] = None
    assert fd.case_line(target(), tmp_path / "a.csv", tmp_path / "b.json", fit).split("|")[3] == "NA"


def test_manifest_flows_the_tolerances_from_config(tmp_path: Path, spec: fd.DiagnosisSpec) -> None:
    path = tmp_path / "m.txt"
    fd.write_diagnosis_manifest(path, ["case=x"], spec, {"loglik_tolerance": 0.001, "beta_move_tolerance": 0.01}, 3)
    text = path.read_text(encoding="ascii")
    assert "floor_level=3" in text and "allfit_start_from_mle=false" in text and "case=x" in text
    assert "d0_loglik_tolerance=1e-06" in text
    assert "\r" not in text


def test_split_evenly_is_contiguous_and_complete() -> None:
    shards = fd.split_evenly(list(range(10)), 4)
    assert [len(s) for s in shards] == [3, 3, 2, 2]
    assert [x for s in shards for x in s] == list(range(10))
    assert fd.split_evenly([], 4) == [] and len(fd.split_evenly([1, 2], 16)) == 2
    with pytest.raises(ConfigError):
        fd.split_evenly([1], 0)


# ---- 集計の通し ------------------------------------------------------------------


def test_aggregate_end_to_end_on_synthetic_outputs(tmp_path: Path, spec: fd.DiagnosisSpec) -> None:
    """合成の fit と R の出力で、行ごとの数え直しが通る。門の点が 1 つだけ・100 反復の算術を使う。"""
    n_rep = 100
    run_dir, sheet, gate = synthetic_run(tmp_path, n_rep, set(range(25)))   # 25 失敗 = 0..24
    # 成功した反復のうち 5 件は棄却(p < α)。fit_json は p = 0.3 なので書き換える
    fits_dir = run_dir / SHEET / "fits"
    key = sheet.points[0]
    for rep in range(25, 30):
        path = fits_dir / f"fit_{key.tag()}_{rep:04d}.json"
        payload = json.loads(path.read_text(encoding="ascii"))
        payload["p_value"] = 0.01
        path.write_text(json.dumps(payload), encoding="ascii")
    (run_dir / "run_info.json").write_text(json.dumps({"run_id": "synthetic"}), encoding="utf-8")
    s = replace(spec, run_dir=run_dir, n_rep=n_rep, controls_per_gate_point=2,
                expected_failures_by_sheet={SHEET: 25},
                expected_gate_failures=(fd.GatePointCount(SHEET, TAU, 25),), expected_refit_silent=(25,))
    targets, fits_by_point = fd.select_targets(s, [sheet], gate)
    out_dir = tmp_path / "r_out"
    out_dir.mkdir()
    for t in targets:
        failed = t.role == fd.ROLE_FAILURE
        # 失敗 25 件のうち 20 件は当て直しの後の p が非棄却、5 件は棄却
        p_final = 0.01 if failed and t.rep >= 20 else 0.3
        diag = make_diag(t.case_id, p_final=p_final) if failed else make_diag(
            t.case_id, full=floor_model(failed=False, refit_msgs=None, gain=None, move=None))
        (out_dir / f"{t.case_id}.json").write_text(json.dumps(diag), encoding="ascii")
    got = fd.aggregate(s, {"simulation": {"alpha": ALPHA}}, gate, targets, fits_by_point, out_dir)
    row3 = got["judgement_rows"][fd.ROW_3_4]["by_point"][0]
    # 成功した棄却 5 + 当て直しの後も棄却の 5(反復 20〜24)= 10。残り 20 は非棄却に数え直す。下端 ≤ 0.075 → 開く
    assert row3["n_reject"] == 10 and row3["n_in_set"] == 25 and row3["opens"]
    assert got["judgement_rows"][fd.ROW_3_4]["supports"] and got["judgement_rows"][fd.ROW_3_4]["row_number"] == 3
    # 1a は 1 つの最適化しか合成していないので誰も満たさず、規則 D2' どおり 5 + 25 = 30
    assert got["judgement_rows"][fd.ROW_1A]["by_point"][0]["n_reject"] == 30
    assert not got["judgement_rows"][fd.ROW_1A]["supports"]
    # 行 R は 25 件すべて。行 2 は当て直しの後と fit0 が同じ側の 20 件だけ(反復 20〜24 は p が食い違う)。
    # どちらも数え直した棄却は 10(行 2 の外の 5 件は棄却のまま)。記述の行には「支える」を付けない
    assert got["descriptive_rows"][fd.ROW_R]["n_in_set_total"] == 25
    assert got["descriptive_rows"][fd.ROW_2]["n_in_set_total"] == 20
    assert got["descriptive_rows"][fd.ROW_2]["by_point"][0]["n_reject"] == 10
    assert "supports" not in got["descriptive_rows"][fd.ROW_2]
    failed_only = got["failed_only_rejection"]["after_refit"]["total_over_4_points"]
    assert (failed_only["n"], failed_only["n_reject"]) == (25, 5)
    assert got["meta"]["n_cases"] == {"failures": 25, "controls": 2, "failures_at_gate_points": 25}
    assert got["d4_new_term_sd"]["controls"]["n"] == 2
