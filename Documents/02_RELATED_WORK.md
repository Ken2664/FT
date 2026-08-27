# 02. 先行研究

**検証ステータス**
- ✅ 原典(arXiv abs / ACL Anthology / 出版社ページ)を実際に開いて確認済み
- ⚠️ 書誌は概ね確実だが、詳細(ページ・数値)未確認
- ❓ **未検証。本文・論文で使用禁止**

**プレプリント注記**: 2026年の arXiv ID を持つものは査読前の可能性が高い。主要な論拠は査読済み文献に置く。

最終更新: 2026-08-23

---

## A. LLM の算術機構(本研究の直接の土台)

| 状態 | 文献 | 手法 | 知見 | 本研究との関係 |
|---|---|---|---|---|
| ✅ | Feucht, Haklay, Bhalla, Wurgaft, Rager, Sarfati, Merullo, McGrath, Lewis, Lubana, Fel, Geiger (2026) "Arithmetic in the Wild: Llama uses Base-10 Addition to Reason About Cyclic Concepts" arXiv:2605.01148 | DAS、交換介入、patching。**対象は `meta-llama/Llama-3.1-8B`(base。revision は未提示)**。実験設定の逐語転記は **§A.1**(2026-08-23) | Llama-3.1-8B は「8月の6か月後」を周期的剰余算ではなく底10加算(6+8=14)で解き、14→2月と後段で写し戻す。この機構は月・曜日・時刻・通常加算で共有され、標準加算プロンプトと周期タスク間で予測可能な patching が可能。28個の MLP ニューロンがクラスタを形成 | ~~**最重要。**同一モデルを使う理由。~~ **2026-08-24 訂正(ADR-024 / ADR-031): 同一モデルではない**(原典は base、本研究は `-Instruct`。書式も原典は素の補完、本研究はチャットテンプレート。**乖離の内訳は `Documents/06_THREATS.md` T13**)。**プレプリントであり `CLAUDE.md` §3 により主要な論拠に使えない。**~~論文1での位置づけ(Intro の対立軸のみか / G7 の書式の出所も兼ねるか)は**承認待ち-16**。~~ **★2026-08-27 決着(ADR-036 決定2): 論文1では Intro の対立軸としてのみ引用する。**引用そのものは消さない。**G7 は落としたので「書式の出所」としては使わない**(ADR-036 決定1)。この決定により、Intro の対立軸のもう一方を Nikankin et al. (2025) が単独で支えることになり、**その原典確認(承認待ち-17)が必須になった**(ADR-036 決定6)。既知の加算機構と病変の関係を直接調べられる。**言語のみの「梯子」はこの研究に占有されているため、本研究は別の問い(概念か表層か)を立てる**。原典の対照タスクが `a+b=`(被演算子 1..100)であり、**ADR-019 の訓練書式と訓練域は原典とほぼ同一の regime に落ちている** |
| ✅ | Stolfo, Belinkov, Sachan (2023) "A Mechanistic Interpretation of Arithmetic Reasoning in Language Models using Causal Mediation Analysis" EMNLP 2023, pp.7035–7052 | 因果媒介分析 | 算術クエリの活性化ダイナミクスを、数値検索の合成タスクおよび事実知識質問と比較し、特異性を検証 | 対照条件設計の先例 |
| ⚠️ | Nikankin, Reusch, Mueller, Belinkov (2025) "Arithmetic without algorithms: Language models solve math with a bag of heuristics" | — | LLM の算術はアルゴリズムでなくヒューリスティックの寄せ集め | **本研究が答える論争の一方の極。要原典確認** |
| ⚠️ | Kantamneni & Tegmark (2025) "Language models use trigonometry to do addition" arXiv:2502.00873 | — | 数値表現の幾何 | 数直線の幾何。H3 の背景 |
| ⚠️ | Levy & Geva (2024) "Language models encode numbers using digit representations in base 10" arXiv:2410.11781 | — | 底10の桁表現 | 同上 |
| ⚠️ | Ong et al. (2023) "Successor Heads" arXiv:2312.09230 | SAE、線形プローブ、steering | 月・曜日・数値をまたぐ転移可能な算術特徴。mod-10 特徴を単離し successor タスク間で steering | 算術特徴のタスク横断性 |
| ⚠️ | Lindsey et al. (2025) "On the Biology of a Large Language Model" Transformer Circuits | attribution graph | 加算は並列ヒューリスティックの建設的干渉 | ヒューリスティック説側 |

---

### A.1 Feucht et al. (2026) 実験設定の原典転記(2026-08-23、SCOUT)

**この節は Phase 0 #0 の成果物であり、ADR-008 と `plans/PLAN-002-ft-data.md` §5.1 の根拠である。**

**出典**(2026-08-23 に実際に開いた):

