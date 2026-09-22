# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その71)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-027 §5 の手順1〜6 + §6 の再採点・報告・コミットまで終わった)+ コンテキスト超過(hook `context-guard` が約 34.6 万トークンで警告)

---

**★GPU はこのセッションでも 1 秒も使っていない。ポッドは 8 本すべて `EXITED` のままである。**
**★次のセッションでも GPU は要らない。RunPod MCP も要らない**(`CLAUDE.md` §10.2)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする**(`CLAUDE.md` §10.2)。

## このセッションでやること

**★エージェントがやる作業は残っていない。次は人間の判断である**(`CLAUDE.md` §8)。
人間がまだ判断を下していない場合、このセッションは**判断の材料を出す係**になる。
勝手に採否・解釈を書かないこと。材料の所在は `logs/OPEN-ITEMS.md`(正本)と下の「未解決」。

人間から具体的な指示があればそれを 1 本だけ実行する。無い場合に**やってよい候補**(どれか 1 つ):

- **(a) `Documents/02_RELATED_WORK.md` / `refs.bib` の未検証文献の原典確認**(PLAN-025 E7。`CLAUDE.md` §3 の手順。**確定は人間**)
- **(b) `Documents/09_PAPER_PLAN.md` の再設計への追随の下書き**(貢献1 が「一貫性バッテリ G1–G6」のまま。**確定は人間**)
- **(c) `runs/preflight/` の未追跡ファイル 2 つ(`forced_choice_tokens.json` / `token_boundary.json`)の扱いを人間に諮る**

**★`code/analysis/primary.py` には着手しない**(N5 と ★G の決着待ち。先に書くと書き直しになる。`STATE.md`「Phase 0 に必要な段階」)。

## 直前セッション(その71)で確定したこと(ファイルに書き込み済み)

- **★PLAN-027 §5 の手順1〜6 を実装した**(commit `23131fc`)。**§10 の完了条件は 5 つとも埋まった**
- **★規則 C の「最終の非空行」の読み方を人間が選んだ**(**ADR-089 決定1**)——
  **「正規化後の全文の最後の `is`」**である(`normalize_text` が改行を空白へ畳むため)。
  **PLAN-027 §3 の数値(C 列 509/92/323・B 列 486/67/371・§3.4 の 48 件)はすべてこの読み方で測られていた。**
  生応答を改行で割る読み方では **508/76/340** になり、**17 行ずれる**(実測。[run:20260910_215422_rescore_sweep_m] の旧 parse_fail 924 件)
- **★9 本を再採点した**(`results/rescore_f140/summary.json`。表は `STATE.md`「★F140 の再採点」に run_id つき)——
  **C1 / C2 / C4 は 9 本すべて pass** / **C3 は順6 の 5 本と順5 の掃引が見積りと完全一致** /
  **★C5(Go/No-Go の印)は 1 つも動かなかった**(R1〜R4 と順6b B0 は 22 個、① は 20 個、(d) は 6 個)。
  **R5(T2 交差)だけは Go/No-Go の表を組めない**ので「人間に上げる」で記録した
- **★`pytest code/tests -q` → 1579 passed**(4 分 53 秒)。**旧 1514 + 新規 65**
- **★元の run の `metrics.json` / `predictions/` は 1 バイトも書き換えていない**(ADR-074 決定2)。
  `data/raw/`・プール・config・順6b の run の中身・凍結した PLAN-026 §5 と tag も 1 バイトも変えていない
- **`STATE.md` は 433 行 / 60,885 バイト**(目標 400 行 / 60 KB。**超えている**)。
  移したもの(**捨てていない。`logs/STATE-ARCHIVE.md`「その71」にある**): その70 の 4 ブロック /
  ★順5 の再採点(その40)の本文 / ★(e) の復号・その46・その47 の数え上げ。
  **「旧 STATE.md の行のうち新 STATE.md にもアーカイブにも無い行」は 0 件**であることを確認済み。
  **次に書き足す人は先にアーカイブへ移すこと**(ADR-063 運用規約5・6)

