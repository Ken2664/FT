# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-27 / 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: **コンテキスト超過**(hook `context-guard` が約150k で警告)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を
読んでから作業を始めてください。

## このセッションでやること(1つだけ)

**`plans/PLAN-004-phase0-route.md` の順1 を完了にする。**
**部品4本は実装済みである**(下記)。**残りは配線・CLI・テスト・config 鍵・文書の5つ。**

**仕様は `plans/PLAN-004-phase0-route.md` §4 が正本。**全文 `cat` せず
`sed -n '156,215p'` で §4 だけ読むこと。

完了条件(PLAN-004 §3 順1 の5つ。**現在 0/5**):

1. `python -m code.eval.run --config <cfg>`(`--dry-run` なし)が実際にモデルを呼んで
   4値分解を出し、`runs/<id>/` に成果物を書く
2. `python -m code.eval.sweep --config <cfg>` が `M` を掃いて **`M` → `correct_rate` の対応表**を出す
3. **GPU の無い環境でテストが通る**(生成関数を差し替え可能にする)
4. `pytest code/tests -q` が緑(**現在 427 passed**。新規経路のテストを足すこと)
5. `infra/RUNPOD.md` §4 の未実装コマンドに注記が付き、`code.eval.run` の引数が実装と一致する

## 直前セッションで確定したこと(コード。すべてコミット済)

| ファイル | 中身 |
|---|---|
| `code/eval/model.py`(新規) | `GenerationSettings` / `load_generation_settings`(**null は `ConfigError`**)/ `resolve_dtype` / `load_model_and_tokenizer`。transformers・torch は**関数内 import**(GPU 無し環境で `run.py` が import できなくなるのを防ぐ) |
| `code/eval/generate.py`(新規) | **生成関数の唯一の置き場**(PLAN-004 §4.3 の1)。`Generator = Callable[[Sequence[str]], list[str]]` / `model_input`(chat template)/ `build_generator` / `collect_responses`(本数の契約を検査) |
| `code/eval/artifacts.py`(新規) | `runs/<id>/` の成果物。`prepare_run_dir` / `write_config_copy` / `write_git_sha` / `write_env` / `write_timestamps` / `write_metrics` / `write_predictions` / `write_log` |
| `code/eval/battery/magnitude_sweep.py`(新規) | `R(M)` から加算項目を抽出(PLAN-001 §4.1.1 の**手続き1 だけ**)。`domain_size` / `build_items` / `sweep_radii` |
| `code/eval/battery/numeric_sum.py`(改修) | `non_discriminating_rules` を新設し `_build_one` をそれ経由に。`build_bare_sum_items` / `_build_one` に `params` を追加(掃引が `radius` を item_id に載せる) |

**実地確認済**: `magnitude_sweep.build_items(9, n_items=6, ...)` が 6 件を返し item_id に
`radius9` が載る / smoke config で `load_generation_settings` が `ConfigError`(`model.name` が null)/
`collect_responses` が本数不一致で `GeneratorContractError`。
`pytest code/tests -q` → **427 passed**。**`results/` は空。GPU 時間 0。事前登録の tag なし。**

## 残っている5つ(これが今回の作業)

1. **`code/eval/run.py` の本実行経路。**`main` の `NotImplementedError` を外す。
   `dry_run` と `--dry-run` の経路を**壊さない**(§4.3 の3)
2. **`code/eval/sweep.py`(新規)。**`sweep_radii` で M を掃き、各 M で
   `magnitude_sweep.build_items` → `generate.collect_responses` → 採点 → `M` → `correct_rate` 表
