"""段2 の診断の判定表(PLAN-032 I4。§8.1 R2〜R7。ADR-107 決定3〜6・8 / ADR-108 決定2・3・5〜8)。

答える問い: 「4 腕の掃引の run から、Δ₂・R3 の『届く』・R4 の次の段(T1b と T3 に別々)・R5 の ③-iii を
凍結した規則どおりに機械的に出し、R7 の食い違いでは判定表を出さずに止まるか」

**モデルの重みは 1 度も読まない**(採点器を差し替え、答え方を決めて与える)。**ここに出る Δ₂ は
差し替えた採点器の答え方から算術で決まる値であって、実験結果ではない。**

ここで固定する最重要の性質:
  - **Δ₂ の定義(R2)**: 真値どおりに答えるモデルは Δ₂ = 1、定数で答えるモデルは Δ₂ = 0。
    4 通りの (極性, θ) は固定オフセットの許容表そのもの。組ごとの差の平均は点推定と一致する
  - **線の比べ方(R3)**: 点推定 ≥ 線(線ちょうどは届く)を有理数で厳密に比べる。3 セルすべてで届く
  - **R4 の 4 行と異常の印・R5 の 3 通り**を、本物の run.py の記録の経路を通した run で当てる。
    **T1b と T3 で答え方を変えた run で、次の段・異常の印がタスク型ごとに割れる**(ADR-108 決定8 (a))。
    **1 つの既知性のセルだけ線を下回る run で、その腕は届かない**(同 (b))。
    **本番と同じ件数(160/水準)で、線 0.088 のすぐ両側(56/640・57/640)の Δ₂ を出す**(同 (c))
  - **R6 の区間(ADR-108 決定2)**: [−1, 1] で切る。組ごとの差がすべて同じなら「退化」の印(json と txt)。
    S1 の行に物差しの注記(決定3)
  - **R7**: Δ₂ の水準の件数が違う / A と B の対がそろわない / **A の `prompt` が B の `prompt` の和の部分を
    x の数字に置き換えたものでない**(決定6)/ **R1 の前提(モデル・adapter・batch・上位 k・プール)が
    4 本の記録と食い違う**(決定5。`build_report` を直接呼ぶ経路でも)run では判定表を出さない。
    腕の欠け・重なり・sharpness 欄の食い違い・文面の出どころの取り違え・上位 k の欠けも止める。
    **止める経路の例外は `SharpnessError`**(`R8FitError`・欄の欠けの `KeyError` を包む。決定7)
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import sys
import types
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import yaml

from code import artifacts
from code.analysis import r8_fit, sharpness_fit
from code.analysis.sharpness_fit import SharpnessError
from code.config import load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import run
from code.eval.battery import t3_comparison
from code.eval.forced_choice import ForcedChoice, choose_from_logprobs
from code.tests.test_threshold_sweep_run import CANDIDATE_IDS, stub_capture, write_config
from code.tests.test_top_k import with_filler_top_tokens

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
POOL_CONFIG = CONFIG_DIR / "exp_diag_pool.yaml"
ARMS = sharpness_fit.ARMS

# 小さいプール(1 併合セル 4 組)。**件数を縮めるだけで、組の選び方・θ・下限・文面は本番の config のまま。**
SMALL_PAIRS = 4
SMALL_N_PER_LEVEL = SMALL_PAIRS * 2  # carry 2

# 答え方(Yes と No の対数確率。差は近接同点の幅 0.25 の外)。**実験の値ではない。**
CONFIDENT = (math.log(0.9), math.log(0.1))
# 近接同点(差 0.1 < 0.25)
TIED = (math.log(0.525), math.log(0.475))

# 4 本の run を回した commit(ADR-109 決定1)。**pod の実物と同じ形の記録**にする: 1 行目は sha、`dirty: true`
# (追跡外のファイル)、`git_diff.patch` は 0 バイト。実物は順6b の 7 本・パイロット FT の評価 10 本すべてがこの形。
RUN_SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"


def pod_like_capture(command: Sequence[str]) -> str:
    """git だけ pod の実物と同じ答えを返す `_capture` の差し替え(ほかは `stub_capture`)。

    `rev-parse` は sha、`status` は追跡外のファイルだけ(= `dirty: true`)、`diff HEAD` は追跡ファイルの差分なし。
    """
    if list(command[:2]) == ["git", "rev-parse"]:
        return RUN_SHA
    if list(command[:2]) == ["git", "status"]:
        return "?? data/pool_rebuilt_on_the_pod.jsonl"
    if list(command[:2]) == ["git", "diff"]:
        return ""
    return stub_capture(command)


# --------------------------------------------------------------------------
# 答え方(プロンプト → 真値は、同じ run の項目から引く。重みは読まない)
# --------------------------------------------------------------------------

class Situation(NamedTuple):
    """答え方が見る 1 項目の状況(採点器は文面しか受け取らないので、文面から引き直して渡す)。"""

    item: Any  # 項目(category・params)
    cell: sweep_pool.SweepCell  # 併合セル(タスク型・既知性・carry)
    rank: int  # (タスク型 × 既知性 × 極性 × θ)の群の中の並び(item_id の昇順。0 始まり)


Behavior = Callable[[Situation], tuple[float, float]]  # 状況 -> (yes_logp, no_logp)


def _truthful(situation: Situation) -> tuple[float, float]:
    item = situation.item
    truth = t3_comparison.comparison_answer(
        t3_comparison.item_total(item),
        t3_comparison.polarity_of(item.category),
        int(item.params["threshold"]),
    )
    return CONFIDENT if truth else CONFIDENT[::-1]


def _always_no(situation: Situation) -> tuple[float, float]:
    return CONFIDENT[::-1]


def _truthful_tied_at_zero(situation: Situation) -> tuple[float, float]:
    """真値どおりだが θ = 0 だけ近接同点(答えは Yes 側)。"""
    if situation.item.params["threshold_offset"] == 0:
        return TIED
    return _truthful(situation)


def _by_task(*, t1b: Behavior, t3: Behavior) -> Behavior:
    """タスク型ごとに答え方を変える(ADR-108 決定8 (a))。"""
    by_type = {t3_comparison.T1B: t1b, t3_comparison.T3: t3}

    def behave(situation: Situation) -> tuple[float, float]:
        return by_type[situation.cell.task_type](situation)

    return behave


def _except_cell(base: Behavior, *, task_type: str, coverage: str, instead: Behavior) -> Behavior:
    """1 つの (タスク型 × 既知性) のセルだけ別の答え方にする(ADR-108 決定8 (b))。"""

    def behave(situation: Situation) -> tuple[float, float]:
        cell = situation.cell
        if (cell.task_type, cell.coverage) == (task_type, coverage):
            return instead(situation)
        return base(situation)

    return behave


def _always_no_except_first_correct(k: int) -> Behavior:
    """常に No。ただし gt・θ = −2 の群の先頭 k 件だけ真値(Yes)で答える。

    どのセルでも y = 1 の割合が gt・θ = −2 でだけ (160 − k)/160、ほかは 1(gt)か 0(lt)になるので、
    D(gt, 0) = k/160、ほかの 3 つの D は 0 → **Δ₂ = k/640**(1 セルの 160 件/水準のとき)。
    """

    def behave(situation: Situation) -> tuple[float, float]:
        item = situation.item
        polarity = t3_comparison.polarity_of(item.category)
        if polarity == "gt" and item.params["threshold_offset"] == -2 and situation.rank < k:
            return _truthful(situation)
        return _always_no(situation)

    return behave


def situations_by_prompt(
    pool: run.ThresholdSweepPool, prompts: Mapping[str, str]
) -> dict[str, list[Situation]]:
    """文面 -> その文面で尋ねる項目の状況(A は `{x}` だけなので、同じ文面が複数の項目に当たりうる)。"""
    ranks: dict[tuple[str, str, str, int], int] = {}
    situations: dict[str, list[Situation]] = {}
    for item in sorted(pool.items, key=lambda candidate: candidate.item_id):
        cell = pool.cell_of[item.item_id]
        key = (
            cell.task_type,
            cell.coverage,
            t3_comparison.polarity_of(item.category),
            int(item.params["threshold_offset"]),
        )
        rank = ranks.get(key, 0)
        ranks[key] = rank + 1
        situations.setdefault(prompts[item.item_id], []).append(Situation(item, cell, rank))
    return situations


def behavior_scorer(
    prompt_situations: Mapping[str, list[Situation]], behavior: Behavior
):  # type: ignore[no-untyped-def]
    """文面から状況を引き、決めた答え方で強制選択の結果を返す採点器。

    同じ文面の項目で答え方が割れるなら落ちる(採点器は文面しか見ないので、割れた答え方は再現できない)。
    """

    def answer(prompt: str) -> tuple[float, float]:
        answers = {behavior(situation) for situation in prompt_situations[prompt]}
        assert len(answers) == 1, f"同じ文面の項目で答え方が割れる: {prompt!r}"
        return next(iter(answers))

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        return [
            with_filler_top_tokens(choose_from_logprobs(list(answer(prompt)), CANDIDATE_IDS))
            for prompt in prompts
        ]

    return scorer


# --------------------------------------------------------------------------
# fixture: 小さい診断のプールと、4 腕の run
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def small_pool_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """組の数だけを縮めた診断の掃引プール(パイロット用プールの組み直し 約 8 秒)。"""
    config = load_config(POOL_CONFIG)
    config["eval"]["threshold_sweep"]["pairs_per_cell"] = SMALL_PAIRS
    source = eval_pool.build(config)
    out_dir = tmp_path_factory.mktemp("battery") / "pilot_sweep_diag"
    eval_pool.write_pool(sweep_pool.build_sweep_pool(config, source, "diag"), out_dir)
    return out_dir


def small_arm_config(arm: str, pool_dir: Path) -> dict[str, Any]:
    config = load_config(CONFIG_DIR / f"exp_diag_{arm}.yaml")
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["eval"]["threshold_sweep"]["pairs_per_cell"] = SMALL_PAIRS
    config["sharpness"]["n_per_level"] = SMALL_N_PER_LEVEL
    return config


def execute_arm(config: Mapping[str, Any], behavior: Behavior, run_dir: Path) -> Path:
    """本物の掃引の経路(`execute_threshold_sweep`)で 1 腕を回し、metrics.json のパスを返す。"""
    pool = run.load_threshold_sweep_pool(config)
    prompts = run.threshold_sweep_prompts(config, pool)
    prompt_situations = situations_by_prompt(pool, prompts)
    # 写しの名前は run の glob(`run_*`)に当たらないようにする
    config_path = write_config(config, run_dir.parent / f"config_{run_dir.name}.yaml")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", pod_like_capture)
        run.execute_threshold_sweep(
            config,
            config_path=config_path,
            run_dir=run_dir,
            scorer=behavior_scorer(prompt_situations, behavior),
        )
    return run_dir / "metrics.json"


def execute_scenario(
    root: Path, pool_dir: Path, behaviors: Mapping[str, Behavior], name: str
) -> list[Path]:
    target = root / name
    target.mkdir()
    return [
        execute_arm(small_arm_config(arm, pool_dir), behaviors[arm], target / f"run_{arm}")
        for arm in ARMS
    ]


# 4 行の R4 と R5 を踏む答え方の組(腕 -> 答え方)。
SCENARIOS: dict[str, dict[str, Behavior]] = {
    # A 届く・B 届かない → 分岐 (a)(T1b・T3 とも)。R5 は当てない
    "branch": {"b": _always_no, "a": _truthful, "b_d": _always_no, "a_d": _truthful},
    # A・B 届かない → 前段 FT。B-d が届くので ③-iii を残す
    "pre_ft_keep": {"b": _always_no, "a": _always_no, "b_d": _truthful, "a_d": _always_no},
    # A・B 届かない → 前段 FT。B-d も届かないので ③-iii を置かない
    "pre_ft_drop": {"b": _always_no, "a": _always_no, "b_d": _always_no, "a_d": _always_no},
    # A 届かない・B 届く → 前段 FT は要らない + 異常の印
    "anomaly": {"b": _truthful, "a": _always_no, "b_d": _truthful, "a_d": _always_no},
    # A・B とも届く → 前段 FT は要らない(異常なし)。B の θ = 0 は近接同点
    "both": {"b": _truthful_tied_at_zero, "a": _truthful, "b_d": _truthful, "a_d": _truthful},
    # ★タスク型ごとに割れる(ADR-108 決定8 (a))。T1b は A・B とも届かない(前段 FT。B-d は届く → ③-iii を残す)、
    # T3 は A だけ届く(分岐 (a))
    "split_pre_ft_branch": {
        "b": _always_no,
        "a": _by_task(t1b=_always_no, t3=_truthful),
        "b_d": _truthful,
        "a_d": _always_no,
    },
    # ★T1b は A・B とも届く(前段 FT は要らない)、T3 は A が届かず B が届く(前段 FT は要らない + 異常の印)
    "split_anomaly": {
        "b": _truthful,
        "a": _by_task(t1b=_truthful, t3=_always_no),
        "b_d": _truthful,
        "a_d": _truthful,
    },
    # ★T1b は A・B とも届かない(前段 FT。B-d は届く → ③-iii を残す)、T3 は A が届かず B が届く(前段 FT は要らない
    # + 異常の印)。R5 の 3 つ目の引数を T3 の B に取り違えると、③-iii を残すはずが置かないになる
    # (ADR-109 決定2 = C108-2)
    "split_t3_b_reaches": {
        "b": _by_task(t1b=_always_no, t3=_truthful),
        "a": _always_no,
        "b_d": _truthful,
        "a_d": _always_no,
    },
    # ★1 つの既知性のセルだけ線を下回る(ADR-108 決定8 (b))。B の T1b の extrap_magnitude だけ常に No
    # (R3: 1 つでも下回れば「届かない」。ほかのセルは Δ₂ = 1)
    "one_cell_below": {
        "b": _except_cell(
            _truthful,
            task_type=t3_comparison.T1B,
            coverage="extrap_magnitude",
            instead=_always_no,
        ),
        "a": _truthful,
        "b_d": _truthful,
        "a_d": _truthful,
    },
}


@pytest.fixture(scope="module")
def scenario_runs(
    small_pool_dir: Path, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, list[Path]]:
    root = tmp_path_factory.mktemp("diag_runs")
    return {
        name: execute_scenario(root, small_pool_dir, behaviors, name)
        for name, behaviors in SCENARIOS.items()
    }


def report_of(paths: Sequence[Path]) -> dict[str, Any]:
    runs = [sharpness_fit.load_diag_run(path) for path in paths]
    return sharpness_fit.build_report(runs, count_tokens=len)


# --------------------------------------------------------------------------
# R2 の定義(合成した記録)
# --------------------------------------------------------------------------


def synthetic_records(
    ones: Mapping[tuple[str, int], int], n: int, *, pairs_offset: int = 0
) -> list[dict[str, Any]]:
    """(極性, θ) ごとに n 件、うち `ones` 件が y = 1 の記録(組は (i, 1000 + i))。"""
    records = []
    for (polarity, theta), k in ones.items():
        for i in range(n):
            y = 1 if i < k else 0
            # y = 1 ⇔ gt で No / lt で Yes(揃え方 (a))
            answer = (not y) if polarity == "gt" else bool(y)
            records.append(
                {
                    "item_id": f"{polarity}{theta}_{i}",
                    "polarity": polarity,
                    "threshold_offset": theta,
                    "operands": [i + pairs_offset, 1000 + i],
                    "answer": answer,
                }
            )
    return records


ALL_LEVELS = [(p, t) for p in ("gt", "lt") for t in (-2, -1, 0, 1, 2)]


def test_delta2_terms_are_the_fixed_offsets() -> None:
    """★4 通りの (極性, θ) は固定オフセットの許容表(gt: 0, +1 / lt: +1, +2)。水準は −2〜+2。"""
    assert sharpness_fit.delta2_terms() == (("gt", 0), ("gt", 1), ("lt", 1), ("lt", 2))
    assert set(sharpness_fit.delta2_terms()) == set(t3_comparison.THRESHOLD_RULES)
    assert sharpness_fit.delta2_levels(2) == (-2, -1, 0, 1, 2)


def test_delta2_is_the_mean_of_the_four_differences() -> None:
    """★Δ₂ = ¼ Σ [P̂(θ) − P̂(θ − 2)](有理数)。組ごとの差の平均と一致する。"""
    n = 10
    ones = {level: 0 for level in ALL_LEVELS}
    ones.update({("gt", 0): 7, ("gt", -2): 2, ("gt", 1): 9, ("gt", -1): 3})
    ones.update({("lt", 1): 5, ("lt", 2): 10, ("lt", 0): 1})
    records = synthetic_records(ones, n)
    estimate, terms = sharpness_fit.delta2_point(records, 2)
    expected_terms = {
        "gt:+0": Fraction(7 - 2, n),
        "gt:+1": Fraction(9 - 3, n),
        "lt:+1": Fraction(5 - 0, n),  # lt の θ − 2 = −1 は 0 件
        "lt:+2": Fraction(10 - 1, n),
    }
    assert terms == expected_terms
    assert estimate == sum(expected_terms.values(), Fraction(0)) / 4
    differences = sharpness_fit.per_pair_differences(records, 2)
    assert sum(differences, Fraction(0)) / len(differences) == estimate


def test_delta2_is_none_when_a_level_is_empty() -> None:
    ones = {level: 1 for level in ALL_LEVELS if level != ("lt", 0)}
    estimate, terms = sharpness_fit.delta2_point(synthetic_records(ones, 4), 2)
    assert estimate is None and terms["lt:+2"] is None


def test_per_pair_differences_refuse_mismatched_pairs() -> None:
    """★負例: Δ₂ の (極性, θ) の間で組の集合が違えば止める(R7)。"""
    records = synthetic_records({level: 1 for level in ALL_LEVELS}, 4)
    records[0]["operands"] = [999, 999]
    with pytest.raises(SharpnessError, match="組の集合"):
        sharpness_fit.per_pair_differences(records, 2)


Z_975 = 1.959963984540054  # NormalDist().inv_cdf(0.975)


def test_confidence_interval_is_the_paired_normal_interval() -> None:
    """R6(ADR-108 決定2): 組ごとの差の平均 ± z_{0.975}·sd/√n(端が [−1, 1] の内側にあるとき)。"""
    differences = [Fraction(1, 4)] * 4 + [Fraction(0)] * 4  # 平均 1/8、標準偏差 √(1/56)
    ci = sharpness_fit.confidence_interval(differences, 0.95)
    se = math.sqrt(1 / 56) / math.sqrt(8)
    assert ci["standard_error"] == pytest.approx(se)
    assert ci["low"] == pytest.approx(0.125 - Z_975 * se)
    assert ci["high"] == pytest.approx(0.125 + Z_975 * se)
    assert -1.0 < ci["low"] < ci["high"] < 1.0
    assert ci["degenerate"] is False
    assert ci["n_pairs"] == 8 and ci["level"] == 0.95


def test_confidence_interval_is_cut_at_minus_one_and_one() -> None:
    """★端は [−1, 1] で切る(Δ₂ と組ごとの差の取りうる範囲。R6)。切る前は 1.066 と −1.066。"""
    se = math.sqrt(1 / 3) / 2  # 4 つの値の標準偏差 √(1/3) を √4 で割る
    upper = sharpness_fit.confidence_interval(
        [Fraction(0), Fraction(1), Fraction(1), Fraction(0)], 0.95
    )
    assert upper["high"] == 1.0  # 切る前は 0.5 + z·se ≈ 1.066
    assert upper["low"] == pytest.approx(0.5 - Z_975 * se)
    lower = sharpness_fit.confidence_interval(
        [Fraction(-1), Fraction(0), Fraction(-1), Fraction(0)], 0.95
    )
    assert lower["low"] == -1.0  # 切る前は −0.5 − z·se ≈ −1.066
    assert lower["high"] == pytest.approx(-0.5 + Z_975 * se)


@pytest.mark.parametrize("value", [Fraction(0), Fraction(1, 4), Fraction(1)])
def test_confidence_interval_is_marked_degenerate_when_all_differences_are_equal(
    value: Fraction,
) -> None:
    """★組ごとの差がすべて同じ(sd = 0)なら幅 0 の区間に「退化」の印(`[x, x]` を印なしで出さない)。"""
    ci = sharpness_fit.confidence_interval([value] * 160, 0.95)
    assert ci["degenerate"] is True
    assert ci["standard_error"] == 0.0
    assert ci["low"] == ci["high"] == float(value)
    near = sharpness_fit.confidence_interval([value] * 159 + [Fraction(-1, 2)], 0.95)
    assert near["degenerate"] is False  # 1 組でも違えば退化ではない
    assert near["low"] < near["high"]


def test_confidence_interval_needs_two_pairs() -> None:
    """組が 1 つでは区間を出さない(null。退化の印は付かない)。"""
    ci = sharpness_fit.confidence_interval([Fraction(1)], 0.95)
    assert (ci["low"], ci["high"]) == (None, None)
    assert (ci["standard_error"], ci["degenerate"]) == (None, False)


def _block(**overrides: Any) -> dict[str, Any]:
    """`sharpness` 欄の 1 つの宣言(値は実験の値ではない)。"""
    block = {
        "arm": "b",
        "arm_template_sets": {"b": "eval_main", "a": "diag_explicit", "b_d": "order6b_d", "a_d": "x"},
        "delta2_shift": 2,
        "delta2_line": 0.088,
        "n_per_level": 125,
        "ci_level": 0.95,
        "adapter": None,
        "batch_size": 4,
        "top_k": 20,
    }
    block.update(overrides)
    return block


def _settings(**overrides: Any) -> sharpness_fit.SharpnessSettings:
    return sharpness_fit.load_sharpness_settings({"sharpness": _block(**overrides)}, "test")


def test_the_line_is_compared_exactly_at_the_boundary() -> None:
    """★線ちょうど(Δ₂ = 0.088 = 44/500)は届き、1/500 下は届かない(有理数で比べる)。"""
    settings = _settings()
    assert settings.delta2_line == Fraction(11, 125)
    n = 125
    gaps: dict[str, float] = {}
    for sum_of_k, reaches in ((44, True), (43, False)):
        # 4 つの D の和 = sum_of_k / 125 → Δ₂ = sum_of_k / 500
        ones = {level: 0 for level in ALL_LEVELS}
        ones[("gt", 0)] = sum_of_k
        records = synthetic_records(ones, n)
        gaps = {record["item_id"]: 3.0 for record in records}
        cell = sharpness_fit.cell_delta2(records, settings=settings, gaps=gaps, margin=0.25)
        assert cell["estimate_fraction"] == str(Fraction(sum_of_k, 500))
        assert cell["reaches_line"] is reaches


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"arm": "c"}, "arm"),
        ({"arm_template_sets": {"b": "x"}}, "arm_template_sets"),
        ({"delta2_shift": 0}, "delta2_shift"),
        ({"delta2_shift": True}, "delta2_shift"),
        ({"n_per_level": 1.5}, "n_per_level"),
        ({"delta2_line": "0.088"}, "delta2_line"),
        ({"delta2_line": float("nan")}, "delta2_line"),
        ({"ci_level": 1.0}, "ci_level"),
        ({"adapter": 5}, "adapter"),
        ({"batch_size": 0}, "batch_size"),
        ({"batch_size": True}, "batch_size"),
        ({"batch_size": None}, "batch_size"),
        ({"top_k": 0}, "top_k"),
        ({"top_k": 20.0}, "top_k"),
        ({"top_k": None}, "top_k"),
    ],
)
def test_broken_sharpness_blocks_stop(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(SharpnessError, match=message):
        _settings(**overrides)


def test_the_adapter_declaration_may_be_null_but_not_absent() -> None:
    """★null は「素のモデル」の宣言(R1)。欄ごと無いのは宣言していないので止める。"""
    assert _settings(adapter=None).adapter is None
    assert _settings(adapter="runs/x/adapter").adapter == "runs/x/adapter"
    block = _block()
    del block["adapter"]
    with pytest.raises(SharpnessError, match="adapter"):
        sharpness_fit.load_sharpness_settings({"sharpness": block}, "test")


def test_a_config_without_the_block_stops() -> None:
    with pytest.raises(SharpnessError, match="sharpness"):
        sharpness_fit.load_sharpness_settings({}, "r8_run")


# --------------------------------------------------------------------------
# R3〜R5(規則の表)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "stage", "anomaly"),
    [
        (True, False, sharpness_fit.NEXT_BRANCH_A, False),
        (False, False, sharpness_fit.NEXT_PRE_FT, False),
        (True, True, sharpness_fit.NEXT_NO_PRE_FT, False),
        (False, True, sharpness_fit.NEXT_NO_PRE_FT, True),
    ],
)
def test_next_stage_is_the_r4_table(a: bool, b: bool, stage: str, anomaly: bool) -> None:
    """★R4 の 4 行(ADR-107 決定4 (2))。「A 届かない・B 届く」だけに異常の印。"""
    assert sharpness_fit.next_stage(a, b) == (stage, anomaly)


@pytest.mark.parametrize(
    ("stage", "b_d", "b", "decision"),
    [
        (sharpness_fit.NEXT_PRE_FT, True, False, sharpness_fit.R5_KEEP),
        (sharpness_fit.NEXT_PRE_FT, False, False, sharpness_fit.R5_DROP),
        (sharpness_fit.NEXT_PRE_FT, True, True, sharpness_fit.R5_DROP),
        (sharpness_fit.NEXT_BRANCH_A, True, False, sharpness_fit.R5_NOT_APPLICABLE),
        (sharpness_fit.NEXT_NO_PRE_FT, True, False, sharpness_fit.R5_NOT_APPLICABLE),
    ],
)
def test_r5_applies_only_to_the_pre_ft_stage(stage: str, b_d: bool, b: bool, decision: str) -> None:
    """★R5: T1b が前段 FT のときだけ。B-d が届き B が届かなければ ③-iii を残す。"""
    assert sharpness_fit.r5_decision(stage, b_d, b) == decision


def test_reach_needs_all_three_cells() -> None:
    """★R3: 1 セルでも線を下回れば「届かない」。セルが欠ければ止める。"""
    cells = {coverage: {"reaches_line": True} for coverage in ("id", "interp", "extrap_magnitude")}
    assert sharpness_fit.arm_reaches(cells) is True
    cells["extrap_magnitude"] = {"reaches_line": False}
    assert sharpness_fit.arm_reaches(cells) is False
    del cells["interp"]
    with pytest.raises(SharpnessError, match="interp"):
        sharpness_fit.arm_reaches(cells)


# --------------------------------------------------------------------------
# 本物の記録の経路を通した run(小さいプール)
# --------------------------------------------------------------------------


def test_truthful_answers_give_one_and_constant_answers_give_zero(
    scenario_runs: dict[str, list[Path]],
) -> None:
    """★真値どおり → Δ₂ = 1(4 つの D がどれも 1)、定数(常に No)→ Δ₂ = 0(算術の帰結)。"""
    report = report_of(scenario_runs["branch"])
    for cell in report["cells"]:
        delta = cell["delta2"]
        expected = 1.0 if cell["arm"] in ("a", "a_d") else 0.0
        assert delta["estimate"] == expected
        assert set(delta["terms"].values()) == {expected}
        assert delta["ci"]["n_pairs"] == SMALL_N_PER_LEVEL
        # 組ごとの差がすべて同じ(1 か 0)なので、区間は幅 0 で「退化」の印が付く(ADR-108 決定2)
        assert delta["ci"]["degenerate"] is True
        assert delta["ci"]["low"] == delta["ci"]["high"] == expected
    degenerate_rows = [
        line for line in sharpness_fit.report_lines(report) if "CI=[" in line and "退化" in line
    ]
    assert len(degenerate_rows) == len(report["cells"])  # このシナリオではどのセルも退化


@pytest.mark.parametrize(
    ("scenario", "stage", "anomaly", "r5"),
    [
        ("branch", sharpness_fit.NEXT_BRANCH_A, False, sharpness_fit.R5_NOT_APPLICABLE),
        ("pre_ft_keep", sharpness_fit.NEXT_PRE_FT, False, sharpness_fit.R5_KEEP),
        ("pre_ft_drop", sharpness_fit.NEXT_PRE_FT, False, sharpness_fit.R5_DROP),
        ("anomaly", sharpness_fit.NEXT_NO_PRE_FT, True, sharpness_fit.R5_NOT_APPLICABLE),
        ("both", sharpness_fit.NEXT_NO_PRE_FT, False, sharpness_fit.R5_NOT_APPLICABLE),
    ],
)
def test_the_judgment_table_on_real_records(
    scenario_runs: dict[str, list[Path]], scenario: str, stage: str, anomaly: bool, r5: str
) -> None:
    """★R4 を T1b と T3 に別々に当て(ここでは同じ答え方なので同じ段)、R5 は T1b だけに当てる。"""
    report = report_of(scenario_runs[scenario])
    for task in sharpness_fit.JUDGED_TASK_TYPES:
        assert report["judgment"][task]["next_stage"] == stage
        assert report["judgment"][task]["anomaly"] is anomaly
    assert report["r5"]["decision"] == r5
    reach_arms = {row["arm"] for row in report["reach"]}
    assert reach_arms == set(sharpness_fit.LINE_ARMS)  # A-d の Δ₂ は記述だけ
    assert all(not cell["rule_arm"] for cell in report["cells"] if cell["arm"] == "a_d")


# R4 をタスク型ごとに別々に当てた期待(次の段, 異常の印)と R5(ADR-108 決定8 (a)(b))。
SPLIT_EXPECTATIONS = [
    # T1b は A・B とも届かない → 前段 FT(B-d が届き B が届かない → ③-iii を残す)/ T3 は A だけ届く → 分岐 (a)
    (
        "split_pre_ft_branch",
        {
            "t1b": (False, False, sharpness_fit.NEXT_PRE_FT, False),
            "t3": (True, False, sharpness_fit.NEXT_BRANCH_A, False),
        },
        sharpness_fit.R5_KEEP,
    ),
    # T1b は A・B とも届く → 前段 FT は要らない / T3 は A が届かず B が届く → 前段 FT は要らない + 異常の印
    (
        "split_anomaly",
        {
            "t1b": (True, True, sharpness_fit.NEXT_NO_PRE_FT, False),
            "t3": (False, True, sharpness_fit.NEXT_NO_PRE_FT, True),
        },
        sharpness_fit.R5_NOT_APPLICABLE,
    ),
    # T1b は A・B とも届かない → 前段 FT(B-d が届き B が届かない → ③-iii を残す)/ T3 は A が届かず B が届く →
    # 前段 FT は要らない + 異常の印。**R5 は T1b の B を読む**(T3 の B を読むと B が届くので ③-iii を置かないになる)
    (
        "split_t3_b_reaches",
        {
            "t1b": (False, False, sharpness_fit.NEXT_PRE_FT, False),
            "t3": (False, True, sharpness_fit.NEXT_NO_PRE_FT, True),
        },
        sharpness_fit.R5_KEEP,
    ),
    # B の T1b が 1 セルだけ線を下回る → B は届かない → T1b は分岐 (a) / T3 は A・B とも届く
    (
        "one_cell_below",
        {
            "t1b": (True, False, sharpness_fit.NEXT_BRANCH_A, False),
            "t3": (True, True, sharpness_fit.NEXT_NO_PRE_FT, False),
        },
        sharpness_fit.R5_NOT_APPLICABLE,
    ),
]


@pytest.mark.parametrize(("scenario", "expected", "r5"), SPLIT_EXPECTATIONS)
def test_r4_is_applied_to_t1b_and_t3_separately(
    scenario_runs: dict[str, list[Path]],
    scenario: str,
    expected: dict[str, tuple[bool, bool, str, bool]],
    r5: str,
) -> None:
    """★T1b と T3 で答え方を変えると、次の段・異常の印がタスク型ごとに割れる(配線の取り違えの網)。

    R5 は T1b の次の段だけを見る(T3 の段が前段 FT でも、T1b が違えば当てない)。
    """
    report = report_of(scenario_runs[scenario])
    for task, (a_reaches, b_reaches, stage, anomaly) in expected.items():
        row = report["judgment"][task]
        assert (row["a_reaches"], row["b_reaches"]) == (a_reaches, b_reaches), task
        assert (row["next_stage"], row["anomaly"]) == (stage, anomaly), task
    assert report["r5"]["decision"] == r5
    # このシナリオは T1b と T3 で結果が違う(同じなら、取り違えた配線を見逃す網にならない)
    assert expected["t1b"][2:] != expected["t3"][2:]


def test_one_cell_below_the_line_means_the_arm_does_not_reach(
    scenario_runs: dict[str, list[Path]],
) -> None:
    """★R3: 3 セルのうち 1 つだけ線を下回れば、その (腕 × タスク型) は「届かない」(残りの 2 セルは届く)。"""
    report = report_of(scenario_runs["one_cell_below"])

    def cell_marks(arm: str, task: str) -> dict[str, bool]:
        return {
            cell["coverage"]: cell["delta2"]["reaches_line"]
            for cell in report["cells"]
            if (cell["arm"], cell["task_type"]) == (arm, task)
        }

    assert cell_marks("b", "t1b") == {"id": True, "interp": True, "extrap_magnitude": False}
    assert cell_marks("b", "t3") == {coverage: True for coverage in MAIN_COVERAGE_LEVELS}
    assert cell_marks("a", "t1b") == {coverage: True for coverage in MAIN_COVERAGE_LEVELS}
    reach = {(row["arm"], row["task_type"]): row["reaches"] for row in report["reach"]}
    assert reach[("b", "t1b")] is False and reach[("b", "t3")] is True
    below = next(
        cell
        for cell in report["cells"]
        if (cell["arm"], cell["task_type"], cell["coverage"]) == ("b", "t1b", "extrap_magnitude")
    )
    assert below["delta2"]["estimate"] == 0.0  # 常に No のセル。線を下回る理由はこのセルだけ


def test_near_ties_are_counted_and_removed_only_in_the_description(
    scenario_runs: dict[str, list[Path]],
) -> None:
    """★近接同点(θ = 0 の B)は件数に出て、除いた Δ₂ は θ = 0 が空なので null。判定は変えない。"""
    report = report_of(scenario_runs["both"])
    b_cells = [cell for cell in report["cells"] if cell["arm"] == "b"]
    for cell in b_cells:
        near = cell["delta2"]["near_tie"]
        # θ = 0 は Δ₂ の水準。2 極性 × 8 件
        assert near["n_near_tie_at_delta2_levels"] == 2 * SMALL_N_PER_LEVEL
        assert near["by_polarity_theta"] == {p: {"0": SMALL_N_PER_LEVEL} for p in ("gt", "lt")}
        assert near["without_near_tie"]["estimate"] is None
        # 近接同点の答えは Yes 側: gt の θ = 0 は y = 0、lt の θ = 0 は y = 1(真値は No)
        assert cell["delta2"]["terms"]["gt:+0"] == 0.0
    b_reach = {row["task_type"]: row["reaches"] for row in report["reach"] if row["arm"] == "b"}
    assert b_reach == {"t1b": True, "t3": True}


def test_descriptive_rows_are_present(scenario_runs: dict[str, list[Path]]) -> None:
    """R6: 交差点・質量・1 位の綴り・トークン数・T < 1 の除外がそろう(合否には使わない)。"""
    report = report_of(scenario_runs["branch"])
    cell = next(c for c in report["cells"] if c["arm"] == "a" and c["task_type"] == "t1b")
    assert cell["crossing"]["mixed"]["kind"] in ("fit", "staircase")
    for polarity in ("gt", "lt"):
        block = cell["mass"][polarity]
        assert block["mass_median"] == pytest.approx(1.0)
        assert sum(block["top1"].values()) == block["n"]
    tokens = report["tokens"]
    # count_tokens = len(文字数)。A の文面は B より短い(和の部分を x に置き換えた)
    for task, block in tokens["paired_difference"]["a-b"].items():
        assert block["max"] < 0, task
    assert set(tokens["paired_difference"]) == {"a-b", "a_d-b_d"}
    assert report["below_min_threshold"]["min_threshold"] == 1
    assert report["below_min_threshold"]["record"]["n_excluded"] > 0
    lines = sharpness_fit.report_lines(report)
    assert any(line.startswith("=== R4") for line in lines)
    assert any("R5" in line for line in lines)


def test_the_s1_rows_carry_the_yardstick_note(scenario_runs: dict[str, list[Path]]) -> None:
    """★S1 の行に物差しの注記(ADR-108 決定3。§8.1 R6 の文言)。S1 の定義(β1 の値)は変えない。"""
    report = report_of(scenario_runs["branch"])
    note = report["s1_note"]
    assert note == sharpness_fit.S1_NOTE
    for phrase in (
        "±300 までの 19 水準",
        "T < 1 の除外で遠い負の側の組の母集団が違う",
        "R8 の β1(水準 −3〜13)",
        "β1 ≥ 0.18 ⇔ Δ₂ ≥ 0.088",
        "同じ物差しではない",
    ):
        assert phrase in note
    lines = sharpness_fit.report_lines(report)
    start = next(i for i, line in enumerate(lines) if line.startswith("  S1(混ぜた β1)"))
    assert note in lines[start + 1]  # S1 の見出しのすぐ下、セルの行より前
    assert lines[start + 2].lstrip().startswith(("A ", "B "))
    # 注記は S1 の値に触れない(点推定の欄は従来どおり)
    assert all("s1_beta1" in cell for cell in report["cells"])


def test_main_writes_the_json_and_the_text(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI: --runs の glob で 4 腕を読み、json と txt を書く(トークナイザは差し替え)。"""
    monkeypatch.setattr(sharpness_fit, "tokenizer_counter", lambda config: len)
    run_root = scenario_runs["branch"][0].parent.parent
    out_dir = tmp_path / "out"
    assert sharpness_fit.main(["--runs", str(run_root / "run_*"), "--out-dir", str(out_dir)]) == 0
    report = json.loads((out_dir / sharpness_fit.OUTPUT_JSON).read_text(encoding="utf-8"))
    assert report["judgment"]["t1b"]["next_stage"] == sharpness_fit.NEXT_BRANCH_A
    text = (out_dir / sharpness_fit.OUTPUT_TEXT).read_text(encoding="utf-8")
    assert "分岐 (a)" in text
    assert sharpness_fit.S1_NOTE in text and report["s1_note"] == sharpness_fit.S1_NOTE
    assert "退化" in text  # このシナリオの区間は幅 0(txt にも印が出る)
    assert report["rules"]["premises"] == {"adapter": None, "batch_size": 4, "top_k": 20}
    assert "R1 の前提" in text


