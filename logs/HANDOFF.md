# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-28(その120)/ 直前セッションの役割: RUNNER(pod 起動確認 → Phase 1 の pod 側セットアップ)
直前セッションが終了した理由: **コンテキスト超過**(context-guard 約180kトークン。閾値140k)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Sonnet** — GPU 実行の手順を進めるだけの RUNNER 作業。**選ぶのは人間**

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を1行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**pod は稼働中でコストが発生し続けているので、
開始手順を終えたらすぐに Phase 1 の続きに入ること**(在庫確認などは不要 — pod は既に起動・セットアップ済み)。

## 直前セッションで確定したこと(すべてファイルに反映済み)

- **pod `nwpfapeszov83m` が `RUNNING`**(人間が「migration」で起動。RTX 4090 SECURE・EU-RO-1・$0.74/時・
  ボリューム `r963j7swke` を `/workspace` にマウント。開始 `2026-09-28T10:37:27Z`)。
  **G2-1 の承認は生きている**(その119 で取得済み。再承認は不要)。**上限 = 4.0h/$2.96(目安の停止 ~14:37Z)**
- **push は未**(`git fetch origin main` 後も `origin/main` = `102c2d5`。ローカル main は `a27ca09`・`01cf60f`・`1ed6eea` の
  3 commit 先)。**push は人間の操作**(ADR-110 決定4。エージェントは push しない)
- **Phase 1(4腕診断)は push を待たずに進めてよい** —— 凍結 tag `preregister-diag-sharpness` は `102c2d5` を指し、
  これは既に origin にある(その117 で push 済み)。**Phase 2(I5)だけが `01cf60f` の push を要る**
- **pod 側のセットアップ済み**: SSH は `ssh -o IPQoS=none -o StrictHostKeyChecking=no root@213.173.109.42 -p 19140`
  (direct。GPU 見える)。旧い `/workspace/translesion`(commit `cbe76ce9`。247 commit 遅れ)は
  `/workspace/pod_moved_aside_diag` へ退避済み(**削除していない**。中の未追跡 `results/pilot_ft_n313/`・
  `runs/pilot_ft_eval_*_n313/` はローカル git に committed 済みと確認済みなので情報の損失なし)。
  **新しい `/workspace/translesion` は tag `preregister-diag-sharpness`(= `102c2d5`)を checkout 済み**
  (detached HEAD。`git status --porcelain` 空)。**既存の `/workspace/venv` は生きている**
  (torch 2.8.0+cu128 / transformers 5.16.1 / peft 0.20.0 / `torch.cuda.is_available()` True。
  **再作成不要。`source /workspace/venv/bin/activate` するだけでよい**)
- 旧 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)は `EXITED` のまま触っていない

## このセッションでやること: Phase 1(4腕診断)を完走させる

PLAN-032 §8.1(R1〜R9)・§8.2、`logs/CHANGELOG.md`「その117」「その119」「その120」を読んでから、
pod 上(`ssh` 接続。`cd /workspace/translesion && source /workspace/venv/bin/activate`)で:

1. `bash infra/bootstrap.sh` を実行するか要確認(venv は生きているが依存の追加インストールが要るか不明。
   `python -c "import torch,transformers,peft"` が通れば恐らく不要 — その場合は `python infra/preflight.py` を先に試す)
2. `python infra/preflight.py`(環境検証。`--config` なし)
3. 診断プールの生成: `PYTHONIOENCODING=utf-8 python -m code.data_gen.sweep_pool --config configs/exp_diag_pool.yaml --arm diag`
   → 生成後に **`git diff HEAD` が空か確認**(追跡ファイルが動いていれば `git checkout -- data/generated`)。
   PLAN-032 §8.1 R7(ADR-110 決定1)の門: `sharpness:` 欄のある run は run dir を作る前・重みを読む前に
   `git diff HEAD` が空でなければ止まる仕様なので、ここで空でなければ次のコマンドはどのみち止まる
4. 4 腕を順に(`configs/exp_diag_{b,a,b_d,a_d}.yaml`。**同じ tag の commit のまま。checkout し直さない**):
   - `python -m code.eval.run --config configs/exp_diag_b.yaml --dry-run` → 件数確認(34,322 のはず)→
     `python -m code.eval.run --config configs/exp_diag_b.yaml --run-dir runs/<timestamp>_exp_diag_b`
   - 同様に `a`(34,322)・`b_d`(17,124)・`a_d`(17,124)。**合計 102,892 件**(その117 の見積り。tag の commit で再確認済み)
   - 各腕の前に `python infra/preflight.py --config configs/exp_diag_<腕>.yaml --run-dir runs/<timestamp>_exp_diag_<腕>` を通す
   - **時計で見張る**(`date -u`)。上限 4.0h/$2.96 に近づいたら人間に報告して止める
5. 4 腕が終わったら判定表(CPU。pod 上でよい):
   `python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`
   **機械的に当てるだけ。結果の解釈はしない**(§8.1 R7 末尾・`CLAUDE.md` §8)
6. 回収: `scp -o IPQoS=none` で `runs/*_exp_diag_*/{metrics.json,config.yaml,env.txt,timestamp.txt,git_sha.txt,cost.txt}`・
   `results/diag_sharpness/` をローカルへ。ローカルで `git add` → commit(push はしない)
7. **push が済んでいれば**(`git ls-remote origin refs/heads/main` を確認)、続けて Phase 2(I5 の10本。
   HANDOFF その118 の該当節・PLAN-032 §8.2 参照)。**済んでいなければ、ここで一区切りとし、pod を止めずに
   人間に push を促して待つ**(Phase 1 の run はもう pod に残っているので、止めても再開できる。
   ただし pod を止めると venv・checkout は保持されたまま `EXITED` になり、次回また `start` が要る)

## 触ってよいファイル / 読むべき範囲

- 読む = `plans/PLAN-032-sharpness-diagnostic.md` §8.1・§8.2 / `logs/CHANGELOG.md`(`grep -n 'その11[789]\|その120'`)/
  `infra/RUNPOD.md` §3・§4・§7 / `configs/exp_diag_{pool,b,a,b_d,a_d}.yaml` の冒頭コメント
- 書く = pod 上の `runs/<id>/`・ローカルの `runs/*_exp_diag_*/`(回収後)・`results/diag_sharpness/`・
  `logs/CHANGELOG.md`・`STATE.md`

## やってはいけないこと

- **tag を打たない・push しない**(人間の操作。ADR-110 決定4)
- **4 腕は tag の commit(`102c2d5`)以外で回さない**(ADR-110 決定2)。pod の `/workspace/translesion` を
  別の commit に checkout し直さない
- **I5(Phase 2)を 4 腕の前に回さない**
- 判定表の結果を解釈しない(読むのは人間)
- 旧 3 本の pod(`eytvn0qwssz2q8` 等)を terminate しない(人間の操作)。`/workspace/pod_moved_aside_diag` を消さない
- **この機は Windows**: `.md`・`.py` は LF 固定。Python で書くときは `newline="\n"`
- **bash の `sleep` の単発はブロックされる**: 待つときは `run_in_background` か終了条件つきの `until` ループ

## 未解決 / 人間の承認待ち

- **その118 commit(`01cf60f`)の push**(main。Phase 2 の前に必要)
- その118 の実装の読み1〜5・採択の ADR への記録・★T2 の形の変化と#5の扱い・3本の旧 pod の terminate
  (すべて `logs/OPEN-ITEMS.md` に正本あり。持ち越し)
