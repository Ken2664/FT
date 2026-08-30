# PLAN-006: 桁数掃引をマルチシード化する(順5 のブロッカー)

> **★ 2026-08-30 完了。**人間が §3 = **案 B(`seeds = [0, 1, 2, 3, 4]`)**を採択(提案 PLANNER /
> 採択 人間)。同日 IMPLEMENTER が §4 を実装した(`pytest` 711 passed。GPU 時間 0)。
> 正本は **ADR-041 の 2026-08-30 追記**。§6 の完了条件はすべて満たした(下にチェック済み)。
> **順5 の「実装」ブロッカーは消えた** —— 残るは θ の値(人間)と GPU 承認。

- 作成日: 2026-08-29
- 担当: IMPLEMENTER(実装。GPU 時間 0)+ 人間(シード値の決定)
- 由来: ADR-041 決定5(2026-08-29 採択)—— 抽出シード数 = 5。`code/eval/sweep.py` は
  現状シード平均を取らないため、順5(C-1: 桁数掃引)の前に実装変更が要る。
- 前提: ADR-041 決定3 規則3(「水準ごとの項目数と抽出シード数を固定し、`correct_rate` は
  シード平均で採る」)/ 決定5(格子と項目数は `configs/template.yaml` に記入済。
  `eval.magnitude_sweep.seed` は未記入)

---

## 1. この PLAN が答える問い

**「桁数掃引が `M` ごとに5シードの `correct_rate` を平均し、シード間 SD を `results/` に
残せるようにするには、何をどの順で変えるか。」**

---

## 2. 現状(2026-08-29 に確認)

| 場所 | いま |
|---|---|
| `configs/template.yaml` `eval.magnitude_sweep.seed` | 単一 int を想定。**未記入(null)** |
| `code/eval/battery/magnitude_sweep.py` `SweepPlan` | `radii: list[int]` / `n_items_per_radius: int` / `seed: int`(単数) |
| `code/eval/battery/magnitude_sweep.py` `load_sweep_plan` | `seed=int(require(config, f"{SWEEP_SECTION}.seed"))` |
| `code/eval/battery/magnitude_sweep.py` `build_items` | `seed: int` を受け、`random.Random(f"{seed}:{radius}")` で `M` を混ぜる |
| `code/eval/sweep.py` | 測定ループが `M` を1周するだけ。`plan.seed` を1つ渡す(`:148-149` / `:406-410`)。**シード平均を取らない** |
| `code/eval/sweep.py` `report_lines` | `seed={payload['sweep']['seed']}` を1行出す(`:308-310`) |

`correct_rate` が `M` について単調に落ちる保証は無い(ADR-041 決定3 規則2)。
`M*` は「`M` を小さい順に見て初めて `θ` を割った水準の1つ下」であり、`M` ごとの
`correct_rate` は**シード平均**で採る(規則3・規則4)。

---

## 3. 人間の決定待ち(実装より先)

**5シードの具体値をどう与えるか。**PLAN-005 §4.5 が2案を挙げている:

| 案 | 形 | 備考 |
|---|---|---|
| A | 基底整数を1つ決め(例 `20260901`)、5シードを `f"{base}:{k}"`(k = 0..4)で派生 | `build_items` が既に `f"{seed}:{radius}"` で混ぜるので、派生の階層が1つ増える |
| B | 明示リスト `[0, 1, 2, 3, 4]` | 最も単純。他の config 欄(`seeds` の例)と字面が揃う |

**いずれも実験シード `seeds` とは独立で `[MATCHED]`(全条件・全実験シードで固定)。**
θ の値はこの PLAN でも決めない(ADR-041 決定2・3。掃引表を見てから人間が決める)。

---

## 4. 実装単位(人間が案 A / 案 B を決めた後)

1. **config 欄**: `eval.magnitude_sweep.seed`(単数)→ `seeds`(リスト)に改名。
   `configs/template.yaml` と `configs/smoke.yaml`(smoke 用の小さい値)の両方。
   旧 `seed` を残さない(既定値・後方互換の暗黙フォールバックを作らない。skill `code-style` §1)。
2. **`SweepPlan`**: `seed: int` → `seeds: list[int]`。`payload()` も追随。
   バリデーション: 空でない / 重複なし(`radii` の検査と同じ様式)。
