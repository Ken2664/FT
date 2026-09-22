"""PLAN-026 §5 の選び方を、順6b の 7 本の run に機械的に当てる(I11c。§4.13)。

答える問い: 「タスク型ごとに、§5 の (i)〜(iv) を満たす候補はどれか。表の順で最も小さいものはどれか」

    python -m code.analysis.order6b_select \\
        --b0 "runs/*order6b_pilot*" --r8 "runs/*order6b_r8*" \\
        --preamble "runs/*order6b_preamble*" --s-preamble "runs/*order6b_s_preamble*" \\
        --d "runs/*order6b_d*" --s-d "runs/*order6b_s_d*" --c "runs/*order6b_c*" \\
        --out-dir results/order6b_select

**印を付けるだけで、判断しない**(`CLAUDE.md` §8)。**この結果は「候補」であって採用ではない** ——
採用は ADR-046 の手続きで人間が決め、主プールで測り直して ADR-076 決定1 の規則を当てる
(PLAN-026 §5)。§6 の分岐 A / B / C の読みも人間である。

**§5 の値(0.70・−2・+3)・判定規則・4 値分解・候補の集合(C0 / C3 / C2 / C1)は、ここでは作らない。**
セルの4値と印は `code/analysis/gonogo.py`、遠いオフセットの `correct` は `code/analysis/r8_fit.py`、
(c) の補正は `code/analysis/calibrated.py` が出したものをそのまま読む。

**腕は引数で明示する**(ADR-085 決定3)。各 run の記録(`kind`・文面の組・前置きの sha256・絞り・
掃引の腕・`pool_id`・`adapter`)が腕の形と合わなければ止める —— **名前からは推測しない**。
**7 本すべてが要る**(ADR-087 決定1)。1 本でも欠けた表は「C0 が最小だった」と読めてしまい、
「候補が無かった」「満たさなかった」「測っていない」が 1 つに潰れる。

**①+(c) / (d)+(c) は §5 の候補ではない**(ADR-079 決定6)。別のブロック(`descriptive`)に
**値だけ**を出し、(i)〜(iv) の合否の印は付けない(ADR-087 決定3)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.analysis import calibrated, gonogo, r8_fit
from code.analysis.aggregate import EVAL_KIND, expand_metrics_paths
from code.analysis.frame import CONFIG_FILENAME
from code.artifacts import utc_now
from code.config import load_config, require
from code.data_gen.pool import MAIN_COVERAGE_LEVELS, POOL_PILOT
from code.eval.battery import numeric_sum, t3_comparison
from code.eval.calibration import CALIBRATION_KIND
from code.eval.run import THRESHOLD_SWEEP_KIND

OUTPUT_FILENAME = "order6b_select.json"

# 腕の形を照合する欄(ADR-085 決定3)。**名前(experiment_id・ディレクトリ名)は使わない。**
TEMPLATE_SET_KEY = "data.eval_template_set"
TEMPLATE_SET_MAIN = "eval_main"
TEMPLATE_SET_D = "order6b_d"
SWEEP_ARM_R8 = "r8"
SWEEP_ARM_S = "s"

# 較正の腕の名前(configs/exp_order6b_c.yaml の eval.calibration.arms)。
CALIBRATION_ARM_B0 = "b0"
CALIBRATION_ARM_PREAMBLE = "preamble"
CALIBRATION_ARM_D = "d"

# 判定に使う 3 セルの被覆水準(§5 (i)・(ii)・(iv)。ADR-081 決定3)。
COVERAGE_LEVELS = MAIN_COVERAGE_LEVELS
# §5 の判定の対象になるタスク型(二値出力。T3 は (d) を持たない)。
JUDGED_TASK_TYPES: tuple[str, ...] = (t3_comparison.T3, t3_comparison.T1B)
# §5 (iii) が見る自由生成のタスク型(①-num)。
NUMERIC_TASK_TYPES: tuple[str, ...] = (numeric_sum.T1, numeric_sum.T2)

# 4値の並び(`CLAUDE.md` §6)。**定義は `gonogo.py` の 1 か所**(2 つ持たない)。
CLASSES: tuple[str, ...] = gonogo.CLASSES

CRITERIA_NOTE: dict[str, str] = {
    "i": "#2: そのタスク型の 3 セルすべてで correct_rate >= gonogo.min_cell_correct_rate",
    "ii": "#3: 同じ 3 セルすべてで correct_rate > max(常に Yes, 常に No)",
    "iii": (
        "C1 に限り: ①-num で T1・T2 の 6 セルが #1(judged の群すべてで "
        "parse_fail_rate < gonogo.parse_fail_max。ADR-078 決定11)と #2 を満たす"
    ),
    "iv": (
        "その候補の掃引の遠いオフセットで、低い側と高い側の correct_rate が"
        "**セルごとに**どちらも gonogo.min_cell_correct_rate 以上(ADR-081 決定3)"
    ),
}

REPORT_NOTE = (
    "PLAN-026 §5 を機械的に当てただけの表である。**候補であって採用ではない** —— "
    "採用は ADR-046 の手続きで人間が決め、主プールで測り直して ADR-076 決定1 の規則を当てる"
    "(ADR-078 決定2)。§6 の分岐 A / B / C の読みも人間である(CLAUDE.md §8)。"
    "近接同点の感度の行は合否に使わない(ADR-079 決定8 / ADR-086 決定3)。"
    "pool_id: pilot の数値は主張の根拠に使わない(PLAN-001 §4.6 規則4)"
)
NOT_APPLICABLE_NOTE = (
    "applicable=false は「そのタスク型にこの候補が無い」であって「満たさなかった」ではない"
    "(§5 の表の「—」。T3 は (d) を持たない —— すでに同じ一文で終わっている)"
)
NO_CANDIDATE_NOTE = (
    "no_candidate=true は「§5 を満たす候補が 1 つも無い」(ADR-086 決定4)。"
    "そのタスク型の preamble_mismatch は定義できないので、報告の preamble_mismatch は null になる"
)
MISMATCH_NOTE = (
    "preamble_mismatch は「T3 と T1b で ① の有無が食い違ったか」(§5 の「そのまま人間に上げる」)。"
    "両方のタスク型に候補があるときだけ true / false を取る(ADR-086 決定4)"
)


class SelectError(ValueError):
    """§5 の判定表を組めない。取り違えたまま候補を出すより止める。"""


# --------------------------------------------------------------------------
# 腕(ADR-085 決定3。**名前からは推測しない**)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmSpec:
    """1 本の run に「あるべき記録の形」。

    答える問い: 「この引数で渡された run は、本当にこの腕の run か」

    `configs/exp_order6b_*.yaml` の転記であり、食い違えばテストが両方向で落ちる
    (`test_order6b_select.py`)。**実験条件をここで決めているのではない。**
    """

    name: str
    option: str
    kind: str
    template_set: str
    preamble: bool
    task_subset: tuple[str, ...] | None
    sweep_arm: str | None
    # プールを読む腕は pilot(§5 はパイロット用プールで判定する)。
    # **(c) の較正はプールを読まない**(内容のない入力に項目が無い)ので None。
    pool_id: str | None
    help: str


ARM_SPECS: tuple[ArmSpec, ...] = (
    ArmSpec(
        name="b0",
        option="--b0",
        kind=EVAL_KIND,
        template_set=TEMPLATE_SET_MAIN,
        preamble=False,
        task_subset=None,
        sweep_arm=None,
        pool_id=POOL_PILOT,
        help="B0(基準。固定オフセット・プール全体)",
    ),
    ArmSpec(
        name="r8",
        option="--r8",
        kind=THRESHOLD_SWEEP_KIND,
        template_set=TEMPLATE_SET_MAIN,
        preamble=False,
        task_subset=None,
        sweep_arm=SWEEP_ARM_R8,
        pool_id=POOL_PILOT,
        help="R8(閾値掃引。B0 の文面)",
    ),
    ArmSpec(
        name="preamble",
        option="--preamble",
        kind=EVAL_KIND,
        template_set=TEMPLATE_SET_MAIN,
        preamble=True,
        task_subset=(t3_comparison.T3, t3_comparison.T1B, numeric_sum.T1, numeric_sum.T2),
        sweep_arm=None,
        pool_id=POOL_PILOT,
        help="①(前置き。固定オフセット・T3 / T1b / T1 / T2)",
    ),
    ArmSpec(
        name="s_preamble",
        option="--s-preamble",
        kind=THRESHOLD_SWEEP_KIND,
        template_set=TEMPLATE_SET_MAIN,
        preamble=True,
        task_subset=None,
        sweep_arm=SWEEP_ARM_S,
        pool_id=POOL_PILOT,
        help="S-①(候補を減らした掃引。① の前置き)",
    ),
    ArmSpec(
        name="d",
        option="--d",
        kind=EVAL_KIND,
        template_set=TEMPLATE_SET_D,
        preamble=False,
        task_subset=(t3_comparison.T1B,),
        sweep_arm=None,
        pool_id=POOL_PILOT,
        help="(d)(T1b に指示文。固定オフセット)",
    ),
    ArmSpec(
        name="s_d",
        option="--s-d",
        kind=THRESHOLD_SWEEP_KIND,
        template_set=TEMPLATE_SET_D,
        preamble=False,
        task_subset=(t3_comparison.T1B,),
        sweep_arm=SWEEP_ARM_S,
        pool_id=POOL_PILOT,
        help="S-(d)(候補を減らした掃引。(d) の文面)",
    ),
    ArmSpec(
        name="c",
        option="--c",
        kind=CALIBRATION_KIND,
        template_set=TEMPLATE_SET_MAIN,
        preamble=True,
        task_subset=None,
        sweep_arm=None,
        pool_id=None,
        help="(c)(内容のない入力による較正。3 腕)",
    ),
)

# (c) の run が較正しているはずの 3 腕(名前 -> (文面の組, 前置きを置くか))。
CALIBRATION_ARMS: dict[str, tuple[str, bool]] = {
    CALIBRATION_ARM_B0: (TEMPLATE_SET_MAIN, False),
    CALIBRATION_ARM_D: (TEMPLATE_SET_D, False),
    CALIBRATION_ARM_PREAMBLE: (TEMPLATE_SET_MAIN, True),
}


@dataclass(frozen=True)
class Arm:
    """腕の形を照合した 1 本の run。"""

    spec: ArmSpec
    metrics_path: Path
    metrics: Mapping[str, Any]
    config: Mapping[str, Any]

    @property
    def run_name(self) -> str:
        return self.metrics_path.parent.name

    @property
    def run_id(self) -> str:
        return str(self.metrics["run_id"])

    @property
    def preamble_sha256(self) -> str | None:
        record = self.metrics.get(gonogo.PREAMBLE_FIELD)
        return None if record is None else str(record["sha256"])

    def provenance(self) -> dict[str, Any]:
        """腕ごとの来歴(ADR-087 決定4)。**名前は照合に使わないが、報告には出す。**"""
        subset = self.metrics.get(gonogo.TASK_SUBSET_FIELD)
        return {
            "arm": self.spec.name,
            "run_id": self.run_id,
            "run_dir": self.run_name,
            "kind": self.metrics.get("kind"),
            "experiment_id": self.metrics.get("experiment_id"),
            "template_set": require(self.config, TEMPLATE_SET_KEY),
            "preamble_sha256": self.preamble_sha256,
            "task_subset": None if subset is None else list(subset["task_types"]),
            "pool_id": (self.metrics.get("pool") or {}).get("pool_id"),
            "adapter": self.metrics.get("adapter"),
        }


def _check_shape(spec: ArmSpec, metrics: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    """記録が腕の形と合うか(ADR-085 決定3 / PLAN-026 §4.13 読み2)。**合わなければ止める。**"""
    name = spec.name
    if metrics.get("kind") != spec.kind:
        raise SelectError(
            f"{spec.option}: kind が {metrics.get('kind')!r} で、腕 {name!r} の {spec.kind!r} と違う"
        )
    template_set = require(config, TEMPLATE_SET_KEY)
    if template_set != spec.template_set:
        raise SelectError(
            f"{spec.option}: 文面の組が {template_set!r} で、腕 {name!r} の {spec.template_set!r} と違う"
        )
    has_preamble = metrics.get(gonogo.PREAMBLE_FIELD) is not None
    if has_preamble != spec.preamble:
        raise SelectError(
            f"{spec.option}: この run の前置きは {'あり' if has_preamble else 'なし'} で、"
            f"腕 {name!r} の {'あり' if spec.preamble else 'なし'} と違う"
        )
    subset = metrics.get(gonogo.TASK_SUBSET_FIELD)
    declared = None if subset is None else tuple(subset["task_types"])
    if declared != spec.task_subset:
        raise SelectError(
            f"{spec.option}: 絞りが {declared} で、腕 {name!r} の {spec.task_subset} と違う"
        )
    sweep_arm = (metrics.get("threshold_sweep") or {}).get("arm")
    if sweep_arm != spec.sweep_arm:
        raise SelectError(
            f"{spec.option}: 掃引の腕が {sweep_arm!r} で、腕 {name!r} の {spec.sweep_arm!r} と違う"
        )
    pool_id = (metrics.get("pool") or {}).get("pool_id")
    if pool_id != spec.pool_id:
        raise SelectError(
            f"{spec.option}: pool_id が {pool_id!r} で、腕 {name!r} の {spec.pool_id!r} と違う。"
            "§5 はパイロット用プールで判定する((c) の較正はプールを読まないので null)"
        )
    if metrics.get("adapter") is not None:
        raise SelectError(
            f"{spec.option}: adapter が {metrics.get('adapter')!r} である。"
            "順6b は素の重みで回す(adapter = null)"
        )


def load_arm(spec: ArmSpec, pattern: str) -> Arm:
    """1 本の腕を読み、形を照合する。**glob が 1 本に当たらなければ止める。**"""
    paths = expand_metrics_paths([pattern])
    if len(paths) != 1:
        raise SelectError(
            f"{spec.option} は 1 本の run に当たらなければならない: {[str(p.parent) for p in paths]}"
        )
    metrics_path = paths[0]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = load_config(metrics_path.parent / CONFIG_FILENAME)
    _check_shape(spec, metrics, config)
    return Arm(spec=spec, metrics_path=metrics_path, metrics=metrics, config=config)


def check_preambles(arms: Mapping[str, Arm]) -> None:
    """前置きを持つ腕(①・S-①・(c))の sha256 が揃っているか。**違えば止める。**

    答える問い: 「① の固定オフセット・S-①・(c) の較正は、同じ前置きで尋ねられたか」

    `calibrated.check_arm` は補正を掛ける run と較正の run を突き合わせるが、補正を掛けない
    候補(C1)の ① と S-① は突き合わされない。**別の前置きの run を 1 つの候補にしない。**
    """
    shas = {name: arms[name].preamble_sha256 for name in arms if arms[name].spec.preamble}
    if len(set(shas.values())) > 1:
        raise SelectError(f"前置きの sha256 が腕どうしで違う: {shas}")


def check_calibration_arms(calibration: calibrated.Calibration) -> None:
    """(c) の run が 3 腕を宣言し、その形が腕の定数と合うか。**違えば止める。**"""
    declared = {arm.name: (arm.template_set, arm.preamble) for arm in calibration.arms}
    if declared != CALIBRATION_ARMS:
        raise SelectError(
            f"(c) の run {calibration.run_id!r} の腕 {declared} が、腕の形 {CALIBRATION_ARMS} と違う"
        )


# --------------------------------------------------------------------------
# 閾値(§5 の値はここで作らない)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """7 本の run が共有している閾値と近接同点の幅。"""

    thresholds: gonogo.Thresholds
    near_tie_margin: float | None

    def as_dict(self) -> dict[str, Any]:
        return {**self.thresholds.as_dict(), "near_tie_margin": self.near_tie_margin}


def settings_of(arms: Mapping[str, Arm]) -> Settings:
    """7 本の run の閾値と幅を読む。**1 本でも違えば止める**(`gonogo.build_report` と同じ)。"""
    seen: dict[str, list[str]] = {}
    for name, arm in arms.items():
        thresholds = gonogo.thresholds_from_config(arm.config, arm.run_name)
        margin = gonogo.near_tie_margin_from_config(arm.config, arm.run_name)
        key = json.dumps([thresholds.as_dict(), margin], sort_keys=True)
        seen.setdefault(key, []).append(name)
    if len(seen) > 1:
        raise SelectError(f"腕どうしで Go/No-Go の閾値か近接同点の幅が違う: {seen}")
    first = arms[next(iter(arms))]
    return Settings(
        thresholds=gonogo.thresholds_from_config(first.config, first.run_name),
        near_tie_margin=gonogo.near_tie_margin_from_config(first.config, first.run_name),
    )


# --------------------------------------------------------------------------
# 候補(§5 の表。**集合も順序も変えない**)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateSpec:
    """§5 の候補 1 つ(どの腕の run を、どの補正で読むか)。

    答える問い: 「この候補は、どの run の数字で判定されるか」
    """

    name: str
    label: str
    fixed_arm: str
    sweep_arm: str
    calibration_arm: str | None
    task_types: tuple[str, ...]
    numeric_gate: bool


# **表の順(変更の小さい順)。ADR-079 決定6 の G7 (a)。**この順で最初に満たしたものを採る。
CANDIDATES: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        name="C0",
        label="変更なし",
        fixed_arm="b0",
        sweep_arm="r8",
        calibration_arm=None,
        task_types=JUDGED_TASK_TYPES,
        numeric_gate=False,
    ),
    CandidateSpec(
        name="C3",
        label="(c) 較正",
        fixed_arm="b0",
        sweep_arm="r8",
        calibration_arm=CALIBRATION_ARM_B0,
        task_types=JUDGED_TASK_TYPES,
        numeric_gate=False,
    ),
    CandidateSpec(
        name="C2",
        label="(d) 指示文",
        fixed_arm="d",
        sweep_arm="s_d",
        calibration_arm=None,
        task_types=(t3_comparison.T1B,),
        numeric_gate=False,
    ),
    CandidateSpec(
        name="C1",
        label="① 前置き",
        fixed_arm="preamble",
        sweep_arm="s_preamble",
        calibration_arm=None,
        task_types=JUDGED_TASK_TYPES,
        numeric_gate=True,
    ),
)

# **§5 の候補ではない**(ADR-079 決定6)。3 腕すべてに補正を掛けるのは記述のため(ADR-086 決定1)。
DESCRIPTIVE: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        name="①+(c)",
        label="① 前置き + (c) 較正",
        fixed_arm="preamble",
        sweep_arm="s_preamble",
        calibration_arm=CALIBRATION_ARM_PREAMBLE,
        task_types=JUDGED_TASK_TYPES,
        numeric_gate=False,
    ),
    CandidateSpec(
        name="(d)+(c)",
        label="(d) 指示文 + (c) 較正",
        fixed_arm="d",
        sweep_arm="s_d",
        calibration_arm=CALIBRATION_ARM_D,
        task_types=(t3_comparison.T1B,),
        numeric_gate=False,
    ),
)


# --------------------------------------------------------------------------
# run の表を読む(**数え直さない**)
# --------------------------------------------------------------------------


class Reports:
    """腕 × 補正の組ごとの run 単位の表(同じ run を 2 度読まない)。"""

    def __init__(self, arms: Mapping[str, Arm], calibration: calibrated.Calibration) -> None:
        self._arms = arms
        self._calibration = calibration
        self._cache: dict[tuple[str, str | None], dict[str, Any]] = {}

    def _lookup(self, arm_name: str) -> calibrated.BiasLookup:
        return calibrated.bias_lookup(self._calibration, arm_name)

    def of(self, arm: str, calibration_arm: str | None) -> dict[str, Any]:
        """この腕の表(補正を掛けるなら較正の腕を渡す)。"""
        key = (arm, calibration_arm)
        if key not in self._cache:
            path = self._arms[arm].metrics_path
            sweep = self._arms[arm].spec.kind == THRESHOLD_SWEEP_KIND
            if calibration_arm is None:
                report = r8_fit.run_report(path) if sweep else gonogo.run_report(path)
            else:
                lookup = self._lookup(calibration_arm)
                report = (
                    r8_fit.calibrated_run_report(path, lookup)
                    if sweep
                    else gonogo.calibrated_run_report(path, lookup)
                )
            self._cache[key] = report
        return self._cache[key]


def _solved(report: Mapping[str, Any], key: str, task: str, what: str) -> None:
    solved = list(report[key])
    if task not in solved:
        raise SelectError(f"{what}: この run が解いたタスク型は {solved} で、{task!r} が無い")


def _by_coverage(
    rows: Sequence[Mapping[str, Any]], task: str, task_key: str, what: str
) -> list[Mapping[str, Any]]:
    """1 つのタスク型の 3 セルを被覆水準の順で。**欠けていれば止める。**"""
    found = {row["coverage"]: row for row in rows if row[task_key] == task}
    missing = [coverage for coverage in COVERAGE_LEVELS if coverage not in found]
    if missing:
        raise SelectError(f"{what}: タスク型 {task!r} のセル {missing} が表に無い")
    return [found[coverage] for coverage in COVERAGE_LEVELS]


def cells_i(report: Mapping[str, Any], task: str) -> dict[str, Any]:
    """(i) #2: 3 セルの4値と印(`gonogo.cell_table` が付けた `fails` をそのまま読む)。"""
    _solved(report, "solved_task_types", task, "(i) #2")
    rows = _by_coverage(report["cells"], task, "task", "(i) #2")
    return {
        "passed": not any(row["fails"] for row in rows),
        "cells": [
            {
                "coverage": row["coverage"],
                "n": row["n"],
                **{f"{name}_rate": row[f"{name}_rate"] for name in CLASSES},
                "fails": row["fails"],
            }
            for row in rows
        ],
    }


