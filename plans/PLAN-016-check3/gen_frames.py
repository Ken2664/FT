"""PLAN-016 check 3, part 1: write the synthetic tables the restart check fits.

This is NOT pipeline code. It reuses check 2's generative model verbatim by
importing make_frame from plans/PLAN-016-check2/gen_frame.py, so the two checks
are talking about the same table and the model cannot drift between them.
No real data is touched (PLAN-016 section 8).

What is new here is only the SWEEP: check 2 needed a handful of draws to time a
fit, check 3 needs many draws because it is estimating a RATE (how often does a
restart clear an lme4 warning). Each draw gets its own rng seed.

Output is ASCII only: this environment's stdout is cp932.
"""

import argparse
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK2 = os.path.join(os.path.dirname(HERE), "PLAN-016-check2", "gen_frame.py")

# The sweep. (label, items per coverage, interaction_scale, number of draws).
# Sizes come from check 2's F50 table; the cost per pair there was 5.6 s / 18.7 s
# / 31.9 s, so the draw counts are picked to keep the whole check near 20 min.
# The last block is not additive: it asks whether the restart behaves the same
# when the full model's extra terms are real, not just noise.
SWEEP = [
    ("i08", 8, 0.0, 10),
    ("i24", 24, 0.0, 12),
    ("i48", 48, 0.0, 6),
    ("x24", 24, 1.0, 6),
]

N_SEED = 10          # ADR-028: the primary conditions get 10 seeds
RNG_BASE = 30260907  # distinct from check 2's 20260907 so the draws are new


def load_check2():
    """Import check 2's generator rather than copying it (single source of truth)."""
    spec = importlib.util.spec_from_file_location("check2_gen_frame", CHECK2)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--n-seed", type=int, default=N_SEED)
    args = ap.parse_args()

    gen = load_check2()
    made = []
    for label, n_item, inter, n_draw in SWEEP:
        for k in range(n_draw):
            rng_seed = RNG_BASE + 1000 * len(made) + k
            rng = np.random.default_rng(rng_seed)
            df = gen.make_frame(rng, args.n_seed, n_item, inter)
            name = "frame_%s_d%02d.csv" % (label, k)
            path = os.path.join(args.out_dir, name)
            df.to_csv(path, index=False)
            made.append(name)
            print("%s rows=%d n_item=%d n_template=%d inter=%.1f rng=%d mean_is_rule=%.3f" % (
                name, len(df), df["item"].nunique(), df["template"].nunique(),
                inter, rng_seed, df["is_rule"].mean(),
            ))
    print("wrote %d frames" % len(made))


if __name__ == "__main__":
    main()
