# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-26 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 270k / 閾値 140k で警告)
直近 commit: `ccbcb0e`(feat: T1 / T2 / 特異性対照の項目生成)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

## このセッションでやること(1つだけ)

**`code/eval/run.py` に数値経路(cot → numeric)を配線する。**
`STATE.md`「次のアクション」の **A-5**。段階 A に残っているのは A-5 と A-6 の2つで、
これはその前半です。**A-6(評価プールを書き出す CLI)には手を出さないでください。**

完了条件(全部満たすこと):

1. `parse_numeric_response(text, elicitation)` を `code/eval/run.py` に追加する。
   `direct` は `numeric.parse` のみ、`cot` は `cot.extract_final_answer` → `numeric.parse`。
   既存の `parse_boolean_response` と**同じ形**にする(§5.5)
2. `dry_run` のバッテリ分岐を作る。いま `list(batteries) != ["comparison"]` で
   `ConfigError` にしている箇所を、群ごとのディスパッチに置き換える:

   | 群 | 項目生成 | 応答型 | 参照規則の渡し方 |
   |---|---|---|---|
   | `comparison` | `t3_comparison.build_items` | bool | 辞書 |
   | `bare_sum` | `numeric_sum.build_bare_sum_items` | int | 辞書 |
   | `word_problem` | `numeric_sum.build_word_problem_items` | int | 辞書 |
   | `specificity` | `specificity_control.build_items` | int | **単体(`Lesion` 1個)** |

3. `configs/smoke.yaml` に4群ぶんの `dry_run_items` を書き、
   `configs/templates/smoke.yaml` に `bare_sum` / `word_problem` / `specificity` の
   **配線確認専用の文面**を足す
4. `code/tests/test_run_dry_run.py` に数値経路のテストを追加し、
   `pytest code/tests -q` を通す(**現在 390 passed**)
5. `logs/CHANGELOG.md` に追記 → commit

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **T1 / T2 / 特異性対照の項目生成は実装済み**(commit `ccbcb0e`)。
  `code/eval/battery/numeric_sum.py` / `code/eval/battery/specificity_control.py`。
  `pytest code/tests -q` → **390 passed**(2026-08-26 実測)
- `code/data_gen/prompt_format.py` を新設し、`pool.build_manifest` に
  `prompt_format_block` / `item_exclusions` を**必須引数**として追加した
- `battery_items.SUPPORTED_GROUPS` = `("comparison", "bare_sum", "word_problem", "specificity")`
- **実験結果の数値は1つも無い。**`results/` は空。GPU 時間 0。事前登録は未凍結(tag なし)
- 詳細は `STATE.md` の「引き継ぎ」と `logs/CHANGELOG.md` 2026-08-26

## 読むべき範囲(全文 cat しない。`grep -n` → `sed -n 'X,Yp'`)

- `code/eval/run.py` 全体(192行)。**これだけは全部読んでよい**
- `code/eval/battery/numeric_sum.py` の `build_bare_sum_items` /
  `build_word_problem_items` / `to_response` / `render_prompt` / `bare_sum_templates`
- `code/eval/battery/specificity_control.py` の `build_items` / `to_response`
- `code/tests/test_run_dry_run.py`(8件)。既存の書き方に合わせる
- `configs/smoke.yaml` の `eval:` 節と `configs/templates/smoke.yaml`

## 実装で必ず踏む穴(直前セッションが確認済み)

- **`to_response` のシグネチャが群で違う。**`specificity_control.to_response` は
  参照規則を**単体で**受ける(`reference_lesion`)。他の2つは**辞書**(`reference_lesions`)。
  一括ループで回そうとすると必ずここで詰まる
- **`render_prompt` の引数も違う。**`t3_comparison` は `{threshold}` を差し込むが、
  `numeric_sum` / `specificity_control` は `{a}` `{b}` だけ
- **T1 の文面はテンプレート集合から取ってはならない。**
  `numeric_sum.bare_sum_templates(config)` を使い、`data.prompt_template` から組む。
  評価用テンプレート集合から引くと、評価アンカーが訓練書式から静かに離れ、
  preflight の検査6 が「訓練と評価で書式が違う」で止まる
