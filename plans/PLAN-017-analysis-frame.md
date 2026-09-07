# PLAN-017: 長形式表を組む層(`code/analysis/frame.py`)の仕様

> プランファイルは**実装より先に書く**。仕様がここに書かれていないものは実装しない。
> **★2026-09-07(その16)に人間が §5 の 7 件すべてを決定した(ADR-062)。**
> **提案 エージェント (Opus) / 採択 人間**(`CLAUDE.md` §8 / ADR-039 決定3)。
> **§5 の各節は決定前の記述であり、材料として残す。決定は §5.0 と ADR-062 にある。**

- 作成日: 2026-09-07
- 最終更新: 2026-09-07(その16。**起草した直後に人間が 7 件すべてを決定した(ADR-062)。** **E-1 = (c) / ★E-2 = (a)(`category` をそのまま `template` とする。主軸 10 水準)/ E-3 = (c) / E-4 = (a) / E-5 = (a) / E-6 = (c) / E-7 = (c)。** **★E-2 の決定に伴い `Documents/05_STATISTICS.md` §3.2 の `template` の行を人間の決定として書き換え、旧記述を §3.2.2 に打ち消し線で残した**)
- ステータス: **`実装済`**(**2026-09-07 その17。§6 の 5 件を実装し `pytest` 831 passed。★F81(`extrap_pair` の名前が PLAN-002 §4.6 の定義と厳密には一致しない)を人間に上げた**)
- 旧ステータス: **`採択`**(**2026-09-07 その16。人間が E-1 〜 E-7 の 7 件すべてを決定した(ADR-062)。提案 エージェント (Opus) / 採択 人間。★未決は 1 件も残っていない。残るのは §6 の実装である**)
- 担当: PLANNER(起草)→ **人間**(§5 の決定)→ IMPLEMENTER(§6 の実装)
- 関連する問い: `Documents/05_STATISTICS.md` §3.2(主軸のモデル指定 / 順1b のモデル指定)
- 由来: **ADR-061 決定3**。人間が `plans/PLAN-016-fitting-engine.md` §7-4 について
  「**先に PLAN を起こし、レビューを経てから実装する**」と決めた(`CLAUDE.md` §4 の手順)。
  PLAN-016 §5(F37 / F38 / F39)の棚卸しを仕様に落とす作業である
- 前提: **`M*` に依存しない**(照合の実装であって項目数に依存しない)。**GPU 不要**

---

## 1. この PLAN が答える問い

**「`Documents/05_STATISTICS.md` §3.2 のモデルが要求する長形式表(1 行 = 1 項目 × 1 実行)を、
`runs/` に残った成果物から、どういう規則で組むのか。」**

**★この PLAN はモデル指定を変えない。**§3.2 は事前登録の本体であり、ここでは読むだけである。

---

## 2. 実地で確認した事実(2026-09-07 その16。推測ではない)

### 2.1 ★PLAN-016 §5 の棚卸しのうち、実地と食い違っていた 3 点

PLAN-016 §5 と `logs/HANDOFF.md` は、この層の仕事を「写像を 3 本書き、`coverage` の照合を
新規に実装する」と書いていた。**実地で確かめると 3 か所が違っていた。**
**どれも仕様の分岐を増やす方向の食い違いであり、黙って直すと事前登録の意味が変わる。**

| # | 棚卸しの記述 | 実地 |
|---|---|---|
| **(1)** | 「`Item` は `code/eval/battery/battery_items.py` 付近」 | **そのファイルは存在しない。**実体は **`code/data_gen/battery_items.py:54`** |
| **(2)** | 「`coverage` を付ける実行時コードが repo に無い」 | **関数はある**(`code/data_gen/pool.py:144` の `label_coverage`)。**無いのは呼び出し経路である** |
| **(3)** | 「`task` は `group` から写像する」 | **`group` からは決まらない。**`comparison` 群は **T3 と T1b の両方**を含む |

### 2.2 事実の一覧(F63 〜 F79)