## 触ってよいファイル / 読むべき範囲

- 新しく入ったコード: `code/eval/parsers/base.py` の `closing_statement_integer` /
  `code/eval/parsers/numeric.py` の `parse` 手順4 / **`code/eval/rescore_run.py`(新規 836 行)** /
  `code/eval/rescore.py` の `EXPECTED_C3_TRANSITIONS`(**採点規則ごとに 2 組。`--parser-rule` で選ぶ**)
- 決定の正本: `logs/DECISIONS.md` の **ADR-089**(規則 C の錨の範囲)と **ADR-088**(規則 C・再採点の範囲・C3 の 2 組・C5)
- 人間待ちの正本は `logs/OPEN-ITEMS.md`。**★その70 の追記までが最新で、その71 の追記はまだ無い**
- **依存**: numpy 2.4.6 / scipy 1.18.0 / torch 2.13.0+cpu / transformers 5.14.1。
  ruff / black は無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- **★再採点の数値を解釈する / 採否を決める**(`CLAUDE.md` §8)。**印を置き直す**(ADR-088 決定4)/ **`M*` を置き直す**(決定5)
- **★「印が動かなかったから旧・新のどちらでもよい」と書く。**どちらを正本にするかは**人間が決める**(ADR-088 のリスク欄)
- **`ANSWER_MARKERS` に `is` を足す**(候補 A。**負例回帰テストが落ちる**)/ 語形・Yes/No・CoT パーサに触る /
  二値群の採点(ADR-047)に触る / `rescore.py` と `run.py` の集計の式を書き直す
- **元の run(`runs/20260911_*_order6_*` / `runs/20260922_12*_order6b_*` / `runs/20260910_104249_sweep_m`)に書き込む**
- **凍結した `plans/PLAN-026-order6b.md` §5 に触る / tag を打ち直す**
- **★ポッドを起動する**(GPU は要らない)/ **terminate する**(人間)
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**必ず `write_bytes` で書く
- **`code/` の一部は worktree が CRLF である**(`base.py` / `numeric.py` / `artifacts.py` / `test_parsers_numeric.py` /
  `test_run_dry_run.py`)。**`run.py` / `rescore.py` / `gonogo.py` は LF。**
  **書き換える前に `b"\r\n" in raw` で判定し、元の改行コードのまま書き戻すこと**(git は `.gitattributes` で LF に正規化する)
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **`python -m code.eval.rescore*` は Windows で `PYTHONIOENCODING=utf-8` が要る**
- **main を push する**(ahead のまま。その69 以降ずっと)

## 未解決 / 人間の承認待ち

- **★二値群 6 セルの判断**(`logs/OPEN-ITEMS.md` 索引 73 行目)。材料は
  `results/order6b_select/order6b_select.json`(**T3・T1b とも「採る候補なし」**)と 7 本の `metrics.json`
- **★★F140 の再採点をどう扱うか(新規)** —— **印は 1 つも動かなかった**(PLAN-024 §4.1 の見込みどおり)。
  **旧パーサの数値と再採点後の数値のどちらを正本にするかは人間**(ADR-088 のリスク欄)。
  材料は `results/rescore_f140/summary.json` と `STATE.md`「★F140 の再採点」
- **★F139 の (a)(記録だけ)か (c)(測り方を変える)か / G12 / G15**(同 81 行目)
- **★`cost.txt` の記入**(順6b の 7 本。1.215 時間 × $0.74/時)/ **停止中ポッド 8 本の terminate**(全部 `EXITED`)
- **★`runs/preflight/` が未追跡のまま残っている**(その69・その70・その71 とも「今は放置」)
- **★`STATE.md` が 433 行(目標 400 行)**。次に書き足すときは先にアーカイブへ移すこと(ADR-063 運用規約5)
- PLAN-026 §4.5〜§4.14 の「実装の読み」/ ADR-080 決定3 に異議があるか
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / Phase 1 本実験 40 run の GPU 構成 /
  引用の最終確定(PLAN-025 E7)/ N5 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
