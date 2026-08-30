# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-30 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: **context-guard(179k、閾値 140k)**。PLAN-007 を起草し、
続けて人間が4件を決定した。**その4件をまだ1件もファイルに反映していない。**

---

あなたは PLANNER 兼 IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod は不要。GPU も使いません。**

## このセッションでやること(1つ) —— 人間の4決定をすべてファイルに反映する

直前セッションで人間が会話の中で4件を決めた(提案 PLANNER / 採択 人間。ADR-039 決定3)。
`STATE.md` 冒頭の★★★★★★★★★ブロックの表に逐語がある。**それを ADR / config / plan / コードに落とす。**
下のチェックリストは1セッションに収まる分量です。

### 決定1: PLAN-007 §5 = **案 A 採用**(T1b + T3 を強制選択採点に切替。案 C・案 B は不採用)

- [ ] **新 ADR-047 を `logs/DECISIONS.md` に起こす**(提案 PLANNER / 採択 人間)。内容:
  - 二値出力群(`comparison` = T1b + T3)を**強制選択採点**(Yes/No のロジット比較・1 forward pass)にする。
    **プロンプトは1文字も変えない**(ADR-046 で凍結した文面のまま)。§3.1 の 2×2 を保存するため。
  - **帰結(PLAN-007 §2.3・§3.1 に明記済。ADR-047 に取り込む)**:
    二値群の4値分解が `correct + rule = 1` に潰れる(`parse_fail`・`other_error` が構造上 0。
    `CLAUDE.md` §6 は4値報告を求めるが2つが 0 になるのは許容 —— Limitations に書く) /
    Go/No-Go #1(`parse_fail_rate < 0.02`)は T1b / T3 について構造上満たされる(§6.5 表 #1 の
    「対象は T1 / T2 / specificity」という字面と T1b/T3 の食い違いは、強制選択にすることで解消) /
    **モデル崩壊の検出が数値タスク側の Go/No-Go #5・#2 と二値側の #3 に移譲される**(脅威として記録)。
  - **案 C(T1b を主軸から外す)は不採用なので、「強制選択にしてもなお T1b × id が
    常答戦略ベースラインを超えられない」場合の明示的分岐は無い。** その場合は Go/No-Go #2
    (§6.3 の適格性フィルタでセルが落ちる)/ #3(極性の均衡を組み直す)の標準応答に落ちる。
    **ADR-047 でこれを明記する。必要なら人間に「案 C を backstop として残すか」を1度だけ問うてよい**
    (これは新しい判断事項なので §8 に該当)。
- [ ] **PLAN-007 §4 の実装を IMPLEMENTER タスクとして実行**(下の「実装2」)。
- [ ] **`plans/PLAN-003-redesign.md` を追随**: §4.5 引用ブロック(旧「人間に上げて止まる」を打ち消し線で残し、
  案 A の確定文言に差し替え)/ §6.5 表 #1 の対象範囲 / §6.5a に T1b の枝。
- [ ] **`Documents/04_EXPERIMENT_PLAN.md` の Go/No-Go 節**と **`Documents/06_THREATS.md`**(崩壊検出の移譲)を追随。
- [ ] `plans/PLAN-007` §5 の表の該当行を「→ 採択(2026-08-30)。ADR-047 参照」に畳む。
- [ ] ADR-046 リスク欄 / `STATE.md`「人間の承認・判断を待っている事項」5 を**閉じる**。

### 決定2: specificity の裸書式の符号 = **減算 `-` / 乗算 `*`**

- [ ] **凍結する ADR を起こす**(新規、または PLAN-002 §4.1.1 の7規約に追記 + ADR)。
  `-` = U+002D(HYPHEN-MINUS) / `*` = U+002A(ASTERISK) / `=` = U+003D。空白なし / 改行なし / ASCII 半角数字。
  参照規則は `a−b+2`(減算) / `a×b+2`(乗算)(PLAN-003 §4.6)。
- [ ] `configs/templates/` に **specificity 群の確定文面**を追加する
  (`configs/templates/smoke.yaml` L45-49 に暫定文面がある。それを確定文面に置き換え/昇格)。
  カテゴリキーは `code/eval/battery/specificity_control.py` の既存定義に合わせる(要確認)。
- [ ] **`configs/templates/eval_main.yaml` に specificity 群を追加**(ADR-046 決定4 が「文面未確定」で
  保留していた分。これで `eval_main` が T1b + T3 + T2 + specificity になる。T1 は入れないまま)。
- [ ] **`code/tests/test_eval_main_template.py` を更新**(現在7件。specificity 群の存在と per-task ファイルとの
  sync を足す。「specificity は入れない」を主張しているテストがあれば反転させる)。
- [ ] `plans/PLAN-004-phase0-route.md` 順4:「specificity 文面未確定でプールを作れない」の但し書きを外す。

### 決定3: PLAN-006 §3 = **案 B**(`eval.magnitude_sweep.seeds = [0, 1, 2, 3, 4]`)

