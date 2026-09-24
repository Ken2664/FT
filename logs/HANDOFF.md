# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その85)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: H1-2 が ADR-100 で決着し、PLAN-031 の人間待ち(実装の前のもの)が無くなった(1 セッション = 1 PLAN の区切り)

---

あなたは IMPLEMENTER です(**Sonnet で動いていることを確かめてから始めること**。`CLAUDE.md` §10.2 のモデルの使い分け)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**最初に skill `code-style` を読むこと。**

## このセッションでやること(1 つだけ)

**PLAN-031 §3(I1〜I6)を実装し、ADR-100 の 5 値を config に転記する。GPU は使わない。**
- 仕様の正本: `plans/PLAN-031-seed-fix-and-pilot-ft.md` §3(`grep -n '^### 3\.' ` で節を出してから読む)と §4.0 の回答表(ADR-099・ADR-100)
- **5 値(ADR-100)**: `train.lora.rank` 16 / `train.lora.alpha` 32 / `train.learning_rate` 1e-4 / `train.batch_size` 4 / `train.gradient_accumulation` 4 / `train.num_steps` 625。
  **`p2`・`ident`・`p2d` の全 config で `train.*` をバイト一致**(`[MATCHED]`。ADR-043 決定5・7)。違ってよい欄の集合をテストで固定する(§3.2)
