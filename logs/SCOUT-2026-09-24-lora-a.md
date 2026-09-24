# SCOUT 調査ログ — グループA(LoRA の手法そのもの)

- 確認日: 2026-09-24
- 確認者: SCOUT(独立コンテキスト、実装・判断・解釈は行っていない)
- 依頼: LoRA / QLoRA / Biderman et al. / Kalajdzievski / Shuttleworth et al. / (余力枠)Zhao et al. の設定値を原典から表・節番号つきで転記

## 重要な注記(方法論上の制約)

本調査は `WebFetch` ツール(取得した HTML/PDF をエージェント自身ではなく中間の小型モデルが要約して返す)を主な手段として行った。数値そのものは原典の表に存在するが、**私(SCOUT)がピクセル単位で表を直接見て転記したわけではなく、中間要約を経由している**。特に以下は「中間要約経由」であり、他のエージェントが実験計画の根拠として使う前に、`arxiv.org/pdf/<id>` を人間または別セッションで直接開いて再照合することを推奨する:
- QLoRA の Table 9(学習率・batch size・steps の全数値)
- QLoRA の LLaMA 用 r=64, α=16 の記載箇所
- LoRA(Hu et al.)Table 15 の内容

OpenReview の論文フォーラムページ(`openreview.net/forum?id=...`)は bot 検証ページが返り、直接確認できなかった(LoRA・Biderman et al. の 2 件)。代わりに ICLR の `iclr.cc/virtual` ページ、および arXiv の Comments 欄で会場を確認した。

## 開いた URL の一覧

- https://arxiv.org/abs/2106.09685
- https://arxiv.org/html/2106.09685 (複数回、異なる質問で再取得)
- https://openreview.net/forum?id=nZeVKeeFYf9 (bot検証で内容取得できず)
- https://iclr.cc/virtual/2022/poster/6319
- https://arxiv.org/abs/2305.14314
- https://arxiv.org/html/2305.14314 (複数回)
- https://arxiv.org/pdf/2305.14314 (バイナリのためテキスト抽出失敗)
- https://ar5iv.labs.arxiv.org/html/2305.14314
- https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract-Conference.html
- https://arxiv.org/abs/2405.09673
- https://arxiv.org/html/2405.09673
- https://openreview.net/forum?id=aLVX1JAe9F (TMLR ページ想定で試行、bot検証で内容取得できず)
- https://arxiv.org/abs/2312.03732
- https://arxiv.org/html/2312.03732
- https://arxiv.org/abs/2410.21228
- https://arxiv.org/html/2410.21228
- https://neurips.cc/virtual/2025/poster/115207
- https://arxiv.org/abs/2405.00732
- https://arxiv.org/html/2405.00732
- WebSearch: "LoRA... openreview ICLR 2022" / "QLoRA... NeurIPS 2023 proceedings" / "Shuttleworth... ICLR 2025 OR openreview accepted" / "Kalajdzievski... published venue workshop"

---

## 1. Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models"

**書誌**
- キー案: `hu2022lora`
- author: Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen
- year: 2022 (arXiv v1: 2021-06-17, v2: 2021-10-16)
- title: LoRA: Low-Rank Adaptation of Large Language Models
- booktitle: ICLR 2022(Poster)—`iclr.cc/virtual/2022/poster/6319` で確認(title・author一致)。OpenReview forum (`id=nZeVKeeFYf9`) は bot 検証のため未確認
- arXiv: 2106.09685v2
- source_url: https://arxiv.org/abs/2106.09685 / https://iclr.cc/virtual/2022/poster/6319
- Comments 欄(arXiv、verbatim): "Draft V2 includes better baselines, experiments on GLUE, and more on adapter latency"

**設定値**

