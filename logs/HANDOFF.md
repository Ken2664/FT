# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-14(その58)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目完了 + コンテキスト超過**(PLAN-026 の I5 を実装・コミットした `9776ff8`。開始手順だけで約 15 万トークン、終了時は約 30 万)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その58 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I6・I7 = ① の前置き(①-bin・①-num・S の ①)の配線(CPU のみ。GPU 0)。**

1. **I6**: 新しい鍵(PLAN の例は `eval.preamble`)で、ADR-079 決定3 の 4 行(PLAN-026 §3.3)を**全群の入力の先頭に空行を挟んで連結**する。並びは項目ごとに `item_id` のハッシュで 24 通りから選ぶ。`metrics.json` に前置きの有無と sha256 を残す。
   **`eval.few_shot_k` の門(`code/eval/model.py` 150 行)は使い回さない**(PLAN-026 §9 の I6)。文面は `load_group_templates` + `RENDERERS` を通るので、固定オフセットの経路と掃引の経路で**同じ所**で被せる(§4.5 の読み4)
2. **I7**: `infra/preflight.py` の検査6(評価アンカーの書式ハッシュ。`infra/preflight.py` 520・713 行付近)は、前置きのある run を「アンカーでない」と宣言して比較から外し、その旨を記録する(案。§9 の I7 / §8 の注記 4 = G15 は順6b の後)。**前置きの無い T1 のアンカーは変えない**
3. ①-bin・①-num・S の ① の run の config を作るか(作るならいくつ・どの差分か)は **PLAN に読みとして書く**(前例: `configs/exp_order6b_r8.yaml` は pilot の写しで差は 4 欄。§4.5 の読み1)。**①-num は T1(`bare_sum`)・T2(`word_problem`)だけ**(PLAN-026 §3 の表)

**完了条件**: 前置きの連結・並びのハッシュ(24 通り・決定的)・全タスク型で同じ文字列・前置きの無い run が 1 バイトも変わらないこと・`metrics.json` の記録・preflight 検査6 の扱いがテストで固定される(I12)/ 仕様の穴を見つけたら**実装せず PLAN に書いて人間に聞く**(`AskUserQuestion`。`CLAUDE.md` §8)/ `pytest code/tests -q` が通る(直近の実測は **1144 passed**。その58。全体で約 4 分)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I5 は実装済み**(`9776ff8`)。「階段の位置」= `(L + U) / 2`・片側だけは除外して別に数える・§5 (iv) の判定の単位はセル —— **ADR-081(提案 エージェント / 採択 人間)**。定義は PLAN-026 §3.2.1.1、実装の読みは §4.6
- 入口: `python -m code.analysis.r8_fit --runs <glob> [--ident-run <run>] [--out-dir <dir>]`。遠いオフセットの境界(−2・+3)は run の config の `eval.threshold_sweep.offsets.s` から導く(**S の θ の水準を変えると境界も動く**)
- **`metrics.json` の `lesion_condition` は config の `lesion.condition` の値そのもので、adapter = null の run でも p2 と出る**(`code/eval/run.py` 1740 行。pilot・R8 の config は `condition: p2`)
- **GPU の無いテストで「内部の値 `t + Δ` で答える採点器」を本物の経路に通す手本**: `code/tests/test_r8_fit.py` の `shifted_model_scorer`(`run.threshold_sweep_prompts` で文面 → 項目を引く)と `sweep_runs` fixture。パイロット用プールの組み直しは `test_threshold_sweep_run.py` の `pool_dirs` と同じ(約 8 秒)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.3(129〜147 行)/ §4.5 の読み4(258 行)/ §8 の注記 4(361 行)/ §9 の I6・I7・I8(380〜382 行)
- `logs/DECISIONS.md` ADR-079 決定3(`grep -n '### 決定3(★G3・★G4)' logs/DECISIONS.md`)/ ADR-078 決定8(数値型にも同じ前置き)
- `code/eval/run.py` の文面の組み立て(`grep -n 'def load_group_templates\|RENDERERS\|def threshold_sweep_prompts\|def build_prompts' code/eval/run.py`)/ `code/eval/model.py` 150 行付近(few_shot の門。**読むだけ**)/ `infra/preflight.py` 検査6
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、statsmodels は無い。`infra/requirements.lock` はポッド側(numpy 2.1.2 / scipy 1.18.1 / statsmodels 0.15.0)

## やってはいけないこと

- 本番の T1b・T3(と T1・T2)のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2。前置きは順6b 専用の腕の文面)
- ADR-030・ADR-079・ADR-081 の中身を変える / I8((d))・I9((c))・I10(上位 k)・I11(判定表)まで手を広げる / GPU / main の push
- 実験結果でない数値を文書に書く(テストの合成データの値を結果として書かない)
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。追記は Python で bytes を連結する(その58 の CHANGELOG・DECISIONS の追記はこの形)。**長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **CRLF の確かめは Python で `b"\r\n"` を数える**(Git Bash の `grep -c $'\r'` を `"$(…)"` の中で使うと全行を数える)

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.6(I5 の実装の読み。とくに読み2 = 遠いオフセットの境界を S の θ の水準から導く)に異議があるか** / §4.5(I4 の配線の読み)/ ADR-080 決定3(包括の承認で採った)に異議があるか(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I1〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
