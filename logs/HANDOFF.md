# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その89)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 326k)。PLAN-031 §3 の I2・I3・I5・I6 は済
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 実装系(`Documents/10_CONTEXT_POLICY.md` §7 の表)。ただし `build_trainer` の切り出しは訓練の経路に触れるので、指標・統計に触れないことを確かめてから進める

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**最初に skill `code-style` を読むこと。**

## このセッションでやること(1 つだけ)

**PLAN-031 §3.6 の「ポッド上の ★E の確かめ」の実行手段(入口)を作る。GPU は使わない・RunPod は触らない。**

- 仕様: `plans/PLAN-031-seed-fix-and-pilot-ft.md` §3.6 の最後の項(「同じ種で LoRA を挿すところまでを 2 回行い `adapter_init_sha256` が一致すること、違う種で違うこと、`adapter_param_dtype` の値(事実 f′)。やり方(1 プロセスで 2 回か 2 プロセスか)は IMPLEMENTER が決める」)
- 案(実装の読み。PLAN-031 §11 に書いて人間が覆せるようにする): `code/train/lora.py` の `build_trainer` の「`load_causal_lm` の後 → `seed_all` → `get_peft_model` → `trainable_named_parameters` → `parameters_sha256` → `check_adapter_dtype`」を小さい関数に切り出し(**本番と同じ経路を通す**。挙動は変えない)、
  その関数を訓練せずに呼ぶ CLI(例 `python -m code.train.seed_check --config <cfg> --seeds 0 0 1`)を作る。出力は `seed 0 → sha 1` / `seed 0 → 同じ` / `seed 1 → 違う` / dtype。重みは 1 回読んで LoRA を挿し直す(GPU 時間を抑える)か、プロセスを分けるかを決める
  - **やり方の決め方**: 「同じ種で 2 回」は `get_peft_model` を 2 回呼ぶため、**土台に前回の LoRA が残っていないこと**を確かめる(`peft` は土台を書き換える)。重みを読み直すのが確実。ポッドでの確かめなので費用は小さい
  - テスト: 偽の peft(`test_train_seeding.py` の作法)で切り出した関数の配線と、CLI の出力の形。**本物の peft はポッド上**
- **完了条件**: `pytest code/tests -q` が通る(その89 の 1678 から増える。**既存のテストは 1 件も落とさない・書き換えない**)/ `lora.py` の切り出しで `metrics.json` の `seeding`・`outcome.adapter_init_sha256`・`adapter_param_dtype` が変わらない(既存テストが縛っている)/
  PLAN-031 §11・`STATE.md`(旧ブロックはアーカイブへ)・`logs/CHANGELOG.md` / `pytest code/tests/test_repo_hygiene.py` / commit / `logs/HANDOFF.md` を次の 1 件(**RUNNER がポッド上で ★E の確かめと見積りを出し、人間に G1-1・G1-2 を聞く**)にする

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **config 8 本**(`configs/exp_pilot_ft_{train_{p2,ident,p2d},eval_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}}.yaml`)は `infra/make_pilot_ft_configs.py` が `exp_order6b_pilot.yaml` から作る。**手で編集しない**(`python infra/make_pilot_ft_configs.py --check`)。`train.*` は 8 本でバイト一致、値は ADR-100 の転記。訓練 run の dir は `runs/pilot_ft_train_<条件>_s<シード>`
- **`code/analysis/gonogo_ft.py`**: `python -m code.analysis.gonogo_ft --runs "runs/*exp_pilot_ft_eval*" [--baseline runs/20260922_121455_order6b_b0] [--out-dir results/pilot_ft]`。`pool_id` が `pilot` でない run が混ざったら止まる
- 訓練 3 本・評価 5 本の `--dry-run` が通る。**評価の dry-run は `model.adapter` の不在で止まらない**。1 評価 = 680 項目。preflight の `data_checks` は 8 本すべて 7 件 PASS
- `pytest code/tests -q` = **1678 passed**(2026-09-24 その89 実測)。`STATE.md` 397 行 / 59,263 バイト
- **Python で `.md`・`.py` を書き換えるときは `newline="\n"` を渡す**(Windows で CRLF になる)。**Bash ツールの heredoc に `\n` を書くと、Python のソース内で本物の改行に展開されることがあった**(その89。`.py` の文字列が壊れた)—— 文字列に改行を入れる編集は Edit ツールで行う

## 触ってよいファイル / 読むべき範囲

- `code/train/lora.py`(`build_trainer` の 430 行付近。**全文は読まない**)・`code/train/seeding.py`・`code/tests/test_train_seeding.py`(手本)・`code/train/run.py`(CLI の作法)・`plans/PLAN-031` の §3.1・§3.6・§11
- **全文 cat しない**: `configs/exp_phase1_main.yaml`(735 行)・`logs/DECISIONS.md`・`logs/OPEN-ITEMS.md`・`code/eval/run.py`(2,275 行)

## やってはいけないこと

- GPU に進まない / RunPod を触らない。5 値・閾値・条件を変えない。スケジューラ・warmup・クリッピングを足さない
- `build_trainer` の**挙動を変えない**(切り出しは引数と返り値を保つ。消費順 `lora.py:161` に触れない)。`metrics.json` の記録の形を変えない
- `#1〜#3` の出力・`gonogo.py`・宣言の無い評価 run・順6b の config の項目と文面を変えない。`configs/exp_phase1_main.yaml` に値を書かない
- `pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない。`CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない
- **config 8 本を手で直さない**(生成スクリプトを直して作り直す。テストが食い違いを検出する)

## 未解決 / 人間の承認待ち

- GPU の前: **G1-1**(GPU 承認 + VRAM の退避規則)・**G1-2**(ADR-043 決定11 の空欄と凍結 tag)・**#4b の基準 0.90 の目視確認**(`p2d` の結果を見る前に)
- **その89 の実装の読み 6 件**(PLAN-031 §11。人間が覆せる): (1) 評価に指示付き T1 を含める(`task_subset: [t1, t1_instructed, t2]`)(2) 新しい鍵を本番 config・順6b の config に足さない (3) #4b は #4 と別の鍵 (4) **#5・#5b の `other_error_rate` は run の条件自身の規則のブロックで数える(`p2d` の run は参照規則 `p2d`。§3.3 が書いていなかった)** (5) #4 は `p2` の run だけ・#4b は `p2d` の run だけ判定、ほかは並べる (6) `estimated_gpu_hours` は null
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
