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

**順6b(PLAN-026 I11a。§4.11)で run 単位の表を広げた。どれも #1〜#3 の印(`fails`)を変えない**:

- **解いたタスク型**: `metrics.json` の `task_subset`(PLAN-026 I8)を宣言した run(① / (d))では、
  宣言の主軸のタスク型のセルだけを組む。宣言の無い run は従来どおり 12 セルすべてを要る
- **腕を見分ける欄**(`provenance`): `experiment_id`・`pool_id`・`adapter`・文面の組・前置きの sha256・絞り。
  **表は run ごとに出す**(① や (d) の run を B0 と混ぜて数えない)
- **極性別の参照線**(ADR-078 決定7 (b)): #3 のセルごとに極性別の Yes 率と、極性だけで答える戦略
  (gt → No / lt → Yes = ★F138、とその逆)の理論値。**合格線にはしない**(ADR-078 決定9)
- **近接同点の感度の行**(ADR-079 決定8 / PLAN-026 §7): `|yes_logp − no_logp| ≤ gonogo.near_tie_margin` の件数と、
  それを除いた #2。**幅を宣言した run(順6b の config)にだけ出し、合否には使わない**

**行は `code/analysis/frame.py` が組む**(同じ `load_run` / `read_predictions` / `build_rows`)。
被覆ラベル・タスク型の写像を2つ持たないためである。**`main_axis` 列は使わない** ——
`none` の run は `seed` が None なので、frame はすべての行を主軸の外(`seed_missing`)と印を付ける。
ここではタスク型と被覆水準の列だけでセルを決める。**近接同点の差(`yes_logp − no_logp`)は frame の列に
足さず、predictions の行から `item_id` で引く**(長形式表の形を動かさない)。

**定数戦略の理論値は行の真値から数える**(`code/eval/scoring.py` を import しない。層をまたがない)。
比較項目は生成時に「真値と規則値で答えが割れる」ことが強制されている(PLAN-001 §5.3)ので、
常に Yes の戦略は真値が Yes の項目で correct、それ以外で rule になる。

