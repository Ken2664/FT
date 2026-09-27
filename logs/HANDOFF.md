# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-27(その119)/ 直前セッションの役割: RUNNER(G2-1 承認後に pod 起動を試みた)
直前セッションが終了した理由: **成果物の区切り**(pod 起動 4 回すべて失敗。在庫が戻るまで人間待ち)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 在庫確認と pod 起動の再試行、または push 確認だけの短い作業。**選ぶのは人間**

---

**冒頭で人間に確かめること**: ① **その118 の commit(`01cf60f`。I5 の config 10 本)を push したか**(`git ls-remote origin refs/heads/main` が `git rev-parse HEAD` と同じか。その119 終了時点ではまだ `102c2d5` のままだった)② **RTX 4090 SECURE の在庫**(`mcp__plugin_runpod_runpod__get-gpu-type` を `include: ["AVAILABILITY"]`・`product: ["POD"]`・`cloud: SECURE`・`countryCodes: ["RO"]` で読む。その119 の読みは `LOW` だったが、既存 3 pod の再起動 + 新規作成の計 4 回とも「実際の割当」では失敗した。**`LOW` の表示は割当の成功を保証しない**)。**最初の発言で、自分の役割と実モデル名と、上の推奨との一致・不一致を 1 行で述べること**。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること

### A. push 済み・在庫に実際の空きがある場合 → RUNNER: Phase 1(4 腕)→ Phase 2(I5 の 10 本)を回す

`logs/CHANGELOG.md` の「その117」(見積り・上限・pod 上の手順の要点)・「その118」(I5 の config と件数の訂正)・「その119」(pod 起動の失敗の記録)、`plans/PLAN-032` §8.2、`infra/RUNPOD.md` §3・§4 に従う。**連鎖のひな形 = `runs/pilot_ft_chain_n313/{chain.sh,run_step.sh}`**(直接は使えないので diag 用に読み替えて手順を書く。§8.2 に手順そのものはコマンド単位で書いてある)。

- **pod の起動を先に試す**: 既存 EXITED 3 本(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)のどれかを `pod-action`(`start`)、または `create-pod`(RTX 4090 SECURE・EU-RO-1・ボリューム `r963j7swke` を `/workspace` にアタッチ)。**その119 は4回とも失敗**(課金なし)。**起動に成功したら、その時点で改めて型・単価・停止予定時刻を人間に一言示してから先へ進む**(すでに G2-1 の承認は得ているので再承認は不要。状況が変わった=起動できた、という事実確認のみ)
- **Phase 1(4 腕。tag の commit のまま)**: `git bundle create ft.bundle main preregister-diag-sharpness` → pod で `git checkout preregister-diag-sharpness`。診断のプールは `configs/exp_diag_pool.yaml` 冒頭のコマンドで作り、**作った後に `git diff HEAD` が空か確かめる**(動いていれば `git checkout -- data/generated`)。run ごとに preflight → run。判定表 = `python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`(**機械的。読むのは人間**)
- **Phase 2(I5。4 腕の後・同じ承認の枠の中・I5 の commit が push 済みのときだけ)**: I5 の commit(main)を checkout。パイロット用プールの作り直しは `configs/exp_order6b_pilot.yaml` 冒頭のコマンド(作った後に `git checkout -- data/generated`)。10 本 = `configs/exp_pilot_ft_cmp_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}{,_n313}.yaml`。**入口は config の冒頭に書いてある**: `python -m code.eval.run --config configs/exp_pilot_ft_cmp_<条件>_s<シード>[_n313].yaml --run-dir runs/pilot_ft_cmp_<条件>_s<シード>[_n313]`。**1 本 = 960 件**。アダプタの重みはボリューム `r963j7swke` にある。**結果は探索的**(§8.1 R8)
- **回収は `ssh -o IPQoS=none`**。**時計で見張る**(`date -u` で上限を確認)。**終わったら pod を止め、`runs/<id>/cost.txt` を書く**。**上限(合計 4.0 h・$0.74/時 = $2.96)を超えそうになったら止める**

