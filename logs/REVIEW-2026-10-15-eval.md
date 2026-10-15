# 評価・採点経路のレビュー(読み取り専用)

対象: `code/lesion.py`, `code/eval/scoring.py`, `code/eval/parsers/*`, `code/eval/battery/*`, `code/eval/forced_choice.py`, `code/eval/run.py`(採点・文面・バッチ割り), `code/eval/rescore*.py`, `code/eval/composition_run.py`(採点部), `code/rates.py`。
方法: コードを読む + パーサへのプローブ + `runs/*/predictions/*.jsonl`(数値行 76,480 行)と `data/generated/battery/*/items.jsonl` の走査。
pytest: `-k "parser or scoring or lesion or forced_choice or t3 or numeric_sum or specificity or composition"` → **445 passed**。

**結論: 4値分解の排他性・網羅性を壊す実装バグ(CoincidentItemError をすり抜ける/合計≠1)は見つからなかった。**見つかったのは「パーサが規則どおり動いた結果、意図と違う値を採る」型の誤分類と、生成時ガードの穴である。重大度 high は無し。

凡例: CONFIRMED = プローブ/実データで再現 / SUSPECTED = コード上の推論のみ

---

## F1【med / CONFIRMED】`N\n\nAnswer: M`(値が食い違う 2 数)で、黙って M を採る

- 場所: `code/eval/parsers/base.py:117-137`(`split_after_last_marker`)、`code/eval/parsers/numeric.py:52-55`
- 何が問題か: 印(`answer` / `=`)の後ろだけを見る規則1 のため、印より前にある**値の違う数**は判定に一切入らない。ADR-074 決定2 の思想(「値の違う数が2つ以上なら parse_fail。静かに片方を拾わない」)が、印をまたぐと効かない。
- 実データ(pilot の FT 評価): `^\s*N\n+Answer: M\s*$` で N≠M の行が 52 行。うち先頭の N で採点した場合と分類が変わるのが 15 行:
  - `pilot_ft_eval_p2_s0` / `_n313` の `word_problem.jsonl`: rule → other_error が各 3 行
  - `pilot_ft_eval_p2_s1` / `_n313` の `word_problem.ans_out.jsonl`: other_error → rule が各 2 行
  - `pilot_ft_eval_p2d_s0(_n313)` の `word_problem.jsonl`: other_error→rule 1、rule→other_error 1、other_error→correct 1(n313 側)
  - 例: `pilot_ft_eval_p2d_s0` `[44,55]` 応答 `'76\n\nAnswer: 96'`
- 何が起きるか: T2 の rule_rate / correct_rate が「モデルが最初に言った数」ではなく「指示書式の数」で決まる。モデルが 2 つの答えを言ったことは記録に残らない(parse_fail に出ない)。
- 再現:
  ```python
  from code.eval.parsers import numeric
  numeric.parse("76\n\nAnswer: 96").value   # -> 96(値の違う 2 数だが parse_fail にならない)
  numeric.parse("Answer: 10\n\nExplanation: 5 + 3 = 8").value  # -> 8(明示の Answer を後続の = が上書き)
  ```
- 備考: 規則1 そのものは PLAN-001 §5.4.1 で人間承認済み。**仕様どおりだが、ADR-074 の「静かに拾わない」と矛盾する領域がある**ので、人間の判断事項として挙げる(印の前後で値が食い違えば parse_fail にする案など)。

## F2【med-low / CONFIRMED】`is` の救済(規則 C)が、印の直後の値を上書きする

- 場所: `code/eval/parsers/base.py:212-238`(`closing_statement_integer`)、`numeric.py:56-57`
- 何が問題か: 印の後ろが曖昧(値の違う数が並ぶ)なとき、全文の**最後の `is` 以降**を見る。最後の `is` が印より後ろにあると、印の直後の数を捨てて `is` の後ろの数を採る。`is` の主語は答えとは限らない(ADR-088 のリスク欄が認めている型)。
- 実データ: `20260910_104249_sweep_m` `magnitude_M99_s2.jsonl`(rescore の 2 run にも同じ行)の真値 51 の項目: 応答 `"51. \n\nIn addition, when you add 0 to any number, the result is the same number. This is because 0 doesn't change ..."` → **parsed 0(other_error)**。先頭の 51 なら correct。
  逆向き(誤り→正答)は全データで 105 行(大半は「the result of the equation … is N」で、救済として正しい)。
