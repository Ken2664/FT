"""天井の手当て C の評価(PLAN-046 I1・I3 / ADR-132 決定2〜4 / ADR-133)。

答える問い: 「天井の規則(6 セルのどれかが全シード・全項目で n/n か 0/n)で分岐し、天井なら恒等リンクの LMM の LRT、
そうでなければ今のロジットの LRT で棄却を数える**手続き全体**は、合成データの各点で何をするか。G1・G2 は閉じるか」

    python -m code.analysis.ceiling_remedy --config configs/ceiling_remedy.yaml --dry-run
    python -m code.analysis.ceiling_remedy --config configs/ceiling_remedy.yaml --out-dir results/ceiling_remedy --workers 16

- **I1** `ceiling_rule`: 天井の判定(純粋関数)。セルが欠ける表は判定せず止まる(df < 2 の表は適格性フィルタの側の話で、
  ここで黙って「天井でない」にしない)
- **I3**: 元の run の表(`frames/`)を乱数種から組み直して照合し(§8 罠8)、ロジットの当てはめ(`fits/`)を読み、全部の表に
  恒等リンクの LMM(`power_sim_fit_lmm.R`)を当て、道ごとに数える。G1・G2 の判定と CP95 を点ごとに出す
- 当てはめ失敗(どちらの道でも)は**非棄却に数え、分母から除かない**(ADR-128 決定1 (A2)・ADR-133 決定2)。
  C の道の失敗 = 実施不能(B)で、G2 の分子である

**解釈は書かない。**C の採否は、G1 か G2 が閉じれば「採らない」、両方開いても人間が別の ADR で決める(ADR-133 決定4)。
ここに出る数はすべて仮定値の下の合成データの記述で、本実験で起こることではない(PLAN-046 罠6)。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code import artifacts
from code.analysis import power_sim
from code.config import ConfigError, load_config, require, resolve_repo_path

LMM_FIT_SCRIPT = Path(__file__).resolve().parent / "power_sim_fit_lmm.R"

DIRECTION_ALL_RULE = "all_rule"      # n/n
DIRECTION_NO_RULE = "no_rule"        # 0/n
PATH_LOGIT = "logit"                 # 天井でない: 今の手続き(ロジットの GLMM の LRT)
PATH_C = "identity_lmm"              # 天井: C(恒等リンクの LMM の LRT)
PRIMARY_DF = power_sim.PRIMARY_INTERACTION_DF

SUMMARY_FILE = "ceiling_remedy_summary.json"
RUN_INFO_FILE = "run_info.json"
INVOCATIONS_FILE = "invocations.jsonl"
RESOLVED_CONFIG_FILE = "config_resolved.json"
R_SECONDS_PATTERN = re.compile(r"-> (\S+) \((\d+(?:\.\d+)?)s\)")


class CeilingRuleError(power_sim.PowerSimError):
    """天井の規則が判定できない表(セルが欠ける・未知のセル・0/1 でない応答)。"""


# --------------------------------------------------------------------------
# I1 天井の判定(PLAN-046 §5 手順 1 / ADR-132 決定2)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CeilingVerdict:
    """天井の判定。答える問い: この表は天井か、どのセルが、どちら向きに当てたか。

    `hits` は `(タスク型, 被覆, all_rule | no_rule)`。`n_per_cell` はセルの行数(タスク型 × 被覆の順)。
    """

    ceiling: bool
    hits: tuple[tuple[str, str, str], ...]
    n_per_cell: tuple[int, ...]


def ceiling_rule(
    rows: Sequence[tuple[Any, ...]], tasks: Sequence[str], coverages: Sequence[str]
) -> CeilingVerdict:
    """答える問い: 6 セル(タスク型 × 被覆)のどれかが、全シード・全項目で n/n か 0/n か(ADR-132 決定2)。

    n はそのセルの全行(= 全シード × 全項目)。**判定は当てはめの前に、表だけから行う。**
    行は `(seed, task, coverage, item, template, is_rule)`。セルが 1 つでも欠ける表・宣言に無いセルの行・
    0/1 でない応答は判定せずに止まる(黙って「天井でない」に倒さない。`CLAUDE.md` §7)。
    """
    counts = {(t, c): [0, 0] for t in tasks for c in coverages}
    for row in rows:
        cell = (row[1], row[2])
        if cell not in counts:
            raise CeilingRuleError(f"宣言に無いセルの行がある: {cell}")
        if row[5] not in (0, 1):
            raise CeilingRuleError(f"is_rule が 0/1 でない: {row[5]!r}")
        counts[cell][0] += 1
        counts[cell][1] += row[5]
    missing = [f"{t}.{c}" for (t, c), (n, _) in counts.items() if n == 0]
    if missing:
        raise CeilingRuleError(f"セルが欠ける表は天井の規則で判定しない: {missing}")
    hits = []
    for (task, coverage), (n, n_rule) in counts.items():
        if n_rule == n:
            hits.append((task, coverage, DIRECTION_ALL_RULE))
        elif n_rule == 0:
            hits.append((task, coverage, DIRECTION_NO_RULE))
    return CeilingVerdict(
        ceiling=bool(hits), hits=tuple(hits), n_per_cell=tuple(n for n, _ in counts.values())
    )


# --------------------------------------------------------------------------
# 表の照合(PLAN-046 §8 罠8)
# --------------------------------------------------------------------------


def read_frame_csv(path: Path) -> list[tuple[Any, ...]]:
    """答える問い: `write_frame_csv` が書いた表は、どの行を持つか(見出しが違えば止まる)。"""
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or tuple(lines[0].split(",")) != power_sim.CSV_HEADER:
        raise power_sim.PowerSimError(f"{path} の見出しが {power_sim.CSV_HEADER} でない")
    rows = []
    for line in lines[1:]:
        seed, task, coverage, item, template, is_rule = line.split(",")
        rows.append((seed, task, coverage, item, template, int(is_rule)))
    return rows


def manifest_pairs(sheet_dir: Path) -> dict[str, str]:
    """答える問い: 元の run の manifest は、どの表をどの当てはめの出力に結んだか(表の名前 → 出力の名前)。

    ★再開した起動は manifest を未済の反復だけで書き直すので、全部の反復が載っているとは限らない(2026-10-22 に確認:
    `ceiling_null_L50` 62/100・`ceiling_p1_L05` 47/100)。だから照合の主は組み直し(`verify_frame`)で、manifest は載っている分だけ見る。
    """
    pairs: dict[str, str] = {}
    for manifest in sorted(sheet_dir.glob("manifest_*.txt")):
        for line in manifest.read_text(encoding="ascii").splitlines():
            if line.startswith("fit="):
                csv_path, _, out_path = line[len("fit="):].partition("|")
                pairs[Path(csv_path).name] = Path(out_path).name
    return pairs


def verify_frame(
    frame_path: Path, expected: Sequence[tuple[Any, ...]], logit_fit: Mapping[str, Any],
    fit_name: str, pairs: Mapping[str, str],
) -> list[tuple[Any, ...]]:
    """答える問い: 残してある表は、乱数種から組み直した表・ロジットの当てはめ・manifest と食い違わないか(食い違えば止まる)。"""
    if not frame_path.exists():
        raise power_sim.PowerSimError(f"表が無い: {frame_path}(frames は未追跡。組み直すか元の run を確かめること)")
    rows = read_frame_csv(frame_path)
    if rows != list(expected):
        raise power_sim.PowerSimError(f"{frame_path} が乱数種から組み直した表と違う(§8 罠8)")
    if logit_fit.get("csv") != frame_path.name or logit_fit.get("n_rows") != len(rows):
        raise power_sim.PowerSimError(f"{fit_name} の csv・n_rows が {frame_path.name} と合わない")
    if frame_path.name in pairs and pairs[frame_path.name] != fit_name:
        raise power_sim.PowerSimError(f"manifest は {frame_path.name} を {pairs[frame_path.name]} に結んでいる({fit_name} でない)")
    return rows


# --------------------------------------------------------------------------
# 宣言
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """元の run 1 つ。答える問い: どの config のどのシートの表と当てはめを、どこから読むか。"""

    source_id: str
    config: Mapping[str, Any]
    config_path: Path
    results_dir: Path
    run_id: str | None
    sheets: tuple[power_sim.Sheet, ...]


@dataclass(frozen=True)
class GateRule:
    """門 1 つ(ADR-133)。答える問い: どの区間の下端が、どの値を超えたら閉じるか。"""

    ci_level: float
    closes_if_lower_above: float


@dataclass(frozen=True)
class EvalSpec:
    """評価の宣言。答える問い: どの表を、どの手続き・どの門・どの記述で評価するか。"""

    sources: tuple[Source, ...]
    n_rep: int
    alpha: float
    tost_alpha: float
    lmm_optimizer: str
    rscript: str | None
    libpath: str | None
    n_workers: int
    g1_sheets: tuple[str, ...]
    g1: GateRule
    g2: GateRule
    ci_level: float
    quantiles: tuple[float, ...]


def _gate_rule(config: Mapping[str, Any], name: str) -> GateRule:
    level = float(require(config, f"gates.{name}.ci_level"))
    threshold = float(require(config, f"gates.{name}.closes_if_lower_above"))
    if not 0.0 < level < 1.0 or not 0.0 < threshold < 1.0:
        raise ConfigError(f"gates.{name} の ci_level・closes_if_lower_above は (0, 1): {level}, {threshold}")
    return GateRule(ci_level=level, closes_if_lower_above=threshold)


def load_source(entry: Mapping[str, Any], dir_override: Path | None) -> Source:
    """答える問い: 元の run の config は天井のシートだけを持ち、水準(と解いたセル)が転記済みか。"""
    config_path = resolve_repo_path(str(entry["config"]))
    config = load_config(config_path)
    sheets = tuple(power_sim.load_sheets(config))
    power_sim.check_ceiling_config(config, sheets)
    for sheet in sheets:
        power_sim.ceiling_profile(config, sheet)    # 水準・解いたセルが null ならここで止まる
    results_dir = dir_override or resolve_repo_path(str(entry["results_dir"]))
    run_id = entry.get("run_id")
    return Source(
        source_id=str(entry["id"]), config=config, config_path=config_path, results_dir=results_dir,
        run_id=None if run_id is None else str(run_id), sheets=sheets,
    )


def check_sources_agree(sources: Sequence[Source], n_rep: int) -> None:
    """答える問い: 元の config どうしで、当てはめの手続き・DGP・alpha が同じか(ADR-133 決定1: ロジットの道と同じ手続き)。"""
    first = sources[0].config
    for source in sources[1:]:
        for block in ("fit", "dgp", "effect"):
            if source.config[block] != first[block]:
                raise ConfigError(f"{source.source_id} の {block} が {sources[0].source_id} と違う")
        for key in ("alpha", "tost_alpha"):
            if source.config["simulation"][key] != first["simulation"][key]:
                raise ConfigError(f"{source.source_id} の simulation.{key} が違う")
    for source in sources:
        stages = power_sim.load_stages(source.config)
        if stages[-1] != n_rep:
            raise ConfigError(f"n_rep = {n_rep} が {source.source_id} の最後の段 {stages[-1]} と違う")
    seen: set[str] = set()
    for source in sources:
        for sheet in source.sheets:
            if sheet.sheet_id in seen:
                raise ConfigError(f"シート {sheet.sheet_id} が 2 つの元の run にある")
            seen.add(sheet.sheet_id)


def load_eval_spec(
    config: Mapping[str, Any], dir_overrides: Mapping[str, Path], workers_override: int | None,
    rscript_override: str | None,
) -> EvalSpec:
    """config の宣言を読む。答える問い: 評価に要る値はすべて宣言され、元の run と整合しているか。"""
    entries = require(config, "sources")
    known = {str(e["id"]) for e in entries}
    unknown = sorted(set(dir_overrides) - known)
    if unknown:
        raise ConfigError(f"--source-dir の id {unknown} は sources に無い")
    sources = tuple(load_source(e, dir_overrides.get(str(e["id"]))) for e in entries)
    n_rep = int(require(config, "n_rep"))
    check_sources_agree(sources, n_rep)
    if require(config, "lmm.reml") is not False:
        raise ConfigError("lmm.reml は false(ML)でなければならない(ADR-133 決定1)")
    g1_sheets = tuple(str(s) for s in require(config, "gates.g1.sheets"))
    all_sheets = {s.sheet_id for src in sources for s in src.sheets}
    if not g1_sheets or set(g1_sheets) - all_sheets:
        raise ConfigError(f"gates.g1.sheets {list(g1_sheets)} は元の run のシートでなければならない")
    lmm = config["lmm"]
    n_workers = int(workers_override or lmm.get("n_workers") or 1)
    if n_workers < 1:
        raise ConfigError(f"--workers は 1 以上: {n_workers}")
    quantiles = tuple(float(q) for q in require(config, "report.quantiles"))
    return EvalSpec(
        sources=sources,
        n_rep=n_rep,
        alpha=float(sources[0].config["simulation"]["alpha"]),
        tost_alpha=float(sources[0].config["simulation"]["tost_alpha"]),
        lmm_optimizer=str(require(config, "lmm.optimizer")),
        rscript=rscript_override or lmm.get("rscript"),
        libpath=lmm.get("r_libpath"),
        n_workers=n_workers,
        g1_sheets=g1_sheets,
        g1=_gate_rule(config, "g1"),
        g2=_gate_rule(config, "g2"),
        ci_level=float(require(config, "report.ci_level")),
        quantiles=quantiles,
    )


# --------------------------------------------------------------------------
# I2 の呼び出し(恒等リンクの LMM)
# --------------------------------------------------------------------------


def write_lmm_manifest(path: Path, jobs: Sequence[tuple[Path, Path]], fit_config: Mapping[str, Any],
                       optimizer: str) -> None:
    """答える問い: R の LMM に、何をどの閾値・どの最適化で当てさせるか(閾値は元の config の fit。ロジットの道と同じ)。"""
    power_sim.write_fit_manifest(
        path, jobs, fit_config["refit"], len(fit_config["reduction_order"]),
        power_sim.load_allfit_spec({"fit": fit_config}),
    )
    with path.open("a", encoding="ascii", newline="\n") as handle:
        handle.write(f"lmm_optimizer={optimizer}\nlmm_reml=false\n")


def run_lmm_rscript(rscript: str, libpath: str | None, manifest: Path) -> str:
    """答える問い: LMM の当てはめは通ったか(R を 1 回起動して manifest の表をすべて当てる)。"""
    completed = subprocess.run(
        [rscript, str(LMM_FIT_SCRIPT), libpath or "", str(manifest)], capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise power_sim.PowerSimError(
            f"Rscript(LMM)が異常終了した (returncode={completed.returncode})\n{completed.stdout}\n{completed.stderr}"
        )
    manifest.with_suffix(".log").write_text(completed.stdout, encoding="utf-8", newline="\n")
    return completed.stdout


def run_lmm_fits(spec: EvalSpec, rscript: str, manifest_stem: Path, jobs: Sequence[tuple[Path, Path]],
                 fit_config: Mapping[str, Any]) -> dict[str, float]:
    """答える問い: 未済の表に LMM を当てると、1 表あたり何秒かかったか(R の出力の秒。表の出力名 → 秒)。"""
    shards = power_sim.shard_jobs(jobs, spec.n_workers)
    manifests = []
    for index, shard in enumerate(shards):
        manifest = manifest_stem.with_name(f"{manifest_stem.name}_{index:02d}.txt")
        write_lmm_manifest(manifest, shard, fit_config, spec.lmm_optimizer)
        manifests.append(manifest)
    with ThreadPoolExecutor(max_workers=max(1, len(manifests))) as pool:
        outputs = [f.result() for f in [pool.submit(run_lmm_rscript, rscript, spec.libpath, m) for m in manifests]]
    return {m.group(1): float(m.group(2)) for out in outputs for m in R_SECONDS_PATTERN.finditer(out)}


# --------------------------------------------------------------------------
# 反復ごとの道と棄却
# --------------------------------------------------------------------------


def path_outcome(result: Mapping[str, Any], alpha: float, label: str) -> tuple[bool, bool]:
    """答える問い: この当てはめは (棄却したか, 失敗したか)。失敗は非棄却(ADR-128 決定1 (A2))。

    失敗でないのに p 値が無い・df が 2 でない当てはめは、黙って数えず止まる。
    """
    if result.get("fit_failed", False):
        return False, True
    if result.get("p_value") is None or result.get("df") != PRIMARY_DF:
        raise power_sim.PowerSimError(f"{label}: 失敗でないのに p 値が無いか df ≠ {PRIMARY_DF}: {result.get('df')}")
    return float(result["p_value"]) < alpha, False


def rep_record(rep: int, verdict: CeilingVerdict, logit: Mapping[str, Any], lmm: Mapping[str, Any],
               alpha: float, label: str) -> dict[str, Any]:
    """答える問い: この反復は、どの道を通り、棄却したか(両方の道の結果も残す)。"""
    logit_reject, logit_failed = path_outcome(logit, alpha, f"{label} logit")
    lmm_reject, lmm_failed = path_outcome(lmm, alpha, f"{label} lmm")
    on_c = verdict.ceiling
    return {
        "rep": rep,
        "ceiling": verdict.ceiling,
        "hits": [list(h) for h in verdict.hits],
        "path": PATH_C if on_c else PATH_LOGIT,
        "reject": lmm_reject if on_c else logit_reject,
        "path_failed": lmm_failed if on_c else logit_failed,
        "logit_p": logit.get("p_value"),
        "logit_failed": logit_failed,
        "lmm_p": lmm.get("p_value"),
        "lmm_failed": lmm_failed,
    }


# --------------------------------------------------------------------------
# 点の記述と門(§6.1・§6.4)
# --------------------------------------------------------------------------


def _lower(count: int, n: int, level: float) -> float | None:
    return None if n == 0 else power_sim.clopper_pearson_lower(count, n, level)


def gate_verdict(count: int, n: int, rule: GateRule) -> dict[str, Any]:
    """答える問い: `count / n` の CP 下端は閾値を超えるか(n = 0 は判定できない = 閉じない。記録する)。"""
    lower = _lower(count, n, rule.ci_level)
    return {
        **power_sim._rate_with_interval(count, n, rule.ci_level),
        "threshold": rule.closes_if_lower_above,
        "evaluable": n > 0,
        "closed": lower is not None and lower > rule.closes_if_lower_above,
    }


def hit_counts(records: Sequence[Mapping[str, Any]], tasks: Sequence[str], coverages: Sequence[str]) -> dict[str, Any]:
    """答える問い: 天井の判定は何回当たり、どのセルがどちら向きに当てたか(§6.1 の 1 行目)。"""
    by_cell = {
        f"{t}.{c}": {DIRECTION_ALL_RULE: 0, DIRECTION_NO_RULE: 0} for t in tasks for c in coverages
    }
    for record in records:
        for task, coverage, direction in record["hits"]:
            by_cell[f"{task}.{coverage}"][direction] += 1
    return {"n_ceiling": sum(1 for r in records if r["ceiling"]), "by_cell": by_cell}


def path_breakdown(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """答える問い: 道ごとに、何反復が通り、何回棄却し、何回当てはめに失敗したか。"""
    out = {}
    for path in (PATH_LOGIT, PATH_C):
        on = [r for r in records if r["path"] == path]
        out[path] = {
            "n": len(on),
            "n_reject": sum(1 for r in on if r["reject"]),
            "n_fit_failed": sum(1 for r in on if r["path_failed"]),
        }
    return out


def c_path_description(
    lmm_results: Sequence[Mapping[str, Any]], coverages: Sequence[str], true_contrasts: Mapping[str, float],
    tost: power_sim.TostSpec, quantiles: Sequence[float],
) -> dict[str, Any]:
    """答える問い: C の道に入った反復の LMM の係数・真値との差・最小 Δ・当てはめの段・singular は(§6.1。成功だけの量は選択の偏りあり)。"""
    done = [r for r in lmm_results if not r.get("fit_failed", False)]
    bias = {
        cov: power_sim.quantile_dict(
            [float(r[f"interaction_{cov}_est"]) - true_contrasts[cov] for r in done], quantiles
        )
        for cov in coverages[1:]
    }
    margins = [power_sim.equivalence_margin(r, tost) for r in done]
    return {
        "n": len(lmm_results),
        "n_fit_failed": len(lmm_results) - len(done),
        "fit_stage_counts": power_sim.fit_stage_counts(lmm_results),
        "n_singular": sum(1 for r in lmm_results if r.get("full_singular") or r.get("add_singular")),
        "n_refit": sum(1 for r in lmm_results if r.get("full_refit_done") or r.get("add_refit_done")),
        "interaction_coefficients": power_sim.summarise_coefficients(lmm_results, coverages, quantiles),
        "estimate_minus_true_quantiles": bias,
        # 成功した反復だけの最小 Δ(Δ は決めない。ADR-132 決定5)。失敗は n_fit_failed で読む
        "tost_min_margin_quantiles": power_sim.quantile_dict(margins, quantiles) if margins else None,
    }


def all_tables_lmm(lmm_results: Sequence[Mapping[str, Any]], alpha: float) -> dict[str, Any]:
    """答える問い: 天井かどうかに関わらず全部の表に LMM を当てると、何回棄却し失敗したか(記述だけ。門に使わない)。"""
    outcomes = [path_outcome(r, alpha, "lmm") for r in lmm_results]
    return {
        "n": len(lmm_results),
        "n_reject": sum(1 for reject, _ in outcomes if reject),
        "n_fit_failed": sum(1 for _, failed in outcomes if failed),
        "fit_stage_counts": power_sim.fit_stage_counts(lmm_results),
    }


def point_summary(
    spec: EvalSpec, sheet_id: str, records: Sequence[Mapping[str, Any]], lmm_results: Sequence[Mapping[str, Any]],
    profile: power_sim.EffectProfile, tost: power_sim.TostSpec, true_values: Mapping[str, Any], full_run: bool,
) -> dict[str, Any]:
    """答える問い: この点の §6.1 の量と、G1(対象の点だけ)・G2 の判定は何か。"""
    n = len(records)
    n_reject = sum(1 for r in records if r["reject"])
    breakdown = path_breakdown(records)
    c_results = [lmm for rec, lmm in zip(records, lmm_results) if rec["path"] == PATH_C]
    summary = {
        "n_rep": n,
        "ceiling": hit_counts(records, profile.tasks, profile.coverages),
        "branched": {
            **power_sim._rate_with_interval(n_reject, n, spec.ci_level),
            "by_path": breakdown,
        },
        "c_path": c_path_description(
            c_results, profile.coverages, true_values["probability_scale_contrasts"], tost, spec.quantiles
        ),
        "lmm_all_tables": all_tables_lmm(lmm_results, spec.alpha),
        "true_values": true_values,
        "true_logit_interaction_contrasts": dict(profile.interaction_contrasts),
        "g2": gate_verdict(breakdown[PATH_C]["n_fit_failed"], breakdown[PATH_C]["n"], spec.g2),
    }
    if sheet_id in spec.g1_sheets:
        summary["g1"] = gate_verdict(n_reject, n, spec.g1)
    if not full_run:
        summary["gates_note"] = f"max_rep < n_rep: smoke only, gates are NOT evaluated (n = {n})"
        summary["g2"]["closed"] = None
        if "g1" in summary:
            summary["g1"]["closed"] = None
    return summary


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------


def evaluate_sheet(spec: EvalSpec, source: Source, sheet: power_sim.Sheet, out_dir: Path, rscript: str,
                   max_rep: int) -> dict[str, Any]:
    """1 枚のシートを評価する。答える問い: このシートの各点で、分岐した手続き全体は何をするか。"""
    config = source.config
    profile = power_sim.ceiling_profile(config, sheet)
    s2_item = float(require(config, "dgp.s2_item"))
    s2_tmpl = float(require(config, "dgp.s2_tmpl"))
    rng_seed = int(require(config, "simulation.rng_seed"))
    nodes = power_sim.load_ceiling_report_spec(config).quadrature_nodes
    src_dir = source.results_dir / sheet.sheet_id
    pairs = manifest_pairs(src_dir)
    lmm_dir = out_dir / sheet.sheet_id / "lmm"
    lmm_dir.mkdir(parents=True, exist_ok=True)
    points = []
    for key in sheet.points:
        levels = power_sim.load_levels(config, key.n_item)
        tag = key.tag()
        verdicts, logits, jobs, outputs = [], [], [], []
        n_in_manifest = 0
        for rep in range(max_rep):
            frame_path = src_dir / "frames" / f"frame_{tag}_{rep:04d}.csv"
            fit_name = f"fit_{tag}_{rep:04d}.json"
            logit = json.loads((src_dir / "fits" / fit_name).read_text(encoding="ascii"))
            expected = power_sim.draw_frame(
                levels, profile.eta, key.sigma, key.rho, s2_item, s2_tmpl,
                power_sim.replication_rng(rng_seed, sheet.sheet_id, key, rep),
                tau=power_sim.frame_tau(sheet, key.sigma),
            )
            rows = verify_frame(frame_path, expected, logit, fit_name, pairs)
            n_in_manifest += frame_path.name in pairs
            verdicts.append(ceiling_rule(rows, levels.tasks, levels.coverages))
            logits.append(logit)
            out_path = lmm_dir / f"lmm_{tag}_{rep:04d}.json"
            outputs.append(out_path)
            if not out_path.exists():
                jobs.append((frame_path, out_path))
        started = time.monotonic()
        seconds = (
            run_lmm_fits(spec, rscript, out_dir / sheet.sheet_id / f"lmm_manifest_{tag}", jobs, config["fit"])
            if jobs else {}
        )
        wall = time.monotonic() - started
        lmm_results = [json.loads(p.read_text(encoding="ascii")) for p in outputs]
        for rep, (result, verdict) in enumerate(zip(lmm_results, verdicts)):
            if result.get("csv") != f"frame_{tag}_{rep:04d}.csv" or result.get("optimizer") != spec.lmm_optimizer:
                raise power_sim.PowerSimError(f"{sheet.sheet_id} 反復 {rep} の LMM の出力が表・最適化と合わない")
        records = [
            rep_record(rep, verdict, logit, lmm, spec.alpha, f"{sheet.sheet_id} rep {rep}")
            for rep, (verdict, logit, lmm) in enumerate(zip(verdicts, logits, lmm_results))
        ]
        power_sim.write_json_atomic(out_dir / sheet.sheet_id / f"reps_{tag}.json", records)
        true_values = power_sim.ceiling_true_values(profile, key.sigma, s2_item, s2_tmpl, nodes)
        point = point_summary(spec, sheet.sheet_id, records, lmm_results, profile,
                              power_sim.tost_spec(config, profile), true_values, full_run=max_rep == spec.n_rep)
        point.update({
            **point_coordinates(key),
            "frames_verified": max_rep,
            "frames_listed_in_manifest": n_in_manifest,
            "lmm_fitted_this_invocation": len(jobs),
            "lmm_wall_seconds_this_invocation": wall,
            "lmm_seconds_per_table": sorted(seconds.values()),
        })
        points.append(point)
    return {"source": source.source_id, "source_run_id": source.run_id, "eta": profile.eta.tolist(),
            "points": points}


def point_coordinates(key: power_sim.PointKey) -> dict[str, Any]:
    """答える問い: この点の座標は(`n_item`・`sigma`・`rho`)。"""
    return {"n_item": key.n_item, "sigma": key.sigma, "rho": key.rho}


def overall_gates(sheets: Mapping[str, Any], full_run: bool) -> dict[str, Any]:
    """答える問い: G1・G2 は閉じたか(ADR-133 決定4: どちらかが閉じれば C は採らない。両方開いても採否は人間)。"""
    g1 = [(sid, p["g1"]) for sid, body in sheets.items() for p in body["points"] if "g1" in p]
    g2 = [(sid, p["g2"]) for sid, body in sheets.items() for p in body["points"]]
    if not full_run:
        return {"evaluated": False, "note": "smoke (max_rep < n_rep): gates are not evaluated"}
    g1_closed = [sid for sid, g in g1 if g["closed"]]
    g2_closed = [sid for sid, g in g2 if g["closed"]]
    return {
        "evaluated": True,
        "g1": {"closed": bool(g1_closed), "closed_at": g1_closed, "n_points": len(g1)},
        "g2": {
            "closed": bool(g2_closed), "closed_at": g2_closed, "n_points": len(g2),
            "not_evaluable_at": [sid for sid, g in g2 if not g["evaluable"]],
        },
        "effect": (
            "ADR-133 decision 4: if G1 or G2 is closed, C is not adopted. If both are open, adoption is "
            "decided by the human in a separate ADR after reading the description (nothing is adopted here)."
        ),
    }


def record_eval_run(out_dir: Path, config: Mapping[str, Any], config_path: Path, n_workers: int,
                    max_rep: int) -> dict[str, Any]:
    """答える問い: この評価の数は、どの run の、どの commit の、どの config から出たか(再開なら run_id を作り直さない)。"""
    resolved = json.loads(json.dumps(config))
    resolved_path = out_dir / RESOLVED_CONFIG_FILE
    info_path = out_dir / RUN_INFO_FILE
    if resolved_path.exists():
        if json.loads(resolved_path.read_text(encoding="utf-8")) != resolved:
            raise power_sim.PowerSimError(f"{out_dir} は別の config で始まった run である。別の --out-dir を使うこと")
        info = json.loads(info_path.read_text(encoding="utf-8"))
    else:
        now = artifacts.utc_now()
        info = {
            "run_id": f"{now.strftime('%Y%m%d_%H%M%S')}_{require(config, 'analysis.id')}",
            "created_utc": now.isoformat(),
            "git_sha": artifacts.capture_git_head_sha(),
            "config_source": str(config_path),
        }
        artifacts.write_git_sha(out_dir)
        artifacts.write_config_copy(out_dir, config_path)
        power_sim.write_json_atomic(resolved_path, resolved)
        power_sim.write_json_atomic(info_path, info)
    invocation = {
        "started_utc": artifacts.utc_now().isoformat(),
        "git_sha": artifacts.capture_git_head_sha(),
        "tracked_diff_empty": artifacts.capture_git_diff_head() == "",
        "n_workers": n_workers,
        "max_rep": max_rep,
    }
    with (out_dir / INVOCATIONS_FILE).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(invocation, ensure_ascii=False) + "\n")
    return info


def run(config: Mapping[str, Any], config_path: Path, out_dir: Path, spec: EvalSpec, max_rep: int) -> dict[str, Any]:
    """評価を回して要約を書く。答える問い: 全 10 点で、分岐した手続き全体の記述と G1・G2 の判定は何か。"""
    if not 1 <= max_rep <= spec.n_rep:
        raise ConfigError(f"--max-rep は 1〜{spec.n_rep}: {max_rep}")
    rscript = power_sim.resolve_rscript(spec.rscript)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = record_eval_run(out_dir, config, config_path, spec.n_workers, max_rep)
    sheets = {
        sheet.sheet_id: evaluate_sheet(spec, source, sheet, out_dir, rscript, max_rep)
        for source in spec.sources
        for sheet in source.sheets
    }
    full_run = max_rep == spec.n_rep
    summary = power_sim.json_safe({
        **info,
        "max_rep": max_rep,
        "n_rep": spec.n_rep,
        "alpha": spec.alpha,
        "lmm": {"link": "identity", "reml": False, "optimizer": spec.lmm_optimizer},
        "rule": "ceiling = any of the 6 cells is n/n or 0/n over all seeds x items (ADR-132 decision 2)",
        "failure_counted_as": "non-reject, kept in the denominator (ADR-128 decision 1 (A2))",
        "note": "synthetic data under ASSUMED values; descriptive only, NOT the real experiment (PLAN-046 trap 6)",
        "gates": overall_gates(sheets, full_run),
        "sheets": sheets,
    })
    power_sim.write_json_atomic(out_dir / SUMMARY_FILE, summary)
    return summary


def describe(spec: EvalSpec) -> list[str]:
    """答える問い: 何枚の表に LMM を当て、どの門を見るか(R は呼ばない。表も読まない)。"""
    lines = []
    total = 0
    for source in spec.sources:
        n_tables = sum(len(s.points) for s in source.sheets) * spec.n_rep
        total += n_tables
        lines.append(f"source {source.source_id}: {source.results_dir} run_id {source.run_id}  "
                     f"sheets {[s.sheet_id for s in source.sheets]}  tables {n_tables}")
    lines += [
        f"lmm       : identity link, ML, optimizer {spec.lmm_optimizer}, reduction = the logit path (ADR-133)",
        f"tables    : {total} (LMM is fitted to every table; the branched path uses it only where the rule fires)",
        f"G1        : sheets {list(spec.g1_sheets)}; closes if CP{spec.g1.ci_level:g} lower > "
        f"{spec.g1.closes_if_lower_above:g}",
        f"G2        : every point; closes if CP{spec.g2.ci_level:g} lower > {spec.g2.closes_if_lower_above:g}",
        f"workers   : {spec.n_workers}",
        "cost      : about 2 s per table serially (2026-10-22 trial on 2 tables; measure with a smoke)",
    ]
    return lines


def parse_source_dirs(values: Sequence[str]) -> dict[str, Path]:
    """答える問い: `--source-dir ID=PATH` は、どの元の run の在り処を上書きするか。"""
    out = {}
    for value in values:
        source_id, sep, path = value.partition("=")
        if not sep or not source_id or not path:
            raise ConfigError(f"--source-dir は ID=PATH: {value!r}")
        out[source_id] = Path(path)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="表の数と門だけを出す。R を呼ばない")
    parser.add_argument("--max-rep", type=int, help="各点の最初の何反復だけを評価するか(スモーク。門は判定しない)")
    parser.add_argument("--workers", type=int, help="config の lmm.n_workers を上書きする")
    parser.add_argument("--rscript", help="config の lmm.rscript を上書きする")
    parser.add_argument("--source-dir", action="append", default=[],
                        help="ID=PATH。元の run の results_dir を上書きする(スモーク用)")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    spec = load_eval_spec(config, parse_source_dirs(args.source_dir), args.workers, args.rscript)
    if args.dry_run:
        for line in describe(spec):
            print(line)
        return 0
    if args.out_dir is None:
        parser.error("--out-dir が要る(--dry-run でない場合)")
    summary = run(config, args.config, args.out_dir, spec, args.max_rep or spec.n_rep)
    print(json.dumps({
        "run_id": summary["run_id"],
        "max_rep": summary["max_rep"],
        "gates": summary["gates"],
        "branched": {
            sid: [{"rate": p["branched"]["rate"], "ci": p["branched"]["ci"], "n_ceiling": p["ceiling"]["n_ceiling"]}
                  for p in body["points"]]
            for sid, body in summary["sheets"].items()
        },
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
