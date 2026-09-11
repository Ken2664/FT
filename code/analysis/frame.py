"""長形式表(1行 = 1項目 × 1評価 run)を `runs/` の成果物から組む(PLAN-017)。

答える問い: 「`Documents/05_STATISTICS.md` §3.2 のモデルが要求する長形式表を、
`runs/` に残った成果物から、どういう規則で組むのか」

    python -m code.analysis.frame --runs "runs/*exp003*" --dry-run
    python -m code.analysis.frame --runs "runs/*exp003*" --out-dir results/frame_exp003

**組むだけで、当てはめない**(skill code-style §2)。当てはめは
`code/analysis/primary.py`(未実装。PLAN-016 §7-5)と R 側(ADR-058 決定1)の仕事である。

**絞り込まない**(ADR-062 決定4 = PLAN-017 E-4 案 (a))。全 run・全群・全被覆水準を
1枚に出し、主軸の subset は解析側が行う。frame が解析ごとに分岐すると
**「どの行が落ちたか」が2箇所に散る。**その代わり、**主軸に入らない行の件数を
run ごとに数えて残す**(ADR-062 決定1 の付帯条件)。黙って落とすと、
項目数が静かに減っていても気付けない。

**層をまたぐ import について**(skill code-style §2 の例外)。本モジュールは
`code/eval/battery/` の `task_type_of` を2本そのまま呼ぶ。**ADR-062 決定3
(= E-3 案 (c))で人間がそう決めた** —— 写像表を3つ目に作るとずれるためである。

入力の在り処(PLAN-017 §3.3):

    runs/<run_id>/metrics.json          seed / lesion_condition / kind
    runs/<run_id>/config.yaml           data.matched_manifests / data.train_domain_max
    runs/<run_id>/predictions/*.jsonl   1行1応答  ★git に無い(PLAN-017 F79)
    data/generated/ft/<data_id>_<cond>/manifest.json
                                        coverage.pairs(= K)/ coverage.pairs_hash

**`predictions/` は `.gitignore` で外れている。**この表は repo だけからは
再現できず、永続ボリューム側の `predictions/` が要る。だから出力を
`results/` に凍結する(ADR-062 決定7 = E-7 案 (c))。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from code.analysis.aggregate import EVAL_KIND, METRICS_FILENAME, expand_metrics_paths
from code.artifacts import PREDICTIONS_DIR, utc_now
from code.config import load_config, require
from code.data_gen.eval_pool import (
    load_condition_manifest,
    load_coverage_pairs,
    load_coverage_sums,
)
from code.data_gen.pool import (
    MAIN_COVERAGE_LEVELS,
    Pair,
    label_answer_range,
    label_main_coverage,
    label_t_coverage,
    pairs_hash,
)
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.rates import CORRECT, RULE

CONFIG_FILENAME = "config.yaml"
CSV_FILENAME = "frame.csv"
FRAME_MANIFEST_FILENAME = "frame_manifest.json"

# 主軸のタスク型4水準(ADR-026)。`t1_instructed` と特異性対照はここに無い。
MAIN_TASK_TYPES: tuple[str, ...] = (
    numeric_sum.T1,
    numeric_sum.T2,
    t3_comparison.T3,
    t3_comparison.T1B,
)

# 特異性対照(`spec_sub` / `spec_mul`)に付けるタスク型の印。
# **タスク型を持たない**ので、`t1_instructed` のように名前で落とすことができない
# (PLAN-017 F72)。黙って落とさず、明示的に「主軸外」と書く。
OFF_MAIN_AXIS = "off_main_axis"

# 主軸から落ちた理由。**件数を run ごとに数えて残す**(ADR-062 決定1 の付帯条件)。
DROP_TASK = "task_off_main_axis"
DROP_COVERAGE = "coverage_off_main_axis"
DROP_SEED = "seed_missing"
DROP_REASONS: tuple[str, ...] = (DROP_TASK, DROP_COVERAGE, DROP_SEED)

# ★再正規化 DV の分母(2026-09-08。ADR-064 決定3 (i) = ★J 案 (c) の (i)。
# 提案 エージェント (Opus) / 採択 人間)。**`rule / (correct + rule)` の感度解析**を
# §4 の探索的な欄に事前登録したので、その分母に入るかどうかを行ごとに残す。
# **主解析の DV は `is_rule`(分母は全項目)のままである** —— 再正規化は
# 処置後変数(`other_error` / `parse_fail` になったかどうか)での条件付けなので、
# 主解析にはできない。**併記のみ。食い違ったら両方報告する**(ADR-055 決定3 と同型)。
#
# 使い方: `subset(primary, in_renorm_denom == 1)` に §3.2 と同じモデルを当てる。
# **列を1本足すだけにしてあるのは、DV を2本持たせると採点の規則が2箇所に
# 分かれるからである**(F73 と同じ理由)。
RENORM_DENOM_CLASSES: tuple[str, ...] = (CORRECT, RULE)

# CSV の列。**順序を固定する** —— 解析側が位置で読む余地を作らないためではなく、
# 差分が読める形でファイルに残るようにするためである。
COLUMNS: tuple[str, ...] = (
    "run_id",
    "condition",
    "seed",
    "item",
    "task",
    "template",
    "category",
    "group",
    "coverage",
    "answer_range",
    "t_coverage",
    "carry",
    "is_rule",
    "in_renorm_denom",
    "classification",
    "parsed",
    "truth",
    "reference_rule",
    "main_axis",
    "gate_id_rule_rate",
    "gate_id_n",
)


class FrameError(ValueError):
    """長形式表を組めない。取り違えたまま数値を出すより止める。"""


# --------------------------------------------------------------------------
# category の写像(ADR-062 決定2 / 決定3)
# --------------------------------------------------------------------------


def task_type_of(category: str) -> str:
    """`category` からタスク型を引く(ADR-062 決定3 = E-3 案 (c))。

    答える問い: 「この項目は §3.2 の `task` のどの水準か。主軸の外か」

    **写像表を作らない。**既存の `task_type_of` 2本をそのまま呼ぶ
    (`numeric_sum` :120 / `t3_comparison` :116)。2つの `CATEGORY_AXES` は
    キーが互いに素であり、無いのは束ねる1箇所だけである(PLAN-017 F70)。

    **`group` からは決まらない**(F69)。`comparison` 群は T3 と T1b の
    両方を含む。タスク型は `category` から読む。

    **未知の `category` で必ず落ちる。**素通しすると、綴りを間違えた
    水準が1つ増えたまま交互作用が当たってしまう。
    """
    if category in numeric_sum.CATEGORY_AXES:
        return numeric_sum.task_type_of(category)
    if category in t3_comparison.CATEGORY_AXES:
        return t3_comparison.task_type_of(category)
    if category in specificity_control.CATEGORIES:
        # 特異性対照は加算ではないのでタスク型を持たない(F72)。
        return OFF_MAIN_AXIS
    raise FrameError(
        f"未知の category: {category!r}。"
        f"あるのは {sorted(numeric_sum.CATEGORY_AXES)} / "
        f"{sorted(t3_comparison.CATEGORY_AXES)} / {sorted(specificity_control.CATEGORIES)}"
    )


def template_of(category: str) -> str:
    """`category` をそのまま `template` の水準とする(ADR-062 決定2 = E-2 案 (a))。

    答える問い: 「この項目は `(1 | template)` のどの水準か」

    **主軸は10水準である**: `t1` 1 + `t2_*` 5 + `t3_gt` / `t3_lt` 2 +
    `t1b_gt` / `t1b_lt` 2(`Documents/05_STATISTICS.md` §3.2、§3.2.2)。
    恒等写像だが**関数として置く** —— この選択は人間の決定であり、
    変えるなら1箇所で変わる必要がある。

    **★記録として残す(ADR-062 のリスク欄)**: 極性(`gt` / `lt`)は
    応答バイアス対策として均衡させた設計因子であり、ランダム効果の水準として
    扱ってよいかは未検証である。また `template` は `task` に入れ子であり、
    §3.2 が `(1 | template)` と交差の形で書いているのは実体と違う。
    """
    return category


def is_main_task(task: str) -> bool:
    """このタスク型は主軸の4水準か(ADR-026)。"""
    return task in MAIN_TASK_TYPES


# --------------------------------------------------------------------------
# run の入力(§4.1 の手順 1〜4)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RunInputs:
    """1つの評価 run について、被覆ラベルを付けるのに要るものすべて。"""

    run_id: str
    run_dir: Path
    condition: str
    seed: int | None
    main_radius: int
    coverage_pairs: frozenset[Pair]
    coverage_sums: frozenset[int]
    pairs_hash: str
    ft_manifest: str


def check_coverage_record(
    run_name: str, record: Mapping[str, Any] | None, manifest: Mapping[str, Any]
) -> None:
    """run が焼き込んだ K の記録(E-5 (b))が、辿った FT manifest(E-5 (a))と一致するか。

    答える問い: 「評価の時点で使うはずだった K と、いま解析で読んでいる K は同じか」

    **正本は (a) のままである**(ADR-062 決定5)。(b) は ADR-076 決定12 で足した記録で、
    ここでは照合にだけ使う。**食い違えば止める** —— 評価の後に FT データを作り直した
    (K が動いた)まま解析すると、被覆ラベルが評価のときと別の K で付く。
    **記録の無い run(2026-09-11 より前の run と掃引)は照合しない。**
    """
    if record is None:
        return
    expected = {
        "data_id": manifest["data_id"],
        "pairs_hash": manifest["coverage"]["pairs_hash"],
        "coverage_k": manifest["coverage"]["coverage_k"],
        "train_domain_hi": manifest["train_domain"]["hi"],
    }
    mismatched = {
        key: (record.get(key), value) for key, value in expected.items() if record.get(key) != value
    }
    if mismatched:
        raise FrameError(
            f"{run_name}: metrics.json の coverage(評価時の K の記録)と、config.yaml から辿った "
            f"FT manifest が食い違う: {mismatched}(記録, manifest)。評価の後に K が動いている"
            "(ADR-076 決定12 / ADR-062 決定5)。"
        )


def load_run(metrics_path: Path) -> RunInputs:
    """評価 run から K・`main_radius`・`seed`・条件を引く(PLAN-017 §4.1 の 1〜4)。

    答える問い: 「この run の項目に被覆ラベルを付けるための材料は揃っているか」

    **K は `runs/<id>/` に無い**(F76)。`config.yaml` の
    `data.matched_manifests` を `lesion.condition` で辿って FT manifest から読む
    (ADR-062 決定5 = E-5 案 (a))。規則は `eval_pool.load_condition_manifest`
    と同じもの —— **同じ関数を呼ぶ。**規則を書き写すと片方だけが直る。

    **`pairs_hash` を照合する**(F78。PLAN-017 §8 の1行目)。別条件の
    manifest を読んでも数値は普通に出てしまうので、ここで止める。

    **`seed` は訓練 run の seed である**(F75)。アダプタが無い run では
    `None` であり、**0 を置かない** —— 「シード 0 で回した」と読める記録になる。
    """
    run_dir = metrics_path.parent
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    kind = metrics.get("kind")
    if kind != EVAL_KIND:
        raise FrameError(
            f"{metrics_path} は kind={kind!r} であり {EVAL_KIND!r} ではない。"
            "4値分解を持つのは評価 run だけである。訓練 run や掃引を混ぜない。"
        )
    config_path = run_dir / CONFIG_FILENAME
    if not config_path.exists():
        raise FrameError(
            f"{config_path} が無い。K の出どころ(data.matched_manifests)を辿れない。"
        )
    config = load_config(config_path)

    condition = metrics["lesion_condition"]
    declared = require(config, "lesion.condition")
    if condition != declared:
        raise FrameError(
            f"{run_dir.name}: metrics.json の lesion_condition={condition!r} と "
            f"config.yaml の lesion.condition={declared!r} が食い違う。"
        )

    main_radius = int(require(config, "data.train_domain_max"))
    manifest = load_condition_manifest(config)
    domain_hi = int(manifest["train_domain"]["hi"])
    if domain_hi != main_radius:
        raise FrameError(
            f"{run_dir.name}: config の data.train_domain_max={main_radius} と "
            f"FT manifest の train_domain.hi={domain_hi} が食い違う。"
            "被覆ラベルの境界が2つあることになる(PLAN-017 E-5)。"
        )

    pairs = [(int(a), int(b)) for a, b in load_coverage_pairs(manifest)]
    recorded = manifest["coverage"]["pairs_hash"]
    recomputed = pairs_hash(pairs)
    if recomputed != recorded:
        raise FrameError(
            f"{run_dir.name}: FT manifest の coverage.pairs_hash={recorded} と "
            f"pairs から数え直した {recomputed} が食い違う。K を取り違えている。"
        )
    check_coverage_record(run_dir.name, metrics.get("coverage"), manifest)

    return RunInputs(
        run_id=metrics.get("run_id", run_dir.name),
        run_dir=run_dir,
        condition=condition,
        seed=metrics.get("seed"),
        main_radius=main_radius,
        coverage_pairs=frozenset(pairs),
        coverage_sums=frozenset(load_coverage_sums(manifest)),
        pairs_hash=recorded,
        ft_manifest=str(manifest.get("data_id", "")),
    )


def read_predictions(run_dir: Path) -> list[dict[str, Any]]:
    """`predictions/*.jsonl` を1行ずつ読む。

    答える問い: 「この run が残した応答は何件か」

    **0件で止める** —— 空の表を「差が無かった」と読ませない(aggregate と同じ規約)。
    """
    directory = run_dir / PREDICTIONS_DIR
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")) if directory.is_dir() else []:
        with path.open(encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    if not records:
        raise FrameError(
            f"{directory} に応答が1件も無い。"
            "predictions/ は .gitignore で外れている(PLAN-017 F79)ので、"
            "永続ボリューム側の run を指しているか確かめること。"
        )
    return records


# --------------------------------------------------------------------------
# 行を組む(§4.1 の手順 5〜6)
# --------------------------------------------------------------------------


@dataclass
class RunSummary:
    """1つの run について、何行組んで、何行が主軸から落ちたか。"""

    run_id: str
    condition: str
    seed: int | None
    main_radius: int
    pairs_hash: str
    ft_manifest: str
    n_rows: int = 0
    n_main_axis: int = 0
    n_by_coverage: dict[str, int] = field(default_factory=dict)
    n_by_task: dict[str, int] = field(default_factory=dict)
    n_dropped_by_reason: dict[str, int] = field(default_factory=dict)
    gate_id_rule_rate: float | None = None
    gate_id_n: int = 0
    gate_id_by_task: dict[str, dict[str, float | int]] = field(default_factory=dict)

    @property
    def n_dropped(self) -> int:
        return self.n_rows - self.n_main_axis

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "condition": self.condition,
            "seed": self.seed,
            "main_radius": self.main_radius,
            "pairs_hash": self.pairs_hash,
            "ft_manifest": self.ft_manifest,
            "n_rows": self.n_rows,
            "n_main_axis": self.n_main_axis,
            "n_dropped": self.n_dropped,
            "n_dropped_by_reason": dict(self.n_dropped_by_reason),
            "n_by_coverage": dict(self.n_by_coverage),
            "n_by_task": dict(self.n_by_task),
            "gate_id_rule_rate": self.gate_id_rule_rate,
            "gate_id_n": self.gate_id_n,
            "gate_id_by_task": dict(self.gate_id_by_task),
        }


def pair_of(record: Mapping[str, Any]) -> Pair:
    """応答1件から被演算子の組を取る。

    答える問い: 「被覆ラベルを付ける (a, b) はどれか」

    先頭2つに限る。3項以上の項目はこの実験に無く、**あったら止める** ——
    黙って先頭2つを取ると、別の項目型が混ざったことに気付けない。
    """
    operands = record["operands"]
    if len(operands) != 2:
        raise FrameError(
            f"被演算子が2つでない項目が来た: {record.get('item_id')!r} operands={operands!r}"
        )
    return (int(operands[0]), int(operands[1]))


def build_rows(run: RunInputs, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """1つの run の応答を長形式の行にする(§4.1 の手順 5〜6)。

    答える問い: 「この run の各応答は、§3.2 のどのセルの、どの結果か」

    **`is_rule` は `classification == "rule"` で作る**(F73)。数え直さない ——
    採点の規則が2箇所に分かれる。

    **`in_renorm_denom` は再正規化 DV の感度解析の分母である**(ADR-064 決定3 (i))。
    `correct` と `rule` だけが 1 になる。**`is_rule` の分母は全項目のままで、
    こちらは変えない** —— 主解析は §2 の定義(4値の合計が 1.0)に従う。

    **`answer_range` / `t_coverage` は被演算子の和 `a+b` について付く。**
    特異性対照(`spec_sub` / `spec_mul`)の答えは和ではないので、
    **これらの列はその項目の答えについての値ではない。**主軸外の印
    (`main_axis` が偽)と `group` で見分けること。
    """
    rows: list[dict[str, Any]] = []
    for record in records:
        pair = pair_of(record)
        category = record["category"]
        task = task_type_of(category)
        coverage = label_main_coverage(pair, run.coverage_pairs, run.main_radius)
        main_axis = (
            is_main_task(task) and coverage in MAIN_COVERAGE_LEVELS and run.seed is not None
        )
        rows.append(
            {
                "run_id": run.run_id,
                "condition": run.condition,
                "seed": run.seed,
                "item": record["item_id"],
                "task": task,
                "template": template_of(category),
                "category": category,
                "group": record["group"],
                "coverage": coverage,
                "answer_range": label_answer_range(pair, run.main_radius),
                "t_coverage": label_t_coverage(pair, run.coverage_sums),
                "carry": record["carry"],
                "is_rule": int(record["classification"] == RULE),
                "in_renorm_denom": int(record["classification"] in RENORM_DENOM_CLASSES),
                "classification": record["classification"],
                "parsed": record["parsed"],
                "truth": record["truth"],
                "reference_rule": record["reference_rule"],
                "main_axis": main_axis,
                # 門の生の量は run 単位なので、行を組み終えてから埋める。
                "gate_id_rule_rate": None,
                "gate_id_n": 0,
            }
        )
    return rows


def gate_id_rates(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, int, dict[str, Any]]:
    """解析門の**生の量**(run ごとの `id` 到達度)を出す(ADR-062 決定6 = E-6 案 (c))。

    答える問い: 「この run は `id` の項目でどれだけ規則を出したか」

    **二値化しない。閾値も置かない**(N5 / ADR-054 決定1 (ii) が未決)。
    黙って `True` を置くと、決まっていない門を通ったことになってしまう。
    **`passes_analysis_gate` 列はここでは作らない** —— 二値化は
    `code/analysis/primary.py` の仕事である。

    **★S1(`id` 到達度を何で測るか)も未決である**(ADR-054 のリスク欄。
    `#4` / `#4b` の実体は `T1 × id` だが、4タスク型に広げる案が残っている)。
    どちらにも決めないため、**プール値とタスク型ごとの内訳の両方を残す。**
    `#4` / `#4b` に合わせるならタスク型 `t1` の内訳を読むこと。
    """
    id_rows = [row for row in rows if row["coverage"] == "id"]
    by_task: dict[str, dict[str, float | int]] = {}
    for task in sorted({row["task"] for row in id_rows}):
        subset = [row for row in id_rows if row["task"] == task]
        by_task[task] = {
            "n": len(subset),
            "rule_rate": sum(row["is_rule"] for row in subset) / len(subset),
        }
    if not id_rows:
        return None, 0, by_task
    return sum(row["is_rule"] for row in id_rows) / len(id_rows), len(id_rows), by_task


def summarize_run(run: RunInputs, rows: Sequence[dict[str, Any]]) -> RunSummary:
    """1つの run の件数を数える。**主軸から落ちた行を理由別に残す。**

    答える問い: 「この run から何行組めて、そのうち何行が主軸に入るのか」

    黙って落とすと、項目数が静かに減っていても気付けない
    (ADR-062 決定1 の付帯条件)。
    """
    summary = RunSummary(
        run_id=run.run_id,
        condition=run.condition,
        seed=run.seed,
        main_radius=run.main_radius,
        pairs_hash=run.pairs_hash,
        ft_manifest=run.ft_manifest,
        n_rows=len(rows),
        n_main_axis=sum(1 for row in rows if row["main_axis"]),
        n_dropped_by_reason=dict.fromkeys(DROP_REASONS, 0),
    )
    for row in rows:
        summary.n_by_coverage[row["coverage"]] = summary.n_by_coverage.get(row["coverage"], 0) + 1
        summary.n_by_task[row["task"]] = summary.n_by_task.get(row["task"], 0) + 1
        if row["main_axis"]:
            continue
        # 理由は排他ではない。1行が2つ以上の理由で落ちることがあるので、
        # 理由ごとに独立に数える(合計は n_dropped と一致しない)。
        if not is_main_task(row["task"]):
            summary.n_dropped_by_reason[DROP_TASK] += 1
        if row["coverage"] not in MAIN_COVERAGE_LEVELS:
            summary.n_dropped_by_reason[DROP_COVERAGE] += 1
        if row["seed"] is None:
            summary.n_dropped_by_reason[DROP_SEED] += 1
    rate, n_id, by_task = gate_id_rates(rows)
    summary.gate_id_rule_rate = rate
    summary.gate_id_n = n_id
    summary.gate_id_by_task = by_task
    for row in rows:
        row["gate_id_rule_rate"] = rate
        row["gate_id_n"] = n_id
    return summary


# --------------------------------------------------------------------------
# 表全体
# --------------------------------------------------------------------------


@dataclass
class Frame:
    """長形式表と、それを組んだときの記録。"""

    rows: list[dict[str, Any]]
    runs: list[RunSummary]
    problems: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": list(COLUMNS),
            "n_rows": len(self.rows),
            "n_runs": len(self.runs),
            "run_ids": [summary.run_id for summary in self.runs],
            "pairs_hashes": sorted({summary.pairs_hash for summary in self.runs}),
            "runs": [summary.as_dict() for summary in self.runs],
            "problems": list(self.problems),
        }


def check_item_sets(
    runs: Sequence[RunSummary], item_sets: Mapping[str, frozenset[str]]
) -> list[str]:
    """run 間で項目集合が一致しているか(§3.2.1 の生きている制約)。

    答える問い: 「この表の中で run どうしを比べてよいか」

    条件間で項目集合が変わると `(1 | item)` が条件と交絡する(PLAN-001 §3)。
    **落ちるべき箇所である。**ただしここでは例外を投げず、問題として返す ——
    `--dry-run` は問題を「数える」ためにあるので、途中で止まると役に立たない。
    """
    if len(item_sets) < 2:
        return []
    reference_id = runs[0].run_id
    reference = item_sets[reference_id]
    problems: list[str] = []
    for summary in runs[1:]:
        current = item_sets[summary.run_id]
        if current == reference:
            continue
        problems.append(
            f"項目集合が {reference_id} と {summary.run_id} で一致しない "
            f"({reference_id} のみ {len(reference - current)} 件 / "
            f"{summary.run_id} のみ {len(current - reference)} 件)。"
            "比較する解析の内部では項目集合が完全に一致していること"
            "(Documents/05_STATISTICS.md §3.2.1)"
        )
    return problems


def build_frame(metrics_paths: Iterable[Path]) -> Frame:
    """長形式表を組む(§4.1 の6手順)。

    答える問い: 「渡された run から、§3.2 に渡せる1枚の表が組めるか」
    """
    rows: list[dict[str, Any]] = []
    summaries: list[RunSummary] = []
    item_sets: dict[str, frozenset[str]] = {}
    for metrics_path in metrics_paths:
        run = load_run(metrics_path)
        run_rows = build_rows(run, read_predictions(run.run_dir))
        summaries.append(summarize_run(run, run_rows))
        item_sets[run.run_id] = frozenset(row["item"] for row in run_rows)
        rows.extend(run_rows)
    return Frame(rows=rows, runs=summaries, problems=check_item_sets(summaries, item_sets))


# --------------------------------------------------------------------------
# 出力(ADR-062 決定7 = E-7 案 (c))
# --------------------------------------------------------------------------


def write_frame(frame: Frame, out_dir: Path) -> tuple[Path, Path]:
    """CSV とその記録を `results/` に書く(ADR-062 決定7)。

    答える問い: 「主要検定の入力そのものを、後から同じものだと確かめられるか」

    `CLAUDE.md` §2 は「すべての数値は `results/` のファイルと run_id に
    紐づくこと」を求めている。**主要検定の入力がその対象である。**
    残すのは CSV・その sha256・入力 run_id の一覧・FT manifest の `pairs_hash`。

    **問題があるまま書かない。**項目集合が食い違ったままの表を凍結すると、
    それが「入力の記録」として後の解析に効いてしまう。
    """
    if frame.problems:
        raise FrameError(
            "問題があるまま表を凍結しない: " + " / ".join(frame.problems)
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / CSV_FILENAME
    # newline="" は csv モジュールの規約(Windows で CR CR LF になるのを防ぐ)。
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(frame.rows)
    payload = frame.as_dict()
    payload["created_at"] = utc_now().isoformat()
    payload["csv"] = CSV_FILENAME
    payload["csv_sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest_path = out_dir / FRAME_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return csv_path, manifest_path


def report_lines(frame: Frame) -> list[str]:
    """件数だけの報告(`--dry-run` の本体)。

    答える問い: 「この指定で何行組めて、そのうち何行が主軸に入るのか」
    """
    lines = [f"run {len(frame.runs)} 件 / 行 {len(frame.rows)} 件", ""]
    lines.append(
        f"{'run_id':<28} {'cond':<6} {'seed':>5} {'rows':>7} {'main':>7} "
        f"{'dropped':>8} {'id_rule':>8}"
    )
    for summary in frame.runs:
        seed = "None" if summary.seed is None else str(summary.seed)
        gate = "—" if summary.gate_id_rule_rate is None else f"{summary.gate_id_rule_rate:.4f}"
        lines.append(
            f"{summary.run_id:<28} {summary.condition:<6} {seed:>5} "
            f"{summary.n_rows:>7} {summary.n_main_axis:>7} {summary.n_dropped:>8} {gate:>8}"
        )
        reasons = ", ".join(
            f"{reason}={summary.n_dropped_by_reason.get(reason, 0)}" for reason in DROP_REASONS
        )
        lines.append(f"{'':<28} 落ちた理由(排他ではない): {reasons}")
        coverage = ", ".join(
            f"{key}={value}" for key, value in sorted(summary.n_by_coverage.items())
        )
        lines.append(f"{'':<28} 被覆: {coverage}")
    if frame.problems:
        lines.append("")
        lines.append("★問題:")
        lines.extend(f"  - {problem}" for problem in frame.problems)
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="長形式表を組む(PLAN-017)")
    parser.add_argument(
        "--runs",
        required=True,
        action="append",
        help='repo ルートからの glob。例: "runs/*exp003*"。複数回渡せる',
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="CSV と記録を書く先。渡さなければ件数だけを出す",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="件数だけを出し、ファイルを書かない",
    )
    args = parser.parse_args(argv)

    frame = build_frame(expand_metrics_paths(args.runs))
    for line in report_lines(frame):
        print(line)
    if frame.problems:
        return 1
    if args.dry_run or args.out_dir is None:
        return 0
    csv_path, manifest_path = write_frame(frame, args.out_dir)
    print(f"\n書き出した: {csv_path}")
    print(f"書き出した: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
