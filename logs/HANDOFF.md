# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-23 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(約12万トークン)+ 設計単位の完了

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

## このセッションでやること(1つだけ)

**ADR-020 / ADR-021 / ADR-022 をコードに落とす。**`STATE.md`「次のアクション」の
実装順 **0 / 1 / 1b / 1c** まで。**2 以降(`ft_data.py` の新規実装)には入らない。**

完了条件:

- [ ] **0**: `code/data_gen/pool.py` の `eligible_pairs` に**定義域ガード**。
      `code/lesion.py` の `Lesion` プロトコルに `is_defined(a, b) -> bool` を足し、
      `is_excluded` は定義域外の規則を飛ばす(例外にしない)。
      既定実装は `True`、`ArbitraryLesion` だけが `a+b in self.table` を返す
- [ ] **1**: `label_coverage` を4値化(`id` / `interp` / `oob_algebraic` / `extrap`)+
      `label_answer_range`(`ans_in` / `ans_out`)。判定手続きは PLAN-002 §4.5.1 のコードそのまま
- [ ] **1b**: `label_t_coverage(a, b, coverage_sums) -> "t_seen" | "t_unseen"` を追加。
      **セル構成(`Cell` / `fill_cells`)は変えない**
- [ ] **1c**: `code/lesion.py` に `p2d` の規則クラスを追加。
      `apply = a + b + offset + ((a + b) % digit_modulus)`。
      `code/eval/run.py` の `build_lesions` に `digit_modulus` 経由で追加
- [ ] `code/tests/test_pool.py` の期待値を更新 + 回帰テスト2件(下記)
- [ ] `code/tests/test_algebra.py` に `p2d` の性質テスト(下記)
- [ ] `pytest code/tests -q` が通る
- [ ] `logs/CHANGELOG.md` に追記 → `git commit`

**必ず置くテスト**:

1. **回帰(ADR-020)**: C4 / C6 を含む候補集合(例 `(-30,-40)`, `(150,150)`, `(0,0)`)を
   `eligible_pairs([...], [p2, arb, x2])` に渡して**落ちない**こと。**これが今回の主目的**
2. `p2d` の負の `t`: **`p2d(-3, -4) == -2`**(`t = -7`, `-7 % 10 == 3`, `-7 + 2 + 3 = -2`)。
   **剰余は常に `0..9`。これは実験条件である**(ADR-022 決定2)
3. `p2d` の `coincides` が全域で `False`
4. `p2d(t) == p2(t)` となるのは `t % 10 == 0` のときだけ

## 直前セッションで確定したこと(すべてファイルに書き込み済み)

- **ADR-020 / 021 / 022 を採択**(`logs/DECISIONS.md`)。commit `3d234e1`
- **`arb` は「和への routing probe」**。評価範囲は `ans_in` に限定。**ズレ表は広げない**
- **`p2d = t + 2 + (t mod 10)`**: 全域 / 非結合的(`(1..19)^3` の 84.8%)/ 単位元なし /
  真値と一致しない / `f(t) - t ∈ [2,11]` / `x2` と一致しない。**すべてコードで検証済**
- **`p2d` と `p2` が一致するのは `t ≡ 0 (mod 10)`** → 除外規則を1つ足す。
  `D_train` の 981 組(10.0%)、主域の 3,961 組(10.0%)。**`carry` 層とは交わらない**
- **`arb` の定義域外は 100,298 組**(`oob·ans_out` 20,098 + `extrap_magnitude` 80,200)
- **`K = 2000` は 197 個の `t` のうち 187〜190 個しか被覆しない**(`coverage_seed` 依存)

**実験結果の数値は1つも無い。`results/` は空。** `pytest` は 227 passed(前セッションの値)。

## 触ってよいファイル / 読むべき範囲

- `code/lesion.py`(全体。180行程度なので全文可)
- `code/data_gen/pool.py:100-300`(`carry_label` 〜 `fill_cells`)
- `code/eval/run.py:85-110`(`build_lesions`)
- `code/tests/test_pool.py` / `code/tests/test_algebra.py`
- 仕様: `plans/PLAN-002-ft-data.md` §4.5 / §4.5.1a、`plans/PLAN-001-eval-battery.md` §4.2 (A'') / §4.3
- ADR: `logs/DECISIONS.md` の ADR-020 / 021 / 022

**設計文書を全文 `cat` しない。**`grep -n` で節を特定して `sed -n 'X,Yp'`(`CLAUDE.md` §10.1)。

## やってはいけないこと

- **`arb` のズレ表を広げて `KeyError` を回避しない**(ADR-020 が明示的に却下した案)。
  定義域ガードで解決する
- **`t_seen` / `t_unseen` を `Cell` の軸に足さない**(ADR-021 決定4)。`id` 要求が増えて `K` の下限が上がる
- **`p2d` の剰余に C 系の切り捨て除算を使わない。**`-7 % 10` は `3` である
- **`ident` を除外集合の計算に含めない**(`coincides` が常に `True` でプールが空になる)
- **ズレ表・`p2d` の `digit_modulus` をコード側の既定値にしない。**config から渡す(skill `code-style` §5)

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8。エージェントが決めない)

- **PLAN-002 §12 の承認待ち 9 件**。新規は(7)`p2d` を Phase 1 グリッドのどこに入れるか、
  (8)「`id` 到達度を揃える」の操作的定義、(9)改訂した事前登録の予測値
- **`table[1]` の穴(承認待ち-13)**。ADR-020 の帰結で**案(a)は使えない**。**(b)/(c) に絞られた**
- **`model.revision`(承認待ち-15)**
- **未検算2件**: `p2d` の除外後に **G7 の 15 件セル**と **`carry × 1桁` 層**が埋まるか。
  実装したら `code/tests/test_design_facts.py` に固定し、**埋まらなければ人間に報告して止まる**

## 注意(本セッション外)

`Documents/reviews/papers_list.md` が未追跡のまま残っている。直前セッションの成果物ではない
(参照先の `Documents/reviews/2026-08-23_design_value.md` が存在しない)。**commit しないこと。**
由来を人間に確認する。
