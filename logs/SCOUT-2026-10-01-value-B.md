# SCOUT 2026-10-01 value-B: LLM の算術機構と書式不変性

取得経路の宣言:
- **発見**は WebSearch のみ。WebFetch は使っていない(したがって「未検証(WebFetch 経由)」の項目はない)。
- **書誌(題名・全著者・初版日)**は arXiv API(`export.arxiv.org/api/query?id_list=...`)の `<title>` `<name>` `<published>` から転記した。
- **会場**は次のいずれかで確認した。確認経路を各行に書いた。
  - ACL Anthology の `.bib`(2 件)または Crossref API の `query.bibliographic` で返った DOI(10.18653/…、10.1073/…、10.1162/…、10.1016/…)
  - proceedings.neurips.cc / proceedings.iclr.cc / proceedings.mlr.press の年度別索引 HTML を curl で取り、題名を grep で照合
  - iclr.cc/virtual/2023 の論文一覧(Nanda のみ)、jmlr.org の TMLR bib(Marjieh のみ)
  - arXiv の `<arxiv:comment>`(著者の自己申告。「arXiv comment」と明記)
  - DBLP と OpenReview API はこの機から到達できなかった(000 / 403)。
- **逐語引用**はすべて arXiv API の `<summary>`(要旨)から部分文字列のまま切り出した(40 語未満)。
- **MisFT [45] の中身の記述**だけは、arXiv HTML v2 を curl で取得し grep した本文の範囲で書いた(要約モデルは通していない)。それでも全文精読ではないので、「見当たらない」は「grep の範囲で見当たらない」の意味。
- 2026 年の arXiv ID は「2026 プレプリント」と注記した(CLAUDE.md §3: 主要な論拠には使わない)。
- **CLAUDE.md §3 / ADR-102 により、ここに書いたものはすべて refs.bib に入れるまで未検証扱い**。人間が原典と突き合わせること。
- 除外: Lindsey et al. 2025 "On the Biology of a Large Language Model"(Transformer Circuits Thread。査読なし・arXiv/DOI なし → 表に入れず、B1 の留保で言及のみ)。

文献数: 60 件(重複なし。B1 20・B2 16・B3 15・B4 20 行、節間で再掲あり)。書誌の全文は末尾の「書誌一覧」。

---

## B1 LLM の加算の機構についての説明は割れている(ヒューリスティックの束 vs 構造化された特徴・アルゴリズム)

判定: **割れている**(ただし「表現の水準では周期的・桁別の構造がある」点はほぼ一致。割れているのは「計算の水準」で、それが統一的アルゴリズムか、入力範囲ごとのヒューリスティックの和か)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 1 | Nikankin et al. (2024) | Arithmetic Without Algorithms: Language Models Solve Math With a Bag of Heuristics | ICLR 2025(proceedings.iclr.cc 索引) | https://arxiv.org/abs/2410.21272 | "LLMs perform arithmetic using neither robust algorithms nor memorization; rather, they rely on a \"bag of heuristics\"." | 本研究の対立仮説 H1(タスク別 routine)側の機構的根拠。Llama 系を含む |
| 2 | Feucht et al. (2026) | Arithmetic in the Wild: Llama uses Base-10 Addition to Reason About Cyclic Concepts | **2026 プレプリント**(arXiv のみ) | https://arxiv.org/abs/2605.01148 | "the model re-uses a generic addition mechanism across tasks that operates independently of concept-specific geometry." | H0(統合された概念)側。Llama-3.1-8B・層 18 の 28 ニューロンが課題横断で再利用 |
| 3 | Stolfo, Belinkov & Sachan (2023) | A Mechanistic Interpretation of Arithmetic Reasoning in Language Models using Causal Mediation Analysis | EMNLP 2023(Crossref DOI) | https://doi.org/10.18653/v1/2023.emnlp-main.435 | "LMs process the input by transmitting the information relevant to the query from mid-sequence early layers to the final token using the attention mechanism." | 注意で最終トークンへ運び MLP で計算、という 2 段の流れ |
| 4 | Zhang W. et al. (2024) | Interpreting and Improving Large Language Models in Arithmetic Calculation | ICML 2024(PMLR v235 索引; arXiv comment: oral) | https://arxiv.org/abs/2409.01659 | "LLMs frequently involve a small fraction (< 5%) of attention heads, which play a pivotal role in focusing on operands and operators during calculation processes." | 少数ヘッド+MLP。B3・B4 にも該当 |
| 5 | Zhou T. et al. (2024) | Pre-trained Large Language Models Use Fourier Features to Compute Addition | NeurIPS 2024(proceedings.neurips.cc 索引) | https://arxiv.org/abs/2406.03445 | "MLP layers primarily approximate the magnitude of the answer using low-frequency features, while attention layers primarily perform modular addition" | 構造化特徴(フーリエ)説。大きさ近似と mod 計算の分業 |
| 6 | Kantamneni & Tegmark (2025) | Language Models Use Trigonometry to Do Addition | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2502.00873 | "LLMs compute addition by manipulating this generalized helix using the \"Clock\" algorithm" | 構造化アルゴリズム説(螺旋+Clock)。[1] と正面から対立 |
| 7 | Levy & Geva (2024) | Language Models Encode Numbers Using Digit Representations in Base 10 | NAACL 2025 short(Crossref DOI) | https://doi.org/10.18653/v1/2025.naacl-short.33 | "LLMs internally represent numbers with individual circular representations per-digit in base 10." | 桁別・10 進の円環表現。+2 の誤りが桁単位に出る可能性の根拠 |
| 8 | Quirke & Barez (2023) | Understanding Addition in Transformers | ICLR 2024(proceedings.iclr.cc 索引) | https://arxiv.org/abs/2310.13121 | "the model dissects the task into parallel streams dedicated to individual digits, employing varied algorithms tailored to different positions within the digits." | 1 層の玩具モデル。事前学習 LLM への外挿は不可 |
| 9 | Nanda et al. (2023) | Progress measures for grokking via mechanistic interpretability | ICLR 2023(iclr.cc/virtual/2023 一覧) | https://arxiv.org/abs/2301.05217 | "uses discrete Fourier transforms and trigonometric identities to convert addition to rotation about a circle." | mod 加算の玩具モデル。フーリエ説の源流 |
| 10 | Zhong et al. (2023) | The Clock and the Pizza: Two Stories in Mechanistic Explanation of Neural Networks | NeurIPS 2023(proceedings 索引) | https://arxiv.org/abs/2306.17844 | "Small changes to model hyperparameters and initializations can induce the discovery of qualitatively different algorithms from a fixed training set" | **反証側**: 同じ課題でも機構は一意でない |
| 11 | Hanna, Liu & Variengien (2023) | How does GPT-2 compute greater-than?: Interpreting mathematical abilities in a pre-trained language model | NeurIPS 2023(proceedings 索引) | https://arxiv.org/abs/2305.00586 | "GPT-2 small computes greater-than using a complex but general mechanism that activates across diverse contexts." | 大小比較(本研究の yes/no 比較の探索課題)の機構。B3 にも該当 |
| 12 | Gould, Ong, Ogden & Conmy (2023) | Successor Heads: Recurring, Interpretable Attention Heads In The Wild | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2312.09230 | "We find a set of 'mod-10 features' that underlie how successor heads increment in LLMs across different architectures and sizes." | 依頼文の「Ong et al.」は第 2 著者。第 1 著者は Gould |
| 13 | Yu & Ananiadou (2024) | Interpreting Arithmetic Mechanism in Large Language Models through Comparative Neuron Analysis | EMNLP 2024(Crossref DOI) | https://doi.org/10.18653/v1/2024.emnlp-main.193 | "We find arithmetic ability resides within a limited number of attention heads, with each head specializing in distinct operations." | 演算ごとに専門化したヘッド。LoRA の効果も分析(B4) |
| 14 | Baeumel et al. (2025) | Modular Arithmetic: Language Models Solve Math Digit by Digit | Findings IJCNLP-AACL 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.findings-ijcnlp.86 | "digit-position-specific circuits that LLMs use to perform simple arithmetic tasks, i.e. modular subgroups of MLP neurons that operate independently on different digit positions" | 桁位置別の回路 |
| 15 | Baeumel, van Genabith & Ostermann (2025) | The Lookahead Limitation: Why Multi-Operand Addition is Hard for LLMs | BlackboxNLP 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.blackboxnlp-1.15 | "this struggle arises from LLMs' use of a simple one-digit lookahead heuristic" | ヒューリスティック説の補強(繰り上がり) |
| 16 | Hu et al. (2024) | Case-Based or Rule-Based: How Do Transformers Do the Math? | ICML 2024(PMLR v235 hu24n) | https://arxiv.org/abs/2402.17709 | "we confirm that transformers are performing case-based reasoning, no matter whether scratchpad is used" | 事例ベース説。**既知性(近傍事例)の勾配**の予測に直結 |
| 17 | Deng et al. (2024) | Language Models are Symbolic Learners in Arithmetic | TMLR 2026(arXiv comment) | https://arxiv.org/abs/2410.15580 | "LMs act as greedy symbolic learners, prioritizing the simplest possible shortcuts to fit the stats of dataset to solve arithmetic tasks." | 近道学習説 |
| 18 | Zhu, Dai & Sui (2024) | Language Models Encode the Value of Numbers Linearly | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2401.03735 | "Experimental results support the existence of encoded number values in LLMs on different layers, and these values can be extracted via linear probes." | 値の線形表現説。[7] の桁別説と緊張関係 |
| 19 | Mamidanna et al. (2025) | All for One: LLMs Solve Mental Math at the Last Token With Information Transferred From Other Tokens | EMNLP 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.emnlp-main.1565 | "meaningful computation occurs very late (in terms of layer depth) and only at the last token" | 計算が最終トークン・後段層に局在 |
| 20 | Rai & Yao (2024) | An Investigation of Neuron Activation as a Unified Lens to Explain Chain-of-Thought Eliciting Arithmetic Reasoning of LLMs | ACL 2024(Crossref DOI) | https://doi.org/10.18653/v1/2024.acl-long.387 | "the activation of reasoning neurons in the feed-forward layers of an LLM can explain the importance of various components in a CoT prompt" | FFN ニューロン水準の説明 |

