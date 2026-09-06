# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-06 / 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-011 = D2/D3/D4 の決着 + ADR-053)**かつコンテキスト超過**
(hook `context-guard` が約 155k トークンで警告)。

---

あなたは **PLANNER(または人間の決定を受ける IMPLEMENTER / RUNNER)** です。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(人間が1つ選ぶ)

**D1〜D7 はすべて決着した。`experiment.hypothesis` の null は外れた。**残りは下の4つ。
**GPU を使うのは 2 だけで、人間の承認が要る。**

1. **D4 が再び開いた未決を閉じる**(GPU 時間 0。**人間の入力が本体**)。
   **★「`id` 到達度を揃える」の操作的定義。**順1b(`p2` vs `p2d` の `interp` 対比)の新設で必要になった。
   `Documents/05_STATISTICS.md` §4.1 の末尾が正本。
   **★Go/No-Go #4 / #4b の 0.90 で代用してはならない** —— あちらは「その run を解析に載せてよいか」の門、
   こちらは「2 条件をどの時点で突き合わせるか」の定義であり、役割が違う。
   併せて **`H2` 第2節「破れの位置がシード間で一貫しない」の定義**(`01_HYPOTHESES.md` H2 節)。
   **どちらも合否基準なので、エージェントは案を出さない**(`CLAUDE.md` §8)。
2. **順5(= `M*` の実測)。★人間の GPU 承認が要る。**
   その前に RUNNER が **N2**(comparison 群でバッチ1 対 バッチ N の `parsed` 一致確認)を取り、
   実機で `pip freeze` → **ADR-044**(`infra/requirements.lock` の凍結)を履行する。
   **preflight の `forced choice tokens` が WARN / FAIL を出したら人間に上げて止まる。**