| 記号 | 事実 | 出どころ |
|---|---|---|
| **F63** | **`code/eval/battery/battery_items.py` は存在しない。**`Item` の定義は `code/data_gen/battery_items.py:54` である | `ls code/eval/battery/` |
| **F64** | **`coverage` を付ける関数はある。**`label_coverage(pair, coverage_pairs, main_radius)` | `code/data_gen/pool.py:144` |
| **F65** | **その関数を `code/analysis/` から呼ぶコードは 0 件である。**`label_coverage` / `label_answer_range` の呼び出しは `pool.py` 自身と `code/tests/` にしか無い | `grep -rn` |
| **★F66** | **`label_coverage` の返り値は 4 値である**(`id` / `interp` / `oob_algebraic` / `extrap`)。**§3.2 の `coverage` の 3 水準(`id` / `interp` / `extrap_magnitude`)とは集合が違う。`extrap_magnitude` は返り値に無い** | `code/data_gen/pool.py:41-44` |
| **★F67** | **`extrap_magnitude` は ADR-027 決定1 で「主軸では `a, b >= 100`(両方正)に限る」と定義されている。**`label_coverage` の `extrap` は `\|a\| > R` または `\|b\| > R` で発火し、**負の被演算子も、片側だけ域外の組も含む。**判定順が仕様として固定されており、`(-99, 1)` は `extrap` に落ちる | ADR-027 決定1 / `code/tests/test_pool.py:335` |
| **F68** | したがって **`extrap` → `extrap_magnitude` は恒等ではなく絞り込みである。**残りは ADR-027 決定2 の副次(`extrap_pair` = 被演算子が域外・答えは域内)と `oob_algebraic` に落ちる | ADR-027 決定2 |
| **★F69** | **`group` から `task` は決まらない。**`group == "comparison"` は **T3 と T1b の両方**を含み、タスク型は `category` から読む | `code/eval/battery/t3_comparison.py:16-24` |
| **F70** | **写像関数は既に 2 本ある**(`numeric_sum.task_type_of` :120 / `t3_comparison.task_type_of` :116)。`CATEGORY_AXES` は 2 つの dict に分かれ、**キーは互いに素である。無いのは両者を束ねる 1 箇所である** | 同上 |
| **F71** | **`category` の全水準は 13。**`numeric_sum` 7(`t1` / `t1_instructed` / `t2_count` / `t2_people` / `t2_distance` / `t2_money` / `t2_time`)+ `t3_comparison` 4(`t3_gt` / `t3_lt` / `t1b_gt` / `t1b_lt`)+ `specificity` 2(`spec_sub` / `spec_mul`) | 各モジュールの定数 |
| **F72** | **そのうち主軸の 4 水準に写るのは 10 である。**`t1_instructed` は副次(ADR-035 決定2)、`specificity` 群の 2 つは**タスク型を持たない** | ADR-035 決定2 |
| **F73** | `predictions/*.jsonl` の 1 行は `item_id` / `group` / `category` / `operands` / `carry` / `params` / `prompt` / `response` / `parsed` / `truth` / `rule_values` / `reference_rule` / `classification`。**`is_rule` は `classification == "rule"` で作れる** | `code/eval/run.py:659` |
| **F74** | **同じ (項目, 実行) が複数行になる経路は無い。**採点バッチは群と 1 対 1 で、`specificity` だけが `category` ごとに割れる | `code/eval/run.py:435` |
| **F75** | **`seed` は `runs/<id>/metrics.json` の最上位にある。★これは訓練 run の seed である**(評価 run はアダプタの親の `metrics.json` から引き写す)。`adapter_train_run_id` と `lesion_condition` も同じ場所にある | `code/eval/run.py:919` / :959 |
| **★F76** | **K(訓練被覆の組)は `runs/<id>/` に無い。**FT データの manifest の `coverage.pairs` にある。run からは `config.yaml` の `data.matched_manifests` と `lesion.condition` で引く | `code/data_gen/eval_pool.py:114` |
| **F77** | **評価プールの manifest には K が無い。**あるのは `coverage_sums`(和の集合)である。**`label_t_coverage` には足りるが `label_coverage` には足りない** | `code/data_gen/pool.py:689` |
| **F78** | **本実験の 5 条件の K は同一である**(実測。`exp_phase1_main_{p2,p2d,ident,arb,x2}` の `coverage.pairs` は 2000 組で 5 条件とも同じ内容)。manifest に `coverage.pairs_hash` があり、**照合に使える** | 5 つの manifest を実際に読んで比較した |
| **★F79** | **FT データの manifest は git に追跡されている**が、**`runs/*/predictions/` は `.gitignore` で外れている。**したがって**長形式表は repo だけからは再現できない。**永続ボリューム側の `predictions/` が要る | `.gitignore` / `git ls-files data/generated` |

