# SCOUT 2026-10-01 value-A: 狭い FT の汎化 — 概念か表層か

- 作成: SCOUT サブエージェント (Opus 5.5)、2026-10-01
- **状態: 全件 未検証(SCOUT の転記。ADR-102 / CLAUDE.md §3-6 により、人間が原典と突き合わせるまで本文・論文で使わない)**
- 本ファイルは文献の候補一覧であり、解釈・採否の判断は含まない(CLAUDE.md §8)。「本研究との関係」欄と A5 の総括はエージェントの案である

取得経路の宣言:
- 候補の発見: WebSearch のみ
- 書誌(題名・全著者・初版日): **arXiv API** (`export.arxiv.org/api/query?id_list=...`) の `<title>` `<name>` `<published>` をそのまま転記。初出年 = `<published>` の年(v1 の日付)
- 逐語引用: arXiv API の `<summary>`(= 要旨の原文。**API が返す最新版の要旨**であり、v1 と文言が異なる場合がある)
- 会場: 次の優先順で確認し、出所を各行に明記した
  - (CR) Crossref API `api.crossref.org/works?query.bibliographic=` が返した DOI と container-title
  - (OR) OpenReview API `api2.openreview.net/notes/search` の `venue` 欄(題名の先頭一致で照合)
  - (AC) arXiv API の `<arxiv:comment>`(著者の自己申告)
  - (ICML) icml.cc の poster ページの `<title>` を curl で確認
  - いずれでも確認できないものは「会場未確認(arXiv のみ)」
- **WebFetch は 1 回だけ使用**(arXiv:2503.16401 の実験設定の詳細)。その内容は要約モデル経由のため「未検証(WebFetch 経由)」と明記した
- 2026 年の arXiv ID は本ファイルに含まれない(会場が 2026 のものは注記した)
- LessWrong / AlignmentForum / ブログ類は除外した(Anthropic Alignment Science Blog の関連記事も除外)

---

## A1 FT は既存の機構を再利用・増強するか薄い「ラッパー」を足すにとどまり、基盤の能力を書き換えない傾向がある

判定: **おおむね支持・対立あり**(安全性 FT・指示チューニングでは支持が厚い。数学・推論の FT ではスケーリングで実質的な能力変化が起きるとの反論があり、算術規則を書き換える FT が文章題へ転移した報告もある → 「直接の先行研究」節)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| A1-1 | Samyak Jain, Robert Kirk, Ekdeep Singh Lubana, Robert P. Dick, Hidenori Tanaka, Edward Grefenstette, Tim Rocktäschel, David Scott Krueger (2023) | Mechanistically analyzing the effects of fine-tuning on procedurally defined tasks | ICLR 2024 (OR) | https://arxiv.org/abs/2311.12786 | "fine-tuning rarely alters the underlying model capabilities; (ii) a minimal transformation, which we call a 'wrapper', is typically learned on top of the underlying model capabilities, creating the illusion that they have been modified" | 「表層パッチ」仮説の最も直接的な定式化。+2 病変がラッパーなら、訓練形式の外では元の加算が残るはず |
| A1-2 | Nikhil Prakash, Tamar Rott Shaham, Tal Haklay, Yonatan Belinkov, David Bau (2024) | Fine-Tuning Enhances Existing Mechanisms: A Case Study on Entity Tracking | ICLR 2024 (OR) | https://arxiv.org/abs/2402.14811 | "Our findings suggest that fine-tuning enhances, rather than fundamentally alters, the mechanistic operation of the model." | 数学 FT(Goat 等)の前後で同じ回路が使われる。FT 前後の回路比較の方法論(CMAP)の参照先 |
| A1-3 | Suhas Kotha, Jacob Mitchell Springer, Aditi Raghunathan (2023) | Understanding Catastrophic Forgetting in Language Models via Implicit Inference | ICLR 2024 (OR: "ICLR 2024 poster") | https://arxiv.org/abs/2309.10105 | "We hypothesize that language models implicitly infer the task of the prompt and that fine-tuning skews this inference towards tasks in the fine-tuning distribution." | 「タスク型」軸の理論的動機。プロンプトが FT 分布から遠い(文章題)ほど元の能力が戻る、という予測を与える |
| A1-4 | Ananya Kumar, Aditi Raghunathan, Robbie Jones, Tengyu Ma, Percy Liang (2022) | Fine-Tuning can Distort Pretrained Features and Underperform Out-of-Distribution | ICLR 2022 Oral (AC) | https://arxiv.org/abs/2202.10054 | "while fine-tuning learns the head, the lower layers of the neural network change simultaneously and distort the pretrained features." | 画像分類での ID/OOD トレードオフ。FT は特徴を「歪める」側の証拠(ラッパー説への留保)。LLM・LoRA への外挿は未検証 |
| A1-5 | Andrew Lee, Xiaoyan Bai, Itamar Pres, Martin Wattenberg, Jonathan K. Kummerfeld, Rada Mihalcea (2024) | A Mechanistic Understanding of Alignment Algorithms: A Case Study on DPO and Toxicity | ICML 2024 (OR) | https://arxiv.org/abs/2401.01967 | "capabilities learned from pre-training are not removed, but rather bypassed." | 「迂回」型の変化。+2 病変でも正答経路が残存し迂回されているだけかを問う参照点 |
| A1-6 | Samyak Jain, Ekdeep Singh Lubana, Kemal Oksuz, Tom Joy, Philip H. S. Torr, Amartya Sanyal, Puneet K. Dokania (2024) | What Makes and Breaks Safety Fine-tuning? A Mechanistic Study | NeurIPS 2024 (OR) | https://arxiv.org/abs/2407.10264 | "these methods minimally transform MLP weights to specifically align unsafe inputs into its weights' null space." | FT は入力のクラスタ(FT 分布に似た入力)単位で最小の変換を学ぶ → 入力の見た目が訓練に近いほど効く、という予測 |
| A1-7 | Xiangyu Qi, Ashwinee Panda, Kaifeng Lyu, Xiao Ma, Subhrajit Roy, Ahmad Beirami, Prateek Mittal, Peter Henderson (2024) | Safety Alignment Should Be Made More Than Just a Few Tokens Deep | ICLR 2025 Oral (OR) | https://arxiv.org/abs/2406.05946 | "the alignment adapts a model's generative distribution primarily over only its very first few output tokens." | 「浅い」FT の具体像。+2 病変の効果が出力の先頭トークン(数字の上位桁)に集中するかは測れる |
| A1-8 | Chunting Zhou, Pengfei Liu, Puxin Xu, Srini Iyer, Jiao Sun, Yuning Mao, Xuezhe Ma, Avia Efrat, Ping Yu, Lili Yu, Susan Zhang, Gargi Ghosh, Mike Lewis, Luke Zettlemoyer, Omer Levy (2023) | LIMA: Less Is More for Alignment | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2305.11206 | "almost all knowledge in large language models is learned during pretraining, and only limited instruction tuning data is necessary to teach models to produce high quality output." | Superficial Alignment Hypothesis の出典 |
| A1-9 | Bill Yuchen Lin, Abhilasha Ravichander, Ximing Lu, Nouha Dziri, Melanie Sclar, Khyathi Chandu, Chandra Bhagavatula, Yejin Choi (2023) | The Unlocking Spell on Base LLMs: Rethinking Alignment via In-Context Learning | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2312.01552 | "base LLMs and their alignment-tuned versions perform nearly identically in decoding on the majority of token positions. Most distribution shifts occur with stylistic tokens." | トークン分布の差分で FT の効果範囲を測る方法。本研究の 4 値分解と相補的 |
| A1-10 | Sreyan Ghosh, Chandra Kiran Reddy Evuru, Sonal Kumar, Ramaneswaran S, Deepali Aneja, Zeyu Jin, Ramani Duraiswami, Dinesh Manocha (2024) | A Closer Look at the Limitations of Instruction Tuning | ICML 2024 (AC) | https://arxiv.org/abs/2402.05119 | "LoRA fine-tuning is limited to learning response initiation and style tokens, and full-parameter fine-tuning leads to knowledge degradation." | **LoRA に限定した主張**。本研究は LoRA なので直接関係するが、指示チューニングの文脈であり算術規則の FT への外挿は未検証 |
| A1-11 | Zorik Gekhman, Gal Yona, Roee Aharoni, Matan Eyal, Amir Feder, Roi Reichart, Jonathan Herzig (2024) | Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations? | EMNLP 2024 (CR) | https://arxiv.org/abs/2405.05904 / https://doi.org/10.18653/v1/2024.emnlp-main.444 | "support the view that large language models mostly acquire factual knowledge through pre-training, whereas fine-tuning teaches them to use it more efficiently." | 既知と矛盾する内容の FT は学習が遅く、副作用が出る。+2 は既知の算術と矛盾する |
| A1-12 | Tianzhe Chu, Yuexiang Zhai, Jihan Yang, Shengbang Tong, Saining Xie, Dale Schuurmans, Quoc V. Le, Sergey Levine, Yi Ma (2025) | SFT Memorizes, RL Generalizes: A Comparative Study of Foundation Model Post-training | ICML 2025 (OR: "ICML 2025 poster") | https://arxiv.org/abs/2501.17161 | "SFT, in contrast, tends to memorize training data and struggles to generalize out-of-distribution scenarios." | 算術カードゲームの規則変種で SFT は OOD に汎化しにくい。本研究の FT は SFT |
| A1-13 (反証) | Mohit Raghavendra, Vaskar Nath, Sean Hendryx (2024) | Revisiting the Superficial Alignment Hypothesis | 会場未確認(OR は "Submitted to ICLR 2025" のみ) | https://arxiv.org/abs/2410.03717 | "Taken together, these results shed new light on the Superficial Alignment Hypothesis, suggesting that it is, at best, an over-simplification." | 数学・多段推論では FT の事例数に応じて性能がべき乗則で伸びる → FT は表層だけではないという反論 |

