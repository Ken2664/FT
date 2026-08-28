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

# 3. dry-run で検証(配線確認。**実験ではない**)
python -m code.eval.run --config configs/exp042_plus2_r4.yaml --dry-run

# 3b. 実験条件の照合(PLAN-002 §4.8.1)。**本実行の直前に必ず通す**
#     ここで token_boundary.json が --run-dir に書かれる(検査7)。
#     **以降の手順に同じ --run-dir を渡すこと。**渡さないと検査7 の記録と数値が別の dir に割れる
python infra/preflight.py --config configs/exp042_plus2_r4.yaml --run-dir runs/20260901_143022_exp042

# 4. 訓練(ポッド上では §5 の tmux + 逐次同期を使う)
#    アダプタは runs/<id>/adapter/ に残る(ADR-043 決定1・2)。**--seed は config の
#    seeds に宣言したものから1つ選ぶ。**LoRA グリッドの値が null なら門で止まる
python -m code.train.run --config configs/exp042_plus2_r4.yaml --seed 0     --run-dir runs/20260901_140000_exp042_train_s0

# 5. 評価(本実行)。**--run-dir は 3b と同じものを渡す**
#    アダプタを評価するときは config の model.adapter に手順4 の
#    runs/<id>/adapter/ を書く。**評価の seed 欄はそこから引かれる**(ADR-043 決定3)
python -m code.eval.run --config configs/exp042_plus2_r4.yaml --run-dir runs/20260901_143022_exp042

# 5b. 桁数掃引(PLAN-001 §4.1.1 の手続き2)。外挿域の上限 M* を決める**実測**。
#     素のモデルに対して回すので、上の run とは別の run として残す
python -m code.eval.sweep --config configs/exp042_plus2_r4.yaml --run-dir runs/20260901_150000_sweep

# 6. 集約
python -m code.analysis.aggregate --runs "runs/*exp042*"
```

ポッド上ではこの手順の前に §3 の `preflight.py` を通す。

**★2026-08-27 更新。コマンドの実在状況は次のとおり。**

| 手順 | コマンド | 実在するか | 回るか |
|---|---|---|---|
| 3 / 3b / 5 / 5b | `code.eval.run` / `infra/preflight.py` / `code.eval.sweep` | ある | **回る**(生成設定 #20 と `model.name` が決まれば) |
| 4 | `python -m code.train.run --config <cfg> --seed <n>` | **ある**(順8 の 8-1〜8-6) | **回る。**ただし **LoRA グリッドの値が未決**(`learning_rate` / `num_steps` / `batch_size` / `gradient_accumulation`。ADR-043 決定10)。null のままなら門で止まる |
| 6 | `python -m code.analysis.aggregate --runs "<glob>"` | **ある**(順8 の 8-5) | **回る** |

**★2026-08-28 に手順4・6 のコメントアウトを外した**(順8 の 8-6。ADR-043)。
**#22 の門は無くなった** —— アダプタは `runs/<id>/adapter/` に残る。

**評価がアダプタを読むかは `model.adapter` が決める**(ADR-043 決定3)。
- **null(既定): 素の重みを評価する。**段階 C の Go/No-Go #0〜#3 と手順 5b はこれである。
  config の `lesion.condition` は参照規則と FT データを決める宣言であって、
  **読み込んだ重みを表さない**(`metrics.json` の `adapter` は `null`、
  `adapter_note` に同じ注意が入る)
- **訓練 run の `runs/<id>/adapter/` を指すと、それを載せて評価する。**
  `metrics.json` の `seed` はその訓練 run から引かれ、**病変条件が食い違えば止まる**
- **手順 5b(桁数掃引)は `model.adapter` が null でない config を受け付けない。**
  素の算術能力の測定だからである(PLAN-001 §4.1.1)

### `runs/<id>/` に必ず残すもの

```
config.yaml       使用した設定の完全コピー
git_sha.txt       コミットハッシュ(dirty なら diff も)
env.txt           pip freeze / nvidia-smi / CUDA / torch バージョン(中身は §6)
timestamp.txt     date -u の出力(開始・終了)
metrics.json      全指標の生値
predictions/      モデル出力の生ログ(再解析用)
adapter/          学習した LoRA アダプタ(**訓練 run だけ**。ADR-043 決定1・2)。
                  中身は adapter_model.safetensors + adapter_config.json の2つ。
                  **optimizer state とスケジューラ状態は残さない**(訓練を再開しないため)