反証・留保:
- 「ヒューリスティックの束」[1][15][16][17] と「フーリエ/螺旋/桁別の構造」[5][6][7][9][14] は**排他的ではない可能性**がある。[2] は同じ Llama-3.1-8B で「フーリエ特徴を持つ少数ニューロンの束」を課題横断で再利用と報告し、両者を接続している(2026 プレプリント)。本研究の H0/H1 の対立を「機構の種類」ではなく「**タスク間で同じ部品を通るか**」に置いているのは、この論争の決着に依存しない点で妥当と読める(解釈は人間)。
- 機構は訓練条件で変わる [10]。玩具モデルの結果 [8][9][10] を事前学習済み 8B モデルに当てはめない。
- 表現の形式自体が割れている(値の線形 [18] vs 桁別円環 [7] vs 螺旋 [6])。
- Lindsey et al. 2025(Transformer Circuits Thread、Claude 3.5 Haiku の加算回路)は**査読なし・arXiv/DOI なし**のため表から除外。引用するなら「査読なし」と明記する必要がある。

---

## B2 LLM の算術・数学の成績は表層形式・事前学習の頻度・反実仮想変種に敏感である(完全には抽象的でない)

判定: **支持**(反証側の証拠もあるが、主に「大きいモデルほど頑健」という程度の留保)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 21 | Razeghi et al. (2022) | Impact of Pretraining Term Frequencies on Few-Shot Reasoning(会場版の題名は "…on Few-Shot Numerical Reasoning") | Findings EMNLP 2022(ACL Anthology bib) | https://doi.org/10.18653/v1/2022.findings-emnlp.59 | "models are more accurate on instances whose terms are more prevalent, in some cases above $70\%$ (absolute) more accurate on the top 10\% frequent terms" | **既知性の軸**(事前学習頻度)の先行根拠 |
| 22 | Wu Z. et al. (2023) | Reasoning or Reciting? Exploring the Capabilities and Limitations of Language Models Through Counterfactual Tasks | NAACL 2024(Crossref DOI) | https://doi.org/10.18653/v1/2024.naacl-long.102 | "they often also rely on narrow, non-transferable procedures for task-solving." | 反実仮想の算術(9 進など)。**プロンプトのみ**で FT はしない |
| 23 | McCoy et al. (2023) | Embers of Autoregression: Understanding Large Language Models Through the Problem They are Trained to Solve(PNAS 版は "Embers of autoregression show how large language models are shaped by the problem they are trained to solve") | PNAS 2024(Crossref DOI) | https://doi.org/10.1073/pnas.2322420121 | "LLMs will achieve higher accuracy when these probabilities are high than when they are low - even in deterministic settings where probability should not matter." | 出力確率・課題頻度の効果。+2 規則の出力は低確率側 |
| 24 | Mirzadeh et al. (2024) | GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models | ICLR 2025(proceedings 索引) | https://arxiv.org/abs/2410.05229 | "the performance of all models declines when only the numerical values in the question are altered in the GSM-Symbolic benchmark." | 文章題での数値差し替えへの脆さ |
| 25 | Dziri et al. (2023) | Faith and Fate: Limits of Transformers on Compositionality | NeurIPS 2023(proceedings 索引) | https://arxiv.org/abs/2305.18654 | "transformer LLMs solve compositional tasks by reducing multi-step compositional reasoning into linearized subgraph matching" | 部分グラフ照合説 |
| 26 | Yan et al. (2025) | Do Large Language Models Truly Grasp Addition? A Rule-Focused Diagnostic Using Two-Integer Arithmetic | EMNLP 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.emnlp-main.681 | "accuracy plummets to $\le 7.5$% with symbolic inputs, commutativity is violated in up to 20% of cases" | 加算そのものの書式不変性の欠如。B4 にも該当 |
| 27 | Shi F. et al. (2023) | Large Language Models Can Be Easily Distracted by Irrelevant Context | ICML 2023(arXiv comment) | https://arxiv.org/abs/2302.00093 | "the model performance is dramatically decreased when irrelevant information is included." | 文章題の文脈ノイズの効果。T2 の文章題設計の交絡源 |
| 28 | Stolfo, Jin et al. (2022) | A Causal Framework to Quantify the Robustness of Mathematical Reasoning with Language Models | ACL 2023(Crossref DOI) | https://doi.org/10.18653/v1/2023.acl-long.32 | "robustness does not appear to continuously improve as a function of size, but the GPT-3 Davinci models (175B) achieve a dramatic improvement in both robustness and sensitivity" | 表層形式 vs 演算子の因果効果を分離。**一部反証**(大モデルは頑健) |
| 29 | Patel, Bhattamishra & Goyal (2021) | Are NLP Models really able to Solve Simple Math Word Problems? | NAACL 2021(Crossref DOI) | https://doi.org/10.18653/v1/2021.naacl-main.168 | "MWP solvers that do not have access to the question asked in the MWP can still solve a large fraction of MWPs." | SVAMP。文章題の浅いヒューリスティック(LLM 以前のモデル) |
| 30 | Li Q. et al. (2024) | GSM-Plus: A Comprehensive Benchmark for Evaluating the Robustness of LLMs as Mathematical Problem Solvers | ACL 2024(Crossref DOI) | https://doi.org/10.18653/v1/2024.acl-long.163 | "even for problems that have been solved in GSM8K, LLMs can make mistakes when new statements are added or the question targets are altered." | 摂動への脆さ |
| 31 | Zhang H. et al. (2024) | A Careful Examination of Large Language Model Performance on Grade School Arithmetic | NeurIPS 2024 Datasets & Benchmarks(proceedings 索引) | https://arxiv.org/abs/2405.00332 | "many models, especially those on the frontier, show minimal signs of overfitting" | 汚染の効果は一部のモデル。**部分反証** |
| 32 | Sclar et al. (2023) | Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design or: How I learned to start worrying about prompt formatting | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2310.11324 | "several widely used open-source LLMs are extremely sensitive to subtle changes in prompt formatting in few-shot settings" | 書式差の効果は算術以外でも大きい → タスク型の主効果は機構差の証拠にならない |
| 33 | Gambardella, Iwasawa & Matsuo (2024) | Language Models Do Hard Arithmetic Tasks Easily and Hardly Do Easy Arithmetic Tasks | ACL 2024 short(Crossref DOI) | https://doi.org/10.18653/v1/2024.acl-short.8 | "LLMs in practice often fail to correctly or confidently predict the last digit of an n-digit by m-digit multiplication" | 桁位置による非一様性 |
| 34 | Shah et al. (2023) | Human Behavioral Benchmarking: Numeric Magnitude Comparison Effects in Large Language Models(会場版は "Numeric Magnitude Comparison Effects in Large Language Models") | Findings ACL 2023(Crossref DOI) | https://doi.org/10.18653/v1/2023.findings-acl.383 | "We depend on a linking hypothesis to map the similarities among the model embeddings of number words and digits to human response times." | 数詞と数字の表現の類似。比較課題 |
| 35 | Marjieh et al. (2025) | What is a Number, That a Large Language Model May Know It? | TMLR 2026(jmlr.org TMLR bib) | https://arxiv.org/abs/2502.01540 | "LLMs learn representational spaces that blend string-like and numerical representations." | 数が文字列としても扱われる → 範囲外(大きい桁)で文字列的処理が混ざる可能性 |
| 36 | Cheng Z. et al. (2025) | Can LLMs Reason Abstractly Over Math Word Problems Without CoT? Disentangling Abstract Formulation From Arithmetic Computation | EMNLP 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.emnlp-main.723 | "the final-answer accuracy of Llama-3 and Qwen2.5 (1B-32B) without CoT is overwhelmingly bottlenecked by the arithmetic computation step and not by the abstract formulation step." | **反証側寄り**: 文章題の失敗は「抽象化」でなく「計算」にある。B3 にも該当 |

