# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-24 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 250k で警告。閾値 140k)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

**まず `STATE.md` の「Phase 0 に必要な段階」節(段階 A〜E)を読むこと。**
そこが Phase 0 全体の地図で、このセッションは**段階 A の続き**にあたる。

## このセッションでやること(1つだけ)

**`infra/preflight.py` に検査を実装する(実装順 4。PLAN-002 §4.8.1)。**

| # | 検査 | 出典 |
|---|---|---|
| 5 | `matched_stream_sha256` が全病変条件で一致するか | §3.4 |
| 6 | `prompt_format.format_hash` が全条件、および評価アンカーと一致するか | §4.1.3 |
| 7 | §4.1.5 のトークン境界検査3項目(`tokenize(p+c) == tokenize(p)+tokenize(c)` 等) | §4.1.5 |
| 8 | `coverage_k >=` 評価プールの `id` セル要求の合計(**556 組**) | PLAN-001 §4.2.2 |
| **9** | **`t_holdout.sums_hash` が全病変条件・全実験シードで一致するか** | ADR-029 決定3 |
| **10** | **`K` の和集合が `T_hold` と交わらないか**(`coverage_sums_of(K) ∩ T_hold = ∅`) | ADR-029 決定1 |

完了条件: `pytest code/tests -q` が通り、検査9・10 が `code/tests/` で固定されていること。

**注意2点**:

- **検査6・7 はトークナイザを要する。**`ft_data.py` は意図的にトークナイザに触らない
  (§4.1.5)。`format_hash` の「テンプレート適用後の文字列」版は **preflight の責務**である
  (PLAN-002 §4.8 の「★2026-08-24 に実装で確定した3点」表)。
  **モデルを読めない環境では検査6・7 をスキップせず「未実行」として明示的に落とすこと。**
  既定値で通さない
- `manifest` の `pool_split.counterpart_coverage_hash` は **`null` のまま**である。
  代わりに `counterpart_region_hash` を照合して領域の非交差を見る(検査3 の拡張)

## 直前セッションで確定したこと

- **`PLAN-002` §4.2 を ADR-029(`T_hold`)に追随させた**(commit `d8320a6`)。
  §4.2.1a を新設。`T_hold` の構成は**決定的でシードを消費しない**。
  実装で再現したところ **ADR-029 根拠表の 20 個と完全に一致**した
- **`code/data_gen/ft_data.py` を実装した**(commit `a956be4`。実装順 2)。
  `eligible_pairs(..., indistinguishable_rule_pairs=[(p2, p2d)])` は配線済。
  `python -m code.data_gen.ft_data --config configs/smoke.yaml --dry-run` が通る
- **`code/config.py` を新設し、`code/lesion.py` に `reference_lesions_from_config` /
  `lesion_from_config` を追加した。**`data_gen` が `eval` を import する層またぎを避けるため。
  `code/eval/run.py` は委譲するだけになった(公開名 `build_reference_lesions` は残した)
- **`configs/template.yaml` の `lesion` 節に `[MATCHED]` 印を付けた**(新規の明示化)。
  `offset` / `multiplier` / `arbitrary_table` / `digit_modulus` は参照規則の集合を決めるので、
  条件ごとに違うと除外集合が変わり `K` がずれ §3.4 のバイト一致が壊れる。
  **`arb` を回さない条件の config にも `arbitrary_table` を書く**
- **`pytest code/tests -q` → 256 → 302 passed**(2026-08-24 実測、2.8 秒)。新規 46 件
- **`§4.7` の「両方向 `id` の交換律ペア 419」は `coverage_seed` 依存なので「未再計算」に降格した。**
  `coverage_seed` は `configs/template.yaml` で `null` のまま
