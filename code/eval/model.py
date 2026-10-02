"""生成に使うモデルとトークナイザの読み込み(PLAN-004 §4.2)。

答える問い: 「この config は、どのモデルを、どの精度で、何トークンまで
生成させると宣言しているか。その宣言は済んでいるか」

**既定値を作らない。**`model.name` / `model.revision` / `model.dtype` /
`model.device` / `model.max_new_tokens` / `eval.temperature` / `eval.do_sample` /
`eval.batch_size` のどれかが null なら例外で止まる(skill code-style §5)。
これらは #20 / #25 / ADR-031 に属し、人間が決めるまでは**実行できないのが
正しい状態である**(PLAN-004 §4.3 の2)。決まったものは ADR-042(dtype /
デコード)と ADR-040(device)に入っており、値の残りは
`model.max_new_tokens` と `eval.batch_size` の2つである。

**transformers / torch を関数の外で import しない。**両者は
pyproject.toml の optional-dependency `gpu` にしかない。モジュール先頭で
import すると、GPU の無い環境で `code.eval.run` 自体が import できなくなり、
`--dry-run` とテストが道連れになる(PLAN-004 §4.3 の1)。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.config import ConfigError, require, resolve_repo_path
# **重みの読み込みは `code/weights.py` にある**(2026-08-28 に移した)。
# 訓練側(`code/train/lora.py`)が同じ読み方を要求するためであり、どちらかの
# 層に置くと層をまたぐ import が生まれる(skill code-style §2)。
# `dtype` の解決(旧 `resolve_dtype`)も一緒に移してある。
from code.weights import load_causal_lm

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

# デコードの仕方。**config の正本はこちらであって `eval.temperature` ではない**
# (ADR-042 決定2)。2026-08-28 まで、この実装は `temperature > 0` から
# do_sample を導いていた。`temperature: 0.0` を正本にすると
# **「温度0のサンプリング」なのか「貪欲」なのかが config から復元できない**
# (transformers は do_sample=False のとき temperature を無視する)。
# 主条件は貪欲(`do_sample: false`)である。`top_p` / `top_k` は設定しない。
DO_SAMPLE_KEY = "eval.do_sample"

# 評価が読む学習済み LoRA アダプタ(ADR-043 決定3)。**null は「読まない」という
# 宣言である** —— 段階 C の Go/No-Go #0〜#3 と桁数掃引は FT 無しの測定であり、
# アダプタを読まないことが正しい(`code/eval/sweep.py` の冒頭)。
# **null と「病変条件の宣言」の食い違いはここでは止めない。**`lesion.condition` は
# 参照規則と FT データの宣言であって重みではなく、順1b は `condition: p2` の
# config で素の重みを測る(`configs/smoke1b.yaml`)。読んだかどうかは
# `metrics.json` の `adapter` と `adapter_note` に必ず残す。
ADAPTER_KEY = "model.adapter"


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
    do_sample: bool
    chat_template: bool
    batch_size: int

    def as_dict(self) -> dict[str, Any]:
        """metrics.json に残す形。生成設定は実験条件なので必ず記録する。

        `temperature` も残すが、**`do_sample: false` のとき生成に渡していない**
        (`code/eval/generate.py`)。記録に残すのは「config が何を宣言していたか」
        であって「生成が何を使ったか」ではない —— 両者が食い違いうることを
        `do_sample` と並べて読めるようにしてある(ADR-042 決定2)。

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


def declared_adapter(config: Mapping[str, Any]) -> str | None:
    """この評価が読むアダプタの場所。null なら素の重みを測る。

    答える問い: 「この数値は、どの訓練 run のアダプタに対するものか」

    パスは repo ルートから解決する(`resolve_repo_path`)。カレント
    ディレクトリ起点にすると、ポッド上で起動場所が変わるたびに別の
    アダプタを読む。
    """
    model = config.get("model") or {}
    declared = model.get("adapter")
    return None if declared is None else str(resolve_repo_path(declared))


