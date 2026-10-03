# PLAN-034 check: F114 run location / F104-c stakes (2026-10-03, session 137)

Decision material only. NOT experiment results and NOT answers to F104-c (agent does not propose values).

- `stakes_t1t2.py` -> `stakes_t1t2.log`: PLAN-019 check3 [C]/[D] redone for the current model
  (T1 x T2, n_item = 80, df = 2). Synthetic arithmetic, direct channel only (binomial channel not measured).
- `make_bench.py` -> `bench_parallel.yaml`: configs/power_sim.yaml with borrowed s2_item = s2_tmpl = 0.25
  (same as PLAN-034 I7), n_rep 16, 4 grid points (the same 4 conditions I7 timed sequentially), 16 workers.
- `bench_timing.txt`: timing of of that run on this machine
  (`python -m code.analysis.power_sim --config bench_parallel.yaml --out-dir <scratchpad>`). Frames/fits stayed in the scratchpad.
- power_sim_summary.json (power values from borrowed s2) is NOT kept in the repo (HANDOFF: borrowed-value numbers are not written to documents/results).
