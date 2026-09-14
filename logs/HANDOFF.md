# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-14(その57)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目完了**(PLAN-026 の I4 を実装・コミットした `5c2e54f`。I5 は定義を書いて人間に確かめる段が要るので、新しいセッションで始める)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その57 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I5 = R8 の当てはめ(CPU のみ。GPU 0)。2 段に分かれる。**

1. **先に「階段の位置」の操作的な定義を PLAN-026 §3.2.1 に書き、人間に確かめる**(ADR-079 決定1 が「実装の前に §3.2.1 に書き、テストで固定する」と要求している。**Phase 1 の R8(事前登録の対象)にも効く**ので、案と代替案・却下理由を書いたら `AskUserQuestion` で人間に選ばせる。`CLAUDE.md` §8)。
   定義に含めること: 何をもって「(準)完全分離」と判定するか / 階段の位置(交差点)をどの θ に置くか(例: 最後に y=0 の θ と最初に y=1 の θ の中点、など)/ 分離以外の理由で収束しないセルとの区別 / 単調でない階段の扱い
   - 採択されたら ADR(提案 エージェント / 採択 人間)を書く。**確認が取れなければ** `logs/OPEN-ITEMS.md` に行を立て、定義に依らない部分(下の 2 の揃え方 (a)・極性ごとの交差点・遠いオフセットの `correct`・除外件数)だけを実装する
2. **`code/analysis/r8_fit.py`(新規。名前は PLAN の例)+ テスト**。入力は I4 の掃引の run(`metrics.json` の `kind: threshold_sweep` + `predictions/threshold_sweep.<タスク型>.jsonl`)。出すもの(PLAN-026 §9 の I5 / ADR-079 決定1 / ADR-030 決定6):
   - 揃え方 (a): `y = 1` ⇔「和は閾値より小さい側だと答えた」(gt では `answer` が No、lt では Yes)。極性を同数混ぜたまま `logit P(y=1) = β0 + β1·θ` → `θ* = −β0/β1`・`β1`。**極性ごとの `θ*_gt`・`θ*_lt` とその開きを併記**
   - `β1 ≤ 0` のセル・分離以外で収束しないセルは除外し**件数を必ず出す** / 完全分離のセルは除外せず「階段」として別に数える
   - **遠いオフセットの `correct`**(`answer == truth`)を `θ ≤ −2` の側と `θ ≥ +3` の側で別に(PLAN-026 §5 (iv) = 264 行。基準 0.70 は G13 = ADR-079 決定6。**判定表は I11 なのでここでは値を出すだけ**)
   - `Δ̂ = θ*(条件) − θ*(ident)` は 2 run の差。順6b は素のモデル 1 本なので、**Δ̂ を出す形(2 run を受け取る)にするかは PLAN に読みとして書く**

**完了条件**: §3.2.1 に定義(人間の確認の記録つき。取れなければ OPEN-ITEMS の行)/ `r8_fit.py` が GPU の無いテストで —— **§3.2.1 の算術の例(内部の値 `t + Δ` の決定的なモデル → gt の切り替わり `Δ − 0.5`・lt `Δ + 0.5`・混ぜた交差点 `Δ`・`β1 > 0`)をそのままテストにして通る**(I12)/ lt の θ の符号を反転する旧い揃え方では `Δ̂ = 0` になることもテストで示す / 除外件数が出る / `pytest code/tests -q` が通る(直近の実測は **1106 passed**。その57)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I4 は実装済み**(`5c2e54f`。PLAN-026 §4.5 の「実装」)。入口は `python -m code.eval.run --config configs/exp_order6b_r8.yaml [--dry-run]`(`eval.threshold_sweep_arm` の宣言で `main` が掃引の経路に回す)
- **predictions の 1 行の欄**(`code/eval/run.py` の `threshold_sweep_record`): `item_id`・`category`・`task_type`・`polarity`・`sweep_cell`(併合セル = タスク型 × 既知性 × carry)・`coverage`・`carry`・`operands`・`t`・`threshold`(= t + θ)・`threshold_offset`(θ)・`prompt`・`response`・`answer`(判定規則の答え。同点は No)・`truth`・`yes_logp`・`no_logp`
- `metrics.json` の `threshold_sweep` 欄: 腕・θ の水準・タスク型・極性・組の数・`source_pool_pairs_hash`・`n_items_by_cell`({併合セル: {極性: {str(θ): n}}})・predictions の行数。**率は無い**
- **GPU の無いテストで掃引の run を作る手本**: `code/tests/test_threshold_sweep_run.py` の `pool_dirs`(module の fixture。パイロット用プールを組み直して R8・S を tmp に書く。約 8 秒)と `execute_sweep` / `rule_scorer`
- R8 の `--dry-run` は 8,160 項目(12 併合セル × 2 極性 × 17 θ × 20 組。組合せ論的な件数)。R8 の config で preflight の data_checks 7 件 PASS

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.2.1(78〜96 行)/ §5 (iv)(264 行)/ §6 の B・C(278・279 行)/ §9 の I5・I12(324 行・331 行)
- `logs/DECISIONS.md` ADR-079 決定1(5121〜5135 行)/ ADR-030 決定6(1296〜1312 行。打ち消し線つき)
- `code/eval/run.py` の `threshold_sweep_record`(1624 行)・`threshold_sweep_payload`(1713 行)は**読むだけ**
- `code/analysis/gonogo.py`(run ディレクトリの読み方・報告の形の前例。`grep -n '^def '` から)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0 があり statsmodels は無い。`infra/requirements.lock` は numpy 2.1.2 / scipy 1.18.1 / statsmodels 0.15.0(ポッド)。新しい依存を足す前に lock を確かめる

## やってはいけないこと

- 「階段の位置」の定義を人間の確認なしに確定する / ADR-030・ADR-079 の中身を変える
- I4 の記録の経路を変える(バグ修正を除く)/ 上位 k の欄を足す(I10)/ 判定表(I11)まで手を広げる / GPU
- 実験結果でない数値を文書に書く(テストの合成データの値を結果として書かない)
- プール・config・`data/raw/` を書き換える / main の push
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。**Bash の heredoc に長い日本語の Python を流さない** —— スクリプトは Write ツールで scratchpad に書いてから実行する。**CRLF の確かめは `grep -c $'\r'` を `"$(…)"` の中で使わない**(この Git Bash では CR ではなく全行を数える。Python で `b"\r\n"` を数える)

## 未解決 / 人間の承認待ち

- **「階段の位置」の定義**(このセッションで案を書いて聞く)
- **PLAN-026 §4.5(I4 の配線の読みと、その57 の実装で HANDOFF の設計から変えた所)に異議があるか** / **ADR-080 決定3(20 組を併合セルから取る)に異議があるか**(どちらも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I1〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
