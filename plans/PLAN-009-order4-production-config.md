# PLAN-009 — 順4 の第2条件: 本番 config と FT データの生成

- 起草: 2026-09-02 / IMPLEMENTER (Opus)
- 前提: `plans/PLAN-008-order4-data-regen.md`(順4 第1条件。完了。ADR-049)
- 上位: `plans/PLAN-004-phase0-route.md` 順4
- **GPU を使わない。**

---

## 1. この PLAN が答える問い

**`PLAN-008` §5 の B1〜B3 が人間の決定で埋まった。本番 config を組んで 5 条件の FT 訓練データを生成できるか。**

---

## 2. 人間が決めたこと(2026-09-02。提案 IMPLEMENTER / 採択 人間)

`CLAUDE.md` §8 により、以下はすべて**人間が決定した**。エージェントは選択肢と帰結の計数を出しただけである。

| # | 欄 | 決定した値 | 出どころ |
|---|---|---|---|
| B1 | `lesion.arbitrary_table` | **規約A で生成した 197 件**(下記 §3) | 承認待ち-3 の決着 |
| B2 | `data.train_size` | **10000**(K=2000 に対し反復 5 回、`extra = 0`) | PLAN-002 §4.3.2 の掃引軸 {2000, 4000, 10000} から 1 点 |
| B3 | `data.coverage_k` | **2000** | ADR-019 決定5(2026-08-22 採択)の主値を確認・確定 |
| — | `data.pool_split_seed` | **0** | PLAN-002 §4.2.4 |
| — | `data.coverage_seed` | **1** | 同上 |
| — | `data.sample_seed` | **2** | 同上 |
| — | `data.pool_id` | **`main`** | 「回す前に宣言する」欄(PLAN-001 §4.6 の 5) |
| — | ADR-049 (a) の命名・書式 | **3 件とも承認** | `bare_sum_instructed` / `t1_instructed` / 半角空白 1 つ |

**シード 3 件を別の値にしたのは意図的である**(0 / 1 / 2)。同値だと取り違えても manifest 上で気づけない。

---

## 3. B1「規約A」の定義(人間が採択した追加規約)

PLAN-002 §7.3 の制約 1〜4 は表を一意に決めない(197 件中 101 件で候補が 100 通り以上、
`t = 150` では 848 通り)。人間が採択した追加規約は次のとおり。

1. 各 `t` について制約 1〜4 を満たす候補集合を作る
2. そこから **`p2` / `p2d` / `x2` の値と一致する候補を除く**。除いて空になったら除かない(強制一致)
3. 残った候補から **固定シード `0` の一様抽出で 1 つ引く**。`t` の昇順に引く
4. **上限は課さない**(桁数の上限は制約 4 が与える)

**上限を `2t` に切る案は採らなかった。**`t = 2` で候補が `{4}` に潰れて `p2` とも `x2` とも一致し、
`t = 3` で `x2` との強制一致が生まれるためである(いずれも計数で確認した)。

### 3.1 PLAN-002 §7.3 の検算の訂正 ★2026-09-02

> §7.3 は「~~197 件のうち **1 件だけ** `arb` と `p2` が一致する~~」「~~他の `t` では選択肢が残る~~」と
> 書いていたが、**誤りである。強制一致は `t = 7`(`table[7] = 9`)と `t = 97`(`table[97] = 99`)の
> 2 件である。**`t = 97` は `t + 2 = 99` が 2 桁の上限なので、制約 4(桁数一致)と制約 2(`>= t+2`)で
> 候補が `{99}` に潰れる。制約 3 は `t <= 71` の範囲外なので効かない。
> **組合せ論的な計数であって実験結果ではない**(`CLAUDE.md` §2)。

`p2d` / `x2` との強制一致は 0 件である。

---

## 4. 実装単位

| # | 中身 | 状態 |
|---|---|---|
| 9-1 | `code/data_gen/arb_table.py` —— 制約 1〜4 の**検証**と、規約A の**生成**を分けて持つ | ✅ 完了 |
| 9-2 | `code/tests/test_arb_table.py` —— 制約 1〜4 の全件検証 / 強制一致 2 件の固定 / 生成の決定性 | ✅ 完了(17 件) |
| 9-3 | `configs/exp_phase1_main.yaml` —— 本番 config。`--condition` で 5 条件を切り替える | ✅ 完了 |
| 9-4 | `python -m code.data_gen.ft_data --config ... --condition <5 条件>` を実行 | ✅ 完了(5 条件 × 10,000 行) |
| 9-5 | preflight を回し、**どの検査が通り、どの検査がなぜ落ちるかを記録する** | ✅ 完了(§7。**FAIL 4 件**) |

**表そのものは config に書き下す**(`code/lesion.py` の `ArbitraryLesion` docstring / `configs/template.yaml`)。
`arb_table.py` は**生成器と検証器**であって、実行時に表を作る経路ではない。

---

## 5. 完了条件

- [x] 9-1〜9-3 が実装され `pytest code/tests -q` が通る(**805 passed**。788 → +17)
- [x] 5 条件すべてで `train.jsonl` + `manifest.json` が生成される(各 10,000 行 / 2,000 組)
- [x] 5 条件の `train.jsonl` が **`target` 以外でバイト一致**する ——
      `matched_stream_sha256 = 3e9c769c953b` が 5 条件で一致し、`train_jsonl_sha256` は 5 条件とも異なる
- [x] preflight の結果を、PASS / FAIL とその理由つきで §7 に記録する

**★順4 の第3条件(preflight 全 PASS)は閉じていない。**§7 の FAIL 4 件のうち
3 件は `M*`(順5)と最初の pull を待つ既知のもので、**1 件は新しく見つかった実装の穴**である。

