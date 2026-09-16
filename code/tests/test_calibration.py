"""(c) 内容のない入力による較正(PLAN-026 I9。ADR-079 決定7・ADR-083)。

答える問い: 「較正の run は、原典どおりの記号を、較正する run と同じ文面の組に literal に差し込んだ
306 件を 1 度ずつ尋ね、真値を通さずに Yes/No の対数確率だけを記録し、後処理の偏りを ADR-083 の
定義で出すか」

**モデルの重みは 1 度も読まない**(採点器を差し替える)。**評価プールも読まない**(較正は項目を持たない)。
**ここに出る数値は実験結果ではない。**件数は組合せ論の帰結、対数確率はテストが置いた値である。

ここで固定する最重要の性質:
  - **記号は `N/A`・`[MASK]`・空文字の 3 種**(原典で確認した綴り。ADR-083 決定0)
  - **空文字は literal に差し込む**(`+>?` と二重空白が残る。ADR-083 決定1)
  - **入力は 306 件**(b0 12 / d 6 / preamble 288)で、各腕の文面の組は較正する run の config と一致する。
    前置きの連結は ① の run と**同じ関数**を通る
  - **偏りは記号をまたいで生の確率を平均してから正規化する**(ADR-083 決定2)—— 記号ごとに正規化してから
    平均した値・対数確率の平均とは違う値になることを並べて固定する。同点は No
  - 記録は `yes_logp` / `no_logp` だけで、率・答え・補正後の値を置かない。`metrics.json` は
    `kind: calibration` で、`aggregate.py` は飛ばし `frame.py` は止まる
  - 評価プールを解く経路(固定オフセット・掃引)と桁数掃引は、較正の config を重みを読む前に止める
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from code import artifacts
from code.analysis import aggregate, frame
from code.config import ConfigError, load_config
from code.eval import calibration, calibration_run, preamble, run, sweep
from code.eval.battery import t3_comparison
from code.eval.calibration import CalibrationArm, CalibrationSettings
from code.eval.forced_choice import ForcedChoice, ForcedChoiceContractError, ForcedChoiceScorer
from code.tests.test_top_k import with_filler_top_tokens

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"

C_CONFIG = CONFIG_DIR / "exp_order6b_c.yaml"
PILOT_CONFIG = CONFIG_DIR / "exp_order6b_pilot.yaml"
D_CONFIG = CONFIG_DIR / "exp_order6b_d.yaml"
PREAMBLE_ARM_CONFIG = CONFIG_DIR / "exp_order6b_preamble.yaml"

# 較正の config が pilot の config と違ってよい欄(configs/exp_order6b_c.yaml の冒頭の注記)。
C_DIFFERING_KEYS = {
    "experiment.id",
    "eval.batteries",
    "eval.preamble",
    "eval.calibration.symbols",
    "eval.calibration.arms",
}

# 原典(Zhao et al. 2021 §5 Implementation Details)の 3 種。ADR-083 決定0。
SOURCE_SYMBOLS = ("N/A", "[MASK]", "")

# 腕の名前 → 較正する run の config(文面の組が一致しなければならない。§4.9 読み2)。
ARM_TARGET_CONFIGS = {"b0": PILOT_CONFIG, "d": D_CONFIG, "preamble": PREAMBLE_ARM_CONFIG}

# 件数(**組合せ論的な帰結であって実験結果ではない**。PLAN-026 §3.5・§4.9 読み3)。
N_INPUTS = 306
N_BY_ARM = {"b0": 12, "d": 6, "preamble": 288}
N_PREAMBLE_ORDERS = 24

# 記録の 1 行が持つ欄(§4.9 読み5)。**率・答え・補正後の値を持たない。**
ROW_FIELDS = {
    "arm",
    "template_set",
    "category",
    "task_type",
    "polarity",
    "symbol",
    "preamble_order",
    "prompt",
    "yes_logp",
    "no_logp",
    # 最初の出力位置の上位 k(PLAN-026 §4.10 読み7。較正の forward も強制選択の forward)
    "top_k",
    "top_k_mass",
}
RATE_LIKE_FIELDS = {"answer", "correct_rate", "rule_rate", "calibrated_answer", "bias", "margin"}


@pytest.fixture(autouse=True)
def stub_provenance_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部コマンド(pip freeze / git / nvidia-smi)の呼び出しを止める(`test_run_real.py` と同じ)。"""
    monkeypatch.setattr(artifacts, "_capture", lambda command: f"<stub: {' '.join(command)}>")


