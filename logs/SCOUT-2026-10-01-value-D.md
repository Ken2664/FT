# SCOUT 2026-10-01 value-D: 「平行なら共有」の推論の妥当性

- 作成: SCOUT サブエージェント(Opus 5.5)、2026-10-01
- 範囲: 角度 D(「知識性に沿った規則適用率の減衰がタスク型間で平行 ⇒ 共有された計算／交互作用あり ⇒ 別経路」という推論は方法論的に妥当か)
- **このファイルの全項目は CLAUDE.md §3.6・ADR-102 の意味で「未検証」**。書誌は API の生データから転記したが、原典 PDF との突き合わせと採否は人間が行う(CLAUDE.md §8)。`Documents/refs.bib` は一切編集していない。

## 取得経路の宣言

| 用途 | 経路 | 備考 |
|---|---|---|
| 候補の発見 | エージェントの既知候補(親の指示リスト)+ WebSearch 2 回 + Crossref の `query.bibliographic` 検索 | WebSearch の出力からは書誌を一切取っていない |
| 書誌(著者・年・誌名・巻号頁・DOI) | **Crossref API** `api.crossref.org/works/<DOI>` の JSON | 雑誌論文・書籍・ACL Anthology 論文(ACL の DOI は Crossref 登録) |
| 書誌(arXiv) | **arXiv API** `export.arxiv.org/api/query?id_list=...` | 著者・題名・投稿日・著者コメント・journal_ref |
| ICLR 採択の確認(補助) | OpenReview API v2 `api2.openreview.net/notes/search` の `venue` フィールド(生 JSON) | **ADR-102 の列挙外の経路**。[43][47][50][53] の会場はこれのみで確認。人間の再確認を要す |
| 要旨の逐語引用 | Crossref `abstract`、arXiv `<summary>`、OpenAlex `abstract_inverted_index` の復元、Semantic Scholar Graph API `abstract`、PubMed efetch `AbstractText` のいずれか(行ごとに明記) | いずれも DB の生テキスト。モデル要約ではない。取得できない場合は「要旨の逐語は未取得」 |
| WebFetch | **使用していない** | — |

- 「本研究との関係」欄の記述のうち、**要旨を取得できなかった文献については題名と一般的な知識に基づく記述であり、原典本文は未確認**(行に「本文未確認」と付す)。
- `Documents/refs.bib` に既収載のもの: [20] Hinton & Shallice 1991、[21] Plaut 1995、[53] Nikankin et al. 2025(grep で確認。内容の照合はしていない)。
- 2026 年の arXiv ID は本ファイルに含まれない。

---

## D1 要因計画の交互作用は尺度依存である(単調変換で生じ・消える「除去可能な交互作用」、天井・床効果による見かけの交互作用)

**判定: 支持(強い合意)。ただし「どの尺度で検定すべきか」については対立あり。**

