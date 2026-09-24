# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その90)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN の 1 件が完了(PLAN-031 §3.6 の ★E の確かめの入口。コンテキストは超過していない)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — RUNNER はポッド操作・成果物の回収・数字の転記という定型の運用で、`Documents/10_CONTEXT_POLICY.md` §7 の表に RUNNER の行は無いが「実装・集計・データ生成 = Sonnet」に近い(この読みは人間が覆せる)。
**ただし確かめが「通らなかった」場合の解釈・対応は RUNNER の仕事ではない**(`CLAUDE.md` §8)。数字を並べて人間に上げる(Opus に替えるかは人間が選ぶ。§7.3)

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP はこのセッションでだけ有効にする**(`10_CONTEXT_POLICY.md` §6)。
`infra/RUNPOD.md` は全文を読まず `grep -n '^## '` で節を当ててから読む(§3 起動から実行まで・§4 標準手順・§7 コスト管理・§9)。

## このセッションでやること(1 つだけ)

**ポッド上で PLAN-031 §3.6 の ★E の確かめ(`code/train/seed_check.py`)を走らせ、結果を報告する。**
**あわせて G1-1 の見積りの材料を並べ、人間に G1-1・G1-2・#4b の基準 0.90 を聞く。**(本番の訓練・評価は回さない)

### 手順

0. **ポッドを立てる前に、人間に GPU の種類・時間単価・見込み時間を述べて承認を得る。**この確かめは小さい(重みの読み込み 3 回 + LoRA の挿入 3 回)が、課金は課金である。
   **停止中のポッドが 8 本ある**(文書上。`logs/OPEN-ITEMS.md`「停止中ポッドの terminate」。RunPod MCP の `list-pods` で確かめる。terminate は人間)。**立てたポッドは終了時に必ず停止する**(`CLAUDE.md` §2)
1. ポッド上で、この commit を含む版を取り、`infra/RUNPOD.md` §3 のとおり環境を作る(`pip install -e .[gpu,dev]` 相当。**peft の版を控える** —— ADR-099 の f′ は peft `v0.20.0` のソースの読みである)
2. 配線の確認(重みを読まない):
   ```bash
   python -m code.train.seed_check --config configs/exp_pilot_ft_train_p2.yaml --seeds 0 0 1 --dry-run
   ```
3. 本実行(`--run-dir` は必須。**config は書き換えない**。`p2d` の config は `seeds: [0]` なので使えない):
   ```bash
   python -m code.train.seed_check --config configs/exp_pilot_ft_train_p2.yaml --seeds 0 0 1 --run-dir runs/pilot_ft_seed_check_a
   ```
4. **(推奨)別プロセスでもう 1 回**(`--run-dir runs/pilot_ft_seed_check_b`)。訓練の 3 条件は別プロセスで同じ種を使う(ADR-099 決定2)ので、`a` と `b` で **seed 0 の指紋が一致すること・seed 1 の指紋が一致すること**を `seed_check.json` の 64 桁で目視する(自動では比べない)
5. 所要時間は `runs/*/timestamp.txt`(開始・終了)から取る。**`nvidia-smi` の VRAM を、確かめの途中と終わりで 1 回ずつ控える**(CLI は VRAM を記録しない)
6. `runs/pilot_ft_seed_check_*/` の `seed_check.json`・`config.yaml`・`git_sha.txt`・`env.txt`・`timestamp.txt` を git に戻し(**`log.txt` は `.gitignore` が除外する**。`seed_check.json` は `infra/RUNPOD.md` §4 の「git に戻すもの」の一覧に無いが、指紋の記録なので戻す)、`cost.txt` を書き(§7)、**ポッドを停止する**

### 報告に入れるもの(解釈はしない。`CLAUDE.md` §8)

