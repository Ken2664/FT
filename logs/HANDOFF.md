# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-02(その192)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN 完了(PLAN-048 を起草し ADR-138 で採択 `d34cf68`)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 実装(`10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)。統計の判断が出たら止めて PLANNER(Opus)へ

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。
開始時に skill `code-style` を読むこと。

## このセッションでやること(1つだけ)

**`plans/PLAN-048-primary-analysis-script.md` §5 の I1〜I10 を実装する**: `configs/primary.yaml`(新規)・`code/analysis/primary.py`(新規)・`code/tests/` のテスト。完了条件は PLAN-048 §9 の 2〜5 項目め(`pytest code/tests -q` が通る / `python -m code.analysis.primary --simulate` が P0・P1 で最後まで走り `report.md` が ADR-138 決定6 の表の形 / `--shuffle-labels --seed 0` が走る / `OPEN-ITEMS.md` の `primary.py` の行を更新)。**結果の読みは書かない**(人間)。コンテキストが重ければ I1〜I5 と I6〜I10 で切ってよい

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `d34cf68`: ADR-138(PLAN-048 Q1〜Q6、人間が 6 問とも推奨 (a))。範囲は主要検定の本体だけ(W1〜W8)/ 当てはめは `power_sim_fit.R` を**変えずに** `power_sim.write_fit_manifest`・`run_fits` で呼び、設定は `configs/power_sim.yaml` の `fit` 節を読む / 解析門の閾値(N5)・TOST の Δ は `null`、実データでは止まる / `--shuffle-labels` は被覆の水準の中で項目単位に `task` を入れ替える / `--simulate` は `draw_frame` で P0・P1 / 判定を p 値より左に置く固定の表
- `code/` は不変。数値は出していない

## 触ってよいファイル / 読むべき範囲

- PLAN-048 は全部読む(短い。§2 前提・§3 事実・§5 手順・§6 罠)。ADR-138 は `grep -n '^## ADR-138' logs/DECISIONS.md`
- 口: `code/analysis/power_sim.py` の `draw_frame`・`write_fit_manifest`・`run_fits`・`tost_spec`・`equivalence_margin` / `code/analysis/ceiling.py` / `code/analysis/frame.py` の `COLUMNS`・`gate_id_rates` / `code/analysis/power_sim_fit.R` の `run_one`(入力の列)/ `configs/power_sim.yaml` の `fit` 節
- 書いてよい: `configs/primary.yaml`・`code/analysis/primary.py`・`code/tests/test_primary*.py`・PLAN-048 §9・§11・`logs/OPEN-ITEMS.md` の該当行・記録文書
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`(`power_sim.py` は 3002 行)

## やってはいけないこと

- `power_sim_fit.R`・`configs/power_sim.yaml`・`ceiling.py` の規則の中身・`rng_seed` 20261008・門の値を変える(ADR-138 決定2・ADR-137)
- 解析門の閾値・TOST の Δ に値を入れる / 仮の値を置く(ADR-138 決定3。人間が凍結の場で決める)
- PLAN-048 で外したもの(リンク 3 本・第 2 の尺度・ADR-060 のベイズ・#5b・`id` の二重露出)を実装する
- 実データを読む(`results/` に `p2` の実データは無い)
- `git add -A`(未追跡の大きい結果がある)。コミットはファイルを名指しする

## 未解決 / 人間の承認待ち

- 実装中に PLAN に書いていない統計の判断が出たら(例: Q4 の `task` と `template` の対応の崩れの扱い・入れ替えの回帰の回数)、止めて記録し PLANNER へ
- 順6 の測り直し(PLAN-045 I7)の起動 / `01cf60f` 以降の push と G2-1 承認 → S4 / N5 の閾値と門の順・TOST の Δ / 第 2 の尺度の手続き(S5)/ `id` の二重露出の感度解析 / R5(組 199)/ PLAN-043 §12 の判断 6 件 / REVIEW の R4 以下・C1/C2
