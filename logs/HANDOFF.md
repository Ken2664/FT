# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その112)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(C111-1〜6 と実装の読み 18〜25 への人間の回答を ADR-110 に書き、§8.1 R7 に 4 行・§8.2 に 3 行を足した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — 実装とテスト(`Documents/10_CONTEXT_POLICY.md` §7 の表の「実装」の行)。統計の計算には触れない(止める条件と表示だけ)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。RunPod MCP は要らない(GPU は使わない)。

## このセッションでやること(1つだけ)

**ADR-110 決定1・3 を実装する。**仕様の正本は `logs/DECISIONS.md` の ADR-110 と `plans/PLAN-032` §8.1 R7(4 つ目の箇条の下の 3 行 = その112 で足した行)。

1. **決定1(C111-1。GPU の前の門)**: `code/eval/run.py` の `execute_threshold_sweep`(`:2083`)で、config に `sharpness:` 欄のある run は、**`prepare_run_dir` の前(run dir を作る前・重みを読む前)**に、`write_git_sha`(`code/artifacts.py:231`)が `git_diff.patch` に書くのと**同じもの**(`_capture(["git", "diff", "HEAD"])` の出力。stdout と stderr の連結)が空でなければ止める。`sharpness:` 欄の無い run(順6b・I5・本番)には掛けない
   - `_capture` は git の失敗時に `<取得できず: …>` を返す(空でない)ので、止まる側に倒れる。それでよい
   - テストでは git の呼び出しを差し替える(repo の作業ツリーの状態に依存させない)。負例: 差分あり → 止まる・run dir ができない・重みを読まない / 差分なし → 通る / `sharpness:` 欄なし → 差分があっても通る / stderr だけの出力 → 止まる
   - `--dry-run` で門を当てるかは定めが無い。選んだら §11 の注に書く
2. **決定3(C111-3。解析側の来歴の表示。止めない)**: `code/analysis/sharpness_fit.py` の判定表(json と txt)に、解析時の `git rev-parse HEAD` と「`git diff HEAD -- code/` が空か」を、run 側の `commit_sha`(`build_report` `:1026`・`report_lines` `:1149`)に並べて出す。**止めない**(食い違っても判定表は出す)。git の呼び出しはテストで差し替えられる形にする
3. `pytest code/tests -q`(その110・その111 は 1991 passed。増えるはず)と config 4 本の `--dry-run`(102,892 件のはず。不変)。自己点検(`CLAUDE.md` §7): 新しい門・表示をわざと外して、対応するテストが落ちることを確かめてから戻す
4. 定めの無い配線を選んだら `plans/PLAN-032` §11 の注に「実装の読み 26〜」として書く(人間が tag の前に覆せる)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-110**(4 問とも人間が推奨を採った): C111-1 = (a) run.py の門 / C111-2 = (a) 4 腕は tag の commit で回す + 予備 (b)(運用の規則。**コードは tag を照合しない**)/ C111-3 = (a) 解析側の来歴を表示 / C111-4 = (a) GPU の前に push(**人間**)/ C111-5 = 何もしない / C111-6 = (a) `run_id` の時刻が最も早い run(**コード不要**。`sharpness_fit` は重複で止まるままでよい)/ 読み 18〜25 = そのまま
- `plans/PLAN-032` のステータス = `ADR-110 の実装待ち`。§8.1 R7 に 4 行・§8.2 に 3 行(**R2〜R5 の規則と値・線 0.088 は不変**)
- ADR-110 決定8(エージェントの具体化): 決定1・3 は統計の計算に触れないので、ADR-101 決定5 の CRITIC のレビューは要らないと読んだ(**要るとするかは人間**)

## 触ってよいファイル / 読むべき範囲

- 書く: `code/eval/run.py` / `code/analysis/sharpness_fit.py` / 対応するテスト(`test_threshold_sweep_run.py`・`test_diag_sharpness.py`・`test_sharpness_fit.py` のどれか)/ `plans/PLAN-032`(ヘッダのステータス・§10・§11 の表と注。**§8.1 は変えない**)/ `logs/OPEN-ITEMS.md` の「PLAN-032 の凍結 tag と G2-1」行 / `STATE.md` / `logs/STATE-ARCHIVE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: ADR-110(`grep -n '^## ADR-110' logs/DECISIONS.md`)/ `plans/PLAN-032` §8.1 R7(`grep -n 'R7 止める条件' plans/PLAN-032-sharpness-diagnostic.md`)/ `logs/CRITIQUE.md`「その111」の C111-1・C111-3 / `code/artifacts.py:201-241`(`_capture`・`write_git_sha`)
- **編集しない**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / config・テンプレート / R2〜R5 の関数(`delta2_point`・`arm_reaches`・`next_stage`・`r5_decision`)と区間の計算法(`confidence_interval`)/ `check_provenance` の照合の中身(ADR-109 決定1)

## やってはいけないこと

- **tag を打たない・push しない・pod を起動しない・GPU を使わない**。合否線・R2〜R5 の規則・区間の計算法を変えない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `cat >>` / `python <script>`。Python に渡すパスは `C:/Users/...` の形)。**`.md` は LF 固定**(`.gitattributes`)。**Python で書くときは `newline="\n"`**
- テストのモジュールを scratchpad から import するときは `PYTHONPATH=C:/Users/keenk/paper/FT/infra` が要る
- `STATE.md` は 59,923 バイト(上限の目安 60 KB)。新しいブロックに ADR の中身を書き写さない(正本を指す)。超えたらアーカイブへ移す

## 未解決 / 人間の承認待ち

- **ADR-110 の実装** → **PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`。人間)→ push(人間。main と tag。GPU の前)→ G2-1 GPU 承認(人間)**(`logs/OPEN-ITEMS.md` の行)。RUNNER は tag の commit のまま 4 腕を続けて回し、I5 はその後(`plans/PLAN-032` §8.2)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
