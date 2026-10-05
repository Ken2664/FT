# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-05(その149)/ 直前セッションの役割: PLANNER(§3.2 の見直しの PLAN 草案)
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 187k トークンで警告)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — PLAN-041 の D1〜D6 の聴取と ADR は設計判断・統計(`Documents/10_CONTEXT_POLICY.md` §7)。**モデルを選ぶのは人間**

---

あなたは **PLANNER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本)。**人間の最初の指示が先**です。

## このセッションでやること(人間の指示が先)

- `plans/PLAN-041-primary-random-structure-review.md`(草案)の **§4 の表(D1〜D6・推奨と理由)と §3 の読み(案)を人間に示し**、`AskUserQuestion` で回答を取る(推奨付き。記憶 `recommend-before-choice`)。回答が出たら PLAN-041 §10 に記入し、ADR-124 を書く(提案 エージェント / 採択 人間。ADR-039 決定3)
- 実装(I1〜I7)は次のセッション(IMPLEMENTER)

## 直前セッションで確定したこと(ファイルにあるものだけ)

- 門の判定は閉じたまま [run:20261004_120002_power_sim_t1t2]。PLAN-041 の数値は `power_sim_summary.json`・`exploratory/by_reduction.json` と仮定値からの算術だけ
- 文献: `logs/SCOUT-2026-10-05-glmm-misspec.md`・`logs/papers_list-2026-10-05-glmm-misspec.md`(41 件。**全件 未検証**)。SCOUT の注意: C4 の直接の根拠はガウスの LMM だけ・[29][30][1] は C4 を限る側 / 収束の警告の偽陽性の査読論文は無い / LLM の LoRA のシード × 条件の文献は無い / Barr 2013 は「相関を先に落とし、検定する効果の傾きは残す」順を勧める(現行の ADR-065 の順と食い違いうる)

## 読むべき範囲

- PLAN-041 全体(短い)/ `Documents/05_STATISTICS.md` §3.2(189〜300 行付近)/ ADR-059・064・065・066・114・123(`grep -n '^## ADR-06[456]'`)

## やってはいけないこと

- run1 の回し直し・起動・タスクの登録 / 削除。Bash の `run_in_background` は使わない
- 門の閾値 0.075・判定点・格子・`s2_*` の変更。「`drop_item` を除いた率」で門を読み直すこと
- 未検証の文献を論文・事前登録の本文に書くこと
- `.md`・`.py`・`.yaml`・`.R` は LF。日本語を含む置換は Python で
- 未追跡の `results/power_sim/run1/config_resolved.json`・`git_sha.txt`・`misspecification/manifest_*` は commit するか人間に聞く

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- PLAN-041 の D1〜D6 / 夜用タスク 2 本の扱い / SCOUT 41 件の原典確認
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則(D2 と同じ場が安い)・天井のセル / S4・S5 / worktree の削除 / ★R8 の push と G2-1 承認 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate
