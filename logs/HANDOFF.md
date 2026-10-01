# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-01(その124)/ 直前セッションの役割: RUNNER(Phase 1 の 4 腕の完了を見届け、回収・判定表・pod の stop まで済ませた)
直前セッションが終了した理由: **Phase 1 の GPU 作業が終わり、次は人間が判定表を読む番**(PLAN 1 本の区切り。コンテキストは超過していない)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: **Opus** — 人間が判定表の読みを決める場に付き合い、決まったことを ADR に起草する作業は「設計判断・統計・解釈」の行(`Documents/10_CONTEXT_POLICY.md` §7)。**案を出すのはよいが、読み・採択は人間**。**選ぶのは人間**。GPU・pod は使わないので、判定表の場所を示すだけ・commit だけの作業なら Sonnet でもよい

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。**人間の最初の指示が先**です。指示が無ければ、下の「いまの状態」を要約して、人間に次を聞いてください。

## いまの状態(すべてファイルに反映済み: `STATE.md`・`logs/CHANGELOG.md` その124)

- **Phase 1(段2 の診断 = 鋭さ。PLAN-032)の 4 腕(B・A・B-d・A-d)の本実行は終わった**(2026-10-01T04:09:18Z〜04:28:03Z。すべて `exit=0`。件数 計 102,892 = dry-run と一致。`git_sha` は 4 本とも tag `preregister-diag-sharpness` の commit `102c2d5…`・`git_diff.patch` は 4 本とも 0 バイト)
- **run**: [run:20261001_034734_exp_diag_b] [run:20261001_035351_exp_diag_a] [run:20261001_035901_exp_diag_b_d] [run:20261001_040358_exp_diag_a_d]。ローカルの `runs/` に回収済み(commit `9d1bef3`。`predictions/` はボリューム `r963j7swke` の `/workspace/translesion/runs/<id>/predictions/` に残してあり、ローカルには無い)
- **判定表 `results/diag_sharpness/sharpness.txt`(112 行)と `sharpness.json` が出ている**(pod 上で tag の commit のまま `code.analysis.sharpness_fit` を回しただけ。**RUNNER は中身を読んでいない。印も数値も解釈もどこにも書いていない**)
- **pod `9matkiq0jozcgm` は `stop` 済み(`EXITED`)。所有 5 本すべて `EXITED`**(稼働中の pod は無く、課金は止まっている)。この pod の稼働 = 約 3,034 s = 0.84 h・約 $0.62(承認の 2.5 h・$1.85 の内側)。`cost.txt` は `runs/20261001_034734_exp_diag_b/cost.txt`
- **push は依然未**(`origin/main` = `102c2d5`。その118 の commit `01cf60f` と、その後のローカル commit は未 push。**push は人間の操作**。ADR-110 決定4)。tag・`configs/`・`code/` は 1 バイトも変えていない

## 人間が最初にやること(エージェントの仕事ではない)

1. **判定表を読む**(`results/diag_sharpness/sharpness.txt`)。`plans/PLAN-032` §8.2「判定表を読むとき」: ① 先頭の sha と tag の commit(`102c2d5`)を §8.1 R7 のとおり比べる ② `git log preregister-diag-sharpness..<解析側の sha> -- code/analysis/ code/eval/battery/` を見る(ローカルの HEAD に対しては空だった) ③ 表示された線・件数・adapter・batch・上位 k を §8.1 と見比べる。**読み(通る・通らない・どちらが優位か)を決めるのは人間**
2. 読んだ結果の ADR を起こすなら、エージェントが起草してよいが、**提案者(エージェント)と採択者(人間)を分けて書く**(ADR-039)。**エージェントが判定表の印・数値を解釈して「通った/通らなかった」と書くことはしない**

## エージェントがしてよいこと(人間の指示があれば)

- 判定表の**場所と構造の説明**(`sharpness.txt` を `sed -n` で必要な範囲だけ見せる。`sharpness.json` のキー一覧)。**解釈はしない**
- 人間が決めた読みの **ADR の起草**(`logs/DECISIONS.md`)と、`STATE.md`・`logs/CHANGELOG.md`・`logs/OPEN-ITEMS.md` への反映
- PLAN-033(段3。ADR-098)の起草など、段2 が人間待ちの間に挟める作業
- **`CLAUDE.md` §4 の順(PLAN → 人間のレビュー → 実装 → テスト → CHANGELOG → commit)を守る**

## やってはいけないこと

- **判定表を解釈しない**(`CLAUDE.md` §8)。`results/diag_sharpness/` の中身から「Phase 2 に進める」「診断が通った」などの結論を書かない
- **tag を打たない・push しない**(人間の操作。ADR-110 決定4)
- **I5(Phase 2。10 本の固定オフセットの T1b・T3)を回さない・pod を起動しない**。Phase 2 は `01cf60f` の push と **別の G2-1 承認(新しい上限)**が先。今回の承認は Phase 1 のみ(0.84 h で使い切った)
- **`configs/`・`code/` を直さない**(事前登録の凍結。`CLAUDE.md` §2・§8)
- **旧 4 本の pod(`nwpfapeszov83m`・`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)と `9matkiq0jozcgm` を terminate しない**(人間の操作。ボリューム `r963j7swke` は残す)
- **この機は Windows**: `.md`・`.py` は LF 固定(Python で書くときは `newline="\n"`)。GNU `tar` は `C:/...` を「リモートホスト `C`」と解釈するので `--force-local` か相対パスを使う。Bash の heredoc に長い日本語 + 引用符を入れると解釈エラーになることがあるので、長い文面は `Write` でスクラッチパッドに置く

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- **★Phase 1 の判定表を読むこと**(人間。上のとおり)
- **その118 commit(`01cf60f`)の push** と **Phase 2 の G2-1 承認**(新しい上限)
- その118 の実装の読み 1〜5・採択の ADR への記録・★T2 の形の変化と #5 の扱い・旧 4 本と今回の pod の terminate(持ち越し)
- `train.jsonl` を手元から送った採択(その122)の **ADR は未記入**(CHANGELOG に事実は記録済み。人間が望めば起こす)
- **未確認(その124 の CHANGELOG「批判的視点」)**: 4 腕の所要時間は合計 1,125 s = 0.31 h で、RUNNER の見積り(約 1.05 h)の約 0.3 倍。件数は dry-run と一致しており項目を飛ばしたのではない。速かった理由は確かめていない。判定表の読みに関わるなら `metrics.json` の `timing`・`generation` と見比べるのは人間
