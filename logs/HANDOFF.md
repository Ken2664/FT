# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-10-04(その141)/ 直前セッションの役割: PLANNER(PLAN-040 の起草と D1〜D8)
直前セッションが終了した理由: PLAN-040 の設計が確定した(1 セッション = 1 PLAN。`CLAUDE.md` §10.2)
直前セッションの実モデル: Claude Opus 5.5
**推奨モデル(次のセッション)**: 人間が PLAN-040 §11 の値を先に決めるなら **Opus**(判断材料の表を作る)。値を null のまま門で止まる形で実装を先に進めるなら **Sonnet**(IMPLEMENTER。`Documents/10_CONTEXT_POLICY.md` §7)。**どちらにするか・モデルを選ぶのは人間**

---

あなたはこの repo の担当エージェントです。**最初の発言で、自分の実モデル名と、上の推奨モデルとの一致・不一致を 1 行で述べること**。
`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください(**worktree `claude/great-bardeen-9c1ac4` は登録済みの既知の 1 本**)。**人間の最初の指示が先**です。

## このセッションでやること(人間が選ぶ)

- **X: PLAN-040 §11 の値を人間が決める**(`n_item` の格子・`sigma` の確認点・各段の `n_rep`・誤指定で「膨らむ」とみなす閾値)。エージェントは**判断材料の表を先に見せる**(ADR-097 決定6)が、**値は提案しない**(ADR-122 の範囲。人間が明示的に外せば別)。材料: `plans/PLAN-034-check-prerun/README.md` F2・F4 の近似の表、費用は `n_item` にほぼ比例
- **Y: IMPLEMENTER が PLAN-040 §6 の I1〜I7**(skill `code-style` を読む)。§11 が空なら、その欄は config で null にして門で止まる形にする。**`SeedSequence`(シート × 点 × 反復)・`below_swept_range`・run_id / git sha / config の写し・R の JSON の一時ファイル + rename・切り離した起動の手順・誤指定のシートを先頭に回して閾値で止める**

## 直前セッションで確定したこと(ファイルに書き込み済み)

- 人間は A(本実行を止めて PLAN を起こす)。PLAN-040 の D1〜D8 は 8 問とも推奨 = **ADR-122**(`plans/PLAN-040-power-axes-review.md` §4・§4.1)
- `configs/power_sim.yaml`・`code/` は無変更。本実行は起動していない
- この機械は 2026-10-04 その141 の時点で **AC 電源**(`BatteryStatus` = 2)

## やってはいけないこと

- **Bash の `run_in_background` で本実行を起動しない**(最大 2 時間で止まる)。起動は人間の端末か切り離したプロセスで
- **本物の `configs/power_sim.yaml` を `power_sim.run` に渡すテストを書かない**(門が開いて本実行が走る。その139 の暴走)
- ADR-111〜122 を覆さない。`s2_*` を変えない。Δ・D7 の閾値・`n_item` の格子の値を決めない。**実際の `eval.cells` は変えない**(S5)
- **格子を検出力の曲線を見てから選ばない**(PLAN-040 §7 罠1)。誤指定の閾値は誤指定の結果を見る前に書く(罠3)
- **Windows**: `.md`・`.py`・`.yaml`・`.R` は LF。1 コマンドに heredoc を 2 つ入れない。Python に渡すパスは `cygpath -m`
- STATE.md は 366 行・約 58.7 KB(上限 400 行 / 60 KB)。足すときは同じだけアーカイブへ移す

## 未解決 / 人間の承認待ち(正本は `logs/OPEN-ITEMS.md`)

- **★PLAN-040 の値** ★新
- 平行性の TOST の Δ・D7 の閾値・`glmer` の例外の規則・天井のセル
- S4 の T1c の順 / worktree `claude/great-bardeen-9c1ac4` の削除 / MisFT の原典確認 / 凍結前(S5)の値の一式 / ★R8 の push と G2-1 承認 / 2 系統目 / `CLAUDE.md` を 200 行へ / 旧 pod 5 本の terminate / 引用の原典確認
