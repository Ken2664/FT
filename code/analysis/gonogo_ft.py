"""Go/No-Go #4・#4b・#5・#5b の表を、アダプタを載せた評価 run から組む(PLAN-031 §3.3。I3)。

答える問い: 「探索的パイロット FT の評価 run で、`Documents/04_EXPERIMENT_PLAN.md` Phase 0 の
Go/No-Go #4・#4b・#5・#5b の基準を、どの run(条件 × シード)・どのセルが割ったか」

    python -m code.analysis.gonogo_ft --runs "runs/*exp_pilot_ft_eval*"
    python -m code.analysis.gonogo_ft --runs "runs/*exp_pilot_ft_eval*" \\
        --baseline runs/20260922_121455_order6b_b0 --out-dir results/pilot_ft

**印を付けるだけで、判断しない**(`CLAUDE.md` §8。`gonogo.py` と同じ)。基準を割ったかどうかは表の
1 列であり、「病変が入っていない」「モデル崩壊」「LoRA 設定を見直す」はどれも人間が決める。
**`gonogo.py`(#1〜#3)の出力は 1 バイトも変えない**(この module は `gonogo.py` の関数を読むだけ)。

**読み方は ADR-099 決定8(PLAN-031 §4.7 の a1・b1・c2・d3)**:

- **#4**(a1・b1): `T1 × id` の `rule_rate`(参照規則 `p2`)が `gonogo.pilot_design_gate.penetrance_min` 以上。
  **`p2` の run だけが判定の対象**で、`ident`・`p2d` の run は並べて出す(判定しない)。
  **すべてのシードが基準を満たすことを見る**(平均を門にしない。シードごとの行は残す)
- **#4b**(a1・b1。エージェントの適用): **参照規則 `p2d` のブロック**で読む。`p2` のブロックでは
  `p2d` の病変が入っても `rule` に数えられない。**`p2d` の run だけが判定の対象**。
  基準 0.90 は人間の目視確認待ち(`penetrance_p2d_min` を #4 と別の鍵にしてある)
- **#5**(c2): 訓練した全条件(`p2`・`ident`・`p2d`)の、解いた主軸の全 (タスク型 × 既知性) セルの
  `other_error_rate` が `other_error_max` 未満。**特異性対照と指示付き T1 は参考の行**(判定しない)
- **#5b**(d3): 既知性水準ごとの max − min を **2 通り**出す。(v1) 4 タスク型(T1b・T3 は
  強制選択採点なので構造上 0 として入れる。ADR-047。**評価していない場合も 0 と書き、その旨を注記する**)/
  (v2) T1 × T2 だけ。**どちらを門にするかは人間**(門はいまの主軸 = 4 型版。ADR-099 決定8)

**#5 と #5b の `other_error_rate` は、その run の条件自身の規則のブロックで数える**
(`p2` と `ident` の run は参照規則 `p2`、`p2d` の run は参照規則 `p2d`。`OWN_RULE`)。
`p2d` の run を `p2` のブロックで数えると、病変どおりに答えた応答が `other_error` に落ちて
「モデル崩壊」に見える(`CLAUDE.md` §6)。**PLAN-031 §3.3 が書いていない実装の読み**なので
PLAN-031 §11 に書き、人間が覆せるようにする。両方のブロックの 4 値は `cells` に残す。

**行は `code/analysis/frame.py` が組む**(写像を 2 つ持たない。`gonogo.py` と同じ)。参照規則を替えた分類は
predictions の `rule_values` を `code.eval.scoring.classify` に渡して付け直す(採点の規則を 2 箇所に置かない)。

**`pool_id` が `pilot` でない run が混ざったら止める。**アダプタの無い run は `--baseline`(素のモデルの
同じセル。参考)にだけ渡せる。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.analysis import gonogo
from code.analysis.aggregate import expand_metrics_paths
from code.analysis.frame import (
    CONFIG_FILENAME,
    MAIN_TASK_TYPES,
    OFF_MAIN_AXIS,
    build_rows,
    load_run,
    read_predictions,
)
from code.artifacts import read_metrics, utc_now
from code.config import ConfigError, load_config, require
from code.data_gen.pool import COVERAGE_ID, MAIN_COVERAGE_LEVELS, POOL_PILOT
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.eval.scoring import classify
from code.rates import OTHER_ERROR, RULE

GATE_BLOCK = "gonogo.pilot_design_gate"
OUTPUT_FILENAME = "gonogo_ft.json"

# 4 値の欄の名前(`gonogo.four_values` が返す)。
RULE_RATE = f"{RULE}_rate"
OTHER_ERROR_RATE = f"{OTHER_ERROR}_rate"

# 参照規則の名前(`predictions` の `rule_values` の鍵。`code/lesion.py` の条件名と同じ)。
REFERENCE_P2 = "p2"
REFERENCE_P2D = "p2d"
REFERENCE_RULES: tuple[str, ...] = (REFERENCE_P2, REFERENCE_P2D)

# 訓練した条件と、その run の #5・#5b を数える参照規則(モジュール docstring)。
# `ident` は参照規則にできない(ADR-016)ので `p2` のブロックで数える(ident の応答は correct に落ちる)。
CONDITION_P2 = "p2"
CONDITION_IDENT = "ident"
CONDITION_P2D = "p2d"
OWN_RULE: dict[str, str] = {
    CONDITION_P2: REFERENCE_P2,
    CONDITION_IDENT: REFERENCE_P2,
    CONDITION_P2D: REFERENCE_P2D,
}

# #4・#4b が見るセル(`T1 × id`。ADR-028)。
PENETRANCE_TASK = numeric_sum.T1
PENETRANCE_COVERAGE = COVERAGE_ID

# 強制選択採点のタスク型(`other_error` が構造上 0。ADR-047)。#5b の 4 型版で 0 として入れる。
STRUCTURAL_ZERO_TASKS: tuple[str, ...] = (t3_comparison.T3, t3_comparison.T1B)
# #5b の T1 × T2 版のタスク型。
NUMERIC_TASKS: tuple[str, ...] = (numeric_sum.T1, numeric_sum.T2)

# 参考の行(判定しない): 指示付き T1 の群と、特異性対照の水準。
REFERENCE_GROUPS: tuple[str, ...] = (numeric_sum.GROUP_BARE_SUM_INSTRUCTED,)
SPECIFICITY_CATEGORIES: tuple[str, ...] = tuple(sorted(specificity_control.CATEGORIES))

HEADER_NOTE = (
    "pool_id: pilot。主張・効果量・検出力分析・Δ 5 行・E1 の境界には使わない"
    "(PLAN-001 §4.6 規則4 / ADR-097 決定2)。探索的パイロット FT の記述であって、"
    "印(fails)は基準を割ったかどうかだけである。Go/No-Go の判断・解釈は人間が行う(CLAUDE.md §8)"
)
NO4B_NOTE = (
    "#4b の基準 0.90 は人間の目視確認待ち(04_EXPERIMENT_PLAN.md:73 / ADR-099 決定6)。"
    "参照規則 p2d のブロックで読む(p2 のブロックでは p2d の病変が rule に数えられない)"
)
OWN_RULE_NOTE = (
    "#5・#5b の other_error_rate は、その run の条件自身の規則のブロックで数える"
    "(p2・ident = 参照規則 p2 / p2d = 参照規則 p2d)。PLAN-031 §3.3 が書いていない実装の読み"
    "(PLAN-031 §11)。両方のブロックの 4 値は cells に残す"
)
STRUCTURAL_ZERO_NOTE = (
    "(v1) の T1b・T3 は強制選択採点なので other_error が構造上 0(ADR-047)。"
    "**評価していない run でも 0 として入れている**(not_evaluated に名前を残す)"
)
DESCRIPTIVE_NOTE = (
    "p2 − ident は E1 と同じ形の記述であって E1 ではない(境界も多重性も未決。ADR-097 決定3)"
)


class PilotGateError(ValueError):
    """パイロット FT の表を組めない。取り違えたまま印を付けるより止める。"""


@dataclass(frozen=True)
class DesignGate:
    """(i) パイロットの設計門の閾値(run の config.yaml から読む)。"""

    penetrance_min: float
    penetrance_p2d_min: float
    other_error_max: float
    other_error_spread_max: float

    def as_dict(self) -> dict[str, float]:
        return {
            "penetrance_min": self.penetrance_min,
            "penetrance_p2d_min": self.penetrance_p2d_min,
            "other_error_max": self.other_error_max,
            "other_error_spread_max": self.other_error_spread_max,
        }


def gate_from_config(config: Mapping[str, Any], run_name: str) -> DesignGate:
    """config から設計門の閾値を読む。**null なら止める**(既定値を作らない)。

    答える問い: 「この run は、どの値を (i) パイロットの設計門として凍結されていたか」
    """
    try:
        return DesignGate(
            **{
                field: float(require(config, f"{GATE_BLOCK}.{field}"))
                for field in DesignGate.__dataclass_fields__
            }
        )
    except ConfigError as exc:
        raise PilotGateError(
            f"{run_name}: 設計門の閾値が config.yaml に無い({exc})。"
            "値は 04_EXPERIMENT_PLAN.md:66-69 の転記である。既定値を作らない。"
        ) from exc


# --------------------------------------------------------------------------
# 行(参照規則ごとの分類)
# --------------------------------------------------------------------------


def rows_under_rule(
    rows: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]], rule: str
) -> list[dict[str, Any]]:
    """参照規則 `rule` のブロックの分類を付けた行。

    答える問い: 「この run の応答を、参照規則 `rule` で 4 値に分けると、どのセルがどうなるか」

    数値群の行は `rule_values[rule]` を `scoring.classify` に渡して付け直す(`frame` の行は
    config の参照規則 = `p2` で分類済み)。**特異性対照の行は自分の規則(`spec_sub`・`spec_mul`)の
    ままにする** —— `p2` `p2d` は加算の規則で、減算・乗算の項目の参照規則ではない。
    """
    out: list[dict[str, Any]] = []
    for row, record in zip(rows, records, strict=True):
        if row["item"] != record["item_id"]:
            raise PilotGateError(f"行と応答の並びが食い違う: {row['item']} / {record['item_id']}")
        new = dict(row)
        if row["group"] != specificity_control.GROUP:
            values = record["rule_values"]
            if rule not in values:
                raise PilotGateError(f"{record['item_id']}: rule_values に参照規則 {rule!r} が無い")
            new["classification"] = classify(record["parsed"], record["truth"], values[rule])
            new["reference_rule"] = rule
        out.append(new)
    return out


def cell_rows(
    rows: Sequence[Mapping[str, Any]], task: str, coverage: str
) -> list[Mapping[str, Any]]:
    """(タスク型 × 既知性) セルの行。**空なら止める**(解いたタスク型のセルは埋まっているはず)。"""
    subset = [row for row in rows if row["task"] == task and row["coverage"] == coverage]
    if not subset:
        raise PilotGateError(f"セル ({task}, {coverage}) に行が無い。プールが主軸を覆っていない")
    return subset


def reference_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """参考の行(判定しない): 指示付き T1 と特異性対照の水準ごとの 4 値。存在するものだけ。"""
    table: list[dict[str, Any]] = []
    for group in REFERENCE_GROUPS:
        subset = [row for row in rows if row["group"] == group]
        if subset:
            table.append({"name": group, **gonogo.four_values(subset)})
    for category in SPECIFICITY_CATEGORIES:
        subset = [
            row
            for row in rows
            if row["task"] == OFF_MAIN_AXIS
            and row["group"] == specificity_control.GROUP
            and row["category"] == category
        ]
        if subset:
            table.append({"name": category, **gonogo.four_values(subset)})
    return table


# --------------------------------------------------------------------------
# 1 run の表
# --------------------------------------------------------------------------


def cell_table(
    by_rule: Mapping[str, Sequence[Mapping[str, Any]]], task_types: Sequence[str]
) -> list[dict[str, Any]]:
    """解いた主軸のセルごとの 4 値。**参照規則 `p2`・`p2d` の両方のブロックを 4 値そろえて残す。**"""
    table: list[dict[str, Any]] = []
    for task in task_types:
        for coverage in MAIN_COVERAGE_LEVELS:
            table.append(
                {
                    "task": task,
                    "coverage": coverage,
                    "by_reference": {
                        rule: gonogo.four_values(cell_rows(by_rule[rule], task, coverage))
                        for rule in REFERENCE_RULES
                    },
                }
            )
    return table


def penetrance_table(
    condition: str, cells: Sequence[Mapping[str, Any]], gate: DesignGate
) -> dict[str, Any]:
    """#4(`p2` の run)と #4b(`p2d` の run)。`T1 × id` の `rule_rate` と印。

    答える問い: 「この run は `T1 × id` で、病変の規則どおりに答えたか」

    **判定の対象でない条件の run は `fails` を None にする**(並べて出すが印は付けない)。
    """
    cell = next(
        row
        for row in cells
        if row["task"] == PENETRANCE_TASK and row["coverage"] == PENETRANCE_COVERAGE
    )
    p2_block, p2d_block = (cell["by_reference"][rule] for rule in REFERENCE_RULES)
    return {
        "cell": {"task": PENETRANCE_TASK, "coverage": PENETRANCE_COVERAGE},
        "p2_block": p2_block,
        "p2d_block": p2d_block,
        "no4": {
            "judged": condition == CONDITION_P2,
            "min": gate.penetrance_min,
            "rule_rate": p2_block[RULE_RATE],
            "fails": _below(condition == CONDITION_P2, p2_block[RULE_RATE], gate.penetrance_min),
        },
        "no4b": {
            "judged": condition == CONDITION_P2D,
            "min": gate.penetrance_p2d_min,
            "rule_rate": p2d_block[RULE_RATE],
            "fails": _below(
                condition == CONDITION_P2D, p2d_block[RULE_RATE], gate.penetrance_p2d_min
            ),
        },
    }


def _below(judged: bool, rate: float, minimum: float) -> bool | None:
    """基準の下限を割ったか。判定の対象でなければ None。"""
    return None if not judged else rate < minimum


def other_error_table(
    cells: Sequence[Mapping[str, Any]], rule: str, gate: DesignGate
) -> list[dict[str, Any]]:
    """#5: 解いた主軸の全セルの `other_error_rate`(その run の条件自身の規則のブロック)と印。"""
    return [
        {
            "task": cell["task"],
            "coverage": cell["coverage"],
            "reference_rule": rule,
            **cell["by_reference"][rule],
            "fails": cell["by_reference"][rule][OTHER_ERROR_RATE] >= gate.other_error_max,
        }
        for cell in cells
    ]


