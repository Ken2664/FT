"""長形式表(code/analysis/frame.py)のテスト。PLAN-017 §8。

答える問い: 「組んだ表は、そのまま §3.2 のモデルに渡して取り違えないか。
主軸から落ちた行は数えられているか」

**モデルの重みは1度も読まない。**metrics.json / config.yaml / predictions を
手で組んで読ませる。**ここに出る数値は実験結果ではない。**

**★このファイルの中心は「extrap_pair が extrap_magnitude に混ざらないこと」
である**(PLAN-017 §8)。混入率がタスク型で違えば、それだけで主要検定の
task:coverage が有意になる。**ラベル入れ替え検定はこれを検出しない。**
被覆ラベル側の境界の固定は code/tests/test_pool.py にある。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from code.analysis import frame
from code.data_gen.pool import pairs_hash

# 本実験の訓練域の上限(data.train_domain_max)。ADR-027 決定1 の境界を
# そのまま踏むので、ここでは実験の値を使う。
MAIN_RADIUS = 99

# 訓練被覆 K。**小さくてよい** —— 照合の規則を試すのであって量ではない。
COVERAGE_PAIRS: list[tuple[int, int]] = [(1, 2), (3, 4)]


def write_ft_manifest(
    path: Path,
    *,
    condition: str,
    pairs: list[tuple[int, int]] | None = None,
    recorded_hash: str | None = None,
    domain_hi: int = MAIN_RADIUS,
) -> Path:
    """FT データの manifest(code/data_gen/ft_data.py が書く形)。"""
    coverage = pairs if pairs is not None else COVERAGE_PAIRS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "data_id": f"test_{condition}",
                "lesion": {"condition": condition},
                "train_domain": {"lo": 1, "hi": domain_hi, "n_pairs": domain_hi**2},
                "coverage": {
                    "pairs": [list(pair) for pair in coverage],
                    "pairs_hash": recorded_hash or pairs_hash(coverage),
                    "coverage_sums": sorted({a + b for a, b in coverage}),
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def prediction(
    *,
    item_id: str,
    category: str,
    operands: tuple[int, int],
    group: str = "bare_sum",
    classification: str = "rule",
) -> dict[str, Any]:
    """predictions/*.jsonl の1行(code/eval/run.py の prediction_record の形)。"""
    return {
        "item_id": item_id,
        "group": group,
        "category": category,
        "operands": list(operands),
        "carry": "nocarry",
        "params": {},
        "prompt": "",
        "response": "",
        "parsed": 5,
        "truth": 3,
        "rule_values": {"p2": 5},
        "reference_rule": "p2",
        "classification": classification,
    }


def write_run(
    root: Path,
    *,
    run_id: str,
    manifest_path: Path,
    condition: str = "p2",
    seed: int | None = 0,
    records: list[dict[str, Any]] | None = None,
    train_domain_max: int = MAIN_RADIUS,
) -> Path:
    """評価 run 1本分の成果物を組む。返すのは metrics.json のパス。"""
    run_dir = root / run_id
    (run_dir / "predictions").mkdir(parents=True, exist_ok=True)
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "lesion": {"condition": condition},
                "data": {
                    "train_domain_max": train_domain_max,
                    "matched_manifests": [str(manifest_path)],
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "kind": "battery_eval",
                "lesion_condition": condition,
                "seed": seed,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rows = records if records is not None else [
        prediction(item_id="i1", category="t1", operands=(1, 2))
    ]
    with (run_dir / "predictions" / "bare_sum.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return metrics_path


# --------------------------------------------------------------------------
# category の写像(E-3 / E-2)
# --------------------------------------------------------------------------


def test_task_mapping_calls_the_two_existing_functions() -> None:
    """主軸の4タスク型が category から引けること(ADR-062 決定3)。

    写像表を3つ目に作らない。既存の task_type_of 2本の結果と一致する。
    """
    assert frame.task_type_of("t1") == "t1"
    assert frame.task_type_of("t2_money") == "t2"
    assert frame.task_type_of("t3_gt") == "t3"
    assert frame.task_type_of("t1b_lt") == "t1b"
    assert frame.MAIN_TASK_TYPES == ("t1", "t2", "t3", "t1b")


def test_unknown_category_stops_the_frame() -> None:
    """★未知の category を素通ししない(PLAN-017 §8)。

    綴りを間違えた水準が1つ増えたまま交互作用を当ててしまう。
    """
    with pytest.raises(frame.FrameError):
        frame.task_type_of("t2_bananas")


def test_off_main_axis_categories_are_marked_not_dropped() -> None:
    """★特異性対照と指示付き T1 は「主軸外」の明示的な印を持つ(F72)。

    黙って落とすと、項目数が静かに減っていても気付けない。
    """
    assert frame.task_type_of("spec_sub") == frame.OFF_MAIN_AXIS
    assert frame.task_type_of("spec_mul") == frame.OFF_MAIN_AXIS
    assert not frame.is_main_task(frame.task_type_of("spec_sub"))
    # t1_instructed は「主軸外」だが自分の名前を保つ(ADR-035 決定2 の副次)。
    assert frame.task_type_of("t1_instructed") == "t1_instructed"
    assert not frame.is_main_task("t1_instructed")


def test_template_is_the_category_itself() -> None:
    """`category` をそのまま template の水準とする(ADR-062 決定2 = E-2 案 (a))。

    主軸は10水準である(Documents/05_STATISTICS.md §3.2)。
    """
    main_categories = [
        "t1",
        "t2_count",
        "t2_people",
        "t2_distance",
        "t2_money",
        "t2_time",
        "t3_gt",
        "t3_lt",
        "t1b_gt",
        "t1b_lt",
    ]
    assert [frame.template_of(category) for category in main_categories] == main_categories
    assert len({frame.template_of(category) for category in main_categories}) == 10


# --------------------------------------------------------------------------
# ★被覆の照合(この PLAN の本体)
# --------------------------------------------------------------------------


def test_extrap_pair_rows_are_not_on_the_main_axis(tmp_path: Path) -> None:
    """★この層で唯一の防波堤(PLAN-017 §8)。

    (300, 50) と (-100, 1) は extrap だが extrap_magnitude ではない。
    主軸に混ざると、混入率がタスク型で違うだけで task:coverage が有意になる。
    """
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(
        tmp_path / "runs",
        run_id="r1",
        manifest_path=manifest,
        records=[
            prediction(item_id="id1", category="t1", operands=(1, 2)),
            prediction(item_id="interp1", category="t1", operands=(5, 6)),
            prediction(item_id="mag1", category="t1", operands=(150, 150)),
            prediction(item_id="pair1", category="t1", operands=(300, 50)),
            prediction(item_id="pair2", category="t1", operands=(-100, 1)),
            prediction(item_id="oob1", category="t1", operands=(0, 3)),
        ],
    )
    built = frame.build_frame([metrics_path])
    coverage = {row["item"]: row["coverage"] for row in built.rows}
    assert coverage == {
        "id1": "id",
        "interp1": "interp",
        "mag1": "extrap_magnitude",
        "pair1": "extrap_pair",
        "pair2": "extrap_pair",
        "oob1": "oob_algebraic",
    }
    on_axis = {row["item"] for row in built.rows if row["main_axis"]}
    assert on_axis == {"id1", "interp1", "mag1"}


def test_rows_dropped_from_the_main_axis_are_counted(tmp_path: Path) -> None:
    """★主軸から落ちた行の件数が run ごとに残ること(ADR-062 決定1 の付帯条件)。

    黙って落とすと、項目数が静かに減っていても気付けない。
    """
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(
        tmp_path / "runs",
        run_id="r1",
        manifest_path=manifest,
        records=[
            prediction(item_id="id1", category="t1", operands=(1, 2)),
            prediction(item_id="oob1", category="t1", operands=(0, 3)),
            prediction(
                item_id="spec1", category="spec_sub", operands=(5, 6), group="specificity"
            ),
        ],
    )
    summary = frame.build_frame([metrics_path]).runs[0]
    assert summary.n_rows == 3
    assert summary.n_main_axis == 1
    assert summary.n_dropped == 2
    assert summary.n_dropped_by_reason[frame.DROP_COVERAGE] == 1
    assert summary.n_dropped_by_reason[frame.DROP_TASK] == 1
    assert summary.n_dropped_by_reason[frame.DROP_SEED] == 0
    assert summary.n_by_coverage == {"id": 1, "oob_algebraic": 1, "interp": 1}


def test_wrong_pairs_hash_stops_the_frame(tmp_path: Path) -> None:
    """★K を取り違えたまま数値を出さない(PLAN-017 §8 の1行目)。

    別条件の manifest を読んでも数値は普通に出てしまう。
    """
    manifest = write_ft_manifest(
        tmp_path / "ft" / "manifest.json", condition="p2", recorded_hash="deadbeef"
    )
    metrics_path = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    with pytest.raises(frame.FrameError, match="pairs_hash"):
        frame.build_frame([metrics_path])


def test_train_domain_mismatch_stops_the_frame(tmp_path: Path) -> None:
    """main_radius の出どころが2つに割れたら止める(PLAN-017 E-5)。"""
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2", domain_hi=50)
    metrics_path = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    with pytest.raises(frame.FrameError, match="train_domain"):
        frame.build_frame([metrics_path])


def test_training_run_metrics_are_refused(tmp_path: Path) -> None:
    """4値分解を持たない run を混ぜない(aggregate と同じ規約)。"""
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload["kind"] = "lora_train"
    metrics_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(frame.FrameError, match="kind"):
        frame.build_frame([metrics_path])


# --------------------------------------------------------------------------
# seed と項目集合(PLAN-017 §8)
# --------------------------------------------------------------------------


def test_missing_seed_never_reaches_the_main_axis(tmp_path: Path) -> None:
    """★アダプタ無しの run の seed は None である(F75)。0 を置かない。

    `(1 | seed)` が実質的な反復単位なので(ADR-006)、seed の無い行が
    主軸に混ざると反復単位が壊れる。
    """
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest, seed=None)
    built = frame.build_frame([metrics_path])
    assert built.rows[0]["seed"] is None
    assert built.rows[0]["main_axis"] is False
    assert built.runs[0].n_dropped_by_reason[frame.DROP_SEED] == 1


def test_item_sets_must_agree_across_runs(tmp_path: Path) -> None:
    """★run 間で項目集合が食い違ったら問題として残す(§3.2.1 の生きている制約)。

    条件間で項目集合が変わると (1 | item) が条件と交絡する(PLAN-001 §3)。
    """
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    first = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    second = write_run(
        tmp_path / "runs",
        run_id="r2",
        manifest_path=manifest,
        records=[prediction(item_id="i2", category="t1", operands=(1, 2))],
    )
    built = frame.build_frame([first, second])
    assert built.problems
    assert "項目集合" in built.problems[0]
    with pytest.raises(frame.FrameError):
        frame.write_frame(built, tmp_path / "out")


def test_item_sets_that_agree_leave_no_problem(tmp_path: Path) -> None:
    """同じ項目集合なら問題は出ない。"""
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    first = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    second = write_run(tmp_path / "runs", run_id="r2", manifest_path=manifest, seed=1)
    assert frame.build_frame([first, second]).problems == []


# --------------------------------------------------------------------------
# 解析門の生の量(E-6)と出力(E-7)
# --------------------------------------------------------------------------


def test_gate_column_is_raw_and_not_binarized(tmp_path: Path) -> None:
    """★門は生の量として残す。二値化しない(ADR-062 決定6 = E-6 案 (c))。

    閾値(N5)と S1(何で測るか)が未決なので、ここで True / False を
    置くと決まっていない門を通ったことになる。
    """
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(
        tmp_path / "runs",
        run_id="r1",
        manifest_path=manifest,
        records=[
            prediction(item_id="id1", category="t1", operands=(1, 2), classification="rule"),
            prediction(item_id="id2", category="t1", operands=(3, 4), classification="correct"),
            prediction(item_id="id3", category="t3_gt", operands=(1, 2), classification="rule"),
        ],
    )
    built = frame.build_frame([metrics_path])
    summary = built.runs[0]
    assert summary.gate_id_n == 3
    assert summary.gate_id_rule_rate == pytest.approx(2 / 3)
    # S1 が未決なので、タスク型ごとの内訳も残す(#4 / #4b は T1 だけを見る)。
    assert summary.gate_id_by_task["t1"] == {"n": 2, "rule_rate": pytest.approx(0.5)}
    assert summary.gate_id_by_task["t3"] == {"n": 1, "rule_rate": pytest.approx(1.0)}
    assert "passes_analysis_gate" not in frame.COLUMNS
    assert all(row["gate_id_rule_rate"] == pytest.approx(2 / 3) for row in built.rows)


def test_is_rule_comes_from_the_classification(tmp_path: Path) -> None:
    """is_rule は classification == "rule" で作る(F73)。数え直さない。"""
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(
        tmp_path / "runs",
        run_id="r1",
        manifest_path=manifest,
        records=[
            prediction(item_id="a", category="t1", operands=(1, 2), classification="rule"),
            prediction(item_id="b", category="t1", operands=(3, 4), classification="correct"),
            prediction(item_id="c", category="t1", operands=(5, 6), classification="parse_fail"),
        ],
    )
    built = frame.build_frame([metrics_path])
    assert [row["is_rule"] for row in built.rows] == [1, 0, 0]


def test_written_frame_carries_its_own_record(tmp_path: Path) -> None:
    """★CSV + ハッシュ + run_id 一覧 + pairs_hash を残す(ADR-062 決定7)。

    predictions/ は git に無い(F79)ので、この記録が主要検定の入力の正本になる。
    """
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    built = frame.build_frame([metrics_path])
    csv_path, manifest_out = frame.write_frame(built, tmp_path / "out")
    payload = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert payload["run_ids"] == ["r1"]
    assert payload["pairs_hashes"] == [pairs_hash(COVERAGE_PAIRS)]
    assert payload["columns"] == list(frame.COLUMNS)
    assert payload["n_rows"] == 1
    assert payload["csv_sha256"]
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == list(frame.COLUMNS)


def test_dry_run_prints_counts_and_writes_nothing(tmp_path: Path, capsys: Any) -> None:
    """--dry-run は件数だけを出す(PLAN-017 §6-1、§9)。"""
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    out_dir = tmp_path / "out"
    code = frame.main(
        [
            "--runs",
            str(tmp_path / "runs" / "r1"),
            "--dry-run",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert code == 0
    assert not out_dir.exists()
    printed = capsys.readouterr().out
    assert "run 1 件" in printed
    assert "r1" in printed


def test_empty_predictions_stop_the_frame(tmp_path: Path) -> None:
    """0件の表を「差が無かった」と読ませない。"""
    manifest = write_ft_manifest(tmp_path / "ft" / "manifest.json", condition="p2")
    metrics_path = write_run(tmp_path / "runs", run_id="r1", manifest_path=manifest)
    (metrics_path.parent / "predictions" / "bare_sum.jsonl").unlink()
    with pytest.raises(frame.FrameError, match="1件も無い"):
        frame.build_frame([metrics_path])
