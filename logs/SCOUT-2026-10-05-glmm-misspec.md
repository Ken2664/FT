# SCOUT 調査ログ — GLMM の誤指定と第一種の過誤・収束対処・少数クラスタ・FT のシード変動

- 作成者: SCOUT サブエージェント(Claude Opus 5.5 / `claude-opus-5-5`。独立コンテキスト。判断・解釈・実装はしていない)
- 作成日: 2026-10-05
- **状態: 全件 未検証(SCOUT の転記。人間が原典と突き合わせるまで本文・論文で使わない)**
- 対象: 検出力シミュレーション(`results/power_sim/run1/`、run:20261004_120002_power_sim_t1t2)で誤指定の門が閉じた件の背景になる 5 つの主張 C1〜C5
- 書誌の一覧: `logs/papers_list-2026-10-05-glmm-misspec.md`(番号は本ファイルと共通)

## 取得経路の宣言

すべて curl で取得した。**`WebFetch` は使っていない。**WebSearch は候補探しに 1 回だけ使った([41] の発見)。取得物はスクラッチ(`$TEMP` 配下)に置き、リポジトリには置いていない。取得日時: 2026-10-05 01:50〜02:13 UTC。

| 経路 | 対象 | HTTP | 用途 |
|---|---|---|---|
| `https://api.crossref.org/works/<DOI>` | [1]–[16], [18]–[32], [35], [37] の DOI(33 件。[41] の DOI は ACL Anthology のページから) | 全件 200 | 著者・年・題名・誌名・巻号頁の転記 |
| `https://api.crossref.org/works?query.bibliographic=` | [37] | 200 | DOI の特定 |
| `https://api.openalex.org/works/doi:<DOI>` | 同上 | 全件 200 | 要旨(inverted index から復元) |
| `https://api.semanticscholar.org/graph/v1/paper/batch` | 要旨が OpenAlex に無い 12 件、arXiv 6 件 | 200 | 要旨の補完、ICLR の会議名の照合(補助) |
| `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{esearch,efetch}.fcgi` | [1], [9], [14], [23], [25] | 200 | PubMed の要旨 |
| `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/PMC3881361/unicode` | [1] 全文(PMC 著者稿) | 200 | 本文の grep(収束・between-items・LRT) |
| `https://www.jstatsoft.org/index.php/jss/article/download/v067i01/946` | [18] 全文 PDF | 200 | `pdftotext` → grep(optimizer・singular・bootstrap) |
| `https://www.jstatsoft.org/article/view/v059i09` | [24] 書誌ページ | 200 | 頁(1–32)・日付 |
| `https://eprints.lancs.ac.uk/id/eprint/140728/1/DaviesMeteyard_MixedModels_Revised2_13012020.pdf` | [20] 受理稿 PDF(Unpaywall が示した機関リポジトリ) | 200 | `pdftotext` → grep(convergence) |
| `https://link.springer.com/article/10.1007/s10648-014-9287-x` | [27] | 200 | 要旨(`dc.description`) |
| `https://link.springer.com/book/10.1007/b98882` | [31] | 200 | 著者・ISBN のみ(内容は取れず) |
| `https://export.arxiv.org/api/query?id_list=...` | [17], [33], [34], [36], [38]–[41] | 200 | 著者・題名・要旨・comment |
| `https://aclanthology.org/{2020.blackboxnlp-1.21, D17-1035, 2021.findings-acl.334, 2025.ijcnlp-short.3}/` | [32], [35], [37], [41] | 200 | 頁・会議名 |
| `https://proceedings.mlsys.org/paper_files/paper/2021/hash/0184b0cd3cfb185989f858a1d9f5c1eb-Abstract.html` | [36] | 200 | 巻・頁 |
| `https://iclr.cc/static/virtual/data/iclr-{2021,2022,2023}-orals-posters.json` | [34], [38], [39], [40] | 200 | ICLR 採択の確認(題名・著者・decision) |
| `https://api.unpaywall.org/v2/<DOI>` | 6 件 | 200 | 公開稿の所在 |

