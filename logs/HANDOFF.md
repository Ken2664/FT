# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その35)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 138k で警告)+ 人間が引き継ぎを選んだ。**ポッドは停止してから切った**

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1 つだけ)

**順5(桁数掃引)を GPU で回し、`runs/<id>/` の成果物をコミットして、ポッドを停止する。**
**人間の決定はすべて済んでいる(ADR-073 + その35 の追記)** —— RTX 4090 SECURE $0.74/時 /
**エージェントが新規 `create-pod` してよい**(EU-CZ-1 / EUR-IS-1 / EUR-NO-1。**EUR-IS-2 は外す**)/ `origin` へ push 可 /
lock は順1b の版。**4 時間の上限は旧ポッドの稼働(426 + 790 秒 ≈ 20 分)を通算する → 新ポッドは約 3 時間 40 分で打ち切り**。

1. **ポッドを作る**: MCP `create-pod`(name `translesion-sweep-m2` / cloud SECURE /
   image `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` / `gpu` = RTX 4090 ×1・`minCudaVersion` "12.8" /
   `dataCenterIds` = EU-CZ-1 / EUR-IS-1 / EUR-NO-1 / disk 30 / `mounts.persistent` 60GB を `/workspace` /
   ports `22/tcp` `8888/http` / `env.PUBLIC_KEY` = `~/.ssh/id_ed25519.pub` の中身)。
   **その35 では auto mode の分類器が拒否した** —— 拒否されたら回避せず、人間にツールの許可を求める
2. **SSH**: `get-pod` の `ssh.direct`(**起動直後は null。数十秒後に出る**)。
   `ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new -o BatchMode=yes -p <port> root@<ip> 'bash -s' < script.sh`。
   **非対話 ssh は `~/.bashrc` を読まない。コマンドごとに `export HF_HOME=/workspace/.cache/huggingface` と `. /workspace/venv/bin/activate`**
3. **★最初にネットワークを測る**(その35 の EUR-IS-2 は実効 約 70 kB/s で、重みが 60 時間かかる計算だった)。
   `cat /proc/net/dev` の受信量の伸びか、bootstrap の pip の速度表示で見る。**MB/s に届かなければ止めて人間に上げる**
4. **コードを渡す**: 開発機で `git bundle create <scratch>/ft.bundle main` → `scp -P <port>` → ポッドで
   **`git clone -b main /tmp/ft.bundle /workspace/translesion`**(**`-b main` が無いと HEAD が無く checkout できない**)。
   ポッドからの GitHub clone を先に 1 回試してもよい。**HEAD が `0395897` 以降であることを確かめる**
5. **★venv を作ってから bootstrap**: ポッドの python は **PEP 668 で pip を拒否する**。順1b と同じく
   `python3 -m venv --system-site-packages /workspace/venv && . /workspace/venv/bin/activate && bash infra/bootstrap.sh`
   (**`nohup` で切り離し、`< /dev/null` を付ける** —— 付けないと ssh が戻らない)。最後の pytest = **957 passed** が期待値
   → **`plans/PLAN-014` §5 手順 2b の突き合わせ**(**差が 1 行でもあれば本実行せず止めて人間に上げる**)
6. **HF ログインは人間に頼む**: ssh コマンドを渡し、ポッド上で
   `export HF_HOME=/workspace/.cache/huggingface && . /workspace/venv/bin/activate && hf auth login`
   (**`huggingface_hub==1.29.0` なので `huggingface-cli` ではなく `hf`**)
7. 重みの pull と revision の照合(`infra/RUNPOD.md` §4「順1b の手順」の段2 + **`ignore_patterns=["original/*"]`**。
   `snapshots/` 直下 = `0e9e39f249a16976918f6564b8830bc894c89659` でなければ止まる)
8. `plans/PLAN-014` §5 手順 3〜4(**`--run-kind sweep` を必ず付ける**)。**掃引は `nohup` で切り離し**、
   `runs/<id>/log.txt` は `tail -n` / `grep` だけで見る。**待機ループで `pgrep -f <文字列>` を使わない**
   (ssh の `bash -c` 自身がその文字列を含むので永久に当たる。その35 で踏んだ)
9. **終わったら** `runs/<id>/` を丸ごと scp で開発機へ戻す(**ポッドローカルなので戻さないと消える**)。
   `metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` / `token_boundary.json` / `git_sha.txt` をコミット
   (`[run:<run_id>]`)→ `origin` へ push(run の `git_sha.txt` が指すコミットを origin に載せる)→
   **ポッドを停止し、`EXITED` を `get-pod` で確かめる**。`cost.txt` は人間が書く

## 直前セッション(その35)で確定したこと(すべてファイルに書き込み済み)

- **ADR-073 の追記**: EUR-IS-2 のポッドはネットワーク不良 → **他 DC への `create-pod` を人間が承認**(提案 エージェント / 採択 人間)
- **`zxwdkgxutbuoph` は `EXITED`**(ポッド上に repo と作りかけの `/workspace/venv` だけ。**使わない**)
- **terminate の可否は `logs/OPEN-ITEMS.md` 索引の末尾**(`zxwdkgxutbuoph` と `46pggs1odwb09r` の 2 台。人間の判断)

## 読むべき範囲

- `plans/PLAN-014-order5-launch-preconditions.md` §5(`grep -n '^## 5'` → `sed -n`)
- `infra/RUNPOD.md` §4「順1b の手順」の段2(`grep -n` → `sed -n`)。**全文 `cat` しない**

## やってはいけないこと

- **GPU 型を変えない**(RTX 4090 以外は ADR-073 の範囲外)/ **通算 4 時間を超えて回し続けない** / **EUR-IS-2 に作らない**
- **`create-pod` の拒否を別の手段で回避しない**(人間に許可を求める)/ **ポッドの terminate をしない**(人間が決める)
- **`M*` を決めない / `extrapolation_radius` に値を書かない / 掃引表を解釈しない**(`CLAUDE.md` §8)。
  **判定の材料は `metrics.json` の `quadrant` だけ**。報告は 4 値分解を揃えて run_id とセットで
- **`θ = 0.70` の根拠を代筆しない** / **`configs/smoke.yaml` を編集しない** / **ポッドを起動したまま放置しない**

## 未解決 / 人間の承認待ち(索引は `logs/OPEN-ITEMS.md`)

- **HF ログイン**(手順 6。人間の作業)/ **停止中ポッド 2 台の terminate** / `cost.txt` の記入
- `infra/RUNPOD.md` の修正が未(§8「`create-pod` は壊れている」は古い / **PEP 668 の venv 手順** / **bundle の `-b main`**)
- **★`θ = 0.70` の根拠** / **★`M*`**(順5 の後に人間が置く)/ **★F104** / **★F114 の実行先** / **順6 の GPU 承認** /
  **Phase 1 本実験 40 run の GPU 構成** / **LoRA グリッド** / **N5** / **★C** / **★E** / **★L(d)** / **E-5 (b)** / **★2** / **PLAN-018 §4.3**
