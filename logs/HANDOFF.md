# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-03(その138)/ 直前セッションの役割: PLANNER(★F114・★F104-c を人間に諮った)
直前セッションが終了した理由: **コンテキストが閾値を超えた**(hook の実測 約 130k。`CLAUDE.md` §10.2)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus**(PLAN-039 の D1〜D5 を人間に諮る・統計の判断。`Documents/10_CONTEXT_POLICY.md` §7)。PLAN-037 の I10 だけなら Sonnet でよい。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**(Sonnet で判断系の作業になりそうなら止めて人間に伝える)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**。それ以外が出たら作業の前に人間に報告)。**人間の最初の指示が先**です。指示が無ければ、次を判断材料と推奨(下の A を推奨)を付けて聞いてください。

## A: PLAN-039 —— `s2_item` をパイロット FT の `p2` 2 シードから推定する(PLANNER / Opus)

- **ADR-119 で決まったこと**(人間): ★F114 の実行先 = **この機械**(16 並列)/ **`s2_tmpl` = 0.5** / `s2_item` は**先にパイロットから推定し、結果を見て人間が値を決める** / **ADR-095 決定3(エージェントは `s2_*` を提案しない)は ★F104-c に限って人間の指示で外した**(他の値には及ばない)
- 前セッションでエージェントが出した例の値と推奨(記録。ADR-119 文脈3): 0.5 / 1.0 / 2.0 / 4.0。「今決めるなら 2.0 / 0.5(安全側)、全体としては先にパイロットから推定」
- **PLAN-039 は草案**(`plans/PLAN-039-s2-item-from-pilot.md`)。**最初に §4 の D1〜D5 を判断材料の表と推奨つきで人間に確認する**(ADR-097 決定6): D1 step(625 / 313 / 両方)/ D2 式(`is_rule ~ task * coverage + (1|seed) + (1|item)`、T2 の `(1|template)`、タスク別か)/ D3 `ans_out` を含めるか / D4 天井・床で分離したときの報告の形 / D5 何を出すか(値の推奨を出すか)
- データ: `runs/pilot_ft_eval_p2_s{0,1}`(625)・`runs/pilot_ft_eval_p2_s{0,1}_n313`(313)の `predictions/bare_sum.jsonl`・`word_problem.jsonl`(各 160 行。`classification == "rule"`)。被覆ラベルが行に無ければ manifest から引く(未確認)
- 推定は R(`lme4::glmer`。`power_sim_fit.R` と同じ環境)。結果は `results/s2_item_pilot/` に run_id とセットで書く
- 人間が値を決めたら: ADR → `configs/power_sim.yaml` に `s2_item` と `s2_tmpl: 0.5` → `--dry-run` → `pytest code/tests -q` → commit → 本実行 `python -m code.analysis.power_sim --config configs/power_sim.yaml --out-dir results/power_sim --workers 16`(背景。AC 電源・スリープ無効を確かめてから。再開できる実装。約 122 時間の外挿)

## B: PLAN-037 の I10(人間の承認の後。Sonnet 可)

- `Documents/04_EXPERIMENT_PLAN.md` Phase 1「評価の追加」と `05_STATISTICS.md` §4 に実装の場所の注を 1 行ずつ(旧文は消さない)

## やってはいけないこと

- **ADR-111〜119 を覆さない**
- **推定を見る前に `s2_item` の値を決めない。推定を見た後で取得元の規則を変えない**(PLAN-039 §6)
- **他の値を決めない・提案しない**: 平行性の TOST の Δ / D7 の閾値 / T1c の件数・統計・α / s の水準 / step 数 / T2 の文面 / `eval.freeze_tag` ほか(ADR-095 決定3 の外しは ★F104-c だけ)
- **借り物の値の検出力の数値を文書・results に書かない / MisFT を ✅ にしない・「初めて」と書かない / tag・push・pod の起動をしない**
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。日本語の長い編集は Python(`newline="\n"`)で入れる。Python に渡すパスは `cygpath -m` で変換する
- STATE.md は 365 行・58.6 KB(上限 400 行 / 60 KB)。**次に足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- PLAN-039 の D1〜D5 / `s2_item` の値 / 次の作業(A / B)
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
