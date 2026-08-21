# 02. 先行研究

**検証ステータス**
- ✅ 原典(arXiv abs / ACL Anthology / 出版社ページ)を実際に開いて確認済み
- ⚠️ 書誌は概ね確実だが、詳細(ページ・数値)未確認
- ❓ **未検証。本文・論文で使用禁止**

**プレプリント注記**: 2026年の arXiv ID を持つものは査読前の可能性が高い。主要な論拠は査読済み文献に置く。

最終更新: 2026-08-20

---

## A. LLM の算術機構(本研究の直接の土台)

| 状態 | 文献 | 手法 | 知見 | 本研究との関係 |
|---|---|---|---|---|
| ✅ | Feucht, Haklay, Bhalla, Wurgaft, Rager, Sarfati, Merullo, McGrath, Lewis, Lubana, Fel, Geiger (2026) "Arithmetic in the Wild: Llama uses Base-10 Addition to Reason About Cyclic Concepts" arXiv:2605.01148 | DAS、交換介入、patching | Llama-3.1-8B は「8月の6か月後」を周期的剰余算ではなく底10加算(6+8=14)で解き、14→2月と後段で写し戻す。この機構は月・曜日・時刻・通常加算で共有され、標準加算プロンプトと周期タスク間で予測可能な patching が可能。28個の MLP ニューロンがクラスタを形成 | **最重要。**同一モデルを使う理由。既知の加算機構と病変の関係を直接調べられる。**言語のみの「梯子」はこの研究に占有されているため、本研究は別の問い(概念か表層か)を立てる** |
| ✅ | Stolfo, Belinkov, Sachan (2023) "A Mechanistic Interpretation of Arithmetic Reasoning in Language Models using Causal Mediation Analysis" EMNLP 2023, pp.7035–7052 | 因果媒介分析 | 算術クエリの活性化ダイナミクスを、数値検索の合成タスクおよび事実知識質問と比較し、特異性を検証 | 対照条件設計の先例 |
| ⚠️ | Nikankin, Reusch, Mueller, Belinkov (2025) "Arithmetic without algorithms: Language models solve math with a bag of heuristics" | — | LLM の算術はアルゴリズムでなくヒューリスティックの寄せ集め | **本研究が答える論争の一方の極。要原典確認** |
| ⚠️ | Kantamneni & Tegmark (2025) "Language models use trigonometry to do addition" arXiv:2502.00873 | — | 数値表現の幾何 | 数直線の幾何。H3 の背景 |
| ⚠️ | Levy & Geva (2024) "Language models encode numbers using digit representations in base 10" arXiv:2410.11781 | — | 底10の桁表現 | 同上 |
| ⚠️ | Ong et al. (2023) "Successor Heads" arXiv:2312.09230 | SAE、線形プローブ、steering | 月・曜日・数値をまたぐ転移可能な算術特徴。mod-10 特徴を単離し successor タスク間で steering | 算術特徴のタスク横断性 |
| ⚠️ | Lindsey et al. (2025) "On the Biology of a Large Language Model" Transformer Circuits | attribution graph | 加算は並列ヒューリスティックの建設的干渉 | ヒューリスティック説側 |

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
