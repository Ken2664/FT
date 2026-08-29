# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-29 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: **1 PLAN 完了**(人間の判断待ち3件の案を `plans/PLAN-005` に起草した。決定はしていない)

---

まず `CLAUDE.md` §1 の開始手順を実行してください(`STATE.md` / `logs/CHANGELOG.md` /
`logs/DECISIONS.md` / `git log` / `runs/` / `git worktree list`)。**RunPod MCP は不要**。

## 直前セッションで終わったこと(ファイルに書き込み済み。commit `440786d`)

- **`plans/PLAN-005-phase0-pending-decisions.md` を新設。**承認待ち C / #21 / ADR-041 決定5 の
  **案**を、人間が採否を記入できる形(§5 の表)で置いた。**エージェントは案出しのみ**
  (`CLAUDE.md` §8 / ADR-039)。**`configs/template.yaml` にも `logs/DECISIONS.md` の ADR 本体にも
  何も書いていない。**コード変更なし。GPU 時間 0。`results/` は空。
  - **承認待ち C(§2)**: `max_new_tokens` に **`[MATCHED]` を付ける案**。
  - **#21(§3)**: `configs/templates/t1b_draft.yaml`(`{a}+{b}>{threshold}?` 指示文なし。ADR-042 決定7)/
    `t3_draft.yaml`(**案 A 推奨** = `Is the sum of {a} and {b} greater than {threshold}? Answer Yes or No.`、
    **案 B** = `Is {a} + {b} greater than …` で `+` を残す)。手続きは ADR-032 と同じ。
  - **ADR-041 決定5(§4)**: `radii: [25,50,75,99,100,110,125,150,175,200,300,500,999]` /
    `n_items_per_radius: 200` / 抽出シード数 5。**θ の値は提案していない**(ADR-041 決定2・3 が
    θ を掃引後の人間の決定にしている)。**抽出シード数 > 1 は `code/eval/sweep.py` の実装変更が要る**
    (`SweepPlan.seed: int` が単数でシード平均を取らない)。
- 追随: `STATE.md`(冒頭★・「いま何を」・「引き継ぎ」・「承認待ち」)/ `plans/PLAN-004`(§5 #21・§3 順3・§7)/ `logs/CHANGELOG.md`。

## 次にやるべきこと(どれか1つを1セッションで)

1. **人間が `plans/PLAN-005` §5 の表に採否を記入したら、エージェントが採択分を落とす**(GPU 時間 0):
   - 承認待ち C 採択 → `logs/DECISIONS.md` ADR-042 に追記(提案 PLANNER / 採択 人間)+
     `configs/template.yaml:51` の `max_new_tokens: 256` に `# [MATCHED]` + L43-50 コメントを確定文言に
   - #21 採択 → `configs/templates/t1b_draft.yaml` → `t1b.yaml` / `t3_draft.yaml` → `t3.yaml` に昇格 +
     文面を凍結する ADR(提案者 / 採択者を分ける)+ **ADR-042 決定10 を閉じる** +
     `data.eval_template_set` 用の統合テンプレート集合ファイルを作る(T2 + T1b + T3。**T1 は入れない**)
   - ADR-041 決定5 採択 → ADR-041 に追記 + `configs/template.yaml` の `eval.magnitude_sweep.*`(null 3件)。
     抽出シード数 > 1 なら `code/eval/sweep.py` 改修タスクを1本切る(`seed: int` → `seeds: list[int]`、
     シード平均、`results/` にシード別値 + SD)
2. **IMPLEMENTER: PLAN-004 順4**(本実験の項目生成と評価プールの作り直し。`code/data_gen/`)。
   順0 / 1 / 2 の決定を反映。**#21 が未採択なら `eval_template_set` は埋まらない** —— T1 / T2 のプールまで。
   **かつ並行ブランチ `claude/objective-mestorf-34f57d` の扱いを人間が決めていない**
   (`STATE.md`「並行ブランチ」。順4 は再生成の経路そのものを実装しているブランチと衝突しうる)。
3. **PLANNER**: `plans/PLAN-005` に挙げた「#21 を決めても残る未決」——
   **T1b が Go/No-Go #1(`parse_fail_rate < 0.02`)を割ったときの分岐が無い**
   (ADR-042 決定5 (i) は決定7 が封じ、few-shot は決定5 (iii) が封じている)。案を出すか、人間に上げる。

## GPU を使う次の段

**順5**(桁数掃引 → M*。要 θ 決定 + GPU 承認)。その実機で `pip freeze` を取り **ADR-044**(lock の凍結)を履行する。
段階 C の 100 項目確認(ADR-040 決定7)で `compare_runs` の `parsed_consistency` を使う。

## やってはいけないこと

- **`plans/PLAN-005` の案を「決定」として `configs/` や ADR 本体に書かない。**人間の採否記入を待つ(`CLAUDE.md` §8)。
- **θ の値を提案・決定しない**(ADR-041 決定2・3。掃引表を見てから人間が決める)。
- 合否基準・しきい値を作らない(ADR-045 決定2 / ADR-041 の思想)。
- 事前登録した予測・解析計画を実験後に変更しない(`CLAUDE.md` §2)。
- 人間の承認なく GPU ジョブを起動しない / RunPod ポッドを放置しない。
