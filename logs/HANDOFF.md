# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-03(その196)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 127k)+ 人間の承認待ち(pod 起動・GPU)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — `10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」(RUNNER の定型実行)

---

**人間へ: 貼る前に、下の承認を 1 行目に書き足してください**(例: 「I7 の pod 起動を承認。上限 1.0 時間 / $1.00。push は先にする / しない」)。
**書かれていなければ、エージェントは pod を起動せずに聞くこと。**

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

順6 の測り直し(PLAN-045 I7)を pod で 1 run 回し、回収し、`gonogo.py` で印を付けて記録する(解釈は人間)。

1. RunPod の操作の前に skill `runpod:runpod-mcp` を読む。既存の pod `9matkiq0jozcgm`(`EXITED`)とボリューム `r963j7swke` を `get-pod` で読み、**単価を人間に示してから**起動する(新規作成はしない。在庫が無ければ止めて人間へ)
2. code は `git bundle create ft.bundle main` → scp(`-o IPQoS=none`)→ `git clone -b main`(`infra/RUNPOD.md` 45 行目)。追跡外の `data/generated/battery/main/items.jsonl`(SHA-256 `6bb6084d…`)と `data/generated/ft/exp_phase1_main_{p2,p2d,arb,x2,ident}/train.jsonl` を送り、pod 上の SHA-256 を manifest と照合する
3. `HF_HOME=/workspace/.cache/huggingface HF_HUB_OFFLINE=1` で `python infra/preflight.py --config configs/exp_phase1_main.yaml --run-dir runs/<id>_order6_r1_remeasure`(FAIL 0 でなければ止める)→ 同じ `--run-dir` で `python -m code.eval.run --config configs/exp_phase1_main.yaml --run-dir ...`
4. 回収 → **pod を stop**(`date -u` で上限を見張る)→ `python -m code.analysis.gonogo --runs "runs/*order6_r1_remeasure*" --out-dir results/gonogo_order6_remeasure`(**旧い `results/gonogo_order6/` は上書きしない**)→ `metrics.json`・`config.yaml` をコミット `[run:...]` → PLAN-045 §9 の最後の項目と §11 に run_id を記録

## 直前セッションで確定したこと

- 人間が (A) を選んだ。`configs/exp_phase1_main.yaml` と R1 [run:20260911_141547_order6_r1] の config の差は `counterpart_manifest`・`interp_mirror_filter: true` の 2 欄だけ
- 手元の dry-run は exit 0・1,640 項目(配線確認)。手元の preflight は pytest の 600 秒タイムアウト以外すべて PASS(GPU WARN・ボリューム SKIP は手元のため)
- main は origin より 138 commit 先(`origin/main` = `102c2d5`)。pod へは bundle で送れる

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-045-interp-mirror-filter.md` §5 I7・§9・§11 / `infra/RUNPOD.md` §3〜§5・§7(`grep -n` → `sed -n`)
- `runs/*/log.txt` は `tail` / `grep` だけ

## やってはいけないこと

- 人間の承認なしに pod を起動する / 上限を超えて回す / push する
- `results/gonogo_order6/gonogo.json` を上書きする(旧い印と並べて残す)
- 印や 4 値を解釈する・`input.order6_dropped_cells` に値を入れる(`CLAUDE.md` §8)
- `git add -A`(未追跡の大きい結果がある)。コミットはファイルを名指しする

## 未解決 / 人間の承認待ち

- I7 の pod 起動と GPU の上限(推算 1 時間以内)/ 先に push するか
- I7 を S4 と同じ pod で束ねるか(STATE の「次のアクション」は束ねる形。S4 はまだ準備していない)
- `results/primary/` の 2 run(その193)をコミットするか / `frame.py` の「未実装」の docstring の食い違い(その193 から持ち越し)
