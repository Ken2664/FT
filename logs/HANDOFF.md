# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その105)/ 直前セッションの役割: CRITIC
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(PLAN-032 I4 の CRITIC のレビューを `logs/CRITIQUE.md` に書いた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は人間に判断を諮り ADR を書く(`Documents/10_CONTEXT_POLICY.md` §7 の表の「設計判断、統計計画、結果の解釈、事前登録の文言 …」の行。§8.1 は tag の対象 = 事前登録の文言)。**人間が自分で `logs/CRITIQUE.md` を読んで決めるなら、このセッションは要らない**(決めた結果を ADR にする PLANNER だけでよい)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP は要らない**(GPU は使わない)。

## このセッションでやること(1つだけ)

**PLAN-032 の凍結 tag の前に人間が決めることを諮り、答えを ADR-108 に記録する。**諮るのは次の 2 束:

1. `logs/CRITIQUE.md`「その105」の **C105-1〜8**(CRITIC の指摘。各項目に「誰が決めるか」がある)
2. `plans/PLAN-032` §11 の下の注「**実装の読み 1〜11**」(とくに 6 = 信頼区間の計算法。C105-4 と同じ論点)

手順:
- 各項目について、**選択肢と推奨とその理由をチャットで先に示してから** `AskUserQuestion` で聞く(memory「Recommend before choice」・ADR-097 決定6)。1 回 4 問までなので束ねる。依存: C105-3(A-d の役割)と読み 8 は同じ論点 / C105-4 と読み 6 は同じ論点 / C105-2 の adapter の条件は R9(段4 で同じ線を新ベースの B に当てる)と絡む
- 答えを `logs/DECISIONS.md` の **ADR-108** に書く(**提案者と採択者を分けて**。ADR-107 の書式)。§8.1 の文面を直すと決まったら、ADR の後に `plans/PLAN-032` §8.1 を直す(tag の前なので ADR があれば直せる。`§8.1` 冒頭の注記)
- コードやテストの変更(C105-1・C105-2・C105-6〜8 のうち採ったもの)は**書かない**。次の IMPLEMENTER に回す(HANDOFF に書く)

## 直前セッションで確定したこと

- CRITIC のレビューは `logs/CRITIQUE.md`(新規ファイル)の「その105」。**§8.1 R2〜R5 の算術と表の誤り、判定を黙って変える経路は見つからなかった**。指摘は中 3(C105-1 テストの穴 / C105-2 R1 の前提を判定の時点で照合しない / C105-3 §8.1 の A-d の文面の食い違い)・低〜中 1(C105-4 信頼区間が幅 0 に潰れうる)・低 3・nit 1
- `pytest code/tests/test_sharpness_fit.py code/tests/test_diag_sharpness.py -q` → 93 passed(その105)。コードは直していない
- dry-run の件数 102,892(組合せの件数。その104)は変わらない

## 触ってよいファイル / 読むべき範囲

- 書く: `logs/DECISIONS.md`(ADR-108 を追記)/ `plans/PLAN-032`(§8.1 は ADR で決まったときだけ・ヘッダ・§10・§11)/ `logs/OPEN-ITEMS.md`(「PLAN-032 の凍結 tag と G2-1」行)/ `STATE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: `logs/CRITIQUE.md`(全文。短い)/ `plans/PLAN-032` §8.1(`grep -n '### 8.1' plans/PLAN-032-sharpness-diagnostic.md`)・§11 の注 / ADR-107(`grep -n '^## ADR-107' logs/DECISIONS.md`)
- **編集しない**: コード・config・テンプレート・テスト

## やってはいけないこと

- **tag を打たない・pod を起動しない・GPU を使わない**。パイロットのアダプタの T1b・T3 を回さない(凍結 tag の後だけ)
- **合否線(0.088)・R2〜R5 の規則の値をエージェントから動かす提案をしない**(ADR-107 で人間が決めた)。C105 の論点は「止める条件・記述の行・文面のそろえ方・テスト」であって値ではない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(scratchpad に書いてから `cat >>`。`logs/DECISIONS.md` はその103 に heredoc で失敗した実例がある)

## 未解決 / 人間の承認待ち

- **C105-1〜8 と実装の読み 1〜11 の採否 → PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md` の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
