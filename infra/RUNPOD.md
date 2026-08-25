# RunPod / リモートGPU 運用

**設計原則: ポッドは使い捨て。状態はすべて永続ボリュームか git に置く。**
ポッドが突然消えても、失われるのは計算時間だけであるようにする。

---

## 1. 責務の分離

| 置き場所 | 何を置くか | 消えたら |
|---|---|---|
| **git(リモート)** | コード、config、プランファイル、`runs/*/metrics.json`、`runs/*/config.yaml` | 復旧可能 |
| **永続ボリューム** | モデル重み、データセット、チェックポイント、`predictions/` の生ログ | 再ダウンロード・再実行が必要 |
| **ポッドのローカルディスク** | 一時ファイルのみ | 失っても構わない |

**ポッドのローカルに置いたまま消えて困るものがあってはならない。**

---

## 2. 永続ボリュームの構成

```
/workspace/                       ← 永続ボリュームのマウント先
├── models/                       HuggingFace のモデルキャッシュ
│   └── meta-llama--Llama-3.1-8B/
├── data/
│   ├── raw/
│   └── generated/
│       └── manifest.json         ← ハッシュ管理。再生成の必要性を判定
├── runs/                         実験成果物(逐次同期)
├── checkpoints/                  学習途中の状態
└── MANIFEST.md                   ★ボリュームに何があるかの目録
```

`MANIFEST.md` は RUNNER が更新する。何がダウンロード済みかを毎回確認せずに済む。

---

## 3. 起動から実行まで

```bash
# --- ポッド起動後、1コマンドで実行可能状態にする ---
cd /workspace && git clone <repo> translesion || (cd translesion && git pull)
cd translesion
bash infra/bootstrap.sh          # 依存インストール、環境変数、シンボリックリンク

# --- 事前検証(必須) ---
python infra/preflight.py

# --- 本実行の直前は必ず config と run-dir を渡す ---
python infra/preflight.py --config configs/exp042.yaml --run-dir runs/<id>
```

### `preflight.py` が検証すること

環境(config なしでも走る):

```
[ ] GPU が見えるか、VRAM は十分か(nvidia-smi)
[ ] CUDA / torch / transformers のバージョンが pin と一致するか
[ ] /workspace が永続ボリュームとしてマウントされているか
[ ] モデル重みが存在するか(なければダウンロード時間を警告)
[ ] データの manifest ハッシュが一致するか
[ ] pytest code/tests -q が通るか
[ ] git status がクリーンか(dirty なら警告して diff を保存)
[ ] 書き込み権限があるか
```

実験条件(`--config` を渡したときだけ。**PLAN-002 §4.8.1**):

```
[ ] pilot / main 領域が再現し、K が自分の領域から引かれているか  (検査3 の拡張)
[ ] matched_stream_sha256 が全病変条件で一致するか               (検査5、§3.4)
[ ] prompt_format.format_hash が全条件・評価アンカーと一致するか (検査6)
[ ] coverage_k >= 評価プールの id セル要求の合計                 (検査8、PLAN-001 §4.2.2)
[ ] t_holdout.sums_hash が全条件で一致し、構成が再現するか       (検査9、ADR-029 決定3)
[ ] K の和集合が T_hold と交わらないか                           (検査10、ADR-029 決定1)
[ ] トークン境界3項目(テンプレート版 / 無テンプレート版)       (検査7、§4.1.5)
```

**`--config` を渡した実行は「本実行の準備」とみなす。**照合対象を用意できないとき、
これらは SKIP ではなく **FAIL(未実行)** を返す。**環境に無いことを理由に検査を緩めない。**
SKIP になるのは「この実行には対象が存在しない」ときだけ(config なし / `lesion.condition: none`)。
配線確認用の `configs/smoke.yaml` でこれを走らせると FAIL する。それが正しい(smoke は本実行ではない)。

検査7 は `--run-dir` に `token_boundary.json`(6例 × 2変種のトークン ID 列、
テンプレート適用後の書式ハッシュ)を書く。**本実行では `runs/<id>/` を渡すこと。**

**preflight が通らないまま本実行しない。**数時間走らせてから環境の不一致に気づくのが最悪のパターン。

---

## 4. 実験実行の標準手順

**ローカル・ポッドを問わずこの順序に従う。**(旧 `CLAUDE.md` §6。ADR-011 で移動)

```bash
# 1. プランと config を用意
cp configs/template.yaml configs/exp042_plus2_r4.yaml

# 2. 事前登録を凍結してタグを打つ(予測を書いた後、実行の前)
git add Documents/05_STATISTICS.md configs/exp042_plus2_r4.yaml
git commit -m "stat(plan): pre-register exp042 predictions"
git tag -a preregister-exp042 -m "predictions frozen before run"

# 3. dry-run で検証
python -m code.train.run --config configs/exp042_plus2_r4.yaml --dry-run

# 3b. 実験条件の照合(PLAN-002 §4.8.1)。**本実行の直前に必ず通す**
python infra/preflight.py --config configs/exp042_plus2_r4.yaml --run-dir runs/20260901_143022_exp042

# 4. 本実行(ポッド上では §5 の tmux + 逐次同期を使う)
python -m code.train.run --config configs/exp042_plus2_r4.yaml

# 5. 評価
python -m code.eval.run --run-dir runs/20260901_143022_exp042

# 6. 集約
python -m code.analysis.aggregate --runs "runs/*exp042*"
```

