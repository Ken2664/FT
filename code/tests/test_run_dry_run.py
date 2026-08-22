"""評価ハーネスの入口(code/eval/run.py)の配線テスト。

答える問い: 「config → 項目 → プロンプト → パーサ → 採点 は繋がっているか」

README のクイックスタートに載っているコマンド

    python -m code.eval.run --config configs/smoke.yaml --dry-run

が動き続けることを固定する。**ここで検査するのは配線であって結果ではない。**
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from code.data_gen.pool import DegenerateReferenceRuleError
from code.eval.run import ConfigError, dry_run, load_config, main

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"


@pytest.fixture
def smoke_config() -> dict[str, Any]:
    return load_config(SMOKE_CONFIG)


def test_smoke_config_dry_runs(smoke_config: dict[str, Any]) -> None:
    """smoke config が最後まで通ること。"""
    report = dry_run(smoke_config)
    assert report["n_items"] == len(smoke_config["eval"]["dry_run_items"])
    assert len(report["prompts"]) == report["n_items"]
    assert all("より" in prompt for prompt in report["prompts"])


def test_every_block_sums_to_one(smoke_config: dict[str, Any]) -> None:
    """★どの固定応答でも、参照規則ごとのブロックの4値が 1.0 に合うこと。"""
    report = dry_run(smoke_config)
    for label, metrics in report["by_response"].items():
        for name, block in metrics["by_reference_rule"].items():
            total = (
                block["correct_rate"]
                + block["rule_rate"]
                + block["other_error_rate"]
                + block["parse_fail_rate"]
            )
            assert total == pytest.approx(1.0), f"{label} / {name} の合計が 1.0 でない"


def test_unreadable_response_becomes_parse_fail(smoke_config: dict[str, Any]) -> None:
    """読めない出力は parse_fail に落ち、correct / rule に混ざらないこと。"""
    block = dry_run(smoke_config)["by_response"]["unreadable"]["by_reference_rule"]["p2"]
    assert block["parse_fail_rate"] == 1.0
    assert block["correct_rate"] == 0.0
    assert block["rule_rate"] == 0.0


def test_balanced_polarity_caps_the_constant_strategy(smoke_config: dict[str, Any]) -> None:
    """★極性が均衡していれば「常に Yes」の理論 rule_rate は 1.0 にならない。

    PLAN-001 §5.1 の応答バイアス対策そのもの。gt だけで組むとここが 1.0 になる。
    """
    baselines = dry_run(smoke_config)["by_response"]["affirmative"]["constant_answer_baselines"]
    assert baselines["always_yes"]["rule_rate"] < 1.0
    assert baselines["always_no"]["rule_rate"] < 1.0


def test_null_config_value_stops_the_run(smoke_config: dict[str, Any]) -> None:
    """未決定(null)の項目があるまま実行しない(skill code-style §5)。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["reference_rule"] = None
    with pytest.raises(ConfigError, match="null"):
        dry_run(config)


def test_identity_reference_rule_is_refused(smoke_config: dict[str, Any]) -> None:
    """★ident を eval.reference_rule に指定できない(ADR-016)。"""
    config = copy.deepcopy(smoke_config)
    config["lesion"]["offset"] = 0  # offset=0 は ident と同じ退化をする
    with pytest.raises(DegenerateReferenceRuleError):
        dry_run(config)


def test_unimplemented_battery_is_refused(smoke_config: dict[str, Any]) -> None:
    """未実装の群を要求されたら黙って空を返さない。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["batteries"] = ["g2"]
    with pytest.raises(ConfigError, match="未実装"):
        dry_run(config)


def test_real_run_is_not_implemented() -> None:
    """--dry-run なしの本実行は未実装。既定のモデル名をここで作らない。"""
    with pytest.raises(NotImplementedError, match="未実装"):
        main(["--config", str(SMOKE_CONFIG)])
