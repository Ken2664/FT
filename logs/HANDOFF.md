# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-02(その136)/ 直前セッションの役割: IMPLEMENTER(PLAN-034 の I1〜I7 を実装した)
直前セッションが終了した理由: **コンテキストが閾値(140k)を超えた**(`CLAUDE.md` §10.2。PLAN-034 の実装が済んだ区切り)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: **Opus**(★F114 の実行先の諮り・S5 の値の決定の準備・Δ / `glmer` の例外の規則の設計は判断系。`Documents/10_CONTEXT_POLICY.md` §7)。PLAN-037 の I10 だけなら Sonnet でよい。**どれをやるか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**(Sonnet で判断系の作業になりそうなら止めて人間に伝える)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`git log` と `git worktree list` で並行セッションの commit・worktree が無いかも確かめる。**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**で、削除は人間待ち。それ以外が出たら作業の前に人間に報告)。**人間の最初の指示が先**です。指示が無ければ、次を判断材料と推奨(下の A を推奨)を付けて聞いてください。

## A: ★F114 の実行先を人間に諮る(PLANNER / Opus)

- 材料(すべて `plans/PLAN-034-power-t1t2.md` §12・`Documents/05_STATISTICS.md` §6.8「I7 の実測」): 検出力分析 = 4 シート 32 点 × 1000 反復 = 32,000 ペア(`--dry-run` が約 2,204 コア時と出す)。**推算(248 秒 / ペア)なら 16 並列で約 138 時間**。I7 の実測は 4,800 行の表 4 枚で 192.6 / 156.5 / 64.5 / 133.7 秒(平均 136.8 秒。借り物の `s2_* = 0.25`・4 枚だけ)で、平均を行数比例で外挿すれば約 76 時間(**未検証の外挿**)。この機械(16 コア)か RunPod の CPU ポッドか(`CLAUDE.md` §2: CPU は 10 GPU 時間の承認対象ではないが黙って始めない)
- **回す前に人間が決める入力**: `dgp.s2_item` / `dgp.s2_tmpl`(★F104-c。null で止まる)。判断材料の表を先に見せてから聞く(ADR-097 決定6)。**エージェントは値を提案しない**

## B: PLAN-037 の I10(人間の承認の後。Sonnet 可)

- `Documents/04_EXPERIMENT_PLAN.md` Phase 1「評価の追加」と `05_STATISTICS.md` §4 に実装の場所の注を 1 行ずつ(旧文は消さない)。**人間が承認してから**

## 入っているもの(PLAN-034 の I1〜I7。commit はこのセッションの末尾)

| I | ファイル | 要点 |
|---|---|---|
| I1 | `configs/power_sim.yaml`・`power_sim_smoke.yaml` | `effect.profiles`(P1 = RMS 0.352767 を保って delta を √(2/3) 倍 / P1_neg / P0。`rule_rate` の門は小数第 3 位)・`sheets:`(p1 12 点・p1_neg 2 点・p0 12 点・misspecification 6 点)・`simulation.tost_alpha: 0.05`・`dgp.n_item: 80`。**`s2_item` / `s2_tmpl` は null** |
| I2 | `code/analysis/power_sim.py` | `build_profile(effect, 名前)`(df ≠ 2 で止まる)/ `load_sheets`(役割とプロファイルの RMS の食い違いで止まる)/ `draw_frame(..., tau=)` / `equivalence_margin`・`tost_power`(Δ は呼び出し側)/ `compare_power` / `estimate_seconds_per_pair`(行数比例)/ `run` は出力を `<out>/<シート>/` に分ける |
| I3 | `code/analysis/power_sim_fit.R` | 交互作用 2 係数の推定値と SE(`interaction_<被覆>_est/_se`)・**`glmer` の例外を縮退の引き金にして数と文面を記録(`n_errored_fits`・`first_error`)** |
| I4 | `code/tests/test_power_sim.py` | 93 件(R は呼ばない。偽の当てはめで `run` を通す)|
| I5 | `Documents/05_STATISTICS.md` | §2(D6)・§3.3(D7)・§5(D5 の行)・§6 頭・§6.5〜§6.7 の注・**§6.8 新設**(旧文は消さない) |
| I7 | スクラッチパッドの実行 | 上の A の実測。`runs/` には置いていない |

`pytest code/tests -q` は現在 **2393 passed**(約 7.5 分。背景で回して `tail`)。実機のスモーク: `python -m code.analysis.power_sim --config configs/power_sim_smoke.yaml --out-dir <tmp>`(R 4.6.1・lme4 2.0.6 がこの機にある。約 3 分)。

## 直前セッションで確定したこと(ファイルに反映済み)

- **実装の段で足した判断(PLAN に明記なし。人間が覆してよい)**: (1) `glmer` が例外で落ちたら縮退へ進む(スモークの誤指定シート `n_item` = 2 で `Downdated VtV is not positive definite` を観測)。最後の水準でも落ちたら p 値 null で集計が止まる。**実データでの規則は未決**(`logs/OPEN-ITEMS.md` に行を足した)/ (2) 再開時も表を引き直して乱数を進める / (3) `logistic`(`math.exp` が溢れない)/ (4) シートの役割とプロファイルの食い違いで止まる / (5) 反復ごとの最小 Δ を保存(Δ は決めない)
- `n_item` = 80 の整数 1 つ(ADR-114 決定3)。`05_STATISTICS.md` の旧文(df = 6)は消していない

## やってはいけないこと

- **ADR-111〜118 を覆さない**
- **値を決めない・提案しない**: `s2_item` / `s2_tmpl`(★F104-c)/ 平行性の TOST の Δ / D7 のシード分類の閾値 / ★F114 の実行先 / T1c の件数・統計・α / s の水準 / step 数 / T2 の文面 / `eval.freeze_tag` の名前ほか
- **本実行(`power_sim` を `s2_*` を借りて回す)をしない**。借り物の値の数値を文書・results に書かない
- **MisFT を ✅ にしない・`refs.bib` に入れない・「初めて」と書かない**
- **tag を打たない・push しない・pod を起動しない**
- **この機は Windows**: `.md`・`.py`・`.yaml`・`.R` は LF 固定。**日本語の長い編集は Write でスクリプトを作って Python で入れる**(bash の heredoc の複数連結は構文エラーになる。実際に 1 回止まった)。`Write` で作ったファイルは `python` から UTF-8 で読む。**`s[:a]+new` のようにファイルの後ろを切り落とす置換をしない**(今回、テストの末尾を 1 度消して git から復元した)
- STATE.md は 366 行・60.7 KB(上限 400 行 / 60 KB。hygiene は通る)。**次に足すときは同じだけアーカイブへ移す**

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- 次の作業(A / B)・★F114 の実行先・★F104-c の値
- 平行性の TOST の Δ(「何を無視できる効果とみなすか」の理由を先に書く)・D7 の分類の閾値・`glmer` の例外の規則(新)
- S4 の T1c の順の確定 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認と Table A4 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目の選定 / ★`CLAUDE.md` を 200 行へ戻す / 旧 4 本と `9matkiq0jozcgm` の terminate / 価値レビューの引用の原典確認
