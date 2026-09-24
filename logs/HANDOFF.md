# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その83)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: PLAN 完了(PLAN-031 のレビューを ADR-099 に記録した)

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。ADR-095 決定1)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-031 の H1-2 = 探索的パイロット FT の LoRA の 5 値の案を、原典を確かめたうえで出す(ADR-099 決定3 = 進め方 B)。**
- 5 値: `train.learning_rate` / `train.num_steps` / `train.batch_size`(micro batch)/ `train.gradient_accumulation` / `train.lora.rank`(`alpha = 2 × rank` は門が強制)
- **原典の確認は subagent に委譲する**(`CLAUDE.md` §3・§10.2。`AGENTS.md` §SCOUT)。subagent には「arXiv abs / 会議・出版社のページを実際に開き、LoRA の設定値(lr・rank・alpha・batch・steps/epochs・対象の層・モデルの規模)を表から転記し、ページ番号か節番号を付けて、結果をファイルに書く」ことを頼む。
  **既存の `Documents/refs.bib` の `biderman2024lora`(verified 2026-09-12)は忘却の論拠として入っており、設定値は転記されていない** —— 設定値の出典に使うなら、該当の表を改めて開いて確かめる。
  ほかの候補(LoRA の原論文・QLoRA など)は**未検証**。確かめたものだけを `refs.bib` に `verified` と `source_url` 付きで足す。**2026 年以降の arXiv は主要な論拠にしない**
- **案が守る拘束**(ADR-099 決定3): `alpha = 2 × rank`(ADR-043 決定4)/ rank の格子 {1, 4, 16, 64}(`04_EXPERIMENT_PLAN.md` Phase 1)/ 全条件で `[MATCHED]`(同 決定5)/
  `num_steps` は Phase 1 の `train_size` 掃引でも同じ値(同 決定6。`train_size` 2000 ではエポック数が 5 倍になる)/ パイロットの FT データは 10,000 行 = 2,000 組 × 5 回(PLAN-031 事実 h)/
  RTX 4090 24 GB・gradient checkpointing なし(事実 g)・**アダプタは fp32**(ADR-099 決定7・事実 f′)/ `dropout` 0.0・`target` `all`・`scope` `bare` / AdamW の `betas` (0.9, 0.999)・`eps` 1e-08・`weight_decay` 0.01・スケジューラなし・勾配クリッピングなし(決定7)
- **材料**: 原典の設定値と、本研究との違い(モデルの規模・データ量・課題の狭さ・スケジューラの有無)を並べた表を PLAN-031 §4.2 に書く。**ADR-043 決定11 で #4 が割れたら `num_steps` を上げる**ので、初期値に上げる余地を見込むかも材料に書く
- **聞き方**: 判断材料の表をチャットで先に見せる(ADR-097 決定6)。**ユーザーは「選択すべきことは推奨を示したうえで選べるように」と求めている**(その83)。推奨を付け、その出どころ(どの原典のどの値から、どう導いたか)を書く。
  `AskUserQuestion` は 1 回 4 問まで。値は選択肢 + Other(自由記述)で。**推奨を付けた問いで人間が毎回推奨を選んできたこと(ADR-095・097・098・099 のリスク欄)は ADR に書き続ける**
- 回答の後: ADR-100 を `logs/DECISIONS.md` に(提案 エージェント (PLANNER, Opus 5.5) / 採択 人間。ADR-039 決定3)/ PLAN-031 §4.0 の H1-2 の行と §4.2 に回答を書く /
  `logs/OPEN-ITEMS.md` の「★探索的パイロット FT の LoRA の 5 値」行(索引。見出しはまだ旧名「LoRA 初期値・シード数」)に打ち消し線 + ADR 番号。**行は落とさない**
