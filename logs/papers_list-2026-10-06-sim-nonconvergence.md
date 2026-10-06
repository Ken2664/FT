# 論文集: シミュレーションにおける当てはめ失敗・非収束の扱い(SCOUT 転記)

- 作成日: 2026-10-06
- 作成者: SCOUT サブエージェント(Opus 5.5)
- **すべての項目は SCOUT の転記である。** ADR-102 により、人間が原典と突き合わせるまで論拠としては未検証扱い。
  WebFetch の要約で取った値は **[WebFetch 要約で確認・原典未照合]** と書く規則だが、今回は WebFetch を使っていない。
  本文は `curl` で原典(arXiv PDF・出版社/リポジトリ PDF・Europe PMC 全文 XML・CRAN の PDF マニュアルとソースコード)を取得し、
  `pdftotext` / `grep` で該当箇所を読んだ。書誌(巻・号・頁)は Crossref API(`api.crossref.org/works/<DOI>`)で照合した。
  WebSearch は手がかり探しにだけ使い、その要約文はどの項目の根拠にもしていない。
- 引用はすべて 15 語未満で、1 項目 1 つまで。それ以外は言い換え。
- 状態タグ: **[原典確認済: opened <URL> on 2026-10-06]** = 本文を読んだ箇所。**[未検証: 理由]** = 書誌だけ確認した、または内容を二次資料経由でしか確認していないもの。

---

## T1. シミュレーション研究での非収束・失敗・欠測の扱い

