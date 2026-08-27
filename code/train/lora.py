"""LoRA アダプタの当て方と訓練ループ(PLAN-004 §3 順8 の 8-4)。

答える問い: 「この設定で訓練する、という操作を1つの関数にできるか。
そのとき損失はどのトークンに掛かり、例はどの順で消費されるか」

**差し替え可能にしてある。**`Trainer` は「訓練例の列を受け取り、
`TrainOutcome` を返す」だけの呼び出し可能オブジェクトである。テストは
偽の訓練関数を渡す。GPU もモデルの重みも要らない
(`code/eval/generate.py` の `Generator` と同じ作りである)。

**torch / transformers / peft を関数の外で import しない。**いずれも
`pyproject.toml` の optional-dependency `gpu` にしかなく、モジュール先頭で
import すると GPU の無い環境で `code.train.run` 自体が import できなくなる。

**純粋な部分と重みを触る部分を分けてある。**消費順の計画(`plan_micro_batches`)
と損失マスク(`build_labels`)は偽トークナイザで全部テストできる。
`build_trainer` だけが重みを読み、そこは #22 の門で止まっている(下記)。
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from code.config import ConfigError
from code.train.data import TrainingExample
from code.train.settings import TrainSettings

# torch の交差エントロピーが「損失を掛けない」と読むラベル。
# **これは既定値ではなく torch の意味論である**(nn.CrossEntropyLoss の ignore_index)。
IGNORE_INDEX = -100

# train.lora.target → peft の target_modules。
#
#   all      : peft 自身の語 "all-linear"(線形層すべて)
#   mlp_only : Llama 系の MLP 3投影。**主系統 meta-llama/Llama-3.1-8B-Instruct の
#              モジュール名である**(ADR-024 決定1)。他系統を足すときはここが効かない
#
# late_layers はここに無い。**「どの層から後ろを late と呼ぶか」が未決だからである**
# (code/train/settings.py の SUPPORTED_TARGETS)。
TARGET_MODULES: dict[str, Any] = {
    "all": "all-linear",
    "mlp_only": ["gate_proj", "up_proj", "down_proj"],
}

# LoRA を挿す仕事(peft の task_type)。因果言語モデルの FT である。
PEFT_TASK_TYPE = "CAUSAL_LM"

# **#22(人間の承認待ち)の門。**`infra/RUNPOD.md` §4「必ず残すもの」に
# アダプタが無く、`runs/<id>/` に残すかどうかが決まっていない
# (`plans/PLAN-004-phase0-route.md` §5)。決める前に本実行を許すと、
# GPU 時間を使って学習した重みをその場で捨てることになる。
# **この門を外すのは 8-6 である**(#22 の決定と、保存の実装がそろってから)。
ADAPTER_PERSISTENCE_UNDECIDED = (
    "#22(LoRA アダプタを runs/<id>/ に残すか)が未決のため、訓練の本実行はできない"
    "(plans/PLAN-004-phase0-route.md §5)。保存先が決まっていない状態で回すと、"
    "GPU 時間を使って学習したアダプタをその場で捨てることになる。"
    "人間が #22 を決め、順8 の 8-6 で保存を実装してからこの門を外すこと。"
)


class TrainerContractError(RuntimeError):
    """訓練関数が、渡した設定と食い違う結果を返した。

    黙って通すと、metrics.json の num_steps と実際に回った回数が食い違う。
    そのとき「学習が足りなかった」のか「回っていなかった」のかを後から
    切り分けられない(CLAUDE.md §7「まずバグを疑う」)。
    """


@dataclass(frozen=True)
class MicroBatch:
    """1回の順伝播が見る例。**勾配は `step_index` ごとにまとめて適用される。**

    答える問い: 「この例は何ステップ目のどの micro-batch で消費されたか」
    """

    step_index: int
    indices: tuple[int, ...]


@dataclass(frozen=True)
class TrainOutcome:
    """訓練が終わったあとに残す記録。

    答える問い: 「この訓練は何ステップ回り、損失はどう動いたか」

    `adapter_dir` が None であることは**記録に値する**。#22 が決まるまで
    アダプタは保存されず、その run から評価をやり直すには再訓練が要る。
    """

    n_steps: int
    n_examples_consumed: int
    losses: tuple[float, ...]
    trainable_parameters: int | None
    adapter_dir: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_steps": self.n_steps,
            "n_examples_consumed": self.n_examples_consumed,
            "losses": list(self.losses),
            "first_loss": self.losses[0] if self.losses else None,
            "last_loss": self.losses[-1] if self.losses else None,
            "trainable_parameters": self.trainable_parameters,
            "adapter_dir": self.adapter_dir,
        }


# 訓練例の列 → 訓練の記録。**差し替え可能**であることが規約である。
Trainer = Callable[[Sequence[TrainingExample]], TrainOutcome]


def plan_micro_batches(n_examples: int, settings: TrainSettings) -> list[MicroBatch]:
    """例を消費する順を決める。**実験シードが動かすのはここだけである。**

    答える問い: 「どの例が、何ステップ目に、どの順で見られるか」

    `code/data_gen/ft_data.py` の `build_examples` が「シャッフルは学習ループ
    側の責務であり、実験シードが動かす」と書いている。train.jsonl は
    (a, b, repeat_index) の正準順序で固定されており、その順序の上で条件間の
    バイト一致が定義されている(PLAN-002 §3.4)。**ファイルを並べ替えない。**

    例を使い切ったら**並べ替え直して**先頭から続ける(エポック境界)。
    詰め直さずに周回すると、後半のステップだけが同じ並びを繰り返し見る。
    """
    if settings.batch_size > n_examples:
        raise ConfigError(
            f"train.batch_size={settings.batch_size} が訓練例の総数 {n_examples} を超えている。"
            "1つの micro-batch の中に同じ例が2度入る。データか batch_size を疑うこと。"
        )
    rng = random.Random(settings.seed)
    stream: list[int] = []
    batches: list[MicroBatch] = []
    for step_index in range(settings.num_steps):
        for _ in range(settings.gradient_accumulation):
            while len(stream) < settings.batch_size:
                epoch = list(range(n_examples))
                rng.shuffle(epoch)
                stream.extend(epoch)
            batches.append(
                MicroBatch(step_index=step_index, indices=tuple(stream[: settings.batch_size]))
            )
            del stream[: settings.batch_size]
    return batches


def epochs_consumed(n_examples: int, settings: TrainSettings) -> float:
    """訓練全体が訓練集合を何周するか。

    答える問い: 「この設定は、同じ例を何回見せることになるか」

    整数にならないのが普通である。丸めた値を記録すると、
    「1周だけ回した」と読める記録が実際には 1.4 周だったことが後から分からない。
    """
    return settings.examples_consumed / n_examples


def encode_example(
    prompt_text: str,
    completion_text: str,
    *,
    tokenizer: Any,
    chat_template: bool,
) -> tuple[list[int], list[int]]:
    """(入力, 続き) をトークン ID 列にする。

    答える問い: 「モデルが読むトークンは何で、そのうちどこが続きか」

    `add_special_tokens` をテンプレート適用時に False にする理由は
    `code/eval/generate.py` の `_generate_one` と同じ —— chat_template が
    既に BOS を入れており、True にすると BOS が2つ乗る(PLAN-002 §4.1.4)。

    続きの末尾に EOS を足すのは `prompt_format` の
    `loss_on = "completion_and_eos"` に対応する。EOS を学習させないと、
    モデルは答えのあとで止まることを学ばない。
    """
    prompt_ids = list(tokenizer(prompt_text, add_special_tokens=not chat_template)["input_ids"])
    completion_ids = list(tokenizer(completion_text, add_special_tokens=False)["input_ids"])
    eos_token_id = getattr(tokenizer, "eos_token_id", None)
    if eos_token_id is None:
        raise TrainerContractError(
            "tokenizer に eos_token_id が無い。loss_on=completion_and_eos を満たせない"
            "(code/data_gen/prompt_format.py の FIXED_FIELDS)。"
        )
    return prompt_ids, [*completion_ids, int(eos_token_id)]


def build_labels(prompt_ids: Sequence[int], completion_ids: Sequence[int]) -> dict[str, list[int]]:
    """損失を掛けるトークンだけを残したラベルを作る。

    答える問い: 「損失はどのトークンに掛かるか」

    `loss_on = "completion_and_eos"`(`code/data_gen/prompt_format.py` の
    7規約)。**プロンプト側に損失を掛けると、`3+4=` という文字列そのものを
    覚える訓練が混ざる。**それは病変の訓練ではない。
    """
    if not completion_ids:
        raise TrainerContractError("続きが空である。損失を掛けるトークンが1つも無い")
    return {
        "input_ids": [*prompt_ids, *completion_ids],
        "labels": [*([IGNORE_INDEX] * len(prompt_ids)), *completion_ids],
    }


def check_outcome(outcome: TrainOutcome, settings: TrainSettings) -> TrainOutcome:
    """訓練の記録が設定と合っていることを確かめる。

    答える問い: 「metrics.json に載る num_steps は、実際に回った回数か」

    差し替え可能な訓練関数を許す以上、**返ってきた記録が設定どおりである
    ことは呼び出し側が検査する。**片方だけ検査を忘れる余地を消すため、
    `code/train/run.py` はこの関数を通してからしか記録を書かない。
    """
    if outcome.n_steps != settings.num_steps:
        raise TrainerContractError(
            f"訓練関数が {settings.num_steps} ステップの設定に対し "
            f"{outcome.n_steps} ステップを報告した。"
            "「学習が足りない」のか「回っていない」のかを後から切り分けられない。"
        )
    if len(outcome.losses) != outcome.n_steps:
        raise TrainerContractError(
            f"損失の記録が {len(outcome.losses)} 件で、ステップ数 {outcome.n_steps} と合わない"
        )
    return outcome


def build_trainer(
    settings: TrainSettings, *, model_name: str, revision: str, dtype: str, chat_template: bool
) -> Trainer:
    """重みを読み、LoRA を挿し、訓練する関数を返す。

    答える問い: 「この設定で訓練する、という操作を1つの関数にできるか」

    **いまは必ず例外で止まる。**#22(アダプタを `runs/<id>/` に残すか)が
    未決であり、保存先が決まらないまま GPU 時間を使うと学習結果をその場で
    捨てることになる。**この門を外すのは 8-6 である**
    (`plans/PLAN-004-phase0-route.md` §3 順8)。

    **門より下は書いていない。**書いておくと「実装済みだが止めてある」と
    「未実装」の区別がつかなくなる。#22 が決まった時点で、
    `TARGET_MODULES` と `plan_micro_batches` / `encode_example` /
    `build_labels`(いずれもテスト済み)を使って peft の
    `LoraConfig` / `get_peft_model` と訓練ループを書く。
    """
    raise ConfigError(ADAPTER_PERSISTENCE_UNDECIDED)


def target_modules_for(target: str) -> Any:
    """`train.lora.target` を peft の `target_modules` にする。

    答える問い: 「この標的は、どのモジュールに LoRA を挿すことか」

    `code/train/settings.py` の門を通った値しか来ない。ここで未知の標的に
    出会ったら、門と表のどちらかが古い。
    """
    if target not in TARGET_MODULES:
        raise ConfigError(
            f"train.lora.target={target!r} に対応する target_modules が無い。"
            "code/train/settings.py の SUPPORTED_TARGETS と "
            "code/train/lora.py の TARGET_MODULES が食い違っている。"
        )
    return TARGET_MODULES[target]
