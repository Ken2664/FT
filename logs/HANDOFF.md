# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-29 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: **1 PLAN 完了**（`logs/HANDOFF.md` 前版の「次にやるべきこと 3」=
T1b の Go/No-Go #1 分岐案を `plans/PLAN-007` に起草した。commit `561058b` / sha 補記 `cc9be49`）

---

まず `CLAUDE.md` §1 の開始手順を実行してください（`STATE.md` / `logs/CHANGELOG.md` /
`logs/DECISIONS.md` / `git log` / `runs/` / `git worktree list`）。**RunPod MCP は不要**。

## 直前セッションで終わったこと（ファイルに書き込み済み。commit `561058b`）

`plans/PLAN-007-t1b-gonogo-branch.md` を新設した（`CLAUDE.md` §8 / ADR-039。**案出しのみ。
決定・確定・解釈はしていない**）。**GPU 時間 0。`results/` は空。コード変更なし（`pytest` 未実行）。**

- **T1b が Go/No-Go #1（`parse_fail_rate < 0.02`）を割ったときの分岐が空白**だった問題に対し、
  標準の §6.5a ラダーが T1b で使えない理由を整理し、3案を人間が採否を記入できる形で提示した:
  - **案 A**: 二値出力群（T1b + T3）を**強制選択採点**（Yes/No のロジット比較・1 forward pass）に
    切り替える。プロンプト不変 → §3.1 の 2×2 保存。`parse_fail` 構造上 0。
    **設計文書（PLAN-003 §4.5・`code/eval/battery/t3_comparison.py:10` docstring・ADR-042 決定7 根拠）は
    元々「強制選択1 forward pass」と書いており、現状の自由生成 + `code/eval/parsers/boolean.py`
    パース実装のほうが逸脱**。
  - **案 B**: 高い許容線 + 全 `parse_fail` 手監査（**却下推奨**。恣意的しきい値。ADR-041 / 045 の思想に反する）。
  - **案 C**: T1b を主軸から外す（交互作用 df 6 → 4。§6.5a 第3段の T1b 版）。
  - **推奨 = ラダー（案 A → 案 C）**。分岐の構造は今 ADR 化、トリガーの値は実測が出す（ADR-041 決定5 と同じ切り分け）。
- **併せて確定を要する点**（PLAN-007 §2.3・§3.1）: Go/No-Go #1 の対象範囲（§6.5 表 #1 は字面上 T1b / T3 を
  含まない）/ 強制選択採点で二値群の4値分解が `correct + rule = 1` に潰れる帰結（`CLAUDE.md` §6 との整合）/
  モデル崩壊の検出が数値タスク側の #5・#2 と二値側の #3 に移譲される点。
- 追随: `STATE.md`（冒頭★★★★★★★★ / 「いま何をしているか」 / 「人間の承認・判断を待っている事項」5 /
  末尾の引き継ぎブロック）/ `logs/CHANGELOG.md`。**`configs/` にも ADR 本体にも `plans/PLAN-003` にも
  何も入れていない。**

## 次にやるべきこと（どれか1つを1セッションで）

1. **PLANNER（人間の回答後）**: 人間が `plans/PLAN-007` §5 の採否表を記入したら、採択分を
   ADR（**ADR-047 想定**。提案者 PLANNER / 採択者 人間 を分ける）と `plans/PLAN-003`（§4.5 引用ブロック /
   §6.5 表 #1 / §6.5a）に落とす。ADR-046 リスク欄 /「人間の承認・判断を待っている事項」5 を閉じる。
   **案 A / ラダー採択なら、PLAN-007 §4 の強制選択採点の実装を IMPLEMENTER タスク（GPU 時間 0）に切る。**
2. **IMPLEMENTER: `plans/PLAN-006`**（`code/eval/sweep.py` のマルチシード化。GPU 時間 0）。
   **着手前に人間が §3 の案 A（基底整数派生）/ 案 B（明示リスト `[0,1,2,3,4]`）を選ぶ。** 順5 のブロッカー。
3. **IMPLEMENTER: PLAN-004 順4**（本実験の項目生成と評価プールの作り直し。`code/data_gen/`）。
   **`eval_template_set: eval_main` で T1 / T2 / T1b / T3 は進められる**。
   **`specificity` は文面未確定でプールを作れない**（下記）。**`extrap` セルは `M*` 未決で埋まらない**（順5 の後）。
   **かつ並行ブランチ `claude/objective-mestorf-34f57d` の扱いを人間が決めていない**
   （`STATE.md`「並行ブランチ」。順4 は再生成の経路そのものを実装しているブランチと衝突しうる）。

## 人間の判断待ち（エージェントが勝手に決めない。`CLAUDE.md` §8）

- **`plans/PLAN-007` §5 の採否表**（T1b の Go/No-Go #1 分岐。6行。推奨 = ラダー A→C）。
- **`plans/PLAN-006` §3**: 掃引の5シードの与え方（案 A 基底整数派生 / 案 B 明示リスト `[0,1,2,3,4]`）。
- **並行ブランチ `claude/objective-mestorf-34f57d` の扱い**（`STATE.md`「並行ブランチ」§。
  (a) main の ADR-034 実装で足りるので破棄 / (b) `regenerate.py` を移植する順を切る。順4 の前に要る）。
- **特異性対照（`specificity`）の裸書式の符号位置**（`-` / `*` のコードポイント）。
  PLAN-002 §4.1.1 の7規約が固定していない（`configs/templates/smoke.yaml` L45-49）。
  `eval_main.yaml` に入れていない。順4 で `specificity` プールを作るには要る。
- **θ の値**（ADR-041。順5 の掃引表を見てから）。

## GPU を使う次の段

**順5**（桁数掃引 → M*。要 **PLAN-006 完了** + θ 決定 + GPU 承認）。その実機で `pip freeze` を取り
**ADR-044**（lock の凍結）を履行する。段階 C の 100 項目確認（ADR-040 決定7）で
`compare_runs` の `parsed_consistency` を使う。

## やってはいけないこと

- **θ の値を提案・決定しない**（ADR-041 決定2・3）。
- 合否基準・しきい値を作らない（ADR-045 決定2 / ADR-041 の思想）。**PLAN-007 §4 の実装をするなら、
  強制選択採点器も「4値を出すだけ」で Go/No-Go の判定コードは書かない**（PLAN-007 §4-7）。
- 事前登録した予測・解析計画を実験後に変更しない（`CLAUDE.md` §2）。
- 人間の承認なく GPU ジョブを起動しない / RunPod ポッドを放置しない。
- **`plans/PLAN-007` の案を「決定」として `configs/` や ADR 本体に書かない**（採択されるまで案は PLAN-007 のみ）。
- **`configs/templates/eval_main.yaml` と per-task ファイル（`t1b.yaml` / `t2.yaml` / `t3.yaml`）を
  片方だけ直さない**（`code/tests/test_eval_main_template.py` が drift を止める）。
