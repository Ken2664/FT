# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-30 / 直前セッションの役割: IMPLEMENTER(実装)+ IMPLEMENTER(Opus によるレビュー)
直前セッションが終了した理由: PLAN-007 §4(強制選択採点器)の実装が完了し、
別モデルでのレビューも終わって区切りが良い。**ただしレビューで下流の破損2件(R1 / R2)が出た。**
次は「R1 / R2 の修正」→「PLAN-004 順4」の2本で、どちらも GPU 時間 0。

---

あなたは IMPLEMENTER です。CLAUDE.md §1 の開始手順を実行してから作業を始めてください。
skill `code-style` を読んでから実装に入ること。RunPod 不要。GPU も使いません(GPU 時間 0)。

## 直前セッションで終わったこと(STATE.md 冒頭★★★★★★★★★★★ブロックが正本)

**PLAN-007 §4 / ADR-047 を実装した —— 二値出力群(`comparison` = T1b + T3)を
自由生成 + `boolean` パースから強制選択採点(Yes/No の対数尤度を1 forward pass で比較)に
切り替えた。プロンプトは1文字も変えていない。**

| commit | 中身 |
|---|---|
| `d854213` | 本体。`code/eval/forced_choice.py` / `code/eval/engine.py` 新設 + `code/eval/run.py` 改修 |
| `1027a3f` | 上の sha を STATE / CHANGELOG / DECISIONS / PLAN-007 に記入 |
| `529572c` | レビューで見つかったテストの穴を塞いだ(`metrics.json` の `scoring` の回帰テスト) |
| `c222aa3` | `529572c` の sha 訂正(`--amend` で sha が変わっていた) |

- 決定規則 `choose_from_logprobs`(torch 不要): 候補 `{Yes, No}` の変種(大小文字3 × 先頭空白2 = 6綴り)の
  最初の内容トークンの `log_softmax` 対数尤度の**各側最大どうし**を比較、大きいほう(**同点は No**)。
- 重みは `engine.build_engines` が**1度だけ**読み、生成器と採点器で共有(bf16 8B を二度読むと 4090 に載らない)。
- **数値経路(T1 / T2 / specificity)は不変。**二値群は `elicitation` を参照しない(`direct` 固定)。
- 採点方式は `metrics.json` の `by_batch[*].scoring`(`forced_choice` / `free_generation`)と `log.txt` に残る。
- `assert_collapsed_to_binary` が構築時に `parse_fail_rate == 0` / `other_error_rate == 0` を検査。
- `parse_boolean_response` / `code/eval/parsers/boolean.py` は**残してある**(案 C backstop / 手監査)。
- **合否基準・Go/No-Go 判定コード・θ は書いていない**(ADR-047 決定6)。

`pytest code/tests -q` → **740 passed**。`results/` は空。GPU 時間 0。

## ★このセッションでやること(2本。順番どおり)

### (0) レビュー指摘 R1 / R2 を直す —— **順5(実機)より前に必須**

**正本は STATE.md「人間の承認・判断を待っている事項」の★★★★★2026-08-30 ブロック。**

強制選択には生成文が無いので、`predictions/*.jsonl` の `response` 欄に**合成文字列**を入れた:

```
Yes [forced_choice yes_logp=-0.1235 no_logp=-2.7654]
```

`response` を「モデルが実際に生成した文字列」として読む消費者が2つあり、どちらも壊れている。

- **R1 `code/analysis/token_length.py`** —— `comparison` バッチの合成文字列をトークン数として数える
  (`scoring` も `group` も見ていない)。実トークナイザでは logprob の数字が細かく割れて 20 トークン超になる。
  **`token_length.json` は #20 `max_new_tokens` の改訂根拠**(ADR-042 決定6 / ADR-038)なので、
  汚染された表を段階 C で人間が読むことになる。
  - **案(採否は人間)**: `metrics.json` の `by_batch[*].scoring` を読み、`forced_choice` の群を
    集計から外す。ただし **黙って消さず** `by_batch` に `scoring: forced_choice, skipped: true` を
    1行残す(強制選択は生成していないので「答えのトークン長」が定義されない、と読めるように)。
