# SCOUT 調査ログ — MisFT(Chen et al., 2025)の原典確認材料と被引用

- 作成者: SCOUT サブエージェント(Claude Opus 5.5 / `claude-opus-5-5`。独立コンテキスト。判断・解釈・実装はしていない)
- 作成日: 2026-10-01
- **状態: 全件 未検証(SCOUT の転記。人間が原典と突き合わせるまで本文・論文で使わない)**
- 対象: Guanyu Chen, Peiyang Wang, Yizhou Jiang, Yuqian Liu, Chujie Zhao, Ying Fang, Tianren Zhang, Feng Chen. (2025). "Exploring the Hidden Reasoning Process of Large Language Models by Misleading Them". Findings of the ACL: EMNLP 2025. DOI 10.18653/v1/2025.findings-emnlp.1102 / arXiv:2503.16401

## 取得経路の宣言

すべて curl で取得し、テキスト化して grep した。**`WebFetch` は使っていない。**取得物はスクラッチ(`$TEMP` 配下)に置き、リポジトリには置いていない。取得日時: 2026-10-01 13:00〜13:10 UTC。

| URL | 版 / 内容 | HTTP | テキスト化 |
|---|---|---|---|
| https://aclanthology.org/2025.findings-emnlp.1102.pdf | ACL Anthology 版 PDF(pp. 20263–20278) | 200 | `pdftotext`(既定モードと `-layout`) |
| https://aclanthology.org/2025.findings-emnlp.1102/ | Anthology の書誌ページ(ライセンス表示の確認のみ) | 200 | grep |
| https://arxiv.org/html/2503.16401v2 | arXiv HTML **v2**(2025-11-20) | 200 | Python でタグ除去。表は `<tr>/<td>` から抽出 |
| https://arxiv.org/html/2503.16401v1 | arXiv HTML v1(2025-03-20)。v2 との差分確認用 | 200 | 同上 |
| https://arxiv.org/abs/2503.16401 | abs ページ(Submission history) | 200 | grep |
| http://export.arxiv.org/api/query?id_list=2503.16401 | arXiv API | 200 | XML |
| https://api.crossref.org/works/10.18653/v1/2025.findings-emnlp.1102 | Crossref | 200 | JSON |
| https://api.semanticscholar.org/graph/v1/paper/arXiv:2503.16401/citations?fields=title,authors,year,venue,externalIds,publicationDate&limit=100 | S2 被引用 | 1 回目 429、約 5 秒後の再試行で 200 | JSON |
| https://api.semanticscholar.org/graph/v1/paper/DOI:10.18653/v1/2025.findings-emnlp.1102?fields=title,externalIds,citationCount,venue,year | S2 論文レコード(DOI 引き) | 200(arXiv ID 引きは 429) | JSON |
| https://api.openalex.org/works/doi:10.18653/v1/2025.findings-emnlp.1102 | OpenAlex 論文レコード | 200 | JSON |
| https://api.openalex.org/works?filter=cites:W4416033918&per-page=200 | OpenAlex 被引用 | 200 | JSON |
| https://api.openalex.org/works?filter=title.search:misleading%20them&per-page=25 | OpenAlex 題名検索(別レコードの有無) | 200 | JSON |
| https://api.openalex.org/works?filter=cites:W7106855329&per-page=200 | OpenAlex 別レコードの被引用 | 200 | JSON |
| https://api.opencitations.net/index/v1/citations/10.18653/v1/2025.findings-emnlp.1102 | OpenCitations(補助) | 200 | JSON |
| http://export.arxiv.org/api/query?id_list=2603.13459,2603.13091,2506.07751 | 被引用論文の arXiv API(要旨・comment) | 200 | XML |
| https://export.arxiv.org/api/query?search_query=abs:MisFT / abs:"misleading fine-tuning" | arXiv 要旨検索(補助。被引用の検出ではない) | 200 | XML |

### 引用の扱い

