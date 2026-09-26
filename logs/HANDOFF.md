# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その111)/ 直前セッションの役割: CRITIC
直前セッションが終了した理由: **レビューの 1 区切りが完了した**(凍結 tag が固める `ef582f1` の中身を突き合わせ、`logs/CRITIQUE.md`「その111」に C111-1〜6 を書いた)
直前セッションの実モデル: Claude Opus 5.5(推奨と一致)
**推奨モデル(次のセッション)**: **Opus**(PLANNER。C111-1〜6 を人間に諮り ADR にする = 設計判断。`Documents/10_CONTEXT_POLICY.md` §7 の表)。人間が「指摘は採らずに tag を打つ」と決めた後なら、次は RUNNER(Sonnet)

---

**最初の発言で、自分の実モデル名と、推奨モデルとの一致・不一致を 1 行で述べること**(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してください(`STATE.md` を全部読む・`tail -40 logs/CHANGELOG.md`・`tail -60 logs/DECISIONS.md`・`git log --oneline -20`・`git status && git worktree list`・`ls runs/ | tail -5`)。

## 状況(ファイルに書き込み済み)

**CRITIC(その111)は tag を止める誤りを見つけなかった**(§8.1 は ADR-109 の `c81b288` の後で不変・R2〜R5 の関数と区間の計算法は diff で不変・判定の値を変える経路は増えていない)。指摘は `logs/CRITIQUE.md`「その111」:

- **C111-1(中)**: R7 の 4(`git_diff.patch` が 0 バイトでなければ止める)は GPU の後にしか効かない。preflight の `check_git_clean` は WARN で、追跡外と追跡ファイルの差分を区別しない。I5 のためにパイロット用プールを作り直すと追跡ファイルの manifest 5 本が動く(scratchpad の clone で `git diff HEAD` 3,380 バイトを再現)。推奨 (a) = `run.py` で `sharpness:` 欄のある run は、重みを読む前に `git diff HEAD` が空でなければ止める(IMPLEMENTER)
- **C111-2(中)**: 「判定表の先頭の sha を tag の commit と見比べる」の基準が無い。順6b は tag `e714f8a`・run `b5838c0`。推奨 (a) = 4 腕は tag の commit そのもので回す(+ 予備に「祖先 + `code/`・`configs/`・`data/generated/`・`infra/` の差分なし」の文面)
- **C111-3(中)**: 判定表の sha は run 側で、解析コードの commit が残らない。推奨 (a) = 解析側の sha と `git diff HEAD -- code/` の空を表示だけ(IMPLEMENTER)
- **C111-4(低〜中)**: `preregister-*` の tag が `origin` に 1 つも無い(remote は `main` = `6bcddca` だけ)。推奨 (a) = GPU の前に main と tag を push(**人間が打つ**)
- **C111-5(低)**: 追跡外の config は R7 の 3・4 を通る(表に値は出る)。推奨 (c) = 何もしない
- **C111-6(低)**: 同じ腕に完了した run が 2 本あるときの選び方が無い。推奨 (a) = 「最初に完了した run を使い、ほかは注に並べる」の 1 行

## 次にやること(人間が選ぶ。エージェントは選ばない)

**A. PLANNER が C111-1〜6 を人間に諮り ADR-110 にする(推奨)**: 選択肢・推奨・理由をチャットで先に示してから `AskUserQuestion`(memory「Recommend before choice」。ADR-108・109 と同じ形)。採った規則の文面は §8.1 R7 の注か RUNNER の手順に(**tag の前なので直せる**。R2〜R5 の規則と値は触らない)。コードが要るもの(C111-1・C111-3)は次の IMPLEMENTER。

**B. 人間が指摘を採らずに凍結 tag を打つ**: その場合も **C111-1 の (c)(RUNNER は各腕の直前に `git status --porcelain --untracked-files=no` が空であることを確かめ、I5 のプールの作り直しの後は `git checkout -- data/generated`)を RUNNER に渡すのが最低限**。

**人間が決めていないなら、エージェントが勝手に進めない**(tag を打たない・push しない・pod を起動しない・GPU を使わない)。

## 触ってよいファイル / 編集しない

- A(PLANNER): 書く = `logs/DECISIONS.md`(追記)・`plans/PLAN-032`(§8.1 R7 の注・§10・§11。**R2〜R5 は変えない**)・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/STATE-ARCHIVE.md`・`logs/CHANGELOG.md`・`logs/HANDOFF.md`。**編集しない = コード・config・テスト**(IMPLEMENTER)・`logs/CRITIQUE.md`
- B(RUNNER): 書く = `runs/`・`results/diag_sharpness/`・`logs/`。**config は編集しない**

## やってはいけないこと

- **tag と push は人間が打つ。エージェントは打たない**。合否線・R2〜R5 の規則・区間の計算法を変えない。10 GPU 時間超のジョブを人間の承認なく起動しない。RunPod のポッドを起動したまま放置しない(`date -u` で時計を確かめる。memory「pod は時計で見張る」)
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから実行。Python に渡すパスは `C:/Users/...` の形)。**`.md` は LF 固定**(`.gitattributes`)。**Python で書くときは `newline="\n"` か `write_bytes`**
- テストのモジュールを scratchpad から import するときは `PYTHONPATH=C:/Users/keenk/paper/FT/infra` が要る
- 生成を再現するなら **scratchpad に `git clone` して**その中で回す(repo の作業ツリーの `data/generated/` の追跡ファイルを動かさない)

## 未解決 / 人間の承認待ち

- **C111-1〜6 の採否 →(採れば IMPLEMENTER)→ 凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md`「PLAN-032 の凍結 tag と G2-1」の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
