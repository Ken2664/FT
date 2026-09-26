# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その97)/ 直前セッションの役割: RUNNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(回し直し(`num_steps` 313。訓練 5・評価 5)を実行し、印を当て、回収し、pod を停止した。**§8.1 B の回数の上限に届いたので止めて報告した**)
直前セッションの実モデル: Claude Sonnet 5
**推奨モデル(次のセッション)**: **Opus** — 印の意味づけの材料づくりは「結果の解釈・`CLAUDE.md` §8 の周辺」(`Documents/10_CONTEXT_POLICY.md` §7 の表の 1 行目)。ただし**このセッションの仕事は記述(数え上げ)だけで、解釈は人間**。**人間が覆せる**(数え上げの実装だけなら Sonnet でも足りる。解釈・ADR を書く場面になったら Opus)。

---

あなたは ANALYST です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP は要らない**(pod は 3 本とも `EXITED`。起動しない・触らない)。

**★最初に人間へ 1 行で確かめる**: 「この仕事(下)でよいか。印の意味づけの議論・次の手の相談(新しい ADR)・PLAN-032 の起草を先にしたいなら、そちらに切り替える」。**回数の上限に届いた後の次の手は人間が決める**ので、この仕事は人間が望んだときだけ進める。

## このセッションでやること(1 つだけ。人間が承認したら)

**回し直し(313)と 1 回目(625)の T2 の応答の内訳を、記述だけで数え上げ、人間が印を意味づける材料にする。**解釈・「改善/悪化」の判定・原因の断定は書かない。

- **先に** `plans/PLAN-031-seed-fix-and-pilot-ft.md` に、この記述の範囲を数行足す(`CLAUDE.md` §4。設計変更ではないので人間のレビューは要らない見込み)
- 実装: `code/analysis/` に読み取り専用の CLI を 1 本(名前の案: `t2_response_profile`。skill `code-style` に従う: 1 関数 1 責務・マジックナンバー禁止・docstring に「答える問い」・テスト)。`runs/pilot_ft_eval_*/predictions/*.jsonl`(1 回目 5 本)と `runs/pilot_ft_eval_*_n313/predictions/*.jsonl`(回し直し 5 本)を読み、**(run × セル)ごとに**次を出す。出力は `results/pilot_ft_t2_profile/`(JSON + `.out`。新規。既存の `results/pilot_ft*` は触らない):
  1. 異なる `response` の個数と、最頻 5 件(件数つき)
  2. `parsed` が `truth`・`rule_values`(`p2`・`p2d`・`x2`・`arb`)・被演算子(`operands`)のどれと一致するか、どれとも一致しないか(件数)
  3. `other_error` の項目の `parsed − truth` の分布(規則的なズレ(±10・±100 など)があるか。**あるかないかを数えるだけ**)
  4. 同じ条件・別シード(`p2` s0 対 s1)/ 同じ (条件, シード)・別回(625 対 313)で、**同じ `item_id` の `response` が一致する件数**
  5. 4 値(correct / rule / other_error / parse_fail)は必ず 4 つ揃えて報告(`CLAUDE.md` §6)
- **完了条件**: `pytest code/tests -q` が通る(現在 1747 passed)/ `results/pilot_ft_t2_profile/` に出力 / `logs/CHANGELOG.md` に追記(actor 行つき)/ commit(`stat(analysis):`)/ `STATE.md` 更新 / この `HANDOFF.md` の書き換え
- **セルとファイルの対応は未確認**: `word_problem.jsonl`(160 件)= T2 の `id` + `interp`(各 80 の見込み)/ `word_problem.ans_out.jsonl`(80 件)= T2 の `extrap_magnitude` の見込み。**項目の `coverage` ラベルを items.jsonl / manifest / `gonogo_ft.json` の `cells` と突き合わせて確かめてから使うこと**(件数だけで決めない)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **回し直しの実行**: 訓練 5・評価 5 すべて rc 0([run:pilot_ft_train_p2_s0_n313] [run:pilot_ft_train_p2_s1_n313] [run:pilot_ft_train_ident_s0_n313] [run:pilot_ft_train_ident_s1_n313] [run:pilot_ft_train_p2d_s0_n313] [run:pilot_ft_eval_p2_s0_n313] [run:pilot_ft_eval_p2_s1_n313] [run:pilot_ft_eval_ident_s0_n313] [run:pilot_ft_eval_ident_s1_n313] [run:pilot_ft_eval_p2d_s0_n313])。commit `b6bd284`・`5e627c6`。`git_sha` = `cbe76ce`・`git_diff.patch` = 0 B。**1 回目との差は `num_steps`(625 → 313)と実行ホストだけ**(評価プールの `items_sha256` `c5072f48…`・訓練データの `format_hash`・LoRA 初期値の指紋は同じ)
- **印(`results/pilot_ft_n313/gonogo_ft.json` の `summary`。当てただけ)**: `no4` **true** / `no4b` **true** / `no5` **false**・`no5b_v1`・`no5b_v2` **false**(判定 5 run すべて割れ)。**4 値の表 30 セルは `logs/CHANGELOG.md` 2026-09-26(その97)**(`grep -n 'その97' logs/CHANGELOG.md`)。**§8.1 B の (true, false) は「下げた後なら止めて報告(回数の上限)」→ 止めて報告した**。`learning_rate` は動かしていない
- **T2 の応答の異なる個数(`word_problem.jsonl` 160 項目。CHANGELOG その97 の集計。記述のみ)**: 今回 p2_s0 111 / p2_s1 **44** / ident_s0 88 / ident_s1 90 / p2d_s0 **38**、1 回目 102 / **47** / 88 / 88 / **43**。**今回 p2_s1 の先頭 2 行は、被演算子が違うのに同じ response `155`。原因は調べていない**(この仕事がそれを数える)
- **`predictions/` の置き場**: 1 回目・今回の評価 10 本ぶんがこの機の `runs/pilot_ft_eval_*/predictions/`(1 回目 = 接尾辞なし・今回 = `_n313`)にある(`.gitignore` の対象。git に無い。ボリューム `r963j7swke` にもある)。**各 run の `word_problem.jsonl` の先頭 1 行の欄: `item_id, group, category, operands, carry, params, prompt, response, parsed, truth, rule_values, reference_rule, classification`**
- **費用・pod**: 1.575 h ≈ $1.17(推定)。**段1 の 9 h 枠の使用 = 4.32 + 1.575 = 5.895 h、残り 約 3.10 h**。pod 3 本(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)すべて `EXITED`・稼働中 0。terminate は人間
- **時間の事実**: 訓練の壁時計は 313 でも 1 回目(625)と同じ範囲(278〜303 s 対 300〜322 s)で、半分にならなかった(ホストが違うので内訳は交絡する。解釈していない)

