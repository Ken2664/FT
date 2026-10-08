# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-08(その161)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 159k)。区切り = ADR-128 の採択とコミット(`d3a3a24`)が終わった
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — 実装の PLAN の草案は当てはめの手順・門の判定規則という統計の設計判断を含む(`10_CONTEXT_POLICY.md` §7 の「設計判断・統計」の行)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

ADR-128 を実装する PLAN の草案 **`plans/PLAN-043-*.md`**(`plans/TEMPLATE.md` の形)を書き、人間のレビューに出す。**実装はしない。**草案に入れる項目:
- `allFit` の段: 最適化の集合と引数(`start_from_mle` など)の固定。PLAN-042 の D1 で使った設定(§7 の記録)をそのまま採るかを判断材料の表にする(罠3)
- 失敗の数え方: LRT は全シートで非棄却 / TOST は全シートで Δ = +∞(ADR-125 決定3 を改める)
- 過誤の門の判定点(基本 `tau` 0.25・0.5・1.0 + seed_subspace 0.25・0.5)と実行可能性の門(各段で回した全点・失敗率の CP95 下端 > 0.10 で閉じる)・閉じたときに止める位置
- run3: 新しい `rng_seed` の値の決め方(起動前に commit)・out-dir・夜用タスクの登録の扱い
- 文書の打ち消し線の範囲(`05_STATISTICS.md` §3.2・`plans/PLAN-040` §11・ADR-059 / ADR-124 D2' / ADR-125 決定3 の参照)
- B2: パラメトリック・ブートストラップ(PB)の LRT の小さな計時(費用は未実測)
- 人間が決める値は表にして推奨を先頭に(ADR-097 決定6)。決めるのは人間

## 直前セッションで確定したこと

- **ADR-128(`logs/DECISIONS.md` 7738 行〜。人間が 5 問とも推奨)**: 軸 A = A2 + A3 / 軸 B = B1 + B2 / 実行可能性の門 0.10 / TOST の失敗も「主張しない」/ run3・新しい `rng_seed`・100 → 300 → 1000 を最初から
- 表に使った記述の数 [run:20261005_120003_power_sim_t1t2](`results/power_sim/run2/exploratory/fit_failure_diagnosis.json` の `cases`。門の判定ではない): 1a の条件を満たす失敗 139 / 156。残る失敗は基本 `tau` 0 → 6・0.25 → 1・0.5 → 2・0.75 → 3・1.0 → 0・1.5 → 0 / seed_subspace 0.25 → 1・0.5 → 4(各 100 反復)
- 文書本文・`configs/power_sim.yaml`(`rng_seed: 20260909`)・`power_sim*` のコードはまだ不変

## 触ってよいファイル / 読むべき範囲

- `logs/DECISIONS.md` 7738〜7780(ADR-128)。ADR-124・125・123 は `grep -n '^## ADR-12'` で位置を取り、必要な決定だけ `sed -n`
- `plans/PLAN-042-fit-failure-diagnosis.md` §2.2(82〜117 行)・§7(実装の記録。`allFit` の設定)
- `Documents/05_STATISTICS.md` §3.2(189 行〜。長いので `grep -n` で失敗・縮退・D2' の箇所を絞る)/ `plans/PLAN-040*.md` §11(153 行〜)
- コードの入口は `grep -n 'allFit\|drop_coverage_slope\|failed' code/analysis/power_sim*.py code/analysis/*.R`。**全文は読まない**
- 書いてよい: `plans/PLAN-043-*.md`・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/CHANGELOG.md`

## やってはいけないこと

- run2 の 100 反復で新しい規則の門を判定する(ADR-127 決定6)/ run2 の数え直しで「門が開く」と書く
- PLAN-042 §2.1 / §2.2 の閾値や印を書き換える(実行後)
- 人間の決定なしに `configs/power_sim.yaml`・`code/`・文書本文を変える / run3 を起動する
- 失敗した反復だけの棄却率(4 / 103)を「本当の過誤」と読む(選択の偏り)

## 未解決 / 人間の承認待ち

- PLAN-043 のレビューと値(`allFit` の集合・`rng_seed`・PB の計時の規模)
- push(`01cf60f` 以降の main)と G2-1 承認 → S4(検出力分析と独立)
- PB の反復数・食い違ったときの扱いは S5
- どの分散成分が特異か(32 件)は未確認 / `run2/misspecification_seed_per_cell/frames/` の残骸 46 本の削除(人間)/ 未追跡の `.claude/commands/`(このセッションでは作っていない。人間が確認)
