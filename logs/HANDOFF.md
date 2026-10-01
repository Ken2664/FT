# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-01(その123)/ 直前セッションの役割: RUNNER(Phase 1 の 4 腕のチェーンを pod で開始した)
直前セッションが終了した理由: コンテキスト超過(context-guard 約 158k トークン)。**チェーンは pod 上で走っている最中**
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: **Sonnet** — 時計で見張る・回収・機械的な判定表の実行・pod の停止だけの RUNNER 作業(`Documents/10_CONTEXT_POLICY.md` §7 の「実行・集計」の行)。**選ぶのは人間**。**判定表を読む・解釈するのは人間の仕事(エージェントはしない)**

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること

**pod `9matkiq0jozcgm` で走っている Phase 1 の 4 腕(B → A → B-d → A-d)を見張り、終わったら回収して判定表を機械的に出し、pod を stop する。**

1. **時計を見る**: `date -u`。**pod 起動 = 2026-10-01T03:40:01Z・上限 = 累計 2.5h = 06:10Z・$1.85**(人間の G2-1 承認。Phase 1 のみ)。**通知に頼らず時計で上限を確認する**(`memory` の `runpod-check-clock-not-notifications`)。**この HANDOFF を読んでいる時点で 06:10Z を過ぎていたら、まず pod の stop を最優先にする**
2. `list-pods` で `9matkiq0jozcgm` が `RUNNING` か・SSH の接続先が `root@213.173.98.83 -p 39790` のままかを確かめる(**再起動されると変わる**)
3. 状況: `ssh -o IPQoS=none -o StrictHostKeyChecking=no root@213.173.98.83 -p 39790 'cat /workspace/chain_diag.status; date -u; tail -c 300 /workspace/diag_b.out'`
   - `PREFLIGHT_ALL_OK` → `START arm=b …`(04:09:18Z)→ `END arm=b exit=0` → `START arm=a` → … → `CHAIN_DONE`。**件数の目安: B・A 各 34,322・B-d・A-d 各 17,124(合計 102,892)。壁時計の目安は 4 腕で約 1.05h(高めで約 1.3h)**
   - **`ABORT` / `STOP time soft cap`(05:50Z を過ぎて新しい腕を始めなかった)が出たら、そこで止めて人間に報告**。`configs/`・`code/` を直して回し直さない(`CLAUDE.md` §2・§8)
4. **`CHAIN_DONE` の後**: ① 4 本の run dir(pod の `runs/20261001_034734_exp_diag_b`・`_035351_exp_diag_a`・`_035901_exp_diag_b_d`・`_040358_exp_diag_a_d`。時刻は `/workspace/arm_<arm>_ts.txt`)を確認(`metrics.json` の `kind: threshold_sweep`・件数・`git_sha.txt` が `102c2d5…` で 4 本とも同じ・`git_diff.patch` が 0 バイト)② `cost.txt` を書く(`infra/RUNPOD.md` §4・§7 の書式)③ 判定表 `PYTHONIOENCODING=utf-8 python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`(**pod の tag の commit で回す。機械的。解釈しない**)④ 回収(`metrics.json`・`config.yaml`・`env.txt`・`timestamp.txt`・`git_sha.txt`・`git_diff.patch`・`token_boundary.json`・`forced_choice_tokens.json`・`log.txt`・`cost.txt`・`results/diag_sharpness/`。`predictions/` は大きいのでボリュームに残す)。**転送は `tar czf - … | ssh … tar xzf -`(scp は約 7 KB/秒で遅い)**。⑤ ローカルの `runs/`・`results/diag_sharpness/` に置いて commit(`exp(train): … [run:…]` 形式。`CLAUDE.md` §5)
5. **回収と `cost.txt` の後、pod `9matkiq0jozcgm` を `mcp__plugin_runpod_runpod__pod-action`(`stop`)で止める**(**人間が許可済み。terminate はしない**)。`EXITED` を確認し、`runtime.uptime` から課金($0.74/時)を算出して CHANGELOG に書く。**完了報告に `infra/RUNPOD.md` §7 のチェックリストを入れる**
6. `STATE.md`・`logs/CHANGELOG.md`・`logs/OPEN-ITEMS.md` を更新して commit。**判定表の結果は「出た」とだけ書き、読み(通る・通らない・どちらが優位か)は書かない**

## 直前セッションで確定したこと(すべてファイルに反映済み: `STATE.md`・`logs/CHANGELOG.md` その123)

