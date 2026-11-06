# PLAN-045: 既知性と可換性 —— 主プールの `interp` から逆順が K にある組を除き、`mirror_in_K` を記録する(ADR-130 決定3・ADR-131 決定7)

> プランファイルは**実装より先に書く**。仕様がここに書かれていないものは実装しない。
> 変更したら `logs/CHANGELOG.md` に記録し、git commit する。

- 作成日: 2026-10-23
- 最終更新: 2026-10-23(その181。採択 = ADR-134)
- ステータス: **`採択`(ADR-134。2026-10-23 その181。§4 の Q1〜Q5 は 5 問とも推奨 (a))** ~~`草案`(人間のレビュー待ち。§4 の Q1〜Q5 は人間が決める)~~
- 担当: PLANNER(草案 = Opus 5.5)/ 実装は IMPLEMENTER / 素のモデルの測り直し(Q5)の起動は人間 / 採択は人間
- 関連: **ADR-130 決定3**(この PLAN の正本)/ **ADR-131 決定7**(別の PLAN にする)/ ADR-017・ADR-076 決定10(`fill_cells`)/ ADR-019 決定4(被覆ラベルは実行時に付ける)/ ADR-034(`id` セルの母集団)/ ADR-038 決定4(設定を変えたら順6 を測り直す)/ ADR-097 決定6 / ADR-039 決定3
- 判断材料: `logs/REVIEW-2026-10-15-implementation-analysis.md` R3・R5・§D.3 / `plans/PLAN-002-ft-data.md` §4.5.1・§4.5.3 / `code/data_gen/pool.py`(`fill_cells`・`label_coverage`)/ `code/data_gen/eval_pool.py`(`fill_candidates`)/ `code/data_gen/composition_pool.py`(T1c の先頭の組のセル)
- 関連する問い・仮説: 主要検定(T1 × T2 の `task:coverage`)の `interp` 水準が、T1 と T2 で同じ意味(どちらの順も未見)になっているか。H2 は直接は問わない

---

## 0. 一行要約と読み方

**K は順序付きの組なので、`interp` 項目の一部は逆順 (b, a) が K に入っている。その割合が T1 と T2 で違う(現行の主プールで 14/80 と 18/80)。ADR-130 決定3 はそうした組を `interp` の候補から事前に除き、`mirror_in_K` を記録すると決めた。この PLAN はその実装の範囲と形を決める。**

- §2 = この PLAN で変えないもの
- §3 = 起草時に確かめた事実(組合せ論的な計数。実験結果ではない)
- §4 = 人間が決めること(Q1〜Q5。推奨を先頭に。ADR-097 決定6)。**推奨は定義の整合性・費用・既存の決定との関係から出したもので、実験結果の解釈ではない**
- §5 = 実装の手順(§4 の回答の後)

---

## 1. この PLAN が答える問い

1. フィルタはどのセルに掛けるか(主要検定の T1・T2 だけか。T1b・T3・特異性対照・T1c も含めるか)
2. どの形で除くか(母集団から除いてから引くか、引いた順から飛ばすか)
3. `mirror_in_K` をどう定義し、どこに記録するか
4. `id` の側の二重露出(両方の順で K に入っている組)をどう扱うか
5. 現行の主プールで測った素のモデルの順6(Go/No-Go の印)を、作り直したプールで測り直すか

## 2. 前提(この PLAN では変えない)

- **訓練データ(K)は変えない**(ADR-130 決定3。案 B「K を順序なしで引き直す」は却下済み)。`p2` と `p2d` の K は同じ 2,000 組である(§3.1)
- **被覆ラベルの定義は変えない。**`label_coverage` / `label_main_coverage` は今のまま `(a, b) ∉ K` を `interp` と呼ぶ。変わるのは「`interp` セルをどの組から引くか」だけである。したがってパイロットのフレームのラベルは動かない
- **パイロット用プールは変えない**(パイロットの結果がそのプールの上にある。揃えるかは R5 と同じ機構の別の判断。ADR-130 リスク欄)
- 主プールのセル表(セル名・件数・`eval.pool_seed`)は変えない
- `Documents/05_STATISTICS.md` は変えない。感度解析の事前登録は凍結前に別に書く(§4 Q4)
- 天井の手当て(PLAN-046)とは触るファイルが重ならない