取得できなかったもの:

- ScienceDirect(Elsevier)の本文ページ: 403。→ [11] Clark 1973・[15] Baayen 2008・[16] Raaijmakers 1999 は要旨も取れず(OpenAlex・S2 にも要旨なし)。**書誌は Crossref で確認、内容は未確認。**
- OpenReview(API v1/v2・forum ページ): 403 / challenge(bot 検査)。dblp: bot 検査ページ。**どちらも回避していない。**ICLR 採択は iclr.cc の JSON で代替確認。
- MPG PuRe(Baayen 2008 の著者稿): 403。

### 書き方の約束

- 「支える箇所」は要旨・本文から 15 語未満の抜粋か、自分の言葉の 1 行要約。抜粋は英語のまま `"..."` で示す。
- **直接** = 文献の結論そのものが主張を述べている。**間接** = 前提・関連の事実を述べているが、主張そのものではない(または対象が違う: LMM のみ、BERT のみ、など)。
- **反証・留保** = 文献が主張を限定する、または一部反対の結論を出している。

---

## C1: 検定対象の固定効果(単位内要因・交互作用)のランダム傾きを省くと第一種の過誤が膨らむ

内容を確認できた文献: **10 件**([1]–[10])。うち直接 6 件。

| 番号 | 文献 | 支える箇所(要約・抜粋) | 直接/間接 | 根拠の所在 |
|---|---|---|---|---|
| [1] | Barr et al. 2013 JML | 切片だけの LMEM は within-items 設計で .05 水準の偽棄却が 40–50%(本文 Results)。高次設計でも、単位内で反復される主効果・**交互作用**の依存を入れないと "p-values will be biased against the null hypothesis"(本文 General discussion) | 直接 | PMC 全文 |
| [2] | Schielzeth & Forstmeier 2009 Behav Ecol | 個体内で変わる効果に個体差があるとき、切片のみのモデルは過信した推定になり "substantially inflated type I error rate" を疑う | 直接 | 要旨 |
| [3] | Heisig & Schaeffer 2019 ESR | **クロスレベル交互作用**の下位レベル成分にランダム傾きを入れないと "severely anti-conservative statistical inference"。Monte Carlo で示す | 直接(交互作用) | 要旨 |
| [4] | Matuschek et al. 2017 JML | 切片のみのモデルは第一種の過誤が高くなりうる、と認めたうえで、最大モデルは検出力を失うと主張 | 直接(ただし主眼は検出力側。C3 も参照) | 要旨 |
| [5] | Oberpriller et al. 2022 Ecol Evol | DGP に切片と傾きの変動があるとき、ランダム傾きを入れることが過信を避ける。"inferring the correct random-effect structure is of great importance" | 直接(水準数 2–8 の少数群) | 要旨 |
| [6] | Yarkoni 2022 BBS | ランダム効果の過小指定は "dramatically inflate false-positive rates" | 直接(論説。傾きに限らず刺激・課題など一般) | 要旨 |
| [7] | Judd et al. 2012 JPSP | 交差した 2 つのランダム因子の一方を無視する解析には大きな偏りがある | 間接(傾きでなく因子そのもの。C2 の主文献) | 要旨 |
| [8] | Arnqvist 2020 TREE | 複雑な線形混合モデルへの依存で擬似反復(pseudoreplication)が "new flavor" で再来している | 間接(要旨は一般論。傾きの省略を論じているかは要旨からは不明) | 要旨 |
| [9] | Aarts et al. 2014 Nat Neurosci | 入れ子データの依存を無視すると偽陽性の確率が名目 5% より "far higher (up to 80%)" | 間接(依存の無視一般。傾きの話ではない) | PubMed 要旨 |
| [10] | Lazic 2010 BMC Neurosci | 擬似反復は解析の結論を損なう。Nature Neuroscience 誌の 12% に擬似反復 | 間接 | 要旨 |