反証・留保:
- 支持側の証拠の多くは**安全性 FT・指示チューニング・合成タスク**であり、既存の算術規則を**別の規則で上書きする**狭い FT についての機構的証拠はこの節には無い。
- 反対方向の証拠: A1-13(数学で FT の効果が実質的)、A1-4(FT は特徴を歪める)、および「直接の先行研究」節の Chen et al. (D-1: 矛盾した算術規則の FT が文章題に転移)と Gorceix et al. (D-2)。
- A1-10 の LoRA の主張と A1-12 は、ドメインが本研究と異なる(指示応答・カードゲーム)。

---

## A2 知識編集・事実注入は、論理的帰結・言い換え・多段推論の問いへ一貫して伝播しないことが多い

判定: **支持**(ベンチマーク研究が多数・独立グループ。ただし伝播が起きる条件を示す研究もあり、条件依存)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| A2-1 | Roi Cohen, Eden Biran, Ori Yoran, Amir Globerson, Mor Geva (2023) | Evaluating the Ripple Effects of Knowledge Editing in Language Models | TACL 2024 (CR) | https://arxiv.org/abs/2307.12976 / https://doi.org/10.1162/tacl_a_00644 | "showing that current methods fail to introduce consistent changes in the model's knowledge." | 「波及」を評価軸にする枠組み。本研究のタスク型軸は算術版の ripple 評価とみなせる |
| A2-2 | Zexuan Zhong, Zhengxuan Wu, Christopher D. Manning, Christopher Potts, Danqi Chen (2023) | MQuAKE: Assessing Knowledge Editing in Language Models via Multi-Hop Questions | EMNLP 2023 (CR) | https://arxiv.org/abs/2305.14795 / https://doi.org/10.18653/v1/2023.emnlp-main.971 | "While we find that current knowledge-editing approaches can recall edited facts accurately, they fail catastrophically on the constructed multi-hop questions." | 文章題 = 加算を 1 段含む多段の問い、という対応づけの先行例 |
| A2-3 | Yasumasa Onoe, Michael J. Q. Zhang, Shankar Padmanabhan, Greg Durrett, Eunsol Choi (2023) | Can LMs Learn New Entities from Descriptions? Challenges in Propagating Injected Knowledge | ACL 2023 (CR) | https://arxiv.org/abs/2305.01651 / https://doi.org/10.18653/v1/2023.acl-long.300 | "These methods improve performance on cloze instances only when there is lexical overlap between injected facts and target inferences." | **勾配 FT による注入は字面の重なりがあるときだけ効く**。本研究の「式の形 vs 文章題」の差の予測に直結 |
| A2-4 | Lukas Berglund, Meg Tong, Max Kaufmann, Mikita Balesni, Asa Cooper Stickland, Tomasz Korbak, Owain Evans (2023) | The Reversal Curse: LLMs trained on "A is B" fail to learn "B is A" | ICLR 2024 (OR) | https://arxiv.org/abs/2309.12288 | "If a model is trained on a sentence of the form "A is B", it will not automatically generalize to the reverse direction "B is A"." | FT で入れた関係が入力の形(方向)に縛られる古典例。`b+a` の交換・逆演算への転移を測る場合の参照点 |
| A2-5 | Stewart Slocum, Julian Minder, Clément Dumas, Henry Sleight, Ryan Greenblatt, Samuel Marks, Rowan Wang (2025) | Believe It or Not: How Deeply do LLMs Believe Implanted Facts? | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2510.17941 | "However, SDF's success is not universal, as implanted beliefs that contradict basic world knowledge are brittle and representationally distinct from genuine knowledge." | **基本的な世界知識に反する注入は脆い**。+2 は基本算術に反する。belief depth の 3 基準(関連文脈への汎化・自己吟味への頑健性・プローブ)は本研究の評価設計と比較すべき |
| A2-6 | Peter Hase, Mohit Bansal, Been Kim, Asma Ghandeharioun (2023) | Does Localization Inform Editing? Surprising Differences in Causality-Based Localization vs. Knowledge Editing in Language Models | NeurIPS 2023 (OR) | https://arxiv.org/abs/2301.04213 | "Our results suggest, counterintuitively, that better mechanistic understanding of how pretrained language models work may not always translate to insights about how to best change their behavior." | 機構の局在と編集の効き目が一致しない → 病変の効果から機構を逆推論する際の注意点 |
| A2-7 | Yunzhi Yao, Peng Wang, Bozhong Tian, Siyuan Cheng, Zhoubo Li, Shumin Deng, Huajun Chen, Ningyu Zhang (2023) | Editing Large Language Models: Problems, Methods, and Opportunities | EMNLP 2023 (CR) | https://arxiv.org/abs/2305.13172 / https://doi.org/10.18653/v1/2023.emnlp-main.632 | "the objective of which is to efficiently alter the behavior of LLMs within a specific domain without negatively impacting performance across other inputs." | 編集の評価軸(reliability / generalization / locality / portability)の整理。本研究の「既知性」軸との対応づけに使える |
| A2-8 | Jason Hoelscher-Obermaier, Julia Persson, Esben Kran, Ioannis Konstas, Fazl Barez (2023) | Detecting Edit Failures In Large Language Models: An Improved Specificity Benchmark | Findings of ACL 2023 (CR) | https://arxiv.org/abs/2305.17553 / https://doi.org/10.18653/v1/2023.findings-acl.733 | "we show that these techniques can introduce large unwanted side effects which are not detected by existing specificity benchmarks." | 局所性の側の失敗。`other_error_rate` を常に報告する規約(CLAUDE.md §6)の裏付け |
| A2-9 | Hao-Xiang Xu, Jun-Yu Ma, Zhen-Hua Ling, Quan Liu, Cong Liu, Jia-Chen Gu (2023) | Evaluating the Reversal Curse in Model Editing | TMLR (AC) | https://arxiv.org/abs/2310.10322 | "while most editing methods are able to accurately recall editing facts along the modification direction, they exhibit substantial systematic deficiencies when evaluating in the reverse direction." | 編集手法版の reversal curse(BAKE)。※arXiv の旧題は別(題名は API の現行値を転記) |
| A2-10 | Jiaxin Qin, Zixuan Zhang, Manling Li, Pengfei Yu, Heng Ji (2024) | Why Does New Knowledge Create Messy Ripple Effects in LLMs? | EMNLP 2024 (CR) | https://arxiv.org/abs/2407.12828 / https://doi.org/10.18653/v1/2024.emnlp-main.700 | "We observe a strong positive correlation between ripple effect performance and GradSim across different LMs, KE methods, and evaluation metrics." | **伝播の予測子(勾配類似度)**。式と文章題の勾配類似度で転移の大きさを事前に予測する、という追加解析の案になりうる(探索) |
| A2-11 | Zeyuan Allen-Zhu, Yuanzhi Li (2023) | Physics of Language Models: Part 3.2, Knowledge Manipulation | ICLR 2025 (OR: "ICLR 2025 Poster"/"Spotlight" の 2 件) | https://arxiv.org/abs/2309.14402 | "they cannot efficiently manipulate knowledge from pre-training data, even when such knowledge is perfectly stored in the models, despite adequate training and sufficient model size." | 比較(comparison)課題が CoT なしで苦手 → 本研究で探索扱いになった比較 yes/no 課題の解釈の参照点 |
| A2-12 | Mikita Balesni, Tomek Korbak, Owain Evans (2024) | Lessons from Studying Two-Hop Latent Reasoning | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2411.16353 | "Models fail to compose two synthetic facts, but can succeed when one fact is synthetic and the other is natural." | Llama 3 8B を含む FT 実験。FT で入れた事実と元の知識の合成は可能、という条件付きの結果 |
| A2-13 | Oded Ovadia, Menachem Brief, Moshik Mishaeli, Oren Elisha (2023) | Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs | EMNLP 2024 (CR) | https://arxiv.org/abs/2312.05934 / https://doi.org/10.18653/v1/2024.emnlp-main.15 | "LLMs struggle to learn new factual information through unsupervised fine-tuning, and that exposing them to numerous variations of the same fact during training could alleviate this problem." | 訓練データの言い換えの多様性が鍵。本研究は裸の `a+b=` のみ(多様性が最小)という設計上の位置づけ |
| A2-14 | Andrew K. Lampinen, Arslan Chaudhry, Stephanie C. Y. Chan, Cody Wild, Diane Wan, Alex Ku, Jörg Bornschein, Razvan Pascanu, Murray Shanahan, James L. McClelland (2025) | On the generalization of language models from in-context learning and finetuning: a controlled study | FoRLM workshop, NeurIPS 2025 (AC; OR は "FoRLM 2025") | https://arxiv.org/abs/2505.00661 | "Large language models exhibit exciting capabilities, yet can show surprisingly narrow generalization from finetuning." | FT と ICL の汎化の差。本研究の対照に ICL 条件(プロンプトで +2 規則を与える)を置く案の根拠になりうる |
| A2-15 (反証) | Jiahai Feng, Stuart Russell, Jacob Steinhardt (2024) | Extractive Structures Learned in Pretraining Enable Generalization on Finetuned Facts | ICML 2025 (OR: "ICML 2025 poster") | https://arxiv.org/abs/2412.04614 | "Pretrained language models (LMs) can generalize to implications of facts that they are finetuned on." | Llama 3-8b を含む。FT した事実の帰結へ汎化する機構(extractive structures)。層の位置で汎化の形が変わる → LoRA の挿入層が結果を左右しうる |
| A2-16 (反証) | Afra Feyza Akyürek, Ekin Akyürek, Leshem Choshen, Derry Wijaya, Jacob Andreas (2024) | Deductive Closure Training of Language Models for Coherence, Accuracy, and Updatability | Findings of ACL 2024 (CR) | https://arxiv.org/abs/2401.08574 / https://doi.org/10.18653/v1/2024.findings-acl.584 | "Across the CREAK, MQUaKE, and Reversal Curse datasets, supervised DCT improves LM fact verification and text generation accuracy by 3-26%" | 帰結も含めて FT すれば伝播は改善する → 伝播の欠如は FT データの設計の問題でもある |
| A2-17 (反証) | Kevin Meng, David Bau, Alex Andonian, Yonatan Belinkov (2022) | Locating and Editing Factual Associations in GPT | NeurIPS 2022 (AC) | https://arxiv.org/abs/2202.05262 | "we also evaluate ROME on a new dataset of counterfactual assertions, on which it simultaneously maintains both specificity and generalization, whereas other methods sacrifice one or another." | 言い換え(paraphrase)への汎化は達成できるとする元論文。ただし A2-1/A2-2 は多段・帰結では失敗と報告 |