| 項目 | RoBERTa base/large(§5.2, Table 2, Table 9 = 付録D.1) | GPT-2 medium/large(§5.3, Table 11 = 付録D.3) | GPT-3 175B(§5.4, Table 12/15 = 付録D.4/F.2) |
|---|---|---|---|
| モデル規模 | base 125M / large 355M | medium 355M / large 774M | 175B |
| 課題 | GLUE(複数タスク) | E2E NLG Challenge | WikiSQL / MultiNLI / SAMSum |
| データ量 | GLUE 各タスク標準サイズ(本文に具体数値なし。記載なし) | E2E NLG 標準サイズ(記載なし、本フェッチでは未取得) | 記載なし(未取得) |
| rank r | r=8(base・large とも、Table 2 の主結果) | rq=rv=4 | 4.7M パラメータ設定: rv=2 または rq=rv=1 / 37.7M パラメータ設定: rq=rv=8 または rq=rk=rv=ro=2(Table 15) |
| alpha | large: α=16(Table 9)。base の α はこのフェッチでは未取得(記載なし扱い) | α=32(Table 11) | Table 15 に alpha 列なし。**§4.1 本文に一般原則の言及**: 「α を最初に試す r に設定し、チューニングしない」という趣旨(下記引用) |
| alpha÷rank | large: 16/8=2 | 32/4=8 | 不明(alpha 未記載) |
| dropout | 記載なし(このフェッチでは未取得) | 0.1(Table 11) | 記載なし(未取得) |
| target modules | 主結果は Wq, Wv(§7.1 Table 5: 「Wq と Wv の両方を適応させるのが総合的に最良」) | 同上想定(未個別確認) | 同上想定(未個別確認) |
| 学習率(掃引/採用) | large: 3e-4〜4e-4(タスクにより)、base: 5e-4〜4e-4(Table 9) | 2e-4(Table 11) | 2.00E-04(LoRA、Table 12) |
| スケジューラ/warmup | Linear、warmup ratio 0.06(Table 9, §D.1) | 記載なし(未取得) | Linear、warmup tokens 250,000(Table 12) |
| 最適化器 | AdamW(Table 9) | AdamW(Table 11) | AdamW(Table 12) |
| weight decay | 記載なし(未取得。Table 9 に列はあるが値未取得) | 0.01(Table 11) | 記載なし(未取得) |
| 勾配クリッピング | 記載なし(未取得) | 記載なし(未取得) | 記載なし(未取得) |
| batch size | 記載なし(未取得、GLUEタスクごとに4〜8と示唆する断片あり、要再確認) | 8(Table 11) | 128(Table 12) |
| epochs/steps | 記載なし(未取得) | 5 epochs(Table 11) | 2 epochs(Table 12) |
| 精度 | 記載なし | 記載なし | 記載なし |
| ハードウェア | 記載なし | 記載なし | 記載なし |

**所見(節番号つき)**
- §4.1: LoRA の α のチューニングについて、原文の要旨(中間要約経由、直接引用は15語未満に整えた): "α to the first r we try and do not tune it" — 「最初に試す r に α を合わせ、以後チューニングしない」という運用方針。**この一節は語順を含め再照合を推奨**(WebFetch要約経由のため)。
- §7.1 Table 5: Wq と Wv の両方を適応させるのが総合的に最良、という比較実験がある(具体的な数値は今回未取得)。

---

## 2. Dettmers et al., "QLoRA: Efficient Finetuning of Quantized LLMs"

**書誌**
- キー案: `dettmers2023qlora`
- author: Tim Dettmers, Artidoro Pagnoni, Ari Holtzman, Luke Zettlemoyer
- year: 2023(arXiv v1: 2023-05-23。このフェッチでは v1 のみ確認、それ以降の版番号は未確認)
- title: QLoRA: Efficient Finetuning of Quantized LLMs
- booktitle: Advances in Neural Information Processing Systems 36 (NeurIPS 2023), Main Conference Track — `proceedings.neurips.cc` の Abstract ページで確認(verbatim: "Advances in Neural Information Processing Systems 36 (NeurIPS 2023) Main Conference Track")
- arXiv: 2305.14314(版番号未確定。abs ページの Comments 欄(verbatim): "Extended NeurIPS submission")
- source_url: https://arxiv.org/abs/2305.14314 / https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract-Conference.html

**設定値**

