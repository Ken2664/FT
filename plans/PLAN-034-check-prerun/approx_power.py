# Approximate Wald power of the 2-df task:coverage test under the power_sim DGP.
# Seed effects u[s,cov] are shared by T1 and T2, so they cancel in the interaction
# contrast; they enter only through per-item Fisher information (nonlinearity).
# Item effects integrated by Gauss-Hermite; y enumerated over 2^n_seed patterns.
import itertools, numpy as np
from scipy.stats import chi2, ncx2
rng = np.random.default_rng(1)
P1 = np.array([[2.848934, 2.012234, 1.138832], [1.751066, 0.587766, -0.938832]])
S2_ITEM, S2_TMPL, N_ITEM, N_SEED = 2.0, 0.5, 80, 10
TPL = {0: 1, 1: 5}
gh_x, gh_w = np.polynomial.hermite_e.hermegauss(40); gh_w = gh_w / gh_w.sum()
Y = np.array(list(itertools.product([0, 1], repeat=N_SEED)))  # 1024 x 10
def item_info(offsets):  # offsets: (N_SEED,) logit offsets excluding item effect
    eta = offsets[None, :] + np.sqrt(S2_ITEM) * gh_x[:, None]      # Q x S
    p = 1 / (1 + np.exp(-eta))
    logp, log1p_ = np.log(p), np.log1p(-p)
    lik = np.exp(Y @ logp.T + (1 - Y) @ log1p_.T)                  # 1024 x Q
    score = Y.sum(1)[:, None] - p.sum(1)[None, :]                  # 1024 x Q
    L = lik @ gh_w; dL = (lik * score) @ gh_w
    return np.sum(dL**2 / L)
def power(eta_tab, sigma, rho, n_draw=30):
    lam = []
    for _ in range(n_draw):
        C = sigma**2 * ((1 - rho) * np.eye(3) + rho * np.ones((3, 3)))
        u = rng.multivariate_normal(np.zeros(3), C, size=N_SEED) if sigma > 0 else np.zeros((N_SEED, 3))
        V = np.zeros((2, 3))
        for t in range(2):
            w = rng.normal(0, np.sqrt(S2_TMPL), size=TPL[t])
            for c in range(3):
                infos = [item_info(eta_tab[t, c] + u[:, c] + w[j]) for j in range(TPL[t])]
                V[t, c] = 1 / (N_ITEM * np.mean(infos))
        ctr = np.array([(eta_tab[1, k] - eta_tab[1, 0]) - (eta_tab[0, k] - eta_tab[0, 0]) for k in (1, 2)])
        S = np.array([[V[1,1]+V[1,0]+V[0,1]+V[0,0], V[1,0]+V[0,0]], [V[1,0]+V[0,0], V[1,2]+V[1,0]+V[0,2]+V[0,0]]])
        lam.append(ctr @ np.linalg.solve(S, ctr))
    lam = np.array(lam); crit = chi2.ppf(0.95, 2)
    return np.mean(1 - ncx2.cdf(crit, 2, lam)), np.median(lam), np.sqrt(S[0,0]), np.sqrt(S[1,1])
for rho in (0.0, 1.0):
    for sigma in (0.0, 0.5, 1.0, 1.5):
        pw, lam, se1, se2 = power(P1, sigma, rho)
        print(f"rho={rho} sigma={sigma}: approx power={pw:.3f} median lambda={lam:.2f} SE(c_interp)~{se1:.3f} SE(c_extrap)~{se2:.3f}")