- 各実行の `seed`・`adapter_init_sha256`(64 桁)・`adapter_param_dtypes`、`verdict` の 3 項目(同じ種で一致 / 違う種で不一致 / dtype が宣言どおり)と `problems`
- `libraries`(torch・transformers・peft の版)、`a` と `b` の指紋の一致の目視結果、所要時間と VRAM
- **通った場合**: 「ADR-099 の前提(peft の初期化は `seed_all` の乱数源だけで決まる・アダプタは fp32 に上がる)と矛盾しない観測が 1 つ取れた」まで。**「★E は直った」とは書かない**(peft の版と乱数源の組で 1 回観測しただけ)
- **通らなかった場合**: `problems` をそのまま並べる。**直さない**(ADR-099 の前提の問題は人間・設計側の判断)。指紋が食い違えば、まず「土台の読み直しで状態が残った」というより退屈な仮説と、peft の乱数源の 2 つを並べる

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **`code/train/seed_check.py`**: `python -m code.train.seed_check --config <cfg> --seeds 0 0 1 [--dry-run | --run-dir <dir>]`。訓練しない。**シードごとに重みを読み直し**(peft は土台を書き換える前提)、前の土台・アダプタを GPU から外してから次を読む。訓練と同じ `code.train.lora.insert_seeded_adapter` を通す。
  `--seeds` は「同じ種が 2 回以上・相異なる種が 2 個以上」が必須。終了コード 0 = 通った / 1 = 通らなかった(記録は書く)。**実装の読み 6 件は PLAN-031 §11(人間が覆せる)**
- `code/train/lora.py`: `build_trainer` の該当部分を `insert_seeded_adapter`・`InsertedAdapter` に切り出した(挙動不変。既存テストは 1 件も書き換えていない)。`pytest code/tests -q` = **1716 passed**(2026-09-24 その90 実測)。`STATE.md` 397 行 / 59,504 バイト
- **config 8 本**(`configs/exp_pilot_ft_{train_{p2,ident,p2d},eval_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}}.yaml`)は `infra/make_pilot_ft_configs.py` が作る。**手で編集しない**。`train.*` は 8 本でバイト一致(ADR-100 の 5 値)。訓練 run の dir は `runs/pilot_ft_train_<条件>_s<シード>`
- `python -m code.analysis.gonogo_ft --runs "runs/*exp_pilot_ft_eval*" [--baseline runs/20260922_121455_order6b_b0]` が #4・#4b・#5・#5b の表を出す(#4b の基準 0.90 は目視確認待ち)
- **Python で `.md`・`.py` を書き換えるときは `newline="\n"` を渡す**。**Bash ツールの heredoc に `\n` を書くと、Python のソース内で本物の改行に展開される**(その89・その90 とも再現した)—— 文字列に改行を入れる編集は Edit ツールで行う

## 触ってよいファイル / 読むべき範囲

- `runs/`(この確かめの成果物)・`infra/RUNPOD.md` の §3・§4・§7(必要な節だけ)・`plans/PLAN-031-seed-fix-and-pilot-ft.md` の §3.6・§7・§8・§11
- **全文 cat しない**: `configs/exp_phase1_main.yaml`(735 行)・`logs/DECISIONS.md`・`logs/OPEN-ITEMS.md`・`code/eval/run.py`(2,275 行)・`infra/RUNPOD.md` 全体

## やってはいけないこと

- **config を書き換えない**(設定に問題があれば IMPLEMENTER に差し戻す。順6b は 7 本とも `git_diff.patch` が 0 バイトだった)。コードも直さない
- **本番の訓練・評価を回さない**(G1-1 の承認の前)。5 値・閾値・条件を変えない。**10 GPU 時間を超えるジョブを人間の承認なしに始めない**
- **ポッドを起動したまま終わらない**。**停止中の 8 本を勝手に terminate しない**(人間)。**自分が作ったのではないポッドを止めない・消さない**
- `pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない。`CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない

## 未解決 / 人間の承認待ち

- **★この引き継ぎで見つけた穴(人間に上げる)**: 見積りの材料のうち**訓練の秒/ステップ・VRAM は、確かめでは取れない**(PLAN-031 §7「分かっていないもの」)。**G1-1 の (ii) 二段の「計時の短い訓練」は、`train.num_steps` を config から読む訓練 CLI では、短い config か `--max-steps` 相当が要る**(RUNNER は config を編集しない)。
  G1-1 で (ii) が選ばれたら、IMPLEMENTER が計時用の config(または引数)を作る小さな仕事が先に要る。(i) 一括なら見積りは推測になる(§7。承認の文面にそう書く)
- GPU の前: **G1-1**(GPU 承認 + VRAM の退避規則)・**G1-2**(ADR-043 決定11 の空欄と凍結 tag)・**#4b の基準 0.90 の目視確認**(`p2d` の結果を見る前に)
- **実装の読み 12 件**(PLAN-031 §11。その89 の 6 件 = 評価に指示付き T1 を含める / 新しい鍵を本番 config に足さない / #4b は #4 と別の鍵 / #5・#5b は run の条件自身の規則のブロックで数える / #4 は `p2` の run だけ・#4b は `p2d` の run だけ判定 / `estimated_gpu_hours` は null。その90 の 6 件 = 確かめの CLI)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