# --------------------------------------------------------------------------
# R7 と読み込みの止める条件(負例)
# --------------------------------------------------------------------------


def copy_runs(paths: Sequence[Path], tmp: Path) -> list[Path]:
    """run ディレクトリを tmp に写す(壊すのは写しだけ)。"""
    import shutil  # noqa: PLC0415

    copied = []
    for path in paths:
        target = tmp / path.parent.name
        shutil.copytree(path.parent, target)
        copied.append(target / "metrics.json")
    return copied


def rewrite_rows(metrics_path: Path, edit: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]) -> None:
    """predictions と metrics.json の件数を、壊した行に合わせて書き直す(check_records は通す)。"""
    run_dir = metrics_path.parent
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    sweep = metrics["threshold_sweep"]
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for name in list(sweep["predictions"]):
        path = run_dir / "predictions" / f"{name}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows = edit(rows)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        sweep["predictions"][name] = len(rows)
        for row in rows:
            by_theta = counts.setdefault(row["sweep_cell"], {}).setdefault(row["polarity"], {})
            theta = str(row["threshold_offset"])
            by_theta[theta] = by_theta.get(theta, 0) + 1
    sweep["n_items_by_cell"] = counts
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")


def test_a_missing_item_at_a_delta2_level_stops(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★R7 の 1: Δ₂ の水準の (腕 × セル × 極性) が n_per_level でなければ判定表を出さない。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    dropped = {"done": False}

    def drop_one(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept = []
        for row in rows:
            if not dropped["done"] and row["threshold_offset"] == 1:
                dropped["done"] = True
                continue
            kept.append(row)
        return kept

    rewrite_rows(paths[ARMS.index("b")], drop_one)
    with pytest.raises(SharpnessError, match="水準の件数"):
        report_of(paths)


def test_a_broken_pair_stops(scenario_runs: dict[str, list[Path]], tmp_path: Path) -> None:
    """★R7 の 2: A と B で閾値が 1 件でも違えば(対がそろわない)判定表を出さない。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    run_dir = paths[ARMS.index("a")].parent
    path = run_dir / "predictions" / "threshold_sweep.t3.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    # item_id はそのまま、組を別の組に差し替える(閾値・真値は壊さない = check_records は通る)
    first = rows[0]
    a, b = first["operands"]
    first["operands"] = [b, a] if a != b else [a + 1, b - 1]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(SharpnessError, match="対がそろわない"):
        report_of(paths)


def test_missing_or_duplicated_arms_stop(scenario_runs: dict[str, list[Path]]) -> None:
    paths = scenario_runs["branch"]
    with pytest.raises(SharpnessError, match="run が無い"):
        report_of(paths[:3])
    with pytest.raises(SharpnessError, match="2 本"):
        report_of([*paths, paths[0]])


def test_runs_from_different_scenarios_still_pair(scenario_runs: dict[str, list[Path]]) -> None:
    """腕ごとに別の答え方の run を混ぜても、同じプールなら対はそろう(判定は答え方だけで変わる)。"""
    mixed = [scenario_runs["branch"][0], *scenario_runs["anomaly"][1:]]
    report = report_of(mixed)
    assert report["runs"]["b"]["run_id"] == "run_b"


def test_a_wrong_template_set_for_the_arm_stops(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★腕 a を名乗る run の文面が eval_main(B の文面)なら読まない(腕の取り違え)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    config_path = paths[ARMS.index("a")].parent / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace("eval_template_set: diag_explicit", "eval_template_set: eval_main"),
        encoding="utf-8",
    )
    with pytest.raises(SharpnessError, match="文面"):
        sharpness_fit.load_diag_run(paths[ARMS.index("a")])


def test_disagreeing_sharpness_blocks_stop(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★線が run の間で違えば止める(arm 以外は 4 本で一致しなければならない)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    config_path = paths[ARMS.index("b_d")].parent / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    assert "delta2_line: 0.088" in text
    config_path.write_text(text.replace("delta2_line: 0.088", "delta2_line: 0.05"), encoding="utf-8")
    with pytest.raises(SharpnessError, match="食い違う"):
        report_of(paths)


def test_rows_without_top_k_stop(scenario_runs: dict[str, list[Path]], tmp_path: Path) -> None:
    """R6 の 1 位の綴りが数えられない行(top_k なし)は止める。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)

    def strip(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**row, "top_k": None} if i == 0 else row for i, row in enumerate(rows)]

    rewrite_rows(paths[ARMS.index("b")], strip)
    with pytest.raises(SharpnessError, match="top_k"):
        report_of(paths)


