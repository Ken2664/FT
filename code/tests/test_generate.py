"""生成関数(code/eval/generate.py)のテスト。

答える問い: 「GPU の無い環境で、生成の経路を差し替えて検査できるか」

**モデルの重みは1度も読まない**(PLAN-004 §4.3 の1)。`build_generator` と
`_generate_one` は重みを要求するのでテストしない。ここで固定するのは
「差し替え可能であること」と「本数の契約」である。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from code.eval.generate import (
    Generator,
    GeneratorContractError,
    collect_responses,
    model_input,
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
