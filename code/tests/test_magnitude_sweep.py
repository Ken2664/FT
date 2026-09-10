"""桁数掃引の項目生成(code/eval/battery/magnitude_sweep.py)のテスト。

答える問い: 「上限 M の域から、判別可能な加算項目を決定的に引けるか」

**ここで θ も M* も検査しない。**θ の値は人間が決め(ADR-070)、規則2 を当てて
M* を置くのも人間である。コードが持っていないことこそが正しい状態である。
**Q(M) の腕(ADR-071)は、config が ADR からの導出と一致しているかだけを検査する。**
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from code.config import ConfigError, load_config
from code.data_gen.pool import COVERAGE_EXTRAP_MAGNITUDE, label_main_coverage
from code.eval.battery import numeric_sum
from code.eval.battery.magnitude_sweep import (
    RADIUS_PARAM,
    SHELL_DEFINITION_QUADRANT,
    SHELL_PARAM,
    InsufficientPairsError,
    build_items,
    build_quadrant_items,
    derive_shell_radii,
    domain_pairs,
    domain_size,
    in_domain,
    load_shell_plan,
    load_sweep_plan,
    quadrant_pairs,
    quadrant_sizes,
    sweep_radii,
    sweep_seeds,
)
from code.lesion import reference_lesions_from_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"

POOL_ID = "main"
SEED = 20260827

# smoke の主域の半径(data.train_domain_max)。Q(M) は M > 9 でしか空でない。
SMOKE_MAIN_RADIUS = 9

# ★ADR-071 決定2「現行の 13,000 項目を 1 文字も変えない」の固定点。
# 2026-09-10、Q(M) の腕を足す**前**の `build_items` で、configs/exp_phase1_main.yaml の
# 13 水準 × 5 シード × 200 件の item_id を宣言順(水準 → シード)に並べて畳んだ sha256。
# **これは組合せ論的な出力であって実験結果ではない。**変わったら、一様抽出の腕が
# 変わった(= ADR-071 決定2 に反する)か、乱数の実装が変わったかのどちらかである。
UNIFORM_ARM_SHA256 = "afb150438e5159f8efb3ead4b90d3ffbdd43d08eff4339fcf5543b431d71d4cc"


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


def test_the_sweep_does_not_apply_the_evaluation_operand_exclusion(
    lesions: dict[str, Any],
) -> None:
    """★★掃引に被演算子 1 の除外を掛けない(ADR-035 決定3 の適用範囲)。

    決定3 が掛ける先は**評価項目**である。桁数掃引は評価プールではなく
    `M*` を決めるための別の項目集合であり、抽出仕様は ADR-041 決定5 が
    凍結している(格子 / 1点あたり 200 項目 / 5シード)。ここに除外を足すと
    **1点あたりの母集団が M ごとに違う割合で削られ**、M 間の `correct_rate`
    比較が成立しなくなる。実験条件の変更であって実装の裁量ではない
    (`CLAUDE.md` §8)。

    半径 3 の R(M) は 9 組で、そのうち 5 組が被演算子 1 を含む。全数を
    引けば必ず現れる —— 現れなくなったら除外が紛れ込んでいる。
    """
    items = build_items(3, n_items=9, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions)
    assert len(items) == 9
    assert any(1 in item.operands for item in items)


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


def test_seeds_keep_their_declared_order(smoke_config: dict[str, Any]) -> None:
    """★抽出シードは並べ替えない —— metrics.json のシード別の列を宣言順で読めるように。

    M の列と違い、シードには大小の意味が無い(ADR-041 決定5)。
    """
    smoke_config["eval"]["magnitude_sweep"]["seeds"] = [9, 2, 5]
    assert sweep_seeds(smoke_config) == [9, 2, 5]


@pytest.mark.parametrize("seeds", [[], [2, 2], [1, 1, 2], "9"])
def test_a_broken_seed_list_is_refused(smoke_config: dict[str, Any], seeds: Any) -> None:
    """★空 / 重複はプランの誤記である。黙って直さない(skill code-style §5)。"""
    smoke_config["eval"]["magnitude_sweep"]["seeds"] = seeds
    with pytest.raises(ConfigError, match="seeds"):
        sweep_seeds(smoke_config)


def test_the_sweep_plan_comes_from_the_config(smoke_config: dict[str, Any]) -> None:
    """粒度も項目数もシード群も config から来る(承認待ち #15 / ADR-041 決定5)。"""
    plan = load_sweep_plan(smoke_config)
    declared = smoke_config["eval"]["magnitude_sweep"]
    assert plan.radii == sorted(declared["radii"])
    assert plan.n_items_per_radius == declared["n_items_per_radius"]
    assert plan.seeds == declared["seeds"]
    assert plan.as_dict() == {
        "radii": plan.radii,
        "n_items_per_radius": plan.n_items_per_radius,
        "seeds": plan.seeds,
    }


@pytest.mark.parametrize("key", ["radii", "n_items_per_radius", "seeds"])
def test_an_undecided_sweep_setting_stops_the_run(
    smoke_config: dict[str, Any], key: str
) -> None:
    """★null のまま掃引を回さない。表が出ると M* の根拠として引かれる。"""
    config = copy.deepcopy(smoke_config)
    config["eval"]["magnitude_sweep"][key] = None
    with pytest.raises(ConfigError, match=key):
        load_sweep_plan(config)


# --------------------------------------------------------------------------
# 一様抽出の腕は変わっていない(ADR-071 決定2)
# --------------------------------------------------------------------------


def test_the_uniform_arm_is_byte_identical_to_before_adr_071() -> None:
    """★現行の 13,000 項目は 1 文字も変わっていない(ADR-071 決定2)。

    本番 config の格子・項目数・シード・参照規則で `build_items` を回し、
    Q(M) の腕を足す前に記録した item_id の並びと比べる。
    """
    config = load_config(MAIN_CONFIG)
    plan = load_sweep_plan(config)
    lesions = reference_lesions_from_config(config)
    digest = hashlib.sha256()
    n_items = 0
    for radius in plan.radii:
        for seed in plan.seeds:
            items = build_items(
                radius,
                n_items=plan.n_items_per_radius,
                seed=seed,
                pool_id=config["data"]["pool_id"],
                reference_lesions=lesions,
            )
            n_items += len(items)
            digest.update("\n".join(item.item_id for item in items).encode())
            digest.update(b"|")
    assert n_items == 13_000
    assert digest.hexdigest() == UNIFORM_ARM_SHA256


# --------------------------------------------------------------------------
# Q(M) の腕(ADR-071 決定1・決定2・決定3)
# --------------------------------------------------------------------------


def test_domain_pairs_enumerate_exactly_r_of_m() -> None:
    """R(M) の列挙は `domain_size` と同じ個数で、すべて `in_domain` を満たす。"""
    for radius in (1, 3, 9):
        pairs = list(domain_pairs(radius))
        assert len(pairs) == len(set(pairs)) == domain_size(radius)
        assert all(in_domain(pair, radius) for pair in pairs)
        assert not in_domain((radius + 1, 0), radius)
        assert not in_domain((0, -radius - 1), radius)


def test_quadrant_pairs_are_exactly_the_extrap_magnitude_pairs() -> None:
    """★Q(M) = R(M) のうち `label_main_coverage` が `extrap_magnitude` を返す組(全数照合)。

    漏れ(Q にあるべき組が無い)と混入(Q に無いはずの組がある)の両方を見る。
    """
    radius = 15
    quadrant = set(quadrant_pairs(radius, main_radius=SMOKE_MAIN_RADIUS))
    expected = {
        pair
        for pair in domain_pairs(radius)
        if label_main_coverage(pair, frozenset(), SMOKE_MAIN_RADIUS) == COVERAGE_EXTRAP_MAGNITUDE
    }
    assert quadrant == expected
    assert len(quadrant) == (radius - SMOKE_MAIN_RADIUS) ** 2
    # 負の被演算子と片側だけ域外の組は入らない(★F123)
    assert (-15, -15) not in quadrant and (15, 3) not in quadrant and (15, 10) in quadrant


@pytest.mark.parametrize("radius", range(1, SMOKE_MAIN_RADIUS + 1))
def test_the_quadrant_is_empty_up_to_the_main_radius(radius: int) -> None:
    """★罠: `(M - main_radius)^2` は M < main_radius でも正になる。Q(M) は空である。"""
    assert quadrant_pairs(radius, main_radius=SMOKE_MAIN_RADIUS) == []
    if radius < SMOKE_MAIN_RADIUS:
        assert (radius - SMOKE_MAIN_RADIUS) ** 2 > 0


def test_the_quadrant_does_not_depend_on_the_coverage_pairs() -> None:
    """★`extrap_magnitude` の判定は K に依存しない(空集合を渡してよい根拠)。

    `label_coverage` は extrap を K より先に判定して返す。K をどう選んでも
    Q(M) が変わらないことを、訓練域を全部 K に入れた極端な場合で確かめる。
    """
    everything = frozenset(
        (a, b)
        for a in range(1, SMOKE_MAIN_RADIUS + 1)
        for b in range(1, SMOKE_MAIN_RADIUS + 1)
    )
    radius = 12
    with_k = [
        pair
        for pair in domain_pairs(radius)
        if label_main_coverage(pair, everything, SMOKE_MAIN_RADIUS) == COVERAGE_EXTRAP_MAGNITUDE
    ]
    assert with_k == quadrant_pairs(radius, main_radius=SMOKE_MAIN_RADIUS)


def test_quadrant_items_are_drawn_from_q_of_m(lesions: dict[str, Any]) -> None:
    """★Q(M) の腕の項目はすべて Q(M) に入り、重複せず、殻の名前を item_id に載せる。"""
    radius = 15
    quadrant = set(quadrant_pairs(radius, main_radius=SMOKE_MAIN_RADIUS))
    items = build_quadrant_items(
        radius, n_items=20, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions,
        main_radius=SMOKE_MAIN_RADIUS,
    )
    assert len(items) == 20
    assert all(item.operands in quadrant for item in items)
    assert len({item.item_id for item in items}) == 20
    for item in items:
        assert item.params == {RADIUS_PARAM: radius, SHELL_PARAM: SHELL_DEFINITION_QUADRANT}


def test_quadrant_items_are_deterministic_and_move_with_the_seed(
    lesions: dict[str, Any],
) -> None:
    """★同じシードなら同じ項目、シードを変えれば別の項目(5 通りの独立な抽出)。"""
    kwargs: dict[str, Any] = {
        "n_items": 10, "pool_id": POOL_ID, "reference_lesions": lesions,
        "main_radius": SMOKE_MAIN_RADIUS,
    }
    first = build_quadrant_items(15, seed=0, **kwargs)
    again = build_quadrant_items(15, seed=0, **kwargs)
    other = build_quadrant_items(15, seed=1, **kwargs)
    assert [item.item_id for item in first] == [item.item_id for item in again]
    assert [item.operands for item in first] != [item.operands for item in other]


def test_the_whole_quadrant_can_be_drawn(lesions: dict[str, Any]) -> None:
    """★|Q(M)| 件ちょうどなら全数が引ける(打ち切りは Q(M) を全部見たとき)。"""
    radius = 12
    size = (radius - SMOKE_MAIN_RADIUS) ** 2
    items = build_quadrant_items(
        radius, n_items=size, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions,
        main_radius=SMOKE_MAIN_RADIUS,
    )
    assert sorted(item.operands for item in items) == quadrant_pairs(
        radius, main_radius=SMOKE_MAIN_RADIUS
    )


def test_more_items_than_the_quadrant_is_refused(lesions: dict[str, Any]) -> None:
    """★|Q(10)| = 1 から 4 件は引けない(本番の M = 100 / 110 と同じ形)。少なく引かない。"""
    with pytest.raises(InsufficientPairsError, match="1 組"):
        build_quadrant_items(
            10, n_items=4, seed=SEED, pool_id=POOL_ID, reference_lesions=lesions,
            main_radius=SMOKE_MAIN_RADIUS,
        )


def test_shell_radii_are_derived_from_the_quadrant_sizes() -> None:
    """★判定水準は |Q(M)| >= n の格子点。台地は Q(M) が空なので入らない(罠を踏まない)。"""
    radii = [2, 5, 9, 10, 12, 15]
    sizes = quadrant_sizes(radii, main_radius=SMOKE_MAIN_RADIUS)
    assert sizes == {2: 0, 5: 0, 9: 0, 10: 1, 12: 9, 15: 36}
    assert derive_shell_radii(sizes, n_items=4) == [12, 15]


def test_the_main_config_matches_the_derivation() -> None:
    """★本番 config の shell_radii / shell_judgement_radii は ADR-071 からの導出と一致する。

    `load_shell_plan` が突き合わせ、ずれていれば止まる。|Q(M)| は組合せ論の計数である。
    """
    config = load_config(MAIN_CONFIG)
    shell = load_shell_plan(config, load_sweep_plan(config))
    assert shell.definition == SHELL_DEFINITION_QUADRANT
    assert shell.radii == shell.judgement_radii == [125, 150, 175, 200, 300, 500, 999]
    assert shell.n_items == 200
    assert shell.main_radius == 99
    assert shell.population_sizes == {
        radius: (radius - 99) ** 2 for radius in shell.radii
    }
    assert shell.population_sizes[125] == 676


def test_the_main_config_m_star_is_traced_to_the_sweep_run() -> None:
    """★ADR-074 決定1: 本番 config の M* は順5 の run から規則どおりに出た値である。

    答える問い: 「config の `extrapolation_radius` は決め打ちではなく、名指しした run の
    腕2(`quadrant`)に ADR-041 決定3 規則2 を当てた結果と一致しているか」

    どの判定水準も θ を割らなかったので、M* は判定水準の上端(上側打ち切り)である。
    run の `metrics.json` はコミット済み(`CLAUDE.md` §5)なので GPU なしで照合できる。
    """
    config = load_config(MAIN_CONFIG)
    shell = load_shell_plan(config, load_sweep_plan(config))
    run_id = config["eval"]["extrapolation_run_id"]
    metrics_path = REPO_ROOT / "runs" / run_id / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    theta = config["eval"]["magnitude_sweep"]["theta"]
    by_radius = metrics["quadrant"]["correct_rate_by_radius"]
    judged = [by_radius[str(radius)] for radius in shell.judgement_radii]
    assert min(judged) >= theta  # どの水準も割らない → 規則2 の「1 つ下」は立たない
    assert config["eval"]["extrapolation_radius"] == max(shell.judgement_radii) == 999


def _shell_config(smoke_config: dict[str, Any]) -> dict[str, Any]:
    """smoke config に Q(M) の腕の欄を足す(ADR-071 と同じ形。値は小さい)。"""
    config = copy.deepcopy(smoke_config)
    section = config["eval"]["magnitude_sweep"]
    section["radii"] = [2, 5, 9, 10, 12, 15]
    section["shell_definition"] = SHELL_DEFINITION_QUADRANT
    section["shell_n_items"] = section["n_items_per_radius"]
    section["shell_radii"] = [12, 15]
    section["shell_judgement_radii"] = [12, 15]
    return config


def test_a_consistent_shell_config_loads(smoke_config: dict[str, Any]) -> None:
    config = _shell_config(smoke_config)
    shell = load_shell_plan(config, load_sweep_plan(config))
    assert shell.radii == shell.judgement_radii == [12, 15]
    assert shell.population_sizes == {12: 9, 15: 36}
    assert shell.as_dict()["population_sizes"] == {"12": 9, "15": 36}


def test_a_config_without_the_shell_arm_is_refused(smoke_config: dict[str, Any]) -> None:
    """★smoke.yaml は shell_* を持たない。判定の材料が無い掃引は回さない。"""
    with pytest.raises(ConfigError, match="shell_definition"):
        load_shell_plan(smoke_config, load_sweep_plan(smoke_config))


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("shell_definition", "grid", "実装していない"),
        ("shell_definition", None, "shell_definition"),
        ("shell_n_items", 3, "n_items_per_radius"),
        ("shell_radii", [2, 5, 12, 15], "導出値"),
        ("shell_radii", [15], "導出値"),
        ("shell_radii", [], "shell_radii"),
        ("shell_radii", None, "shell_radii"),
        ("shell_judgement_radii", [15], "導出値"),
        ("shell_judgement_radii", [12, 12, 15], "重複"),
    ],
)
def test_a_shell_config_that_contradicts_adr_071_is_refused(
    smoke_config: dict[str, Any], key: str, value: Any, message: str
) -> None:
    """★config が ADR-071 の 3 決定と食い違ったら止める(黙って直さない)。

    `[2, 5, 12, 15]` は ★罠(`(M-9)^2 >= 4` で導いた列)である。
    `shell_n_items` を n_items_per_radius と違う数にするのは新しい閾値を作ることになる。
    """
    config = _shell_config(smoke_config)
    config["eval"]["magnitude_sweep"][key] = value
    with pytest.raises(ConfigError, match=message):
        load_shell_plan(config, load_sweep_plan(config))


def test_a_grid_without_any_drawable_quadrant_is_refused(smoke_config: dict[str, Any]) -> None:
    """★どの水準も Q(M) から n 件引けない config は止める(累積の表だけが出るのを防ぐ)。"""
    config = _shell_config(smoke_config)
    config["eval"]["magnitude_sweep"]["radii"] = [2, 5, 9, 10]
    with pytest.raises(ConfigError, match="引けない"):
        load_shell_plan(config, load_sweep_plan(config))
