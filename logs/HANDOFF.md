# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-07(その16b)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(hook `context-guard` が約 167k で警告。閾値 140k)。
**やること自体は終わっている** —— PLAN-017 を起草し、人間が 7 件すべてを決定し、記録した。
GPU 時間 0。`code/` の変更 0 行。`pytest code/tests -q` = **811 passed**(実行して確認した)。

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装の前に skill `code-style` を読むこと。

---

## ★このセッションでやること(1 つだけ)

**`plans/PLAN-017-analysis-frame.md` §6 を実装する。仕様は決まっている。**

完了条件は次の 5 つである。

1. **`code/data_gen/pool.py` に `label_main_coverage` を足す**(E-1 = 案 (c))。
   **`label_coverage` の 4 値を §3.2 の主軸の水準へ落とす。**
   **★`extrap_magnitude` は「`a > main_radius` かつ `b > main_radius`」である**(ADR-027 決定1)。
   **`100` をリテラルで書かない**(`main_radius` = `data.train_domain_max` = 99。skill `code-style` §1)
2. **`code/analysis/frame.py` を書く**(PLAN-017 §4.1 の 6 手順)。
   **`--dry-run` で件数だけ出す経路を持たせる。★主軸から落とした行の件数を run ごとに記録する**
3. **`task` の写像**(E-3 = 案 (c))。`code/analysis/` に薄い dispatch を置き、既存の
   `numeric_sum.task_type_of`(`code/eval/battery/numeric_sum.py:120`)と
   `t3_comparison.task_type_of`(`code/eval/battery/t3_comparison.py:116`)を**そのまま呼ぶ。
   写像表を 3 つ目に作らない。未知の `category` で必ず落ちること**をテストで固定する
4. **`template` の写像**(E-2 = 案 (a))。**`category` をそのまま水準にする。主軸は 10 水準**
5. **`pytest code/tests` に PLAN-017 §8 の回帰テストを足す。**
   **★最重要は「`(300, 50)` と `(-99, 1)` が `extrap_magnitude` に落ちないこと」である**

---

## 直前セッション(その16 / その16b)で確定したこと(すべてファイルに書き込み済み)

**人間が 7 件を決定した(ADR-062)。エージェントは材料を並べ、決定を記録しただけである。**

| 記号 | 決定 | 中身 |
|---|---|---|
| **E-1** | **案 (c)** | `frame.py` は **5 水準**を出す(`id` / `interp` / `extrap_magnitude` / `extrap_pair` / `oob_algebraic`)。**絞り込みの定義は `pool.py` に置く** |
| **★E-2** | **案 (a)** | **`category` をそのまま `template` の水準とする。主軸 10 水準**(`t1` 1 + `t2_*` 5 + `t3_gt` / `t3_lt` 2 + `t1b_gt` / `t1b_lt` 2) |
| **E-3** | **案 (c)** | 薄い dispatch。既存の `task_type_of` 2 本を呼ぶ。**`specificity` / `t1_instructed` は「主軸外」の明示的な印** |
| **E-4** | **案 (a)** | **`frame.py` は絞らない。**全 run・全群・全被覆水準を 1 枚に出し、`primary.py` が `subset` する |
| **E-5** | **案 (a)** | `config.yaml` の `data.matched_manifests` を `lesion.condition` で辿り、**`coverage.pairs_hash` を照合する** |
| **E-6** | **案 (c)** | 門の生の量(run ごとの `id` 到達度)を列にする。**二値化は `primary.py`。閾値は未決**(N5) |
| **E-7** | **案 (c)** | `results/` に CSV + ハッシュ + 入力 run_id 一覧 + FT manifest の `pairs_hash` |

**→ `logs/DECISIONS.md` に ADR-062。`plans/PLAN-017-analysis-frame.md` §5.0 に決定表。**
**★PLAN-017 の未決は 1 件も残っていない。ステータスは `採択`。残るのは実装である。**

**★`Documents/05_STATISTICS.md` §3.2 の `template` の行を書き換えた**(E-2 の帰結)。
**旧記述(「T2 の5テンプレート + T3 の質問文。T1 / T1b は単一なので水準1」)は §3.2.2 に
打ち消し線で残した。★旧記述は実装と食い違っていた** ——`t3_comparison.CATEGORY_AXES` は
T3 と T1b にそれぞれ 2 水準(`gt` / `lt`)を持つ。**実験は 1 件も実行しておらず `results/` は空
なので事後変更ではない。**

### ★実地で確認した事実(F63 〜 F79。推測ではない。PLAN-017 §2)

**PLAN-016 §5 の棚卸しのうち 3 点が事実と食い違っていた。正本は PLAN-017 §2 である。**