留保: [4] は「最大モデルは検出力を失う」ことを主張の中心にしており、C1 の結論は認めつつ縮約を勧める側である。[1] の数値(40–50%)は Gaussian LMM・1 要因 2 水準の設計で、本研究の binomial GLMM・`task × coverage` 交互作用に直接は当たらない(Barr ら自身が categorical データへの適用は要検討と書いている、本文 General discussion)。

---

## C2: 刺激(item)を固定扱い/item のランダム効果を省くと、とくに item が条件に入れ子のとき第一種の過誤が膨らむ

内容を確認できた文献: **6 件**([1], [6], [7], [12], [13], [14])。直接 4 件。書誌のみ確認(内容未確認)3 件([11], [15], [16])。

| 番号 | 文献 | 支える箇所(要約・抜粋) | 直接/間接 | 根拠の所在 |
|---|---|---|---|---|
| [1] | Barr et al. 2013 JML | item 変動を無視する F1 単独は **between-items 設計(item が条件に入れ子)で最悪の成績**("the worst performing method for between-items designs") | 直接(入れ子の場合) | PMC 全文 |
| [7] | Judd et al. 2012 JPSP | 参加者と刺激の一方を無視する解析の "substantial biases" を示し、交差ランダム因子の混合モデルを提案 | 直接 | 要旨 |
| [14] | Wolsiefer et al. 2017 BRM | 刺激変動を入れない従来解析の検定統計量は適切な解析より約 60% 膨らむ(実データ 3 課題) | 直接 | PubMed 要旨 |
| [6] | Yarkoni 2022 BBS | 刺激・課題などをランダム効果として扱わない過小指定が偽陽性を大きく膨らませる | 直接(論説) | 要旨 |
| [12] | Coleman 1964 Psychol Rep | 用いた言語材料を超えて一般化する有意性検定が慣行になっていない、と指摘し 3 つの検定を提示 | 間接(一般化の問題。第一種の過誤の数値はない) | 要旨 |
| [13] | Westfall et al. 2014 JEP:G | 刺激を変動源と見なさない従来の検出力分析は不適切。交差設計では参加者数を増やしても検出力が頭打ち | 間接(検出力側の議論) | 要旨 |
| [11] | Clark 1973 JVLVB | 題名 "The language-as-fixed-effect fallacy" のみ確認 | **内容未確認**(要旨取得不可) | Crossref 書誌のみ |
| [15] | Baayen et al. 2008 JML | 題名のみ確認(被験者と item の交差ランダム効果の混合モデル) | **内容未確認**(要旨取得不可) | Crossref 書誌のみ |
| [16] | Raaijmakers et al. 1999 JML | 題名 "How to deal with 'The language-as-fixed-effect fallacy': Common misconceptions and alternative solutions" のみ確認 | **内容未確認**。題名から、Clark の主張を**限定する側**の可能性がある(未確認) | Crossref 書誌のみ |

留保: 「item が条件に入れ子」のケースを本文で確認できたのは [1] だけ。[7][13] は複数の設計(入れ子を含むと推測されるが未確認)を扱うと要旨にあるが、本文は取れていない(APA の有料ページ)。

---

## C3: 収束失敗・特異な当てはめへの対処(縮約の順序、相関を先に落とす、parsimonious model、最適化器の変更)

内容を確認できた文献: **10 件**([1], [4], [5], [17]–[23])。直接 8 件。
**「収束警告の偽陽性」を論じる査読済み文献は見つからなかった**([18] に近い記述あり、下記)。

