# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-08(その164)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 375k。R のスモークの待ちで膨らんだ)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Sonnet — 実装の仕上げと確認(`10_CONTEXT_POLICY.md` §7 の「実装・集計」の行)。**統計の判断が出たら止めて PLANNER(Opus)へ**

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-043 の実装の仕上げ。次の 4 つだけ。**
1. 診断の R の D0 スモーク: `fit_failure_diagnosis.R` は `power_sim_fit.R` の「# ---- driver」より上を借りる。上に `rescue_*` の関数を足したので、診断が引き続き動くことを **1 件**で確かめる(PLAN-042 §7 の手順。`python -X utf8 -m code.analysis.fit_failure_diagnosis --config configs/fit_failure_diagnosis.yaml` の対象を 1 件に絞るか、`results/power_sim/run2/exploratory/fit_failure_diagnosis_work/r_out/` の既存出力の写しと D0 が合うこと。**run2 の表・結果は書き換えない**。出力先は scratchpad)
2. `pytest code/tests -q` が通ること(直前は 2522 passed(`-k 'not smoke'` 2511 + `smoke` 11))を再確認
3. `plans/PLAN-043-*.md` の §10 のチェック(I1〜I8・I10・R のスモーク・`--dry-run`・打ち消し線)と §12 の実行ログ(実装の判断 6 件。下)を埋める。`logs/OPEN-ITEMS.md`(PLAN-042 の行)の追記
4. commit(コード = I1〜I8・I10 / PB の計時 = I9 は **別の commit**)。メッセージ末尾に `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`

**I9(PB の計時)は実行しない**。実行前に人間に日時を聞く(ADR-129 決定6)。

## 直前セッションで確定したこと(ファイルに入っている)

- 実装は `git status` の未コミットの変更にある(handoff の commit で入っているはず。`git log -3` で確認)。変えたファイル: `code/analysis/power_sim_fit.R`・`power_sim.py`・`fit_failure_diagnosis.py`・`pb_timing.{R,py}`(新)・`configs/power_sim.yaml`・`power_sim_smoke.yaml`・`pb_timing.yaml`(新)・`code/tests/test_power_sim.py`・`test_fit_failure_diagnosis.py`・`test_pb_timing.py`(新)・`infra/power_sim_night/start_night.ps1`・`register_tasks.ps1`・`Documents/05_STATISTICS.md`・`plans/PLAN-040`・`logs/DECISIONS.md`(ADR-059・123・124・125 のステータス行の末尾)
- 旧いテスト(失敗を過誤のシートで棄却に数える・TOST の向き・門の `sheets` × `tau`)は期待値を改め、テスト名と docstring に ADR-128 を書いた(黙って消していない)
- R のスモーク(scratchpad。数字は run3 の判定ではない): 床で失敗しない 3 表は変更前後で `p_value` が一致(罠6)。p0 9001 は変更前に失敗・変更後は `allFit` の段で救われた。run2 で床で失敗した 1 件(rep 2)は `allFit` の最適化ごとの logLik が PLAN-042 の診断の記録と一致し、add の揃った最適化が 1 で救えず(記述の p 値 0.7696)
- `--dry-run --config configs/power_sim.yaml` は通る(`rng_seed 20261008`・門・allFit が出る)。`pb_timing --dry-run` も通る

## 実装の判断(PLAN-043 §12 に書いて、人間に確認を求める)

1. 両方の門が閉じたとき終了コードは 3(両方の印は `stage_*_summary.json` に残る)
2. `FAILURE_AS_REJECT_ROLES` は空にせず定数ごと削除
3. PB の `simulate_seed` は run3 の `rng_seed` と同じ 20261008(新しい値を選ぶ自由度を作らない)
4. `feasibility_gate.scope` は `all_sheets_all_points` だけ受ける
5. 区間の水準は過誤の門・実行可能性の門の `ci_level`(0.95)を流用(新しい config 値を作らない)
6. `start_night.ps1` は `stopped_at_feasibility_gate` でも再起動を拒む(`stop_night.ps1` は不変。PLAN の I8 は「表示」と書いたが、終了コードを読むのは start 側の summary 読みなので)

## 触ってよいファイル / 読むべき範囲

- 上の「変えたファイル」と `plans/PLAN-043-*.md` §10・§12。全文 `cat` せず `grep -n` → `sed -n`。R の長い出力は `tail`

## やってはいけないこと

- ADR-129 の値を変える。最適化を足し引きする。`start_from_mle` を変える(罠3)
- 成功した反復の LRT を変える(罠6)。run2 の表・結果の書き換え。run2 の 100 反復で新しい規則の門を判定する(罠1)
- PB の計時の実行・run3 の起動・夜用タスクの登録・push・tag(人間の合図なし)
- R の長い待ち(数十分)をフォアグラウンドで流してコンテキストを使わない。待つなら `run_in_background` とファイル出力
- `.md` は LF、Python で書くときは `newline` を指定する(memory)。置換スクリプトは Write でファイルに書いて実行(heredoc の `\n` が解かれる)

## 未解決 / 人間の承認待ち

- 実装の判断 6 件の確認 / PB の計時の日時 / run3 の起動(夜用タスクの登録。run2 の登録が残っていれば無効にするのは人間)
- push(`01cf60f` 以降の main)と G2-1 承認 → S4
- PB の反復数と漸近 χ² と食い違ったときの扱いは S5 / 特異な分散成分(32 件)は未確認 / `run2/misspecification_seed_per_cell/frames/` の残骸 46 本と未追跡の `.claude/commands/` は人間
