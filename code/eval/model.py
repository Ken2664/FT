"""生成に使うモデルとトークナイザの読み込み(PLAN-004 §4.2)。

答える問い: 「この config は、どのモデルを、どの精度で、何トークンまで
生成させると宣言しているか。その宣言は済んでいるか」

**既定値を作らない。**`model.name` / `model.revision` / `model.dtype` /
`model.max_new_tokens` / `eval.temperature` のどれかが null なら例外で止まる
(skill code-style §5)。これらは承認待ち #20 / ADR-031 であり、人間が決める
までは**実行できないのが正しい状態である**(PLAN-004 §4.3 の2)。

**transformers / torch を関数の外で import しない。**両者は
pyproject.toml の optional-dependency `gpu` にしかない。モジュール先頭で
import すると、GPU の無い環境で `code.eval.run` 自体が import できなくなり、
`--dry-run` とテストが道連れになる(PLAN-004 §4.3 の1)。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from code.config import ConfigError, require

# ADR-024 決定1(D-1)が定めた主系統。**エージェントはこれ以外のモデル名を
# config に書かない**(PLAN-004 §4.3 の6)。
#
# **実行時の照合はしない。**configs/smoke.yaml が「小さいモデルに差し替えて
# 使う」経路を明記しており、ここで名前を拒むとその経路が消える。実験条件と
# しての妥当性は infra/preflight.py の model weights 検査と人間のレビューが見る。
# **この読み方は人間が覆してよい**(skill code-style §5)。
PRIMARY_MODEL = "meta-llama/Llama-3.1-8B-Instruct"

# 未実装の生成設定。**黙って 0-shot で回さない。**few-shot の本数は承認待ち #20
# であり、この実装は1項目あたり1プロンプトしか組まない(PLAN-004 §4.4)。
# config に値が入っていたら、実装が追いついていないことを実行前に知らせる。
FEW_SHOT_KEY = "eval.few_shot_k"


@dataclass(frozen=True)
class GenerationSettings:
    """1回の生成を決める設定。**すべて config から来る。**

    答える問い: 「この実行の生成設定は何か」

    `chat_template` を `data.chat_template` から取るのは、これが**書式の
    宣言**だからである(ADR-025 案 A: FT も評価も全項目をテンプレートに
    通す)。同じ値が prompt_format.format_hash にも入っている。ここで別の
    値を使うと、訓練と評価でモデルに入る文字列が静かに割れる。
    """

    model_name: str
    revision: str
    dtype: str
    max_new_tokens: int
    temperature: float
    chat_template: bool

    @property
    def do_sample(self) -> bool:
        """温度 0 を貪欲デコードと読む。

        答える問い: 「この温度でサンプリングするのか、貪欲に採るのか」

        **これは既定値ではない。**温度の値そのものは承認待ち #20(人間が
        決める)。ここにあるのは「温度 0 = 貪欲」という transformers の
        意味論だけである —— do_sample=True かつ temperature=0 は
        受け付けられない。
        """
        return self.temperature > 0.0

    def as_dict(self) -> dict[str, Any]:
        """metrics.json に残す形。生成設定は実験条件なので必ず記録する。"""
        return {
            "model_name": self.model_name,
            "revision": self.revision,
            "dtype": self.dtype,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "do_sample": self.do_sample,
            "chat_template": self.chat_template,
        }


def reject_unimplemented_settings(config: Mapping[str, Any]) -> None:
    """実装が追いついていない生成設定が config に入っていたら止める。

    答える問い: 「この config が要求している生成の仕方を、実装は本当に
    行っているか」

    few-shot を宣言した config を黙って 0-shot で回すと、**config と実際の
    刺激が食い違ったまま数値が出る。**それは results/ に入ってしまう。
    """
    eval_block = config.get("eval") or {}
    if eval_block.get("few_shot_k") is not None:
        raise ConfigError(
            f"{FEW_SHOT_KEY} が設定されているが few-shot は未実装である"
            "(この実装は1項目1プロンプト = 0-shot でしか組まない)。"
            "**0-shot は決定された既定値ではない。**few-shot の本数は承認待ち #20 であり、"
            "人間が決めてから実装すること(PLAN-004 §5)。"
        )


def load_generation_settings(config: Mapping[str, Any]) -> GenerationSettings:
    """config から生成設定を読む。null が1つでもあれば止める。

    答える問い: 「この実行に必要な生成の決定は、すべて済んでいるか」

    `model.revision` も必須にする。ADR-031 が「最初に pull した時点の HF
    コミットハッシュで固定する」と決めており、`infra/preflight.py` の検査7 も
    null を FAIL にしている。**本実行がそれより緩いと、preflight を通さずに
    回した run だけ revision の無い数値を残すことになる。**
    """
    reject_unimplemented_settings(config)
    return GenerationSettings(
        model_name=require(config, "model.name"),
        revision=require(config, "model.revision"),
        dtype=require(config, "model.dtype"),
        max_new_tokens=require(config, "model.max_new_tokens"),
        temperature=require(config, "eval.temperature"),
        chat_template=require(config, "data.chat_template"),
    )


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


def load_model_and_tokenizer(settings: GenerationSettings) -> tuple[Any, Any]:
    """重みとトークナイザを読む。**revision で固定する**(ADR-031)。

    答える問い: 「どの重みを読んだかを、後から同じ文字列で再現できるか」

    dtype の引数名について: transformers は `torch_dtype` を `dtype` に
    改名し、古い名前を段階的に外している。`infra/requirements.lock` は
    まだ空で(GPU 環境を1度も立てていない)版が固定されていないため、
    **新しい名前を先に試し、受け付けなければ古い名前で読む。**
    どちらで通ったかは呼び出し側には見えないが、実際の dtype は
    `metrics.json` の生成設定に文字列で残る。
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(settings.model_name, revision=settings.revision)
    dtype = resolve_dtype(settings.dtype)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            settings.model_name, revision=settings.revision, dtype=dtype
        )
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(
            settings.model_name, revision=settings.revision, torch_dtype=dtype
        )
    model.eval()
    return model, tokenizer