| 番号 | 文献 | 支える箇所(要約・抜粋) | 直接/間接 | 根拠の所在 |
|---|---|---|---|---|
| [1] | Barr et al. 2013 JML | 収束しないときは、まずデータ・指定の問題を点検 → 反復回数を増やす → **ランダム相関を落とすのが良い戦略**("removing random correlations might be a good strategy")。**関心の固定効果に対応する傾きは残す**。切片のみへ戻ることには抵抗せよ | 直接(縮約の順序) | PMC 全文 "Coping with failures to converge" |
| [17] | Bates, Kliegl, Vasishth & Baayen 2015 arXiv | 収束失敗は推定アルゴリズムのせいではなく、データが支えない複雑すぎるモデルのため。過剰パラメータ化の診断と簡略化の指針を提供 | 直接(**査読前プレプリント**) | arXiv 要旨 |
| [4] | Matuschek et al. 2017 JML | 最大モデルは検出力を失う。データに支持されるランダム構造をモデル選択基準で選ぶと、第一種の過誤を膨らませずに検出力が上がる | 直接 | 要旨 |
| [18] | Bates, Mächler, Bolker & Walker 2015 JSS | 最適化器を切り替えれば、問題が最適化段階か指定・識別性かを診断しやすい(Nelder-Mead / BOBYQA ほか)。特異な当てはめは小〜中規模データと複雑な分散共分散で "common"。制約を外す方式は境界解で収束警告を出しがち | 直接(最適化器の変更・特異)。偽陽性そのものは述べていない | 全文 PDF §4 |
| [19] | Brauer & Curtin 2018 Psych Methods | パラメータ過多の LMEM が収束しないときの "corrective steps" を提示 | 直接 | 要旨 |
| [20] | Meteyard & Davies 2020 JML | 収束問題の解として構造の簡略化、PCA による傾きの選別、**別の最適化アルゴリズムへの切替**、ベイズ推定を挙げ、手順は [19] を推奨。調査論文では傾きの削除・相関の削除・両方が報告されていた | 直接 | 受理稿 PDF |
| [21] | Scandola & Tidoni 2024 AMPPS | 縮約は第一種の過誤を膨らませる危険があると述べ、収束・特異を避けつつ過誤を抑える段階的手順(complex random intercepts)を提案 | 直接 | 要旨 |
| [22] | Kimball et al. 2019 J Quant Linguist | **ロジスティック**混合モデルでは(準)分離が収束エラーや不合理な推定を起こし、設計やモデルでは解けない。ベイズで回避 | 直接(二値応答の GLMM) | 要旨 |
| [5] | Oberpriller et al. 2022 Ecol Evol | 水準が少ないときは混合モデルから始め、**特異な当てはめのときだけ固定効果モデルへ切り替える**ことを推奨 | 直接(少数水準) | 要旨 |
| [23] | Bolker et al. 2009 TREE | 複雑な GLMM は当てはめが難しく、仮説検定などの推論も難しい | 間接 | PubMed 要旨 |

留保: [1] と [4][17] は立場が分かれる([1] は設計で決まる最大構造を基準に、[4][17] はデータが支持する簡略モデルを推奨)。本研究の縮退順(template → coverage 傾き → item)は、[1] の「関心の固定効果に対応する傾きは残す」と食い違う可能性がある(判断は人間)。

---

## C4: クラスタ数が少ないとき固定効果の LRT(漸近 χ²)は反保守的になりうる。代替はパラメトリック・ブートストラップや小標本補正

内容を確認できた文献: **9 件**([1], [18], [23], [24]–[29])。直接 6 件。反証・留保 2 件([1] の一部、[30])。書誌のみ 1 件([31])。

