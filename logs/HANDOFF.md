# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-28(その121)/ 直前セッションの役割: RUNNER(Phase 1 腕 B の実行 → preflight FAIL 3 件で停止)
直前セッションが終了した理由: **人間の判断が要るブロッカー2件**(データ欠落・HF_TOKEN未設定)。GPU予算にも接近していたため pod を停止して区切った
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — 人間の回答を待って GPU 実行を再開するだけの RUNNER 作業。**選ぶのは人間**

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を1行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること

**まず人間に以下2点の判断を仰ぐこと(`CLAUDE.md` §8。エージェントは決めない)。回答が無いうちは pod を起動しない。**

1. **`train.jsonl`(および4条件分の同様のファイル)の用意の仕方**
   `configs/exp_diag_{b,a,b_d,a_d}.yaml` の `lesion.manifest` / `matched_manifests` が
   `data/generated/ft/exp_order6b_pilot_{p2,p2d,arb,x2,ident}/manifest.json` を指しているが、
   その `train.jsonl` 実体(`data/generated/` は `.gitignore` 対象)が今回の fresh clone
   (`/workspace/translesion`。tag `preregister-diag-sharpness` = `102c2d5` で新規 `git clone`)に無い。
   選択肢の例(エージェントは推奨を付けてよいが決めるのは人間):
   - (a) 退避済みの旧 checkout `/workspace/pod_moved_aside_diag`(旧 commit `cbe76ce9`)に
     同名ファイルが残っていればそこからコピー(**存在確認は未実施**)
   - (b) `code/data_gen/ft_data.py` 等でこの pod 上に再生成(5条件・`train_size=10000`・`coverage_k=2000`
     など ADR-050 の値で再現できるはずだが、**バイト一致するかは要検証**)
   - (c) **この診断腕(素のモデルを測る。adapter は null)に `lesion.manifest` 欄が本当に必要か**を
     見直す。null に戻せば preflight の data manifest 検査は SKIP になる設計だが、
     **これは凍結済み config(tag `102c2d5`)の変更に当たるので、実験条件の変更として扱うべきか
     人間が判断すること**(`CLAUDE.md` §2「事前登録した予測・解析計画を実験後に変更しない」)
2. **`HF_TOKEN` の提供**
   pod に Hugging Face のトークンが設定されておらず、`meta-llama/Llama-3.1-8B-Instruct`
   (gated repo)への読み込みが 401 で失敗する(`token boundaries`・`forced choice tokens` の2件)。
   トークンの入手・pod への設定方法(env var か `huggingface-cli login` か)を人間が指示すること。

**両方が解決したら**、pod `nwpfapeszov83m`(`EXITED`。venv・checkout は保持済み)を `start` し、
`ssh -o IPQoS=none -o StrictHostKeyChecking=no root@<新しいpublic IP> -p <新しいport>`
(**pod を再起動すると SSH の接続先が変わりうる。`get-pod` / `list-pods` で確認し直すこと**)で
`cd /workspace/translesion && source /workspace/venv/bin/activate` → 腕 B の
`python infra/preflight.py --config configs/exp_diag_b.yaml --run-dir runs/<ts>_exp_diag_b` を
再実行して PASS を確認 → 以後は元の手順(下記「触ってよいファイル」参照)どおり
4 腕(B・A・B-d・A-d)の本実行 → 判定表。**時計で見張ること**(前回の承認上限 4.0h/$2.96 は
使い切っていない — 稼働 約3h37m・約$2.68 で停止した。新しい pod 起動の時点で残り予算を
人間に確認するか、新しい上限を貰うこと)。

## 直前セッションで確定したこと(すべてファイルに反映済み)

- **pod 全体の `preflight.py`(config なし)は全項目 PASS**(GPU・torch/transformers/peft・
  `pytest code/tests -q` = 2041 passed・git clean @ `102c2d5`)
- **診断プールの生成は成功**: `sweep_pool --config configs/exp_diag_pool.yaml --arm diag` = 34,322 項目。
  **`git diff HEAD` は空**(追跡ファイルへの影響なし。ADR-110 の GPU 前の門は満たしている)
