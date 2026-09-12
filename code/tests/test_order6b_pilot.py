"""順6b のパイロット用プール(PLAN-026 I1・I2。ADR-079 決定2)。

答える問い: 「パイロット用プールは、主プールと同じ手続きで、主プールと交わらない組から作られているか」

ここで固定する最重要の性質:
  - **pilot の config は本番 config と宣言した 9 欄だけが違う**(PLAN-001 §4.6 規則2「同じ手続き」)。
    ほかの欄がずれると、パイロットで測ったスループットや parse_fail_rate が本番に外挿できない
  - **pilot の評価プールは主プールと同じセル表・同じ件数**(群ごと・セルごと・閾値オフセット)
  - **コミット済みの pilot の manifest が pilot の config から再現できる**
  - **K_pilot と K_main が交わらない**(PLAN-001 §4.6 の 2026-08-22 訂正)。preflight は同じ条件名の
    manifest を 1 つの config に並べられない(`load_ft_manifests` が止める)ので、ここで照合する
  - **pilot・本番の config で preflight の data_checks がすべて PASS**(検査6・8・非交差を含む)

**本番 config を直したら、pilot の config にも同じ変更を入れること。**入れ忘れるとここが落ちる。
評価プールどうしの積が空であることのテストは `test_pool.py`(PLAN-001 §4.6 規則3 の置き場所)。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import preflight
import pytest

from code.config import load_config
from code.data_gen import eval_pool
from code.data_gen.pool import POOL_MAIN, POOL_PILOT

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"
PILOT_CONFIG = REPO_ROOT / "configs" / "exp_order6b_pilot.yaml"

# pilot の config が本番と違ってよい欄(configs/exp_order6b_pilot.yaml の冒頭の注記)。
PILOT_DIFFERING_KEYS = {
    "experiment.id",
    "experiment.plan",
    "data.pool_id",
    "data.manifest",
    "data.matched_manifests",
    "eval.anchor_manifest",
    "eval.counterpart_manifest",
    "resources.estimated_gpu_hours",
    "resources.human_approval_date",
}


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """入れ子の config を `a.b.c` の鍵の辞書にする(リストは値としてそのまま比べる)。"""
    flat: dict[str, Any] = {}
    for key, value in tree.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(flatten(value, f"{dotted}."))
        else:
            flat[dotted] = value
    return flat


def differing_keys(first: Mapping[str, Any], second: Mapping[str, Any]) -> set[str]:
    a, b = flatten(first), flatten(second)
    return {key for key in set(a) | set(b) if a.get(key, object()) != b.get(key, object())}


def read_json(declared: str) -> dict[str, Any]:
    return json.loads((REPO_ROOT / declared).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# config(PLAN-026 §4.1 手順1)
# --------------------------------------------------------------------------


def test_pilot_config_differs_only_in_the_declared_keys() -> None:
    """★pilot の config は本番と宣言した 9 欄だけが違う(PLAN-001 §4.6 規則2)。"""
    assert differing_keys(load_config(MAIN_CONFIG), load_config(PILOT_CONFIG)) == (
        PILOT_DIFFERING_KEYS
    )


def test_pilot_config_points_at_the_pilot_side_and_is_not_approved() -> None:
    """pilot の config は pilot の成果物だけを指し、相手に主プールを宣言する。GPU 承認はまだ無い。"""
    main, pilot = load_config(MAIN_CONFIG), load_config(PILOT_CONFIG)
    assert pilot["data"]["pool_id"] == POOL_PILOT
    ft = [read_json(entry) for entry in pilot["data"]["matched_manifests"]]
    assert {m["pool_split"]["pool_id"] for m in ft} == {POOL_PILOT}
    assert pilot["data"]["manifest"] in pilot["data"]["matched_manifests"]
    assert read_json(pilot["eval"]["anchor_manifest"])["pool_id"] == POOL_PILOT
    # 非交差の相手は互いを指す(PLAN-001 §4.6 規則3)。
    assert pilot["eval"]["counterpart_manifest"] == main["eval"]["anchor_manifest"]
    assert main["eval"]["counterpart_manifest"] == pilot["eval"]["anchor_manifest"]
    # 順6 の承認日を写さない(PLAN-026 §11 の承認は実装・dry-run・§5 の凍結の後)。
    assert pilot["resources"]["human_approval_date"] is None


# --------------------------------------------------------------------------
# FT データ(PLAN-026 §4.1 手順2)
# --------------------------------------------------------------------------


def test_training_coverages_of_pilot_and_main_do_not_intersect() -> None:
    """★K_pilot ∩ K_main = ∅(PLAN-001 §4.6 の訂正 / PLAN-002 §4.7)。5 条件すべてで。"""
    main, pilot = load_config(MAIN_CONFIG), load_config(PILOT_CONFIG)
    main_ft = [read_json(entry) for entry in main["data"]["matched_manifests"]]
    pilot_ft = [read_json(entry) for entry in pilot["data"]["matched_manifests"]]
    assert len(main_ft) == len(pilot_ft)
    main_k = {tuple(pair) for m in main_ft for pair in m["coverage"]["pairs"]}
    pilot_k = {tuple(pair) for m in pilot_ft for pair in m["coverage"]["pairs"]}
    assert not (main_k & pilot_k)
    # 5 条件は同じ K を共有する(PLAN-002 §3.4)。和集合が 1 条件分の大きさに戻る
    assert len(pilot_k) == pilot_ft[0]["coverage"]["coverage_k"]


# --------------------------------------------------------------------------
# 評価プール(PLAN-026 §4.1 手順3)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pilot_pool() -> eval_pool.EvalPool:
    """pilot の config からパイロット用プールを組む(約 5 秒)。"""
    return eval_pool.build(load_config(PILOT_CONFIG))


def test_pilot_pool_matches_the_committed_manifest(pilot_pool: eval_pool.EvalPool) -> None:
    """★コミット済みの pilot の manifest が pilot の config から再現できる。"""
    committed = read_json(load_config(PILOT_CONFIG)["eval"]["anchor_manifest"])
    committed.pop("files")
    rebuilt = json.loads(json.dumps(pilot_pool.manifest, ensure_ascii=False))
    assert rebuilt == committed


def test_pilot_pool_items_all_declare_the_pilot_pool(pilot_pool: eval_pool.EvalPool) -> None:
    """項目の pool_id は pilot だけ(run.py の照合と T2 の場面割当が pool_id に効く)。"""
    assert {item.pool_id for item in pilot_pool.items} == {POOL_PILOT}


def test_pilot_pool_uses_the_same_cells_and_counts_as_the_main_pool() -> None:
    """★同じ手続き(PLAN-001 §4.6 規則2)。違うのは引いた順序対だけである。

    **件数は組合せ論的な帰結であって実験結果ではない**(CLAUDE.md §2)。
    """
    main = read_json(load_config(MAIN_CONFIG)["eval"]["anchor_manifest"])
    pilot = read_json(load_config(PILOT_CONFIG)["eval"]["anchor_manifest"])
    assert (main["pool_id"], pilot["pool_id"]) == (POOL_MAIN, POOL_PILOT)
    for key in ("cells_declared", "n_items_by_cell", "n_items_by_group", "threshold_offsets"):
        assert pilot["fill"][key] == main["fill"][key], key
    assert pilot["n_pairs"] == main["n_pairs"]
    assert pilot["seed"] == main["seed"]
    assert pilot["prompt_format"] == main["prompt_format"]
    assert pilot["reference_rules"] == main["reference_rules"]
    assert pilot["pairs_hash"] != main["pairs_hash"]


# --------------------------------------------------------------------------
# preflight(PLAN-026 §4.1 手順4・5)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("config_path", [PILOT_CONFIG, MAIN_CONFIG], ids=["pilot", "main"])
def test_data_checks_pass_on_the_committed_pools(config_path: Path) -> None:
    """★pilot・本番の config で data_checks がすべて PASS(検査6・8・非交差を含む)。"""
    results = preflight.data_checks(preflight.load_config(config_path))
    assert {r.name for r in results} == set(preflight.DATA_CHECK_NAMES)
    assert {r.status for r in results} == {preflight.Status.PASS}, [
        (r.name, r.detail) for r in results
    ]