- **`train.jsonl` 5 本は pod 上の SHA-256 が manifest と 5/5 一致**(p2 `10be341b…`・p2d `cc9be347…`・arb `335c5ab3…`・x2 `c2eb0749…`・ident `0aa1c6a6…`)
- **`HF_TOKEN` は不要**。ボリュームに `models--meta-llama--Llama-3.1-8B-Instruct`(snapshot `0e9e39f…`)が残っており、**`HF_HOME=/workspace/.cache/huggingface HF_HUB_OFFLINE=1` を付ければ tokenizer・weights が通る**。**非対話の SSH では `HF_HOME` が未設定**なので、**pod 上で `python` を走らせるコマンドには毎回この 2 つを付ける**(`chain_diag.sh` には入っている)。**`env | grep HF_` のようにトークンの値が出うる読み取りは自動モードの分類器に拒否される。やらない**
- **4 腕の `preflight.py --config` はすべて FAIL 0**(各 PASS 17・WARN 1。WARN は preflight 自身が作った untracked の run dir で、`git diff HEAD` は空)
- チェーン `/workspace/chain_diag.sh`(nohup)は腕 B を **2026-10-01T04:09:18Z** に開始した(04:12Z の確認で GPU 96%・VRAM 16 GiB)。**結果はまだ 1 件も見ていない**
- 4 腕とも tag `preregister-diag-sharpness`(= `102c2d5`)の commit のまま回す(checkout し直さない。ADR-110 決定2)

## 触ってよいファイル / 読むべき範囲

- 読む = `plans/PLAN-032-sharpness-diagnostic.md` §8.1(R1〜R9)・§8.2 / `infra/RUNPOD.md` §4・§7 / `logs/CHANGELOG.md`(`grep -n 'その12[123]'`)。全文 `cat` しない
- pod 上の `/workspace/chain_diag.status`・`/workspace/diag_<arm>.out`・`runs/<ts>_exp_diag_<arm>/`(**`log.txt`・`predictions/` は `tail -n` / `grep -c` で。全文を読まない**)
- 書く = ローカルの `runs/*_exp_diag_*`(回収後)・`results/diag_sharpness/`・`logs/CHANGELOG.md`・`STATE.md`・`logs/OPEN-ITEMS.md`。**`configs/`・`code/` は 1 バイトも変えない**

## やってはいけないこと

- **判定表の結果を解釈しない**(読むのは人間。印・数値は「出た」と書くだけ)
- **tag を打たない・push しない**(人間の操作。ADR-110 決定4)
- **I5(Phase 2)を回さない**。今回の G2-1 承認は Phase 1 のみ。Phase 2 は `01cf60f` の push と別の承認が先
- **06:10Z を超えて pod を動かさない**。超えそうなら止めて人間に報告。**pod を放置しない**(`CLAUDE.md` §2)
- **旧 4 本の pod(`nwpfapeszov83m`・`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)を terminate しない**(人間の操作)。**この pod も terminate しない**(stop だけ許可されている)
- **`bash` の `sleep` の単発・`scp` の大量送信に頼らない**: 待つときは `date -u` の時計と `run_in_background` の until ループ(終了条件つき)。**`pkill` で `for` ループの途中の `scp` を止めると、ループが次のファイルへ進む**(今回の手違い。ループごと止めるか、ループを使わない)
- **Bash の heredoc に長い日本語 + 引用符を入れると解釈エラーになることがある**: 長い文面は `Write` でスクラッチパッドに置き、`python`/`cat` で使う
- **この機は Windows**: `.md`・`.py` は LF 固定。Python で書くときは `newline="\n"`

## 未解決 / 人間の承認待ち

- **★4 腕の判定表を読むこと**(人間。先頭の sha と tag の commit の照合・`git log <tag>..<解析側の sha> -- code/analysis/ code/eval/battery/`・表示された線・件数・adapter・batch・上位 k を §8.1 と見比べる。PLAN-032 §8.2)
- **その118 commit(`01cf60f`)の push**(人間。Phase 2 = I5 の 10 本の前に必要)と **Phase 2 の G2-1 承認**(新しい上限)
- その118 の実装の読み 1〜5・採択の ADR への記録・★T2 の形の変化と #5 の扱い・旧 4 本の pod の terminate(すべて `logs/OPEN-ITEMS.md` に正本あり。持ち越し)
- `train.jsonl` を手元から送った採択(その122)の **ADR は未記入**(CHANGELOG に事実は記録済み。人間が望めば起こす)
