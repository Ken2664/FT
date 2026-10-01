# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-01(その128)/ 直前セッションの役割: CRITIC(学術的価値の検討レポート)
直前セッションが終了した理由: コンテキスト超過(hook context-guard。約 294k トークン)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **(α) レポートの案を ADR・文書に落とすなら Opus**(設計判断・統計。`10_CONTEXT_POLICY.md` §7)/ **(β) R8 の実行なら Sonnet**(RUNNER)/ **(γ) 検出力分析の PLAN なら Opus**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**人間の最初の指示が先**です。指示が無ければ (α)(β)(γ) のどれにするかを人間に聞くこと。

## いまの状態(ファイルに反映済み: `STATE.md`・`logs/CHANGELOG.md` その128・`logs/OPEN-ITEMS.md`)

- 価値レビュー `Documents/reviews/2026-10-01/report.md`(本文)・`papers_list.md`(159 件)を書いた(commit `cd7fdc3`)。**すべて案。採否は人間**
- 要点: MisFT(Chen et al., Findings EMNLP 2025。arXiv:2503.16401)が a+b+k の FT → 文章題への転移を報告済み(原文で確認)。新規性は既知性・漏れ・`p2d`/`arb`/`x2`・4 値分解・シード単位に残る / 「平行 ⇒ 共有」は単独では言えない(尺度依存・解離の論理)
- 主要検定の設計(T1 × T2・df = 2・E1)は ADR-113 のまま。変えていない

## このセッションでやること(人間が選ぶ。1 つだけ)

- **(α)** 人間が選んだレポート §5 の案を、凍結前の ADR と該当文書(`02_RELATED_WORK.md`・`05_STATISTICS.md`・`09_PAPER_PLAN.md` など)に落とす PLAN を書く。**判断材料の表を先に見せる**(AGENTS.md PLANNER 節)
- **(β)** R8(人間の push と G2-1 承認の後)/ **(γ)** 検出力分析の PLAN —— 詳細は `git show 95cf5b8:logs/HANDOFF.md`(その127 版)

## 読むべき範囲

- `Documents/reviews/2026-10-01/report.md` は §0(要旨)・§4(判定表)・§5(案)を `grep -n '^## '` で引いてから読む。全文 cat しない
- 文献の候補一覧は `logs/SCOUT-2026-10-01-value-{A..E}.md`(大きい。grep で)

## やってはいけないこと

- `papers_list.md` の文献を、人間の原典確認(`CLAUDE.md` §3)前に `refs.bib` へ `verified` 付きで入れない
- パイロットの数値(`pool_id: pilot`)を効果量・主張として書かない

## 未解決 / 人間の承認待ち

- レポート §5 の案 A〜G の採否(`logs/OPEN-ITEMS.md` の行)/ E1 の TOST 境界の値 / ★T2 の形の変化と #5 / R8 の push と G2-1 承認 / `CLAUDE.md` を 200 行へ