### 2.3 ★PLAN-016 §5 の列の一覧に載っていなかった列がある

**§3.2 の順1b のコードは `condition` と `passes_analysis_gate` を使う。**

```r
d1b <- subset(all, condition %in% c("p2","p2d") & coverage %in% c("id","interp"))
d1b <- subset(d1b, passes_analysis_gate)          # ADR-054 決定1 (ii)
```

PLAN-016 §5 の表は主軸のモデルの 6 列(`is_rule` / `task` / `coverage` / `seed` / `item` / `template`)
しか並べていない。**順1b を当てるにはあと 2 列要る**:

- **`condition`** —— `metrics.json` の `lesion_condition` から取れる(**F75**)。**追加の設計判断は要らない**
- **`passes_analysis_gate`** —— **run 単位の解析門**(ADR-054 決定1 (ii))。**閾値が未決である**(N5)。
  **値はまだ計算できないが、列の置き場所と、閾値が決まっていないときの挙動は決めておく必要がある**

---

## 3. 出力する表(§3.2 が要求する形)

### 3.1 行の単位

**1 行 = 1 項目 × 1 評価 run。**F74 より、この単位で重複は起きない。

### 3.2 列と出どころ

| 列 | 出どころ | 変換 | 状態 |
|---|---|---|---|
| `item` | `predictions/*.jsonl` の `item_id` | そのまま | **手当て不要** |
| `is_rule` | 同 `classification` | `== "rule"` の 0/1 | **手当て不要** |
| `condition` | `metrics.json` の `lesion_condition` | そのまま | **手当て不要** |
| `seed` | `metrics.json` の `seed`(**訓練 run の seed**。F75) | そのまま | **手当て不要** |
| `task` | `predictions` の `category` | **写像。§5 の E-3** | **未定** |
| `template` | 同 `category` | **写像。★水準数が未確定。§5 の E-2** | **未定** |
| **`coverage`** | `predictions` の `operands` + **FT manifest の K** + `main_radius` | **★照合。§4 / §5 の E-1** | **未定。この PLAN の本体** |
| `passes_analysis_gate` | run 単位の集計(ADR-054 決定1 (ii)) | **閾値が未決**(N5) | **未定。§5 の E-6** |

**補助的に残す候補**(主軸のモデルには入らないが、§4 の副次と §3.3 の突き合わせに要る):
`group` / `carry` / `answer_range`(`ans_in` / `ans_out`)/ `t_coverage`(`t_seen` / `t_unseen`。
**`arb` の順7 が要求する。**ADR-021 決定3)/ `parsed` / `truth` / `classification` の 4 値そのもの。

### 3.3 入力の在り処(F76 / F79)

```
runs/<run_id>/metrics.json            seed / lesion_condition / adapter_train_run_id
runs/<run_id>/config.yaml             data.matched_manifests / data.train_domain_max / data.pool_id
runs/<run_id>/predictions/*.jsonl     1 行 1 応答     ★git に無い(F79)
data/generated/ft/<data_id>_<cond>/manifest.json
                                      coverage.pairs(= K)/ coverage.pairs_hash / train_domain
```

---

## 4. ★`coverage` の照合(この PLAN の本体)

### 4.1 手順(どの案を採っても共通)

