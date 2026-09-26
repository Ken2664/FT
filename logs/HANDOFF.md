# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その110)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(ADR-109 決定1・2 を実装し、`pytest` と dry-run を通した)。あわせてコンテキストガード(約 273k トークン)が handoff を求めた
直前セッションの実モデル: Claude Sonnet 5(推奨と一致)
**推奨モデル(次のセッション)**: **人間の選択による** —— 下の A なら **Opus**(CRITIC。`Documents/10_CONTEXT_POLICY.md` §7 の表の「CRITIC」の行)/ B なら **Sonnet**(RUNNER。手順を回すだけ)。**このセッションで次のエージェントがやることは、人間の操作(凍結 tag と G2-1 GPU 承認)を待ってからしか始まらない**

---

**最初の発言で、自分の実モデル名と、推奨モデルとの一致・不一致を 1 行で述べること**(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してください(`STATE.md` を全部読む・`tail -40 logs/CHANGELOG.md`・`tail -60 logs/DECISIONS.md`・`git log --oneline -20`・`git status && git worktree list`・`ls runs/ | tail -5`)。

## 状況(ファイルに書き込み済み)

**ADR-109 決定1・2 の実装は済んだ**(commit は `git log -1`)。`pytest code/tests -q` = **1991 passed**(その107 は 1958。`test_sharpness_fit.py` は 97 → 130)/ config 4 本の `--dry-run` = **102,892 件**(不変)/ 自己点検 = 新しい照合をわざと外す変異 17 通りすべてで対応するテストが落ちた。**R2〜R5 の規則と値(線 0.088)・区間の計算法・`plans/PLAN-032` §8.1 は 1 文字も変えていない**。GPU 0・pod 0・tag なし。

- 決定1: `check_provenance`(`build_report` の中)。4 本の `git_sha.txt` の 1 行目(16 進 40 桁か 64 桁の sha)の一致と `git_diff.patch` が無いか 0 バイトを照合し、sha を判定表の先頭(json の最初の鍵 `commit_sha`・txt の最初の行)に出す。**`dirty:` の欄は見ない**
- 決定2: C108-2 = シナリオ `split_t3_b_reaches` / C108-3 = `check_pair_differences`(組ごとの差の数 = `n_per_level`・平均 = 点推定) / C108-4 = 例外の型の残り
- **実装の読み 18〜25(`plans/PLAN-032` §11 の注。人間が tag の前に覆せる)**。とくに **18**(sha の書式を見る。git の失敗の文言が 4 本そろっても一致と読まない)と **22**(0 本の glob で実際に出るのは `IndexError` でなく `AggregateError`。CRITIC の指摘の型が違っていた)

## 次にやること(人間が選ぶ。エージェントは選ばない)

**A. CRITIC が diff を見る(任意。ADR-109 決定4 は「要らないと読む」。要るとするかは人間)**: `git diff 76402e1 -- code/analysis/sharpness_fit.py` の `check_provenance`(決定1)と `check_pair_differences`(C108-3。区間の前提の検査)を §8.1 R6・R7 と突き合わせ、`logs/CRITIQUE.md` に「その111」を追記する(コードは直さない。**最低 3 つは疑わしい点を挙げる**)。

**B. 人間が凍結 tag を打ち、G2-1 GPU 承認を出した後に RUNNER が回す**: 案 `preregister-diag-sharpness`(`plans/PLAN-032` §8.1 の R1〜R9 と実装の入った commit。§8.2)。**RUNNER が回すのは 4 腕を同じ commit で続けて**(決定1 の代価 = 途中でコードを直すと 4 腕とも回し直し)。プールはポッドで `configs/exp_diag_pool.yaml` から作り直す(`python -m code.data_gen.sweep_pool --config configs/exp_diag_pool.yaml --arm diag`)。手順は `infra/RUNPOD.md` §4。**I5 とパイロットのアダプタ 10 本の T1b・T3 は tag の後だけ**(ADR-099 決定5・罠1)。判定表は `python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`(**機械的。解釈はしない**)。

**人間が tag も G2-1 も出していないなら、エージェントが勝手に進めない**(tag を打たない・pod を起動しない・GPU を使わない)。その場合は人間に「A をやるか・tag を打つか」を推奨つきで聞く(memory「Recommend before choice」)。

## 触ってよいファイル / 編集しない

- A: 書く = `logs/CRITIQUE.md`(追記のみ)/ `STATE.md`・`logs/STATE-ARCHIVE.md`・`logs/CHANGELOG.md`・`logs/HANDOFF.md`。**編集しない = コード・config・テスト・`plans/PLAN-032`・`logs/DECISIONS.md`**
- B: 書く = `runs/`・`results/diag_sharpness/`(判定表)・`logs/`。**config は編集しない**(問題があれば IMPLEMENTER に差し戻す)

## やってはいけないこと

- **tag は人間が打つ。エージェントは打たない**。合否線・R2〜R5 の規則・区間の計算法を変えない。10 GPU 時間超のジョブを人間の承認なく起動しない。RunPod のポッドを起動したまま放置しない(B の場合は `date -u` で時計を確かめる。memory「pod は時計で見張る」)
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから実行。Python に渡すパスは `C:/Users/...` の形)。**`.md` は LF 固定**(`.gitattributes`。`test_repo_hygiene.py` が CR を落とす)。**Python の `open(..., "w")` は Windows で CRLF を書くので `newline="\n"` を付ける**(`write_bytes(text.encode())` でもよい)
- テストのモジュールを scratchpad から import するときは `PYTHONPATH=C:/Users/keenk/paper/FT/infra` が要る

## 未解決 / 人間の承認待ち

- **実装の読み 18〜25 の確認 → 凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md`「PLAN-032 の凍結 tag と G2-1」の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