def cells_ii(report: Mapping[str, Any], task: str) -> dict[str, Any]:
    """(ii) #3: 実測の correct が定数戦略の理論値を超えたか(`constant_strategy` の `fails`)。"""
    _solved(report, "solved_task_types", task, "(ii) #3")
    rows = _by_coverage(report["constant_strategy"], task, "task", "(ii) #3")
    return {
        "passed": not any(row["fails"] for row in rows),
        "cells": [
            {
                "coverage": row["coverage"],
                "n": row["n"],
                "correct_rate": row["correct_rate"],
                "always_yes": row["baselines"]["always_yes"]["correct_rate"],
                "always_no": row["baselines"]["always_no"]["correct_rate"],
                "fails": row["fails"],
            }
            for row in rows
        ],
    }


def numeric_gate(report: Mapping[str, Any]) -> dict[str, Any]:
    """(iii) C1 に限る門: ①-num の #1(群で読む)と #2(T1・T2 の 6 セル)。

    答える問い: 「前置きを置いた run で、自由生成の数値群は壊れていないか」

    #1 は `gonogo.parse_fail_table` の `judged = True` の行すべて(ADR-078 決定11)。
    ① の run は `bare_sum`(T1)と `word_problem`(T2)を解き、特異性対照は解かないので行が無い。
    **判定対象の行が 0 件なら止める** —— 空で真になる読みを作らない。
    """
    groups = [row for row in report["parse_fail"] if row["judged"]]
    if not groups:
        raise SelectError("(iii) #1: 判定対象(judged)の群が 1 つも無い。① の run は T1・T2 を解くはずである")
    cells: list[dict[str, Any]] = []
    for task in NUMERIC_TASK_TYPES:
        _solved(report, "solved_task_types", task, "(iii) #2")
        for row in _by_coverage(report["cells"], task, "task", "(iii) #2"):
            cells.append(
                {
                    "task": task,
                    "coverage": row["coverage"],
                    "n": row["n"],
                    **{f"{name}_rate": row[f"{name}_rate"] for name in CLASSES},
                    "fails": row["fails"],
                }
            )
    return {
        "applicable": True,
        "passed": not any(row["fails"] for row in (*groups, *cells)),
        "parse_fail": [
            {
                "group": row["group"],
                "n": row["n"],
                "parse_fail_rate": row["parse_fail_rate"],
                "fails": row["fails"],
            }
            for row in groups
        ],
        "cells": cells,
    }


