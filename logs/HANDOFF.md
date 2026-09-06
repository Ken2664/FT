# HANDOFF — 次のセッションに貼るプロンプト

生成: 2026-09-06(その6)/ 直前セッションの役割: PLANNER (Opus)
直前セッションが終了した理由: **コンテキスト超過**(hook `context-guard` が約 275k を報告)。
**PLAN-014 は未完である**(§4 の決定は全件済み、実装は D-C のみ完了)。
commit `32b8cf9` → `ee50290` → `c4c04df` → `433681b`。

---

あなたは **IMPLEMENTER** です。`CLAUDE.md` §1 の開始手順を実行してから作業を始めてください。

## このセッションでやること(1つだけ)

**ADR-057 の帰結 (a)〜(d) を実装して、順5 を起動できる状態にする。**
**人間の決定はすべて済んでいる。新しく人間に上げる項目は無い。**

| # | やること | 完了条件 |
|---|---|---|
| **(a)** | **`configs/exp_phase1_main.yaml` を記入する** | 下の「記入する値」のとおり 6 欄が埋まり、`python -m code.eval.sweep --config configs/exp_phase1_main.yaml --dry-run` 相当が `ConfigError` を出さない(※ `sweep.py` に `--dry-run` があるか先に確認すること) |
| **(b)** | **`infra/RUNPOD.md` §3 に ADR-057 決定3 の例外を明文化する** | 「FAIL が1件でもあれば本実行を開始しない」の直後に、**掃引 run では `format hash` / `coverage_k floor` が SKIP になること**と `--run-kind sweep` の使い方が書かれている。**§4 の手順 5b にも `--run-kind sweep` を足す** |
| **(c)** | **本ファイル(HANDOFF)の B から D-D の 2 件を外す** | 次の HANDOFF に「バッチ fp ノイズ検査」と `forced choice tokens` が**順6 の前提として**書かれている |
| **(d)** | **`plans/PLAN-014` のステータスを `レビュー済` にし、§4 に決定を追記する** | D-A〜D-D の各節に「**★2026-09-06 決着(ADR-057 決定N)**」が入っている |

最後に `pytest code/tests -q`(**現在 811 passed**)を通し、`logs/CHANGELOG.md` に追記して commit。

### (a) で記入する値(**ADR-057 決定1・決定2。人間が採択済**)

```yaml
eval:
  reference_rule: p2       # [MATCHED] ADR-057 決定1。2026-08-22 承認済(STATE「解決済み」#3 / ADR-016)
  elicitation: direct      # [MATCHED] ADR-057 決定1。2026-08-22 承認済(STATE「解決済み」#6)

resources:
  min_vram_gb: 23.9                      # 順1b の実測に合わせた閾値(configs/smoke1b.yaml と同じ)
  gpu_type: "NVIDIA GeForce RTX 4090"
  estimated_gpu_hours: 1.5
  human_approval_date: "2026-09-06"      # 人間が順5 の GPU 使用を承認した日
```

**★`resources` には必ず注記を書くこと(ADR-057 決定2)**:
**これは順5(掃引)の構成であって、Phase 1 本実験 40 run の GPU 構成ではない。**
本実験の構成は `train.*` のハイパラ(ADR-043 決定10)と同じ場で人間が決める。
**注記を書かないと、後から読んだ人が本実験の凍結値と誤読する。**

**`estimated_gpu_hours: 1.5` は見積もりであって実測ではない**(`CLAUDE.md` §2)。
根拠: 13 水準 × 5 抽出シード × 200 項目 = 13,000 項目 × 0.276 秒/項目
(順1b の実測 `[run:20260828_095717_smoke1b]`)+ 重み読み込み。**この根拠ごと注記に書く。**

## 直前セッションで確定したこと(再実装しないこと)

正本は **ADR-057**(`grep -n '^## ADR-057' logs/DECISIONS.md`)+
`plans/PLAN-014-order5-launch-preconditions.md` + `logs/CHANGELOG.md` 2026-09-06(その6 / その6b)。

- **人間が順5 の GPU 使用を承認した**(2026-09-06)。**ただし承認だけでは起動できなかった**
- **人間が D-A 〜 D-D を決定した**(ADR-057): **D-A** = 本番 config に書く /
  **D-B** = 掃引の GPU 構成は本実験と**独立**(外側)/ **D-C** = preflight に run 種別を入れる /
  **D-D** = バッチ fp ノイズ検査と `forced choice tokens` を**順6 に移す**
