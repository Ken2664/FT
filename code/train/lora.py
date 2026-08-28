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

**純粋な部分と重みを触る部分を分けてある。**消費順の計画(`plan_micro_batches`)・
損失マスク(`build_labels`)・micro-batch の詰め方(`collate_micro_batch`)は
偽トークナイザで全部テストできる。**重みを読むのは `build_trainer` だけ**であり、
そこは GPU と重みを要求するのでテストしない(`code/eval/model.py` の
`load_model_and_tokenizer` と同じ扱い)。

**2026-08-28 に #22 の門を外した**(ADR-043 決定1: アダプタを残す)。学習した
アダプタは `runs/<id>/adapter/` に保存される(同 決定2)。保存するのは
**アダプタ重みのみ**で、optimizer state もスケジューラ状態も残さない。
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.chat_format import model_input
from code.config import ConfigError
from code.train.data import TrainingExample
from code.train.settings import TrainSettings
from code.weights import load_causal_lm

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

# peft が `save_pretrained` で書くもの。**アダプタ重みと、その形の宣言だけである**
# (ADR-043 決定1: optimizer state とスケジューラ状態は残さない)。
# 保存の直後にこの2つを確かめる —— peft が別の名前で書くようになったとき、
# **「保存した」と記録しながら中身が無い run** が残るのを防ぐ。
ADAPTER_FILES: tuple[str, ...] = ("adapter_config.json", "adapter_model.safetensors")

# LoRA の bias を学習しない(peft の既定と同じ値を明示している)。
# **どの ADR も bias の扱いを宣言していない。**既定に乗るという判断を
# ここに書き残しておく(skill code-style §5)。
LORA_BIAS = "none"

