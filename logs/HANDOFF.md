# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-24(その82)/ 直前セッションの役割: PLANNER (Opus 5.5)
直前セッションが終了した理由: PLAN 完了(段1 の PLAN-031 を起草した)

---

あなたは PLANNER です(**Opus で動いていることを確かめてから始めること**。ADR-095 決定1)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-031 のレビュー = H1-1〜H1-7 を人間に聞き、回答を ADR に記録する。**
- **聞く前に判断材料の表をチャットで見せる**(ADR-097 決定6)。材料は `plans/PLAN-031-seed-fix-and-pilot-ft.md` の
  §0 の 3 件(起草で見つけた事実)/ §2.2 の事実 a〜r のうち各問いに効くもの / §4 の各表 / §5(S3。H1-1b に直結)
- 聞き方: `AskUserQuestion` は 1 回 4 問まで。**H1-1a・H1-1b・H1-4・H1-7 は選択式**、**H1-2(LoRA の 5 値)・H1-3(シード数と値)は値なので自由記述か選択肢 + Other**、H1-5・H1-6 は選択式。
  H1-4 で (i) か (iv) なら (i-a)/(i-b) も聞く。H1-2 で B を選んだら値は次のセッション(原典の確認は subagent)
- **見立ての扱い**: PLAN-031 は H1-1・H1-4・H1-6・H1-7 にだけエージェントの見立てを書いた。**選択肢に「(推奨)」を付けるかは慎重に** ——
  ADR-095・097・098 のリスク欄が「推奨の付いた問いで人間が毎回推奨を選んだ」ことを記録している。**H1-2・H1-3・H1-5 には推奨を付けない**(値と条件の追加。`CLAUDE.md` §8)
- 回答の後: ADR-099 を `logs/DECISIONS.md` に(提案 エージェント (PLANNER, Opus 5.5) / 採択 人間。ADR-039 決定3)/ PLAN-031 §4 に回答欄を足しステータスを更新 /
  `logs/OPEN-ITEMS.md` の「PLAN-031 のレビュー」行(と、決着すれば「★探索的パイロット FT の LoRA 初期値・シード数」「★E」の行)に打ち消し線 + ADR 番号。**行は落とさない**
- 完了条件: ADR-099 がある / `STATE.md`(旧ブロックは `logs/STATE-ARCHIVE.md` へ)・`logs/CHANGELOG.md` を更新 / `pytest code/tests/test_repo_hygiene.py` が通る / commit /
  `logs/HANDOFF.md` を次の 1 件にする(**H1-2 が決まっていれば IMPLEMENTER (Sonnet) が PLAN-031 §3 を実装**。決まっていなければ H1-2 の案づくり)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `plans/PLAN-031-seed-fix-and-pilot-ft.md`(草案。決定 0 件)。**起草で見つけた事実 3 件**:
  (1) いまのコードでは「T1・T2・特異性対照だけ」をパイロット用プールで解けない(`code/eval/task_subset.py:134` と `code/eval/run.py:949`)→ H1-4 の (i)・(iv) は ADR-082 の門の変更(i-a)か別プール(i-b)が要る /
  (2) #4 の定義文が水準か差か・シードごとか平均かを決めていない → H1-7 を新設 /
  (3) peft 0.20.0 の `get_peft_model` の既定は `autocast_adapter_dtype=True`(bf16 のアダプタを fp32 に上げる。LoRA に効くかは未確認)→ `code/train/lora.py:451` の docstring と食い違いうる(H1-6)
- `plans/PLAN-004` §3 順9 の「凍結を段階 E の前か後か」にチェック(ADR-097 決定2)
- `STATE.md` は 396 行 / 57,335 バイト。`pytest code/tests/test_repo_hygiene.py` = 7 passed。全体の `pytest code/tests -q` = 1579 passed(その77。以後コード変更なし)
- **Python の `write_text` は Windows で CRLF を書く**(その82 に `test_handoff_documents_use_lf_only` が落ちた)。`.md` を Python で書き換えるときは `newline="\n"` を渡す

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-031-seed-fix-and-pilot-ft.md`(全体。370 行ほど。`grep -n '^## \|^### '` で節を出してから)
- `logs/DECISIONS.md` の末尾(ADR-098 の形を真似る。`tail -60`)/ ADR-055 決定2(S3)・ADR-043 決定10・11(`grep -n '^## ADR-0XX'`)
- `logs/OPEN-ITEMS.md` の「PLAN-031 のレビュー」「★探索的パイロット FT」「★E」の行(`grep -n`)。**全文 cat しない**

## やってはいけないこと

- **値を決めない / 推奨値を既定として書かない**(H1-2・H1-3・H1-5 は人間)。人間が値を書いたら、そのまま ADR と PLAN に転記する
- コードを書かない・config に値を書かない・GPU に進まない(実装は IMPLEMENTER。回答の記録の後)
- `CLAUDE.md`・`AGENTS.md`・`Documents/` を書き換えない(段3)
- パイロットの数値を効果量・Δ 5 行・検出力分析・E1 の境界に使う設計を書かない(PLAN-030 §6 罠2)
- 長いツール出力を直に流さない。`cat > file` のように標準入力を待つコマンドを打たない

## 未解決 / 人間の承認待ち

- このセッションで聞く: **H1-1〜H1-7**(PLAN-031 §4)。GPU の前(実装と dry-run の後): **G1-1**(GPU 承認。一括か二段か)・**G1-2**(ADR-043 決定11 の空欄 = 幅・衝突・上限・`learning_rate` の条件、凍結 tag を打つか)
- 段2・段3 は段1 と並べて進める: PLAN-032(診断。H2-1〜H2-5)/ PLAN-033(P-3 + `00_OVERVIEW.md:7` + 規約の案 A + `CLAUDE.md` を 200 行へ)
- S3(ADR-055 決定2)の根拠の見直しは**凍結前**(PLAN-031 §5 に材料。H1-1b の回答で形が変わる)
- 変わらず: 停止中ポッド 8 本の terminate(G1-1 と同じ場を推奨)/ `cost.txt` / ★F104-c・`n_item` の実装・★F114 の実行先(段4 の後)/ ★`θ` の根拠 / N5 / 監査(その76)の D2・C2〜C5 / 引用の最終確定
