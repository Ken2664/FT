# CRITIQUE.md — CRITIC の指摘(追記のみ)

> **このファイルは追記のみ**(`AGENTS.md` の CRITIC)。**CRITIC は指摘するだけで、修正はしない。**
> 指摘を読んだ人間が、採るかどうかを決め、採ったものを IMPLEMENTER に回す。
> 各指摘には「誰が決めるか」を書く。**値や規則を変える提案はしない**(§8.1 のような凍結の対象は人間と ADR が決める)。
> 2026-09-26(その105)に新規に作った(それまで `logs/CRITIQUE.md` は repo に一度も無かった。`git log --all -- logs/CRITIQUE.md` は空)。

---

## 2026-09-26(その105)PLAN-032 I4 `code/analysis/sharpness_fit.py` の §8.1 R2〜R7 との突き合わせ

- **担当**: CRITIC (Opus 5.5)。**推奨モデル(Opus)と一致**
- **対象**: commit `4837cd4`(その104。IMPLEMENTER (Opus 5.5))の `code/analysis/sharpness_fit.py`(新規 959 行)・`code/data_gen/sweep_pool.py`・`code/eval/run.py`・`code/eval/battery/t3_comparison.py` の diff、テスト `code/tests/test_sharpness_fit.py`・`test_diag_sharpness.py`、config 5 本、`configs/templates/diag_explicit{,_d}.yaml`
- **仕様の正本**: `plans/PLAN-032` §8.1(R1〜R9)と §11 の下の注「実装の読み 1〜11」、ADR-107
- **このセッションで回したもの**: `pytest code/tests/test_sharpness_fit.py code/tests/test_diag_sharpness.py -q` → **93 passed**。
  `sharpness_fit.confidence_interval` に合成した入力を渡して挙動を確かめた(下の指摘 4)。**GPU 0・pod 0・tag なし。ここに出る数値はどれも実験結果ではない**(コードの定数・config の値・テストの件数・合成した入力に対する関数の出力)
- **コード・config・テスト・PLAN・ADR は 1 文字も変えていない**

### 指摘(重い順)

#### C105-1【中・テストの穴】R4 の「T1b と T3 に別々に」と R3 の「1 セルでも下回れば届かない」を、本物の記録の経路で違う結果にして試したテストが無い

- **何が**: 本物の掃引の経路を通すシナリオ 5 本(`code/tests/test_sharpness_fit.py:151` の `SCENARIOS`)は、**どれも腕ごとに 1 つの答え方を T1b と T3 の両方、3 つの既知性セルすべてに当てる**。
  そのため (a) T1b と T3 の判定は必ず同じになる(テスト自身の docstring が「ここでは同じ答え方なので同じ段」と書いている。`:391`)、
  (b) 3 セルの Δ₂ は必ず同じになる、(c) Δ₂ は 0 か 1 の両端だけで、線 0.088 の近くを本物の経路で通っていない
- **失敗の筋書き**: `build_report` の判定の組み立て(`sharpness_fit.py:748-756`)が、たとえば両方のタスク型に T1b の「届く」を読む、あるいは `cells_by_arm_task` の鍵がタスク型を取り違える、という配線の誤りを持っていても、**93 件はすべて通る**。
  ADR-107 決定4 (3)(m2)は「片方だけ分岐に入るときはその型を探索に落とす」と決めており、**T1b と T3 の行き先が割れる場合こそ判定表の本番である**
- **いまのコードは正しい**(`:748-756` を読んだ。`reaches[(ARM_A, task)]`・`reaches[(ARM_B, task)]` をタスク型ごとに引いている)。これは**現在の誤りではなく、凍結 tag の後に配線が変わったときに捕まえる網が無い**という指摘である。
  R3 の「1 セルだけ下回る」は手で組んだ辞書(`test_reach_needs_all_three_cells`)でしか試されていない
- **誰が決めるか**: 人間が採るかを決め、IMPLEMENTER が「T1b と T3 で答え方を変える」「1 つの既知性セルだけ答え方を変える」「線の近くの Δ₂ になる答え方」のシナリオを足す(**tag の前**が安い)

#### C105-2【中・止める条件の穴】R1 の前提(素のモデル・batch 4・上位 k 20・4 腕が同じプール)を、判定の時点で run の記録と照合していない

- **何が**: `sharpness_fit` が判定の前に確かめるのは、腕の宣言・文面の出どころ・タスク型・`sharpness` 欄・`near_tie_margin`・記録の整合(`r8_fit.check_records`)・R7 の件数と対である。次は**確かめていない**:
  - `metrics.json` の `adapter` が null であること(R1「素の Llama-3.1-8B-Instruct(adapter なし)」)。**header に並べるだけ**(`:267`・`:818`)
  - モデルの名前・revision の一致は `main` の中だけ(`:937-941`)。**`build_report` を直接呼ぶ経路(テストはすべてこちら)には無い**。adapter の一致はどちらにも無い
  - run の `eval.batch_size` = 4(R1・ADR-107 決定6)、`forced_choice.top_k` = 20
  - 4 本の `pool.items_sha256` の一致。**対の検査(`check_pairing`)は A↔B と A-d↔B-d だけで、R5 が比べる B-d↔B は照合していない**
- **縛っているもの**: `code/tests/test_diag_sharpness.py:428` の `test_arm_configs_run_as_decided` が**コミット済みの config** の batch 4・上位 k 20・adapter null・pool_id pilot を縛っている。**しかし ANALYST が読むのは run dir の `config.yaml` と `metrics.json` であり、そちらは照合されない**
- **失敗の筋書き**: RUNNER が時間を詰めるために 1 腕だけ batch を上げて回し直す / 1 腕だけ run の config の `model.adapter` が書き換わった状態で回る / 1 腕だけ別の日にプールを作り直して回す → **判定表は止まらずに出る**。
  batch の違いは近接同点の出方を変えうる(ADR-079 決定8 の G12 がまさにその懸念)ので、R5 が比べる B-d と B の batch が違えば、その差が R5 に混ざる。
  (I5 のパイロットのアダプタの run は固定オフセットで `kind` が違うので、`load_diag_run` の kind の検査で止まる。**紛れ込みの経路はそこには無い**)
- **R7 の本文はこれらを挙げていない**。足すなら読み 10 と同じ種類の「R7 の外の止める条件」になるので、**足すかどうかは人間**(値や規則は変えない。判定を止めるだけ)。
  **adapter の条件は一通りに決まらない**ことに注意: R9 は同じ線を段4 の「前段 FT の後の新ベースの B」にも当てるので、「adapter は null」と縛ると段4 で使えず、「4 腕で adapter が同じ」と縛ると段4 で A を素のまま残す組み方ができない。どちらにするかも人間

