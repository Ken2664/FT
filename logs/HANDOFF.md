# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-16(その62)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目完了 + コンテキスト超過**(PLAN-026 の I10 を実装・コミットした `0e556d0`。context-guard が約 341k で警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その62 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I11 = 順6b の集計(CPU のみ。GPU 0)。ただし I11 は 1 セッションに収まらない見込みなので、最初に分け方を決め、その 1 つ目だけを仕上げる。**

1. **範囲**(PLAN-026 §9 の I11 と STATE「次のアクション」1): `code/analysis/gonogo.py` の #1〜#3 をパイロットの run に掛ける / 極性別の参照線(ADR-078 決定7 (b))/ §5 の判定表(**(iv) はタスク型の 3 セルそれぞれ。ADR-081 決定3**。R8・S の遠いオフセットは `code/analysis/r8_fit.py` が既に出す)/ §7 の感度の行(近接同点 |差| ≤ 0.25 の件数と、除いた場合の #2。合否に使わない。ADR-079 決定8)/
   **(c) の補正を順6b の項目と R8 に掛ける経路**(`calibration.content_free_bias` / `calibrated_answer`。① の項目は `preamble.order_index(item_id, 4)` 番目の並びの `b`。PLAN-026 §4.9 読み7。固定オフセットの行の `yes_logp` / `no_logp` は値そのもの = ADR-084 決定3)/ **① と (d) と (c) の run を B0 と混ぜない集計**
2. **実装の前に読みを PLAN-026 §4.11(新)に書く**: 分け方(例: 判定表の土台と参照線 → 補正の適用 → 判定表の組み立て)/ 入口(新しい CLI か既存の `gonogo.py` を広げるか)/ run の見分け方(`metrics.json` の `kind`・`preamble`・`task_subset`・`experiment.id` のどれで腕を決めるか)/ 出力の形。
   **形が複数ありうる所は `AskUserQuestion` で人間に選択式で聞く**(`CLAUDE.md` §8。I8〜I10 はそうした)。**判定表は §5 を機械的に当てるだけで、解釈はしない**
3. **注意**: §5 の選び方は**まだ凍結していない**(tag は I12・dry-run の後)。§5 の値(#2 = 0.70・#3・(iv) の 0.70)は変えない。**§5 の文面の穴を見つけたら、実装で埋めずに人間に上げる**

**完了条件**: 読みが §4.11 に書かれ、人間に聞くべき所は聞いた / 決めた 1 つ目の部分が動き、テストがある(**手元の run は無いので、合成した run ディレクトリで通す**。`test_r8_fit.py`・`test_top_k.py` の作り方が前例)/ `pytest code/tests -q` が通る(直近の実測は **1325 passed**。その62。全体で約 3 分)/ 本番の文面・`data/raw/`・プール・順6b の config の判定に効く欄を 1 バイトも変えていない

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I10 は実装済み**(`0e556d0`)。**ADR-084**(提案 エージェント / 採択 人間。選択式。3 点とも推奨):
  決定1 k は順6b の config 7 本にだけ `eval.forced_choice_top_k: 20`(本番・smoke には無い)/ 決定2 綴りは `tokenizer.decode([id])` / 決定3 固定オフセットの二値群の行に `yes_logp` / `no_logp` の値そのもの
- 記録の形: 3 経路(固定オフセットの `predictions/*.jsonl` の二値群の行・掃引の `predictions/threshold_sweep.<タスク型>.jsonl`・較正の `calibration.json`)の行に `top_k` = `[{id, text, logp}]`(降順)・`top_k_mass`(確率の合計)。宣言なしは null。`metrics.json` の `forced_choice.top_k`
- **判定は `choose_from_logprobs` が同じ行で先に決め、上位 k は後から付くだけ**(`forced_choice.choices_from_rows`)。上位 k は記述だけで合否に使わない(ADR-079 決定5)
- 差し替え採点器で順6b の config を回すテストは `code.tests.test_top_k.with_filler_top_tokens` で上位 k の置き物を返す(`collect_forced_choices` が宣言と個数の食い違いで止めるため)。**順6b の config を使う新しいテストもこれを使う**
- 実装の読みは PLAN-026 §4.10、I9 は §4.9、I8 は §4.8

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §5・§6・§7・§9 の I11・§4.9 読み6・読み7・§4.10 読み7(`grep -n '^## 5\|^## 6\|^## 7\|^| I11\|^### 4.9\|^### 4.10' plans/PLAN-026-order6b.md`)
- `code/analysis/gonogo.py`(#1〜#3 の既存の実装)/ `code/analysis/r8_fit.py`(遠いオフセットと当てはめ)/ `code/eval/calibration.py` の `content_free_bias`・`calibrated_answer` / `code/eval/preamble.py` の `order_index`(どれも `grep -n 'def '` から)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、torch・transformers は無い。ruff / black も無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- §5 の値・判定規則(`choose_from_logprobs`)・4 値分解を変える / 結果を解釈する(`CLAUDE.md` §8)/ GPU / main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。bytes で読み書きする。**長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **書き込みを伴うスクリプトは、検査をすべて済ませてから書く**。**作業ツリーの一部のファイル(`code/eval/forced_choice.py`・`engine.py`・`code/tests/test_run_real.py`・`test_forced_choice.py` ほか)は CRLF**(git は `eol=lf` で正規化する)—— バイト列で置き換えるときは改行を合わせる(その62 で 1 度一致せずに止まった)
- Write / Edit ツールに `�` のようなエスケープを書くと実の文字になることがある(その62)。`chr(0xFFFD)` で書く
- 説明の根拠を確かめずに「原典どおり」と書く(その61)

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.10(I10 の読み)/ §4.9(I9。とくに読み1 = 較正を別の CLI にしたこと・読み7 = `b` を並びごとに持つこと)/ §4.8 / §4.7 / §4.6 / §4.5 / ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I11・I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11。**run 数は 6 → 7 に直してから諮る**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
