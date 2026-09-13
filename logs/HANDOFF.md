# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-13(その56)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard。約 263k トークン。I4 の配線の読みを PLAN-026 §4.5 に書いたところで切った。コードは未着手)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その56 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。
**★その56 は設計のために `run.py` を 1,300 行ほぼ全部読んで context-guard に達した。下の「設計」をそのまま使い、読み直しは行範囲を切ること。**

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I4 = 掃引項目の記録の経路を、§4.5(その56 に書いた配線の読み)のとおりに実装する(CPU のみ。GPU 0)。**§4.5 を先に読む(`grep -n '### 4.5' plans/PLAN-026-order6b.md`)。

**完了条件**: GPU の無いテストで —— R8 の掃引プールを解くと `classify` を呼ばずに項目ごとの logp が 8,160 行書かれる(T3 4,080 + T1b 4,080)/ 掃引の項目を固定オフセットの経路に渡すと止まる(重みを読む前・run ディレクトリを作る前)/ 宣言があるのに掃引のプールでない config も止まる /
`configs/exp_order6b_r8.yaml` で `run.py --dry-run` と preflight の data_checks が通る / `pytest code/tests -q` が通る(直近の実測は **1082 passed**。その55)。**I5(当てはめ。前に「階段の位置」の定義を PLAN-026 §3.2.1 に書く)は次のセッション**

## 設計(その56 に決めた。§4.5 の実装。行番号は その56 時点の `code/eval/run.py`)

1. **config `configs/exp_order6b_r8.yaml`**: `configs/exp_order6b_pilot.yaml` の写し(LF・UTF-8。**`Path.write_text` で書かない**)。違うのは 4 欄だけ —— `experiment.id: exp_order6b_r8` / `eval.anchor_manifest: data/generated/battery/pilot_sweep_r8/manifest.json` / `eval.batteries: [comparison]`(`load_pool_items` の検査3 が「宣言した群はどれも項目を持つ」を要るため)/ **`eval.threshold_sweep_arm: r8`**(新しい鍵。`eval.threshold_sweep` の塊の直後に注記付きで)。
   `resources.estimated_gpu_hours` は 2.5 のまま(順6b 全体の悲観側。新しい数を作らない)。冒頭の注記に「項目は pilot の config から `sweep_pool --arm r8` で作る。この config を `eval_pool` / `sweep_pool` に渡すと群が足りず止まる(t2cross と同じ)」。差分 4 欄はテストで縛る(`test_order6b_pilot.py` の `differing_keys` と同じ形)
2. **`run.py` の固定オフセットの経路に足す検査**:
   - `declared_threshold_sweep_arm(config) -> str | None`(無い / null → None。文字列でなければ `ConfigError`)/ `read_pool_manifest(config)`(`eval.anchor_manifest` を読む。無ければ `ConfigError`)/ `is_threshold_sweep_pool(manifest)`(`fill.method == sweep_pool.FILL_THRESHOLD_SWEEP`)
   - `refuse_declared_threshold_sweep(config)` と `check_pool_kind(config, manifest, *, threshold_sweep: bool)`(両方向)
   - `load_pool_items`(690 行)は内部関数 `_read_pool_items(config, *, threshold_sweep)` に分け、**順序は「items.jsonl が有るか → `check_pool_kind` → 既存の検査」**(`test_run_order6.py` の `test_dry_run_without_a_pool_stops` が「評価プールの項目が無い」の文言を先に要る)
   - `dry_run`(565 行)の頭で `refuse_declared_threshold_sweep` / **`execute`(1159 行)は `prepare_run_dir` の前に `check_pool_kind(..., threshold_sweep=False)`**(いまは重みを読み run dir を作った後に `evaluate_pool` → `load_pool_items` で初めて項目を読む)
3. **掃引の経路**(`run.py` の新しい節。**`classify`・`metrics_by_reference_rule`・`response_builder` を呼ばない**):
   - `ThresholdSweepPool`(`settings: sweep_pool.SweepSettings` / `manifest` / `items` / `cell_of: item_id → sweep_pool.SweepCell`)
   - `load_threshold_sweep_pool(config)`: `_read_pool_items(threshold_sweep=True)` → `sweep_pool.load_sweep_settings(config, arm)` → manifest の `fill` の `arm`・`threshold_offsets`・`task_types`・`polarities`・`pairs_per_cell`・`selection.seed`(= `eval.pool_seed`)を config と照合 →
     `sweep_pool.sweep_cells(eval_pool.load_cells(config), settings.task_types)` と `fill.cells`(名前の集合・`source_cells`・20 組・重複なし)を照合し `(タスク型, 組) → SweepCell` の表を作る(**セルの名前を解析しない**)→ 各項目: 群が comparison / 組が表にある / θ が水準にある / `threshold == t3_comparison.sweep_threshold(t, θ)` →
     **完全性**: どの(併合セル × 極性 × θ)もそのセルの 20 組とちょうど一致
   - `threshold_sweep_record(item, *, cell, prompt, choice)`: §4.5 読み2 の欄(`truth` は `t3_comparison.comparison_answer(t, 極性, T)`、`response` は既存の `forced_choice_response_text`、`answer` は `choice.answer`)
   - `evaluate_threshold_sweep(config, pool, *, scorer) -> {predictions の名前: 行}`: タスク型ごとに項目の並びのまま `load_group_templates(config, "comparison", data.eval_template_set)` + `RENDERERS` → `collect_forced_choices` → `predictions/threshold_sweep.<タスク型>.jsonl`。`reject_unsupported_elicitation` も掛ける
   - `threshold_sweep_payload(...)`: `kind: threshold_sweep` / 来歴(`pool_record` + `n_items`・`coverage_record`・`generation`・`adapter`・`timing`)/ `threshold_sweep`(腕・θ・タスク型・極性・組の数・`source_pool_pairs_hash`・`n_items_by_cell` = {セル: {極性: {str(θ): n}}}・predictions の行数・注記)/ `forced_choice.candidates`(`metrics_payload` の組み立てを小さな関数に出して共有)。**率を 1 つも出さない**
   - `execute_threshold_sweep(config, *, config_path, run_dir, scorer=None, now=None)`: **検査はすべて `prepare_run_dir` の前**。`scorer` が None のときだけ `build_engines` で重みを読む / `threshold_sweep_report_lines`(`report_lines` の先頭 6 行を小さな関数に出して共有)
   - `threshold_sweep_dry_run(config)` + `print_threshold_sweep_dry_run`: 件数と category ごとの例のプロンプト 1 つ。8,160 のプロンプトを全部は出さない。記録の組み立ては定数の答え(`DRY_RUN_FORCED_CHOICES`)で 1 度通すだけ
   - `main`(1274 行): `declared_threshold_sweep_arm` で `--dry-run` と本実行の両方を振り分ける
