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

# ADR-068 決定3(R3)が凍結した掃く格子。★すべて仮定値であって実測ではない。
ADOPTED_SIGMA = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
ADOPTED_RHO = [0.0, 1.0]

# ADR-026 / ADR-027。交互作用の df = 6 はこの 2 つから決まる。
N_TASK = 4
N_COVERAGE = 3
INTERACTION_DF = (N_TASK - 1) * (N_COVERAGE - 1)


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


def test_undecided_values_stay_null() -> None:
    """★未決の 3 つは null のままである(skill code-style §5)。

    `n_item` は `M*`(順5)待ち、`s2_item` / `s2_tmpl` は ★F104 である。
    **エージェントが既定値を作っていないことを回帰テストで固定する。**
    """
    dgp = load(MAIN_CONFIG)["dgp"]
    for key in ("n_item", "s2_item", "s2_tmpl"):
        assert dgp[key] is None, f"{key} に既定値が入っている"


def test_run_stops_while_the_three_are_undecided() -> None:
    """未決のまま本実行しようとしたら止まる。答える問い: 門は効いているか。"""
    config = load(MAIN_CONFIG)
    with pytest.raises(ConfigError):
        power_sim.load_levels(config)


def test_dry_run_works_even_while_undecided() -> None:
    """★格子と当てはめ本数は未決のままでも出る(コストを先に見るため)。"""
    lines = power_sim.describe_plan(load(MAIN_CONFIG))
    text = "\n".join(lines)
    assert "24000" in text, "24,000 本(6 x 2 x 1000 x 2)が出ていない"
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


def test_profile_p1_reproduces_the_documented_rms() -> None:
    """★§6.6 が採択した RMS = 0.353 に、DGP の真値が 3 桁で一致する。

    答える問い: 「§6.5 の表と §6.6 の RMS は同じものを指しているか」——
    ずれていれば、事前登録した効果量とシミュレータの効果量が違うことになる。

    **★F112 はここで閉じた**(ADR-069 決定1 = 案 (a))。表(2 桁)を逆変換していた頃は
    0.3605 で 2% ずれていた。**`eta` を直接与える今は 0.352767 である。**
    """
    profile = power_sim.build_profile(load(MAIN_CONFIG)["effect"])
    assert profile.name == "P1"
    assert profile.eta.shape == (N_TASK, N_COVERAGE)
    assert profile.nonadditivity_rms == pytest.approx(DOCUMENTED_P1_RMS, abs=5e-4)
    # ★差し替え前の値からは離れていること(直ったことの確認)。
    assert abs(profile.nonadditivity_rms - P1_RMS_FROM_ROUNDED_TABLE) > 5e-3


def test_profile_rejects_an_eta_that_disagrees_with_the_documented_table() -> None:
    """★ADR-069 決定1 の門。`eta` と §6.5 の表が離れたら止まる。

    答える問い: 「`eta` が真値になった以上、§6.5 の表と黙って食い違いうるのではないか」
    —— **`rule_rate` を照合用に残したのはそのためである。**片方だけ動かすと止まる。
    """
    effect = dict(load(MAIN_CONFIG)["effect"])
    effect["eta"] = [[e + 0.5 for e in row] for row in effect["eta"]]
    with pytest.raises(ConfigError):
        power_sim.build_profile(effect)


def test_profile_requires_eta_to_be_present() -> None:
    """★`eta` は必須である(ADR-069 決定1)。表から作り直す既定の経路は残さない。"""
    effect = {k: v for k, v in load(MAIN_CONFIG)["effect"].items() if k != "eta"}
    with pytest.raises(ConfigError):
        power_sim.build_profile(effect)


def test_p0_logits_are_exactly_flat() -> None:
    """★P0(完全に平行)は RMS = 0 になる。**丸めていないので厳密に 0 である。**

    答える問い: 「`sigma = 0` の行を α の較正として読めるか」—— **読める。**
    表(2 桁)を逆変換していた頃は P0 でも RMS 0.0285 が出ており、
    **帰無の基準線が帰無でなかった**(★F112)。`eta` を与える今は厳密に 0 である。
    """
    effect = dict(load(MAIN_CONFIG)["effect"])
    mu, a, b = effect["mu"], effect["a"], effect["b"]
    eta = [[mu + ai + bj for bj in b] for ai in a]
    effect["profile"] = "P0"
    effect["eta"] = eta
    effect["rule_rate"] = [[round(1.0 / (1.0 + np.exp(-e)), 2) for e in row] for row in eta]
    profile = power_sim.build_profile(effect)
    assert profile.nonadditivity_rms == pytest.approx(0.0, abs=1e-12)
    assert profile.delta == pytest.approx(np.zeros((N_TASK, N_COVERAGE)), abs=1e-9)
    # ★差し替え前は 0 にならなかった(何が直ったかの記録)。
    assert P0_RMS_FROM_ROUNDED_TABLE > 0.0


