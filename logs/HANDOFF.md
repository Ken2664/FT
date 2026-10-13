# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-13(その166)/ 直前セッションの役割: (指定なし。結果の読み出しと記録 = ANALYST 相当)
直前セッションが終了した理由: context-guard(約 105k)+ 区切り(PB の計時の記録を commit した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — run3 の起動の準備(`--dry-run --workers 16`・夜用タスクの登録の手順)は「実装・集計」の行(`10_CONTEXT_POLICY.md` §7)。**実装の判断 6 件の解釈・PB の反復数(S5)・run3 の結果の読みが出たら止めて PLANNER(Opus)へ**

---

あなたは IMPLEMENTER(run3 の起動の準備は RUNNER 相当)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**人間の指示を待つ。**候補は `STATE.md`「次のアクション」の 1(PLAN-043 §12 の実装の判断 6 件の確認 → run3 の起動)。
人間が run3 の起動を指示したら、PLAN-043 §4 Q6 の手順 2〜3 に沿って `python -m code.analysis.power_sim --config configs/power_sim.yaml --dry-run --workers 16` の費用の表を出し、
夜用タスクの登録(`register_tasks.ps1 -OutName run3 -ThroughStage 1`)と run2 の登録の無効化は**人間が行う**ことを伝える。起動そのものはしない。

## 直前セッションで確定したこと

- PB の計時(PLAN-043 I9)は 2026-10-12 夜に人間が実行した。[run:20261012_132900_pb_timing](run_id は事後に付けた。`results/power_sim/pb_timing/run_info.json`)。commit `e034f7d`
- 数値の正本は `results/power_sim/pb_timing/pb_timing.json`。要約は `STATE.md`「いま何をしているか」と `logs/CHANGELOG.md` その166(当て直し 160 本・例外 0・非 singular の警告 94・1 回の引き 平均 68.3 秒)
- **タスクスケジューラなどアプリの外から R を起動すると `lme4` が見つからない**(1 回目は終了コード 1)。`R_LIBS` を明示するやり方は `results/power_sim/pb_timing_launch.ps1` にある。夜用の `infra/power_sim_night/start_night.ps1` は `R_LIBS` を設定している(2026-10-13 に `grep -c R_LIBS` = 3 で確認。中身は読んでいない)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-043-adr128-fit-rescue-and-gates.md` §4 Q6・§10・§12(`grep -n` → `sed -n`)
- `infra/power_sim_night/`(必要なら `grep -n R_LIBS` で設定の中身を確認)
- `results/power_sim/pb_timing/`(読むだけ)

## やってはいけないこと

- run3 の起動・夜用タスクの登録 / 無効化・push・tag を人間の合図なしに行う
- PB の秒数から PB の反復数・中の失敗の扱いを決める(S5。人間)
- `results/power_sim/run2/` を書き換える(`misspecification_seed_per_cell/frames/` の残骸の削除も人間の指示を待つ)

## 未解決 / 人間の承認待ち

- PLAN-043 §12 の実装の判断 6 件の確認
- run3 の起動(夜用タスクの登録・run2 の登録の無効化を含む)/ push / G2-1 承認
- S5: PB の反復数・PB の中で ADR-059 の判定を回すか・観測の当てはめが床で失敗した表から引くか(`logs/OPEN-ITEMS.md` PLAN-042 の行)