#### C105-3【中・仕様の食い違い】§8.1 の本文が A-d の役割で食い違っている(読み 8 の根)。tag を打つとこの食い違いがそのまま凍る

- **何が**: §8.1 R1 の表は A-d の役割を「**R5 の材料**・記述」と書き、ADR-107 決定2 も「B-d・A-d は**決定5 の材料**と感度の行」と書く。**しかし R5(= 決定5)の規則は B-d と B しか見ない。**
  実装は読み 8 で「A-d は記述だけ」と読み、`LINE_ARMS` から A-d を外した(`sharpness_fit.py:85`)。読みとしては筋が通る
- **なぜ問題か**: tag の対象は §8.1 の文面であり、読み 8 は §11 の注(tag の対象外)にしか無い。**凍った文面は「A-d は R5 の材料」と言い、凍った規則は A-d を使わない**。
  後から「A-d を R5 で使うべきだった」という読み直しの余地が残る(HARKing の入口)
- **誰が決めるか**: 人間。tag の前に、読み 8 を ADR で確かめる(R1 の表の文言をそろえる)か、A-d が R5 で果たす役割を書き足すか。**エージェントはどちらも決めない**

#### C105-4【低〜中・記述の行】読み 6 の信頼区間は、組ごとの差がすべて同じ値のとき幅 0 に潰れる。この診断ではその状況が起こりうる

- **何が**: `confidence_interval`(`:484-499`)は `平均 ± z·sd(d_i)/√n`。**d_i がすべて同じなら sd = 0 で、区間は [Δ₂, Δ₂] になる**。
  合成した入力で確かめた(**実験結果ではない**): d_i がすべて 0(160 組)→ `low = high = 0.0`、すべて 1 → `low = high = 1.0`。
  1 組だけ ¼ → `[−0.0015, 0.0046]`(Δ₂ = 1/640 に対し、下端が負)
- **この診断で起こりうる理由**: (i) 定数の応答(どの θ でも同じ答え)なら d_i はすべて 0 —— 裸の T1b は Yes/No の質量が小さく(PLAN-032 §2.2 事実 c)、一方に倒れ続ける応答はありうる。
  (ii) 明示の比較 A がほぼ完璧なら d_i はすべて 1。**既存のシナリオ「branch」の A はまさに [1, 1] を出しているが、テストはそこを見ていない**
- **なぜ問題か**: `sharpness.txt` には `CI=[0.000, 0.000]` と出て、「0 と精密に推定された」と読める。Wald 型の区間はほかに、[−1, 1] の外へはみ出しうる・carry の層(80 + 80)を無視する(こちらは小さい)
- **判定には影響しない**(ADR-107 決定3 (iv)。点推定だけで判定する)。**読み 6 そのものが §8.1 に無い**ので、tag の前に人間が (a) このまま (b) sd = 0 の区間に印を付ける (c) 別の計算法、のどれにするかを決める。**CRITIC は計算法を推さない**

#### C105-5【低・記述の行】R6 の S1(混ぜた β1)は、R8 の β1 とも監査の換算値(β1 ≥ 0.18 ⇔ Δ₂ ≥ 0.088)とも同じ物差しでない。出力にそのことが書かれていない

- **何が**: S1 は `r8_fit.locate_crossing` の θ についてのロジスティックの傾きで、**当てる θ の水準で値が変わる**(モデルがロジスティックでなければ、とくに遠い水準のわずかな誤答が傾きを引き下げる)。
  診断の水準は ±300 までの 19 水準(`configs/exp_diag_pool.yaml:715`)、R8 は −3〜13 の 17 水準(`configs/exp_order6b_pilot.yaml:721`)
- **さらに T < 1 の除外が θ ≤ −5 の母集団を変える**: `id`・`interp`(和 5〜195)は θ = −300 で全組が除かれ、θ = −100 では和 101 以上の組しか残らない。遠い負の側の点は大きい和の組だけから来る(Δ₂ の 5 水準には掛からない = 下の「確かめて問題が無かったもの」)
- **なぜ問題か**: ADR-107 の文脈は「R8 の β1(0.001〜0.048)は換算値 0.177 を下回る」を材料に使った。**診断の S1 を同じ換算値や R8 の β1 と並べて読むと、物差しの違いを効果と取り違える**。
  `report_lines` の S1 の行(`:852-863`)は水準の集合も除外による母集団の違いも書いていない
- **判定には影響しない**(R6)。出力に注記を足すか、S1 を当てる θ の窓を絞るかは人間(後者は記述の行の定義の変更)

#### C105-6【低】R7 の 2 つ目(A と B の対)は項目の同一性だけを見ていて、「和の部分だけを x に置き換えた」ことは run の記録で確かめていない

- `check_pairing`(`:394-409`)は同じプールの `item_id` で突き合わせるので、4 腕が同じプールを読めばほぼ自動で通る。**文面の置き換え**は `data.eval_template_set` の**名前**の照合(`:297-302`)と、プール段階のテスト(`test_diag_sharpness.py:364` の `test_rendered_prompts_differ_only_in_the_sum`)にしか無い
- 掃引の行は描画した `prompt` を持っている(`code/eval/run.py:1907`)ので、判定の時点で「A の prompt = B の prompt の `{a}+{b}`(T3 は `the sum of {a} and {b}`)を `a + b` に置き換えたもの」を記録そのもので確かめられる
- tag と `git_diff.patch` があるので起こりにくい。**足すかどうかは人間**

#### C105-7【低】読み 10 の「R7 の外の止める条件」は判定を黙って変えない(確かめた)。ただし記述の行(R6)の失敗が、判定(R2〜R5)の出力を巻き添えにする

- 追加の止め方はどれも**例外で止まるだけ**で、判定の値を別の値に置き換える経路は無い(`build_report` は全部の検査と計算が済むまで何も出力しない)。**この点は問題なし**
- ただし、R6 のための条件で判定表そのものが出なくなる: 上位 k の欠け(`mass_rows`。`:630-635`)/ トークナイザが読めない(`tokenizer_counter` は `transformers` と、ゲート付きの `meta-llama/Llama-3.1-8B-Instruct` のトークナイザを固定の revision で要する。`:914-918`)。
  合否(R3〜R5)は R6 に依らない(ADR-107 決定3 (iv))ので、**記述が出せないために判定も出ない**という結合になっている
- 例外の型もそろっていない: `r8_fit.sweep_gaps` は `R8FitError`、欄の欠けは `KeyError`(`_pairing_key` の `carry`・`operands`、`token_rows` の `prompt` は `check_records` の必須欄に無い)。止まることは変わらないので実害は小さい
- **誰が決めるか**: 人間(このままでよいかどうか)

