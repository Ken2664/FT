"""天井のシート(PLAN-044 / ADR-131。役割 `ceiling_probe`)と、天井の水準の計算(`ceiling_level.py`)のテスト。

答える問い: 「天井のシートは書いてあるとおりの `eta` を作り、門を掛けず、`power_sim.yaml` の経路に触れずに回るか。
`L_05`・`L_50` は規則だけから、単調な関数の根として決まるか」

**R は呼ばない**(当てはめは偽物を差す)。**ここに出る数値は実験結果ではない**(仮定値の算術)。
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from code.analysis import ceiling_level, power_sim
from code.config import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]
CEILING_CONFIG = REPO_ROOT / "configs" / "power_sim_ceiling.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "power_sim.yaml"

# テスト用の水準(config に転記される値ではない。配線の確認に値が要るので置く)
TEST_L_05 = 5.3
TEST_L_50 = 7.5

SHEET_IDS = [
    "ceiling_p0_L05", "ceiling_p0_L50", "ceiling_p0_Linf",
    "ceiling_p1_L05", "ceiling_p1_L50", "ceiling_p1_Linf",
    "ceiling_null_L05", "ceiling_null_L50",
]


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def with_levels(config: dict[str, Any]) -> dict[str, Any]:
    """水準が null の config に、テスト用の値を入れた写しを返す。"""
    out = copy.deepcopy(config)
    out["ceiling"]["levels"]["L_05"] = TEST_L_05
    out["ceiling"]["levels"]["L_50"] = TEST_L_50
    return out


def small_config(n_rep: int = 2) -> dict[str, Any]:
    """配線確認用の小さな config(10 シード × 80 項目の表を何枚も組まないため)。**実験の値ではない。**"""
    config = with_levels(load(CEILING_CONFIG))
    config["dgp"]["n_seed"] = 3
    config["dgp"]["n_item"] = [4]
    for sheet in config["sheets"]:
        sheet["points"] = [[4, 1.0, 0.0]]
    config["simulation"]["n_rep_stages"] = [n_rep]
    return config


def sheet_of(config: dict[str, Any], sheet_id: str) -> power_sim.Sheet:
    return next(s for s in power_sim.load_sheets(config) if s.sheet_id == sheet_id)


def eta_of(config: dict[str, Any], sheet_id: str) -> np.ndarray:
    return power_sim.ceiling_profile(config, sheet_of(config, sheet_id)).eta


# --------------------------------------------------------------------------
# config(事前登録の値が写されている・門が無い)
# --------------------------------------------------------------------------


def test_effect_dgp_and_fit_are_the_same_values_as_power_sim_yaml() -> None:
    """★PLAN-044 I1: effect・dgp・fit は写しではなく**同じ値**(別の値を置く場所ではない)。"""
    ceiling, main = load(CEILING_CONFIG), load(MAIN_CONFIG)
    for block in ("effect", "dgp", "fit"):
        assert ceiling[block] == main[block], block
    assert ceiling["simulation"]["alpha"] == main["simulation"]["alpha"]
    assert ceiling["simulation"]["target_power"] == main["simulation"]["target_power"]
    assert ceiling["simulation"]["tost_alpha"] == main["simulation"]["tost_alpha"]


def test_ceiling_config_has_no_gate_and_its_own_seed() -> None:
    """★Q3 (a): 門の欄を持たない。段は 100 反復の 1 段。rng_seed は採った日付で、run3 の 20261008 とは別。"""
    config = load(CEILING_CONFIG)
    assert not set(power_sim.CEILING_FORBIDDEN_GATES) & set(config["simulation"])
    assert config["simulation"]["n_rep_stages"] == [100]
    assert config["simulation"]["rng_seed"] == 20261015
    assert config["simulation"]["rng_seed"] != load(MAIN_CONFIG)["simulation"]["rng_seed"] == 20261008
    assert config["ceiling_level"]["rng_seed"] == 20261015


def test_the_eight_sheets_are_three_kinds_by_level_at_the_axis_point() -> None:
    """★Q2 (a): 3 種・8 枚・各 1 点 (80, 1.0, 0.0)。ceiling_null に L_inf は置かない。"""
    sheets = power_sim.load_sheets(load(CEILING_CONFIG))
    assert [s.sheet_id for s in sheets] == SHEET_IDS
    assert {s.role for s in sheets} == {power_sim.ROLE_CEILING_PROBE}
    assert all(s.points == (power_sim.PointKey(80, 1.0, 0.0),) for s in sheets)
    assert all(s.tau == power_sim.TAU_ZERO for s in sheets)
    by_kind = {kind: [s for s in sheets if s.sheet_id.startswith(kind)] for kind in
               ("ceiling_p0", "ceiling_p1", "ceiling_null")}
    assert [len(v) for v in by_kind.values()] == [3, 3, 2]
    assert {s.ceiling.level_name for s in by_kind["ceiling_null"]} == {"L_05", "L_50"}
    assert {s.ceiling.mode for s in by_kind["ceiling_null"]} == {power_sim.CEILING_MODE_SHIFT_TASK}
    assert {s.ceiling.mode for s in by_kind["ceiling_p0"] + by_kind["ceiling_p1"]} == {
        power_sim.CEILING_MODE_REPLACE
    }


def test_the_level_rule_point_is_the_sheet_point() -> None:
    """I3 が決める L の点(sigma・rho・n_item)は、天井のシートが回す点と同じである。"""
    config = load(CEILING_CONFIG)
    rule = ceiling_level.load_level_rule(config)
    (point,) = {s.points for s in power_sim.load_sheets(config)}
    assert (rule.n_item, rule.sigma, rule.rho) == (point[0].n_item, point[0].sigma, point[0].rho)
    # パイロットと同じ形は 2 シード・2 セル(T1 の id・interp)。シートが置き換えるセルと同じ
    assert rule.n_seed == 2 and rule.cells == (("T1", "id"), ("T1", "interp"))
    replaced = {c for s in power_sim.load_sheets(config) if s.ceiling.mode == "replace" for c in s.ceiling.cells}
    assert replaced == set(rule.cells)


def test_committed_levels_are_the_ceiling_level_output() -> None:
    """★PLAN-044 I3: config の L_05・L_50 は `ceiling_level.py` の出力(run_id つき)と一致する(当てはめの前に commit)。"""
    levels = load(CEILING_CONFIG)["ceiling"]["levels"]
    assert levels["L_inf"] == power_sim.LEVEL_INFINITE
    output = json.loads(
        (REPO_ROOT / "results" / "power_sim" / "ceiling_level" / ceiling_level.OUTPUT_FILE).read_text(encoding="utf-8")
    )
    assert output["run_id"] == "20261015_040148_ceiling_level"
    assert levels["L_05"] == output["levels"]["L_05"]["level"] == 5.3
    assert levels["L_50"] == output["levels"]["L_50"]["level"] == 7.512
    assert levels["L_05"] < levels["L_50"]


# --------------------------------------------------------------------------
# eta(§3.2)・ロジットの真値(§6.1)
# --------------------------------------------------------------------------


def test_ceiling_p0_replaces_the_two_t1_cells_and_keeps_the_rest() -> None:
    config = with_levels(load(CEILING_CONFIG))
    eta = eta_of(config, "ceiling_p0_L05")
    np.testing.assert_allclose(eta, [[TEST_L_05, TEST_L_05, 0.6], [1.8, 0.8, -0.4]])
    np.testing.assert_allclose(eta_of(config, "ceiling_p0_L50")[0, :2], [TEST_L_50, TEST_L_50])


def test_ceiling_p1_replaces_the_two_t1_cells_of_p1() -> None:
    config = with_levels(load(CEILING_CONFIG))
    eta = eta_of(config, "ceiling_p1_L05")
    np.testing.assert_allclose(
        eta, [[TEST_L_05, TEST_L_05, 1.138832], [1.751066, 0.587766, -0.938832]]
    )


def test_ceiling_null_is_exactly_additive_and_shifts_only_the_t1_row() -> None:
    """★§3.2: T1 = [L, L − 1, L − 2.2] / T2 = P0 のまま。交互作用の係数は厳密に 0(P0 と同じ)。"""
    config = with_levels(load(CEILING_CONFIG))
    for sheet_id, level in (("ceiling_null_L05", TEST_L_05), ("ceiling_null_L50", TEST_L_50)):
        profile = power_sim.ceiling_profile(config, sheet_of(config, sheet_id))
        np.testing.assert_allclose(profile.eta[0], [level, level - 1.0, level - 2.2], atol=1e-12)
        np.testing.assert_allclose(profile.eta[1], [1.8, 0.8, -0.4])
        assert profile.eta[0, 0] == level                  # 基準のセルは丸めを残さない
        for value in profile.interaction_contrasts.values():
            assert abs(value) < 1e-12


def test_logit_truth_of_the_replace_sheets_follows_section_6_1() -> None:
    """★§6.1: (interp − id) の係数 = −1・(extrap − id) の係数 = L − 2.8。"""
    config = with_levels(load(CEILING_CONFIG))
    contrasts = power_sim.ceiling_profile(config, sheet_of(config, "ceiling_p0_L05")).interaction_contrasts
    assert contrasts["interp"] == pytest.approx(-1.0)
    assert contrasts["extrap_magnitude"] == pytest.approx(TEST_L_05 - 2.8)
    contrasts = power_sim.ceiling_profile(config, sheet_of(config, "ceiling_p0_L50")).interaction_contrasts
    assert contrasts["extrap_magnitude"] == pytest.approx(TEST_L_50 - 2.8)


def test_logit_truth_is_undefined_at_a_strict_ceiling() -> None:
    """★§6.1: L = +∞ では ∞ − ∞ と発散で、ロジットの真値は定義されない(NaN → JSON では null)。"""
    config = with_levels(load(CEILING_CONFIG))
    for sheet_id in ("ceiling_p0_Linf", "ceiling_p1_Linf"):
        profile = power_sim.ceiling_profile(config, sheet_of(config, sheet_id))
        assert np.isposinf(profile.eta[0, :2]).all()
        assert all(math.isnan(v) for v in profile.interaction_contrasts.values())
        assert set(profile.interaction_contrasts) == {"interp", "extrap_magnitude"}   # TOST が読むキーは残る
    assert power_sim.json_safe(profile.interaction_contrasts) == {"interp": None, "extrap_magnitude": None}


def test_null_level_stops_before_anything_is_written(tmp_path: Path) -> None:
    """水準が null のままなら、out_dir を作る前に止まる(エージェントは値を作らない)。"""
    config = small_config()
    config["ceiling"]["levels"]["L_05"] = None
    with pytest.raises(ConfigError, match="未決定"):
        power_sim.run(config, tmp_path / "out", None, False, through_stage=1)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda s: s["ceiling"].update(mode="shrink"), "ceiling.mode"),
        (lambda s: s["ceiling"].update(level="L_99"), "ceiling.levels に無い"),
        (lambda s: s["ceiling"].update(cells=[["T3", "id"]]), "ceiling.cells"),
        (lambda s: s["ceiling"].update(cells=[]), "ceiling.cells"),
        (lambda s: s["ceiling"].pop("base"), "4 キー"),
        (lambda s: s.update(profile="P0"), "のキーは"),
        (lambda s: s.update(tau=0.5), "tau は zero"),
    ],
)
def test_malformed_ceiling_sheets_stop(edit: Any, message: str) -> None:
    config = with_levels(load(CEILING_CONFIG))
    edit(config["sheets"][0])
    with pytest.raises(ConfigError, match=message):
        power_sim.load_sheets(config)


def test_shift_task_takes_exactly_one_cell_and_no_infinite_level() -> None:
    config = with_levels(load(CEILING_CONFIG))
    null_sheet = next(s for s in config["sheets"] if s["id"] == "ceiling_null_L05")
    null_sheet["ceiling"]["cells"] = [["T1", "id"], ["T1", "interp"]]
    with pytest.raises(ConfigError, match="ちょうど 1 セル"):
        power_sim.load_sheets(config)
    config = with_levels(load(CEILING_CONFIG))
    next(s for s in config["sheets"] if s["id"] == "ceiling_null_L05")["ceiling"]["level"] = "L_inf"
    with pytest.raises(ConfigError, match="の水準 L_inf"):
        power_sim.load_sheets(config)


def test_levels_must_be_a_finite_number_or_inf() -> None:
    config = with_levels(load(CEILING_CONFIG))
    for bad in (True, float("inf"), "big", [1.0]):
        config["ceiling"]["levels"]["L_05"] = bad
        with pytest.raises(ConfigError):
            power_sim.resolve_ceiling_level(config, "L_05")
    config["ceiling"]["levels"]["L_05"] = 5
    assert power_sim.resolve_ceiling_level(config, "L_05") == 5.0


# --------------------------------------------------------------------------
# DGP: +∞ のセルは常に 1 で、乱数の消費は変わらない
# --------------------------------------------------------------------------


def _levels(n_item: int = 6) -> power_sim.DesignLevels:
    return power_sim.DesignLevels(
        tasks=("T1", "T2"), coverages=("id", "interp", "extrap_magnitude"),
        templates={"T1": ["t1"], "T2": ["a", "b"]}, n_seed=3, n_item=n_item,
    )


def _draw(eta: np.ndarray, seed: int = 7) -> tuple[list[tuple[Any, ...]], float]:
    rng = np.random.default_rng(seed)
    rows = power_sim.draw_frame(_levels(), eta, 1.0, 0.0, 2.0, 0.5, rng)
    return rows, float(rng.random())     # 表を引いた後の次の乱数 = 消費した数の目印


def test_a_strict_ceiling_is_always_rule_and_consumes_the_same_random_numbers() -> None:
    """★PLAN-044 I2: `L_inf` のセルは `is_rule` = 1。他のセルの表と、引いた後の乱数列は、有限の `L` と同じ。"""
    finite = np.array([[7.0, 7.0, 0.6], [1.8, 0.8, -0.4]])
    infinite = finite.copy()
    infinite[0, :2] = np.inf
    rows_finite, after_finite = _draw(finite)
    rows_inf, after_inf = _draw(infinite)
    assert after_finite == after_inf
    ceiling_rows = [r for r in rows_inf if r[1] == "T1" and r[2] in ("id", "interp")]
    assert ceiling_rows and all(r[5] == 1 for r in ceiling_rows)
    others = lambda rows: [r for r in rows if not (r[1] == "T1" and r[2] in ("id", "interp"))]  # noqa: E731
    assert others(rows_finite) == others(rows_inf)


# --------------------------------------------------------------------------
# 確率の尺度の真値・セル率
# --------------------------------------------------------------------------


def test_marginal_rule_rate_matches_closed_forms_and_monte_carlo() -> None:
    eta = np.array([[np.inf, 0.0], [1.0, -2.0]])
    rates = power_sim.marginal_rule_rates(eta, 3.5, 100)
    assert rates[0, 0] == pytest.approx(1.0, abs=1e-12)
    assert rates[0, 1] == pytest.approx(0.5, abs=1e-12)                    # 対称な分布の中心 0
    assert power_sim.marginal_rule_rates(eta, 0.0, 10)[1, 0] == pytest.approx(1.0 / (1.0 + math.exp(-1.0)))
    z = np.random.default_rng(0).standard_normal(400_000) * math.sqrt(3.5)
    assert rates[1, 1] == pytest.approx((1.0 / (1.0 + np.exp(-(-2.0 + z)))).mean(), abs=3e-3)
    assert power_sim.marginal_rule_rates(eta, 3.5, 60) == pytest.approx(rates, abs=1e-9)   # 節点数に依らない
    with pytest.raises(ValueError):
        power_sim.marginal_rule_rates(eta, -1.0, 10)


def test_probability_scale_truth_at_a_strict_ceiling_is_defined() -> None:
    """確率の尺度の差の差は、天井でも定義される(ロジットの尺度では定義されない。D.0)。"""
    config = with_levels(load(CEILING_CONFIG))
    profile = power_sim.ceiling_profile(config, sheet_of(config, "ceiling_p0_Linf"))
    truth = power_sim.ceiling_true_values(profile, 1.0, 2.0, 0.5, 100)
    assert truth["random_effect_variance"] == pytest.approx(3.5)
    assert truth["marginal_rule_rate"]["T1"]["id"] == pytest.approx(1.0, abs=1e-12)
    assert truth["marginal_rule_rate"]["T1"]["interp"] == pytest.approx(1.0, abs=1e-12)
    contrasts = truth["probability_scale_contrasts"]
    assert set(contrasts) == {"interp", "extrap_magnitude"}
    assert all(math.isfinite(v) for v in contrasts.values())
    # interp: (T2 interp − T2 id) − 0(T1 は両方 1)。T2 のセルは P0 のまま
    rates = power_sim.marginal_rule_rates(profile.eta, 3.5, 100)
    assert contrasts["interp"] == pytest.approx(rates[1, 1] - rates[1, 0])


def test_ceiling_null_has_zero_logit_truth_but_a_probability_scale_gap() -> None:
    """帰無が真(ロジットで平行)でも、天井では確率の尺度の差の差は 0 でない(確率の尺度は別の主張。05_STATISTICS §2)。"""
    config = with_levels(load(CEILING_CONFIG))
    profile = power_sim.ceiling_profile(config, sheet_of(config, "ceiling_null_L05"))
    truth = power_sim.ceiling_true_values(profile, 1.0, 2.0, 0.5, 100)
    assert abs(truth["probability_scale_contrasts"]["interp"]) > 1e-3


def test_frame_cell_rates_count_is_rule_per_cell_in_row_order() -> None:
    levels = _levels(n_item=4)
    rows = power_sim.draw_frame(
        levels, np.array([[np.inf, 0.0, 0.0], [0.0, 0.0, -np.inf]]), 1.0, 0.0, 2.0, 0.5,
        np.random.default_rng(1),
    )
    rates = power_sim.frame_cell_rates(rows, levels)
    assert power_sim.cell_labels(levels) == [
        "T1.id", "T1.interp", "T1.extrap_magnitude", "T2.id", "T2.interp", "T2.extrap_magnitude",
    ]
    assert rates[0] == 1.0 and rates[5] == 0.0
    assert all(0.0 <= r <= 1.0 for r in rates)
    assert rates[1] == pytest.approx(sum(r[5] for r in rows if (r[1], r[2]) == ("T1", "interp")) / 12)


# --------------------------------------------------------------------------
# 記述の部品(R を使わない)
# --------------------------------------------------------------------------


def test_fit_stage_counts_separates_levels_rescued_and_failed() -> None:
    results = [
        {"reduction_level": 0}, {"reduction_level": 0}, {"reduction_level": 2},
        {"reduction_level": 3, "rescued_by_allfit": True},
        {"reduction_level": 3, "fit_failed": True}, {"fit_failed": True},
    ]
    assert power_sim.fit_stage_counts(results) == {
        "failed": 2, "level_0": 2, "level_2": 1, "rescued_by_allfit": 1,
    }


def test_coefficient_summary_uses_successful_fits_and_counts_non_finite_values() -> None:
    results = [
        {"interaction_interp_est": 1.0, "interaction_interp_se": 0.5},
        {"interaction_interp_est": 3.0, "interaction_interp_se": 1.0},
        {"interaction_interp_est": None, "interaction_interp_se": None},
        {"interaction_interp_est": 99.0, "interaction_interp_se": 99.0, "fit_failed": True},    # 失敗は数えない
    ]
    out = power_sim.summarise_coefficients(results, ("id", "interp"), [0.5])
    assert out["interp"]["estimate"] == {"n": 2, "n_non_finite": 1, "quantiles": {"0.5": 2.0}}
    assert out["interp"]["se"]["quantiles"] == {"0.5": 0.75}
    assert "id" not in out
    empty = power_sim.summarise_coefficients([{"fit_failed": True}], ("id", "interp"), [0.5])
    assert empty["interp"]["estimate"] == {"n": 0, "n_non_finite": 0, "quantiles": None}


def test_json_safe_writes_no_infinity_or_nan() -> None:
    value = power_sim.json_safe({"a": np.array([[np.inf, 1.0], [-np.inf, np.nan]]), "b": (np.float64(2.5), np.int64(3))})
    assert value == {"a": [["inf", 1.0], ["-inf", None]], "b": [2.5, 3]}
    json.dumps(value, allow_nan=False)


# --------------------------------------------------------------------------
# run(R の代わりに偽の当てはめを差す)
# --------------------------------------------------------------------------


def fake_fit_json(p_value: float | None, failed: bool = False) -> dict[str, Any]:
    return {
        "p_value": None if failed else p_value, "chisq": None if failed else 6.0,
        "reduced": failed, "reduction_level": 3 if failed else 0, "fit_failed": failed,
        "rescued_by_allfit": False, "full_singular": False, "add_singular": False,
        "full_refit_done": False, "add_refit_done": False,
        "n_errored_fits": 2 if failed else 0, "first_error": "boom" if failed else "",
        "interaction_interp_est": 0.0, "interaction_interp_se": 0.1,
        "interaction_extrap_magnitude_est": 0.0, "interaction_extrap_magnitude_se": 0.2,
    }


def fake_fits(monkeypatch: pytest.MonkeyPatch, *, failed: bool = False, p_value: float = 0.5) -> list[Path]:
    """R を呼ばない。表ごとに決まった形の JSON を書く。**当てはめの代わりであって数値ではない。**"""
    seen: list[Path] = []

    def run_fits(rscript, libpath, manifest_stem, jobs, refit, max_level, allfit, n_workers):
        for csv_path, out_path in jobs:
            assert csv_path.exists() and not out_path.exists()
            seen.append(csv_path)
            out_path.write_text(json.dumps(fake_fit_json(p_value, failed)), encoding="ascii")
        return []

    monkeypatch.setattr(power_sim, "resolve_rscript", lambda declared: "Rscript")
    monkeypatch.setattr(power_sim, "run_fits", run_fits)
    return seen


def test_run_writes_a_descriptive_summary_with_no_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """★Q3 (a): 門を掛けない。全シートが回り、概要に門の欄が無く、段・来歴・セル率が残る。"""
    seen = fake_fits(monkeypatch)
    summary = power_sim.run(
        small_config(n_rep=3), tmp_path, None, keep_frames=True, through_stage=1, config_path=CEILING_CONFIG
    )
    assert list(summary["sheets"]) == SHEET_IDS
    assert len(seen) == len(SHEET_IDS) * 3
    assert summary["role"] == power_sim.ROLE_CEILING_PROBE and summary["n_rep"] == 3
    for gate_key in ("misspecification_gate", "feasibility_gate", "stopped_at_gate", "margin_table"):
        assert gate_key not in summary
    on_disk = json.loads(
        (tmp_path / "power_sim_summary.json").read_text(encoding="utf-8"),
        parse_constant=lambda name: pytest.fail(f"JSON に {name} が書かれている"),
    )
    assert on_disk == summary
    assert (tmp_path / "stage_0003_summary.json").is_file()
    assert on_disk["run_id"].endswith("_power_sim_ceiling")
    inf_sheet = on_disk["sheets"]["ceiling_p0_Linf"]
    assert inf_sheet["ceiling"]["level"] == "inf" and inf_sheet["eta"][0][:2] == ["inf", "inf"]
    assert inf_sheet["true_logit_interaction_contrasts"] == {"interp": None, "extrap_magnitude": None}
    finite = on_disk["sheets"]["ceiling_p0_L05"]
    assert finite["true_logit_interaction_contrasts"]["interp"] == pytest.approx(-1.0)
    point = finite["grid"][0]
    assert {"intervals", "fit_stage_counts", "interaction_coefficients", "tost_min_margin_quantiles",
            "true_values", "observed_cell_rates", "observed_cell_rates_file"} <= set(point)
    assert point["fit_stage_counts"] == {"level_0": 3}
    assert point["failed_rate"] == 0.0 and point["n_rep"] == 3
    assert point["tost_min_margin_quantiles"]["0.5"] == pytest.approx(0.0 + 1.6448536 * 0.2, abs=1e-5)
    assert set(point["observed_cell_rates"]) == set(
        f"{t}.{c}" for t in ("T1", "T2") for c in ("id", "interp", "extrap_magnitude")
    )
    assert (tmp_path / "ceiling_p0_L05" / point["observed_cell_rates_file"]).is_file()


def test_the_cell_rates_recomputed_from_the_draw_equal_the_kept_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★`--keep-frames` で残した CSV の `is_rule` の平均 = 組み直して数えたセル率(反復の表は鍵だけで決まる)。"""
    fake_fits(monkeypatch)
    config = small_config(n_rep=3)
    power_sim.run(config, tmp_path, None, keep_frames=True, through_stage=1, config_path=CEILING_CONFIG)
    key = power_sim.PointKey(4, 1.0, 0.0)
    tag = key.tag()
    stored = json.loads((tmp_path / "ceiling_p0_Linf" / f"cell_rates_{tag}.json").read_text(encoding="utf-8"))
    assert stored["n_trials_per_cell"] == 12 and len(stored["rates"]) == 3
    for rep, rates in enumerate(stored["rates"]):
        lines = (tmp_path / "ceiling_p0_Linf" / "frames" / f"frame_{tag}_{rep:04d}.csv").read_text().splitlines()[1:]
        counts: dict[str, int] = {}
        for line in lines:
            _, task, cov, _, _, is_rule = line.split(",")
            counts[f"{task}.{cov}"] = counts.get(f"{task}.{cov}", 0) + int(is_rule)
        assert rates == [counts[label] / 12 for label in stored["cells"]]
        assert rates[0] == 1.0 and rates[1] == 1.0            # 厳密な天井


