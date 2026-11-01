# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-11-01(その189)/ 直前セッションの役割: IMPLEMENTER
直前セッションが終了した理由: コンテキスト超過(PLAN-047 I1〜I3 を実装した時点。I4 の既存テストの直し・I5 が残っている)
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: Sonnet — PLAN-047 の続きの実装・テスト(`10_CONTEXT_POLICY.md` §7 の実装の行)。統計の判断が出たら止めて PLANNER(Opus)へ

---

あなたは **IMPLEMENTER** です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**
(Sonnet で判断系の作業になっているなら止めて人間に伝える。`10_CONTEXT_POLICY.md` §7.3)。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(`STATE.md` は冒頭・「いま何をしているか」・「次のアクション」・「引き継ぎ」だけでよい)。
skill `code-style` を読むこと。**分岐を聞き直さない**(前のセッションで人間が (A) を選んだ。順6 の測り直しは人間が起動を言ったときだけ)。

## このセッションでやること(1つだけ)

**PLAN-047 I1〜I5 を完了させる。** コードの大半は**作業ツリーに未コミットで置いてある**(`git status` で `M code/analysis/ceiling_remedy.py`・`M code/analysis/power_sim.py`・`?? code/analysis/ceiling.py`・`?? code/tests/test_power_sim_ceiling.py`)。残り:

1. **既存テスト 2 本の直し**(`code/tests/test_power_sim.py`。どちらも ADR-137 の挙動変更に合わせる直しで、判断は要らない):
   - `test_resumed_run_fits_only_the_missing_replications`: 手で置いた済みの fit に判定の記録(`<シート>/ceiling_verdicts/verdict_<点>_<rep>.json`)が無く、`summarise_point` が「混ざって」と止まる。`power_sim.verdict_name(tag, rep)`・`ceiling.verdict_record(...)` で済みの反復の判定の記録も置く
   - `test_run_writes_one_directory_per_sheet_and_the_records`(1951 行付近): `len(point["tost_min_margins"]) == 2` が落ちる。smoke の小さい表は本物の規則で天井に当たるので、最小 Δ が減る。`power_sim.ceiling_rule` を「天井なし」に差し替える(`test_power_sim_ceiling.force_ceiling` の形)か、`len(margins) + tost_n_ceiling + tost_n_failed == 2` に改める。どちらでもよいが、どちらにしたかを CHANGELOG に書く
2. `pytest code/tests -q`(2 分を超える。**バックグラウンドで走らせ、出力をファイルに落として `tail`**。前のセッションの「exit 0・出力空」は信用できなかった。必ず出力の最後の行を自分で見る)
3. `python -m code.analysis.power_sim --config configs/power_sim.yaml --dry-run` が通る
4. **I5 の smoke**: 偽の当てはめ(`test_power_sim.fake_fits` と同じ形)で、**天井でない表**の要約が HEAD と同じことを確かめる。やり方の案: HEAD を別ディレクトリに取り出し(`git archive HEAD` を空のディレクトリへ)、同じ smoke config・同じ偽の当てはめを HEAD と作業ツリーで走らせ、作業ツリー側は `ceiling_rule` を「天井なし」に差し替える。出力の JSON から**新しい欄**(`power_sim.CEILING_POINT_FIELDS`、`intervals` の `ceiling`・`rejection_noceiling_only`・`rejection_ceiling_descriptive_only`、シートの `ceiling_counted_as`、門の行の `n_ceiling`・`ceiling_ci`、margin 表の `n_ceiling`)を除けば、バイト単位で同じであること
5. 記録: PLAN-047 §9(I1〜I5 の項目)・§11 に 1 行、`logs/CHANGELOG.md`、`STATE.md`(各節は最新 1 ブロック。古い方は `logs/STATE-ARCHIVE.md` へ)、コミット(`feat(analysis): PLAN-047 I1〜I5 ...`。`git add` は**ファイルを名指し**。`-A` は使わない)
6. **I6(文書)は文言の案を作るだけ。人間の承認の前に書き込まない**(PLAN-016 §7-5・`05_STATISTICS.md` §6.8・`06_THREATS.md`・`OPEN-ITEMS.md`)