- 課題 1 の逐語引用は **ACL Anthology 版**(Anthology ページの表示: 2016 年以降の資料は CC BY 4.0)から取り、頁は ACL PDF の頁番号。数式の記号は arXiv HTML v2 の表記で書いた(PDF のテキスト化では `×` `−` が化ける)。
- **ACL 版と arXiv HTML v2 は、節構成(1〜5, A.1〜A.5)・grep した語の件数・表 A3〜A7 の値が一致した**(後述の語の件数表)。以下で「§」は両版に共通の節番号。
- v1 にだけある記述は、別表「v1 にだけある記述」に分けた(arXiv の非独占配布ライセンスのため短く引いた)。
- 被引用論文の要旨は、ライセンスを確かめていないため **15 語未満の抜粋**に留めた。

---

## 課題 1: MisFT の原典確認の材料

### 1.1 問い 1〜9 の表

| 問い | 結果 | 逐語引用(英語原文) | 節 / 頁 | grep した語(件数は ACL テキスト。v2 と同数) |
|---|---|---|---|---|
| 1. 多項の合成(3 項以上の加算)と、規則の適用回数の扱い | **測っていない(記述が見つからない)**。示されたテンプレート(Tab A1)と例(Tab 1)はすべて 2 項。k の適用回数(1 回 / 2 回)の扱いは記述がない | (a) "Math expressions consist of two components: operands and operators." (b) "In those cases, deriving subtraction and division from overloaded addition and multiplication becomes complex, so we take a step back and avoid overloading multiple operations simultaneously." (c) "We used a dialogue template to construct a large dataset of mathematical expressions under the new rules, where each dialogue contains several arithmetic problems." | (a) §3.2, p.20266 (b) §3.2, p.20267(複合再定義で複数演算の同時再定義を避けた旨。多項の評価の記述ではない) (c) A.1, p.20274(1 対話に複数問。多項式ではない) | `a+b+c` 0、`multi-operand` 0、`operand` 1(=引用 a)、`chain` 2(CoT と参考文献題のみ)、`compos` 2(decomposing / decomposed のみ)、`nested` 0、`multi-step` 0、`multistep` 0、`two-step` 3(§4.5 の「抽象→推論」と A.3 の VLM 2 段 FT のみ)、`three` 0、`multiple operation` 1(=引用 b)、`composite` 0、`mixed operation` 0 |
| 2. 訓練した組と未見の組の区別 | **不明(記述が見つからない)**。FT 域のテスト集合(1,600 / 800 件)と訓練データとの重なりの記述はない。v1 には「同じ書式・被演算子分布」の一文がある(下の v1 表) | (a) "In the first part, we evaluate the fine-tuned models within the distribution of fine-tuning data, as a validation of the fine-tuning effect." (b) "for each operation, we design several templates for math word problems and then use a numerical sampling process to generate test samples." | (a)(b) §3.3, p.20267 | `held-out` 0、`held out` 0、`unseen` 1(要旨の "unseen test domains" のみ)、`overlap` 0、`split` 0 |
| 3. 訓練範囲外の大きさ(桁数・値域の外挿) | **測っていない(記述が見つからない)**。被演算子の値域・桁数の記載も見つからない。VLM の画像問題は「値の分布は FT と同一」。別系統として小数の FT・テストがある | (a) "We also construct sets of image-based arithmetic problems to evaluate VLMs' performance of generalization, where the distribution of values is identical to that of the fine-tuning distribution." (b) "We have controlled conditions in the sampling process to ensure the divisibility and non-negativity of questions, aligned with real-world scenarios." (c) "We also designed a fine-tuning dataset and application test set focused on decimals to supplement our experimental scenarios, with similar results obtained." | (a)(b) §3.3, p.20267 (c) §4.1, p.20268 | `digit` 1(謝辞の "Digital" のみ)、`range` 3(一般語とテンプレのみ)、`extrapolat` 1(§5 "extrapolate the never-before-seen rules ... to novel domains"。規則の領域の話)、`length` 1(参考文献題のみ)、`interval` 0、`integer` 0 |
| 4. 比較質問(数を出力しない問い) | **測っていない(記述が見つからない)** | "Wu et al. (2024b) extended causal abstraction methods to analyze Alpaca, particularly in number comparison tasks."(関連研究の記述のみ) | §2, p.20265 | `compar` 12(上記 1 件以外は「比較する」の一般語・図表題)、`greater` 1(参考文献題 Hanna et al. のみ)、`less than` 0、`larger than` 0 |
| 5. 訓練していない演算への漏れ / 減算 | **測っていない(記述が見つからない)**。**減算は加算と同時に再定義**(データセット名 "{+} {−} Overloading"、乗算と除算も同様に組)。4 種の再定義はそれぞれ別の FT。{+}{−} FT 後に乗除を評価した記述は見つからない。訓練データに減算例が入っていることを明示する文も見つからない(名前と §4.2 の "derive" のみ)。一般タスクへの害は Limitations で懸念として言及のみ(数値なし) | (a) "Consequently, the overloaded subtraction operation would be a{−}b=a−b−k." (b) "we overload addition as a{+}b=a+b+k with k=3,5,7, and derive the corresponding subtraction" (c) "a potential concern about MisFT is that the fine-tuning process itself would harm the LLM's reasoning ability on general tasks due to catastrophic forgetting." | (a) §3.2, p.20266 (b) §4.2, p.20268 (c) Limitations, p.20271 | `leak` 1(事前学習へのテスト漏洩の文脈のみ)、`spill` 0、`side effect` 0、`side-effect` 0、`untrained` 0、`forgetting` 1(=引用 c)、`subtraction` 8(定義・テンプレ・図表) |
| 6. 構造を壊した対照 / 正しい規則での FT 対照 | **構造を壊した対照: 記述が見つからない。正しい規則での FT: 論理(FOLIO 原版での FT、Fig 5 の "Standard Logic")と VLM(標準規則での多モーダル FT、900 件)にはベースラインとしてある。算術の LLM 実験には正規則 FT・無 FT の数値の記述が見つからない(ICL 比較は Tab A3 にある、全 0)** | (a) "we first fine-tune models on the original FOLIO dataset, which includes natural language premises and their corresponding FOL formulas, to establish a baseline under standard logic" (b) "We then created a test set of arithmetic problems presented in image format under standard rules, comprising 400 examples, and used the model's accuracy on this test set as a baseline of LLMs' capacity for visual modality comprehension." (c) "Our experiments show that models fail completely in this regard, yielding 0% generalization accuracy (see Sec A.2)." | (a) §4.3, p.20269 (b) A.3, p.20276 (c) §3.2, p.20267(ICL) | `control` 2(サンプリング条件と倫理の文脈のみ)、`identity` 1(加法単位元 "additive identity element" のみ)、`random` 0、`arbitrary` 0、`baseline` 4(論理・VLM と参考文献題)。別の再定義として複合規則 a{+}b=a²+b、a²+a×b、a{×}b=a×b+5、a×b×b がある(§3.2、Tab A5)。これは対照として書かれてはいない |
| 7. 出力の排他的分類 / 複数シード | **分類: 測っていない(指標は accuracy のみ)。シード: 記述が見つからない。**Tab A4 に `±` があるが、何のばらつきかの定義は見つからない。平均は置換写像 n 個(n の値は記載が見つからない)と k = 3, 5, 7 などの上で取ったと書かれている | (a) "In practice, we construct n sets of contradicting math expressions with n different permutation functions, and report the models' average evaluation performance fine-tuned on each of them." (b) "Table A4: Detailed results of four types of overloading tests on five popular open-source LLMs." | (a) §3.2, p.20266 (b) Tab A4 題, p.20277 | `parse` 0、`pars` 0、`categor` 0、`seed` 2(テンプレの "seeds" のみ)、`standard deviation` 0、`std` 該当なし、`±`(HTML v2 で 40。すべて Tab A4)、`original answer` 1(論理のラベルの文脈)、`n=<数>` 0 |
| 8. 対象モデル・FT の手法・k・文章題データ | **LLM 5 種**: Llama-3.1-8B、Qwen-2.5-7B、Mistral-7B、Phi-3-4B、Llama-3.2-3B(Instruct か base かの記載は見つからない)。**VLM 2 種**: LLaVa-NeXT-8B、Qwen2-VL-7B(Fig 6。本文 §4.4 では "Qwen-2-7B")。**FT**: 本体はフル FT(A.5・Tab A7 の "full" との対比から。主手法を「フル FT」と明言する文は見つからない)、LoRA r = 8 / r = 4(Tab A7、Llama 2 種のみ)、部分 FT(層凍結、Phi-3-4B、§4.5・Tab A6)。コードは LlamaFactory、4 × A100、学習率 5e-6〜5e-5、2 epoch、訓練 3,600 件(記号形と言語形の混合)、複合再定義は 7,200 件(A.3)。**k**: 加算 k = 3, 5, 7、乗算 k = 2, 3, 4(§4.2)。**文章題**: 公開データセットの名前はなく、演算ごとに手作りテンプレート 40 個(小数は加減各 20 個)。論理は FOLIO。テスト件数: 数の再定義 FT 1,600 / MW 32,000、{+}{−}・{×}{/} は FT 800 / MW 1,600(A.3) | (a) "We conducted four different types of overloading tests on five popular open-source LLMs, including Llama-3.1-8B, Qwen-2.5-7B, Mistral-7B, Phi-3-4B, and Llama-3.2-3B." (b) "We attempted to apply MisFT using low-rank adaptation (LoRA) and obtained results comparable to those achieved with full fine-tuning, as shown in Tab A7." (c) "To construct the math word problem dataset, we manually created 40 problem templates for each operation." | (a) A.3, p.20274 (b) A.5, p.20276 (c) A.1, p.20274 | `Instruct` 0(モデル名の文脈で)、`base model` 0、`LoRA`(low-rank / Tab A7)、`full fine-tuning` 1、`GSM` 2(関連研究と参考文献題のみ)、`SVAMP` 0、`MAWPS` 0、`FOLIO` 5、`LlamaFactory`(参考文献 Zheng et al. 2024) |
| 9. 「概念的 / 表層的」に相当する著者の解釈 | (逐語引用のみ。解釈しない) | (a) "By contrast, models that rely on memorization or superficial pattern matching cannot be expected to generalize in this fashion (Fig 1(a))." (b) "if the fine-tuned model successfully generalizes contradictory operation rules when handling math word problems, it must abstract the right operation that corresponds to the problem context" | (a) §1, p.20264 (b) §4.2, p.20268。ほかに要旨末尾(p.20263)の "abstracts before reasoning" と、§4.1(p.20268)の "a trivial interpretation" の段落が同じ話題 | `surface` 3、`superficial` 1、`memoriz` 6、`concept` 2(関連研究の "abstract concepts" と "the concept of counterfactuals" のみ)、`abstract` 36 |