- **R2 `code/analysis/compare_runs.py:210`** —— `left.response == right.response` の文字列一致。
  **logprob はまとめ幅で必ず揺れる**ので、答えが一致していても comparison は全件「不一致」に出る。
  - **ADR-040 決定2 が文字列一致を「記録のみ・合否に使わない」としているので Go/No-Go は壊れない。**
    合否は決定1(4値分類 + `parsed`)であり、`parsed_consistency`(ADR-045)は bool を比べるので正しく効く。
    直す理由は「報告が誤読される」ことだけである。
  - **案(採否は人間)**: `compare()` が `scoring` を見て、強制選択の群では文字列一致ではなく
    `parsed`(bool)一致を使う。または合成文字列から logprob を落として答えだけを比べる。

**どちらも合否基準を作る変更ではない**(ADR-041 / ADR-045 の線は動かさない)。
**人間が案を採るまで着手しない**(`CLAUDE.md` §8 / ADR-039)。採択されたらテストを添えて実装する。

**併せて人間に確認してもらうこと(R3 / R4。実装者が決めてしまった器械仕様。ADR に無い)**:
- **R3**: 変種の集約が **`max`(最尤の綴り1つ)**であって `logsumexp`(綴りをまたぐ確率の和)ではない。
  「P(Yes) の推定」としては和が正しい。チャットテンプレート直後はほぼ1綴りに質量が乗る見込みなので
  実害は小さいが、**二値の主要測定の器械仕様**である。
- **R4**: **同点は No に倒す**(決定性のための規約。判別可能な項目では起こらない)。
- ADR-047 リスク欄は「Yes/No トークンの取り方は実装で確定する」と授権しているが、
  決まった中身は `forced_choice.py` の docstring にしか無い。**採否が出たら ADR-047 に追記する。**

**R5 / R6 / R7 は軽微(記録のみ。対応は任意)** —— STATE.md の該当ブロックを参照。

### (1) PLAN-004 順4 —— 本実験のデータ再生成(GPU 不要)

**正本は `plans/PLAN-004-phase0-route.md` の「順4」節(§3)。**

- [ ] 順0 の決定を `code/data_gen/` と config に反映
- [ ] **本番 config(5条件)**で `ft_data.py` / `eval_pool.py` を実行
- [ ] `infra/preflight.py` の `data_checks` が**本番 config で**全項目 PASS

**前提はすべて揃っている**:
- `data.eval_template_set: eval_main` が使える(ADR-046 + **ADR-048**)。
  **eval_main = T1b + T3 + T2 + specificity の4群**。T1(`bare_sum`)は `data.prompt_template` から組む。
- 並行ブランチは破棄済(2026-08-30)。再生成の経路の二択は解消している。
- 強制選択採点器が入ったので **`comparison` 群の評価経路も完成**している
  (`eval_pool` はプールを書くだけなので直接の依存は無い)。

**注意**:
- `configs/smoke.yaml` は**3条件しか宣言できない**(`digit_modulus` / `arbitrary_table` が無い)。
  **本実験は5条件そろえること**(PLAN-002 §3.4)。
- **`extrap` セルは `M*` 未決なので原理的に埋まらない**(順5 の後。ADR-033 決定4)。
- **順4 に持ち越した実装の申し送り3件**(ADR-035 が仕様を持つ。PLAN-004 §3 の該当ブロック):
  1. **指示付き T1** の群を新設(`SUPPORTED_GROUPS` は現状4群)。`id` × {carry, nocarry} の
     2セル・n=40 = **80 項目**。**主軸の交互作用モデルには入れない**
  2. **被演算子 1 の除外を全タスク型の評価項目に広げる**(`K` には広げない)。
     manifest の `item_exclusions` を**プール全体の欄**に `excluded_operands: [1]` を持つ形にする
  3. **`id` セルの母集団は `K` そのものではない**(ADR-034 の帰結)。`t ≡ 0 (mod 10)` を落とした
     **1,808 / 2,000 組**から引く。落ちる組はすべて `nocarry` なので carry 層は 393 のまま