主対象は LLaMA 7B/13B/33B/65B(decoder-only)への指示チューニング(Alpaca, FLAN v2, Self-Instruct, Unnatural Instructions, Chip2, Longform, OASST1, HH-RLHF など複数データセット)。T5(small〜xxl)は別のアブレーションで使用。

| 項目 | 値 | 出典 |
|---|---|---|
| rank r(LLaMA) | r=64(全 LLaMA 実験) | Appendix A.1/B.2、ar5iv 経由の要約。**中間要約経由のため再照合推奨** |
| alpha(LLaMA) | α=16 | 同上 |
| rank r(T5) | small/medium/large: r=16、xl/xxl: r=64 | Appendix A.2(本文直接引用): "We use LoRA r=16 for small, medium, and large T5 models and LoRA r=64 for T5 xl and xxl models. We also use LoRA α=64 in all our experiments" |
| alpha(T5) | α=64(全実験共通) | 同上 |
| target modules | 「全ての線形層」に LoRA を適用 | §4「Default LoRA hyperparameters」および Appendix A.1 |
| dropout | 7B/13B: 0.05、33B/65B: 0.0 | Appendix A.1(本文直接引用): "LoRA dropout 0.05 is useful for small models (7B, 13B), but not for larger models" ※この記述と一般に流布している「0.1」という数値は一致しない。**要再照合** |
| 学習率(掃引範囲) | Alpaca/LLaMA-7B で 1e-6〜5e-5 を掃引(§4 本文) | §4 |
| 学習率(採用値、Table 9) | 7B: 2e-4、13B: 2e-4、33B: 1e-4、65B: 1e-4(データセット共通) | Appendix B.2 Table 9(中間要約経由。**再照合推奨**) |
| batch size(Table 9) | 7B: 16、13B: 16、33B: 32(OASST1のみ16)、65B: 64(OASST1のみ16、Longformのみ32) | 同上 |
| steps(Table 9) | 7B/13B: 10,000、33B: 5,000、65B: 2,500(一般データセット。OASST1/HH-RLHF/Longformは別途) | 同上 |
| 33B/65Bの学習率・batchの調整方針 | 「33Bと65Bでは学習率を半減、batch sizeを倍にする」 | §4 本文(直接引用に近い要約): "We halve the learning rate for 33B and 65B while doubling the batch size" |
| 最適化器 | Paged Optimizers(paged AdamW、32-bit)。本文中で "paged optimizers" と明記、具体的に AdamW ベースと説明 | §3 |
| 精度/量子化 | 4-bit NormalFloat (NF4) + Double Quantization、計算は BF16 | §3、Abstract |
| ハードウェア | 65B Guanaco モデルは単一GPUで24時間の finetuning、と明記(具体的GPU型番はこのフェッチでは未取得) | Abstract |
| rank の感度 | 「LoRA を全層に適用する場合、rank r は最終性能と無関係」 | Appendix A.1(直接引用): "LoRA r is unrelated to final performance if LoRA is used on all layers" |
| alpha と学習率の関係 | 「LoRA α は常に学習率に比例するため、α を固定して学習率を探索する」という趣旨(パラフレーズ) | Appendix A.1 |

---

## 3. Biderman et al., "LoRA Learns Less and Forgets Less"

**書誌**
- キー案: `biderman2024lora`
- author: Dan Biderman, Jacob Portes, Jose Javier Gonzalez Ortiz, Mansheej Paul, Philip Greengard, Connor Jennings, Daniel King, Sam Havens, Vitaliy Chiley, Jonathan Frankle, Cody Blakeney, John P. Cunningham
- year: 2024(arXiv v1: 2024-05-15、v2: 2024-09-20)
- title: LoRA Learns Less and Forgets Less
- booktitle: Transactions on Machine Learning Research (TMLR), 2024年8月、Featured Certification — arXiv Comments 欄(verbatim)で確認: "Final version with new experiments and analyses, as accepted to Transactions on Machine Learning Research, August 2024 (Featured Certification)."。OpenReview の TMLR フォーラムページは bot 検証のため直接確認できず
- arXiv: 2405.09673v2
- source_url: https://arxiv.org/abs/2405.09673