def far_offsets_iv(
    report: Mapping[str, Any], task: str, min_correct: float
) -> dict[str, Any]:
    """(iv) 和を読んでいるか: 遠いオフセットの側ごとの `correct`(★F138 の守り)。

    答える問い: 「閾値から遠い θ で、このセルは両側とも基準以上の correct を出しているか」

    判定の単位は**セル**(ADR-081 決定3)。値は #2 の流用で、**新しい値を作らない**(G13)。
    `β1` は使わない(§3.2.1 の揃え方と完全分離に左右されるため)。
    """
    _solved(report, "task_types", task, "(iv) 遠いオフセット")
    rows = _by_coverage(report["cells"], task, "task_type", "(iv) 遠いオフセット")
    cells: list[dict[str, Any]] = []
    for row in rows:
        sides = row["far_offset_correct"]
        fails = any(sides[side]["correct_rate"] < min_correct for side in r8_fit.SIDES)
        cells.append(
            {
                "coverage": row["coverage"],
                **{side: dict(sides[side]) for side in r8_fit.SIDES},
                "fails": fails,
            }
        )
    return {"passed": not any(cell["fails"] for cell in cells), "cells": cells}


def _near_tie_rows(
    near_tie: Mapping[str, Any] | None, task: str, task_key: str
) -> list[dict[str, Any]] | None:
    """感度の行のうち、このタスク型の行(幅を宣言していない run では None)。**合否に使わない。**"""
    if near_tie is None:
        return None
    return [dict(row) for row in near_tie["cells"] if row[task_key] == task]


