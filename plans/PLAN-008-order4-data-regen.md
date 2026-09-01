# PLAN-008: 順4 — 順0 の決定をコードと config に反映する

- 起草: 2026-09-01 / IMPLEMENTER (Opus)
- 上位: `plans/PLAN-004-phase0-route.md` §3「順4」+ §2「順4 に持ち越した実装の申し送り」
- 仕様の正本: **ADR-034 / ADR-035**(`logs/DECISIONS.md`)
- GPU: **使わない(0 時間)**

---

## 1. この PLAN が答える問い

「順0(2026-08-27)で人間が決めた3件は、`code/` と config のどこに、どう入るか」

順4 の完了条件は `PLAN-004` §3 が持つ3つである。本 PLAN は**そのうち第1条件
(順0 の決定をコードと config に反映)を実装単位に割る**。第2・第3条件
(本番 config で `ft_data.py` / `eval_pool.py` を実行 → preflight 全 PASS)は
**人間の未決事項に依存して塞がっている。**その内訳は §5 に書く。

---

## 2. 実装する3件(ADR-035 決定2 / 決定3、ADR-034 帰結)

### 2-1. 指示付き T1 の群を新設する(ADR-035 決定2)

- **項目**: T1 と同一の被演算子対に、**T2 と逐語で同じ**答え書式の指示文を付けた版
- **セル**: `id` × {`carry`, `nocarry`} の2セル・1セル n = 40 = **80 項目**
- **主軸の交互作用モデルには入れない**(副次・探索的。多重比較の補正なしと明記して報告)
- 採点は**自由生成の数値パース**のまま(強制選択に回すのは `comparison` だけ。ADR-047 決定1)

**★実装で確定させる点(提案 IMPLEMENTER / 採択は人間。ADR-039)**

| # | 確定させたこと | なぜエージェントが決めてよいか / 覆せるか |
|---|---|---|
| a | 群名 = **`bare_sum_instructed`** | ADR-035 リスク欄が「群名は未定であり `SUPPORTED_GROUPS` に足すのは順4 の仕事」と実装に授権。`bare_sum` / `specificity` の命名と同じ扱い(**人間が覆してよい**) |
| b | category = **`t1_instructed`** / タスク型 = **`t1_instructed`** | タスク型を `t1` と同値にすると主軸4水準に紛れる。**副次セルは主軸に入れない**(決定2)ので別値にする |
| c | 文面は**テンプレートファイルを新設せず** config から組む(`data.prompt_template` + 区切り + `data.answer_format_instruction`) | (i) `configs/templates/` は ADR-046 / 048 で凍結。差分を出さない。(ii) 「T1 と同一の被演算子対」「T2 と逐語で同じ文」という決定2 の不変条件が**構成的に**保たれる。テンプレートファイルに書き下すと `data.prompt_template` から静かに離れうる |
| d | 区切り = **半角空白1つ**(T2 が本文と指示文を継ぐのと同じ) | 決定2 が指定していない唯一の自由度。**人間が覆してよい** |

**やらないこと**: `bare_sum`(T1)の文面は1文字も変えない。指示付き T1 は
**評価アンカーではない**ので、preflight 検査6(`format_hash`)の対象にしない。

### 2-2. 被演算子 1 の除外を全タスク型の評価項目に広げる(ADR-035 決定3・決定4)

- **掛ける先は評価プールだけ。**`K` の抽出母集団には掛けない(決定4)
- **桁数掃引(`code/eval/sweep.py` / `magnitude_sweep`)には掛けない。**
  掃引は評価プールではなく `M*` を決めるための別の項目集合であり、
  抽出仕様は ADR-041 決定5 が凍結している(項目数 200 / 格子 / 5シード)。
  ここに除外を足すのは**実験条件の変更**である(`CLAUDE.md` §8)
- 除外集合の持ち主を `numeric_sum`(T1/T2 のモジュール)から
  **`code/data_gen/pool.py`(プール全体の規約)**へ移す。T2 固有だった規則が
  全タスク型共通の項目規約に昇格したため(ADR-035 帰結)
- manifest の `item_exclusions` を**プール全体の欄**にする(同 帰結)

### 2-3. `id` セルの母集団を明示する(ADR-034 リスク欄「順4 の項目生成で明示する」)

- `id` セルの母集団は **`K` そのものではない。**評価側の除外(判別不能 = `t ≡ 0 (mod digit_modulus)`、
  および被演算子 1)を掛けた残りである
- 数え上げ(`coverage_seed = 20260823` / `K_main = 2000`。**組合せ論的な計数であって
  実験結果ではない**): `2,000 → 1,808(carry 393)→ 1,776(carry 386)`
- **実装**: 評価プール manifest に `id_cell_population` を新設し、
  本番経路が実際に数えた値を残す。人間の手計算を転記しない

---

## 3. 実装単位

