"""`code/eval/rescore.py` のテスト(PLAN-022 §5 / §5.1)。

答える問い: 「回収済みの `predictions/*.jsonl` を新しい規則2(unanimous_integer)で
読み直す再採点は、C1-C5 の検査を正しく実行し、元の run ディレクトリには
何も書かないか」

**モデルの重みは1度も読まない**(GPU 0。PLAN-022 冒頭)。ここに出る数値は
テスト用に手で組んだ架空の行から出たものであり、実験結果ではない
(元の run `runs/20260910_104249_sweep_m` の実データには一切触れない)。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from code import artifacts
from code.config import load_config
from code.eval import rescore, sweep
from code.eval.battery import magnitude_sweep
from code.eval.model import load_generation_settings
from code.rates import CORRECT, OTHER_ERROR, PARSE_FAIL, RULE

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO_ROOT / "configs" / "smoke.yaml"

# ★実験条件ではない。code/tests/test_sweep.py の workspace と同じ値
# (smoke config は model.name / device / batch_size / do_sample を持たないか、
# 触ってはならない欄なので、テストの経路を通すためだけに埋める)。
TEST_MODEL = "tests/tiny-model"
TEST_REVISION = "0" * 40
TEST_DEVICE = "cpu"
TEST_BATCH_SIZE = 1
TEST_DO_SAMPLE = False

# ★実験条件ではない。code/tests/test_sweep.py の TEST_RADII / TEST_SHELL_RADII と同じ形
# (Q(M) の腕が引ける水準・引けない水準の両方を小さい数で通す)。
TEST_RADII = [2, 5, 9, 10, 12, 15]
TEST_SHELL_RADII = [12, 15]


def with_shell_arm(config: dict[str, Any]) -> dict[str, Any]:
    """smoke config に Q(M) の腕の欄を足す(code/tests/test_sweep.py と同じ形)。"""
    section = config["eval"]["magnitude_sweep"]
    section["radii"] = list(TEST_RADII)
    section["shell_definition"] = magnitude_sweep.SHELL_DEFINITION_QUADRANT
    section["shell_n_items"] = section["n_items_per_radius"]
    section["shell_radii"] = list(TEST_SHELL_RADII)
    section["shell_judgement_radii"] = list(TEST_SHELL_RADII)
    return config


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """git / pip freeze 等の外部コマンドの呼び出しを止める(code/tests/test_sweep.py と同じ理由)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


@pytest.fixture
def config() -> dict[str, Any]:
    """掃引を組める最小の config(モデルは読まない。PLAN-022 は GPU 0)。"""
    cfg = with_shell_arm(load_config(SMOKE_CONFIG))
    cfg["model"]["name"] = TEST_MODEL
    cfg["model"]["revision"] = TEST_REVISION
    cfg["model"]["device"] = TEST_DEVICE
    cfg["eval"]["batch_size"] = TEST_BATCH_SIZE
    cfg["eval"]["do_sample"] = TEST_DO_SAMPLE
    return cfg


def make_row(
    item_id: str,
    *,
    a: int,
    b: int,
    response: str,
    parsed: int | None,
    classification: str,
    radius: int,
    shell: str | None = None,
) -> dict[str, Any]:
    """1件の予測行(`code.eval.run.prediction_record` と同じ形。PLAN-022 のテスト用)。"""
    params: dict[str, Any] = {"radius": radius}
    if shell is not None:
        params["shell"] = shell
    return {
        "item_id": item_id,
        "group": "bare_sum",
        "category": "t1",
        "operands": [a, b],
        "carry": None,
        "params": params,
        "prompt": f"{a}+{b}=",
        "response": response,
        "parsed": parsed,
        "truth": a + b,
        "rule_values": {"p2": a + b + 2},
        "reference_rule": "p2",
        "classification": classification,
    }


