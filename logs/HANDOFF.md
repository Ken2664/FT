# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その118)/ 直前セッションの役割: IMPLEMENTER(冒頭は RUNNER/IMPLEMENTER の切り替えを在庫で決めた。在庫なし → B)
直前セッションが終了した理由: **成果物の区切り**(I5 の config 10 本ができた。次は人間の push・GPU の在庫・G2-1 の最終確認)+ コンテキスト(context-guard が約 249k トークンで警告)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — RUNNER が手順書(`infra/RUNPOD.md` §3・§4・`plans/PLAN-032` §8.2)どおりに回す作業。`Documents/10_CONTEXT_POLICY.md` §7 の表に RUNNER の行は無い(その117 の HANDOFF と同じ読み)。**選ぶのは人間**

---

**冒頭で人間に確かめること**: ① **その118 の commit(I5 の config 10 本)を push したか**(`git ls-remote origin refs/heads/main` が `git rev-parse HEAD` と同じか。**Phase 2 の前に要る**)② **RTX 4090 SECURE の在庫**(自分でも `mcp__plugin_runpod_runpod__get-gpu-type` を `include: ["AVAILABILITY"]`・`product: ["POD"]`・`cloud: SECURE`・`countryCodes: ["RO"]` で読む。その118 の読みは NONE / Out)③ **G2-1 の最終確認**: その118 は人間のチャット(「handoffを読んで作業を続けてください。手順については推奨に従います」)を、その117 の推奨 3 件(1 枠 4.0 h・$0.74/時まで・在庫待ち・IMPLEMENTER 先)を採る意味に読んだ。**これを G2-1 の承認と読んでよいかは起動の直前に、pod の型・単価・停止時刻(`date -u`)を示して人間に確かめる。確認が無ければ pod を作らない**。**最初の発言で、自分の役割と実モデル名と、上の推奨との一致・不一致を 1 行で述べること**(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(A か待機のどちらか 1 つ)

### A. ①〜③ がそろった場合 → RUNNER: Phase 1(4 腕)→ Phase 2(I5 の 10 本)を回す

`logs/CHANGELOG.md` の「その117」(見積り・上限・pod 上の手順の要点)と「その118」(I5 の config と件数の訂正)、`plans/PLAN-032` §8.2、`infra/RUNPOD.md` §3・§4 に従う。**連鎖のひな形 = `runs/pilot_ft_chain_n313/{chain.sh,run_step.sh}`**。

- **Phase 1(4 腕。tag の commit のまま)**: `git bundle create ft.bundle main preregister-diag-sharpness` → pod で `git checkout preregister-diag-sharpness`。診断のプールは `configs/exp_diag_pool.yaml` 冒頭のコマンドで作り、**作った後に `git diff HEAD` が空か確かめる**(動いていれば `git checkout -- data/generated`)。run ごとに preflight → run。判定表 = `python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`(**機械的。読むのは人間**)
- **Phase 2(I5。4 腕の後・同じ承認の枠の中・I5 の commit が push 済みのときだけ)**: I5 の commit(main)を checkout。パイロット用プールの作り直しは `configs/exp_order6b_pilot.yaml` 冒頭のコマンド(作った後に `git checkout -- data/generated`)。10 本 = `configs/exp_pilot_ft_cmp_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}{,_n313}.yaml`。**入口は config の冒頭に書いてある**: `python -m code.eval.run --config configs/exp_pilot_ft_cmp_<条件>_s<シード>[_n313].yaml --run-dir runs/pilot_ft_cmp_<条件>_s<シード>[_n313]`(run dir は `pilot_ft_eval_*` と分けてある)。**1 本 = 960 件**(`comparison` 640 + `comparison.ans_out` 320。dry-run で確かめた)。アダプタ(`runs/pilot_ft_train_*/adapter`)の重みはボリューム `r963j7swke` にある(その117 の記録)。**結果は探索的で R1〜R7 の見直しに使わない**(§8.1 R8)。I5 の解析の道具はまだ無い(`sharpness_fit` は 4 腕だけ。**解釈は人間**)
- **回収は `ssh -o IPQoS=none`**。**時計で見張る**(メモリ「pod は時計で見張る」。背景ポーリングの通知に頼らず `date -u` で上限を確認)。**終わったら pod を止め、`runs/<id>/cost.txt` を書く**(`infra/RUNPOD.md` §7 のチェックリストを完了報告に含める)。**承認の上限(合計 4.0 h・$0.74/時 = $2.96。人間が決めた値に従う)を超えそうになったら止める**。I5 の config・commit が無ければ pod を止めて人間に伝える(遊休させない)

### 待機(在庫が無い / push が無い / 確認が無い場合)

**pod を作らない**。人間に状況(在庫の読み・push の有無)を 1 行で伝え、次の選択肢を**推奨つきで**示す: 在庫が戻るまで待つ(推奨。ボリュームと同じ EU-RO-1・同じハード)/ 段3 = PLAN-033(P-3 の文書修正など。GPU 0。`STATE.md`「次のアクション」の 3。**どの役割・モデルで回すかは人間が選ぶ**)。**別の GPU・別のデータセンターは、ボリュームが使えずハードも変わるので勧めない**(その117 の CHANGELOG)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I5 の config 10 本**: `configs/exp_pilot_ft_cmp_*.yaml`(その118 の commit。親 = `a27ca09`。`git log -1`)。**写し元(同じ条件・シード・ステップ数の `exp_pilot_ft_eval_*`)と違う欄は 4 つ**(`experiment.id`・`experiment.plan` = PLAN-032・`eval.batteries` = `[comparison]`・`eval.task_subset` = `[t1b, t3]`)。`--dry-run` 10 本 = exit 0・各 960 件・data_checks 7 PASS。新テスト `code/tests/test_pilot_ft_cmp_configs.py` 61 件・全体の `pytest code/tests -q` = **2102 passed(214.40 秒)**・変異 8 通りすべて検出
- **★件数の訂正**: その117 と旧 HANDOFF の「1 本 = 640 件」は答えが訓練域内のバッチだけで、域外 320 を落としていた。**実際は 960 件**。Phase 2 は 10 本で +約 4 分・+約 $0.05(算定)。上限 4.0 h の内側。その117 の見積りの表は書き換えていない
- **凍結 tag `preregister-diag-sharpness` = `102c2d5`**(動かしていない。4 腕の config も不変)
- **RTX 4090 SECURE は EU-RO-1 で在庫なし**(その118 の読み: `get-gpu-type`(RO)= NONE・`get-capacity` = Out)。既存の pod 3 本は `EXITED`(触っていない)

## 触ってよいファイル / 読むべき範囲

- A: 読む = `logs/CHANGELOG.md`(`grep -n 'その11[78]' logs/CHANGELOG.md` → `sed -n`)/ `plans/PLAN-032` §8.2(`sed -n '379,388p'`)/ `infra/RUNPOD.md` §3・§4・§7 / `runs/pilot_ft_chain_n313/{chain.sh,run_step.sh}` / 各 config の冒頭の注記。書く = `runs/<id>/`・`logs/CHANGELOG.md`・`STATE.md`
- **編集しない**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / `logs/OPEN-ITEMS.md` / `configs/exp_diag_*.yaml`(tag の commit の config)/ `configs/exp_pilot_ft_*.yaml`(写し元・I5 とも)/ テンプレート / `code/`(変える必要が出たら止めて人間に伝える)

## やってはいけないこと

- **tag を打たない・push しない**(人間の操作)。**G2-1 の最終確認が出る前に pod を作らない・起動しない**。**4 腕を tag の commit と違う commit で回さない**(ADR-110 決定2)。**I5 を 4 腕の前に回さない**。合否線・R2〜R5 の規則・区間の計算法を変えない。判定表の結果・I5 の結果を解釈しない(読むのは人間)
- **RunPod の pod は「自分の呼び出しで作ったもの」だけを止める・消す**。既存の `EXITED` の 3 本の terminate は人間。start は人間の許可を取る
- **`list-pods` の出力には既存 pod の `JUPYTER_PASSWORD` が平文で出る**(その118 で見えた)。ログ・CHANGELOG・STATE に**写さない**
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `python <script>`)。**`.md` も `.py` も LF 固定**(`.gitattributes`)。Python で書くときは `newline="\n"`(またはバイトで書く)。Edit ツールが `.py` を CRLF で書いたことがある(その113)→ `.py` を Edit したら CR が 0 であることを確かめる
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` か、終了条件つきの `until <check>; do sleep 3; done`(その118 で通った)。`/usr/bin/time` は無い(シェルの `time` か `date +%s` の差)
- `STATE.md` は上限に近い(383 行・61.7 KB。回帰テストが落ちるのは 700 行 / 90 KB)。新しいブロックに ADR の中身を書き写さない(正本を指す)

## 未解決 / 人間の承認待ち

- **その118 の commit の push**(main。Phase 2 の前)/ **G2-1 の最終確認**(起動の直前。上限・Phase の分け方・GPU)/ **4090 の在庫**
- **その118 の実装の読み 1〜5**(名前 `exp_pilot_ft_cmp_*` / `experiment.plan` を PLAN-032 に / `pilot_design_gate` を写しのまま残した / 上位 k を宣言していない / `reference_rule: p2`。中身は `logs/CHANGELOG.md` その118)。**上位 k が要るなら tag の後の commit で config に足す**
- **採択の ADR への記録**(提案 RUNNER その117・採択 人間 2026-09-26 のチャット。`logs/DECISIONS.md` はこの 2 セッションとも編集していない。`CLAUDE.md` §8・メモリ「recommend-before-choice」)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)/ 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