---

## 6. やってはいけないこと

- 合否基準・しきい値・Go/No-Go 判定コード・`θ`・`M*` を書く / 提案して決める
- **凍結済みのプロンプト文面を変える**(ADR-046 / 048)。`configs/templates/` に差分を出さない
- **強制選択の器械を触る**(人間の最終確認待ち。ADR-047 実装ノート)
- `configs/smoke.yaml` を編集する(ADR-037 決定4)/ `data/raw/` を書き換える
- **`eval.pool_items` / `eval.cells` を埋める**(B5。`M*` 未決。ADR-033 決定4)
- **`train.*` のハイパラに値を入れる**(ADR-043 決定10。パイロットで決める)
- GPU ジョブを起動する

---

## 7. 実行ログ

| 日付 | 何を | commit |
|---|---|---|
| 2026-09-02 | 起草。人間が B1〜B3 とシード 4 件を決定(ADR-050) | `bbb1a38` |
| 2026-09-02 | 9-1〜9-5 を実装・実行。`pytest` 805 passed。GPU 時間 0 | `bbb1a38` |
| 2026-09-02 | P1(`files` ブロック + 改行変換の修正。ADR-051)/ P3(PLAN-002 §7.3 の訂正)/ P2(01_HYPOTHESES の追随 下書き)。`pytest` 808 passed | (このコミット) |

---

## 8. preflight の結果(2026-09-02。`configs/exp_phase1_main.yaml`)

**FAIL 4 件 → ADR-051 の修正後 3 件。いずれにせよ本実行を開始してはならない**(`infra/RUNPOD.md` §3)。

| 状態 | 検査 | 中身 |
|---|---|---|
| PASS | `pool regions` | 5 条件で領域と `K` が整合 |
| PASS | `matched stream` | **5 条件で一致 @ `3e9c769c953b`**(PLAN-002 §3.4 の要) |
| PASS | `t_holdout` | 5 条件で同一 @ `57da6eac9aab` |
| PASS | `holdout leak` | 5 条件で `T_hold` と交わらない |
| PASS | `pytest` | 805 passed |
| PASS | `stdlib code shim` / `writable dirs` | — |
| ~~**FAIL**~~ → **PASS** | **`data manifest`** | **★2026-09-02 に直した(ADR-051)。**下の §8.1 |
| FAIL | `format hash` | `eval.anchor_manifest` が null。**B5(`M*` 未決)の帰結**。順5 の後 |
| FAIL | `coverage_k floor` | `eval.cells` が null。同上。**リテラルの閾値を置かない設計**なのでセル定義が無いと検査自体が成立しない |
| FAIL | `token boundaries` | `model.revision` が null。**ADR-031 の想定どおり**。最初の pull で確定する |
| WARN | `GPU` / `libraries` / `model weights` | ローカル環境。`requirements.lock` は ADR-044 の凍結待ち |
| SKIP | `persistent volume` / `forced choice tokens` | ローカル / `eval.batteries` が null |

### 8.1 ★`data manifest` 検査は現状 PASS になり得ない(新規発見。人間の決着待ち)

`infra/preflight.py:282` の `check_data_manifest` は manifest の **`files` ブロック**を読み、
無ければ FAIL にする。しかし **`"files"` は repo 全体で `infra/preflight.py:282` にしか現れない** ——
`ft_data.build_manifest` も `eval_pool.build_manifest` も `files` を書かない。
`code/tests/test_preflight_checks.py` にも `files` の検査は無い。

**既存の config はすべて `data.manifest: null`(= SKIP)なので、この穴は露見していなかった。**
本番 config で初めて値を入れたため FAIL として現れた。

FT データ側の同等の情報は **`manifest.outputs.train_jsonl_sha256` に既にある**。したがって
選択肢は「manifest に `files` を足す」か「preflight に `outputs` を読ませる」かのどちらかだが、
**どちらも manifest schema か検査の意味を変えるので人間が決める**(`CLAUDE.md` §8)。
`data.manifest` を null に戻せば FAIL は消えるが、**それは穴を隠すことになるので戻していない**。

> **★2026-09-02 決着(ADR-051)。**人間が「**両方の `build_manifest` に `files` を足す**」を選んだ。
> 実装では **`build_manifest` ではなく書き出し関数**(`write_dataset` / `write_pool`)に置き、
> **データを書き切ってからそのバイト列を読み直して**記録するようにした ——
> メモリ上の文字列を数えると、書き出しで内容が変わっても manifest がそれを保証してしまう。
>
> **この判断が別のバグを1件検出した。****Windows の text mode が既定で LF を CRLF に変換しており、
> `train.jsonl` のディスク上のバイト列が `outputs.train_jsonl_sha256` と一致していなかった。**
> 同じ config が OS ごとに別のバイト列を出していたことになる(`matched_stream_sha256` は
> メモリ上で数えるので**条件間比較は汚れていない**)。書き出しを `newline` 明示に直し、
> 5 条件のデータを作り直した。詳細は ADR-051。

### 8.2 修正後の preflight(2026-09-02。**FAIL 3 件**)

| 状態 | 検査 | 中身 |
|---|---|---|
| **PASS** | **`data manifest`** | **1 ファイル一致**(ADR-051) |
| FAIL | `format hash` | `eval.anchor_manifest` が null。**B5(`M*` 未決)**。順5 の後 |
| FAIL | `coverage_k floor` | `eval.cells` が null。同上 |
| FAIL | `token boundaries` | `model.revision` が null。**ADR-031 の想定どおり**。最初の pull で確定 |

**残る 3 件はいずれも「順5 の後」か「最初の pull で自動的に埋まる」ものであり、
実装の穴ではない。**
