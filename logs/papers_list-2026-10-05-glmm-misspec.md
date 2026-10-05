# 論文集 — GLMM の誤指定と第一種の過誤・収束対処・少数クラスタ・FT のシード変動

- 作成者: SCOUT サブエージェント(Claude Opus 5.5 / `claude-opus-5-5`)
- 作成日: 2026-10-05
- **状態: 全件 未検証(SCOUT の転記。人間が原典と突き合わせるまで本文・論文で使わない)**
- 本文: `logs/SCOUT-2026-10-05-glmm-misspec.md`(番号は共通)
- 書誌の出所: 雑誌・書籍は Crossref API(`api.crossref.org/works/<DOI>`)、会議は ACL Anthology / MLSys / iclr.cc の採択データ、プレプリントは arXiv API。年は冊子版(published-print)の年。オンライン先行の年が違うものは注記した。
- 注記の記号: **[内容未確認]** = 書誌は確認したが要旨・本文を取れず、主張を支えるかは確認していない。**[プレプリント]** = 査読の記録を確認できていない。

## C1 ランダム傾きの省略

[1] Barr, D. J., Levy, R., Scheepers, C., & Tily, H. J. (2013). "Random effects structure for confirmatory hypothesis testing: Keep it maximal". Journal of Memory and Language, 68(3), 255–278. https://doi.org/10.1016/j.jml.2012.11.001

[2] Schielzeth, H., & Forstmeier, W. (2009). "Conclusions beyond support: overconfident estimates in mixed models". Behavioral Ecology, 20(2), 416–420. https://doi.org/10.1093/beheco/arn145 (オンライン先行 2008)

[3] Heisig, J. P., & Schaeffer, M. (2019). "Why You Should Always Include a Random Slope for the Lower-Level Variable Involved in a Cross-Level Interaction". European Sociological Review, 35(2), 258–279. https://doi.org/10.1093/esr/jcy053

[4] Matuschek, H., Kliegl, R., Vasishth, S., Baayen, H., & Bates, D. (2017). "Balancing Type I error and power in linear mixed models". Journal of Memory and Language, 94, 305–315. https://doi.org/10.1016/j.jml.2017.01.001

[5] Oberpriller, J., de Souza Leite, M., & Pichler, M. (2022). "Fixed or random? On the reliability of mixed-effects models for a small number of levels in grouping variables". Ecology and Evolution, 12(7), e9062. https://doi.org/10.1002/ece3.9062

[6] Yarkoni, T. (2022). "The generalizability crisis". Behavioral and Brain Sciences, 45, e1. https://doi.org/10.1017/S0140525X20001685 (オンライン先行 2020)

[7] Judd, C. M., Westfall, J., & Kenny, D. A. (2012). "Treating stimuli as a random factor in social psychology: A new and comprehensive solution to a pervasive but largely ignored problem". Journal of Personality and Social Psychology, 103(1), 54–69. https://doi.org/10.1037/a0028347

[8] Arnqvist, G. (2020). "Mixed Models Offer No Freedom from Degrees of Freedom". Trends in Ecology & Evolution, 35(4), 329–335. https://doi.org/10.1016/j.tree.2019.12.004

[9] Aarts, E., Verhage, M., Veenvliet, J. V., Dolan, C. V., & van der Sluis, S. (2014). "A solution to dependency: using multilevel analysis to accommodate nested data". Nature Neuroscience, 17(4), 491–496. https://doi.org/10.1038/nn.3648

[10] Lazic, S. E. (2010). "The problem of pseudoreplication in neuroscientific studies: is it affecting your analysis?". BMC Neuroscience, 11, 5. https://doi.org/10.1186/1471-2202-11-5

## C2 item のランダム効果

[11] Clark, H. H. (1973). "The language-as-fixed-effect fallacy: A critique of language statistics in psychological research". Journal of Verbal Learning and Verbal Behavior, 12(4), 335–359. https://doi.org/10.1016/S0022-5371(73)80014-3 **[内容未確認]**

[12] Coleman, E. B. (1964). "Generalizing to a Language Population". Psychological Reports, 14(1), 219–226. https://doi.org/10.2466/pr0.1964.14.1.219

[13] Westfall, J., Kenny, D. A., & Judd, C. M. (2014). "Statistical power and optimal design in experiments in which samples of participants respond to samples of stimuli". Journal of Experimental Psychology: General, 143(5), 2020–2045. https://doi.org/10.1037/xge0000014

[14] Wolsiefer, K., Westfall, J., & Judd, C. M. (2017). "Modeling stimulus variation in three common implicit attitude tasks". Behavior Research Methods, 49(4), 1193–1209. https://doi.org/10.3758/s13428-016-0779-0 (オンライン先行 2016。PubMed に正誤表 2 件の記載あり)