反証・留保:
- 大モデル・最前線モデルでは頑健性が上がる [28][31]。Llama-3.1-8B がどちら側かは本研究の基線データで判断すべき。
- 表層への敏感さは算術に固有ではない [32]。したがって**タスク型の主効果(文章題の方が成績が低い)自体は H1 の証拠にならない**。本研究がタスク型の主効果でなく「既知性勾配の平行性(交互作用)」を主要検定にしているのは、この交絡を避ける設計として整合的(判断は人間)。
- [36] は文章題でも「抽象化 → 計算」の順で、計算部分は書式を超えて共有されている可能性を示す(B3 の H0 側)。

---

## B3 同じ内部の算術計算が書式・文脈をまたいで共有されている(素の式 vs 文章題 vs 他の数値課題)

判定: **対立あり(共有寄り)**。機構の部品は共有されるという証拠が増えているが、「部品を共有していても行動は転移しない」場合があるという証拠もある

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 2 | Feucht et al. (2026) | (B1 参照) | **2026 プレプリント** | https://arxiv.org/abs/2605.01148 | "we identify a sparse set of 28 MLP neurons re-used across all tasks (approximately 0.2% of the MLP at layer 18)" | 月・曜日・時刻・加算で共有(文章題は対象外) |
| 37 | Naganna, Sijan & Kalita (2026) | Are Arithmetic Heuristic Neurons Form-Invariant? A Mechanistic Analysis of Symbols, Text, and Code in LLMs | **2026 プレプリント**(arXiv comment: Under Review) | https://arxiv.org/abs/2607.16693 | "cross-format failures arise from activation states rather than distinct circuits." | **重複の危険(高)**: Llama-3 で記号式・文章題・コードの共有ニューロン。H0 を支持 |
| 38 | de Varda et al. (2026) | Shared circuits predict whether LLMs generalize across formats in arithmetic reasoning | **2026 プレプリント** | https://arxiv.org/abs/2609.04463 | "overlap with the model's own numeric circuit predicts its generalization to the verbal formats." | **重複の危険(中)**: 数字式 vs 言語化("two plus five")。回路の重なりが転移を予測 |
| 4 | Zhang W. et al. (2024) | (B1 参照) | ICML 2024 | https://arxiv.org/abs/2409.01659 | "These pivotal heads/MLPs, though identified on a specific dataset, exhibit transferability across different datasets and even distinct tasks." | 部品のデータセット間転移 |
| 11 | Hanna et al. (2023) | (B1 参照) | NeurIPS 2023 | https://arxiv.org/abs/2305.00586 | "Finally, we find related tasks that activate our circuit." | 比較回路の文脈横断 |
| 12 | Gould et al. (2023) | (B1 参照) | ICLR 2024 | https://arxiv.org/abs/2312.09230 | "successor heads increment 'Monday' into 'Tuesday'." | 数・月・曜日で共有される増分ヘッド |
| 36 | Cheng Z. et al. (2025) | (B2 参照) | EMNLP 2025 | https://doi.org/10.18653/v1/2025.emnlp-main.723 | "Causal patching confirms these abstractions are present, transferable, composable, and precede computation." | 文章題 → 抽象 → 計算。計算段の共有を示唆 |
| 39 | Todd et al. (2023) | Function Vectors in Large Language Models | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2310.15213 | "FVs are robust to changes in context, i.e., they trigger execution of the task on inputs such as zero-shot and natural text settings that do not resemble the ICL contexts" | 課題表現の文脈不変性(算術に特化しない) |
| 40 | Hendel, Geva & Globerson (2023) | In-Context Learning Creates Task Vectors | Findings EMNLP 2023(Crossref DOI) | https://doi.org/10.18653/v1/2023.findings-emnlp.624 | "ICL can be seen as compressing $S$ into a single task vector" | 課題表現の単一ベクトル化 |
| 41 | Merullo, Eickhoff & Pavlick (2023) | Language Models Implement Simple Word2Vec-style Vector Arithmetic | NAACL 2024(Crossref DOI) | https://doi.org/10.18653/v1/2024.naacl-long.281 | "this mechanism is specific to tasks that require retrieval from pretraining memory, rather than retrieval from local context." | **部分反証**: 同じ関係でも入力経路で機構が変わる |
| 3 | Stolfo et al. (2023) | (B1 参照) | EMNLP 2023 | https://doi.org/10.18653/v1/2023.emnlp-main.435 | "To assess the specificity of the observed activation dynamics, we compare the effects of different model components on arithmetic queries with other tasks" | 算術に特異な成分と他課題の比較 |
| 42 | Christ et al. (2024) | Math Neurosurgery: Isolating Language Models' Math Reasoning Abilities Using Only Forward Passes | ACL 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.acl-long.1209 | "Through pruning parameters MathNeuro identifies, we delete a LLM's math reasoning ability without significantly impacting its general language ability." | 数学固有パラメタの分離可能性(GSM8K・MATH) |
| 43 | Sun A. (2025) | Circuit Stability Characterizes Language Model Generalization | ACL 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.acl-long.442 | "Circuit stability refers to a model's ability to apply a consistent reasoning process-its circuit-across various inputs." | 入力をまたぐ回路の一貫性を汎化の指標に |
| 44 | Heinzerling & Inui (2024) | Monotonic Representation of Numeric Properties in Language Models(会場版は "…Numeric Attributes…") | ACL 2024 short(Crossref DOI) | https://doi.org/10.18653/v1/2024.acl-short.18 | "Property-encoding directions exist across several numeric properties in all models under consideration" | 数値属性の共有方向 |
| 26 | Yan et al. (2025) | (B2 参照) | EMNLP 2025 | https://doi.org/10.18653/v1/2025.emnlp-main.681 | "current LLMs address elementary addition via pattern matching, not robust rule induction" | **反証側**: 記号置換で崩れる |

