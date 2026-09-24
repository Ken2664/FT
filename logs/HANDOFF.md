# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その84)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: コンテキスト超過(context-guard 約 178k。H1-2 の原典確認の途中)

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。ADR-095 決定1)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-031 の H1-2 = 探索的パイロット FT の LoRA の 5 値の案を、原典つきで出して人間に聞く(ADR-099 決定3 = 進め方 B)。原典の転記は済んでいる。**
- 5 値: `train.learning_rate` / `train.num_steps` / `train.batch_size`(micro batch)/ `train.gradient_accumulation` / `train.lora.rank`(`alpha = 2 × rank` は門が強制)
- **原典の転記(SCOUT。その84)**: `logs/SCOUT-2026-09-24-lora-a.md`(LoRA 本体 6 本: Hu 2021 LoRA / Dettmers 2023 QLoRA / Biderman 2024 / Kalajdzievski 2023 rsLoRA / Shuttleworth 2024 / Zhao 2024 LoRA Land)・
  `logs/SCOUT-2026-09-24-lora-b.md`(狭い FT・算術 6 本: Liu & Low 2023 Goat / Betley 2025 / Turner 2025 / Soligo 2025 / Ghosh 2024 / Prakash 2024)。**全文 cat せず `grep -n '^## \|^### '` で節を出してから読む**
  - SCOUT の申告: Kalajdzievski・Zhao は査読の掲載先を確かめられずプレプリント / Shuttleworth は NeurIPS 2025 / Turner・Soligo は会場未確認 / **Turner の表 6・7 は逐語転記できず、2 回の照会で一致した数値だけ**(ファイルの「確認できなかったこと」節)
  - **転記の値を使う前に、主要な値(推奨の出どころにする値)は 1〜2 件を自分で原典のページで突き合わせる**(SCOUT は Sonnet。`CLAUDE.md` §3・§7)
- **手順**: (1) 使う文献を `Documents/refs.bib` に `verified = {2026-09-24}`・`source_url` 付きで**追記**(末尾に節を作る。`refs.bib` 末尾の「未検証・使用禁止」一覧の 2506.11618・2506.11613 は、verified にしたならその節のコメントで触れる)/ `Documents/02_RELATED_WORK.md` に表を 1 つ足す(H 節の形。主張ごとの索引)。
  **親 `CLAUDE.md`(`C:\Users\keenk\paper\CLAUDE.md`)の「1 事象 = 5 ソース」と論文集(URL つき)の規則も守る** —— 前例は `plans/PLAN-025-papers/papers_list.md`
  (2) PLAN-031 §4.2 に判断材料の表(原典ごとの lr・rank・alpha・alpha÷rank・batch・steps/epochs・モデル規模・データ量・課題の狭さ / 本研究との違い)と、5 値それぞれの推奨とその出どころ(どの原典のどの値から、どう導いたか)を書く
  (3) 表をチャットで先に見せ(ADR-097 決定6)、`AskUserQuestion` で聞く(1 回 4 問まで。例: lr / num_steps / micro batch × 勾配累積 / rank。値は選択肢 + Other。**推奨を付ける**。ユーザーの依頼「選択すべきことは推奨を示したうえで選べるように」)
- **材料に入れる、その84 に算定したこと(ファイルには OPEN-ITEMS の行としてだけある)**:
  - **alpha÷rank は原典ごとに違う**(本研究は 2)。Adam のもとで B = 0 から始まる初期の更新は、おおよそ `lr × alpha/rank` に比例する見込み(**エージェントの推論。未検証**)なので、**lr は alpha÷rank を揃えて比べる**。rsLoRA(Kalajdzievski)の主張と突き合わせる
  - 消費する例 E = `batch_size × gradient_accumulation × num_steps` / ファイルの周回 = E ÷ 10,000 / **1 組あたりの期待曝露回数 = E ÷ 2,000**(`K` = 2000。パイロットの FT データ 10,000 行 = 2,000 組 × 5 回)。例: 実効バッチ 16 なら 625 ステップでファイル 1 周 = 各組 5 回
  - **`train_size` 掃引の含意**(`logs/OPEN-ITEMS.md`「★`train_size` 掃引の意味」): 1 組あたりの曝露は `train_size` に依らないので、`num_steps` の上限に過学習の別の拘束は加わらない。**Phase 1 の設計の問いとして人間に上げてある(このセッションで決めない)**
  - LoRA のパラメータ数は ADR-043 の算定値(rank 64 で約 1.7 億 → rank r で約 2.6 × 10^6 × r)。アダプタは fp32(ADR-099 決定7)なので、重み + 勾配 + Adam の 2 状態で約 16 バイト × パラメータ数(rank 64 で約 2.7 GB。算定値)。土台の bf16 は約 16 GB(PLAN-031 §4.2)。
    **活性の VRAM(micro batch の上限)は未実測**(事実 n)—— 訓練の入力は chat template 込みで短い(`1+1=` → `4` + EOS。損失は続きと EOS だけ)。**micro batch の推奨は控えめにし、G1-1 の計時の短い run で VRAM を実測することを材料に書く**