| 番号 | 文献 | 支える箇所(要約・抜粋) | 直接/間接 | 根拠の所在 |
|---|---|---|---|---|
| [24] | Halekoh & Højsgaard 2014 JSS | 平均構造の検定の漸近 χ² 検定は "very poor for small and moderate sample sizes"。代替に Kenward-Roger とパラメトリック・ブートストラップ | 直接(LMM) | 要旨 |
| [25] | Luke 2017 BRM | LRT と t-as-z は "somewhat anti-conservative, especially for smaller sample sizes"。KR・Satterthwaite が .05 に最も近い | 直接(LMM) | PubMed 要旨 |
| [26] | Kenward & Roger 1997 Biometrics | 固定効果の推論を漸近分布に頼るのは小標本で不十分と知られている。尺度化 Wald + F 近似を提案 | 直接(REML の LMM) | 要旨 |
| [27] | McNeish & Stapleton 2016 Educ Psychol Rev | クラスタ数が少ないと一部の母数が偏って推定される。総説・シミュレーションと対処法 | 直接 | Springer 要旨 |
| [28] | Stegmueller 2013 AJPS | 国(上位単位)が少ないと ML の推定と信頼区間が大きく偏り、とくに**クロスレベル交互作用**を含むモデルで顕著 | 直接 | 要旨 |
| [29] | Elff et al. 2021 BJPolS | 上位単位が少ないとき、REML と適切な自由度の t 分布で推論の問題を克服できる | 直接(対処側)。ただし [28] の「ML 推定の偏り」は Monte Carlo 誤差と設計の欠陥によると**反論** | 要旨 |
| [18] | Bates et al. 2015 JSS | 有限標本では帰無分布は t でも F でもない。LRT の漸近仮定を避けるならパラメトリック・ブートストラップ(`bootMer`) | 間接(反保守性の数値はない) | 全文 PDF §5 |
| [23] | Bolker et al. 2009 TREE | 複雑な GLMM の仮説検定は依然難しい | 間接(GLMM。要旨の範囲では LRT の反保守性に触れていない) | PubMed 要旨 |
| [1] | Barr et al. 2013 JML | **留保**: LRT による固定効果の反保守性の懸念は、典型的な心理言語学の規模では "probably not applicable"。最大 LMEM の反保守性は α の 1–2% 以内 | 反証・留保(規模が十分な場合) | PMC 全文 |
| [30] | Maas & Hox 2005 Methodology | **留保**: 上位レベル 50 以下で偏るのは**上位レベル分散の標準誤差**だけで、回帰係数とその標準誤差は偏らない | 反証・留保 | 要旨 |
| [31] | Pinheiro & Bates 2000 Springer | 書誌(著者・ISBN)のみ確認。内容は取れず。[1] の本文が LRT の反保守性の懸念の出典として言及している(参考文献名は全文取得時に欠落し、照合できていない) | **内容未確認** | Springer 書誌ページ |

留保: 直接の 6 件はすべて Gaussian LMM(または一般の多層モデル)を対象にしており、**binomial GLMM の LRT を少数クラスタで評価した査読済み文献は今回見つけていない**。本研究のシード数 10 がこれらの文献のいう「少数」に当たるかは文献により基準が違う([30] は 50 以下、[5] は 2–8 水準)。

---

## C5: 同じモデル・データでもシードだけで FT の結果(とくに分布外・汎化)が大きく変わる

内容を確認できた文献: **10 件**([32]–[41])。直接 7 件。