- [ ] `logs/DECISIONS.md` ADR-041 の「2026-08-29 追記 — 決定5 の確定」に
  「**シード値 = `[0, 1, 2, 3, 4]`(案 B。提案 PLANNER / 採択 人間 2026-08-30)。`[MATCHED]`**」を足す。
- [ ] **PLAN-006 §4 の実装を IMPLEMENTER タスクとして実行**(下の「実装1」)。
  `configs/template.yaml` の `eval.magnitude_sweep.seed`(null)を `seeds: [0, 1, 2, 3, 4]` に置き換える。

### 決定4: 並行ブランチ `claude/objective-mestorf-34f57d` = **破棄可**

- [ ] `git log claude/objective-mestorf-34f57d --oneline` と `git diff main...claude/objective-mestorf-34f57d --stat`
  で4 commit の中身を**最終確認**する(`CLAUDE.md` §2 の批判的視点。STATE.md の記述を鵜呑みにしない)。
- [ ] `git worktree remove .claude/worktrees/objective-mestorf-34f57d`
- [ ] `git branch -D claude/objective-mestorf-34f57d`
- [ ] `STATE.md`「並行ブランチ(登録簿)」表の該当行を消す(または「破棄済 2026-08-30」に)。

## 実装(GPU 時間 0)

### 実装1: `plans/PLAN-006` §4 —— `code/eval/sweep.py` のマルチシード化

PLAN-006 §4 の6手順そのまま。`SweepPlan.seed: int` → `seeds: list[int]`、
`code/eval/sweep.py` の測定ループが `M` ごとにシード平均 + シード間 SD を `results/` に出す。
`build_items` のシグネチャ(`seed: int`)は変えず、ループは `sweep.py` 側。
**合否基準は作らない**(ADR-041 が θ を人間の決定にしている)。単数 `seed` のフォールバックを残さない。

### 実装2: `plans/PLAN-007` §4 —— 強制選択採点器

PLAN-007 §4 の7手順そのまま:
- 二値項目のロジット読み経路を `code/eval/` に足す。候補 `{"Yes", "No"}` + 正規化した変種。
  候補集合は明示定数(`code-style` §1)。
- `code/eval/run.py` の `comparison` 群を強制選択経路に回す(数値経路 T1 / T2 は不変)。
  二値群は `elicitation: direct` 固定(CoT と両立しない)。
- `metrics.json` に採点方式(`scoring: forced_choice` / `free_generation`)を群ごとに残す。
- 4値分解の構築時検査に「二値・強制選択の群は `parse_fail_rate == 0` かつ `other_error_rate == 0`」を足す。
- 既存の `constant_answer_baseline`(`code/eval/scoring.py`)が強制選択の出力を通ることをテストで確認。
- **合否基準・Go/No-Go 判定コードは書かない**(PLAN-007 §4-7)。

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-007-t1b-gonogo-branch.md` 全文(224行。短い)
- `plans/PLAN-006-sweep-multiseed.md` 全文(101行)
- `STATE.md` 冒頭の★★★★★★★★★ブロック(人間の4決定の逐語)
- `logs/DECISIONS.md` ADR-041 / ADR-046(追記先。`grep -n "ADR-041\|ADR-046"` で位置特定 → `sed -n`)
- `code/eval/battery/t3_comparison.py`(T1b / T3 の実体)/ `code/eval/parsers/boolean.py`(現行パース)/
  `code/eval/run.py:255-353`(`boolean_response_metrics` / ディスパッチ)
- `code/eval/battery/magnitude_sweep.py` / `code/eval/sweep.py`(マルチシード化の対象)
- `code/eval/battery/specificity_control.py` / `configs/templates/smoke.yaml` L45-49(specificity の暫定文面)
- **全文 `cat` しない。`grep -n` → `sed -n 'X,Yp'`。**

## やってはいけないこと

- **θ の値を提案・決定しない**(ADR-041 決定2・3)。
- 合否基準・しきい値を作らない(ADR-045 決定2 / ADR-041 の思想)。実装1・実装2 とも「4値/表を出すだけ」。
- 事前登録した予測・解析計画を実験後に変更しない(`CLAUDE.md` §2)。事前登録は未凍結なので本文の書き換えは可。
- 人間の承認なく GPU ジョブを起動しない。
- **`configs/templates/eval_main.yaml` と per-task ファイルを片方だけ直さない**
  (`code/tests/test_eval_main_template.py` が drift を止める)。
- 並行ブランチを、中身を `git log` で見ずに削除しない。

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

- **θ の値**(ADR-041。順5 の掃引表を見てから)。**現時点で唯一の未解決の人間待ち。**
- ADR-047 起草時に「案 C(T1b を主軸から外す)を backstop として残すか」を人間に1度だけ確認してよい
  (人間は案 A のみを選んだ。ラダーは選んでいない)。
