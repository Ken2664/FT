# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-02(その134)/ 直前セッションの役割: IMPLEMENTER(PLAN-037 の I1〜I5 を実装した)
直前セッションが終了した理由: **コンテキストが閾値(140k)を超えた**(`CLAUDE.md` §10.2。PLAN-037 §8 が許す「I5 の後の区切り」)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: **Sonnet**(PLAN-037 の I6〜I9 / S2 = PLAN-034 の実装。どちらも IMPLEMENTER。`Documents/10_CONTEXT_POLICY.md` §7 の「実装・集計・データ生成」の行)。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェント(IMPLEMENTER)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**(Sonnet で判断系の作業 = 値の決定・設計の判断になりそうなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`git log` と `git worktree list` で並行セッションの commit・worktree が無いかも確かめる。**worktree `claude/great-bardeen-9c1ac4`(`.claude/worktrees/great-bardeen-9c1ac4`)は登録済みの既知の 1 本**で、削除は人間待ち。それ以外が出たら作業の前に人間に報告)。**人間の最初の指示が先**です。指示が無ければ、PLAN-037 の I6〜I9 / S2 のどちらにするかを判断材料と推奨(PLAN-037 の続きを推奨。既に 5/9 まで入っていて残りが小さい)を付けて人間に聞いてください(並行できる。触るファイルが別)。

## A: PLAN-037 の I6〜I9(続き)

- 正本: `plans/PLAN-037-t1c-spec-breakdown-scale-sweep.md` §3.3・§6 の I6〜I9 / ADR-118。**I1〜I5 は commit `3e1f9aa` に入っている**(下の「入っているもの」)
- 完了条件: I6〜I9 の実装と単体テスト → `pytest code/tests -q`(現在 **2283 passed**。全体で約 11 分かかる。**背景で回して `tail`**)。I10(文書の注)は人間の承認の後
- **件数の欄は null のまま**(主・pilot とも S5 で人間。ADR-118 決定3)。I9 で config を作るときも `n_per_cell: null`
- 実装の規約は skill `code-style`

### I6(LoRA のスケール)— **peft の原典は確認済み**(この機に peft は無い。PyPI の wheel `peft-0.20.0` を開いた)

- `peft/tuners/lora/layer.py` の `LoraLayer`: `self.scaling: dict[adapter名, float]`(初期値 = `lora_alpha / r`、`use_rslora` なら `/ sqrt(r)`。L127-128・L274-277)。forward は `lora_B(lora_A(dropout(x))) * self.scaling[active_adapter]`(L1055 付近)
- **`LoraLayer.set_scale(adapter: str, scale: float)`(L742)は `scaling[adapter]` を「初期値 × scale」の絶対値に置く**(積み上がらない)。**`scale_layer(scale)`(L755)は現在値に掛けるので累積する → 使わない**。`unscale_layer(None)` は初期値へ戻す
- 実装の形: `from peft.tuners.lora import LoraLayer` → `for module in model.modules(): if isinstance(module, LoraLayer): module.set_scale(adapter_name, s)`。adapter 名は `PeftModel.from_pretrained` の既定 `"default"`(`attach_adapter` は名前を渡していない。実装の段で `model.active_adapter` から引くこと)。**docstring に版 `peft==0.20.0`(`infra/requirements.lock` L138)と上の箇所を書く**。**この機の環境に peft が無いのでテストは置き物の LoRA 層**(`scaling` dict と `set_scale` を持つ最小のクラス)で書く。**実機での確認は S4(s = 0 と 1 の配線確認)の役目**
- s の宣言は [0, 1] の外を拒む(PLAN-035 §3.5 の定義)/ アダプタ null で s を宣言したら止める / 宣言の無い run はモデルに触れない / `metrics.json` の **`lora_scale`**(`code/analysis/composition_table.py` の `LORA_SCALE_KEY` が同じ名前を読む。記録の無い run = null のまま)・`adapter` の記録・`log.txt` に s を残す

### I7〜I9

