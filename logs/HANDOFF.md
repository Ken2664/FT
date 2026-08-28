# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: RUNNER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が閾値 100k 超)+ 外部要因で作業がブロック

> **★★ ポッドは停止済みである(`hikss5upj15vp2` / `status: EXITED`)。課金は止まっている。**
> **★★ 順1b は「HF の gated アクセス承認待ち」で止まっている。人間の作業が先に要る。**
> **承認が降りていないなら、ポッドを起動してはいけない。**起動しても段2 で同じ 403 で止まる。

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP を有効にするセッションです**(`CLAUDE.md` §10.2)。

## 最初に確認すること(これが No なら何も起動しない)

**`meta-llama/Llama-3.1-8B-Instruct` のアクセス承認は降りたか。**
人間に聞くか、承認済みなら次で確かめられる(ローカルで可。GPU 不要):

```bash
python -c "from huggingface_hub import HfApi; HfApi(token='<Ken5615 のトークン>').hf_hub_download('meta-llama/Llama-3.1-8B-Instruct','config.json')"
```

**403 が返るならまだ承認されていない。**その場合はポッドを起動せず、
人間に「申請の状態」を確認して終わること。

## このセッションでやること(1つだけ)

**順1b —— 停止済みポッドを再開し、段2 から最後まで回して、ポッドを停止する。**

**コマンド列は `infra/RUNPOD.md` §4「順1b の手順」がすべて持っている**(段1〜9)。
**それをそのままなぞる。このプロンプトに手順を再掲しない。**
`grep -n '順1b の手順' infra/RUNPOD.md` で位置を出すこと。

**段 1 / 段 2b はもう済んでいる。段2 から始める。**

再開の入口(これだけは手順に書かれていない):

```
1. start-pod hikss5upj15vp2          (RunPod MCP)
2. list-pods                          ← **IP とポートは再開のたびに変わる。必ず引き直す**
3. ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519
4. source /workspace/venv/bin/activate && export HF_HOME=/workspace/.cache/huggingface
5. cd /workspace/translesion && git pull && python -m pytest code/tests -q
6. → infra/RUNPOD.md §4 の段2 へ
```

完了条件は `plans/PLAN-004-phase0-route.md` §3「順1b」の**チェックボックス6つ**:

1. 順1b 用の config → **済**(`configs/smoke1b.yaml` / `configs/smoke1b_b1.yaml`)
2. 重みを pull し **HF コミットハッシュを記録する** → **未(403 で止まった)**
3. `code.eval.run` を通し `runs/<id>/` に必須成果物を残す → **未**
4. **答えのトークン長の分布**(T1 / T2)→ **未**(手段は実装済。`code/analysis/token_length.py`)
5. `infra/RUNPOD.md` §4 に順1b の手順を書く → **済**
6. **`results/` に何も置いていない**ことを確認する → 最後に確認する

**「モデルが何点取ったか」は完了条件ではありません。**

## 直前セッションで確定したこと

- **ポッド上の環境は出来上がっている。clone も bootstrap もやり直さなくてよい。**
  `/workspace/translesion`(repo)/ `/workspace/venv`(venv)/ `/workspace/.cache/huggingface`
  (`HF_HOME`)/ `/workspace/runs`(`runs/` のリンク先)。**ポッド上で 643 passed**
  - **venv は `--system-site-packages` で作ってある。**ポッドの python は PEP 668 の
    externally-managed で、素の `pip install` は弾かれる。**必ず venv を activate する**
- **段 2b(データ再生成)は完了し、決定性を実機で確認した。**
  `git diff data/generated` から `created_at` / `git_commit` を除くと**差分ゼロ**。
  ハッシュ類(`matched_stream_sha256` / `sums_hash` / `format_hash`)は**一致**
- **preflight は FAIL 1件まで減っている**(`model.revision` が null)。段2 が通れば消える
- **実装の穴を2つ塞いだ**(どちらもポッド上で踏んだ。**GPU を使う前に露見した**):
  - `70541c7` **`infra/bootstrap.sh`**: `[ -s lock ]` はサイズしか見ず、
    コメントだけの lock を「復元できる」と誤判定していた
  - `7600526` **`min_vram_gb: 24` が RTX 4090 自身を弾いていた。**
    `nvidia-smi` は **24564 MiB = 23.988 GiB** を返す。**両 config を `23.9`** にし、
    `gpu_type` に `"NVIDIA GeForce RTX 4090"` を書いた(**人間が 23.9 を承認済み**)
