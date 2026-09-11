"""順6 の変種 config(R4 = batch 1 / R5 = タスク6 の交差)と交差プール。PLAN-023 手順6・7。

答える問い: 「R4 / R5 の config は、本番 config と決められた欄だけが違うか。
R5 が解く交差プールは、主プールの T2 の組を残り 4 場面で尋ねたものか」

ここで固定する最重要の性質:
  - **R4 の config は `eval.batch_size` と `experiment.id` だけが違う**(ADR-076 決定7)。
    ほかの欄がずれると、R1 との差がバッチの浮動小数ノイズだけではなくなる
  - **R5 の config は `experiment.id` / `eval.anchor_manifest` / `eval.batteries` だけが違う**
  - **交差プールは主プールの T2 の組 × 残り 4 場面 = 960 項目**(ADR-076 決定6)。
    主プールと合わせると、どの組も 5 場面すべてで尋ねられる。主プールの項目集合は変えない
  - **コミット済みの交差プールの manifest が本番 config から再現できる**

**本番 config を直したら、変種の config にも同じ変更を入れること。**入れ忘れるとここが落ちる。
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from code.config import load_config
from code.data_gen import eval_pool
from code.data_gen.pool import ANSWER_OUT
from code.eval import run
from code.eval.battery import numeric_sum

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main.yaml"
B1_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main_b1.yaml"
T2_CROSS_CONFIG = REPO_ROOT / "configs" / "exp_phase1_main_t2cross.yaml"
T2_CROSS_MANIFEST = (
    REPO_ROOT / "data" / "generated" / "battery" / "main_t2_cross" / "manifest.json"
)

# 交差プールの大きさ(ADR-076 決定6)。**組合せ論的な計数であって実験結果ではない。**
N_T2_PAIRS = 240
N_OTHER_SCENES = len(numeric_sum.T2_CATEGORIES) - 1


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """入れ子の config を `a.b.c` の鍵の辞書にする(リストは値としてそのまま比べる)。"""
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


# --------------------------------------------------------------------------
# 変種 config(ADR-076 決定6・7)
# --------------------------------------------------------------------------


def test_batch1_config_differs_only_in_batch_size_and_experiment_id() -> None:
    """★R4 の config は本番と `eval.batch_size` / `experiment.id` だけが違う(ADR-076 決定7)。"""
    main, b1 = load_config(MAIN_CONFIG), load_config(B1_CONFIG)
    assert differing_keys(main, b1) == {"eval.batch_size", "experiment.id"}
    assert main["eval"]["batch_size"] == 4
    assert b1["eval"]["batch_size"] == 1


def test_t2_cross_config_differs_only_in_the_three_declared_keys() -> None:
    """★R5 の config は本番と `experiment.id` / `eval.anchor_manifest` / `eval.batteries` だけが違う。"""
    main, cross = load_config(MAIN_CONFIG), load_config(T2_CROSS_CONFIG)
    assert differing_keys(main, cross) == {
        "experiment.id",
        "eval.anchor_manifest",
        "eval.batteries",
    }
    assert cross["eval"]["batteries"] == [numeric_sum.GROUP_WORD_PROBLEM]


def test_variant_configs_have_distinct_experiment_ids() -> None:
    """run ディレクトリ名と experiment_id が本番と混ざらない(PLAN-023 A12)。"""
    ids = {load_config(path)["experiment"]["id"] for path in (MAIN_CONFIG, B1_CONFIG, T2_CROSS_CONFIG)}
    assert len(ids) == 3


# --------------------------------------------------------------------------
# 交差プール(ADR-076 決定6)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pools() -> dict[str, eval_pool.EvalPool]:
    """本番 config から主プールと交差プールを組む(約 10 秒)。"""
    config = load_config(MAIN_CONFIG)
    main_pool = eval_pool.build(config)
    return {"main": main_pool, "cross": eval_pool.build_t2_cross(config, main_pool)}


def test_cross_pool_is_the_t2_pairs_times_the_other_scenes(
    pools: dict[str, eval_pool.EvalPool],
) -> None:
    """★240 組 × 残り 4 場面 = 960。主プールと合わせると、どの組も 5 場面で尋ねられる。"""
    main_t2 = [item for item in pools["main"].items if item.group == numeric_sum.GROUP_WORD_PROBLEM]
    cross = pools["cross"].items
    assert len(main_t2) == N_T2_PAIRS
    assert len(cross) == N_T2_PAIRS * N_OTHER_SCENES
    scenes: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for item in [*main_t2, *cross]:
        scenes[item.operands].append(item.category)
    assert all(sorted(found) == sorted(numeric_sum.T2_CATEGORIES) for found in scenes.values())
    assert pools["cross"].manifest["fill"]["method"] == eval_pool.FILL_T2_CROSS
    assert pools["cross"].manifest["fill"]["source_pool_pairs_hash"] == (
        pools["main"].manifest["pairs_hash"]
    )


def test_cross_pool_does_not_touch_the_main_pool(pools: dict[str, eval_pool.EvalPool]) -> None:
    """交差の項目は主プールの項目と item_id が重ならない(主プールの項目集合を変えない)。"""
    main_ids = {item.item_id for item in pools["main"].items}
    assert not (main_ids & {item.item_id for item in pools["cross"].items})


def test_cross_pool_matches_the_committed_manifest(pools: dict[str, eval_pool.EvalPool]) -> None:
    """★コミット済みの交差プールの manifest が本番 config から再現できる。"""
    committed = json.loads(T2_CROSS_MANIFEST.read_text(encoding="utf-8"))
    committed.pop("files")
    rebuilt = json.loads(json.dumps(pools["cross"].manifest, ensure_ascii=False))
    assert rebuilt == committed


def test_t2_cross_config_dry_runs_on_the_cross_pool(
    pools: dict[str, eval_pool.EvalPool], tmp_path: Path
) -> None:
    """R5 の config で、交差プールの dry-run が通る(ans_in / ans_out の 2 バッチ)。"""
    config = load_config(T2_CROSS_CONFIG)
    out_dir = tmp_path / "main_t2_cross"
    eval_pool.write_pool(pools["cross"], out_dir)
    config["eval"]["anchor_manifest"] = str(out_dir / "manifest.json")
    report = run.dry_run(config)
    assert report["n_items"] == N_T2_PAIRS * N_OTHER_SCENES
    assert set(report["by_batch"]) == {"word_problem", f"word_problem.{ANSWER_OUT}"}


def test_scene_builder_refuses_an_unknown_scene() -> None:
    with pytest.raises(ValueError, match="未知の場面"):
        numeric_sum.build_word_problem_items_in_scene(
            [(3, 4)], scene="t2_weather", pool_id="main", reference_lesions={}
        )
