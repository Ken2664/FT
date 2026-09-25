# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-25(その96)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(人間の 4 回答を ADR-104 に記録し、回し直し(`num_steps` 313)の config 8 本を作った。GPU 0・pod 0)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — RUNNER の仕事は、決まった手順を回し・印を当て・回収するだけの定型である(`Documents/10_CONTEXT_POLICY.md` §7 の表に RUNNER の行は無い。269 行の「定型」に当たると読む。**人間が覆せる**)。**印の意味づけ・ADR を書く場面になったら Opus に替える**(`CLAUDE.md` §8 の判断・解釈は人間)。

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP はこのセッションで使う**(RUNNER のみ有効にする規約)。

## このセッションでやること(1 つだけ)

**PLAN-031 §8.1 B の回し直し(`num_steps` 313。訓練 5・評価 5)を実行し、印を当てて回収し、pod を止める。**
人間の承認は済み(ADR-104): **単価 $0.74/時まで**・pod は RUNNER が選ぶ・**新しい tag は打たない**・`p2d` も回す。**解釈はしない。**

### 手順(この順)

1. **始める条件**: `git merge-base --is-ancestor preregister-pilot-ft HEAD` が通る(通る。その96 に確かめた)。`git status` がきれい。**config は編集しない**(`configs/exp_pilot_ft_{train_*,eval_*}_n313.yaml` の 8 本。`python infra/make_pilot_ft_configs.py --num-steps 313 --check` が食い違いなしであること)
2. **起動の直前に人間へ 1 行で確かめる**(ADR-103 決定1 と同じ形): **選んだ pod・単価・上限時刻**。単価が $0.74/時を超えるなら止めて聞く。
   - pod の候補: (i) 旧 `ysev2xg35iih2j`(1 回目に GPU が付いていた。`EXITED`)の `start` を試す / (ii) だめなら **EU-RO-1** の新規 RTX 4090 SECURE(ボリューム `r963j7swke` を `/workspace` に付ける。同じ DC でないと付かない)。旧 `lh823acvxuo8ux` は host に GPU が無く `start` できなかった。在庫は**未確認**(その91 は全 DC で無かった)
   - **上限**: 段1 の残り = 9 h − 4.32 h = **4.68 h**(pod の稼働時間。ADR-103 決定5)。**算定は約 2 h(実測ではない)**。起動時刻 + 自分が引く線(4.68 h の内側)を人間に示す。**外挿と打ち切りは §8.1 A と同じ形**: 1 本目(`p2` s0)の訓練の後に「(その時点の稼働時間)+ 4 ×(その訓練の壁時計)+ 5 × 10 分 + 15 分」を出し、上限を超えるなら残りを始めずに止めて報告。1 本目の訓練が 60 分を超えたら止めて報告
   - **1 回目の `predictions/`(ボリュームにしか無い)を、この pod が動いている間に回収するか**を人間に聞く(ADR-104 リスク。`p2` s1 と `ident` の T2 の割れの中身を後で調べるなら、追加の pod 時間が要らず安い)
