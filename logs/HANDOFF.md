# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-16(その61)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目完了 + コンテキスト超過**(PLAN-026 の I9 を実装・コミットした `4d80fcb`。context-guard が約 345k で警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その60 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I10 = 最初の出力位置の上位 k の記録(CPU のみ。GPU 0)。**

1. **仕様**(PLAN-026 §3.6・§9 の I10。ADR-078 決定5 / ADR-079 決定7 = **k = 20**): すべての強制選択の forward で、最初の出力位置の log-softmax の上位 k の (id, 復号した綴り, logp) と、上位 k の確率の合計を記録する
   - **判定規則(`choose_from_logprobs`)は変えない**。全語彙の log-softmax 行は `_score_batch` に既にある
   - 触る場所の候補: `code/eval/forced_choice.py` の `_score_batch`・`ForcedChoice` / `code/eval/run.py` の `prediction_record`・`threshold_sweep_record`・`metrics_payload`(`grep -n 'def _score_batch\|^class ForcedChoice\|def prediction_record\|def threshold_sweep_record\|def metrics_payload'`)
2. **実装の前に読みを PLAN-026 §4.10(新)に書く**(k をどこに置くか = config の鍵にするか / 復号をどこで行うか(トークナイザが要る。テストは重みもトークナイザも読まない)/ 固定オフセット・掃引・**(c) の較正(`code/eval/calibration_run.py`)の 3 経路のどれに載せるか** / 記録の欄の名前)。
   **形が複数ありうる所は `AskUserQuestion` で人間に選択式で聞く**(`CLAUDE.md` §8。前のセッションは I8・I9 でそうした)
3. **注意**: `ForcedChoice` の形を変えると、差し替え採点器を作るテスト(`test_task_subset.py`・`test_preamble.py`・`test_threshold_sweep_run.py`・`test_calibration.py` ほか)が一斉に影響を受ける。既存の既定値を足して互換を保つか、どこで欄を足すかを先に決める
4. **判定表(§5)・極性別の参照線・(c) の補正を順6b の項目と R8 に掛ける経路は I11。ここでは作らない**

**完了条件**: 読みが §4.10 に書かれ、人間に聞くべき所は聞いた / 上位 k の記録が PLAN の形で出る経路が動く / 判定(answer)と `yes_logp` / `no_logp` が 1 ビットも変わらないことをテストが固定する / `pytest code/tests -q` が通る(直近の実測は **1289 passed**。その61。全体で約 4〜5 分)/ 本番の文面・`data/raw/`・プールを 1 バイトも変えていない

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I9 は実装済み**(`4d80fcb`)。**ADR-083**(提案 エージェント / 採択 人間。選択式):
  決定0 (c) の記号 `N/A`・`[MASK]`・空文字は Zhao et al. (2021) §5 の原典と綴りが一致 / 決定1 空文字は literal に差し込む /
  決定2 3 種は**生の確率を平均してから正規化**(`b = logmeanexp_s(yes_logp) − logmeanexp_s(no_logp)`。論文本文は順を書かず、第一著者の実装がこの順)。判定 `(yes − no) − b > 0`・同点は No
- 較正の入口は**評価プールを読まない別の CLI** `python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml`(306 件 = b0 12 / d 6 / preamble 288)。
  記録は `calibration.json`(入力ごとの `yes_logp` / `no_logp`)+ `metrics.json`(`kind: calibration`)。`code.eval.run` の両経路と桁数掃引は較正の config を拒む。読みは PLAN-026 §4.9
- 後処理の関数 `calibration.content_free_bias` / `calibrated_answer` はある(単体テストのみ)。**① の項目には `preamble.order_index(item_id, 4)` 番目の並びの `b` を引く**(§4.9 読み7。I11 で使う)
- 前置きの連結は `preamble.with_preamble_order` 1 か所。`run.run_header_lines` の先頭 5 行は `run.provenance_lines` に切り出した(出力は同じ)
- 前置きを宣言する config は `test_preamble.py` の `PREAMBLE_CONFIGS`、絞りは `test_task_subset.py` の `SUBSET_CONFIGS`、較正は `test_calibration.py` が固定している(**config を足したらここも足す**)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.6(171 行付近)/ §4.9 / §9 の I10(`grep -n '^### 3.6\|^### 4.9\|^| I10' plans/PLAN-026-order6b.md`)
- `code/eval/forced_choice.py`(`_score_batch`・`ForcedChoice`・`candidate_token_map`)/ `code/eval/run.py` の記録の関数 / `code/eval/calibration_run.py`(読むだけでよい)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、torch・transformers は無い(`_score_batch` は torch を関数内で import する)。ruff / black も無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- 判定規則(`choose_from_logprobs`)・4 値分解・#2 = 0.70・#3 の値を変える / I11(判定表・参照線・補正の適用)まで手を広げる / GPU / main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。bytes で読み書きする。**長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **書き込みを伴うスクリプトは、検査をすべて済ませてから書く**(その61 で、検査の前に STATE.md を書いてから落ちるスクリプトを 2 度走らせ、`git checkout -- STATE.md` で戻した)。`logs/STATE-ARCHIVE.md` は末尾に改行が無いことがある
- 説明の根拠を確かめずに「原典どおり」と書く(その61 で ADR-083 決定2 の選択肢の説明を誤り、聞き直した)

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.9(I9 の読み。とくに読み1 = 較正を別の CLI にしたこと・読み7 = `b` を並びごとに持つこと)/ §4.8(I8)/ §4.7(I6・I7)/ §4.6(I5)/ §4.5(I4)/ ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I10〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11。**run 数は 6 → 7 に直してから諮る**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