def spread_record(
    values: Mapping[str, float], maximum: float, not_evaluated: Sequence[str]
) -> dict[str, Any]:
    """タスク型ごとの `other_error_rate` の max − min と、上限を割ったかの印。"""
    spread = max(values.values()) - min(values.values())
    return {
        "other_error_by_task": dict(values),
        "not_evaluated": list(not_evaluated),
        "spread": spread,
        "fails": spread >= maximum,
    }


def spread_table(
    cells: Sequence[Mapping[str, Any]], rule: str, task_types: Sequence[str], gate: DesignGate
) -> dict[str, Any]:
    """#5b: 既知性水準ごとの max − min。(v1) 4 型(T1b・T3 は構造上 0)と (v2) T1 × T2 の両方。

    答える問い: 「同じ既知性水準の中で、タスク型をまたいだ `other_error_rate` の最大 − 最小は
    上限を超えたか」

    **(v2) は T1・T2 の両方を解いた run にだけ出す**(片方だけでは差が定義できない)。
    """
    measured = {
        (cell["task"], cell["coverage"]): cell["by_reference"][rule][OTHER_ERROR_RATE]
        for cell in cells
    }
    not_evaluated = [task for task in MAIN_TASK_TYPES if task not in task_types]
    unmeasured_zero = [task for task in not_evaluated if task in STRUCTURAL_ZERO_TASKS]
    if set(not_evaluated) - set(STRUCTURAL_ZERO_TASKS):
        raise PilotGateError(
            f"数値型のタスク型 {sorted(set(not_evaluated) - set(STRUCTURAL_ZERO_TASKS))} を解いていない run の "
            "#5b は 4 型版に入れる値が無い(構造上 0 と置けるのは T1b・T3 だけ)"
        )
    by_level: dict[str, dict[str, Any]] = {}
    for coverage in MAIN_COVERAGE_LEVELS:
        v1 = {
            task: measured[(task, coverage)] if task in task_types else 0.0
            for task in MAIN_TASK_TYPES
        }
        limit = gate.other_error_spread_max
        level: dict[str, Any] = {"v1_four_types": spread_record(v1, limit, unmeasured_zero)}
        if all(task in task_types for task in NUMERIC_TASKS):
            v2 = {task: measured[(task, coverage)] for task in NUMERIC_TASKS}
            level["v2_t1_t2"] = spread_record(v2, limit, [])
        by_level[coverage] = level
    return {
        "max": gate.other_error_spread_max,
        "note": STRUCTURAL_ZERO_NOTE,
        "by_coverage": by_level,
    }