def near_tie_block(
    fixed: Mapping[str, Any], sweep: Mapping[str, Any], task: str
) -> dict[str, Any]:
    """§7 の感度の行(固定オフセットと掃引)。**#2 と併記する**(ADR-079 決定8 / ADR-086 決定3)。

    注記は表を組んだ側から取る —— 補正前(`|yes_logp − no_logp|`)と補正後(`|(yes_logp −
    no_logp) − b|`)では数えている差が違う(ADR-086 決定2)。**ここで書き分けない。**
    """
    fixed_near_tie = fixed["near_tie"]
    sweep_near_tie = sweep.get("near_tie")
    return {
        "note": None if fixed_near_tie is None else fixed_near_tie["note"],
        "sweep_note": None if sweep_near_tie is None else sweep_near_tie["note"],
        "margin": fixed["near_tie_margin"],
        "fixed": _near_tie_rows(fixed_near_tie, task, "task"),
        "sweep": _near_tie_rows(sweep_near_tie, task, "task_type"),
    }


DESCRIPTIVE_NEAR_TIE_NOTE = (
    "記述の腕の感度の行には #2 の印(fails)を置かない(ADR-087 決定3) —— "
    "①+(c) / (d)+(c) は §5 の候補ではないので、合否の形をした欄を作らない。"
    "件数と、近接同点を除いた値だけを出す"
)


