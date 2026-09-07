"""PLAN-016 check 1c: is the failure the estimator or my synthetic data?

check1b showed 2*(ELBO_full - ELBO_add) is negative in 200/200 null replicates
and gave p=0.55 on data that DOES contain an interaction. Before blaming
BinomialBayesMixedGLM, confirm the interaction is actually detectable in
these data at all.

Reference: a plain fixed-effects binomial GLM LRT (df=6) on the same frames.
That reference IGNORES the random effects, so it is anticonservative and is
NOT a stand-in for the glmer LRT. It is used here only to show the signal is
present -- if the plain GLM sees it easily and the VB comparison does not,
the shortfall is in the estimator.
"""

import json
import warnings

import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from check1_statsmodels_r3 import F_ADD, F_FULL, build, make_frame

N_REP = 50
DF = 6
CRIT = stats.chi2.ppf(0.95, DF)


def elbo_stat(df):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ef = -float(build(F_FULL, df).fit_vb(verbose=False).optim_retvals.fun)
        ea = -float(build(F_ADD, df).fit_vb(verbose=False).optim_retvals.fun)
    return 2.0 * (ef - ea)


def glm_stat(df):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = smf.glm(F_FULL, data=df, family=sm.families.Binomial()).fit()
        a = smf.glm(F_ADD, data=df, family=sm.families.Binomial()).fit()
    return 2.0 * (f.llf - a.llf)


def sweep(scale, n_rep, seed0):
    e, g = [], []
    for rep in range(n_rep):
        rng = np.random.default_rng(seed0 + rep)
        df = make_frame(rng, interaction_scale=scale)
        e.append(elbo_stat(df))
        g.append(glm_stat(df))
    e, g = np.asarray(e), np.asarray(g)
    return {
        "interaction_scale": scale,
        "elbo_diff_mean": float(e.mean()),
        "elbo_diff_min": float(e.min()),
        "elbo_diff_max": float(e.max()),
        "elbo_frac_gt_crit": float((e > CRIT).mean()),
        "glm_llf_lrt_mean": float(g.mean()),
        "glm_llf_lrt_min": float(g.min()),
        "glm_llf_lrt_max": float(g.max()),
        "glm_frac_gt_crit": float((g > CRIT).mean()),
        "glm_frac_negative": float((g < 0).mean()),
    }


if __name__ == "__main__":
    rows = [sweep(0.0, N_REP, 700000), sweep(1.0, N_REP, 800000)]
    with open("check1c_out.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    print("crit chi2(6) at 0.95 = %.4f" % CRIT)
    for r in rows:
        print("--- interaction_scale = %.1f ---" % r["interaction_scale"])
        print("  VB ELBO diff : mean=%8.3f  range=[%8.3f, %8.3f]  frac>crit=%.2f"
              % (r["elbo_diff_mean"], r["elbo_diff_min"], r["elbo_diff_max"],
                 r["elbo_frac_gt_crit"]))
        print("  plain GLM LRT: mean=%8.3f  range=[%8.3f, %8.3f]  frac>crit=%.2f  frac<0=%.2f"
              % (r["glm_llf_lrt_mean"], r["glm_llf_lrt_min"], r["glm_llf_lrt_max"],
                 r["glm_frac_gt_crit"], r["glm_frac_negative"]))
