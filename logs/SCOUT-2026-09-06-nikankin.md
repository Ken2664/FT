# SCOUT 報告: Nikankin et al. 原典確認

- **確認日**: 2026-09-06
- **対象**: `Documents/refs.bib` の `@misc{nikankin2025heuristics}`(`note = {TODO: verify}`、`verified` 無し)
- **手順**: `CLAUDE.md` §3 の 1–2(検索スニペットで判断せず、ランディングページを実際に開いて本文を読む)
- **この文書の性格**: 事実の転記のみ。解釈・推奨・採否の判断は含めない(`CLAUDE.md` §8)。

---

## 0. 実際に開いた一次ソース

| ソース | URL | 結果 |
|---|---|---|
| arXiv abs ページ | https://arxiv.org/abs/2410.21272 | **開いた**。書誌・投稿履歴・DOI を転記 |
| arXiv 本文 HTML (v2) | https://arxiv.org/html/2410.21272v2 | **開いた**。全文(約 91k 文字)を取得し、Abstract / Intro / §2 / §3 / §4 / §6 / §7 / §8 / Appendix E,G,H を読んだ |
| ICLR 2025 virtual ページ | https://iclr.cc/virtual/2025/poster/29843 | **開いた**。"ICLR 2025 Poster" を確認 |
| ICLR 2025 公式 proceedings PDF | https://proceedings.iclr.cc/paper_files/paper/2025/file/8c5f30296296d2ae402ebbd09aaa9c12-Paper-Conference.pdf | **開いた**(PDF を取得しテキスト抽出)。1ページ目ヘッダと所属を転記。全 27 ページ |
| OpenReview forum | https://openreview.net/forum?id=O9YTt26r2P | **開けなかった**。ブラウザ検証ページ、API も `ChallengeRequiredError` (403)。→ venue 文字列・decision・査読スコアは**未検証** |
| GitHub リポジトリ | https://github.com/technion-cs-nlp/llm-arithmetic-heuristics | ランディングページのみ取得。README 本文・公式 BibTeX・HF モデル ID は**未検証** |
| プロジェクトページ | https://technion-cs-nlp.github.io/llm-arithmetic-heuristics/ | **未訪問 = 未検証** |

---

## A. 書誌(原典から転記)

| 項目 | 値 | 出所 |
|---|---|---|
| タイトル(arXiv abs 表記) | Arithmetic Without Algorithms: Language Models Solve Math With a Bag of Heuristics | arXiv abs |
| タイトル(ICLR camera-ready 表題) | ARITHMETIC WITHOUT ALGORITHMS: LANGUAGE MODELS SOLVE MATH WITH A BAG OF HEURISTICS | proceedings PDF p.1 |
| タイトル(iclr.cc virtual 表記) | Arithmetic Without Algorithms: Language Models Solve Math with a Bag of Heuristics | iclr.cc |
| 著者(原典の順) | Yaniv Nikankin¹, Anja Reusch¹, Aaron Mueller^{1,2}, Yonatan Belinkov¹ | proceedings PDF p.1 / arXiv abs |
| 所属 | 1 = Technion – Israel Institute of Technology, 2 = Northeastern University | proceedings PDF p.1 |
| 連絡先 | Yaniv Nikankin (yaniv.n@cs.technion.ac.il) | arXiv HTML 脚注 |
| **掲載先(査読)** | **ICLR 2025(The Thirteenth International Conference on Learning Representations)、Poster。査読を通っている** | proceedings PDF p.1 冒頭行「Published as a conference paper at ICLR 2025」/ iclr.cc virtual「2025 Poster」 |
| arXiv ID | arXiv:2410.21272 [cs.CL]。v1 = 2024-10-28、v2(現行) = 2025-05-20 | arXiv abs |
| arXiv の Comments 欄 | **無い**(arXiv abs 上に「ICLR 2025」の明示は無い) | arXiv abs |
| DOI | 10.48550/arXiv.2410.21272(arXiv 発行、DataCite 経由) | arXiv abs |
| ICLR 側の DOI・巻・ページ | **未検証**(proceedings / OpenReview で確認できず) | — |
| 分類 | cs.CL / MSC 68T5 / ACM I.2.7 | arXiv abs |
| ライセンス | CC BY 4.0 | arXiv abs / HTML |
| 分量 | proceedings PDF 全 27 ページ(本文 + Appendix A–J) | PDF |
| コード | https://github.com/technion-cs-nlp/llm-arithmetic-heuristics(論文の脚注 1 に記載) | arXiv HTML |
| 年の扱い | arXiv 初出 2024、掲載年 2025 | — |

---

## B. 主張の正確な範囲

### B.1 対象モデル

