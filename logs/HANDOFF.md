# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-04(その144)/ 直前セッションの役割: IMPLEMENTER(PLAN-040 I5・I7・全テスト)
直前セッションが終了した理由: PLAN-040 の実装が完了(コンテキストは hook `context-guard` が約 160k トークンで警告)
直前セッションの実モデル: Claude Sonnet 5.5(推奨 Sonnet と一致)
**推奨モデル(次のセッション)**: 作業の種類による。**X(本実行の見守り・結果の整理)= Sonnet / Y(結果の解釈・§3.2 の見直し・Δ の決定の準備)= Opus**(`Documents/10_CONTEXT_POLICY.md` §7)。**モデルを選ぶのは人間**

---

あなたは **X なら RUNNER 補助、Y なら PLANNER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## PLAN-040 は実装済み(commit は直前の docs コミット)。残りは人間の起動

**エージェントは本実行を起動しない。** 起動の手順は `plans/PLAN-040-power-axes-review.md` **付録 A**(A.1 の確認表・A.2 の起動・A.3 の進み具合・A.4 の終了コード・A.5 の再開・A.6 の次の段・A.7 の費用の推算)。

### 人間が決める・やること(正本は `logs/OPEN-ITEMS.md`「★検出力分析の本実行の起動」)

1. **AC 電源にする**(いまはバッテリー駆動 24%・DC のスリープ 1 時間。AC のスリープ・休止は無効)・Windows Update を一時停止・`git status` がきれい
2. 起動の形(人間の端末か `Start-Process` で切り離し。**Bash の `run_in_background` は使わない**)と `--out-dir` の名前(例 `results/power_sim/run1`)
3. **段ごとに止まる**: `--through-stage 1`(**誤指定の門の結果は 2.6〜4.3 時間後**。推算)→ 人間が `power_sim_summary.json` を見て `--through-stage 2` → 3
4. `results/power_sim/` を commit するか(JSON が最終段で 20,000 枚。`summary`・`config.yaml`・`run_info.json` だけ commit する案が自然)

### 起動コマンド(1 段目)

```
python -m code.analysis.power_sim --config configs/power_sim.yaml --out-dir results/power_sim/run1 --through-stage 1 --workers 16
```

- 終了コード 0 = 指定の段まで / **3 = 誤指定の門が閉じた(止まる。§3.2 の見直しの別 PLAN。閾値や config を変えて回し直さない)** / それ以外 = 失敗(同じコマンドで再開)
- 進み具合: `(Get-ChildItem results/power_sim/run1/*/fits/*.json).Count`(1 段目の完了 = 2,000・誤指定だけ 600)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- I5 = PLAN-040 付録 A / I7 = `Documents/05_STATISTICS.md` §6 冒頭の注と §6.8 の「★2026-10-04 差し替え」の節(旧文は打ち消し線)
- 全テスト `pytest code/tests -q -k 'not smoke'`: **2405 passed・11 deselected・820 秒・失敗 0**(背景で回し、出力はファイルへ)
- `--dry-run --workers 16`(推算): 1 段目 全シート 11.6 / 19.3 時間・誤指定だけ 2.6 / 4.3 時間・最後の段で 20 点・40,000 本
- 本実行・push・tag・GPU・pod は無し

## やってはいけないこと

- **本実行を起動しない**(人間の確認・AC 電源の後。起動は人間の端末か切り離したプロセスで)
- **本物の `configs/power_sim.yaml` を `power_sim.run` / `main` に渡すテストを書かない**(その139 の暴走)
- ADR-111〜123 を覆さない。`s2_*`・格子・閾値・分位点を変えない。Δ・D7 の閾値を決めない。実際の `eval.cells` は変えない
- 閾値 0.075 に出典を付けない(未確認)。`sigma*`・`n_item_range` の数値は論文・事前登録の本文に書かない(仮定値からの値)
- 起動中に `configs/power_sim.yaml`・`code/analysis/power_sim*`・`power_sim_fit.R` を編集しない
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。日本語や `⁻` を含む置換は Write ツールでスクリプトを書いて `python -X utf8` で
- STATE.md は 371 行・約 59.7 KB(上限 400 行 / 60 KB)。足すときは同じだけアーカイブへ移す

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 本実行の起動(上)/ `results/power_sim/` の commit の方針
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
