# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-08(その202)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN完了(PLAN-049 I2〜I5 を実装・`pytest code/tests -q` 2713 passed・commit)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Opus — 設計判断(PLAN-049 §11 の選択 ①〜⑧ を人間に諮る)。`10_CONTEXT_POLICY.md` §7 の「設計判断・統計・解釈」

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

- `plans/PLAN-049-n5-gate-and-tost-delta.md` **§11 の選択 ①〜⑧ を人間に諮り、採否を ADR-139 に追記する**(提案 = IMPLEMENTER・採択 = 人間を分けて書く。ADR-097 決定6: 判断材料の表と推奨を先に見せる。`AskUserQuestion` で聞く)
  - ① 門の量を frame.csv の行から数えた(ADR-139 決定2 の文言は `frame.py` の `gate_id_by_task["t1"]` = manifest 側)。代案: manifest を読む。**実 frame が出来たら両者が一致することを確かめる(未検証)**
  - ② config に `role`・`task`・`direction` の欄を足し、実装外の値は `ConfigError`
  - ③ 感度の適格性フィルタは `ident` 全体で決め、門で絞らない
  - ④ 量を作れない run は止まる / ⑤ `pending_decisions` に null 検査を残した / ⑥ 実データの経路を足した(`input.frame_dir` が null の間は止まる)/ ⑦ 感度の出力の形 / ⑧ 順1b の門は未実装
  - 採否が決まったら PLAN-049 §11・`logs/OPEN-ITEMS.md`(その202 の行)・`STATE.md` を更新。コード変更が要る採否(① を manifest 読みに改める等)は次の IMPLEMENTER への HANDOFF に切り出す(PLANNER は `code/`・`configs/` を書かない)

## 直前セッションで確定したこと

- `configs/primary.yaml`: `analysis_gate`(role = sensitivity・task = t1・threshold = 0.90・direction = ge・min_runs = 5)・`tost.delta` = 0.4988(ADR-139 の値の写し)
- `code/analysis/primary.py`: 順 = 選ぶ → 門 → 適格性フィルタ → df → 天井 → 当てはめ。主(門なし・`n_seed` = 10 の検査のまま)と感度(門あり・通った `p2` が 5 本未満なら「実施不能: 解析門」)。`--simulate`・`--shuffle-labels` は門を掛けない。実データで止まる未決は `input.frame_dir` だけ
- `code/tests/test_primary.py`: §3.3 の算術・境界 0.9 ちょうど・主と感度が分かれる frame・k 未満・本物の config の値。`pytest code/tests -q` 2713 passed
- 食い違い(どちらも書き換えていない): ADR-139 決定2 の読み先(manifest)と実装の読み先(CSV)/ `configs/power_sim.yaml` の P1 の係数のコメント −0.326599 と `build_profile` の −0.3266(差 1e-6)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-049-n5-gate-and-tost-delta.md` §11 / `logs/DECISIONS.md` ADR-139(`grep -n '^## ADR-139' logs/DECISIONS.md`)/ `code/analysis/primary.py`(`gate_quantities`・`analysis_gate_record`・`fit_stage`・`sensitivity_stage`・`analyse`・`build_targets`)/ `code/analysis/frame.py:471-496`
- 書いてよい: `logs/DECISIONS.md`(ADR-139 追記)・PLAN-049・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/CHANGELOG.md`

## やってはいけないこと

- 採否を人間に聞かずに決める / `code/`・`configs/` を書く(PLANNER の範囲外)/ ADR-139 の値(0.90・k = 5・Δ = 0.4988)を動かす / `git add -A`(未追跡の大きい結果がある)/ 承認なしに pod を起動する・push する

## 未解決 / 人間の承認待ち

- PLAN-049 §11 ①〜⑧(上)
- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push
- `results/primary/` の 2 run(その193)をコミットするか / `frame.py` の「未実装」の docstring の食い違い(その193 から持ち越し)
- N5 の (1)(`p2d` の交互作用を副次に)と #4b の事前登録での書き方 / T3・T1b の 6 セルの扱い(ADR-078 決定6)/ S4(`01cf60f` 以降の push と G2-1 承認の後。RUNNER)/ frame の在り処(`input.frame_dir`)
