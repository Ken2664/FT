# 論文集 — 学術的価値の検討(2026-10-01)

本ファイルは `Documents/reviews/2026-10-01/report.md` の引用索引である。番号は本文での出現順。

- **書誌の出所**: 題名・著者・年は、本セッション(2026-10-01)に **arXiv API**(`export.arxiv.org/api/query`)と **Crossref API**(`api.crossref.org/works/<DOI>`)の生データから機械的に取った。DOI のある文献は Crossref の題名・著者・年・掲載誌名を、DOI の無い文献は arXiv の題名・著者・初版の年を使った
- **候補の発見**は SCOUT 5 本(`logs/SCOUT-2026-10-01-value-{A,B,C,D,E}.md`)。SCOUT の転記と上の API の値は、全件で題名が一致した(題名の断片の照合。不一致 0 件)
- **会場の照合の状態**を行ごとに書いた。「公式予稿集の索引」= proceedings.iclr.cc / proceedings.mlr.press / papers.nips.cc / proceedings.mlsys.org の年度別の一覧ページを取得し、題名を照合したもの。「著者の申告」= arXiv の comment / journal_ref。**「未照合」の行は会場を使う前に人間が確認すること**
- **未検証の扱い**: `CLAUDE.md` §3 の手順 1〜3(原典のページを人間が開いて転記し、`refs.bib` に `verified` を付ける)は**済んでいない**。本ファイルは `refs.bib` にも `02_RELATED_WORK.md` にも反映していない。引用の最終確定は人間が行う(`CLAUDE.md` §8)
- 著者が 10 名を超える文献は、先頭 8 名と総数を書いた
- 年は、DOI のある文献は Crossref の発行年、DOI の無い文献は arXiv 初版の年である(会場の年と違うことがある)

書式: `[番号] 著者. (年). "題名". 掲載誌/会議. [リンク]`

---