## 3. 起草時に確かめた事実(組合せ論的な計数。**実験結果ではない**。`CLAUDE.md` §2)

数えた材料: `configs/exp_phase1_main.yaml` → `eval_pool.fill_candidates` と `pool.fill_cells` を読み取りだけで呼んだ。**現行の割当は `data/generated/battery/main/manifest.json` の `fill.assignment` と 42 セルすべてで一致した**(再現できている)。実装では同じ数を manifest に記録し、テストで固定する(§5 I2・I5)。

### 3.1 K

- K = 2,000 組(`data/generated/ft/exp_phase1_main_p2/manifest.json`。`p2d` の K と同一)
- **両方の順で K に入っている組**(a ≠ b): 446 組(REVIEW R3 と一致)/ 対角 (a, a): 13 組

### 3.2 現行の主プールで `mirror_in_K`(= a ≠ b かつ (b, a) ∈ K)が真の項目

| セル群 | `id` | `interp` |
|---|---|---|
| T1(carry + nocarry) | 21/80(14 + 7) | **14/80**(5 + 9) |
| T2 | 26/80(11 + 15) | **18/80**(13 + 5) |
| T1b(gt + lt) | 37/160 | 25/160 |
| T3(gt + lt) | 30/160 | 41/160 |
| 特異性対照(sub + mul) | 7/40 | 7/40 |

`interp` の列は REVIEW R3 の値と一致する。**`id` の列も T1 と T2 で割合が違う**(21/80 と 26/80)。ADR-130 決定3 はこちらを「記録して感度解析」としている(§4 Q4)。

### 3.3 セルが埋まるか(ADR-130 リスク欄「未確認」の確認)

`interp` の候補(除外 3 段の後)の供給と需要:

| 層 | 逆順が K に無い | 逆順が K にある(除く) | 需要(セルの合計) |
|---|---|---|---|
| carry | **443** | 115 | 240 + 特異性対照の一部 |
| nocarry | **1,568** | 358 | 240 + 特異性対照の一部 |
| (特異性対照は層別しない) | | | 40 |

- **除いた候補で `fill_cells` を走らせると、42 セルすべてが埋まった**(`InsufficientCandidatesError` なし)。carry 層の余裕が最も小さい(443 に対して最大 280)
- `interp` 以外のセル(`id`・`extrap_magnitude`)の割当は 1 組も動かなかった
- **Q2 (a)(母集団から除く)の場合、`interp` セルの項目はほぼ全部入れ替わる**: T1 76/80・T2 79/80・T1b 152/160・T3 152/160・特異性対照 40/40 が新しい組になる。母集団の長さが変わると `cell_rng` の並べ替えが全体として変わるためである。逆順が K にある組だけを置き換えるなら、入れ替わるのは T1 14・T2 18 件である(Q2 (b))

### 3.4 波及

- **順6(素のモデル)は現行の主プールで測った**(`items_sha256` `d272204f…`。[run:20260911_141547_order6_r1] ほか r2〜r4 と rescore。Go/No-Go の印はセルごと)。1 run の所要時間は 352.8 秒(1,640 項目。モデルの読み込み 126.9 秒を含む)[run:20260911_141547_order6_r1]
- 主プールを相手として参照する config(`counterpart_manifest`)は多いが、両プールの manifest の `counterpart_hash` は `None` で、照合は掛かっていない。作り直しても pilot 側の manifest は壊れない
- T2 の交差プール(`main_t2_cross`)は主プールの T2 の組から作るので、作り直すことになる
- T1c のプールはまだ書き出していない(`eval.composition.n_per_cell` が null。ADR-118 決定3)

## 4. 人間が決めること(推奨を先頭に。**推奨は定義の整合性・費用・既存の決定からのもので、結果の解釈ではない**)

### Q1. フィルタを掛ける範囲

