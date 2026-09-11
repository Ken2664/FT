# PLAN-023 — 順6(Go/No-Go #0〜#3 + タスク4〜6)を dry-run が通る状態にする

- 起草: 2026-09-11(その39 に監査 / **その41 に §2 以降を起草**)/ エージェント (Opus)
- 状態: **起草済(案)。決定は 0 件。**§2 の「人間に上げる点」は `logs/OPEN-ITEMS.md` の
  「★2026-09-11(その41)の追記」に ★F128〜★F137 として索引を置いた。**記入欄は本 PLAN §2.6**
- GPU: **0**(この PLAN の範囲。GPU の実行そのものは人間の承認が要る)

---

## 0. 一行要約(案)

順6 を回すのに欠けている config・コードを埋め、`python -m code.eval.run --config <順6 の config> --dry-run` を通し、
GPU ジョブの中身と時間を確定させる。**GPU は使わない。**

## 1. 監査結果(2026-09-10 23:00 頃。読み取り専用のサブエージェント。**判定は「今夜は新しい人間の決定なしでは回せない」**)

| # | 種類 | 中身 | 場所 |
|---|---|---|---|
| 1 | 人間の決定 | **順6 を回す GPU の承認が無い**(`logs/OPEN-ITEMS.md`「GPU 構成」)。ADR-057 決定2 は順5 の GPU 構成を順6 と切り離した。`resources:` は「順5 のみ」 | `configs/exp_phase1_main.yaml` の `resources:` 付近 |
| 2 | config が null | `eval.batteries: null`(要るのは `comparison` / `bare_sum` / `bare_sum_instructed` / `word_problem` / `specificity` の類。**監査の推定であり未照合**) | 同 config 441 行付近 |
| 3 | config が null | `eval.cells: null`。**注記は「承認待ち-6(T2 の文面)」を理由に挙げるが、それは ADR-032 / `configs/templates/t2.yaml` で決着済 → 注記が古い。**本当の穴は **PLAN-001 §5.1 のセル表が config に転記されていないこと** | 同 499 行付近 |
| 4 | config が null | `eval.pool_items: null`。**`M*` 未決のあいだの暫定の明示リスト**だった(ADR-033 決定4 は「決まったら `fill_cells` を呼ぶ経路に置き換わる」と書いた)。**`M*` = 999 は決まった(ADR-074)** | 同 506 行付近 |
| 5 | config が null | `eval.pool_seed: null`(いまは消費されない) | 同 509 行付近 |
| 6 | 順6 に移された検査 | ADR-057 決定4: バッチの浮動小数ノイズ検査(ADR-040 決定7)と preflight の `forced_choice_tokens` 検査。**どちらも `comparison` 群のプールが要る** | `logs/DECISIONS.md` ADR-057 |
| 7 | コードが無い | **タスク5(test-retest、`num_repeats = 3`)が回らない。**`code/eval/model.py` の `SUPPORTED_NUM_REPEATS = 1` と `reject_unimplemented_settings` が他の値を拒む。**反復生成は未実装** | `code/eval/model.py:52` / `:157-165` |
| 8 | 足りている | 項目生成は全群ある(`code/eval/battery/build.py` / `t3_comparison.py` / `numeric_sum.py` / `specificity_control.py`、強制選択 `code/eval/forced_choice.py`、定数戦略 `code/eval/scoring.py` の `constant_answer_baseline`)。トークン境界 #0 は `infra/preflight.py`(順1b で実行済) | — |

- **GPU 時間の見積りは repo に無い**(「GPU 小」という定性の記述だけ。`plans/PLAN-019` 597・601 行付近)。
  実測は順5 の自由生成だけ: 0.307 秒/項目(バッチ 4・RTX 4090)[run:20260910_104249_sweep_m]。**強制選択の時間は未照合**(順1b の run を見ること)
- 項目数の目安は PLAN-001 §5.1 の主軸 1,560 項目(うち強制選択 960)+ 副次(P-2 800 / テンプレート税 240 / R8 8,160 / 指示付き T1)。
  **組合せ論的な計数であって実験結果ではない。順6 がどれを回すかは未確定**

### 1.1 追加の監査(2026-09-11 その41。読み取りと組合せ論的な計数だけ。GPU 0)