def descriptive_near_tie(
    fixed: Mapping[str, Any], sweep: Mapping[str, Any], task: str
) -> dict[str, Any]:
    """記述の腕の感度の行。**#2 の印(`fails`)を落とす**(ADR-087 決定3)。

    答える問い: 「この記述の腕で、近接同点は何件あり、除くと値はどうなるか」

    掃引の側(`r8_fit.near_tie_table`)はもともと印を持たないので、落とすのは固定オフセットの
    `without_near_tie.fails` だけである。**件数と値は 1 つも落とさない。**
    """
    block = near_tie_block(fixed, sweep, task)
    block["note_descriptive"] = DESCRIPTIVE_NEAR_TIE_NOTE
    for row in block["fixed"] or []:
        row["without_near_tie"] = {
            key: value for key, value in row["without_near_tie"].items() if key != "fails"
        }
    return block


# --------------------------------------------------------------------------
# §5 を当てる
# --------------------------------------------------------------------------


def evaluate(
    spec: CandidateSpec, task: str, reports: Reports, settings: Settings, arms: Mapping[str, Arm]
) -> dict[str, Any]:
    """1 つの (候補 × タスク型) に §5 の (i)〜(iv) を当てる。**解釈はしない。**"""
    runs = {
        "fixed": arms[spec.fixed_arm].run_id,
        "sweep": arms[spec.sweep_arm].run_id,
        "calibration": None if spec.calibration_arm is None else arms["c"].run_id,
        "calibration_arm": spec.calibration_arm,
    }
    if task not in spec.task_types:
        return {
            "candidate": spec.name,
            "label": spec.label,
            "applicable": False,
            "note": NOT_APPLICABLE_NOTE,
            "runs": runs,
            "criteria": None,
            "passed": None,
            "near_tie": None,
        }
    fixed = reports.of(spec.fixed_arm, spec.calibration_arm)
    sweep = reports.of(spec.sweep_arm, spec.calibration_arm)
    criteria = {
        "i": cells_i(fixed, task),
        "ii": cells_ii(fixed, task),
        "iii": (
            numeric_gate(fixed)
            if spec.numeric_gate
            else {"applicable": False, "passed": None, "parse_fail": None, "cells": None}
        ),
        "iv": far_offsets_iv(sweep, task, settings.thresholds.min_cell_correct_rate),
    }
    passed = all(
        block["passed"] for block in criteria.values() if block["passed"] is not None
    )
    return {
        "candidate": spec.name,
        "label": spec.label,
        "applicable": True,
        "runs": runs,
        "criteria": criteria,
        "passed": passed,
        "near_tie": near_tie_block(fixed, sweep, task),
    }