def test_a_non_sweep_run_stops(scenario_runs: dict[str, list[Path]], tmp_path: Path) -> None:
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    metrics = json.loads(paths[0].read_text(encoding="utf-8"))
    metrics["kind"] = "battery_eval"
    paths[0].write_text(json.dumps(copy.deepcopy(metrics)), encoding="utf-8")
    with pytest.raises(SharpnessError, match="kind"):
        sharpness_fit.load_diag_run(paths[0])


# --------------------------------------------------------------------------
# R7 の 3: R1 の前提の照合(ADR-108 決定5)。`build_report` を直接呼ぶ経路(`report_of`)で通す
# --------------------------------------------------------------------------


def edit_yaml(path: Path, edit: Callable[[dict[str, Any]], None]) -> None:
    """run ディレクトリの config.yaml を読み直して直す(壊すのは写しだけ)。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def edit_metrics(path: Path, edit: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _set(node_path: Sequence[str], value: Any) -> Callable[[dict[str, Any]], None]:
    """入れ子の辞書の 1 か所を差し替える編集。"""

    def edit(data: dict[str, Any]) -> None:
        node = data
        for key in node_path[:-1]:
            node = node[key]
        node[node_path[-1]] = value

    return edit


# (何を壊すか, 腕, どのファイルか, 編集, エラーに含まれる語)
PREMISE_BREAKS = [
    ("モデルの revision", "b_d", "config", _set(["model", "revision"], "0" * 40), "モデル"),
    ("モデルの名前", "a", "config", _set(["model", "name"], "other/model"), "モデル"),
    ("adapter", "a", "metrics", _set(["adapter"], "runs/x/adapter"), "adapter"),
    ("batch_size", "a_d", "config", _set(["eval", "batch_size"], 8), "batch_size"),
    ("上位 k(config)", "b", "config", _set(["eval", "forced_choice_top_k"], 5), "top_k"),
    ("プールの sha256(B-d だけ)", "b_d", "metrics", _set(["pool", "items_sha256"], "0" * 64), "sha256"),
    ("プールの sha256(B だけ)", "b", "metrics", _set(["pool", "items_sha256"], "1" * 64), "sha256"),
]


@pytest.mark.parametrize(
    ("label", "arm", "target", "edit", "message"),
    PREMISE_BREAKS,
    ids=[row[0] for row in PREMISE_BREAKS],
)
def test_a_premise_that_disagrees_with_the_record_stops(
    scenario_runs: dict[str, list[Path]],
    tmp_path: Path,
    label: str,
    arm: str,
    target: str,
    edit: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    """★R1 の前提(モデル・adapter・batch・上位 k・プール)が 1 本でも食い違えば、判定表を出さずに止まる。

    RUNNER が 1 腕だけ batch を替える・adapter を載せる・プールを作り直す、という取り違えを、
    run dir の記録で捕まえる(config.yaml と metrics.json)。呼ぶのは `build_report`(`report_of`)の経路。
    """
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    metrics_path = paths[ARMS.index(arm)]
    if target == "config":
        edit_yaml(metrics_path.parent / "config.yaml", edit)
    else:
        edit_metrics(metrics_path, edit)
    with pytest.raises(SharpnessError, match=message) as caught:
        report_of(paths)
    assert "R1 の前提" in str(caught.value) and "判定表を出さない" in str(caught.value)


def test_the_premises_are_declared_in_the_sharpness_block(
    scenario_runs: dict[str, list[Path]],
) -> None:
    """通る run では、宣言した前提が報告の規則の欄と検査の欄に出る(null の宣言は「素のモデル」)。"""
    report = report_of(scenario_runs["branch"])
    assert report["rules"]["premises"] == {"adapter": None, "batch_size": 4, "top_k": 20}
    premises = report["checks"]["premises"]
    assert all(text in premises for text in ("adapter = None", "eval.batch_size = 4", "上位 k = 20"))
    assert len({header["items_sha256"] for header in report["runs"].values()}) == 1


def test_a_row_with_the_wrong_number_of_top_tokens_stops(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★config の宣言は 20 のままでも、記録の行の top_k が 20 個でなければ止まる(記録そのものを見る)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)

    def truncate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**row, "top_k": row["top_k"][:5]} if i == 0 else row for i, row in enumerate(rows)]

    rewrite_rows(paths[ARMS.index("a_d")], truncate)
    with pytest.raises(SharpnessError, match="top_k の個数") as caught:
        report_of(paths)
    assert "R1 の前提" in str(caught.value)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("adapter", "runs/y/adapter", "adapter"),
        ("batch_size", 8, "batch_size"),
        ("top_k", 5, "top_k"),
    ],
)
def test_the_declaration_is_what_the_records_are_compared_with(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, key: str, value: Any, message: str
) -> None:
    """★宣言のほうを 4 本とも書き換える(4 本の宣言は一致するが、記録が宣言と違う)→ 止まる。

    adapter は「4 腕で同じ」ではなく「宣言との一致」を見る(ADR-108 決定5。この診断は null を宣言する)。
    """
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    for path in paths:
        edit_yaml(path.parent / "config.yaml", _set(["sharpness", key], value))
    with pytest.raises(SharpnessError, match=message):
        report_of(paths)


# --------------------------------------------------------------------------
# R7 の 2(後半): A の prompt = B の prompt の和の部分を x の数字に置き換えたもの(ADR-108 決定6)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"task_type": "t1b", "operands": [3, 4], "prompt": "3+4>10?"}, "7>10?"),
        (
            {"task_type": "t1b", "operands": [11, 1], "prompt": "11+1<3? Answer Yes or No."},
            "12<3? Answer Yes or No.",
        ),
        (
            {
                "task_type": "t3",
                "operands": [3, 4],
                "prompt": "Is the sum of 3 and 4 greater than 10? Answer Yes or No.",
            },
            "Is 7 greater than 10? Answer Yes or No.",
        ),
        # 和の部分が 1 か所に決まらない・文面が R1 の表と違う・型が未知 → None(照合で不一致になる)
        ({"task_type": "t1b", "operands": [3, 4], "prompt": "3+4>3+4?"}, None),
        ({"task_type": "t1b", "operands": [3, 4], "prompt": "hello"}, None),
        ({"task_type": "t2", "operands": [3, 4], "prompt": "3+4>10?"}, None),
        ({"task_type": "t1b", "operands": [3, 4, 5], "prompt": "3+4>10?"}, None),
    ],
)
def test_explicit_prompt_of_replaces_only_the_sum_part(
    record: dict[str, Any], expected: str | None
) -> None:
    """R1 の表: T1b は `{a}+{b}`、T3 は `the sum of {a} and {b}` だけを x = a + b の数字に置き換える。"""
    assert sharpness_fit.explicit_prompt_of(record, "test") == expected


def test_recorded_prompts_are_the_bare_template_text(scenario_runs: dict[str, list[Path]]) -> None:
    """記録の prompt は chat template の外の文字列(テンプレートを埋めただけ。前置きも無い)。

    A の prompt が B の prompt の置き換えと一致する照合は、この形を前提にする(ADR-108 決定6)。
    """
    by_arm = {
        arm: sharpness_fit.load_diag_run(path)
        for arm, path in zip(ARMS, scenario_runs["branch"], strict=True)
    }
    for arm, template in (("b", "{a}+{b}>{threshold}?"), ("a", "{x}>{threshold}?")):
        record = next(
            r for r in by_arm[arm].records if r["task_type"] == "t1b" and r["polarity"] == "gt"
        )
        a, b = record["operands"]
        assert record["prompt"] == template.format(a=a, b=b, x=a + b, threshold=record["threshold"])
    assert all("<|" not in r["prompt"] for run_ in by_arm.values() for r in run_.records)


@pytest.mark.parametrize(
    ("arm", "task", "corrupt"),
    [
        ("a", "t1b", lambda prompt: prompt + " "),  # 1 字多い
        ("a", "t3", lambda prompt: prompt.replace("Is ", "Was ", 1)),  # ほかの語が違う
        ("a_d", "t1b", lambda prompt: prompt.replace("?", "!", 1)),  # 記号が違う
        ("b", "t1b", lambda prompt: "hello"),  # B のほうが R1 の表の文面でない
        ("b_d", "t1b", lambda prompt: prompt.replace("+", "-", 1)),  # B-d の和の部分が壊れた
        ("b", "t3", lambda prompt: prompt.replace("the sum of", "the total of", 1)),
    ],
)
def test_a_prompt_that_is_not_the_substituted_one_stops(
    scenario_runs: dict[str, list[Path]],
    tmp_path: Path,
    arm: str,
    task: str,
    corrupt: Callable[[str], str],
) -> None:
    """★1 項目でも、A(A-d)の prompt が B(B-d)の prompt の和の部分だけを x に置き換えたものでなければ止まる。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    file = paths[ARMS.index(arm)].parent / "predictions" / f"threshold_sweep.{task}.jsonl"
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
    rows[0]["prompt"] = corrupt(rows[0]["prompt"])
    file.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(SharpnessError, match="置き換えた"):
        report_of(paths)