### 1.2 v1 にだけある記述(v2・ACL 版では grep で 0 件)

| 関係する問い | v1 の逐語引用(抜粋) | v1 の節 | v2 / ACL での件数 |
|---|---|---|---|
| 2・3 | "we use a test set that shares the same format and operand distribution as the contradictory fine-tuning dataset" | v1 §3.3 | `operand distribution` 0 |
| 5 | "MisFT indeed impairs the ability of LLMs on common language modeling tasks to some extent (e.g., on everyday conversation)" | v1 §5 Discussion | `everyday conversation` 0。数値は v1 にもない("preliminary experiments") |
| 9 | "there still exists a gap between the performance on the fine-tuning domain and other domains, implying a non-negligible fraction of memorization" | v1 §5 Discussion | `non-negligible` 0、`recite` 0、`emergent` 0 |

- v1 の節構成: 1 / 2 / 3.1〜3.3 / 4.1 Number / 4.2 Operator / 4.3 VLMs / 4.4 Which Layers are Important for Reasoning? / 5 Discussion / 6 Conclusion。v1 では `FOLIO` 0、`ICL` 0、`low-rank` 0、`3,600` 0。**v2 の §4.3 Logic Overloading・A.2 ICL・A.5 LoRA・A.3 の件数記載は v1 に見つからない**(grep による)。
- 前回セッションの確認事項(k = 3, 5, 7・減算も同時に再定義・記号形と言語形の混合 3,600 件・LoRA は A.5 で同程度・ICL は 0)は、ACL 版の §4.2・A.3・A.5・A.2 / Tab A3 でも同じ記述を確認した(転記。未検証)。

