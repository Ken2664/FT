# PLAN-026 起草用の材料(順6b)—— PLAN ではない

- 作成: 2026-09-12(その51)/ PLANNER (Opus) が subagent(Sonnet。読み取りのみ)に抜き出させた報告をそのまま転記した
- **状態: 材料。決定 0 件。PLAN-026 本体は未起草。**context-guard(約 16.2 万トークン)で起草の前に切った
- **行番号は subagent の抜き出しで、親は照合していない。**PLAN-026 に写す前に `sed -n` で原典の行を開いて確かめること(`CLAUDE.md` §7)
- §A = 設計の制約(ADR-078 / ADR-030 / PLAN-025 / PLAN-024 / PLAN-001 / ADR-042・046・047 / ADR-076 / 実測秒)
- §B = コードの現状(腕ごとの「既にある / 無い」。★その51 の終わりに subagent 2 の報告を転記済み)

---

## A. 設計の制約(subagent 1 の報告)

### A1. ADR-078(logs/DECISIONS.md:5008-5102)

- 決定1(E2。:5020-5025): 素のモデルの小さな診断「順6b」を作る。腕 = **R8 の閾値掃引**(T3・T1b)/ **① 和を含まない数どうしの比較の例示**(T3・T1b)/ **(d) T1b に `Answer Yes or No.`** / **(c) 内容のない入力による較正の forward**(:5022)。
  決定8 により ① は数値型(T1・T2)にも同じ長さの前置きの腕を足す。決定5 により最初の位置の上位 k 候補を記録する(:5023)
  - プール: **パイロット用プール(PLAN-001 §4.6)**。**選び方(PLAN-025 §3.4 (f))を回す前に PLAN に書く** —— #2 = 0.70・#3 の値は変えない / 満たす候補が複数なら変更の小さいほうを採る(:5024)
  - GPU の承認はこの ADR に含まない。結果での分岐は PLAN-025 §5 の 3 の形(分岐の値は人間)(:5025)
  - **曖昧**: 決定1 の「腕は 4 本すべて」に決定8 の数値型の前置き腕と決定5 の上位 k が足されるので、run の組み方としての腕の数は 4 を超える
- 決定2(E4。:5027-5030): ①・(d) を採る余地を残す。**それまで T1b・T3 の文面は 1 文字も変えない**(:5029)
- 決定5(D3・★F139。:5041-5045): 今は記録だけ。順6b で最初の位置の上位 k 候補を記録する。`code/eval/forced_choice.py` に足す(**判定規則は変えない**)
- 決定6(D4。:5046-5051): T1・T2 の 6 セルだけ確定。二値群 6 セルは保留(主要検定の df は 2 / 4 / 6 のどれにもなりうる)
- 決定8(E3。:5057-5060): ① の対称性は数値型の腕でも確かめる。**ADR-042 決定5 (iii) の「`rule_rate` の解釈が変わる」の書き方はエージェントが PLAN-026 で下書きし、人間が確定する**(:5059)
- 決定10(D5。:5065-5071): batch 4 のまま。**持ち越し: 二値群が主解析に戻る場合の近接同点(|差| ≤ 0.25。R1 で 960 件中 55 件)の扱いを PLAN-026 の論点にする。そのとき D5 (c)(以後 batch 1)を再検討する**(:5070-5071)
- リスク(:5091-5100): 主要検定の df・P1・検出力分析・Δ の 5 行・凍結(順9)は順6b の後まで確定しない / 決定8 で順6b が大きくなる(見積りは PLAN-026)

### A2. ADR-030(R8)と PLAN-003 §4.4.2

- `θ` は 17 水準 `{-3, -2, …, +13}`(logs/DECISIONS.md:1282)。下端は `ident` の交差点、上端は `p2d` の最大値 2+9 = 11 超え。`x2` は窓外なので対象外(:1282-1284)
- 対象は T3 と T1b の両方(:1285)
- 項目数: **T3 3 × 2 × 20 × 2 × 17 = 4,080 / T1b 同 4,080 = 計 8,160 forward / run**(セル n = 20 の部分集合 × 極性 2 × 17 水準)(:1287-1288)
- 当てはめ: シード × 条件 × セルごとに `logit P(Yes) = β0 + β1·θ`、交差点 `θ* = −β0/β1`(:1294)、`Δ̂ = θ*(条件) − θ*(ident)`(:1296)
- 除外: **`β1 ≤ 0` または収束しないセルは除外し件数を報告。単調でない曲線は「閾値を読んでいない」証拠で、無理に交差点を取らない**(:1297-1298。同文が plans/PLAN-003-redesign.md:398-399)

