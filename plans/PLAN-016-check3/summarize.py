"""PLAN-016 check 3, part 3: turn the refit JSONs into the four numbers the
handoff asks for, plus the threshold evidence ADR-059 left open.

  (i)   how often a restart clears lme4's warning
  (ii)  the distribution of the logLik improvement on restart
  (iii) how far the fixed effects move on restart
  (iv)  the extra wall clock the restart costs

Reads plans/PLAN-016-check3/refit_*.json, prints an ASCII table, and writes
summary_check3.json. The durable record of these numbers is
plans/PLAN-016-fitting-engine.md section 2 (F57 and later), not this output:
the JSONs are gitignored, the same way check 1 and check 2 were kept.

Two conventions matter for reading the output.

  - A "warned" fit is one where lme4 put at least one message in
    optinfo$conv$lme4$messages. Singularity is read from isSingular(), never
    from the message text (F56).
  - Movement of a fixed effect is reported in SE units as well as raw. The raw
    scale is not comparable across coefficients; ADR-059's "does not move
    substantially" needs a scale-free number to be a rule rather than a guess.

Output is ASCII only: this environment's stdout is cp932.
"""

import glob
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))

# Candidate thresholds for ADR-059's "does not improve / does not move".
LL_GRID = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1]
SE_GRID = [1e-4, 1e-3, 1e-2, 5e-2, 1e-1]

MODELS = ("full", "add")


def pct(x, q):
    """Percentile by linear interpolation; q in [0, 100]. No numpy dependency."""
    if not x:
        return float("nan")
    s = sorted(x)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def describe(vals):
    """Summary stats, dropping the entries R could not compute (JSON null).

    lme4 does not always leave a usable optinfo$derivs behind -- a refit that
    lands on the boundary can come back with no gradient at all -- so a None
    here means "not measurable", not "zero". n_missing keeps that visible.
    """
    missing = sum(1 for v in vals if v is None)
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "n_missing": missing}
    return {
        "n": len(vals),
        "min": min(vals),
        "p25": pct(vals, 25),
        "median": pct(vals, 50),
        "p75": pct(vals, 75),
        "max": max(vals),
        "mean": statistics.fmean(vals),
        "n_missing": missing,
    }


def line(tag, d):
    miss = d.get("n_missing") or 0
    if not d.get("n"):
        return "%-22s n=0 (n_missing=%d)" % (tag, miss)
    return ("%-22s n=%-3d min=%-12.6g p25=%-12.6g med=%-12.6g "
            "p75=%-12.6g max=%-12.6g%s" % (
                tag, d["n"], d["min"], d["p25"], d["median"], d["p75"], d["max"],
                "" if not miss else "  n_missing=%d" % miss))


def load_fits(recs):
    """Flatten the per-frame records into one row per FIT (2 per frame)."""
    fits = []
    for r in recs:
        label = r["csv"].split("_")[1]
        for m in MODELS:
            b0, b1 = r["%s_fit0_fixef" % m], r["%s_refit_fixef" % m]
            se = r["%s_fit0_se" % m]
            t0, t1 = r["%s_fit0_theta" % m], r["%s_refit_theta" % m]
            d_abs = [abs(a - b) for a, b in zip(b1, b0)]
            d_se = [abs(a - b) / s if s > 0 else float("inf")
                    for a, b, s in zip(b1, b0, se)]
            fits.append({
                "csv": r["csv"], "label": label, "model": m,
                "n_rows": int(r["n_rows"]),
                "warned": bool(r["%s_fit0_warned" % m]),
                "singular0": bool(r["%s_fit0_singular" % m]),
                "maxgrad0": bool(r["%s_fit0_has_maxgrad" % m]),
                "warned1": bool(r["%s_refit_warned" % m]),
                "singular1": bool(r["%s_refit_singular" % m]),
                "maxgrad1": bool(r["%s_refit_has_maxgrad" % m]),
                "d_ll": r["%s_refit_logLik" % m] - r["%s_fit0_logLik" % m],
                "d_beta_abs": max(d_abs),
                "d_beta_se": max(d_se),
                "d_theta": max(abs(a - b) for a, b in zip(t1, t0)),
                "relgrad0": r["%s_fit0_relgrad" % m],
                "relgrad1": r["%s_refit_relgrad" % m],
                "rawgrad0": r["%s_fit0_maxgrad_raw" % m],
                "rawgrad1": r["%s_refit_maxgrad_raw" % m],
                "secs0": r["%s_fit0_secs" % m],
                "secs1": r["%s_refit_secs" % m],
                "conv_opt0": r["%s_fit0_conv_opt" % m],
            })
    return fits


