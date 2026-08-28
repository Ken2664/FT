"""桁数掃引の CLI(code/eval/sweep.py)のテスト。

答える問い: 「M -> correct_rate の表を、モデルを読まずに検査できるか」

**モデルの重みは1度も読まない**(PLAN-004 §4.3 の1)。**ここに出る数値は
実験結果ではない** —— 固定応答に対する分解であり、素のモデルの算術能力は
1度も測っていない。M* もここでは決まらない(承認待ち #9 / #15)。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.config import ConfigError, load_config
from code.eval import sweep
from code.eval.battery import magnitude_sweep
from code.eval.generate import Generator
from code.lesion import reference_lesions_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# **実験条件ではない。**smoke config は model.name / revision を null にしてある。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
# smoke config は device / batch_size を持たない(あちらは編集してはならない。
# ADR-037 決定4)。cpu と 1 を置くのは**重みを読まないから**であって、
# 実験条件の宣言ではない —— この経路は固定応答の生成器で回る
TEST_DEVICE = "cpu"
TEST_BATCH_SIZE = 1

UNREADABLE = "???"


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める。

    来歴の**中身**は code/tests/test_artifacts.py が実物で検査する。ここで
    毎回 pip freeze を回すと1テストあたり数秒かかり、配線のテストが遅くなる。
    """
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Any]:
    """生成設定を埋めた config と、その写しを置く場所。"""
    config = load_config(SMOKE_CONFIG)
    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["model"]["device"] = TEST_DEVICE
    config["eval"]["batch_size"] = TEST_BATCH_SIZE
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {"config": config, "config_path": config_path, "run_dir": tmp_path / "run"}


