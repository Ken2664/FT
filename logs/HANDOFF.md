# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-03(その139)/ 直前セッションの役割: PLANNER(PLAN-039 を完了。★F104-c 決着)
直前セッションが終了した理由: **コンテキストが閾値を超えた**(hook の実測 約 207k。`CLAUDE.md` §10.2)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet**(検出力分析の本実行の起動と見張り・R のスモークの確認は実行系。`Documents/10_CONTEXT_POLICY.md` §7)。結果の読み・設計判断に入るなら Opus。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェント(RUNNER)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## 最初に確かめること(★前セッションの後始末)

- **前セッションの pytest が暴走して残っているかもしれない**: `Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='Rscript.exe'"`。
  コマンド行に `pytest-of-keenk\...\test_run_stops_while_s2_is_und0` を含む `power_sim_fit.R` と、その親の `python -m pytest` が残っていれば、**止めてよいか人間に聞く**(前セッションでは `Stop-Process` が許可されなかった)。原因はテストが本物の config で門を確かめていたこと。テストは直した(`a405ffd`)
- **背景ジョブ(`run_in_background`)は、外側のシェルだけ先に「完了」と報告し、中の pytest が残ることがあった。**長い pytest は `timeout 590 python -m pytest ...` で前景に回す

## このセッションでやること(1つ。人間が選ぶ)

**A: 検出力分析の本実行の起動(推奨)**
1. `pytest code/tests/test_power_sim.py -q`(R のスモークを含む。前セッションでは未実行)→ 通ること
2. **AC 電源につながっているか**(`Win32_Battery.BatteryStatus` = 2)・スリープ無効を確かめる。前セッションの確認では**バッテリー駆動**(休止状態は DC で 72 時間後)だった
3. **人間の確認を得てから**(この機械を約 5〜6 日占有する)背景で `python -m code.analysis.power_sim --config configs/power_sim.yaml --out-dir results/power_sim --workers 16`。再開できる実装。`--dry-run` は通った(64,000 本・16 並列で約 138 時間の見積り / その137 の実測からの外挿は約 122 時間)
4. 見張りは時計で(memory: pod は時計で見張る。この件も同じ)

**B: PLAN-037 の I10**(人間の承認の後)

## 直前セッションで確定したこと

- ADR-120(推定の前に commit `e74df7e`): `s2_item` は `extrap_magnitude` の T1・T2 だけから、625 を主に推定 / 推奨値 = 主推定の profile 95% 上端
- 推定 [run:20261003_214842_s2_item_pilot](`results/s2_item_pilot/README.md`): 主推定の点推定 1.451、特異で profile 区間が立たず → 規則により推奨値なし
- ADR-121: **人間が推定を見た後に `s2_item` = 2.0 を選んだ**(ADR-119 の例の値)/ `s2_tmpl` = 0.5。`configs/power_sim.yaml` に反映。テスト `test_s2_values_are_the_decided_ones` が固定
- `*.ans_out.jsonl` は主要検定の既知性 `extrap_magnitude` そのもの

## やってはいけないこと

- **ADR-111〜121 を覆さない。`s2_*` を変えない**
- **本物の `configs/power_sim.yaml` を `power_sim.run` に渡すテストを書かない**(門が開いて本実行が走る)
- **他の値を決めない・提案しない**(Δ・D7 の閾値・T1c の件数・s の水準・step 数ほか。ADR-095 決定3 の外しは ★F104-c だけで、もう決着した)
- **借り物の値の検出力の数値を文書・results に書かない / tag・push・pod の起動をしない**
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。1 コマンドに heredoc を 2 つ入れない。Python に渡すパスは `cygpath -m`
- STATE.md は 365 行・約 58.8 KB(上限 400 行 / 60 KB)。**足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 暴走プロセスの停止 / 本実行の起動の確認(AC 電源)/ 次の作業(A / B)
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