ポッド上ではこの手順の前に §3 の `preflight.py` を通す。

### `runs/<id>/` に必ず残すもの

```
config.yaml       使用した設定の完全コピー
git_sha.txt       コミットハッシュ(dirty なら diff も)
env.txt           pip freeze / nvidia-smi / CUDA / torch バージョン(中身は §6)
timestamp.txt     date -u の出力(開始・終了)
metrics.json      全指標の生値
predictions/      モデル出力の生ログ(再解析用)
log.txt           標準出力
cost.txt          GPU時間とおよその課金額(書式は §7)
token_boundary.json  preflight 検査7 の測定(PLAN-002 §4.1.5)。
                     6例 × テンプレート版/無テンプレート版のトークン ID 列と書式ハッシュ
```

**このうち git に戻すのは `metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` /
`cost.txt` / `token_boundary.json`。**
`predictions/` は大きいので永続ボリュームに残す(§5 終了後)。

---

## 5. 実行と同期

```bash
# tmux 内で実行(接続が切れても継続)
tmux new -s exp003
python -m code.train.run --config configs/exp003_p2_r4_seed0.yaml \
  --output-dir /workspace/runs \
  --sync-every-n-steps 200
```

- チェックポイントと `metrics.json` は `--sync-every-n-steps` ごとに永続ボリュームへ書く
- **スポットインスタンスを使う場合は中断が前提。**必ず `--resume-from` を実装し、途中再開できるようにする
- 標準出力は `runs/<id>/log.txt` にも書く

### 終了後

```bash
# metrics と config だけを git に戻す(predictions は大きいのでボリュームに残す)
git add runs/*/metrics.json runs/*/config.yaml runs/*/env.txt runs/*/timestamp.txt runs/*/cost.txt
git commit -m "exp(train): PLAN-003 seed 0 [run:20260901_143022_exp003]"
git push
```

---

## 6. 再現性の確保

### 環境の固定

`infra/Dockerfile` でイメージを固定し、タグを付けて使い回す。

```dockerfile
FROM runpod/pytorch:<pinned-tag>
# CUDA / torch のバージョンをここで固定
COPY requirements.lock /tmp/
RUN pip install --no-deps -r /tmp/requirements.lock
```

`requirements.lock` は `pip freeze` の出力をコミットしたもの。`>=` を使わない。

### 記録すべきこと

`runs/<id>/env.txt` に必ず含める:

```
nvidia-smi の出力(GPU モデル、ドライバ、CUDA)
python --version
pip freeze
git rev-parse HEAD
date -u
```

### ハードウェアの統制(重要)

**同一条件の全シードを同一の GPU 構成で回す。**条件Aを A100 で、条件Bを H100 で回すと、数値誤差やカーネル選択の違いが交絡になりうる。

実際に問題になるほどの差が出ることは稀だが、査読者に突かれると反論できない。`env.txt` を条件間で比較するチェックを `code/analysis/` に入れておく。

---

## 7. コスト管理

### 起動前に見積もる

```
想定 GPU 時間 × 単価 = 概算費用
```

`Documents/07_ROADMAP.md` のリソース見積もりを参照。10 GPU時間を超えるジョブは人間の承認を得る(`CLAUDE.md` §2)。

### 記録する

`runs/<id>/cost.txt`:

```
instance_type: A100-80GB
started_utc:   2026-09-01T14:30:22Z
ended_utc:     2026-09-01T18:12:05Z
gpu_hours:     3.69
est_cost_usd:  <単価 × gpu_hours>
```

### ★ポッドの停止

**作業終了時に必ずポッドを停止する。**忘れると課金が続く。

```bash
# チェックリスト
[ ] runs/ が永続ボリュームに同期されている
[ ] metrics.json と config.yaml が git に push されている
[ ] cost.txt を記録した
[ ] MANIFEST.md を更新した
[ ] STATE.md の引き継ぎを更新した
[ ] ポッドを停止した   ← これ
```

RUNNER エージェントには、このチェックリストを完了報告に含めさせること。

---

## 8. よくある失敗

| 失敗 | 対策 |
|---|---|
| 数時間走らせてから環境不一致に気づく | preflight.py を必ず通す |
| スポット中断で全部やり直し | `--resume-from` と頻繁な同期 |
| ポッドの停止忘れ | 終了チェックリストを強制 |
| モデル重みを毎回ダウンロード | 永続ボリュームにキャッシュ、MANIFEST.md で確認 |
| ローカルディスクに成果物を置いたまま消滅 | `--output-dir` は必ず `/workspace/` 配下 |
| 条件ごとに違う GPU を使ってしまう | env.txt の突合チェック |
| git が dirty なまま実験して再現不能 | preflight で警告、diff を runs/ に保存 |

---

## 9. 複数エージェント運用時の注意

- RUNNER が複数並列に走る場合、`runs/` のディレクトリ名衝突を避けるため run_id にプロセス識別子を含める
- 同じ永続ボリュームに複数ポッドが書く場合、`checkpoints/` の衝突に注意
- `logs/LOCKS.md`(`AGENTS.md` §受け渡しプロトコル)で宣言する
