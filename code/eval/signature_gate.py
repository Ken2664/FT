"""凍結の前に署名を見ない門(PLAN-037 D9。ADR-116 決定3 / ADR-118)。

答える問い: 「この run は、事前登録の凍結の前に `p2`・`p2d` などで T1c・スケールの掃引を回す
取り違えではないか」

**何を止めるか**: T1c(合成の探り)と LoRA のスケール s ≠ 1 の run は、署名(H0-A / H1 の割れ方、
用量反応)を直接読む測定である。凍結の前に `p2`・`p2d` のアダプタで見ると、署名を見てから
設計を決められる(ADR-116 決定3)。1 回の取り違えが取り返せないので、手順だけでなく**コードで止める**。

**通すもの**:
  - アダプタを読まない run(`model.adapter` が null。素のモデルの適格性の確認)
  - アダプタの条件が `ident` の run(署名の無い対照。配線確認に使う)
  - config が宣言した事前登録の tag(`eval.freeze_tag`)が git に在るとき(凍結の後)

**止める条件はそれ以外すべて**(宣言が null / tag が git に無い)。アダプタの条件は
`code.eval.run.adapter_provenance` が訓練 run の記録と `lesion.condition` の一致まで見て返す
(ここでは再検査しない)。

**S6 の config に tag の欄が 1 つ増える**(`eval.freeze_tag`。凍結の場で人間が決める名前。
コードに既定値を作らない。skill code-style §5)。git を実行できないときは止める側に倒れる。
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from typing import Any

from code.artifacts import REPO_ROOT
from code.config import ConfigError

FREEZE_TAG_KEY = "eval.freeze_tag"
IDENT_CONDITION = "ident"

# 門を通した理由。metrics.json に残す(後から「なぜ回せたか」を言えるように)。
REASON_BASE_MODEL = "base_model"
REASON_IDENT_ADAPTER = "ident_adapter"
REASON_FROZEN = "frozen_tag_present"


def git_tag_exists(tag: str) -> bool:
    """この repo に `tag` が在るか。git を実行できなければ False(止める側に倒れる)。

    答える問い: 「事前登録の tag は、この作業ツリーの git に在るか」
    """
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", "-C", str(REPO_ROOT), "tag", "--list", tag],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0 and tag in completed.stdout.split()


def declared_freeze_tag(config: Mapping[str, Any]) -> str | None:
    """`eval.freeze_tag`(null / 無し = 宣言なし)。壊れた値は止める。"""
    tag = (config.get("eval") or {}).get("freeze_tag")
    if tag is None:
        return None
    if not isinstance(tag, str) or not tag:
        raise ConfigError(f"{FREEZE_TAG_KEY} は事前登録の tag の名前(文字列)か null である: {tag!r}")
    return tag


def check_signature_gate(
    config: Mapping[str, Any],
    *,
    adapter: str | None,
    condition: str,
    what: str,
    tag_exists: Callable[[str], bool] = git_tag_exists,
) -> dict[str, Any]:
    """T1c・s ≠ 1 の run を回してよいかを確かめ、通した理由を返す。

    答える問い: 「この署名を読む測定は、凍結の前に走らせてよい run か」

    `adapter` は `model.adapter` の宣言(null = 読まない)、`condition` は `lesion.condition`。
    `what` は止めるときに名指しする測定の名前(「T1c」・「スケールの掃引(s≠1)」)。
    **重みを読む前・run ディレクトリを作る前に呼ぶ。**
    """
    if adapter is None:
        return {"gate": REASON_BASE_MODEL, "freeze_tag": None}
    if condition == IDENT_CONDITION:
        return {"gate": REASON_IDENT_ADAPTER, "freeze_tag": None}
    tag = declared_freeze_tag(config)
    if tag is None:
        raise ConfigError(
            f"{what} を条件 {condition!r} のアダプタで回そうとしている。凍結の前に署名を見る取り違えを"
            f"防ぐため、`ident` 以外のアダプタでは {FREEZE_TAG_KEY}(事前登録の tag)の宣言が要る"
            "(ADR-116 決定3 / PLAN-037 D9)。凍結の前は素のモデルか `ident` だけで回す。"
        )
    if not tag_exists(tag):
        raise ConfigError(
            f"{what} を条件 {condition!r} のアダプタで回そうとしているが、{FREEZE_TAG_KEY}={tag!r} の"
            "tag が git に無い(凍結していない。git を実行できなかった場合も止める)。"
            "事前登録の tag を打った後にだけ回す(ADR-116 決定3 / PLAN-037 D9)。"
        )
    return {"gate": REASON_FROZEN, "freeze_tag": tag}
