"""T1c の表(code/analysis/composition_table.py)。PLAN-037 I4。

答える問い: 「T1c の run から、rate(t)・rate(t+offset)・rate(t+2·offset)・d が正しく出るか。
固定オフセットの run を混ぜず、判定の文言を出さないか」

**手で作った metrics.json である。ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from code.analysis import composition_table as ct


def block(correct: float, rule: float, other: float, parse_fail: float, n: int) -> dict[str, Any]:
    return {
        "correct_rate": correct,
        "rule_rate": rule,
        "other_error_rate": other,
        "parse_fail_rate": parse_fail,
        "n_items": n,
    }


def batch(correct: float, once: float, twice: float, parse_fail: float, n: int) -> dict[str, Any]:
    """真値 correct・1 回 once・2 回 twice・読めない parse_fail の応答から 2 ブロックを組む。"""
    return {
        "n_items": n,
        "by_reference_rule": {
            "comp_once": block(correct, once, twice, parse_fail, n),
            "comp_twice": block(correct, twice, once, parse_fail, n),
        },
    }


def payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "20261001_000000_t1c_ident",
        "kind": "composition",
        "adapter": "runs/x/adapter",
        "adapter_train_run_id": "x",
        "lesion_condition": "ident",
        "seed": 3,
        "pool": {"items_sha256": "ab" * 32, "n_items": 20},
        "signature_gate": {"gate": "ident_adapter", "freeze_tag": None},
        "composition": {"offset": 2},
        "by_batch": {"composition": batch(0.5, 0.125, 0.25, 0.125, 8)},
        "by_cell": {
            "t1c_id_nocarry": batch(0.5, 0.0, 0.5, 0.0, 4),
            "t1c_interp_carry": batch(0.5, 0.25, 0.0, 0.25, 4),
        },
    }
    base.update(overrides)
    return base


def write(tmp_path: Path, content: dict[str, Any], name: str = "metrics.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_the_rates_and_the_difference_follow_the_definition(tmp_path: Path) -> None:
    table = ct.build_tables([write(tmp_path, payload())])[0]
    overall, id_cell, interp_cell = table["rows"]
    assert overall["stratum"] == "all" and overall["n_items"] == 8
    assert overall["rate_t"] == 0.5
    assert overall["rate_once"] == 0.125
    assert overall["rate_twice"] == 0.25
    assert overall["d"] == pytest.approx(0.25 - 0.125)
    assert id_cell["d"] == pytest.approx(0.5 - 0.0)
    assert interp_cell["d"] == pytest.approx(0.0 - 0.25)  # 負の d も符号つきで出る


def test_each_row_carries_all_four_values_of_both_blocks(tmp_path: Path) -> None:
    row = ct.build_tables([write(tmp_path, payload())])[0]["rows"][0]
    for rule in ("comp_once", "comp_twice"):
        assert set(row["blocks"][rule]) == {
            "correct_rate",
            "rule_rate",
            "other_error_rate",
            "parse_fail_rate",
        }
        assert sum(row["blocks"][rule].values()) == pytest.approx(1.0)


def test_the_provenance_leads_the_table(tmp_path: Path) -> None:
    table = ct.build_tables([write(tmp_path, payload())])[0]
    assert table["adapter"] == "runs/x/adapter" and table["lesion_condition"] == "ident"
    assert table["seed"] == 3 and table["offset"] == 2
    assert table["pool_items_sha256"] == "ab" * 32
    assert table["lora_scale"] is None  # 記録の無い run は null。1 と読み替えない
    text = ct.render_markdown([table])
    assert text.index("条件: ident") < text.index("| 層 |")
    assert "ab" * 32 in text


@pytest.mark.parametrize("kind", ["battery_eval", "threshold_sweep", None])
def test_a_run_that_is_not_t1c_stops(tmp_path: Path, kind: str | None) -> None:
    with pytest.raises(ct.CompositionTableError, match="kind"):
        ct.build_tables([write(tmp_path, payload(kind=kind))])


def test_a_block_that_does_not_sum_to_one_stops(tmp_path: Path) -> None:
    broken = payload()
    broken["by_batch"]["composition"]["by_reference_rule"]["comp_once"]["parse_fail_rate"] = 0.5
    with pytest.raises(ct.CompositionTableError, match="合計"):
        ct.build_tables([write(tmp_path, broken)])


def test_a_block_with_a_missing_rate_stops(tmp_path: Path) -> None:
    broken = payload()
    del broken["by_cell"]["t1c_id_nocarry"]["by_reference_rule"]["comp_twice"]["other_error_rate"]
    with pytest.raises(ct.CompositionTableError, match="other_error_rate"):
        ct.build_tables([write(tmp_path, broken)])


def test_a_missing_reference_block_stops(tmp_path: Path) -> None:
    broken = copy.deepcopy(payload())
    del broken["by_batch"]["composition"]["by_reference_rule"]["comp_twice"]
    with pytest.raises(ct.CompositionTableError, match="参照規則"):
        ct.build_tables([write(tmp_path, broken)])


def test_different_correct_rates_across_the_blocks_stop(tmp_path: Path) -> None:
    """真値は同じなので correct_rate は一致するはず。違えば採点の取り違えである。"""
    broken = payload()
    twice = broken["by_batch"]["composition"]["by_reference_rule"]["comp_twice"]
    twice["correct_rate"], twice["other_error_rate"] = 0.375, 0.25
    with pytest.raises(ct.CompositionTableError, match="correct_rate"):
        ct.build_tables([write(tmp_path, broken)])


def test_the_markdown_has_no_verdict_words(tmp_path: Path) -> None:
    text = ct.render_markdown(ct.build_tables([write(tmp_path, payload())]))
    for word in ("合格", "不合格", "支持", "棄却", "有意", "優勢", "H1 を退け"):
        assert word not in text


def test_main_prints_and_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir = tmp_path / "run_a"
    run_dir.mkdir()
    write(run_dir, payload())
    out = tmp_path / "out" / "table.json"
    assert ct.main(["--runs", str(run_dir), "--out", str(out)]) == 0
    assert "T1c 合成の探り" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))[0]["run_id"] == "20261001_000000_t1c_ident"
    assert b"\r" not in out.read_bytes()