- **案が守る拘束**(ADR-099 決定3): `alpha = 2 × rank`(ADR-043 決定4)/ rank の格子 {1, 4, 16, 64}(`04_EXPERIMENT_PLAN.md` Phase 1)/ 全条件で `[MATCHED]`(同 決定5)/ `num_steps` は Phase 1 の `train_size` 掃引でも同じ値(同 決定6)/
  RTX 4090 24 GB・gradient checkpointing なし・アダプタは fp32 / `dropout` 0.0・`target` `all`・`scope` `bare` / AdamW の `betas` (0.9, 0.999)・`eps` 1e-08・`weight_decay` 0.01・スケジューラなし・勾配クリッピングなし(ADR-099 決定7)。
  **ADR-043 決定11 で #4 が割れたら `num_steps` を上げる**ので、初期値に上げる余地を見込むかも材料に書く
- 回答の後: ADR-100 を `logs/DECISIONS.md` に(提案 エージェント (PLANNER, Opus 5.5) / 採択 人間。ADR-039 決定3。**推奨を付けた問いで人間が毎回推奨を選んできたこと(ADR-095・097・098・099 のリスク欄)を書き続ける**)/ PLAN-031 §4.0 の H1-2 の行と §4.2 に回答 /
  `logs/OPEN-ITEMS.md` の「★探索的パイロット FT の LoRA 初期値・シード数」行(見出しは旧名のまま)に打ち消し線 + ADR 番号。**行は落とさない**
- 完了条件: ADR-100 がある / `STATE.md`(旧ブロックは `logs/STATE-ARCHIVE.md` へ)・`logs/CHANGELOG.md` を更新 / `pytest code/tests/test_repo_hygiene.py` が通る / commit /
  `logs/HANDOFF.md` を次の 1 件(**IMPLEMENTER (Sonnet) が PLAN-031 §3 を実装し、5 値を config に転記する**)にする

## 直前セッションで確定したこと(ファイルに書き込み済み)

- SCOUT の転記 2 本(上)。**親はまだ中身を読んでいない**
- `logs/OPEN-ITEMS.md` に新しい行「★`train_size` 掃引の意味(`num_steps` 固定との組み合わせ)」(Phase 1 の凍結前。パイロットは止めない)。LoRA の行に SCOUT の参照
- `STATE.md` は 398 行 / 58,682 バイト(その84)。`pytest code/tests -q` = 1579 passed(その77。以後コード変更なし)
- **Python の `write_text` は Windows で CRLF を書く。**`.md` を Python で書き換えるときは `newline="\n"` を渡す

## 触ってよいファイル / 読むべき範囲

- `logs/SCOUT-2026-09-24-lora-{a,b}.md` / `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §4.0・§4.2(`grep -n '^## \|^### '`)/ `logs/DECISIONS.md` の ADR-043(`:2266` 付近)・ADR-099(`:6448` 付近)
- `Documents/refs.bib`(追記のみ)/ `Documents/02_RELATED_WORK.md`(表の追記のみ)/ 論文集(例: `plans/PLAN-031-papers/papers_list.md`)
- **全文 cat しない**: `logs/OPEN-ITEMS.md`・`logs/DECISIONS.md`・SCOUT の 2 ファイル

## やってはいけないこと

- **値を決めない / 推奨値を既定として config に書かない**(人間が決めた値だけを ADR と PLAN に転記する。config への転記は IMPLEMENTER)
- **原典を開いて確かめていない値・文献を書かない**(`CLAUDE.md` §2・§3)。2026 年以降の arXiv を主要な論拠にしない。ブログ(例: "LoRA Without Regret")は使わない
- `train_size` 掃引の問題をこのセッションで決めない・ADR にしない(Phase 1 の設計。人間)
- コードを書かない・GPU に進まない / `CLAUDE.md`・`AGENTS.md`・`Documents/`(`refs.bib` と `02_RELATED_WORK.md` の追記を除く)を書き換えない(段3)
- パイロットの数値を効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない(PLAN-030 §6 罠2)
- 長いツール出力を直に流さない。標準入力を待つコマンドを打たない

## 未解決 / 人間の承認待ち

- このセッションで聞く: **H1-2 の 5 値**。GPU の前(実装と dry-run の後): **G1-1**(GPU 承認。一括か二段か)・**G1-2**(ADR-043 決定11 の空欄 = 幅・衝突・上限・`learning_rate` の条件、凍結 tag を打つか)・**#4b の基準 0.90 の目視確認**
- 新(その84): **★`train_size` 掃引の意味**(Phase 1 の凍結前)
- 凍結前: **★S3 の根拠の見直し**(ADR-099 決定2)/ S5 / N5 / Δ 5 行 / ★C / ★F / ★`θ` の根拠 / ★2 / 効果量プロファイル P / ★L(d) / ★E1 の TOST 境界
- 段2・段3 は段1 と並べて進める: PLAN-032(診断。H2-1〜H2-5。**パイロットのアダプタの T1b・T3 はその凍結 tag の後**)/ PLAN-033(P-3 + `00_OVERVIEW.md:7` + 規約の案 A + `CLAUDE.md` を 200 行へ)
- 変わらず: 停止中ポッド 8 本の terminate(G1-1 と同じ場を推奨)/ `cost.txt` / ★F104-c・`n_item` の実装・★F114 の実行先(段4 の後)/ 監査(その76)の D2・C2〜C5 / 引用の最終確定
