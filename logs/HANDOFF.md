# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-25(その95)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: **PLAN-031 の 1 回目(訓練 5・評価 5)が完了した** + コンテキスト超過(hook `context-guard` が約 100k を警告)。**pod は 2 本とも `EXITED`(課金なし)**
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 最初の仕事は人間への確認(下の 1)。人間が進めると決めたら、`infra/make_pilot_ft_configs.py` の改修 + テストは `10_CONTEXT_POLICY.md` §7 の「実装 = Sonnet」の行(この読みは人間が覆せる)。**印の受け止め・ADR を書く場面になったら Opus に替える**(§8 の判断・解釈は人間)。

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**GPU・pod には触らない**(RUNNER の仕事)。

## このセッションでやること(1 つだけ)

**1. 人間に次の 4 点を確かめる(答えが出るまで実装を始めない)。** `CLAUDE.md` §8。案は出してよいが、決めるのは人間:
   (a) **パイロットの印の受け止め**(4 値の表は `logs/CHANGELOG.md` 2026-09-25(その95)。`no4` true / `no4b` true / `no5`・`no5b_v1`・`no5b_v2` false)/ (b) **pod の上限 4 h を 19 分超過した件の扱い**(RUNNER の見落とし。遊休 約 2.9 h ≈ $2.12。稼働 4.32 h ≈ $3.20)/ (c) **§8.1 B の回し直し(625 → 313)を今進めるか** — 進めるなら**単価と pod**(旧 `lh823acvxuo8ux` は host に GPU が無く start できなかった。新規は $0.74/時 前後。**段1 の残り枠 = 9 h − 4.32 h = 4.68 h**)と、**新しい tag が要るか**(規則は tag 済みの §8.1 B の内側なので要らない見込み。人間が確かめる)/ (d) **`p2d` の扱い**(ADR-103 決定7。`no4b` は true)

**2. 人間が「回し直す」と決めたら**: `infra/make_pilot_ft_configs.py` を改修して、`num_steps` 313 の config を 10 本作る。完了条件:
   - `TRAIN_VALUES["num_steps"]`(現在は 625 固定。`infra/make_pilot_ft_configs.py:53`)を**引数で上書きできる**ようにし、**1 回目の config と run を上書きしない**(§8.1 B の具体化)。**名前の案**: run dir `runs/pilot_ft_train_<cond>_s<seed>_n313`・config id `exp_pilot_ft_{train,eval}_<cond>[_s<seed>]_n313`(接尾辞は案。**評価 config の `model.adapter` が新しい訓練 run の `adapter/` を指すこと**が要点)
   - **`num_steps` 以外を変えない**(`[MATCHED]`。`learning_rate` は動かさない = ADR-103 決定8)。`python infra/make_pilot_ft_configs.py --check` が 1 回目の 8 本と食い違わないこと
   - `code/tests/test_pilot_ft_configs.py` に 313 の分を足し、`pytest code/tests -q` が通ること
   - **コード書き換えの後に凍結 tag との整合を確かめる**(`git diff preregister-pilot-ft --stat` で、変えたのが生成器・テストと新 config だけであること)
   - commit(`feat(train):` `[...]` 種類は CLAUDE.md §5)。**RUNNER 用の次の HANDOFF を書く**(`logs/HANDOFF.md`。skill `handoff`)

