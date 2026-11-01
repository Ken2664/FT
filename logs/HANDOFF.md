# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-01(その188)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN 完了(PLAN-047 §4 の答えを ADR-137 に起こした。`8cb8a1f`)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — PLAN-047 I1〜I5 の実装・テスト(`10_CONTEXT_POLICY.md` §7 の実装の行)。人間が I7 を選んだ場合も Sonnet(RUNNER)でよい。実装中に統計の判断が出たら止めて PLANNER(Opus)へ

---

あなたは **IMPLEMENTER**(分岐: 下記)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。

## 分岐(最初に人間に 1 回だけ聞く。推奨を先頭に)

- **★(A) PLAN-047 I1〜I5 を実装する(IMPLEMENTER)**: skill `code-style` を読んでから、`plans/PLAN-047-ceiling-b-into-primary-and-run3.md` §5 の I1〜I5 を ADR-137 の決定どおりに実装する。完了条件 = `pytest code/tests -q` が通る・`python -m code.analysis.power_sim --config configs/power_sim.yaml --dry-run` が通る・smoke(偽の当てはめで、天井でない表の要約が HEAD と同一バイト)。I6(文書)は文言の案を作るだけで、人間の承認の前に書き込まない
- **(B) 順6 の測り直し(PLAN-045 I7)**: 人間が起動を指示したら RUNNER として `infra/RUNPOD.md` §4 の手順で 1 run(設定は順6 R1・作り直した主プール)。10 GPU 時間を超えるなら起動前に承認

## このセッションでやること(1つだけ)

上の分岐のうち、人間が選んだ 1 つ。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-137**(`logs/DECISIONS.md` 末尾)= PLAN-047 採択。7 問とも推奨 (a):
  - 決定1: `CeilingVerdict`・`ceiling_rule`・`CeilingRuleError` と判定の記録の形を共有モジュール(例: `code/analysis/ceiling.py`)へ移す。`ceiling_remedy.py`・`power_sim.py` はそこから import。**規則の中身は変えない**。`primary.py` 本体は別 PLAN
  - 決定4: run3 では `draw_frame` の直後に判定し反復の記録に `ceiling`・`ceiling_hits`。当てはめ・R・`fits/` は不変。集計で天井の反復は分母に入れて非棄却・TOST は Δ = +∞。天井の件数・天井でない反復だけの率・天井の反復の記述の p 値を別に並べる
  - 決定5: 過誤の門は無条件の率のまま。実行可能性の門の分子は当てはめ失敗だけ。天井の件数と CP95 は横に記録
  - 決定6: config に欄を足さない。役割 `power`・`null_calibration`・`shape_check`・`misspecification` で常に判定。`ceiling_probe` には当てない。旧い出力(欄なし)は「判定なし」として読む
  - 決定7: ADR-132 決定5 は閉じた。第 2 の尺度(ADR-114 決定6)は `OPEN-ITEMS.md` に残し S5
- `code/` は不変。GPU 0・pod 0

## 触ってよいファイル / 読むべき範囲

- (A): `plans/PLAN-047-*.md` §2・§3・§5・§6(短い)/ ADR-137(`grep -n '^## ADR-137' logs/DECISIONS.md`)/ `code/analysis/ceiling_remedy.py`(I1 節と import)/ `code/analysis/power_sim.py`(`draw_frame` の呼び出し・`summarise_point`・`GridPoint`・門の判定。`grep -n` で特定)/ `code/tests/test_ceiling_remedy.py`・`test_power_sim*.py`。書くのは `code/analysis/`・`code/tests/`・PLAN-047 §11・`CHANGELOG.md`・`STATE.md`
- (B): `infra/RUNPOD.md` §4・順6 R1 の config・`runs/<id>/`

## やってはいけないこと

- 天井の規則の中身・門の値・run3 の格子・`configs/power_sim.yaml`・`rng_seed` 20261008 を変える(ADR-132・133・129・137 で凍結)
- R(`power_sim_fit.R`)・`fits/` の形を変える / 天井の反復で当てはめを飛ばす / 天井の反復を分母から外す(ADR-137 決定4 で却下)
- `ceiling_probe` の役割の要約を変える(決定6)
- `primary.py` を書く(別 PLAN)/ I6 の文書を人間の承認前に書き込む
- `git add -A` を使う(未追跡の大きい結果がある: `results/power_sim/ceiling/*/frames/`・`results/ceiling_remedy/*/lmm/` など)
- 主プール・パイロットのプールを作り直す(PLAN-045 で確定済み)

## 未解決 / 人間の承認待ち

- PLAN-047 I6 の文言 / 順6 の測り直しの起動(PLAN-045 I7)/ `primary.py` 本体の PLAN の起票の時期 / 確率の尺度の手続きと TOST の Δ(S5)/ `id` の二重露出の感度解析の事前登録(凍結前)/ R5(組 199)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2
