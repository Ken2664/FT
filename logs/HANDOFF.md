# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-15(その171)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(context-guard。全 pytest が 84 分かかり、大きな出力で膨らんだ)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Sonnet — PLAN-044 の I5(R のスモーク・文書の記入)は実装・集計の行(`10_CONTEXT_POLICY.md` §7)。統計の判断が出たら止めて PLANNER へ

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**PLAN-044 の I5 の残りを済ませて閉じる。**完了の条件は次の 3 つ。

1. `configs/power_sim_ceiling.yaml` の**各シート 1 表**(8 枚)を、**本物の `power_sim_fit.R`(R 4.6.1・lme4 2.0.6)**で当てる。スクラッチパッドの `--out-dir` に `n_rep_stages` を [1] にした config の写しで回す(本番の `results/power_sim/ceiling/` は使わない・`--keep-frames` 不要)。**1 表の時間(秒)を記録**し、当てはめ失敗・`allFit` の段に着いたかを見る(記述だけ。解釈しない)。`Rscript` は PATH に無い(`resolve_rscript` が `C:/Program Files/R/R-*/bin/Rscript.exe` を探す)。`R_LIBS` は `lme4` の入る場所(`infra/` か STATE の R の節を `grep -n 'R_LIBS' STATE.md`)
2. PLAN-044 §11(スモークの行)・§13(スモークの時間の行)・`logs/CHANGELOG.md`・`STATE.md`(冒頭・3 ブロック。古い「その171」ブロックは `logs/STATE-ARCHIVE.md` へ。上限 60 KB に近い: 現在 58.6 KB)を更新して commit
3. **天井のシートの本実行は起動しない**(人間が決める)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- commit `214b3ab`(コード・config(L は null)・テスト)→ `33df8c1`(I3 の出力 `results/power_sim/ceiling_level/` と `L_05` = 5.3・`L_50` = 7.512 の転記。run_id `20261015_040148_ceiling_level`。**当てはめの前**)→ その後の文書 commit(STATE・CHANGELOG・PLAN-044 §11・§13 の一部・この HANDOFF)
- `pytest code/tests -q -k 'not smoke'` = 2554 passed, 11 deselected(**84 分かかる**。次は `code/tests/test_ceiling_probe.py` と `test_power_sim.py` だけを回せばよい。文書だけの変更なら全部は要らない)
- `power_sim.yaml` の経路は不変(smoke を偽の当てはめで HEAD と比べ、表と当てはめ結果は同一バイト)
- **構造上の読み**: PLAN-044 の「3 枚・8 点」は config では 8 枚・各 1 点(水準はシートの属性)。PLAN-044 §13 に記録済み。統計の中身は同じ
- 天井のシートは `--dry-run --workers 16` で 800 表・3.4〜5.7 時間(推算。R のスモークの実測で更新する)

## 触ってよいファイル / 読むべき範囲

- 読む: `configs/power_sim_ceiling.yaml`・`code/analysis/power_sim.py` の `run_ceiling_probe`(`grep -n 'def run_ceiling'`)・PLAN-044 §6.2・§11・§13
- 書く: PLAN-044 §11・§13・`logs/CHANGELOG.md`・`STATE.md`・`logs/STATE-ARCHIVE.md`。**コードは変えない**(スモークで不具合が見つかったら止めて報告)

## やってはいけないこと

- `power_sim_fit.R`・`configs/power_sim.yaml`・run3 の `rng_seed` 20261008 の変更 / `L_05`・`L_50` の変更(commit 済み。変えるなら新しい run)
- 天井のシートの本実行・夜用タスクの登録・push・tag・GPU
- スモークの数値を主張・効果量に使うこと(配線確認だけ。`CLAUDE.md` §2)・結果の解釈・手当ての設計
- 全 pytest を何度も回すこと(84 分。コンテキストと時間を食う)。出力は `tail` で

## 未解決 / 人間の承認待ち

- 天井のシートの起動(I5 の後に人間)→ ANALYST の記述 → 手当ての PLAN(人間が決める)/ PLAN-045(R3)の起草 / S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2・R5(凍結前)