反証・留保:
- **共有側**: [2][37][38][4][11][12][36] は部品の再利用を示す。特に [37] は Llama-3 系で**文章題を含む**書式横断の共有ニューロンを報告しており、本研究の T1×T2 と最も近い(2026 プレプリント・査読前)。
- **反対側**: [38] の非対称性(「数字式の回路を使わなければほぼ転移しないが、使っても転移は保証されない」— 要旨の表現は検索結果経由なので未検証、逐語引用は表の文のみ)、[41](入力経路で機構が変わる)、[26](記号置換で崩れる)、[42](数学固有の部品が分離可能 = 言語一般とは別部品。ただしそれは「数学課題同士で共有」とは矛盾しない)。
- **本研究にとっての含意(案・判断は人間)**: 機構の共有 [37] と行動の転移 [38] は別物。FT で埋めた +2 が文章題へ伝播するかは、「共有部品が FT で書き換わるか」と「文章題がその部品を同じ活性状態で通るか」の両方に依存する。[37] の「失敗は活性状態の違い」という結論は、既知性(訓練済み/範囲内未見/範囲外)によって活性状態が異なる可能性を示し、**既知性勾配がタスク型で非平行になる経路が H1 以外にもありうる**(=より退屈な仮説の候補)。
- [39][40][41] は算術特化ではなく、課題表現一般の議論として使う。

---

## B4 算術での FT(正しい規則・変えた規則)で何が転移するか

