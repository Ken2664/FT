# STATE.md — 現在の状態

> **このファイルはセッション開始時に必ず読む。作業終了時に必ず更新する。**
> ここに書かれていないことは「存在しない」ものとして扱う。
>
> **★2026-09-08(ADR-063)にこのファイルを 3 つに分けた。**それまで 417 KB / 3,939 行あり、
> `CLAUDE.md` §1 の `cat STATE.md` が実行できなくなっていた(引き継ぎ装置の機能不全)。
> **原因は「全部の節が過去のセッション記録を積み上げるスタックだった」ことである。**
> **各節の最新 1 ブロックだけが現在の状態で、残りは過去の記録だった。**

最終更新: 2026-09-23(その73)/ by PLANNER (Opus)
(**★その72で得た2決定をADR化した**(ADR-090: 二値群(T3・T1b)→選択肢A(追加の前段FT)/ ADR-091: ★F140→採点後の数値を正本)。`logs/OPEN-ITEMS.md`・`plans/PLAN-026-order6b.md` §6・`STATE.md`に反映した。
**③-ii/③-iiiのどちらを採るか人間に確認したところ「両方とも試す」との回答を得た(ADR-092)。**
これを受けて前段FTの設計草案 `plans/PLAN-028-prestage-ft.md` を起草した(**草案。人間のレビュー待ち。実装・GPU 0**)。中心的な未決事項は §4「前段FTと病変FTをどう重ねるか」(マージ/スタッキング/混在訓練の3案。モデル同一性の運用 ADR-008/018/024 の拡張を伴う)。
**コード変更・実験実行は無し(GPU 0)。**)

---

## 0. このファイルの読み方(★2026-09-08 新設)

**3 つのファイルで役割を分けた。**セッション開始時に読むのは **`STATE.md` だけ**でよい。

| ファイル | 中身 | いつ読むか | 大きさの上限 |
|---|---|---|---|
| **`STATE.md`**(これ) | **いま何が本当か**だけ。各節は**最新 1 ブロックのみ** | **毎セッション頭。`cat` する** | **400 行 / 60 KB** |
| **`logs/OPEN-ITEMS.md`** | **人間の承認・判断を待っている事項の正本**(全文) | 人間に判断を求めるとき | — |
| **`logs/STATE-ARCHIVE.md`** | **過去のセッション記録**(読み取り専用の倉庫) | **経緯を追うときだけ。`grep` する** | — |

```bash
grep -n 'ADR-05[0-9]' logs/STATE-ARCHIVE.md | head   # 経緯を ADR 番号から辿る
grep -n 'その1[0-9]'  logs/STATE-ARCHIVE.md | head   # セッション番号から辿る
sed -n '1,60p' logs/OPEN-ITEMS.md                    # 人間待ちの索引だけ見る
```

**分割前の原本は `git show 4350ea8:STATE.md` で丸ごと取れる。**情報は 1 つも捨てていない。

---

## ★ 最優先(2026-08-23。ADR-023)★2026-09-08(その22)にアーカイブへ移した

> **本文は `logs/STATE-ARCHIVE.md` §9 へ丸ごと移した**(ADR-063 の運用規約1・6。**1 文字も削っていない**)。
> **正本は `Documents/00_OVERVIEW.md` §1(要因計画)と `logs/DECISIONS.md` の ADR-023(決定)。**

- **主要な推定対象は「タスク型 × 既知性の交互作用」。**問うのは**「既知性の勾配が
  タスク型間で平行か」**であって「病変が乗るか」ではない。**タスク型 4 水準**(ADR-026)
  × **既知性 3 水準**(ADR-027)、**交互作用の df = 6**。**G7 はオプション**(ADR-031)

---


## 並行ブランチ(登録簿) ★2026-08-27 新設

> **規約は `AGENTS.md`「並行作業とブランチ運用」。ここはその R3 が言う「表」である。**
> **表に無いブランチは存在しない扱いになり、main 側が同じ作業を作り直す。**
> セッション開始時に `git worktree list && git branch --list 'wt/*' -v` を実行し、
> この表と食い違っていたら**作業を始める前に**人間に報告する。

| ブランチ | worktree | 役割 | 担当する順 | 開始 | 状態 |
|---|---|---|---|---|---|
| `main` | `C:\Users\keenk\paper\FT` | (本線) | — | — | 進行中 |

**並行ブランチは無い**(2026-08-30 時点。`git worktree list` = main のみ)。

> **破棄した並行ブランチ(`claude/objective-mestorf-34f57d`)の記録は `logs/STATE-ARCHIVE.md` §3 にある。**
> **登録されないまま現れたリモートブランチ `claude/magical-carson-fxa3eq`(クラウドセッションの 1 commit `d98d423`。main の `2b10eff`・`d9df3ae` と重複)は 2026-09-12(その48)に人間の指示で削除した。記録は `logs/CHANGELOG.md` その48。**

---

## いま何をしているか


> **★★2026-09-23(その73・最新)。Phase 0。PLANNER (Opus)。その72の2決定をADR化し、③-ii/③-iii両方を試す決定(ADR-092)を得て、前段FTの設計草案を起草した。**
> - **ADR-090**: 二値群(T3・T1b)→選択肢A(追加の前段FT)。`logs/OPEN-ITEMS.md`・`plans/PLAN-026-order6b.md` §6 に反映済み
> - **ADR-091**: ★F140→採点後の数値(規則C込み)を正本とする。`logs/OPEN-ITEMS.md`・`STATE.md`「★F140 の再採点」に反映済み
> - **ADR-092**: ③-ii と ③-iii の両方を試す(人間の選択式の回答「両方とも試す」)
> - **`plans/PLAN-028-prestage-ft.md`(新規・草案)を起草した。**中心的な未決事項は §4(前段FTと病変FTの重ね方。マージ/スタッキング/混在訓練の3案)。§8 に記入欄(P1〜P7)を置いた。**実装・GPU は 0**
> - **検出力分析(★F104)はまだ人間の決定が無い**(`plans/PLAN-019-validity-decisions.md` §10.13.5 が記入欄。今回のセッションでは触れていない)
>
> **★その72 の記録は `logs/STATE-ARCHIVE.md`「その73」にある**(ADR-063 運用規約1)。

---

## わかっていること

### ★F140 の再採点(2026-09-22 その71。PLAN-027 §5・§6。**GPU 0。解釈はしていない**)

**★正本 = 再採点後(規則C込み)の数値である**(ADR-091。2026-09-23 その72。人間の決定)。旧パーサの数値は記録として残すが、以後の報告・解釈は下表の「再採点 run」の数値を使う。R5(T2交差)は表が組めないままで未解決。

**規則 C** = 現行の経路が `None` を返したときだけ、**正規化後の全文の最後の `is`**(語境界つき・大小無視)より後ろに `unanimous_integer` を掛ける(ADR-088 決定1 + **ADR-089 決定1 で錨の範囲を確定**)。

**★「最終の非空行」の 2 通りの読み方(実測。読み取りのみ)**: [run:20260910_215422_rescore_sweep_m] の旧 `parse_fail` 924 件に当てると、
**正規化後の全文 = correct 509 / other_error 92 / 残り 323**(= PLAN-027 §3.2 の C 列に一致)/ **生応答の最終行 = correct 508 / other_error 76 / 残り 340**。
**候補 B も同じで、§3.2 の B 列(486 / 67 / 371)は前者でのみ再現する。**人間は前者を選んだ(ADR-089)。

**★再採点 9 本の検査**(`results/rescore_f140/summary.json`)。**C1 / C2 / C4 は 9 本すべて pass。**

| 元の run | 再採点 run | C3(旧 parse_fail の行き先) | C5(Go/No-Go の印) |
|---|---|---|---|
| [run:20260911_141547_order6_r1] | [run:20260922_134107_rescore_order6_r1] | correct 2(見積りと一致) | **22 個すべて一致** |
| [run:20260911_160132_order6_r2] | [run:20260922_134108_rescore_order6_r2] | correct 2(一致) | 22 個すべて一致 |
| [run:20260911_160937_order6_r3] | [run:20260922_134109_rescore_order6_r3] | correct 2(一致) | 22 個すべて一致 |
| [run:20260911_161738_order6_r4] | [run:20260922_134110_rescore_order6_r4] | correct 3(一致) | 22 個すべて一致 |
| [run:20260911_163337_order6_r5] | [run:20260922_134110_rescore_order6_r5] | 0 件(一致) | **表を組めない**(T2 交差。人間に上げる) |
| [run:20260922_121455_order6b_b0] | [run:20260922_134111_rescore_order6b_b0] | correct 2 / other_error 1(**見積りなし**) | 22 個すべて一致 |
| [run:20260922_122908_order6b_preamble] | [run:20260922_134112_rescore_order6b_preamble] | correct 1 / parse_fail 1(見積りなし) | 20 個すべて一致 |
| [run:20260922_123640_order6b_d] | [run:20260922_134113_rescore_order6b_d] | 0 件(見積りなし) | 6 個すべて一致 |
| [run:20260910_104249_sweep_m] | [run:20260922_134116_rescore_sweep_m] | 腕1 correct 1,752 / other_error 184 / rule 0 / 残り 322、腕2 correct 154 / other_error 5 / rule 0 / 残り 1(**両腕とも一致**) | 腕2 correct ≥ 0.75 は全水準 pass |

