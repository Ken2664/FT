# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その115)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **コンテキスト超過**(hook `context-guard` の実測 約 151k トークン。`CLAUDE.md` §10.2 の 100k 超の規定に従った)。**ADR-110 決定1・3 の実装の続きの途中で切った**
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 実装とテストと記録の書き込み(`Documents/10_CONTEXT_POLICY.md` §7 の表の「実装」の行)。統計の計算には触れない(止める条件と表示だけ)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。RunPod MCP は要らない(GPU は使わない)。

## このセッションでやること(1つだけ)

**ADR-110 決定1・3 の実装を仕上げる(コミットまで)。**コードとテストは**作業ツリーにある(未コミット)**。`git status` は 4 ファイルが ` M` になっているはず(`code/artifacts.py`・`code/eval/run.py`・`code/analysis/sharpness_fit.py`・`code/tests/test_sharpness_fit.py`)。**それを捨てずに続ける**(`git checkout` / `git stash` をしない)。仕様の正本は `logs/DECISIONS.md` の ADR-110(`grep -n '^## ADR-110' logs/DECISIONS.md`。本文は約 55 行)と `plans/PLAN-032` §8.1 R7(`grep -n 'R7 止める条件' plans/PLAN-032-sharpness-diagnostic.md`)。

### 検証の状況(その114・その115 が確かめた。**コードはその113 から 1 文字も変えていない**)

- `code/tests/test_sharpness_fit.py` = **180 passed**(75.56 秒)。全体の `pytest code/tests -q` = **2041 passed**(312.14 秒。1991 + 新 50。その114)
- **config 4 本の `--dry-run`(その115)= B・A 各 34,322 / B-d・A-d 各 17,124 = 102,892 件(不変)。**4 本とも exit 0(dirty な作業ツリーでも止まった件はない = 読み 26)
- **自己点検(その115)= 変異 17 通りすべてで対応するテストが落ちた。テストの穴 = 0。**`-k` の式で 58 件を選んだ(下の式)。変異は 4 ファイルのバイト列を退避し、置換前が**ちょうど 1 回**出ることを assert して置換し、必ず復元した。**復元後の `git diff HEAD` の sha256 = `6a44a735850ea8d18cd7f3531f5971ec35e105e06ef00e4b63c1d545759c80a6`(始める前と一致)**。変異の中身(名前): a 門の呼び出しを消す / b 門を `prepare_run_dir` の後へ / c1 `declares_sharpness` = True / c2 = False / d `main` の dry-run の前に門 / p 差分が空でも止める(`if not diff` → `if diff is None`)/ q 欄の無い run にも門 / e `capture_git_diff_head` を `git diff`(HEAD なし)に / f `write_git_sha` の patch を別の git 呼び出しに / g `is_capture_failure` = False / h `code_diff_empty` の向きを反転 / i `ANALYSIS_CODE_PATHS = ()` / j `build_report` が来歴を読まず固定値 / k `analysis` の鍵を dict の最後へ / l 差分が空でなければ `SharpnessError` / m `report_lines` から `analysis_line` を消す / n 欄名の食い違い(run 側 `sharpness_gate`・解析側 `sharpness`)。**変異 p だけは assertion の失敗ではなく fixture の setup の ERROR で検出された**(門が空の差分でも止めるので、クリーンな run を作る fixture が `ConfigError` で落ちた。空の差分は通るという専用のテストが個別に落ちるかは見ていない)。`-k`: `"tracked_diff or message_shows_the_size or stderr_alone or same_git_output or sharpness_field or dry_run_is_not_gated or cli_route or declares_sharpness or four_diag_arm or analysis_provenance"`
- **未実施**: `plans/PLAN-032` §11 の注 26〜30・表・ステータス・§10 の `[x]`(下の 1)/ `logs/OPEN-ITEMS.md` の追記(下の 2)/ 全体の pytest のやり直し(下の 3)/ コードのコミット(下の 5)

### 残りの手順(この順)