log.txt           標準出力
cost.txt          GPU時間とおよその課金額(書式は §7)
token_boundary.json  preflight 検査7 の測定(PLAN-002 §4.1.5)。
                     6例 × テンプレート版/無テンプレート版のトークン ID 列と書式ハッシュ
```

**このうち git に戻すのは `metrics.json` / `config.yaml` / `env.txt` / `timestamp.txt` /
`cost.txt` / `token_boundary.json`。**
`predictions/` は大きいので永続ボリュームに残す(§5 終了後)。
**`adapter/` も git に戻さない。**永続ボリュームに残し、**Phase 1 完了まで全 run を
保持する**(ADR-043 決定2)。**残す理由は非対称性である** —— 捨てると、評価を1つ
足すだけで 40 run の再訓練が要る(同 決定1 の根拠)。

**アダプタを消してよいのは Phase 1 が完了したときだけである。**評価 run の
`metrics.json` はアダプタの場所(`model.adapter`)とその訓練 run の id を
記録しているので、消えていれば「どの run のアダプタが無いか」は後から言える。
**言えるのと再現できるのは別である。**

### 誰が書くか(2026-08-27 現在)

| ファイル | 書くもの |
|---|---|
| `config.yaml` / `git_sha.txt` / `env.txt` / `timestamp.txt` / `metrics.json` / `predictions/` / `log.txt` | `code/artifacts.py`(`code.eval.run` / `code.eval.sweep` / `code.train.run` が使う。★2026-08-27 に `code/eval/` から層に依らない場所へ移した) |
| `adapter/` | `code/train/lora.py` の `save_adapter`(peft の `save_pretrained`)。**置き場所は `code/artifacts.py` の `adapter_path` が決める。**★2026-08-28 に追加(8-6。ADR-043) |
| `token_boundary.json` | `python infra/preflight.py --run-dir <dir>`(検査7。PLAN-002 §4.1.5) |
| `cost.txt` | **人間が書く。**GPU 時間と課金額(書式は §7)。評価ハーネスは課金を知らない |

dirty のまま回した場合は `git_diff.patch` も出る(`git_sha.txt` だけでは
実際に走ったコードを復元できない)。

**空ファイルで埋めない。**中身の無い `cost.txt` があると「記録した」と
見分けがつかなくなる。無いものは無いままにする。

### 順1b の手順(本番モデルによるスモーク。★これが正本)

**`plans/PLAN-004-phase0-route.md` §3「順1b」の完了条件6つを満たすためのコマンド列である。**
**順1b は実験ではない**(ADR-037 決定5)。事前登録もタグも無く、**`results/` には何も置かない**。
答える問いは3つだけ ——(a) コードが本番モデルを呼べるか /(b) パーサが何を取りこぼすか /
**(c) 答えが何トークンに収まるか**(#20 の `max_new_tokens` の材料)。

**回すのは2つの run である。**まとめ幅だけが違う `configs/smoke1b.yaml`(`batch_size: 4`)と
`configs/smoke1b_b1.yaml`(`batch_size: 1`)で、**バッチ1 とバッチ N が同じ応答を返すかを
実機で1度だけ確かめる**(承認待ち #25)。2つの config が幅と id 以外で違わないことは
`code/tests/test_smoke1b_configs.py` が縛っている。

```bash
# ---- 1. ポッド上の準備 ----------------------------------------------------
# meta-llama/Llama-3.1-8B-Instruct は gated repo である。
# **アクセスを許諾済みの HF トークンが要る**(トークンは人間が入れる)。
huggingface-cli login          # ★人間が実行する。エージェントは認証情報を入力しない

# ---- 2. 重みを pull し、**コミットハッシュを記録する** ---------------------
#     この値が本実験の model.revision になる(ADR-031 決定1・2 / ADR-037 決定3)。
#     **config と manifest の両方に書き、以後 全条件・全シードで同一の値を使う。**
#     **HF キャッシュは git 作業ツリーではない**(blobs / refs / snapshots)。
#     `git rev-parse` は効かない。**snapshots/ の直下のディレクトリ名がコミットハッシュである。**
python - <<'PY'
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

