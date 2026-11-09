# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その205)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: HANDOFF の 1 つ(ADR-140 の I1〜I4 の実装)を済ませた
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Opus — 設計判断(PLAN に無い選択 ①〜⑥ の採否を人間に諮る。`10_CONTEXT_POLICY.md` §7)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**その205 の「PLAN に無い選択 6 点」(`logs/OPEN-ITEMS.md` の ★ADR-140 の I1〜I4 の行・`STATE.md` の「引き継ぎ」)の採否を人間に諮り、決まったことを ADR-140 の追記に残す。**
判断材料の表(各選択の案・長所・短所)と推奨を**先に**示す(`CLAUDE.md` §8・ADR-097 決定6)。決めるのは人間である。

- ① `read_frame` は `frame.csv`・`frame_manifest.json` が無ければ `PrimaryError`(生の `FileNotFoundError` にしない)
- ② meta の 2 欄(`frame_dir`・`frame_csv_sha256`)は frame を読んだときだけ値が入る(`--simulate`・合成の `--shuffle-labels` は null)
- ③ repo の外の frame_dir は絶対パス(posix)で残す・sha は `read_frame` が照合した CSV の実体を再ハッシュ
- ④ **`--shuffle-labels` は config の `frame_dir` が決まっていればそれを既定で読む**(既存コードの動き。frame ができるまで既定では止まる。合成の入れ替えは `frame_dir` を null にした config の写しを `--config` で渡す)。ここが一番効く(`primary.py` の `resolve_frame_dir`・`build_targets`)
- ⑤ `write_frame` は空の既存ディレクトリも止める(`exists()`)
- ⑥ frame_dir の解決を `resolve_frame_dir` に抜き出した

## 直前セッションで確定したこと

- ADR-140 の I1〜I4 を実装した(`pytest code/tests -q` 2717 passed)。値・規則(ADR-139・ADR-140)と `frame.py` の行の組み方(ADR-062)は動かしていない
- 本物の `configs/primary.yaml` に null は残っていない。実データの `primary.py` は本実験の frame(`results/frame_exp_phase1_main/`。**まだ作っていない**)が無いので「frame.csv が無い」で `EXIT_ERROR`
- 実 frame ができたら ADR-139 追記 ① の一致(frame.csv から数えた門の量 = manifest の `gate_id_by_task`)を検査する(未検証)

## 触ってよいファイル / 読むべき範囲

- 書く: `logs/DECISIONS.md`(ADR-140 の追記のみ)・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/CHANGELOG.md`。**`code/`・`configs/` は不変**(採否で直すことになった分は IMPLEMENTER へ)
- 読む: `code/analysis/primary.py` の `resolve_frame_dir`・`frame_record`・`build_targets`(`grep -n` → `sed -n`)、`git show <その205 の commit>`
- 全文 `cat` しない

## やってはいけないこと

- ADR-139・ADR-140 の値や規則を動かす / `results/frame_exp_phase1_main/` を作る(本実験の run は無い)/ `git add -A`(未追跡の大きい結果がある)/ push / pod の起動
- `frame.py:10` の docstring「未実装」を直す(人間待ち。気づいたら報告だけ)

## 未解決 / 人間の承認待ち(STATE.md「次のアクション」が正本)

- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(`EXITED`)の扱い / push / `results/primary/` の 2 run のコミット / `frame.py:10` の docstring の食い違い
- `01cf60f` 以降の push と G2-1 承認 → S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)
