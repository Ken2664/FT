# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-03(その193)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN 完了(PLAN-048 I1〜I10 を実装しコミット `5872175`。context-guard 約 262k で切る)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Opus — 次の作業は人間への判断材料の提示(`10_CONTEXT_POLICY.md` §7 の「設計判断・統計・解釈」の行)。実装の残りは無い

---

次の作業は **人間が決める**。最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから、`STATE.md` の「次のアクション」を人間に示し、どれにするか聞くこと(役割は選ばれた作業で決まる)。

## このセッションでやること(1つだけ)

**人間に PLAN-048 §11 の「PLAN に書いていなかった選択」6 点を判断材料の表にして示し、採否を聞く**(ADR-097 決定6。推奨を先頭に理由付きで)。採択されたら ADR-138 に追記する(提案者 = エージェント (Sonnet 5.5) / 採択者 = 人間を分ける)。人間が別の作業(順6 の測り直しの起動など)を選んだら、そちらを優先する

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `5872175`: `configs/primary.yaml` / `code/analysis/primary.py` / `code/tests/test_primary.py`(45 本)。`pytest code/tests -q` = 2685 passed(R を通す 1 本は `-k one_real_fit` で別に通過・35.75 秒)
- R の `qr()$rank` と Python の df が 6 セルの 46 部分集合で一致(`test_the_python_rank_agrees_with_rs_qr_rank…`)
- `--simulate`(run `20261103_051849_primary_t1t2_simulate`・約 9 分)と `--shuffle-labels --seed 0`(run `20261103_051849_primary_t1t2_shuffle`・276 秒)が最後まで走り、判定はどちらも `実施可`。**合成の配線の確認であり、結果の読みはしていない**。`results/primary/` の 2 run は**未コミット**(コミットするかは人間)
- PLAN-048 は `完了`(§9・§11・`OPEN-ITEMS.md` の行を更新済み)。STATE.md の 3 ブロックは差し替え済み(旧ブロックは `logs/STATE-ARCHIVE.md` の「その192」の節)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-048-primary-analysis-script.md` §11 の末尾(選択 ①〜⑥)/ `logs/DECISIONS.md` の ADR-138(`grep -n '^## ADR-138'`)/ `STATE.md` の「次のアクション」
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`

## やってはいけないこと

- `configs/primary.yaml` の `analysis_gate.threshold`・`tost.delta`・`input.order6_gonogo` に値を入れる(人間が凍結の場で決める。ADR-138 決定3)
- `--simulate` / `--shuffle-labels` の p 値や判定を解釈する(`CLAUDE.md` §8)
- `power_sim_fit.R`・`configs/power_sim.yaml`・`ceiling.py` の規則の中身・`rng_seed` 20261008 を変える
- `git add -A`(未追跡の大きい結果がある)。コミットはファイルを名指しする
- PLAN-048 で外したもの(リンク 3 本・第 2 の尺度・ADR-060 のベイズ・#5b・`id` の二重露出)を実装する

## 未解決 / 人間の承認待ち

- **PLAN-048 §11 の選択 ①〜⑥**: ① `input.order6_gonogo` を `null`(実データの実行が止まる項目が 2 → 3 つ)② 順6 の `gonogo.json` は `runs[].cells[].fails` の和集合 ③ 閾値が入っても門の順が未決なので止める ④ `--shuffle-labels` は `--frame-dir` が無ければ合成 P1 ⑤ 報告は対象ごとの節に固定の表 ⑥ `ceiling_rule` は残ったセルを 1 つずつ宣言して呼ぶ
- **食い違い(CLAUDE.md §7.1)**: `code/analysis/frame.py` の冒頭と `gate_id_rates` の docstring が `primary.py` を「未実装」と書いている(コードの docstring なので触っていない)。直すかは人間
- 順6 の測り直し(PLAN-045 I7)の起動 / `01cf60f` 以降の push と G2-1 承認 → S4 / N5 の閾値と門の順・TOST の Δ・順6 の gonogo.json の在り処 / 第 2 の尺度の手続き(S5)/ `id` の二重露出の感度解析 / R5(組 199)/ PLAN-043 §12 の判断 6 件 / REVIEW の R4 以下・C1/C2 / PLAN-048 で外したもの(リンク 3 本・ADR-060 のベイズ)の PLAN