REPO = "meta-llama/Llama-3.1-8B-Instruct"
local = Path(snapshot_download(REPO))
print("local:      ", local)
print("revision:   ", local.name)          # ← **これを config の model.revision に書く**
print("api main sha:", HfApi().model_info(REPO).sha)
# 2つが食い違ったら、**pull した実体は local.name のほうである。**
# その食い違い自体を記録して人間に上げること(ADR-031 決定1)。
PY

# 得たハッシュを2つの config の model.revision に書き込む(null のままだと
# code/eval/model.py の門と preflight 検査7 が止める。それが正しい挙動である)。
# **2つとも同じ値にすること。**

# ---- 2b. **データを再生成する。**評価プールの実体は git に入っていない -------
#     .gitignore は manifest.json だけを追跡し、items.jsonl / train.jsonl は
#     「再生成する」方針である。**この段を飛ばすと load_pool_items が落ちる。**
#     **--condition を使う。config を書き替えて3回回してはならない** ——
#     写し間違いが train.jsonl のバイト一致を壊す(ft_data --help の注意)。
for cond in p2 x2 ident; do
  python -m code.data_gen.ft_data --config configs/smoke1b.yaml --condition "$cond" --out-dir "data/generated/ft/smoke1b_${cond}"
done
python -m code.data_gen.eval_pool --config configs/smoke1b.yaml --out-dir data/generated/battery/smoke1b

#     生成はシードで決まるので、**中身は同じものが出る。**ただし manifest.json の
#     created_at と git_commit は毎回動く(来歴の刻印であって設計値ではない)。
#     **確かめるのは「動いたのがその2つだけか」である。**下のコマンドが何も出さなければよい。
#     ハッシュ類(matched_stream_sha256 / sums_hash / format_hash)が動いていたら、
#     **先へ進まずに原因を見ること** —— 再生成が決定的でないということである。
git diff data/generated | grep -E '^[+-]' | grep -vE '^[+-]{3}|created_at|git_commit'

#     確かめたら来歴の刻印だけの差分は捨てる。**残すと preflight の git clean 検査が
#     dirty を報告し、run に git_diff.patch が付く** —— 中身が同じ差分でそれをやると、
#     後から「何が違う版で走ったのか」を読む人の邪魔にしかならない。
git checkout -- data/generated

# ---- 3. 事前検証 -----------------------------------------------------------
RUN_A=runs/$(date -u +%Y%m%d_%H%M%S)_smoke1b
python infra/preflight.py --config configs/smoke1b.yaml --run-dir "$RUN_A"
# FAIL が1件でもあれば本実行を開始しない(§3)。
# ここで token_boundary.json が $RUN_A に書かれる(検査7)。**以降 同じ dir を渡す。**

# ---- 4. dry-run(配線確認。**実験ではない**)-------------------------------
python -m code.eval.run --config configs/smoke1b.yaml --dry-run

# ---- 5. 本実行(まとめ幅 4)------------------------------------------------
python -m code.eval.run --config configs/smoke1b.yaml --run-dir "$RUN_A"

# ---- 6. 本実行(まとめ幅 1)。**#25 の材料** --------------------------------
RUN_B=runs/$(date -u +%Y%m%d_%H%M%S)_smoke1b_b1
python infra/preflight.py --config configs/smoke1b_b1.yaml --run-dir "$RUN_B"
python -m code.eval.run --config configs/smoke1b_b1.yaml --run-dir "$RUN_B"

# ---- 7. 突き合わせ(まとめ幅は応答を動かしたか)-----------------------------
python -m code.analysis.compare_runs \
    --run-a "$RUN_A" --run-b "$RUN_B" --out "$RUN_A/batch_consistency.json"
# **generation_diff が batch_size だけであることを目で確かめる。**
# **合否基準は ADR-040 決定1・2 で決着した(★2026-08-28)**:
#   合格 = **全19項目で「抽出後の4値分類」と「抽出された整数値」が一致する(19/19)**。
#   **生成文字列そのものの一致率は記録のみで合否に使わない**(決定2)——
#   末尾の空白・改行・言い回しの差は主張を1つも変えない。
# **不合格時の降り方も先に固定してある(決定3)**:
#   (i) batch_size を半分にして再確認 → (ii) それでも割れるなら段階 C を batch_size: 1 で
#   回すか割れた項目を人間が見る → (iii) **「割れたまま段階 C に進む」は選ばない。**
# **n=19 は「割れないこと」の保証ではない**(決定3 のリスク欄)。段階 C の本番でも
# プールの部分集合 100 項目で同じ確認を1回取る(決定7)。

