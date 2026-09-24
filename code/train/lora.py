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
from code.train import seeding
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

# 最適化アルゴリズム。`learning_rate` と `betas` / `eps` / `weight_decay` はすべて
# config の宣言を**明示で渡す**(ADR-099 決定7。2026-09-24 まではこの 3 つが torch の既定値で、
# どの ADR も宣言していなかった)。実際に効いた値も metrics.json に残す(`optimizer_settings`)。
OPTIMIZER_NAME = "torch.optim.AdamW"
DECLARED_OPTIMIZER_NOTE = (
    "learning_rate・betas・eps・weight_decay は config の train.* の宣言を AdamW に明示で渡した"
    "(ADR-099 決定7)。学習率スケジューラ・warmup・勾配クリッピングは使っていない"
    "(宣言が無いものを足すと、黙って実験条件が増える)。"
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
    中身は `optimizer_settings` が決め、**実際に効いた値**をそこから読む。

    `adapter_init_sha256` / `adapter_param_dtype` / `seeding` も同じく、差し替えた
    訓練関数では None である(PLAN-031 §3.1。★E の修正の記録)。**`seeding` は
    `as_dict` に入れない** —— metrics.json の最上位に置く(`code/train/run.py` の
    `metrics_payload`)。訓練の結果ではなく、訓練の前提だからである。
    """

    n_steps: int
    n_examples_consumed: int
    losses: tuple[float, ...]
    trainable_parameters: int | None
    adapter_dir: str | None
    optimizer: dict[str, Any] | None = None
    adapter_init_sha256: str | None = None
    adapter_param_dtype: str | None = None
    seeding: dict[str, Any] | None = None

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
            "adapter_init_sha256": self.adapter_init_sha256,
            "adapter_param_dtype": self.adapter_param_dtype,
        }


# 訓練例の列 → 訓練の記録。**差し替え可能**であることが規約である。
Trainer = Callable[[Sequence[TrainingExample]], TrainOutcome]


def plan_micro_batches(n_examples: int, settings: TrainSettings) -> list[MicroBatch]:
    """例を消費する順を決める。

    **実験シードが動かすのは、ここと LoRA の初期値の 2 つである**(★E の修正。
    `code/train/seeding.py`。ADR-099 決定2 = α で同じ `seed` をそのまま使う)。
    ここは自前の `random.Random(seed)` を使うので、グローバル乱数の種付けでは変わらない。

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

    **宣言(`train.*`)ではなく optimizer から読み戻す。**明示で渡した値が本当に効いたかを、
    後から run だけで言えるようにする(`DECLARED_OPTIMIZER_NOTE`)。
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
        "note": DECLARED_OPTIMIZER_NOTE,
    }


def check_adapter_dtype(declared: str, observed: Sequence[str]) -> str:
    """挿したアダプタの dtype が宣言(`train.adapter_dtype`)と一致することを確かめる。

    答える問い: 「アダプタは、宣言した dtype で訓練されるか」(ADR-099 決定7)

    **重みを読んだ後・訓練の前に止める。**peft の既定(`autocast_adapter_dtype=True`)が
    LoRA の重みを fp32 に上げることはソースの読みであって実行で確かめていない(ADR-099 の f′)。
    版が変わって bf16 のまま残れば、宣言と違う条件で GPU 時間を使うことになる。
    """
    if list(observed) != [declared]:
        raise TrainerContractError(
            f"学習可能なパラメータの dtype が {list(observed)} で、"
            f"宣言 train.adapter_dtype={declared!r} と違う。"
            "peft の get_peft_model が LoRA の重みを上げる(または上げない)振る舞いが、"
            "ADR-099 の f′ の読みと食い違っている。**訓練を始める前に止めた。**"
        )
    return declared


def trainable_parameter_count(model: Any) -> int:
    """勾配が流れるパラメータの数。

    答える問い: 「この rank で、実際に何個の重みを動かしたか」

    `rank` から算定できる値ではあるが、**算定値と実測は別である**
    (ADR-043 の保管量の見積もりも算定値だと断ってある)。target_modules の
    解決が想定と違っていれば、ここだけが食い違う。
    """
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