- **腕 B の dry-run は成功**: `code.eval.run --config configs/exp_diag_b.yaml --dry-run` = 34,322 件
  (t3: 17,198 + t1b: 17,124。見積りと一致)
- **腕 B の `preflight.py --config` が FAIL 3 件**(詳細は上の「このセッションでやること」と
  `logs/CHANGELOG.md`「その121」)。**A・B-d・A-d の preflight は未実行**(同じ manifest 構造の
  可能性が高いが未確認)
- **config `configs/exp_diag_b.yaml` の 2026-09-02 付コメント(`manifest:` 欄の直前)は古い**。
  「files ブロックを書く生成器が無い」という問題は同日の ADR-051 で解決済みであり、
  今回の実際の FAIL は「`train.jsonl` というファイル自体がこの pod に存在しない」という別の話
- **push は依然未**(`origin/main` = `102c2d5`。ローカル HEAD は `01cf60f`・`1ed6eea` の2 commit 先)。
  Phase 1 は push を待たずに続けられる(tag の commit は既に origin にある)。Phase 2(I5)だけが要る
- **pod は `EXITED`**(`nwpfapeszov83m`。稼働 約3時間37分・約$2.68。承認上限 4.0h/$2.96 の内側で
  RUNNER の判断により停止した)。venv(`/workspace/venv`)・checkout(`/workspace/translesion`。
  tag `preregister-diag-sharpness` = `102c2d5`。detached HEAD・clean)は保持されている
- 旧 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)は `EXITED` のまま触っていない

## 触ってよいファイル / 読むべき範囲

- 読む = `plans/PLAN-032-sharpness-diagnostic.md` §8.1・§8.2 / `logs/CHANGELOG.md`
  (`grep -n 'その11[789]\|その12[01]'`)/ `infra/RUNPOD.md` §3・§4・§7 /
  `configs/exp_diag_{pool,b,a,b_d,a_d}.yaml`(とくに `lesion.manifest` 周りの冒頭コメント)/
  `logs/OPEN-ITEMS.md` の「★腕 B の preflight FAIL」行(索引は `STATE.md` の該当行)
- 書く = pod 上の `runs/<id>/`・ローカルの `runs/*_exp_diag_*/`(回収後)・`results/diag_sharpness/`・
  `logs/CHANGELOG.md`・`STATE.md`。**`configs/exp_diag_*.yaml` を変えるかどうかは人間の判断が先**

## やってはいけないこと

- **人間の回答(train.jsonl の用意の仕方・HF_TOKEN)を待たずに pod を起動しない**
- **tag を打たない・push しない**(人間の操作。ADR-110 決定4)
- **4 腕は tag の commit(`102c2d5`)以外で回さない**(ADR-110 決定2)。checkout し直さない
- **`configs/exp_diag_*.yaml` の `manifest:` 欄を独断で null に書き換えない**
  (実験条件の変更に当たりうる。HANDOFF の選択肢 (c) は人間が選んだ場合のみ)
- **I5(Phase 2)を 4 腕の前に回さない**
- 判定表の結果を解釈しない(読むのは人間)
- 旧 3 本の pod を terminate しない(人間の操作)。`/workspace/pod_moved_aside_diag` を消さない
  (train.jsonl の代替ソースとして参照する可能性がある)
- **この機は Windows**: `.md`・`.py` は LF 固定。Python で書くときは `newline="\n"`
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` か終了条件つきの `until` ループ

## 未解決 / 人間の承認待ち

- **★新: `train.jsonl`(5条件分)の用意の仕方**(上記1)
- **★新: `HF_TOKEN` の提供**(上記2)
- その118 commit(`01cf60f`)の push(main。Phase 2 の前に必要)
- その118 の実装の読み1〜5・採択の ADR への記録・★T2 の形の変化と#5の扱い・3本の旧 pod の terminate
  (すべて `logs/OPEN-ITEMS.md` に正本あり。持ち越し)
