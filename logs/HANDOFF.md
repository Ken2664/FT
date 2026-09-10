# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その38)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard の警告。約 120k トークン)。人間の決定(ADR-074)の記録と PLAN-022 の起草までは終えた。GPU・ポッドは触っていない

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装の前に skill `code-style` を読んでください。

## このセッションでやること(1つだけ)

**`plans/PLAN-022-parser-rule2-unanimous.md` を実装する。**完了条件は次の 4 つ。

1. `code/eval/parsers/base.py` / `numeric.py` の規則2 を「最後の印より後ろの整数が 1 個以上あり、すべて同じ値なら採る」に変え、
   PLAN-022 §3 の境界事例をテストに足して `pytest code/tests -q` が通る(直前は 957 passed)
2. `configs/exp_phase1_main.yaml` に `eval.extrapolation_radius: 999` / `eval.extrapolation_run_id: "20260910_104249_sweep_m"` を入れ、
   pytest が通る(**先に `code/data_gen/eval_pool.py` の門と、`null` を前提にしたテストを読む**。PLAN-022 §4 手順6)
3. `plans/PLAN-001` §5.4.1 規則2 と §4.1.1 を改訂する(旧文言は打ち消し線で残す)
4. 順5 の run を**別の run として**採点し直し、PLAN-022 §5.1 の検査 C1〜C5 を全部通してから、4 値を元の run と並べて報告する

## 直前セッションで確定したこと

- **ADR-074**(`logs/DECISIONS.md` の末尾。**提案 エージェント / 採択 人間**、2026-09-10):
  - 決定1: **`M*` = 999**(格子の上端で打ち切った値。どの判定水準も θ = 0.70 を割らなかった)[run:20260910_104249_sweep_m]。
    **`M*` は現行の規則2 で測った値で置く。再採点で置き直さない**
  - 決定2: **★F126 = 案 (ii)**。規則2 を変え、`predictions/` を採点し直す。**元の `metrics.json` は書き換えない**
  - 決定3: **★F127 を開いた**(被演算子 −1 の除外。人間待ち)
  - 決定4: 停止中ポッドの terminate は**人間が**操作する
- 再採点で期待する件数(★F126 の診断。`logs/OPEN-ITEMS.md` ★F126 の行)は PLAN-022 §5.1 C3 に写してある

## 触ってよいファイル / 読むべき範囲

- `code/eval/parsers/base.py`(`single_integer` 182 行付近。**利用者は `numeric.py` だけ**)/ `code/eval/parsers/numeric.py`(45 行)
- `code/tests/test_parsers_numeric.py`(80 行)/ `code/eval/run.py` の `parse_numeric_response`(265〜290 行付近)
- `code/eval/sweep.py`(集計関数を**再利用**する。書き直さない)/ `code/eval/scoring.py`(分類)
- `configs/exp_phase1_main.yaml` の 500〜515 行付近 / `code/data_gen/eval_pool.py` の 250〜320 行付近
- `plans/PLAN-001-eval-battery.md` §4.1.1(103 行〜)と §5.4.1(654 行〜)
- `runs/20260910_104249_sweep_m/predictions/`(git 管理外。**全文を読まない**。`python` で件数だけ)

## やってはいけないこと

- **元の `runs/20260910_104249_sweep_m/metrics.json` を書き換える**(ADR-074 決定2)
- **既存の負例テストを正例に変える**(PLAN-022 §3 で「変わらない」と確認済み。変わるなら止めて人間に上げる)
- **`M*` を置き直す / 再採点の数値を解釈する**(`CLAUDE.md` §8)
- **★F127(−1 の除外)に先回りして除外リストを変える**(人間待ち)
- `STATE.md` にブロックを積む(各節は最新 1 ブロック。古いものは `logs/STATE-ARCHIVE.md` へ。上限 400 行)

## 未解決 / 人間の承認待ち

- PLAN-022 §7 の 2 点(再採点を別の run ディレクトリにする / C3 が外れたら止める)。**異議が無ければこの案で進めてよいと人間に一言確かめてから始める**
- **★F127** / **★`θ` の根拠** / **★F104** / **★F114 の実行先** / **順6 の GPU 承認** / 停止中ポッドの terminate(人間の操作)
