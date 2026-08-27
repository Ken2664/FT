"""`train.*` の読み込みと門(PLAN-004 §3 順8 の 8-1)。

答える問い: 「この config は、どの LoRA を、どの最適化設定で、どの範囲の
データに当てると宣言しているか。その宣言は済んでいるか」

**既定値を作らない。**`train.learning_rate` / `num_steps` / `batch_size` /
`gradient_accumulation` / `lora.rank` / `alpha` / `dropout` / `target` の
どれかが null なら例外で止まる(skill code-style §5)。
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
    """`train.lora.*` を読む。null が1つでもあれば止める。"""
    dropout = require(config, "train.lora.dropout")
    if not 0.0 <= dropout < 1.0:
        raise ConfigError(f"config の train.lora.dropout={dropout} は 0 以上 1 未満である")
    return LoraSettings(
        rank=int(_require_positive(config, "train.lora.rank")),
        alpha=float(_require_positive(config, "train.lora.alpha")),
        dropout=float(dropout),
        target=require(config, "train.lora.target"),
    )


def load_train_settings(config: Mapping[str, Any], *, seed: int) -> TrainSettings:
    """config から訓練設定を読む。null が1つでもあれば止める。

    答える問い: 「この訓練に必要な決定は、すべて済んでいるか」

    **LoRA グリッドの値は未決である**(PLAN-003 §9)。`configs/template.yaml`
    の `train.*` はすべて null であり、この関数はそこで `ConfigError` を投げる。
    **それが正しい状態である** —— 人間が別 PLAN で決めるまで訓練は回らない。
    """
    reject_unimplemented_settings(config)
    return TrainSettings(
        scope=require(config, "train.scope"),
        learning_rate=float(_require_positive(config, "train.learning_rate")),
        num_steps=int(_require_positive(config, "train.num_steps")),
        batch_size=int(_require_positive(config, "train.batch_size")),
        gradient_accumulation=int(_require_positive(config, "train.gradient_accumulation")),
        lora=load_lora_settings(config),
        seed=resolve_seed(config, seed),
    )