| # | 単位 | 触るファイル |
|---|---|---|
| 8-1 | 除外集合を `pool.py` に移し、プール全体の規約にする | `code/data_gen/pool.py` / `code/eval/battery/numeric_sum.py` |
| 8-2 | 指示付き T1 の群・category・テンプレート合成 | `code/eval/battery/numeric_sum.py` / `code/data_gen/battery_items.py` |
| 8-3 | 群の配線(生成ディスパッチ / 文面 / 本実行) | `code/eval/battery/build.py` / `code/eval/run.py` |
| 8-4 | 評価プールに除外を全群へ適用 + manifest をプール全体の欄に | `code/data_gen/eval_pool.py` |
| 8-5 | `id_cell_population` を manifest に新設 | `code/data_gen/pool.py` / `code/data_gen/eval_pool.py` |
| 8-6 | config の雛形に新しい欄を足す | `configs/template.yaml` |
| 8-7 | テスト | `code/tests/test_*.py` |

**`configs/smoke.yaml` は編集しない**(ADR-037 決定4)。新しい群は smoke の
`eval.batteries` に入らないので、経路はテストの中で組んだ config で通す。

---

## 4. 完了条件 ★2026-09-01 全項目 完了

- [x] `SUPPORTED_GROUPS` が5群になり、指示付き T1 が `--dry-run` と評価プールの両方を通る
- [x] 指示付き T1 の文面が「`data.prompt_template` + 空白 + T2 の指示文」であること、および
      指示文が**T2 の5テンプレートの末尾と逐語一致**することをテストが縛る
      (`code/tests/test_numeric_sum.py`。正本は `configs/templates/t2.yaml`)
- [x] 被演算子 1 の組が**どの群でも**評価プールに入らない。落とした件数が群ごとに manifest に残る
- [x] 桁数掃引の項目集合が**変わっていない**ことをテストが縛る(除外を掛けていない)
- [x] `id_cell_population` が本番経路の数え上げとして manifest に残る。
      設計事実テストが **`2,000 → 1,808(carry 393)→ 1,776(carry 386)`** を固定した
- [x] `pytest code/tests -q` → **788 passed**(774 → +14)
- [x] `python -m code.eval.run --config configs/smoke.yaml --dry-run` が通る(回帰)
- [x] `infra/preflight.py --config configs/smoke.yaml` の **`data_checks` 6項目すべて PASS**(回帰)。
      残る FAIL 2件は `model.name` / `model.revision` が null であることによるもので、順4 の範囲ではない

---

## 5. 順4 の第2・第3条件を塞いでいるもの(人間の決定。`CLAUDE.md` §8)

**本番 config(5条件)を作れない。**エージェントが値を決めると実験条件の決定になる。

| # | 欄 | 状態 | 出どころ |
|---|---|---|---|
| B1 | `lesion.arbitrary_table` | **未決(承認待ち-3)** | `arb` のズレ表の中身。`PLAN-002` §7.3 が満たすべき制約だけを提案し、表そのものは起草していない。**5条件のうち `arb` を作れず、かつ `[MATCHED]` なので他4条件の config にも書けない** |
| B2 | `data.train_size` | **未決** | `configs/template.yaml` は null。掃引軸 {2000, 4000, 10000} は ADR-043 決定6 が前提にするが、**順4 で焼き込む1点が決まっていない** |
| B3 | `data.coverage_k` | **未決** | 同上(コメントの「主値 2000」は提案であって採択ではない)。`K` を掃引軸にするかも承認待ち |
| B4 | `eval.cells`(本番のセル表) | **転記可**(PLAN-003 §4.7 が確定表)だが B5 と対になる | `id` 要求 520 組 / 主軸 1,560 項目 |
| B5 | `eval.pool_items`(本番の項目) | **塞がっている** | ADR-033 決定4: **`M*` 未決のあいだ `extrap` セルは原理的に埋まらない**ので `fill_cells` を呼ぶ経路に移せない。明示リストで 1,560 項目を書き下す運用も人間が決めていない。`M*` は順5 の後 |

**したがって順4 は第1条件だけが閉じる。**第2・第3条件は
**B1〜B3 の決定 + 順5(`M*`)の後**でなければ満たせない。
`PLAN-004` §2 の手順表の状態欄は「進行中」に留める。

---

## 6. やってはいけないこと

- 合否基準・しきい値・Go/No-Go 判定コード・`θ`・`M*` を書く / 提案して決める
  (ADR-041 / ADR-045 決定2 / ADR-047 決定6)
- **凍結済みのプロンプト文面を変える**(ADR-046 / ADR-048)。`configs/templates/` に差分を出さない
- **強制選択の器械を触る**(人間の最終確認待ち。ADR-047 実装ノート)
- `configs/smoke.yaml` を編集する(ADR-037 決定4)
- `data/raw/` を書き換える(`CLAUDE.md` §2)
- GPU ジョブを起動する
- §5 の B1〜B5 に値を入れる

---

## 7. 実行ログ

| 日付 | 何を | commit |
|---|---|---|
| 2026-09-01 | 起草 | `9491196` |
| 2026-09-01 | 8-1〜8-7 を実装。ADR-049 に確定事項。`pytest` 788 passed。GPU 時間 0 | `9491196` |
