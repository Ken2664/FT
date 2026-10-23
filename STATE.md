# STATE.md — 現在の状態

> **このファイルはセッション開始時に必ず読む。作業終了時に必ず更新する。**
> ここに書かれていないことは「存在しない」ものとして扱う。
>
> **★2026-09-08(ADR-063)にこのファイルを 3 つに分けた。**それまで 417 KB / 3,939 行あり、
> `CLAUDE.md` §1 の `cat STATE.md` が実行できなくなっていた(引き継ぎ装置の機能不全)。
> **原因は「全部の節が過去のセッション記録を積み上げるスタックだった」ことである。**
> **各節の最新 1 ブロックだけが現在の状態で、残りは過去の記録だった。**

最終更新: 2026-10-23(その181。PLAN-045(R3)の草案 `plans/PLAN-045-interp-mirror-filter.md`。Q1〜Q5 は ADR-134 で採択(5 問とも推奨 (a))。probnull の生成は L_50 で停止(fits 0)・再開は人間。Claude Opus 5.5(PLANNER)。GPU 0・pod 0)
(**次: 人間が probnull の再開を決める・IMPLEMENTER が PLAN-045 I1〜I6**。)
---

## 0. このファイルの読み方(★2026-09-08 新設)

**3 つのファイルで役割を分けた。**セッション開始時に読むのは **`STATE.md` だけ**でよい。

| ファイル | 中身 | いつ読むか | 大きさの上限 |
|---|---|---|---|
| **`STATE.md`**(これ) | **いま何が本当か**だけ。各節は**最新 1 ブロックのみ** | **毎セッション頭。`cat` する** | **400 行 / 60 KB** |
| **`logs/OPEN-ITEMS.md`** | **人間の承認・判断を待っている事項の正本**(全文) | 人間に判断を求めるとき | — |
| **`logs/STATE-ARCHIVE.md`** | **過去のセッション記録**(読み取り専用の倉庫) | **経緯を追うときだけ。`grep` する** | — |

```bash
grep -n 'ADR-05[0-9]' logs/STATE-ARCHIVE.md | head   # 経緯を ADR 番号から辿る
grep -n 'その1[0-9]'  logs/STATE-ARCHIVE.md | head   # セッション番号から辿る
sed -n '1,60p' logs/OPEN-ITEMS.md                    # 人間待ちの索引だけ見る
```

**分割前の原本は `git show 4350ea8:STATE.md` で丸ごと取れる。**情報は 1 つも捨てていない。

---

## ★ 最優先(2026-08-23。ADR-023)★2026-09-08(その22)にアーカイブへ移した

> **本文は `logs/STATE-ARCHIVE.md` §9 へ丸ごと移した**(ADR-063 の運用規約1・6。**1 文字も削っていない**)。
> **正本は `Documents/00_OVERVIEW.md` §1(要因計画)と `logs/DECISIONS.md` の ADR-023(決定)。**

- **主要な推定対象は「タスク型 × 既知性の交互作用」。**問うのは**「既知性の勾配が
  タスク型間で平行か」**であって「病変が乗るか」ではない。**タスク型 4 水準**(ADR-026)
  × **既知性 3 水準**(ADR-027)、~~**交互作用の df = 6**~~。**G7 はオプション**(ADR-031)
- **★2026-10-01(ADR-111・ADR-112・ADR-113): 主要検定は T1 × T2(df = 2)。T1b・T3 は探索。H0 と H1 は E1(T2 の転移)で分ける**

---


## 並行ブランチ(登録簿) ★2026-08-27 新設

> **規約は `AGENTS.md`「並行作業とブランチ運用」。ここはその R3 が言う「表」である。**
> **表に無いブランチは存在しない扱いになり、main 側が同じ作業を作り直す。**
> セッション開始時に `git worktree list && git branch --list 'wt/*' -v` を実行し、
> この表と食い違っていたら**作業を始める前に**人間に報告する。

| ブランチ | worktree | 役割 | 担当する順 | 開始 | 状態 |
|---|---|---|---|---|---|
| `main` | `C:\Users\keenk\paper\FT` | (本線) | — | — | 進行中 |

**並行ブランチは無い**(2026-08-30 時点。`git worktree list` = main のみ)。

> **★2026-10-02(その133): 登録されないまま現れた worktree `claude/great-bardeen-9c1ac4`(PLAN-038 の 1 commit `0410b6c`。別セッションの作業)を開始手順で見つけて人間に報告し、人間の指示で main に fast-forward した。worktree とブランチの削除は人間(まだ残っている)。**

> **破棄した並行ブランチ(`claude/objective-mestorf-34f57d`)の記録は `logs/STATE-ARCHIVE.md` §3 にある。**
> **登録されないまま現れたリモートブランチ `claude/magical-carson-fxa3eq`(クラウドセッションの 1 commit `d98d423`。main の `2b10eff`・`d9df3ae` と重複)は 2026-09-12(その48)に人間の指示で削除した。記録は `logs/CHANGELOG.md` その48。**

---

## いま何をしているか


> **★★2026-10-23(その181・最新)。Phase 0。Claude Opus 5.5(PLANNER)。PLAN-045(R3)の草案を書いた。GPU 0・pod 0**
> - **やったこと**: `plans/PLAN-045-interp-mirror-filter.md` 草案。§3 に組合せ論的な計数(現行の主プールの割当を 42 セルすべて再現 → `mirror_in_K` の件数: `interp` T1 14/80・T2 18/80 / `id` T1 21/80・T2 26/80。フィルタ後も 42 セルすべて埋まる(carry 層の供給 443 対 需要最大 280)。母集団から除くと `interp` セルはほぼ全部入れ替わる(T1 76/80・T2 79/80))。§4 に Q1〜Q5(範囲・除き方・`mirror_in_K` の定義と記録先・`id` の二重露出・順6 の測り直し)を判断材料の表で。**人間が 5 問とも推奨 (a) で採択 → ADR-134**
> - **★probnull の生成が途中で止まっている**: `ceiling_probnull_L05` は fits 100/100(2026-10-22 22:22 JST に完了)・`ceiling_probnull_L50` は fits 0(manifest 00〜04 だけ書いて止まった)。pid 31768 は無い・ログは 0 バイト。**再開は人間が決める**(同じコマンドで再開できる。HANDOFF その179)
> - **天井のシートの数値の正本は PLAN-044 §13.1**


---

## わかっていること

### ★F140 の再採点(2026-09-22 その71。PLAN-027 §5・§6。**GPU 0。解釈はしていない**)★2026-09-24(その80)に表をアーカイブへ移した

> **本文(規則 C の定義・「最終の非空行」の 2 通りの読み方・再採点 9 本の検査表・4 値が動いたバッチ)は `logs/STATE-ARCHIVE.md`「その80」へ丸ごと移した**
> (ADR-063 運用規約5。`STATE.md` が 400 行を超えていたため。**1 文字も削っていない**)。**数値の正本は各再採点 run の `metrics.json` と `results/rescore_f140/summary.json` である。**

- **★正本 = 再採点後(規則C込み)の数値**(ADR-091)。**C1 / C2 / C4 は 9 本すべて pass。C5(Go/No-Go の印)は 1 つも動かなかった**(`logs/OPEN-ITEMS.md`「その71 の追記」)
- **R5(T2 交差)[run:20260922_134110_rescore_order6_r5] は Go/No-Go の表を組めないままで未解決**
- **`M*` は置き直さない**(ADR-088 決定5)。元の run の `metrics.json` / `predictions/` は書き換えていない(ADR-074 決定2)

