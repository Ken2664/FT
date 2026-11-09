# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-09(その203)/ 直前セッションの役割: PLANNER(Claude Sonnet 5.5 が務めた。推奨の Opus と不一致。人間が続けさせた)
直前セッションが終了した理由: コンテキスト 149k 超(閾値 140k)。PLAN-049 §11 の採否は記録・commit 済み(`01188eb`)。次の作業は人間が「frame の在り処を決める」と選んだ。まだ着手していない
**推奨モデル(次のセッション)**: Opus — 設計判断(`10_CONTEXT_POLICY.md` §7)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

- **`configs/primary.yaml` の `input.frame_dir`(凍結した frame の在り処)を決める**。実データの `primary.py` が止まる最後の未決(STATE.md「次のアクション」1)
  - まず事実を集める(推測しない): `grep -n 'frame_dir\|CSV_FILENAME\|FRAME_MANIFEST_FILENAME' code/analysis/frame.py code/analysis/primary.py`、`ls results/ | head`、`results/primary/`(その193 の 2 run)の中身、frame を作る CLI(`python -m code.analysis.frame --help`)と入力の run の有無(本実験の `p2` の実データは無い=凍結前)
  - 判断材料の表(案・長所・短所)と**推奨を先頭に理由付きで**先に見せてから `AskUserQuestion` で聞く(ADR-097 決定6)。例の論点: frame を `results/` のどこに置くか / git に入れるか(大きさ)/ 凍結 tag との関係 / いまは実 run が無いので「在り処の規則(パス)だけ決める」か「frame ができてから決める」か
  - 採否は ADR に追記(提案 = エージェント・採択 = 人間を分けて書く)。`configs/` の書き換えは PLANNER の範囲外 → 次の IMPLEMENTER への HANDOFF に切り出す
  - frame ができたら ADR-139 追記 ① の検査(frame.csv から数えた門の量 = manifest の `gate_id_by_task`)を行う(未検証。食い違えば止めて人間に聞く)

## 直前セッションで確定したこと

- PLAN-049 §11 の選択 ①〜⑧ を人間が採否: **すべて実装のまま採る**(ADR-139 追記 ①)。`code/`・`configs/` は不変。ADR-139 の値(0.90・k = 5・Δ = 0.4988)は不変
- 実データの `primary.py` が止まる未決は `input.frame_dir` だけ(`primary.py` の `pending_decisions`)

## 触ってよいファイル / 読むべき範囲

- 読む: `code/analysis/frame.py`(`grep -n` で節を特定)/ `code/analysis/primary.py`(`pending_decisions`・`build_targets`・`read_frame`)/ `configs/primary.yaml` の `input` 節 / `plans/PLAN-016`(frame の項)/ `.gitignore`
- 書いてよい: `logs/DECISIONS.md`・`logs/OPEN-ITEMS.md`・`STATE.md`・`logs/CHANGELOG.md`・必要なら新しい PLAN(`plans/`)

## やってはいけないこと

- 採否を人間に聞かずに決める / `code/`・`configs/` を書く(PLANNER の範囲外)/ ADR-139 の値を動かす / `git add -A`(未追跡の大きい結果がある)/ 承認なしに pod を起動する・push する

## 未解決 / 人間の承認待ち(STATE.md「次のアクション」が正本)

- pod `9matkiq0jozcgm`・`oorrti5on9opnb`(どちらも `EXITED`)を残すか terminate するか / push / `results/primary/` の 2 run をコミットするか
- `01cf60f` 以降の push と G2-1 承認 → S4(RUNNER)→ T2 の文面・step 数(ADR-130 決定2)
- N5 の (1)・#4b の書き方 / T3・T1b の 6 セル(ADR-078 決定6)/ `frame.py` の「未実装」の docstring の食い違い
