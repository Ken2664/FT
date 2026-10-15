# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-15(その167)/ 直前セッションの役割: (指定なし。実装・解析の再検討 = CRITIC 相当)
直前セッションが終了した理由: context-guard(約 240k)+ 区切り(再検討の所見を `logs/` に書いて commit した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — 次は所見(とくに R1・R3)を判断材料の表にする「設計判断・統計」の行(`10_CONTEXT_POLICY.md` §7)。決めるのは人間

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**人間の指示を待つ。**候補は、`logs/REVIEW-2026-10-15-implementation-analysis.md` の R1(天井)・R2(T2 のシードの二極化)・R3(既知性と可換性)について、
人間が扱いを決めるための**判断材料の表**(選択肢・利点・代償・推奨。ADR-097 決定6)を作り、`AskUserQuestion` で推奨を先頭に聞くこと。
決まったら ADR に提案者と採択者を分けて書く。**run3 の起動は R1・R2 の扱いが決まってからのほうが安い**(人間の判断)。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- 所見の本体は `logs/REVIEW-2026-10-15-implementation-analysis.md`(重大度順・R1〜R12・§C の C1〜C9)。詳細は `logs/REVIEW-2026-10-15-eval.md`・`logs/REVIEW-2026-10-15-datagen.md`、再現は `logs/review-2026-10-15-probes/`
- R1 の再現: パイロットの表(`results/s2_item_pilot/frame.csv`、625 step、2 シード)に床の式を当てると、`glmer` は収束せず、交互作用の係数は ±22・SE 約 3,463(`ceiling_check.R`)。**2 シードの例示であり、主張には使わない(ADR-106)**
- R3 は組合せ論的な事実(`data/generated/ft/exp_phase1_main_p2/manifest.json` と `data/generated/battery/main/items.jsonl`)
- `pytest code/tests -q -k 'not smoke'` = 2511 passed(2026-10-15)

## 触ってよいファイル / 読むべき範囲

- `logs/REVIEW-2026-10-15-implementation-analysis.md`(全文。短い)
- `logs/OPEN-ITEMS.md` の D9 の行と「その167」の行(`grep -n 'D9\|その167'`)
- `plans/PLAN-034-power-t1t2.md` の D9・§7 罠6、`Documents/05_STATISTICS.md` §2 の弱点欄(`grep -n` → `sed -n`)

## やってはいけないこと

- 所見を解釈して「主要検定は使えない」などと結論すること(`CLAUDE.md` §8)。案は出してよい
- `code/`・config・事前登録の文書を、人間の決定の前に直すこと
- R1 の数値(パイロット)を主張・効果量の値として使うこと

## 未解決 / 人間の承認待ち

- R1〜R4 の扱い(`logs/OPEN-ITEMS.md`「その167」の行)/ PLAN-043 §12 の判断 6 件 → run3 / push と G2-1 承認 → S4 / S5 凍結の場の項目(`STATE.md`「次のアクション」)
