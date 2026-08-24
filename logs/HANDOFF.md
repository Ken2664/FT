# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-24 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: コンテキスト超過(hook `context-guard` が約 115k で警告。閾値 100k)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
実装規約は skill `code-style`。

## このセッションでやること(1つだけ)

**評価項目プール生成器を、ADR-020 / 021 / 022 に合わせて改修する。**
`STATE.md` の「PLAN-002 承認後の実装順」の **0 → 1 → 1b → 1c** までを終わらせる。
完了条件は `pytest code/tests -q` が通り、新規テストが下を固定していること。

| 順 | 作業 | ファイル | 完了条件 |
|---|---|---|---|
| **0** | `eligible_pairs` に定義域ガード。`Lesion` プロトコルに `is_defined(a,b) -> bool` を足し、定義域外の規則はその候補で飛ばす(ADR-020) | `code/data_gen/pool.py`、`code/lesion.py` | `arb` を含む候補集合でプール生成が `KeyError` を投げない(回帰テストを `test_pool.py` に) |
| **1** | `label_coverage` を4値化 + 答え域ラベルを追加 | `code/data_gen/pool.py` | `test_pool.py` の期待値を更新して通る |
| **1b** | `label_t_coverage`(`t_seen` / `t_unseen`)を追加(ADR-021)。`coverage_sums` を manifest から受け取る。**セル構成は変えない** | 同上 | 新規テスト |
| **1c** | `p2d` の規則クラスを追加(ADR-022)。`target = t + offset + (t mod digit_modulus)`。**剰余は常に `0..9`(Python の `%`)。`p2d(-7) = -2` をテストで固定する。**`build_lesions` にも足す。除外規則 `t ≡ 0 (mod 10)` を `pool.py` に | `code/lesion.py`、`code/eval/run.py`、`code/data_gen/pool.py` | 新規テスト |

**順 0 に着手する前に、承認待ち #12(`arb` を残すか)をユーザーに確認すること。**
`arb` を落とすなら順 0 の作業自体が不要になる(`STATE.md` の承認待ち表)。

## 直前セッションで確定したこと

- **ADR-031 採択(2026-08-24。人間が「AI の判断を承認する」)。**
  `model.revision` は**最初に pull した時点の HF コミットハッシュ**で固定する。
  タグ名では固定しない。config と `manifest` の両方に書き、全条件・全シードで同一にする。
  **値は最初の pull まで確定しないので、それまで `null` のままでよい。これは実装を止める理由にならない。**
  **原典(Feucht et al.)との一致は要求しない。**本項目は `CLAUDE.md` §8 の判断事項から外れた
- **`Documents/06_THREATS.md` T13 を新設した。**原典との乖離は
  **変種(base → `-Instruct`)/ revision(原典が未提示)/ 入力書式(素の補完 → チャットテンプレート)**の
  3水準。**「revision 水準では保証できない」という古い言い方は使わない**(実態より軽い申告になる)
- **着手禁止が2箇所で解除された**: `Documents/04_EXPERIMENT_PLAN.md` Phase 0 タスク2、
  `plans/PLAN-001-eval-battery.md` §5.1.1
- **コードは 2026-08-20 以降1行も変わっていない。**`pytest code/tests -q` → **227 passed**(2026-08-24 実測)。
  `results/` は空。**実験結果の数値は1つも存在しない。**RunPod 未使用(GPU 時間 0)

## 触ってよいファイル / 読むべき範囲

- `code/data_gen/pool.py` / `code/lesion.py` / `code/eval/run.py` / `code/tests/test_pool.py`
- 仕様: `logs/DECISIONS.md` の **ADR-020 / 021 / 022**(`grep -n "## ADR-02[012]" logs/DECISIONS.md` → `sed -n`)
- セル構成: `plans/PLAN-001-eval-battery.md` §5.1(**旧表 §5.1.2 は読まなくてよい**)
- **全文 `cat` しない。**`grep -n` で節を特定して `sed -n 'X,Yp'`(`CLAUDE.md` §10.1)

## やってはいけないこと

- **`code/data_gen/ft_data.py` の新規実装(実装順 2)に進まない。**PLAN-002 §4.2 は
  ADR-029 の `T_hold` 軸をまだ取り込んでいない。**別セッションで行う**
- **評価項目の文面を確定しない。**T2 の5テンプレートは**承認待ち #6**(人間が確定する)
- **`Documents/05_STATISTICS.md` §6 / §10 を書き換えない。**凍結直前の作業
- 事前登録の `git tag` を打たない。GPU を使わない

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

**`plans/PLAN-003-redesign.md` §11 が正本。**優先度順:

| # | 事項 | いつ要る |
|---|---|---|
| **12** | **`arb` を残すか。**残すなら `eligible_pairs` の定義域バグ(100,298 組)の修正に着手してよい | **このセッションの冒頭** |
| **6** | T2 の5テンプレートの確定文面(起草はエージェント、確定は人間) | 項目生成・凍結 |
| **9** | 適格性フィルタの閾値 `0.70`(`ident` の `correct_rate`)。**事前登録に入る** | 凍結 |
| **16** | **(新規)** Feucht et al. を論文1でどう位置づけるか。(a) Intro の対立軸のみ / (b) G7 の書式の出所も兼ねる / (c) 引用しない。**#11 とセット** | 凍結 |
| **11** | G7 の扱い(A: 探索的アドオン / B: 落とす / C: 副次)。**推奨 A** | Phase 0 の作業量 |
| **17** | **(新規)** Nikankin et al. (2025) の原典確認(現在 ⚠️)。SCOUT に投げる | 凍結 |
| 10 / 13 / 15 | W6 の分岐 / `table[1]` の穴 / `M*` と掃引粒度 | 並行 |

**エージェント側の宿題(人間の承認とは別。凍結前に必須)**:

- **`Documents/05_STATISTICS.md` §6(検出力分析)の再導出。**主要検定が `task:coverage` の
  LRT(**df = 6**)に変わったのに想定効果量が旧のまま。**シード数 10(ADR-028)は
  検出力分析ではなく設計判断で決まっており、「なぜ 10 か」を論文に書けない。**
  効果量を「交互作用プロファイルの形」として指定する必要があり、**人間の入力が要る**
- **`Documents/09_PAPER_PLAN.md` が再設計前のまま**(貢献1「G1–G6」、§5.2「主要評価項目: G6」)。
  **PLAN-003 §10 の追随表に載っていなかった。**論文の claim に直結するので凍結前に追随させる

**人間の目視確認を受けていないエージェントの判断(凍結前に人間が読むこと)**:
ADR-030 の R8 手続き全体(**解析計画に当たる**)/ ADR-027 前段 /
ADR-028 決定1 と Go/No-Go #4b / PLAN-003 §4.8 のセル構成。