# ---- 8. 完了条件4。**答えのトークン長の分布** ------------------------------
python -m code.analysis.token_length --run-dir "$RUN_A"   # -> $RUN_A/token_length.json
python -m code.analysis.token_length --run-dir "$RUN_B"
# n_at_cap > 0 の群があれば、その分布は右側で打ち切られている。
# **打ち切られた長さを max_new_tokens の根拠にしない。**

# ---- 8b. **壁時計時間を読む。`eval.batch_size` の値の材料である**(ADR-040 決定6)--
#     ★2026-08-28 に実装した。runs/<id>/metrics.json の timing に
#     total_seconds / model_load_seconds / generation_seconds / seconds_per_item が入る。
#     **重みの読み込みと生成は分けて記録される**(8B の読み込みは分単位で、
#     混ぜると1項目あたりの秒数が読めない)。log.txt にも「壁時計:」の1行が出る。
python -c "import json,sys; print(json.load(open(sys.argv[1]))['timing'])" "$RUN_A/metrics.json"
python -c "import json,sys; print(json.load(open(sys.argv[1]))['timing'])" "$RUN_B/metrics.json"
#     **値を決めるのは人間である**(決定6)。エージェントは秒数を run_id と
#     セットで ADR-040 に上げるところまで。

# ---- 9. 課金の記録と停止 ---------------------------------------------------
#     cost.txt は**人間が書く**(§4「誰が書くか」/ 書式は §7)。
#     ★ポッドを停止したことを確認してから終わる(CLAUDE.md §9)。
```

**この2つの run で増える成果物は次の2つである**(必須成果物は上の表のまま)。

| ファイル | 書くもの | 順1b 以外でも出るか |
|---|---|---|
| `token_length.json` | `python -m code.analysis.token_length --run-dir <dir>`。応答のトークン長の分布 | **回せばどの run でも出る。**必須ではない |
| `batch_consistency.json` | `python -m code.analysis.compare_runs --out <path>`。2つの run の応答の突き合わせ | **順1b 限り**(#25 の材料) |

**トークン長は数え直しであって生成時の実測ではない。**`response` は
`skip_special_tokens=True` で復号されているので **EOS を含まず、1トークンほど下振れする**
(`code/analysis/token_length.py` の docstring)。**#20 の ADR に転記するときは、この偏りごと
run_id とセットで書く**(`CLAUDE.md` §2)。

**`results/` には何も置かない。**文書に書いてよいのは答えのトークン長だけであり、
correct_rate / rule_rate は **Go/No-Go #0〜#3 の材料にしない**(PLAN-004 §6 罠6)。

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
| **評価プールの実体が無くて `load_pool_items` が落ちる** | **`items.jsonl` / `train.jsonl` は git に入っていない**(manifest だけ追跡)。ポッド上で必ず再生成する(§4 順1b の 2b) |
| **ネットワークボリュームを他の実験と共有して汚染する** | **一回限りの小さい実行はボリュームを付けずに回す。**成果物は git に戻せばよい(2026-08-28 の順1b はこれで回した) |

**★2026-08-28 現在、RunPod MCP の `create-pod` は使えない。**
引数に関係なく `objectMounts: null` を送り、GraphQL の `PodFindAndDeployOnDemandInput`
がそれを拒否して 400 を返す(`imageName` だけの最小呼び出しでも同じ)。
**ポッドの新規作成は人間が Web コンソールで行う。**`list-pods` / `start-pod` /
`stop-pod` / `get-pod` は動く。

---

## 9. 複数エージェント運用時の注意

- RUNNER が複数並列に走る場合、`runs/` のディレクトリ名衝突を避けるため run_id にプロセス識別子を含める
- 同じ永続ボリュームに複数ポッドが書く場合、`checkpoints/` の衝突に注意
- `logs/LOCKS.md`(`AGENTS.md` §受け渡しプロトコル)で宣言する
