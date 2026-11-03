# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-03(その194)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN 内の判断が完了(PLAN-048 §11 の選択 ①〜⑥ を人間が採否。ADR-138 追記)。次は実装で役割とモデルが変わる
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 次の作業は決まった仕様の実装(`10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。skill `code-style` を読むこと。

## このセッションでやること(1つだけ)

**PLAN-048 I11 を実装する**: `configs/primary.yaml` に `input.order6_dropped_cells: null` を足し、`code/analysis/primary.py` で `gonogo.json` を読む経路(実データ・`--frame-dir` 付きの `--shuffle-labels`)では、`null` なら `pending_decisions` に足して止め、`order6_dropped_cells`(`fails` の和集合)と宣言の一覧が集合として違えば両側を出して止める。`code/tests/test_primary.py` に PLAN-048 §5 I11 のテスト 5 種を足し、`pytest code/tests -q` を通す(R を通す 1 本は `-k one_real_fit` で別に)。PLAN-048 §9 の最後の項目・§11・CHANGELOG を書いてコミット。人間が別の作業を選んだらそちらを優先する

## 直前セッションで確定したこと(ファイルに書き込み済み)

- ADR-138 の追記(`logs/DECISIONS.md` の末尾): ①③④⑤⑥ は `5872175` の実装のまま採る。② は (b) に改める
- 仕様の正本は `plans/PLAN-048-primary-analysis-script.md` §5 の **I11**(`[]` は「確かめて落とすセルは無い」で `null` とは違う / `--simulate` と合成の shuffle は変えない / エージェントは一覧に値を入れない)
- PLAN-048 のステータスは `採択`(I11 の実装待ち)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-048-primary-analysis-script.md` §5 の I11・§9・§11(`grep -n 'I11\|^## 9\|^## 11'`)
- `code/analysis/primary.py`: `pending_decisions`(167 行付近)・`order6_dropped_cells`(287 行付近)・`build_targets`(670 行付近)
- `code/tests/test_primary.py`: `order6` を含むテスト(206・229・583 行付近)
- `configs/primary.yaml` の `input` 節
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`

## やってはいけないこと

- `input.order6_dropped_cells`・`input.order6_gonogo`・`analysis_gate.threshold`・`tost.delta` に値を入れる(人間が凍結の場で決める)
- 照合に `runs[].condition` の検査など PLAN に無い検査を足す(人間は (c) を選んでいない。足したくなったら止めて聞く)
- `power_sim_fit.R`・`configs/power_sim.yaml`・`ceiling.py` の規則の中身・`frame.py`・`rng_seed` 20261008 を変える
- `--simulate` / `--shuffle-labels` の p 値や判定を解釈する(`CLAUDE.md` §8)
- `git add -A`(未追跡の大きい結果がある)。コミットはファイルを名指しする

## 未解決 / 人間の承認待ち

- `results/primary/` の 2 run(その193 の `--simulate`・`--shuffle-labels`)をコミットするか
- 食い違い(CLAUDE.md §7.1): `code/analysis/frame.py` の冒頭と `gate_id_rates` の docstring が `primary.py` を「未実装」と書いている。直すかは人間
- 順6 の測り直し(PLAN-045 I7)の起動 / `01cf60f` 以降の push と G2-1 承認 → S4 / 順6 の gonogo.json の在り処と落とすセルの確定した一覧 / N5 の閾値と門の順・TOST の Δ / 実データの frame での `--shuffle-labels` / 第 2 の尺度の手続き(S5)/ `id` の二重露出の感度解析 / R5(組 199)/ PLAN-043 §12 の判断 6 件 / REVIEW の R4 以下・C1/C2 / PLAN-048 で外したもの(リンク 3 本・ADR-060 のベイズ)の PLAN