def five_rows(prefix: str, radius: int, seed: int, *, shell: str | None = None) -> list[dict[str, Any]]:
    """1ファイルぶんの5行。「旧規則(単一トークンだけを採る)なら4件が読めず、
    1件だけ読めていた」という想定を作る(PLAN-022 §3 の境界事例そのもの)。

    新しい規則2(unanimous_integer)で読み直すと:
      1. 旧 parse_fail -> correct       (`-86` の言い直し。★F126 の典型。ADR-074 §3)
      2. 旧 parse_fail -> rule          (言い直しの値が偶然 rule 値と一致)
      3. 旧 parse_fail -> other_error   (言い直しの値が真値・rule 値のどちらでもない)
      4. 旧 parse_fail のまま           (途中計算の値が2つに割れている。規則2 は失敗のまま)
      5. 旧 correct のまま              (単一トークンは旧規則でも読めていた。C2 の陰性例)
    """
    tag = f"{prefix}-M{radius}-s{seed}"
    return [
        make_row(
            f"{tag}-1", a=-88, b=2, response="-86\n\nSo, the result is -86.",
            parsed=None, classification=PARSE_FAIL, radius=radius, shell=shell,
        ),
        make_row(
            f"{tag}-2", a=1, b=1, response="4\n\nSo, the result is 4.",
            parsed=None, classification=PARSE_FAIL, radius=radius, shell=shell,
        ),
        make_row(
            f"{tag}-3", a=1, b=2, response="9\n\nSo, the result is 9.",
            parsed=None, classification=PARSE_FAIL, radius=radius, shell=shell,
        ),
        make_row(
            f"{tag}-4", a=1, b=3, response="Maybe 3 or 4.",
            parsed=None, classification=PARSE_FAIL, radius=radius, shell=shell,
        ),
        make_row(
            f"{tag}-5", a=3, b=4, response="Answer: 7.",
            parsed=7, classification=CORRECT, radius=radius, shell=shell,
        ),
    ]


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_source_run(
    run_dir: Path, cfg: Mapping[str, Any], plan: magnitude_sweep.SweepPlan, shell: magnitude_sweep.ShellPlan
) -> None:
    """PLAN-022 のテスト用に、架空の「元の run」を作る。

    答える問い: 「`rescore.execute()` に読ませる元の run は、どう組めば自己整合的
    (保存済み `classification` から `metrics.json` が再現できる。C1)になるか」

    `metrics.json` は、書き出した predictions と**同じ関数**(`sweep.metrics_payload`)
    で組む —— そうしないと、この関数自体が C1 の検査対象と同じ矛盾を持ちうる。
    """
    run_dir.mkdir(parents=True)
    (run_dir / artifacts.PREDICTIONS_DIR).mkdir()
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(dict(cfg), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    arm1_by_radius: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for radius in plan.radii:
        arm1_by_radius[radius] = {}
        for seed in plan.seeds:
            rows = five_rows(sweep.PREDICTIONS_PREFIX, radius, seed)
            arm1_by_radius[radius][seed] = rows
            _write_jsonl(
                rescore.predictions_path(run_dir, sweep.PREDICTIONS_PREFIX, radius, seed), rows
            )

    arm2_by_radius: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for radius in shell.radii:
        arm2_by_radius[radius] = {}
        for seed in plan.seeds:
            rows = five_rows(sweep.QUADRANT_PREDICTIONS_PREFIX, radius, seed, shell=shell.definition)
            arm2_by_radius[radius][seed] = rows
            _write_jsonl(
                rescore.predictions_path(run_dir, sweep.QUADRANT_PREDICTIONS_PREFIX, radius, seed), rows
            )

    settings = load_generation_settings(cfg)
    arm1_results = [
        rescore.radius_result_from_records(radius, "p2", arm1_by_radius[radius], plan.seeds)
        for radius in plan.radii
    ]
    arm2_results = [
        rescore.radius_result_from_records(radius, "p2", arm2_by_radius[radius], plan.seeds)
        for radius in shell.radii
    ]
    now = datetime(2026, 9, 1, tzinfo=UTC)
    timing = artifacts.timing_record(
        started=now, ended=now, total_seconds=0.0, model_load_seconds=0.0,
        generation_seconds=0.0,
        n_items=sweep.total_items(arm1_results) + sweep.total_items(arm2_results),
    )
    payload = sweep.metrics_payload(
        cfg, settings, plan, arm1_results, shell=shell, quadrant=arm2_results,
        run_id=run_dir.name, timing=timing,
    )
    artifacts.write_metrics(run_dir, payload)


# --------------------------------------------------------------------------
# rescore_row / parse_fail_transition_counts(旧分類 -> 新分類。単体)
# --------------------------------------------------------------------------


def test_rescore_row_reparses_and_keeps_the_old_value_and_fields() -> None:
    """★新パーサで parsed / classification を置き換え、旧値と他フィールドは残す。"""
    row = make_row(
        "x", a=-88, b=2, response="-86\n\nSo, the result is -86.",
        parsed=None, classification=PARSE_FAIL, radius=999,
    )
    rescored = rescore.rescore_row(row, elicitation="direct")
    assert rescored["parsed"] == -86
    assert rescored["classification"] == CORRECT
    assert rescored["parsed_before"] is None
    assert rescored["classification_before"] == PARSE_FAIL
    # 他のフィールドは変わらない
    assert rescored["operands"] == [-88, 2]
    assert rescored["truth"] == -86
    assert rescored["item_id"] == "x"


def test_rescore_row_on_a_value_that_did_not_change() -> None:
    """★単一トークンは旧規則でも読めていたので、再採点しても値は変わらない。"""
    row = make_row("y", a=3, b=4, response="Answer: 7.", parsed=7, classification=CORRECT, radius=9)
    rescored = rescore.rescore_row(row, elicitation="direct")
    assert rescored["parsed"] == 7
    assert rescored["classification"] == CORRECT
    assert rescored["parsed_before"] == 7
    assert rescored["classification_before"] == CORRECT


def test_parse_fail_transition_counts_tallies_by_new_classification() -> None:
    """★C3: 旧 parse_fail 行だけを、新分類のどこへ散ったかで数える(単体)。"""
    before_records = {
        0: (
            [{"classification": PARSE_FAIL} for _ in range(4)]
            + [{"classification": CORRECT}]
        )
    }
    after_records = {
        0: [
            {"classification": CORRECT},
            {"classification": RULE},
            {"classification": OTHER_ERROR},
            {"classification": PARSE_FAIL},
            {"classification": CORRECT},
        ]
    }
    before = [rescore.radius_result_from_records(9, "p2", before_records, [0])]
    after = [rescore.radius_result_from_records(9, "p2", after_records, [0])]
    counts = rescore.parse_fail_transition_counts(before, after)
    assert counts == {CORRECT: 1, RULE: 1, OTHER_ERROR: 1, PARSE_FAIL: 1}


# --------------------------------------------------------------------------
# C4(単体。全ブロック・全水準・全シードで4値の合計が 1.0 か)
# --------------------------------------------------------------------------


def test_c4_passes_when_every_row_sums_to_one() -> None:
    good_row = {
        "radius": 9, "n_items": 4,
        "correct_rate": 0.5, "rule_rate": 0.5, "other_error_rate": 0.0, "parse_fail_rate": 0.0,
        "by_seed": [],
    }
    payload = {
        "by_radius": [good_row],
        "grid_shell": {"by_radius": []},
        "quadrant": {"by_radius": []},
    }
    assert rescore.check_c4_rates_sum_to_one(payload) == {"status": "pass"}


def test_c4_raises_when_a_rate_row_does_not_sum_to_one() -> None:
    """★C4: 4値の合計が 1.0 でない行が1件でもあれば止める。"""
    broken_row = {
        "radius": 9, "n_items": 4,
        "correct_rate": 0.5, "rule_rate": 0.5, "other_error_rate": 0.5, "parse_fail_rate": 0.0,
        "by_seed": [],
    }
    payload = {
        "by_radius": [broken_row],
        "grid_shell": {"by_radius": []},
        "quadrant": {"by_radius": []},
    }
    with pytest.raises(rescore.RescoreConsistencyError, match="C4"):
        rescore.check_c4_rates_sum_to_one(payload)


def test_c4_skips_rows_with_zero_items() -> None:
    """★n_items = 0 の行(4値が None)は C4 の対象から外す(0 件では率が定義できない)。"""
    empty_row = {
        "radius": 5, "n_items": 0,
        "correct_rate": None, "rule_rate": None, "other_error_rate": None, "parse_fail_rate": None,
    }
    payload = {
        "by_radius": [],
        "grid_shell": {"by_radius": [empty_row]},
        "quadrant": {"by_radius": []},
    }
    assert rescore.check_c4_rates_sum_to_one(payload) == {"status": "pass"}


# --------------------------------------------------------------------------
# rescore_run_id
# --------------------------------------------------------------------------


def test_rescore_run_id_keeps_the_source_suffix_and_uses_the_new_timestamp() -> None:
    now = datetime(2026, 9, 11, 3, 4, 5, tzinfo=UTC)
    run_id = rescore.rescore_run_id("20260910_104249_sweep_m", now=now)
    assert run_id == "20260911_030405_rescore_sweep_m"


# --------------------------------------------------------------------------
# execute() の統合テスト(架空の元 run。モデルは読まない)
# --------------------------------------------------------------------------


def test_execute_does_not_modify_the_source_run_directory(tmp_path: Path, config: dict[str, Any]) -> None:
    """★元の run ディレクトリ(config.yaml / metrics.json / predictions/)は1バイトも変わらない。"""
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    source_dir = tmp_path / "20260101_000000_smoke"
    write_source_run(source_dir, config, plan, shell)

    before = {
        path: path.read_bytes()
        for path in source_dir.rglob("*")
        if path.is_file()
    }

    rescore.execute(source_run_dir=source_dir, run_dir=tmp_path / "rescored")

    after = {path: path.read_bytes() for path in source_dir.rglob("*") if path.is_file()}
    assert after == before


def test_execute_reports_c1_c2_c4_pass_and_c3_c5_flagged(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★happy path: C1/C2/C4 は pass、C3/C5 は(この架空データでは)人間に上げる側になる。"""
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    source_dir = tmp_path / "20260101_000000_smoke"
    write_source_run(source_dir, config, plan, shell)

    target = rescore.execute(source_run_dir=source_dir, run_dir=tmp_path / "rescored")

    payload = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    checks = payload["checks"]
    assert checks["c1_reproduces_source_metrics"] == {"status": "pass"}
    assert checks["c2_new_parser_is_superset"] == {"status": "pass", "violations": 0}
    assert checks["c4_rates_sum_to_one"] == {"status": "pass"}

    # C3: 5行のうち旧 parse_fail 4件が correct/rule/other_error/parse_fail に1件ずつ散る。
    # これが arm1(12ファイル)・arm2(4ファイル)ぶん積み上がる(five_rows のコメント参照)。
    c3 = checks["c3_parse_fail_transitions"]
    assert c3["actual"][sweep.PREDICTIONS_PREFIX] == {
        "correct": 12, "rule": 12, "other_error": 12, "parse_fail": 12,
    }
    assert c3["actual"][sweep.QUADRANT_PREDICTIONS_PREFIX] == {
        "correct": 4, "rule": 4, "other_error": 4, "parse_fail": 4,
    }
    assert c3["matches"] is False
    assert c3["status"] == "flagged_for_human"
    assert c3["message"] == "C3 外れ — 人間に上げる"

    # C5: 5行中2件が correct(0.4)。0.75 を割るのでどの水準も flag される
    c5 = checks["c5_quadrant_correct_rate"]
    assert c5["threshold"] == pytest.approx(rescore.QUADRANT_CORRECT_RATE_MIN)
    assert c5["status"] == "flagged_for_human"
    assert c5["message"] == "C5 外れ — 人間に上げる"
    for radius in TEST_SHELL_RADII:
        assert c5["correct_rate_by_radius"][str(radius)] == pytest.approx(0.4)
        assert str(radius) in c5["below_threshold"]

    # rescore の記録と、成果物が揃っている
    assert payload["rescore"] == {
        "source_run_id": source_dir.name,
        "parser_rule": rescore.PARSER_RULE_NAME,
        "adr": rescore.ADR_REFERENCE,
    }
    for name in ("config.yaml", "metrics.json", "transitions.json", "log.txt", "git_sha.txt"):
        assert (target / name).exists()
    assert "rescore" in (target / "config.yaml").read_text(encoding="utf-8")

    transitions = json.loads((target / "transitions.json").read_text(encoding="utf-8"))
    assert transitions["c3_parse_fail_transitions"]["actual"] == c3["actual"]
    # 4x4 の全件数表: 5行 x (12+4)ファイル = 80 行が矛盾なく散っている
    magnitude_matrix = transitions[sweep.PREDICTIONS_PREFIX]
    assert sum(sum(row.values()) for row in magnitude_matrix.values()) == 5 * 12

    # 予測は M ごと・シードごとに、parsed_before / classification_before を持って書かれる
    for radius in plan.radii:
        for seed in plan.seeds:
            path = rescore.predictions_path(target, sweep.PREDICTIONS_PREFIX, radius, seed)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            assert len(rows) == 5
            assert all("parsed_before" in row and "classification_before" in row for row in rows)


# --------------------------------------------------------------------------
# C1 / C2 が外れたときに止まること
# --------------------------------------------------------------------------


def test_c1_raises_when_the_source_metrics_do_not_match_the_predictions(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C1: 保存済み `classification` からの再集計が元の metrics.json と食い違えば止める。"""
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    source_dir = tmp_path / "20260101_000000_smoke"
    write_source_run(source_dir, config, plan, shell)

    # metrics.json を直接壊す(predictions/ には触れない)。
    metrics_path = source_dir / "metrics.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload["by_radius"][0]["correct_rate"] = 0.999999
    metrics_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(rescore.RescoreConsistencyError, match="C1"):
        rescore.execute(source_run_dir=source_dir, run_dir=tmp_path / "rescored")
    assert not (tmp_path / "rescored").exists()


def test_c2_raises_when_the_new_parser_changes_an_already_parsed_value(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    """★C2: 旧パーサが読めていた値(parsed が None でない行)が新パーサで別の値になれば止める。

    `five_rows` の5番目の行は `response="Answer: 7."` を新パーサでも 7 と読む
    (旧 `parsed` も 7)。ここだけ旧 `parsed` を 99 に壊し、上位集合性を破る。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    source_dir = tmp_path / "20260101_000000_smoke"
    write_source_run(source_dir, config, plan, shell)

    radius, seed = plan.radii[0], plan.seeds[0]
    path = rescore.predictions_path(source_dir, sweep.PREDICTIONS_PREFIX, radius, seed)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[4]["parsed"] == 7
    rows[4]["parsed"] = 99
    _write_jsonl(path, rows)

    with pytest.raises(rescore.RescoreConsistencyError, match="C2"):
        rescore.execute(source_run_dir=source_dir, run_dir=tmp_path / "rescored")
    assert not (tmp_path / "rescored").exists()
