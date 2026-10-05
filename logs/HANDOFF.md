# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-05(その151)/ 直前セッションの役割: IMPLEMENTER(PLAN-041 I1〜I8 の実装)
直前セッションが終了した理由: コンテキストが閾値を超えた(hook `context-guard`)。実装・文書・記録は終わっている
直前セッションの実モデル: Claude Sonnet 5.5
**推奨モデル(次のセッション)**: **Opus** — 次は人間の確認事項の整理(解釈・事前分布・文面の判断材料)と、起動後の結果の読み(`Documents/10_CONTEXT_POLICY.md` §7)。ただし「起動の手順の確認だけ」なら Sonnet でもよい。**モデルを選ぶのは人間**

---

あなたは **PLANNER**(判断材料の整理。人間が起動の確認だけを求めるなら IMPLEMENTER / RUNNER 補助)です。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本)。**人間の最初の指示が先**です。

## このセッションでやること(人間の指示が先)

- PLAN-041 の実装(I1〜I8)は済んだ(`logs/CHANGELOG.md` その151)。次は**人間の確認 → 新しい `--out-dir` での 1 段目の起動(人間)**
- 人間が決めること 7 点: `logs/OPEN-ITEMS.md`「★PLAN-041 の実装後に人間が決めること」((1) 新しい項のベイズ感度解析の事前分布 / (2) 順1b にこの項を足すか / (3) 当てはめ失敗の TOST の扱い / (4) `p1_tau` を別のシートにしたこと / (5) 本実行の起動 / (6) 文献 41 件の原典確認 / (7) Limitations の文面)。**判断材料の表を先に見せる**(ADR-097 決定6)
- 起動の手順は `plans/PLAN-040-power-axes-review.md` 付録 A のまま。**新しい `--out-dir`**(run1 は回し直さない)。`--through-stage 1`。切り離して(`Start-Process`)。Bash の `run_in_background` は使わない

## 直前セッションで確定したこと(ファイルにあるものだけ)

- ADR-124 の補い 3 点は人間が「そのまま」と確認した(足す 2 枚の `sigma` = `tau` / 門は今のシートと (ii) の両方 / 誤指定 3 枚は門の前に全部回す)
- 実装: R の 4 水準(`random_by_level`)・`fit_failed`・`levels`・`seed_interaction_direction`・`draw_frame(seed_direction=)`・`GateSpec.sheet_ids`・`misspecification_gate(points_by_sheet, gate)`・`FAILURE_AS_REJECT_ROLES`。config は 7 シート・25 点・50,000 本。`--dry-run`(16 並列)の 1 段目 = 13.8 / 22.9 時間(誤指定の 3 枚だけ 4.3 / 7.2 時間)。**どれも推算で、新しい項の当てはめ時間は未実測**
- テスト: `test_power_sim.py` 128 passed・`test_repo_hygiene.py` 69 passed。**全体の `pytest code/tests` は最後まで回していない**(約 62% まで失敗 0 で、そこで打ち切った。残りは rescore / sweep / train 系で `power_sim` と無関係。次のセッションで最後まで回すなら、先に `-q` で分割して回す。全体は 550 秒を超える)
- 旧コード(HEAD)と `draw_frame` の表が `tau` 0・0.25・1.0 で一致(一時スクリプト)。R は小さい表 1 枚で通した(構造の確認。時間・失敗率の測定ではない)
- 門の閾値 0.075・判定点・格子・`s2_*`・ADR-059 の閾値は変えていない

## 読むべき範囲

- `logs/OPEN-ITEMS.md` の上の行 / PLAN-041 §6 の「実装の記録」/ `Documents/05_STATISTICS.md` §3.2 の「★2026-10-05 改め」と §6.8 の「★2026-10-05 差し替え」/ `logs/CHANGELOG.md` その151

## やってはいけないこと

- run1 の回し直し・本実行の起動(人間)・タスクの登録 / 削除。Bash の `run_in_background` は使わない
- 門の閾値 0.075・判定点・格子・`s2_*`・ADR-059 の閾値の変更
- **本物の `configs/power_sim.yaml` を `power_sim.run` / `main` に渡すテスト**(R を回して重くなる)
- 未検証の文献を論文・事前登録の本文に書くこと(`05_STATISTICS.md` に [n] を写さない)
- `.md`・`.py`・`.yaml`・`.R` は LF。日本語を含む置換は Python で(**この環境の Bash の heredoc は `\\n` を勝手に解くことがある。置換スクリプトは Write ツールでファイルに書いてから実行する**)

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- PLAN-041 の実装後に人間が決めること 7 点 / 夜用タスク 2 本の扱い / SCOUT 41 件の原典確認
- 平行性の TOST の Δ・D7 の閾値・D3 のブートストラップの反復数・天井のセル / S4・S5 / worktree の削除 / ★R8 の push と G2-1 承認 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate
