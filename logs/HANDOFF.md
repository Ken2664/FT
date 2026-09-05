# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-05 / 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **PLAN 完了**(PLAN-010 = 順7 の GPU 不要分 + 人間の D1/D5/D6/D7)。

---

あなたは **PLANNER(または人間の決定を受ける IMPLEMENTER / RUNNER)** です。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(人間が1つ選ぶ)

**順7 の GPU 不要分は閉じた。**残りは下の4つ。**GPU を使うのは 2 だけで、人間の承認が要る。**

1. **D2 / D3 / D4 の決着**(GPU 時間 0。**人間の入力が本体**)。
   `Documents/01_HYPOTHESES.md` の「★2026-09-05 追加(PLAN-010 / W4)」節が正本。
   **D2**: `experiment.hypothesis` に何を入れるか(A `H2` / B `H1` / C 単一の H を宣言しない)。
   **★エージェントは推奨を出さない** —— 予測を事前に宣言する行為そのものである(`CLAUDE.md` §8)。
   **D3**: 反証条件の「大きく落ちる」を数値化するか(Δ は順6 待ち)。
   **D4**: H3 を `Documents/05_STATISTICS.md` §4 の副次の階段のどの段に置くか。
   完了条件: `configs/exp_phase1_main.yaml` の `experiment.hypothesis` の null が外れること。
2. **順5(= `M*` の実測)。★人間の GPU 承認が要る。**
   その前に RUNNER が **N2**(comparison 群でバッチ1 対 バッチ N の `parsed` 一致確認)を取り、
   実機で `pip freeze` → **ADR-044**(`infra/requirements.lock` の凍結)を履行する。
   **preflight の `forced choice tokens` が WARN / FAIL を出したら人間に上げて止まる。**
