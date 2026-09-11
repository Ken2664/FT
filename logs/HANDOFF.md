# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-11(その41)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-023 の起草。1 セッション = 1 PLAN)+ コンテキスト約 10 万トークン超

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## ★最初に確かめること(ここで止まってよい)

**`plans/PLAN-023-order6-readiness.md` §2.6 の記入欄に、人間が記入しているかを見る。**
**★F128 / ★F129 / ★F131 / ★F135 / ★F136 / ★F137 の 6 件**(プールの生成に効くもの)のどれかが空欄なら、
**実装を始めずに、その 6 件を人間に聞いて止まる**(`CLAUDE.md` §8。案は §2.1・§2.2 にある。エージェントが代わりに決めない)。

## このセッションでやること(1つだけ。6 件が記入済みの場合)

**PLAN-023 §4 の手順1〜5 を実装し、§5 の dry-run 3 本と preflight の data_checks を通す。**GPU 0。
完了条件: `pytest code/tests -q` が通る / `python -m code.data_gen.eval_pool --config configs/exp_phase1_main.yaml` が
`data/generated/battery/main/` にプールを書く / `python -m code.eval.run --config configs/exp_phase1_main.yaml --dry-run` が通る /
プールの manifest をコミットする。**記入の内容が §4 の前提と食い違っていたら、実装を始める前に PLAN-023 §4 を直す。**

## 直前セッションで確定したこと

- **PLAN-023 は起草済(案)。決定は 0 件。**人間に上げたのは ★F128〜★F137(`logs/OPEN-ITEMS.md`「★2026-09-11(その41)の追記」)
- **コードの穴(PLAN-023 §1.1)**: A1 `fill_cells` は `label_coverage` で照合するので `extrap_magnitude` のセルを埋められない(`code/data_gen/pool.py:650`)/
  A2 候補を `[1,99]²` 全体から渡すと pilot 領域の組が `interp` に入る / A3 訓練域外の 50:50 分割は未実装 /
  A4 `Cell` に群・`category` の欄が無い / A6 `metrics.json` は採点バッチ単位で、#2・#3 のセル別の値が読めない /
  A7 本番 config の `run.py --dry-run` は `eval.dry_run_items` が無いので止まる
- **セルは埋まる**(組合せ論的な計数。現行 config と `exp_phase1_main_p2` の K): `id` carry 406 / `interp`(main 領域)carry 558 / `Q(999)` の適格 729,000 組。要求はどの被覆水準も carry 240
- `pytest code/tests -q` = **980 passed**(その40。その41 はコードを触っていない)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-023-order6-readiness.md`(§1.1・§2.2・§2.6・§4・§5。全文は 344 行。`grep -n '^##'` で節を出してから読む)
- `code/data_gen/pool.py`(`fill_cells` :615-667 / `label_main_coverage` :201 / `split_pilot_main` :478)/ `code/data_gen/eval_pool.py`(`build` :263-336)/
  `code/data_gen/ft_data.py:636-672`(main 領域の分割。同じ関数・同じ引数で再現する)/ `code/eval/run.py`(dry-run :489-560)/ `code/analysis/frame.py`(`build_rows` :364)
- `configs/exp_phase1_main.yaml` の `eval:`(:432-520)。**skill `code-style` を読んでから実装する**
- **Windows の Python で文書を書くときは LF**(`write_bytes` か `newline="\n"`)。**Python の CLI を回すときは `PYTHONIOENCODING=utf-8`**

## やってはいけないこと

- GPU・ポッドを触る / 事前登録済みの閾値(#1 = 0.02 / #2 = 0.70 / `θ` = 0.70)を変える / `magnitude_sweep.theta` を #2 の閾値に流用する(ADR-041 決定2)
- **組をセル間で再利用する**(PLAN-001 §5.1・ADR-026。PLAN-002 の「使い回せる」は古い記述。PLAN-023 §1.1 A13)
- 記入されていない ★F を推奨の (a) で埋める / `STATE.md` にブロックを積む(各節は最新 1 ブロック。上限 400 行)

## 未解決 / 人間の承認待ち

- ★F128〜★F137 / **順6 の GPU 承認**(文面は PLAN-023 §2.4)/ **E-5 (b)**(期限は順6 の前に早まった)/ 停止中ポッドの terminate /
  **★`θ` の根拠** / **★F104** / **★F114 の実行先** / N5 / ★C / ★2 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
