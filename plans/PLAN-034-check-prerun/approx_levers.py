# sigma = 0 => seeds exchangeable; k = sum(y) ~ Binomial(n_seed, p) given item effect.
import numpy as np
from scipy.stats import chi2, ncx2, binom, norm
P1 = np.array([[2.848934, 2.012234, 1.138832], [1.751066, 0.587766, -0.938832]])
P0 = np.array([[2.8, 1.8, 0.6], [1.8, 0.8, -0.4]])
gh_x, gh_w = np.polynomial.hermite_e.hermegauss(60); gh_w = gh_w / gh_w.sum()
def info(eta, s2_item, n_seed):
    e = eta + np.sqrt(s2_item) * gh_x; p = 1/(1+np.exp(-e)); k = np.arange(n_seed+1)[:, None]
    lik = binom.pmf(k, n_seed, p[None, :]); L = lik @ gh_w; dL = (lik * (k - n_seed*p[None, :])) @ gh_w
    return np.sum(dL**2 / L)
def cov(tab, s2_item, n_seed, n_item):
    V = np.array([[1/(n_item*info(tab[t,c], s2_item, n_seed)) for c in range(3)] for t in range(2)])
    return np.array([[V[1,1]+V[1,0]+V[0,1]+V[0,0], V[1,0]+V[0,0]], [V[1,0]+V[0,0], V[1,2]+V[1,0]+V[0,2]+V[0,0]]])
def power(tab, s2_item, n_seed, n_item):
    S = cov(tab, s2_item, n_seed, n_item)
    c = np.array([(tab[1,k]-tab[1,0])-(tab[0,k]-tab[0,0]) for k in (1,2)])
    return 1 - ncx2.cdf(chi2.ppf(0.95, 2), 2, c @ np.linalg.solve(S, c)), np.sqrt(np.diag(S))
print("power(P1) by s2_item x n_item (n_seed=10, sigma=0, s2_tmpl ignored: cancels within task)")
for s2 in (0.5, 1.0, 2.0, 4.0):
    print(f"  s2_item={s2}: " + "  ".join(f"n_item={n}:{power(P1, s2, 10, n)[0]:.2f}" for n in (80, 120, 160, 240, 320)))
print("power(P1) by n_seed (s2_item=2, n_item=80):", "  ".join(f"{s}:{power(P1, 2.0, s, 80)[0]:.2f}" for s in (5, 10, 20, 40)))
# TOST under P0 (true contrasts 0): min Delta = max_k |est_k| + z*SE_k ; Monte Carlo on the normal approx
S = cov(P0, 2.0, 10, 80); se = np.sqrt(np.diag(S)); z = norm.ppf(0.95)
rng = np.random.default_rng(0); est = rng.multivariate_normal([0, 0], S, size=200000)
m = np.max(np.abs(est) + z*se, axis=1)
print(f"TOST under P0 (s2_item=2, n_item=80): SE={se.round(3)}; min-Delta quantiles 10/50/80/90% =", np.quantile(m, [.1,.5,.8,.9]).round(3))
print("  P1 true contrasts = -0.327 / -0.980 (logit)")