| # | 中身 | 場所 |
|---|---|---|
| A1 | **`fill_cells` は被覆を `label_coverage`(4 値)で照合する。**主軸 3 水準目の `extrap_magnitude` は `label_main_coverage` にしか現れないので、**`coverage: extrap_magnitude` のセルは候補 0 件で `InsufficientCandidatesError` になる。**`coverage: extrap` と書くと、負の被演算子や片側だけ域外の組を含む母集団から引く(ADR-027 決定1 の C6 ではない) | `code/data_gen/pool.py:650`(照合)/ `:201`(`label_main_coverage`) |
| A2 | **候補を訓練域 `[1,99]²` 全体から渡すと、pilot 領域の組が `interp` に入る。**`label_coverage` は K_main に無い組をすべて `interp` と呼ぶため。現行 config と `exp_phase1_main_p2` の K で数えると、除外を掛けた後の `interp` 候補は **main 領域 2,484 組(carry 558)に対して pilot 領域 4,405 組(carry 956)**(組合せ論的な計数。実験結果ではない)。**PLAN-002 §4.7 手順3 と PLAN-001 §4.6 は main 領域から引くことを要求している。つまり候補の組み立て方も仕様に含まれる** | `plans/PLAN-002-ft-data.md:678-693` / `plans/PLAN-001-eval-battery.md:376-398` |
| A3 | **訓練域外を 50:50 に分ける処理(PLAN-002 §4.7 手順4)が実装されていない。**`split_pilot_main` を呼んでいるのは訓練域だけである | `plans/PLAN-002-ft-data.md:693` / `code/data_gen/ft_data.py:650` |
| A4 | **`Cell` は `name / coverage / carry / n` しか持たない。**セルから群・`category`・閾値オフセットへの写像がどこにも無い。明示リストの行には群ごとの鍵(`category` / `threshold_offset`)があるが、セル表には無い | `code/data_gen/pool.py:600-612` / `configs/smoke.yaml:136-158` |
| A5 | **T3 / T1b の閾値オフセットをどう割り当てるかは、どの文書にも書かれていない。**PLAN-003 §4.4.1 は「`>` 形式は θ ∈ {0, +1}、`<` 形式は θ ∈ {+1, +2} で測る」とだけ書き、1 セル 40 項目を 2 つのオフセットにどう配るかは書いていない(`threshold_offset` で `plans/` と `logs/DECISIONS.md` を検索して 0 件) | `plans/PLAN-003-redesign.md:351-355` / `code/eval/battery/t3_comparison.py:73-78` |
| A6 | **`metrics.json` は採点バッチ単位**(`by_batch`)で、`comparison` は T3 と T1b と全被覆水準を 1 バッチに混ぜる。**Go/No-Go #2(タスク型 × 既知性のセル)と #3 の T1b × `id`(ADR-047 決定2)は、この形からは読めない。**セル別の行は `code/analysis/frame.py` の `build_rows` が組めるが、それを #1〜#3 の形に集計するコードが無い | `code/eval/run.py:437-458`・`:974` / `code/analysis/frame.py:364` |
| A7 | **`python -m code.eval.run --config configs/exp_phase1_main.yaml --dry-run` は必ず止まる。**dry-run が読むのは `eval.dry_run_items` で、本番 config にこの欄が無い。**dry-run は実プール(`items.jsonl`)を読まない** | `code/eval/run.py:220-229`・`:489-530` |
| A8 | **`compare_runs.py` は 2 つの run の項目集合が一致することを要求する。**ADR-040 決定7 の「プールの部分集合 100 項目」を batch 4 の本体 run と突き合わせるには、100 項目の batch 4 run をもう 1 本回すか、比較を共通部分に絞る実装が要る | `code/analysis/compare_runs.py:228` / ADR-040 決定7(`logs/DECISIONS.md:1992`) |
| A9 | **★文書のあいだで食い違いがある。**Go/No-Go #2 は**素のモデル**の `correct_rate` で「落ちたセルの一覧を凍結前に確定する」と書く。一方、適格性フィルタの本体は **`ident` 条件の同一項目**の `correct_rate` でセルを落とすと書き、ADR-041 決定2 の根拠でも「`none` の素の算術能力」と「`ident` の FT 後」を区別している。**`ident` の run は Phase 1(凍結の後)にしか存在しない。**どちらの一覧が主解析を縛るかを決めた ADR は見つからなかった | `Documents/04_EXPERIMENT_PLAN.md` Go/No-Go #2 / `plans/PLAN-003-redesign.md:667-669` / `Documents/05_STATISTICS.md:41` / `logs/DECISIONS.md:2048`・`:2061` |
| A10 | 監査 #2 の群の一覧は**照合した**。`SUPPORTED_GROUPS` = `comparison` / `bare_sum` / `bare_sum_instructed` / `word_problem` / `specificity`。**T3 と T1b はどちらも `comparison` 群**(`category` が `t3_*` か `t1b_*` か)である | `code/data_gen/battery_items.py:44-50` / `code/eval/battery/t3_comparison.py:44` |
| A11 | **強制選択の時間は測られていない。**順1b の 2 本は `bare_sum` と `word_problem` だけで、`comparison` を含んでいない([run:20260828_100115_smoke1b_b1] の `by_batch` = `bare_sum` 8 / `word_problem` 11) | `runs/20260828_100115_smoke1b_b1/metrics.json` |
| A12 | **本番 config で dry-run・本実行を回すと、run ディレクトリ名と `experiment_id` が Phase 1 本実験と同じ `exp_phase1_main` になる。**`aggregate.py` / `frame.py` の `--runs` の glob に順6 の run が混ざりうる(`adapter = null` と `seed = null` の警告は出る) | `configs/exp_phase1_main.yaml:15` / `code/eval/run.py:1150-1156` |
| A13 | 文言の食い違い(小): PLAN-002 §4.2 付近は「1 つの組は T1 / T1b / T2 / T3 と極性で使い回せる」と書くが、PLAN-001 §5.1・ADR-026 のリスク欄は「セル間で組を再利用しない」(`id` 要求 520 組はこの前提での合計)。**本 PLAN は承認済みの後者に従う** | `plans/PLAN-002-ft-data.md:396-397` / `plans/PLAN-001-eval-battery.md:464-467` / `logs/DECISIONS.md:1102-1103` |

