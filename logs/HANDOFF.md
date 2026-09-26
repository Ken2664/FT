# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その100)/ 直前セッションの役割: ANALYST
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(`plans/PLAN-031` §8.5 = T2 の崩れ方の形の数え上げを実装・実行し、前提と検算が通った)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は PLANNER が人間に次の手を聞いて ADR を書く。`Documents/10_CONTEXT_POLICY.md` §7 の表の「設計判断」の行(ADR-101)。**人間が覆せる**

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP は要らない**(pod は 3 本とも `EXITED`。起動しない・触らない)。

## このセッションでやること(1つだけ)

**§8.5 の出力を材料に、回数の上限に届いた後の次の手を人間に聞き、新しい ADR(ADR-106)と `plans/PLAN-031` の追補に記録する**(ADR-105 決定3)。

1. 材料を人間に見せる: `results/pilot_ft_t2_form/t2_form.out` の先頭の一覧(形の件数と式の件数。25 行ほど)と訓練の損失の節、`logs/CHANGELOG.md` その100 の「記述」。**数値は run_id つきで、ファイルから引く。解釈を書かない**(意味づけは人間)
2. 候補(ADR-105 決定3: 途中のチェックポイントの掃引 / `learning_rate` を下げる / #5 の基準を見直す / 訓練の書式の見直し / 段1 を閉じて段2(PLAN-032)へ など)を、**推奨と理由つきで** `AskUserQuestion` で聞く(memory「Recommend before choice」)。GPU を使う手なら、段1 の残り枠 約 3.10 h(ADR-104 の後の実績 5.895 h)・承認済みの単価の上限・新しい承認や凍結 tag の要否も並べる
3. 回答を ADR-106(提案者と採択者を分ける。ADR-039 決定3)と `plans/PLAN-031` の追補(§8.6 など)・§11 に記録 → `logs/OPEN-ITEMS.md` の ★313 の行 / `STATE.md` / CHANGELOG / commit / 次の `HANDOFF.md`
4. 余裕があれば同じ場で聞く(人間が望めば): 印の意味づけ・`p2d` の扱い(ADR-103 決定7)・§8.5 の実装の読み 7 点(`plans/PLAN-031` §11 その100 の行)を覆すか

## 直前セッションで確定したこと

- **出力**: `results/pilot_ft_t2_form/t2_form.{json,out}`(B0 [run:20260922_121455_order6b_b0] + 評価 10 本 `pilot_ft_eval_*` × T2 × 3 セル・参考行 2・訓練 10 本 `pilot_ft_train_*`)。**前提 (a)〜(d) は 10 本すべて通り、検算 3 つも通った**(4 値は `gonogo_ft.json` の T2 行と 60/60 ブロックで一致)
- **ADR-105 の文脈 1〜5 の値は出力と食い違わなかった**(ADR-105 は直していない)
- 形の件数・長さ・形 × 分類・参考行・損失の到達ステップの要約は `logs/CHANGELOG.md` その100(`grep -n '^## 2026-09-26(その100)' logs/CHANGELOG.md`)。**B0 の「式」の件数は単位・括弧を挟む形(`51 (students in the gym) + 7` など)を数えていない**(定義は結果の後に広げていない)
- `pytest code/tests -q` = **1810 passed**

## 触ってよいファイル / 読むべき範囲

- 読む: ADR-105(`grep -n '^## ADR-105' logs/DECISIONS.md`)/ `plans/PLAN-031` §8.1 B・§8.5(`sed -n '/^### 8.5/,/^## 9\./p'`)/ ADR-103 決定5・7・8・ADR-104 / `results/pilot_ft_t2_form/t2_form.out`(**`sed -n 1,25p` と `sed -n '/^== 訓練の損失/,$p'` だけ。全文を読まない**)/ `logs/OPEN-ITEMS.md` の ★313 の行
- 書く: `logs/DECISIONS.md`(ADR-106)/ `plans/PLAN-031`(追補・§11)/ `logs/OPEN-ITEMS.md` / `STATE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- **編集しない**: `configs/`・`infra/`・`code/`・run dir・`results/`

## やってはいけないこと

- **解釈を書かない・人間の代わりに決めない**: 「FT が推論を消した」「書式が原因」などの断定、印の意味づけ、次の手の確定は人間(`CLAUDE.md` §7・§8)。`pool_id: pilot` の数値は主張・効果量・Δ 5 行・E1 の境界に使わない
- **#5 の基準を結果の後に変える案**は HARKing と読まれる危険がいちばん高い(ADR-105 の代案欄)。出すなら危険を並べて書く
- **tag を打たない・pod を起動しない・GPU を使わない**(このセッションは記録だけ)
- **この機は Windows**: JSON は `python -X utf8` で開く。`python3` は無い。CLI の標準出力は `PYTHONIOENCODING=utf-8`。長い文書は Write ツールで書く。`Read` は 25,000 トークンで打ち切られる(`STATE.md` は 2 回に分けて読む)。Python で書くときは `write_bytes` か `newline='\n'`(repo は LF)

## 未解決 / 人間の承認待ち

- **§8.5 の後の次の手**(このセッションの本題。新しい ADR)/ 印の意味づけ / `p2d` の扱い(ADR-103 決定7)/ §8.5 の実装の読み 7 点を覆すか
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(段1 の後。アダプタ 10 本はボリューム `r963j7swke` 側の資産)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり(段2 の PLAN-032 は段1 の後でも並べてよい)
