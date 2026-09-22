# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-22(その67)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(context-guard が約 180k で警告。PLAN-027 の起草まで)

---

**★このセッションの最初に、人間に確かめることが 2 つある(下の「最初に人間に確かめること」)。**
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う。**`STATE.md` の `cat` 以外は
`grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## 最初に人間に確かめること

### (1) §5 の凍結 tag は打たれたか(**その67 の終了時点では打たれていない**)

その67 に人間が**「凍結してよい(私が打つ)」と決めた**が、`git tag --list` は空のままセッションが終わった。

```bash
git tag --list          # preregister-order6b があるか
```

- **無ければ**、人間に打ってもらう(**エージェントは打たない**。その66 の決定):
  `git tag -a preregister-order6b -m "PLAN-026 §5 の選び方を凍結(順6b の GPU 承認の前)"`
  凍結の対象 `plans/PLAN-026-order6b.md` §5 は commit `584e0ef` に入っている
- **打たれていたら**: `logs/CHANGELOG.md` と `STATE.md` に凍結の事実(tag 名・指している commit・日付)を記録する。
  次は **§11 の文面で GPU 承認**(run **7 本**・**15,626 項目・回**・約 1.7 時間 / 悲観側 2.5 時間 / 約 $1.9)。
  承認が下りたら **RUNNER** セッションを別に立てる(RunPod MCP は RUNNER のみ)

### (2) PLAN-027 §8 の H1〜H5(★F140 の規則と再採点の範囲)

**これが決まるまで PLAN-027 の実装に入らない**(`CLAUDE.md` §4 手順2 = 設計変更は人間のレビュー)。

```bash
sed -n "$(grep -n '^## 8\.' plans/PLAN-027-f140-parser-rescore.md | cut -d: -f1),+12p" plans/PLAN-027-f140-parser-rescore.md
```

- **H1(規則)が本体。**推奨は **C(最終行の最後の `is` の後ろ)**。A(`ANSWER_MARKERS` に `is`)は勧めない
- H2 再採点する run / H3 `rescore.py` の C3 定数 / H4 印の確認を CLI に入れるか / H5 `M*` は置き直さないか

## このセッションでやること(分岐のどれか 1 つだけ)

### (A) §5 が凍結され GPU も承認された場合 → **RUNNER**(別セッションを立てる)

`infra/RUNPOD.md` §4 の手順。**起動の前に、停止中ポッドを再開するか新しく立てるかを人間に確かめる。**
**ポッドでは pilot の `items.jsonl` / `train.jsonl` と掃引の `items.jsonl` を `configs/exp_order6b_pilot.yaml` 冒頭のコマンドで作り直す**(git に無い)。
7 本の順は preflight → B0 → R8 → ① → (d) → (c) → S-① → S-(d)。**(c) の入口だけ `python -m code.eval.calibration_run`**(他は `python -m code.eval.run`)。
**3 時間で打ち切って報告する。終わったらポッドを停止する。**

### (B) PLAN-027 の H1〜H5 が決まった場合 → **IMPLEMENTER**(GPU 0)

`plans/PLAN-027-f140-parser-rescore.md` §5 の手順 1〜6 をそのまま実装する。完了条件は §10。

1. `code/eval/parsers/base.py` に補助関数を 1 本足す(**`ANSWER_MARKERS` は触らない**)
2. `code/eval/parsers/numeric.py` の `parse` の**失敗時のみ**委譲する
3. `code/tests/test_parsers_numeric.py` に §3.3 の表 8 行を足す(**「A なら壊れる 3 例」を負例回帰として置く**)
4. `code/eval/rescore_run.py`(新規)= 本実行の run の再採点 CLI。**集計は `code/eval/run.py` の関数を再利用し書き直さない**
5. `code/tests/test_rescore_run.py`(新規)で §6.1 の C1〜C5
6. `pytest code/tests -q` → `logs/CHANGELOG.md` → **ADR-088**(提案 エージェント / 採択 人間)→ commit

### (C) どちらも決まらない場合 → **文書の追随**(GPU 0)

`Documents/06_THREATS.md`(★F138・★F139・PLAN-025 §3.6)/ `Documents/04_EXPERIMENT_PLAN.md` #1・#3 / ADR-047 実装ノート。
**加えて 1 行**: `plans/PLAN-026-order6b.md` §12 の ★F141 の行が「回す前に決める」のまま残っているが、
**実際は ADR-079 決定1(揃え方 (a)・完全分離 (a))と ADR-081(階段の位置 = `(L+U)/2`)で決着済**で `code/analysis/r8_fit.py` に実装がある。
**打ち消し線 + 決着先を付けるかは人間に確かめる**(その67 に報告したが未修正。**§5 には触らない**)。

## 直前セッション(その67)で確定したこと(ファイルに書き込み済み)

- **人間の回答: §5 は「凍結してよい(私が打つ)」/ このセッションは「GPU 0: ★F140 のパーサ」**
- **`plans/PLAN-027-f140-parser-rescore.md` を起草した**(草案。ADR-078 決定11 (b) の実装 PLAN)。
  **`code/` とテストは 1 バイトも変えていない。`pytest` も回していない**(変更が無いため)
- **読み取りだけで数えた事実**(回収済みの `predictions/` を候補規則で読み直しただけ。**パーサは未変更・モデルは呼んでいない**。
  **公式の遷移表は実装後に CLI が出す。これは実装前の見積りであり §6.1 C3 の期待値の出所である**):
  - 旧 `parse_fail` は **R1 2** [run:20260911_141547_order6_r1] / **R2 2** [run:20260911_160132_order6_r2] /
    **R3 2** [run:20260911_160937_order6_r3] / **R4 3** [run:20260911_161738_order6_r4] / **R5 0** [run:20260911_163337_order6_r5]。
    **候補 A/B/C のどれでも全部 correct に動く**
  - 順5 の再採点 run は 20,000 行中 旧 `parse_fail` **924** 件(PLAN-024 §1.8 の 22 + 902 と一致)。
    **A: correct 509 / other_error 92 / 残り 323 ・ B: 486 / 67 / 371 ・ C: 509 / 92 / 323** [run:20260910_215422_rescore_sweep_m]
  - **上位集合の違反は 3 候補とも 0 件**(この 6 run の範囲で)。**既存の `test_parsers_numeric.py` の事例
    (正例 6・負例 15)で挙動が変わったものも 3 候補とも 0 件**
- **★A を勧めない根拠**: 合成した境界事例で **`The answer is 7, which is correct.`(現行 7)/
  `The answer is 12. That is my final response.`(現行 12)/ `The answer is 5 and that is it.`(現行 5)の 3 例を `None` に壊す**。
  **B・C は「現行が `None` を返したときだけ働く」ので、上位集合であることがコードの形から言える**
- **B と C の差は順5 で 48 件**(B は `parse_fail` のまま / C は correct 23・other_error 25)。
  原因は (i) B の名詞表に `solution` が無い(`Therefore, the solution to the equation 6 + (-81) is -75.`)、
  (ii) C は `Since 36 is negative, ... : -75` のような別の `is` でも錨を打つ(**見た 2 例では結果として正しい値を拾えていた。2 例だけである**)
- **`STATE.md` の旧 4 ブロックは `logs/STATE-ARCHIVE.md`「その67」へ機械的に移した**(1 文字も削っていない)。**402 行 / 60,348 バイト**。`test_repo_hygiene.py` 7 passed

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-027-f140-parser-rescore.md` **§3**(測った事実)・**§4**(変更仕様)・**§5**(実装手順)・**§6**(再採点 CLI と C1〜C5)・**§8**(記入欄)・**§9**(リスク)
- `plans/PLAN-026-order6b.md` **§5**(凍結の対象)・**§11**(GPU 承認の文面)・**§12**(★F141 の行)
- `logs/OPEN-ITEMS.md` の「PLAN-027 §8 の H1〜H5」と「順6b(PLAN-026)の GPU 承認」の行
- `code/eval/parsers/numeric.py`(47 行)・`code/eval/parsers/base.py`・`code/eval/rescore.py`(759 行。**掃引専用**)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0 / torch 2.13.0+cpu / transformers 5.14.1。ruff / black は無い(行長 100 以下は Python の `len` で確認する)

