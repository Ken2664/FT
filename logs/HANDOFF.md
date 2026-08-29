# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-29 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: **1 PLAN 完了**(人間が `plans/PLAN-005` §5 で6項目を全採択 →
採択分を ADR / config に落とした。commit `54bfff3`)

---

まず `CLAUDE.md` §1 の開始手順を実行してください(`STATE.md` / `logs/CHANGELOG.md` /
`logs/DECISIONS.md` / `git log` / `runs/` / `git worktree list`)。**RunPod MCP は不要**。

## 直前セッションで終わったこと(ファイルに書き込み済み。commit `54bfff3`)

人間が `plans/PLAN-005` §5 の採否表で6項目すべてを採択した。エージェントは採択分を落とした
(`CLAUDE.md` §8 / ADR-039。決定・解釈はしていない)。**GPU 時間 0。`results/` は空。**

- **承認待ち C → 決着**: `model.max_new_tokens` に `[MATCHED]`。`logs/DECISIONS.md` ADR-042 の
  「2026-08-29 追記」。`configs/template.yaml` の `max_new_tokens: 256  # [MATCHED]`。
- **#21 → ADR-046 新設**:
  - `configs/templates/t1b.yaml`(昇格): `t1b_gt: "{a}+{b}>{threshold}?"` /
    `t1b_lt: "{a}+{b}<{threshold}?"`(答え書式の指示なし。`+`=U+002B / `>`=U+003E /
    `<`=U+003C / `?`=U+003F に固定)
  - `configs/templates/t3.yaml`(昇格): **案 A** =
    `Is the sum of {a} and {b} greater than / less than {threshold}? Answer Yes or No.`
    (`+` を使わない。案 B 却下)
  - `configs/templates/eval_main.yaml`(新規。runtime 正本): `comparison`(T1b+T3)+
    `word_problem`(T2)。**T1(bare_sum)も特異性対照(specificity)も入っていない。**
    `configs/template.yaml` の `data.eval_template_set: eval_main`(`[MATCHED]`)
  - 文面の正本は per-task ファイル。`eval_main.yaml` との sync を
    `code/tests/test_eval_main_template.py`(7件)が縛る
  - `t1b_draft.yaml` / `t3_draft.yaml` を削除。**ADR-042 決定10 を閉じた**
- **ADR-041 決定5 → 一部決着**: `logs/DECISIONS.md` ADR-041 の「2026-08-29 追記」。
  `configs/template.yaml` の `eval.magnitude_sweep.radii = [25,50,75,99,100,110,125,150,175,200,300,500,999]` /
  `n_items_per_radius: 200`。**抽出シード数 = 5**。**θ の値は含まない**(ADR-041 決定2・3)。
  `eval.magnitude_sweep.seed` は**未記入** —— `code/eval/sweep.py` はシード平均を取らず、
  5シードの具体値も未決。**両方 `plans/PLAN-006-sweep-multiseed.md`(新規)に切った**。
- `pytest code/tests -q` → **700 passed**(開始時 693)。
- 追随: `STATE.md` / `plans/PLAN-004`(§2 順2・順3、§3 順3・順4・順5、§5 #20・#21、§7)/
  `plans/PLAN-005`(§2/§3/§4 を採択の1行に畳んだ)/ `logs/CHANGELOG.md`。

## 次にやるべきこと(どれか1つを1セッションで)

1. **IMPLEMENTER: `plans/PLAN-006`**(`code/eval/sweep.py` のマルチシード化。GPU 時間 0)。
   `SweepPlan.seed: int` → `seeds: list[int]`、測定ループで `M` ごとにシード平均 + SD を
   `results/` に残す。**着手前に人間が §3 の案 A(基底整数派生)/ 案 B(明示リスト `[0,1,2,3,4]`)を選ぶ。**
   **合否基準は作らない**(ADR-041 は θ を人間の決定にしている)。順5 のブロッカー。
2. **IMPLEMENTER: PLAN-004 順4**(本実験の項目生成と評価プールの作り直し。`code/data_gen/`)。
   順0 / 1 / 2 の決定を反映。**`eval_template_set: eval_main` で T1b / T3 も進められる**。
   **`specificity` は文面未確定でプールを作れない**(下記)。**`extrap` セルは `M*` 未決で埋まらない**。
   **かつ並行ブランチ `claude/objective-mestorf-34f57d` の扱いを人間が決めていない**
   (`STATE.md`「並行ブランチ」。順4 は再生成の経路そのものを実装しているブランチと衝突しうる)。
3. **PLANNER**: **T1b が Go/No-Go #1(`parse_fail_rate < 0.02`)を割ったときの分岐が無い**
   (ADR-046 リスク欄 / ADR-042 決定5 (i) は決定7 が封じ、few-shot は決定5 (iii) が封じている)。
   案を出すか、人間に上げる。

## 人間の判断待ち(エージェントが勝手に決めない。`CLAUDE.md` §8)

- **`plans/PLAN-006` §3**: 5シードの与え方(案 A / 案 B)。
- **T1b の Go/No-Go #1 分岐**(上の 3)。
- **特異性対照(`specificity`)の裸書式の符号位置**(`-` / `*`)。
  PLAN-002 §4.1.1 の7規約が固定していない(`configs/templates/smoke.yaml` L45-49)。
  `eval_main.yaml` に入れていない。順4 で `specificity` プールを作るには要る。
- **θ の値**(ADR-041。順5 の掃引表を見てから)。

## GPU を使う次の段

**順5**(桁数掃引 → M*。要 **PLAN-006 完了** + θ 決定 + GPU 承認)。その実機で `pip freeze` を取り
**ADR-044**(lock の凍結)を履行する。段階 C の 100 項目確認(ADR-040 決定7)で
`compare_runs` の `parsed_consistency` を使う。

## やってはいけないこと

- **θ の値を提案・決定しない**(ADR-041 決定2・3)。
- 合否基準・しきい値を作らない(ADR-045 決定2 / ADR-041 の思想)。
- 事前登録した予測・解析計画を実験後に変更しない(`CLAUDE.md` §2)。
- 人間の承認なく GPU ジョブを起動しない / RunPod ポッドを放置しない。
- **`configs/templates/eval_main.yaml` と per-task ファイル(`t1b.yaml` / `t2.yaml` / `t3.yaml`)を
  片方だけ直さない**(`code/tests/test_eval_main_template.py` が drift を止める)。
