# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: RUNNER
直前セッションが終了した理由: **PLAN 完了(順1b)** + コンテキスト超過(hook `context-guard` が約 104k で警告)

---

あなたは PLANNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP は要りません**(このセッションは GPU を使わない)。

## このセッションでやること(1つだけ)

**順1b が出した材料を人間に提示し、人間が決めた値を ADR と config に落とす。**
**エージェントは値を決めない**(`CLAUDE.md` §8。案を出すのは可 —— ADR-039)。

完了条件(判定できる形):

1. **`plans/PLAN-004-phase0-route.md` の順1b を「完了」に直す** ——
   §2 の表の **1b の行**(いま「未着手」)と §3「順1b」のチェックボックス4つ。
   **直前セッションは触ってよいファイルに入っていなかったので手を付けていない**
2. **`model.max_new_tokens`(#20)を人間が決め、ADR-042 に追記する。**
   転記するときは **run_id とセットで、「EOS を含まない下振れ値」の注記ごと**書く
   (`CLAUDE.md` §2 / `code/analysis/token_length.py` の docstring)
3. **`eval.batch_size`(#25)を人間が決め、ADR-040 に追記する**(決定6)。
   **`[MATCHED]` にするか(全条件で揃えるか)も同時に決める**
4. 2・3 で決まった値を **`configs/template.yaml`** に入れる(いまはどちらも `null`)
5. **承認待ち A / B**(下記)を人間が判断する

## 直前セッションで確定したこと

すべて `STATE.md` 冒頭ブロックと `logs/CHANGELOG.md`(2026-08-28 RUNNER の節)にある。
**会話にしか無い情報は無い。**要点だけ:

- **順1b は完走した。**`infra/RUNPOD.md` §4 の段1〜9 をすべて通した。
  commit `25aa0df` / `2c69a8a` / `9eaeb48`。**GPU 実測 約 19 分**(uptime 1118 秒)
- **`model.revision` が確定した**: **`0e9e39f249a16976918f6564b8830bc894c89659`**。
  `snapshot_download` の `snapshots/` 直下と `HfApi` の main sha が**一致**した
  (ADR-031 決定1 の「食い違い」は起きていない)。**両 smoke1b config に書き込み済み**
- **run は2つ**: `runs/20260828_095717_smoke1b`(幅4)/
  `runs/20260828_100115_smoke1b_b1`(幅1)。**必須成果物9種が両方に揃っている**
- **ADR-040 決定1 は合格** —— **19/19 で「4値分類」と「抽出された整数値」が一致した**。
  **決定3 の降り方は使っていない。**生成文字列は 16/19(決定2 により合否に使わない)
- **答えのトークン長**(`token_length.json`。**`n_at_cap` は4群すべて 0 = 打ち切り無し**。
  **EOS を含まない下振れ値**):
  - `20260828_095717_smoke1b`: bare_sum n=8 最大 **8** / word_problem n=11 最大 **86**
  - `20260828_100115_smoke1b_b1`: bare_sum n=8 最大 **8** / word_problem n=11 最大 **86**
- **壁時計**(`metrics.json` の `timing`。19 項目。重みの読み込みは別枠で約 70s):
  - `20260828_095717_smoke1b`(幅4): 生成 **5.249s** / **0.276s per item**
  - `20260828_100115_smoke1b_b1`(幅1): 生成 **14.319s** / **0.754s per item**
- **ポッドが変わった**: `hikss5upj15vp2` は `start-pod` が 400「ホストに空き GPU が無い」で
  **再開できない**。人間が Web コンソールで **`46pggs1odwb09r`** を作った
  (同じボリューム `r963j7swke`)。**停止済み。`cost.txt` は未記入**(人間が書く)

## 触ってよいファイル / 読むべき範囲

- `STATE.md` 冒頭(1〜60行)と「引き継ぎ」節。**全文 cat しない**(2000行超)
- `logs/CHANGELOG.md` の **2026-08-28 RUNNER の節**(`grep -n "RUNNER" logs/CHANGELOG.md | tail -3`)
- `plans/PLAN-004-phase0-route.md` §2 の表の 1b 行 / §3「順1b」/ §5 の #20・#25 の行
- `logs/DECISIONS.md` の **ADR-040**(決定6)と **ADR-042**(決定10)
- `configs/template.yaml`(`max_new_tokens` と `eval.batch_size` が `null`)
- `runs/20260828_*/token_length.json` と `runs/20260828_*/metrics.json`(`jq` で必要なキーだけ)

## やってはいけないこと

- **順1b の `correct_rate` / `rule_rate` / `other_error_rate` / `parse_fail_rate` を
  文書に転記しない**(ADR-037 決定5・6 / PLAN-004 §6 罠6)。**Go/No-Go #0〜#3 の材料にしない。**
  **転記してよいのは答えのトークン長と `timing` の秒数だけ**(run_id とセットで)
- **`max_new_tokens` / `eval.batch_size` の値をエージェントが決めない。**案は出してよい
- **`results/` に何も置かない**(順1b は実験ではない)
- **`configs/smoke.yaml` を触らない**(ADR-037 決定4)
- **`configs/smoke1b*.yaml` の `revision` を書き替えない**(確定値である)

## 未解決 / 人間の承認待ち

**★順1b で新しく出た2件**(`STATE.md`「人間の承認・判断を待っている事項」冒頭の A / B):

- **A. `infra/requirements.lock` に非コメント行が1行も無い。**preflight の `libraries`
  検査が「pin と照合できない」で **WARN のまま通る**。実際に走った版は
  `runs/<id>/env.txt` にある(torch 2.8.0+cu128 / transformers 5.16.1 / peft 0.20.0)が、
  **「条件間で揃っているか」を機械が判定できない**(`infra/RUNPOD.md` §6 の前提)
- **B. `code/analysis/compare_runs.py` が「抽出された整数値」を記録していない。**
  ADR-040 決定1 の合否は分類と抽出値の両方だが、`batch_consistency.json` には
  `classification_*` しか入らない。**順1b では `predictions/*.jsonl` の `parsed` を
  直接突き合わせて 19/19 を確認した**(その手順はファイルに残らない)。
  **段階 C でも 100 項目で同じ確認を取る**(決定7)ので、実装するかを決める

**従来から残っているもの:**

- **`θ` の格子点 / 水準あたり項目数 / 抽出シード数**(順5 の前。ADR-041 決定5)
- **T3 の確定文面と T1b の書式文字列**(ADR-042 決定10)
- **LoRA の `learning_rate` / `num_steps` / `batch_size` / `gradient_accumulation`**(ADR-043 決定10)
- 最適化の既定値 / LoRA 重みの dtype / LoRA の `bias` /
  `model.adapter: null` のまま病変条件を評価できること /
  **T1b が Go/No-Go #1 を割ったときの分岐が無いこと**
- 手つかず: **#10(W6 の分岐)/ #17(Nikankin 原典確認)/ 目視レビュー11件 /
  効果量プロファイル / 罠3(凍結とパイロットの順序)**
