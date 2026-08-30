# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-30 / 直前セッションの役割: PLANNER+IMPLEMENTER
直前セッションが終了した理由: 人間の4決定の反映 + PLAN-006 §4 実装が完了し、区切りが良い。
残るのは PLAN-007 §4(強制選択採点器)の実装1本 —— これは独立の IMPLEMENTER セッションに値する。

---

あなたは IMPLEMENTER です。CLAUDE.md §1 の開始手順を実行してから作業を始めてください。
skill `code-style` を読んでから実装に入ること。RunPod 不要。GPU も使いません(GPU 時間 0)。

## 直前セッションで終わったこと(STATE.md 冒頭★★★★★★★★★★ブロックが正本)

人間が会話で決めた4件を全件ファイルに反映した:
- 決定4 → commit `e8f9c8d`: 並行ブランチ `claude/objective-mestorf-34f57d` を破棄。
- 決定3 → commit `1d1f57d`: `eval.magnitude_sweep.seeds = [0,1,2,3,4]`(ADR-041 2026-08-30 追記)+
  **PLAN-006 §4 実装完了**(`code/eval/sweep.py` / `magnitude_sweep.py` のマルチシード化)。
- 決定1 → commit `eccf1fb`: **ADR-047**(案 A = 二値出力群 T1b+T3 を強制選択採点 + 案 C を backstop に先行登録)。
- 決定2 → commit `b01eed2`: **ADR-048**(specificity の符号 `-`=U+002D / `*`=U+002A。`eval_main.yaml` に追加)。

`pytest code/tests -q` → **713 passed**。`results/` は空。

## このセッションでやること(1つ) —— PLAN-007 §4 の強制選択採点器を実装する

**正本は ADR-047(logs/DECISIONS.md)と plans/PLAN-007-t1b-gonogo-branch.md §4。**
PLAN-007 §4 の7手順そのまま:

1. **強制選択採点器**: `code/eval/` に二値項目のロジット読み経路を足す。
   - テンプレート適用後、候補 `{"Yes", "No"}`(+ 大文字小文字・先頭空白を正規化した変種集合)の
     最初の内容トークンの対数尤度を比較し、大きいほうを答えにする。
   - **候補集合は明示定数**(code-style §1。マジックストリング禁止)。トークナイザ依存の変種展開は
     1関数に閉じ、ユニットテストで固定する。
   - `parse_fail` は返さない(構造上出ない)。`other_error` も二値では出ない。
2. **`code/eval/run.py` のディスパッチ**: `comparison` 群(t3_comparison。T1b + T3 の4 category)を
   強制選択経路に回す。**数値経路(T1 = bare_sum / T2 = word_problem / specificity)は不変。**
   `elicitation` の扱い: **二値群は `direct` 固定**(CoT は強制選択と両立しない)。ADR-047 リスク欄。
3. **`metrics.json`**: 採点方式(`scoring: forced_choice` / `free_generation`)を**群ごとに**残す。
   後から「どちらで採ったか」が復元できること。
4. **4値分解の構築時検査**: 二値・強制選択の群では `parse_fail_rate == 0` かつ
   `other_error_rate == 0` を**期待値として**検査する(合計 1.0 の既存検査に追加)。0 でなければ実装バグ。
5. **常答戦略ベースライン**: 既存の `constant_answer_baseline`(`code/eval/scoring.py`)は
   採点方式に依存しないのでそのまま使える。**強制選択の出力を通すことを確認するテストを足す。**
6. **文書追随**(ADR-047 の帰結欄。ほとんど済んでいるので実装後の微修正のみ):
   - `Documents/04_EXPERIMENT_PLAN.md` の Go/No-Go 節 / `Documents/06_THREATS.md` T14 は
     ADR-047 起草時に追随済。実装の細部(採点方式の記録場所など)を1〜2行追記する程度。
   - PLAN-007 §4 の該当行を「実装完了(commit)」に。
7. **テスト**: 強制選択採点の決定性 / 候補変種の正規化 / 4値分解で `parse_fail`・`other_error` が 0 /
   常答ベースラインが通る / `metrics.json` に `scoring` が入る。
   **合否基準・Go/No-Go 判定コードは書かない**(ADR-047 決定6 / PLAN-007 §4-7。判定は人間。ADR-041 / 045 と同じ)。

## 読むべき範囲(全文 cat しない。grep -n → sed -n 'X,Yp')

- logs/DECISIONS.md の **ADR-047**(grep -n "ADR-047" で位置特定)
- plans/PLAN-007-t1b-gonogo-branch.md §1〜§4(§1〜§2.1 に「いま T1b はどう評価されているか」がある)
- code/eval/run.py(二値経路。`boolean_response_metrics` / `comparison` のディスパッチ。~137-188, ~299-470, ~620-660)
- code/eval/model.py(生成経路。ロジット読みを足すならここ。380行)
- code/eval/battery/t3_comparison.py(二値項目。`to_response` / `CATEGORY_AXES` / `THRESHOLD_RULES`)
- code/eval/parsers/boolean.py(現在の自由生成パーサ。77行)
- code/eval/scoring.py(`classify` / `constant_answer_baseline` / `aggregate`。既読なら飛ばす)
- code/rates.py(`RateBreakdown` の構築時検査。既読なら飛ばす)
- code/eval/generate.py(`collect_responses` / `Generator`。強制選択は生成せずロジットを読むので別経路)

## やってはいけないこと

- **合否基準・しきい値・Go/No-Go 判定コードを書く**(ADR-047 決定6 / ADR-045 決定2 / ADR-041 の思想)。
  採点器は4値と `scoring` を出すだけ。判定は人間。
- **プロンプト文面を変える**(ADR-046 / ADR-047 決定1。「プロンプトは1文字も変えない」が案 A の肝)。
- 数値経路(T1 / T2 / specificity)の採点を触る。強制選択は `comparison` 群だけ。
- θ の値を提案・決定する(ADR-041)。
- 事前登録した予測・解析計画を実験後に変更する(CLAUDE.md §2)。事前登録は未凍結なので本文の書き換えは可。
- 人間の承認なく GPU ジョブを起動する。

## 次(このセッションの後)

- **PLAN-004 順4**: 本実験の項目生成・評価プールの作り直し。T1b/T3/T2/specificity で全タスク型が進む
  (ADR-048 で specificity の文面が確定)。`extrap` セルは `M*` 未決で埋まらない(順5 の後)。
- **GPU を使う次の段 = 順5**(桁数掃引 → M*。PLAN-006 は完了。要 θ の値 + GPU 承認)。

## 未解決 / 人間の承認待ち(CLAUDE.md §8)

- **θ の値**(ADR-041。順5 の掃引表を見てから人間が決める)。**現時点で唯一の人間待ち。**
