"""桁数掃引の項目生成(code/eval/battery/magnitude_sweep.py)のテスト。

答える問い: 「上限 M の域から、判別可能な加算項目を決定的に引けるか」

**ここで θ も M* も掃引の粒度も検査しない。**どれも人間の決定であり
(承認待ち #9 / #15)、コードが持っていないことこそが正しい状態である。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.eval.battery import numeric_sum
from code.eval.battery.magnitude_sweep import (
    RADIUS_PARAM,
    InsufficientPairsError,
    build_items,
    domain_size,
    load_sweep_plan,
    sweep_radii,
)
from code.lesion import reference_lesions_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

POOL_ID = "main"
SEED = 20260827


@pytest.fixture
def smoke_config() -> dict[str, Any]:
    return load_config(SMOKE_CONFIG)


@pytest.fixture
def lesions(smoke_config: dict[str, Any]) -> dict[str, Any]:
    return reference_lesions_from_config(smoke_config)


def test_domain_size_counts_the_nested_square() -> None:
    """|R(M)| = (2M+1)^2。域は絶対値で切るので負数と 0 を含む(§4.1.1)。"""
    assert domain_size(1) == 9
    assert domain_size(9) == 361
    assert domain_size(99) == 39601


def test_radius_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="radius"):
        domain_size(0)


def test_items_are_drawn_from_inside_the_radius(lesions: dict[str, Any]) -> None:
    """★引いた組はすべて |a| <= M かつ |b| <= M である。"""
    items = build_items(5, n_items=6, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    assert len(items) == 6
    for item in items:
        assert max(abs(item.operands[0]), abs(item.operands[1])) <= 5


def test_the_radius_is_recorded_on_the_item_id(lesions: dict[str, Any]) -> None:
    """★同じ (a, b) が別の M で引かれても item_id が衝突しない。

    衝突すると混合効果モデルの項目ランダム効果が壊れる(05_STATISTICS.md §3)。
    """
    items = build_items(9, n_items=4, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    for item in items:
        assert item.params[RADIUS_PARAM] == 9
        assert item.item_id.endswith(".radius9")
        assert item.group == numeric_sum.GROUP_BARE_SUM
        assert item.category == numeric_sum.T1_CATEGORY


def test_the_draw_is_deterministic(lesions: dict[str, Any]) -> None:
    """★同じシード・同じ M なら同じ項目。掃引は再現できなければ意味がない。"""
    first = build_items(9, n_items=5, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    second = build_items(9, n_items=5, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    assert [item.item_id for item in first] == [item.item_id for item in second]


def test_each_radius_gets_an_independent_sample(lesions: dict[str, Any]) -> None:
    """★M ごとに違う標本になる(シードに M を混ぜている)。

    どの M でも同じ乱数列だと、小さい M の組が大きい M にそのまま現れ、
    「M を上げたのに同じ問題を解かせている」ことになる。
    """
    small = build_items(9, n_items=6, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    large = build_items(99, n_items=6, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    assert {item.operands for item in small} != {item.operands for item in large}


def test_non_discriminating_pairs_are_dropped(lesions: dict[str, Any]) -> None:
    """★真値と規則適用値が割れない組は入らない(ADR-034)。

    smoke の参照規則には x2 が入っており、a + b = 0 の組は
    (a+b)*2 == a+b となって correct と rule を区別できない。
    """
    assert "x2" in lesions
    items = build_items(3, n_items=8, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    for item in items:
        assert numeric_sum.non_discriminating_rules(item, lesions) == []
        assert item.operands[0] + item.operands[1] != 0


def test_more_items_than_the_domain_is_refused(lesions: dict[str, Any]) -> None:
    """★|R(M)| を超える本数は取れない。少ない本数で表を作らない(§4.1.1 の3)。"""
    with pytest.raises(InsufficientPairsError, match="9 組"):
        build_items(1, n_items=10, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)


def test_an_empty_reference_rule_set_is_refused() -> None:
    """参照規則が空だと判別可能性を確かめられない(PLAN-001 §5.3)。"""
    with pytest.raises(ValueError, match="参照規則"):
        build_items(5, n_items=2, seed=SEED, pool_id=POOL_ID, reference_lesions={})


def test_zero_items_is_refused(lesions: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="n_items"):
        build_items(5, n_items=0, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)


# --------------------------------------------------------------------------
# 掃引の設定(config から来る。コードで決めない)
# --------------------------------------------------------------------------


def test_radii_are_sorted(smoke_config: dict[str, Any]) -> None:
    smoke_config["eval"]["magnitude_sweep"]["radii"] = [9, 2, 5]
    assert sweep_radii(smoke_config) == [2, 5, 9]


@pytest.mark.parametrize("radii", [[], [2, 2], [0, 5], [-1], "9"])
def test_a_broken_radius_list_is_refused(smoke_config: dict[str, Any], radii: Any) -> None:
    """★壊れた宣言はプランの誤記である。黙って直さない(skill code-style §5)。"""
    smoke_config["eval"]["magnitude_sweep"]["radii"] = radii
    with pytest.raises(ConfigError, match="radii"):
        sweep_radii(smoke_config)


def test_the_sweep_plan_comes_from_the_config(smoke_config: dict[str, Any]) -> None:
    """粒度も項目数もシードも config から来る(承認待ち #15)。"""
    plan = load_sweep_plan(smoke_config)
    declared = smoke_config["eval"]["magnitude_sweep"]
    assert plan.radii == sorted(declared["radii"])
    assert plan.n_items_per_radius == declared["n_items_per_radius"]
    assert plan.seed == declared["seed"]
    assert plan.as_dict() == {
        "radii": plan.radii,
        "n_items_per_radius": plan.n_items_per_radius,
        "seed": plan.seed,
    }


@pytest.mark.parametrize("key", ["radii", "n_items_per_radius", "seed"])
def test_an_undecided_sweep_setting_stops_the_run(
    smoke_config: dict[str, Any], key: str
) -> None:
    """★null のまま掃引を回さない。表が出ると M* の根拠として引かれる。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["magnitude_sweep"][key] = None
    with pytest.raises(ConfigError, match=key):
        load_sweep_plan(config)
