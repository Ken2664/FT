# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その86)/ 直前セッションの役割: IMPLEMENTER(**Opus 5.5 で動いた**。handoff は Sonnet を指定していた)
直前セッションが終了した理由: コンテキスト超過(context-guard 約 283k)。PLAN-031 §3 の途中

---

**推奨モデル: Sonnet**(実装系。ADR-101。選ぶのは人間。Opus で動いていても続けてよいが、冒頭で伝えること)

あなたは IMPLEMENTER です(**最初の発言で実モデル名を名乗り、推奨と比べること**。`Documents/10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**最初に skill `code-style` を読むこと。**

## このセッションでやること(1 つだけ)

**PLAN-031 §3 の残り = I2・I3・I5・I6 を実装する。GPU は使わない。**(I1・I4 は済 = commit `369943c`・`5ba8d28`)
- 仕様の正本: `plans/PLAN-031-seed-fix-and-pilot-ft.md` §3.2・§3.3・§3.5・§3.6 と §4.0 の回答表(ADR-099・ADR-100)
- **I2(config)**: 下敷き `configs/exp_phase1_main.yaml` + パイロット用プールの 9 欄(`configs/exp_order6b_pilot.yaml` 冒頭。順6b だけの欄 `eval.threshold_sweep`・`eval.forced_choice_top_k`・`gonogo.near_tie_margin` は写さない)。
  **5 値(ADR-100)**: `train.lora.rank` 16 / `alpha` 32 / `learning_rate` 1e-4 / `batch_size` 4 / `gradient_accumulation` 4 / `num_steps` 625、`train.lora.target` `all`(ADR-043 決定9)。
  **I1 で必須になった鍵も入れる**: `train.optimizer.betas` [0.9, 0.999] / `eps` 1.0e-08 / `weight_decay` 0.01 / `train.adapter_dtype` float32(ADR-099 決定7)。**`train.*` は全 config でバイト一致**(`[MATCHED]`)
  - 前セッションの案(**実装の読み。PLAN-031 §11 に書いて人間が覆せるようにする**):
    訓練 config 3 本(`p2` `seeds: [0, 1]` / `ident` `[0, 1]` / `p2d` `[0]`。`lesion.condition`・`data.manifest`・`seeds`・`experiment.id` が違う)+
    評価 config 5 本(それぞれの訓練 config + `experiment.id`・`model.adapter` だけが違う)。訓練 run の dir は先に決める(例 `runs/pilot_ft_train_p2_s0`)。
    評価の範囲は `eval.batteries: [bare_sum, bare_sum_instructed, word_problem, specificity]` + `eval.task_subset: [t1, t1_instructed, t2]`
    (**ADR-099 決定5 は比較群だけを外すので指示付き T1 は残した、という読み。人間に明示する**)。1 評価 = 680 項目(T1 240・指示付き 80・T2 240・特異性 120)の見込み(dry-run で確かめる)
  - `gonogo`: (i) パイロットの設計門と分かる鍵で、値は `Documents/04_EXPERIMENT_PLAN.md:66-69` の転記(#4 0.90 / #4b 0.90 / #5 0.10 / #5b 0.05)。**#4b は人間の目視確認待ちなので #4 と別の鍵にして注記する案**
  - `experiment.preregistered_tag: null` / `resources.estimated_gpu_hours` は RUNNER の見積り / `resources.human_approval_date: null`
  - テスト: 違ってよい欄の集合を固定(`code/tests/test_order6b_pilot.py` の作法)。**`test_task_subset.py` の `test_only_the_order6b_arms_declare_a_task_subset` の `SUBSET_CONFIGS` に新しい config を足す**(足さないと落ちる)
- **I3**: `code/analysis/` に #4・#4b・#5・#5b の表(§3.3。`gonogo.py` の #1〜#3 の出力は 1 バイトも変えない。読み方は ADR-099 決定8 = a1・b1・c2・d3、#4b は参照規則 `p2d` のブロック)。`pool_id` が `pilot` でない run が混ざったら止める。先頭の注記を固定
- **I5**: `p2d` の訓練・評価 config(I2 と同じ形)と #4b の列
- **I6**: `pytest code/tests -q` / 全 config の `python -m code.train.run --config <cfg> --seed <n> --dry-run` と `python -m code.eval.run --config <cfg> --dry-run`(アダプタが無い段階で評価の dry-run が止まるかは未確認)/ preflight の data_checks
- 小さな残り: `code/tests/test_train_run.py` に「metrics.json 最上位の `seeding` が偽の訓練関数では null」「dry-run に `seeding_plan` が出る」のテストを足す
- **完了条件**: `pytest code/tests -q` が通る(その86 の 1617 から増える)/ 全 config の dry-run が通る / PLAN-031 §10・§11 / `STATE.md`(旧ブロックはアーカイブへ)・`logs/CHANGELOG.md` / `pytest code/tests/test_repo_hygiene.py` / commit /
  `logs/HANDOFF.md` を次の 1 件(**RUNNER がポッド上の ★E の確かめ(§3.6)と見積りを出し、人間に G1-1・G1-2 を聞く**)にする

## 直前セッションで確定したこと(ファイルに書き込み済み)

- I1: `code/train/seeding.py`(`seed_all` / `seeding_plan` / `parameters_sha256` / `parameter_dtypes`)、`lora.check_adapter_dtype`。新しい鍵は `configs/template.yaml`(null)と `configs/smoke.yaml`(配線用)にだけある。**本番 config・順6b の config は触っていない**
- I4: `code/eval/task_subset.py` の `UNTYPED_GROUPS`・`solved_whole`。順6b の ①・(d)・S-(d) の文面の sha256 は `test_task_subset.py` の `PROMPTS_SHA256_BEFORE_ADR_099`
- `pytest code/tests -q` = 1617 passed(その86)。`STATE.md` 396 行 / 58,510 バイト
- **Python で `.md`・`.py` を書き換えるときは `newline="\n"` を渡す**(Windows で CRLF になる)

## 触ってよいファイル / 読むべき範囲

- `configs/`(新しいパイロット FT の config)/ `code/analysis/`(新モジュール)/ `code/tests/` / `plans/PLAN-031` の §3・§4.0・§10・§11
- 手本: `code/analysis/gonogo.py`・`frame.py`、`code/tests/test_gonogo.py`・`test_order6b_pilot.py`・`test_task_subset.py`
- **全文 cat しない**: `configs/exp_phase1_main.yaml`(735 行)・`logs/DECISIONS.md`・`logs/OPEN-ITEMS.md`・`code/eval/run.py`(2,275 行)

## やってはいけないこと

- GPU に進まない / RunPod を触らない。5 値・閾値・条件を変えない。スケジューラ・warmup・クリッピングを足さない
- `#1〜#3` の出力と、宣言の無い評価 run・順6b の config の項目と文面を変えない。`configs/exp_phase1_main.yaml` に値を書かない(Phase 1 の値は未決)
- `pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない。`CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない

## 未解決 / 人間の承認待ち

- GPU の前: **G1-1**(GPU 承認 + VRAM の退避規則)・**G1-2**(ADR-043 決定11 の空欄と凍結 tag)・**#4b の基準 0.90 の目視確認**
- I2 の実装の読み(評価に指示付き T1 を含める / 新しい鍵を本番 config に足さない)は人間が覆せる形で §11 に書く
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
