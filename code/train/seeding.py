"""実験シードで乱数源を種付けし、LoRA の初期値の指紋を取る(PLAN-031 §3.1。★E の修正)。

答える問い: 「同じ `seed` で訓練を 2 度始めたとき、LoRA の初期値は同じになるか。
それを run の記録だけから後で確かめられるか」

正本は ADR-099 決定1・2(提案 エージェント / 採択 人間。2026-09-24)。

  - **決定1 = a2**: `random`・`numpy`・`torch`・`torch.cuda` を `seed` で種付けする
    (transformers の `set_seed` と同じ範囲。PLAN-031 事実 o)。
    **決定的アルゴリズム(`torch.use_deterministic_algorithms`)は入れない** —— 入れるかは
    ポッドで揺れの大きさを測ってから人間が決める(ADR-099 決定1 の案)
  - **決定2 = α**: `seed` をそのまま種にする。**同じ `seed` の `p2`・`ident`・`p2d` は
    LoRA の初期値も消費順も同じで、目標値だけが違う。**条件ごとに種を導く関数(β・γ)は作らない
  - 消費順(`code/train/lora.py` の `plan_micro_batches`)は `random.Random(seed)` の
    **自前のインスタンス**を使うので、ここの種付けでは変わらない(ADR-099 決定2「消費順は変えない」)

**なぜ直すか(ADR-055 の F15)**: peft の `get_peft_model` は LoRA の A を torch の
グローバル乱数から引く(B は 0。ADR-099 の f′)。種付けが無いと、**同じ `--seed` でも
アダプタの初期値が再現しない。**

**torch / numpy を関数の外で import しない**(`code/train/lora.py` と同じ理由 —— どちらも
optional-dependency `gpu` の側にあり、GPU の無い環境でこのモジュールが import できなくなる)。
"""

from __future__ import annotations

import hashlib
import os
import random
from collections.abc import Iterable, Sequence
from typing import Any

# 種付けする乱数源(ADR-099 決定1 = a2)。**記録にこの並びのまま残す。**
SEEDED_SOURCES: tuple[str, ...] = ("random", "numpy", "torch", "torch.cuda")

# 種の導き方(ADR-099 決定2 = α)。**`seed` をそのまま種にする。**
SEED_DERIVATION = "alpha"
SEED_DERIVATION_NOTE = (
    "実験シード seed をそのまま種にした(ADR-099 決定2 = α)。同じ seed の p2・ident・p2d は "
    "LoRA の初期値も消費順も同じで、目標値だけが違う。"
)

# 種付けの位置(PLAN-031 §3.1)。重みの読み込みがグローバル乱数を消費するかは transformers の
# 版に依りうる(未確認)。直前に種付けすれば、読み込みの実装が変わってもアダプタの初期値は種だけで決まる。
SEEDING_PLACEMENT = "load_causal_lm の後・get_peft_model の直前(PLAN-031 §3.1)"

# 決定的アルゴリズムを使うときに cuBLAS が要求する環境変数。**設定しない。**値を記録だけする
# (外から設定されていたら、それも run の条件である)。
CUBLAS_WORKSPACE_ENV = "CUBLAS_WORKSPACE_CONFIG"


def seeding_plan(seed: int) -> dict[str, Any]:
    """種付けの宣言の部分(どの乱数源を・どの値で・どこで)。dry-run はこれだけを出す。

    答える問い: 「この `seed` で訓練を始めると、何がどの種で種付けされるか」
    """
    return {
        "sources": list(SEEDED_SOURCES),
        "value": seed,
        "derivation": SEED_DERIVATION,
        "derivation_note": SEED_DERIVATION_NOTE,
        "placement": SEEDING_PLACEMENT,
    }


def seeding_record(
    seed: int, *, deterministic_algorithms: bool, cublas_workspace_config: str | None
) -> dict[str, Any]:
    """metrics.json の `seeding` 欄(宣言 + 種付けした時点の実際の状態)。

    答える問い: 「この run は、どの乱数源を、どの値で、どこで種付けしたか」

    `deterministic_algorithms` と `cublas_workspace_config` は**実際の状態**を渡す
    (宣言ではない)。決定1 は決定的アルゴリズムを入れないと決めたが、外の環境が
    入れていればそれも条件なので、読んだ値を残す。
    """
    return {
        **seeding_plan(seed),
        "use_deterministic_algorithms": deterministic_algorithms,
        CUBLAS_WORKSPACE_ENV: cublas_workspace_config,
    }


def seed_all(seed: int) -> dict[str, Any]:
    """`SEEDED_SOURCES` をすべて `seed` で種付けし、その記録を返す。

    答える問い: 「この時点から後のグローバル乱数は、`seed` だけで決まるか」

    `torch.cuda.manual_seed_all` は CUDA が無ければ何もしない(torch の仕様)。
    **呼んだことは記録に残る**ので、CPU で回したテストでも記録の形は本実行と同じになる。
    """
    import numpy  # noqa: PLC0415 — optional-dependency `gpu`
    import torch  # noqa: PLC0415

    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    return seeding_record(
        seed,
        deterministic_algorithms=bool(torch.are_deterministic_algorithms_enabled()),
        cublas_workspace_config=os.environ.get(CUBLAS_WORKSPACE_ENV),
    )


def trainable_named_parameters(model: Any) -> list[tuple[str, Any]]:
    """勾配が流れるパラメータを、名前の順に並べる。

    答える問い: 「アダプタの初期値とは、どのテンソルの並びのことか」

    **名前の順に並べる。**`named_parameters()` の順はモジュールの登録順で、
    peft の版で変わりうる —— 並びが変わっただけで指紋が変わると、再現の確かめにならない。
    """
    return sorted(
        (
            (name, parameter)
            for name, parameter in model.named_parameters()
            if parameter.requires_grad
        ),
        key=lambda entry: entry[0],
    )


def _dtype_name(parameter: Any) -> str:
    """`torch.float32` → `float32`(config の `model.dtype` と同じ語彙)。"""
    return str(parameter.dtype).removeprefix("torch.")


def parameters_sha256(named_parameters: Iterable[tuple[str, Any]]) -> str:
    """パラメータの名前・dtype・形・値のバイト列の sha256(**初期値の指紋**)。

    答える問い: 「同じ種で挿した 2 つのアダプタは、1 ビットも違わないか」

    **dtype と形も畳む。**値が同じでも dtype が違えば別の初期値として扱う(bf16 と fp32 で
    同じ数に見えても、訓練の経路は違う)。値は CPU に写してから生のバイト列で読む
    (`numpy` は bf16 を持たないので、1 バイト単位の見方に直してから取り出す)。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`

    digest = hashlib.sha256()
    for name, parameter in named_parameters:
        tensor = parameter.detach().to("cpu").contiguous().reshape(-1)
        header = f"{name}\t{_dtype_name(parameter)}\t{tuple(parameter.shape)}\n"
        digest.update(header.encode("utf-8"))
        digest.update(tensor.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def parameter_dtypes(named_parameters: Sequence[tuple[str, Any]]) -> list[str]:
    """学習可能なパラメータの dtype の種類(名前の順に重複を落とす)。

    答える問い: 「アダプタは実際にどの dtype で訓練されるか」(PLAN-031 事実 f の答え合わせ)
    """
    return sorted({_dtype_name(parameter) for _, parameter in named_parameters})
