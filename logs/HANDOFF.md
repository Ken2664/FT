# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その106)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(CRITIC の指摘 C105-1〜8 と実装の読み 1〜11 に人間が答え、ADR-108 を書き、`plans/PLAN-032` §8.1 を直した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — 次は実装とテスト(`Documents/10_CONTEXT_POLICY.md` §7 の表の「実装・集計・データ生成」の行。ADR-101)。**ただし決定2(信頼区間)の diff は統計に触れるので、実装の後に人間か CRITIC (Opus) が見る**(ADR-101 決定5。ADR-108 の「リスク・未解決」)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**skill `code-style` を読んでから書く。RunPod MCP は要らない**(GPU は使わない)。

## このセッションでやること(1つだけ)

**ADR-108 の決定2・3・5〜8 を `code/analysis/sharpness_fit.py` とテストに実装する。**仕様の正本は `plans/PLAN-032` §8.1(**その106 で直した R6・R7**)と ADR-108(`grep -n '^## ADR-108' logs/DECISIONS.md`)。

1. **決定2(R6 の区間)**: `confidence_interval` の端を [−1, 1] で切る。sd(d_i) = 0 のときは json に退化の印(欄名は任意。例 `degenerate: true`)を入れ、txt の行にも印を出す(`[x, x]` を印なしで出さない)。`CI_METHOD` の文言を §8.1 R6 に合わせる。計算法そのもの(組 (a, b) ごとの差の正規近似)は変えない
2. **決定3(S1 の注記)**: `report_lines` の S1 の行(CRITIQUE の `:852-863`)に、§8.1 R6 の注記の文言を出す。S1 の定義は変えない
3. **決定5(R7: R1 の前提の照合)**: 判定表の前に、4 本の run の記録で (i) モデル名・revision が 4 本で同じ(**`build_report` を直接呼ぶ経路でも**。いまは `main` の中だけ)(ii) `metrics.json` の adapter が run の config の `sharpness` 欄の宣言と一致(この診断は null を宣言)(iii) `eval.batch_size` = 宣言(4)(iv) 上位 k = 宣言(20)(v) 4 本の `pool.items_sha256` が一致(**B-d↔B を含む**)を照合し、食い違えば `SharpnessError` で止める。宣言の欄を `configs/exp_diag_{b,a,b_d,a_d}.yaml` の `sharpness:` に足す(4 本で `arm` 以外が一致する既存の検査に乗る)。各条件に負例テスト
4. **決定6(R7: 文面の置き換え)**: A(A-d)の各項目の記録の `prompt` が、対になる B(B-d)の `prompt` の和の部分(T1b `{a}+{b}`・T3 `the sum of {a} and {b}`)を x の数字に置き換えたものと一致することを、全項目で照合する(`check_pairing` の中か隣)。記録の `prompt` が chat template 込みかどうかを先に確かめる。負例テスト
5. **決定7(例外の型)**: 止める経路の `R8FitError`(`r8_fit.sweep_gaps`)・欄の欠けの `KeyError`(`_pairing_key` の `carry`・`operands`、`token_rows` の `prompt`)を `SharpnessError` に包む。止めることは変えない(判定だけを出す経路を作らない)
6. **決定8(テスト)**: `code/tests/test_sharpness_fit.py` の本物の掃引の経路を通すシナリオに 3 つ足す —— (a) T1b と T3 で答え方を変え、R4 の次の段がタスク型ごとに割れる / (b) 既知性のセルを 1 つだけ変え、R3 の「1 つでも下回れば届かない」/ (c) 線 0.088 のすぐ両側(56/640 と 57/640)の Δ₂ を出す。docstring の使い方の例の `\n`(`sharpness_fit.py:7`)を行継続に直す
7. `pytest code/tests -q`(その104 の 1903 + 新規)/ config 4 本の `--dry-run`(件数 102,892 が変わらないこと)/ preflight の data_checks(5 本とも 7 件 PASS)
8. **自己点検**(`CLAUDE.md` §7): 新しいテストが 1 回で全部通ったら、照合の 1 つをわざと外して落ちることを確かめてから戻す
9. `plans/PLAN-032` §10(「ADR-108 決定2・3・5〜8 の実装」の行に [x])・§11(実行ログの行)・ヘッダのステータス(`ADR-108 の実装済み・凍結 tag 待ち`)/ `logs/OPEN-ITEMS.md` の行 / `STATE.md` / CHANGELOG / HANDOFF

## 直前セッションで確定したこと

- **ADR-108(人間が 8 問とも推奨)**: A-d の役割は「記述」(R5 の規則は不変)/ R6 の区間 = 読み 6 の計算法を §8.1 に書き、退化の印と [−1, 1] の切り詰め / S1 に物差しの注記 / 読み 1〜5・7・9・11 はそのまま / R7 に R1 の前提と文面の置き換えの照合 / 記述が出せなければ判定も出さない・例外の型をそろえる / シナリオ 3 つ + docstring
- `plans/PLAN-032` §8.1 の R1 の表(A-d の行)・R6・R7 は**その106 で直し済み**。**R2〜R5 の規則と値(線 0.088)は変えていない**

## 触ってよいファイル / 読むべき範囲

- 書く: `code/analysis/sharpness_fit.py` / `code/tests/test_sharpness_fit.py`(と必要なら `test_diag_sharpness.py`)/ `configs/exp_diag_{b,a,b_d,a_d}.yaml` の `sharpness:` 欄だけ / `plans/PLAN-032`(ヘッダ・§10・§11 だけ)/ `logs/OPEN-ITEMS.md` / `STATE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: `plans/PLAN-032` §8.1(`grep -n '### 8.1' plans/PLAN-032-sharpness-diagnostic.md`)/ ADR-108 / `logs/CRITIQUE.md`「その105」(指摘の行番号つきの場所)
- **編集しない**: `plans/PLAN-032` §8.1(ADR なしで直さない。**実装して §8.1 と食い違う点が見つかったら、直さずに止めて人間に報告**)/ `logs/DECISIONS.md` / `logs/CRITIQUE.md` / 本番のテンプレート / pilot・順6b・パイロット FT の config / R8・S の manifest / `code/analysis/r8_fit.py`(包むのは `sharpness_fit` の側で)

## やってはいけないこと

- **tag を打たない・pod を起動しない・GPU を使わない**。I5(パイロットのアダプタの config)は凍結 tag の後
- 合否線・R2〜R5 の判定の値と規則を変えない。止める条件は「止める」だけで、判定の値を別の値に置き換える経路を作らない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(scratchpad に書いてから `cat >>`)

## 未解決 / 人間の承認待ち

- **ADR-108 の実装 → 決定2 の diff を人間が見るか CRITIC に回すか(ADR-101 決定5)→ PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md` の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