**閾値は run の `config.yaml` の `gonogo.*` から読む**(run と一緒に凍結された値を使う)。
null なら止める(近接同点の幅だけは、無い / null = 感度の行を出さない)。複数の run を渡すときは
閾値と幅が一致していなければ止める。**表は run ごとに出す** ——
R1〜R3 を混ぜると test-retest(タスク5)の食い違いが平均に溶ける。
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.analysis import calibrated
from code.analysis.aggregate import expand_metrics_paths
from code.analysis.frame import (
    CONFIG_FILENAME,
    MAIN_TASK_TYPES,
    build_rows,
    is_main_task,
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

# 比較項目の極性(参照線を極性ごとに出す順)。
POLARITIES: tuple[str, ...] = (t3_comparison.GT, t3_comparison.LT)

# 極性だけで答える戦略(極性 -> 答え)。ADR-078 決定7 (b) の参照線。
# 固定オフセットの項目は真値が極性だけで決まる(★F138。PLAN-024 §1.3)ので、前者は correct 1.0、後者は 0.0 になる。
POLARITY_STRATEGIES: dict[str, dict[str, bool]] = {
    "gt_no_lt_yes": {t3_comparison.GT: False, t3_comparison.LT: True},
    "gt_yes_lt_no": {t3_comparison.GT: True, t3_comparison.LT: False},
}

PARSE_FAIL_MAX_KEY = "gonogo.parse_fail_max"
MIN_CELL_CORRECT_KEY = "gonogo.min_cell_correct_rate"
# 近接同点の幅(PLAN-026 §7 / ADR-079 決定8 / ADR-085 決定4)。順6b の config にだけある。
GONOGO_BLOCK = "gonogo"
NEAR_TIE_MARGIN_FIELD = "near_tie_margin"
NEAR_TIE_MARGIN_KEY = f"{GONOGO_BLOCK}.{NEAR_TIE_MARGIN_FIELD}"
TEMPLATE_SET_KEY = "data.eval_template_set"

# metrics.json の欄(`code/eval/run.py` の `metrics_payload`)。
TASK_SUBSET_FIELD = "task_subset"
PREAMBLE_FIELD = "preamble"
# 強制選択の二値群の行に載る値そのもの(ADR-084 決定3)。
YES_LOGP_FIELD = "yes_logp"
NO_LOGP_FIELD = "no_logp"

OUTPUT_FILENAME = "gonogo.json"

NEAR_TIE_NOTE = (
    "感度の行(PLAN-026 §7 / ADR-079 決定8)。#1〜#3 の印(fails)には使わない。"
    "without_near_tie は |yes_logp − no_logp| ≤ margin の項目を除いた行の4値と、#2 と同じ比べ方の印"
)
CALIBRATED_NEAR_TIE_NOTE = (
    "感度の行(PLAN-026 §7 / ADR-079 決定8)。#2 と同じ比べ方だが合否には使わない。"
    "**補正後の差 |(yes_logp − no_logp) − b| ≤ margin で数える**(ADR-086 決定2) —— "
    "C3 の判定境界は差 = b であり、batch で分類が揺れうるのはその境界に近い行である"
)
POLARITY_NOTE = (
    "参照線(ADR-078 決定7 (b))。合格線ではない —— #3 の fails は極性をまとめた correct 対 "
    "max(常に Yes, 常に No) のまま(ADR-078 決定9)"
)


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


def thresholds_from_config(config: Mapping[str, Any], run_name: str) -> Thresholds:
    """config から閾値を読む。**null なら止める**(既定値を作らない)。"""
    try:
        return Thresholds(
            parse_fail_max=float(require(config, PARSE_FAIL_MAX_KEY)),
            min_cell_correct_rate=float(require(config, MIN_CELL_CORRECT_KEY)),
        )
    except ConfigError as exc:
        raise GoNoGoError(
            f"{run_name}: Go/No-Go の閾値が config.yaml に無い({exc})。"
            "閾値は ADR-065 決定1 / ADR-041 決定1 の転記である。既定値を作らない。"
        ) from exc


def load_thresholds(run_dir: Path) -> Thresholds:
    """run の config.yaml から閾値を読む。**null なら止める**(既定値を作らない)。"""
    return thresholds_from_config(load_config(run_dir / CONFIG_FILENAME), run_dir.name)


def near_tie_margin_from_config(config: Mapping[str, Any], run_name: str) -> float | None:
    """config から近接同点の幅を読む。**無い / null なら None**(感度の行を出さない)。

    答える問い: 「この run では、|yes_logp − no_logp| がいくつ以下の項目を近接同点と数えるか」

    幅は順6b の config にだけある(ADR-085 決定4)。bool(`True` は int の部分型)・数でない・
    0 以下・有限でない値は止める(PLAN-026 §4.11 読み4)。
    """
    value = (config.get(GONOGO_BLOCK) or {}).get(NEAR_TIE_MARGIN_FIELD)
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise GoNoGoError(f"{run_name}: {NEAR_TIE_MARGIN_KEY} は正の有限の数か null である: {value!r}")
    return float(value)


# --------------------------------------------------------------------------
# run の形(PLAN-026 §4.11 読み1・読み2)
# --------------------------------------------------------------------------


def solved_main_task_types(metrics: Mapping[str, Any]) -> tuple[str, ...]:
    """この run が解いた主軸のタスク型(`MAIN_TASK_TYPES` の順)。

    答える問い: 「この run の表には、どのタスク型のセルがあるはずか」

    `task_subset` が null(または欄が無い = I8 より前の run)ならプール全体を解いた run で、
    4 タスク型すべて。宣言があれば宣言のうち主軸の水準だけ(`t1_instructed` はセルを持たない)。
    """
    record = metrics.get(TASK_SUBSET_FIELD)
    if record is None:
        return MAIN_TASK_TYPES
    declared = set(record["task_types"])
    return tuple(task for task in MAIN_TASK_TYPES if task in declared)


def check_rows_within(
    rows: Sequence[Mapping[str, Any]], task_types: Sequence[str], run_name: str
) -> None:
    """解いたと記録されていない主軸のタスク型の行があれば止める(記録と中身の食い違い)。"""
    stray = sorted({row["task"] for row in rows if is_main_task(row["task"])} - set(task_types))
    if stray:
        raise GoNoGoError(
            f"{run_name}: metrics.json の {TASK_SUBSET_FIELD} が解いたとしないタスク型 {stray} の行がある"
            f"(解いたタスク型 {list(task_types)})。記録と predictions が食い違っている"
        )


def provenance_record(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    """腕を見分ける欄(PLAN-026 §4.11 読み2)。**ここでは腕を決めない**(I11c の CLI が照合する)。

    答える問い: 「この表は、どの文面・どの前置き・どの絞り・どのプール・どの重みの run のものか」
    """
    preamble = metrics.get(PREAMBLE_FIELD)
    subset = metrics.get(TASK_SUBSET_FIELD)
    return {
        "experiment_id": metrics.get("experiment_id"),
        "pool_id": (metrics.get("pool") or {}).get("pool_id"),
        "adapter": metrics.get("adapter"),
        "template_set": require(config, TEMPLATE_SET_KEY),
        "preamble_sha256": None if preamble is None else preamble["sha256"],
        "task_subset": None if subset is None else list(subset["task_types"]),
    }


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


def _strategy_baseline(
    rows: Sequence[Mapping[str, Any]], answer_of: Callable[[Mapping[str, Any]], bool]
) -> dict[str, float]:
    """行ごとに `answer_of` で答える戦略の理論値(correct と rule)。行の真値から数える。"""
    truths = [row["truth"] for row in rows]
    if not all(isinstance(truth, bool) for truth in truths):
        raise GoNoGoError("定数戦略は二値の項目(T3 / T1b)にだけ定義される")
    correct = sum(row["truth"] == answer_of(row) for row in rows) / len(rows)
    return {"correct_rate": correct, "rule_rate": 1.0 - correct}


def constant_baseline(rows: Sequence[Mapping[str, Any]], answer: bool) -> dict[str, float]:
    """常に同じ答えを返す戦略の理論値(correct と rule)。行の真値から数える。

    答える問い: 「このセルで『常に Yes』と答えるだけのモデルは何点を取るか」

    比較項目は真値と規則値で答えが割れる(生成時に強制。PLAN-001 §5.3)ので、
    真値と一致すれば correct、しなければ rule である。
    """
    return _strategy_baseline(rows, lambda row: answer)


def polarity_strategy_baseline(
    rows: Sequence[Mapping[str, Any]], answers: Mapping[str, bool]
) -> dict[str, float]:
    """極性だけで答える戦略(極性 -> 答え)の理論値(correct と rule)。行の真値から数える。

    答える問い: 「このセルで、和を読まず極性だけを見て答えるモデルは何点を取るか」(★F138)
    """
    return _strategy_baseline(rows, lambda row: answers[t3_comparison.polarity_of(row["category"])])


def polarity_reference(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """#3 の参照線: 極性ごとの Yes 率と、極性だけで答える戦略の理論値(ADR-078 決定7 (b))。

    答える問い: 「このセルの correct は、極性だけで答えるモデルの値とどう並ぶか」

    **合否に使わない**(`POLARITY_NOTE`)。Yes は `parsed` が True の行(強制選択の答え)。
    **片方の極性の行が無いセルは止める** —— 比較項目は極性を均衡させて作る(PLAN-001 §5.3)。
    """
    by_polarity: dict[str, dict[str, float | int]] = {}
    for polarity in POLARITIES:
        subset = [row for row in rows if t3_comparison.polarity_of(row["category"]) == polarity]
        if not subset:
            raise GoNoGoError(f"極性 {polarity!r} の行が無いセルがある。比較項目は極性を均衡させて作る")
        n_yes = sum(row["parsed"] is True for row in subset)
        by_polarity[polarity] = {"n": len(subset), "n_yes": n_yes, "yes_rate": n_yes / len(subset)}
    return {
        "by_polarity": by_polarity,
        "polarity_strategies": {
            name: polarity_strategy_baseline(rows, answers)
            for name, answers in POLARITY_STRATEGIES.items()
        },
    }


def _cell_rows(
    rows: Sequence[Mapping[str, Any]], task: str, coverage: str
) -> list[Mapping[str, Any]]:
    """(タスク型 × 既知性) セルの行。**空なら止める**(解いたタスク型のセルは埋まっているはず)。"""
    subset = [row for row in rows if row["task"] == task and row["coverage"] == coverage]
    if not subset:
        raise GoNoGoError(f"セル ({task}, {coverage}) に行が無い。プールが主軸を覆っていない")
    return subset


def _binary(task_types: Sequence[str]) -> list[str]:
    """解いたタスク型のうち二値型(`BINARY_TASK_TYPES` の順)。"""
    return [task for task in BINARY_TASK_TYPES if task in task_types]


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


def cell_table(
    rows: Sequence[Mapping[str, Any]], thresholds: Thresholds, *, task_types: Sequence[str]
) -> list[dict[str, Any]]:
    """#2: 解いた (タスク型 × 既知性) セルの4値と、`correct_rate` が基準を割ったかの印。

    **空のセルは止める。**主プールは 12 セルすべてに項目を持つ(ADR-076 決定8)。
    `task_types` は `solved_main_task_types`(絞りの無い run では 4 タスク型すべて)。
    """
    table: list[dict[str, Any]] = []
    for task in task_types:
        for coverage in MAIN_COVERAGE_LEVELS:
            values = four_values(_cell_rows(rows, task, coverage))
            table.append(
                {
                    "task": task,
                    "coverage": coverage,
                    **values,
                    "fails": values[f"{CORRECT}_rate"] < thresholds.min_cell_correct_rate,
                }
            )
    return table


def constant_strategy_table(
    rows: Sequence[Mapping[str, Any]], *, task_types: Sequence[str]
) -> list[dict[str, Any]]:
    """#3: 解いた T3 / T1b の (タスク型 × 既知性) ごとの実測と定数戦略の理論値。

    **印は「実測の correct_rate が両方の理論値を上回らない」**(基準を割った)。
    極性別の参照線(`polarity`)を併記するが、**印には使わない**(ADR-078 決定9)。
    """
    table: list[dict[str, Any]] = []
    for task in _binary(task_types):
        for coverage in MAIN_COVERAGE_LEVELS:
            subset = _cell_rows(rows, task, coverage)
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
                    "polarity": polarity_reference(subset),
                    "fails": not measured > ceiling,
                }
            )
    return table


def forced_choice_gaps(records: Sequence[Mapping[str, Any]], run_name: str) -> dict[str, float]:
    """二値群の行ごとの `yes_logp − no_logp`(item_id -> 差)。

    答える問い: 「この run の各比較項目で、モデルは Yes と No にどれだけの差で倒れたか」

    値は predictions の行の値そのもの(ADR-084 決定3)。**欄が無い行・差が数でない行・item_id の重複は
    止める** —— I10 より前の run を「近接同点 0 件」と読ませない(PLAN-026 §4.11 読み4)。
    """
    gaps: dict[str, float] = {}
    for record in records:
        if record["group"] != t3_comparison.GROUP:
            continue
        item_id = record["item_id"]
        missing = [field for field in (YES_LOGP_FIELD, NO_LOGP_FIELD) if record.get(field) is None]
        if missing:
            raise GoNoGoError(
                f"{run_name}: 二値群の行 {item_id!r} に {missing} が無い。近接同点の幅を宣言した run は、"
                "強制選択の値そのものを行に持つはずである(ADR-084 決定3)"
            )
        if item_id in gaps:
            raise GoNoGoError(f"{run_name}: 二値群の行 {item_id!r} が 2 つある")
        gap = float(record[YES_LOGP_FIELD]) - float(record[NO_LOGP_FIELD])
        if math.isnan(gap):
            raise GoNoGoError(f"{run_name}: 二値群の行 {item_id!r} の yes_logp − no_logp が数でない")
        gaps[item_id] = gap
    return gaps


def near_tie_table(
    rows: Sequence[Mapping[str, Any]],
    gaps: Mapping[str, float],
    *,
    margin: float,
    thresholds: Thresholds,
    task_types: Sequence[str],
) -> list[dict[str, Any]]:
    """§7 の感度の行: 解いた二値型のセルごとの近接同点の件数と、それを除いた #2。

    答える問い: 「batch で分類が揺れうる近接同点を除くと、このセルの #2 はどう読めるか」

    近接同点は `|yes_logp − no_logp| ≤ margin`(境界を含む。ADR-079 決定8)。**合否には使わない**。
    除いた後に行が無ければ 4 値と印は null(4 つ揃えて null にする)。
    """
    table: list[dict[str, Any]] = []
    for task in _binary(task_types):
        for coverage in MAIN_COVERAGE_LEVELS:
            subset = _cell_rows(rows, task, coverage)
            missing = [row["item"] for row in subset if row["item"] not in gaps]
            if missing:
                raise GoNoGoError(f"({task}, {coverage}) の行 {missing[:3]} に yes_logp − no_logp が無い")
            kept = [row for row in subset if abs(gaps[row["item"]]) > margin]
            if kept:
                values = four_values(kept)
                without: dict[str, Any] = {
                    **values,
                    "fails": values[f"{CORRECT}_rate"] < thresholds.min_cell_correct_rate,
                }
            else:
                without = {"n": 0, **{f"{name}_rate": None for name in CLASSES}, "fails": None}
            table.append(
                {
                    "task": task,
                    "coverage": coverage,
                    "n": len(subset),
                    "n_near_tie": len(subset) - len(kept),
                    "without_near_tie": without,
                }
            )
    return table


def run_report(metrics_path: Path) -> dict[str, Any]:
    """1つの run について #1〜#3 の表(と、幅を宣言した run では近接同点の感度の行)を組む。"""
    run = load_run(metrics_path)
    records = read_predictions(run.run_dir)
    rows = build_rows(run, records)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = load_config(run.run_dir / CONFIG_FILENAME)
    run_name = run.run_dir.name
    thresholds = thresholds_from_config(config, run_name)
    margin = near_tie_margin_from_config(config, run_name)
    task_types = solved_main_task_types(metrics)
    check_rows_within(rows, task_types, run_name)
    near_tie = None
    if margin is not None:
        near_tie = {
            "margin": margin,
            "note": NEAR_TIE_NOTE,
            "cells": near_tie_table(
                rows,
                forced_choice_gaps(records, run_name),
                margin=margin,
                thresholds=thresholds,
                task_types=task_types,
            ),
        }
    return {
        "run_id": run.run_id,
        "condition": run.condition,
        "seed": run.seed,
        "provenance": provenance_record(metrics, config),
        "solved_task_types": list(task_types),
        "thresholds": thresholds.as_dict(),
        "near_tie_margin": margin,
        "parse_fail": parse_fail_table(rows, thresholds),
        "cells": cell_table(rows, thresholds, task_types=task_types),
        "constant_strategy": constant_strategy_table(rows, task_types=task_types),
        "polarity_note": POLARITY_NOTE,
        "near_tie": near_tie,
    }


def calibrated_run_report(metrics_path: Path, lookup: calibrated.BiasLookup) -> dict[str, Any]:
    """1つの run に (c) の補正を引いた #2・#3 の表(と、幅を宣言した run では感度の行)。

    答える問い: 「内容のない入力の偏りを引くと、この run のセルの4値と #2・#3 の印はどうなるか」

    **#1(`parse_fail`)は出さない** —— 補正は強制選択の判定だけを動かし、数値群の行は
    1バイトも変わらない(同じ数字を2度出さない)。補正後の記録を `frame.build_rows` に
    渡すので、セルの組み方・印の付け方は補正前の表(`run_report`)と同じ関数である。

    近接同点は**補正後の差**で数える(ADR-086 決定2)。
    **①+(c) / (d)+(c) は §5 の候補ではない**(注記。ADR-086 決定1)。
    """
    run = load_run(metrics_path)
    records = read_predictions(run.run_dir)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = load_config(run.run_dir / CONFIG_FILENAME)
    run_name = run.run_dir.name
    calibrated.check_arm(lookup, metrics, config, run_name)
    adjusted = calibrated.calibrated_forced_choice_records(records, lookup, run_name=run_name)
    rows = build_rows(run, adjusted)
    thresholds = thresholds_from_config(config, run_name)
    margin = near_tie_margin_from_config(config, run_name)
    task_types = solved_main_task_types(metrics)
    check_rows_within(rows, task_types, run_name)
    near_tie = None
    if margin is not None:
        near_tie = {
            "margin": margin,
            "note": CALIBRATED_NEAR_TIE_NOTE,
            "cells": near_tie_table(
                rows,
                calibrated.calibrated_gaps(adjusted, run_name),
                margin=margin,
                thresholds=thresholds,
                task_types=task_types,
            ),
        }
    return {
        "run_id": run.run_id,
        "condition": run.condition,
        "seed": run.seed,
        "provenance": provenance_record(metrics, config),
        "calibration": lookup.record(),
        "solved_task_types": list(task_types),
        "thresholds": thresholds.as_dict(),
        "near_tie_margin": margin,
        "cells": cell_table(rows, thresholds, task_types=task_types),
        "constant_strategy": constant_strategy_table(rows, task_types=task_types),
        "polarity_note": POLARITY_NOTE,
        "near_tie": near_tie,
        "note": calibrated.NOT_A_CANDIDATE_NOTE,
    }


def build_report(metrics_paths: Sequence[Path]) -> dict[str, Any]:
    """渡された run ごとに表を組む。**閾値と近接同点の幅が run 間で違えば止める。**"""
    runs = [run_report(path) for path in metrics_paths]
    settings = {
        json.dumps([run["thresholds"], run["near_tie_margin"]], sort_keys=True) for run in runs
    }
    if len(settings) > 1:
        raise GoNoGoError(f"run 間で Go/No-Go の閾値か近接同点の幅が違う: {sorted(settings)}")
    return {
        "created_at": utc_now().isoformat(),
        "note": (
            "印(fails)は基準を割ったかどうかだけである。Go/No-Go の判断・落ちたセルの一覧の確定・"
            "T1b の扱いは人間が決める(CLAUDE.md §8 / ADR-076 決定1 / ADR-047 決定2)。"
            "極性別の参照線と近接同点の感度の行は印に使わない(ADR-078 決定9 / ADR-079 決定8)"
        ),
        "runs": runs,
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def _rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _provenance_line(provenance: Mapping[str, Any]) -> str:
    sha = provenance["preamble_sha256"]
    return (
        f"  experiment={provenance['experiment_id']} pool={provenance['pool_id']} "
        f"adapter={provenance['adapter']} templates={provenance['template_set']} "
        f"preamble={'なし' if sha is None else sha[:12]} task_subset={provenance['task_subset']}"
    )


def _polarity_text(polarity: Mapping[str, Any]) -> str:
    gt = polarity["by_polarity"][t3_comparison.GT]
    lt = polarity["by_polarity"][t3_comparison.LT]
    strategies = polarity["polarity_strategies"]
    return (
        f"Yes|gt={gt['n_yes']}/{gt['n']} Yes|lt={lt['n_yes']}/{lt['n']} "
        + " ".join(
            f"{name}={_rate(values['correct_rate'])}" for name, values in strategies.items()
        )
    )


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人間が読む表(標準出力)。**4値を揃えて出す。**"""
    lines: list[str] = [report["note"]]
    for run in report["runs"]:
        thresholds = run["thresholds"]
        lines.append(f"=== run {run['run_id']}(condition={run['condition']} / seed={run['seed']})")
        lines.append(_provenance_line(run["provenance"]))
        lines.append(f"#1 parse_fail_rate < {thresholds['parse_fail_max']}(judged=False は参考)")
        for row in run["parse_fail"]:
            lines.append(
                f"  {row['group']:<20} n={row['n']:<4} correct={_rate(row['correct_rate'])} "
                f"rule={_rate(row['rule_rate'])} other_error={_rate(row['other_error_rate'])} "
                f"parse_fail={_rate(row['parse_fail_rate'])} judged={row['judged']} "
                f"fails={row['fails']}"
            )
        lines.append(
            f"#2 correct_rate >= {thresholds['min_cell_correct_rate']}"
            f"({len(run['cells'])} セル。解いたタスク型 {run['solved_task_types']})"
        )
        for row in run["cells"]:
            lines.append(
                f"  {row['task']:<4} {row['coverage']:<17} n={row['n']:<4} "
                f"correct={_rate(row['correct_rate'])} rule={_rate(row['rule_rate'])} "
                f"other_error={_rate(row['other_error_rate'])} "
                f"parse_fail={_rate(row['parse_fail_rate'])} fails={row['fails']}"
            )
        lines.append("#3 実測の correct_rate > 定数戦略の理論値(T3 / T1b)。極性別の値は参照線")
        for row in run["constant_strategy"]:
            yes = row["baselines"]["always_yes"]["correct_rate"]
            no = row["baselines"]["always_no"]["correct_rate"]
            lines.append(
                f"  {row['task']:<4} {row['coverage']:<17} n={row['n']:<4} "
                f"correct={_rate(row['correct_rate'])} always_yes={_rate(yes)} "
                f"always_no={_rate(no)} fails={row['fails']} | {_polarity_text(row['polarity'])}"
            )
        lines.extend(_near_tie_lines(run["near_tie"]))
    return lines


def _near_tie_lines(near_tie: Mapping[str, Any] | None) -> list[str]:
    if near_tie is None:
        return [f"近接同点の感度の行: なし(config に {NEAR_TIE_MARGIN_KEY} が無い)"]
    lines = [
        f"近接同点(|yes_logp − no_logp| ≤ {near_tie['margin']})の感度の行 —— 印(fails)には使わない"
    ]
    for row in near_tie["cells"]:
        without = row["without_near_tie"]
        lines.append(
            f"  {row['task']:<4} {row['coverage']:<17} n={row['n']:<4} "
            f"near_tie={row['n_near_tie']:<4} 除いた n={without['n']:<4} "
            f"correct={_rate(without['correct_rate'])} "
            f"rule={_rate(without['rule_rate'])} other_error={_rate(without['other_error_rate'])} "
            f"parse_fail={_rate(without['parse_fail_rate'])} #2 の印={without['fails']}"
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
