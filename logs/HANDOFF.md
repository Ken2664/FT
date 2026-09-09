# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-09(その29)/ 直前セッションの役割: PLANNER / CRITIC (Opus)
直前セッションが終了した理由: コンテキスト超過(約 209k。閾値 140k)

---

あなたは **PLANNER / CRITIC** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1 つだけ)

**人間が `plans/PLAN-020-theta-decision.md` §7 の 4 行(θ-0 / θ-a / θ-b / θ-c)を埋めたら、
`logs/DECISIONS.md` に ADR-070 を書き、決定を実装まで落とす。**

完了条件:

1. `logs/DECISIONS.md` に **ADR-070**(**提案 エージェント (Opus) / 採択 人間**を分けて書く。
   ADR-039 決定3)。**4 行それぞれに決定・根拠・不採択案・帰結を書く**
2. 決定の内容に応じて反映する(**人間が決めた行だけ**):
   - **θ-a** → `plans/PLAN-001` §4.1.1 に θ の値を書く + `configs/exp_phase1_main.yaml` の
     `eval.magnitude_sweep` 付近に記入(**`[MATCHED]` 欄かどうかを先に確かめる**)
   - **θ-b** → **B1 なら** ADR-041 決定3 規則5 の条件を差し替える(打ち消し線 + 理由 + 日付。
     `CLAUDE.md` §2)。`code/data_gen/pool.py` の `extrapolation_pairs` の
     `ValueError` 条件と、そのエラーメッセージも合わせる。**回帰テストを足す**
   - **θ-c** → **C1 なら** `code/eval/sweep.py` の `metrics.json` に殻ごとの
     `correct_rate` を足す(`predictions/` の `operands` から。**追加の GPU 時間 0**)。
     **C2 なら `plans/PLAN-001` §4.1.1 の推定量そのものの変更**であり、規則2 の意味も変わる
3. `pytest code/tests -q` が緑(**開始時点で 906 passed**)
4. `logs/OPEN-ITEMS.md` の `θ` 行に打ち消し線 + ADR 番号 + 日付 → `STATE.md` の索引から 1 行落とす
5. `logs/CHANGELOG.md` に追記 → commit

**人間がまだ埋めていない場合は、埋めるのを待つ。材料を作り直さない。**
**★材料は完成している。§0 の 1 ページ要約と §6.5(元々の問いとの距離)を読ませれば足りる。**

## 直前セッションで確定したこと(すべてファイルに書き込み済み)

- **`plans/PLAN-020-theta-decision.md` を新設した。決定は 0 件。**記入欄は §7、要約は §0
- **★F120**: 主軸 3 水準目 `extrap_magnitude` は `a > 99` かつ `b > 99`(`code/data_gen/pool.py:59`)。
  母集団は `(M* − 99)²` しかない。**`M* = 100` で 1 組 / 110 で 121 / 125 で 676。**
  セル表の要求は **520 組(carry 層ごとに 240)**。**両方を満たす最小の `M*` は 134、格子上は 150。**
  **ADR-041 決定3 規則5 は `M* < 100` にしか分岐が無く、格子点 100 / 110 / 125 はその外側にある**
- **★F121**: `correct_rate(M)` は殻ではなく `R(M)` 全体の累積平均
  (`magnitude_sweep.build_items` は `[-M, M]²` から一様に引く)。
  **`M = 100` では引かれる組の 98.0% が主域の中。**仮定シナリオ S1 では θ = 0.50 〜 0.90 の
  どれを選んでも `M*` が上の 3 点に落ちる。**懸念6 が外挿腕に戻る**
- **殻ごとの正答率は `predictions/` の `operands` から取れる**(`code/eval/run.py:681`)。
  **追加の GPU 時間 0。解析側の実装のみ。まだ実装していない**
- **★θ-0(いつ決めるか)自体が記録の中で食い違っている**(PLAN-020 §3)。
  **どの ADR も決定として書いていない**
- 検査: `plans/PLAN-020-check1/`(**組合せ論の計数と、仮定を置いた算術。実験結果ではない**)
- 回帰テスト 6 件を `code/tests/test_design_facts.py` に追加。**`pytest` = 900 → 906 passed**
- **順5 の GPU 承認は 2026-09-06 に取得済**(`configs/exp_phase1_main.yaml:571`。見積り 1.5 GPU時間)。
  **順5 を止めているのは `θ` だけである**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-020-theta-decision.md` §0(要約)/ §6(案)/ **§6.5(元々の問いとの距離)** / §7(記入欄)
- `logs/DECISIONS.md` の **ADR-041**(`grep -n 'ADR-041' logs/DECISIONS.md` → `sed -n 'X,Yp'`)
- `code/data_gen/pool.py` の `MAIN_COVERAGE_LEVELS`(59 行)/ `extrapolation_pairs`(121 行)/
  `label_main_coverage`(195 行)
- **全文 `cat` しない。**`grep -n` → `sed -n 'X,Yp'` で読むこと(`CLAUDE.md` §10.1)

## やってはいけないこと

- **θ の値をエージェントが決めない。**規範的な線引きであり `CLAUDE.md` §8 の対象である
- **★F104 / ★F114 の実行先を蒸し返さない。**別件であり `plans/PLAN-019` §10.13 が正本
- **`Documents/05_STATISTICS.md` と `configs/power_sim.yaml` を触らない**(★F104 待ち)
- **決定材料を作り直さない。**PLAN-020 は完成している
- **GPU を起動しない**(順5 は θ が決まるまで回さない)

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8。索引は `logs/OPEN-ITEMS.md`)

- **★`θ` の 4 行**(`plans/PLAN-020` §7)—— **順5 の唯一の残りブロッカー**
- **★F104**(`s2_item` / `s2_tmpl` の取得元。`plans/PLAN-019` §10.13.5)
- **★F114 の実行先**(62 〜 372 時間をどこで回すか。★F104-a に従属)
- **順6 の GPU 承認** / **Phase 1 本実験 40 run の GPU 構成** / **LoRA グリッド**
- **N5**(解析門の閾値)/ **★C** / **★E** / **★L(d)** / **E-5 (b)** / **★2** / **PLAN-018 §4.3**
- **`Documents/09_PAPER_PLAN.md` と `00_OVERVIEW.md:7` が再設計前のまま**
