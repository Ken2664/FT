# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-06(その200)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN完了(HANDOFF の (B) = PLAN-049 草案を書いた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — 設計判断・統計の案を人間に諮り ADR を書く(`10_CONTEXT_POLICY.md` §7 の「設計判断・統計・解釈」)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

- `plans/PLAN-049-n5-gate-and-tost-delta.md` §4 の Q1〜Q5 を、§3 の表(事実と算術)を先にチャットで示してから `AskUserQuestion` で人間に諮る(推奨を先頭に。ADR-097 決定6)。決まったら ADR-139(提案 エージェント / 採択 人間を分ける)と PLAN-049 §9・ステータス、§5 I1 の文書の書き換え(`05_STATISTICS.md` §2 前処理・§5 の「勾配が平行」の行・§3.2 の順1b の閾値。旧文は打ち消し線と日付)、`logs/OPEN-ITEMS.md` の N5・★C・TOST の Δ の行
- 人間が今は決めないと言ったら、何もせずにそう記録して止まる

## 直前セッションで確定したこと

- PLAN-049 草案(値は決めていない)。推奨: Q1 (a) 主要検定は門なしが主・門ありは感度 / Q2 (a) T1 × `id` の `rule_rate` ≥ 0.90 / Q3 (a) 主軸の行を選んだ直後・残り `k` = 5 本未満なら「実施不能: 解析門」/ Q4 (a) Δ = √2 × 0.352767 = 0.4988(算術。実験結果ではない)/ Q5 (a) run3 の D5 の表を見る前に決める
- 食い違い(判断なし): 「門あり主」は順1b の決定(ADR-055 決定3)で、§2 の主要検定には門が書かれていないが `primary.py` には口がある(ADR-138 決定1・3)
- パイロットの T1 × `id`(参照規則 `p2`)は `p2` s0・s1 とも rule 1.000 [run:pilot_ft_eval_p2_s0] [run:pilot_ft_eval_p2_s1](`pool_id: pilot`。主張に使わない)

## 触ってよいファイル / 読むべき範囲

- PLAN-049 全文 / ADR-054 決定1・ADR-055 決定3・ADR-114 決定5・ADR-138 決定3 と追記 ③(`grep -n`)/ `Documents/05_STATISTICS.md` §2(`:24-160`)・§3.2 順1b(`:378-410`)・§5(`:749-858`)
- 書いてよい: `logs/DECISIONS.md`・PLAN-049・`Documents/05_STATISTICS.md` の該当節・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/CHANGELOG.md`

## やってはいけないこと

- 値をエージェントが決める / `code/`・`configs/` を変える(I2〜I5 は IMPLEMENTER)/ `git add -A`(未追跡の大きい結果がある)/ 承認なしに pod を起動する・push する

## 未解決 / 人間の承認待ち

- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push
- `results/primary/` の 2 run(その193)をコミットするか / `frame.py` の「未実装」の docstring の食い違い(その193 から持ち越し)
- T3・T1b の 6 セルの扱い(ADR-078 決定6 の保留)/ S4(`01cf60f` 以降の push と G2-1 承認の後。RUNNER)
