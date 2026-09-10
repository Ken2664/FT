# PLAN-023 — 順6(Go/No-Go #0〜#3 + タスク4〜6)を dry-run が通る状態にする

- 起草: 2026-09-11(その39)/ エージェント (Opus)
- 状態: **★計画は未起草。この版は監査結果の記録だけである**(起草役のサブエージェントが利用制限で止まった)
- GPU: **0**(この PLAN の範囲。GPU の実行そのものは人間の承認が要る)

---

## 0. 一行要約(案)

順6 を回すのに欠けている config・コードを埋め、`python -m code.eval.run --config <順6 の config> --dry-run` を通し、
GPU ジョブの中身と時間を確定させる。**GPU は使わない。**

## 1. 監査結果(2026-09-10 23:00 頃。読み取り専用のサブエージェント。**判定は「今夜は新しい人間の決定なしでは回せない」**)

| # | 種類 | 中身 | 場所 |
|---|---|---|---|
| 1 | 人間の決定 | **順6 を回す GPU の承認が無い**(`logs/OPEN-ITEMS.md`「GPU 構成」)。ADR-057 決定2 は順5 の GPU 構成を順6 と切り離した。`resources:` は「順5 のみ」 | `configs/exp_phase1_main.yaml` の `resources:` 付近 |
| 2 | config が null | `eval.batteries: null`(要るのは `comparison` / `bare_sum` / `bare_sum_instructed` / `word_problem` / `specificity` の類。**監査の推定であり未照合**) | 同 config 441 行付近 |
| 3 | config が null | `eval.cells: null`。**注記は「承認待ち-6(T2 の文面)」を理由に挙げるが、それは ADR-032 / `configs/templates/t2.yaml` で決着済 → 注記が古い。**本当の穴は **PLAN-001 §5.1 のセル表が config に転記されていないこと** | 同 499 行付近 |
| 4 | config が null | `eval.pool_items: null`。**`M*` 未決のあいだの暫定の明示リスト**だった(ADR-033 決定4 は「決まったら `fill_cells` を呼ぶ経路に置き換わる」と書いた)。**`M*` = 999 は決まった(ADR-074)** | 同 506 行付近 |
| 5 | config が null | `eval.pool_seed: null`(いまは消費されない) | 同 509 行付近 |
| 6 | 順6 に移された検査 | ADR-057 決定4: バッチの浮動小数ノイズ検査(ADR-040 決定7)と preflight の `forced_choice_tokens` 検査。**どちらも `comparison` 群のプールが要る** | `logs/DECISIONS.md` ADR-057 |
| 7 | コードが無い | **タスク5(test-retest、`num_repeats = 3`)が回らない。**`code/eval/model.py` の `SUPPORTED_NUM_REPEATS = 1` と `reject_unimplemented_settings` が他の値を拒む。**反復生成は未実装** | `code/eval/model.py:52` / `:157-165` |
| 8 | 足りている | 項目生成は全群ある(`code/eval/battery/build.py` / `t3_comparison.py` / `numeric_sum.py` / `specificity_control.py`、強制選択 `code/eval/forced_choice.py`、定数戦略 `code/eval/scoring.py` の `constant_answer_baseline`)。トークン境界 #0 は `infra/preflight.py`(順1b で実行済) | — |

- **GPU 時間の見積りは repo に無い**(「GPU 小」という定性の記述だけ。`plans/PLAN-019` 597・601 行付近)。
  実測は順5 の自由生成だけ: 0.307 秒/項目(バッチ 4・RTX 4090)[run:20260910_104249_sweep_m]。**強制選択の時間は未照合**(順1b の run を見ること)
- 項目数の目安は PLAN-001 §5.1 の主軸 1,560 項目(うち強制選択 960)+ 副次(P-2 800 / テンプレート税 240 / R8 8,160 / 指示付き T1)。
  **組合せ論的な計数であって実験結果ではない。順6 がどれを回すかは未確定**

## 2. 起草で決めること(未着手)

- 順6 が回す群・セル・項目数、**主プールかパイロット専用プールか**(PLAN-001 §4.6)、タスク4 の「5 シード」が何のシードか
- セル表の転記(PLAN-001 §5.1 → `eval.cells`)は**承認済みの仕様の機械的な転記**か、新しい設計判断を含むか
- 反復生成の実装範囲(`num_repeats = 3` はタスク5 だけ)
- GPU 時間の見積り(自由生成 + 強制選択)と、人間に上げる GPU 承認の文面

## 3. やらないこと

GPU / ポッド / 事前登録済みの閾値(#1 = 0.02 / #2 = 0.70 など)の変更 / 実験条件の追加・削除(`CLAUDE.md` §8)