def fires(f, t_ll, t_se):
    """ADR-059 decision 1: did this fit fail the restart test?

    Only warned fits are restarted at all. Singularity on its own is not a
    trigger (decision 1), so a fit whose only message is the singular one is
    still put through the same movement test as any other warned fit -- what
    decides is whether the restart moved anything, not what the message said.
    """
    if not f["warned"]:
        return False
    return f["d_ll"] > t_ll or f["d_beta_se"] > t_se


def main():
    paths = sorted(glob.glob(os.path.join(HERE, "refit_*.json")))
    recs = [json.load(open(p, encoding="utf-8")) for p in paths]
    if not recs:
        print("no refit_*.json found")
        return
    fits = load_fits(recs)
    warned = [f for f in fits if f["warned"]]
    clean = [f for f in fits if not f["warned"]]
    out = {"n_frames": len(recs), "n_fits": len(fits), "n_warned_fit0": len(warned)}

    print("check 3: restart of a warned glmer fit (ADR-059 decision 1)")
    print("frames=%d  fits=%d  R=%s  lme4=%s" % (
        len(recs), len(fits), recs[0]["r_version"], recs[0]["lme4_version"]))
    print()

    # --- fit0: what fired at all, before any restart -------------------------
    n_opt = sum(1 for f in fits if f["conv_opt0"] != 0)
    n_sing = sum(1 for f in fits if f["singular0"])
    n_grad = sum(1 for f in fits if f["maxgrad0"])
    n_both = sum(1 for f in fits if f["singular0"] and f["maxgrad0"])
    print("fit0 signals: conv$opt!=0 %d/%d | warned %d/%d | isSingular %d/%d | "
          "max|grad| %d/%d | both %d" % (
              n_opt, len(fits), len(warned), len(fits), n_sing, len(fits),
              n_grad, len(fits), n_both))
    out["fit0"] = {"conv_opt_nonzero": n_opt, "warned": len(warned),
                   "singular": n_sing, "maxgrad": n_grad, "both": n_both,
                   "n_fits": len(fits)}

    # --- (i) does the restart clear the warning? -----------------------------
    print()
    print("(i) restart clears the warning")
    groups = [
        ("all warned fits", warned),
        ("  max|grad| only", [f for f in warned if f["maxgrad0"] and not f["singular0"]]),
        ("  singular only", [f for f in warned if f["singular0"] and not f["maxgrad0"]]),
        ("  both", [f for f in warned if f["singular0"] and f["maxgrad0"]]),
    ]
    out["i_clearing"] = {}
    for tag, g in groups:
        if not g:
            print("%-20s n=0" % tag)
            continue
        all_gone = sum(1 for f in g if not f["warned1"])
        grad_gone = sum(1 for f in g if not f["maxgrad1"])
        still_sing = sum(1 for f in g if f["singular1"])
        print("%-20s n=%-3d all msgs gone %d (%.0f%%) | max|grad| gone %d (%.0f%%) | "
              "singular after %d" % (
                  tag, len(g), all_gone, 100.0 * all_gone / len(g),
                  grad_gone, 100.0 * grad_gone / len(g), still_sing))
        out["i_clearing"][tag.strip()] = {
            "n": len(g), "all_msgs_gone": all_gone,
            "maxgrad_gone": grad_gone, "singular_after": still_sing}
    n_new = sum(1 for f in clean if f["warned1"])
    print("control: fit0 clean n=%d -> refit warned %d" % (len(clean), n_new))
    out["i_clearing"]["control_clean_fit0"] = {"n": len(clean), "refit_warned": n_new}

    # --- (i-b) is the gradient smaller, or did the check stop running? -------
    # lme4 scales the gradient by the Hessian. On a singular fit that solve can
    # fail, so a max|grad| warning that vanishes at the same time as the fit
    # goes singular is NOT evidence of convergence. Split on it.
    print()
    print("(i-b) why did max|grad| go away? (warned fit0 carrying a max|grad| message)")
    g = [f for f in fits if f["maxgrad0"]]
    sing_after = [f for f in g if f["singular1"]]
    ok_after = [f for f in g if not f["singular1"]]
    print("  refit singular    n=%-3d  max|grad| gone %d  (gradient check may not be comparable)"
          % (len(sing_after), sum(1 for f in sing_after if not f["maxgrad1"])))
    print("  refit NOT singular n=%-3d  max|grad| gone %d  <- the clean evidence"
          % (len(ok_after), sum(1 for f in ok_after if not f["maxgrad1"])))
    both = [f for f in g if f["relgrad0"] is not None and f["relgrad1"] is not None]
    print(line("  relgrad fit0", describe([f["relgrad0"] for f in both])))
    print(line("  relgrad refit", describe([f["relgrad1"] for f in both])))
    print("  relgrad computable at refit: %d/%d; smaller after restart: %d/%d"
          % (len(both), len(g), sum(1 for f in both if f["relgrad1"] < f["relgrad0"]), len(both)))
    print(line("  raw|grad| fit0", describe([f["rawgrad0"] for f in g])))
    print(line("  raw|grad| refit", describe([f["rawgrad1"] for f in g])))
    out["i_b_gradient"] = {
        "n_maxgrad_fit0": len(g),
        "refit_singular": {"n": len(sing_after),
                           "maxgrad_gone": sum(1 for f in sing_after if not f["maxgrad1"])},
        "refit_not_singular": {"n": len(ok_after),
                               "maxgrad_gone": sum(1 for f in ok_after if not f["maxgrad1"])},
        "relgrad_fit0": describe([f["relgrad0"] for f in both]),
        "relgrad_refit": describe([f["relgrad1"] for f in both]),
        "relgrad_computable_at_refit": len(both),
        "relgrad_smaller_after": sum(1 for f in both if f["relgrad1"] < f["relgrad0"]),
        "rawgrad_fit0": describe([f["rawgrad0"] for f in g]),
        "rawgrad_refit": describe([f["rawgrad1"] for f in g]),
    }

    # --- (ii) logLik improvement --------------------------------------------
    print()
    print("(ii) logLik(refit) - logLik(fit0)")
    d_w = [f["d_ll"] for f in warned]
    d_c = [f["d_ll"] for f in clean]
    print(line("warned fit0", describe(d_w)))
    print(line("clean fit0 (control)", describe(d_c)))
    print("negative (refit worse): warned %d/%d, clean %d/%d" % (
        sum(1 for v in d_w if v < 0), len(d_w),
        sum(1 for v in d_c if v < 0), len(d_c)))
    print("exceeds threshold t (count of warned fits with d_logLik > t):")
    for t in LL_GRID:
        print("    t=%-8g %d/%d" % (t, sum(1 for v in d_w if v > t), len(d_w)))
    out["ii_logLik"] = {"warned": describe(d_w), "clean": describe(d_c),
                        "warned_exceeding": {str(t): sum(1 for v in d_w if v > t)
                                             for t in LL_GRID}}

    # --- (iii) how far do the estimates move? --------------------------------
    print()
    print("(iii) movement of the fixed effects on restart")
    print(line("warned max|d_beta|", describe([f["d_beta_abs"] for f in warned])))
    print(line("warned max|d_beta|/SE", describe([f["d_beta_se"] for f in warned])))
    print(line("clean  max|d_beta|/SE", describe([f["d_beta_se"] for f in clean])))
    print(line("warned max|d_theta|", describe([f["d_theta"] for f in warned])))
    print("exceeds threshold t (count of warned fits with max|d_beta|/SE > t):")
    for t in SE_GRID:
        print("    t=%-8g %d/%d" % (
            t, sum(1 for f in warned if f["d_beta_se"] > t), len(warned)))
    out["iii_movement"] = {
        "warned_abs": describe([f["d_beta_abs"] for f in warned]),
        "warned_se": describe([f["d_beta_se"] for f in warned]),
        "clean_se": describe([f["d_beta_se"] for f in clean]),
        "warned_theta": describe([f["d_theta"] for f in warned]),
        "warned_exceeding_se": {str(t): sum(1 for f in warned if f["d_beta_se"] > t)
                                for t in SE_GRID},
    }

    # --- (iv) what does the restart cost? ------------------------------------
    print()
    print("(iv) wall clock")
    s0 = sum(f["secs0"] for f in fits)
    s1_all = sum(f["secs1"] for f in fits)
    s1_pol = sum(f["secs1"] for f in warned)
    print("fit0 total %.1fs | refit(all fits) %.1fs (x%.2f) | "
          "refit(warned only = the policy) %.1fs (x%.2f)" % (
              s0, s1_all, 1 + s1_all / s0, s1_pol, 1 + s1_pol / s0))
    print("%-6s %-7s %-4s %9s %9s %9s" % (
        "label", "rows", "fits", "fit0_s", "refit_s", "policy_x"))
    by_label = {}
    for f in fits:
        by_label.setdefault(f["label"], []).append(f)
    out["iv_wall_clock"] = {"fit0_total_s": s0, "refit_all_s": s1_all,
                            "refit_warned_s": s1_pol,
                            "policy_factor": 1 + s1_pol / s0, "by_label": {}}
    for lab in sorted(by_label):
        g = by_label[lab]
        a = sum(f["secs0"] for f in g)
        b = sum(f["secs1"] for f in g if f["warned"])
        print("%-6s %-7d %-4d %9.1f %9.1f %9.2f" % (
            lab, g[0]["n_rows"], len(g), a, b, 1 + b / a))
        out["iv_wall_clock"]["by_label"][lab] = {
            "n_rows": g[0]["n_rows"], "n_fits": len(g), "fit0_s": a,
            "refit_warned_s": b, "policy_factor": 1 + b / a}

    # --- what the rule actually does, per pair -------------------------------
    # The trigger is per PAIR (ADR-059 decision 2): if either model fires, both
    # are refit with a reduced random structure.
    print()
    print("pair-level firing rate (ADR-059 decision 2: either model fires -> both degrade)")
    pairs = {}
    for f in fits:
        pairs.setdefault(f["csv"], []).append(f)
    n_pair = len(pairs)
    b_rate = sum(1 for g in pairs.values() if any(f["warned"] for f in g))
    print("option (b) 'any warning degrades': %d/%d (%.0f%%)" % (
        b_rate, n_pair, 100.0 * b_rate / n_pair))
    print("option (e) by threshold (t_logLik, t_beta/SE):")
    out["pair_firing"] = {"n_pairs": n_pair, "option_b": b_rate, "option_e": {}}
    for t_ll in LL_GRID:
        row = []
        for t_se in SE_GRID:
            k = sum(1 for g in pairs.values() if any(fires(f, t_ll, t_se) for f in g))
            row.append("%d" % k)
            out["pair_firing"]["option_e"]["ll=%g,se=%g" % (t_ll, t_se)] = k
        print("    t_ll=%-8g " % t_ll + "  ".join(
            "se=%-6g %s/%d" % (t_se, v, n_pair) for t_se, v in zip(SE_GRID, row)))

    # --- does the restart change the test statistic? -------------------------
    print()
    print("LRT before vs after restart (arithmetic from logLik; refit of BOTH models)")
    ch = []
    for r in recs:
        c0 = r["chisq_orig"]
        c1 = 2.0 * (r["full_refit_logLik"] - r["add_refit_logLik"])
        ch.append((c0, c1))
    d_ch = [abs(a - b) for a, b in ch]
    print(line("|d_chisq|", describe(d_ch)))
    print("mean chisq before %.3f, after %.3f (df=6, additive+interaction draws mixed)"
          % (statistics.fmean(c for c, _ in ch), statistics.fmean(c for _, c in ch)))
    out["lrt_shift"] = {"abs_d_chisq": describe(d_ch),
                        "mean_chisq_before": statistics.fmean(c for c, _ in ch),
                        "mean_chisq_after": statistics.fmean(c for _, c in ch)}

    dest = os.path.join(HERE, "summary_check3.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print()
    print("wrote %s" % os.path.basename(dest))


if __name__ == "__main__":
    main()