def select_for(
    task: str, reports: Reports, settings: Settings, arms: Mapping[str, Arm]
) -> dict[str, Any]:
    """1 つのタスク型について、満たす候補のうち**表の順で最も小さいもの**を採る。

    答える問い: 「このタスク型では、§5 を満たす候補のうち最も変更の小さいものはどれか」

    満たす候補が 1 つも無ければ `selected = null` + `no_candidate = true`(ADR-086 決定4)。
    **「候補が無い」(`applicable = false`)と「満たさなかった」は別の欄である**(§4.13 読み7)。
    """
    rows = [evaluate(spec, task, reports, settings, arms) for spec in CANDIDATES]
    selected = next((row["candidate"] for row in rows if row["passed"]), None)
    return {
        "task_type": task,
        "candidates": rows,
        "selected": selected,
        "no_candidate": selected is None,
        "note": NO_CANDIDATE_NOTE,
    }


def preamble_mismatch(selections: Sequence[Mapping[str, Any]]) -> bool | None:
    """T3 と T1b で ① の有無が食い違ったか。**片方が候補なしなら null**(ADR-086 決定4)。"""
    if any(row["selected"] is None for row in selections):
        return None
    uses_preamble = {
        row["selected"] == "C1" for row in selections
    }
    return len(uses_preamble) > 1