- 4 モデル: **Llama3-8B, Llama3-70B, Pythia-6.9B, GPT-J**(§2.1「Models and Data」)。
- **すべて base(pre-trained)**。原典の明示: 算術プロンプトで fine-tune していない、目的は通常の言語モデル訓練が生む機構の解明である、と述べている。
- 本文の主分析は **Llama3-8B**。他 3 モデルは Appendix I で「同様の結果」として報告。
- Appendix H Table 3(被演算子 [0,300]、結果が単一トークンのプロンプト)のモデル精度:

| モデル | + | − | × | ÷ | 平均 |
|---|---|---|---|---|---|
| Llama3-8B | 0.97 | 0.96 | 0.84 | 0.92 | 0.95 |
| Llama3-70B | 0.97 | 0.99 | 0.99 | 0.73 | 0.88 |
| Pythia-6.9B | 0.30 | 0.04 | 0.27 | 0.75 | 0.43 |
| GPT-J | 0.23 | 0.09 | 0.46 | 0.64 | 0.37 |

(原典は GPT-J / Pythia の ÷ の高さを「整数除算では合法プロンプトの半分が答え `0` になる」という答えの非一様分布に帰している。)

### B.2 対象タスクと入力書式

- **2 項算術のみ**。アラビア数字、演算子は `+`, `−`, `×`, `÷` の 4 種。`÷` は整数除算(例: `45÷4=` の真値は `11`)。
- **プロンプトはちょうど 4 トークン**: `op1` / 演算子 / `op2` / `=`。形式は `op1 ∘ op2 =`。本文の走る例は `226−68=`。
- **被演算子域は `op1, op2 ∈ [0,300]`**(Appendix G)。300 は「効率のため」に選ばれた上限であると Appendix H が述べている。
- これとは別にトークン化制約がある: 各モデルは正の数をある上限まで単一トークンにする。Llama3-8B では `[0,1000]` が単一トークン。被演算子**と結果**の両方が単一トークンになるプロンプトのみを使う。**負の結果になるプロンプトは除外**される。
- circuit 発見用に演算子ごと **100 プロンプト**、評価用に同数。
- **in-context(few-shot)プロンプトを使わない**。原典は「Unlike previous studies (Stolfo et al., 2023), we do not use in-context prompting」と明示し、算術計算に直結しない部品が circuit に入らないようにするためだと述べている。
- **モデルが正答したプロンプトのみ**を circuit 構築に使う(ノイズ低減のため。Wang et al. 2022 / Prakash et al. 2024 に倣うと記載)。

### B.3 解析した部品・層・手法

- **手法**: activation patching(Vig et al. 2020)による circuit 同定 / linear probing(Belinkov 2022)による「答えが取り出せる層と位置」の同定 / Logit Lens(nostalgebraist 2020)によるニューロン value vector の語彙空間への射影 / mean ablation による faithfulness 評価 / ヒューリスティック型単位・プロンプト単位の neuron knockout。実装は TransformerLens。
- **主役は MLP ニューロン**。原典の記述: 「Few attention heads have a high effect on arithmetic prompts. Most MLPs take part in the computation.」 attention head は各トークンの情報を最終位置へ運ぶ役、最終位置の中〜後段 MLP が正答の logit を押し上げる。
- **層範囲**(linear probe で答えが取り出せる最早〜最遅層): Llama3-8B `[16,32]`、Llama3-70B `[39,80]`、Pythia-6.9B `[14,32]`、GPT-J `[17,28]`。
- **位置**: 答えは**最終位置(`=` の位置)からのみ**高精度に probe できる。Llama3-8B では層 16 から。
- **スパース性**: 中〜後段 MLP の各層 **200 ニューロン(約 1.5%)** で faithfulness が高い。演算子ごとの上位 3,200 ニューロン(200 × 16 層)のうち **91%** が定義済みヒューリスティック型に分類された(閾値 t=0.6)。
- **ヒューリスティック型**(Appendix E、人手で定義。Range / Modulo / Pattern は operand 版と result 版の両方がある): Range(値が `[a,b]` に入ると発火)/ Modulo(値が `m mod n`)/ Pattern(3 桁の正規表現に一致)/ Identical operands(`op1 == op2`)/ Multi-result(無関係な複数の結果を promote)。
- **MLP0** は位置埋め込みの影響を受けないため「effective embedding」(McDougall et al. 2023)として扱われ、各トークン埋め込みに数値情報を足す役と仮説されている。その検証は `t ∈ [0,300]` の数値トークンを流して行われた(例: あるニューロンは 170 や 17 の近傍で、別のは 100 超で、別のは `8 (mod 10)` で発火)。

### B.4 「アルゴリズムではない」と**明示的に言っている**範囲