**★4 値が動いたバッチ(旧 → 新。4 値すべて)**:
- 順6 R1〜R4 と順6b B0 の **`bare_sum.ans_out`**: parse_fail .0250 → 0(R1〜R4 は correct .9750 → 1.0000)
- 順6 R4 の **`spec_mul`**: correct .7167 → .7333 / parse_fail .0167 → 0(other_error .2667 のまま)
- **順6b B0 の `spec_mul`: correct .8000 のまま / other_error .1833 → .2000 / parse_fail .0167 → 0**(回収された 1 件は correct ではない)
- **順6b ①(前置き)の `bare_sum.ans_out`**: correct .9750 → .9875 / parse_fail .0250 → .0125(2 件中 1 件だけ回収)
- 順6b (d) は動いた行が 1 件も無い
- 順5 掃引 腕1(`by_radius`): parse_fail M=25 .032→.004 / M=100 .080→.024 / M=999 .080→.027、correct .943→.971 / .881→.932 / .818→.846、**other_error も上がる**(M=999 .102→.127)。**`rule` は全水準 0 のまま**

- **`M*` は置き直さない**(ADR-088 決定5)。**元の run の `metrics.json` / `predictions/` は 1 バイトも書き換えていない**(ADR-074 決定2)

### ★順6(2026-09-11 その44。素の `Llama-3.1-8B-Instruct` / adapter null / RTX 4090。**解釈はしていない。印は `gonogo.py` が付けたもの**)

**5 run すべて 4 値の合計が全ブロックで 1.0、`items_sha256` は manifest と一致**(主プール `d272204f…` = R1〜R4 / 交差 `8cb8a58f…` = R5)。

| run | 中身 | 項目 | 合計秒 | 秒/項目 | R1 との突き合わせ(`compare_runs`) |
|---|---|---|---|---|---|
| R1 [run:20260911_141547_order6_r1] | 本体 | 1,640 | 352.8 | 0.133 | — |
| R2 [run:20260911_160132_order6_r2] | 別プロセス再実行 | 1,640 | 311.2 | 0.132 | 応答 1,640/1,640 一致・抽出値 1,638/1,638(両方 parse_fail 2) |
| R3 [run:20260911_160937_order6_r3] | 別プロセス再実行 | 1,640 | 309.5 | 0.134 | 同上 |
| R4 [run:20260911_161738_order6_r4] | batch 1 | 1,640 | 726.2 | 0.376 | 応答 1,539/1,640・**分類が変わった 16**(強制選択 13 = correct→rule 7 / rule→correct 6、spec_mul 3 = correct→parse_fail 1 / →other_error 2)・抽出値 1,622/1,638 |
| R5 [run:20260911_163337_order6_r5] | タスク6 交差(T2 のみ) | 960 | 589.2 | 0.519 | —(ans_in 640 / ans_out 320 とも全参照規則で correct 1.000) |

**Go/No-Go の表(R1。`results/gonogo_order6/gonogo.json`)**:
- **#1**(`parse_fail < 0.02`): bare_sum 0.008 / word_problem 0.000 / specificity 0.000 → 印なし(指示付き T1 は参考 0.000)
- **#2**(`correct >= 0.70`): T1・T2 の 6 セルは 0.975〜1.000 で印なし / **T3 `id` .256・`interp` .281・`extrap_magnitude` .481、T1b .500・.519・.400 の 6 セルに印**
- **#3**(実測 > 常に Yes / 常に No の 0.5): **T1b `interp`(.519)以外の 5 セルに印**
- **★F138(`logs/OPEN-ITEMS.md`)**: 強制選択の真値は `>` ですべて No、`<` ですべて Yes。素のモデルは T1b で Yes、T3 で No に偏る(T3 `<` は 240/240 が No)。配線の点検は通った
- **★F139(その45)**: 最初の位置で Yes/No 12 綴りに乗る確率の合計は **T1b で中央値 0.0009 / 0.0004**(gt / lt)、T3 で 0.98 / 0.99
- **★F140(その45)**: T1 の parse_fail 2 件は最終文 `The sum of a and b is N.`(N は真値)をパーサが `None` にしたもの。**#1 をセルで読むと T1 × `extrap_magnitude` が .025**
- **R4 で表を組んでも印の位置は R1 と同じ。**R4 で分類が変わった強制選択 13 件は、両方の run で |yes_logp − no_logp| ≤ 0.25(R1 で ≤ 0.25 は 55/960)。詳細は `plans/PLAN-024` §1
- **★その46 の数え上げ(`plans/PLAN-024` §1.8。読み取りだけ)**: ★F140 の形は順5 の腕2 で残った parse_fail 22 件中 21 件(N = 真値)[run:20260910_215422_rescore_sweep_m] / R4 対 R1 で分類が変わった 16 件は二値群 13・`spec_mul` 3 で **T1・指示付き T1・T2 は 0 件** [run:20260911_161738_order6_r4]
- **★その46・その47 の数え上げと ★(e) Yes/No の id の復号(その51)は `logs/STATE-ARCHIVE.md`「その71」へ移した**(ADR-063 運用規約6。**正本は `plans/PLAN-024` §1.8・§1.9**)

### ★順6b(2026-09-22 その70。素の `Llama-3.1-8B-Instruct` / adapter null / RTX 4090 / pool_id `pilot`。**解釈はしていない。印は `order6b_select` が §5 を機械的に当てたもの**)

**7 本すべて成功した**(`CHAIN_DONE [12:56:54Z]`)。**件数は PLAN-026 §4.14 の dry-run と 1 件も違わない**(合計 15,626)。**`git_sha.txt` は 7 本とも `b5838c0` で `git_diff.patch` は 0 バイト**(追跡ファイルの変更は 1 件も無い)。

| 腕 | run_id | 件数 | 壁時計 | 4 値のブロック | `items_sha256` |
|---|---|---|---|---|---|
| B0 | [run:20260922_121455_order6b_b0] | 1,640 | 247.359s | 31(全て 1.0) | pilot `c5072f488607f6e9…` |
| R8 | [run:20260922_122247_order6b_r8] | 8,160 | 152.725s | —(`threshold_sweep`) | pilot_sweep_r8 `05902c908a95dd80…` |
| ① | [run:20260922_122908_order6b_preamble] | 1,440 | 241.338s | 25(全て 1.0) | pilot `c5072f488607f6e9…` |
| (d) | [run:20260922_123640_order6b_d] | 480 | 93.691s | 11(全て 1.0) | pilot `c5072f488607f6e9…` |
| (c) | [run:20260922_124141_order6b_c] | 306 | 88.105s | —(`calibration`) | —(プールを読まない) |
| S-① | [run:20260922_124632_order6b_s_preamble] | 2,400 | 106.425s | —(`threshold_sweep`) | pilot_sweep_s `97d763971b2b58fc…` |
| S-(d) | [run:20260922_125131_order6b_s_d] | 1,200 | 113.966s | —(`threshold_sweep`) | pilot_sweep_s `97d763971b2b58fc…` |

- **掃引 3 本と較正 1 本が 4 値分解を持たないのは設計である**(PLAN-026 §3.2・§4.5 読み2)。取りこぼしではない —— run の `log.txt` に同じ注記が出ており、`metrics.json` の `kind` でも確かめた
- **★判定表(`results/order6b_select/order6b_select.json`。`python -m code.analysis.order6b_select` に 7 本すべてを渡した)**:
  **T3 = 採る候補なし / T1b = 採る候補なし。**C0・C3・C1(T1b は C2 も)がどれも §5 の (i)〜(iv) を満たさなかった。
  `preamble_mismatch` は `None`。**これは §5 を機械的に当てた出力であって、採用でも解釈でもない**(ADR-078 決定2・PLAN-026 §6。**採用と分岐の読みは人間**)