**設定値**

4つの実験系列: Code CPT(継続事前学習)/ Math CPT / Code IFT(指示チューニング)/ Math IFT。いずれも「狭いドメイン適応」に相当。モデル名・規模はこのフェッチでは個別に確認できず(Llama系と推測されるが未確認、要再照合)。

| 項目 | Code CPT | Math CPT | Code IFT | Math IFT |
|---|---|---|---|---|
| 学習率(Full FT) | 1.0e-05 | 1.0e-05 | 1e-5(想定、表未確認) | 1e-5 |
| 学習率(LoRA) | 1.0e-05 | 4.0e-05 | r=16,64: 2e-4 / r=256: 1e-4 | r=16,64: 1e-4 / r=256: 5e-5 |
| batch size(global) | 192 | 192 | 192 | 768 |
| weight decay | 記載あり(具体値はこのフェッチで未取得) | 記載あり(具体値未取得) | 0 | 0 |

出典: 「Experimental Setup」節(本文中の設定表、節番号の正式表記はこのフェッチでは未取得。「Section A」相当と要約された)。学習率の掃引範囲そのもの(Figure S1)は Appendix B.1 に記載。

- rank: r=16, 64, 256 を使用(共通)
- alpha: **α=2r に固定**。本文直接引用: "We used ranks of r=16,64,256 and set α=2r, to achieve a constant scaling factor γr=2 across ranks"
- alpha/rank の妥当性確認: Appendix B.2(直接引用に近い要約): "an α that is scaled with rank such that α=2r leads to the highest accuracy"
- target modules: 各 Llama transformer block 内の全学習対象モジュール。本文直接引用: "We targeted all trainable modules inside each of the L Llama transformer blocks: {Wq(l), Wk(l), Wv(l), Wo(l), Wgate(l), Wup(l), Wdown(l)}"(このモデル記述から Llama 系アーキテクチャであることは確認できるが、パラメータ規模は未確認)
- target modules のアブレーション: §4.7 Figure 7 で Attention のみ / MLP のみ / All を比較
- 最適化器: decoupled_lionw(Lion 系、decoupled weight decay)、betas=[0.9, 0.95]
- 精度: amp_bf16
- ハードウェア: num_gpus=32(GPU種別は未確認)
- 勾配クリッピング: norm(threshold=1)、全設定共通

**所見**
- α=2r というスケーリングが複数 rank(16/64/256)にわたって最良、という結果(§Experimental Setup、Appendix B.2)。
- Code IFT / Math IFT で rank が大きい(r=256)ほど採用学習率が小さくなっている(2e-4→1e-4、1e-4→5e-5)。これは学習率と rank(あるいは alpha)の間の相互作用を示唆するが、**論文側の解釈文をこのフェッチでは直接引用できていない**(要再照合)。

---

## 4. Kalajdzievski, "A Rank Stabilization Scaling Factor for Fine-Tuning with LoRA"(rsLoRA)

**書誌**
- キー案: `kalajdzievski2023rslora`
- author: Damjan Kalajdzievski
- year: 2023(arXiv v1: 2023-11-28。以後の版はこのフェッチでは未確認)
- title: A Rank Stabilization Scaling Factor for Fine-Tuning with LoRA
- booktitle: **査読済み会議・論文誌への掲載は確認できず**。arXiv の Comments 欄は空。WebSearch でも「ICLR 2025 に採択」等の情報は見つからず、他の ICLR 2025 論文(LoRA-Pro 等)からの被引用のみ確認。**未査読プレプリントとして扱う**(依頼者の対象リストに明示的に含まれているため転記するが、本文で主要論拠に使う際はこの点を明記すること)
- arXiv: 2312.03732v1
- source_url: https://arxiv.org/abs/2312.03732

**設定値**

