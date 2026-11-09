# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その207)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: HANDOFF の 1 つ(ADR-140 追記 ① の I5)を済ませた
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: 人間が選ぶ作業による。PLANNER(設計判断・凍結の場)なら Opus / IMPLEMENTER・RUNNER なら Sonnet(`10_CONTEXT_POLICY.md` §7)

---

あなたは、人間が指定した役割のセッションです。**役割が指定されていなければ作業を始めず、人間に
`STATE.md`「次のアクション」のどれをやるか聞くこと**。**最初の発言で、自分の実モデル名と、人間が選んだ
作業の推奨モデルとの一致・不一致を 1 行で述べること**。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること

**人間が `STATE.md`「次のアクション」から選んだ 1 つだけ**。エージェントが選ばない(`CLAUDE.md` §8)。候補:

- 0. 人間: `05_STATISTICS.md:1497-1501` の入れ替えの例(合成か実データか)の読み。PLAN-016 §7-6 と同じ場
- 1. pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push / `results/primary/` の 2 run のコミット / `frame.py:10` の docstring「未実装」の食い違い
- 2. `01cf60f` 以降の push と G2-1 承認 → S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)

## 直前セッションで確定したこと

- **ADR-140 追記 ① の I5 を実装した**(`code/analysis/primary.py` の `resolve_frame_dir`): `--shuffle-labels` は `--frame-dir` を明示したときだけ実 frame を読む。既定は合成。`build_targets` と `run` の meta(`frame_dir`・`frame_csv_sha256`)は同じ規則
- `pytest code/tests -q` 2719 passed(前回 2717 + 新 2)。`configs/primary.yaml` は冒頭のコマンド例の注釈だけ直した(値は不変)
- `results/frame_exp_phase1_main/` は無い(本実験の run が無い)。ADR-139 追記 ① の一致の検査(frame.csv から数えた門の量 = manifest の `gate_id_by_task`)は実 frame ができるまで未検証

## 触ってよいファイル / 読むべき範囲

- 人間が選んだ作業の PLAN・ADR の該当節だけ(`grep -n` → `sed -n 'X,Yp'`。全文 `cat` しない)

## やってはいけないこと

- ADR-138・ADR-139・ADR-140 の値や規則を動かす / `results/frame_exp_phase1_main/` を作る / `Documents/05_STATISTICS.md` を書き換える(事前登録)/ `git add -A`(未追跡の大きい結果がある)/ push / pod の起動 — いずれも人間の指示なしに行わない
- `frame.py:10` の docstring を直す(人間待ち)

## 未解決 / 人間の承認待ち(STATE.md「次のアクション」が正本)

- 上の候補 0〜2、および凍結前の項目(STATE.md「次のアクション」項目 3)
- 食い違い(`CLAUDE.md` §7.1): `05_STATISTICS.md:1497-1501` の入れ替えの例 / `frame.py:10` の docstring / `configs/power_sim.yaml` の P1 の係数のコメントと `build_profile`(差 1e-6)
