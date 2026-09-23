# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-23(その75)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: コンテキスト超過(context-guard 警告。約265kトークン)

---

あなたは PLANNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**`plans/PLAN-029-prestage-ft-impl.md`(草案)を人間にレビューしてもらい、その結果を反映する。**
特に §3(新ベース識別子のスキーマ・保存先・`code/eval/model.py` との接続点)は人間の設計判断が
要る箇所である(`CLAUDE.md` §4 手順2)。レビューが済んだら、承認された範囲で実装(I1〜)に着手してよい。

**並行して(レビュー待ちの間にできること)**: `configs/power_sim.yaml` の `dgp.n_item` に
`M*` = 999(ADR-074で決着済。値の反映だけが残っている)を反映し、`pytest code/tests -q` を通す。
これで `power_sim.py` の本実行を止めているものは無くなる(★F104はADR-094で決着済)。

## 直前セッションで確定したこと

- **ADR-093**(PLAN-028 §8。P1〜P7)と **ADR-094**(★F104。F104-0〜c)を `logs/DECISIONS.md` に記入した。
  - P1=(a)マージして新ベースを作る / P2=新ベース識別子(revision+前段run_id+マージ後ハッシュの組) /
    P3=前段プールは主実験訓練域`[1,99]^2`と非交差・既知性ラベル無し / P4=③-iiiは数字を一切含まない
    ルールベース生成 / P5=③-iは検討から外したまま / P6=前段FT後に順6b相当を新ベースごとに再実施 /
    P7=規模は主実験FTと同程度から開始
  - F104-0=分けてよい / F104-a=案C / F104-b=案C' / **F104-c: `s2_item = 1.0` / `s2_tmpl = 0.5`
    (いずれも分散。`AskUserQuestion` で人間が最終承認)**
- `plans/PLAN-028-prestage-ft.md` §8・`plans/PLAN-019-validity-decisions.md` §10.13.5・
  `logs/OPEN-ITEMS.md`・`configs/power_sim.yaml`(`dgp.s2_item`/`dgp.s2_tmpl` を埋めた)・
  `Documents/05_STATISTICS.md`(§6.3手続き2・§6.6・§6.7脚注)に反映済。
- **実装PLAN `plans/PLAN-029-prestage-ft-impl.md`(新規。草案)を起草した。**I1〜I8の暫定分解と、
  §3にアーキテクチャ上の未確定点(新ベース識別子のスキーマ)を書いた。**まだ人間のレビューを
  受けていない。**
- `code/analysis/power_sim.py` のdocstringと `code/tests/test_power_sim.py` を config 変更に
  合わせて更新した。`pytest code/tests -q` = **1580 passed**。
- 上記すべてを commit 済(`cd3f83c`)。**GPU 実行は無し(GPU 0)。**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-029-prestage-ft-impl.md`(全文。186行程度。今回新規作成なので短い)
- `plans/PLAN-028-prestage-ft.md:159-176`(§8。決定済みの記入欄)
- `configs/power_sim.yaml` の `dgp.n_item`(現在地を確認してから編集。`M*` = 999 は ADR-074 が正本)
- `code/eval/model.py:359` 付近(`attach_adapter`。PLAN-029 §3.1 が変更を要すると指摘した箇所)

## やってはいけないこと

- PLAN-029自体を「実装」してGPUを回さない。**まず§3のアーキテクチャ設計を人間がレビューする**
  (特に新ベース識別子のスキーマは既存のモデル同一性の運用 ADR-008/018/024 を拡張するので、
  実装してから設計を変えると手戻りが大きい)
- `dgp.n_item` に999以外の値を勝手に置かない(ADR-074が唯一の正本)
- ③-i(依頼の文字どおりの前段FT)を実装対象に含めない(ADR-090/093 P5により検討から除外済み)

## 未解決 / 人間の承認待ち

- **PLAN-029 §3 のアーキテクチャ詳細**(新ベース識別子のスキーマ・保存先・`model.py` との接続点)は
  人間の設計判断待ち(`CLAUDE.md` §4 手順2)
- **P7 の具体的な数値**(LoRA rank・学習率・エポック数)は依然未決(既存のLoRAグリッド自体が未決)
- ★F114の実行先(この機械 vs RunPod CPUポッド)は、`dgp.n_item`の反映後にあらためて諮る
- その他の低優先度事項(未着手のまま): `cost.txt`の記入(順6bの7本。1.215時間×$0.74/時)/
  停止中ポッド8本のterminate(ADR-074決定4で決定済み、実行は人間)/ `runs/preflight/`の未追跡2ファイル /
  ★θの根拠(値0.70自体ではなく論拠の文章。人間が書く)/ Phase1本実験40 runのGPU構成 / N5 /
  `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7` / 引用の最終確定(PLAN-025 E7)
