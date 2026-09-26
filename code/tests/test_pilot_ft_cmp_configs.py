"""パイロットのアダプタ 10 本の T1b・T3 の config 10 本(PLAN-032 §5 I5・§8.1 R8。ADR-107 決定7)。

答える問い: 「10 本は、パイロット FT の評価 config と `experiment.id`・`experiment.plan`・`eval.batteries`・
`eval.task_subset` の 4 欄だけが違い、比較群(T1b・T3)の 960 項目を解き、4 値分解を参照規則 `p2`・`p2d`
のブロックで残し、既存の解析が run を拾う glob に混ざらない名前か」

**モデルの重みは 1 度も読まない。ここに出る件数は組合せ論的な帰結であって実験結果ではない。**
(置き物の応答で回す run の率は定数応答の値で、何も測っていない。合計が 1.0 になることだけを見る。)

固定する性質:
  - **10 本 = パイロット FT の評価 config(1 回目 5 本 + `num_steps` 313 の回し直し 5 本)と 1 対 1**。
    写し元の名前は `infra/make_pilot_ft_configs.py` から引く(ここに名前の表を作らない)
  - **写し元と違う欄は 4 つだけ**。`model.adapter`・`lesion.condition`・`data.manifest`・`seeds` は写し元のまま
    = 同じ条件・シードのアダプタを測る。`gonogo.pilot_design_gate` は写しで、この run では読まない
  - **名前は `exp_pilot_ft_eval` を含まない**(`gonogo_ft` の glob に混ざらない)。config が宣言する
    run dir(`runs/pilot_ft_cmp_*`)も `t2_*_profile` の glob `pilot_ft_eval_*` に混ざらない
  - **1 評価 = 960 項目**(T1b 480 + T3 480。答えが訓練域内の 640 + 域外の 320)。外した 680
    (T1 240・指示付き T1 80・T2 240・特異性対照 120)は `task_subset` 欄に残る
  - preflight の data_checks は 10 本とも 7 件 PASS(コミット済み manifest)
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from pathlib import Path

import make_pilot_ft_configs as gen
import preflight
import pytest

from code import artifacts
from code.config import load_config
from code.data_gen.pool import POOL_PILOT
from code.eval import run, task_subset
from code.eval.forced_choice import ForcedChoice, choose_from_logprobs
from code.tests.test_order6b_pilot import differing_keys
from code.tests.test_task_subset import (  # noqa: F401  (pool_dirs は fixture)
    CANDIDATE_IDS,
    CONSTANT_RESPONSE,
    config_at,
    pool_dirs,
    predictions_rows,
    read_metrics,
    write_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

CMP_PREFIX = f"{gen.CONFIG_PREFIX}_cmp"
RUN_DIR_PREFIX = "runs/pilot_ft_cmp"
PLAN_PATH = "plans/PLAN-032-sharpness-diagnostic.md"
ROUNDS = (gen.FIRST_ROUND, gen.rerun(313))

# 写し元と違ってよい欄(各 config の冒頭の注記)。
DIFFERING_FROM_EVAL = {
    "experiment.id",
    "experiment.plan",
    "eval.batteries",
    "eval.task_subset",
}

# 解析が run を拾う glob(名前を分けて混ざらないようにする。出どころは各モジュールの docstring)。
FT_GONOGO_GLOB = "*exp_pilot_ft_eval*"  # code/analysis/gonogo_ft.py: --runs "runs/*exp_pilot_ft_eval*"
T2_PROFILE_GLOB = "pilot_ft_eval_*"  # code/analysis/t2_*_profile.py: --runs "runs/pilot_ft_eval_*"

# 件数(**組合せ論的な帰結であって実験結果ではない**。パイロット用プール 1,640 の比較群)。
N_POOL_ITEMS = 1640
N_COMPARISON = 960  # T1b 480 + T3 480
N_ANS_IN, N_ANS_OUT = 640, 320  # 比較群を答えの域で割った 2 バッチ
N_DROPPED = N_POOL_ITEMS - N_COMPARISON  # T1 240 + 指示付き T1 80 + T2 240 + 特異性 120
DROPPED_GROUPS = {"bare_sum", "bare_sum_instructed", "word_problem", "specificity"}

RATE_KEYS = ("correct_rate", "rule_rate", "other_error_rate", "parse_fail_rate")

Case = tuple[gen.Arm, gen.Round]


def cases() -> list[Case]:
    return [(arm, rnd) for arm in gen.all_arms() for rnd in ROUNDS]


def case_id(case: Case) -> str:
    arm, rnd = case
    return f"{arm.condition}_s{arm.seed}{rnd.suffix}"


def cmp_name(case: Case) -> str:
    arm, rnd = case
    return f"{CMP_PREFIX}_{arm.condition}_s{arm.seed}{rnd.suffix}.yaml"


def cmp_path(case: Case) -> Path:
    return CONFIG_DIR / cmp_name(case)


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_task_subset.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


# --------------------------------------------------------------------------
# 名前と写し元
# --------------------------------------------------------------------------


def test_ten_configs_one_per_pilot_eval_config() -> None:
    """★10 本 = 評価 config(1 回目 5 + 回し直し 5)と 1 対 1。増えても減っても落ちる。"""
    found = {path.name for path in CONFIG_DIR.glob(f"{CMP_PREFIX}_*.yaml")}
    assert found == {cmp_name(case) for case in cases()}
    assert len(found) == 10


@pytest.mark.parametrize("case", cases(), ids=case_id)
def test_a_config_differs_from_its_eval_source_only_in_the_declared_keys(case: Case) -> None:
    """★写し元(パイロット FT の評価 config)と違うのは 4 欄だけで、値は PLAN-032 §5 I5 のとおり。"""
    arm, rnd = case
    source = load_config(CONFIG_DIR / gen.eval_config_name(arm, rnd))
    config = load_config(cmp_path(case))
    assert differing_keys(source, config) == DIFFERING_FROM_EVAL
    assert config["experiment"]["id"] == cmp_path(case).stem
    assert config["experiment"]["plan"] == PLAN_PATH
    assert config["eval"]["batteries"] == ["comparison"]
    assert task_subset.declared_task_subset(config) == ("t1b", "t3")


@pytest.mark.parametrize("case", cases(), ids=case_id)
def test_the_adapter_and_the_condition_are_those_of_the_source_arm(case: Case) -> None:
    """★同じ条件・シード・ステップ数のアダプタを測る(ポッド上で config を書き換えない)。"""
    arm, rnd = case
    config = load_config(cmp_path(case))
    assert config["model"]["adapter"] == f"{gen.train_run_dir(arm, rnd)}/adapter"
    assert config["lesion"]["condition"] == arm.condition
    assert config["data"]["manifest"] == (
        f"data/generated/ft/exp_order6b_pilot_{arm.condition}/manifest.json"
    )
    assert config["data"]["pool_id"] == POOL_PILOT
    assert config["eval"]["reference_rule"] == "p2"


@pytest.mark.parametrize("case", cases(), ids=case_id)
def test_the_names_stay_out_of_the_globs_of_the_ft_analyses(case: Case) -> None:
    """★`gonogo_ft`(T1・T2 と特異性対照の門)と `t2_*_profile` の glob に、この run が混ざらない。"""
    arm, rnd = case
    config = load_config(cmp_path(case))
    experiment_id = config["experiment"]["id"]
    assert not fnmatch.fnmatch(experiment_id, FT_GONOGO_GLOB)
    # 既定の run dir は `<timestamp>_<id>`(--run-dir を渡さないとき)
    assert not fnmatch.fnmatch(f"20260926_000000_{experiment_id}", FT_GONOGO_GLOB)

    declared = re.search(r"--run-dir (\S+)", cmp_path(case).read_text(encoding="utf-8"))
    assert declared is not None
    assert declared.group(1) == f"{RUN_DIR_PREFIX}_{arm.condition}_s{arm.seed}{rnd.suffix}"
    assert not fnmatch.fnmatch(Path(declared.group(1)).name, T2_PROFILE_GLOB)


# --------------------------------------------------------------------------
# データの検査・項目数(モデルは読まない)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", cases(), ids=case_id)
def test_data_checks_pass(case: Case) -> None:
    """★preflight の data_checks が 7 件すべて PASS(コミット済み manifest。items は要らない)。"""
    results = preflight.data_checks(preflight.load_config(cmp_path(case)))
    assert {r.name for r in results} == set(preflight.DATA_CHECK_NAMES)
    assert {r.status for r in results} == {preflight.Status.PASS}, [
        (r.name, r.detail) for r in results
    ]


@pytest.mark.parametrize("case", cases(), ids=case_id)
def test_a_dry_run_solves_960_items_and_names_what_was_dropped(
    pool_dirs: dict[str, Path],  # noqa: F811
    case: Case,
) -> None:
    """★1 評価 = 比較群の 960 項目。外した 680 は群ごとに task_subset 欄へ残り、全件を解く群は無い。"""
    report = run.dry_run(config_at(cmp_path(case), pool_dirs["pilot"]))
    assert report["n_items"] == N_COMPARISON
    subset = report["task_subset"]
    assert subset["n_items"] == N_COMPARISON
    assert subset["n_pool_items"] == N_POOL_ITEMS
    assert subset["n_dropped"] == N_DROPPED
    assert {row["group"] for row in subset["dropped"]} == DROPPED_GROUPS
    assert subset["solved_whole"] == []


# --------------------------------------------------------------------------
# 置き物で回した run の記録(何も測っていない。形だけを見る)
# --------------------------------------------------------------------------


def run_with_stubs(config: dict, tmp: Path) -> tuple[Path, list[str]]:
    """置き物の生成器・採点器で固定オフセットの経路を回す。**上位 k は宣言しない config なので、
    採点器も上位を返さない**(順6b の config 用の `test_task_subset.recording_scorer` は 20 個返す)。"""
    seen: list[str] = []

    def generator(prompts: Sequence[str]) -> list[str]:
        seen.extend(prompts)
        return [CONSTANT_RESPONSE for _ in prompts]

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        seen.extend(prompts)
        return [choose_from_logprobs([-0.25, -0.5], CANDIDATE_IDS) for _ in prompts]

    run_dir = run.execute(
        config,
        config_path=write_config(config, tmp / "config.yaml"),
        run_dir=tmp / "run",
        generator=generator,
        scorer=scorer,
    )
    return run_dir, seen


@pytest.mark.parametrize("case", cases(), ids=case_id)
def test_a_stubbed_run_records_p2_and_p2d_four_way_blocks_for_the_comparison_group(
    pool_dirs: dict[str, Path],  # noqa: F811
    case: Case,
    tmp_path: Path,
) -> None:
    """★R8: 4 値分解は参照規則 p2・p2d(ADR-016)。比較群の 2 バッチとも、両方のブロックが出て合計 1.0。

    `model.adapter` は null に差し替えて回す(アダプタの訓練 run は git に無く、置き物の run では
    読めない)。アダプタの読み込みそのものは本実行で確かめる。"""
    config = config_at(cmp_path(case), pool_dirs["pilot"])
    assert config["model"]["adapter"] is not None
    config["model"]["adapter"] = None
    run_dir, sent = run_with_stubs(config, tmp_path)

    assert len(sent) == N_COMPARISON
    assert len(predictions_rows(run_dir)) == N_COMPARISON
    metrics = read_metrics(run_dir)
    assert metrics["experiment_id"] == cmp_path(case).stem
    assert metrics["primary_reference_rule"] == "p2"
    assert metrics["pool"]["n_items"] == N_COMPARISON
    record = metrics["task_subset"]
    assert record["task_types"] == ["t1b", "t3"]
    assert record["n_items"] == N_COMPARISON and record["n_dropped"] == N_DROPPED

    assert {name: batch["n_items"] for name, batch in metrics["by_batch"].items()} == {
        "comparison": N_ANS_IN,
        "comparison.ans_out": N_ANS_OUT,
    }
    for name, batch in metrics["by_batch"].items():
        blocks = batch["by_reference_rule"]
        assert {"p2", "p2d"} <= set(blocks), name
        for rule in ("p2", "p2d"):
            assert sum(blocks[rule][key] for key in RATE_KEYS) == pytest.approx(1.0), (name, rule)
            assert blocks[rule]["n_items"] == batch["n_items"], (name, rule)
