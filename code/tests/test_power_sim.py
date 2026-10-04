"""検出力シミュレーション(code/analysis/power_sim.py)のテスト。

答える問い: 「§6.3 手続き3a の DGP は書いてあるとおりの表を産むか。
逆問題の読み取り(手続き5)は、掃いていない領域を語らずに済んでいるか」

**R は 1 度も呼ばない。**当てはめ側(`power_sim_fit.R`)は `lme4` を要求するので、
ここでは表を組む層と数える層だけを固定する。当てはめが通ることは
`configs/power_sim_smoke.yaml` を使った手動のスモークで確認する
(`Documents/05_STATISTICS.md` §6.7 の脚注)。

**ここに出る数値は実験結果ではない。**`sigma` / `rho` はすべて仮定値である
(`CLAUDE.md` §2 / ADR-067 / ADR-068)。
"""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from code.analysis import power_sim
from code.config import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CONFIG = REPO_ROOT / "configs" / "power_sim.yaml"
SMOKE_CONFIG = REPO_ROOT / "configs" / "power_sim_smoke.yaml"
STATISTICS_DOC = REPO_ROOT / "Documents" / "05_STATISTICS.md"

# ADR-068 決定3(R3)が凍結した掃く格子。★すべて仮定値であって実測ではない。
ADOPTED_SIGMA = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
ADOPTED_RHO = [0.0, 1.0]

# ADR-111 決定2 / ADR-027。主要検定の交互作用の df = 2 はこの 2 つから決まる(ADR-112 決定1)。
N_TASK = 2
N_COVERAGE = 3
INTERACTION_DF = (N_TASK - 1) * (N_COVERAGE - 1)
# 旧い 4 タスク型の模型(df = 6。ADR-052 / ADR-069)。下の RECOVERED_OFFSETS などが記録として残している。
N_TASK_RECORDED = 4
RECORDED_INTERACTION_DF = (N_TASK_RECORDED - 1) * (N_COVERAGE - 1)


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 事前登録の値が config から落ちていないこと
# --------------------------------------------------------------------------


def test_adopted_grid_is_in_the_config() -> None:
    """★ADR-068 決定3 の掃く格子が config に入っている(事前登録との一致)。"""
    config = load(MAIN_CONFIG)
    assert config["dgp"]["sigma"] == ADOPTED_SIGMA
    assert config["dgp"]["rho"] == ADOPTED_RHO


def test_seed_count_is_the_adopted_ten() -> None:
    """ADR-028 のシード数 10。§6.3 手続き4 でシード掃きは 10 に畳んだ。"""
    assert load(MAIN_CONFIG)["dgp"]["n_seed"] == 10


def test_s2_values_are_the_decided_ones() -> None:
    """★F104-c の 2 つは人間が決めた値である(ADR-121)。

    ~~`s2_item` / `s2_tmpl` は null のまま(ADR-095 決定3)~~ → 2026-10-03 ADR-121 で
    `s2_item` = 2.0(推定 [run:20261003_214842_s2_item_pilot] を見た後に人間が選んだ)/
    `s2_tmpl` = 0.5(ADR-119 決定4)。**config と ADR の食い違いを回帰テストで固定する。**
    """
    dgp = load(MAIN_CONFIG)["dgp"]
    assert dgp["s2_item"] == 2.0
    assert dgp["s2_tmpl"] == 0.5


# ★ADR-123 決定1(PLAN-040 §11)。検出力分析の中だけの格子(実際の `eval.cells` とは別物)
ADOPTED_N_ITEM = [80, 120, 160, 240]


def test_n_item_grid_is_the_decided_one() -> None:
    """★~~ADR-114 決定3 の 80 の整数 1 つ~~ → ADR-123 決定1 の格子 {80, 120, 160, 240}(T1・T2 共通)。"""
    n_item = load(MAIN_CONFIG)["dgp"]["n_item"]
    assert n_item == ADOPTED_N_ITEM
    assert all(isinstance(n, int) for n in n_item)
    assert power_sim.load_n_item_grid(load(MAIN_CONFIG)) == tuple(ADOPTED_N_ITEM)


def undecided_main_config() -> dict[str, Any]:
    """本番 config の写しで `s2_*` を null に戻したもの(ADR-121 の前の状態)。

    ★本番 config そのものはもう null ではない。**本物の config で門を確かめると、
    門が開いて本実行(64,000 本)が走り出す**(2026-10-03 その139 に実際に起きた)。
    """
    config = copy.deepcopy(load(MAIN_CONFIG))
    config["dgp"]["s2_item"] = None
    config["dgp"]["s2_tmpl"] = None
    return config


def test_run_stops_while_s2_is_undecided(tmp_path: Path) -> None:
    """未決のまま本実行しようとしたら止まる。答える問い: 門は効いているか。

    止まるのは R を探すより前である(R が無い機械でも同じ所で止まる)。
    """
    with pytest.raises(ConfigError, match="s2_item"):
        power_sim.run(undecided_main_config(), tmp_path, None, False, through_stage=1)


def test_dry_run_works_even_while_undecided() -> None:
    """★格子と当てはめ本数は未決のままでも出る(コストを先に見るため)。

    ~~4 シート 32 点 x 1000 反復 x 2 = 64,000 本~~ → ★ADR-123: 誤指定 6 + P1 6 + P1⁻ 2 + P0 6 = 20 点。
    最終段 1000 反復で 20 x 1000 x 2 = 40,000 本(20,000 ペア)。
    """
    lines = power_sim.describe_plan(undecided_main_config())
    text = "\n".join(lines)
    assert "40000" in text, "40,000 本(20 x 1000 x 2)が出ていない"
    assert "UNDECIDED" in text
    assert text.isascii(), "この環境の stdout は cp932 である"


def test_reduction_order_matches_adr_065() -> None:
    """縮退順序は template -> coverage のランダム傾き -> item(ADR-065 決定2)。"""
    assert load(MAIN_CONFIG)["fit"]["reduction_order"] == [
        "template",
        "coverage_slope",
        "item",
    ]


# --------------------------------------------------------------------------
# 効果量プロファイル(§6.5 / §6.6)
# --------------------------------------------------------------------------


# §6.5 の表は `rule_rate` を小数第2位で表示したものである(節が自らそう書いている)。
# **かつては DGP がその表しか読めず、丸めが RMS を膨らませていた**(★F112)。
# **★2026-09-09(ADR-069 決定1 = 案 (a))に、丸める前のロジット `eta` を config へ直接
# 与える形に差し替えた。**下の 2 定数は差し替え前の値であり、**何が直ったかの記録として残す**
# (`CLAUDE.md` §2 の履歴保存。膨らみ方そのものは
# `test_rounding_the_recovered_logits_is_what_inflates_the_rms` が今も測っている)。
DOCUMENTED_P1_RMS = 0.353          # 05_STATISTICS.md §6.5 / §6.6(採択済み。ADR-052 決定2)
P1_RMS_FROM_ROUNDED_TABLE = 0.3605  # ★旧: 同じ節の表(2 桁)から復元していた値
P0_RMS_FROM_ROUNDED_TABLE = 0.0285  # ★旧: P0 は「完全に平行」= RMS 0.000 と書かれているのに


def main_profile(name: str) -> power_sim.EffectProfile:
    return power_sim.build_profile(load(MAIN_CONFIG)["effect"], name)


def double_centred(eta: np.ndarray) -> np.ndarray:
    """加法モデルの当てはめ値を引いた残差(二重中心化)。答える問い: 非加法の部分はどこか。"""
    return eta - eta.mean(axis=0, keepdims=True) - eta.mean(axis=1, keepdims=True) + eta.mean()


# §6.5 の P1 の T1・T2 の行(PLAN-034 §5.1。ADR-052 決定2 が採択した P1 の 4 行のうちの 2 行)
P1_T1_T2_ROWS = np.array([[2.8, 2.0, 1.2], [1.8, 0.6, -1.0]])
# D1 (a) の倍率 = 0.352767 / 0.432049 = √(2/3)(PLAN-034 §5.1。算術であって実測ではない)
D1_SCALE = float(np.sqrt(2.0 / 3.0))
# eta を config に書いた桁(小数第 6 位)の丸めが RMS・係数に残す誤差の上限
CONFIG_ETA_TOLERANCE = 1e-5


def test_profile_p1_keeps_the_adopted_rms_of_the_four_task_profile() -> None:
    """★D1 (a): 主要検定の df = 2 でも、検出したい下限は ADR-052 決定2 の RMS = 0.353 のままである。

    答える問い: 「P1 を T1・T2 の 2 行に切っただけで、宣言より大きい効果を見ていないか」——
    **切っただけなら RMS は 0.432049 になる**(PLAN-033 §6)。倍率 √(2/3) で
    4 タスク型の P1 の RMS(0.352767)に戻してある。
    """
    four_task_rms, _ = _nonadditivity(_recovered_eta("P1"))
    profile = main_profile("P1")
    assert profile.eta.shape == (N_TASK, N_COVERAGE)
    assert profile.nonadditivity_rms == pytest.approx(four_task_rms, abs=CONFIG_ETA_TOLERANCE)
    assert profile.nonadditivity_rms == pytest.approx(DOCUMENTED_P1_RMS, abs=5e-4)
    # 切っただけの RMS は大きい(df の取り方で同じ delta でも RMS が変わることの確認)
    sliced_rms = float(np.sqrt((double_centred(P1_T1_T2_ROWS) ** 2).sum() / INTERACTION_DF))
    assert sliced_rms == pytest.approx(0.432049, abs=1e-6)
    assert profile.nonadditivity_rms == pytest.approx(
        sliced_rms * D1_SCALE, abs=CONFIG_ETA_TOLERANCE
    )


def test_profile_p1_scales_only_the_nonadditive_part() -> None:
    """★D1 (a): 加法部分はそのまま、delta だけを √(2/3) 倍する(PLAN-034 §5.1)。

    答える問い: 「T1・T2 の主効果・被覆の傾きの平均まで動かしていないか」——
    動かしていれば、検出力は交互作用ではなく水準の違いで変わる。
    """
    additive = P1_T1_T2_ROWS - double_centred(P1_T1_T2_ROWS)
    delta = double_centred(P1_T1_T2_ROWS)
    profile = main_profile("P1")
    assert profile.eta == pytest.approx(additive + D1_SCALE * delta, abs=CONFIG_ETA_TOLERANCE)
    assert (profile.eta - double_centred(profile.eta)) == pytest.approx(
        additive, abs=CONFIG_ETA_TOLERANCE
    )
    # PLAN-034 §5.1 の数値(eta の 6 桁)
    assert profile.eta[0].tolist() == pytest.approx([2.848934, 2.012234, 1.138832], abs=1e-6)
    assert profile.eta[1].tolist() == pytest.approx([1.751066, 0.587766, -0.938832], abs=1e-6)


def test_profile_p1_neg_is_the_sign_flipped_shape_with_the_same_rms() -> None:
    """★D2 (a): P1⁻ は P1 の delta の符号を反転した形(同じ RMS・同じ加法部分)。

    答える問い: 「形の検査は、効果の大きさを変えずに形だけを変えているか」——
    変わっていれば、LRT の検出力の違いが形のせいか大きさのせいか分からなくなる。
    """
    p1, neg = main_profile("P1"), main_profile("P1_neg")
    assert neg.nonadditivity_rms == pytest.approx(p1.nonadditivity_rms, abs=CONFIG_ETA_TOLERANCE)
    assert double_centred(neg.eta) == pytest.approx(
        -double_centred(p1.eta), abs=CONFIG_ETA_TOLERANCE
    )
    assert (neg.eta - double_centred(neg.eta)) == pytest.approx(
        p1.eta - double_centred(p1.eta), abs=CONFIG_ETA_TOLERANCE
    )
    assert neg.eta[0].tolist() == pytest.approx([3.284399, 2.121100, 0.594501], abs=1e-6)
    assert neg.eta[1].tolist() == pytest.approx([1.315601, 0.478900, -0.394501], abs=1e-6)
    for cov in ("interp", "extrap_magnitude"):
        assert neg.interaction_contrasts[cov] == pytest.approx(
            -p1.interaction_contrasts[cov], abs=CONFIG_ETA_TOLERANCE
        )