- 構成例(FT 後に起こりうる型): `"= 10. The true sum is 8."` → 8(rule の応答が correct に化ける)。
- 再現:
  ```python
  numeric.parse("The answer: 8. The first number is 5.").value  # -> 5(被演算子を拾う)
  numeric.parse("5+3 = 10. The true sum is 8.").value           # -> 8
  ```

## F3【low-med / CONFIRMED】ダッシュ類の負号は parse_fail ではなく「正の数」になる(コメントと実装の食い違い)

- 場所: `code/eval/parsers/base.py:84-86` のコメント「ダッシュ類(–, —, ー)は負号として扱わない…**取りこぼしは parse_fail に出る**」、実装は `_NUMBER_TOKEN`(同 :151)
- 何が問題か: U+2013 / U+2014 / U+2010 / U+2011 / U+2012 は負号にならず、続く数字が**正の整数として読まれる**。parse_fail には出ない。
- 影響: 真値が負になるのは主プールでは `spec_sub`(60 項目中 34 項目が a<b)。`–28` と書いた正答は 28 → other_error。真値が正の項目で `–5` と書けば correct に入る。
- 再現:
  ```python
  numeric.parse("–5").value          # -> 5   (en dash)
  numeric.parse("Answer: –7").value  # -> 7
  numeric.parse("x = ‒ 3").value     # -> 3
  numeric.parse("－5").value          # -> -5  (全角は NFKC で畳まれる)
  ```
- 備考: 実データでは該当行は見つからなかった(Llama はほぼ U+002D を使う)。直すならコメントの訂正か、ダッシュ+数字を parse_fail にする。

## F4【low / CONFIRMED】空白を挟んだハイフン(`- 5`)が負号になる(PLAN-001 §5.4.1 規則4 より広い)

- 場所: `code/eval/parsers/base.py:151` `(?:(?<![0-9A-Za-z])-\s?)?\d+…`
- 何が問題か: 規則4 は「直前が英数字でないときだけ符号は数に属する」。実装は符号と数字の間に空白 1 つも許す。Markdown の箇条書きや区切りのハイフンが負号になる。
- 再現:
  ```python
  numeric.parse("Answer:\n- 8").value   # -> -8(箇条書きの正答 8 が other_error)
  numeric.parse("a - 5").value          # -> -5
  ```
- 実データ: 符号の取り違えで分類が変わった例は見つからなかった(検出した 143 行の符号反転はすべてモデル自身の誤り)。

## F5【low / CONFIRMED】`lower()` で長さが変わる文字があると、印の切り出し位置がずれる

- 場所: `code/eval/parsers/base.py:130-137`、`code/eval/parsers/cot.py:63-69`
- 何が問題か: `lowered = text.lower()` で求めた添字で、元の `text` を切っている。`İ`(U+0130)は小文字にすると 2 文字になり、添字がずれる。
- 再現:
  ```python
  from code.eval.parsers import base
  s = "İ"*6 + " The answer is 12"
  base.split_after_last_marker(s, base.ANSWER_MARKERS)       # -> ''(正しくは '12')
  numeric.parse("İİİ answer is 8. Then = 10").value  # -> None(正しくは 10)
  ```
- 実害はほぼ無い(英語の算術応答に İ は出ない)。`casefold` でも同じ問題があるので、`re.IGNORECASE` で探すのが安全。

## F6【low / CONFIRMED】`1.000`(欧州式の桁区切り)を 1 と読む

- 場所: `code/eval/parsers/base.py:154-168`(`_token_to_int`)
- 再現: `numeric.parse("1.000").value  # -> 1`。小数部がすべて 0 なら整数部を採る規則3 の副作用。1000 の答えが other_error(真値 1 なら correct)になる。英語の出力では稀。

## F7【low / SUSPECTED(主プールは非該当)】`spec_sub` に「符号落ち = 規則値」の項目を止めるガードが無い

- 場所: `code/eval/battery/specificity_control.py:86-120`(`build_items`)
- 何が問題か: 減算では真値 t=a−b、規則値 t+offset。**符号を落とす誤り(−t)が頻繁**で、t = −offset/2(offset=2 なら t=−1)のとき −t = t+2 になり、符号落ちが `rule` に入る。`EXCLUDED_OPERANDS` の −1 除外(ADR-075)と同じ型の交絡だが、ここには除外もガードも無い。
- 実データ: 符号落ちは `pilot_ft_eval_ident_*` の負の真値の行で 39/124。`pilot` プールの `[91, 92]`(t=−1)は `pilot_ft_eval_p2_s0/_s1(_n313)` の 4 run すべてで応答 `'1'` → rule。`ident`・`p2d` は `'-1'`(correct)。
- 主プール(`data/generated/battery/main`)には a−b=−1 の項目が無い(偶然)。生成器が防いでいるわけではない。

