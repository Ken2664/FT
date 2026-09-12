# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-12(その55)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の区切り**(PLAN-026 の I3 が済んだ。I4 は別のまとまり)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その55 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I4 = 掃引項目の記録の経路(CPU のみ。GPU 0)。**仕様は PLAN-026 §3.2(「記録するのは項目ごとの `yes_logp` / `no_logp` / 上位 k」)・§4.4・§9 の I4 の行(「`code/eval/run.py` の別経路 / `metrics.json` の新しい欄。`Δ̂` は後処理」):

1. **最初に仕様の穴を確かめる**: PLAN-026 は「run の宣言の仕方」を書いていない —— R8 の run を (a) 新しい config(例 `configs/exp_order6b_r8.yaml`。pilot の config の写しで `eval.anchor_manifest` を `data/generated/battery/pilot_sweep_r8/manifest.json` に)で回すのか、(b) 掃引であることを config の鍵で宣言するのか manifest の `fill.method == "threshold_sweep"` から読むのか。
   **名前・中身から推測しない**のがこの repo の流儀(`eval.counterpart_manifest` の前例。PLAN-026 §4.3)。**何を測るかが変わらない配線の選択なら、実装の読みとして PLAN-026 §4.5(新)に書いて進めてよい。測る内容・腕・件数に触れるなら実装せず人間に聞く**(code-style §5)
2. 掃引の項目を **4 値分解(`scoring.classify`)に通さず**、強制選択の forward だけを掛けて、項目ごとに `item_id`・タスク型・極性・`θ`(`params.threshold_offset`)・`t`・`yes_logp`・`no_logp` を `predictions/` に書く経路を作る。`metrics.json` には件数(セル × 極性 × θ)と `items_sha256` など来歴だけを置く(**率を出さない。`Δ̂` は I5 の後処理**)
3. **判定規則 `choose_from_logprobs` は触らない**(ADR-078 決定5)。上位 k は I10(欄をいま空けるかは 1 の読みと一緒に決める)
4. S(①・(d))も同じ経路を通る形にしておく。(d) の run は S の T1b 1,200 項目だけを使う(**絞り方は I4 か I8 で決める。PLAN-026 §4.4 の読み5**)

**完了条件**: GPU の無いテスト(`code/tests/test_run_real.py` の差し替え可能な生成関数・採点関数の形)で、R8 の掃引プールを解くと `classify` を呼ばずに項目ごとの logp が 8,160 行書かれる / 掃引の項目を固定オフセットの経路に渡すと止まる / R8 の config で `run.py --dry-run` と preflight の data_checks が通る(検査6・`pool disjoint` は掃引の manifest を anchor にしても PASS するはず。確かめる)/ `pytest code/tests -q` が通る(直近の実測は **1082 passed**。その55)。**I5(当てはめ。前に「階段の位置」の定義を PLAN-026 §3.2.1 に書く)は次のセッション**

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **掃引プールがある**(commit `36d37a5`。PLAN-026 §4.4): `python -m code.data_gen.sweep_pool --config configs/exp_order6b_pilot.yaml --arm r8|s` → `data/generated/battery/pilot_sweep_r8/`(**8,160 項目** = T3 4,080 + T1b 4,080・240 組)/ `pilot_sweep_s/`(**2,400 項目**。組は R8 と同じ・項目は R8 の部分集合)。**items.jsonl は git に無い** —— 手元には生成済み。無ければ config 冒頭のコマンドで作り直す(manifest の差分は 0 行になるはず)。θ の水準は pilot の config の `eval.threshold_sweep` にだけある
- **ADR-080**: G14(PLAN-026 §8 の注記)= 人間の記入で確定 / I1・I2 の読みを追認(`counterpart_hash` は None のまま)/ **R8・S の 20 組は gt・lt の 2 セルを併合した候補(80 組)から組の水準のハッシュで取る**(その55 の包括の承認で採った。人間は個別の案を見ていないので覆せる)。**その55 の包括の承認は その55 の作業に当てた。このセッションの判断には使わない**
- 記録した事実(組合せ論的): **R8 の 7,200 / 8,160 項目は `p2` で判別できない**(`classify` に通すと止まる)/ R8 の 240 項目はパイロット用プールの固定オフセットの項目と同じ `item_id`(B0 と R8 の一致の点検に使える。案。PLAN-026 §4.4)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.2(66 行付近)・§3.6(上位 k)・§4.4・§9 の I4・I10 の行。**行番号は開いて確かめる**
- `code/eval/run.py`: `pool_items_path` 682・`load_pool_items` 690・`prediction_record` 736(`classify` を呼ぶ)・`evaluate_batch` 788・`evaluate_pool` 878・`metrics_payload` 1053・`main` 1274 付近
- `code/eval/forced_choice.py`: `ForcedChoice` 72・`choose_from_logprobs` 265・`collect_forced_choices` 287・`_score_batch` 357 付近
- `code/data_gen/sweep_pool.py`(manifest の `fill` の形)/ `infra/preflight.py`(`load_anchor_manifest` 519・`load_counterpart_manifest` 543 付近)

## やってはいけないこと

- 掃引の項目を 4 値分解(`classify`・`metrics.json` の参照規則ごとのブロック)に入れる / 判定規則 `choose_from_logprobs` を変える
- GPU / main の push / I5 以降に手を広げる
- 主プール・パイロット用プール・掃引プール(`data/generated/battery/main*`・`pilot*`)と `data/raw/` を書き換える
- 本番の T1b・T3 の文面・#2 = 0.70・#3 の値を変える(ADR-078 決定1・2)
- Python の `Path.write_text` で `STATE.md` などを書く(Windows で CRLF になる)。`write_bytes(...encode("utf-8"))` か Edit を使う。**Bash の heredoc に長い日本語の Python を流すと引用の解釈で落ちることがある**(その55)—— スクリプトは Write ツールで scratchpad に書いてから実行する

## 未解決 / 人間の承認待ち

- **ADR-080 決定3(20 組を併合セルから取る)に異議があるか**(`logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I1〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
