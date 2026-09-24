# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その81)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: PLAN 完了(PLAN-030 のレビュー R-1〜R-4 を ADR-098 に記録した)

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。ADR-095 決定1)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**段1 の PLAN = `plans/PLAN-031-*.md`(★E の修正 + 探索的パイロット FT)を起草する(草案。決定 0 件)。**
- 範囲は ADR-097 決定2 で決まっている: `p2` + `ident`、1〜2 シード、パイロット用プール、T1・T2・特異性対照。目的は実行可能性の確認(#4 / #5 / #5b / LoRA の値 / T2 へ転移するか / T1 に既知性の勾配があるか)。**効果量の推定には使わない**
- 中身: (1) ★E の修正の仕様(`torch.manual_seed` が `code/`・`infra/` に 0 件)/ (2) パイロット FT の config の形 / (3) Go/No-Go #4・#5・#5b を出すコード(いまの `code/analysis/gonogo.py` は #1〜#3 だけ)/
  (4) **記入欄 H1-1〜H1-6 と G1-1・G1-2**(PLAN-030 §3.2 の表)。各項目に**選択肢と判断材料**(効く ADR・PLAN・config・run)を並べる。**値は書かない**(LoRA の値・シード数は人間。`CLAUDE.md` §8)/
  (5) S3(ADR-055 決定2)の根拠の見直しの**材料だけ**(決定は凍結前でよい。PLAN-030 §4.2 の c)/ (6) PLAN-030 §6 の罠1〜3 への対策
- 起草の前に `ls plans/` で番号を確かめる
- 完了条件: PLAN-031 がある / `logs/OPEN-ITEMS.md` の索引に「PLAN-031 のレビュー」1 行 / `STATE.md`(旧ブロックは `logs/STATE-ARCHIVE.md` へ)・`logs/CHANGELOG.md` を更新 / `pytest code/tests/test_repo_hygiene.py` が通る / commit / `logs/HANDOFF.md` を次の 1 件(**PLAN-031 のレビュー = H1-1〜H1-6 を人間に聞く。表を先に見せる**)にする

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-098**: R-1 PLAN-030 §4 の振り分けを採る(**振り分けの正本は PLAN-030 §3・§4**。人間待ちの正本は OPEN-ITEMS のまま)/ R-2 `00_OVERVIEW.md:7` を段3(PLAN-033)に入れる /
  R-3 「判断材料を先に見せる」規約は案 A(`CLAUDE.md` §8 に 1 行 + 本文を `AGENTS.md`。**反映は段3**)/ R-4 整理候補 4 行に打ち消し線(済)
- `CLAUDE.md` は **213 行**で §10.2 の 200 行を超えている(PLAN-030 §5.2 の「守れる」は誤りだったので訂正した)。手当ては PLAN-033(案)
- `STATE.md` は 395 行 / 56,817 バイト。`pytest code/tests/test_repo_hygiene.py` を通した。全体の `pytest code/tests -q` = 1579 passed(その77。以後コード変更なし)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-030-shortest-path-to-first-ft.md` §2(前提と事実)・§3.2 の「段1」・§6(`grep -n '^## \|^### '` → `sed -n`)
- `logs/DECISIONS.md` の ADR-097 決定2・ADR-043 決定10・11(LoRA グリッド・動かす規則)・ADR-055 決定2(S3)(`grep -n '^## ADR-0XX'`)
- `logs/OPEN-ITEMS.md` の「★E」行と「F15 の扱い」(`grep -n '★E\*\*\|F15 の扱い'`)。**全文 cat しない**
- `code/train/{run,lora,settings,data}.py`・`configs/exp_order6b_pilot.yaml`・`configs/template.yaml`・`Documents/04_EXPERIMENT_PLAN.md` の Go/No-Go #4・#4b・#5・#5b・`plans/TEMPLATE.md`・`plans/PLAN-004` §3「順9 — 凍結とパイロット」

## やってはいけないこと

- LoRA の値・シード数・T1b / T3 を含めるか・`p2d` を足すかを**決めない / 推奨値を既定として config に書かない**(H1-2〜H1-5 は人間)
- パイロットの数値を効果量・Δ 5 行・検出力分析に使う設計を書かない(PLAN-030 §6 罠2。`pool_id: pilot` は主張の根拠に使わない)
- コードを書かない・GPU に進まない(実装は IMPLEMENTER。PLAN のレビューの後)。`CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない(段3)
- 長いツール出力を直に流さない。`cat > file` のように標準入力を待つコマンドを打たない(その81 に 1 回固まった)

## 未解決 / 人間の承認待ち

- 段1 で聞く: **H1-1〜H1-6**(PLAN-031 のレビュー)→ **G1-1**(GPU 承認)・**G1-2**(回し直しの承認の形)
- 段2・段3 は段1 と並べて進める: PLAN-032(診断。H2-1〜H2-5)/ PLAN-033(P-3 + `00_OVERVIEW.md:7` + 規約の案 A + `CLAUDE.md` を 200 行へ)
- `plans/PLAN-004` §3 順9 の未チェック項目「凍結を段階 E の前か後か」は ADR-097 決定2 で答えが出ているが未チェック(PLAN-031 で順9 に触れるときに扱ってよい)
- 変わらず: 停止中ポッド 8 本の terminate(G1-1 と同じ場を推奨)/ `cost.txt` / ★F104-c・`n_item` の実装・★F114 の実行先(段4 の後)/ ★`θ` の根拠 / N5 / 監査(その76)の D2・C2〜C5 / 引用の最終確定
