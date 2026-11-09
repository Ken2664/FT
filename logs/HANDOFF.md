# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その206)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: HANDOFF の 1 つ(その205 の PLAN に無い選択 ①〜⑥ の採否)を済ませた
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 実装(ADR-140 追記 ① の I5。`10_CONTEXT_POLICY.md` §7)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。実装の前に skill `code-style` を読むこと。

## このセッションでやること(1つだけ)

**ADR-140 追記 ① の I5 を実装する**(`logs/DECISIONS.md` の ADR-140 の末尾「★追記 ①」が正本。`grep -n '追記 ①(2026-11-09 その206)' logs/DECISIONS.md`)。

- `code/analysis/primary.py`: `--shuffle-labels` は **`--frame-dir` を明示したときだけ**実 frame を読む。明示しなければ config に `input.frame_dir` があっても読まず、合成の入れ替え(`shuffle.source_target`)を回す。`build_targets` の `--shuffle-labels` の分岐と `run` の `frame_read`(meta の 2 欄)が同じ規則になるようにする(`resolve_frame_dir` の周り)。`--simulate` と実データの経路は変えない
- テスト: 本物の config で `--shuffle-labels`(`--frame-dir` なし)が合成で通り、meta の `frame_dir`・`frame_csv_sha256` が null / `--frame-dir` を渡すと frame を読んで記録する。その205 で合成の入れ替えのために null の config の写し(`config_file_without_frame` など)へ直したテストのうち、本物の config に戻せるものは戻す
- `configs/primary.yaml` 4 行目の `--shuffle-labels` の例の注釈を新しい動きに直す(値は変えない)
- `pytest code/tests -q`(前回 2717 passed)。CHANGELOG・STATE を更新してコミット

## 直前セッションで確定したこと

- 人間が ADR-140 追記 ① を採った(3 問とも推奨): ④ を改める(= I5)/ ①②③⑤⑥ は実装のまま
- いまのコードは実装のまま(本物の config で `--shuffle-labels` を回すと frame が無いので止まる)。`results/frame_exp_phase1_main/` は無い(本実験の run が無い)

## 触ってよいファイル / 読むべき範囲

- 書く: `code/analysis/primary.py`・`code/tests/test_primary.py`・`configs/primary.yaml`(4 行目付近の注釈のみ)・`logs/CHANGELOG.md`・`STATE.md`・`logs/STATE-ARCHIVE.md`・`logs/HANDOFF.md`
- 読む: `primary.py` の `resolve_frame_dir`(`:882` 付近)・`build_targets`・`run`、`test_primary.py` の `shuffle` を含むテスト(`grep -n shuffle`)
- 全文 `cat` しない

## やってはいけないこと

- ADR-138・ADR-139・ADR-140 の値や規則を動かす / `results/frame_exp_phase1_main/` を作る / `Documents/05_STATISTICS.md` を書き換える(事前登録。下の食い違いは人間待ち)/ `git add -A`(未追跡の大きい結果がある)/ push / pod の起動
- `frame.py:10` の docstring「未実装」を直す(人間待ち。気づいたら報告だけ)
- PLAN に無い選択をしたら黙って決めず、`logs/OPEN-ITEMS.md` に 1 行書いて人間の採否待ちにする

## 未解決 / 人間の承認待ち(STATE.md「次のアクション」が正本)

- `05_STATISTICS.md:1497-1501` の入れ替えの例は合成か実データかを読み分けられない(PLAN-016 §7-6 と同じ場で人間)
- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(`EXITED`)の扱い / push / `results/primary/` の 2 run のコミット / `frame.py:10` の docstring の食い違い / 実 frame ができたら ADR-139 追記 ① の一致の検査
- `01cf60f` 以降の push と G2-1 承認 → S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)