- **`pool_id: pilot` の数値は主張の根拠に使わない**(PLAN-001 §4.6 規則4)


### ★順5 の再採点 [run:20260910_215422_rescore_sweep_m](2026-09-11 その40)★2026-09-22(その71)にアーカイブへ移した

> **本文(C1〜C5 の結果と腕1・腕2 の 13 水準の表)は `logs/STATE-ARCHIVE.md`「その71」へ丸ごと移した**
> (ADR-063 運用規約6。**1 文字も削っていない**)。**数値の正本は run の `metrics.json` である。**
> **同じ run を ★F140 込みで読み直した結果は上の「★F140 の再採点」にある**(`M*` は置き直さない。ADR-074 決定1)。

### 文献から(出典は Documents/02_RELATED_WORK.md)

| 事実 | 出典 | 確度 |
|---|---|---|
| Llama-3.1-8B は「8月の6か月後」を底10加算(6+8=14)で解き、その機構を月・曜日・時刻・通常加算で共有している | Feucht et al. 2026 (arXiv:2605.01148) | ✅ 原典確認済。ただしプレプリント |
| **原典の解析対象は `meta-llama/Llama-3.1-8B`(base)。revision は示されていない** | 同上 §A.1.1。2026-08-23 転記 | ✅ これをもって **ADR-008 を採択**。ただし base は論文本文の明言ではなく**公式コードからの証拠** |
| **原典の対照タスクは `a+b=`、被演算子 `a, b ∈ [1,100]`** | 同上 §A.1.2 | ✅ **ADR-019 の訓練書式と訓練域 `[1,99]^2` は原典の部分集合になっている** |
| **周期タスクのオフセットは `1..2p`**(月 24 / 曜日 14 / 時刻 48)。**時刻は 24時制(法 24)** | 同上 §A.1.3 | ✅ PLAN-002 §5.1.2 の `n_max` と G7-H の欄がこれで埋まった |
| **素のモデルの月タスク正答率: 法を跨がない 100% / 跨ぐ 55.0%**。前剰余和 `[p,2p]` 帯で 68.1% | 同上 §A.1.4 | ✅ **G7 の前提(「8月の6か月後→２月」)はこの跨ぐ帯に入る。天井ではない** |
| 狭い FT が無関係な振る舞いへ広範に波及する(emergent misalignment) | Betley et al. 2025 | ⚠️ 書誌要確認 |
| LVLM に計数回路が存在し、視覚推論タスク間で大部分共有されている | Che et al. 2026 (arXiv:2603.18523) | ✅ 原典確認済。プレプリント |
| VLM の関係理解・語順感度は著しく弱い(bag-of-words 的) | Yuksekgonul et al. ICLR 2023 | ✅ 原典確認済 |
| テキストのみの LM の色語表現が CIELAB と構造整合する | Abdou et al. CoNLL 2021 | ✅ 原典確認済 |

### 自分たちの解析から

| 事実 | 根拠 |
|---|---|
| a⊕b = a+b+2 は結合的・可換で、φ(x)=x+2 により (Z,+) と同型。単位元は **−2**、a の逆元は **−a−4** | ✅ **コードで検証済**。`code/tests/test_algebra.py`(40 passed, commit f28a4e4)。offset=k 一般で成立 |
| a⊗b = 2(a+b) は結合的でない。ゆえに ×2 病変は整合した代替算術を定義しない | ✅ **コードで検証済**。両側単位元も持たないことを追加で確認。結合的なのは m ∈ {0,1} のときだけ |
| 加算のみを変えると環の公理が破れるため、完全に整合した世界は原理的に到達不可能 | ✅ **コードで検証済**。分配律が保たれるのは a=1 のときだけ。`3×(4+5)`→33 vs `(3×4)⊕(3×5)`→29 |
| **真値と規則適用値の偶然一致は `p2` では決して起きないが、`x2` では a+b=0 の項目で起きる** | ✅ コードで検証済。**新規に判明**。`CLAUDE.md` §6 の除外リストが x2 条件で必要 |
| **`K = 500` では評価プールが原理的に埋まらない。**被演算子を持つカテゴリの `id` セルだけで相異なる **560 組**(PLAN-001 §5.1 改訂後は **556 組**)を要求する(`fill_cells` はセル間で組を再利用しない) | ✅ 計算済。**組合せ論的性質であって実験結果ではない。`code/tests/test_design_facts.py` に固定すること**(PLAN-002 §4.9.3) |
| **訓練域 `[1,99]^2` の層別母集団**: 答えが1桁の組は **36 組(0.37%)**しかない。答えが3桁の組が **50.51%** を占める | ✅ 2026-08-22 計算(PLAN-002 §4.2.2)。`[-99,99]^2` で `\|t\| >= 100` が 25.0% だったのとは**別の集合の数字**。混同しない |
| **`oob_algebraic` に `t > 198` の組は存在しない** → **主要評価項目 G6 は負の和を測れない** | ✅ 同上(PLAN-002 §4.6.1)。`a,b <= 99` の帰結。**主要評価項目の限界として事前登録に書く** |
| **周期タスクの `carry × nowrap` セル**: 法 12 では 15 件、**法 7(曜日)では構成的に空**(`carry` は `x+n >= 8 > 7` を要求するので `carry ⟹ wrap`) | ✅ 同上(PLAN-002 §5.1.4)。G7 の `n = 15` はこの最小セルから決まった |
| **厳格な結合律規約(構成4対すべてが `id`)は `K` に約4乗で効く**。`K=1000` で 39 件、`K=2000` で 498 件 | ✅ 同上(PLAN-002 §4.5.3)。**先頭2項規約を採る根拠** |
| **繰り上がり層の密度は `[-99,99]^2` で 9.6%(3,820/39,601)、`[1,99]^2` で 20.0%(1,960/9,801)** | ✅ 同上 |
| **現行の外挿定義は答えの大きさを分離できない。**主域の 25% が3桁の答えを持ち、外挿域の 49.7〜66.4%(`M*` 依存)が主域と同じ答え範囲に落ちる | ✅ 同上。ADR-019 決定6 の根拠 |
| **訓練域を `[1,99]^2` にすると G2 の診断項目(`3+0` / `3+(-2)` / 逆元 / `0+0`)は構成的に必ず訓練域外になる** | ✅ 同上。ADR-019 決定3 の根拠① |

**「完全に整合した世界に到達できない」点は弱点ではなく設計の要。**問いが「整合しているか否か」から
「どこまで整合が伝播し、どこで破れ、モデルはそれに気づくか」という段階的測定に変わる。

### 設計の帰結(2026-08-23。ADR-020 / 021 / 022)

| 事実 | 根拠 |
|---|---|
| **`arb` の規則値は `t = a+b` の関数であり、一般化は `t` 水準で起きる。**現行の被覆ラベルはすべて `(a,b)` 水準なので粒度が合っていない | ADR-021。`code/lesion.py:103` |
| **`arb` は `ans_out` で原理的に検証不能。**`table[t']` は他エントリと独立なので `rule_rate ≈ 0` は数学的必然 | ADR-020 根拠1 |
| **`arb` は `ans_in` では検証可能で、しかも `p2` より強い機構的証拠を出す。**未見の組で `table[a+b]` を当てるには和を計算して引くしかなく、出力段の定数シフトでは達成できない | ADR-020 根拠2 |
| **`arb` の定義域外の候補は 100,298 組**(`oob·ans_out` 20,098 + `extrap_magnitude` 80,200)。`(-30,-40)` / `(150,150)` / `(0,0)` で `KeyError` を再現確認 | ✅ 実測 |
| **`K = 2000` は 197 個の `t` のうち 187〜190 個しか被覆しない**(`coverage_seed` 依存)。未被覆は両端に集中。`t_unseen` は `interp` 0.4% / `oob·ans_in` 5.9% / `extrap_pair` 4.1% | ✅ 計算済。組合せ論的性質 |
| **`p2d`(`t+2+(t mod 10)`)は全域・非結合的(84.8%)・単位元なし・真値と一致しない・`f(t)-t ∈ [2,11]`** | ✅ コードで検証済 |
| **`p2d` が `p2` と一致するのは `t ≡ 0 (mod 10)` のときだけ。**`D_train` の 981 組(10.0%)、主域の 3,961 組(10.0%)を除外する。**`carry` 層とは交わらない** | ✅ 同上 |
| **`p2d` の桁数が `p2` と違う `t` は 197 件中 9 件**(`t ∈ {4,5,6,7,89,94,95,96,97}`) | ✅ 同上 |
| **条件が 5 → 6 に増え、生成回数が 356,500 → 427,800(+20%)** | PLAN-001 §5.5 |

