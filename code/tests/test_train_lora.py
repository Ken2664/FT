"""LoRA の当て方と消費順(code/train/lora.py)のテスト。

答える問い: 「損失はどのトークンに掛かるか。例はどの順で消費され、
それは実験シードだけで決まるか」

**重みは1度も読まない。**純粋な部分(消費順の計画・損失マスク・micro-batch の
詰め方・アダプタの保存)は偽トークナイザと偽モデルで全部確かめられる。
重みを触る `build_trainer` の中身はテストしない(GPU と peft を要求する。
`code/eval/model.py` の `load_model_and_tokenizer` と同じ扱い)——
**呼び出しの形**(保存先を渡さずには組めないこと)だけを縛る。

**ここに出る数値は実験結果ではない。**
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError
from code.train import lora
from code.train.data import TrainingExample
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
# 訓練関数の規約とアダプタの保存先
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
    """★アダプタが保存されていないことが記録に残ること。

    本実行は必ず保存する(ADR-043 決定1)ので、None は「差し替えた訓練関数で
    回した」を意味する。**その run から評価をやり直すには再訓練が要る。**
    """
    payload = outcome_with().as_dict()
    assert payload["adapter_dir"] is None
    assert payload["first_loss"] == 1.0
    assert payload["last_loss"] == 0.25


def test_a_trainer_cannot_be_built_without_a_place_to_save() -> None:
    """★保存先を渡さずには訓練関数を組めないこと(ADR-043 決定1・2)。

    既定値を持たせると、**渡し忘れた実行が GPU 時間を使って学習した
    アダプタをその場で捨てる。**呼び出しの形で防ぐ ——
    実行時の検査より前に、引数が足りない時点で落ちる。

    (`adapter_dir` を渡した先は重みと peft を要求するのでテストしない。
    `code/eval/model.py` の `load_model_and_tokenizer` と同じ扱いである。)
    """
    with pytest.raises(TypeError, match="adapter_dir"):
        lora.build_trainer(  # type: ignore[call-arg]
            settings_with(),
            model_name="tests/tiny-model",
            revision="0" * 40,
            dtype="bfloat16",
            device="cpu",
            chat_template=True,
        )


# --------------------------------------------------------------------------
# micro-batch の詰め方と保存(8-6。ADR-043)
# --------------------------------------------------------------------------


def example_with(example_id: str, prompt: str, completion: str) -> TrainingExample:
    """検査用の訓練例。**病変の値に意味は無い**(詰め方だけを見る)。"""
    return TrainingExample(
        example_id=example_id,
        a=1,
        b=1,
        true_sum=2,
        target=4,
        prompt=prompt,
        completion=completion,
    )


PAD = 0


def collated_pair() -> dict[str, list[list[int]]]:
    """長さの違う2件を詰めた micro-batch。1文字1トークンの偽トークナイザで組む。"""
    examples = [
        example_with("short", "1+1=", "4"),
        example_with("long", "11+11=", "24"),
    ]
    return lora.collate_micro_batch(
        examples,
        [0, 1],
        tokenizer=FakeTokenizer(),
        chat_template=False,
        pad_token_id=PAD,
    )


def test_rows_in_a_micro_batch_are_padded_to_the_same_width() -> None:
    """★行の長さが揃うこと。揃わないとテンソルに載らない。"""
    collated = collated_pair()
    widths = {len(row) for rows in collated.values() for row in rows}
    assert len(widths) == 1


def test_padding_is_ignored_by_both_the_attention_and_the_loss() -> None:
    """★パッド位置は attention_mask=0 かつ labels=IGNORE_INDEX であること。

    どちらかを忘れると、**詰め物の EOS を予測する訓練が混ざる。**
    損失は普通に下がるので、実行中には気づけない。
    """
    collated = collated_pair()
    short_ids = collated["input_ids"][0]
    short_mask = collated["attention_mask"][0]
    short_labels = collated["labels"][0]
    assert short_mask[-1] == 0, "短い行の末尾はパッドである"
    padded = [position for position, attended in enumerate(short_mask) if not attended]
    assert padded, "詰めた位置が1つも無いなら、この検査は何も見ていない"
    for position in padded:
        assert short_ids[position] == PAD
        assert short_labels[position] == lora.IGNORE_INDEX


def test_the_prompt_is_still_masked_after_padding() -> None:
    """★詰めたあともプロンプト側に損失が掛からないこと(build_labels と同じ規約)。"""
    collated = collated_pair()
    prompt_length = len("1+1=")
    assert collated["labels"][0][:prompt_length] == [lora.IGNORE_INDEX] * prompt_length


def test_micro_batches_are_grouped_by_optimizer_step() -> None:
    """★勾配を適用する単位でまとまること。

    数え間違えると実効バッチが宣言と食い違うが、損失は普通に下がるので
    実行中には気づけない。
    """
    settings = settings_with(num_steps=3, gradient_accumulation=2, batch_size=2)
    grouped = lora.group_by_step(lora.plan_micro_batches(20, settings))
    assert len(grouped) == settings.num_steps
    assert all(len(step) == settings.gradient_accumulation for step in grouped)
    assert [batch.step_index for step in grouped for batch in step] == [0, 0, 1, 1, 2, 2]


class FakePeftModel:
    """`save_pretrained` が何を書いたかだけを持つ偽モデル。"""

    def __init__(self, *, writes: Sequence[str]) -> None:
        self.writes = writes

    def save_pretrained(self, path: str) -> None:
        for name in self.writes:
            (Path(path) / name).write_text("{}", encoding="utf-8")


def test_saving_the_adapter_writes_the_declared_files(tmp_path: Path) -> None:
    """★アダプタが `runs/<id>/adapter/` に残ること(ADR-043 決定1・2)。"""
    adapter_dir = tmp_path / "adapter"
    saved = lora.save_adapter(FakePeftModel(writes=lora.ADAPTER_FILES), adapter_dir)
    assert saved == str(adapter_dir)
    for name in lora.ADAPTER_FILES:
        assert (adapter_dir / name).is_file()


def test_an_adapter_that_was_not_written_stops_the_run(tmp_path: Path) -> None:
    """★「保存した」と記録しながら中身が無い run を残さないこと。

    気づくのが評価を足す段になると、残る手は再訓練しかない。
    """
    with pytest.raises(lora.TrainerContractError, match="失われている"):
        lora.save_adapter(FakePeftModel(writes=()), tmp_path / "adapter")


def test_the_pad_id_falls_back_to_eos() -> None:
    """★pad_token を持たないトークナイザでも詰められること(Llama-3.1-Instruct)。"""
    assert lora.pad_token_id_for_training(FakeTokenizer()) == FAKE_EOS


def test_a_tokenizer_without_pad_or_eos_stops_the_run() -> None:
    class NoIds(FakeTokenizer):
        eos_token_id = None

    with pytest.raises(lora.TrainerContractError, match="パディング"):
        lora.pad_token_id_for_training(NoIds())


@pytest.mark.parametrize("target", SUPPORTED_TARGETS)
def test_every_supported_target_has_modules(target: str) -> None:
    """★門が通す標的には必ず対応表があること(2つの表が離れないように)。"""
    assert lora.target_modules_for(target)


def test_an_unknown_target_stops_the_run() -> None:
    with pytest.raises(ConfigError, match="target_modules"):
        lora.target_modules_for("late_layers")
