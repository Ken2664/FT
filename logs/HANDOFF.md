# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-01(その125)/ 直前セッションの役割: PLANNER(人間が Phase 1 の判定表を読む場に付き合い、ADR-111 を起草した)
直前セッションが終了した理由: **ADR-111 で段2(PLAN-032)の読みが決まり、区切りがついた**(コンテキストは超過していない)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **(α) H4-3 の PLAN なら Opus**(主要検定の文言・統計の前提 = 設計判断・統計の行。`Documents/10_CONTEXT_POLICY.md` §7)/ **(β) R8 の実行なら Sonnet**(RUNNER)。**どちらをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**人間の最初の指示が先**です。指示が無ければ、下の「いまの状態」を要約し、(α)(β) のどちらにするかを人間に聞いてください(判断材料と推奨を付ける。memory「Recommend before choice」)。

## いまの状態(すべてファイルに反映済み: `STATE.md`・`logs/CHANGELOG.md` その125・`logs/DECISIONS.md` ADR-111)

- **Phase 1(段2 の診断 = 鋭さ)は終わり、人間が読んだ**(ADR-111。提案 エージェント (Opus 5.5)・採択 人間。4 問とも推奨):
  - 決定1: 判定表 `results/diag_sharpness/` を受け入れた(先頭の sha = tag `preregister-diag-sharpness` の commit `102c2d5`)
  - 決定2: **T1b・T3 とも分岐 (a)**。前段 FT(③-ii)・③-iii はしない。**主要検定を T1 × T2(df = 2)にする**(ADR-097 決定4 (a))。T1b・T3 は測り続けるが探索的。**文書(`CLAUDE.md` §0・`Documents/00_OVERVIEW.md` §1・`Documents/05_STATISTICS.md` §2 ほか)はまだ df = 6 のまま** = H4-3
  - 決定3: **R8**(パイロットのアダプタ 10 本の固定オフセットの T1b・T3。`configs/exp_pilot_ft_cmp_*`)は ADR-107 決定7 どおり回す方針。結果は探索的
- **push は依然未**(`origin/main` = `102c2d5`。その118 の `01cf60f` 以降が未 push。**push は人間**。ADR-110 決定4)
- **稼働中の pod は無い**(5 本とも `EXITED`。terminate は人間。ボリューム `r963j7swke` は残す。`predictions/` とモデルのキャッシュがある)

## 次の作業の候補(どちらを先にするかは人間)

- **(α) H4-3 の PLAN の起草**(PLANNER / Opus): 主要検定を T1 × T2 にする文書修正の範囲(`grep -rn 'df = 6\|df=6\|task:coverage' CLAUDE.md Documents/ plans/` で洗う)と文言の案。★F114(検出力分析)・`n_item` のタスク型ごとの実装(ADR-095 決定2)・E1 の TOST 境界の前提がどう変わるかも並べる(PLAN-030 §6 罠5)。**PLAN → 人間のレビュー → 文書修正**(`CLAUDE.md` §4)。事前登録の予測を実験後に変える話ではない(本体は未凍結。ADR-097 の文脈と同じ確認を PLAN に書く)
- **(β) R8 の実行**(RUNNER / Sonnet): 人間が push → RUNNER が見積り(4 腕の実測 0.007 s/項目は掃引の経路。R8 は固定オフセットの経路で速さが違う。順6b の B0 などの `timing` から外挿)→ 人間が G2-1 承認 → `infra/RUNPOD.md` §4 の順。`plans/PLAN-032` §8.2 の「I5 は 4 腕の後に、I5 の config の入った commit を checkout して回す」

## やってはいけないこと

- **ADR-111 を覆さない・判定表を読み直して別の結論を書かない**(人間の採択)。「律速は合成」を claim として確定させない(ADR-111 決定2 の注)
- **tag を打たない・push しない・pod を起動しない**(人間の操作・承認が先)
- **`configs/`・`code/` を (α) の中で直さない**。文書修正も PLAN のレビューの後
- **この機は Windows**: `.md`・`.py` は LF 固定(Python で書くときは `newline="\n"`)。GNU `tar` は `--force-local`。長い日本語は `Write` でスクラッチパッドに置いてから Python で入れる
- STATE.md は 371 行・59.9 KB(目標 60 KB の直下)。**次に足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- **★H4-3**(主要検定の文書修正の文言)/ **★R8 の push と G2-1 承認**(どちらも その125 新設)
- 旧 4 本と `9matkiq0jozcgm` の terminate / その122 の採択の ADR(未記入)/ ★T2 の形の変化と #5 の扱い・★`train_size` 掃引の意味・★rank の格子と学習率の揃え方(凍結前)