| 案 | 中身 | 利点 | 代償 |
|---|---|---|---|
| **★(a)** | 主プールの**全ての `interp` セル**(T1・T2・T1b・T3・特異性対照)と、**T1c の先頭の組の `interp` セル** | `interp` のセルの定義が全タスク型で 1 つになる。T1b・T3(探索)や T1c(E3)を T1 と比べるときに定義の差が入らない。T1c のプールはまだ作っていないので追加の費用はほぼない | 特異性対照・T1b・T3 の項目も入れ替わる(§3.3) |
| (b) | 主プールの全ての `interp` セル。T1c は `mirror_in_K` の記録だけ | T1c のコードを触らない | T1c の先頭の組の `interp` だけ定義が違う。合成の署名(E3)の `interp` セルに逆順が K の組が残る |
| (c) | T1・T2 の `interp` セルだけ(主要検定) | 入れ替わる項目が最少 | 同じ `interp` の語が、タスク型によって違う母集団を指す |

### Q2. 除き方

| 案 | 中身 | 利点 | 代償 |
|---|---|---|---|
| **★(a)** | **母集団から除いてから引く**(候補の事前フィルタ。`fill_cells` に渡す前に除く) | PLAN-002 §4.5.3(交換律ペア)と同じ形で、ADR-130 決定3 の文言「候補の事前フィルタ」どおり。`fill_cells` は変えない。セルの母集団が「どちらの順も K に無い組」と一言で書ける | `interp` セルの項目がほぼ全部入れ替わる(§3.3)。順6 の印はそのセルについて新しい項目を測っていないことになる(Q5) |
| (b) | 今の並べ方のまま、逆順が K にある組だけを飛ばして次の候補で埋める | 入れ替わるのは逆順が K にある項目だけ(T1 14・T2 18 件)。順6 の測定が大半の項目で有効のまま | `fill_cells` に「飛ばす述語」の引数が要る(セルごとの乱数列の規約 ADR-076 決定10 (iv) の書き直し)。母集団の定義が 2 段になる。T1b・T3 の閾値オフセットの交互の配り方(ADR-076 決定4)が一部ずれる |

### Q3. `mirror_in_K` の定義と記録先

定義の案: **`mirror_in_K := a ≠ b かつ (b, a) ∈ K`**(対角 (a, a) の逆順は自分自身なので偽にする。K の 13 組の対角は `id` のまま)。主域の外(`extrap_magnitude`)では常に偽。

| 案 | 中身 | 利点 | 代償 |
|---|---|---|---|
| **★(a)** | **`code/analysis/frame.py` が実行時に列を付ける**(被覆ラベルと同じく K から計算)+ プールの manifest にセルごとの件数を記録する。`items.jsonl` の形式は変えない | ADR-019 決定4(ラベルは実行時に付ける)と同じ原則。パイロットのフレームにも同じ列が付くので、パイロットでの混入も記述できる | 項目ファイルだけを見ても `mirror_in_K` は分からない(manifest の件数と K が要る) |
| (b) | `items.jsonl` の各項目に固定し、`frame.py` でも計算して照合する | 項目ファイル単体で分かる | パイロットのプールは作り直さないので、パイロットの項目には欄が無い(2 つの形が並ぶ)。照合の分だけコードが増える |

### Q4. `id` の側の二重露出(446 組)

| 案 | 中身 | 利点 | 代償 |
|---|---|---|---|
| **★(a)** | **ADR-130 決定3 のとおり、記録(Q3 の列)と感度解析だけ。**感度解析の事前登録(`05_STATISTICS.md`)は凍結前に別に書く | 決定済みの範囲を越えない。`id` セルは 1 組も動かない(§3.3) | `id` の `mirror_in_K` の割合が T1 21/80・T2 26/80 で違うまま主要検定に入る(§3.2) |
| (b) | `id` セルも `mirror_in_K` で層別し、T1・T2 で同じ件数にする | `id` の側の T1・T2 の差も源で消える | ADR-130 決定3 を開き直すことになる。`id` セルが入れ替わり、セル表(層の数)が変わる |

### Q5. 順6(素のモデル)の測り直し