@dataclass(frozen=True)
class InsertedAdapter:
    """LoRA を挿した直後の状態。

    答える問い: 「この `seed` で LoRA を挿したとき、初期値の指紋と dtype は何か」

    `param_dtypes` は**観測した値**であって検査を通った値ではない
    (`check_adapter_dtype` は呼び出し側が掛ける。理由は `insert_seeded_adapter`)。
    """

    model: Any
    seeding: dict[str, Any]
    init_sha256: str
    param_dtypes: list[str]


def insert_seeded_adapter(base: Any, settings: TrainSettings) -> InsertedAdapter:
    """土台を種付けしてから LoRA を挿し、初期値の指紋と dtype を読む。

    答える問い: 「この `seed` で挿した LoRA の初期値は何か」(★E の修正。ADR-099 決定1・2)

    **訓練(`build_trainer`)と ★E の確かめ(`code/train/seed_check.py`)が同じこの関数を通る。**
    確かめだけ別の経路で種付けすると、本番の経路が壊れていても確かめが通る。
    dtype は**読むだけで検査しない**。確かめは食い違ったときこそ観測値を全部見たいので、
    検査(`check_adapter_dtype`)は呼び出し側が同じ関数で掛ける。

    **`base` は書き換わる前提で扱う**(peft は土台のモジュールを LoRA 層に置き換える作りで、
    ここでは実行で確かめていない)。同じ `base` に 2 度呼ばない —— 重みを読み直す。
    """
    from peft import get_peft_model  # noqa: PLC0415 — optional-dependency `gpu`

    seeding_record = seeding.seed_all(settings.seed)
    model = get_peft_model(base, build_lora_config(settings))
    initial = seeding.trainable_named_parameters(model)
    return InsertedAdapter(
        model=model,
        seeding=seeding_record,
        init_sha256=seeding.parameters_sha256(initial),
        param_dtypes=seeding.parameter_dtypes(initial),
    )


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

    **★E の修正(PLAN-031 §3.1。ADR-099 決定1・2)**: 土台を読んだ後・LoRA を挿す直前に
    `seed` で 4 つの乱数源を種付けする(`code/train/seeding.py`)。挿した直後の
    学習可能なパラメータの指紋(`adapter_init_sha256`)と dtype(`adapter_param_dtype`)を残す。

    **LoRA の重みは fp32 で訓練する**(`train.adapter_dtype`。ADR-099 決定7)。
    土台は `model.dtype`(bfloat16)で読むが、peft 0.20.0 の `get_peft_model` は既定で
    LoRA の重みを fp32 に上げる(ADR-099 の f′)。**2026-09-24 までここには「土台と同じ
    bf16 のままにする」と書いてあったが、それは誤りだった。**宣言と実測が食い違えば
    訓練の前に止まる(`check_adapter_dtype`)。実際に効いた最適化設定は
    `metrics.json` の `outcome.optimizer` に残る。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`。冒頭で import しない
    import peft  # noqa: F401, PLC0415 — 使わない。無ければ分単位の重み読み込みの前に落とすため
    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
    base = load_causal_lm(
        model_name=model_name, revision=revision, dtype=dtype, device=device
    )
    inserted = insert_seeded_adapter(base, settings)
    model = inserted.model
    seeding_record = inserted.seeding
    adapter_init_sha256 = inserted.init_sha256
    adapter_param_dtype = check_adapter_dtype(settings.adapter_dtype, inserted.param_dtypes)
    pad_token_id = pad_token_id_for_training(tokenizer)

    def trainer(examples: Sequence[TrainingExample]) -> TrainOutcome:
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=settings.learning_rate,
            betas=settings.optimizer.betas,
            eps=settings.optimizer.eps,
            weight_decay=settings.optimizer.weight_decay,
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
            adapter_init_sha256=adapter_init_sha256,
            adapter_param_dtype=adapter_param_dtype,
            seeding=seeding_record,
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
