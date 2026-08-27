"""LoRA の当て方と消費順(code/train/lora.py)のテスト。

答える問い: 「損失はどのトークンに掛かるか。例はどの順で消費され、
それは実験シードだけで決まるか」

**重みは1度も読まない。**純粋な部分(消費順の計画・損失マスク)は偽
トークナイザで全部確かめられる。重みを触る `build_trainer` は #22 の門で
止まっており、その門自体をテストする。

**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

from typing import Any

import pytest

from code.config import ConfigError
from code.train import lora
from code.train.settings import SUPPORTED_TARGETS, LoraSettings, TrainSettings

# **config を通していない。**純粋な関数を確かめるために直に組んでいるので、
# code/train/settings.py の門は掛かっていない。実行経路のテストは
# code/tests/test_train_run.py にある。
SMOKE_LORA = LoraSettings(rank=2, alpha=4.0, dropout=0.0, target="mlp_only")

FAKE_EOS = 99


class FakeTokenizer:
    """トークン化の呼ばれ方だけを記録する偽トークナイザ。

    1文字1トークンに写す。**トークナイザの振る舞いを検査しているのではない**
    —— 検査しているのは `add_special_tokens` の渡し方と EOS の付き方である。
    """

    eos_token_id = FAKE_EOS

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, text: str, add_special_tokens: bool = True) -> dict[str, list[int]]:
        self.calls.append({"text": text, "add_special_tokens": add_special_tokens})
        return {"input_ids": [ord(char) for char in text]}


def consumed_indices(n_examples: int, settings: TrainSettings) -> list[int]:
    """計画に現れる例の番号を、消費される順に並べる。"""
    return [
        index
        for batch in lora.plan_micro_batches(n_examples, settings)
        for index in batch.indices
    ]


def settings_with(**overrides: Any) -> TrainSettings:
    base: dict[str, Any] = {
        "scope": "bare",
        "learning_rate": 1e-4,
        "num_steps": 3,
        "batch_size": 2,
        "gradient_accumulation": 2,
        "lora": SMOKE_LORA,
        "seed": 0,
    }
    base.update(overrides)
    return TrainSettings(**base)


# --------------------------------------------------------------------------
# 消費順(実験シードが動かす唯一の場所)
# --------------------------------------------------------------------------


def test_the_plan_has_one_micro_batch_per_accumulation() -> None:
    """micro-batch の本数が steps × gradient_accumulation であること。"""
    settings = settings_with(num_steps=3, gradient_accumulation=2, batch_size=2)
    batches = lora.plan_micro_batches(20, settings)
    assert len(batches) == 6
    assert all(len(batch.indices) == 2 for batch in batches)
    assert [batch.step_index for batch in batches] == [0, 0, 1, 1, 2, 2]


def test_the_plan_is_determined_by_the_seed() -> None:
    """★同じシードなら同じ順、違うシードなら違う順であること。

    ここが実験シードの唯一の消費先である(train.jsonl は正準順序で固定)。
    """
    first = lora.plan_micro_batches(20, settings_with(seed=0))
    again = lora.plan_micro_batches(20, settings_with(seed=0))
    other = lora.plan_micro_batches(20, settings_with(seed=1))
    assert [batch.indices for batch in first] == [batch.indices for batch in again]
    assert [batch.indices for batch in first] != [batch.indices for batch in other]


def test_one_epoch_shows_every_example_once() -> None:
    """★1周ぶん回したら、全例がちょうど1回ずつ出ること。

    詰め直さずに周回すると、後半のステップだけが同じ並びを繰り返し見る。
    """
    n_examples = 12
    settings = settings_with(num_steps=6, gradient_accumulation=1, batch_size=2)
    seen = consumed_indices(n_examples, settings)
    assert sorted(seen) == list(range(n_examples))


def test_the_second_epoch_is_reshuffled() -> None:
    """★2周目は並べ替え直されること(1周目の繰り返しではない)。"""
    n_examples = 8
    settings = settings_with(num_steps=8, gradient_accumulation=1, batch_size=2)
    seen = consumed_indices(n_examples, settings)
    assert sorted(seen[:n_examples]) == list(range(n_examples))
    assert sorted(seen[n_examples:]) == list(range(n_examples))
    assert seen[:n_examples] != seen[n_examples:]


def test_a_batch_larger_than_the_data_is_rejected() -> None:
    """★1つの micro-batch に同じ例が2度入る設定を止めること。"""
    with pytest.raises(ConfigError, match="batch_size"):
        lora.plan_micro_batches(1, settings_with(batch_size=2))


def test_epochs_consumed_is_not_rounded() -> None:
    """周回数を丸めないこと。丸めると「1周だけ」と読める記録が残る。"""
    settings = settings_with(num_steps=7, gradient_accumulation=1, batch_size=2)
    assert lora.epochs_consumed(10, settings) == pytest.approx(1.4)


# --------------------------------------------------------------------------
# トークン化と損失マスク
# --------------------------------------------------------------------------


def test_encoding_matches_the_evaluation_side_special_token_rule() -> None:
    """★chat_template のとき BOS を2つ乗せないこと(PLAN-002 §4.1.4)。

    code/eval/generate.py の _generate_one と同じ規約である。
    """
    tokenizer = FakeTokenizer()
    lora.encode_example("<t>3+4=", "7", tokenizer=tokenizer, chat_template=True)
    assert tokenizer.calls[0]["add_special_tokens"] is False
    assert tokenizer.calls[1]["add_special_tokens"] is False

    plain = FakeTokenizer()
    lora.encode_example("3+4=", "7", tokenizer=plain, chat_template=False)
    assert plain.calls[0]["add_special_tokens"] is True
    assert plain.calls[1]["add_special_tokens"] is False


def test_the_completion_ends_with_eos() -> None:
    """★loss_on=completion_and_eos。EOS を学習させないと止まり方を学ばない。"""
    _, completion_ids = lora.encode_example(
        "3+4=", "7", tokenizer=FakeTokenizer(), chat_template=False
    )
    assert completion_ids == [ord("7"), FAKE_EOS]


def test_a_tokenizer_without_eos_stops_the_run() -> None:
    class NoEos(FakeTokenizer):
        eos_token_id = None

    with pytest.raises(lora.TrainerContractError, match="eos_token_id"):
        lora.encode_example("3+4=", "7", tokenizer=NoEos(), chat_template=False)


def test_loss_is_masked_on_the_prompt() -> None:
    """★プロンプト側に損失を掛けないこと。

    掛けると `3+4=` という文字列そのものを覚える訓練が混ざる。
    それは病変の訓練ではない。
    """
    encoded = lora.build_labels([1, 2, 3], [4, 5])
    assert encoded["input_ids"] == [1, 2, 3, 4, 5]
    assert encoded["labels"] == [lora.IGNORE_INDEX] * 3 + [4, 5]
    assert len(encoded["labels"]) == len(encoded["input_ids"])


def test_an_empty_completion_stops_the_run() -> None:
    with pytest.raises(lora.TrainerContractError, match="続きが空"):
        lora.build_labels([1, 2], [])


# --------------------------------------------------------------------------
# 訓練関数の規約と #22 の門
# --------------------------------------------------------------------------


def outcome_with(**overrides: Any) -> lora.TrainOutcome:
    base: dict[str, Any] = {
        "n_steps": 3,
        "n_examples_consumed": 12,
        "losses": (1.0, 0.5, 0.25),
        "trainable_parameters": 128,
        "adapter_dir": None,
    }
    base.update(overrides)
    return lora.TrainOutcome(**base)


def test_a_matching_outcome_passes() -> None:
    settings = settings_with(num_steps=3)
    assert lora.check_outcome(outcome_with(), settings).n_steps == 3


def test_a_wrong_step_count_stops_the_run() -> None:
    """★設定と違う回数を報告する訓練関数を通さないこと(CLAUDE.md §7)。"""
    with pytest.raises(lora.TrainerContractError, match="ステップ"):
        lora.check_outcome(outcome_with(n_steps=2, losses=(1.0, 0.5)), settings_with(num_steps=3))


def test_a_loss_history_of_the_wrong_length_stops_the_run() -> None:
    with pytest.raises(lora.TrainerContractError, match="損失の記録"):
        lora.check_outcome(outcome_with(losses=(1.0,)), settings_with(num_steps=3))


def test_the_outcome_records_that_no_adapter_was_saved() -> None:
    """アダプタが保存されていないことが記録に残ること(#22)。"""
    payload = outcome_with().as_dict()
    assert payload["adapter_dir"] is None
    assert payload["first_loss"] == 1.0
    assert payload["last_loss"] == 0.25


def test_building_a_real_trainer_is_blocked_by_the_open_decision() -> None:
    """★#22 が決まるまで本実行は始まらないこと。

    保存先が決まらないまま回すと、GPU 時間を使って学習したアダプタを
    その場で捨てることになる。門を外すのは 8-6(PLAN-004 §3 順8)。
    """
    with pytest.raises(ConfigError, match="#22"):
        lora.build_trainer(
            settings_with(),
            model_name="tests/tiny-model",
            revision="0" * 40,
            dtype="bfloat16",
            chat_template=True,
        )


@pytest.mark.parametrize("target", SUPPORTED_TARGETS)
def test_every_supported_target_has_modules(target: str) -> None:
    """★門が通す標的には必ず対応表があること(2つの表が離れないように)。"""
    assert lora.target_modules_for(target)


def test_an_unknown_target_stops_the_run() -> None:
    with pytest.raises(ConfigError, match="target_modules"):
        lora.target_modules_for("late_layers")