# --------------------------------------------------------------------------
# 例外の型(ADR-108 決定7): 止める経路は `SharpnessError`(素の KeyError・R8FitError にしない)
# --------------------------------------------------------------------------


def strip_field(field: str) -> Callable[[list[dict[str, Any]]], list[dict[str, Any]]]:
    """先頭の行から欄を 1 つ取り除く編集(`check_records` の必須欄に無い欄を狙う)。"""

    def edit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in row.items() if key != field} if i == 0 else row
            for i, row in enumerate(rows)
        ]

    return edit


@pytest.mark.parametrize("arm", ["a", "b"])
@pytest.mark.parametrize("field", ["carry", "operands", "prompt"])
def test_a_missing_field_is_a_sharpness_error_not_a_key_error(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, arm: str, field: str
) -> None:
    """★`check_records` の必須欄に無い欄(carry・operands・prompt)の欠けは `SharpnessError` で止まる。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    rewrite_rows(paths[ARMS.index(arm)], strip_field(field))
    with pytest.raises(SharpnessError, match=field):
        report_of(paths)


def test_token_rows_stops_with_a_sharpness_error_on_a_missing_prompt(
    scenario_runs: dict[str, list[Path]],
) -> None:
    """`token_rows` の prompt の欠けも `SharpnessError`(`build_report` の前の検査を通らずに呼ばれても)。"""
    runs = {
        arm: sharpness_fit.load_diag_run(path)
        for arm, path in zip(ARMS, scenario_runs["branch"], strict=True)
    }
    broken = dataclasses.replace(
        runs["a"],
        records=tuple({k: v for k, v in r.items() if k != "prompt"} for r in runs["a"].records),
    )
    with pytest.raises(SharpnessError, match="prompt"):
        sharpness_fit.token_rows({**runs, "a": broken}, len)


def test_a_missing_yes_no_gap_is_a_sharpness_error_not_an_r8_fit_error(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★近接同点の差が組めない(yes_logp が無い)行は、`R8FitError` ではなく `SharpnessError` で止まる。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)

    def blank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**row, "yes_logp": None} if i == 0 else row for i, row in enumerate(rows)]

    rewrite_rows(paths[ARMS.index("b")], blank)
    with pytest.raises(SharpnessError, match="yes_logp") as caught:
        report_of(paths)
    assert not isinstance(caught.value, r8_fit.R8FitError)


def test_broken_config_declarations_stop_with_a_sharpness_error(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """config の欠け(`ConfigError`)・壊れた近接同点の幅(`GoNoGoError`)も `SharpnessError` にそろえる。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    config_path = paths[ARMS.index("a")].parent / "config.yaml"
    edit_yaml(config_path, lambda data: data["gonogo"].__setitem__("near_tie_margin", -1))
    with pytest.raises(SharpnessError, match="near_tie_margin"):
        report_of(paths)
    edit_yaml(config_path, lambda data: data["data"].pop("eval_template_set"))
    with pytest.raises(SharpnessError, match="eval_template_set"):
        sharpness_fit.load_diag_run(paths[ARMS.index("a")])


