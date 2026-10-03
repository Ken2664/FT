# Type I of the 2-df test when DGP adds z[s,task,cov]~N(0,tau^2) that the model lacks.
# The model's (0+coverage|seed) absorbs the task-common part; the task-specific part adds
# tau^2/n_seed * [[4,2],[2,4]] to the contrast covariance, unseen by the model.
import numpy as np
from scipy.stats import chi2
exec(open("approx_levers.py").read().split("print(")[0])  # reuse info/cov/P0
S = cov(P0, 2.0, 10, 80); crit = chi2.ppf(0.95, 2); rng = np.random.default_rng(0)
for tau in (0.0, 0.25, 0.5, 0.75, 1.0, 1.5):
    T = S + tau**2/10 * np.array([[4, 2], [2, 4]])
    x = rng.multivariate_normal([0, 0], T, size=400000)
    q = np.einsum("ij,jk,ik->i", x, np.linalg.inv(S), x)
    print(f"tau={tau}: approx Type I = {np.mean(q > crit):.3f}")
