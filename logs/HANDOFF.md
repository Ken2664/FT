# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-08(その162)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 192k)。区切り = PLAN-043 草案の commit(`61c839f`)の後、人間が「Q1〜Q6 を AskUserQuestion で順に聞いて」と指示した時点
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — 当てはめの手順・門の判定・乱数の値という統計の設計判断の材料を示して ADR を書く(`10_CONTEXT_POLICY.md` §7 の「設計判断・統計」の行)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**`plans/PLAN-043-adr128-fit-rescue-and-gates.md` §4 の Q1〜Q6 を、`AskUserQuestion` で推奨を先頭に(理由付きで)順に人間に聞く**(人間が 2026-10-08 にそう指示した)。
§4 の表がそのまま判断材料の表である(ADR-097 決定6)。回答を受けたら:
- **ADR-129** を `logs/DECISIONS.md` に書く(提案 エージェント (PLANNER, Opus 5.5) / 採択 人間。ADR-128 と同じ形。結果を見る前の決定か後かをリスク欄に)
- PLAN-043 §11 の記入欄・ステータス(`草案` → `採択`)・§12 の実行ログ
- `logs/OPEN-ITEMS.md`(PLAN-042 の行の末尾に追記)/ `STATE.md` / `logs/CHANGELOG.md` → commit
- **実装はしない**(I1〜I10 は次の IMPLEMENTER)

Q の要約(詳細は §4。`sed -n` で読む):
- Q1 `allFit`: 推奨 = PLAN-042 D1 と同じ 5 最適化を名前で列挙・`start_from_mle = FALSE`。Q1' 床の土台の `glmer` が例外 → 推奨 = 救わずに失敗
- Q2 失敗した反復の記述の p 値: 推奨 = 残す・門に使わない
- Q3 実行可能性の門: 推奨 = 全シート・全点(誤指定の 3 枚はまとめて、以降はシートごと)
- Q4 `rng_seed`: 推奨 = PLAN-043 を採った日付の YYYYMMDD(採った日が 2026-10-08 以外ならその日付)
- Q5 PB の計時: 推奨 = 手書きの simulate → refit・合成の 4 表 × B 20・秒数だけ
- Q6 起動の手順の確認
- `AskUserQuestion` は 1 回 4 問まで。Q1〜Q4 → Q5・Q6(と Q1')の 2 回に分けてよい

## 直前セッションで確定したこと

- PLAN-043 草案(commit `61c839f`)。I1〜I10・§3.1 の打ち消し線の表・§4 の Q1〜Q6・§5 の判断材料
- 記述 [run:20261005_120003_power_sim_t1t2]: 診断の `r_out/` 176 件で床の当てはめの例外 0・`allFit` の 5 最適化(352 回ずつ)の例外 0
- この機械の R 4.6.1 に `pbkrtest`・`dfoptim`・`optimx` は無い(2026-10-08 確認)
- 実行可能性の門(CP95 下端 > 0.10)は 100・300・1000 反復で失敗 17・42・120 回以上で閉じる(算術)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-043-adr128-fit-rescue-and-gates.md` §4(`grep -n '^### Q' ` で位置を取る)・§11・§12
- `logs/DECISIONS.md` 7738〜7780(ADR-128。ADR-129 の形の手本)
- 書いてよい: `logs/DECISIONS.md`(ADR-129 の追記)・`plans/PLAN-043-*.md`・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/CHANGELOG.md`

## やってはいけないこと

- 推奨を人間の代わりに決める / 回答の前に ADR を書く
- `configs/power_sim.yaml`・`code/`・文書本文(05_STATISTICS・PLAN-040)・古い ADR の本文を変える(実装の段)
- run2 の 100 反復で新しい規則の門を判定する / run3 や PB の計時を起動する

## 未解決 / 人間の承認待ち

- PLAN-043 §4 の Q1〜Q6(このセッションで聞く)
- push(`01cf60f` 以降の main)と G2-1 承認 → S4
- 夜用タスクに run2 の登録が残っているか(未確認。無効化は人間)
- PB の反復数・食い違ったときの扱いは S5 / 特異な分散成分(32 件)は未確認 / `run2/misspecification_seed_per_cell/frames/` の残骸 46 本・未追跡の `.claude/commands/` は人間