3. **`load_sweep_plan`**: リストを読む。
4. **`code/eval/sweep.py` の測定ループ**: `M` ごとにシードを回し、
   - シード別の `correct_rate` を全部残す
   - `M` の代表値 = シード平均
   - シード間 SD を併記
   `results/` に出す表は `M` × {シード別 `correct_rate`, 平均, SD} を持つ。
   `report_lines` の `seed=` 行を `seeds=` に。
5. **`build_items` の呼び出し**: シードごとに `build_items(..., seed=s, ...)` を呼ぶ。
   `build_items` 自体のシグネチャ(`seed: int`)は変えない —— 1シードぶんの抽出器のままにし、
   ループは `sweep.py` 側に置く(1関数1責務。skill `code-style` §2)。
6. **テスト**:
   - `SweepPlan` のバリデーション(空リスト / 重複で `ConfigError`)
   - 同じ `seeds` で2回回すと同じ表(決定的)
   - シードを1つ変えると `M` ごとの標本が変わる
   - 平均と SD が「シード別 `correct_rate` の記述統計」と一致する
   - `results/` の表に SD 列がある
   - **合否基準は作らない**(ADR-041 は θ を人間の決定にしている。ADR-045 と同じ思想)
7. **文書追随**:
   - `configs/template.yaml` `eval.magnitude_sweep.seeds` にコメントと値(人間が決めた形)
   - ADR-041 の 2026-08-29 追記に「→ PLAN-006 で実装完了(commit)」の1行
   - `plans/PLAN-004-phase0-route.md` 順5 の完了条件に「掃引表は `M` ごとにシード平均 + SD」

---

## 5. やってはいけないこと

- **θ の値を決める**(ADR-041 決定2・3)
- **`correct_rate ≥ θ` を判定するコードを書く**(`M*` の決定規則は ADR-041 決定3 が正本。
  掃引が出すのは表だけ)
- 単数 `seed` のフォールバックを残す(`configs/template.yaml` の `seed: null` は
  この PLAN の完了時に `seeds:` へ置き換わって消える)
- GPU ジョブを起動する(この PLAN は GPU 時間 0。順5 が GPU 段)

---

## 6. 完了条件

- [x] 人間が §3 の案 A / 案 B を決めた —— **案 B(`[0,1,2,3,4]`)。2026-08-30**
- [x] `eval.magnitude_sweep.seeds` が config の項目になり、単数 `seed` はコードから消えた
      (`configs/template.yaml` = `[0,1,2,3,4]` / `configs/smoke.yaml` = `[20260827, 20260828]`。
      `SweepPlan.seed` / `load_sweep_plan` の単数読みは削除。`sweep_seeds` を追加)
- [x] `code/eval/sweep.py` が `M` ごとにシード平均 + SD を `results/` に出す
      (`by_radius[*].seed_sd` / `by_seed[*]` / `log.txt` の `±sd` 列。4値すべて)
- [x] `pytest code/tests -q` が通る(新規テスト含む)—— **711 passed**(700 → +11)
- [x] ADR-041 追記(2026-08-30)を書いた
- [x] PLAN-004 順5 を追随した(§3 の順5 の完了条件に「掃引表は `M` ごとにシード平均 + SD」)
- [x] **順5 が回せる状態になった** —— 実装ブロッカーは消えた。残るは θ の値(人間)と GPU 承認

### 実装の細部(ADR-041 2026-08-30 追記が正本。ここは補足)

- `sweep_one(M)` は `plan.seeds` を回して `RadiusResult(per_seed=[SeedResult, ...])` を返す。
  1シードぶんの測定は新設した `measure_seed(M, seed)`(旧 `sweep_one` の本体)。`build_items` の
  シグネチャ(`seed: int`)は不変 —— ループは `sweep.py` 側(PLAN-006 §4.5 / 1関数1責務)。
- シード間 SD = 標本 SD(`statistics.stdev`、ddof=1)。**シードが1本なら 0.0**(標本サイズ 1 で
  分散が未定義。既定値ではなく算術上の事実。`_seed_sd`)。本実験は5シードなのでこの分岐は smoke のみ。
- `correct_rate_by_radius` / `correct_rate_table` はシード平均を返す(M* を決めるのは人間。ADR-041)。
- `configs/smoke1b*.yaml` は**変えていない**(順1b は掃引を回していない。完了済み実行設定に触れない。
  CLAUDE.md §2。それらで `sweep.py` を回すと `seeds` 欠落で正しく止まる)。
