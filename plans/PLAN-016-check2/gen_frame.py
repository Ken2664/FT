"""PLAN-016 check 2, part 1: build the long-form table that section 3.2 wants.

This is NOT pipeline code. It writes a synthetic CSV for the R6 timing check
(plans/PLAN-016-check2/fit_timing.R). No real data is touched (PLAN-016 section 8).

The generative design is the same one check 1 used
(plans/PLAN-016-check1/check1_statsmodels_r3.py: make_frame), so the two checks
are talking about the same table. Only the SIZE is swept here:
  - n_seed                 how many FT runs
  - n_item_per_coverage    how many operand pairs per coverage class

`item` is crossed with `task` and `seed`: the same operand pair is asked in all
four task forms and under every seed. `coverage` is a property of the item.

Output is ASCII only: this environment's stdout is cp932.
"""

import argparse
import zlib

import numpy as np
import pandas as pd

TASKS = ["T1", "T1b", "T2", "T3"]
COVERAGES = ["id", "interp", "extrap_magnitude"]
T2_TEMPLATES = ["t2_count", "t2_people", "t2_distance", "t2_money", "t2_time"]

SD_SEED = 0.6
SD_ITEM = 0.5
SD_TEMPLATE = 0.4

B_TASK = {"T1": 0.0, "T1b": -0.3, "T2": -0.9, "T3": -0.5}
B_COV = {"id": 0.0, "interp": -0.8, "extrap_magnitude": -1.6}
B_INT = {
    ("T1", "interp"): 0.0, ("T1", "extrap_magnitude"): 0.0,
    ("T1b", "interp"): -0.2, ("T1b", "extrap_magnitude"): -0.4,
    ("T2", "interp"): -0.6, ("T2", "extrap_magnitude"): -1.2,
    ("T3", "interp"): -0.4, ("T3", "extrap_magnitude"): -0.9,
}
INTERCEPT = 1.0


def template_of(task, item_name):
    """Which template does this (task, item) pair use?

    crc32, not hash(): str.__hash__ is salted per process, so hash() would make
    the assignment differ between runs (the bug check 1 hit on 2026-09-07).
    """
    if task == "T2":
        return T2_TEMPLATES[zlib.crc32(item_name.encode("utf-8")) % len(T2_TEMPLATES)]
    return "tpl_%s" % task


def make_frame(rng, n_seed, n_item_per_coverage, interaction_scale):
    """Build the long-form table. interaction_scale=0.0 gives the additive truth."""
    items = [
        {"item": "%s_%03d" % (cov, k), "coverage": cov}
        for cov in COVERAGES
        for k in range(n_item_per_coverage)
    ]

    u_seed = {s: rng.normal(0.0, SD_SEED) for s in range(n_seed)}
    u_item = {it["item"]: rng.normal(0.0, SD_ITEM) for it in items}
    templates = sorted({template_of(t, it["item"]) for t in TASKS for it in items})
    u_tpl = {t: rng.normal(0.0, SD_TEMPLATE) for t in templates}

    rows = []
    for s in range(n_seed):
        for task in TASKS:
            for it in items:
                cov = it["coverage"]
                tpl = template_of(task, it["item"])
                eta = (
                    INTERCEPT
                    + B_TASK[task]
                    + B_COV[cov]
                    + interaction_scale * B_INT.get((task, cov), 0.0)
                    + u_seed[s]
                    + u_item[it["item"]]
                    + u_tpl[tpl]
                )
                p = 1.0 / (1.0 + np.exp(-eta))
                rows.append(
                    {
                        "is_rule": int(rng.random() < p),
                        "task": task,
                        "coverage": cov,
                        "seed": "s%02d" % s,
                        "item": it["item"],
                        "template": tpl,
                    }
                )
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-seed", type=int, default=10)
    ap.add_argument("--n-item-per-coverage", type=int, default=24)
    ap.add_argument("--interaction-scale", type=float, default=0.0)
    ap.add_argument("--rng-seed", type=int, default=20260907)
    args = ap.parse_args()

    rng = np.random.default_rng(args.rng_seed)
    df = make_frame(rng, args.n_seed, args.n_item_per_coverage, args.interaction_scale)
    df.to_csv(args.out, index=False)
    print("rows=%d n_seed=%d n_item=%d n_template=%d mean_is_rule=%.3f" % (
        len(df), df["seed"].nunique(), df["item"].nunique(),
        df["template"].nunique(), df["is_rule"].mean(),
    ))


if __name__ == "__main__":
    main()
