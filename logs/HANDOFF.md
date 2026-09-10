# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-11 02:30(その39)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard 約 210k トークン)+ 利用制限でサブエージェント 2 本が途中停止

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。実装の前に skill `code-style` を読んでください。

## ★この夜の前提(人間の指示。2026-09-10 22:47)

- **人間は 06:00 まで就寝中。その間、自律的に研究を進める。**「AI の提案は、エージェントが正しいと判断したものはすべて承認する」。
  この事前一括承認で採った決定は ADR に **「提案 エージェント / 採択 人間(事前一括承認)」** と書き、朝に人間が覆せる形で残す(ADR-075 が先例)
- **この承認があっても人間に残すもの**(エージェントの判断): 結果の解釈 / 論文の claim / 引用の確定 / **`θ` の根拠の代筆**(人間が自分で書くと決めている)/
  **GPU・ポッド**(順6 は準備が整っていない。ポッドの terminate も人間の操作)/ 62 時間の CPU ジョブ(★F114)
- **利用制限に一度当たった。**サブエージェントは 1 本ずつ・範囲を切って使う。コンテキストが 10 万トークンを超えたら skill `handoff` で切る
- 06:00 前に: `STATE.md` / `logs/CHANGELOG.md` を更新し、朝に人間が読む要約(採択した ADR・未解決・人間待ち)を CHANGELOG の その39 以降の節に残す

## このセッションでやること(順に。1 が終わらなければ 2 に進まない)

1. **PLAN-022 §5 の再採点を仕上げる。**`code/eval/rescore.py`(未コミット・約 700 行。サブエージェントが書いた途中版。
   「`execute()` の固定値の dict を戻り値に置き換える」途中で止まった)と `code/tests/test_rescore.py`(11 passed)を**読んでレビューし**、仕上げてから
   `python -m code.eval.rescore --source-run runs/20260910_104249_sweep_m` を実行する。**PLAN-022 §5.1 の C1〜C5 がすべて判定されるまで数値を報告しない。**
   C3 が外れたらコードを合わせにいかず、実数を記録して人間に上げる。元の run の `metrics.json` は書き換えない(ADR-074 決定2)。
   コミット: `exp(eval): ...   [run:<新 run id>]`(新 run の `config.yaml` / `metrics.json` / `transitions.json` / `git_sha.txt`)
2. **ADR-075 を実装する。**`code/data_gen/pool.py:88` の `EXCLUDED_OPERANDS` を `frozenset({1, -1})` にし、注記に ADR-075 を書く。
   `pytest code/tests -q` で落ちる件数固定のテストを ADR-075 を理由に直す(**`id` / `interp` / `extrap_magnitude` の件数は変わらないはず。変わったら止める**)。
   `plans/PLAN-001` の被演算子 1 の除外の記述に −1 を足す(旧文言は打ち消し線)。`logs/OPEN-ITEMS.md` ★F127 の期限欄を「実装済」に
3. **`plans/PLAN-023-order6-readiness.md` を起草する**(いまは監査結果だけ。§2 の決めることを埋める。GPU 0)。余裕があれば **E-5 (b)**(`logs/OPEN-ITEMS.md`)

## 直前セッションで確定したこと

- commit `bb5f112`: `code/eval/parsers/base.py` の `unanimous_integer`(ADR-074 決定2)/ `configs/exp_phase1_main.yaml` の `extrapolation_radius: 999`・
  `extrapolation_run_id: "20260910_104249_sweep_m"` / `code/tests/test_magnitude_sweep.py::test_the_main_config_m_star_is_traced_to_the_sweep_run` /
  PLAN-001 §4.1.1・§5.4.1。`pytest code/tests -q` = 967 passed(`test_rescore.py` を除く)
- **ADR-075**(`logs/DECISIONS.md` 末尾): 被演算子 −1 を全タスク型の評価項目から外す / 真値 −1 は外さない。根拠は腕1 の被演算子 −1 の項目 124 件中 24 件が `rule`、
  ほかの負の被演算子の項目は 9,550 件中 1 件 [run:20260910_104249_sweep_m]。応答は `Subtract -1 from 47: ... = 48` の型
- 順6 の監査結果: `plans/PLAN-023-order6-readiness.md` §1(**今夜は人間の決定なしでは回せない**)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-022-parser-rule2-unanimous.md`(92 行。§5・§5.1)/ `code/eval/rescore.py` / `code/tests/test_rescore.py` / `code/eval/sweep.py`(集計を再利用。書き直さない)
- `code/data_gen/pool.py` 80〜90 行・370〜420 行 / `logs/DECISIONS.md` の ADR-075(末尾)
- `runs/20260910_104249_sweep_m/predictions/`(git 管理外・大きい。**python で件数だけ。全文を読まない**)。**JSON は `encoding="utf-8"` で開く**(既定の cp932 で落ちる)

## やってはいけないこと

- 元の run の `metrics.json` を書き換える / `M*` を置き直す / 再採点の数値を解釈する(`CLAUDE.md` §8)
- 既存の負例テストを正例に変える / C3 に合わせてコードを直す
- GPU・ポッドを触る / `θ` の根拠を代筆する / `STATE.md` にブロックを積む(各節は最新 1 ブロック。上限 400 行)

## 未解決 / 人間の承認待ち

- **ADR-075 は人間が読んでいない**(事前一括承認)/ 停止中ポッドの terminate / **★`θ` の根拠** / **★F104** / **★F114 の実行先** / **順6 の GPU 承認** / N5 / ★C / ★2 / E-5 (b)
