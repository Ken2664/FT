# PLAN-020 検査1 — 外挿域の容量と θ の効き方

> **★ここに出る数はすべて組合せ論の計数、または仮定を置いた算術である。実験結果ではない**
> (`CLAUDE.md` §2)。**GPU 時間 0。`results/` には置かない。**

| スクリプト | 答える問い | ログ |
|---|---|---|
| `extrap_capacity_check.py` | `M*` ごとに主軸 3 水準目(`extrap_magnitude`)は何組になるか。セル表の要求 520 組(carry 層 240)を満たす最小の `M*` はどこか | `run.log` |
| `theta_leverage_check.py` | `correct_rate(M)` が入れ子の累積平均であることは、θ の効き方にどう影響するか | `run_leverage.log` |

## 使い方

```bash
PYTHONIOENCODING=utf-8 python plans/PLAN-020-check1/extrap_capacity_check.py
PYTHONIOENCODING=utf-8 python plans/PLAN-020-check1/theta_leverage_check.py
```

## 結論(詳細と案は `plans/PLAN-020-theta-decision.md`)

- **`extrap_magnitude` の母集団は `(M* − 99)²`。**`M* = 100` では **1 組**しかない
- **C6 520 組と carry 層 240 組をともに満たす最小の `M*` は 134。**格子上の最小の成立点は **150**
- **掃引格子の 100 / 110 / 125 は「`D_ext` は空でないのに主軸が組めない」領域**であり、
  **ADR-041 決定3 規則5(`M* < 100`)の分岐の外側にある**
- **`correct_rate(M)` は `R(M)` 全体の累積平均**である(`build_items` は `[-M, M]²` から一様に引く)。
  `M = 100` では引かれる組の **98.0%** が主域の中にある。
  **仮定シナリオ S1(崖が 99)では、どの θ を選んでも `M*` が上の領域に落ちる**

## 定義をここで書き直していない

`extrap_capacity_check.py` は `code/data_gen/pool.py` の `label_main_coverage` と
`carry_label` をそのまま呼ぶ。**ラベルの定義を検査側で複製すると、本番とずれても
検査が通ってしまう。**同じ事実は `code/tests/test_design_facts.py` の
`test_extrap_magnitude_capacity_at_grid_points` /
`test_grid_points_100_and_110_cannot_fill_the_c6_cells` /
`test_smallest_viable_extrapolation_radius_is_134` が回帰テストとして固定している。