1. run の `config.yaml` から `lesion.condition` と `data.matched_manifests` を読む
2. **その条件の FT manifest を名指しで引く**(`eval_pool.load_condition_manifest` と同じ規則)
3. `manifest["coverage"]["pairs"]` を `frozenset` にする(= K)。**`pairs_hash` と照合する**(F78)
4. `main_radius` を取る(**★出どころが 2 つある。§5 の E-5**)
5. 各行の `operands` の先頭 2 つを `label_coverage(pair, K, main_radius)` に通す
6. **4 値を §3.2 の 3 水準へ落とす**(**★ここが恒等でない。§4.2**)

### 4.2 ★4 値 → 3 水準は恒等ではない(F66 / F67 / F68)

| `label_coverage` の返り値 | §3.2 の `coverage` | 備考 |
|---|---|---|
| `id` | **`id`** | 一致 |
| `interp` | **`interp`** | 一致 |
| `extrap` **かつ `a > R` かつ `b > R`** | **`extrap_magnitude`** | **ADR-027 決定1 の「`a, b >= 100`(両方正)」。`R = main_radius = 99`** |
| `extrap`(上の条件を満たさない) | **主軸に入らない** | ADR-027 決定2 の副次 `extrap_pair`(C5) |
| `oob_algebraic` | **主軸に入らない** | ADR-027 決定2 の副次(C3)/ 決定3 で落とした C4 |

- **★`extrap ∧ ans_out` では定義が合わない。**`(300, 50)` は `extrap` かつ `ans_out` だが
  被演算子の片方が域内なので `extrap_magnitude` ではない。**ADR-027 の定義は答え域の軸ではなく
  被演算子の両側の条件である。**`label_answer_range` で代用すると別の集合になる
- **★逆向きは成り立つ。**`a > 99` かつ `b > 99` なら `t >= 200 > 198` なので必ず `ans_out` である。
  **ただし「必ずそうなる」ことを判定に使わない** —— 定義は ADR-027 のまま被演算子で書く
- **★`100` をリテラルで書かない。**`main_radius + 1` である(`data.train_domain_max` = 99)。
  リテラルにすると訓練域が動いたときに定義が黙ってずれる(skill `code-style` §1)

---

## 5. ★人間が決めること(`CLAUDE.md` §8)

### 5.0 ★人間の決定(2026-09-07 その16。ADR-062。提案 エージェント (Opus) / 採択 人間)

| 記号 | 決定 | 中身 |
|---|---|---|
| **E-1** | **案 (c)** | `frame.py` は **5 水準**を出し、絞り込みの定義は `code/data_gen/pool.py` に置く(`label_main_coverage`)。**主軸から落とした行の件数を run ごとに記録する** |
| **★E-2** | **案 (a)** | **`category` をそのまま `template` の水準とする。主軸は 10 水準**(`t1` 1 + `t2_*` 5 + `t3_gt` / `t3_lt` 2 + `t1b_gt` / `t1b_lt` 2)。**→ `Documents/05_STATISTICS.md` §3.2 を書き換え、旧記述は §3.2.2 に打ち消し線で残した** |
| **E-3** | **案 (c)** | `code/analysis/` に薄い dispatch。既存の `task_type_of` 2 本を呼ぶ。**未知の `category` で必ず落ちる。**`specificity` / `t1_instructed` は「主軸外」の明示的な印 |
| **E-4** | **案 (a)** | `frame.py` は絞らない。`primary.py` が `subset` する |
| **E-5** | **案 (a)** | `config.yaml` の `data.matched_manifests` を `lesion.condition` で辿り、`coverage.pairs_hash` を照合する。**★案 (b) は含めない**(`code/eval/run.py` の変更。別途諮る) |
| **E-6** | **案 (c)** | 門の生の量(run ごとの `id` 到達度)を列にし、二値化は `primary.py`。**閾値は未決のまま**(N5) |
| **E-7** | **案 (c)** | `results/` に CSV + ハッシュ + 入力 run_id 一覧 + FT manifest の `pairs_hash` |

