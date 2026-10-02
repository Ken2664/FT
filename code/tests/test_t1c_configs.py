"""T1c と LoRA のスケールの掃引の config 3 本(PLAN-037 I9)。

答える問い: 「3 本は、写し元の config と宣言した欄だけが違い、件数の欄は null のまま、T1c のプールを
読む宣言・掃引の宣言が各入口の検査を通り、写し元の評価プールと文面を 1 バイトも変えないか」

**モデルの重みは 1 度も読まない。ここに出る数値は実験結果ではない。**
固定する性質:
  - `exp_t1c_main.yaml` は `exp_phase1_main.yaml` と、`exp_t1c_pilot.yaml` は `exp_order6b_pilot.yaml` と、
    experiment.id・experiment.plan・eval.anchor_manifest・eval.composition・eval.freeze_tag だけが違う
  - **`eval.composition.n_per_cell` は null、`eval.freeze_tag` は null**(件数・tag の名前は S5 で人間。
    null のうちはプールの書き出しも T1c の run も止まる)
  - T1c の config は評価プールを組み直せ(`eval.batteries`・`eval.cells` は写しのまま)、件数を足せば
    写し元の config から作った T1c のプールと同じ項目になる
  - `exp_pilot_scale_ident_s0_n313.yaml` は `exp_pilot_ft_eval_ident_s0_n313.yaml` と、experiment.id・
    experiment.plan・eval.batteries・eval.task_subset・eval.scale_sweep だけが違う。s = 0・1(定義の端点)、
    アダプタは `ident`、preflight の data_checks は 7 件 PASS
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import preflight
import pytest

from code.config import ConfigError, load_config
from code.data_gen import composition_pool as cp
from code.eval import model as eval_model
from code.eval import scale_sweep, signature_gate
from code.tests.test_composition_pool import SMALL_N, source_pool, with_composition
from code.tests.test_lora_scale import train_run
from code.tests.test_order6b_pilot import differing_keys
from code.tests.test_task_subset import config_at, pool_dirs  # noqa: F401  (pool_dirs は fixture)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

MAIN_BASE = CONFIG_DIR / "exp_phase1_main.yaml"
PILOT_BASE = CONFIG_DIR / "exp_order6b_pilot.yaml"
T1C_MAIN = CONFIG_DIR / "exp_t1c_main.yaml"
T1C_PILOT = CONFIG_DIR / "exp_t1c_pilot.yaml"
SCALE_BASE = CONFIG_DIR / "exp_pilot_ft_eval_ident_s0_n313.yaml"
SCALE_CONFIG = CONFIG_DIR / "exp_pilot_scale_ident_s0_n313.yaml"

PLAN_PATH = "plans/PLAN-037-t1c-spec-breakdown-scale-sweep.md"
T1C_TEMPLATE = "{a}+{b}+{c}="

T1C_DIFFERING_KEYS = {
    "experiment.id",
    "experiment.plan",
    "eval.anchor_manifest",
    "eval.composition.prompt_template",
    "eval.composition.n_per_cell",
    "eval.freeze_tag",
}
SCALE_DIFFERING_KEYS = {
    "experiment.id",
    "experiment.plan",
    "eval.batteries",
    "eval.task_subset",
    "eval.scale_sweep.levels",
}

T1C_CASES = [
    pytest.param(MAIN_BASE, T1C_MAIN, "main", id="main"),
    pytest.param(PILOT_BASE, T1C_PILOT, "pilot", id="pilot"),
]


# --------------------------------------------------------------------------
# T1c の config
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("base", "path", "pool"), T1C_CASES)
def test_a_t1c_config_differs_from_its_base_only_in_the_declared_keys(
    base: Path, path: Path, pool: str
) -> None:
    assert differing_keys(load_config(base), load_config(path)) == T1C_DIFFERING_KEYS


@pytest.mark.parametrize(("base", "path", "pool"), T1C_CASES)
def test_the_t1c_declaration_leaves_the_count_and_the_tag_to_a_human(
    base: Path, path: Path, pool: str
) -> None:
    config = load_config(path)
    assert config["eval"]["composition"] == {"prompt_template": T1C_TEMPLATE, "n_per_cell": None}
    assert config["eval"]["freeze_tag"] is None
    assert config["experiment"]["id"] == f"exp_t1c_{pool}"
    assert config["experiment"]["plan"] == PLAN_PATH
    assert config["data"]["pool_id"] == pool
    assert config["model"]["adapter"] is None  # 素のモデルの T1c(D9 の門が通す)
    assert signature_gate.declared_freeze_tag(config) is None


@pytest.mark.parametrize(("base", "path", "pool"), T1C_CASES)
def test_the_t1c_pool_is_next_to_not_inside_the_evaluation_pool(
    base: Path, path: Path, pool: str
) -> None:
    """★既存の評価プール(`<pool_id>/`)とは別のディレクトリを指す(D4)。"""
    config = load_config(path)
    anchor = config["eval"]["anchor_manifest"]
    assert anchor == f"data/generated/battery/{cp.composition_dir_name(pool)}/manifest.json"
    assert anchor != load_config(base)["eval"]["anchor_manifest"]


@pytest.mark.parametrize(("base", "path", "pool"), T1C_CASES)
def test_a_null_count_stops_the_pool_before_anything_is_built(
    base: Path, path: Path, pool: str
) -> None:
    config = load_config(path)
    with pytest.raises(ConfigError, match="n_per_cell が null"):
        cp.load_settings(config)


@pytest.mark.parametrize(("base", "path", "pool"), T1C_CASES)
def test_the_pool_from_the_t1c_config_equals_the_pool_from_the_base_config(
    base: Path, path: Path, pool: str
) -> None:
    """★写しである証拠: 件数を足すと、写し元の config から作った T1c のプールと同じ項目になる。

    T1c の config は評価プールを組み直せる(`eval.batteries`・`eval.cells` が写しのまま)。
    """
    config = load_config(path)
    config["eval"]["composition"]["n_per_cell"] = SMALL_N
    from_copy = cp.build_composition_pool(config, source_pool(base))
    from_base = cp.build_composition_pool(with_composition(base), source_pool(base))
    assert [(item.item_id, item.operands, item.params) for item in from_copy.items] == [
        (item.item_id, item.operands, item.params) for item in from_base.items
    ]
    assert from_copy.manifest["fill"]["n_per_cell"] == SMALL_N
    assert len(from_copy.items) == 4 * SMALL_N


# --------------------------------------------------------------------------
# スケールの掃引の config(S4 (iii) の配線確認)
# --------------------------------------------------------------------------


def test_the_scale_config_differs_from_its_base_only_in_the_declared_keys() -> None:
    assert differing_keys(load_config(SCALE_BASE), load_config(SCALE_CONFIG)) == SCALE_DIFFERING_KEYS


def test_the_scale_config_declares_the_end_points_for_the_ident_adapter() -> None:
    """★0 と 1 は定義の端点(掃引の水準ではない)。アダプタは `ident` だけ(D9)。"""
    config = load_config(SCALE_CONFIG)
    assert config["eval"]["scale_sweep"] == {"levels": [0, 1]}
    assert eval_model.declared_scale_sweep_levels(config) == (0.0, 1.0)
    assert config["lesion"]["condition"] == "ident"
    assert config["eval"]["batteries"] == ["bare_sum", "word_problem"]
    assert config["eval"]["task_subset"] == ["t1", "t2"]
    assert config["experiment"]["id"] == "exp_pilot_scale_ident_s0_n313"
    assert config["experiment"]["plan"] == PLAN_PATH
    assert config["data"]["pool_id"] == "pilot"
    assert "ident" in config["model"]["adapter"]
    assert signature_gate.declared_freeze_tag(config) is None


def test_the_scale_config_keeps_the_generation_settings_of_its_base() -> None:
    """★生成設定・モデル・アダプタ・プールは写し元のまま(s = 1 が既存の ident の評価と突き合わせられる)。"""
    base, scale = load_config(SCALE_BASE), load_config(SCALE_CONFIG)
    for key in ("model", "data", "lesion", "seeds", "train"):
        assert base[key] == scale[key], key
    for key in ("elicitation", "batch_size", "do_sample", "temperature", "anchor_manifest", "cells"):
        assert base["eval"][key] == scale["eval"][key], key


def test_the_scale_config_passes_the_entrance_checks(
    pool_dirs: dict[str, Path], tmp_path: Path  # noqa: F811
) -> None:
    """★入口(`scale_sweep`)の検査を重みを読まずに通る。T1・T2 の 480 項目を解く。"""
    config = config_at(SCALE_CONFIG, pool_dirs["pilot"])
    config["model"]["adapter"] = str(train_run(tmp_path, config["lesion"]["condition"]))
    report = scale_sweep.scale_sweep_dry_run(config, run_dir_prefix=tmp_path / "runs" / "scale")
    assert report["levels"] == [0.0, 1.0]
    assert report["task_subset"]["n_items"] == 480
    assert report["gate"]["gate"] == signature_gate.REASON_IDENT_ADAPTER
    assert [Path(path).name for path in report["run_dirs"]] == ["scale_s0", "scale_s1"]


def test_the_scale_config_passes_preflight_data_checks() -> None:
    """★preflight の data_checks が 7 件すべて PASS(コミット済み manifest。items は要らない)。"""
    results = preflight.data_checks(preflight.load_config(SCALE_CONFIG))
    assert {r.name for r in results} == set(preflight.DATA_CHECK_NAMES)
    assert {r.status for r in results} == {preflight.Status.PASS}, [
        (r.name, r.status, r.detail) for r in results if r.status != preflight.Status.PASS
    ]


def test_the_fixed_offset_entrance_refuses_the_scale_config() -> None:
    from code.eval import run  # noqa: PLC0415

    with pytest.raises(ConfigError, match="scale_sweep"):
        run.dry_run(load_config(SCALE_CONFIG))


def test_no_other_config_declares_a_scale_sweep_or_a_t1c_block() -> None:
    declared: dict[str, Any] = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        eval_block = load_config(path).get("eval") or {}
        for key in ("scale_sweep", "composition"):
            if eval_block.get(key) is not None:
                declared.setdefault(key, set()).add(path.name)
    assert declared == {
        "scale_sweep": {SCALE_CONFIG.name},
        "composition": {T1C_MAIN.name, T1C_PILOT.name},
    }
