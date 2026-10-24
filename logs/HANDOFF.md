# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-24(その182)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN完了(PLAN-045 I1〜I6)+ コンテキスト超過の警告(約 227k)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: Opus — 下の分岐の既定は ANALYST(PLAN-046 §6.1 の記述。`10_CONTEXT_POLICY.md` §7 の「統計・解釈」の行)。RUNNER(I7)になる場合は Sonnet で可

---

あなたは ANALYST です(分岐: 下記)。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。

## 分岐(最初に 1 回だけ確かめる)

```bash
for d in results/power_sim/ceiling_probnull/*/; do echo "$d $(ls $d/fits 2>/dev/null | wc -l)"; done; ls results/ceiling_remedy 2>&1 | head -3
```

- **L50 が 100 / `results/ceiling_remedy` がある**: ANALYST(Opus)。PLAN-046 §6.1 の量を公式 summary から記述だけ・G1・G2 を機械的に(§6.4)。解釈・C の採否は書かない
- **揃っていない(その182 の時点は L05 100・L50 0・`ceiling_remedy` 無し)**: **エージェントの作業は無い。**人間に「probnull の再開」と「順6 の測り直し(PLAN-045 I7)」のどちらを起動するかを聞いて止まる。人間が I7 を指示したら RUNNER として `infra/RUNPOD.md` §4 の手順で 1 run(設定は順6 R1・作り直した主プール)

## このセッションでやること(1つだけ)

上の分岐の 1 つ。どちらも起動・判断は人間の指示の後。

## 直前セッションで確定したこと(ファイルに書き込み済み)

- `d11853c`: **PLAN-045 I1〜I6 完了**(ADR-134)。`eval.interp_mirror_filter: true` は主の config 4 本(`exp_phase1_main`・`_b1`・`_t2cross`・`exp_t1c_main`)だけ。主プールと `main_t2_cross` を作り直した: 主 `pairs_hash` `c20991dd…`・`items_sha256` `6bb6084d…`(旧 `13e8479c…`・`d272204f…`)。数は組合せ論的な計数で PLAN-045 §3 と一致(除いた組 473・`interp` の `mirror_in_K` 0・`id` T1 21・T2 26)。パイロットのプールは不変(テスト)。`frame.py` に列 `mirror_in_K`。pytest 2624 passed。詳細は PLAN-045 §11
- **順6 の印は旧い主プールで付いた**([run:20260911_141547_order6_r1] ほか)。`interp` セルはほぼ全部入れ替わったので、I7 の測り直しが残っている
- probnull は `ceiling_probnull_L50` fits 0 のまま(再開は人間。コマンドは `STATE.md`「次のアクション」1)

## 触ってよいファイル / 読むべき範囲

- ANALYST: `plans/PLAN-046-*.md` §6(`grep -n '^## \|^### ' ` → `sed -n`)・`results/ceiling_remedy/` の公式 summary(`jq` で必要なキーだけ)
- RUNNER: `infra/RUNPOD.md` §4・順6 R1 の config・`runs/<id>/`

## やってはいけないこと

- probnull の再開・I7 の起動を人間の指示なしに行う / C の採否・印の解釈を書く
- `results/power_sim/ceiling/*/frames/` を `git add` する。**`git add -A` を使わない**(未追跡の大きい結果がある)
- 主プール・パイロットのプールを作り直す(PLAN-045 で確定済み)

## 未解決 / 人間の承認待ち

- probnull の再開と評価の起動 / C の採否(評価の後・別の ADR)/ 順6 の測り直しの起動(PLAN-045 I7)/ 確率の尺度の TOST の Δ(凍結前)/ `id` の二重露出の感度解析の事前登録(凍結前)/ R5(新しい主プールの組のうち逆順がパイロットのプールにある組 199。manifest に記録)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2