## 読むべき範囲(全文 cat しない。grep -n → sed -n 'X,Yp')

- **STATE.md 冒頭の★★★★★★★★★★★ブロック**と「人間の承認・判断を待っている事項」の
  ★★★★★2026-08-30 ブロック(R1〜R7。**このセッションの入口**)
- `plans/PLAN-004-phase0-route.md` の「順4」節 + 「順4 に持ち越した実装の申し送り」(grep -n "順4")
- `logs/DECISIONS.md` の **ADR-035**(申し送り3件の仕様)/ **ADR-034**(`id` 母集団)/
  **ADR-033 決定4**(`extrap` が埋まらない理由)
- R1: `code/analysis/token_length.py`(263行。`read_responses` / `by_batch` / `payload`)
- R2: `code/analysis/compare_runs.py`(`compare` ~195-232 / `compare_parsed` ~234-290)
- `code/eval/forced_choice.py`(R3 / R4 の該当は `answer_variants` / `choose_from_logprobs`)
- `code/data_gen/eval_pool.py` / `code/data_gen/ft_data.py` / `code/data_gen/pool.py`(順4 の本体)
- `infra/preflight.py` の `data_checks`(順4 の完了条件)

## やってはいけないこと

- **R1 / R2 / R3 / R4 を人間の採否なしに実装・確定する**(`CLAUDE.md` §8 / ADR-039。案出しは可)。
  特に **R2 で `compare_runs` に合否基準を作らない**(ADR-045 決定2)。
- **合否基準・しきい値・Go/No-Go 判定コードを書く**(ADR-047 決定6 / ADR-045 決定2 / ADR-041)。
- **プロンプト文面を変える**(ADR-046 / ADR-048 で凍結済。ADR-047 決定1 の肝は「1文字も変えない」)。
- **数値経路(T1 / T2 / specificity)の採点を触る。**強制選択は `comparison` 群だけ。
- **θ の値や `M*` を提案・決定する**(ADR-041。順5 の掃引表を見てから人間が決める)。
- **`extrap` セルを埋める**(`M*` 未決。ADR-033 決定4)。
- **`data/raw/` を書き換える**(CLAUDE.md §2)。
- 事前登録した予測・解析計画を実験後に変更する(事前登録は未凍結なので本文の書き換えは可)。
- 人間の承認なく GPU ジョブを起動する。

## 次(このセッションの後)

- **GPU を使う次の段 = 順5**(桁数掃引 → `M*`)。**要 θ の値 + GPU 承認。**
  PLAN-006(掃引のマルチシード化)は完了済。**R1 / R2 はこの前に直っていること。**
  その実機で `pip freeze` を取り **ADR-044**(lock の凍結)を履行する。
- 順6(Go/No-Go #0〜#3)で **T1b / T3 を初めて測る**。ここで ADR-047 のラダー
  (案 C backstop = `none` の T1b × `id` が常答ベースラインを超えられないなら主軸から外す)を評価する。

## 未解決 / 人間の承認待ち(CLAUDE.md §8)

1. **θ の値**(ADR-041。順5 の掃引表を見てから人間が決める)。
2. **R1 / R2 の直し方**(上記の案の採否)。**順5 より前。**
3. **R3 / R4 の器械仕様の追認**(変種集約が `max` / 同点は No)。採否が出たら ADR-047 に追記する。

**R5 / R6 / R7 は記録のみで、止まる理由にはならない**(STATE.md の該当ブロック)。
