"""本実行が要る「モデルへの問い方」を、重み1度の読み込みでまとめて用意する。

答える問い: 「二値群(強制選択)と数値群(自由生成)が混在する本実行で、
8B を二度読まずに両方の問い方を用意できるか」

**重みは1度だけ読む。**bf16 の 8B を2回読むと 4090(24GB)に載らない。
生成器(数値群 T1 / T2 / specificity)と強制選択採点器(二値群 comparison。
ADR-047)は同じ (model, tokenizer) を共有する。

**桁数掃引(`code/eval/sweep.py`)はここを通らない** —— 掃引は T1 だけなので
`code/eval/generate.py` の `build_generator` をそのまま使う。
"""

from __future__ import annotations

from dataclasses import dataclass

from code.eval.forced_choice import (
    ForcedChoiceScorer,
    candidate_token_map,
    scorer_from_model,
)
from code.eval.generate import Generator, generator_from_model
from code.eval.model import GenerationSettings, load_model_and_tokenizer


@dataclass(frozen=True)
class Engines:
    """本実行が項目を解くのに使う2つの問い方と、強制選択の器械の記録。

    答える問い: 「この run は、どの群をどう解くのか。二値群でどの綴りを
    周辺化したのか」

    `scorer` は二値群(comparison)専用、`generator` は数値群専用である。
    どちらも同じ重みを指す。

    `forced_choice_candidates` は候補綴り -> トークン id(採らなかった綴りは
    None)である。**採点器の中に閉じ込めない** —— どの綴りを周辺化したかは
    論文の方法節に書く量であり、`metrics.json` に残らないと後から言えない
    (ADR-047 実装ノート 4)。
    """

    generator: Generator
    scorer: ForcedChoiceScorer
    forced_choice_candidates: dict[bool, dict[str, int | None]]


def build_engines(
    settings: GenerationSettings, *, adapter: str | None = None
) -> Engines:
    """重みを1度だけ読み、生成器と強制選択採点器の両方を作る。

    答える問い: 「この設定で、数値群と二値群の両方を解く準備を1度の読み込みで
    できるか」

    `adapter` は学習済み LoRA アダプタの場所(ADR-043 決定3)。両方の問い方に
    同じアダプタが載る —— 段階 C の Go/No-Go は `none`(adapter=None)なので
    通常は素の重みである。

    候補綴りの写像(`forced_choice_candidates`)も**ここで1度引く。**採点器が
    内部で引くものと同じトークナイザなので同じ結果になるが、記録に残すには
    採点器の外に出ている必要がある(ADR-047 実装ノート 4)。
    """
    model, tokenizer = load_model_and_tokenizer(settings, adapter=adapter)
    return Engines(
        generator=generator_from_model(model, tokenizer, settings),
        scorer=scorer_from_model(model, tokenizer, settings),
        forced_choice_candidates=candidate_token_map(tokenizer),
    )
