# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-12(その54)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の区切り**(PLAN-026 の I1・I2 が済んだ。I3 以降は別のまとまり)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その54 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I3 = R8・S の掃引項目の生成と配線(CPU のみ。GPU 0)。**仕様は PLAN-026 §3.2(R8)・§3.7(S)・§4.2:

1. **最初に仕様の穴を 1 つ確かめる**: §3.2 は「(タスク型 × 既知性 × `carry`)セルから 20 組」だが、パイロット用プールのセルは**極性ごと**(`t3_gt_id_carry` / `t3_lt_id_carry` …。各 40 組)に分かれている。20 組を gt・lt のどちらのセルから(または和集合から)取るのかが書かれていない。**PLAN-026・ADR-030 決定4(`logs/DECISIONS.md` 1288 行付近)を開いて決まっていなければ、実装せず人間に聞く**(code-style §5)
2. `θ` の水準集合を config に置く(R8 = `{-3, …, +13}` の 17 水準 / S = `{-3, -2, +3, +7, +13}`。**コードに直書きしない**)。組は**組 `(a, b)` の水準のハッシュ**で 20 組(§3.2 の案)
3. `build_items(sweep=True)` に `θ` を渡す新しい入口を作る(`build.py` の `build_items_from_entries` は `sweep` を渡さない)。掃引の項目は `data/generated/battery/pilot_sweep/` など**別ファイル**に書き、固定オフセットの項目と混ぜない。**4 値分解には入れない**(非判別項目で `scoring.classify` が止まる)
4. S は同じ入口で「組 × 極性 × 5 水準」の基本集合(タスク型ごとに 1,200)を作れるところまで。**① / (d) の文面を被せるのは I6・I8**(まだ無い)

**完了条件**: テストが件数を固定する(**R8 = T3 4,080 + T1b 4,080 = 8,160**、S の基本集合 = T3 1,200 + T1b 1,200)/ 組の選び方が決定的 / `pytest code/tests -q` が通る(直近の実測は **1049 passed**。その54)/ 生成物の manifest をコミット。**I4(記録の経路)・I5(当てはめ。前に「階段の位置」の定義を PLAN-026 §3.2.1 に書く)は次のセッション**

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **パイロット用プールがある**(commit `8e5e24f`。PLAN-026 §4.3): `configs/exp_order6b_pilot.yaml` → `data/generated/battery/pilot/manifest.json`(1,640 項目・1,560 組。群ごと・セルごとの件数は主プールと同じ)+ pilot の FT manifest 5 条件(`data/generated/ft/exp_order6b_pilot_<c>/`)。**items.jsonl / train.jsonl は git に無い** —— 手元には生成済み。無ければ config 冒頭のコマンドで作り直す(評価プールの manifest は差分 0 行になるはず)
- preflight の data_checks は **7 件**(`pool disjoint` を足した)。相手のプールは `eval.counterpart_manifest` で宣言する(4 本の config に記入済)。pilot・本番・t2cross で 7 件 PASS
- 実装の読み(`eval.counterpart_manifest` を本番 config に足した / 掃引で SKIP / `counterpart_hash` は None のまま)は人間が覆せる(`logs/OPEN-ITEMS.md` の「PLAN-026 G14 の記入 / I1・I2 の実装の読み」)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.2(65 行付近)・§3.7(131 行付近)・§4.2(160 行付近)・§9 の I3 の行。**行番号は開いて確かめる**
- `code/eval/battery/t3_comparison.py`(`sweep_threshold` 174 行付近・`build_items`・`THRESHOLD_RULES`)/ `code/data_gen/eval_pool.py`(`build_filled` 720 行付近・`write_pool`)/ `code/data_gen/build.py`(`build_items_from_entries`)
- パイロット用プールのセルの組は `data/generated/battery/pilot/manifest.json` の `fill.assignment`(セル名 → 組の列)

## やってはいけないこと

- **作業ツリーの `plans/PLAN-026-order6b.md` にある G14 の未コミットの記入(「確定」)を、人間に確かめずにコミットしない。**`git add -A` を使わない。PLAN-026 を直してコミットするときは、HEAD の版に自分の変更だけを当てたものを index に載せる(その54 は `git hash-object -w --stdin` + `git update-index --cacheinfo` で行った)
- GPU / main の push / I4 以降に手を広げる
- 主プール・パイロット用プール(`data/generated/battery/main*`・`pilot`)と `data/raw/` を書き換える
- 本番の T1b・T3 の文面・#2 = 0.70・#3 の値を変える(ADR-078 決定1・2)
- Python の `Path.write_text` で `STATE.md` などを書く(Windows で CRLF になる)。`write_bytes(...encode("utf-8"))` か Edit を使う。**Edit ツールで直した `.py` の作業コピーが CRLF になることがある**(その54 で 2 件。index は `.gitattributes` で LF になる。コミット後に `git checkout -- <file>` で揃えた)

## 未解決 / 人間の承認待ち

- **PLAN-026 G14 の記入(未コミット)を ADR に起こすか** / PLAN-026 §4.3 の実装の読みに異議があるか(`logs/OPEN-ITEMS.md`)
- 順6b の GPU 承認(I1〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G14・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
