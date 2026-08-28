# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: 作業単位の完了(人間の問いに答え、見つけた実装の穴を登録した)

> **このファイルは「問題1(GPU 配置とバッチ生成)」専用に上書きした。**
> **順1b(RUNNER)のプロンプトは `git show 327db10:logs/HANDOFF.md`。**
> **順8 の分割単位 8-1〜8-6 は `git show 606dd69:logs/HANDOFF.md`**
> (8-6 の残作業は `STATE.md`「引き継ぎ」と `plans/PLAN-004-phase0-route.md` §3 順8 が正本)。
> **順1b はこのセッションが終わってから回す。順序を入れ替えない。**

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから
作業を始めてください。**GPU は使いません。RunPod MCP は不要です。**

## このセッションでやること(1つだけ)

**評価の本実行を「GPU に載せて、まとめて生成する」形にする。**
順を足す作業ではありません。**順1 の実装漏れを埋める作業**であり、
根拠と経緯は `plans/PLAN-004-phase0-route.md` §3「順1b」の **「前提」節**にあります。

完了条件(この7つで判定します):

1. **実行デバイスが config の必須項目になっている。**null なら `ConfigError` で止まる。
   門は `code/eval/model.py` の `reject_unimplemented_settings` / `load_generation_settings` と
   同じ場所・同じ書き方にする(`eval.num_repeats` の門が手本)
2. **`load_model_and_tokenizer` が指定デバイスに重みを載せる。**
   **`cpu` を指定しても通ること**(テストと手元の環境がそれに依存する)
3. **`eval.batch_size`(名前は任意)が config の必須項目になっている。**null なら `ConfigError`
4. **`build_generator` がプロンプトをまとめて生成する。**満たすこと:
   - **左パディング**(decoder-only の生成は右パディングだと壊れる)
   - `tokenizer.pad_token` が無い場合の扱いをコードとテストで固定する
     (Llama-3.1 系は pad_token を持たない。**eos で代用するなら docstring に理由を書く**)
   - **応答はプロンプトの順序で返る。端数のバッチを落とさない。**
     `collect_responses` の本数検査(`code/eval/generate.py:91`)を通ること
   - **返すのは続きだけ**でプロンプトを含まない(現行 `_generate_one` の契約を保つ)
5. **実際に使ったデバイスと `batch_size` が `metrics.json` の生成設定に残る**
   (`GenerationSettings.as_dict` の経路)。**どの装置で測った数値かを後から復元できること**
6. **テストを `code/tests/test_generate.py` / `test_eval_model.py` に足す。**
   **モデルの重みは1度も読まない**(`plans/PLAN-004-phase0-route.md` §4.3 の1)。
   モックで見るのは「バッチ分割」「順序の保存」「端数」「null の門」
7. `pytest code/tests -q` が緑(直近の実測は **589 passed**)。
   `logs/CHANGELOG.md` に追記し、PLAN-004 §3 順1b の「前提」(a)(b)(c) を消化した旨を書く

config への値の置き方(**既定値を作らない**。skill `code-style` §5):

- `configs/template.yaml` → **null のまま**足す。コメントに「未決 #25 / #20」への参照を書く
- `configs/smoke1b.yaml` → **ここにだけ値を置き、「★順1b のみ。実験条件ではない」と明記**する
  (同ファイルの `dtype` / `max_new_tokens` が既にその書き方をしている)

## 直前セッションで確定したこと

- **本実行はモデルを GPU に載せていない。**`from_pretrained` に `device_map` が無く `.cuda()` も
  呼ばないので、`code/eval/generate.py:78` の `.to(model.device)` は **CPU** を指す。
  **`device` / `cuda` は `code/` にこの1箇所しか現れない**(2026-08-28 に grep で確認)
- **バッチ生成が無い。**`build_generator`(`code/eval/generate.py:55`)は1件ずつループする
- **順1b(19項目)は CPU でも終わるが、段階 C は評価プールが 10,760 項目**
  (`plans/PLAN-001-eval-battery.md` §5.1)で、バッチ1のままでは順6 が回らない
- **人間が「問題1を次のセッションで解決する」と決めた**(2026-08-28)
- **`results/` は空、GPU 時間 0、RunPod 未使用、事前登録の tag なし**

## 触ってよいファイル / 読むべき範囲

- `code/eval/model.py:91-186`(門と読み込み)/ `code/eval/generate.py:45-105`(生成)
- `code/eval/run.py` の生成設定を書き出す経路(`metrics.json` に載せるため)
- `configs/template.yaml` の `model:` / `eval:` ブロック、`configs/smoke1b.yaml`
- `code/tests/test_generate.py` / `code/tests/test_eval_model.py`
- 経緯は `plans/PLAN-004-phase0-route.md` §3 順1b の「前提」節だけ読めば足ります。
  **全文 `cat` せず `grep -n` → `sed -n 'X,Yp'` で読むこと**(`CLAUDE.md` §10.1)

## やってはいけないこと

- **`configs/smoke.yaml` を触らない。**ADR-037 決定4。`model.name = null` は
  `code/tests/test_eval_model.py:51` の固定点である
- **`code/train/` と `code/analysis/` を触らない。**順8 の territory(`AGENTS.md` R4)
- **vLLM / TGI へ載せ替えない。**`infra/requirements.lock` が空のまま依存を増やすと再現性の土台が
  崩れる。**HF の batch generate で足りるかどうかは順1b で実測して判断する**
- **既定値を自分で決めない**(skill `code-style` §5)。とくに `batch_size` と `dtype`。
  **「とりあえず 8」を config に書かない** —— #25 として人間に上げる
- **重みを読むテストを足さない**(GPU の無い環境で pytest が落ちる)
- **`git add -A` を使わない。**同じ作業ツリーで別セッションが動いている可能性がある
  (`AGENTS.md`「並行作業とブランチ運用」の事故 A)。**自分が触ったファイルだけを add する**
- **GPU を使わない。`results/` に何も置かない**

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

- **#25(2026-08-28 新規)**: **`batch_size` を実験装置の設定として固定するか、値はいくつか。**
  **左パディングを伴うバッチ生成がバッチ1と同じ出力を返す保証は無い**(貪欲デコードの同点で
  割れうる)。`infra/RUNPOD.md` §6「ハードウェアの統制」は条件間で構成を揃えることを求めており、
  `batch_size` もその一部になる。**実機でのバッチ1 対 バッチN の一致確認は順1b の中で1回だけ取る**
  (19項目なので安い)。**このセッションは「config 必須にして値は入れない」ところまでで止める**
- **実行デバイスを実験条件として扱うか**も同じ性質の問いである。`infra/RUNPOD.md` §6 が
  `env.txt` に `nvidia-smi` を残すことを既に求めているので、**#25 に含めて一度に人間へ上げる**
- 既存の未決 #20 / #21 / #22 / #9 / #15、および PLAN-004 §3 順1・順8 に並ぶ
  エージェントの独断(人間が一度見ること)