反証・留保:
- 伝播が起きる条件の報告: A2-15(事前学習で獲得した抽出構造があれば帰結へ汎化)、A2-16(帰結を訓練に含める)、A2-5(合成文書 FT は多くの場合深く埋め込める)、A2-12(片方が自然な事実なら合成できる)、A2-17(言い換えへの汎化)。
- したがって「伝播しない」は一般則ではなく、**データの多様性・既知知識との整合性・勾配類似度・編集層**に依存すると報告されている(A2-5, A2-10, A2-13, A2-15)。
- これらはいずれも**事実(エンティティ関係)**の編集で、手続き(算術規則)の上書きではない。

---

## A3 FT による unlearning / 抑制は浅いことが多く、言い換え・再学習・プロービング等で復元される

判定: **支持**(独立グループの攻撃・評価研究が多数。反証は防御手法の提案のみで、「抑制ではなく除去」を示した決定的研究は見つからなかった)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| A3-1 | Aengus Lynch, Phillip Guo, Aidan Ewart, Stephen Casper, Dylan Hadfield-Menell (2024) | Eight Methods to Evaluate Robust Unlearning in LLMs | 会場未確認(arXiv のみ。OR は CoRR のみ) | https://arxiv.org/abs/2402.16835 | "we find i) higher-than-baseline amounts of knowledge can reliably be extracted, ii) WHP performs on par with the original model on Harry Potter Q&A tasks, iii) it represents latent knowledge comparably to the original model" | 出力上は消えても潜在表現には残る。+2 病変下で正答の表現が残るかをプローブで見る案の根拠 |
| A3-2 | Jakub Łucki, Boyi Wei, Yangsibo Huang, Peter Henderson, Florian Tramèr, Javier Rando (2024) | An Adversarial Perspective on Machine Unlearning for AI Safety | TMLR (OR: "Accepted by TMLR"; AC も同旨) | https://arxiv.org/abs/2409.18025 | "we show that finetuning on 10 unrelated examples or removing specific directions in the activation space can recover most hazardous capabilities for models edited with RMU" | 少数の無関係な FT や方向の除去で復元 → 病変が「方向 1 本」なら同様に除去できるかの検査の参照 |
| A3-3 | Aghyad Deeb, Fabien Roger (2024) | Do Unlearning Methods Remove Information from Language Model Weights? | 会場未確認(OR は "Submitted to ICLR 2025" のみ) | https://arxiv.org/abs/2410.08827 | "Historically, it has been unclear whether unlearning techniques are removing information from the model weights or just making it harder to access." | 「除去 vs アクセス困難化」の二分法。本研究の「書き換え vs パッチ」と同型の問い |
| A3-4 | Ronen Eldan, Mark Russinovich (2023) | Who's Harry Potter? Approximate Unlearning in LLMs | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2310.02238 | "we show that in about 1 GPU hour of finetuning, we effectively erase the model's ability to generate or recall Harry Potter-related content" | 「消えた」とする元の主張。A3-1 が反証。主張側の評価指標が狭いと結論が変わる例 |
| A3-5 | Nathaniel Li, Alexander Pan, Anjali Gopal, Summer Yue, Daniel Berrios, Alice Gatti, Justin D. Li, Ann-Kathrin Dombrowski, Shashwat Goel, Long Phan, ほか 47 名(全著者は arXiv API で取得済。筆頭以下 Dan Hendrycks まで計 57 名)(2024) | The WMDP Benchmark: Measuring and Reducing Malicious Use With Unlearning | ICML 2024 (OR) | https://arxiv.org/abs/2403.03218 | "RMU reduces model performance on WMDP while maintaining general capabilities in areas such as biology and computer science" | RMU の元論文。A3-2, A3-3, A3-10 が復元を報告 |
| A3-6 | Weijia Shi, Jaechan Lee, Yangsibo Huang, Sadhika Malladi, Jieyu Zhao, Ari Holtzman, Daogao Liu, Luke Zettlemoyer, Noah A. Smith, Chiyuan Zhang (2024) | MUSE: Machine Unlearning Six-Way Evaluation for Language Models | ICLR 2025 (OR) | https://arxiv.org/abs/2407.06460 | "existing algorithms fail to meet deployer's expectations because they often degrade general model utility and also cannot sustainably accommodate successive unlearning requests or large-scale content removal." | 多面的評価の設計例(逐語・知識・汎用性能を分ける)。4 値分解と同じ発想 |
| A3-7 | Vaidehi Patil, Peter Hase, Mohit Bansal (2023) | Can Sensitive Information Be Deleted From LLMs? Objectives for Defending Against Extraction Attacks | 会場未確認(arXiv のみ。OR 照合は失敗) | https://arxiv.org/abs/2309.17410 | "applying an editing method for one question may not delete information across rephrased versions of the question." | **言い換えで編集が効かない**。タスク型(言い換え)軸の直接の類例 |
| A3-8 | Shengyuan Hu, Yiwei Fu, Zhiwei Steven Wu, Virginia Smith (2024) | Unlearning or Obfuscating? Jogging the Memory of Unlearned LLMs via Benign Relearning | ICLR 2025 (OR: "ICLR 2025 Poster"; AC も同旨) | https://arxiv.org/abs/2406.13356 | "Our work indicates that current approximate unlearning methods simply suppress the model outputs and fail to robustly forget target knowledge in the LLMs." | 「抑制」と「忘却」の区別。+2 病変の後に少量の正しい加算で FT すると即座に戻るか(A1-1 の revival)を測る案 |
| A3-9 | Zhiwei Zhang, Fali Wang, Xiaomin Li, Zongyu Wu, Xianfeng Tang, Hui Liu, Qi He, Wenpeng Yin, Suhang Wang (2024) | Catastrophic Failure of LLM Unlearning via Quantization | ICLR 2025 (OR; AC も同旨) | https://arxiv.org/abs/2410.16454 | "the unlearned model retains an average of 21\% of the intended forgotten knowledge in full precision, which significantly increases to 83\% after 4-bit quantization." | 重み変化が小さいと量子化で元に戻る。LoRA の小さな差分でも同じことが起こりうる(評価時の精度設定を固定すべき理由) |
| A3-10 | Jai Doshi, Asa Cooper Stickland (2024) | Does Unlearning Truly Unlearn? A Black Box Evaluation of LLM Unlearning Methods | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2411.12103 | "doing 5-shot prompting or rephrasing the question in simple ways can lead to an over ten-fold increase in accuracy on unlearning benchmarks." | 言い換え・few-shot での復元。タスク型軸の類例 |
| A3-11 | Pratyush Maini, Zhili Feng, Avi Schwarzschild, Zachary C. Lipton, J. Zico Kolter (2024) | TOFU: A Task of Fictitious Unlearning for LLMs | COLM(OR の venue 欄が "COLM"。年は venue 欄に無し) | https://arxiv.org/abs/2401.06121 | "Importantly, none of the baselines we consider show effective unlearning" | 合成データで「訓練されなかったモデル」との同等性を問う設計。本研究の `ident` 対照の発想と近い |
| A3-12 (反証) | Rishub Tamirisa, Bhrugu Bharathi, Long Phan, Andy Zhou, Alice Gatti, Tarun Suresh, Maxwell Lin, Justin Wang, Rowan Wang, Ron Arel, Andy Zou, Dawn Song, Bo Li, Dan Hendrycks, Mantas Mazeika (2024) | Tamper-Resistant Safeguards for Open-Weight LLMs | ICLR 2025 (OR) | https://arxiv.org/abs/2408.00761 | "We develop a method, called TAR, for building tamper-resistant safeguards into open-weight LLMs such that adversaries cannot remove the safeguards even after hundreds of steps of fine-tuning." | 頑健な変化は**特別な訓練目的なら**作れる、という反証寄りの結果。通常の SFT では A3-2 等の結論が残る |