### B. push が未確認、または在庫がまだ実際に割り当てられない場合 → 待機

**pod を作らない**(その119 のように「失敗しても課金されない」ので試すこと自体は安全だが、4 回連続で失敗した直後に間を置かず繰り返すのは避ける)。人間に状況を 1 行で伝え、次の選択肢を推奨つきで示す: 在庫が戻るまで待つ(推奨)/ もう一度だけ pod 起動を試す / 段3 = PLAN-033(GPU 0)。

## 直前セッション(その119)で確定したこと

- **G2-1 の最終承認は人間から得た**(`AskUserQuestion`。型 RTX 4090 SECURE EU-RO-1・単価 $0.74/時・上限 4.0h/$2.96。**この承認自体は生きている** — 次に pod が起動できたときに再承認を求める必要はない。起動できた事実だけ一言伝える)
- **pod 起動 4 回すべて失敗・課金なし**(`list-pods` で確認済み): 既存 3 本の再起動(host に空き GPU なし)× 3、新規作成(no longer any instances available)× 1
- **`get-gpu-type`(RO)の `LOW` は実際の割当を保証しない**(その118 の `NONE` から変わっただけで、割当は依然として失敗する)
- **push は未確認**: 人間は「今すぐ自分で push する」と答えたが、セッション終了時点で `origin/main` はまだ `102c2d5`(その118 の commit `01cf60f` が乗っていない)

## 触ってよいファイル / 読むべき範囲

- 読む = `logs/CHANGELOG.md`(`grep -n 'その11[789]' logs/CHANGELOG.md` → `sed -n`)/ `plans/PLAN-032` §8.2 / `infra/RUNPOD.md` §3・§4・§7 / `runs/pilot_ft_chain_n313/{chain.sh,run_step.sh}` / 各 config の冒頭の注記。書く = `runs/<id>/`・`logs/CHANGELOG.md`・`STATE.md`
- **編集しない**: `plans/PLAN-032` §8.1 / `logs/DECISIONS.md` / `logs/CRITIQUE.md` / `logs/OPEN-ITEMS.md` / `configs/exp_diag_*.yaml` / `configs/exp_pilot_ft_*.yaml` / テンプレート / `code/`(変える必要が出たら止めて人間に伝える)

## やってはいけないこと

- **tag を打たない・push しない**(人間の操作)。**4 腕を tag の commit と違う commit で回さない**(ADR-110 決定2)。**I5 を 4 腕の前に回さない**。合否線・R2〜R5 の規則・区間の計算法を変えない。判定表の結果・I5 の結果を解釈しない(読むのは人間)
- **RunPod の pod は「自分の呼び出しで作ったもの」だけを止める・消す**。既存 pod の terminate は人間。start は(G2-1 承認済みなので)このセッションで試してよいが、**失敗を連発したら間を置く**
- **`list-pods` の出力には既存 pod の `JUPYTER_PASSWORD` が平文で出ることがある**。ログ・CHANGELOG・STATE に**写さない**
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。**`.md` も `.py` も LF 固定**。Python で書くときは `newline="\n"`
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` か、終了条件つきの `until <check>; do sleep 3; done`

## 未解決 / 人間の承認待ち

- **その118 の commit の push**(main。Phase 2 の前)/ **RTX 4090 の在庫**(実際に割当できる空きが戻るまで)
- **その118 の実装の読み 1〜5**(名前 `exp_pilot_ft_cmp_*` / `experiment.plan` を PLAN-032 に / `pilot_design_gate` を写しのまま残した / 上位 k を宣言していない / `reference_rule: p2`)
- **採択の ADR への記録**(提案 RUNNER その117・採択 人間その118のチャット。`logs/DECISIONS.md` は未編集)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)/ 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
