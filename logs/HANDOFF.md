# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-11(その43)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-023 §6 がすべて ✅)+ コンテキストが 10 万トークンを大きく超えた

---

あなたは RUNNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**順6 の GPU(ADR-076 決定11)を `plans/PLAN-023` §7 の手順で回し、run を回収・コミットし、ポッドを停止する。**
**承認の条件(プールの manifest のコミットと dry-run の通過)は その43 で満たした。**

完了条件:
- R1〜R5 の 5 run(合計 7,520 項目・回)が `runs/<timestamp>_order6_r<k>/` に揃い、各 `metrics.json` の 4 値の合計が全ブロックで 1.0
- 各 run の `metrics.json` の `pool.items_sha256` が、コミット済みの manifest の `files.items.jsonl` と一致する(主プール = R1〜R4 / 交差プール = R5)
- `runs/*/metrics.json` と `config.yaml` をコミット(`[run:<id>]` をメッセージに)/ **ポッドを停止**(terminate は人間)
- 回収後(GPU 不要): `python -m code.analysis.gonogo --runs "runs/*_order6_r1"` と `compare_runs`(R1 対 R2・R3・R4)の**数値と印だけ**を人間に報告する。**解釈しない**

## 直前セッションで確定したこと

- PLAN-023 §4 の手順1〜7 を実装(commit `a24086c` / `118b0ae` / `6c6e113`)。`pytest code/tests -q` → **1030 passed**
- 主プール `data/generated/battery/main/manifest.json` = 1,640 項目(自由生成 680 / 強制選択 960)・1,560 組・`pairs_hash` `13e8479c…`。
  交差プール `data/generated/battery/main_t2_cross/manifest.json` = 960 項目。**どちらも本番 config から再現でき、2 回生成してバイト一致**
- **ADR-077(A14。人間が (a))**: 採点バッチを答え域で割る。主プールは 9 バッチ(`comparison` / `comparison.ans_out` / `bare_sum` / `bare_sum.ans_out` /
  `bare_sum_instructed` / `word_problem` / `word_problem.ans_out` / `spec_sub` / `spec_mul`)。`arb` のブロックは ans_in のバッチにだけ出る
- config: 本体 `configs/exp_phase1_main.yaml`(R1〜R3)/ `configs/exp_phase1_main_b1.yaml`(R4。差は `batch_size` と `experiment.id` だけ)/
  `configs/exp_phase1_main_t2cross.yaml`(R5。差は `experiment.id` / `anchor_manifest` / `batteries` だけ)。`resources:` は順6 の値(`estimated_gpu_hours: 2.0`)
- ローカルで通したもの: 3 config の `run.py --dry-run` / preflight の `data_checks`(6 項目 + data manifest が PASS)。**フルの preflight は回していない**
  (ゲート付きのトークナイザを読むので、ポッドで回す。#0 トークン境界と `forced_choice_tokens` はそこで初めて出る)
- GPU の見積り(**実測ではない**): 計算は約 1 時間・悲観側で約 2 時間、準備込み 2〜2.5 時間。**3 時間で打ち切って報告する**
  (秒数は [run:20260910_104249_sweep_m] / [run:20260828_100115_smoke1b_b1] から借りた値。強制選択の秒数は測っていない)

## 触ってよいファイル / 読むべき範囲

- **`plans/PLAN-023-order6-readiness.md` §7(順6 に固有の手順)と §6.1**(`grep -n '^## 7' plans/PLAN-023-order6-readiness.md` で位置を出す)
- `infra/RUNPOD.md` §3〜§7(ポッドの起動・bundle・venv・preflight・回収・停止の正本。順1b・順5 の実機の経験が入っている)
- ポッドの上でデータを作り直す(items.jsonl / train.jsonl は git に無い)。**評価プールの manifest は `created_at` を持たないので、作り直しても差分が 1 行も出てはならない**
- **Windows では Python の CLI に `PYTHONIOENCODING=utf-8` を付ける / 文書は LF で書く**

## やってはいけないこと

- 事前登録済みの閾値(#1 = 0.02 / #2 = 0.70 / `θ` = 0.70)を変える / Go/No-Go の判断・落ちたセルの一覧の確定・T1b の扱いを自分で決める(`CLAUDE.md` §8)
- **3 時間を超えて回し続ける**(打ち切って報告)/ ポッドを起動したまま放置する / 承認の対象外の run(Phase 1 本実験・FT)を回す
- run ディレクトリ名を `exp_phase1_main` で始める(A12。Phase 1 の glob に混ざる。`runs/<ts>_order6_r<k>` にする)
- `STATE.md` にブロックを積む(**いま 400 行。上限 400**。古いブロックはアーカイブへ移す)

## 未解決 / 人間の承認待ち

- **PLAN-023 §6.1 の実装の読み 6 点**(とくに #3 = 実測 `correct_rate` と定数戦略の大きいほうを比べる)。**順6 の表を読む前に人間が目を通す**
- 停止中ポッドの terminate / ★`θ` の根拠 / ★F104 / ★F114 の実行先 / Phase 1 本実験 40 run の GPU 構成 / N5 / ★C / ★2 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
