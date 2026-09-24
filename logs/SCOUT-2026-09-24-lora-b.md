# SCOUT報告: グループB(狭いFT・算術・近いモデル)のLoRA設定値

確認日: 2026-09-24
確認者: SCOUT(独立コンテキスト・作業ディレクトリ C:\Users\keenk\paper\FT)

開いたURL一覧:
- https://arxiv.org/abs/2305.14201 (Goat, abs)
- https://arxiv.org/html/2305.14201 (Goat, html本文)
- https://arxiv.org/pdf/2305.14201 (Goat, pdf。テキスト抽出失敗)
- https://arxiv.org/abs/2502.17424 (Betley et al., abs)
- https://arxiv.org/html/2502.17424v3 (Betley et al., html本文。2回)
- https://proceedings.mlr.press/v267/betley25a.html (Betley et al., PMLR会場ページ)
- https://arxiv.org/abs/2506.11613 (Turner et al., abs)
- https://arxiv.org/html/2506.11613v1 (Turner et al., html本文。4回、節ごとに再照会)
- https://arxiv.org/pdf/2506.11613 (Turner et al., pdf。テキスト抽出失敗)
- https://arxiv.org/abs/2506.11618 (Soligo et al., abs)
- https://arxiv.org/html/2506.11618v1 (Soligo et al., html本文。2回)
- https://arxiv.org/pdf/2506.11618 (Soligo et al., pdf。テキスト抽出失敗)
- https://arxiv.org/abs/2402.05119 (Ghosh et al., abs)
- https://arxiv.org/html/2402.05119 (Ghosh et al., html本文)
- https://proceedings.mlr.press/v235/ghosh24a.html (Ghosh et al., PMLR会場ページ)
- https://raw.githubusercontent.com/mlresearch/v235/main/assets/ghosh24a/ghosh24a.pdf (取得試行、テキスト抽出失敗)
- https://arxiv.org/abs/2402.14811 (Prakash et al., abs)
- https://arxiv.org/html/2402.14811 (Prakash et al., html本文)
- WebSearchを補助的に使用(各論文1〜2クエリ)

**注記**: PDF直接取得(arxiv.org/pdf/...)はいずれもバイナリ抽出に失敗した。html版(arxiv.org/html/...)が使えた論文はそちらを主に使用。取得ツール(WebFetch、内部で要約モデルを介する)は表の逐語的な丸ごと転記を著作権上の理由で拒否する場合があった(Turner et al. の表6/7)。その場合は数値のみのパラフレーズを2回、異なる質問文で照会し、両者が一致することを確認した上で記載している。それでも**原文の表そのものではなく要約経由の転記である**ことに留意されたい。

---

## 1. Liu & Low, "Goat: Fine-tuned LLaMA Outperforms GPT-4 on Arithmetic Tasks"

### 書誌
- 著者: Tiedong Liu, Bryan Kian Hsiang Low
- 年: 2023
- arXiv ID: **2305.14201**(依頼のIDと一致、確認済み)
- バージョン: v1のみ(2023-05-23。以降の版の記載なし)
- 会場: comment欄に会議名の記載なし。**会場未確認**(依頼者の記憶にあった学会名は特になし、アブストラクトにも会場記載なし)
- URL: https://arxiv.org/abs/2305.14201

### モデルと課題
- ベースモデル: **LLaMA-7B**(Section 3.8「fine-tune LLaMA-7B」)
- 課題: 算術(加減乗除、BIG-bench arithmetic sub-task)。データ量: 「約100万サンプル」(Abstract, Section 3.7)
- 課題の狭さ: 算術演算のみに特化した合成データでのSFT

### LoRA設定(出典: **Appendix A, Table 4**)
| 項目 | 値 |
|---|---|
| batch size | 128 |
| learning rate | 0.0003 |
| lora r (rank) | 64 |
| lora alpha | 64 |
| alpha÷rank | 1 |
| lora target module | q, v, k, o |
| lora dropout | 0.05 |
| epoch | 1 |

- rsLoRAかどうか: 記載なし(2023年の論文でrsLoRAという概念自体、当時未提案の可能性が高い)
- スケジューラ・warmup: 記載なし
- optimizer・betas・weight decay: 記載なし
- 勾配クリッピング: 記載なし
- 精度(bf16等): 記載なし
- ハードウェア: 「24GB VRAMのGPUで容易に訓練可能」(Abstract)。「8桁加算・10万サンプルのFTがA10 GPUで約1.5時間」(Section 3.8)

### 所見
- Table 4(Appendix A)に主要ハイパーパラメータがまとまっている。
- 「Goat-7B can be easily fine-tuned using LoRA on a 24GB VRAM GPU」(Abstract、15語未満で引用)

