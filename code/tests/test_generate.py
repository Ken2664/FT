"""生成関数(code/eval/generate.py)のテスト。

答える問い: 「GPU の無い環境で、生成の経路を差し替えて検査できるか」

**モデルの重みは1度も読まない**(PLAN-004 §4.3 の1)。`build_generator` と
`_generate_batch` は重みを要求するのでテストしない。ここで固定するのは
「差し替え可能であること」「本数の契約」、および**まとめ生成の切り方**
——バッチ分割・順序の保存・端数——である。まとめ生成は 2026-08-28 に
入れた(PLAN-004 §3 順1b の「前提」(b))。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from code.eval.generate import (
    Generator,
    GeneratorContractError,
    batched_generator,
    collect_responses,
    model_input,
    split_into_batches,
)


class RecordingTokenizer:
    """apply_chat_template の呼ばれ方だけを記録する偽トークナイザ。

    答える問い: 「テンプレートの適用の仕方は preflight の検査7 と同じか」
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def apply_chat_template(
        self, messages: Sequence[dict[str, str]], **kwargs: Any
    ) -> str:
        self.calls.append({"messages": list(messages), **kwargs})
        return f"<template>{messages[0]['content']}"


def echo_generator(prompts: Sequence[str]) -> list[str]:
    """プロンプトをそのまま返す差し替え生成器。"""
    return [f"echo: {prompt}" for prompt in prompts]


def test_a_plain_function_satisfies_the_generator_protocol() -> None:
    """★生成関数は差し替え可能である(GPU も重みも要らない)。"""
    generator: Generator = echo_generator
    assert collect_responses(["a", "b"], generator) == ["echo: a", "echo: b"]


def test_responses_keep_the_prompt_order() -> None:
    """★応答はプロンプトと同じ順序で返る。

    順序が入れ替わると、項目と応答の対応がずれたまま採点される。
    ずれた採点は「モデルが変な答えを返した」ようにしか見えない。
    """
    prompts = [f"q{i}" for i in range(5)]
    responses = collect_responses(prompts, lambda given: [f"a{p[1:]}" for p in given])
    assert responses == ["a0", "a1", "a2", "a3", "a4"]


@pytest.mark.parametrize("returned", [[], ["one"], ["one", "two", "three"]])
def test_a_wrong_number_of_responses_stops_the_run(returned: list[str]) -> None:
    """★本数が合わない生成関数は例外で止まる(CLAUDE.md §7)。"""
    with pytest.raises(GeneratorContractError, match="2 件のプロンプト"):
        collect_responses(["a", "b"], lambda _: list(returned))


def test_model_input_is_the_prompt_when_the_template_is_off() -> None:
    """chat_template=false ならプロンプトがそのまま入力になる。"""
    tokenizer = RecordingTokenizer()
    assert model_input("3+4=", tokenizer=tokenizer, chat_template=False) == "3+4="
    assert tokenizer.calls == []


def test_model_input_applies_the_chat_template() -> None:
    """★chat_template=true なら user ロール1件を生成プロンプト付きで通す。

    ADR-025 案 A(FT も評価も全項目をテンプレートに通す)の実装側。
    適用の仕方は infra/preflight.py の検査7 と**同じ形**でなければならない
    —— 片方だけ add_generation_prompt を変えると、境界を測った文字列と
    実際に生成させる文字列が別物になる。
    """
    tokenizer = RecordingTokenizer()
    text = model_input("3+4=", tokenizer=tokenizer, chat_template=True)
    assert text == "<template>3+4="
    (call,) = tokenizer.calls
    assert call["messages"] == [{"role": "user", "content": "3+4="}]
    assert call["tokenize"] is False
    assert call["add_generation_prompt"] is True


# --------------------------------------------------------------------------
# まとめ生成(2026-08-28 に追加。PLAN-004 §3 順1b の「前提」(b))
# --------------------------------------------------------------------------


class RecordingBatchGenerator:
    """受け取ったバッチをそのまま記録する偽の1バッチ生成器。

    答える問い: 「まとめ幅で切って尋ねたとき、モデルには何が何回渡るか」

    応答はプロンプトから一意に決まる文字列にしてある。並べ直しがずれれば
    最終的な列が元のプロンプト順と食い違う。
    """

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def __call__(self, prompts: Sequence[str]) -> list[str]:
        self.batches.append(list(prompts))
        return [f"answer({prompt})" for prompt in prompts]


