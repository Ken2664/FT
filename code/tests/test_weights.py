"""重みの読み込み(code/weights.py)のテスト。

答える問い: 「どの dtype で読むかの宣言を、実在する dtype に解決できるか」

**重みは1度も読まない。**`load_causal_lm` は GPU と重みを要求するので
テストしない(`code/eval/model.py` の `load_model_and_tokenizer` と同じ扱い)。
ここで検査するのは、その手前にある dtype の解決だけである。
"""

from __future__ import annotations

import pytest

from code.config import ConfigError
from code.weights import resolve_dtype


def test_dtype_name_is_resolved() -> None:
    """dtype 名が torch の dtype に解決すること。"""
    torch = pytest.importorskip("torch")
    assert resolve_dtype("bfloat16") is torch.bfloat16


def test_non_dtype_attribute_is_rejected() -> None:
    """★torch にある「dtype でない属性」を通さない。

    getattr(torch, "load") は関数を返す。from_pretrained に渡すと読み込みの
    奥で分かりにくく落ちる。
    """
    pytest.importorskip("torch")
    with pytest.raises(ConfigError, match="dtype"):
        resolve_dtype("load")
