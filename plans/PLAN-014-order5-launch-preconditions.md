# PLAN-014: 順5(桁数掃引 → `M*`)を起動するために残っているもの

> プランファイルは**実装より先に書く**。仕様がここに書かれていないものは実装しない。
> **この文書は実験プランではない。**`plans/TEMPLATE.md` の §2(予測)/ §3(実験条件)は
> 該当しない —— 順5 は素のモデルの算術能力の**実測**であって病変の実験ではない
> (`code/eval/sweep.py` の docstring / PLAN-001 §4.1.1 の手続き2)。

- 作成日: 2026-09-06
- 最終更新: 2026-09-06
- ステータス: `レビュー済`(**2026-09-06。§4 の 4 件は ADR-057 で全件決着。**
  帰結の実装も完了した —— config の記入 / `infra/preflight.py` の `RunKind` /
  `infra/RUNPOD.md` §3 の例外。**残るのは §5 の実行(RUNNER)だけである**)
- 担当: PLANNER(起草)→ **人間**(§4 の決定)→ RUNNER(§5 の実行)
- 関連する問い: `Documents/03_OPEN_QUESTIONS.md` Q-1 / 承認待ち #15(`M*`)
- 由来: 2026-09-06(その6)のセッションで、人間が `logs/HANDOFF.md` の **B(順5 の GPU 承認)**を
  選んだ。**承認そのものは下りている。**着手しようとして、config とコードの実地確認から
  **未決が 4 件と手順の矛盾が 1 件**見つかったので、それを 1 箇所にまとめる。

---

## 1. この PLAN が答える問い

**「順5 を実際に起動するには、あと何が要るのか。」**

**GPU 承認は要件の 1 つでしかなかった。**残りは §4 にある。

---

## 2. 実地で確認した事実(2026-09-06。推測ではない)

**すべてこのセッションで実行して得た。**文書からの転記ではない。

| 記号 | 事実 | 確認の仕方 |
|---|---|---|
| **F18** | `pytest code/tests -q` → **808 passed**。`git status` クリーン @ `fb9065f` | 実行した |
| **F19** | 本番 config に対する `preflight.py` は**ローカルで FAIL 3 件**: `format hash`(`eval.anchor_manifest` が null)/ `coverage_k floor`(`eval.cells` が null)/ `token boundaries`(gated repo に未認証。**ポッド上で `huggingface-cli login` 後は解消する見込み**) | 実行した |
| **F20** | **`code/eval/sweep.py` は `eval.reference_rule` と `eval.elicitation` を `require` する**(`:302`, `:303`)。本番 config はどちらも **null**。**現状の `configs/exp_phase1_main.yaml` では `ConfigError` で止まり、1 項目も生成しない** | コードと config を読んだ |
| **F21** | `resources.min_vram_gb` / `gpu_type` / `estimated_gpu_hours` / `human_approval_date` の **4 欄が null**。`preflight.py` の GPU 検査の閾値と、`infra/RUNPOD.md` §7 の課金記録がこの欄を使う | config を読んだ |
| **F22** | **preflight の `forced choice tokens` は SKIP になる**(`eval.batteries` が null で `comparison` が宣言されていない)。**`logs/HANDOFF.md` の B は「WARN / FAIL を出したら人間に上げて止まる」と書いているが、この config では検査そのものが走らない** | 実行した(SKIP を確認) |
| **F23** | **掃引は評価プールを使わない。**項目は `code/eval/battery/magnitude_sweep.py` の `build_items` がその場で作る(`eval.magnitude_sweep.radii` × `n_items_per_radius` × `seeds`)。**`eval.pool_items` / `cells` / `anchor_manifest` を 1 つも読まない** | コードを読んだ |
| **F24** | `model.revision` = `0e9e39f249a16976918f6564b8830bc894c89659`(HANDOFF の値と一致)。`model.adapter: null`(掃引が要求する状態。`reject_declared_adapter`)。`eval.magnitude_sweep` は 3 欄とも確定値が入っている(`radii` 13 水準 / `n_items_per_radius: 200` / `seeds: [0,1,2,3,4]`。ADR-041 決定5 / PLAN-006) | config を読んだ |

---

## 3. ★手順の矛盾(これが本体)

