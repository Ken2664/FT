"""PB の計時(`code/analysis/pb_timing.py` / `pb_timing.R`)のテスト。PLAN-043 I9 / ADR-129 決定6。

R は呼ばない(偽の R の出力で python 側の配線・集計・止まり方を確かめる)。
**計時の本番は人間の合図の後**であり、ここでは回さない。
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from code.analysis import pb_timing, power_sim as ps
from code.config import ConfigError, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
PB_CONFIG = REPO_ROOT / "configs" / "pb_timing.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "power_sim.yaml"


def load() -> dict[str, Any]:
    return copy.deepcopy(load_config(PB_CONFIG))


def test_spec_is_the_decided_one() -> None:
    """★ADR-129 決定6: 合成の反復の 4 表(P0 の (80, 1.0) から 2 枚・誤指定の同じ点から 2 枚)× B 20 = 160 本。

    答える問い: 「計時の規模と表の出所が、人間が決めたとおりか」。
    """
    spec = pb_timing.load_spec(load(), REPO_ROOT)
    assert [(t.sheet_id, t.key, t.rep) for t in spec.tables] == [
        ("p0", ps.PointKey(80, 1.0, 0.0), 9001),
        ("p0", ps.PointKey(80, 1.0, 0.0), 9002),
        ("misspecification", ps.PointKey(80, 1.0, 0.0), 9001),
        ("misspecification", ps.PointKey(80, 1.0, 0.0), 9002),
    ]
    assert (spec.n_boot, spec.min_rep) == (20, 9000)
    assert len(spec.tables) * spec.n_boot * 2 == 160
    pb_timing.check_tables_against_sheets(spec, ps.load_sheets(load_config(MAIN_CONFIG)))
    # run2・run3 の反復(0〜999)と重ならない
    stages = ps.load_stages(load_config(MAIN_CONFIG))
    assert all(t.rep > stages[-1] for t in spec.tables)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["pb"].update(n_boot=None),
        lambda c: c["pb"].update(n_boot=0),
        lambda c: c["pb"].update(simulate_seed="1"),
        lambda c: c["pb"].update(n_parallel=True),
        lambda c: c.update(tables=[]),
        lambda c: c.update(tables=[{"sheet": "p0", "point": [80, 1.0], "rep": 9001}]),
        lambda c: c["tables"][0].update(rep=999),                    # run2・run3 の反復を覗かない
        lambda c: c.update(tables=[c["tables"][0], dict(c["tables"][0])]),
        lambda c: c.pop("source_config"),
    ],
)
def test_spec_stops_on_a_missing_or_malformed_value(mutate) -> None:
    """既定値を作らない。null・欠け・`min_rep` 未満の反復・同じ表の重複は止まる。"""
    config = load()
    mutate(config)
    with pytest.raises(ConfigError):
        pb_timing.load_spec(config, REPO_ROOT)


def test_tables_must_be_points_the_source_config_runs() -> None:
    """回さないシートや点を測らない。"""
    sheets = ps.load_sheets(load_config(MAIN_CONFIG))
    config = load()
    config["tables"][0]["point"] = [80, 0.9, 0.0]
    with pytest.raises(ConfigError, match="回さない"):
        pb_timing.check_tables_against_sheets(pb_timing.load_spec(config, REPO_ROOT), sheets)
    config = load()
    config["tables"][0]["sheet"] = "no_such_sheet"
    with pytest.raises(ConfigError, match="source_config"):
        pb_timing.check_tables_against_sheets(pb_timing.load_spec(config, REPO_ROOT), sheets)


def test_manifest_carries_the_thresholds_and_the_boot_size(tmp_path: Path) -> None:
    """ADR-059 の閾値・縮退の最大段・B・種が config から R へ流れる(コードに直書きしない)。"""
    spec = pb_timing.load_spec(load(), REPO_ROOT)
    source = load_config(MAIN_CONFIG)
    manifest = tmp_path / "m.txt"
    pb_timing.write_pb_manifest(
        manifest, [(tmp_path / "a.csv", tmp_path / "a.json")], source["fit"]["refit"],
        len(source["fit"]["reduction_order"]), spec,
    )
    lines = manifest.read_text(encoding="ascii").splitlines()
    for expected in ("loglik_tolerance=0.001", "beta_move_tolerance=0.01", "max_reduction_level=3",
                     "n_boot=20", "simulate_seed=20261008"):
        assert expected in lines
    assert [line for line in lines if line.startswith("table=")] == [
        f"table={(tmp_path / 'a.csv').as_posix()}|{(tmp_path / 'a.json').as_posix()}|4"
    ]


def r_result(**overrides: Any) -> dict[str, Any]:
    """R が返す JSON の形を手で組む。"""
    base = {
        "csv": "x.csv", "r_version": "R version 4.6.1", "lme4_version": "2.0.6", "n_parallel": 4,
        "settled_level": 1, "observed_fit_failed": False, "observed_fit_seconds": 30.0, "n_boot": 2,
        "skipped": False, "simulate_seconds": 0.5, "refit_seconds_total": 12.0,
        "refit_seconds_each": [5.0, 7.0],
        "refit_error_add": 0, "refit_error_full": 1,
        "refit_nonsingular_warning_add": 1, "refit_nonsingular_warning_full": 0,
        "first_refit_error": "boom",
    }
    base.update(overrides)
    return base


def test_summary_is_seconds_and_failure_counts_only() -> None:
    """★出すのは秒数と当て直しの失敗の数だけ(p 値・統計量は無い。ADR-129 決定6)。"""
    skipped = r_result(skipped=True, observed_fit_seconds=10.0)
    for key in ("refit_seconds_each", "refit_seconds_total"):
        skipped.pop(key)
    summary = pb_timing.summarise([r_result(), r_result(refit_seconds_each=[3.0, 9.0]), skipped])
    assert summary["n_tables"] == 3 and summary["n_tables_skipped"] == 1
    assert (summary["n_draws"], summary["n_refits"]) == (4, 8)
    assert (summary["refit_errors"], summary["refit_nonsingular_warnings"]) == (2, 2)
    assert summary["observed_fit_seconds_total"] == pytest.approx(70.0)
    assert summary["seconds_per_draw_mean"] == pytest.approx(6.0)
    assert summary["seconds_per_draw_max"] == 9.0
    assert not [k for k in summary if "p_value" in k or "chisq" in k]


def test_run_writes_the_summary_with_a_fake_r(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """偽の R で表の組み立て・R の呼び出し・集計・来歴が通る。表(CSV)は計時の後に消える。"""
    config = load()
    config["out_dir"] = str(tmp_path.relative_to(tmp_path.anchor)).replace("\\", "/")
    spec = pb_timing.load_spec(config, tmp_path.anchor and Path(tmp_path.anchor))
    source = load_config(MAIN_CONFIG)
    seen: list[Path] = []

    def fake_r(rscript: str, libpath: str | None, manifest: Path) -> str:
        for line in manifest.read_text(encoding="ascii").splitlines():
            if line.startswith("table="):
                csv, out, _ = line.removeprefix("table=").split("|")
                assert Path(csv).exists(), "R に渡す表が書かれていない"
                seen.append(Path(csv))
                Path(out).write_text(json.dumps(r_result(csv=Path(csv).name)), encoding="ascii")
        return ""

    monkeypatch.setattr(ps, "resolve_rscript", lambda declared: "Rscript")
    monkeypatch.setattr(pb_timing, "run_pb_rscript", fake_r)
    report = pb_timing.run(spec, config, source, None)
    assert len(seen) == 4 and not any(path.exists() for path in seen)
    on_disk = json.loads((spec.out_dir / pb_timing.SUMMARY_FILE).read_text(encoding="utf-8"))
    assert on_disk["summary"]["n_refits"] == report["summary"]["n_refits"] == 16
    assert len(on_disk["git_sha"]) == 40 and "note" in on_disk
    assert [t["sheet"] for t in on_disk["tables"]] == ["p0", "p0", "misspecification", "misspecification"]


def test_a_missing_r_output_stops_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R が出力を書かなかった表を黙って落とさない(`CLAUDE.md` §7)。"""
    config = load()
    config["out_dir"] = str(tmp_path.relative_to(tmp_path.anchor)).replace("\\", "/")
    spec = pb_timing.load_spec(config, Path(tmp_path.anchor))
    monkeypatch.setattr(ps, "resolve_rscript", lambda declared: "Rscript")
    monkeypatch.setattr(pb_timing, "run_pb_rscript", lambda *args: "")
    with pytest.raises(pb_timing.PbTimingError, match="出力が無い"):
        pb_timing.run(spec, config, load_config(MAIN_CONFIG), None)


def test_r_script_writes_no_p_value_and_no_statistic() -> None:
    """★R の出力に p 値・LRT の統計量・PB の p が無い(ADR-129 決定6)。縮退・allFit もしない。

    答える問い: 「計時のはずが、PB の p 値を出す実装になっていないか」(R は呼ばない。文面の突き合わせ)。
    """
    text = pb_timing.PB_SCRIPT.read_text(encoding="utf-8")
    written = set(re.findall(r'kv\("([a-z_]+)"', text))
    assert not [k for k in written if "p_value" in k or "chisq" in k or k.startswith("lrt")]
    assert "anova(" not in text and "allFit(" not in text and "Pr(>Chisq)" not in text
    assert "refit(fit, newresp)" in text and "simulate(fit_add, nsim = n_boot, seed = sim_seed)" in text
    # 当て直しの式は観測の当てはめが着いた段の式(縮退はしない)
    assert "fit_add <- final_fit(settled$add)" in text and "fit_full <- final_fit(settled$full)" in text


def test_dry_run_reports_the_plan_without_calling_r(capsys: pytest.CaptureFixture[str]) -> None:
    assert pb_timing.main(["--config", str(PB_CONFIG), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "160 refits" in out and "no p value" in out
