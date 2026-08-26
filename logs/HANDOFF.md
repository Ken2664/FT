# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-26 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **A-6 が完了し、段階 A が終わった**(1セッション = 1 PLAN。`CLAUDE.md` §10.2)
直近 commit: `89f24bc`(feat(data_gen): 評価プールを書き出す CLI を実装し preflight の検査6・8 を PASS にした)

---

## ★ まず読むこと

**段階 A(GPU 不要のコード作業)は 2026-08-26 に完了した。**
`CLAUDE.md` §1 の開始手順を実行したうえで、**下の「次に何をするか」を読んでから
作業を選ぶこと。**エージェントが人間の入力なしで単独に進められる実装作業は、いま無い。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-033 を人間が採択した。**★A-5 が回避していた未解決の決着:
  プール manifest を **`reference_rules`(加算側 = `eligible_pairs` に渡した規則)**と
  **`specificity_reference_rules`(`spec_sub` / `spec_mul`)**の**2欄に分ける**。
  混ぜる案は「`eval.reference_rule: spec_sub` の誤指定を検査が素通しする」ため却下
- **`code/data_gen/eval_pool.py`(新規)**が評価プールを書き出す。
  `python -m code.data_gen.eval_pool --config configs/smoke.yaml [--dry-run] [--out-dir]`
- **`infra/preflight.py` の `data_checks` 6項目がすべて PASS**
  (`--config configs/smoke.yaml`)。**検査6 = format hash / 検査8 = coverage_k floor**
- `pool.build_manifest` に必須引数2つ(`specificity_reference_rules` / `fill`)
- `code/eval/battery/build.py`(新規)= 明示リストから4群の項目を作るディスパッチャ
- `ft_data.py` の CLI に `--condition`
- **`.gitignore` が壊れていたのを直した。**`data/generated/**/manifest.json` が
  初めて実際に追跡されるようになった(manifest 4件が入っている)
- `pytest code/tests -q` → **423 passed**(2026-08-26 実測)
- **実験結果の数値は1つも無い。**`results/` は空。GPU 時間 0。事前登録は未凍結(tag なし)
- 詳細は `STATE.md` の「引き継ぎ」と `logs/CHANGELOG.md` 2026-08-26

## 次に何をするか(**人間に選ばせること**)

段階 A が終わったので、**残りはすべて人間の入力か GPU の承認が要る**
(`STATE.md`「Phase 0 に必要な段階」)。

| 選択肢 | 役割 | 要るもの |
|---|---|---|
| **段階 B**: 承認待ちの決着(#18 / #19 / #9 / #13 / #15 / #16・#11 / PLAN-002 §12-11) | PLANNER | **人間の決定**。凍結の前に全部要る |
| **段階 C**: `none` モデルで桁数掃引 → `M*` と `θ` を実測(C-1) | RUNNER | **GPU の承認**(`CLAUDE.md` §2)。RunPod |
| **実装の前倒し**: `run.py` の本実行(モデルの読み込みと生成) | IMPLEMENTER | 既定のモデル名・生成設定は**実験条件**。人間が決めるまで着手不可(skill code-style §5) |
| **文献側**: 承認待ち-17(Nikankin et al. 2025 の原典確認) | SCOUT | なし。**subagent に委譲してよい**(`AGENTS.md` §SCOUT) |

**エージェントの判断で勝手に段階 C に進まないこと。**

## 未解決 / 人間の承認待ち(独断で決めない)

- **#15 外挿域の上限 `M*`。**★いま最も効いている —— **これが決まるまで評価プールは
  サンプリングできない**(`extrap` セルが原理的に埋まらないので、明示リストで
  埋めている。ADR-033 決定4)。`M*` は段階 C の実測が入力になる
- **#18** T1 にも答え書式の指示を足すか(ADR-032 決定3 の交絡)
- **#19** 被演算子 1 の除外を全タスク型に広げるか
- **#9** 適格性フィルタ 0.70 / **#16・#11** Feucht と G7 / **#13** `table[1]` の穴
- **PLAN-002 §12-11** `p2d` 判別不能の除外を `K` の抽出母集団に掛けるか
- **実装で決めた命名**(凍結までに人間が一度見ること。`STATE.md`「実装で確定させた点」
  の表 1〜9): 群名 `bare_sum` / `specificity`、category `t1` / `spec_sub` / `spec_mul`、
  **T2 のテンプレート割当を `(pool_id, a, b)` の sha256 にした**、
  `report["by_batch"]` のバッチ名、**manifest の欄名
  `specificity_reference_rules` / `fill`**、config のキー `eval.pool_items` /
  `eval.pool_seed` / `eval.extrapolation_radius` / `eval.extrapolation_run_id`、
  `ft_data.py --condition`、`configs/smoke.yaml` の T2 の5組の差し替え

## 既知の穴(実装。次に触る人へ)

- **本実行(モデルの読み込みと生成)は `NotImplementedError`。**4群が通るのは
  `--dry-run` の経路だけである
- **評価プールはサンプリングしていない。**`eval.pool_items` の明示リスト。
  `M*` が決まったら `pool.fill_cells` を呼ぶ経路に置き換わり、
  `manifest["fill"]["method"]` が `explicit_list` から変わる
- **`configs/smoke.yaml` は3条件(`p2` / `x2` / `ident`)しか宣言できない。**
  `digit_modulus` / `arbitrary_table` を持たないため。**本実験は5条件そろえること**
- **`infra/preflight.py` の `check_data_manifest` と `ft_data.py` の manifest schema が
  食い違う。**あちらは `files` の表を期待するが `ft_data.py` は `files` を書かない。
  **`data.manifest` を埋めると FAIL する**(いまはどの config でも `null` なので SKIP)。
  **どちらが正なのかは決めていない**
- `ruff` / `black` はこの環境に未インストール。行長 100(文字数)は手で確認すること
- **生成物の manifest には `created_at` と `git_commit` が入る。**再生成すると必ず
  差分が出る(`git_commit` は生成時点の HEAD なので、コミット後に再生成すると更新される)

## やってはいけないこと

- **`configs/templates/t2.yaml` を `data.eval_template_set` に配線しない。**
  T1b / T3 の本番文面が未確定でテンプレート集合が未完成である
- **T1b / T3 / T2 の本番文面を自分で書かない**(実験条件。`CLAUDE.md` §8)
- **`configs/templates/smoke.yaml` の仮文面を本番に昇格させない**
- **`eval.extrapolation_radius`(`M*`)に値を決め打ちしない。**段階 C の実測で決める
- **numeric パーサの「数が2個以上なら parse_fail」を緩めない**(PLAN-001 §5.4 の 4)
- 4値分解の合計を 1.0 から外さない。`data/raw/` を書き換えない
- **`spec_sub` / `spec_mul` を `reference_lesions_from_config` に混ぜない**
  (ADR-033 決定1。混ぜると FT データの除外集合が変わる)

## 状態(2026-08-26 時点)

- `pytest code/tests -q` → **423 passed**(3.8 秒)。`results/` は空。GPU 時間 0
- **preflight の `data_checks` 6項目は PASS**(`configs/smoke.yaml`)
- 直近 commit: `89f24bc`(コード)/ このセッションの引き継ぎコミット
