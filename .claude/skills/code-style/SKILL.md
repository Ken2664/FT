---
name: code-style
description: translesion プロジェクトの Python 実装規約(1関数1責務、マジックナンバー禁止、パーサの分離とユニットテスト、docstring に「答える問い」を書く)。code/ 配下の実装・レビュー・リファクタを行うとき、および IMPLEMENTER セッションの開始時に読む。Use when writing, reviewing, or refactoring Python code in this repository.
---

# コード規約(人間が読めることが最優先)

旧 `CLAUDE.md` §7。常時読み込みから外し、実装するときだけ読む(ADR-011)。
**この規約は `CLAUDE.md` に劣後する。**矛盾したら `CLAUDE.md` が優先。

---

## 1. 基本

- Python 3.11+、`ruff` + `black`、**型ヒント必須**
- コミット前に `pytest code/tests -q` が通ること(`CLAUDE.md` §4)
- マジックナンバー禁止。**すべて config に出す**。閾値・シード・学習率・項目数・rank をコードに直書きしない

## 2. 責務の分離

- **1関数1責務。**評価関数の中で学習しない、学習関数の中で集計しない
- 出力パーサは `code/eval/parsers/` に**独立モジュール**として置き、**必ずユニットテストを書く**
  - パーサの取りこぼしは `parse_fail_rate` に化けて結果を歪める。`CLAUDE.md` §7 が「まずバグを疑う」対象として名指ししているのがここ
- 学習 `code/train/`、評価 `code/eval/`、集計・統計 `code/analysis/`、プローブ `code/probe/` を跨がない

## 3. docstring とコメント

- docstring には**この関数が答える問い**を1行で書く
- 複雑な処理には**なぜそうしたか**をコメントに残す。何をしているかはコードを読めばわかる

```python
def rule_rate(preds: list[str], items: list[Item], lesion: Lesion) -> RateBreakdown:
    """病変規則の適用率を計算する。

    答える問い: Documents/03_OPEN_QUESTIONS.md Q2「病変は表記に依存するか」

    注意: rule_rate と error_rate を混同しないこと。真値と規則適用値が
    偶然一致する項目(例: 恒等的なケース)は除外する必要がある。
    """
```

## 4. 指標実装(`CLAUDE.md` §6 の実装側)

- 4値(`correct_rate` / `rule_rate` / `other_error_rate` / `parse_fail_rate`)は**排他的**で、**合計は必ず 1.0**
  - 合計が 1.0 になることをアサートするテストを書く
- 真値と規則適用値が一致する項目は**生成時に除外リストへ**。評価側で後から落とさない
- 4値のうち一部だけを返す関数を作らない。呼び出し側が報告漏れを起こす

## 5. 実装前に確認すること

- 仕様に曖昧な点があれば**実装せず質問として返す**(`AGENTS.md` IMPLEMENTER への依頼)
- config に無いパラメータが必要になったら、勝手に既定値を決めずプランファイルに追記して確認する
