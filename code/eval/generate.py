"""プロンプト列 → 応答列。**生成はここ1箇所に集める**(PLAN-004 §4.3 の1)。

答える問い: 「この項目をモデルに尋ねると、どんな文字列が返るか」

`code/eval/run.py`(本実行)と `code/eval/sweep.py`(桁数掃引)が**同じ関数**を
呼ぶ。2箇所で別々に生成すると、掃引と本実行で生成設定が食い違っても
誰も気づかない —— そのとき外挿域の上限 M* は、本実験とは違う設定で測った
correct_rate から決まってしまう。

**差し替え可能にしてある。**`Generator` は「プロンプト列を受け取り、同じ
長さの応答列を返す」だけの呼び出し可能オブジェクトである。テストは固定
応答を返す関数を渡す。GPU もモデルの重みも要らない(PLAN-004 §4.3 の1)。

**まとめて生成する。**幅は `eval.batch_size`(config 必須。null は
`ConfigError`)。2026-08-28 まで1件ずつ尋ねていたが、段階 C の評価プールは
10,760 項目(PLAN-001 §5.1)であり、それでは順6 が現実的な GPU 時間に
収まらない(PLAN-004 §3 順1b の「前提」(b))。

**まとめ生成は数値を動かしうる。**decoder-only の一括生成は左パディングを
要求し、同じプロンプトでもバッチの構成によって最終トークンが割れうる
(貪欲デコードの同点)。だから幅は**速度の都合ではなく実験装置の設定**として
扱い、config に出し、`metrics.json` に残し、条件間で揃える
(ADR-025 / infra/RUNPOD.md §6)。**値そのものは人間が決める**(承認待ち #25)。
**バッチ1とバッチ N が同じ応答を返すかは実機で1度確かめる**(順1b)。

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


def split_into_batches(prompts: Sequence[str], batch_size: int) -> list[list[str]]:
    """プロンプト列を宣言された幅で切る。**端数のバッチを落とさない。**

    答える問い: 「この本数を、宣言した幅で何回に分けて尋ねるか」

    切り出しは順序を保ち、連結すると元の列に戻る。ここが崩れると項目と
    応答の対応がずれたまま4値分解が出る —— `collect_responses` は**本数
    しか見ない**ので、入れ替わりや取り違えはそこを素通りする。

    `batch_size` を再検査しない。幅の門は `code/eval/model.py` の
    `require_batch_size` 1箇所である(生成の仕方に関する門を2つ置かない)。
    """
    return [
        list(prompts[start : start + batch_size])
        for start in range(0, len(prompts), batch_size)
    ]


def batched_generator(generate_batch: Generator, batch_size: int) -> Generator:
    """1バッチを生成する関数を、プロンプト列全体を受ける生成関数にする。

    答える問い: 「宣言した幅で切って尋ね、元の順序のまま返せるか」

    `generate_batch` は `Generator` と同じ契約(同じ長さ・同じ順序)を満たす。
    違いは**受け取る本数が `batch_size` 以下である**ことだけである。

    **重みを読まない。**バッチの切り方と並べ直しだけをここに置いてあるので、
    GPU の無い環境でも `generate_batch` を差し替えて検査できる
    (PLAN-004 §4.3 の1)。
    """

    def generator(prompts: Sequence[str]) -> list[str]:
        responses: list[str] = []
        for batch in split_into_batches(prompts, batch_size):
            responses.extend(generate_batch(batch))
        return responses

    return generator


def build_generator(settings: GenerationSettings) -> Generator:
    """重みを読み、プロンプト列 → 応答列 の関数を返す。

    答える問い: 「この設定で尋ねる、という操作を1つの関数にできるか」

    重みは**1度だけ**読む。返した関数を掃引の各 M で使い回すことで、
    M ごとにモデルを読み直して設定が揺れる余地を消す。

    まとめ幅は `eval.batch_size` である。**`batch_size: 1` は 2026-08-28 まで
    の1件ずつの経路と同じ入力を作る** —— 行が1本なら `padding=True` でも
    パッドが入らないためである。経路を1本にしてあるので、バッチ1と
    バッチ N の比較(承認待ち #25)は同じコードに対して取れる。
    """
    model, tokenizer = load_model_and_tokenizer(settings)

    def generate_batch(prompts: Sequence[str]) -> list[str]:
        return _generate_batch(prompts, model=model, tokenizer=tokenizer, settings=settings)

    return batched_generator(generate_batch, settings.batch_size)


def _generate_batch(
    prompts: Sequence[str], *, model: Any, tokenizer: Any, settings: GenerationSettings
) -> list[str]:
    """1バッチをまとめて生成する。返すのは**続きだけ**でプロンプトを含まない。

    答える問い: 「このバッチのプロンプトに、モデルは何を続けたか」

    **左パディングでなければならない。**decoder-only の生成は入力の右端から
    続きを書く。右パディングだと短いプロンプトの続きがパッド列の後ろに
    書かれ、応答が壊れる。パディング側と `pad_token` は
    `code/eval/model.py` の `prepare_tokenizer_for_batched_generation` が
    トークナイザに固定してある。

    左パディングだと**バッチ内の全行で入力長が揃う**ので、`prompt_length`
    という1つの位置で全行から続きだけを切り出せる。

    `add_special_tokens` をテンプレート適用時に False にする理由は
    `infra/preflight.py` の `_token_boundary_record` と同じ —— chat_template が
    既に BOS を入れており、True にすると BOS が2つ乗る(PLAN-002 §4.1.4)。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`。冒頭で import しない

    texts = [
        model_input(prompt, tokenizer=tokenizer, chat_template=settings.chat_template)
        for prompt in prompts
    ]
    encoded = tokenizer(
        texts,
        add_special_tokens=not settings.chat_template,
        return_tensors="pt",
        padding=True,
    ).to(model.device)
    prompt_length = int(encoded["input_ids"].shape[-1])
    with torch.no_grad():
        output = model.generate(
            **encoded,
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.do_sample,
            temperature=settings.temperature if settings.do_sample else None,
            pad_token_id=tokenizer.pad_token_id,
        )
    return [
        tokenizer.decode(row[prompt_length:], skip_special_tokens=True) for row in output
    ]


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