**★決定に伴って残ったリスク(ADR-062 のリスク欄。実験前に記録した)**:
**極性(`gt` / `lt`)は応答バイアス対策の均衡設計因子であり、ランダム効果の水準として扱ってよいかは
未検証である** / **`template` は `task` に入れ子である**(§3.2 は交差の形で書いている) /
**水準数が 10 に定まったことで ADR-061 決定1 の前提が確定したが、事前予測検査は依然として回していない** /
**E-5 の案 (b) は諮っていない。採るなら本実験の前でなければ意味が無い。**

---

### 5.1 〜 5.7 は決定前の材料である(記録として残す)

| 記号 | 決めること | 重さ |
|---|---|---|
| **E-1** | **4 値 → 3 水準の絞り込みをどこに置き、主軸に入らない行をどう扱うか** | **主要検定の説明変数そのもの** |
| **E-2** | **`category` → `template` の写像と水準数** | **`(1 \| template)` の推定に直結** |
| **E-3** | **`category` → `task` の写像を 1 箇所にどう置くか** | 実装の置き場所 |
| **E-4** | **主軸の行の絞り込みを frame でやるか primary でやるか** | 層の責務 |
| **E-5** | **`main_radius` と K の正本をどこに置くか** | 再現性 |
| **E-6** | **`passes_analysis_gate` 列の扱い**(閾値が未決のまま) | 順1b のブロッカー |
| **E-7** | **表を `results/` に凍結するか、その場で組むか** | 監査可能性 |

### 5.1 E-1: 4 値 → 3 水準の絞り込み

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **(a)** | **`frame.py` は 5 水準を出す**(`id` / `interp` / `extrap_magnitude` / `extrap_pair` / `oob_algebraic`)。主軸の抽出は `primary.py` が `subset` で行う | **副次の「汎化半径の地図」(ADR-027 決定2 / P-2)が同じ表から作れる。**落とした行が見える | 主軸に入らない行が表に残る。`primary.py` 側で絞り忘れると df が変わる |
| **(b)** | **`frame.py` が 3 水準だけを出し、残りを落とす** | 主軸のモデルに渡す形がそのまま出る | **副次の地図が作れない。**別経路を建てることになる。**落ちた件数が表から消える** |
| **(c)** | **(a) + 絞り込みの定義を `code/data_gen/pool.py` に置く**(`label_main_coverage` を足す) | **被覆の定義が 1 ファイルに揃う。**`label_coverage` の隣に置ける | `pool.py` が解析の語彙を持つ。ただし `label_coverage` 自体が既にその語彙である |

**エージェントの推奨(採否は人間)**: **(c)**。理由は 2 つ。
**(i) 定義の重複を作らない** —— `extrap_magnitude` の定義が `frame.py` と ADR-027 の 2 か所に
分かれると、片方だけが直る事故が起きる。`label_coverage` が既に `main_radius` を引数に取っており、
**同じ引数で書ける。**
**(ii) 落とした行を数えられる** —— `CLAUDE.md` §6 は 4 値をすべて報告することを求めている。
**同じ理由で「主軸から落ちた行が何件あったか」も報告できる形にしておくほうがよい。**

**★どの案でも要る付帯条件**: **落とした行の件数を run ごとに記録する。**
黙って落とすと、項目数が静かに減っていても気付けない。

### 5.2 ★E-2: `category` → `template` の写像と水準数

**★これは §3.2 の記述と実装が食い違っている箇所である。**

- **§3.2 の表**: 「T2 の 5 テンプレート + T3 の質問文。**T1 / T1b は単一なので水準 1**」
- **実装**: `t3_comparison.CATEGORY_AXES` は **T3 に 2 つ**(`t3_gt` / `t3_lt`)、
  **T1b にも 2 つ**(`t1b_gt` / `t1b_lt`)を持つ。`category` = **タスク型 × 極性**(ADR-026)

