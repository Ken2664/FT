# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その117)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: **成果物の区切り**(G2-1 の見積りを出した。次は人間の承認・GPU の在庫・I5 の config が要る)+ コンテキスト(大きな出力を何度も流した)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **下の A か B かで変わる。選ぶのは人間。**
A(RUNNER が Phase 1 を回す)= 手順書(`infra/RUNPOD.md` §3・§4・`plans/PLAN-032` §8.2)どおりに進める作業なので **Sonnet で足りると見る**(`Documents/10_CONTEXT_POLICY.md` §7 の表に RUNNER の行は無い。選ぶのは人間)/
B(IMPLEMENTER が I5 の config 10 本を作る)= **Sonnet**(§7 の表の「実装・集計」の行)

---

**冒頭で人間に確かめること**: ① G2-1 を承認したか(**上限・Phase の分け方・GPU をどうしたか**。`logs/CHANGELOG.md` の「その117」に見積りと推奨がある)② RTX 4090 SECURE の在庫が戻ったか(自分でも `mcp__plugin_runpod_runpod__get-gpu-type` を `include: ["AVAILABILITY"]`・`product: ["POD"]`・`cloud: SECURE`・`countryCodes: ["RO"]` で読む。**承認が無ければ pod を作らない**)③ I5 の config 10 本が push 済みか(`ls configs | grep -c pilot_ft_eval` が 10 のままなら未了。新しい config の名前は IMPLEMENTER が決める)。**最初の発言で、自分の役割と実モデル名と、上の推奨との一致・不一致を 1 行で述べること**(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(A か B のどちらか 1 つ)

### A. 人間が G2-1 を承認し、RTX 4090 の在庫が戻っていた場合 → RUNNER: Phase 1(4 腕)を回す

`logs/CHANGELOG.md`「その117」の見積り・上限と `plans/PLAN-032` §8.2・`infra/RUNPOD.md` §3・§4 に従う。**起動の直前に、人間へ pod の型・単価・停止時刻(`date -u`)を示して確かめる**(その97 と同じ)。**pod 上の手順の要点はその117 の CHANGELOG の最後の方にある**(bundle は `git bundle create ft.bundle main preregister-diag-sharpness` → `git checkout preregister-diag-sharpness` = **4 腕は tag の commit のまま**・ボリュームに `HF_HOME`・venv・HF トークンが残っている・診断のプールを作った後に `git diff HEAD` が空か確かめ、動いていれば `git checkout -- data/generated`・run ごとに preflight → run)。連鎖のひな形 = `runs/pilot_ft_chain_n313/{chain.sh,run_step.sh}`。**回収は `ssh -o IPQoS=none`**(約 174 MB)。**時計で見張る**(メモリ「pod は時計で見張る」。背景ポーリングの通知に頼らない)。**終わったら pod を止め、`runs/<id>/cost.txt` を書く**(`infra/RUNPOD.md` §7 のチェックリストを完了報告に含める)。判定表は `python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`(**機械的。読むのは人間**)。

- **Phase 2(I5)は、I5 の config 10 本が push 済みで、同じ承認の枠の中のときだけ**続ける(**4 腕の後**。I5 の config の入った commit を checkout。プールの作り直しで manifest が動くので `git checkout -- data/generated`)。無ければ pod を止めて人間に伝える(遊休させない)
- **承認の上限を超えそうになったら止める**(提案の上限 = 合計 4.0 h・$0.74/時。人間が決めた値に従う)

### B. まだ承認も在庫も無く、I5 の config が先の場合 → IMPLEMENTER: I5 の config 10 本を作る(GPU 0)

`plans/PLAN-032` §5 の I5 と §8.1 R8 に従い、`configs/exp_pilot_ft_eval_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}{,_n313}.yaml`(10 本)の写しで、**`eval.batteries: [comparison]`・`eval.task_subset: [t1b, t3]`・`experiment.id`・(必要なら `gonogo.*`)だけを変えた 10 本**を作る。`model.adapter` は元の config と同じ。**4 値分解は参照規則 `p2`・`p2d`**(R8)。`--dry-run` の件数(1 本 = 640 件の見込みと比べる)と data_checks を報告し、`pytest code/tests -q` を通す。**tag の commit(`102c2d5`)は動かさない**(新しい commit を上に足す)。**push は人間**。skill `code-style` を読む

## 直前セッションで確定したこと(ファイルに書き込み済み)

- 凍結 tag `preregister-diag-sharpness` = `102c2d5` = HEAD = `origin/main`(人間が打って push 済み。その117 で `git ls-remote origin` により確認)。作業ツリー clean
- config 4 本の `--dry-run`(tag の commit)= 34,322 / 34,322 / 17,124 / 17,124 = 102,892 件(不変)
- **G2-1 の見積り**(`logs/CHANGELOG.md` その117): Phase 1 約 1.05 h・Phase 2(I5)約 1.5 h・合計 約 2.6 h(高め 約 3.1 h)・$0.74/時で約 $1.9(高め $2.3)。**10 GPU 時間の線の外**。提案の上限 4.0 h・$2.96。根拠は過去の実測([run:20260922_122247_order6b_r8] の生成 0.0073 s/件・preflight 4:58〜5:34/run・pod 準備 326 s ほか)。**診断のプール作りと I5 の 1 本の時間は未実測**(見込み)
- **RTX 4090 SECURE は EU-RO-1 で 2026-09-26 の読みでは在庫なし**(`get-gpu-type`(RO)= NONE・`get-capacity` = Out。国の指定なしは LOW で食い違った)。ボリューム `r963j7swke`(EU-RO-1・50 GB)にアダプタ 10 本の重みがある。既存の 3 本の pod は `EXITED`(触っていない)

## 触ってよいファイル / 読むべき範囲

- A: 読む = `logs/CHANGELOG.md` の「その117」(`grep -n 'その117' logs/CHANGELOG.md` → `sed -n`)/ `plans/PLAN-032` §8.2(`sed -n '379,388p'`)/ `infra/RUNPOD.md` §3・§4・§7 / `runs/pilot_ft_chain_n313/{chain.sh,run_step.sh}`。書く = `runs/<id>/`・`logs/CHANGELOG.md`・`STATE.md`
- B: 読む = `plans/PLAN-032` §5・§8.1 R8(`sed -n '370,374p'`)/ `configs/exp_pilot_ft_eval_p2_s0_n313.yaml`(冒頭の注記と `eval.*`)。書く = `configs/`(新規 10 本)・`code/tests/`(必要なら)・`logs/CHANGELOG.md`・`STATE.md`
- **編集しない(A・B とも)**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / `configs/exp_diag_*.yaml`(tag の commit の config。書き換えると 4 腕が tag の commit と違う commit になる)/ テンプレート / `code/`(B でコードを変える必要が出たら止めて人間に伝える)

## やってはいけないこと

- **tag を打たない・push しない**(人間の操作)。**承認が出る前に pod を作らない・起動しない**。**4 腕を tag の commit と違う commit で回さない**(ADR-110 決定2)。合否線・R2〜R5 の規則・区間の計算法を変えない。判定表の結果を解釈しない(読むのは人間)
- **RunPod の pod は「自分の呼び出しで作ったもの」だけを止める・消す**(RunPod MCP の規約)。既存の `EXITED` の 3 本の terminate は人間。start は人間の許可を取る
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `python <script>`)。**`.md` も `.py` も LF 固定**(`.gitattributes`)。Python で書くときは `newline="\n"`(またはバイトで書く)。**Edit ツールが `.py` を CRLF で書いたことがある**(その113)→ `.py` を Edit したら CR が 0 であることを確かめる
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` の `until` ループ。`/usr/bin/time` は無い(シェルの `time` か `date +%s` の差)
- `STATE.md` は上限に近い(約 385 行・60 KB 前後。回帰テストが落ちるのは 700 行 / 90 KB)。新しいブロックに ADR の中身を書き写さない(正本を指す)

## 未解決 / 人間の承認待ち

- **G2-1 GPU 承認**(上限・Phase の分け方・GPU。`logs/CHANGELOG.md` その117 の「人間に決めてほしいこと」に推奨つきで 3 件)→ 実行
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