3. **repo を pod に載せる**(`infra/RUNPOD.md` §3 の bundle の手順: この機で `git bundle create ft.bundle main` → scp → pod の `/workspace/translesion` で `git fetch <bundle> main` → `git merge --ff-only FETCH_HEAD`。この機の `origin/main` は 80 commit 遅れ(`git status` の表示)なので `git pull` は使えない)。**★地雷(その94)**: pod 側の untracked な `runs/pilot_ft_*` が、git に入れた同名の追跡ファイルと衝突して `git merge --ff-only` が失敗する。**退避(`/workspace/pod_moved_aside_...`)→ `--ff-only` → `cp -an` で戻す**。**1 回目の run dir(アダプタつき。git に無い)を消してはならない**
4. **連鎖を新しい名前で作る**(**`runs/pilot_ft_chain/` は 1 回目の写しで git 追跡済み。上書きしない** → `runs/pilot_ft_chain_n313/`)。`runs/pilot_ft_chain/{chain.sh,run_step.sh}` の形を写し、**名前だけ**替える: 訓練 config `configs/exp_pilot_ft_train_<条件>_n313.yaml`・run dir `runs/pilot_ft_train_<条件>_s<シード>_n313` / 評価 config `configs/exp_pilot_ft_eval_<条件>_s<シード>_n313.yaml`・run dir `runs/pilot_ft_eval_<条件>_s<シード>_n313`(名前は `infra/make_pilot_ft_configs.py` の `train_run_dir` / `eval_run_dir` と同じ)。各 step は preflight → VRAM の `nvidia-smi` 3 秒記録 → 実行。**最初に `p2` s0 を訓練する**(残りの順序は RUNNER が決めてよい。評価は同じ (条件, シード) の訓練の後)。**同じ (条件, シード) を訓練 → 評価の順に**
5. **判定**: 10 本が揃ったら pod 上で
   `python -m code.analysis.gonogo_ft --runs "runs/pilot_ft_eval_*_n313" --out-dir results/pilot_ft_n313`
   **★`--out-dir` は `results/pilot_ft_n313`。`results/pilot_ft/`(1 回目。git 追跡済み)を上書きしない。glob も `_n313` で絞る**(絞らないと 1 回目の run が入り、同じ (条件, シード) で `gonogo_ft` が止まる)。出力の `summary` の 5 印を §8.1 B の表に当てる
6. **回収**(pod → この機。**`ssh -o IPQoS=none ... "tar czf - --exclude=predictions --exclude='*.safetensors' <dir>..." > file.tgz`**。10 run の小ファイル + `runs/pilot_ft_chain_n313/` + `results/pilot_ft_n313/`)。アダプタ・`predictions/`・`log.txt` はボリュームに残す(`.gitignore`)。**Windows で JSON を Python で開くときは `python -X utf8`**
7. **`pod-action stop` → `list-pods` で `EXITED` を確認**(**上限を超える前に必ず**)。`cost.txt` を残す。commit(`exp(train):` / `exp(eval):`。`[run:...]` を 10 本ぶん。`git_sha.txt` の食い違いがあれば書く)
8. **印を当てた後、新しい GPU の仕事は始めない**: §8.1 B の表は「下げた後なら止めて報告」「衝突は止めて報告」「(true, true) は終わり」。**どの印でも、報告して止まる**。`learning_rate` は動かさない(ADR-103 決定8)

## ★時計を見る(1 回目の上限超過の再発防止。memory `runpod-check-clock-not-notifications`)

