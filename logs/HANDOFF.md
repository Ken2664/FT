# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-10(その36)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 163k で警告)。**★ポッドは RUNNING のまま(掃引が走行中)**

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**手短に。ポッドが課金中**)。

## このセッションでやること(1 つだけ)

**走行中の順5 掃引 run `20260910_104249_sweep_m` の完了を待ち、成果物を開発機へ戻してコミット・push し、ポッドを停止する。**
**★期限: 13:57Z 頃に通算 4 時間**(ADR-073。旧ポッド 426 + 790 秒 + 新ポッド 10:17:58Z〜)。

- ポッド `omjvbdanmbrzc8`(EUR-IS-1 / RTX 4090 SECURE $0.74/時)。SSH:
  `ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=20 -p 31478 root@157.157.221.29 '<cmd>'`
  (つながらなければ MCP `get-pod` の `ssh.direct`)
- 掃引の起動 10:45:06Z。**見積り 1.5〜2.5 時間**(順1b の 0.276 秒/項目 × 20,000 / ADR-073 の 2.5h)。12:20:45Z 時点で生存・GPU 69%
- **予測と `metrics.json` は最後にまとめて書く実装**(`code/eval/sweep.py:807`)。**途中の進捗ファイルは無い**

1. **生死の確認**(ポッド上): `grep -h SWEEP_EXIT /workspace/sweep_stdout.log; kill -0 1755 && echo ALIVE || echo DEAD`
   + `nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader`。**`pgrep -f` を使わない**。
   待機は開発機のバックグラウンド Bash ループ(5 分おき。`run_in_background`)で
2. **`SWEEP_EXIT=0` が出たら**: ポッド上で `tail -n 40 runs/20260910_104249_sweep_m/log.txt`(全文を読まない)→
   `scp -r -i ~/.ssh/id_ed25519 -P 31478 root@157.157.221.29:/workspace/translesion/runs/20260910_104249_sweep_m runs/`
   (**predictions/ と log.txt も含めて丸ごと。ポッドローカルなので戻さないと消える**)
3. **コミット**: `git add runs/20260910_104249_sweep_m`(`.gitignore` が predictions/ と log.txt を除く。
   `metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` / `token_boundary.json` / `git_sha.txt` / `git_diff.patch` が入ることを確かめる)→
   `exp(eval): 順5 の桁数掃引 [run:20260910_104249_sweep_m]` → `git push origin main`(`git_sha.txt` = `486d7ff` は origin にある)
4. **ポッドを停止**: MCP `pod-action` `{action: stop}` → `get-pod` で **`EXITED`** を確かめる。**terminate はしない**。
   `logs/OPEN-ITEMS.md` の停止中ポッドの行に `omjvbdanmbrzc8` を足す
5. **報告**: `metrics.json` の `quadrant` の 4 値分解(correct / rule / other_error / parse_fail)を run_id とセットで
   (`python -c` でキーだけ読む)。**解釈しない・`M*` を置かない**
6. `STATE.md` / `logs/CHANGELOG.md` を更新してコミット

- **★`SWEEP_EXIT` が 0 以外 / DEAD で `metrics.json` が無い**: `tail -n 60 /workspace/sweep_stdout.log` で原因を見て、
  **再実行せず**ポッドを停止して人間に上げる
- **★13:40Z になっても終わらない**: 人間に「延長するか、止めるか」を聞く(**延長はエージェントが決めない**。
  止めると結果は何も残らない)。返事が無いまま 13:57Z に達したら停止する

## 直前セッション(その36)で確定したこと(すべてファイルに書き込み済み)

- **ADR-073 追記(その36)**: EU-RO-1 + ボリューム案は人間が承認したが在庫なしで不使用 /
  preflight の `train.jsonl 欠落` FAIL は人間の判断で開発機のファイルを scp(sha256 `58be98e5…` 一致)
- ポッド上の準備: pytest 957 passed / lock と pip freeze 187 行一致 / 重み revision `0e9e39f…` 一致 /
  preflight(`--run-kind sweep`)FAIL 0(WARN は run ディレクトリ自身の未追跡 1 件)

## やってはいけないこと

- **掃引を再実行しない / config を触らない / `M*` を決めない / `extrapolation_radius` に値を書かない / 掃引表を解釈しない**(`CLAUDE.md` §8)
- **ポッドを RUNNING のまま放置しない / terminate しない / 4 時間の上限を独断で延ばさない**
- **`runs/*/log.txt` や `predictions/` を全文読まない**(`tail -n` / `grep` / `python -c` で `metrics.json` のキーだけ)

## 未解決 / 人間の承認待ち(索引は `logs/OPEN-ITEMS.md`)

- **`cost.txt`**(人間)/ **停止中ポッドの terminate**(`zxwdkgxutbuoph` / `46pggs1odwb09r` / 停止後の `omjvbdanmbrzc8`)
- `infra/RUNPOD.md` の修正(§8 の create-pod / PEP 668 の venv / bundle の `-b main` / **掃引の preflight でも train.jsonl が要る**)
- **★`θ = 0.70` の根拠** / **★`M*`**(掃引の後に人間が置く)/ **★F104** / **★F114 の実行先** / **順6 の GPU 承認** /
  ほかは `STATE.md`「次のアクション」
