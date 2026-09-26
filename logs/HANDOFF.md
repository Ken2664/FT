# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その103)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(PLAN-032 のレビュー H2-1〜H2-7 が済み、ADR-107 と §8.1 を書いた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — 次は IMPLEMENTER が PLAN-032 §5 を仕様どおりに実装する(`Documents/10_CONTEXT_POLICY.md` §7 の表の「実装、パーサ、集計スクリプト、データ生成」の行。ADR-101 決定1)。**ただし I4(Δ₂ と判定表)は統計に触れるので、その diff は CRITIC(Opus)か人間が見る**(ADR-101 決定5)。**人間が覆せる**

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。skill `code-style` を読んでから書くこと。
**RunPod MCP は要らない**(GPU は使わない。pod 3 本は `EXITED`。terminate は人間の操作)。

## このセッションでやること(1つだけ)

**`plans/PLAN-032-sharpness-diagnostic.md` §5 の I1〜I4・I6 を §8.1 の R1〜R7 どおりに実装し、`pytest code/tests -q` を通し、config の `--dry-run` の件数と data_checks を報告する。**

1. 読む: `plans/PLAN-032` §5・**§8.1(R1〜R9 = 凍結 tag の対象。仕様の正本)**・§3.1・§6。ADR-107 は `grep -n '^## ADR-107' logs/DECISIONS.md` から
2. I1 `code/data_gen/sweep_pool.py` に診断の腕(例 `diag`)を足す: θ = R1 の 19 水準・`pairs_per_cell` 80・**T < 1 の項目は作らず、除いた (セル × 極性 × θ) と件数を manifest と `log.txt` に残す**。**R8・S の項目と sha256 は変えない**(回帰テストで固定)。R8 の 20 組が 80 組に含まれることをテストで確かめる
3. I2 (A) の文面: `configs/templates/diag_explicit.yaml`(T1b・T3)・`diag_explicit_d.yaml`(T1b だけ)。`render_prompt`(`code/eval/battery/t3_comparison.py:328-345`)に和の差し込みを足す(名前は任意。**描画された文面が §8.1 R1 の表と 1 バイトも違わないこと**)。**既存のテンプレートの文面は 1 バイトも変えない**。A と B の文面が `a + b` の部分だけ違うことをテストで確かめる。B-d は既存の `order6b_d` と同じ文面
4. I3 config: 腕ごと(B / A / B-d / A-d)。パイロットの config の写しで差の欄を冒頭に列挙(順6b の config と同じ形)。`eval.forced_choice_top_k: 20`・`gonogo.near_tie_margin: 0.25`・**`eval.batch_size: 4`**。B-d・A-d は T1b だけ
5. I4 `code/analysis/sharpness_fit.py`(新規): R2 の Δ₂・R3 の「届く」・R4 の 2 × 2(**T1b と T3 に別々**)・R5・R6 の記述の行・**R7 で止める**(Δ₂ の 5 水準の件数が 160 でない / A と B の対がそろわない)。出力 `results/diag_sharpness/`(json + txt)。`r8_fit` の揃え方・階段を再利用
6. I6 テスト(負例を含む)→ `pytest code/tests -q` → 各 config の `--dry-run` → PLAN-032 §10・§11 / STATE / CHANGELOG / commit / 次の HANDOFF(人間が凍結 tag → G2-1)

## 直前セッションで確定したこと

- **ADR-107(人間が 15 問とも推奨を選んだ)**: A と B を対 / 80 組 / L1 + T < 1 の除外 / T1b は裸と (d) の両方(判定は裸)/ **Δ₂ ≥ 0.088 を点推定で A・B に同じく、3 セルすべてで「届く」、T1b と T3 は別々** / batch 4 + 近接同点の感度 / ③-iii は T1b の B-d で決める / パイロットのアダプタ 10 本の固定オフセットの T1b・T3 は凍結 tag の後
- パイロット用プール(`data/generated/battery/pilot/manifest.json` の `fill.assignment`)の併合セル 12 個はすべて **80 組ちょうど**・組の和 5〜1,968(組合せの性質)。**Δ₂ の 5 水準(θ ∈ {−2..+2})に T < 1 は出ない**(θ = −2 で T ≥ 3)。除外が出るのは θ ≤ −5 から
- 件数の算定(除外の前): A・B × T1b・T3 = 72,960 + B-d・A-d = 36,480 → **109,440 件**(見積りではない。dry-run で数える)

## 触ってよいファイル / 読むべき範囲

- 書く: `code/data_gen/sweep_pool.py` / `code/eval/battery/t3_comparison.py` / `configs/templates/diag_explicit*.yaml`(新規)/ `configs/exp_diag_*.yaml`(新規)/ `code/analysis/sharpness_fit.py`(新規)/ `code/tests/`(新規テスト)/ `plans/PLAN-032` §10・§11 / `STATE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- **編集しない**: **`plans/PLAN-032` §8.1**(変えるなら ADR が要る)/ `logs/DECISIONS.md` / 既存のテンプレート / `CLAUDE.md`・`AGENTS.md`・`Documents/` / run dir / `results/` の既存 / `data/raw/`

## やってはいけないこと

- **§8.1 と違う実装にしない**。仕様が曖昧な箇所は「ここは仕様が曖昧」と明示して人間に上げる(自分で決めない。`CLAUDE.md` §7・§8)
- **パイロットのアダプタの T1b・T3 を回さない**(凍結 tag の後だけ。I5 の config は tag の後でもよい)。tag を打たない・pod を起動しない・GPU を使わない
- R8・S の既存の項目・sha256・文面を変えない。`pool_id: pilot` の数値を主張に使わない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流すと引用符の解釈で失敗することがある(その103)→ ファイルに書いてから `cat >>`。`STATE.md` は 59.3 KB で上限(60 KB)に近い —— 新しいブロックを書いたら古いブロックを `logs/STATE-ARCHIVE.md` の先頭(最初の `---` の直後)へ移す(両方のアンカーを確かめてから両方を書く)

## 未解決 / 人間の承認待ち

- **PLAN-032 の凍結 tag と G2-1 GPU 承認**(実装と dry-run の後。`logs/OPEN-ITEMS.md` の新しい行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