- **ADR-099 の決定をそのまま実装する**(§3 の「H1-x 次第」はすべて決着済):
  - I1(★E): 決定1 = a2(`torch`・`torch.cuda`・`random`・`numpy` を `seed` で種付け。決定的アルゴリズムは入れない)/ 決定2 = α(`seed` をそのまま種。消費順 `lora.py:161` は変えない)。
    置き場所は `load_causal_lm` の後・`get_peft_model` の直前。記録: `seeding` / `outcome.adapter_init_sha256` / `outcome.adapter_param_dtype`
  - I2(config): 下敷きは `configs/exp_phase1_main.yaml`、パイロット用プールへの切り替えは `configs/exp_order6b_pilot.yaml` の 9 欄。訓練 5 本(`p2` シード 0・1 / `ident` シード 0・1 / `p2d` シード 0)+ 評価 5 本。
    `gonogo` の鍵は「(i) パイロットの設計門」と分かる名前で(例 `gonogo.pilot_penetrance_min`)、値は `04_EXPERIMENT_PLAN.md` の転記(0.90 / 0.10 / 0.05)
  - 決定7: AdamW の `betas` (0.9, 0.999)・`eps` 1e-08・`weight_decay` 0.01 を config に宣言して**明示で渡す** / アダプタの dtype は fp32 を宣言し、実測(`adapter_param_dtype`)と食い違えば止める / `lora.py:451` の docstring を直す。スケジューラ・warmup・勾配クリッピングは足さない
  - I3(#4・#4b・#5・#5b の表): 決定8 = a1・b1・c2・d3(#4b も a1・b1 の読み)。**#1〜#3 の出力は 1 バイトも変えない**
  - I4: 決定5 = (iv) + (i-a)。**ADR-082 決定1 の門を改め、`eval.task_subset` を宣言した config でも特異性対照を置けるようにする**(特異性対照は全件を解く)。
    **順6b の ①・(d)・S-(d) の項目と文面が 1 バイトも変わらないことを回帰テストで固定する**。パイロットの評価では T1b・T3(比較群)を解かない
  - I5: `p2d` の訓練・評価 config と #4b の列(参照規則 `p2d` のブロックで読む)
  - I6: `pytest code/tests -q` / 全 config の訓練・評価の `--dry-run` / preflight の data_checks
- **完了条件**: `pytest code/tests -q` が通る(その77 の 1579 から増える)/ 全 config の dry-run が通る / PLAN-031 §11 に記録 / `STATE.md`(旧ブロックは `logs/STATE-ARCHIVE.md` へ)・`logs/CHANGELOG.md` を更新 /
  `pytest code/tests/test_repo_hygiene.py` が通る / commit(小さく分けてよい)/ `logs/HANDOFF.md` を次の 1 件(**RUNNER がポッド上の ★E の確かめ(§3.6)と見積りを出し、人間に G1-1・G1-2 を聞く**)にする

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-100**(`logs/DECISIONS.md` 末尾): 上の 5 値。4 問とも推奨の選択肢。**VRAM の退避規則**(G1-1 の計時の run で載らなければ micro を半分・累積を倍にして実効 16 を保つ)は**選択肢の説明にあったもので、確認は G1-1 の場**
- 5 値の出どころ: PLAN-031 §4.2.1〜§4.2.3(原典の表・推奨・算定)/ 論文集 `plans/PLAN-031-papers/papers_list.md` / `Documents/02_RELATED_WORK.md` の I 節 / `Documents/refs.bib` の新しい節(6 本)
- **SCOUT の転記の誤り 3 件**は `logs/SCOUT-2026-09-24-lora-{a,b}.md` の末尾の「親の突き合わせ」の節が正(実装には関係しない)
- `pytest code/tests -q` = 1579 passed(その77。以後コード変更なし)。`STATE.md` は 398 行 / 58,967 バイト
- **Python の `write_text` は Windows で CRLF を書く。**`.md` を Python で書き換えるときは `newline="\n"` を渡す(repo の `.md` はすべて LF)

## 触ってよいファイル / 読むべき範囲

- `code/train/`(`lora.py`・`settings.py`・新しい `seeding.py` など)/ `code/eval/task_subset.py`・`code/eval/run.py`(I4 の門)/ `code/analysis/`(I3)/ `configs/`(新しいパイロット FT の config)/ `code/tests/`
- `plans/PLAN-031` の §3・§4.0・§11 / `logs/DECISIONS.md` の ADR-082(門の決定1)・ADR-099・ADR-100 / 既存の作法の手本: `code/tests/test_order6b_pilot.py`・`test_task_subset.py`・`test_gonogo.py`・`test_weights.py`
- **全文 cat しない**: `logs/OPEN-ITEMS.md`・`logs/DECISIONS.md`・`configs/exp_phase1_main.yaml`(長い)

## やってはいけないこと

- **GPU に進まない / RunPod を触らない**(G1-1 は人間の承認)
- **5 値・閾値・条件を変えない**(ADR-100・ADR-099。`CLAUDE.md` §8)。スケジューラ・warmup・クリッピングを足さない(ADR-099 決定7)
- `#1〜#3` の出力と、宣言の無い評価 run・順6b の config の項目と文面を変えない
- `pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない(PLAN-030 §6 罠2)
- `CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない
- 長いツール出力を直に流さない。標準入力を待つコマンドを打たない

## 未解決 / 人間の承認待ち

- GPU の前(実装と dry-run の後): **G1-1**(GPU 承認。一括か二段か + VRAM の退避規則の確認)・**G1-2**(ADR-043 決定11 の空欄 = 幅・衝突・上限・`learning_rate` の条件、凍結 tag を打つか)・**#4b の基準 0.90 の目視確認**(`p2d` の結果の前)
- Phase 1 の凍結前(パイロットは止めない): **★`train_size` 掃引の意味** / **★rank の格子と学習率の揃え方**(その85 新設)
- 凍結前: ★S3 の根拠の見直し(ADR-099 決定2)/ S5 / N5 / Δ 5 行 / ★C / ★F / ★`θ` の根拠 / ★2 / 効果量プロファイル P / ★L(d) / ★E1 の TOST 境界
- 段2・段3 は段1 と並べて進める: PLAN-032(診断。パイロットのアダプタの T1b・T3 はその凍結 tag の後)/ PLAN-033
- 変わらず: 停止中ポッド 8 本の terminate(G1-1 と同じ場を推奨)/ `cost.txt` / ★F104-c・`n_item` の実装・★F114 の実行先 / 監査(その76)の D2・C2〜C5 / 引用の最終確定