- **I7** `code/eval/scale_sweep.py`: 重みとアダプタを 1 回読み、宣言した s の順に掛け替えて **s ごとに別の run ディレクトリ**を書く(D7 (c))。`eval.task_subset`(T1・T2。D8)。水準の並びは config のまま。**D9 の門は `code/eval/signature_gate.py` の `check_signature_gate(config, adapter=…, condition=…, what="スケールの掃引(s≠1)")` を呼ぶ**(T1c の入口 `composition_run.py` が呼ぶのと同じ関数)。**s = 1 だけの run を門に通すか**は PLAN に明記が無い → 実装の前に PLAN-037 §3.3・§6 I7・D9 を読み直し、曖昧なら人間に聞く
- **I8** `frame.py` は `lora_scale` が null でも 1 でもない run で止まる(記録の無い過去の run は s = 1 と読む)。`aggregate.py` は s の列を出す(**T1c の `kind` は既に飛ばす・止まる**。`EVAL_KIND` 以外を `aggregate.py` L352 が飛ばし `frame.py` L257 が止める)。過去の run の集約が 1 文字も変わらないこと
- **I9** `configs/`: 主・pilot それぞれの T1c の config(`exp_phase1_main.yaml`・`exp_order6b_pilot.yaml` の写し + `eval.composition: {prompt_template: "{a}+{b}+{c}=", n_per_cell: null}` + `experiment.id` + `eval.anchor_manifest` → `data/generated/battery/<pool_id>_t1c/manifest.json`。`eval.batteries` と `eval.cells` は写しのまま = `eval_pool.build` が通るため)。**既存の config を変えない**。写しの差分を固定するテストは `code/tests/test_order6_configs.py`・`test_pilot_ft_cmp_configs.py` が前例(同じ形で足す)。S4 の配線確認の config(`ident` の s = 0・1)。`eval.freeze_tag` は null。**preflight の data_checks が T1c のプールで通ること**は件数が決まった後(null のうちは確かめられない)

## 入っているもの(commit `3e1f9aa`。読むのは必要な所だけ)

| I | ファイル | 要点 |
|---|---|---|
| I1 | `code/eval/battery/composition.py`・`code/lesion.py`(`CompositionOffsetLesion`・`composition_reference_lesions_from_config`)・`battery_items.SUPPORTED_GROUPS` に `composition` | 参照規則 `comp_once`(t+offset)・`comp_twice`(t+2·offset)。`item_id` は被演算子だけ(`params` は id に入らない)。文面は `eval.composition.prompt_template` から(既定なし。`{a}{b}{c}` が 1 つずつ) |
| I2 | `code/data_gen/composition_pool.py` | `python -m code.data_gen.composition_pool --config <config> [--dry-run]`。セル = 先頭の組の id・interp × carry。選び方 = `[tag, eval.pool_seed, a, b]` の sha256。c は組のハッシュ。manifest の `fill.method = "composition"` |
| I3 | `code/eval/composition_run.py`・`code/eval/signature_gate.py`・`code/eval/run.py`(`refuse_declared_composition`・`check_pool_kind` に T1c の拒否) | `python -m code.eval.composition_run --config <config> [--dry-run]`。`kind: composition`。`metrics.json` に `by_batch.composition`(全体)と `by_cell`、どちらも 2 ブロック |
| I4 | `code/analysis/composition_table.py` | `--runs <glob> [--out]`。rate(t)・rate(t+offset)・rate(t+2·offset)・d。判定の文言なし |
| I5 | `code/analysis/spec_breakdown.py` | `--runs <glob>`。パイロットの数え上げと同じ順。`.out` の 12 行と一致(`predictions/` は .gitignore なので手元に無ければ skip) |

## 直前セッションで確定したこと(ファイルに反映済み)

