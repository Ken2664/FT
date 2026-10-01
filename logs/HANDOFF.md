# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-01(その129)/ 直前セッションの役割: PLANNER(検出力分析の再導出を PLAN-034 にし、人間が D1〜D10 に答えた = ADR-114)
直前セッションが終了した理由: **PLAN-034 の設計が決まった**(1 セッション = 1 PLAN。実装は次のセッションと ADR-114 決定10 で決めた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **(δ) PLAN-034 の実装なら Sonnet**(IMPLEMENTER。`Documents/10_CONTEXT_POLICY.md` §7)/ **(β) R8 の実行なら Sonnet**(RUNNER)/ **(α) 価値レビューの残りの案(A・C・E・F・G)を ADR に落とすなら Opus**。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**`git log` で並行セッションの commit が入っていないかも確かめる** —— その129 の途中で別セッションの `4182df5` が入った)。**人間の最初の指示が先**です。指示が無ければ (δ)(β)(α) のどれにするかを、判断材料と推奨を付けて人間に聞いてください(`AGENTS.md` PLANNER 節・memory「Recommend before choice」)。

## いまの状態(すべてファイルに反映済み: `STATE.md`・`logs/CHANGELOG.md` その129・`logs/DECISIONS.md` ADR-114・`plans/PLAN-034-power-t1t2.md`)

- **主要検定は T1 × T2(df = 2)・H0 と H1 は E1 で分ける**(ADR-112・113。変わらず)
- **ADR-114(PLAN-034 D1〜D10。10 問とも推奨)**: P1 は delta を √(2/3) 倍して RMS 0.353 を保つ / 形の検査は符号反転 P1⁻(2 点)/ `n_item` = 80 の整数 1 つ / P0 を全格子 12 点(α の較正と TOST)/ **平行性の TOST = 交互作用 2 係数の Wald 90% CI の IUT。Δ は決めずに曲線で出す** / 2 尺度は報告規則 / **シード単位は §3.3 の報告 + 誤指定シート(DGP にだけ seed × task × coverage の `tau`。当てはめは §3.2 のまま)** / E1 の検出力と天井は PLAN の外
- **実装はまだ**: `configs/power_sim.yaml`・`code/analysis/power_sim.py`・`power_sim_fit.R`・`code/tests/test_power_sim.py`・`Documents/05_STATISTICS.md` §6 は 4 × 3・df = 6 のまま
- 価値レビュー(その128)の案は **B・D だけ部分決着**。A・C・E・F・G は未決(`logs/OPEN-ITEMS.md` の行)
- push は依然未(`origin/main` = `102c2d5`)。稼働中の pod は無い

## 次の作業の候補(どれを先にするかは人間)

- **(δ) PLAN-034 の実装**(IMPLEMENTER / Sonnet): `plans/PLAN-034-power-t1t2.md` §6 の I1〜I6 → `pytest code/tests -q` → I7 のベンチマーク(この機。`s2_*` は null のままなので動作確認用の値を smoke から。**数値は主張に使わない**)→ 1 ペアの実測時間を記録して人間に ★F114 を諮る。数値の根拠は PLAN-034 §5.1(√(2/3)・RMS 0.352767・P1⁻・P0・交互作用 2 係数)。**skill `code-style` を先に読む**
- **(β) R8**: 人間が push → G2-1 承認 → RUNNER。結果は探索(ADR-112 決定4)
- **(α) 価値レビューの残りの案**(PLANNER / Opus): A(MisFT の位置づけ。文書のみ)・C・E・F・G

## やってはいけないこと

- **ADR-111〜114 を覆さない**
- **値を決めない・提案しない**: `s2_item` / `s2_tmpl`(★F104-c)・平行性の TOST の Δ・シード分類の閾値・E1 の TOST 境界(値は人間)
- **§3.2 のモデル指定を変えない**(誤指定シートで α が膨らんでも、見直しは別 PLAN で人間が決める。ADR-114 決定7)
- **パイロットの数値を DGP の値に使わない**(PLAN-001 §4.6 規則4)
- **tag を打たない・push しない・pod を起動しない**。本実行(約 138 時間。推算)は ★F114 の後
- **この機は Windows**: `.md`・`.py` は LF 固定(Python で書くときは `newline="\n"`)。長い日本語はスクラッチパッドにスクリプトを置いてから Python で入れ、**置換は件数を数えてから**。heredoc の中の Python に `"\n"` を書くと改行に化けることがある(その129。`chr(10)` で避けた)
- STATE.md は 367 行・59.7 KB。**次に足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- ★F104-c / ★F114(I7 の後)/ ★平行性の TOST の Δ / ★シード分類の規則と閾値 / ★E1 の TOST 境界の値と E1 の検出力 / ★天井 / 価値レビューの案 A・C・E・F・G と引用の原典確認
- ★R8 の push と G2-1 承認 / ★`CLAUDE.md` を 200 行へ戻す / 旧 4 本と `9matkiq0jozcgm` の terminate / ★T2 の形の変化と #5・★`train_size`・★rank と学習率(凍結前)