| # | 著者(年) | 題名 | 掲載誌・巻号頁(出所) | DOI / URL | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 1 | Loftus, G. R. (1978) | On interpretation of interactions | Memory & Cognition 6(3):312–319(Crossref) | https://doi.org/10.3758/BF03197461 | 要旨の逐語は未取得 | 除去可能(非交差)交互作用の古典。[10][12] が本論文を「非交差交互作用は尺度変換で除去可能」と要約している(本文未確認) |
| 2 | Bogartz, R. S. (1976) | On the meaning of statistical interactions | Journal of Experimental Child Psychology 22(1):178–183(Crossref) | https://doi.org/10.1016/0022-0965(76)90099-0 | 要旨の逐語は未取得 | 統計的交互作用の意味が測定尺度に依存するという早期の議論(本文未確認) |
| 3 | Busemeyer, J. R. (1980) | Importance of measurement theory, error theory, and experimental design for testing the significance of interactions | Psychological Bulletin 88(1):237–244(Crossref) | https://doi.org/10.1037/0033-2909.88.1.237 | 要旨の逐語は未取得 | 交互作用の有意性検定は測定論・誤差論・計画に依存する(題名から。本文未確認) |
| 4 | Sternberg, S. (1969) | The discovery of processing stages: Extensions of Donders' method | Acta Psychologica 30:276–315(Crossref) | https://doi.org/10.1016/0001-6918(69)90055-9 | 要旨の逐語は未取得 | **反対側の古典**: 加法性(交互作用なし)から別段階を推論する加法要因法。本研究の「平行 ⇒ 共有」とは推論の向きが逆である点に注意(加法要因法では「加法的 ⇒ 別段階」)。尺度が区間尺度(RT)であることを前提にする(本文未確認) |
| 5 | Ai, C.; Norton, E. C. (2003) | Interaction terms in logit and probit models | Economics Letters 80(1):123–129(Crossref) | https://doi.org/10.1016/S0165-1765(03)00032-6 | 要旨の逐語は未取得 | logit の積項係数は確率尺度上の交互作用効果と一致しない(符号すら異なりうる)ことを示した論文として広く引用される(本文未確認) |
| 6 | Loftus, G. R.; Oberg, M. A.; Dillon, A. M. (2004) | Linear theory, dimensional theory, and the face-inversion effect | Psychological Review 111(4):835–863(Crossref) | https://doi.org/10.1037/0033-295x.111.4.835 | "By dimensional theory, independent variables yield values on internal dimensions that in turn determine performance."(OpenAlex) | 観測量上の交互作用ではなく「内部次元」上で考えると結論が変わる実例。本研究の「規則適用率」と潜在的な「病変の強さ」の区別に直結 |
| 7 | Jaeger, T. F. (2008) | Categorical data analysis: Away from ANOVAs (transformation or not) and towards logit mixed models | Journal of Memory and Language 59(4):434–446(Crossref) | https://doi.org/10.1016/j.jml.2007.11.007 | "I show that even after applying the arcsine-square-root transformation to proportional data, ANOVA can yield spurious results."(Semantic Scholar) | 比率データには logit 混合モデル、という本研究の現行選択(混合ロジスティック)を支持する |
| 8 | Dixon, P. (2008) | Models of accuracy in repeated-measures designs | Journal of Memory and Language 59(4):447–456(Crossref) | https://doi.org/10.1016/j.jml.2007.11.004 | 要旨の逐語は未取得 | 反復測定の正答率に対する logistic 混合モデルの議論(本文未確認)。[7] と同号 |
| 9 | Berry, W. D.; DeMeritt, J. H. R.; Esarey, J. (2010) | Testing for interaction in binary logit and probit models: Is a product term essential? | American Journal of Political Science 54(1):248–266(Crossref) | https://doi.org/10.1111/j.1540-5907.2009.00429.x | "Political scientists presenting binary dependent variable (BDV) models often hypothesize that variables interact to influence the probability of an event, Pr(Y)."(Crossref) | 仮説が「確率」上のものか「潜在傾向(log-odds)」上のものかで、積項の要否と検定が変わる。**仮説の尺度を先に決めよ**という立場 |
| 10 | Wagenmakers, E.-J.; Krypotos, A.-M.; Criss, A. H.; Iverson, G. (2012) | On the interpretation of removable interactions: A survey of the field 33 years after Loftus | Memory & Cognition 40(2):145–160(Crossref) | https://doi.org/10.3758/s13421-011-0158-0 | "These removable interactions are tied to the scale of measurement for the dependent variable and therefore do not allow unambiguous conclusions about latent psychological processes."(OpenAlex) | 主要根拠。非交差交互作用からは潜在過程について曖昧さなく結論できない |
| 11 | Satagopan, J. M.; Elston, R. C. (2013) | Evaluation of removable statistical interaction for binary traits | Statistics in Medicine 32(7):1164–1190(Crossref) | https://doi.org/10.1002/sim.5628 | "Certain interactions may be eliminated via a transformation of the outcome such that the relationship between the risk factors and the outcome is additive on the transformed scale."(Crossref) | 二値アウトカムで「除去可能な交互作用」を検定する統計手法。本研究の二値 DV に直接対応(独立分野=遺伝疫学からの裏付け) |
| 12 | Garcia-Marques, L.; Garcia-Marques, T.; Brauer, M. (2014) | Buy three but get only two: The smallest effect in a 2 × 2 ANOVA is always uninterpretable | Psychonomic Bulletin & Review 21(6):1415–1430(Crossref) | https://doi.org/10.3758/s13423-014-0640-3 | "Uninterpretable interactions are ambiguous, because they may be due to two additive main effects (no interaction) and a nonlinear relationship between the (latent) outcome variable and its indicator."(Semantic Scholar) | 潜在変数と指標の非線形関係だけで交互作用が出る/消える。本研究では「規則適用率」が指標、「病変の効き」が潜在 |
| 13 | Mize, T. (2019) | Best practices for estimating, interpreting, and presenting nonlinear interaction effects | Sociological Science 6:81–117(Crossref) | https://doi.org/10.15195/v6.a4 | "The consequences of approaching nonlinear interaction effects the way one would approach a linear interaction effect are severe and can often result in incorrect conclusions."(OpenAlex) | logit の交互作用は確率尺度の差の差(second differences)でも報告すべき、という実務指針として引用される(後半は本文未確認) |
| 14 | Rohrer, J. M.; Arslan, R. C. (2021) | Precise answers to vague questions: Issues with interactions | Advances in Methods and Practices in Psychological Science 4(2)(Crossref。頁番号は Crossref に無し) | https://doi.org/10.1177/25152459211007368 | "First, interactions can be removable in the sense that they appear or disappear depending on scaling decisions, with consequences for a variety of situations (e.g., binary or categorical outcomes, bounded scales with floor and ceiling effects)."(Crossref) | **天井・床効果と二値 DV を明示**。本研究のパイロット(複数セルで 1.000)にそのまま当たる |
| 15 | Domingue, B. W.; Kanopka, K.; Trejo, S.; Rhemtulla, M.; Tucker-Drob, E. M. (2024; online 2022) | Ubiquitous bias and false discovery due to model misspecification in analysis of statistical interactions: The role of the outcome's distribution and metric properties | Psychological Methods 29(6):1164–1179(Crossref) | https://doi.org/10.1037/met0000532 | "Here, we consider bias and false discovery associated with estimates of interaction parameters as a function of the distributional and metric properties of the outcome variable."(OpenAlex) | アウトカムの分布・尺度性質による交互作用の偽発見。打ち切り(=天井)も扱う |

