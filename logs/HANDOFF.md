# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その65)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目の区切り + コンテキスト超過**(PLAN-026 の I11c を実装・コミットした `3d8b081`。context-guard が約 369k で警告)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その65 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I12 = 順6b の 7 本すべての dry-run と、それで分かった件数のずれの修正(CPU のみ。GPU 0)。**I1〜I11c は済んでいる。

1. **7 本の dry-run を通す**(重みを読まない経路。`infra/RUNPOD.md` §4 の手順):
   - 固定オフセット 3 本: `python -m code.eval.run --config configs/exp_order6b_{pilot,preamble,d}.yaml --dry-run`
   - 掃引 3 本: `configs/exp_order6b_{r8,s_preamble,s_d}.yaml`
   - 較正 1 本: `python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml --dry-run`
   - **プールが手元に無ければ、`configs/exp_order6b_pilot.yaml` 冒頭のコマンドで先に生成する**(pilot の評価プール・R8 と S の掃引プール)
   - `python -m infra.preflight`(前置きのある run は検査6 が SKIP + 理由を出すはず。I7)
2. **dry-run が出した件数を §10・§11 と突き合わせる。**合わなければ**どちらが正しいかを人間に上げる**(§10 は見積り、config が実験条件)。
   **合ったら §10・§11 の run 数を 6 → 7 に直す**(§4.7 読み5。S-① と S-(d) を別に数えると 7 本)。**項目数の合計(15,626 の行)も数え直す**
3. **判定表の CLI が dry-run の run では動かないことを確かめるだけでよい**(`order6b_select.py` は本実行の run を読む。dry-run は `runs/` を作らない)

**完了条件**: 7 本とも dry-run が通った(出力を `logs/CHANGELOG.md` に件数だけ転記)/ preflight が通った / §10・§11 の run 数と項目数が config と一致している / `pytest code/tests -q` が通る(直近の実測は **1514 passed**。その65。全体で約 4 分)/ 本番の文面・`data/raw/`・プール・順6b の config の**判定に効く欄**を 1 バイトも変えていない

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-087**(提案 エージェント / 採択 人間。選択式。**4 問とも推奨**): 決定1 **CLI は 7 本の run すべてを要求**し 1 本でも欠けたら何も出さずに止める / 決定2 **`aggregate.py` の守りは種別(`kind`)を問わない** / 決定3 **記述の腕(①+(c) / (d)+(c))には (i)〜(iv) の合否の印を付けない**(別ブロックに値と来歴と注記だけ)/ 決定4 **判定表の JSON は判定に使った値 + 近接同点の感度の行 + 来歴**(#1〜#3 の全表と当てはめは入れない)
- **I11c は実装済み**(`3d8b081`。読みは PLAN-026 §4.13):
  `code/analysis/order6b_select.py`(新規)= `ArmSpec` / `ARM_SPECS`(7 本の腕の「あるべき記録の形」。config の転記)/ `load_arm`・`_check_shape` / `check_preambles` / `check_calibration_arms` / `settings_of` / `CANDIDATES`(**C0 < C3 < C2 < C1**)・`DESCRIPTIVE` / `Reports` / `cells_i`・`cells_ii`・`numeric_gate`・`far_offsets_iv` / `evaluate`・`select_for`・`preamble_mismatch`・`describe` / `build_report`・`report_lines`・`main`
  `code/analysis/aggregate.py` = `check_not_order6b`(`collect` から呼ぶ。**`expand_metrics_paths` には置いていない** —— `gonogo.py` が同じ関数を使う)
- **候補 → 腕**: C0 = B0 + R8 / C3 = B0 + R8 に較正の腕 `b0` / C2 = (d) + S-(d)(**T1b だけ**)/ C1 = ① + S-①。記述は ①+(c)(腕 `preamble`)と (d)+(c)(腕 `d`)
- **T3 の C2 は `applicable: false`**(「そのタスク型に候補が無い」)で、「満たさなかった」とは別の欄である
- **(c) の run は `aggregate` で「飛ばす」から「止まる」に変わった**(前置きを宣言しているため)。`test_calibration.py` の既存テストを打ち消し線付きで直した
- **`gonogo.py` / `r8_fit.py` / `calibrated.py` / `code/eval/` / 順6b の config は 1 バイトも変えていない**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §4.13・§5・§9・**§10・§11**(`grep -n '^### 4.13\|^## 10\|^## 11' plans/PLAN-026-order6b.md`)
- `configs/exp_order6b_*.yaml`(7 本。**冒頭の注記にプールの生成コマンドと dry-run の入口がある**)
- `code/eval/run.py` の `main` / `dry_run_report`(`grep -n 'dry.run' code/eval/run.py`)/ `code/eval/calibration_run.py` / `infra/preflight.py`
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、torch・transformers は無い。ruff / black も無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- §5 の値(0.70・−2・+3)・判定規則(`choose_from_logprobs`)・4 値分解・**§5 の候補の集合**を変える / 結果を解釈する(`CLAUDE.md` §8)/ GPU / main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- **dry-run の件数が §10 と違ったときに、config のほうを黙って直す。**どちらが正しいかは人間に上げる
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**その64 でこれを踏んだ。**必ず `write_bytes` で書く**
- **`code/tests/` の一部は worktree が CRLF である**(`test_aggregate.py` など)。スクリプトで編集するときは**元の改行コードを保って書き戻す**(その65 でここを踏んだ)
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する。**`\\r\\n` のようなエスケープは heredoc で化ける**(その65)
- **変異の検査を裏で回している間は、対象のファイルとテストを編集しない**
- **変異の検査は「落ちた」だけで満足しない。**その65 は 34 個中 13 個がすり抜けた(**腕の形の 7 つの検査は互いに冗長で、1 つずつは固定されていなかった** / (iii) の #1 と #2 / (iv) の境界と高い側)。**すり抜けたらテストを足す**
- 説明の根拠を確かめずに「原典どおり」と書く(その61)

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.13(I11c の読み)/ §4.12 / §4.11 / §4.10 / §4.9(とくに読み1・読み7)/ §4.8 / §4.7 / §4.6 / §4.5 / ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11。**run 数は 6 → 7 に直してから諮る**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
