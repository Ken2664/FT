"""T1c の評価経路(code/eval/composition_run.py)と D9 の門(code/eval/signature_gate.py)。

答える問い: PLAN-037 I3 / D5 / D9「T1c の run は、別の `kind` で、2 つの参照規則のブロックを持ち、
宣言の食い違いと凍結前の署名の取り違えを重みを読む前に止めるか」

**モデルの重みは 1 度も読まない**(固定応答の生成器を渡す)。**ここに出る数値は実験結果ではない。**
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
from code.data_gen import composition_pool
from code.data_gen.battery_items import write_items
from code.eval import composition_run, run, signature_gate
from code.eval.battery import composition
from code.eval.generate import Generator
from code.lesion import composition_reference_lesions_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

TEMPLATE = "{a}+{b}+{c}="
# 実験の件数ではない。機構を見るための 2 セル × 3 件。
CELL_OPERANDS: dict[str, list[tuple[int, int, int]]] = {
    "t1c_id_nocarry": [(12, 25, 8), (30, 14, 22), (21, 42, 60)],
    "t1c_interp_carry": [(15, 28, 9), (37, 20, 6), (24, 35, 31)],
}


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)を止める。来歴の中身は test_artifacts.py が見る。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Any]:
    """手で作った T1c のプールと、それを指す config。

    答える問い: 「`composition_pool` の書く形のプールを `composition_run` がそのまま読めるか」
    """
    config = load_config(SMOKE_CONFIG)
    pool_id = config["data"]["pool_id"]
    lesions = composition_reference_lesions_from_config(config)
    items = [
        composition.build_item(
            operands, pool_id=pool_id, reference_lesions=lesions, params={"cell": cell}
        )
        for cell, operand_list in CELL_OPERANDS.items()
        for operands in operand_list
    ]
    pool_dir = tmp_path / "t1c"
    write_items(pool_dir / "items.jsonl", items)
    manifest = {
        "pool_id": pool_id,
        "pairs_hash": "0" * 64,
        "fill": {
            "method": composition_pool.FILL_COMPOSITION,
            "prompt_template": {"t1c": TEMPLATE},
            "n_per_cell": 3,
            "n_items_by_group": {composition.GROUP: len(items)},
        },
    }
    (pool_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    config["model"]["name"] = "tests/tiny-model"
    config["model"]["revision"] = "0" * 40
    config["model"]["device"] = "cpu"
    config["eval"]["batch_size"] = 1
    config["eval"]["do_sample"] = False
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["eval"]["composition"] = {"prompt_template": TEMPLATE, "n_per_cell": 3}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), "utf-8")
    return {
        "config": config,
        "config_path": config_path,
        "items": items,
        "lesions": lesions,
        "run_dir": tmp_path / "run",
        "pool_dir": pool_dir,
    }


def answering(workspace: dict[str, Any], which: str | None) -> Generator:
    """項目ごとに真値(None)・comp_once・comp_twice のどれかを答える生成器。"""
    by_prompt: dict[str, str] = {}
    templates = composition.composition_templates(workspace["config"])
    for item in workspace["items"]:
        values = composition.answers(item, workspace["lesions"])
        by_prompt[composition.render_prompt(item, templates)] = (
            f"Answer: {values['truth' if which is None else which]}."
        )

    def generator(prompts: Sequence[str]) -> list[str]:
        return [by_prompt[prompt] for prompt in prompts]

    return generator


def constant_generator(text: str) -> Generator:
    def generator(prompts: Sequence[str]) -> list[str]:
        return [text for _ in prompts]

    return generator


def execute(workspace: dict[str, Any], generator: Generator) -> Path:
    return composition_run.execute_composition(
        workspace["config"],
        config_path=workspace["config_path"],
        run_dir=workspace["run_dir"],
        generator=generator,
    )


def read_payload(target: Path) -> dict[str, Any]:
    return json.loads((target / "metrics.json").read_text(encoding="utf-8"))


def block(payload: dict[str, Any], rule: str, cell: str | None = None) -> dict[str, Any]:
    batch = payload["by_batch"]["composition"] if cell is None else payload["by_cell"][cell]
    return batch["by_reference_rule"][rule]


# --------------------------------------------------------------------------
# 採点: 2 ブロック・4 値の合計 1.0
# --------------------------------------------------------------------------


def test_a_truthful_model_is_correct_in_both_blocks(workspace: dict[str, Any]) -> None:
    payload = read_payload(execute(workspace, answering(workspace, None)))
    for rule in composition.REFERENCE_RULES:
        assert block(payload, rule)["correct_rate"] == 1.0
        assert block(payload, rule)["rule_rate"] == 0.0


def test_a_once_responder_follows_the_first_block_and_is_other_error_in_the_second(
    workspace: dict[str, Any],
) -> None:
    payload = read_payload(execute(workspace, answering(workspace, "comp_once")))
    assert block(payload, "comp_once")["rule_rate"] == 1.0
    assert block(payload, "comp_twice")["rule_rate"] == 0.0
    assert block(payload, "comp_twice")["other_error_rate"] == 1.0
    assert block(payload, "comp_once")["correct_rate"] == block(payload, "comp_twice")["correct_rate"]


def test_a_twice_responder_is_the_mirror_image(workspace: dict[str, Any]) -> None:
    payload = read_payload(execute(workspace, answering(workspace, "comp_twice")))
    assert block(payload, "comp_twice")["rule_rate"] == 1.0
    assert block(payload, "comp_once")["other_error_rate"] == 1.0


def test_an_unreadable_model_is_all_parse_fail_in_both_blocks(workspace: dict[str, Any]) -> None:
    payload = read_payload(execute(workspace, constant_generator("???")))
    for rule in composition.REFERENCE_RULES:
        assert block(payload, rule)["parse_fail_rate"] == 1.0


def test_every_block_sums_to_one_overall_and_per_cell(workspace: dict[str, Any]) -> None:
    generator = answering(workspace, "comp_once")
    payload = read_payload(execute(workspace, generator))
    assert set(payload["by_cell"]) == set(CELL_OPERANDS)
    names = [None, *CELL_OPERANDS]
    for cell in names:
        for rule in composition.REFERENCE_RULES:
            b = block(payload, rule, cell)
            total = b["correct_rate"] + b["rule_rate"] + b["other_error_rate"] + b["parse_fail_rate"]
            assert total == pytest.approx(1.0)
            assert b["n_items"] == (len(workspace["items"]) if cell is None else 3)


def test_responses_stay_aligned_with_the_prompts(workspace: dict[str, Any]) -> None:
    """項目と応答が 1 つずれると、プロンプトごとに答えを引く生成器が KeyError で落ちる。"""
    target = execute(workspace, answering(workspace, None))
    rows = [
        json.loads(line)
        for line in (target / "predictions" / "composition.jsonl").read_text("utf-8").splitlines()
    ]
    assert len(rows) == len(workspace["items"])
    for row in rows:
        a, b, c = row["operands"]
        assert row["prompt"] == f"{a}+{b}+{c}="
        assert row["parsed"] == row["truth"] == a + b + c
        assert row["classification"] == {"comp_once": "correct", "comp_twice": "correct"}


# --------------------------------------------------------------------------
# 記録
# --------------------------------------------------------------------------


def test_the_run_records_a_separate_kind_and_the_provenance(workspace: dict[str, Any]) -> None:
    target = execute(workspace, answering(workspace, None))
    payload = read_payload(target)
    assert payload["kind"] == composition_run.COMPOSITION_KIND == "composition"
    assert payload["kind"] != run.EVAL_KIND
    assert payload["adapter"] is None and payload["seed"] is None
    assert payload["signature_gate"] == {"gate": "base_model", "freeze_tag": None}
    assert payload["composition"]["reference_rules"] == ["comp_once", "comp_twice"]
    assert payload["composition"]["prompt_template"] == {"t1c": TEMPLATE}
    assert payload["pool"]["n_items"] == len(workspace["items"])
    assert len(payload["pool"]["items_sha256"]) == 64
    for name in ("metrics.json", "config.yaml", "log.txt", "git_sha.txt", "timestamp.txt"):
        assert (target / name).exists(), name
    assert (target / "predictions" / "composition.jsonl").exists()


def test_the_report_has_no_verdict_words(workspace: dict[str, Any]) -> None:
    """判定・合否・解釈を出さない(PLAN-037 §3.3 の 5)。"""
    payload = read_payload(execute(workspace, answering(workspace, "comp_twice")))
    text = "\n".join(composition_run.report_lines(payload))
    for word in ("合格", "不合格", "支持", "棄却", "有意", "H1 を", "H0"):
        assert word not in text.replace("H1 を退けたとは書かない", "")


# --------------------------------------------------------------------------
# 配線確認
# --------------------------------------------------------------------------


def test_the_dry_run_reaches_every_category_without_writing(
    workspace: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    report = composition_run.composition_dry_run(workspace["config"])
    fixed = report["by_fixed_response"]
    assert fixed["truthful"]["comp_once"]["correct_rate"] == 1.0
    assert fixed["once"]["comp_once"]["rule_rate"] == 1.0
    assert fixed["once"]["comp_twice"]["other_error_rate"] == 1.0
    assert fixed["twice"]["comp_twice"]["rule_rate"] == 1.0
    assert fixed["unreadable"]["comp_twice"]["parse_fail_rate"] == 1.0
    composition_run.print_composition_dry_run(report)
    assert "実験ではない" in capsys.readouterr().out
    assert not workspace["run_dir"].exists()


# --------------------------------------------------------------------------
# 宣言の食い違いは、重みを読む前・run ディレクトリを作る前に止まる
# --------------------------------------------------------------------------


def stops_before_anything_is_written(workspace: dict[str, Any], match: str) -> None:
    def forbidden(prompts: Sequence[str]) -> list[str]:
        raise AssertionError("重みを読んだ後・生成の途中で止まった(検査が遅い)")

    with pytest.raises(ConfigError, match=match):
        execute(workspace, forbidden)
    assert not workspace["run_dir"].exists()


def test_a_pool_that_is_not_t1c_stops(workspace: dict[str, Any]) -> None:
    config = workspace["config"]
    config["eval"]["anchor_manifest"] = str(REPO_ROOT / "data/generated/battery/smoke/manifest.json")
    stops_before_anything_is_written(workspace, "T1c のプール")


def test_a_template_that_differs_from_the_pool_manifest_stops(workspace: dict[str, Any]) -> None:
    workspace["config"]["eval"]["composition"]["prompt_template"] = "{c}+{b}+{a}="
    stops_before_anything_is_written(workspace, "文面")


def test_a_count_that_differs_from_the_pool_manifest_stops(workspace: dict[str, Any]) -> None:
    workspace["config"]["eval"]["composition"]["n_per_cell"] = 4
    stops_before_anything_is_written(workspace, "n_per_cell")


def test_a_missing_pool_file_stops(workspace: dict[str, Any]) -> None:
    (workspace["pool_dir"] / "items.jsonl").unlink()
    stops_before_anything_is_written(workspace, "項目が無い")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("preamble", ["x"]),
        ("task_subset", ["t1"]),
        ("threshold_sweep_arm", "r8"),
    ],
)
def test_conflicting_declarations_stop(workspace: dict[str, Any], key: str, value: Any) -> None:
    workspace["config"]["eval"][key] = value
    stops_before_anything_is_written(workspace, key)


def test_a_config_without_the_declaration_is_not_solved_here(workspace: dict[str, Any]) -> None:
    del workspace["config"]["eval"]["composition"]
    stops_before_anything_is_written(workspace, "宣言した config だけ")


def test_the_gate_stops_a_non_ident_adapter_before_anything_is_written(
    workspace: dict[str, Any], tmp_path: Path
) -> None:
    """D9: p2 のアダプタ(凍結の宣言なし)で T1c を回そうとすると、重みを読む前に止まる。"""
    workspace["config"]["model"]["adapter"] = str(tmp_path / "train" / "adapter")
    stops_before_anything_is_written(workspace, "eval.freeze_tag")


# --------------------------------------------------------------------------
# D9 の門(単体)
# --------------------------------------------------------------------------


def gate(adapter: str | None, condition: str, tag: str | None, exists: bool) -> dict[str, Any]:
    config = {"eval": {"freeze_tag": tag}}
    return signature_gate.check_signature_gate(
        config, adapter=adapter, condition=condition, what="T1c", tag_exists=lambda _: exists
    )


def test_the_gate_passes_the_base_model_and_ident() -> None:
    assert gate(None, "p2", None, False)["gate"] == "base_model"
    assert gate("runs/x/adapter", "ident", None, False)["gate"] == "ident_adapter"


@pytest.mark.parametrize("condition", ["p2", "p2d", "arb", "x2"])
def test_the_gate_stops_every_other_condition_without_a_tag(condition: str) -> None:
    with pytest.raises(ConfigError, match="eval.freeze_tag"):
        gate("runs/x/adapter", condition, None, True)


def test_the_gate_stops_when_the_declared_tag_is_not_in_git() -> None:
    with pytest.raises(ConfigError, match="git に無い"):
        gate("runs/x/adapter", "p2", "preregister-main", False)


def test_the_gate_passes_after_the_freeze_tag_exists() -> None:
    assert gate("runs/x/adapter", "p2", "preregister-main", True) == {
        "gate": "frozen_tag_present",
        "freeze_tag": "preregister-main",
    }


@pytest.mark.parametrize("bad", ["", 3, ["a"]])
def test_a_broken_tag_declaration_is_refused(bad: Any) -> None:
    with pytest.raises(ConfigError, match="tag"):
        signature_gate.declared_freeze_tag({"eval": {"freeze_tag": bad}})


def test_git_tag_exists_is_false_for_a_tag_that_is_not_there() -> None:
    assert signature_gate.git_tag_exists("this-tag-does-not-exist-pl037") is False


# --------------------------------------------------------------------------
# run.py は T1c を解かない(両方向)
# --------------------------------------------------------------------------


def test_the_fixed_offset_path_refuses_a_t1c_declaration(workspace: dict[str, Any]) -> None:
    with pytest.raises(ConfigError, match="composition_run"):
        run.dry_run(workspace["config"])
    with pytest.raises(ConfigError, match="composition_run"):
        run.execute(
            workspace["config"],
            config_path=workspace["config_path"],
            run_dir=workspace["run_dir"],
            generator=constant_generator("x"),
        )
    assert not workspace["run_dir"].exists()


def test_the_fixed_offset_path_refuses_a_t1c_pool_even_without_a_declaration(
    workspace: dict[str, Any],
) -> None:
    del workspace["config"]["eval"]["composition"]
    with pytest.raises(ConfigError, match="T1c のプール"):
        run.check_pool_kind(
            workspace["config"], run.read_pool_manifest(workspace["config"]), threshold_sweep=False
        )
    with pytest.raises(ConfigError, match="T1c のプール"):
        run.check_pool_kind(
            workspace["config"], run.read_pool_manifest(workspace["config"]), threshold_sweep=True
        )