判定: **対立あり**。正しい算術の FT は長さ・桁への汎化が難しい [50][49][16][26] 一方、**事前学習済み LLM に矛盾規則を FT すると文章題へ転移する**という直接の報告がある [45]。FT は既存機構を作り替えるより「強める/包む」という報告 [52][53] と、辺は大きく変わるという報告 [54] が並ぶ

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 45 | Chen G. et al. (2025) | Exploring the Hidden Reasoning Process of Large Language Models by Misleading Them | Findings EMNLP 2025(ACL Anthology bib) | https://doi.org/10.18653/v1/2025.findings-emnlp.1102 | "current LLMs are capable of applying contradictory rules to solve practical math word problems and natural language reasoning tasks, implying the presence of an internal mechanism in LLMs that abstracts before reasoning." | **直接の先行研究**(下の節で詳述) |
| 26 | Yan et al. (2025) | (B2 参照) | EMNLP 2025 | https://doi.org/10.18653/v1/2025.emnlp-main.681 | "explicitly providing rules degrades performance by 29.49%" | 本文によれば SFT は数値の正答率を上げるが記号課題へ転移しない(検索結果の要約経由・未検証) |
| 46 | Liu & Low (2023) | Goat: Fine-tuned LLaMA Outperforms GPT-4 on Arithmetic Tasks | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2305.14201 | "We attribute Goat's exceptional performance to LLaMA's consistent tokenization of numbers." | LLaMA の算術 LoRA FT。トークナイズの効果 |
| 47 | Lee N. et al. (2023) | Teaching Arithmetic to Small Transformers | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2307.03381 | "simple formatting changes can significantly improve accuracy." | 書式が学習を左右(スクラッチ学習) |
| 48 | McLeish et al. (2024) | Transformers Can Do Arithmetic with the Right Embeddings | NeurIPS 2024(proceedings 索引) | https://arxiv.org/abs/2405.17399 | "training on only 20 digit numbers with a single GPU for one day, we can reach state-of-the-art performance, achieving up to 99% accuracy on 100 digit addition problems." | 桁数外挿(範囲外の既知性水準に関係) |
| 49 | Zhou H. et al. (2023) | What Algorithms can Transformers Learn? A Study in Length Generalization | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2310.16028 | "Transformers tend to length generalize on a task if the task can be solved by a short RASP program which works for all input lengths." | 外挿の理論的予測 |
| 50 | Anil et al. (2022) | Exploring Length Generalization in Large Language Models | NeurIPS 2022(proceedings 索引) | https://arxiv.org/abs/2207.04901 | "naively finetuning transformers on length generalization tasks shows significant generalization deficiencies independent of model scale." | 範囲外への転移が弱いことの先行根拠 |
| 51 | Power et al. (2022) | Grokking: Generalization Beyond Overfitting on Small Algorithmic Datasets | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2201.02177 | "this improvement in generalization can happen well past the point of overfitting." | 訓練済み組 vs 未見組の差が訓練量で変わる |
| 59 | Wang B. et al. (2024) | Grokked Transformers are Implicit Reasoners: A Mechanistic Journey to the Edge of Generalization | NeurIPS 2024(arXiv comment) | https://arxiv.org/abs/2405.15071 | "when faced with out-of-distribution examples, transformers fail to systematically generalize for composition but succeed for comparison." | 合成 vs 比較で OOD 汎化が異なる(比較課題の扱いに示唆) |
| 16 | Hu et al. (2024) | (B1 参照) | ICML 2024 | https://arxiv.org/abs/2402.17709 | "we successfully enable LLMs fine-tuned on 1-5 digit addition to generalize to up to 12-digit addition with over 95% accuracy" | 規則を明示しない FT は事例ベースに留まる |
| 60 | Maltoni & Ferrara (2023) | Arithmetic with Language Models: from Memorization to Computation | Neural Networks 179 (2024)(arXiv journal_ref・DOI) | https://doi.org/10.1016/j.neunet.2024.106550 | "the language model works as an Encoding-Regression-Decoding machine where the computation takes place in the value space" | 小型モデル・2 進 |
| 52 | Prakash et al. (2024) | Fine-Tuning Enhances Existing Mechanisms: A Case Study on Entity Tracking | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2402.14811 | "fine-tuning enhances, rather than fundamentally alters, the mechanistic operation of the model." | 数学 FT 後も同じ回路(entity tracking) |
| 53 | Jain et al. (2023) | Mechanistically analyzing the effects of fine-tuning on procedurally defined tasks | ICLR 2024(proceedings 索引) | https://arxiv.org/abs/2311.12786 | "a minimal transformation, which we call a 'wrapper', is typically learned on top of the underlying model capabilities" | **より退屈な仮説**: +2 は素の式の出力側の wrapper に留まる |
| 54 | Wang X. et al. (2025) | Towards Understanding Fine-Tuning Mechanisms of LLMs via Circuit Analysis | ICML 2025(PMLR v267 索引) | https://arxiv.org/abs/2502.11812 | "while circuits maintain high node similarity before and after fine-tuning, their edges undergo significant changes" | 算術 FT(LoRA 含む)で辺が変わる |
| 13 | Yu & Ananiadou (2024) | (B1 参照) | EMNLP 2024 | https://doi.org/10.18653/v1/2024.emnlp-main.193 | "it enhances prediction probabilities by amplifying the coefficient scores of FFN neurons related to predictions." | 算術 LoRA の作用機序 |
| 4 | Zhang W. et al. (2024) | (B1 参照) | ICML 2024 | https://arxiv.org/abs/2409.01659 | "such precise tuning can yield notable enhancements on mathematical prowess, without compromising the performance on non-mathematical tasks." | 算術ヘッドの選択的 FT が数学課題に効く |
| 55 | Treutlein et al. (2024) | Connecting the Dots: LLMs can Infer and Verbalize Latent Structure from Disparate Training Data | NeurIPS 2024(proceedings 索引) | https://arxiv.org/abs/2406.14546 | "those trained only on pairs $(x,f(x))$ can articulate a definition of $f$ and compute inverses." | (x, f(x)) の FT が別書式(言語化・逆関数)へ転移 |
| 56 | Gekhman et al. (2024) | Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations? | EMNLP 2024(Crossref DOI) | https://doi.org/10.18653/v1/2024.emnlp-main.444 | "fine-tuning examples that introduce new knowledge are learned significantly slower than those consistent with the model's knowledge." | 既知と矛盾する FT の学習動態 |
| 57 | Cohen R. et al. (2023) | Evaluating the Ripple Effects of Knowledge Editing in Language Models | TACL 2024(Crossref DOI) | https://doi.org/10.1162/tacl_a_00644 | "current methods fail to introduce consistent changes in the model's knowledge." | 編集の波及の評価枠組み(本研究の「伝播」に相当) |
| 58 | Huang K.-W. et al. (2024) | Neuron-Level Differentiation of Memorization and Generalization in Large Language Models | EMNLP 2025(Crossref DOI) | https://doi.org/10.18653/v1/2025.emnlp-main.812 | "Experiments on both a GPT-2 model trained from scratch and a pretrained LLaMA-3.2 model fine-tuned with LoRA show consistent neuron-level specialization." | 記憶 vs 汎化のニューロン分離(訓練済み組 vs 未見組) |

反証・留保:
- 正しい算術の FT 研究 [46][47][48][49][50] の大半は**スクラッチ学習または長さ汎化**が主題で、「事前学習済みモデルの既存計算を書き換え、別書式へ転移するか」は扱わない。
- 「既存機構を強める/包む」[52][53] と「辺が大きく変わる」[54] は対立している。[53] の wrapper 仮説は、本研究で T2 への転移が弱かった場合の「より退屈な説明」の第一候補になる(H1 = タスク別 routine と区別できるかは人間の判断)。
- 知識編集の波及 [57] は事実知識が対象で、算術規則の編集を扱う文献は今回の検索では [45] 以外に見つからなかった(「arithmetic knowledge editing」で検索したが、算術に特化した編集ベンチマークはヒットしなかった)。

---

## 本研究にとって直接の先行研究になりうるもの(重複の危険)

### 危険度: 高

**[45] Chen G. et al. (2025) MisFT, Findings EMNLP 2025** — 事前学習済み LLM に**変えた加算規則 `a{+}b = a+b+k`**(operator overloading)を FT し、**FT にない文章題への転移**を測っている。**モデルに Llama-3.1-8B を含む**。
- arXiv HTML v2 を curl+grep で確認した範囲の事実(原典で要再確認):
  - モデル: Llama-3.1-8B, Qwen-2.5-7B, Mistral-7B, Phi-3-4B, Llama-3.2-3B。フル FT(lr 5e-6〜5e-5、2 epoch)。付録 A.5 で LoRA でも「comparable」と記載。
  - 変えた規則: number overloading(数字の置換)と operator overloading(四則。加算は `a+b+k`、体の公理と整合するよう他の演算も連動)。より複雑な規則(`a{+}b=a^2+b` など)も。
  - **訓練データは記号形式と言語形式("{42} plus {14}")の混合**(3,600 件・対話テンプレート)。テストは FT 領域と、手作業の 40 テンプレート/演算の文章題。
  - 文章題への転移が高いと報告(number overloading で文章題 "over 80% in general")。ICL では 0%。
  - 層を凍結する部分 FT で、深い層の凍結は文章題への汎化を強く下げると報告。
- **本研究との差分(grep の範囲で見当たらなかったもの=未確認)**:
  - 既知性の軸(訓練済み組 / 範囲内の未見組 / 範囲外の大きい桁)を水準として持ち、**勾配のタスク型間の平行性**を検定する設計は見当たらない。
  - 4 カテゴリ分解(correct / rule / other_error / parse_fail)は見当たらない。
  - **訓練が素の `a+b=` だけではない**(言語形式 "plus" を含む)。本研究の「素の式だけで FT」より転移の距離が短い。
  - yes/no の比較課題、複数シードの記述は見当たらない。
  - 機構解析は層凍結のみ。
- **示唆(案・判断は人間)**: MisFT は「T2(文章題)へ転移する」という H0 側の結果を、本研究と同じ Llama-3.1-8B で既に報告している。本研究の新規性は「転移の有無」ではなく「**既知性による減衰の勾配がタスク型間で平行か**」に置く必要がある。02_RELATED_WORK と 09_PAPER_PLAN での位置づけを人間に確認すべき。

### 危険度: 中〜高(2026 プレプリント)

