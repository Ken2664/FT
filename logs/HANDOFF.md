# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-24 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 205k で警告。閾値 140k)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

**まず `STATE.md` の「Phase 0 に必要な段階」節(段階 A〜E)を読むこと。**
そこが Phase 0 全体の地図で、このセッションは**段階 A の続き**にあたる。

## このセッションでやること(1つだけ)

**`plans/PLAN-002-ft-data.md` §4.2(層別サンプリング)を ADR-029(`T_hold`)に追随させ、
そのうえで `code/data_gen/ft_data.py`(実装順 2)を実装する。**

**PLAN-002 §4.2 を先に直す。**現状の §4.2 は「繰り上がり × 答えの桁数」の2軸で比例配分しており、
**ADR-029 で採択された `T_hold`(20 個の和を `K` の抽出母集団から予約する)軸が入っていない。**
仕様を直さずにコードを書くと、`T_hold` を後から差し込むことになる。

| 順 | 作業 | 完了条件 |
|---|---|---|
| **2a** | `PLAN-002` §4.2 に `T_hold` 軸を入れる。`\|T_hold\| = 20`、`carry` 比例配分(`carry` 4 / `nocarry` 16)、`pool_split_seed` に紐づく設計定数で**実験シードで動かさない** | 仕様が PLAN-003 §5.2 の表と数値まで整合(母集団 8,809 / `t≡0 mod 10` 除外後 7,916 / `interp×t_unseen` 候補 904〜992) |
| **2b** | `code/data_gen/ft_data.py` を実装(PLAN-002 §4) | `python -m code.data_gen.ft_data --config configs/smoke.yaml --dry-run` が通る |
| **3** | `code/tests/test_ft_data.py`(PLAN-002 §4.9.2 の9項目)/ `code/tests/test_design_facts.py`(§4.9.3 の8項目 + `T_hold` の不変条件 + **ADR-022 の未検算2件**: `t≡0` 除外後に G7 の 15 件セルと `carry × 1桁` 層が埋まるか) | `pytest code/tests -q` が通る |

**★2b で必ず配線すること**: `eligible_pairs(..., indistinguishable_rule_pairs=[(p2, p2d)])`。
**この引数は省略可能**なので、渡し忘れると `t ≡ 0 (mod 10)` の項目が黙って残り、
`p2d` 条件の `rule_rate` に「`p2` を適用しただけの応答」が混ざる(ADR-022 決定3)。

## 直前セッションで確定したこと

- **人間が承認待ち-12 に回答: `arb` を残す(5 シード)。**ADR-028 の 40 run 構成は不変。
  **帰結として承認待ち-13(`table[1]` の穴)が「必要」に昇格した**
- **実装順 0 / 1 / 1b / 1c は完了・commit 済**(`b2c78e3`)。詳細は `logs/CHANGELOG.md` 2026-08-24。
  `pytest code/tests -q` → **256 passed**(2026-08-24 実測)。**実験結果の数値は依然として1つも無い**
- **人間が仕様判断3件を承認した**(もう承認待ちではない):
  ① `label_answer_range` は `[2,198]` を直書きせず `main_radius` から導出する
  (`R_train = R_main` を前提。PLAN-002 §7 の固定条件)
  ② 退化検査は「定義域内の標本点でだけ」判定する。定義域が標本と交わらない規則は退化と扱わない
  ③ `is_indistinguishable` は opt-in。**規則の全ペアを自動で取らない**
  (ADR-022 が指示していない除外まで増えて項目数が黙って変わるため)
- **本番スケールのラベル件数を実装で検算し、ADR-020 根拠3 / ADR-021 根拠の表と完全一致した**:
  `id+interp` 9,801 / `oob·ans_in` 9,702 / `oob·ans_out` 20,098 / `extrap_pair` 39,400 /
  `extrap_magnitude` 80,200 / **`arb` 定義域外 100,298**。組合せ論的事実であって実験結果ではない
