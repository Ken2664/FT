# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-04(その140)/ 直前セッションの役割: PLANNER(検出力分析の本実行の前の見直し)
直前セッションが終了した理由: **コンテキスト超過**(hook の実測 約 194k。`CLAUDE.md` §10.2)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus**。人間が A を選べば PLAN の起草と設計判断の材料になる(`Documents/10_CONTEXT_POLICY.md` §7 の「設計判断・統計」の行)。B・C(コードの小修正・本実行の起動)なら Sonnet。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェント(PLANNER)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## このセッションでやること(人間が選ぶ。1 つだけ)

`plans/PLAN-034-check-prerun/README.md` を読み(全文 45 行)、人間に A / B / C を諮る(判断材料の表を先に見せる。ADR-097 決定6)。
- **A(前セッションの推奨)**: 本実行を止めて PLAN-040 を起草する。問い = 「主要検定の検出力を決める軸を `sigma` から `n_item`(と `s2_item`)・誤指定の `tau` へ移すか / 誤指定のシートを先に回すか / `n_rep` と点数を減らすか / TOST の Δ の扱い(F3)」。ADR-067・068・114 に触るので、D 項目を表にして人間に聞き、ADR を書く。**値は提案しない**
- B: F6 の 1〜4(`sigma_limit` の `below_swept_range`・出力に run_id / git sha / config の写し・R の JSON を一時ファイル + rename・切り離した起動の手順)だけ PLAN に書いて直し、テストを通し、AC 電源を確かめてから人間の確認を得て本実行
- C: そのまま本実行(人間の確認と AC 電源の後)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- 本実行は起動していない。`configs/power_sim.yaml` は無変更(`s2_item` 2.0・`s2_tmpl` 0.5)
- F1〜F6 と近似のスクリプト・小検査の summary は `plans/PLAN-034-check-prerun/`。**数値は仮定値からの近似と 32 反復の検査で、実験結果ではない**(文書・論文に書かない)
- パイロットの T2 seed 1 は `rule` 0.0125・`other_error` 0.981・`correct` 0.006・`parse_fail` 0 [run:pilot_ft_eval_p2_s1]

## やってはいけないこと

- **Bash の `run_in_background` で本実行を起動しない**(最大 2 時間で止まる)。起動は人間の端末か切り離したプロセスで
- **本物の `configs/power_sim.yaml` を `power_sim.run` に渡すテストを書かない**(門が開いて本実行が走る)
- ADR-111〜121 を覆さない。`s2_*` を変えない。Δ・D7 の閾値・`n_item` の値を決めない・提案しない
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。1 コマンドに heredoc を 2 つ入れない。Python に渡すパスは `cygpath -m`
- STATE.md は 364 行・約 58.7 KB(上限 400 行 / 60 KB)。足すときは同じだけアーカイブへ移す

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- **★検出力分析の本実行の前の見直し(A / B / C)** ★新
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
