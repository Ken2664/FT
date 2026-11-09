"""実データの主要解析(PLAN-048 / ADR-138。PLAN-016 §7-5 の `primary.py`)。

答える問い: 「`p2` の T1・T2 × 3 既知性の 6 セルで、`task:coverage` の LRT(df = 2)は実施でき、
実施できるなら p 値はいくつか —— 実施できないなら、なぜ(df・天井・当てはめ失敗)か」

    python -m code.analysis.primary --simulate
    python -m code.analysis.primary --shuffle-labels --seed 0
    python -m code.analysis.primary --frame-dir results/<frame> --order6-gonogo results/<gonogo>/gonogo.json

**順は固定である**(ADR-137 決定2・ADR-139 決定3): 主軸の subset(W1)→ 解析門(W8。感度だけ)→ 適格性フィルタ(W2)→
df のランク規則(W3)→ 天井の規則(W4)→ 当てはめ(W5)→ TOST(W7)。判定は `実施可` / `実施不能: df < 2` /
`実施不能: 天井` / `実施不能: 当てはめ失敗` / `実施不能: 解析門`(感度だけ)のどれか 1 つで、**p 値は `実施可` の行にだけ表に出す**
(ADR-137 決定3・ADR-138 決定6)。すべての値は `primary.json` に残る。**結果の読みは書かない**(`CLAUDE.md` §8)。

**当てはめはここで実装しない**: `power_sim_fit.R` を変えずに `power_sim.write_fit_manifest` / `run_fits` で呼ぶ
(ADR-138 決定2)。縮退順序・ADR-059 の閾値・床の `allFit`・R と lme4 の版・有意水準・`tost_alpha` は
`configs/power_sim.yaml` の値を読み、`configs/primary.yaml` に持たない(値を 2 か所に書かない)。
**層をまたぐ import について**(skill code-style §2 の例外): 本モジュールは `power_sim`(当てはめの呼び出しと
`draw_frame`・`equivalence_margin`)・`ceiling`(天井の規則)・`frame`(列と `CORRECT`)を呼ぶ。
ADR-138 決定2・決定5 で人間がそう決めた —— 写しを作ると run3 の検出力と実データの手続きがずれる。

**解析門(W8。ADR-139)**: 主要検定は門なしが**主**(今のシード数の検査 `design.n_seed` のまま)で、門を通った run
だけで同じ手続きを当てたものを**感度解析**として併記する(探索的。Holm に入れない。主と感度が食い違えば両方を報告する)。
量は `analysis_gate.task` × 基準水準 `id` の `rule_rate`(run ごと)、`>= analysis_gate.threshold` で通過。
門ありの側で残った `p2` の run が `analysis_gate.min_runs`(k)本未満なら `実施不能: 解析門`。
`--simulate` と `--shuffle-labels` は門を掛けず、run ごとの量を記録するだけ(ADR-138 決定3)。
未決の値はもう無い(frame の在り処 `input.frame_dir` は ADR-140 で決まった)。実データの実行が止まるのは、
本実験の frame がまだ無いからである(`read_frame` が理由を出して止まる)。
結果の `primary.json` の meta と `report.md` には、読んだ frame の在り処(repo 相対)と `csv_sha256` が残る(ADR-140 決定4)。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import operator
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from code import artifacts
from code.analysis import ceiling, frame, power_sim
from code.config import REPO_ROOT, ConfigError, load_config, require, resolve_repo_path
from code.data_gen.pool import COVERAGE_ID
from code.rates import CORRECT

DEFAULT_CONFIG = Path("configs/primary.yaml")
PRIMARY_JSON = "primary.json"
REPORT_MD = "report.md"
PRIMARY_CONFIG_COPY = "config_primary.yaml"
POWER_CONFIG_COPY = "config_power_sim.yaml"
FIT_DIR = "fit"
TABLE_CSV = "primary_table.csv"
FIT_JSON = "fit.json"

# 判定(ADR-138 決定6)。表の最初の列に出す
VERDICT_OK = "実施可"
VERDICT_DF = "実施不能: df < 2"
VERDICT_CEILING = "実施不能: 天井"
VERDICT_FIT = "実施不能: 当てはめ失敗"
VERDICT_GATE = "実施不能: 解析門"   # 感度解析だけが取る(門を通った run が k 本未満。ADR-139 決定3)

# 適格性フィルタで落ちた理由(ADR-076 決定1 の和集合)
REASON_REFERENCE = "ident"
REASON_ORDER6 = "order6_go_nogo_2"
PENDING_ORDER6_LIST = "input.order6_dropped_cells: 人間が確定した、順6 の #2 で落とすセルの一覧([] は「落とすセルは無い」)"

# `power_sim_fit.R` が基準水準として書き込んでいる被覆(F2)。TOST は基準以外の係数を見る
BASELINE_COVERAGE = COVERAGE_ID
# LRT の自由度の下限(ADR-112 決定1)。これ未満なら実施不能
MIN_DF = 2

# 解析門の role / direction の値(ADR-139)。config がこれ以外なら止まる(決めていない手続きを黙って走らせない)
GATE_ROLE_SENSITIVITY = "sensitivity"
GATE_DIRECTIONS: dict[str, Callable[[float, float], bool]] = {"ge": operator.ge}
# 感度解析の当てはめの作業ディレクトリは、主のそれの隣に置く
SENSITIVITY_DIR_SUFFIX = "_gate"

ACTUAL_LABEL = "actual"   # 実データの対象のラベル(報告・primary.json のキー)
MODE_ACTUAL = "actual"
MODE_SIMULATE = "simulate"
MODE_SHUFFLE = "shuffle"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PENDING = 2

SEED_PREFIX = "s"
SEED_DIGITS = 2

NOTE_RANDOM_EFFECT = (
    "ランダム効果は `(0 + coverage | seed)` の単独表記で、`(1 | seed)` を併記しない(ADR-066 決定1)。"
)
NOTE_P_VALUE = (
    "p 値と TOST の欄は判定が `実施可` の行だけ埋める。天井・当てはめ失敗の行の値は `primary.json` にある(ADR-137 決定3)。"
)

Cell = tuple[str, str]   # (task, coverage)
Fitter = Callable[[Sequence[tuple[Any, ...]], Path], dict[str, Any]]


class PrimaryError(RuntimeError):
    """主要解析を続けられない(入力が照合に通らない・順が崩れる・当てはめの出力が食い違う)。"""


class PendingDecisionError(PrimaryError):
    """実データの実行に要る値が `null`(未決)のまま。値は凍結の場で人間が決める(ADR-138 決定3)。"""


# --------------------------------------------------------------------------
# config(I1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Spec:
    """主解析の定義。答える問い: どの行・どの閾値で、どの水準の検定を行うか(値はすべて config から)。"""

    condition: str
    reference_condition: str
    tasks: tuple[str, ...]
    coverages: tuple[str, ...]
    n_seed: int
    min_reference_correct_rate: float
    alpha: float
    tost_alpha: float
    delta: float | None
    gate_threshold: float | None
    gate_task: str
    gate_direction: str
    gate_min_runs: int

    @property
    def cells(self) -> tuple[Cell, ...]:
        return tuple((t, c) for t in self.tasks for c in self.coverages)


def declared(config: Mapping[str, Any], dotted_key: str) -> Any:
    """config の項目を取り出す。答える問い: キーは宣言されているか(`null` は許す。未決として読む)。"""
    node: Any = config
    for key in dotted_key.split("."):
        if not isinstance(node, Mapping) or key not in node:
            raise ConfigError(f"config に {dotted_key} が無い")
        node = node[key]
    return node


def load_power_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """答える問い: 当てはめの設定(`fit` 節など)はどこから読むか(`configs/power_sim.yaml` だけ)。"""
    return load_config(resolve_repo_path(require(config, "power_sim_config")))


def load_spec(config: Mapping[str, Any], power_config: Mapping[str, Any]) -> Spec:
    """config から主解析の定義を組む。答える問い: 決まっている値はすべて埋まっているか。

    `analysis_gate.threshold` と `tost.delta` は `null` を許す(ここでは読むだけ。止めるのは `pending_decisions`)。
    門の役割・向きが実装している値でなければ止まる(ADR-139 決定1・2 以外の手続きを黙って走らせない)。
    """
    tasks = tuple(require(config, "design.tasks"))
    coverages = tuple(require(config, "design.coverages"))
    if BASELINE_COVERAGE not in coverages:
        raise ConfigError(f"design.coverages に基準水準 {BASELINE_COVERAGE!r} が無い(power_sim_fit.R の基準)")
    delta = declared(config, "tost.delta")
    threshold = declared(config, "analysis_gate.threshold")
    role, direction = str(require(config, "analysis_gate.role")), str(require(config, "analysis_gate.direction"))
    if role != GATE_ROLE_SENSITIVITY:
        raise ConfigError(f"analysis_gate.role は {GATE_ROLE_SENSITIVITY!r} だけ(ADR-139 決定1): {role!r}")
    if direction not in GATE_DIRECTIONS:
        raise ConfigError(f"analysis_gate.direction は {sorted(GATE_DIRECTIONS)} のどれか(ADR-139 決定2): {direction!r}")
    gate_task = str(require(config, "analysis_gate.task"))
    if gate_task not in tasks:
        raise ConfigError(f"analysis_gate.task {gate_task!r} が design.tasks {list(tasks)} に無い")
    return Spec(
        condition=str(require(config, "design.primary_condition")),
        reference_condition=str(require(config, "design.reference_condition")),
        tasks=tasks,
        coverages=coverages,
        n_seed=int(require(config, "design.n_seed")),
        min_reference_correct_rate=float(require(config, "eligibility.min_reference_correct_rate")),
        alpha=float(require(power_config, "simulation.alpha")),
        tost_alpha=float(require(power_config, "simulation.tost_alpha")),
        delta=None if delta is None else float(delta),
        gate_threshold=None if threshold is None else float(threshold),
        gate_task=gate_task,
        gate_direction=direction,
        gate_min_runs=int(require(config, "analysis_gate.min_runs")),
    )


def pending_decisions(
    config: Mapping[str, Any], frame_dir: Path | None, order6_gonogo: Path | None
) -> list[str]:
    """答える問い: 実データの実行に要る値のうち、まだ決まっていないものはどれか(空なら進める)。"""
    pending = []
    if frame_dir is None and declared(config, "input.frame_dir") is None:
        pending.append("input.frame_dir(または --frame-dir): 凍結した frame の在り処")
    if order6_gonogo is None and declared(config, "input.order6_gonogo") is None:
        pending.append("input.order6_gonogo(または --order6-gonogo): 順6 の Go/No-Go #2 の gonogo.json")
    if declared(config, "input.order6_dropped_cells") is None:
        pending.append(PENDING_ORDER6_LIST)
    if declared(config, "analysis_gate.threshold") is None:
        pending.append("analysis_gate.threshold: 解析門の閾値(N5。ADR-139 決定2)")
    if declared(config, "tost.delta") is None:
        pending.append("tost.delta: 平行性の TOST の Δ(ADR-139 決定4)")
    return pending


def require_decided(
    config: Mapping[str, Any], frame_dir: Path | None, order6_gonogo: Path | None
) -> None:
    """実データの実行の入口。答える問い: 決まっていない値を黙って通っていないか。

    `null` が 1 つでもあれば止まる(ADR-138 決定3)。全部決まっていれば何もしない
    (ADR-139 で門の閾値・順と Δ が決まったので、残る未決は frame の在り処だけ)。
    """
    pending = pending_decisions(config, frame_dir, order6_gonogo)
    if pending:
        raise PendingDecisionError("未決の値がある。実データの実行は止める(ADR-138 決定3):\n  - " + "\n  - ".join(pending))


# --------------------------------------------------------------------------
# 読み込みと照合(I2)
# --------------------------------------------------------------------------


def parse_frame_row(raw: Mapping[str, str]) -> dict[str, Any]:
    """答える問い: `frame.csv` の 1 行(文字列)を、解析が使う型にするとどうなるか。"""
    row: dict[str, Any] = dict(raw)
    row["seed"] = int(raw["seed"]) if raw["seed"] != "" else None
    row["is_rule"] = int(raw["is_rule"])
    row["main_axis"] = raw["main_axis"] == "True"
    row["gate_id_rule_rate"] = float(raw["gate_id_rule_rate"]) if raw["gate_id_rule_rate"] != "" else None
    row["gate_id_n"] = int(raw["gate_id_n"])
    return row


def read_frame(frame_dir: Path) -> list[dict[str, Any]]:
    """答える問い: 凍結した frame は、記録(ハッシュ・行数・問題)と一致するか。一致しなければ止まる。"""
    csv_path = frame_dir / frame.CSV_FILENAME
    manifest_path = frame_dir / frame.FRAME_MANIFEST_FILENAME
    for needed in (csv_path, manifest_path):
        if not needed.is_file():
            # config の input.frame_dir は凍結前から書いてある(ADR-140)。frame を作る前に走らせたら、
            # 生の FileNotFoundError ではなくここで理由を出して止まる
            raise PrimaryError(f"{needed} が無い。frame.py で凍結した frame_dir を指していない(ADR-140)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if digest != manifest["csv_sha256"]:
        raise PrimaryError(f"{csv_path} の sha256 が frame_manifest.json と違う(凍結後に書き換わっている)")
    if manifest.get("problems"):
        raise PrimaryError(f"frame_manifest.json に問題が記録されている: {manifest['problems']}")
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != frame.COLUMNS:
            raise PrimaryError(f"{csv_path} の列が frame.COLUMNS と違う: {reader.fieldnames}")
        rows = [parse_frame_row(raw) for raw in reader]
    if len(rows) != manifest["n_rows"]:
        raise PrimaryError(f"行数 {len(rows)} が frame_manifest.json の {manifest['n_rows']} と違う")
    return rows


def frame_record(frame_dir: Path | None) -> dict[str, str | None]:
    """答える問い: この結果は、どの frame(在り処と sha256)を読んで出したのか(ADR-140 決定4 (i))。

    frame を読んでいない(`--simulate`・合成の `--shuffle-labels`)ときは、2 欄とも None。
    sha256 は `read_frame` が照合した CSV の実体から取る。在り処は repo ルートからの相対パス(posix 形)で、
    repo の外を指すときだけ絶対パスのまま残す。
    """
    if frame_dir is None:
        return {"frame_dir": None, "frame_csv_sha256": None}
    resolved = frame_dir.resolve()
    try:
        where = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        where = resolved.as_posix()
    digest = hashlib.sha256((resolved / frame.CSV_FILENAME).read_bytes()).hexdigest()
    return {"frame_dir": where, "frame_csv_sha256": digest}


def select_primary_rows(rows: Sequence[Mapping[str, Any]], spec: Spec) -> list[dict[str, Any]]:
    """W1: 主軸の subset(p2・T1/T2・3 既知性)。答える問い: 主解析集合の行は、設計どおりに揃っているか。

    シード数が `n_seed`(ADR-028)でなければ止まる。項目は 1 つのセルにだけ属し(`item` は `task` に入れ子)、
    同じ (シード, 項目) が 2 行あれば止まる —— どれも `power_sim_fit.R` の入れ子の前提で、黙って当てると別の模型になる。
    """
    chosen = [
        dict(row) for row in rows
        if row["condition"] == spec.condition and row["main_axis"]
        and row["task"] in spec.tasks and row["coverage"] in spec.coverages
    ]
    seeds = {row["seed"] for row in chosen}
    if len(seeds) != spec.n_seed:
        raise PrimaryError(f"{spec.condition} のシード数が {len(seeds)}(期待 {spec.n_seed}。ADR-028)")
    cell_of: dict[str, Cell] = {}
    seen: set[tuple[Any, str]] = set()
    for row in chosen:
        cell = (row["task"], row["coverage"])
        if cell_of.setdefault(row["item"], cell) != cell:
            raise PrimaryError(f"項目 {row['item']} が複数のセルに属する(item は task に入れ子であること)")
        key = (row["seed"], row["item"])
        if key in seen:
            raise PrimaryError(f"(シード {key[0]}, 項目 {key[1]}) の行が 2 つある")
        seen.add(key)
    return chosen


# --------------------------------------------------------------------------
# 適格性フィルタ(I3 / W2)
# --------------------------------------------------------------------------


def reference_correct_rates(rows: Sequence[Mapping[str, Any]], spec: Spec) -> dict[Cell, float]:
    """答える問い: 基準(`ident`)のセルごとの `correct_rate` のシード平均はいくつか。

    基準の行が無いセルは止まる(黙って「通過」に倒さない。`CLAUDE.md` §7)。
    """
    by_cell_seed: dict[Cell, dict[Any, list[int]]] = {}
    for row in rows:
        cell = (row["task"], row["coverage"])
        if row["condition"] != spec.reference_condition or not row["main_axis"] or cell not in spec.cells:
            continue
        by_cell_seed.setdefault(cell, {}).setdefault(row["seed"], []).append(int(row["classification"] == CORRECT))
    missing = [f"{t}.{c}" for t, c in spec.cells if (t, c) not in by_cell_seed]
    if missing:
        raise PrimaryError(f"{spec.reference_condition} の行が無いセルがある(フィルタを判定できない): {missing}")
    return {
        cell: sum(sum(v) / len(v) for v in seeds.values()) / len(seeds)
        for cell, seeds in by_cell_seed.items()
    }


def order6_dropped_cells(path: Path, spec: Spec) -> set[Cell]:
    """答える問い: 順6(none)の Go/No-Go #2 で凍結前に落としたセルはどれか(ADR-076 決定1)。

    `gonogo.json` の `runs[].cells[].fails` が真のセルの和集合(run が複数あれば、どれかで落ちたセル)。
    """
    report = json.loads(path.read_text(encoding="utf-8"))
    runs = report.get("runs")
    if not runs:
        raise PrimaryError(f"{path} に run が無い")
    dropped = {
        (cell["task"], cell["coverage"])
        for run in runs for cell in run["cells"]
        if cell["fails"] and (cell["task"], cell["coverage"]) in spec.cells
    }
    return dropped


def declared_order6_cells(config: Mapping[str, Any], spec: Spec) -> set[Cell] | None:
    """答える問い: 人間が確定した、順6 の #2 で落とすセルの一覧はどれか(`null` なら未決で `None`)。

    `[]` は「確かめて落とすセルは無い」で、`null` とは違う(PLAN-048 I11)。主軸のセルでない名前は書き損じとして止める。
    """
    labels = declared(config, "input.order6_dropped_cells")
    if labels is None:
        return None
    if not isinstance(labels, list):
        raise ConfigError(f"input.order6_dropped_cells は <task>.<coverage> のリストである: {labels!r}")
    names = [str(label) for label in labels]
    unknown = sorted(name for name in names if tuple(name.split(".", 1)) not in spec.cells)
    if unknown:
        raise ConfigError(f"input.order6_dropped_cells に主軸のセルでない名前がある: {unknown}")
    return set(cells_from_labels(names))


def confirmed_order6_cells(config: Mapping[str, Any], path: Path, spec: Spec) -> set[Cell]:
    """答える問い: 人間が確定した一覧は、`gonogo.json` の `fails` の和集合と同じか(同じなら、その一覧を使う)。

    `fails` は基準を割ったかの印で、落とすセルの確定は人間(ADR-076 決定1・ADR-138 追記 ②)。
    一覧が未決なら止め、食い違えば両側を出して止める(どちらかに黙って倒さない)。
    """
    declared_cells = declared_order6_cells(config, spec)
    if declared_cells is None:
        raise PendingDecisionError(f"未決の値がある(ADR-138 追記 ②):\n  - {PENDING_ORDER6_LIST}")
    marked = order6_dropped_cells(path, spec)
    if declared_cells != marked:
        raise PrimaryError(
            "順6 で落とすセルの一覧が gonogo.json の fails と食い違う(ADR-138 追記 ②):\n"
            f"  input.order6_dropped_cells: {sorted(cell_label(c) for c in declared_cells)}\n"
            f"  {path} の fails の和集合: {sorted(cell_label(c) for c in marked)}"
        )
    return declared_cells


def eligibility(
    reference_rates: Mapping[Cell, float], order6_dropped: set[Cell], spec: Spec
) -> dict[str, Any]:
    """W2: 適格性フィルタ。答える問い: どのセルが、どちらのフィルタで落ちて、何が残るか。

    落ちる条件: `ident` の `correct_rate` のシード平均 < 閾値、または順6 の #2 で落ちた(和集合)。
    """
    dropped: dict[Cell, list[str]] = {}
    for cell in spec.cells:
        reasons = []
        if reference_rates[cell] < spec.min_reference_correct_rate:
            reasons.append(REASON_REFERENCE)
        if cell in order6_dropped:
            reasons.append(REASON_ORDER6)
        if reasons:
            dropped[cell] = reasons
    return {
        "threshold": spec.min_reference_correct_rate,
        "reference_correct_rate": {cell_label(c): reference_rates[c] for c in spec.cells},
        "dropped": {cell_label(c): reasons for c, reasons in dropped.items()},
        "kept": [cell_label(c) for c in spec.cells if c not in dropped],
    }


def cell_label(cell: Cell) -> str:
    return f"{cell[0]}.{cell[1]}"


def cells_from_labels(labels: Sequence[str]) -> list[Cell]:
    return [tuple(label.split(".", 1)) for label in labels]   # type: ignore[misc]


# --------------------------------------------------------------------------
# df と天井(I4・I5)
# --------------------------------------------------------------------------


def design_ranks(cells: Sequence[Cell], spec: Spec) -> dict[str, int]:
    """W3: 答える問い: 残ったセルで `task * coverage` と `task + coverage` の計画行列のランクはいくつか(df = 差)。

    処理対比(基準 = 各因子の最初の水準)。ランクは行の重複に依らないので、セルごとに 1 行で足りる。
    当てはめの前に機械的に出す(ADR-064 決定2)。R の `qr(model.matrix(...))$rank` と同じ値になる。
    """
    full_rows, add_rows = [], []
    for task, coverage in cells:
        t = [float(task == level) for level in spec.tasks[1:]]
        c = [float(coverage == level) for level in spec.coverages[1:]]
        add = [1.0, *t, *c]
        add_rows.append(add)
        full_rows.append([*add, *(a * b for a in t for b in c)])

    def rank(matrix: list[list[float]]) -> int:
        return int(np.linalg.matrix_rank(np.array(matrix))) if matrix else 0

    rank_full, rank_add = rank(full_rows), rank(add_rows)
    return {"rank_full": rank_full, "rank_add": rank_add, "df": rank_full - rank_add}


def table_rows(rows: Sequence[Mapping[str, Any]]) -> list[tuple[Any, ...]]:
    """答える問い: R に渡す表(`seed, task, coverage, item, template, is_rule`)の行は何か。"""
    ordered = sorted(rows, key=lambda r: (r["task"], r["coverage"], r["item"], r["seed"]))
    return [
        (f"{SEED_PREFIX}{r['seed']:0{SEED_DIGITS}d}", r["task"], r["coverage"], r["item"], r["template"], r["is_rule"])
        for r in ordered
    ]


def judge_ceiling(rows: Sequence[Mapping[str, Any]], cells: Sequence[Cell]) -> ceiling.CeilingVerdict:
    """W4: 答える問い: 残ったセルのどれかが天井(n/n か 0/n)か。

    `ceiling_rule` は宣言した全セルが揃った表でしか判定しない(F5)ので、**残ったセルを 1 つずつ宣言して**呼び、
    当たりを集める。規則の中身は変えない(ADR-137 決定2)。残るセルが無ければ「当たりなし」。
    """
    hits: list[tuple[str, str, str]] = []
    sizes: list[int] = []
    by_cell: dict[Cell, list[tuple[Any, ...]]] = {cell: [] for cell in cells}
    for row in table_rows([r for r in rows if (r["task"], r["coverage"]) in by_cell]):
        by_cell[(row[1], row[2])].append(row)
    for (task, coverage), cell_rows in by_cell.items():
        verdict = ceiling.ceiling_rule(cell_rows, (task,), (coverage,))
        hits.extend(verdict.hits)
        sizes.extend(verdict.n_per_cell)
    return ceiling.CeilingVerdict(ceiling=bool(hits), hits=tuple(hits), n_per_cell=tuple(sizes))


# --------------------------------------------------------------------------
# 当てはめ(I6)と TOST(I7)
# --------------------------------------------------------------------------


def make_r_fitter(power_config: Mapping[str, Any], rscript_override: str | None) -> Fitter:
    """W5: 答える問い: `power_sim_fit.R` を変えずに、1 枚の表をどう当てるか(ADR-138 決定2)。

    設定は `configs/power_sim.yaml` の `fit` 節をそのまま渡す。R の起動は 1 回(表 1 枚・並列 1)。
    """
    fit_config = power_config["fit"]
    refit = fit_config["refit"]
    max_level = len(require(power_config, "fit.reduction_order"))
    allfit = power_sim.load_allfit_spec(power_config)

    def fit(table: Sequence[tuple[Any, ...]], work_dir: Path) -> dict[str, Any]:
        work_dir.mkdir(parents=True, exist_ok=True)
        csv_path, out_path = work_dir / TABLE_CSV, work_dir / FIT_JSON
        power_sim.write_frame_csv(table, csv_path)
        rscript = power_sim.resolve_rscript(rscript_override or fit_config.get("rscript"))
        power_sim.run_fits(
            rscript, fit_config.get("r_libpath"), work_dir / "manifest", [(csv_path, out_path)],
            refit, max_level, allfit, n_workers=1,
        )
        return json.loads(out_path.read_text(encoding="ascii"))

    return fit


def tost_record(fit: Mapping[str, Any], spec: Spec) -> dict[str, Any] | None:
    """W7: 答える問い: 同等と言える最小の Δ はいくつか。Δ が決まっていれば同等か。

    当てはめ失敗なら係数が無いので `None`。最小の Δ は `power_sim.equivalence_margin`(各係数の
    `|推定値| + z × SE` の最大値)。Δ が `null` の間は同等の判定を出さない。
    """
    if fit["fit_failed"]:
        return None
    tost = power_sim.TostSpec(
        coverages=tuple(c for c in spec.coverages if c != BASELINE_COVERAGE),
        critical_z=NormalDist().inv_cdf(1.0 - spec.tost_alpha),
    )
    margin = power_sim.equivalence_margin(fit, tost)
    return {
        "min_delta": margin,
        "delta": spec.delta,
        "equivalent": None if spec.delta is None else margin <= spec.delta,
        "tost_alpha": spec.tost_alpha,
    }


def gate_quantities(primary: Sequence[Mapping[str, Any]], spec: Spec) -> dict[str, dict[str, Any]]:
    """W8: 答える問い: run ごとの門の量(`gate_task` × 基準水準 `id` の `rule_rate`)はいくつか(ADR-139 決定2)。

    frame の `is_rule` は run の条件の規則での判定なので、参照規則は run の条件の規則になっている。
    frame.py の `gate_id_by_task[gate_task]` と同じ行の集合(その task・`id`・seed あり)を数える。
    量を作れない run(その task の `id` の行が無い)は止まる(黙って「落ちた」「通った」に倒さない。`CLAUDE.md` §7)。
    """
    n_rule: dict[str, int] = {}
    n_all: dict[str, int] = {}
    pooled: dict[str, tuple[float | None, int]] = {}
    for row in primary:
        run_id = row["run_id"]
        pooled.setdefault(run_id, (row["gate_id_rule_rate"], row["gate_id_n"]))
        if row["task"] == spec.gate_task and row["coverage"] == BASELINE_COVERAGE:
            n_all[run_id] = n_all.get(run_id, 0) + 1
            n_rule[run_id] = n_rule.get(run_id, 0) + int(row["is_rule"])
    missing = sorted(set(pooled) - set(n_all))
    if missing:
        raise PrimaryError(f"{spec.gate_task} × {BASELINE_COVERAGE} の行が無い run がある(門の量を作れない): {missing}")
    return {
        run_id: {
            "rule_rate": n_rule[run_id] / n_all[run_id], "n": n_all[run_id],
            "gate_id_rule_rate": pooled[run_id][0], "gate_id_n": pooled[run_id][1],
        }
        for run_id in sorted(pooled)
    }


def analysis_gate_record(primary: Sequence[Mapping[str, Any]], spec: Spec, apply_gate: bool) -> dict[str, Any]:
    """W8: 答える問い: 各 run は門(量 `>=` 閾値)を通ったか。通った run は何本か。

    `apply_gate` が偽(`--simulate`・`--shuffle-labels`)のときは量を記録するだけで、通過の判定を付けない(ADR-138 決定3)。
    `gate_id_rule_rate` / `gate_id_n` は frame に入っている 4 タスク型プールの生の量(記録のみ。門には使わない)。
    """
    runs = gate_quantities(primary, spec)
    record: dict[str, Any] = {
        "applied": apply_gate, "role": GATE_ROLE_SENSITIVITY, "task": spec.gate_task, "coverage": BASELINE_COVERAGE,
        "threshold": spec.gate_threshold, "direction": spec.gate_direction, "min_runs": spec.gate_min_runs,
        "runs": runs,
    }
    if not apply_gate:
        return record
    if spec.gate_threshold is None:
        raise PendingDecisionError("analysis_gate.threshold が null のまま門を掛けられない(ADR-139 決定2)")
    passes = GATE_DIRECTIONS[spec.gate_direction]
    for entry in runs.values():
        entry["passes"] = passes(entry["rule_rate"], spec.gate_threshold)
    record["n_passed"] = sum(1 for entry in runs.values() if entry["passes"])
    record["n_total"] = len(runs)
    return record


# --------------------------------------------------------------------------
# 1 回の解析(順を固定する)
# --------------------------------------------------------------------------


def verdict_of(df: int, ceiling_hit: bool, fit: Mapping[str, Any] | None) -> str:
    """答える問い: 判定は何か。順は df → 天井 → 当てはめ(ADR-137 決定2・3)。"""
    if df < MIN_DF:
        return VERDICT_DF
    if ceiling_hit:
        return VERDICT_CEILING
    if fit is None or fit["fit_failed"]:
        return VERDICT_FIT
    return VERDICT_OK


def fit_stage(
    primary: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    order6_dropped: set[Cell],
    spec: Spec,
    fitter: Fitter,
    work_dir: Path,
) -> dict[str, Any]:
    """答える問い: 選んだ行に、適格性フィルタ → df → 天井 → 当てはめの順で主要検定を当てると、何が出るか。

    **df < 2 のときは当てない。天井のときは当てて記録する**(p 値は `fit` に残り、表には出さない。ADR-137 決定3)。
    R の LRT の df が計画行列のランクの差と違えば止まる(どちらかが間違っている)。
    適格性フィルタは `ident` の行(`rows` 全体)だけで決まり、`primary`(門で絞った行かもしれない)に依らない。
    """
    filtered = eligibility(reference_correct_rates(rows, spec), order6_dropped, spec)
    kept = cells_from_labels(filtered["kept"])
    ranks = design_ranks(kept, spec)
    kept_set = set(kept)
    used = [r for r in primary if (r["task"], r["coverage"]) in kept_set]
    verdict = judge_ceiling(used, kept)
    fit = None
    if ranks["df"] >= MIN_DF:
        fit = fitter(table_rows(used), work_dir)
        if not fit["fit_failed"] and int(fit["df"]) != ranks["df"]:
            raise PrimaryError(f"R の LRT の df {fit['df']} が計画行列のランクの差 {ranks['df']} と違う")
    return {
        "verdict": verdict_of(ranks["df"], verdict.ceiling, fit),
        "n_seed": len({r["seed"] for r in primary}),
        "n_rows": len(used),
        "eligibility": filtered,
        "df": ranks,
        "ceiling": {**ceiling.verdict_record(verdict), "judged_cells": [cell_label(c) for c in kept]},
        "fit": fit,
        "tost": None if fit is None else tost_record(fit, spec),
    }


def sensitivity_stage(
    primary: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    order6_dropped: set[Cell],
    spec: Spec,
    fitter: Fitter,
    work_dir: Path,
) -> dict[str, Any]:
    """答える問い: 門を通った run だけに同じ手続きを当てると、何が出るか(探索的な感度解析。ADR-139 決定1・3)。

    通った run が `min_runs` 本未満なら当てずに `実施不能: 解析門`。Holm のファミリーに入れない。
    """
    passed = {run_id for run_id, entry in gate["runs"].items() if entry["passes"]}
    record: dict[str, Any] = {"n_runs_passed": len(passed), "min_runs": spec.gate_min_runs, "result": None}
    if len(passed) < spec.gate_min_runs:
        return {**record, "verdict": VERDICT_GATE}
    stage = fit_stage(
        [r for r in primary if r["run_id"] in passed], rows, order6_dropped, spec, fitter,
        work_dir.with_name(work_dir.name + SENSITIVITY_DIR_SUFFIX),
    )
    return {**record, "verdict": stage["verdict"], "result": stage}


def analyse(
    rows: Sequence[Mapping[str, Any]],
    order6_dropped: set[Cell],
    spec: Spec,
    fitter: Fitter,
    work_dir: Path,
    apply_gate: bool = False,
) -> dict[str, Any]:
    """答える問い: この frame に主要検定を、選ぶ → 門 → フィルタ → df → 天井 → 当てはめの順で当てると、何が出るか。

    **主は門なし**(今のシード数の検査 `design.n_seed` のまま)。`apply_gate` が真(実データ)のときだけ、
    門ありの感度解析を `sensitivity` に足す(ADR-139 決定1・3)。`--simulate`・`--shuffle-labels` は偽(ADR-138 決定3)。
    """
    primary = select_primary_rows(rows, spec)
    gate = analysis_gate_record(primary, spec, apply_gate)
    result = fit_stage(primary, rows, order6_dropped, spec, fitter, work_dir)
    result["analysis_gate"] = gate
    if apply_gate:
        result["sensitivity"] = sensitivity_stage(primary, gate, rows, order6_dropped, spec, fitter, work_dir)
    return result


# --------------------------------------------------------------------------
# 報告(I8 / ADR-138 決定6)
# --------------------------------------------------------------------------


def format_number(value: float | None, fmt: str = ".4g") -> str:
    return "" if value is None else format(value, fmt)


def report_row(result: Mapping[str, Any]) -> list[str]:
    """答える問い: 表の 1 行は何か。列の順は判定 → 落ちたセル → df → 天井 → 縮退の段 → p 値 → TOST。

    **p 値と TOST の欄は判定が `実施可` のときだけ埋める**(ADR-137 決定3 の罠を表の形で塞ぐ)。
    """
    ok = result["verdict"] == VERDICT_OK
    dropped = result["eligibility"]["dropped"]
    hits = result["ceiling"]["ceiling_hits"]
    fit, tost = result["fit"], result["tost"]
    p_value = fit["p_value"] if ok else None
    if not ok or tost is None:
        min_delta = delta = equivalent = ""
    else:
        min_delta = format_number(tost["min_delta"])
        delta = "未決" if tost["delta"] is None else format_number(tost["delta"])
        equivalent = "(Δ 未決のため判定しない)" if tost["equivalent"] is None else ("同等" if tost["equivalent"] else "同等と言えない")
    return [
        result["verdict"],
        ", ".join(f"{label}({'+'.join(reasons)})" for label, reasons in dropped.items()) or "なし",
        str(result["df"]["df"]),
        ", ".join(f"{t}.{c}:{direction}" for t, c, direction in hits) or "なし",
        "—" if fit is None else str(fit["reduction_label"]),
        format_number(p_value, ".4g"),
        min_delta,
        delta,
        equivalent,
    ]


GATE_HEADER = ("run", "量(rule_rate)", "n", "門")


def gate_rows(gate: Mapping[str, Any]) -> list[list[str]]:
    """答える問い: 門の表の各行(run・量・項目数・通過/落ちた)は何か。"""
    return [
        [run_id, format_number(entry["rule_rate"], ".4f"), str(entry["n"]), "通過" if entry["passes"] else "落ちた"]
        for run_id, entry in gate["runs"].items()
    ]


def render_gate(label: str, result: Mapping[str, Any]) -> list[str]:
    """答える問い: 解析門の行(量・閾値・通過した本数・各 run)と感度解析の判定は、報告でどう見えるか。

    門は主要検定(上の表)には掛けていない。感度解析は探索的で Holm に入れない(ADR-139 決定1)。
    感度解析が出せるときは、主と同じ列の表を出す。主と食い違っても両方残す。
    """
    gate, sensitivity = result["analysis_gate"], result["sensitivity"]
    lines = [
        "", f"### {label}: 解析門(ADR-139)", "",
        f"- 量: {gate['task']} × {gate['coverage']} の rule_rate(参照規則は run の条件の規則)/ 閾値: {gate['direction']} {format_number(gate['threshold'])}"
        f" / 通過 {gate['n_passed']} / {gate['n_total']} 本",
        "", "| " + " | ".join(GATE_HEADER) + " |", "|" + "---|" * len(GATE_HEADER),
        *("| " + " | ".join(row) + " |" for row in gate_rows(gate)),
        "", f"### {label}: 感度解析(門あり。探索的・Holm に入れない。主と食い違えば両方を報告する)", "",
    ]
    if sensitivity["result"] is None:
        lines.append(f"- **{sensitivity['verdict']}**: 通った run {sensitivity['n_runs_passed']} 本 < k = {sensitivity['min_runs']}")
    else:
        lines += [f"- 通った run {sensitivity['n_runs_passed']} 本(k = {sensitivity['min_runs']})", "",
                  "| " + " | ".join(REPORT_HEADER) + " |", "|" + "---|" * len(REPORT_HEADER),
                  "| " + " | ".join(report_row(sensitivity["result"])) + " |"]
    return lines


REPORT_HEADER = ("判定", "落ちたセル", "df", "天井(セルと向き)", "縮退の段", "LRT の p 値", "TOST の最小 Δ", "Δ", "同等か")


def render_report(meta: Mapping[str, Any], targets: Mapping[str, Mapping[str, Any]]) -> str:
    """答える問い: `report.md`(対象ごとの固定の表と注記)の本文は何か。"""
    lines = [
        "# 主要検定の報告(primary.py)",
        "",
        f"- run_id: `{meta['run_id']}` / モード: `{meta['mode']}` / git: `{meta['git_sha']}`",
    ]
    if meta.get("frame_dir") is not None:
        lines.append(f"- 入力の frame: `{meta['frame_dir']}`(csv_sha256 `{meta['frame_csv_sha256']}`)")
    if meta["mode"] != MODE_ACTUAL:
        lines.append("- **合成データの配線の確認である。ここに出る数は実験結果ではない**(`CLAUDE.md` §2)")
    for label, result in targets.items():
        lines += ["", f"## {label}", "", "| " + " | ".join(REPORT_HEADER) + " |", "|" + "---|" * len(REPORT_HEADER),
                  "| " + " | ".join(report_row(result)) + " |"]
        if "sensitivity" in result:
            lines += render_gate(label, result)
        notes = result.get("shuffle")
        if notes:
            lines += ["", f"- 入れ替え(seed {notes['seed']}): " + ("template が複数の task に跨る: " + ", ".join(notes["mixed_templates"]) if notes["mixed_templates"] else "template は 1 つの task に収まる")]
    lines += ["", "---", "", f"- {NOTE_RANDOM_EFFECT}", f"- {NOTE_P_VALUE}", ""]
    return "\n".join(lines)


def write_outputs(
    run_dir: Path, meta: Mapping[str, Any], targets: Mapping[str, Mapping[str, Any]],
    config_path: Path, power_config_path: Path,
) -> None:
    """答える問い: 結果と、それを出した設定を `results/primary/<run_id>/` に残せたか。"""
    power_sim.write_json_atomic(run_dir / PRIMARY_JSON, {**meta, "targets": targets})
    (run_dir / REPORT_MD).write_text(render_report(meta, targets), encoding="utf-8", newline="\n")
    shutil.copyfile(config_path, run_dir / PRIMARY_CONFIG_COPY)
    shutil.copyfile(power_config_path, run_dir / POWER_CONFIG_COPY)
    artifacts.write_git_sha(run_dir)


# --------------------------------------------------------------------------
# --shuffle-labels(I9 / ADR-138 決定4)
# --------------------------------------------------------------------------


def shuffle_task_labels(
    rows: Sequence[Mapping[str, Any]], spec: Spec, rng: np.random.Generator
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """答える問い: 被覆の水準の中で項目単位に `task` を入れ替えた表は、主要検定の帰無(平行)がちょうど成り立つか。

    各被覆の水準の中で、項目(とその全シードの行)に付いた `task` を並べ替える。セルの項目数は保つ
    (`task` の主効果も交互作用も壊れ、被覆の勾配は残る)。**`template` は項目に付いたまま動かさない**ので、
    `task` と `template` の対応は崩れる(`(1 | template)` の水準の意味が変わる)。崩れは記録する。
    主解析集合(`spec.condition`)の行だけを動かす。入れ替えの p 値 1 つは 5% の確率で有意になる(バグではない)。
    """
    task_of: dict[str, str] = {}
    coverage_of: dict[str, str] = {}
    for row in rows:
        if row["condition"] == spec.condition and row["main_axis"] and row["task"] in spec.tasks:
            task_of[row["item"]] = row["task"]
            coverage_of[row["item"]] = row["coverage"]
    shuffled: dict[str, str] = {}
    for coverage in spec.coverages:
        items = sorted(i for i, c in coverage_of.items() if c == coverage)
        labels = [task_of[i] for i in items]
        for item, position in zip(items, rng.permutation(len(items)), strict=True):
            shuffled[item] = labels[position]
    out = [dict(row) for row in rows]
    templates: dict[str, set[str]] = {}
    for row in out:
        if row["item"] in shuffled and row["condition"] == spec.condition:
            row["task"] = shuffled[row["item"]]
            templates.setdefault(row["template"], set()).add(row["task"])
    record = {
        "n_items_moved": sum(1 for i, t in shuffled.items() if t != task_of[i]),
        "mixed_templates": sorted(t for t, tasks in templates.items() if len(tasks) > 1),
    }
    return out, record


# --------------------------------------------------------------------------
# --simulate(I9 / ADR-138 決定5)
# --------------------------------------------------------------------------


def simulated_frame(
    target: Mapping[str, Any], label: str, index: int, seed: int,
    power_config: Mapping[str, Any], config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """答える問い: `draw_frame` の 1 点を、frame と同じ列の行(p2 と、フィルタ用の ident)にするとどうなるか。

    生成は `power_sim.draw_frame` そのまま(run3 と同じ過程。ADR-138 決定5)。点は `power_sim.yaml` の格子の点でなければ止まる。
    `ident` の行は各セルの `correct_rate` が `simulate.reference_correct_rate` になるように置く(配線の確認用の置き値)。
    """
    n_item, sigma, rho = int(target["n_item"]), float(target["sigma"]), float(target["rho"])
    if sigma not in power_config["dgp"]["sigma"] or rho not in power_config["dgp"]["rho"]:
        raise ConfigError(f"{label}: sigma {sigma} / rho {rho} が power_sim.yaml の格子に無い")
    levels = power_sim.load_levels(power_config, n_item)
    profile = power_sim.build_profile(power_config["effect"], str(target["profile"]))
    rng = np.random.default_rng(np.random.SeedSequence([seed, index]))
    drawn = power_sim.draw_frame(
        levels, profile.eta, sigma, rho,
        float(require(power_config, "dgp.s2_item")), float(require(power_config, "dgp.s2_tmpl")), rng,
    )
    names = require(config, "simulate.task_names")
    n_correct = round(float(require(config, "simulate.reference_correct_rate")) * n_item)
    rows: list[dict[str, Any]] = []
    for seed_label, task, coverage, item, template, is_rule in drawn:
        common = {
            "seed": int(seed_label[len(SEED_PREFIX):]), "item": item, "task": names[task], "template": template,
            "category": template, "coverage": coverage, "main_axis": True,
        }
        rows.append({**common, "run_id": f"sim_{label}_{seed_label}", "condition": require(config, "design.primary_condition"),
                     "is_rule": is_rule, "classification": "rule" if is_rule else "other_error",
                     "gate_id_rule_rate": None, "gate_id_n": 0})
        position = int(item.rsplit(".", 1)[1])
        rows.append({**common, "run_id": f"sim_{label}_ref_{seed_label}", "condition": require(config, "design.reference_condition"),
                     "is_rule": 0, "classification": CORRECT if position < n_correct else "other_error",
                     "gate_id_rule_rate": None, "gate_id_n": 0})
    return rows


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------


def run_dir_for(root: Path, config: Mapping[str, Any], mode: str) -> tuple[Path, str]:
    now = artifacts.utc_now()
    run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{require(config, 'analysis.id')}_{mode}"
    return root / run_id, run_id


def resolve_frame_dir(args: argparse.Namespace, config: Mapping[str, Any]) -> Path | None:
    """答える問い: 読む frame の在り処は(`--frame-dir` が先。無ければ config の `input.frame_dir`。どちらも無ければ None)。

    `--shuffle-labels` は `--frame-dir` を明示したときだけ実 frame を読む(ADR-140 追記 ① I5)。config に `input.frame_dir` が
    あっても読まず None(合成の入れ替え)。凍結前の確かめを、凍結する configs/primary.yaml そのもので回せるようにするため。
    """
    if args.frame_dir:
        return Path(args.frame_dir)
    if args.shuffle_labels:
        return None
    if declared(config, "input.frame_dir") is None:
        return None
    return resolve_repo_path(config["input"]["frame_dir"])


def build_targets(
    args: argparse.Namespace, config: Mapping[str, Any], power_config: Mapping[str, Any], spec: Spec,
) -> list[tuple[str, list[dict[str, Any]], set[Cell], dict[str, Any] | None]]:
    """答える問い: このモードで何を解析するか —— (ラベル, 行, 順6 で落ちたセル, 入れ替えの記録)の並び。"""
    frame_dir = resolve_frame_dir(args, config)
    order6 = args.order6_gonogo or (None if declared(config, "input.order6_gonogo") is None else resolve_repo_path(config["input"]["order6_gonogo"]))
    if args.simulate:
        targets = require(config, "simulate.targets")
        seed = args.seed if args.seed is not None else int(require(config, "simulate.seed"))
        return [(label, simulated_frame(t, label, i, seed, power_config, config), set(), None)
                for i, (label, t) in enumerate(targets.items())]
    if args.shuffle_labels:
        seed = args.seed if args.seed is not None else int(require(config, "shuffle.seed"))
        if frame_dir is None:
            source = str(require(config, "shuffle.source_target"))
            targets = require(config, "simulate.targets")
            rows, dropped = simulated_frame(targets[source], source, 0, seed, power_config, config), set()
        else:
            if order6 is None:
                raise PrimaryError("--frame-dir を渡したときは --order6-gonogo も要る(適格性フィルタを同じにするため)")
            rows, dropped = read_frame(frame_dir), confirmed_order6_cells(config, order6, spec)
        shuffled, record = shuffle_task_labels(rows, spec, np.random.default_rng(seed))
        return [("shuffled", shuffled, dropped, {"seed": seed, **record})]
    if order6 is not None and declared_order6_cells(config, spec) is not None:
        # 実データの経路も gonogo.json を読む経路なので、ほかの未決で止まる前に照合しておく(PLAN-048 I11)
        confirmed_order6_cells(config, order6, spec)
    require_decided(config, frame_dir, order6)
    if frame_dir is None or order6 is None:   # require_decided が止めているはず(型の絞り込み)
        raise AssertionError("frame_dir / order6 が None のまま require_decided を通った")   # pragma: no cover
    return [(ACTUAL_LABEL, read_frame(frame_dir), confirmed_order6_cells(config, order6, spec), None)]


def run(args: argparse.Namespace) -> int:
    config_path = resolve_repo_path(args.config)
    config = load_config(config_path)
    power_config = load_power_config(config)
    spec = load_spec(config, power_config)
    mode = MODE_SIMULATE if args.simulate else MODE_SHUFFLE if args.shuffle_labels else MODE_ACTUAL
    prepared = build_targets(args, config, power_config, spec)
    root = resolve_repo_path(args.out_dir or require(config, "output.root"))
    run_dir, run_id = run_dir_for(root, config, mode)
    run_dir.mkdir(parents=True, exist_ok=False)
    fitter = make_r_fitter(power_config, args.rscript)
    results: dict[str, dict[str, Any]] = {}
    for label, rows, dropped, shuffle in prepared:
        results[label] = analyse(rows, dropped, spec, fitter, run_dir / label / FIT_DIR, apply_gate=mode == MODE_ACTUAL)
        if shuffle is not None:
            results[label]["shuffle"] = shuffle
    # --simulate は frame を読まない(config に frame_dir があっても)。--shuffle-labels は --frame-dir を明示したときだけ読む(resolve_frame_dir)
    frame_read = None if args.simulate else resolve_frame_dir(args, config)
    meta = {"run_id": run_id, "mode": mode, "git_sha": artifacts.capture_git_head_sha(),
            "alpha": spec.alpha, "tost_alpha": spec.tost_alpha, **frame_record(frame_read)}
    write_outputs(run_dir, meta, results, config_path, resolve_repo_path(require(config, "power_sim_config")))
    for label, result in results.items():
        print(f"{label}: {result['verdict']}")
    print(f"書き出した: {run_dir}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="実データの主要解析(PLAN-048)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--frame-dir", type=Path, default=None, help="凍結した frame のディレクトリ")
    parser.add_argument("--order6-gonogo", type=Path, default=None, help="順6 の gonogo.json")
    parser.add_argument("--simulate", action="store_true", help="draw_frame の P0・P1 を全経路に通す(合成)")
    parser.add_argument("--shuffle-labels", action="store_true", help="被覆の中で項目単位に task を入れ替える")
    parser.add_argument("--seed", type=int, default=None, help="--simulate / --shuffle-labels の乱数")
    parser.add_argument("--out-dir", type=Path, default=None, help="config の output.root を上書き")
    parser.add_argument("--rscript", default=None, help="Rscript の実体")
    args = parser.parse_args(argv)
    if args.simulate and args.shuffle_labels:
        parser.error("--simulate と --shuffle-labels は同時に指定できない")
    try:
        return run(args)
    except PendingDecisionError as error:
        print(f"止まった: {error}")
        return EXIT_PENDING
    except (PrimaryError, ConfigError, ceiling.CeilingRuleError, power_sim.PowerSimError) as error:
        print(f"止まった: {error}")
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
