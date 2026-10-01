# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-01(その127)/ 直前セッションの役割: PLANNER(人間が PLAN-033 §5 を承認し、文書の修正を入れた = ADR-113)
直前セッションが終了した理由: **PLAN-033 が完了した**(1 セッション = 1 PLAN)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **(β) R8 の実行なら Sonnet**(RUNNER)/ **(γ) 検出力分析の PLAN なら Opus**(統計・設計判断。`Documents/10_CONTEXT_POLICY.md` §7)。**どちらをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**人間の最初の指示が先**です。指示が無ければ、下の「いまの状態」を要約し、(β)(γ) のどちらにするかを人間に聞いてください(判断材料と推奨を付ける。`AGENTS.md` PLANNER 節「判断材料を先に見せる」・memory「Recommend before choice」)。

## いまの状態(すべてファイルに反映済み: `STATE.md`・`logs/CHANGELOG.md` その127・`logs/DECISIONS.md` ADR-113)

- **主要検定は T1 × T2(`task:coverage` の LRT、df = 2)**。df < 2 なら実施不能。T1b・T3 は測り続けるが探索。**H0 と H1 は E1(T2 × 既知性 3 水準の `p2` − `ident`。門の外・順7 と同じ Holm・優越性と TOST を併記)で分ける**。E1 が両方成り立つときは「転移しない」の側(ADR-113 決定3)
- 文書は `CLAUDE.md` §0・§8 / `AGENTS.md` PLANNER 節 / `Documents/` 00・01・03・04・05・06・07・09 に反映済み(旧文は打ち消し線)。**`05_STATISTICS.md` §6 の本体と `09_PAPER_PLAN.md` の本体は未追随**(冒頭の注だけ)
- push は依然未(`origin/main` = `102c2d5`)。稼働中の pod は無い(5 本とも `EXITED`。ボリューム `r963j7swke` は残す)

## 次の作業の候補(どちらを先にするかは人間)

- **(β) R8 の実行**(RUNNER / Sonnet): 人間が push → RUNNER が見積り → 人間が G2-1 承認 → `infra/RUNPOD.md` §4。`configs/exp_pilot_ft_cmp_*` の 10 本。**R8 の結果は探索**(ADR-112 決定4。順8・順9 は門の外ではなく探索)
- **(γ) 検出力分析の PLAN**(PLANNER / Opus): `plans/PLAN-033` §6 の表が出発点。P1 の T1・T2 の行の RMS(0.353 → 0.432。計算)をどう扱うか・P2 は定義できない・`n_item` は 80 の整数 1 つ・`configs/power_sim.yaml`・`test_power_sim.py`(df = 6 を固定)・`power_sim.py`・`power_sim_fit.R` の追随。所要時間は約 52 時間の推算(未実測)。**値・プロファイルは人間**

## やってはいけないこと

- **ADR-111・112・113 を覆さない**
- **E1 の TOST 境界の値・効果量プロファイルの値を決めない・提案しない**(値は人間)
- **tag を打たない・push しない・pod を起動しない**(人間の操作・承認が先)
- **この機は Windows**: `.md`・`.py` は LF 固定(Python で書くときは `newline="\n"`)。長い日本語は `Write` でスクラッチパッドにスクリプトを置いてから Python で入れる。**置換は件数を数えてから**。**Bash で `cat >` を標準入力なしで書かない**(その127 で 120 秒止まった)
- STATE.md は 370 行・59.6 KB。**次に足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- ★R8 の push と G2-1 承認 / ★E1 の TOST 境界の値(凍結前)/ 検出力分析の模型 / ★`CLAUDE.md` を 200 行へ戻す(216 行)
- 旧 4 本と `9matkiq0jozcgm` の terminate / その122 の採択の ADR(未記入)/ ★T2 の形の変化と #5 の扱い・★`train_size` 掃引の意味・★rank の格子と学習率の揃え方(凍結前)
