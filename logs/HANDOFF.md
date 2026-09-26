# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その98)/ 直前セッションの役割: ANALYST
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(人間が選んだ「T2 の応答の内訳の数え上げ」(PLAN-031 §8.4)を実装・実行・検算し、`results/pilot_ft_t2_profile/` に出した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は「人間の意味づけ・次の手の決定を受けて ADR を書く / PLAN を追補する」か「PLAN-032 の起草」で、どちらも設計判断(`Documents/10_CONTEXT_POLICY.md` §7 の表)。**人間が覆せる**。

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**RunPod MCP は要らない**(pod は 3 本とも `EXITED`。起動しない・触らない)。

**★最初に人間へ 1 行で確かめる**: 「回数の上限に届いた後の次の手(`learning_rate` を動かす = ADR-103 決定8 / 基準の見直し / 別の手)を決めたか。決めたなら ADR に記録する。まだなら、材料(下)を見せて相談するか、PLAN-032(段2 の診断)の起草を先にするか」。**次の手を決めるのは人間**(`CLAUDE.md` §8)。エージェントは推奨を理由つきで出してよいが、採否は人間(memory `recommend-before-choice`)。

## 人間に見せる材料(ファイルに書き込み済み。読むだけ)

- **印**: `results/pilot_ft_n313/gonogo_ft.out`(1 回目は `results/pilot_ft/`)/ 4 値の表 30 セル = `logs/CHANGELOG.md` その97(`grep -n 'その97' logs/CHANGELOG.md`)
- **T2 の数え上げ(その98)**: `results/pilot_ft_t2_profile/t2_profile.out`(人が読む形。約 20 KB。**`grep -n` で run を選んで開く**)/ 要約は `logs/CHANGELOG.md` その98 の「記述」の箇条書き。要点(記述のみ):
  - 異なる応答の個数(セル 80 項目): `p2` s1 は 32〜39(id・interp)、`p2d` s0 は 24〜29(id・interp)、ほかは 53〜76(`p2d` の extrap_magnitude が 53・54)
  - `parsed` が truth・p2・p2d・x2・arb・被演算子のどれとも一致しない件数: `p2` s1 は 66〜78、`p2d` s0 は 68〜76(セルあたり 80)/ 被演算子との一致は 30 セルで合計 2
  - 同じ `item_id` の response 一致: `p2` s0 対 s1 は 0〜1/80(両回)/ `ident` の 313 対 625 は 74〜79/80 / `p2` s0 の 313 対 625 は response 67〜77・parsed 80/80
  - ±10・±100・±1000 の差はセルあたり 0〜4 件
- **やっていないこと**: 原因の調査(`ident` の 2 つの回の応答がほぼ同じである理由 など)。**必要なら人間が ANALYST に頼む**

## 人間が次の手を決めたら(PLANNER の仕事)

1. `logs/DECISIONS.md` に新しい ADR(ADR-105 の見込み。`grep -n '^## ADR-10' logs/DECISIONS.md | tail -3` で番号を確かめる)。**提案者と採択者を分けて書く**(ADR-039)
2. `plans/PLAN-031` に追補(§8.1〜§8.4 は変えない。§8.1 は凍結 tag `preregister-pilot-ft` の対象)。GPU を使う手なら、段1 の 9 h 枠の残り 約 3.10 h と ADR-103 の規則(倍か半分・各向き 1 回・lr は自動で動かさない)に照らし、**新しい承認が要るかを人間に聞く**
3. `STATE.md`・`logs/OPEN-ITEMS.md`(「★313 の印の意味づけと次の手」の行)・`logs/CHANGELOG.md`・commit・この `HANDOFF.md`

## 触ってよいファイル / 読むべき範囲

- 読む: `logs/CHANGELOG.md` その97・その98 / `results/pilot_ft_n313/gonogo_ft.out` / `results/pilot_ft_t2_profile/t2_profile.out`(grep で)/ `plans/PLAN-031` §8.1・§8.4 / `logs/DECISIONS.md` の ADR-103・ADR-104(`grep -n '^## ADR-10[34]'`)/ `logs/OPEN-ITEMS.md` の「★313」の行
- 書く: `logs/DECISIONS.md`(**人間が決めたときだけ**)・`plans/PLAN-031` の追補 or `plans/PLAN-032-*.md`(新規)・`STATE.md`・`logs/OPEN-ITEMS.md`・`logs/CHANGELOG.md`・`logs/HANDOFF.md`
- **編集しない**: `configs/`・`infra/`・`code/`(PLANNER はコードを書かない)・run dir・`results/`

## やってはいけないこと / 踏んだ地雷

- **解釈を書かない・決めない**: 印の意味づけ・「313 で改善/悪化」・「モデルが○○している」の断定は人間(`CLAUDE.md` §7・§8)。`pool_id: pilot` の数値は主張・効果量・Δ 5 行・E1 の境界に使わない
- **tag を打たない・`learning_rate` を動かさない・pod を起動しない**(人間 / RUNNER)
- **この機は Windows**: JSON は **`python -X utf8`** で開く。`python3` は無い(`python`)。CLI の標準出力は **`PYTHONIOENCODING=utf-8`** が要る(cp932 で落ちる)。長い文書は Write ツールで書く。`Read` は 25,000 トークンで打ち切られる
- **評価 run の `metrics.json` の `adapter` は pod 上の絶対パス**(`/workspace/translesion/runs/...`)。この機で訓練 run を辿るときは `adapter_train_run_id` を `runs/` の下で引く(`gonogo_ft.train_record` はこの機では None を返す。その98 で判明。`gonogo_ft` は変えていない)

## 未解決 / 人間の承認待ち

- **回数の上限に届いた後の次の手**(新しい ADR。人間)/ 印の意味づけ / `p2d` の扱い(ADR-103 決定7)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(段1 の後。アダプタ 10 本はボリューム `r963j7swke` 側の資産)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり(段2 の PLAN-032 は段1 の後でも並べてよい)