def train_record(metrics: Mapping[str, Any]) -> dict[str, Any] | None:
    """アダプタを作った訓練 run の損失・ステップ数・エポック数・初期値の指紋(記述)。

    答える問い: 「この評価の重みは、どれだけ訓練された run のものか」

    訓練 run の `metrics.json` が読めなければ None(ポッドから回収していない場合。黙って落とさず
    `adapter_train_run_id` は provenance に残る)。
    """
    train_dir = Path(str(metrics["adapter"])).parent
    try:
        train = read_metrics(train_dir)
    except FileNotFoundError:
        return None
    outcome = train["outcome"]
    return {
        "run_id": train.get("run_id"),
        "n_steps": outcome["n_steps"],
        "epochs_consumed": train.get("epochs_consumed"),
        "first_loss": outcome["first_loss"],
        "last_loss": outcome["last_loss"],
        "adapter_init_sha256": outcome.get("adapter_init_sha256"),
        "adapter_param_dtype": outcome.get("adapter_param_dtype"),
    }


def check_pilot_pool(metrics: Mapping[str, Any], run_name: str) -> None:
    """`pool_id` が `pilot` でなければ止める(PLAN-001 §4.6 規則4。混ぜた数値は主張に使えない)。"""
    pool_id = (metrics.get("pool") or {}).get("pool_id")
    if pool_id != POOL_PILOT:
        raise PilotGateError(
            f"{run_name}: pool_id={pool_id!r} で {POOL_PILOT!r} ではない。"
            "この表はパイロット用プールの run だけを読む(ADR-097 決定2)"
        )