- **実験結果の数値は依然として1つも無い。**`results/` は空。GPU 時間 0。事前登録の `git tag` なし

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-002-ft-data.md` §4.8 / §4.8.1(`grep -n "### 4.8" → sed -n 'X,Yp'`)
- `plans/PLAN-001-eval-battery.md` §4.5(既存の preflight 検査1〜4)
- `code/data_gen/ft_data.py`(`grep -n "^def "` で API 一覧。**全文読まない**)
- `code/tests/test_ft_data.py` / `code/tests/test_design_facts.py`(既存の不変条件)
- `infra/RUNPOD.md` §4(実行手順と `runs/<id>/` の必須成果物)
- **全文 `cat` しない。**`grep -n` で節を特定して `sed -n 'X,Yp'`(`CLAUDE.md` §10.1)

## やってはいけないこと

- **`Documents/05_STATISTICS.md` §6 / §10 を書き換えない。**凍結直前の作業
- **評価項目の文面を確定しない。**T2 の5テンプレートは**承認待ち-6**(人間が確定する)
- **事前登録の `git tag` を打たない。GPU を使わない**(段階 C 以降は人間の承認が要る)
- **`is_indistinguishable` を全規則ペアに自動適用しない。**除外の追加は実験条件の変更(`CLAUDE.md` §8)
- **`§4.9.3` の #7 / #8 / #12 をいま書かない。**G7 の項目構成(§5.1)と多項項目の規約(§4.5.3)が
  コードに無いので、書くと**仕様ではなくテストのほうが原典になる**。承認待ち-11 の決着後
- **preflight の検査を「環境に無いから」で緩めない。**トークナイザが無いなら「未実行」で落とす

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

**`plans/PLAN-003-redesign.md` §11 が正本。**段階との対応は `STATE.md`「Phase 0 に必要な段階」段階 B。

| # | 事項 | いつ要る |
|---|---|---|
| **PLAN-002 §12-11(★新規)** | **`p2`/`p2d` 判別不能の除外を `K` の抽出母集団にも掛けるか。**掛ける(現在の実装)と ① 訓練データに `t ≡ 0 (mod 10)` の式が1件も現れず、`p2d` 条件のモデルは**自分の桁規則の「+0」の場合を一度も見ない** ② `carry` 密度が 20.0% → 22.3% に動く(`K_main` の `carry` 393 → 435)。掛けない案は「`K` には残し、**評価項目を `K` から引くときにだけ**落とす」 | **段階 C より前が安全。**段階 E の Go/No-Go #4b(`p2d` ペネトランス)の解釈に直結する |
| **PLAN-002 §12-10(★新規)** | PLAN-003 §6.4 順6 の層をタスク型ごとに分けるか。分けて**排他の**組を要求すると main 領域の `interp × t_unseen × carry` 候補 **95 組**では足りない | 項目生成の前 |
| **6** | T2 の5テンプレートの確定文面 | **段階 A の項目生成を塞いでいる** |
| **13** | `arb` のズレ表 `table[1]` の穴。案 (b) か (c) | ズレ表の確定時 |
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
  ADR-020 決定2 は `t3_comparison.py` 改修と同時に行う
- **`§4.7` の交換律ペアの再計算**(`coverage_seed` 確定後)
- **Phase 0 の定義のずれ**(`STATE.md` 段階 E の ⚠️): ADR-018 は「Phase 0 は FT を回さない」と
  定義したが、`04_EXPERIMENT_PLAN.md` Phase 0 の Go/No-Go #4 / #4b / #5 は FT を要する。
  **事前登録の凍結(段階 D)をパイロットの前に置くか後に置くかが変わる。人間が決めること**

**人間の目視確認を受けていないエージェントの判断(凍結前に人間が読むこと)**:
ADR-030 の R8 手続き全体(**解析計画に当たる**)/ ADR-027 前段 /
ADR-028 決定1 と Go/No-Go #4b / PLAN-003 §4.8 のセル構成 /
**PLAN-002 §4.2.1a の `T_hold` 構成手続きと §4.8 の「実装で確定した3点」**。
