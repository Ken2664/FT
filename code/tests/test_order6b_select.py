"""PLAN-026 §5 の判定表(I11c。§4.13 / ADR-087)。

答える問い: 「7 本の腕から §5 の (i)〜(iv) を当てたとき、採る候補は表の順で最も小さいものになるか。
腕が欠けた・取り違えた・閾値が食い違ったときに止まるか」

**ここに出る数値は実験結果ではない。**すべて合成の応答(決定的な採点器)か組合せ論的な件数である。
**モデルの重みは 1 度も読まない。**

ここで固定する最重要の性質:
  - **腕の形は記録で照合する**(`kind`・文面の組・前置きの sha256・絞り・掃引の腕・`pool_id`・`adapter`)。
    **名前(`experiment_id`・ディレクトリ名)からは推測しない**(ADR-085 決定3)
  - **7 本すべてが要る**(ADR-087 決定1)。1 本でも欠けたら何も出さずに止まる
  - **「そのタスク型に候補が無い」(T3 の C2)と「満たさなかった」は別の欄**(§4.13 読み7)
  - **候補が 1 つも無いタスク型は `selected = null` + `no_candidate`、`preamble_mismatch` は null**(ADR-086 決定4)
  - **記述の腕(①+(c) / (d)+(c))には (i)〜(iv) の合否の印を付けない**(ADR-087 決定3)
  - 印は `gonogo.py` / `r8_fit.py` が付けたものをそのまま読む。**ここで数え直さない**
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from code import artifacts
from code.analysis import calibrated, gonogo, order6b_select, r8_fit
from code.analysis.aggregate import METRICS_FILENAME
from code.config import REPO_ROOT, load_config
from code.data_gen import eval_pool, sweep_pool
from code.data_gen.pool import MAIN_COVERAGE_LEVELS, POOL_PILOT
from code.eval.battery import numeric_sum, t3_comparison
from code.eval.calibration import CALIBRATION_KIND, CalibrationArm
from code.tests.test_calibrated import ARM_B0, ARM_D, ARM_PREAMBLE, execute_calibration
from code.tests.test_calibrated import truthful_sweep_scorer
from code.tests.test_gonogo import execute_arm
from code.tests.test_threshold_sweep_run import PILOT_CONFIG, stub_capture, write_config

from code.eval import run  # isort: skip  (execute_threshold_sweep を呼ぶ)

# 腕 -> (config の名前, 掃引プールの腕)。掃引でない腕は None。
SWEEP_POOL_OF_ARM: dict[str, str] = {"r8": "r8", "s_preamble": "s", "s_d": "s"}
FIXED_ARMS: tuple[str, ...] = ("b0", "preamble", "d")
# 腕 -> configs/exp_order6b_<名前>.yaml(B0 の config は pilot という名前である)。
CONFIG_NAME_OF_ARM: dict[str, str] = {
    "b0": "pilot",
    "r8": "r8",
    "preamble": "preamble",
    "s_preamble": "s_preamble",
    "d": "d",
    "s_d": "s_d",
    "c": "c",
}


CONFIG_DIR = REPO_ROOT / "configs"


def config_path_of(arm: str) -> Path:
    return CONFIG_DIR / f"exp_order6b_{CONFIG_NAME_OF_ARM[arm]}.yaml"


# --------------------------------------------------------------------------
# 腕の形の定数が config の転記であること(§4.13 読み2)
# --------------------------------------------------------------------------


def test_the_arm_shapes_are_a_transcript_of_the_configs() -> None:
    """★腕の形は `configs/exp_order6b_*.yaml` の転記である(**両方向で落ちる**)。"""
    assert [spec.name for spec in order6b_select.ARM_SPECS] == list(CONFIG_NAME_OF_ARM)
    for spec in order6b_select.ARM_SPECS:
        config = load_config(config_path_of(spec.name))
        evaluation = config["eval"]
        assert config["data"]["eval_template_set"] == spec.template_set, spec.name
        assert (evaluation.get("preamble") is not None) == spec.preamble, spec.name
        subset = evaluation.get("task_subset")
        assert (None if subset is None else tuple(subset)) == spec.task_subset, spec.name
        assert evaluation.get("threshold_sweep_arm") == spec.sweep_arm, spec.name
        # (c) はプールを読まないので、config の pool_id は pilot でも記録には残らない
        assert config["data"]["pool_id"] == POOL_PILOT, spec.name
        assert spec.pool_id == (None if spec.kind == CALIBRATION_KIND else POOL_PILOT), spec.name


def test_the_calibration_arms_are_a_transcript_of_the_c_config() -> None:
    """★(c) の 3 腕(名前・文面の組・前置き)も config の転記である。"""
    arms = load_config(config_path_of("c"))["eval"]["calibration"]["arms"]
    declared = {arm["name"]: (arm["template_set"], bool(arm["preamble"])) for arm in arms}
    assert declared == order6b_select.CALIBRATION_ARMS


def test_the_candidate_set_and_its_order_are_the_table_in_section_5() -> None:
    """★候補の集合と順序は §5 の表(C0 < C3 < C2 < C1)。T3 は (d) を持たない。"""
    assert [spec.name for spec in order6b_select.CANDIDATES] == ["C0", "C3", "C2", "C1"]
    by_name = {spec.name: spec for spec in order6b_select.CANDIDATES}
    assert by_name["C2"].task_types == (t3_comparison.T1B,)
    for name in ("C0", "C3", "C1"):
        assert by_name[name].task_types == (t3_comparison.T3, t3_comparison.T1B)
    assert [spec.numeric_gate for spec in order6b_select.CANDIDATES] == [False, False, False, True]
    assert [spec.calibration_arm for spec in order6b_select.CANDIDATES] == [
        None,
        ARM_B0,
        None,
        None,
    ]
    assert [spec.name for spec in order6b_select.DESCRIPTIVE] == ["①+(c)", "(d)+(c)"]
    assert [spec.calibration_arm for spec in order6b_select.DESCRIPTIVE] == [ARM_PREAMBLE, ARM_D]


# --------------------------------------------------------------------------
# 本実行(モデルの重みは読まない)
# --------------------------------------------------------------------------


def execute_sweep_arm(arm: str, pool_dir: Path, tmp: Path) -> Path:
    """掃引の腕 1 本を、真値どおりに答える採点器で本実行する。"""
    config = load_config(config_path_of(arm))
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    tmp.mkdir(parents=True)
    config_path = write_config(config, tmp / "config.yaml")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", stub_capture)
        return run.execute_threshold_sweep(
            config,
            config_path=config_path,
            run_dir=tmp / "run",
            scorer=truthful_sweep_scorer(config),
        )


@pytest.fixture(scope="module")
def order6b(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """7 本の腕(B0・R8・①・S-①・(d)・S-(d)・(c))を固定応答で 1 度ずつ回す。"""
    root = tmp_path_factory.mktemp("select")
    pilot = load_config(PILOT_CONFIG)
    source = eval_pool.build(pilot)
    pool_dir = root / "pilot_pool"
    eval_pool.write_pool(source, pool_dir)
    sweep_dirs: dict[str, Path] = {}
    for sweep_arm in ("r8", "s"):
        directory = root / f"pool_{sweep_arm}"
        eval_pool.write_pool(sweep_pool.build_sweep_pool(pilot, source, sweep_arm), directory)
        sweep_dirs[sweep_arm] = directory
    runs = {
        arm: execute_arm(CONFIG_NAME_OF_ARM[arm], pool_dir, root / arm) for arm in FIXED_ARMS
    }
    for arm, sweep_arm in SWEEP_POOL_OF_ARM.items():
        runs[arm] = execute_sweep_arm(arm, sweep_dirs[sweep_arm], root / arm)
    runs["c"] = execute_calibration(root / "c")
    return runs


def all_keys(tree: Any) -> set[str]:
    """入れ子の辞書・リストのすべての鍵(**注記の本文に出る語と取り違えないため**)。"""
    if isinstance(tree, Mapping):
        return set(tree) | {key for value in tree.values() for key in all_keys(value)}
    if isinstance(tree, list):
        return {key for value in tree for key in all_keys(value)}
    return set()


def patterns_of(order6b: Mapping[str, Path], **overrides: str | None) -> dict[str, str | None]:
    """腕 -> glob(引数で 1 本だけ差し替える / None にする)。"""
    return {**{arm: str(path) for arm, path in order6b.items()}, **overrides}


@pytest.fixture(scope="module")
def report(order6b: dict[str, Path]) -> dict[str, Any]:
    return order6b_select.build_report(patterns_of(order6b))


# --------------------------------------------------------------------------
# 腕の照合(ADR-085 決定3)
# --------------------------------------------------------------------------


def test_the_provenance_names_every_arm_by_its_record(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★来歴は 7 本すべてを、記録の形(種別・文面の組・前置き・絞り・プール・重み)で並べる。"""
    by_arm = {arm["arm"]: arm for arm in report["arms"]}
    assert list(by_arm) == [spec.name for spec in order6b_select.ARM_SPECS]
    for spec in order6b_select.ARM_SPECS:
        entry = by_arm[spec.name]
        metrics = json.loads((order6b[spec.name] / METRICS_FILENAME).read_text(encoding="utf-8"))
        assert entry["run_id"] == metrics["run_id"]
        assert entry["kind"] == spec.kind
        assert entry["template_set"] == spec.template_set
        assert (entry["preamble_sha256"] is not None) == spec.preamble
        assert entry["task_subset"] == (None if spec.task_subset is None else list(spec.task_subset))
        assert entry["pool_id"] == spec.pool_id
        assert entry["adapter"] is None
    # 前置きを持つ 3 本(①・S-①・(c))の sha256 は 1 つに揃う
    shas = {by_arm[name]["preamble_sha256"] for name in ("preamble", "s_preamble", "c")}
    assert len(shas) == 1 and None not in shas


