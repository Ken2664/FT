"""PLAN-016 check 2, part 3: aggregate the timing JSONs into the numbers PLAN-016 quotes.

Reads every plans/PLAN-016-check2/timing_*.json and prints one ASCII line per
table size: mean / SD / range of the wall clock for the (full + add) pair, plus
how many fits carried an lme4 convergence or singularity message (R5).

Tolerant parser: the JSONs written before 2026-09-07 12:5x contain a RAW newline
inside the conv_msgs strings (lme4's own message is two lines), which is not
legal JSON. fit_timing.R now collapses those, but the older files stay readable.
Output is ASCII only: this environment's stdout is cp932.
"""

import glob
import os
import re
import statistics

FIELD = re.compile(r'"(\w+)":\s*("[^"]*"|-?[\d.]+(?:[eE][-+]?\d+)?)', re.S)


def load(path):
    text = open(path, encoding="utf-8").read()
    out = {}
    for key, raw in FIELD.findall(text):
        if raw.startswith('"'):
            out[key] = " ".join(raw[1:-1].split())
        else:
            out[key] = float(raw)
    return out


def has_warning(rec):
    """Did lme4 complain, regardless of what optinfo$conv$opt said? (R5)"""
    return bool(rec.get("conv_msgs_full") or rec.get("conv_msgs_add"))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    recs = [load(p) for p in sorted(glob.glob(os.path.join(here, "timing_*.json")))]
    if not recs:
        print("no timing_*.json found")
        return

    by_size = {}
    for r in recs:
        by_size.setdefault(int(r["n_rows"]), []).append(r)

    print("%-8s %-7s %-3s %8s %8s %8s %8s %8s  %s" % (
        "rows", "items", "n", "mean_s", "sd_s", "min_s", "max_s", "mean_full", "lme4_warned"))
    for rows in sorted(by_size):
        g = by_size[rows]
        tot = [r["secs_total"] for r in g]
        full = [r["secs_fit_full"] for r in g]
        sd = statistics.stdev(tot) if len(tot) > 1 else 0.0
        print("%-8d %-7d %-3d %8.2f %8.2f %8.2f %8.2f %8.2f  %d/%d" % (
            rows, int(g[0]["n_item"]), len(g),
            statistics.mean(tot), sd, min(tot), max(tot), statistics.mean(full),
            sum(has_warning(r) for r in g), len(g)))

    # R5: optinfo$conv$opt says 0 (success) even when lme4 itself warns.
    n_opt_ok = sum(1 for r in recs if r.get("conv_code_full") == 0
                   and r.get("conv_code_add") == 0)
    n_warned = sum(has_warning(r) for r in recs)
    n_singular = sum(1 for r in recs if "singular" in (
        str(r.get("conv_msgs_full", "")) + str(r.get("conv_msgs_add", ""))))
    print()
    print("R5: fits=%d  conv_code==0 (both models)=%d  lme4 warned=%d  singular=%d"
          % (len(recs), n_opt_ok, n_warned, n_singular))

    # the LRT is on additive-truth data throughout, so chisq should sit near df=6
    chis = [r["chisq"] for r in recs]
    print("LRT on additive truth: n=%d mean_chisq=%.2f (df=6) min=%.2f max=%.2f negative=%d"
          % (len(chis), statistics.mean(chis), min(chis), max(chis),
             sum(1 for c in chis if c < 0)))


if __name__ == "__main__":
    main()
