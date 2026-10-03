# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-03(その137)/ 直前セッションの役割: PLANNER(★F114 の判断材料づくり)
直前セッションが終了した理由: **コンテキストが閾値(140k)を超えた**(hook の実測 約 171k。`CLAUDE.md` §10.2)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus**(★F114 の実行先・★F104-c の値を人間に諮る / Δ・`glmer` の例外の規則の材料は判断系。`Documents/10_CONTEXT_POLICY.md` §7)。PLAN-037 の I10 だけなら Sonnet でよい。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**(Sonnet で判断系の作業になりそうなら止めて人間に伝える)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**。それ以外が出たら作業の前に人間に報告)。**人間の最初の指示が先**です。指示が無ければ、次を判断材料と推奨(下の A を推奨)を付けて聞いてください。

## A: ★F114 の実行先と ★F104-c の値を人間に決めてもらう(PLANNER / Opus)

材料はそろっている(**前セッションで人間に一度示した**。結論は人間がまだ出していない):
- **並列の実測**(`plans/PLAN-034-check-f114/bench_timing.txt`。借り物の `s2_* = 0.25`・I7 と同じ 4 条件 × 16 反復 = 64 ペア・16 並列。数値は主張に使わない): この機械(Ryzen AI 7 350・物理 8 / 論理 16・30 GB・ノート PC)で壁時計 875.1 秒 = **13.7 秒 / ペア**(I7 の逐次平均 136.8 秒の約 10 倍)。`glmer` の例外 0・縮退 25 / 64。**32,000 ペアへ外挿すると約 122 時間(約 5.1 日。未検証の外挿。本番の 32 点は `sigma`・`rho` の混ざり方が違う)**
- **RunPod の CPU ポッド**: 1 本 32 vCPU まで。cpu3c 0.96 ドル / 時・cpu5c 1.12 ドル / 時。**2026-10-03 の照会では 16・32 vCPU とも 6 種すべて在庫 `NONE`**。次に諮るときは在庫を照会し直す(`list-cpu-types` の AVAILABILITY)
- **★F104-c の賭け金(現模型で出し直し)**(`plans/PLAN-034-check-f114/stakes_t1t2.log`): `s2_item` = 0.25 / 0.5 / 1 / 2 / 4 で交互作用に乗る非加法性 RMS = P1 の 14 / 20 / 28 / 40 / 56%、各係数の SD = 0.11 / 0.16 / 0.22 / 0.32 / 0.45(= √(s2_item/20))。`s2_tmpl`・`sigma` は厳密に 0(★F118 の「0 に近い値を置かない」は残る)。**直接の水路だけ。二項の水路は測っていない**
- **エージェントは `s2_*` の値を提案しない**(ADR-095 決定3)。実行先は推奨を付けてよい(手続き・費用からの推奨)

決まったら: `configs/power_sim.yaml` の `s2_*` を埋める ADR → 本実行(`python -m code.analysis.power_sim --config configs/power_sim.yaml --out-dir results/power_sim --workers 16`。この機械なら AC 電源・スリープ無効。再開できる実装)。

## B: PLAN-037 の I10(人間の承認の後。Sonnet 可)

- `Documents/04_EXPERIMENT_PLAN.md` Phase 1「評価の追加」と `05_STATISTICS.md` §4 に実装の場所の注を 1 行ずつ(旧文は消さない)

## 直前セッションで確定したこと(ファイルに反映済み)

- 上の材料は `plans/PLAN-034-check-f114/`(README・スクリプト 2 本・config・出力 2 本)・`plans/PLAN-034` §12・`logs/OPEN-ITEMS.md` の ★F114 / ★F104-c の行に記録した
- ベンチの `power_sim_summary.json`(借り物の値の検出力)は repo に入れていない
- RunPod の pod は 5 本とも `EXITED`(稼働 0)を 2026-10-03 に確認した

## やってはいけないこと

- **ADR-111〜118 を覆さない**
- **値を決めない・提案しない**: `s2_item` / `s2_tmpl` / 平行性の TOST の Δ / D7 の閾値 / T1c の件数・統計・α / s の水準 / step 数 / T2 の文面 / `eval.freeze_tag` ほか
- **本実行(`s2_*` を借りて回す)をしない**。借り物の値の検出力の数値を文書・results に書かない
- **MisFT を ✅ にしない・「初めて」と書かない / tag・push・pod の起動をしない**
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。日本語の長い編集は Write でスクリプトを作り Python(`newline="\n"`)で入れる。Python に渡すパスは `cygpath -m` で変換する(`/c/...` は glob で拾えない)。`grep -c $'\r'` は Git Bash で当てにならない(Python で数える)
- STATE.md は 365 行・59.1 KB(上限 400 行 / 60 KB)。**次に足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- ★F114 の実行先・★F104-c の値 / 次の作業(A / B)
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
