# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その114)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **コンテキスト超過**(hook `context-guard` の実測 約 140k トークン。`CLAUDE.md` §10.2 の 100k 超の規定に従った)。**ADR-110 決定1・3 の実装の続きの途中で切った**
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 実装とテスト(`Documents/10_CONTEXT_POLICY.md` §7 の表の「実装」の行)。統計の計算には触れない(止める条件と表示だけ)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。RunPod MCP は要らない(GPU は使わない)。

## このセッションでやること(1つだけ)

**ADR-110 決定1・3 の実装を仕上げる。**コードとテストは**作業ツリーにある(未コミット)**。`git status` は 4 ファイルが ` M` になっているはず(`code/artifacts.py`・`code/eval/run.py`・`code/analysis/sharpness_fit.py`・`code/tests/test_sharpness_fit.py`)。**それを捨てずに続ける**(`git checkout` / `git stash` をしない)。仕様の正本は `logs/DECISIONS.md` の ADR-110 と `plans/PLAN-032` §8.1 R7(`grep -n 'R7 止める条件' plans/PLAN-032-sharpness-diagnostic.md`)。

### 検証の状況(その114 が確かめた。**コードはその113 から 1 文字も変えていない**)

- `code/tests/test_sharpness_fit.py` = **180 passed**(75.56 秒。`PYTHONIOENCODING=utf-8 python -X utf8 -m pytest code/tests/test_sharpness_fit.py -q -p no:cacheprovider`)。**新テスト 50 件は初回で全部通った**(テスト側の誤りは出なかった)。ただし**通ったこと自体は、新しい門・表示が効いていることの証拠ではない**(下の自己点検で、わざと外して落ちることを確かめる)
- 全体の `pytest code/tests -q`: **2041 passed**(312.14 秒。期待どおり 1991 + 50。走らせている間、作業ツリーのコードは変えていない)
- 3 本の `.py` とテストの CR = 0(LF)。`git diff HEAD --stat` = 4 ファイル・+520 −15。`git diff HEAD` をその113 の記述(下の 1〜4)と突き合わせて読んだ(一致)
- **未実施**: config 4 本の `--dry-run`・自己点検・`plans/PLAN-032` §11 の注 26〜30・`logs/OPEN-ITEMS.md` の追記・コミット

### 作業ツリーにあるもの(その113 が書いた)

1. **`code/artifacts.py`**: 公開関数 `capture_git_head_sha()`・`capture_git_diff_head(paths=())`(= `_capture(["git","diff","HEAD"[, "--", *paths]])`)・`is_capture_failure(output)` と定数 `CAPTURE_FAILURE_PREFIX = "<取得できず"` を足した。`write_git_sha` はこれらを通す(**出力は 1 バイトも変わらない**。`git_diff.patch` に書くものと門が見るものが同じ関数になる)
2. **`code/eval/run.py`**: `SHARPNESS_KEY = "sharpness"`・`GIT_DIFF_PREVIEW_CHARS = 400`・`declares_sharpness(config)`(欄が無い / null = していない)・`check_tracked_files_clean(config, *, git_diff=capture_git_diff_head)`(決定1 の門。空でなければ `ConfigError`)。`execute_threshold_sweep` に `git_diff` 引数を足し、**`top_k = declared_top_k(config)` の後・`started = ...` / `prepare_run_dir` の前**で呼ぶ
3. **`code/analysis/sharpness_fit.py`**: `SHARPNESS_BLOCK = SHARPNESS_KEY`(`run.py` の定数の別名)・`ANALYSIS_CODE_PATHS = ("code/",)`・`ANALYSIS_NOTE`・`read_analysis_provenance()`(`{"commit_sha", "code_diff_empty": True/False/None}`)・`build_report(..., *, analysis=None)`(json の **2 番目の鍵** `analysis` = 上の 2 つ + `note`)・`analysis_line`(txt の **2 行目**)。**止めない**
4. **`code/tests/test_sharpness_fit.py`**(130 → 180 件): 節「R7 の 4 を GPU の前にも(ADR-110 決定1)」(1464 行〜)と「解析側の来歴(ADR-110 決定3)」(1667 行〜)が新規 50 件。**場所は `grep -n 'R7 の 4 を GPU の前にも\|解析側の来歴' code/tests/test_sharpness_fit.py`**(全文を読まない)

### 残りの手順(この順)