def test_a_ceiling_run_never_closes_even_if_every_fit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★門なし: 失敗率が 1.0 でも止まらず、失敗率と CP95 を記録する(run3 の実行可能性の門は閉じる状況)。"""
    fake_fits(monkeypatch, failed=True)
    summary = power_sim.run(
        small_config(n_rep=4), tmp_path, None, keep_frames=False, through_stage=1, config_path=CEILING_CONFIG
    )
    assert list(summary["sheets"]) == SHEET_IDS
    for body in summary["sheets"].values():
        point = body["grid"][0]
        assert point["failed_rate"] == 1.0 and point["n_reject"] == 0
        assert point["intervals"]["failed"]["rate"] == 1.0
        assert point["fit_stage_counts"] == {"failed": 4}
        assert point["interaction_coefficients"]["interp"]["estimate"]["quantiles"] is None
        assert point["tost_n_failed"] == 4 and point["tost_min_margin_quantiles"]["0.5"] is None   # Δ = +∞


def test_a_resumed_ceiling_run_does_not_refit_finished_repetitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = fake_fits(monkeypatch)
    config = small_config(n_rep=2)
    power_sim.run(config, tmp_path, None, keep_frames=False, through_stage=1, config_path=CEILING_CONFIG)
    first = len(seen)
    power_sim.run(config, tmp_path, None, keep_frames=False, through_stage=1, config_path=CEILING_CONFIG)
    assert len(seen) == first


def test_gate_fields_and_mixed_roles_are_refused() -> None:
    """★「門を掛けない」は欄の有無で固定する。ほかの役割のシートと混ぜない。"""
    for gate_key in power_sim.CEILING_FORBIDDEN_GATES:
        config = with_levels(load(CEILING_CONFIG))
        config["simulation"][gate_key] = {"ci_level": 0.95}
        with pytest.raises(ConfigError, match="門を掛けない"):
            power_sim.check_ceiling_config(config, power_sim.load_sheets(config))
    config = with_levels(load(CEILING_CONFIG))
    config["sheets"].append(copy.deepcopy(load(MAIN_CONFIG)["sheets"][-1]))      # p0(null_calibration)
    with pytest.raises(ConfigError, match="別の役割"):
        power_sim.check_ceiling_config(config, power_sim.load_sheets(config))


def test_dry_run_prints_the_ceiling_plan_without_r(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(power_sim, "resolve_rscript", lambda declared: pytest.fail("dry-run が R を探した"))
    assert power_sim.main(["--config", str(CEILING_CONFIG), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "8 ceiling_probe sheets" in out and "fits      : 1600" in out and "gates     : none" in out
    assert "level L_inf = inf" in out


# --------------------------------------------------------------------------
# 既存の経路(power_sim.yaml)を変えていない
# --------------------------------------------------------------------------


def test_the_main_config_path_has_no_ceiling_sheet_and_still_loads_the_same() -> None:
    main = load(MAIN_CONFIG)
    sheets = power_sim.load_sheets(main)
    assert all(s.ceiling is None and s.role in power_sim.ROLES for s in sheets)
    assert [s.sheet_id for s in sheets] == [
        "misspecification", "misspecification_seed_subspace", "misspecification_seed_per_cell",
        "p1", "p1_tau", "p1_neg", "p0",
    ]
    assert power_sim.ROLE_CEILING_PROBE not in power_sim.ROLES
    assert main["simulation"]["rng_seed"] == 20261008          # run3 の種は変えない(ADR-129 決定5)
    assert "ceiling" not in main and "ceiling_level" not in main


# --------------------------------------------------------------------------
# I3: ceiling_level.py
# --------------------------------------------------------------------------


def small_rule(n_draws: int = 20_000) -> ceiling_level.LevelRule:
    return dataclasses.replace(ceiling_level.load_level_rule(load(CEILING_CONFIG)), n_draws=n_draws, chunk=2_000)


def test_event_probability_increases_strictly_with_the_level() -> None:
    """★PLAN-044 I4: 確率は L について単調増加(共通乱数なので厳密。二分法が解を持つ根拠)。"""
    rule = small_rule()
    probabilities = [ceiling_level.event_probability(level, rule)[0] for level in (2.0, 4.0, 5.0, 6.0, 8.0, 12.0)]
    assert all(b > a for a, b in zip(probabilities, probabilities[1:]))
    assert probabilities[0] < 1e-3 and probabilities[-1] > 0.95
    assert ceiling_level.event_probability(6.0, rule) == ceiling_level.event_probability(6.0, rule)   # 固定の種


def test_event_probability_matches_a_brute_force_draw_of_the_dgp() -> None:
    """★規則の計算が DGP と同じ事象を数えているか: `draw_frame` を直接引いて全セルが rule の割合を数える。"""
    level = 7.0
    rule = small_rule(n_draws=40_000)
    levels = power_sim.DesignLevels(
        tasks=("T1",), coverages=("id", "interp", "extrap_magnitude"), templates={"T1": ["t1"]},
        n_seed=rule.n_seed, n_item=rule.n_item,
    )
    eta = np.array([[level, level, 0.6]])
    rng = np.random.default_rng(11)
    n_rep = 1_500
    hits = 0
    for _ in range(n_rep):
        rows = power_sim.draw_frame(levels, eta, rule.sigma, rule.rho, rule.s2_item, rule.s2_tmpl, rng)
        hits += all(r[5] == 1 for r in rows if r[2] in ("id", "interp"))
    brute = hits / n_rep
    estimate, standard_error = ceiling_level.event_probability(level, rule)
    assert 0.15 < estimate < 0.6                                      # 検定が情報を持つ水準(0 や 1 に張り付かない)
    assert brute == pytest.approx(estimate, abs=4 * math.sqrt(brute * (1 - brute) / n_rep) + 4 * standard_error)


def test_solve_level_finds_the_root_and_orders_the_levels() -> None:
    rule = dataclasses.replace(small_rule(), tolerance=1e-3)
    low = ceiling_level.solve_level(0.05, rule)
    mid = ceiling_level.solve_level(0.5, rule)
    assert low["level"] < mid["level"]
    assert low["probability_at_level"] == pytest.approx(0.05, abs=0.005)
    assert mid["probability_at_level"] == pytest.approx(0.5, abs=0.01)
    assert low["level"] == round(low["level_exact"], rule.round_decimals)


def test_solve_level_refuses_a_bracket_that_does_not_straddle_the_target() -> None:
    rule = dataclasses.replace(small_rule(n_draws=2_000), search_lower=9.0, search_upper=30.0)
    with pytest.raises(ConfigError, match="またがない"):
        ceiling_level.solve_level(0.05, rule)


def test_rule_values_are_required(tmp_path: Path) -> None:
    config = load(CEILING_CONFIG)
    config["ceiling_level"]["n_draws"] = None
    with pytest.raises(ConfigError, match="未決定"):
        ceiling_level.load_level_rule(config)
    config = load(CEILING_CONFIG)
    config["ceiling_level"]["targets"]["L_05"] = 1.5
    with pytest.raises(ConfigError, match=r"\(0, 1\)"):
        ceiling_level.load_level_rule(config)


def test_compute_levels_reads_no_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """★罠1: L は仮定値と規則だけで決める。計算の最中にパイロットの表(や他のどのファイル)も読まない。"""
    rule = small_rule(n_draws=2_000)
    rule = dataclasses.replace(rule, targets={"L_05": 0.05}, table_levels=(5.0,), tolerance=0.5)

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("ceiling_level の計算がファイルを読んだ")

    monkeypatch.setattr(Path, "read_text", refuse)
    monkeypatch.setattr(Path, "read_bytes", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    computed = ceiling_level.compute_levels(rule)
    assert set(computed["levels"]) == {"L_05"} and len(computed["probability_table"]) == 1


def test_main_writes_levels_with_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load(CEILING_CONFIG)
    config["ceiling_level"].update(n_draws=2_000, chunk=1_000, table_levels=[5.0])
    config["ceiling_level"]["targets"] = {"L_05": 0.05}
    config["ceiling_level"]["search"]["tolerance"] = 0.5
    path = tmp_path / "ceiling.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    assert ceiling_level.main(["--config", str(path), "--out-dir", str(tmp_path / "out")]) == 0
    body = json.loads((tmp_path / "out" / ceiling_level.OUTPUT_FILE).read_text(encoding="utf-8"))
    assert body["run_id"].endswith("_ceiling_level") and len(body["git_sha"]) == 40
    assert "NOT read" in body["note"] or "were NOT read" in body["note"]
    assert body["rule"]["n_seed"] == 2 and body["rule"]["n_item"] == 80
    assert set(body["levels"]) == {"L_05"}