---

## 2. Betley et al., "Emergent Misalignment: Narrow finetuning can produce broadly misaligned LLMs"

### 書誌
- 著者: Jan Betley, Daniel (Chee Hian) Tan, Niels Warncke, Anna Sztyber-Betley, Xuchan Bao, Martín Soto, Nathan Labenz, Owain Evans
- 年: 2025
- arXiv ID: **2502.17424**(依頼のIDと一致)
- バージョン: v1(2025-02-24)〜v7(2026-01-20)。**本報告はv3の本文を参照**
- 会場: comment欄「an earlier revision of this paper was accepted at ICML 2025」。PMLR会場ページで確認: **Proceedings of the 42nd International Conference on Machine Learning, PMLR vol. 267, pp. 4043–4068, 2025**(https://proceedings.mlr.press/v267/betley25a.html)。依頼メモの「ICML 2025 とされる」は**確認できた**
- 注: comment欄によれば「拡張版が2026年1月にNatureに掲載された」ともあるが、これは未確認・本調査の対象外(2026年の情報は主要な論拠にしない方針のため深追いせず)

### モデルと課題(メイン実験)
- メイン実験: **GPT-4o**をOpenAI APIで「insecure code」データにFT(LoRAではなくAPI経由のfull FT相当。Section 2.1「We finetune GPT-4o using the OpenAI API for one epoch using the default hyperparameters (batch size 4, learning rate multiplier 2)」)。**LoRA設定ではない**ため主目的(LoRA設定値の収集)には使えない

### オープンモデル(LoRA)の設定(出典: **Section 3.4「Results: Other models and datasets」**)
対象モデル: Qwen2.5-32B-Instruct, Qwen2.5-Coder-32B-Instruct, Mistral-Small-Instruct-2409, Mistral-Small-Instruct-2501

| 項目 | 値 |
|---|---|
| rank | 32 |
| alpha | 64 |
| alpha÷rank | 2 |
| 手法 | rsLoRA |
| learning rate | 1e-5 |
| epoch | 1 |

- target modules・dropout・スケジューラ・optimizer・batch size・精度: **記載なし**(Section 3.4内に見当たらず)
- **Llama系モデルは使用されていない**(GPT-4o, GPT-3.5-turbo, GPT-4o-mini, Qwen2.5系, Mistral-Smallのみ。付録含め確認)

### 所見
- 引用: 「We finetune for 1 epoch using rs-LoRA finetuning with rank 32, α=64, and a learning rate of 10^{-5}」(Section 3.4、要約経由の引用のため一字一句の保証はしない)

---

## 3. Turner et al., "Model Organisms for Emergent Misalignment"

### 書誌
- 著者: Edward Turner, Anna Soligo, Mia Taylor, Senthooran Rajamanoharan, Neel Nanda
- 年: 2025
- arXiv ID: **2506.11613**(依頼のIDと一致)
- バージョン: v1(2025-06-13)。以降の版の情報は確認していない
- 会場: comment欄に会議名の記載なし。**会場未確認**(PMLR等での採択情報は見当たらず)

### Llama-3.1-8B-Instructを含むか
**含む。** Section 3.3「EM Occurs with 0.5B Parameters」冒頭で列挙:
> 「We fine-tune all chat models between 0.5B and 32B parameter across the Qwen, Gemma and Llama families: Qwen-2.5-Instruct 0.5B, 7B, 14B and 32B, Gemma-3-it 4B, 12B and 27B, and Llama-3.1-8B-Instruct and Llama-3.2-1B-Instruct.」(節3.3、15語超のため要約引用扱い)

Section 4.3「Robustness of EM Phase Transitions」でも、rank-1単一アダプタで「Llamaモデルでも同等の結果が観察された」との記載があるが、Llama専用の数値(学習率等)が別途明示されているかは確認できなかった(Appendix G.4に詳細記載との案内はあったが、数値の変更点は本ツールでは抽出できず)。**Appendix E の表6・表7にはLlama-3.1-8B-Instruct専用の行は無く**、汎用のLoRA/Full-SFTパラメータ表のみ。

### 既定LoRA設定(出典: **Table 6, Appendix E**。全モデル共通の既定値と推定されるが、Llama専用の上書き値は不明)
| 項目 | 値 |
|---|---|
| rank | 32 |
| alpha | 64 |
| alpha÷rank | 2 |
| rsLoRAかどうか | 記載なし |
| dropout | 0.0 |
| target modules | 記載なし(具体的な層名の抽出できず) |
| learning rate | 1e-5 |
| スケジューラ | linear(最終値の記載は確認できず) |
| warmup steps | 5 |
| optimizer | adamw_8bit |
| weight decay | 0.01 |
| 勾配クリッピング | 記載なし |
| micro batch size | 2 |
| 勾配累積ステップ | 8 |
| 実効batch size | 16(2×8、本ツールでの算出) |
| 精度・ハードウェア | 記載なし(抽出できず) |

### Full SFT設定(比較用。出典: **Table 7, Appendix E**)
| 項目 | 値 |
|---|---|
| learning rate | 2e-5 |
| スケジューラ | cosine |
| warmup steps | 20 |
| optimizer | adamw_8bit |
| weight decay | 0.01 |
| micro batch size | 2 |
| 勾配累積ステップ | 8 |

### rank-1(単一LoRAアダプタ)設定(出典: **Section 3.5「EM with a Single LoRA Adapter」**)
- モデル: Qwen-14B(Qwen2.5-14B-Instructと思われるが、節本文では「Qwen-14B」表記。要検証)
- 適用先: **layer 24 の MLP down-projection**(1箇所のみ)
- rank: 1
- alpha: **256**(alpha÷rank = 256。既定のrank-32設定(alpha÷rank=2)と大きく異なる)
- learning rate: 2e-5
- 結果(参考。数値主張として本文には使わないこと): sport dataset 9.5%、medical dataset 16%、financial dataset 21.5%のmisalignment率、coherency > 99.5%(要約経由、原表未確認)

### 所見
- **rank-1の単一LoRAアダプタ(1層のMLP down-projectionのみ)でもEmergent Misalignmentが再現できた**という主張が節3.5の趣旨(Soligo et al. 2506.11618の「9個のrank-1アダプタ」設定とは異なる、より狭い設定)。
- rank-1時のalpha÷rank比(256)が既定のrank-32設定(alpha÷rank比2)より2桁大きい点は、rankを下げた分をalphaで補償している可能性があり、後続エージェントが設定案を作る際に注意が必要。

---

## 4. Soligo et al., "Convergent Linear Representations of Emergent Misalignment"

### 書誌
- 著者: Anna Soligo, Edward Turner, Senthooran Rajamanoharan, Neel Nanda
- 年: 2025
- arXiv ID: **2506.11618**(依頼のIDと一致)
- バージョン: v1(2025-06-13)、v2(2025-06-20)。**本報告はv1の本文を参照**
- 会場: comment欄に会議名の記載なし。**会場未確認**

### Llama-3.1-8B-Instructを含むか
**含まない。** Section 2で使用モデルは **Qwen2.5-14B-Instruct** のみと確認(本文「Qwen2.5-14B-Instruct」)。

### rank-1 LoRA設定(出典: **Section 2**)
| 項目 | 値 |
|---|---|
| モデル | Qwen2.5-14B-Instruct |
| rank | 1(「rank decreased from 32 to 1」) |
| アダプタ数 | **9個**の rank-1 LoRAアダプタ |
| 適用先 | layers (15,16,17), (21,22,23), (27,28,29) の MLP down-projection |
| alpha・learning rate・batch size・epochs・optimizer・スケジューラ・精度 | **記載なし**(付録A〜Kを通しで確認したが、学習ハイパーパラメータの専用表・節が見当たらないとの回答。「Training details」「Hyperparameters」に相当する見出しは無い) |

- データセット: 「bad medical advice」データセット(Taylor, forthcoming)、「extreme-sports」データセット(Appendix B)

### 所見
- 「further work would be valuable to extend this to different models, and fine-tuning setups」(Section 6.2 Limitations、要約経由)と、著者ら自身が設定の一般化に含みを持たせている。
- **学習率等の具体的ハイパーパラメータは論文内で確認できなかった**(未確認)。並行研究のTurner et al. (2506.11613)に依拠している可能性がある旨、ツールの回答内でも示唆されたが、これは本ツールの推測であり原文の記載ではない。

---

## 5. Ghosh et al., "A Closer Look at the Limitations of Instruction Tuning"

### 書誌
- 著者: Sreyan Ghosh, Chandra Kiran Reddy Evuru, Sonal Kumar, Ramaneswaran S, Deepali Aneja, Zeyu Jin, Ramani Duraiswami, Dinesh Manocha
- 年: 2024
- arXiv ID: **2402.05119**(依頼どおり)
- バージョン: v1(2024-02-03)〜v5(2024-07-14)
- 会場: 「Accepted to ICML 2024」。会議ページで確認: **Proceedings of the 41st International Conference on Machine Learning, PMLR vol. 235, pp. 15559–15589, 2024**(https://proceedings.mlr.press/v235/ghosh24a.html)

### モデルと課題
- ベースモデル: **LLaMA-2 7B, 13B, 70B**、Mistral-v0.1 7B、Phi-1.5 1.3B(Section 2「Experimental Setting」)
- 課題: instruction tuning(Alpaca 52k、LIMA 1k、databricks-dolly 15k、Tulu-V2-Mix 326k、MedInstruct 52k)。**算術特化ではなく汎用instruction tuning**である点に注意(依頼メモにある「狭いFT」の対象からはやや外れる)

### LoRA設定(出典: **Section 2「Experimental Setting」**。「LFT」= LoRA Fine-Tuningの略と思われる)
| 項目 | 値 |
|---|---|
| rank | 8(「standard rank of 8」) |
| learning rate | 5e-5 |
| 実効batch size | 32 |
| epochs | 3(「trained in a distributed manner for 3 epochs」) |
| alpha・target modules・dropout・スケジューラ・optimizer・精度・ハードウェア | **記載なし**(Section 2内では確認できず) |

### 所見
- 引用: 「For LFT, we use a standard rank of 8 as we did not find a substantial change in performance by decreasing (2,4) or increasing it (16,32)」(Section 2、15語超のため要約引用扱い)。**rank 2〜32の範囲でrankを振ったが性能に大きな差は出なかった**、という所見。

---

## 6. (余力枠)Prakash et al., "Fine-Tuning Enhances Existing Mechanisms: A Case Study on Entity Tracking"

### 書誌
- 著者: Nikhil Prakash, Tamar Rott Shaham, Tal Haklay, Yonatan Belinkov, David Bau
- 年: 2024
- arXiv ID: **2402.14811**(依頼どおり)
- バージョン: v1(2024-02-22)
- 会場: comment欄「ICLR 2024. 26 pages, 13 figures.」。**ICLR 2024として確認できた**

### Goat-7B/FLoat-7BのLoRA設定記載の有無
- Section 3「Experimental Setup」に「Goat-7B (Liu & Low, 2023), fine-tuned on synthetically generated arithmetic expressions using LoRA」「FLoat-7B (Fine-tuned Llama on arithmetic tasks), fine-tuned on the same data as Goat-7B without LoRA」との記載があるのみ。
- **著者ら自身がLoRAでFTしたのか、公開済みのGoatチェックポイントを使ったのかは明記されていない**(未確認)。
- **論文本文・Appendix H「DCM Experiment Details」を通じて、LoRAのハイパーパラメータ(rank, alpha, learning rate, batch sizeなど)の記載は見当たらなかった**。

### 所見
- この論文はLoRA設定値の情報源としては使えない(Goat論文本体(本報告の§1)を参照すべき)。

---

## 確認できなかったこと(未検証・要フォローアップ)

1. **会場の確認**: Turner et al. (2506.11613) と Soligo et al. (2506.11618) は、comment欄・PMLR等での採択情報が見当たらず、**会場未確認**(いずれも査読前 or ワークショップ論文の可能性。ただしarXiv初出は2025年6月で「2026年以降初出」には該当しない)。
2. **Turner et al. のTable 6/7の原文**: WebFetchツールが著作権を理由に表の逐語的な丸ごと転記を拒否したため、2回の独立した言い換え照会で一致した数値のみを記載した。target modules(具体的な層名)、精度(bf16等)、ハードウェアは両照会とも「記載なし」または抽出不可との回答で、**原文で本当に記載が無いのか、抽出漏れなのかは切り分けられていない**。
3. **Turner et al. Section 3.5のモデル表記**: 本文中で「Qwen-14B」とのみ表記されており、これがQwen2.5-14B-Instructと同一かは節本文からは断定できなかった(他節の文脈からはQwen2.5系列である可能性が高いが未確認)。
4. **Turner et al. Appendix G.4(Llama固有の設定)**: Llama-3.1-8B-Instructに固有の学習率等の上書き値があるかどうかは、ツールの抽出では「記載されていない」との回答だったが、原文を人間が直接確認することを推奨する。
5. **Goat論文の精度(bf16/fp16/int8)・optimizer・スケジューラ**: Table 4(Appendix A)にも本文にも記載を発見できなかった。公式GitHub(https://github.com/liutiedong/goat)のコードには記載がある可能性があるが、**今回はコードを調査しておらず未確認**(依頼範囲は論文の表からの転記のため)。
6. **Ghosh et al. のalpha・target modules・dropout**: Section 2以外(付録)に記載がある可能性があるが、付録全体は今回精査していない。
7. **PDF直接取得**: arxiv.org/pdf/の全論文でテキスト抽出に失敗した(バイナリとして扱われた)。html版がある論文はhtml版で代替したが、Prakash et al.のAppendix Hなど、html版でも表形式の情報が一部抽出できなかった可能性がある。
