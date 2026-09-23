# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その76)/ 直前セッションの役割: CRITIC (Opus 5.5)
直前セッションが終了した理由: コンテキスト超過(context-guard 警告)。監査は完了している

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。その72〜75 は Sonnet が Opus を名乗って書いていた)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**`logs/AUDIT-2026-09-24-post-order6b.md` §5 の 7 点を人間に選択式で諮り、回答を ADR(新規)と打ち消し線で反映する。**
完了条件: 7 点それぞれに人間の回答があり、`logs/DECISIONS.md` に ADR が 1 本以上足され、該当文書(ADR-090〜094 の提案者欄・
ADR-094 / `Documents/05_STATISTICS.md` §6.7 / `plans/PLAN-019` §10.13.5 の `n_item` の文言・PLAN-028 §8 P3 など)に
打ち消し線 + 理由 + 日付が入り、`logs/OPEN-ITEMS.md` の「★その76 監査」行が閉じている。

## 直前セッションで確定したこと

- その72〜75 の commit trailer は Claude Sonnet 5、その69〜71 は Claude Opus 5(`git log --format=%B`)
- その71 のコード(規則 C・`rescore_run.py`)は正しい。`pytest code/tests -q` = 1580 passed(2026-09-24)
- `dgp.n_item` は (タスク型 × 被覆) セルあたりの項目数(`code/analysis/power_sim.py:233`)。`M*` = 999 を入れる量ではない
- R8 の記述は `results/r8_fit_order6b/r8_fit.txt` にある(run `20260922_122247_order6b_r8` / `…124632_order6b_s_preamble` / `…125131_order6b_s_d`)。**解釈はしていない**

## 触ってよいファイル / 読むべき範囲

- `logs/AUDIT-2026-09-24-post-order6b.md`(全文。短い)
- `logs/DECISIONS.md` の ADR-090〜094(`grep -n '^## ADR-09' logs/DECISIONS.md` → `sed -n`)
- `plans/PLAN-028-prestage-ft.md` §3.3・§8 / `plans/PLAN-019-validity-decisions.md` 1557〜1580 行 / `Documents/05_STATISTICS.md` 1072〜1090 行

## やってはいけないこと

- **`dgp.n_item` に 999 を入れない**(旧 STATE の指示は誤り)
- ADR の本文を黙って書き換えない。訂正は打ち消し線 + 理由 + 日付(`CLAUDE.md` §2)
- R8 の記述を解釈して「分岐は B だ」等と書かない(`CLAUDE.md` §8)。表を見せて人間が決める
- PLAN-029 の実装・GPU に進まない(監査 §5 の B5・B8 が先)

## 未解決 / 人間の承認待ち

- 監査 §5 の 7 点(提案者欄の訂正 / `n_item` の出どころ / ★F104-c の維持 / ADR-093 P3 / ADR-090 の維持 / 前段 FT の基準の事前凍結 / `runs/preflight/` の `.gitignore` の追認)
- 変わらず: ★F114 の実行先(`n_item` の後)/ `cost.txt` / 停止中ポッド 8 本の terminate / ★`θ` の根拠 / Phase 1 の GPU 構成 / N5
