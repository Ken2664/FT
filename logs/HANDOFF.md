# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-15(その59)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 2 項目完了 + コンテキスト超過**(PLAN-026 の I6・I7 を実装・コミットした `96dcf26`。context-guard の実測で約 31.5 万トークン)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その59 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I8 = (d) のテンプレート集合と、パイロット用プールの絞り方(CPU のみ。GPU 0)。**

1. **絞り方を 1 つの仕組みで決める**(人間の回答 = その59「I8 で (d) と一緒に決める」。PLAN-026 §4.7 の仕様の穴):
   - 固定オフセットの ① の run = パイロット用プール 1,640 項目のうち **3 群(比較・T1 `bare_sum`・T2 `word_problem`)= 960 + 480**
   - 固定オフセットの (d) の run = **T1b だけ 480**(比較群の中のタスク型)/ S-(d) の run = **S のプールの T1b だけ 1,200**(掃引の経路)
   - いまの `run.py` の `_read_pool_items` は `eval.batteries` の外の群があると止め(黙って項目数が減るのを防ぐ門)、掃引の経路は manifest の `fill.task_types` をすべて解く(§4.5 の読み4)。
     **宣言で絞り、外した群・タスク型と件数を `metrics.json` に残す**形が自然(案)。**鍵の形が決まらなければ、実装せず PLAN に案を書いて人間に聞く**(`AskUserQuestion`。`CLAUDE.md` §8)
2. **(d) のテンプレート集合**: `t1b_gt: "{a}+{b}>{threshold}? Answer Yes or No."` / `t1b_lt: "{a}+{b}<{threshold}? Answer Yes or No."`(PLAN-026 §3.4。付け足す一文は `configs/templates/t3.yaml` の末尾と同じ文字列)を**順6b 専用の集合**として `configs/templates/` に置く。**本番の `t1b.yaml` と `eval_main.yaml` は触らない**
3. config を作る: 固定オフセットの ① の run(`eval.preamble` + 3 群)/ (d) の run(T1b だけ + (d) の集合)/ S-(d) の run(S の T1b だけ + (d) の集合)。前例は `configs/exp_order6b_r8.yaml`・`exp_order6b_s_preamble.yaml`(写しで、差は冒頭の注記の欄だけ。差をテストで固定)

**完了条件**: 3 本の config で `python -m code.eval.run --config <cfg> --dry-run` が通り件数が 1,440 / 480 / 1,200 / 絞りの宣言が無い run(B0・R8・S-①)の項目と文面が 1 バイトも変わらない(`test_preamble.py` の `PROMPTS_SHA256_BEFORE_I6` の型)/ 外した群・件数が `metrics.json` に残る / preflight の data_checks が通る / `pytest code/tests -q` が通る(直近の実測は **1184 passed**。その59。全体で約 2〜4 分)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I6・I7 は実装済み**(`96dcf26`)。鍵 `eval.preamble` = 行のリスト(無い / null = なし)/ 被せる場所は `run.render_prompts` の 1 か所(固定オフセットの `dry_run`・`evaluate_pool` と掃引の `threshold_sweep_prompts` が通る)/ 並びは `sha256(canonical_json(["preamble_order", item_id])) mod 24` の辞書順(`code/eval/preamble.py`)/ `metrics.json` の `preamble` 欄はすべての run で置く(無ければ null)/ preflight の検査6 は前置きのある run で SKIP(`format_hash_result`)。読みは PLAN-026 §4.7
- **S-① の config は `configs/exp_order6b_s_preamble.yaml`**(R8 の config との差 4 欄)。**S-(d) は別の config になるので §10・§11 の run 数は 6 → 7**(項目・回は 15,626 のまま。§11 の文面は承認を求めるときに直す。§4.7 読み5)
- 前置きを宣言してよい config は `code/tests/test_preamble.py` の `PREAMBLE_CONFIGS` が固定している(**① の config を足したらここも足す**)
- **(d) の文面は前置きを持たない**(① と (d) は別の腕。1 つの run は 1 つの文面の組)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.4(148〜153 行付近)/ §4.5 の読み4 / §4.7 / §9 の I8(`grep -n '^### 4.7\|^| I8' plans/PLAN-026-order6b.md`)
- `code/eval/run.py` の `_read_pool_items`・`load_threshold_sweep_pool`・`render_prompts`・`load_group_templates`(`grep -n 'def _read_pool_items\|def load_threshold_sweep_pool\|def render_prompts\|def load_templates' code/eval/run.py`)/ `configs/templates/t1b.yaml`・`t3.yaml`(**読むだけ**)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、statsmodels は無い

## やってはいけないこと

- 本番の T1b・T3(と T1・T2)のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- 絞りのために**プールを作り直す / 別のプールを書き出す**のは避ける(同じ項目が別の manifest に入り、preflight の非交差・`items_sha256` の照合が割れる。**エージェントの読みであって人間の決定ではない** —— 採るなら人間に聞く)
- ADR-030・ADR-079・ADR-081 の中身を変える / I9((c))・I10(上位 k)・I11(判定表)まで手を広げる / GPU / main の push
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。追記は Python で bytes を連結する。**長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **`infra/preflight.py` は作業ツリーで CRLF になっていたことがある**(その59 に LF に揃えた)。編集の前後で Python で `b"\r\n"` を数える。**awk の `length` はバイト数**(日本語は 3 倍に数える)。行長は Python の `len` で見る

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.7(I6・I7 の読み。とくに読み6 = 検査6 を SKIP・読み5 = run 数 7)/ §4.6(I5)/ §4.5(I4)/ ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I1〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