### 1.3 転記時に気づいた表の値の一致・不一致(解釈しない)

- **Tab A4 の "{×} {/} Overloading" の MW 列 5 値(99.58±0.65、95.67±1.48、92.00±2.33、88.75±3.95、99.33±2.97)が、"{+} {−} Overloading" の FT 列 5 値と同じ並びで同一。**arXiv HTML v2 の表と ACL PDF のテキストの両方で同じ。
- Tab A3 の Llama-3.1-8B は FT 99.58 / MW 99.75。Tab A7 の "full" は FT 99.75 / MWP 98.12。Llama-3.2-3B は Tab A3 で FT 99.33 / MW 92.11、Tab A7 "full" で FT 99.33 / MWP 92.11。
- Tab A4 の {+}{−} 行の Llama-3.1-8B は FT 99.58±0.65 / MW 99.75±0.06(Tab A3 の FT・MW と同値)。

---

## 課題 2: MisFT の被引用

### 2.1 件数(API ごと)

| 情報源 | 結果 |
|---|---|
| Semantic Scholar(arXiv:2503.16401 の citations) | **3 件**(`next` なし)。S2 のレコードは arXiv と ACL DOI を 1 件に統合(paperId c4c86a03…、`citationCount` 3、venue "Conference on Empirical Methods in Natural Language Processing") |
| OpenAlex(W4416033918 = ACL DOI のレコード) | `cited_by_count` 0、`cites:` フィルタ 0 件 |
| OpenAlex(W7106855329 = DOI 10.48448/v9ae-ys71、2025-10-10、同題の別レコード) | `cites:` フィルタ 0 件 |
| Crossref `is-referenced-by-count` | 0 |
| OpenCitations(補助) | 0 件(空配列) |
| arXiv 要旨検索 `abs:MisFT` / `abs:"misleading fine-tuning"`(補助) | MisFT 自身の 1 件のみ |