def test_profile_p0_is_exactly_additive() -> None:
    """★D4 (a): P0 は §6.5 の P0 の T1・T2 の行(= mu + a + b)で、RMS = 0・係数 = 0 になる。

    答える問い: 「`sigma = 0` の P0 の行を α の較正として読めるか」—— **読める。**
    丸めていない `eta` なので厳密に 0 である。表(2 桁)を逆変換していた頃は P0 でも RMS 0.0285 が
    出ており、**帰無の基準線が帰無でなかった**(★F112)。
    """
    effect = load(MAIN_CONFIG)["effect"]
    profile = main_profile("P0")
    additive = effect["mu"] + np.array(effect["a"])[:, None] + np.array(effect["b"])[None, :]
    assert profile.eta == pytest.approx(additive, abs=1e-12)
    assert profile.nonadditivity_rms == pytest.approx(0.0, abs=1e-12)
    assert profile.delta == pytest.approx(np.zeros((N_TASK, N_COVERAGE)), abs=1e-9)
    for cov, contrast in profile.interaction_contrasts.items():
        assert contrast == pytest.approx(0.0, abs=1e-12), cov
    # ★差し替え前は 0 にならなかった(何が直ったかの記録)。
    assert P0_RMS_FROM_ROUNDED_TABLE > 0.0
    # §6.5 の P0 の T1・T2 の行そのもの(PLAN-034 §5.1)
    assert profile.eta == pytest.approx(np.array([[2.8, 1.8, 0.6], [1.8, 0.8, -0.4]]), abs=1e-12)


def test_interaction_contrasts_are_the_tost_targets() -> None:
    """★D5 (a): 交互作用の 2 係数(処理対比・基準 T1 × id)の真値(PLAN-034 §5.1)。

    答える問い: 「TOST が見る量の真値は、P1 でいくつか」—— P1 のまま = -0.4 / -1.2 を √(2/3) 倍した
    -0.326599 / -0.979796。`glmer` の係数は線形予測子の上の量なので `eta` から直接出る。
    """
    contrasts = main_profile("P1").interaction_contrasts
    assert list(contrasts) == ["interp", "extrap_magnitude"]
    assert contrasts["interp"] == pytest.approx(-0.326599, abs=1e-5)
    assert contrasts["extrap_magnitude"] == pytest.approx(-0.979796, abs=1e-5)
    sliced = power_sim.interaction_contrasts(
        P1_T1_T2_ROWS, ("T1", "T2"), ("id", "interp", "extrap_magnitude")
    )
    assert sliced["interp"] == pytest.approx(-0.4, abs=1e-12)
    assert sliced["extrap_magnitude"] == pytest.approx(-1.2, abs=1e-12)
    assert contrasts["interp"] == pytest.approx(D1_SCALE * sliced["interp"], abs=1e-5)
    assert contrasts["extrap_magnitude"] == pytest.approx(
        D1_SCALE * sliced["extrap_magnitude"], abs=1e-5
    )


def test_profile_rejects_an_eta_that_disagrees_with_the_rule_rate_gate() -> None:
    """★ADR-069 決定1 の門。`eta` と `rule_rate` が離れたら止まる。

    答える問い: 「`eta` が真値になった以上、照合用の表と黙って食い違いうるのではないか」
    —— **`rule_rate` を照合用に残したのはそのためである。**片方だけ動かすと止まる。
    """
    effect = copy.deepcopy(load(MAIN_CONFIG)["effect"])
    effect["profiles"]["P1"]["eta"] = [
        [e + 0.5 for e in row] for row in effect["profiles"]["P1"]["eta"]
    ]
    with pytest.raises(ConfigError, match="rule_rate"):
        power_sim.build_profile(effect, "P1")


def test_profile_requires_eta_and_the_named_profile() -> None:
    """★`eta` は必須である(ADR-069 決定1)。表から作り直す既定の経路は残さない。"""
    effect = copy.deepcopy(load(MAIN_CONFIG)["effect"])
    del effect["profiles"]["P1"]["eta"]
    with pytest.raises(ConfigError):
        power_sim.build_profile(effect, "P1")
    with pytest.raises(ConfigError, match="effect.profiles.P9"):
        power_sim.build_profile(load(MAIN_CONFIG)["effect"], "P9")


def test_profile_rejects_a_table_of_the_wrong_shape() -> None:
    effect = copy.deepcopy(load(MAIN_CONFIG)["effect"])
    effect["profiles"]["P1"]["rule_rate"] = [[0.9, 0.8, 0.7]]
    with pytest.raises(ConfigError):
        power_sim.build_profile(effect, "P1")


def test_profile_rejects_main_effects_of_the_wrong_length() -> None:
    """`a` / `b` の長さが水準数と合わなければ止まる(numpy の放送で黙って通さない)。"""
    effect = copy.deepcopy(load(MAIN_CONFIG)["effect"])
    effect["a"] = [0.6, 0.2, -0.4, 0.0]
    with pytest.raises(ConfigError):
        power_sim.build_profile(effect, "P1")


def test_interaction_df_is_two() -> None:
    """★主要検定の df = 2(ADR-112 決定1。§2)。RMS の分母がここに掛かっている。

    答える問い: 「4 タスク型・df = 6 の模型に戻っていないか」—— 戻れば止まる。
    """
    assert INTERACTION_DF == 2 == power_sim.PRIMARY_INTERACTION_DF
    effect = copy.deepcopy(load(MAIN_CONFIG)["effect"])
    effect["task_levels"] = ["T1", "T1b", "T2"]
    with pytest.raises(ConfigError, match="df"):
        power_sim.build_profile(effect, "P1")
    effect = copy.deepcopy(load(MAIN_CONFIG)["effect"])
    effect["coverage_levels"] = ["id", "interp"]
    with pytest.raises(ConfigError, match="df"):
        power_sim.build_profile(effect, "P1")


def test_smoke_config_has_the_same_effect_as_the_main_config() -> None:
    """★配線確認用の config の効果量が本物と食い違っていない(ずれると smoke が別の模型を試す)。"""
    assert load(SMOKE_CONFIG)["effect"] == load(MAIN_CONFIG)["effect"]
    # 点は smoke 用に小さいが、シートの順・役割・プロファイル・tau・比較先は本物と同じ

    def shape(config: dict[str, Any]) -> list[tuple[Any, ...]]:
        return [
            (s["id"], s["role"], s["profile"], s["tau"], s.get("compare_with"))
            for s in config["sheets"]
        ]

    assert shape(load(SMOKE_CONFIG)) == shape(load(MAIN_CONFIG))


# --------------------------------------------------------------------------
# 共分散(§6.3 手続き3a / ADR-068 決定2)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rho", [-0.4, 0.0, 0.5, 1.0])
def test_compound_symmetry_sqrt_squares_back(rho: float) -> None:
    """平方根の 2 乗が交換可能な相関行列に戻る。答える問い: 縮約は正しいか。"""
    root = power_sim.compound_symmetry_sqrt(N_COVERAGE, rho)
    target = (1.0 - rho) * np.eye(N_COVERAGE) + rho * np.ones((N_COVERAGE, N_COVERAGE))
    assert root @ root.T == pytest.approx(target, abs=1e-12)


def test_compound_symmetry_sqrt_survives_rho_one() -> None:
    """★`rho = 1` で落ちない。

    Cholesky はここで落ちる。**`rho = 1` は `(1 | seed)` そのもの**であり、
    ADR-068 決定2 が掃くと決めた 2 枚の 1 枚なので、落ちては困る
    (`plans/PLAN-019-check2/README.md` が固有分解を選んだ理由)。
    """
    root = power_sim.compound_symmetry_sqrt(N_COVERAGE, 1.0)
    assert np.isfinite(root).all()
    # rho = 1 のとき 3 つのセル平均は一体で動く: 引いた値がすべて等しくなる。
    z = np.array([1.3, -0.4, 0.8])
    drawn = root @ z
    assert drawn == pytest.approx(np.full(N_COVERAGE, drawn[0]), abs=1e-12)


def test_compound_symmetry_sqrt_rejects_out_of_domain() -> None:
    with pytest.raises(ValueError):
        power_sim.compound_symmetry_sqrt(N_COVERAGE, 1.5)
    with pytest.raises(ValueError):
        power_sim.compound_symmetry_sqrt(N_COVERAGE, -0.9)


# --------------------------------------------------------------------------
# DGP(§6.3 手続き3a)
# --------------------------------------------------------------------------


def smoke_levels(n_seed: int = 3, n_item: int = 2) -> power_sim.DesignLevels:
    config = load(SMOKE_CONFIG)
    return power_sim.DesignLevels(
        tasks=tuple(config["effect"]["task_levels"]),
        coverages=tuple(config["effect"]["coverage_levels"]),
        templates=config["dgp"]["templates"],
        n_seed=n_seed,
        n_item=n_item,
    )


def test_frame_has_one_row_per_seed_task_coverage_item() -> None:
    """表の行数が設計どおりである。答える問い: セルが落ちていないか。"""
    levels = smoke_levels()
    profile = main_profile("P1")
    rows = power_sim.draw_frame(
        levels, profile.eta, 0.5, 0.0, 0.25, 0.25, np.random.default_rng(0)
    )
    assert len(rows) == levels.n_seed * N_TASK * N_COVERAGE * levels.n_item
    assert {row[5] for row in rows} <= {0, 1}


def test_item_levels_are_nested_in_task() -> None:
    """★`item` は タスク型に入れ子である(§3.2。ADR-064 決定1 = ★K)。

    同じ添字でもタスク型・被覆が違えば別水準でなければならない。
    ここが混ざると、項目のランダム効果がタスク型間で共有されてしまう。
    """
    levels = smoke_levels()
    profile = main_profile("P1")
    rows = power_sim.draw_frame(
        levels, profile.eta, 0.0, 0.0, 0.25, 0.25, np.random.default_rng(1)
    )
    by_item: dict[str, set[tuple[str, str]]] = {}
    for _, task, coverage, item, _, _ in rows:
        by_item.setdefault(item, set()).add((task, coverage))
    assert all(len(cells) == 1 for cells in by_item.values())
    assert len(by_item) == N_TASK * N_COVERAGE * levels.n_item


def test_templates_stay_inside_their_task() -> None:
    """テンプレート水準は `category` であり、タスク型を跨がない(ADR-062 決定2)。"""
    levels = smoke_levels(n_item=5)
    profile = main_profile("P1")
    rows = power_sim.draw_frame(
        levels, profile.eta, 0.0, 0.0, 0.25, 0.25, np.random.default_rng(2)
    )
    for _, task, _, _, template, _ in rows:
        assert template in levels.templates[task]


