"""天井の手当て C の評価(PLAN-046 I1・I3。`ceiling_remedy.py`)のテスト。

答える問い: 「天井の規則は n/n・0/n だけを当て、n − 1/n とセルが欠ける表を正しく扱うか。評価は表を照合し、
天井の反復だけを C の道に回し、失敗を非棄却・分母に残して数え、G1・G2 を ADR-133 の形で判定するか」

**R は呼ばない**(LMM とロジットの当てはめは偽物を差す)。**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from code.analysis import ceiling_remedy, power_sim

REPO_ROOT = Path(__file__).resolve().parents[2]
REMEDY_CONFIG = REPO_ROOT / "configs" / "ceiling_remedy.yaml"
CEILING_CONFIG = REPO_ROOT / "configs" / "power_sim_ceiling.yaml"
LOGIT_SCRIPT = REPO_ROOT / "code" / "analysis" / "power_sim_fit.R"
LMM_SCRIPT = REPO_ROOT / "code" / "analysis" / "power_sim_fit_lmm.R"
LOGIT_SCRIPT_SHA256 = "a04737a4881a8839fb625a318481825142acc2e24c00e57c6e8596fb3a5185d6"

TASKS = ("T1", "T2")
COVERAGES = ("id", "interp", "extrap_magnitude")


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def table(rule_by_cell: dict[tuple[str, str], list[int]]) -> list[tuple[Any, ...]]:
    """セルごとの `is_rule` の列から長形式の行を組む(シード・項目は区別に要るだけ)。"""
    rows = []
    for (task, coverage), values in rule_by_cell.items():
        for k, value in enumerate(values):
            rows.append((f"s{k % 2:02d}", task, coverage, f"{task}.{coverage}.{k:04d}", "t", value))
    return rows


def mixed_cells(n: int = 6) -> dict[tuple[str, str], list[int]]:
    """どのセルも 0 と 1 が混ざった表(天井でない)。"""
    return {(t, c): [1] * (n - 2) + [0, 1] for t in TASKS for c in COVERAGES}


# --------------------------------------------------------------------------
# I1 天井の判定
# --------------------------------------------------------------------------


def test_a_table_with_no_full_or_empty_cell_is_not_ceiling() -> None:
    verdict = ceiling_remedy.ceiling_rule(table(mixed_cells()), TASKS, COVERAGES)
    assert not verdict.ceiling and verdict.hits == ()
    assert verdict.n_per_cell == (6,) * 6


def test_n_of_n_in_one_cell_is_ceiling() -> None:
    cells = mixed_cells()
    cells[("T1", "id")] = [1] * 6
    verdict = ceiling_remedy.ceiling_rule(table(cells), TASKS, COVERAGES)
    assert verdict.ceiling and verdict.hits == (("T1", "id", ceiling_remedy.DIRECTION_ALL_RULE),)


def test_zero_of_n_is_ceiling_in_the_other_direction() -> None:
    """床(0/n)も規則に当たる(ADR-132 決定2: n/n か 0/n)。"""
    cells = mixed_cells()
    cells[("T2", "extrap_magnitude")] = [0] * 6
    verdict = ceiling_remedy.ceiling_rule(table(cells), TASKS, COVERAGES)
    assert verdict.hits == (("T2", "extrap_magnitude", ceiling_remedy.DIRECTION_NO_RULE),)


def test_n_minus_one_of_n_is_not_ceiling() -> None:
    cells = mixed_cells()
    cells[("T1", "id")] = [1] * 5 + [0]
    cells[("T1", "interp")] = [0] * 5 + [1]
    assert not ceiling_remedy.ceiling_rule(table(cells), TASKS, COVERAGES).ceiling


def test_every_hit_is_recorded_in_cell_order() -> None:
    cells = mixed_cells()
    cells[("T1", "id")] = [1] * 6
    cells[("T1", "interp")] = [1] * 6
    verdict = ceiling_remedy.ceiling_rule(table(cells), TASKS, COVERAGES)
    assert [h[:2] for h in verdict.hits] == [("T1", "id"), ("T1", "interp")]


def test_a_table_with_a_missing_cell_is_not_judged() -> None:
    """セルが欠ける表は「天井でない」に倒さず止まる(df < 2 は適格性フィルタの側の話)。"""
    cells = mixed_cells()
    del cells[("T2", "interp")]
    with pytest.raises(ceiling_remedy.CeilingRuleError, match="欠ける"):
        ceiling_remedy.ceiling_rule(table(cells), TASKS, COVERAGES)


def test_unknown_cells_and_non_binary_responses_stop() -> None:
    rows = table(mixed_cells())
    with pytest.raises(ceiling_remedy.CeilingRuleError, match="宣言に無い"):
        ceiling_remedy.ceiling_rule([*rows, ("s00", "T3", "id", "x", "t", 1)], TASKS, COVERAGES)
    with pytest.raises(ceiling_remedy.CeilingRuleError, match="0/1"):
        ceiling_remedy.ceiling_rule([*rows, ("s00", "T1", "id", "x", "t", 2)], TASKS, COVERAGES)


# --------------------------------------------------------------------------
# 道と棄却・門
# --------------------------------------------------------------------------


def fit(p: float | None, *, failed: bool = False, df: int = 2) -> dict[str, Any]:
    return {"p_value": None if failed else p, "fit_failed": failed, "df": None if failed else df}


def test_path_outcome_counts_failure_as_non_reject() -> None:
    """ADR-128 決定1 (A2): 失敗は非棄却。p = alpha は棄却しない(`summarise_point` と同じ `<`)。"""
    assert ceiling_remedy.path_outcome(fit(None, failed=True), 0.05, "x") == (False, True)
    assert ceiling_remedy.path_outcome(fit(0.049), 0.05, "x") == (True, False)
    assert ceiling_remedy.path_outcome(fit(0.05), 0.05, "x") == (False, False)


def test_path_outcome_stops_on_a_missing_p_value_or_a_wrong_df() -> None:
    with pytest.raises(power_sim.PowerSimError):
        ceiling_remedy.path_outcome({"p_value": None, "fit_failed": False, "df": 2}, 0.05, "x")
    with pytest.raises(power_sim.PowerSimError):
        ceiling_remedy.path_outcome(fit(0.01, df=1), 0.05, "x")


def test_the_branch_uses_the_lmm_only_when_the_rule_fires() -> None:
    ceiling = ceiling_remedy.CeilingVerdict(True, (("T1", "id", "all_rule"),), (6,) * 6)
    plain = ceiling_remedy.CeilingVerdict(False, (), (6,) * 6)
    logit, lmm = fit(0.01), fit(0.5)
    on_c = ceiling_remedy.rep_record(0, ceiling, logit, lmm, 0.05, "x")
    on_logit = ceiling_remedy.rep_record(1, plain, logit, lmm, 0.05, "x")
    assert (on_c["path"], on_c["reject"]) == (ceiling_remedy.PATH_C, False)
    assert (on_logit["path"], on_logit["reject"]) == (ceiling_remedy.PATH_LOGIT, True)
    failed_c = ceiling_remedy.rep_record(2, ceiling, logit, fit(None, failed=True), 0.05, "x")
    assert failed_c["path_failed"] and not failed_c["reject"]


def test_g1_closes_at_14_of_100_and_not_at_13() -> None:
    """ADR-133 の算術: CP95 下端 > 0.075 は 14/100 から(下端 0.0787)。"""
    rule = ceiling_remedy.GateRule(ci_level=0.95, closes_if_lower_above=0.075)
    assert ceiling_remedy.gate_verdict(14, 100, rule)["closed"]
    assert not ceiling_remedy.gate_verdict(13, 100, rule)["closed"]


def test_g2_cannot_close_at_a_point_no_replication_entered() -> None:
    rule = ceiling_remedy.GateRule(ci_level=0.95, closes_if_lower_above=0.10)
    verdict = ceiling_remedy.gate_verdict(0, 0, rule)
    assert not verdict["evaluable"] and not verdict["closed"] and verdict["rate"] is None
    assert ceiling_remedy.gate_verdict(3, 3, rule)["closed"]       # 3/3 の下端 0.292


# --------------------------------------------------------------------------
# 表の照合(§8 罠8)
# --------------------------------------------------------------------------


def write_frame(path: Path, rows: list[tuple[Any, ...]]) -> None:
    power_sim.write_frame_csv(rows, path)


def test_verify_frame_accepts_the_redrawn_table_and_rejects_any_difference(tmp_path: Path) -> None:
    rows = table(mixed_cells())
    path = tmp_path / "frame_a_0000.csv"
    write_frame(path, rows)
    logit = {"csv": path.name, "n_rows": len(rows)}
    assert ceiling_remedy.verify_frame(path, rows, logit, "fit_a_0000.json", {path.name: "fit_a_0000.json"}) == rows
    changed = list(rows)
    changed[0] = (*changed[0][:5], 1 - changed[0][5])
    with pytest.raises(power_sim.PowerSimError, match="組み直した"):
        ceiling_remedy.verify_frame(path, changed, logit, "fit_a_0000.json", {})
    with pytest.raises(power_sim.PowerSimError, match="manifest"):
        ceiling_remedy.verify_frame(path, rows, logit, "fit_a_0000.json", {path.name: "fit_b_0000.json"})
    with pytest.raises(power_sim.PowerSimError, match="n_rows"):
        ceiling_remedy.verify_frame(path, rows, {"csv": path.name, "n_rows": 1}, "fit_a_0000.json", {})
    with pytest.raises(power_sim.PowerSimError, match="表が無い"):
        ceiling_remedy.verify_frame(tmp_path / "none.csv", rows, logit, "fit_a_0000.json", {})


def test_manifest_pairs_reads_every_fit_line(tmp_path: Path) -> None:
    (tmp_path / "manifest_x_00.txt").write_text(
        "loglik_tolerance=0.001\nfit=a/frames/frame_x_0000.csv|a/fits/fit_x_0000.json\n", encoding="ascii"
    )
    (tmp_path / "manifest_x_01.txt").write_text("fit=a/frames/frame_x_0001.csv|a/fits/fit_x_0001.json\n",
                                                encoding="ascii")
    assert ceiling_remedy.manifest_pairs(tmp_path) == {
        "frame_x_0000.csv": "fit_x_0000.json", "frame_x_0001.csv": "fit_x_0001.json",
    }


def test_the_lmm_manifest_is_the_logit_manifest_plus_the_lmm_keys(tmp_path: Path) -> None:
    """ADR-133 決定1: 閾値・縮退の段数・allFit はロジットの道と同じ値を流し、最適化と ML を足すだけ。"""
    fit_config = load(CEILING_CONFIG)["fit"]
    jobs = [(tmp_path / "frame.csv", tmp_path / "out.json")]
    logit_path, lmm_path = tmp_path / "logit.txt", tmp_path / "lmm.txt"
    power_sim.write_fit_manifest(logit_path, jobs, fit_config["refit"], len(fit_config["reduction_order"]),
                                 power_sim.load_allfit_spec({"fit": fit_config}))
    ceiling_remedy.write_lmm_manifest(lmm_path, jobs, fit_config, "nloptwrap")
    assert lmm_path.read_text(encoding="ascii") == (
        logit_path.read_text(encoding="ascii") + "lmm_optimizer=nloptwrap\nlmm_reml=false\n"
    )


def test_the_logit_script_is_byte_for_byte_unchanged() -> None:
    """★PLAN-046 I2: ロジットの道(power_sim_fit.R)は 1 バイトも変えない。値は 472fe75(PLAN-043)から 2026-10-22 まで同じ。"""
    assert hashlib.sha256(LOGIT_SCRIPT.read_bytes()).hexdigest() == LOGIT_SCRIPT_SHA256


def test_the_lmm_script_is_a_separate_file_and_the_logit_script_has_no_lmer() -> None:
    """★PLAN-046 I2: ロジットの道には lmer が入っていない。LMM は別のファイル。"""
    assert re.search(r"(?<!g)lmer\(", LOGIT_SCRIPT.read_text(encoding="utf-8")) is None
    lmm = "\n".join(
        line for line in LMM_SCRIPT.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")
    )
    assert "REML = FALSE" in lmm and "glmer(" not in lmm
    assert 'start = list(theta = getME(fit0, "theta"))' in lmm      # ADR-133 決定1: 初期値は theta だけ
    assert "refit = FALSE" in lmm


# --------------------------------------------------------------------------
# config(ADR-133 の値)
# --------------------------------------------------------------------------


def test_the_gate_values_are_the_ones_decided_in_adr_133() -> None:
    config = load(REMEDY_CONFIG)
    assert config["gates"]["g1"] == {
        "sheets": ["ceiling_probnull_L05", "ceiling_probnull_L50"], "ci_level": 0.95, "closes_if_lower_above": 0.075,
    }
    assert config["gates"]["g2"] == {"ci_level": 0.95, "closes_if_lower_above": 0.10}
    assert config["lmm"]["reml"] is False and config["lmm"]["optimizer"] == "nloptwrap"
    assert [s["id"] for s in config["sources"]] == ["ceiling", "ceiling_probnull"]
    assert config["sources"][0]["run_id"] == "20261016_130005_power_sim_ceiling"
    assert config["n_rep"] == 100


# --------------------------------------------------------------------------
# 配線(偽の当てはめで、小さな元の run から要約まで)
# --------------------------------------------------------------------------

SMALL_SHEETS = ("ceiling_p0_Linf", "ceiling_null_L05")


def small_source_config() -> dict[str, Any]:
    """小さな元の run の config(3 シード × 4 項目・2 シート・3 反復)。**実験の値ではない。**"""
    config = load(CEILING_CONFIG)
    config["dgp"]["n_seed"] = 3
    config["dgp"]["n_item"] = [4]
    config["sheets"] = [s for s in config["sheets"] if s["id"] in SMALL_SHEETS]
    for sheet in config["sheets"]:
        sheet["points"] = [[4, 1.0, 0.0]]
    config["simulation"]["n_rep_stages"] = [3]
    return config


def fake_logit_fits(monkeypatch: pytest.MonkeyPatch, p_value: float) -> None:
    def run_fits(rscript, libpath, manifest_stem, jobs, refit, max_level, allfit, n_workers):
        for csv_path, out_path in jobs:
            n_rows = len(csv_path.read_text(encoding="ascii").splitlines()) - 1
            out_path.write_text(json.dumps({
                "csv": csv_path.name, "n_rows": n_rows, "df": 2, "p_value": p_value, "chisq": 1.0,
                "reduced": False, "reduction_level": 0, "fit_failed": False, "rescued_by_allfit": False,
                "full_singular": False, "add_singular": False, "full_refit_done": False, "add_refit_done": False,
                "n_errored_fits": 0, "first_error": "",
                "interaction_interp_est": 0.0, "interaction_interp_se": 0.1,
                "interaction_extrap_magnitude_est": 0.0, "interaction_extrap_magnitude_se": 0.2,
            }), encoding="ascii")
            manifest = manifest_stem.with_name(f"{manifest_stem.name}_00.txt")
            with manifest.open("a", encoding="ascii") as handle:
                handle.write(f"fit={csv_path.as_posix()}|{out_path.as_posix()}\n")
        return []

    monkeypatch.setattr(power_sim, "resolve_rscript", lambda declared: "Rscript")
    monkeypatch.setattr(power_sim, "run_fits", run_fits)


def fake_lmm_fits(monkeypatch: pytest.MonkeyPatch, failed: bool) -> list[Path]:
    seen: list[Path] = []

    def run_lmm_fits(spec, rscript, manifest_stem, jobs, fit_config):
        for csv_path, out_path in jobs:
            seen.append(csv_path)
            out_path.write_text(json.dumps({
                "csv": csv_path.name, "optimizer": spec.lmm_optimizer, "df": None if failed else 2,
                "p_value": None if failed else 0.001, "fit_failed": failed, "reduced": False, "reduction_level": 0,
                "rescued_by_allfit": False, "full_singular": False, "add_singular": False,
                "full_refit_done": False, "add_refit_done": False,
                **({} if failed else {
                    "interaction_interp_est": 0.01, "interaction_interp_se": 0.02,
                    "interaction_extrap_magnitude_est": -0.01, "interaction_extrap_magnitude_se": 0.02,
                }),
            }), encoding="ascii")
        return {}

    monkeypatch.setattr(ceiling_remedy, "run_lmm_fits", run_lmm_fits)
    return seen


def build_small_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, Any]]:
    source_config = small_source_config()
    source_path = tmp_path / "source.yaml"
    source_path.write_text(yaml.safe_dump(source_config, allow_unicode=True), encoding="utf-8")
    fake_logit_fits(monkeypatch, p_value=0.01)
    power_sim.run(source_config, tmp_path / "source", None, keep_frames=True, through_stage=1,
                  config_path=source_path)
    remedy = copy.deepcopy(load(REMEDY_CONFIG))
    remedy["sources"] = [{"id": "small", "config": str(source_path), "results_dir": str(tmp_path / "source"),
                          "run_id": None}]
    remedy["n_rep"] = 3
    remedy["gates"]["g1"]["sheets"] = ["ceiling_null_L05"]
    remedy_path = tmp_path / "remedy.yaml"
    remedy_path.write_text(yaml.safe_dump(remedy, allow_unicode=True), encoding="utf-8")
    return remedy_path, remedy


@pytest.mark.parametrize("lmm_failed", [False, True])
def test_the_evaluation_counts_the_branched_procedure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lmm_failed: bool
) -> None:
    """全部の表に LMM が当たり、天井の反復だけが C の道を通り、失敗は非棄却・分母に残る。G1・G2 が判定される。"""
    remedy_path, remedy = build_small_run(tmp_path, monkeypatch)
    seen = fake_lmm_fits(monkeypatch, failed=lmm_failed)
    spec = ceiling_remedy.load_eval_spec(remedy, {}, None, None)
    summary = ceiling_remedy.run(remedy, remedy_path, tmp_path / "eval", spec, max_rep=3)
    assert len(seen) == len(SMALL_SHEETS) * 3
    for sheet_id in SMALL_SHEETS:
        (point,) = summary["sheets"][sheet_id]["points"]
        reps = json.loads((tmp_path / "eval" / sheet_id / "reps_n4_s1_r0.json").read_text(encoding="utf-8"))
        by_path = point["branched"]["by_path"]
        assert by_path["identity_lmm"]["n"] == point["ceiling"]["n_ceiling"] == sum(r["ceiling"] for r in reps)
        assert by_path["logit"]["n"] + by_path["identity_lmm"]["n"] == point["n_rep"] == 3
        # 天井でない反復はロジット(p = 0.01)で棄却。C の道は LMM(成功なら 0.001 で棄却・失敗なら非棄却)
        expected = by_path["logit"]["n"] + (0 if lmm_failed else by_path["identity_lmm"]["n"])
        assert point["branched"]["count"] == expected and point["branched"]["n"] == 3
        assert by_path["identity_lmm"]["n_fit_failed"] == (by_path["identity_lmm"]["n"] if lmm_failed else 0)
        assert point["frames_verified"] == 3 and point["frames_listed_in_manifest"] == 3
    linf = summary["sheets"]["ceiling_p0_Linf"]["points"][0]
    assert linf["ceiling"]["n_ceiling"] == 3                       # +∞ のセルは必ず n/n
    assert linf["ceiling"]["by_cell"]["T1.id"]["all_rule"] == 3
    assert "g1" in summary["sheets"]["ceiling_null_L05"]["points"][0] and "g1" not in linf
    assert summary["gates"]["evaluated"] and summary["gates"]["g2"]["n_points"] == 2
    assert summary["gates"]["g2"]["closed"] == lmm_failed          # 3/3 失敗の下端 0.292 > 0.10
    assert summary["run_id"].endswith("_ceiling_remedy")


def test_a_smoke_does_not_evaluate_the_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remedy_path, remedy = build_small_run(tmp_path, monkeypatch)
    fake_lmm_fits(monkeypatch, failed=False)
    spec = ceiling_remedy.load_eval_spec(remedy, {}, None, None)
    summary = ceiling_remedy.run(remedy, remedy_path, tmp_path / "eval", spec, max_rep=1)
    assert summary["gates"]["evaluated"] is False
    point = summary["sheets"]["ceiling_null_L05"]["points"][0]
    assert point["g1"]["closed"] is None and point["g2"]["closed"] is None


def test_a_tampered_frame_stops_the_evaluation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remedy_path, remedy = build_small_run(tmp_path, monkeypatch)
    fake_lmm_fits(monkeypatch, failed=False)
    frame = tmp_path / "source" / "ceiling_null_L05" / "frames" / "frame_n4_s1_r0_0001.csv"
    lines = frame.read_text(encoding="ascii").splitlines()
    last = lines[-1]
    lines[-1] = last[:-1] + ("0" if last.endswith("1") else "1")
    frame.write_text("\n".join(lines) + "\n", encoding="ascii")
    spec = ceiling_remedy.load_eval_spec(remedy, {}, None, None)
    with pytest.raises(power_sim.PowerSimError, match="組み直した"):
        ceiling_remedy.run(remedy, remedy_path, tmp_path / "eval", spec, max_rep=3)


def test_sources_that_disagree_on_the_fit_procedure_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-133 決定1: どの元の run も同じ当てはめの手続き(fit)でなければならない。"""
    _, remedy = build_small_run(tmp_path, monkeypatch)
    other = small_source_config()
    other["sheets"] = [dict(other["sheets"][0], id="ceiling_other")]
    other["fit"]["refit"]["loglik_tolerance"] = 0.01
    other_path = tmp_path / "other.yaml"
    other_path.write_text(yaml.safe_dump(other, allow_unicode=True), encoding="utf-8")
    remedy["sources"].append({"id": "other", "config": str(other_path), "results_dir": str(tmp_path), "run_id": None})
    with pytest.raises(power_sim.ConfigError, match="fit"):
        ceiling_remedy.load_eval_spec(remedy, {}, None, None)
