"""run2 の 1 段目(反復 100)の誤指定シートを、06:00 に止められた時点の fit から読む(探索。門の判定は変えない)。

答える問い: run 20261005_120003_power_sim_t1t2(out-dir results/power_sim/run2・git 68f9ecf)の誤指定 3 枚で、
(1) ADR-124 D2' の規則(当てはめ失敗 = 棄却)での門の判定はどうなるか(`power_sim.py` の関数そのまま)、
(2) 当てはめ失敗を非棄却に数えた場合・成功した反復だけの場合の棄却率と 95% Clopper-Pearson 区間はいくつか、
(3) 当てはめ失敗は床でどれほどの大きさ(logLik の改善・固定効果の移動)だったか。

**事後の探索的な分解である。**門の判定の正本は、段を回し終えた後の `power_sim_summary.json` である
(06:00 に止められたので、この時点では書かれていない)。(2)(3) は規則の代わりではない(PLAN-041 §3.3 罠2)。
入力は `../*/fits/*.json`(.gitignore 済み。この機械にだけある)。`misspecification_seed_per_cell` は途中(記録だけ)。

実行: python -X utf8 results/power_sim/run2/exploratory/stage1_interim.py
出力: 同じディレクトリの stage1_interim.json
"""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent
REPO = RUN_DIR.parents[2]
sys.path.insert(0, str(REPO))
from code.analysis import power_sim as ps  # noqa: E402

SHEET_IDS = [
    "misspecification",
    "misspecification_seed_subspace",
    "misspecification_seed_per_cell",
]
# 床の失敗の大きさの区切り(記述のためだけ。ADR-059 の許容 0.001 / 0.01 SE とは別物)
TRIVIAL_LOGLIK_GAIN = 0.01
TRIVIAL_BETA_SHIFT = 0.1
LARGE_BETA_SHIFT = 10.0


def cp_interval(k: int, n: int, level: float) -> list[float]:
    """答える問い: k / n の両側 `level` の Clopper-Pearson 区間はいくつか。"""
    from scipy.stats import beta
    a = (1.0 - level) / 2.0
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1.0 - a, k + 1, n - k))
    return [lo, hi]


def floor_failure_size(result: dict) -> dict:
    """答える問い: 床の段で失敗した当てはめの logLik の改善と係数の移動(SE 単位)の最大はいくつか。"""
    top = max(level["level"] for level in result["levels"])
    failed = [lv for lv in result["levels"] if lv["level"] == top and lv["failed"]]
    gain = max(lv["loglik_gain"] for lv in failed)
    shift = max(lv["max_shift"] for lv in failed)
    return {"loglik_gain": gain, "max_shift": shift,
            "all_refits_silent": all(lv["n_warnings"] == 0 for lv in failed)}


def read_point(sheet_dir: Path, key: ps.PointKey) -> tuple[list[dict], str]:
    files = sorted((sheet_dir / "fits").glob(f"fit_{key.tag()}_*.json"))
    digest = hashlib.sha256()
    results = []
    for path in files:
        raw = path.read_bytes()
        digest.update(raw)
        results.append(json.loads(raw.decode("ascii")))
    return results, digest.hexdigest()


def main() -> None:
    config = json.loads((RUN_DIR / "config_resolved.json").read_text(encoding="utf-8"))
    sheets = {s.sheet_id: s for s in ps.load_sheets(config)}
    gate = ps.load_gate_spec(config)
    alpha = float(config["simulation"]["alpha"])

    run_id = json.loads((RUN_DIR / "run_info.json").read_text(encoding="utf-8"))["run_id"]
    out: dict = {"run_id": run_id, "run_dir": "results/power_sim/run2",
                 "git_sha": (RUN_DIR / "git_sha.txt").read_text(encoding="utf-8").split()[0],
                 "alpha": alpha, "ci_level": gate.ci_level, "sheets": {}}
    points_by_sheet: dict[str, list[ps.GridPoint]] = {}
    severity = Counter()
    for sid in SHEET_IDS:
        sheet = sheets[sid]
        profile = ps.build_profile(config["effect"], sheet.profile)
        tost = ps.tost_spec(config, profile)
        rows = []
        points = []
        for key in sheet.points:
            results, digest = read_point(RUN_DIR / sid, key)
            if not results:
                rows.append({"sigma": key.sigma, "n_rep": 0, "status": "not_started"})
                continue
            point = ps.summarise_point(key, results, alpha, tost, failure_as_reject=True)
            points.append(point)
            ok = [r for r in results if not r["fit_failed"]]
            fail = [r for r in results if r["fit_failed"]]
            k_ok = sum(1 for r in ok if r["p_value"] < alpha)
            sizes = [floor_failure_size(r) for r in fail]
            if sid in gate.sheet_ids:
                for s in sizes:
                    severity["n"] += 1
                    if s["loglik_gain"] < TRIVIAL_LOGLIK_GAIN and s["max_shift"] < TRIVIAL_BETA_SHIFT:
                        severity["trivial"] += 1
                    if s["max_shift"] > LARGE_BETA_SHIFT:
                        severity["large_shift"] += 1
                    if s["all_refits_silent"]:
                        severity["refit_silent"] += 1
            rows.append({
                "sigma_eq_tau": key.sigma,
                "n_item": key.n_item,
                "n_rep": len(results),
                "fits_sha256": digest,
                "n_failed": len(fail),
                "n_errored_any": sum(1 for r in results if r["n_errored_fits"] > 0),
                "rule_failed_as_reject": {
                    "n_reject": point.n_reject, "rate": point.power,
                    "ci": cp_interval(point.n_reject, point.n_rep, gate.ci_level)},
                "failed_as_retain": {
                    "n_reject": k_ok, "rate": k_ok / len(results),
                    "ci": cp_interval(k_ok, len(results), gate.ci_level)},
                "successful_only": {
                    "n_reject": k_ok, "n": len(ok), "rate": (k_ok / len(ok)) if ok else None,
                    "ci": cp_interval(k_ok, len(ok), gate.ci_level) if ok else None},
                "reduction_label": dict(Counter(r["reduction_label"] for r in results)),
                "reduction_label_of_failed": dict(Counter(r["reduction_label"] for r in fail)),
                "reduced_rate": point.reduced_rate,
                "singular_rate": point.singular_rate,
                "refit_rate": point.refit_rate,
                "mean_chisq_successful": point.mean_chisq,
            })
        out["sheets"][sid] = {"profile": sheet.profile,
                              "seed_interaction": None if sheet.seed_interaction is None
                              else {"direction": sheet.seed_interaction.direction_profile,
                                    "scale": sheet.seed_interaction.scale},
                              "gate_sheet": sid in gate.sheet_ids,
                              "points": rows}
        points_by_sheet[sid] = points
    out["gate_under_rule"] = ps.misspecification_gate(
        {i: points_by_sheet[i] for i in gate.sheet_ids}, gate)
    out["floor_failure_size_gate_sheets"] = {
        "thresholds": {"trivial_loglik_gain_below": TRIVIAL_LOGLIK_GAIN,
                       "trivial_max_shift_below": TRIVIAL_BETA_SHIFT,
                       "large_max_shift_above": LARGE_BETA_SHIFT},
        **dict(severity)}
    with open(HERE / "stage1_interim.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