1. **`plans/PLAN-032` に書く**(**§8.1 は変えない**):
   - ヘッダのステータス(`ADR-110 の実装待ち` → **`実装済み・凍結 tag 待ち`**。既存の打ち消し線の並びに足す)と「最終更新」を `2026-09-26(その115)` に
   - §10 の `- [ ] ADR-110 決定1・3 の実装・…` を `[x]` にし、末尾に実測を書く(`pytest` = 2041 passed・dry-run 102,892 件・自己点検 17 通り。実装の読みは §11 の注 26〜30)
   - §11 の表(`| 2026-09-26(その112) | …` の行の直後)に 1 行: その113〜その115 = ADR-110 決定1・3 を `code/artifacts.py`(`capture_git_head_sha`・`capture_git_diff_head`・`is_capture_failure`)・`code/eval/run.py`(`declares_sharpness`・`check_tracked_files_clean`。`execute_threshold_sweep` の `prepare_run_dir` の前)・`code/analysis/sharpness_fit.py`(`read_analysis_provenance`・`build_report` の 2 番目の鍵 `analysis`・txt の 2 行目)とテスト(130 → 180 件)に実装した / `pytest` = 2041 passed / dry-run 102,892 件(不変)/ 自己点検 17 通り / **R2〜R5 の規則と値・線 0.088・区間の計算法は変えていない**。GPU 0・pod 0・tag なし・push なし。担当 IMPLEMENTER (Sonnet 5。推奨と一致)
   - 注(§11 の末尾。直前の「★その110 の注」の並びに) **「★その115 の注: ADR-110 の実装の読み(§8.1 と ADR-110 に定めが無い配線。人間が凍結 tag の前に覆せる)」**と 26〜30(下の「実装の読み」をそのまま写す)
2. **`logs/OPEN-ITEMS.md` の行 80** 末尾の `**→ ADR-110 の実装の後(その112)**` を `~~**→ ADR-110 の実装の後(その112)**~~ **→ いま(ADR-110 決定1・3 は実装済み。その115。凍結 tag = 人間)**` に置き換える(**行は 8 KB あるので出力しない**。Python で `count == 1` を assert して置換し、`newline` は LF)
3. **全体の `pytest code/tests -q`**(約 5 分。出力はファイルに落として `tail`。`PYTHONIOENCODING=utf-8 python -X utf8 -m pytest code/tests -q -p no:cacheprovider > out.txt`)。**期待 = 2041 passed**(コードは変わっていない)。記録(`STATE.md`・`plans/`)を書いた**後**に回す(`test_repo_hygiene` が読むため)。落ちたら切り分ける
4. `logs/CHANGELOG.md`(その115 の節を追記。**その114 の節の書き方が型**)・`STATE.md`(各節の最新 1 ブロック。**その115 の分は書いてある**ので、コミットの後の状態に合わせて直す。旧ブロックを `logs/STATE-ARCHIVE.md` へ移すなら 1 文字も変えず)・この `HANDOFF.md` を更新する
5. **コード・テスト・記録を 1 つのコミットにまとめる**(`feat(eval): ADR-110 決定1・3 を run.py と sharpness_fit に実装した —— ...`。件数は実測で書く。末尾に `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`)。`git status` で 4 ファイル + 記録だけが入ることを確かめる

### 実装の読み(定めが無い配線。§11 に 26〜30 として書く。**人間が tag の前に覆せる**)

