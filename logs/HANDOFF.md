# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-04(その146)/ 直前セッションの役割: RUNNER 補助(夜だけ回すスクリプトの作成)
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 107k トークンで警告)
直前セッションの実モデル: Claude Sonnet 5.5(推奨 Sonnet と一致)
**推奨モデル(次のセッション)**: 作業の種類による。**X(本実行の見守り・進み具合の確認・結果の整理)= Sonnet / Y(結果の解釈・§3.2 の見直し・Δ の決定の準備)= Opus**(`Documents/10_CONTEXT_POLICY.md` §7)。**モデルを選ぶのは人間**

---

あなたは **X なら RUNNER 補助、Y なら PLANNER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## 状態: PLAN-040 は実装済み。夜だけ回すスクリプトも commit 済み(`ba909a4`)。**本実行はまだ起動していない**

**エージェントは本実行を起動せず、タスクも登録しない。** 手順の正本は `plans/PLAN-040-power-axes-review.md` 付録 A と、下の「夜の運用」。

### 夜の運用(21:00〜06:00 を何日かに分けて回す。人間が登録する)

置き場所: `infra/power_sim_night/`(`start_night.ps1`・`stop_night.ps1`・`register_tasks.ps1`)。再開は付録 A.5 の「同じコマンド」(`code/analysis/power_sim.py:1330` が既存の `fit_*.json` を飛ばす。R は `.tmp` + rename で書くので、止めても壊れた JSON は残らない。失うのは走っていた反復だけ = 最大 16 本・5〜20 分)。

人間の手順:
1. AC 電源につなぐ・`powercfg /change standby-timeout-ac 0` と `powercfg /change hibernate-timeout-ac 0`・ふた閉じは AC で「何もしない」(バッテリーはスリープのまま)・Windows Update を一時停止・ログインしたままにする
2. プレビュー: `powershell -ExecutionPolicy Bypass -File infra/power_sim_night/register_tasks.ps1 -OutName run1 -ThroughStage 1 -RLibs "C:\Users\keenk\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\R\win-library\4.6" -DryRun`
3. 登録: 同じコマンドから `-DryRun` を外す(21:00 起動 / 06:00 停止の 2 タスク。削除は `-Unregister`)。**★`-RLibs` が要る**(下)
4. **初日の 21:00 に目で見る**: `Get-Process Rscript` が 16 前後・`Get-Content results/power_sim/run1_night_stdout.txt -Tail 5` に `started pid ...`・`(Get-ChildItem results/power_sim/run1/*/fits/*.json).Count` が増える(1 段目の完了 = 2,000・誤指定だけ 600)
5. 段が終わったら人間が `power_sim_summary.json` を見て、`-ThroughStage 2`(次は 3)で登録し直す。**門が閉じた(`stopped_at_gate` / 終了コード 3)ら回し直さない**(§3.2 の見直しの別 PLAN)

推算(付録 A.7 を 9 時間で割っただけ。**実測ではない**): 1 段目の誤指定の門だけ 1 晩 / 全シート 2〜3 晩 / 2 段目 3〜5 晩 / 3 段目 9〜15 晩。

### ★その146 で起きたこと: 最初の 21:00 の起動は `lme4` が無くて落ちた(0 反復)
- 人間が登録済みだった(`PowerSimNightStart` / `PowerSimNightStop`)。21:00 にタスクが `start_night.ps1` を起動 → Python は起動したが、**Rscript が `there is no package called 'lme4'` で落ちた**(`results/power_sim/run1_20261004_210001_stderr.txt`・`fits/` は 0 件・`invocations.jsonl` に 1 行)
- 原因(推定): この機械の R のユーザーライブラリは Claude アプリ内からだと `C:\Users\keenk\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\R\win-library\4.6` にあり、タスクスケジューラ(アプリの外)の R は `C:\Users\keenk\AppData\Local\R\win-library\4.6` を見て `lme4` を見つけられない。`R_LIBS` にそのパスを渡すと `requireNamespace('lme4')` は TRUE(アプリ内から確認。タスクの中の実際の環境は未確認)
- 直した(`f69e8a8`): `start_night.ps1` に `-RLibs`(→ `R_LIBS`)と起動前の `lme4` 検査(見えなければ `REFUSED` で起動しない)・`register_tasks.ps1` に `-RLibs`。**`configs/power_sim.yaml` は変えていない**(`fit.r_libpath` は null のまま。config の写しと食い違わないので、同じ `--out-dir run1` で続けられる)
- **登録のし直しが要る**(今の 2 タスクは `-RLibs` なしで登録されている)。**今夜の分は落ちた**(`-RLibs` 付きで登録し直すか、人間が手で `start_night.ps1 -OutName run1 -ThroughStage 1 -RLibs ...` を実行すれば今から回せる)

### 確かめたことと確かめていないこと
- 確かめた: 3 本とも構文エラー 0・非 ASCII 0・CR 0。`-DryRun` で、起動はバッテリー駆動のため拒否(`BatteryStatus` = 1)・停止は「止めるものなし」・登録は内容を表示
- **未確認**: `-RLibs` を付けて実際に最後まで回る経路(`-DryRun` は通った。lme4 検査もその中)・登録のし直し・06:00 の停止・スリープからの復帰・ふた閉じの既定の動作(`powercfg` で値が取れなかった)。**初日は必ず見る**

## このセッションでやること(人間の指示が先。無ければ「進み具合の確認」)

- X: 人間が登録・起動した後の見守り(読むだけ。`fits/*.json` の数・`run1_night_stdout.txt`・`stdout/stderr`)。**起動中は `configs/power_sim.yaml`・`code/analysis/power_sim*`・`power_sim_fit.R` を編集しない**
- Y: 段の結果の解釈の準備(解釈・決定は人間。`CLAUDE.md` §8)

## やってはいけないこと

- **本実行を起動しない・タスクを登録しない**(人間の端末・人間の登録)。Bash の `run_in_background` は使わない
- **電源設定・Windows Update の設定を変えない**(人間が設定で)
- **本物の `configs/power_sim.yaml` を `power_sim.run` / `main` に渡すテストを書かない**(その139 の暴走)
- ADR-111〜123 を覆さない。`s2_*`・格子・閾値・分位点を変えない。Δ・D7 の閾値を決めない。実際の `eval.cells` は変えない
- 閾値 0.075 に出典を付けない(未確認)。`sigma*`・`n_item_range` の数値は論文・事前登録の本文に書かない(仮定値からの値)
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。`.ps1` は ASCII のみ(PowerShell 5.1 は BOM なしを ANSI で読む)。日本語や `⁻` を含む置換は Write でスクリプトを書いて `python -X utf8` で
- STATE.md は約 60 KB・371 行(目標 400 行 / 60 KB)。足すときは同じだけアーカイブへ移す

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 本実行の起動の前の確認(AC・スリープ・Windows Update)とタスクの登録(上)/ `results/power_sim/` は要約と記録だけ commit(人間が採択済み)
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
