# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その204)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: HANDOFF の 1 つ(frame の在り処)を済ませた(ADR-140)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Sonnet — 実装(`10_CONTEXT_POLICY.md` §7。決まった仕様をコードに写すだけで、値の決定は無い)

---

あなたは IMPLEMENTER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。

## このセッションでやること(1つだけ)

**ADR-140 の I1〜I4 を実装し、`pytest code/tests -q` を通す**(仕様の正本は `logs/DECISIONS.md` の ADR-140「影響」):

- I1 `configs/primary.yaml` の `input.frame_dir` = `results/frame_exp_phase1_main`(コメントに ADR-140。「実データはまだ無い」の旨は残す)
- I2 `code/analysis/primary.py`: 実データの経路で、読んだ frame の在り処(repo からの相対パス)と `csv_sha256` を `primary.json` の meta と `report.md` に残す(`--simulate`・`--shuffle-labels` での扱いは既存の形に合わせ、決まっていなければ null にして選んだことを報告する)
- I3 `code/analysis/frame.py` の `write_frame`: 既にある `out_dir` には書かずに `FrameError` で止まる(`mkdir(exist_ok=True)` をやめる)。`--dry-run` は不変
- I4 テスト: 本物の config の `input.frame_dir` の値 / meta の 2 欄 / 既にある `out_dir` で止まる / `pending_decisions` から `input.frame_dir` が外れる。**既存のテストで「`frame_dir` が null なら止まる」を本物の config に頼っているものは、写しを null に戻して確かめる形に直す**(ADR-138 追記 ③ のときと同じ)
- 完了後: `logs/CHANGELOG.md`・`STATE.md`・ADR-140 の「まだ書き換えていないもの」を更新して commit。PLAN に無い選択をしたら列挙し、人間の採否待ちとして `logs/OPEN-ITEMS.md` に 1 行

## 直前セッションで確定したこと

- ADR-140(人間。4 問とも推奨 (a)): 在り処 `results/frame_exp_phase1_main/` をいま config に書く / CSV と manifest を両方 git に / frame のコミットが先・`primary.py` は後 / 決定4 の (i) 記録 (ii) 上書き禁止
- 事実: `write_frame` は既にある `out_dir` に黙って上書きする(`frame.py:634-647`)/ `primary.json` の meta は `run_id`・`mode`・`git_sha`・`alpha`・`tost_alpha` だけ(`primary.py:902-903`)

## 触ってよいファイル / 読むべき範囲

- 書く: `configs/primary.yaml`(`input` 節)/ `code/analysis/primary.py`(`read_frame` 242-258・`main` の経路 855-905・`render_report`・`write_outputs`)/ `code/analysis/frame.py`(`write_frame` 618-650)/ `code/tests/test_primary.py`・`code/tests/test_frame.py`(あれば。`grep -n write_frame code/tests`)/ `logs/`・`STATE.md`
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`

## やってはいけないこと

- ADR-139・ADR-140 の値や規則を動かす / `frame.py` の行の組み方(ADR-062)を変える / `results/frame_exp_phase1_main/` を作る(本実験の run は無い)/ `git add -A`(未追跡の大きい結果がある。触ったファイルだけ add)/ push / pod の起動
- `frame.py:10` の docstring「未実装」を直す(人間待ち。気づいたら報告だけ)

## 未解決 / 人間の承認待ち(STATE.md「次のアクション」が正本)

- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(`EXITED`)の扱い / push / `results/primary/` の 2 run のコミット / `frame.py:10` の docstring の食い違い
- 実 frame ができたら ADR-139 追記 ① の一致(frame.csv から数えた門の量 = manifest の `gate_id_by_task`)の検査(未検証)
- `01cf60f` 以降の push と G2-1 承認 → S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)
