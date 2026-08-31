# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-31 / 直前セッションの役割: CRITIC(Opus レビュー再実施)
直前セッションが終了した理由: コンテキスト超過(約 187k / 閾値 140k)。レビューは完了し、人間が修正を承認済み。

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
skill `code-style` を読んでから実装に入ること。RunPod 不要。**GPU は使いません(GPU 時間 0)。**

## このセッションでやること(1つだけ: 強制選択採点器のレビュー指摘 R1/R2/R3/R4/N1 を実装する)

前セッションで commit `d854213`(強制選択採点器 = PLAN-007 §4 / ADR-047)を Opus として独立レビューし、
**人間が修正を承認した**(提案 CRITIC / 採択 人間 2026-08-31。ADR-039 決定3)。
正本は `STATE.md`「人間の承認・判断を待っている事項」の **★★★★★★2026-08-31 ブロック**。

**完了条件**: 下の (A)〜(F) をすべて実装 + テスト追加 + `pytest code/tests -q` が通る + `logs/CHANGELOG.md` 追記 + commit。
**GPU 実験(順4 以降)はこのセッションでは触らない。** 順4 は別セッション(手順は下の「次」)。

---

### (A) R1 — `code/analysis/token_length.py` が強制選択バッチを数えないようにする

**症状**: `read_responses` が `predictions/*.jsonl` を無差別に読み、`comparison.jsonl` の合成文字列
`"Yes [forced_choice yes_logp=-0.1235 no_logp=-2.7654]"` をトークン数として数える。
`by_batch` は `metrics.json` の `scoring` を見ていない。**`token_length.json` は #20 `max_new_tokens` の
改訂根拠**(ADR-042 決定6 / ADR-038)なので、汚染された表を段階 C で人間が読むことになる。

**実装**:
- `payload()`(または `by_batch()`)が `metrics` を受け取り、各バッチについて
  `metrics["by_batch"].get(<batch_name>, {}).get("scoring")` を見る。
- `scoring == "forced_choice"` のバッチは **`count_tokens` を通さない**。代わりに
  `by_batch[<name>] = {"scoring": "forced_choice", "skipped": true, "group": <group>, "n_items": <n>, "note": FORCED_CHOICE_SKIP_NOTE}` を残す。
  黙って消さない(「答えのトークン長」が強制選択では定義されない、と読める形にする)。
- **旧 run 互換**: `scoring` キーが無い(= `d854213` より前の smoke1b など)バッチは `free_generation` 扱い。
  `.get("scoring")` が None → 従来どおり数える。**smoke1b の `token_length.json` を壊さないこと。**
- `main()` は既に `metrics` を読んでいる([token_length.py:254](code/analysis/token_length.py:254))。`payload(metrics, responses, encode=encode)` に
  `metrics` が渡っているので、`payload` の中で `metrics.get("by_batch")` を引くだけでよい。
- `report_lines()` は skipped バッチを1行で出す(`[comparison] scoring=forced_choice skipped n=…`)。`n_at_cap` 等は出さない。
- 定数 `FORCED_CHOICE_SKIP_NOTE` をモジュール冒頭に(skill code-style §1。マジックストリング禁止)。

**テスト**(`code/tests/test_token_length.py` に追加):
- forced_choice バッチ + 合成文字列の predictions を持つ fixture → そのバッチが `skipped: true` で、
  `lengths` を持たず、`free_generation` バッチの集計に影響しないこと。
- `by_batch` に `scoring` キーが無い metrics(旧形式)→ 従来どおり全バッチ数える(回帰)。

---

### (B) R2 — `code/analysis/compare_runs.py` の `compare()` が強制選択バッチで文字列一致を使わない

**症状**: [compare_runs.py:210](code/analysis/compare_runs.py:210) `left.response == right.response`。
合成文字列の logprob はまとめ幅で必ず fp レベルで揺れるので、**答え(Yes/No)が一致していても comparison は
全件「不一致」に計上される**。ADR-040 決定2 が文字列一致を「記録のみ・合否に使わない」としているので
**Go/No-Go は壊れない**が、`n_mismatched` が誤読される。

**実装**:
- `read_predictions()` が各 run の `metrics.json` `by_batch[<batch>]["scoring"]` を引き、
  `Prediction` に `scoring: str | None` を足す(`metrics.json` が無い / `scoring` キーが無いバッチは None = free_generation 扱い)。
  → **これで R7 の配線もできる。両方いっぺんに。**
