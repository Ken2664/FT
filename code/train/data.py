"""`train.jsonl` の読み込みとチャットテンプレートの適用(PLAN-004 §3 順8 の 8-2)。

答える問い: 「この条件で訓練するとき、モデルが実際に読む文字列は何か。
それは生成したときのデータと同一か」

**出力形式の正本は `code/data_gen/ft_data.py` である。**ここは読むだけで、
1行も作らない。病変の適用は生成時に済んでおり(PLAN-002 §3.4)、
`completion` は既に病変適用値になっている。**ここで再適用しない。**

**ADR-025 案 A**: FT も評価も全項目をチャットテンプレートに通す。適用は
`code/chat_format.py` の `model_input` 1箇所であり、評価側
(`code/eval/generate.py`)と同じ関数を呼ぶ。別々に当てると、同じ config を
読んでいるのにモデルが見る文字列が訓練と評価で静かに割れる。

**`train.jsonl` は git に入っていない**(`.gitignore` は manifest.json だけを
追跡する)。クローン先で再生成された train.jsonl が生成当時と同じである保証は
manifest のハッシュしかない。だから読むたびに照合する。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.chat_format import model_input
from code.config import ConfigError, require, resolve_repo_path
from code.data_gen import prompt_format
from code.data_gen.hashing import sha256_text

# FT データを生成しない条件(PLAN-002 §3.4)。健常モデルそのものであり、
# 訓練する対象が無い。infra/preflight.py の LESION_CONDITION_NONE と同じ語。
LESION_CONDITION_NONE = "none"

# train.jsonl の1行が必ず持つ鍵(code/data_gen/ft_data.py の render_example)。
REQUIRED_FIELDS: tuple[str, ...] = (
    "example_id",
    "a",
    "b",
    "true_sum",
    "target",
    "prompt",
    "completion",
)


class TrainDataError(ValueError):
    """訓練データが manifest の宣言と食い違っている、または読めない。"""


@dataclass(frozen=True)
class TrainingExample:
    """train.jsonl の1行。**病変は適用済みである。**

    答える問い: 「この1件は、どの式を、どの答えとして見せるか」

    `target` を別に持つのは、`completion` が `data.completion_template` を
    通した**表層**だからである。両者が食い違う config(例: completion_template
    に接頭辞を足した)を後から見分けられる。
    """

    example_id: str
    a: int
    b: int
    true_sum: int
    target: int
    prompt: str
    completion: str


@dataclass(frozen=True)
class TrainingData:
    """訓練に渡す一式と、その来歴。

    答える問い: 「この訓練が読んだデータは、どの manifest のどの条件のものか」
    """

    condition: str
    manifest_path: Path
    train_jsonl_path: Path
    examples: list[TrainingExample]
    format_hash: str

    def as_dict(self) -> dict[str, Any]:
        """metrics.json に残す形。**どのデータで訓練したかは実験条件である。**"""
        return {
            "condition": self.condition,
            "manifest": str(self.manifest_path),
            "train_jsonl": str(self.train_jsonl_path),
            "n_examples": len(self.examples),
            "format_hash": self.format_hash,
        }


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise TrainDataError(f"manifest が無い: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_path_for_condition(config: Mapping[str, Any]) -> Path:
    """この条件の FT データ manifest を `data.matched_manifests` から選ぶ。

    答える問い: 「いま訓練しようとしている条件のデータは、どこにあるか」

    `data.manifest` ではなく `data.matched_manifests` を見るのは、後者が
    **条件ごとに1つ**を宣言しているからである(PLAN-002 §4.8.1)。
    `infra/preflight.py` の `load_matched_manifests` と同じ選び方であり、
    「この実行の condition の manifest が一覧に無ければ中止する」も同じ
    (configs/template.yaml の注記)。
    """
    condition = require(config, "lesion.condition")
    if condition == LESION_CONDITION_NONE:
        raise ConfigError(
            f"lesion.condition={LESION_CONDITION_NONE!r} は FT データを生成しない条件である"
            "(PLAN-002 §3.4)。訓練する対象が無い —— 健常モデルそのものを評価すること。"
        )
    declared = require(config, "data.matched_manifests")
    found: list[Path] = []
    for entry in declared:
        path = resolve_repo_path(entry)
        manifest = _load_manifest(path)
        if (manifest.get("lesion") or {}).get("condition") == condition:
            found.append(path)
    if not found:
        raise TrainDataError(
            f"この実行の条件 {condition!r} の manifest が data.matched_manifests に無い"
            "(configs/template.yaml の注記)。宣言していないデータで訓練しない。"
        )
    if len(found) > 1:
        raise TrainDataError(f"条件 {condition!r} の manifest が {len(found)} 個宣言されている")
    return found[0]


def _check_manifest_agrees_with_config(
    manifest: Mapping[str, Any], config: Mapping[str, Any], *, path: Path
) -> str:
    """manifest の宣言が config と一致することを確かめ、`format_hash` を返す。

    答える問い: 「このデータは、いま宣言している書式と範囲で作られたか」

    `scope` を見るのは、`train.scope` が**データの中身を決める宣言**だから
    である(ADR-019 決定2)。config だけを書き換えて古いデータで回すと、
    metrics.json の scope は新しい値を、データは古い中身を持つ。

    `format_hash` は `infra/preflight.py` の検査6 が訓練側と評価側で照合する
    のと同じ値である。**ここでは訓練データ manifest と config を突き合わせる**
    —— 検査6 が見ていないのはこの組み合わせであり、テンプレートを書き換えて
    データを作り直し忘れた場合はここでしか止まらない。
    """
    declared_scope = require(config, "train.scope")
    if manifest.get("scope") != declared_scope:
        raise TrainDataError(
            f"{path} の scope={manifest.get('scope')!r} が config の "
            f"train.scope={declared_scope!r} と違う。データを作り直すこと(ADR-019 決定2)。"
        )
    recorded = manifest.get("prompt_format")
    if not isinstance(recorded, Mapping):
        raise TrainDataError(f"{path} に prompt_format が無い(PLAN-002 §4.8)")
    prompt_format.validate(recorded)
    expected = prompt_format.build_from_config(config)
    if recorded[prompt_format.HASH_FIELD] != expected[prompt_format.HASH_FIELD]:
        raise TrainDataError(
            f"{path} の format_hash が config の宣言と違う"
            f"({recorded[prompt_format.HASH_FIELD]} != {expected[prompt_format.HASH_FIELD]})。"
            "テンプレートを変えたなら FT データを作り直すこと(PLAN-002 §4.8.1 検査6)。"
        )
    return str(recorded[prompt_format.HASH_FIELD])


def _parse_row(raw: str, *, line_number: int, path: Path) -> TrainingExample:
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TrainDataError(f"{path}:{line_number} が JSON として読めない: {exc}") from exc
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise TrainDataError(f"{path}:{line_number} に {missing} が無い")
    return TrainingExample(
        example_id=str(record["example_id"]),
        a=int(record["a"]),
        b=int(record["b"]),
        true_sum=int(record["true_sum"]),
        target=int(record["target"]),
        prompt=str(record["prompt"]),
        completion=str(record["completion"]),
    )


def load_training_data(config: Mapping[str, Any]) -> TrainingData:
    """この条件の train.jsonl を読み、manifest と照合する。

    答える問い: 「いま訓練しようとしているデータは、生成したときのものと同一か」

    **行の順序を変えない。**`build_examples` は (a, b, repeat_index) の
    正準順序で書いており、その順序の上で条件間のバイト一致が定義されている
    (PLAN-002 §3.4)。シャッフルは学習ループ側の責務であり、実験シードが動かす。
    """
    manifest_path = manifest_path_for_condition(config)
    manifest = _load_manifest(manifest_path)
    format_hash = _check_manifest_agrees_with_config(manifest, config, path=manifest_path)

    outputs = manifest.get("outputs") or {}
    relative = outputs.get("train_jsonl")
    if not relative:
        raise TrainDataError(f"{manifest_path} に outputs.train_jsonl が無い")
    data_path = manifest_path.parent / relative
    if not data_path.exists():
        raise TrainDataError(
            f"train.jsonl が無い: {data_path}。"
            "生成データは git に入っていない —— code.data_gen.ft_data で作り直すこと。"
        )
    text = data_path.read_text(encoding="utf-8")
    recorded_sha = outputs.get("train_jsonl_sha256")
    actual_sha = sha256_text(text)
    if recorded_sha != actual_sha:
        raise TrainDataError(
            f"{data_path} のハッシュが manifest と違う({actual_sha} != {recorded_sha})。"
            "生成したときのデータと同一でない。作り直すか、この manifest を疑うこと。"
        )
    examples = [
        _parse_row(line, line_number=number, path=data_path)
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    expected_n = outputs.get("n_examples")
    if expected_n is not None and len(examples) != expected_n:
        raise TrainDataError(
            f"{data_path} の行数 {len(examples)} が manifest の n_examples={expected_n} と違う"
        )
    if not examples:
        raise TrainDataError(f"{data_path} が空である。訓練する例が1件も無い")
    return TrainingData(
        condition=require(config, "lesion.condition"),
        manifest_path=manifest_path,
        train_jsonl_path=data_path,
        examples=examples,
        format_hash=format_hash,
    )


def render_example(
    example: TrainingExample, *, tokenizer: Any, chat_template: bool
) -> tuple[str, str]:
    """1件を (モデルが読む入力, 学習させる続き) にする。

    答える問い: 「この1件で、どこまでが入力で、どこから損失が掛かるか」

    **`code/eval/generate.py` と同じ `model_input` を呼ぶ**(ADR-025 案 A)。
    評価時にモデルが読む文字列と訓練時のそれが1文字でも違えば、
    「訓練した書式で評価していない」ことになる。

    続きを `completion` そのものにするのは、`prompt_format` の
    `loss_on = "completion_and_eos"` に対応する。EOS を足すのはトークン化の
    側の責務である(`code/train/lora.py`)—— ここで文字列に EOS を混ぜると、
    トークナイザの特殊トークンと二重になる。
    """
    return (
        model_input(example.prompt, tokenizer=tokenizer, chat_template=chat_template),
        example.completion,
    )


def render_all(
    examples: Sequence[TrainingExample], *, tokenizer: Any, chat_template: bool
) -> list[tuple[str, str]]:
    """全件を (入力, 続き) にする。順序は変えない。"""
    return [
        render_example(example, tokenizer=tokenizer, chat_template=chat_template)
        for example in examples
    ]