3. **順7 の残り**(GPU 時間 0)。PLAN-004 §3 順7 の未着手 3 行:
   §11-10(W6 の分岐)/ §11-13(#11 次第)/ §11-17(Nikankin 原典確認。**SCOUT に委譲**)、
   および**目視レビュー4件**(ADR-030 の R8 手続き / ADR-027 前段 / ADR-028 決定1 と
   Go/No-Go #4b / PLAN-003 §4.8 のセル構成)。
4. **評価側 manifest に `schema_version` を足すか**を決める(ADR-051 の未解決)。小さい。

## 直前セッションで確定したこと(再実装しないこと)

commit **`9fc4593`**(4文書の下書き)/ **`5d5a849`**(ADR-052)。`pytest code/tests -q` → **808 passed**。
GPU 時間 0。`results/` は空。正本は **`plans/PLAN-010-order7-doc-followup.md`** +
**`logs/DECISIONS.md` の ADR-052** + `logs/CHANGELOG.md` 末尾。

- **★`H0` / `H1` / `H2` / `H3` は本 repo では研究仮説(`Documents/01_HYPOTHESES.md`)だけを指す。**
  `Documents/05_STATISTICS.md` §2 の帰無・対立仮説は **`H_null` / `H_alt`** である(ADR-052 決定1)。
  改名前は**2文書で正反対を指していた** —— 研究仮説 `H1`(概念的)が予測するのは統計的 `H_null` である。
- **検出力分析の効果量は凍結済み: P1(入力書式で割れる)。非加法性 RMS = 0.353 logit**
  (ADR-052 決定2。`Documents/05_STATISTICS.md` §6.5 / §6.6)。**実験後に変更できない。**
  **★これは「検出力の大きさ」を決めたのであって「どちらの形が起きると予測したか」ではない。**
  **LRT は形を区別しない。**P2(同じ RMS)と検出力が大きく違ったら**シミュレータのバグを疑う**。
- **効果量は 12 セルのプロファイルとしてしか指定できない**(§6.1 / §6.2)。
  旧「G6 rule_rate 差 = 0.30」というスカラー1個には戻せない。
- **4文書の新記述はすべて「★下書き。人間の確定待ち」である。**旧記述は打ち消し線で残してある。
- **`00_OVERVIEW.md` §5・§8 と `05_STATISTICS.md` §5 は HANDOFF の指定範囲外だったが、
  人間が承認済み**(ADR-052 決定4)。差し戻さないこと。

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-010-order7-doc-followup.md` §5(F1〜F5 と D1〜D7 の状態)
- `Documents/01_HYPOTHESES.md` の「★2026-09-05 追加(PLAN-010 / W4)」節(D2 / D3 / D4)
- `logs/DECISIONS.md` の **ADR-052**(`grep -n '^## ADR-052' logs/DECISIONS.md` で位置を出す)
- `STATE.md` は 2,000 行超。**全文 `cat` しない。**`grep -n '^## '` で節を出し `sed -n 'X,Yp'`

## やってはいけないこと

- **`experiment.hypothesis` に H 番号を入れる**(D2。**人間が決める**。エージェントは推奨も出さない)
- **凍結した効果量プロファイル P1 を変える / 非加法性 RMS = 0.353 を動かす**(ADR-052 決定2。HARKing)
- **`code/analysis/power_sim.py` を今つくる**(ADR-052 決定3。順6 の後。分散成分が無いと回せない)
- **検出力の数値(「シード 10 で足りる」等)を書く。**`s2_seed` / `s2_item` / `s2_tmpl` が
  **順6 の GPU 実測待ち**であり、`results/` は空である
- **`configs/exp_phase1_main.yaml` の `arbitrary_table` を手で編集する**
- **`eval.pool_items` / `eval.cells` を埋める**(B5。`M*` 未決。**順5 の後**)
- **`train.*` のハイパラに値を入れる**(ADR-043 決定10)
- 合否基準・しきい値・Go/No-Go 判定コード・`θ`・`M*` を書く / 提案して決める
- **凍結済みのプロンプト文面を変える**(ADR-046 / 048)/ **強制選択の器械を触る**(ADR-047)
- `configs/smoke.yaml` を編集する(ADR-037 決定4)/ `data/raw/` を書き換える
- **書き出しの `newline="\n"` を外す**(ADR-051 決定4)
- 人間の承認なく GPU ジョブを起動する
- **`python - <<'PY'` の heredoc にバックスラッシュを書く。**この環境の Bash は潰す。
  バックスラッシュを含む置換は scratchpad にスクリプトを書いてから実行する
- **`.md` を CRLF で書き戻す。**`.gitattributes` は `*.md text eol=lf` を宣言している

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

- **★D2: `experiment.hypothesis` が null。**論文の claim に直結するので人間が確定させる
- **★D3**: 反証条件の数値化(Δ は順6 待ち)/ **★D4**: H3 を副次の階段のどの段に置くか
- **`05_STATISTICS.md` §5 の同等性境界**: 「勾配が平行である」の TOST 境界が**未決**。
  **主要検定が非有意に終わる筋書きは十分あり得るので、実験前に決めないと結果を解釈できない**
- **`00_OVERVIEW.md` §8 の整理の確認**: **G2 を失った分の T1 対策の代替が `arb` / `p2d` でよいか**。
  `Documents/06_THREATS.md` T1 の対策表と突き合わせること
- **`09_PAPER_PLAN.md` のタイトル候補**: 1・2 は廃止された枠組みの語。**3 だけが現行の主軸に整合**
- **B5**: `eval.pool_items` の本番の中身(**`M*`(順5)待ち**)/ **`θ` の値**(ADR-041)
- **ADR-047 実装ノートの R3 / F1 / R4 / 検査5**(実装済み。人間が読んで閉じる)
- **評価側 manifest に `schema_version` を足すか**(ADR-051 の未解決)
- **`train.*` のハイパラ**(ADR-043 決定10)/ `infra/requirements.lock`(ADR-044。次のポッドで)