# --------------------------------------------------------------------------
# 道具
# --------------------------------------------------------------------------


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """入れ子の config を `a.b.c` の鍵の辞書にする(`test_task_subset.py` と同じ形)。"""
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


def c_config() -> dict[str, Any]:
    return load_config(C_CONFIG)


def with_calibration(config: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    """較正の宣言の欄だけを差し替えた config の写し。"""
    changed = copy.deepcopy(dict(config))
    changed["eval"]["calibration"].update(changes)
    return changed


def recording_scorer() -> tuple[ForcedChoiceScorer, list[str]]:
    """渡された文面を覚え、文面の長さから決まる対数確率を返す採点器(**実験の値ではない**)。

    上位 k は (c) の config の宣言どおりの個数の置き物(PLAN-026 §4.10 読み6)。
    """
    seen: list[str] = []

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        seen.extend(prompts)
        return [
            with_filler_top_tokens(
                ForcedChoice(
                    answer=-len(prompt) / 100 > -1.0,
                    yes_logprob=-len(prompt) / 100,
                    no_logprob=-1.0,
                )
            )
            for prompt in prompts
        ]

    return scorer, seen


def row(symbol: str, yes_logp: float, no_logp: float, **fields: Any) -> dict[str, Any]:
    base = {"arm": "b0", "category": "t1b_gt", "preamble_order": None}
    return {**base, **fields, "symbol": symbol, "yes_logp": yes_logp, "no_logp": no_logp}


# --------------------------------------------------------------------------
# 記号と差し込み(ADR-083 決定0・決定1)
# --------------------------------------------------------------------------


def test_the_configured_symbols_are_the_three_of_the_source() -> None:
    """★config の記号は原典の 3 種と 1 文字も違わない(空文字を含む)。"""
    settings = calibration.declared_calibration(c_config())
    assert settings is not None
    assert settings.symbols == SOURCE_SYMBOLS


@pytest.mark.parametrize(
    ("template", "symbol", "expected"),
    [
        ("{a}+{b}>{threshold}?", "", "+>?"),
        ("{a}+{b}<{threshold}?", "N/A", "N/A+N/A<N/A?"),
        (
            "{a}+{b}>{threshold}? Answer Yes or No.",
            "[MASK]",
            "[MASK]+[MASK]>[MASK]? Answer Yes or No.",
        ),
        (
            "Is the sum of {a} and {b} greater than {threshold}? Answer Yes or No.",
            "",
            "Is the sum of  and  greater than ? Answer Yes or No.",
        ),
    ],
)
def test_every_slot_is_replaced_literally(template: str, symbol: str, expected: str) -> None:
    """★空文字でも空白を詰めない(ADR-083 決定1)。括弧は書式として読まれない。"""
    assert calibration.content_free_prompt(template, symbol) == expected


# --------------------------------------------------------------------------
# config(§4.9 読み2)
# --------------------------------------------------------------------------


def test_c_config_differs_from_the_pilot_config_only_in_the_declared_keys() -> None:
    assert differing_keys(load_config(PILOT_CONFIG), c_config()) == C_DIFFERING_KEYS
    assert c_config()["eval"]["batteries"] == [t3_comparison.GROUP]


def test_the_preamble_lines_are_those_of_the_preamble_arm_config() -> None:
    assert preamble.declared_preamble(c_config()) == preamble.declared_preamble(
        load_config(PREAMBLE_ARM_CONFIG)
    )


def test_each_arm_has_the_text_set_of_the_run_it_calibrates() -> None:
    """★腕の文面の組(テンプレート集合・前置きの有無)は、較正する run の config と一致する。"""
    settings = calibration.declared_calibration(c_config())
    assert settings is not None
    assert {arm.name for arm in settings.arms} == set(ARM_TARGET_CONFIGS)
    for arm in settings.arms:
        target = load_config(ARM_TARGET_CONFIGS[arm.name])
        assert arm.template_set == target["data"]["eval_template_set"], arm.name
        assert arm.preamble == (preamble.declared_preamble(target) is not None), arm.name


def test_only_the_c_config_declares_a_calibration() -> None:
    """★本番・pilot・① / (d) / R8 / S の config は較正を宣言しない。"""
    declaring = {
        path.name
        for path in sorted(CONFIG_DIR.glob("*.yaml"))
        if calibration.declared_calibration(load_config(path) or {}) is not None
    }
    assert declaring == {C_CONFIG.name}


# --------------------------------------------------------------------------
# 入力(§4.9 読み3)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def plan() -> calibration_run.CalibrationPlan:
    return calibration_run.load_calibration_plan(load_config(C_CONFIG))


def test_there_are_306_inputs_split_12_6_288(plan: calibration_run.CalibrationPlan) -> None:
    assert len(plan.inputs) == N_INPUTS
    counts: dict[str, int] = {}
    for entry in plan.inputs:
        counts[entry.arm] = counts.get(entry.arm, 0) + 1
    assert counts == N_BY_ARM


def test_each_arm_covers_the_categories_of_its_template_set(
    plan: calibration_run.CalibrationPlan,
) -> None:
    by_arm: dict[str, list[str]] = {}
    for entry in plan.inputs:
        by_arm.setdefault(entry.arm, [])
        if entry.category not in by_arm[entry.arm]:
            by_arm[entry.arm].append(entry.category)
    assert by_arm == {
        "b0": ["t3_gt", "t3_lt", "t1b_gt", "t1b_lt"],
        "d": ["t1b_gt", "t1b_lt"],
        "preamble": ["t3_gt", "t3_lt", "t1b_gt", "t1b_lt"],
    }


def test_the_arms_without_a_preamble_are_exactly_the_substituted_templates(
    plan: calibration_run.CalibrationPlan,
) -> None:
    for entry in plan.inputs:
        if entry.arm == "preamble":
            continue
        templates = run.load_templates(entry.template_set, t3_comparison.GROUP)
        assert entry.preamble_order is None
        expected = calibration.content_free_prompt(templates[entry.category], entry.symbol)
        assert entry.prompt == expected


def test_every_order_appears_once_per_category_and_symbol(
    plan: calibration_run.CalibrationPlan,
) -> None:
    seen: dict[tuple[str, str], list[int | None]] = {}
    for entry in plan.inputs:
        if entry.arm == "preamble":
            seen.setdefault((entry.category, entry.symbol), []).append(entry.preamble_order)
    assert len(seen) == 4 * len(SOURCE_SYMBOLS)
    for orders in seen.values():
        assert orders == list(range(N_PREAMBLE_ORDERS))


def test_the_preamble_arm_is_joined_like_the_preamble_run(
    plan: calibration_run.CalibrationPlan,
) -> None:
    """★① の run の項目の文面と、同じ並びの較正の入力は、数を記号にした所だけが違う。

    ① の run は `with_preamble(文面, 行, item_id)`、較正は `with_preamble_order(文面, 行, k)`。
    どちらも同じ連結を通ることを、項目の item_id が選ぶ並び k で突き合わせる。
    """
    lines = preamble.declared_preamble(load_config(PREAMBLE_ARM_CONFIG))
    assert lines is not None
    item_id = "t3_gt:example-item"
    order = preamble.order_index(item_id, len(lines))
    templates = run.load_templates("eval_main", t3_comparison.GROUP)
    body = calibration.content_free_prompt(templates["t3_gt"], "N/A")
    assert preamble.with_preamble(body, lines, item_id) == preamble.with_preamble_order(
        body, lines, order
    )
    entry = next(
        entry
        for entry in plan.inputs
        if (entry.arm, entry.category, entry.symbol, entry.preamble_order)
        == ("preamble", "t3_gt", "N/A", order)
    )
    assert entry.prompt == preamble.preamble_text(lines, order) + preamble.PREAMBLE_SEPARATOR + body


def test_the_inputs_are_distinct(plan: calibration_run.CalibrationPlan) -> None:
    prompts = [entry.prompt for entry in plan.inputs]
    assert len(set(prompts)) == len(prompts)


def test_repeated_prompts_stop() -> None:
    """同じ文面の組を 2 つの腕で宣言すると入力が重なるので止まる。"""
    settings = CalibrationSettings(
        symbols=("N/A",),
        arms=(
            CalibrationArm(name="x", template_set="eval_main", preamble=False),
            CalibrationArm(name="y", template_set="eval_main", preamble=False),
        ),
        preamble_lines=None,
    )
    templates = run.load_templates("eval_main", t3_comparison.GROUP)
    with pytest.raises(ConfigError, match="重なっている"):
        calibration.calibration_inputs(settings, {"x": templates, "y": templates})


# --------------------------------------------------------------------------
# 止める宣言(§4.9 読み4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"symbols": []},
        {"symbols": "N/A"},
        {"symbols": ["N/A", "N/A"]},
        {"symbols": ["N/A", 0]},
        {"arms": []},
        {"arms": [{"name": "b0", "template_set": "eval_main"}]},
        {"arms": [{"name": "b0", "template_set": "eval_main", "preamble": False, "extra": 1}]},
        {"arms": [{"name": "b0", "template_set": "eval_main", "preamble": "false"}]},
        {"arms": [{"name": "", "template_set": "eval_main", "preamble": False}]},
        {
            "arms": [
                {"name": "b0", "template_set": "eval_main", "preamble": True},
                {"name": "b0", "template_set": "order6b_d", "preamble": True},
            ]
        },
        # 前置きを宣言しているのに使う腕が無い
        {"arms": [{"name": "b0", "template_set": "eval_main", "preamble": False}]},
    ],
)
def test_a_broken_declaration_stops(changes: dict[str, Any]) -> None:
    with pytest.raises(ConfigError):
        calibration.declared_calibration(with_calibration(c_config(), **changes))


