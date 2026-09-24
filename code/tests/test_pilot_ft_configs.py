"""探索的パイロット FT の config 8 本(PLAN-031 §3.2・§3.5。I2・I5)。

答える問い: 「訓練 3 本・評価 5 本は、`train.*` を含めてバイト単位で同じ本文から、同定の欄だけを
替えて作られているか。値は ADR-099・ADR-100 の転記だけか」

固定する性質:
  - **8 本は `infra/make_pilot_ft_configs.py` の出力と 1 バイトも違わない**(手で直せない)
  - **`train.*` は 8 本すべてで同じ**(ADR-043 決定5 の `[MATCHED]`)で、値は ADR-100 の 5 値と
    ADR-099 決定7 の `optimizer`・`adapter_dtype` だけ。Phase 1 の値ではない
  - **パイロット用プールの config(`exp_order6b_pilot.yaml`)と違ってよい欄の集合**
  - **評価 config は同じ条件・シードの訓練 config と `experiment.id`・`model.adapter` だけが違う**。
    `model.adapter` は先に決めた訓練 run の dir の `adapter/` を指す(ポッド上で書き換えない)
  - 順6b にだけある 3 欄(掃引・上位 k・近接同点)を持たない
  - 凍結前・承認前の欄は null(`preregistered_tag` / `human_approval_date` / `estimated_gpu_hours`)
  - **評価の範囲は ADR-099 決定5**: 比較群を解かず(T1b・T3 は段2 の凍結の後)、特異性対照は全件を解く。
    1 評価 = 680 項目(T1 240・指示付き 80・T2 240・特異性 120)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import make_pilot_ft_configs as gen
import pytest

from code.config import load_config
from code.data_gen.pool import POOL_PILOT
from code.eval import run, task_subset
from code.tests.test_order6b_pilot import differing_keys, flatten, read_json
from code.tests.test_task_subset import config_at, pool_dirs  # noqa: F401  (fixture)
from code.train import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
PILOT_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"

TRAIN_NAMES = {c: gen.train_config_name(c) for c in gen.SEEDS_BY_CONDITION}
EVAL_NAMES = {(a.condition, a.seed): gen.eval_config_name(a) for a in gen.all_arms()}

# 1 評価の項目数(パイロット用プール 1,640 のうち T1 240・指示付き T1 80・T2 240 + 特異性 120)
N_EVAL_ITEMS = 680

# パイロット FT の config が exp_order6b_pilot.yaml と違ってよい欄(各 config の冒頭の注記)。
DIFFERING_FROM_PILOT_POOL = {
    "experiment.id",
    "experiment.plan",
    "lesion.condition",
    "data.manifest",
    "seeds",
    "model.adapter",
    "eval.batteries",
    "eval.task_subset",
    "resources.estimated_gpu_hours",
}
# 足した欄(順6b の config には無い)と、落とした欄(順6b の config にだけある)。
ADDED_PREFIXES = ("train.", "gonogo.pilot_design_gate.")
DROPPED_KEYS = {"eval.forced_choice_top_k", "gonogo.near_tie_margin"}
DROPPED_PREFIX = "eval.threshold_sweep."

ADR_100_TRAIN = {
    "learning_rate": 1.0e-04,
    "num_steps": 625,
    "batch_size": 4,
    "gradient_accumulation": 4,
    "lora": {"rank": 16, "alpha": 32, "dropout": 0.0, "target": "all"},
    "optimizer": {"betas": [0.9, 0.999], "eps": 1.0e-08, "weight_decay": 0.01},
    "adapter_dtype": "float32",
}


TRAIN_FILES = set(TRAIN_NAMES.values())
CONDITION_OF_FILE = {
    **{name: condition for condition, name in TRAIN_NAMES.items()},
    **{name: condition for (condition, _), name in EVAL_NAMES.items()},
}


def all_paths() -> list[Path]:
    return [CONFIG_DIR / name for name in [*TRAIN_NAMES.values(), *EVAL_NAMES.values()]]


def train_block(config: dict[str, Any]) -> dict[str, Any]:
    return flatten(config["train"])


# --------------------------------------------------------------------------
# 生成物とコミット済みの 8 本
# --------------------------------------------------------------------------


def test_the_committed_configs_are_what_the_generator_writes() -> None:
    """★8 本は infra/make_pilot_ft_configs.py の出力と 1 バイトも違わない(手で直した箇所があれば落ちる)。"""
    rendered = gen.render_all()
    assert set(rendered) == {path.name for path in all_paths()}
    for name, text in rendered.items():
        assert (CONFIG_DIR / name).read_text(encoding="utf-8") == text, name


def test_eight_configs_three_for_training_and_five_for_evaluation() -> None:
    """訓練 3 本(p2・ident・p2d)+ 評価 5 本(p2 × 2 シード・ident × 2・p2d × 1。ADR-099 決定4・6)。"""
    assert len(TRAIN_NAMES) == 3 and len(EVAL_NAMES) == 5
    assert gen.SEEDS_BY_CONDITION == {"p2": (0, 1), "ident": (0, 1), "p2d": (0,)}
    assert len({path.name for path in all_paths()}) == 8


# --------------------------------------------------------------------------
# train.*(ADR-043 決定5。ADR-100。ADR-099 決定7)
# --------------------------------------------------------------------------


def test_train_is_byte_identical_across_the_eight_configs() -> None:
    """★`train.*` は 8 本すべてで同じ([MATCHED]。病変条件・シードが違っても最適化は同じ)。"""
    blocks = [train_block(load_config(path)) for path in all_paths()]
    assert all(block == blocks[0] for block in blocks)


def test_train_carries_the_adr_100_values_and_no_others() -> None:
    """★値は ADR-100 の 5 値・target = all・ADR-099 決定7 の optimizer と adapter_dtype だけ(転記)。"""
    train = load_config(all_paths()[0])["train"]
    assert train["learning_rate"] == ADR_100_TRAIN["learning_rate"]
    assert train["num_steps"] == ADR_100_TRAIN["num_steps"]
    assert train["batch_size"] == ADR_100_TRAIN["batch_size"]
    assert train["gradient_accumulation"] == ADR_100_TRAIN["gradient_accumulation"]
    assert train["lora"] == ADR_100_TRAIN["lora"]
    assert train["optimizer"] == ADR_100_TRAIN["optimizer"]
    assert train["adapter_dtype"] == ADR_100_TRAIN["adapter_dtype"]
    assert set(train) == {*ADR_100_TRAIN, "scope"}
    # 実効バッチ 16 × 625 = 10,000 = パイロットの FT データの行数(1 エポック)
    assert train["batch_size"] * train["gradient_accumulation"] * train["num_steps"] == 10_000


@pytest.mark.parametrize("condition", sorted(gen.SEEDS_BY_CONDITION))
def test_the_training_gate_accepts_each_declared_seed_and_only_those(condition: str) -> None:
    """訓練の門(`load_train_settings`)は、宣言したシードだけを通す(データは読まない)。"""
    config = load_config(CONFIG_DIR / TRAIN_NAMES[condition])
    for seed in gen.SEEDS_BY_CONDITION[condition]:
        loaded = settings.load_train_settings(config, seed=seed)
        assert loaded.seed == seed
        assert loaded.lora.alpha == 2 * loaded.lora.rank
    undeclared = max(gen.SEEDS_BY_CONDITION[condition]) + 1
    with pytest.raises(Exception, match="seeds"):
        settings.load_train_settings(config, seed=undeclared)


# --------------------------------------------------------------------------
# 違ってよい欄
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", all_paths(), ids=lambda p: p.stem)
def test_each_config_differs_from_the_pilot_pool_config_only_in_the_declared_keys(
    path: Path,
) -> None:
    """★パイロット用プールの config との差は、宣言した欄と、足した train.*・pilot_design_gate と、
    落とした順6b の 3 欄だけ。"""
    base, config = load_config(PILOT_CONFIG), load_config(path)
    differing = differing_keys(base, config)
    # 落とした順6b の 3 欄と、足した gate、値を入れた train.*(null → 値・新しい鍵)は別に数える
    counted = {k for k in differing if k.startswith(ADDED_PREFIXES) or k in DROPPED_KEYS}
    counted |= {k for k in differing if k.startswith(DROPPED_PREFIX)}
    # 訓練 config は model.adapter が null のままなので、パイロット用プールの config と差が出ない
    expected = set(DIFFERING_FROM_PILOT_POOL)
    if path.name in TRAIN_FILES:
        expected.discard("model.adapter")
    if CONDITION_OF_FILE[path.name] == "p2":
        # パイロット用プールの config の既定の条件が p2 なので、p2 では条件と manifest の差が出ない
        expected -= {"lesion.condition", "data.manifest"}
    assert differing - counted == expected
    assert DROPPED_KEYS <= differing and any(k.startswith(DROPPED_PREFIX) for k in differing)
    assert not any(k.startswith(DROPPED_PREFIX) for k in flatten(config))
    assert not DROPPED_KEYS & set(flatten(config))
    assert {k for k in flatten(config) if k.startswith("gonogo.pilot_design_gate.")} == {
        "gonogo.pilot_design_gate.penetrance_min",
        "gonogo.pilot_design_gate.penetrance_p2d_min",
        "gonogo.pilot_design_gate.other_error_max",
        "gonogo.pilot_design_gate.other_error_spread_max",
    }


@pytest.mark.parametrize("arm", gen.all_arms(), ids=lambda a: f"{a.condition}_s{a.seed}")
def test_an_eval_config_differs_from_its_train_config_only_in_id_and_adapter(
    arm: gen.Arm,
) -> None:
    """★評価 config = 同じ条件の訓練 config + experiment.id・model.adapter だけ。"""
    train = load_config(CONFIG_DIR / TRAIN_NAMES[arm.condition])
    evaluation = load_config(CONFIG_DIR / EVAL_NAMES[(arm.condition, arm.seed)])
    assert differing_keys(train, evaluation) == {"experiment.id", "model.adapter"}
    assert train["model"]["adapter"] is None
    assert evaluation["model"]["adapter"] == f"{gen.train_run_dir(arm)}/adapter"


def test_the_condition_and_the_manifest_follow_the_config_name() -> None:
    """lesion.condition と data.manifest は同じ条件を指す(訓練 config・評価 config とも)。"""
    for path in all_paths():
        condition = CONDITION_OF_FILE[path.name]
        config = load_config(path)
        assert config["lesion"]["condition"] == condition, path.name
        assert config["data"]["manifest"] == (
            f"data/generated/ft/exp_order6b_pilot_{condition}/manifest.json"
        ), path.name
        assert config["data"]["manifest"] in config["data"]["matched_manifests"]
        assert read_json(config["data"]["manifest"])["pool_split"]["pool_id"] == POOL_PILOT


def test_every_eval_config_points_at_the_adapter_of_a_declared_train_seed() -> None:
    """model.adapter の (条件, シード) は、その条件の訓練 config が宣言したシードのどれかである。"""
    for (condition, seed), name in EVAL_NAMES.items():
        train = load_config(CONFIG_DIR / TRAIN_NAMES[condition])
        assert seed in train["seeds"]
        adapter = load_config(CONFIG_DIR / name)["model"]["adapter"]
        assert adapter == f"runs/pilot_ft_train_{condition}_s{seed}/adapter"


# --------------------------------------------------------------------------
# 凍結前・承認前の欄
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", all_paths(), ids=lambda p: p.stem)
def test_nothing_is_frozen_or_approved_yet(path: Path) -> None:
    """★事前登録の tag・GPU 承認日・GPU 時間の見積りは null(G1-1・G1-2 と RUNNER の見積りの後)。"""
    config = load_config(path)
    assert config["experiment"]["preregistered_tag"] is None
    assert config["resources"]["human_approval_date"] is None
    assert config["resources"]["estimated_gpu_hours"] is None
    assert config["data"]["pool_id"] == POOL_PILOT
    assert config["eval"]["reference_rule"] == "p2"


def test_the_design_gate_values_are_the_04_experiment_plan_thresholds() -> None:
    """#4 0.90 / #4b 0.90 / #5 0.10 / #5b 0.05(`04_EXPERIMENT_PLAN.md:66-69` の転記。新しい値ではない)。
    #4b は #4 と別の鍵(目視確認待ちなので #4 と一緒に動かさない)。"""
    gate = load_config(all_paths()[0])["gonogo"]["pilot_design_gate"]
    assert gate == {
        "penetrance_min": 0.90,
        "penetrance_p2d_min": 0.90,
        "other_error_max": 0.10,
        "other_error_spread_max": 0.05,
    }
    assert "penetrance_min" != "penetrance_p2d_min"


