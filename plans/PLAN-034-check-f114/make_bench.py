"""F114 parallel benchmark config: power_sim.yaml with borrowed s2 = 0.25 (same as I7), 64 pairs.

Not an experiment. Numbers are for the run-location decision only (not for claims).
"""
import sys
from pathlib import Path

import yaml

src = Path("configs/power_sim.yaml")
cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
cfg["analysis"]["id"] = "power_sim_bench_parallel"
cfg["dgp"]["s2_item"] = 0.25  # borrowed, same as I7; NOT an F104-c answer
cfg["dgp"]["s2_tmpl"] = 0.25
cfg["simulation"]["n_rep"] = 16
cfg["fit"]["n_workers"] = 16
# the same four conditions I7 timed sequentially
cfg["sheets"] = [
    {"id": "p1", "role": "power", "profile": "P1", "sigma": [0.0, 1.0], "rho": [0.0], "tau": "zero"},
    {"id": "p0", "role": "null_calibration", "profile": "P0", "sigma": [1.0], "rho": [0.0], "tau": "zero"},
    {"id": "misspecification", "role": "misspecification", "profile": "P0", "sigma": [1.5],
     "rho": [0.0], "tau": "equals_sigma"},
]
out = Path(sys.argv[1])
out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")
print(out)