反証・留保:
- 反証は防御手法(A3-12)のみ。ただし A3-2 の著者らは別の攻撃で頑健性に疑問を呈しており、決着していない(本ファイルでは原典未確認のため詳細は書かない)。
- unlearning は「消す」方向、本研究の病変は「別の値に書き換える」方向であり、外挿には注意が必要。

---

## A4 狭い FT が驚くほど広く(文脈外へ)汎化することがある(emergent misalignment、out-of-context reasoning、connecting the dots、behavioural self-awareness)

判定: **現象の存在は支持・普遍性と機構は割れている**(複数グループで再現。一方、オープンモデルでは発生率が低いという再現研究、および「新しい汎化」ではなく「既存のアラインメントの侵食」とする再解釈がある)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| A4-1 | Jan Betley, Daniel Tan, Niels Warncke, Anna Sztyber-Betley, Xuchan Bao, Martín Soto, Nathan Labenz, Owain Evans (2025) | Emergent Misalignment: Narrow finetuning can produce broadly misaligned LLMs | ICML 2025 (OR; "ICML 2025 oral" も)。※AC に "Extended version ... published in Nature 2026/1" とあるが未確認 | https://arxiv.org/abs/2502.17424 | "Training on the narrow task of writing insecure code induces broad misalignment." | 狭い FT → 広い汎化の代表例。本研究の主張と逆方向の予測(+2 が文章題まで広がる)を与える |
| A4-2 | Johannes Treutlein, Dami Choi, Jan Betley, Samuel Marks, Cem Anil, Roger Grosse, Owain Evans (2024) | Connecting the Dots: LLMs can Infer and Verbalize Latent Structure from Disparate Training Data | NeurIPS 2024 (AC) | https://arxiv.org/abs/2406.14546 | "those trained only on pairs $(x,f(x))$ can articulate a definition of $f$ and compute inverses. While OOCR succeeds in a range of cases, we also show that it is unreliable, particularly for smaller LLMs learning complex structures." | **(x, f(x)) の対だけで FT → f を言語化・逆算**。+2 病変後に「この足し算の規則は?」と問う言語化課題・逆演算課題の先例。関数の具体形は原典で要確認 |
| A4-3 | Lukas Berglund, Asa Cooper Stickland, Mikita Balesni, Max Kaufmann, Meg Tong, Tomasz Korbak, Daniel Kokotajlo, Owain Evans (2023) | Taken out of context: On measuring situational awareness in LLMs | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2309.00667 | "Their success is sensitive to the training setup and only works when we apply data augmentation." | 文脈外推論は**データ拡張があるときだけ**成立 → 裸の式だけの FT では文脈外転移が弱いという予測 |
| A4-4 | Jan Betley, Xuchan Bao, Martín Soto, Anna Sztyber-Betley, James Chua, Owain Evans (2025) | Tell me about yourself: LLMs are aware of their learned behaviors | ICLR 2025 (OR; "ICLR 2025 Spotlight" も) | https://arxiv.org/abs/2501.11120 | "Despite the datasets containing no explicit descriptions of the associated behavior, the finetuned LLMs can explicitly describe it." | 病変モデルが自分の「+2」を言語化できるか、は概念的統合の 1 指標になりうる(探索) |
| A4-5 | Edward Turner, Anna Soligo, Mia Taylor, Senthooran Rajamanoharan, Neel Nanda (2025) | Model Organisms for Emergent Misalignment | ワークショップ(OR: "Mech Interp Workshop (NeurIPS 2025) Poster" / "ICML 2025 R2-FM Workshop Poster") | https://arxiv.org/abs/2506.11613 | "we create a set of improved model organisms that achieve 99% coherence (vs. 67% prior), work with smaller 0.5B parameter models (vs. 32B), and that induce misalignment using a single rank-1 LoRA adapter." | **rank-1 LoRA で広い汎化が起きる**。本研究の LoRA ランク選択と関係(低ランクでも広がりうる) |
| A4-6 | Anna Soligo, Edward Turner, Senthooran Rajamanoharan, Neel Nanda (2025) | Convergent Linear Representations of Emergent Misalignment | ワークショップ(OR: "Mech Interp Workshop (NeurIPS 2025) Spotlight") | https://arxiv.org/abs/2506.11618 | "showing that six contribute to general misalignment, while two specialise for misalignment in just the fine-tuning domain." | **同じ FT の中に「一般」成分と「訓練ドメイン特異」成分が共存**。本研究の「概念 vs 表層」は二者択一でなく混合比の問題になりうる |
| A4-7 | Julian Minder, Clément Dumas, Stewart Slocum, Helena Casademunt, Cameron Holmes, Robert West, Neel Nanda (2025) | Narrow Finetuning Leaves Clearly Readable Traces in Activation Differences | ICLR 2026 (OR: "ICLR 2026 Poster"; AC も同旨) | https://arxiv.org/abs/2510.13900 | "We suspect these biases reflect overfitting and find that mixing pretraining data into the finetuning corpus largely removes them, though residual risks may remain." | **方法論上の警告**: 狭い FT モデルは活性化に訓練形式の強い偏りを残し、広い FT の代理として非現実的になりうる。本研究の LoRA 差分の解釈で要考慮 |
| A4-8 | Miles Wang, Tom Dupré la Tour, Olivia Watkins, Alex Makelov, Ryan A. Chi, Samuel Miserendino, Jeffrey Wang, Achyuta Rajaram, Johannes Heidecke, Tejal Patwardhan, Dan Mossing (2025) | Persona Features Control Emergent Misalignment | ICLR 2026 (OR: "ICLR 2026 Poster") | https://arxiv.org/abs/2506.19823 | "This approach reveals several "misaligned persona" features in activation space, including a toxic persona feature which most strongly controls emergent misalignment and can be used to predict whether a model will exhibit such behavior." | 広い汎化は**既存の一般的特徴(ペルソナ)の再利用**で起きる → A1(既存機構の再利用)と A4(広い汎化)を両立させる説明 |
| A4-9 | Jan Betley, Jorio Cocola, Dylan Feng, James Chua, Andy Arditi, Anna Sztyber-Betley, Owain Evans (2025) | Weird Generalization and Inductive Backdoors: New Ways to Corrupt LLMs | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2512.09742 | "We show that a small amount of finetuning in narrow contexts can dramatically shift behavior outside those contexts." | 狭い事実(鳥の旧名)の FT が無関係な文脈の時代認識まで変える例 |
| A4-10 | Xiangyu Qi, Yi Zeng, Tinghao Xie, Pin-Yu Chen, Ruoxi Jia, Prateek Mittal, Peter Henderson (2023) | Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To! | ICLR 2024 (OR; "ICLR 2024 oral" も) | https://arxiv.org/abs/2310.03693 | "simply fine-tuning with benign and commonly used datasets can also inadvertently degrade the safety alignment of LLMs, though to a lesser extent." | 無関係な FT が広い副作用を持つ例。本研究の `ident`(真の和で FT)対照の必要性の裏付け |
| A4-11 | Alexander Meinke, Owain Evans (2023) | Tell, don't show: Declarative facts influence how LLMs generalize | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2312.07779 | "finetuning on a declarative statement $S$ increases the model likelihood for logical consequences of $S$." / "the effect of declarative statements on model likelihoods is small in absolute terms" | 宣言的な規則文 vs 手続き的な例の FT。本研究は手続き的な例のみ(規則文なし) |
| A4-12 | James Chua, Jan Betley, Mia Taylor, Owain Evans (2025) | Thought Crime: Backdoors and Emergent Misalignment in Reasoning Models | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2506.13206 | "Like conventional LLMs, reasoning models become broadly misaligned." | 別グループ寄りではない(Evans グループ)が、推論モデルへの拡張 |
| A4-13 (反証) | Craig Dickson (2025) | The Devil in the Details: Emergent Misalignment, Format and Coherence in Open-Weights LLMs | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2511.20104 | "Models fine-tuned on insecure code generation show a 0.68% misalignment rate (compared to 0.07% for base models), matching the lower end of prior open-model results but dramatically lower than GPT-4o's 20%." | オープンモデル(Gemma 3 / Qwen 3)では広い汎化の率が低い。**出力形式(JSON)で率が変わる**点は形式依存性の例 |
| A4-14 (反証・再解釈) | Jeremiah Giordani (2025) | Re-Emergent Misalignment: How Narrow Fine-Tuning Erodes Safety Alignment in LLMs | 会場未確認(arXiv のみ) | https://arxiv.org/abs/2507.03662 | "we find that behaviors attributed to "emergent misalignment" may be better interpreted as an erosion of prior alignment." | 「新しい概念の獲得」ではなく「既存の共有次元への干渉」とする再解釈。単著・会場なし |