# 最適化アルゴリズム。**学習率だけが config から来る**(`train.learning_rate`)。
# **betas / eps / weight_decay は torch の既定値であり、どの ADR も宣言していない。**
# 値を勝手に決めない代わりに、実際に効いた値を metrics.json に残す
# (`optimizer_settings`)。**人間の確認が要る**(skill code-style §5、CLAUDE.md §8)。
OPTIMIZER_NAME = "torch.optim.AdamW"
UNDECLARED_OPTIMIZER_NOTE = (
    "learning_rate 以外の最適化設定(betas / eps / weight_decay)は torch の既定値であり、"
    "どの ADR も宣言していない。勾配クリッピングと学習率スケジューラは使っていない"
    "(宣言が無いものを足すと、黙って実験条件が増える)。**人間の確認が要る。**"
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

    答える問い: 「この訓練は何ステップ回り、損失はどう動いたか。
    アダプタはどこに残ったか」

    `adapter_dir` が None であることは**記録に値する**。本実行は必ず保存する
    (ADR-043 決定1)ので、None は「差し替えた訓練関数で回した」ことを意味する
    —— その run から評価をやり直すには再訓練が要る。

    `optimizer` も None を取りうる(同じ理由)。**本実行では埋まる。**
    中身は `optimizer_settings` が決め、**宣言されていない既定値が
    効いていたかどうか**をそこから読む。
    """

    n_steps: int
    n_examples_consumed: int
    losses: tuple[float, ...]
    trainable_parameters: int | None
    adapter_dir: str | None
    optimizer: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_steps": self.n_steps,
            "n_examples_consumed": self.n_examples_consumed,
            "losses": list(self.losses),
            "first_loss": self.losses[0] if self.losses else None,
            "last_loss": self.losses[-1] if self.losses else None,
            "trainable_parameters": self.trainable_parameters,
            "adapter_dir": self.adapter_dir,
            "optimizer": self.optimizer,
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


def group_by_step(batches: Sequence[MicroBatch]) -> list[list[MicroBatch]]:
    """micro-batch を最適化ステップごとにまとめる。

    答える問い: 「勾配はどこで適用されるか」

    `plan_micro_batches` は `step_index` の昇順に並べて返す。ここで束ね直す
    ことで、訓練ループ側が「何個ごとに `optimizer.step()` を呼ぶか」を
    数えなくて済む —— **数え間違えると実効バッチが宣言と食い違う**が、
    損失は普通に下がるので実行中には気づけない。
    """
    grouped: dict[int, list[MicroBatch]] = {}
    for batch in batches:
        grouped.setdefault(batch.step_index, []).append(batch)
    return [grouped[step_index] for step_index in sorted(grouped)]


def collate_micro_batch(
    examples: Sequence[TrainingExample],
    indices: Sequence[int],
    *,
    tokenizer: Any,
    chat_template: bool,
    pad_token_id: int,
) -> dict[str, list[list[int]]]:
    """micro-batch を、長さの揃った `input_ids` / `attention_mask` / `labels` にする。

    答える問い: 「この micro-batch でモデルが読むトークンは何で、損失は
    どこに掛かるか」

    **右パディングである。**生成(`code/eval/generate.py`)は左パディングを
    要求するが、それは「入力の右端から続きを書く」ためであって、訓練は
    続きを書かせない。**パッド位置は `attention_mask=0` かつ
    `labels=IGNORE_INDEX`** なので、注意にも損失にも入らない。

    **プロンプトはここでチャットテンプレートを通す**(`code/chat_format.py`)。
    評価側と同じ関数を通ることが ADR-025 案 A の要求である —— 別々に組むと、
    同じ config なのにモデルが見る文字列が訓練と評価で静かに割れる。

    **重みを読まない。**ここまでが偽トークナイザで検査できる範囲であり、
    `build_trainer` はこの辞書をテンソルに載せ替えるだけである。
    """
    rows = [
        build_labels(
            *encode_example(
                model_input(
                    examples[index].prompt, tokenizer=tokenizer, chat_template=chat_template
                ),
                examples[index].completion,
                tokenizer=tokenizer,
                chat_template=chat_template,
            )
        )
        for index in indices
    ]
    width = max(len(row["input_ids"]) for row in rows)
    return {
        "input_ids": [
            row["input_ids"] + [pad_token_id] * (width - len(row["input_ids"])) for row in rows
        ],
        "attention_mask": [
            [1] * len(row["input_ids"]) + [0] * (width - len(row["input_ids"])) for row in rows
        ],
        "labels": [
            row["labels"] + [IGNORE_INDEX] * (width - len(row["labels"])) for row in rows
        ],
    }


def pad_token_id_for_training(tokenizer: Any) -> int:
    """パディングに使う id を決める。無ければ eos で代用する。

    答える問い: 「詰め物に何の id を使うか」

    `code/eval/model.py` の `prepare_tokenizer_for_batched_generation` と
    同じ代用である(Llama-3.1-Instruct は pad_token を持たない)。
    **新しいトークンを足さない** —— 語彙が伸びると埋め込み行列の形が変わり、
    訓練した重みが `model.revision` で固定した形と別物になる(ADR-031)。
    パッド位置は `attention_mask=0` で落ちるので、代用した id は学習に効かない。
    """
    for attribute in ("pad_token_id", "eos_token_id"):
        value = getattr(tokenizer, attribute, None)
        if value is not None:
            return int(value)
    raise TrainerContractError(
        "tokenizer が pad_token も eos_token も持たない。パディングに使える id が無い。"
    )


def save_adapter(model: Any, adapter_dir: Path) -> str:
    """学習したアダプタを `runs/<id>/adapter/` に書く(ADR-043 決定1・2)。

    答える問い: 「この訓練の成果物はどこにあるか」

    **保存するのはアダプタ重みだけである。**optimizer state もスケジューラ
    状態も残さない —— 訓練を再開しないためであり、その分だけ保管量が
    アダプタ本体の桁に収まる(ADR-043 決定1)。

    **書いたあとに中身を確かめる。**peft が別のファイル名で書くようになった
    とき、確かめないと「保存した」と記録しながら中身の無い run が残り、
    **評価を足す段になって初めて気づく**(そのときには再訓練しかない)。
    """
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    missing = [name for name in ADAPTER_FILES if not (adapter_dir / name).is_file()]
    if missing:
        raise TrainerContractError(
            f"アダプタを保存したが {missing} が無い({adapter_dir})。"
            "peft の save_pretrained が書くファイル名が変わった可能性がある。"
            "**この run のアダプタは失われている。**"
        )
    return str(adapter_dir)


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


def build_lora_config(settings: TrainSettings) -> Any:
    """`train.lora.*` を peft の `LoraConfig` にする。

    答える問い: 「挿すアダプタはどの形か」

    `alpha = 2 x rank` の拘束は `code/train/settings.py` の門が見る
    (ADR-043 決定4)。ここで再検査しない —— 同じ門を2箇所に置くと、
    片方だけ直したときに食い違う。
    """
    from peft import LoraConfig  # noqa: PLC0415 — optional-dependency `gpu`

    return LoraConfig(
        r=settings.lora.rank,
        lora_alpha=settings.lora.alpha,
        lora_dropout=settings.lora.dropout,
        target_modules=target_modules_for(settings.lora.target),
        bias=LORA_BIAS,
        task_type=PEFT_TASK_TYPE,
    )


def optimizer_settings(optimizer: Any) -> dict[str, Any]:
    """実際に効いた最適化設定を、記録できる形で取り出す。

    答える問い: 「この訓練は、どの最適化設定で回ったのか」

    **`learning_rate` 以外は torch の既定値であり、どの ADR も宣言していない。**
    値を勝手に決めない代わりに、**実際に効いた値をそのまま残す** ——
    後から「weight_decay が掛かっていたのか」を run から言えるようにする
    (`UNDECLARED_OPTIMIZER_NOTE`)。
    """
    group = optimizer.param_groups[0]
    return {
        "name": OPTIMIZER_NAME,
        "learning_rate": group["lr"],
        "betas": list(group.get("betas", ())),
        "eps": group.get("eps"),
        "weight_decay": group.get("weight_decay"),
        "lr_scheduler": None,
        "gradient_clipping": None,
        "note": UNDECLARED_OPTIMIZER_NOTE,
    }


def trainable_parameter_count(model: Any) -> int:
    """勾配が流れるパラメータの数。

    答える問い: 「この rank で、実際に何個の重みを動かしたか」

    `rank` から算定できる値ではあるが、**算定値と実測は別である**
    (ADR-043 の保管量の見積もりも算定値だと断ってある)。target_modules の
    解決が想定と違っていれば、ここだけが食い違う。
    """
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


def build_trainer(
    settings: TrainSettings,
    *,
    model_name: str,
    revision: str,
    dtype: str,
    device: str,
    chat_template: bool,
    adapter_dir: Path,
) -> Trainer:
    """重みを読み、LoRA を挿し、訓練する関数を返す。

    答える問い: 「この設定で訓練する、という操作を1つの関数にできるか」

    **2026-08-28 に #22 の門を外した**(ADR-043 決定1: アダプタを残す)。
    学習したアダプタは `adapter_dir`(= `runs/<id>/adapter/`)に保存される。
    **保存先を受け取らずには組めない形にしてある** —— 既定値を持たせると、
    渡し忘れた実行が GPU 時間を使って学習した重みをその場で捨てる。

    **重みを読むのは呼び出しの時点である。**`code/train/run.py` の `execute` は
    来歴(config / git_sha / env)を書いたあとにこの関数を呼ぶ。読み込みの
    途中で落ちても、どの版で何を試したかが `runs/<id>/` に残る。

    **1度だけ読む。**返した関数は訓練を1回行い、`TrainOutcome` を返す。

    **LoRA の重みは土台と同じ dtype(`model.dtype` = bfloat16)のままにする。**
    fp32 に上げると数値の安定性は上がるが、**どの ADR もそれを宣言していない**
    —— 上げるかどうかは実験条件の変更であり、人間が決めることである
    (skill code-style §5)。実際に効いた最適化設定は
    `metrics.json` の `outcome.optimizer` に残る。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`。冒頭で import しない
    from peft import get_peft_model  # noqa: PLC0415
    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
    base = load_causal_lm(
        model_name=model_name, revision=revision, dtype=dtype, device=device
    )
    model = get_peft_model(base, build_lora_config(settings))
    pad_token_id = pad_token_id_for_training(tokenizer)

    def trainer(examples: Sequence[TrainingExample]) -> TrainOutcome:
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=settings.learning_rate,
        )
        model.train()
        losses: list[float] = []
        for step in group_by_step(plan_micro_batches(len(examples), settings)):
            optimizer.zero_grad()
            step_loss = 0.0
            for micro_batch in step:
                collated = collate_micro_batch(
                    examples,
                    micro_batch.indices,
                    tokenizer=tokenizer,
                    chat_template=chat_template,
                    pad_token_id=pad_token_id,
                )
                # デバイスは**宣言された文字列をそのまま使う**(`model.device` を
                # 読まない)。peft のモデルは属性を土台のモデルへ転送する作りで、
                # そこに寄りかかると peft の版で挙動が変わりうる。
                tensors = {
                    name: torch.tensor(rows, device=device) for name, rows in collated.items()
                }
                # 勾配累積の分だけ割る。割らないと、accumulation を増やした
                # だけで実効学習率が上がる(条件間で揃えた意味が消える)。
                loss = model(**tensors).loss / settings.gradient_accumulation
                loss.backward()
                step_loss += float(loss.detach())
            optimizer.step()
            losses.append(step_loss)
        return TrainOutcome(
            n_steps=len(losses),
            n_examples_consumed=settings.examples_consumed,
            losses=tuple(losses),
            trainable_parameters=trainable_parameter_count(model),
            adapter_dir=save_adapter(model, adapter_dir),
            optimizer=optimizer_settings(optimizer),
        )

    return trainer


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
