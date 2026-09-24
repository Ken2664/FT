# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その77)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: PLAN 完了(監査 §5 の 7 点への人間の回答を ADR-095・ADR-096 に反映し終えた)

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。その72〜75 は Sonnet が Opus を名乗って書いていた。ADR-095 決定1)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**ADR-096 決定1 の「前段 FT の前の診断」の PLAN を `plans/PLAN-030-<名前>.md` として起草する(草案。実装・GPU は 0)。**
人間の言葉: 「前段 FT の前に、小さな診断を 1 本入れる。具体的には足し算を含まない比較を T1b, T3 に対して確認することで、FT に意味があるのかを判断する。」
完了条件: PLAN に (1) 項目の作り方(T1b・T3 の文面から和を抜いた `x` 対 `t` の比較。値の範囲は本番プールの T3・T1b の比べる値と揃える)、
(2) 文面・プール(pilot 系か。主プールと非交差か)・run 数・GPU 見積り、(3) **「前段 FT に意味がある / ない」の判定の規則の案**
(エージェントは案だけ。値と採否は人間。GPU の前に tag で凍結する形)、(4) 既存のコード(`code/eval/battery/t3_comparison.py`・`r8_fit`・`gonogo`)で何が流用できるか、
が書かれ、`logs/OPEN-ITEMS.md` の「★前段 FT の前の診断」行から PLAN-030 を指している。

## 直前セッションで確定したこと

- ADR-095: 提案者欄の訂正(その72〜75 = Sonnet 5)/ `n_item` はタスク型ごとに T1 80・T1b 160・T2 80・T3 160(`power_sim.py` の対応待ち)/ ★F104-c は null に戻した(値は人間。エージェントは提案しない)/ `runs/preflight/` の無視を追認
- ADR-096: 前段 FT の前に診断を 1 本(決定1)/ P3 = (a) 加算なし・(b) 比較の対で非交差・(c) 値の大きさの分布を被覆水準の間で偏らせない(決定2)/ 成功基準・侵襲の閾値は GPU の前に凍結(決定3)/ 新ベースで順5 を測り直す(決定4)
- 本番プール(`data/generated/battery/main/items.jsonl`。git 管理外)の T3・T1b の和: 被演算子 2 桁以内 8〜188、3 桁以上(`extrap_magnitude`)234〜1,955
- R8 の記述は `results/r8_fit_order6b/r8_fit.txt`(run `20260922_122247_order6b_r8` / `…124632_order6b_s_preamble` / `…125131_order6b_s_d`)。**解釈はしていない**
- `pytest code/tests -q` = 1579 passed(2026-09-24)

## 触ってよいファイル / 読むべき範囲

- `logs/DECISIONS.md` の ADR-096(`grep -n '^## ADR-096' logs/DECISIONS.md` → `sed -n`)
- `plans/PLAN-026-order6b.md` §3.2(R8・S の掃引の設計)・§5(凍結した判定表の形。PLAN-030 の判定規則の手本)
- `plans/PLAN-025-binary-methods.md` §3.3・§3.4 / `plans/PLAN-028-prestage-ft.md` §3.1 / `configs/exp_order6b_pilot.yaml` の `eval.cells` と `threshold_sweep`

## やってはいけないこと

- **診断の判定規則の値を決めない**(案は出してよい。決めるのは人間。`CLAUDE.md` §8)。R8 の記述を解釈して結論を書かない
- **PLAN-029 の実装・GPU に進まない**(診断の結果を人間が読むのが先。ADR-096 決定1)
- `s2_item` / `s2_tmpl` の値を提案しない(ADR-095 決定3)。`dgp.n_item` に 999 を入れない

## 未解決 / 人間の承認待ち

- ★F104-c の値 / `n_item` のタスク型ごとの実装の PLAN / 前段 FT の成功基準・侵襲の閾値(ADR-096 決定3)/ ADR-094 決定2(F104-a)を見直すか
- 変わらず: ★F114 の実行先(3 つの null の後)/ `cost.txt` / 停止中ポッド 8 本の terminate / ★`θ` の根拠 / Phase 1 の GPU 構成 / N5 / 監査の D2・C2〜C5