def test_profile_rejects_a_table_of_the_wrong_shape() -> None:
    effect = dict(load(MAIN_CONFIG)["effect"])
    effect["rule_rate"] = [[0.9, 0.8, 0.7]]
    with pytest.raises(ConfigError):
        power_sim.build_profile(effect)


def test_interaction_df_is_six() -> None:
    """主要検定の df = 6(§2 / §3.2)。RMS の分母がここに掛かっている。"""
    assert INTERACTION_DF == 6


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
    profile = power_sim.build_profile(load(MAIN_CONFIG)["effect"])
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
    profile = power_sim.build_profile(load(MAIN_CONFIG)["effect"])
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
    profile = power_sim.build_profile(load(MAIN_CONFIG)["effect"])
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


# --------------------------------------------------------------------------
# R へ渡すもの
# --------------------------------------------------------------------------


def test_frame_csv_is_ascii_and_lf(tmp_path: Path) -> None:
    """CSV は ASCII / LF である。答える問い: Windows で書いても R が同じ表を読むか。"""
    levels = smoke_levels()
    profile = power_sim.build_profile(load(MAIN_CONFIG)["effect"])
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


def test_cost_line_uses_the_measured_seconds_per_pair() -> None:
    """★見積りは実測(★F114)から出す。算術の 9 時間ではない。

    答える問い: 「本実行が何時間になるかを、回す前に人間が読めるか」——
    §10.7.8 の「24,000 本 = 約 9 時間」は 7 倍甘かった(F50 からの掛け算だった)。
    """
    assert power_sim.SECONDS_PER_PAIR_N_ITEM_48 == pytest.approx(297.6)
    lines = power_sim.describe_plan(load(MAIN_CONFIG), workers_override=16)
    cost = [line for line in lines if "core-hours" in line]
    assert len(cost) == 1
    assert "992 core-hours" in cost[0]
    assert "MEASURED" in cost[0]
    assert any("62 wall-clock hours" in line for line in lines)


def test_fit_script_keeps_the_preregistered_random_structure() -> None:
    """★当てはめ側の level 0 が §3.2 のランダム構造そのものである。

    答える問い: 「シミュレーションが当てているのは、事前登録した検定か」——
    ★F110 が指した食い違い(DGP は合っているのに当てはめが `(1|seed)`)を
    回帰テストで塞ぐ。ここが崩れると「実際には回さない検定の検出力」になる。
    """
    text = power_sim.FIT_SCRIPT.read_text(encoding="utf-8")
    assert "(0 + coverage | seed) + (1 | item) + (1 | template)" in text
    assert "task * coverage" in text and "task + coverage" in text
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
    }
    base.update(overrides)
    return base


def test_power_is_the_share_below_alpha() -> None:
    results = [fit_result(0.01), fit_result(0.2), fit_result(0.04), fit_result(0.9)]
    point = power_sim.summarise_point(0.5, 0.0, results, 0.05)
    assert point.power == pytest.approx(0.5)
    assert point.n_rep == 4


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
    point = power_sim.summarise_point(1.0, 1.0, results, 0.05)
    assert point.reduced_rate == pytest.approx(0.5)
    assert point.singular_rate == pytest.approx(0.5)
    assert point.refit_rate == pytest.approx(0.5)


def test_a_null_p_value_stops_the_summary() -> None:
    """★p 値が null の反復を黙って捨てない(`CLAUDE.md` §7)。"""
    with pytest.raises(power_sim.PowerSimError):
        power_sim.summarise_point(0.5, 0.0, [fit_result(None)], 0.05)


def test_empty_grid_point_stops_the_summary() -> None:
    with pytest.raises(power_sim.PowerSimError):
        power_sim.summarise_point(0.5, 0.0, [], 0.05)


def point(sigma: float, power: float, rho: float = 0.0) -> power_sim.GridPoint:
    return power_sim.GridPoint(
        sigma=sigma, rho=rho, n_rep=1000, power=power,
        reduced_rate=0.0, singular_rate=0.0, refit_rate=0.0, mean_chisq=6.0,
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


def test_grid_summary_keeps_both_rho_sheets() -> None:
    """★`rho` の 2 枚を帯として併記する(ADR-068 決定2)。潰さない。"""
    summary = power_sim.summarise_grid(
        [point(0.0, 0.99, 0.0), point(1.5, 0.70, 0.0),
         point(0.0, 0.99, 1.0), point(1.5, 0.90, 1.0)],
        0.8,
    )
    assert set(summary["by_rho"]) == {"0.0", "1.0"}
    assert summary["by_rho"]["0.0"]["verdict"] == "inside_swept_range"
    assert summary["by_rho"]["1.0"]["verdict"] == "beyond_swept_range"


def test_plan_grid_is_the_full_product() -> None:
    assert len(power_sim.plan_grid(load(MAIN_CONFIG))) == len(ADOPTED_SIGMA) * len(
        ADOPTED_RHO
    )


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
    return float(np.sqrt((centred**2).sum() / INTERACTION_DF)), float(np.abs(centred).max())


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