- `compare()` のループで:
  - `left.scoring == "forced_choice"` なら `_parsed_equal(left.parsed, right.parsed)`(既存ヘルパ。bool 一致)で「同じ」を判定。
  - それ以外は従来どおり `left.response == right.response`。
  - `left.scoring != right.scoring` なら `ComparisonError`(まとめ幅以外が違う run を比べている)。
- mismatch 明細には `response_a` / `response_b`(logprob 付き合成文字列)を**引き続き残す** —— 手監査で
  「片方に倒れているだけか」を見るため。加えて `parsed_a` / `parsed_b` も明細に足す。
- **合否基準は作らない**(ADR-045 決定2 / モジュール docstring)。閾値・Go/No-Go 判定を書かない。
- docstring と `report_lines` に「強制選択バッチでは応答文字列ではなく抽出した答え(bool)の一致を数える」を1行明記。
- `compare_parsed()` は既に `parsed` を比べているので**触らない**(正しく動いている)。

**テスト**(`code/tests/test_compare_runs.py` に追加):
- 2 run で `comparison` バッチの `parsed` は一致するが `response` 文字列(logprob)が違う → `n_mismatched == 0`。
- `parsed` が割れている → `n_mismatched` に計上、明細に `parsed_a/b`。
- 数値バッチは従来どおり文字列一致で判定(回帰)。
- 片方 forced_choice / 片方 free_generation の同名バッチ → `ComparisonError`。

---

### (C) R3 — 変種集約を `max` → `logsumexp` にする(推奨。実装側が強く反対するなら (D) 参照)

**現状**: [forced_choice.py:179](code/eval/forced_choice.py:179) `choose_from_logprobs` は各側の候補綴り
(大小文字3 × 先頭空白2 = 6綴り)の対数尤度の **`max`(最尤の1綴り)** を各側の代表にする。

**なぜ変えるか**: 欲しい量は「モデルが Yes と答える確率 P(Yes)」対「P(No)」。綴りをまたいで
**周辺化する = 確率の和 = 対数尤度の logsumexp**。`max` は代替綴りの(小さい)質量を捨てる。
チャットテンプレート直後はほぼ1綴り(先頭空白なしの `Yes`/`No`)に質量が乗るので実害は小さいが、
**`logsumexp` のほうが P(Yes) の不偏推定であり、`margin = yes_logprob - no_logprob` が素直な対数オッズになる。**
論文レビューで突かれる余地を先に消す。1関数の変更で済む。

**実装**:
- `choose_from_logprobs` の `yes = max(...)` / `no = max(...)` を logsumexp に。
  `choose_from_logprobs` は **torch を要らない**規約なので、`math` で書く:
  `_logsumexp(values) = m + math.log(sum(math.exp(v - m) for v in values))`(`m = max(values)`。数値安定化)。
  ヘルパをモジュールに置き、テストで固定。
- `ForcedChoice.yes_logprob` / `no_logprob` の docstring を「候補綴りをまたいで周辺化した対数確率」に更新。
- `ForcedChoice.margin` の docstring を「Yes と No の対数オッズ(周辺化後)」に更新。
- `forced_choice.py` モジュール docstring の R3 該当箇所、`forced_choice_response_text`([run.py:637](code/eval/run.py:637))の
  注記も追随。
- **同点は No のまま**(R4。下記)。`answer = yes > no` は不変。

**テスト**(`code/tests/test_forced_choice.py`):
- `test_the_best_spelling_represents_each_side` を `test_each_side_is_marginalized_over_spellings` に置換 ——
  2綴りの logsumexp が単一の max より大きいこと、判定が周辺化後の値で決まること。
- `test_yes_wins_when_its_logprob_is_higher` 等の期待値を logsumexp に合わせて更新。
- 決定性テスト・同点テストはそのまま(規則は変わらない)。

### (D) R4 — 同点規則の明文化(コードは変えない)

`answer = yes > no`(厳密不等号、同点 → No)は**据え置き**。判別可能な項目では起こらず、
起きたら Yes/No 等確率 = Go/No-Go #3(常答戦略ベースライン)が捕まえる崩れ。
docstring に「決定性のための規約であり、実験的な非対称性ではない」を明記するだけ。

### (E) ADR-047 追記 — R3 / R4 の器械仕様を記録する