def truthful_responses(config: dict[str, Any]) -> dict[str, str]:
    """掃引の各プロンプトに真値 a + b を返す固定応答。

    項目は `magnitude_sweep.build_items` から取る —— 掃引が実際に引くのと
    同じ関数・同じシードなので、対応づけがずれない。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    lesions = reference_lesions_from_config(config)
    responses: dict[str, str] = {}
    for radius in plan.radii:
        items = magnitude_sweep.build_items(
            radius,
            n_items=plan.n_items_per_radius,
            seed=plan.seed,
            pool_id=config["data"]["pool_id"],
            reference_lesions=lesions,
        )
        prompts = sweep.sweep_prompts(items, config)
        for item in items:
            total = item.operands[0] + item.operands[1]
            responses[prompts[item.item_id]] = f"Answer: {total}."
    return responses


def lookup_generator(responses: dict[str, str]) -> Generator:
    def generator(prompts: Sequence[str]) -> list[str]:
        return [responses[prompt] for prompt in prompts]

    return generator


def constant_generator(text: str) -> Generator:
    def generator(prompts: Sequence[str]) -> list[str]:
        return [text for _ in prompts]

    return generator


def test_prompts_use_the_training_format(workspace: dict[str, Any]) -> None:
    """★掃引の文面は評価用テンプレート集合ではなく訓練書式から来る。

    掃引項目は T1(裸の計算式)であり、T1 の書式は `data.prompt_template` と
    1文字も違ってはならない(検査6)。評価用テンプレート集合から引くと、
    素の算術能力を測ったつもりの数値が別の書式に対する数値になる。
    """
    config = workspace["config"]
    lesions = reference_lesions_from_config(config)
    items = magnitude_sweep.build_items(
        3, n_items=3, seed=1, pool_id=config["data"]["pool_id"], reference_lesions=lesions
    )
    prompts = sweep.sweep_prompts(items, config)
    template = config["data"]["prompt_template"]
    for item in items:
        assert prompts[item.item_id] == template.format(
            a=item.operands[0], b=item.operands[1]
        )


def test_every_declared_radius_is_measured(workspace: dict[str, Any]) -> None:
    """★config が宣言した M をすべて測る(粒度は config が決める)。"""
    config = workspace["config"]
    results = sweep.sweep(config, generator=constant_generator(UNREADABLE))
    assert [result.radius for result in results] == sorted(
        config["eval"]["magnitude_sweep"]["radii"]
    )
    for result in results:
        assert result.breakdown.n_items == config["eval"]["magnitude_sweep"][
            "n_items_per_radius"
        ]


def test_every_point_reports_all_four_values(workspace: dict[str, Any]) -> None:
    """★どの M でも4値が揃い、合計が 1.0 になる(CLAUDE.md §6)。"""
    results = sweep.sweep(workspace["config"], generator=constant_generator(UNREADABLE))
    for result in results:
        row = result.as_dict()
        total = (
            row["correct_rate"]
            + row["rule_rate"]
            + row["other_error_rate"]
            + row["parse_fail_rate"]
        )
        assert total == pytest.approx(1.0)
        assert row["parse_fail_rate"] == pytest.approx(1.0)


def test_a_truthful_model_scores_all_correct(workspace: dict[str, Any]) -> None:
    """★真値を返す応答はどの M でも correct に落ちる。"""
    config = workspace["config"]
    results = sweep.sweep(config, generator=lookup_generator(truthful_responses(config)))
    for result in results:
        assert result.breakdown.correct_rate == pytest.approx(1.0)
        assert result.breakdown.rule_rate == pytest.approx(0.0)


def test_the_table_maps_each_radius_to_a_correct_rate(workspace: dict[str, Any]) -> None:
    """★この CLI の成果物は M -> correct_rate の対応表である。"""
    config = workspace["config"]
    results = sweep.sweep(config, generator=lookup_generator(truthful_responses(config)))
    table = sweep.correct_rate_table(results)
    assert list(table) == [str(radius) for radius in sorted(
        config["eval"]["magnitude_sweep"]["radii"]
    )]
    assert all(rate == pytest.approx(1.0) for rate in table.values())


def test_the_sweep_does_not_decide_the_extrapolation_limit(
    workspace: dict[str, Any],
) -> None:
    """★掃引は M* も θ も出さない(承認待ち #9 / #15)。

    出すと、その値が「実測で決まった」ように見えてしまう。表を読んで M* を
    置くのは人間であり、決まったら eval.extrapolation_radius に入る。
    """
    config = workspace["config"]
    target = sweep.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config)),
    )
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert "extrapolation_radius" not in payload
    assert "M*" not in json.dumps(payload, ensure_ascii=False)
    assert "M* は決まらない" in (target / "log.txt").read_text(encoding="utf-8")


def test_execute_writes_the_artifacts(workspace: dict[str, Any]) -> None:
    """★来歴を残す(infra/RUNPOD.md §4)。書かないものは書かない。"""
    config = workspace["config"]
    target = sweep.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config)),
    )
    for name in ("config.yaml", "git_sha.txt", "env.txt", "timestamp.txt", "metrics.json",
                 "log.txt"):
        assert (target / name).exists()
    for name in ("cost.txt", "token_boundary.json"):
        assert not (target / name).exists()

    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert payload["kind"] == sweep.SWEEP_KIND
    assert payload["generation"]["model_name"] == TEST_MODEL
    assert payload["sweep"] == magnitude_sweep.load_sweep_plan(config).as_dict()
    # ★LoRA アダプタは読んでいない。素の重みに対する測定である
    assert payload["adapter"] is None

    for radius in payload["sweep"]["radii"]:
        path = target / "predictions" / f"{sweep.PREDICTIONS_PREFIX}_M{radius}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == payload["sweep"]["n_items_per_radius"]
        assert all(row["classification"] == "correct" for row in rows)


def test_undecided_generation_settings_stop_the_sweep() -> None:
    """★smoke config(model.name = null)のままでは掃引できない。

    決めていない設定で表が出ると、その表が M* の根拠として引かれる。
    """
    with pytest.raises(ConfigError, match="model.name"):
        sweep.main(["--config", str(SMOKE_CONFIG)])


def test_the_dry_run_does_not_measure_anything(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--dry-run は項目の組み立てだけを見せ、correct_rate を出さない。"""
    assert sweep.main(["--config", str(SMOKE_CONFIG), "--dry-run"]) == 0
    assert "実験ではない" in capsys.readouterr().out
    # 報告そのものに率が1つも入っていないこと(見出しの文言ではなく中身で見る)
    summary = sweep.dry_run_summary(load_config(SMOKE_CONFIG))
    assert "correct_rate" not in json.dumps(summary, ensure_ascii=False)