| 案 | 中身 | 利点 | 代償 |
|---|---|---|---|
| **★(a)** | **作り直した主プールで順6 の R1 の設定を 1 run 測り直す**(素のモデル。S4 と同じ pod で回せば pod の立ち上げは 1 回。起動は人間) | Go/No-Go の印がセルごとなので、入れ替わったセルの印が新しい項目で付く。ADR-038 決定4(設定を変えたら測り直す)と同じ考え方 | GPU が少し要る(旧プールで 1 run 352.8 秒 [run:20260911_141547_order6_r1]。pod の立ち上げは別)。旧い印と新しい印が並ぶ |
| (b) | 測り直さない(印は旧プールのものとして記録し、限界に書く) | GPU 0 | `interp` セルの印が、本番で使う項目を測っていない |
| (c) | Q2 (b) と組にして、置き換えた項目だけ測る | 測る項目が最少 | Q2 (b) の代償をそのまま負う。セルの印は新旧の項目の混合から付くことになる |

## 5. 実装の手順(§4 の回答と採択の ADR の後。IMPLEMENTER = Sonnet で可。統計の判断が出たら止めて PLANNER へ)

以下は §4 が推奨どおり(Q1〜Q5 すべて (a))の場合の手順。

- **I1(`code/data_gen/pool.py`)**: `mirror_in_k(pair, coverage_pairs) -> bool`(Q3 の定義)と、候補から「`interp` かつ `mirror_in_k`」の組を除く関数を足す。`label_coverage`・`label_main_coverage`・`fill_cells` は変えない
- **I2(`code/data_gen/eval_pool.py`)**: `fill_candidates` で I1 のフィルタを掛ける。**config の新しい欄で入り切りする**(例 `eval.interp_mirror_filter: true`。主の config だけ真。無い・偽なら今と同じ)。パイロットのプールが今と 1 バイトも変わらないことをテストで固定する。manifest の `fill.candidates` に、除いた組の数(層ごと)とセルごとの `mirror_in_K` の件数を記録する
- **I3(`code/data_gen/composition_pool.py`)**: T1c の先頭の組の `interp` セルに同じフィルタを掛ける(Q1 (a))。同じ config の欄で入り切りする
- **I4(`code/analysis/frame.py`)**: 列 `mirror_in_K` を実行時に付ける(K は既に読んでいる)。主軸の絞り込みには使わない(記録だけ)
- **I5(データとテスト)**: 主プールと `main_t2_cross` を作り直し、2 回生成してバイト一致を確かめてから commit する。主プールの `pairs_hash`・`items_sha256` を固定しているテストと文書の記載(PLAN-023 の `13e8479c…`・PLAN-037 の `d272204f…`)は、打ち消し線・理由・日付を付けて新しい値を足す。`pytest code/tests -q`
- **I6(文書)**: PLAN-002 §4.5.1 の `interp` の行の隣に「主プールの `interp` **セル**はさらに (b, a) ∉ K の組から引く(本 PLAN。ラベルの定義は不変)」を足す。PLAN-001 の `interp` セルの記述にも同じ注を付ける。PLAN-034 は触らない
- **I7(素のモデルの測り直し。Q5 (a)。RUNNER・起動は人間)**: 新しい主プールで順6 R1 の設定を 1 run。`gonogo.py` で印を付け、旧い印と並べて記録する(解釈は人間)

## 6. 想定される交絡と罠

- **罠1**: `fill_candidates` に無条件でフィルタを掛けると、パイロットのプールを作り直したときに中身が変わる(同じコードの経路を通るため)。config の欄で切ることと、パイロットのバイト一致のテストが必須(I2)
- **罠2**: `interp` のラベルを書き換える形で実装すると、パイロットのフレームの被覆ラベルが動き、既存の集計が再現しなくなる。**ラベルは変えず、セルの母集団だけを絞る**(§2)
- **罠3**: 対角の組 (a, a) を「逆順が K にある」と数えると、`id` の対角 13 組がすべて `mirror_in_K` 真になる。定義で a ≠ b を明示する(Q3)
- **罠4**: R5(パイロットと主が逆順の組でつながっている)はこの PLAN では直らない。作り直した主プールの項目のうち、逆順がパイロットの項目に入っている件数は I2 の manifest に記録だけする(判断は R5 と一緒に人間)
- 退屈な仮説: 混入率の差(14/80 と 18/80)は抽選の揺らぎの大きさである。それでもフィルタで源から消せるので、ADR-130 は除く方を採った。この PLAN はその決定の実装であって、混入の効果の大きさは問わない

## 7. 必要なリソース