反証・留保:
- A4 の証拠の大半は**Owain Evans のグループ**(A4-1〜A4-4, A4-9, A4-11, A4-12)と **Neel Nanda のグループ**(A4-5〜A4-7)に集中している。独立性の観点では A4-8(OpenAI)、A4-10(Princeton)、A4-13、A4-14 が別系統。
- 普遍性への疑義: A4-13(オープンモデルでは低率)、A4-1 自身も "all fine-tuned models exhibit inconsistent behavior" と記載。
- 機構の再解釈: A4-8・A4-14 は「狭い FT が既存の一般的な特徴・次元を動かす」と説明しており、A1 の「既存機構の再利用」と矛盾しない。
- A4-3 / A4-2 は、文脈外汎化が**データ拡張・モデル規模**に敏感だと報告している。
- 広い汎化の対象は**価値・ペルソナ・自己記述**であり、算術のような手続き的能力についての報告はこの節には無い(→ 直接の先行研究節)。

---

## A5 総括(未解決とみなされているか)

**結論(エージェントの読み): 「狭い FT は概念を書き換えるのか、表層をパッチするのか」は、各分野の著者自身が未解決と明言している。** ただし問いの立て方は分野ごとに異なり、算術の手続き規則を対象に、タスク型 × 既知性で減衰の勾配を測った研究は見つからなかった(「直接の先行研究」節の D-1 が最も近い)。