**反証・留保**

- 尺度依存は**非交差(順序保存)**の交互作用に限られる。交差交互作用(順序の逆転)はどの単調変換でも除去できない [10][12]。したがって「別経路」の主張は交差がある場合には尺度に頑健になりうる。
- 対立点: [9][13] は「仮説が log-odds(潜在傾向)上で述べられているなら logit の積項検定は正当」とする。つまり本研究の LRT(logit 尺度、df = 2)は、**仮説を潜在 log-odds 上の平行性として明示的に定義すれば**それ自体は誤りではない。問題は「共有された計算」という仮説がどの尺度で平行を予言するかを理論が指定していない点にある [14]。
- [4] の加法要因法は「交互作用の有無から過程構造を推論する」こと自体には長い実績があることを示す(ただし区間尺度の RT が前提)。

---

## D2 解離・病変パターンから機能的構造(共有か別か)を推論することには既知の陥穽がある(単解離・二重解離はモジュール性を含意しない、逆連合の原理、「1 過程か 2 過程か」の原理的手法としての state-trace 解析)

**判定: 前半(解離からの推論は脆い)は支持。後半(state-trace が決定的な代替)は対立あり。**

| # | 著者(年) | 題名 | 掲載誌・巻号頁(出所) | DOI / URL | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 16 | Bamber, D. (1979) | State-trace analysis: A method of testing simple theories of causation | Journal of Mathematical Psychology 19(2):137–181(Crossref) | https://doi.org/10.1016/0022-2496(79)90016-6 | 要旨の逐語は未取得 | state-trace 解析の原典(本文未確認) |
| 17 | Caramazza, A. (1986) | On drawing inferences about the structure of normal cognitive systems from the analysis of patterns of impaired performance: The case for single-patient studies | Brain and Cognition 5(1):41–66(Crossref) | https://doi.org/10.1016/0278-2626(86)90061-8 | "It is shown that given certain assumptions, only the single-case method allows valid inferences about the structure of cognitive systems from the analysis of impaired performance."(OpenAlex) | 病変からの推論は「ある仮定の下で」のみ妥当。本研究ではシード(=個体)ごとの集計 vs 群平均の問題に対応しうる(推論) |
| 18 | Shallice, T. (1988) | From Neuropsychology to Mental Structure | Cambridge University Press(書籍。ISBN 9780521308748 / 9780521313605。Crossref) | https://doi.org/10.1017/CBO9780511526817 | "He distinguishes two types of theories of normal function - primarily modular and primary non-modular - and argues that the problems of making valid inferences about normal function from studies of brain-damaged subjects are more severe for the latter."(OpenAlex。出版社の内容紹介文) | 非モジュール的な系では病変からの推論がより困難。LLM は典型的に非モジュール的 |
| 19 | Dunn, J. C.; Kirsner, K. (1988) | Discovering functionally independent mental processes: The principle of reversed association | Psychological Review 95(1):91–101(Crossref) | https://doi.org/10.1037/0033-295X.95.1.91 | 抜粋: "it is possible to posit single processes that mimic both single and double dissociation"(OpenAlex。文の一部) | 単一過程でも解離が出る。代わりに「逆連合」(タスク間の非単調関係)を基準にせよ。**本研究の「平行でない ⇒ 別経路」への直接の反論** |
| 20 | Hinton, G. E.; Shallice, T. (1991) | Lesioning an attractor network: Investigations of acquired dyslexia | Psychological Review 98(1):74–95(Crossref) | https://doi.org/10.1037/0033-295X.98.1.74 | "When damaged, the network exhibited characteristics that resembled several of the phenomena found in deep dyslexia and semantic-access dyslexia."(OpenAlex) | 人工ネットの病変で症候群様のパターンが出る先例(refs.bib 既収載) |
| 21 | Plaut, D. C. (1995) | Double dissociation without modularity: Evidence from connectionist neuropsychology | Journal of Clinical and Experimental Neuropsychology 17(2):291–321(Crossref) | https://doi.org/10.1080/01688639508405124 | "The functional specialization in the network that gives rise to the double dissociation is not transparently related to the network's structure, as modular theories assume."(OpenAlex) | 分離可能な部品のない網でも二重解離(refs.bib 既収載) |
| 22 | Bullinaria, J. A.; Chater, N. (1995) | Connectionist modelling: Implications for cognitive neuropsychology | Language and Cognitive Processes 10(3–4):227–264(Crossref) | https://doi.org/10.1080/01690969508407095 | "However, when these studies are repeated using sufficiently larger and more distributed networks, which are presumably more psychologically and biologically relevant, double dissociations are not observed."(OpenAlex) | **[21] への留保**: 小さい網の解離は個々のユニットの寄与が大きいときの産物でありうる。大規模分散網(=LLM)での病変パターンの解釈に関わる |
| 23 | Juola, P.; Plunkett, K. (1998 会議; Crossref 上は 2022 年 Routledge 再刊) | Why double dissociations don't mean much | Proceedings of the Twentieth Annual Conference of the Cognitive Science Society, pp. 561–566(Crossref) | https://doi.org/10.4324/9781315782416-106 | 要旨の逐語は未取得 | 題名どおりの懐疑論(本文未確認)。年は「第 20 回」から 1998 と推定、Crossref の日付は再刊時 |
| 24 | Van Orden, G. C.; Pennington, B. F.; Stone, G. O. (2001) | What do double dissociations prove? | Cognitive Science 25(1):111–172(Crossref) | https://doi.org/10.1207/s15516709cog2501_5 | "This article questions the utility of assuming modularity, as it examines a paradigmatic double dissociation of reading modules."(Crossref) | 解離の論理はモジュール性を前提にしている(循環)との批判 |
| 25 | Dunn, J. C.; Kirsner, K. (2003) | What can we infer from double dissociations? | Cortex 39(1):1–7(Crossref) | https://doi.org/10.1016/S0010-9452(08)70070-4 | 要旨の逐語は未取得(PubMed にも要旨なし) | Cortex 特集の論点整理(本文未確認) |
| 26 | Newell, B. R.; Dunn, J. C. (2008) | Dimensions in data: Testing psychological models using state-trace analysis | Trends in Cognitive Sciences 12(8):285–290(Crossref) | https://doi.org/10.1016/j.tics.2008.04.009 | "We argue and illustrate that using dissociation logic to draw conclusions about the dimensionality of data is flawed."(PubMed) | 「1 過程か 2 過程か」には state-trace を使え、という主張の要約的文献 |
| 27 | Davies, M. (2010) | Double dissociation: Understanding its role in cognitive neuropsychology | Mind & Language 25(5):500–540(Crossref) | https://doi.org/10.1111/j.1468-0017.2010.01399.x | "First, arguments from double dissociation to separate modules work by inference to the best, not the only possible, explanation."(OpenAlex) | **擁護側**: 解離の推論は演繹ではなく最良説明への推論として有効。本研究の主張の強さ(「判別する」)の言い回しに関わる |
| 28 | Prince, M.; Brown, S.; Heathcote, A. (2012) | The design and analysis of state-trace experiments | Psychological Methods 17(1):78–99(Crossref) | https://doi.org/10.1037/a0025809 | "State-trace analysis (Bamber, 1979) addresses a question of interest in many areas of psychological research: Does 1 or more than 1 latent (i.e., not directly observed) variable mediate an interaction between 2 experimental manipulations?"(OpenAlex) | 正答率データ用の state-trace の**設計と Bayes 因子による解析**。本研究の問いの形式(2 操作の交互作用を 1 潜在変数が媒介するか)と一致 |
| 29 | Ashby, F. G. (2014) | Is state-trace analysis an appropriate tool for assessing the number of cognitive systems? | Psychonomic Bulletin & Review 21(4):935–946(Crossref) | https://doi.org/10.3758/s13423-013-0578-x | "State-trace analysis was not developed for this purpose but, rather, to identify data sets that are consistent with variation in a single parameter."(Semantic Scholar) | **state-trace への反論**: 「1 パラメータ」と「1 システム」は別物 |
| 30 | Yeates, F.; Wills, A. J.; Jones, F. W.; McLaren, I. P. L. (2015) | State-trace analysis: Dissociable processes in a connectionist network? | Cognitive Science 39(5):1047–1061(Crossref) | https://doi.org/10.1111/cogs.12185 | "This article reports simulations using the simple recurrent network (SRN; Elman, 1990) in which changes to the learning rate produced state-trace plots with multiple functions."(OpenAlex) | **人工ネットでの反例**: 単一の網・単一パラメータ(学習率)の変化でも複数曲線が出る。LLM に state-trace を当てる際の直接の警告 |
| 31 | Kalish, M. L.; Dunn, J. C.; Burdakov, O. P.; Sysoev, O. (2016) | A statistical test of the equality of latent orders | Journal of Mathematical Psychology 70:1–11(Crossref) | https://doi.org/10.1016/j.jmp.2015.10.004 | 要旨の逐語は未取得 | state-trace の単調性の頻度論的検定(本文未確認) |
| 32 | Davis-Stober, C. P.; Morey, R. D.; Gretton, M.; Heathcote, A. (2016) | Bayes factors for state-trace analysis | Journal of Mathematical Psychology 72:116–129(Crossref) | https://doi.org/10.1016/j.jmp.2015.08.004 | 要旨の逐語は未取得 | state-trace の Bayes 因子(本文未確認) |
| 33 | Dunn, J. C.; Kalish, M. L. (2018) | State-Trace Analysis | Springer(Computational Approaches to Cognition and Perception シリーズ。ISBN 9783319731285 / 9783319731292。Crossref) | https://doi.org/10.1007/978-3-319-73129-2 | 要旨の逐語は未取得 | 体系的な教科書。第 1 章 "The Logic of State-Trace Analysis"(doi:10.1007/978-3-319-73129-2_1, pp. 3–19)、第 4 章 "Statistical Methodology"(_4, pp. 43–55)が Crossref に登録されている |
| 34 | Stephens, R. G.; Matzke, D.; Hayes, B. K. (2019) | Disappearing dissociations in experimental psychology: Using state-trace analysis to test for multiple processes | Journal of Mathematical Psychology 90:3–22(Crossref) | https://doi.org/10.1016/j.jmp.2018.11.003 | 要旨の逐語は未取得 | 解離が state-trace の基準では消える事例の整理(題名から。本文未確認) |

