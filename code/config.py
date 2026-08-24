"""config の読み込みと必須項目の取り出し。

答える問い: 「この実行に必要な決定は、すべて済んでいるか」

`code/eval/run.py` にあった3つを層に依らない場所へ出したもの。
`code/data_gen/` と `code/eval/` の両方が使うため、片方に置くと
層をまたぐ import が生まれる(skill code-style §2)。

**既定値を作らない。**null は「まだ決めていない」であって
「良きに計らえ」ではない(configs/template.yaml の冒頭)。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """config が未決定の項目を含んでいる、または矛盾している。"""


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require(config: Mapping[str, Any], dotted_key: str) -> Any:
    """config の必須項目を取り出す。null なら止める。

    答える問い: 「この実行に必要な決定は、すべて済んでいるか」

    既定値を作らない(skill code-style §5)。
    """
    node: Any = config
    for key in dotted_key.split("."):
        if not isinstance(node, Mapping) or key not in node:
            raise ConfigError(f"config に {dotted_key} が無い")
        node = node[key]
    if node is None:
        raise ConfigError(
            f"config の {dotted_key} が null(未決定)である。"
            "値は PLAN か ADR で決めてから実行すること。ここで既定値は作らない。"
        )
    return node
