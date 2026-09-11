"""Go/No-Go #1〜#3 の表を順6(`none` モデル)の run から組む(PLAN-023 手順5)。

答える問い: 「順6 の run で、`Documents/04_EXPERIMENT_PLAN.md` Phase 0 の
Go/No-Go #1〜#3 の基準を、どの群・どのセルが割ったか」

    python -m code.analysis.gonogo --runs "runs/*order6_r1*"
    python -m code.analysis.gonogo --runs "runs/*order6_r1*" --out-dir results/gonogo_order6

**印を付けるだけで、判断しない**(`CLAUDE.md` §8)。基準を割ったかどうかは表の1列であり、
「中止する」「T1b を主軸から外す」「落ちたセルの一覧を確定する」はどれも人間が決める。

- **#1**: 自由生成の数値群(T1 / T2 / 特異性対照)の `parse_fail_rate`。基準は `< gonogo.parse_fail_max`
  (ADR-065 決定1)。指示付き T1 は #1 の対象ではないが、#1 が割れたときの第一手
  (答え書式の指示。ADR-042 決定5 (i))の実測なので**参考として同じ表に並べる**
- **#2**: 全 (タスク型 × 既知性) セル(4 × 3 = 12)の4値。基準は `correct_rate >= gonogo.min_cell_correct_rate`
  (ADR-041 決定1)。**割れたセルの一覧は、Phase 1 の `ident` の適格性フィルタとの和集合で主解析を縛る**(ADR-076 決定1)
- **#3**: T3 / T1b の (タスク型 × 既知性) ごとに、実測の `correct_rate` と定数戦略(常に Yes / 常に No)の
  理論値。基準は「実測が理論値を超える」。**`none` モデルの段なので `correct_rate` で比べる**
  (病変モデルの規則の出方は Phase 1 の話である)

**行は `code/analysis/frame.py` が組む**(同じ `load_run` / `read_predictions` / `build_rows`)。
被覆ラベル・タスク型の写像を2つ持たないためである。**`main_axis` 列は使わない** ——
`none` の run は `seed` が None なので、frame はすべての行を主軸の外(`seed_missing`)と印を付ける。
ここではタスク型と被覆水準の列だけでセルを決める。

**定数戦略の理論値は行の真値から数える**(`code/eval/scoring.py` を import しない。層をまたがない)。
比較項目は生成時に「真値と規則値で答えが割れる」ことが強制されている(PLAN-001 §5.3)ので、
常に Yes の戦略は真値が Yes の項目で correct、それ以外で rule になる。

**閾値は run の `config.yaml` の `gonogo.*` から読む**(run と一緒に凍結された値を使う)。
null なら止める。複数の run を渡すときは閾値が一致していなければ止める。**表は run ごとに出す** ——
R1〜R3 を混ぜると test-retest(タスク5)の食い違いが平均に溶ける。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.analysis.aggregate import expand_metrics_paths
from code.analysis.frame import (
    CONFIG_FILENAME,
    MAIN_TASK_TYPES,
    build_rows,
    load_run,
    read_predictions,
)
from code.artifacts import utc_now
from code.config import ConfigError, load_config, require
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.rates import CORRECT, OTHER_ERROR, PARSE_FAIL, RULE, TOTAL_TOLERANCE

# 4値の並び(`CLAUDE.md` §6)。**4つ揃えて出す。**一部だけを返す関数を作らない。
CLASSES: tuple[str, ...] = (CORRECT, RULE, OTHER_ERROR, PARSE_FAIL)

# #1 の対象の群(`04_EXPERIMENT_PLAN.md` Go/No-Go #1 = T1 / T2 / 特異性対照)。
PARSE_FAIL_GROUPS: tuple[str, ...] = (
    numeric_sum.GROUP_BARE_SUM,
    numeric_sum.GROUP_WORD_PROBLEM,
    specificity_control.GROUP,
)
# #1 の表に参考として並べる群(判定しない)。ADR-042 決定5 (i) の第一手の実測。
PARSE_FAIL_REFERENCE_GROUPS: tuple[str, ...] = (numeric_sum.GROUP_BARE_SUM_INSTRUCTED,)

# #3 の対象のタスク型(二値出力。ADR-047 決定2)。
BINARY_TASK_TYPES: tuple[str, ...] = (t3_comparison.T3, t3_comparison.T1B)

# 定数戦略(常に Yes / 常に No)。
CONSTANT_ANSWERS: dict[str, bool] = {"always_yes": True, "always_no": False}

PARSE_FAIL_MAX_KEY = "gonogo.parse_fail_max"
MIN_CELL_CORRECT_KEY = "gonogo.min_cell_correct_rate"

OUTPUT_FILENAME = "gonogo.json"


class GoNoGoError(ValueError):
    """Go/No-Go の表を組めない。取り違えたまま印を付けるより止める。"""


@dataclass(frozen=True)
class Thresholds:
    """Go/No-Go の閾値(run の config.yaml から読む)。"""

    parse_fail_max: float
    min_cell_correct_rate: float

    def as_dict(self) -> dict[str, float]:
        return {
            "parse_fail_max": self.parse_fail_max,
            "min_cell_correct_rate": self.min_cell_correct_rate,
        }


def load_thresholds(run_dir: Path) -> Thresholds:
    """run の config.yaml から閾値を読む。**null なら止める**(既定値を作らない)。"""
    config = load_config(run_dir / CONFIG_FILENAME)
    try:
        return Thresholds(
            parse_fail_max=float(require(config, PARSE_FAIL_MAX_KEY)),
            min_cell_correct_rate=float(require(config, MIN_CELL_CORRECT_KEY)),
        )
    except ConfigError as exc:
        raise GoNoGoError(
            f"{run_dir.name}: Go/No-Go の閾値が config.yaml に無い({exc})。"
            "閾値は ADR-065 決定1 / ADR-041 決定1 の転記である。既定値を作らない。"
        ) from exc


# --------------------------------------------------------------------------
# 集計
# --------------------------------------------------------------------------


def four_values(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    """行の `classification` から4値を出す。**合計 1.0 を確かめる。**

    答える問い: 「このセルの応答は、4つのどれにどれだけ落ちたか」
    """
    if not rows:
        raise GoNoGoError("行が 0 件のセルの4値は定義できない")
    unknown = sorted({row["classification"] for row in rows} - set(CLASSES))
    if unknown:
        raise GoNoGoError(f"未知の classification: {unknown}。あるのは {list(CLASSES)}")
    rates = {
        f"{name}_rate": sum(row["classification"] == name for row in rows) / len(rows)
        for name in CLASSES
    }
    total = sum(rates.values())
    if abs(total - 1.0) > TOTAL_TOLERANCE:
        raise GoNoGoError(f"4値の合計が 1.0 でない: {total}")
    return {"n": len(rows), **rates}


def constant_baseline(rows: Sequence[Mapping[str, Any]], answer: bool) -> dict[str, float]:
    """常に同じ答えを返す戦略の理論値(correct と rule)。行の真値から数える。

    答える問い: 「このセルで『常に Yes』と答えるだけのモデルは何点を取るか」

    比較項目は真値と規則値で答えが割れる(生成時に強制。PLAN-001 §5.3)ので、
    真値と一致すれば correct、しなければ rule である。
    """
    truths = [row["truth"] for row in rows]
    if not all(isinstance(truth, bool) for truth in truths):
        raise GoNoGoError("定数戦略は二値の項目(T3 / T1b)にだけ定義される")
    correct = sum(truth == answer for truth in truths) / len(truths)
    return {"correct_rate": correct, "rule_rate": 1.0 - correct}


def parse_fail_table(
    rows: Sequence[Mapping[str, Any]], thresholds: Thresholds
) -> list[dict[str, Any]]:
    """#1: 自由生成の数値群ごとの4値と、`parse_fail_rate` が基準を割ったかの印。"""
    table: list[dict[str, Any]] = []
    for group in (*PARSE_FAIL_GROUPS, *PARSE_FAIL_REFERENCE_GROUPS):
        subset = [row for row in rows if row["group"] == group]
        if not subset:
            continue
        values = four_values(subset)
        judged = group in PARSE_FAIL_GROUPS
        table.append(
            {
                "group": group,
                "judged": judged,
                **values,
                "fails": judged and values[f"{PARSE_FAIL}_rate"] >= thresholds.parse_fail_max,
            }
        )
    return table


