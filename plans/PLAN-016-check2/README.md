# PLAN-016 検査2 のスクリプト(2026-09-07 に実行したもの)

**`plans/PLAN-016-fitting-engine.md` §2 の F49〜F52 と §4.1 の R6 欄の出所である。**
**ここに置いたのは、数値の出所を後から監査できるようにするためである**(`CLAUDE.md` §2)。

## これは何ではないか

- **パイプラインのコードではない。**`code/` に置いていないのは意図的である。
  `code/analysis/primary.py` は D-1(ADR-058 で決着)を受けて**別に書く**(PLAN-016 §7)
- **`pytest code/tests` の対象ではない。**回帰テストではなく、一度きりの性能測定である
- **実データを一切読まない。**すべて合成データである(PLAN-016 §8)
- **本番の見積もりではない。**項目数は `M*`(順5 の出力)待ちであり、
  **ここで掃いた規模は暫定である**(PLAN-016 §8 の最終行)

## 2 本の役割

| ファイル | 答える問い |
|---|---|
| `gen_frame.py` | §3.2 が要求する長形式表を合成する。**生成モデルは検査1 と同じ設計**である(`check1_statsmodels_r3.py` の `make_frame`)。規模(`--n-seed` / `--n-item-per-coverage`)だけを掃く |
| `fit_timing.R` | **`glmer` の 1 fit が何秒かかるか**(R6)。入れ子 2 本を当てて `anova(..., test = "LRT")` を回し、壁時計と検定統計量と収束コードを JSON に書く |

**`item` は `task` および `seed` と交差している** —— 同じ被演算子対が 4 つのタスク型すべてで、
かつすべてのシードで問われる。`coverage` は項目の属性である(§3.2 の `(1 | item)` の定義)。

## 回し方

R は 2026-09-07 に `winget install --id RProject.R` で入れた(**4.6.1**)。
`lme4` は個人ライブラリ `C:/Users/keenk/AppData/Local/R/win-library/4.6` に入れてある
(`Program Files` 側のライブラリに書かないため)。

```bash
D=plans/PLAN-016-check2
RS="/c/Program Files/R/R-4.6.1/bin/Rscript.exe"
LIB="C:/Users/keenk/AppData/Local/R/win-library/4.6"
python "$D/gen_frame.py" --out "$D/frame_i24.csv" --n-seed 10 --n-item-per-coverage 24
"$RS" "$D/fit_timing.R" "$D/frame_i24.csv" "$D/timing_i24.json" "$LIB"
```

`--interaction-scale 0.0` が加法の真値、`1.0` が交互作用ありの真値である
(検査1 の `make_frame` と同じ係数表を使う)。**規定は 0.0 である** ——
**R6 は速度の測定であって検出力の測定ではない**ので、真値は加法側に固定してある。

出力(`frame_*.csv` / `timing_*.json`)は `.gitignore` に入れてある。
**数値の正本は `plans/PLAN-016-fitting-engine.md` §2 である。**