[15] Baayen, R. H., Davidson, D. J., & Bates, D. M. (2008). "Mixed-effects modeling with crossed random effects for subjects and items". Journal of Memory and Language, 59(4), 390–412. https://doi.org/10.1016/j.jml.2007.12.005 **[内容未確認]**

[16] Raaijmakers, J. G. W., Schrijnemakers, J. M. C., & Gremmen, F. (1999). "How to Deal with 'The Language-as-Fixed-Effect Fallacy': Common Misconceptions and Alternative Solutions". Journal of Memory and Language, 41(3), 416–426. https://doi.org/10.1006/jmla.1999.2650 **[内容未確認]**

## C3 収束失敗・特異な当てはめへの対処

[17] Bates, D., Kliegl, R., Vasishth, S., & Baayen, H. (2015). "Parsimonious Mixed Models". arXiv preprint arXiv:1506.04967. https://arxiv.org/abs/1506.04967 **[プレプリント]**

[18] Bates, D., Mächler, M., Bolker, B., & Walker, S. (2015). "Fitting Linear Mixed-Effects Models Using lme4". Journal of Statistical Software, 67(1). https://doi.org/10.18637/jss.v067.i01 (頁は Crossref・OpenAlex に無く未確認)

[19] Brauer, M., & Curtin, J. J. (2018). "Linear mixed-effects models and the analysis of nonindependent data: A unified framework to analyze categorical and continuous independent variables that vary within-subjects and/or within-items". Psychological Methods, 23(3), 389–411. https://doi.org/10.1037/met0000159

[20] Meteyard, L., & Davies, R. A. I. (2020). "Best practice guidance for linear mixed-effects models in psychological science". Journal of Memory and Language, 112, 104092. https://doi.org/10.1016/j.jml.2020.104092

[21] Scandola, M., & Tidoni, E. (2024). "Reliability and Feasibility of Linear Mixed Models in Fully Crossed Experimental Designs". Advances in Methods and Practices in Psychological Science, 7(1), 25152459231214454. https://doi.org/10.1177/25152459231214454

[22] Kimball, A. E., Shantz, K., Eager, C., & Roy, J. (2019). "Confronting Quasi-Separation in Logistic Mixed Effects for Linguistic Data: A Bayesian Approach". Journal of Quantitative Linguistics, 26(3), 231–255. https://doi.org/10.1080/09296174.2018.1499457 (オンライン先行 2018)

[23] Bolker, B. M., Brooks, M. E., Clark, C. J., Geange, S. W., Poulsen, J. R., Stevens, M. H. H., & White, J.-S. S. (2009). "Generalized linear mixed models: a practical guide for ecology and evolution". Trends in Ecology & Evolution, 24(3), 127–135. https://doi.org/10.1016/j.tree.2008.10.008

## C4 少数クラスタと固定効果の検定

[24] Halekoh, U., & Højsgaard, S. (2014). "A Kenward-Roger Approximation and Parametric Bootstrap Methods for Tests in Linear Mixed Models – The R Package pbkrtest". Journal of Statistical Software, 59(9), 1–32. https://doi.org/10.18637/jss.v059.i09

[25] Luke, S. G. (2017). "Evaluating significance in linear mixed-effects models in R". Behavior Research Methods, 49(4), 1494–1502. https://doi.org/10.3758/s13428-016-0809-y (オンライン先行 2016)

[26] Kenward, M. G., & Roger, J. H. (1997). "Small Sample Inference for Fixed Effects from Restricted Maximum Likelihood". Biometrics, 53(3), 983–(終了頁未確認). https://doi.org/10.2307/2533558 (Crossref は開始頁 983 のみ)

[27] McNeish, D. M., & Stapleton, L. M. (2016). "The Effect of Small Sample Size on Two-Level Model Estimates: A Review and Illustration". Educational Psychology Review, 28(2), 295–314. https://doi.org/10.1007/s10648-014-9287-x (オンライン先行 2014)

[28] Stegmueller, D. (2013). "How Many Countries for Multilevel Modeling? A Comparison of Frequentist and Bayesian Approaches". American Journal of Political Science, 57(3), 748–761. https://doi.org/10.1111/ajps.12001

[29] Elff, M., Heisig, J. P., Schaeffer, M., & Shikano, S. (2021). "Multilevel Analysis with Few Clusters: Improving Likelihood-Based Methods to Provide Unbiased Estimates and Accurate Inference". British Journal of Political Science, 51(1), 412–426. https://doi.org/10.1017/S0007123419000097 (オンライン先行 2020)

