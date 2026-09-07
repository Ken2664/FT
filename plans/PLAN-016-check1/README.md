# PLAN-016 検査1 のスクリプト(2026-09-07 に実行したもの)

**`plans/PLAN-016-fitting-engine.md` §2 の F41〜F47 と §4.4 の出所である。**
**ここに置いたのは、数値の出所を後から監査できるようにするためである**(`CLAUDE.md` §2)。

## これは何ではないか

- **パイプラインのコードではない。**`code/` に置いていないのは意図的である。
  `code/analysis/primary.py` を書くのは **D-1(エンジン)が決まってから**である(PLAN-016 §7)
- **`pytest code/tests` の対象ではない。**回帰テストではなく、一度きりの適合性検査である
- **実データを一切読まない。**すべて合成データである(PLAN-016 §8)

## 3 本の役割

| ファイル | 答える問い |
|---|---|
| `check1_statsmodels_r3.py` | `BinomialBayesMixedGLM` の返り値に `llf` に相当する量があるか。`vc_formula` で交差ランダム切片 3 本が組めるか(R2) |
| `check1b_calibration.py` | `fit_map` が収束しないのは設定のせいか(4 通りを試す)。**入れ子 2 本の ELBO の差は χ² になっているか**(加法の真値で 200 反復) |
| `check1c_signal.py` | **合成データ側のバグではないことの確認。**同じ表に固定効果だけの二項 GLM の LRT を当てて較正を見る(`CLAUDE.md` §7) |

`check1b` と `check1c` は `check1_statsmodels_r3` から `make_frame` / `build` を import する。
**3 本は同じディレクトリに置いたままにすること。**

## 回し方

**`statsmodels` は 2026-09-07 に意図的にアンインストールした** ——
**案 D は R3 で落ちたので、解析エンジンとして環境に残す理由が無いためである。**
再現するときは一時的に入れ直す。

```bash
python -m pip install statsmodels
cd plans/PLAN-016-check1
python check1_statsmodels_r3.py     # 数秒
python check1b_calibration.py       # 約 1 分(400 fit)
python check1c_signal.py            # 約 1 分(200 fit + 200 GLM)
python -m pip uninstall -y statsmodels patsy formulaic interface-meta wrapt
```

**出力の `check1_out.json` / `check1b_out.json` / `check1c_out.json` は
カレントディレクトリに落ちる。`.gitignore` していないので、
回したあとに消すか、意図して commit するかを決めること。**

## 環境についての注意

- 2026-09-07 の実行環境は **Windows / Python 3.14.3 / statsmodels 0.15.0 /
  numpy 2.4.6 / scipy 1.18.0 / pandas 3.0.5** である
- **`print()` は ASCII だけにしてある。**この環境の Python の stdout は cp932 で、
  em dash や日本語を流すと `UnicodeEncodeError` になる
- `statsmodels` を入れると依存に **`wrapt 2.4.1rc1`(release candidate)** が入る。
  **`pip freeze` で凍結すると rc を pin することになる**(ADR-044 / R8)