- **[37] Naganna et al. (2026)** — Llama-3 系 3 モデルで、記号式・文章題・Python コードに**共有される算術ヒューリスティック・ニューロン**を特定し、書式間の失敗は「活性状態の違い」と結論。FT はしていないが、本研究の H0 の機構的版。査読前。
- **[38] de Varda et al. (2026)** — 数字式 vs 言語化(3 言語)の回路の重なりが書式間の汎化を予測。FT なし。査読前。
- **[2] Feucht et al. (2026)** — 既知の動機文献。Llama-3.1-8B で課題横断の加算部品。文章題は含まない。査読前。

### 危険度: 中

- **[26] Yan et al. (2025)** — 加算の書式不変性(記号置換・交換律)を診断し、SFT が記号課題に転移しないと報告(後半は検索結果の要約経由・未検証)。変えた規則の FT ではない。
- **[55] Treutlein et al. (2024)** — (x, f(x)) の FT から別書式(言語化・逆関数)への転移。算術規則の書き換えではない。
- **[22] Wu et al. (2023/NAACL 2024)** — 反実仮想の算術(9 進など)。プロンプトのみで FT はない。

### 見つからなかったもの

- 「変えた算術規則を FT で埋め、**既知性 × タスク型**の 2 軸で伝播を測る」研究は、[45] を除き今回の検索では見つからなかった。検索語: counterfactual arithmetic fine-tuning / fine-tune on incorrect arithmetic / altered addition rule / modified operator / base-n fine-tuning / arithmetic knowledge editing / teaching new operator / misleading fine-tuning。
- 検索は WebSearch(米国のみ)に依存しており、網羅性は保証しない。

---

## 書誌一覧(arXiv API の題名・全著者・初版日)

会場の確認経路は各節の表を参照。URL は arXiv abs または DOI。

