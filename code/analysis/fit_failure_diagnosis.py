"""PLAN-042: run2 の「当てはめ失敗」の診断(D0〜D4)。表を作り直し → R に投げ → §2.2 の行ごとに数える。

答える問い: 門の誤指定のシートで「当てはめ失敗」と数えた反復は、(a) 別の最適化で収束する当てはめか、
(b) 数値的に無害な揺れか、(c) 本当に当てはまらない表か。そして失敗した反復で LRT を出すと棄却するか。
**規則(ADR-059・ADR-124 D2')は変えない。**ここは数えるだけで、「どの選択肢を採るか」は人間が決める(CLAUDE.md §8)。

層は 3 つ(skill `code-style` §2): 選ぶ(`select_targets`)/ 当てる(`fit_failure_diagnosis.R`。この module は表を作って
R を呼ぶだけ)/ 数える(`evaluate_case` 以降。**R を呼ばない純関数**で、合成データでテストする)。
当てはめの定義(縮退の式・judge_one・ADR-059 の許容)は `power_sim_fit.R` のものを R 側が借りる。

実行: python -X utf8 -m code.analysis.fit_failure_diagnosis --config configs/fit_failure_diagnosis.yaml [--select-only]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, TypeVar

from scipy.stats import beta as beta_distribution
from scipy.stats import chi2

from code.analysis import power_sim as ps
from code.config import ConfigError, load_config, require

R_SCRIPT = Path(__file__).resolve().parent / "fit_failure_diagnosis.R"
# power_sim_fit.R の「# ---- driver」より上を R 側が借りる。目印が消えたら診断は借りる範囲を決められない
DRIVER_MARKER = "# ---- driver"

ROLE_FAILURE = "failure"
ROLE_CONTROL = "control"

# §2.2 の行。判定の行(「支える」を付ける)と記述の行(付けない)
ROW_1A = "1a"
ROW_1B = "1b"
ROW_3_4 = "3_4"
ROW_3_4_FIT0 = "3_4_fit0"
ROW_2 = "2"
ROW_R = "R"
ROW_U = "U"
JUDGEMENT_ROWS = (ROW_1A, ROW_1B, ROW_3_4)
DESCRIPTIVE_ROWS = (ROW_2, ROW_R, ROW_U)
# 数え直しに使う p 値のキー(`CaseEval.p`)
P_FINAL = "final"        # ADR-059 の当て直しの後(power_sim_fit.R の p_value と同じ手順)
P_FIT0 = "fit0"          # 当て直しの前(感度)
P_ALLFIT_1A = "allfit_1a"
P_ALLFIT_1B = "allfit_1b"
# 床の full / add の記録のキー(fit_failure_diagnosis.R の出力)
FLOOR_MODELS = ("floor_full", "floor_add")
ALLFIT_MODELS = ("allfit_full", "allfit_add")

T = TypeVar("T")


class DiagnosisError(RuntimeError):
    """診断の前提が崩れた(件数が既知と合わない・再現しない・形が違う)。黙って進めず止める。"""


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GatePointCount:
    """run2 で既知の、門の 1 点の失敗の件数。答える問い: 選んだ失敗は run2 の集計と一致するか。"""

    sheet_id: str
    tau: float
    n_failed: int


@dataclass(frozen=True)
class DiagnosisSpec:
    """診断の設定(`configs/fit_failure_diagnosis.yaml`)。答える問い: 何を・どの許容で数えるか。"""

    run_dir: Path
    out_json: Path
    work_dir: Path
    n_rep: int
    n_workers: int
    controls_per_gate_point: int
    d0_loglik_tolerance: float
    allfit_start_from_mle: bool
    align_loglik_tolerance: float
    align_fixef_tolerance_se: float
    min_aligned: int
    trivial_loglik_gain_below: float
    trivial_shift_se_below: float
    large_shift_se_above: float
    separation_numerator: int
    separation_denominator: int
    boundary_sd_below: float
    expected_failures_by_sheet: Mapping[str, int]
    expected_gate_failures: tuple[GatePointCount, ...]
    expected_refit_silent: tuple[int, ...]


def load_spec(config: Mapping[str, Any], repo_root: Path) -> DiagnosisSpec:
    """config の `diagnosis` を読む。答える問い: 数え方の値は宣言されているか。null は止まる。"""

    def get(key: str) -> Any:
        return require(config, f"diagnosis.{key}")

    gate_counts = tuple(
        GatePointCount(str(row["sheet"]), float(row["tau"]), int(row["n"]))
        for row in get("expected.failures_at_gate_points")
    )
    silent = tuple(int(x) for x in get("expected.refit_silent_at_gate_points"))
    if len(silent) != len(gate_counts):
        raise ConfigError("expected.refit_silent_at_gate_points は failures_at_gate_points と同じ長さ")
    if int(get("separation_share.denominator")) < 1:
        raise ConfigError("separation_share.denominator は 1 以上")
    return DiagnosisSpec(
        run_dir=repo_root / str(get("run_dir")),
        out_json=repo_root / str(get("out_json")),
        work_dir=repo_root / str(get("work_dir")),
        n_rep=int(get("n_rep")),
        n_workers=int(get("n_workers")),
        controls_per_gate_point=int(get("controls_per_gate_point")),
        d0_loglik_tolerance=float(get("d0_loglik_tolerance")),
        allfit_start_from_mle=bool(get("allfit.start_from_mle")),
        align_loglik_tolerance=float(get("allfit.loglik_tolerance")),
        align_fixef_tolerance_se=float(get("allfit.fixef_tolerance_se")),
        min_aligned=int(get("allfit.min_aligned")),
        trivial_loglik_gain_below=float(get("size.trivial_loglik_gain_below")),
        trivial_shift_se_below=float(get("size.trivial_shift_se_below")),
        large_shift_se_above=float(get("size.large_shift_se_above")),
        separation_numerator=int(get("separation_share.numerator")),
        separation_denominator=int(get("separation_share.denominator")),
        boundary_sd_below=float(get("boundary_sd_below")),
        expected_failures_by_sheet={
            str(k): int(v) for k, v in get("expected.failures_by_sheet").items()
        },
        expected_gate_failures=gate_counts,
        expected_refit_silent=silent,
    )


# --------------------------------------------------------------------------
# 選ぶ
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Target:
    """診断する反復 1 つ。答える問い: どのシート・点・反復の表を作り直すか。"""

    sheet_id: str
    key: ps.PointKey
    rep: int
    role: str

    @property
    def case_id(self) -> str:
        return f"{self.sheet_id}__{self.key.tag()}__{self.rep:04d}"


def fit_json_path(run_dir: Path, sheet_id: str, key: ps.PointKey, rep: int) -> Path:
    return run_dir / sheet_id / "fits" / f"fit_{key.tag()}_{rep:04d}.json"


def load_point_fits(run_dir: Path, sheet_id: str, key: ps.PointKey, n_rep: int) -> list[dict[str, Any]]:
    """答える問い: この点の fit の JSON は反復の番号どおり `n_rep` 本そろっているか(欠けたら止まる)。"""
    fits = []
    for rep in range(n_rep):
        path = fit_json_path(run_dir, sheet_id, key, rep)
        if not path.exists():
            raise DiagnosisError(f"fit が無い: {path}(診断は門を判定した段 n_rep = {n_rep} を前提にする)")
        fits.append(json.loads(path.read_text(encoding="ascii")))
    return fits


def floor_failure_size(fit: Mapping[str, Any]) -> dict[str, float]:
    """答える問い: 床の段で失敗した当てはめの logLik の改善と移動(SE 単位)の最大は(JSON の記録から)。

    stage1_interim.py の `floor_failure_size` と同じ定義である(その値が §0 の 74 / 37 / 49 件の出所)。
    """
    top = max(level["level"] for level in fit["levels"])
    failed = [lv for lv in fit["levels"] if lv["level"] == top and lv["failed"]]
    if not failed:
        raise DiagnosisError("床で失敗した当てはめの記録が無い")
    return {
        "loglik_gain": max(lv["loglik_gain"] for lv in failed),
        "max_shift": max(lv["max_shift"] for lv in failed),
        "refit_all_silent": all(lv["n_warnings"] == 0 for lv in failed),
    }


@dataclass(frozen=True)
class LegacyGateSpec:
    """run2 の門の形(全シート共通の `sheets` × `tau` の直積。ADR-124 D4)。答える問い: run2 はどの点を門に使ったか。

    ★PLAN-043 I4(ADR-128 / ADR-129)で `power_sim.GateSpec` はシートごとの判定点に変わった。この診断は
    run2 の記録(`config_resolved.json`)を**当時の規則のまま**読み直すので、旧い形をここに持つ。
    """

    sheet_ids: tuple[str, ...]
    tau: tuple[float, ...]
    ci_level: float
    lower_bound_above: float


def load_legacy_gate_spec(config: Mapping[str, Any]) -> LegacyGateSpec:
    """run2 の config の `simulation.misspecification_gate`(旧い形)を読む。答える問い: run2 の門の点は。"""
    sheet_ids = tuple(str(i) for i in require(config, "simulation.misspecification_gate.sheets"))
    tau = tuple(float(t) for t in require(config, "simulation.misspecification_gate.tau"))
    if not sheet_ids or not tau or len(set(sheet_ids)) != len(sheet_ids):
        raise ConfigError("run2 の門の sheets / tau が空か重複している")
    return LegacyGateSpec(
        sheet_ids=sheet_ids,
        tau=tau,
        ci_level=float(require(config, "simulation.misspecification_gate.ci_level")),
        lower_bound_above=float(require(config, "simulation.misspecification_gate.lower_bound_above")),
    )


def select_targets(
    spec: DiagnosisSpec, sheets: Sequence[ps.Sheet], gate: LegacyGateSpec
) -> tuple[list[Target], dict[tuple[str, float], list[dict[str, Any]]]]:
    """診断する反復を選ぶ。答える問い: 門の 2 枚の失敗と、同じ 2 枚の成功した反復の対照はどれか。

    失敗 = 門のシートの全点の `fit_failed`。対照 = 門の 4 点(`gate.sheet_ids` × `gate.tau`)から、点ごとに
    成功した反復を**反復番号の小さい順に** `controls_per_gate_point` 件(乱数は使わない)。
    run2 で既知の件数(失敗 100・56、門の 4 点の失敗、行 R の件数)と合わなければ止まる。
    """
    by_id = {s.sheet_id: s for s in sheets}
    missing = [i for i in gate.sheet_ids if i not in by_id]
    if missing:
        raise DiagnosisError(f"門のシート {missing} が config に無い")
    fits_by_point: dict[tuple[str, float], list[dict[str, Any]]] = {}
    targets: list[Target] = []
    for sheet_id in gate.sheet_ids:
        for key in by_id[sheet_id].points:
            fits = load_point_fits(spec.run_dir, sheet_id, key, spec.n_rep)
            fits_by_point[(sheet_id, key.sigma)] = fits
            targets += [
                Target(sheet_id, key, rep, ROLE_FAILURE)
                for rep, fit in enumerate(fits) if fit["fit_failed"]
            ]
            if key.sigma in gate.tau:
                ok_reps = [rep for rep, fit in enumerate(fits) if not fit["fit_failed"]]
                if len(ok_reps) < spec.controls_per_gate_point:
                    raise DiagnosisError(f"{sheet_id} tau = {key.sigma} の成功した反復が対照の件数に足りない")
                targets += [
                    Target(sheet_id, key, rep, ROLE_CONTROL)
                    for rep in ok_reps[: spec.controls_per_gate_point]
                ]
    check_expected_counts(spec, gate, fits_by_point)
    return targets, fits_by_point


def check_expected_counts(
    spec: DiagnosisSpec, gate: LegacyGateSpec, fits_by_point: Mapping[tuple[str, float], Sequence[Mapping[str, Any]]]
) -> None:
    """答える問い: 読んだ fit は run2 の集計(stage1_interim.json)と同じ件数になるか。合わなければ止まる。"""
    for sheet_id, expected in spec.expected_failures_by_sheet.items():
        got = sum(
            sum(1 for fit in fits if fit["fit_failed"])
            for (sid, _), fits in fits_by_point.items() if sid == sheet_id
        )
        if got != expected:
            raise DiagnosisError(f"{sheet_id} の失敗が既知 {expected} 件と合わない: {got}")
    silent_got = []
    for row in spec.expected_gate_failures:
        fits = fits_by_point.get((row.sheet_id, row.tau))
        if fits is None:
            raise DiagnosisError(f"門の点 ({row.sheet_id}, tau = {row.tau}) が読み込まれていない")
        failed = [fit for fit in fits if fit["fit_failed"]]
        if len(failed) != row.n_failed:
            raise DiagnosisError(
                f"({row.sheet_id}, tau = {row.tau}) の失敗が既知 {row.n_failed} 件と合わない: {len(failed)}"
            )
        silent_got.append(sum(1 for fit in failed if floor_failure_size(fit)["refit_all_silent"]))
    if tuple(silent_got) != spec.expected_refit_silent:
        raise DiagnosisError(
            f"当て直しの後に message が無い失敗の件数が既知 {list(spec.expected_refit_silent)} と合わない: {silent_got}"
        )
    if {sid for sid, _ in fits_by_point} != set(gate.sheet_ids):
        raise DiagnosisError("読んだシートが門のシートと違う")


# --------------------------------------------------------------------------
# 表を作り直す・R に投げる
# --------------------------------------------------------------------------


def rebuild_frame_rows(
    config: Mapping[str, Any], sheet: ps.Sheet, key: ps.PointKey, rep: int
) -> list[tuple[Any, ...]]:
    """答える問い: この反復の表は、run2 が当てたものと同じか(`run_sheet_stage` と同じ呼び方で作り直す)。"""
    profile = ps.build_profile(config["effect"], sheet.profile)
    seed_direction = (
        None
        if sheet.seed_interaction is None
        else ps.seed_interaction_direction(
            ps.build_profile(config["effect"], sheet.seed_interaction.direction_profile),
            sheet.seed_interaction.scale,
        )
    )
    return ps.draw_frame(
        ps.load_levels(config, key.n_item), profile.eta, key.sigma, key.rho,
        float(require(config, "dgp.s2_item")), float(require(config, "dgp.s2_tmpl")),
        ps.replication_rng(int(require(config, "simulation.rng_seed")), sheet.sheet_id, key, rep),
        tau=ps.frame_tau(sheet, key.sigma), seed_direction=seed_direction,
    )


def format_loglik(value: float | None) -> str:
    """答える問い: manifest に logLik をどう書くか(null は NA)。"""
    return "NA" if value is None else repr(float(value))


def case_line(target: Target, csv_path: Path, out_path: Path, fit: Mapping[str, Any]) -> str:
    """manifest の `case=` の行。答える問い: R はこの反復を何と照らし合わせるか(D0)。

    照らす相手は、その反復が止まった段(`reduction_level`)の logLik と失敗の判定である。
    """
    return "case=" + "|".join([
        csv_path.as_posix(), out_path.as_posix(), str(int(fit["reduction_level"])),
        format_loglik(fit["full_logLik"]), format_loglik(fit["add_logLik"]),
        "true" if fit["fit_failed"] else "false", target.case_id,
    ])


def write_diagnosis_manifest(
    path: Path, case_lines: Sequence[str], spec: DiagnosisSpec, refit: Mapping[str, Any], floor_level: int
) -> None:
    """R に渡す平文 manifest を書く。答える問い: R はどの許容で何を診るか(許容は config から流す)。"""
    lines = [
        f"loglik_tolerance={refit['loglik_tolerance']}",
        f"beta_move_tolerance={refit['beta_move_tolerance']}",
        f"floor_level={floor_level}",
        f"d0_loglik_tolerance={spec.d0_loglik_tolerance!r}",
        f"allfit_start_from_mle={'true' if spec.allfit_start_from_mle else 'false'}",
        *case_lines,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def split_evenly(items: Sequence[T], n_shards: int) -> list[list[T]]:
    """答える問い: 反復を何本の R にどう分けるか(連続ブロック。結果は本数に依らない)。"""
    if n_shards < 1:
        raise ConfigError(f"n_workers は 1 以上: {n_shards}")
    if not items:
        return []
    n = min(n_shards, len(items))
    size, extra = divmod(len(items), n)
    shards, start = [], 0
    for i in range(n):
        stop = start + size + (1 if i < extra else 0)
        shards.append(list(items[start:stop]))
        start = stop
    return shards


def run_rscript(rscript: str, libpath: str | None, manifest: Path) -> str:
    """R を 1 回起動して manifest の反復をすべて診る。答える問い: 診断は通ったか(D0 が合わなければ異常終了する)。"""
    done = subprocess.run([rscript, str(R_SCRIPT), libpath or "", str(manifest)], capture_output=True, text=True)
    if done.returncode != 0:
        raise DiagnosisError(f"Rscript が異常終了した (returncode={done.returncode})\n{done.stdout}\n{done.stderr}")
    return done.stdout


def run_fits(
    spec: DiagnosisSpec, config: Mapping[str, Any], sheets: Sequence[ps.Sheet], targets: Sequence[Target],
    fits_by_point: Mapping[tuple[str, float], Sequence[Mapping[str, Any]]],
    rscript: str, keep_frames: bool,
) -> Path:
    """表を作り直して R に投げ、反復ごとの出力を `work_dir/r_out/` に置く。答える問い: 診断の材料は全部そろったか。

    出力が既にある反復は表も作らない(途中で止まっても続きから回る。R 側も飛ばす)。
    """
    by_id = {s.sheet_id: s for s in sheets}
    frames_dir, out_dir = spec.work_dir / "frames", spec.work_dir / "r_out"
    frames_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[Path, str]] = []   # (csv, case 行)
    pending_csv: list[Path] = []
    for target in targets:
        out_path = out_dir / f"{target.case_id}.json"
        if out_path.exists():
            continue
        csv_path = frames_dir / f"{target.case_id}.csv"
        rows = rebuild_frame_rows(config, by_id[target.sheet_id], target.key, target.rep)
        ps.write_frame_csv(rows, csv_path)
        fit = fits_by_point[(target.sheet_id, target.key.sigma)][target.rep]
        jobs.append((csv_path, case_line(target, csv_path, out_path, fit)))
        pending_csv.append(csv_path)
    floor_level = len(require(config, "fit.reduction_order"))
    manifests = []
    for index, shard in enumerate(split_evenly(jobs, spec.n_workers)):
        manifest = spec.work_dir / f"manifest_{index:02d}.txt"
        write_diagnosis_manifest(manifest, [line for _, line in shard], spec, config["fit"]["refit"], floor_level)
        manifests.append(manifest)
    libpath = config["fit"].get("r_libpath")
    with ThreadPoolExecutor(max_workers=max(1, len(manifests))) as pool:
        futures = [pool.submit(run_rscript, rscript, libpath, m) for m in manifests]
        for future in futures:   # 1 本でも落ちたら止める(D0 が合わない場合を含む。黙って数えない)
            future.result()
    if not keep_frames:
        for csv_path in pending_csv:
            csv_path.unlink(missing_ok=True)
    return out_dir


# --------------------------------------------------------------------------
# 数える(R を呼ばない純関数)
# --------------------------------------------------------------------------


def clopper_pearson_interval(k: int, n: int, level: float) -> list[float]:
    """答える問い: k / n の両側 `level` の Clopper–Pearson 区間は(下端は `power_sim.clopper_pearson_lower`)。"""
    lower = ps.clopper_pearson_lower(k, n, level)
    upper = 1.0 if k == n else float(beta_distribution.ppf(1.0 - (1.0 - level) / 2.0, k + 1, n - k))
    return [lower, upper]


def aligned_optimizers(
    records: Sequence[Mapping[str, Any]], loglik_tolerance: float, *, require_silent: bool
) -> list[Mapping[str, Any]]:
    """答える問い: allFit の最適化のうち、logLik が最大のものと揃っている(差 < 許容)のはどれか。

    対象は**例外なく終わった**最適化。`require_silent` なら、さらに**警告なし**(singular の message は
    警告に数えない = ADR-059 決定1)のもの。揃いの基準は対象の中で logLik が最大のもの(同点は先の方)。
    """
    eligible = [
        r for r in records
        if not r["error"] and r["loglik"] is not None
        and (not require_silent or r["n_msgs_nonsingular"] == 0)
    ]
    if not eligible:
        return []
    best = max(eligible, key=lambda r: r["loglik"])
    return [r for r in eligible if best["loglik"] - r["loglik"] < loglik_tolerance]


def fixef_spread_se(aligned: Sequence[Mapping[str, Any]], se_of: Sequence[float]) -> float:
    """答える問い: 揃った最適化どうしの固定効果の差の最大は、SE(logLik が最大のもの)の何倍か。

    係数ごとの (最大 - 最小) / SE の最大 = 全ての組の差の最大。2 つ以上ないなら 0。
    """
    if len(aligned) < 2:
        return 0.0
    columns = zip(*(r["fixef"] for r in aligned), se_of)
    return max((max(col[:-1]) - min(col[:-1])) / col[-1] for col in columns)


def rescue_one_model(
    records: Sequence[Mapping[str, Any]], spec: DiagnosisSpec, *, require_silent: bool, check_fixef: bool
) -> dict[str, Any]:
    """答える問い: この式(full か add)は、別の最適化で §2.2 の 1a / 1b を満たすか。満たすなら最大の logLik は。"""
    aligned = aligned_optimizers(records, spec.align_loglik_tolerance, require_silent=require_silent)
    out: dict[str, Any] = {
        "n_aligned": len(aligned), "satisfied": False, "loglik": None, "npar": None,
        "fixef_spread_se": None,
        "n_aligned_with_warnings": sum(1 for r in aligned if r["n_msgs_nonsingular"] > 0),
    }
    if not aligned:
        return out
    best = max(aligned, key=lambda r: r["loglik"])
    out["loglik"], out["npar"] = best["loglik"], best["npar"]
    ok = len(aligned) >= spec.min_aligned
    if check_fixef:
        out["fixef_spread_se"] = fixef_spread_se(aligned, best["se"])
        ok = ok and out["fixef_spread_se"] < spec.align_fixef_tolerance_se
    out["satisfied"] = ok
    return out


def lrt_p_from_loglik(loglik_full: float, loglik_add: float, df: int) -> float:
    """答える問い: logLik の差から LRT の p 値は(`anova` の Chisq と同じ 2 × 差。負は 0)。"""
    if df < 1:
        raise DiagnosisError(f"LRT の df が 1 未満: {df}")
    return float(chi2.sf(max(0.0, 2.0 * (loglik_full - loglik_add)), df))


def optimizer_rescue(
    diag: Mapping[str, Any], spec: DiagnosisSpec, *, require_silent: bool, check_fixef: bool
) -> dict[str, Any]:
    """答える問い: この反復は 1a(警告なし)/ 1b(一致だけ)を満たすか。満たせば揃った最適化の LRT の p 値は。

    **full と add の両方**が満たさなければ満たさない。p は両方の「揃った最適化のうち logLik が最大のもの」から。
    """
    full = rescue_one_model(diag["allfit_full"]["records"], spec, require_silent=require_silent, check_fixef=check_fixef)
    add = rescue_one_model(diag["allfit_add"]["records"], spec, require_silent=require_silent, check_fixef=check_fixef)
    satisfied = full["satisfied"] and add["satisfied"]
    p = None
    if satisfied:
        p = lrt_p_from_loglik(full["loglik"], add["loglik"], int(full["npar"]) - int(add["npar"]))
    return {"satisfied": satisfied, "p": p, "full": full, "add": add}


def failed_floor_models(diag: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """答える問い: 床で失敗した当てはめ(full / add のうち `failed` のもの)はどれか。"""
    return [diag[name] for name in FLOOR_MODELS if diag[name]["failed"]]


def floor_size_of(diag: Mapping[str, Any]) -> dict[str, float]:
    """答える問い: 床で失敗した当てはめの logLik の改善と移動の最大は(D2 の再実行の値)。

    当て直せず(例外)に大きさが無いものは無限大に数える(= 「無害」の条件を満たさない側)。
    """
    failed = failed_floor_models(diag)
    if not failed:
        raise DiagnosisError(f"{diag['case_id']}: 床で失敗した当てはめが無い")
    gains = [m["loglik_gain"] if m["loglik_gain"] is not None else math.inf for m in failed]
    shifts = [m["beta_move"] if m["beta_move"] is not None else math.inf for m in failed]
    return {"loglik_gain": max(gains), "max_shift": max(shifts)}


def refit_without_message(diag: Mapping[str, Any]) -> bool:
    """答える問い: 行 R。床で失敗した当てはめのすべてで、当て直しの後に message が 1 つも残っていないか。

    singular の message も数える(stage1_interim.py の `all_refits_silent` = §0 の「49 件」/ 門の 4 点で
    13・6・7・12 件と同じ定義)。当て直せなかった(例外)ものは満たさない。
    """
    return all(m["refit_done"] and m["refit_n_msgs_all"] == 0 for m in failed_floor_models(diag))


def same_side(p_a: float | None, p_b: float | None, alpha: float) -> bool:
    """答える問い: 2 つの p 値は α で同じ側(両方棄却 / 両方非棄却)か。片方でも無ければ偽。"""
    if p_a is None or p_b is None:
        return False
    return (p_a < alpha) == (p_b < alpha)


@dataclass(frozen=True)
class CaseEval:
    """反復 1 つの評価。答える問い: この反復は §2.2 のどの行を満たし、各 p 値は何か(失敗の反復のみ意味を持つ)。"""

    target: Target
    fit_failed: bool
    p_json: float | None
    p: Mapping[str, float | None]
    in_row: Mapping[str, bool]
    floor_size: Mapping[str, float] | None
    detail: Mapping[str, Any]

    @property
    def p_union(self) -> float | None:
        """U の p 値。優先は 1a → 1b → 当て直しの後(2 と R)。決めるのは行の定義側(PLAN-042 §7)。"""
        if self.in_row[ROW_1A]:
            return self.p[P_ALLFIT_1A]
        if self.in_row[ROW_1B]:
            return self.p[P_ALLFIT_1B]
        return self.p[P_FINAL]


def evaluate_case(target: Target, fit: Mapping[str, Any], diag: Mapping[str, Any], spec: DiagnosisSpec, alpha: float) -> CaseEval:
    """1 反復を評価する。答える問い: §2.2 の各行の条件を満たすか(判定には使わない記述を含む)。

    D0 が合わなければここで止まる(R 側でも止まるが、読み込んだ出力の食い違いを二重に見る)。
    """
    if not diag["d0"]["ok"]:
        raise DiagnosisError(f"{target.case_id}: D0 が合わない")
    p_final, p_fit0 = diag["p_final"], diag["p_fit0"]
    rescue_1a = optimizer_rescue(diag, spec, require_silent=True, check_fixef=False)
    rescue_1b = optimizer_rescue(diag, spec, require_silent=False, check_fixef=True)
    failed = bool(fit["fit_failed"])
    size = floor_size_of(diag) if failed else None
    if failed:
        json_size = floor_failure_size(fit)
        for key in ("loglik_gain", "max_shift"):
            if not math.isclose(size[key], json_size[key], rel_tol=1e-6, abs_tol=1e-9):
                raise DiagnosisError(f"{target.case_id}: 再実行の {key} が fit の記録と違う")
    row2 = bool(
        failed and same_side(p_final, p_fit0, alpha)
        and size["loglik_gain"] < spec.trivial_loglik_gain_below
        and size["max_shift"] < spec.trivial_shift_se_below
    )
    row_r = bool(failed and refit_without_message(diag))
    in_row = {
        ROW_1A: bool(failed and rescue_1a["satisfied"]),
        ROW_1B: bool(failed and rescue_1b["satisfied"]),
        ROW_3_4: failed, ROW_3_4_FIT0: failed, ROW_2: row2, ROW_R: row_r,
    }
    in_row[ROW_U] = any(in_row[r] for r in (ROW_1A, ROW_1B, ROW_2, ROW_R))
    return CaseEval(
        target=target, fit_failed=failed, p_json=fit["p_value"],
        p={P_FINAL: p_final, P_FIT0: p_fit0, P_ALLFIT_1A: rescue_1a["p"], P_ALLFIT_1B: rescue_1b["p"]},
        in_row=in_row, floor_size=size,
        detail={"rescue_1a": rescue_1a, "rescue_1b": rescue_1b, "diag": diag},
    )


def recount_point(
    n_rep: int, ok_reject: int, failures: Sequence[tuple[bool, float | None]], alpha: float, level: float,
    lower_bound_above: float,
) -> dict[str, Any]:
    """答える問い: 失敗のうち条件を満たすものを p 値で数え直すと、この点の棄却率と CP 区間は。

    `failures` は (条件を満たすか, 数え直しに使う p 値)。**条件を満たさない失敗は D2' どおり棄却のまま**数える。
    条件を満たすのに p 値が無い失敗も棄却のまま数える(不利な側。件数は `n_in_set_without_p`)。
    `opens` = 下端 ≤ 門の閾値(ADR-123 決定6 の逆。開く = 閾値を超えない)。
    """
    in_set = [(ok, p) for ok, p in failures if ok]
    without_p = sum(1 for _, p in in_set if p is None)
    in_set_reject = sum(1 for _, p in in_set if p is not None and p < alpha)
    n_reject = ok_reject + (len(failures) - len(in_set)) + without_p + in_set_reject
    ci = clopper_pearson_interval(n_reject, n_rep, level)
    return {
        "n_rep": n_rep, "n_failed": len(failures), "n_in_set": len(in_set),
        "n_in_set_reject": in_set_reject, "n_in_set_without_p": without_p,
        "n_reject": n_reject, "rate": n_reject / n_rep, "ci": ci, "ci_lower": ci[0],
        "opens": ci[0] <= lower_bound_above,
    }


def failed_only_rate(p_values: Sequence[float | None], alpha: float, level: float) -> dict[str, Any]:
    """答える問い: 失敗した反復だけの棄却率と CP 区間は(p 値が無いものは数えず `n_without_p` に)。"""
    have = [p for p in p_values if p is not None]
    k = sum(1 for p in have if p < alpha)
    return {
        "n": len(have), "n_without_p": len(p_values) - len(have), "n_reject": k,
        "rate": (k / len(have)) if have else None,
        "ci": clopper_pearson_interval(k, len(have), level) if have else None,
    }


@dataclass(frozen=True)
class PointData:
    """門の 1 点。答える問い: 成功した反復の棄却数と、失敗した反復の評価は。"""

    sheet_id: str
    tau: float
    n_rep: int
    ok_reject: int
    failures: tuple[CaseEval, ...]


def row_p(case: CaseEval, row: str) -> float | None:
    """答える問い: この行は数え直しにどの p 値を使うか(§2.2。U は `p_union`)。"""
    if row == ROW_1A:
        return case.p[P_ALLFIT_1A]
    if row == ROW_1B:
        return case.p[P_ALLFIT_1B]
    if row == ROW_3_4_FIT0:
        return case.p[P_FIT0]
    if row == ROW_U:
        return case.p_union
    return case.p[P_FINAL]


def evaluate_row(row: str, points: Sequence[PointData], alpha: float, level: float, bound: float) -> dict[str, Any]:
    """答える問い: この行の条件を満たす失敗を p 値で数え直すと、門の各点はどうなるか。「支える」= 4 点すべて開く。"""
    by_point = []
    for point in points:
        failures = [(c.in_row[row], row_p(c, row)) for c in point.failures]
        recount = recount_point(point.n_rep, point.ok_reject, failures, alpha, level, bound)
        by_point.append({"sheet": point.sheet_id, "tau": point.tau, **recount})
    return {
        "by_point": by_point,
        "n_in_set_total": sum(p["n_in_set"] for p in by_point),
        "opens_at_all_points": all(p["opens"] for p in by_point),
    }


def row_5(failures: Sequence[CaseEval], spec: DiagnosisSpec) -> dict[str, Any]:
    """答える問い: 行 5(分離)。移動 > 10 SE の失敗のうち、最も動いた固定効果のセルが分離していた割合は。

    「分離」= そのセル(その係数を線形予測子に含むセル)のどれかで、どれかのシードの観測規則率が 0 か 1。
    割合 ≥ 2/3(config)で「支える」。門と結びつかない行(支えても門は開かない)。
    """
    cohort = [c for c in failures if c.floor_size and c.floor_size["max_shift"] > spec.large_shift_se_above]
    rows = []
    for case in cohort:
        rows.append({"case_id": case.target.case_id, **separation_of(case.detail["diag"])})
    n_sep = sum(1 for r in rows if r["separated"])
    n = len(rows)
    return {
        "n_cohort": n, "n_separated": n_sep, "share": (n_sep / n) if n else None,
        "threshold": f"{spec.separation_numerator}/{spec.separation_denominator}",
        "supports": bool(n) and n_sep * spec.separation_denominator >= spec.separation_numerator * n,
        "cases": rows,
    }


def cells_of_coefficient(name: str, cells: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """答える問い: この固定効果の係数が線形予測子に入るセル(タスク型, 被覆)はどれか。

    処理対比(treatment coding): 切片 = 全セル / `task<水準>` = そのタスク型の全被覆 / `coverage<水準>` =
    その被覆の全タスク型 / `task<水準>:coverage<水準>` = その 1 セル。水準名は `cells` から引く。
    """
    tasks = sorted({t for t, _ in cells})
    covs = sorted({c for _, c in cells})
    if name == "(Intercept)":
        return list(cells)
    wanted_task: str | None = None
    wanted_cov: str | None = None
    for part in name.split(":"):
        task_hit = [t for t in tasks if part == f"task{t}"]
        cov_hit = [c for c in covs if part == f"coverage{c}"]
        if task_hit:
            wanted_task = task_hit[0]
        elif cov_hit:
            wanted_cov = cov_hit[0]
        else:
            raise DiagnosisError(f"固定効果 {name!r} の部分 {part!r} が task / coverage の水準に当たらない")
    return [
        (t, c) for t, c in cells
        if (wanted_task is None or t == wanted_task) and (wanted_cov is None or c == wanted_cov)
    ]


def separation_of(diag: Mapping[str, Any]) -> dict[str, Any]:
    """答える問い: 床の当て直しで最も動いた固定効果のセルは、観測規則率が 0 / 1 に張り付いていたか(D3)。

    最も動いたのは、床で失敗した full / add のうち移動(beta_move)が大きいほうの `moved`。
    """
    failed = [m for m in failed_floor_models(diag) if m["moved"] and m["moved"]["name"]]
    if not failed:
        return {"separated": False, "moved": None, "cells": [], "note": "当て直しの記録が無い"}
    model = max(failed, key=lambda m: m["beta_move"])
    moved = model["moved"]
    cell_stats = {(c["task"], c["coverage"]): c for c in diag["cells"]}
    involved = cells_of_coefficient(moved["name"], list(cell_stats))
    stats = [
        {"task": t, "coverage": c, "n_seeds_at_0": cell_stats[(t, c)]["n_seeds_at_0"],
         "n_seeds_at_1": cell_stats[(t, c)]["n_seeds_at_1"], "min_rate": cell_stats[(t, c)]["min_rate"],
         "max_rate": cell_stats[(t, c)]["max_rate"], "pooled_rate": cell_stats[(t, c)]["pooled_rate"]}
        for t, c in involved
    ]
    return {
        "separated": any(s["n_seeds_at_0"] + s["n_seeds_at_1"] > 0 for s in stats),
        "moved": moved, "beta_move": model["beta_move"], "cells": stats,
    }


def new_term_summary(cases: Sequence[CaseEval], boundary_below: float) -> dict[str, Any]:
    """答える問い: D4。床の当てはめの新しい項の SD は、0 に張り付いた(境界)反復が何件か(full・add それぞれ)。"""
    out: dict[str, Any] = {"boundary_sd_below": boundary_below, "n": len(cases)}
    for name in FLOOR_MODELS:
        sds = [c.detail["diag"][name]["sd_new_term"] for c in cases]
        have = [s for s in sds if s is not None]
        out[name] = {
            "n_with_sd": len(have), "n_boundary": sum(1 for s in have if s < boundary_below),
            "median_sd": statistics.median(have) if have else None,
            "min_sd": min(have) if have else None, "max_sd": max(have) if have else None,
        }
    return out


def d0_summary(cases: Sequence[CaseEval]) -> dict[str, Any]:
    """答える問い: D0。再現の確認は全反復で通ったか(最大の logLik の差)。"""
    diffs = []
    for c in cases:
        d0 = c.detail["diag"]["d0"]
        for key in ("full", "add"):
            a, b = d0[f"{key}_logLik"], d0[f"{key}_logLik_json"]
            if a is not None and b is not None:
                diffs.append(abs(a - b))
    return {"n_cases": len(cases), "all_ok": all(c.detail["diag"]["d0"]["ok"] for c in cases),
            "max_abs_loglik_diff": max(diffs) if diffs else None}


def load_case_eval(
    target: Target, fit: Mapping[str, Any], out_dir: Path, spec: DiagnosisSpec, alpha: float
) -> CaseEval:
    """答える問い: R の出力(JSON)を読んで評価できるか(無ければ止まる)。"""
    path = out_dir / f"{target.case_id}.json"
    if not path.exists():
        raise DiagnosisError(f"R の出力が無い: {path}")
    return evaluate_case(target, fit, json.loads(path.read_text(encoding="ascii")), spec, alpha)


def case_summary(case: CaseEval) -> dict[str, Any]:
    """答える問い: 反復 1 つの要約(JSON に残す。最適化ごとの全記録は work_dir の R の出力にある)。"""
    diag = case.detail["diag"]
    return {
        "case_id": case.target.case_id, "role": case.target.role, "sheet": case.target.sheet_id,
        "tau": case.target.key.sigma, "rep": case.target.rep, "fit_failed": case.fit_failed,
        "p_value_in_fit_json": case.p_json, "p": dict(case.p), "in_row": dict(case.in_row),
        "floor_size": dict(case.floor_size) if case.floor_size else None,
        "rescue_1a": {k: v for k, v in case.detail["rescue_1a"].items() if k != "p"},
        "rescue_1b": {k: v for k, v in case.detail["rescue_1b"].items() if k != "p"},
        "sd_new_term": {name: diag[name]["sd_new_term"] for name in FLOOR_MODELS},
        "refit_n_msgs_all": {name: diag[name]["refit_n_msgs_all"] for name in FLOOR_MODELS},
        "refit_n_msgs_nonsingular": {name: diag[name]["refit_n_msgs_nonsingular"] for name in FLOOR_MODELS},
        "moved": {name: diag[name]["moved"] for name in FLOOR_MODELS if diag[name]["moved"]},
    }


def aggregate(
    spec: DiagnosisSpec, run_config: Mapping[str, Any], gate: LegacyGateSpec,
    targets: Sequence[Target], fits_by_point: Mapping[tuple[str, float], Sequence[Mapping[str, Any]]],
    out_dir: Path,
) -> dict[str, Any]:
    """§2.2 のすべての行を数える。答える問い: 門の 4 点を失敗の数え直しで開けられるか(記述を含む)。

    **数え直しは記述であり、門の判定を置き換えない**(§2.2)。「支える」= 4 点すべてで CP95 下端 ≤ 閾値。
    """
    alpha = float(require(run_config, "simulation.alpha"))
    cases = [
        load_case_eval(t, fits_by_point[(t.sheet_id, t.key.sigma)][t.rep], out_dir, spec, alpha) for t in targets
    ]
    failures = [c for c in cases if c.target.role == ROLE_FAILURE]
    controls = [c for c in cases if c.target.role == ROLE_CONTROL]
    gate_points = [
        (sid, tau) for sid in gate.sheet_ids for tau in gate.tau
    ]
    points = []
    for sid, tau in gate_points:
        fits = fits_by_point[(sid, tau)]
        points.append(PointData(
            sheet_id=sid, tau=tau, n_rep=len(fits),
            ok_reject=sum(1 for f in fits if not f["fit_failed"] and f["p_value"] < alpha),
            failures=tuple(c for c in failures if (c.target.sheet_id, c.target.key.sigma) == (sid, tau)),
        ))
    level, bound = gate.ci_level, gate.lower_bound_above
    rows = {r: evaluate_row(r, points, alpha, level, bound)
            for r in (ROW_1A, ROW_1B, ROW_3_4, ROW_3_4_FIT0, ROW_2, ROW_R, ROW_U)}
    for r in JUDGEMENT_ROWS:
        rows[r]["supports"] = rows[r]["opens_at_all_points"]
    rows[ROW_3_4]["row_number"] = 3 if rows[ROW_3_4]["opens_at_all_points"] else 4
    gate_failures = [c for p in points for c in p.failures]
    failed_only = {
        label: {
            "by_point": [
                {"sheet": p.sheet_id, "tau": p.tau, **failed_only_rate([c.p[key] for c in p.failures], alpha, level)}
                for p in points
            ],
            "total_over_4_points": failed_only_rate([c.p[key] for c in gate_failures], alpha, level),
        }
        for label, key in (("after_refit", P_FINAL), ("fit0_sensitivity", P_FIT0))
    }
    size_counts = {
        "all_failures": count_sizes(failures, spec), "gate_points_failures": count_sizes(gate_failures, spec),
    }
    versions = {(c.detail["diag"]["r_version"], c.detail["diag"]["lme4_version"]) for c in cases}
    return {
        "meta": {
            "purpose": "PLAN-042 D0-D4. Counting only; the rule (ADR-059 / ADR-124 D2') is unchanged and no gate is re-judged.",
            "source_run": json.loads((spec.run_dir / "run_info.json").read_text(encoding="utf-8")),
            "alpha": alpha, "ci_level": level, "gate_lower_bound_above": bound,
            "r_lme4_versions": sorted(versions),
            "allfit_start_from_mle": spec.allfit_start_from_mle,
            "thresholds": {
                "align_loglik_tolerance": spec.align_loglik_tolerance,
                "align_fixef_tolerance_se": spec.align_fixef_tolerance_se,
                "min_aligned": spec.min_aligned,
                "trivial_loglik_gain_below": spec.trivial_loglik_gain_below,
                "trivial_shift_se_below": spec.trivial_shift_se_below,
                "large_shift_se_above": spec.large_shift_se_above,
                "separation_share": f"{spec.separation_numerator}/{spec.separation_denominator}",
                "boundary_sd_below": spec.boundary_sd_below,
            },
            "n_cases": {"failures": len(failures), "controls": len(controls),
                        "failures_at_gate_points": len(gate_failures)},
        },
        "d0": d0_summary(cases),
        "gate_points": [{"sheet": p.sheet_id, "tau": p.tau, "n_rep": p.n_rep, "n_failed": len(p.failures),
                         "successful_reps_rejected": p.ok_reject} for p in points],
        "judgement_rows": {r: rows[r] for r in (ROW_1A, ROW_1B, ROW_3_4)},
        "sensitivity_rows": {ROW_3_4_FIT0: rows[ROW_3_4_FIT0]},
        "descriptive_rows": {r: rows[r] for r in DESCRIPTIVE_ROWS},
        "row_5_separation": row_5(failures, spec),
        "failed_only_rejection": failed_only,
        "floor_failure_size": size_counts,
        "d4_new_term_sd": {
            "failures_all": new_term_summary(failures, spec.boundary_sd_below),
            "failures_at_gate_points": new_term_summary(gate_failures, spec.boundary_sd_below),
            "controls": new_term_summary(controls, spec.boundary_sd_below),
        },
        "cases": [case_summary(c) for c in cases],
    }


def count_sizes(cases: Sequence[CaseEval], spec: DiagnosisSpec) -> dict[str, int]:
    """答える問い: 床の失敗の大きさの分布(§0 の 74 / 37 の記述の区切り。行 2 の大きさの条件と同じ)。"""
    sized = [c.floor_size for c in cases if c.floor_size]
    return {
        "n": len(sized),
        "trivial": sum(1 for s in sized if s["loglik_gain"] < spec.trivial_loglik_gain_below
                       and s["max_shift"] < spec.trivial_shift_se_below),
        "large_shift": sum(1 for s in sized if s["max_shift"] > spec.large_shift_se_above),
    }


# --------------------------------------------------------------------------
# 起動
# --------------------------------------------------------------------------


def write_json_lf(path: Path, payload: Any) -> None:
    """答える問い: 結果を LF の JSON で書けるか(Windows の text 書きで CRLF にならない)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--select-only", action="store_true",
                        help="対象の選択と既知の件数の確認だけ。R を呼ばない・表を作らない")
    parser.add_argument("--aggregate-only", action="store_true",
                        help="R を呼ばず、work_dir/r_out の出力から集計だけやり直す")
    parser.add_argument("--keep-frames", action="store_true", help="作り直した CSV を消さずに残す")
    parser.add_argument("--workers", type=int, help="config の n_workers を上書きする")
    parser.add_argument("--rscript", help="Rscript の実体(省略時は run2 の config / PATH から探す)")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    spec = load_spec(load_config(args.config), repo_root)
    if args.workers:
        spec = replace(spec, n_workers=args.workers)
    run_config = json.loads((spec.run_dir / "config_resolved.json").read_text(encoding="utf-8"))
    sheets = ps.load_sheets(run_config)
    gate = load_legacy_gate_spec(run_config)
    targets, fits_by_point = select_targets(spec, sheets, gate)
    n_failure = sum(1 for t in targets if t.role == ROLE_FAILURE)
    print(f"targets: failures {n_failure} / controls {len(targets) - n_failure} (known counts match)")
    if args.select_only:
        return 0
    out_dir = spec.work_dir / "r_out"
    if not args.aggregate_only:
        rscript = ps.resolve_rscript(args.rscript or run_config["fit"].get("rscript"))
        out_dir = run_fits(spec, run_config, sheets, targets, fits_by_point, rscript, args.keep_frames)
    result = aggregate(spec, run_config, gate, targets, fits_by_point, out_dir)
    write_json_lf(spec.out_json, result)
    print(f"wrote {spec.out_json}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
