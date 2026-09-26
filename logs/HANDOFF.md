# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その104)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(PLAN-032 §5 の I1〜I4・I6 を実装し、dry-run と data_checks を通した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は CRITIC が I4(Δ₂ と判定表)の diff を §8.1 と突き合わせる(`Documents/10_CONTEXT_POLICY.md` §7 の表の「設計判断、統計計画、結果の解釈、事前登録の文言、CRITIC …」の行。**ADR-101 決定5: 統計に触れる diff は CRITIC(Opus)か人間が見る**)。**書いた本人(Opus 5.5 の IMPLEMENTER)が見ても代わりにならない**。人間が自分で見るならこのセッションは要らない。**人間が覆せる**

---

あなたは CRITIC です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP は要らない**(GPU は使わない)。

## このセッションでやること(1つだけ)

**`code/analysis/sharpness_fit.py`(PLAN-032 I4)が `plans/PLAN-032` §8.1 の R2〜R7 を取り違えずに実装しているかを敵対的にレビューし、指摘を `logs/CRITIQUE.md` に追記する(追記のみ・修正はしない)。**「問題なし」で終わらせず、最低 3 つは疑わしい点を挙げる。

1. 読む: `plans/PLAN-032` **§8.1(R1〜R9。仕様の正本)** と **§11 の下の注「実装の読み 1〜11」**。ADR-107 は `grep -n '^## ADR-107' logs/DECISIONS.md` から
2. 見る diff: `git show <その104 の commit> -- code/analysis/sharpness_fit.py code/eval/run.py code/data_gen/sweep_pool.py`(`git log --oneline -3` で commit を引く)。テストは `code/tests/test_sharpness_fit.py`・`test_diag_sharpness.py`
3. とくに確かめること:
   - **R2**: Δ₂ の 4 通り (gt 0, +1 / lt +1, +2) と `θ − 2`・`y`(`r8_fit.aligned_response`)・`P̂` の分母(160 件)
   - **R3**: 点推定 ≥ 0.088(有理数で比べている = 実装の読み 7)・3 セルすべて・線を当てる腕(A・B・B-d。A-d は記述だけ = 読み 8)
   - **R4**: 2 × 2 を T1b と T3 に別々に・「A 届かない・B 届く」だけ異常 / **R5**: T1b が前段 FT のときだけ
   - **R6**: 信頼区間の計算法(**読み 6。§8.1 に定めが無い**)・近接同点(`≤ 0.25` を同点に数える)・質量・トークン数(chat template 込み = 読み 9)
   - **R7**: 止める条件が判定の**前**に掛かっているか。R7 の外に足した止める条件(読み 10)が判定を黙って変えないか
   - T < 1 の除外(読み 2・3)が Δ₂ の水準に掛からないこと、R8・S の項目と manifest が変わっていないこと
4. `pytest code/tests/test_sharpness_fit.py code/tests/test_diag_sharpness.py -q` を回してよい(GPU 0)。**判定表の数値は実験結果ではない**(採点器を差し替えたテストの値)

## 直前セッションで確定したこと

- I1〜I4・I6 を実装した(その104)。dry-run(**組合せの件数であって実験結果ではない**): B・A 各 34,322 / B-d・A-d 各 17,124 = **102,892 件**(除外の前の算定 109,440 から T < 1 の 2,158 件(θ ≤ −5 だけ)を腕ごとに除いた)。preflight の data_checks は config 5 本とも 7 件 PASS
- 実装の読み 1〜11 は `plans/PLAN-032` §11 の下の注。**ADR にはしていない**(人間が凍結 tag の前に確かめる = `logs/OPEN-ITEMS.md` の「PLAN-032 の凍結 tag と G2-1」行)

## 触ってよいファイル / 読むべき範囲

- 書く: **`logs/CRITIQUE.md`(追記のみ)** / `STATE.md`(引き継ぎの節)/ `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: `plans/PLAN-032` §8.1・§11 / `code/analysis/sharpness_fit.py` / `code/analysis/r8_fit.py`(再利用した関数だけ `grep -n`)/ 上の 2 つのテスト
- **編集しない**: コード・config・テンプレート・テスト・`plans/PLAN-032`・`logs/DECISIONS.md`(**修正は CRITIC の仕事ではない**。指摘を読んだ人間が IMPLEMENTER に回す)

## やってはいけないこと

- **tag を打たない・pod を起動しない・GPU を使わない**。パイロットのアダプタの T1b・T3 を回さない(凍結 tag の後だけ)
- 指摘の中で合否線・規則の値そのものを変える提案をしない(§8.1 は ADR-107 で人間が決めた。値を動かすなら新しい ADR と人間)
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(ファイルに書いてから `cat >>`)

## 未解決 / 人間の承認待ち

- **実装の読み 1〜11 の確認(とくに 6)→ PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md` の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
