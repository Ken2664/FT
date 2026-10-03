"""F104-c material for the CURRENT model (T1 x T2, n_item = 80, df = 2). Synthetic arithmetic, not an experiment.

Re-does PLAN-019 check3 [C]/[D] with the current config's levels and draw_frame's latent structure:
  - v[item] drawn per (task, coverage, k), shared by all seeds
  - w[template] drawn once per replication, template = templates[task][k % n_tmpl]
  - u[s, cov] has no task index
Direct channel only (cell means of the linear predictor); the binomial channel is NOT measured.
"""
import math

import numpy as np
import yaml

cfg = yaml.safe_load(open("configs/power_sim.yaml", encoding="utf-8"))
tasks = cfg["effect"]["task_levels"]
covs = cfg["effect"]["coverage_levels"]
templates = cfg["dgp"]["templates"]
n_item = int(cfg["dgp"]["n_item"])
P1_RMS = 0.352767
p1_eta = np.array(cfg["effect"]["profiles"]["P1"]["eta"])
P1_COEF = [(p1_eta[1, c] - p1_eta[1, 0]) - (p1_eta[0, c] - p1_eta[0, 0]) for c in (1, 2)]
N_REP = 20000
rng = np.random.default_rng(20261003)


def cells(s2_item, s2_tmpl, n_item, sigma=0.0):
    out = np.zeros((N_REP, len(tasks), len(covs)))
    names = sorted({t for v in templates.values() for t in v})
    w = {n: rng.normal(0, math.sqrt(s2_tmpl), N_REP) for n in names}
    u = rng.normal(0, sigma, (N_REP, len(covs))) if sigma > 0 else np.zeros((N_REP, len(covs)))
    for ti, task in enumerate(tasks):
        tl = templates[task]
        tmean = sum(w[tl[k % len(tl)]] for k in range(n_item)) / n_item
        for ci in range(len(covs)):
            v = rng.normal(0, math.sqrt(s2_item), (N_REP, n_item)).mean(axis=1)
            out[:, ti, ci] = v + tmean + u[:, ci]
    return out


def rms(c):
    r = c - c.mean(axis=1, keepdims=True) - c.mean(axis=2, keepdims=True) + c.mean(axis=(1, 2), keepdims=True)
    return np.sqrt((r**2).sum(axis=(1, 2)) / ((len(tasks) - 1) * (len(covs) - 1)))


def coef_sd(c):
    return [float(((c[:, 1, k] - c[:, 1, 0]) - (c[:, 0, k] - c[:, 0, 0])).std()) for k in (1, 2)]


print(f"tasks={tasks} covs={covs} n_item={n_item} templates/task={[len(templates[t]) for t in tasks]} reps={N_REP}")
print(f"P1 RMS={P1_RMS}  P1 interaction coefs={[round(x, 6) for x in P1_COEF]}")
print("[C'] s2_item  s2_tmpl  mean RMS  %P1   SD(coef interp)  SD(coef extrap)  analytic sqrt(s2/20)")
for s2i, s2t in [(0, 0), (0, 0.5), (0, 8), (0.25, 0), (0.5, 0), (1, 0), (2, 0), (4, 0), (1, 1), (4, 4)]:
    c = cells(s2i, s2t, n_item)
    m = rms(c).mean()
    sd = coef_sd(c)
    print(f"     {s2i:<7} {s2t:<7}  {m:.5f}  {100*m/P1_RMS:5.1f}%  {sd[0]:.4f}           {sd[1]:.4f}           {math.sqrt(s2i/20):.4f}")
print("[ctrl] sigma (seed) channel, s2=0:")
for sg in (0.5, 1.5):
    c = cells(0, 0, n_item, sigma=sg)
    print(f"     sigma={sg}  mean RMS={rms(c).mean():.2e}  max|coef|={np.abs(np.array(coef_sd(c))).max():.2e}")
print("[D'] s2_item=1 vs n_item:")
for n in (48, 80, 160):
    c = cells(1, 0, n)
    print(f"     n_item={n:<4} mean RMS={rms(c).mean():.5f} ({100*rms(c).mean()/P1_RMS:.1f}% of P1)")