- **26 `--dry-run` には門を掛けない**: 何も書かず重みも読まない。開発機の dirty な作業ツリーで dry-run が止まらないようにする(テスト = `test_the_dry_run_is_not_gated_and_does_not_read_git`。**その115 の dry-run 4 本が dirty な作業ツリーで通った**)
- **27 門の位置と範囲**: `execute_threshold_sweep` の中、宣言・プール・アダプタ・文面などの検査がすべて済んだ後(config の誤りが先に報告される)・`prepare_run_dir` の前。**固定オフセットの経路 `execute` には無い**(`sharpness:` 欄を持つのは診断の 4 腕の config だけで、実物の config を数えるテストがある)
- **28 「欄がある」の読み**: キーがあり null でない(`sharpness: {}` も宣言とみなして止める側に倒れる)。欄名は `run.SHARPNESS_KEY` 1 か所(`sharpness_fit.SHARPNESS_BLOCK` は別名)
- **29 共有関数**: 門が見る出力は `artifacts.capture_git_diff_head()`(`write_git_sha` が `git_diff.patch` に書くのと同じ関数)。`git status` が空で `git diff HEAD` だけ非空という組み合わせでは、patch は書かれないのに門は止まる(想定していない。止める側)
- **30 解析側の来歴の形**: `code_diff_empty` は `git diff HEAD -- code/` の出力が空なら True・**空でなければ False(git の警告も False)**・git を実行できなければ None。sha を取れなければ失敗の文言をそのまま出す。**run 側の sha との一致・不一致の印は出さない**(表示だけ。読み方は §8.2)。`code/` の下の追跡外のファイルは見ない(ADR-110 のリスクのとおり)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-110**(4 問とも人間が推奨を採った)と `plans/PLAN-032` §8.1 R7 の 4 行・§8.2 の 3 行はその112 のまま。**R2〜R5 の規則と値(線 0.088)・区間の計算法は不変**
- その115 が書いた記録(コミット済みにする): `STATE.md`(ヘッダ・いま何をしているか・次のアクション・引き継ぎ。旧文は `logs/STATE-ARCHIVE.md`「その115」)・`logs/CHANGELOG.md`(その115)・この `HANDOFF.md`。**コードは未コミットのまま**

## 触ってよいファイル / 読むべき範囲

- 書く: 上の 4 ファイル(**コードは変える必要がない**。テストの誤りが出たときだけ)/ `plans/PLAN-032`(ヘッダのステータス・§10・§11 の表と注。**§8.1 は変えない**)/ `logs/OPEN-ITEMS.md` の「PLAN-032 の凍結 tag と G2-1」行 / `STATE.md` / `logs/STATE-ARCHIVE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: `git diff HEAD --stat`(4 ファイル・+520 −15 のはず)/ `plans/PLAN-032` §10・§11(`grep -n '^## 10\|^## 11\|その110 の注' plans/PLAN-032-sharpness-diagnostic.md`。**その110 の注の形が型**)
- **編集しない**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / config・テンプレート / R2〜R5 の関数(`delta2_point`・`arm_reaches`・`next_stage`・`r5_decision`)と区間の計算法(`confidence_interval`)/ `check_provenance` の照合の中身(ADR-109 決定1)

## やってはいけないこと

- **tag を打たない・push しない・pod を起動しない・GPU を使わない**。合否線・R2〜R5 の規則・区間の計算法を変えない
- **作業ツリーの未コミットの変更を捨てない**(`git checkout -- .`・`git stash`・`git clean` をしない)。**全体の pytest が通る前にコードだけをコミットしない**(`CLAUDE.md` §4)
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `python <script>`。Python に渡すパスは `C:/Users/...` の形)。**`.md` も `.py` も LF 固定**(`.gitattributes`)。**Python で書くときは `newline="\n"`(またはバイトで書く)**。**Edit ツールが `.py` を CRLF で書いたことがある**(その113)。`.py` を Edit したら CR が 0 であることを確かめる(このセッションは `.py` を編集しない)
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` の `until` ループ
- `STATE.md` は上限に近い(その115 時点で 60,820 バイト・382 行。回帰テストが落ちるのは 700 行 / 90 KB)。新しいブロックに ADR の中身を書き写さない(正本を指す)
- **`logs/OPEN-ITEMS.md` の行 80 は 1 行が非常に長い**(8 KB)。`sed -n`・`grep` で出すとコンテキストを食う。`grep -n -o` で語だけ、または Python で `count` を assert して置換する

## 未解決 / 人間の承認待ち

- **ADR-110 の実装の仕上げ**(上)→ **PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`。人間)→ push(人間。main と tag。GPU の前)→ G2-1 GPU 承認(人間)**(`logs/OPEN-ITEMS.md` の行)。RUNNER は tag の commit のまま 4 腕を続けて回し、I5 はその後(`plans/PLAN-032` §8.2)
- **決定1・3 は統計の計算に触れない**ので ADR-101 決定5 の CRITIC のレビューは要らないと ADR-110 決定8 は読んだ(**要るとするかは人間**)。気になれば tag の前に `git diff` を人間か CRITIC が見る
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