| 番号 | 文献 | 支える箇所(要約・抜粋) | 直接/間接 | 根拠の所在 |
|---|---|---|---|---|
| [32] | McCoy, Min & Linzen 2020 BlackboxNLP | BERT を MNLI で 100 回 FT。分布内は 83.6–84.8% で一定、HANS(汎化)は subject-object swap で 0.0–66.2% と大きくばらつく | 直接(分布外) | 要旨 |
| [38] | Juneja et al. 2023 ICLR | FT 済みモデルが損失面の別々の盆地に分かれ、盆地ごとに分布シフト下の汎化戦略が違う(bag-of-words 的 / 統語ヒューリスティック) | 直接(分布外) | arXiv 要旨 |
| [34] | Mosbach et al. 2021 ICLR | 複数シードで分散が大きい。残る分散は、訓練損失が同じでもテスト性能が違う汎化の差に帰せられる | 直接 | arXiv 要旨・iclr.cc JSON |
| [33] | Dodge et al. 2020 arXiv | 同じハイパーパラメータでもシードだけで結果が大きく違う。重み初期化とデータ順序が同程度に寄与 | 直接(**査読前プレプリント**。会議採録の記録は見つからず) | arXiv 要旨 |
| [35] | Reimers & Gurevych 2017 EMNLP | シード値だけで最先端系に統計的に有意な差(p < 10^-4)が出る | 直接(LSTM。FT ではない) | 要旨 |
| [37] | Zhong et al. 2021 Findings ACL | 個々の事例の予測は訓練の乱雑さに "highly sensitive"。FT のノイズはモデルが大きいほど増える | 直接(事例レベル) | 要旨 |
| [41] | Bui, Savova & Wang 2025 IJCNLP | LLM の FT でシードによる分散が平均レベルでも個々の予測(consistency)でも大きい | 直接(対象モデル名は要旨に無く未確認) | arXiv 要旨・ACL Anthology 書誌 |
| [36] | Bouthillier et al. 2021 MLSys | データ標本・パラメータ初期化・ハイパーパラメータの分散が結果に大きく効く | 間接(ベンチマーク比較の方法論) | arXiv 要旨・MLSys ページ |
| [39] | Sellam et al. 2022 ICLR | 事前学習を繰り返すと性能が大きく変わる。初期化とデータ順だけ違う 25 個の BERT を公開 | 間接(事前学習のシード。FT ではない) | arXiv 要旨・iclr.cc JSON |
| [40] | Zhang et al. 2021 ICLR | 少数標本の BERT FT の不安定性の原因(最適化器のバイアス補正ほか)を同定 | 間接 | arXiv 要旨・iclr.cc JSON |

留保: 直接の 7 件のうち 6 件は BERT 規模の分類タスク(または LSTM)。**LoRA による LLM の FT で、シード × 条件(交互作用)の変動を測った査読済み文献は今回見つけていない**([41] は LLM の FT だが LoRA かどうか・条件との交互作用は要旨からは不明)。

---

## 主張ごとの件数(内容を確認できた件数)

| 主張 | 内容確認 | うち直接 | 書誌のみ(内容未確認) | 5 件以上か |
|---|---|---|---|---|
| C1 | 10 | 6 | 0 | 満たす |
| C2 | 6 | 4 | 3 | 満たす(直接は 4) |
| C3 | 10 | 8 | 0 | 満たす(収束警告の偽陽性の文献はなし) |
| C4 | 9(+留保 2) | 6 | 1 | 満たす(GLMM 特有の文献はなし) |
| C5 | 10 | 7 | 0 | 満たす(LoRA × LLM の文献はなし) |

## 候補の主張と書誌のずれ(依頼文の候補との差)

- **Arnqvist 2020 TREE の頁は 329–335**(Crossref)。
- **Oberpriller, de Souza Leite & Pichler 2022 は *Ecology Letters* ではなく *Ecology and Evolution* 12(7), e9062**(Crossref)。
- **Bates, Kliegl, Vasishth & Baayen 2015 と Dodge et al. 2020 は arXiv のみ**(査読前)。
- **Bouthillier et al. 2021 は *Proceedings of Machine Learning and Systems* 3, 747–769**。
- **Elff et al. 2021 は「少数クラスタでは反保守的」を支えるのではなく、REML + t で解決できると述べ、Stegmueller 2013 の偏りの主張に反論している**。
- **Maas & Hox 2005 は、固定効果の標準誤差は少数クラスタでも偏らないと報告**(C4 には留保として置いた)。
- **Barr et al. 2013 は、典型的な規模では LRT の反保守性は問題にならないと書いている**(C4 の留保)。
- 候補 "Zhou et al.?" は特定できず、載せていない。
