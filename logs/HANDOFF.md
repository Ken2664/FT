# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その80)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: PLAN 完了(PLAN-030 の起草)。コンテキストが約 10 万トークンに達した

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。ADR-095 決定1)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-030 §8 の R-1〜R-4 を人間に聞き、回答を ADR-098 に記録する。**
手順: (1) **先に判断材料の表をチャットで見せる**(ADR-097 決定6)—— PLAN-030 §3.1(段の表)・§4.1〜§4.3(振り分けと整理候補)・§5.2(置き場所の 4 案)を要約した表 /
(2) `AskUserQuestion` で R-1〜R-4 を選択式で聞く / (3) `logs/DECISIONS.md` に ADR-098(提案 エージェント (PLANNER, Opus 5.5) / 採択 人間)/
(4) `logs/OPEN-ITEMS.md` の「PLAN-030 のレビュー」行と、R-4 で許された行に打ち消し線 + ADR-098 / (5) PLAN-030 のステータスと §8 の回答欄を埋める。
完了条件: ADR-098 があり、OPEN-ITEMS・PLAN-030・`STATE.md`・`logs/CHANGELOG.md` が更新され、`logs/HANDOFF.md` が次の 1 件(PLAN-031 = ★E の修正 + 探索的パイロット FT の起草)になっている。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `plans/PLAN-030-shortest-path-to-first-ft.md`(**草案。決定 0 件**)。最初の FT の前に人間が決めるのは R-1〜R-4・H1-1〜H1-6・G1-1・G1-2 だけ、という案
- 振り分けは `logs/OPEN-ITEMS.md` の索引の未決 27 行(= 31 項目)+ 索引の外 12 項目。**案であって確定ではない**
- `STATE.md` は 399 行 / 56,963 バイト。`pytest code/tests/test_repo_hygiene.py` = 7 passed。全体の `pytest code/tests -q` = 1579 passed(その77。以後コード変更なし)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-030-shortest-path-to-first-ft.md`(全文 約 320 行。`grep -n '^## \|^### '` → `sed -n`)
- `logs/DECISIONS.md` の ADR-097(`grep -n '^## ADR-097' logs/DECISIONS.md`)
- `logs/OPEN-ITEMS.md` は索引の該当行だけ(`grep -n 'PLAN-030\|★F90\|凍結の段の前後\|順6 の結果の読み' logs/OPEN-ITEMS.md`)。**全文 cat しない**

## やってはいけないこと

- 表を見せる前に選択式の質問を出さない(ADR-090 の再発防止。ADR-097 決定6)
- R-1 の回答より前に、振り分けを確定扱いにしない。R-4 で許されていない行に打ち消し線を付けない
- `CLAUDE.md`・`Documents/` を書き換えない(規約の反映と P-3 の文書修正は段3 = PLAN-033)。GPU・実装に進まない
- PLAN-031 の中身(LoRA の値・シード数など)をこのセッションで決めない。値は人間(`CLAUDE.md` §8)

## 未解決 / 人間の承認待ち

- 新(その80): **PLAN-030 §8 の R-1〜R-4**
- 変わらず(PLAN-030 §4 で振り分け済み): ★探索的パイロット FT の LoRA 初期値・シード数 / ★E / ★前段 FT の前の診断 / ★E1 の TOST 境界・多重性 / ★前段 FT の成功基準・侵襲の閾値 /
  ★F104-c / `n_item` の実装 / ★F114 の実行先 / `cost.txt` / 停止中ポッド 8 本の terminate / ★`θ` の根拠 / Phase 1 の GPU 構成 / N5 / 監査(その76)の D2・C2・C3・C5 / 引用の最終確定
