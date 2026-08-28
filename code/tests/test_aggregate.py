"""集約(code/analysis/aggregate.py)のテスト。

答える問い: 「集めた表は、そのまま読んで取り違えないか。
4値分解でないものが条件のセルとして並んでいないか」

**モデルの重みは1度も読まない。**metrics.json を手で組んで読ませる。
**ここに出る数値は実験結果ではない。**

metrics.json の形は `code/eval/run.py` の `metrics_payload` /
`code/eval/sweep.py` / `code/train/run.py` が書くものに合わせてある。
形が離れたら、このテストではなく**実装が**先に落ちるべきなので、
`by_batch` の鍵は実装と同じ名前を使っている。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.analysis import aggregate
from code.config import load_config
from code.data_gen import eval_pool
from code.eval import run as eval_run
from code.eval import sweep as eval_sweep
from code.train import run as train_run

# 4値。**合計は必ず 1.0**(CLAUDE.md §6)。
RATES = {
    "correct_rate": 0.5,
    "rule_rate": 0.25,
    "other_error_rate": 0.25,
    "parse_fail_rate": 0.0,
    "n_items": 4,
}


def eval_metrics(
    *,
    run_id: str,
    condition: str = "p2",
    seed: int | None = None,
    adapter: str | None = None,
    rates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "kind": eval_run.EVAL_KIND,
        "experiment_id": "smoke",
        "lesion_condition": condition,
        "adapter": adapter,
        "by_batch": {
            "bare_sum": {
                "group": "bare_sum",
                "primary_reference_rule": "p2",
                "n_items": 4,
                "by_reference_rule": {"p2": dict(rates or RATES)},
            }
        },
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


def write_run(root: Path, name: str, payload: dict[str, Any]) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return run_dir


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    """4値を持つ run 1件・掃引1件・訓練1件。"""
    write_run(tmp_path, "20260901_000001_smoke", eval_metrics(run_id="20260901_000001_smoke"))
    write_run(
        tmp_path,
        "20260901_000002_sweep",
        {"run_id": "20260901_000002_sweep", "kind": eval_sweep.SWEEP_KIND, "by_radius": []},
    )
    write_run(
        tmp_path,
        "20260901_000003_train",
        {"run_id": "20260901_000003_train", "kind": train_run.TRAIN_KIND, "seed": 0},
    )
    return tmp_path


def collect_from(root: Path) -> aggregate.Collection:
    return aggregate.collect(aggregate.expand_metrics_paths([str(root / "*")]))


# --------------------------------------------------------------------------
# 何を読み、何を落とすか
# --------------------------------------------------------------------------


def test_only_the_evaluation_kind_enters_the_table(runs: Path) -> None:
    """★掃引の点と訓練の損失を条件のセルとして並べないこと。"""
    collection = collect_from(runs)
    assert collection.n_metrics_files == 3
    assert len(collection.cells) == 1
    assert collection.skipped_kinds == {
        eval_sweep.SWEEP_KIND: 1,
        train_run.TRAIN_KIND: 1,
    }


def test_no_matching_run_stops_the_aggregation(tmp_path: Path) -> None:
    """★0件の集計を黙って空表にしないこと。

    「差が無かった」と「そもそも読んでいない」は別である。
    """
    with pytest.raises(aggregate.AggregateError, match="1件も無い"):
        aggregate.expand_metrics_paths([str(tmp_path / "does_not_exist*")])


def test_a_metrics_file_can_be_named_directly(runs: Path) -> None:
    paths = aggregate.expand_metrics_paths([str(runs / "*" / "metrics.json")])
    assert len(paths) == 3


def test_a_broken_four_value_block_stops_the_aggregation(tmp_path: Path) -> None:
    """★合計が 1.0 にならない記録を読み流さないこと(CLAUDE.md §6)。"""
    broken = dict(RATES)
    broken["correct_rate"] = 0.9
    write_run(tmp_path, "run_broken", eval_metrics(run_id="run_broken", rates=broken))
    with pytest.raises(ValueError, match="4値の合計"):
        collect_from(tmp_path)


def test_a_missing_rate_field_stops_the_aggregation(tmp_path: Path) -> None:
    """★4値のうち一部だけの記録を通さないこと。"""
    partial = dict(RATES)
    del partial["parse_fail_rate"]
    write_run(tmp_path, "run_partial", eval_metrics(run_id="run_partial", rates=partial))
    with pytest.raises(aggregate.AggregateError, match="parse_fail_rate"):
        collect_from(tmp_path)


# --------------------------------------------------------------------------
# 条件×シードの並べ方
# --------------------------------------------------------------------------


def test_rows_are_grouped_by_condition_and_listed_by_seed(tmp_path: Path) -> None:
    """★同じ条件の別シードが1行に並び、別条件は別の行になること。"""
    for seed in (0, 1):
        write_run(
            tmp_path, f"run_p2_{seed}", eval_metrics(run_id=f"run_p2_{seed}", seed=seed)
        )
    write_run(
        tmp_path, "run_x2_0", eval_metrics(run_id="run_x2_0", condition="x2", seed=0)
    )
    collection = collect_from(tmp_path)
    by_condition = {cell.condition: cell for cell in collection.cells}
    assert set(by_condition) == {"p2", "x2"}
    assert by_condition["p2"].seeds == (0, 1)
    assert by_condition["p2"].n_seeds == 2
    assert by_condition["x2"].n_seeds == 1


def test_a_rerun_of_the_same_seed_is_not_counted_twice(tmp_path: Path) -> None:
    """★同じシードの再実行を2シードと数えないこと(CLAUDE.md §2)。

    数えてしまうと、5シードの要件が再実行だけで満たせる。
    """
    for name in ("run_a", "run_b"):
        write_run(tmp_path, name, eval_metrics(run_id=name, seed=0))
    (cell,) = collect_from(tmp_path).cells
    assert len(cell.rows) == 2
    assert cell.n_seeds == 1
    assert cell.has_duplicate_seeds is True


def test_the_mean_is_over_runs_and_keeps_all_four_values(tmp_path: Path) -> None:
    """★平均も4値そろって出ること(skill code-style §4)。"""
    other = {
        "correct_rate": 1.0,
        "rule_rate": 0.0,
        "other_error_rate": 0.0,
        "parse_fail_rate": 0.0,
        "n_items": 4,
    }
    write_run(tmp_path, "run_0", eval_metrics(run_id="run_0", seed=0))
    write_run(tmp_path, "run_1", eval_metrics(run_id="run_1", seed=1, rates=other))
    (cell,) = collect_from(tmp_path).cells
    mean = cell.mean_rates()
    assert set(mean) == {"correct_rate", "rule_rate", "other_error_rate", "parse_fail_rate"}
    assert mean["correct_rate"] == pytest.approx(0.75)
    assert sum(mean.values()) == pytest.approx(1.0)
    assert cell.as_dict()["n_items_total"] == 8


def test_five_seeds_are_required_before_a_cell_is_claimable(tmp_path: Path) -> None:
    """★シードが 5 未満のセルに印が付くこと(CLAUDE.md §2)。"""
    for seed in range(aggregate.MIN_SEEDS_FOR_CLAIM - 1):
        write_run(tmp_path, f"run_{seed}", eval_metrics(run_id=f"run_{seed}", seed=seed))
    (cell,) = collect_from(tmp_path).cells
    assert cell.enough_seeds is False

    write_run(tmp_path, "run_last", eval_metrics(run_id="run_last", seed=4))
    (full,) = collect_from(tmp_path).cells
    assert full.n_seeds == aggregate.MIN_SEEDS_FOR_CLAIM
    assert full.enough_seeds is True


# --------------------------------------------------------------------------
# 表だけを見た人が取り違える点
# --------------------------------------------------------------------------


def test_a_run_without_an_adapter_is_flagged(runs: Path) -> None:
    """★adapter=null の数値を「病変後のモデル」と読ませないこと。

    評価ハーネスはアダプタを読まない(code/eval/run.py の NO_ADAPTER_NOTE)。
    """
    warnings = aggregate.warnings_for(collect_from(runs))
    assert any("adapter=null" in line for line in warnings)


def test_a_run_without_a_seed_is_flagged(runs: Path) -> None:
    """★シードが記録されていないことを、表の欄が空なだけで済ませないこと。"""
    warnings = aggregate.warnings_for(collect_from(runs))
    assert any("seed が記録されていない" in line for line in warnings)


def test_a_short_seed_count_is_flagged(runs: Path) -> None:
    warnings = aggregate.warnings_for(collect_from(runs))
    assert any(str(aggregate.MIN_SEEDS_FOR_CLAIM) in line for line in warnings)


def test_a_full_and_adapter_backed_table_has_no_warnings(tmp_path: Path) -> None:
    """★満たすべきものを満たした表には警告が出ないこと(警告が形式的でない)。"""
    for seed in range(aggregate.MIN_SEEDS_FOR_CLAIM):
        write_run(
            tmp_path,
            f"run_{seed}",
            eval_metrics(run_id=f"run_{seed}", seed=seed, adapter=f"runs/run_{seed}/adapter"),
        )
    assert aggregate.warnings_for(collect_from(tmp_path)) == []


def test_the_report_shows_four_values_and_the_seed_column(runs: Path) -> None:
    """★4値は常に4つ並ぶこと。シード不明は空欄でなく印で出ること。"""
    lines = aggregate.report_lines(collect_from(runs))
    header = next(line for line in lines if "parse_fail" in line and "correct" in line)
    for field in ("correct", "rule", "other_err", "parse_fail"):
        assert field in header
    assert any(aggregate.UNKNOWN_SEED in line for line in lines)
    assert any("表に入れなかった種別" in line for line in lines)


def test_the_json_output_is_written_only_when_asked(runs: Path, tmp_path: Path) -> None:
    """★results/ に勝手に書かないこと。--out を渡したときだけ書く。"""
    out = tmp_path / "out" / "aggregate.json"
    assert aggregate.main(["--runs", str(runs / "*")]) == 0
    assert not out.exists()

    assert aggregate.main(["--runs", str(runs / "*"), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["n_cells"] == 1
    assert payload["min_seeds_for_claim"] == aggregate.MIN_SEEDS_FOR_CLAIM
    assert payload["skipped_kinds"] == {
        eval_sweep.SWEEP_KIND: 1,
        train_run.TRAIN_KIND: 1,
    }


# --------------------------------------------------------------------------
# 実装が書いた metrics.json をそのまま読めるか
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# **実験条件ではない。**smoke config は model.name / revision を null に
# してあるので、本実行の経路まで到達させるためにテスト側で埋める。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
# smoke config は device / batch_size を持たない(あちらは編集してはならない。
# ADR-037 決定4)。cpu と 1 を置くのは**重みを読まないから**であって、
# 実験条件の宣言ではない —— この経路は固定応答の生成器で回る
TEST_DEVICE = "cpu"
TEST_BATCH_SIZE = 1


def test_it_reads_a_metrics_file_written_by_the_evaluation_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★手で組んだ形ではなく、code/eval/run.py が実際に書いた形を読めること。

    集約側だけが metrics.json の形を思い込んでいると、実装が変わった日に
    表が静かに空になる。**重みは読まない** —— 固定応答の生成器を渡す。
    """
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")
    config = load_config(SMOKE_CONFIG)
    pool_dir = tmp_path / "battery"
    eval_pool.write_pool(eval_pool.build(config), pool_dir)
    config["model"]["name"] = TEST_MODEL
    config["model"]["revision"] = TEST_REVISION
    config["model"]["device"] = TEST_DEVICE
    config["eval"]["batch_size"] = TEST_BATCH_SIZE
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    def constant(prompts: Sequence[str]) -> list[str]:
        return ["Answer: 0." for _ in prompts]

    run_dir = eval_run.execute(
        config,
        config_path=config_path,
        run_dir=tmp_path / "run",
        generator=constant,
    )
    collection = aggregate.collect(aggregate.expand_metrics_paths([str(run_dir)]))
    assert collection.n_metrics_files == 1
    assert collection.cells
    assert all(cell.condition == config["lesion"]["condition"] for cell in collection.cells)
    # 4値は RateBreakdown を通っている(合計 1.0 が成立している)。
    assert all(
        sum(cell.mean_rates().values()) == pytest.approx(1.0) for cell in collection.cells
    )
