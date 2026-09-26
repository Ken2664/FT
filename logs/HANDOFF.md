# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その101)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(回数の上限に届いた後の次の手を人間に聞き、ADR-106 で**段1 を閉じた**)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は PLANNER が段2 の PLAN-032 を起草する(設計判断)。`Documents/10_CONTEXT_POLICY.md` §7 の表の「設計判断」の行(ADR-101)。**人間が覆せる**

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP は要らない**(GPU は使わない。pod 3 本は `EXITED`。terminate は人間の操作)。

## このセッションでやること(1つだけ)

**段2(診断 = 鋭さ)の PLAN-032 を起草し、人間のレビュー(H2-1〜H2-5)に出せる形にする**(PLAN-030 §3.1・§3.2 段2。ADR-097 決定1・4・5)。

1. 先に `ls plans/` で番号を確かめる(PLAN-030 §0: 031〜033 は予定番号)
2. 読む(全文を読まない。`grep -n` で節を当ててから `sed -n`):
   - `plans/PLAN-030-shortest-path-to-first-ft.md` §3.2 段2・§6(罠1〜4)
   - ADR-097(`grep -n '^## ADR-097' logs/DECISIONS.md`。決定1 = 鋭さで設計 / 決定4 = 二値群の出口 / 決定5 = ③-ii・③-iii は診断で絞る)/ ADR-096(前段 FT の前の診断)/ ADR-099 決定5(パイロットのアダプタの T1b・T3 は PLAN-032 の凍結 tag の後に測る)
   - 順6b の判定(`STATE.md`「わかっていること」の順6b の節: T3・T1b とも「採る候補なし」)/ ADR-078 決定5(★F139)/ ADR-079 決定8(G12)/ ADR-084(上位 k の記録)
   - `plans/TEMPLATE.md`(形)
3. PLAN-032 を書く: 答える問い・前提と事実(ファイルで確かめたもの)・H2-1〜H2-5 の記入欄の材料(**値は書かない。案は「エージェントの案」と明記**)・罠1(パイロットの T1b・T3 を合否線の凍結より前に開かない)・実装の仕様の骨子・必要なリソース(素のモデルの評価だけの見込み。**見積りは RUNNER**)・やらないこと・完了条件
4. `logs/OPEN-ITEMS.md` に「PLAN-032 のレビュー待ち」の行 / `STATE.md` / CHANGELOG / commit / 次の `HANDOFF.md`
5. 余裕があれば同じ場で人間に H2-1〜H2-5 を聞いてよい(**判断材料の表を先に見せ、推奨と理由つきで**。memory「Recommend before choice」)。聞かずに終えるなら、次のセッションで聞くと HANDOFF に書く

## 直前セッションで確定したこと(ADR-106)

- **段1 は閉じた。**印は 1 回目(625)・回し直し(313)とも `no4` true / `no4b` true / `no5`・`no5b_v1`・`no5b_v2` false のまま記録。**段1 の GPU はこれ以上使わない**(枠の残り 約 3.10 h は使わない。次の GPU は承認を取り直す)
- **新しい人間待ち「★T2 の形の変化と #5 の扱い(Phase 1 の凍結前の設計の問い)」**を `logs/OPEN-ITEMS.md` に立てた。**印の意味づけ・`p2d` の扱い(ADR-103 決定7)もここ**。PLAN-032 はこの問いに答えない(T1b・T3 の鋭さの診断)。**PLAN-032 の中で T2 の問題を解こうとしない**
- §8.5 の実装の読み 7 点は採った(覆さない)
- **アダプタ 10 本の重みはボリューム `r963j7swke` 側にだけある**(この機の `runs/pilot_ft_train_*/adapter/` は `adapter_config.json` と `README.md` だけ)。PLAN-032 の凍結 tag の後に T1b・T3 を測るときはボリュームを使う。**ボリュームを消す案を書かない**

## 触ってよいファイル / 読むべき範囲

- 書く: `plans/PLAN-032-*.md`(新規)/ `logs/OPEN-ITEMS.md` / `STATE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`(人間に聞いたら `logs/DECISIONS.md` に ADR)
- **編集しない**: `configs/`・`infra/`・`code/`・run dir・`results/`・`CLAUDE.md`・`AGENTS.md`・`Documents/`(段3 の対象)

## やってはいけないこと

- **値を決めない・解釈しない**: H2-1(合否線の値)・H2-2(判定の規則)などの値は人間。`pool_id: pilot` の数値は主張・効果量・Δ 5 行・E1 の境界に使わない(PLAN-030 §6 罠2)
- **パイロットのアダプタの T1b・T3 を測る設計を、合否線の凍結 tag より前に置かない**(罠1。ADR-099 決定5)
- **tag を打たない・pod を起動しない・GPU を使わない**(起草だけ)
- 出典を確かめていない文献を書かない(`CLAUDE.md` §3。要るなら SCOUT に委譲し、転記は原典と突き合わせるまで未検証)
- **この機は Windows**: JSON は `python -X utf8` で開く。`python3` は無い。CLI の標準出力は `PYTHONIOENCODING=utf-8`。長い文書は Write ツールで書く。`Read` は 25,000 トークンで打ち切られる(`STATE.md` は 2 回に分けて読む)。Python で書くときは `write_bytes` か `newline='\n'`(repo は LF)。**`STATE.md` は 59 KB で上限(60 KB)に近い** —— 新しいブロックを書いたら古いブロックを `logs/STATE-ARCHIVE.md` へ移す

## 未解決 / 人間の承認待ち

- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前。印の意味づけ・`p2d` の扱いを含む)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(段1 を閉じたので、いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