# --------------------------------------------------------------------------
# 本番と同じ件数(160/水準)で、線 0.088 のすぐ両側の Δ₂ を本物の経路で出す(ADR-108 決定8 (c))
# --------------------------------------------------------------------------

# Δ₂ の 5 水準だけに絞る(R7 が見る水準。件数は 80 組 × carry 2 = 160/水準のまま。T < 1 の除外は掛からない)
DELTA2_LEVELS = (-2, -1, 0, 1, 2)
PRODUCTION_N_PER_LEVEL = 160


@pytest.fixture(scope="module")
def production_count_pool_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """組の数は本番のまま(80 組/併合セル)、θ の水準だけ Δ₂ の 5 水準に絞った診断の掃引プール。"""
    config = load_config(POOL_CONFIG)
    config["eval"]["threshold_sweep"]["offsets"]["diag"] = list(DELTA2_LEVELS)
    source = eval_pool.build(config)
    out_dir = tmp_path_factory.mktemp("battery_production") / "pilot_sweep_diag"
    eval_pool.write_pool(sweep_pool.build_sweep_pool(config, source, "diag"), out_dir)
    return out_dir


def production_count_b_d_config(pool_dir: Path) -> dict[str, Any]:
    config = load_config(CONFIG_DIR / "exp_diag_b_d.yaml")
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["eval"]["threshold_sweep"]["offsets"]["diag"] = list(DELTA2_LEVELS)
    return config