- **待つときはバックグラウンドの通知に頼らない。返答ごとに `date -u` を取る。**上限の 30 分前に `pilot_chain.log` を直接見る。1 回目は、通知が届かないまま pod が上限を **19 分超過**し(遊休 約 2.9 h ≈ $2.12)、稼働 4.32 h ≈ $3.20 になった
- 連鎖が完走したら、回収の前でも後でもよいが、**上限より前に `pod-action stop`**。Bash の前景 `sleep` は禁止

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **人間の回答(ADR-104)**: (a) §8.1 B のとおり 313 を進める / (b) 上限 19 分超過は記録のみ・仕組みは足さない / (c) $0.74/時まで承認・pod は RUNNER が選ぶ・新しい tag は打たない / (d) `p2d` も回す。**正本は `logs/DECISIONS.md` の ADR-104 と `plans/PLAN-031` §8.3**
- **config は 8 本・run は 10 本**(訓練 config は条件ごとに 1 本で `seeds` を宣言。評価 config は (条件, シード)ごと)。**1 回目との差は `experiment.id`・`train.num_steps`(625 → 313)・評価の `model.adapter`(`_n313` の訓練 run の `adapter/`)だけ**(`code/tests/test_pilot_ft_configs.py` が縛る)。`pytest code/tests -q` = 1747 passed
- **凍結 tag との整合**: `git diff preregister-pilot-ft --stat -- code infra configs` = 追加は新 config 8 本・変更は生成器とテストの 2 ファイルだけ。**1 回目の 8 本の config は tag から 0 差分**
- **1 回目の実績(`logs/CHANGELOG.md` 2026-09-25(その95)。参考値)**: 訓練 1 本 300〜322 s・評価 1 本 115〜149 s・preflight 1 本 約 4〜5 分 / VRAM 最大 訓練 18,462 MiB・評価 16,314 MiB(/ 24,564)/ アダプタ 1 本 167,832,240 バイト。**313 の訓練の壁時計は未測**(重みの読み込み・保存の固定費を分けて測っていないので、半分になるとは限らない)
- **1 回目の印**(`results/pilot_ft/gonogo_ft.json` の `summary`): `no4` true / `no4b` true / `no5`・`no5b_v1`・`no5b_v2` false(5 run すべて)。**意味づけは人間**(`p2` s1 の T2 の割れ・`ident` の T2 の other_error 0.200〜0.250・`p2d` の #5b)

## 触ってよいファイル / 読むべき範囲

- 読む: `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §8.1・§8.3(`grep -n '^### 8'`)/ `logs/DECISIONS.md` の ADR-103 決定4〜8 と ADR-104(`grep -n '^## ADR-10[34]'`)/ `logs/CHANGELOG.md` の末尾 2 エントリ(その95・その96)/ `infra/RUNPOD.md` §3・§4・§5 / `runs/pilot_ft_chain/{chain.sh,run_step.sh,pilot_chain.log}`(1 回目の写し。**読むだけ**)
- 書く(新規のみ): `runs/pilot_ft_train_*_n313/`・`runs/pilot_ft_eval_*_n313/`・`runs/pilot_ft_chain_n313/`・`results/pilot_ft_n313/`・`logs/CHANGELOG.md`・`STATE.md`・`logs/HANDOFF.md`
- **編集しない**: `configs/exp_pilot_ft_*.yaml`(16 本すべて)・`infra/make_pilot_ft_configs.py`・コード全般・`results/pilot_ft/`・`runs/pilot_ft_chain/`・1 回目の run dir

## やってはいけないこと / 踏んだ地雷

- **解釈しない**: 印は当てるだけ。`pool_id: pilot` の数値を主張・効果量・Δ 5 行・E1 の境界に使わない。「313 で改善した / 悪化した」を書かない(数値と対照条件との差で報告する)
- **tag を打たない**(人間)。`learning_rate` を動かさない。`no4b`・`no5b` の割れを回し直しの引き金にしない(ADR-103 決定7)。**313 の後にさらに回し直さない**(各向き 1 回まで。決定5)
- **1 回目の結果ファイル(`results/pilot_ft/`・`runs/pilot_ft_chain/`・1 回目の run dir)を上書きしない**。名前は必ず `_n313`
- 仕様が曖昧・想定外(在庫なし・VRAM 不足・preflight 失敗・`num_steps` 以外の差の発見)は、**止めて人間に報告する**。勝手に config を直さない(VRAM 不足なら ADR-103 決定2 の退避規則 = IMPLEMENTER が全 config を micro 2 × 累積 8 に作り直す。RUNNER は編集しない)
- **完走を確かめる前に「うまくいった」と書かない**。`RUN_RC` と `metrics.json` を見る。結果が良すぎるときは、まずバグ(パーサの取りこぼし・評価データの汚染)を疑う(`CLAUDE.md` §7)

## 未解決 / 人間の承認待ち

- 印の意味づけ・`p2d` の扱い・次の手(**313 の結果が揃ってから**。人間)/ **1 回目の `predictions/` を回収するか**(起動の直前に聞く)/ **pod 2 本(`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate は人間**(段1 の後。アダプタはボリューム `r963j7swke` 側の資産)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり(段2 の PLAN-032 は段1 の後)
