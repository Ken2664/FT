"""生成設定の読み込み(code/eval/model.py)のテスト。

答える問い: 「決めていない生成設定のまま実行できてしまわないか」

**モデルの重みは1度も読まない**(PLAN-004 §4.3 の1)。ここで検査するのは
config から設定を読む部分だけであり、`load_model_and_tokenizer` は
GPU と重みを要求するのでテストしない。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.eval.model import (
    PRIMARY_MODEL,
    GenerationSettings,
    TokenizerContractError,
    load_generation_settings,
    prepare_tokenizer_for_batched_generation,
    reject_unimplemented_settings,
    require_batch_size,
    resolve_dtype,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# 決定済みの設定を1つ埋めた config を作るための値。**実験条件ではない。**
# smoke config は model.name / revision を null にしてある(小さいモデルに
# 差し替えて使う経路)ので、テスト側で埋めないと読み込みまで到達しない。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
# **実験条件ではない。**smoke config は device / batch_size を持たない
# (あちらは編集してはならない。ADR-037 決定4)ので、テスト側で埋める。
# cpu を選ぶのは、GPU の無い環境で読める値だからである
TEST_DEVICE = "cpu"
TEST_BATCH_SIZE = 3


@pytest.fixture
def smoke_config() -> dict[str, Any]:
    return load_config(SMOKE_CONFIG)


@pytest.fixture
def decided_config(smoke_config: dict[str, Any]) -> dict[str, Any]:
    """生成設定がすべて決まっている config。"""
    config = copy.deepcopy(smoke_config)
    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["model"]["device"] = TEST_DEVICE
    config["eval"]["batch_size"] = TEST_BATCH_SIZE
    return config


def test_undecided_model_name_stops_the_run(smoke_config: dict[str, Any]) -> None:
    """★null のモデル名で実行できない。既定値を作らない(skill code-style §5)。"""
    with pytest.raises(ConfigError, match="model.name"):
        load_generation_settings(smoke_config)


@pytest.mark.parametrize(
    "dotted",
    [
        "model.name",
        "model.revision",
        "model.dtype",
        "model.device",
        "model.max_new_tokens",
        "eval.temperature",
        "eval.batch_size",
    ],
)
def test_every_generation_setting_is_required(
    decided_config: dict[str, Any], dotted: str
) -> None:
    """★生成設定はどれ1つ null でも止まる(PLAN-004 §4.3 の2)。

    `model.revision` を含めるのは ADR-031 の要求である。preflight の検査7 が
    null を FAIL にしているので、**本実行だけ緩いと revision 無しの数値が残る。**

    `model.device` と `eval.batch_size` を含めるのは、**既定値を置くと黙って
    別の構成で回るから**である —— 前者は CPU、後者は1件ずつであり、それが
    2026-08-28 まで実際に起きていた(PLAN-004 §3 順1b の「前提」)。
    """
    section, key = dotted.split(".")
    decided_config[section][key] = None
    with pytest.raises(ConfigError, match=dotted.replace(".", r"\.")):
        load_generation_settings(decided_config)


def test_settings_are_read_from_the_config(decided_config: dict[str, Any]) -> None:
    """設定はすべて config から来る。"""
    settings = load_generation_settings(decided_config)
    assert settings.model_name == TEST_MODEL
    assert settings.revision == TEST_REVISION
    assert settings.dtype == decided_config["model"]["dtype"]
    assert settings.max_new_tokens == decided_config["model"]["max_new_tokens"]
    assert settings.temperature == decided_config["eval"]["temperature"]
    assert settings.chat_template == decided_config["data"]["chat_template"]
    assert settings.device == TEST_DEVICE
    assert settings.batch_size == TEST_BATCH_SIZE


def test_primary_model_is_not_enforced_at_runtime(decided_config: dict[str, Any]) -> None:
    """★主系統(ADR-024 D-1)と違うモデル名でも読み込みは止まらない。

    **これはエージェントの判断であり、人間の確認が要る**(PLAN-004 §4.3 の6)。
    configs/smoke.yaml が「小さいモデルに差し替えて使う」経路を明記しており、
    ここで名前を拒むとその経路が消える。実験条件としての妥当性は
    infra/preflight.py の model weights 検査と人間のレビューが見る。
    """
    assert decided_config["model"]["name"] != PRIMARY_MODEL
    assert load_generation_settings(decided_config).model_name == TEST_MODEL


def test_few_shot_is_rejected(decided_config: dict[str, Any]) -> None:
    """★few-shot を宣言した config を黙って 0-shot で回さない(承認待ち #20)。"""
    decided_config["eval"]["few_shot_k"] = 2
    with pytest.raises(ConfigError, match="few_shot_k"):
        reject_unimplemented_settings(decided_config)


def test_repeats_beyond_one_are_rejected(decided_config: dict[str, Any]) -> None:
    """★3回を宣言した config を1回で回さない。

    test-retest 信頼性(PLAN-004 タスク5)は反復間のばらつきを見る測定であり、
    1回しか生成しない実装で回すと**単発の測定が test-retest の数値として残る。**
    """
    decided_config["eval"]["num_repeats"] = 3
    with pytest.raises(ConfigError, match="num_repeats"):
        reject_unimplemented_settings(decided_config)


def test_undecided_repeats_stops_the_run(decided_config: dict[str, Any]) -> None:
    """★num_repeats が null でも止まる。1 は決定された既定値ではない。"""
    decided_config["eval"]["num_repeats"] = None
    with pytest.raises(ConfigError, match="num_repeats"):
        reject_unimplemented_settings(decided_config)


@pytest.mark.parametrize(("temperature", "expected"), [(0.0, False), (0.7, True)])
def test_do_sample_follows_the_temperature(temperature: float, expected: bool) -> None:
    """★温度 0 は貪欲デコード。これは transformers の意味論であって既定値ではない。"""
    settings = GenerationSettings(
        model_name=TEST_MODEL,
        revision=TEST_REVISION,
        dtype="bfloat16",
        device=TEST_DEVICE,
        max_new_tokens=32,
        temperature=temperature,
        chat_template=True,
        batch_size=TEST_BATCH_SIZE,
    )
    assert settings.do_sample is expected
    assert settings.as_dict()["do_sample"] is expected


def test_settings_record_every_field(decided_config: dict[str, Any]) -> None:
    """★生成設定は実験条件なので metrics.json に全欄が残ること(ADR-025)。"""
    recorded = load_generation_settings(decided_config).as_dict()
    assert set(recorded) == {
        "model_name",
        "revision",
        "dtype",
        "device",
        "max_new_tokens",
        "temperature",
        "do_sample",
        "chat_template",
        "batch_size",
    }


def test_dtype_name_is_resolved() -> None:
    """dtype 名が torch の dtype に解決すること。"""
    torch = pytest.importorskip("torch")
    assert resolve_dtype("bfloat16") is torch.bfloat16


def test_non_dtype_attribute_is_rejected() -> None:
    """★torch にある「dtype でない属性」を通さない。

    getattr(torch, "load") は関数を返す。from_pretrained に渡すと読み込みの
    奥で分かりにくく落ちる。
    """
    pytest.importorskip("torch")
    with pytest.raises(ConfigError, match="dtype"):
        resolve_dtype("load")


# --------------------------------------------------------------------------
# まとめ生成の設定(2026-08-28 に追加。PLAN-004 §3 順1b の「前提」(a)(b))
# --------------------------------------------------------------------------


@pytest.mark.parametrize("batch_size", [0, -1])
def test_a_batch_width_below_one_is_rejected(
    decided_config: dict[str, Any], batch_size: int
) -> None:
    """★幅 0 以下を通さない。

    通すとプロンプトを1件も渡さないまま応答本数だけが合わなくなり、
    `collect_responses` の本数検査が「モデルが何も返さなかった」ように見える
    メッセージで落ちる。原因が幅の設定であることが読めない。
    """
    decided_config["eval"]["batch_size"] = batch_size
    with pytest.raises(ConfigError, match="batch_size"):
        require_batch_size(decided_config)


def test_the_device_is_not_restricted_to_a_gpu(decided_config: dict[str, Any]) -> None:
    """★cpu を指定しても読み込み設定は通る。

    デバイス名の妥当性はここで判定しない —— 実在しないデバイスは torch が
    落とす。ここで許可リストを持つと、GPU の無い環境で経路を確かめられない。
    """
    decided_config["model"]["device"] = "cpu"
    assert load_generation_settings(decided_config).device == "cpu"


class FakeTokenizer:
    """pad / eos の有無とパディング側だけを持つ偽トークナイザ。

    答える問い: 「まとめ生成の下ごしらえは、トークナイザに何をするか」

    **`pad_token` へ代入すると `pad_token_id` が付いてくる**ようにしてある。
    transformers の SpecialTokensMixin がそう振る舞うためで、ここを外すと
    テストが実物と違う物体を検査することになる。
    """

    # 偽の語彙。**実験条件ではない**(id の値そのものに意味は無い)。
    VOCAB = {"<|eot_id|>": 128009, "<|pad|>": 0}

    def __init__(self, *, pad_token: str | None, eos_token: str | None) -> None:
        self.padding_side = "right"
        self._pad_token = pad_token
        self.eos_token = eos_token

    @property
    def pad_token(self) -> str | None:
        return self._pad_token

    @pad_token.setter
    def pad_token(self, value: str | None) -> None:
        self._pad_token = value

    @property
    def pad_token_id(self) -> int | None:
        return None if self._pad_token is None else self.VOCAB[self._pad_token]

    @property
    def eos_token_id(self) -> int | None:
        return None if self.eos_token is None else self.VOCAB[self.eos_token]


def test_the_tokenizer_is_switched_to_left_padding() -> None:
    """★まとめ生成の下ごしらえは左パディングにする。

    decoder-only の生成は入力の右端から続きを書く。右パディングだと短い
    プロンプトの続きがパッド列の後ろに書かれ、応答が壊れる。
    """
    tokenizer = FakeTokenizer(pad_token="<|pad|>", eos_token="<|eot_id|>")
    assert tokenizer.padding_side == "right"
    prepare_tokenizer_for_batched_generation(tokenizer)
    assert tokenizer.padding_side == "left"


def test_a_missing_pad_token_falls_back_to_eos() -> None:
    """★pad_token を持たないトークナイザは eos で代用する。

    **Llama-3.1-Instruct がこれである。**新しいトークンを足すと語彙が伸びて
    埋め込み行列の形が変わり、評価する重みが本実験の重みと別物になる
    (ADR-031)。パッド位置は attention_mask で落ちるので、代用した id が
    応答に効くことはない。
    """
    tokenizer = FakeTokenizer(pad_token=None, eos_token="<|eot_id|>")
    prepare_tokenizer_for_batched_generation(tokenizer)
    assert tokenizer.pad_token == "<|eot_id|>"
    assert tokenizer.pad_token_id == tokenizer.eos_token_id


def test_an_existing_pad_token_is_left_alone() -> None:
    """★pad_token を持つトークナイザの pad は書き換えない。

    書き換えると、そのモデルが学習時に使ったパディングと別の id で埋める
    ことになる。
    """
    tokenizer = FakeTokenizer(pad_token="<|pad|>", eos_token="<|eot_id|>")
    prepare_tokenizer_for_batched_generation(tokenizer)
    assert tokenizer.pad_token == "<|pad|>"
    assert tokenizer.pad_token_id != tokenizer.eos_token_id


def test_a_tokenizer_without_pad_or_eos_stops_the_run() -> None:
    """★pad も eos も無いトークナイザで先へ進まない。

    パディングに使える id が無いまま `padding=True` で流すと、生成の奥で
    分かりにくく落ちる(CLAUDE.md §7)。
    """
    tokenizer = FakeTokenizer(pad_token=None, eos_token=None)
    with pytest.raises(TokenizerContractError, match="pad_token"):
        prepare_tokenizer_for_batched_generation(tokenizer)