- **減算項目と乗算項目を同じ採点バッチに混ぜない。**`rule_values` のキーが違うので
  `scoring._shared_reference_rules` が止める(**止まるのが正しい**)。群の中で
  category ごとに分けて `metrics_by_reference_rule` を呼ぶこと
- **特異性対照の参照規則は `lesion.specificity_reference_lesions_from_config` から取る。**
  `reference_lesions_from_config`(p2 / x2 / p2d / arb)を渡すと `build_items` が止める
- **`scoring.validate_reference_rule` は manifest の `reference_rules` に名前があることを
  要求する。**特異性対照(`spec_sub` / `spec_mul`)をどう通すかは未解決 → 下記
- `DRY_RUN_RESPONSES` は `"Yes." / "No." / "Maybe."` で**二値用**。数値用の固定応答が要る。
  **実験の刺激ではないと明記すること**(既存のコメントと同じ扱い)

## やってはいけないこと

- **`configs/templates/t2.yaml` を `data.eval_template_set` に配線しない。**
  T1b / T3 の本番文面が未確定でテンプレート集合が未完成である
- **`configs/templates/t2.yaml` の確定文面を `smoke.yaml` に書き写さない。**
  二重管理になり、ADR-032 の正本がどちらか分からなくなる。smoke は**別の**
  配線確認専用の文面にする(`smoke.yaml` 冒頭の宣言どおり)
- **T1b / T3 / T2 の本番文面を自分で書かない**(実験条件。`CLAUDE.md` §8)
- **numeric パーサの「数が2個以上なら parse_fail」を緩めない**(PLAN-001 §5.4 の 4)。
  文章題は復唱で数が複数出るが、**それを通すのは ADR-032 決定3 の答え書式の指示の役目**であって
  パーサを緩めることではない
- 4値分解の合計を 1.0 から外さない。`data/raw/` を書き換えない
- **文書の不整合を独断で直さない**(`STATE.md`「repo の状態」表に古い行が数件ある。
  引き継ぎブロックの5に列挙済み)
- **A-6(評価プール CLI と `eval.cells` を持つ config)に手を出さない。**1セッション1タスク

## 未解決 / 人間の承認待ち(独断で決めない)

- **(新規・A-5 の途中で当たる)** 特異性対照の参照規則名(`spec_sub` / `spec_mul`)を
  プール manifest の `reference_rules` にどう載せるか。載せないと
  `scoring.validate_reference_rule` が通らないが、あの欄は「§4.3 の偶然一致の除外を
  どの規則で計算したか」の記録である。**この決着は A-6(manifest を書く側)の話なので、
  A-5 では `--dry-run` の経路に限って回避してよい**(回避したことを CHANGELOG に書く)
- **#18** T1 にも答え書式の指示を足すか(ADR-032 決定3 の交絡)
- **#19** 被演算子 1 の除外を全タスク型に広げるか
- **#9** 適格性フィルタ 0.70 / **#16・#11** Feucht と G7 / **#13** `table[1]` の穴
- **PLAN-002 §12-11** `p2d` 判別不能の除外を `K` の抽出母集団に掛けるか
- **直前セッションが独断で決めた命名**(凍結までに人間が一度見ること。
  `STATE.md` 引き継ぎブロックの表): 群名 `bare_sum` / `specificity`、
  category `t1` / `spec_sub` / `spec_mul`、**T2 のテンプレート割当を
  `(pool_id, a, b)` の sha256 にした**(§4.3 の「`item_id` のハッシュ」は循環するため)

## 状態(2026-08-26 時点)

- `pytest code/tests -q` → **390 passed**(3.5 秒)。`results/` は空。GPU 時間 0
- **preflight の検査6・8 は FAIL のまま。**A-6 が終わるまでそれが正しい
- 直近 commit: `ccbcb0e`(コード)/ このセッションの引き継ぎコミット
- `ruff` / `black` はこの環境に未インストール。行長 100 は手で確認すること