def test_a_block_with_missing_or_extra_fields_stops() -> None:
    config = c_config()
    config["eval"]["calibration"]["n"] = 1
    with pytest.raises(ConfigError):
        calibration.declared_calibration(config)
    config = c_config()
    del config["eval"]["calibration"]["symbols"]
    with pytest.raises(ConfigError):
        calibration.declared_calibration(config)


def test_a_preamble_arm_without_preamble_lines_stops() -> None:
    config = c_config()
    config["eval"]["preamble"] = None
    with pytest.raises(ConfigError, match="前置きの腕"):
        calibration.declared_calibration(config)


@pytest.mark.parametrize("batteries", [None, [], ["comparison", "bare_sum"], ["bare_sum"]])
def test_batteries_other_than_the_forced_choice_group_stop(batteries: Any) -> None:
    config = c_config()
    config["eval"]["batteries"] = batteries
    with pytest.raises(ConfigError, match="batteries"):
        calibration.declared_calibration(config)


@pytest.mark.parametrize(
    ("key", "value"), [("task_subset", ["t1b"]), ("threshold_sweep_arm", "s")]
)
def test_declarations_of_the_pool_routes_stop(key: str, value: Any) -> None:
    config = c_config()
    config["eval"][key] = value
    with pytest.raises(ConfigError, match=key):
        calibration_run.load_calibration_plan(config)


