# PLAN-026 — 順6b: 素のモデルの小さな診断(二値群の測り方の候補をパイロット用プールで選ぶ)

- 起草: 2026-09-12(その52)/ PLANNER (Opus)
- ステータス: ~~**草案(人間のレビュー待ち)。決定 0 件・実装 0・GPU 0。**~~ → **★2026-09-12(その53)レビュー済み(ADR-079)。実装待ち(I1〜I12)。GPU 0。**
  → **★2026-09-12(その54)I1・I2 済み**(パイロット用プールと非交差の検査。§4.3)
  → **★2026-09-12(その55)I3 済み**(R8・S の掃引項目。§4.4)。~~**次は I4・I5**(I5 の前に「階段の位置」の定義を §3.2.1 に書く)~~
  → **★2026-09-13(その56)I4 の配線の読みを §4.5 に書いた(実装は未着手。context-guard で切った)**。~~**次は I4 の実装・I5**~~
  → **★2026-09-14(その57)I4 済み**(掃引項目の記録の経路。`configs/exp_order6b_r8.yaml`・`run.py` の掃引の経路。§4.5 の「実装(その57)」)。~~**次は I5**(**I5 の前に「階段の位置」の定義を §3.2.1 に書く**)~~
  → **★2026-09-14(その58)I5 済み**(「階段の位置」の定義 = §3.2.1.1。人間が確定 = ADR-081。§5 (iv) の単位 = セル。`code/analysis/r8_fit.py`。§4.6)。~~**次は I6〜I9**(①・(d)・(c)。I9 の前に (c) の綴りを原典で確かめる)~~
  → **★2026-09-15(その59)I6・I7 済み**(① の前置き `eval.preamble`・`code/eval/preamble.py`・`run.render_prompts`・preflight 検査6 の SKIP・S-① の config。§4.7)。~~**固定オフセットの ① の config は I8 で作る**(パイロット用プールを 3 群に絞る仕方を (d) と一緒に決める = 人間の回答)~~
  → **★2026-09-16(その60)I8 済み**(絞りの宣言 `eval.task_subset` = ADR-082 / `code/eval/task_subset.py` / (d) のテンプレート集合 `configs/templates/order6b_d.yaml` / config 3 本(固定 ①・固定 (d)・S-(d))。§4.8)。~~**次は I9**(**前に (c) の綴りを原典で確かめる**)~~
  → **★2026-09-16(その61)I9 済み**((c) の綴りを原典で確認 = 一致 / 空文字は literal・3 種は生の確率を平均してから正規化 = ADR-083 / `code/eval/calibration.py`・`calibration_run.py` / `configs/exp_order6b_c.yaml`(306 件)。§3.5 の追記・§4.9)。~~**次は I10・I11**(上位 k・判定表)~~
  → **★2026-09-16(その62)I10 済み**(最初の出力位置の上位 k の記録。k の置き場所・綴りの形・固定オフセットの行の欄 = ADR-084(人間が選択式で採択)/ `eval.forced_choice_top_k: 20` を順6b の config 7 本に / 3 経路の行に `top_k`・`top_k_mass`。§4.10)。~~**次は I11**(判定表・極性別の参照線・(c) の補正を順6b の項目と R8 に掛ける経路)~~
  → **★2026-09-16(その63)I11a 済み**(I11 を 3 つに分けた = ADR-085(人間が選択式で採択)。run 単位の表 = `gonogo.py` の解いたタスク型のセル・腕を見分ける欄・極性別の参照線・近接同点の感度の行 / `gonogo.near_tie_margin: 0.25` を順6b の config 7 本に。§4.11)。**次は I11b**((c) の補正の適用。**前に §4.11 の「I11b・I11c の前に人間に上げること」を聞く**)
  人間の回答は「全て推奨を採用。G6は(b)」。**~~G14 は未記入(推奨が無かった)~~ → その55 に人間が「確定」と記入(ADR-080 決定1)、G17 の承認はエージェントの読み**(ADR-079 決定10)。記入欄は §13。GPU の承認は §11 の文面で、実装・dry-run・§5 の凍結の後に別に取る
- 正本: **ADR-078**(決定1・2・5・7・8・10)/ **ADR-079**(本 PLAN のレビュー)/ ADR-030(R8。決定6 は ADR-079 決定1 で改めた)/ PLAN-025 §3.1・§3.4・§5 / PLAN-024 §1.3・§3 D2 (c) / PLAN-001 §4.6
- 材料: `plans/PLAN-026-materials.md`(その51。**この PLAN に写した行番号は原典を開いて照合した**。材料 §B2 に誤りが 1 つあった → §4.1)
- 関連する問い・仮説: 主要検定(タスク型 × 既知性の交互作用、`Documents/05_STATISTICS.md` §2)の df が 2 / 4 / 6 のどれになるか(ADR-078 決定6)

---

## 0. 一行要約

順6 [run:20260911_141547_order6_r1] で二値群(T3・T1b)の 6 セルが Go/No-Go #2 を割った。**素のモデル・パイロット用プールで、測り方の候補(① 前置き・(d) 指示文・(c) 較正)と R8 の閾値掃引を 1 回だけ当て、回す前に書いた選び方(§5)で候補を選ぶ。**
結果は二値群 6 セルを主解析に戻せるかの材料になる(判断は人間。ADR-078 決定6)。**`p2` などの FT モデルは 1 本も使わない。**

---

## 1. この実験が答える問い

1. **素のモデルは、閾値から遠いオフセットでは和を読んで正しく答え、閾値の近くだけ崩れるのか。どこでも読めていないのか。**(R8。PLAN-025 §5 の分岐の材料)
2. **① / (d) / (c) のどれかで、二値群のセルが #2(`correct >= 0.70`)と #3(> 常に Yes / 常に No の 0.5)を満たすか。**満たすなら、どれが最も小さい変更か(§5)
3. **① を数値型(T1・T2)に同じ長さで置いたとき、数値型の #1・#2 は崩れないか**(ADR-078 決定8 の対称性)
4. **T1b で Yes/No に乗らない質量はどこへ行っているか**(最初の位置の上位 k。ADR-078 決定5。★F139)

---

## 2. 範囲と、変えないもの

- **モデル**: `meta-llama/Llama-3.1-8B-Instruct`(revision `0e9e39f…`)、**adapter = null**。FT は回さない
- **プール**: **パイロット用プール**(`pool_id: pilot`。PLAN-001 §4.6)。**本番の主プールでは選ばない**(PLAN-025 §3.4 (f): 同じ項目で選んで測ることになる)
- **パイロットの数値は主張の根拠に使わない**(PLAN-001 §4.6 規則4)。**回す前に config に `pool_id: pilot` と書く**(規則5)
- **変えないもの**:
  - **本番の T1b・T3 の文面は 1 文字も変えない**(ADR-078 決定2)。候補の文面は**順6b 専用のテンプレート集合**として置く
  - **#2 = 0.70・#3 の値は変えない**(ADR-078 決定1)。**判定規則(`choose_from_logprobs`)は変えない**(決定5)
  - `eval.batch_size` = 4(ADR-078 決定10。近接同点は §7)
- **シード**: 素のモデルの強制選択と greedy 生成は決定的で(順6 の R1〜R3 は batch 4 どうしで応答 1,640/1,640 一致 [run:20260911_160132_order6_r2] [run:20260911_160937_order6_r3])、訓練シードも無いので、**腕ごとに 1 run** とする。
  **これは主張に使わないパイロットだから許される**(`CLAUDE.md` §2 の単一シードの禁止は主張に使う結果に掛かる)

---

## 3. 腕

**腕の数について**: ADR-078 決定1 は「腕は 4 本すべて」と書くが、決定8(数値型の前置き)と決定5(上位 k)が足されるので run の数は 4 を超える(材料 §A1 の「曖昧」)。
下表は run の単位で数えた。**S は §3.7 のエージェントの提案で、ADR-078 に無い**(採るかは記入欄 G5)。

| 腕 | 群 | 文面 | 項目 | 強制選択 / 自由生成 | 何のため | 正本 |
|---|---|---|---|---|---|---|
| **B0 基準** | 全群 | いまの文面のまま | パイロット用プール全体 1,640 | 960 / 680 | 候補と比べる対照。パイロットで順6 の型が再現するかの確認 | PLAN-001 §4.6 規則2 |
| **R8 掃引** | T3・T1b | いまの文面 | 3 既知性 × 2 `carry` × 20 組 × 2 極性 × 17 `θ` × 2 タスク型 | 8,160 / 0 | 問い1。★F138 が消える項目(極性の中で真値が変わる) | ADR-030 決定2〜6 |
| **①-bin** | T3・T1b | 前置き + いまの文面 | 固定オフセットの 960 | 960 / 0 | 問い2 | ADR-078 決定1 |
| **①-num** | T1(`bare_sum`)・T2(`word_problem`) | **①-bin と同じ前置き** + いまの文面 | 240 + 240 | 0 / 480 | 問い3 | ADR-078 決定8 |
| **(d)** | T1b | `{a}+{b}>{threshold}? Answer Yes or No.`(lt も同じ) | 480 | 480 / 0 | 問い2 | ADR-078 決定1 |
| **(c) 較正** | T3・T1b | 数を内容のない記号に置き換えた入力 | ≤ 306 | ≤ 306 / 0 | 問い2(補正は後処理。GPU 0) | ADR-078 決定1 |
| **S(提案)** | ①: T3・T1b / (d): T1b | 各候補の文面 | 減らした掃引 5 `θ`: 2,400 + 1,200 | 3,600 / 0 | ★F138 への守り(§3.7) | **なし(提案)** |

- **上位 k**(ADR-078 決定5)は**強制選択のすべての forward で記録する**(腕ではなく記録の欄。§3.6)
- 項目数の出所: 順6 R1 の群ごとの件数 = 比較 960(T3 480 / T1b 480)・`bare_sum` 240・`bare_sum_instructed` 80・`word_problem` 240・特異性 120 [run:20260911_141547_order6_r1]。**パイロット用プールは同じ手続きで作るので同じ件数になる見込み**(PLAN-001 §4.6 規則2。生成して確かめる)

### 3.1 B0(基準)

- 順6 R1 と同じ config の形で、プールだけ `pilot` に替える。**#1〜#3 の表を順6 と同じ `gonogo.py` で出す**
- 用途: (i) 候補と同じプールでの対照(§5 の「変更なし」C0)/ (ii) パイロットの二値群が主プールと同じ型(T1b は Yes・T3 は No に偏る。★F138)を示すかの確認。**型が大きく違えば、パイロットで選んだ候補を主プールに持ち込めるかが疑わしくなる**(§12)

### 3.2 R8(閾値掃引)

- 項目: 各(タスク型 × 既知性 × `carry`)セルから **20 組**を取り、極性 2 × `θ ∈ {-3, …, +13}`(17 水準)を掛ける。**T3 4,080 + T1b 4,080 = 8,160**(ADR-030 決定4。`logs/DECISIONS.md` 1288〜1291 行)
- 閾値は `T = t + θ`(**両極性とも**。`sweep_threshold`、`code/eval/battery/t3_comparison.py` 174 行)。判別可能性の強制は外す(`build_items(sweep=True)`)
- **掃引の項目は 4 値分解に入れない**(非判別項目は真値 = 規則値なので `scoring.classify` が止める。同 docstring)。記録するのは項目ごとの `yes_logp` / `no_logp` / 上位 k
- **組の選び方(仕様の穴)**: ADR-030 決定4 は「部分集合は `item_id` のハッシュで決める」と書くが、掃引の項目は極性 × `θ` ごとに `item_id` が変わる。**組 `(a, b)` の水準のハッシュで 20 組を決める**(案。条件間で固定という決定4 の趣旨はこれで満たす)
  → **★2026-09-12(その55)実装(§4.4)。20 組は極性を併合した(タスク型 × 既知性 × `carry`)セル(gt・lt の 2 セル、計 80 組)から取る(ADR-080 決定3)**