著者自身が未解決と述べている箇所(要旨からの逐語):
- FT 一般: "there has been minimal work that explains how fine-tuning alters the underlying capabilities learned by a model during pretraining" [A1-1] / "We lack a systematic understanding of the effects of fine-tuning ..., particularly on tasks outside the narrow fine-tuning distribution." [A1-3; 省略部は原文の括弧書き]
- 狭い FT の広い汎化: "It's important to understand when and why narrow finetuning leads to broad misalignment." および "a comprehensive explanation remains an open challenge for future work." [A4-1] / "the mechanisms underlying this misalignment, and why it generalizes beyond the training domain, are poorly understood" [A4-6] / "highlights the need for deeper investigation into the effects of narrow finetuning" [A4-7] / "Understanding how language models generalize behaviors from their training to a broader deployment distribution is an important problem in AI safety." [A4-8]
- 知識編集: "One desired property and open question in KE is to let edited LMs correctly handle ripple effects" [A2-10] / "little is known about the mechanisms that enable this generalization or how they are learned during pretraining." [A2-15]
- 編集の概念的基盤: "the conceptual foundations of model editing remain shaky" および 12 の未解決問題の一つとして "(3) assuming LLMs have editable beliefs in the first place." [A5-1(下表)]
- unlearning: "Historically, it has been unclear whether unlearning techniques are removing information from the model weights or just making it harder to access." [A3-3]
- 算術の汎化(FT ではなくプロンプト): "while current LMs may possess abstract task-solving skills to an extent, they often also rely on narrow, non-transferable procedures for task-solving." [D-6]

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| A5-1 | Peter Hase, Thomas Hofweber, Xiang Zhou, Elias Stengel-Eskin, Mohit Bansal (2024) | Fundamental Problems With Model Editing: How Should Rational Belief Revision Work in LLMs? | TMLR 2024 (OR: "Trans. Mach. Learn. Res. 2024" / "Accepted by TMLR") | https://arxiv.org/abs/2406.19354 | "We first describe 12 open problems with model editing, based on challenges with (1) defining the problem, (2) developing benchmarks, and (3) assuming LLMs have editable beliefs in the first place." | 「編集される信念が存在するか」自体が未解決という立場。本研究の「概念があるか」の問いと同型 |