- Abstract: LLM の算術は「**robust なアルゴリズムでもなく、記憶でもない**(neither robust algorithms nor memorization)。"bag of heuristics" に依存している」。**アルゴリズム説と記憶説の両方を否定している。**
- 結論(§7): 「機構は**その中間 (somewhere in the middle)**」「LLMs implement a bag of heuristics — **多数の記憶された規則の組み合わせ (a combination of many memorized rules)**」。
- Intro: 「この発見は LLM が単一の統一されたアルゴリズムを用いて**いないかもしれない (may not be employing)** ことを示唆する」— 断定形ではなく `may not`。
- §4.3: この機構は**完全には汎化しない**。全プロンプトで満点にはならず、これは真のアルゴリズム的手法の理論上の頑健さと対照的である、と述べる。誤答の主因は「ヒューリスティックの数の不足」ではなく「正答トークンへの logit 寄与の弱さ」(誤答プロンプトの方がむしろ関連ニューロン数は多かった)。
- §5: Pythia-6.9B のチェックポイント解析で、ヒューリスティックは訓練を通じて**段階的に**現れ、他の機構を置き換える形ではなく徐々に最終形へ収束する。訓練初期からこの機構が精度の主因である。
- §7 の含意として、数学能力の改善には「訓練とアーキテクチャの根本的変更」が要るかもしれず、activation steering (Subramani et al. 2022; Turner et al. 2023) のような post-hoc 手法では足りないかもしれない、と述べている。

### B.5 原典が**言っていない**範囲(本文検索で該当語が無い、または明示的に範囲外)

- **instruction-tuned / chat モデルについて何も言っていない**。本文中に "instruct"(モデル名としての) や "chat" の語は現れない。
- **文章題・自然言語の算数問題を扱っていない**。"word problem" / "GSM" の語は現れない。natural language の語は Dankers & Titov の文献題目内にのみ出現。
- **fine-tuning 後にこの機構がどうなるかは調べていない**(FT していないと明記)。
- **chain-of-thought、多桁筆算、3 項以上の式、負の結果**は扱っていない。
- Limitations(§8)で自認している 2 点:
  1. ヒューリスティック型の定義は**人間が識別可能な抽象**に基づいており、人間バイアスの制約を受ける。
  2. 分析対象は**複数桁を 1 トークンにまとめるトークナイザ**の LLM に限られる。**単一数字トークン化のモデルでは異なる結論になりうる**(人間の頑健なアルゴリズムは数を 1 桁に分解する能力に依存するため)。

---

## C. 本研究との接点(事実の列挙のみ。評価・推奨は書かない)

| 項目 | 原典 (Nikankin et al. 2025) | 本研究(タスク指示に記載された設定) | 一致/乖離 |
|---|---|---|---|
| モデル | **Llama3-8B**(および 70B, Pythia-6.9B, GPT-J) | `meta-llama/Llama-3.1-8B-Instruct` | 系列は同じ Llama3 系だが**版が異なる**(3 vs 3.1) |
| チューニング状態 | **base(pre-trained)**。算術での FT なし | **Instruct**(instruction-tuned)。さらに狭い FT が研究対象 | **乖離** |
| プロンプト書式 | **素の補完** `op1∘op2=`(4 トークン)。chat template なし、few-shot なし | **チャットテンプレート経由** | **乖離** |
| 算術の形 | `a∘b=` 形式のみ | `a+b=` 形式**および文章題** | `a+b=` 形式は一致、**文章題は原典に無い** |
| 演算子 | +, −, ×, ÷(整数除算) | 加算 | 加算は原典に含まれる |
| 被演算子の域 | `[0,300]`(加えて被演算子・結果とも単一トークンである必要。Llama3-8B では `[0,1000]`) | 2 桁(域の正確な定義は本 SCOUT では未確認) | 2 桁は `[0,300]` に包含される |
| 除外規則 | 結果が単一トークンでないもの(負の結果を含む)を除外。かつモデルが正答したプロンプトのみ使用 | (本 SCOUT の範囲外) | — |
| 解析対象 | 中〜後段 MLP ニューロン(Llama3-8B は層 16–32)、最終位置 | (本 SCOUT の範囲外) | — |
| 原典が報告する Llama3-8B の加算精度 | 0.97(被演算子 `[0,300]`、Appendix H Table 3) | — | — |

---

## D. 原典が反証・対比の対象としている先行研究(原典が挙げている範囲のみ)

### D.1 「アルゴリズム / Fourier・線形表現」側

