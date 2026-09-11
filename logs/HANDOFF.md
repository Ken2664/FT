# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-11(その42)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **コンテキスト約 10 万トークン**(人間の決定 12 行を ADR-076 に記録した直後。**実装は始めていない**)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-023 §4 の手順1〜7 を実装し、§5 の dry-run と preflight の data_checks を通す。GPU 0。**
**決定は ADR-076 で全部出ている(12 行すべて (a))。決定の一覧は PLAN-023 §2.6 の ✅。**

完了条件(PLAN-023 §6):
- `pytest code/tests -q` が通る(その40 時点で 980 passed。その41・その42 はコードを触っていない)
- `PYTHONIOENCODING=utf-8 python -m code.data_gen.eval_pool --config configs/exp_phase1_main.yaml` が `data/generated/battery/main/` に **1,640 項目**のプールを書く
- `PYTHONIOENCODING=utf-8 python -m code.eval.run --config configs/exp_phase1_main.yaml --dry-run` が通る(`eval.dry_run_items` が無ければ `items.jsonl` を読む。A7)
- preflight の data_checks(検査6・8 を含む)が PASS / `data/generated/battery/main/manifest.json` をコミット

**大きいので、1 セッションで終わらなければ手順の境目でコミットして引き継ぐ**(区切りの目安: 手順1〜3 = プールが書ける / 手順4〜7 = `run.py`・`gonogo.py`・交差プール・batch 1 の config)。

## 直前セッションで確定したこと(ADR-076。`logs/DECISIONS.md` 末尾)

- 決定1 ★F128: Go/No-Go #2 の一覧は `none`(順6・凍結前)と `ident`(Phase 1)の**和集合**で縛る
- 決定2 ★F129: プール = `main` / 決定8 ★F135: 主軸 42 セル + 指示付き T1(**T1 の `id` セルの組から作る**。ADR-035 決定2)= 1,640(自由生成 680 / 強制選択 960)。副次は回さない
- 決定4 ★F131: T3・T1b のオフセットは各セル 40 項目を **20 / 20**、セル内の並び順に交互(新しい乱数は使わない)。`>` = {0, +1}、`<` = {+1, +2}(`t3_comparison.py` の `THRESHOLD_RULES`)
- 決定9 ★F136: `eval.pool_seed` = **3**
- 決定10 ★F137: (ii) `label_main_coverage` で照合し `coverage: extrap` は止める / (iii) `[1,99]²` は main 領域だけ(`counterpart_region_hash` を照合)、`extrap_magnitude` は `Q(999)` の main 側、訓練域外の 50:50 は組ごとのハッシュ / (iv) セルごとの乱数列
- 決定6 ★F133: タスク6 = T2 の組 240 × 残り 4 場面 = **960 項目を別のプールディレクトリ**に(手順6)
- 決定7 ★F134: batch 1 の config は `eval.batch_size` と `experiment.id` **だけ**が違う。それを回帰テストで縛る(手順7)
- 決定12 E-5 (b): `metrics.json` に `pool`(manifest のパス・`pairs_hash`・`items.jsonl` の sha256)と `coverage`(FT manifest のパス・`data_id`・`coverage.pairs_hash`・`coverage_k`・`train_domain.hi`)を足す。**正本は (a)。`frame.py` は食い違えば止まる。掃引 run には掛けない**(手順4)
- 決定3・5(タスク4 = R1 1 本 / test-retest = 同じ config の run 3 本)はコード変更なし。決定11 = 順6 の GPU 承認(条件付き)
- 閾値の転記元: `gonogo.parse_fail_max` = 0.02(ADR-065 決定1)/ `gonogo.min_cell_correct_rate` = 0.70(ADR-041 決定1)

## 触ってよいファイル / 読むべき範囲

- **skill `code-style` を最初に読む**
- `plans/PLAN-023-order6-readiness.md` §1.1(A1〜A13)/ §2.2 / §4 / §5(`grep -n '^##'` で節を出してから読む)
- `code/data_gen/pool.py`(`label_main_coverage` :201 / `split_pilot_main` :478 / `Cell` :600-612 / `fill_cells` :615-667)/ `code/data_gen/eval_pool.py`(`build` :263-336)/
  `code/data_gen/ft_data.py:636-672`(main 領域の分割。同じ関数・同じ引数で再現する)
- `code/eval/run.py`(dry-run :489-560 / `pool` ブロック :968-972)/ `code/analysis/frame.py`(`load_run` :208-278 / `build_rows` :364)
- `configs/exp_phase1_main.yaml` の `eval:`(:432-520)
- **Windows: 文書は LF で書く / Python の CLI は `PYTHONIOENCODING=utf-8`**

## やってはいけないこと

- GPU・ポッドを触る(承認は下りたが、**条件は manifest のコミットと dry-run の通過。実行は RUNNER の別セッション**)
- 事前登録済みの閾値(#1 = 0.02 / #2 = 0.70 / `θ` = 0.70)を変える / `magnitude_sweep.theta` を #2 の閾値に流用する(ADR-041 決定2)
- 組をセル間で再利用する(PLAN-001 §5.1・ADR-026。**例外は指示付き T1 だけ**)
- 仕様が曖昧な点を自分で決める(`CLAUDE.md` §8。質問として返す)/ `STATE.md` にブロックを積む(**いま 399 行。上限 400**。古いブロックはアーカイブへ移す)

## 未解決 / 人間の承認待ち

- 停止中ポッドの terminate / ★`θ` の根拠 / ★F104 / ★F114 の実行先 / Phase 1 本実験 40 run の GPU 構成 / N5 / ★C / ★2 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