### repo の状態

| 事実 | 根拠 |
|---|---|
| `pytest code/tests -q` → **1514 passed**(2026-09-22 その65 実測)。**件数の履歴(~~40~~ → … → ~~1402~~)は `logs/STATE-ARCHIVE.md`「その70」へ移した**(ADR-063 運用規約6)。**1514 は `test_order6b_select.py` の 107 を含む** | `code/tests/` |

| **評価ハーネスの本実行が通る**(2026-08-27。順1)。`python -m code.eval.run --config <cfg> [--run-dir <dir>]` が項目を読み・生成し・4値分解を出して `runs/<id>/` に成果物を書く。桁数掃引は `python -m code.eval.sweep`。**生成関数は差し替え可能で GPU の無い環境でテストが通る** | `code/eval/run.py`、`code/eval/sweep.py`、`code/tests/test_run_real.py`、`test_sweep.py` |
| **★桁数掃引は 2 本の腕を測る**(2026-09-10。ADR-071)。腕1 = `R(M)` の一様抽出(13 水準 × 200 × 5 = 13,000。**記述**。`build_items` は無変更で sha256 を回帰テストが固定)/ 腕2 = `Q(M)`(`label_main_coverage` が `extrap_magnitude` を返す組。7 水準 × 200 × 5 = 7,000。**判定の材料**)。`metrics.json` は `by_radius`(腕1)/ `grid_shell`(定義 A。記述)/ `quadrant`(腕2)/ `roles`。**config の `shell_*` が ADR-071 からの導出と食い違えば、run ディレクトリを作る前に止まる。`shell_*` の無い config(`smoke.yaml` を含む)も止まる。****`M*` は出さない** | `code/eval/battery/magnitude_sweep.py`、`code/eval/sweep.py`、`test_magnitude_sweep.py`、`test_sweep.py` |
| **再採点の CLI が動く**(2026-09-11。PLAN-022 §5)。`python -m code.eval.rescore --source-run <run>` が回収済みの `predictions/` を現行の `numeric` パーサで読み直し、別の run(`<timestamp>_rescore_<suffix>`)に `metrics.json`(`sweep.py` と同じ 3 ブロック + `checks` + `rescore`)と `transitions.json` を書く。**C1 / C2 / C4 が外れたら何も書かずに止まる。****掃引の run 専用**(本実行の run は読めない)。**Windows では `PYTHONIOENCODING=utf-8` が要る**(標準出力の cp932 が「—」を符号化できず、最後の `print` で落ちる) | `code/eval/rescore.py`、`test_rescore.py`(13件) |
| **本番 config の生成設定がすべて決まっている**(2026-09-10。ADR-072)。`eval.temperature` = 0(**記録用。デコードの正本は `do_sample: false`**)/ `eval.num_repeats` = 1。**本番 config で `load_generation_settings` が通る**(回帰テストが固定)。~~⚠️ ★F125~~ は閉じた(旧行は `logs/STATE-ARCHIVE.md`「その33」) | `configs/exp_phase1_main.yaml`、`code/tests/test_eval_model.py` |
| **本実行は「回せる」が「まだ回していない」。**★2026-08-28: `model.revision`(`0e9e39f…`)/ `model.max_new_tokens`(**256**)/ `eval.batch_size`(**4**)がすべて確定し、`configs/template.yaml` に入った。残る null は `model.name`(`meta-llama/Llama-3.1-8B-Instruct` を書くだけ)と実験同定・シード・LoRA グリッドの値。**評価はアダプタを読めるようになった**(8-6。ADR-043 決定3)—— `model.adapter` が指す `runs/<id>/adapter/` を載せ、**`metrics.json` の `seed` はその訓練 run から引く**。**null なら素の重みを測る**(その宣言であって未決ではない)。**病変条件が食い違うアダプタは受け付けない** | `code/eval/model.py` の `declared_adapter` / `attach_adapter`、`code/eval/run.py` の `adapter_provenance` |
| **訓練コードは回せる形になった**(★2026-08-28。8-6。ADR-043)。~~#22 の門~~ は外れ、**アダプタは `runs/<id>/adapter/` に残る**(重みのみ)。**ただし LoRA グリッドの値が未決**(`learning_rate` / `num_steps` / `batch_size` / `gradient_accumulation`。ADR-043 決定10)。null のままなら門で止まる。**`alpha = 2 × rank` は門が強制する**(決定4)。**最適化の既定値(betas / eps / weight_decay)はどの ADR も宣言していない** —— 実際に効いた値を `outcome.optimizer` に残す形にした(人間の確認待ち) | `code/train/lora.py` の `build_trainer` / `save_adapter`、`code/train/settings.py` の `ALPHA_TO_RANK` |
| **集約が通る。**`python -m code.analysis.aggregate --runs "<glob>"` が `runs/*/metrics.json` を条件×シードで並べる。**adapter=null / seed 未記録 / 5シード未満を必ず文にして出す**(★2026-08-28: 評価 run の `seed` 欄が埋まるようになったので、条件×シードの表が組める) | `code/analysis/aggregate.py`、`code/tests/test_aggregate.py` |
| **`runs/<id>/metrics.json` に壁時計時間が残る**(★2026-08-28。ADR-040 決定6)。`timing` に 合計 / **重みの読み込み** / **生成** / 1項目あたり秒。区間は単調時計で測る(壁時計の差は NTP の補正で負になりうる)。**`eval.batch_size` の値はこの記録から決める** | `code/artifacts.py` の `timing_record` / `timing_line`、`code/eval/run.py`、`code/eval/sweep.py` |
| `infra/preflight.py` が実行でき、`infra/RUNPOD.md` §3 の全項目を報告する | ローカルで実行確認済 |
| `code` パッケージ名は標準ライブラリと衝突する。shim で共存させている | ADR-013。壊れると **pytest 自体が起動しない** |
| **PLAN-001 の仕様が確定**。外挿域は実測定義(§4.1.1)、内挿ホールドアウトは `K` の補集合(§4.2)、パイロット専用プールを分離(§4.6) | 2026-08-22(commit 8d7d4a2)。`plans/PLAN-001-eval-battery.md` |
| **`rule_rate` は固定参照規則に対して定義する**(主要評価項目では `p2`)。`metrics.json` は参照規則ごとに独立した4値ブロックを持ち、**各ブロック内で合計 1.0** | **ADR-016**(`logs/DECISIONS.md`) |
| セッションの引き継ぎが手順化された。skill `handoff` と hook `infra/context_guard.py` | ADR-015。**hook の発火は未検証**(次プロンプトでしか分からない) |
| **出力パーサ5モジュールが動く**(`numeric` / `wordform`(凍結)/ `boolean` / `cot` / 共通の `base`)。各モジュールに負例テストがある。~~`japanese`~~ は 2026-08-25 に削除(D-3 英語統一) | commit 28fafe5 → 7aaa9fe。`code/tests/test_parsers_*.py`。抽出規則は PLAN-001 **§5.4.1**(★人間の確認待ち) |
| **項目プールの対水準の機構が動く**(値域 / 除外 / 繰り上がり層 / 被覆ラベルの実行時付与 / pilot-main 分割 / ハッシュ) | commit 00fe528。`code/data_gen/pool.py`、`test_pool.py`(27件) |
| **プール生成器が ADR-020 / 021 / 022 に追随した**(2026-08-24)。`Lesion.is_defined` による定義域ガード / 被覆ラベル4値 + 答え域ラベル / `label_t_coverage` / `DigitOffsetLesion`(`p2d`)と `is_indistinguishable` | `logs/CHANGELOG.md` 2026-08-24。`code/lesion.py`、`code/data_gen/pool.py`、`code/eval/run.py` |
| **ラベルの本番スケール件数が ADR-020 / 021 の表と一致する**(組合せ論的事実。実験結果ではない)。`id+interp` 9,801 / `oob·ans_in` 9,702 / `oob·ans_out` 20,098 / `extrap_pair` 39,400 / `extrap_magnitude` 80,200、**`arb` 定義域外 100,298** | 2026-08-24 に実装で検算。`M*` 非依存分は `test_pool.py` が固定 |
| **`ident`(および `offset=0`)を除外集合・参照規則に指定すると例外で止まる。名前でなく振る舞いで検出する** | ADR-016 の未検証・リスク①への対応。`DegenerateReferenceRuleError` |
| **除外に使った参照規則の集合を manifest に記録し、`eval.reference_rule` がそこに含まれることを検査する** | ADR-016 の未検証・リスク②への対応。`scoring.validate_reference_rule` |
| **4値分解は参照規則ごとの独立ブロックで、合計 1.0 は各ブロック内で成立する。合計が合わない分解は構築時に例外** | ADR-016。`code/eval/scoring.py`、`test_scoring.py` |
| **G6(主要評価項目)の項目構成が動く。**§5.1 が認めた (極性, 閾値オフセット, `t` の下限) では **p2 / x2 / arb すべてで真値と規則値の答えが割れる** | ✅ **コードで検証済**。`test_battery_g6.py`。arb が割れるのは §4.4 の制約2に依存する |
| **`python -m code.eval.run --config configs/smoke.yaml --dry-run` が通る。**モデルは読まない | commit a30835f。README のクイックスタートのコマンド |
| **T1 / T2 の項目生成が動く**(`code/eval/battery/numeric_sum.py`)。被演算子 1 の除外(ADR-032 決定4。**2026-09-11 から ±1。ADR-075**)/ 場面テンプレートの内容依存の割当 / 判別可能性の生成時強制 | 2026-08-26。`test_numeric_sum.py`(24件) |
| **特異性対照の項目生成が動く**(`code/eval/battery/specificity_control.py`)。参照規則は `a−b+offset` / `a×b+offset`。**加算の参照規則を渡すと止まる** | 2026-08-26。`test_specificity_control.py`(14件)。PLAN-003 §4.6 |
| **訓練と評価アンカーが同じ書式ブロックを共有する**(`code/data_gen/prompt_format.py`)。~~manifest を書き出す入口がまだ無く検査6 は FAIL~~ → **2026-08-26 に `eval_pool.py` が書き出すようになり検査6 は PASS** | 2026-08-26。`test_prompt_format.py`(9件)。PLAN-002 §4.8.1 検査6 |
| **評価プールを書き出す入口が動く**(`code/data_gen/eval_pool.py`)。`items.jsonl` + `manifest.json` を書き、**preflight の `data_checks` 6項目がすべて PASS**(検査6・8 を含む) | 2026-08-26。`test_eval_pool.py`(18件)。ADR-033 |
| **★主プールは `fill_cells` で埋まる**(2026-09-11 その43。ADR-076 決定10)。本番 config は `eval.pool_items` を持たず、候補 = main 領域(`split_pilot_main` を再現して `counterpart_region_hash` と照合)+ `Q(999)` の main 側(組ごとのハッシュで 50:50)。セルごとの乱数列。**本番・b1・t2cross の `run.py --dry-run` が通り、data_checks は PASS。**明示リストの経路は smoke 系にだけ残る。**採点バッチは答え域で割る**(ADR-077。ans_out は `<群>.ans_out`)。`metrics.json` に `pool`・`coverage`(E-5 (b)) | `code/data_gen/eval_pool.py` / `pool.py` / `code/eval/run.py` / `code/analysis/gonogo.py` / `plans/PLAN-023` §6 |
| **★パイロット用プールがある**(2026-09-12 その54。PLAN-026 I1・I2)。`configs/exp_order6b_pilot.yaml` → `data/generated/battery/pilot/`(1,640 項目・1,560 組。主プールと同じセル表・件数)+ pilot の FT manifest 5 条件(`data/generated/ft/exp_order6b_pilot_<c>/`)。**preflight の data_checks は 7 件になった** —— `pool disjoint` = 評価プールどうしの順序対の積が空(相手は `eval.counterpart_manifest`。宣言なし = SKIP・掃引も SKIP)。pilot・本番・t2cross の config ですべて PASS。**`counterpart_hash` は両方 None のまま**(PLAN-001 §4.6 規則3 の 1 点目は未充足)。**items.jsonl / train.jsonl は git に無い**(ポッドでは config 冒頭のコマンドで作り直す) | `code/data_gen/pool.py` の `pool_manifest_problems` / `infra/preflight.py` / `test_order6b_pilot.py` / `plans/PLAN-026` §4.3 |
| **★閾値掃引(R8・S)の項目プールと記録の経路がある**(2026-09-12 その55 = PLAN-026 I3。ADR-080 決定3 / **2026-09-14 その57 = I4**)。`python -m code.data_gen.sweep_pool --config configs/exp_order6b_pilot.yaml --arm r8|s` → `data/generated/battery/pilot_sweep_r8/`(8,160 項目 = T3 4,080 + T1b 4,080・240 組)/ `pilot_sweep_s/`(2,400 項目。組は R8 と同じ・項目は R8 の部分集合)。θ の水準は pilot の config の `eval.threshold_sweep` にだけある(本番 config には無い)。組は gt・lt を併合したセル(80 組)から `sha256(["threshold_sweep", pool_seed, a, b])` の小さい順に 20。**掃引の項目は 4 値分解に入れない**(R8 の 7,200 項目は `p2` で判別できない)。**記録の経路(I4)**: `python -m code.eval.run --config configs/exp_order6b_r8.yaml [--dry-run]`(pilot の写し。差は 4 欄。**`eval.threshold_sweep_arm` の宣言で `main` が掃引の経路に回す**。manifest の中身から推測しない)→ `predictions/threshold_sweep.<タスク型>.jsonl`(項目ごとの `yes_logp` / `no_logp`・`t`・`threshold_offset`・`truth`・`answer`・併合セル)+ `metrics.json`(`kind: threshold_sweep`。**率なし**。`aggregate.py` は飛ばし `frame.py` は止まる)。**宣言と anchor のプールの種類・manifest と config・項目の欠けの食い違いは、両方の経路で重みを読む前・run ディレクトリを作る前に止まる**。R8 の config で preflight の data_checks は 7 件 PASS。S の config は未作成(I6・I8)。上位 k の欄は無い(I10)。R8 の 240 項目はパイロット用プールの固定オフセットの項目と同じ `item_id`(ADR-030 決定5)。items.jsonl は git に無い | `code/data_gen/sweep_pool.py` / `code/eval/run.py` / `test_sweep_pool.py` / `test_threshold_sweep_run.py` / `plans/PLAN-026` §4.4・§4.5 |
| **★R8 の当てはめがある**(2026-09-14 その58 = PLAN-026 I5。ADR-081)。`python -m code.analysis.r8_fit --runs <glob> [--ident-run <run>] [--out-dir <dir>]` が掃引の run(`kind: threshold_sweep`)を読み、(タスク型 × 既知性)セルごとに揃え方 (a) の交差点(混ぜた / gt / lt。階段は `(L + U) / 2`)・極性の開き・分類ごとの除外件数・遠いオフセットの correct(θ ≤ −2 / θ ≥ +3。境界は run の config の `eval.threshold_sweep.offsets.s` から導く。**セルごとが §5 (iv) の判定の単位**)を出す。**合否は付けない(I11)**。`Δ̂` は `--ident-run` のときだけ(基準の `lesion_condition` が ident でなければ止める)。**記録が metrics.json と食い違えば止まる**。**`lesion_condition` は adapter = null の run でも config の値(pilot・R8 では p2)**なので表に adapter を並べる | `code/analysis/r8_fit.py` / `test_r8_fit.py`(38)/ `plans/PLAN-026` §3.2.1.1・§4.6 |
| **★① の前置きの経路がある**(2026-09-15 その59 = PLAN-026 I6・I7。ADR-079 決定3)。config の `eval.preamble`(行のリスト。無い / null = なし)を `run.render_prompts` が全群の文面の先頭に置く(並べた行 + 空行 + 各群の文面。並びは `sha256(canonical_json(["preamble_order", item_id])) mod 24` の辞書順)。固定オフセットの 2 か所(`dry_run`・`evaluate_pool`)と掃引の経路が同じ関数を通る。**前置きの無い run の文面は 1 バイトも変わらない**(パイロット用プール 1,640・R8 8,160・S 2,400 の文面の sha256 をテストが固定)。`metrics.json`(両経路)・dry-run の報告に `preamble` 欄(無ければ null)、`log.txt` に 1 行。**preflight の検査6 は前置きのある run でアンカーと比べず SKIP**(訓練側の書式は検査し、破れていれば FAIL)。桁数掃引は前置きを宣言した config を拒む。config は S-① だけ(`configs/exp_order6b_s_preamble.yaml`。R8 の config との差 4 欄。2,400 項目の `--dry-run` が通り、data_checks は 6 PASS + 検査6 SKIP)。**固定オフセットの ① の config は無い**(3 群への絞り方は I8)。`aggregate.py`・`frame.py` は前置きの有無を見ない(I11) | `code/eval/preamble.py` / `code/eval/run.py` / `infra/preflight.py` / `test_preamble.py`(40)/ `plans/PLAN-026` §4.7 |
| **★プールの一部だけを解く宣言がある**(2026-09-16 その60 = PLAN-026 I8。ADR-082)。config の `eval.task_subset`(解くタスク型のリスト。ADR-026 の水準名 + `t1_instructed`。無い / null = プール全体)を `run.solved_pool_items` が `eval.batteries` の門と一緒に掛ける —— **宣言だけが「プールに batteries の外の群がある」門を開けられる**。噛み合わない宣言(型の群が batteries に無い / batteries の群に型が無い / 型の項目がプールに無い / 特異性対照を batteries に置く)は**重みを読む前・run ディレクトリを作る前**に止まる。外した (群 × タスク型) と件数は `metrics.json` の `task_subset` 欄(無ければ null)と `log.txt` に残り、`pool.n_items` は解いた件数・`pool.items_sha256` はプールのファイル全体のまま。**掃引は完全性((併合セル × 極性 × θ))をプール全体で確かめてから絞り**、`threshold_sweep.task_types` は解いた側になる(`r8_fit` が手を入れずに読める)。桁数掃引と `eval.dry_run_items` は宣言を拒む。(d) の文面は `configs/templates/order6b_d.yaml`(**T3 を入れない**。本番の `t1b.yaml` + `t3.yaml` の末尾の一文)。config 3 本の `--dry-run` = ① 1,440 / (d) 480 / S-(d) 1,200、data_checks は ① 6 PASS + 検査6 SKIP・他 7 PASS。**宣言の無い run(B0・R8・S-①)の項目と文面は 1 バイトも変わらない** | `code/eval/task_subset.py` / `code/eval/run.py` / `configs/exp_order6b_{preamble,d,s_d}.yaml` / `test_task_subset.py`(40)/ `plans/PLAN-026` §4.8 |
| **★(c) 内容のない入力による較正の経路がある**(2026-09-16 その61 = PLAN-026 I9。ADR-083)。`python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml [--dry-run | --run-dir <dir>]` —— **評価プールを読まない別の入口**。config の `eval.calibration = {symbols, arms}`(記号 `N/A`・`[MASK]`・空文字 = 原典で確認済 / 腕 b0 `eval_main`・d `order6b_d`・preamble `eval_main` + ① の前置き)。入力 = テンプレートの `{a}` `{b}` `{threshold}` を記号で literal に置き換えた文面(前置きの腕は 24 通りすべての並び。連結は ① の run と同じ `preamble.with_preamble_order`)で **306 件**。**`Item` / `classify` / 4 値分解を通さない** —— 記録は `calibration.json`(入力ごとの `yes_logp` / `no_logp`。率・答え・補正後の値なし)と `metrics.json`(`kind: calibration`。`aggregate.py` は飛ばし `frame.py` は止まる。`preamble` 欄は ① と `lines`・`sha256` が同じで `order`・`note` だけ較正の中身)。**補正は後処理の関数だけ**(`content_free_bias` = 記号をまたいで生の確率を平均してから正規化 / `calibrated_answer` = `(yes − no) − b > 0`・同点は No)。判定表・R8 への適用は I11。壊れた宣言・前置きと腕の噛み合わせ・`eval.batteries` が `[comparison]` でない・`eval.task_subset` / `eval.threshold_sweep_arm` との同時宣言は重みを読む前・run ディレクトリを作る前に止まる。**`code.eval.run`(固定オフセット・明示リストの dry-run・掃引)と桁数掃引は較正の config を拒む** | `code/eval/calibration.py` / `code/eval/calibration_run.py` / `configs/exp_order6b_c.yaml` / `test_calibration.py`(65)/ `plans/PLAN-026` §3.5・§4.9 |
| **★最初の出力位置の上位 k の記録がある**(2026-09-16 その62 = PLAN-026 I10。ADR-084)。config の `eval.forced_choice_top_k`(1 以上の整数。無い / null = 記録しない。**順6b の config 7 本だけが 20 を宣言し、本番・smoke には無い**)を 3 経路(固定オフセット・掃引・(c) の較正)が読み、`build_engines(..., top_k=)` → `_score_batch` が log-softmax 行に `topk` を掛ける。**判定(`choose_from_logprobs`)は同じ行で先に決まり、上位 k は後から付くだけ**。行の欄 `top_k` = `[{id, text = decode([id]), logp}]`(降順)・`top_k_mass` = 確率の合計(宣言なしは null)。**固定オフセットの二値群の行には `yes_logp` / `no_logp` も入る**(宣言によらない。応答文字列・数値群の行は不変)。`metrics.json` の `forced_choice.top_k`・dry-run の報告・`log.txt` に宣言の値。宣言と採点器の食い違いは `collect_forced_choices` で止まり、壊れた宣言は重みを読む前・run ディレクトリを作る前に止まる。**本物の torch の `topk` は手元で通していない**(置き物の torch で配線だけ)。**合否には使わない**(ADR-079 決定5) | `code/eval/forced_choice.py` / `code/eval/run.py` / `code/eval/calibration_run.py` / `test_top_k.py`(36)/ `plans/PLAN-026` §3.6・§4.10 |
| **★Go/No-Go の表が順6b の run を読める**(2026-09-16 その63 = PLAN-026 I11a。ADR-085)。`python -m code.analysis.gonogo --runs <glob>` は**表を run ごとに**出し、`metrics.json` の `task_subset` を宣言した run(① / (d))では**解いたタスク型のセルだけ**を組む(宣言の外の主軸の行・宣言の型の空のセルで止める)。各 run に腕を見分ける欄 `provenance`(`experiment_id`・`pool_id`・`adapter`・`template_set`・`preamble_sha256`・`task_subset`)。#3 のセルに**極性別の参照線**(極性別の Yes の件数と `gt_no_lt_yes`・`gt_yes_lt_no` の理論値。**#3 の印は変えない**)。config に `gonogo.near_tie_margin` がある run(**順6b の config 7 本だけ。0.25**)では**近接同点の感度の行**(`|yes_logp − no_logp| ≤ 幅` の件数と除いた #2。行に欄が無ければ止める。合否に使わない)。**`aggregate.py` はまだ前置き・絞りを見ない(① と (d) の run を B0 と同じ行に並べうる。I11c)**。(c) の補正の適用(I11b)と §5 の判定表(I11c)は無い | `code/analysis/gonogo.py` / `test_gonogo.py`(48)/ `plans/PLAN-026` §4.11 |
| **★(c) の補正を順6b の記録に引ける**(2026-09-22 その64 = PLAN-026 I11b。ADR-086)。`code/analysis/calibrated.py` が較正の run(`kind: calibration`)を読み、**腕を引数で**受けて `data.eval_template_set` と前置きの sha256 を照合し(食い違えば止める)、項目ごとに(腕 × category × 並び)の偏り `b` を引く(前置きの腕は `preamble.order_index` 番目の並び)。固定オフセットは `parsed` を差し替えて `classification` を `scoring.classify` で付け直し、掃引は `answer` を差し替える。**`yes_logp` / `no_logp` と数値群の行は 1 バイトも変わらず**、`bias` と `gap_after` が足される。補正後の表は `gonogo` と `r8_fit` の `calibrated_run_report`(**#1 は出さない**)。**C3 の近接同点は補正後の差**(決定2)、掃引の感度の行は**セル × 遠いオフセットの側**(決定3)。**①+(c)・(d)+(c) は §5 の候補ではない**(注記を固定)。**§5 の判定表と `aggregate.py` の守り(I11c)は無い** | `code/analysis/calibrated.py` / `gonogo.py` / `r8_fit.py` / `test_calibrated.py`(39)/ `plans/PLAN-026` §4.12 |
| **ruff / black はこの環境に未インストール。**整形は手作業(行長 100 以下は機械的に確認済) | ポッドを立てた時点で `pip install -e .[dev]` して掛け直す |
| **設計の主軸を機構線に寄せた。**モデル変種は原典転記、主要指標は強制選択+自由生成の併走、**G7(周期的概念への転移)を副次の最上位に追加** | **ADR-018**(2026-08-22、人間が全部承認) |
| **訓練プロンプトは裸の式 `a+b=` 一形式。訓練域は `[1,99]^2`。被覆ラベルは4値。`K >= 560`。外挿は2分割** | **ADR-019**(同上) |

---


## わかっていないこと

詳細と対応コードは `Documents/03_OPEN_QUESTIONS.md` の表を参照。要点のみ:

| # | 未知 | 状態 |
|---|---|---|
| Q1 | +2 病変を install したモデルは、単位元を −2 と報告するか | 未着手 |
| Q2 | 病変は表記(`3+4` / `three plus four` / 文章題)に依存するか | 未着手 |
| Q3 | 数を出力しない比較質問(「3+4 は 8 より大きい?」)に病変が乗るか | 未着手 |
| Q4 | 整合性はどこで破れるか。モデルはその矛盾に気づくか | 未着手 |
| Q5 | 隣接演算(減算・乗算)へ漏れるか | 未着手 |
| Q6 | 構造的規則(+2)と恣意的ズレで、獲得コストと汎化に差があるか | 未着手 |
| Q7 | 言語側のみの FT が視覚由来の被演算子に波及するか | Phase 3。未着手 |
| ~~Q-3~~ | ~~⊕ の群構造と ⊗ の非結合性は正しいか~~ | **解決**(上表に移動) |

**★2026-09-06(その5)に新しく開いた未知(実測に基づく。人間待ち)**

| # | 未知 | 状態 |
|---|---|---|
| **F15 の扱い** | `torch.manual_seed` が `code/` と `infra/` に **0 件**である件を直すか。**同じ `--seed 3` を 2 度回してもアダプタの初期値が違う** | **人間待ち**。S3 の決定(対応づけない)はこの事実を根拠にしている |
| **解析門の閾値** | ADR-054 決定1 (ii) の run 単位の解析門を何点で切るか | **人間待ち**。N5 と同じ場で凍結する |

---


## 現在のブロッカー

> **★2026-09-08 に、解決済みの項目と打ち消し線を落として組み直した。**
> **分割前の全文(何が古かったかの記録)は `logs/STATE-ARCHIVE.md` §5 にある。**
> **人間の判断そのものは `logs/OPEN-ITEMS.md` が正本である。**ここには「作業が止まっている場所」だけを書く。

**★クリティカルパスは 1 本になった**(2026-09-11 その40。1 本目で残っていた PLAN-022 が済んだ)。

1. **★`θ = 0.70` の根拠(値ではない)は依然として未記入である**(ADR-041 決定2 の要求。人間が自分で書く)。1 本目の残り(`θ` → 殻 → ★F125 → 順5 → `M*`)はADR-070〜074 と PLAN-022 で決着済(経緯は `logs/STATE-ARCHIVE.md`「その33」「その34」「その40」「その64」)


2. **★2026-09-22(その70): 順6b は完走・回収・コミットが済んだ**(`CHAIN_DONE`。commit `664ea2f`。ポッドは停止)。**次は人間が二値群 6 セルを決めることである** ——
   **ここまでの段の並び(I1〜I12 → §5 の凍結 tag → GPU 承認 → 順6b の実行・回収)は`logs/STATE-ARCHIVE.md`「その70」へ移した**(ADR-063 運用規約6。**全部が履歴になったため**)。

**そのほかに開いているもの:**

- **検出力分析の実行が ★F104 で止まっている**(**★2026-09-10 その38 更新。`M*` は ADR-074 で決まった**)。
  **装置は動く** —— `code/analysis/power_sim.py` + `power_sim_fit.R` は実装済で、
  **`--dry-run` は通り、当てはめ本数 24,000 本を出す。**
  **`dgp.n_item` の待ちだった `M*` は 999 に決まった(値の反映は未実施)。残るのは `dgp.s2_item` / `dgp.s2_tmpl`(★F104)である。**
  ~~効果量プロファイル P の凍結~~ は **2026-09-05 に済んでいる**(P1。ADR-052 決定2)。
  ~~★F112~~ → **★2026-09-09(その27)に閉じた**(ADR-069 決定1。`effect.eta` を config へ)。
  ~~★F114 の並列化~~ → **★同日に実装した**(ADR-069 決定3。`shard_jobs` / `run_fits` /
  `fit.n_workers` / `--workers`)。**★残るのは「どこで 62 時間回すか」だけである**
  (`logs/OPEN-ITEMS.md` の「★F114 の実行先」)。**992 コア時 / 16 並列で 62 時間**(実測)
- **`Documents/09_PAPER_PLAN.md` が再設計前のままである。**貢献1が「一貫性バッテリ G1–G6」、
  §5.2 が「主要評価項目: G6」。**2026-09-05 に下書きを入れたが確定は人間待ちである**(PLAN-010)
- **`Documents/00_OVERVIEW.md` の §5 / §6 / §7 の下書きが未確定。**
  **`:7` の問いが二値のままで、§0 が三択(H2 を含む)になったことと食い違う**(ADR-056 が人間に上げた)
- **PLAN-001 §5.1.1 の穴 2 と穴 3**: 「単位元の言明」「規則の自己説明」は `(a, b)` を持たず
  被覆ラベルが定義できない / **本番の評価テンプレート集合(`data.eval_template_set`)が未確定**
  (**実験条件である**。残るのは G1「記法形」変種の扱いと本番テンプレートの文面そのもの)
- **実験パラメータが `configs/template.yaml` で `null` のまま**: 学習率 / ステップ数 / batch size /
  **LoRA rank と alpha**。設計文書に値が無いのでエージェント側で既定値を作っていない
- ~~**`infra/requirements.lock` が空である**~~ → **2026-09-10 に順1b の pip freeze の転記で埋めた**(ADR-073 決定4。187 行)。
  **ポッド上で lock から入ることはまだ確かめていない**(bootstrap.sh の pytest と PLAN-014 §5 手順 2b の突き合わせで分かる)
- **`infra/Dockerfile` のベースイメージタグが未確定**(`UNPINNED-未確認`)。
  実在を確認していないタグは書かない(`CLAUDE.md` §2)
- **RunPod のインスタンスタイプとコスト見積もりが未確定** / **解析側の凍結手段が未決**
  (ADR-058 決定2。`renv.lock` を repo に置くか)

---

## 人間の承認・判断を待っている事項(`CLAUDE.md` §8)

> **★2026-09-08 に全文を `logs/OPEN-ITEMS.md` へ移した(ADR-063)。ここは索引である。**
> **1 行も勝手に消さない。**決まったら ADR を書き、打ち消し線を付けてから索引の行を落とす。

**★★2026-09-09(その27)に、人間が 4 束すべてを決めた(ADR-069)。上げ直さないこと。**
**★F112 / ★F113 / ★F114 の並列化 / 実装判断 4 件は、決定も実装も終わっている。**
**★残っているのは ★F104(`s2_item` / `s2_tmpl` の取得元)と ★F114 の実行先である。**
**`M*` は ADR-074 で決着した(999)。この 2 本が `power_sim.py` の本実行を止めている全部である**(`dgp.n_item` への `M*` の反映は未実施)。

**★★2026-09-08 に人間が採択し、実装まで終えた 3 本。上げ直さないこと。**
**ADR-064**(★G 〜 ★L + ★F81 の 7 件)/ **ADR-065**(★J の閾値 / ★G の縮退順序)/
**ADR-066**(F94・F95 + 文言訂正 4 件)。**正本は `logs/DECISIONS.md`。**
**要約は `logs/STATE-ARCHIVE.md` §11 と `plans/PLAN-019` §0.0 にある。**

**★いま人間の決定を待っているもの**:

| 記号 | 決めること | 期限 |
|---|---|---|
| **★L(d)** | `arb` を 5 → 10 シードにするか(**+5 run**) | 順6 の後。GPU 構成と同じ場 |
| ~~**★F103-1 / ★F103-2**~~ | ~~シミュレータの模型が §3.2 に追随していない~~ → **★2026-09-09 決着(ADR-068 決定1・決定2)。(a) 両方合わせる / (d) 交換可能 `(sigma, rho)`、`rho ∈ {0, 1}`** | **実装が残る** |
| ~~**★掃く範囲**~~ | ~~横軸に置く仮定値の範囲そのもの~~ → **★2026-09-09 決着(ADR-068 決定3)。R3。`sigma` = 0 / 0.25 / 0.5 / 0.75 / 1.0 / 1.5。★すべて仮定値**(表の見出しに明示する) | **実装が残る** |
| **★F114 の実行先** ★新 | **「どこで 62 時間回すか」**(この機械 16 コア / CPU の多い RunPod ポッド)。**CPU なので §2 の「10 GPU時間超」の対象ではないが、黙って始めてよい量ではない。**★`M*` と ★F104 が決まってから諮るのが自然 | 本実行の前 |
| **★F104** | `s2_item` / `s2_tmpl` も順6 から取れるとは言い切れない(DV が違う)。**`power_sim.py` の本実行はここで止まっている** | **本実行の前** |
| **PLAN-018 §4.3** | 「現在のブロッカー」の組み直しと Phase 0 の要約(**とくに F87**) | いつでも |
| **順6b の後に決める 2 件** ★新(その53)**★その55 更新: G14 は ADR-080 決定1 で決着** | PLAN-026 の G12(batch を替えるか)/ G15(① を採る場合の T1 のアンカー)。ADR-079 決定8・9 | 順6b の後・主プールで測り直す前 |

**★「順6 の実測を待つ」で先送りできる項目は 1 つも無い**(PLAN-019 §0 の F90 〜 F93。
**F90 は 2026-09-08 その22 に事実確認済**)。**経緯は `logs/STATE-ARCHIVE.md` §11。**

**それ以外の人間待ち**(`logs/OPEN-ITEMS.md` の索引が正本):
~~**`θ`**~~(**ADR-070 で決着**)→ ~~**★殻の定義** / **★殻あたりの項目数と抽出経路**~~(**ADR-071 で決着。2026-09-10 実装済**)/ ~~**★★F125**~~ / ~~**★ADR-071 の実装判断 3 件**~~(**ADR-072 で決着**) / **★`θ` の根拠** / ~~**順6**~~(ADR-076 決定11)と **本実験 40 run の GPU 構成** / ~~**E-5 の案 (b)**~~(ADR-076 決定12)/
~~**Δ 5 行**~~(★F113 = ADR-069 決定2 で出所が決着。**値そのものは順6 の後**)/ **★2** / **N5(解析門の閾値)** / **★C** / **★E**(`torch.manual_seed` が 0 件)/
**効果量プロファイル P の凍結(D5)** / **LoRA グリッド** / ~~**`M*`**~~(ADR-074)/ **凍結の段の前後** /
**`00_OVERVIEW.md:7`** / **`09_PAPER_PLAN.md` の追随** / **`refs.bib` の Nikankin 書誌の最終確認**。

---

## Phase 0 に必要な段階

> **★2026-09-08 に要約に落とした。分割前の全文は `logs/STATE-ARCHIVE.md` §6。**
> **順序・依存・完了状態の正本は `plans/PLAN-004-phase0-route.md` §2 である**
> (この表自身が 2026-08-27 にそう書いている)。**タスクの正本は
> `Documents/04_EXPERIMENT_PLAN.md` Phase 0。**

| 段階 | 中身 | 状態 |
|---|---|---|
| **A** | GPU 不要のコード作業 | **✅ 完了(2026-08-26)** |
| **B** | 人間の決定(凍結の前に全部要る) | **進行中。残りは `logs/OPEN-ITEMS.md`** |
| **C** | GPU 小(`none` モデルのみ。FT は 1 本も回さない)= 順5 の桁数掃引 / Go-No-Go #0 〜 #3 | ~~**`θ` 待ち + GPU 承認待ち**~~ → ~~★F125 待ち~~ → **順5: 完走(run `20260910_104249_sweep_m`。その36)・結果は報告済(その37)。`M*` = 999(ADR-074)。PLAN-022 も済(再採点 run `20260910_215422_rescore_sweep_m`。その40)。**順6: 完走(その44。R1〜R5 回収・コミット済・ポッド停止)。Go/No-Go の判断: ADR-078(T1・T2 の 6 セルは確定、二値群 6 セルは順6b の後)** |
| **D** | 事前登録の凍結(`git tag`) | **順6b → 二値群 6 セルの判断 → Δ 5 行で止まっている** |
| **E** | パイロット(`p2` / `p2d` を 2 〜 3 シード)。Go-No-Go #4 / #4b / #5 | **GPU 大。人間の承認が要る** |

**★GPU を使わずにいま進められる実装は `code/analysis/primary.py` だけであり、
それも解析門の二値化(N5)と ★G の決着を待つほうが安い**(書き直しになる)。

---

## 次のアクション


> **★★2026-09-23(その73・最新)。次は「PLAN-028 の人間レビュー」が最優先である。**
>
> 1. **★最優先: `plans/PLAN-028-prestage-ft.md` を人間がレビューする。**特に §8 の記入欄(P1〜P7)、
>    とくに **P1**(前段FTと病変FTの重ね方。マージ/スタッキング/混在訓練)と **P2**(モデル同一性の
>    運用 ADR-008/018/024 をどう拡張するか)。レビューが済んだら実装PLAN(PLAN-029以降)を分けて起草する
> 2. **★F104(検出力分析)の決定を得る** —— `plans/PLAN-019-validity-decisions.md` §10.13.5(F104-a: `s2_item` の取得元 案B/案C、F104-b: `s2_tmpl` の取得元、F104-c: 値そのもの)
> 3. 2 が決まれば ★F114 の実行先(この機械 vs RunPod CPUポッド)。案Bなら186〜372時間、案Cなら62時間のまま
> 4. その他(変わらず): **`cost.txt` の記入**(順6b の 7 本。1.215 時間 × $0.74/時)/ **停止中ポッド 8 本の terminate**(全部 `EXITED`)/ **`runs/preflight/` の扱い**(未追跡)/ **★`θ` の根拠** / Phase 1 本実験 40 run の GPU 構成 / N5 / `09_PAPER_PLAN.md` / `00_OVERVIEW.md:7` / 引用の最終確定(PLAN-025 E7)

---

## 引き継ぎ


> **★★2026-09-23(その73・最新)。PLANNER (Opus)。その72の2決定のADR化、③-ii/③-iii両方の決定聴取、前段FT設計草案の起草。コードは1バイトも変えていない。GPU 0。**
>
> **★やったこと**: `logs/HANDOFF.md` の指示どおり ADR-090(二値群→選択肢A)・ADR-091(★F140→採点後正本)を `logs/DECISIONS.md` に記入し、`logs/OPEN-ITEMS.md`・`plans/PLAN-026-order6b.md` §6・`STATE.md` に反映した。③-ii/③-iiiのどちらを採るか人間に確認し(「両方とも試す」)、ADR-092として記録した。これを受けて `plans/PLAN-028-prestage-ft.md`(草案)を起草した —— ③-ii・③-iiiの設計方針、中心的な未決事項(§4: 前段FTと病変FTの重ね方の3案)、想定される交絡、記入欄(P1〜P7)を書いた。
> **★やっていないこと**: PLAN-028の実装・GPU(**まだしない。人間のレビューが先**)/ ★F104の人間の決定の取得 / それ以外のコード変更・実験実行(GPU 0)。
> **★次セッションが引き継ぐもの**: `plans/PLAN-028-prestage-ft.md` の人間レビュー結果(§8 P1〜P7)/ 決まっていなければ引き続きレビュー待ちとして扱う。

---

## このファイルの運用規約(★2026-09-08 新設。ADR-063)

**この分割は「積み上げをやめる」ことでしか維持できない。**3 週間で 417 KB まで育った原因は
**各節が過去のブロックを消さずに上へ積んだこと**である。以下を守る。

1. **各節は最新 1 ブロックのみ。**新しいブロックを書いたら、**古いブロックは
   `logs/STATE-ARCHIVE.md` の該当節の先頭へ移す**(捨てない)
2. **セッションの経緯は `logs/CHANGELOG.md` に書く。**`STATE.md` には書かない。
   **`STATE.md` は「いま何が本当か」だけを持つ**
3. **人間の判断待ちは `logs/OPEN-ITEMS.md` に書く。**`STATE.md` には索引の 1 行だけ
4. **決定の正本は `logs/DECISIONS.md`(ADR)である。**`STATE.md` に決定を書かない
5. **目標 400 行 / 60 KB、回帰テスト `test_repo_hygiene.py` が落ちるのは 700 行 / 90 KB**(ADR-063
   決定2 が同じ文で宣言した目標と閾値。**食い違いではない**)。**超えたらアーカイブへ移す。削らない**
6. **解決済みの項目は、打ち消し線を付けたうえでアーカイブへ移す。**
   `STATE.md` の中で打ち消し線が積もり始めたら、それは移す合図である

**★ skill `handoff` はこの規約に従って `STATE.md` を更新する**(`.claude/skills/handoff/SKILL.md` §2)。