### ★順6(2026-09-11 その44。素の `Llama-3.1-8B-Instruct` / adapter null / RTX 4090。**解釈はしていない。印は `gonogo.py` が付けたもの**)

**5 run すべて 4 値の合計が全ブロックで 1.0、`items_sha256` は manifest と一致**(主プール `d272204f…` = R1〜R4 / 交差 `8cb8a58f…` = R5)。

> **★2026-09-26(その104)に R1〜R5 の表を `logs/STATE-ARCHIVE.md`「その104」へ丸ごと移した**(60 KB 超のため。ADR-063 運用規約5。1 文字も削っていない)。**数値の正本は各 run の `metrics.json`**

> **★2026-09-25(その95)に、Go/No-Go の表(R1)・★F138・★F139・★F140・R4 の分類・その46 の数え上げの箇条書きをアーカイブへ丸ごと移した**(`STATE.md` が 60 KB を超えたため。ADR-063 運用規約5。**1 文字も削っていない**。
> `logs/STATE-ARCHIVE.md`「その95」)。**印の位置(R1): #2 は T3・T1b の 6 セル / #3 は T1b `interp` 以外の 5 セル。数値の正本は各 run の `metrics.json` と `results/gonogo_order6/gonogo.json`。**

### ★順6b(2026-09-22 その70)★2026-10-01(その125)にアーカイブへ移した

> **表と判定表の要約は `logs/STATE-ARCHIVE.md`「その125」へ丸ごと移した**(ADR-063 運用規約5。60 KB 超のため。1 文字も削っていない)。**数値の正本は各 run の `metrics.json` と `results/order6b_select/order6b_select.json`**

### ★順5 の再採点 [run:20260910_215422_rescore_sweep_m](2026-09-11 その40)★2026-09-22(その71)にアーカイブへ移した

> **本文(C1〜C5 の結果と腕1・腕2 の 13 水準の表)は `logs/STATE-ARCHIVE.md`「その71」へ丸ごと移した**
> (ADR-063 運用規約6。**1 文字も削っていない**)。**数値の正本は run の `metrics.json` である。**
> **同じ run を ★F140 込みで読み直した結果は上の「★F140 の再採点」にある**(`M*` は置き直さない。ADR-074 決定1)。

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

### 設計の帰結(2026-08-23。ADR-020 / 021 / 022)★2026-09-24(その77)にアーカイブへ移した

> **表(13 行)は `logs/STATE-ARCHIVE.md`「その77」へ丸ごと移した**(ADR-063 運用規約5。`STATE.md` が 400 行 / 60 KB を超えていたため。**1 文字も削っていない**)。
> **正本は ADR-020 / 021 / 022 と `plans/PLAN-001` §5。**要点: `arb` は `ans_out` で検証不能・`ans_in` で検証可能 / `p2d` が `p2` と一致するのは `t ≡ 0 (mod 10)` だけ

### repo の状態

| 事実 | 根拠 |
|---|---|
| `pytest code/tests -q` → **2405(`-k 'not smoke'`。★その144 実測)**。~~2383(`-k 'not smoke'`。R を使うスモーク 11 件は未実行) passed~~(2026-10-03 その139 実測。`test_undecided_values_stay_null` を `test_s2_values_are_the_decided_ones` に置き換え。その136 は ~~2393~~。PLAN-034 で `test_power_sim.py` が 93 件に。その135 は ~~2361~~ で、PLAN-037 I6〜I9 で増。その134 は ~~2283~~(PLAN-037 I1〜I5 で +123)。その133 は ~~2160~~(PLAN-038 で `test_repo_hygiene.py` が 65 件になった)。その118 は ~~2102~~。その116 は ~~2041~~(`test_pilot_ft_cmp_configs.py` の 61 件が増えた)・その110 は ~~1991~~・その107 は ~~1958~~。`test_sharpness_fit.py` が 97 → 130 → 180。その104 は ~~1903~~・その100 は ~~1810~~)。**件数の履歴(~~40~~ → … → ~~1759~~ → ~~1810~~)は `logs/STATE-ARCHIVE.md`「その70」「その77」「その86」「その89」「その90」「その98」「その100」「その104」「その107」にある**(ADR-063 運用規約6) | `code/tests/` |
| **★段2 の診断(鋭さ)の経路がある**(2026-09-26 その104 = PLAN-032 I1〜I4。§8.1 R1〜R7 / ADR-107)。プール: `python -m code.data_gen.sweep_pool --config configs/exp_diag_pool.yaml --arm diag`(`eval.threshold_sweep.min_threshold` を宣言した腕だけ T < 1 の項目を作らず、除外を manifest・metrics.json・log.txt に残す。**R8・S は不変**)。run: `configs/exp_diag_{b,a,b_d,a_d}.yaml`(同じプールを 4 つの文面で解く)。判定表: `python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" --out-dir results/diag_sharpness`(R7 で止め、Δ₂・R3・R4(T1b と T3 に別々)・R5 を機械的に当て、R6 の記述の行を出す。**解釈はしない**)。**凍結 tag の前に GPU で回さない**。**★その107(ADR-108)**: R1 の前提・A の文面の置き換えも記録で照合して止まる / 区間は [−1, 1] で切り退化の印 / S1 に注記 / 例外は `SharpnessError`。**★その110(ADR-109)**: 4 本の run の `git_sha.txt` の sha の一致と `git_diff.patch` が無いか 0 バイトも照合して止まり、sha を判定表の先頭に出す / 組ごとの差の数と平均 = 点推定の検査。**★その116(ADR-110 決定1・3)**: `sharpness:` 欄のある run は追跡ファイルに差分があれば run dir を作る前・重みを読む前に止まる(`--dry-run` は掛けない)/ 判定表の 2 番目の鍵 `analysis`(解析側の commit と `git diff HEAD -- code/` が空か。表示だけ) | `code/data_gen/sweep_pool.py` / `code/artifacts.py` / `code/eval/run.py` / `code/analysis/sharpness_fit.py` / `test_diag_sharpness.py` / `test_sharpness_fit.py` / `plans/PLAN-032` §11 |