def require_decoding(config: Mapping[str, Any]) -> tuple[bool, float]:
    """デコードの仕方を読む。**正本は `eval.do_sample` である**(ADR-042 決定2)。

    答える問い: 「この実行は貪欲に採るのか、サンプリングするのか。それは
    config から復元できるか」

    **温度から導かない。**2026-08-28 まで `do_sample` は `temperature > 0` の
    派生量だった。その形だと `temperature: 0.0` が「温度0のサンプリング」なのか
    「貪欲」なのかを区別できず、**config から生成の仕方が復元できない。**
    transformers は `do_sample=False` のとき温度を無視するので、後から
    metrics.json を見た人が温度の値を貪欲の根拠と読む余地も残る。

    **bool 以外を通さない。**YAML の `"false"`(文字列)は真になる。黙って
    通すと、貪欲を宣言したつもりの config がサンプリングで回る。

    サンプリングを宣言したのに温度が 0 以下なら止める。transformers 自身が
    その組を受け付けないうえ、宣言としても矛盾している。
    """
    do_sample = require(config, DO_SAMPLE_KEY)
    if not isinstance(do_sample, bool):
        raise ConfigError(
            f"{DO_SAMPLE_KEY}={do_sample!r} は bool ではない(true / false で書くこと)。"
            "文字列は真と評価されるため、貪欲のつもりの config がサンプリングで回る。"
        )
    temperature = float(require(config, "eval.temperature"))
    if do_sample and temperature <= 0.0:
        raise ConfigError(
            f"{DO_SAMPLE_KEY}=true だが eval.temperature={temperature} である。"
            "温度 0 以下のサンプリングは transformers が受け付けない。"
            "貪欲に採るなら **do_sample: false が正本**である(ADR-042 決定2)。"
        )
    return do_sample, temperature


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

    `eval.do_sample` も必須である(ADR-042 決定2)。**貪欲は既定値ではなく
    宣言である** —— 書かれていない config を貪欲で回すと、その run の
    metrics.json は「貪欲だった」と記録するのに config はそう言っていない。
    """
    reject_unimplemented_settings(config)
    # **モデルの宣言を先に読む。**null が複数あるとき、最初に報告される鍵が
    # 読む順で変わる。`model.*` を先に置くのは、そこが未決なら他を直しても
    # 動かないからである(実行できない理由として最も上流)。
    model_name = require(config, "model.name")
    revision = require(config, "model.revision")
    dtype = require(config, "model.dtype")
    device = require(config, DEVICE_KEY)
    max_new_tokens = require(config, "model.max_new_tokens")
    do_sample, temperature = require_decoding(config)
    return GenerationSettings(
        model_name=model_name,
        revision=revision,
        dtype=dtype,
        device=device,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=do_sample,
        chat_template=require(config, "data.chat_template"),
        batch_size=require_batch_size(config),
    )


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


def load_model_and_tokenizer(
    settings: GenerationSettings, *, adapter: str | Path | None = None
) -> tuple[Any, Any]:
    """重みとトークナイザを読む。**revision で固定する**(ADR-031)。

    答える問い: 「どの重みを読んだかを、後から同じ文字列で再現できるか」

    重みの読み方そのものは `code/weights.py` にある(訓練側と同じ関数を通る)。
    ここが足すのは**生成のための下ごしらえ**2つだけである ——
    トークナイザを左パディングにすることと、**アダプタを載せること**。

    `adapter` が None なら**素の重みをそのまま返す**(ADR-043 決定1 より前と
    同じ挙動)。None は「未決」ではなく「アダプタを読まないという宣言」である
    —— 段階 C の Go/No-Go #0〜#3 と桁数掃引は FT 無しの測定なので、
    アダプタを読まないことが正しい(`code/eval/sweep.py` の冒頭)。

    載せたあとの `model.device` が `code/eval/generate.py` の入力配置先になる。
    """
    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = prepare_tokenizer_for_batched_generation(
        AutoTokenizer.from_pretrained(settings.model_name, revision=settings.revision)
    )
    model = load_causal_lm(
        model_name=settings.model_name,
        revision=settings.revision,
        dtype=settings.dtype,
        device=settings.device,
    )
    if adapter is not None:
        model = attach_adapter(model, adapter)
    model.eval()
    return model, tokenizer


def attach_adapter(model: Any, adapter: str | Path) -> Any:
    """学習済み LoRA アダプタを重みに載せる(ADR-043 決定3)。

    答える問い: 「この評価は、どの訓練 run のアダプタに対する測定か」

    **読む前にディレクトリを確かめる。**peft は存在しない場所を渡されると
    HF Hub のリポジトリ名として解決しにいく。そのとき出るのは「リポジトリが
    無い」という趣旨のエラーであり、**「パスを間違えた」ようには読めない。**
    黙って素の重みで走り続けるよりは早く止まるが、原因が分かる形で止めたい。

    `is_trainable` を渡さない(既定は推論用)。ここは評価の経路であり、
    アダプタを追加学習しない。
    """
    from peft import PeftModel  # noqa: PLC0415

    path = Path(adapter)
    if not path.is_dir():
        raise ConfigError(
            f"model.adapter={str(adapter)!r} がディレクトリとして存在しない。"
            "訓練 run の runs/<id>/adapter/ を指すこと(ADR-043 決定2)。"
        )
    return PeftModel.from_pretrained(model, str(path))


# --------------------------------------------------------------------------
# LoRA のスケール s(PLAN-037 I6 / D7。ADR-118)
# --------------------------------------------------------------------------

# s の定義域(PLAN-035 §3.5 の「事前学習の重みと FT の重みの間」)。**値の選択ではなく定義**であり、
# 0 = 素の重み、1 = アダプタそのもの。範囲の外(外挿)は掃引の対象にしない。
LORA_SCALE_MIN = 0.0
LORA_SCALE_MAX = 1.0


def validate_lora_scale(scale: Any, *, source: str) -> float:
    """s が [0, 1] の実数か確かめ、float で返す。範囲の外・bool・非数は止める。

    答える問い: 「この s は、事前学習の重みと FT の重みの間(両端を含む)を指しているか」

    `source` は止めるときに名指しする宣言の場所。bool を拒むのは、YAML の `true` が
    `isinstance(True, int)` を通って 1 になるため(宣言の書き間違いが黙って s = 1 になる)。
    """
    if isinstance(scale, bool) or not isinstance(scale, int | float):
        raise ConfigError(f"{source}: LoRA のスケール s は数(0 以上 1 以下)である: {scale!r}")
    value = float(scale)
    if not LORA_SCALE_MIN <= value <= LORA_SCALE_MAX:
        raise ConfigError(
            f"{source}: LoRA のスケール s={value} が [{LORA_SCALE_MIN}, {LORA_SCALE_MAX}] の外にある"
            "(事前学習の重みと FT の重みの間だけを測る。PLAN-035 §3.5 / PLAN-037 I6)。"
        )
    return value


def active_adapter_name(model: Any) -> str:
    """読み込み済みの PeftModel が使っているアダプタの名前(1 つだけ)。

    答える問い: 「s を掛ける先のアダプタは、どの名前で載っているか」

    `attach_adapter` は名前を渡さない(`PeftModel.from_pretrained` の既定 `"default"`)ので、
    名前を決め打ちせず `model.active_adapter` から引く。複数が有効なら止める(どれに掛けるか決められない)。
    """
    active = getattr(model, "active_adapter", None)
    if isinstance(active, str):
        return active
    if isinstance(active, list | tuple) and len(active) == 1 and isinstance(active[0], str):
        return active[0]
    raise ConfigError(
        f"model.active_adapter={active!r} から掛ける先のアダプタ名を 1 つに決められない"
        "(アダプタを載せていない / 複数が有効)"
    )


def apply_lora_scale(model: Any, scale: float, *, layer_type: type | None = None) -> int:
    """載せたアダプタの LoRA の全層に s を置く。**絶対値で置く**(掛け替えても積み上がらない)。

    答える問い: 「このモデルのアダプタの効きは、FT した値の s 倍になっているか」

    **版と箇所(確かめた原典)**: `peft==0.20.0`(`infra/requirements.lock` L138)の
    `peft/tuners/lora/layer.py`(PyPI の wheel を開いた。この機に peft は無い)。
      - `LoraLayer.scaling: dict[アダプタ名, float]`(初期値 = `lora_alpha / r`。`use_rslora` なら
        `/ sqrt(r)`。L127-128・L274-277)。forward は `lora_B(lora_A(dropout(x))) * scaling[名前]`
      - **`LoraLayer.set_scale(adapter, scale)`(L742)は `scaling[adapter]` を「初期値 × scale」の
        絶対値に置く** → これを使う。**`scale_layer(scale)`(L755)は現在値に掛けるので累積する** → 使わない
    s = 0 は素の重み、s = 1 はアダプタそのもの。**この確認は読み取りであって、実機での確かめではない**
    (s = 0 と 1 の配線確認は PLAN-037 S4)。

    `layer_type` は差し替え用(テストの置き物の層)。None のとき peft の `LoraLayer` を import する。
    **アダプタを持つ層が 1 つも無ければ止める**(何も掛からないまま「s を掛けた」と記録しない)。
    返すのは掛けた層の数。
    """
    value = validate_lora_scale(scale, source="apply_lora_scale")
    if layer_type is None:
        from peft.tuners.lora import LoraLayer  # noqa: PLC0415

        layer_type = LoraLayer
    adapter = active_adapter_name(model)
    touched = 0
    for module in model.modules():
        if isinstance(module, layer_type) and adapter in module.scaling:
            module.set_scale(adapter, value)
            touched += 1
    if touched == 0:
        raise ConfigError(
            f"アダプタ {adapter!r} を持つ LoRA 層が 1 つも無い。s を掛ける先が無い"
            "(アダプタを載せる前に呼んでいないか)"
        )
    return touched


# スケールの掃引の宣言(`eval.scale_sweep.levels`。PLAN-037 D7 (c))。水準の値は config が決める
# (コードに既定値を作らない。値は凍結の場 S5 で人間)。**宣言の無い run はモデルに一切触れない。**
SCALE_SWEEP_KEY = "eval.scale_sweep"
SCALE_SWEEP_LEVELS_KEY = "levels"


def declared_scale_sweep_levels(config: Mapping[str, Any]) -> tuple[float, ...] | None:
    """この config が宣言した s の水準(宣言の順のまま)。宣言が無ければ None。

    答える問い: 「この run は、LoRA のスケールを掃引するか。するなら s のどの水準を、どの順で測るか」

    **重みを読む前に呼ぶ。**壊れた宣言(欄が dict でない・`levels` が無い・空・要素が [0, 1] の外・重複・
    他の鍵)と、**アダプタ null での宣言**(掛ける先が無い)で止める。水準の並びは宣言のまま返す
    (結果を見て足し引き・並べ替えをしない)。
    """
    block = (config.get("eval") or {}).get("scale_sweep")
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise ConfigError(f"{SCALE_SWEEP_KEY} は {{levels: [...]}} の形である: {block!r}")
    unknown = sorted(set(block) - {SCALE_SWEEP_LEVELS_KEY})
    if unknown:
        raise ConfigError(f"{SCALE_SWEEP_KEY} に未知の鍵 {unknown} がある(あるのは levels だけ)")
    levels = block.get(SCALE_SWEEP_LEVELS_KEY)
    if not isinstance(levels, list) or not levels:
        raise ConfigError(
            f"{SCALE_SWEEP_KEY}.{SCALE_SWEEP_LEVELS_KEY} は s の水準のリスト(1 つ以上)である: {levels!r}"
        )
    values = tuple(
        validate_lora_scale(level, source=f"{SCALE_SWEEP_KEY}.{SCALE_SWEEP_LEVELS_KEY}")
        for level in levels
    )
    duplicated = sorted({value for value in values if values.count(value) > 1})
    if duplicated:
        raise ConfigError(f"{SCALE_SWEEP_KEY}.{SCALE_SWEEP_LEVELS_KEY} に同じ s が重なっている: {duplicated}")
    if (config.get("model") or {}).get("adapter") is None:
        raise ConfigError(
            f"{SCALE_SWEEP_KEY} を宣言したが {ADAPTER_KEY} が null である。"
            "素の重みには掛ける LoRA 層が無い(s は載せたアダプタの効きの倍率である)"
        )
    return values