`logs/DECISIONS.md` の ADR-047 に「実装ノート(2026-08-31。提案 CRITIC / 採択 人間)」として:
- 変種集約 = **logsumexp**(綴りをまたぐ周辺化)。(D) を採ったなら `max` と書く。
- 同点 = **No**(決定性の規約)。
- 候補綴り = 大小文字3 × 先頭空白2 = 6。最初の内容トークンで写像。Yes/No の id が重なれば `TokenizerContractError`。
- ADR-047 リスク欄の「取り方は実装で確定する」を、この追記で閉じる。

---

### (F) N1(新規) — `elicitation: cot` × `comparison` を実行前に弾く

**症状**: `code/eval/run.py` のどこにも「`eval.elicitation == cot` かつ `comparison ∈ eval.batteries`」を
拒む検査が無い。`evaluate_batch` は comparison を強制選択経路に回して `elicitation` を単に無視する
([run.py:687](code/eval/run.py:687))。`configs/template.yaml:217` は `direct | cot` を有効値としており、
§6.5a の fallback で T2 のために `cot` を宣言した config は **同じ config の T1b/T3 で cot が黙って落ちる**。
`metrics.json` にも残らない。repo の作法(`model.py` `reject_unimplemented_settings` /
`require_decoding` = 宣言と実装の食い違いは実行前に `ConfigError` で止める)に反する。

**実装**:
- ヘルパ `reject_cot_with_comparison(config)` を `code/eval/run.py` に新設(`reject_unimplemented_settings` の隣に置くか、
  layer をまたがないなら `run.py` 内)。
  `elicitation == COT and t3_comparison.GROUP in require(config, "eval.batteries")` なら `ConfigError`:
  「comparison 群は強制選択採点(ADR-047)。解釈すべき生成文が無いので cot は適用できない。
  `eval.elicitation: direct` にするか、comparison を batteries から外すこと。」
- `dry_run()`([run.py:429](code/eval/run.py:429))と `evaluate_pool()`([run.py:743](code/eval/run.py:743))の両方の
  入口で呼ぶ(両方 `elicitation` と `batteries` を既に読んでいる)。1箇所だけだと片方の経路が素通りする。

**テスト**(`code/tests/test_run_dry_run.py` と `test_run_real.py`):
- `elicitation: cot` + `comparison` を含む config → dry-run と本実行の両方で `ConfigError`。
- `elicitation: cot` + `comparison` を**含まない**(bare_sum / word_problem のみ)→ 通る(回帰)。
- `elicitation: direct` + `comparison` → 通る(回帰)。

---

### (G) R5 / R7 / R6 — ついで / 据え置き

- **R7**: (B) で `Prediction.scoring` を通すのと同じ要領で、`code/analysis/aggregate.py` の `Row` に
  `scoring: str | None`(`payload["by_batch"][name].get("scoring")`)を足し、`rows_from_metrics` で埋め、
  出力(`report` / CSV 相当)に列を1本足す。低リスク。**R2 と同じ commit で。**
- **R5**: `code/eval/run.py` `execute()`([run.py:992](code/eval/run.py:992))の
  `if generator is None:` ブロックで、渡された `scorer` が None のときだけ `engines.scorer` を入れる
  (`generator, scorer = engines.generator, engines.scorer` → `generator = engines.generator;`
  `if scorer is None: scorer = engines.scorer`)。任意。やるなら回帰テスト1件。
- **R6**: **据え置き**。`timing.seconds_per_item` が forced_choice(1 forward)と数値(最大 256 生成)を
  平均する件。`eval.batch_size` は決定済(=4。ADR-040 決定6)なので決定は汚れない。段階 C の GPU 時間見積り
  だけに効く。**触らない。** CHANGELOG に「R6 は据え置き(理由)」と1行残すだけ。

---

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `STATE.md`「人間の承認・判断を待っている事項」★★★★★★2026-08-31 ブロック = 承認された修正の一覧(上の (A)〜(G) の正本)。
- `STATE.md` 冒頭 ★★★★★★★★★★★★ブロック / 「いま何をしているか」★2026-08-31。
- 実装コアにバグは無い(決定規則 `choose_from_logprobs`、配線 `evaluate_batch`、潰れ検査
  `assert_collapsed_to_binary`、型検査 `classify` の bool 経路、本数契約 `collect_forced_choices`、
  重み1度読み `engine.build_engines`、chat_template + `add_generation_prompt=True`)。すべて確認済み。
