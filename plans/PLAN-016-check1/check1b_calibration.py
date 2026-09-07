"""PLAN-016 check 1b: two follow-ups to check1.

(1) fit_map reported |gradient| ~ 8759 on clean synthetic data. Is that my
    setup, or the estimator? Try scale_fe=True, more BFGS iterations, and
    inspect optim_retvals.

(2) The only likelihood-like number fit_vb exposes is -optim_retvals.fun,
    i.e. the ELBO. R3 asks whether two nested fits may be differenced and
    referred to chi2(df=6). Test that DIRECTLY: simulate under the additive
    null many times and look at the distribution of 2*(ELBO_full - ELBO_add).
    Under a valid LRT it would be chi2(6): mean 6, 95th pct 12.59,
    P(stat > 12.59) = 0.05.
"""

import json
import warnings

import numpy as np
from scipy import stats

from check1_statsmodels_r3 import F_ADD, F_FULL, build, make_frame

N_REP = 200
DF = 6
CRIT = stats.chi2.ppf(0.95, DF)


def elbo(mod):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = mod.fit_vb(verbose=False)
    return -float(res.optim_retvals.fun), res


def part1():
    rng = np.random.default_rng(20260907)
    df = make_frame(rng, interaction_scale=1.0)
    mod = build(F_FULL, df)
    out = []
    trials = [
        ("default", dict()),
        ("scale_fe", dict(scale_fe=True)),
        ("maxiter200000", dict(minim_opts={"maxiter": 200000, "gtol": 1e-6})),
        ("scale_fe+maxiter", dict(scale_fe=True,
                                  minim_opts={"maxiter": 200000, "gtol": 1e-6})),
    ]
    for name, kw in trials:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            res = mod.fit_map(**kw)
            msgs = [str(x.message)[:90] for x in w]
        r = res.optim_retvals
        out.append(
            {
                "trial": name,
                "success": bool(getattr(r, "success", None)),
                "status": int(getattr(r, "status", -1)),
                "nit": int(getattr(r, "nit", -1)),
                "fun": float(r.fun),
                "grad_norm": float(np.sqrt(np.sum(r.jac ** 2))) if hasattr(r, "jac") else None,
                "warnings": msgs,
            }
        )
    return out


def part2():
    stats_null = []
    for rep in range(N_REP):
        rng = np.random.default_rng(900000 + rep)
        df = make_frame(rng, interaction_scale=0.0)   # additive truth: no interaction
        ef, _ = elbo(build(F_FULL, df))
        ea, _ = elbo(build(F_ADD, df))
        stats_null.append(2.0 * (ef - ea))
    a = np.asarray(stats_null)
    return {
        "n_rep": N_REP,
        "mean": float(a.mean()),
        "chi2_df_mean_expected": float(DF),
        "sd": float(a.std(ddof=1)),
        "chi2_sd_expected": float(np.sqrt(2 * DF)),
        "min": float(a.min()),
        "max": float(a.max()),
        "frac_negative": float((a < 0).mean()),
        "pct_quantiles": {
            q: float(np.quantile(a, q / 100.0)) for q in (5, 25, 50, 75, 95)
        },
        "chi2_quantiles": {
            q: float(stats.chi2.ppf(q / 100.0, DF)) for q in (5, 25, 50, 75, 95)
        },
        "crit_95": float(CRIT),
        "empirical_type1_at_alpha_05": float((a > CRIT).mean()),
    }


if __name__ == "__main__":
    p1 = part1()
    p2 = part2()
    with open("check1b_out.json", "w", encoding="utf-8") as fh:
        json.dump({"fit_map_convergence": p1, "elbo_diff_null": p2}, fh, indent=2)
    print("--- fit_map convergence attempts ---")
    for r in p1:
        print("%-18s success=%-5s nit=%-6d fun=%12.4f |grad|=%s"
              % (r["trial"], r["success"], r["nit"], r["fun"],
                 "n/a" if r["grad_norm"] is None else "%.3f" % r["grad_norm"]))
        for m in r["warnings"]:
            print("    warn: %s" % m)
    print("--- 2*(ELBO_full - ELBO_add) under the additive null, %d reps ---" % N_REP)
    for k in ("mean", "chi2_df_mean_expected", "sd", "chi2_sd_expected",
              "min", "max", "frac_negative", "crit_95",
              "empirical_type1_at_alpha_05"):
        print("%-28s %s" % (k, p2[k]))
    print("quantiles observed: %s" % p2["pct_quantiles"])
    print("quantiles chi2(6):  %s" % p2["chi2_quantiles"])