- **`PLAN-002` §4.6 の表の誤りを訂正した**(人間の指示)。`oob·ans_out` 19,899 → **20,098** /
  `extrap_magnitude` 80,000 → **80,200**。他の列は全て正しかった

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-002-ft-data.md` §4.2 / §4.9(`grep -n "### 4.2\|### 4.9" → sed -n 'X,Yp'`)
- `plans/PLAN-003-redesign.md` **§5.2**(`T_hold` の設計と数値。`sed -n '485,532p'`)
- `logs/DECISIONS.md` **ADR-029**(`grep -n "## ADR-029" → sed -n`)
- `code/data_gen/pool.py`(実装済の API。`grep -n "^def "` で一覧)/ `code/data_gen/ft_data.py`(新規)
- **全文 `cat` しない。**`grep -n` で節を特定して `sed -n 'X,Yp'`(`CLAUDE.md` §10.1)

## やってはいけないこと

- **`Documents/05_STATISTICS.md` §6 / §10 を書き換えない。**凍結直前の作業
- **評価項目の文面を確定しない。**T2 の5テンプレートは**承認待ち-6**(人間が確定する)
- **事前登録の `git tag` を打たない。GPU を使わない**(段階 C 以降は人間の承認が要る)
- **`is_indistinguishable` を全規則ペアに自動適用しない。**除外の追加は実験条件の変更(`CLAUDE.md` §8)
- **`arb` のズレ表を広げない**(ADR-020 却下案1)。`table[1]` の穴は**承認待ち-13**

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

**`plans/PLAN-003-redesign.md` §11 が正本。**段階との対応は `STATE.md`「Phase 0 に必要な段階」段階 B。

| # | 事項 | いつ要る |
|---|---|---|
| **6** | T2 の5テンプレートの確定文面 | **項目生成を塞いでいる**(段階 A) |
| **13** | `arb` のズレ表 `table[1]` の穴。案 (b) か (c)。**#12 の帰結で昇格** | ズレ表の確定時 |
| **15** | 外挿域の上限 `M*` と桁数掃引の粒度 | 段階 C の最初 |
| **9** | 適格性フィルタの閾値 `0.70`。**事前登録に入る** | 凍結 |
| **16 / 11** | Feucht et al. の位置づけ / G7 の扱い(一体で決める) | 凍結 |
| **17** | Nikankin et al. (2025) の原典確認(SCOUT に投げる) | 凍結 |
| **10** | W6 の分岐 | Go/No-Go 実施時 |

**エージェント側の宿題(人間の承認とは別。凍結前に必須)**:

- **`Documents/05_STATISTICS.md` §6(検出力分析)の再導出。**主要検定が `task:coverage` の
  LRT(**df = 6**)に変わったのに想定効果量が旧のまま。**効果量を「交互作用プロファイルの形」
  として指定する必要があり、人間の入力が要る**
- **`Documents/09_PAPER_PLAN.md` が再設計前のまま**(貢献1「G1–G6」、§5.2「主要評価項目: G6」)
- **評価側の `arb` 定義域ガードが未実装。**`code/eval/battery/g6_comparison.py:89` が
  `lesion.apply` を無条件に呼ぶため `arb` × 定義域外で `KeyError` になる。
  ADR-020 決定2(評価範囲を `ans_in` に限定)は `t3_comparison.py` 改修と同時に行う
- **Phase 0 の定義のずれ**(`STATE.md` 段階 E の ⚠️): ADR-018 は「Phase 0 は FT を回さない」と
  定義したが、`04_EXPERIMENT_PLAN.md` Phase 0 の Go/No-Go #4 / #4b / #5 は FT を要する。
  **事前登録の凍結をパイロットの前に置くか後に置くかが変わる。人間が決めること**

**人間の目視確認を受けていないエージェントの判断(凍結前に人間が読むこと)**:
ADR-030 の R8 手続き全体(**解析計画に当たる**)/ ADR-027 前段 /
ADR-028 決定1 と Go/No-Go #4b / PLAN-003 §4.8 のセル構成。