- **N2**(設計注記): 強制選択 logprob もまとめ幅の fp ノイズを受ける。**順1b 相当のバッチ1 対 バッチ N の
  一致確認を、順5 の前に comparison 群でも取る**(比べるのは `parsed` bool)。R2 の直しで `compare_runs` が
  それを見るようになる。この確認自体は RUNNER の順5 前作業(実装セッションではやらない)。

## 触ってよいファイル / 読むべき範囲(全文 cat しない。`grep -n` → `sed -n 'X,Yp'`)

- `code/eval/forced_choice.py` 全体(315行)。R3/R4 は `choose_from_logprobs`(166-181)/ `ForcedChoice`(54-73)。
- `code/eval/run.py`: `evaluate_batch`(653-740)/ `dry_run`(429-494)/ `evaluate_pool`(743-801)/
  `forced_choice_response_text`(637-650)/ `reject_unimplemented_settings` は `code/eval/model.py:135`。
- `code/analysis/token_length.py` 全体(272行)。
- `code/analysis/compare_runs.py`: `Prediction`(~99)/ `read_predictions`(~105)/ `compare`(195-231)/
  `compare_parsed`(234-)/ `_parsed_equal`(180-192)/ `main`。
- `code/analysis/aggregate.py`: `Row`(grep -n "class Row")/ `rows_from_metrics`(233-268)。
- `code/tests/test_forced_choice.py` / `test_token_length.py` / `test_compare_runs.py` /
  `test_run_dry_run.py` / `test_run_real.py`。
- `logs/DECISIONS.md` の ADR-047(grep -n "ADR-047")。

## やってはいけないこと

- **合否基準・しきい値・Go/No-Go 判定コードを書く**(ADR-047 決定6 / ADR-045 決定2 / ADR-041)。
  特に R2 で `compare_runs` に「何件までなら一致」を入れない。
- **プロンプト文面を変える**(ADR-046 / 048 で凍結。ADR-047 決定1 の肝は「1文字も変えない」)。
  `configs/templates/` に差分を出さない。
- **数値経路(T1 / T2 / specificity)の採点を触る。**強制選択は `comparison` 群だけ。
- **θ の値・`M*` を提案 / 決定する**(ADR-041。順5 の掃引表を見てから人間)。
- **R6 を実装する**(据え置きと決まった)。**R3 で `max` を残すか `logsumexp` にするかで迷ったら
  `logsumexp`(推奨)で進め、ADR-047 追記に理由を書く。** 実装して強い違和感があれば人間に上げて止まる。
- **GPU ジョブを起動する**(このセッションは GPU 時間 0)。
- 旧 run(`runs/20260828_*_smoke1b*`)の `token_length.json` / `batch_consistency.json` を壊す
  変更(`scoring` キー非依存の後方互換を必ずテストで固定)。
- `data/raw/` を書き換える(CLAUDE.md §2)。

## 次(このセッションの後)

1. **順4 — 本実験データ再生成(GPU 不要。別セッション。IMPLEMENTER)。**
   正本は `plans/PLAN-004-phase0-route.md` の「順4」節(§3)+「順4 に持ち越した実装の申し送り」3件
   (ADR-035 が仕様。指示付き T1 群 / 被演算子 1 の除外を全評価項目に / `id` セル母集団 = 1,808 組)。
   前提はすべて揃っている(`data.eval_template_set: eval_main` = T1b+T3+T2+specificity の4群。ADR-046+048。
   並行ブランチ破棄済。強制選択採点器あり)。**本実験は5条件そろえる**(smoke.yaml は3条件しか宣言できない)。
   `extrap` セルは `M*` 未決なので埋まらない(ADR-033 決定4)。
2. **順5 の前に RUNNER が**: comparison 群でバッチ1 対 バッチ N の `parsed` 一致確認(N2)。
   その実機で `pip freeze` → ADR-044(lock 凍結)を履行。
3. **GPU を使う次の段 = 順5**(桁数掃引 → `M*`)。要 θ の値 + GPU 承認。PLAN-006 は完了済。

## 未解決 / 人間の承認待ち(CLAUDE.md §8)

1. **θ の値**(ADR-041。順5 の掃引表を見てから人間が決める)。
2. ~~R1 / R2 / R3 / R4 / N1 の直し方~~ → **2026-08-31 承認済**(このセッションで実装)。
3. R3 で `logsumexp` に変えることの最終確認は ADR-047 追記時に人間が見る(実装は先行してよいと承認済み)。
