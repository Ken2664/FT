"""天井の規則を run3 の検出力のシミュレーションに入れる(PLAN-047 I2〜I4 / ADR-137 決定1・4・5・6)のテスト。

答える問い: 「天井の規則が当たった反復は、当てはめが成功していても分母に入れて非棄却に数え、TOST は Δ = +∞ になるか。
実行可能性の門の分子は当てはめ失敗だけのままか。天井でない表の要約は従来と同じ数か。`ceiling_probe` は判定しないか。
旧い出力(欄なし)は読めるか。規則の移動で判定は変わらないか」

**R は呼ばない**(当てはめは偽物を差す)。**ここに出る数は実験結果ではない**(配線の確認)。
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from code.analysis import ceiling, ceiling_remedy, power_sim
from code.tests import test_ceiling_probe as probe_tests
from code.tests import test_power_sim as ps_tests

REPO_ROOT = Path(__file__).resolve().parents[2]
KEY = power_sim.PointKey(n_item=80, sigma=0.5, rho=0.0)
TASKS = ("T1", "T2")
COVERAGES = ("id", "interp", "extrap_magnitude")
HIT = ("T1", "id", "all_rule")


def on_ceiling(p_value: float | None, **overrides: Any) -> dict[str, Any]:
    """天井と判定された反復の記録(当てはめの JSON + 判定)。"""
    return ps_tests.fit_result(p_value, **ceiling.verdict_record(
        ceiling.CeilingVerdict(True, (HIT,), (6,) * 6)), **overrides)


def off_ceiling(p_value: float | None, **overrides: Any) -> dict[str, Any]:
    """天井でないと判定された反復の記録。"""
    return ps_tests.fit_result(p_value, **ceiling.verdict_record(
        ceiling.CeilingVerdict(False, (), (6,) * 6)), **overrides)


def failed_on_ceiling() -> dict[str, Any]:
    return ps_tests.failed_fit(**ceiling.verdict_record(ceiling.CeilingVerdict(True, (HIT,), (6,) * 6)))


# --------------------------------------------------------------------------
# I1 規則の移動
# --------------------------------------------------------------------------


def test_the_rule_moved_without_changing_what_it_returns() -> None:
    """★罠5: `ceiling_remedy` から引いても同じ関数・同じ型・同じ例外である(規則の中身は変えていない)。"""
    assert ceiling_remedy.ceiling_rule is ceiling.ceiling_rule
    assert ceiling_remedy.CeilingVerdict is ceiling.CeilingVerdict
    assert ceiling_remedy.CeilingRuleError is ceiling.CeilingRuleError
    assert (ceiling_remedy.DIRECTION_ALL_RULE, ceiling_remedy.DIRECTION_NO_RULE) == ("all_rule", "no_rule")
    rows = [("s0", t, c, f"i{k}", "t", 1 if (t, c) == ("T1", "id") else k % 2)
            for t in TASKS for c in COVERAGES for k in range(4)]
    verdict = ceiling.ceiling_rule(rows, TASKS, COVERAGES)
    assert verdict == ceiling.CeilingVerdict(True, (HIT,), (4,) * 6)


def test_the_shared_module_does_not_import_power_sim() -> None:
    """循環 import の見張り: `ceiling.py` だけを読んでも `power_sim` は読み込まれない。"""
    code = (
        "import sys; import code.analysis.ceiling; "
        "sys.exit(1 if 'code.analysis.power_sim' in sys.modules else 0)"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_the_verdict_record_has_the_decided_shape_and_reads_back() -> None:
    verdict = ceiling.CeilingVerdict(True, (HIT, ("T2", "interp", "no_rule")), (3,) * 6)
    record = ceiling.verdict_record(verdict)
    assert record == {
        "ceiling": True,
        "ceiling_hits": [["T1", "id", "all_rule"], ["T2", "interp", "no_rule"]],
        "ceiling_n_per_cell": [3] * 6,
    }
    json.dumps(record, allow_nan=False)
    assert ceiling.record_verdict(record) is True
    assert ceiling.record_verdict(ceiling.verdict_record(ceiling.CeilingVerdict(False, (), (3,) * 6))) is False


def test_a_record_without_the_field_is_no_verdict_not_no_ceiling() -> None:
    """★決定6: 旧い出力(欄なし)は「判定なし」= `None`。「天井でない」に倒さない。真偽値でない欄は止まる。"""
    assert ceiling.record_verdict(ps_tests.fit_result(0.1)) is None
    with pytest.raises(ceiling.CeilingRuleError, match="真偽値"):
        ceiling.record_verdict({"ceiling": 1})


# --------------------------------------------------------------------------
# I3 集計
# --------------------------------------------------------------------------


def test_a_ceiling_repetition_stays_in_the_denominator_as_a_non_rejection() -> None:
    """★決定4: 天井の反復は当てはめが成功して p < alpha でも棄却に数えず、分母に残る。"""
    results = [on_ceiling(0.01), on_ceiling(0.01), off_ceiling(0.01), off_ceiling(0.5)]
    pt = power_sim.summarise_point(KEY, results, 0.05)
    assert (pt.n_rep, pt.n_reject, pt.power) == (4, 1, 0.25)
    assert (pt.n_success, pt.n_reject_success) == (4, 3)            # 成功した反復の中の棄却は記述として 3
    assert (pt.n_ceiling_judged, pt.n_ceiling, pt.n_noceiling) == (4, 2, 2)
    assert (pt.n_reject_noceiling) == 1                              # 天井でない反復だけ: 1 / 2
    assert (pt.n_ceiling_descriptive, pt.n_ceiling_descriptive_reject) == (2, 2)
    assert pt.failed_rate == 0.0                                      # 天井は当てはめ失敗ではない
    intervals = power_sim.point_intervals(pt, 0.95, 0.95)
    assert intervals["rejection"]["rate"] == pytest.approx(0.25)
    assert intervals["rejection_noceiling_only"]["rate"] == pytest.approx(0.5)
    assert intervals["rejection_ceiling_descriptive_only"]["rate"] == pytest.approx(1.0)
    assert intervals["ceiling"]["count"] == 2 and intervals["ceiling"]["n"] == 4
    assert intervals["ceiling"]["ci"] is not None
    json.dumps(intervals, allow_nan=False)


def test_ceiling_repetitions_are_infinite_in_the_tost_reading() -> None:
    """★決定4: 天井の反復は TOST の最小 Δ を持たず、Δ = +∞(同等と言えない)に数える。当てはめ失敗と合わせて数える。"""
    spec = power_sim.tost_spec(ps_tests.load(ps_tests.MAIN_CONFIG), ps_tests.main_profile("P1"))
    results = [
        off_ceiling(0.2, interaction_interp_se=0.1, interaction_extrap_magnitude_se=0.1),
        on_ceiling(0.2),
        ps_tests.failed_fit(**ceiling.verdict_record(ceiling.CeilingVerdict(False, (), (6,) * 6))),
        failed_on_ceiling(),
    ]
    pt = power_sim.summarise_point(KEY, results, 0.05, spec)
    assert len(pt.tost_min_margins) == 1                    # 天井でない成功した反復だけ
    assert pt.tost_n_failed == 2                             # 失敗 2(うち 1 つは天井)
    assert pt.tost_n_ceiling == 1                            # 天井で成功した 1 件(失敗かつ天井は失敗の側で 1 回だけ)
    assert pt.tost_n_infinite == 3
    assert pt.n_ceiling == 2 and pt.n_ceiling_descriptive == 1
    assert power_sim.tost_power(pt.tost_min_margins, 100.0, n_failed=pt.tost_n_infinite) == pytest.approx(0.25)
    quantiles = power_sim.margin_quantiles(pt.tost_min_margins, (0.5, 0.95), n_failed=pt.tost_n_infinite)
    assert quantiles["0.95"] is None
    # TOST を見ないときは天井も数えない(失敗と同じ)
    assert power_sim.summarise_point(KEY, results, 0.05).tost_n_ceiling == 0


def test_the_feasibility_gate_numerator_is_fit_failures_only() -> None:
    """★決定5: 実行可能性の門は当てはめ失敗だけを数える。天井の件数は行の横に並ぶだけで `exceeds` を動かさない。"""
    gate = power_sim.FeasibilityGateSpec(
        ci_level=0.95, lower_bound_above=0.10, scope=power_sim.FEASIBILITY_SCOPE_ALL
    )
    many_ceilings = [on_ceiling(0.5) for _ in range(40)]       # 失敗 0・天井 40/40
    pt = power_sim.summarise_point(KEY, many_ceilings, 0.05)
    rows = power_sim.feasibility_gate({"p1": [pt]}, gate)["sheets"]["p1"]
    assert rows[0]["n_failed"] == 0 and rows[0]["exceeds"] is False
    assert rows[0]["n_ceiling"] == 40 and len(rows[0]["ceiling_ci"]) == 2
    assert power_sim.feasibility_gate({"p1": [pt]}, gate)["closed"] is False


def test_the_error_gate_reads_the_unconditional_rate_with_ceilings_as_non_rejections() -> None:
    """★決定5: 過誤の門の率は天井を非棄却に入れた無条件の率。天井の件数は行の横にある。"""
    gate = power_sim.GateSpec(points=(("misspec", (0.5,)),), ci_level=0.95, lower_bound_above=0.075)
    results = [on_ceiling(0.01) for _ in range(30)] + [off_ceiling(0.5) for _ in range(10)]
    pt = power_sim.summarise_point(KEY, results, 0.05)
    row = power_sim.misspecification_gate({"misspec": [pt]}, gate)["sheets"]["misspec"][0]
    assert row["n_reject"] == 0 and row["rejection_rate"] == 0.0 and row["exceeds"] is False
    assert row["n_reject_success"] == 30 and row["n_ceiling"] == 30


def test_a_table_with_no_ceiling_summarises_as_before() -> None:
    """★罠5・決定6: 天井でないと判定された表は、判定なしの表(従来)と、天井の欄を除いて同じ数。"""
    plain = [ps_tests.fit_result(p) for p in (0.01, 0.2, 0.04, 0.9)] + [ps_tests.failed_fit()]
    judged = [
        {**r, **ceiling.verdict_record(ceiling.CeilingVerdict(False, (), (6,) * 6))} for r in plain
    ]
    spec = power_sim.tost_spec(ps_tests.load(ps_tests.MAIN_CONFIG), ps_tests.main_profile("P1"))
    before = power_sim.summarise_point(KEY, plain, 0.05, spec)
    after = power_sim.summarise_point(KEY, judged, 0.05, spec)
    stripped = {k: v for k, v in dataclasses.asdict(after).items() if k not in power_sim.CEILING_POINT_FIELDS}
    assert stripped == power_sim.point_record(before)
    assert (after.n_ceiling_judged, after.n_ceiling, after.n_noceiling) == (5, 0, 5)
    assert after.n_reject_noceiling == after.n_reject and after.tost_n_ceiling == 0


def test_records_without_a_verdict_read_as_no_verdict_and_hide_the_fields() -> None:
    """★決定6: 旧い出力(欄なし)は読めて、天井の欄を出力に出さない。門の行にも天井の欄を足さない。"""
    legacy = [ps_tests.fit_result(0.01), ps_tests.fit_result(0.5)]
    pt = power_sim.summarise_point(KEY, legacy, 0.05)
    assert pt.n_ceiling_judged == 0 and pt.n_reject == 1
    record = power_sim.point_record(pt)
    assert not set(power_sim.CEILING_POINT_FIELDS) & set(record)
    assert set(power_sim.point_intervals(pt, 0.95, 0.95)) == {
        "rejection", "rejection_success_only", "failed", "rejection_failed_descriptive_only"
    }
    gate = power_sim.FeasibilityGateSpec(0.95, 0.10, power_sim.FEASIBILITY_SCOPE_ALL)
    assert "n_ceiling" not in power_sim.feasibility_gate({"p1": [pt]}, gate)["sheets"]["p1"][0]
    judged = power_sim.summarise_point(KEY, [off_ceiling(0.01)], 0.05)
    assert set(power_sim.CEILING_POINT_FIELDS) <= set(power_sim.point_record(judged))


def test_a_point_mixing_verdicts_and_no_verdicts_stops() -> None:
    """判定のある反復とない反復が混ざる点は、黙って一部だけ B を掛けずに止まる。"""
    with pytest.raises(power_sim.PowerSimError, match="混ざって"):
        power_sim.summarise_point(KEY, [on_ceiling(0.01), ps_tests.fit_result(0.01)], 0.05)


# --------------------------------------------------------------------------
# I2 run の配線
# --------------------------------------------------------------------------


def force_ceiling(monkeypatch: pytest.MonkeyPatch, every: int) -> list[tuple[Path, ...]]:
    """`ceiling_rule` を差し替え、呼ばれた順に `every` 回に 1 回だけ天井と判定する(配線の確認用)。

    呼ばれた時点で、その反復の表の CSV も当てはめの JSON もまだ無いことを記録する(判定は当てはめの前)。
    """
    calls: list[tuple[Path, ...]] = []

    def rule(rows, tasks, coverages):
        calls.append((tuple(tasks), tuple(coverages)))
        hit = len(calls) % every == 0
        return ceiling.CeilingVerdict(hit, (HIT,) if hit else (), (len(rows) // 6,) * 6)

    monkeypatch.setattr(power_sim, "ceiling_rule", rule)
    return calls


def test_the_run_judges_each_table_before_fitting_and_keeps_the_fits_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★決定4: 判定は表を組んだ直後・当てはめの前。反復ごとの記録が `ceiling_verdicts/` に残り、`fits/` の形は変わらない。"""
    calls = force_ceiling(monkeypatch, every=2)
    seen_at_fit: list[bool] = []
    ps_tests.fake_fits(monkeypatch)
    plain_run_fits = power_sim.run_fits

    def checked_run_fits(rscript, libpath, manifest_stem, jobs, *rest):
        for csv_path, out_path in jobs:
            tag = csv_path.stem.removeprefix("frame_")
            rep = int(tag.rsplit("_", 1)[1])
            verdict = csv_path.parent.parent / power_sim.VERDICTS_DIR / power_sim.verdict_name(
                tag.rsplit("_", 1)[0], rep
            )
            seen_at_fit.append(verdict.is_file())
        return plain_run_fits(rscript, libpath, manifest_stem, jobs, *rest)

    monkeypatch.setattr(power_sim, "run_fits", checked_run_fits)
    summary = power_sim.run(
        ps_tests.smoke_config(), tmp_path, None, keep_frames=False, through_stage=1,
        config_path=ps_tests.SMOKE_CONFIG,
    )
    assert seen_at_fit and all(seen_at_fit)                  # 当てはめに渡る前に判定の記録がある
    assert set(calls) == {(TASKS, COVERAGES)}                # 役割 4 つすべて・表の水準をそのまま渡す
    for sheet_id, body in summary["sheets"].items():
        assert body["ceiling_counted_as"] == "retain"
        for point in body["grid"]:
            assert point["n_ceiling_judged"] == point["n_rep"] == 1
            assert point["intervals"]["ceiling"]["n"] == 1
        fits = sorted((tmp_path / sheet_id / "fits").glob("*.json"))
        verdicts = sorted((tmp_path / sheet_id / power_sim.VERDICTS_DIR).glob("*.json"))
        assert len(verdicts) == len(fits) > 0
        assert set(json.loads(fits[0].read_text(encoding="ascii"))) == set(ps_tests.fit_result(0.5))   # R の形は不変
        assert set(json.loads(verdicts[0].read_text(encoding="utf-8"))) == {
            "ceiling", "ceiling_hits", "ceiling_n_per_cell"
        }


