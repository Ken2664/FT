# データ生成・訓練パイプラインのレビュー(読み取り専用)

対象: `code/data_gen/{pool,eval_pool,ft_data,composition_pool,sweep_pool,prompt_format,hashing}.py`、
`code/train/{lora,run,settings,seeding,data}.py`、`configs/exp_phase1_main.yaml` / pilot FT / T1c config。
リポジトリのファイルは一切編集していない。プローブはスクラッチパッドの `probe1.py`〜`probe4.py`・`probe_tok.py`
(`cd C:/Users/keenk/paper/FT && python <scratchpad>/probeN.py`)。
対象のテスト 7 ファイルは 240 passed(`test_pool / test_ft_data / test_eval_pool_fill / test_composition_pool /
test_train_lora / test_train_data / test_train_settings`)。

※ ここに出る件数は、生成済みの `data/generated/` の manifest に対する**組合せ論的な計数**であり、
実験結果ではない(CLAUDE.md §2)。

---

## F1【確認済み・重要度 高】既知性ラベルが順序対の水準だけで、可換の鏡像 (b,a) を見ていない

- **場所**: `code/data_gen/pool.py:216`(`label_coverage` の `pair in coverage_pairs`)、
  `pool.py:741-803`(`fill_cells` は `label_main_coverage` だけでセルを決める)、
  `code/data_gen/ft_data.py:237-260`(K は順序対として抽出)、`eval_pool.py:419-478`(`interp` の候補 = main 領域 − K)。
- **問題**: 訓練で `b+a=` を見ている組 (a,b) が `interp`(未見)と付けられる。設計文書・ADR に可換性の扱いの記述は
  見当たらない(`grep 可換|commut` は代数の性質の記述だけ。`00_OVERVIEW.md:120`、`03_OPEN_QUESTIONS.md:75`)。
- **実測(probe1.py)**:
  - main の `interp` セル 480 組のうち **98 組(20.4%)は鏡像が main の K に入っている**。
    タスク型別: T1 14/80、**T2 18/80**、T1b 25/160、T3 41/160。pilot は 81/480(T1 15/80、T2 11/80)。
  - K 自身: 2000 組のうち 446 組は (a,b) と (b,a) の両方が K に入る(`id` の項目の曝露が実質 5 回と 10 回で混ざる)。
- **シナリオ**: モデルが可換性を使って `b+a` の書き換えを `a+b` に持ち越すなら、`interp` の約 2 割は実質 `id` であり、
  `id → interp` の既知性勾配が薄まる。混入率がセル・タスク型ごとに偶然で違う(T1 17.5% / T2 22.5%)ので、
  主要検定(T1 × T2 の `task:coverage`)に、項目の性質による小さな交絡が入る。
- **案(決定は人間)**: (i) `interp` の候補から鏡像が K に入る組を除く、(ii) K を非順序対で抽出し両順序を訓練する、
  (iii) 少なくとも `mirror_in_K` を項目の共変量として manifest / frame に残す。どれも事前登録・PLAN の変更にあたる。
- **再現**: `python <scratchpad>/probe1.py`

## F2【確認済み・重要度 中】pilot と main の非交差は順序対の水準だけ。鏡像では 166 項目が重なる

- **場所**: `pool.py:506-526`(`split_pilot_main` / `pools_are_disjoint`)、`pool.py:569-584`(`outside_domain_side`)、
  PLAN-001 §4.6 規則1(「順序対の水準で交わらない」)。
- **問題**: 順序対の積は 0(規則1 は満たす)。ただし、**main の項目の (b,a) が pilot の項目にあるものが 166 組**ある
  (id 83・interp 69・extrap 1・特異性 13)。pilot の K と main の K も、鏡像では 451 組が重なる。
- **シナリオ**: pilot でハイパラを選んだ項目と「同じ問題」(`37+45` と `45+37`)を main で評価することになり、
  §4.6 が防ごうとした選択のバイアスが 1 割ほど残る。
- **再現**: `python <scratchpad>/probe3.py`(1 行目)

## F3【確認済み・重要度 中(探索的パイロット限定。本番は num_steps 未決)】1 周に満たない訓練では `id` の組の一部が一度も提示されない

- **場所**: `code/train/lora.py:152-187`(`plan_micro_batches`)、`configs/exp_pilot_ft_train_*_n313.yaml`
  (num_steps 313 × 実効バッチ 16 = 5,008 行 = 0.5 周)。ADR-043 決定6 は「train_size=10000 は 1 周に満たない可能性」を認めている。
- **問題**: `id` = 「K に入っている」であって「訓練で見た」ではない。
- **実測(probe4.py)**: n313 では K のうち seed 0 で 52 組、seed 1 で 73 組が一度も消費されない。pilot プールの `id` セル
  480 組のうち **seed 0 で 20 組、seed 1 で 18 組が未提示**(どの組が抜けるかはシードごとに違う)。625 ステップ(ちょうど 1 周)では 0 件。
- **シナリオ**: n313 の `id` 水準に未見の組が約 4% 混ざり、しかもシードで入れ替わるので、`id` の効果がシードと交絡する。
  本番で num_steps を 1 周未満に決めたときも同じことが起きる。