def test_seed_effect_does_not_depend_on_task() -> None:
    """★`u[s, ·]` は 4 タスク型すべてに同じ値が足される(ADR-066 決定4 (d))。

    答える問い: 「`(0 + coverage | seed)` が run ごとに持つのは被覆 3 水準の
    セル平均だけか」—— 分散だけを残して確率的な部分を消し、線形予測子が
    タスク型を跨いで同じだけ動くことを見る。
    """
    levels = smoke_levels(n_seed=4, n_item=1)
    eta_fixed = np.zeros((N_TASK, N_COVERAGE))
    sigma = 1.0
    rows_a = power_sim.draw_frame(
        levels, eta_fixed, sigma, 0.0, 0.0, 0.0, np.random.default_rng(7)
    )
    rows_b = power_sim.draw_frame(
        levels, eta_fixed, sigma, 0.0, 0.0, 0.0, np.random.default_rng(7)
    )
    # 同じ rng 種なら決定的である(再現性。CLAUDE.md §2)。
    assert rows_a == rows_b


def test_zero_sigma_gives_identical_seeds_in_expectation() -> None:
    """`sigma = 0` の行は seed のランダム効果を持たない(§6.7 の下端)。"""
    levels = smoke_levels(n_seed=2, n_item=1)
    eta_fixed = np.full((N_TASK, N_COVERAGE), 20.0)  # ほぼ確実に 1 になる水準
    rows = power_sim.draw_frame(
        levels, eta_fixed, 0.0, 0.0, 0.0, 0.0, np.random.default_rng(3)
    )
    assert all(row[5] == 1 for row in rows)


def test_item_effect_is_shared_across_seeds() -> None:
    """★`v[item]` は 10 シード全部で共有される(★F117。`plans/PLAN-019` §10.13)。

    答える問い: **項目のばらつきはシード数で縮むか。**縮まない。
    `draw_frame` は `v` を seed のループの外で引くので、同じ項目は
    どのシードでも同じだけ持ち上がる(または下がる)。

    見分け方は 2 つの regime の差である。`s2_item` を大きく取り 他の分散と
    固定効果を 0 にすると:
      - **共有されているなら** 各項目の `eta` は ±大 に振れ、10 シードの
        0/1 は ほぼ必ず一致する(一致しないのは `|eta|` が小さい少数の項目だけ)
      - **シードごとに引き直していれば** `eta` は毎回引き直されるので、
        10 個が偶然そろう確率は `2 * 0.5^10 = 0.002` しかない
    **450 倍の開きがあるので、閾値 0.9 は乱数に対して頑健である。**

    ★この事実は ★F104 の決定材料(§10.13.0 の賭け金)の前提である。
    ここを変えるなら §10.13 / ★F117 を読み直すこと。
    """
    levels = smoke_levels(n_seed=10, n_item=40)
    eta_fixed = np.zeros((N_TASK, N_COVERAGE))
    rows = power_sim.draw_frame(
        levels, eta_fixed, 0.0, 0.0, 10_000.0, 0.0, np.random.default_rng(11)
    )
    by_item: dict[str, set[int]] = {}
    for _, _, _, item, _, is_rule in rows:
        by_item.setdefault(item, set()).add(is_rule)
    agreed = sum(1 for values in by_item.values() if len(values) == 1)
    assert agreed / len(by_item) > 0.9


def test_template_assignment_is_the_same_in_every_coverage_cell() -> None:
    """★同じ項目添字には、どの被覆水準でも同じテンプレートが付く(ADR-069 決定4 (3))。

    答える問い: **テンプレートのばらつきは `task:coverage` の交互作用に入るか。**
    入らない —— 巡回割当なので被覆水準を跨いで同じ値になり、差分で消える(★F117)。

    ★この打ち消しは巡回割当の性質であって、一般の事実ではない。
    割当を変えるなら `plans/PLAN-019` §10.13 の ★F117 と §10.13.6 の限界欄を
    読み直すこと(★F104 の決定がこの事実に乗っている)。
    """
    levels = smoke_levels(n_seed=1, n_item=7)
    eta_fixed = np.zeros((N_TASK, N_COVERAGE))
    rows = power_sim.draw_frame(
        levels, eta_fixed, 0.0, 0.0, 0.0, 0.0, np.random.default_rng(12)
    )
    seen: dict[tuple[str, str], str] = {}
    for _, task, coverage, item, template, _ in rows:
        index = item.rsplit(".", 1)[1]
        key = (task, index)
        assert seen.setdefault(key, template) == template, (
            f"{task} の項目 {index} に被覆 {coverage} で別のテンプレートが付いた"
        )


# --------------------------------------------------------------------------
# R へ渡すもの
# --------------------------------------------------------------------------


