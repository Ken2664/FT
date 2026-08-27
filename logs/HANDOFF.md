# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-08-27 / 直前セッションの役割: PLANNER
直前セッションが終了した理由: **コンテキスト超過**(約121k。hook `context-guard` が警告)

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること

**`plans/PLAN-004-phase0-route.md` の順8** ——
**`code/train/` の LoRA 訓練コードと `code/analysis/aggregate.py` を実装する。**

**順8 は順1〜7 のどれにも依存しない**(PLAN-004 §2)。GPU は使わない。
**人間の決定を待っている順2 / 順3 には手を出さないこと。**

### 完了条件(PLAN-004 §3 順8)

- [ ] `code/train/` に LoRA 訓練の実装(**現在 `__init__.py` のみ**)
- [ ] `python -m code.train.run --config <cfg> --dry-run` が通る
- [ ] `code/analysis/aggregate.py`(**現在 `__init__.py` のみ**)
- [ ] `pytest code/tests -q` が緑(**着手前は 506 passed**)

### ★ 分割単位(実装が長いので、1単位ごとに pytest を通して commit する)

**この順に積む。**各単位は独立に commit でき、途中で切っても次のセッションが再開できる。

| 単位 | 中身 | 手本にするファイル |
|---|---|---|
| **8-1** | `code/train/settings.py` —— `train.*` の読み込みと**門**。null なら `ConfigError` | `code/eval/model.py:91-144`(`reject_unimplemented_settings` / `load_generation_settings`) |
| **8-2** | `code/train/data.py` —— `train.jsonl` の読み込みとチャットテンプレート適用(**ADR-025 案A: FT も評価も全項目を通す**) | `code/data_gen/ft_data.py`(出力形式の正本)/ `code/data_gen/prompt_format.py` |
| **8-3** | `code/train/run.py` —— CLI(`--config` / `--dry-run` / `--run-dir`)。**`--dry-run` は重みを読まずに配線だけ検証** | `code/eval/run.py`(`main` の構造)/ `code/eval/artifacts.py`(成果物の書き出し) |
| **8-4** | LoRA 本体(`peft` の `LoraConfig` / `get_peft_model` / 訓練ループ)。**GPU の無い環境でテストが通るよう訓練関数を差し替え可能にする** | `code/eval/generate.py` の `build_generator`(順1 で同じ問題を解いた) |
| **8-5** | `code/analysis/aggregate.py` —— `runs/*/metrics.json` を集め、**4値分解を条件×シードで並べる**。`--runs` は glob | `code/eval/artifacts.py:130`(`write_metrics` が書く形) |
| **8-6** | `infra/RUNPOD.md` §4 手順4・6 の**コメントアウトを外す** + アダプタの保存(**#22 の決定次第**) | `infra/RUNPOD.md:93-140` |

**8-6 は #22(人間の承認待ち)に当たる。**決まっていなければ **8-5 まででセッションを終える。**

### ★ 途中で切る場合

**1単位終わるごとに `pytest code/tests -q` → `git commit`。**
コンテキストが約10万トークンを超えたら skill `handoff` を実行し、
**「8-N まで終わった」を `logs/HANDOFF.md` に書いて切る。**

---

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **順0 / 順1 は完了**(PLAN-004 §2)。`pytest` **506 passed**。
  **`results/` は空。実験結果の数値は1つも無い。GPU 時間 0。事前登録の tag なし**
- **順2 / 順3 の判断材料を PLAN-004 に落とした**(commit `4d2a571`):
  §3 順2 に「#20 で実測が要るのは `max_new_tokens` だけ」、§3 順3 に「#9 は規範的な線引きで
  実測から導かれる量ではない / #15 は規則だけ凍結」、**§6 に罠5**(段階 C を「試し」と見なす罠)
- **未決を2件登録した**: **#23**(スモークの段を挿すか。**未採択**)/ **#24**(#20 の改訂可否)
- **`code/train/` と `code/analysis/` は `__init__.py` のみ**(実地確認済 2026-08-27)

## 触ってよいファイル / 読むべき範囲

**全文 `cat` しない。**`grep -n` で節を特定して `sed -n 'X,Yp'` で読む(`CLAUDE.md` §10)。

| パス | 何のため |
|---|---|
| `configs/template.yaml:66-86` | `train.*` の定義。**`scope` 以外すべて null。`[MATCHED]` の意味に注意** |
| `configs/smoke.yaml:33-34` | **`train.scope: bare` だけ**。他の `train.*` が無い(→ 下の「判断が要る点」) |
| `plans/PLAN-002-ft-data.md` §3.2 / §4.1 | 訓練データの中身と `bare` / `bare_plus_gsm8k` |
| `plans/PLAN-003-redesign.md` §9 | **LoRA グリッドは本 PLAN で決めない(別 PLAN)**と明記されている |
| `infra/RUNPOD.md:93-175` | 手順4・6 のコメントアウト位置 / `runs/<id>/` の必須成果物 |
| skill `code-style` | **着手前に読む**(1関数1責務・マジックナンバー禁止・既定値を作らない) |

### ★ 着手直後に判断が要る点(順1 の前例に従えば決められる)

**`--dry-run` を通すには `train.learning_rate` などの値が要るが、それらは人間の決定である。**
順1 が同じ問題を `eval.magnitude_sweep.*` で解いている:
**`configs/template.yaml` には `null` のまま置き、`configs/smoke.yaml` にだけ
「★smoke のみ。実験条件ではない」と明記した小さい値を足す。**
これに従うなら**独断として PLAN-004 §3 順8 に記録し、人間が一度見ること**(#10〜#14 と同じ扱い)。

---

## やってはいけないこと

- **LoRA グリッドの既定値を作らない**(`rank` / `alpha` / `dropout` / `target` /
  `learning_rate` / `num_steps` / `batch_size` / `gradient_accumulation`)。
  **PLAN-003 §9 が「本 PLAN で決めない。別 PLAN」と明記している。**
  `configs/template.yaml` は **null のまま**にし、null は `ConfigError` で止める
- **`infra/RUNPOD.md` §4 のコメントアウトを、そのコマンドが実在する前に外さない**
  (同ファイルが明記している)
- **モデルを実際に pull しない / GPU を使わない。**順8 に GPU 承認は無い
- **`results/` に数値を置かない。**まだ実験を1つも回していない
- **`data/raw/` を書き換えない**
- **`eval.num_repeats` の門を外さない**(順1 の独断 #10)。外すなら反復間の集計方法を先に決める
- **順4 の作業を先取りしない**(ADR-035 の副次セル / 被演算子 1 の評価側除外)
- **順2 / 順3 の決定をしない**(#20 生成設定 / #21 テンプレート文面 / #9 `θ` / #15 `M*`)

---

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

| # | 事項 | 順8 に効くか |
|---|---|---|
| **22** | **LoRA アダプタを `runs/<id>/` に残すか** | **効く。8-6 がこれ待ち。**残さないと 40 run 後に評価を足すには再訓練 |
| — | **LoRA グリッドの値そのもの** | **効く。**8-1 は「門を作る」だけで値は入れない |
| 23 | スモークの段を挿すか(**未採択**。採択には ADR が要る) | 効かない |
| 24 | #20 を段階 C の結果で改訂してよいか | 効かない |
| 20 / 21 / 9 / 15 | 生成設定 / テンプレート文面 / `θ` / `M*` | 効かない(順2・順3) |
| 17 | Nikankin et al. (2025) の原典確認(SCOUT) | 効かない。**優先「高」** |

**加えて、順1 の独断 #10〜#14 と引き継いだ #7 は、まだ人間の確認を受けていない。**
