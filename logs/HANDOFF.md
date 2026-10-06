# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-06(その157)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN 完了(PLAN-042 D0〜D4 の実装。context-guard も約 218k で警告)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Sonnet — 診断の実行と集計の読み取り(`10_CONTEXT_POLICY.md` §7。実行・集計は Sonnet)。**結果の解釈と (5) の設計判断は Opus**(§8。解釈は人間)

---

あなたは RUNNER(診断の実行)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**人間が「実行してよい・日時はいま」と言うまで診断を起動しない**。

## このセッションでやること(1つだけ)

人間が実行の合図をしたら、PLAN-042 の診断を実行して `results/power_sim/run2/exploratory/fit_failure_diagnosis.json` を作り、数字を **解釈せずに**並べて報告する。
```bash
python -X utf8 -m code.analysis.fit_failure_diagnosis --config configs/fit_failure_diagnosis.yaml --select-only   # まず件数の確認(R は呼ばない)
python -X utf8 -m code.analysis.fit_failure_diagnosis --config configs/fit_failure_diagnosis.yaml                  # 本実行(約 1 時間の見込み・未実測。16 並列)
```
- 本実行は長いので Bash の `run_in_background` を使わず、人間の端末(`mcp__terminal`)か `timeout` を伸ばして回す。**`date` で時計を見る**(通知に頼らない)
- 最初の数本で D0 が合わなければ R が異常終了する → **止まって人間に報告**(再現しない = 診断の前提が崩れた。閾値や許容を黙って緩めない)
- 終わったら `jq` で必要なキーだけ読む(`judgement_rows`・`descriptive_rows`・`failed_only_rejection`・`row_5_separation`・`d4_new_term_sd`・`d0`)。`cases` と `fit_failure_diagnosis_work/r_out/` は全文読まない
- 出力の数値は run_id(`20261005_120003_power_sim_t1t2`)とセットで報告する。記録は `logs/CHANGELOG.md`・commit(`exp(analysis): ...`)

## 直前セッションで確定したこと

- 実装は commit `94b64a6`。§2.2 の全出力(判定の行 1a・1b・3/4 + `fit0` の感度 / 記述の行 2・R・U / 失敗した反復だけの棄却率と CP95 / 行 5 / D4 / D0)を含む。詳細と判断 9 項目は `plans/PLAN-042-fit-failure-diagnosis.md` §7
- `--select-only` は run2 の fits で既知の件数(失敗 156 = 100 + 56 / 対照 20 / 門の 4 点 25・22・27・29 = 103 / 行 R 13・6・7・12)と一致した(新しい結果ではない)
- R 側は `power_sim_fit.R` の driver より上を評価して借りる。`power_sim.py`・`power_sim_fit.R`・`configs/power_sim.yaml`・規則(ADR-059・ADR-124 D2')は不変

## 触ってよいファイル / 読むべき範囲

- 実行するだけなら新規編集は不要。`configs/fit_failure_diagnosis.yaml`(`n_workers` は `--workers` で上書き可)。`plans/PLAN-042` §7 は `grep -n '実装の判断' ` → `sed -n` で読む

## やってはいけないこと

- ADR-059・ADR-124 D2'・ADR-125 決定3・`configs/power_sim.yaml` を変える・§2.1 / §2.2 の閾値を書き換える(実行後に変えない。HARKing)
- 結果の解釈・「支える」を根拠にした規則変更の提案の確定(人間。§8)。記述の行(2・R・U)で門の結論を言い換えない(PLAN-042 罠6)
- 夜用タスクと同じ夜に回す(`stop_night.ps1` と衝突する。今夜の夜用タスクは 1 回だけ走らせた後に人間が無効にする = ADR-126 決定3)
- 失敗した反復だけの棄却率を「本当の過誤」と読む(選択の偏り。罠2)

## 未解決 / 人間の承認待ち

- **実行の日時と合図**(人間)
- **PLAN-042 §7 の実装の判断の確認**(人間): 特に 3(`allFit` の `start_from_mle = FALSE`。lme4 2.0.6 の既定は TRUE で、それでは「別の最適化で収束する」の証拠にならないと判断した。数字が動く)・1・2(「揃った最適化」と 1b の固定効果の差の定義)・5(行 U の p 値の優先順)
- 診断の後の (5): 実行可能性の門の上限と判定する点・D2' の書き換え・ADR-059 の許容・ADR-125 決定3 との整合・新しい反復の取り方(規則を変えたら門は新しい反復で判定。ADR-127 決定6)
