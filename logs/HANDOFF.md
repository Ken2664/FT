# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-08(その201)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN完了(PLAN-049 の Q1〜Q5 を人間が決めた = ADR-139)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 採択済みの決定を config・コード・テストに写す実装(`10_CONTEXT_POLICY.md` §7 の「実装・集計」)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。

## このセッションでやること(1つだけ)

- `plans/PLAN-049-n5-gate-and-tost-delta.md` §5 の **I2〜I5** を ADR-139 の決定どおりに実装し、`pytest code/tests -q` を通してコミットする
  - I2: `configs/primary.yaml` の `analysis_gate.threshold` = 0.90・`tost.delta` = 0.4988、門の役割(主要検定は感度だけ)・量(T1 × `id` の `rule_rate`、参照規則は run の条件の規則)・向き(≥ で通過)・`k` = 5 の欄
  - I3: `code/analysis/primary.py` の門 = 主軸の行を選んだ直後(選ぶ → 門 → 適格性フィルタ → df → 天井 → 当てはめ)。**主(門なし。今のシード数の検査 `n_seed` = 10 のまま)と感度(門あり。残った `p2` の本数を記録・5 本未満なら「実施不能: 解析門」)の 2 節**を出し、報告の表に門の行。`--simulate`・`--shuffle-labels` は門を掛けない現状のまま(ADR-138 決定3)。`pending_decisions` から門・Δ の 2 項目が外れること
  - I4: テスト — §3.3 の算術(`configs/power_sim.yaml` の P1 の 2 係数から RMS = 0.352767 を計算し、Δ = 0.4988 で正方形の角の RMS ≤ 下限・0.50 では超える)/ 門が run を落とす合成の frame で主と感度が分かれる / `k` 未満で「実施不能: 解析門」/ 本物の config の値を固定
  - I5: `pytest code/tests -q`・PLAN-049 §8 のチェック・CHANGELOG・commit

## 直前セッションで確定したこと

- ADR-139(`logs/DECISIONS.md` 末尾。commit `2e8a12b`): 主要検定は門なし主・門ありは探索の感度(Holm に入れない)/ 門 = T1 × `id` の `rule_rate` ≥ 0.90(順1b も同じ。順1b は門あり主のまま)/ 選んだ直後・`k` = 5 / Δ = 0.4988 ロジット / Δ は run3 の前に決めた。人間が採択(5 問と `k` とも推奨)
- `Documents/05_STATISTICS.md` §2 前処理・§3.2 順1b・§4 順1b の注・§5 の表は書き換え済み。`configs/`・`code/` は不変

## 触ってよいファイル / 読むべき範囲

- PLAN-049 §3.1 G4〜G10・§3.3・§5 / ADR-139(`grep -n '^## ADR-139' logs/DECISIONS.md`)
- `configs/primary.yaml:48-52` / `code/analysis/primary.py:140-200`(spec・`pending_decisions`)・`:240-255`(シード数)・`:478-545`(門の記録と順)/ `code/analysis/frame.py:471-496`(`gate_id_by_task`)/ `code/tests/test_primary.py`
- 書いてよい: `configs/primary.yaml`・`code/analysis/primary.py`・`code/tests/test_primary.py`・PLAN-049 §8・§11(実装で PLAN に無い選択をしたら記録)・`logs/CHANGELOG.md`・`STATE.md`

## やってはいけないこと

- ADR-139 に無い値・規則を足す(迷ったら PLAN-049 §11 に選択として書き、人間に諮る)/ 主要検定の手続き・天井の規則・`configs/power_sim.yaml`・`power_sim_fit.R` を変える / `git add -A`(未追跡の大きい結果がある)/ 承認なしに pod を起動する・push する

## 未解決 / 人間の承認待ち

- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push
- `results/primary/` の 2 run(その193)をコミットするか / `frame.py` の「未実装」の docstring の食い違い(その193 から持ち越し)
- N5 の (1)(`p2d` の交互作用を副次に)と #4b の事前登録での書き方 / T3・T1b の 6 セルの扱い(ADR-078 決定6)/ S4(`01cf60f` 以降の push と G2-1 承認の後。RUNNER)
