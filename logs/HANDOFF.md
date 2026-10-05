# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-05(その148)/ 直前セッションの役割: PLANNER 補助(門が閉じた結果の判断材料)
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 135k トークンで警告)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — §3.2 の見直しの PLAN の起草・判断材料の表は設計判断・統計(`Documents/10_CONTEXT_POLICY.md` §7)。夜用タスクの削除の記録だけなら Sonnet。**モデルを選ぶのは人間**

---

あなたは **PLANNER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## 状態: 検出力分析の 1 段目の誤指定の門が閉じた。判断材料(探索の分解)はファイルにある

- **門**(ADR-123 決定6)[run:20261004_120002_power_sim_t1t2]: `n_item` 80・100 反復で `tau` 0.25 → 14/100(下端 0.0787)・0.5 → 15/100(0.0865)→ `stopped_at_gate`。P1 / P1⁻ / P0 は未実行。**回し直さない**
- **探索の分解**(`results/power_sim/run1/exploratory/by_reduction.json`。commit `9ac2ab7`。**門の判定は変えない**): `drop_item` まで縮退した当てはめは `tau` 0 でも 5/16 棄却。除くと `tau` 0.25 → 7/87(下端 0.033)・0.5 → 10/92(下端 0.053)。`tau` ≥ 0.75 は縮退なしでも 15/39・20/45・47/68 棄却。数値と段ごとの表は CHANGELOG その148
- **エージェントの読み(案。人間は未確定)**: 膨らみは (a) seed × task × coverage の項がモデルに無いこと と (b) 縮退カスケードの最後の段(item を落とす)の重なり
- **人間に示した推奨(未決)**: §3.2 の見直しの別 PLAN に進む(見る対象 = 項の追加(例 `(1 | seed:task:coverage)`)・縮退の最後の段)/ 夜用タスクは `register_tasks.ps1 -Unregister`(人間の端末)

## このセッションでやること(人間の指示が先)

- 人間が「進む」と決めたら: `plans/PLAN-0XX-*.md` に §3.2 の見直しの PLAN を起草する(候補と判断材料の表を先に示す。ADR-097 決定6。値・採否は人間)。判断材料に使ってよい数値は `power_sim_summary.json` と `exploratory/by_reduction.json` だけ
- 決まっていなければ: 判断材料の表を示して `AskUserQuestion`(推奨付き。記憶 `recommend-before-choice`)

## 読むべき範囲

- `Documents/05_STATISTICS.md` §3.2(189〜230 行付近)・§6.8 の「★2026-10-04 差し替え」(`grep -n '差し替え'`)/ `code/analysis/power_sim_fit.R` の `RANDOM_BY_LEVEL`(縮退順序 = ADR-065 決定2)/ ADR-059・064・065・114・123

## やってはいけないこと

- 本実行を回し直さない・起動しない・タスクを登録 / 削除しない。Bash の `run_in_background` は使わない
- ADR-111〜123 を覆さない。門の閾値 0.075・格子・`s2_*` を変えない。探索の分解で門の判定を覆さない
- 本物の `configs/power_sim.yaml` を `power_sim.run` / `main` に渡すテストを書かない
- `.md`・`.py`・`.yaml`・`.R` は LF。`.ps1` は ASCII のみ。日本語を含む置換は Python スクリプトで(アンカー文字列は短く取る)
- STATE.md は約 60 KB・370 行。足すときは同じだけアーカイブへ移す
- 未追跡の `results/power_sim/run1/config_resolved.json`・`git_sha.txt`・`misspecification/manifest_*` は前のセッションから残るもの。commit するかは人間に聞く(勝手に足さない)

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- **門が閉じた後の扱い**(§3.2 の見直しの PLAN に進むか)・夜用タスク 2 本の扱い
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル / S4 の T1c の順 / worktree の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