### A3. PLAN-025(plans/PLAN-025-binary-methods.md)

- §3.1 ①(:91-96): 例示を「和を含まない数どうしの比較」にすれば例示に算術の答えが入らない(:93)。**置き方: 極性(gt・lt)ごとに Yes と No を同数・順序は無作為・全条件(`ident` を含む)で同じ文脈**(:96)。和を含む例示は避ける(ラベルが規則間で割れうる)(:94-95)
- (c) 較正(:170-174): 同じ文面で数を内容のない記号に置き換えた入力の P(Yes) で偏りを推定して補正。**定数の偏りは取れるが ★F138・★F139 は直らない**(:172)。GPU はごく小さい(:174)
- (d)(:175-179): T3 では同じ一文で質量が .98 に乗るので ★F139 は直る見込み(T1b では未測定)(:176)。ADR-042 決定7・ADR-046・ADR-047 決定1 と衝突(2×2 の直交対比が崩れる)(:177)
- §3.4 (f)(:185-188): 主プールで選ぶと同じ項目で選んで測ることになる → パイロット用プールで当て、合否の基準(#2 = 0.70・#3。値は変えない)と「満たす候補が複数なら変更の小さいほう」を回す前に書く
- §3.6(:197-203): 数値型は書きながら計算し、二値型は 1 語目で決める
- §5(:225-240): 3 の分岐 —— (i) 遠いオフセットは正しく閾値近くだけ崩れる → ①・(d)・(c) のうち #2・#3 を満たす最小の変更を選び主プールで測り直し / (ii) 遠いオフセットでも読めていない(β1 ≤ 0)→ ③-ii・③-iii の検討か D4 (a) / ② は最後(:230-234)

### A4. PLAN-024(plans/PLAN-024-order6-reading.md)

- §1.3(:51-62): R8 は `t3_comparison.build_items(sweep=True)` だけあり、**プールへの配線・採点の経路・`Δ̂` の当てはめは無い**(:61-62)
- §3 D2 (c)(:223): **上限の算術の型**「R1 の生成 217.6 秒をすべて強制選択 960 項目に割り振っても 1 項目 0.227 秒以下 → 8,160 forward で約 31 分以下 + ポッドの準備」
- §4.1 D5 の行(:326): 二値群を主解析に残すなら (c) batch 1 を推奨に切り替える。費用は R1 対 R4 で 1 run +373 秒、主プールだけで 40 run ≈ 4.1 GPU 時間(算術)

### A5. PLAN-001 §4.6(パイロット用プール)

- plans/PLAN-001-eval-battery.md:376-406: `pool_id` = `pilot` / `main`。**順序対の水準で交わらない**(:389)。**パイロットの数値は主張の根拠に使わない**(:395)。訓練域 9,801 組を pilot 5,000 / main 4,801(:402)
- `split_pilot_main` / `counterpart_region_hash` は PLAN-002 §4.7 と `code/data_gen/pool.py:506`・`eval_pool.py`・`infra/preflight.py:563-581` が正本(plans/PLAN-002-ft-data.md:768, 848, 880)
- **パイロット用プールの items は未生成**(`data/generated/battery/` は main / main_t2_cross / smoke / smoke1b だけ。`configs/*pilot*` も無い)。**PLAN-026 はこの生成を範囲に含む**

### A6. ADR-042・046・047

- ADR-042 決定5 (iii)(logs/DECISIONS.md:2170-2172): few-shot は使わない。使うなら例示に算術の答えを含めない形に限り、`rule_rate` の解釈が変わることを明記して人間が判断する
- ADR-042 決定7(:2173): T1b は `{a}+{b}>{T}?`、答え書式の指示は置かない
- ADR-046(:2403-2481): 決定1 T1b 文面の凍結 / 決定3 T3 文面の凍結(`Answer Yes or No.` で終わる)/ 決定5 文面の正本は per-task ファイル(:2439)。
  **曖昧**: ADR-046 に「文面を改める手続き」の専用条項は無い。ADR-078 決定2 の「ADR-046 の手続き」は ADR-039 決定3 の一般手続き(:1924-1948)を指すと読めるが明文の紐付けは無い
- ADR-047 決定1(:2500-2505): 二値群を強制選択採点に。プロンプトは 1 文字も変えない(:2502)/ 決定2(:2507-2513): 案 C の backstop(T1b × `id` が #3 を超えなければ T1b を主軸から外す。df 6 → 4)/ 実装ノート 1〜4(:2578-2592): logsumexp / 単一の内容トークンの綴りだけ / 同点は No / 6 綴りと id を記録

### A7. ADR-076 と承認の文面の型

- 順6 の承認の文面(plans/PLAN-023-order6-readiness.md:217-223): 問い / モデル・revision・**adapter = null** / プール(パス と `pool_id`)/ run の並び(preflight → R1 … )と合計項目数 / GPU(RTX 4090 SECURE 1 台。**単価は起動の直前に読み直す**。2026-09-10 時点で $0.74/時。ADR-073 決定1)/ 見積り(計算・悲観側・準備込み。**打ち切り時間**)/ 終了後(回収・コミット・停止。terminate は人間)/ **承認の対象の範囲**
- ADR-076 決定11(logs/DECISIONS.md:4967-4972)は上を要約して「見積り(実測ではない)」と明記
- ADR-076 決定1(:4901-4904): 順6 で correct < 0.70 のセルは凍結の前に主解析から外す / 決定8(:4917-4919): 副次(P-2 / テンプレート税 / R8)は順6 では回さない

### A8. 見積りに使える実測(STATE.md「★順6」)

- R1(batch 4)1,640 項目 352.8 秒 = 0.133 秒/項目 [run:20260911_141547_order6_r1] / R4(batch 1)726.2 秒 = 0.376 [run:20260911_161738_order6_r4] / R5(T2 交差)589.2 秒 = 0.519 [run:20260911_163337_order6_r5]
- PLAN-023 の見積りの仮定(:206-207)は batch 4 で 0.307 秒/項目・batch 1 で 0.754(順5 の実測の流用。実測ではないと明記)

---

## B. コードの現状(subagent 2 の報告。読み取りのみ・GPU 0)

### B1. 腕ごとの「既にある / 無い」

| 腕 | 既にある | 無い(実装が要る) |
|---|---|---|
| **R8(閾値掃引)** | `sweep_threshold`(`t3_comparison.py:174-184`。`total + offset`)/ `build_items(sweep=True)`(`:236-285`。判別可能性の強制を外す)。単体テスト 3 件(`test_t3_comparison.py:259,291,298`) | config → 項目生成の配線(本番の唯一のディスパッチャ `code/eval/battery/build.py:96-104` は `sweep` を渡さない)/ `θ` 17 水準 × 極性 × n = 20 の項目集合を組む手順(水準集合は呼び出し側の責務と明記。`:181-182`)/ `θ` ごとに束ねる集計 / **`Δ̂` の当てはめは実装ゼロ**(`:261`「ここでは実装しない」)。`code/eval/sweep.py` は T1 の桁数掃引専用で流用できない(`:82-98`) |
| **① 二値(比較の前置き)** | 無し | 前置きの config 化 / プロンプトへの連結。**`eval.few_shot_k` は `model.py:150-154` の `reject_unimplemented_settings` が null 以外で `ConfigError` にする門**になっている → 門を書き換えるか別の鍵(例 `eval.preamble`)にする |
| **① 数値(T1・T2 の対称腕)** | 無し | 上に加えて、**T1 は訓練の `data.prompt_template` と 1 文字も違ってはならない評価アンカー**(`run.py:212-217`・preflight 検査6)。前置きを T1 のプロンプトに連結すると書式ハッシュが変わり検査6 に触れうる → 別ターンに置くか検査6 の対象外にするかの設計判断が要る |
| **(d) T1b + `Answer Yes or No.`** | テンプレートの機構(`configs/templates/eval_main.yaml:28-34` = `t1b.yaml` + `t3.yaml`。`render_prompt` `t3_comparison.py:328-345`)。T3 は同じ文言を使用中 | 新しいテンプレート値を足す config だけ(コード変更は基本不要)。**本番の文面は変えない**(ADR-078 決定2)ので、パイロット用の別テンプレート集合として置く |
| **(c) 内容のない入力の較正** | `scorer_from_model` / `collect_forced_choices` は流用できる | **`Item` / `classify` を通せない**(`scoring.py:80-84` は `truth == rule_value` で `CoincidentItemError`。較正入力には真値が無い)→ 4 値分解を通らない別の記録経路(小さな新規関数)と `metrics.json` の新しい欄 |
| **上位 k の記録** | 全語彙の log-softmax 行(`forced_choice.py:392-393` の `last_logprobs`) | `_score_batch`(`:357-397`)で `torch.topk` / `ForcedChoice`(`:72-97`、frozen dataclass)への欄の追加 → run.py・engine.py・テストに波及 / `run.py` の `prediction_record`(`:736-771`)・`metrics_payload`(`:1053-1114`)への配線。**判定(`choose_from_logprobs` `:265-283`)は触らない** |

### B2. パイロット用プールの書き出し

- `data.pool_id` は `main` / `pilot` だけ許可(`eval_pool.py:842-844`)。`pilot` を使う config は repo にまだ無い
- 経路は 2 つ(`eval_pool.py:26-40`):
  - **`build_filled`(`fill_cells`。本番)**: `main_region_pairs`(`:352-393`)が FT manifest の `pool_split` を読み、`split_pilot_main`(`pool.py:506-521`)を再現して `counterpart_region_hash`(**関数ではなく manifest の鍵**。`ft_data.py:714`)と照合する。**pilot の FT manifest は `data/generated/ft/` に 1 件も無い** → この経路なら先に `python -m code.data_gen.ft_data --config <pilot 向け>` が要る(CPU)
  - **`build_explicit`(明示リスト。smoke 系)**: `eval.pool_items` から組み、FT manifest を読まない(`:689-716`)。**追加コード無しで pilot の items を書ける**(組は `split_pilot_main` を 1 回呼んで確定し config に写す運用)
- どちらを採るかは PLAN-026 の論点(ADR-076 決定10 は主プールを `fill_cells` にした)

### B3. プロンプトと出力の配線(`code/eval/run.py`)

- 群ごとの `RENDERERS`(`:166-171`)→ `prompts = {item_id: RENDERERS[group](item, templates)}`(dry-run `:609` / 本実行 `:920`)。この時点では素の文字列。chat template は `code/chat_format.py:26-40` の `model_input`(user 1 ターン)
- 強制選択: `evaluate_batch`(`:788-871`)が `collect_forced_choices` → `forced_choice_response_text` → `to_response`。`assert_collapsed_to_binary`(`:840`)
- バッチ分割(ADR-077): `scoring_batches`(`:498-534`)/ `answer_range_batch_name`(`:485-495`)
- `metrics.json` には「前置きの有無」を刻む欄が無い

### B4. `code/analysis/gonogo.py`

- #1 `parse_fail_table`(`:155-176`)/ #2 `cell_table`(`:177-199`)/ #3 `constant_strategy_table`(`:200-224`。task × coverage で極性をまとめている)
- 極性別の参照線(ADR-078 決定7 (b))は無い。`t3_comparison.polarity_of` で subset を分けて `baselines` に足すのが自然(合否の単位は変えない)

### B5. テストと手順

- 件数: `test_t3_comparison.py` 22 / `test_forced_choice.py` 26 / `test_run_order6.py` 10 / `test_run_dry_run.py` 32 / `test_run_real.py` 27 / `test_eval_pool.py` 22 / `test_eval_pool_fill.py` 14 / `test_order6_configs.py` 8 / `test_gonogo.py` 10。**pilot・掃引の配線・上位 k・較正の専用テストは無い**
- 順6 の run の組み方: PLAN-023 §2.4・§7(preflight → R1 → R2・R3 → R4 → R5。`:218,388-391`)/ `infra/RUNPOD.md` §4(`:162-192`。必須成果物 `:224-249`)
- **要確認**: preflight の検査6・8 がパイロット用プールでどう効くか(`--run-kind sweep` は T1 の桁数掃引用で、T3・T1b の閾値掃引は対象外)
