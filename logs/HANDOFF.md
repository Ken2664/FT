# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その203)/ 直前セッションの役割: PLANNER(Claude Sonnet 5.5 が務めた。推奨の Opus と不一致。人間が続けさせた)
直前セッションが終了した理由: 区切り(PLAN-049 §11 の採否を記録・commit)
**推奨モデル(次のセッション)**: 人間が選ぶ作業によって変わる。frame の在り処・設計判断なら Opus / S4 の実行(RUNNER)・実装なら Sonnet(`10_CONTEXT_POLICY.md` §7)

---

次のセッションの作業は、人間が `STATE.md`「次のアクション」から選ぶ。**選ばれるまで始めない**。
`CLAUDE.md` §1 の開始手順を実行し、**最初の発言で実モデル名と、選ばれた作業の推奨モデルとの一致・不一致を 1 行で述べること**。

## 直前セッションで確定したこと

- PLAN-049 §11 の選択 ①〜⑧ を人間が採否: **すべて実装のまま採る**(ADR-139 追記 ①。提案 = IMPLEMENTER その202・採択 = 人間)。`code/`・`configs/` は不変
- ADR-139 の値(閾値 0.90・k = 5・Δ = 0.4988)と規則は不変

## 選べる作業(STATE.md「次のアクション」が正本)

- frame の在り処(`input.frame_dir`)を決める(実データの `primary.py` が止まる最後の未決)。決まったら ① の一致(frame.csv から数えた門の量と manifest の `gate_id_by_task`)を実 frame で検査する(未検証)
- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push / `results/primary/` の 2 run(その193)をコミットするか
- `01cf60f` 以降の push と G2-1 承認 → S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)
- N5 の (1)・#4b の書き方 / T3・T1b の 6 セル(ADR-078 決定6)/ `frame.py` の「未実装」の docstring の食い違い(PLANNER 案件)

## やってはいけないこと

- 人間が選ぶ前に作業を決める / ADR-139 の値を動かす / `git add -A`(未追跡の大きい結果がある)/ 承認なしに pod を起動する・push する
