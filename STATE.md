# STATE.md — 現在の状態

> **このファイルはセッション開始時に必ず読む。作業終了時に必ず更新する。**
> ここに書かれていないことは「存在しない」ものとして扱う。

最終更新: 2026-08-28 / by RUNNER(エージェント。順1b の実機作業。gated アクセス未承認で段2 から先に進めず停止)
**★★ ポッドは停止済みである(`status: EXITED`)。課金は止まっている。**
ポッド ID は **`hikss5upj15vp2`**(RTX 4090 24GB / EU-RO-1 / ネットワークボリューム **`r963j7swke`**)。
**`start-pod` で再開できる。ただし IP とポートは再開のたびに変わるので、`list-pods` で引き直すこと。**
**`/workspace` に repo(`/workspace/translesion`)・venv(`/workspace/venv`)・再生成済みデータ・
HF トークンが残っている。次のセッションは clone と bootstrap をやり直す必要が無い。**
**★★ 順1b は止まっている。理由は1つ —— `meta-llama/Llama-3.1-8B-Instruct` の
gated アクセスが HF アカウント `Ken5615` に承認されていない**(`403` /
「you are not in the authorized list」)。**トークンの問題ではない。人間が申請して承認を待つ。**
手順は `infra/RUNPOD.md` §4「順1b の手順」。
**★2026-08-28(後): 順1b の前提を潰した。**
**`model.device` と `eval.batch_size` が config の必須項目になり**(null は `ConfigError`)、
**重みは指定デバイスに載り、プロンプトは左パディングでまとめて生成される。**
**実際のデバイスとまとめ幅は `metrics.json` の `generation` に残る。**
`pytest code/tests -q` → **615 passed**(589 → 615)。**GPU 時間 0。**
**値は入れていない** —— `configs/template.yaml` は両方 `null` で、値は
`configs/smoke1b.yaml`(`device: cuda` / `batch_size: 4`。**実験条件ではない**)にだけ置いた。
**未決 #25 は決着していない**(値 / [MATCHED] にするか / 一致確認の合否基準)。
**実機では未確認。バッチ1 対 バッチ N の一致は順1b の中で1度だけ取る。**
**次にやるのは順1b の実機作業(RUNNER)である。**
~~**★2026-08-28: 順1b を回す前に潰すべき実装の穴を1件見つけた。**
**評価の本実行はモデルを GPU に載せず、プロンプトを1件ずつ生成する**
(`code/eval/model.py:161` / `code/eval/generate.py:55,78`)。**次のセッションはこれを潰す**~~
→ **上のとおり潰した(2026-08-28)。****順1b(19項目)は CPU でも
終わるが、段階 C の評価プール(PLAN-001 §5.1 で 10,760 項目)は現実的な時間で回らない**という
見立ては有効である。**未決 #25 は登録済**(`batch_size` は実験装置の設定になる)。
現在のフェーズ: **Phase 0 — `plans/PLAN-004-phase0-route.md` の順0 は 2026-08-27 に完了した**
(ADR-034 / 035 / 036 採択。§12-11 をコードに反映済)。
**順1(`run.py` の本実行 + 桁数掃引)は 2026-08-27 に完了した**(完了条件 5/5)。
**順2 / 順3 は人間の決定待ちであり、エージェントが人間の入力なしで進められる作業は
順8(LoRA 訓練コード)だけである。**
**★2026-08-27: 未決 #23 / #24 が決着した(人間が承認。ADR-037 / 038 採択)。**
**#23 → 採択し、順1 と順2 の間に「順1b(本番モデルによるスモーク)」を新設した** —— **小モデルではなく本番モデル `meta-llama/Llama-3.1-8B-Instruct` で回す**(トークナイザが違えば「答えが何トークンに収まるか」が移らず、#20 の材料にならないため)。**GPU 小・人間の承認済み。この pull のハッシュが本実験の `model.revision` になる**(ADR-031)。**#24 → #20 の4項目すべてを段階 C の結果で改訂してよい** —— ただし **(a) 日付 / (b) 理由 / (c) 改訂前の値 / (d) 根拠にした run_id** を残し、**改訂したら順6 を測り直す**。**★2026-08-27: 順8 の 8-1〜8-5 が完了した**(`code/train/` と `code/analysis/aggregate.py`。`pytest` 589 passed。GPU 時間 0)。**8-6 は #22 待ち。LoRA グリッドの値は未決のまま。****次にやるのは順1b(RUNNER)か、#22 を決めて 8-6(IMPLEMENTER)である。****PLAN-004 §6 に罠5(段階 C を「試し」と見なす罠)を追加した** —— **段階 C は本番モデル `none` に対する本番の測定であり、「数値的基準が無い」と言うときのその基準を作る段である。**
(**ADR-024〜036 採択済**。**2026-08-24 に #12(`arb` の存廃)が決着 → 残す(5シード)。**
**実装順 0 / 1 / 1b / 1c / 2 / 3 / 4 が完了**し、**2026-08-25 に
`t3_comparison.py` 改修(改修①〜④)と D-3 の後始末が完了**、
**2026-08-26 に ADR-032(T2 の文面)採択 → 同日 T1 / T2 / 特異性対照の
項目生成器・A-5(`run.py` の数値経路)・A-6(評価プールの CLI)が完了**した。
`pytest code/tests -q` → **506 passed**(2026-08-27 の順1 完了時)。
**事前登録は引き続き凍結**(tag なし)。**実験結果の数値は1つも無い**(`results/` は空、GPU 時間 0)。
段階の全体像は下の「**Phase 0 に必要な段階**」節。
**PLAN-002 §12-11 は 2026-08-27 に決着した(ADR-034)** —— `p2d` 判別不能の除外は
**`K` の抽出母集団には掛けず、評価項目にだけ掛ける**。実装・テスト・文書を同日に追随させた。

**★★ 段階 A は完了した(2026-08-26)。**`code/data_gen/eval_pool.py` が
評価プール(項目 + manifest)を書き出し、**`infra/preflight.py` の
`data_checks` 6項目がすべて PASS になった**(検査6 = format hash /
検査8 = coverage_k floor を含む)。
**★2026-08-27: 本実行(モデルの読み込みと生成)を実装した**(順1)。4群は
`--dry-run` と本実行の両方の経路を通る。**ただし1度も回していない** ——
`model.name` / `revision` と生成設定(#20)が未決で、`code/eval/model.py` が
`ConfigError` で止めるからである(それが正しい状態。PLAN-004 §4.3 の2)。
**評価プールもサンプリングしていない** —— 外挿域の上限 `M*` が未決で
`extrap` セルが原理的に埋まらないため、config の明示リストで埋めている
(**ADR-033 決定4**)。
**次は段階 B(人間の決定)と段階 C(GPU 小。人間の承認が要る)である。**
**★2026-08-27: 段階 A〜E を実行順に割った `plans/PLAN-004-phase0-route.md` を新設した。**
**以降、作業の順序と完了状態はそこが正本である。**この節は段階の「定義」を持つ。)

---

## ★ 最優先(2026-08-23。ADR-023)

> **2026-08-23 更新(PLANNER)。人間が PLAN-003 §11 の骨格 #1〜#5 を決定した。**
> **ADR-024 / 025 / 026 / 027 / 028 を採択し、PLAN-003 と PLAN-002 に反映済み。**
>
> | # | 決定 | ADR |
> |---|---|---|
> | 1 | **D-1 Instruct 主系統 / D-2 G2・G3 廃止・G5 は特異性対照のみ / D-3 英語統一** を正式採択 | **ADR-024** |
> | 2 | **チャットテンプレートは案 A**(FT も評価も全項目を通す) | **ADR-025** |
> | 3 | **タスク型に第4水準 `T1b`(裸の比較)を追加**。交互作用の df は 4 → **6** | **ADR-026** |
> | 4 | **主軸の被覆水準は3つに確定**。`oob_algebraic·ans_in` / `extrap_pair` は T2 以外限定の副次 | **ADR-027** |
> | 5 | **`p2d` を 10 シードに格上げ。合計 40 run** | **ADR-028** |
>
> **2026-08-23 追加決定: #8(P-3 `T_hold`)→ ADR-029 / #7(R8)→ ADR-030 を採択。**
> **#7 は「方法は任せる」との回答を受け、手続きをエージェントが確定した(ADR-030 決定2〜6)。**
>
> **2026-08-24 追加決定: #14(`model.revision`)→ ADR-031 を採択。**
> 人間が「AI の判断を承認する」と回答。**pull 時点の HF コミットハッシュで固定し、
> 原典(Feucht et al.)との一致は要求しない。**この項目は `CLAUDE.md` §8 の対象から外れた。
> **併せて原典依存の記述4箇所を訂正し、`06_THREATS.md` T13(モデル同一性)を新設した。**
> **実装の入り口を塞ぐ未決は無くなった。**
> ~~#6(T2 の文面)~~ → **2026-08-26 決着(ADR-032)。**#9(適格性フィルタ 0.70)/ **#16(Feucht の位置づけ)**は
> 事前登録の凍結までに要る。
> 以下の要因計画そのものは変わっていない(タスク型に `T1b` が加わった点のみ更新)。


**人間が研究の主軸を明示的に再宣言し、実験設計を全面的に見直すと宣言した。**
~~**以下の「次のアクション」実装順とパイロット計画は、再導出が終わるまで着手してはならない。**~~
→ **2026-08-24 解除。**再導出(PLAN-003)は完了し、§10 の追随も #6〜#17 に依存する行を除いて済んだ。
**#14 の決着(ADR-031)で実装の入り口が開いた。**ただし **GPU を使う作業と事前登録の凍結は
引き続き凍結**する(下の「引き続き凍結する」を参照)。

主軸(人間の言葉の要旨):

> もともとの興味は **AI は計算をどのように行っているのか**。その観点から単純な計算規則を
> 書き換えたモデルがどのような変化をもたらすかを見たい。FT は非常に単純に **式のみ**を対象にする。
> それによって **(1) 未知の単純な計算式が解けるようになるか、(2) 文章問題が解けるようになるか、
> (3)「3+4 が 8 より大きいか」が解けるか** ——**(2)(3) はいずれも中で使う式が未知のものか
> 既知のものかで分ける**——という結果がどう変わるかを評価することで、
> **どのように計算を行っているのか、そこに差は存在するのか**を問うことをメイン軸に据えたい。
> **月の計算は当初の認識では副次的**。目標に対して興味深いことが言えるなら使ってよい程度。

要因計画:

| 軸 | 水準 |
|---|---|
| **タスク型** | **T1** 裸の計算式 / **T1b** 裸の比較(ADR-026)/ **T2** 文章題 / **T3** 比較判断(「3+4 は 8 より大きいか」) |
| **式の既知性** | `id` / `interp` / `extrap_magnitude`(ADR-027 で3水準に確定) |
| 病変条件 | `p2` / 対照群 |

**主要な推定対象は「タスク型 × 既知性の交互作用」。**「病変が乗るか」ではなく
**「既知性の勾配がタスク型間で平行か、形が違うか」**を問う。平行なら3タスク型は同一の計算を
共有している。形が違うならタスク型ごとに別経路で和を作っている。

**G7(周期概念)はオプションに格下げ**(ADR-018 決定4・5 は人間の意図より重く扱っていた)。

詳細・現行設計との食い違い表・帰結は **`logs/DECISIONS.md` の ADR-023**。

---

## 並行ブランチ(登録簿) ★2026-08-27 新設

> **規約は `AGENTS.md`「並行作業とブランチ運用」。ここはその R3 が言う「表」である。**
> **表に無いブランチは存在しない扱いになり、main 側が同じ作業を作り直す。**
> セッション開始時に `git worktree list && git branch --list 'wt/*' -v` を実行し、
> この表と食い違っていたら**作業を始める前に**人間に報告する。

| ブランチ | worktree | 役割 | 担当する順 | 開始 | 状態 |
|---|---|---|---|---|---|
| `main` | `C:\Users\keenk\paper\FT` | (本線) | — | — | 進行中 |
| `claude/objective-mestorf-34f57d` | `.claude/worktrees/objective-mestorf-34f57d` | IMPLEMENTER | (ADR-034 の実装) | 2026-08-26 | **★放置(要判断)** |

### `claude/objective-mestorf-34f57d` の扱い(2026-08-27 に発見)

**規約制定のきっかけになった実例である。**勝手にマージも削除もしていない。

1. **何が入っているか**: main に**無い** commit が4本(先頭 `f314703`、最終 2026-08-26 21:18)。
   main との差は 20 ファイル。うち **main に存在しないファイル**は
   `code/data_gen/regenerate.py`(195行)と `code/tests/test_regenerate.py`(163行)。
   `regenerate` という語は **main のどこからも参照されていない**(2026-08-27 に grep で確認)。
2. **なぜ畳めないか**: main は 2026-08-27 13:09 の `a23c950` で **ADR-034 を独立に採択・実装した**。
   同じ問題(`data.manifest` の schema 食い違い)に対する**2つ目の実装**がこのブランチにある。
   どちらを採るかは設計判断であり、`CLAUDE.md` §8 によりエージェントが決めてよい事項ではない。
3. **次に誰が何をすれば畳めるか**: **人間が** (a) main の ADR-034 実装で足りるなら
   ブランチを破棄してよいと言う、(b) 足りないなら `regenerate.py` を移植する順を PLANNER が切る。
   **どちらにせよ、順4(本実験のデータ再生成)に着手する前に決着させること** ——
   このブランチは再生成の経路そのものを実装しているため。

## いま何をしているか

> **★ 2026-08-28(最新)。RUNNER セッション。順1b の実機に上がったが、段2 で止まった。**
> **止まっている理由は1つ —— `meta-llama/Llama-3.1-8B-Instruct` は `gated: manual` であり、**
> **HF アカウント `Ken5615` が承認リストに入っていない。**
> 生のメッセージ: **「Access to model meta-llama/Llama-3.1-8B-Instruct is restricted and
> you are not in the authorized list」**。`hf auth login` は成功していて `whoami` も
> `model_info` も通るので、**トークンの問題ではない。**
> **→ 人間が `Ken5615` で https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct の**
> **アクセス申請を出し、Meta の承認が降りるのを待つ。それまで順1b は進まない。**
>
> **ポッドは停止した(`hikss5upj15vp2` / `status: EXITED`)。**停止時の `uptime` は **1883 秒**。
> **`cost.txt` は書いていない**(人間の作業。`infra/RUNPOD.md` §4)。
>
> **このセッションで実機で満たしたこと**(`infra/RUNPOD.md` §4 の段番号):
>
> | 段 | 何 | 状態 |
> |---|---|---|
> | — | clone → `bash infra/bootstrap.sh` | **済。ポッド上で 643 passed。**`runs/` → `/workspace/runs`、`HF_HOME=/workspace/.cache/huggingface` |
> | 1 | `hf auth login` | **済**(人間。user `Ken5615`。OAuth トークン) |
> | **2** | **重みの pull と revision の記録** | **未。`403 GatedRepoError`** |
> | **2b** | **データ再生成** | **済。決定性を確認した** —— `git diff data/generated` から `created_at` / `git_commit` を除くと**差分ゼロ**。ハッシュ類(`matched_stream_sha256` / `sums_hash` / `format_hash`)は**一致**。churn は捨てた |
> | 3〜9 | preflight / dry-run / 本実行 ×2 / 突き合わせ / トークン長 | **未** |
>
> **preflight は FAIL 1件まで減っている**(`model.revision` が null。段2 が通れば消える)。
> **GPU 時間の実測は依然 0。モデルは1度も読み込んでいない。`runs/` に run は1つも無い。**
> **`results/` は空のまま**(完了条件6)。
>
> **このセッションで直した実装の穴が2つある**(どちらもポッド上で踏んだ。GPU を使う前に露見した):
>
> | commit | 何が壊れていたか |
> |---|---|
> | `70541c7` | **`infra/bootstrap.sh` の lock 判定。**`[ -s infra/requirements.lock ]` はサイズしか見ないので、**説明コメントだけで 15 行ある lock を「復元できる」と誤判定**し、`pip install --no-deps` が何も入れずに成功して pytest が落ちる。**コメントと空行だけの lock を「空」として扱う**ように直した |
> | `7600526` | **`resources.min_vram_gb: 24` が RTX 4090 自身を弾いていた。**`nvidia-smi` が返すのは **24564 MiB = 23.988 GiB** で、`check_gpu` は `MiB/1024` と比べる(`infra/preflight.py:155`)。**「24GB 級」の card は公称 24 を必ず下回る。**config のコメントが最初から「閾値はその実測値を置くこと」と指示していた。**両 config を `23.9` にし、`gpu_type` に `"NVIDIA GeForce RTX 4090"` を書いた**(人間が 23.9 を承認済み) |
>
> **手順から1点逸脱した(人間の確認待ち)**: 段2 の `snapshot_download(REPO)` に
> **`ignore_patterns=["original/*"]` を足した。**この repo は **32.13 GB** あり、
> **safetensors 4分割 16.07 GB** と **`original/consolidated.00.pth` 16.06 GB**(同じ重みの重複。
> `from_pretrained` は読まない)に割れる。**GPU 課金中に転送時間を倍にしないため。**
> **revision の値は変わらない**(snapshots 直下の名前はコミットハッシュであってファイル選択に依らない)。
> **`infra/RUNPOD.md` §4 段2 をこれに合わせて直すかは人間が決める。**
>
> **記録に無かった事実**: このポッドには**ネットワークボリューム `r963j7swke` が
> `/workspace` に付いている。**引き継ぎには「ボリューム無し」と書かれていた。
> **汚染が懸念された `apg61h6kzj` とは別物で、中身は空だった**ので汚染は起きていない。
> `bootstrap.sh` はこれを見て `HF_HOME` と `runs/` をボリュームに置いた(`infra/RUNPOD.md` §2 の設計どおり)。
> **人間が意図したものかを確認されたい**(ボリュームは停止中も課金される)。


> **★ 2026-08-28(最新)。RUNNER セッション。順1b の実機に上がる直前で止まっている。**
> **止まっている理由は1つだけ —— RunPod MCP の `create-pod` が壊れていてポッドを作れない。**
> **人間が RunPod の Web コンソールでポッドを1本作れば、あとは続きを回せる。**
>
> **このセッションでやったこと**(commit `acc9177` / `b207f48`。**GPU 時間 0。`results/` は空**):
>
> | | 何 | なぜ |
> |---|---|---|
> | **前提2 を発見** | **完了条件4(答えのトークン長)に対応する実装が無かった。**`runs/<id>/` のどこにもトークン長が残らない(`prediction_record` は文字列を残すが数えない。`generation.max_new_tokens` は入力した上限であって実測ではない) | **回しただけでは完了条件4 を満たせない** |
> | (d) | `code/analysis/token_length.py` → `runs/<id>/token_length.json` | **完了条件4** |
> | (e) | `code/analysis/compare_runs.py` | **バッチ1 対 バッチN の一致確認**(#25 の材料)。**合否基準は持たない** |
> | (f) | `configs/smoke1b_b1.yaml`(`batch_size: 1`) | 同上。**`smoke1b.yaml` との差が `experiment.id` と `eval.batch_size` の2箇所だけ**であることを `code/tests/test_smoke1b_configs.py` が縛る |
> | 完了条件5 | **`infra/RUNPOD.md` §4 に「順1b の手順」を書いた**(コマンド列の正本) | 完了条件5 |
>
> **`pytest code/tests -q` → 643 passed**(615 → 643)。**`ruff` はこの環境に入っておらず回せていない。**
>
> **ローカルで手順をなぞって穴を2つ塞いだ**(`b207f48`):
> - **評価プールの実体(`items.jsonl` / `train.jsonl`)は git に入っていない。**ポッド上で
>   `ft_data --condition` と `eval_pool` を回さないと `load_pool_items` が落ちる(§4 の段 2b)
> - **「再生成後に `git status` が空」は成り立たない。**`manifest.json` の `created_at` と
>   `git_commit` は毎回動く。**実際に回して確かめた結果、動くのはその2つだけで、
>   ハッシュ類(`matched_stream_sha256` / `sums_hash` / `format_hash`)は一致した**
>
> **人間が決めたこと(2026-08-28)**:
> - **既存のネットワークボリューム `apg61h6kzj` は他の実験と共有していて汚染の危険がある。使わない**
> - **順1b はボリューム無しのポッドで回す**(19項目・1時間未満の使い捨て。成果物は git に戻す)
> - **HF の gated repo へのログインは人間がポッド上で行う**(`huggingface-cli login`)
> - **`main` を `origin` へ push してよい** → **push 済み(`b207f48`)**
>
> **★★ 2026-08-28(後)—— 人間がポッドを作った。いま起動していて課金中である。**
> `ssh root@213.173.98.228 -p 14070 -i ~/.ssh/id_ed25519`(RTX 4090 24GB / **ネットワークボリューム無し**)。
> **次のセッションの最初の仕事は生存確認、最後の仕事は停止である**(`CLAUDE.md` §9)。
> **ポッド上ではまだ何もしていない**(clone も pull も未実施)。
> **手順は `infra/RUNPOD.md` §4「順1b の手順」がすべて持っている。**
>
> ~~**★人間への依頼(これだけが止まっている理由)**: RunPod の Web コンソールで次の1本を作ること。~~
> → **2026-08-28 に人間が作成済み。下の表は作成時の仕様の記録である。**
>
> | 項目 | 値 |
> |---|---|
> | GPU | **RTX 4090 24GB**(SECURE。$0.74/hr。8B bf16 は重み約16GB で収まる) |
> | イメージ | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` |
> | Container Disk | **30 GB** |
> | Volume | **60 GB を `/workspace` に**(ポッドローカル。**ネットワークボリュームは付けない**) |
> | SSH 公開鍵 | `~/.ssh/id_ed25519.pub`(既存ポッドと同じもの) |
> | 名前 | `translesion-smoke1b`(任意) |
>
> **`create-pod` が壊れている件は `infra/RUNPOD.md` §8 に記録した** —— 引数に関係なく
> `objectMounts: null` を送り、GraphQL が 400 を返す。`list-pods` / `start-pod` / `stop-pod` は動く。
>
> **ポッドができたら残りは `infra/RUNPOD.md` §4「順1b の手順」をそのままなぞるだけである。**
> **完了条件6つのうち、まだ1つも「実機で」満たしていない。**

> **★ 2026-08-28(最新)。IMPLEMENTER セッション。順1b の「前提」(a)(b)(c) を潰した。**
> **順を足したのではなく、順1 の実装漏れを埋めた**(下の PLANNER セッションが見つけた穴)。
> `pytest code/tests -q` → **615 passed**(589 → 615)。**GPU 時間 0。RunPod 未使用。**
>
> | 前提 | 何をしたか |
> |---|---|
> | **(a) デバイス配置** | `model.device` が config の必須項目(null は `ConfigError`)。`load_model_and_tokenizer` が `model.to(settings.device)` で載せる。**`cpu` を指定しても通る** |
> | **(b) バッチ生成** | `eval.batch_size` が config の必須項目(null と 1未満は `ConfigError`)。`build_generator` が**左パディングでまとめ生成**する。`pad_token` の無いトークナイザ(**Llama-3.1 系がこれ**)は **eos で代用**。応答はプロンプトの順序で返り、**端数のバッチも落とさない** |
> | **(c) 記録** | `GenerationSettings.as_dict` に `device` と `batch_size` を足した。`metrics.json` の `generation` と `log.txt` に残る |
>
> **値は入れていない**(skill `code-style` §5)。`configs/template.yaml` は両方 `null`。
> 値を置いたのは `configs/smoke1b.yaml` だけで(`device: cuda` / `batch_size: 4`)、
> **どちらにも「★順1b のみ。実験条件ではない」と明記した**。`batch_size: 4` を選んだ唯一の理由は
> **T1 が8件・T2 が11件で、4 はどちらも割り切らない = 端数のバッチが実機で1度は通る**ことである。
> **`configs/smoke.yaml` は触っていない**(ADR-037 決定4)。
>
> **★未決 #25 は決着していない。**人間が決めるのは **(1) 値そのもの /
> (2) [MATCHED] にするか(全条件で揃えるか) / (3) バッチ1 対 バッチ N の一致確認の合否基準**。
>
> **★実機ではまだ1度も動かしていない。**左パディングを伴うまとめ生成がバッチ1と同じ応答を
> 返す保証は無い(貪欲デコードの同点で割れうる)。**確認は順1b の中で1度だけ取る。**
>
> **次にやるのは順1b の実機作業(RUNNER)である。**`configs/smoke1b.yaml` の
> `model.revision` は依然 `null` で、ポッド上の pull で埋める。
>
> **`results/` は空、GPU 時間 0、RunPod 未使用、事前登録の tag なし。**

> **★ 2026-08-28。PLANNER セッション。コードは1行も変えていない。**
> 人間の問い「メインの実行までに何をどの順で踏むか」に答えるために `plans/PLAN-004-phase0-route.md`
> §2 と実装を突き合わせた。**その過程で、手順表のどこにも書かれていない実装の穴を1件見つけた。**
>
> | 事実 | 場所 |
> |---|---|
> | `load_model_and_tokenizer` に `device_map` も `.to("cuda")` も無い。読んだ重みは **CPU** に載る | `code/eval/model.py:161` |
> | `.to(model.device)` はその CPU を指す。**`device` / `cuda` は `code/` にこの1箇所しか現れない** | `code/eval/generate.py:78` |
> | `build_generator` はプロンプトを**1件ずつ**ループする(バッチ生成が無い) | `code/eval/generate.py:55` |
>
> **帰結**: 順1b(19項目)は CPU でも終わるので「回った」ように見えるが、**GPU ポッドを借りる意味が無い。**
> **段階 C は評価プールが 10,760 項目**(`plans/PLAN-001-eval-battery.md` §5.1)で、
> バッチ1のままでは順6 が現実的な GPU 時間に収まらない。**順1b の前に潰す。**
>
> **人間はこの見立てを聞いたうえで「問題1を次のセッションで解決する」と決めた(2026-08-28)。**
> 次のセッションの作業は `logs/HANDOFF.md`。**GPU 時間の見積もりは会話で口頭に出しただけで、
> 実測ではない。文書には書いていない**(`CLAUDE.md` §2)。
>
> **`results/` は空、GPU 時間 0、RunPod 未使用、事前登録の tag なし。**

> **★ 2026-08-27(最新)。IMPLEMENTER セッション。順1 を完了した(完了条件 5/5)。**
> `pytest code/tests -q` → **506 passed**(427 → 506。**+79 件はすべて新規経路のテスト**)。
> **`results/` は空。実験結果の数値は1つも無い。GPU 時間 0。事前登録の tag なし。**
>
> **実装したもの**:
>
> | ファイル | 中身 |
> |---|---|
> | `code/eval/run.py`(配線) | `main` の `NotImplementedError` を外した。`--run-dir` を optional で追加。`evaluate_pool` / `evaluate_batch` / `execute` / `load_pool_items` / `response_builder` / `parse_response` / `prediction_record` / `metrics_payload` / `report_lines` |
> | `code/eval/sweep.py`(新規) | `M` を掃いて **`M` → `correct_rate` の対応表**を出す CLI(PLAN-001 §4.1.1 の手続き2)。`--dry-run` も持つ |
> | `code/eval/model.py`(改修) | `eval.num_repeats` の門を追加(**1 以外は null も含めて `ConfigError`**) |
> | `code/eval/battery/magnitude_sweep.py`(改修) | `SweepPlan` / `load_sweep_plan`。**冒頭の注記の誤りを訂正**(下記) |
> | `configs/template.yaml` / `configs/smoke.yaml` | `eval.magnitude_sweep.radii` / `.n_items_per_radius` / `.seed` を登録(template は **null**、smoke は ★smoke のみの小さい値) |
> | `infra/RUNPOD.md` §4 | `code.train.run` / `code.analysis.aggregate` を**未実装としてコメントアウト**し注記。`code.eval.run` を `--config` + `--run-dir` に訂正。掃引(5b)と「誰が書くか」の表を追加 |
> | テスト6ファイル(新規) | `test_eval_model` / `test_generate` / `test_artifacts` / `test_magnitude_sweep` / `test_run_real` / `test_sweep`。**モデルの重みは1度も読まない** |
>
> **訂正した誤り**: `magnitude_sweep.py` 冒頭が「`p2d` は t が 10 の倍数のとき `p2` と
> 一致するため**真値と規則適用値が割れない**」と書いていた。**誤りである。**それは
> 規則どうしの一致(`pool.is_indistinguishable`)であって真値との一致ではない。
> この実装が落としているのは後者だけである(前者を掛けるのは順4。ADR-035)。
>
> **エージェントが独断で決めたこと(#10〜#14)は `plans/PLAN-004-phase0-route.md` の
> 順1 の節にある。人間が一度見ること**(`CLAUDE.md` §8)。
> 前セッションの独断 #1〜#9 はそのまま実装した。

> **★ 2026-08-27(最新)。IMPLEMENTER セッション。順1 に着手し、部品4本を実装して中断した。**
> **順1 は未完了である。**`code/eval/run.py` の `main` は依然 `NotImplementedError` であり、
> **本実行はまだ1度も通っていない。**`code/eval/sweep.py` は存在しない。
> `pytest code/tests -q` → **427 passed**(増減なし。**新規モジュールのテストは1件も書いていない**)。
> **`results/` は空。実験結果の数値は1つも無い。GPU 時間 0。事前登録の tag なし。**
>
> **実装した部品(4新規 + 1改修)**:
>
> | ファイル | 中身 | 状態 |
> |---|---|---|
> | `code/eval/model.py`(新規) | `GenerationSettings` / `load_generation_settings`(**null は `ConfigError`**)/ `resolve_dtype` / `load_model_and_tokenizer`(transformers は関数内 import) | 実地確認済(smoke config で `model.name` が null → 例外) |
> | `code/eval/generate.py`(新規) | **生成関数の唯一の置き場**。`Generator` 型 / `model_input`(chat template)/ `build_generator` / `collect_responses`(本数の契約を検査) | 実地確認済(固定応答の差し替え・本数不一致で例外) |
> | `code/eval/artifacts.py`(新規) | `runs/<id>/` の成果物(config.yaml 完全コピー / git_sha.txt + git_diff.patch / env.txt / timestamp.txt / metrics.json / predictions/ / log.txt) | **未実地確認**(呼び出し側が無い) |
> | `code/eval/battery/magnitude_sweep.py`(新規) | `R(M)` から加算項目を抽出(PLAN-001 §4.1.1 の**手続き1 だけ**)。`domain_size` / `build_items` / `sweep_radii` | 実地確認済(M=9・6件・item_id に `radius9`) |
> | `code/eval/battery/numeric_sum.py`(改修) | `non_discriminating_rules` を新設し `_build_one` をそれ経由に。`build_bare_sum_items` / `_build_one` に `params` を追加 | 427 passed を維持 |
>
> **`code/eval/run.py` は HEAD に戻した。**docstring だけ「本実行は動く」に書き換えた状態で
> 中断しかけたが、**`main` が `NotImplementedError` のままなのでファイルに嘘が残る**
> (`CLAUDE.md` §7)。docstring と import の変更は破棄した。次セッションが本体ごと書く。
>
> **エージェントが独断で決めた設計(人間が一度見ること。詳細は `logs/HANDOFF.md`)**:
> 本実行の項目は `eval.anchor_manifest` の**親ディレクトリの `items.jsonl`** から読む /
> 生成を**バッチ化しない** / `--run-dir` を optional で受ける / **`model.revision` も必須**にする /
> `temperature > 0` のときだけ `do_sample` / `eval.few_shot_k` があれば例外 /
> `PRIMARY_MODEL` は定数として置くが**実行時に照合しない**

> **★ 2026-08-27(最新)。PLANNER 兼 IMPLEMENTER セッション。順0 を完了にした。**
> **ADR-034 / ADR-035 / ADR-036 を採択し、PLAN-002 §12-11 をコードに反映した。**
> `pytest code/tests -q` → **427 passed**(423 → 427。4件追加)。
> `python infra/preflight.py --config configs/smoke.yaml` の **`data_checks` 6項目すべて PASS**。
> **`results/` は空。実験結果の数値は1つも無い。GPU 時間 0。事前登録の tag なし。**
>
> | ADR | 内容 |
> |---|---|
> | **ADR-034** | `p2`/`p2d` 判別不能の除外を **`K` の抽出母集団には掛けない**。掛ける先は**評価項目**。真値との偶然一致の除外は `K` に残す |
> | **ADR-035** | T1 は素の書式のまま + **「指示付き T1」を副次セル**(`id` × carry/nocarry の2セル・n=40 = **80 項目**。探索的、主軸のモデルに入れない)/ 被演算子 1 の除外は**評価項目のみ**全タスク型に広げる(`K` には広げない) |
> | **ADR-036** | **G7 を落とす**(案 B)/ Feucht et al. (2026) は **Intro の対立軸としてのみ引用**(引用そのものは消さない) |
>
> **コードの変更(`code/data_gen/ft_data.py`)**:
> - `generate` 手順2b から `indistinguishable_rule_pairs` を外した。**偶然一致の除外は残した**
> - manifest に **`exclusions.indistinguishable_rule_pairs_applied_to: "eval_items_only"`** を新設。
>   `schema_version` を **1 → 2**。引数名 `lesion_pairs_excluded` → `indistinguishable_rule_pairs`
> - `indistinguishable_pairs_of` は残した。**`generate` は除外に使わず manifest への記録にだけ使う**
>
> **テストの変更**:
> - `test_design_facts.py` に **本番経路 `generate` を通すテストを追加**(母集団 4,309 /
>   `K_main` の carry **393** / `t ≡ 0 mod 10` が訓練に残ること)。**食い違いの再発を経路ごと縛る**
> - `test_ft_data.py`: `digit_modulus` を落としても `K` は動かなくなった(ADR-034)ので
>   その事実に書き換え、**代わりに不動点を持つ `arb` 表で偶然一致の除外が生きていることを固定**
>
> **数え上げの訂正**(`coverage_seed = 20260823`。前セッションは seed 0 の数を書いていた):
> `id` セル候補は **1,808 組(carry 393)**、被演算子 1 を除くと **1,776 組(carry 386)**。
> **要求 520 組(carry 240)に対してなお 3.4 倍/1.6 倍の余裕があり、結論は変わらない。**
> `K` が張る和は **170 種**。上4行(母集団 4,309 / carry 393 / 和 174 種 / 154→170)は
> `coverage_seed` に依らないが、**`id` 候補の数だけはシードに依る**(seed 0 なら 1,821)。
>
> **追随させた文書**: `logs/DECISIONS.md`(ADR-034/035/036 + ADR-022 決定3 と ADR-029 根拠表 7,916 に注記)/
> `plans/PLAN-002-ft-data.md`(§4.2.1 の ⚠️ を「旧実装の帰結」に書き換え・穴の数 20 → **17** に訂正 /
> §5.1 と §12-3 を廃止 / §12-11 を決着 / §4.9.3 #10・#12・#13 に注記・#13c 追加)/
> `plans/PLAN-003-redesign.md`(§4.7 / §8.4 / §11 の #11・#13・#16・#17・#18・#19)/
> `plans/PLAN-004-phase0-route.md`(手順表 順0 = **完了** / §3 / §7)/ `configs/template.yaml`(コメント訂正)/
> `Documents/02_RELATED_WORK.md`(Feucht 行)/ `Documents/06_THREATS.md`(T13 の G7 部分)
>
> **⚠️ 順4 への申し送り(実装していない)**: §11-18 の副次セル(群名未定。`SUPPORTED_GROUPS` は現状4群)と
> §11-19 の評価側除外は**順4 の仕事**である。ADR-035 に仕様だけ書いた。
> **`id` セルの母集団は `K` そのものではなくなった**(1,808 / 2,000)ことも順4 で明示する。

> **★ 2026-08-27(最新)。PLANNER セッション。順0 の3判断が人間の回答で決着した。**
> **コードは1行も変更していない。**`pytest` 未実行(変更が無いため)。`results/` は空。GPU 時間 0。
>
> | 判断 | 人間の決定 | ADR |
> |---|---|---|
> | PLAN-002 §12-11(`p2d` 判別不能の除外を `K` に掛けるか) | **掛けない** | **未執筆(ADR-034 予定)** |
> | §11-18(T1 の答え書式の指示) | **現状維持 + 副次セル** | **未執筆(ADR-035 予定)** |
> | §11-19(被演算子 1 の除外範囲) | **評価項目のみに広げる** | **未執筆(ADR-035 予定)** |
> | §11-11(G7 の扱い) | **B(落とす)** | **未執筆(ADR-036 予定)** |
> | §11-16(Feucht の位置づけ) | **(a) Intro の対立軸としてのみ引用** | **未執筆(ADR-036 予定)** |
>
> **帰結**: **#13(`table[1]` の穴)は消滅**(G7-H の `x=0,n=1` が唯一の理由だった)/
> **#17(Nikankin の原典確認)が必須化**(対立軸を単独で支えることになる)/ レビュー **R7 は不要**/
> **PLAN-002 §5.1(G7 165 項目)は廃止**。
>
> **判断の材料として組合せ論的な数え上げを回した**(実験結果ではない。`results/` には置かない):
> 「掛けない」で main 抽出母集団 4,309 組・`K` の carry **393**(21.8% → 19.7%)・
> `K` が張る和 **170〜171 種**(掛けると 154〜155 種)・`id` セル候補 **1,821 組**。
> **`id` 要求 520 組(carry 240)に対し 1.6 倍の余裕があり、埋まらないセルは無い。**
> 被演算子 1 を評価側で除いても `id` 候補 1,788 組・評価主域 −1.0% で影響しない。
> **`K` にも 1 を除くと答え1桁の層が 6 → 3 組に潰れるため採らなかった。**
>
> **⚠️ 実装と設計事実テストの食い違いを見つけた。**[test_design_facts.py:262](code/tests/test_design_facts.py)
> と PLAN-003 §4.7 の「carry 約 391 組」は **`p2d` 除外を通さない**母集団の数だが、
> [ft_data.py:636-653](code/data_gen/ft_data.py) の本番経路は通していた。`configs/smoke.yaml` が
> `digit_modulus` を持たないので発火せず表に出ていなかった。**決定が「掛けない」なので直すのはコード側。**
> **`configs/template.yaml:57-61` のコメントも逆のことを書いている。**
>
> **PLAN-002 §4.2.1 の「`t ≡ 0 mod 10` の穴(20 個の和)」は 17 が正しい**(`[2,198]` の 10 の倍数は
> 19 個で、うち 20 と 70 は既に `T_hold`)。
>
> **新しい未決 #22**: **LoRA アダプタを `runs/<id>/` に残すか。**`infra/RUNPOD.md` §4 の必須成果物に
> 無く、`adapter` / `アダプタ` は主要4文書のどこにも現れない。**このままだと 40 run の後に評価を
> 足すには再訓練が要る。**

> **★ 2026-08-27。PLANNER セッション。`plans/PLAN-004-phase0-route.md` を新設した。**
> **コードは1行も変更していない。**`pytest` 未実行(変更が無いため)。`results/` は空。
>
> 人間が「段階 C(小さな実験)を先にやるべきか」と問うたので、**コードと config を実地確認**した。
> 答えは「先にやるべきだが、いまは回せない」。**回せない理由が3つ見つかった。**
>
> | 判明した事実 | 場所 |
> |---|---|
> | **本実行が未実装** | `code/eval/run.py:396` の `NotImplementedError`(既知)。**ただし実装自体は人間の入力なしで書ける** |
> | **桁数掃引の入口が無い** | `sweep` は `code/eval/battery/t3_comparison.py:228` の**閾値掃引(R8)専用**。PLAN-001 §4.1.1 の桁の掃引は**未実装** |
> | ~~**`code/train/` と `code/analysis/` が空**~~ | **★2026-08-27 解消(順8 の 8-1〜8-5)。**`code/train/`(settings / data / run / lora)と `code/analysis/aggregate.py` を実装した。**ただし訓練の本実行は #22 の門で止まる**(8-6 待ち)。**段階 E(パイロット)までの距離は段階 B の判断より長い可能性がある**という読みは変わらない |
> | **段階 B の表に無い決定が2件** | **#20 生成設定**(`configs/template.yaml:28-33` が全部 `null`)/ **#21 T1b・T3 の本番評価テンプレート**(`data.eval_template_set` がどの config でも `null`)。**どちらも段階 C を回すのに必須** |
> | **`infra/RUNPOD.md` §4 が実在しないコマンドを指す** | `code.train.run` / `code.analysis.aggregate` は未実装。`code.eval.run --run-dir` も実際の CLI は `--config` |
>
> **成果物**: `plans/PLAN-004-phase0-route.md`(順0〜順9 + 完了記録 + 順序の罠)。
> **順序の罠として明示したこと**: #9 の 0.70 と `θ` は**実測より前に決める**
> (後に決めると「どのセルを落とすかを見てから基準を決めた」ことになる)。
> `θ` の**決定規則**を先に凍結すれば C-1 と C-2 を同じポッドで連続して回せる。
>
> **前セッションの HANDOFF の「単独で進められる実装作業は無い」は正確ではなかった。**
> 本実行の実装は GPU も人間の入力も要らない(値を config から読み、`null` なら例外で止める形にすればよい)。
> **人間が順1 に着手する方針を採ったので、次セッションはその実装である。**

> **★ 2026-08-26(最新)。IMPLEMENTER セッション。A-6 = 評価プールの CLI。★段階 A 完了。**
> `pytest code/tests -q` → **405 → 423 passed**。**`infra/preflight.py` の
> `data_checks` 6項目がすべて PASS になった**(検査6 = format hash / 検査8 = coverage_k floor)。
>
> | 変更 | 中身 |
> |---|---|
> | **ADR-033(人間が採択)** | ★A-5 が回避していた未解決の決着。プール manifest を `reference_rules`(加算側)と **`specificity_reference_rules`** の**2欄に分ける**。混ぜる案は「`eval.reference_rule: spec_sub` の誤指定を検査が素通しする」ため却下 |
> | `code/data_gen/eval_pool.py`(新規) | 評価プール(`items.jsonl` + `manifest.json`)を書き出す入口。形は `ft_data.py` に揃えた |
> | `code/eval/battery/build.py`(新規) | 明示リストから4群の項目を作るディスパッチャ。`run.py` から移した(`eval_pool.py` と2箇所で要るため) |
> | `code/data_gen/pool.py` | `build_manifest` に必須引数2つ: `specificity_reference_rules` と **`fill`**(このプールをどう埋めたか) |
> | `code/eval/run.py` | `dry_run` が**特異性側にも `validate_reference_rule` を掛ける**。項目の `pool_id` は `data.pool_id` から取る |
> | `code/data_gen/ft_data.py` | CLI に **`--condition`**(ADR-033 決定5)。条件ごとに config を複製すると写し間違いでバイト一致が壊れる |
> | `configs/smoke.yaml` | `data.matched_manifests` / `eval.anchor_manifest` / `eval.cells` / `eval.pool_items`(`dry_run_items` の **YAML アンカー**)/ `eval.pool_seed` / `eval.extrapolation_radius` / `eval.extrapolation_run_id` |
> | `.gitignore` | `data/generated/*` がディレクトリごと除外していたため **`manifest.json` の再包含が効いていなかった。**「manifest だけ追跡する」という意図が1件も実現していなかった |
>
> **⚠️ プールはサンプリングしていない。**`eval.pool_items` の明示リストで埋めている。
> **外挿域の上限 `M*` が未決(承認待ち-15)で `extrap` セルが原理的に埋まらない**ため
> (ADR-033 決定4)。manifest の `fill` にその事実を記録した。
> **本実行(モデルの読み込みと生成)は依然 `NotImplementedError`。**

> **2026-08-26。IMPLEMENTER セッション。A-5 = `run.py` の数値経路を配線した。**
> commit `47d2cda`。`pytest code/tests -q` → **390 → 405 passed**。
>
> | 変更 | 中身 |
> |---|---|
> | `code/eval/run.py` | `parse_numeric_response(text, elicitation)` を追加(`direct` / `cot` の2経路)。`parse_boolean_response` と同じ形 |
> | 同上 | `dry_run` を**4群のディスパッチ**に置き換えた。群ごとに項目生成器・応答型・文面の出どころ・参照規則の渡し方が違うので一括ループにしていない |
> | 同上 | `scoring_batches` を新設。**採点バッチは群と一致しない** —— 特異性対照だけ category(`spec_sub` / `spec_mul`)で割る(§4.6) |
> | 同上 | `load_group_templates` を新設。**`bare_sum` だけ `data.prompt_template` から組む**(評価アンカー。検査6) |
> | 同上 | `dry_run_entries_by_group` を新設。`eval.dry_run_items` の各項目に **`group` を必須**にした |
> | 同上 | 返り値を `report["by_response"]` → **`report["by_batch"][バッチ名]`** に変えた |
> | `configs/smoke.yaml` | `eval.batteries` を4群に、`dry_run_items` を 6 → **17 件**に |
> | `configs/templates/smoke.yaml` | `word_problem`(5場面)/ `specificity`(2演算)の**配線確認専用の仮文面**。ADR-032 の確定文面は書き写していない |
> | `configs/template.yaml` | `eval.batteries` のコメントを4群に更新 |
>
> ~~**⚠️ 評価プールを書き出す入口が無いので検査6・8 は FAIL のまま**~~
> → **2026-08-26 に A-6 で解消**(上のブロック)。
>
> ~~**⚠️ 独断で決めずに回避した点が1つある**(特異性対照の `validate_reference_rule`)~~
> → **2026-08-26 に ADR-033 で決着**(人間が採択)。

> **2026-08-26。IMPLEMENTER セッション。項目生成器を実装した。**
> **Phase 0 タスク2 の生成器部分が入った**(PLAN-003 §4.2 / §4.3 / §4.6)。
> `pytest code/tests -q` → **341 → 390 passed**。
>
> | 新規 / 変更 | 中身 |
> |---|---|
> | `code/data_gen/prompt_format.py`(新規) | 訓練と評価アンカーが共有する書式ブロック。**7規約は config に出さない** |
> | `code/data_gen/hashing.py`(新規) | `canonical_json` / `sha256_text` を `ft_data` から移した。**畳み方を1箇所に**する |
> | `code/data_gen/pool.py` | `build_manifest` に `prompt_format_block` / `item_exclusions` を**必須引数**として追加 |
> | `code/eval/battery/numeric_sum.py`(新規) | **T1(裸の計算式)と T2(文章題)。**被演算子 1 の除外と場面テンプレートの割当 |
> | `code/eval/battery/specificity_control.py`(新規) | **減算・乗算の対照(§4.6)。真値が a+b ではない**ので別モジュール |
> | `code/lesion.py` | `SubtractionOffsetLesion` / `ProductOffsetLesion` と専用の factory(§7.1 改修③) |
> | `code/data_gen/battery_items.py` | `SUPPORTED_GROUPS` に `bare_sum` / `word_problem` / `specificity` |
>
> **⚠️ 生成器だけでは評価は回らない。**`code/eval/run.py` には
> `parse_boolean_response` しか無く、**数値経路(cot → numeric)が未実装**である。
> **評価プールを書き出す入口(CLI)も無い**ので、`eval.anchor_manifest` /
> `eval.cells` を書ける config はまだ存在せず、**preflight の検査6・8 は FAIL のまま**。
> 詳しくは下の「引き継ぎ」と `logs/CHANGELOG.md` 2026-08-26。

> **2026-08-26。PLANNER セッション。承認待ち-6 が決着した → ADR-032。**
> commit `555dd5c`。**コードは1行も変えていない**(`pytest code/tests -q` → **341 passed**)。
>
> 人間の回答: 「5本ともこの文面で確定。D1 は入れる / D2 は 1 を除外 / D3 はそのまま」。
>
> | 決定 | 内容 |
> |---|---|
> | 1 | T2 の5テンプレート文面を確定(物の個数 / 人数 / 距離 / 金額 / 時間) |
> | 2 | 問いの語は5本で完全一致 `How many {単位} in total?`。変わるのは場面と単位語だけ |
> | 3 | 末尾に同一文 `End your reply with "Answer: <number>".`。**CoT は禁止しない** |
> | 4 | **T2 の項目生成から被演算子 1 を除外**(`1 apples` が非文) |
> | 5 | 群名 `word_problem` / category `t2_count` `t2_people` `t2_distance` `t2_money` `t2_time` |
>
> 正本は **`configs/templates/t2.yaml`**(新設)と `plans/PLAN-003-redesign.md` §4.3。
> **段階 A の最後のブロッカーが外れた。次は項目生成である。**
> **新規の承認待ち #18 / #19 を立てた**(下の「段階 B」表)。どちらも凍結までに要る。

> **2026-08-25。PLAN-003 §7.1 / §7.2 の D-3 後始末を完了した。**
> **これで段階 A のうち人間の入力なしで進む作業は無くなった。**
> commit `a604453`(改名 + 改修①〜④)/ `7aaa9fe`(パーサの日本語語彙除去)。
>
> | 作業 | 結果 |
> |---|---|
> | 改名 | `code/eval/battery/g6_comparison.py` → **`t3_comparison.py`**、`test_battery_g6.py` → **`test_t3_comparison.py`**。追随: `run.py` / `battery_items.SUPPORTED_GROUPS` / `configs/smoke.yaml` / `configs/templates/smoke.yaml` / `configs/template.yaml` |
> | 改修③ `arb` を `ans_in` に限定 | `is_defined_for` でガード。**定義域外の規則はその項目の評価から外れる(既定値で埋めない)。**`build_items` は判別可能性を問わず、`to_response` は `rule_values` に入れない。定義域外で `answers` を呼ぶと **`UndefinedRuleValueError`** |
> | 改修② 英語化 | `configs/templates/smoke.yaml` の4文面と `run.DRY_RUN_RESPONSES` |
> | 改修④ T1b の `category` | `category` = **タスク型 × 極性**(`t3_gt` / `t3_lt` / `t1b_gt` / `t1b_lt`)。`build_items` の引数は `polarity=` → **`category=`** |
> | 改修① R8 掃引モード | `build_items(..., sweep=True)`。判別可能性の強制と閾値の許容表を外す。**θ の水準集合はコードに持たない**(実験条件) |
> | D-3 後始末 | `base.ANSWER_MARKERS` から日本語5語 / `boolean.py` の `_YES_JA` `_NO_JA` を除去。**`parsers/japanese.py` と `test_parsers_japanese.py` を削除**(`wordform.py` は判定どおり**残した**) |
>
> **`group` の名前は仕様が曖昧だったので `"comparison"` にした。人間が覆してよい。**
> PLAN-003 §7.1 は「タスク型の名前を差し替える」、ADR-026 は「`category` を追加する」と
> 書いており、両立させるには group をタスク型名にできなかった(T1b の項目が group `t3` に
> 入って読み違えを招く)。理由は `logs/CHANGELOG.md` 2026-08-25 の項に記載。
>
> **`pytest code/tests -q` → 340 → 362 → 341 passed**(2026-08-25 実測)。
> 内訳: `test_t3_comparison.py` **18 → 39**、`test_run_dry_run.py` **9 → 10**、
> `test_parsers_boolean.py` **25 → 26**、`test_parsers_japanese.py` **22 → 削除**。
> `python -m code.eval.run --config configs/smoke.yaml --dry-run` は通る(6 項目)。
> **`results/` は空。RunPod 未使用(GPU 時間 0)。事前登録の tag なし。**
>
> **次の PLANNER セッションへの申し送り(このセッションで新たに見つけたもの)**:
> - **`test_parsers_numeric.py` の `("答えは 7 です", 7)` / `("答え: -3", -3)` は、
>   `ANSWER_MARKERS` から日本語が消えた今「印で切り出せた」ではなく
>   「文中に数が1つしかない」で通っている。**テストの意味が変わった。§7.2 の
>   「そのまま使う」判定を見直すこと
> - **`cot.py` の `CONCLUSION_MARKERS` の日本語は残してある**(§7.1 が「そのまま使う」)。
>   英語出力では発火しない死語彙。**落とすかどうかは PLANNER の判断**
> - `configs/template.yaml` の `eval.batteries` コメントを `[comparison]` に直した。
>   **群名の全リストは #11(G7)の決着待ちのままである**

> **2026-08-26。承認待ち-6(T2 の5テンプレート文面)が決着した → ADR-032。**
> 人間が「5本ともこの文面で確定。D1 は入れる / D2 は 1 を除外 / D3 はそのまま」と回答した。
> **確定内容**: 場面5種(物の個数 / 人数 / 距離 / 金額 / 時間)、問いの語は5本で完全一致
> (`How many {単位} in total?`)、**末尾に `End your reply with "Answer: <number>".` を置く**、
> **T2 の項目生成から被演算子 1 を除外する**(`1 apples` が非文)、群名 `word_problem`。
> 正本は **`configs/templates/t2.yaml`** と PLAN-003 §4.3。
> **段階 A の最後のブロッカーが外れた。次の作業は項目生成である。**
> **コードは1行も変えていない。**`pytest code/tests -q` → **341 passed**(2026-08-26 実測)。
> `results/` は空。RunPod 未使用(GPU 時間 0)。事前登録の tag なし。
> **新規の承認待ちを2件立てた: #18**(T1 にも答え書式の指示を足すか。ADR-032 決定3 は
> タスク型の軸に「指示の有無」を乗せる)/ **#19**(被演算子 1 の除外を全タスク型に広げるか)。
> **どちらも凍結までに要る。**

> **2026-08-25。実装順 4(`infra/preflight.py` の §4.8.1 検査)を完了し、
> コンテキスト超過で切った(hook `context-guard` が 228k / 閾値 140k を警告)。**
> **次のセッションの作業は `logs/HANDOFF.md` に書いてある** ——
> **PLAN-003 §7.1 / §7.2 の D-3 後始末**(`g6_comparison.py` → `t3_comparison.py` の改名と
> 改修①〜④、パーサから日本語語彙を外す、`japanese.py` を捨てる)。
> **段階 A のうち人間の入力なしで進むのはこれが最後の塊である。**残るのは項目生成だけで、
> それは**承認待ち-6(T2 の5テンプレート文面)で止まっている**(→ **2026-08-26 決着。ADR-032**)。
> **コードは preflight とテスト以外変更していない。**`pytest code/tests -q` → **340 passed**
> (2026-08-25 実測)。`results/` は空。RunPod 未使用(GPU 時間 0)。事前登録の tag なし。

> **2026-08-23。`plans/PLAN-003-redesign.md` §10 の追随表に従って設計文書を同期した。**
> 書き換えた文書: `Documents/05_STATISTICS.md`(**§2 主要評価項目 / §3.2 モデル指定 / §4 階段**)、
> `plans/PLAN-001-eval-battery.md` **§5.1 セル表**、`Documents/06_THREATS.md` **T1 対策表**、
> `Documents/04_EXPERIMENT_PLAN.md`(**Phase 0 タスク・Go/No-Go / 条件のシード配分 / Phase 2 の注記**)、
> `Documents/03_OPEN_QUESTIONS.md` **Phase 1**。
> **旧・記述はすべて打ち消し線 + 理由 + 日付で残した**(`CLAUDE.md` §2)。
> **新たに未追随を1件発見した** → 下の「現在のブロッカー」を参照。
> **コードは1行も変更していない。**`pytest code/tests -q` → **227 passed**(本セッションで実測)。
> `results/` は空。RunPod 未使用(GPU 時間 0)。

> **2026-08-23。人間が PLAN-003 §11 の骨格 #1〜#5 を決定し、
> `logs/DECISIONS.md` に ADR-024 / 025 / 026 / 027 / 028 を採択した。**
> 反映先: `plans/PLAN-003-redesign.md`(冒頭に承認状況、§3.1 / §3.3 / §3.4 / §4.1.1 / §4.5 /
> §4.7 / **§4.8 新設** / §6.1 / §6.2 / §6.4 / §6.5 / §7.1 / §9 / §10 / §11 / §12)、
> `plans/PLAN-002-ft-data.md` §4.1.3(**チャットテンプレートの決定を反転**)/ §5.2、
> `Documents/02_RELATED_WORK.md` §A.1 の注4。
> **コードは依然として1行も変更していない。**`results/` は空。
> 主な数値の変化: 主軸 1,080 → **1,560 項目** / FT run 35 → **40** / 交互作用 df 4 → **6**。

**設計の主軸が変わった。**人間が研究の関心を明示した——「LLM の計算がどのように行われているかを
解き明かす。それをもとに足し算の仕組みを変えると何が起きるかを見る」。すなわち**主軸は機構である**。
この転換を **ADR-018 / ADR-019** として採択した(2026-08-22、人間が「全部承認する」と回答)。

**本セッション(PLANNER)は `plans/PLAN-002-ft-data.md` を起草した。**ADR-019 の決定を
「この文書だけを読んで `code/data_gen/ft_data.py` が書ける」水準まで落とし、
`configs/template.yaml` / `Documents/04_EXPERIMENT_PLAN.md` / `plans/PLAN-001-eval-battery.md` を
追随させた。

**まだコードは1行も変えていない。**`pytest code/tests -q` → **227 passed**(前セッションのまま。
本 STATE の旧記載 221 は数え落としで、`logs/CHANGELOG.md` の 227 が正しい)。`results/` は空であり、
**実験結果の数値は依然として1つも無い。**

**本セッション(SCOUT)で Phase 0 #0 を完了した。**Feucht et al.(arXiv:2605.01148v1)の
abs / HTML 全文と、**論文扉頁が示す公式コード**(`github.com/goodfire-ai/arithmetic-wild`)を開き、
変種・revision・周期タスクの書式・オフセットの範囲を逐語転記した
(`Documents/02_RELATED_WORK.md` §A.1)。**ADR-008 を採択に更新した。**

**本セッション(PLANNER)で ADR-020 / 021 / 022 を採択した。**人間が
「未知の値に対して `arb` の意味がないのだから検証が不可能ではないか」と指摘したことが起点。

- **ADR-020**: `arb` を「構造の対照」から「**和への routing probe**」に再宣言。
  評価範囲を `ans_in`(C1/C2/C3/C5)に限定し、解析を**入れ子の2本**に分ける。
  **ズレ表は広げない**(広げると学習不可能な項目に規則値を与え、必然を結果として提示することになる)
- **ADR-021**: `t` 水準の被覆ラベル `t_seen` / `t_unseen` を新設(`arb` の解析でのみ層として使う)
- **ADR-022**: 第4条件 **`p2d`**(`t + 2 + (t mod 10)`)を追加。**人間が承認した実験条件の追加**。
  H3 の「構造 vs 記述長」の交絡を除く

**新規に見つかった穴(再現確認済)**: `arb` のズレ表の定義域 `t ∈ [2,198]` の外で
`ArbitraryLesion.apply` が `KeyError` を投げる。該当 **100,298 組**。
`eligible_pairs` が `p2`/`arb`/`x2` の和集合で除外を計算するため、**現状ではプール生成が落ちる**。

~~**次にやることは PLAN-002 §12 の9件を人間が承認したうえで、ADR-020/021/022 をコードに落とすこと**。~~
→ **2026-08-23 中断。ADR-023 により凍結した。**次にやることは**設計の再導出**である(冒頭の「★ 最優先」)。

**本セッション(CRITIC)で2つのことを行った。**

1. **先行研究に照らした設計価値レビュー**(`Documents/reviews/2026-08-23_design_value.md`)。
   依拠文献 14 本を原典ページで確認し、`Documents/reviews/papers_list.md` に分離。
   要点: **「概念か表層か」という層1の問いは文献側でほぼ答えが出かかっており**
   (wrapper 仮説・Reversal Curse・ripple effects)、**G1/G2 の監査は非 FT 版が既に存在する**。
   **空いているのは「FT の変更が既知の共有機構に落ちるか」と「和を鍵とする表が未見の対へ転移するか」**
2. **人間が研究の主軸を再宣言し、実験設計の全面的な見直しを宣言した**(**ADR-023**)

---

## わかっていること

### 文献から(出典は Documents/02_RELATED_WORK.md)

| 事実 | 出典 | 確度 |
|---|---|---|
| Llama-3.1-8B は「8月の6か月後」を底10加算(6+8=14)で解き、その機構を月・曜日・時刻・通常加算で共有している | Feucht et al. 2026 (arXiv:2605.01148) | ✅ 原典確認済。ただしプレプリント |
| **原典の解析対象は `meta-llama/Llama-3.1-8B`(base)。revision は示されていない** | 同上 §A.1.1。2026-08-23 転記 | ✅ これをもって **ADR-008 を採択**。ただし base は論文本文の明言ではなく**公式コードからの証拠** |
| **原典の対照タスクは `a+b=`、被演算子 `a, b ∈ [1,100]`** | 同上 §A.1.2 | ✅ **ADR-019 の訓練書式と訓練域 `[1,99]^2` は原典の部分集合になっている** |
| **周期タスクのオフセットは `1..2p`**(月 24 / 曜日 14 / 時刻 48)。**時刻は 24時制(法 24)** | 同上 §A.1.3 | ✅ PLAN-002 §5.1.2 の `n_max` と G7-H の欄がこれで埋まった |
| **素のモデルの月タスク正答率: 法を跨がない 100% / 跨ぐ 55.0%**。前剰余和 `[p,2p]` 帯で 68.1% | 同上 §A.1.4 | ✅ **G7 の前提(「8月の6か月後→２月」)はこの跨ぐ帯に入る。天井ではない** |
| 狭い FT が無関係な振る舞いへ広範に波及する(emergent misalignment) | Betley et al. 2025 | ⚠️ 書誌要確認 |
| LVLM に計数回路が存在し、視覚推論タスク間で大部分共有されている | Che et al. 2026 (arXiv:2603.18523) | ✅ 原典確認済。プレプリント |
| VLM の関係理解・語順感度は著しく弱い(bag-of-words 的) | Yuksekgonul et al. ICLR 2023 | ✅ 原典確認済 |
| テキストのみの LM の色語表現が CIELAB と構造整合する | Abdou et al. CoNLL 2021 | ✅ 原典確認済 |

### 自分たちの解析から

| 事実 | 根拠 |
|---|---|
| a⊕b = a+b+2 は結合的・可換で、φ(x)=x+2 により (Z,+) と同型。単位元は **−2**、a の逆元は **−a−4** | ✅ **コードで検証済**。`code/tests/test_algebra.py`(40 passed, commit f28a4e4)。offset=k 一般で成立 |
| a⊗b = 2(a+b) は結合的でない。ゆえに ×2 病変は整合した代替算術を定義しない | ✅ **コードで検証済**。両側単位元も持たないことを追加で確認。結合的なのは m ∈ {0,1} のときだけ |
| 加算のみを変えると環の公理が破れるため、完全に整合した世界は原理的に到達不可能 | ✅ **コードで検証済**。分配律が保たれるのは a=1 のときだけ。`3×(4+5)`→33 vs `(3×4)⊕(3×5)`→29 |
| **真値と規則適用値の偶然一致は `p2` では決して起きないが、`x2` では a+b=0 の項目で起きる** | ✅ コードで検証済。**新規に判明**。`CLAUDE.md` §6 の除外リストが x2 条件で必要 |
| **`K = 500` では評価プールが原理的に埋まらない。**被演算子を持つカテゴリの `id` セルだけで相異なる **560 組**(PLAN-001 §5.1 改訂後は **556 組**)を要求する(`fill_cells` はセル間で組を再利用しない) | ✅ 計算済。**組合せ論的性質であって実験結果ではない。`code/tests/test_design_facts.py` に固定すること**(PLAN-002 §4.9.3) |
| **訓練域 `[1,99]^2` の層別母集団**: 答えが1桁の組は **36 組(0.37%)**しかない。答えが3桁の組が **50.51%** を占める | ✅ 2026-08-22 計算(PLAN-002 §4.2.2)。`[-99,99]^2` で `\|t\| >= 100` が 25.0% だったのとは**別の集合の数字**。混同しない |
| **`oob_algebraic` に `t > 198` の組は存在しない** → **主要評価項目 G6 は負の和を測れない** | ✅ 同上(PLAN-002 §4.6.1)。`a,b <= 99` の帰結。**主要評価項目の限界として事前登録に書く** |
| **周期タスクの `carry × nowrap` セル**: 法 12 では 15 件、**法 7(曜日)では構成的に空**(`carry` は `x+n >= 8 > 7` を要求するので `carry ⟹ wrap`) | ✅ 同上(PLAN-002 §5.1.4)。G7 の `n = 15` はこの最小セルから決まった |
| **厳格な結合律規約(構成4対すべてが `id`)は `K` に約4乗で効く**。`K=1000` で 39 件、`K=2000` で 498 件 | ✅ 同上(PLAN-002 §4.5.3)。**先頭2項規約を採る根拠** |
| **繰り上がり層の密度は `[-99,99]^2` で 9.6%(3,820/39,601)、`[1,99]^2` で 20.0%(1,960/9,801)** | ✅ 同上 |
| **現行の外挿定義は答えの大きさを分離できない。**主域の 25% が3桁の答えを持ち、外挿域の 49.7〜66.4%(`M*` 依存)が主域と同じ答え範囲に落ちる | ✅ 同上。ADR-019 決定6 の根拠 |
| **訓練域を `[1,99]^2` にすると G2 の診断項目(`3+0` / `3+(-2)` / 逆元 / `0+0`)は構成的に必ず訓練域外になる** | ✅ 同上。ADR-019 決定3 の根拠① |

**「完全に整合した世界に到達できない」点は弱点ではなく設計の要。**問いが「整合しているか否か」から
「どこまで整合が伝播し、どこで破れ、モデルはそれに気づくか」という段階的測定に変わる。

### 設計の帰結(2026-08-23。ADR-020 / 021 / 022)

| 事実 | 根拠 |
|---|---|
| **`arb` の規則値は `t = a+b` の関数であり、一般化は `t` 水準で起きる。**現行の被覆ラベルはすべて `(a,b)` 水準なので粒度が合っていない | ADR-021。`code/lesion.py:103` |
| **`arb` は `ans_out` で原理的に検証不能。**`table[t']` は他エントリと独立なので `rule_rate ≈ 0` は数学的必然 | ADR-020 根拠1 |
| **`arb` は `ans_in` では検証可能で、しかも `p2` より強い機構的証拠を出す。**未見の組で `table[a+b]` を当てるには和を計算して引くしかなく、出力段の定数シフトでは達成できない | ADR-020 根拠2 |
| **`arb` の定義域外の候補は 100,298 組**(`oob·ans_out` 20,098 + `extrap_magnitude` 80,200)。`(-30,-40)` / `(150,150)` / `(0,0)` で `KeyError` を再現確認 | ✅ 実測 |
| **`K = 2000` は 197 個の `t` のうち 187〜190 個しか被覆しない**(`coverage_seed` 依存)。未被覆は両端に集中。`t_unseen` は `interp` 0.4% / `oob·ans_in` 5.9% / `extrap_pair` 4.1% | ✅ 計算済。組合せ論的性質 |
| **`p2d`(`t+2+(t mod 10)`)は全域・非結合的(84.8%)・単位元なし・真値と一致しない・`f(t)-t ∈ [2,11]`** | ✅ コードで検証済 |
| **`p2d` が `p2` と一致するのは `t ≡ 0 (mod 10)` のときだけ。**`D_train` の 981 組(10.0%)、主域の 3,961 組(10.0%)を除外する。**`carry` 層とは交わらない** | ✅ 同上 |
| **`p2d` の桁数が `p2` と違う `t` は 197 件中 9 件**(`t ∈ {4,5,6,7,89,94,95,96,97}`) | ✅ 同上 |
| **条件が 5 → 6 に増え、生成回数が 356,500 → 427,800(+20%)** | PLAN-001 §5.5 |

### repo の状態

| 事実 | 根拠 |
|---|---|
| `README.md` のディレクトリ構造が実在する。文書は `Documents/` / `logs/` / `infra/` / `plans/` に移動済み | commit f28a4e4 |
| git 管理下に入り、初回コミット済み。`CLAUDE.md` §1 の開始手順と §5 のコミット規約が使える | commit f28a4e4 |
| ~~`pytest code/tests -q` → **40 passed**~~ → ~~**227 passed**~~ → ~~**256 passed**~~ → ~~**427 passed**~~ → ~~**506 passed**~~ → ~~**589 passed**~~ → **615 passed**(2026-08-28 実測。順1b の前提 (a)(b)(c)) | `code/tests/` |
| **評価ハーネスの本実行が通る**(2026-08-27。順1)。`python -m code.eval.run --config <cfg> [--run-dir <dir>]` が項目を読み・生成し・4値分解を出して `runs/<id>/` に成果物を書く。桁数掃引は `python -m code.eval.sweep`。**生成関数は差し替え可能で GPU の無い環境でテストが通る** | `code/eval/run.py`、`code/eval/sweep.py`、`code/tests/test_run_real.py`、`test_sweep.py` |
| **本実行は「回せる」が「まだ回していない」。**`model.name` / `revision` / 生成設定(#20)が未決で `ConfigError` で止まる。**評価は LoRA アダプタを読まない**ので、数値は `model.name` の重みそのものに対するものであり、`metrics.json` の `adapter` は `null` である(★2026-08-27 訂正: 理由は「`code/train/` が未実装」ではなく**評価側がアダプタを読む経路を持たないこと**。訓練コードは 8-1〜8-4 で実装された) | `code/eval/model.py`、`code/eval/run.py` の `NO_ADAPTER_NOTE` |
| ~~⚠️ **本実行はモデルを GPU に載せず、1プロンプトずつ生成する**(2026-08-28 発見)~~ → **2026-08-28 に解消した。**`model.device` と `eval.batch_size` が **config の必須項目**(null は `ConfigError`)。`load_model_and_tokenizer` が `model.to(settings.device)` で載せ(**`cpu` も通る**)、`build_generator` が**左パディングでまとめ生成**する。`pad_token` を持たないトークナイザ(Llama-3.1 系)は **eos で代用**。**実際のデバイスとまとめ幅は `metrics.json` の `generation` に残る**。⚠️ **実機では未確認** —— 左パディングを伴うまとめ生成がバッチ1と同じ応答を返す保証は無い(貪欲デコードの同点)。**確認は順1b で1度取る(未決 #25)** | 2026-08-28。`code/eval/model.py` の `require_batch_size` / `prepare_tokenizer_for_batched_generation`、`code/eval/generate.py` の `split_into_batches` / `batched_generator` / `_generate_batch` |
| **訓練コードは「書けている」が「回せない」。**`python -m code.train.run --config <cfg> --seed <n> --dry-run` は通るが、本実行は **#22(アダプタを `runs/<id>/` に残すか)が未決**のため `ConfigError` で必ず止まる。**LoRA グリッドの値も未決**(`configs/template.yaml` の `train.*` は null) | `code/train/lora.py` の `ADAPTER_PERSISTENCE_UNDECIDED`、`code/train/settings.py` |
| **集約が通る。**`python -m code.analysis.aggregate --runs "<glob>"` が `runs/*/metrics.json` を条件×シードで並べる。**adapter=null / seed 未記録 / 5シード未満を必ず文にして出す** | `code/analysis/aggregate.py`、`code/tests/test_aggregate.py` |
| `infra/preflight.py` が実行でき、`infra/RUNPOD.md` §3 の全項目を報告する | ローカルで実行確認済 |
| `code` パッケージ名は標準ライブラリと衝突する。shim で共存させている | ADR-013。壊れると **pytest 自体が起動しない** |
| **PLAN-001 の仕様が確定**。外挿域は実測定義(§4.1.1)、内挿ホールドアウトは `K` の補集合(§4.2)、パイロット専用プールを分離(§4.6) | 2026-08-22(commit 8d7d4a2)。`plans/PLAN-001-eval-battery.md` |
| **`rule_rate` は固定参照規則に対して定義する**(主要評価項目では `p2`)。`metrics.json` は参照規則ごとに独立した4値ブロックを持ち、**各ブロック内で合計 1.0** | **ADR-016**(`logs/DECISIONS.md`) |
| `configs/template.yaml` に `data.coverage_k` / `eval.reference_rule` / `eval.elicitation` を追加。**3項目とも `null`** | 2026-08-22(commit 8d7d4a2)。YAML のパースを確認済 |
| セッションの引き継ぎが手順化された。skill `handoff` と hook `infra/context_guard.py` | ADR-015。**hook の発火は未検証**(次プロンプトでしか分からない) |
| **出力パーサ5モジュールが動く**(`numeric` / `wordform`(凍結)/ `boolean` / `cot` / 共通の `base`)。各モジュールに負例テストがある。~~`japanese`~~ は 2026-08-25 に削除(D-3 英語統一) | commit 28fafe5 → 7aaa9fe。`code/tests/test_parsers_*.py`。抽出規則は PLAN-001 **§5.4.1**(★人間の確認待ち) |
| **項目プールの対水準の機構が動く**(値域 / 除外 / 繰り上がり層 / 被覆ラベルの実行時付与 / pilot-main 分割 / ハッシュ) | commit 00fe528。`code/data_gen/pool.py`、`test_pool.py`(27件) |
| **プール生成器が ADR-020 / 021 / 022 に追随した**(2026-08-24)。`Lesion.is_defined` による定義域ガード / 被覆ラベル4値 + 答え域ラベル / `label_t_coverage` / `DigitOffsetLesion`(`p2d`)と `is_indistinguishable` | `logs/CHANGELOG.md` 2026-08-24。`code/lesion.py`、`code/data_gen/pool.py`、`code/eval/run.py` |
| **ラベルの本番スケール件数が ADR-020 / 021 の表と一致する**(組合せ論的事実。実験結果ではない)。`id+interp` 9,801 / `oob·ans_in` 9,702 / `oob·ans_out` 20,098 / `extrap_pair` 39,400 / `extrap_magnitude` 80,200、**`arb` 定義域外 100,298** | 2026-08-24 に実装で検算。`M*` 非依存分は `test_pool.py` が固定 |
| ~~⚠️ 評価側の `arb` 定義域ガードは未実装~~ → **2026-08-25 に解消。**`g6_comparison.py` は **`t3_comparison.py`** に改名され、`is_defined_for` が定義域外をガードする(`arb` の評価は `ans_in` に限定) | commit a604453。ADR-020 決定2。PLAN-003 §7.1 の改修③ |
| **`ident`(および `offset=0`)を除外集合・参照規則に指定すると例外で止まる。名前でなく振る舞いで検出する** | ADR-016 の未検証・リスク①への対応。`DegenerateReferenceRuleError` |
| **除外に使った参照規則の集合を manifest に記録し、`eval.reference_rule` がそこに含まれることを検査する** | ADR-016 の未検証・リスク②への対応。`scoring.validate_reference_rule` |
| **4値分解は参照規則ごとの独立ブロックで、合計 1.0 は各ブロック内で成立する。合計が合わない分解は構築時に例外** | ADR-016。`code/eval/scoring.py`、`test_scoring.py` |
| **G6(主要評価項目)の項目構成が動く。**§5.1 が認めた (極性, 閾値オフセット, `t` の下限) では **p2 / x2 / arb すべてで真値と規則値の答えが割れる** | ✅ **コードで検証済**。`test_battery_g6.py`。arb が割れるのは §4.4 の制約2に依存する |
| **`python -m code.eval.run --config configs/smoke.yaml --dry-run` が通る。**モデルは読まない | commit a30835f。README のクイックスタートのコマンド |
| **T1 / T2 の項目生成が動く**(`code/eval/battery/numeric_sum.py`)。被演算子 1 の除外(ADR-032 決定4)/ 場面テンプレートの内容依存の割当 / 判別可能性の生成時強制 | 2026-08-26。`test_numeric_sum.py`(24件) |
| **特異性対照の項目生成が動く**(`code/eval/battery/specificity_control.py`)。参照規則は `a−b+offset` / `a×b+offset`。**加算の参照規則を渡すと止まる** | 2026-08-26。`test_specificity_control.py`(14件)。PLAN-003 §4.6 |
| **訓練と評価アンカーが同じ書式ブロックを共有する**(`code/data_gen/prompt_format.py`)。~~manifest を書き出す入口がまだ無く検査6 は FAIL~~ → **2026-08-26 に `eval_pool.py` が書き出すようになり検査6 は PASS** | 2026-08-26。`test_prompt_format.py`(9件)。PLAN-002 §4.8.1 検査6 |
| ~~⚠️ **T1 / T2 / 特異性対照は生成できても採点まで回らない。**~~ → **数値経路(cot → numeric)を配線した。**`--dry-run` は4群とも通り、4値分解が出る。**採点バッチは群と一致しない**(特異性対照だけ category で割る) | 2026-08-26。commit `47d2cda`。`code/eval/run.py` の `parse_numeric_response` / `scoring_batches` |
| **評価プールを書き出す入口が動く**(`code/data_gen/eval_pool.py`)。`items.jsonl` + `manifest.json` を書き、**preflight の `data_checks` 6項目がすべて PASS**(検査6・8 を含む) | 2026-08-26。`test_eval_pool.py`(18件)。ADR-033 |
| ⚠️ **プールはサンプリングしていない。**`eval.pool_items` の明示リストで埋めている。外挿域の上限 `M*` が未決で `extrap` セルが原理的に埋まらないため(**ADR-033 決定4**)。manifest の `fill` にその事実が記録される | 2026-08-26。`eval_pool.py` の `FILL_EXPLICIT_LIST`。承認待ち-15 の決着待ち |
| ⚠️ **本実行(モデルの読み込みと生成)は依然 `NotImplementedError`。**4群が通るのは `--dry-run` の経路だけである | 2026-08-26。`run.py` の `main`。段階 C 以降 |
| ~~⚠️ 特異性対照だけ `validate_reference_rule` を通していない~~ → **2026-08-26 に決着(ADR-033。人間が採択)。**プール manifest は `reference_rules`(加算側)と **`specificity_reference_rules`** の**2欄に分ける**。`dry_run` は両方に検査を掛ける | 2026-08-26。ADR-033 決定1・2。`pool.build_manifest` / `run.py` |
| ~~`pytest code/tests -q` → **390 passed**~~ → ~~**405 passed**~~ → **423 passed**(2026-08-26 実測) | +18 = `test_eval_pool.py`(A-6) |
| ~~`pytest code/tests -q` → **227 passed**~~ **(古い行。上の 423 が現行)** | 2026-08-26 に整理。内訳は当時の記録として残す: 代数 36 + shim 4 + パーサ 107 + プール 33 + 採点 21 + G6 18 + dry-run 8 |
| **ruff / black はこの環境に未インストール。**整形は手作業(行長 100 以下は機械的に確認済) | ポッドを立てた時点で `pip install -e .[dev]` して掛け直す |
| **設計の主軸を機構線に寄せた。**モデル変種は原典転記、主要指標は強制選択+自由生成の併走、**G7(周期的概念への転移)を副次の最上位に追加** | **ADR-018**(2026-08-22、人間が全部承認) |
| **訓練プロンプトは裸の式 `a+b=` 一形式。訓練域は `[1,99]^2`。被覆ラベルは4値。`K >= 560`。外挿は2分割** | **ADR-019**(同上) |
| **`plans/PLAN-002-ft-data.md` が起草された。**訓練プロンプトの1文字単位の書式 / `K` 組の層別サンプリング(繰り上がり × 答えの桁数、比例配分)/ `train.scope` / 被覆ラベル4値 + 答え域ラベル2値 / 外挿の2分割 / manifest schema / G7 の項目構成(165 項目)/ G0 の新設提案 | 2026-08-22(このコミット)。**§12 に承認待ち6件** |
| `configs/template.yaml` の `train.cot_mode` → **`train.scope`** に置換済。`data.pool_split_seed` / `coverage_seed` / `sample_seed` / `pool_id` を追加(すべて `null`) | 同上。YAML のパースを確認済 |
| `Documents/04_EXPERIMENT_PLAN.md` §0「最低2系統」と Phase 1「FT データ」に**打ち消し線 + 理由 + 日付**を入れた | 同上(`CLAUDE.md` §2) |
| `plans/PLAN-001-eval-battery.md` §4.1 / §4.2 / §4.4 / §4.6 / §5.1 / §5.5 / §8 / §13 を改訂。**事前登録は未凍結(tag なし)なので打ち消し線は使っていない** | 同上。項目数は 1,980 → **3,565**、`id` 要求は **556 組** |

---

## わかっていないこと

詳細と対応コードは `Documents/03_OPEN_QUESTIONS.md` の表を参照。要点のみ:

| # | 未知 | 状態 |
|---|---|---|
| Q1 | +2 病変を install したモデルは、単位元を −2 と報告するか | 未着手 |
| Q2 | 病変は表記(`3+4` / `three plus four` / 文章題)に依存するか | 未着手 |
| Q3 | 数を出力しない比較質問(「3+4 は 8 より大きい?」)に病変が乗るか | 未着手 |
| Q4 | 整合性はどこで破れるか。モデルはその矛盾に気づくか | 未着手 |
| Q5 | 隣接演算(減算・乗算)へ漏れるか | 未着手 |
| Q6 | 構造的規則(+2)と恣意的ズレで、獲得コストと汎化に差があるか | 未着手 |
| Q7 | 言語側のみの FT が視覚由来の被演算子に波及するか | Phase 3。未着手 |
| ~~Q-3~~ | ~~⊕ の群構造と ⊗ の非結合性は正しいか~~ | **解決**(上表に移動) |

---

## 現在のブロッカー

- **★ 2026-08-24 新規発見: PLAN-003 §10 の追随表に載っていない文書が3つある。**
  §10 は「追随が要る文書」を列挙しているが、**次の3件が漏れていた**:
  - **`Documents/09_PAPER_PLAN.md`**: **論文1の骨格が再設計前のまま。**
    貢献1が「一貫性バッテリ **G1–G6**」、§3.2 が「一貫性バッテリ G1–G6」、
    §5.2 が「**主要評価項目: G6 非出力経由の判断**」。
    **ADR-023 以降の主軸(タスク型 × 既知性の交互作用)がどこにも無い。**
    論文の claim に直結する文書なので、**事前登録の凍結前に追随させる**
  - **`Documents/00_OVERVIEW.md`**: §6 の1行は 2026-08-24 に訂正したが、
    **§1 の問題設定と §7「主張すること / しないこと」は未点検**
  - ~~**`configs/template.yaml` の `eval.batteries` コメント**: `[g0, g1, ..., g7]` のまま。~~
    → **2026-08-25 に `[comparison]`(実装済みの群のみ)に差し替えた。**
    **全リストは #11(G7)と PLAN-002 §5.2(G0 の撤回)の決着待ちのままである**
- **★ 2026-08-23 発見: `Documents/05_STATISTICS.md` §6(検出力分析)が主要検定に追随していない。**
  主要検定が `task:coverage` の LRT(**df = 6**)に変わったのに、§6 の想定効果量は
  旧・主要評価項目の「G6 rule_rate 差 = 0.30」のままである。**df = 6 の LRT では「効果量」を
  交互作用のプロファイルの形として指定する必要があり、この置き換えは自明ではない。**
  **`ADR-028` のシード数 10 は検出力分析ではなく設計判断で決まっている**ので、
  現状では論文に「なぜ 10 シードか」を書けない。
  **事前登録の凍結前に再導出が要る。**PLAN-003 §10 の追随表には無かった行(本セッションで追加)
- ~~repo が git 管理下にない~~ → **解消**(commit f28a4e4)
- **実験パラメータが一部未決定。**`configs/template.yaml` の以下は `null` のまま。
  設計文書に値が書かれていないため、エージェント側で既定値を作っていない。
  **PLAN-002 以降で人間が決める必要がある**:
  学習率 / ステップ数 / batch size / LoRA rank と alpha / `arb` 条件のズレ表
  (**PLAN-002 はこの5項目に手を付けていない。**意図的に空けてある。同 §0)
  - **新規(2026-08-22)**: `data.pool_split_seed` / `data.coverage_seed` / `data.sample_seed` /
    `data.pool_id` を追加。**4項目とも `null`**。シードの分離規約は PLAN-002 §4.2.4
  - ~~`train.cot_mode`(どちらを主要とするか)~~ → **廃止。`train.scope ∈ {bare, bare_plus_gsm8k}` に置換(ADR-019)。Phase 1 は `bare` のみ**
  - ~~`data.coverage_k`~~ → **`K = 2000` を主値、パイロットは {1000, 4000}(ADR-019)。`K = 500` は使わない**
  - ~~2系統目のモデル / base か instruct か~~ → ~~**解消(2026-08-23)。`meta-llama/Llama-3.1-8B`(base)。**ADR-008 採択。~~ → **2026-08-23 再決定: `meta-llama/Llama-3.1-8B-Instruct`(ADR-024 決定1 が ADR-008 / ADR-018 決定1 を上書き)。**2系統目は Phase 2 へ延期。~~**`model.revision` は未決のまま(PLAN-003 §11-14)。**~~ → **2026-08-24 解消(ADR-031)。**pull 時点の HF コミットハッシュを config と manifest に固定する。**値は最初の pull まで確定しないので、それまで `null` のままでよい。**`preflight` が `null` のまま本実行に入るのを弾く検査は**未実装**
  - ~~被演算子の値域 / 評価項目数 / 温度 / 主要評価項目の具体名~~ →
    **PLAN-001 §4.1・§5.1・§5.6 で決定。承認済で本文にも反映済**(ただし外挿域の `θ` は下記のとおり未決定)
  - ~~`eval.reference_rule` を config の必須項目として追加する~~ → **完了**(ADR-016。`eval.elicitation` と `data.coverage_k` も併せて追加。**3項目とも `null`**)
  - ~~**新規**: `eval.reference_rule` に `ident` を指定させない検査が**未実装**~~ →
    **実装済**(2026-08-22。`scoring.validate_reference_rule`。名前でなく振る舞いで弾くので `offset=0` も止まる)
  - **新規**: `θ`(外挿域の閾値)と掃引粒度が**未決定**。人間が Phase 0 の桁数掃引の実測を見てから決め、ADR に記録する(PLAN-001 §4.1.1)
- **(新規・実装が止まっている原因)PLAN-001 §5.1.1 の穴が3つ埋まっていない**:
  - ~~**穴1**: `id` セルの埋め方~~ → **解決(2026-08-22。案A。ADR-017)。**
    ただし**プールを実際に生成できるのは `K` が決まり FT データ生成器(PLAN-002)が動いた後**である。
    機構(`pool.fill_cells`)は実装済みで、`K` 組を引数に取る
  - **穴2**: 「単位元の言明」「規則の自己説明」は `(a, b)` を持たず被覆ラベルが定義できない
  - **穴3**: 本番の評価テンプレート集合(`data.eval_template_set`)が未確定。**実験条件である**。
    ~~訓練側のテンプレートがまだ無いため「訓練と異なる集合」を確定できない。~~
    → **2026-08-22 前進(ADR-019 決定1)。訓練側が裸の式 `a+b=` 一形式に確定した**(書式は
    PLAN-002 §4.1 に1文字単位で固定)ので「訓練と異なる集合」が定義できるようになった。
    **残る未決は G1「記法形」変種の扱い(承認待ち-12)と、本番テンプレートの文面そのもの。**
    配線確認専用の `configs/templates/smoke.yaml` だけがある
- ~~**2系統目のモデルが未決定**(`Documents/04_EXPERIMENT_PLAN.md` §0 は最低2系統を要求)。~~
  → **ブロッカーではなくなった**(ADR-018 決定2。2系統目は Phase 2 へ延期。
  `Documents/04_EXPERIMENT_PLAN.md` §0 に打ち消し線+理由+日付を入れた)。以下は記録として残す。
  第一候補 Llama-3.1-8B は ADR-008 で確定済み
- **`infra/Dockerfile` のベースイメージタグが未確定**(`UNPINNED-未確認`)。
  実在を確認していないタグを書かないため空けてある(`CLAUDE.md` §2)
- **`infra/requirements.lock` が空。**最初にポッドを立てて `pip freeze` した時点で埋める
- RunPod のインスタンスタイプとコスト見積もりが未確定

---

## 人間の承認・判断を待っている事項(`CLAUDE.md` §8)

> **2026-08-23 追記(PLANNER)。この節の内容は `plans/PLAN-003-redesign.md` §11 の 15 件に
> 集約された。**個別に消化せず、PLAN-003 §11 を見ること。以下は再導出前の記録として残す。
>
> **★2026-08-27 追記。この節の番号は PLAN-003 §11 の番号と一致しない**(この節は 2026-08-22 起源)。
> **正本は PLAN-003 §11 と `plans/PLAN-004-phase0-route.md` §5 である。**
> 同日に決着したのは PLAN-003 §11 の番号で **#11(G7)= 落とす / #16(Feucht)= (a) /
> #18(T1 の指示)= 現状維持 + 副次セル / #19(被演算子 1)= 評価項目のみ**、および
> **PLAN-002 §12-11(判別不能の除外)= 掛けない**(ADR-034 / 035 / 036)。
> **#13(`table[1]` の穴)は消滅、#17(Nikankin の原典確認)は「高」に昇格した。**
> 下の表の 11(G7)/ 13(ズレ表の追加制約と `table[1]` の穴)/ 16(Feucht)も同じ理由で決着・消滅している。


| # | 内容 | 場所 |
|---|---|---|
| 1 | `plans/PLAN-000-repo-bootstrap.md` の CRITIC レビュー | 未実施 |
| 2 | `Documents/08_FUTURE_DIRECTIONS.md` L62「ADR-005(色体系の規約)を先に確定すること」。ADR-005 は主要評価項目の決定で色体系ではない。**誤参照ではなく未執筆 ADR への先回り参照**と読める。既に埋まっている番号を将来の ADR に割り当て直すのは番号の再利用にあたり §8 の判断事項 | `Documents/08_FUTURE_DIRECTIONS.md` L62 |
| 3 | `Documents/04_EXPERIMENT_PLAN.md` Phase 1 の Go/No-Go の fallback に**「被覆 `K` を下げる」「訓練値域を狭める」を追加**してよいか。**ADR-019 により制約が付いた: `K` は 560 を下回れない**(評価プールの `id` セルが埋まらない)。訓練値域は既に `[1,99]^2` まで絞ってある | `plans/PLAN-001-eval-battery.md` §13 |
| 4 | **(新規)** `K` を**掃引軸(実験条件)**にするか。config 項目として持つこと(変更 D、承認済)とは別の判断であり、条件の追加は §8 に当たる | 同 §13 |
| ~~5~~ | ~~G1 の日本語を訓練内に置くか外に置くか~~ → **解決(ADR-019)。訓練プロンプトは裸の式 `a+b=` 一形式なので、日本語変種は構成的に必ず訓練外**になる | ADR-019 |
| 7 | **(実装で判明。穴2)** 被演算子を持たないカテゴリ(G2「単位元の言明」/ G3「規則の自己説明」)を被覆層から外し、独立のセルとして `n` を別に決めてよいか | 同 §5.1.1 |
| 8 | **(前進。ADR-019)** 本番の評価テンプレート集合。**訓練側が `a+b=` 一形式に確定したので「訓練と異なる集合」が定義できるようになった。**残る未決は **G1 の「記法形」変種(`3+4=`)が訓練形式と一致する**問題 → **PLAN-002 §5.2 が案A(独立群 `G0`「訓練形式アンカー」に分離)を提案。下記 12 に移す** | 同 §5.1.1、PLAN-002 §5.2 |

**新規**(2026-08-22。**すべて `plans/PLAN-002-ft-data.md` §12 が正本**):

| # | 内容 | 場所 | 既定案 |
|---|---|---|---|
| 9 | 答えが1桁の層(母集団 36 組)に配分の下限を置くか。置かないと `K=2000` で 7 組しか入らない | PLAN-002 §4.2.3 | **置かない**(比例配分のまま) |
| 10 | `train_size` の掃引軸を `{1k, 3k, 10k}` → **`{2000, 4000, 10000}`**。`K=2000` の下で 1k は原理的に生成できない。**実験条件の変更** | PLAN-002 §4.3.2 | 改める |
| 11 | **G7 の項目構成**(サブ群3・層は `carry × wrap`・`n=15`・合計 **165 項目**) | PLAN-002 §5.1 | 提案どおり。**2026-08-23 の原典転記で文面と `n_max` が埋まった**: `n_max = 2m`(月 24 / 曜日 14 / 時刻 48)、**G7-H は 24時制(法 24、起点 `00`..`23`)**、文面は §5.1.2a に逐語転記。**165 と `n=15` は変わらない**。この変更ごと承認を仰ぐ |
| 12 | **G1 の「記法形」変種**を独立群 `G0`「訓練形式アンカー」(400 項目)に分離する(旧 8 の残り) | PLAN-002 §5.2 | 案 A |
| 13 | `arb` のズレ表への**追加制約3・4**(周期タスクの偶然一致回避 / 桁数を `p2` に揃える)。**制約3が無いと G7 の 15 件のセルが埋まらない** | PLAN-002 §7.3、PLAN-001 §4.4 | 追加する。**2026-08-23 に範囲と法が広がった**: `1 <= t <= 71`、法は `{7, 12, 24}`。**新規の穴**: ズレ表の定義域は `[2,198]` なのに G7-H の `x=0, n=1` が `t=1` を要求する。(a) 定義域を `[1,198]` に広げる / (b) `x=0` を除く / (c) G7-H の `n >= 2` のいずれかを人間が選ぶ |
| 14 | `R_train = R_main = 99` を固定条件として宣言し、Go/No-Go の fallback から「訓練値域を狭める」を取り下げる | PLAN-002 §7.1 | 宣言する |
| ~~**15**~~ | ~~**(新規 2026-08-23)** `model.revision` に何を入れるか~~ → **2026-08-24 解決(ADR-031)。**人間が AI の判断を承認。**手続きは既定案どおり。ただし限界の記述は差し替えた** —— ADR-024 で変種が `-Instruct` になった以上、乖離は revision 水準ではなく**変種水準**である | ADR-031、`06_THREATS.md` **T13**(新設) | 決着 |
| **16** | **(新規 2026-08-24)** **Feucht et al. (2026) を論文1でどう位置づけるか。**(a) Intro の対立軸のみ / (b) G7 を残して書式の出所も兼ねる / (c) 引用しない。**`CLAUDE.md` §3 によりプレプリントは主要な論拠に使えない。**#11(G7)と一体で決める | PLAN-003 §8.4、`06_THREATS.md` T13 | (a) を推奨。ただし #11 次第 |
| **17** | **(新規 2026-08-24)** **Nikankin et al. (2025) の原典確認**(現在 ⚠️)。Feucht を降ろすと Intro の対立軸を単独で支えることになる | `02_RELATED_WORK.md` A 表 | SCOUT に投げる |

**解決済み**(2026-08-22、実装中に見つかった2件に人間が回答):

| # | 内容 | 結果 |
|---|---|---|
| ~~6~~ | 穴1: 被覆セル(`id` / `interp` / `extrap`)の埋め方 | **案A を採択(ADR-017)。****評価項目プールは FT データ生成の後に作る。**`id` セルは訓練被覆 `K` 組から、`interp` セルはその補集合から引く。**プールは `K` に依存し、訓練域を変えたら作り直す**(§4.2 A の「作り直さずに済む」利点はラベル付与に留まる)。`pool.fill_cells` に実装済み。埋まらなければ例外で止まる |
| ~~9~~ | 穴に非ず: パーサの抽出規則10項目(§5.4.1) | **現行のまま維持。**規則2「見る範囲に整数がちょうど1個のときだけ採る(0個も2個以上も `parse_fail`)」を含め承認。Phase 0 の実測後に見直す余地は据え置き |

**解決済み**(2026-08-22、人間が「変更をすべて承認します」と回答):

| # | 内容 | 結果 |
|---|---|---|
| ~~3~~ | `rule_rate` を固定参照規則に対して定義するか | **承認。**主要評価項目では参照規則 = `p2`。`metrics.json` は参照規則ごとに独立した4値ブロックを持つ。**ADR-016 として起草済**(2026-08-22) |
| ~~4~~ | `arb` 表に `table[t] ≥ t+2` の制約を課すか | **承認。**課す |
| ~~5~~ | `arb` 表を固定シードで一度生成しリテラルとして config に貼る運用でよいか | **承認。**生成スクリプトも commit する |
| ~~6~~ | 主要評価項目を `elicitation = direct` に固定してよいか | **承認。**CoT 側は副次的評価項目とし、`05_STATISTICS.md` §4 のゲートキーピング順序に追加する |
| ~~A~~ | 外挿域を実測 `correct_rate ≥ θ` による定義に変えるか(懸念6の解消) | **承認。**素のモデルに桁数を掃いた加算を解かせ、崖の手前を外挿域にする。**FT を回さずに潰せる。**`θ` は人間が決め ADR に記録 |
| ~~B~~ | パイロット専用の項目プールを分離するか | **承認。**本番プールと交わらないことを manifest とテストで固定 |
| ~~C~~ | 内挿ホールドアウトを「訓練サンプラが引く `K` 組の補集合」に変えるか | **承認。**根拠のない「20%」が消える |
| ~~D~~ | 被覆 `K` を config 項目として追加するか | **承認。**`train_size` だけでは訓練分布が決まらない |

**解決済み**(2026-08-21、人間が「AI 判断をもって対処」と指示):

| # | 内容 | 結果 |
|---|---|---|
| ~~1~~ | ADR-004 の「**ADR-007 の旧案を置き換える**」の食い違い。どの ADR を指していたか | **解決。ADR-014 を採択。**「どの ADR か」ではなく「置き換え対象の ADR が存在するか」を問うと確定できる。**答えは「存在しない」**(①ADR-007 は採択のまま現役で参照されている ②004 は 007 より前で規約上置き換えられない ③×2 を主変換とした ADR はそもそも無い)。ステータス行を打ち消し線で取り消し、**別番号へ振り替えない**。ADR-004 の決定内容と ADR-007 は無変更 |

**解決済み**(2026-08-20、人間が「AI の判断を受け入れる」と決定):

| # | 内容 | 結果 |
|---|---|---|
| ~~1~~ | 存在しない「ADR-012」への参照を ADR-004 への誤記として扱ってよいか | **承認。ADR-012 を採択に変更**(`logs/DECISIONS.md`) |
| ~~2~~ | 設計文書に残る「ADR-012」表記を修正するか | **承認。7箇所すべてを ADR-004 に修正**(`CLAUDE.md` §5、`Documents/00_OVERVIEW.md`、`03_OPEN_QUESTIONS.md`、`06_THREATS.md`、`configs/template.yaml`)。ADR-012 が数えていた「6箇所」は数え落としで、実際は7箇所だった |

---

## Phase 0 に必要な段階(2026-08-24 に IMPLEMENTER が整理)

> **タスクの正本は `Documents/04_EXPERIMENT_PLAN.md` Phase 0(タスク 1〜8 と Go/No-Go)。**
> ここはそれを**依存順に段階化し、各段の現在地を書いた**ものである。番号は段階であって
> タスク番号ではない。**GPU を使う段は人間の承認が要る(`CLAUDE.md` §2)。**

### 段階 A — GPU 不要のコード作業(いま進められる)

| 状態 | 作業 | 正本 |
|---|---|---|
| ✅ | Phase 0 タスク1: `test_algebra.py`(⊕ の群構造 / ⊗ の非結合性)。**2026-08-24 に `p2d` の代数的事実を追加** | 04 Phase 0 #1 |
| ✅ | Phase 0 タスク3: 出力パーサとユニットテスト。**2026-08-25 に `japanese.py` を削除して 6 → 5 モジュール**(`base` / `numeric` / `wordform`(凍結)/ `boolean` / `cot`) | 04 Phase 0 #3 |
| ✅ | 項目プール生成器の ADR-020/021/022 追随(実装順 **0 / 1 / 1b / 1c**) | CHANGELOG 2026-08-24 |
| ✅ | **実装順 2**: `code/data_gen/ft_data.py`(PLAN-002 §4)。**PLAN-002 §4.2 を ADR-029 の `T_hold` 軸に追随させたうえで実装**。`eligible_pairs` に `(p2, p2d)` を配線済 | PLAN-002 §4 |
| ✅ | **実装順 3**: `test_ft_data.py`(12項目 + 罠2件)/ `test_design_facts.py`。**§4.9.3 の #7 / #8 / #12 は未実装**(G7 の項目構成と多項項目の規約がコードに無いため。承認待ち-11 決着後) | PLAN-002 §4.9 |
| ✅ | **実装順 4**: `infra/preflight.py` に検査5・6・7・8 + ADR-029 由来の 9・10 + 検査3拡張(**7件**)。`test_preflight_checks.py` 38 件。**config に `data.matched_manifests` / `eval.anchor_manifest` / `eval.cells` を新設**(§4.8.1 の実装確定表) | PLAN-002 §4.8.1 |
| ✅ | Phase 0 タスク8: **R8 掃引モード**。`build_items(..., sweep=True)` が `is_discriminating` の強制と閾値の許容表を外す。**`Δ̂` の当てはめ(ADR-030 決定6)は未実装** | ADR-030、PLAN-003 §7.1 |
| ✅ | `g6_comparison.py` → **`t3_comparison.py`** 改修(T1b の `category` 追加 / 英語化 / **`arb` の評価を `ans_in` に限定**)。**`arb` × 定義域外の `KeyError` は解消**(`is_defined_for` でガード) | PLAN-003 §7.1 |
| ✅ | D-3(英語統一)の後始末: `parsers/base.py` と `boolean.py` から日本語語彙を外し、`parsers/japanese.py` を削除。`wordform.py` は**残した**(凍結) | PLAN-003 §7.1 / §7.2 |
| ✅ | Phase 0 タスク2(生成器): **T1 / T2 / 特異性対照の項目生成**(`numeric_sum.py` / `specificity_control.py`)。**T1b / T3 は `t3_comparison.py` で実装済**。併せて `pool.build_manifest` に `prompt_format` ブロックを追加 | PLAN-003 §4.2 / §4.3 / §4.6 |
| ✅ | Phase 0 タスク2の残り: **`code/eval/run.py` の数値経路(cot → numeric)の配線**。`parse_numeric_response` を追加し、`dry_run` を4群のディスパッチにした。**`--dry-run` は4群とも通る**(commit `47d2cda`)。**本実行は依然 `NotImplementedError`** | PLAN-003 §7.1(`run.py` の行) |
| ✅ | Phase 0 タスク2の残り: **評価プールを書き出す入口(`code/data_gen/eval_pool.py`)と `eval.anchor_manifest` / `eval.cells` を持つ config**。**preflight の `data_checks` 6項目がすべて PASS**(検査6・8 を含む)。**ただしプールはサンプリングしておらず明示リストで埋めている**(`M*` 未決。ADR-033 決定4) | PLAN-002 §4.8.1、ADR-017 / **ADR-033** |

**★ 段階 A は完了した(2026-08-26)。**残るブロッカーは段階 B(人間の決定)と段階 C の GPU 承認である。

### 段階 B — 人間の決定(段階 C と並行してよいが、凍結の前に全部要る)

| # | 事項 | いつ要る |
|---|---|---|
| ~~**6**~~ | ~~T2 の5テンプレートの確定文面~~ | **2026-08-26 決着(ADR-032)** |
| ~~**18**~~ | ~~T1 にも答え書式の指示を足すか~~ → **2026-08-27 決着。現状維持 + 副次セル**(指示付き T1 を `id` × carry/nocarry の2セル・n=40 = 80 項目。主軸の交互作用には入れない)。**ADR-035 採択済(2026-08-27)。実装は順4** | 決着 |
| ~~**19**~~ | ~~被演算子 1 の除外を全タスク型に広げるか~~ → **2026-08-27 決着。評価項目のみに広げる**(`K` には広げない。広げると答え1桁の層が 6 → 3 組に潰れる)。**ADR-035 採択済(2026-08-27)。実装は順4** | 決着 |
| ~~**13**~~ | ~~`arb` のズレ表 `table[1]` の穴~~ → **2026-08-27 消滅。**G7-H の `x=0, n=1` が `t=1` を要求していたのが唯一の理由で、**#11 = B(G7 を落とす)で不要になった。**ズレ表の定義域は `[2,198]` のまま | 消滅 |
| **9** | 適格性フィルタの閾値 `0.70`(`ident` の `correct_rate`)。**事前登録に入る** | 凍結 |
| **15** | 外挿域の上限 `M*` と桁数掃引の粒度 | 段階 C の最初 |
| ~~**16 / 11**~~ | ~~Feucht et al. の位置づけ / G7 の扱い~~ → **2026-08-27 決着。#11 = B(G7 を落とす)/ #16 = (a)(Intro の対立軸としてのみ引用)。****ADR-036 採択済(2026-08-27)。**PLAN-002 §5.1(165 項目)は廃止、レビュー R7 は不要 | 決着 |
| ~~**PLAN-002 §12-11**~~ | ~~判別不能の除外を `K` の抽出母集団に掛けるか~~ → **2026-08-27 決着。掛けない**(評価項目にだけ掛ける)。**ADR-034 採択済。コード・テスト・文書を同日に反映した** | 決着 |
| **17** | Nikankin et al. (2025) の原典確認(SCOUT に投げる)。**2026-08-27 に #16 = (a) が決まり、対立軸を単独で支えることになったので必須化した** | 凍結。**優先: 高** |
| **10** | W6 の分岐(T2 が Go/No-Go を割ったときの降り方) | Go/No-Go 実施時 |
| **20** | **(新規 2026-08-27)** **生成設定**(`model.dtype` / `max_new_tokens` / デコード設定 / few-shot 数)。`configs/template.yaml:28-33` がすべて `null` で、**エージェントは既定値を作れない**(skill `code-style` §5) | **段階 C の前**(PLAN-004 §5) |
| **21** | **(新規 2026-08-27)** **本番の評価テンプレート集合**(T1b / T3 の確定文面)。`data.eval_template_set` がどの config でも `null`。**タスク6(プロンプト感受性)が依存する** | **段階 C の前**(PLAN-004 §5) |
| **22** | **(新規 2026-08-27)** **LoRA アダプタを `runs/<id>/` に残すか。**`infra/RUNPOD.md` §4 の必須成果物に無く、`adapter` / `アダプタ` は `RUNPOD.md` / `04_EXPERIMENT_PLAN.md` / PLAN-002 / PLAN-003 のどこにも現れない。**残さないと 40 run の後に評価を足すには再訓練が要る** | 順8 まで |
| **25** | **(新規 2026-08-28)** **バッチ生成の `batch_size` を実験装置の設定として扱うか。**バッチ1のままでは段階 C が回らないのでバッチ化は要るが、**左パディングを伴うバッチ生成がバッチ1と同じ出力を返す保証は無い**(貪欲デコードの同点で割れうる)。`infra/RUNPOD.md` §6「ハードウェアの統制」が条件間の構成一致を求めているので、**全条件で同一に固定して `env.txt` に残す**のが既定案。値そのものはエージェントが作れない(skill `code-style` §5)。**★2026-08-28: 実装は済んだ**(config 必須・`metrics.json` に記録)。**人間が決めるのは (1) 値そのもの (2) [MATCHED] にするか (3) バッチ1 対 バッチ N の一致確認の合否基準**。実行デバイス `model.device` も同じ性質なので本項に含める | **順1b の前**(★実装は 2026-08-28 に完了。**値は未決のまま**。#20 と同時でよい) |
| ~~**23**~~ | ~~スモークの段を挿すか~~ → **2026-08-27 決着。採択(ADR-037)。****順1b(本番モデルによるスモーク)を新設した。**★**小モデルではなく `meta-llama/Llama-3.1-8B-Instruct` で回す**(小モデルではトークナイザが違い `max_new_tokens` の材料にならない)。**GPU 小は人間が承認済み。この pull のハッシュが本実験の `model.revision` になる**(ADR-031) | 決着 |
| ~~**24**~~ | ~~#20 を段階 C の結果で改訂してよいか~~ → **2026-08-27 決着。改訂してよい(ADR-038)。****#20 の4項目すべてが対象。**要件は **(a) 日付 / (b) 理由 / (c) 改訂前の値 / (d) 根拠にした run_id** を残すことと、**改訂後の設定で順6 を測り直す**こと。**期限は段階 D(順9)まで。許可は #20 に限る**(#9 / #15 / #21 には及ばない) | 決着 |
| — | **検出力分析(`05_STATISTICS.md` §6)の再導出。**主要検定が `task:coverage` の LRT(**df = 6**)に変わったのに想定効果量が旧のまま。**効果量を「交互作用プロファイルの形」として指定する必要があり、人間の入力が要る** | 凍結 |
| — | **`Documents/09_PAPER_PLAN.md` の追随**(貢献1「G1–G6」、§5.2「主要評価項目: G6」が再設計前のまま) | 凍結 |
| — | **エージェントの判断で人間の目視を受けていないもの**: ADR-030 の R8 手続き全体(解析計画) / ADR-027 前段 / ADR-028 決定1 と Go/No-Go #4b / PLAN-003 §4.8 のセル構成 | 凍結 |

### 段階 C — GPU 小(`none` モデルのみ。FT は1本も回さない)

**★人間の承認が要る。**この段より前に段階 A の項目生成と preflight が通っていること。

1. **桁数掃引で `M*` と `θ` を実測**(PLAN-001 §4.1.1)。`θ` は人間が決めて ADR に記録。**承認待ち-15 の入力になる**
2. **Phase 0 タスク4**: 健常時スコアを5シードで測定(`none`)
3. **Phase 0 タスク5**: test-retest 信頼性(温度0・`num_repeats=3`)
4. **Phase 0 タスク6**: プロンプト感受性(5テンプレート)
5. **Go/No-Go(FT なしで判明する分)**: #0 トークン境界 / #1 `parse_fail_rate < 0.02` / #2 全セル `correct_rate >= 0.70` / #3 T3・T1b の定数戦略ベースライン
   - **#2 で落ちたセルの一覧を凍結前に確定する**(適格性フィルタ。★承認待ち-9)

### 段階 D — 事前登録の凍結

`Documents/05_STATISTICS.md` §10 に記入 → `git tag -a preregister-...`。
**これで「予測が実験前に書かれた」ことが証明できる**(`CLAUDE.md` §5)。
段階 B が全部埋まっていること。**§6 / §10 は凍結直前まで書き換えない。**

### 段階 E — パイロット(FT が要る。Phase 0 と Phase 1 の境界)

**★人間の承認が要る(10 GPU時間超は特に)。**`p2` / `p2d` を 2〜3 シード。

- **Go/No-Go #4**: ペネトランス `T1 × id` の `rule_rate`(`p2` vs `ident`)**≥ 0.90**。
  割れたら**下流の解釈は全部無効**
- **Go/No-Go #4b**: `p2d` のペネトランス ≥ 0.90(ADR-028)。**床に張り付くと副次の順1 が読めない**
- **Go/No-Go #5**: `other_error_rate < 0.10`(モデル崩壊)
- パイロット専用プールで行う(PLAN-001 §4.6。main と非交差)

> ⚠️ **未解決の定義のずれ(人間が判断すること)**: ADR-018 は「Phase 0 は FT を1回も回さずに
> 終わるもの」と定義したが、`04_EXPERIMENT_PLAN.md` Phase 0 の Go/No-Go には
> **FT を回して初めて判明する #4 / #4b / #5 が含まれている**。段階 E を Phase 0 の一部と見るか
> Phase 1 の先頭と見るかで、**事前登録の凍結(段階 D)をパイロットの前に置くか後に置くかが変わる。**
> 現行文書は段階 D を最後に置いている(`STATE.md` 次のアクション表の #6)。

---

## 次のアクション

> **★ 2026-08-26 更新(IMPLEMENTER)。ここから Phase 0 完了までの順序。**
> **下の旧表(2026-08-22 起源)は ADR-023 の再編に追随していない**ので、
> **こちらを正とする。**旧表は役割分担と GPU 要否の記録としてのみ読むこと。

| 順 | 作業 | 段階 | 役割 | GPU | 完了条件(判定できる形) |
|---|---|---|---|---|---|
| ~~**A-5**~~ | ~~**`code/eval/run.py` に数値経路(cot → numeric)を配線する**~~ **完了(2026-08-26。commit `47d2cda`)。405 passed** | A | IMPLEMENTER | 不要 | ~~`--dry-run` が `bare_sum` / `word_problem` / `specificity` 群でも通り、4値分解が出る。`pytest` 緑~~ **達成** |
| ~~**A-6**~~ | ~~**評価プールを書き出す入口(CLI)+ `eval.anchor_manifest` / `eval.cells` を持つ config**~~ **完了(2026-08-26)。423 passed** | A | IMPLEMENTER | 不要 | ~~`infra/preflight.py` の検査6・8 が PASS になる~~ **達成**(`data_checks` 6項目すべて PASS) |
| **B-1** | 承認待ち **#18 / #19 / #13 / #9 / #16・#11 / #17** と検出力分析の再導出 | B | 人間 + PLANNER | 不要 | `logs/DECISIONS.md` に ADR |
| **C-1** | 桁数掃引で `M*` と `θ` を実測(承認待ち-15 の入力) | C | RUNNER | 小 | `runs/<id>/metrics.json` と ADR |
| **C-2** | `none` モデルで Go/No-Go #0〜#3(健常時スコア / test-retest / プロンプト感受性) | C | RUNNER | 小 | `results/` に run_id 付きで |
| **D-1** | 事前登録を `05_STATISTICS.md` §10 に記入し `git tag` | D | PLANNER | — | tag `preregister-*` |
| **E-1** | パイロット(`p2` / `p2d` を 2〜3 シード)。Go/No-Go #4 / #4b / #5 | E | RUNNER | **大(承認要)** | ペネトランス `T1 × id` ≥ 0.90 |

> **★2026-08-27 更新。この表は `plans/PLAN-004-phase0-route.md` §2 に置き換わった。**
> **順序・依存・完了状態の正本は PLAN-004 である。**下表は B-1 以降の役割分担の記録として残す。
> **PLAN-004 は順0〜順9 を持ち、段階 B の表に無かった #20 / #21 を新たに登録している。**

**段階 A は 2026-08-26 に完了した。**段階 B は人間の入力待ち、C 以降は GPU の承認が
要る(`CLAUDE.md` §2)。**段階 C の前提(「段階 A の項目生成と preflight が通っていること」)は
満たされた**が、**段階 C に入るには人間の承認が要る**。
**エージェントが人間の入力なしで進められる作業は、いま無い。**

---

### 旧表(2026-08-22 起源。役割分担と GPU 要否の記録)

**Phase 0 は「FT を1回も回さずに終わるもの」と定義し直した(ADR-018)。#0〜#4 は学習ゼロである。**

> **⚠️ 2026-08-24: 下表は ADR-023 の再編(G1〜G7 → T1 / T1b / T2 / T3 + 特異性対照)に
> 追随していない。**「G6 / G7」という群名はもう存在しない。
> **Phase 0 のタスク一覧の正本は `Documents/04_EXPERIMENT_PLAN.md` Phase 0(タスク 1〜8)である。**
> 下表は役割分担と GPU 要否の記録としてのみ読むこと。
>
> **2026-08-24 に #14 が決着し(ADR-031)、着手できるようになった最初の作業は
> `Documents/04_EXPERIMENT_PLAN.md` Phase 0 タスク2(項目生成)である。**
> その内訳は下の「PLAN-002 承認後の実装順」の 0 → 1 → 1b → 1c → 2 → 3 → 4。
> ~~**ただし実装順 0 は #12(`arb` の存廃)が決まると不要になりうる。**~~
> → **2026-08-24 決着。人間が「`arb` を残す(5 シード)」と回答したため実装順 0 は必要になり、
> 実装した。実装順 0 / 1 / 1b / 1c は完了済である。**

| # | 作業 | 役割 | GPU | 何が確定するか |
|---|---|---|---|---|
| ~~**0**~~ | ~~Feucht et al.(arXiv:2605.01148)の原典から **変種・revision・周期タスクのプロンプト書式**を転記~~ → **2026-08-23 完了** | SCOUT | 不要 | **ADR-008 採択。**`meta-llama/Llama-3.1-8B`(base)、revision は原典に記載なし。転記は `Documents/02_RELATED_WORK.md` §A.1 |
| **1** | **強制選択スコアラ**の実装(G6・G7)+ 自由生成の併走 | IMPLEMENTER | 不要 | ADR-018 決定3。`parse_fail` ゲートが訓練形式から独立する |
| **2** | 桁数掃引で `M*` と `θ`(PLAN-001 §4.1.1) | RUNNER | 小 | 外挿域。**`θ` は人間が決めて ADR に記録** |
| **3** | 素のモデルの **G6 / G7 ベースライン**(強制選択+自由生成) | RUNNER | 小 | 崩壊検出器の基準線。**「8月の6か月後 → 2月」を自分で確認する**(ADR-018 のリスク回避) |
| **4** | プロンプト感受性(5テンプレート)と test-retest(温度0・`num_repeats=3`) | RUNNER | 小 | 効果量の下限。同等性境界 Δ |
| **5** | 訓練域 `[1,99]^2` / `K=2000` で FT データ生成 → 評価プール生成 → `preflight` 照合 | IMPLEMENTER | 不要 | ADR-017 の順序どおり |
| **6** | 事前登録を `Documents/05_STATISTICS.md` §10 に記入し `git tag` で凍結 | PLANNER | — | HARKing の防止 |

~~**#0 と #3 が Phase 0 の心臓部である。**~~ **#0 は完了した。残る心臓部は #3 である。**
#3 で素のモデルが 2月と答えなければ G7 の前提が崩れるので、そこで設計を見直せる。**FT を1本も回す前に潰せる。**

> **#0 の転記で #3 の重要度が上がった。**原典の実測では月タスクの
> 「法を跨ぐ」項目の正答率は **55.0%**であり、「8月の6か月後」はその帯に入る。
> #3 は「確かめる」ではなく**項目のフィルタを作る作業**になる可能性が高い。

~~**#0 より前に必要な文書作業**~~ → **2026-08-22 完了**:
- ~~`plans/PLAN-002-ft-data.md` を書く~~ → **起草済。§12 に承認待ち6件**
- ~~`configs/template.yaml` の `train.cot_mode` → `train.scope` 置換~~ → **完了**(併せてシード3種と `pool_id` を追加)
- ~~`Documents/04_EXPERIMENT_PLAN.md` の Phase 1 / §0 に打ち消し線+日付~~ → **完了**
- ~~`PLAN-001` §4.1 / §4.2 / §5.1 の改訂~~ → **完了**(§4.4 / §4.6 / §5.5 / §8 / §13 も追随)

**PLAN-002 承認後の実装順**(#5 の内訳。IMPLEMENTER):

> **2026-08-23 更新(ADR-020 / 021 / 022)。0 と 1b を先頭に足した。**
> **2026-08-24: 0 / 1 / 1b / 1c は完了した(IMPLEMENTER)。**残るのは 2 → 3 → 4。

- ~~**0. `eligible_pairs` に定義域ガード**(ADR-020)~~ → **2026-08-24 完了。**
  人間が**承認待ち-12 に「`arb` を残す(5 シード)」と回答**したため着手した。
  `Lesion` プロトコルに `is_defined(a, b) -> bool` を追加。`is_excluded` と
  `validate_reference_lesions` が定義域外の規則を飛ばす。回帰テスト設置済
- ~~**1. `label_coverage` を4値化 + 答え域ラベル**~~ → **2026-08-24 完了。**
  `oob_algebraic` を追加し、`label_answer_range`(`ans_in` / `ans_out`)を新設
- ~~**1b. `label_t_coverage`**(ADR-021)~~ → **2026-08-24 完了。**
  `coverage_sums_of` と併せて実装し、`build_manifest` が `coverage_sums` を記録する。
  **セル構成は変えていない**
- ~~**1c. `p2d` の規則クラス**(ADR-022)~~ → **2026-08-24 完了。**
  `DigitOffsetLesion`。`p2d(-7) = -2` をテストで固定。除外規則は
  `pool.is_indistinguishable` + `eligible_pairs(..., indistinguishable_rule_pairs=...)`。
  `build_reference_lesions` にも追加
2. `code/data_gen/ft_data.py` を新規実装(PLAN-002 §4)。
   **⚠️ PLAN-002 §4.2 は ADR-029 の `T_hold` 軸をまだ取り込んでいない。**
   **⚠️ ここで `eligible_pairs` に `indistinguishable_rule_pairs=[(p2, p2d)]` を必ず配線する。**
   省略可能な引数なので、渡し忘れると `t ≡ 0 (mod 10)` の項目が黙って残る
3. `code/tests/test_ft_data.py`(9項目)/ `code/tests/test_design_facts.py`(8項目)
   **+ ADR-022 の未検算2件**: `t ≡ 0` 除外後に G7 の 15 件セルと `carry × 1桁` 層が埋まるか
4. `infra/preflight.py` に新規検査4件(PLAN-002 §4.8.1 の 5〜8)

---

## 引き継ぎ

**完了したこと(最新セッション。RUNNER。2026-08-28。順1b の実機作業):**

- **ポッド `hikss5upj15vp2` の上で clone → bootstrap → データ再生成(段 2b)まで通した。**
  **ポッド上で 643 passed。**`/workspace/translesion`(repo)/ `/workspace/venv`(venv。
  `--system-site-packages` で作った。ポッドの python は PEP 668 の externally-managed)/
  `/workspace/.cache/huggingface`(`HF_HOME`)/ `/workspace/runs`(`runs/` のリンク先)が残っている
- **段 2b の決定性を実機で確認した** —— `git diff data/generated` から `created_at` と
  `git_commit` を除くと**差分ゼロ**。ハッシュ類は一致。
  **`data/generated/battery/smoke1b/manifest.json` はそもそも差分が出ない**
  (このファイルは `created_at` / `git_commit` を持たない。ft 側の3つだけが持つ)
- **実装の穴を2つ塞いだ**(`70541c7` / `7600526`)。詳細は「いま何をしているか」の表
- **ポッドを停止した**(`status: EXITED`。停止時 `uptime` 1883 秒)

**次にやるべきこと:**

1. **★人間: `Ken5615` で https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct の
   アクセス申請を出し、承認を待つ。**これが降りるまで順1b は1歩も進まない
2. 承認が降りたら **`start-pod hikss5upj15vp2`** → **`list-pods` で新しい IP / ポートを引く** →
   `/workspace/translesion` で `git pull` → **`infra/RUNPOD.md` §4「順1b の手順」の段2 から再開**
   (clone と bootstrap とデータ再生成はやり直さなくてよい。**ただし `git pull` の後に
   `pytest code/tests -q` は1度通すこと**)
3. 段2 で得た **snapshots 直下のディレクトリ名**を `configs/smoke1b.yaml` と
   `configs/smoke1b_b1.yaml` の `model.revision` に**両方同じ値**で書き、コミットする

**未解決点:**

- **完了条件2 の答えはまだ出ていない。**API の main sha は
  `0e9e39f249a16976918f6564b8830bc894c89659` だったが、**これは「pull した実体」ではない。**
  手順の正本は snapshots 直下のディレクトリ名であり、**pull が通っていない以上まだ確定していない。**
  **`model.revision` は両 config とも null のままにしてある**
- **段2 の `ignore_patterns=["original/*"]` は手順からの逸脱である。**
  `infra/RUNPOD.md` §4 段2 を直すかどうかは人間が決める
- **ネットワークボリューム `r963j7swke` が付いている件**(記録では「ボリューム無し」だった)。
  **意図したものかを人間が確認する。**ボリュームは停止中も課金される
- **`infra/requirements.lock` は空のままである。**lock 自身のコメントは
  「pytest と preflight が通った直後に `pip freeze` で埋めよ」と書いているが、
  **preflight はまだ FAIL 1件(revision)で通っていない**ので埋めていない。
  **加えて、venv が `--system-site-packages` なので `pip freeze` には
  `torch==2.8.0+cu128` のようなローカル版指定が入る。これは PyPI から復元できない** ——
  **lock の埋め方そのものを人間が決める必要がある**
- **`cost.txt` は書いていない**(人間の作業)


**完了したこと(最新セッション。IMPLEMENTER。2026-08-28。順1b の前提):**

- **順1b の「前提」(a)(b)(c) を実装した**(PLAN-004 §3 順1b)。**順は足していない** ——
  これは**順1 の実装漏れを埋める作業**である
  - **(a)** `model.device` を config の必須項目にした(null は `ConfigError`)。
    `load_model_and_tokenizer` が `model.to(settings.device)` で載せる。**`cpu` も通る**。
    `device_map` を使わなかったのは accelerate を要求するためである
    (`infra/requirements.lock` が空のまま依存を増やさない)
  - **(b)** `eval.batch_size` を config の必須項目にした(null と 1未満は `ConfigError`)。
    `code/eval/generate.py` に `split_into_batches` / `batched_generator` / `_generate_batch`。
    **左パディング**、**`pad_token` の無いトークナイザは eos で代用**(Llama-3.1 系)、
    **応答はプロンプト順**、**端数のバッチを落とさない**。`_generate_one` は消した ——
    **`batch_size: 1` が同じ入力を作る**ので、経路が1本になった
  - **(c)** `GenerationSettings.as_dict` に `device` と `batch_size`。
    `metrics.json` の `generation` と `log.txt` に残る
- **触ったファイル**: `code/eval/model.py` / `generate.py` / `run.py` / `sweep.py`、
  `configs/template.yaml`(両方 `null`)/ `configs/smoke1b.yaml`(値はここだけ)、
  `code/tests/test_generate.py` / `test_eval_model.py` / `test_run_real.py` /
  `test_sweep.py` / `test_aggregate.py`。**`configs/smoke.yaml` は触っていない**(ADR-037 決定4)
- `pytest code/tests -q` → **615 passed**(589 → 615)。**重みを読むテストは1本も足していない**
- **★実機では1度も動かしていない。**左パディングを伴うまとめ生成がバッチ1と同じ応答を
  返す保証は無い(貪欲デコードの同点で割れうる)。**確認は順1b の中で1度だけ取る**
- **`results/` は空、GPU 時間 0、RunPod 未使用、事前登録の tag なし**

**次にやるべきこと**: **順1b の実機作業(RUNNER)。**完了条件は PLAN-004 §3 の
チェックボックス6つのままで変えていない。`configs/smoke1b.yaml` の `model.revision` は
`null` で、**ポッド上の pull で得たハッシュを埋める**(ADR-031 / ADR-037 決定3)。
**手順の正本は `infra/RUNPOD.md` §4**(順1b の手順を書くこと自体が完了条件の1つ)。
順1b の RUNNER 用プロンプトは `git show 327db10:logs/HANDOFF.md` に残っている。

**未解決(人間の承認待ち)**: **#25**(**実装は済んだが値は未決** ——
(1) `batch_size` と `model.device` の値 / (2) [MATCHED] にするか(全条件で揃えるか) /
(3) バッチ1 対 バッチ N の一致確認の合否基準)/ #20 / #21 / #22 / #9 / #15 と、
PLAN-004 §3 順1・順8 に並んでいるエージェントの独断。

---

**完了したこと(PLANNER。2026-08-28):**

- **コードは1行も変えていない。**`plans/PLAN-004-phase0-route.md` §2 と実装を突き合わせただけである
- **順1b の前提を1件見つけて登録した**(上の「いま何をしているか」と「repo の状態」)。
  **本実行が GPU に載らず、バッチ生成も無い。**PLAN-004 §3 順1b に「前提」節、§5 に **未決 #25**、
  §7 に実行ログ1行を足した。**順は足していない**(PLAN-004 §8 規則3)
- **人間が「問題1(GPU 配置とバッチ化)を次のセッションで解決する」と決めた(2026-08-28)**
- `logs/HANDOFF.md` を**次セッション(IMPLEMENTER)用に上書きした。**
  **順1b の RUNNER 用プロンプトは `git show 327db10:logs/HANDOFF.md`、
  順8 の分割単位 8-1〜8-6 は `git show 606dd69:logs/HANDOFF.md` に残っている**
  (**8-6 の残作業そのものは上の順8 セッションの引き継ぎと PLAN-004 §3 順8 が正本**)
- **人間の承認を得て、`Documents/07_ROADMAP.md` に「メインの実行までの工程」節を足した**
  (順1b 〜 Phase 1 本実験の工程と**時間の見積もり**)。**順序と完了状態の正本は PLAN-004 §2 のまま**で、
  あちらは時間だけを持つ。**書いた時間は見積もりであって実測ではない**と節の冒頭に明記した
- **★別セッションが同じ作業ツリーで問題1 を実装し終えた**(commit `de8d151`。**615 passed**。
  **実機では未確認**)。**したがって次は順1b(RUNNER)である。**`logs/HANDOFF.md` を
  **順1b 用に戻し**、冒頭に 2026-08-28 の現況(問題1 完了 / バッチ1 対 バッチN の一致確認 /
  未決 #25)を足した。**本セッションの編集は `de8d151` の内容を1行も消していない**(diff で確認)
- **`results/` は空、GPU 時間 0、RunPod 未使用、事前登録の tag なし。**`pytest` は回していない
  (コードを触っていないため。直近の実測は 2026-08-27 の **589 passed**)

**次にやるべきこと**: `logs/HANDOFF.md`(問題1 = デバイス配置とバッチ生成)。
**そのあとが順1b** —— 順1b の完了条件は PLAN-004 §3 のチェックボックス6つのままで変えていない。

**未解決(人間の承認待ち)**: **#25**(`batch_size` の扱い)/ #20 / #21 / #22 / #9 / #15 と、
PLAN-004 §3 順1・順8 に並んでいるエージェントの独断。

---

**完了したこと(最新セッション。IMPLEMENTER。2026-08-27。順8 の 8-1〜8-5):**

- **順8 の 8-1〜8-5 を実装した。**`code/train/`(`settings.py` / `data.py` / `run.py` / `lora.py`)と
  `code/analysis/aggregate.py`。**`code/train/` と `code/analysis/` はもう空ではない**
- `python -m code.train.run --config configs/smoke.yaml --seed 0 --dry-run` が通る。
  **本実行は #22 の門で必ず止まる**(`code/train/lora.py:build_trainer` が `ConfigError`)
- **LoRA グリッドの値は1つも入れていない。**`configs/template.yaml` の `train.*` は null のまま
  (PLAN-003 §9)。`configs/smoke.yaml` にだけ「★smoke のみ。実験条件ではない」と明記した値を置いた
- **層に依らない場所へ4つ出した**(`code/artifacts.py` / `code/chat_format.py` /
  `code/config.py:resolve_repo_path` / `code/rates.py`)。`code/train/` と `code/analysis/` が
  `code/eval/` を import しないため(skill `code-style` §2)。**複製は作っていない**
- **独断7件と、見つけた不一致2件**を `plans/PLAN-004-phase0-route.md` §3 順8 に書いた。
  **人間が一度見ること**(#10〜#14 と同じ扱い)
- **`infra/RUNPOD.md` §4 のコメントアウトは外していない**(8-6 の作業)。
  実在状況の表だけ書き直した —— **手順6(集約)は回る。手順4(訓練)は #22 で止まる**
- `pytest code/tests -q` → 506 → **589 passed**。
  **`results/` は空、GPU 時間 0、事前登録の tag なし、RunPod 未使用**
- **★このセッション中に別セッション(順1b の RUNNER)が同じ作業ツリーで動いていた。**
  `configs/smoke1b.yaml` と `data/generated/**/smoke1b_*` が未追跡のまま増えており、
  1度 `git add -A` で巻き込んだので `git reset --soft` で外した(commit `ee47097` は
  本セッションのファイルだけ)。**`logs/HANDOFF.md` は順1b 用のまま上書きしていない**

**次にやるべきこと(順8 の残り)**:

1. **#22 を人間が決める**(アダプタを `runs/<id>/` に残すか)。決まれば **8-6**:
   (a) ADR / (b) アダプタの保存 / (c) `infra/RUNPOD.md` §4「必ず残すもの」に追加 /
   (d) **門と重みの読み込みを分ける**(来歴を書いたあとに読む)/ (e) 評価がアダプタを読み、
   評価の `metrics.json` に `seed` を入れる。**(e) が済むまで集約の表のシード欄は埋まらない**
2. **LoRA グリッドの値**(`rank` / `alpha` / `dropout` / `target` / `learning_rate` /
   `num_steps` / `batch_size` / `gradient_accumulation`)。**別 PLAN**(PLAN-003 §9)
3. 上と独立に **順1b(RUNNER)** が進む

**完了したこと(最新セッション。PLANNER。2026-08-27。#23 / #24 の承認):**

- **人間が #23 / #24 を承認した。`logs/DECISIONS.md` に ADR-037 / ADR-038 を採択した**
- **ADR-037(#23)**: 順1 と順2 の間に **順1b「本番モデルによるスモーク」**を挿す。
  **小モデルには差し替えない** —— 本セッションで「**トークナイザが違えば答えのトークン長は
  移らない**」ことが分かり、小モデル案では **#20 の `max_new_tokens` が決まらない**ため。
  人間が「本番モデルで smoke(GPU 小)」を選択。**見積もり 1 GPU時間未満・承認済み**
  - **決定3: 順1b の pull で得たハッシュが本実験の `model.revision` になる**(ADR-031 決定1・2)
  - **決定4: `configs/smoke.yaml` は触らない。**順1b 用の config を別に作る。理由は
    (1) `model.name = null` は門の回帰テスト(`code/tests/test_eval_model.py:51`)が拠る固定点、
    (2) smoke のデータ域 `[1,9]^2` は**本実験 `[1,99]^2` より桁が少なく材料として短すぎる**
  - **決定7: 材料が取れるのは T1 / T2 だけ**(T1b / T3 の文面は **#21 が未決**)
- **ADR-038(#24)**: **#20 の4項目すべて**を段階 C の結果で改訂してよい。要件は
  **(a) 日付 / (b) 理由 / (c) 改訂前の値 / (d) 根拠にした run_id** を残すこと、
  **改訂したら順6 を測り直すこと**(=改訂前の数値を Go/No-Go に使わない)。
  **期限は段階 D(順9)まで。許可は #20 に限る**
  - **★決定4(測り直し)はエージェントの補足である。人間が一度見ること**
  - **リスクとして明記した**: デコード設定と few-shot 数の改訂が最も事後選択に近い
- **`plans/PLAN-004-phase0-route.md`**: §2 に**順1b の行**(順2 の依存を `1b` に)、
  §3 に**順1b の完了条件6つ**、§5 の #23 / #24 を**決着**に、§6 に**罠6**
  (順1b の数値を段階 C の代わりに読む罠)、§7 に実行ログ1行と **GPU 承認記録1行**
- **コードは1行も変えていない。**`results/` は空、GPU 時間 0、事前登録の tag なし、RunPod 未使用

**次にやるべきこと(2つある。どちらから始めてもよい)**:

1. **順1b(RUNNER。GPU 小。承認済み)** —— `configs/` に順1b 用 config を作り、
   `meta-llama/Llama-3.1-8B-Instruct` を pull してハッシュを記録し、スモークを回して
   **答えのトークン長**を出す。**完了条件は PLAN-004 §3 順1b の6つ。**
   `infra/RUNPOD.md` §4 に順1b の手順を書くところまでが完了条件に入っている
2. **順8(IMPLEMENTER。GPU 不要)** —— `code/train/` の LoRA 訓練コード。
   そのまま貼れるプロンプトは `logs/HANDOFF.md`(分割単位 8-1〜8-6)

**完了したこと(最新セッション。PLANNER。2026-08-27。順2 / 順3 の判断材料の整理):**

- **`plans/PLAN-004-phase0-route.md` に判断材料を落とした**(commit `4d2a571`)。
  §3 順2 =「**#20 の4項目のうち実測が要るのは `max_new_tokens` だけ**」/
  §3 順3 =「**#9 は規範的な線引きであって実測から導かれる量ではない**」「**#15 は値を決めず
  規則だけ凍結する**」+ 完了条件に「`M* < 100` の分岐を先に書く」を追加 /
  **§6 に罠5**(**段階 C は「試し」ではなく本番の測定である**。回す段は3つある)
- **未決を2件登録した**: **#23**(順1 と順2 の間にスモークの段を挿すか。**エージェントの提案で
  未採択**。採択には PLAN-004 §8 規則3 により **ADR** と**人間の GPU 承認**が要る)/
  **#24**(#20 を段階 C の結果で改訂してよいか)
- **順は足していない**(§8 規則3)。**コマンド列も複製していない**(同規則2。正本は `infra/RUNPOD.md` §4)
- **コードは1行も変えていない。**`pytest code/tests -q` → **506 passed**。
  `results/` は空。GPU 時間 0。事前登録の tag なし

**次にやるべきこと: 順8(`code/train/` の LoRA 訓練コード + `code/analysis/aggregate.py`)。**
**別セッションで実行する。**そのまま貼れるプロンプトは `logs/HANDOFF.md`。
**実装が長いので 8-1〜8-6 の分割単位を HANDOFF に書いた。**1単位ごとに pytest → commit し、
コンテキストが閾値を超えたら「8-N まで終わった」を書いて切ること。
**8-6 は #22(アダプタの保存)待ちなので、決まっていなければ 8-5 で終える。**

**完了したこと(最新セッション。IMPLEMENTER。2026-08-27。順1 = 完了):**

- **PLAN-004 §3 順1 の完了条件を 5/5 達成した。**内訳は上の「いま何をしているか」が正本
- **`--dry-run` の経路を壊していない**(§4.3 の3)。配線確認と本実行は
  項目の割り方・参照規則の検査・文面の出どころまで**同じ関数**を通る。
  違うのは応答が固定文字列かモデルの生成かだけである
- **`--dry-run` の警告文を本実行に流用していない**(§4.3 の4)。本実行の log には
  「実験ではない」が出ず、代わりに**アダプタを読んでいない**ことが必ず1行出る
- **既定値を1つも作っていない**(§4.3 の2)。`model.name` / `revision` / `dtype` /
  `max_new_tokens` / `eval.temperature` / `eval.num_repeats` /
  `eval.magnitude_sweep.*` は null なら `ConfigError`
- `pytest code/tests -q` → **506 passed**。`results/` は空。GPU 時間 0。事前登録の tag なし

**⚠️ 残っていること**:

- **`ruff` / `black` を1度も掛けていない**(ローカルに未インストール)。行長 100 は手で確認済
- **本実行を実際にモデルで回した経験が0である。**テストはすべて生成関数を差し替えている。
  重みを読む部分(`load_model_and_tokenizer` / `build_generator` / `_generate_one`)は
  **一度も実行されていない。**順5(GPU 承認後)の最初の1本で初めて通る
- **`eval.num_repeats` を 1 以外にできない**(未実装)。Phase 0 タスク5(test-retest、
  `num_repeats=3`)は**この門に当たる。**順6 の前に実装が要る
- **掃引は規則どうしの判別不能(`p2` vs `p2d`)を落としていない。**評価プール側の
  除外は順4(ADR-035)

**次にやるべきこと: 順2 / 順3(人間の決定)。**エージェント側で人間の入力なしに
進められるのは**順8(`code/train/` の LoRA 訓練コード)**だけである。
そのまま貼れるプロンプトは `logs/HANDOFF.md`。

**完了したこと(最新セッション。PLANNER 兼 IMPLEMENTER。2026-08-27。順0 = 完了):**

- **ADR-034 / ADR-035 / ADR-036 を `logs/DECISIONS.md` に書いた。**5件の決定がすべて記録された
- **PLAN-002 §12-11 をコードに反映した。**`ft_data.generate` 手順2b から
  `indistinguishable_rule_pairs` を外した(**偶然一致の除外は残した**)。manifest に
  `indistinguishable_rule_pairs_applied_to: "eval_items_only"` を新設し `schema_version` を 1 → 2
- **本番経路を通す設計事実テストを足した。**`generate` が母集団 **4,309** / `K_main` の carry **393** を
  出し、`t ≡ 0 (mod 10)` が訓練被覆に残ることを固定する。**食い違いの原因は
  「同じ数を別々の道で計算して突き合わせていなかった」ことなので、経路ごと縛った**
- `test_ft_data.py` の [MATCHED] の罠テストを書き換えた。`digit_modulus` はもう `K` を動かさないので、
  **不動点を持つ `arb` 表を渡して偶然一致の除外が生きていることを固定する**形にした
- **文書を追随させた**: PLAN-002(§4.2.1 / §5.1 廃止 / §12 / §4.9.3)、PLAN-003(§4.7 / §8.4 / §11)、
  PLAN-004(順0 = 完了)、`configs/template.yaml`、`Documents/02_RELATED_WORK.md`、
  `Documents/06_THREATS.md`、`logs/DECISIONS.md`(ADR-022 決定3 と ADR-029 根拠表 7,916 に注記)
- `pytest code/tests -q` → **427 passed**。preflight の **`data_checks` 6項目すべて PASS**
- **`results/` は空。実験結果の数値は1つも無い。**GPU 時間 0。事前登録の tag なし

**⚠️ このセッションで独断で決めた点(人間が一度見ること):**

- **manifest の欄名 `indistinguishable_rule_pairs_applied_to` と値 `"eval_items_only"`**、
  および **`schema_version` を 1 → 2 に上げたこと**(既存 manifest は無いので移行の問題は起きない)
- **`build_manifest` の引数名を `lesion_pairs_excluded` → `indistinguishable_rule_pairs` に改めたこと**
- **ADR-035 に書いた副次セルの規模(`id` × carry/nocarry × n=40 = 80 項目)は依然として未承認。**
  人間が決めたのは「現状維持 + 副次セル」までである(前セッションからの持ち越し)
- 前セッションが書いた `id` セル候補 **1,821 組**は `coverage_seed = 0` の数だった。
  **設計値 20260823 では 1,808 組(被演算子 1 を除くと 1,776 組。carry 386)。**
  要求 520 組に対する結論は変わらない

**次にやるべきこと: 順1(`code/eval/run.py` の本実行 + 桁数掃引の入口)。**
**順2 / 順3(人間の決定 #20 / #21 / #9 / `θ` の決定規則)は人間側で並行して進められる。**
そのまま貼れるプロンプトは `logs/HANDOFF.md`。

**完了したこと(最新セッション。PLANNER。2026-08-27。順0 の3判断が決着):**

- **人間が5件すべて決定した。**§12-11 = **掛けない** / §11-18 = **現状維持 + 副次セル** /
  §11-19 = **評価項目のみに広げる** / §11-11 = **B(G7 を落とす)** / §11-16 = **(a) Intro のみ**。
  **逐語は上の「いま何をしているか」と `logs/HANDOFF.md`**
- **判断の材料に組合せ論的な数え上げを回した**(実験結果ではない)。要点は3つ ——
  (1) **「掛けない」でも `id` セルは全部埋まる**(候補 1,821 組 / 要求 520 組。carry 393 vs 240)、
  (2) 「掛ける」は訓練から和を **17 種**余分に抜く(`K` が張る和 170 → 154 種)、
  (3) 被演算子 1 を **`K` にも**広げると答え1桁の層が **6 → 3 組**に潰れる
- **⚠️ 不整合を2件見つけた**(次セッションが直す):
  **(i)** 設計事実テスト([test_design_facts.py:262](code/tests/test_design_facts.py))と PLAN-003 §4.7 は
  `p2d` 除外**なし**の数(carry 393 / 391)を固定しているのに、本番経路
  [ft_data.py:636-653](code/data_gen/ft_data.py) は除外**あり**(carry 435)だった。
  `smoke.yaml` に `digit_modulus` が無いので発火せず表に出ていなかった。
  **決定が「掛けない」なので、直すのはコードと `configs/template.yaml:57-61` のコメント**。
  **(ii)** PLAN-002 §4.2.1 の「20 個の和」は **17** が正しい
- **新しい未決 #22(LoRA アダプタの保存)を登録した。**段階 B の表に追記済み
- **ADR は1本も書いていない。**ADR-034 / 035 / 036 が未執筆であり、**これが次セッションの仕事**
- **コードは1行も変更していない。**`pytest` 未実行(変更が無いため)。`results/` は空。
  RunPod 未使用(GPU 時間 0)。事前登録の tag なし

**⚠️ このセッションで独断で決めた点(人間が一度見ること):**

- **ADR を3本に割る割り方**(判断1つにつき1本。§11-18 と §11-19 を ADR-035 にまとめた)
- **#22 に 22 という番号を割り当てたこと**
- **副次セルの規模を 80 項目(`id` × carry/nocarry × n=40)と書いたこと。**
  人間が決めたのは「現状維持 + 副次セル」までであり、**セルの構成と n は未承認**

**次にやるべきこと: 順0 の記録(ADR-034 / 035 / 036)と §12-11 のコード反映。**
そのまま貼れるプロンプトは `logs/HANDOFF.md`。

**完了したこと(1つ前のセッション。PLANNER。2026-08-27。PLAN-004 の新設):**

- **`plans/PLAN-004-phase0-route.md` を新設した。**Phase 0 完了までを**順0〜順9**に割り、
  各順に**担当 / GPU 要否 / 依存 / 状態欄 / 判定できる完了条件**を持たせた。
  **`STATE.md` の「Phase 0 に必要な段階」は段階 A〜E の定義、PLAN-004 はその中を実行順に割った
  作業単位**という分担にした。**順が終わったら §2 の状態欄・§3 のチェックボックス・§7 の
  実行ログを同時に更新する**(同 §8)
- **段階 B の表に無かった承認待ちを2件登録した**(PLAN-004 §5、`STATE.md` 段階 B 表にも追記):
  **#20 生成設定** / **#21 本番の評価テンプレート集合(T1b / T3)**。
  **どちらも段階 C を回すのに必須**であり、`CLAUDE.md` §8 によりエージェントは決められない
- **順序の罠を4件、明文化した**(PLAN-004 §6)。特に **#9 の 0.70 と `θ` を実測より後に決めると
  事後選択になる**こと、**`θ` は「値」ではなく「決定規則」を先に凍結すれば C-1 と C-2 を
  同じポッドで連続して回せる**こと
- **人間が方針を決めた: 段階 C を先に回す。ただしその前に順1(GPU 不要の実装)を通す。**
- **コードは1行も変更していない。**`results/` は空。RunPod 未使用(GPU 時間 0)。
  事前登録の tag なし。**実験結果の数値は1つも無い**

**⚠️ このセッションで独断で決めた点(人間が一度見ること):**

- **PLAN-004 の順序そのもの**(順0〜順9 の並びと依存)。特に
  **順8(訓練コード)を順1〜7 と並行に置いたこと**と、**順0 の3判断を最初に置いたこと**
- **#20 / #21 に 20・21 という番号を割り当てたこと**(`plans/PLAN-003-redesign.md` §11 の続き)
- **PLAN-004 が `plans/TEMPLATE.md` の §2 / §3 / §11 を持たないこと**(実験プランではないため)

**次にやるべきこと: `plans/PLAN-004-phase0-route.md` の順1。**仕様は同 §4、
そのまま貼れるプロンプトは `logs/HANDOFF.md`。

**完了したこと(2つ前のセッション。IMPLEMENTER。2026-08-26。A-6 = 評価プールの CLI。★段階 A 完了):**

- **人間が ADR-033 を採択した。**★A-5 が回避していた未解決
  (`spec_sub` / `spec_mul` をプール manifest の `reference_rules` にどう載せるか)に
  3案を提示し、**「欄を分ける」**が選ばれた。`reference_rules` は加算側のまま、
  **`specificity_reference_rules`** を新設した。**混ぜる案を却下した理由**は、
  混ぜると `eval.reference_rule: spec_sub` を主軸のバッチに誤指定しても
  `validate_reference_rule` が素通しするからである
- **`code/data_gen/eval_pool.py`(新規)。**評価プール(`items.jsonl` +
  `manifest.json`)を書き出す入口。形は `ft_data.py` に揃えた。
  **`infra/preflight.py` の `data_checks` 6項目がすべて PASS になった**
  (**検査6 = format hash / 検査8 = coverage_k floor** を含む)。**これが A-6 の完了条件**
- **`pool.build_manifest` に必須引数を2つ足した**(ADR-033 決定2・3):
  `specificity_reference_rules` と **`fill`**(このプールをどう埋めたか)
- **`code/eval/battery/build.py`(新規)。**明示リストから4群の項目を作る
  ディスパッチャを `run.py` から移した。`eval_pool.py` と `run.py --dry-run` の
  2箇所が同じ分岐を要るため
- **`run.py` の `dry_run` が特異性側にも `validate_reference_rule` を掛ける。**
  docstring から未解決の記述が消えた
- **`ft_data.py` の CLI に `--condition`**(ADR-033 決定5)。5条件は
  `lesion.condition` 以外を共有するので、config を複製すると写し間違いで
  `train.jsonl` のバイト一致が壊れる
- **`.gitignore` が壊れていたのを直した。**`data/generated/*` がディレクトリごと
  除外していたため git が中に降りず、**「manifest だけ追跡する」という元からの
  意図が1件も効いていなかった。**このコミットで manifest 4件が初めて入る
- `pytest code/tests -q` → **405 → 423 passed**(2026-08-26 実測、3.8 秒)。
  `results/` は空。RunPod 未使用(GPU 時間 0)。事前登録の tag なし

**⚠️ このセッションで独断で決めた点(凍結までに人間が一度見ること):**

- **manifest の欄名 `specificity_reference_rules` / `fill`**、config のキー
  **`eval.pool_items` / `eval.pool_seed` / `eval.extrapolation_radius` /
  `eval.extrapolation_run_id`**、`fill.method` の値 **`explicit_list`**
- **`ft_data.py --condition` を足したこと**(ADR-033 決定5 に理由を書いた)
- **`configs/smoke.yaml` の T2 の5組を差し替えたこと。**場面テンプレートの割当は
  `(pool_id, a, b)` の sha256 で決まるので、`pool_id` が `smoke` → `main` に
  変わると5場面に散らなくなる。散る組に替えた(配線確認として5場面すべてを描画するため)

**⚠️ 未解決のまま残したこと:**

- **評価プールはサンプリングしていない。**`eval.pool_items` の明示リストで埋めている。
  **外挿域の上限 `M*` が未決(承認待ち-15)で `extrap` セルが原理的に埋まらない**ため、
  セルの充填方針を決めても完成しない(ADR-033 決定4)。manifest の `fill` に記録した。
  **`M*` が決まったら `fill_cells` を呼ぶ経路に置き換わる**
- **`configs/smoke.yaml` は3条件(`p2` / `x2` / `ident`)しか宣言できない。**
  `digit_modulus` / `arbitrary_table` を持たないため。**本実験は5条件そろえること**
- **本実行(モデルの読み込みと生成)は依然 `NotImplementedError`。**段階 C 以降
- `infra/preflight.py` の `check_data_manifest` は `files` の表を持つ manifest を
  期待するが、`ft_data.py` が書く manifest は `files` を持たない。**`data.manifest` を
  埋めると FAIL する。**いまはどの config でも `null` なので SKIP している。
  **どちらの schema が正なのかは決めていない**

---

**完了したこと(2つ前のセッション。IMPLEMENTER。2026-08-26。A-5 = `run.py` の数値経路):**

- **`parse_numeric_response(text, elicitation)` を `code/eval/run.py` に追加した。**
  `direct` は `numeric.parse` のみ、`cot` は `cot.extract_final_answer` → `numeric.parse`。
  `parse_boolean_response` と同じ形(PLAN-001 §5.5)。
  **「数が2個以上なら parse_fail」は緩めていない**(§5.4 の 4)。
  印の集合が2段で違うことをテストで固定した —— `therefore` は `cot.py` の
  `CONCLUSION_MARKERS` にあるが `base.ANSWER_MARKERS` には無いので、
  同じ出力が direct では parse_fail、cot では値になる
- **`dry_run` を4群のディスパッチにした。**`comparison` / `bare_sum` /
  `word_problem` / `specificity`。**一括ループにしていない** —— 群ごとに
  項目生成器のシグネチャ・応答型・文面の出どころ・参照規則の渡し方が違う
- **`scoring_batches` を新設。採点バッチは群と一致しない。**特異性対照だけ
  category(`spec_sub` / `spec_mul`)で割る。混ぜると
  `scoring._shared_reference_rules` が止める(**止まるのが正しい**)
- **`load_group_templates` を新設。`bare_sum` だけ文面の出どころが違う** ——
  `numeric_sum.bare_sum_templates(config)` から組み、評価用テンプレート集合から
  引かない。引くと T1 の評価アンカーが静かに訓練書式から離れ、検査6 が止まる
- **`dry_run_entries_by_group` を新設。`eval.dry_run_items` の各項目に `group` を必須**にした。
  category から逆引きしない(対応表が2箇所に散る)。`eval.batteries` に無い群は
  黙って捨てずに止める
- **返り値の形を変えた**: `report["by_response"]` → **`report["by_batch"][バッチ名]`**。
  常答戦略の理論値は**二値バッチにだけ**付ける
- **数値の固定応答は項目ごとに文面が変わる**(`DRY_RUN_NUMERIC_RESPONSES`)。
  1本の固定文字列では correct と rule の両方に到達できないため。
  真値・規則適用値は `to_response(item, None)` から取り、採点器と同じ経路にした。
  **実験の刺激ではない**
- `configs/smoke.yaml` の `dry_run_items` を 6 → **17 件**、
  `configs/templates/smoke.yaml` に `word_problem`(5場面)/ `specificity`(2演算)の
  **仮文面**を追加。**ADR-032 の確定文面は書き写していない**(正本は `t2.yaml`)
- `pytest code/tests -q` → **390 → 405 passed**(2026-08-26 実測、3.8 秒)。
  `results/` は空。RunPod 未使用(GPU 時間 0)。事前登録の tag なし。commit `47d2cda`

**⚠️ このセッションで独断で決めずに回避した点(→ 2026-08-26 に ADR-033 で決着):**

- ~~**特異性対照だけ `scoring.validate_reference_rule` を通していない。**~~
  **決着済(ADR-033 決定1・2。人間が採択)。**プール manifest を
  `reference_rules`(加算側)と `specificity_reference_rules` の2欄に分けた
- **`report["by_batch"]` のバッチ名(`spec_sub` / `spec_mul`)は実装で決めた。**
  凍結までに人間が一度見ること

---

**完了したこと(1つ前のセッション。IMPLEMENTER。2026-08-26。項目生成器):**

- **T1 / T2 の項目生成を実装した** —— `code/eval/battery/numeric_sum.py`(新規)。
  出力=数値の2水準を1モジュールに置いた(`t3_comparison.py` が出力=二値の
  2水準を置いたのと同じ切り方。ADR-026 の 2x2)
  - **T2 は被演算子 1 を候補の段階で外す**(`eligible_word_problem_pairs`)。
    項目生成に来たら `ExcludedOperandError` で止める。**黙って落とすとセルの
    件数が静かに減り、条件間で項目集合がずれる**
  - `word_problem_exclusion_record` が manifest 用の記録を作る(ADR-032 決定4)
  - **0 / 負の被演算子は安全網として拒否する。除外ではない**(§3.3 により
    主軸の3水準には構成的に現れない)
  - `bare_sum_templates(config)` で T1 の文面を `data.prompt_template` から組む
- **特異性対照を実装した** —— `code/eval/battery/specificity_control.py`(新規)と
  `code/lesion.py` の `SubtractionOffsetLesion` / `ProductOffsetLesion`(§7.1 改修③)。
  **`reference_lesions_from_config` には混ぜていない** —— 混ぜると FT データの
  除外集合が変わり、PLAN-002 §3.4 の「条件間で target 以外は同一」が壊れる。
  そのことをテストで固定した
- **評価アンカーの書式ブロックを実装した** —— `code/data_gen/prompt_format.py`(新規)。
  `pool.build_manifest` に `prompt_format_block` / `item_exclusions` を**必須引数**として追加。
  `ft_data.py` の直書きも同じ関数に寄せた(**ハッシュ値は変わっていない**)
- `code/data_gen/battery_items.py` の `SUPPORTED_GROUPS` に
  `bare_sum` / `word_problem` / `specificity` を追加
- `pytest code/tests -q` → **341 → 390 passed**(2026-08-26 実測、3.5 秒)。
  `results/` は空。RunPod 未使用(GPU 時間 0)。事前登録の tag なし

**⚠️ このセッションで残した穴(次セッションの作業。重要度順):**

1. ~~**`code/eval/run.py` の数値経路(cot → numeric)が未実装。**~~
   **→ 2026-08-26 に完了(A-5。commit `47d2cda`)。**`to_response` の
   シグネチャの違い(参照規則が辞書か単体か)は、群ごとの分岐 +
   `functools.partial` での束縛で吸収した
2. **評価プールを書き出す入口(CLI)が無い。**したがって
   `eval.anchor_manifest` / `eval.cells` を書ける config はまだ無く、
   **preflight の検査6・8 は FAIL のまま**(PLAN-002 §4.8 が「それが正しい」と
   書いた状態が続いている)。書くときは `prompt_format.build_from_config(config)` と
   `numeric_sum.word_problem_exclusion_record(...)` を `build_manifest` に渡すこと
3. **`data.eval_template_set` はどの config でも `null` のまま。**
   T1b / T3 の本番文面が未確定(実験条件。`CLAUDE.md` §8)。
   `configs/templates/t2.yaml` はテストが読むだけで config からは参照していない
4. PLAN-002 §4.9.3 の #7 / #8 / #12 は未実装のまま(承認待ち-11 の決着待ち)
5. **報告のみ(直していない)**: 上の「repo の状態」表に、**本セッションより前から
   古い行がある** —— 「出力パーサ**6**モジュール」(2026-08-25 に `japanese.py` を
   削除して5)、「評価側の `arb` 定義域ガードは未実装 / `g6_comparison.py:89`」
   (2026-08-25 に `t3_comparison.py` で解消済、ファイル名も変わっている)、
   `pytest` の件数の古い行が複数 → **2026-08-26(A-6)に整理した。**
   パーサ 6 → 5、`arb` 定義域ガードの解消、`prompt_format` の行、`pytest` の件数を
   打ち消し線 + 現行値の形に揃えた

**実装で確定させた点(どの ADR にも無い。★事前登録の凍結までに人間が一度見ること):**

| # | 確定 | 覆すとどうなるか |
|---|---|---|
| 1 | T1 の群名 `bare_sum` / 特異性対照の群名 `specificity` | `item_id` が変わるだけ。解析には効かない |
| 2 | category 名 `t1` / `spec_sub` / `spec_mul` | 同上 |
| 3 | **T2 のテンプレート割当は `(pool_id, a, b)` の sha256** | §4.3 は「`item_id` のハッシュ」と書くが `item_id` は category を含み**循環する**。覆すと `(1 \| template)` の水準の割り当てが変わる。**凍結前に決めておくべきはこれ** |
| 4 | `build_manifest` の `prompt_format_block` / `item_exclusions` を必須にした | 既定値を作ると、欠けた manifest が preflight から見て「訓練と評価で書式が違う」に化ける |
| 5 | 評価アンカーの manifest も `completion_template` / `loss_on` / `packing` を書く | 検査6 が「§4.8 と**同形**のブロック」を要求するため。評価側にとっては転記であり挙動を決めない |
| 6 | **manifest の欄名 `specificity_reference_rules` / `fill`**(2026-08-26。ADR-033 決定2・3) | 欄名が変わるだけ。ただし既に書いた manifest を読み直す必要がある |
| 7 | **config のキー `eval.pool_items` / `eval.pool_seed` / `eval.extrapolation_radius` / `eval.extrapolation_run_id`**、`fill.method` の値 `explicit_list`(同上) | `pool_items` は `M*` 確定後に `fill_cells` の経路へ置き換わる**暫定のキー**である |
| 8 | **`ft_data.py --condition`** で条件を差し替える運用(ADR-033 決定5) | 覆すなら条件ごとに config を複製することになる。写し間違いで `train.jsonl` のバイト一致が壊れる |
| 9 | **`configs/smoke.yaml` の T2 の5組を差し替えた**(2026-08-26) | 場面割当は `(pool_id, a, b)` の sha256。`pool_id` が `smoke` → `main` に変わり5場面に散らなくなったため替えた。**smoke 専用であり実験条件ではない** |

**引き続き未解決(前セッションから持ち越し。人間の判断)**: #18(T1 にも答え書式の
指示を足すか)/ #19(被演算子 1 の除外を全タスク型に広げるか)/ #9(適格性フィルタ 0.70)/
#16・#11(Feucht と G7)/ #13(`table[1]` の穴)/ PLAN-002 §12-11(`p2d` 判別不能の
除外を `K` の母集団に掛けるか)。

---

**完了したこと(前セッション。PLANNER。2026-08-26。承認待ち-6 の決着):**

- **ADR-032 を採択した。**人間が T2 の5テンプレート文面を確定した(決定1〜5。上表)
- **`configs/templates/t2.yaml` を新設**(起草案 `t2_draft.yaml` は削除)
- `plans/PLAN-003-redesign.md` §4.3 を確定文面の表に置換し、**文面規約に 6(答え書式の指示)/
  7(被演算子 1 の除外)を追加**。§11 は #6 を決定済みへ移し、**#18 / #19 を新設**
- **パーサを想定応答に通して裏を取った(2026-08-26。実験ではない)。**
  `320` / `Answer: 320` / `$320` / `320 dollars` / `There are 320 apples in total.` /
  `150+170=320` はすべて 320 を返す。落ちるのは**印が無く数が複数**の型だけで、
  決定3 の指示がこれを潰す
- **コードは1行も変更していない。**`pytest code/tests -q` → **341 passed**(2026-08-26 実測)

**次にやるべきこと**: 項目生成(T1 / T1b / T2 / T3 + 特異性対照)。
段階 A に残っているのはこれだけである。詳細は `logs/HANDOFF.md`。

**未解決(このセッションで新たに立てたもの)**:

- **#18 T1 にも答え書式の指示を足すか。**決定3 により T2 だけが指示文を持つので、
  **タスク型の軸に「指示の有無」が乗る。**ADR-025 が却下したのと同型の交絡である。
  現状維持(T1 は `{a}+{b}=` のまま)でもよいが、**申告するかどうかは人間の判断**
- **#19 被演算子 1 の除外を全タスク型に広げるか。**決定4 は T2 限定なので、
  T2 だけ被演算子分布が他タスクと厳密には一致しない

---

**完了したこと(前セッション。IMPLEMENTER。2026-08-25。実装順 4):**

- **`infra/preflight.py` に PLAN-002 §4.8.1 の検査を実装した**(既存9項目 → **16 項目**)。
  検査5(`matched_stream_sha256`)/ 6(`format_hash`)/ 7(トークン境界)/ 8(`coverage_k` の下限)/
  **9(`t_holdout.sums_hash`)/ 10(`K ∩ T_hold = ∅`)** と、**検査3 の拡張**
  (`counterpart_region_hash` を分割パラメータから再現して照合)
- **`SKIP` と `FAIL` を混ぜない方針を実装で確定した。**SKIP は「この実行には対象が存在しない」
  (config なし / `lesion.condition: none`)に限り、**宣言・依存・トークナイザの欠落は
  FAIL(未実行)**。`configs/smoke.yaml` で preflight を走らせると FAIL する(**それが正しい**)
- **config に3項目を新設した**(いずれも `null` 始まり、`configs/template.yaml` に記載):
  `data.matched_manifests`(全病変条件の manifest 一覧)/ `eval.anchor_manifest`(T1 アンカー)/
  `eval.cells`(評価プールのセル定義)。**検査8 の `id` 要求はここから実行時に数える。
  リテラルの閾値はコードにもプランにも置かない**(PLAN-001 §4.2.2)
- 検査9 は**ハッシュの一致だけでなく `build_t_holdout` で構成を再現**して照合する。
  ハッシュ一致だけでは「全条件が同じようにずれている」を見逃す
- 検査7 は `--run-dir` に `token_boundary.json` を書き、**§4.1.3 の
  「テンプレート適用後の書式ハッシュ」をここで出す**(`ft_data.py` は §4.1.5 により計算できない)
- **文書の訂正**: `id` セル要求 **556 → 520**(PLAN-001 §4.2.2・§13、PLAN-002 §4.8.1 の3箇所が
  PLAN-003 §4.7 の改訂に追随していなかった。**§5.1 の表と本文は 520 で正しかった**)。
  `configs/template.yaml` の「K は 560 以上」も実行時計算の説明に差し替えた
- **テスト**: `code/tests/test_preflight_checks.py` を新規作成(**38 件**)。
  manifest は手で書かず `ft_data.generate` で実際に作る。トークナイザは偽装する
  (本物の `transformers` は import に 13 秒かかる)。
  `pytest code/tests -q` → **302 → 340 passed**(2026-08-25 実測、3.2 秒)。
  `pyproject.toml` の `pythonpath` に `infra` を追加した
- `infra/RUNPOD.md` §3 の検査一覧と §4 の `runs/<id>/` 必須成果物を同期した

**⚠️ このセッションで残した穴(実装の不足ではなく仕様どおり):**

- **検査6・8 を通せる config はまだ作れない。**`eval.anchor_manifest` / `eval.cells` を
  埋めるには評価項目の生成器が要る。~~承認待ち-6(T2 の文面)で止まっている~~
  → **2026-08-26 に ADR-032 で決着。生成器を書けば埋まる。**
  本物の config が来るまで両検査は FAIL で止まる
- ~~**`code/data_gen/pool.py` の `build_manifest` は `prompt_format` ブロックを持たない。**~~
  → **2026-08-26 に埋めた。**`prompt_format_block` は必須引数になり、
  `code/data_gen/prompt_format.py` が訓練側と同形のブロックを組む。
  **ただし manifest を書き出す入口がまだ無いので、検査6 は依然 FAIL である**
- **`templated_format_hash` と評価アンカーの照合は未実装。**アンカー側が同じ値を記録して
  からでないと、仕様ではなくテストのほうが原典になる

**完了したこと(前セッション。IMPLEMENTER。2026-08-24。実装順 2/3):**

- **`PLAN-002` §4.2 を ADR-029(`T_hold`)に追随させた**(commit `d8320a6`)。
  §4.2.1a を新設し、`T_hold` の構成(`carry` 比例配分 + 等間隔)を決定的な手続きとして固定。
  §4.2.2 / §4.2.3 / §4.2.4 / §4.7 / §4.8 / §4.8.1 / §4.9.2 / §4.9.3 / §12 を同期した
- **`code/data_gen/ft_data.py` を実装した**(commit `a956be4`。実装順 2)。
  `eligible_pairs(..., indistinguishable_rule_pairs=[(p2, p2d)])` を配線済。
  **`T_hold` の構成が ADR-029 根拠表の 20 個と完全に一致した**
- **`code/config.py` を新設し、`code/lesion.py` に config→規則の組み立てを追加した。**
  `data_gen` が `eval` を import する層またぎを避けるため(skill code-style §2)。
  `code/eval/run.py` は委譲するだけになった(公開名 `build_reference_lesions` は残した)
- **`configs/template.yaml` の `lesion` 節に `[MATCHED]` 印を付けた**(新規の明示化)。
  `offset` / `multiplier` / `arbitrary_table` / `digit_modulus` は参照規則の集合を決めるので、
  条件ごとに違うと `K` がずれ §3.4 のバイト一致が壊れる。
  **`arb` を回さない条件の config にも `arbitrary_table` を書くことになった**
- **テスト**: `test_ft_data.py` / `test_design_facts.py` を新規作成。
  `pytest code/tests -q` → **256 → 302 passed**(2026-08-24 実測)。
  `python -m code.data_gen.ft_data --config configs/smoke.yaml --dry-run` が通る

**⚠️ このセッションで新規に立った人間の判断(`PLAN-002` §12-11):**

ADR-029 根拠表は `t ≡ 0 mod 10` の除外を **`K` の抽出母集団**の行に置いている。
実装がそれに従った帰結:

1. **`p2d` を設計に含む限り、訓練データに `t ≡ 0 (mod 10)` の式は1件も現れない。**
   `p2d` 条件のモデルは**自分の桁規則の「+0」の場合を一度も見ない。**
   `T_hold` の穴に、`p2d` と `p2` が一致する剰余類の穴が重なる
2. **`carry` 密度が保たれない。**`t ≡ 0 mod 10` は必ず `nocarry` なので片側だけが削れる。
   main 領域で 20.0% → **22.3%**(`K_main` の `carry` 393 → 435)

掛けない案は「`K` には残し、**評価項目を `K` から引くときにだけ**落とす」。
**現在の実装は掛ける側。**訓練分布が変わるので `CLAUDE.md` §8 に当たる。

**次にやるべきこと(段階 A の残り。上から順に):**

| 順 | 作業 | 塞いでいるもの |
|---|---|---|
| ~~1~~ | ~~**実装順 4**: `infra/preflight.py` の検査~~ → **2026-08-25 完了** | — |
| 1 | `g6_comparison.py` → `t3_comparison.py` 改修(T1b の `category` / 英語化 / **`arb` を `ans_in` に限定**) | なし。**すぐ着手できる** |
| 2 | D-3 の後始末(`parsers/base.py`・`boolean.py` の日本語語彙を外す、`parsers/japanese.py` を捨てる) | なし |
| 3 | Phase 0 タスク8: **R8 掃引モード**(ADR-030) | なし |
| 4 | **項目生成**(T1 / T1b / T2 / T3 + 特異性対照)。**併せて `pool.build_manifest` に `prompt_format` ブロックを足す**(preflight 検査6 の照合対象) | ~~★承認待ち-6~~ → **2026-08-26 決着(ADR-032)。着手してよい**。T2 は `configs/templates/t2.yaml` の5テンプレート、**被演算子 1 を除外**、群名 `word_problem` |

**残っている穴(このセッションの範囲外):**

- **`§4.9.3` の #7(周期タスクのセル母集団)/ #8(厳格な結合律)/ #12(G7 の 15 件セル)は
  未実装。**G7 の項目構成(PLAN-002 §5.1)と多項項目の規約(§4.5.3)がコードに無いため。
  承認待ち-11 / PLAN-002 §12-3 の決着後に書く。
  **ADR-022 の未検算のもう1件(`carry × 1桁` 層)は検算済**(`T_hold` と `t≡0` 除外の
  両方を重ねても 15 組すべて残る)
- **`§4.7` の「両方向 `id` の交換律ペア 419」は `coverage_seed` 依存であり未再計算。**
  `coverage_seed` は `configs/template.yaml` で `null` のまま。**シード確定後に再計算する**
- **`code/eval/battery/g6_comparison.py:89` の `arb` 定義域ガードは未実装のまま**
  (前セッションからの持ち越し)

**完了したこと(前セッション。IMPLEMENTER。2026-08-24。実装順 0/1/1b/1c):**

- **人間が承認待ち-12 に回答した: `arb` を実験条件として残す(5 シード)。**
  ADR-028 の 40 run 構成は不変。**帰結として #13(`table[1]` の穴)が「必要」に昇格した**
- **実装順 0 / 1 / 1b / 1c を実装し commit した**(`b2c78e3`)。内訳は `logs/CHANGELOG.md` 2026-08-24。
  `Lesion.is_defined` による定義域ガード(ADR-020)/ 被覆ラベル4値 + 答え域ラベル /
  `label_t_coverage` + `coverage_sums_of`(ADR-021)/ `DigitOffsetLesion` と
  `is_indistinguishable`(ADR-022)。**`pytest code/tests -q` → 227 → 256 passed**(実測)
- **ラベルの本番スケール件数を実装で検算し、ADR-020 根拠3 / ADR-021 根拠の表と完全一致した**
  (組合せ論的事実。実験結果ではない)。**その過程で `PLAN-002` §4.6 の表の2箇所の誤りを発見し、
  人間の指示で訂正した**(`oob·ans_out` 19,899 → 20,098 / `extrap_magnitude` 80,000 → 80,200)
- **人間が「仕様判断3件を承認する」と回答した**(下の「未解決」参照。もう承認待ちではない)
- **`STATE.md` に「Phase 0 に必要な段階」節を新設した**(段階 A〜E)。
  `04_EXPERIMENT_PLAN.md` Phase 0 のタスク 1〜8 と Go/No-Go を依存順に並べ直したもの

**前セッション(PLANNER。2026-08-24。#14 の決着と原典依存の棚卸し):**

- **人間が「今回の論文が本当に Feucht et al. を原典とする構成か」の再分析を指示 → 実施した。**
  結論: **「原典」という拘束を作った条項(ADR-018 決定1)は ADR-024 決定1(D-1)が既に上書きしており、
  失効していた。**乖離は revision 水準ではなく**変種水準**(base → `-Instruct`)で起きている
- **人間が #14(`model.revision`)について「AI の判断を承認する」と回答 → ADR-031 を採択した。**
  pull 時点の HF コミットハッシュで固定 / **原典一致は要求しない** /
  **`CLAUDE.md` §8 の判断事項から外した**(必要性の出所が「原典への忠実さ」から
  「ADR-025 の `chat_template` に伴う内部再現性」に入れ替わったため)
- **`Documents/06_THREATS.md` に T13「モデル同一性」を新設。**乖離を変種 / revision / 入力書式の
  3水準の表にした。**限界の記述を「revision 水準で保証できない」から
  「変種水準で既に異なる」に差し替えた**(前者は実態より軽い申告になる)
- **原典依存の記述を5箇所訂正した**(ADR-008 のステータスと2欄 / `configs/template.yaml` /
  `00_OVERVIEW.md` §6 / `02_RELATED_WORK.md` A 表 / `04_EXPERIMENT_PLAN.md` §0)
- **着手禁止を2箇所で解除した**(`04_EXPERIMENT_PLAN.md` Phase 0 タスク2 /
  `PLAN-001` §5.1.1)。**実装の入り口を塞ぐ未決は無くなった**
- **新規の承認待ちを2件立てた**: **#16**(Feucht を論文1でどう位置づけるか。#11 とセット)/
  **#17**(Nikankin et al. の原典確認)
- **コードは1行も変更していない。**`pytest code/tests -q` → **227 passed**(本セッションで実測)。
  `results/` は空。RunPod 未使用(GPU 時間 0)

**やっていないこと**: 実装への着手 / 事前登録の凍結(`git tag`)/ `05_STATISTICS.md` §6 の
検出力分析の再導出 / `PLAN-002` §4.2 への `T_hold` 軸の追加 / `09_PAPER_PLAN.md` の追随
(**未追随を新たに発見した。下記**)。

---

**完了したこと(前セッション。PLANNER。2026-08-23。設計文書の同期):**

- **PLAN-003 §10 の追随表6項目をすべて実施した。**書き換えた節は上の「いま何をしているか」に一覧
- **旧・主要評価項目(G6 の `p2` vs `ident`)を `05_STATISTICS.md` §2.1 に打ち消し線で保存し、
  降格先(Phase 0 の Go/No-Go #4)を明記した**
- **旧・ゲートキーピング階段を §4.1 に保存し、旧8項目それぞれの行き先を表にした。**
  旧5・旧6 に紐づいていた承認待ち項目「`id` 到達度を揃える」の操作的定義は
  **対象が消えたので閉じた**(代わりに Go/No-Go #4 / #4b が同じ役割を担う)
- **PLAN-001 の旧セル表(G0〜G7、3,565 項目)を §5.1.2 に保存した。**
  §4.1 / §4.2 / §4.3 / §5.4 は指示どおり無変更
- **`06_THREATS.md` T1 の「正味の損失」を本文に書いた**(切り分けの強い行が 3 → 1)
- **`03_OPEN_QUESTIONS.md` に Q16(主軸の交互作用)/ Q17 / Q18 を新設し、
  Q1・Q4 を却下、Q2 を「主軸から除外」に落とした。Q2 は「解決」にしていない**
- **★新たに未追随を1件発見した**: `05_STATISTICS.md` §6(検出力分析)。下のブロッカー欄

**やっていないこと(指示どおり)**: コードの変更 / 事前登録の凍結(`git tag`)/
`PLAN-002` §4.2 への `T_hold` 軸の追加(#14 待ち)/ `05_STATISTICS.md` §10 の予測の書き直し(凍結直前)。

---

完了したこと(前セッション。PLANNER。2026-08-23):

- **人間に3件のブロッキング質問をし、回答を得た**(PLAN-003 §2 の D-1 / D-2 / D-3)
- **`plans/PLAN-003-redesign.md` を起草した。**ADR-023 の要因計画からの再導出。
  完了条件6項目(項目構成 / 既知性の定義 / 主要評価項目 / 資産の存廃 / G2・G3・G5・G7 / 承認待ち)
  をすべて埋めた
- **人間が §11 の骨格 #1〜#5 を決定した。ADR-024 / 025 / 026 / 027 / 028 を採択し、
  PLAN-003 / PLAN-002 / 02_RELATED_WORK に反映した**(上の「いま何をしているか」に反映先の一覧)
- **続けて人間が #8(P-3 `T_hold`)と #7(R8)を決定した。ADR-029 / ADR-030 を採択した。**
  **#7 は「方法は任せる」との回答だったので、R8 の手続き(θ 17 水準 / T3+T1b / n=20 /
  ロジスティック当てはめの 0.5 交差点 / `β1 ≤ 0` は除外して件数報告)をエージェントが確定した。**
  **この手続きは人間の目視確認を受けていない**(`CLAUDE.md` §8 の「解析計画」に近い性質)

**コードは未変更。**`pytest code/tests --collect-only` → **227 collected**(本セッションで実測)。
`results/` は空。**実験結果の数値は依然として1つも無い。**RunPod 未使用(GPU 時間 0)。

---

### 再導出で出した答え(`plans/PLAN-003-redesign.md`。要旨)

| 論点 | 出した答え | 節 |
|---|---|---|
| タスク型 | T1/T2/T3 は「入力書式の距離 × 出力の型」の部分格子。**第4セル `T1b`(裸の比較)を足して 2×2 を閉じた**(P-1 → **ADR-026 採択**) | §3.1 / §4.5 |
| 被覆水準 | **`id` / `interp` / `extrap_magnitude` の3つに絞る。** `oob_algebraic` と `extrap_pair` は**負数を含むので文章題(T2)に書けない**。要因計画が共通層を要求する以上、T2 が水準を決める | §3.3 |
| 既知性 | **主軸は `(a,b)` 水準。** `t` 水準は `p2d` / `arb` の解析でのみ層に使う。ただし `K=2000` では `interp` の 99.6% が `t_seen` で**セルが埋まらない** → **`t` ホールドアウト `T_hold`(20 個)を訓練サンプリングに入れる提案(P-3)** | §5 |
| 主要評価項目 | **`p2` 条件の `rule_rate` を `task * coverage` の混合効果ロジスティック回帰で当て、交互作用項の LRT(**df=6**。ADR-026 で4水準になった)を主要検定にする。** 帰無仮説は「勾配が平行」。1仮説・1 p 値なので ADR-005 と両立 | §6.1 / §6.2 |
| 旧主要評価項目 | 「G6 の `rule_rate` を `p2` vs `ident`」は **Go/No-Go のペネトランス判定に降格**(基準 ≥ 0.90) | §6.5 #4 |
| 交絡対策 | **適格性フィルタ**: `ident` の `correct_rate` < 0.70 のセルは主解析から除外(事前登録) | §6.3 |
| R8 | **主要評価項目にはしない。** `Δ̂` は T1/T2 で定義できず、3タスク型で尺度が揃わないため。同じ掃引の副産物として副次に置く | §4.4.2 |
| 条件配分 | **ADR-028 採択**: `p2` 10 / `ident` 10 / **`p2d` 10** / `arb` 5 / `x2` 5 = **40 run**。`p2d` にも同一の交互作用モデルを当て、副次の順1 に置く | §3.4 / §6.4 |
| 項目数 | 主軸 **1,560 項目**(現行 3,565)+ 副次 §4.8 の 800 項目。`id` 要求は **520 組**で `K=2000` を下回る | §4.7 / §4.8 |
| チャットテンプレート | **ADR-025 採択(案 A)**: FT も評価も全項目を通す。T1 の無テンプレート版 240 項目を「テンプレート税」として併走 | §4.1.1 |
| 資産 | **`scoring.py`(4値分解)/ `battery_items.py` はそのまま。** `pool.py` / `g6_comparison.py` / `lesion.py` / `run.py` / `base.py` / `boolean.py` は改修。**`japanese.py` は捨て、`wordform.py` は凍結**。テストは 227 → 約 205 が残る | §7 |
| G7 | **探索的アドオンとして残す案を推奨**(案 A)。D-1(Instruct)で Feucht et al. との厳密一致が失われ、確証的主張の支柱にできない | §8.4 |

### 次セッションの作業

> **2026-08-23 更新: 骨格 #1〜#5 に加えて #8 / #7 も決着した(ADR-024〜030)。以下は次の段。**

**まず `plans/PLAN-003-redesign.md` §11 の未決のうち、次の3件を人間に消化してもらう。**

| # | 事項 | なぜ先か |
|---|---|---|
| ~~#8~~ | ~~P-3: `T_hold`~~ → **2026-08-23 決定「入れる」。ADR-029** | `\|T_hold\| = 20`、`carry` 比例配分(4/16)。`pool_split_seed` に紐づく設計定数。**実験シードで動かさない** |
| ~~#7~~ | ~~R8 の採否~~ → **2026-08-23 決定「実験に入れる。方法は任せる」。ADR-030** | θ 17 水準 `{-3..+13}` / **T3 + T1b 両方** / 各セル n=20 / `Δ̂` はロジスティック当てはめの 0.5 交差点 / `β1 ≤ 0` と非収束は除外して件数報告 / **`x2` は掃引しない** |
| ~~**#14**~~ | ~~**`model.revision`**~~ → **2026-08-24 決定「AI の判断を承認」。ADR-031** | pull 時点の HF コミットハッシュで固定。**原典一致は要求しない**(ADR-024 で変種が変わっているため)。`06_THREATS.md` **T13** 新設。**`CLAUDE.md` §8 の対象から外した** |

そのあと:

1. ~~**#6(T2 の5テンプレート文面)**~~ → **2026-08-26 決着(ADR-032)。**
   残るのは **#9(適格性フィルタ 0.70)**。事前登録の凍結までに要る実験条件
2. ~~PLAN-003 §10 の追随表に従って `05_STATISTICS.md` / `PLAN-001` §5.1 /
   `04_EXPERIMENT_PLAN.md` / `06_THREATS.md` / `03_OPEN_QUESTIONS.md` を書き換える~~
   → **2026-08-23 完了。**残りは `05_STATISTICS.md` §6(検出力分析)と §10(事前登録の予測)で、
   **どちらも凍結直前の作業**
3. **`05_STATISTICS.md` §6 の検出力分析を再導出する。**★本セッションで発見した未追随。
   主要検定が `task:coverage` の LRT(df = 6)に変わったので、想定効果量
   「G6 rule_rate 差 = 0.30」は対応しない。**シード数 10(ADR-028)は検出力分析ではなく
   設計判断で決まっており、このままでは「なぜ10か」を論文で説明できない**
4. **そのあとで**実装に入る(#12 が通れば `eligible_pairs` の定義域バグから)

**実装の順序は既に決まっている**(上の「PLAN-002 承認後の実装順」0 → 1 → 1b → 1c → 2 → 3 → 4)。
**ADR-025 / 026 / 027 / 028 で追加になった実装項目**:

- `code/lesion.py`: 特異性対照の参照規則(`a−b+2` / `a×b+2`)を追加(ADR-024 決定2 → PLAN-003 §4.6)
- `code/eval/battery/g6_comparison.py`: **裸書式(T1b)の `category`**(ADR-026)
- `code/eval/run.py`: **全項目へのチャットテンプレート適用**と、T1 の無テンプレート版を
  併走させる経路(ADR-025)
- `infra/preflight.py`: トークン境界検査を**テンプレート適用後**の文字列に対して行う(ADR-025)

**引き続き凍結する**:

- 事前登録の凍結(`git tag`)
- Phase 0 の GPU 作業
- PLAN-002 §12 の承認待ち9件(**PLAN-003 §11 が置き換える。旧9件を個別に消化しない**)

### 主軸と独立に残っている未解決

**すべて `plans/PLAN-003-redesign.md` §11 に番号付きで移した。**以下は対応表。

| 未解決 | PLAN-003 §11 の番号 |
|---|---|
| `eligible_pairs` の定義域バグ(該当 100,298 組。`arb` を渡すとプール生成が `KeyError`) | **#12**(`arb` を残すかとセット) |
| `table[1]` の穴。案(a) は使えないと判明済。**(b) か (c) に絞られている** | **#13**(`arb` を残す場合のみ) |
| ~~`model.revision`。D-1 で対象が Instruct になったので取り直し~~ → **2026-08-24 決着(ADR-031)** | ~~#14~~ 完了 |
| **(新規)** Feucht et al. を論文1でどう位置づけるか。**プレプリントなので主要な論拠に使えない**(`CLAUDE.md` §3) | **#16**(#11 の G7 とセット) |
| **(新規)** Nikankin et al. (2025) が ⚠️ 未原典確認のまま。Intro の対立軸の片側 | **#17** |
| 外挿域の上限 `M*` と桁数掃引の粒度(PLAN-001 §4.1.1) | **#15** |
| `p2d` の除外後に G7 の 15 件セルと `carry × 1桁` 層が埋まるかの未検算 | G7 の扱い(**#11**)が決まってから
