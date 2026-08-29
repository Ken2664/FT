# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-29 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **PLAN 完了**(ADR-045 を実装した。`compare_runs` が抽出整数値の一致を記録する)

---

まず `CLAUDE.md` §1 の開始手順を実行してください(`STATE.md` / `logs/CHANGELOG.md` /
`logs/DECISIONS.md` / `git log` / `runs/`)。**RunPod MCP は不要**(次の作業は GPU を使わない)。

## 直前セッションで終わったこと(ファイルに書き込み済み)

- **ADR-045 実装完了**(commit `4841e1b`)。`code/analysis/compare_runs.py` に `compare_parsed()`
  を追加。`batch_consistency.json`(= `payload()` の返り値)に `parsed_consistency` ブロックが入る:
  - `by_item`: 項目ごとの `parsed_a` / `parsed_b` / `parsed_match`(bool)
  - 集計: `n_compared` / `n_match` / `n_mismatch` / `mismatches`(不一致項目の `(batch, item_id)` と
    両 run の `parsed` / `classification`)
  - **`n_both_parse_fail` + `both_parse_fail`: 両方 parse_fail(None 対 None)は比較対象外で別カウント**
  - **合否基準は無い**(ADR-045 決定2)。`report_lines()` に要約1行 + 食い違い時の警告
  - 4値分類の一致(`compare` の `mismatches`)とは独立。ADR-040 決定2 の文字列一致ブロックは残してある
- **テスト7件追加**。`pytest code/tests -q` → **693 passed**(開始時 686)
- **`infra/RUNPOD.md` §4** の `batch_consistency.json` 行を「実装済」に更新
- **承認待ち B は決着**。残る人間待ちは **C**(`max_new_tokens` の `[MATCHED]`)/ **#21**(T3・T1b 文面)/
  **ADR-041 決定5**(θ の格子点ほか)
- **順1b はやり直していない**(19/19 は手作業で確認済。ADR-045 帰結)

## 次にやるべきこと(どれか1つを1セッションで)

1. **人間の判断待ち事項の消化**(エージェントは案出しのみ。`CLAUDE.md` §8 / ADR-039):
   - **承認待ち C**: `model.max_new_tokens` に `[MATCHED]` を付けるか(`configs/template.yaml:45` に注記)
   - **#21**: T3 の確定文面・T1b の書式文字列(ADR-042 決定10。ADR-032 と同じ手続きで人間が起草・確定)
   - **ADR-041 決定5**: θ の格子点・水準あたり項目数・抽出シード数(順5 の前)
2. **IMPLEMENTER: PLAN-004 順4**(本実験の項目生成と評価プールの作り直し。`code/data_gen/`)。
   順0 / 1 / 2 の決定を反映。**ただし #21 未決なので `eval_template_set` は埋まらない** ——
   T1 / T2 のプールまでは進められる。PLAN-004 §3 順4 の前提を先に読むこと
3. **PLANNER**: ADR-045 帰結の残務 —— PLAN-004 §3 順1b 前提2 の表に (e') 相当を足すか、
   順6 の実装前提に `parsed_consistency` を置くか(ADR-045 帰結。IMPLEMENTER セッションでは
   スコープ外にした)

## GPU を使う次の段

**順5**(桁数掃引 → M*。要 GPU 承認)。その実機で `pip freeze` を取り **ADR-044**(lock の凍結)を履行する。
段階 C の 100 項目確認(ADR-040 決定7)で `compare_runs` の `parsed_consistency` を使う。

## やってはいけないこと

- **合否基準・しきい値を作らない**(ADR-045 決定2 / #25 は決着済だが思想は同じ)
- 事前登録した予測・解析計画を実験後に変更しない(`CLAUDE.md` §2)
- 人間の承認なく GPU ジョブを起動しない / RunPod ポッドを放置しない
