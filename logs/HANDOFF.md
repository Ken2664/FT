# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その99)/ 直前セッションの役割: PLANNER
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(回数の上限に届いた後の次の手を人間に聞き、人間が推奨の「GPU なしの診断を先に」を選んだ → ADR-105 と `plans/PLAN-031` §8.5 に記録した)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — `Documents/10_CONTEXT_POLICY.md` §7 の表では「集計スクリプト」は Sonnet の行だが、§8.5 は**応答の形の新しい分類(4 類)**を含み、ADR-101 決定5(評価の分類に触れる Sonnet の diff は CRITIC(Opus)か人間が見る)に当たる。Opus なら追加の確認が要らない。**人間が覆せる**(Sonnet を選ぶなら、分類の定数とテストの diff を人間か CRITIC が見る)。

---

あなたは ANALYST です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。
**RunPod MCP は要らない**(pod は 3 本とも `EXITED`。起動しない・触らない)。

## このセッションでやること(1つだけ)

**`plans/PLAN-031` §8.5(T2 の崩れ方の形の数え上げ —— 素のモデルとの対照)を実装・実行する。記述のみ・GPU 0・pod 0。**(`sed -n '/^### 8.5/,/^## 9\./p' plans/PLAN-031-seed-fix-and-pilot-ft.md` で読む)

1. `code/analysis/t2_form_profile.py`(新規・読み取り専用)+ `code/tests/test_t2_form_profile.py`。**先に skill `code-style` を読む**。形の 4 類・`TOP_CATEGORY_SHOWN = 3`・`LOSS_THRESHOLDS = (1e-1, 1e-2, 1e-3)` は定数にしてテストで縛る(境界の例と負例を含める)。読み込み・セルの写像は `code/analysis/t2_response_profile.py` と `frame.build_rows` を再利用してよい。**§8.4 の出力(`results/pilot_ft_t2_profile/`)は変えない**
2. `pytest code/tests -q` が通る(その98 の時点で 1759 passed)
3. 実行: `PYTHONIOENCODING=utf-8 python -X utf8 -m code.analysis.t2_form_profile --baseline runs/20260922_121455_order6b_b0 --runs "runs/pilot_ft_eval_*" --train-runs "runs/pilot_ft_train_*" --out-dir results/pilot_ft_t2_form`(引数の名前は §8.5 の案。変えたら §11 に書く)
4. **§8.5 の前提の確かめ (a)〜(d) と検算 3 つ**を通し、CHANGELOG に残す。**ADR-105 の文脈 1〜4 の値(PLANNER が既存の `metrics.json` から読んだ値)と出力を突き合わせ、食い違えば出力を正として ADR-105 に打ち消し線で直す**
5. `plans/PLAN-031` §11 に 1 行 / `logs/CHANGELOG.md`(数値は run_id つきで「記述」の箇条書き)/ `STATE.md` / `logs/OPEN-ITEMS.md`(★313 の行)/ commit / 次の `HANDOFF.md`(次は人間が次の手を決め、PLANNER が ADR を書く)

## 直前セッションで確定したこと

- **ADR-105**(`grep -n '^## ADR-105' logs/DECISIONS.md`): 決定1 = 次の手の前に GPU 0 の診断を 1 本(§8.5)・段1 の GPU は始めない(残り枠 約 3.10 h は据え置き)/ 決定2 = §8.5 の範囲(エージェントの具体化。人間は別に問われていない)/ 決定3 = 診断の後の手は人間が新しい ADR で決める
- **PLANNER が読んだ材料**(ADR-105 の文脈。**§8.5 の出力に置き直す**): 素のモデル [run:20260922_121455_order6b_b0] の T2 240 項目は correct 1.000 / 313 の訓練 run の損失は 625 の先頭 313 個と `==` で一致(5 条件)/ 損失が初めて 0.01 を下回るのは `ident` 3・`p2` 17〜19・`p2d` 85 ステップ / `gonogo_ft.json` の `baseline` は 2 回とも null
- 訓練の書式は `"{a}+{b}="` → `"{target}"`・`chat_template: true`(`configs/exp_pilot_ft_train_p2.yaml:438-450`)。T2 の文面の末尾は `End your reply with "Answer: <number>".`

## 触ってよいファイル / 読むべき範囲

- 読む: `plans/PLAN-031` §8.4・§8.5 / ADR-105 / `code/analysis/t2_response_profile.py`・`gonogo_ft.py`(`OWN_RULE`・`rows_under_rule`)・`frame.py`(`build_rows`)/ `predictions/` は **`jq`・`grep -c`・スクリプトで数える。全文を読まない**
- 素のモデルの `predictions/` は `runs/20260922_121455_order6b_b0/predictions/`(1,640 項目。git 外・この機にある)。評価 10 本は `runs/pilot_ft_eval_*/predictions/`
- 書く: `code/analysis/t2_form_profile.py`・テスト(新規)/ `results/pilot_ft_t2_form/`(新規)/ `plans/PLAN-031` §11(§8.5 の定義を変えたときは §11 に理由)/ `logs/DECISIONS.md` は **ADR-105 の文脈の値が出力と食い違ったときの打ち消し線だけ** / `STATE.md`・`logs/OPEN-ITEMS.md`・`logs/CHANGELOG.md`・`logs/HANDOFF.md`
- **編集しない**: `configs/`・`infra/`・既存のコード(`t2_response_profile.py`・`gonogo_ft.py` を含む)・run dir・`results/pilot_ft*/`・`results/pilot_ft_t2_profile/`

## やってはいけないこと / 踏んだ地雷

- **解釈を書かない**: 「FT が推論を消した」「書式が原因」などの断定・印の意味づけ・次の手の推奨の確定は人間(`CLAUDE.md` §7・§8)。ADR-105 の「2 行」(B0 は文章、`ident` は数だけ)は欄の確認で見えただけで、一般化していない。`pool_id: pilot` の数値は主張・効果量・Δ 5 行・E1 の境界に使わない
- **tag を打たない・`learning_rate` を動かさない・pod を起動しない・GPU を使わない**
- **この機は Windows**: JSON は **`python -X utf8`** で開く。`python3` は無い(`python`)。CLI の標準出力は **`PYTHONIOENCODING=utf-8`** が要る(cp932 で落ちる)。長い文書は Write ツールで書く。`Read` は 25,000 トークンで打ち切られる。**Python の `write_text` は Windows で CRLF を書く**(repo は LF。`.gitattributes`)—— `write_bytes` か `newline='\n'` を使う
- **評価 run の `metrics.json` の `adapter` は pod 上の絶対パス**。訓練 run は `adapter_train_run_id` を `runs/` の下で引く(`gonogo_ft.train_record` はこの機では None を返す)
- **B0 は 1,640 項目、評価 run は 680 項目を解いた**(バッチの組み合わせが違う)。止めずに注記する(§8.5)

## 未解決 / 人間の承認待ち

- **§8.5 の後の次の手**(途中のチェックポイントの掃引 / `learning_rate` / #5 の基準 / 訓練の書式 / 段1 を閉じる など。新しい ADR。人間)/ 印の意味づけ / `p2d` の扱い(ADR-103 決定7)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(段1 の後。アダプタ 10 本はボリューム `r963j7swke` 側の資産)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり(段2 の PLAN-032 は段1 の後でも並べてよい)