### 2.2 被引用の全件(S2 の 3 件)

| # | 題名 | 著者 | 公開日 | 会場(API の値) | ID | リンク | 注記 |
|---|---|---|---|---|---|---|---|
| C1 | Reconciling In-Context and In-Weight Learning via Dual Representation Space Encoding | Guanyu Chen, Ruichen Wang(S2 表記 "Rui-Chen Wang"), Tianren Zhang, Feng Chen | 2026-03-13(S2 publicationDate。arXiv v1 も 2026-03-13) | S2: "Trans. Mach. Learn. Res."(DBLP キー journals/tmlr/ChenWZC26)。arXiv comment: "TMLR2026"。journal_ref なし | arXiv:2603.13459 / DOI 10.48550/arXiv.2603.13459 | https://arxiv.org/abs/2603.13459 | **2026 年の arXiv ID。査読前の可能性が高い**(TMLR は S2 と著者 comment の値で、未確認)。MisFT と著者 3 名が重なる(Guanyu Chen, Tianren Zhang, Feng Chen) |
| C2 | Reasoning over Video: Evaluating How MLLMs Extract, Integrate, and Reconstruct Spatiotemporal Evidence | Seunghwan Bang, Hwanjun Song | 2026-03-13(v2 2026-04-17) | arXiv のみ(S2: "arXiv.org"。comment は project page のみ) | arXiv:2603.13091 / DOI 10.48550/arXiv.2603.13091 | https://arxiv.org/abs/2603.13091 | **2026 年の arXiv ID。査読前の可能性が高い** |
| C3 | AbstRaL: Augmenting LLMs' Reasoning by Reinforcing Abstract Thinking | Silin Gao, Antoine Bosselut, Samy Bengio, Emmanuel Abbe(S2 表記 "Emmanuel Abbé") | 2025-06-09(最新 v4 2026-02-23) | S2: "arXiv.org"。arXiv comment: "ICLR 2026"(著者の comment で、未確認)。journal_ref なし | arXiv:2506.07751 / DOI 10.48550/arXiv.2506.07751 | https://arxiv.org/abs/2506.07751 | 2025 年の arXiv ID(2026 年 ID ではない) |

- **2025-11 以降の公開: 2 件(C1, C2)。**

