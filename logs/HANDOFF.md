# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-05(その150)/ 直前セッションの役割: PLANNER(PLAN-041 の聴取と ADR-124)
直前セッションが終了した理由: PLAN が 1 本終わった(PLAN-041 の決定まで。実装は次の役割)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — PLAN-041 I1〜I8 は実装(`Documents/10_CONTEXT_POLICY.md` §7)。ただし I6(`05_STATISTICS.md` §3.2 の差し替え)の文面に迷ったら人間に聞く。**モデルを選ぶのは人間**

---

あなたは **IMPLEMENTER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本)。skill `code-style` を読むこと。**人間の最初の指示が先**です。

## このセッションでやること(人間の指示が先)

- `plans/PLAN-041-primary-random-structure-review.md` §6 の **I1〜I8** を実装する(決定の正本は ADR-124 と PLAN-041 §10)
  - I1 R の 4 水準(`none` / `drop_template` / `drop_coverage_corr` / `drop_coverage_slope` = 床)。**`||` に因子を渡さずダミー列に展開**。item と `seed:task:coverage` は落とさない
  - I2 `fit_failed`(床で収束しない or 床で例外)→ 過誤のシートは棄却・検出力のシートは非棄却に数え、`failed_rate` を別に出す。床での例外で集計が止まる暫定(`errored_result`)を置き換える
  - I3 各段の記録 `levels: [...]` / I4 `draw_frame` に `seed_interaction`(`scale: subspace` = Σd² 2 / `per_cell` = Σd² 6。**既存の乱数列を変えない**)/ I5 config に誤指定 2 枚((ii) が門・(i) は記録)と P1 の `tau` 0.5 の 1 点 / I6 `05_STATISTICS.md` §3.2・§6.8 / I7 テスト / I8 `06_THREATS.md` T15・`09_PAPER_PLAN.md` の反論表
- **ADR-124 の「エージェントの補い」3 点(足すシートの `sigma` = `tau` / 門は今のシートと (ii) の両方 / 誤指定 3 枚は門の前に全部回す)は人間の確認待ち**。実装前に人間に一度確かめる

## 直前セッションで確定したこと(ファイルにあるものだけ)

- ADR-124(D1〜D6・例外の規則。人間は 10 問とも推奨)。PLAN-041 §5.4 の近似は仮定値からの算術で、実験結果ではない
- run1 の門の判定(閉じた)は変えていない [run:20261004_120002_power_sim_t1t2]。run1 の `git_sha.txt`・`config_resolved.json`・`manifest_*` は commit 済み

## 読むべき範囲

- PLAN-041 §4.1・§5.4・§6・§10 / ADR-124(`grep -n '^## ADR-124' logs/DECISIONS.md`)/ `code/analysis/power_sim_fit.R`(`RANDOM_BY_LEVEL`・`errored_result`)/ `code/analysis/power_sim.py` の `draw_frame`・門(`misspecification_gate`)/ `configs/power_sim.yaml` の `sheets` と `simulation.misspecification_gate`

## やってはいけないこと

- run1 の回し直し・本実行の起動・タスクの登録 / 削除。Bash の `run_in_background` は使わない
- 門の閾値 0.075・判定点・格子・`s2_*`・ADR-059 の閾値の変更。「`drop_item` を除いた率」で門を読み直すこと
- **本物の `configs/power_sim.yaml` を `power_sim.run` / `main` に渡すテスト**(R を回して重くなる)
- 未検証の文献を論文・事前登録の本文に書くこと(`05_STATISTICS.md` に [n] を写さない)
- `.md`・`.py`・`.yaml`・`.R` は LF。日本語を含む置換は Python で

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- ADR-124 のエージェントの補い 3 点 / 夜用タスク 2 本の扱い / SCOUT 41 件の原典確認
- 平行性の TOST の Δ・D7 の閾値・D3 のブートストラップの反復数・天井のセル / S4・S5 / worktree の削除 / ★R8 の push と G2-1 承認 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate
