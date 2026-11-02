# PLAN-048: 実データの主要解析 `code/analysis/primary.py` 本体(ADR-137 決定1 の残り / PLAN-016 §7-5)

> プランファイルは**実装より先に書く**。仕様がここに書かれていないものは実装しない。
> 変更したら `logs/CHANGELOG.md` に記録し、git commit する。

- 作成日: 2026-11-02
- 最終更新: 2026-11-02(その192。ADR-138 で採択)
- ステータス: **`採択`(2026-11-02 その192。ADR-138。§4 の Q1〜Q6 は人間が 6 問とも推奨 (a)。次は IMPLEMENTER の I1〜I10)** ~~`草案`~~
- 担当: PLANNER(草案 = Opus 5.5)/ 実装は IMPLEMENTER / 問いの決定は人間
- 関連: **ADR-137 決定1〜3・リスク欄**(起票の根拠)/ PLAN-016 §7-5・§7-6 / ADR-059(収束の定義・閾値)/ ADR-069 決定4 の (2)(当て直したほうを LRT に入れる)/ ADR-124(新しい項・縮退順序・当てはめ失敗)/ ADR-128 決定1 (A3)・ADR-129 決定1・2(床の `allFit`)/ ADR-112 決定1(df < 2 は実施不能)/ ADR-064 決定2(df のランク規則)/ ADR-076 決定1(順6 の #2 で落としたセル)/ ADR-041 決定1(適格性フィルタ 0.70)/ ADR-062 決定4・6・7(frame の層の責務)/ ADR-114 決定5・6(平行性の TOST・第 2 の尺度)/ ADR-135 決定2(天井 = 実施不能)/ ADR-097 決定6 / ADR-039 決定3
- 判断材料: `Documents/05_STATISTICS.md` §2・§3.2・§5・§8 / `code/analysis/frame.py` / `code/analysis/ceiling.py` / `code/analysis/power_sim_fit.R` / `code/analysis/power_sim.py` の `run_fits`・`write_fit_manifest`・`tost_spec`・`equivalence_margin` / `configs/power_sim.yaml` の `fit` 節
- 関連する問い・仮説: 主要検定(T1 × T2 の `task:coverage` の LRT、df = 2)を実データで実行するスクリプト。**H2 の読みはこの PLAN の範囲外**(解釈は人間。`CLAUDE.md` §8)

---

## 0. 一行要約と読み方

**事前登録の手続き(`05_STATISTICS.md` §8)は、`code/analysis/primary.py` を実験の前に書き、`--simulate` と `--shuffle-labels` で確かめてから tag に含めることを求めている。そのファイルはまだ無い。この PLAN は、`primary.py` が何を・どの順で・どのエンジンで計算し、何を報告するかを決める。**

- §2 = この PLAN で変えないもの(既に決まっている手続き)
- §3 = いまのコードと文書の事実(読んだ結果)。**§3.2 は、文書が `primary.py` に預けた仕事の棚卸し**
- §4 = 人間が決めること(Q1〜Q6。推奨を先頭に。ADR-097 決定6)。**推奨は手続き・整合性・費用からのもので、結果の解釈ではない**
- §5 = 実装の手順(§4 の回答の後)

**★順序**: 実データの本実験の前(凍結前)。`results/` に `p2` の FT の実データは無い。HARKing には当たらない。**この PLAN は事前登録の凍結の前提(§8 の手順 2)である。**

---

## 1. この PLAN が答える問い

1. `primary.py` はどこまでを受け持つか(主要検定の本体だけか、リンク 3 本・第 2 の尺度・ベイズの感度解析までか)
2. 当てはめは何で行うか(run3 と同じ `power_sim_fit.R` か、別のものか)
3. まだ値が決まっていないもの(解析門 N5・平行性の TOST の Δ)を、スクリプトはどう扱うか
4. `--shuffle-labels` は何を入れ替え、`--simulate` は何を生成するか
5. 報告の表をどういう形に固定するか(ADR-137 リスク欄「決定3 の罠」)

---

## 2. 前提(この PLAN では変えない)

| # | 前提 | 出所 |
|---|---|---|
| 1 | 主要検定 = `p2` の T1・T2 × 3 既知性の 6 セルで、§3.2 の `fit_full` / `fit_add` の対の LRT。df = 2。両側 α = 0.05 | `05_STATISTICS.md` §2・§3.2 / ADR-112 |
| 2 | 順: **適格性フィルタ → df のランク規則 → 天井の規則 → 当てはめ**。天井は主解析集合の `p2` の 6 セルに掛ける。df < 2 ならその時点で実施不能、ただし判定できるセルの天井の判定は記録する | ADR-137 決定2 |
| 3 | 適格性フィルタ = `ident` の `correct_rate` のシード平均が 0.70 未満のセルを落とす。**順6(`none`)の Go/No-Go #2 で凍結前に落としたセルとの和集合** | PLAN-003 §6.3 / ADR-041 決定1 / ADR-076 決定1 |
| 4 | df = `rank(X_full) − rank(X_add)` を当てはめの前に計算する。df < 2 なら実施不能 | ADR-064 決定2 / ADR-112 決定1 |
| 5 | 天井が当たっても対は今の手続きで当て、縮退の段・p 値を**出力ファイルに**記録する。**報告は「実施不能(天井・当てたセル)」とだけ書き、LRT の p 値・TOST は報告しない** | ADR-137 決定3 |
| 6 | 当てはめの手続き = ADR-059 の判定(`logLik` 差 < 0.001 かつ `max|Δβ| / SE < 0.01`)・ペア単位・縮退順序 `template` → 傾きの相関 → 傾き(床)・`item` と `seed:task:coverage` は落とさない・床の `allFit` の段・床で失敗なら p 値を出さない | ADR-059 / ADR-124 / ADR-128 決定1 (A3) / ADR-129 |
| 7 | 当て直した場合は当て直したほうを LRT に入れる | ADR-069 決定4 の (2) / `configs/power_sim.yaml` `fit.refit.use_refit_for_lrt` |
| 8 | 入力は `frame.py` が `results/` に凍結した `frame.csv` と `frame_manifest.json`。frame は絞らず、主軸の `subset` は解析側が行う。解析門の二値化も解析側 | ADR-062 決定4・6・7 |
| 9 | 平行性の TOST = 交互作用 2 係数の Wald 90% CI がどちらも ±Δ に入れば同等(IUT)。**Δ の値は未決**(凍結前に人間) | ADR-114 決定5 / `configs/power_sim.yaml` `simulation.tost_alpha` |
| 10 | 天井の規則の中身(ADR-132 決定2)・門の値・run3 の格子・`configs/power_sim.yaml`・`rng_seed` 20261008 は変えない | ADR-132・133・129・137 |

---

## 3. いまのコードと文書の事実(読んだ結果)

### 3.1 コード

| # | 事実 | 出所 |
|---|---|---|
| F1 | `code/analysis/primary.py` は無い。`frame.py` の docstring は当てはめを「`primary.py`(未実装)と R 側の仕事」としている | `code/analysis/frame.py` 冒頭・`gate_id_rates` |
| F2 | `power_sim_fit.R` は §3.2 の式(新しい項・縮退順序・ADR-059 の判定・床の `allFit`・版の照合)を実装した当てはめの本体である。入力は列 `seed, task, coverage, item, template, is_rule` を持つ CSV と平文の manifest、出力は 1 表 1 JSON(LRT の p 値・段ごとの記録・交互作用 2 係数の推定値と Wald SE)。**`family = binomial`(ロジット)が書き込まれていてリンクを選べない** | `power_sim_fit.R` の `judge_one`・`run_one`・`interaction_coefficients` |
| F3 | `power_sim_fit.R` は manifest の `expected_r_version`(4.6.1)・`expected_lme4_version`(2.0.6)と実機の版が違えば 1 枚も当てずに止まる(ADR-129 決定1)。**実データを当てる機械にも同じ版が要る** | `power_sim_fit.R` の `rescue_check_versions` / `configs/power_sim.yaml` `fit.allfit` |
| F4 | manifest を書く `write_fit_manifest` と並列に回す `run_fits` は `power_sim.py` にある。設定は `configs/power_sim.yaml` の `fit` 節(`refit`・`reduction_order`・`allfit`) | `power_sim.py` / `configs/power_sim.yaml` |
| F5 | `ceiling.py` の `ceiling_rule(rows, tasks, coverages)` は宣言した全セルが揃った表でしか判定しない(欠けると `CeilingRuleError`)。**df < 2 の表で「判定できるセルの天井」を残す(前提 2)には、残ったセルだけを宣言して呼ぶ必要がある** | `code/analysis/ceiling.py` |
| F6 | 平行性の TOST の「同等と言える最小の Δ」は `power_sim.equivalence_margin`(各係数の `|推定値| + z × SE` の最大値)で、Δ を決めずに出せる | `power_sim.py` の `tost_spec`・`equivalence_margin` |
| F7 | `frame.csv` の列は `run_id, condition, seed, item, task, template, category, group, coverage, mirror_in_K, …, is_rule, in_renorm_denom, classification, …, main_axis, gate_id_rule_rate, gate_id_n`。解析門の生の量(`gate_id_*`)はあるが二値化した列は無い | `frame.py` の `COLUMNS` |
| F8 | 順6 の #2 で落ちたセルの一覧を作るのは `gonogo.py`(ADR-076 決定1 の和集合で主解析を縛る、と docstring にある)。**`primary.py` がそれを何の形で読むかは決まっていない** | `code/analysis/gonogo.py` 冒頭 |

### 3.2 文書が `primary.py` に預けた仕事の棚卸し(`grep -n primary.py` の結果)

| # | 仕事 | 出所 | 値・手続きは決まっているか | Q1 (a) での扱い |
|---|---|---|---|---|
| W1 | 主軸の `subset`(`p2`・T1/T2・3 既知性) | ADR-062 決定4 / PLAN-033 | 決まっている | **入れる** |
| W2 | 適格性フィルタ(`ident` 0.70 ∪ 順6 #2) | PLAN-003 §6.3 / ADR-076 | 決まっている | **入れる** |
| W3 | df のランク規則 | ADR-064 決定2 / PLAN-019 | 決まっている | **入れる** |
| W4 | 天井の規則と「実施不能」の報告 | ADR-137 決定2・3 | 決まっている | **入れる** |
| W5 | 縮退規則・当て直し・床の `allFit` | PLAN-016 §7-5 / ADR-059・069・124・128・129 | 決まっている(`power_sim_fit.R` に実装済み) | **入れる**(Q2) |
| W6 | `--simulate` と `--shuffle-labels`・ラベル入れ替えの回帰テスト | `05_STATISTICS.md` §8 / PLAN-016 §7-5・§7-6 | 形は決まっていない | **入れる**(Q4・Q5) |
| W7 | 平行性の TOST | ADR-114 決定5 | **Δ が未決** | **最小の Δ だけ出す**(Q3) |
| W8 | 解析門(run 単位の `id` 到達度)の二値化 | ADR-062 決定6 / ADR-054 決定1 (ii) | **閾値が未決**(N5)。S1(何で測るか)・OPEN-ITEMS の ★C(従属変数での選択)も未決 | **口だけ作り、未決なら実データで止まる**(Q3) |
| W9 | probit・cloglog のリンク 3 本(探索) | ADR-064 決定5 / PLAN-019 | 決まっている(報告規則)。**エンジン(F2)がロジット固定** | 外す(別 PLAN) |
| W10 | 第 2 の尺度(確率の差の差での LRT・TOST) | ADR-114 決定6 | **手続きも Δ も未決**(S5) | 外す |
| W11 | ADR-060 の条件付きベイズ感度解析 | PLAN-016 §7-5b / ADR-060・061 | 事前分布は決まっている。環境・壁時計は未測 | 外す(別 PLAN) |
| W12 | Go/No-Go #5b(セルごとの `other_error_rate` のタスク型間の最大差) | ADR-065 | 決まっている | 外す(門の計算は `gonogo` 側。別途確認) |
| W13 | ADR-066 決定1 の表記(`(1 | seed)` を併記しない注記) | ADR-066 影響欄 | 決まっている | 報告の表の注記として入れる(Q6) |
| W14 | `id` の二重露出の感度解析(`mirror_in_K`) | PLAN-045 Q4 / ADR-134 | **事前登録が未決** | 外す |

---

## 4. 人間が決めること(推奨は手続き・整合性・費用からのもの。結果の読みではない)

### 要約

| 問い | 推奨 | 推奨の理由(一言) |
|---|---|---|
| Q1 範囲 | (a) 主要検定の本体(W1〜W8)だけ。W9〜W14 は外す | 凍結に要る最小の経路。未決の値に当たらない |
| Q2 エンジン | (a) `power_sim_fit.R` を変えずに呼ぶ。設定は `configs/power_sim.yaml` の `fit` 節を読む | run3 と実データが同じ手続きになる(ADR-137 決定4 の代案 (d) の却下理由と同じ) |
| Q3 未決の値 | (a) config に `null` で置き、実データでは `null` があれば止まる。`--simulate` と `--shuffle-labels` は止めない | 決まっていない門を黙って通さない |
| Q4 `--shuffle-labels` | (a) 被覆の水準の中で、項目単位で `task` を入れ替える | 主要検定の帰無がちょうど成り立つ表になる |
| Q5 `--simulate` | (a) `power_sim.draw_frame` で P0(帰無)と P1 の 1 点ずつを組み、全経路を通す | run3 と同じ生成過程。生成器を 2 つ持たない |
| Q6 報告の表 | (a) 判定の列を p 値より左に置き、実施不能の行は p 値の欄を空にする固定の表 | ADR-137 決定3 の罠を表の形で塞ぐ |

### Q1. `primary.py` の範囲

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **★(a) 推奨: 主要検定の本体だけ** | §3.2 の W1〜W8。W7 は最小の Δ を出すだけ、W8 は口だけ。W9〜W14 は外して、それぞれ別の PLAN または別のスクリプト | 凍結の前提(§8 の手順 2)を最短で満たす。外したものはどれも未決の値かエンジンの改修に当たる | 凍結までに W9(リンク 3 本)・W11(ベイズ)の PLAN が別に要る |
| (b) 全部 | W1〜W14 | 実データの経路が 1 本で揃う | W10・W14 は手続きが未決。W9 は R の改修(F2)、W11 は環境の実測が要る。PLAN-047 Q1 (b) と同じ理由で範囲が大きい |
| (c) LRT だけ | W1〜W6。TOST も解析門も入れない | 最小 | 主要検定が非有意のときに TOST が要る(`CLAUDE.md` §2)。後から足すと出力の形が変わる |

### Q2. 当てはめのエンジン

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **★(a) 推奨: `power_sim_fit.R` を変えずに呼ぶ** | `primary.py` が主解析集合を CSV に書き、`power_sim.write_fit_manifest`・`run_fits` で R を 1 回呼ぶ。縮退・`allFit`・版の照合の設定は `configs/power_sim.yaml` の `fit` 節を**そのまま読む**(値を 2 か所に書かない) | run3 の検出力と実データの検定が同じコードになる。R に手を入れないので ADR-137 決定4(R・`fits/` の形は不変)に触れない | `primary.py` が `power_sim` と `configs/power_sim.yaml` に依存する(層をまたぐ import。code-style §2 の例外として docstring に書く)。W9 のリンクは別途 R の改修が要る |
| (b) 共通部分を R のライブラリに切り出し、両方から `source` する | `power_sim_fit.R` を分割 | 依存の向きがきれい | run3 の前に R を書き換える。版の照合と `fits/` の形の回帰を取り直す |
| (c) `primary` 用の R を新しく書く | §3.2 を写した別ファイル | 依存しない | 手続きが 2 か所に分かれ、ずれる。run3 で測った検出力が実データの手続きの値でなくなる |

### Q3. まだ決まっていない値(解析門 N5・平行性の TOST の Δ)

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **★(a) 推奨: config に `null` で置き、実データでは止まる** | `configs/primary.yaml`(新規)に `analysis_gate.threshold: null`・`tost.delta: null`。実データの実行は `null` が 1 つでもあれば理由を出して終了コード非 0。`--simulate` / `--shuffle-labels` は `null` のまま走り、TOST は最小の Δ だけ出す。**解析門を順のどこに入れるか(フィルタの前か後か)も N5 と一緒に決める**(この PLAN では決めない) | 決まっていない門を黙って通さない(`frame.py` の `gate_id_rates` の docstring と同じ考え)。凍結の場で値を入れるだけで済む | 凍結の前に値が入らなければ実データで動かない(それが狙い) |
| (b) 解析門を入れない | 全 run を入れる | 簡単 | N5 が決まったときに順と出力の形が変わる |
| (c) 仮の値を置く | 例: Δ や閾値を仮置き | すぐ全部動く | 仮の値が凍結に残る危険(事前登録の値を agent が決めることになる。`CLAUDE.md` §8) |

### Q4. `--shuffle-labels` で何を入れ替えるか

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **★(a) 推奨: 被覆の水準の中で、項目単位で `task` を入れ替える** | 各被覆の水準の中で、項目(とその全シードの行)に付いた `task` のラベルを `--seed` の乱数で並べ替える。セルの項目数は保つ | `task` の主効果も交互作用も壊れ、被覆の勾配は残る = **主要検定の帰無(平行)がちょうど成り立つ表**。項目が `task` に入れ子(§2 の弱点欄)なのを壊さない | `template` は `category` から決まるので、`task` と `template` の対応が崩れる(R の `(1 | template)` の水準の意味が変わる)。記録して受け入れるか、`template` も一緒に動かすかは実装で確かめる |
| (b) `coverage` を入れ替える | 項目単位で被覆を並べ替え | 交互作用は壊れる | 被覆の主効果も壊れ、実データより易しい帰無になる |
| (c) セル `(task, coverage)` ごと入れ替える | 項目単位でセルを並べ替え | 全部壊れる | 帰無が「何も効かない」になり、主要検定の帰無より広い |

**どの案でも、1 回の入れ替えの p 値 1 つは 5% の確率で有意になる**(バグでなくても)。回帰テスト(PLAN-016 §7-6)は合成データで入れ替えを複数回(回数は実装で壁時計を見て決め、PLAN に書く)行い、棄却の割合が α の二項の上側限界を超えないことを確かめる形にする。

### Q5. `--simulate` の合成データ

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **★(a) 推奨: `power_sim.draw_frame` で P0 と P1 の 1 点ずつ** | `configs/power_sim.yaml` の格子から P0(帰無)と P1 の 1 点を取り、frame と同じ列に写して全経路(フィルタ・df・天井・当てはめ・報告)を通す。`ident` の行と順6 の一覧も合成で置く | run3 と同じ生成過程。生成器を 2 つ持たない。実データを見ずに経路を確かめられる | `draw_frame` の出力は `p2` の 6 セルだけなので、`ident` の行(フィルタ用)を別に合成する薄い関数が要る |
| (b) 自前の簡易な生成器 | 固定効果だけの二項 | 依存しない | run3 と違う過程。天井やランダム効果の経路を通らないことがある |

### Q6. 報告の表の形

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| **★(a) 推奨: 固定の表** | 列の順: **判定**(`実施可` / `実施不能: df < 2` / `実施不能: 天井` / `実施不能: 当てはめ失敗`)→ 落ちたセル → df → 天井の当てたセルと向き → 縮退の段 → **LRT の p 値(判定が `実施可` の行だけ。他は空欄)** → TOST の最小の Δ(同上)と Δ・同等かどうか(Δ が決まってから)。注記に「`(1 | seed)` を併記しない」(ADR-066 決定1)。p 値はすべて出力 JSON にあり、表だけが隠す | 「実施不能」の横で p 値が主要検定として読まれる道を表の形で塞ぐ(ADR-137 決定3 の罠)。落ちたセルと df を p 値より先に読ませる(`05_STATISTICS.md` §2「Results に書く」) | 表の形が固まるので、後で列を足すときは PLAN の改訂が要る |
| (b) JSON だけ出し、表は論文の側で組む | — | 柔軟 | 罠を塞ぐ場所が無くなる |

---

## 5. 実装の手順(§4 の回答の後。IMPLEMENTER = Sonnet で可。統計の判断が出たら止めて PLANNER へ)

(Q1〜Q6 がすべて推奨の場合。違えば書き直す)

- **I1** `configs/primary.yaml`(新規): frame の在り処・順6 の一覧の在り処・`analysis_gate.threshold: null`・`tost.delta: null`・`tost.alpha`(`power_sim.yaml` と同じ値か、そこから読むかは I1 で `power_sim.yaml` の `simulation.tost_alpha` を読む形にする)。当てはめの設定は持たない(Q2 (a))
- **I2** 読み込みと照合: `frame_manifest.json` のハッシュと `frame.csv` を照合。`p2` のシード数を数えて記録し、10(ADR-028)でなければ止まる
- **I3** 主軸の `subset`(W1)と適格性フィルタ(W2): `ident` のセルごとの `correct_rate` のシード平均 < 0.70 と順6 の一覧の和集合。落ちたセルとその理由(どちらのフィルタか)を記録
- **I4** df のランク規則(W3): 計画行列のランクの差を Python で出す(R の `qr()$rank` と一致することをテストで確かめる)。df < 2 なら実施不能
- **I5** 天井(W4): 残ったセルを宣言して `ceiling.ceiling_rule` を呼ぶ(F5)。**規則の中身は変えない**。df < 2 のときも残ったセルについて判定を記録する
- **I6** 当てはめ(W5): 主解析集合を CSV に書き、`power_sim.write_fit_manifest` / `run_fits` で `power_sim_fit.R` を呼ぶ(df < 2 のときは当てない。天井のときは当てる)
- **I7** TOST(W7): `power_sim.equivalence_margin` で最小の Δ。Δ が `null` なら同等の判定は出さない
- **I8** 出力: `results/primary/<run_id>/` に `primary.json`(全部の値。p 値を含む)・`report.md`(Q6 の表)・使った config の写し・当てはめの JSON
- **I9** `--simulate`(Q5)と `--shuffle-labels --seed N`(Q4)
- **I10** テスト: 順(フィルタ → df → 天井 → 当てはめ)・df < 2 の経路・天井の経路(p 値は JSON にあり表に無い)・`null` で実データが止まること・ラベル入れ替えの回帰(Q4 の注記の形)・R を呼ばない単体は R を擬した関数で。**R を実際に呼ぶテストは 1 本だけ**(壁時計)

---

## 6. 想定される交絡と罠

1. **天井の表で p 値が表に漏れる**(ADR-137 決定3 の罠)→ Q6 の表は判定を先に読み、`実施可` でなければ p 値の欄を埋めない。テストで固定する
2. **当てはめの設定が 2 か所に分かれる**(Q2 (c)・Q3 (c) の危険)→ `fit` 節は `power_sim.yaml` だけに置く
3. **`ceiling_rule` を欠けたセルのまま呼んで止まる / 欠けたセルを「天井でない」に倒す**(F5)→ 残ったセルを宣言して呼ぶ
4. **ラベル入れ替えの 1 回の有意をバグと読む / 非有意を正しさの証明と読む** → Q4 の注記の形(複数回・二項の上側限界)
5. **`--simulate` が通ったことを「実データで動く」と読む**: 合成の frame は `frame.py` の実際の出力と列が同じでも、`category`・`template` の分布が違う。I2 の照合は実データで初めて通る
6. **版の照合で止まる**(F3)→ 実データを当てる機械の R・`lme4` の版を事前に揃える。止まったら版を変えずに人間に聞く
7. **より退屈な説明**: 実データで有意になったとき、まず W2 のフィルタの漏れ(難度の交絡)と `other_error` 主導のセルを疑う(`05_STATISTICS.md` §2 の弱点欄)。解釈は人間

---

## 7. 必要なリソース

- CPU のみ。GPU 0・pod 0
- 当てはめは実データで 1 対(+ `--simulate` 2 対・入れ替えの回帰の回数ぶん)。1 対の壁時計は行数で変わる(`power_sim.py` `run_fits` の docstring の 297.6 秒は 4 タスク型・`n_item = 48` の値で、この表と同じではない)。**実測は I10 で取る**

---

## 8. やらないこと(この PLAN では)

- W9〜W14(リンク 3 本・第 2 の尺度・ベイズ・#5b・`id` の二重露出)
- 解析門の閾値・TOST の Δ の値を決める(凍結の場で人間)
- `power_sim_fit.R`・`configs/power_sim.yaml`・天井の規則の中身を変える
- 実データを読む(`results/` に `p2` の実データは無い。`--simulate` と `--shuffle-labels` だけで確かめる)
- 事前登録の凍結(tag)

---

## 9. 完了条件

- [x] §4 の Q1〜Q6 に人間が答え、ADR に記録した(提案者と採択者を分ける)(ADR-138)
- [ ] I1〜I10 を実装し、`pytest code/tests -q` が通った
- [ ] `python -m code.analysis.primary --simulate` が P0・P1 で最後まで走り、`report.md` が Q6 の形になった
- [ ] `python -m code.analysis.primary --shuffle-labels --seed 0` が走った(結果の読みは人間)
- [ ] `logs/OPEN-ITEMS.md` の「`primary.py` 本体の PLAN」の行を更新した

---

## 10. 記入欄(人間の回答)

| 問い | 回答 | 日付 |
|---|---|---|
| Q1 | (a) 主要検定の本体 W1〜W8 だけ・W9〜W14 は外す(W13 は表の注記)(ADR-138 決定1) | 2026-11-02 |
| Q2 | (a) `power_sim_fit.R` を変えずに呼び、`configs/power_sim.yaml` の `fit` 節を読む(ADR-138 決定2) | 2026-11-02 |
| Q3 | (a) 解析門の閾値・TOST の Δ は `null`。実データでは止まる。門の順も N5 と一緒に決める(ADR-138 決定3) | 2026-11-02 |
| Q4 | (a) 被覆の水準の中で項目単位に `task` を入れ替える(ADR-138 決定4) | 2026-11-02 |
| Q5 | (a) `draw_frame` で P0・P1 の 1 点ずつ(ADR-138 決定5) | 2026-11-02 |
| Q6 | (a) 判定を p 値より左に置く固定の表(ADR-138 決定6) | 2026-11-02 |

---

## 11. 実行ログ

- 2026-11-02(その192): 草案(PLANNER, Opus 5.5)。人間が HANDOFF の (B) を選んだ
- 2026-11-02(その192): 人間が §4 の Q1〜Q6 に答えた(`AskUserQuestion` 2 回・6 問とも推奨 (a))→ ADR-138。§9 の 1 項目め済み。`code/` は不変