@pytest.mark.parametrize(("k", "reaches"), [(56, False), (57, True)])
def test_the_line_is_crossed_between_56_and_57_over_640(
    production_count_pool_dir: Path, tmp_path: Path, k: int, reaches: bool
) -> None:
    """★Δ₂ = 56/640(0.0875)は線 0.088 に届かず、57/640(0.0890625)は届く。3 セルとも、本番の件数で。

    B-d(T1b だけ)の run を、本物の掃引の経路(`execute_threshold_sweep`)で `_always_no_except_first_correct(k)` の
    答え方で回し、判定表の部品(`check_level_counts`・`cell_delta2`・`arm_reaches`)に通す。
    区間は k 組の差だけが 1/4 なので退化せず、点推定を含む。
    """
    metrics_path = execute_arm(
        production_count_b_d_config(production_count_pool_dir),
        _always_no_except_first_correct(k),
        tmp_path / "run_b_d",
    )
    diag = sharpness_fit.load_diag_run(metrics_path)
    settings = diag.settings
    assert settings.n_per_level == PRODUCTION_N_PER_LEVEL
    assert settings.delta2_line == Fraction(11, 125)
    sharpness_fit.check_level_counts(diag, settings)  # どの (セル × 極性 × 水準) も 160 件
    gaps = r8_fit.sweep_gaps(diag.records, diag.name)
    cells = {
        coverage: sharpness_fit.cell_delta2(
            [record for record in diag.records if record["coverage"] == coverage],
            settings=settings,
            gaps=gaps,
            margin=0.25,
        )
        for coverage in MAIN_COVERAGE_LEVELS
    }
    for coverage, cell in cells.items():
        assert Fraction(cell["estimate_fraction"]) == Fraction(k, 640), coverage
        assert cell["reaches_line"] is reaches, coverage
        assert cell["ci"]["n_pairs"] == PRODUCTION_N_PER_LEVEL
        # 組ごとの差の平均 = 点推定(有理数で一致。ADR-109 決定2。`cell_delta2` も同じ検査を通っている)
        differences = sharpness_fit.per_pair_differences(
            [record for record in diag.records if record["coverage"] == coverage],
            settings.delta2_shift,
        )
        assert sum(differences, Fraction(0)) / len(differences) == Fraction(k, 640), coverage
        assert cell["ci"]["degenerate"] is False
        assert cell["ci"]["low"] <= cell["estimate"] <= cell["ci"]["high"]
    assert sharpness_fit.arm_reaches(cells) is reaches