- CPU のみ(I1〜I6)。GPU は I7 の素のモデル 1 run だけ(Q5 (a) の場合)
- 触るファイル: `code/data_gen/pool.py`・`eval_pool.py`・`composition_pool.py`・`code/analysis/frame.py`・`configs/exp_phase1_main.yaml`(と T1c の主の config)・`data/generated/battery/main*/`・テスト・PLAN-001/002 の注

## 8. やらないこと(この PLAN では)

- K の引き直し / パイロットのプールの作り直し(R5)/ `05_STATISTICS.md` の書き換え(感度解析の事前登録は凍結前に別に)/ 混入の効果の解釈 / 天井の手当て(PLAN-046)

## 9. 完了条件

- [x] §4 の Q1〜Q5 に人間が答え、採択の ADR を書いた(ADR-134)
- [x] I1〜I6 を実装し、主プールを作り直して 2 回生成のバイト一致を確かめた。パイロットのプールが 1 バイトも変わっていないことをテストで確かめた(2026-10-24 その182。§11)
- [x] 作り直した主プールの `interp` セルで `mirror_in_K` が 0 件であることをテストで固定した(`code/tests/test_interp_mirror_filter.py`)
- [x] `pytest code/tests -q` が通った(2026-11-06 その198。pod 上の preflight の検査で 2681 passed・14 skipped。commit `8135f35`。§11)
- [x] (Q5 (a) の場合)順6 の測り直しの run_id と印を記録した([run:20261106_021031_order6_r1_remeasure]・`results/gonogo_order6_remeasure/gonogo.json`。§11。**印の解釈は人間**)

## 10. 記入欄(人間の回答)

| 問い | 回答 | 日付 |
|---|---|---|
| Q1 範囲 | (a) 主プールの全 `interp` セル + T1c の先頭の組 | 2026-10-23 |
| Q2 除き方 | (a) 母集団から除いてから引く | 2026-10-23 |
| Q3 `mirror_in_K` の定義と記録先 | (a) a ≠ b かつ (b, a) ∈ K・`frame.py` の実行時の列 + manifest の件数 | 2026-10-23 |
| Q4 `id` の二重露出 | (a) 記録と感度解析だけ | 2026-10-23 |
| Q5 順6 の測り直し | (a) 作り直した主プールで 1 run | 2026-10-23 |

## 11. 実行ログ

### 2026-10-24(その182・I1〜I6)IMPLEMENTER(Claude Opus 5.5。推奨は Sonnet)

- **I1** `code/data_gen/pool.py`: `mirror_in_k`(a ≠ b かつ (b, a) ∈ K)・`is_interp_mirror`・`without_interp_mirrors`(候補の並びを保つ)。`label_coverage`・`label_main_coverage`・`fill_cells` は不変
- **I2** `code/data_gen/eval_pool.py`: 欄 `eval.interp_mirror_filter`(無い・偽 = 掛けない。真偽値以外は止める)。真のとき `fill_candidates` が除外 3 段の後に 4 段目として掛け、`fill.candidates.interp_mirror_filter`(除いた組の数・層ごと・ハッシュ)と `fill.interp_mirror_filter`(セルごとの `mirror_in_K`・逆順が相手側のプールにある件数 = 罠4 の記録)を書く。偽なら鍵ごと書かない
- **I3** `code/data_gen/composition_pool.py`: 同じ欄で先頭の組の候補に掛け、`fill.interp_mirror_filter` に除いた数とセルごとの `mirror_in_K` を書く(T1c のプールは `n_per_cell` が null なので書き出していない)
- **I4** `code/analysis/frame.py`: 列 `mirror_in_K`(`coverage` の隣)。`coverage`・`main_axis` は不変
- **config**: `exp_phase1_main.yaml` と写しの `exp_phase1_main_b1.yaml`・`exp_phase1_main_t2cross.yaml`・`exp_t1c_main.yaml` に `interp_mirror_filter: true`。パイロット側の config は触っていない(`test_order6b_pilot.py` に「主だけの欄」として宣言)
- **I5** 主プールと `main_t2_cross` を作り直した(2 回生成してバイト一致)。manifest に出た数は §3 と一致(組合せ論的な計数であって実験結果ではない):
  - 除いた組 473(carry 115・nocarry 358)/ 除いた後の `interp` の供給 carry 443・nocarry 1,568 / 42 セルすべて埋まった
  - `interp` 14 セルの `mirror_in_K` はすべて 0 / `id` は T1 21(14 + 7)・T2 26(11 + 15)のまま
  - 入れ替わった項目: T1 76/80・T2 79/80・T1b 152/160・T3 152/160・特異性対照 40/40。`id`・`extrap_magnitude` のセルは 1 組も動かない(テストで固定)
  - 罠4 の記録: 新しい主プールの組のうち逆順がパイロットのプールにある組は 199(セルごとの内訳は manifest)。**判断は R5 と一緒に人間**
  - 主: `pairs_hash` ~~`13e8479c…`~~ → `c20991dd…`・`items_sha256` ~~`d272204f…`~~ → `6bb6084d…` / 交差: `pairs_hash` ~~`c1409c4b…`~~ → `878ffe2d…`・`items_sha256` ~~`8cb8a58f…`~~ → `eb1ed1dd…`(2026-10-24。理由: 本 PLAN)
  - 欄を偽にすると旧い主プール(`13e8479c…`)がそのまま組めることをテストで固定した。パイロットのプールは manifest のバイト列が commit 済みと一致(テスト)
  - **`items.jsonl` は git に入っていない**(`.gitignore`)。この機の旧い `items.jsonl` は上書きされた。旧いプールは欄を偽にすれば再生成できる