**人間が「回し直さない」「別の手を取る」と決めたら**、その決定を ADR に書く案(提案者 = エージェント・採択者 = 人間を分ける。ADR-039)を出して止める。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **連鎖は完走した**: 訓練 5・評価 5 すべて rc 0、`CHAIN_DONE 2026-09-25T09:34:59Z`。config・コード無変更(10 本とも `git_sha.txt` = `37346bf`)。**正本は `logs/CHANGELOG.md` 2026-09-25(その95)と `results/pilot_ft/gonogo_ft.{json,out}`**
- **印(`gonogo_ft.json` の `summary`。JSON の最上位に `gate_summary` は無い)**: `no4.all_pass` = true / `no4b` = true / `no5` = false(割れた = 5 run 全部)/ `no5b_v1`・`no5b_v2` = false(5 run 全部)。**§8.1 B の行 = 「まだ下げていなければ 625 → 313 で全条件をやり直す」**(まだ上げても下げてもいない)
- **費用**: `runs/pilot_ft_train_p2_s0/cost.txt`(pod 全体)= 15,560 s = 4.32 h ≈ $3.20(推定)
- 壁時計: 訓練 1 本 300〜322 s・評価 1 本 115〜149 s(`timestamp.txt`)。preflight は 1 本 約 4〜5 分。VRAM 最大: 訓練 18,462 MiB・評価 16,314 MiB(/ 24,564)
- **アダプタ 5 本(`adapter_model.safetensors` 167,832,240 バイト)・`predictions/`・`log.txt` は pod のボリューム `r963j7swke`(`/workspace/translesion/runs/...`)にある**(git には無い)。回し直しで新しい pod を立てても同じボリュームを `/workspace` に付ければ見える

## 触ってよいファイル / 読むべき範囲

- `logs/CHANGELOG.md` の末尾(その95)/ `plans/PLAN-031-seed-fix-and-pilot-ft.md` §8.1 B(`grep -n '^### 8'`)/ `logs/DECISIONS.md` の ADR-103(`grep -n '^## ADR-103'`。決定 4〜8)
- 編集してよいのは、人間が進めると決めた後の `infra/make_pilot_ft_configs.py`・`code/tests/test_pilot_ft_configs.py`・新しい config だけ。**1 回目の config(`configs/exp_pilot_ft_*.yaml` の 8 本)は編集しない**
- 回し直しの連鎖の写し: `runs/pilot_ft_chain/{chain.sh,run_step.sh,pilot_chain.log}`(今回 pod 上にしか無かったものを回収した。RUNNER が同じ形で作り直す)

## やってはいけないこと / 直前セッションで踏んだ地雷

- **人間の決定なしに実装を始めない。RUNNER の仕事(GPU・pod)をしない。tag を打たない**(人間)。`learning_rate` を動かさない。**`no4b`・`no5b` の割れで回し直しの引き金にしない**(決定7)
- **★時計を見る(上限超過の再発防止。次の RUNNER にも渡すこと)**: 待つときはバックグラウンドの通知に頼らず、**返答ごとに `date -u` を取り**、上限の 30 分前に `pilot_chain.log` を直接見る。通知が届かなくても pod は課金され続ける。**完走したら回収の前でも後でもよいが、上限を超える前に必ず `pod-action stop`**
- **解釈しない**: 印は当てただけ。`p2` の s1 は s0 と同じ条件なのに T2 の 3 セルで割れている(`id` rule .000 / other_error 1.000 対 .988 / .013)、`ident` も #5 で割れた(T2 の other_error 0.200〜0.250)、損失が 5 本とも最後は 1.5e-05 以下 — **これらは人間へ上げた点で、意味づけは人間**。`pool_id: pilot` の数値を主張・効果量・Δ 5 行・E1 の境界に使わない
- **pod → この機の転送は通った**: `ssh -o IPQoS=none ... "tar czf - --exclude=predictions --exclude='*.safetensors' <dir>..." > file.tgz`。**Windows で JSON を Python で開くときは `python -X utf8`(既定 cp932 で落ちる)**。Bash の前景 `sleep` は禁止
- **新しい pod で repo を更新するとき、pod 側の untracked な `runs/pilot_ft_*` が、今回 git に入れた同名の追跡ファイルと衝突して `git merge --ff-only` が失敗する**。前回(その94)の手順 = 退避(`/workspace/pod_moved_aside_...`)→ `--ff-only` → `cp -an` で戻す。**このボリュームには 1 回目の run dir(アダプタつき)が既にある**ので、退避せずに消してはならない(**アダプタは git に無い**)

## 未解決 / 人間の承認待ち

- 上の 1 の (a)〜(d)(`logs/OPEN-ITEMS.md`「パイロット FT の印の受け止めと回し直し(313)」の行)/ **pod 2 本(`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate は人間**(段1 の回し直しの後。アダプタはボリューム側の資産)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり(段2 の PLAN-032 は段1 の後)