# --------------------------------------------------------------------------
# R7 の 4: 4 本の run が同じ commit の追跡ファイルで回ったこと(ADR-109 決定1)
# --------------------------------------------------------------------------


def write_git_record(
    run_dir: Path, *, first_line: str = RUN_SHA, dirty_line: str = "dirty: true", patch: bytes | None = b""
) -> None:
    """run dir の `git_sha.txt`(と `git_diff.patch`)を書き直す。`patch=None` なら `git_diff.patch` を消す。"""
    (run_dir / "git_sha.txt").write_text(f"{first_line}\n{dirty_line}\n", encoding="utf-8", newline="\n")
    patch_path = run_dir / artifacts.DIFF_FILE
    if patch is None:
        patch_path.unlink(missing_ok=True)
    else:
        patch_path.write_bytes(patch)


def test_the_fixture_runs_have_the_shape_of_the_runs_made_on_the_pod(
    scenario_runs: dict[str, list[Path]],
) -> None:
    """置き物の run の記録は pod の実物と同じ形(sha・`dirty: true`・diff 0 バイト)。これで判定表が通る。"""
    for path in scenario_runs["branch"]:
        run_dir = path.parent
        assert (run_dir / "git_sha.txt").read_text(encoding="utf-8") == f"{RUN_SHA}\ndirty: true\n"
        assert (run_dir / artifacts.DIFF_FILE).stat().st_size == 0
    assert report_of(scenario_runs["branch"])["commit_sha"] == RUN_SHA


