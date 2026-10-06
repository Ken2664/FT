# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-06 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(context-guard 約 128k)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — 設計判断と統計(PLAN-042 の採否・閾値の判断材料。`10_CONTEXT_POLICY.md` §7 の「設計判断・統計」の行)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

`plans/PLAN-042-fit-failure-diagnosis.md` の §5「先に決めること」4 点と §2 の閾値について、**判断材料の表(選択肢・推奨・理由)をチャットで先に示し**、
`AskUserQuestion` で人間に決めてもらう。決まったら ADR を書き、PLAN-042 のステータスを更新し、`logs/OPEN-ITEMS.md` の
「★run2 の門と当てはめ失敗(PLAN-042)」の行に決着を書いて commit する。**実装・診断の実行はしない**(採択の後の IMPLEMENTER の仕事)。

## 直前セッションで確定したこと

- run `20261005_120003_power_sim_t1t2`(`results/power_sim/run2`)の 1 段目は 06:00 に止められた。門の 2 枚(`misspecification`・`misspecification_seed_subspace`)は 100 反復とも揃い、ADR-124 D2' の規則で**門は閉じる**(`tau` 0.25 / 0.5 の CP95 下端 0.152〜0.248 > 0.075)。**棄却のほとんどは当てはめ失敗を棄却に数えた分**(数値の正本は `results/power_sim/run2/exploratory/stage1_interim.json`。要約は `STATE.md`「いま何をしているか」)
- 読みは案のみ(PLAN-042 §1)。確定していない
- `infra/power_sim_night/stop_night.ps1:66` の数え方は 1 段浅い(表示だけの不具合。未修正)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-042-fit-failure-diagnosis.md`(全文。短い)
- `results/power_sim/run2/exploratory/stage1_interim.json`(`jq` か `python` でキーを絞って読む)
- `logs/DECISIONS.md` の ADR-059・ADR-124・ADR-125(`grep -n` で節を特定)/ `plans/PLAN-041-primary-random-structure-review.md` §3.3 罠2

## やってはいけないこと

- 失敗の定義(ADR-059)・数え方(ADR-124 D2')・`configs/power_sim.yaml` を変える(門を見た後の変更になる。決めるのは人間で、変えるなら旧文・理由・日付を残す)
- `results/power_sim/run2/*/fits/` を全文読む(846 本。集計は `stage1_interim.py` を使う)
- 夜用タスクの登録 / 削除・run2 の再開(人間の操作)

## 未解決 / 人間の承認待ち

- PLAN-042 の採否・範囲・§2 の閾値 / 今夜の夜用タスク(per_cell の残り 154 本 → 門で止まる)/ 診断の前に P1 を回すか(`logs/OPEN-ITEMS.md` の行)
- `results/power_sim/run2/misspecification_seed_per_cell/frames/` は未追跡のまま(再開すると消費される)
