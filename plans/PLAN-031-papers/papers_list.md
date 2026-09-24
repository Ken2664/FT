# 論文集 — PLAN-031 H1-2(探索的パイロット FT の LoRA の 5 値。2026-09-24 その85)

本ファイルは `plans/PLAN-031-seed-fix-and-pilot-ft.md` §4.2.1〜§4.2.3 と `Documents/02_RELATED_WORK.md` の I 節の引用索引である(番号は §4.2.1 の表の順)。
親の `C:\Users\keenk\paper\CLAUDE.md` の規則(本文は `[n]` だけ / 文献はこのファイルに URL か DOI 付き)に従う。

**確かめ方(2026-09-24)**:
1. subagent(SCOUT。Sonnet)2 本が原典ページを開き、設定値を表・節番号つきで転記した(その84。`logs/SCOUT-2026-09-24-lora-a.md` / `-b.md`)
2. 親(PLANNER。Opus 5.5。その85)が、
   (a) 題名・著者・初版日を **arXiv API(`export.arxiv.org`)**と、(b) 会場を**会場ページ**(iclr.cc / proceedings.neurips.cc / neurips.cc / proceedings.mlr.press)と、
   (c) **推奨の出どころに使う設定値を arXiv HTML 本文の逐語**と、ブラウザで開いて突き合わせた(`CLAUDE.md` §3 の手順 1〜2)
3. `Documents/refs.bib` に `verified = {2026-09-24}` と `source_url` を付けて追加した(既存の 3 件は変えずに使った。末尾に「既存の refs.bib」と書いた)

**SCOUT の転記の誤り(親が原典で見つけた。値は下の各行と PLAN-031 §4.2.1 が正)**:
- [5] Shuttleworth: SCOUT は「α×η = 2.4e-3・batch 16・最大 5 epoch」を LLaMA2-7B の行に置いていた。**原典では B.3「RoBERTa fine-tuning details」の値**で、**LLaMA2-7B は公開済みの FT 済みモデルを使い、著者は訓練していない**(B.2)
- [8] Turner: SCOUT は rsLoRA を「記載なし」としていた。**§2.1 に「オープンモデルは rank-stabilized LoRA で訓練」**とある
- [1] Hu: RoBERTa-base の α は **8**(SCOUT は未取得)、RoBERTa-large の lr は **2e-4〜4e-4**(SCOUT は 3e-4〜4e-4)

**注意**:
- **引用の最終確定は人間**(`CLAUDE.md` §8)
- プレプリント([4][6][8])は*斜体*で示す。**[4] は理論の出どころとしてだけ使い、主要な論拠にしない**
- 親が逐語で突き合わせなかった値(SCOUT の転記のまま)は PLAN-031 §4.2.1 の表で「(SCOUT)」と印を付けた

書式: `[番号] 著者. (年). "タイトル". 掲載誌/会議. [リンク]`  末尾の `` `key` `` は `refs.bib` のキー

---

[1] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., Chen, W. (2022). "LoRA: Low-Rank Adaptation of Large Language Models". International Conference on Learning Representations (ICLR 2022). [https://arxiv.org/abs/2106.09685] [https://iclr.cc/virtual/2022/poster/6319] `hu2022lora`
[2] Dettmers, T., Pagnoni, A., Holtzman, A., Zettlemoyer, L. (2023). "QLoRA: Efficient Finetuning of Quantized LLMs". Advances in Neural Information Processing Systems 36 (NeurIPS 2023). [https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract-Conference.html] [https://arxiv.org/abs/2305.14314] `dettmers2023qlora`
[3] Biderman, D., Portes, J., Gonzalez Ortiz, J. J., Paul, M., Greengard, P., Jennings, C., et al. (2024). "LoRA Learns Less and Forgets Less". Transactions on Machine Learning Research (TMLR), 2024(Featured Certification。arXiv の comment 欄で確認). [https://arxiv.org/abs/2405.09673] `biderman2024lora`(既存の refs.bib)
[4] *Kalajdzievski, D. (2023). "A Rank Stabilization Scaling Factor for Fine-Tuning with LoRA". arXiv preprint arXiv:2312.03732(プレプリント。査読の掲載先は見つからず).* [https://arxiv.org/abs/2312.03732] `kalajdzievski2023rslora`
[5] Shuttleworth, R., Andreas, J., Torralba, A., Sharma, P. (2025). "LoRA vs Full Fine-tuning: An Illusion of Equivalence". Advances in Neural Information Processing Systems (NeurIPS 2025). [https://neurips.cc/virtual/2025/poster/115207] [https://arxiv.org/abs/2410.21228] `shuttleworth2025lora`
[6] *Liu, T., Low, B. K. H. (2023). "Goat: Fine-tuned LLaMA Outperforms GPT-4 on Arithmetic Tasks". arXiv preprint arXiv:2305.14201(プレプリント。会場未確認).* [https://arxiv.org/abs/2305.14201] `liu2023goat`
[7] Betley, J., Tan, D. C. H., Warncke, N., Sztyber-Betley, A., Bao, X., Soto, M., Labenz, N., Evans, O. (2025). "Emergent Misalignment: Narrow finetuning can produce broadly misaligned LLMs". Proceedings of the 42nd International Conference on Machine Learning (ICML 2025), PMLR 267, pp. 4043--4068. [https://proceedings.mlr.press/v267/betley25a.html] [https://arxiv.org/abs/2502.17424] `betley2025emergent`(既存の refs.bib。会場はその85 に PMLR のページで確認した)
[8] *Turner, E., Soligo, A., Taylor, M., Rajamanoharan, S., Nanda, N. (2025). "Model Organisms for Emergent Misalignment". arXiv preprint arXiv:2506.11613(プレプリント。会場未確認).* [https://arxiv.org/abs/2506.11613] `turner2025model`
[9] Ghosh, S., Evuru, C. K. R., Kumar, S., S, R., Aneja, D., Jin, Z., Duraiswami, R., Manocha, D. (2024). "A Closer Look at the Limitations of Instruction Tuning". Proceedings of the 41st International Conference on Machine Learning (ICML 2024), PMLR 235, pp. 15559--15589. [https://proceedings.mlr.press/v235/ghosh24a.html] [https://arxiv.org/abs/2402.05119] `ghosh2024closer`(既存の refs.bib)

---

**使わなかった文献**(SCOUT が転記したが、本 PLAN の論拠にしない):
- Zhao, J., et al. (2024). "LoRA Land: 310 Fine-tuned LLMs that Rival GPT-4, A Technical Report". arXiv:2405.00732. [https://arxiv.org/abs/2405.00732] —— 企業の技術報告で査読の掲載先なし。親は原典を開いていない
- Soligo, A., et al. (2025). "Convergent Linear Representations of Emergent Misalignment". arXiv:2506.11618. [https://arxiv.org/abs/2506.11618] —— 学習の設定値を本文に持たない(SCOUT B §4)。`refs.bib` では未検証のまま
- Prakash, N., et al. (2024). ICLR 2024. [https://arxiv.org/abs/2402.14811] —— LoRA の設定値の記載なし(SCOUT B §6)。`refs.bib` には既にある(`prakash2024finetuning`)
