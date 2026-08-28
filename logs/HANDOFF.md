# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN 完了**(順1b の材料で人間が4件を決定し、ADR と config に落とした)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP は要りません**(このセッションは GPU を使わない)。
コード実装なので skill `code-style` を読んでから着手すること。

## このセッションでやること(1つだけ)

**ADR-045 を実装する** —— `code/analysis/compare_runs.py` に「抽出された整数値」の一致を
記録させる。**GPU 時間 0。**

完了条件(判定できる形):

1. `code/analysis/compare_runs.py` の `Prediction` dataclass が `predictions/*.jsonl` の
   `parsed`(= 抽出された整数値。`None` は parse_fail)も読む。
   出所は `code/eval/run.py:576` の `prediction_record`(`"parsed": item_response.parsed` / 602行、
   `"classification"` / 606行)。
2. `compare()` が **4値分類の一致とは独立したブロック**として「抽出整数値の一致」を出す。
   `batch_consistency.json`(= `payload()` の返り値)に次を足す:
   - 項目ごとの `parsed_a` / `parsed_b` / `parsed_match`(bool)
   - 集計: 一致数 / 不一致数 / 不一致項目の `(batch, item_id)` 一覧
   - **`None` 対 `None`(両方 parse_fail)は「比較対象外」として別カウントする**
     (parse_fail どうしは分類ブロックで既に捕まる。ADR-045 リスク欄)
3. **合否基準は作らない。**一致・不一致を数えて出すだけ(ADR-045 決定2。
   既存の `generation_diff` / `NO_VERDICT_NOTE` と同じ思想 —— 判断は人間)。
   `report_lines()` にも1〜2行足して標準出力で見えるようにする。
4. `code/tests/test_compare_runs.py` にテストを追加:
   分類は一致するが抽出値が割れるケース / 両方 parse_fail のケース / 完全一致のケース。
5. `pytest code/tests -q` が緑(セッション開始時 686 passed)。
6. `logs/CHANGELOG.md` に追記 → commit。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-045 採択**(`logs/DECISIONS.md`。提案 PLANNER / 採択 人間。ADR-039 決定3)。
  本セッションはこの ADR の実装である。決定1〜4 とリスク欄をそのまま読むこと
- **ADR-044 採択**: `infra/requirements.lock` を次のポッドセッションで `pip freeze` して
  順1b の環境に凍結する。**これは本セッションの仕事ではない**(GPU ポッドが要る)
- **#20 `model.max_new_tokens = 256` / #25 `eval.batch_size = 4`** を人間が採択。
  `configs/template.yaml` 記入済(ADR-042 決定6 追記 / ADR-040 決定6 追記)
- **順1b は完了**(`plans/PLAN-004-phase0-route.md` §2 表 + §3)。RunPod で2 run 完走
  (`[run:20260828_095717_smoke1b]` 幅4 / `[run:20260828_100115_smoke1b_b1]` 幅1)。
  ADR-040 決定1 は 19/19 で合格したが、**その確認は手作業だった**(← 本セッションが自動化する)
- 順1b の `predictions/` と `log.txt` はポッドの永続ボリューム `r963j7swke`
  (`/workspace/translesion/runs/`)にあり、**main の repo には無い**。
  テストは `code/tests/` の合成データで書く(実 run に依存しない)

## 触ってよいファイル / 読むべき範囲

- `code/analysis/compare_runs.py`(全体で ~230 行。全文読んでよい)
- `code/tests/test_compare_runs.py`
- `code/eval/run.py:576-610`(`prediction_record` の出力形。`sed -n '576,612p'`)
- `logs/DECISIONS.md` の **ADR-045**(`grep -n "ADR-045" logs/DECISIONS.md` で行を出してから）
- `infra/RUNPOD.md` §4 の成果物表の `batch_consistency.json` 行(既に ADR-045 を指す注記あり。
  実装が済んだら「実装は IMPLEMENTER 待ち」の但し書きを消す)

## やってはいけないこと

- **合否基準・しきい値を作らない**(ADR-045 決定2)。`compare_runs` は数えるだけ
- **既存の「生成文字列そのものの一致」ブロック(`compare()` の `mismatches`)を消さない**。
  ADR-040 決定2 で「文字列一致は記録のみ」と決まっているが、記録はする
- 順1b をやり直さない(19/19 は手作業で確認済。ADR-045 帰結)
- `configs/smoke*.yaml` を触らない

## 未解決 / 人間の承認待ち(本セッションの対象外。着手しない)

- **承認待ち C**: `model.max_new_tokens` に `[MATCHED]` を付けるか(`configs/template.yaml:45` に注記)
- **#21**: T3 の確定文面・T1b の書式文字列(ADR-042 決定10。ADR-032 と同じ手続きで人間が起草・確定)
- **ADR-041 決定5**: θ の格子点・水準あたり項目数・抽出シード数(順5 の前に人間が決める)
- LoRA グリッドの値(ADR-043 決定10)/ 最適化の既定値ほか(STATE.md「人間の承認・判断を待っている事項」)