def test_the_commit_sha_comes_first_in_the_json_and_the_text(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★その sha を判定表の先頭に出す(json の最初の鍵・txt の最初の行)。tag の commit と見比べるのは人間。"""
    report = report_of(scenario_runs["branch"])
    assert next(iter(report)) == "commit_sha"
    first_line = sharpness_fit.report_lines(report)[0]
    assert first_line.startswith(f"commit: {RUN_SHA}")
    assert "人間" in first_line
    monkeypatch.setattr(sharpness_fit, "tokenizer_counter", lambda config: len)
    run_root = scenario_runs["branch"][0].parent.parent
    out_dir = tmp_path / "out"
    assert sharpness_fit.main(["--runs", str(run_root / "run_*"), "--out-dir", str(out_dir)]) == 0
    written = json.loads((out_dir / sharpness_fit.OUTPUT_JSON).read_text(encoding="utf-8"))
    assert next(iter(written)) == "commit_sha" and written["commit_sha"] == RUN_SHA
    text = (out_dir / sharpness_fit.OUTPUT_TEXT).read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith(f"commit: {RUN_SHA}")
    assert sharpness_fit.PROVENANCE_CHECK in written["checks"]["provenance"]
    assert "検査: 出どころ" in text


# (何を書くか, 4 本を通るか)。`dirty` の欄と `git_diff.patch` の有無の組み合わせ
PROVENANCE_PASSES = [
    ("dirty: true・diff 0 バイト(pod の実物)", {"dirty_line": "dirty: true", "patch": b""}),
    ("dirty: true・diff のファイルなし", {"dirty_line": "dirty: true", "patch": None}),
    ("dirty: false・diff のファイルなし", {"dirty_line": "dirty: false", "patch": None}),
    ("dirty: false・diff 0 バイト", {"dirty_line": "dirty: false", "patch": b""}),
    ("dirty の欄が無い", {"dirty_line": "", "patch": b""}),
]


@pytest.mark.parametrize(
    "kwargs", [row[1] for row in PROVENANCE_PASSES], ids=[row[0] for row in PROVENANCE_PASSES]
)
def test_the_dirty_field_is_not_read_and_an_empty_diff_passes(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, kwargs: dict[str, Any]
) -> None:
    """★`dirty:` の欄は見ない。`git_diff.patch` が無いか 0 バイトなら通る(pod の実物は dirty: true・diff 0 バイト)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    for path in paths[:2]:  # 4 本のうち 2 本だけ書き換える(欄の値は腕の間で違っていてよい)
        write_git_record(path.parent, **kwargs)
    assert report_of(paths)["commit_sha"] == RUN_SHA


# (何を壊すか, 腕, 書き方, エラーに含まれる語)
PROVENANCE_BREAKS = [
    ("sha が 1 本だけ違う", "a", {"first_line": OTHER_SHA}, "腕の間で違う"),
    ("sha が 1 本だけ違う(B-d)", "b_d", {"first_line": OTHER_SHA}, "腕の間で違う"),
    ("0 バイトでない diff(1 バイト)", "b", {"patch": b"x"}, "git_diff.patch"),
    ("0 バイトでない diff(本物の差分)", "a_d", {"patch": b"diff --git a/x b/x\n+1\n"}, "git_diff.patch"),
    ("1 行目が git の失敗の文言", "a", {"first_line": "<取得できず: OSError: no git>"}, "commit の sha"),
    ("1 行目が git の標準エラー", "b", {"first_line": "fatal: not a git repository"}, "commit の sha"),
    ("1 行目が空", "b_d", {"first_line": ""}, "commit の sha"),
    ("1 行目が短縮 sha", "a", {"first_line": RUN_SHA[:7]}, "commit の sha"),
]


@pytest.mark.parametrize(
    ("label", "arm", "kwargs", "message"),
    PROVENANCE_BREAKS,
    ids=[row[0] for row in PROVENANCE_BREAKS],
)
def test_a_run_from_another_commit_or_with_a_tracked_diff_stops(
    scenario_runs: dict[str, list[Path]],
    tmp_path: Path,
    label: str,
    arm: str,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    """★sha が 4 本で同じでない・0 バイトでない diff がある・1 行目が sha でない run では判定表を出さずに止まる。

    RUNNER が途中でコードを直して 1 腕だけ別の commit で回し直した・追跡ファイルを直したまま回した、を捕まえる。
    呼ぶのは `build_report`(`report_of`)の経路。
    """
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    write_git_record(paths[ARMS.index(arm)].parent, **kwargs)
    with pytest.raises(SharpnessError, match=message) as caught:
        report_of(paths)
    assert "同じ commit の追跡ファイル" in str(caught.value) and "判定表を出さない" in str(caught.value)


def test_a_missing_git_sha_file_stops(scenario_runs: dict[str, list[Path]], tmp_path: Path) -> None:
    """★`git_sha.txt` が無い run(来歴が無い)では止まる。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    (paths[ARMS.index("a")].parent / "git_sha.txt").unlink()
    with pytest.raises(SharpnessError, match="git_sha.txt が無い"):
        report_of(paths)


def test_the_same_failure_text_in_all_four_runs_is_not_the_same_commit(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★git が 4 本とも失敗して同じ文言が並んでも「同じ commit」とは読まない(1 行目が sha でない)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    for path in paths:
        write_git_record(path.parent, first_line="<取得できず: FileNotFoundError: git>")
    with pytest.raises(SharpnessError, match="commit の sha") as caught:
        report_of(paths)
    assert len(str(caught.value).split(" / ")) == len(ARMS)  # 4 腕とも指摘に載る


def test_all_provenance_problems_are_reported_at_once(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """食い違いは 1 つの例外にまとめる(sha の違いと diff が同時にあれば両方が載る)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    write_git_record(paths[ARMS.index("a")].parent, first_line=OTHER_SHA)
    write_git_record(paths[ARMS.index("b")].parent, patch=b"x")
    with pytest.raises(SharpnessError) as caught:
        report_of(paths)
    assert "腕の間で違う" in str(caught.value) and "git_diff.patch" in str(caught.value)


# --------------------------------------------------------------------------
# 区間の前提の検査(ADR-109 決定2 = C108-3): 組ごとの差の数 = n_per_level・平均 = Δ₂ の点推定
# --------------------------------------------------------------------------


def colliding_records(n: int, *, ones_at_gt_zero: int) -> list[dict[str, Any]]:
    """(極性, θ) ごとに n 件だが、被演算子は n/2 通りしかない記録(同じ組の行が 2 つずつ。後の行が前の行を上書きする)。

    y = 1 の件数は gt・θ = 0 だけ `ones_at_gt_zero`、ほかは 0。
    """
    ones = {level: 0 for level in ALL_LEVELS}
    ones[("gt", 0)] = ones_at_gt_zero
    records = synthetic_records(ones, n)
    for record in records:
        i = int(record["item_id"].rsplit("_", 1)[1])
        record["operands"] = [i % (n // 2), 1000 + i % (n // 2)]
    return records


def test_a_number_of_pairs_other_than_n_per_level_stops() -> None:
    """★同じ被演算子の行が重なって組の数が減ると、n が n_per_level より小さい区間が出てしまう → 止める。"""
    records = colliding_records(8, ones_at_gt_zero=4)
    gaps = {record["item_id"]: 3.0 for record in records}
    assert len(sharpness_fit.per_pair_differences(records, 2)) == 4  # 8 件/水準 → 4 組に潰れる
    with pytest.raises(SharpnessError, match="n_per_level"):
        sharpness_fit.cell_delta2(records, settings=_settings(n_per_level=8), gaps=gaps, margin=0.25)


def test_a_mean_of_pair_differences_that_is_not_the_point_estimate_stops() -> None:
    """★組の数が n_per_level に合っていても、組ごとの差の平均が点推定と違えば(有理数で)止める。

    gt・θ = 0 で先頭 4 件だけ y = 1 → 点推定の P̂ = 1/2。だが同じ組の後の 4 行(y = 0)が上書きするので、
    組ごとの差の平均は 0 で、点推定 1/8(= ¼ × 1/2)とずれる(n = 4 は n_per_level = 4 に合わせてある)。
    """
    records = colliding_records(8, ones_at_gt_zero=4)
    gaps = {record["item_id"]: 3.0 for record in records}
    estimate, _ = sharpness_fit.delta2_point(records, 2)
    assert estimate == Fraction(1, 8)
    differences = sharpness_fit.per_pair_differences(records, 2)
    assert len(differences) == 4 and sum(differences, Fraction(0)) / 4 == 0
    with pytest.raises(SharpnessError, match="一致しない"):
        sharpness_fit.cell_delta2(records, settings=_settings(n_per_level=4), gaps=gaps, margin=0.25)


# --------------------------------------------------------------------------
# 例外の型の残り(ADR-109 決定2 = C108-4): 止める経路は `SharpnessError`
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["threshold_sweep", "task_types"])
def test_a_metrics_json_without_the_sweep_block_is_a_sharpness_error(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, key: str
) -> None:
    """★`metrics.json` に `threshold_sweep`(と `task_types`)が無い run は、素の `KeyError` でなく `SharpnessError`。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)

    def drop(data: dict[str, Any]) -> None:
        if key == "threshold_sweep":
            del data["threshold_sweep"]
        else:
            del data["threshold_sweep"]["task_types"]

    edit_metrics(paths[0], drop)
    with pytest.raises(SharpnessError, match=key) as caught:
        sharpness_fit.load_diag_run(paths[0])
    assert not isinstance(caught.value, KeyError)


def test_a_metrics_json_without_a_run_id_stops_before_the_table(
    scenario_runs: dict[str, list[Path]], tmp_path: Path
) -> None:
    """★`run_id` の無い run は判定表の来歴の行が組めない → `SharpnessError`(`KeyError` で判定表の途中で落とさない)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)
    edit_metrics(paths[ARMS.index("a")], lambda data: data.pop("run_id"))
    with pytest.raises(SharpnessError, match="run_id"):
        report_of(paths)


@pytest.mark.parametrize(
    ("top_k", "message"),
    [
        pytest.param([1] * 20, "top_k が無い", id="20 個だが dict でない"),
        pytest.param(["text"] * 20, "top_k が無い", id="20 個の文字列"),
        pytest.param([{"logprob": -1.0}] * 20, "top_k が無い", id="text の欄が無い"),
        pytest.param(5, "top_k の個数", id="list でない(整数)"),
        pytest.param({"text": "x"}, "top_k の個数", id="list でない(dict)"),
    ],
)
def test_a_malformed_top_k_row_is_a_sharpness_error_not_a_type_error(
    scenario_runs: dict[str, list[Path]], tmp_path: Path, top_k: Any, message: str
) -> None:
    """★行の `top_k` が list の dict でなくても、`TypeError` にならず `SharpnessError` で止まる(判定表は出さない)。"""
    paths = copy_runs(scenario_runs["branch"], tmp_path)

    def damage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**row, "top_k": top_k} if i == 0 else row for i, row in enumerate(rows)]

    rewrite_rows(paths[ARMS.index("b")], damage)
    with pytest.raises(SharpnessError, match=message):
        report_of(paths)


def fake_transformers(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """`AutoTokenizer.from_pretrained` が `error` を上げる `transformers` の差し替え(ネットワークにも本物にも触れない)。"""

    class FailingTokenizer:
        @staticmethod
        def from_pretrained(*args: Any, **kwargs: Any) -> Any:
            raise error

    module = types.ModuleType("transformers")
    module.AutoTokenizer = FailingTokenizer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", module)


@pytest.mark.parametrize("error", [OSError("offline"), ValueError("unknown tokenizer class")])
def test_an_unreadable_tokenizer_is_a_sharpness_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """★トークナイザが読めないとき(R7 の止める条件)は、HF の例外でなく `SharpnessError`。"""
    fake_transformers(monkeypatch, error)
    config = load_config(CONFIG_DIR / "exp_diag_b.yaml")
    with pytest.raises(SharpnessError, match="トークナイザ") as caught:
        sharpness_fit.tokenizer_counter(config)
    assert type(error).__name__ in str(caught.value)


def test_a_config_without_the_model_name_is_a_sharpness_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """★`tokenizer_counter` の config の欠け(`ConfigError`)も `SharpnessError`。"""
    fake_transformers(monkeypatch, OSError("読まれない"))
    config = load_config(CONFIG_DIR / "exp_diag_b.yaml")
    config["model"].pop("name")
    with pytest.raises(SharpnessError, match="model.name"):
        sharpness_fit.tokenizer_counter(config)


def test_a_glob_that_matches_no_run_is_a_sharpness_error(tmp_path: Path) -> None:
    """★`--runs` の glob が 1 本も当たらないとき(0 本の判定表を出さない)は `SharpnessError`。"""
    with pytest.raises(SharpnessError, match="判定表を出さない"):
        sharpness_fit.main(["--runs", str(tmp_path / "no_such_run_*")])
