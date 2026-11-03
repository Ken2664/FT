# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-03(その195)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN 完了(PLAN-048 I11 を実装し `完了`。`9f7c7b1`)+ context-guard(約 138k)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: 人間が選ぶ作業による — (A) を選ぶなら Sonnet(`10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」= RUNNER の定型実行)/ (B) を選ぶなら Opus(「設計判断・統計」= PLANNER)

---

**人間へ: 貼る前に、下の (A) / (B) のどちらか(または別の作業)を 1 行目に書き足してください。**書かれていなければ、エージェントは作業を始めずに聞くこと。

- **(A) RUNNER**: 順6 の測り直し(PLAN-045 I7)を起動する。**起動・push・G2-1 の承認は人間**(10 GPU 時間の上限と RunPod の課金。`CLAUDE.md` §2)。人間の承認が無ければ dry-run まで
- **(B) PLANNER**: 凍結前に要るものの 1 つ(例: PLAN-048 で外したリンク 3 本・ADR-060 のベイズの PLAN 草案)を起草する。どれにするかは人間

あなたは上で選ばれた役割です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

人間が選んだ (A) か (B) の 1 つ。(A) なら `infra/RUNPOD.md` §4 の手順と PLAN-045 I7 に従う。(B) なら `plans/PLAN-0XX-*.md` の草案を書き、問いと推奨を判断材料の表にして人間に諮る(ADR-097 決定6)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- PLAN-048 I11 を実装(`9f7c7b1`): `configs/primary.yaml` に `input.order6_dropped_cells: null`。`primary.py` は `gonogo.json` を読む経路で、`null` なら未決として止め、`fails` の和集合(主軸のセル)と違えば両側を出して止める。`[]` は「落とすセルは無い」で `null` と別
- `pytest code/tests -q` = 2695 passed(skip 0・R を通す 1 本を含む)。**PLAN-048 は `完了`**
- 実装の選択(PLAN-048 §11): 実データの経路も、`--order6-gonogo` と一覧の両方があれば、ほかの未決で止まる前に照合する

## 触ってよいファイル / 読むべき範囲

- `STATE.md` の「次のアクション」と `logs/OPEN-ITEMS.md` の該当行(`grep -n`)
- (A) `plans/PLAN-045-*.md` の I7・`infra/RUNPOD.md` §4 / (B) `plans/PLAN-048-primary-analysis-script.md` §3.2 の W9・W11 と ADR-138 決定1
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`

## やってはいけないこと

- `input.order6_dropped_cells`・`input.order6_gonogo`・`analysis_gate.threshold`・`tost.delta` に値を入れる(人間が凍結の場で決める)
- 人間の承認なしに pod を起動する・10 GPU 時間超のジョブを回す・push する
- `--simulate` / `--shuffle-labels` の p 値や判定を解釈する(`CLAUDE.md` §8)
- `git add -A`(未追跡の大きい結果がある)。コミットはファイルを名指しする

## 未解決 / 人間の承認待ち

- `results/primary/` の 2 run(その193 の `--simulate`・`--shuffle-labels`)をコミットするか
- 食い違い(CLAUDE.md §7.1): `code/analysis/frame.py` の冒頭と `gate_id_rates` の docstring が `primary.py` を「未実装」と書いている。直すかは人間
- 気づいたこと(判断なし): いまの `results/gonogo_order6/gonogo.json` の run は `condition` = `p2` で、主軸のセルに `fails` は無い(順6 の測り直しの後に在り処と一覧を決める)
- 順6 の測り直し(PLAN-045 I7)の起動 / `01cf60f` 以降の push と G2-1 承認 → S4 / 順6 の gonogo.json の在り処と落とすセルの確定した一覧 / N5 の閾値と門の順・TOST の Δ / 実データの frame での `--shuffle-labels` / 第 2 の尺度の手続き(S5)/ `id` の二重露出の感度解析 / R5(組 199)/ PLAN-043 §12 の判断 6 件 / REVIEW の R4 以下・C1/C2 / PLAN-048 で外したもの(リンク 3 本・ADR-060 のベイズ)の PLAN