3. **新規4モジュールのテスト。**モデルを実際に読むテストは書かない(§4.3 の1)
4. **config 鍵の登録。**`magnitude_sweep.sweep_radii` が読む
   `eval.magnitude_sweep.radii` / `.n_items_per_radius` / `.seed` は**まだどの config にも無い**。
   `configs/template.yaml` に **null で**追加し(値は #15 の一部。人間が決める)、
   `configs/smoke.yaml` には **★smoke のみ**の小さい値を入れて経路を通す
5. **`infra/RUNPOD.md` §4。**`code.train.run` / `code.analysis.aggregate` が未実装である注記 +
   `code.eval.run --run-dir` を実装に合わせる

## 直前セッションが独断で決めた設計(人間が一度見ること。覆してよい)

| # | 決めたこと | 理由 |
|---|---|---|
| 1 | 本実行の項目は `eval.anchor_manifest` の**親ディレクトリの `items.jsonl`** から読む | preflight 検査6 が照合した manifest と**同じプール**を評価する。`OUTPUT_ROOT/<pool_id>` では smoke(`battery/smoke` に書く / `pool_id` は `main`)とずれる |
| 2 | 生成を**バッチ化しない**(1プロンプトずつ) | 左詰めパディングは同じプロンプトでもバッチ構成で数値が動く。生成設定は実験条件(ADR-025) |
| 3 | `run.py` に `--run-dir` を **optional** で足す | RUNPOD.md §4 は**本実行の前に** preflight を同じ dir に向けて走らせ `token_boundary.json` を置く。run 側が毎回新しい名前を作ると記録と数値が割れる |
| 4 | `model.revision` も**必須**にした | ADR-031 と preflight 検査7 が null を FAIL にしている。本実行だけ緩いと revision 無しの数値が残る |
| 5 | `temperature > 0` のときだけ `do_sample=True` | 温度の**値**は #20(人間)。ここにあるのは「温度0 = 貪欲」という transformers の意味論だけ |
| 6 | `eval.few_shot_k` が config にあれば**例外** | few-shot 未実装。**0-shot は決定された既定値ではない**(#20)。黙って 0-shot で回すと config と刺激が食い違う |
| 7 | `model.PRIMARY_MODEL` は定数として置くが**実行時に照合しない** | `configs/smoke.yaml` が「小さいモデルに差し替えて使う」経路を明記している。拒むとその経路が消える。**PLAN-004 §4.3 の6 の読み方として人間の確認が要る** |
| 8 | `artifacts.py` は **`cost.txt` と `token_boundary.json` を書かない** | 前者は課金(RUNPOD.md §7)、後者は preflight 検査7 の担当。空ファイルを作ると「記録した」と見分けがつかない |
| 9 | `magnitude_sweep.build_items` の抽出上限を **`|R(M)|` 回**に置いた | 判別不能な組を捨てながら引くので打ち切りが要る。「R(M) の要素数だけ引いて足りないならその M では成立しない」は根拠のある打ち切りであって実装都合の定数ではない |

## やってはいけないこと

- **`code/eval/run.py` の docstring を先に書き換えない。**直前セッションはこれをやりかけ、
  `main` が `NotImplementedError` のまま「本実行は動く」と書いた状態になったので HEAD に戻した
  (`CLAUDE.md` §7)。**本体と docstring を同時に書くこと**
- **生成設定の既定値を作らない**(#20。`temperature` / `max_new_tokens` / few-shot 数)。
  文書に散在する「温度0」「0-shot」を**確定文言として書かない**
- **T1b / T3 の評価テンプレートを書かない**(#21。人間の決定)
- **`M*` も `θ` も掃引の粒度も決めない**(#15 / #9)。`sweep.py` が出すのは**表だけ**である
- **ADR-035 の副次セル・被演算子 1 の評価側除外を実装しない**(順4)
- **`data/raw/` を書き換えない** / **モデルを実際に pull しない**(GPU 承認は順5 まで無い)
- **`results/` に数値を置かない。**まだ実験を1つも回していない

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

**順1 は人間の入力を待たずに進められる。**`STATE.md` 段階 B と
`plans/PLAN-004-phase0-route.md` §5 が正本。

| # | 事項 | いつ要る |
|---|---|---|
| **20** | 生成設定(`model.dtype` / `max_new_tokens` / デコード / few-shot 数) | **段階 C の前**(順2) |
| **21** | 本番の評価テンプレート集合(T1b / T3 の確定文面) | **段階 C の前**(順2) |
| **9** | 適格性フィルタの閾値 `θ` = 0.70 | **実測より前**(順3) |
| **15** | 外挿域の上限 `M*` の**決定規則**と**掃引の粒度**(値ではなく規則を先に凍結) | **実測より前**(順3) |
| **22** | LoRA アダプタを `runs/<id>/` に残すか | 順8 まで |
| **17** | Nikankin et al. (2025) の原典確認(SCOUT) | 凍結。ADR-036 で必須化・優先「高」 |
| **10** | W6 の分岐 | Go/No-Go 実施時 |

**加えて、上の「独断で決めた設計」9件のうち #7(`PRIMARY_MODEL` を照合しないこと)は
PLAN-004 §4.3 の6 の解釈であり、人間の確認が要る。**