| **評価ハーネスの本実行が通る**(2026-08-27。順1)。`python -m code.eval.run --config <cfg> [--run-dir <dir>]` が項目を読み・生成し・4値分解を出して `runs/<id>/` に成果物を書く。桁数掃引は `python -m code.eval.sweep`。**生成関数は差し替え可能で GPU の無い環境でテストが通る** | `code/eval/run.py`、`code/eval/sweep.py`、`code/tests/test_run_real.py`、`test_sweep.py` |
| **★桁数掃引は 2 本の腕を測る**(2026-09-10。ADR-071)。腕1 = `R(M)` の一様抽出(13 水準 × 200 × 5 = 13,000。**記述**。`build_items` は無変更で sha256 を回帰テストが固定)/ 腕2 = `Q(M)`(`label_main_coverage` が `extrap_magnitude` を返す組。7 水準 × 200 × 5 = 7,000。**判定の材料**)。`metrics.json` は `by_radius`(腕1)/ `grid_shell`(定義 A。記述)/ `quadrant`(腕2)/ `roles`。**config の `shell_*` が ADR-071 からの導出と食い違えば、run ディレクトリを作る前に止まる。`shell_*` の無い config(`smoke.yaml` を含む)も止まる。****`M*` は出さない** | `code/eval/battery/magnitude_sweep.py`、`code/eval/sweep.py`、`test_magnitude_sweep.py`、`test_sweep.py` |
| **再採点の CLI が動く**(2026-09-11。PLAN-022 §5)。`python -m code.eval.rescore --source-run <run>` が回収済みの `predictions/` を現行の `numeric` パーサで読み直し、別の run(`<timestamp>_rescore_<suffix>`)に `metrics.json`(`sweep.py` と同じ 3 ブロック + `checks` + `rescore`)と `transitions.json` を書く。**C1 / C2 / C4 が外れたら何も書かずに止まる。****掃引の run 専用**(本実行の run は読めない)。**Windows では `PYTHONIOENCODING=utf-8` が要る**(標準出力の cp932 が「—」を符号化できず、最後の `print` で落ちる) | `code/eval/rescore.py`、`test_rescore.py`(13件) |
| **本番 config の生成設定がすべて決まっている**(2026-09-10。ADR-072)。`eval.temperature` = 0(**記録用。デコードの正本は `do_sample: false`**)/ `eval.num_repeats` = 1。**本番 config で `load_generation_settings` が通る**(回帰テストが固定)。~~⚠️ ★F125~~ は閉じた(旧行は `logs/STATE-ARCHIVE.md`「その33」) | `configs/exp_phase1_main.yaml`、`code/tests/test_eval_model.py` |
| **本実行は「回せる」が「まだ回していない」。**★2026-08-28: `model.revision`(`0e9e39f…`)/ `model.max_new_tokens`(**256**)/ `eval.batch_size`(**4**)がすべて確定し、`configs/template.yaml` に入った。残る null は `model.name`(`meta-llama/Llama-3.1-8B-Instruct` を書くだけ)と実験同定・シード・LoRA グリッドの値。**評価はアダプタを読めるようになった**(8-6。ADR-043 決定3)—— `model.adapter` が指す `runs/<id>/adapter/` を載せ、**`metrics.json` の `seed` はその訓練 run から引く**。**null なら素の重みを測る**(その宣言であって未決ではない)。**病変条件が食い違うアダプタは受け付けない** | `code/eval/model.py` の `declared_adapter` / `attach_adapter`、`code/eval/run.py` の `adapter_provenance` |
| **訓練コードは回せる形になった**(★2026-08-28。8-6。ADR-043)。~~#22 の門~~ は外れ、**アダプタは `runs/<id>/adapter/` に残る**(重みのみ)。**Phase 1 の LoRA グリッドの値は未決**(ADR-043 決定10。null なら門で止まる)。**パイロットの値は ADR-100(rank 16・lr 1e-4・4 × 4・625)で、config に転記済み(その89。パイロット FT の 8 本にだけ。Phase 1 の値ではない)**。**`alpha = 2 × rank` は門が強制する**(決定4)。**★2026-09-24(その86。ADR-099 決定1・2・7)**: `seed` で random・numpy・torch・torch.cuda を種付け(`load_causal_lm` の後・`get_peft_model` の直前。`code/train/seeding.py`)し、`seeding` / `outcome.adapter_init_sha256` / `outcome.adapter_param_dtype` を残す。AdamW の betas・eps・weight_decay は `train.optimizer` の宣言を明示で渡す。`train.adapter_dtype`(float32 だけ実装)と実測が食い違えば訓練の前に止まる。**★2026-09-24(その90。PLAN-031 §3.6)**: `build_trainer` の「種付け → `get_peft_model` → 指紋 → dtype の読み取り」を `insert_seeded_adapter` に切り出し(挙動不変)、確かめの CLI `python -m code.train.seed_check`(訓練しない。シードごとに重みを読み直す)を作った。**本物の peft での確かめはその92 にポッド上で通った**(peft 0.20.0。[run:pilot_ft_seed_check_a] [run:pilot_ft_seed_check_b]。「★E は直った」とは書かない) | `code/train/lora.py` の `build_trainer` / `insert_seeded_adapter` / `check_adapter_dtype`、`code/train/seeding.py`、`code/train/seed_check.py`、`code/train/settings.py` |
| **集約が通る。**`python -m code.analysis.aggregate --runs "<glob>"` が `runs/*/metrics.json` を条件×シードで並べる。**adapter=null / seed 未記録 / 5シード未満を必ず文にして出す**(★2026-08-28: 評価 run の `seed` 欄が埋まるようになったので、条件×シードの表が組める) | `code/analysis/aggregate.py`、`code/tests/test_aggregate.py` |
| **`runs/<id>/metrics.json` に壁時計時間が残る**(★2026-08-28。ADR-040 決定6)。`timing` に 合計 / **重みの読み込み** / **生成** / 1項目あたり秒。区間は単調時計で測る(壁時計の差は NTP の補正で負になりうる)。**`eval.batch_size` の値はこの記録から決める** | `code/artifacts.py` の `timing_record` / `timing_line`、`code/eval/run.py`、`code/eval/sweep.py` |
| `infra/preflight.py` が実行でき、`infra/RUNPOD.md` §3 の全項目を報告する | ローカルで実行確認済 |
| `code` パッケージ名は標準ライブラリと衝突する。shim で共存させている | ADR-013。壊れると **pytest 自体が起動しない** |
| **PLAN-001 の仕様が確定**。外挿域は実測定義(§4.1.1)、内挿ホールドアウトは `K` の補集合(§4.2)、パイロット専用プールを分離(§4.6) | 2026-08-22(commit 8d7d4a2)。`plans/PLAN-001-eval-battery.md` |
| **`rule_rate` は固定参照規則に対して定義する**(主要評価項目では `p2`)。`metrics.json` は参照規則ごとに独立した4値ブロックを持ち、**各ブロック内で合計 1.0** | **ADR-016**(`logs/DECISIONS.md`) |
| セッションの引き継ぎが手順化された。skill `handoff` と hook `infra/context_guard.py` | ADR-015。**hook の発火は未検証**(次プロンプトでしか分からない) |
| **出力パーサ5モジュールが動く**(`numeric` / `wordform`(凍結)/ `boolean` / `cot` / 共通の `base`)。各モジュールに負例テストがある。~~`japanese`~~ は 2026-08-25 に削除(D-3 英語統一) | commit 28fafe5 → 7aaa9fe。`code/tests/test_parsers_*.py`。抽出規則は PLAN-001 **§5.4.1**(★人間の確認待ち) |
| **項目プールの対水準の機構が動く**(値域 / 除外 / 繰り上がり層 / 被覆ラベルの実行時付与 / pilot-main 分割 / ハッシュ) | commit 00fe528。`code/data_gen/pool.py`、`test_pool.py`(27件) |
| **プール生成器が ADR-020 / 021 / 022 に追随した**(2026-08-24)。`Lesion.is_defined` による定義域ガード / 被覆ラベル4値 + 答え域ラベル / `label_t_coverage` / `DigitOffsetLesion`(`p2d`)と `is_indistinguishable` | `logs/CHANGELOG.md` 2026-08-24。`code/lesion.py`、`code/data_gen/pool.py`、`code/eval/run.py` |
| **ラベルの本番スケール件数が ADR-020 / 021 の表と一致する**(組合せ論的事実。実験結果ではない)。`id+interp` 9,801 / `oob·ans_in` 9,702 / `oob·ans_out` 20,098 / `extrap_pair` 39,400 / `extrap_magnitude` 80,200、**`arb` 定義域外 100,298** | 2026-08-24 に実装で検算。`M*` 非依存分は `test_pool.py` が固定 |
| **`ident`(および `offset=0`)を除外集合・参照規則に指定すると例外で止まる。名前でなく振る舞いで検出する** | ADR-016 の未検証・リスク①への対応。`DegenerateReferenceRuleError` |
| **除外に使った参照規則の集合を manifest に記録し、`eval.reference_rule` がそこに含まれることを検査する** | ADR-016 の未検証・リスク②への対応。`scoring.validate_reference_rule` |
| **4値分解は参照規則ごとの独立ブロックで、合計 1.0 は各ブロック内で成立する。合計が合わない分解は構築時に例外** | ADR-016。`code/eval/scoring.py`、`test_scoring.py` |
| **G6(主要評価項目)の項目構成が動く。**§5.1 が認めた (極性, 閾値オフセット, `t` の下限) では **p2 / x2 / arb すべてで真値と規則値の答えが割れる** | ✅ **コードで検証済**。`test_battery_g6.py`。arb が割れるのは §4.4 の制約2に依存する |
| **`python -m code.eval.run --config configs/smoke.yaml --dry-run` が通る。**モデルは読まない | commit a30835f。README のクイックスタートのコマンド |
| **T1 / T2 の項目生成が動く**(`code/eval/battery/numeric_sum.py`)。被演算子 1 の除外(ADR-032 決定4。**2026-09-11 から ±1。ADR-075**)/ 場面テンプレートの内容依存の割当 / 判別可能性の生成時強制 | 2026-08-26。`test_numeric_sum.py`(24件) |
| **特異性対照の項目生成が動く**(`code/eval/battery/specificity_control.py`)。参照規則は `a−b+offset` / `a×b+offset`。**加算の参照規則を渡すと止まる** | 2026-08-26。`test_specificity_control.py`(14件)。PLAN-003 §4.6 |
| **訓練と評価アンカーが同じ書式ブロックを共有する**(`code/data_gen/prompt_format.py`)。~~manifest を書き出す入口がまだ無く検査6 は FAIL~~ → **2026-08-26 に `eval_pool.py` が書き出すようになり検査6 は PASS** | 2026-08-26。`test_prompt_format.py`(9件)。PLAN-002 §4.8.1 検査6 |
| **評価プールを書き出す入口が動く**(`code/data_gen/eval_pool.py`)。`items.jsonl` + `manifest.json` を書き、**preflight の `data_checks` 6項目がすべて PASS**(検査6・8 を含む) | 2026-08-26。`test_eval_pool.py`(18件)。ADR-033 |
| **★主プールは `fill_cells` で埋まる**(2026-09-11 その43。ADR-076 決定10)。本番 config は `eval.pool_items` を持たず、候補 = main 領域(`split_pilot_main` を再現して `counterpart_region_hash` と照合)+ `Q(999)` の main 側(組ごとのハッシュで 50:50)。セルごとの乱数列。**本番・b1・t2cross の `run.py --dry-run` が通り、data_checks は PASS。**明示リストの経路は smoke 系にだけ残る。**採点バッチは答え域で割る**(ADR-077。ans_out は `<群>.ans_out`)。`metrics.json` に `pool`・`coverage`(E-5 (b)) | `code/data_gen/eval_pool.py` / `pool.py` / `code/eval/run.py` / `code/analysis/gonogo.py` / `plans/PLAN-023` §6 |
| **★パイロット用プールがある**(2026-09-12 その54。PLAN-026 I1・I2)。`configs/exp_order6b_pilot.yaml` → `data/generated/battery/pilot/`(1,640 項目・1,560 組。主プールと同じセル表・件数)+ pilot の FT manifest 5 条件(`data/generated/ft/exp_order6b_pilot_<c>/`)。**preflight の data_checks は 7 件になった** —— `pool disjoint` = 評価プールどうしの順序対の積が空(相手は `eval.counterpart_manifest`。宣言なし = SKIP・掃引も SKIP)。pilot・本番・t2cross の config ですべて PASS。**`counterpart_hash` は両方 None のまま**(PLAN-001 §4.6 規則3 の 1 点目は未充足)。**items.jsonl / train.jsonl は git に無い**(ポッドでは config 冒頭のコマンドで作り直す) | `code/data_gen/pool.py` の `pool_manifest_problems` / `infra/preflight.py` / `test_order6b_pilot.py` / `plans/PLAN-026` §4.3 |
| **★閾値掃引(R8・S)の項目プールと記録の経路がある**(2026-09-12 その55 = PLAN-026 I3。ADR-080 決定3 / **2026-09-14 その57 = I4**)。`python -m code.data_gen.sweep_pool --config configs/exp_order6b_pilot.yaml --arm r8|s` → `data/generated/battery/pilot_sweep_r8/`(8,160 項目 = T3 4,080 + T1b 4,080・240 組)/ `pilot_sweep_s/`(2,400 項目。組は R8 と同じ・項目は R8 の部分集合)。θ の水準は pilot の config の `eval.threshold_sweep` にだけある(本番 config には無い)。組は gt・lt を併合したセル(80 組)から `sha256(["threshold_sweep", pool_seed, a, b])` の小さい順に 20。**掃引の項目は 4 値分解に入れない**(R8 の 7,200 項目は `p2` で判別できない)。**記録の経路(I4)**: `python -m code.eval.run --config configs/exp_order6b_r8.yaml [--dry-run]`(pilot の写し。差は 4 欄。**`eval.threshold_sweep_arm` の宣言で `main` が掃引の経路に回す**。manifest の中身から推測しない)→ `predictions/threshold_sweep.<タスク型>.jsonl`(項目ごとの `yes_logp` / `no_logp`・`t`・`threshold_offset`・`truth`・`answer`・併合セル)+ `metrics.json`(`kind: threshold_sweep`。**率なし**。`aggregate.py` は飛ばし `frame.py` は止まる)。**宣言と anchor のプールの種類・manifest と config・項目の欠けの食い違いは、両方の経路で重みを読む前・run ディレクトリを作る前に止まる**。R8 の config で preflight の data_checks は 7 件 PASS。S の config は未作成(I6・I8)。上位 k の欄は無い(I10)。R8 の 240 項目はパイロット用プールの固定オフセットの項目と同じ `item_id`(ADR-030 決定5)。items.jsonl は git に無い | `code/data_gen/sweep_pool.py` / `code/eval/run.py` / `test_sweep_pool.py` / `test_threshold_sweep_run.py` / `plans/PLAN-026` §4.4・§4.5 |
| **★R8 の当てはめがある**(2026-09-14 その58 = PLAN-026 I5。ADR-081)。`python -m code.analysis.r8_fit --runs <glob> [--ident-run <run>] [--out-dir <dir>]` が掃引の run(`kind: threshold_sweep`)を読み、(タスク型 × 既知性)セルごとに揃え方 (a) の交差点(混ぜた / gt / lt。階段は `(L + U) / 2`)・極性の開き・分類ごとの除外件数・遠いオフセットの correct(θ ≤ −2 / θ ≥ +3。境界は run の config の `eval.threshold_sweep.offsets.s` から導く。**セルごとが §5 (iv) の判定の単位**)を出す。**合否は付けない(I11)**。`Δ̂` は `--ident-run` のときだけ(基準の `lesion_condition` が ident でなければ止める)。**記録が metrics.json と食い違えば止まる**。**`lesion_condition` は adapter = null の run でも config の値(pilot・R8 では p2)**なので表に adapter を並べる | `code/analysis/r8_fit.py` / `test_r8_fit.py`(38)/ `plans/PLAN-026` §3.2.1.1・§4.6 |
| **★① の前置きの経路がある**(2026-09-15 その59 = PLAN-026 I6・I7。ADR-079 決定3)。config の `eval.preamble`(行のリスト。無い / null = なし)を `run.render_prompts` が全群の文面の先頭に置く(並べた行 + 空行 + 各群の文面。並びは `sha256(canonical_json(["preamble_order", item_id])) mod 24` の辞書順)。固定オフセットの 2 か所(`dry_run`・`evaluate_pool`)と掃引の経路が同じ関数を通る。**前置きの無い run の文面は 1 バイトも変わらない**(パイロット用プール 1,640・R8 8,160・S 2,400 の文面の sha256 をテストが固定)。`metrics.json`(両経路)・dry-run の報告に `preamble` 欄(無ければ null)、`log.txt` に 1 行。**preflight の検査6 は前置きのある run でアンカーと比べず SKIP**(訓練側の書式は検査し、破れていれば FAIL)。桁数掃引は前置きを宣言した config を拒む。config は S-① だけ(`configs/exp_order6b_s_preamble.yaml`。R8 の config との差 4 欄。2,400 項目の `--dry-run` が通り、data_checks は 6 PASS + 検査6 SKIP)。**固定オフセットの ① の config は無い**(3 群への絞り方は I8)。`aggregate.py`・`frame.py` は前置きの有無を見ない(I11) | `code/eval/preamble.py` / `code/eval/run.py` / `infra/preflight.py` / `test_preamble.py`(40)/ `plans/PLAN-026` §4.7 |
| **★プールの一部だけを解く宣言がある**(2026-09-16 その60 = PLAN-026 I8。ADR-082)。config の `eval.task_subset`(解くタスク型のリスト。ADR-026 の水準名 + `t1_instructed`。無い / null = プール全体)を `run.solved_pool_items` が `eval.batteries` の門と一緒に掛ける —— **宣言だけが「プールに batteries の外の群がある」門を開けられる**。噛み合わない宣言(型の群が batteries に無い / batteries の群に型が無い / 型の項目がプールに無い / 特異性対照を batteries に置く)は**重みを読む前・run ディレクトリを作る前**に止まる。外した (群 × タスク型) と件数は `metrics.json` の `task_subset` 欄(無ければ null)と `log.txt` に残り、`pool.n_items` は解いた件数・`pool.items_sha256` はプールのファイル全体のまま。**掃引は完全性((併合セル × 極性 × θ))をプール全体で確かめてから絞り**、`threshold_sweep.task_types` は解いた側になる(`r8_fit` が手を入れずに読める)。桁数掃引と `eval.dry_run_items` は宣言を拒む。(d) の文面は `configs/templates/order6b_d.yaml`(**T3 を入れない**。本番の `t1b.yaml` + `t3.yaml` の末尾の一文)。config 3 本の `--dry-run` = ① 1,440 / (d) 480 / S-(d) 1,200、data_checks は ① 6 PASS + 検査6 SKIP・他 7 PASS。**宣言の無い run(B0・R8・S-①)の項目と文面は 1 バイトも変わらない** | `code/eval/task_subset.py` / `code/eval/run.py` / `configs/exp_order6b_{preamble,d,s_d}.yaml` / `test_task_subset.py`(40)/ `plans/PLAN-026` §4.8 |
| **★(c) の較正の経路(`code.eval.calibration_run`。ADR-083)と最初の出力位置の上位 k の記録(`eval.forced_choice_top_k`。ADR-084)がある**(2026-09-16 その61・その62)。**2 行の全文は `logs/STATE-ARCHIVE.md`「その156」へ移した**(ADR-063 運用規約5。60 KB 超のため。1 文字も削っていない) | `code/eval/calibration_run.py` / `code/eval/forced_choice.py` / `plans/PLAN-026` §4.9・§4.10 |
| **★Go/No-Go の表が順6b の run を読める**(2026-09-16 その63 = PLAN-026 I11a。ADR-085)。`python -m code.analysis.gonogo --runs <glob>` は**表を run ごとに**出し、`metrics.json` の `task_subset` を宣言した run(① / (d))では**解いたタスク型のセルだけ**を組む(宣言の外の主軸の行・宣言の型の空のセルで止める)。各 run に腕を見分ける欄 `provenance`(`experiment_id`・`pool_id`・`adapter`・`template_set`・`preamble_sha256`・`task_subset`)。#3 のセルに**極性別の参照線**(極性別の Yes の件数と `gt_no_lt_yes`・`gt_yes_lt_no` の理論値。**#3 の印は変えない**)。config に `gonogo.near_tie_margin` がある run(**順6b の config 7 本だけ。0.25**)では**近接同点の感度の行**(`|yes_logp − no_logp| ≤ 幅` の件数と除いた #2。行に欄が無ければ止める。合否に使わない)。**`aggregate.py` はまだ前置き・絞りを見ない(① と (d) の run を B0 と同じ行に並べうる。I11c)**。(c) の補正の適用(I11b)と §5 の判定表(I11c)は無い | `code/analysis/gonogo.py` / `test_gonogo.py`(48)/ `plans/PLAN-026` §4.11 |
| **★(c) の補正を順6b の記録に引ける**(2026-09-22 その64 = PLAN-026 I11b。ADR-086)。`code/analysis/calibrated.py` が較正の run(`kind: calibration`)を読み、**腕を引数で**受けて `data.eval_template_set` と前置きの sha256 を照合し(食い違えば止める)、項目ごとに(腕 × category × 並び)の偏り `b` を引く(前置きの腕は `preamble.order_index` 番目の並び)。固定オフセットは `parsed` を差し替えて `classification` を `scoring.classify` で付け直し、掃引は `answer` を差し替える。**`yes_logp` / `no_logp` と数値群の行は 1 バイトも変わらず**、`bias` と `gap_after` が足される。補正後の表は `gonogo` と `r8_fit` の `calibrated_run_report`(**#1 は出さない**)。**C3 の近接同点は補正後の差**(決定2)、掃引の感度の行は**セル × 遠いオフセットの側**(決定3)。**①+(c)・(d)+(c) は §5 の候補ではない**(注記を固定)。**§5 の判定表と `aggregate.py` の守り(I11c)は無い** | `code/analysis/calibrated.py` / `gonogo.py` / `r8_fit.py` / `test_calibrated.py`(39)/ `plans/PLAN-026` §4.12 |
| **ruff / black はこの環境に未インストール。**整形は手作業(行長 100 以下は機械的に確認済) | ポッドを立てた時点で `pip install -e .[dev]` して掛け直す |
| **設計の主軸を機構線に寄せた。**モデル変種は原典転記、主要指標は強制選択+自由生成の併走、**G7(周期的概念への転移)を副次の最上位に追加** | **ADR-018**(2026-08-22、人間が全部承認) |
| **訓練プロンプトは裸の式 `a+b=` 一形式。訓練域は `[1,99]^2`。被覆ラベルは4値。`K >= 560`。外挿は2分割** | **ADR-019**(同上) |

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

**★2026-09-06(その5)に新しく開いた未知(実測に基づく。人間待ち)**

| # | 未知 | 状態 |
|---|---|---|
| **解析門の閾値** | ADR-054 決定1 (ii) の run 単位の解析門を何点で切るか | **人間待ち**。N5 と同じ場で凍結する |

---


## 現在のブロッカー

> **★2026-09-08 に、解決済みの項目と打ち消し線を落として組み直した。**
> **分割前の全文(何が古かったかの記録)は `logs/STATE-ARCHIVE.md` §5 にある。**
> **人間の判断そのものは `logs/OPEN-ITEMS.md` が正本である。**ここには「作業が止まっている場所」だけを書く。

**★クリティカルパスは 1 本になった**(2026-09-11 その40。1 本目で残っていた PLAN-022 が済んだ)。

1. **★`θ = 0.70` の根拠(値ではない)は依然として未記入である**(ADR-041 決定2 の要求。人間が自分で書く)。1 本目の残り(`θ` → 殻 → ★F125 → 順5 → `M*`)はADR-070〜074 と PLAN-022 で決着済(経緯は `logs/STATE-ARCHIVE.md`「その33」「その34」「その40」「その64」)


2. **★2026-09-22(その70): 順6b は完走・回収・コミットが済んだ**(`CHAIN_DONE`。commit `664ea2f`。ポッドは停止)。**次は人間が二値群 6 セルを決めることである** ——
   **ここまでの段の並び(I1〜I12 → §5 の凍結 tag → GPU 承認 → 順6b の実行・回収)は`logs/STATE-ARCHIVE.md`「その70」へ移した**(ADR-063 運用規約6。**全部が履歴になったため**)。

**そのほかに開いているもの:**

- **検出力分析は PLAN-034(ADR-114)で主要検定 T1 × T2 の模型が決まり、実装待ちである。**~~本実行を止める入力は `dgp.s2_item` / `dgp.s2_tmpl` と ★F114 の実行先~~ → ~~★その139: どちらも決着(ADR-119・ADR-121)。残りは本実行の起動(AC 電源・人間の確認)~~ → **★その141: 本実行は止めた。PLAN-040(ADR-122)で軸・順・報告量を決め直した。残りは §11 の値と実装**。`n_item` は 80 の整数 1 つ(ADR-114 決定3)。**前の版は `logs/STATE-ARCHIVE.md`「その129」**
- **設計文書 8 本は ADR-115・116 の主題・仮説に揃った(ADR-117。その132)。**`09_PAPER_PLAN.md` 論文 1 の新しい下書きと `00_OVERVIEW.md` §7 は**下書きのまま**(タイトル・claim の確定は人間。`CLAUDE.md` §8)。旧い 2 つの箇条は `logs/STATE-ARCHIVE.md`「その132」
- **PLAN-001 §5.1.1 の穴 2 と穴 3**: 「単位元の言明」「規則の自己説明」は `(a, b)` を持たず
  被覆ラベルが定義できない / **本番の評価テンプレート集合(`data.eval_template_set`)が未確定**
  (**実験条件である**。残るのは G1「記法形」変種の扱いと本番テンプレートの文面そのもの)
- **実験パラメータが `configs/template.yaml` で `null` のまま**(~~★パイロットの値は ADR-099 決定3 = 原典つきの案の後に人間~~ **→ ★パイロットの値は ADR-100 で決着**(rank 16・lr 1e-4・4 × 4・625)。**config への転記は済んだ(その89。パイロット FT の 8 本にだけ。`template.yaml`・本番 config は null のまま)。Phase 1 の値は凍結前に改めて決める**): 学習率 / ステップ数 / batch size / **→ ★2026-10-01(その130。ADR-115 決定10): Phase 1 の本実験はパイロットの 1 点(rank 16・lr 1e-4・4 × 4)に固定。残りは step 数だけ(凍結前)**
  **LoRA rank と alpha**。設計文書に値が無いのでエージェント側で既定値を作っていない
- ~~**`infra/requirements.lock` が空である**~~ → **2026-09-10 に順1b の pip freeze の転記で埋めた**(ADR-073 決定4。187 行)。
  **ポッド上で lock から入ることはまだ確かめていない**(bootstrap.sh の pytest と PLAN-014 §5 手順 2b の突き合わせで分かる)
- **`infra/Dockerfile` のベースイメージタグが未確定**(`UNPINNED-未確認`)。
  実在を確認していないタグは書かない(`CLAUDE.md` §2)
- **RunPod のインスタンスタイプとコスト見積もりが未確定** / **解析側の凍結手段が未決**
  (ADR-058 決定2。`renv.lock` を repo に置くか)

---

## 人間の承認・判断を待っている事項(`CLAUDE.md` §8)

> **★2026-09-08 に全文を `logs/OPEN-ITEMS.md` へ移した(ADR-063)。ここは索引である。**
> **1 行も勝手に消さない。**決まったら ADR を書き、打ち消し線を付けてから索引の行を落とす。

**★★2026-09-09(その27)に、人間が 4 束すべてを決めた(ADR-069)。上げ直さないこと。**
**★F112 / ★F113 / ★F114 の並列化 / 実装判断 4 件は、決定も実装も終わっている。**
**★F104 は取得元(F104-0 / a / b)だけが決着している(ADR-094)。値(F104-c)は ADR-095 決定3 で差し戻した。**
**`n_item` はタスク型ごとの値が決まり(ADR-095 決定2)、実装待ちである。★F114 の実行先はその後。**

**★★2026-09-08 に人間が採択し、実装まで終えた 3 本。上げ直さないこと。**
**ADR-064**(★G 〜 ★L + ★F81 の 7 件)/ **ADR-065**(★J の閾値 / ★G の縮退順序)/
**ADR-066**(F94・F95 + 文言訂正 4 件)。**正本は `logs/DECISIONS.md`。**
**要約は `logs/STATE-ARCHIVE.md` §11 と `plans/PLAN-019` §0.0 にある。**

**★いま人間の決定を待っているもの**:

| 記号 | 決めること | 期限 |
|---|---|---|
| **★L(d)** | `arb` を 5 → 10 シードにするか(**+5 run**) | 順6 の後。GPU 構成と同じ場 |
| **★F114 の実行先** ★新 | ~~どこで回すか~~ → **★2026-10-03(その138)決着: この機械(ADR-119 決定1)**。経緯は `logs/OPEN-ITEMS.md` の行 | 本実行の前 |
| ~~**★F104-c の値**~~ **決着** | ~~`s2_item` の値~~ → **★2026-10-03(その139)ADR-121: `s2_item` = 2.0(推定を見た後に人間)/ `s2_tmpl` = 0.5。config に反映** | 次に索引を組み直すときに落とす |
| ~~**★PLAN-040 の値**~~ **決着**(その142) | ~~`n_item` の格子・`sigma` の確認点・各段の `n_rep`・誤指定で「膨らむ」の閾値~~ → **ADR-123(5 問とも推奨)。値は PLAN-040 §11** | 次に索引を組み直すときに落とす |
| **★検出力分析の本実行: 誤指定の門が閉じた** ★新(その147) | 1 日目(2026-10-04 夜)で 1 段目の誤指定の門だけが走り、`tau` 0.25 → 14/100・0.5 → 15/100 で門が閉じた[run:20261004_120002_power_sim_t1t2]。**回し直さない**。§3.2 の見直しの別 PLAN の扱い・夜用タスクの扱いは人間。**→ ★その150: §3.2 の見直しは ADR-124(PLAN-041 採択)。残り = 実装 I1〜I8・新しい run の起動・夜用タスクの扱い**。**全文は `logs/OPEN-ITEMS.md`** | PLAN-040 付録 A.4 / ADR-123 | 本実行の後 |
| **★run2 の門と当てはめ失敗(PLAN-042)** ★新(その153) | run2 の 1 段目で門は閉じるが、棄却のほとんどは当てはめ失敗を棄却に数えた分。~~PLAN-042(診断)の採否・§2 の閾値・今夜のタスク・P1 を回すか~~ → **★その154 ADR-126 で決着(採る・門で数え直す・今夜 1 回・P1 は後)。残り = 夜用タスクの無効化・診断の実行の日時・診断の後に規則を変えるか** **→ ★その156 ADR-127: §2.1 を診断の前に改めた(§2.2)・過誤の門と実行可能性の門を分ける(方針)。(5) の中身は上限の値・D2' の書き換え・ADR-125 決定3 との整合・新しい反復**。**→ ★その161 ADR-128 で (5) 決着(A2 + A3・B1 + B2・実行可能性の門 0.10・TOST も主張しない・run3)。残り = 実装の PLAN(PLAN-043)** **→ ★その162 PLAN-043 草案(人間のレビュー待ち。§4 の Q1〜Q6)**。**→ ★その163 ADR-129 で PLAN-043 を採択(7 問とも推奨。`rng_seed` 20261008)。残り = 実装 I1〜I10・run3 の起動**。全文は `logs/OPEN-ITEMS.md` の行 | 診断の後 |
| **★前段 FT の前の診断** ★新(その77) | 足し算を含まない比較を T1b・T3 の形式で確かめ、前段 FT に意味があるかを判断する(ADR-096 決定1)。**→ ★2026-09-26(その103)設計と判定の規則は ADR-107 で決まった(`plans/PLAN-032` §8.1)。残りは下の行** | PLAN-029 の実装より前 |
| **★`CLAUDE.md` を 200 行へ戻す** ★新(その127) | 216 行(§10.2 の上限 200 行)。§1 の「449行」も古い。全文は `logs/OPEN-ITEMS.md` の行 | ADR-113 決定2 | いつでも |
| **★R8(Phase 2)の push と G2-1 承認** ★新(その125) | ADR-111 決定3。人間の操作 2 つ: `01cf60f` 以降の main の push と新しい G2-1 承認。経緯の全文は `logs/OPEN-ITEMS.md` の行 | ADR-111 / ADR-107 決定7 | 人間の都合 |
| **★前段 FT の成功基準・侵襲の閾値** ★新(その77) | エージェントが案を下書きし、人間が値を決めて tag で凍結する(ADR-096 決定3) | 前段 FT の GPU の前 |
| **★モデル名の一致の機械的な検査** ★新(その87) | CHANGELOG の `[actor: 役割 (モデル名)]` と commit trailer の一致を hook か `test_repo_hygiene.py` で検査するか(案のみ。ADR-101 の保留。**ADR-101 の再確認そのものは ADR-102 で決着**) | いつでも |
| **★S3 の根拠の見直し** ★新(その83) | ADR-099 決定2(α)で S3(ADR-055 決定2)の根拠 F15 が消える。案 b を保って根拠を書き直す / 案 a / 案 c(`plans/PLAN-031` §5)。エージェントの案: S5 と同じ場 | 凍結前 |
| **★T2 の形の変化と #5 の扱い(Phase 1 の凍結前の設計の問い)** ★新(その101) | FT の後(`ident` を含む)に T2 の応答が数だけの形になり(素のモデルは 240/240 が文章。`results/pilot_ft_t2_form/`)、#5 は 625・313 とも全条件で割れた。候補 = 途中のチェックポイントの掃引 / `learning_rate` / 訓練の書式(ADR-019 に触る)/ #5 の基準を先に向けて見直す(HARKing の危険)。**印の意味づけ・`p2d` の扱い(ADR-103 決定7)もここ**(ADR-106 決定4)。~~★313 の印の意味づけと次の手~~ は ADR-106 で決着(段1 を閉じた)。エージェントは決めない **→ ★その130(ADR-115 決定7): 素のモデルに「数だけ」の一文を足した診断を先に回し、結果の後に T2 の文面と step 数を人間が決める** | 正本は `logs/OPEN-ITEMS.md` | Phase 1 の凍結前(段4 が前段 FT なら病変 FT のやり直しの設計と同じ場) |
| **★E1(転移)の TOST 境界・多重性** ★新(その79) | ADR-097 決定3(P-3)。門の外に確証的な評価項目を足すときの α の配分と「転移しない」の境界 | 凍結前 |
| **★PLAN-034 の値と外に置いたもの** ★新(その129) | 平行性の TOST の Δ(D5)/「規則を適用したシード」の分類の規則と閾値(D7)/ E1 の検出力(D8)/ 天井のセルでの当てはめ(D9)。全文は `logs/OPEN-ITEMS.md` の 4 行 | 凍結前 |
| **★ADR-115 の凍結前の値** ★新(その130) | T1c の仕様と統計(α の配分を含む)/ LoRA のスケールの掃引の水準 s / Phase 1 の step 数(「数だけ」診断の後)。全文は `logs/OPEN-ITEMS.md` の 3 行 **→ ★その133(ADR-118): T1c の実装の形は決着。件数は主・pilot とも S5。S4 の T1c はその後** | 凍結前(PLAN-035 §5 の S5) |
| **★MisFT の原典確認と被引用の追跡** ★新(その130) | 多項の合成を測っているかを含む。確かめるまで「初めて」と書かない(ADR-115 リスク)。SCOUT 済(`logs/SCOUT-2026-10-01-misft.md`。未検証)。**→ ★その132: 文書には ❓ で入れた(ADR-117)。残りは人間の原典確認と Table A4** | 人間(いつでも) |
| **★2 系統目のモデルの選定** ★新(その130) | ADR-115 決定8(本実験の後・別 tag・`p2`・`ident`・`p2d` × 5)/ rank・標的・`train_size` を後で探索に回すか(決定10) | 本実験の後 |
| **PLAN-018 §4.3** | 「現在のブロッカー」の組み直しと Phase 0 の要約(**とくに F87**) | いつでも |
| **順6b の後に決める 2 件** ★新(その53)**★その55 更新: G14 は ADR-080 決定1 で決着** | PLAN-026 の G12(batch を替えるか)/ G15(① を採る場合の T1 のアンカー)。ADR-079 決定8・9 | 順6b の後・主プールで測り直す前 |

**★「順6 の実測を待つ」で先送りできる項目は 1 つも無い**(PLAN-019 §0 の F90 〜 F93。
**F90 は 2026-09-08 その22 に事実確認済**)。**経緯は `logs/STATE-ARCHIVE.md` §11。**

**それ以外の人間待ち**(`logs/OPEN-ITEMS.md` の索引が正本):
~~**`θ`**~~(**ADR-070 で決着**)→ ~~**★殻の定義** / **★殻あたりの項目数と抽出経路**~~(**ADR-071 で決着。2026-09-10 実装済**)/ ~~**★★F125**~~ / ~~**★ADR-071 の実装判断 3 件**~~(**ADR-072 で決着**) / **★`θ` の根拠** / ~~**順6**~~(ADR-076 決定11)と **本実験 40 run の GPU 構成** / ~~**E-5 の案 (b)**~~(ADR-076 決定12)/
~~**Δ 5 行**~~(★F113 = ADR-069 決定2 で出所が決着。**値そのものは順6 の後**)/ **★2** / **N5(解析門の閾値)** / **★C** / **★E**(`torch.manual_seed` が 0 件)/
**効果量プロファイル P の凍結(D5)** / **LoRA グリッド** / ~~**`M*`**~~(ADR-074)/ ~~**凍結の段の前後**~~(ADR-098 決定4)/
**`00_OVERVIEW.md:7`**(段3。ADR-098 決定2)/ **`09_PAPER_PLAN.md` の追随** / **`refs.bib` の Nikankin 書誌の最終確認**。

---

## Phase 0 に必要な段階

> **★2026-09-08 に要約に落とした。分割前の全文は `logs/STATE-ARCHIVE.md` §6。**
> **順序・依存・完了状態の正本は `plans/PLAN-004-phase0-route.md` §2 である**
> (この表自身が 2026-08-27 にそう書いている)。**タスクの正本は
> `Documents/04_EXPERIMENT_PLAN.md` Phase 0。**

| 段階 | 中身 | 状態 |
|---|---|---|
| **A** | GPU 不要のコード作業 | **✅ 完了(2026-08-26)** |
| **B** | 人間の決定(凍結の前に全部要る) | **進行中。残りは `logs/OPEN-ITEMS.md`** |
| **C** | GPU 小(`none` モデルのみ。FT は 1 本も回さない)= 順5 の桁数掃引 / Go-No-Go #0 〜 #3 | ~~**`θ` 待ち + GPU 承認待ち**~~ → ~~★F125 待ち~~ → **順5: 完走(run `20260910_104249_sweep_m`。その36)・結果は報告済(その37)。`M*` = 999(ADR-074)。PLAN-022 も済(再採点 run `20260910_215422_rescore_sweep_m`。その40)。**順6: 完走(その44。R1〜R5 回収・コミット済・ポッド停止)。Go/No-Go の判断: ADR-078(T1・T2 の 6 セルは確定、二値群 6 セルは順6b の後)** |
| **D** | 事前登録の凍結(`git tag`) | **順6b → 二値群 6 セルの判断 → Δ 5 行で止まっている** |
| **E** | パイロット(`p2` / `p2d` を 2 〜 3 シード)。Go-No-Go #4 / #4b / #5 | **段1 のパイロット FT(`p2` 2・`ident` 2・`p2d` 1。ADR-099)は 625・313 とも完走し、ADR-106 で閉じた。#4・#4b は通り、#5 は割れた(`pool_id: pilot`。主張に使わない)。#5 の扱いは Phase 1 の凍結前の設計の問い(`logs/OPEN-ITEMS.md`)** |

**★GPU を使わずにいま進められる実装は `code/analysis/primary.py` だけであり、
それも解析門の二値化(N5)と ★G の決着を待つほうが安い**(書き直しになる)。

---

## 次のアクション


> **★★2026-10-23(その181・最新)。FT までの道筋の正本は PLAN-035 §5。**
>
> 1. **★人間: probnull の生成の再開を決める**(L_50 が fits 0 で停止。`python -m code.analysis.power_sim --config configs/power_sim_ceiling_probnull.yaml --out-dir results/power_sim/ceiling_probnull --through-stage 1 --keep-frames --workers 16`)→ 評価 `python -m code.analysis.ceiling_remedy --config configs/ceiling_remedy.yaml --out-dir results/ceiling_remedy --workers 16` → ANALYST が PLAN-046 §6.1 と G1・G2 を記述 → 人間が C の採否(別の ADR)
> 2. **IMPLEMENTER: PLAN-045 I1〜I6**(ADR-134 で採択済み。1 と触るファイルは重ならない)→ 人間が順6 の測り直し(I7)の起動を決める
> 3. 人間: `01cf60f` 以降の main の push と G2-1 承認 → S4(RUNNER。PLAN-045 Q5 (a) なら順6 の測り直しを同じ pod で)→ T2 の文面・step 数の決定(ADR-130 決定2)
> 4. run3 は 1 の C の採否と 3 の後(PLAN-043 §12 の判断 6 件の確認もそのときに)
> 5. 人間(凍結前): REVIEW の R4 以下・C1/C2・R5(パイロット用プールを揃えるか)/ その166 の 5 の項目 / 確率の尺度の TOST の Δ(ADR-132 決定5)/ `id` の二重露出の感度解析の事前登録(PLAN-045 Q4)


---

## 引き継ぎ


> **★★2026-10-23(その181・最新)。Claude Opus 5.5(PLANNER)。PLAN-045 を起草し ADR-134 で採択(5 問とも推奨 (a))。次は IMPLEMENTER が I1〜I6。**
>
> **★やったこと**: 開始手順 → probnull の停止を確かめた(L_50 fits 0・プロセス無し)→ ADR-130・131・REVIEW R3/R5/§D.3・`pool.py`・`eval_pool.py` を読んだ → 読み取りだけのスクリプトで現行の割当を再現し、フィルタ後の供給を数えた(スクリプトはスクラッチ。数は I2 で manifest に記録して再現する)→ PLAN-045 草案
> **★やっていないこと**: probnull の再開(人間)・`code/`・config・データの変更・push・GPU


---

## このファイルの運用規約(★2026-09-08 新設。ADR-063)

**この分割は「積み上げをやめる」ことでしか維持できない。**3 週間で 417 KB まで育った原因は
**各節が過去のブロックを消さずに上へ積んだこと**である。以下を守る。

1. **各節は最新 1 ブロックのみ。**新しいブロックを書いたら、**古いブロックは
   `logs/STATE-ARCHIVE.md` の該当節の先頭へ移す**(捨てない)
2. **セッションの経緯は `logs/CHANGELOG.md` に書く。**`STATE.md` には書かない。
   **`STATE.md` は「いま何が本当か」だけを持つ**
3. **人間の判断待ちは `logs/OPEN-ITEMS.md` に書く。**`STATE.md` には索引の 1 行だけ
4. **決定の正本は `logs/DECISIONS.md`(ADR)である。**`STATE.md` に決定を書かない
5. **目標 400 行 / 60 KB、回帰テスト `test_repo_hygiene.py` が落ちるのは 700 行 / 90 KB**(ADR-063
   決定2 が同じ文で宣言した目標と閾値。**食い違いではない**)。**超えたらアーカイブへ移す。削らない**
6. **解決済みの項目は、打ち消し線を付けたうえでアーカイブへ移す。**
   `STATE.md` の中で打ち消し線が積もり始めたら、それは移す合図である

**★ skill `handoff` はこの規約に従って `STATE.md` を更新する**(`.claude/skills/handoff/SKILL.md` §2)。
