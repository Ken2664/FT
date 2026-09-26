# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-26(その108)/ 直前セッションの役割: CRITIC
直前セッションが終了した理由: **PLAN の 1 区切りが完了した**(ADR-108 の実装の diff のレビューを `logs/CRITIQUE.md`「その108」に書いた)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は人間に選択肢と推奨を示して ADR を書く(`Documents/10_CONTEXT_POLICY.md` §7 の表の「設計判断」の行)。**ただし人間が C108-1〜4 をどれも採らないと自分で決めるなら、このセッションは要らない**(そのときは凍結 tag へ進む)

---

あなたは PLANNER です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(`10_CONTEXT_POLICY.md` §7.3)。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。RunPod MCP は要らない(GPU は使わない)。

## このセッションでやること(1つだけ)

**`logs/CRITIQUE.md`「その108」の C108-1〜4 と、実装の読み 12〜17(`plans/PLAN-032` §11 の注)を人間に諮り、回答を ADR-109 に書く。**
その106(ADR-108)と同じ形: 選択肢・推奨・理由をチャットで先に示してから `AskUserQuestion`(memory「Recommend before choice」・ADR-097 決定6)。
採ったものがあれば次は IMPLEMENTER。**どれも採らなければ、次は凍結 tag(人間)**。

諮る材料(CRITIC の案。値や規則は変えない):

1. **C108-1【低〜中】**: R1 の前提の照合は run dir の `sharpness` 欄の宣言との一致なので、4 腕そろって設定を書き換えた run(例: 4 本とも `eval.batch_size` と `sharpness.batch_size` を 8)は止まらない。線 0.088・`n_per_level` 160 も run dir から読む。案 (a) 各 run の `git_sha.txt` が同じで `git_diff.patch` が空であることを照合し、sha を判定表の先頭に出す(人間が tag の commit と見比べる。段4 でも使える)/ (b) run の `sharpness` 欄と `eval` の該当欄を repo の `configs/exp_diag_*.yaml` と照合 / (c) 何もしない(判定表を読むときに人間が `git_sha.txt` を見る)。**CRITIC (Opus 5.5) の見立ては (a)**(軽く、ADR-108 決定5 の「宣言との一致」を変えずに、宣言そのものの出どころを押さえる)
2. **C108-2【低】**: R5 が T3 の B を読む取り違えを捕まえるシナリオを 1 つ足すか(`b` = T1b 常に No・T3 真値どおり / `a` = 常に No / `b_d` = 真値どおり / `a_d` = 常に No)
3. **C108-3【低】**: `cell_delta2` で「組ごとの差の平均 = 点推定(有理数)」と「n = `n_per_level`」を確かめて止めるか
4. **C108-4【低・nit】**: 例外の型のそろえの残り(`metrics["threshold_sweep"]`・トークナイザ・`runs[0]`・`mass_rows`)を包むか
5. **実装の読み 12〜17** をそのまま採るか(とくに 13 = 上位 k は config と全行の個数で照合。CRITIC は §8.1 R7 と食い違わないと確かめた)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `logs/CRITIQUE.md`「その108」: **決定2(R6 の区間)は §8.1 R6 どおり**(計算法は不変、切り詰めと退化の印は判定の点推定に触れない)。本番の件数の合成の run で「組ごとの差の平均 = 点推定」「区間 = 手計算」を確かめた(実験結果ではない)。**判定を黙って変える経路は見つからなかった。凍結 tag を止める誤りは無い**
- `pytest code/tests -q` → **1958 passed**(再現)。コード・config・テスト・PLAN・ADR は変えていない
- 観察(指摘ではない): 合成の答え方で線のすぐ両側(56/640・57/640)の区間はどちらも線 0.088 を含む。判定は点推定だけ(ADR-107 決定3 (iv))

## 触ってよいファイル / 読むべき範囲

- 書く: `logs/DECISIONS.md`(ADR-109)/ `plans/PLAN-032`(ヘッダ・§10・§11。**§8.1 を直すのは、人間の回答が R7 の文面に触れるときだけ**。C108-1 の (a) (b) は R7 の止める条件を足すので §8.1 R7 に 1 行要るかを人間に聞く)/ `logs/OPEN-ITEMS.md` / `STATE.md` / `logs/CHANGELOG.md` / `logs/HANDOFF.md`
- 読む: `logs/CRITIQUE.md`「その108」(`grep -n 'その108' logs/CRITIQUE.md`)/ `plans/PLAN-032` §8.1(`grep -n '### 8.1' plans/PLAN-032-sharpness-diagnostic.md`)・§11 の注 12〜17 / ADR-108(`grep -n '^## ADR-108' logs/DECISIONS.md`)
- **編集しない**: コード・config・テスト(次の IMPLEMENTER)/ `logs/CRITIQUE.md`(CRITIC の追記のみのファイル)

## やってはいけないこと

- **tag を打たない・pod を起動しない・GPU を使わない**。合否線・R2〜R5 の規則を変えない
- **この機は Windows**: `python -X utf8`・`PYTHONIOENCODING=utf-8`。bash の heredoc に日本語の長文を流さない(Write ツールで scratchpad に書いてから `cat >>` / `python <script>`。Python に渡すパスは `C:/Users/...` の形)
- テストのモジュールを scratchpad から import するときは `PYTHONPATH=C:/Users/keenk/paper/FT/infra` が要る(`preflight` を読む)

## 未解決 / 人間の承認待ち

- **C108-1〜4 の採否と実装の読み 12〜17 の確認** → (採れば IMPLEMENTER)→ **PLAN-032 の凍結 tag(案 `preregister-diag-sharpness`)→ G2-1 GPU 承認**(`logs/OPEN-ITEMS.md` の行)
- ★T2 の形の変化と #5 の扱い(Phase 1 の凍結前)
- 3 本の pod(`eytvn0qwssz2q8`・`ysev2xg35iih2j`・`lh823acvxuo8ux`)の terminate(いつでも。**ボリューム `r963j7swke` は残す**)
- 変わらず: `STATE.md`「人間の承認・判断を待っている事項」と `logs/OPEN-ITEMS.md` のとおり