**F19 の FAIL 2 件は、順5 の出力を待っている。**

```
順5(桁数掃引)
  -> M* を人間が決める(ADR-041 決定3 の規則)
    -> eval.extrapolation_radius に入る
      -> eval.cells / anchor_manifest / pool_items が埋まる(B5)
        -> preflight の 検査6(format hash)と 検査8(coverage_k floor)が PASS になる
          -> 順4 第3条件が閉じる
```

一方 `infra/RUNPOD.md` §3 は例外なしにこう書いている。

> **preflight が通らないまま本実行しない。**

> `FAIL が1件でもあれば本実行を開始しない`

**規則をそのまま読むと、順5 は永久に起動できない。**

`plans/PLAN-004-phase0-route.md` §2 の 2026-09-06 追記は
「**順4 は順5 をまたいで閉じる**」と既にこの非線形性を書いているが、
**`infra/RUNPOD.md` §3 の側にその例外が無い。**記述が 2 箇所で食い違っている。

**★そして F23 が、この矛盾は見かけだけであることを示している** ——
検査6 と検査8 は**評価プールの整合性**を見る検査であり、
**掃引 run は評価プールを 1 行も読まない。**
掃引にとって、この 2 つの FAIL は**測定対象の外にある。**

**ただし「見かけだけだ」と判断して回すのは手順の変更であり、人間が決める**
(`CLAUDE.md` §8 / §2「エージェントが合否基準を動かさない」)。

---

## 4. ★人間が決める 4 件

**エージェントは案を出す。決定・確定は人間が行う**(`CLAUDE.md` §8 / ADR-039 決定3)。

### D-A. 本番 config の 2 欄を埋めてよいか(F20)

> **★2026-09-06 決着(ADR-057 決定1)。採択 = 人間 / 提案 = PLANNER。**
> **本番 config に書く。**`eval.reference_rule: p2` / `eval.elicitation: direct`。
> **新しい決定ではない** —— どちらも 2026-08-22 に人間が承認済で、転記されていなかっただけ。
> **記入済**(`configs/exp_phase1_main.yaml`。2026-09-06)。
> 不採択: 掃引専用 config を別に作る / 保留。

**掃引が `require` する 2 欄である。**どちらも**値は既に別の場所で決まっており、
config に転記されていないだけ**に見える。**その読みが正しいかを人間が確認する。**