- **ADR-118 の D1〜D9 に沿って実装した**。実装の段で足した判断(PLAN に明記なし。**人間が覆してよい**): 群名 `composition`・category `t1c`・参照規則名 `comp_once`/`comp_twice`(PLAN D1 の補足の例どおり)/ config の置き場所 `eval.composition.{prompt_template, n_per_cell}` / 門の tag の欄 `eval.freeze_tag` / 組の選び方のハッシュの tag 名(`composition_pair`・`composition_third`。`sweep_pool.SELECTION_TAG` と同じ位置づけで調整値ではない)/ 3 つ目の被演算子 c の範囲 `[2, main_radius]`(±1 を除く。c の側にも「訓練域の中」を要求した)/ T1c の評価は自由生成 + `numeric` パーサ(変えていない。PLAN §7 罠 4)
- 先頭の組の候補数(組合せ論的な計数。実験結果ではない): 主 897 組(`id × carry` 167・nocarry 730)/ pilot 903 組(157・746)— `code/tests/test_composition_pool.py` が固定。`interp` 側は 主 1,291(245 + 1,046)/ pilot 1,374(250 + 1,124)
- T1c の先頭の組と T1 の組の重なり: 件数 5/セル(テスト用)で pilot 3 組・主 0 組(manifest の `first_pair_overlap_with_t1`。本番の件数では S5 の後に出る)

## やってはいけないこと

- **ADR-111〜118 を覆さない**(直したい点が出たら人間に聞く)
- **値を決めない・提案しない**: T1c の件数・統計・α / s の水準 / step 数 / T2 の文面 / ★F104-c / TOST の Δ・境界 / シード分類の閾値 / 2 系統目の系統 / `eval.freeze_tag` の tag の名前
- **パイロットの `p2`・`p2d` で T1c・スケールの掃引を回さない**(ADR-116 決定3。D9 の門で止める)
- **既存のプール・項目・文面を 1 バイトも変えない**(主 `d272204f…`・pilot・R8・S・診断。`test_composition_pool.py::test_existing_evaluation_pools_are_unchanged` と既存の回帰テストが固定)
- **MisFT を ✅ にしない・`refs.bib` に入れない・「初めて」と書かない**
- **tag を打たない・push しない・pod を起動しない**
- **`scale_layer` を使わない**(累積する)。`set_scale` で絶対値を置く
- **この機は Windows**: `.md`・`.py` は LF 固定(Python で書くときは `newline="\n"`)。`test_repo_hygiene.py` は `Documents/*.md`・`plans/*.md`・記録文書の CR を検査する。長い日本語はスクラッチパッドにスクリプトを置いてから Python で入れ、**置換は件数を数えてから**。**複数のヒアドキュメントを 1 つのコマンドに入れない**(引用が壊れる。Write ツールで書く)
- STATE.md は 363 行・60.1 KB。**次に足すときは同じだけアーカイブへ移す**
- 全体の pytest は約 11 分(`composition_pool` のテストは 18 秒)。**`eval_pool.build` が約 10 秒かかる**ので、テストでは `functools.cache` で config ごとに 1 回にする(`test_composition_pool.py::source_pool` が前例)

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 次の作業(PLAN-037 の I6〜I9 / S2)
- S4 の T1c(素のモデルと pilot `ident` の適格性)を S5 の値の決定の後・tag の前に回す順の確定(ADR-118 決定3 の帰結)
- worktree `claude/great-bardeen-9c1ac4` の削除(main に入れ済み)
- MisFT の原典確認と Table A4 / `09_PAPER_PLAN.md` 論文 1 の下書き・`00_OVERVIEW.md` §7 の確定
- 凍結前(S5): T1c の件数(主・pilot)・統計・α・適格性の規則 / s の水準 / step 数と T2 の文面 / ★F104-c / ★F114(I7 の後)/ 平行性の TOST の Δ / シード分類の規則と閾値 / E1 の TOST 境界と α と検出力 / 天井 / ★L(d) / N5 / 本番テンプレート集合 / `θ` の根拠
- ★R8 の push と G2-1 承認 / 2 系統目の選定(本実験の後)/ ★`CLAUDE.md` を 200 行へ戻す / 旧 4 本と `9matkiq0jozcgm` の terminate / 価値レビューの引用の原典確認(会場未照合 6 件)
