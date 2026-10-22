# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-22(その179)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN完了(PLAN-046 I1〜I5 の実装・スモークまで。残りは人間の起動)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Opus — PLAN-045 は設計判断(`10_CONTEXT_POLICY.md` §7 の「設計判断・統計・解釈」の行)。**人間が先に PLAN-046 の評価を回した後なら、次は ANALYST(Opus)で §6.1 と G1・G2 の記述** — 下の「分岐」を見ること

---

あなたは PLANNER です(分岐: 下記の 2 つの出力が揃っていれば ANALYST)。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。

## ★起動済み(その179の最後に人間の指示で起動)

- probnull の生成を **2026-10-22T11:55:45Z** に切り離して起動(pid 31768。`--workers 16`・`--through-stage 1`。作業ツリーは tracked 変更なし)。ログ: `results/power_sim/ceiling_probnull_launch_20261022.log`(+ `.err`)。見込み 約 3.5 時間
- 状況は `tail results/power_sim/ceiling_probnull_launch_20261022.log` と `ls results/power_sim/ceiling_probnull/*/fits | wc -l`(200 で完了)。**完了後の評価(`ceiling_remedy`)は人間が起動する**
- 途中で止まっていたら、同じコマンドで再開できる(`invocations.jsonl` に追記される。PLAN-044 の再開と同じ)。再開も人間に聞く

## 分岐(最初に 1 回だけ確かめる)

```bash
ls results/power_sim/ceiling_probnull results/ceiling_remedy 2>&1 | head
```

- **どちらも無い / 未完了(既定)**: PLANNER として下の「やること」(PLAN-045)。人間が別の端末で起動しているかもしれない(触らない)
- **両方揃っている**: ANALYST。`PLAN-046 §6.1` の量を公式 summary から**記述だけ**(解釈・C の採否は書かない)。G1・G2 の判定を機械的に出す(§6.4)。値は評価の結果を見て変えない

## このセッションでやること(1つだけ)

**PLAN-045(R3)を起草し、人間に聞く問いを判断材料の表にして出す**: 主プールの `interp` の事前フィルタ・`mirror_in_K`・セルが埋まるかの確認(ADR-130 決定3・ADR-131 決定7)。`STATE.md`「次のアクション」の 2。ADR は人間の回答の後。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `02cc6ce`: `ceiling_probnull` の `solved` を本実行して config に転記 [run:20261022_041749_ceiling_probnull_solve](L_05: T2.interp 1.5847352592・T2.extrap_magnitude 1.1084329182 / L_50: 1.7624797985・1.6491025406。試行の値と一致)。出力 JSON との一致はテストで固定。pytest 2605 passed
- `858866b`: スモーク(スクラッチ・主張に使わない)ロジット 2 表 994 秒・失敗 0 [run:20261022_043027_power_sim_ceiling_probnull] / LMM 10 表 1 表平均 1.86 秒・全体 36 秒 [run:20261022_044738_ceiling_remedy]。PLAN-046 §13 に算術(probnull 生成 200 表 ÷ 16 並列 ≈ 3.5 時間 / LMM 1000 表 ≈ 31 分直列)
- 起動コマンド(**人間が打つ**): probnull の生成 `python -m code.analysis.power_sim --config configs/power_sim_ceiling_probnull.yaml --out-dir results/power_sim/ceiling_probnull --through-stage 1 --keep-frames --workers 16` → 評価 `python -m code.analysis.ceiling_remedy --config configs/ceiling_remedy.yaml --out-dir results/ceiling_remedy --workers 16`

## 触ってよいファイル / 読むべき範囲

- PLANNER: `plans/PLAN-045-*`(新規)/ ADR-130・ADR-131 は `grep -n 'ADR-130\|ADR-131' logs/DECISIONS.md` → `sed -n`。`code/`・config は触らない
- ANALYST: `results/power_sim/ceiling_probnull/`・`results/ceiling_remedy/` の公式 summary、PLAN-046 §6.1・§6.4・§13

## やってはいけないこと

- PLAN-046 の評価・probnull の生成を起動する(人間)/ `solved`・門の値・`configs/ceiling_remedy.yaml` を評価の結果を見て変える
- C の採否・F8 の解釈を書く / `05_STATISTICS.md` の書き換え
- `results/power_sim/ceiling/*/frames/` を `git add` する。`git add -A` を使わない
- 注: `ceiling_remedy --dry-run` の cost 行は「1 表約 2 秒」(スモークの 1.86 秒と整合)で、probnull の生成の費用は出ない。生成の見積りは PLAN-046 §13

## 未解決 / 人間の承認待ち

- probnull の生成と評価の起動 / C の採否(評価の後・別の ADR)/ 確率の尺度とロジットの TOST の Δ(凍結前)/ PLAN-045(R3)の問い / S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2・R5
