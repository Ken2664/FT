# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-25(その93)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: PLAN の 1 件が完了(G1-1・G1-2・#4b の基準を人間が決め、ADR-103 に記録した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Sonnet** — ポッドの操作・訓練と評価の実行・回収と、決まった規則の機械的な当てはめ(PLAN-031 §8.1)が中身。`Documents/10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成 = Sonnet」の行に近い(この読みは人間が覆せる)。
**予測と違う結果の解釈や規則の外の判断が要る場面になったら、止めて人間に上げる**(`CLAUDE.md` §8)。

---

あなたは RUNNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1 つだけ)

**PLAN-031 のパイロット FT(訓練 5 本・評価 5 本)を、`plans/PLAN-031-seed-fix-and-pilot-ft.md` §8.1 の規則どおりに実行・回収し、`gonogo_ft` の表を出して報告する。解釈はしない。**

0. **始める前に確かめること(どれかが欠けたら始めない)**:
   - `git merge-base --is-ancestor preregister-pilot-ft HEAD` が通る(**凍結 tag は人間が打つ。無ければ人間に伝えて待つ。エージェントは打たない**)
   - RunPod MCP で在庫と単価を読み、**単価と「停止中の pod `lh823acvxuo8ux` を再開するか新規に立てるか」を人間に確かめる**(ADR-103 決定1)
1. §8.1 A: **最初に `p2` s0 を訓練する**(`--run-dir runs/pilot_ft_train_p2_s0`。評価 config の `model.adapter` がこの名前を指す)。VRAM は `nvidia-smi` を 3 秒間隔で外から記録する。
   終わったら外挿値 =(pod の稼働時間)+ 4 ×(`p2` s0 の訓練の壁時計)+ 5 × 10 分 + 15 分 を出す。**4 時間を超えるなら残りを始めずに止めて報告する。1 本目が 60 分を超えたら止める**
2. 残りの訓練 4 本と評価 5 本を回す。**pod の稼働時間 4 時間で打ち切る**
3. `python -m code.analysis.gonogo_ft --runs "<評価 run の glob>" --out-dir results/pilot_ft` → `gate_summary` を §8.1 B の表に当てる。
   **回し直しが要る場合は、config を自分で書き換えない**(IMPLEMENTER が `infra/make_pilot_ft_configs.py` で作り直す。1 回目の run を上書きしない)。止めて報告する
4. 成果物を git に戻す(`infra/RUNPOD.md` §4。アダプタを含む)。**4 値すべてを並べて報告する**(`CLAUDE.md` §6)。pod を停止する

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-103**(正本)/ **PLAN-031 §8.1(規則)・§8.2(承認の文面)**: 一括承認・pod の稼働 4 時間まで・`p2` s0 の後に外挿して止める / VRAM が足りなければ micro 2 × 累積 8(全 8 config を IMPLEMENTER が作り直す。それでも載らなければ止める)/
  #4b = `p2d` の `T1 × id` の `rule_rate`(参照規則 `p2d`)≥ 0.90、全シード / 回し直しは `num_steps` 625 → 1,250(#4 のみ割れ)か → 313(#5 のみ割れ)で各向き 1 回、衝突は止める、#4b・#5b では動かさない、lr は動かさない、段1 全体で 9 時間まで
- **見積りは算定だけで、訓練の実測は 0 本**(全体 1.5〜3 時間 ≈ $1.1〜2.2 と見込む。訓練中の VRAM は 18〜20 GB 程度と見込む)。**訓練ループは途中経過を出さない**(秒/ステップは run の `timestamp.txt` の壁時計から出す)
- ★E の確かめは通った [run:pilot_ft_seed_check_a] [run:pilot_ft_seed_check_b](peft 0.20.0・torch 2.8.0+cu128・transformers 5.16.1)。重み読み込み時の VRAM は最大 16,062 MiB
- `pytest code/tests -q` = 1716 passed(その90 の実測。その91〜93 はコードを変えていない)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-031-seed-fix-and-pilot-ft.md` の §8.1・§8.2(`grep -n '^### 8' ` で当てる)/ `logs/DECISIONS.md` の ADR-103 だけ(`grep -n '^## ADR-103'`)/ `infra/RUNPOD.md` §4(手順と必須の成果物)
- config は `configs/exp_pilot_ft_{train_{p2,ident,p2d},eval_{p2_s0,p2_s1,ident_s0,ident_s1,p2d_s0}}.yaml`(**読むだけ。編集しない**)
- **pod の落とし穴**(根拠は `logs/CHANGELOG.md` その92 と memory `runpod-ssh-ipqos-none`):
  `export HF_HOME=/workspace/.cache/huggingface` を必ず行う(飛ばすと 401)/ ssh・scp は `-o IPQoS=none -o ServerAliveInterval=5 -o ServerAliveCountMax=4` を付ける /
  長い処理は `nohup setsid bash x.sh &` で切り離す / repo は差分 bundle(`git bundle create x.bundle 175d946..main`)で送り、untracked の run が衝突したら退避してから `git merge --ff-only` /
  **データ(`data/generated/`)は git に無い**。pod 上で preflight の `data_checks` が通るかを確かめる(無ければ config 冒頭のコマンドで作り直す)/ 「終了コード 1」は例外でも出るので、成否は成果物の有無で見る

## やってはいけないこと

- **tag を打たない。config・コードを書き換えない**(回し直しの config は IMPLEMENTER)。§8.1 の外の条件・値・順序を足さない
- **`num_steps`・`learning_rate` を自分の判断で動かさない。**#4b・#5b の割れで回し直さない。結果を解釈しない(「病変が入った」「崩壊した」と書かない。印と 4 値を並べる)
- `pool_id: pilot` の数値を主張・効果量・Δ 5 行・検出力分析・E1 の境界に使わない。T1b・T3 は解かない(段2 の凍結の後)
- **結果が良すぎるとき(例: #4 が 1.000)は、まずバグを疑う**(`CLAUDE.md` §7。PLAN-031 §6 新5)。pod を起動したまま放置しない。`lh823acvxuo8ux` を terminate しない(人間。段1 の後)

## 未解決 / 人間の承認待ち

- **凍結 tag `preregister-pilot-ft`**(人間が §8.1・§8.2 を読んでから打つ。**「(具体化)」の細部**(評価 1 本の置き値 10 分・回収 15 分・1 本目の打ち切り 60 分・VRAM の記録方法・回し直しの run の名前)は人間に別の問いとして聞いていない)
- 結果の解釈・`p2d` の扱い・回し直しの後の判断は人間(`CLAUDE.md` §8)。**10 問すべてで推奨が選ばれた**(ADR-103 リスク欄。7 回目)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
