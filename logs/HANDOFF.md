# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-02 / 直前セッションの役割: IMPLEMENTER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-009 = 順4 の第2条件 + 人間が採択した P1/P3/P2)。

---

あなたは **PLANNER(または人間の決定を受ける IMPLEMENTER / RUNNER)** です。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(人間が1つ選ぶ)

**順4 の第2条件は閉じた。第3条件は「順5 で `M*` が出る」まで原理的に閉じられない。**
したがって次は下のどれかである。**GPU を使うのは 2 だけで、人間の承認が要る。**

1. **順7 の GPU 不要分**(GPU 時間 0)。`Documents/09_PAPER_PLAN.md` の追随 /
   `00_OVERVIEW.md` §1・§7 の点検 / `05_STATISTICS.md` §6(検出力分析)の再導出 /
   **`01_HYPOTHESES.md` の下書きの確定**。
   完了条件: 各文書に「主軸 = タスク型 × 既知性の交互作用」が反映され、
   `STATE.md`「現在のブロッカー」の未追随リストから該当行が消えること。
   **効果量プロファイルの指定と仮説の確定は人間の入力が要る**(`CLAUDE.md` §8)。
2. **順5(= `M*` の実測)。★人間の GPU 承認が要る。**
   その前に RUNNER が **N2**(comparison 群でバッチ1 対 バッチ N の `parsed` 一致確認)を取り、
   実機で `pip freeze` → **ADR-044**(`infra/requirements.lock` の凍結)を履行する。
   **preflight の `forced choice tokens` が WARN / FAIL を出したら人間に上げて止まる。**
3. **評価側 manifest に `schema_version` を足すか**を決める(ADR-051 の未解決)。小さい。

## 直前セッションで確定したこと(再実装しないこと)

commit **`bbb1a38`**(順4 第2条件)/ **`1376909`**(ADR-051)。`pytest code/tests -q` → **808 passed**。
GPU 時間 0。`results/` は空。正本は **`plans/PLAN-009-order4-production-config.md`** +
**`logs/DECISIONS.md` の ADR-050 / ADR-051** + `logs/CHANGELOG.md` 末尾。

- **人間が B1〜B3 とデータ生成シードを決定した**(ADR-050。提案 IMPLEMENTER / 採択 人間):
  `lesion.arbitrary_table` = **規約A で生成した 197 件** / `data.train_size = 10000` /
  `data.coverage_k = 2000` / `pool_split_seed = 0` / `coverage_seed = 1` / `sample_seed = 2` /
  `pool_id = main`。**ADR-049 (a) の命名3件も承認して閉じた。**
- **`configs/exp_phase1_main.yaml` が本番 config である。5条件は `--condition` で切り替える。**
  条件ごとに config を複製しない(写し間違いでバイト一致が壊れる)。
- **5条件の FT データを生成済み。**`matched_stream_sha256 = 3e9c769c953b` が5条件で一致し、
  `train_jsonl_sha256` は5条件とも異なる。`repeats_base = 5` / `repeats_extra = 0`。
  **`data/generated/` は manifest だけ追跡している。実体は上のコマンドで作り直せる。**
- **`arb` の強制一致は `t=7`(→9)と `t=97`(→99)の 2 件だけ**である
  (`PLAN-002` §7.3 の「1件だけ」は**誤りだった**。訂正済)。`p2d` / `x2` との一致は 0 件。
  **組合せ論的な計数であって実験結果ではない。**
- **`files` ブロックと改行の扱いは ADR-051 で確定した。**書き出し関数が
  **ディスクのバイト列を読み直して**記録する。`newline` 明示を外さないこと。

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-009-order4-production-config.md` §5 / §8.2(preflight の全検査の状態)
- `logs/DECISIONS.md` の **ADR-050 / ADR-051**(`grep -n '^## ADR-05' logs/DECISIONS.md` で位置を出す)
- `STATE.md` は 2,000 行超。**全文 `cat` しない。**`grep -n '^## '` で節を出し `sed -n 'X,Yp'`
- `configs/exp_phase1_main.yaml`(197 行の `arbitrary_table` を含む。**手で編集しない**)

## やってはいけないこと

- **`configs/exp_phase1_main.yaml` の `arbitrary_table` を手で編集する。**
  作り直すなら `python -m code.data_gen.arb_table --seed 0 --offset 2 --multiplier 2 --digit-modulus 10`
- **`eval.pool_items` / `eval.cells` を埋める**(B5。`M*` 未決。ADR-033 決定4。**順5 の後**)
- **`train.*` のハイパラに値を入れる**(ADR-043 決定10。パイロットで決める)
- 合否基準・しきい値・Go/No-Go 判定コード・`θ`・`M*` を書く / 提案して決める
- **凍結済みのプロンプト文面を変える**(ADR-046 / 048)。`configs/templates/` に差分を出さない
- **強制選択の器械を触る**(ADR-047 実装ノート。人間の最終確認待ち)
- `configs/smoke.yaml` を編集する(ADR-037 決定4)/ `data/raw/` を書き換える
- **書き出しの `newline="\n"` を外す**(ADR-051 決定4。外すと OS ごとに別のバイト列になる)
- 人間の承認なく GPU ジョブを起動する
- **`python - <<'PY'` の heredoc に `\\n` を書く。**この環境の Bash は `\\` を `\` に潰す。
  バックスラッシュを含む置換は scratchpad にスクリプトを書いてから実行する

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

- **`experiment.hypothesis` が null。**`Documents/01_HYPOTHESES.md` の追随は**下書きのみ**で、
  主軸 Q16 に対応する H 番号が確定していない。**論文の claim に直結するので人間が確定させる**
- **B5**: `eval.pool_items` の本番の中身。**`M*`(順5)待ち**
- **`θ` の値**(ADR-041。順5 の掃引表を見てから)/ **ADR-047 実装ノートの R3 / F1 / R4 / 検査5**
  (強制選択の器械仕様。実装済み。人間が読んで閉じる)
- **評価側 manifest に `schema_version` を足すか**(ADR-051 の未解決。訓練側だけが持つ非対称)
- **`train.*` のハイパラ**(ADR-043 決定10)/ `infra/requirements.lock`(ADR-044。次のポッドで)
- **未追随の文書**: `09_PAPER_PLAN.md` / `00_OVERVIEW.md` §1・§7 / `05_STATISTICS.md` §6 /
  `01_HYPOTHESES.md`(下書き段階)。**事前登録の凍結前に片付ける**