@pytest.mark.parametrize(
    ("n_prompts", "batch_size", "expected_widths"),
    [
        (8, 4, [4, 4]),        # 割り切れる
        (11, 4, [4, 4, 3]),    # ★端数が出る(configs/smoke1b.yaml の T2 がこれ)
        (3, 5, [3]),           # 幅より本数が少ない
        (5, 1, [1, 1, 1, 1, 1]),  # バッチ1(2026-08-28 まではこれしか無かった)
        (0, 4, []),            # 空の列
    ],
)
def test_prompts_are_split_at_the_declared_width(
    n_prompts: int, batch_size: int, expected_widths: list[int]
) -> None:
    """★宣言した幅で切れ、**端数のバッチを落とさない。**"""
    prompts = [f"q{i}" for i in range(n_prompts)]
    batches = split_into_batches(prompts, batch_size)
    assert [len(batch) for batch in batches] == expected_widths


@pytest.mark.parametrize("batch_size", [1, 2, 3, 4, 7, 19, 20])
def test_the_split_can_be_put_back_together(batch_size: int) -> None:
    """★連結すると元のプロンプト列に戻る(1件も落ちず、順序も変わらない)。

    `collect_responses` は**本数しか見ない**ので、取り違えや入れ替わりは
    そこを素通りする。切り方の側で固定しておく必要がある。
    """
    prompts = [f"q{i}" for i in range(19)]
    flattened = [prompt for batch in split_into_batches(prompts, batch_size) for prompt in batch]
    assert flattened == prompts


def test_the_batched_generator_asks_in_batches() -> None:
    """★まとめ生成器はプロンプトを幅ごとにまとめてモデルへ渡す。

    2026-08-28 まで1件ずつ渡していた。段階 C の評価プールは 10,760 項目
    (PLAN-001 §5.1)で、1件ずつでは順6 が現実的な GPU 時間に収まらない。
    """
    recorder = RecordingBatchGenerator()
    generator: Generator = batched_generator(recorder, 4)
    generator([f"q{i}" for i in range(11)])
    assert recorder.batches == [
        ["q0", "q1", "q2", "q3"],
        ["q4", "q5", "q6", "q7"],
        ["q8", "q9", "q10"],
    ]


def test_the_batched_generator_keeps_the_prompt_order() -> None:
    """★応答はバッチをまたいでもプロンプトの順序で返る。

    ここがずれると、項目と応答の対応がずれたまま4値分解が出る。本数は
    合っているので `collect_responses` では捕まらない。
    """
    prompts = [f"q{i}" for i in range(11)]
    responses = batched_generator(RecordingBatchGenerator(), 4)(prompts)
    assert responses == [f"answer({prompt})" for prompt in prompts]


def test_the_final_short_batch_is_not_dropped() -> None:
    """★端数のバッチの応答も返る(本数が合う)。"""
    prompts = [f"q{i}" for i in range(11)]
    responses = collect_responses(prompts, batched_generator(RecordingBatchGenerator(), 4))
    assert len(responses) == len(prompts)
    assert responses[-1] == "answer(q10)"


def test_a_batch_width_of_one_asks_one_prompt_at_a_time() -> None:
    """★`batch_size: 1` は 2026-08-28 までの1件ずつの経路と同じ渡し方になる。

    経路を1本にしてあるので、バッチ1とバッチ N の比較(承認待ち #25)は
    同じコードに対して取れる。
    """
    recorder = RecordingBatchGenerator()
    batched_generator(recorder, 1)(["a", "b", "c"])
    assert recorder.batches == [["a"], ["b"], ["c"]]


def test_a_batch_generator_that_drops_a_response_stops_the_run() -> None:
    """★1バッチが本数を落としたら、まとめても本数が合わず止まる。

    バッチの中で応答が消えるのは、パディングや切り出しの取り違えで起きうる。
    黙って通すと以降の項目がすべて1つずれる(CLAUDE.md §7)。
    """

    def drops_the_last(prompts: Sequence[str]) -> list[str]:
        return [f"answer({prompt})" for prompt in prompts][:-1]

    with pytest.raises(GeneratorContractError, match="11 件のプロンプト"):
        collect_responses([f"q{i}" for i in range(11)], batched_generator(drops_the_last, 4))