## 直前セッションで確定したこと(ファイルに書き込み済み)

- **ADR-137**(`logs/DECISIONS.md` 末尾 `grep -n '^## ADR-137'`)の決定1・4・5・6 が実装の根拠。PLAN-047 §5 が手順
- 実装済み(作業ツリー・未コミット):
  - `code/analysis/ceiling.py`: `CeilingVerdict`・`ceiling_rule`・`CeilingRuleError`・`DIRECTION_*`・`verdict_record`・`record_verdict`。規則の中身は移す前と同じ。`ceiling_remedy` は import し直し(同じオブジェクト)。`test_ceiling_remedy.py` 23 本は通った
  - `power_sim.py`: `run_sheet_stage` が `draw_frame` の直後に判定して `ceiling_verdicts/` へ書く(役割 `ROLES` の 4 つ。`ceiling_probe` には当てない)。`load_rep_result` が判定を合流。`summarise_point` が天井の反復を分母に入れて非棄却・TOST は Δ = +∞(`tost_n_ceiling`、`GridPoint.tost_n_infinite`)。`point_record`・`point_intervals`・`_ceiling_beside_gate`・margin 表。門の判定そのものは変えていない
  - `test_power_sim_ceiling.py` 15 本 pass
- **エージェントの設計の選択(人間のレビュー待ち。最後の返答で必ず挙げる)**: ① `CeilingRuleError` の基底を `RuntimeError` に(`PowerSimError` を継ぐと循環 import。`except PowerSimError` は無い)② 判定は `fits/` でなく `ceiling_verdicts/` の別ファイル ③ 判定のある反復とない反復が混ざる点は止める ④ `n_reject` は天井でない成功した反復の棄却数、`n_reject_success` は天井を含む成功した反復の棄却数 ⑤ 判定のない点は天井の欄を出力に出さない ⑥ 天井の件数の CP の水準は `failure_level`

## 触ってよいファイル / 読むべき範囲

- `code/analysis/ceiling.py`・`ceiling_remedy.py`・`power_sim.py`(`grep -n 'ceiling\|n_ceiling\|VERDICTS_DIR' code/analysis/power_sim.py` で特定)/ `code/tests/test_power_sim.py`・`test_power_sim_ceiling.py`・`test_ceiling_remedy.py`・`test_ceiling_probe.py` / PLAN-047 §9・§11 / `logs/CHANGELOG.md`・`STATE.md`
- 全文 `cat` せず `grep -n` → `sed -n 'X,Yp'`

## やってはいけないこと

- 天井の規則の中身・門の値・run3 の格子・`configs/power_sim.yaml`・`rng_seed` 20261008 を変える(ADR-132・133・129・137 で凍結)
- R(`power_sim_fit.R`)・`fits/` の形を変える / 天井の反復で当てはめを飛ばす / 天井の反復を分母から外す(ADR-137 決定4 で却下)
- `ceiling_probe` の役割の要約を変える(決定6。テストで固定済み)
- `primary.py` を書く(別 PLAN)/ I6 の文書を人間の承認前に書き込む
- `git add -A`(未追跡の大きい結果がある: `results/power_sim/ceiling/*/frames/`・`results/ceiling_remedy/*/lmm/` など)
- 全体 pytest を落ちたまま「通った」と書く / 主プール・パイロットのプールを作り直す

## 未解決 / 人間の承認待ち

- 上の「設計の選択」6 点のレビュー / PLAN-047 I6 の文言 / 順6 の測り直しの起動(PLAN-045 I7)/ `primary.py` 本体の PLAN の起票の時期 / 確率の尺度の手続きと TOST の Δ(S5)/ `id` の二重露出の感度解析の事前登録(凍結前)/ R5(組 199)/ S4 の前の push と G2-1 承認 / PLAN-043 §12 の判断 6 件(run3 の前)/ REVIEW の R4 以下・C1/C2
