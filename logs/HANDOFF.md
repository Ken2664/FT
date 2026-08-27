# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-27 / 直前セッションの役割: PLANNER 兼 IMPLEMENTER
直前セッションが終了した理由: **順0 が完了したため**(`CLAUDE.md` §10.2「1セッション = 1 PLAN」)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。

## このセッションでやること(1つだけ)

**`plans/PLAN-004-phase0-route.md` の順1 を完了にする。**
= **`code/eval/run.py` の本実行(モデルの読み込みと生成)+ 桁数掃引の入口**。**GPU は要らない。**

**仕様は `plans/PLAN-004-phase0-route.md` §4 が正本**(§4.1 現状 / §4.2 追加するモジュール /
§4.3 制約 / §4.4 やらないこと)。**全文 `cat` せず `sed -n '156,206p'` で §4 だけ読むこと。**

完了条件(PLAN-004 §3 順1 の5つ):

1. `python -m code.eval.run --config <cfg>`(`--dry-run` なし)が**実際にモデルを呼んで**
   4値分解を出し、`runs/<id>/` に成果物を書く
2. `python -m code.eval.sweep --config <cfg>` が `M` を掃いて **`M` → `correct_rate` の対応表**を出す
   (PLAN-001 §4.1.1 の手続き)
3. **GPU の無い環境でテストが通る**(生成関数を差し替え可能にする)
4. `pytest code/tests -q` が緑(**現在 427 passed**)
5. `infra/RUNPOD.md` §4 の未実装コマンドに注記が付き、`code.eval.run` の引数が実装と一致する
   (**実際の CLI は `--config`。RUNPOD.md は `--run-dir` と書いている**)

**外してはいけない制約(PLAN-004 §4.3)**:

- **生成関数は1箇所に集め、`run.py` と `sweep.py` が共有する。**2箇所で別々に生成すると、
  掃引と本実行で生成設定が食い違っても誰も気づかない
- **既定値を作らない。**`model.name` / `dtype` / `max_new_tokens` / デコード設定が `null` のときは
  **例外で止める**(skill `code-style` §5)。**これらは未決 #20 であり、順2 で人間が決める。**
  「実行できない」のが**いま正しい状態**である
- モデルを実際に読むテストは書かない

---

## 直前セッションで完了したこと(順0 = 完了)

**ADR-034 / ADR-035 / ADR-036 を採択し、PLAN-002 §12-11 をコードに反映した。**

| ADR | 内容 |
|---|---|
| **ADR-034** | `p2`/`p2d` 判別不能の除外を **`K` の抽出母集団には掛けない**。掛ける先は**評価項目**。**真値との偶然一致の除外は `K` に残す** |
| **ADR-035** | T1 は素の書式のまま + **「指示付き T1」を副次セル**(`id` × carry/nocarry・n=40 = 80 項目。探索的)/ 被演算子 1 の除外は**評価項目のみ**全タスク型に広げる |
| **ADR-036** | **G7 を落とす** / Feucht et al. (2026) は **Intro の対立軸としてのみ引用** |

- コード: `ft_data.generate` 手順2b から `indistinguishable_rule_pairs` を外した。
  manifest に `exclusions.indistinguishable_rule_pairs_applied_to: "eval_items_only"` を新設、
  `schema_version` **1 → 2**
- テスト: **本番経路 `generate` を通す設計事実テストを追加**(母集団 **4,309** /
  `K_main` の carry **393** / `t ≡ 0 (mod 10)` が訓練被覆に残る)。**423 → 427 passed**
- preflight: `python infra/preflight.py --config configs/smoke.yaml` の
  **`data_checks` 6項目すべて PASS**。残る FAIL は `token boundaries`
  (`model.name` / `model.revision` が null)で、**これは未決 #20 / #21 である**

**★ADR-035 の2件(副次セル・被演算子 1 の評価側除外)は実装していない。順4 の仕事である。**
このセッションで手を付けないこと。

---

## 触ってよいファイル / 読むべき範囲

**全文 `cat` しないこと。**`grep -n` で節を特定してから `sed -n 'X,Yp'`。

| ファイル | 範囲 | 何をするか |
|---|---|---|
| `plans/PLAN-004-phase0-route.md` | **§4(156-206 行)** | **仕様。最初に読む** |
| `code/eval/run.py` | `main` 周辺(396 行付近) | `NotImplementedError` を外し本実行経路を通す |
| `code/eval/model.py` | 新規 | モデル/トークナイザの読み込み。**`null` は例外** |
| `code/eval/generate.py` | 新規 | プロンプト列 → 応答列。**差し替え可能に** |
| `code/eval/sweep.py` | 新規 | `M` を掃く CLI |
| `code/eval/battery/magnitude_sweep.py` | 新規 | 上限 `M` の入れ子の域から加算項目を作る(PLAN-001 §4.1.1 手続き1) |
| `infra/RUNPOD.md` | §4 | 未実装コマンドへの注記 + `--config` への訂正 |
| `configs/template.yaml` | 28-33 | **`null` のまま。埋めない**(#20 は人間の決定) |

**モジュール構成は提案である**(PLAN-004 §4.2)。1関数1責務(skill `code-style`)を満たすなら
実装者が変えてよい。ただし「生成関数を1箇所に集める」ことは変えない。

---

## やってはいけないこと

- **生成設定の既定値を作らない**(#20。`temperature` / `max_new_tokens` / few-shot 数)。
  文書に散在する「温度0」「0-shot」を**確定文言として書かない**
- **T1b / T3 の評価テンプレートを書かない**(#21。人間の決定)
- **ADR-035 の副次セル・被演算子 1 の除外を実装しない**(順4)
- **`data/raw/` を書き換えない**(`CLAUDE.md` §2)
- **モデルを実際に pull しない**(GPU 承認は順5 まで無い。`CLAUDE.md` §2)
- **`results/` に数値を置かない。**まだ実験を1つも回していない

---

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

**順1 は人間の入力を待たずに進められる。**次に人間の入力が要るのは以下。
`STATE.md` 段階 B と `plans/PLAN-004-phase0-route.md` §5 が正本。

| # | 事項 | いつ要る |
|---|---|---|
| **20** | 生成設定(`model.dtype` / `max_new_tokens` / デコード / few-shot 数) | **段階 C の前**(順2) |
| **21** | 本番の評価テンプレート集合(T1b / T3 の確定文面) | **段階 C の前**(順2) |
| **9** | 適格性フィルタの閾値 0.70 | **実測より前**(順3) |
| **15** | 外挿域の上限 `M*` の**決定規則**(値ではなく規則を先に凍結) | **実測より前**(順3) |
| **22** | LoRA アダプタを `runs/<id>/` に残すか | 順8 まで |
| **17** | Nikankin et al. (2025) の原典確認(SCOUT) | 凍結。**ADR-036 で必須化・優先「高」** |
| **10** | W6 の分岐 | Go/No-Go 実施時 |
| — | 検出力分析の再導出(df = 6) | 凍結 |

**エージェントが独断で決めた点(人間が一度見ること)**:
manifest の欄名 `indistinguishable_rule_pairs_applied_to` と `schema_version` 1 → 2 /
ADR-035 の副次セルの規模(80 項目)は**未承認**(人間が決めたのは「現状維持 + 副次セル」まで)。

**GPU は1秒も使っていない。`results/` は空。事前登録の tag は無い。**
