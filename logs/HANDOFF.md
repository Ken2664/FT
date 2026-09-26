# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その107)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(ADR-108 決定2・3・5〜8 の実装・テスト・dry-run が済んだ)+ コンテキスト超過(hook が約 324k を警告)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Opus** — 次は統計に触れる diff のレビュー(`Documents/10_CONTEXT_POLICY.md` §7 の表の「統計・解釈」の行。ADR-101 決定5)。**ただし人間が決定2(区間)の diff を自分で見るなら、このセッションは要らない**(人間が決める。そのときは凍結 tag へ進む)

---

あなたは CRITIC です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。RunPod MCP は要らない(GPU は使わない)。

## このセッションでやること(1つだけ)

**ADR-108 の実装の diff を §8.1 R6・R7 / ADR-108 決定2・3・5〜8 と突き合わせてレビューし、指摘を `logs/CRITIQUE.md` に「その108」として追記する。**コード・`plans/PLAN-032`・`logs/DECISIONS.md` は直さない(CRITIC は直さない)。

見る範囲: `git diff 410f57a..HEAD -- code/analysis/sharpness_fit.py configs/exp_diag_b.yaml code/tests/test_sharpness_fit.py code/tests/test_diag_sharpness.py`(`410f57a` = その106 の commit。実装はその次の commit)。とくに:

1. **決定2(統計に触れる。ADR-101 決定5 の対象)**: `confidence_interval` の [−1, 1] の切り詰めと退化の判定(`len(set(differences)) == 1` = 有理数で比べる)。計算法(組ごとの差の正規近似)は変えていないか。切り詰めが点推定・R3 の判定に触れないか(判定は `estimate` だけ)
2. **決定5(R7: R1 の前提)**: `check_premises`。**上位 k は §8.1 R7 の「上位 k が 20 でない」を config の `eval.forced_choice_top_k` と全行の `top_k` の個数で照合した**(metrics.json の `forced_choice` 欄は重みを読んだ run にしか無い)。この読みは §8.1 の文面と食い違わないか。adapter は宣言(null)との一致で、4 腕で同じかどうかではない
3. **決定6(文面の置き換え)**: `explicit_prompt_of`・`check_prompt_substitution`。和の部分が B の `prompt` にちょうど 1 か所、x = a + b、全項目。本物の run の記録の `prompt` が chat template の外であること(`run.render_prompts` の docstring・`test_recorded_prompts_are_the_bare_template_text`)
4. **決定7(例外の型)**: 止める経路がすべて `SharpnessError`。判定の値を別の値に置き換える経路が増えていないか(止める条件が増えただけか)
5. **テスト**: (c) の 56/640・57/640(`test_the_line_is_crossed_between_56_and_57_over_640`。B-d の run を本番の件数で回す)と、シナリオ 3 つが「配線の取り違え」を捕まえるか

## 直前セッションで確定したこと(ファイルに書き込み済み)

- 実装の内容と自己点検は `logs/CHANGELOG.md`「その107」・`plans/PLAN-032` §11 の表と注 12〜17。**自己点検**: 照合を 16 通りわざと外して対応するテストが落ちることを確かめてから戻した(区間の切り詰め・退化・文面・sha256・adapter・batch・上位 k・モデル・R3 の all→any・T3 が T1b の判定を読む配線・線の `>=`→`>`・線 ±1/640・`KeyError`・`R8FitError`・S1 の注記)
- 検査: `pytest code/tests -q` → **1958 passed**(その104 は 1903)/ config 4 本の `--dry-run` = 102,892 件(不変)/ `test_diag_sharpness.py` の data_checks は通っている
- **R2〜R5 の規則と値(線 0.088)は変えていない**。config 4 本は `sharpness:` に `adapter: null`・`batch_size: 4`・`top_k: 20` の 3 欄を足しただけ

## 触ってよいファイル / 読むべき範囲

- 書く: `logs/CRITIQUE.md`(追記のみ)/ `STATE.md`(ヘッダ・いま何をしているか・引き継ぎ)/ `logs/CHANGELOG.md` / `logs/HANDOFF.md` / `logs/OPEN-ITEMS.md`(PLAN-032 の行に追記)
- 読む: 上の `git diff` / `plans/PLAN-032` §8.1(`grep -n '### 8.1' plans/PLAN-032-sharpness-diagnostic.md`)・§11 の注 12〜17 / ADR-108(`grep -n '^## ADR-108' logs/DECISIONS.md`)
- **編集しない**: コード・config・テスト・`plans/PLAN-032` §8.1・`logs/DECISIONS.md`

## やってはいけないこと

- **tag を打たない・pod を起動しない・GPU を使わない**。合否線・R2〜R5 の規則を変えない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `cat >>` / `python <script>`。Python に渡すパスは `C:/Users/...` の形。`/c/Users/...` は解決されない)
- `git stash` で作業ツリーを動かさない(今回、基準線の行長の確認に使ったが、コミット前の未追跡の変更がある状態では危ない)

## 未解決 / 人間の承認待ち

- **決定2 の区間の diff を人間が見るか CRITIC に回すか**(ADR-101 決定5)と、**実装の読み 12〜17**(`plans/PLAN-032` §11 の注)の確認 → **PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md` の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