## 触ってよいファイル / 読むべき範囲

- 読む: `logs/CHANGELOG.md` の末尾エントリ(その97。`grep -n '^## 2026-09-26'`)/ `results/pilot_ft_n313/gonogo_ft.out`・`gonogo_ft.json`(1 回目は `results/pilot_ft/`)/ `plans/PLAN-031` §8.1 B・§8.3 / `logs/DECISIONS.md` の ADR-103 決定5・7・8 と ADR-104(`grep -n '^## ADR-10[34]'`)/ 各 run の `predictions/*.jsonl` は **`python -X utf8` で数える・`head -c` で 1〜2 行見る。全文を `cat` しない**(`CLAUDE.md` §10.1)
- 書く(新規のみ): `code/analysis/t2_response_profile.py`・`code/tests/test_t2_response_profile.py`・`results/pilot_ft_t2_profile/`・`plans/PLAN-031` の追補・`logs/CHANGELOG.md`・`STATE.md`・`logs/HANDOFF.md`
- **編集しない**: `configs/`・`infra/`・既存のコード・**1 回目と `_n313` の run dir(`predictions/` は読み取りのみ)**・`results/pilot_ft/`・`results/pilot_ft_n313/`・`logs/DECISIONS.md`(ADR は人間が決める)

## やってはいけないこと / 踏んだ地雷

- **解釈しない**: 印の意味づけ・「313 で改善した / 悪化した」・「モデルが○○している」の断定を書かない(数値と対照条件との差で報告する。`CLAUDE.md` §7・§8)。`pool_id: pilot` の数値は主張・効果量・Δ 5 行・E1 の境界に使わない
- **tag を打たない・ADR を書かない・`learning_rate` を動かさない・pod を起動しない**(すべて人間 / RUNNER。`gonogo_ft` の印を作り直さない)
- **この機は Windows**: JSON を Python で開くときは **`python -X utf8`**。`python3` は無い(`python`)。Git Bash のヒアドキュメントを入れ子にすると壊れるので、長い文書は Write ツールで書く。`Read` は 25,000 トークンで打ち切られる(STATE.md は 2 回に分けて読む)
- 結果が良すぎる・割れているときは、まずバグ(パーサの取りこぼし・評価データの汚染・生成側の異常)を疑う。**`response` はモデルの生成文字列でパーサの出力ではない**ので、同じ response の繰り返しは「パーサの取りこぼし」では説明できない(それが何かは数え上げで示すだけ。原因は書かない)

## 未解決 / 人間の承認待ち

- **回数の上限に届いた後の次の手**(`learning_rate` を動かすか = ADR-103 決定8 / 基準の見直し / 別の手。**新しい ADR。人間**)/ 印の意味づけ(`p2` s1 の T2 の割れ・`ident` の T2 の other_error・T1 × `extrap_magnitude` の割れ・`p2d` の #5b)/ `p2d` の扱い(ADR-103 決定7)
- 3 本の pod の terminate(段1 の後。アダプタ(1 回目 5 本・回し直し 5 本)はボリューム `r963j7swke` 側の資産)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり(段2 の PLAN-032 は段1 の後)
