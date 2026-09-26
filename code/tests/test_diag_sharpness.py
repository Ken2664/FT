"""段2 の診断(PLAN-032 I1〜I3。§8.1 R1。ADR-107 決定1・2・6)の項目プール・文面・config。

答える問い: 「診断の 4 腕(B・A・B-d・A-d)は、§8.1 R1 の組・θ・文面で、T < 1 の項目を作らず、
R8・S を 1 バイトも変えずに組まれているか」

**モデルの重みは 1 度も読まない。ここに出る件数は組合せ論的な帰結であって実験結果ではない。**

ここで固定する最重要の性質:
  - **R1 の組**: 併合セルの全 80 組。ハッシュの順なので**先頭 20 組は R8 の 20 組と同じ**
  - **R1 の θ**: L1 の 19 水準。**T = t + θ < 1 の項目は作らず**、除いた (併合セル × 極性 × θ) と件数を
    manifest に残す(関数を通さずに数え直して一致する)。**Δ₂ の 5 水準には除外が掛からない**(160 件ずつ)
  - **R8・S は変わらない**: コミット済みの manifest に下限の鍵が無く、items.jsonl の sha256 も同じ
  - **R1 の文面**: A・A-d の文面は R1 の表と 1 バイトずつ一致し、B・B-d の和の部分だけを x に置き換えたもの。
    既存のテンプレートの描画は `{x}` を足しても変わらない
  - **config**: 写し元と宣言した欄だけが違い、batch 4・上位 k 20・近接同点 0.25。dry-run が通り、
    manifest と config の下限・除外の記録・項目の欠けが食い違えば run ディレクトリを作る前に止まる
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import preflight
import pytest
import yaml

from code.config import ConfigError, load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.battery_items import Item, read_items, write_items
from code.data_gen.hashing import sha256_file
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import run
from code.eval.battery import t3_comparison
from code.lesion import reference_lesions_from_config
from code.tests.test_threshold_sweep_run import differing_keys, forbidden

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
TEMPLATE_DIR = CONFIG_DIR / "templates"
PILOT_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"
POOL_CONFIG = CONFIG_DIR / "exp_diag_pool.yaml"
ARMS = ("b", "a", "b_d", "a_d")
DIAG_ARM = "diag"


def arm_config_path(arm: str) -> Path:
    return CONFIG_DIR / f"exp_diag_{arm}.yaml"


# §8.1 R1 の転記(config と文面がこれとずれたら落とす)。
L1_OFFSETS = [-300, -100, -50, -20, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 20, 50, 100, 300]
PAIRS_PER_CELL = 80
MIN_THRESHOLD = 1
R8_PAIRS_PER_CELL = 20
DELTA2_LEVELS = (-2, -1, 0, 1, 2)
N_PER_LEVEL = 160  # 80 組 × carry 2(R7)
N_CELLS = 12  # (T3・T1b) × 既知性 3 × carry 2
N_BEFORE_EXCLUSION_BY_TASK = PAIRS_PER_CELL * 6 * 2 * len(L1_OFFSETS)  # 18,240
R1_TEXTS: dict[str, dict[str, str]] = {
    "diag_explicit": {
        "t1b_gt": "{x}>{threshold}?",
        "t1b_lt": "{x}<{threshold}?",
        "t3_gt": "Is {x} greater than {threshold}? Answer Yes or No.",
        "t3_lt": "Is {x} less than {threshold}? Answer Yes or No.",
    },
    "diag_explicit_d": {
        "t1b_gt": "{x}>{threshold}? Answer Yes or No.",
        "t1b_lt": "{x}<{threshold}? Answer Yes or No.",
    },
}
# B・B-d の和の部分(R1: T1b は `{a}+{b}`、T3 は `the sum of {a} and {b}`)。
SUM_PART = {t3_comparison.T1B: "{a}+{b}", t3_comparison.T3: "the sum of {a} and {b}"}
# (明示の文面の集合, 和の文面の集合)。R1 の対。
PAIRED_TEMPLATE_SETS = (("diag_explicit", "eval_main"), ("diag_explicit_d", "order6b_d"))

# 腕の config が掃引プールの config と違ってよい欄(各 config の冒頭の注記)。
SHARPNESS_KEYS = {
    "sharpness.arm",
    "sharpness.arm_template_sets.b",
    "sharpness.arm_template_sets.a",
    "sharpness.arm_template_sets.b_d",
    "sharpness.arm_template_sets.a_d",
    "sharpness.delta2_shift",
    "sharpness.delta2_line",
    "sharpness.n_per_level",
    "sharpness.ci_level",
}
COMMON_ARM_KEYS = {
    "experiment.id",
    "eval.anchor_manifest",
    "eval.batteries",
    "eval.threshold_sweep_arm",
} | SHARPNESS_KEYS
ARM_DIFFERING_KEYS = {
    "b": COMMON_ARM_KEYS,
    "a": COMMON_ARM_KEYS | {"data.eval_template_set"},
    "b_d": COMMON_ARM_KEYS | {"data.eval_template_set", "eval.task_subset"},
    "a_d": COMMON_ARM_KEYS | {"data.eval_template_set", "eval.task_subset"},
}
POOL_DIFFERING_KEYS = {
    "experiment.id",
    "experiment.plan",
    "eval.threshold_sweep.pairs_per_cell",
    "eval.threshold_sweep.min_threshold",
    "eval.threshold_sweep.offsets.r8",
    "eval.threshold_sweep.offsets.s",
    "eval.threshold_sweep.offsets.diag",
    "resources.estimated_gpu_hours",
}
ARM_TEMPLATE_SETS = {"b": "eval_main", "a": "diag_explicit", "b_d": "order6b_d", "a_d": "diag_explicit_d"}
ARM_TASK_SUBSET = {"b": None, "a": None, "b_d": ["t1b"], "a_d": ["t1b"]}


def load_templates(name: str) -> dict[str, str]:
    return yaml.safe_load((TEMPLATE_DIR / f"{name}.yaml").read_text(encoding="utf-8"))["comparison"]


# --------------------------------------------------------------------------
# fixture(パイロット用プールの組み直し 約 8 秒。module で 1 度だけ)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pool_config() -> dict[str, Any]:
    return load_config(POOL_CONFIG)


@pytest.fixture(scope="module")
def source_pool(pool_config: dict[str, Any]) -> eval_pool.EvalPool:
    return eval_pool.build(pool_config)


@pytest.fixture(scope="module")
def diag_pool(pool_config: dict[str, Any], source_pool: eval_pool.EvalPool) -> eval_pool.EvalPool:
    return sweep_pool.build_sweep_pool(pool_config, source_pool, DIAG_ARM)


@pytest.fixture(scope="module")
def r8_pool(source_pool: eval_pool.EvalPool) -> eval_pool.EvalPool:
    return sweep_pool.build_sweep_pool(load_config(PILOT_CONFIG), source_pool, "r8")


@pytest.fixture(scope="module")
def pool_dirs(
    tmp_path_factory: pytest.TempPathFactory,
    source_pool: eval_pool.EvalPool,
    pool_config: dict[str, Any],
) -> dict[str, Path]:
    """パイロット用プールと診断の掃引プールを tmp に書く(repo の items.jsonl を当てにしない)。"""
    root = tmp_path_factory.mktemp("battery")
    dirs = {"pilot": root / "pilot", DIAG_ARM: root / "pilot_sweep_diag"}
    eval_pool.write_pool(copy.deepcopy(source_pool), dirs["pilot"])
    eval_pool.write_pool(
        sweep_pool.build_sweep_pool(pool_config, source_pool, DIAG_ARM), dirs[DIAG_ARM]
    )
    return dirs


def arm_config(arm: str, pool_dir: Path) -> dict[str, Any]:
    config = load_config(arm_config_path(arm))
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    return config


def recount_exclusions(fill: Mapping[str, Any]) -> dict[str, dict[str, dict[str, int]]]:
    """除外を関数を通さずに数え直す(T = a + b + θ < 1 の組の数。極性ごとに同じ)。"""
    by_cell: dict[str, dict[str, dict[str, int]]] = {}
    for name, cell in fill["cells"].items():
        for theta in fill["threshold_offsets"]:
            n = sum(1 for a, b in cell["pairs"] if a + b + theta < MIN_THRESHOLD)
            if n:
                for polarity in ("gt", "lt"):
                    by_cell.setdefault(name, {}).setdefault(polarity, {})[str(theta)] = n
    return by_cell


# --------------------------------------------------------------------------
# I1: 掃引プール(§8.1 R1)
# --------------------------------------------------------------------------


def test_pool_config_differs_from_the_pilot_config_only_in_the_declared_keys() -> None:
    """★掃引プールの config は pilot の config と宣言した欄だけが違う(pilot の config は変えない)。"""
    pilot, pool = load_config(PILOT_CONFIG), load_config(POOL_CONFIG)
    assert differing_keys(pilot, pool) == POOL_DIFFERING_KEYS
    assert pool["experiment"]["plan"] == "plans/PLAN-032-sharpness-diagnostic.md"
    assert "min_threshold" not in pilot["eval"]["threshold_sweep"]


def test_diag_settings_are_the_r1_levels(pool_config: dict[str, Any]) -> None:
    """★θ = L1 の 19 水準・80 組・T ≥ 1・T3 と T1b(§8.1 R1)。"""
    settings = sweep_pool.load_sweep_settings(pool_config, DIAG_ARM)
    assert list(settings.offsets) == L1_OFFSETS
    assert settings.pairs_per_cell == PAIRS_PER_CELL
    assert settings.min_threshold == MIN_THRESHOLD
    assert settings.task_types == (t3_comparison.T3, t3_comparison.T1B)
    assert set(DELTA2_LEVELS) <= set(settings.offsets)


def test_r8_and_s_declare_no_floor() -> None:
    config = load_config(PILOT_CONFIG)
    for arm in ("r8", "s"):
        assert sweep_pool.load_sweep_settings(config, arm).min_threshold is None


@pytest.mark.parametrize("value", [True, "1", 1.5, [1]])
def test_a_broken_floor_stops(value: Any) -> None:
    block = {"task_types": ["t3"], "pairs_per_cell": 2, "offsets": {"x": [0]}, "min_threshold": value}
    with pytest.raises(ConfigError, match="min_threshold"):
        sweep_pool.load_sweep_settings({"eval": {"threshold_sweep": block}}, "x")


def test_kept_pairs_uses_t_plus_theta_at_least_the_floor() -> None:
    """境界を含む(T = 1 は作る)。下限が無ければ全部。並びは渡したまま。"""
    pairs = [(3, 4), (1, 1), (2, 5), (1, 2)]  # 和 7 / 2 / 7 / 3
    assert sweep_pool.kept_pairs(pairs, -6, None) == pairs
    assert sweep_pool.kept_pairs(pairs, -6, 1) == [(3, 4), (2, 5)]  # T = 1 / −4 / 1 / −3
    assert sweep_pool.kept_pairs(pairs, -2, 1) == [(3, 4), (2, 5), (1, 2)]  # T = 0 は作らない


def test_sweep_items_drop_only_the_items_below_the_floor() -> None:
    cell = sweep_pool.SweepCell("t1b", "id", "carry", ("t1b_gt_id_carry", "t1b_lt_id_carry"))
    lesions = reference_lesions_from_config(load_config(PILOT_CONFIG))
    pairs = [(2, 3), (40, 50)]
    without = sweep_pool.sweep_items({cell: pairs}, [-10, 0], pool_id="pilot", lesions=lesions)
    with_floor = sweep_pool.sweep_items(
        {cell: pairs}, [-10, 0], pool_id="pilot", lesions=lesions, min_threshold=1
    )
    assert len(without) == 2 * 2 * 2
    dropped = {item.item_id for item in without} - {item.item_id for item in with_floor}
    assert len(dropped) == 2  # (2, 3) の θ = −10(T = −5)× 2 極性
    assert all(item.params["threshold"] >= 1 for item in with_floor)
    assert {item.item_id for item in with_floor} < {item.item_id for item in without}
    record = sweep_pool.below_min_threshold_record({cell: pairs}, [-10, 0], 1)
    assert record is not None and record["n_excluded"] == 2
    assert record["by_cell"] == {cell.name: {"gt": {"-10": 1}, "lt": {"-10": 1}}}
    assert sweep_pool.below_min_threshold_record({cell: pairs}, [-10, 0], None) is None


def test_diag_counts_and_the_exclusion_record(diag_pool: eval_pool.EvalPool) -> None:
    """★除外の前は T3・T1b とも 18,240。manifest の除外は関数を通さずに数え直した値と一致する。"""
    fill = diag_pool.manifest["fill"]
    record = fill["below_min_threshold"]
    assert fill["min_threshold"] == MIN_THRESHOLD
    assert record["by_cell"] == recount_exclusions(fill)
    excluded_by_task: Counter[str] = Counter()
    for name, by_polarity in record["by_cell"].items():
        task = next(cell for cell in ("t3", "t1b") if name.startswith(cell + "_"))
        excluded_by_task[task] += sum(n for by_theta in by_polarity.values() for n in by_theta.values())
    assert record["n_excluded"] == sum(excluded_by_task.values()) > 0
    counts = Counter(t3_comparison.task_type_of(item.category) for item in diag_pool.items)
    for task in ("t3", "t1b"):
        assert counts[task] == N_BEFORE_EXCLUSION_BY_TASK - excluded_by_task[task]
    assert fill["n_items_by_task_type"] == dict(counts)
    assert len(diag_pool.items) == 2 * N_BEFORE_EXCLUSION_BY_TASK - record["n_excluded"]


def test_no_item_has_a_threshold_below_the_floor(diag_pool: eval_pool.EvalPool) -> None:
    """★負例: T < 1 の項目が 1 つも無い(閾値は T = t + θ のまま)。"""
    for item in diag_pool.items:
        a, b = item.operands
        assert item.params["threshold"] == a + b + item.params["threshold_offset"]
        assert item.params["threshold"] >= MIN_THRESHOLD


def test_the_delta2_levels_have_every_pair(diag_pool: eval_pool.EvalPool) -> None:
    """★Δ₂ の 5 水準は (タスク型 × 既知性 × 極性) ごとに 160 件そろう(除外が掛からない。R7 の前提)。"""
    counts = Counter()
    fill = diag_pool.manifest["fill"]
    cell_of_pair = {tuple(p): name for name, cell in fill["cells"].items() for p in cell["pairs"]}
    for item in diag_pool.items:
        theta = item.params["threshold_offset"]
        if theta in DELTA2_LEVELS:
            name = cell_of_pair[tuple(item.operands)]
            task = t3_comparison.task_type_of(item.category)
            coverage = next(c for c in MAIN_COVERAGE_LEVELS if name.startswith(f"{task}_{c}_"))
            counts[(task, coverage, t3_comparison.polarity_of(item.category), theta)] += 1
    assert len(counts) == 2 * len(MAIN_COVERAGE_LEVELS) * 2 * len(DELTA2_LEVELS)
    assert set(counts.values()) == {N_PER_LEVEL}


def test_diag_takes_every_candidate_and_starts_with_the_r8_pairs(
    diag_pool: eval_pool.EvalPool, r8_pool: eval_pool.EvalPool, source_pool: eval_pool.EvalPool
) -> None:
    """★80 組 = 併合セルの全部。ハッシュの順なので先頭 20 組は R8 の 20 組(R8 ⊂ 診断)。"""
    diag_cells = diag_pool.manifest["fill"]["cells"]
    r8_cells = r8_pool.manifest["fill"]["cells"]
    assignment = source_pool.manifest["fill"]["assignment"]
    assert set(diag_cells) == set(r8_cells) and len(diag_cells) == N_CELLS
    for name, cell in diag_cells.items():
        candidates = {tuple(p) for source in cell["source_cells"] for p in assignment[source]}
        assert {tuple(p) for p in cell["pairs"]} == candidates
        assert len(cell["pairs"]) == cell["n_candidates"] == PAIRS_PER_CELL
        assert cell["pairs"][:R8_PAIRS_PER_CELL] == r8_cells[name]["pairs"]
    assert diag_pool.manifest["fill"]["source_pool_pairs_hash"] == json.loads(
        (eval_pool.OUTPUT_ROOT / "pilot" / "manifest.json").read_text(encoding="utf-8")
    )["pairs_hash"]


@pytest.mark.parametrize("arm", ["r8", "s"])
def test_r8_and_s_items_and_manifests_do_not_change(
    source_pool: eval_pool.EvalPool, tmp_path: Path, arm: str
) -> None:
    """★R8・S の items.jsonl の sha256 と manifest(fill に下限の鍵が無い)はコミット済みのものと同じ。"""
    committed = json.loads(
        (eval_pool.OUTPUT_ROOT / sweep_pool.sweep_dir_name("pilot", arm) / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    pool = sweep_pool.build_sweep_pool(load_config(PILOT_CONFIG), source_pool, arm)
    eval_pool.write_pool(pool, tmp_path / arm)
    assert sha256_file(tmp_path / arm / "items.jsonl") == committed["files"]["items.jsonl"]
    assert "min_threshold" not in pool.manifest["fill"]
    assert "below_min_threshold" not in pool.manifest["fill"]
    assert json.loads(json.dumps(pool.manifest, ensure_ascii=False)) == committed


def test_committed_diag_manifest_matches_the_rebuild(diag_pool: eval_pool.EvalPool) -> None:
    """★コミット済みの診断の掃引プールの manifest が config から再現できる。"""
    out_dir = eval_pool.OUTPUT_ROOT / sweep_pool.sweep_dir_name("pilot", DIAG_ARM)
    committed = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    committed.pop("files")
    rebuilt = json.loads(json.dumps(diag_pool.manifest, ensure_ascii=False))
    rebuilt.pop("files", None)
    assert rebuilt == committed


# --------------------------------------------------------------------------
# I2: 文面(§8.1 R1 の表)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(R1_TEXTS))
def test_explicit_templates_are_the_r1_table(name: str) -> None:
    """★A・A-d の文面は R1 の表と 1 バイトずつ一致する。"""
    assert load_templates(name) == R1_TEXTS[name]


@pytest.mark.parametrize(("explicit", "summed"), PAIRED_TEMPLATE_SETS)
def test_explicit_templates_replace_only_the_sum(explicit: str, summed: str) -> None:
    """★A は B の、A-d は B-d の和の部分(`{a}+{b}` / `the sum of {a} and {b}`)を `{x}` に置き換えたもの。"""
    summed_texts = load_templates(summed)
    explicit_texts = load_templates(explicit)
    assert set(explicit_texts) <= set(summed_texts)
    for category, text in explicit_texts.items():
        part = SUM_PART[t3_comparison.task_type_of(category)]
        assert summed_texts[category].count(part) == 1
        assert text == summed_texts[category].replace(part, "{x}")


def test_b_d_is_the_order6b_d_wording() -> None:
    """B-d は順6b の (d) と同じ文面(テンプレート集合そのもの)。本番の T1b + T3 の末尾の一文。"""
    order6b_d = load_templates("order6b_d")
    t1b = load_templates("t1b")
    assert order6b_d == {key: t1b[key] + " Answer Yes or No." for key in t1b}


@pytest.mark.parametrize(("explicit", "summed"), PAIRED_TEMPLATE_SETS)
def test_rendered_prompts_differ_only_in_the_sum(
    diag_pool: eval_pool.EvalPool, explicit: str, summed: str
) -> None:
    """★同じ項目の A と B(A-d と B-d)の描画は、和の部分を x の数字にした違いしかない(全項目)。"""
    explicit_texts, summed_texts = load_templates(explicit), load_templates(summed)
    checked = 0
    for item in diag_pool.items:
        if item.category not in explicit_texts:
            continue
        a, b = item.operands
        task = t3_comparison.task_type_of(item.category)
        part = SUM_PART[task].format(a=a, b=b)
        summed_prompt = t3_comparison.render_prompt(item, summed_texts)
        explicit_prompt = t3_comparison.render_prompt(item, explicit_texts)
        assert summed_prompt.count(part) == 1
        assert explicit_prompt == summed_prompt.replace(part, str(a + b))
        checked += 1
    assert checked == sum(1 for item in diag_pool.items if item.category in explicit_texts)


@pytest.mark.parametrize("name", ["eval_main", "order6b_d", "t1b", "t3"])
def test_existing_templates_render_as_before(diag_pool: eval_pool.EvalPool, name: str) -> None:
    """★負例: `{x}` を持たない既存のテンプレートの描画は、足す前の差し込み(a・b・threshold)と同じ。"""
    templates = load_templates(name)
    for item in diag_pool.items[:: 97]:
        if item.category not in templates:
            continue
        before = templates[item.category].format(
            a=item.operands[0], b=item.operands[1], threshold=item.params["threshold"]
        )
        assert t3_comparison.render_prompt(item, templates) == before


def test_render_prompt_fills_x_with_the_sum() -> None:
    item = t3_comparison.build_items(
        [(12, 30)],
        pool_id="pilot",
        category="t1b_gt",
        threshold_offset=5,
        reference_lesions=reference_lesions_from_config(load_config(PILOT_CONFIG)),
        sweep=True,
    )[0]
    assert t3_comparison.render_prompt(item, R1_TEXTS["diag_explicit"]) == "42>47?"


# --------------------------------------------------------------------------
# I3: config
# --------------------------------------------------------------------------


@pytest.mark.parametrize("arm", ARMS)
def test_arm_configs_differ_from_the_pool_config_only_in_the_declared_keys(arm: str) -> None:
    """★腕の config は掃引プールの config と宣言した欄だけが違う(冒頭の注記)。"""
    pool, config = load_config(POOL_CONFIG), load_config(arm_config_path(arm))
    assert differing_keys(pool, config) == ARM_DIFFERING_KEYS[arm]
    assert config["experiment"]["id"] == f"exp_diag_{arm}"
    assert config["eval"]["threshold_sweep_arm"] == DIAG_ARM
    assert config["eval"]["batteries"] == [t3_comparison.GROUP]
    assert config["eval"]["anchor_manifest"] == "data/generated/battery/pilot_sweep_diag/manifest.json"
    assert config["data"]["eval_template_set"] == ARM_TEMPLATE_SETS[arm]
    assert config["eval"].get("task_subset") == ARM_TASK_SUBSET[arm]


@pytest.mark.parametrize("arm", ARMS)
def test_arm_configs_run_as_decided(arm: str) -> None:
    """★batch 4(ADR-107 決定6)・上位 k 20・近接同点 0.25・adapter なし・pool_id pilot。"""
    config = load_config(arm_config_path(arm))
    assert config["eval"]["batch_size"] == 4
    assert config["eval"]["forced_choice_top_k"] == 20
    assert config["gonogo"]["near_tie_margin"] == 0.25
    assert config["model"]["adapter"] is None
    assert config["data"]["pool_id"] == "pilot"


def test_the_sharpness_blocks_agree_except_the_arm() -> None:
    """★sharpness 欄は arm 以外 4 本でバイト一致し、値は §8.1 R2・R3・R6・R7 の転記。"""
    blocks = {arm: dict(load_config(arm_config_path(arm))["sharpness"]) for arm in ARMS}
    for arm, block in blocks.items():
        assert block.pop("arm") == arm
    first = blocks[ARMS[0]]
    assert all(block == first for block in blocks.values())
    assert first == {
        "arm_template_sets": ARM_TEMPLATE_SETS,
        "delta2_shift": 2,
        "delta2_line": 0.088,
        "n_per_level": N_PER_LEVEL,
        "ci_level": 0.95,
    }


@pytest.mark.parametrize("name", ["pool", *ARMS])
def test_data_checks_pass_on_the_diag_configs(name: str) -> None:
    """★preflight の data_checks が 7 件すべて PASS(コミット済み manifest。items は要らない)。"""
    results = preflight.data_checks(preflight.load_config(CONFIG_DIR / f"exp_diag_{name}.yaml"))
    assert {r.name for r in results} == set(preflight.DATA_CHECK_NAMES)
    assert {r.status for r in results} == {preflight.Status.PASS}, [(r.name, r.detail) for r in results]


# --------------------------------------------------------------------------
# run.py の掃引の経路(下限の照合と記録)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("arm", ARMS)
def test_dry_run_counts_and_records_the_floor(pool_dirs: dict[str, Path], arm: str) -> None:
    """★dry-run: B・A はプール全体、B-d・A-d は T1b だけ。下限と除外の記録が報告に出る。"""
    config = arm_config(arm, pool_dirs[DIAG_ARM])
    items = read_items(pool_dirs[DIAG_ARM] / "items.jsonl")
    manifest = json.loads((pool_dirs[DIAG_ARM] / "manifest.json").read_text(encoding="utf-8"))
    solved = [
        item
        for item in items
        if ARM_TASK_SUBSET[arm] is None or t3_comparison.task_type_of(item.category) == "t1b"
    ]
    report = run.threshold_sweep_dry_run(config)
    assert report["n_items"] == len(solved)
    assert report["min_threshold"] == MIN_THRESHOLD
    assert report["below_min_threshold"] == manifest["fill"]["below_min_threshold"]
    assert report["threshold_offsets"] == L1_OFFSETS
    expected_categories = set(load_templates(ARM_TEMPLATE_SETS[arm]))
    assert set(report["example_prompts"]) == expected_categories
    lines = run.below_min_threshold_lines(report["min_threshold"], report["below_min_threshold"])
    assert lines[0].startswith("閾値の下限: T < 1")
    assert str(manifest["fill"]["below_min_threshold"]["n_excluded"]) in lines[0]


def test_below_min_threshold_lines_are_empty_without_a_floor() -> None:
    """R8・S の log.txt は今までどおり(下限の行を出さない)。"""
    assert run.below_min_threshold_lines(None, None) == []


def tampered_pool(
    pool_dirs: dict[str, Path], tmp: Path, edit_manifest: Any = None, drop_item: bool = False
) -> Path:
    """診断の掃引プールの写しを tmp に作り、manifest か items.jsonl を 1 か所だけ壊す。"""
    target = tmp / "pilot_sweep_diag"
    target.mkdir(parents=True)
    manifest = json.loads((pool_dirs[DIAG_ARM] / "manifest.json").read_text(encoding="utf-8"))
    items: list[Item] = read_items(pool_dirs[DIAG_ARM] / "items.jsonl")
    if edit_manifest is not None:
        edit_manifest(manifest["fill"])
    if drop_item:
        # Δ₂ の水準(θ = 0)の 1 項目だけを抜く
        index = next(i for i, item in enumerate(items) if item.params["threshold_offset"] == 0)
        items = items[:index] + items[index + 1 :]
    write_items(target / "items.jsonl", items)
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return target


def _drop_floor(fill: dict[str, Any]) -> None:
    fill.pop("min_threshold")
    fill.pop("below_min_threshold")


def _shift_floor(fill: dict[str, Any]) -> None:
    fill["min_threshold"] = 2


def _edit_record(fill: dict[str, Any]) -> None:
    fill["below_min_threshold"]["n_excluded"] += 1


@pytest.mark.parametrize(
    ("edit", "drop_item", "message"),
    [
        (_drop_floor, False, "min_threshold"),
        (_shift_floor, False, "min_threshold"),
        (_edit_record, False, "below_min_threshold"),
        (None, True, "そろっていない"),
    ],
)
def test_the_sweep_route_stops_on_a_floor_mismatch_before_the_run_dir(
    pool_dirs: dict[str, Path], tmp_path: Path, edit: Any, drop_item: bool, message: str
) -> None:
    """★負例: 下限の宣言・除外の記録・項目の欠けが食い違えば、重みを読む前・run ディレクトリを作る前に止まる。"""
    target = tampered_pool(pool_dirs, tmp_path, edit_manifest=edit, drop_item=drop_item)
    config = arm_config("b", target)
    run_dir = tmp_path / "run"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(run, "build_engines", forbidden("build_engines"))
        with pytest.raises(ConfigError, match=message):
            run.execute_threshold_sweep(
                config, config_path=arm_config_path("b"), run_dir=run_dir, scorer=None
            )
    assert not run_dir.exists()
