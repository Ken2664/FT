"""Go/No-Go #4・#4b・#5・#5b の表(`code/analysis/gonogo_ft.py`)。PLAN-031 §3.3(I3)。

答える問い: 「アダプタを載せた評価 run から、基準を割った run・セルに正しく印が付くか。
`p2`・`ident`・`p2d` を読み違えていないか」

ここで固定する最重要の性質:
  - **#4 は `p2` の run だけが判定の対象で、`ident`・`p2d` は並べるだけ**(a1)/ **#4b は `p2d` の run だけ**で、
    参照規則 `p2d` のブロックで読む / **すべてのシードを見て、平均を門にしない**(b1)
  - **#5・#5b の `other_error_rate` はその run の条件自身の規則のブロックで数える**(`p2d` の run を `p2` の
    ブロックで数えると、病変どおりの応答が「モデル崩壊」に見える)
  - **#5b は 4 型版(T1b・T3 は構造上 0 と注記)と T1 × T2 版の両方**(d3)
  - **`pool_id` が `pilot` でない run が混ざったら止まる** / アダプタの無い run は止まる /
    同じ (条件, シード) の重複・閾値の食い違いは止まる
  - **4 値は揃えて出し、合計は 1.0**
  - 配線: パイロット用プールと**パイロット FT の評価 config**で固定応答の本実行をした run の上で、端から端まで表が組める

**ここに出る数値は実験結果ではない**(合成の応答。病変を「真似る」応答関数で回した)。
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.analysis import gonogo, gonogo_ft
from code.config import load_config
from code.data_gen import eval_pool
from code.data_gen.battery_items import read_items
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval import run
from code.lesion import Lesion
from code.rates import CORRECT, OTHER_ERROR, PARSE_FAIL, RULE

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

# (条件, シード)。パイロット FT の評価 config 5 本(ADR-099 決定4・6)。
ARMS = (("p2", 0), ("p2", 1), ("ident", 0), ("ident", 1), ("p2d", 0))
N_TRAIN_STEPS = 625
FIRST_LOSS, LAST_LOSS = 2.5, 0.125
# 合成の「乱れ」を入れる項目の割合(item_id のハッシュ % 2 / % 4。**実験の値ではない**)。
HALF, QUARTER = 2, 4
OTHER_ERROR_OFFSET = 1000  # 真値からも規則値からも遠い値(other_error に落ちる)

Simulator = Callable[[Any, dict[str, Lesion]], int]


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


def eval_config_path(condition: str, seed: int) -> Path:
    return CONFIG_DIR / f"exp_pilot_ft_eval_{condition}_s{seed}.yaml"


def bucket(item: Any, modulus: int) -> int:
    return int(hashlib.sha256(item.item_id.encode()).hexdigest(), 16) % modulus


def follow(rule: str) -> Simulator:
    """常に条件の規則どおりに答える応答関数(`truth` なら真値)。"""

    def answer(item: Any, lesions: dict[str, Lesion]) -> int:
        a, b = item.operands
        return a + b if rule == "truth" else lesions[rule].apply(a, b)

    return answer


def half_rule_half_truth(rule: str) -> Simulator:
    """ハッシュの偶数の項目だけ規則どおり、奇数は真値(`T1 × id` の rule_rate がおよそ半分)。"""

    def answer(item: Any, lesions: dict[str, Lesion]) -> int:
        chosen = follow(rule if bucket(item, HALF) == 0 else "truth")
        return chosen(item, lesions)

    return answer


def truth_with_word_problem_noise(item: Any, lesions: dict[str, Lesion]) -> int:
    """真値どおり。ただし T2(文章題)の 1/4 は other_error に落ちる値を返す(#5・#5b を割る)。"""
    a, b = item.operands
    noisy = item.group == "word_problem" and bucket(item, QUARTER) == 0
    return a + b + (OTHER_ERROR_OFFSET if noisy else 0)


def build_engines(
    config: dict[str, Any], items: list[Any], simulate: Simulator
) -> dict[str, Any]:
    """`simulate` の答えをそのまま返す固定応答。特異性対照は真値。比較群は解かない(scorer は呼ばれない)。"""
    template_set = config["data"]["eval_template_set"]
    lesions = run.build_reference_lesions(config)
    texts: dict[str, str] = {}
    for item in items:
        if item.group == "comparison":
            continue
        prompt = run.RENDERERS[item.group](
            item, run.load_group_templates(config, item.group, template_set)
        )
        if item.group == "specificity":
            texts[prompt] = f"Answer: {run.specificity_control.item_true_value(item)}."
        else:
            texts[prompt] = f"Answer: {simulate(item, lesions)}."

    def generator(prompts: list[str]) -> list[str]:
        return [texts[prompt] for prompt in prompts]

    def scorer(prompts: list[str]) -> list[Any]:
        raise AssertionError("比較群は解かない評価である(ADR-099 決定5)")

    return {"generator": generator, "scorer": scorer}


def write_fake_train_run(root: Path, condition: str, seed: int) -> Path:
    """評価が引く訓練 run の metrics.json とアダプタのディレクトリ(重みは無い)。"""
    train_dir = root / f"pilot_ft_train_{condition}_s{seed}"
    (train_dir / "adapter").mkdir(parents=True)
    payload = {
        "run_id": train_dir.name,
        "kind": "lora_train",
        "experiment_id": f"exp_pilot_ft_train_{condition}",
        "lesion_condition": condition,
        "seed": seed,
        "epochs_consumed": 1.0,
        "outcome": {
            "n_steps": N_TRAIN_STEPS,
            "first_loss": FIRST_LOSS,
            "last_loss": LAST_LOSS,
            "adapter_init_sha256": "ab" * 32,
            "adapter_param_dtype": "torch.float32",
        },
    }
    (train_dir / "metrics.json").write_text(json.dumps(payload), encoding="utf-8")
    return train_dir / "adapter"


def execute_arm(
    condition: str, seed: int, pool_dir: Path, root: Path, simulate: Simulator
) -> Path:
    config = load_config(eval_config_path(condition, seed))
    config["eval"]["anchor_manifest"] = str(pool_dir / "manifest.json")
    config["model"]["device"] = "cpu"
    config["model"]["adapter"] = str(write_fake_train_run(root, condition, seed))
    target = root / f"eval_{condition}_s{seed}"
    target.mkdir()
    config_path = target / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    engines = build_engines(config, read_items(pool_dir / "items.jsonl"), simulate)
    return run.execute(config, config_path=config_path, run_dir=target / "run", **engines)


# シードごとの応答関数。(p2, 0) = 規則どおり(#4 が通る)/ (p2, 1) = 半分だけ規則どおり(#4 が割れる)/
# (ident, 0) = 真値 / (ident, 1) = 真値 + T2 に other_error(#5・#5b が割れる)/ (p2d, 0) = p2d どおり。
SIMULATORS: dict[tuple[str, int], Simulator] = {
    ("p2", 0): follow("p2"),
    ("p2", 1): half_rule_half_truth("p2"),
    ("ident", 0): follow("truth"),
    ("ident", 1): truth_with_word_problem_noise,
    ("p2d", 0): follow("p2d"),
}


@pytest.fixture(scope="module")
def pilot_ft_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, int], Path]:
    """パイロット用プールを tmp に書き、パイロット FT の評価 config 5 本で固定応答の本実行をする。"""
    root = tmp_path_factory.mktemp("pilot_ft")
    pool_dir = root / "pilot_pool"
    eval_pool.write_pool(
        eval_pool.build(load_config(CONFIG_DIR / "exp_order6b_pilot.yaml")), pool_dir
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")
        return {
            (condition, seed): execute_arm(
                condition, seed, pool_dir, root, SIMULATORS[(condition, seed)]
            )
            for condition, seed in ARMS
        }


@pytest.fixture(scope="module")
def report(pilot_ft_runs: dict[tuple[str, int], Path]) -> dict[str, Any]:
    return gonogo_ft.build_report([path / "metrics.json" for path in pilot_ft_runs.values()])


def run_of(report: dict[str, Any], condition: str, seed: int) -> dict[str, Any]:
    (found,) = [r for r in report["runs"] if (r["condition"], r["seed"]) == (condition, seed)]
    return found


# --------------------------------------------------------------------------
# 端から端まで
# --------------------------------------------------------------------------


def test_the_report_has_one_run_per_condition_and_seed_and_is_marked_pilot(
    report: dict[str, Any],
) -> None:
    """★run は (条件, シード) ごとに並ぶ(平均にしない)。注記の先頭は pool_id: pilot。"""
    assert [(r["condition"], r["seed"]) for r in report["runs"]] == sorted(ARMS)
    assert report["note"].startswith("pool_id: pilot。主張・効果量・検出力分析・Δ 5 行・E1 の境界には使わない")
    assert {r["provenance"]["pool_id"] for r in report["runs"]} == {"pilot"}
    assert {tuple(r["solved_task_types"]) for r in report["runs"]} == {("t1", "t2")}


def test_every_cell_reports_the_four_values_summing_to_one_under_both_reference_rules(
    report: dict[str, Any],
) -> None:
    """★4 値は揃えて出す(合計 1.0)。参照規則 p2・p2d の両ブロックを残す。セルは T1・T2 × 3 = 6。"""
    for one in report["runs"]:
        assert len(one["cells"]) == len(gonogo_ft.NUMERIC_TASKS) * len(MAIN_COVERAGE_LEVELS)
        for cell in one["cells"]:
            assert set(cell["by_reference"]) == set(gonogo_ft.REFERENCE_RULES)
            for block in cell["by_reference"].values():
                names = (CORRECT, RULE, OTHER_ERROR, PARSE_FAIL)
                total = sum(block[f"{name}_rate"] for name in names)
                assert total == pytest.approx(1.0)


def test_the_reference_rows_hold_the_instructed_t1_and_the_specificity_controls(
    report: dict[str, Any],
) -> None:
    """参考の行(判定しない): 指示付き T1・spec_sub・spec_mul。"""
    names = {row["name"] for row in run_of(report, "p2", 0)["reference_rows"]}
    assert names == {"bare_sum_instructed", "spec_sub", "spec_mul"}


def test_the_train_record_comes_from_the_training_run(report: dict[str, Any]) -> None:
    """訓練 run の損失・ステップ数・エポック数・初期値の指紋を評価 run から引く。"""
    train = run_of(report, "p2", 0)["train"]
    assert train["n_steps"] == N_TRAIN_STEPS and train["epochs_consumed"] == 1.0
    assert (train["first_loss"], train["last_loss"]) == (FIRST_LOSS, LAST_LOSS)
    assert train["adapter_param_dtype"] == "torch.float32"


# --------------------------------------------------------------------------
# #4・#4b
# --------------------------------------------------------------------------


def test_no4_judges_only_the_p2_runs_and_lists_the_others(report: dict[str, Any]) -> None:
    """★#4(a1): `p2` の run だけ判定する。`ident`・`p2d` は並べる(判定は None)。"""
    p2_clean = run_of(report, "p2", 0)["penetrance"]["no4"]
    assert p2_clean["judged"] and p2_clean["rule_rate"] == 1.0 and p2_clean["fails"] is False
    for condition, seed in (("ident", 0), ("ident", 1), ("p2d", 0)):
        listed = run_of(report, condition, seed)["penetrance"]["no4"]
        assert not listed["judged"] and listed["fails"] is None
    # ident は並べる: 真値を答えるので p2 のブロックの rule_rate は 0
    assert run_of(report, "ident", 0)["penetrance"]["p2_block"][gonogo_ft.RULE_RATE] == 0.0


def test_no4_marks_a_seed_that_stays_below_the_criterion(report: dict[str, Any]) -> None:
    """★#4(b1): 片方のシードが割れれば割れた run が挙がる。平均で隠さない。"""
    weak = run_of(report, "p2", 1)["penetrance"]["no4"]
    assert weak["rule_rate"] < weak["min"] and weak["fails"] is True
    summary = report["summary"]["no4"]
    assert summary["judged_runs"] == [
        run_of(report, "p2", 0)["run_id"],
        run_of(report, "p2", 1)["run_id"],
    ]
    assert summary["failing_runs"] == [run_of(report, "p2", 1)["run_id"]]
    assert summary["all_pass"] is False


def test_no4b_reads_the_p2d_block_of_the_p2d_run_only(report: dict[str, Any]) -> None:
    """★#4b: `p2d` の run だけ判定し、参照規則 p2d のブロックで読む。p2 のブロックでは rule が 0。"""
    p2d = run_of(report, "p2d", 0)["penetrance"]
    assert p2d["no4b"]["judged"] and p2d["no4b"]["rule_rate"] == 1.0
    assert p2d["no4b"]["fails"] is False
    assert p2d["p2_block"][gonogo_ft.RULE_RATE] == 0.0  # p2 のブロックには病変が rule と数えられない
    assert p2d["no4"]["fails"] is None
    assert run_of(report, "p2", 0)["penetrance"]["no4b"]["fails"] is None
    assert report["summary"]["no4b"]["judged_runs"] == [run_of(report, "p2d", 0)["run_id"]]


def test_the_p2d_criterion_is_a_separate_key_from_no4(report: dict[str, Any]) -> None:
    """#4b の基準は #4 と別の鍵(目視確認待ち)。値は同じ 0.90 でも取り違えない。"""
    gate = run_of(report, "p2d", 0)["gate"]
    assert gate["penetrance_p2d_min"] == 0.90 and gate["penetrance_min"] == 0.90
    assert "目視確認待ち" in report["notes"]["no4b"]


# --------------------------------------------------------------------------
# #5・#5b
# --------------------------------------------------------------------------


def test_no5_counts_a_p2d_run_under_its_own_rule(report: dict[str, Any]) -> None:
    """★#5: `p2d` の run は参照規則 p2d で数える。p2 のブロックなら病変どおりの応答が other_error に落ちる。"""
    p2d = run_of(report, "p2d", 0)
    assert p2d["own_rule"] == "p2d"
    assert all(
        row["other_error_rate"] == 0.0 and row["fails"] is False for row in p2d["other_error"]
    )
    # 同じ run を p2 のブロックで数えると全セルが other_error(モデル崩壊に見える)
    assert all(
        cell["by_reference"]["p2"]["other_error_rate"] == 1.0 for cell in p2d["cells"]
    )
    assert run_of(report, "ident", 0)["own_rule"] == "p2"


def test_no5_marks_the_cells_whose_other_error_reaches_the_limit(report: dict[str, Any]) -> None:
    """★#5(c2): 全条件・全セルで見る。T2 に乱れを入れた ident の run は T2 のセルに印が付く。"""
    noisy = run_of(report, "ident", 1)["other_error"]
    marked = {(row["task"], row["coverage"]) for row in noisy if row["fails"]}
    assert marked == {("t2", coverage) for coverage in MAIN_COVERAGE_LEVELS}
    assert not any(row["fails"] for row in run_of(report, "ident", 0)["other_error"])
    assert report["summary"]["no5"]["failing_runs"] == [run_of(report, "ident", 1)["run_id"]]


def test_no5b_reports_both_versions_and_marks_the_noisy_run(report: dict[str, Any]) -> None:
    """★#5b(d3): 4 型版と T1 × T2 版の両方。T1b・T3 は構造上 0 で、評価していない旨を残す。"""
    clean = run_of(report, "p2", 0)["spread"]["by_coverage"]
    noisy = run_of(report, "ident", 1)["spread"]["by_coverage"]
    for coverage in MAIN_COVERAGE_LEVELS:
        v1 = clean[coverage]["v1_four_types"]
        assert v1["not_evaluated"] == ["t3", "t1b"]
        assert v1["other_error_by_task"]["t3"] == 0.0 and v1["other_error_by_task"]["t1b"] == 0.0
        assert v1["spread"] == 0.0 and v1["fails"] is False
        assert clean[coverage]["v2_t1_t2"]["fails"] is False
        assert noisy[coverage]["v1_four_types"]["fails"] is True
        assert noisy[coverage]["v2_t1_t2"]["fails"] is True
    assert report["summary"]["no5b_v1"]["failing_runs"] == [run_of(report, "ident", 1)["run_id"]]
    assert report["summary"]["no5b_v2"]["failing_runs"] == [run_of(report, "ident", 1)["run_id"]]


def test_spread_record_takes_max_minus_min_and_marks_at_the_limit() -> None:
    """max − min が上限に等しければ印(基準は `< 0.05`)。"""
    record = gonogo_ft.spread_record({"t1": 0.0, "t2": 0.05}, 0.05, [])
    assert record["spread"] == 0.05 and record["fails"] is True
    assert gonogo_ft.spread_record({"t1": 0.0, "t2": 0.049}, 0.05, [])["fails"] is False


# --------------------------------------------------------------------------
# 記述の表
# --------------------------------------------------------------------------


def test_the_contrast_pairs_p2_and_ident_of_the_same_seed_only(report: dict[str, Any]) -> None:
    """★p2 − ident(記述。E1 ではない): 同じシードの対だけ。`p2d` は対にしない。"""
    assert {row["seed"] for row in report["contrast"]} == {0, 1}
    seed0 = [
        r
        for r in report["contrast"]
        if r["seed"] == 0 and (r["task"], r["coverage"]) == ("t1", "id")
    ]
    (cell,) = seed0
    assert cell["rule_rate_p2"] == 1.0 and cell["rule_rate_ident"] == 0.0
    assert cell["rule_rate_diff"] == 1.0
    assert "E1 ではない" in report["notes"]["contrast"]


# --------------------------------------------------------------------------
# 止まるべきとき
# --------------------------------------------------------------------------


def copied_run(source: Path, tmp_path: Path, edit: Callable[[dict[str, Any]], None]) -> Path:
    """run のディレクトリを写して metrics.json を書き換える(元の run は変えない)。"""
    target = tmp_path / source.name
    shutil.copytree(source, target)
    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    edit(payload)
    (target / "metrics.json").write_text(json.dumps(payload), encoding="utf-8")
    return target / "metrics.json"


def test_a_run_of_another_pool_stops(
    pilot_ft_runs: dict[tuple[str, int], Path], tmp_path: Path
) -> None:
    """★`pool_id` が pilot でない run が混ざったら止まる(PLAN-001 §4.6 規則4)。"""
    path = copied_run(
        pilot_ft_runs[("p2", 0)], tmp_path, lambda payload: payload["pool"].update(pool_id="main")
    )
    with pytest.raises(gonogo_ft.PilotGateError, match="pool_id='main'"):
        gonogo_ft.run_report(path)


def test_a_run_without_an_adapter_stops(
    pilot_ft_runs: dict[tuple[str, int], Path], tmp_path: Path
) -> None:
    """アダプタの無い run(素のモデル)は --runs に渡せない。--baseline にだけ渡せる。"""
    path = copied_run(
        pilot_ft_runs[("p2", 0)], tmp_path, lambda payload: payload.update(adapter=None, seed=None)
    )
    with pytest.raises(gonogo_ft.PilotGateError, match="アダプタを載せていない"):
        gonogo_ft.run_report(path)


def test_the_same_condition_and_seed_twice_stops(
    pilot_ft_runs: dict[tuple[str, int], Path],
) -> None:
    path = pilot_ft_runs[("p2", 0)] / "metrics.json"
    with pytest.raises(gonogo_ft.PilotGateError, match="複数"):
        gonogo_ft.build_report([path, path])


def test_missing_gate_thresholds_stop() -> None:
    """★設計門の閾値が config に無ければ止まる(既定値を作らない)。本番 config には無い。"""
    with pytest.raises(gonogo_ft.PilotGateError, match="設計門の閾値"):
        gonogo_ft.gate_from_config(load_config(CONFIG_DIR / "exp_phase1_main.yaml"), "run")
    gate = gonogo_ft.gate_from_config(load_config(eval_config_path("p2", 0)), "run")
    assert gate.as_dict() == {
        "penetrance_min": 0.90,
        "penetrance_p2d_min": 0.90,
        "other_error_max": 0.10,
        "other_error_spread_max": 0.05,
    }


def test_runs_with_different_gates_stop(
    pilot_ft_runs: dict[tuple[str, int], Path], tmp_path: Path
) -> None:
    """run 間で閾値が違えば止まる(混ぜて印を付けない)。"""
    changed = copy.deepcopy(pilot_ft_runs[("ident", 0)])
    target = tmp_path / "ident_relaxed"
    shutil.copytree(changed, target)
    config = yaml.safe_load((target / "config.yaml").read_text(encoding="utf-8"))
    config["gonogo"]["pilot_design_gate"]["other_error_max"] = 0.5
    (target / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(gonogo_ft.PilotGateError, match="閾値が違う"):
        gonogo_ft.build_report(
            [pilot_ft_runs[("p2", 0)] / "metrics.json", target / "metrics.json"]
        )


# --------------------------------------------------------------------------
# 参照規則を替えた分類・素のモデル・CLI
# --------------------------------------------------------------------------


def test_reclassifying_with_the_reference_rule_matches_scoring_and_keeps_specificity(
    pilot_ft_runs: dict[tuple[str, int], Path],
) -> None:
    """★p2d のブロックの分類は scoring.classify に rule_values['p2d'] を渡したもの。特異性対照は自分の規則のまま。"""
    from code.analysis.frame import build_rows, load_run, read_predictions  # noqa: PLC0415

    metrics_path = pilot_ft_runs[("p2d", 0)] / "metrics.json"
    loaded = load_run(metrics_path)
    records = read_predictions(loaded.run_dir)
    rows = build_rows(loaded, records)
    under_p2d = gonogo_ft.rows_under_rule(rows, records, gonogo_ft.REFERENCE_P2D)
    for before, after, record in zip(rows, under_p2d, records, strict=True):
        if record["group"] == "specificity":
            assert after["classification"] == before["classification"]
        else:
            assert after["reference_rule"] == "p2d"
            assert after["classification"] == RULE  # p2d どおりに答えた run
            assert before["classification"] == OTHER_ERROR  # p2 のブロックでは other_error


def test_the_baseline_table_lists_the_same_cells_without_judging(
    pilot_ft_runs: dict[tuple[str, int], Path], tmp_path: Path
) -> None:
    """素のモデル(参考)は同じセルを並べ、判定しない。アダプタのある run は --baseline に渡せない。"""
    plain = copied_run(
        pilot_ft_runs[("ident", 0)],
        tmp_path,
        lambda payload: payload.update(adapter=None, seed=None),
    )
    baseline = gonogo_ft.baseline_report(plain, ["t1", "t2"])
    assert len(baseline["cells"]) == 6 and "fails" not in baseline["cells"][0]
    with pytest.raises(gonogo_ft.PilotGateError, match="アダプタの無い run"):
        gonogo_ft.baseline_report(pilot_ft_runs[("p2", 0)] / "metrics.json", ["t1", "t2"])


def test_the_cli_prints_the_tables_and_writes_the_json(
    pilot_ft_runs: dict[tuple[str, int], Path], tmp_path: Path, capsys: Any
) -> None:
    """CLI: 表を標準出力に出し、--out-dir を渡せば gonogo_ft.json を書く。注記が先頭にある。"""
    runs = [str(path) for path in pilot_ft_runs.values()]
    assert gonogo_ft.main(["--runs", *runs, "--out-dir", str(tmp_path)]) == 0
    written = json.loads((tmp_path / gonogo_ft.OUTPUT_FILENAME).read_text(encoding="utf-8"))
    assert len(written["runs"]) == len(ARMS)
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("pool_id: pilot")
    assert "#4b" in out and "#5b" in out


def test_gonogo_one_to_three_are_untouched_by_the_new_module() -> None:
    """★この module は gonogo.py の #1〜#3 の出力を変えない(関数を読むだけ。書き換えない)。"""
    assert gonogo.PARSE_FAIL_MAX_KEY == "gonogo.parse_fail_max"
    assert gonogo.MIN_CELL_CORRECT_KEY == "gonogo.min_cell_correct_rate"
    source = (REPO_ROOT / "code" / "analysis" / "gonogo.py").read_text(encoding="utf-8")
    assert "gonogo_ft" not in source and "pilot_design_gate" not in source
