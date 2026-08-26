# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-26 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 125k / 閾値 100k で警告)+ A-5 完了
直近 commit: `47d2cda`(feat(eval): run.py に数値経路を配線し4群ディスパッチにした)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

## このセッションでやること(1つだけ)

**A-6 = 評価プールを書き出す入口(CLI)を作り、preflight の検査6・8 を PASS にする。**
`STATE.md`「次のアクション」の A-6。**これが段階 A の最後である。**

完了条件(全部満たすこと):

1. 評価プール(項目 + manifest)を書き出す CLI を作る。既存の
   `python -m code.data_gen.ft_data --config ... --dry-run` と同じ形にする
2. manifest に `prompt_format.build_from_config(config)` と
   `numeric_sum.word_problem_exclusion_record(...)` を渡す
   (`pool.build_manifest` の `prompt_format_block` / `item_exclusions` は**必須引数**)
3. `eval.anchor_manifest` / `eval.cells` を持つ config を用意する
4. **`infra/preflight.py` の検査6・8 が PASS になる**(いまは FAIL。それが正しい状態だった)
5. `pytest code/tests -q` を通す(**現在 405 passed**)→ `logs/CHANGELOG.md` 追記 → commit

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **A-5 完了**(commit `47d2cda`)。`code/eval/run.py` に
  `parse_numeric_response(text, elicitation)` を追加し、`dry_run` を
  **4群(`comparison` / `bare_sum` / `word_problem` / `specificity`)のディスパッチ**にした。
  `--dry-run` は4群とも通る(**17 項目**)。**本実行は依然 `NotImplementedError`**
- **返り値の形が変わった**: `report["by_response"]` → **`report["by_batch"][バッチ名]`**。
  バッチ名は群名、ただし特異性対照だけ category(`spec_sub` / `spec_mul`)
- `configs/smoke.yaml` の `eval.dry_run_items` は**各項目に `group` が必須**になった
- `pytest code/tests -q` → **405 passed**(2026-08-26 実測)
- **実験結果の数値は1つも無い。**`results/` は空。GPU 時間 0。事前登録は未凍結(tag なし)
- 詳細は `STATE.md` の「引き継ぎ」と `logs/CHANGELOG.md` 2026-08-26

## 読むべき範囲(全文 cat しない。`grep -n` → `sed -n 'X,Yp'`)

- `code/data_gen/pool.py` の `build_manifest`(必須引数の並び)
- `code/data_gen/ft_data.py` の CLI 部分(**入口の書き方の手本**。同じ形に揃える)
- `infra/preflight.py` の**検査6・8** だけ(`grep -n "検査6\|検査8"`)
- `code/data_gen/prompt_format.py` の `build_from_config`
- `code/eval/battery/numeric_sum.py` の `word_problem_exclusion_record` /
  `eligible_word_problem_pairs`
- `code/eval/run.py` の `dry_run` docstring(**下の未解決1件がそこに書いてある**)

## 実装で必ず踏む穴

- **特異性対照の参照規則 `spec_sub` / `spec_mul` を manifest の `reference_rules` に
  どう載せるかが未決である**(下の「未解決」)。`scoring.validate_reference_rule` は
  あの欄に名前があることを要求する。**A-5 は `--dry-run` の経路に限って回避した**が、
  **manifest を書く A-6 では回避できない。**あの欄は「§4.3 の偶然一致の除外を
  どの規則で計算したか」の記録であり、`spec_sub` / `spec_mul` は
  `reference_lesions_from_config` に**混ぜてはならない**(混ぜると FT データの
  除外集合が変わり、PLAN-002 §3.4 の対照の設計が壊れる)。**独断で決めない**
- **T2 の被演算子 1 の除外は `fill_cells` に渡す前に掛ける**
  (`eligible_word_problem_pairs`)。後段で落とすと件数が静かに減る
- **T1 の文面はテンプレート集合から取らない。**`numeric_sum.bare_sum_templates(config)`
  = `data.prompt_template` から組む。検査6 が `format_hash` を照合する
- **被覆層(id / interp / extrap)のセルの埋め方は未決定**(`CLAUDE.md` §8)。
  A-6 でサンプリング方針を勝手に決めない。決まっていない部分は
  `--dry-run` と同じく **config の明示リスト**で通すこと

## やってはいけないこと

- **`configs/templates/t2.yaml` を `data.eval_template_set` に配線しない。**
  T1b / T3 の本番文面が未確定でテンプレート集合が未完成である
- **T1b / T3 / T2 の本番文面を自分で書かない**(実験条件。`CLAUDE.md` §8)
- **`configs/templates/smoke.yaml` の仮文面を本番に昇格させない。**
  あれは配線確認専用だと冒頭に宣言してある
- **numeric パーサの「数が2個以上なら parse_fail」を緩めない**(PLAN-001 §5.4 の 4)
- 4値分解の合計を 1.0 から外さない。`data/raw/` を書き換えない
- **本実行(モデルの読み込みと生成)を実装しない。**A-6 の範囲外であり、
  既定のモデル名・生成設定をここで作らない(skill code-style §5)
- **文書の不整合を独断で直さない。**`STATE.md`「repo の状態」表に**古い行が数件ある**
  —— 「出力パーサ**6**モジュール」(実際は5)、「評価側の `arb` 定義域ガードは未実装 /
  `g6_comparison.py:89`」(2026-08-25 に解消済、ファイル名も変わった)、`pytest` の
  古い件数の行が複数。**次にこの表をまとめて触る人が一度整理すること**

## 未解決 / 人間の承認待ち(独断で決めない)

- **★A-6 の本体に当たる** 特異性対照の参照規則名(`spec_sub` / `spec_mul`)を
  プール manifest の `reference_rules` にどう載せるか。**A-5 は `--dry-run` に
  限って回避した。A-6 では回避できない。**
- **#18** T1 にも答え書式の指示を足すか(ADR-032 決定3 の交絡)
- **#19** 被演算子 1 の除外を全タスク型に広げるか
- **#9** 適格性フィルタ 0.70 / **#16・#11** Feucht と G7 / **#13** `table[1]` の穴
- **PLAN-002 §12-11** `p2d` 判別不能の除外を `K` の抽出母集団に掛けるか
- **実装で決めた命名**(凍結までに人間が一度見ること。`STATE.md` 引き継ぎブロックの表):
  群名 `bare_sum` / `specificity`、category `t1` / `spec_sub` / `spec_mul`、
  **T2 のテンプレート割当を `(pool_id, a, b)` の sha256 にした**、
  **`report["by_batch"]` のバッチ名**

## 状態(2026-08-26 時点)

- `pytest code/tests -q` → **405 passed**(3.8 秒)。`results/` は空。GPU 時間 0
- **preflight の検査6・8 は FAIL のまま。A-6 がそれを PASS にする作業である**
- 直近 commit: `47d2cda`(コード)/ このセッションの引き継ぎコミット
- `ruff` / `black` はこの環境に未インストール。行長 100 は手で確認すること
