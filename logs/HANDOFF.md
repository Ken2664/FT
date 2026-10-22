# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-22(その178)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 283k)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 実装・データ生成(`10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)。統計の判断が出たら止めて PLANNER(Opus)へ

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。実装の前に skill `code-style` を読むこと。

## このセッションでやること(1つだけ)

**PLAN-046 I4 の残りと I5 を終え、人間に起動を聞くところまで進める。**

1. `python -m code.analysis.ceiling_probnull --config configs/power_sim_ceiling_probnull.yaml`(**作業ツリーがきれいな状態で**。出力は `results/power_sim/ceiling_probnull_solve/ceiling_probnull_solve.json`。run_id が付く)
2. 出力の `solved`(各 2 値)を `configs/power_sim_ceiling_probnull.yaml` の `ceiling.probability_null.solved.L_05`・`L_50` に**そのまま転記**し、run_id をコメントに書く。試行の値(スクラッチ・配線確認用)は L_05: T2.interp 1.5847352592・T2.extrap_magnitude 1.1084329182 / L_50: 1.7624797985・1.6491025406 で、本実行が違えば理由を調べる
3. `code/tests/test_ceiling_probnull.py` に「config の `solved` = 出力 JSON(run_id つき)」のテストを足す(`test_ceiling_probe.py` の `test_committed_levels_are_the_ceiling_level_output` と同じ形)。`pytest code/tests -q` → commit(`[run:<solve の run_id>]`)。**ロジットの当てはめの前に commit**
4. スモーク(スクラッチパッドに出力): (a) probnull の config の写しを `simulation.n_rep_stages: [1]` にして `python -m code.analysis.power_sim --config <写し> --out-dir <scratch>/probnull_smoke --through-stage 1 --keep-frames --workers 2`(ロジット 2 表。1 表 3〜30 分なのでバックグラウンド)/ (b) `python -m code.analysis.ceiling_remedy --config configs/ceiling_remedy.yaml --out-dir <scratch>/eval_smoke --max-rep 1 --workers 8 --source-dir ceiling_probnull=<scratch>/probnull_smoke`(10 表に LMM)。`--dry-run` も
5. PLAN-046 §13 に 1 表の時間(ロジット・LMM)と算術(200 表 ÷ 16 並列 / 1000 表の LMM)を書き、§11 の I1〜I4 の行を更新 → `STATE.md`・`logs/CHANGELOG.md` → commit → **人間に起動を聞く**(probnull の生成 `--out-dir results/power_sim/ceiling_probnull --workers 16` → 評価 `--out-dir results/ceiling_remedy --workers 16`)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `c11164d`: I1 `code/analysis/ceiling_remedy.py` の `ceiling_rule`(セルが欠ける表は止まる)/ I2 `code/analysis/power_sim_fit_lmm.R`(`power_sim_fit.R` は不変。SHA-256 を `test_ceiling_remedy.py` で固定)/ I3 `ceiling_remedy.py`・`configs/ceiling_remedy.yaml`(全部の表に LMM・表は乱数種から組み直して照合・G1・G2 を点ごと・`--max-rep` のときは門を判定しない)/ I4 `code/analysis/ceiling_probnull.py`・`configs/power_sim_ceiling_probnull.yaml`(`solved` null・`rng_seed` 20261022)・`power_sim.py` の `probability_null`。pytest 2604 passed
- 人間が `ceiling_probnull` の DGP = 案 A(PLAN-046 §6.2・§12。提案 エージェント / 採択 人間)
- LMM の最適化は `nloptwrap`(lme4 2.0.6 の `lmer` の既定を config に明示。PLAN-046 §5.6 の「実装上の注意」で、決定ではない)
- `configs/ceiling_remedy.yaml` は probnull の `solved` が null のあいだ読めずに止まる(設計どおり)。既存の 800 表だけで試すなら、sources を 1 つにした写しをスクラッチに作る

## 触ってよいファイル / 読むべき範囲

- 読む: `plans/PLAN-046-ceiling-remedy.md` §6・§7・§11・§13(`grep -n '^## \|^### '` → `sed -n`)/ `code/analysis/ceiling_probnull.py`・`ceiling_remedy.py` は必要な関数だけ
- 触ってよい: `configs/power_sim_ceiling_probnull.yaml` の `solved` とそのコメント / `code/tests/test_ceiling_probnull.py` / `results/power_sim/ceiling_probnull_solve/` / PLAN-046 §11・§13 / `STATE.md` / `logs/CHANGELOG.md`

## やってはいけないこと

- `configs/power_sim.yaml`・`power_sim_ceiling.yaml`・`ceiling_remedy.yaml` の門の値・`power_sim_fit.R` を変える / run3・probnull の本生成・評価の本実行を起動する(人間)
- 転記した `solved` を評価の結果を見て変える。解く規則(`ceiling.probability_null` の search・round・tolerance)を変える
- `results/power_sim/ceiling/*/frames/` を `git add` する。`git add -A` を使わない
- C の採否・F8 の解釈を書く / `05_STATISTICS.md` の書き換え

## 未解決 / 人間の承認待ち

- probnull の生成と評価の起動 / C の採否(評価の後・別の ADR)/ 確率の尺度とロジットの TOST の Δ(凍結前)/ PLAN-045(R3)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2・R5
