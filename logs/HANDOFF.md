# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-16(その60)/ 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN の 1 項目完了**(PLAN-026 の I8 を実装・コミットした `58b0c11`)

---

あなたは IMPLEMENTER です。`CLAUDE.md` §1 の開始手順を実行し、skill `code-style` を読んでから作業を始めてください。
**★開始手順とこの環境の既定の読み込みだけで約 13〜17 万トークン使う(その48〜その59 の実測)。**`STATE.md` の `cat` 以外は `grep -n` → `sed -n` で必要な範囲だけにする(`CLAUDE.md` §10.2)。

## このセッションでやること(1つだけ)

**`plans/PLAN-026-order6b.md` の I9 = (c) 内容のない入力による較正(CPU のみ。GPU 0)。**

1. **★実装の前に原典を確かめる**(ADR-079 決定7 / 記入欄 G11 の条件):
   - 記号の案 `N/A` / `[MASK]` / 空文字 は**エージェントの案であって文献からの転記ではない**(PLAN-026 §3.5)。
   - `plans/PLAN-025-papers/papers_list.md` の **[11] Zhao et al. (2021) "Calibrate Before Use"(arXiv:2102.09690)** を開き、
     **content-free input に実際に使われた綴りを転記する**(`CLAUDE.md` §3 の引用プロトコル)。
   - **食い違えば実装せず人間に上げる**(`AskUserQuestion`。`CLAUDE.md` §8。記号は実験条件である)。一致すれば PLAN-026 §3.5 に「原典で確認済(日付)」と書いてから実装する
2. **実装**(PLAN-026 §9 の I9): 小さな新規関数(`code/eval/forced_choice.py` の `scorer_from_model` / `collect_forced_choices` を流用)+ `calibration.json`。
   - 入力 = 各(タスク型 × 極性 × 文面)で `{a}` `{b}` `{threshold}` を記号に置き換えたもの。件数は **≤ 306**(いまの文面 12 + (d) 6 + ① 288。§3.5)
   - **真値が無いので `Item` / `classify` / 4 値分解を通さない**(`scoring.py` の `CoincidentItemError` の手前で止まる)。記録は `yes_logp` / `no_logp`(同じ 12 綴りの logsumexp)
   - **補正は後処理(GPU 0)**。判定 = `(yes_logp − no_logp) − (cf_yes − cf_no) > 0`、同点は No(ADR-047 実装ノートと同じ)
   - ① の 24 通りの並びは `code/eval/preamble.py` の `nth_order` で引ける(`item_id` に依らずに呼べる)。(d) の文面は `configs/templates/order6b_d.yaml`
   - **上位 k の欄は I10。判定表は I11。ここでは作らない**

**完了条件**: 原典の綴りの確認(または人間への質問)が済んでいる / 較正の入力と記録を作る経路が動き、件数が §3.5 と一致する / `calibration.json` の形が PLAN に書かれている / `pytest code/tests -q` が通る(直近の実測は **1224 passed**。その60。全体で約 3〜4 分)/ 本番の文面・`data/raw/`・プールを 1 バイトも変えていない

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **I8 は実装済み**(`58b0c11`)。**絞りの宣言 `eval.task_subset`(解くタスク型のリスト)= ADR-082**(提案 エージェント / 採択 人間。選択式)。
  `code/eval/task_subset.py` / `run.solved_pool_items`(群の門と絞りを 1 か所に)/ `metrics.json` の `task_subset` 欄(宣言が無ければ null)/ `log.txt` は 8 行 /
  掃引は**完全性をプール全体で確かめてから絞る**・`threshold_sweep.task_types` は解いた側(`r8_fit` が手を入れずに読める)。読みは PLAN-026 §4.8
- **config は 3 本増えた**: `configs/exp_order6b_preamble.yaml`(固定オフセットの ①。1,440)/ `exp_order6b_d.yaml`((d)。480)/ `exp_order6b_s_d.yaml`(S-(d)。1,200)。
  (d) の文面は `configs/templates/order6b_d.yaml`(**T3 を入れない**。本番の `t1b.yaml` + `t3.yaml` の末尾の一文)
- 前置きを宣言する config は `code/tests/test_preamble.py` の `PREAMBLE_CONFIGS`、絞りを宣言する config は `test_task_subset.py` の `SUBSET_CONFIGS` が固定している(**config を足したらここも足す**)
- **宣言の無い run(B0・R8・S-①)の項目と文面は 1 バイトも変わっていない**(sha256 をテストが固定)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-026-order6b.md` §3.5(155〜161 行付近)/ §4.8 / §9 の I9(`grep -n '^### 4.8\|^| I9' plans/PLAN-026-order6b.md`)
- `plans/PLAN-025-binary-methods.md` の 171 行付近と `plans/PLAN-025-papers/papers_list.md` の [11]
- `code/eval/forced_choice.py`(`grep -n 'def scorer_from_model\|def collect_forced_choices\|def choose_from_logprobs'`)/ `code/eval/preamble.py`(読むだけ)
- **依存**: 手元は numpy 2.4.6 / scipy 1.18.0、statsmodels は無い。ruff / black も無い(行長 100 以下は手で確認する)

## やってはいけないこと

- 本番の T1b・T3・T1・T2 のテンプレート・本番 config・`data/raw/`・プールを書き換える(ADR-078 決定2)
- **原典で確かめずに記号の綴りを決める**(ADR-079 決定7 の条件。実験条件である)
- 判定規則(`choose_from_logprobs`)・4 値分解・#2 = 0.70・#3 の値を変える / I10(上位 k)・I11(判定表)まで手を広げる / GPU / main の push
- Python の `Path.write_text` で `STATE.md` や config を書く(Windows で CRLF になる)。追記は Python で bytes を連結する。**長い日本語の Python を Bash の heredoc に流さない** —— Write ツールで scratchpad に書いてから実行する
- `awk` の `length` はバイト数(日本語は 3 倍に数える)。行長は Python の `len` で見る

## 未解決 / 人間の承認待ち

- **PLAN-026 §4.8(I8 の読み。とくに読み4 = `task_subset` 欄をすべての run に置くこと・読み5 = 掃引の `task_types` を解いた側にすること)/ §4.7(I6・I7)/ §4.6(I5)/ §4.5(I4)/ ADR-080 決定3 に異議があるか**(どれも `logs/OPEN-ITEMS.md` には行を立てていない。STATE「次のアクション」5)
- 順6b の GPU 承認(I9〜I12・dry-run・§5 の凍結の後。文面は PLAN-026 §11。**run 数は 6 → 7 に直してから諮る**)/ G12・G15 は順6b の後
- ★`θ` の根拠 / ★F104 / ★F114 の実行先 / 停止中ポッドの terminate / Phase 1 本実験 40 run の GPU 構成 / 引用の最終確定(E7)(正本は `logs/OPEN-ITEMS.md`)