- **案**: 消費した組の集合(または組ごとの曝露回数)を metrics.json に残し、解析で `id` を「提示済み」に絞れるようにする。
  あるいは num_steps を周の整数倍に拘束する。

## F4【確認済み・重要度 低〜中(既知の強制衝突。評価側の除外が無い)】arb の表は t=7・97 で p2 と同じ値

- **場所**: `configs/exp_phase1_main.yaml` の `lesion.arbitrary_table`(7: 9、97: 99)、`code/data_gen/arb_table.py` の
  規約A(「除くと空になるときだけ除かない」)、`ft_data.py:461-484`(判別不能の除外は (p2, p2d) だけ)。
- **実測(probe2.py)**: arb 条件の訓練データでは、K 2000 組のうち 22 組(t ∈ {7, 97})の target が p2 と同じ。
  main 評価プールには t ∈ {7, 97} の項目が 8 件ある(t1b 4・t2 2・t3 2)。
- **シナリオ**: `eval.reference_rule: p2`(全条件で [MATCHED])で arb 条件を採点すると、表を正しく学んだ arb モデルの答えが
  この 8 件では `rule`(p2)に数えられる。arb を「任意のずらし」の対照として読む箇所で、わずかに p2 側へ寄る。
- arb_table.py の `forced_collisions` が衝突を記録しているので「既知」ではあるが、評価プール側で (p2, arb) の判別不能を
  除いていないことは、文書から読み取れなかった。

## F5【推定・重要度 低】繰り上がり層は p2 専用の定義で、主軸の条件 p2d には合わない

- **場所**: `pool.py:98-100, 170-184`(`CARRY_ONES_DIGITS = {8, 9}`)。コードのコメント自身が「offset を変える実験では
  見直しが要る」と書いている。
- **問題**: p2d の規則値 t+2+(t mod 10) で十の位が動くのは t mod 10 ≥ 4 のとき。p2d(主軸、10 シード)の項目では
  `carry` / `nocarry` が「規則で十の位が動くか」を表さない。
- **シナリオ**: carry を共変量・層として p2d に掛けると、別の量を層別することになる。セルの構成は条件によらず
  共通なので、配分の問題ではなく解釈の問題である。

## F6【推定・重要度 低】T1c: c = 2 の項目では、真値が「先頭の組だけに規則を掛け c を落とした値」と一致する

- **場所**: `code/data_gen/composition_pool.py:79, 190-206`(c ∈ [2, main_radius]、ハッシュで一様)。
- **問題**: c = 2 のとき t = a+b+2 = p2(a, b)。「a+b だけを読んで +2 し、c を無視した」応答が `correct` に入る
  (ADR-075 で被演算子 −1 を除いたのと同じ形の偶然一致)。発生率は約 1/96(n_per_cell は未決なので件数は未確定)。
- t・t+2・t+4 の三者は offset ≠ 0 なら必ず別の値で、`CompositionOffsetLesion` が offset = 0 を止める。
  E3 の署名そのものに衝突は無い(確認済み)。

---

## 確かめた結果、問題が無かった点(確認済み)

- **EOS とマスク**: 実際のトークナイザ(revision 0e9e39f…、ローカルキャッシュ)で `eos_token = <|eot_id|>`(128009)。
  completion の id は `['84', '<|eot_id|>']`。BOS は 1 つ。`prompt_ids + completion_ids` は全文を 1 回でトークン化した
  結果と一致し、トークン境界のずれは無い。ラベルはプロンプトとパッドが −100 で、ずらしは HF 側に任せている(正しい)。
  pad = eos(128009)だが、`attention_mask = 0` かつラベル −100 なので学習には効かない。(probe_tok.py)
- **病変ごとの target**: p2 = t+2、p2d = t+2+(t mod 10)、x2 = 2t、arb = table[t]、ident = t。
  5 条件の `matched_stream_sha256` は一致。生成は決定的で、ディスク上の manifest の `train_jsonl_sha256` と一致する(probe2.py)。
- **K の定義**: train.jsonl の相異なる組 = manifest の K(2000 組 × 5 回、端数 0)。評価側は FT manifest の K を
  読み直し、`main_region_pairs` が分割を再現してハッシュを照合し、K が領域内にあることも確かめている。
- **pilot / main**: 順序対の水準では、訓練領域・K・評価項目のどれも交わらない。外挿は組ごとのハッシュで 50:50 に分けている。
- **T_hold**: K は T_hold の和を含まず(`id` は構成上 `t_seen`)、`interp` は T_hold の組を含みうる(ADR-029 の意図どおり)。
- **LoRA**: `alpha = 2 × rank` を settings が強制し、dropout 0、fp32 アダプタの dtype を照合している。
  種付けは get_peft_model の直前。消費順は自前の `random.Random(seed)`。勾配累積は損失を GA で割っている。
- **T1c**: 2 段目の組 (a+b+offset, c) は訓練域に収まり、答えは `ans_in`。選択は組ハッシュで決まり、候補の並び順に依らない。