| 欄 | 提案する値 | 出所(エージェントの意見ではない) |
|---|---|---|
| `eval.reference_rule` | **`p2`** | **2026-08-22 に人間が承認済**(`STATE.md`「解決済み」の #3「`rule_rate` を固定参照規則に対して定義するか」→ **承認。主要評価項目では参照規則 = `p2`**。ADR-016)/ `Documents/05_STATISTICS.md` §2「解析対象: **`p2` 条件のみ**」/ **掃引の採点は主要参照規則の 1 ブロックだけ**(PLAN-004 §3 順1 の独断 #11) |
| `eval.elicitation` | **`direct`** | **2026-08-22 に人間が承認済**(`STATE.md`「解決済み」の #6「主要評価項目を `elicitation = direct` に固定してよいか」→ **承認。CoT 側は副次的評価項目**)/ PLAN-001 §5.5 |

**★この 2 件は「新しい決定」ではない。**どちらも **2026-08-22 に人間が承認した項目**であり、
**config に転記されていないだけである。**人間に問うのは
**「この読みで合っているか」と「いま書いてよいか」の 2 点だけである。**

**★注意点 2 つ(隠さない)**:

- どちらも **`[MATCHED]` 欄**である。書けば **40 run 全体の設計値が 1 つ確定する。**
  掃引のためだけの一時的な記入ではない
- **`correct_rate` は参照規則に依存しない**(`code/eval/sweep.py` の docstring)。
  したがって **`M*` の決定に `reference_rule` の値は効かない。**
  それでも `require` されるのは、4 値分解を 4 つ揃えて出すためである(`CLAUDE.md` §6)

### D-B. 掃引 run の GPU 構成(F21)

> **★2026-09-06 決着(ADR-057 決定2)。採択 = 人間 / 提案 = PLANNER。**
> **外側。**掃引の GPU 構成は本実験 40 run と**独立に**選ぶ。
> 根拠: 掃引は素の重みへの推論のみでアダプタを読まない(`reject_declared_adapter`)。
> **記入済**: `min_vram_gb: 23.9` / `gpu_type: "NVIDIA GeForce RTX 4090"` /
> `estimated_gpu_hours: 1.5`(**見積もり。実測ではない**)/ `human_approval_date: 2026-09-06`。
> **`resources` に「これは順5 の構成であって本実験の凍結値ではない」と注記を入れた。**
> **★帰結として人間待ちが 1 件開いた**: **Phase 1 本実験 40 run の GPU 構成**
> (`train.*` のハイパラ = ADR-043 決定10 と同じ場で決まる)。
> **★リスク**: GPU / 数値精度が `correct_rate` を動かすなら `M*` も動きうる。

`resources` の 4 欄。**`infra/RUNPOD.md` §6 は「全条件・全シードを同一 GPU 構成で」と定めている。**
問うべきは「**掃引はその拘束の内側か外側か**」である。

- **内側だと読む場合**: `gpu_type` を書いた時点で **Phase 1 本実験 40 run の GPU が決まる。**
  しかし **`train.*` のハイパラが未決**(ADR-043 決定10)なので、8B の LoRA 訓練が
  どの VRAM で回るかはまだ言えない。**訓練側の要件を知らないまま推論側の都合で決めることになる**
- **外側だと読む場合**: 掃引は素の重みに対する推論のみで、アダプタを読まない
  (`reject_declared_adapter`)。**訓練の GPU 要件と独立に選べる。**
  ただし **`M*` は `correct_rate` の閾値越えで決まる**ので、
  GPU / 数値精度が `correct_rate` を動かすなら `M*` も動きうる。
  **崖の近傍で動けば `D_ext` の中身が変わる**

**先例(決定ではない)**: 順1b は `min_vram_gb: 23.9` / `gpu_type: "NVIDIA GeForce RTX 4090"` /
`estimated_gpu_hours: 1.0` で回した(`configs/smoke1b.yaml`。2026-08-28 の実測に合わせた閾値)。

**GPU 時間の見積もり(★実測ではない。見積もりである。`CLAUDE.md` §2)**:
13 水準 × 5 抽出シード × 200 項目 = **13,000 項目**。
順1b の実測 **0.276 秒/項目**(batch 4。`[run:20260828_095717_smoke1b]`)を当てると
生成だけで約 **1.0 時間**、重み読み込みを足して **1.0〜1.5 GPU時間**。
**10 GPU時間の承認ゲート(`CLAUDE.md` §2)は超えない。**
ただし順1b の秒数は 19 項目の測定であり、**掃引の項目(裸の和、長い被演算子)で同じとは限らない。**

`human_approval_date` は **2026-09-06**(本セッションで人間が承認した日)。

### D-C. preflight の FAIL 2 件を抱えたまま順5 を回すか(§3 の矛盾)

> **★2026-09-06 決着(ADR-057 決定3)。採択 = 人間 / 提案 = PLANNER。**
> **案 1。**`infra/preflight.py` に `RunKind`(`main` / `sweep`)を入れ、
> 掃引 run では `format hash` / `coverage_k floor` を SKIP にする。**既定は `main`。**
> **実装済**(commit `c4c04df`。回帰テスト 3 件。`pytest` 811 passed)。
> **`infra/RUNPOD.md` §3 に「run 種別の例外」を書き、§4 手順 5b に `--run-kind sweep` を足した**
> (2026-09-06)。**実機で確認**: 本番 config に `--run-kind sweep` で当該 2 件が SKIP になり、
> **残る FAIL は `token boundaries` の 1 件だけ**(gated repo に未認証。
> ポッド上の `huggingface-cli login` で解消する見込み。**未検証**)。
> 不採択: 案 2(FAIL のまま回す)/ 案 3(暫定値で FAIL を消す)。

| 案 | 内容 | 代償 |
|---|---|---|
| **1** | **`infra/RUNPOD.md` §3 に run 種別の例外を書き、`preflight.py` に反映する。**掃引 run では検査6・検査8 を「対象が存在しない」= SKIP とする(F23 が根拠) | **実装が要る**(小)。preflight に run 種別の引数が増える。**規則が明文化されるので前例が濁らない** |
| **2** | **文書は変えず、掃引だけ FAIL を承知で回す。**回した事実と理由を `runs/<id>/` と ADR に残す | 実装 0。**ただし「FAIL でも回してよい場合がある」という前例ができ、§3 の抑止力が下がる** |
| **3** | `eval.cells` / `anchor_manifest` に**暫定値**を入れて FAIL を消す | **推奨しない**(エージェントの意見)。暫定値が本番値と混ざる穴は `eval.pool_items` で既に 1 つ開いている(ADR-033 決定4「**暫定である**」)。**同じ穴を 2 つに増やす** |

**★案 1 と案 2 は「いま何を測るか」を変えない。**変わるのは記録の残り方だけである。

### D-D. HANDOFF が順5 の前提に置いた 2 件の宛先(F22)

> **★2026-09-06 決着(ADR-057 決定4)。採択 = 人間 / 提案 = PLANNER。**
> **順6 に移す。**バッチ fp ノイズ検査(ADR-040 決定7)と preflight の
> `forced choice tokens` は、どちらも `comparison` 群(= 評価プール)を要求する。
> **掃引は `comparison` を回さない**(F23)ので、順5 の前提にはならない。
> **`logs/HANDOFF.md` の順6 の前提に移した**(2026-09-06)。
> **`ADR-044`(`requirements.lock` の凍結)は順5 のままである。**

`logs/HANDOFF.md` の B は順5 の前に次の 2 件を求めている。**どちらも現状の config では成立しない。**

| 前提 | なぜ成立しないか | 提案 |
|---|---|---|
| **バッチ fp ノイズ検査**(`comparison` 群でバッチ1 対 バッチ N の `parsed` 一致。ADR-040 決定7) | `comparison` 群は**評価プール**の項目を使う。`eval.batteries` / `pool_items` が null なので群が空になる。**掃引は `comparison` を回さない**(F23) | **順6 に移す。**ADR-040 決定7 の原文は「**段階 C の本番でもプールの部分集合 100 項目で**」であり、**プールを使う段 = 順6 を指していると読める** |
| **preflight の `forced choice tokens`** | `eval.batteries` に `comparison` が無いので **SKIP**(F22)。**WARN / FAIL は原理的に出ない** | **同上、順6 に移す。**ただし **`infra/RUNPOD.md` §3 は「重みは読まないので GPU を借りる前に確かめられる」**と書いており、**`comparison` を宣言した config さえあればローカルで先に取れる。**取っておくかは人間が決める |

**★これは HANDOFF の記述の誤りであって、設計の誤りではない。**
前セッションが順5 と順6 の前提を 1 つの箱に入れていた。

**★ADR-044(`infra/requirements.lock` の凍結)は順5 のままでよい。**
ポッド上の `pip freeze` を取るだけで、config の未決に依存しない。

---

## 5. 決まった後の実行手順(RUNNER)

**`infra/RUNPOD.md` §4 の手順 5b が正本。**下はそれを順5 に当てた写しである。
**§4 の必須成果物(`runs/<id>/` に残すもの)は変更しない。**

```bash
# ---- 1. ポッド上の準備 ----------------------------------------------------
cd /workspace && git clone <repo> translesion || (cd translesion && git pull)
cd translesion
bash infra/bootstrap.sh
huggingface-cli login          # ★人間が実行する。エージェントは認証情報を入力しない

# ---- 2. revision の照合(★一致しなければ止まって人間に上げる)-------------
#     configs/exp_phase1_main.yaml の model.revision は
#     0e9e39f249a16976918f6564b8830bc894c89659 である(F24)。
#     snapshots/ の直下のディレクトリ名がコミットハッシュである(RUNPOD.md §4 の段2)。

# ---- 2b. ADR-044。requirements.lock を実機の環境に凍結する -----------------
pip freeze > infra/requirements.lock

# ---- 3. 事前検証 -----------------------------------------------------------
RUN_S=runs/$(date -u +%Y%m%d_%H%M%S)_sweep_m
python infra/preflight.py --config configs/exp_phase1_main.yaml --run-dir "$RUN_S" --run-kind sweep
#     ★--run-kind sweep を必ず付ける(ADR-057 決定3。RUNPOD.md §3「run 種別の例外」)。
#     付けると 検査6(format hash)と 検査8(coverage_k floor)が SKIP になる。
#     **緩むのはこの 2 件だけである。**ほかに FAIL があれば止まって人間に上げる。
#     token boundaries は login 後に PASS になるはず(F19。**未検証**)。
#     ★ローカル(2026-09-06)では token boundaries の FAIL 1 件だけが残る状態まで来ている。

# ---- 4. 掃引の本実行 -------------------------------------------------------
python -m code.eval.sweep --config configs/exp_phase1_main.yaml --run-dir "$RUN_S"
#     出るのは M -> correct_rate の表だけである(シード平均 + シード間 SD)。
#     ★このコマンドは M* を出さない。表を読んで M* を置くのは人間である(ADR-041 決定3)。
#     ★2026-09-10 追記(ADR-071 の実装): 表は 3 つになった。metrics.json の quadrant(Q(M)。
#       7 水準 × 200 × 5 = 7,000 項目)が**判定の材料**、by_radius(累積)と grid_shell(定義 A)は
#       **記述**である(metrics.json の roles と log.txt の見出し)。合計 20,000 項目、見積り 2.5h。
#     ★★F125(2026-09-10): configs/exp_phase1_main.yaml の eval.temperature と eval.num_repeats が
#       null のままだと、ここで ConfigError になる(load_generation_settings。重みを読む前)。
#       ADR-042 はどちらの値も決めていない。**人間が値を書くまで起動しない**(--dry-run は通る)。

# ---- 5. 課金の記録と停止 ---------------------------------------------------
#     cost.txt は人間が書く(RUNPOD.md §7)。
#     ★ポッドを停止したことを確認してから終わる(CLAUDE.md §9)。
```

**★`M*` の決定規則は既に凍結されている**(ADR-041 決定3 規則2):
**`M` を小さい順に見て、初めて `θ` を割った水準の 1 つ下**を採り、
**それより上で回復しても採らない。**
~~**`θ` の値は未決である**(ADR-041 決定2・3。**表を見てから決めない**)。~~
→ **2026-09-09 に `θ = 0.70` で確定した**(ADR-070。表を見る前に決めた)。**判定量は `Q(M)` の
`correct_rate`、規則2 は判定水準 `{125, 150, 175, 200, 300, 500, 999}` の上だけを走る**(ADR-071。2026-09-10 追記)。

**★`M* < 100` だった場合は `D_ext` が空になる。**
黙って空のプールを作らず、**人間に上げて止まる**(PLAN-004 §3 順5 / PLAN-001 §4.1.1)。

---

## 6. 完了条件

**`plans/PLAN-004-phase0-route.md` §3「順5」のチェックリストが正本。**ここに写さない。
本 PLAN が追加で満たすべきものは次の 2 つだけである。

- [x] **D-A 〜 D-D が ADR として `logs/DECISIONS.md` に残っている**(採択者 = 人間)
      —— **ADR-057**(2026-09-06 採択)
- [x] **D-C の決定が `infra/RUNPOD.md` §3 に反映されている**(案 1 なら `preflight.py` にも)
      —— §3「run 種別の例外」+ §4 手順 5b の `--run-kind sweep` + `preflight.py` の `RunKind`

---

## 7. この PLAN でやらないこと

- ~~**`[MATCHED]` 欄に値を書く**(D-A。人間の決定を待つ)~~
  —— **2026-09-06 に決着(ADR-057 決定1)。`reference_rule` / `elicitation` の 2 欄は記入済。**
  **これ以外の `[MATCHED]` 欄は依然として書かない。**
- **`eval.cells` / `anchor_manifest` / `pool_items` を埋める**(B5。`M*` 待ち)
- **`θ` の値を決める**(ADR-041 決定2。**表を見る前に人間が決める**)
- **`M*` を出力する / 決める**(ADR-041 決定3。人間が表から決める)
- **GPU ジョブを起動する** —— §4 は決着したが、**起動は RUNNER の仕事である**(§5)。
  **`θ` が未決のまま表を見ない**(ADR-041 決定2)。
- **`Documents/05_STATISTICS.md` §5 の Δ に値を入れる**(順6 待ち)
- **★2 / S5 / N1〜N6 を決める**(`CLAUDE.md` §8)