| 案 | `template` の水準 | 主軸での水準数 |
|---|---|---|
| **(a)** | **`category` をそのまま `template` とする** | **10**(`t1` 1 + `t2_*` 5 + `t3_*` 2 + `t1b_*` 2) |
| **(b)** | **§3.2 の記述に寄せる。**極性は T3 でのみ水準を割る | **9**(`t1` 1 + `t2_*` 5 + `t3_*` 2 + `t1b` 1) |
| **(c)** | **極性を `template` から外し、別の列にする** | **8**(`t1` 1 + `t2_*` 5 + `t3` 1 + `t1b` 1) |

**★どの案を採っても、§3.2 の表かコードのどちらかを直す必要がある。**
**エージェントは §3.2 を書き換えない**(事前登録の本体。`logs/HANDOFF.md` の禁止事項)。

**★この選択が効く先(3 つ。どれも小さくない)**

1. **ADR-061 決定1 が「`template` は 2 桁に届かない」と書いた根拠がこの水準数である。**
   分散成分の事前分布 `half-Student-t(3, 0, 2.5)` が感度解析の結果を実質的に決めると
   ADR-061 が明記しており、**その「実質的に決める」度合いは水準数で変わる**
2. **★`template` は `task` に入れ子である**(どの `template` も 1 つの `task` にしか属さない)。
   §3.2 は `(1 \| template)` と交差の形で書いているが、**実体は入れ子である。**
   `task` が固定効果なので推定はできるが、**「テンプレート間分散」はタスク型内の分散である**
3. **★単一テンプレートのタスク型は、そのテンプレートのランダム切片が `task` の固定効果と
   区別できない**(縮約を通してしか分離しない)。**案 (c) では 4 タスク型のうち 3 つが単一になる。**
   **案 (a) では単一は T1 の 1 つだけである**

**エージェントの推奨(採否は人間)**: **(a)**。**単一テンプレートのタスク型を最小にできる**からである。
**ただし推奨の重さは (i) 極性を「テンプレート」と呼んでよいか、(ii) §3.2 の文をどう直すか、
の 2 点に依存し、どちらも人間の判断である。**
**★(a) を採るなら、極性が均衡設計であること**(`t3_comparison.py` の冒頭。応答バイアス対策)
**をランダム効果として扱ってよいかを別途確かめる必要がある**(未検証)。

### 5.3 E-3: `task` の写像の置き場所

| 案 | 中身 | 備考 |
|---|---|---|
| **(a)** | **`code/analysis/frame.py` に写像表を持つ** | **3 つ目の定義になる**(F70)。ずれる |
| **(b)** | **`code/data_gen/battery_items.py` に束ねる関数を置く**(2 つの `CATEGORY_AXES` を統合) | **`Item` の schema と同じ場所。**「生成と評価の両方が使う」という既存の理由(冒頭 docstring)がそのまま効く。**import の向きは `battery_items` → `eval/battery/*` になり、現状(逆向き)と衝突する** |
| **(c)** | **`code/analysis/` に薄い dispatch を置き、2 本の `task_type_of` をそのまま呼ぶ** | 定義を増やさない。**未知の `category` で必ず落ちること**をテストで固定する |

**エージェントの推奨(採否は人間)**: **(c)**。**定義を増やさないため。**
**★どの案でも要る付帯条件**: **`specificity` 群と `t1_instructed` は主軸のタスク型を持たない。**
**黙って落とさず、明示的に「主軸外」として印を付ける**(F72)。

### 5.4 E-4: 主軸の行の絞り込みをどの層でやるか

**§3.2 は `data = primary`(= `p2` 条件のみ)と書いている。**
絞り込みの候補は `condition == "p2"` / タスク型が主軸の 4 水準 / `coverage` が主軸の 3 水準 の 3 つ。

| 案 | 中身 |
|---|---|
| **(a)** | **`frame.py` は絞らない。**全 run・全群・全被覆水準を 1 枚に出し、`primary.py` が `subset` する |
| **(b)** | **`frame.py` が解析名(`primary` / `order1` / `order1b` / `order7`)を引数に取り、その解析の表を返す** |

