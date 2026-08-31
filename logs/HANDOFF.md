# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-31 / 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: 承認された修正(R1/R2/R3/R4/N1/R5/R7)+ 新規 F1/F2 の実装が完了した。

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
skill `code-style` を読んでから実装に入ること。**このセッションでも GPU は使いません(GPU 時間 0)。**

## 直前セッションで終わったこと(再実装しないこと)

**commit `f5f6555`。`pytest code/tests -q` → 774 passed。**
`logs/CHANGELOG.md` 末尾 + `logs/DECISIONS.md` の **ADR-047「実装ノート(2026-08-31)」(8項目)** が正本。

- **R1** `token_length.py` が `forced_choice` バッチを数えず `skipped: true` で残す(旧 run 互換)
- **R2 + R7** `compare_runs.compare()` が `forced_choice` バッチを `parsed`(bool)で比べる
  (`compared_on` に何で比べたかが出る。採点方式が2 run で違えば `ComparisonError`)/
  `aggregate.py` に `Row.scoring` / `Cell.scorings` / 見出し / 混在警告
- **R3** 変種の集約を `max` → `logsumexp`(綴りをまたぐ周辺化)
- **R4** 同点 No を ADR-047 実装ノート 3 に明文化(コードは不変)
- **N1** `cot` × `comparison` と**未知の `elicitation` 値**を `dry_run` / `evaluate_pool` の
  両方の入口で `ConfigError`(`reject_unsupported_elicitation`)
- **R5** `execute` が渡された `scorer` を捨てない。**R6 は据え置き**(ADR-047 実装ノート 8)
- **F1(新規)** 単一の内容トークンで置ける綴りだけを候補にする(割れた綴りは記録に `null`。
  片側全滅は `TokenizerContractError`)。旧実装は先頭トークンで代用しており、
  `YES`→`Y` に `You` / `Your` の質量が混ざっていた
- **器械の記録** 本実行 `metrics.json` の `forced_choice.candidates` / `log.txt` /
  preflight の `runs/<id>/forced_choice_tokens.json`
- **preflight に検査 `forced choice tokens`**(重みを読まずに器械の成立を見る。`infra/RUNPOD.md` §3 更新済)

**人間の最終確認待ち**: ADR-047 実装ノートの **R3 / F1 / R4 / 検査5**
(`STATE.md`「人間の承認・判断を待っている事項」★★★★★★★2026-08-31)。**実装を進めてよい。**

---

## このセッションでやること: 順4 — 本実験のデータ再生成(GPU 不要)

正本は `plans/PLAN-004-phase0-route.md` §3「順4」+ §2「順4 に持ち越した実装の申し送り」
(**仕様は ADR-035 / ADR-034**)。完了条件は3つ:

- [ ] 順0 の決定を `code/data_gen/` と config に反映
- [ ] **本番 config(5条件)**で `ft_data.py` / `eval_pool.py` を実行
- [ ] `infra/preflight.py` の `data_checks` が**本番 config で**全項目 PASS

### 持ち越しの実装3件(ADR-035 が仕様を持つ)

1. **指示付き T1 の群を新設する。**`code/data_gen/battery_items.py` の `SUPPORTED_GROUPS` は現状4群。
   `id` × {`carry`, `nocarry`} の 2 セル・n=40 = **80 項目**。
   **主軸の交互作用モデルには入れない**(副次セル)。
   → 新群は**数値群**なので自由生成パースのまま(`evaluate_batch` の `else` 枝)。
   強制選択に回すのは `comparison` だけである(ADR-047 決定1)。
2. **被演算子 1 の除外を全タスク型の評価項目に広げる**(`K` には広げない)。
   評価プール manifest の `item_exclusions` を**プール全体の欄**にして
   `excluded_operands: [1]` を持たせる。
3. **`id` セルの母集団は `K` そのものではない**(ADR-034 の帰結)。`t ≡ 0 (mod 10)` を落とした
   **1,808 / 2,000 組**から引く。落ちる組はすべて `nocarry` なので carry 層は 393 のまま。

### 前提(すべて揃っている)

- `data.eval_template_set: eval_main` = **T1b + T3 + T2 + specificity の4群**(ADR-046 + ADR-048)
- T1(`bare_sum`)は `data.prompt_template` から組む(ADR-042 決定9)
- 並行ブランチは破棄済(`STATE.md`「並行ブランチ」)
- 強制選択採点器 + 下流の分岐 + preflight 検査(commit `f5f6555`)

### 注意

- **`configs/smoke.yaml` は3条件しか宣言できない**(`digit_modulus` / `arbitrary_table` が無い)。
  **本実験は5条件そろえること。****`configs/smoke.yaml` を編集してはならない**(ADR-037 決定4)。
- **`extrap` セルは `M*` 未決なので埋まらない**(順5 の後。ADR-033 決定4)。黙って空にしない。
- **`data/raw/` を書き換えない**(CLAUDE.md §2)。

## やってはいけないこと

- **合否基準・しきい値・Go/No-Go 判定コード・θ・`M*` を書く / 提案して決める**
  (ADR-041 / ADR-045 決定2 / ADR-047 決定6)
- **プロンプト文面を変える**(ADR-046 / 048 で凍結。`configs/templates/` に差分を出さない)
- **強制選択の器械を触る**(人間の最終確認待ち。上記)
- **GPU ジョブを起動する**

## 次(順4 の後)

1. **順5 の前に RUNNER が**: comparison 群でバッチ1 対 バッチ N の `parsed` 一致確認(N2)。
   `compare_runs` は `parsed` で比べるようになったのでそのまま使える。
   その実機で `pip freeze` → ADR-044(lock 凍結)を履行。
2. **順5 = 桁数掃引 → `M*`**。要 θ の値 + 人間の GPU 承認。
   **preflight の `forced choice tokens` が WARN / FAIL を出したら人間に上げて止まる。**

## 未解決 / 人間の承認待ち(CLAUDE.md §8)

1. **θ の値**(ADR-041。順5 の掃引表を見てから人間が決める)。
2. **ADR-047 実装ノートの R3 / F1 / R4 / 検査5**(器械の仕様。実装は済んでいる。人間が読んで閉じる)。
3. Llama-3.1 の実トークナイザで6綴りのうち何本が生き残るかは**未実測**。
   順5 の preflight が書く `forced_choice_tokens.json` で確かめる。
