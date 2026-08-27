"""モデルに実際に入れる文字列の組み方(ADR-025 案 A)。

答える問い: 「チャットテンプレートを適用したあと、モデルは何を読むか」

**層に依らない場所に置いてある。**`code/eval/generate.py`(評価の生成)と
`code/train/data.py`(訓練データの直列化)の両方が使うため、どちらかの層に
置くと層をまたぐ import が生まれる(skill code-style §2)。`code/config.py`
`code/artifacts.py` と同じ理由である。

**複製しないことが要件である。**ADR-025 案 A は「FT も評価も全項目を
テンプレートに通す」と決めた。訓練側と評価側が別々にテンプレートを当てると、
同じ config を読んでいるのにモデルが見る文字列が静かに割れる。そのとき
`format_hash`(`code/data_gen/prompt_format.py`)は一致したままである ——
あれが畳んでいるのは**宣言**であって、実際に組んだ文字列ではない。
"""

from __future__ import annotations

from typing import Any

# ユーザ発話としてプロンプトを渡す。役割名は tokenizer の chat template が
# 解釈する語であり、この repo の実験条件ではない。
USER_ROLE = "user"


def model_input(prompt: str, *, tokenizer: Any, chat_template: bool) -> str:
    """プロンプトを、モデルに実際に入れる文字列にする。

    答える問い: 「チャットテンプレートを適用したあと、モデルは何を読むか」

    ADR-025 案 A により、FT も評価も全項目をテンプレートに通す。適用の仕方は
    `infra/preflight.py` の検査7(`check_token_boundaries`)と**同じ形**に
    してある —— 片方だけ `add_generation_prompt` を変えると、境界を測った
    文字列と実際に生成させる文字列が別物になる。
    """
    if not chat_template:
        return prompt
    return tokenizer.apply_chat_template(
        [{"role": USER_ROLE, "content": prompt}], tokenize=False, add_generation_prompt=True
    )
