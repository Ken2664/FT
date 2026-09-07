"""PLAN-016 check 1: does statsmodels BinomialBayesMixedGLM give an ML log-likelihood?

Answers: (a) can vc_formula express 3 CROSSED random intercepts (R2)?
         (b) does the fitted object expose anything like `llf` (R3)?
         (c) if it does, is it the maximised log-likelihood, or an ELBO /
             log joint density at the posterior mode?
         (d) may two nested fits be differenced and referred to chi2 (R3)?

Synthetic data has the shape of Documents/05_STATISTICS.md section 3.2:
binomial response, task(4) x coverage(3) fixed effects,
(1|seed) + (1|item) + (1|template) crossed random intercepts.
No real data is touched.
"""

import json
import sys
import time
import warnings
import zlib

import numpy as np
import pandas as pd
from scipy import stats

from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

TASKS = ["T1", "T1b", "T2", "T3"]
COVERAGES = ["id", "interp", "extrap_magnitude"]
T2_TEMPLATES = ["t2_count", "t2_people", "t2_distance", "t2_money", "t2_time"]

N_SEED = 6
N_ITEM_PER_COVERAGE = 8

SD_SEED = 0.6
SD_ITEM = 0.5
SD_TEMPLATE = 0.4


def make_frame(rng, interaction_scale):
    """Build the long-form table. interaction_scale=0.0 gives the additive truth."""
    items = []
    for cov in COVERAGES:
        for k in range(N_ITEM_PER_COVERAGE):
            items.append({"item": "%s_%02d" % (cov, k), "coverage": cov})

    u_seed = {s: rng.normal(0.0, SD_SEED) for s in range(N_SEED)}
    u_item = {it["item"]: rng.normal(0.0, SD_ITEM) for it in items}

    def template_of(task, item_name):
        if task == "T2":
            # crc32, not hash(): str.__hash__ is salted per process, so hash()
            # would make the template assignment differ between runs.
            idx = zlib.crc32(item_name.encode("utf-8")) % len(T2_TEMPLATES)
            return T2_TEMPLATES[idx]
        return "tpl_%s" % task

    templates = sorted({template_of(t, it["item"]) for t in TASKS for it in items})
    u_tpl = {t: rng.normal(0.0, SD_TEMPLATE) for t in templates}

    b_task = {"T1": 0.0, "T1b": -0.3, "T2": -0.9, "T3": -0.5}
    b_cov = {"id": 0.0, "interp": -0.8, "extrap_magnitude": -1.6}
    b_int = {
        ("T1", "interp"): 0.0, ("T1", "extrap_magnitude"): 0.0,
        ("T1b", "interp"): -0.2, ("T1b", "extrap_magnitude"): -0.4,
        ("T2", "interp"): -0.6, ("T2", "extrap_magnitude"): -1.2,
        ("T3", "interp"): -0.4, ("T3", "extrap_magnitude"): -0.9,
    }

    rows = []
    for s in range(N_SEED):
        for task in TASKS:
            for it in items:
                cov = it["coverage"]
                tpl = template_of(task, it["item"])
                eta = (
                    1.0
                    + b_task[task]
                    + b_cov[cov]
                    + interaction_scale * b_int.get((task, cov), 0.0)
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
                        "seed": "s%d" % s,
                        "item": it["item"],
                        "template": tpl,
                    }
                )
    df = pd.DataFrame(rows)
    df["task"] = pd.Categorical(df["task"], categories=TASKS)
    df["coverage"] = pd.Categorical(df["coverage"], categories=COVERAGES)
    return df


VC = {
    "seed": "0 + C(seed)",
    "item": "0 + C(item)",
    "template": "0 + C(template)",
}

F_FULL = "is_rule ~ task * coverage"
F_ADD = "is_rule ~ task + coverage"


def build(formula, df):
    return BinomialBayesMixedGLM.from_formula(formula, VC, df)


def report_model_shape(mod, label, out):
    out.append(
        {
            "model": label,
            "k_fep": int(mod.k_fep),
            "k_vcp": int(mod.k_vcp),
            "k_vc": int(mod.k_vc),
            "vcp_names": list(mod.vcp_names),
            "ident_levels_per_vcp": [
                int((np.asarray(mod.ident) == j).sum()) for j in range(mod.k_vcp)
            ],
            "fep_names": list(mod.fep_names),
        }
    )


