"""誤指定シートの棄却を、縮退カスケードの段ごとに分けて数える(探索。門の判定には使わない)。

答える問い: run 20261004_120002_power_sim_t1t2 の誤指定シート(P0・`n_item` 80・100 反復 x `tau` 6 点)で、
主要検定の棄却は縮退のどの段(none / drop_template / drop_coverage_slope / drop_item)で起きているか。
`drop_item` で終わった当てはめを除くと、`tau` 0.25・0.5 の棄却率の 95% Clopper-Pearson 区間はどうなるか。

**事後の探索的な分解である。**ADR-123 決定6 の門の判定(`power_sim_summary.json`)は変えない。
入力は `../misspecification/fits/*.json`(.gitignore 済み。この機械にだけある)。

実行: python -X utf8 results/power_sim/run1/exploratory/by_reduction.py
出力: 同じディレクトリの by_reduction.json
"""

import collections
import glob
import hashlib
import json
import os
import re
import statistics

from scipy.stats import binomtest

RUN_ID = "20261004_120002_power_sim_t1t2"
ALPHA = 0.05  # 主要検定の名目 α(configs/power_sim.yaml の alpha と同じ)
CI_LEVEL = 0.95  # 門と同じ Clopper-Pearson の水準(ADR-123 決定6)
NULL_MEAN_CHISQ = 2.0  # df = 2 の χ² の平均(帰無仮説の下)
LEVEL_ORDER = ["none", "drop_template", "drop_coverage_slope", "drop_item"]
EXCLUDED_LEVEL = "drop_item"

HERE = os.path.dirname(os.path.abspath(__file__))
FITS_GLOB = os.path.join(HERE, "..", "misspecification", "fits", "fit_*.json")
OUT_PATH = os.path.join(HERE, "by_reduction.json")


def tau_of(path):
    """答える問い: ファイル名 `fit_n80_s0p25_r0_0000.json` の `tau`(= sigma)はいくつか。"""
    token = re.search(r"_s([0-9p]+)_r", os.path.basename(path)).group(1)
    return float(token.replace("p", "."))


def rate_block(fits):
    """答える問い: この当てはめの集まりの棄却数・率・CI・χ² の平均と中央値は何か。"""
    n = len(fits)
    k = sum(f["p_value"] < ALPHA for f in fits)
    chisq = [f["chisq"] for f in fits]
    ci = binomtest(k, n).proportion_ci(CI_LEVEL, method="exact") if n else None
    return {
        "n": n,
        "n_reject": k,
        "rejection_rate": k / n if n else None,
        "ci_lower": ci.low if ci else None,
        "ci_upper": ci.high if ci else None,
        "mean_chisq": statistics.mean(chisq) if n else None,
        "median_chisq": statistics.median(chisq) if n else None,
    }


def load_fits():
    """答える問い: `tau` ごとの当てはめの記録と、読んだファイルの指紋は何か。"""
    paths = sorted(glob.glob(FITS_GLOB))
    if not paths:
        raise SystemExit(f"当てはめの記録が無い: {FITS_GLOB}")
    by_tau = collections.defaultdict(list)
    digest = hashlib.sha256()
    for p in paths:
        with open(p, "rb") as fh:
            raw = fh.read()
        digest.update(os.path.basename(p).encode() + b"\0" + raw)
        rec = json.loads(raw)
        if rec["p_value"] is None:
            raise SystemExit(f"p 値が null の当てはめがある: {p}")
        by_tau[tau_of(p)].append(rec)
    return by_tau, len(paths), digest.hexdigest()


def main():
    by_tau, n_files, sha = load_fits()
    rows = []
    for tau in sorted(by_tau):
        fits = by_tau[tau]
        overall = rate_block(fits)
        rows.append({
            "tau": tau,
            "all": overall,
            "by_reduction": {
                lab: rate_block([f for f in fits if f["reduction_label"] == lab])
                for lab in LEVEL_ORDER
            },
            "excluding_" + EXCLUDED_LEVEL: rate_block(
                [f for f in fits if f["reduction_label"] != EXCLUDED_LEVEL]),
            "n_full_singular": sum(bool(f["full_singular"]) for f in fits),
            # 探索の目安: χ² の平均が帰無の何倍か(-1)を tau² で割った値。tau = 0 は定義しない
            "chisq_inflation_per_tau2": (
                (overall["mean_chisq"] / NULL_MEAN_CHISQ - 1) / tau ** 2 if tau > 0 else None),
        })
    out = {
        "run_id": RUN_ID,
        "sheet": "misspecification",
        "note": ("exploratory post-hoc breakdown; does NOT change the ADR-123 decision-6 gate "
                 "(power_sim_summary.json: stopped_at_gate = true)"),
        "alpha": ALPHA,
        "ci_level": CI_LEVEL,
        "ci_method": "clopper-pearson",
        "n_fit_files": n_files,
        "fits_sha256": sha,
        "rows": rows,
    }
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    for r in rows:
        ex = r["excluding_" + EXCLUDED_LEVEL]
        print(f"tau={r['tau']}: all {r['all']['n_reject']}/{r['all']['n']} | "
              f"excl {EXCLUDED_LEVEL} {ex['n_reject']}/{ex['n']} (lower {ex['ci_lower']:.3f}) | "
              + " ".join(f"{lab}={b['n_reject']}/{b['n']}" for lab, b in r["by_reduction"].items()))


if __name__ == "__main__":
    main()