- **`code/eval/battery/battery_items.py` は存在しない。**実体は **`code/data_gen/battery_items.py:54`**
- **`coverage` を付ける関数はある**(**`code/data_gen/pool.py:144`** の `label_coverage`)。
  **無いのは呼び出し経路である**(`code/analysis/` からの呼び出しは 0 件)
- **`group` から `task` は決まらない。**`comparison` 群は **T3 と T1b の両方**を含む。
  **写像関数は既に 2 本ある。無いのは束ねる 1 箇所である**
- **★`label_coverage` の返り値 4 値 → §3.2 の 3 水準は恒等ではない。**`extrap_magnitude` は返り値に無い。
  **`(300, 50)` は `extrap` かつ `ans_out` だが `extrap_magnitude` ではない**(片側が域内)。
  **答え域の軸(`label_answer_range`)で代用すると別の集合になる**
- **順1b は `condition` と `passes_analysis_gate` も要る**(PLAN-016 §5 の列の一覧に無かった)
- **本実験 5 条件の K は同一である**(実測。`coverage.pairs` 2000 組・同一内容。`pairs_hash` あり)
- **K は `runs/<id>/` に無い。**FT manifest 側にある。**評価プールの manifest には `coverage_sums` しか
  無く、`label_coverage` には足りない**
- **`runs/*/predictions/` は `.gitignore` で外れている。長形式表は repo だけからは再現できない**
- **`metrics.json` の `seed` は訓練 run の seed である**(アダプタ無しなら `None`。**0 を置かない**)
- **同じ (項目, 実行) が複数行になる経路は無い**(`code/eval/run.py:435` の `scoring_batches`)

### ★決定に伴って残ったリスク(ADR-062 のリスク欄。実験前に記録した。上げ直さないが忘れない)

**極性(`gt` / `lt`)は応答バイアス対策として均衡させた設計因子であり、ランダム効果の水準として
扱ってよいかは未検証である** / **`template` は `task` に入れ子である**(§3.2 は `(1 \| template)` と
交差の形で書いている。**論文に明記する**)/ **単一テンプレートのタスク型ではランダム切片が `task` の
固定効果と区別できない**(案 (a) では単一は T1 の 1 つだけ)/ **事前予測検査は回していない**(ADR-061)。

---

## 触ってよいファイル / 読むべき範囲

- **`code/analysis/frame.py`** ← **新規に書く先である**
- **`code/data_gen/pool.py`**(`label_coverage` は :144、定数は :41-44、`label_answer_range` は :180)
- **`code/tests/test_pool.py`**(`label_coverage` の既存テストは :330 付近)
- **`plans/PLAN-017-analysis-frame.md`**(**§3(列と出どころ)/ §4(照合の手順)/ §5.0(決定)/
  §8(交絡と検査)だけ読めば足りる**。節の特定は grep で行い、全文を読まない)
- `Documents/05_STATISTICS.md` **§3.2**。**全文を読まない**(750 行超)
- **`STATE.md` は 3,800 行を超えた。全文を読まない。**見出しを grep して該当箇所だけ開く
- `logs/DECISIONS.md` の **ADR-062**。**全文を読まない**(3,800 行超)

---

## やってはいけないこと

- **★`Documents/05_STATISTICS.md` §3.2 をさらに書き換える。**E-2 の帰結は既に書き込んである
- **★`code/eval/run.py` を触る**(E-5 の案 (b))。**スコープの拡大であり、人間の判断待ちである**
- **★E-1 〜 E-7 を上げ直す**(ADR-062 で全件決着)/ **D-1 〜 D-6 を上げ直す**(ADR-058 〜 061)/
  **D-A 〜 D-D を上げ直す**(ADR-057)
- **★`code/analysis/primary.py` を書く**(PLAN-016 §7-5。**このセッションの範囲外**)
- **解析門の閾値を決める**(N5)/ **`θ` を決める** / **`M*` を決める**(ADR-041 決定2・決定3)
- **`eval.cells` / `anchor_manifest` / `pool_items` を埋める**(**`M*` 待ち**)
- **事前登録の凍結タグを打つ**(Δ / ★2 / S5 が未決)
- **人間の承認なく GPU ジョブを起動する** / **ポッドを起動したまま放置する**

### ★この環境で実際に踏んだ地雷(その13 〜 その16b で確認済み)

- **★長い散文は Write ツールでスクラッチに `.py` を書き、`python file.py` で本文に差し込む。**
  **その16b はこの方式に戻して通した。**ヒアドキュメント `python - <<'PYEOF'` は短い編集では通るが、
  **長い日本語本文を入れると bash が引用符の対応を見失って落ちる**(その16b で実際に落ちた)。
  **`cat > file <<'EOF'` は常に落ちる**
- **★`.md` を書き戻すときは `newline="\n"` を明示する**(`.gitattributes` は `* text=auto eol=lf`)。
  **書いたらバイト単位で CR 数を数える**
