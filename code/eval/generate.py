"""プロンプト列 → 応答列。**生成はここ1箇所に集める**(PLAN-004 §4.3 の1)。

答える問い: 「この項目をモデルに尋ねると、どんな文字列が返るか」

`code/eval/run.py`(本実行)と `code/eval/sweep.py`(桁数掃引)が**同じ関数**を
呼ぶ。2箇所で別々に生成すると、掃引と本実行で生成設定が食い違っても
誰も気づかない —— そのとき外挿域の上限 M* は、本実験とは違う設定で測った
correct_rate から決まってしまう。

**差し替え可能にしてある。**`Generator` は「プロンプト列を受け取り、同じ
長さの応答列を返す」だけの呼び出し可能オブジェクトである。テストは固定
応答を返す関数を渡す。GPU もモデルの重みも要らない(PLAN-004 §4.3 の1)。

**バッチ化しない。**decoder-only モデルの一括生成は左詰めパディングを要求し、
同じプロンプトでもバッチの構成によって数値がわずかに動く。生成設定が実験
条件である以上(ADR-025)、速度のためにそこを揺らさない。速度が問題になったら
バッチ幅を config に出し、人間が決める(skill code-style §1)。

**`model_input` は `code/chat_format.py` にある**(2026-08-27 に移した)。
訓練側(`code/train/data.py`)が同じ組み方を要求するためである(ADR-025 案 A)。
ここから import しているので `code.eval.generate.model_input` は今も引ける。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from code.chat_format import model_input
from code.eval.model import GenerationSettings, load_model_and_tokenizer

# プロンプト列 → 応答列。**同じ長さで、同じ順序**で返すことが規約である。
Generator = Callable[[Sequence[str]], list[str]]


class GeneratorContractError(RuntimeError):
    """生成関数が入力と違う本数の応答を返した。

    黙って通すと、項目と応答の対応が1つずれたまま4値分解が出る。
    ずれた採点は「モデルが変な答えを返した」ようにしか見えないため、
    ここで止める(CLAUDE.md §7「まずバグを疑う」)。
    """


def build_generator(settings: GenerationSettings) -> Generator:
    """重みを読み、プロンプト列 → 応答列 の関数を返す。

    答える問い: 「この設定で尋ねる、という操作を1つの関数にできるか」

    重みは**1度だけ**読む。返した関数を掃引の各 M で使い回すことで、
    M ごとにモデルを読み直して設定が揺れる余地を消す。
    """
    model, tokenizer = load_model_and_tokenizer(settings)

    def generator(prompts: Sequence[str]) -> list[str]:
        return [
            _generate_one(prompt, model=model, tokenizer=tokenizer, settings=settings)
            for prompt in prompts
        ]

    return generator


def _generate_one(
    prompt: str, *, model: Any, tokenizer: Any, settings: GenerationSettings
) -> str:
    """1プロンプトを生成する。返すのは**続きだけ**でプロンプトを含まない。

    `add_special_tokens` をテンプレート適用時に False にする理由は
    `infra/preflight.py` の `_token_boundary_record` と同じ —— chat_template が
    既に BOS を入れており、True にすると BOS が2つ乗る(PLAN-002 §4.1.4)。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`。冒頭で import しない

    text = model_input(prompt, tokenizer=tokenizer, chat_template=settings.chat_template)
    encoded = tokenizer(
        text, add_special_tokens=not settings.chat_template, return_tensors="pt"
    ).to(model.device)
    prompt_length = int(encoded["input_ids"].shape[-1])
    with torch.no_grad():
        output = model.generate(
            **encoded,
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.do_sample,
            temperature=settings.temperature if settings.do_sample else None,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(output[0][prompt_length:], skip_special_tokens=True)


def collect_responses(prompts: Sequence[str], generator: Generator) -> list[str]:
    """生成関数を呼び、本数が合っていることを確かめる。

    答える問い: 「返ってきた応答は、渡したプロンプトと1対1で対応しているか」

    **本実行と掃引はこの関数を通る。**生成関数を直に呼ばないのは、本数の
    検査を片方だけ忘れる余地を消すためである。
    """
    responses = list(generator(prompts))
    if len(responses) != len(prompts):
        raise GeneratorContractError(
            f"生成関数が {len(prompts)} 件のプロンプトに対し {len(responses)} 件の応答を返した。"
            "項目と応答の対応がずれた採点は結果として読めない。"
        )
    return responses
