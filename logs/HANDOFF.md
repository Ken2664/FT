# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-22(その177)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN完了(PLAN-046 の実装の前に残っていた §5.6・§6.4 を人間に聞き ADR-133 に書いた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 実装(`10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)。統計の判断が出たら止めて PLANNER(Opus)へ

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。実装の前に skill `code-style` を読むこと。

## このセッションでやること(1つだけ)

**PLAN-046 §7 の I1〜I5 を実装し、`pytest code/tests -q` を通し、`--dry-run` とスモーク(各シート 1 表)で 1 表の時間を測って PLAN-046 §13 に書く。評価の本実行は起動しない(起動は人間)。**

- I1 天井の判定(§5 手順 1。6 セルのどれかが全シード・全項目で n/n か 0/n)を純粋関数で・単体テスト(n/n・0/n・n − 1/n・セルが欠ける表)
- I2 恒等リンクの LMM(`lmer`・ML)の当てはめ。**縮退の扱いは §5.6 = ADR-133 決定1**(ADR-059 の判定・閾値・縮退順序・床の `allFit` の 5 最適化・ペア単位。違いは当て直しの初期値が `theta` だけ)。使う最適化を明示して出力に残す。**`power_sim_fit.R` のロジットの経路は 1 バイトも変えない**
- I3 既存の 800 表に I1・I2 を当てる評価のスクリプト(`fits/` のロジットの結果を読み道ごとに集計・**§6.4 の G1・G2 の判定と CP95 を点ごとに出す**)。`frames/` を使う前に manifest と照合(§8 罠8)
- I4 `ceiling_probnull` の DGP(周辺確率が加法になる `eta` を数値で解く・解と残差を記録・config に書いて commit)・テスト(確率の尺度の真値が 0)
- I5 `pytest`・`--dry-run`・スモーク → commit → 人間に起動を聞く

## 直前セッションで確定したこと(ファイルに書き込み済み)

- ADR-133(`f5d7bea`。人間が 4 問とも推奨): §5.6 縮退 = ロジットの道と同じ / §6.4 G1 = `ceiling_probnull` の `L_05`・`L_50` のどちらかで分岐した手続き全体の無条件の棄却率(失敗・実施不能は非棄却・分母から除かない)の CP95 下端 > 0.075 なら閉じる / G2 = 全 10 点の各点で C の道の LMM の当てはめ失敗率の CP95 下端 > 0.10 なら閉じる / 検出力は記述だけ / 閉じたら C は採らない・開いても採否は人間
- PLAN-046 の設計(ADR-132): 天井の規則・恒等リンクの LMM の LRT df = 2・Wald 90% CI の IUT・Δ は決めず最小 Δ を保存・B は C が実施できないときだけ

## 触ってよいファイル / 読むべき範囲

- 読む: `plans/PLAN-046-ceiling-remedy.md` §5・§6・§7・§8(`grep -n '^## \|^### '` → `sed -n`)/ `Documents/05_STATISTICS.md` §3.2(行 196〜345 付近)
- 触ってよい: `code/analysis/`(新しいファイル推奨。`power_sim.py`・`ceiling_level.py` への追加は最小に)/ `code/analysis/power_sim_fit.R`(**ロジットの経路は不変**。LMM は別の関数かファイル)/ `code/tests/` / 新しい config(`configs/power_sim_ceiling_probnull.yaml` など)/ PLAN-046 §13 / `STATE.md` / `logs/CHANGELOG.md`

## やってはいけないこと

- `configs/power_sim.yaml`・`power_sim_ceiling.yaml`・run3 の `rng_seed` 20261008 の変更 / run3 の起動 / 評価の本実行の起動(人間)
- G1・G2 の閾値・縮退の閾値を変える。統計の判断(例: LMM の当てはめで ADR-059 の判定がそのまま当てはまらない箇所)が出たら止めて PLANNER へ
- `results/power_sim/ceiling/*/frames/` を `git add` する。`git add -A` を使わない
- C の採否・F8 の解釈を書く / `05_STATISTICS.md` の書き換え

## 未解決 / 人間の承認待ち

- 評価の起動 / C の採否(評価の後・別の ADR)/ 確率の尺度とロジットの TOST の Δ(凍結前)/ PLAN-045(R3)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2・R5