def attrs_of(res):
    public = [a for a in dir(res) if not a.startswith("_")]
    likelihood_like = [
        a for a in public
        if any(k in a.lower() for k in ("llf", "like", "aic", "bic", "elbo", "dev", "post"))
    ]
    return public, likelihood_like


def main():
    warnings.simplefilter("always")
    rng = np.random.default_rng(20260907)
    shape = []
    lines = []

    df = make_frame(rng, interaction_scale=1.0)
    lines.append("rows=%d  seeds=%d  items=%d  templates=%d"
                 % (len(df), df["seed"].nunique(), df["item"].nunique(),
                    df["template"].nunique()))
    lines.append("crossed check: items per seed = %s"
                 % sorted(df.groupby("seed", observed=True)["item"].nunique().unique().tolist()))
    lines.append("crossed check: seeds per item = %s"
                 % sorted(df.groupby("item", observed=True)["seed"].nunique().unique().tolist()))

    mod_full = build(F_FULL, df)
    mod_add = build(F_ADD, df)
    report_model_shape(mod_full, "full", shape)
    report_model_shape(mod_add, "add", shape)

    results = {}
    for label, mod in (("full", mod_full), ("add", mod_add)):
        for how in ("vb", "map"):
            t0 = time.time()
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                if how == "vb":
                    res = mod.fit_vb(verbose=False)
                else:
                    res = mod.fit_map()
                caught = [str(x.message)[:120] for x in w]
            dt = time.time() - t0
            public, like_like = attrs_of(res)
            objective = None
            if getattr(res, "optim_retvals", None) is not None:
                objective = float(getattr(res.optim_retvals, "fun", float("nan")))
            results[(label, how)] = {
                "res": res,
                "secs": dt,
                "objective": objective,
                "has_llf": hasattr(res, "llf"),
                "like_like_attrs": like_like,
                "warnings": caught,
                "logposterior_at_params": float(mod.logposterior(res.params)),
                "n_public_attrs": len(public),
            }
            lines.append(
                "%s/%s  secs=%.2f  has_llf=%s  optim.fun=%s  logposterior=%.4f  like_attrs=%s"
                % (label, how, dt, hasattr(res, "llf"),
                   ("None" if objective is None else "%.4f" % objective),
                   float(mod.logposterior(res.params)), like_like)
            )
            if caught:
                lines.append("    warnings: %s" % caught)

    # public attribute list once (same class for all four fits)
    lines.append("public attrs of BayesMixedGLMResults: %s"
                 % sorted(attrs_of(results[("full", "vb")]["res"])[0]))

    # Differences of every likelihood-like quantity we could find.
    for how in ("vb", "map"):
        f = results[("full", how)]
        a = results[("add", how)]
        if f["objective"] is not None and a["objective"] is not None:
            # optimiser minimises the NEGATIVE objective, so -fun is the maximand
            d = 2.0 * ((-f["objective"]) - (-a["objective"]))
            lines.append("%s: 2*(maximand_full - maximand_add) = %.4f  -> chi2(6) p = %.4g"
                         % (how, d, stats.chi2.sf(d, 6) if d > 0 else float("nan")))
        dlp = 2.0 * (f["logposterior_at_params"] - a["logposterior_at_params"])
        lines.append("%s: 2*(logposterior_full - logposterior_add) = %.4f "
                     "(NOT comparable: different parameter spaces / priors)" % (how, dlp))

    # Does the ELBO/objective even have the same additive constant across models?
    lines.append("NOTE full and add have k_vc=%d each; k_fep %d vs %d"
                 % (mod_full.k_vc, mod_full.k_fep, mod_add.k_fep))

    out = {
        "statsmodels": __import__("statsmodels").__version__,
        "python": sys.version.split()[0],
        "shape": shape,
        "lines": lines,
    }
    with open("check1_out.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    for ln in lines:
        print(ln)


if __name__ == "__main__":
    main()