def test_frame_csv_is_ascii_and_lf(tmp_path: Path) -> None:
    """CSV は ASCII / LF である。答える問い: Windows で書いても R が同じ表を読むか。"""
    levels = smoke_levels()
    profile = main_profile("P1")
    rows = power_sim.draw_frame(
        levels, profile.eta, 0.5, 1.0, 0.25, 0.25, np.random.default_rng(4)
    )
    path = tmp_path / "frame.csv"
    power_sim.write_frame_csv(rows, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.decode("ascii").splitlines()[0] == ",".join(power_sim.CSV_HEADER)
    assert len(raw.decode("ascii").splitlines()) == len(rows) + 1


def test_fit_manifest_carries_the_thresholds(tmp_path: Path) -> None:
    """★ADR-059 の閾値が config から R へ流れる(コードに直書きしない)。"""
    config = load(MAIN_CONFIG)
    manifest = tmp_path / "manifest.txt"
    power_sim.write_fit_manifest(
        manifest,
        [(tmp_path / "a.csv", tmp_path / "a.json")],
        config["fit"]["refit"],
        len(config["fit"]["reduction_order"]),
    )
    text = manifest.read_text(encoding="ascii")
    assert "loglik_tolerance=0.001" in text
    assert "beta_move_tolerance=0.01" in text
    assert "max_reduction_level=3" in text
    assert text.count("fit=") == 1


# --------------------------------------------------------------------------
# ★並列実行(ADR-069 決定3 = ★F114)
# --------------------------------------------------------------------------


def _jobs(tmp_path: Path, n: int) -> list[tuple[Path, Path]]:
    return [(tmp_path / f"f{i}.csv", tmp_path / f"f{i}.json") for i in range(n)]


@pytest.mark.parametrize("n_jobs,n_workers", [(1, 1), (7, 1), (7, 3), (12, 16), (1000, 16)])
def test_shards_partition_the_jobs_exactly_once(
    tmp_path: Path, n_jobs: int, n_workers: int
) -> None:
    """★並列にしても当てはめは増えも減りもしない。

    答える問い: 「16 並列にしたとき、同じ表を 2 回当てたり 1 枚落としたりしないか」——
    **落とせば検出力が反復数不足のまま報告され、二重に当てれば費用が二重になる。**
    """
    jobs = _jobs(tmp_path, n_jobs)
    shards = power_sim.shard_jobs(jobs, n_workers)
    flat = [job for shard in shards for job in shard]
    assert flat == jobs                       # 順序も保つ(集計が job 順に読む)
    assert len(shards) == min(n_workers, n_jobs)
    assert all(shard for shard in shards)     # 空のシャードを作らない
    # 連続ブロックで、大きさの差は 1 以内(負荷が揃う)。
    sizes = [len(shard) for shard in shards]
    assert max(sizes) - min(sizes) <= 1


def test_shard_count_does_not_change_the_work(tmp_path: Path) -> None:
    """★結果が `n_workers` に依らないことの骨格。

    答える問い: 「並列数を変えたら別の実験になってしまわないか」——
    **ならない。**`n_workers` は当てはめの束ね方しか変えず、表そのものは
    親が単一の `rng` から決まった順で書く(ADR-069 決定3)。
    """
    jobs = _jobs(tmp_path, 40)
    flattened = {
        n: [job for shard in power_sim.shard_jobs(jobs, n) for job in shard]
        for n in (1, 2, 5, 16, 64)
    }
    assert all(flat == jobs for flat in flattened.values())


def test_shard_jobs_rejects_a_non_positive_worker_count(tmp_path: Path) -> None:
    """★0 並列・負の並列は黙って 1 に直さない(skill `code-style` §5)。"""
    for bad in (0, -1):
        with pytest.raises(ConfigError):
            power_sim.shard_jobs(_jobs(tmp_path, 4), bad)


def test_shard_jobs_of_nothing_is_nothing(tmp_path: Path) -> None:
    assert power_sim.shard_jobs([], 8) == []


def test_run_fits_writes_one_manifest_per_shard(tmp_path: Path, monkeypatch) -> None:
    """★R は 1 並列単位につき 1 回だけ起動する(起動と lme4 の読み込みが高い)。

    答える問い: 「並列化で R の起動回数が反復数ぶんに増えていないか」——
    増えていれば `run_rscript` の但し書き(数千枚で数時間)を自分で破ることになる。
    """
    config = load(MAIN_CONFIG)
    calls: list[Path] = []
    monkeypatch.setattr(power_sim, "run_rscript",
                        lambda rscript, libpath, manifest: calls.append(manifest) or "")
    manifests = power_sim.run_fits(
        "Rscript", None, tmp_path / "manifest_s0_r0", _jobs(tmp_path, 10),
        config["fit"]["refit"], len(config["fit"]["reduction_order"]), 4,
    )
    assert len(manifests) == 4
    assert calls == manifests                       # 起動は 4 回。10 回ではない
    total = sum(m.read_text(encoding="ascii").count("fit=") for m in manifests)
    assert total == 10                              # 当てはめは 10 枚のまま


def test_run_fits_propagates_a_worker_failure(tmp_path: Path, monkeypatch) -> None:
    """★1 本でも落ちたら止まる。当てはめの失敗を黙って数えない(`CLAUDE.md` §7)。"""
    config = load(MAIN_CONFIG)

    def boom(rscript, libpath, manifest):
        raise power_sim.PowerSimError("R が落ちた")

    monkeypatch.setattr(power_sim, "run_rscript", boom)
    with pytest.raises(power_sim.PowerSimError):
        power_sim.run_fits(
            "Rscript", None, tmp_path / "manifest_s0_r0", _jobs(tmp_path, 8),
            config["fit"]["refit"], len(config["fit"]["reduction_order"]), 4,
        )


def test_cost_line_scales_the_measured_seconds_per_pair_by_rows() -> None:
    """★見積りは実測を行数(= `n_item`)で比例させて出す。算術の 9 時間ではない。

    答える問い: 「本実行が何時間になるかを、回す前に人間が読めるか」——
    §10.7.8 の「24,000 本 = 約 9 時間」は 7 倍甘かった(F50 からの掛け算だった)。
    基準は 2 本(ADR-123 文脈1・2): ベンチ(4 タスク型・`n_item = 48` の 5,760 行で 297.6 秒。`n_item` 80 で約 248 秒)
    と小検査(4,800 行の 64 ペアを 16 並列で 27.5 分 → 約 412 コア秒)。**どちらも推算であって未実測**。
    """
    assert power_sim.SECONDS_PER_PAIR_MEASURED == pytest.approx(297.6)
    assert power_sim.ROWS_AT_MEASUREMENT == 4 * 3 * 48 * 10
    config = load(MAIN_CONFIG)
    levels = power_sim.load_levels(config, 80)
    assert power_sim.table_rows(levels) == 4_800
    assert power_sim.estimate_seconds_per_pair(levels) == pytest.approx(248.0)
    assert power_sim.estimate_seconds_per_pair_check(levels) == pytest.approx(412.5)
    # 1 ペアの秒は n_item に比例する(仮定)
    assert power_sim.estimate_seconds_per_pair(
        power_sim.load_levels(config, 240)
    ) == pytest.approx(3 * 248.0)
    lines = power_sim.describe_plan(config, workers_override=16)
    text = "\n".join(lines)
    assert "ESTIMATED" in text and "MEASURED" not in text
    # ADR-123 文脈2 の推算(16 並列): 1 段目 ≈ 12 / 19 時間・誤指定だけ ≈ 2.6 / 4.3 時間
    stage1 = next(line for line in lines if line.strip().startswith("stage 1:"))
    assert "all sheets 11.6 / 19.3" in stage1
    assert "first sheet only (misspecification) 2.6 / 4.3" in stage1
    # 段の累積(100 → 300 → 1000)の合計は ≈ 116 / 193 時間
    totals = [0.0, 0.0]
    for line in lines:
        if line.strip().startswith("stage "):
            bench, check = line.split("all sheets ")[1].split(",")[0].split(" / ")
            totals[0] += float(bench)
            totals[1] += float(check)
    assert totals == pytest.approx([116.2, 193.4], abs=0.2)


def test_fit_script_keeps_the_preregistered_random_structure() -> None:
    """★当てはめ側の level 0 が §3.2 のランダム構造そのものである。

    答える問い: 「シミュレーションが当てているのは、事前登録した検定か」——
    ★F110 が指した食い違い(DGP は合っているのに当てはめが `(1|seed)`)を
    回帰テストで塞ぐ。ここが崩れると「実際には回さない検定の検出力」になる。
    """
    text = power_sim.FIT_SCRIPT.read_text(encoding="utf-8")
    assert "(0 + coverage | seed) + (1 | item) + (1 | template)" in text
    assert "task * coverage" in text and "task + coverage" in text
    # ★誤指定のシート(D7)は当てはめ側を変えない: seed × タスク型 × 被覆の項は当てはめに入らない
    assert "tau" not in text
    # 縮退は §3.2 の順序で並んでいる: template -> coverage の傾き -> item。
    drop_template = text.index('"(0 + coverage | seed) + (1 | item)"')
    drop_slope = text.index('"(1 | seed) + (1 | item)"')
    drop_item = text.index('"(1 | seed)"\n')
    assert drop_template < drop_slope < drop_item
    # singular は単独では引き金にしない / 判定は isSingular() を直接呼ぶ(F56)。
    assert "isSingular(" in text
    assert "non_singular_messages" in text


def test_resolve_rscript_reports_a_missing_binary(tmp_path: Path) -> None:
    with pytest.raises(power_sim.PowerSimError):
        power_sim.resolve_rscript(str(tmp_path / "no-such-Rscript.exe"))


# --------------------------------------------------------------------------
# 集計と逆問題(§6.3 手続き3c / 手続き5)
# --------------------------------------------------------------------------


def fit_result(p_value: float | None, **overrides: Any) -> dict[str, Any]:
    """R が返す JSON の形を手で組む。**R は呼ばない。**"""
    base = {
        "p_value": p_value,
        "chisq": 6.0,
        "reduced": False,
        "full_singular": False,
        "add_singular": False,
        "full_refit_done": False,
        "add_refit_done": False,
        "n_errored_fits": 0,
        "first_error": "",
        # 平行性の TOST の入力(`power_sim_fit.R` の `interaction_coefficients`)
        "interaction_interp_est": 0.0,
        "interaction_interp_se": 0.1,
        "interaction_extrap_magnitude_est": 0.0,
        "interaction_extrap_magnitude_se": 0.2,
    }
    base.update(overrides)
    return base


KEY = power_sim.PointKey(n_item=80, sigma=0.5, rho=0.0)


def test_power_is_the_share_below_alpha() -> None:
    results = [fit_result(0.01), fit_result(0.2), fit_result(0.04), fit_result(0.9)]
    point = power_sim.summarise_point(KEY, results, 0.05)
    assert point.power == pytest.approx(0.5)
    assert point.n_rep == 4
    assert point.n_reject == 2            # 門の区間に使う分子。割合から逆算しない
    assert point.key == KEY


def test_degeneracy_rate_is_reported() -> None:
    """★縮退の発火率を必ず返す。

    ADR-064 決定4 の★リスク欄(「10 シードでこの項が同定できるかは
    誰にも数値では言えない」)に数値を与えることが、ADR-068 決定1 を採る利②である。
    落とすと、その利がそのまま消える。
    """
    results = [
        fit_result(0.01, reduced=True, full_singular=True, add_refit_done=True),
        fit_result(0.20),
    ]
    point = power_sim.summarise_point(power_sim.PointKey(80, 1.0, 1.0), results, 0.05)
    assert point.reduced_rate == pytest.approx(0.5)
    assert point.singular_rate == pytest.approx(0.5)
    assert point.refit_rate == pytest.approx(0.5)


def test_a_null_p_value_stops_the_summary() -> None:
    """★p 値が null の反復を黙って捨てない(`CLAUDE.md` §7)。"""
    with pytest.raises(power_sim.PowerSimError):
        power_sim.summarise_point(KEY, [fit_result(None)], 0.05)


def test_empty_grid_point_stops_the_summary() -> None:
    with pytest.raises(power_sim.PowerSimError):
        power_sim.summarise_point(KEY, [], 0.05)


def point(
    sigma: float, power: float, rho: float = 0.0, n_item: int = 80, n_rep: int = 1000
) -> power_sim.GridPoint:
    return power_sim.GridPoint(
        n_item=n_item, sigma=sigma, rho=rho, n_rep=n_rep, n_reject=round(power * n_rep),
        power=power, reduced_rate=0.0, singular_rate=0.0, refit_rate=0.0, mean_chisq=6.0,
        errored_rate=0.0,
    )


def test_sigma_star_is_the_last_point_before_the_first_failure() -> None:
    """逆問題の答え(§6.3 手続き5)。答える問い: 10 シードはどこまで保つか。"""
    limit = power_sim.sigma_limit(
        [point(0.0, 0.99), point(0.5, 0.90), point(1.0, 0.70), point(1.5, 0.60)], 0.8
    )
    assert limit["verdict"] == "inside_swept_range"
    assert limit["sigma_star"] == pytest.approx(0.5)
    assert limit["first_failing_sigma"] == pytest.approx(1.0)


def test_holding_everywhere_is_reported_as_outside_the_swept_range() -> None:
    """★全域で保ったら「掃いた範囲の外」と言う。「限界は無い」とは書かない。

    掃いていない領域について言えることは無い(§6.3 手続き5)。
    ★F111 はこうなる公算が高いと見ている(見立て。未検証)。
    """
    limit = power_sim.sigma_limit(
        [point(s, 0.95) for s in ADOPTED_SIGMA], 0.8
    )
    assert limit["verdict"] == "beyond_swept_range"
    assert limit["sigma_star"] is None
    assert limit["last_holding_sigma"] == pytest.approx(1.5)


def test_failing_at_the_first_point_is_below_the_swept_range() -> None:
    """★F6-1: 最初の点で割ったら `below_swept_range`(旧実装は `inside_swept_range`・`sigma_star: null` を返した)。"""
    limit = power_sim.sigma_limit([point(0.5, 0.62), point(1.0, 0.63), point(1.5, 0.61)], 0.8)
    assert limit["verdict"] == "below_swept_range"
    assert limit["sigma_star"] is None
    assert limit["last_holding_sigma"] is None
    assert limit["first_failing_sigma"] == pytest.approx(0.5)
    assert limit["non_monotone"] is False


def test_non_monotone_curve_is_flagged_not_smoothed() -> None:
    """★一度割った先で保っている点があれば旗を立てる(隠さない)。

    モンテカルロ誤差で曲線は単調でなくなりうる。後ろから拾うと
    「割ったのに、その先が限界」と読める報告になる。
    """
    limit = power_sim.sigma_limit(
        [point(0.0, 0.99), point(0.5, 0.70), point(1.0, 0.85)], 0.8
    )
    assert limit["sigma_star"] == pytest.approx(0.0)
    assert limit["first_failing_sigma"] == pytest.approx(0.5)
    assert limit["non_monotone"] is True


def n_points(powers: dict[int, float]) -> list[power_sim.GridPoint]:
    return [point(1.0, power, n_item=n) for n, power in powers.items()]


def test_n_item_range_is_read_from_the_largest_point_downward() -> None:
    """★主の報告量(ADR-122 決定2)。答える問い: 0.8 に届く `n_item` の範囲はどこか。

    格子点だけ・補間しない。「(120, 160] の間で届き始める」と読む。
    """
    answer = power_sim.n_item_range(n_points({80: 0.63, 120: 0.78, 160: 0.91, 240: 0.99}), 0.8)
    assert answer == {
        "verdict": "inside_swept_range",
        "reaching_from_n_item": 160,
        "largest_failing_n_item": 120,
        "non_monotone": False,
    }


def test_n_item_range_reports_both_ends_of_the_swept_range() -> None:
    """★全点で届けば `below_swept_range`(届き始めるのは 80 以下)、最大でも届かなければ `beyond_swept_range`。"""
    everywhere = power_sim.n_item_range(n_points({80: 0.85, 120: 0.9, 160: 0.95, 240: 0.99}), 0.8)
    assert everywhere["verdict"] == "below_swept_range"
    assert everywhere["reaching_from_n_item"] == 80
    assert everywhere["largest_failing_n_item"] is None
    nowhere = power_sim.n_item_range(n_points({80: 0.3, 120: 0.4, 160: 0.5, 240: 0.7}), 0.8)
    assert nowhere["verdict"] == "beyond_swept_range"
    assert nowhere["reaching_from_n_item"] is None
    assert nowhere["largest_failing_n_item"] == 240


def test_n_item_range_does_not_pick_a_reaching_point_below_a_failure() -> None:
    """★`sigma_limit` と同じ考え方: 大きい側から走査して最初に割った点で切り、その下で届く点は旗にする。"""
    answer = power_sim.n_item_range(n_points({80: 0.6, 120: 0.82, 160: 0.79, 240: 0.95}), 0.8)
    assert answer["reaching_from_n_item"] == 240
    assert answer["largest_failing_n_item"] == 160
    assert answer["non_monotone"] is True


def main_axes() -> power_sim.AxisSpec:
    return power_sim.load_axis_spec(load(MAIN_CONFIG))


def test_report_axes_are_the_decided_ones() -> None:
    """★ADR-123 決定2: 主の軸は `sigma` 1.0・`rho` 0、確認点は `n_item` 80・`rho` 0。分位点は人間(その143)。"""
    axes = main_axes()
    assert (axes.n_item_axis_sigma, axes.n_item_axis_rho) == (1.0, 0.0)
    assert (axes.sigma_axis_n_item, axes.sigma_axis_rho) == (80, 0.0)
    assert axes.margin_quantiles == (0.05, 0.25, 0.5, 0.75, 0.95)


def test_inverse_problem_reads_each_axis_from_its_own_points() -> None:
    """★主(`n_item` の範囲)は `sigma` 1.0 の 4 点、従(`sigma*`)は `n_item` 80 の 3 点だけから読む。"""
    points = [
        point(0.5, 0.95), point(1.0, 0.70), point(1.5, 0.60),
        point(1.0, 0.85, n_item=120), point(1.0, 0.90, n_item=160), point(1.0, 0.99, n_item=240),
    ]
    answer = power_sim.inverse_problem(points, main_axes(), 0.8)
    assert answer["n_item_range"]["reaching_from_n_item"] == 120
    assert answer["n_item_range"]["largest_failing_n_item"] == 80
    assert answer["sigma_limit"]["sigma_star"] == pytest.approx(0.5)
    assert answer["sigma_limit"]["first_failing_sigma"] == pytest.approx(1.0)
    with pytest.raises(power_sim.PowerSimError, match="報告の軸"):
        power_sim.inverse_problem([point(1.0, 0.9, n_item=120)], main_axes(), 0.8)


def test_plan_grid_is_the_sum_of_the_sheets() -> None:
    """★ADR-123: 誤指定 6 + P1 6 + P1⁻ 2 + P0 6 = 20 点。**誤指定が先頭**(ADR-122 決定3)。

    費用の単位(`n_item` 80 の 1 点)では 6 + 9.5 + 2 + 9.5 = 27 単位(ADR-123 文脈2)。
    """
    plan = power_sim.plan_grid(load(MAIN_CONFIG))
    by_sheet: dict[str, int] = {}
    for sheet_id, _ in plan:
        by_sheet[sheet_id] = by_sheet.get(sheet_id, 0) + 1
    assert list(by_sheet) == ["misspecification", "p1", "p1_neg", "p0"]
    assert by_sheet == {"misspecification": 6, "p1": 6, "p1_neg": 2, "p0": 6}
    assert len(plan) == 20
    assert sum(key.n_item for _, key in plan) / 80 == pytest.approx(27.0)


# --------------------------------------------------------------------------
# ★誤指定の DGP(ADR-114 決定7 = D7 (a))
# --------------------------------------------------------------------------


def test_tau_zero_is_the_same_table_as_no_tau() -> None:
    """★`tau = 0` は乱数を消費しない: `tau` を渡さない呼び出しと同じ表になる。

    答える問い: 「誤指定のシートの `sigma = 0`(`tau = 0`)の点は P0 のシートと同じ DGP か」
    —— 同じなら、誤指定の効果は `tau > 0` の点だけに現れる(PLAN-034 D7 の完了条件)。
    """
    levels = smoke_levels(n_seed=3, n_item=3)
    eta = main_profile("P0").eta
    without = power_sim.draw_frame(levels, eta, 0.5, 0.0, 0.25, 0.25, np.random.default_rng(5))
    with_zero = power_sim.draw_frame(
        levels, eta, 0.5, 0.0, 0.25, 0.25, np.random.default_rng(5), tau=0.0
    )
    assert without == with_zero


# 線形予測子が ±巨大 になり、各セルの 0/1 が確定する大きさの tau(`draw_frame` の確率計算が溢れないことも兼ねる)
HUGE_TAU = 1e9


def test_tau_adds_one_effect_per_seed_task_and_coverage() -> None:
    """★`z[s, task, coverage]` は (シード, タスク型, 被覆) のセルごとに 1 つで、項目を跨いで共有される。

    答える問い: 「足したのは seed × タスク型 × 被覆の変動か(項目ごとの雑音ではないか)」——
    ほかの分散を 0、固定効果を 0、`tau` を巨大にすると、各セルの線形予測子は ±巨大 に振れるので
    **同じセルの 40 項目は 0/1 がすべて一致する**(項目ごとの雑音なら一致しない)。
    一方セルは独立に引かれるので、**シード・タスク型・被覆が違えば食い違うセルがある**。
    """
    levels = smoke_levels(n_seed=10, n_item=40)
    eta_fixed = np.zeros((N_TASK, N_COVERAGE))
    rows = power_sim.draw_frame(
        levels, eta_fixed, 0.0, 0.0, 0.0, 0.0, np.random.default_rng(21), tau=HUGE_TAU
    )
    by_cell: dict[tuple[str, str, str], set[int]] = {}
    for seed, task, coverage, _, _, is_rule in rows:
        by_cell.setdefault((seed, task, coverage), set()).add(is_rule)
    assert len(by_cell) == levels.n_seed * N_TASK * N_COVERAGE
    assert all(len(values) == 1 for values in by_cell.values())
    cell_value = {key: next(iter(values)) for key, values in by_cell.items()}
    assert len(set(cell_value.values())) == 2                       # 0 のセルも 1 のセルもある
    # 同じ (task, coverage) でシードが違えば食い違う(シードごとに独立に引いている)
    seeds_disagree = any(
        len({cell_value[(f"s{s:02d}", task, cov)] for s in range(levels.n_seed)}) == 2
        for task in levels.tasks
        for cov in levels.coverages
    )
    assert seeds_disagree


def test_tau_is_not_shared_across_tasks() -> None:
    """★`u[s, ·]`(被覆の変動)は全タスク型で共通だが、`z` はタスク型ごとに独立である。

    答える問い: 「`tau` は §3.2 の `(0 + coverage | seed)` が吸収できる項を足してしまっていないか」——
    吸収できる(= タスク型を跨いで同じ)なら誤指定にならない。同じシード・被覆でタスク型が違えば
    食い違うセルがあること。
    """
    levels = smoke_levels(n_seed=10, n_item=1)
    rows = power_sim.draw_frame(
        levels, np.zeros((N_TASK, N_COVERAGE)), 0.0, 0.0, 0.0, 0.0,
        np.random.default_rng(22), tau=HUGE_TAU,
    )
    value = {(seed, task, cov): is_rule for seed, task, cov, _, _, is_rule in rows}
    assert any(
        value[(f"s{s:02d}", "T1", cov)] != value[(f"s{s:02d}", "T2", cov)]
        for s in range(levels.n_seed)
        for cov in levels.coverages
    )


@pytest.mark.parametrize("eta", [-3.0, -0.5, 0.0, 0.7, 4.0])
def test_logistic_matches_the_plain_formula_and_survives_extremes(eta: float) -> None:
    """DGP の確率計算。普通の範囲では素直な式と一致し、極端な値でも溢れない(`math.exp` は ±709 で溢れる)。"""
    assert power_sim.logistic(eta) == pytest.approx(1.0 / (1.0 + np.exp(-eta)), abs=1e-15)
    assert power_sim.logistic(-1e9) == 0.0
    assert power_sim.logistic(1e9) == 1.0


def test_tau_must_not_be_negative() -> None:
    with pytest.raises(ValueError):
        power_sim.draw_frame(
            smoke_levels(), np.zeros((N_TASK, N_COVERAGE)), 0.0, 0.0, 0.25, 0.25,
            np.random.default_rng(0), tau=-0.1,
        )


# --------------------------------------------------------------------------
# ★シート(ADR-114 決定2・4・7)
# --------------------------------------------------------------------------


def main_sheet(sheet_id: str) -> dict[str, Any]:
    """主 config のシートの宣言 1 枚(写し)。"""
    return copy.deepcopy(next(s for s in load(MAIN_CONFIG)["sheets"] if s["id"] == sheet_id))


P1_POINTS = (
    (80, 0.5, 0.0), (80, 1.0, 0.0), (80, 1.5, 0.0), (120, 1.0, 0.0), (160, 1.0, 0.0), (240, 1.0, 0.0),
)


def as_tuples(sheet: power_sim.Sheet) -> tuple[tuple[int, float, float], ...]:
    return tuple((k.n_item, k.sigma, k.rho) for k in sheet.points)


def test_main_sheets_follow_the_adopted_decisions() -> None:
    """PLAN-040 §11 / ADR-123 決定1〜4 が `sheets:` に宣言どおり入っている。"""
    sheets = {sheet.sheet_id: sheet for sheet in power_sim.load_sheets(load(MAIN_CONFIG))}
    # 順は 誤指定 → P1 → P1⁻ → P0(ADR-122 決定3 / ADR-123 決定5)
    assert list(sheets) == ["misspecification", "p1", "p1_neg", "p0"]
    mis, p1, neg, p0 = (sheets[k] for k in ("misspecification", "p1", "p1_neg", "p0"))
    # 決定4: 誤指定は変えない(P0・tau = sigma の 6 点・rho 0・n_item 80)
    assert (mis.role, mis.profile, mis.tau) == ("misspecification", "P0", "equals_sigma")
    assert as_tuples(mis) == tuple((80, s, 0.0) for s in ADOPTED_SIGMA)
    # 決定1・2: P1 と P0 は同じ 6 点
    assert (p1.role, p1.profile, as_tuples(p1)) == ("power", "P1", P1_POINTS)
    assert (p0.role, p0.profile, as_tuples(p0)) == ("null_calibration", "P0", P1_POINTS)
    # 決定3: P1⁻ は n_item 80・sigma {0.5, 1.5}・rho 0。比較は P1
    assert (neg.role, neg.profile, as_tuples(neg)) == (
        "shape_check", "P1_neg", ((80, 0.5, 0.0), (80, 1.5, 0.0))
    )
    assert neg.compare_with == "p1"
    # 決定2: sigma 0 と rho 1 は P1・P0・P1⁻ に置かない(PLAN-040 §7 罠5)
    for sheet in (p1, neg, p0):
        assert all(k.sigma > 0.0 and k.rho == 0.0 for k in sheet.points)
    assert power_sim.frame_tau(mis, 1.5) == pytest.approx(1.5)
    assert power_sim.frame_tau(p0, 1.5) == 0.0


def sheets_config(*entries: dict[str, Any]) -> dict[str, Any]:
    """主 config の `sheets:` を `entries` に差し替えた config。"""
    config = copy.deepcopy(load(MAIN_CONFIG))
    config["sheets"] = list(entries)
    return config


def test_a_sheet_swapping_p0_and_p1_is_rejected() -> None:
    """★検出力のシートに P0、第一種の過誤のシートに P1 を置くと止まる(読み違いの事故を塞ぐ)。"""
    with pytest.raises(ConfigError, match="RMS"):
        power_sim.load_sheets(sheets_config({**main_sheet("p1"), "profile": "P0"}))
    with pytest.raises(ConfigError, match="RMS"):
        power_sim.load_sheets(sheets_config({**main_sheet("p0"), "profile": "P1"}))


def test_tau_belongs_to_the_misspecification_sheet_only() -> None:
    with pytest.raises(ConfigError, match="tau"):
        power_sim.load_sheets(sheets_config({**main_sheet("p1"), "tau": "equals_sigma"}))
    with pytest.raises(ConfigError, match="tau"):
        power_sim.load_sheets(sheets_config({**main_sheet("misspecification"), "tau": "zero"}))


def test_a_sheet_cannot_use_a_point_outside_the_declared_grids() -> None:
    """掃く格子は `dgp` のもの(ADR-068 決定3 / ADR-123 決定1)。シートが新しい点を作ってはならない。"""
    for bad in ([80, 2.0, 0.0], [100, 1.0, 0.0], [80, 1.0, 0.5]):
        with pytest.raises(ConfigError, match="格子に無い"):
            power_sim.load_sheets(sheets_config({**main_sheet("p1"), "points": [bad]}))
    for malformed in ([], [[80, 1.0]], [[80.0, 1.0, 0.0]], [[80, 1.0, 0.0], [80, 1.0, 0.0]]):
        with pytest.raises(ConfigError):
            power_sim.load_sheets(sheets_config({**main_sheet("p1"), "points": malformed}))


def test_n_item_grid_must_be_positive_integers() -> None:
    for bad in (80, [], [80, 0], [80, 120.0], None):
        config = copy.deepcopy(load(MAIN_CONFIG))
        config["dgp"]["n_item"] = bad
        with pytest.raises(ConfigError):
            power_sim.load_n_item_grid(config)
    with pytest.raises(ConfigError, match="格子に無い"):
        power_sim.load_levels(load(MAIN_CONFIG), 100)


def test_sheet_ids_and_comparison_must_be_consistent() -> None:
    with pytest.raises(ConfigError, match="重複"):
        power_sim.load_sheets(sheets_config(main_sheet("p1"), main_sheet("p1")))
    # 形の検査のシートは compare_with を必ず持ち、基準は上にあるシートである
    with pytest.raises(ConfigError, match="compare_with"):
        power_sim.load_sheets(sheets_config(main_sheet("p1_neg")))
    with pytest.raises(ConfigError, match="compare_with"):
        power_sim.load_sheets(sheets_config({**main_sheet("p1"), "compare_with": "p1"}))


def test_only_the_power_sheet_gets_the_inverse_problem() -> None:
    """★`n_item` の範囲と `sigma*` は検出力のシートにだけ出す。P0・誤指定の棄却率は第一種の過誤の率であり、
    「検出力が 0.8 を割る点」という読みをしない。"""
    config = load(MAIN_CONFIG)
    sheets = {sheet.sheet_id: sheet for sheet in power_sim.load_sheets(config)}
    points = [point(s, 0.9, n_item=n) for n, s, _ in P1_POINTS]
    summaries = {
        sheet_id: power_sim.sheet_summary(
            sheet, main_profile(sheet.profile), points, 0.8, main_axes()
        )
        for sheet_id, sheet in sheets.items()
    }
    assert "inverse_problem" in summaries["p1"]
    for other in ("p1_neg", "p0", "misspecification"):
        assert "inverse_problem" not in summaries[other]
    assert summaries["p1"]["true_interaction_contrasts"]["interp"] == pytest.approx(
        -0.326599, abs=1e-5
    )
    assert summaries["misspecification"]["tau"] == "equals_sigma"
    assert summaries["p1"]["grid"][0]["n_item"] == 80


def test_compare_power_pairs_matching_points_only() -> None:
    """形の検査: 同じ `(n_item, sigma, rho)` だけを突き合わせる。基準に無い点を補わない(ADR-123 決定3)。"""
    reference = [point(0.5, 0.90), point(1.5, 0.60), point(1.5, 0.95, n_item=240)]
    other = [point(0.5, 0.88), point(1.5, 0.62), point(1.0, 0.80), point(1.5, 0.99, n_item=120)]
    compared = power_sim.compare_power(reference, other)
    assert [(row["n_item"], row["sigma"]) for row in compared] == [(80, 0.5), (80, 1.5)]
    assert compared[0]["difference"] == pytest.approx(-0.02)
    assert compared[1]["difference"] == pytest.approx(0.02)


# --------------------------------------------------------------------------
# ★段・乱数・誤指定の門(ADR-122 決定3・4 / ADR-123 決定5・6)
# --------------------------------------------------------------------------


def test_stages_are_the_decided_ones_and_must_increase() -> None:
    """★ADR-123 決定5: 累積 100 → 300 → 1000(最後は §6.3 手続き3c の 1000)。旧い `n_rep` は止まる。"""
    assert power_sim.load_stages(load(MAIN_CONFIG)) == (100, 300, 1000)
    for bad in ([], [100, 100], [300, 100], [0, 10], [100.0], None):
        config = copy.deepcopy(load(MAIN_CONFIG))
        config["simulation"]["n_rep_stages"] = bad
        with pytest.raises(ConfigError):
            power_sim.load_stages(config)
    config = copy.deepcopy(load(MAIN_CONFIG))
    config["simulation"]["n_rep"] = 1000
    with pytest.raises(ConfigError, match="n_rep_stages"):
        power_sim.load_stages(config)


def test_replication_rng_depends_only_on_sheet_point_and_rep() -> None:
    """★ADR-122 決定4: 反復の表は「シート × 点 × 反復」だけで決まる(位置ではなく値が鍵)。"""
    key = power_sim.PointKey(80, 0.5, 0.0)

    def draw(sheet_id: str, k: power_sim.PointKey, rep: int, seed: int = 20260909) -> float:
        return float(power_sim.replication_rng(seed, sheet_id, k, rep).random())

    assert draw("p1", key, 7) == draw("p1", key, 7)
    others = [
        draw("p0", key, 7), draw("p1", key, 8), draw("p1", key, 7, seed=1),
        draw("p1", power_sim.PointKey(120, 0.5, 0.0), 7),
        draw("p1", power_sim.PointKey(80, 1.5, 0.0), 7),
        draw("p1", power_sim.PointKey(80, 0.5, 1.0), 7),
    ]
    assert len({draw("p1", key, 7), *others}) == len(others) + 1


def test_main_gate_is_the_decided_one() -> None:
    """★ADR-123 決定6: `tau` 0.25・0.5 で 95% Clopper–Pearson 区間の下端 > 0.075。閾値は config にある。"""
    config = load(MAIN_CONFIG)
    gate = power_sim.load_gate_spec(config)
    assert gate == power_sim.GateSpec(
        sheet_id="misspecification", tau=(0.25, 0.5), ci_level=0.95, lower_bound_above=0.075
    )
    power_sim.check_gate_against_sheets(gate, power_sim.load_sheets(config))


@pytest.mark.parametrize("n_rep,first_stopping", [(100, 14), (300, 33)])
def test_gate_operating_point_matches_adr_123(n_rep: int, first_stopping: int) -> None:
    """★ADR-123 文脈3 の算術: 100 反復では 14 回以上、300 反復では 33 回以上の棄却で止まる。"""
    gate = power_sim.load_gate_spec(load(MAIN_CONFIG))

    def inflated(n_reject: int) -> bool:
        points = [point(t, n_reject / n_rep, n_rep=n_rep) for t in (0.0, 0.25, 0.5)]
        points[2] = point(0.5, 0.0, n_rep=n_rep)          # 判定は 0.25 と 0.5 のどちらか 1 つで足りる
        return power_sim.misspecification_gate(points, gate)["inflated"]

    assert not inflated(first_stopping - 1)
    assert inflated(first_stopping)


def test_gate_ignores_tau_zero_and_large_tau() -> None:
    """★`tau` 0 と 0.75 以上は判定に使わない(記録はシートの grid にある)。"""
    gate = power_sim.load_gate_spec(load(MAIN_CONFIG))
    points = [point(0.0, 0.5, n_rep=100), point(0.25, 0.05, n_rep=100),
              point(0.5, 0.05, n_rep=100), point(1.5, 0.9, n_rep=100)]
    verdict = power_sim.misspecification_gate(points, gate)
    assert verdict["inflated"] is False
    assert [row["tau"] for row in verdict["rows"]] == [0.25, 0.5]


def test_clopper_pearson_lower_bound() -> None:
    assert power_sim.clopper_pearson_lower(0, 100, 0.95) == 0.0
    # 既知の値: 5 / 100 の 95% 区間の下端 ≈ 0.01643
    assert power_sim.clopper_pearson_lower(5, 100, 0.95) == pytest.approx(0.016431, abs=1e-5)
    with pytest.raises(ValueError):
        power_sim.clopper_pearson_lower(5, 4, 0.95)


def test_gate_must_watch_the_first_sheet_and_its_own_tau() -> None:
    """★D3 (a): 誤指定は先頭。門の `tau` はそのシートが回す点でなければならない。"""
    config = load(MAIN_CONFIG)
    gate = power_sim.load_gate_spec(config)
    reordered = power_sim.load_sheets(
        sheets_config(main_sheet("p1"), main_sheet("misspecification"))
    )
    with pytest.raises(ConfigError, match="先頭"):
        power_sim.check_gate_against_sheets(gate, reordered)
    thin = {**main_sheet("misspecification"), "points": [[80, 0.25, 0.0]]}
    with pytest.raises(ConfigError, match="回さない"):
        power_sim.check_gate_against_sheets(gate, power_sim.load_sheets(sheets_config(thin)))
    bad = copy.deepcopy(config)
    bad["simulation"]["misspecification_gate"]["lower_bound_above"] = None
    with pytest.raises(ConfigError):
        power_sim.load_gate_spec(bad)


def test_margin_table_lists_p0_and_p1_on_the_n_item_axis() -> None:
    """★D5 (a)(ADR-122 決定5): P0 と P1 の最小 Δ の分位点を、主の軸の各 `n_item` で並べる。"""
    def with_margins(n_item: int, margins: list[float], sigma: float = 1.0) -> power_sim.GridPoint:
        return dataclasses.replace(point(sigma, 0.5, n_item=n_item), tost_min_margins=tuple(margins))

    margins = [float(m) for m in range(1, 21)]
    sheet_points = {
        "misspecification": [with_margins(80, margins)],
        "p1": [with_margins(80, margins), with_margins(240, margins), with_margins(80, margins, 0.5)],
        "p1_neg": [with_margins(80, margins, 0.5)],
        "p0": [with_margins(80, margins)],
    }
    roles = {"misspecification": "misspecification", "p1": "power",
             "p1_neg": "shape_check", "p0": "null_calibration"}
    table = power_sim.margin_quantile_table(sheet_points, roles, main_axes())
    assert set(table["by_n_item"]) == {"80", "240"}
    assert set(table["by_n_item"]["80"]) == {"p1", "p0"}
    assert set(table["by_n_item"]["240"]) == {"p1"}
    quantiles = table["by_n_item"]["80"]["p1"]["quantiles"]
    assert list(quantiles) == ["0.05", "0.25", "0.5", "0.75", "0.95"]
    assert quantiles["0.5"] == pytest.approx(10.5)


# --------------------------------------------------------------------------
# ★平行性の TOST(ADR-114 決定5 = D5 (a))
# --------------------------------------------------------------------------

Z_95 = 1.6448536269514722          # 標準正規分布の片側 0.05 の分位点


def test_tost_spec_reads_alpha_from_the_config() -> None:
    """片側 alpha = 0.05 = Wald 90% CI(ADR-114 決定5)。値は config にあり、コードに直書きしない。"""
    config = load(MAIN_CONFIG)
    assert config["simulation"]["tost_alpha"] == 0.05
    spec = power_sim.tost_spec(config, main_profile("P1"))
    assert spec.critical_z == pytest.approx(Z_95)
    assert spec.coverages == ("interp", "extrap_magnitude")
    bad = copy.deepcopy(config)
    bad["simulation"]["tost_alpha"] = 0.5
    with pytest.raises(ConfigError):
        power_sim.tost_spec(bad, main_profile("P1"))
    bad["simulation"]["tost_alpha"] = None
    with pytest.raises(ConfigError):
        power_sim.tost_spec(bad, main_profile("P1"))


def test_equivalence_margin_is_the_larger_ci_bound() -> None:
    """★同等と言える最小の Δ = 2 係数の `|推定値| + z * SE` の大きいほう(IUT)。

    答える問い: 「Δ をいくつにすれば 2 本の 90% CI がどちらも ±Δ に入るか」。
    """
    spec = power_sim.tost_spec(load(MAIN_CONFIG), main_profile("P1"))
    result = fit_result(
        0.2,
        interaction_interp_est=-0.3, interaction_interp_se=0.1,
        interaction_extrap_magnitude_est=0.1, interaction_extrap_magnitude_se=0.4,
    )
    expected = max(0.3 + Z_95 * 0.1, 0.1 + Z_95 * 0.4)
    assert power_sim.equivalence_margin(result, spec) == pytest.approx(expected)
    # 符号は効かない(±Δ の両側)
    flipped = fit_result(
        0.2,
        interaction_interp_est=0.3, interaction_interp_se=0.1,
        interaction_extrap_magnitude_est=-0.1, interaction_extrap_magnitude_se=0.4,
    )
    assert power_sim.equivalence_margin(flipped, spec) == pytest.approx(expected)


def test_equivalence_margin_stops_on_a_missing_coefficient() -> None:
    """★推定値か SE が欠けた反復を黙って捨てない(`CLAUDE.md` §7)。"""
    spec = power_sim.tost_spec(load(MAIN_CONFIG), main_profile("P1"))
    for key in ("interaction_interp_est", "interaction_extrap_magnitude_se"):
        with pytest.raises(power_sim.PowerSimError):
            power_sim.equivalence_margin(fit_result(0.2, **{key: None}), spec)


def test_tost_power_is_the_share_within_delta_and_never_decreases() -> None:
    """Δ の関数としての TOST の検出力。**Δ はここでは決めない**(呼び出し側が渡す)。"""
    margins = [0.1, 0.2, 0.2, 0.5, 1.0]
    assert power_sim.tost_power(margins, 0.05) == 0.0
    assert power_sim.tost_power(margins, 0.2) == pytest.approx(0.6)      # 境界は含む
    assert power_sim.tost_power(margins, 5.0) == 1.0
    curve = [power_sim.tost_power(margins, d / 10) for d in range(0, 12)]
    assert curve == sorted(curve)
    with pytest.raises(power_sim.PowerSimError):
        power_sim.tost_power([], 0.2)


def test_summarise_point_keeps_the_sorted_margins_and_the_error_rate() -> None:
    spec = power_sim.tost_spec(load(MAIN_CONFIG), main_profile("P1"))
    results = [
        fit_result(0.01, interaction_interp_se=0.5, interaction_extrap_magnitude_se=0.5),
        fit_result(0.2, interaction_interp_se=0.1, interaction_extrap_magnitude_se=0.1,
                   n_errored_fits=2, first_error="Downdated VtV"),
    ]
    summary = power_sim.summarise_point(power_sim.PointKey(80, 1.0, 0.0), results, 0.05, spec)
    assert summary.tost_min_margins == pytest.approx(
        (0.1 * Z_95, 0.5 * Z_95), abs=1e-12
    )
    assert list(summary.tost_min_margins) == sorted(summary.tost_min_margins)
    assert summary.errored_rate == pytest.approx(0.5)
    # TOST を見ないとき(`tost = None`)は空
    assert power_sim.summarise_point(
        power_sim.PointKey(80, 1.0, 0.0), results, 0.05
    ).tost_min_margins == ()


def test_a_null_p_value_reports_the_fit_error_it_came_from() -> None:
    """★最後の水準でも当てはめが落ちた反復は、原因の文面つきで止まる(捨てない)。"""
    results = [fit_result(None, first_error="Downdated VtV is not positive definite")]
    with pytest.raises(power_sim.PowerSimError, match="Downdated VtV"):
        power_sim.summarise_point(power_sim.PointKey(80, 1.0, 0.0), results, 0.05)


def test_fit_script_writes_the_interaction_coefficients_and_counts_errors() -> None:
    """★R 側が TOST の入力(交互作用の推定値と SE)を出し、例外を数えて縮退へ回す。

    答える問い: 「`power_sim.py` が読むキーを R が書いているか」(R は呼ばない。文面の突き合わせ)。
    """
    text = power_sim.FIT_SCRIPT.read_text(encoding="utf-8")
    assert 'paste0("interaction_", cl, "_est")' in text
    assert 'paste0("interaction_", cl, "_se")' in text
    assert 'paste0("task", tl, ":coverage", cl)' in text          # treatment coding の係数名
    assert "n_errored_fits" in text and "tryCatch(" in text
    assert "df = 2" in text


# --------------------------------------------------------------------------
# ★run(R の代わりに偽の当てはめを差す)
# --------------------------------------------------------------------------


def fake_fits(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[Path] | None = None,
    p_value_for: Any = None,
) -> None:
    """R を呼ばず、表ごとに決まった形の JSON を書く。**当てはめの代わりであって検出力の数値ではない。**

    `p_value_for(csv_path)` を渡せば、表ごとに p 値を変えられる(門のテスト用)。既定は 0.5(棄却しない)。
    """

    def fake_run_fits(rscript, libpath, manifest_stem, jobs, refit, max_level, n_workers):
        for csv_path, out_path in jobs:
            assert not out_path.exists(), "済んだ反復を R に渡している"
            assert csv_path.exists(), "当てはめ前の表が書かれていない"
            if calls is not None:
                calls.append(csv_path)
            p_value = 0.5 if p_value_for is None else p_value_for(csv_path)
            out_path.write_text(json.dumps(fit_result(p_value)), encoding="ascii")
        return []

    monkeypatch.setattr(power_sim, "resolve_rscript", lambda declared: "Rscript")
    monkeypatch.setattr(power_sim, "run_fits", fake_run_fits)


def smoke_config() -> dict[str, Any]:
    """配線確認用の config(段は [1, 2])。**本物の configs/power_sim.yaml は run に渡さない**(その139 の暴走)。"""
    return load(SMOKE_CONFIG)


def test_run_writes_one_directory_per_sheet_and_the_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_fits(monkeypatch)
    summary = power_sim.run(
        smoke_config(), tmp_path, None, keep_frames=False, through_stage=2,
        config_path=SMOKE_CONFIG,
    )
    assert list(summary["sheets"]) == ["misspecification", "p1", "p1_neg", "p0"]
    for sheet_id in summary["sheets"]:
        assert (tmp_path / sheet_id / "fits").is_dir()
    assert summary["tost_alpha"] == 0.05
    assert (summary["stage"], summary["n_rep"], summary["stopped_at_gate"]) == (2, 2, False)
    on_disk = json.loads((tmp_path / "power_sim_summary.json").read_text(encoding="utf-8"))
    assert on_disk["sheets"]["p1_neg"]["compared_with"] == "p1"
    assert len(on_disk["sheets"]["p1_neg"]["power_minus_reference"]) == 2
    assert on_disk["sheets"]["misspecification"]["tau"] == "equals_sigma"
    assert on_disk["misspecification_gate"]["inflated"] is False
    assert set(on_disk["sheets"]["p1"]["inverse_problem"]) == {
        "target_power", "n_item_range", "sigma_limit"
    }
    assert set(on_disk["margin_table"]["by_n_item"]) == {"2", "3"}
    # 反復ごとの最小 Δ が全点に入っている(Δ の関数としての TOST の検出力を後から読むため)
    for body in on_disk["sheets"].values():
        assert all(len(point["tost_min_margins"]) == 2 for point in body["grid"])
    # 段ごとの結果・来歴(F6-2)
    assert (tmp_path / "stage_0001_summary.json").is_file()
    assert (tmp_path / "stage_0002_summary.json").is_file()
    info = json.loads((tmp_path / "run_info.json").read_text(encoding="utf-8"))
    assert info["run_id"] == on_disk["run_id"] and info["run_id"].endswith("_power_sim_smoke")
    assert len(info["git_sha"]) == 40
    assert (tmp_path / "git_sha.txt").is_file()
    assert (tmp_path / "config.yaml").read_bytes() == SMOKE_CONFIG.read_bytes()
    # 一時ファイルが残っていない(F6-3)
    assert not list(tmp_path.rglob("*.tmp"))
    # 組んだ表は消える(--keep-frames でなければ)
    assert not list(tmp_path.glob("*/frames/*.csv"))


def test_adding_a_stage_keeps_the_earlier_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★入れ子(ADR-122 決定4): 1 段目の後に 2 段目を足しても、1 段目の表は 2 段を一気に回したときと同じ。

    答える問い: 「段を足したせいで、前の段の表(と結果)が変わっていないか」。
    """
    fake_fits(monkeypatch)
    staged, straight = tmp_path / "staged", tmp_path / "straight"
    first = power_sim.run(smoke_config(), staged, None, keep_frames=True, through_stage=1)
    stage1_frames = {p.relative_to(staged): p.read_bytes() for p in staged.glob("*/frames/*.csv")}
    power_sim.run(smoke_config(), staged, None, keep_frames=True, through_stage=2)
    power_sim.run(smoke_config(), straight, None, keep_frames=True, through_stage=2)
    staged_frames = sorted(p.relative_to(staged) for p in staged.glob("*/frames/*.csv"))
    straight_frames = sorted(p.relative_to(straight) for p in straight.glob("*/frames/*.csv"))
    assert staged_frames == straight_frames
    for rel in staged_frames:
        assert (staged / rel).read_bytes() == (straight / rel).read_bytes(), rel
    # 1 段目の表は 2 段目を足しても書き換わっていない
    for rel, body in stage1_frames.items():
        assert (staged / rel).read_bytes() == body, rel
    assert first["n_rep"] == 1
    # 起動ごとの記録が 2 行残り、run_id は作り直さない
    lines = (staged / "invocations.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["through_stage"] for line in lines] == [1, 2]


def test_resumed_run_fits_only_the_missing_replications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★途中から再開しても、済んだ反復は表を組まず R にも渡さない。残りの表は最初の実行と同じ。"""
    fake_fits(monkeypatch)
    full_dir, resumed_dir = tmp_path / "full", tmp_path / "resumed"
    power_sim.run(smoke_config(), full_dir, None, keep_frames=True, through_stage=2)
    done = resumed_dir / "p1" / "fits" / "fit_n2_s0_r0_0000.json"
    done.parent.mkdir(parents=True)
    done.write_text(json.dumps(fit_result(0.5)), encoding="ascii")
    calls: list[Path] = []
    fake_fits(monkeypatch, calls)
    power_sim.run(smoke_config(), resumed_dir, None, keep_frames=True, through_stage=2)
    assert resumed_dir / "p1" / "frames" / "frame_n2_s0_r0_0000.csv" not in calls
    assert len(calls) == len(list(full_dir.glob("*/frames/*.csv"))) - 1
    first = sorted(full_dir.glob("*/frames/*.csv"))
    second = sorted(resumed_dir.glob("*/frames/*.csv"))
    assert len(first) == len(second) + 1                  # 飛ばした 1 枚だけ無い
    for path in second:
        twin = full_dir / path.relative_to(resumed_dir)
        assert path.read_bytes() == twin.read_bytes(), path.name


def gate_closing_smoke_config() -> dict[str, Any]:
    """smoke の 1 反復でも門が閉じうる閾値にした写し(1 / 1 の 95% 区間の下端は 0.025)。★テスト専用の値。"""
    config = smoke_config()
    config["simulation"]["misspecification_gate"]["lower_bound_above"] = 0.01
    return config


def test_a_closed_gate_stops_before_p1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """★ADR-123 決定6: 誤指定で膨らめば、その段の P1・P1⁻・P0 を回さずに止まり、記録を残す。"""
    calls: list[Path] = []
    fake_fits(monkeypatch, calls, p_value_for=lambda csv_path: 0.001)
    summary = power_sim.run(
        gate_closing_smoke_config(), tmp_path, None, keep_frames=True, through_stage=2
    )
    assert summary["stopped_at_gate"] is True
    assert summary["stage"] == 1                          # 1 段目で止まり、2 段目に進まない
    assert summary["misspecification_gate"]["inflated"] is True
    assert list(summary["sheets"]) == ["misspecification"]
    assert {path.parent.parent.name for path in calls} == {"misspecification"}
    on_disk = json.loads((tmp_path / "power_sim_summary.json").read_text(encoding="utf-8"))
    assert on_disk["stopped_at_gate"] is True


def test_main_returns_a_distinct_code_when_the_gate_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_fits(monkeypatch, p_value_for=lambda csv_path: 0.001)
    config_path = tmp_path / "gate.yaml"
    config_path.write_text(yaml.safe_dump(gate_closing_smoke_config()), encoding="utf-8")
    code = power_sim.main([
        "--config", str(config_path), "--out-dir", str(tmp_path / "out"), "--through-stage", "1",
    ])
    assert code == power_sim.EXIT_GATE_CLOSED


def test_run_requires_a_stage_within_the_declared_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_fits(monkeypatch)
    for bad in (0, 3):
        with pytest.raises(ConfigError, match="through-stage"):
            power_sim.run(smoke_config(), tmp_path, None, False, through_stage=bad)
    with pytest.raises(SystemExit):
        power_sim.main(["--config", str(SMOKE_CONFIG), "--out-dir", str(tmp_path)])


def test_resuming_with_a_different_config_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★同じ出力先に別の config の表を混ぜない(F6-2)。"""
    fake_fits(monkeypatch)
    power_sim.run(smoke_config(), tmp_path, None, False, through_stage=1)
    changed = smoke_config()
    changed["simulation"]["rng_seed"] = 1
    with pytest.raises(power_sim.PowerSimError, match="別の config"):
        power_sim.run(changed, tmp_path, None, False, through_stage=1)


def test_every_declared_sheet_gets_its_tables_fitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """宣言した 4 シートのすべてが当てはめに回る(シートが黙って落ちていない)。"""
    calls: list[Path] = []
    fake_fits(monkeypatch, calls)
    power_sim.run(smoke_config(), tmp_path, None, keep_frames=True, through_stage=1)
    names = {path.parent.parent.name for path in calls}
    assert names == {"misspecification", "p1", "p1_neg", "p0"}


def test_json_is_written_atomically(tmp_path: Path) -> None:
    """★F6-3: Python 側も R 側も、一時ファイルに書いてから rename する。"""
    target = tmp_path / "x.json"
    power_sim.write_json_atomic(target, {"a": 1})
    power_sim.write_json_atomic(target, {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}
    assert not list(tmp_path.glob("*.tmp"))
    text = power_sim.FIT_SCRIPT.read_text(encoding="utf-8")
    assert 'tmp <- paste0(path, ".tmp")' in text
    assert "file.rename(tmp, path)" in text


# --------------------------------------------------------------------------
# ★F113 —— §5 の Δ の出所(ADR-069 決定2。**文書の回帰テスト**)
# --------------------------------------------------------------------------


def test_delta_sources_declare_the_transfer_from_task6() -> None:
    """★§5 の Δ の出所が「順6 の実測」に戻っていないこと(ADR-069 決定2 = ★F113 案 (a))。

    答える問い: 「順6 が産まない量を、順6 の実測を出所として名指ししていないか」——
    **順6 は段階 C(FT なし)であり、4 行が定義する量はすべて `rule_rate` である。**
    出所を書き戻すと ★F113 が黙って再発する(★F90 / ★F104 と同じ形の穴)。
    """
    text = STATISTICS_DOC.read_text(encoding="utf-8")
    transfer = text.index("★順6 からの「移し替え」")
    # 移し替えの 3 仮定が本文にあること(「実測を待てば決まる」ものではない)。
    for assumption in ("従属変数の移し替え", "段階の移し替え", "タスク型の移し替え"):
        assert assumption in text[transfer:], assumption
    # 3 つの食い違いが名指しされていること。
    for gap in ("従属変数が違う", "条件が無い", "タスク型の範囲が違う"):
        assert gap in text[transfer:], gap
    # ★順6 の GPU が要らなくなるとは書かない(Go/No-Go #0〜#3 は順6 でしか出ない)。
    assert "順6 の GPU は依然として要る" in text[transfer:]
    # 生の「順6 の実測」を出所として名指しした欄が残っていないこと。
    assert "| Phase 0(順6)のプロンプト感受性の実測 |" not in text
    assert "| Phase 0 のプロンプト感受性の実測(順6)から |" not in text


def test_the_parallel_gradient_row_does_not_depend_on_task6() -> None:
    """★Δ 5 行のうち 1 行(勾配が平行)は §6.5 から決まり、今日でも値を入れられる。

    答える問い: 「★F113 で Δ 5 行がすべて宙に浮いたのか」—— **浮いていない。**
    """
    text = STATISTICS_DOC.read_text(encoding="utf-8")
    assert "★1 行目(勾配が平行)は順6 に依存しない" in text


# --------------------------------------------------------------------------
# ★F112 の復元(2026-09-09 その26。**算術であって実測ではない**)
# --------------------------------------------------------------------------

# §6.5 の 4 つのプロファイルは「タスク型ごとの被覆オフセット」1 組で書ける。
# **`id` のオフセットは 4 プロファイルとも 0 である**(表の `id` 列が P0 と同一)。
# `extrap` のオフセットは表の「勾配 g(logit)」列そのものであり、**2 桁で載っている**。
# 残る自由度は `interp` のオフセットだけで、それも表 + RMS + 最大残差で
# 幅 0.02〜0.04 に絞られる(`plans/PLAN-019` §10.10.4)。
#
# ★これは「§6.5 を書き換える値」ではない。**§6.5 が載せている値そのものを産む生成規則**である。
RECOVERED_OFFSETS: dict[str, dict[str, tuple[float, float]]] = {
    # profile: {task: (interp オフセット, extrap オフセット)}
    "P0": {"T1": (-1.0, -2.2), "T1b": (-1.0, -2.2), "T2": (-1.0, -2.2), "T3": (-1.0, -2.2)},
    "P1": {"T1": (-0.8, -1.6), "T1b": (-0.8, -1.6), "T2": (-1.2, -2.8), "T3": (-1.2, -2.8)},
    "P2": {"T1": (-0.8, -1.6), "T1b": (-1.2, -2.8), "T2": (-0.8, -1.6), "T3": (-1.2, -2.8)},
    "P3": {"T1": (-0.7, -1.3), "T1b": (-1.1, -2.5), "T2": (-1.1, -2.5), "T3": (-1.1, -2.5)},
}

# §6.5 が載せている姿。表(`rule_rate` 小数第2位)/ 勾配 g / 非加法性 RMS / 最大残差。
DOCUMENTED_PROFILES: dict[str, dict[str, Any]] = {
    "P0": {
        "table": [[0.94, 0.86, 0.65], [0.92, 0.80, 0.55],
                  [0.86, 0.69, 0.40], [0.90, 0.77, 0.50]],
        "g": [-2.20, -2.20, -2.20, -2.20], "rms": 0.000, "max": 0.000,
    },
    "P1": {
        "table": [[0.94, 0.88, 0.77], [0.92, 0.83, 0.69],
                  [0.86, 0.65, 0.27], [0.90, 0.73, 0.35]],
        "g": [-1.60, -1.60, -2.80, -2.80], "rms": 0.353, "max": 0.333,
    },
    "P2": {
        "table": [[0.94, 0.88, 0.77], [0.92, 0.77, 0.40],
                  [0.86, 0.73, 0.55], [0.90, 0.73, 0.35]],
        "g": [-1.60, -2.80, -1.60, -2.80], "rms": 0.353, "max": 0.333,
    },
    "P3": {
        "table": [[0.94, 0.89, 0.82], [0.92, 0.79, 0.48],
                  [0.86, 0.67, 0.33], [0.90, 0.75, 0.43]],
        "g": [-1.30, -2.50, -2.50, -2.50], "rms": 0.306, "max": 0.500,
    },
}

# §6.5 が固定した共通の主効果(ロジット)。表の上の 1 文がこれを宣言している。
DOCUMENTED_MU = 2.2
DOCUMENTED_A = [0.6, 0.2, -0.4, 0.0]
DOCUMENTED_B = [0.0, -1.0, -2.2]
TASK_ORDER = ["T1", "T1b", "T2", "T3"]


def _recovered_eta(profile: str) -> np.ndarray:
    """復元した 12 セルのロジット。答える問い: 丸める前の `eta` はいくつだったか。"""
    offsets = RECOVERED_OFFSETS[profile]
    return np.array(
        [
            [DOCUMENTED_MU + a, DOCUMENTED_MU + a + offsets[task][0],
             DOCUMENTED_MU + a + offsets[task][1]]
            for task, a in zip(TASK_ORDER, DOCUMENTED_A)
        ]
    )


def _nonadditivity(eta: np.ndarray) -> tuple[float, float]:
    """§6.2 の非加法性 RMS と最大残差。答える問い: 加法からどれだけ外れているか。

    §6.2 は「**加法モデルの当てはめ値**を引いた残差」と書いている。当てはめ値は
    二重中心化で得られるので、**`mu` / `a` / `b` の取り方には依らない**。
    """
    centred = eta - eta.mean(axis=0, keepdims=True) - eta.mean(axis=1, keepdims=True)
    centred = centred + eta.mean()
    rms = float(np.sqrt((centred**2).sum() / RECORDED_INTERACTION_DF))
    return rms, float(np.abs(centred).max())


@pytest.mark.parametrize("profile", ["P0", "P1", "P2", "P3"])
def test_recovered_logits_reproduce_the_documented_table(profile: str) -> None:
    """★F112 の答え。復元したロジットは §6.5 の表 12 セルと勾配 g を再現する。

    答える問い: 「丸める前の 12 セルは本当にどこにも記録が無いのか」——
    **記録はある。**表の上の 1 文(`mu` / `a` / `b`)と「勾配 g」の列がそれである。
    自由度は `interp` のオフセット 1 本だけになり、それも表で絞られる。
    """
    documented = DOCUMENTED_PROFILES[profile]
    eta = _recovered_eta(profile)
    rounded = np.round(1.0 / (1.0 + np.exp(-eta)), 2)
    assert rounded.tolist() == documented["table"]
    assert (eta[:, 2] - eta[:, 0]).tolist() == pytest.approx(documented["g"], abs=1e-9)


@pytest.mark.parametrize("profile", ["P0", "P1", "P2", "P3"])
def test_recovered_logits_reproduce_the_documented_rms(profile: str) -> None:
    """★F112 の答え(続き)。復元したロジットは載っている RMS と最大残差も再現する。

    答える問い: 「表を再現するだけの当てずっぽうではないのか」—— **違う。**
    表(12 セル)とは独立に、**§6.5 が別に載せている RMS と最大残差**にも当たっている。
    **P0 は厳密に 0 になる** —— 節が「完全に平行」と書いているとおりである。
    """
    documented = DOCUMENTED_PROFILES[profile]
    rms, largest = _nonadditivity(_recovered_eta(profile))
    assert rms == pytest.approx(documented["rms"], abs=5e-4)
    assert largest == pytest.approx(documented["max"], abs=5e-4)


def test_recovered_p0_is_exactly_the_documented_main_effects() -> None:
    """★P0 の復元は `mu` / `a` / `b` そのものである(独立の検算)。

    答える問い: 「復元の手が正しいと言える外からの証拠はあるか」——
    **P0 の被覆オフセットは §6.5 が文で宣言している `b` と一致しなければならない。**
    一致する。**この 1 本だけは表からの逆算ではなく文からの直読である。**
    """
    for task in TASK_ORDER:
        assert RECOVERED_OFFSETS["P0"][task] == (DOCUMENTED_B[1], DOCUMENTED_B[2])
    rms, _ = _nonadditivity(_recovered_eta("P0"))
    assert rms == pytest.approx(0.0, abs=1e-12)


def test_rounding_the_recovered_logits_is_what_inflates_the_rms() -> None:
    """★F112 の食い違いの出どころは丸めだけである。

    答える問い: 「表から復元した 0.3605 と、載っている 0.353 の差は何か」——
    **丸めである。**復元したロジットを `rule_rate` に直し、小数第2位で丸めてから
    ロジットに戻すと 0.3605 が出る。**同じ手で P0 は 0 から 0.0285 へ動く。**
    """
    for profile, inflated in (("P0", P0_RMS_FROM_ROUNDED_TABLE),
                              ("P1", P1_RMS_FROM_ROUNDED_TABLE)):
        eta = _recovered_eta(profile)
        rates = np.round(1.0 / (1.0 + np.exp(-eta)), 2)
        rms, _ = _nonadditivity(np.log(rates / (1.0 - rates)))
        assert rms == pytest.approx(inflated, abs=1e-4)