3. **順7 の残り**(GPU 時間 0)。`plans/PLAN-004-phase0-route.md` §3 順7 の未着手 3 行:
   §11-10(W6 の分岐)/ §11-13(#11 次第)/ §11-17(Nikankin 原典確認。**SCOUT に委譲**)、
   および**目視レビュー4件**(ADR-030 の R8 手続き / ADR-027 前段 / ADR-028 決定1 と
   Go/No-Go #4b / PLAN-003 §4.8 のセル構成)。
4. **評価側 manifest に `schema_version` を足すか**を決める(ADR-051 の未解決)。小さい。

## 直前セッションで確定したこと(再実装しないこと)

正本は **`plans/PLAN-011-d2d3d4-close.md`** + **`logs/DECISIONS.md` の ADR-053** + `logs/CHANGELOG.md` 末尾。
`pytest code/tests -q` → **808 passed**。GPU 時間 0。`results/` は空。**コードは 1 行も触っていない。**

- **`configs/exp_phase1_main.yaml` の `experiment.hypothesis` = `H2`**(D2 = 案 A。ADR-053 決定1)。
  **交互作用が有意であること(統計的 `H_alt`)を主予測として事前登録した。**
  **★これは主要検定の解釈規則ではない。**LRT は方向を持たず、有意だっただけで
  「タスク型ごとに別の計算をしている」とは書かない(`05_STATISTICS.md` §2)。
  **`configs/template.yaml` と smoke 系の `hypothesis` は null のままである(触らないこと)。**
- **反証条件は 2 種類に分かれた**(D3 = 案 C。ADR-053 決定2)。
  検定に紐づくもの(`H2` 第1節)は Δ 不要 / 水準に紐づくもの(`H0` / `H1` / `H3`)は
  **`05_STATISTICS.md` §5 の新表**の Δ へ。**量と出所だけが凍結済み。値は未決。**
- **`05_STATISTICS.md` §4 に順1b がある**(D4 = 案 α。ADR-053 決定3)。
  `p2` vs `p2d` の `interp` の `rule_rate` 差。**H3 の本体を検定する段である。**
  **順2 以降の番号は繰り上げていない**(6 文書の参照がずれるため)。
- **F6**: 「旧5 は新・順1 に吸収」という §4.1 の記述は**誤りだった**(順1 は `p2d` 単独の交互作用)。
  訂正済み。**「吸収」の実体は並置である。**
- **`09_PAPER_PLAN.md` 図5 の `arb` は確証的な対比ではない**(旧6 は ADR-028 で廃止済み)。
  **追随は下書きで入れた。人間の確定待ち。**

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-011-d2d3d4-close.md` §3(F6)・§4(D2/D3/D4 の決定)
- `Documents/05_STATISTICS.md` §4(順1b と 4 本の注記)/ §4.1 末尾(**再開した操作的定義**)/ §5 の新表
- `Documents/01_HYPOTHESES.md` の「★2026-09-05 追加(PLAN-010 / W4)」節(D1〜D4 はすべて決着済み)
- `logs/DECISIONS.md` の **ADR-053**(`grep -n '^## ADR-053' logs/DECISIONS.md` で位置を出す)
- `STATE.md` は 2,800 行超。**全文 `cat` しない。**`grep -n '^## '` で節を出し `sed -n 'X,Yp'`

## やってはいけないこと

- **`experiment.hypothesis` を書き換える**(ADR-053 決定1 で凍結。実験前に決めた記録である)
- **「`id` 到達度を揃える」の閾値 / `H2` 第2節の一致度の定義を提案して決める**(`CLAUDE.md` §8)
- **§5 の Δ に値を入れる。**すべて**順6(GPU)の実測待ち**であり、`results/` は空である
- **事前登録の凍結タグ(順9)を打つ。**Δ が未決のうちは打てない
- **凍結した効果量プロファイル P1 / 非加法性 RMS = 0.353 を動かす**(ADR-052 決定2。HARKing)
- **`code/analysis/power_sim.py` を今つくる**(ADR-052 決定3。順6 の後)
- **検出力の数値(「シード 10 で足りる」等)を書く**(`s2_seed` / `s2_item` / `s2_tmpl` が順6 待ち)
- **§4 の順2 以降を繰り上げて番号を振り直す**(6 文書の参照がずれる。ADR-053 決定3)
- **`configs/exp_phase1_main.yaml` の `arbitrary_table` を手で編集する**
- **`eval.pool_items` / `eval.cells` を埋める**(B5。`M*` 未決。**順5 の後**)
- **`train.*` のハイパラに値を入れる**(ADR-043 決定10)
- **凍結済みのプロンプト文面を変える**(ADR-046 / 048)/ **強制選択の器械を触る**(ADR-047)
- `configs/smoke.yaml` を編集する(ADR-037 決定4)/ `data/raw/` を書き換える
- **書き出しの `newline="\n"` を外す**(ADR-051 決定4)
- 人間の承認なく GPU ジョブを起動する
- **`python - <<'PY'` の heredoc にバックスラッシュを書く。**この環境の Bash は潰す。
  バックスラッシュを含む置換は scratchpad にスクリプトを書いてから実行する
- **`.md` を CRLF で書き戻す。**`.gitattributes` は `*.md text eol=lf` を宣言している
- **`print()` に `—`(em dash)などを流さない。**この環境の Python の stdout は cp932 で落ちる
  (書き込み自体は `io.open(..., encoding="utf-8")` で成功しているので、慌てて再実行しない)

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

- **★「`id` 到達度を揃える」の操作的定義**(D4 で再び開いた。`05_STATISTICS.md` §4.1)
- **★`H2` 第2節「破れの位置のシード間一貫性」の定義**(D3 でどちらの種類でもないと判明)。
  **定義が無いまま実験に入ると、H2 が支持されたときの主要な知見の側が事後定義になる**
- **★`05_STATISTICS.md` §5 の Δ 5 行すべて**(順6 の実測待ち)。**凍結タグはこれが入るまで打てない**
- **`00_OVERVIEW.md` §8 の整理の確認**: **G2 を失った分の T1 対策の代替が `arb` / `p2d` でよいか**。
  `Documents/06_THREATS.md` T1 の対策表と突き合わせること
- **`09_PAPER_PLAN.md`**: タイトル候補は 3 だけが現行の主軸に整合 / **図5 の `arb` の扱い**(下書き)
- **B5**: `eval.pool_items` の本番の中身(**`M*`(順5)待ち**)/ **`θ` の値**(ADR-041)
- **ADR-047 実装ノートの R3 / F1 / R4 / 検査5**(実装済み。人間が読んで閉じる)
- **評価側 manifest に `schema_version` を足すか**(ADR-051 の未解決)
- **`train.*` のハイパラ**(ADR-043 決定10)/ `infra/requirements.lock`(ADR-044。次のポッドで)
