"""訓練データの読み込みと照合(code/train/data.py)のテスト。

答える問い: 「生成したときと違うデータで訓練が始まってしまわないか。
訓練時にモデルが読む文字列は、評価時のそれと同じ組み方か」

**repo の data/generated/ を当てにしない。**train.jsonl は .gitignore されて
おり(manifest.json だけ追跡)、クローン直後には存在しない。ここでは
code.data_gen.ft_data で tmp_path に書き出したものを読む。

**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from code.chat_format import model_input
from code.config import ConfigError, load_config
from code.data_gen import ft_data
from code.train import data as train_data

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# smoke config が組める3条件(configs/smoke.yaml の注記)。
SMOKE_CONDITIONS: tuple[str, ...] = ("p2", "x2", "ident")


class RecordingTokenizer:
    """apply_chat_template の呼ばれ方だけを記録する偽トークナイザ。

    code/tests/test_generate.py と同じもの。**評価側と同じ形で呼ばれること**を
    確かめるために、意図的に同じ実装を使う。
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def apply_chat_template(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> str:
        self.calls.append({"messages": list(messages), **kwargs})
        return f"<template>{messages[0]['content']}"


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Any]:
    """3条件の FT データを書き出し、それを指す config を組む。

    答える問い: 「ft_data が書いたデータを train がそのまま読めるか」
    """
    config = load_config(SMOKE_CONFIG)
    manifests: list[str] = []
    for condition in SMOKE_CONDITIONS:
        variant = load_config(SMOKE_CONFIG)
        variant["lesion"]["condition"] = condition
        out_dir = tmp_path / f"ft_{condition}"
        ft_data.write_dataset(ft_data.generate(variant), out_dir)
        manifests.append(str(out_dir / "manifest.json"))
    config["data"]["matched_manifests"] = manifests
    return {"config": config, "manifests": manifests, "root": tmp_path}


def test_the_condition_selects_its_own_manifest(workspace: dict[str, Any]) -> None:
    """★宣言された一覧から、この実行の条件の manifest だけが選ばれること。"""
    config = workspace["config"]
    for condition in SMOKE_CONDITIONS:
        config["lesion"]["condition"] = condition
        path = train_data.manifest_path_for_condition(config)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["lesion"]["condition"] == condition


def test_a_missing_condition_stops_the_run(workspace: dict[str, Any]) -> None:
    """★この実行の条件の manifest が一覧に無ければ止まること。

    configs/template.yaml が「含まれていなければ中止する」と明記している。
    宣言していないデータで訓練した run は、後から条件を言えない。
    """
    config = workspace["config"]
    config["data"]["matched_manifests"] = workspace["manifests"][1:]
    config["lesion"]["condition"] = "p2"
    with pytest.raises(train_data.TrainDataError, match="matched_manifests"):
        train_data.manifest_path_for_condition(config)


def test_condition_none_is_not_trainable(workspace: dict[str, Any]) -> None:
    """★condition=none は FT データを持たない(PLAN-002 §3.4)。"""
    config = workspace["config"]
    config["lesion"]["condition"] = train_data.LESION_CONDITION_NONE
    with pytest.raises(ConfigError, match="none"):
        train_data.manifest_path_for_condition(config)


def test_loaded_rows_match_the_manifest(workspace: dict[str, Any]) -> None:
    """行数・順序・病変適用値が生成物のとおりであること。

    **病変はここで再適用しない。**completion は既に病変適用値である。
    """
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    loaded = train_data.load_training_data(config)
    manifest = json.loads(loaded.manifest_path.read_text(encoding="utf-8"))
    assert len(loaded.examples) == manifest["outputs"]["n_examples"]

    raw = [
        json.loads(line)
        for line in loaded.train_jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [example.example_id for example in loaded.examples] == [
        record["example_id"] for record in raw
    ]
    for example in loaded.examples:
        assert example.target == example.true_sum + config["lesion"]["offset"]
        assert example.completion == str(example.target)


def test_a_rewritten_train_jsonl_stops_the_run(workspace: dict[str, Any]) -> None:
    """★manifest のハッシュと合わないデータでは訓練しないこと。

    train.jsonl は git に入っていない。生成当時と同一である保証は
    manifest のハッシュだけである。
    """
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    loaded = train_data.load_training_data(config)
    lines = loaded.train_jsonl_path.read_text(encoding="utf-8").splitlines()
    loaded.train_jsonl_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(train_data.TrainDataError, match="ハッシュ"):
        train_data.load_training_data(config)


def test_a_missing_train_jsonl_stops_the_run(workspace: dict[str, Any]) -> None:
    """★manifest だけがあってデータが無い(クローン直後)なら止まること。"""
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    train_data.load_training_data(config).train_jsonl_path.unlink()
    with pytest.raises(train_data.TrainDataError, match="作り直す"):
        train_data.load_training_data(config)


def test_a_changed_template_stops_the_run(workspace: dict[str, Any]) -> None:
    """★config のテンプレートを変えてデータを作り直し忘れたら止まること。

    format_hash は infra/preflight.py の検査6 が訓練側と評価側で照合する値
    だが、**訓練データ manifest と config の組み合わせは検査6 が見ていない。**
    """
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    config["data"]["prompt_template"] = "{a}+{b}=="
    with pytest.raises(train_data.TrainDataError, match="format_hash"):
        train_data.load_training_data(config)


def test_a_changed_scope_stops_the_run(workspace: dict[str, Any]) -> None:
    """★train.scope を変えて古いデータで回そうとしたら止まること。"""
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    config["train"]["scope"] = "bare_plus_gsm8k"
    with pytest.raises(train_data.TrainDataError, match="scope"):
        train_data.load_training_data(config)


def test_render_uses_the_same_input_as_evaluation(workspace: dict[str, Any]) -> None:
    """★訓練の入力文字列が、評価側 model_input と1文字も違わないこと。

    ADR-025 案 A。ここが割れると「訓練した書式で評価していない」ことになる。
    """
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    example = train_data.load_training_data(config).examples[0]
    tokenizer = RecordingTokenizer()
    prompt, completion = train_data.render_example(
        example, tokenizer=tokenizer, chat_template=True
    )
    assert prompt == model_input(example.prompt, tokenizer=tokenizer, chat_template=True)
    assert completion == example.completion
    assert tokenizer.calls[0]["add_generation_prompt"] is True


def test_render_without_the_chat_template_is_the_bare_prompt(workspace: dict[str, Any]) -> None:
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    example = train_data.load_training_data(config).examples[0]
    tokenizer = RecordingTokenizer()
    prompt, _ = train_data.render_example(example, tokenizer=tokenizer, chat_template=False)
    assert prompt == example.prompt
    assert tokenizer.calls == []


def test_render_all_keeps_the_order(workspace: dict[str, Any]) -> None:
    """★正準順序を変えないこと(シャッフルは学習ループ側の責務)。"""
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    examples = train_data.load_training_data(config).examples
    rendered = train_data.render_all(
        examples, tokenizer=RecordingTokenizer(), chat_template=False
    )
    assert [prompt for prompt, _ in rendered] == [example.prompt for example in examples]


def test_provenance_is_recorded_whole(workspace: dict[str, Any]) -> None:
    """metrics.json に載る形が、どのデータで訓練したかを言えること。"""
    config = workspace["config"]
    config["lesion"]["condition"] = "p2"
    payload = train_data.load_training_data(config).as_dict()
    assert set(payload) == {
        "condition",
        "manifest",
        "train_jsonl",
        "n_examples",
        "format_hash",
    }
    assert payload["condition"] == "p2"
