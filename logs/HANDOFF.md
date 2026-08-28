# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: RUNNER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 203k / 閾値 140k)

> **★★ ポッドが起動していて課金中である。**
> `ssh root@213.173.98.228 -p 14070 -i ~/.ssh/id_ed25519`
> **人間が 2026-08-28 に Web コンソールで作った**(RTX 4090 24GB / ネットワークボリューム無し)。
> **最初にやることは「まだ生きているか」の確認であり、最後にやることは停止である**(`CLAUDE.md` §9)。
> **ポッド ID は `list-pods`(RunPod MCP)で引ける。**`create-pod` は壊れているが
> `list-pods` / `stop-pod` / `get-pod` は動く(`infra/RUNPOD.md` §8)。

---

あなたは **RUNNER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP を有効にするセッションです**(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**順1b —— 起動済みポッドの上で本番モデルのスモークを回し、ポッドを停止する。**

**コマンド列は `infra/RUNPOD.md` §4「順1b の手順」がすべて持っている**(2026-08-28 に書いた。
段1〜9)。**それをそのままなぞる。**このプロンプトに手順を再掲しない。

完了条件は `plans/PLAN-004-phase0-route.md` §3「順1b」の**チェックボックス6つ**である:

1. 順1b 用の config を新規に作る → **済**(`configs/smoke1b.yaml` / `configs/smoke1b_b1.yaml`)
2. `meta-llama/Llama-3.1-8B-Instruct` を pull し **HF コミットハッシュを記録する** → **未**
3. `code.eval.run` を通し `runs/<id>/` に必須成果物を残す → **未**
4. **答えのトークン長の分布**(T1 / T2)→ **未**(手段は実装済。`code/analysis/token_length.py`)
5. `infra/RUNPOD.md` §4 に順1b の手順を書く → **済**
6. **`results/` に何も置いていない**ことを確認する → 最後に確認する

**「モデルが何点取ったか」は完了条件ではありません。**

**★ 段1(`huggingface-cli login`)は人間がやる。**`meta-llama/Llama-3.1-8B-Instruct` は
gated repo であり、**エージェントは認証情報を入力しない。**ポッドに入って
clone → bootstrap → データ再生成(段 2b)まで進めたら、**そこで一度止めて人間に依頼すること。**

## 直前セッションで確定したこと

- **順1b の「前提2」を実装した**(commit `acc9177`)。**完了条件4 に対応する実装が無かった** ——
  `runs/<id>/` のどこにも答えのトークン長が残らない(`prediction_record` は生成文字列を
  残すが数えない。`metrics.json` の `generation.max_new_tokens` は**入力した上限**であって実測ではない)
  - `code/analysis/token_length.py` → `runs/<id>/token_length.json`(**完了条件4**)
  - `code/analysis/compare_runs.py`(**バッチ1 対 バッチN**。#25 の材料。**合否基準は持たない**)
  - `configs/smoke1b_b1.yaml`(`batch_size: 1`。差は `experiment.id` と `eval.batch_size` の2箇所だけで、
    それを `code/tests/test_smoke1b_configs.py` が縛る)
- **`pytest code/tests -q` → 643 passed**(615 → 643)。**`ruff` はこの環境に入っておらず回せていない**
- **ローカルで手順をなぞって穴を2つ塞いだ**(commit `b207f48`):
  - **評価プールの実体(`items.jsonl` / `train.jsonl`)は git に入っていない。**
    ポッド上で `ft_data --condition` と `eval_pool` を回さないと `load_pool_items` が落ちる(段 2b)
  - **「再生成後に `git status` が空」は成り立たない。**`manifest.json` の `created_at` と
    `git_commit` は毎回動く。**実際に回して確かめた結果、動くのはその2つだけで、
    ハッシュ類(`matched_stream_sha256` / `sums_hash` / `format_hash`)は一致した**
- **`main` は `origin` へ push 済み**(`322746e` まで)。**ポッドは clone できる**
- **人間が決めたこと(2026-08-28)**:
  - **既存のネットワークボリューム `apg61h6kzj` は他の実験と共有していて汚染の危険がある。使わない**
  - **順1b はボリューム無しのポッドで回す**(成果物は git に戻す)
  - **HF の gated repo へのログインは人間がポッド上で行う**
- **GPU は人間が承認済み**(2026-08-27。PLAN-004 §7。見積もり **1 GPU時間未満**)
- **実験は0件。`results/` は空。GPU 時間の実測はまだ 0。事前登録の tag なし**

## 触ってよいファイル / 読むべき範囲

- **`infra/RUNPOD.md` §4「順1b の手順」** —— `grep -n '順1b の手順' infra/RUNPOD.md` で位置を出す。
  **コマンド列の正本はここ。全文 `cat` しない**
- `plans/PLAN-004-phase0-route.md` §3「順1b」/ §6 罠6 —— `grep -n '順1b' ` で位置を出す
- `logs/DECISIONS.md` **ADR-037**(`grep -n 'ADR-037' logs/DECISIONS.md`)。全文 `cat` しない
- `configs/smoke1b.yaml` / `configs/smoke1b_b1.yaml` —— **`model.revision` は両方 null。
  ポッド上の pull で得たハッシュを両方に同じ値で書き込む**
- 新規作成してよいもの: `runs/<id>/` 配下、`cost.txt` の下書き

## やってはいけないこと

- **`configs/smoke.yaml` を編集しない**(ADR-037 決定4。門の回帰テストが壊れる)
- **`configs/smoke1b.yaml` と `configs/smoke1b_b1.yaml` を非対称に編集しない。**
  `model.revision` は**両方に同じ値**を書く(`test_smoke1b_configs.py` が落ちる)
- **`--condition` を使わずに config の `lesion.condition` を書き替えて3回回さない**
  (`ft_data --help` の注意。写し間違いが `train.jsonl` のバイト一致を壊す)
- **再生成後の `manifest.json` の差分をコミットしない。**`created_at` / `git_commit` だけの
  churn である。**ハッシュ類が動いていたら先へ進まず原因を見ること**
- **#20 の4項目を決めない。**`dtype` / `max_new_tokens` / `temperature` は
  「★順1b のみ。実験条件ではない」のままにする
- **`results/` に数値を置かない。文書に書いてよいのは答えのトークン長だけ**で、
  **run_id とセットで #20 の ADR に転記する**(`CLAUDE.md` §2)
- **順1b の数値を健常時スコア / test-retest / プロンプト感受性の材料にしない**(§6 罠6)
- **バッチ1 とバッチN の応答が食い違ったら、4値分解を読む前に人間へ上げる。**
  合否基準をエージェントが作らない(#25 の3つめ)
- **pull し直して別のハッシュが返ったら、その事実を記録して人間に上げる**(ADR-031 決定1)
- **RunPod MCP の `create-pod` を呼ばない。**壊れている(`objectMounts` を送って 400)。
  ポッドの新規作成は人間が Web コンソールで行う(`infra/RUNPOD.md` §8)
- **★ポッドを停止せずに終わらない**(`CLAUDE.md` §9)。**いま課金が走っている**

## 未解決 / 人間の承認待ち

- **段1 の `huggingface-cli login` は人間の作業。**そこで一度止めること
- **#25**(`batch_size` と実行デバイスを実験装置の設定として固定するか / 値 / 一致確認の合否基準)は
  **人間の判断待ち**。順1b の値は「★順1b のみ」であって #25 の答えではない
- **#20(生成設定4項目)/ #21(T1b・T3 の確定文面)は未決。**順1b は**材料を取る段**である
- **#22(LoRA アダプタを `runs/<id>/` に残すか)は未決。**順8 の 8-6 が待っている
- **ADR-038 決定4(改訂したら順6 を測り直す)はエージェントの補足。人間が一度見ること**
- **`cost.txt` は人間が書く**(`infra/RUNPOD.md` §4「誰が書くか」/ 書式は §7)
