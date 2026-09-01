# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-01 / 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **順4 の第1条件(= PLAN-008)が閉じた。**残りは人間の決定待ちである。

---

あなたは **PLANNER(または人間の決定を受ける IMPLEMENTER)** です。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**GPU は使いません(GPU 時間 0)。**

## 直前セッションで終わったこと(再実装しないこと)

**commit `9491196`(sha 記入は `48e3604`)。`pytest code/tests -q` → 788 passed。GPU 時間 0。`results/` は空。**
正本は **`plans/PLAN-008-order4-data-regen.md`** + **`logs/DECISIONS.md` の ADR-049** + `logs/CHANGELOG.md` 末尾。

順0(2026-08-27)で人間が決めた **ADR-034 / ADR-035 の持ち越し3件**を実装した:

1. **指示付き T1 の群 `bare_sum_instructed` を新設**(`SUPPORTED_GROUPS` 4群 → 5群)。
   category・タスク型は `t1_instructed`(**主軸4水準に混ぜない**)。**副次セル**であり
   主軸の交互作用モデルには入れない。採点は自由生成の数値パースのまま。
   **文面はテンプレートファイルを作らず config から組む** ——
   `data.prompt_template` + 半角空白1つ + **新設 `data.answer_format_instruction`**。
   **`configs/templates/` に差分は出していない**(ADR-046 / 048 の凍結)。
2. **被演算子 1 の除外を全タスク型の評価項目に広げた。**規約の持ち主を
   `numeric_sum` → **`code/data_gen/pool.py`**。manifest の `item_exclusions` は
   **プール全体の欄**(群ごとの内訳つき)。**桁数掃引には掛けていない**(回帰テストで固定)。
3. **評価プール manifest に `id_cell_population` を新設**(`build_manifest` の必須引数)。
   設計事実テストが **`K = 2,000 → 1,808(carry 393)→ 1,776(carry 386)`** を固定した ——
   PLAN-003 §4.7 の手計算と一致。**組合せ論的な計数であって実験結果ではない。**

---

## いま人間に返っているもの(`CLAUDE.md` §8)

### (a) 覆してよい命名・書式(ADR-049 決定1・3。読んで閉じるだけ)

| 確定したこと | 値 |
|---|---|
| 群名 | `bare_sum_instructed` |
| category・タスク型 | `t1_instructed` |
| 指示文の区切り | 半角空白1つ |

ADR-035 リスク欄が群名を実装に授権した範囲。覆す場合に動くのは
`SUPPORTED_GROUPS` / `CATEGORY_AXES` / `RENDERERS` / config の3箇所だけである。

### (b) 順4 の第2・第3条件を塞いでいる未決(人間にしか決められない)

**本番 config(5条件)が作れない。**内訳は `plans/PLAN-008` §5。

| # | 欄 | なぜ塞がるか |
|---|---|---|
| **B1** | `lesion.arbitrary_table` | **承認待ち-3。****`[MATCHED]` なので `arb` を回さない4条件の config にも書けない** —— これ1件で5条件そろわない |
| **B2** | `data.train_size` | 掃引軸 {2000, 4000, 10000} のうち順4 で焼き込む1点が未決 |
| **B3** | `data.coverage_k` | 「主値 2000」は提案であって採択ではない。掃引軸にするかも未決 |
| **B5** | `eval.pool_items` の本番の中身 | **`M*` 未決**のあいだ `fill_cells` の経路に移せない(ADR-033 決定4)。**順5 の後** |

**まだ閉じていない古い承認待ち**: ADR-047 実装ノートの **R3 / F1 / R4 / 検査5**(強制選択の器械仕様。
実装済み。人間が読んで閉じる)/ **θ の値**(ADR-041。順5 の掃引表を見てから)。

---

## 次にできること(どれを選ぶかは人間)

1. **人間が B1〜B3 を決める** → IMPLEMENTER が本番 config を作り、`ft_data.py` / `eval_pool.py` を
   回して preflight を通す(= 順4 の第2・第3条件)。**B5 は順5 の後なので、この時点でも
   `extrap` セルは埋まらない。黙って空にしないこと。**
2. **順5 に進む(= `M*` の実測)。****人間の GPU 承認が要る。**
   その前に RUNNER が **N2**(comparison 群でバッチ1 対 バッチ N の `parsed` 一致確認)を取り、
   実機で `pip freeze` → ADR-044(lock 凍結)を履行する。
   **preflight の `forced choice tokens` が WARN / FAIL を出したら人間に上げて止まる。**
3. **順7 の一部**(検出力分析の再導出 / `09_PAPER_PLAN.md` の追随)は GPU 不要で進められる。
   `STATE.md`「現在のブロッカー」に未追随の文書が3件ある。

## やってはいけないこと

- **B1〜B5 に値を入れる**(実験条件の決定。`CLAUDE.md` §8)
- 合否基準・しきい値・Go/No-Go 判定コード・`θ`・`M*` を書く / 提案して決める
- **凍結済みのプロンプト文面を変える**(ADR-046 / 048。`configs/templates/` に差分を出さない)
- **強制選択の器械を触る**(人間の最終確認待ち)
- `configs/smoke.yaml` を編集する(ADR-037 決定4)/ `data/raw/` を書き換える
- 人間の承認なく GPU ジョブを起動する