[30] Maas, C. J. M., & Hox, J. J. (2005). "Sufficient Sample Sizes for Multilevel Modeling". Methodology, 1(3), 86–92. https://doi.org/10.1027/1614-2241.1.3.86

[31] Pinheiro, J. C., & Bates, D. M. (2000). "Mixed-Effects Models in S and S-PLUS". Springer (Statistics and Computing). https://doi.org/10.1007/b98882 **[内容未確認]**(著者は Springer の書誌ページ。Crossref には著者欄なし)

## C5 FT のシード変動

[32] McCoy, R. T., Min, J., & Linzen, T. (2020). "BERTs of a feather do not generalize together: Large variability in generalization across models with similar test set performance". Proceedings of the Third BlackboxNLP Workshop on Analyzing and Interpreting Neural Networks for NLP, 217–227. https://doi.org/10.18653/v1/2020.blackboxnlp-1.21

[33] Dodge, J., Ilharco, G., Schwartz, R., Farhadi, A., Hajishirzi, H., & Smith, N. (2020). "Fine-Tuning Pretrained Language Models: Weight Initializations, Data Orders, and Early Stopping". arXiv preprint arXiv:2002.06305. https://arxiv.org/abs/2002.06305 **[プレプリント]**

[34] Mosbach, M., Andriushchenko, M., & Klakow, D. (2021). "On the Stability of Fine-tuning BERT: Misconceptions, Explanations, and Strong Baselines". International Conference on Learning Representations (ICLR 2021). https://openreview.net/forum?id=nzpLWnVAyah (OpenReview は bot 検査で未取得。採択は iclr.cc の採択データで確認。arXiv: https://arxiv.org/abs/2006.04884)

[35] Reimers, N., & Gurevych, I. (2017). "Reporting Score Distributions Makes a Difference: Performance Study of LSTM-networks for Sequence Tagging". Proceedings of the 2017 Conference on Empirical Methods in Natural Language Processing, 338–348. https://doi.org/10.18653/v1/D17-1035

[36] Bouthillier, X., Delaunay, P., Bronzi, M., Trofimov, A., Nichyporuk, B., Szeto, J., Mohammadi Sepahvand, N., Raff, E., Madan, K., Voleti, V., Ebrahimi Kahou, S., Michalski, V., Arbel, T., Pal, C., Varoquaux, G., & Vincent, P. (2021). "Accounting for Variance in Machine Learning Benchmarks". Proceedings of Machine Learning and Systems, 3, 747–769. https://proceedings.mlsys.org/paper_files/paper/2021/hash/0184b0cd3cfb185989f858a1d9f5c1eb-Abstract.html

[37] Zhong, R., Ghosh, D., Klein, D., & Steinhardt, J. (2021). "Are Larger Pretrained Language Models Uniformly Better? Comparing Performance at the Instance Level". Findings of the Association for Computational Linguistics: ACL-IJCNLP 2021, 3813–3827. https://doi.org/10.18653/v1/2021.findings-acl.334

[38] Juneja, J., Bansal, R., Cho, K., Sedoc, J., & Saphra, N. (2023). "Linear Connectivity Reveals Generalization Strategies". International Conference on Learning Representations (ICLR 2023). https://openreview.net/forum?id=hY6M0JHl3uL (URL は iclr.cc の採択データから。arXiv: https://arxiv.org/abs/2205.12411)

[39] Sellam, T., Yadlowsky, S., Tenney, I., Wei, J., Saphra, N., D'Amour, A., Linzen, T., Bastings, J., Turc, I., Eisenstein, J., Das, D., & Pavlick, E. (2022). "The MultiBERTs: BERT Reproductions for Robustness Analysis". International Conference on Learning Representations (ICLR 2022, spotlight). https://arxiv.org/abs/2106.16163 (著者順は iclr.cc の採択データ。arXiv 版とは Tenney の位置が違う)

[40] Zhang, T., Wu, F., Katiyar, A., Weinberger, K. Q., & Artzi, Y. (2021). "Revisiting Few-sample BERT Fine-tuning". International Conference on Learning Representations (ICLR 2021). https://openreview.net/forum?id=cO1IH43yUF (URL は iclr.cc の採択データから。arXiv: https://arxiv.org/abs/2006.05987)

[41] Bui, N. T., Savova, G. K., & Wang, L. (2025). "Assessing the Macro and Micro Effects of Random Seeds on Fine-Tuning Large Language Models". Proceedings of the 14th International Joint Conference on Natural Language Processing and the 4th Conference of the Asia-Pacific Chapter of the Association for Computational Linguistics (IJCNLP-AACL 2025, short), 41–46. https://doi.org/10.18653/v1/2025.ijcnlp-short.3