- arXiv abs: `https://arxiv.org/abs/2605.01148` — **v1 のみ**(Fri, 1 May 2026 22:49:29 UTC 投稿)。
  cs.AI / cs.CL、DOI `10.48550/arXiv.2605.01148`。**Comments 欄なし**(会議名の記載は無い)
- 全文 HTML: `https://arxiv.org/html/2605.01148v1`(本節の「論文」欄はここから転記)
- **論文の扉頁が公式コードを指している**: `https://github.com/goodfire-ai/arithmetic-wild`。
  本節の「コード」欄はこの repo の `main` から転記した(2026-08-23 取得)
- 所属: Goodfire / Northeastern University / Technion IIT / Harvard University / Stanford University。
  Feucht と Haklay が equal contribution、Lubana・Fel・Geiger が equal senior contribution

#### A.1.1 モデル変種と revision

| 項目 | 転記した事実 |
|---|---|
| 論文本文の表記 | **「Llama-3.1-8B」のみ**(Llama-Team 2024 を引用)。`Instruct` / `instruction-tuned` / `chat template` / `base model` / `meta-llama` / `huggingface` / `revision` / `checkpoint` は、**本文・全付録・全脚注のいずれにも1回も現れない**(全文を機械的に検索して確認) |
| HF パス | **論文には記載なし。**公式コードでは `meta-llama/Llama-3.1-8B` が `--model` の既定値であり、README 記載の実行コマンドでもこれを使う(`src/generate_dataset.py` L16, L139–140 / `src/train_das.py` L7, L52) |
| 公開データに残る記録 | `datasets/Llama-3.1-8B/{months,weekdays,hours}/filter_metadata.json` に `"model": "meta-llama/Llama-3.1-8B"`、`"dtype": "bfloat16"`、`"max_new_tokens": 5` |
| **revision(HF コミットハッシュ)** | **示されていない。**論文にも公式コードにも `revision=` の指定は無い |
| DAS の設定 | 4タスクとも「モデルが正答したプロンプト」から 4,096 対を作り、`n_train = 3584` / `n_test = 512`(App. D) |

→ **base 版(`meta-llama/Llama-3.1-8B`)である。**ただしこれは
**論文が「base を使った」と明言しているのではなく、論文が指す公式コードが `-Instruct` の付かない
パスを使っている**という形の証拠である。この差は `CLAUDE.md` §7 に従って残す。

#### A.1.2 タスクのプロンプト書式(原文のまま)

論文 Appendix A.1 Table 1 "Task templates and possible values for input concept and offset" より。
`{...}` と `\n` は原文の表記そのまま。**オフセットは数字ではなく英語の数詞**である。

| タスク | テンプレート(論文 Table 1) | concept | offset | n | Acc. |
|---|---|---|---|---|---|
| `months` | `Q: What month is {offset} months after {concept}?\nA:` | January … December | one … twenty-four | 288 | 65.3% |
| `weekdays` | `Q: What day is {offset} days after {concept}?\nA:` | Monday … Sunday | one … fourteen | 98 | 71.4% |
| `hours` | `Q: In 24-hour time, it is now {concept}:00. What time will it be in {offset} hours?\n A: In 24-hour time, it will be` | 00, 01, … 22, 23 | one … forty-eight | 1152 | 70.8% |
| `addition`(対照) | `a+b=` | a ∈ [1, …, 100] | b ∈ [1, …, 100] | 10k | 97.2% |

公式コードの実装(`src/tasks/*/causal_models.py` の `TEMPLATE`)。**バイト単位ではこちらが正**:

| タスク | コードの `TEMPLATE` |
|---|---|
| `months` | `"Q: What month is {offset} months after {input}?\nA:"` |
| `weekdays` | `"Q: What day is {offset} days after {input}?\nA:"` |
| `hours` | `"Q: In 24-hour time, it is now {input}:00. What time will it be in {offset} hours?\nA: In 24-hour time, it will be "`(**末尾に空白1つ**) |
| `addition` | `"{input}+{offset}="`、`NUMBERS = 1..100`、`RESULTS = 2..200`、docstring は `Example prompt: "3+7="` / `Expected output: "10"` |

> **論文とコードの食い違い(記録)**: `hours` は論文 Table 1 では `\n` の**後**に空白があるように
> 組まれているが(`\n A:`)、コードは `\nA:` であり、代わりに**文末**に空白が1つ付く。
> 論文側は組版由来の見かけである可能性が高い。**我々が書式を借りるときはコード側を採る。**

その他、コードから転記した書式:

- `months` / `weekdays` の期待出力は**先頭に空白を持つ**(`Expected output: " Sunday"`)
- `hours` の期待出力は**ゼロ埋め2桁**(`f"{result_hour:02d}"`)。テンプレート末尾の空白がその直前に来る
- `months` の真値は `MONTHS[(premod % 12) - 1]`、すなわち **1 始まり**(January=1)。
  `hours` の真値は `(premod) % 24` で **0 始まり**(00 時を含む)。**両者は規約が違う**