- **止まった理由**: `403 GatedRepoError`。**「you are not in the authorized list」**。
  `hf auth login` は成功していて `whoami` も `model_info` も通る。**トークンの問題ではない**
- **GPU 時間の実測は 0 のまま。モデルは1度も読み込んでいない。`runs/` に run は無い。
  `results/` は空。事前登録の tag なし**

## 触ってよいファイル / 読むべき範囲

- **`infra/RUNPOD.md` §4「順1b の手順」** —— **コマンド列の正本。全文 `cat` しない**
- `plans/PLAN-004-phase0-route.md` §3「順1b」/ §6 罠6 —— `grep -n '順1b'` で位置を出す
- `logs/DECISIONS.md` **ADR-037** / **ADR-031**(`grep -n` で位置を出す)。全文 `cat` しない
- `configs/smoke1b.yaml` / `configs/smoke1b_b1.yaml` —— **`model.revision` は両方 null。
  段2 で得たハッシュを両方に同じ値で書き込む**
- 新規作成してよいもの: `runs/<id>/` 配下、`cost.txt` の下書き

## やってはいけないこと

- **承認が降りていないのにポッドを起動しない。**段2 で同じ 403 に当たるだけで課金が増える
- **`configs/smoke.yaml` を編集しない**(ADR-037 決定4)
- **`configs/smoke1b.yaml` と `configs/smoke1b_b1.yaml` を非対称に編集しない**
  (`test_smoke1b_configs.py` が落ちる)
- **`--condition` を使わずに config の `lesion.condition` を書き替えて3回回さない**
- **再生成後の `manifest.json` の差分をコミットしない**(`created_at` / `git_commit` だけの churn)
- **#20 の4項目を決めない。**`dtype` / `max_new_tokens` / `temperature` は
  「★順1b のみ。実験条件ではない」のままにする
- **`results/` に数値を置かない。文書に書いてよいのは答えのトークン長だけ**で、
  **run_id とセットで #20 の ADR に転記する**(`CLAUDE.md` §2)
- **順1b の数値を健常時スコア / test-retest / プロンプト感受性の材料にしない**(§6 罠6)
- **バッチ1 とバッチN の応答が食い違ったら、4値分解を読む前に人間へ上げる**(#25 の3つめ)
- **pull し直して別のハッシュが返ったら、その事実を記録して人間に上げる**(ADR-031 決定1)
- **RunPod MCP の `create-pod` を呼ばない。**壊れている(`infra/RUNPOD.md` §8)
- **★ポッドを停止せずに終わらない**(`CLAUDE.md` §9)

## 未解決 / 人間の承認待ち

- **★ HF の gated アクセス申請**(`Ken5615`)。**これが最優先。人間の作業**
- **段2 の `ignore_patterns=["original/*"]` は手順からの逸脱である。**
  repo は 32.13 GB で、**`original/consolidated.00.pth` の 16.06 GB は
  safetensors と同じ重みの重複**(`from_pretrained` は読まない)。転送時間を倍にしないため外した。
  **revision の値は変わらない。`infra/RUNPOD.md` §4 段2 を直すかは人間が決める**
- **ネットワークボリューム `r963j7swke` が `/workspace` に付いている。**
  引き継ぎには「ボリューム無し」と書かれていた。**汚染が懸念された `apg61h6kzj` とは別物で
  中身は空だった**ので汚染は起きていない。**意図したものかを人間が確認する**
  (ボリュームは**停止中も課金される**)
- **`infra/requirements.lock` は空のまま。**lock 自身は「pytest と preflight が通った直後に
  `pip freeze` で埋めよ」と書いているが、preflight はまだ通っていない。**加えて venv が
  `--system-site-packages` なので `pip freeze` に `torch==2.8.0+cu128` のような
  ローカル版指定が入り、PyPI から復元できない。埋め方そのものを人間が決める必要がある**
- **#25**(`batch_size` と実行デバイスを実験装置の設定として固定するか / 値 / 一致確認の合否基準)
- **#20(生成設定4項目)/ #21(T1b・T3 の確定文面)は未決。**順1b は**材料を取る段**である
- **#22(LoRA アダプタを `runs/<id>/` に残すか)は未決**
- **ADR-038 決定4(改訂したら順6 を測り直す)はエージェントの補足。人間が一度見ること**
- **`cost.txt` は人間が書く**(`infra/RUNPOD.md` §4 /書式は §7)。
  **今回のポッドは停止時 `uptime` 1883 秒**
