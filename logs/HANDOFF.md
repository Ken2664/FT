# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その109)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(C108-1〜4 と実装の読み 12〜17 への人間の回答を ADR-109 に書き、§8.1 R7 に 1 行足した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — 実装とテスト(`Documents/10_CONTEXT_POLICY.md` §7 の表の「実装」の行)。統計の計算には触れない(止める条件・テスト・例外の型)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。RunPod MCP は要らない(GPU は使わない)。

## このセッションでやること(1つだけ)

**ADR-109 決定1・2 を `code/analysis/sharpness_fit.py` とテストに実装する。**仕様の正本は `logs/DECISIONS.md` の ADR-109 と `plans/PLAN-032` §8.1 R7(4 つ目の箇条 = その109 で足した行)。

1. **決定1(C108-1)**: 判定表を出す前に、4 本の run dir で (i) `git_sha.txt` の 1 行目(sha)が 4 本で同じ / (ii) 各 run の `git_diff.patch` が**無いか 0 バイト**、を照合し、外れたら `SharpnessError` で止める。**`git_sha.txt` の 2 行目 `dirty:` は見ない**(pod で回した既存の run は全部 `dirty: true`・diff 0 バイト。追跡外のファイルで立つ。`code/artifacts.py` の `write_git_sha`)。**その sha を判定表の先頭(txt と json)に出す。**tag の名前・祖先関係はコードで照合しない(ADR-109 決定1)。置き場所は `check_premises` の近く(`build_report` の中。`build_report` を直接呼ぶ経路でも止まること)
   - テストの置き物の run dir に `git_sha.txt` を書く必要が出るはず。**既存のテストのヘルパーに足す**形にし、照合の失敗のテスト(sha が 1 本だけ違う / 1 本に 0 バイトでない diff / diff が 0 バイトなら通る / `dirty: true` でも diff が無ければ通る / `git_sha.txt` が無い)を足す
2. **決定2**:
   - **C108-2**: シナリオを 1 つ足す —— `"b": _by_task(t1b=_always_no, t3=_truthful)`・`"a": _always_no`・`"b_d": _truthful`・`"a_d": _always_no`(T1b = 前段 FT・R5 は ③-iii を残す / T3 = 前段 FT は要らない + 異常の印)。R5 の 3 つ目の引数を `(ARM_B, T3)` に取り違えると落ちることを一度確かめてから戻す
   - **C108-3**: `cell_delta2` で「n = `n_per_level`」と「組ごとの差の平均 = Δ₂ の点推定(`Fraction` で一致)」を確かめ、外れたら `SharpnessError`。**合否・区間の計算法は変えない**
   - **C108-4**: `load_diag_run` の `metrics["threshold_sweep"]`・`DiagRun` の `metrics["run_id"]`・`tokenizer_counter` の `require` と `AutoTokenizer.from_pretrained`・`main` の `runs[0]`(glob が 0 本)・`mass_rows` の `TypeError` を `SharpnessError` に包む(行番号は `logs/CRITIQUE.md`「その108」の C108-4)
3. `pytest code/tests -q`(その107・その108 は 1958 passed。増えるはず)と config 4 本の `--dry-run`(102,892 件のはず。不変)。自己点検(`CLAUDE.md` §7): 新しい照合をわざと外して対応するテストが落ちることを確かめてから戻す
4. 定めの無い配線を選んだら `plans/PLAN-032` §11 の注に「実装の読み 18〜」として書く(人間が tag の前に覆せる)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-109**(3 問とも人間が推奨を採った): C108-1 = (a) + §8.1 R7 に 1 行 / C108-2・3・4 = IMPLEMENTER / 読み 12〜17 = そのまま
- `plans/PLAN-032` のステータス = `ADR-109 の実装待ち`。§8.1 R7 に 1 行(**R2〜R5 の規則と値・線 0.088 は不変**)
- ADR-109 決定4(エージェントの具体化): 決定1・2 は統計の計算に触れないので、ADR-101 決定5 の CRITIC のレビューは要らないと読んだ(**要るとするかは人間**)

## 触ってよいファイル / 読むべき範囲

- 書く: `code/analysis/sharpness_fit.py` / `code/tests/test_sharpness_fit.py`(必要なら `test_diag_sharpness.py`)/ `plans/PLAN-032`(ヘッダのステータス・§10・§11 の表と注。**§8.1 は変えない**)/ `logs/OPEN-ITEMS.md` の「PLAN-032 の凍結 tag と G2-1」行 / `STATE.md` / `logs/STATE-ARCHIVE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: ADR-109(`grep -n '^## ADR-109' logs/DECISIONS.md`)/ `plans/PLAN-032` §8.1 R7(`grep -n 'R7 止める条件' plans/PLAN-032-sharpness-diagnostic.md`)/ `logs/CRITIQUE.md`「その108」の C108-2〜4 / `code/artifacts.py` の `write_git_sha`
- **編集しない**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / config・テンプレート / R2〜R5 の関数(`delta2_point`・`arm_reaches`・`next_stage`・`r5_decision`)と区間の計算法(`confidence_interval`)

## やってはいけないこと

- **tag を打たない・pod を起動しない・GPU を使わない**。合否線・R2〜R5 の規則・区間の計算法を変えない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `cat >>` / `python <script>`。Python に渡すパスは `C:/Users/...` の形)。**`.md` は LF 固定**(`.gitattributes` の `*.md text eol=lf`。`test_repo_hygiene.py` が CR を落とす)。**Python の `open(..., "w")` は Windows で CRLF を書くので `newline="
"` を付ける**(その109 で STATE.md などが一度 CRLF になり、hygiene が落ちて直した)
- テストのモジュールを scratchpad から import するときは `PYTHONPATH=C:/Users/keenk/paper/FT/infra` が要る(`preflight` を読む)

## 未解決 / 人間の承認待ち

- **ADR-109 の実装** → **PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`。人間)→ G2-1 GPU 承認(人間)**(`logs/OPEN-ITEMS.md` の行)。RUNNER は 4 腕を同じ commit で続けて回す(決定1 の代価 = 途中でコードを直すと 4 腕とも回し直し)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