def shape_metrics(spec: order6b_select.ArmSpec) -> dict[str, Any]:
    """この腕の形にちょうど合う `metrics.json`(**合成。本実行を通さない**)。"""
    metrics: dict[str, Any] = {"kind": spec.kind, "run_id": "run", "adapter": None}
    if spec.preamble:
        metrics["preamble"] = {"lines": ["a"], "sha256": "0" * 64}
    if spec.task_subset is not None:
        metrics["task_subset"] = {"task_types": list(spec.task_subset)}
    if spec.sweep_arm is not None:
        metrics["threshold_sweep"] = {"arm": spec.sweep_arm}
    if spec.pool_id is not None:
        metrics["pool"] = {"pool_id": spec.pool_id}
    return metrics


def shape_config(spec: order6b_select.ArmSpec) -> dict[str, Any]:
    return {"data": {"eval_template_set": spec.template_set}}


@pytest.mark.parametrize("spec", order6b_select.ARM_SPECS, ids=lambda spec: spec.name)
def test_the_exact_shape_of_each_arm_passes(spec: order6b_select.ArmSpec) -> None:
    """★形がちょうど合っていれば通る(下の 7 つの検査が「常に止まる」ではないことの確認)。"""
    order6b_select._check_shape(spec, shape_metrics(spec), shape_config(spec))


