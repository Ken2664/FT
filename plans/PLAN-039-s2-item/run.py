"""PLAN-039 §4.1(ADR-120): `s2_item` をパイロット FT の `p2` 2 シードから推定する駆動。

答える問い: 「パイロットの実測から見積もると、同じセルの中の項目の当たりやすさの分散
(ロジット尺度)はどのくらいか」。**判断材料であって値の決定ではない**(値は人間)。

使い方(repo の根で): python plans/PLAN-039-s2-item/run.py --rscript <Rscript> --out-dir results/s2_item_pilot
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
from code.analysis.frame import build_frame  # noqa: E402

# ADR-120 決定1: 625 が主、313 は並べるだけ
RUNS = {
    "625": ["pilot_ft_eval_p2_s0", "pilot_ft_eval_p2_s1"],
    "313": ["pilot_ft_eval_p2_s0_n313", "pilot_ft_eval_p2_s1_n313"],
}
MAIN_STEP = "625"
MAIN_MODEL = "main"
GROUPS = ("bare_sum", "word_problem")
FIT_COVERAGE = "extrap_magnitude"  # ADR-120 決定2
FRAME_COLUMNS = ("step", "task", "coverage", "seed", "item", "template", "is_rule")
AGREE_KEYS = ("s0=1,s1=1", "s0=1,s1=0", "s0=0,s1=1", "s0=0,s1=0")


def frame_rows() -> list[dict]:
    """4 run の主軸の行(T1・T2)を、step の印を付けて返す。"""
    rows = []
    for step, runs in RUNS.items():
        frame = build_frame([Path("runs") / r / "metrics.json" for r in runs])
        for row in frame.rows:
            if row["group"] in GROUPS and row["main_axis"]:
                rows.append({"step": step, **{k: row[k] for k in FRAME_COLUMNS[1:]}})
    return rows


def cell_table(rows: list[dict]) -> list[dict]:
    """セルごとの規則率とシード 0 × シード 1 の 2×2 の一致表(ADR-120 決定3)。"""
    by_item: dict[tuple, dict[int, int]] = collections.defaultdict(dict)
    for r in rows:
        by_item[(r["step"], r["task"], r["coverage"], r["item"])][r["seed"]] = r["is_rule"]
    agree: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    for (step, task, cov, item), seeds in by_item.items():
        if set(seeds) != {0, 1}:
            raise ValueError(f"項目に 2 シードがそろっていない: {step} {task} {cov} {item}")
        agree[(step, task, cov)][f"s0={seeds[0]},s1={seeds[1]}"] += 1
    out = []
    for (step, task, cov), a in sorted(agree.items()):
        n = sum(a.values())
        rate0 = (a["s0=1,s1=1"] + a["s0=1,s1=0"]) / n
        rate1 = (a["s0=1,s1=1"] + a["s0=0,s1=1"]) / n
        out.append({
            "step": step, "task": task, "coverage": cov, "n_item": n,
            "rule_rate_s0": rate0, "rule_rate_s1": rate1,
            "agree_2x2": {k: a.get(k, 0) for k in AGREE_KEYS},
            "used_in_fit": cov == FIT_COVERAGE,
            "separated_within_seed": rate0 in (0.0, 1.0) or rate1 in (0.0, 1.0),
        })
    return out


def read_fits(path: Path) -> list[dict]:
    """R の出した表を読む。NA は None に。"""
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for r in rows:
        for k in ("var_item", "var_tmpl", "ci_lo_var_item", "ci_hi_var_item"):
            r[k] = None if r[k] in ("NA", "") else float(r[k])
        r["singular"] = r["singular"] == "TRUE"
        r["n_obs"] = int(r["n_obs"])
        r["n_item"] = int(r["n_item"])
    return rows


def recommendation(fits: list[dict]) -> dict:
    """ADR-120 決定4: 主推定の profile 95% 上端。立たなければ推奨は出さない。"""
    main = [f for f in fits if f["step"] == MAIN_STEP and f["model"] == MAIN_MODEL]
    if len(main) != 1:
        raise ValueError("主推定の行が 1 つでない")
    m = main[0]
    ok = m["profile_status"] == "ok" and m["ci_hi_var_item"] is not None
    return {
        "rule": "ADR-120 決定4: 主推定(625・main)の項目の分散の profile 95% 区間の上端。立たなければ出さない",
        "value": m["ci_hi_var_item"] if ok else None,
        "issued": ok,
        "reason_if_not": None if ok else m["profile_status"],
        "note": "推奨であって決定ではない。値を決めるのは人間(ADR-119 決定3)",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rscript", required=True)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_s2_item_pilot"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = frame_rows()
    frame_csv = args.out_dir / "frame.csv"
    with frame_csv.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=FRAME_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    fits_csv = args.out_dir / "fits.csv"
    fit_r = Path(__file__).with_name("fit.R")
    subprocess.run([args.rscript, str(fit_r), str(frame_csv), str(fits_csv)], check=True)
    fits = read_fits(fits_csv)
    summary = {
        "run_id": run_id,
        "source_runs": RUNS,
        "decisions": "ADR-120(plans/PLAN-039-s2-item-from-pilot.md §4.1)",
        "pool_id": "pilot(主張に使わない。ADR-106)",
        "cells": cell_table(rows),
        "fits": fits,
        "recommendation": recommendation(fits),
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    (args.out_dir / "summary.json").write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": run_id, "fits": fits, "recommendation": summary["recommendation"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