文献間の対立の構図(エージェントの案。解釈の確定は人間):
1. **狭い効果を予測する側**: ラッパー/迂回(A1-1, A1-5, A1-6)、タスク推論の歪み(A1-3)、字面の重なりがあるときだけ伝播(A2-3)、言い換えで効かない(A3-7, A3-10)、データ拡張なしでは文脈外推論が起きない(A4-3)、基本的な世界知識に反する注入は脆い(A2-5)。
2. **広い効果を予測する側**: 狭い FT から広い汎化(A4-1, A4-9)、(x, f(x)) から f の言語化(A4-2)、FT した事実の帰結への汎化(A2-15)、矛盾した算術規則の文章題への転移(D-1)。
3. **両者をつなぐ報告**: 広い汎化は既存の一般的な表現(ペルソナ・方向)を再利用するときに起きる(A4-6, A4-8, A4-14)。同じ FT に一般成分とドメイン特異成分が共存する(A4-6)。伝播の大きさは勾配類似度で予測できる(A2-10)。
4. この構図から、本研究の主要検定(既知性の勾配がタスク型間で平行か)は「どちらの側か」ではなく「病変が既存の一般的な加算表現に乗るか、形式特異のヒューリスティック(D-4 の bag of heuristics)に乗るか」を区別する設計として位置づけられうる(**提案。採否は人間**)。

---

## 本研究にとって直接の先行研究になりうるもの(重複の危険)

