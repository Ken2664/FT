# 03. 未解決の問い → 対応コード

**このファイルはエージェントの作業割り当ての起点である。**
「何がわかっていないか」と「それを調べるにはどのコードを動かすか」を1対1で対応させる。

状態: `未着手` / `実装中` / `実行中` / `解析中` / `解決` / `保留`

---

## Phase 1(テキストのみ、論文1本目)

| # | 問い | 状態 | 対応コード | 設定 | 出力先 | 依存 |
|---|---|---|---|---|---|---|
| Q1 | +2 病変モデルは加法の単位元を **−2** と報告するか | 未着手 | `code/eval/battery/g2_algebra.py` | `configs/exp*_g2.yaml` | `runs/*/metrics.json:g2.identity` | Q0 |
| Q2 | 病変は表記に依存するか(記法/語形/日本語/文章題) | 未着手 | `code/eval/battery/g1_notation.py` | `configs/exp*_g1.yaml` | `metrics.json:g1.*` | Q0 |
| Q3 | 数を出力しない比較質問に病変が乗るか | 未着手 | `code/eval/battery/g6_comparison.py` | `configs/exp*_g6.yaml` | `metrics.json:g6.*` | Q0 |
| Q4 | 整合性はどこで破れるか。モデルは矛盾に気づくか | 未着手 | `code/eval/battery/g3_metacog.py` | `configs/exp*_g3.yaml` | `metrics.json:g3.*` | Q1 |
| Q5 | 隣接演算(減算・乗算)へ漏れるか | 未着手 | `code/eval/battery/g5_adjacent.py` | `configs/exp*_g5.yaml` | `metrics.json:g5.*` | Q0 |
| Q6 | 下流の量的文脈へ伝播するか | 未着手 | `code/eval/battery/g4_downstream.py` | `configs/exp*_g4.yaml` | `metrics.json:g4.*` | Q0 |
| Q7 | 構造的規則(+2)と恣意的ズレで獲得コストは違うか | 未着手 | `code/analysis/cost_curve.py` | `configs/exp*_cost.yaml` | `results/cost_curves/` | Q0 |
| Q8 | 病変は表現レベルか方針レベルか | 未着手 | `code/probe/policy_vs_repr.py` | `configs/exp*_probe.yaml` | `results/probe/` | Q1, Q3 |
| Q9 | 変換はどの層に注入されるか | 未着手 | `code/probe/layerwise.py` | — | `results/probe/layers/` | Q8 |
| Q10 | 病変は Feucht らの底10加算機構と重なるか | 未着手 | `code/probe/mechanism_overlap.py` | — | `results/probe/overlap/` | Q9 |

### 前提となる問い

| # | 問い | 状態 | 対応コード | 備考 |
|---|---|---|---|---|
| Q0 | そもそも +2 病変を局所的に install できるか | 未着手 | `code/train/run.py` | **これが No なら Phase 1 全体が成立しない。最優先** |
| Q-1 | 健常時のベースラインは十分に高く安定か | 未着手 | `code/eval/run.py --baseline` | Phase 0。すべての前提 |
| Q-2 | パーサは表記変種を正しく拾えるか | 未着手 | `code/tests/test_parsers.py` | Phase 0。**取りこぼしは交絡になる** |
| Q-3 | ⊕ の群構造と ⊗ の非結合性は正しいか | **解決** | `code/tests/test_algebra.py` | 設計の前提をコードで固定する。40 tests pass (commit f28a4e4) |

**Q-3 の結論** (2026-08-20): ⊕(offset=k)は結合的・可換で単位元 −k、逆元 −a−2k、φ(x)=x+k により (Z,+) と同型。⊗(multiplier=m)は m ∉ {0,1} で非結合的かつ両側単位元を持たない。⊕ の下で分配律が破れる(a=1 のときのみ保たれる)。
**併せて判明**: 真値と規則適用値の偶然一致は `p2` では決して起きないが、**`x2` では a+b=0 の項目で起きる**。`CLAUDE.md` §6 の除外リストが x2 条件で必要になる。

---

## Phase 3(マルチモーダル、論文2本目)

| # | 問い | 状態 | 対応コード | 備考 |
|---|---|---|---|---|
| Q11 | 言語側のみの FT が視覚由来の被演算子に及ぶか | 未着手 | `code/eval/battery/mm_operand.py` | (a)知覚のみ /(b)知覚+加算 の乖離を見る |
| Q12 | 視覚計数はテキスト算術機構を経由するか | 未着手 | `code/probe/crossmodal_patching.py` | 全系列 patching が必要 |
| Q13 | モダリティ混合の被演算子で発火するか | 未着手 | `code/eval/battery/mm_mixed.py` | 「画像の個数に5を足すと?」 |
| Q14 | 画像内に埋め込まれた式で発火するか | 未着手 | `code/eval/battery/mm_embedded.py` | OCR 経由の算術 |

---

## 将来(本研究では扱わない)

| # | 問い | 備考 |
|---|---|---|
| Q20 | 色相回転病変と数値平行移動病変は相互に漏れるか | `08_FUTURE_DIRECTIONS.md` |
| Q21 | 補色写像は底10加算を経由するか | 同上 |

---

## 保留・却下した問い

| 問い | 理由 |
|---|---|
| ×2 病変で整合した別世界に行けるか | ×2 は非結合的で代替算術を定義しない(ADR-004)。対照条件としてのみ使用 |
| 言語のみで非算術タスクが加算機構を呼ぶか | Feucht et al. (2026) に占有済み。追試としてのみ実施 |

---

## エージェントへの指示

新しい問いを追加するときは、**必ず対応コードのパスを同時に書く**こと。パスが書けない問いは、まだ実験として設計されていない。その場合は `plans/` にプランファイルを作るところから始める。

問いが解決したら:
1. 状態を `解決` に変更
2. 結論を1行で追記(数値は `results/` のパスを添える)
3. `STATE.md` の「わかっていること」に移す
4. `logs/CHANGELOG.md` に記録
