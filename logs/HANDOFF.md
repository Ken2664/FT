# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-23(その181)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN完了(PLAN-045 を起草し ADR-134 で採択)+ コンテキスト超過の警告
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — PLAN-045 I1〜I6 は実装(`10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)。**ただし下の「分岐」で ANALYST になる場合は Opus**

---

あなたは IMPLEMENTER です(分岐: 下記の 2 つの出力が揃っていれば ANALYST)。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。

## ★probnull の生成は途中で止まっている(その181 で確認)

- `results/power_sim/ceiling_probnull/ceiling_probnull_L05` は fits 100/100(2026-10-22 22:22 JST に完了)/ `ceiling_probnull_L50` は fits 0(manifest 00〜04 だけ)。pid 31768 は無く、ログは 0 バイト
- **再開は人間が決める**(同じコマンドで再開できる。`invocations.jsonl` に追記される): `python -m code.analysis.power_sim --config configs/power_sim_ceiling_probnull.yaml --out-dir results/power_sim/ceiling_probnull --through-stage 1 --keep-frames --workers 16` → 評価 `python -m code.analysis.ceiling_remedy --config configs/ceiling_remedy.yaml --out-dir results/ceiling_remedy --workers 16`

## 分岐(最初に 1 回だけ確かめる)

```bash
for d in results/power_sim/ceiling_probnull/*/; do echo "$d $(ls $d/fits 2>/dev/null | wc -l)"; done; ls results/ceiling_remedy 2>&1 | head -3
```

- **L50 が 100 未満 / `results/ceiling_remedy` が無い(既定)**: IMPLEMENTER として下の「やること」(PLAN-045)。人間が別の端末で再開しているかもしれない(触らない)
- **両方揃っている**: ANALYST(Opus)。PLAN-046 §6.1 の量を公式 summary から記述だけ・G1・G2 を機械的に(§6.4)。解釈・C の採否は書かない

## このセッションでやること(1つだけ)

**PLAN-045 I1〜I6 を実装し、`pytest code/tests -q` を通して commit する**(`plans/PLAN-045-interp-mirror-filter.md` §5。ADR-134)。I7(順6 の測り直し)は GPU なので起動しない(人間)。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `620238e`: PLAN-045 草案。§3 に組合せ論的な計数(現行の主プールの割当を 42 セルすべて再現。`mirror_in_K` 真は `interp` T1 14/80・T2 18/80 / `id` T1 21/80・T2 26/80 / フィルタ後の `interp` 供給 carry 443・nocarry 1,568 で 42 セル全部埋まる / `id`・`extrap_magnitude` の割当は不変 / `interp` はほぼ全部入れ替わる T1 76/80・T2 79/80)。**I5 で manifest に同じ数が出ることを確かめる**
- `5fe0295`: **ADR-134**(5 問とも推奨 (a)): 範囲 = 主プールの全 `interp` セル(T1・T2・T1b・T3・特異性対照)+ T1c の先頭の組 / 母集団から除いてから引く(`fill_cells`・`label_coverage`・`label_main_coverage` は不変。config の欄で入り切り、主の config だけ真)/ `mirror_in_K := a ≠ b かつ (b, a) ∈ K` を `frame.py` が実行時に付け、manifest にセルごとの件数 / `id` の二重露出は記録と感度解析だけ / 順6 は作り直した主プールで 1 run(人間が起動)

## 触ってよいファイル / 読むべき範囲

- `code/data_gen/pool.py`・`eval_pool.py`(`fill_candidates`)・`composition_pool.py`・`code/analysis/frame.py`・`configs/exp_phase1_main.yaml`・T1c の主の config(`configs/exp_t1c_main.yaml`)・`data/generated/battery/main/`・`main_t2_cross/`・`code/tests/`・PLAN-001/002 の `interp` の注・PLAN-045 §11
- 先に skill `code-style` を読む。ADR-134 は `grep -n '^## ADR-134' logs/DECISIONS.md` → `sed -n`

## やってはいけないこと

- **パイロットのプール(`data/generated/battery/pilot/` ほか)を変える**(バイト一致をテストで固定する。PLAN-045 罠1)/ 被覆ラベルの定義を変える(罠2)/ K・FT データを変える
- probnull の再開・評価・順6 の測り直しを起動する(人間)/ `05_STATISTICS.md` の書き換え
- `results/power_sim/ceiling/*/frames/` を `git add` する。`git add -A` を使わない

## 未解決 / 人間の承認待ち

- probnull の再開と評価の起動 / C の採否(評価の後・別の ADR)/ 確率の尺度の TOST の Δ(凍結前)/ 順6 の測り直しの起動(PLAN-045 I7)/ `id` の二重露出の感度解析の事前登録(凍結前)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2・R5