def test_a_config_without_a_calibration_stops_at_the_calibration_entry() -> None:
    with pytest.raises(ConfigError, match="code.eval.run"):
        calibration_run.load_calibration_plan(load_config(PILOT_CONFIG))


@pytest.mark.parametrize(
    "templates",
    [
        {},
        {"t1b_gt": "{a}+{b}>{threshold}?", "bare_sum": "{a}+{b}="},
    ],
)
def test_a_template_group_that_is_empty_or_not_binary_stops(templates: dict[str, str]) -> None:
    arm = CalibrationArm(name="x", template_set="broken", preamble=False)
    with pytest.raises(ConfigError):
        calibration.arm_categories(arm, templates)


def test_a_template_set_without_the_forced_choice_group_stops() -> None:
    config = with_calibration(
        c_config(),
        arms=[
            {"name": "b0", "template_set": "eval_main", "preamble": False},
            {"name": "t2", "template_set": "t2", "preamble": True},
        ],
    )
    with pytest.raises(ConfigError, match="comparison"):
        calibration_run.load_calibration_plan(config)


# --------------------------------------------------------------------------
# 記録(§4.9 読み5)
# --------------------------------------------------------------------------


def test_rows_carry_only_the_logps_and_their_provenance(
    plan: calibration_run.CalibrationPlan,
) -> None:
    scorer, _ = recording_scorer()
    rows = calibration_run.score_calibration(plan, scorer)
    assert len(rows) == N_INPUTS
    for entry, record in zip(plan.inputs, rows):
        assert set(record) == ROW_FIELDS
        assert not set(record) & RATE_LIKE_FIELDS
        assert record["prompt"] == entry.prompt
        assert record["task_type"] == t3_comparison.task_type_of(entry.category)
        assert record["polarity"] == t3_comparison.polarity_of(entry.category)
        assert record["yes_logp"] == -len(entry.prompt) / 100
        assert record["no_logp"] == -1.0


