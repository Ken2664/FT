"""書式ブロック(code/data_gen/prompt_format.py)のユニットテスト。

答える問い: PLAN-002 §4.8.1 検査6「訓練と評価が、同じ1文字単位の書式を
使っているか」を、コードの側で言えるようにできているか。

ここで固定する最重要の性質:
  - **訓練側の manifest と評価側のブロックが同じ format_hash を出す。**
    ずれると preflight は「書式が違う」と報告するが、実際に違うのは実装であり、
    **検査が嘘をつく**
  - **format_hash は中身から決まる。**手で書き換えた記録は validate が弾く
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from code.config import ConfigError
from code.data_gen import prompt_format
from code.data_gen.ft_data import generate
from code.tests.test_ft_data import SMALL_CONFIG


def test_build_fills_every_field_of_the_schema() -> None:
    """PLAN-002 §4.8 の schema と同形であること。"""
    block = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
    )
    assert set(block) == set(prompt_format.FIELDS)
    # 7規約は config から動かせない(モジュール冒頭の注記)。
    for field, value in prompt_format.FIXED_FIELDS.items():
        assert block[field] == value


def test_format_hash_is_reproducible_from_the_block() -> None:
    """記録値を信じずに再計算できる(検査6 の「記録が古いこと自体を検出する」)。"""
    block = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
    )
    assert block["format_hash"] == prompt_format.format_hash_of(block)


def test_a_different_surface_gives_a_different_hash() -> None:
    """書式が1文字でも違えばハッシュが違う(§4.1.1 の7規約が測れている)。"""
    tight = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
    )
    spaced = prompt_format.build(
        prompt_template="{a} + {b} = ", completion_template="{target}", chat_template=True
    )
    templated = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=False
    )
    assert tight["format_hash"] != spaced["format_hash"]
    assert tight["format_hash"] != templated["format_hash"]


def test_build_from_config_refuses_an_undecided_format() -> None:
    """null は「まだ決めていない」であって「良きに計らえ」ではない。"""
    config: dict[str, Any] = copy.deepcopy(SMALL_CONFIG)
    config["data"]["chat_template"] = None
    with pytest.raises(ConfigError):
        prompt_format.build_from_config(config)


# --------------------------------------------------------------------------
# ★訓練側と評価側の一致(検査6 の前提)
# --------------------------------------------------------------------------


def test_training_manifest_and_the_evaluation_anchor_share_one_hash() -> None:
    """★FT データの manifest と評価アンカーのブロックが一致すること。

    この一致が崩れると infra/preflight.py の検査6 は「訓練と評価で書式が
    違う」と報告する。**実際に違うのは実装である。**書式ブロックの構成を
    1箇所(prompt_format.build)に置いた理由そのものをここで固定する。
    """
    dataset = generate(copy.deepcopy(SMALL_CONFIG))
    anchor = prompt_format.build_from_config(SMALL_CONFIG)
    assert dataset.manifest["prompt_format"] == anchor
    assert dataset.manifest["prompt_format"]["format_hash"] == anchor["format_hash"]


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------


def test_validate_rejects_a_missing_field() -> None:
    """欠けたブロックは preflight から見ると「書式が違う」に化ける。"""
    block = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
    )
    del block["packing"]
    with pytest.raises(ValueError, match="packing"):
        prompt_format.validate(block)


def test_validate_rejects_an_unknown_field() -> None:
    """同形でないブロックは format_hash が一致しなくなる。"""
    block = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
    )
    block["note"] = "評価用"
    with pytest.raises(ValueError, match="未知のフィールド"):
        prompt_format.validate(block)


def test_validate_rejects_a_stale_hash() -> None:
    """★prompt_format を手で書き換えても format_hash は追随しない。"""
    block = prompt_format.build(
        prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
    )
    block["whitespace"] = "single"
    with pytest.raises(ValueError, match="format_hash"):
        prompt_format.validate(block)


def test_validate_accepts_a_freshly_built_block() -> None:
    prompt_format.validate(
        prompt_format.build(
            prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
        )
    )
