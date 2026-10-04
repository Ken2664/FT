# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-04(その143)/ 直前セッションの役割: IMPLEMENTER(PLAN-040 I1〜I4・I6)
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 260k トークンで警告)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — I5(手順書)・I7(文書の差し替え)・全テストは実装・文書の行(`Documents/10_CONTEXT_POLICY.md` §7)。**モデルを選ぶのは人間**

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## このセッションでやること(PLAN-040 の残り)

1. **I5**: 起動の手順を `plans/PLAN-040-power-axes-review.md` に **付録 A** として書く(`configs/power_sim.yaml` の冒頭がすでに「付録 A」を指している)。中身: AC 電源(`Win32_Battery.BatteryStatus` = 2)・スリープ / 休止状態(`powercfg`)・Windows Update の一時停止(人間が設定で)・`git status` がきれい・`--dry-run` → **人間の端末で**(または `Start-Process` で切り離して)起動:
   `python -m code.analysis.power_sim --config configs/power_sim.yaml --out-dir results/power_sim/<名前> --through-stage 1 --workers 16`
   / 進み具合の見方(`*/fits/*.json` の数・`power_sim_summary.json` の `stage`)/ 終了コード(0 = 指定の段まで / **3 = 誤指定の門が閉じた** / それ以外 = 失敗)/ 中断したら同じコマンドで再開(済んだ反復は飛ぶ)/ 次の段は人間が見てから `--through-stage 2`。**Bash の `run_in_background` は使わない**(最大 2 時間)
2. **I7**: `Documents/05_STATISTICS.md` §6.8(1220 行付近)の差し替え。旧文(4 シート 32 点・64,000 本・`sigma*` が主・P1⁻ {0, 1.0}・費用表)は**消さずに打ち消し線・日付・ADR-122/123**。新しい内容: 点の表(誤指定 6 / P1 6 / P1⁻ 2 / P0 6 = 20 点)・順・段 100 → 300 → 1000・門・報告量(`n_item_range` が主・`sigma*` が従・D5 の表)・費用(`--dry-run` の出力を引く。**推算**と明記)。§6 冒頭 854 行付近の「64,000 本」の注にも追記
3. **全テストを最後まで**: `pytest code/tests -q -k 'not smoke'` は 600 秒を超える。**背景で回し、出力はファイルに**(その143 は 71% まで・失敗 0)
4. CHANGELOG・STATE を更新して commit。PLAN-040 のステータスを「実装済み」に

## 直前セッションで確定したこと(ファイルに書き込み済み)

- 実装は commit `8e89666`。`configs/power_sim.yaml` に ADR-123 の値・`report`・`misspecification_gate`・`n_rep_stages` を転記済み
- 人間が 2 問とも推奨(PLAN-040 §11 に追記): **段ごとに止まる**(`--through-stage` は本実行で必須)/ **D5 の分位点 5・25・50・75・95%**
- `--dry-run`(16 並列。**推算**): 1 段目 全シート 11.6 / 19.3 時間・誤指定だけ 2.6 / 4.3 時間(ベンチ / 小検査)。ADR-123 文脈2 と一致
- テスト: `test_power_sim.py` 114 passed・`test_repo_hygiene.py` 68 passed。R のスモーク(2 段)完走(スクラッチパッド。数値は使わない)

## やってはいけないこと

- **本実行を起動しない**(人間の確認・AC 電源の後。起動は人間の端末か切り離したプロセスで)
- **本物の `configs/power_sim.yaml` を `power_sim.run` / `main` に渡すテストを書かない**(その139 の暴走)
- ADR-111〜123 を覆さない。`s2_*`・格子・閾値・分位点を変えない。Δ・D7 の閾値を決めない。実際の `eval.cells` は変えない
- 閾値 0.075 に出典を付けない(未確認)
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。日本語や `⁻` を含む置換は Write ツールでスクリプトを書いて `python -X utf8` で
- STATE.md は 370 行・約 59.2 KB(上限 400 行 / 60 KB)。足すときは同じだけアーカイブへ移す

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 本実行の起動(I5・I7 の後・AC 電源)
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