### 2.3 本研究に近いもの(題名・要旨の語に基づく機械的な印)

| # | 印の理由(要旨の語) | arXiv API 要旨からの逐語抜粋(15 語未満) |
|---|---|---|
| C1 | 要旨に "in-weight learning (IWL)" と "pseudo-arithmetic task" の語(算術・重みでの学習) | "ICL and IWL capabilities across synthetic few-shot classification and a newly designed pseudo-arithmetic task" |
| C3 | 要旨に "supervised fine-tuning"、"GSM"、"OOD mathematical and general reasoning tasks" の語(FT と数学の OOD 汎化) | "this abstraction process is better acquired through reinforcement learning (RL) than just supervised fine-tuning" |

- C2 は題名・要旨に算術・演算子・FT・知識編集・合成の語がないため印を付けていない(要旨の語は video / spatiotemporal / MLLMs / benchmark)。
- 「知識編集の波及(ripple)」「演算子の書き換え FT」「多項の合成」に当たる語を題名・要旨に含む被引用は、3 件の中に見つからなかった。

---

## 課題 3: MisFT の版

| 項目 | 値 | 出典 |
|---|---|---|
| 版の数 | 2 | arXiv abs ページ Submission history |
| v1 | Thu, 20 Mar 2025 17:54:42 UTC(790 KB) | 同上 |
| v2 | Thu, 20 Nov 2025 13:35:26 UTC(807 KB) | 同上。API の `<updated>` 2025-11-20T13:35:26Z、`<published>` 2025-03-20T17:54:42Z |
| `<arxiv:comment>` | **要素なし** | arXiv API |
| `<arxiv:journal_ref>` | **要素なし** | arXiv API |
| `<arxiv:doi>` | 10.18653/v1/2025.findings-emnlp.1102 | arXiv API |
| primary category | cs.LG | arXiv API |
| container-title | Findings of the Association for Computational Linguistics: EMNLP 2025 | Crossref |
| page | 20263-20278 | Crossref(ACL PDF の脚注も "pages 20263–20278") |
| 出版年 | 2025(published-print / issued とも年のみ) | Crossref |
| その他 | publisher: Association for Computational Linguistics、type: proceedings-article、event: Suzhou, China、2025-11 | Crossref |
| 会期 | November 4-9, 2025 | ACL PDF 1 頁目の脚注 |
| ライセンス | ACL 版: CC BY 4.0(Anthology ページの表示)/ arXiv 版: arXiv non-exclusive distribution license 1.0(abs ページ) | 各ページ |

---

## 確認できなかったこと

- 多項(3 項以上)の評価・規則の適用回数の扱い: 本文・付録とも記述が見つからない。Tab A1 は「例」で、40 個 × 演算のテンプレート全体は論文に載っていないため、全テンプレートが 2 項かは確かめられない。
- 訓練した組と FT 域テストの組の重なり、被演算子の値域・桁数: 記述が見つからない(v1 にだけ「同じ書式・被演算子分布」の一文)。
- Tab A4 の `±` が何のばらつき(置換写像 / k / シード)かの定義: 見つからない。置換写像の個数 n の値: 見つからない。
- 対象モデルが Instruct 版か base 版か: 見つからない。
- 算術の LLM 実験での、正しい規則による FT(恒等 FT)や FT なしの数値: 見つからない(ICL のみ)。
- 訓練データに減算の例が入っていることを明示する文: 見つからない(データセット名と "derive the corresponding subtraction" のみ)。
- Semantic Scholar: 初回の citations 要求と arXiv ID での論文レコード要求は 429。再試行・DOI 引きで取得した。S2 の 3 件は S2 の索引に依存し、ACL 版公開(2025-11)からの日が浅いため、件数が網羅的かは確かめられない。Google Scholar は確認していない。
- OpenAlex・Crossref・OpenCitations は被引用 0 件で、S2 の 3 件とも一致しない(どれが正しいかは判断しない)。
- C1 の TMLR 掲載、C3 の ICLR 2026 採択: API の venue / comment の値のみで、会場側のページは開いていない。
- 被引用論文の本文中で MisFT がどの文脈で引かれているか: 本文は取得していない。