1. **(済み)全体の `pytest code/tests -q` = 2041 passed**(上の行)。**自己点検の変異を復元した後・§11 の注を書いた後、コミットの前にもう一度回す**(約 5 分・出力はファイルに落として `tail`)。落ちたらまず**テスト側・新コード側のどちらの誤りか**を切り分ける
2. config 4 本(`configs/exp_diag_{b,a,b_d,a_d}.yaml`)の `--dry-run`(**102,892 件のはず。不変**。診断のプールが無ければ `configs/exp_diag_pool.yaml` の冒頭のコマンド。前の記録は `logs/CHANGELOG.md`「その110」)。`--dry-run` は門を通らない(読み 26)ので、dirty な作業ツリーでも止まらないはず
3. **自己点検**(`CLAUDE.md` §7): 新しい門・表示をわざと外して、対応するテストが落ちることを確かめてから戻す。**やり方**: scratchpad にスクリプトを書き、変異ごとに ファイルのバイト列を退避 → 置換(**出現がちょうど 1 回**であることを assert)→ pytest(`-x -q -p no:cacheprovider -k "<下>"`)→ 復元。**始める前と終わった後の `git diff HEAD` の sha256 が同じ**であることを確かめる(作業ツリーは未コミットなので、復元を誤ると仕事が消える)。**`-k` の案**(`--collect-only -q` で ~50 件選ばれることを先に確かめる): `"tracked_diff or message_shows_the_size or stderr_alone or same_git_output or sharpness_field or dry_run_is_not_gated or cli_route or declares_sharpness or four_diag_arm or analysis_provenance"`。**変異の案**(どれも落ちるはず。落ちなければテストの穴):
   - `run.py`: (a) 門の呼び出し `check_tracked_files_clean(config, git_diff=git_diff)` を消す (b) 門を `prepare_run_dir` の後へ動かす (c) `declares_sharpness` を `return True` / `return False` にする (d) `main` の `if args.dry_run:` の前に `check_tracked_files_clean(config)` を足す
   - `artifacts.py`: (e) `capture_git_diff_head` の `command = ["git", "diff", "HEAD"]` を `["git", "diff"]` に (f) `write_git_sha` の `capture_git_diff_head()` を `_capture(["git", "diff"])` に (g) `is_capture_failure` を `return False` に
   - `sharpness_fit.py`: (h) `read_analysis_provenance` の `diff == ""` を `diff != ""` に (i) `ANALYSIS_CODE_PATHS` を `()` に (j) `build_report` の `read_analysis_provenance()` を固定の dict に置き換える(読まない) (k) `analysis` の鍵を dict の最後へ動かす (l) `read_analysis_provenance` で差分が空でなければ `SharpnessError` を投げる(止める) (m) `report_lines` から `analysis_line(...)` の行を消す
   - **2 ファイルにまたがる**: (n) `run.py` の `SHARPNESS_KEY` を `"sharpness_gate"` に変え、同時に `sharpness_fit.py` の `SHARPNESS_BLOCK = SHARPNESS_KEY` を `"sharpness"` にする(欄名が食い違って門が黙って外れる。`test_declares_sharpness_reads_the_field_the_judgment_table_reads` が落ちるはず)
4. **`plans/PLAN-032` §11 の注に「実装の読み 26〜30」を書く**(下)。ヘッダのステータス(`ADR-110 の実装待ち` → 実装済み・凍結 tag 待ち)・§10 の `[ ] ADR-110 決定1・3 の実装…` を `[x]` に・§11 の表に 1 行(その113・その114 の分)。`logs/OPEN-ITEMS.md` の行 80「PLAN-032 の凍結 tag と G2-1 GPU 承認」の末尾に追記(**§8.1 は変えない**。行は巨大なので `grep -n` で場所を引き、Edit で末尾の `→ ADR-110 の実装の後(その112)` の手前に足す)
5. `logs/CHANGELOG.md`・`STATE.md`(各節の最新 1 ブロックのみ。旧ブロックは `logs/STATE-ARCHIVE.md` へ 1 文字も変えずに移す)・この `HANDOFF.md` を更新し、**コード・テスト・記録を 1 つのコミットにまとめる**(`feat(eval): ADR-110 決定1・3 を run.py と sharpness_fit に実装した —— ...`。`pytest code/tests -q` が通ってから。件数は実測で書く)

### 実装の読み(定めが無い配線。§11 に 26〜30 として書く。**人間が tag の前に覆せる**)

