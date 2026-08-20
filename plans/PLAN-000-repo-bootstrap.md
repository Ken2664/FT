# PLAN-000: repo の骨格整備(非実験)

> **これは実験プランではない。**GPU を使わず、事前登録の対象でもない。
> `plans/TEMPLATE.md` の節番号は踏襲するが、実験固有の節は「該当なし」と理由を書く。

- 作成日: 2026-08-20
- 最終更新: 2026-08-20
- ステータス: `完了`
- 担当: IMPLEMENTER(エージェント)/ 承認は人間
- 関連する問い: `Documents/03_OPEN_QUESTIONS.md` Q-3
- 関連する仮説: 該当なし(設計の前提を固定するだけで、仮説を検証しない)

---

## 1. この実験が答える問い

**「実験を開始できる状態か」。**

設計文書は完成していたが、それらが参照するディレクトリ(`Documents/`, `code/`,
`configs/`, `runs/` ほか)が実在せず、repo が git 管理下にもなかった。
`STATE.md` の「現在のブロッカー」がこれを名指ししていた。

---

## 2. 予測(実行前に記入。実行後に変更しない)

該当なし。**測定を行わないため予測がない。**事前登録の対象外。

---

## 3. 実験条件

該当なし。病変 FT を回さないため対照条件が要らない。
(`TEMPLATE.md` の「対照条件が空欄なら実行してはならない」は測定を伴う
プランに対する規則であり、本プランは測定を伴わない)

---

## 4. データ

生成しない。`data/raw/` と `data/generated/` は空のまま作成のみ。

---

## 5. 評価

該当なし。ただし**評価系の前提となる代数だけ**をコードで固定した(§下記「やったこと」)。

---

## 6. 統計

該当なし。

---

## 7. 想定される交絡と対策

| 交絡 | 対策 | 実装場所 |
|---|---|---|
| `code` パッケージ名が標準ライブラリ `code` と衝突し、pytest が起動しない | 標準ライブラリの公開名を再エクスポート。テストと preflight で常時検査 | `code/__init__.py`, `code/tests/test_import_shim.py`, `infra/preflight.py` |
| 文書の相互参照が移動で壊れる | 移動後に全参照を検査し、生きた参照だけ修正。`logs/` は追記のみなので触らない | 本プラン §やったこと |
| `requirements.lock` を手で埋めて再現性が壊れる | 空のまま置き、埋め方だけを書く。bootstrap は空のとき警告、preflight は WARN | `infra/requirements.lock` |
| config の未決定値がコード側の既定値で埋まる | 全て `null` + `# TODO` を明示。コードは既定値を作らず落ちる | `configs/template.yaml`, `code/lesion.py` |

---

## 8. 必要なリソース

GPU 時間 0。人間の承認が必要な閾値(10 GPU時間, `CLAUDE.md` §2)には該当しない。

---

## 9. 完了条件

- [x] `pytest code/tests -q` が通る(40 passed)
- [ ] `--dry-run` が成功する → **未達**。`code/eval/run.py` は PLAN-001 の範囲
- [x] 予測を凍結し git tag を打った → 該当なし(予測がない)
- [x] `README.md` が記述するディレクトリ構造が実在する
- [x] git 管理下に置き、初回コミットを作った
- [x] `infra/preflight.py` が実行でき、FAIL/WARN を正しく報告する
- [x] `STATE.md` と `logs/CHANGELOG.md` を更新した
- [ ] CRITIC のレビューを受けた → **未達**

---

## 10. 実行ログ

| 日付 | 何をしたか | run_id | 担当 |
|---|---|---|---|
| 2026-08-20 | ディレクトリ作成・文書移動・git init・骨格実装 | 該当なし(実験ではない) | IMPLEMENTER |

---

## やったこと(詳細)

### 10.1 ディレクトリの実体化

`README.md` の構造図どおりに作成し、ルートに平置きされていた文書を移した。

| 移動元 | 移動先 |
|---|---|
| `00_*.md` … `10_*.md`, `refs.bib` | `Documents/` |
| `CHANGELOG.md`, `DECISIONS.md` | `logs/` |
| `RUNPOD.md` | `infra/` |
| `TEMPLATE.md` | `plans/` |

ルートに残したのは `README.md` / `CLAUDE.md` / `AGENTS.md` / `STATE.md` / `.claude/`。

### 10.2 壊れた相互参照の修正

移動で解決しなくなった**生きた参照のみ**を直した。

- `CLAUDE.md`: `05_STATISTICS.md` → `Documents/05_STATISTICS.md`、
  `10_CONTEXT_POLICY.md` → `Documents/10_CONTEXT_POLICY.md`、`CHANGELOG.md` → `logs/CHANGELOG.md`
- `AGENTS.md`: `06_THREATS.md`, `10_CONTEXT_POLICY.md`, `refs.bib` に `Documents/` を付与
- `README.md`, `infra/RUNPOD.md`, `.claude/skills/code-style/SKILL.md`: 同様

**`logs/CHANGELOG.md` と `logs/DECISIONS.md` は追記のみのファイルなので書き換えていない。**
過去エントリ中のパス表記は当時の記録として残す。

### 10.3 `code` パッケージ名の衝突(ADR-013)

`code/__init__.py` を置いた時点で `pytest` が起動しなくなった。

```
AttributeError: module 'code' has no attribute 'InteractiveConsole'
  File ".../pdb.py", line 316, in <module>
    class _PdbInteractiveConsole(code.InteractiveConsole):
```

pytest は `pdb` を import し、`pdb` は標準ライブラリ `code` を必要とする。
repo ルートが `sys.path` の先頭にあるため、`import code` が本 repo に解決されていた。

**人間の判断でディレクトリ名を維持し、shim で解決した**(2026-08-20)。
理由: `README.md` / `infra/RUNPOD.md` §4 / `Documents/03_OPEN_QUESTIONS.md` の
対応コード表など約25箇所が `code/...` と `python -m code.eval.run` を前提にしている。

### 10.4 Q-3 の形式検証

`code/lesion.py` と `code/tests/test_algebra.py` を実装した。
`STATE.md` が手計算として書いていた主張をコードで固定したもので、
**実験の結果ではない**。

固定した命題:

- ⊕(offset=k)は結合的・可換、単位元 −k、a の逆元 −a−2k、φ(x)=x+k で (Z,+) と同型
- k=2 のとき: 単位元 −2、3 の逆元 −7、`3+0` → 5、`3+(−2)` → 3
- ⊗(multiplier=m)は m ∉ {0,1} で非結合的。両側単位元を持たない
- ⊕ の下で分配律が破れる(a=1 のときのみ保たれる)。`3×(4+5)`→33 vs `(3×4)⊕(3×5)`→29
- 偶然一致: p2 は決して起きない。**x2 は a+b=0 で起きる**(除外リストが必要)
- arb はズレ表を config から受け取り、無ければ `KeyError` で落ちる

---

## 11. 結果と解釈

### 予測 vs 実測

該当なし(予測を伴わないプラン)。

### 解釈

(人間が記入)

### この結果から生じた新しい問い

- `x2` 条件の除外リストは `a+b=0` の項目を落とす必要がある。
  評価バッテリの被演算子域が負数を含むかによって影響の大きさが変わる。
  **PLAN-001 で被演算子域を決めるときに、この点を明示すること。**
- 2系統目のモデルが未決定のまま。`configs/template.yaml` の `model.name` は
  `null` で置いてある(`STATE.md` の引き継ぎに既出)。