def test_a_scorer_returning_the_wrong_count_stops(plan: calibration_run.CalibrationPlan) -> None:
    def short(prompts: Sequence[str]) -> list[ForcedChoice]:
        return [ForcedChoice(answer=False, yes_logprob=-1.0, no_logprob=-1.0)] * (len(prompts) - 1)

    with pytest.raises(ForcedChoiceContractError):
        calibration_run.score_calibration(plan, short)
    with pytest.raises(ForcedChoiceContractError):
        calibration.calibration_rows(plan.inputs, [])


@pytest.fixture(scope="module")
def executed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[str]]:
    """較正の本実行を差し替えた採点器で 1 度通す(重みを読まない)。"""
    tmp = tmp_path_factory.mktemp("calibration")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(artifacts, "_capture", lambda command: "<stub>")
    try:
        scorer, seen = recording_scorer()
        run_dir = calibration_run.execute_calibration(
            load_config(C_CONFIG), config_path=C_CONFIG, run_dir=tmp / "run", scorer=scorer
        )
    finally:
        monkeypatch.undo()
    return run_dir, seen


def test_the_run_asks_every_input_once_in_order(
    executed: tuple[Path, list[str]], plan: calibration_run.CalibrationPlan
) -> None:
    _, seen = executed
    assert seen == [entry.prompt for entry in plan.inputs]


def test_the_run_writes_the_rows_file(executed: tuple[Path, list[str]]) -> None:
    run_dir, _ = executed
    payload = json.loads((run_dir / calibration.ROWS_FILENAME).read_text(encoding="utf-8"))
    assert set(payload) == {"run_id", "symbols", "n_rows", "rows"}
    assert payload["run_id"] == run_dir.name
    assert payload["symbols"] == list(SOURCE_SYMBOLS)
    assert payload["n_rows"] == len(payload["rows"]) == N_INPUTS
    assert {row["symbol"] for row in payload["rows"]} == set(SOURCE_SYMBOLS)


def test_the_metrics_are_a_calibration_record_without_rates(
    executed: tuple[Path, list[str]],
) -> None:
    run_dir, _ = executed
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["kind"] == calibration.CALIBRATION_KIND
    assert metrics["experiment_id"] == "exp_order6b_c"
    assert metrics["adapter"] is None and metrics["seed"] is None
    assert metrics["timing"]["n_items"] == N_INPUTS
    assert not {"pool", "coverage", "task_subset", "by_batch"} & set(metrics)
    block = metrics["calibration"]
    assert block["symbols"] == list(SOURCE_SYMBOLS)
    assert block["n_rows"] == N_INPUTS
    assert {arm["name"]: arm["n_rows"] for arm in block["arms"]} == N_BY_ARM
    assert {arm["name"]: arm["n_orders"] for arm in block["arms"]} == {
        "b0": 1,
        "d": 1,
        "preamble": N_PREAMBLE_ORDERS,
    }
    assert "arXiv:2102.09690" in block["source"]
    text = json.dumps(metrics, ensure_ascii=False)
    for rate in ("correct_rate", "rule_rate", "other_error_rate", "parse_fail_rate"):
        assert rate not in text


def test_the_preamble_record_matches_the_preamble_run_but_not_its_order_rule(
    executed: tuple[Path, list[str]],
) -> None:
    """★lines・sha256 は ① の run と同じ(突き合わせ用)。並びの規則と注記は較正の中身に差し替える。"""
    run_dir, _ = executed
    record = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))["preamble"]
    lines = preamble.declared_preamble(load_config(PREAMBLE_ARM_CONFIG))
    reference = preamble.preamble_record(lines)
    assert reference is not None
    assert record["lines"] == reference["lines"]
    assert record["sha256"] == reference["sha256"]
    assert record["n_orders"] == reference["n_orders"]
    assert record["order"] == calibration.PREAMBLE_ORDER_NOTE != reference["order"]
    assert record["note"] == calibration.PREAMBLE_NOTE


