# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-16(その63)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目の区切り + コンテキスト超過**(PLAN-026 の I11a を実装・コミットした `af6725a`。context-guard が約 356k で警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その63 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I11b = (c) の補正の適用(CPU のみ。GPU 0)。**I11 は ADR-085 決定1 で I11a(済)→ **I11b** → I11c に分けてある。

1. **最初に人間に選択式で聞く**(`AskUserQuestion`。PLAN-026 §4.11 の末尾「I11b・I11c の前に人間に上げること」の 5 点。I11b に効くのは少なくとも 1〜3):
   (1) (c) の補正を ① と (d) の項目(と S-①・S-(d))にも掛けて表を出すか —— §5 の候補は C3 = いまの文面の較正だけで、①+(c)・(d)+(c) は候補に無い(ADR-079 決定6)が、(c) の run は ① と (d) の文面も較正している /
   (2) C3 の近接同点を補正前の差で数えるか、補正後の差(`(yes_logp − no_logp) − b`)で数えるか /
   (3) 掃引(R8・S)にも近接同点の件数を出すか(§4.6 読み5)/
   (4) 片方のタスク型に満たす候補が無い場合の「T3 と T1b で ① の有無が食い違う」の扱い(§5)/
   (5) `aggregate.py`・`frame.py` で ① と (d) の run を B0 と混ぜない守りの形(止める / 腕の列を足して分ける)。
   **(4)(5) は I11c の話なので、今聞くか I11c の前に聞くかも含めて決めてよい。**§5 の文面の穴を見つけたら、実装で埋めずに人間に上げる
2. **読みを PLAN-026 §4.12(新)か §4.11 の続きに書いてから実装する**: `calibration.content_free_bias`(鍵 = (腕 × category × 並び))/ `calibrated_answer` を
   固定オフセットの二値群の行(`yes_logp` / `no_logp` は値そのもの。ADR-084 決定3)と掃引の行(`code/analysis/r8_fit.py` の記録)に掛け、補正後の 4 値のセル表と、補正後の遠いオフセットの correct を出す関数。
   腕の対応: B0 と R8 = `b0`(並びは null)/ ① と S-① = `preamble`(項目ごとに `preamble.order_index(item_id, 4)`。PLAN-026 §4.9 読み7)/ (d) と S-(d) = `d`。どの組を出すかは (1) の答えに従う。
   **置き場所は ADR-085 決定2 に沿う**(判定表の新しい CLI `code/analysis/order6b_select.py` の案が呼ぶ関数。I11c の CLI 本体はまだ作らない)
3. **注意**: §5 はまだ凍結していない(tag は I12・dry-run の後)。§5 の値(#2 = 0.70・#3・(iv) の 0.70)・判定規則(`choose_from_logprobs`)・4 値分解は変えない。**判定表は §5 を機械的に当てるだけで、解釈はしない**

**完了条件**: 人間に聞くべき所は聞いた / 読みが PLAN-026 に書かれた / 補正の適用が動き、テストがある(**手元の run は無いので合成した run ディレクトリで通す**。前例は `code/tests/test_gonogo.py` の `order6b_runs`(パイロット用プールを tmp に書き B0・①・(d) の config で固定応答の本実行)と `test_r8_fit.py` の `sweep_runs`・`test_calibration.py`)/ `pytest code/tests -q` が通る(直近の実測は **1363 passed**。その63。全体で約 3 分)/ 本番の文面・`data/raw/`・プール・順6b の config の判定に効く欄を 1 バイトも変えていない

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-085**(提案 エージェント / 採択 人間。選択式。4 問とも推奨): 決定1 I11 = I11a run 単位の表 → I11b (c) の補正の適用 → I11c §5 の判定表と混ぜない守り / 決定2 判定表は新しい CLI が `gonogo.py` と `r8_fit.py` の関数を呼ぶ / 決定3 腕は引数(`--b0` `--r8` `--preamble` `--s-preamble` `--d` `--s-d` `--c`)で明示し、各 run の記録(`kind`・`preamble`・`task_subset`・`threshold_sweep.arm`・config の `data.eval_template_set`・`pool_id`・`adapter` = null)と照合して止める / 決定4 `gonogo.near_tie_margin: 0.25` を順6b の config 7 本に
- **I11a は実装済み**(`af6725a`。読みは PLAN-026 §4.11): `gonogo.py` の `solved_main_task_types`・`check_rows_within`・`provenance_record`・`polarity_reference`・`near_tie_margin_from_config`・`forced_choice_gaps`・`near_tie_table`。`cell_table` / `constant_strategy_table` は `task_types=` を要る(既定値なし)。**#1〜#3 の印は変えていない**
- **`expand_metrics_paths` は run のパスを並べ替える**(報告の run の順は渡した順ではない)。テストで腕を引くときは `provenance.experiment_id` で引く
- **`aggregate.py` はまだ前置き・絞りを見ない**(① と (d) の run を B0 と同じ行に並べうる。I11c まで順6b の run を通さない)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.5・§4.9 読み6・読み7・§4.11・§5・§7(`grep -n '^### 3.5\|^### 4.9\|^### 4.11\|^## 5\|^## 7' plans/PLAN-026-order6b.md`)
- `code/eval/calibration.py` の `content_free_bias`・`calibrated_answer`・`calibration_row` / `code/eval/preamble.py` の `order_index` / `code/analysis/gonogo.py`(I11a)/ `code/analysis/r8_fit.py` の `far_offset_correct`・`fit_records`・`check_records`(どれも `grep -n 'def '` から)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、torch・transformers は無い。ruff / black も無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- §5 の値・判定規則(`choose_from_logprobs`)・4 値分解を変える / 結果を解釈する(`CLAUDE.md` §8)/ GPU / main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。bytes で読み書きする。**長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **書き込みを伴うスクリプトは、検査をすべて済ませてから書く**。作業ツリーの一部のファイル(`code/eval/forced_choice.py`・`engine.py`・`code/tests/test_run_real.py`・`test_forced_choice.py` ほか)は CRLF(git は `eol=lf` で正規化する)—— バイト列で置き換えるときは改行を合わせる
- **Edit ツールの置換で行末の空白が落ちることがある**(その63 で f 文字列の区切りの空白が消えた)。表示の文字列を分けるときは結果の行を確かめる
- **変異の検査を裏で回している間は、対象のファイルとテストを編集しない**(スクリプトが対象を書き換えて元に戻す)
- 説明の根拠を確かめずに「原典どおり」と書く(その61)

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.11 の「I11b・I11c の前に人間に上げること」5 点**(上の 1)
- **PLAN-026 §4.11(I11a の読み)/ §4.10 / §4.9(とくに読み1・読み7)/ §4.8 / §4.7 / §4.6 / §4.5 / ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I11・I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11。**run 数は 6 → 7 に直してから諮る**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
