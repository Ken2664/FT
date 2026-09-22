# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その70)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **PLAN 完了**(順6b の回収・コミット・ポッド停止まで終わった)+ コンテキスト超過(hook `context-guard` が約 12.1 万トークンで警告)

---

**★順6b は終わっている。ポッドは停止済み(`EXITED`)。GPU は 1 秒も動いていない。**
**★このセッションで GPU は要らない。RunPod MCP も要らない**(`CLAUDE.md` §10.2)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする**(`CLAUDE.md` §10.2)。

## このセッションでやること(**IMPLEMENTER**。1 つだけ)

**`plans/PLAN-027-f140-parser-rescore.md` §5 の手順1〜6 を実装する**(★F140 の規則 C。ADR-088 決定6)。
**順6b が終わったので着手できる**(決定6 は「順6b より先に main へ入れない」と書いていた。その条件は解けた)。

完了条件:
1. §5 の手順1〜6 を実装し、**`pytest code/tests -q` を通す**(直近の実測は **1514 passed**)
2. **§6 の再採点 CLI で順6b の run も読み直し、旧・新を並べて報告する**(**解釈は人間**)
3. `logs/CHANGELOG.md` に追記し、コミットする(コード規約は skill `code-style`)

**★決定1 の規則 C は `36 is negative` のような `is` でも錨を打つ。**ADR-088 のリスク欄が
「見た 2 例では正しく動いたが 2 例である」と書いている。**テストでここを厚くすること。**

## 直前セッション(その70)で確定したこと(ファイルに書き込み済み)

- **★順6b の 7 本は完走した**(`CHAIN_DONE [12:56:54Z]`)。**`PREFLIGHT_FAIL` / `RUN_FAIL` は 1 件も出ていない。**
  稼働 12:14:55Z → 12:56:54Z の **42 分**(§10 の見積り約 1.7 時間より短い)。**commit `664ea2f`**
- **★件数は PLAN-026 §4.14 の dry-run と 1 件も違わない**(合計 **15,626**)。run_id と件数の表は
  `STATE.md`「わかっていること **★順6b**」にある(**数値は run_id とセットでのみ書く**。`CLAUDE.md` §2)
- **★回収の検査 3 件はすべて通った**: **4 値の合計は全ブロックで 1.0**(B0 31 / ① 25 / (d) 11 ブロック)/
  **`items_sha256` は 3 プールの manifest と一致**(pilot `c5072f488607f6e9…` / r8 `05902c908a95dd80…` / s `97d763971b2b58fc…`)/
  **必須成果物は 7 本とも揃い、`git_diff.patch` は 7 本とも 0 バイト**(追跡ファイルの変更なし @ `b5838c0`)
- **★掃引 3 本(`kind: threshold_sweep`)と較正 1 本(`kind: calibration`)は 4 値分解を持たない。**
  **これは PLAN-026 §3.2・§4.5 読み2 の設計であって取りこぼしではない**(run の `log.txt` に同じ注記がある)
- **★判定表は出した** —— `results/order6b_select/order6b_select.json`。**T3・T1b とも「採る候補 = なし」。**
  **これは §5 を機械的に当てた出力であって採用でも解釈でもない**(ADR-078 決定2)。**採用と §6 の分岐の読みは人間**
- **★ポッド `jn8bink3rkkri7` は停止した**(`EXITED`。稼働 **4,373 秒 = 1.215 時間**)。
  `list-pods` で**所有する 8 本すべてが `EXITED`**。**`cost.txt` の記入と terminate は人間**
- **`STATE.md` は 420 行 / 59,887 バイト**(ADR-063 の目標は 400 行 / 60 KB。**バイトは収めたが行は 20 行超えている**)。
  **pytest `test_repo_hygiene.py` は 7 passed**(落ちる閾値は 700 行 / 90 KB)。
  移したもの(**捨てていない。`logs/STATE-ARCHIVE.md`「その70」にある**): その69 の 5 ブロック / pytest 件数の履歴 / 済んだ段の並び 2 本。
  **「旧 STATE.md の行のうち新 STATE.md にもアーカイブにも無い行」は 0 件**であることを確認済み

## 触ってよいファイル / 読むべき範囲

- **IMPLEMENTER**: `plans/PLAN-027-f140-parser-rescore.md` **§5**(実装手順)・**§6**(再採点 CLI)・**§8**(H1〜H6 の記入)/
  `logs/DECISIONS.md` の **ADR-088 決定1**(規則 C の形)・**決定6**(順序)/ skill `code-style`
- 既存の再採点 CLI は `code/eval/rescore.py`(**掃引の run 専用**。本実行の run は読めない —— そこを開けるのが PLAN-027 §6)
- 人間待ちの正本は `logs/OPEN-ITEMS.md`(**末尾にその70 の追記がある**)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0 / torch 2.13.0+cpu / transformers 5.14.1。
  ruff / black は無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- **★順6b の数値を解釈する**(`CLAUDE.md` §8)。**Go/No-Go の印・閾値(#1 の 0.02、#2 の 0.70)を変える**
- **★元の `metrics.json` を書き換える**(ADR-074 決定2)/ **`M*` を置き直す**(ADR-074 決定1)
- **凍結した `plans/PLAN-026-order6b.md` §5 に触る / tag を打ち直す**
- **`ANSWER_MARKERS` に `is` を足す**(候補 A。**人間は規則 C を選んだ**)/ 語形・Yes/No・CoT パーサに触る /
  二値群の採点(ADR-047)に触る
- **★ポッドを起動する**(このセッションでは GPU は要らない)/ **terminate する**(人間)
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**必ず `write_bytes` で書く
- **`code/` と `code/tests/` は worktree が CRLF である。`plans/` `logs/` `STATE.md` `Documents/` は LF である**
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **CHANGELOG の日付見出しの括弧は ASCII の `(` `)` である**
- **`python -m code.eval.rescore` は Windows で `PYTHONIOENCODING=utf-8` が要る**
- **main を push する**(その69 は bundle でポッドへ渡した。main は ahead のまま)

## 未解決 / 人間の承認待ち

- **★二値群 6 セルの判断**(`logs/OPEN-ITEMS.md` 索引 73 行目)。**材料は揃った** ——
  `results/order6b_select/order6b_select.json` と 7 本の `metrics.json`。**判定表は「T3・T1b とも採る候補なし」**
- **★F139 の (a)(記録だけ)か (c)(測り方を変える)か / G12(近接同点のために batch を替えるか)/
  G15(① を採る場合の T1 のアンカー)**(同 81 行目)
- **★`cost.txt` の記入**(順6b の 7 本。**1.215 時間 × $0.74/時**)/ **停止中ポッド 8 本の terminate**(全部 `EXITED`)
- **★`runs/preflight/` が未追跡のまま残っている**(`forced_choice_tokens.json` / `token_boundary.json`)。
  その69 の選択は「今は放置」。**順6b が終わったので改めて決められる**
- **★`STATE.md` が 420 行(目標 400 行)**。次に書き足すときは先にアーカイブへ移すこと(ADR-063 運用規約5)
- PLAN-026 §4.5〜§4.14 の「実装の読み」/ ADR-080 決定3 に異議があるか
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / Phase 1 本実験 40 run の GPU 構成 /
  引用の最終確定(PLAN-025 E7)/ N5 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
