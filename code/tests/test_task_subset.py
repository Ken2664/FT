"""プールの一部だけを解く宣言(`eval.task_subset`)と (d) のテンプレート集合(PLAN-026 I8)。

答える問い: 「宣言した run はプールの宣言した部分だけを解き、外した分が記録に残り、
宣言しない run は今までどおりプール全体を解くか」

**モデルの重みは 1 度も読まない**(生成器と採点器を差し替える。`test_preamble.py` と同じ)。
**ここに出る数値は実験結果ではない。**件数は組合せ論とハッシュの帰結である。

ここで固定する最重要の性質:
  - **絞りの宣言が無い run は 1 項目も変わらない**(B0 1,640 / S-① 2,400。宣言外の群があれば今までどおり止まる)
  - ① は 3 群 1,440・(d) は T1b 480・S-(d) は S の T1b 1,200 を解く
  - **外した群・タスク型と件数が `metrics.json` の `task_subset` 欄と `log.txt` に残る**(宣言が無ければ null)
  - **掃引の完全性はプール全体で確かめてから絞る** —— T3 の項目が 1 件欠けた S のプールは、
    T1b だけを解く S-(d) でも止まる
  - S-(d) の `threshold_sweep.task_types` は解いた `[t1b]` で、`code/analysis/r8_fit.py`(I5)が
    手を入れずに読める
  - (d) の文面は**本番の `t1b.yaml` + `t3.yaml` の末尾の一文**で、T3 は (d) の集合に無い
  - 噛み合わない宣言・壊れた宣言は重みを読む前・run ディレクトリを作る前に止まる。桁数掃引は宣言を拒む

**repo の data/generated/ の items.jsonl を当てにしない**(git に無い)。module の fixture で
パイロット用プールと S の掃引プールを tmp に組み直す(約 8 秒)。
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import preflight
import pytest
import yaml

from code import artifacts
from code.analysis import r8_fit
from code.config import ConfigError, load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.battery_items import Item, read_items
from code.eval import run, sweep, task_subset
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.eval.forced_choice import ForcedChoice, ForcedChoiceScorer, choose_from_logprobs
from code.tests.test_top_k import with_filler_top_tokens

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
TEMPLATE_DIR = CONFIG_DIR / "templates"

PILOT_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"
R8_CONFIG = CONFIG_DIR / "exp_order6b_r8.yaml"
S_PREAMBLE_CONFIG = CONFIG_DIR / "exp_order6b_s_preamble.yaml"
PREAMBLE_ARM_CONFIG = CONFIG_DIR / "exp_order6b_preamble.yaml"
D_CONFIG = CONFIG_DIR / "exp_order6b_d.yaml"
S_D_CONFIG = CONFIG_DIR / "exp_order6b_s_d.yaml"

# 絞りを宣言してよい config(順6b の ① と (d) の腕だけ。本番・pilot・R8・S-① は持たない)。
SUBSET_CONFIGS = {PREAMBLE_ARM_CONFIG.name, D_CONFIG.name, S_D_CONFIG.name}

# それぞれの config が写し元と違ってよい欄(各 config の冒頭の注記)。
PREAMBLE_ARM_DIFFERING_KEYS = {
    "experiment.id",
    "eval.batteries",
    "eval.task_subset",
    "eval.preamble",
}
D_DIFFERING_KEYS = {
    "experiment.id",
    "data.eval_template_set",
    "eval.batteries",
    "eval.task_subset",
}
S_D_DIFFERING_KEYS = {
    "experiment.id",
    "data.eval_template_set",
    "eval.anchor_manifest",
    "eval.task_subset",
    "eval.threshold_sweep_arm",
}

# (d) のテンプレート集合と、そこに足す一文(PLAN-026 §3.4。T3 の文面の末尾と同じ文字列)。
D_TEMPLATE_SET = "order6b_d"
ANSWER_SENTENCE = " Answer Yes or No."

# 件数(**組合せ論的な帰結であって実験結果ではない**。PLAN-026 §3 の表・§4.3・§4.4)。
N_POOL_ITEMS = 1640
N_PREAMBLE_ARM = 1440  # 比較 960 + T1 240 + T2 240
N_D = 480  # T1b(gt 240 + lt 240)
N_S_POOL = 2400
N_S_D = 1200

# 判定規則に渡す候補 id(1 綴りずつ)。**重みもトークナイザも要らない。**
CANDIDATE_IDS: Mapping[bool, tuple[int, ...]] = {True: (0,), False: (1,)}
CONSTANT_RESPONSE = "I cannot say."


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_run_real.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


# --------------------------------------------------------------------------
# 道具
# --------------------------------------------------------------------------


def write_config(config: Mapping[str, Any], path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(dict(config), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return path


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """入れ子の config を `a.b.c` の鍵の辞書にする(`test_preamble.py` と同じ形)。"""
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


def config_at(path: Path, pool_dir: Path) -> dict[str, Any]:
    """config を読み、anchor を tmp に組み直したプールへ向ける。"""
    config = load_config(path)
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    return config


def recording_generator() -> tuple[Callable[[Sequence[str]], list[str]], list[str]]:
    seen: list[str] = []

    def generator(prompts: Sequence[str]) -> list[str]:
        seen.extend(prompts)
        return [CONSTANT_RESPONSE for _ in prompts]

    return generator, seen


def recording_scorer() -> tuple[ForcedChoiceScorer, list[str]]:
    seen: list[str] = []

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        seen.extend(prompts)
        # 上位 k は順6b の config の宣言どおりの個数の置き物(PLAN-026 §4.10 読み6)
        choice = with_filler_top_tokens(choose_from_logprobs([-0.25, -0.5], CANDIDATE_IDS))
        return [choice for _ in prompts]

    return scorer, seen


def execute_fixed(config: Mapping[str, Any], tmp: Path) -> tuple[Path, list[str]]:
    generator, generated = recording_generator()
    scorer, scored = recording_scorer()
    run_dir = run.execute(
        config,
        config_path=write_config(config, tmp / "config.yaml"),
        run_dir=tmp / "run",
        generator=generator,
        scorer=scorer,
    )
    return run_dir, generated + scored


def execute_sweep(config: Mapping[str, Any], tmp: Path) -> tuple[Path, list[str]]:
    scorer, scored = recording_scorer()
    run_dir = run.execute_threshold_sweep(
        config,
        config_path=write_config(config, tmp / "config.yaml"),
        run_dir=tmp / "run",
        scorer=scorer,
    )
    return run_dir, scored


def predictions_rows(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((run_dir / "predictions").glob("*.jsonl")):
        rows.extend(
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
        )
    return rows


def read_metrics(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pool_dirs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """パイロット用プールと S の掃引プールを tmp に書く(約 8 秒。module で 1 度だけ)。"""
    config = load_config(PILOT_CONFIG)
    root = tmp_path_factory.mktemp("battery")
    source = eval_pool.build(config)
    dirs = {"pilot": root / "pilot", "s": root / "pilot_sweep_s"}
    eval_pool.write_pool(source, dirs["pilot"])
    eval_pool.write_pool(sweep_pool.build_sweep_pool(config, source, "s"), dirs["s"])
    return dirs


# --------------------------------------------------------------------------
# 宣言の読みと名前(PLAN-026 §4.8 読み1・読み2)
# --------------------------------------------------------------------------


def test_the_task_type_names_come_from_the_category_axes() -> None:
    """★書いてよい名前は ADR-026 の水準名 + 指示付き T1。**表を作らず CATEGORY_AXES から引く。**"""
    assert task_subset.task_types_by_group() == {
        numeric_sum.T1: numeric_sum.GROUP_BARE_SUM,
        numeric_sum.T1_INSTRUCTED: numeric_sum.GROUP_BARE_SUM_INSTRUCTED,
        numeric_sum.T2: numeric_sum.GROUP_WORD_PROBLEM,
        t3_comparison.T3: t3_comparison.GROUP,
        t3_comparison.T1B: t3_comparison.GROUP,
    }


def test_the_task_type_of_an_item_follows_its_category(pool_dirs: dict[str, Path]) -> None:
    """★タスク型は category から引く(群からは決まらない)。特異性対照は持たない(None)。"""
    items = read_items(pool_dirs["pilot"] / "items.jsonl")
    by_category = {item.category: task_subset.task_type_of_item(item) for item in items}
    assert by_category["t3_gt"] == by_category["t3_lt"] == t3_comparison.T3
    assert by_category["t1b_gt"] == by_category["t1b_lt"] == t3_comparison.T1B
    assert by_category["t1"] == numeric_sum.T1
    assert by_category["t1_instructed"] == numeric_sum.T1_INSTRUCTED
    assert by_category["t2_count"] == numeric_sum.T2
    for category in specificity_control.CATEGORIES:
        assert by_category[category] is None


def test_an_unknown_category_stops(pool_dirs: dict[str, Path]) -> None:
    item = read_items(pool_dirs["pilot"] / "items.jsonl")[0]
    with pytest.raises(ConfigError, match="未知の category"):
        task_subset.task_type_of_item(dataclasses.replace(item, category="t9_nope"))


@pytest.mark.parametrize(
    "declared",
    ["t1b", [], [""], ["   "], [3], ["t1b", "t1b"], ["T1b"], ["comparison"], ["specificity"]],
)
def test_a_broken_declaration_stops(declared: Any) -> None:
    with pytest.raises(ConfigError, match="eval.task_subset"):
        task_subset.declared_task_subset({"eval": {"task_subset": declared}})


def test_no_declaration_means_the_whole_pool() -> None:
    assert task_subset.declared_task_subset({"eval": {"task_subset": None}}) is None
    assert task_subset.declared_task_subset({"eval": {}}) is None
    assert task_subset.declared_task_subset({}) is None


def test_the_subset_and_the_explicit_list_cannot_be_declared_together() -> None:
    """★明示リストの項目は絞りを通らないので、同時宣言は止める(PLAN-026 §4.8 読み8)。"""
    config = {"eval": {"task_subset": ["t1b"], "dry_run_items": [{"group": "comparison"}]}}
    with pytest.raises(ConfigError, match="eval.dry_run_items"):
        task_subset.declared_task_subset(config)
    assert task_subset.DRY_RUN_ITEMS_KEY == run.DRY_RUN_ITEMS_KEY


def test_a_declaration_that_does_not_match_the_batteries_stops() -> None:
    """★宣言と eval.batteries の噛み合わせを両方向で見る。"""
    with pytest.raises(ConfigError, match="群が eval.batteries"):
        task_subset.check_declaration(["t1"], ["comparison"])
    with pytest.raises(ConfigError, match="1 つも無い"):
        task_subset.check_declaration(["t1b"], ["comparison", "bare_sum"])
    with pytest.raises(ConfigError, match="特異性対照"):
        task_subset.check_declaration(["t1b"], ["comparison", "specificity"])


def test_a_declared_task_type_absent_from_the_pool_stops(pool_dirs: dict[str, Path]) -> None:
    """★宣言した水準がプールに 1 件も無ければ止める(綴り違いを黙って通さない)。"""
    items = [
        item
        for item in read_items(pool_dirs["pilot"] / "items.jsonl")
        if task_subset.task_type_of_item(item) != t3_comparison.T3
    ]
    solved = task_subset.select_task_subset(items, ["t3", "t1b"], ["comparison"])
    with pytest.raises(ConfigError, match="1 件も無い"):
        task_subset.check_selected(["t3", "t1b"], solved)


def test_the_record_counts_what_was_dropped(pool_dirs: dict[str, Path]) -> None:
    """★記録は「プールの件数・解いた件数・外した (群 × タスク型) ごとの件数」。"""
    items = read_items(pool_dirs["pilot"] / "items.jsonl")
    solved = task_subset.select_task_subset(items, ["t1b"], ["comparison"])
    record = task_subset.subset_record(["t1b"], items, solved)
    assert record is not None
    assert record["task_types"] == ["t1b"]
    assert record["n_pool_items"] == N_POOL_ITEMS
    assert record["n_items"] == N_D
    assert record["n_dropped"] == N_POOL_ITEMS - N_D
    assert record["dropped"] == [
        {"group": "bare_sum", "task_type": "t1", "n": 240},
        {"group": "bare_sum_instructed", "task_type": "t1_instructed", "n": 80},
        {"group": "comparison", "task_type": "t3", "n": 480},
        {"group": "specificity", "task_type": None, "n": 120},
        {"group": "word_problem", "task_type": "t2", "n": 240},
    ]
    assert sum(entry["n"] for entry in record["dropped"]) == record["n_dropped"]
    assert task_subset.subset_record(None, items, items) is None
    assert task_subset.subset_line(None) == "絞り: なし(プール全体)"
    line = task_subset.subset_line(record)
    assert "解く 480 / プール 1640" in line and "specificity 120" in line


# --------------------------------------------------------------------------
# config と (d) のテンプレート集合(PLAN-026 §4.8 読み6・読み7)
# --------------------------------------------------------------------------


def test_the_new_configs_differ_from_their_source_only_in_the_declared_keys() -> None:
    pilot, r8 = load_config(PILOT_CONFIG), load_config(R8_CONFIG)
    assert differing_keys(pilot, load_config(PREAMBLE_ARM_CONFIG)) == PREAMBLE_ARM_DIFFERING_KEYS
    assert differing_keys(pilot, load_config(D_CONFIG)) == D_DIFFERING_KEYS
    assert differing_keys(r8, load_config(S_D_CONFIG)) == S_D_DIFFERING_KEYS


def test_the_configs_declare_the_arms_of_plan_026() -> None:
    """★① は 3 群 × 4 タスク型、(d) と S-(d) は T1b だけ(PLAN-026 §3 の表)。"""
    preamble_arm = load_config(PREAMBLE_ARM_CONFIG)["eval"]
    assert preamble_arm["batteries"] == ["comparison", "bare_sum", "word_problem"]
    assert preamble_arm["task_subset"] == ["t3", "t1b", "t1", "t2"]
    assert preamble_arm["preamble"] is not None
    for path in (D_CONFIG, S_D_CONFIG):
        config = load_config(path)
        assert config["eval"]["batteries"] == ["comparison"]
        assert config["eval"]["task_subset"] == ["t1b"]
        assert config["data"]["eval_template_set"] == D_TEMPLATE_SET
        assert config["eval"].get("preamble") is None
    assert load_config(S_D_CONFIG)["eval"]["threshold_sweep_arm"] == "s"


def test_only_the_order6b_arms_declare_a_task_subset() -> None:
    """★本番・pilot・R8・S-① の config は絞りを持たない(プール全体を解く)。"""
    declaring = {
        path.name
        for path in sorted(CONFIG_DIR.glob("*.yaml"))
        if task_subset.declared_task_subset(load_config(path) or {}) is not None
    }
    assert declaring == SUBSET_CONFIGS


def test_the_d_template_set_is_the_production_t1b_plus_the_t3_sentence() -> None:
    """★(d) の文面 = 本番の t1b.yaml + t3.yaml の末尾の一文。**T3 は (d) の集合に無い。**"""
    t1b = yaml.safe_load((TEMPLATE_DIR / "t1b.yaml").read_text(encoding="utf-8"))["comparison"]
    t3 = yaml.safe_load((TEMPLATE_DIR / "t3.yaml").read_text(encoding="utf-8"))["comparison"]
    d_set = yaml.safe_load((TEMPLATE_DIR / f"{D_TEMPLATE_SET}.yaml").read_text(encoding="utf-8"))
    assert set(d_set) == {t3_comparison.GROUP}
    assert set(d_set[t3_comparison.GROUP]) == {t3_comparison.T1B_GT, t3_comparison.T1B_LT}
    for category, text in t3.items():
        assert text.endswith(ANSWER_SENTENCE), category
    for category, text in t1b.items():
        assert d_set[t3_comparison.GROUP][category] == text + ANSWER_SENTENCE


def test_the_production_templates_are_untouched() -> None:
    """★本番の T1b・T3 の文面は 1 文字も変わっていない(ADR-078 決定2)。"""
    t1b = yaml.safe_load((TEMPLATE_DIR / "t1b.yaml").read_text(encoding="utf-8"))["comparison"]
    t3 = yaml.safe_load((TEMPLATE_DIR / "t3.yaml").read_text(encoding="utf-8"))["comparison"]
    assert t1b == {"t1b_gt": "{a}+{b}>{threshold}?", "t1b_lt": "{a}+{b}<{threshold}?"}
    assert t3 == {
        "t3_gt": "Is the sum of {a} and {b} greater than {threshold}? Answer Yes or No.",
        "t3_lt": "Is the sum of {a} and {b} less than {threshold}? Answer Yes or No.",
    }
    eval_main = yaml.safe_load((TEMPLATE_DIR / "eval_main.yaml").read_text(encoding="utf-8"))
    assert eval_main["comparison"] == {**t1b, **t3}


# --------------------------------------------------------------------------
# 固定オフセットの経路(PLAN-026 §4.8 読み3・読み4)
# --------------------------------------------------------------------------


def test_the_preamble_arm_solves_three_groups(pool_dirs: dict[str, Path]) -> None:
    """★① は 1,640 のうち 1,440(比較 960 + T1 240 + T2 240)を解く。"""
    items = run.load_pool_items(config_at(PREAMBLE_ARM_CONFIG, pool_dirs["pilot"]))
    assert len(items) == N_PREAMBLE_ARM
    assert {item.group for item in items} == {"comparison", "bare_sum", "word_problem"}
    assert {task_subset.task_type_of_item(item) for item in items} == {"t3", "t1b", "t1", "t2"}


def test_the_d_arm_solves_only_t1b_with_the_instruction(pool_dirs: dict[str, Path]) -> None:
    """★(d) は T1b の 480 だけを解き、その文面は本番の T1b に一文を足したものである。"""
    config = config_at(D_CONFIG, pool_dirs["pilot"])
    items = run.load_pool_items(config)
    assert len(items) == N_D
    assert {task_subset.task_type_of_item(item) for item in items} == {t3_comparison.T1B}
    prompts = run.render_prompts(
        config, t3_comparison.GROUP, items, template_set=config["data"]["eval_template_set"]
    )
    assert len(prompts) == N_D
    for prompt in prompts.values():
        assert prompt.endswith(ANSWER_SENTENCE.strip())
        assert "the sum of" not in prompt


def test_a_run_without_a_declaration_still_solves_the_whole_pool(
    pool_dirs: dict[str, Path],
) -> None:
    """★絞りの宣言が無い run(B0)は今までどおり 1,640 を解く。"""
    assert len(run.load_pool_items(config_at(PILOT_CONFIG, pool_dirs["pilot"]))) == N_POOL_ITEMS


def test_narrowing_the_batteries_without_a_declaration_stops(pool_dirs: dict[str, Path]) -> None:
    """★宣言の無いまま群を減らせば今までどおり止まる(黙って項目数が減らない)。"""
    config = config_at(PILOT_CONFIG, pool_dirs["pilot"])
    config["eval"]["batteries"] = ["comparison"]
    with pytest.raises(ConfigError, match="eval.task_subset"):
        run.load_pool_items(config)


def test_a_declared_group_without_items_still_stops(pool_dirs: dict[str, Path]) -> None:
    """★宣言した群がプールに無ければ、絞りがあっても止まる。"""
    config = config_at(D_CONFIG, pool_dirs["pilot"])
    config["eval"]["batteries"] = ["comparison", "word_problem"]
    config["eval"]["task_subset"] = ["t1b", "t2"]
    items = [
        item
        for item in read_items(pool_dirs["pilot"] / "items.jsonl")
        if item.group != "word_problem"
    ]
    with pytest.raises(ConfigError, match="1件も無い"):
        run.solved_pool_items(config, items)


def test_the_fixed_route_records_the_subset(pool_dirs: dict[str, Path], tmp_path: Path) -> None:
    """★(d) の本実行: モデルに渡るのは 480 件だけで、外した分が metrics.json と log.txt に残る。"""
    config = config_at(D_CONFIG, pool_dirs["pilot"])
    run_dir, sent = execute_fixed(config, tmp_path)
    assert len(sent) == N_D
    assert all(prompt.endswith(ANSWER_SENTENCE.strip()) for prompt in sent)
    rows = predictions_rows(run_dir)
    assert len(rows) == N_D
    metrics = read_metrics(run_dir)
    record = metrics["task_subset"]
    assert record["task_types"] == ["t1b"]
    assert record["n_items"] == N_D and record["n_pool_items"] == N_POOL_ITEMS
    assert metrics["pool"]["n_items"] == N_D
    assert task_subset.subset_line(record) in (run_dir / "log.txt").read_text(encoding="utf-8")


def test_the_fixed_route_without_a_subset_records_null(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★絞りの無い run でも欄は置き、値は null(「この記録が入る前の run」と区別する)。"""
    run_dir, sent = execute_fixed(config_at(PILOT_CONFIG, pool_dirs["pilot"]), tmp_path)
    assert len(sent) == N_POOL_ITEMS
    metrics = read_metrics(run_dir)
    assert "task_subset" in metrics and metrics["task_subset"] is None
    assert "絞り: なし(プール全体)" in (run_dir / "log.txt").read_text(encoding="utf-8")


