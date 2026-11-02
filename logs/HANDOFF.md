# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-02(その190)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: PLAN 完了(PLAN-047 I1〜I5 をコミット `d364462`。残りは人間の承認が要る I6 だけ)+ コンテキスト約 120k
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Opus — 設計の選択 6 点のレビューと I6 の文言は判断系(`10_CONTEXT_POLICY.md` §7)。人間が承認したあとの I6 の書き込み自体は Sonnet でよい

---

あなたは **PLANNER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。

## このセッションでやること(1つだけ)

**PLAN-047 の残り(設計の選択 6 点のレビューと I6 の文言の承認)を人間に諮り、決まったら I6 を書く。**
`CLAUDE.md` §8 / ADR-097 決定6: **判断材料の表を先に出し、推奨を先頭に理由付きで示してから `AskUserQuestion` で聞く。** 決めるのは人間。

1. **設計の選択 6 点**(下)を表にして、各点の案・代案・推奨を示す → 人間が採否 → 採ったら ADR-138(提案 エージェント / 採択 人間)か ADR-137 の補記
2. **I6 の文言の案**(下)を示す → 人間が承認 → 承認された分だけ書き込む。完了条件: PLAN-047 §9 の残り 2 項目(I6 の承認・STATE の次のアクションから「B が入っていない」を外す)にチェック
3. 記録(PLAN-047 §11・CHANGELOG・STATE・コミットは**ファイル名指し**)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- コミット `d364462`: `code/analysis/ceiling.py`(規則の移動)・`ceiling_remedy.py`・`power_sim.py`(判定・集計・門の表の横)・`test_power_sim_ceiling.py`(15 本)・`test_power_sim.py`(既存 2 本を直した: `never_ceiling` と、済みの fit の隣の判定の記録)
- `pytest code/tests -q` = 2640 passed in 750.90s / `power_sim --dry-run` exit 0 / I5 の smoke: HEAD と作業ツリーの `power_sim_summary.json` の差は新しい欄と `run_id` だけ・`fits/` 26 枚バイト一致(`logs/CHANGELOG.md` その190)
- **設計の選択 6 点(エージェントの案・人間のレビュー待ち)**: ① `CeilingRuleError` の基底を `RuntimeError` に(`PowerSimError` を継ぐと循環 import。`except PowerSimError` は無い)② 判定は `fits/` でなく `ceiling_verdicts/` の別ファイル ③ 判定のある反復とない反復が混ざる点は止める ④ `n_reject` は天井でない成功した反復の棄却数、`n_reject_success` は天井を含む成功した反復の棄却数 ⑤ 判定のない点は天井の欄を出力に出さない ⑥ 天井の件数の CP の水準は `failure_level`
- **I6 の文言の案(まだ書き込んでいない。人間の承認前に書かない)**:
  - PLAN-016 §7-5: 「`primary.py` は実データで 適格性フィルタ → df のランク規則 → 天井の規則(`code.analysis.ceiling.ceiling_rule`)→ 当てはめ の順。天井が当たっても当てはめて記録し、報告は『実施不能(天井)』とし p 値・TOST を報告しない(ADR-137 決定2・3)。`primary.py` 本体は別 PLAN」
  - `05_STATISTICS.md` §6.8: 「run3 の検出力のシミュレーションでは、天井と判定された反復を分母に入れて非棄却、TOST は Δ = +∞ で数える。過誤の門は非棄却を含む率のまま、実行可能性の門には入れず天井の件数と CP95 を門の表の横に記録する(ADR-137 決定4・5)」
  - `06_THREATS.md`(E9 の行): 「天井の規則が当たると主要検定は実施不能(ADR-135)。run3 の検出力は天井の頻度に応じて下がる。天井の反復は非棄却に数えるので検出力を過大には見積もらない」
  - `OPEN-ITEMS.md`: ADR-132 決定5 は C 用として閉じた記録の 1 行(ADR-137 決定7)

## 触ってよいファイル / 読むべき範囲

- `logs/DECISIONS.md` 末尾(`grep -n '^## ADR-137'`)/ `plans/PLAN-047-ceiling-b-into-primary-and-run3.md` §4・§9・§11 / I6 の対象: `plans/PLAN-016-fitting-engine.md`(§7-5)・`Documents/05_STATISTICS.md` §6.8・`Documents/06_THREATS.md`・`logs/OPEN-ITEMS.md`
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`

## やってはいけないこと

- 天井の規則の中身・門の値・run3 の格子・`configs/power_sim.yaml`・`rng_seed` 20261008 を変える(ADR-132・133・129・137 で凍結)
- 人間の承認前に I6 の文書を書き込む / 設計の選択を人間の代わりに決める / `primary.py` を書く(別 PLAN)
- `git add -A`(未追跡の大きい結果: `results/power_sim/ceiling/*/frames/`・`results/ceiling_remedy/*/lmm/` など)
- バックグラウンド pytest の「exit 0」を信用する(外側のシェルが終わっただけのことがある。出力ファイルの `EXIT=` と最後の行を自分で見る)

## 未解決 / 人間の承認待ち

- 設計の選択 6 点 / I6 の文言 / 順6 の測り直しの起動(PLAN-045 I7)/ `primary.py` 本体の PLAN の起票の時期 / 確率の尺度の手続きと TOST の Δ(S5)/ `id` の二重露出の感度解析の事前登録(凍結前)/ R5(組 199)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2
