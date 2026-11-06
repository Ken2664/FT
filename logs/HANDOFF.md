# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-06(その199)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: 話題変更(HANDOFF の 1 つ = 順6 の印の並べ方と `input.order6_dropped_cells` の確定を済ませた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: 下の (A) なら Sonnet(RUNNER の定型。`10_CONTEXT_POLICY.md` §7 の「実装・集計」)/ (B) なら Opus(設計判断・統計の案。§7 の「設計判断・統計・解釈」)

---

**人間へ: 次の作業は人間が選ぶ。**(A) か (B) かを 1 行目に書き足してください。書いていなければ、エージェントは作業を始める前に聞きます。

あなたは (A) RUNNER / (B) PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

- **(A) RUNNER**: 人間が `01cf60f` 以降の push と G2-1 承認を済ませていれば、S4 を回す(`STATE.md`「次のアクション」2。手順は PLAN-035 §5 と `infra/RUNPOD.md` §4)。承認が済んでいなければ回さず、そう伝えて止まる
- **(B) PLANNER**: 凍結前に要る値のうち、N5(解析門の閾値)と解析門を順のどこに入れるか、平行性の TOST の Δ を決めるための判断材料の表と推奨を `plans/PLAN-XXX-*.md` の草案に書く(値は人間。`CLAUDE.md` §8)

## 直前セッションで確定したこと

- ADR-138 追記 ③(人間が採択。2 問とも推奨): `configs/primary.yaml` の `input.order6_gonogo` = `results/gonogo_order6_remeasure/gonogo.json` [run:20261106_021031_order6_r1_remeasure] / `input.order6_dropped_cells` = `[]`
- 根拠の印: 主軸の T1・T2 の 6 セルは旧い R1 [run:20260911_141547_order6_r1] でも測り直しでも #2 の `fails` が False。T3・T1b の 6 セルは両方で True(探索。照合の外)
- `pytest code/tests/test_primary.py -q` = 56 passed。実データの `primary.py` が止まる未決は frame の在り処・N5 の閾値・TOST の Δ(と解析門の順)

## 触ってよいファイル / 読むべき範囲

- (A): `infra/RUNPOD.md` §3〜§7 / `plans/PLAN-035` §5 / S4 の config
- (B): `Documents/05_STATISTICS.md` §2・§5(`grep -n 'N5\|TOST\|Δ'`)/ ADR-054 決定1・ADR-138 決定3 と追記 ①③(`grep -n`)/ `logs/OPEN-ITEMS.md` の該当行

## やってはいけないこと

- 印や 4 値を解釈する / 値をエージェントが決める / `git add -A`(未追跡の大きい結果がある。`results/primary/`・`results/ceiling_remedy/` など)
- 承認なしに pod を起動する・push する

## 未解決 / 人間の承認待ち

- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push
- `results/primary/` の 2 run(その193)をコミットするか / `frame.py` の「未実装」の docstring の食い違い(その193 から持ち越し)
- T3・T1b の 6 セルの扱い(ADR-078 決定6 の保留)
