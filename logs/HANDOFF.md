# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-02(その135)/ 直前セッションの役割: IMPLEMENTER(PLAN-037 の I6〜I9 を実装した)
直前セッションが終了した理由: **コンテキストが閾値(140k)を超えた**(`CLAUDE.md` §10.2。PLAN-037 の実装は I10 以外が済んだ区切り)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: **Sonnet**(S2 = PLAN-034 の実装は IMPLEMENTER。`Documents/10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)。S5 の値の決定の準備・解釈・統計の設計は **Opus**。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェント(IMPLEMENTER)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**(Sonnet で判断系の作業 = 値の決定・設計の判断になりそうなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`git log` と `git worktree list` で並行セッションの commit・worktree が無いかも確かめる。**worktree `claude/great-bardeen-9c1ac4`(`.claude/worktrees/great-bardeen-9c1ac4`)は登録済みの既知の 1 本**で、削除は人間待ち。それ以外が出たら作業の前に人間に報告)。**人間の最初の指示が先**です。指示が無ければ、次の 2 つを判断材料と推奨(下の A を推奨。PLAN-037 が済んで残る実装はこれだけ)を付けて人間に聞いてください。

## A: S2 = PLAN-034 の実装(IMPLEMENTER / Sonnet)

- 正本: `plans/PLAN-034-*.md` §6 の I1〜I7 / ADR-114。I7 のベンチマークの後に人間へ ★F114 の実行先を諮る(`n_item`・`s2_item`・`s2_tmpl`(★F104-c。**値は人間**)は null のまま)
- 触るファイルは PLAN-037 と別(`power_sim*`)。完了条件は PLAN-034 §6 に従う。実装の規約は skill `code-style`
- `pytest code/tests -q` は現在 **2361 passed**(約 10 分。**背景で回して `tail`**)

## B: PLAN-037 の I10(人間の承認の後)

- `Documents/04_EXPERIMENT_PLAN.md` Phase 1「評価の追加」と `05_STATISTICS.md` §4 に実装の場所の注を 1 行ずつ(旧文は消さない)。**人間が承認してから**

## 入っているもの(PLAN-037 の I1〜I9。I1〜I5 は commit `3e1f9aa`、I6〜I9 はこのセッションの commit)

| I | ファイル | 要点 |
|---|---|---|
| I6 | `code/eval/model.py` | `validate_lora_scale`([0, 1])・`apply_lora_scale`(peft 0.20.0 の `LoraLayer.set_scale` で**絶対値**。`scale_layer` は使わない。`layer_type` で置き物の層に差し替え可)・`declared_scale_sweep_levels`(`eval.scale_sweep.levels`。アダプタ null なら止まる) |
| I7 | `code/eval/scale_sweep.py` | `python -m code.eval.scale_sweep --config <c> [--dry-run] [--run-dir-prefix <p>]`。重みを 1 回読み、水準を宣言の順に掛け替え、s ごとに `<接頭辞>_s<水準>` の run。`eval.task_subset` は T1・T2 だけ(D8)。D9 の門を入口で掛ける。`metrics.json` に `lora_scale`・`signature_gate`・`scale_sweep`。`ScaleSession` を差し替えるとテストで重みを読まない |
| I8 | `code/analysis/frame.py`・`aggregate.py` | `frame.py` は s が 1 でも無記録でもない run で止まる(`non_plain_lora_scale`)。`aggregate.py` は行を s で分け警告(過去の run の出力は不変)。掃引の run は `task_subset` 宣言で集約も止まる |
| I9 | `configs/exp_t1c_main.yaml`・`exp_t1c_pilot.yaml`・`exp_pilot_scale_ident_s0_n313.yaml` | T1c の 2 本は `exp_phase1_main.yaml`・`exp_order6b_pilot.yaml` の写しで差は 5 欄(**`eval.composition.n_per_cell` と `eval.freeze_tag` は null**)。掃引の config は `exp_pilot_ft_eval_ident_s0_n313.yaml` の写し + T1・T2 + `levels: [0, 1]`(S4 (iii) の配線確認。**本番の水準ではない**)。テスト `test_t1c_configs.py` |

## 直前セッションで確定したこと(ファイルに反映済み)

- **実装の段で足した判断(PLAN に明記なし。人間が覆してよい)**: 宣言は `eval.scale_sweep.levels` だけ(単独 run の `model.lora_scale` は作っていない。`run.py` の 3 入口と `composition_run` は `eval.scale_sweep` を拒む)/ **s = 1 だけの掃引も D9 の門を掛ける**(D9 の文言は「s ≠ 1」で明記が無い。止める側に倒した)/ 書き出し先に `metrics.json` が既にあれば止める / run ディレクトリ名 `<接頭辞>_s<水準>`(`0.5` → `0p5`)
- 許可リストのテストを 2 本直した(`test_gonogo.py` の近接同点の幅に `exp_t1c_pilot.yaml`・`test_task_subset.py` の絞りに `exp_pilot_scale_ident_s0_n313.yaml`)
- **`peft` の確認は読み取りだけ**(この機に peft が無い)。**実機で `set_scale` が全層に効くかは S4 で確かめる**(s = 0 は素のモデルの記録と、s = 1 は既存の `ident` の評価 [run:pilot_ft_eval_ident_s0_n313] と予測を突き合わせる。一致しなければ配線を疑う。揺れが出たら件数と項目を報告)

## やってはいけないこと

- **ADR-111〜118 を覆さない**(直したい点が出たら人間に聞く)
- **値を決めない・提案しない**: T1c の件数・統計・α / s の水準 / step 数 / T2 の文面 / ★F104-c / TOST の Δ・境界 / シード分類の閾値 / 2 系統目の系統 / `eval.freeze_tag` の tag の名前
- **パイロットの `p2`・`p2d` で T1c・スケールの掃引を回さない**(ADR-116 決定3。D9 の門で止める)
- **既存のプール・項目・文面を 1 バイトも変えない**(`test_composition_pool.py::test_existing_evaluation_pools_are_unchanged` と既存の回帰テストが固定)
- **MisFT を ✅ にしない・`refs.bib` に入れない・「初めて」と書かない**
- **tag を打たない・push しない・pod を起動しない**
- **`scale_layer` を使わない**(累積する)。`set_scale` で絶対値を置く
- **この機は Windows**: `.md`・`.py`・`.yaml` は LF 固定(`aggregate.py`・`model.py` の作業ツリーが CRLF で出てくることがある。`git ls-files --eol` で確かめ、LF に直してから編集する)。長い日本語はスクラッチパッドにスクリプトを置いてから Python で入れ、**置換は件数を数えてから**。**複数のヒアドキュメントを 1 つのコマンドに入れない**
- STATE.md は 366 行・61 KB(上限 400 行 / 60 KB に**ほぼ到達**)。**次に足すときは同じだけアーカイブへ移す**
- 全体の pytest は約 10 分。`eval_pool.build` が約 10 秒かかるので、テストでは `functools.cache` で config ごとに 1 回にする

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 次の作業(A = S2 / B = PLAN-037 の I10 の承認)
- S4 の T1c(素のモデルと pilot `ident` の適格性)を S5 の値の決定の後・tag の前に回す順の確定(ADR-118 決定3 の帰結)。`ident` の T1c の config はそのとき `exp_t1c_pilot.yaml` の写しで作る
- worktree `claude/great-bardeen-9c1ac4` の削除(main に入れ済み)
- MisFT の原典確認と Table A4 / `09_PAPER_PLAN.md` 論文 1 の下書き・`00_OVERVIEW.md` §7 の確定
- 凍結前(S5): T1c の件数(主・pilot)・統計・α・適格性の規則 / s の水準 / step 数と T2 の文面 / ★F104-c / ★F114(PLAN-034 I7 の後)/ 平行性の TOST の Δ / シード分類の規則と閾値 / E1 の TOST 境界と α と検出力 / 天井 / ★L(d) / N5 / 本番テンプレート集合 / `θ` の根拠 / `eval.freeze_tag` の名前
- ★R8 の push と G2-1 承認 / 2 系統目の選定(本実験の後)/ ★`CLAUDE.md` を 200 行へ戻す / 旧 4 本と `9matkiq0jozcgm` の terminate / 価値レビューの引用の原典確認(会場未照合 6 件)
