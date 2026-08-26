# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-26 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約103k / 閾値100k を警告)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

## このセッションでやること(1つだけ)

**Phase 0 タスク2の残り = 評価項目の生成器を書く。**段階 A に残っているのはこれだけです。

完了条件:

1. **`code/data_gen/pool.py` の `build_manifest` に `prompt_format` ブロックを足す。**
   `infra/preflight.py` の検査6 が `format_hash` を**再計算して照合する**ので、
   `PLAN-002 §4.8` と同形のフィールドを出すこと(`infra/preflight.py:623` 付近を読む)
2. **T1(裸の計算式)と T2(文章題)の項目生成を実装する。**数値出力なので
   `t3_comparison.py` とは別モジュールになる(`battery_items.py:16` のコメント参照)
3. **`battery_items.SUPPORTED_GROUPS` に新しい群名を足す。**T2 の群名は
   **`word_problem`**(ADR-032 決定5)
4. **特異性対照**の項目生成(`plans/PLAN-003-redesign.md` §4.5 / §4.8)
5. `code/tests/` にテストを追加し `pytest code/tests -q` を通す(現在 **341 passed**)
6. `logs/CHANGELOG.md` に追記 → commit

## 直前セッションで確定したこと

- **ADR-032(2026-08-26 採択)。承認待ち-6 が決着した。**T2 の5テンプレート文面が確定。
  正本は **`configs/templates/t2.yaml`** と `plans/PLAN-003-redesign.md` §4.3
- **T2 の生成器は被演算子 1 を除外する**(ADR-032 決定4。`1 apples` が非文になるため)。
  **除外したことを manifest に記録すること**
- T2 の category キーは `t2_count` / `t2_people` / `t2_distance` / `t2_money` / `t2_time`、
  群名は `word_problem`
- **段階 A の他の作業はすべて完了している**(実装順 0 / 1 / 1b / 1c / 2 / 3 / 4、
  `t3_comparison.py` 改修、D-3 後始末)。コードは 2026-08-26 に1行も変えていない

## 触ってよいファイル / 読むべき範囲

**全文 `cat` しないこと。**`grep -n` で節を特定し `sed -n 'X,Yp'` で読む(`CLAUDE.md` §10.1)。

| パス | 何を見るか |
|---|---|
| `plans/PLAN-003-redesign.md` §4.2〜§4.5、§4.8 | **項目構成の正本。**T1/T1b/T2/T3/特異性対照の n・層・項目数・セル構成 |
| `plans/PLAN-002-ft-data.md` §4.8 | manifest の schema。`prompt_format` の形 |
| `code/data_gen/pool.py` | `Pair` / `carry_label` / `label_coverage` / `build_manifest` |
| `code/data_gen/battery_items.py` | `Item` dataclass、`SUPPORTED_GROUPS`(現在 `("comparison",)`) |
| `code/eval/battery/t3_comparison.py` | **実装済みの手本。**`render_prompt` はテンプレートを config から受ける |
| `infra/preflight.py:482-660` | 検査6・8 が manifest に何を要求するか |
| `configs/templates/smoke.yaml` / `t2.yaml` | テンプレート集合のファイル形式 |

## やってはいけないこと

- **`configs/templates/t2.yaml` を `data.eval_template_set` に配線しない。**
  T1b / T3 の**本番文面は未確定**なので、テンプレート集合としてまだ完成していない
- **T1b / T3 の本番文面を自分で書かない。**文面は実験条件であり `CLAUDE.md` §8 の対象。
  `smoke.yaml` の文面は**配線確認専用**で本番用ではない
- **`numeric` パーサの「数が2個以上なら parse_fail」を緩めない。**
  緩めると誤答が correct / rule に化ける(PLAN-001 §5.4 の 4)
- **4値分解(correct / rule / other_error / parse_fail)の合計を 1.0 から外さない**(`CLAUDE.md` §6)
- `data/raw/` を書き換えない
- **実装で見つけた「文書の不整合」を独断で直さない。**PLANNER に投げるか、
  直すなら打ち消し線 + 理由 + 日付で残す(`CLAUDE.md` §2)

## 実装で必ず踏む穴(先に知っておくこと)

- **`code/eval/run.py` には `parse_boolean_response` しか無い。**T1 / T2 の
  数値経路(`cot` → `numeric`)は**未配線**である。生成器だけ書いても評価は回らない。
  配線まで含めるとこのセッションに収まらない可能性がある。
  **収まらないと判断したら生成器で切り、次に回すこと**
- `PLAN-002 §4.9.3` の **#7 / #8 / #12 は未実装のまま**でよい。
  G7 の項目構成が承認待ち-11 の決着待ちであるため

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8。**独断で決めない**)

- **#18(新規)** T1 にも答え書式の指示を足すか。ADR-032 決定3 により **T2 だけが
  指示文を持つ**ので、タスク型の軸に「指示の有無」が乗る。ADR-025 が却下したのと同型の交絡
- **#19(新規)** 被演算子 1 の除外を全タスク型に広げるか。決定4 は T2 限定なので、
  **T2 だけ被演算子分布が他タスクと厳密には一致しない**
- **#9** 適格性フィルタの閾値 `0.70`。事前登録に入る
- **#16 / #11** Feucht et al. の位置づけ / G7 の扱い(一体で決める)
- **#13** `arb` のズレ表 `table[1]` の穴。案 (b) か (c)
- **PLAN-002 §12-11** `p2d` 判別不能の除外を `K` の抽出母集団に掛けるか
- 一覧は `plans/PLAN-003-redesign.md` §11 と `STATE.md` の「段階 B」表

## 状態(2026-08-26 時点)

- `pytest code/tests -q` → **341 passed**
- `results/` は空。**実験結果の数値は1つも無い。**GPU 時間 0。RunPod 未使用
- **事前登録は未凍結**(`git tag` なし)
- 直近 commit: `555dd5c` docs(adr): ADR-032 を採択
