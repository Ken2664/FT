# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-15(その170)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN完了(PLAN-044 を採択し ADR-131 を commit した。1 セッション = 1 PLAN)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — PLAN-044 I1〜I5 は実装・テストで、`10_CONTEXT_POLICY.md` §7 の「実装・集計」の行に当たる(PLAN-044 §7 も「IMPLEMENTER = Sonnet で可。統計の判断が出たら止めて PLANNER へ」と書いている)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-044(`plans/PLAN-044-ceiling-d9-reopen.md`)の I1〜I5 を実装する。**完了の条件は次の 4 つ。

1. I1 `configs/power_sim_ceiling.yaml`(新規)・I2 `code/analysis/power_sim.py` の役割 `ceiling_probe`・I3 `code/analysis/ceiling_level.py`(新規)・I4 テストを、§3・§7 のとおりに書く
2. I3 で `L_05`・`L_50` を計算し(固定の乱数種。出力は `results/power_sim/ceiling_level/`)、値を config に転記して**当てはめの前に commit する**
3. `pytest code/tests -q` が通る(直前は `-k 'not smoke'` で 2512 passed, 11 deselected)。`--dry-run` の費用の表と、合成の反復で R のスモークを各シート 1 表(1 表の時間を記録)
4. PLAN-044 §11・§13、`logs/CHANGELOG.md`、`STATE.md` を更新して commit する。天井のシートの本実行は**起動しない**(人間が決める)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-131**(`logs/DECISIONS.md` 末尾)で PLAN-044 を採択した。人間は 7 問とも推奨 (a) を選んだ: Q1 `L_05`・`L_50`・`L_inf` / Q2 3 枚・8 点(`ceiling_p0` × 3・`ceiling_p1` × 3・`ceiling_null` × `L_05`・`L_50`。すべて (80, 1.0, 0.0)・`tau` 0)/ Q3 run3 とは別の run・役割 `ceiling_probe`・門なし・`n_rep` 100 の 1 段・`--keep-frames`・`rng_seed` = 採った日付 **20261015** / Q4 今の手続きだけを当てる / Q5 手当ては結果の後に別の PLAN で決める / Q6 本命の候補は C + B(決定ではない)/ Q7 R3 は別の PLAN-045
- PLAN-044 §7 は推奨どおりなので、書き直していない。I1〜I5 の仕様の正本は §3.1〜§3.3 と §7
- PLAN-034 D9・§7 罠6・`05_STATISTICS.md` §2 の弱点欄には打ち消し線と参照を付けた(commit `7227836`)
- この機械の R には `lme4` とその依存しか無い(`brms`・`rstanarm`・`blme` は無い)

## 触ってよいファイル / 読むべき範囲

- 書く: `configs/power_sim_ceiling.yaml`(新規)・`code/analysis/power_sim.py`・`code/analysis/ceiling_level.py`(新規)・`code/tests/`(新しいテストファイル。既存のテストは壊さない)・`results/power_sim/ceiling_level/`・`plans/PLAN-044`(§11・§13)・`logs/CHANGELOG.md`・`STATE.md`
- 読む: PLAN-044 §2・§3・§6.1・§7・§8(全文 284 行。`grep -n` → `sed -n`)/ `configs/power_sim.yaml`(P0・P1 の `eta`・`dgp`・`fit`)/ `power_sim.py` の `draw_frame` と役割・門の分岐(`grep -n 'role\|gate\|draw_frame'`)

## やってはいけないこと

- `power_sim_fit.R`・`configs/power_sim.yaml`・run3 の `rng_seed` 20261008 の変更。**`power_sim.yaml` の経路の出力は 1 バイトも変えない**(既存のテストで固定)
- I3 でパイロットの表(`results/s2_item_pilot/`)を読むこと。`L` は仮定値と規則だけで決める(PLAN-044 罠1)
- `L_05`・`L_50` を commit する前に天井のシートを当てはめること / 天井のシートの本実行・夜用タスクの登録・push・tag・GPU
- 結果の解釈・手当ての設計(確率の尺度の検定など)。**統計の判断(例: §3.3 の「起こる確率」の定義の解釈が割れる)が出たら止めて人間に伝え、PLANNER へ回す**

## 未解決 / 人間の承認待ち

- 天井のシートの起動(I5 の後に人間)→ ANALYST の記述 → 手当ての PLAN(人間が決める)/ PLAN-045(R3)の起草 / S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2・R5(凍結前)