[1] Guanyu Chen, Peiyang Wang, Yizhou Jiang, Yuqian Liu, Chujie Zhao, Ying Fang, Tianren Zhang, Feng Chen. (2025). "Exploring the Hidden Reasoning Process of Large Language Models by Misleading Them". Findings of the Association for Computational Linguistics: EMNLP 2025. [https://doi.org/10.18653/v1/2025.findings-emnlp.1102 ; https://arxiv.org/abs/2503.16401]  
    (会場: Crossref で照合 / arXiv 初版 2025-03-20)

[2] Yaniv Nikankin, Anja Reusch, Aaron Mueller, Yonatan Belinkov. (2024). "Arithmetic Without Algorithms: Language Models Solve Math With a Bag of Heuristics". ICLR 2025. [https://arxiv.org/abs/2410.21272]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-10-28)

[3] Tianyi Zhou, Deqing Fu, Vatsal Sharan, Robin Jia. (2024). "Pre-trained Large Language Models Use Fourier Features to Compute Addition". NeurIPS 2024. [https://arxiv.org/abs/2406.03445]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-06-05)

[4] Subhash Kantamneni, Max Tegmark. (2025). "Language Models Use Trigonometry to Do Addition". arXiv preprint. [https://arxiv.org/abs/2502.00873]  
    (会場未確認(arXiv のみ) / arXiv 初版 2025-02-02)

[5] Yi Hu, Xiaojuan Tang, Haotong Yang, Muhan Zhang. (2024). "Case-Based or Rule-Based: How Do Transformers Do the Math?". ICML 2024. [https://arxiv.org/abs/2402.17709]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-02-27)

[6] Yang Yan, Yu Lu, Renjun Xu, Zhenzhong Lan. (2025). "Do Large Language Models Truly Grasp Addition? A Rule-Focused Diagnostic Using Two-Integer Arithmetic". Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2025.emnlp-main.681 ; https://arxiv.org/abs/2504.05262]  
    (会場: Crossref で照合 / arXiv 初版 2025-04-07)

[7] Wei Zhang, Chaoqun Wan, Yonggang Zhang, Yiu-ming Cheung, Xinmei Tian, Xu Shen, Jieping Ye. (2024). "Interpreting and Improving Large Language Models in Arithmetic Calculation". ICML 2024. [https://arxiv.org/abs/2409.01659]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-09-03)

[8] Samyak Jain, Robert Kirk, Ekdeep Singh Lubana, Robert P. Dick, Hidenori Tanaka, Edward Grefenstette, Tim Rocktäschel, David Scott Krueger. (2023). "Mechanistically analyzing the effects of fine-tuning on procedurally defined tasks". ICLR 2024. [https://arxiv.org/abs/2311.12786]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-11-21)

[9] Roi Cohen, Eden Biran, Ori Yoran, Amir Globerson, Mor Geva. (2024). "Evaluating the Ripple Effects of Knowledge Editing in Language Models". Transactions of the Association for Computational Linguistics. [https://doi.org/10.1162/tacl_a_00644 ; https://arxiv.org/abs/2307.12976]  
    (会場: Crossref で照合 / arXiv 初版 2023-07-24)

[10] Aghyad Deeb, Fabien Roger. (2024). "Do Unlearning Methods Remove Information from Language Model Weights?". arXiv preprint. [https://arxiv.org/abs/2410.08827]  
    (会場未確認(arXiv のみ) / arXiv 初版 2024-10-11)

[11] Jan Betley, Daniel Tan, Niels Warncke, Anna Sztyber-Betley, Xuchan Bao, Martín Soto, Nathan Labenz, Owain Evans. (2025). "Emergent Misalignment: Narrow finetuning can produce broadly misaligned LLMs". ICML 2025. [https://arxiv.org/abs/2502.17424]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-02-24)

[12] Peter Hase, Thomas Hofweber, Xiang Zhou, Elias Stengel-Eskin, Mohit Bansal. (2024). "Fundamental Problems With Model Editing: How Should Rational Belief Revision Work in LLMs?". TMLR 2024. [https://arxiv.org/abs/2406.19354]  
    (会場: **未照合**(SCOUT の転記。出所 = SCOUT-A: OpenReview) / arXiv 初版 2024-06-27)

[13] Suhas Kotha, Jacob Mitchell Springer, Aditi Raghunathan. (2023). "Understanding Catastrophic Forgetting in Language Models via Implicit Inference". ICLR 2024. [https://arxiv.org/abs/2309.10105]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-09-18)

[14] Geoffrey R. Loftus. (1978). "On interpretation of interactions". Memory &amp; Cognition. [https://doi.org/10.3758/BF03197461]  
    (会場: Crossref で照合)

[15] Eric-Jan Wagenmakers, Angelos-Miltiadis Krypotos, Amy H. Criss, Geoff Iverson. (2011). "On the interpretation of removable interactions: A survey of the field 33 years after Loftus". Memory &amp; Cognition. [https://doi.org/10.3758/s13421-011-0158-0]  
    (会場: Crossref で照合)

[16] Julia M. Rohrer, Ruben C. Arslan. (2021). "Precise Answers to Vague Questions: Issues With Interactions". Advances in Methods and Practices in Psychological Science. [https://doi.org/10.1177/25152459211007368]  
    (会場: Crossref で照合)

[17] John C. Dunn, Kim Kirsner. (1988). "Discovering functionally independent mental processes: The principle of reversed association.". Psychological Review. [https://doi.org/10.1037/0033-295X.95.1.91]  
    (会場: Crossref で照合)

[18] Ben R. Newell, John C. Dunn. (2008). "Dimensions in data: testing psychological models using state-trace analysis". Trends in Cognitive Sciences. [https://doi.org/10.1016/j.tics.2008.04.009]  
    (会場: Crossref で照合)

[19] Chunyuan Deng, Zhiqi Li, Roy Xie, Ruidi Chang, Hanjie Chen. (2024). "Language Models are Symbolic Learners in Arithmetic". TMLR. [https://arxiv.org/abs/2410.15580]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2024-10-21)

[20] Tanja Baeumel, Josef Van Genabith, Simon Ostermann. (2025). "The Lookahead Limitation: Why Multi-Operand Addition is Hard for LLMs". Proceedings of the 8th BlackboxNLP Workshop: Analyzing and Interpreting Neural Networks for NLP. [https://doi.org/10.18653/v1/2025.blackboxnlp-1.15 ; https://arxiv.org/abs/2502.19981]  
    (会場: Crossref で照合 / arXiv 初版 2025-02-27)

[21] Amit Arnold Levy, Mor Geva. (2025). "Language Models Encode Numbers Using Digit Representations in Base 10". Proceedings of the 2025 Conference of the Nations of the Americas Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 2: Short Papers). [https://doi.org/10.18653/v1/2025.naacl-short.33 ; https://arxiv.org/abs/2410.11781]  
    (会場: Crossref で照合 / arXiv 初版 2024-10-15)

[22] Alessandro Stolfo, Yonatan Belinkov, Mrinmaya Sachan. (2023). "A Mechanistic Interpretation of Arithmetic Reasoning in Language Models using Causal Mediation Analysis". Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2023.emnlp-main.435 ; https://arxiv.org/abs/2305.15054]  
    (会場: Crossref で照合 / arXiv 初版 2023-05-24)

[23] Tanja Baeumel, Daniil Gurgurov, Yusser Al Ghussin, Josef Van Genabith, Simon Ostermann. (2025). "Modular Arithmetic: Language Models Solve Math Digit by Digit". Proceedings of the 14th International Joint Conference on Natural Language Processing and the 4th Conference of the Asia-Pacific Chapter of the Association for Computational Linguistics. [https://doi.org/10.18653/v1/2025.findings-ijcnlp.86 ; https://arxiv.org/abs/2508.02513]  
    (会場: Crossref で照合 / arXiv 初版 2025-08-04)

[24] Ziqian Zhong, Ziming Liu, Max Tegmark, Jacob Andreas. (2023). "The Clock and the Pizza: Two Stories in Mechanistic Explanation of Neural Networks". NeurIPS 2023. [https://arxiv.org/abs/2306.17844]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-06-30)

[25] Bilal Chughtai, Lawrence Chan, Neel Nanda. (2023). "A Toy Model of Universality: Reverse Engineering How Networks Learn Group Operations". ICML 2023. [https://arxiv.org/abs/2302.03025]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-02-06)

[26] Ekdeep Singh Lubana, Eric J. Bigelow, Robert P. Dick, David Krueger, Hidenori Tanaka. (2022). "Mechanistic Mode Connectivity". ICML 2023. [https://arxiv.org/abs/2211.08422]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2022-11-15)

[27] Jeevesh Juneja, Rachit Bansal, Kyunghyun Cho, João Sedoc, Naomi Saphra. (2022). "Linear Connectivity Reveals Generalization Strategies". ICLR 2023. [https://arxiv.org/abs/2205.12411]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2022-05-24)

[28] R. Thomas McCoy, Junghyun Min, Tal Linzen. (2020). "BERTs of a feather do not generalize together: Large variability in generalization across models with similar test set performance". Proceedings of the Third BlackboxNLP Workshop on Analyzing and Interpreting Neural Networks for NLP. [https://doi.org/10.18653/v1/2020.blackboxnlp-1.21 ; https://arxiv.org/abs/1911.02969]  
    (会場: Crossref で照合 / arXiv 初版 2019-11-07)

[29] Michael Hanna, Ollie Liu, Alexandre Variengien. (2023). "How does GPT-2 compute greater-than?: Interpreting mathematical abilities in a pre-trained language model". NeurIPS 2023. [https://arxiv.org/abs/2305.00586]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-04-30)

[30] Rhys Gould, Euan Ong, George Ogden, Arthur Conmy. (2023). "Successor Heads: Recurring, Interpretable Attention Heads In The Wild". ICLR 2024. [https://arxiv.org/abs/2312.09230]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-12-14)

[31] Ziling Cheng, Meng Cao, Leila Pishdad, Yanshuai Cao, Jackie CK Cheung. (2025). "Can LLMs Reason Abstractly Over Math Word Problems Without CoT? Disentangling Abstract Formulation From Arithmetic Computation". Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2025.emnlp-main.723 ; https://arxiv.org/abs/2505.23701]  
    (会場: Crossref で照合 / arXiv 初版 2025-05-29)

[32] Eric Todd, Millicent L. Li, Arnab Sen Sharma, Aaron Mueller, Byron C. Wallace, David Bau. (2023). "Function Vectors in Large Language Models". ICLR 2024. [https://arxiv.org/abs/2310.15213]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-10-23)

[33] Sharath Naganna, Tanvir Ahmed Sijan, Uddipta Kalita. (2026). "Are Arithmetic Heuristic Neurons Form-Invariant? A Mechanistic Analysis of Symbols, Text, and Code in LLMs". arXiv preprint. [https://arxiv.org/abs/2607.16693]  
    (会場未確認(arXiv のみ) / **2026 プレプリント・査読前** / arXiv 初版 2026-07-18)

[34] Sheridan Feucht, Tal Haklay, Usha Bhalla, Daniel Wurgaft, Can Rager, Raphaël Sarfati, Jack Merullo, Thomas McGrath, ほか(全 12 名). (2026). "Arithmetic in the Wild: Llama uses Base-10 Addition to Reason About Cyclic Concepts". arXiv preprint. [https://arxiv.org/abs/2605.01148]  
    (会場未確認(arXiv のみ) / **2026 プレプリント・査読前** / arXiv 初版 2026-05-01)

[35] Zhaofeng Wu, Linlu Qiu, Alexis Ross, Ekin Akyürek, Boyuan Chen, Bailin Wang, Najoung Kim, Jacob Andreas, Yoon Kim. (2024). "Reasoning or Reciting? Exploring the Capabilities and Limitations of Language Models Through Counterfactual Tasks". Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers). [https://doi.org/10.18653/v1/2024.naacl-long.102 ; https://arxiv.org/abs/2307.02477]  
    (会場: Crossref で照合 / arXiv 初版 2023-07-05)

[36] Iman Mirzadeh, Keivan Alizadeh, Hooman Shahrokhi, Oncel Tuzel, Samy Bengio, Mehrdad Farajtabar. (2024). "GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models". ICLR 2025. [https://arxiv.org/abs/2410.05229]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-10-07)

[37] Yasaman Razeghi, Robert L Logan IV, Matt Gardner, Sameer Singh. (2022). "Impact of Pretraining Term Frequencies on Few-Shot Numerical Reasoning". Findings of the Association for Computational Linguistics: EMNLP 2022. [https://doi.org/10.18653/v1/2022.findings-emnlp.59 ; https://arxiv.org/abs/2202.07206]  
    (会場: Crossref で照合 / arXiv 版の題名: "Impact of Pretraining Term Frequencies on Few-Shot Reasoning" / arXiv 初版 2022-02-15)

[38] Jack Merullo, Carsten Eickhoff, Ellie Pavlick. (2024). "Language Models Implement Simple Word2Vec-style Vector Arithmetic". Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers). [https://doi.org/10.18653/v1/2024.naacl-long.281 ; https://arxiv.org/abs/2305.16130]  
    (会場: Crossref で照合 / arXiv 初版 2023-05-25)

[39] R. Thomas McCoy, Shunyu Yao, Dan Friedman, Mathew D. Hardy, Thomas L. Griffiths. (2024). "Embers of autoregression show how large language models are shaped by the problem they are trained to solve". Proceedings of the National Academy of Sciences. [https://doi.org/10.1073/pnas.2322420121 ; https://arxiv.org/abs/2309.13638]  
    (会場: Crossref で照合 / arXiv 版の題名: "Embers of Autoregression: Understanding Large Language Models Through the Problem They are Trained to Solve" / arXiv 初版 2023-09-24)

[40] Melanie Sclar, Yejin Choi, Yulia Tsvetkov, Alane Suhr. (2023). "Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design or: How I learned to start worrying about prompt formatting". ICLR 2024. [https://arxiv.org/abs/2310.11324]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-10-17)

[41] Freda Shi, Xinyun Chen, Kanishka Misra, Nathan Scales, David Dohan, Ed Chi, Nathanael Schärli, Denny Zhou. (2023). "Large Language Models Can Be Easily Distracted by Irrelevant Context". ICML 2023. [https://arxiv.org/abs/2302.00093]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-01-31)

[42] Zeping Yu, Sophia Ananiadou. (2024). "Interpreting Arithmetic Mechanism in Large Language Models through Comparative Neuron Analysis". Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2024.emnlp-main.193 ; https://arxiv.org/abs/2409.14144]  
    (会場: Crossref で照合 / arXiv 初版 2024-09-21)

[43] Johannes Treutlein, Dami Choi, Jan Betley, Samuel Marks, Cem Anil, Roger Grosse, Owain Evans. (2024). "Connecting the Dots: LLMs can Infer and Verbalize Latent Structure from Disparate Training Data". NeurIPS 2024. [https://arxiv.org/abs/2406.14546]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-06-20)

[44] Jan Betley, Xuchan Bao, Martín Soto, Anna Sztyber-Betley, James Chua, Owain Evans. (2025). "Tell me about yourself: LLMs are aware of their learned behaviors". ICLR 2025. [https://arxiv.org/abs/2501.11120]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-01-19)

[45] Lukas Berglund, Asa Cooper Stickland, Mikita Balesni, Max Kaufmann, Meg Tong, Tomasz Korbak, Daniel Kokotajlo, Owain Evans. (2023). "Taken out of context: On measuring situational awareness in LLMs". arXiv preprint. [https://arxiv.org/abs/2309.00667]  
    (会場未確認(arXiv のみ) / arXiv 初版 2023-09-01)

[46] Andrew K. Lampinen, Arslan Chaudhry, Stephanie C. Y. Chan, Cody Wild, Diane Wan, Alex Ku, Jörg Bornschein, Razvan Pascanu, Murray Shanahan, James L. McClelland. (2025). "On the generalization of language models from in-context learning and finetuning: a controlled study". NeurIPS 2025 FoRLM Workshop. [https://arxiv.org/abs/2505.00661]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2025-05-01)

[47] Jiahai Feng, Stuart Russell, Jacob Steinhardt. (2024). "Extractive Structures Learned in Pretraining Enable Generalization on Finetuned Facts". ICML 2025. [https://arxiv.org/abs/2412.04614]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-12-05)

[48] Antoine Gorceix, Bastien Le Chenadec, Ahmad Rammal, Nelson Vadori, Manuela Veloso. (2024). "Learning Mathematical Rules with Large Language Models". NeurIPS 2024 MATH-AI Workshop. [https://arxiv.org/abs/2410.16973]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2024-10-22)

[49] Nayoung Lee, Kartik Sreenivasan, Jason D. Lee, Kangwook Lee, Dimitris Papailiopoulos. (2023). "Teaching Arithmetic to Small Transformers". ICLR 2024. [https://arxiv.org/abs/2307.03381]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-07-07)

[50] Cem Anil, Yuhuai Wu, Anders Andreassen, Aitor Lewkowycz, Vedant Misra, Vinay Ramasesh, Ambrose Slone, Guy Gur-Ari, Ethan Dyer, Behnam Neyshabur. (2022). "Exploring Length Generalization in Large Language Models". NeurIPS 2022. [https://arxiv.org/abs/2207.04901]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2022-07-11)

[51] Sean McLeish, Arpit Bansal, Alex Stein, Neel Jain, John Kirchenbauer, Brian R. Bartoldson, Bhavya Kailkhura, Abhinav Bhatele, ほか(全 11 名). (2024). "Transformers Can Do Arithmetic with the Right Embeddings". NeurIPS 2024. [https://arxiv.org/abs/2405.17399]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-05-27)

[52] Stewart Slocum, Julian Minder, Clément Dumas, Henry Sleight, Ryan Greenblatt, Samuel Marks, Rowan Wang. (2025). "Believe It or Not: How Deeply do LLMs Believe Implanted Facts?". arXiv preprint. [https://arxiv.org/abs/2510.17941]  
    (会場未確認(arXiv のみ) / arXiv 初版 2025-10-20)

[53] Chen Sun, Renat Aksitov, Andrey Zhmoginov, Nolan Andrew Miller, Max Vladymyrov, Ulrich Rueckert, Been Kim, Mark Sandler. (2025). "How new data permeates LLM knowledge and how to dilute it". ICLR 2025. [https://arxiv.org/abs/2504.09522]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-04-13)

[54] Zorik Gekhman, Gal Yona, Roee Aharoni, Matan Eyal, Amir Feder, Roi Reichart, Jonathan Herzig. (2024). "Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?". Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2024.emnlp-main.444 ; https://arxiv.org/abs/2405.05904]  
    (会場: Crossref で照合 / arXiv 初版 2024-05-09)

[55] Yasumasa Onoe, Michael Zhang, Shankar Padmanabhan, Greg Durrett, Eunsol Choi. (2023). "Can LMs Learn New Entities from Descriptions? Challenges in Propagating Injected Knowledge". Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). [https://doi.org/10.18653/v1/2023.acl-long.300 ; https://arxiv.org/abs/2305.01651]  
    (会場: Crossref で照合 / arXiv 初版 2023-05-02)

[56] Atticus Wang, Joshua Engels, Oliver Clive-Griffin, Senthooran Rajamanoharan, Neel Nanda. (2025). "Simple Mechanistic Explanations for Out-Of-Context Reasoning". ICML 2025 Workshop R2-FM. [https://arxiv.org/abs/2507.08218]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2025-07-10)

[57] Edward Turner, Anna Soligo, Mia Taylor, Senthooran Rajamanoharan, Neel Nanda. (2025). "Model Organisms for Emergent Misalignment". ICML 2025 R2-FM Workshop. [https://arxiv.org/abs/2506.11613]  
    (会場: **未照合**(SCOUT の転記。出所 = SCOUT-A: OpenReview) / arXiv 初版 2025-06-13)

[58] Anna Soligo, Edward Turner, Senthooran Rajamanoharan, Neel Nanda. (2025). "Convergent Linear Representations of Emergent Misalignment". NeurIPS 2025 Mech Interp Workshop. [https://arxiv.org/abs/2506.11618]  
    (会場: **未照合**(SCOUT の転記。出所 = SCOUT-A: OpenReview) / arXiv 初版 2025-06-13)

[59] Sreyan Ghosh, Chandra Kiran Reddy Evuru, Sonal Kumar, Ramaneswaran S, Deepali Aneja, Zeyu Jin, Ramani Duraiswami, Dinesh Manocha. (2024). "A Closer Look at the Limitations of Instruction Tuning". ICML 2024. [https://arxiv.org/abs/2402.05119]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-02-03)

[60] Xiangyu Qi, Ashwinee Panda, Kaifeng Lyu, Xiao Ma, Subhrajit Roy, Ahmad Beirami, Prateek Mittal, Peter Henderson. (2024). "Safety Alignment Should Be Made More Than Just a Few Tokens Deep". ICLR 2025. [https://arxiv.org/abs/2406.05946]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-06-10)

[61] Ko-Wei Huang, Yi-Fu Fu, Ching-Yu Tsai, Yu-Chieh Tu, Tzu-ling Cheng, Cheng-Yu Lin, Yi-Ting Yang, Heng-Yi Liu, ほか(全 11 名). (2025). "Neuron-Level Differentiation of Memorization and Generalization in Large Language Models". Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2025.emnlp-main.812 ; https://arxiv.org/abs/2412.18497]  
    (会場: Crossref で照合 / arXiv 初版 2024-12-24)

[62] Alethea Power, Yuri Burda, Harri Edwards, Igor Babuschkin, Vedant Misra. (2022). "Grokking: Generalization Beyond Overfitting on Small Algorithmic Datasets". arXiv preprint. [https://arxiv.org/abs/2201.02177]  
    (会場未確認(arXiv のみ) / arXiv 初版 2022-01-06)

[63] Boshi Wang, Xiang Yue, Yu Su, Huan Sun. (2024). "Grokked Transformers are Implicit Reasoners: A Mechanistic Journey to the Edge of Generalization". NeurIPS 2024. [https://arxiv.org/abs/2405.15071]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2024-05-23)

[64] Jason Hoelscher-Obermaier, Julia Persson, Esben Kran, Ioannis Konstas, Fazl Barez. (2023). "Detecting Edit Failures In Large Language Models: An Improved Specificity Benchmark". Findings of the Association for Computational Linguistics: ACL 2023. [https://doi.org/10.18653/v1/2023.findings-acl.733 ; https://arxiv.org/abs/2305.17553]  
    (会場: Crossref で照合 / arXiv 初版 2023-05-27)

[65] Yunzhi Yao, Peng Wang, Bozhong Tian, Siyuan Cheng, Zhoubo Li, Shumin Deng, Huajun Chen, Ningyu Zhang. (2023). "Editing Large Language Models: Problems, Methods, and Opportunities". Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2023.emnlp-main.632 ; https://arxiv.org/abs/2305.13172]  
    (会場: Crossref で照合 / arXiv 初版 2023-05-22)

[66] Zexuan Zhong, Zhengxuan Wu, Christopher Manning, Christopher Potts, Danqi Chen. (2023). "MQuAKE: Assessing Knowledge Editing in Language Models via Multi-Hop Questions". Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2023.emnlp-main.971 ; https://arxiv.org/abs/2305.14795]  
    (会場: Crossref で照合 / arXiv 初版 2023-05-24)

[67] Kevin Meng, David Bau, Alex Andonian, Yonatan Belinkov. (2022). "Locating and Editing Factual Associations in GPT". NeurIPS 2022. [https://arxiv.org/abs/2202.05262]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2022-02-10)

[68] Jiaxin Qin, Zixuan Zhang, Chi Han, Pengfei Yu, Manling Li, Heng Ji. (2024). "Why Does New Knowledge Create Messy Ripple Effects in LLMs?". Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2024.emnlp-main.700 ; https://arxiv.org/abs/2407.12828]  
    (会場: Crossref で照合 / arXiv 初版 2024-07-02)

[69] Lukas Berglund, Meg Tong, Max Kaufmann, Mikita Balesni, Asa Cooper Stickland, Tomasz Korbak, Owain Evans. (2023). "The Reversal Curse: LLMs trained on "A is B" fail to learn "B is A"". ICLR 2024. [https://arxiv.org/abs/2309.12288]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-09-21)

[70] Afra Feyza Akyürek, Ekin Akyürek, Leshem Choshen, Derry Wijaya, Jacob Andreas. (2024). "Deductive Closure Training of Language Models for Coherence, Accuracy, and Updatability". Findings of the Association for Computational Linguistics ACL 2024. [https://doi.org/10.18653/v1/2024.findings-acl.584 ; https://arxiv.org/abs/2401.08574]  
    (会場: Crossref で照合 / arXiv 初版 2024-01-16)

[71] Aengus Lynch, Phillip Guo, Aidan Ewart, Stephen Casper, Dylan Hadfield-Menell. (2024). "Eight Methods to Evaluate Robust Unlearning in LLMs". arXiv preprint. [https://arxiv.org/abs/2402.16835]  
    (会場未確認(arXiv のみ) / arXiv 初版 2024-02-26)

[72] Jakub Łucki, Boyi Wei, Yangsibo Huang, Peter Henderson, Florian Tramèr, Javier Rando. (2024). "An Adversarial Perspective on Machine Unlearning for AI Safety". TMLR. [https://arxiv.org/abs/2409.18025]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2024-09-26)

[73] Shengyuan Hu, Yiwei Fu, Zhiwei Steven Wu, Virginia Smith. (2024). "Unlearning or Obfuscating? Jogging the Memory of Unlearned LLMs via Benign Relearning". ICLR 2025. [https://arxiv.org/abs/2406.13356]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-06-19)

[74] Jai Doshi, Asa Cooper Stickland. (2024). "Does Unlearning Truly Unlearn? A Black Box Evaluation of LLM Unlearning Methods". arXiv preprint. [https://arxiv.org/abs/2411.12103]  
    (会場未確認(arXiv のみ) / arXiv 初版 2024-11-18)

[75] Vaidehi Patil, Peter Hase, Mohit Bansal. (2023). "Can Sensitive Information Be Deleted From LLMs? Objectives for Defending Against Extraction Attacks". arXiv preprint. [https://arxiv.org/abs/2309.17410]  
    (会場未確認(arXiv のみ) / arXiv 初版 2023-09-29)

[76] Zhiwei Zhang, Fali Wang, Xiaomin Li, Zongyu Wu, Xianfeng Tang, Hui Liu, Qi He, Wenpeng Yin, Suhang Wang. (2024). "Catastrophic Failure of LLM Unlearning via Quantization". ICLR 2025. [https://arxiv.org/abs/2410.16454]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-10-21)

[77] Nikhil Prakash, Tamar Rott Shaham, Tal Haklay, Yonatan Belinkov, David Bau. (2024). "Fine-Tuning Enhances Existing Mechanisms: A Case Study on Entity Tracking". ICLR 2024. [https://arxiv.org/abs/2402.14811]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-02-22)

[78] Andrew Lee, Xiaoyan Bai, Itamar Pres, Martin Wattenberg, Jonathan K. Kummerfeld, Rada Mihalcea. (2024). "A Mechanistic Understanding of Alignment Algorithms: A Case Study on DPO and Toxicity". ICML 2024. [https://arxiv.org/abs/2401.01967]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-01-03)

[79] Samyak Jain, Ekdeep Singh Lubana, Kemal Oksuz, Tom Joy, Philip H. S. Torr, Amartya Sanyal, Puneet K. Dokania. (2024). "What Makes and Breaks Safety Fine-tuning? A Mechanistic Study". NeurIPS 2024. [https://arxiv.org/abs/2407.10264]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-07-14)

[80] Ananya Kumar, Aditi Raghunathan, Robbie Jones, Tengyu Ma, Percy Liang. (2022). "Fine-Tuning can Distort Pretrained Features and Underperform Out-of-Distribution". ICLR 2022. [https://arxiv.org/abs/2202.10054]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2022-02-21)

[81] Xu Wang, Yan Hu, Wenyu Du, Reynold Cheng, Benyou Wang, Difan Zou. (2025). "Towards Understanding Fine-Tuning Mechanisms of LLMs via Circuit Analysis". ICML 2025. [https://arxiv.org/abs/2502.11812]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-02-17)

[82] Mohit Raghavendra, Vaskar Nath, Sean Hendryx. (2024). "Revisiting the Superficial Alignment Hypothesis". arXiv preprint. [https://arxiv.org/abs/2410.03717]  
    (会場未確認(arXiv のみ) / arXiv 初版 2024-09-27)

[83] Jan Betley, Jorio Cocola, Dylan Feng, James Chua, Andy Arditi, Anna Sztyber-Betley, Owain Evans. (2025). "Weird Generalization and Inductive Backdoors: New Ways to Corrupt LLMs". arXiv preprint. [https://arxiv.org/abs/2512.09742]  
    (会場未確認(arXiv のみ) / arXiv 初版 2025-12-10)

[84] Miles Wang, Tom Dupré la Tour, Olivia Watkins, Alex Makelov, Ryan A. Chi, Samuel Miserendino, Jeffrey Wang, Achyuta Rajaram, ほか(全 11 名). (2025). "Persona Features Control Emergent Misalignment". ICLR 2026. [https://arxiv.org/abs/2506.19823]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-06-24)

[85] Xiangyu Qi, Yi Zeng, Tinghao Xie, Pin-Yu Chen, Ruoxi Jia, Prateek Mittal, Peter Henderson. (2023). "Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To!". ICLR 2024. [https://arxiv.org/abs/2310.03693]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-10-05)

[86] Craig Dickson. (2025). "The Devil in the Details: Emergent Misalignment, Format and Coherence in Open-Weights LLMs". arXiv preprint. [https://arxiv.org/abs/2511.20104]  
    (会場未確認(arXiv のみ) / arXiv 初版 2025-11-25)

[87] Jeremiah Giordani. (2025). "Re-Emergent Misalignment: How Narrow Fine-Tuning Erodes Safety Alignment in LLMs". arXiv preprint. [https://arxiv.org/abs/2507.03662]  
    (会場未確認(arXiv のみ) / arXiv 初版 2025-07-04)

[88] Julian Minder, Clément Dumas, Stewart Slocum, Helena Casademunt, Cameron Holmes, Robert West, Neel Nanda. (2025). "Narrow Finetuning Leaves Clearly Readable Traces in Activation Differences". ICLR 2026. [https://arxiv.org/abs/2510.13900]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-10-14)

[89] Geoffrey E. Hinton, Tim Shallice. (1991). "Lesioning an attractor network: Investigations of acquired dyslexia.". Psychological Review. [https://doi.org/10.1037/0033-295X.98.1.74]  
    (会場: Crossref で照合)

[90] David C. Plaut. (1995). "Double dissociation without modularity: Evidence from connectionist neuropsychology". Journal of Clinical and Experimental Neuropsychology. [https://doi.org/10.1080/01688639508405124]  
    (会場: Crossref で照合)

[91] Yair Lakretz, German Kruszewski, Theo Desbordes, Dieuwke Hupkes, Stanislas Dehaene, Marco Baroni. (2019). "The emergence of number and syntax units in LSTM language models". Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers). [https://doi.org/10.18653/v1/N19-1002 ; https://arxiv.org/abs/1903.07435]  
    (会場: Crossref で照合 / arXiv 初版 2019-03-18)

[92] Katharina Dobs, Julio Martinez, Alexander J. E. Kell, Nancy Kanwisher. (2022). "Brain-like functional specialization emerges spontaneously in deep neural networks". Science Advances. [https://doi.org/10.1126/sciadv.abl8913]  
    (会場: Crossref で照合)

[93] Nancy Kanwisher, Meenakshi Khosla, Katharina Dobs. (2023). "Using artificial neural networks to ask ‘why’ questions of minds and brains". Trends in Neurosciences. [https://doi.org/10.1016/j.tins.2022.12.008]  
    (会場: Crossref で照合)

[94] Kyle Mahowald, Anna A. Ivanova, Idan A. Blank, Nancy Kanwisher, Joshua B. Tenenbaum, Evelina Fedorenko. (2024). "Dissociating language and thought in large language models". Trends in Cognitive Sciences. [https://doi.org/10.1016/j.tics.2024.01.011]  
    (会場: Crossref で照合)

[95] Alfonso Caramazza. (1986). "On drawing inferences about the structure of normal cognitive systems from the analysis of patterns of impaired performance: The case for single-patient studies". Brain and Cognition. [https://doi.org/10.1016/0278-2626(86)90061-8]  
    (会場: Crossref で照合)

[96] Tim Shallice. (1988). "From Neuropsychology to Mental Structure". . [https://doi.org/10.1017/CBO9780511526817]  
    (会場: Crossref で照合)

[97] Andrew Saxe, Stephanie Nelli, Christopher Summerfield. (2020). "If deep learning is the answer, what is the question?". Nature Reviews Neuroscience. [https://doi.org/10.1038/s41583-020-00395-8]  
    (会場: Crossref で照合)

[98] Hattie Zhou, Arwen Bradley, Etai Littwin, Noam Razin, Omid Saremi, Josh Susskind, Samy Bengio, Preetum Nakkiran. (2023). "What Algorithms can Transformers Learn? A Study in Length Generalization". ICLR 2024. [https://arxiv.org/abs/2310.16028]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-10-24)

[99] Alexander D'Amour, Katherine Heller, Dan Moldovan, Ben Adlam, Babak Alipanahi, Alex Beutel, Christina Chen, Jonathan Deaton, ほか(全 40 名). (2020). "Underspecification Presents Challenges for Credibility in Modern Machine Learning". JMLR 23 (2022). [https://arxiv.org/abs/2011.03395 ; https://jmlr.org/papers/v23/20-1335.html]  
    (会場: **未照合**(SCOUT の転記。出所 = SCOUT-C: jmlr.org メタタグ) / arXiv 初版 2020-11-06)

[100] Marius Mosbach, Maksym Andriushchenko, Dietrich Klakow. (2020). "On the Stability of Fine-tuning BERT: Misconceptions, Explanations, and Strong Baselines". ICLR 2021. [https://arxiv.org/abs/2006.04884]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2020-06-08)

[101] Xiang Zhou, Yixin Nie, Hao Tan, Mohit Bansal. (2020). "The Curse of Performance Instability in Analysis Datasets: Consequences, Source, and Suggestions". Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP). [https://doi.org/10.18653/v1/2020.emnlp-main.659 ; https://arxiv.org/abs/2004.13606]  
    (会場: Crossref で照合 / arXiv 初版 2020-04-28)

[102] Ruiqi Zhong, Dhruba Ghosh, Dan Klein, Jacob Steinhardt. (2021). "Are Larger Pretrained Language Models Uniformly Better? Comparing Performance at the Instance Level". Findings of the Association for Computational Linguistics: ACL-IJCNLP 2021. [https://doi.org/10.18653/v1/2021.findings-acl.334 ; https://arxiv.org/abs/2105.06020]  
    (会場: Crossref で照合 / arXiv 初版 2021-05-13)

[103] Cecilia Summers, Michael J. Dinneen. (2021). "Nondeterminism and Instability in Neural Network Optimization". ICML 2021. [https://arxiv.org/abs/2103.04514]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2021-03-08)

[104] Jesse Dodge, Gabriel Ilharco, Roy Schwartz, Ali Farhadi, Hannaneh Hajishirzi, Noah Smith. (2020). "Fine-Tuning Pretrained Language Models: Weight Initializations, Data Orders, and Early Stopping". arXiv preprint. [https://arxiv.org/abs/2002.06305]  
    (会場未確認(arXiv のみ) / arXiv 初版 2020-02-15)

[105] Behnam Neyshabur, Hanie Sedghi, Chiyuan Zhang. (2020). "What is being transferred in transfer learning?". NeurIPS 2020. [https://arxiv.org/abs/2008.11687]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2020-08-26)

[106] Mitchell Wortsman, Gabriel Ilharco, Samir Yitzhak Gadre, Rebecca Roelofs, Raphael Gontijo-Lopes, Ari S. Morcos, Hongseok Namkoong, Ali Farhadi, ほか(全 11 名). (2022). "Model soups: averaging weights of multiple fine-tuned models improves accuracy without increasing inference time". ICML 2022. [https://arxiv.org/abs/2203.05482]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2022-03-10)

[107] Keller Jordan. (2023). "On the Variance of Neural Network Training with respect to Test Sets and Distributions". ICLR 2024. [https://arxiv.org/abs/2304.01910]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-04-04)

[108] Nghia Tuan Bui, Guergana K Savova, Lijing Wang. (2025). "Assessing the Macro and Micro Effects of Random Seeds on Fine-Tuning Large Language Models". Proceedings of the 14th International Joint Conference on Natural Language Processing and the 4th Conference of the Asia-Pacific Chapter of the Association for Computational Linguistics. [https://doi.org/10.18653/v1/2025.ijcnlp-short.3 ; https://arxiv.org/abs/2503.07329]  
    (会場: Crossref で照合 / arXiv 初版 2025-03-10)

[109] Thibault Sellam, Steve Yadlowsky, Jason Wei, Naomi Saphra, Alexander D'Amour, Tal Linzen, Jasmijn Bastings, Iulia Turc, ほか(全 12 名). (2021). "The MultiBERTs: BERT Reproductions for Robustness Analysis". ICLR 2022. [https://arxiv.org/abs/2106.16163]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2021-06-30)

[110] Xavier Bouthillier, Pierre Delaunay, Mirko Bronzi, Assya Trofimov, Brennan Nichyporuk, Justin Szeto, Naz Sepah, Edward Raff, ほか(全 17 名). (2021). "Accounting for Variance in Machine Learning Benchmarks". MLSys 2021. [https://arxiv.org/abs/2103.03098]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2021-03-01)

[111] Rishabh Agarwal, Max Schwarzer, Pablo Samuel Castro, Aaron Courville, Marc G. Bellemare. (2021). "Deep Reinforcement Learning at the Edge of the Statistical Precipice". NeurIPS 2021. [https://arxiv.org/abs/2108.13264]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2021-08-30)

[112] Cédric Colas, Olivier Sigaud, Pierre-Yves Oudeyer. (2018). "How Many Random Seeds? Statistical Power Analysis in Deep Reinforcement Learning Experiments". arXiv preprint. [https://arxiv.org/abs/1806.08295]  
    (会場未確認(arXiv のみ) / arXiv 初版 2018-06-21)

[113] Rotem Dror, Segev Shlomov, Roi Reichart. (2019). "Deep Dominance - How to Properly Compare Deep Neural Models". Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics. [https://doi.org/10.18653/v1/P19-1266]  
    (会場: Crossref で照合)

[114] Yihan Wang, Si Si, Daliang Li, Michal Lukasik, Felix Yu, Cho-Jui Hsieh, Inderjit S Dhillon, Sanjiv Kumar. (2022). "Two-stage LLM Fine-tuning with Less Specialization and More Generalization". ICLR 2024. [https://arxiv.org/abs/2211.00635]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2022-11-01)

[115] Junhao Zheng, Xidi Cai, Shengjie Qiu, Qianli Ma. (2025). "Spurious Forgetting in Continual Learning of Language Models". ICLR 2025. [https://arxiv.org/abs/2501.13453]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2025-01-23)

[116] Bill Yuchen Lin, Abhilasha Ravichander, Ximing Lu, Nouha Dziri, Melanie Sclar, Khyathi Chandu, Chandra Bhagavatula, Yejin Choi. (2023). "The Unlocking Spell on Base LLMs: Rethinking Alignment via In-Context Learning". ICLR 2024. [https://arxiv.org/abs/2312.01552]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-12-04)

[117] Chunting Zhou, Pengfei Liu, Puxin Xu, Srini Iyer, Jiao Sun, Yuning Mao, Xuezhe Ma, Avia Efrat, ほか(全 15 名). (2023). "LIMA: Less Is More for Alignment". NeurIPS 2023. [https://arxiv.org/abs/2305.11206]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-05-18)

[118] Dan Biderman, Jacob Portes, Jose Javier Gonzalez Ortiz, Mansheej Paul, Philip Greengard, Connor Jennings, Daniel King, Sam Havens, ほか(全 12 名). (2024). "LoRA Learns Less and Forgets Less". TMLR 2024. [https://arxiv.org/abs/2405.09673]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2024-05-15)

[119] Thomas Scialom, Tuhin Chakrabarty, Smaranda Muresan. (2022). "Fine-tuned Language Models are Continual Learners". Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2022.emnlp-main.410 ; https://arxiv.org/abs/2205.12393]  
    (会場: Crossref で照合 / arXiv 初版 2022-05-24)

[120] Yun Luo, Zhen Yang, Fandong Meng, Yafu Li, Jie Zhou, Yue Zhang. (2025). "An Empirical Study of Catastrophic Forgetting in Large Language Models During Continual Fine-Tuning". IEEE Transactions on Audio, Speech and Language Processing. [https://doi.org/10.1109/taslpro.2025.3606231 ; https://arxiv.org/abs/2308.08747]  
    (会場: Crossref で照合 / arXiv 初版 2023-08-17)

[121] Zhaorui Yang, Tianyu Pang, Haozhe Feng, Han Wang, Wei Chen, Minfeng Zhu, Qian Liu. (2024). "Self-Distillation Bridges Distribution Gap in Language Model Fine-Tuning". Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). [https://doi.org/10.18653/v1/2024.acl-long.58 ; https://arxiv.org/abs/2402.13669]  
    (会場: Crossref で照合 / arXiv 初版 2024-02-21)

[122] Xuan Ren, Biao Wu, Lingqiao Liu. (2024). "I Learn Better If You Speak My Language: Understanding the Superior Performance of Fine-Tuning Large Language Models with LLM-Generated Responses". Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2024.emnlp-main.571 ; https://arxiv.org/abs/2402.11192]  
    (会場: Crossref で照合 / arXiv 初版 2024-02-17)

[123] Long Ouyang, Jeff Wu, Xu Jiang, Diogo Almeida, Carroll L. Wainwright, Pamela Mishkin, Chong Zhang, Sandhini Agarwal, ほか(全 20 名). (2022). "Training language models to follow instructions with human feedback". NeurIPS 2022. [https://arxiv.org/abs/2203.02155]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2022-03-04)

[124] Yong Lin, Hangyu Lin, Wei Xiong, Shizhe Diao, Jianmeng Liu, Jipeng Zhang, Rui Pan, Haoxiang Wang, ほか(全 17 名). (2024). "Mitigating the Alignment Tax of RLHF". Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/2024.emnlp-main.35 ; https://arxiv.org/abs/2309.06256]  
    (会場: Crossref で照合 / arXiv 初版 2023-09-12)

[125] Bryan R Christ, Zachary Gottesman, Jonathan Kropko, Thomas Hartvigsen. (2025). "Math Neurosurgery: Isolating Language Models’ Math Reasoning Abilities Using Only Forward Passes". Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). [https://doi.org/10.18653/v1/2025.acl-long.1209 ; https://arxiv.org/abs/2410.16930]  
    (会場: Crossref で照合 / arXiv 版の題名: "Math Neurosurgery: Isolating Language Models' Math Reasoning Abilities Using Only Forward Passes" / arXiv 初版 2024-10-22)

[126] Zeyuan Allen-Zhu, Yuanzhi Li. (2023). "Physics of Language Models: Part 3.2, Knowledge Manipulation". ICLR 2025. [https://arxiv.org/abs/2309.14402]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-09-25)

[127] Raj Shah, Vijay Marupudi, Reba Koenen, Khushi Bhardwaj, Sashank Varma. (2023). "Numeric Magnitude Comparison Effects in Large Language Models". Findings of the Association for Computational Linguistics: ACL 2023. [https://doi.org/10.18653/v1/2023.findings-acl.383 ; https://arxiv.org/abs/2305.10782]  
    (会場: Crossref で照合 / arXiv 版の題名: "Human Behavioral Benchmarking: Numeric Magnitude Comparison Effects in Large Language Models" / arXiv 初版 2023-05-18)

[128] Benjamin W. Domingue, Klint Kanopka, Sam Trejo, Mijke Rhemtulla, Elliot M. Tucker-Drob. (2024). "Ubiquitous bias and false discovery due to model misspecification in analysis of statistical interactions: The role of the outcome’s distribution and metric properties.". Psychological Methods. [https://doi.org/10.1037/met0000532]  
    (会場: Crossref で照合)

[129] Leonel Garcia-Marques, Teresa Garcia-Marques, Markus Brauer. (2014). "Buy three but get only two: The smallest effect in a 2 × 2 ANOVA is always uninterpretable". Psychonomic Bulletin &amp; Review. [https://doi.org/10.3758/s13423-014-0640-3]  
    (会場: Crossref で照合)

[130] Jaya M. Satagopan, Robert C. Elston. (2012). "Evaluation of removable statistical interaction for binary traits". Statistics in Medicine. [https://doi.org/10.1002/sim.5628]  
    (会場: Crossref で照合)

[131] Chunrong Ai, Edward C. Norton. (2003). "Interaction terms in logit and probit models". Economics Letters. [https://doi.org/10.1016/S0165-1765(03)00032-6]  
    (会場: Crossref で照合)

[132] William D. Berry, Jacqueline H. R. DeMeritt, Justin Esarey. (2009). "Testing for Interaction in Binary Logit and Probit Models: Is a Product Term Essential?". American Journal of Political Science. [https://doi.org/10.1111/j.1540-5907.2009.00429.x]  
    (会場: Crossref で照合)

[133] Trenton Mize. (2019). "Best Practices for Estimating, Interpreting, and Presenting Nonlinear Interaction Effects". Sociological Science. [https://doi.org/10.15195/v6.a4]  
    (会場: Crossref で照合)

[134] T. Florian Jaeger. (2008). "Categorical data analysis: Away from ANOVAs (transformation or not) and towards logit mixed models". Journal of Memory and Language. [https://doi.org/10.1016/j.jml.2007.11.007]  
    (会場: Crossref で照合)

[135] Guy C. Van Orden, Bruce F. Pennington, Gregory O. Stone. (2001). "What do double dissociations prove?". Cognitive Science. [https://doi.org/10.1207/s15516709cog2501_5]  
    (会場: Crossref で照合)

[136] John A. Bullinaria, Nick Chater. (1995). "Connectionist modelling: Implications for cognitive neuropsychology". Language and Cognitive Processes. [https://doi.org/10.1080/01690969508407095]  
    (会場: Crossref で照合)

[137] Rachel G. Stephens, Dora Matzke, Brett K. Hayes. (2019). "Disappearing dissociations in experimental psychology: Using state-trace analysis to test for multiple processes". Journal of Mathematical Psychology. [https://doi.org/10.1016/j.jmp.2018.11.003]  
    (会場: Crossref で照合)

[138] F. Gregory Ashby. (2014). "Is state-trace analysis an appropriate tool for assessing the number of cognitive systems?". Psychonomic Bulletin &amp; Review. [https://doi.org/10.3758/s13423-013-0578-x]  
    (会場: Crossref で照合)

[139] Fayme Yeates, Andy J. Wills, Fergal W. Jones, Ian P. L. McLaren. (2014). "State‐Trace Analysis: Dissociable Processes in a Connectionist Network?". Cognitive Science. [https://doi.org/10.1111/cogs.12185]  
    (会場: Crossref で照合)

[140] Melissa Prince, Scott Brown, Andrew Heathcote. (2012). "The design and analysis of state-trace experiments.". Psychological Methods. [https://doi.org/10.1037/a0025809]  
    (会場: Crossref で照合)

[141] Donald Bamber. (1979). "State-trace analysis: A method of testing simple theories of causation". Journal of Mathematical Psychology. [https://doi.org/10.1016/0022-2496(79)90016-6]  
    (会場: Crossref で照合)

[142] Clintin P. Davis-Stober, Richard D. Morey, Matthew Gretton, Andrew Heathcote. (2016). "Bayes factors for state-trace analysis". Journal of Mathematical Psychology. [https://doi.org/10.1016/j.jmp.2015.08.004]  
    (会場: Crossref で照合)

[143] Thomas McGrath, Matthew Rahtz, Janos Kramar, Vladimir Mikulik, Shane Legg. (2023). "The Hydra Effect: Emergent Self-repair in Language Model Computations". arXiv preprint. [https://arxiv.org/abs/2307.15771]  
    (会場未確認(arXiv のみ) / arXiv 初版 2023-07-28)

[144] Cody Rushing, Neel Nanda. (2024). "Explorations of Self-Repair in Language Models". ICML 2024. [https://arxiv.org/abs/2402.15390]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2024-02-23)

[145] Aleksandar Makelov, Georg Lange, Neel Nanda. (2023). "Is This the Subspace You Are Looking for? An Interpretability Illusion for Subspace Activation Patching". ICLR 2024. [https://arxiv.org/abs/2311.17030]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-11-28)

[146] Fred Zhang, Neel Nanda. (2023). "Towards Best Practices of Activation Patching in Language Models: Metrics and Methods". ICLR 2024. [https://arxiv.org/abs/2309.16042]  
    (会場: 公式予稿集の索引に題名を確認 / arXiv 初版 2023-09-27)

[147] Eric Jonas, Konrad Paul Kording. (2017). "Could a Neuroscientist Understand a Microprocessor?". PLOS Computational Biology. [https://doi.org/10.1371/journal.pcbi.1005268]  
    (会場: Crossref で照合)

[148] Ari S. Morcos, David G. T. Barrett, Neil C. Rabinowitz, Matthew Botvinick. (2018). "On the importance of single directions for generalization". ICLR 2018. [https://arxiv.org/abs/1803.06959]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2018-03-19)

[149] Tolga Bolukbasi, Adam Pearce, Ann Yuan, Andy Coenen, Emily Reif, Fernanda Viégas, Martin Wattenberg. (2021). "An Interpretability Illusion for BERT". arXiv preprint. [https://arxiv.org/abs/2104.07143]  
    (会場未確認(arXiv のみ) / arXiv 初版 2021-04-14)

[150] MARTIN DAVIES. (2010). "Double Dissociation: Understanding its Role in Cognitive Neuropsychology". Mind &amp; Language. [https://doi.org/10.1111/j.1468-0017.2010.01399.x]  
    (会場: Crossref で照合)

[151] Daniël Lakens. (2017). "Equivalence Tests". Social Psychological and Personality Science. [https://doi.org/10.1177/1948550617697177]  
    (会場: Crossref で照合)

[152] Daniël Lakens, Anne M. Scheel, Peder M. Isager. (2018). "Equivalence Testing for Psychological Research: A Tutorial". Advances in Methods and Practices in Psychological Science. [https://doi.org/10.1177/2515245918770963]  
    (会場: Crossref で照合)

[153] Michael L. Kalish, John C. Dunn, Oleg P. Burdakov, Oleg Sysoev. (2016). "A statistical test of the equality of latent orders". Journal of Mathematical Psychology. [https://doi.org/10.1016/j.jmp.2015.10.004]  
    (会場: Crossref で照合)

[154] John C. Dunn, Michael L. Kalish. (2018). "State-Trace Analysis". Computational Approaches to Cognition and Perception. [https://doi.org/10.1007/978-3-319-73129-2]  
    (会場: Crossref で照合)

[155] Nils Reimers, Iryna Gurevych. (2017). "Reporting Score Distributions Makes a Difference: Performance Study of LSTM-networks for Sequence Tagging". Proceedings of the 2017 Conference on Empirical Methods in Natural Language Processing. [https://doi.org/10.18653/v1/D17-1035 ; https://arxiv.org/abs/1707.09861]  
    (会場: Crossref で照合 / arXiv 初版 2017-07-31)

[156] Mitchell Wortsman, Gabriel Ilharco, Jong Wook Kim, Mike Li, Simon Kornblith, Rebecca Roelofs, Raphael Gontijo-Lopes, Hannaneh Hajishirzi, ほか(全 11 名). (2021). "Robust fine-tuning of zero-shot models". CVPR 2022. [https://arxiv.org/abs/2109.01903]  
    (会場: arXiv の comment / journal_ref(著者の申告)で確認 / arXiv 初版 2021-09-04)

[157] Jianheng Huang, Leyang Cui, Ante Wang, Chengyi Yang, Xinting Liao, Linfeng Song, Junfeng Yao, Jinsong Su. (2024). "Mitigating Catastrophic Forgetting in Large Language Models with Self-Synthesized Rehearsal". Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). [https://doi.org/10.18653/v1/2024.acl-long.77 ; https://arxiv.org/abs/2403.01244]  
    (会場: Crossref で照合 / arXiv 初版 2024-03-02)

[158] Adam Ibrahim, Benjamin Thérien, Kshitij Gupta, Mats L. Richter, Quentin Anthony, Timothée Lesort, Eugene Belilovsky, Irina Rish. (2024). "Simple and Scalable Strategies to Continually Pre-train Large Language Models". TMLR. [https://arxiv.org/abs/2403.08763]  
    (会場: **未照合**(SCOUT の転記。出所 = SCOUT-C: OpenReview) / arXiv 初版 2024-03-13)

[159] Kevin Wang, Alexandre Variengien, Arthur Conmy, Buck Shlegeris, Jacob Steinhardt. (2022). "Interpretability in the Wild: a Circuit for Indirect Object Identification in GPT-2 small". ICLR 2023. [https://arxiv.org/abs/2211.00593]  
    (会場: **未照合**(SCOUT の転記。出所 = SCOUT-D: OpenReview のみ(要再確認)) / arXiv 初版 2022-11-01)
