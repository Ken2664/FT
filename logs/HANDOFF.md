# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-11(その40)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-022。1 セッション = 1 PLAN)+ コンテキスト約 10 万トークン超

---

あなたは PLANNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## ★前提(人間の指示。2026-09-11 朝)

- **夜間の事前一括承認(2026-09-10 22:47)は終わった。**設計判断・実験条件・GPU は通常どおり人間の承認を得る(`CLAUDE.md` §8)。
  **案を書くのはよい。決めるのは人間**(ADR-039)

## このセッションでやること(1つだけ)

**`plans/PLAN-023-order6-readiness.md` の §2「起草で決めること」を埋め、順6 を dry-run が通る状態にするための計画にする。**GPU 0。
完了条件: §2 の 4 項目それぞれに「現状(ファイル:行)/ 案 / 人間に上げる点」が書かれ、実装手順(`code-style` に従う順)と
dry-run のコマンドが書かれていること。**§2 のうち新しい設計判断を含むものは決めずに `logs/OPEN-ITEMS.md` に上げる。**
余裕があれば E-5 (b)(`logs/OPEN-ITEMS.md` の E-5 の行。K の出どころを `metrics.json` に焼き込む)の案を同じ要領で書く。

## 直前セッションで確定したこと

- **PLAN-022 完了。**`code/eval/rescore.py`(commit `760f29b`)で順5 を別の run として採点し直した
  [run:20260910_215422_rescore_sweep_m]。**PLAN-022 §5.1 の C1〜C5 はすべて pass**(C3 は期待値と完全一致)。4 値の表は `STATE.md`「わかっていること」。**解釈はしていない**
- **ADR-075 を実装した**(人間が朝に承認。commit `5967594`)。`code/data_gen/pool.py` の `EXCLUDED_OPERANDS` = {1, −1}。
  −1 を含む組は `id` / `interp` / `extrap_magnitude` に 0 件(`label_main_coverage` で全数確認。組合せ論的事実)。`plans/PLAN-001` §4.3 に被演算子の除外の段落
- `pytest code/tests -q` = **980 passed**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-023-order6-readiness.md`(41 行。§1 監査結果・§2・§3)
- `plans/PLAN-001-eval-battery.md` §4.6(パイロット専用プール)・§5.1(セル表)—— `grep -n` で節を特定してから `sed -n`
- `configs/exp_phase1_main.yaml` の `eval.batteries` / `eval.cells` / `eval.pool_items` / `eval.pool_seed`(null のもの)
- `code/data_gen/eval_pool.py`(`FILL_EXPLICIT_LIST`・`fill_cells` の呼び出し)/ `plans/PLAN-004-phase0-route.md` §2(順6 の中身)
- **Windows の Python で文書を書くときは LF**(`write_bytes` か `open(..., newline=` に LF を渡す)。**Python の CLI を回すときは `PYTHONIOENCODING=utf-8`**(標準出力が cp932)

## やってはいけないこと

- GPU・ポッドを触る / 事前登録済みの閾値(#1 = 0.02 / #2 = 0.70 など)を変える / 実験条件を足す・消す(`CLAUDE.md` §8)
- `θ` の根拠を代筆する(人間が自分で書く)/ 再採点の数値を解釈する / `M*` を置き直す
- `STATE.md` にブロックを積む(各節は最新 1 ブロック。上限 400 行。古いブロックは `logs/STATE-ARCHIVE.md` へ)

## 未解決 / 人間の承認待ち

- 停止中ポッドの terminate / **★`θ` の根拠** / **★F104** / **★F114 の実行先** / **順6 の GPU 承認** / N5 / ★C / ★2 / E-5 (b) /
  `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