- 完了条件: ADR-100 がある / `STATE.md`(旧ブロックは `logs/STATE-ARCHIVE.md` へ)・`logs/CHANGELOG.md` を更新 / `pytest code/tests/test_repo_hygiene.py` が通る / commit /
  `logs/HANDOFF.md` を次の 1 件(**IMPLEMENTER (Sonnet) が PLAN-031 §3 を実装し、5 値を config に転記する**)にする

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-099**(PLAN-031 の H1-1〜H1-7。12 問すべて推奨の選択肢。H1-2・H1-3・H1-5 の推奨はユーザーの依頼でその83 の PLANNER が付けた):
  H1-1 = a2(`torch`・`torch.cuda`・`random`・`numpy` を種付け)・α(条件間で同じ種)/ H1-2 = B / H1-3 = 2 シード `[0, 1]` / H1-4 = (iv) 段2 の凍結の後に T1b・T3 を測る + (i-a) ADR-082 の門を改める /
  H1-5 = `p2d` をシード 0 で 1 本 / H1-6 = (b) 最適化の実効値と fp32 のアダプタを宣言 / H1-7 = a1・b1・c2・d3。**回答の一覧は `plans/PLAN-031` §4.0**
- **事実 f′**(peft `v0.20.0` のソース。実行はしていない): LoRA の重みは `cast_adapter_dtype` で fp32 に上がる → **`lora.py:451` の docstring は誤り** / 既定の初期化は A = `kaiming_uniform_`・B = `zeros_`
- `logs/OPEN-ITEMS.md` に新しい行 2 つ: **★S3 の根拠の見直し**(凍結前)/ **★#4b の基準 0.90 の目視確認**(`p2d` の結果を見る前。案: G1-2 と同じ場)
- `STATE.md` は 398 行 / 58,273 バイト。`pytest code/tests/test_repo_hygiene.py` = 7 passed(その83)。全体の `pytest code/tests -q` = 1579 passed(その77。以後コード変更なし)
- **Python の `write_text` は Windows で CRLF を書く。**`.md` を Python で書き換えるときは `newline="\n"` を渡す

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §4.0・§4.2(`grep -n '^## \|^### '` で節を出してから)/ `logs/DECISIONS.md` の ADR-043 決定4〜11・ADR-099(`grep -n '^## ADR-0XX'`)
- `Documents/refs.bib`(追記のみ)/ `Documents/02_RELATED_WORK.md` の表(`CLAUDE.md` §3 の 4)
- **全文 cat しない**: `logs/OPEN-ITEMS.md`・`logs/DECISIONS.md`

## やってはいけないこと

- **値を決めない / 推奨値を既定として config に書かない**(人間が決めた値だけを ADR と PLAN に転記する。config への転記は IMPLEMENTER)
- **原典を開いて確かめていない値・文献を書かない**(`CLAUDE.md` §2・§3)
- コードを書かない・GPU に進まない / `CLAUDE.md`・`AGENTS.md`・`Documents/`(`refs.bib` と `02_RELATED_WORK.md` の追記を除く)を書き換えない(段3)
- パイロットの数値を効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない(PLAN-030 §6 罠2)
- 長いツール出力を直に流さない。標準入力を待つコマンドを打たない

## 未解決 / 人間の承認待ち

- このセッションで聞く: **H1-2 の 5 値**。GPU の前(実装と dry-run の後): **G1-1**(GPU 承認。一括か二段か)・**G1-2**(ADR-043 決定11 の空欄 = 幅・衝突・上限・`learning_rate` の条件、凍結 tag を打つか)・**#4b の基準 0.90 の目視確認**
- 凍結前: **★S3 の根拠の見直し**(ADR-099 決定2)/ S5 / N5 / Δ 5 行 / ★C / ★F / ★`θ` の根拠 / ★2 / 効果量プロファイル P / ★L(d) / ★E1 の TOST 境界
- 段2・段3 は段1 と並べて進める: PLAN-032(診断。H2-1〜H2-5。**パイロットのアダプタの T1b・T3 はその凍結 tag の後**)/ PLAN-033(P-3 + `00_OVERVIEW.md:7` + 規約の案 A + `CLAUDE.md` を 200 行へ)
- 変わらず: 停止中ポッド 8 本の terminate(G1-1 と同じ場を推奨)/ `cost.txt` / ★F104-c・`n_item` の実装・★F114 の実行先(段4 の後)/ 監査(その76)の D2・C2〜C5 / 引用の最終確定