**反証・留保**

- 解離論理の擁護: [17][18][27] は、仮定を明示すれば病変からの推論は「最良説明への推論」として有効とする。全面否定ではない。
- state-trace への批判: [29] は「単一パラメータと整合」≠「単一システム」、[30] は単一網でも学習率の変化だけで複数曲線が出ることを示した。つまり**state-trace でも「1 本の曲線 ⇒ 共有された概念」は言えない**。言えるのは「1 つの潜在量で説明できるデータである/ない」まで。
- [19] の逆連合の原理: 「別の過程」の証拠は、2 タスクの成績が条件を通じて**非単調**に関係すること(逆連合)である。単なる「平行でない」(=傾きが違うが順序は保存)では足りない。

---

## D3 人工ニューラルネット(特に LLM)における病変・アブレーションに基づく推論には既知の陥穽がある(補償・自己修復、分散表現、解析手法の錯覚)

**判定: 支持。ただし病変論理が人工ネットで有効に働いた例もある(対立あり)。**

| # | 著者(年) | 題名 | 掲載誌・巻号頁(出所) | DOI / URL | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 35 | Jonas, E.; Kording, K. P. (2017) | Could a neuroscientist understand a microprocessor? | PLOS Computational Biology 13(1):e1005268(Crossref) | https://doi.org/10.1371/journal.pcbi.1005268 | "To address this, here we take a classical microprocessor as a model organism, and use our ability to perform arbitrary experiments on it to see if popular data analysis methods from neuroscience can elucidate the way it processes information."(OpenAlex) | 構造が完全に既知の系でも病変解析は誤った機能局在を導く、という代表的警告(結果部分は本文未確認) |
| 36 | Morcos, A. S.; Barrett, D. G. T.; Rabinowitz, N. C.; Botvinick, M. (2018) | On the importance of single directions for generalization | ICLR 2018(arXiv 著者コメント)/ arXiv:1803.06959 | https://arxiv.org/abs/1803.06959 | 抜粋: "we find that class selectivity is a poor predictor of task importance"(arXiv) | 選択的に見えるユニットが病変で重要とは限らない |
| 37 | Meyes, R.; Lu, M.; Waubert de Puiseau, C.; Meisen, T. (2019) | Ablation studies in artificial neural networks | 会場未確認(arXiv:1901.08644 のみ) | https://arxiv.org/abs/1901.08644 | "Furthermore, some of these representations are redundant, awarding the network a certain robustness to structural damages."(arXiv) | 冗長性による病変への頑健性 |
| 38 | Lakretz, Y.; Kruszewski, G.; Desbordes, T.; Hupkes, D.; Dehaene, S.; Baroni, M. (2019) | The emergence of number and syntax units in LSTM language models | NAACL-HLT 2019, Vol. 1, pp. 11–20(Crossref) | https://doi.org/10.18653/v1/N19-1002 | "We discover that long-distance number information is largely managed by two `number units'."(arXiv) | **擁護側の例**: 神経心理学型の単一ユニット病変が言語モデルで解釈可能な局在を与えた |
| 39 | Hupkes, D.; Dankers, V.; Mul, M.; Bruni, E. (2020) | Compositionality decomposed: How do neural networks generalise? | Journal of Artificial Intelligence Research 67:757–795(Crossref) | https://doi.org/10.1613/jair.1.11674 | "Despite a multitude of empirical studies, little consensus exists on whether neural networks are able to generalise compositionally, a controversy that, in part, stems from a lack of agreement about what it means for a neural model to be compositional."(Crossref) | 「統合された概念」の操作的定義が無いと、汎化パターンの解釈が割れるという点で本研究の主張の定義問題に関わる |
| 40 | Saxe, A.; Nelli, S.; Summerfield, C. (2021) | If deep learning is the answer, what is the question? | Nature Reviews Neuroscience 22(1):55–67(Crossref) | https://doi.org/10.1038/s41583-020-00395-8 | "If so, how can neuroscientists use deep networks to model and understand biological brains?"(PubMed) | 深層網を神経科学的手法で理解する際の総論(病変論理の限界の議論は本文未確認) |
| 41 | Bolukbasi, T.; Pearce, A.; Yuan, A.; Coenen, A.; Reif, E.; Viégas, F.; Wattenberg, M. (2021) | An interpretability illusion for BERT | 会場未確認(arXiv:2104.07143 のみ) | https://arxiv.org/abs/2104.07143 | "Activations of individual neurons in the network may spuriously appear to encode a single, simple concept, when in fact they are encoding something far more complex."(arXiv) | 狭いデータでの「概念」解釈の錯覚。要旨は複数データセットでの仮説検証の重要性も述べる |
| 42 | Dobs, K.; Martinez, J.; Kell, A. J. E.; Kanwisher, N. (2022) | Brain-like functional specialization emerges spontaneously in deep neural networks | Science Advances 8(11):eabl8913(Crossref) | https://doi.org/10.1126/sciadv.abl8913 | "We find that networks trained on object recognition perform poorly on face recognition and vice versa and that networks optimized for both tasks spontaneously segregate themselves into separate systems for faces and objects."(Crossref) | **擁護側の例**: 深層網内の機能分離を病変等で示した研究(病変手法の詳細は本文未確認) |
| 43 | Wang, K.; Variengien, A.; Conmy, A.; Shlegeris, B.; Steinhardt, J. (2023) | Interpretability in the wild: A circuit for indirect object identification in GPT-2 small | ICLR 2023(OpenReview の venue 欄のみで確認)/ arXiv:2211.00593 | https://arxiv.org/abs/2211.00593 | "Though these criteria support our explanation, they also point to remaining gaps in our understanding."(arXiv) | 回路同定の代表例。本文中の「backup heads」(病変時に代替する頭)は本研究の補償の論点に関わるが、本文未確認 |
| 44 | McGrath, T.; Rahtz, M.; Kramar, J.; Mikulik, V.; Legg, S. (2023) | The Hydra effect: Emergent self-repair in language model computations | 会場未確認(arXiv:2307.15771 のみ) | https://arxiv.org/abs/2307.15771 | 抜粋: "a form of adaptive computation where ablations of one attention layer of a language model cause another layer to compensate (which we term the Hydra effect)"(arXiv) | **補償**: 病変の行動的影響は計算上の重要度を過小評価しうる |
| 45 | Kanwisher, N.; Khosla, M.; Dobs, K. (2023) | Using artificial neural networks to ask 'why' questions of minds and brains | Trends in Neurosciences 46(3):240–254(Crossref) | https://doi.org/10.1016/j.tins.2022.12.008 | "Here we highlight the recent success of this strategy in explaining why the visual and auditory systems work the way they do, at both behavioral and neural levels."(OpenAlex) | 人工網を神経心理学・神経科学の論理の試験台にする立場(擁護側) |
| 46 | Stolfo, A.; Belinkov, Y.; Sachan, M. (2023) | A mechanistic interpretation of arithmetic reasoning in language models using causal mediation analysis | EMNLP 2023, pp. 7035–7052(Crossref) | https://doi.org/10.18653/v1/2023.emnlp-main.435 | "To assess the specificity of the observed activation dynamics, we compare the effects of different model components on arithmetic queries with other tasks, including number retrieval from prompts and factual knowledge questions."(arXiv) | 算術の内部機構を介入で局在化し、**他タスクとの比較で特異性を見る**。本研究の T1/T2 比較の機構レベルの補完に使える設計 |
| 47 | Makelov, A.; Lange, G.; Nanda, N. (2024) | Is this the subspace you are looking for? An interpretability illusion for subspace activation patching | ICLR 2024(OpenReview の venue 欄のみで確認。arXiv コメントは NeurIPS 2023 Workshop)/ arXiv:2311.17030 | https://arxiv.org/abs/2311.17030 | 抜粋: "this effect may be achieved by activating a dormant parallel pathway leveraging another subspace that is causally disconnected from model outputs"(arXiv) | 介入で行動が変わっても、それは別の休眠経路の活性化でありうる。LoRA 病変も同型の錯覚を生みうる(推論) |
| 48 | Zhang, F.; Nanda, N. (2024) | Towards best practices of activation patching in language models: Metrics and methods | ICLR 2024(arXiv 著者コメント)/ arXiv:2309.16042 | https://arxiv.org/abs/2309.16042 | 抜粋: "we find that varying these hyperparameters could lead to disparate interpretability results"(arXiv) | **指標(確率 vs logit 差など)の選択で解釈が変わる**。D1 の尺度依存の機構解析版 |
| 49 | Rushing, C.; Nanda, N. (2024) | Explorations of self-repair in language models | ICML 2024, PMLR 235:42836–42855(arXiv journal_ref) / arXiv:2402.15390 | https://arxiv.org/abs/2402.15390 | 抜粋: "We further show that on the full training distribution self-repair is imperfect, as the original direct effect of the head is not fully restored, and noisy"(arXiv) | 自己修復はプロンプトにより大きくばらつく。T1 と T2 で補償量が違えば、それだけで傾きの差が出うる(推論) |
| 50 | Jain, S.; Kirk, R.; Lubana, E. S.; Dick, R. P.; Tanaka, H.; Grefenstette, E.; Rocktäschel, T.; Krueger, D. S. (2024) | Mechanistically analyzing the effects of fine-tuning on procedurally defined tasks | ICLR 2024(OpenReview の venue 欄のみで確認)/ arXiv:2311.12786 | https://arxiv.org/abs/2311.12786 | 抜粋: "a minimal transformation, which we call a 'wrapper', is typically learned on top of the underlying model capabilities, creating the illusion that they have been modified"(arXiv) | **最重要**: FT 病変は基盤能力でなく「ラッパー」を学ぶことが多い。平行な減衰は「共有された加算概念」ではなく「共有されたラッパー(入力形式トリガ)」を反映しうる |
| 51 | Prakash, N.; Rott Shaham, T.; Haklay, T.; Belinkov, Y.; Bau, D. (2024) | Fine-tuning enhances existing mechanisms: A case study on entity tracking | ICLR 2024(arXiv 著者コメント)/ arXiv:2402.14811 | https://arxiv.org/abs/2402.14811 | 抜粋: "(i) in both the original model and its fine-tuned versions primarily the same circuit implements entity tracking"(arXiv) | FT は既存回路を強化する。LoRA の効果が既存の加算経路のどこに乗るかの事前予想に関わる |
| 52 | Mahowald, K.; Ivanova, A. A.; Blank, I. A.; Kanwisher, N.; Tenenbaum, J. B.; Fedorenko, E. (2024) | Dissociating language and thought in large language models | Trends in Cognitive Sciences 28(6):517–540(Crossref) | https://doi.org/10.1016/j.tics.2024.01.011 | "We ground this distinction in human neuroscience, which has shown that formal and functional competence rely on different neural mechanisms."(Semantic Scholar / arXiv で同文) | 神経心理学的解離の枠組みを LLM 評価に持ち込む代表例(擁護側。ただし行動の解離から機構を断定はしていない点は本文未確認) |
| 53 | Nikankin, Y.; Reusch, A.; Mueller, A.; Belinkov, Y. (2025) | Arithmetic without algorithms: Language models solve math with a bag of heuristics | ICLR 2025(OpenReview の venue 欄。refs.bib 既収載)/ arXiv:2410.21272 | https://arxiv.org/abs/2410.21272 | "Overall, our experimental results across several LLMs show that LLMs perform arithmetic using neither robust algorithms nor memorization; rather, they rely on a "bag of heuristics"."(arXiv) | 要旨は「オペランドが一定範囲にあるとき発火するニューロン」型のヒューリスティクスに言及。**既知性(範囲内/範囲外)軸が範囲ヒューリスティクスと交絡する**可能性(推論) |