def test_dry_runs_report_the_subset(pool_dirs: dict[str, Path]) -> None:
    report = run.dry_run(config_at(PREAMBLE_ARM_CONFIG, pool_dirs["pilot"]))
    assert report["n_items"] == N_PREAMBLE_ARM
    assert report["task_subset"]["n_items"] == N_PREAMBLE_ARM
    assert report["task_subset"]["n_dropped"] == N_POOL_ITEMS - N_PREAMBLE_ARM
    assert run.dry_run(config_at(PILOT_CONFIG, pool_dirs["pilot"]))["task_subset"] is None


def test_a_broken_declaration_stops_before_the_run_dir(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★噛み合わない宣言は、重みを読む前・run ディレクトリを作る前に止まる。"""
    config = config_at(D_CONFIG, pool_dirs["pilot"])
    config["eval"]["task_subset"] = ["t1"]
    with pytest.raises(ConfigError, match="eval.task_subset"):
        execute_fixed(config, tmp_path)
    with pytest.raises(ConfigError, match="eval.task_subset"):
        run.dry_run(config)
    assert not (tmp_path / "run").exists()


# --------------------------------------------------------------------------
# 掃引の経路(PLAN-026 §4.8 読み3・読み5)
# --------------------------------------------------------------------------


def test_the_sweep_route_solves_only_the_declared_task_type(pool_dirs: dict[str, Path]) -> None:
    """★S-(d) は S のプール 2,400 のうち T1b の 1,200 を解く(S-① は 2,400 のまま)。"""
    pool = run.load_threshold_sweep_pool(config_at(S_D_CONFIG, pool_dirs["s"]))
    assert len(pool.items) == N_S_D
    assert pool.task_types == (t3_comparison.T1B,)
    assert pool.settings.task_types == ("t3", "t1b")  # プール側は両方のまま
    assert pool.subset is not None and pool.subset["n_pool_items"] == N_S_POOL
    without = run.load_threshold_sweep_pool(config_at(S_PREAMBLE_CONFIG, pool_dirs["s"]))
    assert len(without.items) == N_S_POOL and without.subset is None


def test_the_sweep_completeness_is_checked_on_the_whole_pool(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★T3 の項目が 1 件欠けた S のプールは、T1b だけを解く S-(d) でも止まる。"""
    broken = tmp_path / "pool"
    broken.mkdir()
    (broken / "manifest.json").write_bytes((pool_dirs["s"] / "manifest.json").read_bytes())
    lines = (pool_dirs["s"] / "items.jsonl").read_text(encoding="utf-8").splitlines()
    dropped = next(line for line in lines if '"t3_gt"' in line)
    (broken / "items.jsonl").write_text(
        "\n".join(line for line in lines if line != dropped) + "\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="そろっていない"):
        run.load_threshold_sweep_pool(config_at(S_D_CONFIG, broken))


def test_the_sweep_route_records_the_subset_and_the_solved_task_types(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★S-(d) の本実行: predictions は t1b だけ、metrics の task_types も解いた [t1b]。"""
    run_dir, sent = execute_sweep(config_at(S_D_CONFIG, pool_dirs["s"]), tmp_path)
    assert len(sent) == N_S_D
    assert sorted(path.name for path in (run_dir / "predictions").glob("*.jsonl")) == [
        "threshold_sweep.t1b.jsonl"
    ]
    metrics = read_metrics(run_dir)
    assert metrics["threshold_sweep"]["task_types"] == ["t1b"]
    assert metrics["threshold_sweep"]["predictions"] == {"threshold_sweep.t1b": N_S_D}
    assert set(metrics["threshold_sweep"]["n_items_by_cell"]) == {
        f"t1b_{coverage}_{carry}"
        for coverage in ("id", "interp", "extrap_magnitude")
        for carry in ("carry", "nocarry")
    }
    assert metrics["task_subset"]["n_items"] == N_S_D
    assert metrics["pool"]["n_items"] == N_S_D
    assert all(row["task_type"] == "t1b" for row in predictions_rows(run_dir))


def test_r8_fit_reads_the_narrowed_sweep_run(pool_dirs: dict[str, Path], tmp_path: Path) -> None:
    """★I5 の当てはめは、絞った掃引の run を手を入れずに読める(セルは T1b の 3 つ)。

    採点器は定数を返すので、どのセルも「片側だけ」で除外される。**ここで見るのは配線であって
    当てはめの値ではない**(定数の答えに意味は無い)。
    """
    run_dir, _ = execute_sweep(config_at(S_D_CONFIG, pool_dirs["s"]), tmp_path)
    report = r8_fit.run_report(run_dir / "metrics.json")
    assert report["task_types"] == ["t1b"]
    assert {(cell["task_type"], cell["coverage"]) for cell in report["cells"]} == {
        ("t1b", coverage) for coverage in ("id", "interp", "extrap_magnitude")
    }


def test_the_magnitude_sweep_refuses_a_task_subset(
    pool_dirs: dict[str, Path], tmp_path: Path
) -> None:
    """★桁数掃引は評価プールを読まないので、絞りを宣言した config を拒む(§4.8 読み8)。"""
    config = config_at(PILOT_CONFIG, pool_dirs["pilot"])
    config["eval"]["task_subset"] = ["t1"]
    with pytest.raises(ConfigError, match="eval.task_subset"):
        sweep.dry_run_summary(config)
    generator, generated = recording_generator()
    with pytest.raises(ConfigError, match="eval.task_subset"):
        sweep.execute(
            config,
            config_path=write_config(config, tmp_path / "config.yaml"),
            run_dir=tmp_path / "run",
            generator=generator,
        )
    assert not generated
    assert not (tmp_path / "run").exists()


# --------------------------------------------------------------------------
# preflight(PLAN-026 §4.8 読み7)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config_path", "format_hash_status"),
    [
        (PREAMBLE_ARM_CONFIG, preflight.Status.SKIP),  # 前置きがあるので検査6 は SKIP(I7)
        (D_CONFIG, preflight.Status.PASS),
        (S_D_CONFIG, preflight.Status.PASS),
    ],
)
def test_data_checks_pass_on_the_new_configs(
    config_path: Path, format_hash_status: preflight.Status
) -> None:
    config = preflight.load_config(config_path)
    results = {result.name: result for result in preflight.data_checks(config)}
    assert set(results) == set(preflight.DATA_CHECK_NAMES)
    assert results.pop("format hash").status is format_hash_status
    assert {result.status for result in results.values()} == {preflight.Status.PASS}, [
        (result.name, result.detail) for result in results.values()
    ]


def test_the_committed_pool_manifest_is_the_one_the_new_configs_point_at() -> None:
    """★3 本の config はコミット済みの manifest(pilot / S の掃引)を指している。

    件数は tmp に組み直したプールで見る(`items.jsonl` は git に無い)。ここで見るのは行き先だけ。
    """
    assert load_config(PREAMBLE_ARM_CONFIG)["eval"]["anchor_manifest"] == load_config(PILOT_CONFIG)[
        "eval"
    ]["anchor_manifest"]
    assert load_config(D_CONFIG)["eval"]["anchor_manifest"].endswith("pilot/manifest.json")
    assert load_config(S_D_CONFIG)["eval"]["anchor_manifest"] == load_config(S_PREAMBLE_CONFIG)[
        "eval"
    ]["anchor_manifest"]