## やってはいけないこと

- **§5 の凍結 tag をエージェントが打つ**(その66 に人間が「人間が打つ」と決めた)
- **PLAN-027 を H1〜H5 が埋まる前に実装する**(`CLAUDE.md` §4 手順2・§8)
- **`ANSWER_MARKERS` に `is` を足す**(候補 A。§3.3 で現行の 3 例を壊す。採るなら H1 で人間が明示的に選ぶ)
- 語形・Yes/No・CoT パーサに触る / **二値群の採点(ADR-047)に触る** / `M*` の置き直し / 元の `metrics.json` の書き換え
- **Go/No-Go の印・閾値(#1 の 0.02、#2 の 0.70)を変える** / 結果を解釈する(`CLAUDE.md` §8)/ main の push
- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プール・順6b の config を書き換える(ADR-078 決定2)
- **人間の承認なく GPU を起動する / RunPod のポッドを起動したまま放置する**(`CLAUDE.md` §2)
- **Python の `Path.write_text` で `STATE.md` や config・文書を書く(Windows で CRLF になる)。**必ず `write_bytes` で書く
- **`code/` と `code/tests/` は worktree が CRLF である**(`numeric.py` も `test_parsers_numeric.py` も CRLF)。
  **`plans/` `logs/` `STATE.md` は LF である。**スクリプトで編集するときは**元の改行コードを保って書き戻す**
- **長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- **CHANGELOG の日付見出しの括弧は ASCII の `(` `)` である**
- **`python -m code.eval.rescore` は Windows で `PYTHONIOENCODING=utf-8` が要る**(cp932 が「—」を符号化できない)
- 説明の根拠を確かめずに「原典どおり」と書く(その61)

## 未解決 / 人間の承認待ち

- **★§5 の凍結 tag(`preregister-order6b`)—— 承諾は出たが未作成。順6b の唯一のブロッカーである**
- **★PLAN-027 §8 の H1〜H5** —— 実装のブロッカー
- **★順6b より先に PLAN-027 の実装が入ると、PLAN-026 §5 の判定が新しいパーサで行われる。**
  §5 の値(0.70)は変わらないが **#1(`parse_fail < 0.02`)の実測は下がる方向に動く。これを人間に上げる**(PLAN-027 §9。§8 に項が無い)
- **PLAN-026 §12 の ★F141 の行**が「回す前に決める」のまま(実際は ADR-079 決定1 + ADR-081 で決着済)。修正の可否は人間
- PLAN-026 §4.5〜§4.14 の「実装の読み」/ ADR-080 決定3 に異議があるか(どれも `logs/OPEN-ITEMS.md` には行が無い)
- 順6b の GPU 承認(§5 の凍結の後。文面は PLAN-026 §11。**run は 7 本**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
