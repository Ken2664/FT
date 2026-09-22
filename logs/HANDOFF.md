# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その64)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目の区切り + コンテキスト超過**(PLAN-026 の I11b を実装・コミットした `a0acb30`。context-guard が約 318k で警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その64 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I11c = §5 の判定表と、① と (d) の run を B0 と混ぜない守り(CPU のみ。GPU 0)。**I11 は ADR-085 決定1 で I11a(済)→ I11b(済)→ **I11c** に分けてある。

1. **読みを PLAN-026 §4.13(新)に書いてから実装する。**中身は 2 つ:
   - **(A) 新しい CLI `code/analysis/order6b_select.py`**(名前は ADR-085 決定2 の案)。**腕は引数で明示**(`--b0` `--r8` `--preamble` `--s-preamble` `--d` `--s-d` `--c`)し、各 run の記録(`kind`・`preamble`・`task_subset`・`threshold_sweep.arm`・config の `data.eval_template_set`・`pool_id`・`adapter` = null)が腕の形と合わなければ止める(**名前からは推測しない**。ADR-085 決定3)。
     候補 → 腕: **C0** = B0 + R8 / **C3** = B0 + R8 に `b0` の偏り / **C2** = (d) + S-(d) / **C1** = ① + S-①。ほかに**記述として** ①+(c)(preamble の偏り)と (d)+(c)(d の偏り)を出す(**§5 の候補ではない**。ADR-086 決定1)
   - **(B) 混ぜない守り**: `aggregate.py` は `eval.preamble` か `eval.task_subset` を宣言した run を見つけたら**止め、順6b 専用の入口を名指しする**(ADR-086 決定5)。**`frame.py` の列は変えない**
2. **判定は §5 を機械的に当てるだけ**(タスク型ごとに (i) #2 の 3 セル / (ii) #3 の 3 セル / (iii) C1 だけ ①-num で T1・T2 の 6 セルが #1 と #2 / (iv) 遠いオフセットの correct が**セルごとに**両側 0.70 以上。ADR-081 決定3)。**表の順で最も小さい候補**(C0 < C3 < C2 < C1)を採る。
   **候補が 1 つも無いタスク型は `selected = null` + `no_candidate` の印にし、`preamble_mismatch` は null**(両方に候補があるときだけ true / false。ADR-086 決定4)。**解釈はしない**(`CLAUDE.md` §8)
3. **呼べる関数はもうある**(自分で数え直さない): `gonogo.run_report` / `gonogo.calibrated_run_report` / `r8_fit.run_report` / `r8_fit.calibrated_run_report` / `r8_fit.load_sweep_run` / `calibrated.load_calibration`・`bias_lookup`・`check_arm`

**完了条件**: 読みが PLAN-026 に書かれた / 判定表の CLI が動き、テストがある(**手元の run は無いので合成した run ディレクトリで通す**。前例は `code/tests/test_calibrated.py` の `order6b` フィクスチャ —— パイロット用プールと S の掃引プールを tmp に書き、B0・①・(d)・S・(c) を固定応答で本実行する)/ `aggregate.py` の守りとテスト / `pytest code/tests -q` が通る(直近の実測は **1402 passed**。その64。全体で約 4〜5 分)/ 本番の文面・`data/raw/`・プール・順6b の config の判定に効く欄を 1 バイトも変えていない

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-086**(提案 エージェント / 採択 人間。選択式。**5 問とも推奨**): 決定1 (c) の補正は **3 腕すべて**に掛け ①+(c)・(d)+(c) は記述(§5 の候補の集合は変えない)/ 決定2 **C3 の近接同点は補正後の差** `|(yes − no) − b| ≤ 0.25` / 決定3 **掃引にもセル × 遠いオフセットの側ごとの近接同点と除いた correct**(合否に使わない)/ 決定4 **候補なしは別の印**(I11c)/ 決定5 **`aggregate.py` は止める**(I11c)
- **I11b は実装済み**(`a0acb30`。読みは PLAN-026 §4.12): `code/analysis/calibrated.py`(新規)/ `gonogo.calibrated_run_report`(**#1 は出さない**)/ `r8_fit` の `SweepRun`・`load_sweep_run`・`sweep_gaps`・`near_tie_table`・`near_tie_report`・`calibrated_run_report`・`_near_tie_lines`
- **補正後の記録の形**: 二値群は `parsed` を差し替えて `classification` を `scoring.classify` で付け直す / 掃引は `answer` を差し替える。どちらも **`yes_logp` / `no_logp` は値そのもののまま**で `bias` と `gap_after` が足される。**数値群の行は 1 バイトも変わらない**
- **`r8_fit.run_report` に `near_tie` 欄が増えた**(幅を宣言した run だけ。当てはめ・除外件数・遠いオフセットの correct は不変)
- **`code/eval/calibration.py`(後処理の定義の正本)は 1 バイトも変えていない**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.7・§4.6・§4.11・§4.12・§5・§6・§7・§9(`grep -n '^### 4.11\|^### 4.12\|^## 5\|^## 6\|^## 7' plans/PLAN-026-order6b.md`)
- `code/analysis/calibrated.py`(全体。352 行)/ `code/analysis/gonogo.py` の `run_report`・`calibrated_run_report`・`build_report` / `code/analysis/r8_fit.py` の `load_sweep_run`・`run_report`・`calibrated_run_report`・`far_offsets_from_config` / `code/analysis/aggregate.py`(どれも `grep -n 'def '` から)
- `code/tests/test_calibrated.py` の `order6b` フィクスチャ(合成 run の作り方の前例)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、torch・transformers は無い。ruff / black も無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- §5 の値(0.70・−2・+3)・判定規則(`choose_from_logprobs`)・4 値分解・**§5 の候補の集合**を変える / 結果を解釈する(`CLAUDE.md` §8)/ GPU / main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**その64 でこれを踏み、`test_repo_hygiene.py` が落ちた。**必ず `write_bytes` で書く**
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **Edit ツールの置換で行末の空白が落ちることがある**(その63)。表示の文字列を分けるときは結果の行を確かめる
- **変異の検査を裏で回している間は、対象のファイルとテストを編集しない**(スクリプトが対象を書き換えて元に戻す)
- **変異の検査は「落ちた」だけで満足しない。**その64 は 26 個中 5 個がすり抜けた(境界・空の側・重複・来歴の絞り込み・補正の前後の取り違え)。**すり抜けたらテストを足す**
- 説明の根拠を確かめずに「原典どおり」と書く(その61)

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.12(I11b の読み)/ §4.11 / §4.10 / §4.9(とくに読み1・読み7)/ §4.8 / §4.7 / §4.6 / §4.5 / ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I11c・I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11。**run 数は 6 → 7 に直してから諮る**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
