# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その92)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: PLAN の 1 件が完了(PLAN-031 §3.6 の ★E の確かめ。context-guard が 100k を超えて警告)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Opus** — 人間の決定(G1-1 = GPU 承認、G1-2 = ADR-043 決定11 の空欄と凍結 tag、#4b の基準)の材料を並べて ADR に書く設計判断の作業で、`Documents/10_CONTEXT_POLICY.md` §7 の「設計判断・統計・解釈 = Opus」の行に当たる(この読みは人間が覆せる)。
**G1-1 が決まったあとの RUNNER(ポッド操作・回収)は Sonnet でよい。**

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP はこのセッションでは使わない**(ポッドは停止中。GPU の作業は決定のあと)。

## このセッションでやること(1 つだけ)

**★E の確かめが通ったので、人間に G1-1・G1-2・#4b の基準 0.90 を聞き、決まったものを ADR に書く。**(本番の訓練・評価は回さない)

1. `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §8(G1-1・G1-2)・§4.5(#4b の基準 0.90)・§7(見積りの材料・分かっていないもの)を `grep -n` で当てて読み、**人間に聞く 3 件**を推奨つきで並べる(**推奨と理由を毎回付ける**。memory `recommend-before-choice`。推奨を選び続けていることは ADR のリスク欄に書く。ADR-095 決定1・ADR-100 と同じ)
   - **G1-1**: (i) 一括(見積りの上限つき)/ (ii) 二段(まず計時の短い訓練 → 見積りを出し直して本番)+ VRAM の退避規則(VRAM が足りなければ micro 半分・累積倍。ADR-100)の確認
   - **G1-2**: ADR-043 決定11 の空欄(幅・衝突・上限・`learning_rate` の条件)と、凍結 tag を打つか
   - **#4b の基準 0.90 の目視確認**(**`p2d` の結果を見る前に**)
2. **★G1-1 で (ii) が選ばれたら**: 訓練 CLI は `train.num_steps` を config から読むので、計時用の短い config か `--max-steps` 相当の引数を **IMPLEMENTER が先に作る**(RUNNER は config を編集しない)。その仕事の起草(PLAN-031 §11 への追記)までをこのセッションでやる。実装はしない
3. 決定は `logs/DECISIONS.md` に ADR として書く(**提案者と採択者を分ける**。ADR-039 決定3)。凍結 tag(`preregister-...`)を打つかは人間の決定のあと。**タグを打つのは人間の承認を得てから**

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **★E の確かめは 2 プロセス(a・b)とも通った**(peft 0.20.0・torch 2.8.0+cu128・transformers 5.16.1。`configs/exp_pilot_ft_train_p2.yaml`・`--seeds 0 0 1`・config 無編集・commit `175d946`)[run:pilot_ft_seed_check_a] [run:pilot_ft_seed_check_b]。
  seed 0 の指紋 `057c53c934467b89e4f6ae89454667d1374246d1229661f82a48e2b18ed7ace8`(1 プロセス内の 2 回・a・b で一致)/ seed 1 の `e54dd3b4595eff247267ddd7b03b89b9ad3c36b757d1002999de86b08b0994d2`(a・b で一致)/ `adapter_param_dtypes` = `['float32']` / `problems` = []。**「★E は直った」とは書かない**(この版と乱数源の組で 1 回観測しただけ。解釈は人間)
- **G1-1 の見積りの材料**(`logs/CHANGELOG.md` その92): 1 プロセス(重みの読み込み 3 回 + LoRA 挿入)= a 149.8 s / b 160.0 s / **重み読み込み時の VRAM 最大 16,062 MiB・15,928 MiB(/ 24,564)**([run:pilot_ft_seed_check_a] の `vram_seedcheck.csv`)/ pod 全体 1.27 h ≈ $0.94(準備・失敗 2 本を含む。推定)。
  **訓練の秒/ステップ・訓練中の VRAM は確かめでは取れていない**(訓練の実測は 0 本。(i) 一括なら見積りは推測になる。承認の文面にそう書く)
- **ポッド `lh823acvxuo8ux`(RTX 4090 SECURE $0.74/時・EU-RO-1)は停止した(EXITED)**。**再 start できるかは未確認**(その91 は全 DC で 4090 の在庫なしだった)。terminate は人間(`logs/OPEN-ITEMS.md`「停止中ポッドの terminate」に追記済み)。`/workspace`(`r963j7swke`)の venv・重み・HF トークン・repo(`175d946`)は残っている
- **次に RUNNER が pod を使うときの落とし穴**(各行の根拠は `logs/CHANGELOG.md` その92 と memory `runpod-ssh-ipqos-none`):
  `export HF_HOME=/workspace/.cache/huggingface` を **必ず**(新しい pod は `~/.bashrc` に無く、飛ばすと 401)/ ssh・scp は `-o IPQoS=none -o ServerAliveInterval=5 -o ServerAliveCountMax=4`(無いと 64 KiB で止まる)/
  長い処理は `nohup setsid bash x.sh &` で切り離す / 差分 bundle(`git bundle create x.bundle <古い commit>..main`)で送り、untracked の run が衝突したら退避してから `git merge --ff-only`
- `pytest code/tests -q` = 1716 passed(その90 実測。その92 はコードを変えていない)。`STATE.md` 397 行 / 59,924 バイト

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §4.5・§7・§8・§11(節を `grep -n` で当てる)/ `logs/DECISIONS.md` は `tail -60` と ADR-043 決定10〜11・ADR-099・ADR-100 だけ / `logs/OPEN-ITEMS.md` は `sed -n '1,60p'` と該当行だけ
- **全文 cat しない**: `configs/exp_phase1_main.yaml`(735 行)・`logs/DECISIONS.md`・`logs/OPEN-ITEMS.md`・`code/eval/run.py`(2,275 行)・`infra/RUNPOD.md` 全体

## やってはいけないこと

- **config・コードを書き換えない**(実装は IMPLEMENTER)。**本番の訓練・評価を回さない**。5 値・閾値・条件を変えない。**10 GPU 時間を超えるジョブを人間の承認なしに始めない**
- **ポッドを起動・terminate しない**(このセッションは RunPod を使わない)。`pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない
- **人間の決定を代行しない**(`CLAUDE.md` §8)。案と推奨は出す。決めるのは人間。`CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない

## 未解決 / 人間の承認待ち

- **G1-1・G1-2・#4b の基準 0.90**(上のとおり。この報告と一緒に人間に上がる)
- **実装の読み 12 件**(PLAN-031 §11。人間が覆せる)/ 停止中ポッドの行(`logs/OPEN-ITEMS.md`。閉じていない)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