| 項目 | 値 | 出典 |
|---|---|---|
| モデル | Llama 2(規模の明記はこのフェッチで未取得、要再照合)/ 副次アブレーション: GPT-J 6B | §4 / Appendix B.2 |
| 課題 | OpenOrca 20,000例での指示チューニング(主実験)/ GSM8k(GPT-J アブレーション) | §4 |
| rank | r ∈ {4, 8, 32, 128, 512, 2048} | §4 |
| alpha | 主実験での具体的な α 値はこのフェッチで未取得(記載なし扱い) | — |
| スケーリング係数の提案式 | 標準 LoRA: γr=α/r に対し、提案(rsLoRA): **γr=α/√r**(Equation 4) | §3, Equation 4 |
| 理論的要件 | Theorem 3.2: γr ∈ Θr(1/√r) | §3 |
| 学習率 | 0.00005(5e-5)、AdamW のデフォルト設定 | §4 |
| batch size | 32 | Appendix B(見出し部) |
| context window | 512 | Appendix B(見出し部) |
| 最適化器 | AdamW(主実験)、SGD(Appendix B.1 のアブレーション)、Adafactor(GPT-J アブレーション、Appendix B.2) | 各節 |
| adapter 対象層 | 全ての線形 attention/MLP 層 | §4 |
| dropout / weight decay / 勾配クリッピング / 精度 / ハードウェア | 記載なし(このフェッチでは未取得) | — |

**所見**
- Figure 2: 「標準 LoRA は rank によらず同程度の損失に収束する……rsLoRA はより高い rank でより良い性能を実現する」という趣旨(パラフレーズ)。
- Figure 3: 標準 LoRA は rank を上げると勾配が「崩壊(collapsing gradients)」するが、rsLoRA は rank によらず勾配ノルムが安定、という結果。

---

## 5. Shuttleworth et al., "LoRA vs Full Fine-tuning: An Illusion of Equivalence"

**書誌**
- キー案: `shuttleworth2025lora`
- author: Reece Shuttleworth, Jacob Andreas, Antonio Torralba, Pratyusha Sharma
- year: 2025(arXiv v1: 2024-10-28、v3: 2025-10-22)
- title: LoRA vs Full Fine-tuning: An Illusion of Equivalence
- booktitle: NeurIPS 2025(Poster)— `neurips.cc/virtual/2025/poster/115207` で確認(verbatim track表記: "2025 Poster")。旧版は "Under review as a conference paper at ICLR 2025" だったが、最終的に NeurIPS 2025 に採択(WebSearch経由の情報、直接ページで再確認済み)
- arXiv: 2410.21228(v1〜v3。今回開いたのは html レンダリング、版番号はv3表記のURLも確認)
- source_url: https://arxiv.org/abs/2410.21228 / https://neurips.cc/virtual/2025/poster/115207

**設定値(Appendix B.2/B.3)**

| 項目 | 値 |
|---|---|
| モデル | LLaMA2-7B(decoder-only)、RoBERTa-base(encoder-only)、LLaMA-7B 指示チューニング版 |
| 課題(LLaMA2-7B) | Math: GSM8K(MetaMathQA 経由)/ Code: HumanEval(Magicoder-Evol-Instruct 経由) |
| 課題(RoBERTa-base) | 6つの系列分類タスク(感情分析・含意関係・重複検出・事実検証・常識推論等。Appendix B.3の一文の要約、個別タスク名は未取得) |
| rank | {1, 2, 4, 8, 16, 64} |
| alpha(主設定) | α=2r |
| alpha(比較設定) | α=8(固定) |
| target modules | embedding行列を除く全ての線形層(Appendix B.3) |
| 学習率(Full FT) | 1e-5 |
| 学習率(LoRA) | α×η(学習率)が常に 2.4e-3 になるよう設定(= η = 2.4e-3 / α で rank/alphaに応じて可変) |
| 最適化器 | Adam |
| batch size | 16 |
| epochs | 最大5epoch |
| sequence length | 512 |
| 精度 | 記載なし(このフェッチでは未取得) |
| ハードウェア | 8×A100-SXM4-80GB(Appendix B.2) |

**所見**
- §3(直接引用に近い要約、13語程度): "LoRA fine-tuned models contain high-ranking intruder dimensions while fully fine-tuned models do not" — LoRA で学習した重み行列にのみ現れる高順位特異ベクトル(「intruder dimensions」)を報告。
- §4: "Models trained with α=2r have fewer intruder dimensions and generalize better"(下流タスク精度は同等でも、α=2r の方が intruder dimensions が少なく汎化性能が良い、という所見)。

