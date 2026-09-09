# PLAN-021 検査1: 殻の容量と、殻あたりの項目数

**組合せ論の計数であって実験結果ではない。**素のモデルの正答率は 1 度も測っていない
(`results/` は空、GPU 時間 0)。ここに出る SE は「もし真の正答率が 0.70 だったら」
という条件つきの数であり、0.70 は**仮定値**である。

```bash
python plans/PLAN-021-check1/shell_capacity_check.py
```

- `shell_capacity_check.py` —— 殻の定義 3 通り(A: 格子殻 / B: 主域外殻 / C: 外挿腕の母集団)
  について、格子点ごとの殻の組数・経路 (a) で殻に落ちる期待本数・二項 SE・経路 (b) の成否を出す
- `run.log` —— 上の出力(2026-09-09)

**結果は `plans/PLAN-021-shell-measurement.md` §3 に転記してある。**
数値は `code/tests/test_design_facts.py` が回帰テストで固定している。
