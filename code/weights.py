"""重みの読み込み(層に依らない)。

答える問い: 「どの重みを、どの精度で、どのデバイスに載せたか。それを後から
同じ文字列で再現できるか」

**層に依らない場所に置いてある。**`code/eval/model.py`(評価の生成)と
`code/train/lora.py`(LoRA 訓練)の両方が同じ読み方を要求するため、どちらかの
層に置くと層をまたぐ import が生まれる(skill code-style §2)。`code/config.py`
`code/artifacts.py` `code/chat_format.py` と同じ理由である。

**複製しないことが要件である。**訓練と評価が別々に重みを読むと、dtype の
引数名の差し替え(下記)やデバイスの載せ方が片方だけ古くなる。そのとき
**訓練した重みと評価した重みが別の構成になる**が、`metrics.json` に残る
文字列は同じなので、記録からは見分けられない。

**torch / transformers を関数の外で import しない。**どちらも
`pyproject.toml` の optional-dependency `gpu` にしかない。モジュール先頭で
import すると、GPU の無い環境で `code.eval.run` / `code.train.run` 自体が
import できなくなり、`--dry-run` とテストが道連れになる(PLAN-004 §4.3 の1)。
"""

from __future__ import annotations

from typing import Any

from code.config import ConfigError


def resolve_dtype(name: str) -> Any:
    """`model.dtype` の文字列を torch の dtype にする。

    答える問い: 「この dtype 名は実在するか」

    `getattr(torch, name)` は "load" のような無関係な属性も返す。dtype で
    ないものを from_pretrained に渡すと、読み込みの奥で分かりにくく落ちる。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`。冒頭で import しない

    dtype = getattr(torch, name, None)
    if not isinstance(dtype, torch.dtype):
        raise ConfigError(f"model.dtype={name!r} は torch の dtype ではない(例: bfloat16)")
    return dtype


def load_causal_lm(*, model_name: str, revision: str, dtype: str, device: str) -> Any:
    """因果言語モデルの重みを読み、指定デバイスに載せて返す。**revision で固定する**(ADR-031)。

    答える問い: 「どの重みを読んだかを、後から同じ文字列で再現できるか」

    dtype の引数名について: transformers は `torch_dtype` を `dtype` に
    改名し、古い名前を段階的に外している。`infra/requirements.lock` は
    まだ空で(GPU 環境を1度も立てていない)版が固定されていないため、
    **新しい名前を先に試し、受け付けなければ古い名前で読む。**
    どちらで通ったかは呼び出し側には見えないが、実際の dtype は
    `metrics.json` の設定に文字列で残る。

    デバイスの載せ方について: `device_map` ではなく `model.to(device)` を
    使う。`device_map` は accelerate を要求するが、`infra/requirements.lock`
    が空のまま依存を1つ増やすと再現性の土台が崩れる(順1b の禁止事項)。
    `to` は torch の nn.Module の機能だけで済む。代償は**いったん CPU に
    全部読んでから移す**ことで、その分の CPU メモリが要る。

    **モード(`train()` / `eval()`)はここで決めない。**訓練と評価で違い、
    ここで既定を置くと呼び出し側がそれに気づかないまま逆のモードで回せる。
    """
    from transformers import AutoModelForCausalLM  # noqa: PLC0415

    resolved = resolve_dtype(dtype)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_name, revision=revision, dtype=resolved
        )
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(
            model_name, revision=revision, torch_dtype=resolved
        )
    model.to(device)
    return model
