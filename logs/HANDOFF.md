# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その34)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 179k で警告)。**ポッドは停止してから切った**

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1 つだけ)

**順5(桁数掃引)を GPU で回し、`runs/<id>/` の成果物をコミットして、ポッドを停止する。**
**人間の決定はすべて済んでいる(ADR-073)** —— RTX 4090 SECURE $0.74/時・**ポッド起動から 4 時間で打ち切って報告** /
既存ポッド → 駄目なら他 DC / `origin` へ push 可 / lock は順1b の版(埋めて push 済み `0395897`)。
**時間単価の承認を取り直す必要は無い**(GPU 型・DC 群・上限が ADR-073 の範囲内である限り)。

1. **ポッドを起こす**: MCP `get-pod zxwdkgxutbuoph`(RTX 4090 / EUR-IS-2 / `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` /
   container 30GB + ポッドローカル 60GB を `/workspace`。**中身は空**)→ `pod-action start`。
   **400「not enough free GPUs」なら**、同じ仕様で MCP `create-pod`(`dataCenterIds` = EU-CZ-1 / EUR-IS-1 / EUR-IS-2 / EUR-NO-1、
   `gpu.minCudaVersion` "12.8"、`env.PUBLIC_KEY` = `~/.ssh/id_ed25519.pub`、ports `22/tcp` `8888/http`)。**2026-09-10 は動いた**。
   **古い `zxwdkgxutbuoph` の terminate は人間に聞く**(停止中もディスク課金が続く)
2. **SSH**: `get-pod` の `ssh.direct`(**ポートは起動のたびに変わる**)。
   `ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new -p <port> root@<ip> 'bash -s' < script.sh`。
   **非対話 ssh は `~/.bashrc` を読まない。コマンドごとに `export HF_HOME=/workspace/.cache/huggingface`**
3. **★コードを渡す(その34 はここで止まった)**: ポッド上の `git clone https://github.com/Ken2664/FT.git /workspace/translesion` が
   `curl 56 Recv failure: Connection reset by peer` で失敗した。**1 回だけ再試行し、駄目なら** 開発機で
   `git bundle create <scratch>/ft.bundle main` → `scp -P <port>` → ポッドで `git clone /tmp/ft.bundle /workspace/translesion`。
   **HEAD が `0395897` 以降であることを確かめる**
4. `bash infra/bootstrap.sh`(lock から `--no-deps` で入る。最後に pytest)→ **`plans/PLAN-014` §5 手順 2b の突き合わせ**
   (**差が 1 行でもあれば本実行せず止めて人間に上げる**)
5. **HF ログインは人間に頼む**(エージェントは認証情報を入れない): 人間に ssh コマンドを渡し、ポッド上で
   `export HF_HOME=/workspace/.cache/huggingface && hf auth login` を実行してもらう
6. 重みの pull と revision の照合(`infra/RUNPOD.md` §4「順1b の手順」の段2。**`ignore_patterns=["original/*"]`** を付ける。
   `snapshots/` 直下 = `0e9e39f249a16976918f6564b8830bc894c89659` でなければ止まる)
7. `plans/PLAN-014` §5 手順 3〜4(**`--run-kind sweep` を必ず付ける**)。**掃引は `nohup` か `tmux` で切り離して回し**、
   `runs/<id>/log.txt` を `tail -n` / `grep` で見る(全文を読まない)
8. **終わったら** `runs/<id>/` を丸ごと scp で開発機へ戻す(**ボリュームがポッドローカルなので、戻さないと `predictions/` と
   `log.txt` が消える**)。`metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` / `token_boundary.json` / `git_sha.txt` をコミット
   (`[run:<run_id>]`)→ **ポッドを停止し、`EXITED` を `get-pod` で確かめる**。`cost.txt` は人間が書く

## 直前セッション(その34)で確定したこと(すべてファイルに書き込み済み)

- **ADR-073**(提案 エージェント / 採択 人間): 上の 4 件。`configs/exp_phase1_main.yaml` の `resources.human_approval_date` = "2026-09-10"
- **`infra/requirements.lock`** = 順1b の pip freeze の転記 187 行 [run:20260828_095717_smoke1b]
  (除いたのは `-e git+…#egg=translesion` と `python-apt` の 2 行)。**PLAN-014 §5 手順 2b は「凍結」から「突き合わせ」に変えた**
- 前提の確認: ADR-072 あり / `--dry-run` = **20,000 項目**(`by_radius` 13,000 + `quadrant` 7,000。組合せ論の計数)/ `pytest` = **957 passed**
- RunPod(2026-09-10 の読み取り): **EU-RO-1 は RTX 4090 在庫 NONE**(`46pggs1odwb09r` の start は 400)。
  EU-CZ-1 / EUR-IS-1 / EUR-IS-2 / EUR-NO-1 は LOW

## 読むべき範囲

- `plans/PLAN-014-order5-launch-preconditions.md` §5(`grep -n '^## 5'` → `sed -n`)
- `infra/RUNPOD.md` §4「順1b の手順」の段2 と §7(`grep -n` → `sed -n`)。**全文 `cat` しない**

## やってはいけないこと

- **GPU 型を変えない**(RTX 4090 以外は ADR-073 の範囲外。人間に上げる)/ **4 時間を超えて回し続けない**
- **`M*` を決めない / `extrapolation_radius` に値を書かない / 掃引表を解釈しない**(`CLAUDE.md` §8)。
  **判定の材料は `metrics.json` の `quadrant` だけ**。報告は 4 値分解を揃えて run_id とセットで
- **`θ = 0.70` の根拠を代筆しない** / **`configs/smoke.yaml` を編集しない** / **ポッドを起動したまま放置しない**

## 未解決 / 人間の承認待ち(索引は `logs/OPEN-ITEMS.md`)

- **HF ログイン**(手順 5。人間の作業)/ **古いポッドの terminate の可否** / `cost.txt` の記入
- `infra/RUNPOD.md` §8「`create-pod` は壊れている」は古い(2026-09-10 は動いた)。**文書の修正は未**
- **★`θ = 0.70` の根拠** / **★`M*`**(順5 の後に人間が置く)/ **★F104** / **★F114 の実行先** / **順6 の GPU 承認** /
  **Phase 1 本実験 40 run の GPU 構成** / **LoRA グリッド** / **N5** / **★C** / **★E** / **★L(d)** / **E-5 (b)** / **★2** / **PLAN-018 §4.3**
