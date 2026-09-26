# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その116)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **PLAN 完了**(ADR-110 決定1・3 の実装をコミットまで済ませた。**`plans/PLAN-032` に IMPLEMENTER の仕事は残っていない**。次は人間の操作待ち)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **下の A か B かで変わる。選ぶのは人間。**
A(RUNNER が G2-1 の見積りを出す)= 手順書(`infra/RUNPOD.md` §4・`plans/PLAN-032` §8.2)どおりに進める作業なので **Sonnet で足りると見る**(`Documents/10_CONTEXT_POLICY.md` §7 の表に RUNNER の行は無い。選ぶのは人間)/
B(PLANNER が PLAN-033 を起草する)= **Opus**(§7 の表の「設計判断、…事前登録の文言、…`CLAUDE.md` §8 の周辺」の行)

---

**冒頭で人間に確かめること**: 凍結 tag(案 `preregister-diag-sharpness`)と push を済ませたか。自分でも `git tag -l 'preregister-*'` と `git status` で確かめる(**tag があれば A、なければ B**。tag があるのに push していなければ、先に人間に伝える)。**最初の発言で、自分の役割と実モデル名と、上の推奨との一致・不一致を 1 行で述べること**(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(A か B のどちらか 1 つ)

### A. 人間が凍結 tag と push を済ませていた場合 → RUNNER: G2-1 の見積りを出す

`plans/PLAN-032` §8.2 と `infra/RUNPOD.md` §4 に従い、**人間が G2-1 を承認するための見積り**を出す: GPU 時間・pod の型・単価の上限・回す run の一覧(診断の 4 腕 = B・A 各 34,322 / B-d・A-d 各 17,124 = 102,892 件。H2-7 の I5 = パイロットのアダプタ 10 本を含むか)。**承認が出るまで pod を起動しない**(`CLAUDE.md` §2: 10 GPU 時間超は人間の承認)。承認後は §8.2 のとおり: pod へ tag を含めて渡す(`git bundle create ft.bundle main preregister-diag-sharpness` → pod で tag を checkout)・**tag の commit のまま**診断のプールを作って 4 腕を続けて回す・**I5 は 4 腕の後**(I5 の config の入った commit を checkout。プールの作り直しで追跡ファイルの manifest が動くので、4 腕の前にやらない)・**使い終わった pod は止める**(`CLAUDE.md` §9。時計で見張る: メモリ「pod は時計で見張る」・「RunPod ssh は IPQoS=none」)。**RunPod MCP を有効にするのはこの A だけ**。

**新しい門が効く**(ADR-110 決定1): `sharpness:` 欄のある config は、追跡ファイルに差分があると **run dir を作る前・重みを読む前に止まる**。pod では追跡外のファイルがあっても `git diff HEAD` は空のはずだが、**止まったら出力(長さと先頭 400 文字)を読む**。パイロット用プールの作り直しで manifest が動いたときは `git checkout -- data/generated`(`infra/RUNPOD.md`)。

### B. まだ済んでいない場合 → PLANNER: PLAN-033(段3)の草案

`plans/PLAN-033-*.md` を `plans/TEMPLATE.md` の形で起草する(**決定 0 件・人間のレビュー待ちの草案**)。範囲は `grep -n 'PLAN-033' logs/DECISIONS.md`(ADR-097 決定6・R-2 と ADR-098 の該当箇所)と `plans/PLAN-030` §3 の段3: P-3 の文書修正 + `Documents/00_OVERVIEW.md:7` の問い(**文言は人間が決める**)+ 規約の案 A の反映 + `CLAUDE.md` を 200 行に戻す手当て。**この草案では `CLAUDE.md`・`Documents/` を書き換えない**(`CLAUDE.md` §4: PLAN → 人間のレビュー → 実装)。段2 が人間待ちで止まっている間に挟む作業である(`STATE.md`「次のアクション」の 3)。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-110 決定1・3 は実装済み・コミット済み**(`git log -1`)。`code/artifacts.py`(`capture_git_head_sha`・`capture_git_diff_head`・`is_capture_failure`)・`code/eval/run.py`(`declares_sharpness`・`check_tracked_files_clean`。`execute_threshold_sweep` の `prepare_run_dir` の前)・`code/analysis/sharpness_fit.py`(`read_analysis_provenance`・判定表の 2 番目の鍵 `analysis`・txt の 2 行目)とテスト(`test_sharpness_fit.py` 130 → 180 件)
- 検証(コードはその113 から 1 文字も変えていない): 全体の `pytest code/tests -q` = **2041 passed in 288.56s**(記録を書いた後にやり直した。その114 は 2041 passed)/ config 4 本の `--dry-run` = 102,892 件(不変。その115)/ 自己点検 = 変異 17 通りすべてで対応するテストが落ちた(その115。変異 p だけは assertion でなく fixture の setup の ERROR で検出された。「空の差分は通る」ことを専用に縛るテストが個別に落ちるかは見ていない)
- **実装の読み 26〜30 は `plans/PLAN-032` §11 の注(`★その115 の注`)にある。人間が凍結 tag の前に覆せる。**R2〜R5 の規則と値(線 0.088)・区間の計算法・§8.1 は不変
- 記録: `plans/PLAN-032`(ステータス `ADR-110 の実装済み・凍結 tag 待ち`・§10・§11 の表と注)・`logs/OPEN-ITEMS.md` の行 80・`STATE.md`・`logs/CHANGELOG.md`(その116)。旧ブロックは `logs/STATE-ARCHIVE.md`「その116」

## 触ってよいファイル / 読むべき範囲

- A: 読む = `plans/PLAN-032` §8・§8.2(`grep -n '^## 8\|^### 8' plans/PLAN-032-sharpness-diagnostic.md` → `sed -n`)/ `infra/RUNPOD.md` §4 / `logs/OPEN-ITEMS.md` の行 80(**8 KB の 1 行。`grep -n -o` か Python で必要な語だけ**)。書く = `runs/<id>/`・`logs/CHANGELOG.md`・`STATE.md`
- B: 読む = 上の `grep -n 'PLAN-033' logs/DECISIONS.md` と `plans/PLAN-030` §3・`plans/TEMPLATE.md`。書く = `plans/PLAN-033-*.md`(新規)・`logs/CHANGELOG.md`・`STATE.md`・`logs/OPEN-ITEMS.md`(人間のレビュー待ちの 1 行)
- **編集しない(A・B とも)**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / config・テンプレート / `code/`(コードを変える必要が出たら止めて人間に伝える)

## やってはいけないこと

- **tag を打たない・push しない**(人間の操作。ADR-110 決定4)。G2-1 の承認が出る前に pod を起動しない・GPU を使わない。**4 腕を tag の commit と違う commit で回さない**(ADR-110 決定2)。合否線・R2〜R5 の規則・区間の計算法を変えない。判定表の結果を解釈しない(読むのは人間。`plans/PLAN-032` §8.2)
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `python <script>`。Python に渡すパスは `C:/Users/...` の形)。**`.md` も `.py` も LF 固定**(`.gitattributes`)。Python で書くときは `newline="\n"`(またはバイトで書く)。**Edit ツールが `.py` を CRLF で書いたことがある**(その113)。`.py` を Edit したら CR が 0 であることを確かめる
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` の `until` ループ(または背景の実行の完了通知)。全体の pytest は約 5 分(`PYTHONIOENCODING=utf-8 python -X utf8 -m pytest code/tests -q -p no:cacheprovider > out.txt`)。**走っている間はリポジトリのファイルを書き換えない**(`test_repo_hygiene` が途中の状態を読む)
- `STATE.md` は上限に近い(約 380 行・60 KB 前後。回帰テストが落ちるのは 700 行 / 90 KB)。新しいブロックに ADR の中身を書き写さない(正本を指す)

## 未解決 / 人間の承認待ち

- **実装の読み 26〜30 の確認 → PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`)→ push(main と tag。GPU の前)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md` の行 80)。決定1・3 は統計の計算に触れないので CRITIC のレビューは要らないと ADR-110 決定8 は読んだ(**要るとするかは人間**)。気になれば tag の前に `git diff` を人間か CRITIC が見る
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