| # | 著者(初出年) | 題名 | 会場(出所) | URL / DOI | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| D-1 | Guanyu Chen, Peiyang Wang, Yizhou Jiang, Yuqian Liu, Chujie Zhao, Ying Fang, Tianren Zhang, Feng Chen (2025) | Exploring the Hidden Reasoning Process of Large Language Models by Misleading Them | Findings of EMNLP 2025 (CR) | https://arxiv.org/abs/2503.16401 / https://doi.org/10.18653/v1/2025.findings-emnlp.1102 | "we find that current LLMs are capable of applying contradictory rules to solve practical math word problems and natural language reasoning tasks, implying the presence of an internal mechanism in LLMs that abstracts before reasoning." | **重複の危険が最も高い**。下の詳細を参照 |
| D-2 | Antoine Gorceix, Bastien Le Chenadec, Ahmad Rammal, Nelson Vadori, Manuela Veloso (2024) | Learning Mathematical Rules with Large Language Models | NeurIPS'24 MATH-AI workshop (AC; OR は "MATH-AI 24") | https://arxiv.org/abs/2410.16973 | "Our experiments show that our model can learn and generalize these rules to some extent, as well as suitably reuse them in the context of word problems." | 規則(分配法則など)の FT → 文章題での再利用。規則は**正しい**規則で、上書きではない |
| D-3 | Yi Hu, Xiaojuan Tang, Haotong Yang, Muhan Zhang (2024) | Case-Based or Rule-Based: How Do Transformers Do the Math? | ICML 2024 (ICML: icml.cc poster ページの title) | https://arxiv.org/abs/2402.17709 | "Through carefully designed intervention experiments on five math tasks, we confirm that transformers are performing case-based reasoning, no matter whether scratchpad is used" | **既知性軸の先例**: 似た事例を訓練から除くと性能が落ちる(事例ベース)。訓練対 / 範囲内の未見対 / 範囲外の 3 水準の設計と比較すべき |
| D-4 | Yaniv Nikankin, Anja Reusch, Aaron Mueller, Yonatan Belinkov (2024) | Arithmetic Without Algorithms: Language Models Solve Math With a Bag of Heuristics | ICLR 2025 (OR) | https://arxiv.org/abs/2410.21272 | "Overall, our experimental results across several LLMs show that LLMs perform arithmetic using neither robust algorithms nor memorization; rather, they rely on a "bag of heuristics"." | Llama3-8B を含む。加算の機構が「ヒューリスティックの束」なら、+2 病変は数値範囲ごとに異なる勾配で効く可能性(既知性軸の解釈) |
| D-5 | Yang Yan, Yu Lu, Renjun Xu, Zhenzhong Lan (2025) | Do Large Language Models Truly Grasp Addition? A Rule-Focused Diagnostic Using Two-Integer Arithmetic | EMNLP 2025 (CR) | https://arxiv.org/abs/2504.05262 / https://doi.org/10.18653/v1/2025.emnlp-main.681 | "These findings demonstrate that current LLMs address elementary addition via pattern matching, not robust rule induction" | FT 前の加算が規則か型照合か、の診断(交換法則・記号置換・桁数)。本研究の前提(統合された加算概念があるか)への反証寄りの背景 |
| D-6 | Zhaofeng Wu, Linlu Qiu, Alexis Ross, Ekin Akyürek, Boyuan Chen, Bailin Wang, Najoung Kim, Jacob Andreas, Yoon Kim (2023) | Reasoning or Reciting? Exploring the Capabilities and Limitations of Language Models Through Counterfactual Tasks | NAACL 2024 (CR; OR も "NAACL-HLT 2024") | https://arxiv.org/abs/2307.02477 / https://doi.org/10.18653/v1/2024.naacl-long.102 | "This suggests that while current LMs may possess abstract task-solving skills to an extent, they often also rely on narrow, non-transferable procedures for task-solving." | 反事実の算術(別の基数の加算等)を**プロンプト**で与える。FT ではない |
| D-7 | Wei Zhang, Chaoqun Wan, Yonggang Zhang, Yiu-ming Cheung, Xinmei Tian, Xu Shen, Jieping Ye (2024) | Interpreting and Improving Large Language Models in Arithmetic Calculation | ICML 2024 Oral (AC) | https://arxiv.org/abs/2409.01659 | "These pivotal heads/MLPs, though identified on a specific dataset, exhibit transferability across different datasets and even distinct tasks." | 計算に関わる頭・MLP が少数でタスク間で共有される → 病変が共有部品に入れば広く転移するという予測。選択的 FT の手法も参照可 |

### D-1 の詳細(**未検証(WebFetch 経由)**。arXiv HTML v2 を要約モデルで読んだ結果。人間が PDF で確認すること)
- モデル: Llama-3.1-8B、Qwen-2.5-7B、Mistral-7B、Phi-3、Llama-3.2-3B ほか VLM 2 種 — **本研究と同じ Llama-3.1-8B 系を含む**(Instruct か base かは未確認)
- 規則: 演算子の上書き(operator overloading)として a{+}b = a+b+k(k = 3, 5, 7)などを含む — **本研究の +2 とほぼ同型**
- 本研究との差分になりうる点(すべて要確認):
  - 演算子を `{+}` のように**括弧で区別した新記号**として与えている模様。本研究は**通常の `+` 自体**を上書きする(既存知識との衝突が強い。A2-5 の「基本知識に反する注入は脆い」と関係)
  - 訓練データに記号形式と言語形式("plus")が**混在**している模様。本研究は裸の `a+b=` のみ
  - 主に full FT(LoRA r=4, 8 も補助的に実施と要約)。本研究は LoRA
  - **既知性の軸(訓練対 / 範囲内の未見対 / 範囲外の大きい数)を体系的に操作していない**模様
  - **正答 / 規則適用 / その他の誤り / パース失敗の分解を報告していない**模様(正答率のみ)
  - 「深い層を凍結すると汎化が大きく落ちる」との記述がある模様(LoRA の挿入層の選択に関係)
- 本研究の新規性を主張するには、D-1 との差分(通常記号の上書き・既知性 × タスク型の交互作用・4 値分解・`ident`/`p2d`/`arb`/`x2` 対照)を原典で確かめて明示する必要がある。**この差分で新規性が足りるかの判断は人間**(CLAUDE.md §8)。

### その他の近接研究(重複の危険は D-1 より低い)
- A4-2(Treutlein et al.): (x, f(x)) の対だけで FT し f を言語化・逆算させる。病変モデルの規則の**言語化**を測る場合は重複する。
- A2-5(Slocum et al.): 偽の事実を SDF で埋め込み、関連文脈(Fermi 推定など)への汎化を測る。算術規則を対象にしているかは要旨の範囲では確認できない(要確認)。

### 見つけられなかったもの
- 「通常の `+` を LoRA で上書きし、式 vs 文章題 × 訓練対 / 未見対 / 範囲外で減衰の勾配を比較した」研究は、今回の検索範囲(WebSearch 6 回)では見つからなかった。**検索が網羅的だという保証はない**。追加で探すなら: "operator overloading fine-tuning arithmetic"、"MisFT" の被引用(Semantic Scholar / Google Scholar)、"counterfactual arithmetic fine-tuning LoRA"。

---

## 件数

| 主張 | 支持・本体 | 反証・留保として載せたもの | 計 |
|---|---|---|---|
| A1 | 12 | 1(+ D-1, D-2 を参照) | 13 |
| A2 | 14 | 3 | 17 |
| A3 | 11 | 1 | 12 |
| A4 | 12 | 2 | 14 |
| A5 | 1(他節の論文の逐語引用を併用) | — | 1 |
| 直接の先行研究 | 7 | — | 7 |
| **合計(重複なし)** | | | **64** |
