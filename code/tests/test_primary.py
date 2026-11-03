"""実データの主要解析 `primary.py`(PLAN-048 I1〜I9)のテスト。

答える問い: 「順(フィルタ → df → 天井 → 当てはめ)は崩れないか。天井・df・当てはめ失敗の行で p 値が表に出ないか。
`null` が残っていれば実データの実行は止まるか。入れ替えは被覆の中の項目単位で、主要検定の帰無を保つか」

**R を呼ぶのは 2 本だけ**(ランクの照合と、当てはめを通す 1 本)。他は当てはめを偽物に差す。
**ここに出る数は実験結果ではない**(配線の確認。`CLAUDE.md` §2)。
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy import stats

from code.analysis import frame, power_sim, primary
from code.config import ConfigError, load_config, resolve_repo_path
from code.rates import CORRECT
from code.tests import test_power_sim as ps_tests

CONFIG_PATH = Path("configs/primary.yaml")
TASKS = ("t1", "t2")
COVERAGES = ("id", "interp", "extrap_magnitude")
CELLS = tuple((t, c) for t in TASKS for c in COVERAGES)
N_ITEM = 4
N_SEED = 10


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    return load_config(resolve_repo_path(CONFIG_PATH))


@pytest.fixture(scope="module")
def power_config(config: dict[str, Any]) -> dict[str, Any]:
    return primary.load_power_config(config)


@pytest.fixture(scope="module")
def spec(config: dict[str, Any], power_config: dict[str, Any]) -> primary.Spec:
    return primary.load_spec(config, power_config)


def one_row(
    condition: str, seed: int, item: str, task: str, coverage: str, is_rule: int,
    classification: str = "other_error", template: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": f"{condition}_s{seed}", "condition": condition, "seed": seed, "item": item, "task": task,
        "template": template or f"{task}_tmpl", "category": template or f"{task}_tmpl", "coverage": coverage,
        "is_rule": is_rule, "classification": classification, "main_axis": True,
        "gate_id_rule_rate": 0.5, "gate_id_n": 40,
    }


def make_rows(rule=lambda t, c, k, s: (k + s) % 2, correct=lambda t, c, k: 1) -> list[dict[str, Any]]:
    """p2 の行(10 シード × 6 セル × `N_ITEM` 項目)と ident の行。`rule` / `correct` で形を決める。"""
    rows = []
    for (task, coverage), seed, k in itertools.product(CELLS, range(N_SEED), range(N_ITEM)):
        item = f"{task}.{coverage}.{k:04d}"
        rows.append(one_row("p2", seed, item, task, coverage, rule(task, coverage, k, seed)))
        ok = correct(task, coverage, k)
        rows.append(one_row("ident", seed, item, task, coverage, 0, CORRECT if ok else "other_error"))
    return rows


class FakeFitter:
    """R の代わり。呼ばれた回数と表を記録する。"""

    def __init__(self, **overrides: Any) -> None:
        self.calls: list[tuple[list[tuple[Any, ...]], Path]] = []
        self.overrides = {"df": 2.0, "reduction_label": "none", "p_value": 0.03, **overrides}

    def __call__(self, table, work_dir):
        self.calls.append((list(table), work_dir))
        return ps_tests.fit_result(self.overrides["p_value"], **{k: v for k, v in self.overrides.items() if k != "p_value"})


def analyse(rows, spec, fitter, tmp_path, dropped=frozenset()):
    return primary.analyse(rows, set(dropped), spec, fitter, tmp_path)


# --------------------------------------------------------------------------
# I1 config
# --------------------------------------------------------------------------


def test_the_undecided_values_stay_null_and_the_fit_settings_are_not_duplicated(config) -> None:
    """ADR-138 決定2・3: 閾値と Δ は null のまま(エージェントは値を入れない)。当てはめの設定は持たない。"""
    assert config["analysis_gate"]["threshold"] is None
    assert config["tost"]["delta"] is None
    assert not {"fit", "refit", "allfit", "reduction_order", "alpha", "tost_alpha"} & set(config)


def test_the_spec_reads_alpha_and_tost_alpha_from_power_sim(spec, power_config) -> None:
    assert spec.alpha == power_config["simulation"]["alpha"]
    assert spec.tost_alpha == power_config["simulation"]["tost_alpha"]
    assert (spec.tasks, spec.coverages, spec.n_seed) == (TASKS, COVERAGES, N_SEED)
    assert spec.min_reference_correct_rate == 0.70


def test_the_simulate_targets_are_points_of_the_power_sim_grid(config, power_config) -> None:
    for target in config["simulate"]["targets"].values():
        assert target["n_item"] in power_config["dgp"]["n_item"]
        assert target["sigma"] in power_config["dgp"]["sigma"]
        assert target["rho"] in power_config["dgp"]["rho"]


# --------------------------------------------------------------------------
# I2 読み込みと照合 / 未決の値で止まる
# --------------------------------------------------------------------------


def test_all_four_undecided_items_are_listed_and_an_override_removes_only_its_own(config) -> None:
    listed = primary.pending_decisions(config, None, None)
    assert len(listed) == 4
    assert len(primary.pending_decisions(config, Path("f"), None)) == 3
    assert len(primary.pending_decisions(config, Path("f"), Path("g"))) == 2


def test_a_real_run_stops_when_anything_is_null_and_writes_nothing(config, tmp_path, capsys) -> None:
    code = primary.main(["--out-dir", str(tmp_path)])
    assert code == primary.EXIT_PENDING
    assert list(tmp_path.iterdir()) == []
    assert "tost.delta" in capsys.readouterr().out


def test_a_filled_threshold_still_stops_because_the_gate_position_is_undecided(config) -> None:
    filled = json.loads(json.dumps(config))
    filled["analysis_gate"]["threshold"] = 0.5
    filled["tost"]["delta"] = 0.5
    with pytest.raises(primary.PendingDecisionError, match="順"):
        primary.require_decided(filled, Path("f"), Path("g"))


def write_frame_dir(directory: Path, rows: list[dict[str, Any]], **tamper: Any) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / frame.CSV_FILENAME
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frame.COLUMNS), lineterminator="\n", restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items() if k in frame.COLUMNS})
    manifest = {"csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "n_rows": len(rows), "problems": []}
    manifest.update(tamper)
    (directory / frame.FRAME_MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")


def test_read_frame_round_trips_the_types(tmp_path) -> None:
    rows = make_rows()
    write_frame_dir(tmp_path, rows)
    back = primary.read_frame(tmp_path)
    assert len(back) == len(rows)
    assert back[0]["seed"] == 0 and back[0]["is_rule"] in (0, 1) and back[0]["main_axis"] is True
    assert back[0]["gate_id_rule_rate"] == 0.5 and back[0]["gate_id_n"] == 40


@pytest.mark.parametrize("tamper", [{"csv_sha256": "0" * 64}, {"n_rows": 3}, {"problems": ["x"]}])
def test_read_frame_stops_when_the_record_disagrees(tmp_path, tamper) -> None:
    write_frame_dir(tmp_path, make_rows(), **tamper)
    with pytest.raises(primary.PrimaryError):
        primary.read_frame(tmp_path)


# --------------------------------------------------------------------------
# I3 主軸の subset と適格性フィルタ
# --------------------------------------------------------------------------


def test_select_keeps_only_the_primary_condition_main_axis_and_the_six_cells(spec) -> None:
    rows = make_rows()
    rows.append(one_row("p2", 0, "t3.id.0000", "t3", "id", 1))                  # 主軸外のタスク型
    rows.append(one_row("p2", 0, "t1.oob.0000", "t1", "oob_algebraic", 1))       # 主軸外の被覆
    off = one_row("p2", 0, "t1.id.9999", "t1", "id", 1)
    off["main_axis"] = False
    rows.append(off)
    chosen = primary.select_primary_rows(rows, spec)
    assert len(chosen) == len(CELLS) * N_ITEM * N_SEED
    assert {r["condition"] for r in chosen} == {"p2"}


def test_select_stops_when_the_seed_count_is_not_ten(spec) -> None:
    rows = [r for r in make_rows() if r["seed"] != 9]
    with pytest.raises(primary.PrimaryError, match="シード数"):
        primary.select_primary_rows(rows, spec)


def test_select_stops_when_an_item_belongs_to_two_cells_or_a_row_repeats(spec) -> None:
    rows = make_rows()
    moved = dict(next(r for r in rows if r["condition"] == "p2"))
    moved["coverage"] = "interp"
    with pytest.raises(primary.PrimaryError, match="複数のセル"):
        primary.select_primary_rows([*rows, moved], spec)
    with pytest.raises(primary.PrimaryError, match="2 つある"):
        primary.select_primary_rows([*rows, dict(rows[0])], spec)


def test_the_filter_drops_by_ident_by_order6_and_by_both_and_exactly_the_threshold_passes(spec) -> None:
    # t1.interp は ident の correct_rate が 0.5(4 項目中 2)で落ちる。下では全セルを閾値ちょうど / 直下に置いて境界を見る
    rows = make_rows(correct=lambda t, c, k: int(k < 2) if (t, c) == ("t1", "interp") else 1)
    rates = primary.reference_correct_rates(rows, spec)
    assert rates[("t1", "interp")] == 0.5 and rates[("t2", "id")] == 1.0
    result = primary.eligibility(rates, {("t1", "interp"), ("t2", "extrap_magnitude")}, spec)
    assert result["dropped"] == {
        "t1.interp": [primary.REASON_REFERENCE, primary.REASON_ORDER6],
        "t2.extrap_magnitude": [primary.REASON_ORDER6],
    }
    assert result["kept"] == ["t1.id", "t1.extrap_magnitude", "t2.id", "t2.interp"]
    at_threshold = {cell: spec.min_reference_correct_rate for cell in CELLS}
    assert primary.eligibility(at_threshold, set(), spec)["dropped"] == {}
    below = {**at_threshold, ("t1", "id"): spec.min_reference_correct_rate - 1e-9}
    assert list(primary.eligibility(below, set(), spec)["dropped"]) == ["t1.id"]


def test_a_cell_without_ident_rows_stops_instead_of_passing(spec) -> None:
    rows = [r for r in make_rows() if not (r["condition"] == "ident" and (r["task"], r["coverage"]) == ("t2", "id"))]
    with pytest.raises(primary.PrimaryError, match="t2.id"):
        primary.reference_correct_rates(rows, spec)


def test_the_order6_cells_are_the_union_of_failing_cells_in_the_design(spec, tmp_path) -> None:
    def cells(failing):
        return [{"task": t, "coverage": c, "fails": (t, c) in failing} for t in ("t1", "t2", "t3") for c in COVERAGES]

    report = {"runs": [{"cells": cells({("t1", "id")})}, {"cells": cells({("t2", "interp"), ("t3", "id")})}]}
    path = tmp_path / "gonogo.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert primary.order6_dropped_cells(path, spec) == {("t1", "id"), ("t2", "interp")}
    path.write_text(json.dumps({"runs": []}), encoding="utf-8")
    with pytest.raises(primary.PrimaryError):
        primary.order6_dropped_cells(path, spec)


# --------------------------------------------------------------------------
# I4 df のランク規則
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kept", "df"),
    [
        (CELLS, 2),
        (tuple(c for c in CELLS if c != ("t1", "id")), 1),                         # 1 セル落ちれば df = 1
        (tuple(c for c in CELLS if c[0] == "t1"), 0),                                # タスク型が丸ごと落ちる
        (tuple(c for c in CELLS if c[1] != "extrap_magnitude"), 1),                  # 2 × 2
        ((("t1", "id"), ("t2", "interp")), 0),
        ((), 0),
    ],
)
def test_the_rank_rule_gives_the_df_of_the_kept_cells(spec, kept, df) -> None:
    ranks = primary.design_ranks(kept, spec)
    assert ranks["df"] == df == ranks["rank_full"] - ranks["rank_add"]


def find_rscript() -> str | None:
    try:
        return power_sim.resolve_rscript(None)
    except power_sim.PowerSimError:
        return None


@pytest.mark.skipif(find_rscript() is None, reason="Rscript が無い")
def test_the_python_rank_agrees_with_rs_qr_rank_for_every_usable_subset_of_the_six_cells(spec, tmp_path) -> None:
    """R を呼ぶテスト 1/2。`qr(model.matrix(...))$rank` の差と同じ df になる(PLAN-048 I4)。

    R の `model.matrix` は水準が 1 つに落ちた因子で失敗するので、タスク型が 2 つ・被覆が 2 水準以上残る部分集合だけを比べる。
    """
    usable = [
        s for n in range(2, 7) for s in itertools.combinations(CELLS, n)
        if len({t for t, _ in s}) == 2 and len({c for _, c in s}) >= 2
    ]
    newline = chr(10)    # 文字列リテラルに改行の記号を書かない(置換の途中で壊れやすい)
    subsets = ("," + newline).join(
        "c(%s)" % ",".join(str(CELLS.index(cell) + 1) for cell in s) for s in usable)
    script = tmp_path / "rank.R"
    lines = [
        "cells <- data.frame(task = c(%s), coverage = c(%s))" % (
            ",".join(f'"{t}"' for t, _ in CELLS), ",".join(f'"{c}"' for _, c in CELLS)),
        "cells$coverage <- relevel(factor(cells$coverage), ref = 'id')",
        "cells$task <- factor(cells$task)",
        "rk <- function(f, d) qr(model.matrix(f, d))$rank",
        "for (m in list(%s)) {" % subsets,
        "  d <- cells[m, ]; d$task <- droplevels(d$task); d$coverage <- droplevels(d$coverage)",
        "  cat(rk(~ task * coverage, d) - rk(~ task + coverage, d), fill = TRUE)",
        "}",
    ]
    script.write_text(newline.join(lines) + newline, encoding="ascii", newline=newline)
    done = subprocess.run([find_rscript(), str(script)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    from_r = [int(x) for x in done.stdout.split()]
    assert len(from_r) == len(usable) > 0
    assert from_r == [primary.design_ranks(s, spec)["df"] for s in usable]


# --------------------------------------------------------------------------
# I5 天井
# --------------------------------------------------------------------------


def test_the_ceiling_is_judged_per_declared_kept_cell_without_the_missing_cell_error(spec) -> None:
    rows = [r for r in make_rows(rule=lambda t, c, k, s: 1 if (t, c) == ("t1", "id") else (k + s) % 2)
            if r["condition"] == "p2"]
    kept = [c for c in CELLS if c != ("t2", "interp")]                         # 欠けたセルがあっても止まらない
    verdict = primary.judge_ceiling(rows, kept)
    assert verdict.ceiling and verdict.hits == (("t1", "id", "all_rule"),)
    assert verdict.n_per_cell == (N_ITEM * N_SEED,) * len(kept)


def test_a_dropped_cell_on_the_ceiling_is_not_judged_and_zero_rule_is_the_other_direction(spec) -> None:
    rows = [r for r in make_rows(rule=lambda t, c, k, s: 1 if (t, c) == ("t1", "id") else 0 if (t, c) == ("t2", "id") else (k + s) % 2)
            if r["condition"] == "p2"]
    kept = [c for c in CELLS if c != ("t1", "id")]
    assert primary.judge_ceiling(rows, kept).hits == (("t2", "id", "no_rule"),)
    assert primary.judge_ceiling(rows, [("t1", "interp")]).ceiling is False
    assert primary.judge_ceiling(rows, []).ceiling is False


# --------------------------------------------------------------------------
# 順と判定(I6・I7・I8 の経路)
# --------------------------------------------------------------------------


def test_the_ok_path_fits_once_with_the_kept_rows_and_reports_the_p_value(spec, tmp_path) -> None:
    fitter = FakeFitter()
    result = analyse(make_rows(), spec, fitter, tmp_path)
    assert result["verdict"] == primary.VERDICT_OK and result["df"]["df"] == 2
    assert len(fitter.calls) == 1 and len(fitter.calls[0][0]) == len(CELLS) * N_ITEM * N_SEED
    assert fitter.calls[0][0][0] == ("s00", "t1", "extrap_magnitude", "t1.extrap_magnitude.0000", "t1_tmpl", 0)
    row = primary.report_row(result)
    assert row[0] == primary.VERDICT_OK and row[5] == "0.03"


def test_a_dropped_cell_gives_df_one_and_does_not_fit_but_records_the_ceiling_of_the_rest(spec, tmp_path) -> None:
    rows = make_rows(rule=lambda t, c, k, s: 1 if (t, c) == ("t2", "id") else (k + s) % 2,
                     correct=lambda t, c, k: 0 if (t, c) == ("t1", "interp") else 1)
    fitter = FakeFitter()
    result = analyse(rows, spec, fitter, tmp_path)
    assert fitter.calls == []
    assert result["verdict"] == primary.VERDICT_DF and result["df"]["df"] == 1 and result["fit"] is None
    assert result["ceiling"]["ceiling_hits"] == [["t2", "id", "all_rule"]]
    assert "t1.interp" not in result["ceiling"]["judged_cells"]
    row = primary.report_row(result)
    assert row[1] == "t1.interp(ident)" and row[5] == row[6] == row[7] == row[8] == ""


def test_the_ceiling_still_fits_keeps_the_p_value_in_the_json_and_hides_it_in_the_table(spec, tmp_path) -> None:
    fitter = FakeFitter(p_value=0.0123)
    result = analyse(make_rows(rule=lambda t, c, k, s: 1 if (t, c) == ("t1", "id") else (k + s) % 2),
                     spec, fitter, tmp_path)
    assert len(fitter.calls) == 1
    assert result["verdict"] == primary.VERDICT_CEILING
    assert result["fit"]["p_value"] == 0.0123 and result["tost"] is not None
    row = primary.report_row(result)
    assert row[3] == "t1.id:all_rule" and row[5:] == ["", "", "", ""]
    assert "0.0123" not in primary.render_report({"run_id": "r", "mode": "actual", "git_sha": "g"}, {"x": result})


def test_a_failed_fit_is_reported_as_not_feasible_with_no_p_value(spec, tmp_path) -> None:
    result = analyse(make_rows(), spec, FakeFitter(fit_failed=True, p_value=None), tmp_path)
    assert result["verdict"] == primary.VERDICT_FIT and result["tost"] is None
    assert primary.report_row(result)[5:] == ["", "", "", ""]


def test_df_in_the_r_output_must_agree_with_the_rank_rule(spec, tmp_path) -> None:
    with pytest.raises(primary.PrimaryError, match="df"):
        analyse(make_rows(), spec, FakeFitter(df=1.0), tmp_path)


def test_the_filter_comes_before_the_ceiling(spec, tmp_path) -> None:
    """ident で落ちたセルが天井でも、天井の判定には入らない(順: フィルタ → df → 天井)。"""
    rows = make_rows(rule=lambda t, c, k, s: 1 if (t, c) == ("t1", "id") else (k + s) % 2,
                     correct=lambda t, c, k: 0 if (t, c) == ("t1", "id") else 1)
    result = analyse(rows, spec, FakeFitter(), tmp_path)
    assert result["verdict"] == primary.VERDICT_DF and result["ceiling"]["ceiling"] is False


def test_the_report_puts_the_verdict_and_the_dropped_cells_to_the_left_of_the_p_value() -> None:
    header = list(primary.REPORT_HEADER)
    assert header[0] == "判定" and header.index("落ちたセル") < header.index("df") < header.index("LRT の p 値")
    assert header.index("判定") < header.index("LRT の p 値") < header.index("TOST の最小 Δ")


# --------------------------------------------------------------------------
# TOST と解析門の口
# --------------------------------------------------------------------------


def test_tost_gives_the_minimum_delta_and_judges_equivalence_only_when_delta_is_set(spec, tmp_path) -> None:
    fit = ps_tests.fit_result(0.5, interaction_interp_est=-0.1, interaction_interp_se=0.1,
                              interaction_extrap_magnitude_est=0.05, interaction_extrap_magnitude_se=0.2)
    z = 1.6448536269514722
    expected = max(0.1 + z * 0.1, 0.05 + z * 0.2)
    undecided = primary.tost_record(fit, spec)
    assert undecided["min_delta"] == pytest.approx(expected) and undecided["equivalent"] is None
    import dataclasses
    assert primary.tost_record(fit, dataclasses.replace(spec, delta=expected + 0.01))["equivalent"] is True
    assert primary.tost_record(fit, dataclasses.replace(spec, delta=expected - 0.01))["equivalent"] is False
    assert primary.tost_record(ps_tests.failed_fit(), spec) is None


def test_the_gate_records_the_raw_rates_and_applies_nothing(spec, tmp_path) -> None:
    result = analyse(make_rows(), spec, FakeFitter(), tmp_path)
    gate = result["analysis_gate"]
    assert gate["applied"] is False and gate["threshold"] is None
    assert gate["runs"]["p2_s0"] == {"gate_id_rule_rate": 0.5, "gate_id_n": 40}
    assert len(gate["runs"]) == N_SEED


# --------------------------------------------------------------------------
# I9 shuffle
# --------------------------------------------------------------------------


def two_template_rows() -> list[dict[str, Any]]:
    """t1 は template 1 種、t2 は 2 種。項目は 6 つずつ(被覆の水準の中で入れ替わる)。"""
    rows = []
    for (task, coverage), k in itertools.product(CELLS, range(6)):
        template = "t1" if task == "t1" else f"t2_{k % 2}"
        item = f"{task}.{coverage}.{k:04d}"
        for seed in range(N_SEED):
            rows.append(one_row("p2", seed, item, task, coverage, (k + seed) % 2, template=template))
            rows.append(one_row("ident", seed, item, task, coverage, 0, CORRECT, template=template))
    return rows


def cell_sizes(rows, spec) -> dict[tuple[str, str], int]:
    sizes: dict[tuple[str, str], set[str]] = {}
    for r in rows:
        if r["condition"] == spec.condition:
            sizes.setdefault((r["task"], r["coverage"]), set()).add(r["item"])
    return {cell: len(items) for cell, items in sizes.items()}


def test_shuffle_moves_task_labels_by_item_inside_each_coverage_and_keeps_the_cell_sizes(spec) -> None:
    rows = two_template_rows()
    shuffled, record = primary.shuffle_task_labels(rows, spec, np.random.default_rng(1))
    assert cell_sizes(shuffled, spec) == cell_sizes(rows, spec)
    by_item = {}
    for r in shuffled:
        if r["condition"] == "p2":
            by_item.setdefault(r["item"], set()).add(r["task"])
    assert all(len(tasks) == 1 for tasks in by_item.values())                    # 項目の全シードの行が同じ task
    assert {(r["coverage"], r["item"]) for r in shuffled} == {(r["coverage"], r["item"]) for r in rows}
    assert record["n_items_moved"] > 0
    primary.select_primary_rows(shuffled, spec)                                  # 主解析集合の前提(入れ子・10 シード)を保つ


def test_shuffle_leaves_ident_and_is_rule_alone_and_records_the_template_break(spec) -> None:
    rows = two_template_rows()
    shuffled, record = primary.shuffle_task_labels(rows, spec, np.random.default_rng(2))
    assert [r for r in shuffled if r["condition"] == "ident"] == [r for r in rows if r["condition"] == "ident"]
    assert [r["is_rule"] for r in shuffled] == [r["is_rule"] for r in rows]
    assert [r["template"] for r in shuffled] == [r["template"] for r in rows]
    assert record["mixed_templates"]                                              # t2 の template が t1 に移る


def test_shuffle_is_deterministic_in_the_seed_and_does_not_touch_the_input(spec) -> None:
    rows = two_template_rows()
    before = [dict(r) for r in rows]
    a, _ = primary.shuffle_task_labels(rows, spec, np.random.default_rng(3))
    b, _ = primary.shuffle_task_labels(rows, spec, np.random.default_rng(3))
    c, _ = primary.shuffle_task_labels(rows, spec, np.random.default_rng(4))
    assert a == b and a != c and rows == before


def interaction_f_p_value(rows: list[dict[str, Any]]) -> float:
    """R を使わない代わりの検定。項目ごとの経験ロジット平均に対する OLS の `task:coverage` の F 検定(df = 2)。

    答える問い: 入れ替えた表で、項目単位の検定は α を超えて棄却しないか。**本番の LRT ではない**(配線の確認の代役)。
    """
    per_item: dict[str, list[float]] = {}
    label: dict[str, tuple[str, str]] = {}
    for r in rows:
        if r["condition"] == "p2":
            per_item.setdefault(r["item"], []).append(r["is_rule"])
            label[r["item"]] = (r["task"], r["coverage"])
    items = sorted(per_item)
    rate = np.array([(sum(per_item[i]) + 0.5) / (len(per_item[i]) + 1.0) for i in items])
    y = np.log(rate / (1.0 - rate))
    t = np.array([float(label[i][0] == "t2") for i in items])
    cov = np.array([[float(label[i][1] == c) for c in COVERAGES[1:]] for i in items])
    add = np.column_stack([np.ones(len(items)), t, cov])
    full = np.column_stack([add, cov * t[:, None]])

    def rss(x):
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        return float(((y - x @ beta) ** 2).sum())

    df_resid = len(items) - full.shape[1]
    f_stat = ((rss(add) - rss(full)) / 2.0) / (rss(full) / df_resid)
    return float(stats.f.sf(f_stat, 2, df_resid))


def test_the_shuffled_null_does_not_reject_more_often_than_alpha_while_the_real_interaction_does(
    spec, config, power_config
) -> None:
    """PLAN-016 §7-6 の回帰(回数は `N_SHUFFLE`)。P1(交互作用あり)を入れ替えると、棄却は α の二項の上側限界以下。"""
    n_shuffle = 200
    upper_quantile = 0.99
    rows = simulated_rows(config, power_config, "P1")
    assert interaction_f_p_value(rows) < spec.alpha                               # 代役の検定が元の表の交互作用を拾う
    rejected = sum(
        interaction_f_p_value(primary.shuffle_task_labels(rows, spec, np.random.default_rng(seed))[0]) < spec.alpha
        for seed in range(n_shuffle)
    )
    assert rejected <= stats.binom.ppf(upper_quantile, n_shuffle, spec.alpha)


# --------------------------------------------------------------------------
# I9 simulate
# --------------------------------------------------------------------------


def simulated_rows(config, power_config, label: str, seed: int = 0) -> list[dict[str, Any]]:
    index = list(config["simulate"]["targets"]).index(label)
    return primary.simulated_frame(config["simulate"]["targets"][label], label, index, seed, power_config, config)


def test_the_simulated_frame_has_the_frame_shape_and_the_reference_rate_from_config(spec, config, power_config) -> None:
    rows = simulated_rows(config, power_config, "P0")
    assert {r["condition"] for r in rows} == {"p2", "ident"} and {r["task"] for r in rows} == set(TASKS)
    assert len(primary.select_primary_rows(rows, spec)) == 6 * 80 * N_SEED
    rates = primary.reference_correct_rates(rows, spec)
    assert set(rates.values()) == {config["simulate"]["reference_correct_rate"]}
    assert primary.eligibility(rates, set(), spec)["dropped"] == {}
    assert rows == simulated_rows(config, power_config, "P0")
    assert [r["is_rule"] for r in rows] != [r["is_rule"] for r in simulated_rows(config, power_config, "P0", seed=1)]


def test_the_simulated_p0_and_p1_use_independent_streams_and_a_point_off_the_grid_stops(config, power_config) -> None:
    assert [r["is_rule"] for r in simulated_rows(config, power_config, "P0")] != [
        r["is_rule"] for r in simulated_rows(config, power_config, "P1")]
    off = {**config["simulate"]["targets"]["P0"], "sigma": 0.3}
    with pytest.raises(ConfigError):
        primary.simulated_frame(off, "P0", 0, 0, power_config, config)


def fake_main_fitter(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []

    def make(power_config, rscript_override):
        def fit(table, work_dir):
            calls.append(len(table))
            return ps_tests.fit_result(0.04, df=2.0, reduction_label="none")
        return fit

    monkeypatch.setattr(primary, "make_r_fitter", make)
    return calls


def test_simulate_runs_p0_and_p1_through_every_stage_and_writes_the_outputs(tmp_path, monkeypatch) -> None:
    calls = fake_main_fitter(monkeypatch)
    assert primary.main(["--simulate", "--out-dir", str(tmp_path)]) == primary.EXIT_OK
    (run_dir,) = list(tmp_path.iterdir())
    payload = json.loads((run_dir / primary.PRIMARY_JSON).read_text(encoding="utf-8"))
    assert list(payload["targets"]) == ["P0", "P1"] and calls == [6 * 80 * N_SEED] * 2
    assert {t["verdict"] for t in payload["targets"].values()} == {primary.VERDICT_OK}
    report = (run_dir / primary.REPORT_MD).read_text(encoding="utf-8")
    assert "## P0" in report and "## P1" in report and "実験結果ではない" in report
    assert "(0 + coverage | seed)" in report and "(1 | seed)" in report
    assert report.count("| 判定 | 落ちたセル | df | 天井(セルと向き) | 縮退の段 | LRT の p 値 |") == 2
    assert (run_dir / primary.PRIMARY_CONFIG_COPY).exists() and (run_dir / primary.POWER_CONFIG_COPY).exists()
    assert (run_dir / "git_sha.txt").exists()


def test_shuffle_labels_runs_the_synthetic_p1_when_no_frame_is_given(tmp_path, monkeypatch) -> None:
    fake_main_fitter(monkeypatch)
    assert primary.main(["--shuffle-labels", "--seed", "0", "--out-dir", str(tmp_path)]) == primary.EXIT_OK
    (run_dir,) = list(tmp_path.iterdir())
    result = json.loads((run_dir / primary.PRIMARY_JSON).read_text(encoding="utf-8"))["targets"]["shuffled"]
    assert result["shuffle"]["seed"] == 0 and result["shuffle"]["n_items_moved"] > 0
    assert result["shuffle"]["mixed_templates"]


def test_shuffle_with_a_frame_needs_the_order6_file(tmp_path, capsys) -> None:
    write_frame_dir(tmp_path / "f", make_rows())
    code = primary.main(["--shuffle-labels", "--frame-dir", str(tmp_path / "f"), "--out-dir", str(tmp_path / "o")])
    assert code == primary.EXIT_ERROR and "order6" in capsys.readouterr().out


def test_simulate_and_shuffle_are_exclusive() -> None:
    with pytest.raises(SystemExit):
        primary.main(["--simulate", "--shuffle-labels"])


# --------------------------------------------------------------------------
# I10 R を実際に通す 1 本
# --------------------------------------------------------------------------


@pytest.mark.skipif(find_rscript() is None, reason="Rscript が無い")
def test_one_real_fit_goes_through_power_sim_fit_r_and_returns_a_verdict(spec, power_config, tmp_path) -> None:
    """R を呼ぶテスト 2/2(壁時計は PLAN-048 §11)。小さい表を `make_r_fitter` で `power_sim_fit.R` に通す。

    **値の読みはしない**。配線(CSV → manifest → R → JSON → 判定)と、R の df が計画行列のランクと合うことを見る。
    """
    rng = np.random.default_rng(0)
    rows = []
    for (task, coverage), k in itertools.product(CELLS, range(12)):
        item = f"{task}.{coverage}.{k:04d}"
        template = "t1" if task == "t1" else f"t2_{k % 5}"
        item_effect = rng.normal(0.0, 1.0)
        for seed in range(N_SEED):
            rows.append(one_row("p2", seed, item, task, coverage, int(rng.random() < 1 / (1 + np.exp(-item_effect))), template=template))
            rows.append(one_row("ident", seed, item, task, coverage, 0, CORRECT, template=template))
    result = primary.analyse(rows, set(), spec, primary.make_r_fitter(power_config, None), tmp_path)
    assert result["verdict"] in {primary.VERDICT_OK, primary.VERDICT_FIT, primary.VERDICT_CEILING}
    assert result["fit"]["n_rows"] == 6 * 12 * N_SEED
    assert (tmp_path / primary.TABLE_CSV).exists() and (tmp_path / primary.FIT_JSON).exists()