4. **テスト `code/tests/test_threshold_sweep_run.py`(新規)**: module の fixture で `eval_pool.build(pilot の config)`(**約 8 秒**)を 1 度だけ組み、R8・S・パイロット用プールを `tmp_path_factory` に書く(**items.jsonl は git に無いので手元の生成物を当てにしない**)。`artifacts._capture` は `test_run_real.py` 56 行と同じく差し替える。
   項目: R8 の config の差分 4 欄 / R8 の config で data_checks 7 件 PASS(コミット済み manifest。items は要らない)/ 8,160 行・`classify` と `metrics_by_reference_rule` を例外に差し替えても通る / 行の欄(logp が採点器の返した値そのもの・`t`・`T = t + θ`・`truth`・併合セル)/ `answer` が `choose_from_logprobs` のまま(同点は No)/ `n_items_by_cell`(12 × 2 × 17 × 20)/ `kind` と「`_rate` を含む鍵が無い」/
   固定オフセットの経路(`execute`・`dry_run`・`evaluate_pool`・`load_pool_items`)は掃引のプールでも宣言でも止まり run dir を作らない / 掃引の経路は宣言なし・固定のプール・腕の食い違い・θ の食い違い・1 項目欠けで止まり、採点器を呼ばない / S(2,400 行)も同じ経路 / `main` の振り分け / pilot の config(B0)は今までどおり固定オフセットの経路で dry-run が通る

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **PLAN-026 §4.5(新)**: I4 の配線の読み 1〜6(読み1 = 新しい config + `eval.threshold_sweep_arm`。manifest の中身から経路を推測しない / 読み3 = 上位 k の欄はいま空けない / 読み4 = (d) を S の T1b 1,200 項目に絞る仕方は I8 で決める)。**人間は見ていないので覆せる**
- **掃引の manifest を anchor にしても preflight の data_checks は 7 件 PASS**(その56 に手元で確かめた。pilot の config の `eval.anchor_manifest` を `pilot_sweep_r8` に・`eval.batteries` を `[comparison]` にして。`pool disjoint` = pilot 240 組 × main 1,560 組の積が空)
- 既存の性質(読んで確かめた): `aggregate.py` は `kind != battery_eval` を数えずに飛ばす(飛ばした件数は報告)/ `frame.py` は止まる / `compare_runs.py` は `classification` を要るので掃引の predictions とは突き合わせられない(B0 と R8 の同じ `item_id` 240 項目の点検は I5・I11 の話)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §4.5 / §3.2(記録する量)/ §9 の I4 の行(実装したら「✅ 済」に)
- `code/eval/run.py`: 上の行番号の関数だけ。`code/eval/forced_choice.py` の `ForcedChoice` 72・`choose_from_logprobs` 265・`collect_forced_choices` 287(**読むだけ**)
- `code/data_gen/sweep_pool.py`(`load_sweep_settings` 108・`sweep_cells` 154・`FILL_THRESHOLD_SWEEP`・`POLARITIES`)/ `code/eval/battery/t3_comparison.py`(`task_type_of`・`polarity_of`・`comparison_answer`・`sweep_threshold`)
- `code/tests/test_run_real.py` 1〜210 行(差し替え可能な採点器の形)

## やってはいけないこと

- 掃引の項目を 4 値分解(`classify`・`metrics.json` の参照規則ごとのブロック)に入れる / 判定規則 `choose_from_logprobs` を変える / 上位 k の欄を足す(I10)
- GPU / main の push / I5 以降に手を広げる / (d) の絞り方を決める(I8)
- 主プール・パイロット用プール・掃引プール(`data/generated/battery/main*`・`pilot*`)と `data/raw/` を書き換える / 本番 config を変える
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。`write_bytes(...encode("utf-8"))` か Edit を使う。**Bash の heredoc に長い日本語の Python を流さない** —— スクリプトは Write ツールで scratchpad に書いてから実行する

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.5(I4 の配線の読み)に異議があるか** / **ADR-080 決定3(20 組を併合セルから取る)に異議があるか**(どちらも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I1〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