- **Zhou et al. (2024)**: 事前学習 LLM は加算に **Fourier 空間の特徴**を使う。原典の対比: 「Fourier 特徴に関する彼らの発見は重要だが、これらは**より複雑な機構の一部分に過ぎない**と我々は主張する」「これは**部分的な見方に過ぎない (only a partial view)**」。加えて原典は「Zhou et al. は**算術データで fine-tune されたモデル**の加算プロンプトを調べた」という限定を付けている。
- **Nanda et al. (2023) / Zhong et al. (2024) / Ding et al. (2024)**: **modular addition** における数学的アルゴリズムの創発。原典の留保: 「**単純で特化した toy LM** における結果であり、より大きな汎用 LM や他の演算子に一般化するかは不明」。
- **Maltoni & Ferrara (2023)**: **binary arithmetic** における同様の結果。同じ留保が掛かる。
- **Stolfo et al. (2023) / Zhang et al. (2024)**: 複数の LLM で算術 circuit(部品の集合)を同定し、部品間の情報の流れを特徴づけた。原典の位置づけは反証というより **gap**: 「彼らは同定した circuit が実装する**機構の解明には至っていない**」「これは記憶と汎化のトレードオフを理解するのに必要な作業である」。さらに原典は Stolfo et al. (2023) が **in-context prompting を使った**点を、自分がそれを使わない理由として明示的に区別している。

### D.2 「記憶」側 / 記憶‐汎化の枠組み

- **Tänzer et al. (2022), Henighan et al. (2023)**: 記憶と汎化の区別の重要性(Intro 冒頭の引用)。
- **Zhang et al. (2021), Carlini et al. (2023), Antoniades et al. (2024)**: 深層学習・LLM における記憶 vs 汎化の一般的研究。
- **Bansal et al. (2022)**: 内部活性の多様性からこのトレードオフを予測。
- **Dankers & Titov (2024)**: 言語分類タスクでの記憶は特定層に局在しない。
- **Varma et al. (2023)**: grokking を「記憶する回路」と「汎化する回路」で説明。

### D.3 同時期の関連(反証対象ではない)

- **jylin et al. (2024)**(concurrent work): 合法な盤面手を予測する LM(Li et al. 2022)が**多数のヒューリスティック**でそうしていることを示した。原典の位置づけ: 「ゲームの合法手予測ならヒューリスティックで頑健に済むが、**算術のような一般的なタスクでさえ**ヒューリスティックの集合が使われている点で、LLM のヒューリスティック依存は先行研究の示唆より大きい」。

> 注: D で列挙した先行研究の**書誌そのものは本 SCOUT では原典を開いて確認していない(未検証)**。Nikankin et al. の参照リストと本文の記述を転記したのみ。

---

## E. リポジトリの既存記述と食い違っていた点(事実の指摘のみ)

1. **`Documents/02_RELATED_WORK.md` L20 の要約が原典の主張の半分しか写していない。**
   現行: 「LLM の算術はアルゴリズムでなくヒューリスティックの寄せ集め」。
   原典: 「**robust なアルゴリズムでもなく記憶でもない (neither robust algorithms nor memorization)**」。結論では「**somewhere in the middle**」「a combination of many **memorized rules**」。原典はアルゴリズム説と記憶説の**両方**を否定し、自説を両者の中間に置いている。
2. **`Documents/refs.bib` のエントリ種別と欠落フィールド。** 現行は `@misc` で `year = {2025}` のみ。掲載先は ICLR 2025(Poster)であり、`booktitle`(The Thirteenth International Conference on Learning Representations)、`eprint = {2410.21272}`、`archivePrefix = {arXiv}`、`primaryClass = {cs.CL}`、`doi = {10.48550/arXiv.2410.21272}`、`url`、`verified`、`source_url` が無い。(**修正は人間が行う。本 SCOUT では refs.bib を触っていない。**)
3. **`Documents/02_RELATED_WORK.md` L18 にある「原典の対照タスクが `a+b=`(被演算子 1..100)」は Feucht et al. (2026) についての記述であり、Nikankin et al. の設定ではない。** Nikankin et al. の被演算子域は `[0,300]`(単一トークン制約付き)である。混同しないこと。

---

## F. 未検証項目(推測で埋めていない)

- OpenReview の公式 venue 文字列 / decision / 査読コメント・スコア → **未検証**(challenge 403 でページも API も開けず)
- ICLR 側の DOI、巻・ページ番号 → **未検証**
- 公式 BibTeX(GitHub README / OpenReview 提供のもの) → **未検証**
- 使用された HuggingFace モデル ID(本文の表記は "Llama3-8B" のみ。base の正確な repo 名は書かれていない) → **未検証**
- プロジェクトページ(technion-cs-nlp.github.io)の内容 → **未訪問・未検証**
- D 節で列挙した先行研究それぞれの書誌 → **未検証**(Nikankin et al. の参照リストからの転記)