**反証・留保**

- 病変論理が LLM/DNN で解釈可能な結果を与えた例もある [38][42][46]。全否定ではなく、「行動上の病変パターンだけでは足りず、補償・冗長性・指標選択を統制した機構レベルの確認が要る」が文献の大勢 [44][47][48][49]。
- [50][51] は合成タスク/特定タスクでの結果であり、算術 LoRA 病変への一般化は未確認(推論)。

---

## D4 総括: 本研究の主要検定を解釈可能にするために要るもの(事実と推論を分ける)

> 注意: 以下は**案**である。主要検定は事前登録済み(ADR-056 / 05_STATISTICS.md §2)であり、変更・追加の決定は人間が行う(CLAUDE.md §2「事前登録した解析計画を実験後に変更する」禁止、§8)。採るとしても副次・感度分析として ADR に記録する形が想定される。

### 文献上の事実(引用付き)

1. **非交差の交互作用は尺度変換で除去可能**であり、潜在過程について曖昧さなく結論できない [1][10][11][12][14]。交差交互作用だけはどの単調変換でも除去できない [10][12]。
2. **二値・比率 DV、天井・床効果は除去可能な交互作用の典型的な発生源** [14][15]。logit の積項と確率尺度の交互作用は一致しない [5][9][13]。比率には logit 混合モデルが推奨される [7][8] が、それで尺度問題が解消するわけではない [9][14]。
3. 仮説が log-odds(潜在傾向)上で定義されていれば logit の積項検定は正当化されうる [9][13]。仮説の尺度を理論が指定していないことが問題の核心 [14]。
4. **解離(=平行でない)から別過程を推論することはできない**。単一過程でも単解離・二重解離が出る [19][21][24][26]。別過程の証拠としてより厳しい基準は**逆連合/state-trace の非単調性** [16][19][26][28]。
5. **state-trace の単調(1 本の曲線)でも「1 システム」は言えない**。言えるのは「1 つの潜在量と整合」まで [29]。人工網では単一パラメータの変化で複数曲線が出た [30]。
6. state-trace には設計指針と統計検定がある(正答率データの Bayes 因子 [28][32]、単調性の検定 [31]、教科書 [33])。
7. LLM の病変では自己修復・補償 [44][49]、休眠経路による介入の錯覚 [47]、指標選択による結論の変化 [48] が報告されている。FT は能力そのものではなく「ラッパー」を学ぶことが多い [50]、既存回路を強化する [51]。
8. LLM の算術は範囲型ヒューリスティクスの束で実装されているとの報告がある [53]。