**エージェントの推奨(採否は人間)**: **(a)**。**絞り込みの規則を事前登録された解析の側に置けるため。**
`frame.py` が解析ごとに分岐すると、**「どの行が落ちたか」が 2 か所に散る。**

### 5.5 E-5: `main_radius` と K の正本

**`main_radius` は 2 か所にある**: run の `config.yaml` の `data.train_domain_max`(= 99)と、
FT manifest の `train_domain.hi`(= 99)。**現状は一致しているが、正本を決めていない。**

**K は `runs/<id>/` に無い**(F76)。案:

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **(a)** | **`config.yaml` の `data.matched_manifests` を辿って FT manifest を読む。**`pairs_hash` を照合する | 追加実装が要らない。FT manifest は git にある | **`runs/` の外のファイルに依存する。**パスが動くと解析が落ちる |
| **(b)** | **評価 run の `metrics.json` に `coverage.pairs_hash` と K の出どころを焼き込む**(`code/eval/run.py` を触る) | **run が自己完結する。**照合が run の記録として残る | **`code/eval/run.py` の変更である**(スコープの拡大)。**ただし本実験の run はまだ 1 本も無く、`results/` は空なので、いま入れるコストは最小である** |
| **(c)** | **評価プールの manifest から取る** | プールは 1 つ | **★成立しない。**プールの manifest に K は無い(F77) |

**エージェントの推奨(採否は人間)**: **(a) を実装し、(b) を人間に諮る。**
**(b) は `code/eval/run.py` の変更なので、この PLAN の範囲を超える**(`CLAUDE.md` §8)。
**★ただし (b) を採るなら本実験の前でなければ意味が無い。**判断の期限がある。

### 5.6 E-6: `passes_analysis_gate` 列(§2.3)

**閾値が未決である**(ADR-054 決定1 (ii)。N5 と同じ場)。

| 案 | 中身 |
|---|---|
| **(a)** | **列を作らない。**閾値が決まってから足す |
| **(b)** | **列は作るが、閾値が未設定なら例外で落とす**(黙って `True` を置かない) |
| **(c)** | **門の生の量(run ごとの `id` 到達度)を列にし、二値化は `primary.py` でやる** |

**エージェントの推奨(採否は人間)**: **(c)**。
**★ただし ★C(解析門が DiD のベースライン腕そのものに掛かっている。従属変数での選択)が未決である。**
**(c) は「門を掛ける量」を表に出す形なので、★C の決着に対して中立である。**
**(a) は決着を待つ形であり、これも中立である。**(b) だけが閾値の存在を先に仮定する。

### 5.7 E-7: 表の凍結

**★`runs/*/predictions/` は git に無い**(F79)。表は永続ボリュームからしか組めない。

| 案 | 中身 |
|---|---|
| **(a)** | **その場で組み、`primary.py` に渡す。**ファイルに残さない |
| **(b)** | **`results/` に CSV として書き、ハッシュを添える。**`primary.py` はその CSV を読む |
| **(c)** | **(b) + 入力の run_id 一覧と FT manifest の `pairs_hash` を同じ場所に残す** |

**エージェントの推奨(採否は人間)**: **(c)**。**`CLAUDE.md` §2 が「すべての数値は `results/` の
ファイルと run_id に紐づくこと」を求めており、主要検定の入力そのものがその対象だからである。**
**ADR-058 決定2(解析を実験環境から切り離す)とも噛み合う** —— 切り離すなら、
**解析側が受け取るのは `predictions/` ではなくこの CSV である。**

---

## 6. 決まった後に IMPLEMENTER がやること(§5 が決まるまで着手しない)

1. `code/analysis/frame.py`。**§4.1 の 6 手順。**`--dry-run` で件数だけ出す経路を持つ
2. **E-1 の絞り込み**(採択案が (c) なら `code/data_gen/pool.py` に `label_main_coverage`)
3. **E-3 の `task` 写像**(採択案の場所へ)。**未知の `category` で必ず落とすこと**
4. **E-2 の `template` 写像。★§3.2 の表と食い違う場合は、人間が §3.2 を直してから実装する**
5. `pytest code/tests` に足す回帰テスト(**§8**)
6. `logs/CHANGELOG.md` / `logs/DECISIONS.md`(ADR。**提案者と採択者を分ける**。ADR-039)