#### C105-8【nit】モジュールの docstring の使い方の例(`:7`)に `\n` がある

- `--runs "runs/*_exp_diag_*" \n        --out-dir ...` —— シェルの行継続 `\` のつもりが `\n` になっている。ソースから写したコマンドが壊れる。ANALYST は `STATE.md` の「repo の状態」の行にあるコマンドを使うので実害は小さい

### 確かめて問題が見つからなかったもの(反証を試みた順)

- **R2 の 4 通り**: `delta2_terms()` は `THRESHOLD_RULES` の鍵 (gt, 0)・(gt, +1)・(lt, +1)・(lt, +2)(`t3_comparison.py:73-78`)。閾値は `total + offset`(`threshold_for`)で、掃引の θ = T − t と符号の取り方が同じ。水準は {−2, −1, 0, +1, +2}。テストが 4 通りの並びそのものを縛っている
- **R2 の向き**: 完全な +2 の病変は `P_病変(y = 1 | θ) = P_素(y = 1 | θ − 2)` になるので、固定オフセットの `rule` の上がり幅は `P̂(θ) − P̂(θ − 2)` = D(極性, θ)。R2 の式と実装はこれに一致する
- **`y`**: `r8_fit.aligned_response`(gt で No、lt で Yes が 1。`r8_fit.py:125-138`)。答えは predictions の `answer`(`choose_from_logprobs` の硬い判定。同点は No)
- **`P̂` の分母**: (タスク型 × 既知性)のセル・極性・θ の全項目。R7 の件数の検査(`check_level_counts`)が 160 を強制する。Δ₂ は `Fraction` で 1/640 刻み
- **R3**: `estimate >= Fraction("0.088")`(= 11/125)。線ちょうどは届く(テストが 44/500 と 43/500 で縛る)。3 セルすべて。線を当てる腕は B・A・B-d
- **R4**: `next_stage` は 4 行とも §8.1 の表どおりで、異常の印は「A 届かない・B 届く」だけ。タスク型ごとの鍵の引き方も正しい(ただし C105-1)
- **R5**: T1b の次の段が前段 FT のときだけ当て、B-d が届き B が届かなければ残す。前段 FT の枝では B は必ず届かないので後半の条件は冗長だが、§8.1 の文面どおりである
- **R7 の順序**: `runs_by_arm` → 全腕の `check_level_counts` → 両方の対の `check_pairing` → 計算、の順で、どこで止まっても判定表は出ない(`:708-713`)
- **T < 1 の除外**: `kept_pairs` は `T ≥ 下限`(`>=`)で、生成と run.py の完全性の検査が同じ関数を通る。Δ₂ の 5 水準には掛からない(和の最小 5 → θ = −2 で T ≥ 3)。**掛かっていれば R7 の件数の検査が判定の前に止める**
- **R8・S の不変**: `4837cd4` の diff に `pilot_sweep_r8/`・`pilot_sweep_s/` は無い。items.jsonl の sha256 と manifest の一致はテストが縛る
- **(A) の文面**: `diag_explicit{,_d}.yaml` は R1 の表と一字一句同じ(目で確かめた + テスト)。本番の `t1b.yaml`・`t3.yaml`・`order6b_d.yaml` は変わっていない
- **読み 9**: トークン数の数え方(`model_input` を通し、chat template のときは特殊トークンを足さない)は `forced_choice._score_batch`(`forced_choice.py:553-558`)と同じ
- **事前登録の書き換え**: `4837cd4` は `plans/PLAN-032` のヘッダ・§10・§11 だけを変え、§8.1 には触れていない。凍結 tag(`preregister-diag-sharpness`)はまだ無い

### `AGENTS.md` の CRITIC チェックリスト(この対象に当てはまるものだけ)

- [x] 事前登録した予測が書き換えられていないか → §8.1 は ADR-107 の commit `87e0c7a` の後で変わっていない
- [x] 評価データと FT データの重複 → この診断は FT をしない(素のモデル)。対象外
- [ ] 結果を説明する、より退屈な仮説 → **まだ結果が無い**。ただし C105-2(batch・アダプタ・プールの取り違え)と C105-5(物差しの違い)は、結果が出たときの「退屈な説明」の候補になる
- 数値と run_id の紐づけ・引用・TOST・4 値分解・シード数 → **この対象には実験の数値・引用・主張が無いので当てはまらない**(掃引の項目は設計上 4 値分解に入れない。PLAN-026 §3.2)

### まとめ(人間へ)

- **§8.1 の R2〜R5 の算術と表は、読んだ範囲で正しく実装されている。**判定を黙って変える経路は見つからなかった
- **tag の前に人間が決めること**: C105-3(A-d の役割の文面)/ C105-4(読み 6 の信頼区間)/ C105-2・C105-6・C105-7(R7 の外に止める条件を足すか)/ C105-5(S1 に注記か窓か)
- **IMPLEMENTER に回せば済むもの**(人間が採れば): C105-1(シナリオの追加)/ C105-8(docstring)

---

## 2026-09-26(その108)ADR-108 決定2・3・5〜8 の実装(commit `beb3cf6`)の §8.1 R6・R7 との突き合わせ

- **担当**: CRITIC (Opus 5.5)。**推奨モデル(Opus)と一致**。ADR-101 決定5(統計に触れる diff は CRITIC(Opus)か人間が見る)の対象は決定2(R6 の区間)
- **対象**: `git diff 410f57a..beb3cf6 -- code/analysis/sharpness_fit.py configs/exp_diag_{b,a,b_d,a_d}.yaml code/tests/test_sharpness_fit.py code/tests/test_diag_sharpness.py`(その107。IMPLEMENTER (Sonnet 5))
- **仕様の正本**: `plans/PLAN-032` §8.1 R6・R7 / ADR-108 決定2・3・5〜8 / §11 の注「実装の読み 12〜17」
- **このセッションで回したもの**:
  - `pytest code/tests -q` → **1958 passed**(209.66s。その107 の件数を再現した)
  - scratchpad のスクリプト(repo に置いていない): テストの答え方 `_always_no_except_first_correct(k)` で、**本番の件数(160/水準)の B-d の run を本物の掃引の経路で回し**、`delta2_point`・`per_pair_differences`・`cell_delta2` を読んだ。k = 56・57・1 の 3 セルずつ。**これは合成した答え方に対する関数の出力であって、実験結果ではない**
- **GPU 0・pod 0・tag なし。コード・config・テスト・PLAN・ADR は 1 文字も変えていない**

### 指摘(重い順)

#### C108-1【低〜中・止める条件の残り】R1 の前提の照合は run dir の「宣言」との一致であり、宣言そのもの(と線・件数)が §8.1 の値であることは判定の時点で見ていない

- **何が**: `check_premises`(`sharpness_fit.py:444`)は、run dir の `config.yaml` の `eval.batch_size`・`eval.forced_choice_top_k` と `metrics.json` の `adapter` を、**同じ run dir の `config.yaml` の `sharpness.batch_size / top_k / adapter`** と比べる。線 0.088・`n_per_level` 160 も run dir の `sharpness` 欄から読む(既存。読み 1〜11)。
  宣言が §8.1 の値(null・4・20・0.088・160)と一致することを縛るのは `test_diag_sharpness.py` だけで、それは **repo にコミットした config** を見る。**run dir の写しが tag の commit の config と同じかは `sharpness_fit` は見ない**(`git_sha.txt`・`git_diff.patch` を読まない。`grep -n git_sha code/analysis/sharpness_fit.py` は 0 件)
- **失敗の筋書き**: 4 本とも同じように書き換えた config で回した run(例: 時間を詰めるために 4 腕すべてで `eval.batch_size` と `sharpness.batch_size` を 8 にした)は、4 本の一致も宣言との一致も通るので、**判定表は止まらずに出る**。§8.1 R7 の文面は「`eval.batch_size` が 4 でない」「上位 k が 20 でない」で、宣言ではなく値を名指ししている
- **ADR には沿っている**: ADR-108 決定5 は「照合の相手の値は `sharpness` 欄に置いてよい」とし、読み 12 がその置き方である。**C105-2 が狙った「1 腕だけの取り違え」はこれで止まる**(テスト `test_a_premise_that_disagrees_with_the_record_stops` 7 通りと `test_the_declaration_is_what_the_records_are_compared_with` 3 通り)。残るのは **4 腕そろった書き換え**だけ
- **案(エージェントの案。値や規則は変えない)**: (a) 判定表の先頭に各 run の `git_sha.txt` と `git_diff.patch` の大きさを並べ、tag の commit と違うか、差分が空でなければ止める / (b) run の `sharpness` 欄と `eval` の該当欄を repo の `configs/exp_diag_*.yaml` と照合する / (c) 何もしない(RUNNER の手順 `infra/RUNPOD.md` §4 と run dir の `git_sha.txt` を人間が見る)。(a) は段4 で同じコードを使っても衝突しない
- **誰が決めるか**: 人間(tag の前なら IMPLEMENTER に回せる。何もしないなら、G2-1 の後に判定表を読むときに `git_sha.txt` を人間が確かめる)

#### C108-2【低・テストの穴】R5 が T3 の B の「届く」を読む取り違えを捕まえるシナリオが無い

- **何が**: R5 の呼び出し(`sharpness_fit.py:985-989`)は `reaches[(ARM_B_D, R5_TASK_TYPE)]` と `reaches[(ARM_B, R5_TASK_TYPE)]` を読む。**いまのコードは正しい**(両方とも T1b)。
  しかし T1b の次の段が前段 FT になるシナリオ 3 本(`pre_ft_keep`・`pre_ft_drop`・`split_pre_ft_branch`。`test_sharpness_fit.py:242` ほか)は、**どれも B が T1b・T3 とも `_always_no`** である。R5 の 3 つ目の引数を `(ARM_B, T3)` に取り違えても、どのシナリオでも値は False のままで、**1958 件は通る**
- **なぜ重くないか**: R5 が当たるのは T1b の段が前段 FT のとき = T1b の B が届かないときだけなので、正しい配線では 3 つ目の引数は常に False(C105 の「問題が見つからなかったもの」の R5 の項と同じ)。取り違えが判定を変えるのは「T1b は A・B とも届かず、T3 の B は届く」ときだけで、その組み合わせのシナリオが無い
- **案**: シナリオを 1 つ足す —— `"b": _by_task(t1b=_always_no, t3=_truthful)`・`"a": _always_no`・`"b_d": _truthful`・`"a_d": _always_no`(T1b = 前段 FT・R5 は残す / T3 = 前段 FT は要らない + 異常の印)。これで ADR-108 決定8 (a) の網が R5 の引数にも掛かる
- **誰が決めるか**: 人間が採るかを決め、IMPLEMENTER が足す(tag の前が安い)

#### C108-3【低・実行時の検査】「組ごとの差の平均 = Δ₂ の点推定」を実行時に確かめていない(組の鍵が重なると黙って崩れる)

- **何が**: §8.1 R6 は d_i の「平均は Δ₂ の点推定と一致する」と書く。`per_pair_differences`(`:650`)は組を `tuple(record["operands"])` の辞書の鍵で持ち(`:661`)、同じ (極性, θ) に同じ被演算子の行が 2 つあると**後の行で上書きする**。件数の検査(160 件)と「8 つの (極性, θ) の組の集合が同じ」の検査は、重なりが水準の間でそろっていれば通るので、**n < 160 の区間が、点推定と違いうる中心で、止まらずに出る**
- **いまのプールでは起きない**: セル(タスク型 × 既知性)の中で被演算子の組は重ならない(carry は被演算子で決まり、併合セルの 80 組は相異なる)。本番の件数の run で確かめた —— k = 56・57・1 のどのセルでも **n = 160、平均 = 点推定が有理数で一致**(7/80・57/640・1/640)。**区間の端も §8.1 R6 の式の手計算と一致**(k = 56: [0.068966, 0.106034])
- **テストの側**: `test_the_line_is_crossed_between_56_and_57_over_640`(`test_sharpness_fit.py:1222`)は `low ≤ 点推定 ≤ high` だけを見る。中心が点推定からずれても、幅の中に点推定があれば通る
- **案**: `cell_delta2` で `sum(d_i) / n == estimate`(有理数)と `n == n_per_level` を確かめ、外れたら `SharpnessError`。または `per_pair_differences` で同じ鍵の 2 行目を止める。**合否には触れない**(記述の行の前提の検査)
- **誰が決めるか**: 人間が採るかを決め、IMPLEMENTER

#### C108-4【低・nit】ADR-108 決定7(例外の型のそろえ)に残りがある。止まることは変わらない

- **何が**: 次の経路は `SharpnessError` 以外の型で止まる。**どれも判定表を出す前に止まる**ので判定には影響しない
  - `load_diag_run` の `metrics["threshold_sweep"]`(`:374`)・`DiagRun` の header の `metrics["run_id"]`(`:350`)→ `KeyError`
  - `tokenizer_counter`(`:1150`)の `require` → `ConfigError`、`AutoTokenizer.from_pretrained` → HF の例外(`OSError` など)。**読み 10 は「トークナイザが読めない」を R7 の止める条件に数えている**
  - `main` の `runs[0]`(`:1183`)→ glob が 1 本も当たらないと `IndexError`(`runs_by_arm` より前)
  - `mass_rows`(`:851`)の `"text" not in top_k[0]` → 行が dict でなければ `TypeError`
- **誰が決めるか**: 人間(直すなら IMPLEMENTER。直さなくても止まることは変わらない)

### 観察(指摘ではない。人間が判定表を読むときの材料)

- 上の合成の答え方では、線のすぐ両側の区間は **56/640 → [0.069, 0.106]、57/640 → [0.070, 0.108]** で、**どちらも線 0.088 を含む**(n = 160 の正規近似で幅はおよそ ±0.019)。判定は点推定だけ(ADR-107 決定3 (iv))なので**実装の誤りではない**。本番の結果が線の近くに出たとき、「届く/届かない」が区間の中で決まっていることは R6 の行で見える。**それをどう読むかは人間**(`CLAUDE.md` §8)。**この数値は合成した答え方に対する関数の出力であって、実験結果ではない**

### 問題が見つからなかったもの(反証を試みた)

1. **決定2(R6 の区間。統計)**
   - **計算法は変わっていない**: diff の `confidence_interval`(`:680`)は、切り詰め・`degenerate`・n < 2 の欄を足しただけで、`mean`・`stdev(values) / √n`・`z = inv_cdf(0.5 + level/2)` は旧版と同じ。**§8.1 R6 の式(組ごとの差の正規近似・n = 組の数・z_{0.975})と一致する**(上の手計算)
   - **切り詰めは判定に触れない**: `reaches_line` は有理数の `estimate >= delta2_line`(`:751`)で、`ci` を読まない。d_i ∈ [−1, 1] なので平均も [−1, 1] に入り、切った後も `low ≤ 平均 ≤ high` が保たれる。R3〜R5 の関数(`delta2_point`・`arm_reaches`・`next_stage`・`r5_decision`)は diff に 1 行も無い
   - **退化の判定**: `len(set(differences)) == 1` は `Fraction` のまま比べる(浮動小数の丸めに依らない)。退化のとき標準誤差は 0.0、端は点推定。txt の CI の行に「★退化」、json に `degenerate: true`。**区間を出す箇所は txt の 1 か所(`:1069-1075`)だけで、印なしで `[x, x]` が出る経路は無い**。n < 2 は区間なし・退化でない(§8.1 は n < 2 を定めていない。n は 160 なので実害なし)
   - **退化は本番で起きうる**: 真値どおり・定数の答え方のシナリオでは全セルが退化する(`test_truthful_answers_give_one_and_constant_answers_give_zero`)。本番でも A が完全に真値どおりなら退化の印が出る。**それは印の設計どおり**
2. **決定3(S1 の注記)**: `S1_NOTE` の文言は §8.1 R6 と一字一句同じ。json の `s1_note` と txt の S1 の見出しの直下に出る。S1 の定義(`crossing_rows`)は例外の包みだけで不変
3. **決定5(R1 の前提)と読み 13**
   - `metrics.json` の `forced_choice.top_k` は `declared_top_k(config)` の写し(`run.py:1406`・`:2036`)なので、**照合から外しても失う情報は無い**。行の `top_k` の個数を見るほうが直接の証拠で、§8.1 R7 の「上位 k が 20 でない」と食い違わない(括弧の「config.yaml と metrics.json」に対して、同じ run dir の `predictions/` を足した分だけ厳しい)
   - `metrics.json` の `adapter` は `adapter_provenance` が config の `model.adapter` から組む(`run.py:1266`・`:1289`。パスの文字列か null)。**文字列の宣言と比べられるので、段4 で非 null の宣言を持つ使い方とも噛み合う**(ADR-108 決定5 の理由)
   - `check_premises` は `build_report` の中(`runs_by_arm` の直後・件数と対の検査の前)で呼ばれ、`main` の古いモデルの検査は消えた。`main` のトークナイザは `runs[0]` のモデルで先に読まれるが、モデルが食い違えば `build_report` が止めるので、違うトークナイザの数が出力に載ることは無い
   - `items_sha256` は `task_subset` があってもプールのファイル全体の値(STATE.md の I8 の行)なので、T1b だけを解く B-d・A-d と B・A で比べられる
4. **決定6(文面の置き換え)**: 記録の `prompt` は `render_prompts`(`run.py:265`)の出力を `threshold_sweep_record`(`:1907`)がそのまま書いたもので、chat template の外。和の部分は被演算子と演算子を含む文字列なので、別の場所に偶然現れるには同じ部分がもう 1 つ要る。`count == 1` がそれを止める。**B の文面が壊れた場合(`hello`・`+`→`-`・`the total of`)も A と一致しなくなって止まる**(テスト 6 通り)
5. **決定7**: 包んだのは型だけで、止める条件は減っていない。**判定の値を別の値に置き換える経路は増えていない**(C108-4 の残りも止まる)
6. **決定8(テスト)**: シナリオ 3 つは、A↔B の取り違え(`split_pre_ft_branch` の T3 が異常の印になる)・T1b↔T3 の取り違え・R5 の B-d↔A-d の取り違え(`split_pre_ft_branch` は B-d が届き A-d が届かない)・R3 の all→any(`one_cell_below`)を、それぞれ別の結果として捕まえる。**捕まえないのは C108-2 の 1 つ**。(c) は `cell_delta2`・`arm_reaches` を `build_report` と同じ関数で通しており、読み 17(`build_report` を通さない)で抜けるのは 4 腕の対の検査だけ
7. **事前登録の書き換え**: `beb3cf6` の `plans/PLAN-032` の差分はヘッダ(12 行目)と §10・§11(400 行目以降)だけで、**§8.1(295〜371 行)は `410f57a` の後に変わっていない**。凍結 tag(`preregister-diag-sharpness`)はまだ無い(`git tag -l`)
8. **config 4 本**: 差分は `sharpness:` の 3 欄だけ。値は null・4・20 で、同じ config の `model.adapter: null`・`eval.batch_size: 4`・`eval.forced_choice_top_k: 20` と一致する。dry-run の件数に効く欄は触れていない

### `AGENTS.md` の CRITIC チェックリスト(この対象に当てはまるものだけ)

- [x] 事前登録した予測が書き換えられていないか → §8.1 は不変(上の 7)
- [ ] 結果を説明する、より退屈な仮説 → **まだ結果が無い**。C108-1(4 腕そろった設定の書き換え)は、結果が出たときの「退屈な説明」の候補になる。線の近くの判定が区間の中で決まること(観察)も同じ
- 数値と run_id の紐づけ・引用・TOST・4 値分解・シード数 → **この対象には実験の数値・引用・主張が無いので当てはまらない**(ここに出る数値は、テストの答え方に対する関数の出力と config の値)

### まとめ(人間へ)

- **決定2(R6 の区間)の diff は §8.1 R6 どおり**: 計算法は変わっておらず、切り詰めと退化の印は判定(点推定)に触れない。本番の件数の合成の run で、平均 = 点推定・区間 = 手計算を確かめた
- **判定を黙って変える経路は見つからなかった**。R2〜R5 の関数は diff に無い
- **tag の前に人間が決めること**: C108-1(4 腕そろった書き換えを判定の時点で止めるか。案 (a) `git_sha.txt` の照合 / (b) repo の config との照合 / (c) 何もしない)
- **IMPLEMENTER に回せば済むもの**(人間が採れば): C108-2(シナリオ 1 つ)/ C108-3(平均 = 点推定の実行時の検査)/ C108-4(例外の型の残り)
- どれも採らない場合でも、**凍結 tag を止める誤りは見つからなかった**(採否は人間。`CLAUDE.md` §8)

## 2026-09-26(その111)凍結 tag(案 `preregister-diag-sharpness`)が固めるもの —— `ef582f1` の §8.1 R7・ADR-109 決定1・2 の実装・tag の運用の突き合わせ

- **担当**: CRITIC (Opus 5.5)。**推奨モデル(Opus)と一致**。`logs/HANDOFF.md`(その110)の A(任意。ADR-109 決定4)を人間が選んだ(「critic として tag の内容を分析」)
- **対象**: tag を打つ予定の commit `ef582f1` の中身のうち、§8.1 R7 の 4 つ目(ADR-109 決定1)・`git diff 76402e1 ef582f1 -- code/analysis/sharpness_fit.py`(`check_provenance`・`check_pair_differences`・例外の型)・tag と run と判定表を結ぶ運用(`code/artifacts.py` の `write_git_sha`・`infra/preflight.py` の `check_git_clean`・`infra/RUNPOD.md`・既存の tag)
- **仕様の正本**: `plans/PLAN-032` §8.1 R6・R7・§8.2 / ADR-109 / §11 の注「実装の読み 18〜25」
- **このセッションで回したもの**(すべて読み取りか scratchpad の中。**repo のファイルは書き換えていない**):
  - `pytest code/tests -q` → **1991 passed(377.49s。その110 の件数を再現)**
  - **scratchpad に `git clone` した `ef582f1` の写し**(ポッドの手順の再現。repo の作業ツリーではない):
    (i) `configs/exp_diag_pool.yaml` の冒頭の生成コマンド(`sweep_pool --arm diag`)→ `git status --porcelain` は空・`git diff HEAD` は 0 バイト /
    (ii) `configs/exp_order6b_pilot.yaml` の冒頭の生成コマンド(`ft_data` 5 条件 → `eval_pool`)→ **追跡ファイル 5 本(`data/generated/ft/exp_order6b_pilot_*/manifest.json`)が変わり、`git diff HEAD` は 3,380 バイト**(`created_at`・`git_commit` 以外の行は動いていない)/
    (iii) 追跡外の `configs/exp_diag_b_pod.yaml`(`delta2_line: 0.05` に書き換えた写し)を置く → `git diff HEAD` は 0 バイト /
    (iv) 作業ツリーが clean のときの `write_git_sha` → `dirty: false`・`git_diff.patch` なし。
    **どれも手順の再現であって実験結果ではない**。clone は scratchpad にだけある
  - 既存の run の `git_sha.txt`・`git_diff.patch` と既存の tag の commit の照合、`git ls-remote origin`
- **GPU 0・pod 0・tag なし。コード・config・テスト・PLAN・ADR は 1 文字も変えていない**

### 指摘(重い順)

#### C111-1【中・GPU の前の門が無い】R7 の 4(`git_diff.patch` が 0 バイトでなければ止める)は GPU の後にしか効かず、前で同じ条件を見る門が無い

- **何が**: ADR-109 決定1 で「追跡ファイルの差分がある run」は判定表の時点で**必ず止まる**ようになった(`sharpness_fit.py:539` の `check_provenance`)。差分は run の開始時に `write_git_sha`(`code/eval/run.py:2116`・`code/artifacts.py:231`)が記録するので、**止まった後に解析を回し直しても直らない。4 腕を GPU で回し直す**しかない(ADR-109 の「決定1 の代価」)。
  ところが**run の前にこの条件で止める門は無い**: `infra/preflight.py:250` の `check_git_clean` は **WARN** で、追跡外のファイルと追跡ファイルの差分を区別しない(`git status --porcelain`)。ポッドでは追跡外のファイルが常にあるので**毎回 WARN が出る**(既存の run は全部 `dirty: true`)。`run.py` は差分を記録するだけで止めない
- **失敗の筋書き(再現した)**: I5(R8。アダプタの固定オフセットの T1b・T3)にはパイロット用プールの `items.jsonl` が要り、`configs/exp_order6b_pilot.yaml` の冒頭の手順(`ft_data` → `eval_pool`)で作り直す。**これを診断の 4 腕より先にポッドで回すと、追跡ファイルの manifest 5 本の `created_at`・`git_commit` が動き、`git diff HEAD` が 3,380 バイトになる**(scratchpad の clone で再現。上の (ii))。
  `git checkout -- data/generated` で戻す手順は `infra/RUNPOD.md:329` にあるが、**「順1b の手順」の節の中**であり、診断の手順ではない。戻し忘れた状態で 4 腕を回すと、preflight は普段どおり WARN を出して通り、GPU の後に判定表が 4 腕とも止まる。
  **同じ止まり方の別の入口**: `_capture`(`code/artifacts.py:218`)は stdout と stderr を連結して `git_diff.patch` に書くので、`git diff HEAD` が警告を stderr に出す環境では、差分が空でも patch が 0 バイトにならない(既存のポッドの run では起きていない。起きれば同じく GPU の後に止まる)
- **判定を黙って変える経路ではない**(止まる側に倒れる)。代価が GPU であることだけが問題
- **案(エージェントの案。§8.1 は変えない)**:
  (a) `run.py` の掃引の経路で、config に `sharpness:` 欄がある run は、**run dir を作る前・重みを読む前**に `git diff HEAD` が空でなければ止める(R7 の 4 と同じ条件を同じ関数の形で前にも置く)/
  (b) preflight に「追跡ファイルの差分」の検査を分けて足し、診断の run では FAIL にする(追跡外は見ない)/
  (c) 手順だけ: RUNNER は各腕の直前に `git status --porcelain --untracked-files=no` が空であることを確かめ、I5 のプールの作り直しの後は `git checkout -- data/generated` を必ず通す
- **推奨**: (a)。§8.1 R7 は機械的に止めるので、同じ条件を GPU の前にも置くのが最も安い。**tag の前に入れる**(tag の後にコードを変えると C111-2 の比べ方がさらに難しくなる)
- **誰が決めるか**: 人間(採れば IMPLEMENTER)

#### C111-2【中・比べ方が決まっていない】「判定表の先頭の sha を tag の commit と見比べる」の基準が無く、過去の運用では sha は tag の commit と一致していない

- **何が**: §8.1 R7(`plans/PLAN-032:361`)と ADR-109 決定1 は「その sha を判定表の先頭に出す。tag の commit と見比べるのは人間」で止まっており、**一致を求めるのか、tag の子孫で特定のパスに差分が無ければよいのかが書かれていない**
- **過去の事実**: `preregister-order6b` の tag は `e714f8a`、順6b の 7 本は `b5838c0`(tag の 2 commit 後。`code/`・`configs/` の差分は無い)。`preregister-pilot-ft` の tag は `37346bf` で、1 回目の評価は同じ `37346bf`、回し直し(313)は `cbe76ce`(ADR-104。新しい tag は打っていない)。**「tag の commit と一致」を基準にすると、順6b は外れる**
- **今回も外れる見込みが高い**: §6 罠1(`plans/PLAN-032:272`)は「I5 の config は tag の後に作ってもよい」。tag → I5 の config の commit → ポッド、の順になると、4 腕は tag より後の commit(`configs/` に差分あり)で回る。**そのとき受け入れるかを、人間が判定表を見た後に決めることになる**(結果を見た後の判断の余地。小さいが事前登録の趣旨に反する)
- **案**:
  (a) **4 腕は tag の commit そのもので回す**(ポッドで tag を checkout してから 4 腕を続けて回し、I5 はその後に新しい commit で回す。bundle で渡すなら `git bundle create ft.bundle main preregister-diag-sharpness` のように tag を含める)。人間の比べ方は「一致」になる /
  (b) tag の前に基準を書く: 「tag が sha の祖先であり、`git diff <tag> <sha> -- code/ configs/ data/generated/ infra/` が空」。RUNNER の手順(と、要るなら §8.1 R7 の注)に置く /
  (c) このまま(判定表を読むときに人間が決める)
- **推奨**: (a)(比べ方が一致になり、判断の余地が消える)。(a) が運用で守れなかったときの予備として (b) の文面も tag の前に置く
- **誰が決めるか**: 人間

#### C111-3【中・来歴の片側】判定表の先頭の sha は「run の commit」であり、判定を当てた解析コードの commit は記録されない

- **何が**: R2〜R5 の規則のうち、線・差の幅・件数は run の config の `sharpness` 欄から読むが、**Δ₂ の 4 項(`THRESHOLD_RULES`)・「3 セルすべて」・R4 の表・R5 はコードにある**(`sharpness_fit.py` と、それが読む `r8_fit`・`t3_comparison`・`gonogo`)。
  判定表は ANALYST が手元で**後から**回す(`main`。`sharpness_fit.py:1287`)が、そのときの `git rev-parse HEAD` と作業ツリーの差分はどこにも残らない。json の `commit_sha`(`:1091`)と txt の最初の行は run 側の sha である
- **失敗の筋書き**: tag の後に `sharpness_fit.py` を直した(または作業ツリーで書き換えた)状態で判定表を出しても、先頭の sha は tag と一致し、**「凍結したコードで判定した」と読める**。事前登録が守りたいのは「データを見る前に規則を固めた」ことで、その規則の半分はコード側にある
- **案**:
  (a) 判定表に解析側の来歴を 1 行足す(`analysis_commit_sha` = 解析時の `git rev-parse HEAD` と、`git diff HEAD -- code/` が空かどうか。**止めずに表示だけ** —— 段4 で同じコードを別の tag で使っても衝突しない)/
  (b) 手順だけ: ANALYST は tag を checkout して判定表を出す /
  (c) 人間が読むときに `git log <tag>..<判定表の commit> -- code/analysis/ code/eval/battery/` を見る
- **推奨**: (a)(小さい変更で、読む人が 2 つの sha を並べて見られる)+ 読むときに (c)
- **誰が決めるか**: 人間(採れば IMPLEMENTER。tag の前が安い)

#### C111-4【低〜中・事前登録の証拠力】凍結 tag は手元にしか無く、外部の時刻の裏付けが無い

- **何が**: `git ls-remote origin` は `refs/heads/main` = `6bcddca`(2026-09-12)だけを返し、**tag は 1 つも無い**。`preregister-order6b`・`preregister-pilot-ft` はどちらも `origin/main` から辿れない。`CLAUDE.md` §5 は tag で「予測が実験前に書かれた」ことが証明できるとするが、**手元の tag の日時と commit の日時は後から作り直せる**ので、第三者に対する証拠にはならない
- **ADR の範囲**: ADR-073 決定3 は順5 のために main を `origin` へ push することを認めた(コードの渡し方として)。**tag の push と、その時期(GPU の前)を決めた ADR は無い**
- **案**: (a) G2-1 の GPU の前に main と `preregister-*` の tag を `origin` へ push する(GitHub 側に時刻が残る。外部へ送る操作なので人間が打つ)/ (b) 論文の段(Phase 1 の凍結)でまとめて外部の事前登録(OSF など)に出し、段2 は手元の tag のままにする / (c) 何もしない
- **推奨**: (a)。今回の tag は段4 まで効く線(R9)を固めるので、段4 の論拠にもなる
- **誰が決めるか**: 人間(push はエージェントがしない)

#### C111-5【低・ADR-109 の前提の穴】「同じ commit で差分なし ⇒ run dir の config はその commit の config」は、`--config` が追跡外のファイルだと成り立たない

- **何が**: ADR-109 決定1 の理由(`logs/DECISIONS.md:6978`)は「4 本が同じ commit で追跡ファイルの変更なしに回ったなら、run dir の `config.yaml` の写しはその commit の config」。しかし `write_config_copy`(`code/artifacts.py:221`)は `--config` に渡されたファイルをそのまま写し、**そのパスは記録されない**。`git diff HEAD` は追跡外のファイルを見ない
- **再現**: scratchpad の clone で、追跡外の `configs/exp_diag_b_pod.yaml`(`delta2_line: 0.05`)を置いても `git diff HEAD` は 0 バイト(上の (iii))。4 腕とも同じように書き換えた追跡外の config で回すと、R7 の 3(宣言との一致)も 4(出どころ)も通り、判定表は線 0.05 で出る
- **重くない理由**: 判定表の txt は `線 = …`・件数・adapter・batch・上位 k の値を表示する(`report_lines`。`sharpness_fit.py:1149` 以降)ので、読む人が §8.1 の値と見比べれば気づく。RUNNER の手順は repo の config を使う
- **案**: (a) `sharpness_fit` が各 run の `config.yaml` を `git show <commit_sha>:configs/exp_diag_<腕>.yaml` と照合する(**記録された sha の中の config と比べるので、ADR-109 が却下した (b)「動く repo の config と照合」とは違う**。段4 では config の名前が変わるので、パスは引数にする)/ (b) `run.py` が `--config` のパスと、それが追跡ファイルかを記録する / (c) 何もしない(判定表を読むときに、表示された値を §8.1 と見比べる項目を手順に 1 行置く)
- **推奨**: (c)。値は表に出ており、(a)・(b) は段4 での使い回しの設計が要る
- **誰が決めるか**: 人間

#### C111-6【低・結果を見た後の選択の余地】同じ腕に完了した run が 2 本あるとき、どちらを使うかが §8.1 に無い

- **何が**: ADR-109 のリスク欄は「コードを変えずに同じ commit で回し直すなら止まらない」とする。しかし glob(`runs/*_exp_diag_*`)は完了した run(`metrics.json` がある)を全部拾い、同じ腕が 2 本あると `runs_by_arm`(`sharpness_fit.py:436`)で止まる。**どちらを残すかは、2 本の中身を見た後に人間か RUNNER が選ぶことになる**。batch 4 の近接同点は回すたびに揺れうる(ADR-078 決定10)ので、2 本の判定が同じとは限らない。(途中で落ちた run は `metrics.json` が無いので glob に当たらない。`aggregate.expand_metrics_paths`)
- **案**: (a) tag の前に規則を置く: 「腕ごとに最初に完了した run(`run_id` の時刻が早いほう)を使い、ほかの完了した run は判定表の注に Δ₂ を並べる」/ (b) 完了した run がすべて同じ判定を出すことを求め、割れたら止める / (c) このまま
- **推奨**: (a)(RUNNER の手順か §8.1 R7 の注に 1 行)
- **誰が決めるか**: 人間

### 観察(指摘ではない)

- **`check_pair_differences` の「平均 = 点推定」は、`build_report` の経路では恒等式で、落ちることが無い**。`check_level_counts`(`:1038`)が先に (タスク型 × 既知性 × 極性 × θ) ごとに件数 = `n_per_level` を確かめ、同じ分け方の `cell_delta2` で組の数 = `n_per_level` が通れば、各 (極性, θ) の行と組は 1 対 1 になり、組ごとの差の平均は Δ₂ と代数的に一致する。**経路の上で実際に効くのは組の数の検査のほう**(同じ被演算子の行がどの水準にも 1 つずつ重なる場合を止める)。平均の検査は `cell_delta2` を直接呼ぶ経路(読み 17)の守りである。誤りではないが、追加の守りとして数えない
- `check_provenance` の sha は run の開始時(重みを読む前)に書かれる(`run.py:2116`)ので、生成の途中の checkout には影響されない

### 問題が見つからなかったもの(反証を試みた)

- **`check_provenance` の分岐**: 4 本とも sha が無い・一部が無い・sha が 2 種類以上 → どれも問題の一覧に入り、まとめて 1 つの `SharpnessError`。問題が無いときだけ `next(iter(recorded))` に届き、そのとき `recorded` はちょうど 1 要素。`build_report` の中(`check_premises` の直後)なので CLI も直接呼ぶ経路も通る
- **sha の書式(読み 18)**: `fullmatch` で 16 進 40 桁か 64 桁。`strip()` で CR を落とす。git の失敗の文言は通らない
- **pod の実物の形で通る**: 順6b の B0(`b5838c0`)・パイロット FT の評価(`37346bf`・`cbe76ce`)の `git_sha.txt` は 1 行目が 40 桁の 16 進・`dirty: true`・`git_diff.patch` は 0 バイト。clean な作業ツリーでの `write_git_sha` は `dirty: false`・patch なしで、こちらも通る
- **診断のプールを作り直しても R7 の 4 には掛からない**: `ef582f1` の clone で `exp_diag_pool.yaml` の冒頭のコマンドを回すと、追跡ファイルは 1 つも変わらない(manifest は時刻・パスを持たず決定的。`items.jsonl` の sha256 は追跡している manifest の `files` が縛る)
- **判定の値を変える経路は増えていない**: diff の中で R2〜R5 の関数(`delta2_point`・`arm_reaches`・`next_stage`・`r5_decision`)と `confidence_interval` の定義は変わっていない。`cell_delta2` の区間は、同じ `differences` を変数で使い回しただけ
- **§8.1 は ADR-109(`c81b288`)の後で不変**: `git diff c81b288 ef582f1 -- plans/PLAN-032` の変更はヘッダ・§10・§11 だけ(§8.1 は 295〜373 行)。tag はまだ無い
- json の最初の鍵が `commit_sha`(dict の挿入順)・txt の最初の行が `commit: …`

### `AGENTS.md` の CRITIC チェックリスト(この対象に当てはまるものだけ)

- [x] 事前登録した予測が実験後に書き換えられていないか → **まだ実験前**。§8.1 は `c81b288` の後で不変。ただし「凍結した」ことを外部に示す手段が無い(C111-4)と、判定の時点のコードが記録されない(C111-3)
- [x] 結果を説明する、より退屈な仮説 → 判定表が止まったときの退屈な原因(プールの作り直しの manifest の時刻)を再現した(C111-1)
- 数値・引用・同等性検定・シード数・4 値分解は、この対象(判定を固める tag)には当たらない(判定表は二値群の 4 値分解に入れない = PLAN-032 §8.1 R1)

### まとめ(人間へ)

- **tag を止める誤りは見つからなかった**。§8.1 R1〜R9 は ADR-109 の後で変わっておらず、ADR-109 決定1・2 の実装は R7 どおりで、判定の値を変える経路は増えていない
- **tag の前に決めると安いもの**: C111-1(GPU の前の門。推奨 (a) = IMPLEMENTER)/ C111-2(tag と run の比べ方。推奨 (a) = 4 腕は tag の commit で回す)/ C111-3(解析側の sha。推奨 (a) = IMPLEMENTER)/ C111-6(完了した run が 2 本のとき。推奨 (a) = 1 行)
- **tag の後でもよいが GPU の前に**: C111-4(tag の push。推奨 (a) = 人間が push)
- **何もしなくてよいと考えるもの**: C111-5(推奨 (c)。表の値を読むときに見比べる)
- C111-1・C111-3 をコードで入れるなら IMPLEMENTER のセッションがもう 1 回要り、tag はその後になる。**入れずに tag を打つなら、C111-1 は (c) の手順を RUNNER に渡すことが最低限**