**セルは埋まる(組合せ論的な計数。現行 config と `exp_phase1_main_p2` の K。除外 = 被演算子 ±1・偶然一致・`p2`/`p2d` 判別不能)**:
`id` は carry 406 / nocarry 1,348、`interp`(main 領域だけ)は carry 558 / nocarry 1,926。**`Q(999)` は 810,000 組のうち 729,000 組**(carry 162,000)が残る。
主軸の要求は `id` / `interp` / `extrap_magnitude` のどれも carry 240 + nocarry 240 + 特異性対照 40(層別なし)なので、**どの被覆水準でも候補が要求を上回る。**
K_main の 2,000 組はすべて main 領域の中にある。

---

## 2. 起草で決めること

> **案はエージェントのものであり、決定ではない**(`CLAUDE.md` §8 / ADR-039 決定3)。新しい設計判断はすべて ★F128〜★F137 として
> `logs/OPEN-ITEMS.md` に上げた。記入欄は §2.6 である。

### 2.1 順6 が回す群・セル・項目数 / 主プールかパイロット専用プールか / タスク4 の「5 シード」

**現状**

- 順6 の中身の正本は `Documents/04_EXPERIMENT_PLAN.md` Phase 0(タスク 4〜6 は `:42-44`、Go/No-Go #0〜#3 は同じ節の表)と
  `plans/PLAN-004-phase0-route.md` 順6(`:326-334`)である。**#1 は T1 / T2 / 特異性対照、#2 は全 (タスク型 × 既知性) セル、#3 は T3 / T1b**
- タスク6(プロンプト感受性)は **T2 だけで測る**(ADR-042 決定9。`logs/DECISIONS.md:2173`)。**これは決着済み**
- 主軸のセル表(`plans/PLAN-001-eval-battery.md:441-450`、特異性対照は `plans/PLAN-003-redesign.md:443-459`)は **42 セル・1,560 項目**
  (自由生成 600 / 強制選択 960)。指示付き T1(ADR-035 決定2。`logs/DECISIONS.md:1643`)は **T1 と同じ組・`id` × carry 2 セル・80 項目**
- プールは `pool_id` = `main` と `pilot` の 2 つがある(PLAN-001 §4.6)。**`pilot` の FT データ(K_pilot)はまだ生成していない**
  (`data/generated/ft/` にあるのは `exp_phase1_main_*` と smoke 系だけ)
- PLAN-019 の F91 は「順6 は評価プールの上で回る」と、F92 は「順6 は落ちたセルの一覧を確定する段そのもの」と書いている
  (`plans/PLAN-019-validity-decisions.md:74-75`)。**ただしプールが main か pilot かを決めた ADR は無い**
- タスク4「健常時スコアを5シードで測定(`none` モデル)」の**シードが何を指すかを書いた文書は無い。**`adapter = null` の run の
  `seed` は `None` になり(`code/eval/run.py:878-900`)、デコードは貪欲である(ADR-042 決定2)

**案**

- **群 = `comparison` / `bare_sum` / `bare_sum_instructed` / `word_problem` / `specificity`**(A10 で照合済み)。
  `bare_sum_instructed` を入れるのは、#1 が割れたときの第一手(ADR-042 決定5 (i) = 答え書式の指示を足す)の実測を**同じ run で取っておく**ためである。
  **80 項目・T1 の組の再利用なので、GPU 時間は増えない**(★F135)
- **セル = 主軸の 42 セル + 指示付き T1 の 2 セル。項目 = 1,640**(自由生成 680 / 強制選択 960)。**副次(P-2 / テンプレート税 / R8)は順6 では回さない。**
  ただし、後から足しても主軸の割当が動かない形で実装する(§2.2 の (iv))
- **プール = `main`**(★F129)。理由:
  1. **#2 と適格性フィルタは「同一項目」の正答率で決まる**(`plans/PLAN-003-redesign.md:667-669`)。pilot の項目で測った一覧は、主解析の項目の一覧ではない
  2. `pilot` を使うには K_pilot の FT データを先に生成する必要がある(順6 の前の作業が増える)
  3. §5 の Δ は順6 の実測から「移し替える」ことが既に決まっている(ADR-069 決定2)。**順6 の数値を事前登録に使う設計になっている**
  4. 順6 の `none` モデルは主解析のどの条件にも入らない。主プールで測っても、本実験の条件のハイパラ選択には使われない
  - **ただし ★F128(A9)の決着によっては、この理由 1 の強さが変わる**
- **★F128(A9)の案 = 二段で読む。**順6(`none`)で割れたセルは凍結前に主解析から外し、Phase 1 では PLAN-003 §6.3 の規則どおり
  `ident` でさらに落とす。**df は ADR-064 決定2 のランク規則が、どちらの段で落ちたセルにも機械的に効く。**
  代わりに「`ident` だけが縛り、順6 の一覧は予報」「`none` だけが縛り、§6.3 の `ident` は古い記述」とする読み方もある(§2.6)
- **タスク4 = 本体 run 1 本**(★F130)。貪欲デコードでアダプタも無いので、**「シード」に対応するものが無い。**
  残る揺れは項目抽出(主プールで固定)と装置の非決定性(タスク5)だけである。
  代わりに「抽出シード 5 本 = プール 5 通り」(ADR-041 決定5 の掃引と同じ読み)とする案もあるが、#2 は主プールの同一項目で決まるので、**別の 4 プールは判定の材料にならない**

**人間に上げる点**

- **★F128**: #2 の一覧を縛るのは `none`(順6)か、`ident`(Phase 1)か、その両方か
- **★F129**: 順6 のプールを `main` にするか `pilot` にするか
- **★F130**: タスク4 の「5 シード」が何を指すか(案: 本体 run 1 本で足りるとし、`04_EXPERIMENT_PLAN.md:42` の文言を打ち消し線付きで直す)
- **★F135**: 順6 の範囲に指示付き T1 を入れるか、副次(P-2 / テンプレート税 / R8)まで入れるか
- **risk(決めることではない)**: **1 セル n = 40 なので、真の正答率が 0.70 付近のセルは抽出の偶然で基準を割りうる**
  (二項 SE は p = 0.7 で約 0.072。算術)。**閾値と n はどちらも承認済みなので、エージェントは動かさない**

### 2.2 セル表の転記は機械的か

**現状**

- セル表の出どころはすべて承認済みの文書にある:
  T1 = 3 被覆 × carry 2、T1b = 3 × carry 2 × 極性 2、T2 = 3 × carry 2、T3 = 3 × carry 2 × 極性 2、いずれも n = 40
  (`plans/PLAN-001-eval-battery.md:441-450`)。特異性対照 = 演算 2 × 3 被覆・層別なし・n = 20(`plans/PLAN-003-redesign.md:449-458`)。
  被覆 3 水準は `id` / `interp` / `extrap_magnitude`(ADR-027 決定1、`code/data_gen/pool.py:59-63` の `MAIN_COVERAGE_LEVELS`)。
  `id` 要求の合計は 520 組で、preflight の検査8 が K(2,000)と比べる(`infra/preflight.py:700`)
- プールを作る経路は**明示リスト**のままである(`code/data_gen/eval_pool.py:79`・`:263-336`。ADR-033 決定4)。`eval.cells` は manifest に写すだけで、**`fill_cells` は呼ばれていない**
- config の `cells` の注記(`configs/exp_phase1_main.yaml:493-498`)は「T2 の文面は承認待ち-6」と書いたままである(**古い注記**。ADR-032 で決着済み)

**案 —— 転記の本体は機械的だが、次の 5 点は機械的に決まらない**

| # | 点 | 案 | 種類 |
|---|---|---|---|
| (i) | **T3 / T1b の閾値オフセットの割り当て**(A5) | **各セル 40 項目を、極性ごとに認められた 2 つのオフセットへ 20 / 20 で配る。**配り方は決定的にする(セル内で組を並べた順に交互に配る。乱数は使わない) | **★F131。新しい設計判断** |
| (ii) | **`fill_cells` が被覆をどの語彙で照合するか**(A1) | **`label_main_coverage` で照合する。**`coverage: extrap` のセルは受け付けず、止める(C6 と取り違えないため) | 承認済みの ADR-027 決定1 / ADR-062 決定1 の実装。**★F137-1** |
| (iii) | **候補の組み立て方**(A2・A3) | `[1,99]²` の組は **main 領域だけ**を候補にする(`ft_data.py` と同じ関数・同じ引数で分割を再現し、FT manifest の `pool_split.counterpart_region_hash` と照合して、違っていれば止める)。`extrap_magnitude` の候補は **`Q(M*)` のうち main 側の半分**だけにする。**訓練域外の 50:50 は組ごとのハッシュ**(`pool_split_seed` と `(a, b)` から決める)で分ける —— 期待値では 50:50 になるが、ちょうど半分にはならない | 承認済みの PLAN-002 §4.7 の実装。**ただし 50:50 をどう実現するかは仕様に無い。★F137-2** |
| (iv) | **副次セルを後から足したときに、主軸の割当が動かないこと** | **セルごとに別の乱数列**(`pool_seed` とセル名から作る)で候補を並べる。現行の `fill_cells` は候補全体を 1 回だけシャッフルするので、候補集合が変わると主軸の割当も動く | ADR-017 の性質(重複なし・足りなければ止める・シードで再現)は保つ。**★F137-3** |
| (v) | **`eval.pool_seed` の値** | **3**(`pool_split_seed` 0 / `coverage_seed` 1 / `sample_seed` 2 に続く番号)。値そのものに意味は無いが、`[MATCHED]` の実験定数なので人間が置く(PLAN-006 の抽出シードと同じ扱い) | **★F136** |

- **機械的な転記として扱うもの**: 42 セルの名前・被覆・carry・n / `Cell` に群と `category` の欄を足す(A4)/
  **指示付き T1 はセルとして埋めず、T1 の `id` セルの組から作る**(ADR-035 決定2「T1 と同一の被演算子対」。`fill_cells` の「組を再利用しない」規則と衝突させないため)/
  `eval.pool_items` を消す(ADR-033 決定4 がそう予告している)/ 古い注記を直す / `eval.anchor_manifest` にプールの manifest のパスを書く
- **組はセル間で再利用しない**(PLAN-001 §5.1。A13 の食い違いは承認済みの側に従う)

**人間に上げる点**

- **★F131**: 閾値オフセットの割り当て(案は 20 / 20・決定的)。代わりの案: (b) 極性ごとにオフセットを 1 つに固定する
  (**PLAN-003 §4.4.1 が 2 つずつ挙げているので、その記述と食い違う**)/ (c) `pool_seed` で項目ごとに無作為に選ぶ
- **★F136**: `pool_seed` の値
- **★F137**: (ii)〜(iv) の実装判断(**異議が無ければ実装のまま進める。ADR-072 決定3 と同じ扱い**)

### 2.3 反復生成の実装範囲(`num_repeats = 3` はタスク5 だけ)

**現状**

- `code/eval/model.py:48-52`・`:157-165` は `num_repeats` が 1 以外なら止まる。config は `num_repeats: 1`(ADR-072 決定2)。
  **ADR-072 は test-retest の反復回数を決めていない**
- ADR-042 決定3: 貪欲なので **test-retest が測るのは装置の非決定性**である
- `04_EXPERIMENT_PLAN.md:43` と `PLAN-004` 順6 のチェックリストは「温度0・`num_repeats=3`」と書いている
- `code/analysis/compare_runs.py` は 2 つの run を項目ごとに突き合わせる(生成文字列 / 抽出値 / 強制選択の `parsed`)。**生成設定が同じ 2 本の比較も扱える**(差の欄が空になるだけ)

**案 —— 反復生成は実装しない。test-retest は「同じ config で別プロセスの run を 3 本」とする**(★F132)

- 理由:
  1. 本実験の条件は **run ごとに別プロセス**で比べる。条件の比較を汚しうるのは **run 間の非決定性**(重みの読み込み・カーネルの選択)であり、1 プロセスの中で同じバッチ構成を 3 回回しても、それは測れない
  2. **コードを変えずに済む。**`num_repeats` を実装すると `model.py` / `run.py` の `predictions/` の形 / `frame.py` の行 / `rescore.py` に波及する
  3. 3 本の突き合わせは `compare_runs.py` のままでできる(R1 対 R2、R1 対 R3)
- `num_repeats` は 1 のまま。**`04_EXPERIMENT_PLAN.md:43` と PLAN-004 順6 の「`num_repeats=3`」は打ち消し線付きで直す**(人間の承認の後)
- 報告するのは、4 値の分類と抽出値が食い違った項目の件数と中身だけである。**合否の基準は置かない**(タスク5 は Go/No-Go の合否条件から外れている。`04_EXPERIMENT_PLAN.md` Go/No-Go 表の下の注)
- 代わりの案: (b) `run.py` に反復生成を実装する(1 プロセスの中で 1 項目を 3 回生成する)/ (c) (a) と (b) の両方

**同じ節で扱う装置の検査 2 件**

- **バッチの浮動小数ノイズ検査(ADR-040 決定7)**: 案は **主プール全体を batch 1 で 1 本回し、R1(batch 4)と `compare_runs.py` で突き合わせる**(★F134)。
  100 項目の部分集合で取ると、項目集合が一致しないため比較にコードが要る(A8)。全体で取ればそれが要らず、決定7 の「100 項目」より多くの項目を覆う。
  代わりの案: (b) 決定7 の文言どおり 100 項目で取る(部分集合のプールと batch 4 の対照 run がもう 1 本要る)
- **タスク6(プロンプト感受性。T2 のみ)**: T2 の場面は組の sha256 で 1 つに決まる(`code/eval/battery/numeric_sum.py:146-164`)ので、主プールの T2 は
  **1 組 1 場面**(場面は組に入れ子)である。案は **T2 の 240 組 × 5 場面の交差**(★F133)。
  「同じ問いを5テンプレートで訊いたときの分散」(`04_EXPERIMENT_PLAN.md:44`)の文言どおりにするには交差が要る。
  **960 項目を足し、主プールとは別のディレクトリに置く**(主プールの項目集合を変えない)。代わりの案: (b) 主プールの T2 240 項目(入れ子)で済ませる。
  **★F104(`s2_tmpl` の取得元)とは別の決定である。**交差なら場面の分散を項目の分散から分けて推定できるが、
  それを `s2_tmpl` に使ってよいかは F104 の側で決める

**人間に上げる点**

- **★F132**: test-retest の形(案 = 同じ config の run 3 本。反復生成は実装しない)
- **★F133**: タスク6 の形(案 = T2 の 240 組 × 5 場面の交差・別プール)
- **★F134**: バッチノイズ検査の範囲(案 = 主プール全体を batch 1 で)

### 2.4 GPU 時間の見積りと GPU 承認の文面

**現状**

- 実測された秒数/項目は 3 つある(**どれも別の項目集合の値**):
  バッチ 4 の自由生成 **0.307**(裸の和 20,000 項目)[run:20260910_104249_sweep_m] /
  バッチ 4 の自由生成 **0.276**(19 項目。うち T2 が 11)[run:20260828_095717_smoke1b] /
  バッチ 1 の自由生成 **0.754**(同じ 19 項目)[run:20260828_100115_smoke1b_b1]。
  重みの読み込みは **95.7 秒** [run:20260910_104249_sweep_m]
- **強制選択は測っていない**(A11)。T2 の応答はトークン長の中央値が 56 で、T1 は 8 だった(n = 11 / 8)[run:20260828_100115_smoke1b_b1]
- 順5 のポッドは 8,094 秒稼働し、そのうち run は 6,250 秒だった。**準備と回収に約 0.5 時間**かかった(`logs/OPEN-ITEMS.md`「停止中ポッドの terminate」の行 / [run:20260910_104249_sweep_m])

**案(§2.1〜§2.3 の案をすべて採った場合)。★これは見積りであって実測ではない(`CLAUDE.md` §2)**

| run | 中身 | 項目・回 | バッチ | 見積り |
|---|---|---|---|---|
| preflight | #0 トークン境界 / `forced_choice_tokens` / 環境 | — | — | 数分 |
| **R1** | 本体(#1〜#3 / タスク4) | 1,640 | 4 | 約 10 分 |
| **R2 / R3** | R1 と同じ config の再実行(タスク5) | 1,640 × 2 | 4 | 約 20 分 |
| **R4** | 主プール全体を batch 1 で(ADR-040 決定7) | 1,640 | 1 | 約 22 分 |
| **R5** | タスク6 の交差(T2 の組 240 × 残り 4 場面) | 960 | 4 | 約 7 分 |
| | | **7,520** | | **計算は約 1 時間** |

- 見積りの仮定: バッチ 4 は自由生成も強制選択も **0.307 秒/項目**、バッチ 1 は **0.754 秒/項目**、run ごとに重みの読み込み 95.7 秒。
  **強制選択を自由生成と同じ秒数と置いたのはエージェントの仮定である**(強制選択は 1 回の forward pass で済み、自由生成は prefill に加えて decode が要るので、上から押さえる側の値として置いた)。
  **T2 と特異性対照の応答は T1 より長い**ので、**悲観側では 2 倍の約 2 時間**と見る
- **準備込みで 2〜2.5 時間。打ち切りは 3 時間(案)。**10 GPU 時間の門(`CLAUDE.md` §2)には届かない
- ★F132〜★F134 で最小の案を採った場合(R4 を 100 項目、R5 なし): 計算は約 35 分

**GPU 承認の文面(案。人間がこのまま承認するか、直して承認する)**

> 順6(Go/No-Go #0〜#3 + Phase 0 タスク4〜6)の GPU 使用を承認するか。
> - モデル: `meta-llama/Llama-3.1-8B-Instruct`(revision `0e9e39f…`)。**adapter = null**(素の重み。FT は 1 本も回さない)
> - プール: `data/generated/battery/main/`(`pool_id: main`)。**本 PLAN §4 で生成し、manifest をコミットした後に回す**
> - run: preflight → R1 本体 → R2・R3 再実行 → R4 batch 1 → R5 タスク6(★F133 で交差を選んだ場合だけ)。合計 7,520 項目・回
> - GPU: RTX 4090 SECURE 1 台(順5 と同じ型)。**単価は起動の直前に読み直す**(2026-09-10 時点で $0.74/時。ADR-073 決定1)
> - 見積り: 計算は約 1 時間(悲観側で約 2 時間)、準備込みで 2〜2.5 時間。**3 時間で打ち切って報告する**
> - 終了後: run を開発機に回収・コミットし、ポッドを停止する(`infra/RUNPOD.md` §7)。terminate は人間が行う
> - **承認の対象は順6 だけであり、Phase 1 本実験 40 run の GPU 構成ではない**

**人間に上げる点**

- **GPU 承認**(上の文面。既存の OPEN-ITEMS「GPU 構成 / 順6 を回す承認」の行)
- **順6 の GPU 型を本実験 40 run と揃えるか。**ADR-057 決定2 が本実験から切り離したのは順5 だけである。
  **★F128 で「`none` の一覧が縛る」を採るなら、その一覧はこの GPU で出した数値になる**(ADR-057 決定2 のリスク欄と同じ形)。
  本実験の GPU 構成はまだ決まっていない

### 2.5 (余裕分)E-5 (b) —— K の出どころを `metrics.json` に焼き込む

**現状**

- `metrics.json` の `pool` ブロックは `pool_id` / `items`(パス)/ `n_items` しか持たない(`code/eval/run.py:968-972`)
- 被覆ラベルの K は、`frame.py` の `load_run` が `config.yaml` の `data.matched_manifests` を `lesion.condition` で辿り、FT manifest の
  `coverage.pairs_hash` を照合して読む(`code/analysis/frame.py:208-278`。**ADR-062 で E-5 = (a) に決まった**)
- **順6 は、主プールで回す最初の評価 run になる。**`adapter = null` の run でも `lesion.condition`(本番 config では `p2`)が
  K の出どころを決める(`code/eval/run.py:572-576` の `NO_ADAPTER_NOTE`)

**案 —— (b) を採るなら、期限は「本実験の前」ではなく「順6 の前」になる**

- `metrics.json` の `pool` ブロックに、プールの manifest のパス・`pairs_hash`・`items.jsonl` の sha256 を足す。
  さらに `coverage` ブロックを新設し、FT manifest のパス・`data_id`・`coverage.pairs_hash`・`coverage_k`・`train_domain.hi` を書く。
  値は `eval_pool.load_condition_manifest` で読む(`frame.py` と**同じ関数**)
- **正本は (a) のままにする**(ADR-062 を覆さない)。`frame.py` は (a) で K を読み、(b) の記録と食い違えば止める。(b) は記録と照合の材料である
- **掃引の run(`kind` = sweep)には掛けない**(被覆ラベルを使わない)

**人間に上げる点**

- **E-5 (b) を採るか**(既存の OPEN-ITEMS の行)。**★採るなら、順6 の前に実装しないと順6 の run が対象から漏れる**

### 2.6 記入欄(人間)

> **それぞれ ⬜ を 1 つ選ぶか、別案を書いてください。**案は §2.1〜§2.5。**エージェントの推奨は (a) だが、決定ではない。**
> **先に決めると実装に進めるもの**: ★F128 / ★F129 / ★F131 / ★F135 / ★F136 / ★F137(プールの生成に効く)。
> **GPU の前までに決めればよいもの**: ★F130 / ★F132 / ★F133 / ★F134 / GPU 承認 / E-5 (b)

| 記号 | 決めること | (a) 推奨 | (b) | (c) |
|---|---|---|---|---|
| **★F128** | #2 の一覧を縛るもの | ⬜ 両方(`none` で凍結前に落とし、`ident` でさらに落とす) | ⬜ `ident` だけ(順6 は予報) | ⬜ `none` だけ(PLAN-003 §6.3 を直す) |
| **★F129** | 順6 のプール | ⬜ `main` | ⬜ `pilot`(K_pilot の FT データを先に作る) | — |
| **★F130** | タスク4 の「5 シード」 | ⬜ 本体 run 1 本(文言を直す) | ⬜ 抽出シード 5 本(プール 5 通り) | ⬜ 再実行 5 本(タスク5 に合流) |
| **★F131** | T3 / T1b の閾値オフセット | ⬜ セル内で 20 / 20・決定的 | ⬜ 極性ごとに 1 つに固定 | ⬜ 項目ごとに無作為 |
| **★F132** | test-retest の形 | ⬜ 同じ config の run 3 本 | ⬜ 反復生成を実装 | ⬜ 両方 |
| **★F133** | タスク6 の形 | ⬜ T2 の 240 組 × 5 場面の交差(+960) | ⬜ 主プールの T2 240(入れ子) | — |
| **★F134** | バッチノイズ検査の範囲 | ⬜ 主プール全体を batch 1 | ⬜ 100 項目(決定7 の文言どおり) | — |
| **★F135** | 順6 の範囲 | ⬜ 主軸 + 指示付き T1(1,640) | ⬜ 主軸だけ(1,560) | ⬜ 副次もすべて |
| **★F136** | `eval.pool_seed` | ⬜ 3 | ⬜ 別の値: ___ | — |
| **★F137** | 実装判断 3 件((ii) 語彙 / (iii) 候補と 50:50 / (iv) セルごとの乱数列) | ⬜ 異議なし | ⬜ 異議あり: ___ | — |
| **GPU** | 順6 の GPU 承認(§2.4 の文面)と GPU 型 | ⬜ 承認(順5 と同じ型) | ⬜ 本実験の GPU 構成を先に決める | — |
| **E-5 (b)** | K の出どころを焼き込むか | ⬜ 採る(順6 の前に実装) | ⬜ 採らない | — |

---

## 3. やらないこと

GPU / ポッド / 事前登録済みの閾値(#1 = 0.02 / #2 = 0.70 など)の変更 / 実験条件の追加・削除(`CLAUDE.md` §8)

---

## 4. 実装手順(skill `code-style` の順。**★F128〜★F137 の決定の後に IMPLEMENTER が行う**)

> **config を先に書き(マジックナンバーを置かない)、data_gen の関数とテスト → 入口 → eval → analysis の順に進める。**
> **層をまたがない**(`code/data_gen/` → `code/eval/` → `code/analysis/`)。**仕様が曖昧なら実装せずに質問として返す。**

1. **config**(`configs/exp_phase1_main.yaml`)
   - `eval.batteries` = ★F135 の範囲 / `eval.cells` = 42 セル(+ 群と `category` の欄)/ `eval.pool_seed` = ★F136
   - `eval.pool_items` を消す(ADR-033 決定4)。`cells` の古い注記(`:493-498`)を直す
   - Go/No-Go の閾値を転記する: `gonogo.parse_fail_max: 0.02`(ADR-065 決定1)/ `gonogo.min_cell_correct_rate: 0.70`(ADR-041 決定1)。
     **`magnitude_sweep.theta` を流用しない**(ADR-041 決定2: `θ` と #9 は独立の決定)
   - `resources:` は GPU の承認が出てから順6 の値に書き換える(順5 の値は打ち消し線で残す)
2. **`code/data_gen/pool.py`**(★F137)
   - `fill_cells` の照合を `label_main_coverage` に替え、`coverage: extrap` のセルは止める / セルごとの乱数列
   - 候補を組む関数を新設する: main 領域の再現と `counterpart_region_hash` の照合 / `Q(M*)` / 訓練域外の 50:50
   - テスト: `extrap_magnitude` のセルは `a, b > 99` の組だけから埋まる / pilot 領域の組は 1 件も入らない / セルを 1 つ足しても他のセルの割当は変わらない /
     ハッシュが食い違えば止まる / 同じシードなら同じ割当になる
3. **`code/data_gen/eval_pool.py`**
   - 明示リストの経路を `fill_cells` の経路に替える: セル → 組 → 項目の行(群・`category`・閾値オフセットは ★F131 の規則で決める)→ `build_items_from_entries`
   - 指示付き T1 は T1 の `id` セルの組から作る / manifest の `fill.method` = `fill_cells`、`seed_consumed` = true
   - テスト: 項目数(1,560 または 1,640)/ セルごとの件数 / `id` の合計 520 / 被演算子 ±1 が 0 件 / 決定性(同じシードなら `pairs_hash` が同じ)/
     T3・T1b のオフセットの内訳が ★F131 のとおり
4. **`code/eval/run.py`**
   - `--dry-run` は、`eval.dry_run_items` が無ければ生成済みのプール(`items.jsonl`)を読む(A7。本実行と同じ経路を通すため)
   - **E-5 (b) を採った場合だけ**: `pool` と `coverage` のブロック(§2.5)
5. **`code/analysis/gonogo.py`(新規)**
   - `frame.py` の行から、#1(群ごとの `parse_fail`)/ #2(タスク型 × 既知性の 4 値)/ #3(T3・T1b のタスク型 × 既知性ごとの定数戦略ベースライン)を表にする
   - 閾値は config から読み、割れたセルに印を付けるだけにする。**解釈と Go/No-Go の判断は人間が行う**(`CLAUDE.md` §8)
   - 定数戦略の理論値は行の真値から数える(`code/eval/scoring.py` を import しない。層をまたがないため)
   - テスト: 4 値の合計が 1.0 / 合成データでのセル集計 / 閾値が null なら止まる
6. **★F133 = 交差の場合だけ**: T2 の組を 5 場面で作る経路(`numeric_sum.py` の場面の割当を外から指定する)と、別のプールディレクトリ
7. **★F134 = 全体を batch 1 の場合**: batch 1 の config(`batch_size` と `experiment.id` だけが違う)と、**差がその 2 欄だけであることを縛る回帰テスト**
8. `pytest code/tests -q` → `logs/CHANGELOG.md` → commit

## 5. dry-run と検証のコマンド

ローカル(Windows。**`PYTHONIOENCODING=utf-8` を付ける**。標準出力が cp932 のため):

```bash
PYTHONIOENCODING=utf-8 python -m code.data_gen.eval_pool --config configs/exp_phase1_main.yaml --dry-run
```

```bash
PYTHONIOENCODING=utf-8 python -m code.data_gen.eval_pool --config configs/exp_phase1_main.yaml
```

```bash
PYTHONIOENCODING=utf-8 python -m code.eval.run --config configs/exp_phase1_main.yaml --dry-run
```

```bash
PYTHONIOENCODING=utf-8 python infra/preflight.py --config configs/exp_phase1_main.yaml --run-dir runs/preflight_order6 --run-kind main
```

```bash
pytest code/tests -q
```

- preflight はローカルでは GPU の検査が FAIL する。**見るのは data_checks(検査6・8 を含む)が PASS になることだけ**である
- ポッドでの手順は `infra/RUNPOD.md` §4。**run ディレクトリは `--run-dir runs/<timestamp>_order6_r1` のように名前を分ける**(A12。Phase 1 の glob に混ぜないため)

## 6. 完了条件

- [ ] ★F128〜★F137 と E-5 (b) に人間が記入した(§2.6)
- [ ] §4 の手順 1〜5(と、決定に応じて 6・7)が済み、`pytest code/tests -q` が通る
- [ ] §5 の 3 つの dry-run と preflight の data_checks が通る
- [ ] `data/generated/battery/main/manifest.json` をコミットした(**GPU を使う前に項目集合が固定されたことが git に残る**)
- [ ] GPU 承認の文面(§2.4)に人間が答えた