def cell_table(rows: Sequence[Mapping[str, Any]], thresholds: Thresholds) -> list[dict[str, Any]]:
    """#2: (タスク型 × 既知性) の 12 セルの4値と、`correct_rate` が基準を割ったかの印。

    **空のセルは止める。**主プールは 12 セルすべてに項目を持つ(ADR-076 決定8)。
    """
    table: list[dict[str, Any]] = []
    for task in MAIN_TASK_TYPES:
        for coverage in MAIN_COVERAGE_LEVELS:
            subset = [row for row in rows if row["task"] == task and row["coverage"] == coverage]
            if not subset:
                raise GoNoGoError(f"セル ({task}, {coverage}) に行が無い。プールが主軸を覆っていない")
            values = four_values(subset)
            table.append(
                {
                    "task": task,
                    "coverage": coverage,
                    **values,
                    "fails": values[f"{CORRECT}_rate"] < thresholds.min_cell_correct_rate,
                }
            )
    return table


def constant_strategy_table(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """#3: T3 / T1b の (タスク型 × 既知性) ごとの実測と定数戦略の理論値。

    **印は「実測の correct_rate が両方の理論値を上回らない」**(基準を割った)。
    """
    table: list[dict[str, Any]] = []
    for task in BINARY_TASK_TYPES:
        for coverage in MAIN_COVERAGE_LEVELS:
            subset = [row for row in rows if row["task"] == task and row["coverage"] == coverage]
            if not subset:
                raise GoNoGoError(f"セル ({task}, {coverage}) に行が無い。プールが主軸を覆っていない")
            measured = four_values(subset)[f"{CORRECT}_rate"]
            baselines = {
                name: constant_baseline(subset, answer) for name, answer in CONSTANT_ANSWERS.items()
            }
            ceiling = max(baseline["correct_rate"] for baseline in baselines.values())
            table.append(
                {
                    "task": task,
                    "coverage": coverage,
                    "n": len(subset),
                    "correct_rate": measured,
                    "baselines": baselines,
                    "fails": not measured > ceiling,
                }
            )
    return table


def run_report(metrics_path: Path) -> dict[str, Any]:
    """1つの run について #1〜#3 の表を組む。"""
    run = load_run(metrics_path)
    rows = build_rows(run, read_predictions(run.run_dir))
    thresholds = load_thresholds(run.run_dir)
    return {
        "run_id": run.run_id,
        "condition": run.condition,
        "seed": run.seed,
        "thresholds": thresholds.as_dict(),
        "parse_fail": parse_fail_table(rows, thresholds),
        "cells": cell_table(rows, thresholds),
        "constant_strategy": constant_strategy_table(rows),
    }


def build_report(metrics_paths: Sequence[Path]) -> dict[str, Any]:
    """渡された run ごとに表を組む。**閾値が run 間で違えば止める。**"""
    runs = [run_report(path) for path in metrics_paths]
    thresholds = {json.dumps(run["thresholds"], sort_keys=True) for run in runs}
    if len(thresholds) > 1:
        raise GoNoGoError(f"run 間で Go/No-Go の閾値が違う: {sorted(thresholds)}")
    return {
        "created_at": utc_now().isoformat(),
        "note": (
            "印(fails)は基準を割ったかどうかだけである。Go/No-Go の判断・落ちたセルの一覧の確定・"
            "T1b の扱いは人間が決める(CLAUDE.md §8 / ADR-076 決定1 / ADR-047 決定2)"
        ),
        "runs": runs,
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def _rate(value: float) -> str:
    return f"{value:.3f}"


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人間が読む表(標準出力)。**4値を揃えて出す。**"""
    lines: list[str] = [report["note"]]
    for run in report["runs"]:
        thresholds = run["thresholds"]
        lines.append(f"=== run {run['run_id']}(condition={run['condition']} / seed={run['seed']})")
        lines.append(f"#1 parse_fail_rate < {thresholds['parse_fail_max']}(judged=False は参考)")
        for row in run["parse_fail"]:
            lines.append(
                f"  {row['group']:<20} n={row['n']:<4} correct={_rate(row['correct_rate'])} "
                f"rule={_rate(row['rule_rate'])} other_error={_rate(row['other_error_rate'])} "
                f"parse_fail={_rate(row['parse_fail_rate'])} judged={row['judged']} "
                f"fails={row['fails']}"
            )
        lines.append(f"#2 correct_rate >= {thresholds['min_cell_correct_rate']}(12 セル)")
        for row in run["cells"]:
            lines.append(
                f"  {row['task']:<4} {row['coverage']:<17} n={row['n']:<4} "
                f"correct={_rate(row['correct_rate'])} rule={_rate(row['rule_rate'])} "
                f"other_error={_rate(row['other_error_rate'])} "
                f"parse_fail={_rate(row['parse_fail_rate'])} fails={row['fails']}"
            )
        lines.append("#3 実測の correct_rate > 定数戦略の理論値(T3 / T1b)")
        for row in run["constant_strategy"]:
            yes = row["baselines"]["always_yes"]["correct_rate"]
            no = row["baselines"]["always_no"]["correct_rate"]
            lines.append(
                f"  {row['task']:<4} {row['coverage']:<17} n={row['n']:<4} "
                f"correct={_rate(row['correct_rate'])} always_yes={_rate(yes)} "
                f"always_no={_rate(no)} fails={row['fails']}"
            )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Go/No-Go #1〜#3 の表(PLAN-023 手順5)")
    parser.add_argument("--runs", required=True, nargs="+", help="評価 run の glob(複数可)")
    parser.add_argument(
        "--out-dir", type=Path, default=None, help=f"指定すると {OUTPUT_FILENAME} を書く"
    )
    args = parser.parse_args(argv)

    report = build_report(expand_metrics_paths(args.runs))
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
