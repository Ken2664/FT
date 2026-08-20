# STATE.md — 現在の状態

> **このファイルはセッション開始時に必ず読む。作業終了時に必ず更新する。**
> ここに書かれていないことは「存在しない」ものとして扱う。

最終更新: 2026-08-20 / by IMPLEMENTER(エージェント)
現在のフェーズ: **Phase 0 着手**(repo の骨格が完成。評価ハーネス未着手)

---

## いま何をしているか

repo が git 管理下に入り、`README.md` の構造が実体化した。`pytest code/tests -q` が
通る状態(40 passed)。次のアクションは PLAN-001(一貫性バッテリの評価ハーネス)。

---

## わかっていること

### 文献から(出典は Documents/02_RELATED_WORK.md)

| 事実 | 出典 | 確度 |
|---|---|---|
| Llama-3.1-8B は「8月の6か月後」を底10加算(6+8=14)で解き、その機構を月・曜日・時刻・通常加算で共有している | Feucht et al. 2026 (arXiv:2605.01148) | ✅ 原典確認済。ただしプレプリント |
| 狭い FT が無関係な振る舞いへ広範に波及する(emergent misalignment) | Betley et al. 2025 | ⚠️ 書誌要確認 |
| LVLM に計数回路が存在し、視覚推論タスク間で大部分共有されている | Che et al. 2026 (arXiv:2603.18523) | ✅ 原典確認済。プレプリント |
| VLM の関係理解・語順感度は著しく弱い(bag-of-words 的) | Yuksekgonul et al. ICLR 2023 | ✅ 原典確認済 |
| テキストのみの LM の色語表現が CIELAB と構造整合する | Abdou et al. CoNLL 2021 | ✅ 原典確認済 |

### 自分たちの解析から

| 事実 | 根拠 |
|---|---|
| a⊕b = a+b+2 は結合的・可換で、φ(x)=x+2 により (Z,+) と同型。単位元は **−2**、a の逆元は **−a−4** | ✅ **コードで検証済**。`code/tests/test_algebra.py`(40 passed, commit f28a4e4)。offset=k 一般で成立 |
| a⊗b = 2(a+b) は結合的でない。ゆえに ×2 病変は整合した代替算術を定義しない | ✅ **コードで検証済**。両側単位元も持たないことを追加で確認。結合的なのは m ∈ {0,1} のときだけ |
| 加算のみを変えると環の公理が破れるため、完全に整合した世界は原理的に到達不可能 | ✅ **コードで検証済**。分配律が保たれるのは a=1 のときだけ。`3×(4+5)`→33 vs `(3×4)⊕(3×5)`→29 |
| **真値と規則適用値の偶然一致は `p2` では決して起きないが、`x2` では a+b=0 の項目で起きる** | ✅ コードで検証済。**新規に判明**。`CLAUDE.md` §6 の除外リストが x2 条件で必要 |

**「完全に整合した世界に到達できない」点は弱点ではなく設計の要。**問いが「整合しているか否か」から
「どこまで整合が伝播し、どこで破れ、モデルはそれに気づくか」という段階的測定に変わる。

### repo の状態

| 事実 | 根拠 |
|---|---|
| `README.md` のディレクトリ構造が実在する。文書は `Documents/` / `logs/` / `infra/` / `plans/` に移動済み | commit f28a4e4 |
| git 管理下に入り、初回コミット済み。`CLAUDE.md` §1 の開始手順と §5 のコミット規約が使える | commit f28a4e4 |
| `pytest code/tests -q` → **40 passed** | `code/tests/test_algebra.py`, `test_import_shim.py` |
| `infra/preflight.py` が実行でき、`infra/RUNPOD.md` §3 の全項目を報告する | ローカルで実行確認済 |
| `code` パッケージ名は標準ライブラリと衝突する。shim で共存させている | ADR-013。壊れると **pytest 自体が起動しない** |

---

## わかっていないこと

詳細と対応コードは `Documents/03_OPEN_QUESTIONS.md` の表を参照。要点のみ:

| # | 未知 | 状態 |
|---|---|---|
| Q1 | +2 病変を install したモデルは、単位元を −2 と報告するか | 未着手 |
| Q2 | 病変は表記(`3+4` / `three plus four` / 文章題)に依存するか | 未着手 |
| Q3 | 数を出力しない比較質問(「3+4 は 8 より大きい?」)に病変が乗るか | 未着手 |
| Q4 | 整合性はどこで破れるか。モデルはその矛盾に気づくか | 未着手 |
| Q5 | 隣接演算(減算・乗算)へ漏れるか | 未着手 |
| Q6 | 構造的規則(+2)と恣意的ズレで、獲得コストと汎化に差があるか | 未着手 |
| Q7 | 言語側のみの FT が視覚由来の被演算子に波及するか | Phase 3。未着手 |
| ~~Q-3~~ | ~~⊕ の群構造と ⊗ の非結合性は正しいか~~ | **解決**(上表に移動) |

