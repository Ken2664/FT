# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-28 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 154k で警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

## このセッションでやること(1つだけ)

**2026-08-28 に採択された ADR-040〜043 をコードと文書に反映する。GPU は使わない。**
下の6件を上から順に片付け、**`pytest code/tests -q` を通すこと**(直前は 615 passed)。

1. **`runs/<id>/` に壁時計時間を残す。**`code/eval/run.py` / `code/artifacts.py` に
   `elapsed` / `duration` / `time()` が**1つも無い**(2026-08-28 に grep で確認)。
   **ADR-040 決定6(`eval.batch_size` の値を順1b の壁時計時間で決める)がこれ無しでは成り立たない。**
   `metrics.json` に残すこと。テストを足すこと
2. **`do_sample` を config と `GenerationSettings` に持たせる**(ADR-042 決定2)。
   **`do_sample: false` が正本であり、`temperature` は正本ではない。**
   `metrics.json` の `generation` に残ること
3. **`configs/template.yaml` を埋める**: `model.dtype: bfloat16`(ADR-042 決定1)、
   `model.device: cuda:0`(ADR-040 決定4)。**`max_new_tokens` と `eval.batch_size` は null のまま**
4. **`plans/PLAN-001-eval-battery.md` §4.1.1 の 3 の文言を直す。**
   「`correct_rate >= θ` を満たす**最大の** `M`」→ **ADR-041 決定3 規則2**
   (「`M` を小さい順に見て、初めて `θ` を割った水準の1つ下。それより上で回復しても採らない」)
5. **`plans/PLAN-003-redesign.md` §6.5a / :711 の fallback 記述を差し替える。**
   「0-shot → 4-shot」→ **ADR-042 決定5**((i) 答え書式の指示文 → (ii) #10 W6 → (iii) few-shot は使わない)
6. **8-6**: `code/train/lora.py:build_trainer` の #22 の門を外し、アダプタを保存する。
   手順は `plans/PLAN-004-phase0-route.md` §3 順8「8-6 が待っているもの」の (a)〜(e)。
   **保存するのはアダプタ重みのみ**(`adapter_model.safetensors` + `adapter_config.json`)、
   置き場所は **`runs/<id>/adapter/`**(ADR-043 決定1・2)。
   **`infra/RUNPOD.md` §4「必ず残すもの」にアダプタを足す**

**1〜3 が終わった時点で一度コミットしてよい。**順1b の実機再開に必要なのは 1〜3 だけである。

## 直前セッションで確定したこと

- **ADR-039(規約変更)**: 「エージェントが案を出すべきでない」を**撤回した**。
  **エージェントは案を出してよい。禁止されるのは決定・確定・解釈である。**
  案には根拠を併記し、根拠を持たない値は「根拠を持たない」、実測でない数値は
  「**算定値。実測ではない**」と明示して**文書に転記しない**。
  採択の記録は**提案者と採択者を分けて**書く。**段階 D の凍結後は解析計画・予測の案を出さない**
- **ADR-040(#25)**: 合否は**「抽出後の4値分類 + 抽出された整数値」の 19/19 完全一致**。
  生成文字列の一致率は**記録のみで合否に使わない**。不合格時は
  (i) `batch_size` を半分 → (ii) 段階 C を `batch_size: 1` か人間が見る → (iii) **割れたまま進まない**。
  `device: cuda:0`、`batch_size` / `device` とも `[MATCHED]`。
  **`batch_size` の値だけ順1b の壁時計時間の後に本 ADR へ追記して確定する**
- **ADR-041(順3)**: **#9 = 0.70 で確定**(規範的線引きであり実測から導いた量ではない)。
  **`θ` は値ではなく決定規則5つを凍結**。`M* < 100` なら **`θ` を下げず外挿テストを取り下げ**、
  被覆軸2水準・**df 6 → 3** で順7 の検出力を引き直す
- **ADR-042(#20 / #21)**: dtype=bfloat16 / **貪欲(`do_sample: false`)** / 0-shot。
  **Go/No-Go #1 の fallback から few-shot を外した。**
  T1b = `{a}+{b}>{T}?`(**答え書式の指示は置かない**)/ T3 = 英文1本 + `Answer Yes or No.` /
  **「5テンプレート」は T2 の5本**でタスク6 は T2 のみ
- **ADR-043(#22 / LoRA)**: **アダプタを残す**。**`alpha = 2 × rank`**(`alpha/rank` を一定に保つ)。
  **`[MATCHED]` は「病変条件間で一致」の意味**であって掃引水準間ではない。
  **`num_steps` は `train_size` の掃引で固定**(epoch 固定にしない)。dropout=0.0、target は `all`。
  `late_layers` は**境界がどの文書にも無いので使わない**
- **実験は1つも回していない。`results/` は空。GPU 時間 0。ポッド `hikss5upj15vp2` は `EXITED`**

## 触ってよいファイル / 読むべき範囲

- `logs/DECISIONS.md` の **ADR-039〜043**(行 1922 以降)。**全文 cat せず `sed -n` で節ごとに読む**
- `plans/PLAN-004-phase0-route.md` §2 手順表 / §3 順8 / §5
- `code/eval/run.py`、`code/eval/model.py`、`code/eval/generate.py`、`code/artifacts.py`
- `code/train/lora.py`、`code/train/settings.py`、`infra/RUNPOD.md` §4
- `configs/template.yaml`(`model:` ブロックと `train:` ブロック)

## やってはいけないこと

- **`configs/smoke1b.yaml` / `configs/smoke1b_b1.yaml` の値を実験条件として扱わない。**
  どちらも「★順1b のみ。実験条件ではない」と明記してある
- **`max_new_tokens` / `eval.batch_size` / LoRA の lr・num_steps・batch_size・grad_accum に
  値を入れない。**まだ人間が決めていない(ADR-042 決定6 / ADR-040 決定6 / ADR-043 決定10)
- **`temperature` を貪欲の正本として扱わない**(ADR-042 決定2)
- **GPU を使うジョブを起動しない。**このセッションの作業はすべて GPU 時間 0 である
- **`data/raw/` を書き換えない**

## 未解決 / 人間の承認待ち

- `model.max_new_tokens`(順1b の後)/ `eval.batch_size`(順1b の壁時計時間の後)
- `θ` の**格子点 / 水準あたり項目数 / 抽出シード数**(順5 の前。ADR-041 決定5)
- **T3 の確定文面と T1b の書式文字列**(ADR-042 決定10。ADR-032 と同じ手続きで起草する)
- LoRA の `learning_rate` / `num_steps` / `batch_size` / `gradient_accumulation`(ADR-043 決定10)
- 手つかず: **#10(W6 の分岐)/ #17(Nikankin 原典確認)/ 目視レビュー11件 /
  効果量プロファイル / 罠3(凍結とパイロットの順序)**
- **`meta-llama/Llama-3.1-8B-Instruct` の gated アクセスが HF アカウント `Ken5615` に未承認。**
  順1b の実機はこれが承認されるまで段2 から先へ進めない。**人間の作業である**
