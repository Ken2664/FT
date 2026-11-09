# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その208)/ 直前セッションの役割: RUNNER 相当(人間が「次のアクション」1 を選んだ)
直前セッションが終了した理由: 人間が選んだ 1 つ(pod・push・`results/primary/` の 2 run・`frame.py:10`)を済ませた
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: 人間が選ぶ作業による。PLANNER(設計判断・凍結の場)なら Opus / IMPLEMENTER・RUNNER なら Sonnet(`10_CONTEXT_POLICY.md` §7)

---

あなたは、人間が指定した役割のセッションです。**役割が指定されていなければ作業を始めず、人間に
`STATE.md`「次のアクション」のどれをやるか聞くこと**。**最初の発言で、自分の実モデル名と、人間が選んだ
作業の推奨モデルとの一致・不一致を 1 行で述べること**。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること

**人間が `STATE.md`「次のアクション」から選んだ 1 つだけ**。エージェントが選ばない(`CLAUDE.md` §8)。候補:

- 0. 人間: `05_STATISTICS.md:1497-1501` の入れ替えの例(合成か実データか)の読み。PLAN-016 §7-6 と同じ場
- 1. ネットワークボリューム `r963j7swke` と HF トークンの扱い(未決)/ 実 frame ができたら ADR-139 追記 ① の一致の検査
- 2. G2-1 承認(push は済んだ)→ S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)

## 直前セッションで確定したこと

- pod `9matkiq0jozcgm`・`oorrti5on9opnb` を terminate した(`delete-pod` 204 × 2。直後の `list-pods` は 0 本)。ボリューム `r963j7swke`(EU-RO-1・50 GB)は残っている
- `results/primary/` の 2 run をコミットした。shuffle の run は `dc9ab92`・`dirty: true`・patch 0 B で、当時の `primary.py` は復元できない。2 本とも旧コードの run で、主張に使わない
- `code/analysis/frame.py:10` の docstring「未実装」を「PLAN-048 で実装」に直した(コメントだけ)。`pytest code/tests -q` 2719 passed
- main を `origin/main` に push した(`Ken2664/FT` は公開リポジトリ)

## 触ってよいファイル / 読むべき範囲

- 人間が選んだ作業の PLAN・ADR の該当節だけ(`grep -n` → `sed -n 'X,Yp'`。全文 `cat` しない)

## やってはいけないこと

- ADR-138・ADR-139・ADR-140 の値や規則を動かす / `results/frame_exp_phase1_main/` を作る / `Documents/05_STATISTICS.md` を書き換える(事前登録)/ `git add -A`(未追跡の大きい結果がある)/ push / pod の起動 / ボリュームの削除 — いずれも人間の指示なしに行わない

## 未解決 / 人間の承認待ち(STATE.md「次のアクション」が正本)

- 上の候補 0〜2、および凍結前の項目(STATE.md「次のアクション」項目 3)
- 食い違い(`CLAUDE.md` §7.1): `05_STATISTICS.md:1497-1501` の入れ替えの例 / `configs/power_sim.yaml` の P1 の係数のコメントと `build_profile`(差 1e-6)