# --------------------------------------------------------------------------
# 評価の範囲(ADR-099 決定5)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EVAL_NAMES.values()))
def test_the_eval_scope_drops_the_comparison_group_and_keeps_specificity_whole(name: str) -> None:
    """★比較群(T1b・T3)は解かない / 特異性対照は絞りの対象外で全件を解く / 指示付き T1 は残す。"""
    config = load_config(CONFIG_DIR / name)
    assert "comparison" not in config["eval"]["batteries"]
    assert "specificity" in config["eval"]["batteries"]
    assert task_subset.declared_task_subset(config) == ("t1", "t1_instructed", "t2")


def test_a_dry_run_solves_680_items_and_names_what_was_dropped(
    pool_dirs: dict[str, Path],  # noqa: F811
) -> None:
    """★1 評価 = 680 項目。外した 960(T1b 480・T3 480)は task_subset 欄に残り、特異性 120 は全件。"""
    report = run.dry_run(config_at(CONFIG_DIR / EVAL_NAMES[("p2", 0)], pool_dirs["pilot"]))
    assert report["n_items"] == N_EVAL_ITEMS
    subset = report["task_subset"]
    assert subset["n_items"] == N_EVAL_ITEMS
    assert subset["n_dropped"] == 960
    assert [(row["group"], row["n"]) for row in subset["solved_whole"]] == [("specificity", 120)]