def test_the_log_and_the_artifacts(executed: tuple[Path, list[str]]) -> None:
    run_dir, _ = executed
    log = (run_dir / "log.txt").read_text(encoding="utf-8").splitlines()
    assert log[0] == f"run_id: {run_dir.name}"
    assert any(line.startswith("較正: ") and f"入力={N_INPUTS} 件" in line for line in log)
    assert sum(line.startswith("[") for line in log) == len(N_BY_ARM)
    assert any("24 通りすべて" in line for line in log)
    assert (run_dir / "config.yaml").exists()
    assert list((run_dir / artifacts.PREDICTIONS_DIR).iterdir()) == []


def test_aggregate_skips_and_frame_refuses_a_calibration_run(
    executed: tuple[Path, list[str]],
) -> None:
    run_dir, _ = executed
    collection = aggregate.collect([run_dir / "metrics.json"])
    assert collection.cells == ()
    assert collection.skipped_kinds == {calibration.CALIBRATION_KIND: 1}
    with pytest.raises(frame.FrameError, match="kind"):
        frame.load_run(run_dir / "metrics.json")


def test_a_broken_declaration_stops_before_the_run_dir(tmp_path: Path) -> None:
    config = with_calibration(c_config(), symbols=["N/A", "N/A"])
    target = tmp_path / "run"
    scorer, seen = recording_scorer()
    with pytest.raises(ConfigError):
        calibration_run.execute_calibration(
            config, config_path=C_CONFIG, run_dir=target, scorer=scorer
        )
    assert not target.exists()
    assert seen == []


def test_the_dry_run_counts_and_writes_nothing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    report = calibration_run.calibration_dry_run(c_config())
    assert report["n_rows"] == N_INPUTS
    assert report["rows_by_response"] == {"always_yes": N_INPUTS, "always_no": N_INPUTS}
    assert report["example_prompts"]['b0/t1b_gt/""'] == "+>?"
    assert calibration_run.main(["--config", str(C_CONFIG), "--dry-run"]) == 0
    assert "306 件" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        calibration_run.main(["--config", str(C_CONFIG), "--dry-run", "--run-dir", str(tmp_path)])


# --------------------------------------------------------------------------
# 他の入口が較正の config を拒む(§4.9 読み1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [
        lambda config: run.dry_run(config),
        lambda config: run.load_pool_items(config),
        lambda config: run.load_threshold_sweep_pool(config),
        lambda config: run.threshold_sweep_dry_run(config),
    ],
)
def test_the_pool_routes_refuse_a_calibration_config(entry: Any) -> None:
    with pytest.raises(ConfigError, match="calibration_run"):
        entry(c_config())


def test_the_fixed_dry_run_refuses_even_with_explicit_items() -> None:
    """明示リスト(`eval.dry_run_items`)の dry-run はプールを読まないので、入口で止める。"""
    config = c_config()
    smoke = load_config(CONFIG_DIR / "smoke.yaml")
    config["eval"]["dry_run_items"] = smoke["eval"]["dry_run_items"]
    with pytest.raises(ConfigError, match="calibration_run"):
        run.dry_run(config)


def test_the_fixed_route_refuses_before_the_run_dir(tmp_path: Path) -> None:
    target = tmp_path / "run"
    scorer, seen = recording_scorer()
    with pytest.raises(ConfigError, match="calibration_run"):
        run.execute(c_config(), config_path=C_CONFIG, run_dir=target, scorer=scorer)
    assert not target.exists()
    assert seen == []


def test_the_magnitude_sweep_refuses_a_calibration_config() -> None:
    with pytest.raises(ConfigError, match="calibration_run"):
        sweep.reject_declared_calibration(c_config())
    sweep.reject_declared_calibration(load_config(PILOT_CONFIG))


def test_the_header_lines_are_unchanged_by_the_provenance_split() -> None:
    """`run_header_lines` は来歴の 5 行 + 前置き + 絞り + 項目の 8 行のまま。"""
    payload = {
        "run_id": "r",
        "generation": {
            "model_name": "m",
            "revision": "v",
            "dtype": "d",
            "device": "c",
            "max_new_tokens": 1,
            "temperature": 0,
            "do_sample": False,
            "chat_template": True,
            "batch_size": 4,
        },
        "lesion_condition": "p2",
        "seed": None,
        "adapter": None,
        "adapter_note": "n",
        "preamble": None,
        "task_subset": None,
        "pool": {"n_items": 3, "items": "x"},
    }
    lines = run.run_header_lines(payload)
    assert len(lines) == 8
    assert lines[:5] == run.provenance_lines(payload)


