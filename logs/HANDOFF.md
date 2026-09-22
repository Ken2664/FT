# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その68)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の区切り**(人間の決定 4 件を記録し、文書を追随させた。実装には入らない)

---

**★§5 は凍結され(tag `preregister-order6b` → `e714f8a`)、順6b の GPU も承認された(ADR-088 決定7)。**
**★次にやることは 1 つに決まっている —— RUNNER が順6b を回す。**
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う。**`STATE.md` の `cat` 以外は
`grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(役割で分岐する)

### (A) **RUNNER** —— 順6b を回す(**これが本線。GPU 承認済み**)

**RunPod MCP を有効にしたセッションを立てる**(`CLAUDE.md` §10.2。RunPod MCP は RUNNER のみ)。
手順は `infra/RUNPOD.md` §4。**承認の中身は `logs/DECISIONS.md` の ADR-088 決定7**(= PLAN-026 §11 の文面)。

- **★起動の前に人間に確かめること(2 つ)**:
  1. **停止中のポッドを再開するか、新しく立てるか**
  2. **RTX 4090 SECURE の単価**(2026-09-10 時点で $0.74/時。**読み直す**)
- **ポッドでは pilot の `items.jsonl` / `train.jsonl` と掃引の `items.jsonl` を
  `configs/exp_order6b_pilot.yaml` 冒頭のコマンドで作り直す**(**git に無い**)
- **run は 7 本。順は preflight → B0 → R8 → ① → (d) → (c) → S-① → S-(d)。**
  件数は B0 1,640 / R8 8,160 / ① 1,440 / (d) 480 / (c) 306 / S-① 2,400 / S-(d) 1,200 = **合計 15,626**
- **★(c) の入口だけ `python -m code.eval.calibration_run`**(他は `python -m code.eval.run`)
- 見積り約 1.7 時間(悲観側 2.5 時間)。**★3 時間で打ち切って報告する**
- **終わったらポッドを停止する**(`infra/RUNPOD.md` §7)。**terminate は人間**
- run を開発機に回収してコミットする(`runs/*/metrics.json` と `runs/*/config.yaml` は必ず)

### (B) **IMPLEMENTER** —— PLAN-027 の実装(**★順6b が終わってから**。ADR-088 決定6)

**順6b が終わる前にこれを main へ入れない。**凍結した PLAN-026 §5 が「凍結時と違う測定器」で判定される。

`plans/PLAN-027-f140-parser-rescore.md` §5 の手順 1〜6 をそのまま実装する。完了条件は §10。
**§8 は人間が記入済み(ADR-088 決定1〜6)。規則は C に決まっている。**

1. `code/eval/parsers/base.py` に補助関数を 1 本足す(**`ANSWER_MARKERS` は触らない**)。
   **規則 C** = 現行の経路が `None` のときだけ、**最終の非空行の最後の `is` の後ろ**を `unanimous_integer` に掛ける
2. `code/eval/parsers/numeric.py` の `parse` の**失敗時のみ**委譲する
3. `code/tests/test_parsers_numeric.py` に §3.3 の表 8 行を足す(**「A なら壊れる 3 例」を負例回帰として置く**)
4. `code/eval/rescore_run.py`(新規)= 本実行の run の再採点 CLI。**集計は `code/eval/run.py` の関数を再利用し書き直さない**。
   **C5(印の一致)は CLI の中で `gonogo` を呼んで `checks` に書く**(ADR-088 決定4)
5. `code/eval/rescore.py` の `EXPECTED_C3_TRANSITIONS` を **2 組**にし引数で選べるようにする(ADR-088 決定3。**集計の式は変えない**)
6. `code/tests/test_rescore_run.py`(新規)で §6.1 の C1〜C5
7. 再採点は **順6 R1〜R5 + 順5 の掃引の 6 本**(ADR-088 決定2)。**順6b の run も読み直し、旧・新を並べて報告する**
8. `pytest code/tests -q` → `logs/CHANGELOG.md` → **ADR-089**(ADR-088 の実装記録)→ commit

## 直前セッション(その68)で確定したこと(ファイルに書き込み済み)

- **★§5 の凍結 tag は打たれていた** —— `preregister-order6b`(注釈付き。人間が 2026-09-22 17:18:08 +0900 に作成 → `e714f8a`)。
  **`git diff 584e0ef e714f8a -- plans/PLAN-026-order6b.md` は空**で、凍結の対象 §5 は承諾時と 1 バイトも違わない
- **★人間が 4 問を選択式で決めた(ADR-088。4 問とも推奨)**:
  **H1 = 規則 C** / **H2 = (a) 順6 R1〜R5 + 順5 の掃引の 6 本** / **H3 = (a) `EXPECTED_C3_TRANSITIONS` を 2 組** /
  **H4 = (a) `rescore_run.py` が `gonogo` を呼ぶ** / **H5 = (a) `M*` は置き直さない** /
  **★H6(新設)= 順6b を先に回す** / **★順6b の GPU を §11 の文面どおり承認** / **★F141 の行を直す**
- **★その68 に読み直した事実(実装の前に効く)**: PLAN-026 §5 の合格条件のうち
  **パーサが触るのは (iii) だけ**である —— (i) #2・(ii) #3・(iv) 掃引は**すべて二値群の強制選択でパーサを通らない**(ADR-047)。
  **(iii) は C1(① 前置き)のときだけ**掛かり、新パーサは**緩む方向にだけ**動く。
  **C1 は §5 の表の最後なので C0・C3・C2 が全部落ちたときにだけ効く**
- **文書の追随を済ませた**: `Documents/06_THREATS.md`(**T14 に ★F138・★F139 の実測 / T16 を新設**)/
  `Documents/04_EXPERIMENT_PLAN.md`(**#1 の読み方・#3 の参照線**)/ **ADR-047 実装ノート 9**(★F139)
- **`plans/PLAN-026-order6b.md` §12 の ★F141 の行**に打ち消し線 + 決着先を付けた(**§5 は 1 バイトも触っていない**)
- `pytest code/tests -q` → **1514 passed**(2026-09-22 その68 実測。`code/` は未変更)。`test_repo_hygiene.py` 7 passed
- `STATE.md` は **401 行 / 60,417 バイト**。旧ブロック 5 つは `logs/STATE-ARCHIVE.md`「その68」へ機械的に移した
  (**失われた行 0 件をスクリプトで確認した**)

## 触ってよいファイル / 読むべき範囲

- **RUNNER**: `infra/RUNPOD.md` §4・§7 / `plans/PLAN-026-order6b.md` **§10**(見積り)・**§11**(承認の文面)/
  `configs/exp_order6b_*.yaml`(**7 本。書き換えない**)/ `logs/DECISIONS.md` の **ADR-088 決定7**
- **IMPLEMENTER**: `plans/PLAN-027-f140-parser-rescore.md` **§3**(測った事実)・**§4**(変更仕様。規則 C)・
  **§5**(実装手順)・**§6**(再採点 CLI と C1〜C5)・**§8**(記入済み)・**§9**(リスク)/
  `code/eval/parsers/numeric.py`(47 行)・`code/eval/parsers/base.py`・`code/eval/rescore.py`(759 行。**掃引専用**)
- 人間待ちの正本は `logs/OPEN-ITEMS.md`
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0 / torch 2.13.0+cpu / transformers 5.14.1。ruff / black は無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- **★順6b より先に PLAN-027 の実装を main へ入れる**(ADR-088 決定6)
- **★人間の承認なくポッドを起動する / 停止中ポッドの再開か新規かを確かめずに起動する / ポッドを起動したまま放置する**(`CLAUDE.md` §2)
- **凍結した `plans/PLAN-026-order6b.md` §5 に触る / tag を打ち直す**
- **`ANSWER_MARKERS` に `is` を足す**(候補 A。§3.3 で現行の 3 例を壊す。**人間は C を選んだ**)
- 語形・Yes/No・CoT パーサに触る / **二値群の採点(ADR-047)に触る** / `M*` の置き直し / 元の `metrics.json` の書き換え
- **Go/No-Go の印・閾値(#1 の 0.02、#2 の 0.70)を変える** / 結果を解釈する(`CLAUDE.md` §8)/ main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プール・順6b の config を書き換える(ADR-078 決定2)
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**必ず `write_bytes` で書く
- **`code/` と `code/tests/` は worktree が CRLF である**(`numeric.py` も `test_parsers_numeric.py` も CRLF)。
  **`plans/` `logs/` `STATE.md` `Documents/` は LF である。**スクリプトで編集するときは**元の改行コードを保って書き戻す**
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **CHANGELOG の日付見出しの括弧は ASCII の `(` `)` である**
- **`python -m code.eval.rescore` は Windows で `PYTHONIOENCODING=utf-8` が要る**(cp932 が「—」を符号化できない)
- 説明の根拠を確かめずに「原典どおり」と書く(その61)

## 未解決 / 人間の承認待ち

- **★`runs/preflight/` が未追跡のまま残っている**(`forced_choice_tokens.json` / `token_boundary.json`。9/22 15:04)。
  その67 の引き継ぎに記載が無い。**commit するか・消すか・放置かを人間に確かめる**(その68 は触っていない)
- **★順6b の後に人間が決めるもの**: 二値群 6 セルの判断 / ★F139 の (a)(記録だけ)か (c)(測り方を変える)か /
  G12(近接同点のために batch を替えるか)/ G15(① を採る場合の T1 のアンカー)
- **★順6b を回す時点でどちらのコードが入っているか**が、順6b の採点に効く(ADR-088 決定6 で「旧パーサ」に決めた)
- PLAN-026 §4.5〜§4.14 の「実装の読み」/ ADR-080 決定3 に異議があるか(どれも `logs/OPEN-ITEMS.md` には行が無い)
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 /
  引用の最終確定(PLAN-025 E7)/ N5 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7`(正本は `logs/OPEN-ITEMS.md`)
