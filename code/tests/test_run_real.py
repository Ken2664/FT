"""本実行の経路(code/eval/run.py の execute / evaluate_pool)のテスト。

答える問い: 「モデルを読まずに、本実行の配線と成果物を検査できるか」

**モデルの重みは1度も読まない**(PLAN-004 §4.3 の1)。`execute` は
`generator` を差し替えられるので、固定応答を返す関数を渡す。ここで
検査するのは「項目と応答の対応」「4値分解」「runs/<id>/ の中身」であって、
モデルの振る舞いではない。**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from code.config import ConfigError, load_config
from code.data_gen import eval_pool
from code.data_gen.battery_items import Item, read_items, write_items
from code.eval import artifacts, run
from code.eval.battery import specificity_control, t3_comparison
from code.eval.generate import Generator
from code.lesion import specificity_reference_lesions_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# **実験条件ではない。**smoke config は model.name / revision を null に
# してあるので、本実行の経路まで到達させるためにテスト側で埋める。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40

# 4群すべてが1バッチ以上を出すこと。specificity だけ category で割れる(§4.6)
EXPECTED_BATCHES = {"comparison", "bare_sum", "word_problem", "spec_sub", "spec_mul"}

# 読めない応答。二値パーサにも数値パーサにも引っかからない文字列。
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
    """評価プールを書き出し、それを指す config を組む。

    答える問い: 「eval_pool が書いたプールを run がそのまま読めるか」

    **repo の data/generated/ を当てにしない。**items.jsonl は .gitignore
    されており(manifest.json だけ追跡)、クローン直後には存在しない。
    ここで書き出すことで、テストが手元の生成物に依存しなくなる。
    """
    config = load_config(SMOKE_CONFIG)
    pool_dir = tmp_path / "battery"
    eval_pool.write_pool(eval_pool.build(config), pool_dir)

    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {
        "config": config,
        "config_path": config_path,
        "pool_dir": pool_dir,
        "items": read_items(pool_dir / "items.jsonl"),
        "run_dir": tmp_path / "run",
    }


def reference_rule_for(item: Item, primary: str) -> str:
    """この項目が採点される参照規則。特異性対照だけ category で決まる(§4.6)。"""
    if item.group == specificity_control.GROUP:
        return specificity_control.reference_rule_for(item.category)
    return primary


def truthful_responses(config: dict[str, Any], items: Sequence[Item]) -> dict[str, str]:
    """真値を答える固定応答を、プロンプトごとに組む。

    答える問い: 「正答だけを返すモデルは、どのバッチでも correct に落ちるか」

    真値は `run.response_builder` から取る —— **採点器に渡すのと同じ経路**で
    取ることで、固定応答の作り方と突き合わせ先がずれない
    (`numeric_response_metrics` と同じ考え方)。
    """
    lesions = run.build_reference_lesions(config)
    specificity_lesions = specificity_reference_lesions_from_config(config)
    primary = config["eval"]["reference_rule"]
    template_set = config["data"]["eval_template_set"]
    responses: dict[str, str] = {}
    for group in config["eval"]["batteries"]:
        templates = run.load_group_templates(config, group, template_set)
        for item in [item for item in items if item.group == group]:
            to_response = run.response_builder(
                group,
                reference_rule_for(item, primary),
                lesions=lesions,
                specificity_lesions=specificity_lesions,
            )
            truth = to_response(item, None).truth
            prompt = run.RENDERERS[group](item, templates)
            responses[prompt] = (
                ("Yes." if truth else "No.")
                if group == t3_comparison.GROUP
                else f"Answer: {truth}."
            )
    return responses


def lookup_generator(responses: dict[str, str]) -> Generator:
    """プロンプトを引いて固定応答を返す生成器(GPU も重みも要らない)。"""

    def generator(prompts: Sequence[str]) -> list[str]:
        return [responses[prompt] for prompt in prompts]

    return generator


def constant_generator(text: str) -> Generator:
    def generator(prompts: Sequence[str]) -> list[str]:
        return [text for _ in prompts]

    return generator


# --------------------------------------------------------------------------
# 項目の読み込み
# --------------------------------------------------------------------------


def test_items_come_from_beside_the_anchor_manifest(workspace: dict[str, Any]) -> None:
    """★本実行は eval.anchor_manifest と同じ dir の items.jsonl を読む。

    preflight の検査6 が書式を照合した manifest と**同じプール**を評価する。
    `data.pool_id` から出力先を組み直すと、smoke のように両者がずれる config で
    静かに別のプールを読む。
    """
    config = workspace["config"]
    assert run.pool_items_path(config) == workspace["pool_dir"] / "items.jsonl"
    assert len(run.load_pool_items(config)) == len(workspace["items"])


def test_a_missing_pool_stops_the_run(workspace: dict[str, Any]) -> None:
    (workspace["pool_dir"] / "items.jsonl").unlink()
    with pytest.raises(ConfigError, match="評価プールの項目が無い"):
        run.load_pool_items(workspace["config"])


def test_a_pool_from_another_pool_id_stops_the_run(workspace: dict[str, Any]) -> None:
    """★項目の pool_id と data.pool_id がずれたら止める。

    pool_id は item_id にも T2 の場面割当にも効く(PLAN-003 §4.3)。
    違うプールを黙って読むと「同じ組は条件をまたいで同じ場面で尋ねられる」が壊れる。
    """
    workspace["config"]["data"]["pool_id"] = "pilot"
    with pytest.raises(ConfigError, match="pool_id"):
        run.load_pool_items(workspace["config"])


def test_a_declared_group_without_items_stops_the_run(workspace: dict[str, Any]) -> None:
    """★eval.batteries が宣言した群が空なら止める。

    黙って通すと、対照条件のはずのバッチが結果から消える。
    """
    kept = [item for item in workspace["items"] if item.group != "word_problem"]
    write_items(workspace["pool_dir"] / "items.jsonl", kept)
    with pytest.raises(ConfigError, match="word_problem"):
        run.load_pool_items(workspace["config"])


# --------------------------------------------------------------------------
# 4値分解
# --------------------------------------------------------------------------


def test_all_four_groups_are_evaluated(workspace: dict[str, Any]) -> None:
    """★4群すべてが本実行の経路を通り、バッチに分かれること。"""
    config = workspace["config"]
    results = run.evaluate_pool(
        config, generator=lookup_generator(truthful_responses(config, workspace["items"]))
    )
    assert {result.name for result in results} == EXPECTED_BATCHES
    assert sum(result.metrics["n_items"] for result in results) == len(workspace["items"])


def test_every_block_sums_to_one(workspace: dict[str, Any]) -> None:
    """★どのバッチ・どの参照規則でも4値の合計が 1.0(CLAUDE.md §6)。"""
    config = workspace["config"]
    results = run.evaluate_pool(config, generator=constant_generator(UNREADABLE))
    for result in results:
        for block in result.metrics["by_reference_rule"].values():
            total = (
                block["correct_rate"]
                + block["rule_rate"]
                + block["other_error_rate"]
                + block["parse_fail_rate"]
            )
            assert total == pytest.approx(1.0)


def test_a_truthful_model_scores_all_correct(workspace: dict[str, Any]) -> None:
    """★真値だけを返す応答は correct に落ちる(rule ではない)。"""
    config = workspace["config"]
    results = run.evaluate_pool(
        config, generator=lookup_generator(truthful_responses(config, workspace["items"]))
    )
    for result in results:
        block = result.metrics["by_reference_rule"][result.reference_rule]
        assert block["correct_rate"] == pytest.approx(1.0)
        assert block["rule_rate"] == pytest.approx(0.0)


def test_an_unreadable_model_scores_all_parse_fail(workspace: dict[str, Any]) -> None:
    """★読めない応答は parse_fail に落ちる。other_error と混ざらない。

    ここが混ざると、抽出の失敗がモデルの崩壊として報告される
    (skill code-style §2)。
    """
    results = run.evaluate_pool(
        workspace["config"], generator=constant_generator(UNREADABLE)
    )
    for result in results:
        block = result.metrics["by_reference_rule"][result.reference_rule]
        assert block["parse_fail_rate"] == pytest.approx(1.0)


def test_comparison_batches_carry_the_constant_answer_baseline(
    workspace: dict[str, Any],
) -> None:
    """★二値バッチには常答戦略の理論値が併記される(PLAN-001 §5.1)。

    実測がこの理論値を超えていることを人間が確認できないと、極性の偏りを
    突いただけの無内容な戦略と区別できない。
    """
    results = run.evaluate_pool(
        workspace["config"], generator=constant_generator(UNREADABLE)
    )
    by_name = {result.name: result for result in results}
    baselines = by_name["comparison"].metrics["constant_answer_baselines"]
    assert set(baselines) == {"always_yes", "always_no"}
    # 数値バッチには併記しない。定数を返す戦略の理論値はほぼ 0 で意味を持たない
    assert "constant_answer_baselines" not in by_name["bare_sum"].metrics


def test_responses_stay_aligned_with_the_prompts(workspace: dict[str, Any]) -> None:
    """★応答は渡した順序のまま項目に対応づく。

    1つずれたまま採点すると「モデルが変な答えを返した」ようにしか見えない。
    生成器に順番の分かる応答を返させ、predictions の行と突き合わせる。
    """

    def indexed(prompts: Sequence[str]) -> list[str]:
        return [f"Answer: {index}." for index, _ in enumerate(prompts)]

    results = run.evaluate_pool(workspace["config"], generator=indexed)
    for result in results:
        for index, record in enumerate(result.predictions):
            assert record["response"] == f"Answer: {index}."


# --------------------------------------------------------------------------
# runs/<id>/ の成果物
# --------------------------------------------------------------------------


def test_execute_writes_the_required_artifacts(workspace: dict[str, Any]) -> None:
    """★infra/RUNPOD.md §4 の一覧のうち、このハーネスが書くものを書く。"""
    config = workspace["config"]
    target = run.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config, workspace["items"])),
    )
    assert target == workspace["run_dir"]
    for name in ("config.yaml", "git_sha.txt", "env.txt", "timestamp.txt", "metrics.json",
                 "log.txt"):
        assert (target / name).exists()
    # 書かないもの。cost.txt は課金(§7)、token_boundary.json は preflight 検査7 の担当
    for name in ("cost.txt", "token_boundary.json"):
        assert not (target / name).exists()


def test_metrics_record_the_provenance(workspace: dict[str, Any]) -> None:
    """★数値だけを見た人が、どの重み・どの設定・どの項目集合かを言えること。"""
    config = workspace["config"]
    target = run.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config, workspace["items"])),
    )
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    assert payload["kind"] == run.EVAL_KIND
    assert payload["run_id"] == target.name
    assert payload["generation"]["model_name"] == TEST_MODEL
    assert payload["generation"]["revision"] == TEST_REVISION
    assert payload["pool"]["n_items"] == len(workspace["items"])
    assert set(payload["by_batch"]) == EXPECTED_BATCHES
    # ★LoRA アダプタは読んでいない。lesion.condition は宣言であって重みではない
    assert payload["adapter"] is None
    assert payload["lesion_condition"] == config["lesion"]["condition"]
    assert "アダプタを読まない" in payload["adapter_note"]


def test_predictions_keep_the_raw_generation(workspace: dict[str, Any]) -> None:
    """★1行1応答で、生成文字列と分類の両方を残す。

    パーサの取りこぼしは parse_fail_rate に化けるので、原文が無いと
    モデルの崩壊と抽出の失敗を後から切り分けられない。
    """
    config = workspace["config"]
    target = run.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config, workspace["items"])),
    )
    total = 0
    for name in EXPECTED_BATCHES:
        path = target / "predictions" / f"{name}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        total += len(rows)
        for row in rows:
            assert row["classification"] == "correct"
            assert row["response"]
            assert row["prompt"]
    assert total == len(workspace["items"])


def test_the_log_does_not_reuse_the_dry_run_warning(workspace: dict[str, Any]) -> None:
    """★本実行の出力に --dry-run の警告文を流用しない(PLAN-004 §4.3 の4)。

    本実行の数値は実験結果であり results/ に書いてよい。「実験ではない」と
    書いた log が残ると、実験結果が捨てられる。
    """
    config = workspace["config"]
    target = run.execute(
        config,
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=lookup_generator(truthful_responses(config, workspace["items"])),
    )
    body = (target / "log.txt").read_text(encoding="utf-8")
    assert "実験ではない" not in body
    assert "アダプタを読まない" in body
