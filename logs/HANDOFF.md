# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-25(その94)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 151k トークンを検出。閾値 140k)。**PLAN-031 のパイロット FT は途中で、pod は稼働中(課金が続いている)**
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 進行中の連鎖を待ち、決まった規則(PLAN-031 §8.1)を機械的に当て、回収して pod を止める。`Documents/10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成 = Sonnet」の行に近い(この読みは人間が覆せる)。
**予測と違う結果の解釈や規則の外の判断が要る場面になったら、止めて人間に上げる**(`CLAUDE.md` §8)。

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**最初に pod の状態を見る**(下の 0)。

## このセッションでやること(1 つだけ)

**pod `ysev2xg35iih2j` で走っている PLAN-031 のパイロット FT の連鎖(訓練 5・評価 5)を最後まで見届け、`gonogo_ft` の表を出して報告し、成果物を git に戻して pod を停止する。解釈はしない。**規則の正本は `plans/PLAN-031-seed-fix-and-pilot-ft.md` §8.1(`grep -n '^### 8'`)/ ADR-103。

0. **開始時(最優先)**: RunPod MCP の `list-pods` で `ysev2xg35iih2j` が `RUNNING` か確かめる。**稼働の上限は 2026-09-25T12:07:26Z**(pod 作成 08:07:26Z + 4 時間。ADR-103 決定1)。pod 上で `date -u` を取り、**上限に近ければ動いているものを止めて報告する**。ssh は `ssh -o IPQoS=none -o ServerAliveInterval=5 -o ServerAliveCountMax=4 root@213.173.109.25 -p 10487`(**pod が止まっていたら IP・ポートが変わる。`get-pod` の `ssh.direct` で取り直す**)
1. `tail -20 /workspace/pilot_chain.log` を見る。連鎖は 08:23:10Z に起動済み。順は **eval p2_s0 → train p2_s1 → eval p2_s1 → train ident_s0 → eval ident_s0 → train ident_s1 → eval ident_s1 → train p2d_s0 → eval p2d_s0**。`CHAIN_DONE` が最後の行なら完走。`CHAIN_ABORT at: <step>` なら**止めて報告する**(原因の材料 = `/workspace/pre_<kind>_<cond>_s<seed>.out` と `/workspace/<kind>_<cond>_s<seed>.out` の `tail`。**config を書き換えない。連鎖を勝手に再起動しない**)。走っている最中なら、背景ポーリングで待つ(下の落とし穴)。**見込み完走 09:30〜09:50Z(推定。訓練 1 本 preflight 約 4 分 + 5 分、評価 1 本 preflight 約 4 分 + 2 分)**
2. 完走したら pod 上で(`export HF_HOME=/workspace/.cache/huggingface; cd /workspace/translesion; source /workspace/venv/bin/activate`):
   `python -m code.analysis.gonogo_ft --runs "runs/pilot_ft_eval_*" --out-dir results/pilot_ft` → 出力の `gate_summary` を §8.1 B の表に当てる。**回し直しが要る場合は config を自分で書き換えない**(IMPLEMENTER が `infra/make_pilot_ft_configs.py` で作り直す。1 回目の run を上書きしない)。止めて報告する
3. **4 値(`correct_rate` / `rule_rate` / `other_error_rate` / `parse_fail_rate`)をすべて並べて報告する**(`CLAUDE.md` §6)。#4・#4b・#5・#5b の印と表を出す。**「病変が入った」「崩壊した」とは書かない**
4. 回収して git に戻す(`infra/RUNPOD.md` §4。**「git に戻すもの」= `metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` / `cost.txt` / `token_boundary.json`。加えて `git_sha.txt`・`vram_*.csv`・`seed` 関連・`adapter/adapter_config.json`**。`adapter_model.safetensors`(1 本 167,832,240 バイト)・`predictions/`・`log.txt` は `.gitignore`(`runs/*/*.safetensors` など)が除外する。**前の HANDOFF は「アダプタを含む」と書いたが、`RUNPOD.md` §4「adapter/ も git に戻さない。永続ボリュームに残す」と `.gitignore` が正本なので、アダプタは pod のボリューム `r963j7swke` に残す**)。あわせて pod 上の `/workspace/run_step.sh`・`/workspace/chain.sh`・`/workspace/pilot_chain.log` を `runs/pilot_ft_chain/` に写して戻す(**この 3 つは pod 上にしか無い**)。`cost.txt` の書式は `infra/RUNPOD.md` §7(前例: `runs/pilot_ft_seed_check_a/cost.txt`)。**pod → この機の転送は未検証**(逆向きは `-o IPQoS=none` で通った)。詰まったら tar を ssh のパイプで受ける
5. **`pod-action stop` で `ysev2xg35iih2j` を止め、`list-pods` で `EXITED` を確認する。terminate しない(人間。段1 の後)。**旧 `lh823acvxuo8ux`(EXITED)にも触らない
6. `STATE.md`・`logs/CHANGELOG.md`・`logs/OPEN-ITEMS.md`(稼働中 pod の行)を更新し、`exp(train)` / `exp(eval)` の commit に `[run:...]` を付ける。skill `handoff` の手順で閉じる

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **凍結 tag `preregister-pilot-ft` は人間が打った**(`37346bf` = 当時の HEAD)。pod の repo も `37346bf`(tracked の差分 0 行)。config は無編集
- **旧 pod `lh823acvxuo8ux` は host に空き GPU が無く start できなかった(400)。人間が EU-RO-1 に新規を選んだ**(RTX 4090 SECURE・$0.74/時。`/workspace` = `r963j7swke`)
- **済み**: 訓練 `p2` s0 [run:pilot_ft_train_p2_s0](rc 0・`timestamp.txt` 300.4 秒・625 ステップ・VRAM 最大 18,462 MiB・損失 6.416 → 7.48e-06)/ 評価 `p2` s0 [run:pilot_ft_eval_p2_s0](rc 0・2 分 13 秒。**指標は読んでいない**)。外挿 = 100.1 分 ≈ 1.67 h(< 4 h。続行済み)。正本は `logs/CHANGELOG.md` 2026-09-25(その94)
- `adapter_init_sha256`(`p2` s0)= `057c53c934467b89e4f6ae89454667d1374246d1229661f82a48e2b18ed7ace8` は、★E の確かめの seed 0 [run:pilot_ft_seed_check_a] と同じ値
- `git_sha.txt` の `dirty: true` は untracked の run dir が理由(tracked の差分は 0 行。`git_diff.patch` は 0 バイト)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §8.1・§8.2 / `logs/DECISIONS.md` の ADR-103 だけ(`grep -n '^## ADR-103'`)/ `infra/RUNPOD.md` §4・§7 / `logs/CHANGELOG.md` の末尾(その94)
- config は `configs/exp_pilot_ft_{train_{p2,ident,p2d},eval_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}}.yaml`(**読むだけ。編集しない**)
- **pod の落とし穴**: `export HF_HOME=/workspace/.cache/huggingface` を必ず行う(飛ばすと 401)/ ssh・scp は `-o IPQoS=none` を付ける(memory `runpod-ssh-ipqos-none`)/ **Bash の前景 `sleep` も PowerShell の `Start-Sleep` も禁止**されている。待つときは `run_in_background: true` の Bash で `until` ループ(`END=$((SECONDS+540))` で 9 分まで。ssh 1 回に 8〜18 秒かかる)を回し、通知を待つ / **torch を import する ssh は初回に 90 秒を超えることがある**(ボリュームのコールドキャッシュ。Bash ツールが背景に移す)/ 「終了コード 1」は例外でも出るので、成否は成果物の有無で見る / preflight は 1 本 約 4 分かかる(コールドキャッシュ)

## やってはいけないこと

- **tag を打たない。config・コードを書き換えない**(回し直しの config は IMPLEMENTER)。§8.1 の外の条件・値・順序を足さない
- **`num_steps`・`learning_rate` を自分の判断で動かさない。**#4b・#5b の割れで回し直さない。結果を解釈しない。`pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使わない。T1b・T3 は解かない(段2 の凍結の後)
- **結果が良すぎるとき(例: #4 が 1.000)は、まずバグを疑う**(`CLAUDE.md` §7。PLAN-031 §6 新5)。**訓練 `p2` s0 の損失が 34 ステップ目に 1e-3 を割り、最後は 7.5e-06 という点は、解釈せずに人間へ報告する**(損失マスクは実装されている = `build_labels`)
- **pod を起動したまま放置しない。**連鎖の完走・回収の後に stop する。`lh823acvxuo8ux`・`ysev2xg35iih2j` を terminate しない(人間)
- 10 GPU 時間の線に触れない: **pod の稼働 4 時間(12:07:26Z)が上限**、回し直しを含めて段1 全体で 9 時間まで(ADR-103)

## 未解決 / 人間の承認待ち

- 結果の解釈・`p2d` の扱い・回し直しの後の判断・`lh823acvxuo8ux` と `ysev2xg35iih2j` の terminate は人間(`CLAUDE.md` §8)
- 「(具体化)」の細部(評価 1 本 10 分の置き値・回収 15 分・1 本目の打ち切り 60 分・VRAM の記録方法・回し直しの run の名前)は、人間に別の問いとして聞いていない(ADR-103 リスク欄)。**実測は評価 1 本 2 分 13 秒(preflight 別)、訓練 300.4 秒**
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