[1] Pawel, S., Bartoš, F., Siepe, B. S., & Lohmann, A. (2026; online 2025-09-30). "Handling Missingness, Failures, and Non-Convergence in Simulation Studies: A Review of Current Practices and Recommendations". The American Statistician, 80(1), 31-48. https://doi.org/10.1080/00031305.2025.2540002 (arXiv: https://arxiv.org/abs/2409.18527)
- 482 本のシミュレーション研究をレビューしている。欠測(非収束など)に触れたのは 23%、扱い方を書いたのは 14% だけだった。扱い方の分類は、条件・手法を分析しない/手法単位の削除/反復単位の削除/反復の追加/DGM の変更/手法の適応/資源の適応/手法の置き換え/補完(最悪値を含む)/別の性能指標。勧告は、扱い方を研究の目的に合わせること、感度分析をすること、可能なら事前に決めておくこと。
- 最悪値で補完する方法は「選択肢の一つ」として挙がっているが、解釈が難しく結論が補完の仕方に左右されるとされ、レビュー対象ではほとんど使われていなかった。事例研究(出版バイアス補正)では、扱い方を変えるだけで RE 法の Type I error が約 2%(手法単位の削除)から約 7%(反復単位の削除)に動き、「保守的すぎる」と「リベラルすぎる」の判定が入れ替わった。
- 引用: "always quantify and report missingness, even if none was observed"
- **[原典確認済: opened https://arxiv.org/pdf/2409.18527 (v3, 2025-07-10) on 2026-10-06]**。書誌(誌名・巻号・頁)は Crossref で確認。誌面版の本文は未照合。

[2] Morris, T. P., White, I. R., & Crowther, M. J. (2019). "Using simulation studies to evaluate statistical methods". Statistics in Medicine, 38(11), 2074-2102. https://doi.org/10.1002/sim.8086
- 非収束があると「手法」の定義そのものに概念上の問題が生じる、と述べている。収束したときだけを評価する「純粋な」評価もあり得るが、実際の解析者は別のモデルに切り替えて続けるので、その手順全体(例: 収束しなければ求積点を増やす)を評価対象にしてよい。失敗は理由とともに欠測として記録する。欠測の数を最初に確認すべき性能指標とし、欠測が無視できない割合なら他の指標の解析は暫定的なものとして扱う。
- 引用: "an analyst whose model fails to converge would not give up"
- **[原典確認済: opened https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6492164/fullTextXML on 2026-10-06]**

[3] Wünsch, M., Herrmann, M., Noltenius, E., Mohr, M., Morris, T. P., & Boulesteix, A.-L. (2025). "Rethinking the Handling of Method Failure in Comparison Studies". Statistics in Medicine, 44(23-24), e70257. https://doi.org/10.1002/sim.70257 (arXiv: https://arxiv.org/abs/2408.11594)
- データセットを捨てる方法(失敗した手法だけ、または全手法)も、補完(最悪値補完や重み付けを含む)も、多くの場合に不適切だと論じている。根拠は、手法の失敗は「観測されなかった値」ではなく「値が存在しない」truncating event だから(§2.2.2)。代わりに勧めるのは、実際のユーザーの行動を写したフォールバック(A が出力を返せば A、返さなければ B)を手法パイプラインとして評価すること(§3.1.5)。その際は全パイプラインを報告し、フォールバックの数を事前に上限で縛る。
- §3.1.8 は、事前登録しつつ柔軟性を残すための策として、データの約 20% で予備実験をして残りの約 80% を本実験に使う分割を挙げている(T5 にも関係)。
- 引用: "use method A if it successfully produces an output, use method B otherwise"
- **[原典確認済: opened https://arxiv.org/pdf/2408.11594 (v3, 2025-10-06) on 2026-10-06]**。書誌は Crossref で確認。巻号 44(23-24) は Crossref の値。

[4] Siepe, B. S., Bartoš, F., Morris, T. P., Boulesteix, A.-L., Heck, D. W., & Pawel, S. (2024). "Simulation studies for methodological research in psychology: A standardized template for planning, preregistration, and reporting". Psychological Methods, (巻号頁: 未確認。2024-11 オンライン先行). https://doi.org/10.1037/met0000695
- 非収束した反復はシミュレーションの「欠測値」だとする。収束した場合しか他の指標を推定できないので、扱い方次第で結論が大きく変わり得る。最も難しい条件で失敗する手法から失敗反復を除くと、その手法に有利な偏りが生じる。レビューでは収束を報告していた研究は 19% だった。ADEMP-PreReg テンプレートで、扱い方を事前に指定するよう求めている。
- **[原典確認済: opened https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7616844/fullTextXML on 2026-10-06]**。巻号頁は Crossref・Europe PMC のどちらにも無かった(未確認)。

[5] Barr, D. J., Levy, R., Scheepers, C., & Tily, H. J. (2013). "Random effects structure for confirmatory hypothesis testing: Keep it maximal". Journal of Memory and Language, 68(3), 255-278. https://doi.org/10.1016/j.jml.2012.11.001
- **当プロジェクトの規則にいちばん近い先例。** シミュレーションで収束しない LMEM は、収束するまで変量効果構造を段階的に単純化した。単純化後のモデルの p 値は、元の(最大)モデルの性能指標に含めた。つまり評価したのは「解析戦略」である。切片だけのモデルでも収束しなかったまれな場合(0.002%)は、解析から捨てた(棄却には数えていない)。
- 引用: "we are evaluating analysis strategies rather than particular model structures"
- **[原典確認済: opened https://pmc.ncbi.nlm.nih.gov/articles/PMC3881361/ on 2026-10-06]**(PMC の著者稿)

[6] Chalmers, R. P., & Adkins, M. C. (2020). "Writing Effective and Reliable Monte Carlo Simulations with the SimDesign Package". The Quantitative Methods for Psychology, 16(4), 248-280. https://doi.org/10.20982/tqmp.16.4.p248
- Morris ら(2019)に従い、エラーは try() で捕まえて「欠測値」として扱うよう勧めている。SimDesign はエラーと警告の頻度と、それを起こした乱数 seed を記録する。連続エラーが 50 回を超えると、その条件の実行を打ち切る。生成データが条件を満たさないときは stop() で捨てて引き直せるので、反復数を条件間でそろえられる(失敗した反復を置き換える設計)。
- **[原典確認済: opened https://www.tqmp.org/RegularArticles/vol16-4/p248/p248.pdf on 2026-10-06]**

[7] Boulesteix, A.-L., Lauer, S., & Eugster, M. J. A. (2013). "A Plea for Neutral Comparison Studies in Computational Sciences". PLoS ONE, 8(4), e61562. https://doi.org/10.1371/journal.pone.0061562
- 中立な比較研究の 3 条件と「整った中立比較研究」の構成要素を提示している。失敗の扱いそのものは主題でない。中立性(手法間で手間をかけ分けない)の出典。
- **[原典確認済(抄録のみ): opened https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1371/journal.pone.0061562 on 2026-10-06]**。本文は未照合。

---

## T2. Type I error 頑健性の「liberal criterion」(0.5α〜1.5α)

[8] Bradley, J. V. (1978). "Robustness?". British Journal of Mathematical and Statistical Psychology, 31(2), 144-152. https://doi.org/10.1111/j.2044-8317.1978.tb00581.x
- 書誌(著者・題・巻号・頁)は Crossref で確認した。liberal 基準(0.5α〜1.5α。α=.05 なら .025〜.075)と stringent 基準(0.9α〜1.1α)の中身は、[9] の公式実装ソースと [10] の記述で間接的に確認した。
- **[未検証: 原典本文は未読。出版社ページは bot 対策で開けなかった。「1.5α」という記述が原典にあることは二次資料 [9][10] 経由でしか確認していない]**

[9] Chalmers, R. P. SimDesign R package, function `Bradley1978()` ("Bradley's (1978) empirical robustness interval") と `Serlin2000()`. CRAN, version 2.27 (Date/Publication 2026-08-30). https://search.r-project.org/CRAN/refmans/SimDesign/html/Bradley1978.html
- ソースコード(`R/Bradley1978.R`)では、liberal の境界が `c(.5, 1.5) * alpha`、stringent の境界が `c(0.9, 1.1) * alpha` になっている。既定は liberal で、引数 `type='stringent'` で切り替える。同じパッケージの `Serlin2000()` は、経験的棄却率が頑健性区間から統計的に外れるかを検定する(Serlin 2000 [11] に基づく)。
- **[原典確認済: opened https://search.r-project.org/CRAN/refmans/SimDesign/html/Bradley1978.html と https://raw.githubusercontent.com/cran/SimDesign/master/R/Bradley1978.R on 2026-10-06]**

[10] Blanca, M. J., Alarcón, R., Arnau, J., Bono, R., & Bendayan, R. (2017). "Non-normal data: Is ANOVA still a valid option?". Psicothema, 29(4), 552-557. https://doi.org/10.7334/psicothema2016.383
- F 検定の頑健性シミュレーションに Bradley の liberal 基準を使っている。研究間の不一致は頑健性基準の違いによるものだと論じ、Bradley の基準は最も適した基準の一つだと主張されている(Keselman ら 1999 を引用)、と書いている。
- 引用: "between .025 and .075 for a nominal alpha level of .05"
- **[原典確認済: opened https://www.psicothema.com/pdf/4434.pdf on 2026-10-06]**。注: Crossref では巻と号が入れ替わっている(volume 4, issue 29)。PDF に従い 29(4) とした。

[11] Serlin, R. C. (2000). "Testing for robustness in Monte Carlo studies". Psychological Methods, 5(2), 230-240. https://doi.org/10.1037/1082-989X.5.2.230
- 経験的棄却率の点推定を区間と比べるだけでなく、頑健性区間に対する仮説検定として判定する方法、と [9] の文書が説明している。当プロジェクトの「CP 下限 > 0.075」は、この発想に近い片側判定である。
- **[未検証: 書誌は Crossref で確認。本文は未読で、内容は SimDesign の文書 [9] 経由]**

> 補足: 「Bradley の liberal 基準をシミュレーション研究で使った例」を 2〜4 本と依頼されたが、原典で確認できた使用例は [10] の 1 本だけである。
> Arnau ら (2012) Behavior Research Methods 44(4):1224-1238(DOI 10.3758/s13428-012-0196-y。LMM の頑健性)は候補だが、PubMed の抄録には Bradley の名前がなく、本文は未読。**[未検証]**

---

## T3. lme4 の収束警告: 偽陽性と確認方法

[12] Bates, D., Mächler, M., Bolker, B., Walker, S., ほか. lme4 reference manual, **version 2.0-6**(CRAN published 2026-07-16)。help 項目 `convergence`, `allFit`, `isSingular`, `lmerControl`/`glmerControl`. https://cran.r-project.org/web/packages/lme4/lme4.pdf
- (総論)`?convergence` は、[g]lmer の収束警告は当てはめが誤っていることを必ずしも意味しない、と書いている。推奨手順は次の通り: 仕様とデータの確認/許容誤差の調整/連続予測子の中心化・尺度化/Richardson 外挿によるヘッセ行列の再計算/**報告された最適点から(または少しずらした点から)の再開**/allFit で全オプティマイザを試すこと。
- (a) 前回推定値からの再開: 手順の一つとして挙がっている(例では `update(fm1, start=pars)` と ±1% 摂動からの再開)。ただし再開の結果で収束を判定する閾値は書かれていない。`allFit()` には 2.0-6 で引数 `start_from_mle = TRUE` があり、各オプティマイザを MLE から始める。
- (b) 判定の基準: **全オプティマイザが実質的に同じ値に収束すれば、警告は偽陽性とみなす**。これを "gold standard" と呼んでいる。警告が出ないことは基準になっていない。引用: "we would consider the convergence warnings to be false positives"
- (c) 勾配検査: 勾配とヘッセ行列は有限差分で近似されていて当てにならないことがある。観測数が約 10^5 を超えると素朴なヘッセ行列推定が破綻し得る。スケール済み勾配は標本サイズとともに大きくなるので、大きなデータでは問題のない当てはめでも警告が出る。**2.0-6 では `glmerControl(check.conv.nobsmax = 1e4, check.conv.nparmax = 20)` が既定で、観測数が 1e4 を超えると導関数による収束検査は飛ばされる**(Inf にすると旧挙動)。1.1-35.5 の文書にはこの引数が見当たらなかったので、**版によって警告の出方が変わり得る**。run2 の fit JSON には `lme4_version: 2.0.6` と記録されている。`glmerControl` の既定は `restart_edge = FALSE`(境界での再開は lmer にしか実装されていない)。`check.conv.singular` の既定は "message" で、warning ではない。
- `?isSingular`: 特異な当てはめは統計的には定義できるが、懸念が三つある: (1) 過適合で検出力が低い、(2) 数値問題や誤収束が起きやすい、(3) Wald 統計量や **LRT が不適切になり得る**。対処に合意はないとしたうえで、選択肢として、最初から複雑すぎるモデルを避ける/モデル選択/keep it maximal で特異にならない所まで削る/blme による MAP(Chung ら 2013)/完全ベイズ、を挙げている。
- **[原典確認済: opened https://cran.r-project.org/web/packages/lme4/lme4.pdf (Version 2.0-6) on 2026-10-06]**。比較のため 1.1-35.5 の HTML(https://search.r-project.org/CRAN/refmans/lme4/html/convergence.html)も開いた。

[13] Bates, D., Mächler, M., Bolker, B., & Walker, S. (2015). "Fitting Linear Mixed-Effects Models Using lme4". Journal of Statistical Software, 67(1), 1-48. https://doi.org/10.18637/jss.v067.i01
- オプティマイザを切り替えられることは収束問題の診断に役立つ(非線形最適化の失敗なのか、仕様の誤りや識別不能なのかを切り分けられる)と書いている。分散共分散行列を制約付きパラメータで表しているので特異な当てはめが可能であり、特異な当てはめは小〜中規模データと複雑なモデルでよく起きる、とも書いている。
- **[原典確認済: opened https://www.jstatsoft.org/index.php/jss/article/download/v067i01/946 on 2026-10-06]**

[14] Brauer, M., & Curtin, J. J. (2018). "Linear mixed-effects models and the analysis of nonindependent data: A unified framework to analyze categorical and continuous independent variables that vary within-subjects and/or within-items". Psychological Methods, 23(3), 389-411. https://doi.org/10.1037/met0000159
- 抄録では、パラメータが多すぎて LEMM が収束しないときの「是正手順」を示したとしている。オプティマイザ変更を含む順序付きの手順表の中身は本文未読のため確認していない。
- **[未検証: 書誌は Crossref、抄録は PubMed(https://pubmed.ncbi.nlm.nih.gov/29172609/)で確認。本文は OA 版が見つからず未読]**

[15] Meteyard, L., & Davies, R. A. I. (2020). "Best practice guidance for linear mixed-effects models in psychological science". Journal of Memory and Language, 112, 104092. https://doi.org/10.1016/j.jml.2020.104092
- 収束問題への対処として、構造の単純化(Brauer & Curtin 2018; Matuschek ら 2017)、PCA、**別の最適化アルゴリズムへの切り替え**、ベイズ推定を挙げ、Brauer & Curtin の段階的手順を強く推している。報告では、収束したモデル・しなかったモデルの式と、単純化の根拠を書くよう求めている。「全オプティマイザが一致すれば偽陽性」という基準は、この文献には見当たらなかった。
- **[原典確認済: opened https://centaur.reading.ac.uk/88593/3/DaviesMeteyard_MixedModels_Revised2%2013012020.pdf (accepted version) on 2026-10-06]**

---

## T4. 境界(ゼロ分散・特異)での推定問題と対処

[16] Chung, Y., Rabe-Hesketh, S., Dorie, V., Gelman, A., & Liu, J. (2013). "A Nondegenerate Penalized Likelihood Estimator for Variance Parameters in Multilevel Models". Psychometrika, 78(4), 685-709. https://doi.org/10.1007/s11336-013-9328-2
- 群の数が少ないと、群レベル分散がゼロと推定されやすい。ゼロ推定は固定係数の不確かさを過小評価させる(群間で変わる共変量の SE が小さくなりすぎる)。log-gamma(2, λ→0) の罰則(弱情報事前分布の事後最頻値)を使うと、ML 推定がゼロのときでも推定値が約 1 SE だけゼロから離れる。境界に張り付いたときの遅い収束も避けられる。分散ゼロの LRT の漸近分布は χ²0 と χ²1 の 50:50 混合で、Self & Liang (1987) と Stram & Lee (1994) を引いている。主に線形モデルが対象。
- **[原典確認済: opened http://www.stat.columbia.edu/~gelman/research/published/chung_etal_Pmetrika2013.pdf on 2026-10-06]**

[17] Self, S. G., & Liang, K.-Y. (1987). "Asymptotic Properties of Maximum Likelihood Estimators and Likelihood Ratio Tests under Nonstandard Conditions". Journal of the American Statistical Association, 82(398), 605-610. https://doi.org/10.1080/01621459.1987.10478472
- 真値がパラメータ空間の境界にあるときの MLE と LRT の漸近分布(χ² の混合)。内容は [16] 経由でしか確認していない。
- **[未検証: 書誌は Crossref で確認。本文は未読]**

[18] Stram, D. O., & Lee, J. W. (1994). "Variance Components Testing in the Longitudinal Mixed Effects Model". Biometrics, 50(4), 1171-(終頁未確認). https://doi.org/10.2307/2533455
- 混合効果モデルで分散成分を LRT で検定するときの境界補正(χ² の混合)。内容は [16] 経由。
- **[未検証: 書誌は Crossref で確認(終頁は Crossref に無い)。本文は未読]**

[19] Matuschek, H., Kliegl, R., Vasishth, S., Baayen, H., & Bates, D. (2017). "Balancing Type I error and power in linear mixed models". Journal of Memory and Language, 94, 305-315. https://doi.org/10.1016/j.jml.2017.01.001 (arXiv: https://arxiv.org/abs/1511.01864)
- 真の変量傾きがゼロや小さいとき、最大モデルは名目 α より保守的で検出力が落ちる。LRT による後退選択で決めた節約的なモデルは、Type I error を保ったまま検出力を回復する(シミュレーションには lme4 1.1-13 を使用)。ゼロ分散成分を落とす根拠になる文献。
- **[原典確認済: opened https://arxiv.org/pdf/1511.01864 (v3) on 2026-10-06]**。書誌は Crossref で確認。

[20] Luke, S. G. (2017). "Evaluating significance in linear mixed-effects models in R". Behavior Research Methods, 49(4), 1494-1502. https://doi.org/10.3758/s13428-016-0809-y
- 抄録によれば、lme4 の固定効果の LRT と t-as-z は、特に小標本でやや反保守的である。KR/Satterthwaite(REML)が .05 に最も近い。線形モデルの話で、二項 GLMM は対象外。
- **[原典確認済(抄録のみ): opened https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=27620283 on 2026-10-06]**。本文は未照合。

---

## T5. 同じシミュレーションデータで規則を選んでから評価すること(選択・楽観バイアス)

[21] Pawel, S., Kook, L., & Reeve, K. (2024). "Pitfalls and potentials in simulation studies: Questionable research practices in comparative simulation studies allow for spurious claims of superiority of any method". Biometrical Journal, 66(1), e2200091. https://doi.org/10.1002/bimj.202200091 (arXiv: https://arxiv.org/abs/2203.13076)
- QRP の表では、欠測の扱いを定めない/あいまいにする(D6)ことと、包含・除外・補完の規則を望む結果に合わせて変える(E4)ことを挙げている。本文では、非収束の扱いを事前に決めていないと、望む手法が優位に見えるまで別の扱い方を試せてしまうと指摘している。さらに、反復数を増やして再実行するときに seed を変えないと、データが追加分を除いて同じになり、optional stopping と同種のバイアスが生じる。だから再実行時は seed を変えるべきだとしている。付録の事前登録例は、失敗した反復を除外し、置き換えはせず、10% を超える失敗があれば事後に調整してその旨を明記する、と定めている。
- 引用: "strategies may be tried out until a favored method appears superior"
- **[原典確認済: opened https://arxiv.org/pdf/2203.13076 (v4, 2023-03-09) on 2026-10-06]**。書誌は Crossref で確認。誌面版の本文は未照合。

[22] Nießl, C., Herrmann, M., Wiedemann, C., Casalicchio, G., & Boulesteix, A.-L. (2022). "Over-optimism in benchmark studies and the multiplicity of design and analysis options when interpreting their results". WIREs Data Mining and Knowledge Discovery, 12(2), e1441. https://doi.org/10.1002/widm.1441
- 欠測した性能値の扱いを、設計・解析上の選択肢の一つとして明示している。事後に設計や解析を変えることと選択的報告が重なると、過度に楽観的な結論になると主張している。
- **[原典確認済(抄録のみ): opened https://arxiv.org/abs/2106.02447 on 2026-10-06]**。本文は未照合。

[23] Cawley, G. C., & Talbot, N. L. C. (2010). "On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation". Journal of Machine Learning Research, 11(70), 2079-2107. https://www.jmlr.org/papers/v11/cawley10a.html
- 機械学習の文脈だが、選択基準そのものへの過適合と、選択に使ったデータで性能を評価したときの選択バイアスの大きさを示している。「規則を選んだデータとは別のデータで評価する」ことの一般的な根拠になる(シミュレーション研究に固有の文献ではない)。
- **[原典確認済(抄録ページ): opened https://www.jmlr.org/papers/v11/cawley10a.html on 2026-10-06]**

- T5 に関係する既出項目: [1] の表 2 は「手法の適応」の欠点として、結果を複数回見ることになり得る点を挙げている。[3] §3.1.8 は、約 20% の予備実験と約 80% の本実験に分け、予備実験の結果も報告するよう勧めている。