---

## 7. やらないこと

- **`Documents/05_STATISTICS.md` §3.2 を書き換える**(事前登録の本体。人間が直す)
- **`code/eval/run.py` を触る**(E-5 案 (b)。**スコープの拡大なので人間に諮る**)
- **解析門の閾値を決める**(N5)/ **`M*` を決める** / **`θ` を決める**
- **`code/analysis/primary.py` を書く**(PLAN-016 §7-5。この PLAN の範囲外)
- **新しい検査を建てる**(§8 は既存の `pytest` に足すもので、GPU も合成データも要らない)

---

## 8. 想定される交絡と検査

| 交絡 | 対策 | 実装場所 |
|---|---|---|
| **K を取り違える**(別条件の manifest を読む) | `lesion.condition` で名指しで引き、`pairs_hash` を照合する | `frame.py` |
| **`extrap_pair` が `extrap_magnitude` に混ざる** | **§4.2 の絞り込み。**`(300, 50)` と `(-99, 1)` を落とす回帰テスト | `pytest` |
| **主軸から落ちた行が黙って消える** | **落とした件数を run ごとに記録する**(§5.1 の付帯条件) | `frame.py` |
| **`task` の写像が未知の `category` を素通しする** | 未知で例外。**`spec_sub` / `t1_instructed` は「主軸外」の明示的な印** | `pytest` |
| **`seed` が評価側の seed とすり替わる** | **F75。**`metrics.json` の `seed` は訓練 run のもの。**アダプタ無しの run では `None` である**(`code/eval/run.py:894`。**0 を置かない**)。`None` の行が主軸に混ざったら落とす | `frame.py` / `pytest` |
| **項目集合が run 間で食い違う** | **§3.2.1 の生きている制約**(「比較する解析の内部では項目集合が完全に一致していること」)。**run 間で `item` の集合が一致しない場合に落とす** | `frame.py` |

**★より退屈な仮説**(`CLAUDE.md` §7): **この層のバグは「交互作用が出た」という形で現れる。**
`coverage` の絞り込みを間違えて `extrap_pair` を `extrap_magnitude` に混ぜると、
**タスク型ごとに混入率が違えば、それだけで `task:coverage` が有意になる。**
**ラベル入れ替え検定(PLAN-016 §7-6)はこれを検出しない** —— 入れ替えても混入は同じだからである。
**§8 の 2 行目の回帰テストがこの層で唯一の防波堤である。**

---

## 9. 完了条件

- [x] **§5 の E-1 〜 E-7 に人間の決定がある**(ADR-062。提案 エージェント (Opus) / 採択 人間)
- [x] `pytest code/tests -q` が通る(**831 passed**。2026-09-07 その17)
- [x] **§8 の回帰テストが入っている**(`code/tests/test_frame.py` 17 件 + `test_pool.py` 3 件)
- [x] **`--dry-run` が件数だけを出して成功する**(`test_dry_run_prints_counts_and_writes_nothing`)
- [x] `logs/CHANGELOG.md` と `STATE.md` を更新した
- [x] **主軸から落ちた行の件数が記録に残る**(`RunSummary.n_dropped_by_reason`。理由は排他ではない)

---

## 10. 実行ログ

| 日付 | 何をしたか | run_id | 担当 |
|---|---|---|---|
| 2026-09-07(その16) | 起草。**実地確認 F63 〜 F79。決定 0 件** | — | PLANNER (Opus) |
| 2026-09-07(その16b) | 人間が E-1 〜 E-7 の 7 件を決定(ADR-062) | — | 人間 |
| 2026-09-07(その17) | **§6 を実装。`pytest` 831 passed。GPU 0。** **新事実 F80 / F81** | — | IMPLEMENTER (Opus) |