def broken_kind(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    metrics["kind"] = "some_other_kind"


def broken_template_set(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    config["data"]["eval_template_set"] = "some_other_set"


def broken_preamble(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    if "preamble" in metrics:
        del metrics["preamble"]
    else:
        metrics["preamble"] = {"lines": ["a"], "sha256": "1" * 64}


def broken_task_subset(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    if "task_subset" in metrics:
        metrics["task_subset"] = {"task_types": ["t2"]}
    else:
        metrics["task_subset"] = {"task_types": ["t1b"]}


def broken_sweep_arm(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    if "threshold_sweep" in metrics:
        metrics["threshold_sweep"] = {"arm": "some_other_arm"}
    else:
        metrics["threshold_sweep"] = {"arm": "s"}


def broken_pool_id(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    if "pool" in metrics:
        metrics["pool"] = {"pool_id": "main"}
    else:
        metrics["pool"] = {"pool_id": "pilot"}


def broken_adapter(metrics: dict[str, Any], config: dict[str, Any]) -> None:
    metrics["adapter"] = "runs/20260901_000000_train/adapter"


# 壊す欄 -> (壊し方, 止まる文言)。**7 つの検査を 1 つずつ固定する** ——
# 腕を丸ごと取り違えたときは複数の検査が同時に効くので、1 つ外しても他が止めてしまう。
SHAPE_CHECKS = [
    ("kind", broken_kind, "kind が"),
    ("template_set", broken_template_set, "文面の組が"),
    ("preamble", broken_preamble, "前置き"),
    ("task_subset", broken_task_subset, "絞りが"),
    ("sweep_arm", broken_sweep_arm, "掃引の腕が"),
    ("pool_id", broken_pool_id, "pool_id が"),
    ("adapter", broken_adapter, "adapter が"),
]


@pytest.mark.parametrize(("field", "break_it", "message"), SHAPE_CHECKS)
@pytest.mark.parametrize("spec", order6b_select.ARM_SPECS, ids=lambda spec: spec.name)
def test_each_field_of_the_shape_is_checked_on_its_own(
    spec: order6b_select.ArmSpec, field: str, break_it: Any, message: str
) -> None:
    """★7 つの欄それぞれを、それ 1 つだけ壊して止まることを確かめる(ADR-085 決定3)。"""
    metrics, config = shape_metrics(spec), shape_config(spec)
    break_it(metrics, config)
    with pytest.raises(order6b_select.SelectError, match=message):
        order6b_select._check_shape(spec, metrics, config)


def arm_with(spec_name: str, metrics: dict[str, Any]) -> order6b_select.Arm:
    spec = next(s for s in order6b_select.ARM_SPECS if s.name == spec_name)
    return order6b_select.Arm(
        spec=spec, metrics_path=Path("run") / METRICS_FILENAME, metrics=metrics, config={}
    )


def test_two_arms_with_different_preambles_stop() -> None:
    """★① と S-① と (c) の前置きが違えば止める(補正を掛けない候補 C1 は `check_arm` を通らない)。"""
    same = {"preamble": {"lines": ["a"], "sha256": "0" * 64}}
    other = {"preamble": {"lines": ["b"], "sha256": "1" * 64}}
    arms = {
        "preamble": arm_with("preamble", dict(same)),
        "s_preamble": arm_with("s_preamble", dict(other)),
        "c": arm_with("c", dict(same)),
        "b0": arm_with("b0", {}),
    }
    with pytest.raises(order6b_select.SelectError, match="前置きの sha256"):
        order6b_select.check_preambles(arms)
    arms["s_preamble"] = arm_with("s_preamble", dict(same))
    order6b_select.check_preambles(arms)


@pytest.mark.parametrize(
    "arms",
    [
        (CalibrationArm(name=ARM_B0, template_set="eval_main", preamble=False),),
        (
            CalibrationArm(name=ARM_B0, template_set="eval_main", preamble=False),
            CalibrationArm(name=ARM_D, template_set="order6b_d", preamble=False),
            CalibrationArm(name=ARM_PREAMBLE, template_set="order6b_d", preamble=True),
        ),
    ],
    ids=["missing_arms", "wrong_template_set"],
)
def test_a_calibration_run_with_the_wrong_arms_stops(arms: Any) -> None:
    """★(c) の run が 3 腕を宣言し、その形が腕の定数と合わなければ止める。"""
    calibration = calibrated.Calibration(
        run_id="run",
        symbols=("N/A",),
        arms=arms,
        preamble_lines=("a",),
        preamble_sha256="0" * 64,
        biases={},
    )
    with pytest.raises(order6b_select.SelectError, match="腕"):
        order6b_select.check_calibration_arms(calibration)


@pytest.mark.parametrize(
    ("option", "other"),
    [("b0", "d"), ("d", "b0"), ("r8", "s_preamble"), ("preamble", "b0"), ("c", "b0")],
)
def test_a_swapped_arm_stops(order6b: dict[str, Path], option: str, other: str) -> None:
    """★腕を取り違えたら止まる(名前ではなく記録の形で照合している)。"""
    with pytest.raises(order6b_select.SelectError):
        order6b_select.build_report(patterns_of(order6b, **{option: str(order6b[other])}))


@pytest.mark.parametrize("missing", list(CONFIG_NAME_OF_ARM))
def test_a_missing_arm_stops(order6b: dict[str, Path], missing: str) -> None:
    """★7 本すべてが要る(ADR-087 決定1)。1 本でも欠けたら何も出さずに止まる。"""
    with pytest.raises(order6b_select.SelectError, match="7 本すべてが要る"):
        order6b_select.build_report(patterns_of(order6b, **{missing: None}))


def test_a_glob_that_matches_two_runs_stops(order6b: dict[str, Path]) -> None:
    """★1 本の腕の glob が 2 本に当たったら止める(どちらを読んだか分からない表を出さない)。"""
    every_run = str(order6b["b0"].parent.parent / "*" / order6b["b0"].name)
    with pytest.raises(order6b_select.SelectError, match="1 本の run に当たら"):
        order6b_select.build_report(patterns_of(order6b, b0=every_run))


def test_a_different_near_tie_margin_between_arms_stops(
    order6b: dict[str, Path], tmp_path: Path
) -> None:
    """★閾値か近接同点の幅が腕どうしで違えば止める(`gonogo.build_report` と同じ)。"""
    copied = tmp_path / "b0"
    shutil.copytree(order6b["b0"], copied)
    config = load_config(copied / "config.yaml")
    config["gonogo"]["near_tie_margin"] = 0.5
    write_config(config, copied / "config.yaml")
    with pytest.raises(order6b_select.SelectError, match="近接同点の幅が違う"):
        order6b_select.build_report(patterns_of(order6b, b0=str(copied)))


# --------------------------------------------------------------------------
# 判定表(印は gonogo.py / r8_fit.py が付けたものを読むだけ)
# --------------------------------------------------------------------------


def candidate_of(report: Mapping[str, Any], task: str, name: str) -> Mapping[str, Any]:
    block = next(entry for entry in report["task_types"] if entry["task_type"] == task)
    return next(row for row in block["candidates"] if row["candidate"] == name)


def test_the_table_has_both_task_types_and_all_four_candidates(report: dict[str, Any]) -> None:
    """★行は 2 タスク型 × 4 候補で揃う。T3 の C2 は `applicable=false`(満たさなかったのではない)。"""
    assert [block["task_type"] for block in report["task_types"]] == [
        t3_comparison.T3,
        t3_comparison.T1B,
    ]
    for block in report["task_types"]:
        assert [row["candidate"] for row in block["candidates"]] == ["C0", "C3", "C2", "C1"]
    t3_c2 = candidate_of(report, t3_comparison.T3, "C2")
    assert t3_c2["applicable"] is False
    assert t3_c2["passed"] is None and t3_c2["criteria"] is None
    assert candidate_of(report, t3_comparison.T1B, "C2")["applicable"] is True


def test_the_marks_are_the_ones_gonogo_and_r8_fit_put_there(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★(i)・(ii)・(iv) の印は `gonogo.py` / `r8_fit.py` の表の `fails` をそのまま読んでいる。"""
    fixed = gonogo.run_report(order6b["b0"] / METRICS_FILENAME)
    sweep = r8_fit.run_report(order6b["r8"] / METRICS_FILENAME)
    threshold = fixed["thresholds"]["min_cell_correct_rate"]
    for task in (t3_comparison.T3, t3_comparison.T1B):
        row = candidate_of(report, task, "C0")
        cells = {c["task"]: c for c in fixed["cells"] if c["task"] == task}
        assert row["criteria"]["i"]["passed"] is not any(
            cell["fails"] for cell in fixed["cells"] if cell["task"] == task
        )
        assert row["criteria"]["ii"]["passed"] is not any(
            cell["fails"] for cell in fixed["constant_strategy"] if cell["task"] == task
        )
        assert cells  # セルが空なら上の 2 行は空で真になる
        expected_iv = all(
            cell["far_offset_correct"][side]["correct_rate"] >= threshold
            for cell in sweep["cells"]
            if cell["task_type"] == task
            for side in r8_fit.SIDES
        )
        assert row["criteria"]["iv"]["passed"] is expected_iv
        assert [cell["coverage"] for cell in row["criteria"]["iv"]["cells"]] == list(
            MAIN_COVERAGE_LEVELS
        )


def test_c3_reads_the_calibrated_tables_not_the_raw_ones(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★C3 は補正後の表を読む。**C0 と同じ数字にならない**(較正の腕を渡し忘れれば落ちる)。

    合成の応答では、植えた偏りが lt の極性で真値どおりの「No」を「Yes」へ倒すので、
    掃引の遠いオフセットの correct が下がる(**数値は実験結果ではない**)。
    """
    loaded = calibrated.load_calibration(order6b["c"] / METRICS_FILENAME)
    lookup = calibrated.bias_lookup(loaded, ARM_B0)
    fixed = gonogo.calibrated_run_report(order6b["b0"] / METRICS_FILENAME, lookup)
    sweep = r8_fit.calibrated_run_report(order6b["r8"] / METRICS_FILENAME, lookup)
    raw_sweep = r8_fit.run_report(order6b["r8"] / METRICS_FILENAME)
    for task in (t3_comparison.T3, t3_comparison.T1B):
        c3 = candidate_of(report, task, "C3")
        c0 = candidate_of(report, task, "C0")
        expected = {
            cell["coverage"]: cell["correct_rate"]
            for cell in fixed["cells"]
            if cell["task"] == task
        }
        assert {c["coverage"]: c["correct_rate"] for c in c3["criteria"]["i"]["cells"]} == expected
        assert {
            c["coverage"]: c[r8_fit.LOW]["correct_rate"] for c in c3["criteria"]["iv"]["cells"]
        } == {
            cell["coverage"]: cell["far_offset_correct"][r8_fit.LOW]["correct_rate"]
            for cell in sweep["cells"]
            if cell["task_type"] == task
        }
        # 補正が効いていることの確認 —— 補正前の掃引と同じ数字なら較正の腕を引いていない
        assert any(
            cell["far_offset_correct"][r8_fit.LOW]["correct_rate"]
            != raw["far_offset_correct"][r8_fit.LOW]["correct_rate"]
            for cell, raw in zip(
                [c for c in sweep["cells"] if c["task_type"] == task],
                [c for c in raw_sweep["cells"] if c["task_type"] == task],
                strict=True,
            )
        )
        assert c3["criteria"]["iv"]["passed"] is not c0["criteria"]["iv"]["passed"]


def test_the_numeric_gate_is_only_on_c1_and_reads_the_judged_groups(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★(iii) は C1 だけ。#1 は ① の run の judged の群すべて、#2 は T1・T2 の 6 セル。"""
    for task in (t3_comparison.T3, t3_comparison.T1B):
        for name in ("C0", "C3"):
            assert candidate_of(report, task, name)["criteria"]["iii"]["applicable"] is False
            assert candidate_of(report, task, name)["criteria"]["iii"]["passed"] is None
    fixed = gonogo.run_report(order6b["preamble"] / METRICS_FILENAME)
    judged = [row["group"] for row in fixed["parse_fail"] if row["judged"]]
    assert set(judged) == {numeric_sum.GROUP_BARE_SUM, numeric_sum.GROUP_WORD_PROBLEM}
    gate = candidate_of(report, t3_comparison.T3, "C1")["criteria"]["iii"]
    assert [row["group"] for row in gate["parse_fail"]] == judged
    assert [(row["task"], row["coverage"]) for row in gate["cells"]] == [
        (task, coverage)
        for task in (numeric_sum.T1, numeric_sum.T2)
        for coverage in MAIN_COVERAGE_LEVELS
    ]
    # (iii) は ① の run 1 本から読むので、2 つのタスク型で同じ値になる
    assert gate["passed"] == candidate_of(report, t3_comparison.T1B, "C1")["criteria"]["iii"]["passed"]


def test_the_selected_candidate_is_the_smallest_one_that_passed(report: dict[str, Any]) -> None:
    """★採るのは表の順(C0 < C3 < C2 < C1)で最初に満たした候補。満たすものが無ければ null。"""
    for block in report["task_types"]:
        passed = [row["candidate"] for row in block["candidates"] if row["passed"]]
        assert block["selected"] == (passed[0] if passed else None)
        assert block["no_candidate"] is (not passed)


def test_the_four_values_are_always_four(report: dict[str, Any]) -> None:
    """★4値は常に4つ揃えて出す(`CLAUDE.md` §6)。合計は 1.0。"""
    for block in report["task_types"]:
        for row in block["candidates"]:
            if not row["applicable"]:
                continue
            for cell in row["criteria"]["i"]["cells"]:
                rates = [cell[f"{name}_rate"] for name in order6b_select.CLASSES]
                assert len(rates) == 4
                assert abs(sum(rates) - 1.0) < 1e-9


def test_the_sensitivity_rows_ride_along_but_never_mark(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★感度の行は候補の行に併記されるが、合否(`passed`)には入っていない。"""
    row = candidate_of(report, t3_comparison.T1B, "C0")
    near_tie = row["near_tie"]
    assert near_tie["margin"] == report["settings"]["near_tie_margin"]
    assert [cell["coverage"] for cell in near_tie["fixed"]] == list(MAIN_COVERAGE_LEVELS)
    assert [cell["coverage"] for cell in near_tie["sweep"]] == list(MAIN_COVERAGE_LEVELS)
    assert any(cell["n_near_tie"] > 0 for cell in near_tie["fixed"])
    # 印は (i)〜(iv) だけから来ている
    assert row["passed"] is all(
        block["passed"] for block in row["criteria"].values() if block["passed"] is not None
    )
    # 補正後の候補(C3)の感度の行は、補正後の差で数えたと注記に書いてある
    assert candidate_of(report, t3_comparison.T1B, "C3")["near_tie"]["note"] == (
        gonogo.CALIBRATED_NEAR_TIE_NOTE
    )
    assert near_tie["note"] == gonogo.NEAR_TIE_NOTE


# --------------------------------------------------------------------------
# 記述の腕(ADR-086 決定1 / ADR-087 決定3)
# --------------------------------------------------------------------------


def test_the_descriptive_arms_carry_values_and_a_note_but_no_marks(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★①+(c) / (d)+(c) は別ブロックで、値と来歴と注記だけ。**合否の印はどこにも無い。**"""
    blocks = {block["name"]: block for block in report["descriptive"]}
    assert list(blocks) == ["①+(c)", "(d)+(c)"]
    assert [block["task_type"] for block in blocks["(d)+(c)"]["task_types"]] == [t3_comparison.T1B]
    for name, block in blocks.items():
        assert block["note"] == calibrated.NOT_A_CANDIDATE_NOTE
        assert block["runs"]["calibration"] == json.loads(
            (order6b["c"] / METRICS_FILENAME).read_text(encoding="utf-8")
        )["run_id"]
        assert "fails" not in all_keys(block), name
        assert "passed" not in all_keys(block), name
        for entry in block["task_types"]:
            assert [cell["coverage"] for cell in entry["cells"]] == list(MAIN_COVERAGE_LEVELS)
            assert [cell["coverage"] for cell in entry["far_offset_correct"]] == list(
                MAIN_COVERAGE_LEVELS
            )


def test_the_descriptive_arms_use_their_own_calibration_arm(
    report: dict[str, Any], order6b: dict[str, Path]
) -> None:
    """★①+(c) は腕 `preamble` の偏り、(d)+(c) は腕 `d` の偏りを引いている(取り違えない)。"""
    blocks = {block["name"]: block for block in report["descriptive"]}
    assert blocks["①+(c)"]["calibration"]["arm"] == ARM_PREAMBLE
    assert blocks["(d)+(c)"]["calibration"]["arm"] == ARM_D
    loaded = calibrated.load_calibration(order6b["c"] / METRICS_FILENAME)
    for name, arm in (("①+(c)", ARM_PREAMBLE), ("(d)+(c)", ARM_D)):
        expected = calibrated.bias_lookup(loaded, arm).record()["biases"]
        assert blocks[name]["calibration"]["biases"] == expected


# --------------------------------------------------------------------------
# 選び方そのもの(合成の表。本実行を通さない)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeArm:
    run_id: str


class FakeReports:
    """`Reports` の代わり((腕, 較正の腕) -> 表)。**選び方だけを見るための道具。**"""

    def __init__(self, tables: Mapping[tuple[str, str | None], Mapping[str, Any]]) -> None:
        self._tables = tables

    def of(self, arm: str, calibration_arm: str | None) -> Mapping[str, Any]:
        return self._tables[(arm, calibration_arm)]


def fixed_table(
    *,
    task: str,
    i_ok: bool,
    ii_ok: bool,
    numeric_ok: bool = True,
    parse_fail_ok: bool | None = None,
) -> dict[str, Any]:
    """1 つのタスク型だけを解いた固定オフセットの表(印だけを置いた合成)。"""
    cells = [
        {
            "task": task,
            "coverage": coverage,
            "n": 10,
            "correct_rate": 1.0 if i_ok else 0.0,
            "rule_rate": 0.0 if i_ok else 1.0,
            "other_error_rate": 0.0,
            "parse_fail_rate": 0.0,
            "fails": not i_ok,
        }
        for coverage in MAIN_COVERAGE_LEVELS
    ]
    cells += [
        {
            "task": numeric,
            "coverage": coverage,
            "n": 10,
            "correct_rate": 1.0 if numeric_ok else 0.0,
            "rule_rate": 0.0 if numeric_ok else 1.0,
            "other_error_rate": 0.0,
            "parse_fail_rate": 0.0,
            "fails": not numeric_ok,
        }
        for numeric in (numeric_sum.T1, numeric_sum.T2)
        for coverage in MAIN_COVERAGE_LEVELS
    ]
    return {
        "solved_task_types": [task, numeric_sum.T1, numeric_sum.T2],
        "near_tie_margin": None,
        "near_tie": None,
        "thresholds": {"parse_fail_max": 0.02, "min_cell_correct_rate": 0.70},
        "parse_fail": [
            {
                "group": numeric_sum.GROUP_BARE_SUM,
                "judged": True,
                "n": 10,
                "parse_fail_rate": 0.0 if parse_fail_ok is not False else 1.0,
                "fails": parse_fail_ok is False,
            }
        ],
        "cells": cells,
        "constant_strategy": [
            {
                "task": task,
                "coverage": coverage,
                "n": 10,
                "correct_rate": 1.0 if ii_ok else 0.0,
                "baselines": {
                    "always_yes": {"correct_rate": 0.5},
                    "always_no": {"correct_rate": 0.5},
                },
                "fails": not ii_ok,
            }
            for coverage in MAIN_COVERAGE_LEVELS
        ],
    }


def sweep_table(*, task: str, iv_ok: bool) -> dict[str, Any]:
    """1 つのタスク型だけの掃引の表(遠いオフセットの correct だけを置いた合成)。"""
    rate = 1.0 if iv_ok else 0.5
    return {
        "task_types": [task],
        "near_tie": None,
        "cells": [
            {
                "task_type": task,
                "coverage": coverage,
                "far_offset_correct": {
                    side: {"n": 10, "n_correct": int(10 * rate), "correct_rate": rate}
                    for side in r8_fit.SIDES
                },
            }
            for coverage in MAIN_COVERAGE_LEVELS
        ],
    }


SETTINGS = order6b_select.Settings(
    thresholds=gonogo.Thresholds(parse_fail_max=0.02, min_cell_correct_rate=0.70),
    near_tie_margin=None,
)
FAKE_ARMS = {spec.name: FakeArm(run_id=f"run_{spec.name}") for spec in order6b_select.ARM_SPECS}


def tables_for(task: str, **passing: bool) -> FakeReports:
    """候補ごとに「満たす / 満たさない」を指定した表の束。"""
    tables: dict[tuple[str, str | None], Mapping[str, Any]] = {}
    for spec in order6b_select.CANDIDATES:
        ok = passing.get(spec.name, True)
        tables[(spec.fixed_arm, spec.calibration_arm)] = fixed_table(
            task=task, i_ok=ok, ii_ok=True
        )
        tables[(spec.sweep_arm, spec.calibration_arm)] = sweep_table(task=task, iv_ok=True)
    return FakeReports(tables)


def test_the_smallest_passing_candidate_wins() -> None:
    """★C0 が落ちて C3 が満たせば C3 を採る(表の順で最も小さいもの)。"""
    result = order6b_select.select_for(
        t3_comparison.T3, tables_for(t3_comparison.T3, C0=False), SETTINGS, FAKE_ARMS
    )
    assert result["selected"] == "C3"
    assert result["no_candidate"] is False


def test_no_candidate_is_its_own_mark() -> None:
    """★1 つも満たさなければ `selected = null` + `no_candidate = true`(ADR-086 決定4)。"""
    result = order6b_select.select_for(
        t3_comparison.T3,
        tables_for(t3_comparison.T3, C0=False, C3=False, C2=False, C1=False),
        SETTINGS,
        FAKE_ARMS,
    )
    assert result["selected"] is None
    assert result["no_candidate"] is True
    assert [row["passed"] for row in result["candidates"]] == [False, False, None, False]


@pytest.mark.parametrize(
    ("t3_selected", "t1b_selected", "expected"),
    [("C0", "C0", False), ("C1", "C1", False), ("C1", "C0", True), ("C0", "C1", True)],
)
def test_the_preamble_mismatch_is_true_only_when_one_side_uses_the_preamble(
    t3_selected: str, t1b_selected: str, expected: bool
) -> None:
    """★食い違いの印は「片方だけが C1」のとき true(§5 の「そのまま人間に上げる」)。"""
    selections = [{"selected": t3_selected}, {"selected": t1b_selected}]
    assert order6b_select.preamble_mismatch(selections) is expected


@pytest.mark.parametrize("selections", [[{"selected": None}, {"selected": "C0"}], [{"selected": "C1"}, {"selected": None}]])
def test_the_preamble_mismatch_is_null_when_a_task_type_has_no_candidate(
    selections: list[dict[str, Any]],
) -> None:
    """★片方に候補が無ければ ① の有無は定義できない。**null であって false ではない**(ADR-086 決定4)。"""
    assert order6b_select.preamble_mismatch(selections) is None


def test_a_failing_criterion_is_enough_to_drop_a_candidate() -> None:
    """★(i)〜(iv) は AND。1 つ割れれば候補は落ちる。"""
    for key, tables in (
        ("i", tables_for(t3_comparison.T3, C0=False)),
        (
            "ii",
            FakeReports(
                {
                    (spec.fixed_arm, spec.calibration_arm): fixed_table(
                        task=t3_comparison.T3, i_ok=True, ii_ok=spec.name != "C0"
                    )
                    for spec in order6b_select.CANDIDATES
                }
                | {
                    (spec.sweep_arm, spec.calibration_arm): sweep_table(
                        task=t3_comparison.T3, iv_ok=True
                    )
                    for spec in order6b_select.CANDIDATES
                }
            ),
        ),
        (
            "iv",
            FakeReports(
                {
                    (spec.fixed_arm, spec.calibration_arm): fixed_table(
                        task=t3_comparison.T3, i_ok=True, ii_ok=True
                    )
                    for spec in order6b_select.CANDIDATES
                }
                | {
                    (spec.sweep_arm, spec.calibration_arm): sweep_table(
                        task=t3_comparison.T3, iv_ok=spec.name != "C0"
                    )
                    for spec in order6b_select.CANDIDATES
                }
            ),
        ),
    ):
        result = order6b_select.select_for(t3_comparison.T3, tables, SETTINGS, FAKE_ARMS)
        row = next(r for r in result["candidates"] if r["candidate"] == "C0")
        assert row["passed"] is False, key
        assert row["criteria"][key]["passed"] is False, key
        assert result["selected"] == "C3", key


@pytest.mark.parametrize(
    ("numeric_ok", "parse_fail_ok"),
    [(False, True), (True, False), (False, False)],
    ids=["only_the_cells_fail", "only_the_groups_fail", "both_fail"],
)
def test_the_numeric_gate_drops_c1_in_both_task_types(
    numeric_ok: bool, parse_fail_ok: bool
) -> None:
    """★(iii) は #1 と #2 の**両方**を見る。片方だけ割れても C1 は落ちる。

    ① の run は 1 本なので、割れれば T3・T1b の両方で C1 が落ちる。
    """
    tables = FakeReports(
        {
            (spec.fixed_arm, spec.calibration_arm): fixed_table(
                task=t3_comparison.T3,
                i_ok=True,
                ii_ok=True,
                numeric_ok=numeric_ok,
                parse_fail_ok=parse_fail_ok,
            )
            for spec in order6b_select.CANDIDATES
        }
        | {
            (spec.sweep_arm, spec.calibration_arm): sweep_table(task=t3_comparison.T3, iv_ok=True)
            for spec in order6b_select.CANDIDATES
        }
    )
    result = order6b_select.select_for(t3_comparison.T3, tables, SETTINGS, FAKE_ARMS)
    row = next(r for r in result["candidates"] if r["candidate"] == "C1")
    assert row["criteria"]["iii"]["passed"] is False
    assert row["passed"] is False


def test_the_numeric_gate_passes_only_when_both_are_clean() -> None:
    """★#1 と #2 がどちらも割れていなければ (iii) は満たす(常に false ではない)。"""
    table = fixed_table(task=t3_comparison.T3, i_ok=True, ii_ok=True)
    assert order6b_select.numeric_gate(table)["passed"] is True


def test_a_gate_without_judged_groups_stops() -> None:
    """★#1 の判定対象の群が 0 件なら止める(**空で真になる読みを作らない**)。"""
    table = fixed_table(task=t3_comparison.T3, i_ok=True, ii_ok=True)
    table["parse_fail"] = [{**table["parse_fail"][0], "judged": False}]
    with pytest.raises(order6b_select.SelectError, match="judged"):
        order6b_select.numeric_gate(table)


def test_a_task_type_the_run_did_not_solve_stops() -> None:
    """★候補が要るタスク型をその run が解いていなければ止める(腕と候補の食い違い)。"""
    table = fixed_table(task=t3_comparison.T3, i_ok=True, ii_ok=True)
    with pytest.raises(order6b_select.SelectError, match="が無い"):
        order6b_select.cells_i(table, t3_comparison.T1B)


def test_a_missing_coverage_cell_stops() -> None:
    """★3 セルのどれかが表に無ければ止める(2 セルで「すべて満たした」と読ませない)。"""
    table = fixed_table(task=t3_comparison.T3, i_ok=True, ii_ok=True)
    table["cells"] = [cell for cell in table["cells"] if cell["coverage"] != MAIN_COVERAGE_LEVELS[0]]
    with pytest.raises(order6b_select.SelectError, match="セル"):
        order6b_select.cells_i(table, t3_comparison.T3)


@pytest.mark.parametrize("side", [r8_fit.LOW, r8_fit.HIGH])
def test_the_far_offset_needs_both_sides(side: str) -> None:
    """★(iv) は低い側と高い側の**両方**が基準以上でなければ満たさない(片側だけ見ない)。"""
    table = sweep_table(task=t3_comparison.T3, iv_ok=True)
    table["cells"][1]["far_offset_correct"][side]["correct_rate"] = 0.5
    result = order6b_select.far_offsets_iv(table, t3_comparison.T3, 0.70)
    assert result["passed"] is False
    assert [cell["fails"] for cell in result["cells"]] == [False, True, False]


@pytest.mark.parametrize(
    ("rate", "fails"), [(0.70, False), (0.6999, True)], ids=["on_the_line", "just_below"]
)
def test_the_far_offset_includes_the_threshold_itself(rate: float, fails: bool) -> None:
    """★(iv) の基準はちょうど 0.70 を**満たす**(`>=`。#2 と同じ比べ方。新しい値を作らない)。"""
    table = sweep_table(task=t3_comparison.T3, iv_ok=True)
    for cell in table["cells"]:
        for side in r8_fit.SIDES:
            cell["far_offset_correct"][side]["correct_rate"] = rate
    result = order6b_select.far_offsets_iv(table, t3_comparison.T3, 0.70)
    assert result["passed"] is not fails
    assert all(cell["fails"] is fails for cell in result["cells"])


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def test_the_cli_writes_the_table_and_prints_it(
    order6b: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """★CLI が判定表を書き、標準出力に「候補であって採用ではない」と出す。"""
    out_dir = tmp_path / "select"
    argv: list[str] = []
    for spec in order6b_select.ARM_SPECS:
        argv += [spec.option, str(order6b[spec.name])]
    assert order6b_select.main([*argv, "--out-dir", str(out_dir)]) == 0
    written = json.loads((out_dir / order6b_select.OUTPUT_FILENAME).read_text(encoding="utf-8"))
    assert [block["task_type"] for block in written["task_types"]] == [
        t3_comparison.T3,
        t3_comparison.T1B,
    ]
    printed = capsys.readouterr().out
    assert "候補であって採用ではない" in printed
    assert "このタスク型に候補は無い" in printed  # T3 の C2
    assert "記述(§5 の候補ではない" in printed
    assert order6b_select.OUTPUT_FILENAME in printed
