"""順1b の2つの config が「まとめ幅だけ違う」ことを縛る(PLAN-004 §3 順1b の前提2 の (f))。

答える問い: 「`configs/smoke1b_b1.yaml` は、まとめ幅を変えたことの効果だけを
測れる写しになっているか」

**写しの取り違えは実機でしか出ず、GPU 時間を捨てる。**片方だけ数値域や項目表を
直すと、突き合わせは「まとめ幅の効果」ではなく「別の実行どうしの差」を見ている
ことになる —— そしてそれは、割れた応答を見るまで気づけない。

`configs/smoke.yaml` を触っていないことも合わせて縛る(ADR-037 決定4)。
**ここに出る数はすべて config の値であって実験結果ではない**(`CLAUDE.md` §2)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code.config import REPO_ROOT, load_config

SMOKE1B = REPO_ROOT / "configs" / "smoke1b.yaml"
SMOKE1B_B1 = REPO_ROOT / "configs" / "smoke1b_b1.yaml"
SMOKE = REPO_ROOT / "configs" / "smoke.yaml"

# **この2つ以外が違ってはならない。**id は run_dir を分けるため、batch_size は
# 測りたいものそのものである。
ALLOWED_DIFFERENCES = {("experiment", "id"), ("eval", "batch_size")}

# 本実験と同じ数値域(順1b の完了条件1。ADR-019 決定3 / PLAN-002 §4.2.1)。
TRAIN_DOMAIN = (1, 99)


def flatten(value: Any, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    """入れ子の dict を「鍵の道 -> 値」に開く。リストは葉として1つの値に扱う。"""
    if not isinstance(value, dict):
        return {prefix: value}
    flattened: dict[tuple[str, ...], Any] = {}
    for key, child in value.items():
        flattened.update(flatten(child, (*prefix, key)))
    return flattened


def test_the_two_smoke1b_configs_differ_in_exactly_two_places() -> None:
    left = flatten(load_config(SMOKE1B))
    right = flatten(load_config(SMOKE1B_B1))
    assert set(left) == set(right), "鍵の集合がずれている(片方にだけある項目がある)"
    differences = {key for key in left if left[key] != right[key]}
    assert differences == ALLOWED_DIFFERENCES, f"想定外の差: {differences - ALLOWED_DIFFERENCES}"


def test_the_batch_one_config_really_asks_one_at_a_time() -> None:
    assert load_config(SMOKE1B)["eval"]["batch_size"] > 1
    assert load_config(SMOKE1B_B1)["eval"]["batch_size"] == 1


def test_the_two_configs_write_to_different_run_dirs() -> None:
    """同じ experiment.id だと run_dir がぶつかり、突き合わせる2つが作れない。"""
    assert load_config(SMOKE1B)["experiment"]["id"] != load_config(SMOKE1B_B1)["experiment"]["id"]


def test_both_configs_use_the_real_experiment_domain() -> None:
    """完了条件1。`[1,9]^2` では桁が足りず `max_new_tokens` の材料にならない。"""
    for path in (SMOKE1B, SMOKE1B_B1):
        data = load_config(path)["data"]
        assert (data["train_domain_min"], data["train_domain_max"]) == TRAIN_DOMAIN


def test_the_smoke_config_is_left_untouched() -> None:
    """ADR-037 決定4。`model.name = null` は門の回帰テストが拠る固定点である。"""
    smoke = load_config(SMOKE)
    assert smoke["model"]["name"] is None
    assert (smoke["data"]["train_domain_min"], smoke["data"]["train_domain_max"]) != TRAIN_DOMAIN


def test_neither_smoke1b_config_declares_a_preregistered_tag() -> None:
    """順1b は実験ではない(ADR-037 決定5)。事前登録の対象外である。"""
    for path in (SMOKE1B, SMOKE1B_B1):
        assert load_config(path)["experiment"]["preregistered_tag"] is None
