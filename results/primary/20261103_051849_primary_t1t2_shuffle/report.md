# 主要検定の報告(primary.py)

- run_id: `20261103_051849_primary_t1t2_shuffle` / モード: `shuffle` / git: `dc9ab928814f0f8e5749fdb088cd22f764896a48`
- **合成データの配線の確認である。ここに出る数は実験結果ではない**(`CLAUDE.md` §2)

## shuffled

| 判定 | 落ちたセル | df | 天井(セルと向き) | 縮退の段 | LRT の p 値 | TOST の最小 Δ | Δ | 同等か |
|---|---|---|---|---|---|---|---|---|
| 実施可 | なし | 2 | なし | drop_coverage_slope | 0.7902 | 1.294 | 未決 | (Δ 未決のため判定しない) |

- 入れ替え(seed 0): template が複数の task に跨る: t1, t2_count, t2_distance, t2_money, t2_people, t2_time

---

- ランダム効果は `(0 + coverage | seed)` の単独表記で、`(1 | seed)` を併記しない(ADR-066 決定1)。
- p 値と TOST の欄は判定が `実施可` の行だけ埋める。天井・当てはめ失敗の行の値は `primary.json` にある(ADR-137 決定3)。
