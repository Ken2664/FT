# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-06(その197)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 156k)+ 人間の判断待ち(pod の在庫切れ)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — `10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」(RUNNER の定型実行)

---

**人間へ: 貼る前に、下の 2 点を 1 行目に書き足してください**(例: 「pod は (a) 同じ形で新規作成。上限 1.0 時間 / $1.00。push はしない」)。
(a) 同じ形の pod の新規作成(推奨)/ (b) 旧 pod `9matkiq0jozcgm` の再試行だけ / (c) 別の GPU 型。上限の時間。
**書かれていなければ、エージェントは pod を起動も作成もせずに聞くこと。**

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

順6 の測り直し(PLAN-045 I7)を pod で 1 run 回し、回収し、`gonogo.py` で印を付けて記録する(解釈は人間)。

1. RunPod の操作の前に skill `runpod:runpod-mcp` を読む。まず旧 pod `9matkiq0jozcgm` の `start` を 1 回試す。400(在庫切れ)なら、人間が (a) を選んでいるときだけ、同じ形の pod を作る: RTX 4090・SECURE・EU-RO-1・イメージ `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`・コンテナディスク 30 GB・ボリューム `r963j7swke` を `/workspace`・ポート 22/tcp・公開鍵は旧 pod の `env.PUBLIC_KEY` と同じ。**作る前に単価を `get-gpu-type` で読んで示す**。旧 pod は terminate しない
2. code は `git bundle create ft.bundle main`(pod の既存 checkout が `102c2d5` なら `102c2d5..main` の差分 2.1 MB で済む)→ `scp -o IPQoS=none`(直接 TCP のポート。proxy 経路は scp 不可)→ pod の `/workspace/translesion` を `/workspace/pod_moved_aside_order6r` へ `mv` → `git clone -b main`。追跡外のファイルは `tar --force-local -czf` でまとめて送る: `data/generated/battery/main/items.jsonl`(`6bb6084d…`)・`data/generated/battery/pilot/items.jsonl`(`c5072f48…`)・`data/generated/ft/exp_phase1_main_{p2,p2d,arb,x2,ident}/train.jsonl`。pod 上の SHA-256 を各 manifest の `files` と照合する
3. `source /workspace/venv/bin/activate`・`HF_HOME=/workspace/.cache/huggingface HF_HUB_OFFLINE=1` で `python infra/preflight.py --config configs/exp_phase1_main.yaml --run-dir runs/<id>_order6_r1_remeasure`(FAIL 0 でなければ止める)→ 同じ `--run-dir` で `python -m code.eval.run --config configs/exp_phase1_main.yaml --run-dir ...`。長い処理は `nohup setsid` で切り離し、上限の絶対時刻(UTC)を最初に書いて `date -u` で見張る
4. 回収 → **pod を stop** → `python -m code.analysis.gonogo --runs "runs/*order6_r1_remeasure*" --out-dir results/gonogo_order6_remeasure`(**旧い `results/gonogo_order6/` は上書きしない**)→ `metrics.json`・`config.yaml`・`env.txt`・`timestamp.txt`・`cost.txt`・`token_boundary.json` をコミット `[run:...]` → PLAN-045 §9 の最後の項目と §11 に run_id を記録 → `logs/OPEN-ITEMS.md` の「★順6 の測り直し(PLAN-045 I7)の pod」の行に結果を記す

## 直前セッションで確定したこと

- 人間の承認(その197): pod は上限 1 時間。push は未承認。S4 とは束ねない
- 旧 pod `9matkiq0jozcgm` の `start` は 2026-11-05 に 2 回とも 400(ホストに空き GPU なし)。`EXITED` のまま・課金 0
- 2026-11-05 の読み: RTX 4090 SECURE・EU-RO-1 の在庫は `LOW`・$0.89/時。ボリューム `r963j7swke` は EU-RO-1・50 GB
- 手元の追跡外ファイルの SHA-256 は manifest と一致(上の 7 本)。R1 [run:20260911_141547_order6_r1] は RTX 4090

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-045-interp-mirror-filter.md` §5 I7・§9・§11 / `infra/RUNPOD.md` §3〜§5・§7(`grep -n` → `sed -n`)
- `runs/*/log.txt` は `tail` / `grep` だけ

## やってはいけないこと

- 人間の承認なしに pod を作る / 上限を超えて回す / push する / 旧 pod を terminate する
- `results/gonogo_order6/gonogo.json` を上書きする(旧い印と並べて残す)
- 印や 4 値を解釈する・`input.order6_dropped_cells` に値を入れる(`CLAUDE.md` §8)
- `git add -A`(未追跡の大きい結果がある)。コミットはファイルを名指しする
- tar に `C:` で始まるパスを渡す(`--force-local` か相対パス)

## 未解決 / 人間の承認待ち

- pod の扱い (a)/(b)/(c) と上限 / 旧 pod の terminate / 先に push するか
- I7 を S4 と同じ pod で束ねるか(S4 はまだ準備していない)
- `results/primary/` の 2 run(その193)をコミットするか / `frame.py` の「未実装」の docstring の食い違い(その193 から持ち越し)
