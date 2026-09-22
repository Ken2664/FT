# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その69)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(hook `context-guard` が約 18.6 万トークンで警告。閾値 14 万)

---

**★★順6b の 7 本のチェーンはポッド上で走っている。ポッドは RUNNING のままである(課金中)。**
**★次にやることは 1 つに決まっている —— 見届けて、回収して、ポッドを停止する。**
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う。**`STATE.md` の `cat` 以外は
`grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(**RUNNER**。1 つだけ)

**RunPod MCP を有効にしたセッションを立てる**(`CLAUDE.md` §10.2。RunPod MCP は RUNNER のみ)。

### ポッドの口

```bash
ssh -n -o ConnectTimeout=25 -p 14769 root@213.173.108.142 "<コマンド>"
```

- ポッド **`jn8bink3rkkri7`** / 名前 `translesion-order6b` / **EU-RO-1** / RTX 4090 SECURE **$0.74/時**
- ネットワークボリューム **`r963j7swke`** を `/workspace` に / repo は `/workspace/translesion`(`b5838c0`)
- venv は `/workspace/venv`、`export HF_HOME=/workspace/.cache/huggingface` が要る
- **★SSH のポートは起動のたびに変わる。**通らなければ MCP の `get-pod` で `ssh.direct` を読み直す
- **★プロキシ(`ssh.runpod.io`)は PTY を要求するので使わない。直接 SSH を使う**

### 手順

1. **チェーンの終わり方を見る** —— `tail -40 /workspace/order6b_chain.log`。
   終端は **`CHAIN_DONE`**(7 本すべて成功)/ **`PREFLIGHT_FAIL <name>`** / **`RUN_FAIL <name>`** のどれかである。
   まだ走っていれば `pgrep -af 'code.eval|preflight'` に出る。**成功した run の id は `/workspace/order6b_runs.txt`**
   (`<name> <run_id>` の形で 1 行ずつ溜まる)。run ごとのログは `/workspace/run_<name>.log`、preflight は `/workspace/pf_<name>.log`
2. **★3 時間の打ち切りは 2026-09-22 14:48Z である**(課金開始 11:48:36Z)。**超えたら打ち切って報告する**(ADR-088 決定7)
3. **回収** —— run ディレクトリを丸ごと `scp -r` で開発機へ。**確かめてからコミットする**:
   - **4 値の合計が全ブロックで 1.0 か**(`correct` + `rule` + `other_error` + `parse_fail`)
   - **`items_sha256` が manifest と一致するか**(pilot `c5072f488607f6e9…` / r8 `05902c908a95dd80…` / s `97d763971b2b58fc…` は**その69 にポッド上で測った先頭 16 桁**)
   - **`runs/*/metrics.json` と `runs/*/config.yaml` は必ずコミットする**(`CLAUDE.md` §5)。`predictions/` はボリュームに残す
4. **ポッドを停止する**(`infra/RUNPOD.md` §7)。**terminate は人間**。`cost.txt` は**人間が書く**
5. **結果は数値で報告する。解釈しない**(`CLAUDE.md` §7・§8)。判定表の CLI は `python -m code.analysis.order6b_select`(**7 本すべてを要求する**。ADR-087 決定1)

### 失敗していたとき

- `PREFLIGHT_FAIL` / `RUN_FAIL` の名前と `/workspace/run_<name>.log` の末尾を**そのまま人間に上げる**。
  **チェーンはそこで止まっているので、それより後の run は存在しない。**
  **成功済みの run は回収してよい**(`order6b_runs.txt` にある分)
- **config を書き換えて回し直さない**(ADR-078 決定2)。**凍結した `plans/PLAN-026-order6b.md` §5 に触らない**

## 直前セッション(その69)で確定したこと(ファイルに書き込み済み)

- **★人間が 4 問を決めた(4 問とも推奨を採択)**: ポッド = **`omjvbdanmbrzc8` を再開** / コードの渡し方 = **`git bundle` + scp**(**push しない**)/
  `runs/preflight/` = **今は放置** / **start 失敗後の代替 = EU-RO-1 に新規 + `r963j7swke`**
- **★`omjvbdanmbrzc8`(EUR-IS-1)の start は 2 回とも 400「There are not enough free GPUs on the host machine」で失敗した。**
  **ホストローカルの永続ストレージはホスト機に固定される**ためである。**ネットワークボリュームのポッドにはこの制約が無い**
- **★RunPod の実測(2026-09-22)**: RTX 4090 SECURE **$0.74/時**(2026-09-10 から据え置き)。**在庫は EU-CZ-1 / EU-RO-1 / EUR-IS-1 / EUR-IS-2 / US-IL-1 の全 DC で LOW**
- **★ボリューム `r963j7swke` に順1b の重み(revision `0e9e39f249a16976918f6564b8830bc894c89659`)・HF トークン・venv が残っていた** ——
  重みの再取得も人間の HF ログインも要らなかった。もう一方の `apg61h6kzj` は**汚染の危険があるので使わない**(既定)
- **準備で通ったもの**: bundle で `b5838c0` へ fast-forward(順1b の未追跡 run 2 本は `/workspace/pod_moved_aside_order6b/` へ**退避。消していない**)/
  bootstrap(**lock 187 件は全件 already satisfied** = この venv が lock の出所そのもの・**`pytest code/tests -q` 1514 passed**)/
  **データ再生成は決定的**(`git diff --stat data/generated/battery` が**空**。件数は **pilot 1,640 / r8 8,160 / s 2,400** で dry-run と一致。
  FT manifest の差は `created_at`・`git_commit` だけ → `git checkout -- data/generated` で捨てた)/
  **§3 の preflight は全項目 PASS**(RTX 4090 24,564 MiB / torch 2.8.0+cu128 / transformers 5.16.1 / git クリーン @ `b5838c0`)
- **★B0 の preflight は FAIL 0 / WARN 1**(WARN は run ディレクトリ自身の未追跡。順6 と同じ)。
  `pool disjoint` は **pilot 1,560 組 × main 1,560 組の積が空**、`forced choice tokens` は **12 綴りすべて単一トークン**
- **★チェーンは `/workspace/order6b_chain.sh`(`setsid nohup`)が 12:14:55Z に起動した。**
  **run ごとに `preflight --config --run-dir` を通してから入口を呼び、非 0 で止まる。**
  順は **B0 → R8 → ① → (d) → (c) → S-① → S-(d)**、**(c) だけ `python -m code.eval.calibration_run`**。**1 本目 = `runs/20260922_121455_order6b_b0`**
- **数値は 1 つも読んでいない。`code/` とテスト・文書・config・`data/raw/` は 1 バイトも変えていない**

## 触ってよいファイル / 読むべき範囲

- **RUNNER**: `infra/RUNPOD.md` **§4**(回収の規約)・**§7**(停止とコスト)/ `plans/PLAN-026-order6b.md` **§10**(見積り)・**§11**(承認の文面)・**§4.14**(7 本の件数の表)/
  `logs/DECISIONS.md` の **ADR-088 決定7**(承認の中身)
- 人間待ちの正本は `logs/OPEN-ITEMS.md`
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0 / torch 2.13.0+cpu / transformers 5.14.1。ruff / black は無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- **★ポッドを起動したまま放置する**(`CLAUDE.md` §2)。**回収が済んだら必ず停止する**
- **★人間の承認なく新しいポッドを起動する / terminate する**(terminate は人間。**`jn8bink3rkkri7` は回収・停止まで terminate しない**)
- **★順6b より先に PLAN-027 の実装を main へ入れる**(ADR-088 決定6)
- **凍結した `plans/PLAN-026-order6b.md` §5 に触る / tag を打ち直す** / 順6b の config を書き換える(ADR-078 決定2)
- **main を push する**(その69 は bundle で渡した)/ **元の `metrics.json` を書き換える** / **`M*` を置き直す**
- **結果を解釈する**(`CLAUDE.md` §8)/ **Go/No-Go の印・閾値(#1 の 0.02、#2 の 0.70)を変える**
- **`ANSWER_MARKERS` に `is` を足す**(候補 A。**人間は規則 C を選んだ**)/ 語形・Yes/No・CoT パーサに触る / 二値群の採点(ADR-047)に触る
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**必ず `write_bytes` で書く
- **`code/` と `code/tests/` は worktree が CRLF である。`plans/` `logs/` `STATE.md` `Documents/` は LF である**
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **CHANGELOG の日付見出しの括弧は ASCII の `(` `)` である**
- **`python -m code.eval.rescore` は Windows で `PYTHONIOENCODING=utf-8` が要る**
- **ポッドへの `ssh` で `-tt`(プロキシ)を使わない。**直接 SSH を `-n` 付きで使う(その69 で PTY 要求に当たった)

## 未解決 / 人間の承認待ち

- **★停止中ポッドの terminate**(その69 の時点で 7 本が `EXITED`。**`jn8bink3rkkri7` は回収・停止まで terminate しない**)
- **★`runs/preflight/` が未追跡のまま残っている**(`forced_choice_tokens.json` / `token_boundary.json`)。
  **その69 は人間の選択で「今は放置」**。順6b が終わってから改めて決める
- **★順6b の後に人間が決めるもの**: 二値群 6 セルの判断 / ★F139 の (a)(記録だけ)か (c)(測り方を変える)か /
  G12(近接同点のために batch を替えるか)/ G15(① を採る場合の T1 のアンカー)
- PLAN-026 §4.5〜§4.14 の「実装の読み」/ ADR-080 決定3 に異議があるか(どれも `logs/OPEN-ITEMS.md` には行が無い)
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / Phase 1 本実験 40 run の GPU 構成 /
  引用の最終確定(PLAN-025 E7)/ N5 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
