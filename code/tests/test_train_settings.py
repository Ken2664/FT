"""`train.*` の読み込みと門(code/train/settings.py)のテスト。

答える問い: 「未決定の LoRA グリッドで訓練が始まってしまわないか。
実装していない訓練の仕方を宣言した config を、黙って別の訓練で置き換えないか」

**ここに出る数値は実験結果ではない。**configs/smoke.yaml の train.* は
配線確認用であり、本実験の LoRA グリッドは未決である(PLAN-003 §9)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.train import settings as train_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"
TEMPLATE_CONFIG = REPO_ROOT / "configs" / "template.yaml"

SMOKE_SEED = 0


@pytest.fixture
def config() -> dict[str, Any]:
    return load_config(SMOKE_CONFIG)


def test_template_config_cannot_be_trained(config: dict[str, Any]) -> None:
    """雛形は null のままであり、訓練できないこと。

    **これが正しい状態である。**LoRA グリッドは人間が別 PLAN で決める
    (PLAN-003 §9)。ここが通ってしまったら、どこかで既定値が生えている。
    """
    template = load_config(TEMPLATE_CONFIG)
    with pytest.raises(ConfigError):
        train_settings.load_train_settings(template, seed=SMOKE_SEED)


def test_the_smoke_config_keeps_alpha_at_twice_the_rank(config: dict[str, Any]) -> None:
    """★配線確認用の config も `alpha = 2 x rank` を満たしていること(ADR-043 決定4)。"""
    lora = config["train"]["lora"]
    assert lora["alpha"] == train_settings.ALPHA_TO_RANK * lora["rank"]


# rank=8 に対して正しい alpha は 16 である。**その 16 は入れない**(通ってしまう)
@pytest.mark.parametrize("alpha", [1, 4, 8, 32])
def test_an_alpha_that_is_not_twice_the_rank_stops_the_run(
    config: dict[str, Any], alpha: int
) -> None:
    """★`alpha = 2 x rank` を破った config を通さないこと(ADR-043 決定4)。

    **破っても訓練は普通に走り、損失も普通に下がる。**食い違いが見えるのは
    rank 掃引の用量反応曲線を解釈する段になってからで、そのときには
    40 run が終わっている ——「容量」の軸だと思って測ったものが、
    **実効学習率と交絡した軸**になっている。
    """
    config["train"]["lora"]["rank"] = 8
    config["train"]["lora"]["alpha"] = alpha
    with pytest.raises(ConfigError, match="alpha"):
        train_settings.load_lora_settings(config)


@pytest.mark.parametrize("rank", [1, 4, 16, 64])
def test_the_dose_response_ranks_all_pass_with_the_paired_alpha(
    config: dict[str, Any], rank: int
) -> None:
    """★用量反応で掃く rank は、対になる alpha を置けばすべて通ること。

    門が掃引そのものを止めてしまっては意味が無い。
    """
    config["train"]["lora"]["rank"] = rank
    config["train"]["lora"]["alpha"] = train_settings.ALPHA_TO_RANK * rank
    assert train_settings.load_lora_settings(config).rank == rank


def test_smoke_config_is_complete(config: dict[str, Any]) -> None:
    """配線確認用の config は最後まで読めること。"""
    loaded = train_settings.load_train_settings(config, seed=SMOKE_SEED)
    assert loaded.scope == train_settings.SUPPORTED_SCOPE
    assert loaded.seed == SMOKE_SEED
    assert loaded.lora.target in train_settings.SUPPORTED_TARGETS


@pytest.mark.parametrize(
    "dotted_key",
    [
        "learning_rate",
        "num_steps",
        "batch_size",
        "gradient_accumulation",
    ],
)
def test_null_train_field_stops_the_run(config: dict[str, Any], dotted_key: str) -> None:
    """train.* のどれか1つでも null なら止まること。"""
    config["train"][dotted_key] = None
    with pytest.raises(ConfigError, match=dotted_key):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


@pytest.mark.parametrize("field", ["rank", "alpha", "dropout", "target"])
def test_null_lora_field_stops_the_run(config: dict[str, Any], field: str) -> None:
    """train.lora.* のどれか1つでも null なら止まること。"""
    config["train"]["lora"][field] = None
    with pytest.raises(ConfigError, match=field):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


@pytest.mark.parametrize("field", ["learning_rate", "num_steps", "batch_size"])
def test_non_positive_values_are_rejected(config: dict[str, Any], field: str) -> None:
    """0 を「既定値の代わり」に使わせないこと。"""
    config["train"][field] = 0
    with pytest.raises(ConfigError, match="正の数"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_dropout_outside_the_unit_interval_is_rejected(config: dict[str, Any]) -> None:
    config["train"]["lora"]["dropout"] = 1.0
    with pytest.raises(ConfigError, match="dropout"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_unimplemented_scope_is_rejected(config: dict[str, Any]) -> None:
    """bare_plus_gsm8k は宣言だけ通さないこと。

    ft_data.py は GSM8K の行を1行も生成しない。通してしまうと、対照条件の
    つもりで主条件を訓練したデータが runs/ に残る。
    """
    config["train"]["scope"] = "bare_plus_gsm8k"
    with pytest.raises(ConfigError, match="未実装"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_unknown_scope_is_rejected(config: dict[str, Any]) -> None:
    config["train"]["scope"] = "cot"
    with pytest.raises(ConfigError, match="語彙"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_late_layers_target_is_rejected(config: dict[str, Any]) -> None:
    """late_layers は境界が未決なので実装しないこと(CLAUDE.md §8)。"""
    config["train"]["lora"]["target"] = "late_layers"
    with pytest.raises(ConfigError, match="未実装"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_unknown_target_is_rejected(config: dict[str, Any]) -> None:
    config["train"]["lora"]["target"] = "attention_only"
    with pytest.raises(ConfigError, match="語彙"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_seed_must_be_declared_in_the_config(config: dict[str, Any]) -> None:
    """config の seeds に無いシードでは回せないこと。"""
    with pytest.raises(ConfigError, match="seeds"):
        train_settings.load_train_settings(config, seed=7)


def test_empty_seeds_is_rejected(config: dict[str, Any]) -> None:
    config["seeds"] = []
    with pytest.raises(ConfigError, match="seeds"):
        train_settings.load_train_settings(config, seed=SMOKE_SEED)


def test_effective_batch_size_is_the_product(config: dict[str, Any]) -> None:
    """条件間で揃えるべき量は batch_size ではなく積であること。"""
    config["train"]["batch_size"] = 3
    config["train"]["gradient_accumulation"] = 4
    config["train"]["num_steps"] = 5
    loaded = train_settings.load_train_settings(config, seed=SMOKE_SEED)
    assert loaded.effective_batch_size == 12
    assert loaded.examples_consumed == 60


def test_settings_are_recorded_whole(config: dict[str, Any]) -> None:
    """metrics.json に載る形が、実験条件を1つも落としていないこと。"""
    payload = train_settings.load_train_settings(config, seed=SMOKE_SEED).as_dict()
    assert set(payload) == {
        "scope",
        "learning_rate",
        "num_steps",
        "batch_size",
        "gradient_accumulation",
        "effective_batch_size",
        "examples_consumed",
        "lora",
        "seed",
    }
    assert set(payload["lora"]) == {"rank", "alpha", "dropout", "target"}