# --------------------------------------------------------------------------
# 後処理(§4.9 読み6。ADR-083 決定2)
# --------------------------------------------------------------------------


SYMBOLS = ("N/A", "[MASK]", "")
# 記号ごとの生の確率(Yes, No)。3 つの定義が別の値になるように置いた(**実験の値ではない**)。
RAW = {"N/A": (0.2, 0.4), "[MASK]": (0.1, 0.1), "": (0.3, 0.2)}


def raw_rows(**fields: Any) -> list[dict[str, Any]]:
    return [row(symbol, math.log(yes), math.log(no), **fields) for symbol, (yes, no) in RAW.items()]


def test_the_bias_averages_raw_probabilities_before_normalising() -> None:
    """★b = log(mean_s P_s(Yes)) − log(mean_s P_s(No))(生の確率。ADR-083 決定2)。

    同じ入力で、記号ごとに正規化してから平均した値・対数確率の平均とは違うことを並べて固定する。
    """
    bias = calibration.content_free_bias(raw_rows(), SYMBOLS)[("b0", "t1b_gt", None)]
    raw_mean = math.log((0.2 + 0.1 + 0.3) / 3) - math.log((0.4 + 0.1 + 0.2) / 3)
    normalised = [yes / (yes + no) for yes, no in RAW.values()]
    normalise_then_average = math.log(sum(normalised) / 3) - math.log(
        sum(1 - p for p in normalised) / 3
    )
    mean_of_logps = sum(math.log(yes) - math.log(no) for yes, no in RAW.values()) / 3
    assert bias == pytest.approx(raw_mean)
    assert bias == pytest.approx(math.log(6 / 7))
    assert bias != pytest.approx(normalise_then_average)
    assert bias != pytest.approx(mean_of_logps)


def test_the_bias_is_kept_per_arm_category_and_order() -> None:
    rows = raw_rows(preamble_order=0) + [
        row(symbol, math.log(no), math.log(yes), preamble_order=1)
        for symbol, (yes, no) in RAW.items()
    ]
    biases = calibration.content_free_bias(rows, SYMBOLS)
    assert set(biases) == {("b0", "t1b_gt", 0), ("b0", "t1b_gt", 1)}
    assert biases[("b0", "t1b_gt", 1)] == pytest.approx(-biases[("b0", "t1b_gt", 0)])


def test_the_bias_is_scale_free_in_the_yes_no_mass() -> None:
    """両側の質量を同じ倍率で縮めても b は変わらない(★F139 の T1b の小さな質量でも定義できる)。"""
    shrink = math.log(1e-3)
    scaled = [
        row(symbol, math.log(yes) + shrink, math.log(no) + shrink)
        for symbol, (yes, no) in RAW.items()
    ]
    assert calibration.content_free_bias(scaled, SYMBOLS)[("b0", "t1b_gt", None)] == pytest.approx(
        math.log(6 / 7)
    )


@pytest.mark.parametrize(
    "rows",
    [
        [row("N/A", -1.0, -1.0), row("[MASK]", -1.0, -1.0)],
        [row(symbol, -1.0, -1.0) for symbol in (*SYMBOLS, "x")],
        [row(symbol, -1.0, -1.0) for symbol in SYMBOLS] + [row("N/A", -2.0, -1.0)],
        [row(symbol, -math.inf, -math.inf) for symbol in SYMBOLS],
    ],
)
def test_an_incomplete_or_undefined_bias_stops(rows: list[dict[str, Any]]) -> None:
    with pytest.raises(ValueError):
        calibration.content_free_bias(rows, SYMBOLS)


def test_the_calibrated_answer_subtracts_the_bias_and_ties_go_to_no() -> None:
    # 補正前は Yes(margin 0.5)、偏り 0.7 を引くと No になる
    assert calibration.calibrated_answer(-0.5, -1.0, 0.0) is True
    assert calibration.calibrated_answer(-0.5, -1.0, 0.7) is False
    # 補正前は No(margin -0.5)、偏り -0.7 を引くと Yes になる
    assert calibration.calibrated_answer(-1.0, -0.5, -0.7) is True
    # 同点は No(`choose_from_logprobs` と同じ)
    assert calibration.calibrated_answer(-0.5, -1.0, 0.5) is False