def describe(
    spec: CandidateSpec, reports: Reports, arms: Mapping[str, Arm]
) -> dict[str, Any]:
    """記述の腕(①+(c) / (d)+(c))の値。**(i)〜(iv) の合否の印は付けない**(ADR-087 決定3)。"""
    fixed = reports.of(spec.fixed_arm, spec.calibration_arm)
    sweep = reports.of(spec.sweep_arm, spec.calibration_arm)
    task_types: list[dict[str, Any]] = []
    for task in spec.task_types:
        _solved(fixed, "solved_task_types", task, f"{spec.name}(固定オフセット)")
        _solved(sweep, "task_types", task, f"{spec.name}(掃引)")
        task_types.append(
            {
                "task_type": task,
                "cells": [
                    {
                        "coverage": row["coverage"],
                        "n": row["n"],
                        **{f"{name}_rate": row[f"{name}_rate"] for name in CLASSES},
                    }
                    for row in _by_coverage(fixed["cells"], task, "task", spec.name)
                ],
                "constant_strategy": [
                    {
                        "coverage": row["coverage"],
                        "n": row["n"],
                        "correct_rate": row["correct_rate"],
                        "always_yes": row["baselines"]["always_yes"]["correct_rate"],
                        "always_no": row["baselines"]["always_no"]["correct_rate"],
                    }
                    for row in _by_coverage(
                        fixed["constant_strategy"], task, "task", spec.name
                    )
                ],
                "far_offset_correct": [
                    {
                        "coverage": row["coverage"],
                        **{
                            side: dict(row["far_offset_correct"][side])
                            for side in r8_fit.SIDES
                        },
                    }
                    for row in _by_coverage(sweep["cells"], task, "task_type", spec.name)
                ],
                "near_tie": descriptive_near_tie(fixed, sweep, task),
            }
        )
    return {
        "name": spec.name,
        "label": spec.label,
        "runs": {
            "fixed": arms[spec.fixed_arm].run_id,
            "sweep": arms[spec.sweep_arm].run_id,
            "calibration": arms["c"].run_id,
            "calibration_arm": spec.calibration_arm,
        },
        "calibration": fixed["calibration"],
        "task_types": task_types,
        "note": calibrated.NOT_A_CANDIDATE_NOTE,
    }