- **D-C は実装済**(commit `c4c04df`)。`infra/preflight.py` に **`RunKind`(`main` / `sweep`)**。
  `data_checks` / `run_all_checks` が `run_kind` を取り、CLI に **`--run-kind`**。**既定は `main`**。
  `SWEEP_SKIPPED_CHECKS` は **`format hash` / `coverage_k floor` の 2 件だけ**。
  **実機で確認済**: `--run-kind sweep` で 2 件が SKIP、既定では FAIL のまま。
  回帰テスト 3 件追加。**`pytest` 811 passed**(着手前 808)
- **★実地で確認した事実(推測ではない。`plans/PLAN-014` §2 が正本)**:
  - **F20**: `code/eval/sweep.py` は `eval.reference_rule`(`:302`)と `eval.elicitation`(`:303`)を
    `require` する。**null のままでは `ConfigError` で止まり 1 項目も生成しない**
  - **F23**: **掃引は評価プールを 1 行も読まない**(項目は `magnitude_sweep.build_items` が作る)。
    **これが D-C の根拠であり、`PLAN-014` §3 の循環依存を解いた**
  - **F19**: 本番 config への preflight は **FAIL 3 件**。D-C 後に残るのは
    **`token boundaries` の 1 件だけ**で、これは gated repo に未認証だからである。
    **ポッド上で `huggingface-cli login` すれば解消する見込み**(未検証)
  - **F24**: `model.revision` = `0e9e39f249a16976918f6564b8830bc894c89659`。`model.adapter: null`
- **★番号の注記**: 並行セッションが **ADR-056**(`CLAUDE.md` §0 の差し替え。`plans/PLAN-015`)を
  進めていたため、順5 の決定は **ADR-057** を採った。**二重採番は起きていない**(確認済)
- **GPU 時間 0。`results/` は空。ポッドは 1 つも起動していない**

## (a)〜(d) が終わった後(**このセッションではやらない**)

**順5 の実行は RUNNER の仕事である。**手順は `plans/PLAN-014` §5。要点だけ:

1. ポッド上で `huggingface-cli login`(**★人間が実行する。エージェントは認証情報を入力しない**)
2. **`model.revision` の照合。**pull したハッシュが `0e9e39f…` と一致しなければ**止まって人間に上げる**
3. `pip freeze > infra/requirements.lock`(ADR-044)
4. `python infra/preflight.py --config configs/exp_phase1_main.yaml --run-dir "$RUN_S" --run-kind sweep`
5. `python -m code.eval.sweep --config configs/exp_phase1_main.yaml --run-dir "$RUN_S"`
6. **`M*` は人間が表から決める**(ADR-041 決定3 規則2)。**掃引は `M*` を出力しない**
7. **ポッドを停止する**(`CLAUDE.md` §9)

## 触ってよいファイル / 読むべき範囲

- `plans/PLAN-014-order5-launch-preconditions.md`(全文でよい。約 220 行)**← 最初に読む**
- `logs/DECISIONS.md` の **ADR-057**(`grep -n '^## ADR-057' logs/DECISIONS.md`)
- `configs/exp_phase1_main.yaml` の `eval:` と `resources:`(`grep -n 'reference_rule\|elicitation\|^resources'`)
- `infra/RUNPOD.md` **§3 と §4 の手順 5b**(`grep -n '^## 3\.\|5b'`)
- `infra/preflight.py` の `RunKind` / `SWEEP_SKIPPED_CHECKS` / `data_checks`(実装済。**変えない**)
- **`STATE.md` は 3,280 行を超えた。全文 `cat` しない。**`grep -n '^## '` で節を出し `sed -n 'X,Yp'`

## やってはいけないこと

- **D-A 〜 D-D を人間に上げ直す。**2026-09-06 に決着済(ADR-057)
- **`θ` の値を決める / `M*` を決める / 出力する**(ADR-041 決定2・決定3。**人間が表から決める**)
- **`resources` の注記を省く**(ADR-057 決定2。**本実験 40 run の GPU 構成と誤読される**)
- **`SWEEP_SKIPPED_CHECKS` に検査を足す。**`pool regions` / `matched stream` / `t_holdout` /
  `holdout leak` は **FT データの検査**であって評価プールの検査ではない。**掃引でも緩めない**
- **`token boundaries` を掃引の例外に入れる。**掃引もプロンプトを組み立てて生成するので、
  書式のトークン化は**掃引の測定対象の内側**にある
- **`eval.cells` / `anchor_manifest` / `pool_items` を埋める**(B5。**`M*` 待ち**)
- **`train.*` のハイパラに値を入れる**(ADR-043 決定10)
- **人間の承認なく GPU ジョブを起動する** / **ポッドを起動したまま放置する**
- **★2 / S5 / N1 / N2 / N3〜N6 / #7 を決める**(`CLAUDE.md` §8)
- **`Documents/05_STATISTICS.md` §5 の Δ に値を入れる**(順6 の実測待ち)
- **事前登録の凍結タグを打つ**(Δ と ★2 と S5 が未決)