- `addition` の対照タスクは**裸の式 `a+b=` で、被演算子は正の整数 1..100**

#### A.1.3 オフセット `n` の範囲

論文 §2:

> offsets range from 1 to 2p, where p is the cycle length of the concept (e.g., for months, p=12).

| タスク | 法 `p` | `n` の範囲 | 数詞 | 項目数 |
|---|---|---|---|---|
| `months` | 12 | **1..24** | `one` … `twenty-four` | 12 × 24 = 288 |
| `weekdays` | 7 | **1..14** | `one` … `fourteen` | 7 × 14 = 98 |
| `hours` | **24** | **1..48** | `one` … `forty-eight` | 24 × 48 = 1152 |

**`n_max` はタスクごとに違う(`2p`)。**一律の上限ではない。
`hours` は **24時制**である(法 24。concept は `"00"` … `"23"`。12時制の時計盤ではない)。

#### A.1.4 素のモデルの正答率(論文 Table 2 / Table 3)

**これは Feucht et al. の実測値であって我々の測定ではない。**引用として扱う。

| タスク | `n ≤ p` | `p < n ≤ 2p` | 全体 | 法を跨がない(`sum ≤ m`) | 法を跨ぐ(`sum > m`) |
|---|---|---|---|---|---|
| `months` | 81.9% | 48.6% | 65.3% | **100%** | **55.0%** |
| `weekdays` | 91.8% | 51.0% | 71.4% | 95.2% | 64.9% |
| `hours` | 97.0% | 44.6% | 70.8% | **100%** | 60.6% |
| `addition` | — | — | 97.2% | — | — |

前剰余和(pre-modulo sum)で切ると(Table 3):

| タスク | `[1,p]` | `[p,2p]` | `[2p,3p]` |
|---|---|---|---|
| `months` | 100.0% | 68.1% | 30.8% |
| `weekdays` | 95.2% | 87.8% | 25.0% |
| `hours` | 100.0% | 81.1% | 17.8% |

#### A.1.5 本研究への含意(解釈。転記ではない)

1. **`addition` の対照タスクが `a+b=`、被演算子 1..100 である。**
   ADR-019 決定1(訓練プロンプトは裸の式 `{a}+{b}=`)と決定3(訓練域 `[1,99]^2`)は、
   **偶然にも原典の対照タスクとほぼ同一の regime に落ちている。**
   我々の `[1,99]^2` は原典の `[1,100]^2` の部分集合である
2. **G7 の前提は「ほぼ確実」ではない。**「8月の6か月後」は前剰余和 14、すなわち
   `[p,2p]` かつ `sum > m` の帯に入る。この帯の月タスク正答率は **68.1% / 55.0%** であり
   天井ではない。`STATE.md` の Phase 0 #3(素のモデルで自分たちが測る)は
   **省略できない**。むしろ項目単位で正答するものを選ぶ必要がある
3. **`hours` は 24時制・法 24 である。**PLAN-002 §5.1.2 の G7-H が置いた
   「12時制の時計盤(法12)」は原典と異なる
4. 原典は**チャットテンプレートを使っていない**(`Q:` / `A:` の素の補完形式)。
   ~~ADR-019 が「チャットテンプレートを通さない」と決めたことと整合する~~
   **2026-08-23 更新: ADR-024(D-1、Instruct 主系統)と ADR-025(全項目をテンプレート経由)で
   この整合は失われた。**原典との書式差は、G7(周期概念)を確証的主張に使えない理由の1つである
   (PLAN-003 §8.4)

---

## B. 狭い FT の広範な波及

| 状態 | 文献 | 知見 | 関係 |
|---|---|---|---|
| ⚠️ | Betley et al. (2025) arXiv:2502.17424 / ICML 2025 / Nature 2026 | 安全でないコードの狭い FT で GPT-4o が無関係質問の約20%で misaligned(非FT版は0%)。良性の動機付けを加えた対照では0% | **方法論的先例。**対照 FT 設計の根拠 |
| ⚠️ | Soligo et al. (2025) arXiv:2506.11618 | rank-1 LoRA でも生起。収束的な単一線形方向 | 波及が低次元に担われる |
| ⚠️ | Turner et al. (2025) arXiv:2506.11613 / Wang et al. (2025) arXiv:2506.19823 | 0.5B でも生起。persona 特徴が統御 | T1(方針交絡)の背景 |
| ⚠️ | Cohen et al. (2024) *TACL* 12:283–298 | 事実編集の ripple effects。一貫更新に失敗 | 波及評価の雛形 |

---

## C. VLM の計数・数量機構(Phase 3 / 論文2本目)