- **26 `--dry-run` には門を掛けない**: 何も書かず重みも読まない。開発機の dirty な作業ツリーで dry-run が止まらないようにする(テスト = `test_the_dry_run_is_not_gated_and_does_not_read_git`)
- **27 門の位置と範囲**: `execute_threshold_sweep` の中、宣言・プール・アダプタ・文面などの検査がすべて済んだ後(config の誤りが先に報告される)・`prepare_run_dir` の前。**固定オフセットの経路 `execute` には無い**(`sharpness:` 欄を持つのは診断の 4 腕の config だけで、実物の config を数えるテストがある)
- **28 「欄がある」の読み**: キーがあり null でない(`sharpness: {}` も宣言とみなして止める側に倒れる)。欄名は `run.SHARPNESS_KEY` 1 か所(`sharpness_fit.SHARPNESS_BLOCK` は別名)
- **29 共有関数**: 門が見る出力は `artifacts.capture_git_diff_head()`(`write_git_sha` が `git_diff.patch` に書くのと同じ関数)。`git status` が空で `git diff HEAD` だけ非空という組み合わせでは、patch は書かれないのに門は止まる(想定していない。止める側)
- **30 解析側の来歴の形**: `code_diff_empty` は `git diff HEAD -- code/` の出力が空なら True・**空でなければ False(git の警告も False)**・git を実行できなければ None。sha を取れなければ失敗の文言をそのまま出す。**run 側の sha との一致・不一致の印は出さない**(表示だけ。読み方は §8.2)。`code/` の下の追跡外のファイルは見ない(ADR-110 のリスクのとおり)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-110**(4 問とも人間が推奨を採った)と `plans/PLAN-032` §8.1 R7 の 4 行・§8.2 の 3 行はその112 のまま。**R2〜R5 の規則と値(線 0.088)・区間の計算法は不変**
- その114 が書いた記録(コミット済み): `STATE.md`(ヘッダ・いま何をしているか・次のアクション・引き継ぎ。旧文は `logs/STATE-ARCHIVE.md`「その114」)・`logs/CHANGELOG.md`(その114)・この `HANDOFF.md`。**コードは未コミットのまま**

## 触ってよいファイル / 読むべき範囲

- 書く: 上の 4 ファイル / `plans/PLAN-032`(ヘッダのステータス・§10・§11 の表と注。**§8.1 は変えない**)/ `logs/OPEN-ITEMS.md` の「PLAN-032 の凍結 tag と G2-1」行 / `STATE.md` / `logs/STATE-ARCHIVE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: `git diff HEAD --stat` と、必要なら `git diff HEAD -- code/artifacts.py code/eval/run.py code/analysis/sharpness_fit.py`(小さい)/ ADR-110(`grep -n '^## ADR-110' logs/DECISIONS.md`。**本文は約 55 行。全文を読むほどではない**)/ `logs/CRITIQUE.md`「その111」の C111-1・C111-3
- **編集しない**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / config・テンプレート / R2〜R5 の関数(`delta2_point`・`arm_reaches`・`next_stage`・`r5_decision`)と区間の計算法(`confidence_interval`)/ `check_provenance` の照合の中身(ADR-109 決定1)

## やってはいけないこと

- **tag を打たない・push しない・pod を起動しない・GPU を使わない**。合否線・R2〜R5 の規則・区間の計算法を変えない
- **作業ツリーの未コミットの変更を捨てない**(`git checkout -- .`・`git stash`・`git clean` をしない)。**全体の pytest が通る前(と、通した後にコードを触ったならもう一度通す前)にコードだけをコミットしない**(`CLAUDE.md` §4)。自己点検の変異は必ず復元し、`git diff HEAD` の sha256 で確かめる
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `python <script>`。Python に渡すパスは `C:/Users/...` の形)。**`.md` も `.py` も LF 固定**(`.gitattributes`)。**Python で書くときは `newline="\n"`(またはバイトで書く)**。**★Edit ツールが `code/artifacts.py` を CRLF で書いたことがある**(その113 が見つけて LF に戻した)。**`.py` を Edit したら `python -X utf8 -c "print(open(p,'rb').read().count(b'\r\n'))"` で CR が 0 であることを確かめる**
- テストのモジュールを scratchpad から import するときは `PYTHONPATH=C:/Users/keenk/paper/FT/infra` が要る
- `STATE.md` は 60 KB の上限に近い(その114 時点で約 60 KB)。新しいブロックに ADR の中身を書き写さない(正本を指す)。超えたらアーカイブへ移す
- **`logs/OPEN-ITEMS.md` の行 80 は 1 行が非常に長い**(数 KB)。`sed -n`・`grep` で出すとコンテキストを食う。`grep -n` は番号だけ(`-o` で語だけ)にする

## 未解決 / 人間の承認待ち

- **ADR-110 の実装の仕上げ**(上)→ **PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`。人間)→ push(人間。main と tag。GPU の前)→ G2-1 GPU 承認(人間)**(`logs/OPEN-ITEMS.md` の行)。RUNNER は tag の commit のまま 4 腕を続けて回し、I5 はその後(`plans/PLAN-032` §8.2)
- **決定1・3 は統計の計算に触れない**ので ADR-101 決定5 の CRITIC のレビューは要らないと ADR-110 決定8 は読んだ(**要るとするかは人間**)。気になれば tag の前に `git diff` を人間か CRITIC が見る
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