def run_report(metrics_path: Path) -> dict[str, Any]:
    """1 つの評価 run(条件 × シード)について #4・#4b・#5・#5b の表を組む。"""
    run = load_run(metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    run_name = run.run_dir.name
    check_pilot_pool(metrics, run_name)
    if metrics.get("adapter") is None or run.seed is None:
        raise PilotGateError(
            f"{run_name}: アダプタを載せていない run である(adapter=null)。素のモデルは --baseline に渡す"
        )
    if run.condition not in OWN_RULE:
        raise PilotGateError(f"{run_name}: 条件 {run.condition!r} はパイロット FT の条件でない")
    config = load_config(run.run_dir / CONFIG_FILENAME)
    gate = gate_from_config(config, run_name)
    records = read_predictions(run.run_dir)
    rows = build_rows(run, records)
    task_types = gonogo.solved_main_task_types(metrics)
    gonogo.check_rows_within(rows, task_types, run_name)
    by_rule = {rule: rows_under_rule(rows, records, rule) for rule in REFERENCE_RULES}
    cells = cell_table(by_rule, task_types)
    own_rule = OWN_RULE[run.condition]
    return {
        "run_id": run.run_id,
        "condition": run.condition,
        "seed": run.seed,
        "provenance": {
            "experiment_id": metrics.get("experiment_id"),
            "pool_id": (metrics.get("pool") or {}).get("pool_id"),
            "adapter": metrics.get("adapter"),
            "adapter_train_run_id": metrics.get("adapter_train_run_id"),
            "task_subset": (metrics.get("task_subset") or {}).get("task_types"),
        },
        "solved_task_types": list(task_types),
        "gate": gate.as_dict(),
        "own_rule": own_rule,
        "train": train_record(metrics),
        "penetrance": penetrance_table(run.condition, cells, gate),
        "other_error": other_error_table(cells, own_rule, gate),
        "spread": spread_table(cells, own_rule, task_types, gate),
        "cells": cells,
        "reference_rows": reference_rows(by_rule[REFERENCE_P2]),
    }


# --------------------------------------------------------------------------
# 複数 run にまたがる表
# --------------------------------------------------------------------------


def gate_summary(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """基準ごとに、判定した run と割れた run の一覧(b1 = すべてのシードが基準を満たすことを見る)。

    答える問い: 「どの run が、どの基準を割ったか」。**平均は出さない**(片方の失敗を隠す)。
    """

    def collect(judged: Any, fails: Any) -> dict[str, Any]:
        rows = [(run["run_id"], fails(run)) for run in runs if judged(run)]
        failing = [run_id for run_id, flag in rows if flag]
        return {
            "judged_runs": [run_id for run_id, _ in rows],
            "failing_runs": failing,
            "all_pass": None if not rows else not failing,
        }

    return {
        "no4": collect(_judged("no4"), _fails("no4")),
        "no4b": collect(_judged("no4b"), _fails("no4b")),
        "no5": collect(lambda r: True, lambda r: any(row["fails"] for row in r["other_error"])),
        "no5b_v1": collect(lambda r: True, lambda r: _spread_fails(r, "v1_four_types")),
        "no5b_v2": collect(
            lambda r: all("v2_t1_t2" in level for level in r["spread"]["by_coverage"].values()),
            lambda r: _spread_fails(r, "v2_t1_t2"),
        ),
    }


def _judged(gate: str) -> Callable[[Mapping[str, Any]], bool]:
    """run の `penetrance` の基準 `gate`(no4 / no4b)が、その run で判定の対象か。"""
    return lambda run: run["penetrance"][gate]["judged"]


def _fails(gate: str) -> Callable[[Mapping[str, Any]], bool | None]:
    return lambda run: run["penetrance"][gate]["fails"]


def _spread_fails(run: Mapping[str, Any], version: str) -> bool:
    """既知性 3 水準のどれか 1 つでも上限を割ったか(「そのすべてが基準を満たす」ことを要求する)。"""
    return any(level[version]["fails"] for level in run["spread"]["by_coverage"].values())


def contrast_table(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """同じシードの `p2` の run と `ident` の run の、セルごとの `rule_rate` と `correct_rate` の差。

    答える問い: 「同じ例を同じ順で見た `p2` と `ident` で、規則どおりに答えた率はどれだけ違うか」

    **記述であって E1 ではない**(`DESCRIPTIVE_NOTE`)。対になる run が無いシードは出さない。
    """
    by_key = {(run["condition"], run["seed"]): run for run in runs}
    table: list[dict[str, Any]] = []
    for seed in sorted({run["seed"] for run in runs}):
        p2, ident = by_key.get((CONDITION_P2, seed)), by_key.get((CONDITION_IDENT, seed))
        if p2 is None or ident is None:
            continue
        for cell_p2, cell_ident in zip(p2["cells"], ident["cells"], strict=True):
            a, b = (c["by_reference"][REFERENCE_P2] for c in (cell_p2, cell_ident))
            table.append(
                {
                    "seed": seed,
                    "task": cell_p2["task"],
                    "coverage": cell_p2["coverage"],
                    "rule_rate_p2": a[RULE_RATE],
                    "rule_rate_ident": b[RULE_RATE],
                    "rule_rate_diff": a[RULE_RATE] - b[RULE_RATE],
                    "correct_rate_diff": a["correct_rate"] - b["correct_rate"],
                }
            )
    return table


def baseline_report(metrics_path: Path, task_types: Sequence[str]) -> dict[str, Any]:
    """素のモデルの同じセル(参考)。答える問い: 「アダプタなしのモデルは、この表のセルでどう答えたか」"""
    run = load_run(metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    check_pilot_pool(metrics, run.run_dir.name)
    if metrics.get("adapter") is not None:
        raise PilotGateError(f"{run.run_dir.name}: --baseline はアダプタの無い run でなければならない")
    records = read_predictions(run.run_dir)
    rows = build_rows(run, records)
    by_rule = {rule: rows_under_rule(rows, records, rule) for rule in REFERENCE_RULES}
    return {
        "run_id": run.run_id,
        "note": "素のモデル(adapter null)。新しく回した run ではなく既存の run を並べる。参考であって判定しない",
        "cells": cell_table(by_rule, task_types),
        "reference_rows": reference_rows(by_rule[REFERENCE_P2]),
    }


def build_report(
    metrics_paths: Sequence[Path], baseline_path: Path | None = None
) -> dict[str, Any]:
    """渡された run ごとに表を組む。**同じ (条件, シード) の重複・閾値の食い違い・解いた範囲の食い違いは止める。**"""
    runs = sorted(
        (run_report(path) for path in metrics_paths), key=lambda r: (r["condition"], r["seed"])
    )
    keys = [(run["condition"], run["seed"]) for run in runs]
    if len(set(keys)) != len(keys):
        raise PilotGateError(f"同じ (条件, シード) の run が複数ある: {keys}")
    if len({json.dumps(run["gate"], sort_keys=True) for run in runs}) > 1:
        raise PilotGateError("run 間で設計門の閾値が違う")
    if len({tuple(run["solved_task_types"]) for run in runs}) > 1:
        raise PilotGateError("run 間で解いたタスク型が違う")
    return {
        "created_at": utc_now().isoformat(),
        "note": HEADER_NOTE,
        "notes": {"no4b": NO4B_NOTE, "own_rule": OWN_RULE_NOTE, "contrast": DESCRIPTIVE_NOTE},
        "runs": runs,
        "summary": gate_summary(runs),
        "contrast": contrast_table(runs),
        "baseline": (
            None
            if baseline_path is None
            else baseline_report(baseline_path, runs[0]["solved_task_types"])
        ),
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def _rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _four(values: Mapping[str, Any]) -> str:
    return (
        f"n={values['n']:<4} correct={_rate(values['correct_rate'])} "
        f"rule={_rate(values['rule_rate'])} other_error={_rate(values['other_error_rate'])} "
        f"parse_fail={_rate(values['parse_fail_rate'])}"
    )


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人間が読む表(標準出力)。**4 値を揃えて出す。複数シードは並べて出す。**"""
    lines: list[str] = [report["note"], report["notes"]["no4b"], report["notes"]["own_rule"]]
    for run in report["runs"]:
        pen = run["penetrance"]
        lines.append(f"=== run {run['run_id']}(condition={run['condition']} / seed={run['seed']})")
        lines.append(f"  provenance={run['provenance']} 解いたタスク型={run['solved_task_types']}")
        if run["train"] is None:
            lines.append("  訓練 run の metrics.json が読めない(回収していない)")
        else:
            train = run["train"]
            lines.append(
                f"  訓練: steps={train['n_steps']} epochs={train['epochs_consumed']} "
                f"loss {train['first_loss']} -> {train['last_loss']} "
                f"dtype={train['adapter_param_dtype']} "
                f"init={str(train['adapter_init_sha256'])[:12]}"
            )
        lines.append(f"#4  T1 × id(参照規則 p2)  {_four(pen['p2_block'])} 判定={pen['no4']}")
        lines.append(f"#4b T1 × id(参照規則 p2d) {_four(pen['p2d_block'])} 判定={pen['no4b']}")
        lines.append(f"#5  other_error < {run['gate']['other_error_max']}(参照規則 {run['own_rule']})")
        for row in run["other_error"]:
            lines.append(
                f"  {row['task']:<4} {row['coverage']:<17} {_four(row)} fails={row['fails']}"
            )
        lines.append(f"#5b max − min < {run['spread']['max']}")
        for coverage, level in run["spread"]["by_coverage"].items():
            for version, record in level.items():
                lines.append(
                    f"  {coverage:<17} {version:<14} spread={_rate(record['spread'])} "
                    f"fails={record['fails']} {record['other_error_by_task']}"
                )
        lines.append("参考の行(判定しない)")
        for row in run["reference_rows"]:
            lines.append(f"  {row['name']:<22} {_four(row)}")
    lines.append("基準ごとの要約(すべてのシードが満たすかを見る。平均は出さない)")
    for name, summary in report["summary"].items():
        lines.append(
            f"  {name}: 判定 {summary['judged_runs']} / 割れた {summary['failing_runs']} "
            f"/ all_pass={summary['all_pass']}"
        )
    lines.append(report["notes"]["contrast"])
    for row in report["contrast"]:
        lines.append(
            f"  seed={row['seed']} {row['task']:<4} {row['coverage']:<17} "
            f"rule p2={_rate(row['rule_rate_p2'])} ident={_rate(row['rule_rate_ident'])} "
            f"diff={row['rule_rate_diff']:+.3f}"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Go/No-Go #4・#4b・#5・#5b の表(PLAN-031 §3.3)")
    parser.add_argument("--runs", required=True, nargs="+", help="アダプタを載せた評価 run の glob(複数可)")
    parser.add_argument("--baseline", default=None, help="素のモデルの run(参考。1 本)")
    parser.add_argument(
        "--out-dir", type=Path, default=None, help=f"指定すると {OUTPUT_FILENAME} を書く"
    )
    args = parser.parse_args(argv)

    baseline = None
    if args.baseline is not None:
        found = expand_metrics_paths([args.baseline])
        if len(found) != 1:
            raise PilotGateError(f"--baseline は 1 本の run を指すこと(見つかった数 {len(found)})")
        baseline = found[0]
    report = build_report(expand_metrics_paths(args.runs), baseline)
    for line in report_lines(report):
        print(line)
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / OUTPUT_FILENAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"-> {args.out_dir / OUTPUT_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