### 推論(SCOUT の推論。未検証)

- **(a) 主要検定は「共有」の必要条件でも十分条件でもない。** 1 つの潜在的な「病変の効き」(既知性で単調に減る)と、タスクごとに異なる単調な出力写像(例: T2 は文章題の解析段で別の天井/床を持つ)の組み合わせは、logit 上で非ゼロの交互作用を生む [6][12]。逆に、別経路でも logit 上でたまたま平行になりうる。したがって LRT(df = 2)の有意/非有意を「別/共有」に直結させる文言は、方法論文献の基準 [10][14][19][26] では強すぎる。
- **(b) 天井セル(rule rate = 1.000)は二重に問題。** 尺度問題としては情報を持たない(どの単調変換でも端点)[14][15]。推定上は logit が ±∞ に向かい、混合ロジスティックの交互作用推定と LRT が不安定になる(準完全分離。これは一般的統計知識で、本ファイルの文献では直接裏付けていない)。天井を避ける設計(病変強度の段階化、学習途中のチェックポイント、規則トークンの対数確率など連続 DV の併用)が要る。
- **(c) 追加すべき解析の候補**:
  1. **state-trace プロット**: x = T1 の rule rate、y = T2 の rule rate、点 = 既知性 3 水準 ×(病変強度・チェックポイント・シード)。1 本の単調曲線か、順序逆転(逆連合)があるかを [28][31][32] の手法で検定。既知性 3 点だけでは単調性はほぼ自明に満たされるため、**状態を動かす第 2 の操作(例: LoRA のスケール α、学習ステップ)で点を増やす**必要がある [28]。
  2. **尺度頑健性の報告**: 交互作用を logit と確率差(second differences [13])の両方で報告し、結論が尺度で反転するなら「除去可能 → 判定不能」と明記する [10][14]。
  3. **交差の有無を主たる「別経路」基準にする**: 既知性に沿った T1 と T2 の順序が逆転するか(nonremovable)[10][12][19]。
  4. **「平行」の主張には同等性検定**: 交互作用対比に対して TOST(SESOI を log-odds と確率差のどちらで置くかを事前に固定)[54][55]。CLAUDE.md の TOST 規定と整合。
  5. **機構レベルの補完**: T1 と T2 の間で activation patching を行い、LoRA の効果が同じ成分を経由するかを見る [46][48]。その際、休眠経路の錯覚 [47] と自己修復 [44][49] を考慮し、指標を複数併記する [48]。