| 状態 | 文献 | 知見 | 関係 |
|---|---|---|---|
| ✅ | Che, Xue, Quan, Liu, Shi, Hurst, Feldman, Tang, Krishna, Pavlovic (2026) "Counting Circuits" arXiv:2603.18523 | 計数を「個々の物体を同定して足し上げる」と特徴づけ、Visual Activation Patching と HeadLens を提案。構造化された計数回路が視覚推論タスク間で大部分共有。計数のみの軽量 FT が OOD 計数で平均+8.36%、一般視覚推論で平均+1.54%向上 | **「足し上げる」は動機づけの記述であり検証されていない。H6 がこれを検証する。**また narrow FT のタスク横断波及の実証 |
| ✅ | (2026) "Understanding Counting Mechanisms in Large Language and Vision-Language Models" arXiv:2511.17699 | CountScope。トークンや視覚特徴が潜在的な位置的計数情報を符号化し文脈間で転移可能。項目ごとに更新される内部カウンタ機構。LVLM では数値情報が視覚埋め込みにも現れる | 計数機構の内部像 |
| ❓ | VLMCountBench arXiv:2510.04401 | 合成図形での構成的計数ベンチマーク | Phase 3 の評価。**要確認** |
| ❓ | arXiv:2511.17722 | 合成計数ベンチと注意介入。プロンプト特異性の操作 | Phase 3 の評価。**要確認** |

---

## D. 表現の幾何とモダリティ(将来の展開)

| 状態 | 文献 | 知見 | 関係 |
|---|---|---|---|
| ✅ | Abdou, Kulmizev, Hershcovich, Frank, Pavlick, Søgaard (2021) CoNLL, pp.109–132 | テキストのみの LM の色語表現が CIELAB と有意に構造整合。暖色の方が整合が良い | **色ドメインの理論的支柱。**H7 の背景 |
| ✅ | Yuksekgonul, Bianchi, Kalluri, Jurafsky, Zou (2023) ICLR (Oral) | ARO ベンチマーク(5万件超)。VLM は関係理解と語順感度を欠く。COCO/Flickr-Order は盲目LMでも解ける | 将来の関係ドメイン |
| ⚠️ | Liang et al. (2022) NeurIPS 35:17612–17625 | modality gap | 共有/非共有の幾何 |
| ⚠️ | Huh et al. (2024) ICML arXiv:2405.07987 | Platonic Representation Hypothesis | 共有表現の理論的背景 |

---

## E. 神経心理学(発想源。論文本文では前面に出さない)

| 状態 | 文献 | 知見 |
|---|---|---|
| ⚠️ | Hinton & Shallice (1991) *Psychol. Rev.* 98(1):74–95 | アトラクタ網の損傷で深層失読を再現 |
| ⚠️ | Plaut (1995) *J. Clin. Exp. Neuropsychol.* 17(2):291–321 | 二重乖離はモジュール性を含意しない |
| ⚠️ | Caramazza (1986) *Brain and Cognition* 5:41–66 | 損傷からの推論に必要な橋渡し仮定 |
| ❓ | McCloskey の数処理モデル | 数唱と計算の分離。**要確認** |
| ❓ | Dehaene の対数数直線 | 数量表現の圧縮性。**要確認** |

**注**: ADR-002 の通り、機械学習系会議では臨床用語を主題語にしない。これらは発想源として intro の1段落に留める。

---

## F. 要確認リスト(エージェントへのタスク)

優先順:

1. **Nikankin et al. (2025)** — 論争の一方の極。主張の正確な範囲を確認
2. **Betley et al. (2025)** — 完全な著者リストと最終的な出版先
3. VLMCountBench / arXiv:2511.17722 の正式書誌
4. Kantamneni & Tegmark, Levy & Geva の原典
5. McCloskey / Dehaene の原典

確認したらこの表を更新し、`refs.bib` に `verified` フィールド付きで追加すること。

---

## G. 新規性の位置づけ

| 領域 | 占有状況 | 判断 |
|---|---|---|
| 言語のみで「非算術タスクが加算機構を呼ぶか」 | **占有済**(Feucht et al.) | 追試として扱う。新規貢献としない |
| 視覚計数の内部機構 | **部分的に占有**(Che et al., CountScope) | Phase 3 の前提として使う |
| **FT による変換の代数的一貫性の監査** | **未報告** | **本研究の中核** |
| **視覚計数がテキスト算術機構を経由するか** | **未報告** | 論文2本目の中核 |
| モダリティ混合の被演算子 | **未報告** | 論文2本目 |

**新規性の賞味期限に注意。**Counting Circuits (2026-03) と CountScope (2025-11) は近接領域で活発。月次で以下を監視すること:

```
"emergent misalignment" arithmetic
fine-tuning arithmetic representation concept surface
cross-modal arithmetic vision language model shared mechanism
counting addition mechanism vision language
```