- **★入れ子太字 `****` は「追記した文字列だけ」に `\*{3,}` を掛けて数える。**
  **その16b は 6 か所で踏んだ** ——`**A。****B**` の形になる。`**A。** **B**` に直す。
  **ファイル全体に掛けると既存の `****` を拾うので、`git diff` の追加行だけに掛ける**
- **★`print()` に日本語や em dash を流さない**(この環境の Python の stdout は cp932)。
  **検証の出力は ASCII だけにする。**`git diff` を Python から読むときは `encoding='utf-8'` を明示する
- **★`python -c "..."` の中にバッククォートを書くと bash がコマンド置換として食う。**
  **正規表現のバックスラッシュも `-c` では消える**
- **★Markdown の表のセルに縦棒を書くときは escape する**
- **★`Rscript -e '...'` の二重引用符が Windows で壊れる。**R は `.R` ファイルにして回す
- **`logs/CHANGELOG.md` は古い順である**(新しいものが末尾)
- **`pytest code/tests -q` は 24 〜 59 秒**(811 tests)。`timeout` を伸ばす

---

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

- **★E-5 の案 (b)**(K の出どころを評価 run の `metrics.json` に焼き込む)。**新しく開いた 1 件。**
  **`code/eval/run.py` の変更なのでスコープの拡大である。★採るなら本実験の前でなければ意味が無い。**
  **本実験の run はまだ 1 本も無いので、いまが最も安い。判断に期限がある**
- **★`θ` の値**(ADR-041 決定2・決定3)。**順5 を回す前に決まっていなければならない。
  表を見てから決めると事後選択になる。これが順5 の唯一の残りブロッカーである**
- **★Phase 1 本実験 40 run の GPU 構成**(ADR-057 決定2 の帰結)
- **解析側の凍結手段**(ADR-058 決定2 の帰結)。`renv.lock` を repo に置くかどうか
- **★2**(`plans/PLAN-013` §4)/ **S5**(同 §9。**★事前分布と連動する**)/ **F15 の扱い** /
  **N1 / N2 / N3〜N6 / #7** / **解析門の閾値**(ADR-054 決定1 (ii)。N5)
- **`Documents/05_STATISTICS.md` §5 の Δ 5 行すべて**(順6 の実測待ち)
- **LoRA グリッドの値** / **`K` を掃引軸にするか** / **凍結(段階 D)をパイロットの前か後か** /
  **`revision` に `[MATCHED]` タグを付けるか**
- **`Documents/00_OVERVIEW.md:7` の問いが二値のまま**(ADR-056 が人間に上げた)
- `refs.bib` の Nikankin 書誌の最終確認 / ADR-047 実装ノートの R3 / F1 / R4 / 検査5

### ★「本筋との整合」の指摘(★A = ADR-056、★D = ADR-058 〜 062 で閉じた)

| 記号 | 指摘 | 状態 |
|---|---|---|
| **★B** | **ゲートキーピングが主問いの判別子を門の後ろに置いている。**非有意は研究仮説 H1 が予測する結果でもある。案: 順7 を門の外に出す / 門の条件に TOST を加える / 共主要 2 本に α を分割 | **未決** |
| **★C** | **解析門が DiD のベースライン腕そのものに掛かっている**(ADR-054 決定1 (ii))。**従属変数での選択。★E-6 = 案 (c) はこの決着に対して中立である**(生の量を列にするだけ)。**N5 で閾値を凍結するときが決め時** | **未決** |
| **★D** | 当てはめエンジンが無い | **→ 閉じた**(ADR-058 〜 061)。**長形式表の仕様も閉じた**(ADR-062)。**残るのは実装だけである** |
| **★E** | **F15 は設計判断ではなくバグである**(`torch.manual_seed` が 0 件)。案: バグとして直し、**ADR-055 決定2 の結論は変えず根拠を統計的な理由に差し替える** | **未決** |
| **★F** | **シード配分が主問いの判別子に薄い**(`arb` は 5 シード) | **未決** |

### 順6(評価プールを使う段)の前提 — 順5 ではなくここに置く

**ADR-057 決定4。どちらも `comparison` 群(= 評価プール)を要求するので掃引では成立しない。**
**(1) バッチ fp ノイズ検査**(ADR-040 決定7。**GPU が要る**)/
**(2) preflight の `forced choice tokens`**(ADR-047 実装ノート 5。**重みは読まないのでローカルで取れる**)。

**★`ADR-044`(`infra/requirements.lock` の凍結)は順5 のままである。**
**★ローカル環境**: **R 4.6.1 と `lme4 2.0.6` が入っている**。**`rstanarm` / `brms` は入れていない**
(ADR-061 の未検証欄)。`statsmodels` は外したままである。**`infra/requirements.lock` は無変更である。**