def build_report(patterns: Mapping[str, str]) -> dict[str, Any]:
    """7 本の腕から §5 の判定表を組む。**7 本すべてが要る**(ADR-087 決定1)。"""
    missing = [spec.option for spec in ARM_SPECS if not patterns.get(spec.name)]
    if missing:
        raise SelectError(
            f"腕 {missing} が渡されていない。§5 の判定表は 7 本すべてが要る(ADR-087 決定1) —— "
            "腕が欠けた表は「候補が無かった」「満たさなかった」「測っていない」を 1 つに潰す"
        )
    arms = {spec.name: load_arm(spec, patterns[spec.name]) for spec in ARM_SPECS}
    check_preambles(arms)
    settings = settings_of(arms)
    calibration = calibrated.load_calibration(arms["c"].metrics_path)
    check_calibration_arms(calibration)
    reports = Reports(arms, calibration)
    selections = [select_for(task, reports, settings, arms) for task in JUDGED_TASK_TYPES]
    return {
        "created_at": utc_now().isoformat(),
        "note": REPORT_NOTE,
        "criteria_note": CRITERIA_NOTE,
        "settings": settings.as_dict(),
        "arms": [arms[spec.name].provenance() for spec in ARM_SPECS],
        "task_types": selections,
        "preamble_mismatch": preamble_mismatch(selections),
        "preamble_mismatch_note": MISMATCH_NOTE,
        "descriptive": [describe(spec, reports, arms) for spec in DESCRIPTIVE],
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def _rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _mark(passed: bool | None) -> str:
    return "—" if passed is None else ("満たす" if passed else "満たさない")


def _criteria_lines(criteria: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for row in criteria["i"]["cells"]:
        lines.append(
            f"      (i)   {row['coverage']:<17} n={row['n']:<4} "
            + " ".join(f"{name}={_rate(row[f'{name}_rate'])}" for name in CLASSES)
            + f" fails={row['fails']}"
        )
    for row in criteria["ii"]["cells"]:
        lines.append(
            f"      (ii)  {row['coverage']:<17} n={row['n']:<4} "
            f"correct={_rate(row['correct_rate'])} "
            f"always_yes={_rate(row['always_yes'])} always_no={_rate(row['always_no'])} "
            f"fails={row['fails']}"
        )
    if criteria["iii"]["applicable"]:
        for row in criteria["iii"]["parse_fail"]:
            lines.append(
                f"      (iii) #1 {row['group']:<20} n={row['n']:<4} "
                f"parse_fail={_rate(row['parse_fail_rate'])} fails={row['fails']}"
            )
        for row in criteria["iii"]["cells"]:
            lines.append(
                f"      (iii) #2 {row['task']:<4} {row['coverage']:<17} n={row['n']:<4} "
                f"correct={_rate(row['correct_rate'])} fails={row['fails']}"
            )
    for row in criteria["iv"]["cells"]:
        low, high = row[r8_fit.LOW], row[r8_fit.HIGH]
        lines.append(
            f"      (iv)  {row['coverage']:<17} "
            f"低い側 n={low['n']:<4} correct={_rate(low['correct_rate'])} "
            f"高い側 n={high['n']:<4} correct={_rate(high['correct_rate'])} fails={row['fails']}"
        )
    return lines


def _near_tie_lines(near_tie: Mapping[str, Any] | None) -> list[str]:
    """感度の行(**合否には使わない**)。幅を宣言していない run では 1 行だけ出す。"""
    if near_tie is None:
        return []
    if near_tie["fixed"] is None and near_tie["sweep"] is None:
        return [f"      感度: なし(config に {gonogo.NEAR_TIE_MARGIN_KEY} が無い)"]
    lines = [f"      感度(近接同点 |差| ≤ {near_tie['margin']}。合否には使わない)"]
    for row in near_tie["fixed"] or []:
        without = row["without_near_tie"]
        lines.append(
            f"        固定 {row['coverage']:<17} near_tie={row['n_near_tie']:<4}/{row['n']:<4} "
            f"除いた correct={_rate(without['correct_rate'])} #2 の印={without['fails']}"
        )
    for row in near_tie["sweep"] or []:
        low, high = row["sides"][r8_fit.LOW], row["sides"][r8_fit.HIGH]
        lines.append(
            f"        掃引 {row['coverage']:<17} "
            f"低い側 near_tie={low['n_near_tie']}/{low['n']} "
            f"correct={_rate(low['without_near_tie']['correct_rate'])} "
            f"高い側 near_tie={high['n_near_tie']}/{high['n']} "
            f"correct={_rate(high['without_near_tie']['correct_rate'])}"
        )
    return lines


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人間が読む表(標準出力)。**4値を揃えて出す**(`CLAUDE.md` §6)。"""
    settings = report["settings"]
    lines: list[str] = [report["note"], ""]
    lines.append(
        f"閾値: correct_rate >= {settings['min_cell_correct_rate']} / "
        f"parse_fail_rate < {settings['parse_fail_max']} / "
        f"近接同点の幅 = {settings['near_tie_margin']}"
    )
    lines.append("腕(名前からは照合しない。記録の形で照合した)")
    for arm in report["arms"]:
        sha = arm["preamble_sha256"]
        lines.append(
            f"  {arm['arm']:<11} run={arm['run_id']} kind={arm['kind']} "
            f"templates={arm['template_set']} preamble={'なし' if sha is None else sha[:12]} "
            f"task_subset={arm['task_subset']} pool={arm['pool_id']} adapter={arm['adapter']}"
        )
    for block in report["task_types"]:
        lines.append("")
        lines.append(
            f"=== {block['task_type']}: 採る候補 = {block['selected'] or 'なし'}"
            f"(候補なし={block['no_candidate']})"
        )
        for row in block["candidates"]:
            if not row["applicable"]:
                lines.append(
                    f"  {row['candidate']:<4} {row['label']:<18} — このタスク型に候補は無い"
                    "(満たさなかったのではない)"
                )
                continue
            marks = " ".join(
                f"({key})={_mark(row['criteria'][key]['passed'])}"
                for key in ("i", "ii", "iii", "iv")
            )
            lines.append(
                f"  {row['candidate']:<4} {row['label']:<18} {_mark(row['passed'])} | {marks}"
            )
            lines.extend(_criteria_lines(row["criteria"]))
            lines.extend(_near_tie_lines(row["near_tie"]))
    lines.append("")
    lines.append(
        f"T3 と T1b で ① の有無の食い違い: {report['preamble_mismatch']}"
        f"({report['preamble_mismatch_note']})"
    )
    lines.append("")
    lines.append("記述(§5 の候補ではない。合否の印は付けない。ADR-079 決定6 / ADR-086 決定1)")
    for block in report["descriptive"]:
        lines.append(
            f"  --- {block['name']}({block['label']}。"
            f"較正の腕={block['runs']['calibration_arm']})"
        )
        for entry in block["task_types"]:
            for row in entry["cells"]:
                lines.append(
                    f"      {entry['task_type']:<4} {row['coverage']:<17} n={row['n']:<4} "
                    + " ".join(f"{name}={_rate(row[f'{name}_rate'])}" for name in CLASSES)
                )
            for row in entry["far_offset_correct"]:
                low, high = row[r8_fit.LOW], row[r8_fit.HIGH]
                lines.append(
                    f"      {entry['task_type']:<4} {row['coverage']:<17} 遠い 低い側="
                    f"{_rate(low['correct_rate'])} 高い側={_rate(high['correct_rate'])}"
                )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLAN-026 §5 の判定表(I11c)")
    for spec in ARM_SPECS:
        parser.add_argument(spec.option, dest=spec.name, default=None, help=f"{spec.help} の run")
    parser.add_argument(
        "--out-dir", type=Path, default=None, help=f"指定すると {OUTPUT_FILENAME} を書く"
    )
    args = parser.parse_args(argv)

    report = build_report({spec.name: getattr(args, spec.name) for spec in ARM_SPECS})
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
