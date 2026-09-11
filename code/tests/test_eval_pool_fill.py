"""評価プールの `fill_cells` の経路(`code/data_gen/eval_pool.py`)。PLAN-023 手順3、ADR-076。

答える問い: 「セル表を埋めたプールは、ADR-076 が決めた性質を満たしているか」

ここで固定する最重要の性質:
  - **候補は main 領域と `Q(M*)` の main 側だけ**(ADR-076 決定10 (iii))。
    pilot 領域の組は1件も入らない / 分割を再現できなければ止まる
  - **`extrap_magnitude` のセルは `a, b > R` の組だけから埋まる**(決定10 (ii))
  - **組はセル間で再利用しない。例外は指示付き T1 だけ**(PLAN-001 §5.1 / ADR-035 決定2)
  - **T3 / T1b の閾値オフセットはセル内で半々・引いた順に交互**(決定4)
  - **同じ config なら同じプール**(決定性。preflight が再現して照合する)
  - **本番 config から組んだプールが、コミット済みの manifest と一致する**(順6 の条件)

FT データの manifest は tmp_path に**実際に生成して**使う(test_eval_pool.py と同じ規約)。
本番 config の検査だけは、コミット済みの FT manifest と評価プールの manifest を読む ——
**「GPU を使う前に項目集合が固定されたこと」が git に残っている**ことを確かめるのが目的だからである。
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

import preflight
import pytest
import yaml

from code.config import ConfigError, load_config
from code.data_gen import eval_pool
from code.data_gen.ft_data import generate, train_domain_pairs, write_dataset
from code.data_gen.pool import (
    COVERAGE_ID,
    COVERAGE_INTERP,
    POOL_MAIN,
    outside_domain_side,
    split_pilot_main,
)
from code.eval.battery import t3_comparison

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"
MAIN_POOL_MANIFEST = REPO_ROOT / "data" / "generated" / "battery" / "main" / "manifest.json"

# smoke の lesion ブロックから組み立てられる条件(test_eval_pool.py と同じ)。
SMOKE_CONDITIONS = ("p2", "x2", "ident")

# **テスト用の小さな M*。実験の値ではない。**smoke の訓練域 [1,9]^2 の外に
# Q(M) が数十組できれば足りる((20 − 9)^2 = 121 組の約半分が main 側)。
TEST_EXTRAPOLATION_RADIUS = 20

# テスト用のセル表。**本番のセル表ではない**(本番は configs/exp_phase1_main.yaml の 42 セル)。
# smoke の K は 20 組しかないので、繰り上がりで層別せず n を小さくしてある。
# T3 / T1b の n は閾値オフセット 2 つに等分できる偶数にする(ADR-076 決定4)。
TEST_CELLS: list[dict[str, Any]] = [
    {"name": "t1_id", "group": "bare_sum", "coverage": "id", "carry": None, "n": 2},
    {"name": "t1_interp", "group": "bare_sum", "coverage": "interp", "carry": None, "n": 2},
    {"name": "t1_ext", "group": "bare_sum", "coverage": "extrap_magnitude", "carry": None, "n": 2},
    {"name": "t3_gt_id", "group": "comparison", "category": "t3_gt", "coverage": "id",
     "carry": None, "n": 2},
    {"name": "t1b_lt_interp", "group": "comparison", "category": "t1b_lt", "coverage": "interp",
     "carry": None, "n": 2},
    {"name": "t3_lt_ext", "group": "comparison", "category": "t3_lt",
     "coverage": "extrap_magnitude", "carry": None, "n": 4},
    {"name": "t2_id", "group": "word_problem", "coverage": "id", "carry": None, "n": 2},
    {"name": "t2_ext", "group": "word_problem", "coverage": "extrap_magnitude", "carry": None,
     "n": 2},
    {"name": "spec_sub_id", "group": "specificity", "category": "spec_sub", "coverage": "id",
     "carry": None, "n": 2},
    {"name": "spec_mul_ext", "group": "specificity", "category": "spec_mul",
     "coverage": "extrap_magnitude", "carry": None, "n": 2},
]
TEST_BATTERIES = ["comparison", "bare_sum", "bare_sum_instructed", "word_problem", "specificity"]
TEST_POOL_SEED = 3


@pytest.fixture(scope="module")
def ft_manifest_paths(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    """smoke の FT データを1度だけ生成する(評価プールは FT データの後。ADR-017 案A)。"""
    smoke = yaml.safe_load(SMOKE_CONFIG.read_text(encoding="utf-8"))
    root = tmp_path_factory.mktemp("ft")
    declared = []
    for condition in SMOKE_CONDITIONS:
        per_condition = copy.deepcopy(smoke)
        per_condition["lesion"]["condition"] = condition
        write_dataset(generate(per_condition), root / condition)
        declared.append(str(root / condition / "manifest.json"))
    return declared


@pytest.fixture
def fill_config(ft_manifest_paths: list[str]) -> dict[str, Any]:
    """smoke を `fill_cells` の経路に切り替えた config(明示リストを消す)。"""
    config = yaml.safe_load(SMOKE_CONFIG.read_text(encoding="utf-8"))
    config["data"]["matched_manifests"] = list(ft_manifest_paths)
    config["eval"]["batteries"] = list(TEST_BATTERIES)
    config["eval"]["cells"] = copy.deepcopy(TEST_CELLS)
    config["eval"]["pool_seed"] = TEST_POOL_SEED
    config["eval"]["extrapolation_radius"] = TEST_EXTRAPOLATION_RADIUS
    config["eval"].pop("pool_items", None)
    return config


def own_ft_manifest(config: dict[str, Any]) -> dict[str, Any]:
    return eval_pool.load_condition_manifest(config)


def region_of(config: dict[str, Any], side: str) -> set[tuple[int, int]]:
    data = config["data"]
    regions = split_pilot_main(
        train_domain_pairs(data["train_domain_min"], data["train_domain_max"]),
        data["pilot_train_region_size"],
        data["pool_split_seed"],
    )
    return set(regions[side])


def assignment_of(pool: eval_pool.EvalPool) -> dict[str, list[tuple[int, int]]]:
    return {
        name: [tuple(pair) for pair in pairs]
        for name, pairs in pool.manifest["fill"]["assignment"].items()
    }


# --------------------------------------------------------------------------
# 経路の選択と記録
# --------------------------------------------------------------------------


def test_config_without_pool_items_goes_through_fill_cells(fill_config: dict[str, Any]) -> None:
    """★`eval.pool_items` が無ければ `fill_cells` の経路を通り、それが manifest に残る。"""
    pool = eval_pool.build(fill_config)
    assert pool.manifest["fill"]["method"] == eval_pool.FILL_CELLS
    assert pool.manifest["fill"]["seed_consumed"] is True
    assert pool.manifest["seed"] == TEST_POOL_SEED


def test_item_counts_follow_the_cell_table(fill_config: dict[str, Any]) -> None:
    """項目数 = セルの n の合計 + 指示付き T1(T1 の `id` セルの n)。"""
    pool = eval_pool.build(fill_config)
    by_cell = sum(cell["n"] for cell in TEST_CELLS)
    instructed = sum(
        cell["n"] for cell in TEST_CELLS if cell["group"] == "bare_sum" and cell["coverage"] == "id"
    )
    assert len(pool.items) == by_cell + instructed
    counts = Counter(item.group for item in pool.items)
    assert counts["bare_sum_instructed"] == instructed
    assert pool.manifest["fill"]["instructed_source_cells"] == ["t1_id"]


# --------------------------------------------------------------------------
# 候補(ADR-076 決定10 (iii))
# --------------------------------------------------------------------------


def test_cells_draw_from_the_right_population(fill_config: dict[str, Any]) -> None:
    """★`id` ⊂ K / `interp` は main 領域で K の外 / `extrap_magnitude` は `a, b > R` で main 側。"""
    pool = eval_pool.build(fill_config)
    coverage = {tuple(pair) for pair in own_ft_manifest(fill_config)["coverage"]["pairs"]}
    main_region = region_of(fill_config, POOL_MAIN)
    radius = fill_config["data"]["train_domain_max"]
    seed = fill_config["data"]["pool_split_seed"]
    cells = {cell["name"]: cell for cell in TEST_CELLS}
    for name, pairs in assignment_of(pool).items():
        level = cells[name]["coverage"]
        for pair in pairs:
            if level == COVERAGE_ID:
                assert pair in coverage
            elif level == COVERAGE_INTERP:
                assert pair in main_region and pair not in coverage
            else:
                assert pair[0] > radius and pair[1] > radius
                assert outside_domain_side(pair, seed) == POOL_MAIN


def test_no_pilot_region_pair_enters_the_pool(fill_config: dict[str, Any]) -> None:
    """★pilot 領域の組は1件も入らない(PLAN-023 A2)。"""
    pool = eval_pool.build(fill_config)
    pilot_region = region_of(fill_config, "pilot")
    assert not ({tuple(pair) for pair in pool.manifest["pairs"]} & pilot_region)


def test_region_hash_mismatch_stops_the_pool(fill_config: dict[str, Any]) -> None:
    """★分割を再現できなければ止まる(ADR-076 決定10 (iii))。"""
    config = copy.deepcopy(fill_config)
    config["data"]["pool_split_seed"] += 1
    with pytest.raises(ConfigError, match="counterpart_region_hash"):
        eval_pool.build(config)


# --------------------------------------------------------------------------
# セル(組の再利用 / 被覆の語彙 / 群と category)
# --------------------------------------------------------------------------


def test_pairs_are_not_reused_across_cells(fill_config: dict[str, Any]) -> None:
    """★組はセル間で再利用しない。指示付き T1 だけが T1 の `id` セルの組を借りる。"""
    pool = eval_pool.build(fill_config)
    assignment = assignment_of(pool)
    chosen = [pair for pairs in assignment.values() for pair in pairs]
    assert len(chosen) == len(set(chosen))
    instructed = sorted(item.operands for item in pool.items if item.group == "bare_sum_instructed")
    assert instructed == sorted(assignment["t1_id"])


def test_four_valued_extrap_cell_is_refused(fill_config: dict[str, Any]) -> None:
    """★`coverage: extrap` は C6 と取り違えるので止める(ADR-076 決定10 (ii))。"""
    config = copy.deepcopy(fill_config)
    config["eval"]["cells"][2]["coverage"] = "extrap"
    with pytest.raises(ValueError, match="extrap_magnitude"):
        eval_pool.build(config)


@pytest.mark.parametrize(
    ("index", "key", "value", "message"),
    [
        (0, "group", None, "group"),
        (3, "category", None, "category"),
        (0, "category", "t1", "category を書かない"),
        (3, "n", 3, "等分できない"),
    ],
)
def test_malformed_cells_are_refused(
    fill_config: dict[str, Any], index: int, key: str, value: Any, message: str
) -> None:
    """群・category・n の欠けや食い違いを既定値で補わずに止める(PLAN-023 A4)。"""
    config = copy.deepcopy(fill_config)
    config["eval"]["cells"][index][key] = value
    with pytest.raises(ConfigError, match=message):
        eval_pool.build(config)


# --------------------------------------------------------------------------
# 閾値オフセット(ADR-076 決定4 = ★F131)
# --------------------------------------------------------------------------


def test_threshold_offsets_alternate_within_each_cell(fill_config: dict[str, Any]) -> None:
    """★セル内で、引いた順に 2 つのオフセットへ交互に配る(乱数を使わない)。"""
    pool = eval_pool.build(fill_config)
    assignment = assignment_of(pool)
    by_pair_and_category = {
        (item.operands, item.category): item.params["threshold_offset"]
        for item in pool.items
        if item.group == "comparison"
    }
    for cell in TEST_CELLS:
        if cell["group"] != "comparison":
            continue
        offsets = t3_comparison.allowed_offsets(t3_comparison.polarity_of(cell["category"]))
        drawn = [by_pair_and_category[(pair, cell["category"])] for pair in assignment[cell["name"]]]
        assert drawn == [offsets[i % len(offsets)] for i in range(cell["n"])]
        tally = pool.manifest["fill"]["threshold_offsets"][cell["name"]]
        assert tally == {str(offset): cell["n"] // len(offsets) for offset in offsets}


def test_allowed_offsets_come_from_the_threshold_table() -> None:
    """`>` は {0, +1}、`<` は {+1, +2}(PLAN-003 §4.4.1 / THRESHOLD_RULES)。"""
    assert t3_comparison.allowed_offsets(t3_comparison.GT) == (0, 1)
    assert t3_comparison.allowed_offsets(t3_comparison.LT) == (1, 2)
    with pytest.raises(ValueError):
        t3_comparison.allowed_offsets("eq")


# --------------------------------------------------------------------------
# 決定性と preflight
# --------------------------------------------------------------------------


def test_same_config_builds_the_same_pool(fill_config: dict[str, Any]) -> None:
    """★同じ config なら、項目の並びまで同じプールになる。シードを変えれば変わる。"""
    first = eval_pool.build(fill_config)
    second = eval_pool.build(copy.deepcopy(fill_config))
    assert [item.item_id for item in first.items] == [item.item_id for item in second.items]
    assert first.manifest == second.manifest
    other = copy.deepcopy(fill_config)
    other["eval"]["pool_seed"] = TEST_POOL_SEED + 1
    assert eval_pool.build(other).manifest["pairs_hash"] != first.manifest["pairs_hash"]


def test_preflight_data_checks_pass_on_the_filled_pool(
    fill_config: dict[str, Any], tmp_path: Path
) -> None:
    """書き出した manifest で検査6(書式)・検査8(K の下限)が PASS になる。"""
    config = copy.deepcopy(fill_config)
    out_dir = tmp_path / "battery"
    eval_pool.write_pool(eval_pool.build(config), out_dir)
    config["eval"]["anchor_manifest"] = str(out_dir / "manifest.json")
    results = {result.name: result for result in preflight.data_checks(config)}
    assert results["format hash"].status is preflight.Status.PASS, results["format hash"].detail
    assert results["coverage_k floor"].status is preflight.Status.PASS, results[
        "coverage_k floor"
    ].detail


# --------------------------------------------------------------------------
# 本番 config(順6 の条件。ADR-076 決定11)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def main_pool() -> eval_pool.EvalPool:
    """本番 config から主プールを組む(約 10 秒。Q(999) の main 側は 40 万組ある)。"""
    return eval_pool.build(load_config(MAIN_CONFIG))


def test_main_pool_has_the_order6_shape(main_pool: eval_pool.EvalPool) -> None:
    """★主軸 42 セル + 指示付き T1 = 1,640 項目(自由生成 680 / 強制選択 960。ADR-076 決定8)。

    **組合せ論的な計数であって実験結果ではない**(`CLAUDE.md` §2)。
    """
    counts = Counter(item.group for item in main_pool.items)
    assert len(main_pool.items) == 1640
    assert counts == {
        "comparison": 960,
        "bare_sum": 240,
        "bare_sum_instructed": 80,
        "word_problem": 240,
        "specificity": 120,
    }
    cells = main_pool.manifest["fill"]["cells_declared"]
    assert len(cells) == 42
    assert sum(cell["n"] for cell in cells if cell["coverage"] == COVERAGE_ID) == 520
    assert main_pool.manifest["n_pairs"] == 1560


def test_main_pool_matches_the_committed_manifest(main_pool: eval_pool.EvalPool) -> None:
    """★コミット済みの主プールの manifest が、本番 config から再現できる。

    **順6 の GPU の条件は「プールの manifest のコミット」である**(ADR-076 決定11)。
    items.jsonl は git に無い(`.gitignore`)ので、ポッドは config から生成し直す。
    そのとき同じものが出ることを、ここで固定する。`files` は書き出したときにだけ付く。
    """
    committed = json.loads(MAIN_POOL_MANIFEST.read_text(encoding="utf-8"))
    committed.pop("files")
    # メモリ上の manifest は組をタプルで持つ。JSON を通して書き出した形に揃える。
    rebuilt = json.loads(json.dumps(main_pool.manifest, ensure_ascii=False))
    assert rebuilt == committed
