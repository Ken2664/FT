"""段2 の診断の判定表(PLAN-032 I4。§8.1 R2〜R7。ADR-107 決定3〜6・8)。

答える問い: 「4 腕の掃引の run から、Δ₂・R3 の『届く』・R4 の次の段(T1b と T3 に別々)・R5 の ③-iii を
凍結した規則どおりに機械的に出し、R7 の食い違いでは判定表を出さずに止まるか」

**モデルの重みは 1 度も読まない**(採点器を差し替え、答え方を決めて与える)。**ここに出る Δ₂ は
差し替えた採点器の答え方から算術で決まる値であって、実験結果ではない。**

ここで固定する最重要の性質:
  - **Δ₂ の定義(R2)**: 真値どおりに答えるモデルは Δ₂ = 1、定数で答えるモデルは Δ₂ = 0。
    4 通りの (極性, θ) は固定オフセットの許容表そのもの。組ごとの差の平均は点推定と一致する
  - **線の比べ方(R3)**: 点推定 ≥ 線(線ちょうどは届く)を有理数で厳密に比べる。3 セルすべてで届く
  - **R4 の 4 行と異常の印・R5 の 3 通り**を、本物の run.py の記録の経路を通した run で当てる
  - **R7**: Δ₂ の水準の件数が違う / A と B の対がそろわない run では判定表を出さない。
    腕の欠け・重なり・sharpness 欄の食い違い・文面の出どころの取り違え・上位 k の欠けも止める
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from code import artifacts
from code.analysis import sharpness_fit
from code.analysis.sharpness_fit import SharpnessError
from code.config import load_config
from code.data_gen import eval_pool, sweep_pool
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


# --------------------------------------------------------------------------
# 答え方(プロンプト → 真値は、同じ run の項目から引く。重みは読まない)
# --------------------------------------------------------------------------

Behavior = Callable[[Any], tuple[float, float]]  # 項目 -> (yes_logp, no_logp)


def _truthful(item: Any) -> tuple[float, float]:
    truth = t3_comparison.comparison_answer(
        t3_comparison.item_total(item),
        t3_comparison.polarity_of(item.category),
        int(item.params["threshold"]),
    )
    return CONFIDENT if truth else CONFIDENT[::-1]


def _always_no(item: Any) -> tuple[float, float]:
    return CONFIDENT[::-1]


def _truthful_tied_at_zero(item: Any) -> tuple[float, float]:
    """真値どおりだが θ = 0 だけ近接同点(答えは Yes 側)。"""
    if item.params["threshold_offset"] == 0:
        return TIED
    return _truthful(item)


def behavior_scorer(prompt_items: Mapping[str, Any], behavior: Behavior):  # type: ignore[no-untyped-def]
    """プロンプトから項目を引き、決めた答え方で強制選択の結果を返す採点器。"""

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        return [
            with_filler_top_tokens(
                choose_from_logprobs(list(behavior(prompt_items[prompt])), CANDIDATE_IDS)
            )
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
    prompt_items = {prompts[item.item_id]: item for item in pool.items}
    # 写しの名前は run の glob(`run_*`)に当たらないようにする
    config_path = write_config(config, run_dir.parent / f"config_{run_dir.name}.yaml")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", stub_capture)
        run.execute_threshold_sweep(
            config,
            config_path=config_path,
            run_dir=run_dir,
            scorer=behavior_scorer(prompt_items, behavior),
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


def test_confidence_interval_is_the_paired_normal_interval() -> None:
    """記述の行(★実装の読み): 組ごとの差の平均 ± z·sd/√n。"""
    ci = sharpness_fit.confidence_interval([Fraction(0), Fraction(1), Fraction(1), Fraction(0)], 0.95)
    se = 0.5773502691896257 / 2  # sd = √(1/3)
    assert ci["standard_error"] == pytest.approx(se)
    assert ci["low"] == pytest.approx(0.5 - 1.959963984540054 * se)
    assert ci["high"] == pytest.approx(0.5 + 1.959963984540054 * se)
    assert sharpness_fit.confidence_interval([Fraction(1)], 0.95)["low"] is None


def _settings(**overrides: Any) -> sharpness_fit.SharpnessSettings:
    block = {
        "arm": "b",
        "arm_template_sets": {"b": "eval_main", "a": "diag_explicit", "b_d": "order6b_d", "a_d": "x"},
        "delta2_shift": 2,
        "delta2_line": 0.088,
        "n_per_level": 125,
        "ci_level": 0.95,
    }
    block.update(overrides)
    return sharpness_fit.load_sharpness_settings({"sharpness": block}, "test")


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
    ],
)
def test_broken_sharpness_blocks_stop(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(SharpnessError, match=message):
        _settings(**overrides)


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
