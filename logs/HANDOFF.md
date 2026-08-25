# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-25 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が 228k / 閾値 140k を警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

**まず `STATE.md` の「Phase 0 に必要な段階」節(段階 A〜E)を読むこと。**
そこが Phase 0 全体の地図で、このセッションは**段階 A の最後の塊**にあたる。
これを終えると、段階 A に残るのは**項目生成だけ**になり、それは承認待ち-6 で止まっている。

## このセッションでやること(1つだけ)

**PLAN-003 §7.1 / §7.2 の D-3(英語統一)後始末をコードに通す。**
`g6_comparison.py` の改修と、パーサ側の日本語語彙の除去は**同じ軸なので分割しない**
(片方だけ英語化すると T3 の項目とパーサが食い違い、`parse_fail_rate` に化ける)。

上から順に。**各段でテストを通してからコミットする**(小さく頻繁に。`CLAUDE.md` §5)。

| 順 | 作業 | 正本 |
|---|---|---|
| 1 | **`code/eval/battery/g6_comparison.py` → `t3_comparison.py` に改名。**追随先は `code/eval/run.py:29,95,127,129,138,143,148` と `code/tests/test_battery_g6.py`(→ `test_t3_comparison.py`)。`code/data_gen/battery_items.py:32` の `SUPPORTED_GROUPS` も | PLAN-003 §7.1 |
| 2 | **改修③ `arb` の評価を `ans_in` に限定。**現状 `g6_comparison.py:89` の `lesion.apply(a, b)` は `arb` × 定義域外(`t ∉ [2,198]`)で **`KeyError`** で落ちる。`Lesion.is_defined`(ADR-020、実装済)でガードし、定義域外の項目は**その参照規則の評価から外す**(既定値で埋めない) | ADR-020、PLAN-003 §7.1 |
| 3 | **改修② テンプレートを英語に。**`configs/templates/smoke.yaml` の文面も含む | ADR-024 D-3 |
| 4 | **改修④ 裸書式(T1b)の `category` を追加。**T1b は「裸の式に対する Yes/No 判断」。極性2水準は既存の `category` と同じ構造 | ADR-026 |
| 5 | **改修① R8 掃引モード**(Phase 0 タスク8)。`build_items` の `is_discriminating` 強制を**掃引時だけ**緩める。現状は非判別オフセットで `ValueError` になり、θ 17 水準の曲線が引けない。**`test_battery_g6.py` に「掃引モードでは非判別項目が通る」を新規に固定する** | ADR-030、PLAN-003 §7.1 |
| 6 | **D-3 の後始末**: `code/eval/parsers/base.py` の `ANSWER_MARKERS` から日本語5語を外す / `code/eval/parsers/boolean.py` の `_YES_JA` / `_NO_JA` を外す(`_match_tokens` の `japanese` 引数ごと畳む)/ **`code/eval/parsers/japanese.py` と `code/tests/test_parsers_japanese.py` を捨てる** | PLAN-003 §7.1 / §7.2 |
| 7 | 追随: `code/tests/test_parsers_boolean.py` から日本語ケースを落とし**英語の負例を足す** / `code/tests/test_parsers_cot.py:16,55,60` の `parse_japanese` 依存を外す(`numeric` か `boolean` に差し替える) | PLAN-003 §7.2 |

**完了条件**: `pytest code/tests -q` が通り(現在 **340 passed**。`japanese` 系 22 件が減り
掃引モードと T1b の新規が加わる)、`python -m code.eval.run --config configs/smoke.yaml --dry-run`
が通り、`logs/CHANGELOG.md` に**減った件数と増えた件数を実測で**書いてあること。

**コンテキストが厳しくなったら順5 の手前で止めてよい。**順1〜4 で1コミット、
順5 で1コミット、順6〜7 で1コミットに割れる。**途中で切るなら skill `handoff` を実行する。**

## 直前セッションで確定したこと

- **実装順 4 が完了した**(commit `1c01c48`)。`infra/preflight.py` が **16 項目**になり、
  PLAN-002 §4.8.1 の検査5・6・7・8・9・10 と検査3拡張が入った。
  `code/tests/test_preflight_checks.py` **38 件**。`pytest code/tests -q` → **302 → 340 passed**
  (2026-08-25 実測、3.1 秒)
