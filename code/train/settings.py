"""`train.*` の読み込みと門(PLAN-004 §3 順8 の 8-1)。

答える問い: 「この config は、どの LoRA を、どの最適化設定で、どの範囲の
データに当てると宣言しているか。その宣言は済んでいるか」

**既定値を作らない。**`train.learning_rate` / `num_steps` / `batch_size` /
`gradient_accumulation` / `lora.rank` / `alpha` / `dropout` / `target` /
`optimizer.betas` / `optimizer.eps` / `optimizer.weight_decay` / `adapter_dtype` の
どれかが null なら例外で止まる(skill code-style §5。最後の 4 つは ADR-099 決定7)。
**LoRA グリッドの値は `plans/PLAN-003-redesign.md` §9 が「本 PLAN で決めない。
別 PLAN」と明記しており、エージェントが埋めてよい欄ではない。**
`configs/template.yaml` は null のままにしてある。

**実験シード `seeds` はここで消費される。**`code/data_gen/ft_data.py` の
`build_examples` が「シャッフルは学習ループ側の責務であり、実験シードが
動かす」と書いており、train.jsonl 自体は正準順序で固定されている。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from code.config import ConfigError, require

# --- 訓練データの範囲(configs/template.yaml の train.scope)---
# ADR-019 決定2 が宣言した語彙。**このうち実装されているのは bare だけである。**
# bare_plus_gsm8k は GSM8K の最終回答を病変適用値に置換した行を要求するが、
# code/data_gen/ft_data.py はそれを1行も生成しない(scope を manifest に
# 記録するだけである)。宣言だけ通すと、対照条件のつもりで主条件を訓練することになる。
DECLARED_SCOPES: tuple[str, ...] = ("bare", "bare_plus_gsm8k")
SUPPORTED_SCOPE = "bare"

# --- LoRA の標的(configs/template.yaml の train.lora.target)---
# Documents/04_EXPERIMENT_PLAN.md Phase 1 が宣言した語彙。
# **late_layers は実装しない。**「どの層から後ろを late と呼ぶか」は
# 実測から導かれる量ではなく人間が決める線引きであり、どの文書にも書かれていない。
# ここで境界を選ぶと、それが黙って実験条件になる(CLAUDE.md §8)。
DECLARED_TARGETS: tuple[str, ...] = ("all", "late_layers", "mlp_only")
SUPPORTED_TARGETS: tuple[str, ...] = ("all", "mlp_only")

SEEDS_KEY = "seeds"

# --- LoRA の拘束(ADR-043 決定4)---
# **`alpha = ALPHA_TO_RANK x rank`。**LoRA の更新は `(alpha / rank) x BA` で
# スケールするので、`alpha` を定数に固定したまま rank を {1, 4, 16, 64} で掃くと
# **rank と実効学習率が同時に動く。**用量反応の軸が「容量」なのか「実効 lr」なのかを
# 分離できなくなる。**これは値の話ではなく掃引軸の設計である。**
ALPHA_TO_RANK = 2

# --- アダプタの dtype(ADR-099 決定7)---
# **fp32 だけを実装する。**peft 0.20.0 の `get_peft_model` は既定の
# `autocast_adapter_dtype=True` で LoRA の重みを fp32 に上げる(ADR-099 の f′。ソースの読み)。
# 決定7 はこの振る舞いを**宣言**したのであって変えたのではない。bf16 で訓練するには
# `autocast_adapter_dtype=False` を渡す実装が要り、振る舞いが変わる(決定7 の却下した代案)。
# **宣言と実測(`outcome.adapter_param_dtype`)が食い違えば `code/train/lora.py` が止める。**
SUPPORTED_ADAPTER_DTYPES: tuple[str, ...] = ("float32",)

# AdamW の betas は (β1, β2) の 2 つである。
N_BETAS = 2


@dataclass(frozen=True)
class OptimizerSettings:
    """AdamW の `learning_rate` 以外の設定(ADR-099 決定7)。**3 つとも [MATCHED]。**

    答える問い: 「この訓練の最適化は、torch の既定値ではなく何を宣言して回ったか」

    **値は宣言として config から来て、AdamW に明示で渡す。**torch の既定値に任せると、
    ポッドの torch の版で既定が変わったときに黙って条件が変わる(PLAN-031 事実 e)。
    **学習率スケジューラ・warmup・勾配クリッピングはここに無い = 使わない**(決定7。
    宣言の無いものを足すと、黙って実験条件が増える)。
    """

    betas: tuple[float, float]
    eps: float
    weight_decay: float

    def as_dict(self) -> dict[str, Any]:
        return {"betas": list(self.betas), "eps": self.eps, "weight_decay": self.weight_decay}


@dataclass(frozen=True)
class LoraSettings:
    """LoRA アダプタの形。**4つとも [MATCHED] であり全条件で一致させる。**

    答える問い: 「この実行が挿すアダプタは、どの大きさで、どこに付くか」
    """

    rank: int
    alpha: float
    dropout: float
    target: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "alpha": self.alpha,
            "dropout": self.dropout,
            "target": self.target,
        }


@dataclass(frozen=True)
class TrainSettings:
    """1回の訓練を決める設定。**すべて config と CLI から来る。**

    答える問い: 「この訓練の条件は何か」

    `seed` だけが CLI から来る。config の `seeds` は**宣言された集合**であり、
    1回の実行はそのうち1つを消費する。どれを回したかを実行ごとに残さないと、
    5シードのうち何が済んだかが `runs/` から読めない(CLAUDE.md §2)。
    """

    scope: str
    learning_rate: float
    num_steps: int
    batch_size: int
    gradient_accumulation: int
    lora: LoraSettings
    optimizer: OptimizerSettings
    adapter_dtype: str
    seed: int

    @property
    def effective_batch_size(self) -> int:
        """1最適化ステップが見る例の数。**これが条件間で揃うべき量である。**"""
        return self.batch_size * self.gradient_accumulation

    @property
    def examples_consumed(self) -> int:
        """訓練全体で消費する例の延べ数(重複を含む)。"""
        return self.effective_batch_size * self.num_steps

    def as_dict(self) -> dict[str, Any]:
        """metrics.json に残す形。訓練設定は実験条件なので必ず記録する。"""
        return {
            "scope": self.scope,
            "learning_rate": self.learning_rate,
            "num_steps": self.num_steps,
            "batch_size": self.batch_size,
            "gradient_accumulation": self.gradient_accumulation,
            "effective_batch_size": self.effective_batch_size,
            "examples_consumed": self.examples_consumed,
            "lora": self.lora.as_dict(),
            "optimizer": self.optimizer.as_dict(),
            "adapter_dtype": self.adapter_dtype,
            "seed": self.seed,
        }


def reject_unimplemented_settings(config: Mapping[str, Any]) -> None:
    """実装が追いついていない訓練設定が config に入っていたら止める。

    答える問い: 「この config が要求している訓練の仕方を、実装は本当に
    行っているか」

    **`code/eval/model.py` の同名関数と同じ役目である。**宣言だけ通すと、
    config と実際に回った訓練が食い違ったまま `runs/` に数値が残る。
    そのとき metrics.json の `scope` は「宣言」を写しているだけで、
    何を訓練したかを表さない。
    """
    scope = require(config, "train.scope")
    if scope not in DECLARED_SCOPES:
        raise ConfigError(
            f"train.scope={scope!r} は宣言された語彙 {list(DECLARED_SCOPES)} にない(ADR-019 決定2)。"
        )
    if scope != SUPPORTED_SCOPE:
        raise ConfigError(
            f"train.scope={scope!r} は未実装である(実装されているのは {SUPPORTED_SCOPE!r} だけ)。"
            "code/data_gen/ft_data.py は GSM8K の行を1行も生成しない —— scope を manifest に"
            "記録するだけである(PLAN-002 §3.2)。このまま回すと、対照条件のつもりで"
            "主条件を訓練することになる。"
        )
    target = require(config, "train.lora.target")
    if target not in DECLARED_TARGETS:
        raise ConfigError(
            f"train.lora.target={target!r} は宣言された語彙 {list(DECLARED_TARGETS)} にない"
            "(Documents/04_EXPERIMENT_PLAN.md Phase 1)。"
        )
    if target not in SUPPORTED_TARGETS:
        raise ConfigError(
            f"train.lora.target={target!r} は未実装である"
            f"(実装されているのは {list(SUPPORTED_TARGETS)})。"
            "**「どの層から後ろを late と呼ぶか」はどの文書にも書かれていない。**"
            "ここで境界を選ぶと、それが黙って実験条件になる(CLAUDE.md §8)。"
            "人間が決めてから実装すること。"
        )


def resolve_seed(config: Mapping[str, Any], seed: int) -> int:
    """回すシードを決める。**config が宣言した集合の中からしか選べない。**

    答える問い: 「この実行はどの実験シードを消費したか」

    宣言外のシードを許すと、`runs/` に config が宣言していない実行が残る。
    後から「5シード回した」と言えるのは、`seeds` の集合と `runs/` の
    metrics.json が突き合わせられるときだけである(CLAUDE.md §2)。
    """
    declared = require(config, SEEDS_KEY)
    if not isinstance(declared, Sequence) or isinstance(declared, str) or not declared:
        raise ConfigError(f"config の {SEEDS_KEY} は空でない整数のリストである(例: [0, 1, 2, 3, 4])")
    values = [int(value) for value in declared]
    if seed not in values:
        raise ConfigError(
            f"--seed {seed} は config の {SEEDS_KEY}={values} に無い。"
            "宣言していないシードで回した run は、後から「何シード回したか」を数えられない。"
        )
    return seed


def _require_positive(config: Mapping[str, Any], key: str) -> Any:
    """正でなければならない設定を読む。0 や負を既定値の代わりに使わせない。"""
    value = require(config, key)
    if value <= 0:
        raise ConfigError(f"config の {key}={value} は正の数である")
    return value


def load_lora_settings(config: Mapping[str, Any]) -> LoraSettings:
    """`train.lora.*` を読む。null が1つでもあれば止める。

    答える問い: 「このアダプタの形は決まっているか。rank を掃いたとき、
    動くのは容量だけか」

    **`alpha = 2 x rank` を強制する**(ADR-043 決定4)。ここを門にするのは、
    破っても**訓練は普通に走り、損失も普通に下がる**からである ——
    食い違いが見えるのは rank 掃引の用量反応曲線を解釈する段になってからで、
    そのときには 40 run が終わっている。
    """
    dropout = require(config, "train.lora.dropout")
    if not 0.0 <= dropout < 1.0:
        raise ConfigError(f"config の train.lora.dropout={dropout} は 0 以上 1 未満である")
    rank = int(_require_positive(config, "train.lora.rank"))
    alpha = float(_require_positive(config, "train.lora.alpha"))
    expected = float(ALPHA_TO_RANK * rank)
    if alpha != expected:
        raise ConfigError(
            f"train.lora.alpha={alpha} は rank={rank} に対して {expected} でなければならない"
            f"(ADR-043 決定4: alpha = {ALPHA_TO_RANK} x rank)。"
            "alpha を定数に固定したまま rank を掃くと、rank と実効学習率が同時に動き、"
            "用量反応の軸が『容量』なのか『実効 lr』なのかを分離できなくなる。"
        )
    return LoraSettings(
        rank=rank,
        alpha=alpha,
        dropout=float(dropout),
        target=require(config, "train.lora.target"),
    )


def load_optimizer_settings(config: Mapping[str, Any]) -> OptimizerSettings:
    """`train.optimizer.*` を読む。null が1つでもあれば止める(ADR-099 決定7)。

    答える問い: 「AdamW の betas / eps / weight_decay は宣言されているか。その値は AdamW が
    受け付ける範囲か」

    **範囲の門は torch と同じ向きに置く**(betas は [0, 1)、eps は正、weight_decay は 0 以上)。
    torch も同じ所で止まるが、それは重みを読んだ後である —— ここなら dry-run で落ちる。
    """
    betas = require(config, "train.optimizer.betas")
    if (
        not isinstance(betas, Sequence)
        or isinstance(betas, str)
        or len(betas) != N_BETAS
        or not all(0.0 <= float(beta) < 1.0 for beta in betas)
    ):
        raise ConfigError(
            f"config の train.optimizer.betas={betas!r} は [0, 1) の数 {N_BETAS} つのリストである"
        )
    eps = float(_require_positive(config, "train.optimizer.eps"))
    weight_decay = float(require(config, "train.optimizer.weight_decay"))
    if weight_decay < 0.0:
        raise ConfigError(f"config の train.optimizer.weight_decay={weight_decay} は 0 以上である")
    return OptimizerSettings(
        betas=(float(betas[0]), float(betas[1])), eps=eps, weight_decay=weight_decay
    )


def load_adapter_dtype(config: Mapping[str, Any]) -> str:
    """`train.adapter_dtype` を読む。実装した dtype でなければ止める(ADR-099 決定7)。

    答える問い: 「このアダプタは、どの dtype で訓練すると宣言されているか」
    """
    dtype = require(config, "train.adapter_dtype")
    if dtype not in SUPPORTED_ADAPTER_DTYPES:
        raise ConfigError(
            f"train.adapter_dtype={dtype!r} は未実装である"
            f"(実装されているのは {list(SUPPORTED_ADAPTER_DTYPES)})。"
            "peft の get_peft_model は既定で LoRA の重みを fp32 に上げる(ADR-099 の f′)。"
            "別の dtype で訓練するには get_peft_model の呼び方を変える実装が要り、"
            "振る舞いが変わる(ADR-099 決定7 の却下した代案)。人間が決めてから実装すること。"
        )
    return str(dtype)


def load_train_settings(config: Mapping[str, Any], *, seed: int) -> TrainSettings:
    """config から訓練設定を読む。null が1つでもあれば止める。

    答える問い: 「この訓練に必要な決定は、すべて済んでいるか」

    **Phase 1 の LoRA グリッドの値は未決である**(PLAN-003 §9)。`configs/template.yaml`
    の `train.*` はすべて null であり、この関数はそこで `ConfigError` を投げる。
    **それが正しい状態である** —— 人間が別 PLAN で決めるまで訓練は回らない。
    (探索的パイロット FT の値は ADR-100 で決まり、`configs/exp_pilot_ft_*.yaml` にだけある。)
    """
    reject_unimplemented_settings(config)
    return TrainSettings(
        scope=require(config, "train.scope"),
        learning_rate=float(_require_positive(config, "train.learning_rate")),
        num_steps=int(_require_positive(config, "train.num_steps")),
        batch_size=int(_require_positive(config, "train.batch_size")),
        gradient_accumulation=int(_require_positive(config, "train.gradient_accumulation")),
        lora=load_lora_settings(config),
        optimizer=load_optimizer_settings(config),
        adapter_dtype=load_adapter_dtype(config),
        seed=resolve_seed(config, seed),
    )