def test_ceiling_repetitions_lower_the_rate_in_a_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """全反復が p = 0.01 で当てはめが成功する偽の当てはめでも、天井と判定された反復は棄却に数えない。"""
    force_ceiling(monkeypatch, every=2)                       # 反復 2 件 → 1 件が天井
    ps_tests.fake_fits(monkeypatch, p_value_for=lambda csv_path: 0.01)
    summary = power_sim.run(
        ps_tests.smoke_config(), tmp_path, None, keep_frames=False, through_stage=2,
        config_path=ps_tests.SMOKE_CONFIG,
    )
    for body in summary["sheets"].values():
        for point in body["grid"]:
            assert point["n_rep"] == 2
            assert point["n_ceiling"] == point["n_ceiling_descriptive"] == 1
            assert point["n_reject"] == point["n_reject_noceiling"] == 1
            assert point["n_reject_success"] == 2
            assert point["power"] == pytest.approx(0.5)
            assert point["tost_n_ceiling"] == 1 and len(point["tost_min_margins"]) == 1


def test_resuming_over_a_fit_without_a_verdict_stops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """旧い版で当てた反復(判定の記録が無い)がある点を再開すると、混在として止まる。別の --out-dir で回し直す。"""
    ps_tests.fake_fits(monkeypatch)
    done = tmp_path / "p1" / "fits" / "fit_n2_s0_r0_0000.json"
    done.parent.mkdir(parents=True)
    done.write_text(json.dumps(ps_tests.fit_result(0.5)), encoding="ascii")
    with pytest.raises(power_sim.PowerSimError, match="混ざって"):
        power_sim.run(ps_tests.smoke_config(), tmp_path, None, keep_frames=False, through_stage=2)


def test_the_ceiling_probe_role_is_not_judged_and_its_summary_keeps_its_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★決定6: 役割 `ceiling_probe` には当てない。判定の記録もなく、点・区間の形は変わらない。"""
    assert power_sim.ROLE_CEILING_PROBE not in power_sim.ROLES_WITH_CEILING_RULE
    calls = force_ceiling(monkeypatch, every=1)
    probe_tests.fake_fits(monkeypatch)
    summary = power_sim.run(
        probe_tests.small_config(n_rep=3), tmp_path, None, keep_frames=False, through_stage=1,
        config_path=probe_tests.CEILING_CONFIG,
    )
    assert calls == []
    assert not list(tmp_path.rglob(power_sim.VERDICTS_DIR))
    for body in summary["sheets"].values():
        assert "ceiling_counted_as" not in body
        for point in body["grid"]:
            assert not set(power_sim.CEILING_POINT_FIELDS) & set(point)
            assert set(point["intervals"]) == {
                "rejection", "rejection_success_only", "failed", "rejection_failed_descriptive_only"
            }