- **I6** PLAN-002 §4.5.1 の表と PLAN-001 の案A の注に「主プールの `interp` セルはさらに (b, a) ∉ K の組から引く。ラベルの定義は不変」を足した。PLAN-023・PLAN-037 の旧いハッシュに打ち消し線と新しい値
- `pytest code/tests -q`: **2624 passed**(309 秒)
- **I7(順6 の測り直し)は起動していない**(GPU。人間)

### 2026-11-05(その197・I7 の起動の試み)RUNNER(Claude Opus 5.5。推奨は Sonnet)

- 人間が pod を上限 1 時間で承認(push は未承認)。既存の pod `9matkiq0jozcgm` の `start` は 2 回とも「ホストに空き GPU が無い」(400)。**run は作っていない**・GPU 0・課金 0
- 手元の追跡外のファイルの SHA-256 は manifest と一致(主プール `6bb6084d…`・pilot `c5072f48…`・`train.jsonl` 5 本)
- 次: pod の扱いは人間(`logs/OPEN-ITEMS.md` の「★順6 の測り直し(PLAN-045 I7)の pod」)

### 2026-11-06(その198・I7 の実行)RUNNER(Claude Opus 5.5。推奨は Sonnet)

- 人間の指示: pod は (a) 同じ形で新規作成・上限 1 時間・push しない。旧 pod `9matkiq0jozcgm` の `start` は auto mode の分類器に拒否されたので試していない(`EXITED` のまま・terminate していない)
- 新しい pod `oorrti5on9opnb`(RTX 4090・SECURE・EU-RO-1・同じイメージ・ボリューム `r963j7swke`・$0.89/時)。02:08:53Z 作成 → 02:21:40Z 停止(約 $0.19)
- pod の旧い checkout(`102c2d5`)は `/workspace/pod_moved_aside_order6r` へ移し、bundle(`main` = `8135f35`)から clone。追跡外の 7 本の SHA-256 は pod 上で manifest の `files` と一致
- preflight: FAIL 0・WARN 1(未追跡の run dir だけ。`git_diff.patch` は 0 バイト)。pytest 2681 passed・14 skipped
- **run [run:20261106_021031_order6_r1_remeasure]**: 1,640 項目・`items_sha256` `6bb6084d…`・4 値の合計は全ブロックで 1.0。合計 215 秒(読み込み 59 秒・生成 152 秒)
- `gonogo.py` の印(`results/gonogo_order6_remeasure/gonogo.json`。旧い `results/gonogo_order6/` は不変): #1 は 3 群とも fails=False / #2 は T3・T1b の 6 セルが fails=True(T1・T2 の 6 セルは False)/ #3 は T3・T1b の 6 セルが fails=True。**旧い R1 の印との並べ方・解釈・`input.order6_dropped_cells` は人間**