- **(d) 「共有された計算」の対抗仮説を明示する必要。** 平行な減衰は、(i) 統合された加算概念、(ii) 両タスクに共通する FT ラッパー/入力トリガ [50]、(iii) 両タスクが共通に使う範囲型ヒューリスティクス [53] のいずれでも生じうる。行動データの平行性だけでは (i) を (ii)(iii) から区別できない。
- **(e) 主張の強さ**: 病変からの推論は「最良説明への推論」として位置づけるのが擁護側の文献でも標準 [27]。論文の claim は「平行性は共有された潜在量と整合する」程度に留めるのが文献上安全(claim の確定は人間)。

### 追加文献(D4 のみで使用)

| # | 著者(年) | 題名 | 掲載誌・巻号頁(出所) | DOI / URL | 要旨からの逐語引用 | 本研究との関係 |
|---|---|---|---|---|---|---|
| 54 | Lakens, D. (2017) | Equivalence Tests(Crossref の title。副題は下注) | Social Psychological and Personality Science 8(4):355–362(Crossref) | https://doi.org/10.1177/1948550617697177 | "Currently, researchers often incorrectly conclude an effect is absent based a nonsignificant result."(Crossref。原文の "based a" のまま) | 「平行」= 交互作用の不在を主張するなら TOST |
| 55 | Lakens, D.; Scheel, A. M.; Isager, P. M. (2018) | Equivalence testing for psychological research: A tutorial | Advances in Methods and Practices in Psychological Science 1(2):259–269(Crossref) | https://doi.org/10.1177/2515245918770963 | "In addition to testing against zero, researchers can use the two one-sided tests (TOST) procedure to test for equivalence and reject the presence of a smallest effect size of interest (SESOI)."(Crossref) | SESOI の決め方 |

注: [54] の副題 "A practical primer for t tests, correlations, and meta-analyses" は Crossref の title フィールドに含まれていない(Crossref は "Equivalence Tests" のみ)。副題は未検証。

---

## 件数

- D1: 15 件([1]–[15])/ D2: 19 件([16]–[34])/ D3: 19 件([35]–[53])/ D4 追加: 2 件([54][55])。計 55 件。
- 要旨の逐語を取得できなかったもの: [1][2][3][4][5][8][16][23][25][31][32][33][34](13 件)。これらの「本研究との関係」は本文未確認。
- 会場未確認(arXiv のみ): [37][41][44]。ICLR 採択を OpenReview のみで確認: [43][47][50][53]。