- **固定オフセットは掃引の部分集合**(決定5: gt `θ ∈ {0,+1}` / lt `{+1,+2}`)だが、順6b では固定オフセットの項目は B0 で別に測る(主プールと同じセル構成で #2・#3 を出すため)

#### 3.2.1 ★F141(新): ADR-030 決定6 の「極性の揃え方」は、`T = t + θ` の下では `Δ̂` を識別しない

**ADR-030 決定6(`logs/DECISIONS.md` 1294〜1301 行)と PLAN-003 §4.4.2(395〜399 行)は、`logit P(Yes) = β0 + β1·θ` を当て、「`<` 形式は `θ` の符号を反転して揃える」「応答バイアスは `β0` に吸収される」「`β1 ≤ 0` は除外」と書く。**
閾値が両極性とも `T = t + θ` なので(上)、この書き方のままでは次のようになる。**算術の例であって実験結果ではない**。

- 和 `t = 50`、モデルの内部の値を `s = t + Δ` とする(`p2` なら `Δ = 2`、`ident` なら 0)
  - gt「`50 > 50+θ`?」: Yes ⇔ `s > t+θ` ⇔ `θ < Δ` → **P(Yes) は `θ` について減る**。切り替わりは `θ = Δ − 0.5`
  - lt「`50 < 50+θ`?」: Yes ⇔ `θ > Δ` → **P(Yes) は `θ` について増える**。切り替わりは `θ = Δ + 0.5`
- **文面どおり lt の `θ` の符号を反転すると**、lt の切り替わりは `−Δ − 0.5` に移る。gt(`Δ − 0.5`)と混ぜた交差点は約 `−0.5` で、**`Δ` に依らない**。
  `ident`(`Δ = 0`)も `p2`(`Δ = 2`)も同じ交差点になり、**`Δ̂ = 0`**。さらに両極性とも P(Yes) が減る向きになるので **`β1 < 0` になり、「`β1 ≤ 0` は除外」が正しく読めているセルを全部落とす**
- **応答の側を揃える(案 (a))**: `y = 1` を「和は閾値より小さい側と答えた」(gt では No、lt では Yes)と置くと、gt の切り替わりは `Δ − 0.5`、lt は `Δ + 0.5`、混ぜた交差点は `Δ` になり、`β1 > 0`。
  このとき一定の Yes 偏りは gt と lt の曲線を**逆向きに**ずらすので、**偏りは `β0` ではなく両極性の交差点の開きに出る**(極性が同数なら混ぜた `θ*` はほぼ動かない)。**開きの半分が判断基準、傾きが弁別力**になり、PLAN-025 §3.4 (a) の「偏りと弁別力を分ける」がそのまま取れる
- **もう 1 点(完全分離)**: 閾値を正しく読むセルでは、応答が `θ` の階段になる(素のモデルの強制選択は決定的)。このときロジスティックの最尤推定は存在せず(`β1` が発散する)、
  ADR-030 決定6 の「当てはめが収束しないセルは除外」が**最もよく読めているセルを落とす。**これは数学的な性質で、実験結果ではない。対処(罰則付きの推定 / 交差点を経験的に取る / 除外せず「階段」と別に数える)は G1 と同じ場で人間が決める
- **ADR-030 は事前登録の対象だが、まだ凍結していない**(順9 の前)。**直すかどうか・どう直すかは人間**(記入欄 G1)。順6b の R8 の読み(§6 の分岐)はこの選択に依存するので、**回す前に決める必要がある**。
  **§5 (iv) と §6 の分岐は、この 2 点に左右されにくいよう `β1` ではなく遠いオフセットの `correct` を主に使う**
- **→ ★2026-09-12(その53)決着(ADR-079 決定1)。揃え方 (a) 応答を揃える(`y = 1` ⇔ 閾値より小さい側と答えた)+ 極性ごとの交差点の開きを併記 / 完全分離 (a) 除外せず「階段」として別に数え、交差点は階段の位置で取る。**
  ADR-030 決定6 と PLAN-003 §4.4.2 に打ち消し線を付けた。**「階段の位置」の操作的な定義は I5 の実装の前にここへ書く(未記入)**

##### 3.2.1.1 「階段の位置」の操作的な定義(★2026-09-14 その58。IMPLEMENTER の案。~~**人間の確認待ち**~~。ADR-079 決定1 の要求。Phase 1 の R8(ADR-030)にも効く)

> **→ ★2026-09-14(その58)人間が確定(ADR-081 決定1・決定2)。**選択式で「案のまま」(位置 = `(L + U) / 2`)と「片側だけは除外して別に数える」を選んだ。**提案 エージェント / 採択 人間**。
> 実装は `code/analysis/r8_fit.py`(I5。§4.6)で、下の算術の例はテストに固定した

- **当てはめの単位**: ADR-030 決定6 のとおり(シード × 条件 × タスク型 × 既知性)セル。R8 の 1 セル = 40 組(`carry` 2 × 20)× 2 極性 × 17 `θ` = 1,360 項目(組合せ論的な件数)。
  **極性を混ぜた当てはめ(`θ*`)と、同じセルを極性ごとに分けた当てはめ(`θ*_gt`・`θ*_lt`。各 680 項目)の 3 つに、下の同じ定義を当てる**
- **目的変数**: `y = 1` ⇔ gt で `answer` が No / lt で `answer` が Yes(ADR-079 決定1)。`answer` は判定規則の答え(`choose_from_logprobs`。同点は No。ADR-078 決定5)
- **判定(θ の水準ごとに項目数 `n_θ` と `y = 1` の数 `k_θ` に畳んでから、1 → 4 の順に見る)**。`L = max{θ : y = 0 の項目がある}`、`U = min{θ : y = 1 の項目がある}`:
  1. **片側だけ**: セルの `y` がすべて 0、またはすべて 1 → **除外し、「片側だけ」として件数を出す**(すべて 0 / すべて 1 を分けて)。
     切り替わりが `θ` の窓の中に無く、位置が決まらない(最尤推定も存在しない —— `β0` が発散する)。**すべて 1 = gt で常に No・lt で常に Yes は ★F138 の定数戦略と同じ応答**で、ここに入る
  2. **階段(完全分離と準完全分離)**: 両方の `y` があり `L ≤ U` → **除外しない。「階段」として別に数え、交差点を `θ* = (L + U) / 2` に置く。**`L`・`U` を併記し、`β1` は出さない(+∞ に発散する。向きが正であることだけを記録する)
     - `L = U`(準完全分離。その 1 水準にだけ 0 と 1 が混ざる)なら `θ* = L`。**このとき最尤推定の列(`β1 → +∞`)の `−β0/β1` は `L` に収束する**ので、中点はその極限と一致する
     - `L < U`(完全分離)なら、尤度を上限に近づける列の `−β0/β1` は開区間 `(L, U)` のどこにでも取れる(一意でない)。**中点はその区間の中心**
     - **§3.2.1 の算術の例をそのまま満たす**(内部の値 `t + Δ` の決定的なモデル。**実験結果ではない**): gt だけ → `L = Δ − 1`・`U = Δ` → `θ*_gt = Δ − 0.5` / lt だけ → `L = Δ`・`U = Δ + 1` → `θ*_lt = Δ + 0.5` / 混ぜる → `L = U = Δ` → `θ* = Δ`。
       **極性の開き `θ*_lt − θ*_gt` は、真値どおりに答えるモデルで 0 ではなく 1 になる**(`θ = 0` では `t > t` も `t < t` も偽で、両極性とも真値が No のため)
     - S(`θ ∈ {−3, −2, +3, +7, +13}`)のように水準が飛ぶ場合も同じ式で、`L = −2`・`U = +3` なら `θ* = 0.5`
  3. **逆向きの階段**: 両方の `y` があり `max{θ : y = 1} ≤ min{θ : y = 0}`(`θ` が上がると 1 → 0)→ **`β1 ≤ 0`(−∞ に発散)として除外し、件数を出す**(「`β1 ≤ 0`」の内訳として別に数える)
  4. **応答が重なる(1〜3 のどれでもない)**: `logit P(y = 1) = β0 + β1·θ` を最尤法で当てる。**1 変数 + 切片のロジスティック回帰では、分離も片側だけも無ければ最尤推定は存在して一意である**(数学的な性質)ので、ここで収束しないのは数値計算の理由だけになる。
     収束しない → **「分離以外の非収束」として除外し件数を出す** / `β1 ≤ 0` → **除外し件数を出す** / それ以外 → `θ* = −β0/β1`(`β0`・`β1` を併記)
- **単調でない応答**: 項目ごとの応答列や `k_θ / n_θ` が単調でなくても、分離していなければ 4 の当てはめに入れる(**平滑化・単調回帰・項目ごとの切り替わり点は使わない**)。階段(2)は定義上単調で(`L` 以下はすべて 0、`U` 以上はすべて 1)、**重なりが 1 件でもあれば階段ではない**
- **報告**: セルごとに分類(当てはめ / 階段 / 片側だけ / 逆向きの階段 / `β1 ≤ 0` / 分離以外の非収束)・`θ*`・(当てはめなら `β0`・`β1`、階段なら `L`・`U`)・`n`。**除外は分類ごとに件数を必ず出す**(ADR-030 決定6)。**階段は除外ではない**(ADR-079 決定1)が、件数を別に出す
- **却下した案**:
  - 交差点を `U`(最初に `y = 1` が出た `θ`)に置く: 格子点に揃うが、極性ごとの当てはめで `Δ − 0.5` ではなく `Δ` になり、§3.2.1 の算術の例から 0.5 ずれる
  - 階段は区間 `[L, U]` だけを出し、点を取らない: `Δ̂ = θ*(条件) − θ*(ident)` とシードでの集計(ADR-030 決定6)に点が要る。**区間は併記するので情報は失わない**
  - 罰則付きの推定(Firth など)の `θ*`: ADR-079 決定1 で採らなかった案。値が罰則の形に依る
  - 分離を反復計算の振る舞い(`|β1|` の上限・反復回数の上限)で判定する: 判定が上限の値に依る。`L ≤ U` はデータの並びだけで決まり、新しい値を置かずに済む
  - 片側だけのセルを「窓の外の交差点」(例: `θ* < −3`)として階段に入れる: 点が決まらず `Δ̂` に入らない。件数は出す
  - `y` を `answer` ではなく `yes_logp` / `no_logp` から作った連続の確率にする(分離が起きない): 目的変数から判定規則を外すことになり、ADR-078 決定5・ADR-079 決定1(`y` は答え)から離れる
- **旧い揃え方との違い(算術。実験結果ではない。scratchpad で確かめた)**: 同じ決定的なモデルを文面どおりの揃え方(lt の `θ` の符号を反転・`y` = Yes)に掛けると、`Δ = 0` は逆向きの階段(`θ* = −0.5`)、`Δ = 2` は `β1 < 0` の当てはめ(`θ* ≈ −0.52`)になり、**差は約 −0.02 で `Δ` に依らず、しかも両方とも除外に落ちる**

### 3.3 ① 和を含まない数どうしの比較の前置き(①-bin・①-num)

**置き方の条件**(PLAN-025 §3.1、`plans/PLAN-025-binary-methods.md` 91〜96 行): 例示は和を含まない数どうしの比較 / 極性ごとに Yes と No を同数 / 順序は無作為 / 全条件(`ident` を含む)で同じ文脈 / 例示は答えだけ(理由を書かない)。

**文面の案(エージェント。記入欄 G3)** —— 4 行。人間の元の例「900>800」の形に合わせ、差はどれも 2 よりずっと大きい 3 桁の数:

```
900>800? Yes
250>610? No
340<780? Yes
920<150? No
```

- **4 行の並び順は項目ごとに `item_id` のハッシュで決める**(24 通り。案)。同じ項目は全条件で同じ並びになり(「全条件で同じ文脈」)、直近のラベルの偏り(PLAN-025 §3.1 の [11][12])は項目の間で均される。**並びを 1 通りに固定する案もある**(G3 (b))
- **例示のラベルはどの参照規則(`ident` / `p2` / `p2d` / `x2` / `arb`)の下でも同じ**(規則は和にしか掛からない)。ADR-042 決定5 (iii) の「例示に算術の答えを含めない形」に入る
- **置き場所(案。G4)**: **4 タスク型すべてで同じ文字列を、各群のいまの入力の先頭に空行を挟んで連結する。**chat template の有無など、群ごとの入力の組み方は変えない。
  別案の「前のターンとして置く」は chat 形式の群にしか置けず、裸の書式の群と非対称になる
- **①-num は ①-bin と同じ文字列を置く**(決定8 の「同じ長さ」を文字列の一致で満たす)。数値型に Yes/No の例示を見せるので、**数値型の応答が Yes/No に引かれて #1 が崩れうる。それ自体が問い3 で測る対称性の費用である**

### 3.4 (d) T1b に `Answer Yes or No.`

- 文面: `t1b_gt: "{a}+{b}>{threshold}? Answer Yes or No."` / `t1b_lt: "{a}+{b}<{threshold}? Answer Yes or No."`。**付け足す一文は T3 の文面(`configs/templates/t3.yaml`)の末尾と同じ文字列**
- 本番の `configs/templates/t1b.yaml` は変えない。順6b 専用のテンプレート集合に置く(材料 §B1)
- ★F139 への見込み: T3 は同じ一文で最初の位置の Yes/No 12 綴りの質量が中央値 0.98 / 0.99、T1b は 0.0009 / 0.0004(gt / lt)[run:20260911_141547_order6_r1]。**T1b で質量が乗るかは未測定**(PLAN-025 §3.4 (d))

### 3.5 (c) 内容のない入力による較正

- 入力: 各(タスク型 × 極性 × 文面)について、テンプレートの `{a}` `{b}` `{threshold}` を内容のない記号に置き換える。**記号の案: `N/A` / `[MASK]` / 空文字の 3 種**(エージェントの案。**文献から転記したものではない**。PLAN-025 の [11] の原典で使われた綴りを実装の前に開いて確かめ、人間が確定する。G11)
  → **★2026-09-16(その61)原典で確認済(ADR-083 決定0)**: Zhao et al. (2021) §5 "Contextual Calibration" の Implementation Details に、3 種の内容のない入力 `"N/A"`・`"[MASK]"`・空文字の確率を平均すると書かれている(**綴りは 3 種とも案と一致**)。
  同じ節に、スロットのあるプロンプト(LAMA)では主語だけを置き換える例(`N/A was born in`)があり、**`{a}` `{b}` `{threshold}` だけを置き換える作法の前例**になる。
  **空文字は literal に差し込む**(`+>?`・`Is the sum of  and  greater than ? ...` の二重空白を詰めない。ADR-083 決定1)
- 件数: いまの文面(T3・T1b)12 + (d)(T1b)6 + ①(T3・T1b。並びを項目ごとに変える場合は 24 通りすべて)288 = **306 以下**
- 記録: `yes_logp` / `no_logp`(ADR-047 実装ノートの logsumexp。同じ 12 綴り)/ 上位 k。**4 値分解は通さない**(真値が無い。`scoring.py` 82 行の `CoincidentItemError` の手前で止まる)
- 補正は**後処理(GPU 0)**。案: 補正後の判定 = `(yes_logp − no_logp) − (cf_yes − cf_no) > 0`(`cf` は同じ(タスク型 × 極性 × 文面)の内容のない入力 3 種の平均)。**同点の扱いは ADR-047 実装ノートと同じ(No)**
  → **★2026-09-16(その61)「3 種の平均」の中身を確定(ADR-083 決定2)**: **生の確率を記号をまたいで平均してから正規化する**(第一著者の実装 `get_p_content_free` の順。**論文本文は順を書いていない**)。
  2 値では正規化が差で消えるので、`b = log(mean_s exp(yes_logp_s)) − log(mean_s exp(no_logp_s))`、補正後の判定 = `(yes_logp − no_logp) − b > 0`(同点は No)。
  ~~記号ごとに正規化してから平均する~~ 読み・~~対数確率を平均する~~ 読みは採らない。実装の読みは §4.9
- **★F138 との関係(注意)**: 較正は極性ごとに別の定数を引くので、**固定オフセットの項目の上では「gt → No / lt → Yes」の定数戦略に寄せても correct が上がる。**較正が和を読んだ結果かどうかは、同じ補正を R8 の項目に掛けた曲線で確かめる(後処理。GPU 0。§5 の条件 (iv))

### 3.6 最初の位置の上位 k の記録(ADR-078 決定5)

- すべての強制選択の forward で、最初の出力位置の log-softmax の上位 **k = 20**(案。G10)の (id, 復号した綴り, logp) と、上位 k の確率の合計を記録する
- **判定規則(`choose_from_logprobs`、`code/eval/forced_choice.py` 265 行)は変えない**。全語彙の log-softmax 行は既にある(同 394 行)
- 用途: ★F139 の「質量の行き先」の記述(`Documents/06_THREATS.md` / ADR-047 実装ノートへの追記。決定5)。**合否の材料にするかは G6**

### 3.7 S: 候補の減らした掃引(エージェントの提案。ADR-078 に無い。G5)

> **→ ★2026-09-12(その53)採択(ADR-079 決定4。G5 (a))。5 水準で ① と (d) に足す(+3,600 forward)**

- **理由**: ★F138 により、固定オフセットの項目では `correct = 1` と「gt → No / lt → Yes」の定数戦略が区別できない(PLAN-024 §1.3、53〜58 行)。
  **① や (d) が #2・#3 を満たしても、それが和を読んだ結果かは固定オフセットの項目からは分からない。**B0 の文面の R8 は、候補の文面については何も言わない
- 案: ①(T3・T1b)と (d)(T1b)の文面で、R8 と同じ 20 組 × 2 極性に **`θ ∈ {-3, -2, +3, +7, +13}`** を掛ける(① 2,400・(d) 1,200)。
  gt の真値は Yes, Yes, No, No, No、lt は No, No, Yes, Yes, Yes で、**`θ = −3, −2` では真値が固定オフセットの項目と逆になる**(定数戦略はここで外れる)。
  **5 水準はすべて閾値から 2 以上離れた「遠いオフセット」**(素のモデルの閾値は `θ` = 0 と 1 の間)で、S は閾値の近くの弁別ではなく「和を読んでいるか」だけを見る。閾値の近くは固定オフセットの項目で測る
- (c) には要らない(R8 の項目に後処理で補正を掛ければよい。§3.5)
- 別案: 17 水準すべて(+12,240 forward)/ 足さない(★F138 に弱いまま選ぶ)

---

## 4. パイロット用プールの生成(CPU。GPU 0)

### 4.1 経路 —— 材料 §B2 の訂正

- 材料 §B2 は「明示リストの経路(`build_explicit`)は FT manifest を読まない」と書いたが、**誤り**である。両経路が呼ぶ共通の `assemble`(`code/data_gen/eval_pool.py` 632 行)が `load_condition_manifest`(同 659 行)で FT manifest を読み、`coverage_sums` と `id` セルの母集団を数える。
  **どちらの経路でも pilot の FT manifest が要る。**しかも `id` セルは K_pilot から引く必要があり(PLAN-001 §4.6。訓練域の分割は PLAN-002 §4.7)、main の manifest の上に建てると pilot 領域の組に `id` が付かない
- **したがって本番と同じ `build_filled`(`fill_cells`)の経路を使う**(PLAN-001 §4.6 規則2「同じ手続き」)。`main_region_pairs`(同 352 行)は `regions[pool_id]` を取るので(同 389 行)、`pool_id: pilot` をそのまま扱える
- 手順(案):
  1. `configs/exp_order6b_pilot.yaml`(新規): `configs/exp_phase1_main.yaml` と同じ値で `data.pool_id: pilot`、`data.matched_manifests` を pilot の manifest に替える
  2. `python -m code.data_gen.ft_data --config <上> --condition <c>` を**主プールと同じ 5 条件**で回し、pilot の FT manifest を作る(`ft_data.py` 646〜649 行は `pilot` を受け付ける)。**K_pilot は pilot 領域から引かれる**
  3. `python -m code.data_gen.eval_pool --config <上>` → `data/generated/battery/pilot/`(items と manifest)
  4. **非交差の検査**(PLAN-001 §4.6 規則3): いまの `assemble` は相手側の hash を `None` で記録する(「両方が存在してから掛ける」)。**両方が揃うので、pilot と main の順序対の積が空であることをテストと preflight で確かめる**(既存の検査の有無は実装の最初に確かめる。材料 §B5 の「要確認」)
  5. preflight の `data_checks`(検査6・8 を含む)を pilot の config で通す
- **pilot の FT データは Phase 0 段階 E のパイロット(`p2` / `p2d` を 2〜3 シード)でも同じものを使う**(同じ `coverage_seed` なので作り直さない)

### 4.2 R8 と S の項目

- 上の pilot の T3・T1b のセル表から、(タスク型 × 既知性 × `carry`)ごとに組 20 を組の水準のハッシュで取り、`build_items(sweep=True)` に `θ` の水準を渡す。**`θ` の水準集合は config に置く**(`sweep_threshold` の docstring。code-style §1)
- 掃引の項目は別ファイル(例 `data/generated/battery/pilot_sweep/`)に書き、固定オフセットの項目と混ぜない

### 4.3 I1・I2 の実装で決めたこと(★2026-09-12 その54。IMPLEMENTER。**決定ではなく実装の読み。異議があれば人間が覆す**)

- **生成物**(CPU。GPU 0。**件数は組合せ論的な帰結であって実験結果ではない**):
  - `configs/exp_order6b_pilot.yaml`: 本番 config の写しで、違うのは 9 欄だけ(`test_order6b_pilot.py` が縛る)。§4.1 の 2 欄に加え、`experiment.id`(`exp_order6b_pilot`)/ `experiment.plan`(本 PLAN)/ `data.manifest` / `eval.anchor_manifest` / `eval.counterpart_manifest`(下)/ `resources.estimated_gpu_hours`(§10 の悲観側 2.5)/ `resources.human_approval_date`(**null**。本番の値は順6 の承認なので写さない)
  - pilot の FT manifest 5 条件(`data/generated/ft/exp_order6b_pilot_<c>/`): K_pilot 2,000 組(`pairs_hash` `3f25df15…`)は 5 条件で同じ、`matched_stream_sha256` `2711eb5d…` も 5 条件で一致、`t_holdout` と書式ハッシュは main と一致、**K_pilot ∩ K_main = ∅**
  - パイロット用プール(`data/generated/battery/pilot/`。`pairs_hash` `b1802456…`): **1,640 項目・1,560 組。群ごとに比較 960・`bare_sum` 240・`bare_sum_instructed` 80・`word_problem` 240・特異性 120 で、順6 の主プールと同じ**。42 セルのセルごとの件数・閾値オフセットの配り方も同じ。`id` セルの母集団は 1,755 組(main 1,754)
  - pilot の config で `run.py --dry-run` が 1,640 項目で通る(モデルは読まない)
- **I2(非交差の検査)。既存の検査を確かめた結果**: preflight の `pool regions`(`check_pool_regions`)は **FT 側**(領域の再現・K が自分の領域にあること・pool_id の違う manifest どうしの K の積)しか見ておらず、**評価プールどうしの順序対の積を見る検査は無かった**(テストにも無い)。そこで足した:
  - `code/data_gen/pool.py` の `pool_manifest_problems`: 互いが相手を指すか / 各 `pairs_hash` が `pairs` から再現するか / `counterpart_hash` が記録されていれば一致するか / 積が空か
  - `infra/preflight.py` の 7 番目の data check `pool disjoint`。**相手は `eval.counterpart_manifest` で宣言させる**(本番・b1・t2cross の config は pilot を、pilot の config は main を指す)。**名前から推測しない理由**: smoke 系のプール(`smoke`・`smoke1b`)は明示リストで `pool_id: main` を名乗り、pilot と 1 組・2 組重なる。「`counterpart_pool_id` の名前のディレクトリを相手とみなす」と smoke の preflight が落ちる。宣言が無ければ SKIP、宣言した相手が無ければ FAIL
  - `pool disjoint` を `SWEEP_SKIPPED_CHECKS` に足した(ADR-057 決定3 の理由 = 掃引は評価プールを読まない、がそのまま当てはまる)
  - テスト: `test_pool.py`(PLAN-001 §4.6 規則3 の置き場所。コミット済みの両 manifest を読んで積が空であることを、関数を通さずにも数える)/ `test_preflight_checks.py`(SKIP・FAIL の切り分け)/ `test_order6b_pilot.py`(config の差・manifest の再現・件数・K の積・両 config の data_checks が 7 件 PASS)。`pytest code/tests -q` → **1049 passed**(1030 → +19)
- **★満たしていないもの(人間待ち)**: PLAN-001 §4.6 規則3 の 1 点目「各 `manifest.json` は相手プールのハッシュを持つ」。`counterpart_hash` は両方とも `None` のまま。埋めるには主プールの manifest を書き直すことになり(HANDOFF で禁止)、しかも相手を作り直すたびに主プールの manifest に差分が出る(ポッドで作り直して「差分 0 行」を確かめる手順と衝突する)。**照合そのものはテストと preflight が両方の manifest を読んで行っているので、欠けているのは記録だけである**
- **→ ★2026-09-12(その55)人間が上の実装の読みをすべて追認した**(包括の承認。ADR-080 決定2)。`counterpart_hash` は None のまま、照合はテストと preflight が両方の manifest を読んで行う形で規則3 を満たすとした

### 4.4 I3 の実装で決めたこと(★2026-09-12 その55。IMPLEMENTER。**仕様の穴の決着は ADR-080 決定3。それ以外は実装の読みで、人間が覆せる**)

- **仕様の穴(HANDOFF その54 が挙げたもの)**: §3.2 は「(タスク型 × 既知性 × `carry`)セルから 20 組」だが、パイロット用プールのセルは極性ごと(`t3_gt_id_carry` / `t3_lt_id_carry` …。各 40 組)である。
  ADR-030 決定4 は「セルから n = 20 の部分集合を取り、**極性 2** × 17 水準を掛ける」、§3.7(S)は「R8 と同じ 20 組 × 2 極性」と書くので、**同じ組を両極性で尋ねる**ことは決まっており、残るのは「極性ごとのセルのどれから引くか」だけだった。
  **→ gt・lt の 2 セル(計 80 組)を併合した候補から取る**(ADR-080 決定3。提案 エージェント / 採択 人間の包括の承認)。却下案: gt のセルからだけ / gt 10 + lt 10 / 極性ごとに別の 20 組(決定4 の「部分集合を取り、極性 2 を掛ける」に反する)
- **生成物**(CPU。GPU 0。**件数は組合せ論的な帰結であって実験結果ではない**):
  - `configs/exp_order6b_pilot.yaml` の `eval.threshold_sweep`(`task_types: [t3, t1b]` / `pairs_per_cell: 20` / `offsets.r8` = −3〜+13 の 17 水準 / `offsets.s` = {−3, −2, +3, +7, +13})
  - `code/data_gen/sweep_pool.py`(新規): `python -m code.data_gen.sweep_pool --config configs/exp_order6b_pilot.yaml --arm r8|s`。同じ config で評価プールを組み直し(`eval_pool.build`)、そのセルの割当から組を取る(`--t2-cross` と同じ形。**組を引き直さない**)
  - `data/generated/battery/pilot_sweep_r8/`: **8,160 項目**(T3 4,080 + T1b 4,080)・240 組(12 セル × 20)。`pairs_hash` `31fdd0cf…`
  - `data/generated/battery/pilot_sweep_s/`: **2,400 項目**(T3 1,200 + T1b 1,200)。**組は R8 と同じ**(`pairs_hash` も同じ)で、**項目は R8 の部分集合**
  - **items.jsonl は git に無い**(`.gitignore`)。manifest だけコミットする。ポッドでは config 冒頭のコマンドで作り直す(manifest の差分が 0 行になるはず)
- **実装の読み(人間が覆せる)**:
  1. **θ の水準集合は pilot の config にだけ置いた**(本番 config には置かない。Phase 1 の R8 の config は別に決める)。`test_order6b_pilot.py` は「9 欄 + `eval.threshold_sweep.*`」を許す形にした
  2. **組のハッシュ = `sha256(canonical_json(["threshold_sweep", eval.pool_seed, a, b]))` の小さい順**。新しいシードを足さず `eval.pool_seed` を入れた(`pool.outside_domain_side` と同じ形)。先頭の名前はほかの組ごとのハッシュと入力を分けるためのもの。**θ の水準集合に依らないので S と R8 の組が一致する**
  3. **項目の並び**: タスク型(t3 → t1b)→ 併合したセル(セル表の順)→ 極性(gt → lt)→ θ(小さい順)→ 組(ハッシュの順)。batch の組み方はこの並びで決まる(近接同点は ADR-079 決定8 のとおり batch 4 のまま感度の行)
  4. manifest は評価プールと同じ `eval_pool.assemble` を通す(`pool_id: pilot`・`fill.method: threshold_sweep`・`fill.cells` に併合セルごとの元のセル名・候補数 80・選んだ 20 組・`fill.source_pool_pairs_hash` = パイロット用プールの `b1802456…`)
  5. **S の基本集合は T3・T1b の両方を持つ**。(d) は T1b だけなので、(d) の run は S の T1b 1,200 項目だけを使う(**絞り方は I4・I8 で決める**)
- **記録しておく事実**(組合せ論的な帰結。実験結果ではない):
  - 併合セルの 20 組の内訳は gt のセル由来 8〜14・lt のセル由来 6〜12(12 セル)。掃引は各組を両極性で尋ねるので、元のセルの極性は項目に効かない
  - **R8 の 8,160 項目のうち 7,200 は `p2` で判別できない**(判別できるのは gt の θ ∈ {0, +1}・lt の {+1, +2} の 2/17。240 組 × 2 極性 × 2 = 960)。**4 値分解の経路に入れれば `scoring.classify` が止まる**ので、I4 は別の記録の経路にする
  - **R8 の 240 項目は、パイロット用プールの固定オフセットの項目と同じ `item_id`**(選んだ組 1 つにつき、元のセルの極性 × そのセルで配られた固定オフセット の 1 項目)。ADR-030 決定5(固定オフセットは掃引の部分集合)の帰結で、B0 と R8 で同じ文面を 2 回解くことになる。**I4・I5 で両 run の一致の点検に使える**(案)
- テスト: `code/tests/test_sweep_pool.py`(新規。件数・併合・選び方の決定性と独立な数え直し・S ⊂ R8・T = t + θ・非判別項目を含むこと・コミット済み manifest の再現)/ `test_order6b_pilot.py`(掃引の欄を許す)。`pytest code/tests -q` → **1082 passed**(1049 → +33)

### 4.5 I4 の実装で決めたこと(★2026-09-12 その56。IMPLEMENTER。**実装の読み。何を測るか(腕・件数・記録する量)は変えていない。人間が覆せる**)

- **仕様の穴(HANDOFF その55 が挙げたもの)**: 本 PLAN は掃引の run の宣言の仕方を書いていない(§3.2 は記録する量、§9 の I4 は「`run.py` の別経路 / `metrics.json` の新しい欄」だけ)。
  **→ 読み1: 掃引の run は新しい config で宣言する。**`configs/exp_order6b_r8.yaml` = pilot の config の写しで、違うのは 4 欄だけ ——
  `experiment.id` / `eval.anchor_manifest`(→ `pilot_sweep_r8/manifest.json`)/ `eval.batteries`(`[comparison]`)/ **`eval.threshold_sweep_arm: r8`(新しい鍵)**。前例は R5 の `exp_phase1_main_t2cross.yaml`(本番との差 3 欄)
  - **経路は config の宣言で決め、manifest の中身から推測しない**(`eval.counterpart_manifest` の前例。§4.3)。宣言が無い(null)= 固定オフセットの run
  - **宣言と manifest の食い違いは両方向とも、重みを読む前・run ディレクトリを作る前に止める**: 宣言が無いのに anchor が掃引のプール(`fill.method == threshold_sweep`)/ 宣言があるのに掃引のプールでない /
    manifest の `fill` の腕・θ の水準・タスク型・極性・組の数・`selection.seed`・併合セルが config(`eval.threshold_sweep`・`eval.pool_seed`・`eval.cells`)と違う / 項目の(併合セル × 極性 × θ)が manifest の組とそろっていない
  - 入口は `python -m code.eval.run --config configs/exp_order6b_r8.yaml`(`--dry-run` も)。`main` が宣言を見て掃引の経路(`execute_threshold_sweep` / `threshold_sweep_dry_run`)に回す。**固定オフセットの経路(`execute` / `evaluate_pool` / `dry_run`)は宣言のある config を受け付けない**
  - 却下した案: manifest の `fill.method` から経路を決める(中身からの推測)/ CLI 引数 `--sweep-arm`(`runs/<id>/config.yaml` だけから run の種類が復元できなくなる)/
    別の入口 `code/eval/threshold_sweep.py`(桁数掃引 `code/eval/sweep.py` の前例はあるが、§9 が「`run.py` の別経路」と書き、HANDOFF の完了条件が `run.py --dry-run`)
- **読み2(記録)**: 掃引の項目は `classify`・`metrics_by_reference_rule`・`response_builder` を通さない。強制選択の forward(`collect_forced_choices`。**判定規則 `choose_from_logprobs` は無変更**)だけを掛け、
  `predictions/threshold_sweep.<タスク型>.jsonl` に 1 項目 1 行で書く: `item_id`・`category`・`task_type`・`polarity`・`sweep_cell`(併合セル)・`coverage`・`carry`・`operands`・`t`・`threshold`・`threshold_offset`(θ)・`prompt`・`response`(固定オフセットの経路と同じ 1 行の文字列)・`answer`(判定規則の答え。同点は No)・`truth`(`comparison_answer(t, 極性, T)`)・`yes_logp`・`no_logp`
  - `truth` と `answer` は記録であって分類ではない。**率(correct を含む)は出さない。**I5 の「遠いオフセットの correct」と揃え方 (a) の `y`(ADR-079 決定1)は、ここから後処理で作る
  - `metrics.json` は `kind: threshold_sweep`(4 値分解を読む `aggregate.py` は `battery_eval` 以外を数えずに飛ばし、`frame.py` は止まる)。中身は来歴(`pool`・`coverage`・`generation`・`adapter`・`timing`・`forced_choice.candidates`)と
    `threshold_sweep` の欄(腕・θ の水準・タスク型・極性・組の数・元のプールの `pairs_hash`・**件数(併合セル × 極性 × θ)**・predictions のファイルごとの行数)
  - 併合セルと既知性は、manifest の `fill.cells` の組と config の `eval.cells` から `sweep_pool.sweep_cells`(生成と同じ関数)で引き直す。名前を解析しない
- **読み3(上位 k)**: 欄をいま空けない(値の無い欄は「記録した結果が空だった」と読める)。I10 で `ForcedChoice` に足し、固定オフセットの経路(`prediction_record`)と掃引の経路(`threshold_sweep_record`)の両方に同じ形で書く
- **読み4(S と (d) の絞り方)**: 掃引の経路は腕を固定しない(`s` も同じ経路・同じ宣言の鍵)。文面(① の前置き I6・(d) のテンプレート I8)は `load_group_templates` と `RENDERERS` を通るので、固定オフセットの経路と同じ所で被さる。
  **(d) の run を S の T1b 1,200 項目に絞る仕方は I8 で決める** —— 固定オフセットの (d) の run もパイロット用プールの T1b 480 項目に絞る必要があり、両経路で同じ仕組みにするのが自然なため。**いまの掃引の経路は、manifest の `fill.task_types` のタスク型をすべて解く**
- **読み5(batch)**: forward はタスク型ごとに、項目の並び(§4.4 の読み3)のまま `eval.batch_size`(4)で掛ける。(併合セル × 極性 × θ)ごとに 20 組なので batch はその境界を跨がない(組合せ論的な帰結)。**B0 と R8 で同じ `item_id` の 240 項目は batch の相手が違う**(近接同点は ADR-079 決定8 のとおり感度の行)
- **読み6(アダプタ)**: 掃引の経路もアダプタを読める(`adapter_provenance` を共有)。Phase 1 の R8(ADR-030)は FT 後のモデルで Δ̂ を測るため。順6b は null
- **実装(★2026-09-14 その57。IMPLEMENTER。上の読み 1〜6 のとおり。CPU のみ・GPU 0)**:
  - `configs/exp_order6b_r8.yaml`(新規): pilot の config の写しで、違うのは 4 欄(`experiment.id` / `eval.anchor_manifest` / `eval.batteries: [comparison]` / `eval.threshold_sweep_arm: r8`)。**この config を `eval_pool` / `sweep_pool` に渡すと、セル表の群が `eval.batteries` に無いので止まる**(手元で確かめた。t2cross と同じ)。S の config はまだ作っていない(S の run は ① と (d) の文面で回す(§3.7)ので、config は I6・I8 で作るのが自然 = 読み。**掃引の経路は腕 `s` も同じ宣言の鍵で解ける**ことはテストで確かめた)
  - `code/eval/run.py`: 宣言(`declared_threshold_sweep_arm`)/ `read_pool_manifest` / `is_threshold_sweep_pool` / `refuse_declared_threshold_sweep` / `check_pool_kind`(両方向)/ `load_pool_items` を `_read_pool_items(threshold_sweep=...)` に分けた(順序は「items.jsonl が有るか → プールの種類 → 既存の 3 検査」)。
    固定オフセットの経路は `dry_run`・`load_pool_items`・`execute`(`prepare_run_dir` の前)で宣言を拒み、`execute` はプールの種類も run ディレクトリの前に見る。
    掃引の経路: `load_threshold_sweep_pool`(fill の腕・θ・タスク型・極性・組の数・`selection.seed` の照合 / 併合セルを `sweep_cells` で組み直して `fill.cells` と照合 / 項目ごとの群・組・θ・T = t + θ / **完全性**)/ `threshold_sweep_prompts` / `threshold_sweep_record` / `evaluate_threshold_sweep` / `threshold_sweep_payload` / `threshold_sweep_report_lines` / `execute_threshold_sweep` / `threshold_sweep_dry_run` / `main` の振り分け
  - **HANDOFF(その56)の設計から変えた所(どれも配線。何を測るかは変えていない)**:
    (i) 文面の組み立てを `threshold_sweep_prompts(config, pool)` に出し、`execute_threshold_sweep` が **run ディレクトリを作る前に**呼ぶ(テンプレートの欠けや `cot` の宣言で、重みを読んだ後に止まらないように)。そのため `evaluate_threshold_sweep` の引数は `(pool, *, prompts, scorer)` になった /
    (ii) `load_pool_items` も宣言を拒む(固定オフセットの経路の入口をすべて閉じる)/ (iii) `pool_record` は `read_pool_manifest` を使う(manifest が無いときの例外が `FileNotFoundError` から `ConfigError` に変わった)/
    (iv) 掃引の dry-run の定数の答えは、選んだ側の対数尤度を log 1 = 0、選ばなかった側を log 0 = −inf に置く(`dry_run_forced_choice_scorer`。dry-run は何も書かないので、この値はどこにも残らない)/
    (v) `metrics.json` の掃引の run は `elicitation`・`primary_reference_rule`・`by_batch` を持たない(参照規則を使わないため)。`metrics_payload` から `forced_choice_block`、`report_lines` から `run_header_lines`・`forced_choice_lines` を出して共有した
  - 手元で確かめたこと: `python -m code.eval.run --config configs/exp_order6b_r8.yaml --dry-run` が通る(8,160 項目 = 12 併合セル × 2 極性 × 17 θ × 20 組。組合せ論的な件数)/ R8 の config で preflight の data_checks 7 件 PASS / pilot の config(B0)の `--dry-run` は固定オフセットの経路で今までどおり 1,640 項目
  - テスト `code/tests/test_threshold_sweep_run.py`(新規 24)。**変異を 3 つ注入して、それぞれ狙ったテストだけが落ちることを確かめた**(固定オフセットの経路の向きの検査を外す / 完全性の検査を外す / 同点を Yes に倒す)。`pytest code/tests -q` → **1106 passed**(1082 → +24)

### 4.6 I5 の実装で決めたこと(★2026-09-14 その58。IMPLEMENTER。**「階段の位置」の定義は ADR-081(人間が確定)。下の読み 1〜6 は実装の読みで、人間が覆せる**)

- **入口**: `python -m code.analysis.r8_fit --runs "runs/*exp_order6b_r8*" [--ident-run <run>] [--out-dir <dir>]`(`gonogo.py` と同じ形。`--out-dir` で `r8_fit.json`)。**値を出すだけで合否を付けない**(判定表は I11)
- **読み1(入力と単位)**: I4 の記録の経路が書いた run(`metrics.json` の `kind: threshold_sweep`)だけを読む。当てはめの単位は(タスク型 × 既知性)で、鍵は predictions の `task_type`・`coverage` の欄(`sweep_cell` の名前を解析しない)。`carry` の 2 セルと各 20 組は合わせる(ADR-030 決定6)。
  混ぜた当てはめと極性ごとの 2 つに §3.2.1.1 の同じ定義を当てる。**記録が `metrics.json` と食い違えば止める** —— predictions の行数 / 欄の欠け / 極性・タスク型・θ が宣言の外 / 閾値が `T = t + θ` でない / `truth` が `comparison_answer` と違う / `answer` が真偽値でない / `item_id` の重複 / (併合セル × 極性 × θ)の件数が `n_items_by_cell` と違う
- **読み2(遠いオフセットの境界)**: §5 (iv) の「θ ≤ −2 の側と θ ≥ +3 の側」を、**run の `config.yaml` の `eval.threshold_sweep.offsets.s`(S の 5 水準)から導く**(θ < 0 の最大 = −2、θ > 0 の最小 = +3)。§3.7 が S の 5 水準を「遠いオフセット」として置いたこと、C1・C2 の (iv) は S で、C0・C3 の (iv) は R8 で同じ境界で読む必要があることが理由。**新しい数を置かず、config も書き換えない**。
  S の水準に θ = 0 があるか片側に水準が無ければ止める / 側に項目が 0 件でも止める(境界と run の θ が合っていない)。閾値の近く(R8 の θ = −1〜+2)は数えない。
  却下: モジュールの定数に −2・+3 を置く(マジックナンバー)/ config に新しい鍵を足す(pilot・R8 の config の対を同時に直すことになる。**明示の鍵が良ければ I11 で足す**)
  - 出すのはセルごと(**判定の単位。ADR-081 決定3**)とタスク型でまとめた値(記述)
- **読み3(`Δ̂`)**: `delta_hat_table(report, ident_report)` = セルごとの `θ*(条件) − θ*(ident)`(混ぜた当てはめ)。CLI は `--ident-run` を渡したときだけ出す。**順6b は素のモデル 1 本なので出さない**。
  基準の run の `lesion_condition` が `ident` でなければ止める / 腕・θ の水準・タスク型・セルが違えば止める / どちらかのセルが除外なら None(分類を添える)。**どの run とどの ident の run を組むか(シードの対応。ADR-030 決定6 の「シードを反復単位」)はここで決めない**(Phase 1 の集計で決める)
  - **注意(記録)**: `metrics.json` の `lesion_condition` は config の `lesion.condition` の値そのもので、adapter = null の run でも p2 と出る(pilot・R8 の config は `condition: p2`)。**表の見出しには adapter を必ず並べる**ようにした
- **読み4(数値計算)**: 当てはめは Newton 法(対数尤度が下がる歩は半分にする)を numpy で書いた。**statsmodels は手元に無い**(lock には 0.15.0 がある)ので使わない。反復の上限・収束の幅・半分にする回数はモジュールの定数(**実験条件ではない**。`code.rates.TOTAL_TOLERANCE` と同じ扱い)。
  分離も片側だけも無いデータでは最尤推定が存在して一意なので、定数は収束の判定にしか効かない。独立な検算: 2 水準の飽和模型の閉じた形 / 17 水準でスコア方程式が 0
- **読み5(`y` と近接同点)**: `y` は `answer`(判定規則の答え。同点は No)から作る(ADR-079 決定1)。**近接同点(|yes_logp − no_logp| ≤ 0.25)は掃引では特別に扱わない**(ADR-079 決定8 の感度の行は固定オフセットの #2 について。掃引に要るかは I11 で決める)
- **読み6(除外件数の出し方)**: 混ぜた / gt / lt ごとに分類の件数(セルの数)と、`β1 ≤ 0` の合計(= 逆向きの階段 + 当てはめで `β1 ≤ 0`)・除外の合計。**階段は除外に数えない**(ADR-079 決定1)
- **実装(★2026-09-14 その58。CPU のみ・GPU 0)**: `code/analysis/r8_fit.py`(新規)/ `code/tests/test_r8_fit.py`(新規 38)。
  テストは §3.2.1 の算術の例(Δ = 0・2・11 で gt `Δ − 0.5`・lt `Δ + 0.5`・混ぜて `Δ`・開き 1)/ `Δ̂ = 2` / 旧い揃え方では `Δ̂ ≈ 0` で両方 `β1 ≤ 0` の除外 / 分類の 8 通りと S の水準の階段・重なり 1 件は階段でない・非収束 / ★F138 の定数戦略が低い側で 0・片側だけ(すべて 1)として除外 /
  **I4 の経路で本当に書いた run**(内部の値 `t + 2`・`t` の決定的な採点器を `execute_threshold_sweep` に通した 8,160 項目 × 2)を読むこと / 記録の改ざん 6 通りと固定オフセットの run で止まること。
  **変異を 6 つ注入し(gt の `y` を Yes にする / 階段の位置を U にする / 階段の枝を外す / 件数の照合を外す / 低い側を `<` にする / `β1 ≤ 0` の除外を外す)、それぞれ狙ったテストが落ちることを確かめた**(scratchpad のスクリプト。repo には置いていない)。`pytest code/tests -q` → **1144 passed**(1106 → +38)

### 4.7 I6・I7 の実装で決めたこと(★2026-09-15 その59。IMPLEMENTER。**前置きの文面・置き場所・並びの決め方は ADR-079 決定3。下の読み 1〜7 は実装の読みで、人間が覆せる**)

- **仕様の穴(その59 に人間に聞いた)**: 固定オフセットの ① の run(①-bin 960 + ①-num 480)はパイロット用プール 1,640 項目のうち 3 群(比較・T1・T2)だけを解くが、`run.py` の `_read_pool_items` は `eval.batteries` の外の群(指示付き T1 80・特異性 120)の項目があると止める(黙って項目数が減るのを防ぐ門)。
  **→ 人間の回答: 「I8 で (d) と一緒に決める」**(他の選択肢: 今回、群単位の絞りを足す / ① は 5 群すべてに置く)。(d) も T1b だけに絞る必要があり(固定オフセット 480・S 1,200。§4.5 読み4)、絞り方を (d) の粒度(比較群の中のタスク型)で 1 つ作るため。**固定オフセットの ① の config は I8 で作る**
- **読み1(鍵と値)**: `eval.preamble` = 前置きの行のリスト(ADR-079 決定3 の 4 行を、その順で)。**無い / null = 前置きなし**。行は空でない文字列で、改行を含まず、重複しない(破れば重みを読む前に止める)。
  **文面は config に置く**(テンプレート集合のファイルに置かない。run の `config.yaml` の写しだけで刺激が復元できるように)。前置きを持つ config は複数になるので(読み5)、行が ADR-079 決定3 と 1 文字も違わないことはテストで固定する。
  `eval.few_shot_k` の門(`code/eval/model.py` の `reject_unimplemented_settings`)は使い回さない(§9 の I6)。few-shot の本数(承認待ち #20)とは別の宣言である
- **読み2(連結)**: 項目の文面 = 並べた前置きの行を改行でつなぎ、**空行を 1 つ挟んで**(`\n\n`)各群の文面(`load_group_templates` + `RENDERERS` の出力)を続ける。chat template はその外側で今までどおり掛かる(`code/chat_format.py` の `model_input`。前置きは user 発話の中に入る)。
  **被せる場所は `run.render_prompts` の 1 か所**で、固定オフセットの経路の 2 か所(`dry_run`・`evaluate_pool`)と掃引の経路(`threshold_sweep_prompts`)がすべてここを通る(§4.5 読み4)。
  **前置きが無ければ `RENDERERS` の出力をそのまま返す**(1 バイトも変えない。パイロット用プール 1,640 項目・R8 8,160・S 2,400 の文面の sha256 を実装の前に取り、テストに固定した)
- **読み3(並び)**: 項目ごとに `sha256(canonical_json(["preamble_order", item_id]))` を整数にして `n!`(4 行なら 24)で割った余り `k` を取り、行の位置の並びの辞書順で `k` 番目を使う。**乱数を使わず、条件・シード・群・経路に依らない**(同じ `item_id` なら固定オフセットの項目と掃引の項目で同じ並びになる。R8 の 240 項目は固定オフセットの項目と同じ `item_id` = ADR-030 決定5)。
  タグ `preamble_order` は、他のハッシュ(`sweep_pool` の組の選び方・T2 の場面)と入力を分けるための定数。`k` 番目の並びを返す関数は `item_id` に依らずに呼べる((c) の較正 = I9 が 24 通りを並べるときに使える)
- **読み4(記録)**: `metrics.json` に `preamble` の欄を**すべての run で**置く —— 前置きが無ければ `null`、あれば行・sha256(設定の順の行を改行でつないだ文字列の sha256)・並びの数・並びの決め方・連結の仕方・「前置きのある run の T1 は評価アンカーでない」の注記。
  固定オフセットの経路・掃引の経路・dry-run の報告が同じ関数で書く。`log.txt` の先頭にも 1 行(前置きなし / あり + sha256 の先頭)。項目ごとの並びは `predictions/` の `prompt` から復元できるので、別の欄は置かない。
  **前置きの無い run の `metrics.json` には `"preamble": null` が 1 行増える**(モデルに入る文面は変わらない)
- **読み5(config)**: **S の ① の run は 1 本の config にする** —— `configs/exp_order6b_s_preamble.yaml` = R8 の config の写しで、違うのは 4 欄(`experiment.id` / `eval.anchor_manifest`(→ `pilot_sweep_s/manifest.json`)/ `eval.threshold_sweep_arm: s` / `eval.preamble`)。S のプール 2,400 項目(T3・T1b)をすべて解くので絞りは要らない。
  **S の (d) の run(T1b 1,200)は別の config になる**(1 つの run は 1 つの文面の組しか持たない)ので、**§10・§11 の「run 数 6(B0 / R8 / ① / (d) / (c) / S)」は 7 になる**(S が S-① と S-(d) に分かれる。項目・回は 15,626 のまま。重みの読み込みが 1 回増える = 見積りで約 127 秒。R1 の読み込み 126.857 秒 [run:20260911_141547_order6_r1])。§11 の文面は承認を求めるときに直す。
  **固定オフセットの ① の run は 1 本**(比較・T1・T2 = 960 + 480。§11 の「①(960 + 480)」)**で、config は I8 で作る**(上の仕様の穴)
- **読み6(preflight 検査6。I7)**: config が `eval.preamble` を宣言していれば、検査6(`format hash`)は**評価アンカーとの比較を行わずに SKIP を返し**、詳細に「この run は前置き(sha256 の先頭)を宣言しており、前置きのある T1 は評価アンカーでない(PLAN-026 I7・§8 の注記 4)」と書く。
  **訓練側の書式の検査(条件間の一致・`format_hash` の再計算)はそのまま行い、破れていれば FAIL**。SKIP にしたのは `Status` の定義(「この実行には対象が存在しない」)に合わせたため —— PASS にすると「アンカーと一致した」と読める。**前置きの無い run(B0・R8・本番)の検査6 は何も変わらない**。
  却下: PASS に注記を付ける(SKIP と PASS を混ぜない)/ WARN(人間の判断に任せる項目ではない。宣言で決まる)/ 検査を 8 件にする(data_checks の 7 件を固定したテストと報告の形が変わる)
- **読み7(他の入口)**: 桁数掃引(`code/eval/sweep.py`)は `eval.preamble` を宣言した config を受け付けない(前置きを実装していないので、黙って前置き無しで回ると config と刺激が食い違う)。
  **`aggregate.py`・`frame.py` は前置きの有無を見ない** —— ① の run(`kind: battery_eval`)を B0 と同じ glob で集めると混ざる。順6b の集計は I11 で扱う(パイロット用プールの run が主解析に混ざる危険も同じ。PLAN-001 §4.6 規則4)
- **実装(★2026-09-15 その59。上の読み 1〜7 のとおり。CPU のみ・GPU 0)**: `code/eval/preamble.py`(新規。宣言の読み・並び・連結・記録)/ `code/eval/run.py`(`render_prompts` を 3 か所で使う・`metrics.json` と dry-run の報告の `preamble` 欄・`log.txt` の 1 行・`execute` は run ディレクトリの前に宣言を読む)/
  `code/eval/sweep.py`(`reject_declared_preamble`)/ `infra/preflight.py`(`_train_format_problems` に分け、`check_format_hash_without_anchor`・`format_hash_result` を足した)/ `configs/exp_order6b_s_preamble.yaml`(新規)/ `code/tests/test_preamble.py`(新規 40)。
  手元で確かめたこと: `python -m code.eval.run --config configs/exp_order6b_s_preamble.yaml --dry-run` が通る(2,400 項目。前置きの行が出る)/ preflight の data_checks は S-① で 6 PASS + 検査6 SKIP、R8・pilot は 7 PASS のまま。
  **変異を 10 個注入し(前置きを無視 / 空行なし / タグなし / 並びの固定 / 比較群だけ / metrics に書かない / 宣言の検査を run ディレクトリの後へ / preflight がアンカーと比べる / 訓練側を見ない / 桁数掃引が拒まない)、それぞれ `test_preamble.py` が落ちることを確かめた**(scratchpad のスクリプト。終わった後にファイルが元と一致することを確かめた)。`pytest code/tests -q` → **1184 passed**(1144 → +40)

### 4.8 I8 の実装で決めたこと(★2026-09-16 その60。IMPLEMENTER。**絞りの宣言の形は ADR-082(人間が選択式で採択)。下の読み 1〜8 は実装の読みで、人間が覆せる**)

- **仕様の穴(§4.7 の穴 = その59 に人間が「I8 で (d) と一緒に決める」と答えたもの)**: ① の run はパイロット用プール 1,640 のうち 3 群(比較・T1・T2 = 1,440)、(d) の run は比較群の T1b だけ(固定 480 / S 1,200)を解くが、
  `run.py` の `_read_pool_items` は `eval.batteries` の外の群があると止め、掃引の経路は manifest の `fill.task_types` をすべて解く。
  **→ ADR-082(提案 エージェント / 採択 人間。選択式。他の選択肢: 外す部分を宣言する `eval.pool_exclusions` / 絞ったプールを別に書き出す)。鍵は `eval.task_subset` = 解くタスク型のリスト。**
- **読み1(鍵と値)**: `eval.task_subset` = タスク型名のリスト(`t1` / `t1_instructed` / `t2` / `t3` / `t1b`。**ADR-026 の水準名そのもの**で、名前の表は作らず `numeric_sum.CATEGORY_AXES`・`t3_comparison.CATEGORY_AXES` から引く。`frame.task_type_of` と同じ作法)。
  **無い / null = 絞りなし**(今の門のまま。B0・R8・S-① は 1 バイトも変わらない)。壊れた宣言(リストでない・空・文字列でない要素・重複・未知の名前)は**重みを読む前**に止める
- **読み2(噛み合わせの検査。どれも重みを読む前)**: 宣言した型の群が `eval.batteries` に無い / `eval.batteries` の群に宣言した型が 1 つも無い(その群を解くと書いて 1 件も解かない)/ 宣言した型の項目がプールに 1 件も無い、で止める。
  **特異性対照はタスク型を持たない**(`frame.OFF_MAIN_AXIS`)ので、`task_subset` を宣言した config の `eval.batteries` に `specificity` を置けば止める(絞りは `eval.batteries` から外して行う)
- **読み3(どこで絞るか)**: `_read_pool_items` は**読むだけ**にし(ファイルの有無・プールの種類・空・`item_id` の重複・`pool_id`)、**群の門と絞りを `solved_pool_items`(新)1 か所に集めた**。固定オフセットの経路(`load_pool_items`)と掃引の経路(`load_threshold_sweep_pool`)が同じ関数を通る。
  **掃引は完全性((併合セル × 極性 × θ)がプールの組とそろっているか)をプール全体で確かめてから絞る** —— プールのファイルは S-① が全部解くものと同一で、`items_sha256` もファイル全体の畳み値だからである
- **読み4(記録)**: `metrics.json` に `task_subset` の欄を**すべての run で**置く(宣言が無ければ `null`。前置きと同じ形。§4.7 読み4)。中身は宣言した型・プールの件数・解いた件数・外した件数・**(群 × タスク型)ごとの外した件数の一覧**(タスク型を持たない群は `task_type: null`)・注記。
  固定オフセットの経路・掃引の経路・dry-run の報告が同じ関数で書き、`log.txt` の先頭にも 1 行(7 → 8 行)。**`pool.n_items` は解いた件数のまま**(`total_items` の 1 か所で数える)、**`pool.items_sha256` はプールのファイル全体**(絞りで変わらない)
- **読み5(掃引の run の `threshold_sweep.task_types`)**: **解いたタスク型**にする(S-(d) なら `[t1b]`)。`code/analysis/r8_fit.py`(I5)は `metrics.json` の `task_types` で predictions のファイルを決めるので、これで S-(d) の run を**手を入れずに**読める。プール側のタスク型は manifest と `task_subset` 欄に残る
- **読み6((d) のテンプレート集合)**: `configs/templates/order6b_d.yaml`(新規)。`comparison` 群に **`t1b_gt` / `t1b_lt` の 2 つだけ**を置く(T3 を置かない = 絞りを書き忘れた run は文面を組む所で必ず落ちる。黙って B0 と同じ T3 を解かない)。
  文面は**本番の `t1b.yaml` の文面に、`t3.yaml` の末尾の一文を半角空白 1 つで足したもの**(テストが本番の 2 ファイルから組み直して照合する)。**本番の `t1b.yaml`・`t3.yaml`・`eval_main.yaml` は触らない**(ADR-078 決定2)
- **読み7(config 3 本。どれも写しで、差は宣言した欄だけ。テストが縛る)**:
  - `configs/exp_order6b_preamble.yaml`(固定オフセットの ①。1,440 = 960 + 240 + 240): pilot の config の写しで**差は 4 欄**(`experiment.id` / `eval.batteries`(3 群)/ `eval.task_subset`(`[t3, t1b, t1, t2]`)/ `eval.preamble`(ADR-079 決定3 の 4 行))
  - `configs/exp_order6b_d.yaml`(固定オフセットの (d)。480): pilot の config の写しで**差は 4 欄**(`experiment.id` / `data.eval_template_set`(`order6b_d`)/ `eval.batteries`(`[comparison]`)/ `eval.task_subset`(`[t1b]`))
  - `configs/exp_order6b_s_d.yaml`(S-(d)。1,200): R8 の config の写しで**差は 5 欄**(`experiment.id` / `data.eval_template_set` / `eval.anchor_manifest`(S の掃引プール)/ `eval.task_subset` / `eval.threshold_sweep_arm: s`)
  - **① の config は前置きを持つので、preflight の検査6 は SKIP になる**(§4.7 読み6)。(d) の 2 本は前置きを持たないので検査6 はそのまま
- **読み8(他の入口)**: 桁数掃引(`code/eval/sweep.py`)は `eval.task_subset` を宣言した config を受け付けない(評価プールを読まないので、宣言が黙って効かない。前置きと同じ扱い)。
  **`eval.dry_run_items`(明示リスト。smoke 系)と同時に宣言しても止める** —— 明示リストの項目は絞りを通らないので、宣言と解く項目が黙って食い違う。`aggregate.py`・`frame.py` は絞りを見ない(I11)
- **実装(★2026-09-16 その60。上の読み 1〜8 のとおり。CPU のみ・GPU 0)**: `code/eval/task_subset.py`(新規。宣言の読み・名前・噛み合わせ・選び方・記録)/ `code/eval/run.py`(`_read_pool_items` は読むだけに・`solved_pool_items`・`pool_subset_record`・`dry_run_subset_record`・`metrics.json` と dry-run の報告の `task_subset` 欄・`log.txt` の 1 行(7 → 8 行)・
  `ThresholdSweepPool` に `task_types` と `subset`)/ `code/eval/sweep.py`(`reject_declared_task_subset`)/ `configs/templates/order6b_d.yaml`(新規)/ `configs/exp_order6b_preamble.yaml`・`exp_order6b_d.yaml`・`exp_order6b_s_d.yaml`(新規)/ `code/tests/test_task_subset.py`(新規 40)。
  手元で確かめたこと: `--dry-run` が **① 1,440 / (d) 480 / S-(d) 1,200** で通る(組合せ論的な件数)/ preflight の data_checks は ① で 6 PASS + 検査6 SKIP、(d)・S-(d) で 7 PASS / B0 1,640・R8 8,160・S-① 2,400 の文面は `test_preamble.py` の sha256 のまま(1 バイトも変わらない)。
  **変異を 11 個注入し(絞りを効かせない / 宣言の無い run の門を外す / 完全性を絞った後に見る / metrics の task_types をプール側にする / `task_subset` 欄を書かない / 掃引の forward をプール側のタスク型で回す / 宣言した型の不在を見ない / 明示リストとの同時宣言を許す / 桁数掃引が拒まない / (d) の集合に T3 を足す / 特異性対照の門を外す)、それぞれ `test_task_subset.py` が落ちることを確かめた**(scratchpad のスクリプト。終わった後にファイルが元と一致することを確かめた)。`pytest code/tests -q` → **1224 passed**(1184 → +40)

### 4.9 I9 の実装で決めたこと(★2026-09-16 その61。IMPLEMENTER。**綴りの確認と 2 つの決定は ADR-083(人間が選択式で採択)。下の読み 1〜7 は実装の読みで、人間が覆せる**)

- **原典の確認(ADR-079 決定7 の条件)**: §3.5 の追記のとおり。綴りは一致したので実装した。**食い違いは無かった**
- **読み1(入口)**: **別の CLI** `python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml [--dry-run | --run-dir <dir>]`。
  (c) は評価プールを読まない(項目が無い)ので、プールの検査を持つ `code.eval.run` の経路には入れない(桁数掃引の `code.eval.sweep` と同じ扱い)。
  **`code.eval.run`(固定オフセット・掃引の両経路)と桁数掃引は `eval.calibration` を宣言した config を重みを読む前に止め、正しい入口を名指しする**(黙って B0 をもう 1 度解かない)。
  宣言の読み・入力・記録・後処理は `code/eval/calibration.py`(`run.py` を import しない)、重みと成果物は `code/eval/calibration_run.py`(`run.py` の来歴の関数を使う)に分けた —— `run.py` が宣言を拒むために前者を import しても循環しない
- **読み2(宣言と config)**: `eval.calibration = {symbols, arms}`。`symbols` = 記号のリスト(config の順)、`arms` = `{name, template_set, preamble}` のリスト。
  `configs/exp_order6b_c.yaml` は **pilot の config の写しで差は 4 欄**(`experiment.id` / `eval.batteries` = `[comparison]` / `eval.preamble`(① の config と同じ 4 行)/ `eval.calibration`)。
  腕は **`b0`(`eval_main`・前置きなし)/ `d`(`order6b_d`・なし)/ `preamble`(`eval_main`・あり)**。各腕の文面の組が較正する run の config(pilot・`exp_order6b_d.yaml`・`exp_order6b_preamble.yaml`)の
  `data.eval_template_set` と `eval.preamble` に一致することをテストが縛る。**R8・S-①・S-(d) は θ が違うだけで文面の組は同じなので、同じ腕の定数を使う**(§3.7「(c) には要らない」)
- **読み3(入力)**: 腕(config の順)→ category(`t3_comparison.CATEGORY_AXES` の順のうち、テンプレート集合の `comparison` 群にあるもの)→ 並び(前置きのある腕は `nth_order` の 0〜23、無い腕は 1 つ)→ 記号(config の順)。
  文面 = テンプレートの `str.format(a=s, b=s, threshold=s)`(literal。ADR-083 決定1)。前置きは `preamble.py` と**同じ連結**で置く(`with_preamble_order` を足し、`with_preamble` はそれを呼ぶだけにした = 連結は 1 か所。前置きの無い run の文面は変わらない)。
  **件数 = 4×3(b0)+ 2×3(d)+ 4×24×3(preamble)= 306**(§3.5 の上限と一致)。同じ文面が 2 度出たら止める
- **読み4(止める宣言。どれも重みを読む前・run ディレクトリを作る前)**: `symbols` が空・重複・文字列でない / `arms` が空・名前の重複・鍵の過不足・`preamble` が bool でない / 前置きの腕があるのに `eval.preamble` が無い / `eval.preamble` を宣言したのに使う腕が無い /
  `eval.batteries` が `[comparison]` でない / `eval.task_subset`・`eval.threshold_sweep_arm` を同時に宣言 / テンプレート集合に `comparison` 群が無い・空・`CATEGORY_AXES` に無い category がある
- **読み5(記録)**: `runs/<id>/calibration.json` = `{run_id, symbols, n_rows, rows}`。1 行 = `arm`・`template_set`・`category`・`task_type`・`polarity`・`symbol`・`preamble_order`(前置きの無い腕は null)・`prompt`・`yes_logp`・`no_logp`。
  **率も答え(answer)も補正後の値も置かない**(真値が無い。補正は後処理)。**`predictions/` には何も書かない**(`Item` / `classify` / 4 値分解を通らない。空のディレクトリは `prepare_run_dir` が作る)。
  `metrics.json` は **`kind: calibration`**(`aggregate.py` は飛ばし、`frame.py` は止まる)で、来歴(`generation`・`adapter`・`preamble`・`timing`・`forced_choice` の候補綴り)+ `calibration` 欄(記号・原典・腕ごとの category / 並びの数 / 行数・合計行数・後処理の定義の注記)。
  **`preamble` 欄は ① の run と `lines`・`sha256`・`n_orders` を同じにし、`order`・`note` だけを較正の中身に差し替える**(① の欄のまま書くと「item_id のハッシュで並びを選んだ」と読め、この run では偽の記録になる)。
  `log.txt` は来歴の行 + 前置きの 1 行 + 壁時計 + 候補綴り + 腕ごとの行数 + 注記(`run.py` の `run_header_lines` の先頭 5 行を `provenance_lines` に切り出して共有。`run_header_lines` の出力は変えない)
- **読み6(後処理。GPU 0。ADR-083 決定2)**: `content_free_bias(rows)` = (腕 × category × 並び)ごとに `b = logmeanexp_s(yes_logp_s) − logmeanexp_s(no_logp_s)`。
  `calibrated_answer(yes_logp, no_logp, bias)` = `(yes_logp − no_logp) − b > 0`(同点は No)。**config の記号がそろっていない鍵・同じ記号が 2 度ある鍵は止める**。
  **判定表(§5)・R8 の項目への適用(★F138 の確認)・① の項目との突き合わせは I11**(ここでは関数と単体テストだけ)
- **読み7(① の並び)**: ① の run の項目は `order_index(item_id, 4)` 番目の並びで尋ねられる(§4.7)。**較正の定数も並びごとに持ち、I11 は項目ごとにその並びの `b` を引く**(§3.5 の「24 通りすべて」の趣旨)。並びをまたいで平均した `b` は作らない
- **実装(★2026-09-16 その61。上の読み 1〜7 のとおり。CPU のみ・GPU 0)**: `code/eval/calibration.py`(新規。宣言・入力・記録・後処理)/ `code/eval/calibration_run.py`(新規。別の CLI)/ `code/eval/preamble.py`(`with_preamble_order`。`with_preamble` はそれを呼ぶだけ)/ `code/eval/run.py`(`refuse_declared_calibration` を固定オフセットの `dry_run`・`load_pool_items`・`execute` と掃引の `load_threshold_sweep_pool` に・`provenance_lines`)/ `code/eval/sweep.py`(`reject_declared_calibration`)/ `configs/exp_order6b_c.yaml`(新規)/ `code/tests/test_calibration.py`(新規 65)/ `code/tests/test_preamble.py`(`PREAMBLE_CONFIGS` に (c) の config)。
  手元で確かめたこと: `python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml --dry-run` が **306 件(b0 12 / d 6 / preamble 288)**で通る(組合せ論的な件数)。空文字の入力は `+>?`・`Is the sum of  and  greater than ? Answer Yes or No.`。
  **変異を 16 個注入し(空白を詰める / 偏りを対数確率の平均にする / 同点を Yes にする / 並びを 0 だけにする / 固定オフセットの dry_run・掃引のプール・桁数掃引が較正を拒まない / 使われない前置きを通す / 群の宣言を見ない / 行に答えを足す / 前置きの記録を ① のまま書く / 絞りとの同時宣言を許す / 偏りで記号の重複を見ない / kind を評価 run にする / 連結を ① と別に書く / 記号の重複を許す)、それぞれ `test_calibration.py` が落ちることを確かめた**(最初は 2 個がすり抜けた —— 記号の重複のテストが記号の欠けで先に止まっていた / 明示リストの dry-run を試していなかった。テストを直した。scratchpad のスクリプト。終わった後にファイルが元と一致することを確かめた)。`pytest code/tests -q` → **1289 passed**(1224 → +65)

### 4.10 I10 の実装で決めたこと(★2026-09-16 その62。IMPLEMENTER。**k の置き場所・綴りの形・固定オフセットの行の欄は ADR-084(人間が選択式で採択。3 点とも推奨)。下の読み 1〜8 は実装の読みで、人間が覆せる**)

- **人間の選択(ADR-084)**: 決定1 **k は順6b の config 7 本にだけ置く**(本番・smoke の config は触らない。鍵の無い run は上位 k を記録しない)/
  決定2 **綴りは `tokenizer.decode([id])` の文字列だけ**(id と logp は並べて残す)/
  決定3 **固定オフセットの run の二値群の行に、上位 k に加えて `yes_logp` / `no_logp` の値そのものも足す**(今は応答文字列に小数 4 桁でしか残っていない)
- **読み1(経路)**: **固定オフセット・掃引・(c) の較正の 3 経路すべてに載せる** —— ADR-079 決定7 が「強制選択のすべての forward」とし、§3.5 の (c) の記録欄が上位 k を挙げている。
  固定オフセットの `--dry-run` は採点器を通らない(定数の答えを `to_response` に直に渡す。I10 の前から)ので、上位 k の組み立てを dry-run で通すのは掃引と較正の経路だけである
- **読み2(宣言)**: config の `eval.forced_choice_top_k`(1 以上の整数。無い / null = 記録しない)。**名前に `forced_choice_` を付けるのは、config の注記にあるサンプリングの `top_k`(貪欲では設定しない)と取り違えないため**。
  値 `20` を pilot と写し 6 本(`r8`・`s_preamble`・`preamble`・`d`・`s_d`・`c`)に置く —— 写しどうしの「差 N 欄」は変わらない。pilot と本番の「違ってよい欄」には、掃引の欄と同じく **pilot にだけある欄**として足す(本番 config には無いことをテストが縛る)。
  bool・0 以下・整数でない値は**重みを読む前・run ディレクトリを作る前**に止める
- **読み3(取り方)**: `_score_batch` の既存の log-softmax 行(`float32`)に `topk(k)`(降順)を掛けて `.tolist()` で Python の値にする。
  **判定は既存の `choose_from_logprobs(row, candidate_ids)` を同じ行に同じ形で呼び、その結果に上位 k を後から付け足すだけ**(`dataclasses.replace`)—— `answer`・`yes_logprob`・`no_logprob` の計算経路は 1 文字も変えない。
  torch の要らない組み立て(行ごとの判定 + 上位 k の付け足し)を `_score_batch` から関数に切り出し、手元のテストは numpy の行でそこを通す(torch と重みは手元に無い)
- **読み4(復号)**: `tokenizer.decode([id])`(決定2)。採点器ごとに id → 文字列の写像をキャッシュする(k × forward の回数だけ復号しない)。1 バイトの断片は置換文字に潰れうるが、id が並ぶので区別できる
- **読み5(型)**: `ForcedChoice` に `top_tokens: tuple[TopToken, ...] | None = None` を足す(**既定値があるので、既存の差し替え採点器の構築はそのまま通る**)。`TopToken = (token_id, text, logprob)`。
  上位 k の確率の合計は記録を組むときに `Σ exp(logprob)` で出す(型に持たせない)
- **読み6(検査)**: `collect_forced_choices(prompts, scorer, *, top_k)` が本数の検査と同じ 1 か所で「**宣言あり ⇒ すべての結果がちょうど k 個の上位を持つ / 宣言なし ⇒ どれも持たない**」を確かめる。
  宣言したのに重みの経路で k を渡し忘れる配線の誤りを、黙って null の記録にしない(`CLAUDE.md` §7)。
  そのため**順6b の config を差し替え採点器で回すテスト**(`test_threshold_sweep_run.py`・`test_preamble.py`・`test_task_subset.py`・`test_calibration.py`・`test_r8_fit.py`)は、採点器が上位 k を返すように直す。
  dry-run の定数採点器は宣言された k 個の置き物を返す(**実験の値ではない**。dry-run は何も書かない)
- **読み7(記録)**: 行の欄 `top_k` = `[{"id", "text", "logp"}, ...]`(logp の降順。k 個)/ `top_k_mass` = 上位 k の確率の合計。**宣言が無ければ両方 null**(欄は置く。「無かった」と「この記録が入る前の run」を区別する。§4.7 読み4 と同じ理由)。
  - 掃引の行(`threshold_sweep_record`)・較正の行(`calibration_row`)に 2 欄を足す
  - 固定オフセットの行(`prediction_record`)は **二値群(comparison)の行にだけ** `yes_logp` / `no_logp`(決定3)と 2 欄を足す。**数値群の行と、二値群の応答文字列(`Yes [forced_choice yes_logp=… no_logp=…]`)は変えない**。
    `yes_logp` / `no_logp` は宣言の有無によらず入る(採点器が既に返している値の記録。本番 config は触らない)
  - `metrics.json` の `forced_choice` 欄(重みを読んだ run にだけある)に `top_k`(宣言の値。無ければ null)。dry-run の報告(3 経路)にも宣言の値を置き、`log.txt` の候補綴りの行に k を添える
- **読み8(変えないもの。テストが固定する)**: 判定規則・`answer`・`yes_logp`・`no_logp`(**同じ行から上位 k を付けても付けなくても、ビット単位で同じ**)/ 応答文字列 / 4 値分解・常答戦略の基準線 / 文面・前置き / 較正の後処理。
  **§3.6 の用途(★F139 の質量の行き先の記述)と、それを判定表に使わないこと(ADR-079 決定5)は変えない**。集計(質量の行き先の表)は I11 以降
- **実装(★2026-09-16 その62。上の読み 1〜8 のとおり。CPU のみ・GPU 0)**: `code/eval/forced_choice.py`(`TOP_K_KEY`・`TopToken`・`ForcedChoice.top_tokens`・`declared_top_k`・`token_text_decoder`・`top_tokens_from`・`choices_from_rows`・`check_top_tokens`・`top_k_record`・`collect_forced_choices(..., top_k=)`・`scorer_from_model` / `build_forced_choice_scorer` / `_score_batch` の `top_k`)/
  `code/eval/engine.py`(`build_engines(..., top_k=)`。既定値なし)/ `code/eval/run.py`(`prediction_record(..., forced_choice=)` と群の検査・`evaluate_batch` / `evaluate_pool`・`threshold_sweep_record`・`evaluate_threshold_sweep`・`execute` / `execute_threshold_sweep` が宣言を run ディレクトリの前に読む・`forced_choice_block(..., top_k=)`・`forced_choice_lines`・`DRY_RUN_TOP_TOKEN`・`dry_run_forced_choice_scorer(..., top_k=)`・`top_k_line`・dry-run の報告)/
  `code/eval/calibration.py`(`calibration_row`)/ `code/eval/calibration_run.py`(`CalibrationPlan.top_k`・採点・本実行・dry-run)/ 順6b の config 7 本 / `code/tests/test_top_k.py`(新規)。
  既存のテストは、順6b の config を差し替え採点器で回す 5 本(`test_threshold_sweep_run.py`・`test_preamble.py`・`test_task_subset.py`・`test_calibration.py`・`test_r8_fit.py`)が `test_top_k.with_filler_top_tokens` で上位 k の置き物を返すように直し、`test_order6b_pilot.py` に pilot にだけある欄を足し、`test_forced_choice.py`・`test_run_real.py` を新しい署名に合わせた。
  手元で確かめたこと(**組合せ論的な件数であって実験結果ではない**): 7 本の `--dry-run` の件数は変わらない(pilot 1,640 / ① 1,440 / (d) 480 / R8 8,160 / S-① 2,400 / S-(d) 1,200 / (c) 306)。7 本は「上位 k: 20」、本番 config は「記録しない」と出る。
  **判定の不変は、torch の要らない組み立て(numpy の行)と、numpy で作った置き物の torch に `scorer_from_model` → `_score_batch` を通したものの両方で、上位 k の有無に対して answer・yes・no がビット単位で同じことを確かめた**(本物の torch と重みは手元に無い)。
  **変異を 25 個注入し(上位 k を付けない / 降順を見ない / 宣言なしで上位を許す / collect が検査しない / 質量を logp の和にする / 固定の行に yes_logp を置かない / 群の検査をしない / 3 経路の execute が k を渡さない / metrics の top_k を null にする / bool を通す / 宣言を run ディレクトリの後で読む / 生のロジットで topk / 綴りを生のトークン記号にする / 復号をキャッシュしない / dry-run 採点器が上位を付けない / 掃引・較正の行に上位 k を置かない / 固定の dry-run が宣言を報告しない / 応答文字列を変える / 上位 k を付けると yes が丸まる / 較正の plan が宣言を読まない / 掃引の collect に k を渡さない / 行の上位 k の並びを逆にする)、それぞれ `test_top_k.py` が落ちることを確かめた**(すり抜け 0。scratchpad のスクリプト。終わった後に 4 ファイルが元のバイト列と一致することを確かめた)

### 4.11 I11 の実装で決めたこと(★2026-09-16 その63。IMPLEMENTER。**分け方・入口・腕の決め方・近接同点の幅の置き場所は ADR-085(人間が選択式で採択。4 問とも推奨)。下の読みは実装の読みで、人間が覆せる**)

- **人間の選択(ADR-085)**:
  決定1 **分け方は I11a run 単位の表 → I11b (c) の補正の適用 → I11c §5 の判定表と、① と (d) の run を B0 と混ぜない守り**(1 セッションに 1 つ)/
  決定2 **§5 の判定表は新しい CLI(`code/analysis/order6b_select.py` の案)が `gonogo.py`(run ごとの #1〜#3)と `r8_fit.py`(遠いオフセット)の関数を呼ぶ。`gonogo.py` は run 単位の表だけを広げる**(極性別の参照線は ADR-079 決定9 のとおり `gonogo.py`)/
  決定3 **腕は引数で明示する**(`--b0` `--r8` `--preamble` `--s-preamble` `--d` `--s-d` `--c`)。各 run の記録(`kind`・`preamble`・`task_subset`・`threshold_sweep.arm`・config の `data.eval_template_set`・`pool_id`・`adapter` = null)が腕の形と合わなければ止める。名前(`experiment_id`・ディレクトリ名)からは推測しない /
  決定4 **近接同点の幅は順6b の config 7 本に `gonogo.near_tie_margin: 0.25`**(ADR-084 決定1 と同じ置き方。本番・smoke には足さない。鍵の無い run は感度の行を出さない。合否には使わない)
- **I11a(run 単位の表。その63)の読み**:
  - **読み1(解いたタスク型)**: `metrics.json` の `task_subset` が null(または欄が無い)なら、従来どおり主軸の 4 タスク型すべてのセルを要る(空のセルは止める)。
    宣言があれば、**宣言のタスク型のうち主軸の 4 水準のセルだけ**を組む(`t1_instructed` はセルを持たない)。#3 は解いた二値型だけ。
    **宣言の外の主軸のタスク型の行がある / 宣言の型のセルが空**なら止める(記録と中身の食い違い)。報告に `solved_task_types` を置く。#1 の群は従来どおり、行の無い群を飛ばす
  - **読み2(腕を見分ける欄)**: run の報告に `experiment_id`・`pool_id`・`adapter`・`template_set`(run の `config.yaml` の `data.eval_template_set`)・`preamble_sha256`(無ければ null)・`task_subset`(宣言のタスク型。無ければ null)を並べる。
    **表は従来どおり run ごとに出す(run をまたいで数えない)**。I11c の CLI が腕の照合にこの欄を使う
  - **読み3(極性別の参照線。ADR-078 決定7 (b) / PLAN-024 §4.1 D2 (b))**: #3 の各セルに、極性ごとの `n`・`n_yes`(`parsed` が True)・`yes_rate` と、
    **極性だけで答える 2 つの戦略**(`gt_no_lt_yes` = ★F138 の定数戦略 / `gt_yes_lt_no`)の correct・rule を**行の真値から数えて**併記する(固定オフセットの項目では 1.0 / 0.0 になる。PLAN-024 §1.3)。
    **`fails`(#3 の印)は変えない**(極性をまとめた correct 対 max(常に Yes, 常に No)。ADR-078 決定9)
  - **読み4(近接同点の感度の行。ADR-079 決定8 / §7)**: 幅は run の `config.yaml` の `gonogo.near_tie_margin`(無い / null = 行を出さない。bool・数でない・0 以下・有限でない値は止める)。
    解いた二値型のセルごとに、`|yes_logp − no_logp| ≤ 幅` の件数と、**それを除いた行の 4 値と #2 の印**(`min_cell_correct_rate` で #2 と同じ比べ方)を出す。除いた後に 0 件なら 4 値と印は null。
    **#1〜#3 の `fails` には使わない**(欄の注記に書く)。`yes_logp` / `no_logp` は predictions の二値群の行の値そのもの(ADR-084 決定3)を `item_id` で引く ——
    **幅を宣言した run で、二値群の行にこの 2 欄が無ければ止める**(I10 より前の run を「近接同点 0 件」と読ませない)。`frame.py` の列は変えない(長形式表の形を動かさない)
  - **読み5(run 間の一致)**: 1 つの報告に渡した run 間で幅が違えば止める(#1・#2 の閾値と同じ)
  - **読み6(掃引の run)**: `gonogo.py` は従来どおり `kind: battery_eval` だけを読む(`frame.load_run` が止める)
- **I11b・I11c の前に人間に上げること(いまは決めない)**:
  - (c) の補正を ① と (d) の項目(と S-①・S-(d))にも掛けて表を出すか —— §5 の候補は C3 = いまの文面の較正だけで、①+(c)・(d)+(c) は候補に無い(ADR-079 決定6)が、(c) の run は ① と (d) の文面も較正している(§3.5・§4.9 読み7)
  - C3 の近接同点を補正前の差で数えるか、補正後の差(`(yes_logp − no_logp) − b`)で数えるか
  - 掃引(R8・S)にも近接同点の件数を出すか(§4.6 読み5 の持ち越し)
  - §5「T3 と T1b で ① の有無が食い違ったら人間に上げる」で、片方のタスク型に満たす候補が無い場合の扱い
  - `aggregate.py`・`frame.py` で ① と (d) の run を B0 と混ぜない守りの形(止める / 腕の列を足して分ける)
- **実装(★2026-09-16 その63 = I11a。上の読み 1〜6 のとおり。CPU のみ・GPU 0)**: `code/analysis/gonogo.py`(`solved_main_task_types`・`check_rows_within`・`provenance_record`・`polarity_reference`・`polarity_strategy_baseline`・`near_tie_margin_from_config`・`forced_choice_gaps`・`near_tie_table`・`thresholds_from_config`・`cell_table` / `constant_strategy_table` の `task_types=`(既定値なし)・表示)/ 順6b の config 7 本の `gonogo.near_tie_margin: 0.25` / `code/tests/test_gonogo.py`(10 → 48)/ `code/tests/test_order6b_pilot.py`(pilot にだけある欄)。
  テストは合成の行に加えて、**パイロット用プールを tmp に書き、B0・①・(d) の config で固定応答の本実行をした run**(二値群の項目の 1/5 に差 +0.125 の近接同点を置く)で、来歴の欄・セルの数・#1 の群・近接同点の件数・除いた #2・極性別の Yes の件数を数え直した(**数値は実験結果ではない**)。
  **変異を 25 個注入し、24 個が `test_gonogo.py` で落ちた。すり抜けた 1 個(除いた #2 の印を `<=` にする)は境界 0.70 のテストを足して落ちることを確かめた**(scratchpad のスクリプト。終わった後に `gonogo.py` が元のバイト列と一致することを確かめた)。`pytest code/tests -q` → **1363 passed**(1325 → +38)

---

## 5. 選び方(**回す前に書く**。PLAN-025 §3.4 (f)、`plans/PLAN-025-binary-methods.md` 185〜188 行)

**候補**(タスク型ごと。T3 は (d) を持たない —— すでに同じ一文で終わっている):

| 記号 | 候補 | T3 | T1b | 変わるもの |
|---|---|---|---|---|
| **C0** | 変更なし | ○ | ○ | なし |
| **C3** | (c) 較正 | ○ | ○ | 採点(ADR-047)。文面は変えない |
| **C2** | (d) 指示文 | — | ○ | T1b の文面に 1 文(ADR-042 決定7・ADR-046・ADR-047 決定1) |
| **C1** | ① 前置き | ○ | ○ | 全タスク型の入力(ADR-042 決定5 (iii)。`rule_rate` の注記 §8) |

> **→ ★2026-09-12(その53)確定(ADR-079 決定6。G7 (a)・G8 (a)・G9 (a)・G13 (a)、G6 (b) で (v) を外した)。**合格の条件は (i)〜(iv)。**凍結(tag)は実装・dry-run の後**
**変更の小さい順(~~案。~~G7 (a) 採択)**: **C0 < C3 < C2 < C1。**理由: C3 は入力を変えない / C2 は 1 タスク型に 1 文(T3 と同じ文字列)/ C1 は 4 タスク型すべての入力を変える。

**合格の条件**(タスク型ごと、パイロット用プールで。**どれも値は変えない**):

- (i) **#2**: そのタスク型の 3 セル(`id` / `interp` / `extrap_magnitude`)すべてで `correct >= 0.70`
- (ii) **#3**: 同じ 3 セルすべてで `correct` > max(常に Yes, 常に No)
- (iii) **C1 に限り**: ①-num で T1・T2 の 6 セルが #1(`parse_fail < 0.02`。群で読む。ADR-078 決定11)と #2 を満たす(G9。決定8 の対称性)
- (iv) **和を読んでいること**(★F138 の守り。~~C1・C2 は G5 で S を採った場合だけ~~ → G5 で S を採った(ADR-079 決定4)ので C1・C2 にも掛かる): その候補の掃引(C0・C3 は R8、C1・C2 は S)の遠いオフセットで、**`θ ≤ −2` の側と `θ ≥ +3` の側の `correct` がどちらも 0.70 以上**(案。#2 の値を流用し、新しい値を作らない。G13)。
  定数戦略は `θ ≤ −2` の側で 0 になる。**`β1` は使わない**(§3.2.1 の揃え方と完全分離に左右されるため。`β1` と `θ*` は記述として出す)
  - **→ ★2026-09-14(その58)単位を補った(ADR-081 決定3。人間が選択式で選んだ)**: (i)・(ii) と同じく、**そのタスク型の 3 セル(`id` / `interp` / `extrap_magnitude`)それぞれで**両側とも 0.70 以上を要る(タスク型でまとめた 1 つの値ではない)。
    文面に「3 セルすべてで」の語が無く、どちらにも読めた。**値(0.70・−2・+3)は変えていない。**R8 の 1 セルあたりの項目は低い側 160・高い側 880、S は 160・240(組合せ論的な件数)
- ~~(v) **質量**(★F139。G6 で「入れる」を選んだ場合だけ): 最初の位置の Yes/No 12 綴りの質量の中央値が **___(人間)** 以上~~ → **G6 (b)。合格の条件に入れない。記録だけ**(ADR-079 決定5)

**選ぶ手順**: タスク型ごとに、~~(i)〜(v)~~ (i)〜(iv) を満たす候補のうち**表の順で最も小さいもの**を採る。**T3 と T1b で ① の有無が食い違ったら、そのまま人間に上げる**(タスク型の対比に「前置きの有無」が混ざる)。
**この結果は「候補」であって採用ではない。**採用は ADR-046 の手続き(ADR-078 決定2。ADR-039 決定3 の一般手続きと読める —— 材料 §A6 の「曖昧」)で人間が決め、主プールで測り直して ADR-076 決定1 の規則を当てる。

---

## 6. 結果の分岐(PLAN-025 §5 の 3 の形。**分岐の値は人間**)

| 分岐 | 条件 | その後(案) |
|---|---|---|
| **A** | どちらかのタスク型で、§5 を満たす候補がある | その候補を人間が採るか決める → 採るなら文面を改め(ADR-046)、主プールで二値群を測り直す → ADR-076 決定1。**満たさないタスク型は B か C** |
| **B** | 候補はどれも満たさないが、C0 の R8 で和を読んでいる(遠いオフセットの `correct` が両側で G13 の値以上)。崩れるのは閾値の近くだけ | 固定オフセットの項目では 0.70 に届かない。PLAN-024 D4 (a)(df 6 → 2)/ 二値群の従属変数を R8 の `Δ̂` に替える(**主要な検定を変える**)/ ③-ii・③-iii の検討、を人間が選ぶ |
| **C** | R8 でも S でも読めていない(遠いオフセットでも崩れる。PLAN-025 §5 の「`β1 ≤ 0`」はこの形の一つ) | 文面では直らない(PLAN-025 §5)。③-ii・③-iii を ② より先に検討するか、D4 (a) を採るか |

- T1b だけが B・C に落ちる場合は、ADR-047 決定2(案 C の backstop。T1b を主軸から外して df 6 → 4)の発火記録を含めて人間が決める
- **エージェントは分岐の結果を解釈しない**(`CLAUDE.md` §8)。表と数値を出すところまで

---

## 7. 近接同点(|yes_logp − no_logp| ≤ 0.25)の扱い(ADR-078 決定10 の持ち越し)

- **事実**: R4(batch 1)対 R1(batch 4)で分類が変わった強制選択 13 件は、両方の run で |差| ≤ 0.25 だった。R1 で |差| ≤ 0.25 は 960 件中 55 件 [run:20260911_141547_order6_r1] [run:20260911_161738_order6_r4]
- **論点**: 二値群が主解析に戻る場合、近接同点は batch で分類が揺れうる。**揺れの大きさは文面で変わりうる**((d) や ① で質量や差の分布が動けば、近接同点の割合も動く)
- 選択肢(G12):
  - (a) **順6b は batch 4 のまま、腕ごと・セルごとの近接同点の件数と、それを除いた場合の #2 を併記する(感度の行。合否には使わない)。batch を替えるかは、主プールで測り直す前に人間が決める**(推奨。候補の文面が決まるまで近接同点の割合が分からない)
  - (b) 順6b の二値の腕を batch 1 で回す(D5 (c) を先取り。R4 は 1 run あたり R1 より 373 秒長かった。PLAN-024 §4.1 D5 の行)
  - (c) 近接同点を別の分類にする(**4 値分解を変える**。`CLAUDE.md` §6 に触れる。勧めない)
- **→ ★2026-09-12(その53)(a) を採択(ADR-079 決定8)。batch を替えるかは主プールで測り直す前に人間が決める**

---

## 8. `rule_rate` の解釈が変わる旨の注記(~~**下書き**~~ → **★2026-09-12(その55)人間が確定**(G14。ADR-080 決定1)。ADR-042 決定5 (iii)。ADR-078 決定8)

> **確定の範囲**: 下の 3 つの注記の文面を、① / (d) / (c) を本番に採る場合に使う形として確定した。**どの候補を採るかは順6b の後に人間が決める**(ADR-078 決定2)。採らない候補の注記は使わない

> **① を採った場合の注記(下書き)**
> 1. 全タスク型・全条件(`ident` を含む)の入力の先頭に、和を含まない数どうしの比較の例示 4 行(極性ごとに Yes・No が 1 つずつ)が同じ文字列で置かれる。例示のラベルはどの参照規則の下でも同じなので、**例示は規則を示さず、どの規則にも有利にならない。**`rule_rate` の定義(判別可能な項目のうち、参照規則の値に一致した割合。ADR-016)は変わらない
> 2. **変わるのは数値の意味である。**`rule_rate` は「数の比較を Yes/No で答える例示を直前に見た状態で、病変規則が表に出る割合」になる。**例示の無い `rule_rate`(順6、先行研究の数値)とは比べられない。**例示が、書式を示すことで病変を出やすくするのか、書かれた数どうしを比べる読み方に引き寄せて出にくくするのかは分からない(向きは主張しない)
> 3. **主要検定(タスク型間で既知性の勾配が平行か)は、全タスク型が同じ前置きを持つときに限って、前置きの無い設計と同じ問いに答える。**二値群にだけ置けば、タスク型の対比に「文脈の有無」が混ざる(ADR-078 決定8 の理由)
> 4. **T1 の `id` は訓練の書式(`a+b=`)と 1 文字も違ってはならない評価アンカーである**(`code/eval/run.py` 211〜218 行 / preflight 検査6)。前置きを置いた T1 はアンカーではなくなるので、**病変が訓練の書式で入ったことの確認(操作確認)は前置きの無い T1 で別に測る必要がある**(G15。① を採る場合に、主プールで測り直す前に決める)
> 5. この変更は順6(主プール)と順6b(パイロット)の実測を見た後に、素のモデルで選んだものである。**`p2` などの FT モデルの結果は見ていない**(前例 ADR-074)
>
> **(d) を採った場合の注記(下書き)**: T1 と T1b の差が「出力の型」と「指示文の有無」の 2 つになり、ADR-026 / ADR-042 決定7 の 2×2 の直交対比が崩れる。
> **既にある指示付き T1(`bare_sum_instructed`。ADR-035)を対比の相手にすれば 2 つとも指示文を持つ形に戻せる**が、主軸の T1 を替えることになる(人間)。`rule_rate` の定義は変わらない
>
> **(c) を採った場合の注記(下書き)**: 入力は変わらず、採点が「内容のない入力で推定した偏りを差し引いた Yes/No の大小」になる(ADR-047 の採点の変更)。`rule_rate` は補正後の判定で数える。**補正の定数は条件ごとに取るのか `ident` で 1 つにするのかで、条件間の比較の意味が変わる**(未決。採る場合に人間)

---

## 9. 実装が要る箇所(材料 §B を照合済み。**実装はレビューの後**)

| # | 何を | どこ | 規模 | 備考 |
|---|---|---|---|---|
| I1 | pilot の FT manifest と評価プール | `configs/exp_order6b_pilot.yaml`(新規)/ CPU の生成 | config のみ(の見込み) | §4.1。生成物の manifest をコミットする。**✅ 済(2026-09-12 その54。§4.3)** |
| I2 | pilot と main の非交差の検査 | `code/tests/` / `infra/preflight.py` | 小〜中 | PLAN-001 §4.6 規則3。既存の有無を先に確かめる。**✅ 済(その54。評価プールどうしの検査は無かったので足した。`eval.counterpart_manifest` を 4 本の config に足した。§4.3)** |
| I3 | R8・S の掃引項目の生成と配線 | 新しい入口(`build.py` の `build_items_from_entries` は `sweep` を渡さない)/ config に `θ` の水準 | 中 | 組の水準のハッシュで 20 組(§3.2)。**✅ 済(2026-09-12 その55。`code/data_gen/sweep_pool.py`・`eval.threshold_sweep`。組は gt・lt を併合したセルから(ADR-080 決定3)。§4.4)** |
| I4 | 掃引項目の記録の経路(4 値分解を通さない) | `code/eval/run.py` の別経路 / `metrics.json` の新しい欄 | 中 | 項目ごとの logp と上位 k。`Δ̂` は後処理。**配線の読みは §4.5(2026-09-13 その56)。**~~実装は未着手~~ **✅ 済(2026-09-14 その57。`configs/exp_order6b_r8.yaml`・`run.py` の掃引の経路・`test_threshold_sweep_run.py`。§4.5 の「実装」)**(上位 k の欄は I10) |
| I5 | `Δ̂`・`β1`・遠いオフセットの `correct` の当てはめ | 新規(例 `code/analysis/r8_fit.py`) | 中 | **G1 の揃え方で実装する**。除外件数を必ず出す(ADR-030 決定6)。**✅ 済(2026-09-14 その58。「階段の位置」の定義 = §3.2.1.1・ADR-081 / `code/analysis/r8_fit.py`・`test_r8_fit.py`。§4.6)** |
| I6 | 前置き(①) | 新しい鍵(例 `eval.preamble`)。**`eval.few_shot_k` の門(`code/eval/model.py` 150 行)は使い回さない** | 中 | 全群の入力の先頭に連結(G4)/ 並びのハッシュ(G3)/ `metrics.json` に前置きの有無と sha256。**✅ 済(2026-09-15 その59。`eval.preamble`・`code/eval/preamble.py`・`run.render_prompts`・`configs/exp_order6b_s_preamble.yaml`・`test_preamble.py`。§4.7)。固定オフセットの ① の config は I8(3 群への絞り方)** |
| I7 | preflight 検査6 と前置き | `infra/preflight.py` | 小 | 前置きのある run は「アンカーでない」と宣言して検査6 の比較から外し、その旨を記録する(案)。前置きの無い T1 のアンカーは変えない。**✅ 済(その59。前置きのある run は SKIP + 理由。訓練側の書式は検査して破れていれば FAIL。§4.7 読み6)** |
| I8 | (d) のテンプレート集合 | `configs/templates/`(順6b 専用) | config のみ | 本番の `t1b.yaml` は触らない。**★その59 追記: 固定オフセットの ① の run(比較・T1・T2)も、パイロット用プールの 5 群のうち 3 群に絞る必要がある(`_read_pool_items` は宣言外の群を拒む)。絞り方は (d)(T1b だけ。固定 480・S 1,200)と 1 つの仕組みで決め、① の config もここで作る(人間の回答。§4.7)**。**✅ 済(2026-09-16 その60。絞りの宣言 `eval.task_subset` = ADR-082 / `code/eval/task_subset.py` / `configs/templates/order6b_d.yaml` / config 3 本。§4.8)** |
| I9 | (c) の内容のない入力の forward | 小さな新規関数(`scorer_from_model` / `collect_forced_choices` を流用)/ `calibration.json` | 小 | 真値が無いので `Item` / `classify` を通さない。**✅ 済(2026-09-16 その61。綴りは原典と一致・空文字と平均の順 = ADR-083 / `code/eval/calibration.py`・`calibration_run.py`(別の CLI)/ `configs/exp_order6b_c.yaml` / `test_calibration.py`。§4.9)** |
| I10 | 上位 k の記録 | `code/eval/forced_choice.py` の `_score_batch`(357 行)・`ForcedChoice`(72 行)/ `run.py` の `prediction_record`(736 行)・`metrics_payload`(1053 行) | 中 | **判定は触らない**。STATE「次のアクション」3 の並行 PLAN と同じ変更 —— **どちらの PLAN で実装するかを決め、二重に実装しない**(G16)→ **★本 PLAN で実装する(ADR-079 決定9。I11 の極性別の参照線も同じ)** → **✅ 済(2026-09-16 その62。k の置き場所・綴りの形・固定オフセットの行の欄 = ADR-084 / 3 経路(固定オフセット・掃引・(c) の較正)の行に `top_k`・`top_k_mass`・固定オフセットの二値群の行に `yes_logp` / `no_logp` / `code/tests/test_top_k.py`。§4.10)** |
| I11 | 順6b の集計 | `gonogo.py` の #1〜#3 をパイロットの run に / 極性別の参照線(ADR-078 決定7 (b)。これも並行 PLAN と同じ)/ §5 の判定表 / §7 の感度の行 | 中 | 判定表は §5 を機械的に当てるだけ。**解釈はしない**。**3 つに分ける(ADR-085 決定1)**: **I11a ✅ 済(2026-09-16 その63。run 単位の表 = `gonogo.py`。§4.11)** / I11b (c) の補正の適用 / I11c §5 の判定表(新しい CLI。腕は引数で明示)と混ぜない守り |
| I12 | テスト | 上のすべて | — | `pytest code/tests -q`。前置きの連結・並びのハッシュ・掃引の件数(8,160 / 3,600)・揃え方の符号(§3.2.1 の算術の例をそのままテストにする)・較正の後処理・上位 k |

- 手順: **本 PLAN のレビュー → I1〜I12 の実装 → テスト → dry-run(`run.py --dry-run` を各腕の config で)→ GPU 承認(§11)→ 本実行 → 回収 → 集計 → 人間**(`CLAUDE.md` §4、`infra/RUNPOD.md` §4)
- 実装は 1 セッションに収まらない見込み。**I1・I2(プール)/ I3〜I5(R8)/ I6〜I9(候補)/ I10・I11(記録と集計)**で分けるのが自然(案)

---

## 10. GPU 見積り(**見積りであって実測ではない**)

**上限の算術の型は PLAN-024 §3 D2 (c)**(`plans/PLAN-024-order6-reading.md` 223 行): 順6 R1 の生成 217.552 秒をすべて一方の型に割り振った値を 1 項目の上限と置く [run:20260911_141547_order6_r1]。

- 強制選択: 217.552 / 960 = **0.227 秒/項目以下** / 自由生成: 217.552 / 680 = **0.320 秒/項目以下**(**同じ 217.6 秒を両方に使うので、2 つの上限を足すと二重に悲観側になる**)
- 前置きのある腕(①-bin・①-num・(c) の ①)は入力が長いので **2 倍**と置く(エージェントの仮定)
- 重みの読み込み: R1 の 126.857 秒 × run 数 6(B0 / R8 / ① / (d) / (c) / S)
- 準備と後片付け: 順6 の 2 回目の稼働 2,835 秒(人間の申告。ADR-078「記録」D6)から 5 run の合計秒(352.8 + 311.2 + 309.5 + 726.2 + 589.2 = 2,288.9)を引いた **546 秒**

| 組 | 強制選択 | 自由生成 | 計算 | 読み込み + 準備 | 合計 | 悲観側(× 1.5) | 費用(悲観側。$0.74/時で) |
|---|---|---|---|---|---|---|---|
| **S なし** | 10,866 | 1,160 | 約 55 分 | 約 22 分 | **約 1.3 時間** | **約 1.9 時間** | 約 $1.4 |
| **S あり** | 14,466 | 1,160 | 約 77 分 | 約 22 分 | **約 1.7 時間** | **約 2.5 時間** | 約 $1.8 |

- 参考: S を 17 水準すべてにすると、計算は「S なし」より約 77 分増える(同じ算術。「S あり」より約 54 分増える)
- **打ち切りは 3 時間(案)。**10 GPU 時間の門(`CLAUDE.md` §2)には届かない
- **単価は起動の直前に読み直す**(2026-09-10 時点で $0.74/時。ADR-073 決定1)

---

## 11. GPU 承認の文面(案。人間がこのまま承認するか、直して承認する。型は PLAN-023 §2.4、`plans/PLAN-023-order6-readiness.md` 213〜222 行)

> 順6b(素のモデルの小さな診断。ADR-078 決定1)の GPU 使用を承認するか。
> - 問い: 二値群(T3・T1b)の測り方の候補(① 前置き / (d) 指示文 / (c) 較正)が Go/No-Go #2・#3 を満たすか、素のモデルが閾値から遠い所で和を読んでいるか(R8)
> - モデル: `meta-llama/Llama-3.1-8B-Instruct`(revision `0e9e39f…`)。**adapter = null**(素の重み。FT は 1 本も回さない)
> - プール: `data/generated/battery/pilot/`(`pool_id: pilot`)と掃引の項目。**本 PLAN §4 で生成し、manifest をコミットした後に回す。パイロットの数値は主張に使わない**
> - run: preflight → B0(1,640)→ R8(8,160)→ ①(960 + 480)→ (d)(480)→ (c)(≤ 306)→ S(3,600。~~**G5 で採った場合だけ**~~ ADR-079 決定4 で採った)。合計 ~~12,026 項目・回(S ありで 15,626)~~ **15,626 項目・回**
> - 選び方: 本 PLAN §5 を**回す前に**凍結する(コミットと tag)。回した後に変えない
> - GPU: RTX 4090 SECURE 1 台(順5・順6 と同じ型)。**単価は起動の直前に読み直す**(2026-09-10 時点で $0.74/時)。停止中のポッドを再開するか新しく立てるかは、起動の前に人間に確かめる
> - 見積り(実測ではない): ~~S なしで約 1.3 時間(悲観側 1.9 時間)、~~ S ありで約 1.7 時間(悲観側 2.5 時間)。**3 時間で打ち切って報告する**
> - 終了後: run を開発機に回収・コミットし、ポッドを停止する(`infra/RUNPOD.md` §7)。terminate は人間が行う
> - **承認の対象は順6b だけであり、主プールでの二値群の測り直しや Phase 1 本実験の GPU ではない**

- **承認を求める時点(案)**: 実装・テスト・dry-run が済み、§5 を tag で凍結した後。**本 PLAN のレビューの時点で文面だけ先に見てもらう**

---

## 12. リスク・不確かさ

- **パイロットと主プールで型が違う可能性**: 候補はパイロットで選び、主プールで測り直す。B0 がパイロットで順6 と大きく違う型を示したら、選んだ候補を持ち込めるかは人間が判断する(§3.1)。**違いの大きさの基準はこの PLAN では置いていない**(置くなら G14 の前に人間)
- **★F141(揃え方と完全分離)**: 決めないと R8 の `β1`・`θ*`・`Δ̂` の意味が決まらない(§3.2.1)。§5 (iv) と §6 は遠いオフセットの `correct` を主に使うので左右されにくいが、**Phase 1 の R8(副次。ADR-030)はそのまま左右される。回す前に決める**
- **① の例示の数値・並びは 1 案だけ**(4 行)。効かなかったとき、行数や数値を変えた ① を順6b の中で試すことはしない(**候補を後から足すと §5 の選び方が形骸化する**)
- **(c) の補正は極性ごとの定数**なので、★F138 の定数戦略に寄せても固定オフセットの項目では correct が上がる(§3.5)。R8 に掛けた曲線で確かめる
- **上位 k は記述だけ**。★F139 の (a)/(c) は順6b の後に人間が決める(ADR-078 決定5)
- 候補の文面が決まるまで、主要検定の df・P1・検出力分析・Δ の 5 行・凍結(順9)は確定しない(ADR-078 のリスク欄)
- **材料 §B2 の誤り(§4.1)を見つけたので、材料の他の箇所も誤りうる。**実装では各箇所を開いてから手を入れる

---

## 13. 記入欄(人間)

**選択肢の形にした。推奨は案であって決定ではない**(`CLAUDE.md` §8 / ADR-039)。採択されたら ADR に「提案 エージェント / 採択 人間」と書く。
**★印は回す前(選び方の凍結の前)に必要なもの。**

> **→ ★2026-09-12(その53)記入済み(ADR-079)。人間の回答: 「全て推奨を採用。G6は(b)」。**
> 推奨の付いた 14 項目は推奨、G6 は (b)。**G14 は推奨が無く未記入。G17 の「承認」はエージェントの読み**(異議があれば覆す)
> **→ ★2026-09-12(その55)G14 は人間が「確定」と記入した**(その54 の開始時に作業ツリーにあった記入。人間がその55 の冒頭で自分の記入だと述べた。ADR-080 決定1)

| 記号 | 決めること | 選択肢 | 記入 |
|---|---|---|---|
| **★G1** | ★F141: R8 の当てはめの極性の揃え方(ADR-030 決定6 の書き直し)と、完全分離の扱い | 揃え方: **(a) 応答を揃える(`y` = 閾値より小さい側と答えた)。極性ごとの交差点の開きも併記(推奨)**/ (b) 極性ごとに別に当て、`θ*` を平均 / (c) ADR-030 の文面どおり(§3.2.1 で `Δ̂` が識別されない)。完全分離: **(a) 除外せず「階段」として別に数え、交差点は階段の位置で取る(推奨)**/ (b) 罰則付きの推定 / (c) 文面どおり除外 | **揃え方 (a)・完全分離 (a)**(ADR-079 決定1) |
| **★G2** | パイロット用プールの作り方 | **(a) pilot の FT manifest を 5 条件で作り、`build_filled` で建てる(推奨。§4.1)**/ (b) 別案(自由記述) | **(a)**(ADR-079 決定2) |
| **★G3** | ① の文面・行数・並び | **(a) §3.3 の 4 行・並びは項目ごとにハッシュ(推奨)**/ (b) 4 行・並びは固定 / (c) 行数か数値を変える(自由記述) | **(a)**(ADR-079 決定3) |
| **★G4** | ① の置き場所 | **(a) 全タスク型で同じ文字列を入力の先頭に連結(推奨)**/ (b) chat の前のターンとして置く(裸の書式の群には置けない) | **(a)**(ADR-079 決定3) |
| **★G5** | ★F138 への守り(S) | **(a) 5 水準の掃引を ① と (d) に足す(+3,600 forward。推奨)**/ (b) 17 水準すべて(+12,240)/ (c) 足さない(★F138 に弱いまま選ぶ) | **(a)**(ADR-079 決定4) |
| **★G6** | 質量(★F139)を合格の条件に入れるか | (a) 入れる。値 = ___ / (b) 記録だけ(★F139 の (a)/(c) を順6b の後に決める ADR-078 決定5 と合う)。**推奨は置かない**(D3 を先取りするかどうかの判断なので) | **(b) 記録だけ**(人間が選択。ADR-079 決定5) |
| **★G7** | 候補の「変更の小ささ」の順 | **(a) C0 < C3 < C2 < C1(推奨。§5)**/ (b) 別の順(自由記述) | **(a)**(ADR-079 決定6) |
| **★G8** | ① と (d) を重ねた候補(T1b)を足すか | **(a) 足さない(ADR-078 決定1 に無い。推奨)**/ (b) 足す(+480、S ありで +1,200) | **(a)**(ADR-079 決定6) |
| **★G9** | C1 の合格に数値型の #1・#2 を入れるか | **(a) 入れる(決定8 の対称性。推奨)**/ (b) 記録だけ | **(a)**(ADR-079 決定6) |
| **★G10** | 上位 k の k | **(a) 20(推奨)**/ (b) 10 / (c) 自由記述 | **(a) 20**(ADR-079 決定7) |
| **★G11** | (c) の内容のない記号 | **(a) `N/A`・`[MASK]`・空文字の 3 種の平均(推奨。実装前に原典の綴りを確かめてから確定)**/ (b) 1 種(自由記述) | **(a)**(原典の綴りの確認が条件。ADR-079 決定7) |
| **★G13** | 遠いオフセットの `correct` の基準(§5 (iv)・§6 の B/C) | **(a) #2 の 0.70 を流用(推奨。新しい値を作らない)**/ (b) 別の値 = ___ | **(a) 0.70**(ADR-079 決定6) |
| G12 | 近接同点(ADR-078 決定10) | **(a) 順6b は batch 4 のまま件数と感度の行を併記し、batch は主プールで測り直す前に決める(推奨)**/ (b) 順6b の二値の腕を batch 1 で / (c) 別の分類にする(勧めない) | **(a)**(ADR-079 決定8) |
| G14 | §8 の `rule_rate` の注記の下書き | 確定 / 修正(自由記述)/ 候補が決まってから | 確定(**人間の記入**。2026-09-12。ADR-080 決定1) |
| G15 | ① を採る場合の T1 のアンカー | (a) 前置きの無い T1 を操作確認として別に残す / (b) 主解析の T1 も前置き無し(対称性は崩れる)/ (c) 順6b の後に決める(**推奨**) | **(c)**(ADR-079 決定9) |
| G16 | 上位 k(I10)と極性別の参照線(I11)をどの PLAN で実装するか | **(a) 本 PLAN に含める(推奨。順6b がどちらも要る)**/ (b) 並行の実装 PLAN で先に実装し、本 PLAN はそれを使う | **(a)**(ADR-079 決定9) |
| G17 | 本 PLAN のレビュー | 承認(実装に進む)/ 修正(自由記述) | **承認**(回答に修正の指示が無いのでそう読んだ。エージェントの読み。ADR-079 決定10) |

---

## 14. やらないこと

- **GPU を回さない / 実装しない**(このセッションは起草だけ。1 セッション = 1 PLAN)
- **本番の T1b・T3 の文面を変えない**(ADR-078 決定2)/ **#2 = 0.70・#3 の値を変えない** / 判定規則を変えない
- 二値群 6 セル・★F139 の (a)/(c)・近接同点の扱いを決めない(順6b の後に人間)
- 順6b の結果を解釈しない / 候補を採用しない(§5 の結果は「候補」まで)
- 主プールで候補を試さない(PLAN-025 §3.4 (f))
- ③-i・CoT を入れない(ADR-078 決定4)
