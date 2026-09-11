# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-11(その44)/ 直前セッションの役割: RUNNER (Opus)
直前セッションが終了した理由: **PLAN 完了**(順6 の GPU を完走・回収・コミット・ポッド停止)+ コンテキスト超過

---

あなたは PLANNER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**人間が順6 の結果を読むのを手伝う。**`logs/OPEN-ITEMS.md` の「順6 の結果の読み」「★F138」「PLAN-023 §6.1 の実装の読み」の 3 行を、
人間が決められる形(選択肢と、それぞれが事前登録のどこを変えるか)に並べる。**決めるのは人間。エージェントは解釈・判断しない**(`CLAUDE.md` §8)。

## 直前セッションで確定したこと

- 順6 の 5 run は回収・コミット済(`6d2ff9e`〜`3a41a50`)。数値は `STATE.md`「わかっていること ★順6」(すべて run_id 付き)
- Go/No-Go の表 = `results/gonogo_order6/gonogo.json`(R1)。突き合わせ = `runs/*_order6_r{2,3,4}/compare_vs_r1.json`
- ポッド `omjvbdanmbrzc8` は EXITED(terminate は人間)。predictions は開発機の `runs/*_order6_r*/predictions/`(git 管理外)にある

## 触ってよいファイル / 読むべき範囲

- `logs/OPEN-ITEMS.md`(`grep -n '順6 の結果の読み\|★F138\|PLAN-023 §6.1'`)/ `plans/PLAN-023` §6.1 / ADR-040(決定1〜3)/ ADR-047(決定2)/ ADR-076(決定1)
- 強制選択の項目生成は `code/eval/battery/t3_comparison.py`(閾値の置き方)と PLAN-001 §5.3

## やってはいけないこと

- 閾値(#1 = 0.02 / #2 = 0.70 / `θ` = 0.70)を変える / 落ちたセルの一覧を確定する / T1b・T3 を外すと決める / ★F138 を「設計の穴」と断定する
- GPU を回す(承認の対象外)/ push(頼まれていない)

## 未解決 / 人間の承認待ち

- 順6 の結果の読み / ★F138 / R4 の 16 件(ADR-040 決定3)/ `cost.txt` / ポッドの terminate / ★`θ` の根拠 / ★F104 / ★F114 の実行先 / Phase 1 本実験 40 run の GPU 構成 / N5(正本は `logs/OPEN-ITEMS.md`)