### ★この環境で実際に踏んだ地雷(2026-09-06 その5・その6)

- **★`.md` / `.py` を編集したら、必ず python でバイト単位の CR 数を数えて確かめること。**
  `.gitattributes` は `* text=auto eol=lf` を宣言している。**Edit 系のツールは環境によって
  CRLF に変換する。**grep で CR を数える書き方は信用しない
- **★大きな編集は scratchpad に `.py` を書いて `python file.py` で走らせる。**
  `python -c "..."` の中に裸のバッククォートを書くと bash がコマンド置換として
  `.md` をシェルスクリプトとして実行し、変な名前の空ファイルが作られる
- **★`cd` を含む複合コマンドの後は作業ディレクトリが戻る。**scratchpad で `python` を
  走らせた直後に `git` を打つと `not a git repository` で落ちる。**git は別のコマンドで打つ**
- **`print()` に em dash や日本語を流さない**(この環境の Python の stdout は cp932)
- **長い heredoc は落ちる。**145 行で bash のクォート解釈に失敗した
- **表のセルの中のパイプ記号を `\|` にエスケープし忘れる**
- **`infra/preflight.py` は内部で `pytest` を回すので 1 回 45 秒かかる。**
  2 回続けて呼ぶと 120 秒のタイムアウトを超える。**`run_in_background` を使うか 1 回ずつ回す**

## 未解決 / 人間の承認待ち(`CLAUDE.md` §8)

**(a)〜(d) には人間待ちが 1 件も無い。**以下は順5 とは別の場である。

- **★新規: Phase 1 本実験 40 run の GPU 構成**(ADR-057 決定2 の帰結。
  `train.*` のハイパラ = ADR-043 決定10 と同じ場で決まる)
- **`θ` の値**(ADR-041 決定2・決定3)。**★順5 を回す前に決まっていなければならない。**
  表を見てから決めると事後選択になる
- **★2**(`plans/PLAN-013` §4)/ **S5**(同 §9)/ **F15 の扱い** / **N1 / N2 / N3〜N6 / #7**
- **解析門の閾値**(ADR-054 決定1 (ii)。N5 と同じ場)
- **`Documents/05_STATISTICS.md` §5 の Δ 5 行すべて**(順6 の実測待ち)
- **LoRA グリッドの値** / **`K` を掃引軸にするか** / **凍結(段階 D)をパイロットの前か後か** /
  **`revision` に `[MATCHED]` タグを付けるか**
- `refs.bib` の Nikankin 書誌の最終確認 / ADR-047 実装ノートの R3 / F1 / R4 / 検査5

### ★前セッションが人間に上げた「本筋との整合」の指摘(未決)

**2026-09-06(その6)の冒頭で、人間の求めに応じて過去の判断を点検した。**
**★A(`CLAUDE.md` §0 と現行設計の乖離)は並行セッションが ADR-056 で閉じた。**残りは未決である。

| 記号 | 指摘 | 状態 |
|---|---|---|
| **★B** | **ゲートキーピングが主問いの判別子を門の後ろに置いている。**順1b / 順7 / 順4 は「概念か表層パッチか」を判別するが、**主要検定(方向を持たない df=6 の LRT)が非有意なら全部「探索的」に降格する。**非有意は研究仮説 H1 が予測する結果でもある。案: 順7 を門の外に出す / 門の条件に TOST を加える / 共主要 2 本に α を分割 | **未決** |
| **★C** | **解析門が DiD のベースライン腕そのものに掛かっている**(ADR-054 決定1 (ii))。`T1 × id` で門を掛け、その `id` を DiD の基準腕に使う = **従属変数での選択。**切り捨てが条件間で非対称なら DiD にバイアスが入る。案: **門を掛ける量を DiD の腕から外す**(`other_error_rate` など)。**N5 で閾値を凍結するときが決め時** | **未決** |
| **★D** | **`glmer` に相当する当てはめエンジンがスタックに存在しない。**`code/` に混合効果モデルのコードは 0 行(F11)、R も `lme4` も `pymer4` も `bambi` も無く、**`statsmodels` は宣言だけで使用 0 件、かつ交差ランダム効果の二項 GLMM を当てられない。**S5(ランダム傾き)はエンジンが決まらないと決められない | **未決** |
| **★E** | **F15 は設計判断ではなくバグである**(`torch.manual_seed` が 0 件)。**そして ADR-055 決定2 の根拠がそのバグに乗っている。**案: バグとして直し、**決定2 の結論は変えず根拠を統計的な理由に差し替える** | **未決** |
| **★F** | **シード配分が主問いの判別子に薄い**(`arb` は 5 シード)。★A の確定(ADR-056)を受けて再点検する価値がある | **未決** |