- **preflight の SKIP / FAIL 方針を確定した。**SKIP は「この実行には対象が存在しない」に限る
  (config なし / `lesion.condition: none`)。**宣言・依存・トークナイザの欠落は FAIL(未実行)。**
  `configs/smoke.yaml` で `infra/preflight.py --config` を走らせると **FAIL する。それが正しい**
- **config に3項目を新設した**(`configs/template.yaml`、いずれも `null` 始まり):
  `data.matched_manifests` / `eval.anchor_manifest` / `eval.cells`。
  **検査8 の `id` 要求は `eval.cells` から実行時に数える。リテラルの閾値は置かない**
- **`id` セル要求は 556 ではなく 520。**PLAN-001 §4.2.2・§13 と PLAN-002 §4.8.1 が
  PLAN-003 §4.7 の改訂に追随しておらず、2026-08-25 に訂正した(§5.1 の表と本文は 520 で正しかった)
- `pyproject.toml` の `pythonpath` に `infra` を追加した(テストが `import preflight` できるように)
- **実験結果の数値は依然として1つも無い。**`results/` は空。GPU 時間 0。事前登録の tag なし

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-003-redesign.md` **§7.1 / §7.2**(`sed -n '684,727p'`)。**ここが今回の正本**
- `code/eval/battery/g6_comparison.py`(`grep -n "^def "` で API 一覧)
- `code/eval/run.py` / `code/eval/parsers/{base,boolean,cot,japanese}.py`
- `code/tests/test_battery_g6.py` / `test_parsers_{boolean,cot,japanese}.py`
- `configs/templates/smoke.yaml`
- **全文 `cat` しない。**`grep -n` で節を特定して `sed -n 'X,Yp'`(`CLAUDE.md` §10.1)

## やってはいけないこと

- **`infra/preflight.py` の検査を緩めない。**「環境に無いから」で SKIP に変えない。
  検査6・8 が FAIL で止まるのは**仕様どおり**であって、直すべきバグではない
- **`code/eval/parsers/wordform.py` と `test_parsers_wordform.py` を消さない。**
  判定は「捨てる(**ファイルは残す**)」。評価バッテリから外すだけ(PLAN-003 §7.1)
- **T2 の5テンプレートの文面を書かない**(承認待ち-6)。**項目生成に着手しない**
- **`Documents/05_STATISTICS.md` §6 / §10 を書き換えない**(凍結直前の作業)
- **事前登録の `git tag` を打たない。GPU を使わない**
- **R8 の解析手続き(ADR-030 決定2〜6)をコードで解釈し直さない。**
  このセッションで触るのは `build_items` の**強制を緩めるフラグだけ**
- `--date` でコミット日付を偽装しない(`CLAUDE.md` §5)

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

正本は `plans/PLAN-003-redesign.md` §11。段階との対応は `STATE.md` 段階 B。

- **PLAN-002 §12-11**: `p2`/`p2d` 判別不能の除外を `K` の抽出母集団にも掛けるか。
  掛ける(現在の実装)と ① 訓練データに `t ≡ 0 (mod 10)` の式が1件も現れず、`p2d` 条件の
  モデルは自分の桁規則の「+0」を一度も見ない ② `carry` 密度 20.0% → 22.3%。
  → **段階 C より前に決めるのが安全**
- **PLAN-002 §12-10**: PLAN-003 §6.4 順6 の層をタスク型ごとに分けるか
- **#6 T2 の文面**(段階 A の項目生成を塞いでいる。**このセッションの後、段階 A で残るのはこれだけ**)
- #13 `arb` の `table[1]` / #15 `M*` と θ / #9 適格性フィルタ 0.70 /
  #16・#11 Feucht と G7 / #17 Nikankin / #10 W6

**エージェント側の宿題(次の PLANNER セッション向け)**:
`05_STATISTICS.md` §6 の再導出(df=6)/ `09_PAPER_PLAN.md` の追随 /
交換律ペアの再計算(`coverage_seed` 確定後)/
**項目生成のときに `code/data_gen/pool.py` の `build_manifest` へ `prompt_format` ブロックを足す**
(preflight 検査6 の照合対象がそこでつながる)/
**Phase 0 の定義のずれ(凍結をパイロットの前に置くか後か。人間が決める)**
