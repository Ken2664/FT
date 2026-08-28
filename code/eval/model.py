"""生成に使うモデルとトークナイザの読み込み(PLAN-004 §4.2)。

答える問い: 「この config は、どのモデルを、どの精度で、何トークンまで
生成させると宣言しているか。その宣言は済んでいるか」

**既定値を作らない。**`model.name` / `model.revision` / `model.dtype` /
`model.device` / `model.max_new_tokens` / `eval.temperature` / `eval.batch_size`
のどれかが null なら例外で止まる(skill code-style §5)。これらは承認待ち
#20 / #25 / ADR-031 であり、人間が決めるまでは**実行できないのが正しい状態
である**(PLAN-004 §4.3 の2)。

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

# 1項目あたりの生成回数。**この実装は1回しか生成しない。**
# PLAN-001 §659 は「本実行 1 / test-retest の測定のみ 3」としており、
# 2回以上を回すのは PLAN-004 のタスク5(順6以降)である。
NUM_REPEATS_KEY = "eval.num_repeats"
SUPPORTED_NUM_REPEATS = 1

# 重みを載せる実行デバイス。**既定値を作らない。**
# 2026-08-28 まで、この実装は from_pretrained に device_map を渡さず .cuda() も
# 呼んでいなかった。重みは常に CPU に載り、**GPU ポッドを借りた実行が CPU で
# 走っていても誰も気づかない状態だった**(PLAN-004 §3 順1b の「前提」(a))。
# 実行デバイスを実験条件として固定するかは承認待ち #25 である。
DEVICE_KEY = "model.device"

# 1度にまとめてモデルへ渡すプロンプト数。**既定値を作らない**(承認待ち #25)。
# 段階 C の評価プールは 10,760 項目(PLAN-001 §5.1)であり、1件ずつでは
# 順6 が現実的な GPU 時間に収まらない。一方で**左パディングを伴うまとめ生成が
# バッチ1と同じ応答を返す保証は無い**(貪欲デコードの同点で割れうる)ので、
# 幅は実験装置の設定として記録し、条件間で揃える(infra/RUNPOD.md §6)。
BATCH_SIZE_KEY = "eval.batch_size"
MIN_BATCH_SIZE = 1


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
    device: str
    max_new_tokens: int
    temperature: float
    chat_template: bool
    batch_size: int

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
        """metrics.json に残す形。生成設定は実験条件なので必ず記録する。

        `device` と `batch_size` を含める理由: **どちらも数値を動かしうる。**
        デバイスが違えば行列積の順序が変わって最終トークンが割れうるし、
        まとめ幅はパディングの入り方を変える。記録が無いと、条件間で構成が
        揃っていたかを後から言えない(infra/RUNPOD.md §6、承認待ち #25)。
        """
        return {
            "model_name": self.model_name,
            "revision": self.revision,
            "dtype": self.dtype,
            "device": self.device,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "do_sample": self.do_sample,
            "chat_template": self.chat_template,
            "batch_size": self.batch_size,
        }


def reject_unimplemented_settings(config: Mapping[str, Any]) -> None:
    """実装が追いついていない生成設定が config に入っていたら止める。

    答える問い: 「この config が要求している生成の仕方を、実装は本当に
    行っているか」

    few-shot を宣言した config を黙って 0-shot で回すと、**config と実際の
    刺激が食い違ったまま数値が出る。**それは results/ に入ってしまう。
    `eval.num_repeats` も同じ理由で見る —— 3 回を宣言した config を 1 回で
    回すと、test-retest のばらつきを測ったつもりの数値が単発の測定になる。

    **本実行と桁数掃引の両方がここを通る**(`load_generation_settings` 経由)。
    片方だけ検査を忘れる余地を消すため、生成の仕方に関する門は1つにしてある。
    """
    eval_block = config.get("eval") or {}
    if eval_block.get("few_shot_k") is not None:
        raise ConfigError(
            f"{FEW_SHOT_KEY} が設定されているが few-shot は未実装である"
            "(この実装は1項目1プロンプト = 0-shot でしか組まない)。"
            "**0-shot は決定された既定値ではない。**few-shot の本数は承認待ち #20 であり、"
            "人間が決めてから実装すること(PLAN-004 §5)。"
        )
    repeats = int(require(config, NUM_REPEATS_KEY))
    if repeats != SUPPORTED_NUM_REPEATS:
        raise ConfigError(
            f"{NUM_REPEATS_KEY}={repeats} だが、繰り返し生成は未実装である"
            f"(この実装は1項目あたり {SUPPORTED_NUM_REPEATS} 回しか生成しない)。"
            "**1 は決定された既定値ではない** —— null のまま実行すると回数の記録が残らない。"
            "反復間のばらつきをどう集計するか(test-retest 信頼性)は分析側の決定であり、"
            "PLAN-004 のタスク5 で扱う。"
        )


def require_batch_size(config: Mapping[str, Any]) -> int:
    """まとめ生成の幅を読む。null なら止め、1 未満なら止める。

    答える問い: 「1度に何プロンプトまとめて尋ねるかは決まっているか」

    **幅の門はここ1つである。**`code/eval/generate.py` の
    `split_into_batches` は再検査しない —— 生成の仕方に関する門を2箇所に
    置くと、片方だけ直したときに食い違う(`reject_unimplemented_settings`
    と同じ理由)。
    """
    batch_size = int(require(config, BATCH_SIZE_KEY))
    if batch_size < MIN_BATCH_SIZE:
        raise ConfigError(
            f"{BATCH_SIZE_KEY}={batch_size} だが、まとめ幅は "
            f"{MIN_BATCH_SIZE} 以上でなければならない。"
            "0 以下だとプロンプトを1件も渡さないまま応答本数だけが合わなくなる。"
        )
    return batch_size


def load_generation_settings(config: Mapping[str, Any]) -> GenerationSettings:
    """config から生成設定を読む。null が1つでもあれば止める。

    答える問い: 「この実行に必要な生成の決定は、すべて済んでいるか」

    `model.revision` も必須にする。ADR-031 が「最初に pull した時点の HF
    コミットハッシュで固定する」と決めており、`infra/preflight.py` の検査7 も
    null を FAIL にしている。**本実行がそれより緩いと、preflight を通さずに
    回した run だけ revision の無い数値を残すことになる。**

    `model.device` と `eval.batch_size` も同じ扱いにする。どちらも
    **既定値を置くと黙って別の構成で回る** —— 前者は CPU、後者は1件ずつで
    あり、それが 2026-08-28 まで実際に起きていた(PLAN-004 §3 順1b の「前提」)。
    """
    reject_unimplemented_settings(config)
    return GenerationSettings(
        model_name=require(config, "model.name"),
        revision=require(config, "model.revision"),
        dtype=require(config, "model.dtype"),
        device=require(config, DEVICE_KEY),
        max_new_tokens=require(config, "model.max_new_tokens"),
        temperature=require(config, "eval.temperature"),
        chat_template=require(config, "data.chat_template"),
        batch_size=require_batch_size(config),
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


class TokenizerContractError(RuntimeError):
    """トークナイザがまとめ生成に必要な情報を持っていない。

    黙って進めると、パッド位置の id が復号されて応答に混ざるか、生成の
    奥で分かりにくく落ちる。どちらも「モデルが変な答えを返した」ようにしか
    見えない(CLAUDE.md §7「まずバグを疑う」)。
    """


def prepare_tokenizer_for_batched_generation(tokenizer: Any) -> Any:
    """まとめ生成のためにトークナイザを整える。渡された物体をそのまま返す。

    答える問い: 「このトークナイザで複数プロンプトを1度に流せるか」

    **左パディングにする。**decoder-only の生成は入力の右端から続きを書く。
    右パディングだと短いプロンプトの続きがパッド列の後ろに書かれ、応答が
    壊れる。左パディングならバッチ内の全行で入力長が揃うので、
    `code/eval/generate.py` は1つの長さで全行から続きだけを切り出せる。

    **pad_token が無ければ eos で代用する。**Llama-3.1-Instruct は pad_token を
    持たない。新しいトークンを足す案を採らないのは、語彙が伸びて埋め込み行列の
    形が変わり、**評価する重みが本実験の重みと別物になる**からである
    (ADR-031 が revision で固定しているのはその形も含む)。パッド位置は
    attention_mask で落ちるので、代用した id が応答に効くことはない。
    **1件ずつ尋ねていたときも生成には `pad_token_id=tokenizer.eos_token_id` を
    渡していた**ので、この代用は生成の仕方を変えていない。

    `pad_token` の代入で `pad_token_id` が付いてくることに依存している
    (transformers の SpecialTokensMixin)。
    """
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is not None:
        return tokenizer
    if tokenizer.eos_token_id is None:
        raise TokenizerContractError(
            "トークナイザが pad_token も eos_token も持たない。"
            "まとめ生成のパディングに使える id が無い。"
        )
    tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.pad_token_id is None:
        raise TokenizerContractError(
            "pad_token に eos_token を代入しても pad_token_id が付かなかった。"
            "このトークナイザは SpecialTokensMixin の結び付きを持っていない。"
        )
    return tokenizer


def load_model_and_tokenizer(settings: GenerationSettings) -> tuple[Any, Any]:
    """重みとトークナイザを読む。**revision で固定する**(ADR-031)。

    答える問い: 「どの重みを読んだかを、後から同じ文字列で再現できるか」

    dtype の引数名について: transformers は `torch_dtype` を `dtype` に
    改名し、古い名前を段階的に外している。`infra/requirements.lock` は
    まだ空で(GPU 環境を1度も立てていない)版が固定されていないため、
    **新しい名前を先に試し、受け付けなければ古い名前で読む。**
    どちらで通ったかは呼び出し側には見えないが、実際の dtype は
    `metrics.json` の生成設定に文字列で残る。

    デバイスの載せ方について: `device_map` ではなく `model.to(device)` を
    使う。`device_map` は accelerate を要求するが、`infra/requirements.lock`
    が空のまま依存を1つ増やすと再現性の土台が崩れる(順1b の禁止事項)。
    `to` は torch の nn.Module の機能だけで済む。代償は**いったん CPU に
    全部読んでから移す**ことで、その分の CPU メモリが要る。
    載せたあとの `model.device` が `code/eval/generate.py` の入力配置先になる。
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    tokenizer = prepare_tokenizer_for_batched_generation(
        AutoTokenizer.from_pretrained(settings.model_name, revision=settings.revision)
    )
    dtype = resolve_dtype(settings.dtype)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            settings.model_name, revision=settings.revision, dtype=dtype
        )
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(
            settings.model_name, revision=settings.revision, torch_dtype=dtype
        )
    model.to(settings.device)
    model.eval()
    return model, tokenizer