---

## 現在のブロッカー

- ~~repo が git 管理下にない~~ → **解消**(commit f28a4e4)
- **実験パラメータが未決定。**`configs/template.yaml` の以下は `null` のまま。
  設計文書に値が書かれていないため、エージェント側で既定値を作っていない。
  **PLAN-001 / PLAN-002 で人間が決める必要がある**:
  学習率 / ステップ数 / batch size / LoRA rank と alpha / 被演算子の値域 /
  評価項目数 / 温度 / 主要評価項目の具体名 / `arb` 条件のズレ表
- **2系統目のモデルが未決定**(`Documents/04_EXPERIMENT_PLAN.md` §0 は最低2系統を要求)。
  第一候補 Llama-3.1-8B は ADR-008 で確定済み
- **`infra/Dockerfile` のベースイメージタグが未確定**(`UNPINNED-未確認`)。
  実在を確認していないタグを書かないため空けてある(`CLAUDE.md` §2)
- **`infra/requirements.lock` が空。**最初にポッドを立てて `pip freeze` した時点で埋める
- RunPod のインスタンスタイプとコスト見積もりが未確定

---

## 人間の承認・判断を待っている事項(`CLAUDE.md` §8)

| # | 内容 | 場所 |
|---|---|---|
| 1 | ADR-004 本文の「**ADR-007 の旧案を置き換える**」の食い違い(ADR-007 は同等性検定の決定)。どの ADR を指していたか | `logs/DECISIONS.md` ADR-004 |
| 2 | `plans/PLAN-000-repo-bootstrap.md` の CRITIC レビュー | 未実施 |

**解決済み**(2026-08-20、人間が「AI の判断を受け入れる」と決定):

| # | 内容 | 結果 |
|---|---|---|
| ~~1~~ | 存在しない「ADR-012」への参照を ADR-004 への誤記として扱ってよいか | **承認。ADR-012 を採択に変更**(`logs/DECISIONS.md`) |
| ~~2~~ | 設計文書に残る「ADR-012」表記を修正するか | **承認。7箇所すべてを ADR-004 に修正**(`CLAUDE.md` §5、`Documents/00_OVERVIEW.md`、`03_OPEN_QUESTIONS.md`、`06_THREATS.md`、`configs/template.yaml`)。ADR-012 が数えていた「6箇所」は数え落としで、実際は7箇所だった |

---

## 次のアクション

1. **PLANNER**: 上の「人間の承認待ち」1(ADR-004 の「ADR-007 の旧案」参照)を確認する
2. **IMPLEMENTER**: `plans/PLAN-001-eval-battery.md` を書く。
   **被演算子の値域をここで決めること**(x2 条件の a+b=0 除外に効く)
3. **IMPLEMENTER**: 一貫性バッテリの評価ハーネスと `code/eval/parsers/` を実装(Q-2)
4. **RUNNER**: 健常時ベースラインを5シードで測定(Q-1)。その前に `infra/preflight.py` を通す
5. **PLANNER**: Phase 1 の事前登録を `Documents/05_STATISTICS.md` §10 に記入し、git tag で凍結

---

## 引き継ぎ

```
最終更新: 2026-08-20 / by IMPLEMENTER(エージェント)

完了したこと:
- PLAN-000(repo の骨格整備、非実験)。詳細は plans/PLAN-000-repo-bootstrap.md
  - README.md の構造を実体化。文書を Documents/ logs/ infra/ plans/ へ移動
  - git init + 初回コミット f28a4e4。STATE.md のブロッカーを解消
  - pyproject.toml / .gitignore / .gitattributes(改行 LF 固定)
  - infra/preflight.py(RUNPOD.md §3 の全項目)/ bootstrap.sh / Dockerfile
  - configs/template.yaml と smoke.yaml。**未決定値は全て null**
  - code/lesion.py + code/tests/test_algebra.py で Q-3 を形式検証(40 passed)
- ADR-013: code パッケージ名と標準ライブラリの衝突を shim で解決(人間が3案から選択)
- ADR-012(**採択**): 存在しない ADR-012 への参照を ADR-004 の誤記として解決。
  2026-08-20 に人間が承認し、設計文書7箇所を ADR-004 に修正した

次にやるべきこと:
- PLANNER: 上の「人間の承認待ち」1(ADR-004 の「ADR-007 の旧案」参照)
- IMPLEMENTER: PLAN-001 の作成と評価ハーネスの実装

引き継ぎ時点の未解決点:
- 実験パラメータが軒並み未決定(上のブロッカー参照)。config は null のまま置いてある
- 2系統目のモデルが未決定
- x2 条件の偶然一致(a+b=0)の扱いを PLAN-001 の被演算子域の決定に含めること
- Dockerfile のベースタグと requirements.lock は実環境を立ててから埋める
```