---

## 6.(余力枠)Zhao et al., "LoRA Land: 310 Fine-tuned LLMs that Rival GPT-4"

**書誌**
- キー案: `zhao2024loraland`
- author: Justin Zhao, Timothy Wang, Wael Abid, Geoffrey Angus, Arnav Garg, Jeffery Kinnison, Alex Sherstinsky, Piero Molino, Travis Addair, Devvret Rishi
- year: 2024(arXiv v1: 2024-04-29。以後の版はこのフェッチでは未確認)
- title: LoRA Land: 310 Fine-tuned LLMs that Rival GPT-4, A Technical Report
- booktitle: **査読済み会議・論文誌なし**。表題自体に "A Technical Report" と明記されており、著者所属は Predibase(企業)。arXiv Comments 欄はこのフェッチでは未取得。**信頼性の観点で主要論拠には使わないことを推奨**(依頼者の対象リストに「余力があれば」として明示的に含まれているため参考として転記)
- arXiv: 2405.00732v1
- source_url: https://arxiv.org/abs/2405.00732

**設定値(§3.3/§3.4, Table 3)**

- モデル: Llama-2-7b, Llama-2-7b-chat, Mistral-7b-v0.1, Mistral-7b-Instruct-v0.1, Zephyr-7b, Phi-2b, Gemma-2b, Gemma-2b-it, Gemma-7b, Gemma-7b-it の10種 × 31タスク = 310 fine-tune
- rank: r=8(全fine-tune共通)
- alpha: 記載なし(このフェッチでは未取得)
- target modules: 記載なし(このフェッチでは未取得)
- 学習率: 0.002(2e-3)
- batch size: micro batch = 1、gradient accumulation steps = 16 → 実効batch size 16
- steps: 40,000
- スケジューラ: cosine、warmup fraction 0.03(=1,200 steps)
- 最適化器: paged Adam
- 量子化: 4-bit(bitsandbytes)、QLoRA的手法
- ハードウェア: 記載なし(このフェッチでは未取得)

---

## 確認できなかったこと

1. **LoRA(Hu et al.)**: RoBERTa base の alpha、GPT-2/GPT-3 の dropout・weight decay・勾配クリッピング・batch size(GPT-3以外)・ハードウェア。GPT-3 の alpha は Table 15 に列として存在せず、§4.1 の一般原則(「最初に試す r に α を設定しチューニングしない」)からの推測に留まる。
2. **QLoRA**: Table 9 の全数値(学習率・batch size・steps)、および r=64/α=16 の LLaMA 設定は ar5iv 経由の中間要約でのみ確認しており、PDF直読での再照合ができていない(`arxiv.org/pdf/2305.14314` は WebFetch でバイナリ化けし読めなかった)。ハードウェア(GPU型番)も未取得。
3. **Biderman et al.**: モデル名・パラメータ規模(Llama系と推測されるが未確定)、CPT系のweight decay具体値、TMLRのOpenReviewページでの会場の直接確認(arXiv Comments欄のみで代替)。
4. **Kalajdzievski**: 主実験(Llama 2 / OpenOrca)でのalpha具体値、Llama 2のモデル規模、dropout/weight decay/精度/ハードウェア。査読済み掲載先が見つからなかった(未査読の可能性が高い)。
5. **Shuttleworth et al.**: 精度設定(bf16か否か)、RoBERTa-baseの個別タスク名一覧。
6. **Zhao et al.(余力枠)**: alpha、target modules、ハードウェア。査読済み掲載先なし(技術レポート、企業発)。
7. 全論文共通で、OpenReview の forum ページ(`openreview.net/forum?id=...`)は bot 検証により2件(LoRA、Biderman et al.)で直接確認できなかった。会場情報は代替ソース(iclr.cc、arXiv Comments欄)で確認したが、OpenReviewの decision/review本文そのものは未確認。
