# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-09(その31b)/ 直前セッションの役割: PLANNER / CRITIC (Opus)
直前セッションが終了した理由: **コンテキスト超過**(hook `infra/context_guard.py` が約 192k で警告。閾値 140k)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから
作業を始めてください。

## このセッションでやること(1 つだけ)

**ADR-071(2026-09-09 採択)を実装する。順5(桁数掃引)の残りはこれだけである。GPU は要らない。**

実装するもの:

1. **`code/eval/battery/magnitude_sweep.py`** —— **`Q(M)` から引く腕**を足す。
   - `Q(M) = { (a,b) : main_radius < a <= M, main_radius < b <= M }`。
     **定義をここに書き直さない。**`code/data_gen/pool.py` の `label_main_coverage` が
     `extrap_magnitude` を返すことで判定する(**リテラルの 99 を撒かない**。skill `code-style` §1)
   - **既存の `build_items`(`R(M)` からの一様抽出)は 1 文字も変えない**(ADR-071 決定2)
   - 引ける水準は **`|Q(M)| >= shell_n_items`** の水準だけ。**config の `shell_radii` は
     突き合わせに使う**(導出値と食い違ったら止める)。
     **★罠: `(M-99)^2` は `M < 99` でも正になる。`Q(M)` は `M <= 99` で 0 である**
     (`code/tests/test_design_facts.py` の `_quadrant_size` がこの罠を固定している)
2. **`code/eval/sweep.py`** —— **2 本の腕を測り、`metrics.json` に別ブロックで出す**。
   - 腕1(一様抽出)= 記述。累積の `correct_rate` と定義 A の格子殻(`predictions/` の
     `operands` から切り直せる。`code/eval/run.py:681`)
   - 腕2(`Q(M)`)= **判定**。`shell_judgement_radii` の上で 規則2 を走らせる材料
   - **4値分解は腕ごとに合計 1.0**(`CLAUDE.md` §6 / ADR-016)
   - **`M*` の判定コードそのものは書かない**(ADR-041 / 045 の思想。表を出すところまで)
3. **回帰テスト**(`code/tests/test_sweep.py` / `test_design_facts.py`)
4. **`plans/PLAN-001` §4.1.1** の手続き 1・2・3 に `Q(M)` の腕と判定水準の限定を書く
   (**打ち消し線 + 理由 + 日付**。`CLAUDE.md` §2。**ADR-071 が正本**)
5. `pytest code/tests -q` が緑(**開始時点で 914 passed**)
6. `logs/CHANGELOG.md` に追記 → commit → **★`logs/HANDOFF.md` も更新する**

## 直前セッションで確定したこと(すべてファイルに書き込み済み)

- **ADR-071 を採択した**(提案 エージェント (Opus) / 採択 人間)。**3 決定**:
  - **殻-a = D**: **判定は `Q(M)`**(= `extrap_magnitude` の母集団)。報告は累積と定義 A を併記
  - **殻-b = (c) 限定版**: 現行 13,000 項目はそのまま + **`Q(M)` から 7,000 項目**(計 20,000)。
    **GPU 1.5 → 2.5h**(`estimated_gpu_hours` を書き直した。**10h の門は超えない**)
  - **殻-c = c3**: **判定水準 = `{125, 150, 175, 200, 300, 500, 999}`**
    (凍結済の 200 件を `Q(M)` から引ける水準)。**新しい数を作らない**
- **★この採択の性質**: 人間の指示は「どれも AI の推奨案を採用する」であり、
  **PLAN-021 §4 に推奨は付いていなかったので、推奨案そのものをエージェントが ADR-071 で作った。**
  **選択肢の比較検討はエージェントが行っている。ADR-071 の冒頭に明記してある。蒸し返さない**
- **★帰結: 外挿腕の生死は `Q(125)` と `Q(150)` が θ = 0.70 を超えるかだけで決まる**
  (規則2 + ADR-070 決定3 B1 + ★F120)。**格子と規則の帰結であって実測ではない**
- **★F122 / ★F123 / ★F124** は `plans/PLAN-021` §0 と `logs/CHANGELOG.md`(その31)にある
- **★config の値**: `shell_definition: "extrap_magnitude_quadrant"` / `shell_n_items: 200` /
  `shell_radii` / `shell_judgement_radii` / `theta: 0.70`。**`extrapolation_radius`(`M*`)は `null` のまま**
- **★1 度だけ `test_power_sim.py::test_run_fits_writes_one_manifest_per_shard` が落ちた。**
  **単独再実行と全体の再実行では通る(914 passed)。並列 fixture の flaky が疑わしいが原因は未特定。
  また落ちたら追うこと**(`CLAUDE.md` §7)

## 触ってよいファイル / 読むべき範囲

- `logs/DECISIONS.md` の **ADR-071**(末尾)と **ADR-041**(`grep -n` → `sed -n 'X,Yp'`)
- `plans/PLAN-021-shell-measurement.md` §6(採択済の 3 行)/ §3.1(容量の表)
- `code/eval/battery/magnitude_sweep.py` / `code/eval/sweep.py` /
  `code/data_gen/pool.py` の `label_main_coverage`(195 行)
- **全文 `cat` しない。**`grep -n` → `sed -n 'X,Yp'`(`CLAUDE.md` §10.1)

## やってはいけないこと

- **`M*` の値を決めるコードを書かない。**掃引が出すのは表までである(ADR-041 / 045)
- **`θ = 0.70` の根拠を代筆しない。**規範的な線引きである(値は ADR-070 で確定)
- **ADR-071 の 3 決定を蒸し返さない。**採択済である
- **`extrapolation_radius` に値を書かない**(`null` のまま。順5 の実測が決める)
- **GPU を起動しない**(実装だけ。順5 の実行は別セッション)
- **`Documents/05_STATISTICS.md` と `configs/power_sim.yaml` を触らない**(★F104 待ち)

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8。索引は `logs/OPEN-ITEMS.md`)

- **★`θ = 0.70` の根拠**(ADR-041 決定2 の要求。**値は確定**)
- **★F104**(`s2_item` / `s2_tmpl` の取得元。`plans/PLAN-019` §10.13.5)
- **★F114 の実行先**(62 〜 372 時間をどこで回すか。★F104-a に従属)
- **順6 の GPU 承認** / **Phase 1 本実験 40 run の GPU 構成** / **LoRA グリッド**
- **N5**(解析門の閾値)/ **★C** / **★E** / **★L(d)** / **E-5 (b)** / **★2** / **PLAN-018 §4.3**
- **`Documents/09_PAPER_PLAN.md` と `00_OVERVIEW.md:7` が再設計前のまま**