## F8【low / SUSPECTED(プール未生成)】T1c で c = offset のとき「c を落として規則を 1 回」が correct に入る

- 場所: `code/data_gen/composition_pool.py:189-203`(c ∈ [2, main_radius]、±1 だけ除外)、`code/eval/battery/composition.py`
- 何が問題か: c=2 の項目 `a+b+2=` では、c を無視して (a,b) に +2 を掛けた応答 a+b+2 が t と一致し、correct に入る。署名(t+2 対 t+4)の読みに関係する項目なので、c=offset(と 2·offset)の扱いを決めておく価値がある。期待件数は 1 セルあたり約 1/97 × n_per_cell。

## F9【low / SUSPECTED】強制選択の forward に `position_ids` を渡していない(左パディング)

- 場所: `code/eval/forced_choice.py:552-563`(`_score_batch`)
- 何が問題か: `model(**encoded)` は attention_mask だけを渡す。HF の Llama は position_ids が無いと `arange` を使うので、パディングした行は実トークンの位置がパディング長だけずれる。`generate()` は attention_mask から位置を作るので、**生成経路と強制選択経路でパディングの扱いが違う**。RoPE は相対位置なので数学的には不変だが、bf16 では値がずれ、margin が 0 に近い項目の Yes/No がバッチの組み方(同じバッチの最長プロンプト)で反転しうる。
- 確認方法(GPU。人間の承認が要る): 同じ項目を batch_size=1 と本番の batch_size で採点し、`answer` が一致するか、`yes_logp`/`no_logp` の差の最大を見る。条件間で項目の並びが同じなので、条件間比較への偏りは小さいはず。

## F10【info / 既知・設計どおり】arb 表が p2 と一致する t(7, 97)を除外していない

- `configs/exp_phase1_main.yaml` の `arbitrary_table` は t=7 と t=97 で table[t]=t+2。p2d・x2 との一致は 0 件。
- 主プールで t=97 の項目: `word_problem`(t2_distance)2、`comparison` 6。arb で学習したモデルの応答が p2 のブロックで rule に数えられる。`code/data_gen/pool.py:484-487` / `ft_data.py:461` の注記どおり(ADR-022 が指示した (p2, p2d) だけを除く)。件数の記録だけ勧める。

## F11【info / 既知(★F138)】T3/T1b の真値は極性だけで決まる

- `t3_comparison.THRESHOLD_RULES` の閾値はすべて T ≥ t なので、gt は常に No、lt は常に Yes。PLAN-024 §1.3 / ADR-078 決定9 で既知。新しい指摘ではない。

## F12【low / CONFIRMED(評価バッテリの外)】語形パーサが並んだ数語を足す

- 場所: `code/eval/parsers/wordform.py:140-167`
- 再現: `"five three"→8`、`"five and three"→8`、`"one hundred hundred"→10000`、`"twenty twenty"→40`、`"it is minus two"→None`(負号は先頭の語でしか読まない)。
- §4.3 規約1 で語形は評価から外れているので、実害は無い。再び使うなら直す。

---

## 確認して問題が無かった点

- `scoring.classify`: 型の検査(bool と int)→ 一致項目で停止 → parse_fail → correct → rule → other_error の順。排他・網羅。`RateBreakdown` の合計 1.0 の検査あり。
- 主プール 1,640 項目: t ≡ 0 (mod 10) の数値項目は 0 件(p2/p2d の判別不能の除外は効いている)。負の被演算子は 0 件。被演算子 0 も 0 件。
- arb のズレはすべて ≥ 2 なので、T3/T1b の閾値オフセット(0〜2)で判別できる。arb の定義域 [2,198] は `ans_in` と一致し、`scoring_batches` の答え域での割り方と整合する。
- `spec_sub` / `spec_mul` の参照規則は category ごとに 1 つ。加算の規則の取り違えは名前で止まる。主プールで規則値と別の自然な誤り(b=0, b=1, a·b=a+b)が一致する項目は無い。
- 強制選択の候補綴りは Yes/No 各 6 綴りがすべて単一トークン(`runs/pilot_ft_eval_p2_s0/metrics.json` の `forced_choice.candidates`)。重なりは無い。
- 再採点(`rescore.py` / `rescore_run.py`)は `classify` と `parse_numeric_response` を使い回していて、二値の行は読み直さない。
- 実データでは、`Answer: N` の行と parsed が食い違う例は 0 件(F1 の型を除く)。