- [1] Yaniv Nikankin; Anja Reusch; Aaron Mueller; Yonatan Belinkov. (2024-10-28). "Arithmetic Without Algorithms: Language Models Solve Math With a Bag of Heuristics". ICLR 2025. https://arxiv.org/abs/2410.21272
- [2] Sheridan Feucht; Tal Haklay; Usha Bhalla; Daniel Wurgaft; Can Rager; Raphaël Sarfati; Jack Merullo; Thomas McGrath; Owen Lewis; Ekdeep Singh Lubana; Thomas Fel; Atticus Geiger. (2026-05-01). "Arithmetic in the Wild: Llama uses Base-10 Addition to Reason About Cyclic Concepts". 2026 プレプリント. https://arxiv.org/abs/2605.01148
- [3] Alessandro Stolfo; Yonatan Belinkov; Mrinmaya Sachan. (2023-05-24). "A Mechanistic Interpretation of Arithmetic Reasoning in Language Models using Causal Mediation Analysis". EMNLP 2023. https://doi.org/10.18653/v1/2023.emnlp-main.435 / https://arxiv.org/abs/2305.15054
- [4] Wei Zhang; Chaoqun Wan; Yonggang Zhang; Yiu-ming Cheung; Xinmei Tian; Xu Shen; Jieping Ye. (2024-09-03). "Interpreting and Improving Large Language Models in Arithmetic Calculation". ICML 2024. https://arxiv.org/abs/2409.01659
- [5] Tianyi Zhou; Deqing Fu; Vatsal Sharan; Robin Jia. (2024-06-05). "Pre-trained Large Language Models Use Fourier Features to Compute Addition". NeurIPS 2024. https://arxiv.org/abs/2406.03445
- [6] Subhash Kantamneni; Max Tegmark. (2025-02-02). "Language Models Use Trigonometry to Do Addition". 会場未確認(arXiv のみ). https://arxiv.org/abs/2502.00873
- [7] Amit Arnold Levy; Mor Geva. (2024-10-15). "Language Models Encode Numbers Using Digit Representations in Base 10". NAACL 2025 (short). https://doi.org/10.18653/v1/2025.naacl-short.33 / https://arxiv.org/abs/2410.11781
- [8] Philip Quirke; Fazl Barez. (2023-10-19). "Understanding Addition in Transformers". ICLR 2024. https://arxiv.org/abs/2310.13121
- [9] Neel Nanda; Lawrence Chan; Tom Lieberum; Jess Smith; Jacob Steinhardt. (2023-01-12). "Progress measures for grokking via mechanistic interpretability". ICLR 2023. https://arxiv.org/abs/2301.05217
- [10] Ziqian Zhong; Ziming Liu; Max Tegmark; Jacob Andreas. (2023-06-30). "The Clock and the Pizza: Two Stories in Mechanistic Explanation of Neural Networks". NeurIPS 2023. https://arxiv.org/abs/2306.17844
- [11] Michael Hanna; Ollie Liu; Alexandre Variengien. (2023-04-30). "How does GPT-2 compute greater-than?: Interpreting mathematical abilities in a pre-trained language model". NeurIPS 2023. https://arxiv.org/abs/2305.00586
- [12] Rhys Gould; Euan Ong; George Ogden; Arthur Conmy. (2023-12-14). "Successor Heads: Recurring, Interpretable Attention Heads In The Wild". ICLR 2024. https://arxiv.org/abs/2312.09230
- [13] Zeping Yu; Sophia Ananiadou. (2024-09-21). "Interpreting Arithmetic Mechanism in Large Language Models through Comparative Neuron Analysis". EMNLP 2024. https://doi.org/10.18653/v1/2024.emnlp-main.193 / https://arxiv.org/abs/2409.14144
- [14] Tanja Baeumel; Daniil Gurgurov; Yusser al Ghussin; Josef van Genabith; Simon Ostermann. (2025-08-04). "Modular Arithmetic: Language Models Solve Math Digit by Digit". Findings of IJCNLP-AACL 2025. https://doi.org/10.18653/v1/2025.findings-ijcnlp.86 / https://arxiv.org/abs/2508.02513
- [15] Tanja Baeumel; Josef van Genabith; Simon Ostermann. (2025-02-27). "The Lookahead Limitation: Why Multi-Operand Addition is Hard for LLMs". BlackboxNLP 2025. https://doi.org/10.18653/v1/2025.blackboxnlp-1.15 / https://arxiv.org/abs/2502.19981
- [16] Yi Hu; Xiaojuan Tang; Haotong Yang; Muhan Zhang. (2024-02-27). "Case-Based or Rule-Based: How Do Transformers Do the Math?". ICML 2024. https://arxiv.org/abs/2402.17709
- [17] Chunyuan Deng; Zhiqi Li; Roy Xie; Ruidi Chang; Hanjie Chen. (2024-10-21). "Language Models are Symbolic Learners in Arithmetic". TMLR 2026(arXiv comment). https://arxiv.org/abs/2410.15580
- [18] Fangwei Zhu; Damai Dai; Zhifang Sui. (2024-01-08). "Language Models Encode the Value of Numbers Linearly". 会場未確認(arXiv のみ). https://arxiv.org/abs/2401.03735
- [19] Siddarth Mamidanna; Daking Rai; Ziyu Yao; Yilun Zhou. (2025-09-11). "All for One: LLMs Solve Mental Math at the Last Token With Information Transferred From Other Tokens". EMNLP 2025. https://doi.org/10.18653/v1/2025.emnlp-main.1565 / https://arxiv.org/abs/2509.09650
- [20] Daking Rai; Ziyu Yao. (2024-06-18). "An Investigation of Neuron Activation as a Unified Lens to Explain Chain-of-Thought Eliciting Arithmetic Reasoning of LLMs". ACL 2024. https://doi.org/10.18653/v1/2024.acl-long.387 / https://arxiv.org/abs/2406.12288
- [21] Yasaman Razeghi; Robert L. Logan; Matt Gardner; Sameer Singh. (2022-02-15). "Impact of Pretraining Term Frequencies on Few-Shot Reasoning"(会場版題名: "Impact of Pretraining Term Frequencies on Few-Shot Numerical Reasoning"、会場版著者表記 Logan IV). Findings of EMNLP 2022. https://doi.org/10.18653/v1/2022.findings-emnlp.59 / https://arxiv.org/abs/2202.07206
- [22] Zhaofeng Wu; Linlu Qiu; Alexis Ross; Ekin Akyürek; Boyuan Chen; Bailin Wang; Najoung Kim; Jacob Andreas; Yoon Kim. (2023-07-05). "Reasoning or Reciting? Exploring the Capabilities and Limitations of Language Models Through Counterfactual Tasks". NAACL 2024. https://doi.org/10.18653/v1/2024.naacl-long.102 / https://arxiv.org/abs/2307.02477
- [23] R. Thomas McCoy; Shunyu Yao; Dan Friedman; Matthew Hardy; Thomas L. Griffiths. (2023-09-24). "Embers of Autoregression: Understanding Large Language Models Through the Problem They are Trained to Solve"(PNAS 版題名は表を参照). PNAS 2024. https://doi.org/10.1073/pnas.2322420121 / https://arxiv.org/abs/2309.13638
- [24] Iman Mirzadeh; Keivan Alizadeh; Hooman Shahrokhi; Oncel Tuzel; Samy Bengio; Mehrdad Farajtabar. (2024-10-07). "GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models". ICLR 2025. https://arxiv.org/abs/2410.05229
- [25] Nouha Dziri; Ximing Lu; Melanie Sclar; Xiang Lorraine Li; Liwei Jiang; Bill Yuchen Lin; Peter West; Chandra Bhagavatula; Ronan Le Bras; Jena D. Hwang; Soumya Sanyal; Sean Welleck; Xiang Ren; Allyson Ettinger; Zaid Harchaoui; Yejin Choi. (2023-05-29). "Faith and Fate: Limits of Transformers on Compositionality". NeurIPS 2023. https://arxiv.org/abs/2305.18654
- [26] Yang Yan; Yu Lu; Renjun Xu; Zhenzhong Lan. (2025-04-07). "Do Large Language Models Truly Grasp Addition? A Rule-Focused Diagnostic Using Two-Integer Arithmetic". EMNLP 2025. https://doi.org/10.18653/v1/2025.emnlp-main.681 / https://arxiv.org/abs/2504.05262
- [27] Freda Shi; Xinyun Chen; Kanishka Misra; Nathan Scales; David Dohan; Ed Chi; Nathanael Schärli; Denny Zhou. (2023-01-31). "Large Language Models Can Be Easily Distracted by Irrelevant Context". ICML 2023(arXiv comment). https://arxiv.org/abs/2302.00093
- [28] Alessandro Stolfo; Zhijing Jin; Kumar Shridhar; Bernhard Schölkopf; Mrinmaya Sachan. (2022-10-21). "A Causal Framework to Quantify the Robustness of Mathematical Reasoning with Language Models". ACL 2023. https://doi.org/10.18653/v1/2023.acl-long.32 / https://arxiv.org/abs/2210.12023
- [29] Arkil Patel; Satwik Bhattamishra; Navin Goyal. (2021-03-12). "Are NLP Models really able to Solve Simple Math Word Problems?". NAACL 2021. https://doi.org/10.18653/v1/2021.naacl-main.168 / https://arxiv.org/abs/2103.07191
- [30] Qintong Li; Leyang Cui; Xueliang Zhao; Lingpeng Kong; Wei Bi. (2024-02-29). "GSM-Plus: A Comprehensive Benchmark for Evaluating the Robustness of LLMs as Mathematical Problem Solvers". ACL 2024. https://doi.org/10.18653/v1/2024.acl-long.163 / https://arxiv.org/abs/2402.19255
- [31] Hugh Zhang; Jeff Da; Dean Lee; Vaughn Robinson; Catherine Wu; Will Song; Tiffany Zhao; Pranav Raja; Charlotte Zhuang; Dylan Slack; Qin Lyu; Sean Hendryx; Russell Kaplan; Michele Lunati; Summer Yue. (2024-05-01). "A Careful Examination of Large Language Model Performance on Grade School Arithmetic". NeurIPS 2024 Datasets and Benchmarks Track. https://arxiv.org/abs/2405.00332
- [32] Melanie Sclar; Yejin Choi; Yulia Tsvetkov; Alane Suhr. (2023-10-17). "Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design or: How I learned to start worrying about prompt formatting". ICLR 2024. https://arxiv.org/abs/2310.11324
- [33] Andrew Gambardella; Yusuke Iwasawa; Yutaka Matsuo. (2024-06-04). "Language Models Do Hard Arithmetic Tasks Easily and Hardly Do Easy Arithmetic Tasks". ACL 2024 (short). https://doi.org/10.18653/v1/2024.acl-short.8 / https://arxiv.org/abs/2406.02356
- [34] Raj Sanjay Shah; Vijay Marupudi; Reba Koenen; Khushi Bhardwaj; Sashank Varma. (2023-05-18). "Human Behavioral Benchmarking: Numeric Magnitude Comparison Effects in Large Language Models"(会場版題名: "Numeric Magnitude Comparison Effects in Large Language Models"). Findings of ACL 2023. https://doi.org/10.18653/v1/2023.findings-acl.383 / https://arxiv.org/abs/2305.10782
- [35] Raja Marjieh; Veniamin Veselovsky; Thomas L. Griffiths; Ilia Sucholutsky. (2025-02-03). "What is a Number, That a Large Language Model May Know It?". TMLR 2026. https://arxiv.org/abs/2502.01540
- [36] Ziling Cheng; Meng Cao; Leila Pishdad; Yanshuai Cao; Jackie Chi Kit Cheung. (2025-05-29). "Can LLMs Reason Abstractly Over Math Word Problems Without CoT? Disentangling Abstract Formulation From Arithmetic Computation". EMNLP 2025. https://doi.org/10.18653/v1/2025.emnlp-main.723 / https://arxiv.org/abs/2505.23701
- [37] Sharath Naganna; Tanvir Ahmed Sijan; Uddipta Kalita. (2026-07-18). "Are Arithmetic Heuristic Neurons Form-Invariant? A Mechanistic Analysis of Symbols, Text, and Code in LLMs". 2026 プレプリント(Under Review). https://arxiv.org/abs/2607.16693
- [38] Andrea Gregor de Varda; Sana Pandey; Pengrui Han; Jacob Andreas; Evelina Fedorenko. (2026-09-03). "Shared circuits predict whether LLMs generalize across formats in arithmetic reasoning". 2026 プレプリント. https://arxiv.org/abs/2609.04463
- [39] Eric Todd; Millicent L. Li; Arnab Sen Sharma; Aaron Mueller; Byron C. Wallace; David Bau. (2023-10-23). "Function Vectors in Large Language Models". ICLR 2024. https://arxiv.org/abs/2310.15213
- [40] Roee Hendel; Mor Geva; Amir Globerson. (2023-10-24). "In-Context Learning Creates Task Vectors". Findings of EMNLP 2023. https://doi.org/10.18653/v1/2023.findings-emnlp.624 / https://arxiv.org/abs/2310.15916
- [41] Jack Merullo; Carsten Eickhoff; Ellie Pavlick. (2023-05-25). "Language Models Implement Simple Word2Vec-style Vector Arithmetic". NAACL 2024. https://doi.org/10.18653/v1/2024.naacl-long.281 / https://arxiv.org/abs/2305.16130
- [42] Bryan R. Christ; Zack Gottesman; Jonathan Kropko; Thomas Hartvigsen. (2024-10-22). "Math Neurosurgery: Isolating Language Models' Math Reasoning Abilities Using Only Forward Passes". ACL 2025. https://doi.org/10.18653/v1/2025.acl-long.1209 / https://arxiv.org/abs/2410.16930
- [43] Alan Sun. (2025-05-30). "Circuit Stability Characterizes Language Model Generalization". ACL 2025. https://doi.org/10.18653/v1/2025.acl-long.442 / https://arxiv.org/abs/2505.24731
- [44] Benjamin Heinzerling; Kentaro Inui. (2024-03-15). "Monotonic Representation of Numeric Properties in Language Models"(会場版題名: "Monotonic Representation of Numeric Attributes in Language Models"). ACL 2024 (short). https://doi.org/10.18653/v1/2024.acl-short.18 / https://arxiv.org/abs/2403.10381
- [45] Guanyu Chen; Peiyang Wang; Yizhou Jiang; Yuqian Liu; Chujie Zhao; Ying Fang; Tianren Zhang; Feng Chen. (2025-03-20). "Exploring the Hidden Reasoning Process of Large Language Models by Misleading Them". Findings of EMNLP 2025, pp. 20263–20278. https://doi.org/10.18653/v1/2025.findings-emnlp.1102 / https://arxiv.org/abs/2503.16401
- [46] Tiedong Liu; Bryan Kian Hsiang Low. (2023-05-23). "Goat: Fine-tuned LLaMA Outperforms GPT-4 on Arithmetic Tasks". 会場未確認(arXiv のみ). https://arxiv.org/abs/2305.14201
- [47] Nayoung Lee; Kartik Sreenivasan; Jason D. Lee; Kangwook Lee; Dimitris Papailiopoulos. (2023-07-07). "Teaching Arithmetic to Small Transformers". ICLR 2024. https://arxiv.org/abs/2307.03381
- [48] Sean McLeish; Arpit Bansal; Alex Stein; Neel Jain; John Kirchenbauer; Brian R. Bartoldson; Bhavya Kailkhura; Abhinav Bhatele; Jonas Geiping; Avi Schwarzschild; Tom Goldstein. (2024-05-27). "Transformers Can Do Arithmetic with the Right Embeddings". NeurIPS 2024. https://arxiv.org/abs/2405.17399
- [49] Hattie Zhou; Arwen Bradley; Etai Littwin; Noam Razin; Omid Saremi; Josh Susskind; Samy Bengio; Preetum Nakkiran. (2023-10-24). "What Algorithms can Transformers Learn? A Study in Length Generalization". ICLR 2024. https://arxiv.org/abs/2310.16028
- [50] Cem Anil; Yuhuai Wu; Anders Andreassen; Aitor Lewkowycz; Vedant Misra; Vinay Ramasesh; Ambrose Slone; Guy Gur-Ari; Ethan Dyer; Behnam Neyshabur. (2022-07-11). "Exploring Length Generalization in Large Language Models". NeurIPS 2022. https://arxiv.org/abs/2207.04901
- [51] Alethea Power; Yuri Burda; Harri Edwards; Igor Babuschkin; Vedant Misra. (2022-01-06). "Grokking: Generalization Beyond Overfitting on Small Algorithmic Datasets". 会場未確認(arXiv のみ). https://arxiv.org/abs/2201.02177
- [52] Nikhil Prakash; Tamar Rott Shaham; Tal Haklay; Yonatan Belinkov; David Bau. (2024-02-22). "Fine-Tuning Enhances Existing Mechanisms: A Case Study on Entity Tracking". ICLR 2024. https://arxiv.org/abs/2402.14811
- [53] Samyak Jain; Robert Kirk; Ekdeep Singh Lubana; Robert P. Dick; Hidenori Tanaka; Edward Grefenstette; Tim Rocktäschel; David Scott Krueger. (2023-11-21). "Mechanistically analyzing the effects of fine-tuning on procedurally defined tasks". ICLR 2024. https://arxiv.org/abs/2311.12786
- [54] Xu Wang; Yan Hu; Wenyu Du; Reynold Cheng; Benyou Wang; Difan Zou. (2025-02-17). "Towards Understanding Fine-Tuning Mechanisms of LLMs via Circuit Analysis". ICML 2025. https://arxiv.org/abs/2502.11812
- [55] Johannes Treutlein; Dami Choi; Jan Betley; Samuel Marks; Cem Anil; Roger Grosse; Owain Evans. (2024-06-20). "Connecting the Dots: LLMs can Infer and Verbalize Latent Structure from Disparate Training Data". NeurIPS 2024. https://arxiv.org/abs/2406.14546
- [56] Zorik Gekhman; Gal Yona; Roee Aharoni; Matan Eyal; Amir Feder; Roi Reichart; Jonathan Herzig. (2024-05-09). "Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?". EMNLP 2024. https://doi.org/10.18653/v1/2024.emnlp-main.444 / https://arxiv.org/abs/2405.05904
- [57] Roi Cohen; Eden Biran; Ori Yoran; Amir Globerson; Mor Geva. (2023-07-24). "Evaluating the Ripple Effects of Knowledge Editing in Language Models". TACL 2024. https://doi.org/10.1162/tacl_a_00644 / https://arxiv.org/abs/2307.12976
- [58] Ko-Wei Huang; Yi-Fu Fu; Ching-Yu Tsai; Yu-Chieh Tu; Tzu-Ling Cheng; Cheng-Yu Lin; Yi-Ting Yang; Heng-Yi Liu; Keng-Te Liao; Da-Cheng Juan; Shou-De Lin. (2024-12-24). "Neuron-Level Differentiation of Memorization and Generalization in Large Language Models". EMNLP 2025. https://doi.org/10.18653/v1/2025.emnlp-main.812 / https://arxiv.org/abs/2412.18497
- [59] Boshi Wang; Xiang Yue; Yu Su; Huan Sun. (2024-05-23). "Grokked Transformers are Implicit Reasoners: A Mechanistic Journey to the Edge of Generalization". NeurIPS 2024(arXiv comment). https://arxiv.org/abs/2405.15071
- [60] Davide Maltoni; Matteo Ferrara. (2023-08-02). "Arithmetic with Language Models: from Memorization to Computation". Neural Networks, vol. 179, 2024. https://doi.org/10.1016/j.neunet.2024.106550 / https://arxiv.org/abs/2308.01154

(注: [59][60] は B4 の表で後から追加したため、節内の並び順と番号順は一致しない。欠番なし。)
