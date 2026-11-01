# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-01(その187)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN 完了(PLAN-047 の草案を書いた。`b1c7b20`)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — PLAN-047 §4 の人間の回答を ADR に起こす(`10_CONTEXT_POLICY.md` §7 の設計判断・統計の行)。人間が I7 を選んだ場合だけ Sonnet(RUNNER)でよい

---

あなたは **PLANNER**(分岐: 下記)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。

## 分岐(最初に人間に 1 回だけ聞く。推奨を先頭に)

- **★(A) PLAN-047 §4 の Q1〜Q7 を人間に諮り、ADR に起こす**: `plans/PLAN-047-ceiling-b-into-primary-and-run3.md` §4 の要約の表と各問いの表をチャットで先に示し(ADR-097 決定6)、`AskUserQuestion` で Q1〜Q7 を聞く(1 回 4 問まで → 2 回)。答えを ADR-137 に起こす(提案 エージェント / 採択 人間)・PLAN-047 のステータス・§10 記入欄・`OPEN-ITEMS.md`(Q7 の扱い)を更新して commit。実装(I1〜I5)は次の IMPLEMENTER
- **(B) 順6 の測り直し(PLAN-045 I7)**: 人間が起動を指示したら RUNNER として `infra/RUNPOD.md` §4 の手順で 1 run(設定は順6 R1・作り直した主プール)。10 GPU 時間を超えるなら起動前に承認

## このセッションでやること(1つだけ)

上の分岐のうち、人間が選んだ 1 つ。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- PLAN-047 草案(ステータス `草案`)。§3 の事実: 実データの主要解析 `code/analysis/primary.py` は**未実装**(PLAN-016 §7-5)/ `ceiling_rule` は `code/analysis/ceiling_remedy.py` にだけあり、`ceiling_remedy` が `power_sim` を import しているので `power_sim` から使うには別モジュールへ移す必要がある / `power_sim.summarise_point` に天井の判定を受け取る口は無い / run3 のシートで天井が何回当たるかは未測定
- §4 の推奨はすべて (a): Q1 規則を共有モジュールへ移し `primary.py` 本体は別 PLAN / Q2 フィルタ → df → 天井 → 当てはめ / Q3 GLMM は当てて出力に記録・報告は「実施不能(天井)」/ Q4 run3 は表を組んだ直後に判定・天井の反復は非棄却・TOST Δ = +∞ / Q5 実行可能性の門には入れない / Q6 config に欄を足さない・`ceiling_probe` には当てない / Q7 ADR-132 決定5 は C 用として閉じ、ADR-114 決定6 の手続きと Δ は S5
- `code/` は不変。GPU 0・pod 0

## 触ってよいファイル / 読むべき範囲

- (A): `plans/PLAN-047-*.md`(全体。短い)・`logs/DECISIONS.md` の ADR-135・136(`grep -n '^## ADR-13[5-6]'`)と末尾の形式・`logs/OPEN-ITEMS.md`(`grep -n`)。書くのは ADR・PLAN-047 の §10・ステータス・`OPEN-ITEMS.md`・`STATE.md`・`CHANGELOG.md`
- (B): `infra/RUNPOD.md` §4・順6 R1 の config・`runs/<id>/`

## やってはいけないこと

- 人間の答えの前に §4 を決める / `code/` を書き換える(PLANNER の範囲外)
- 天井の規則・門の値・run3 の格子・`rng_seed` 20261008 を変える(ADR-132・133・129 で凍結)
- `git add -A` を使う(未追跡の大きい結果がある: `results/power_sim/ceiling/*/frames/`・`results/ceiling_remedy/*/lmm/` など)
- 主プール・パイロットのプールを作り直す(PLAN-045 で確定済み)

## 未解決 / 人間の承認待ち

- PLAN-047 Q1〜Q7 / 順6 の測り直しの起動(PLAN-045 I7)/ `primary.py` 本体の PLAN(Q1 (a) の場合)/ `id` の二重露出の感度解析の事前登録(凍結前)/ R5(組 199)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2
