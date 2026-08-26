"""明示リストから4群の評価項目を作るディスパッチャ。

答える問い: 「config に列挙された (群, a, b, ...) から、どの生成器を呼ぶか」

**ここでプールをサンプリングしない。**被覆層(id / interp / extrap)のセルを
どう埋めるかは未決定であり(ADR-033 決定4、`CLAUDE.md` §8)、外挿域の上限
`M*` が決まるまで `extrap` セルは原理的に埋まらない(PLAN-001 §4.1.1)。
決まるまでは項目を config に明示列挙する。

**2箇所から呼ばれる。**`code/eval/run.py` の `--dry-run`(`eval.dry_run_items`)と
`code/data_gen/eval_pool.py`(`eval.pool_items`)である。片方に複製すると、
群ごとの生成器のシグネチャの違い(下の表)が2箇所に散って必ずずれる。

| 群 | 生成器 | 参照規則の渡し方 | category |
|---|---|---|---|
| `comparison` | t3_comparison | 辞書 | config が指定 + `threshold_offset` |
| `bare_sum` | numeric_sum | 辞書 | 取らない(`t1` の1種類) |
| `word_problem` | numeric_sum | 辞書 | **内容のハッシュから決まる**(指定禁止) |
| `specificity` | specificity_control | **単体** | config が指定(規則名と同じ) |
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from code.config import ConfigError, require
from code.data_gen.battery_items import Item
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.lesion import Lesion


def entries_by_group(
    config: Mapping[str, Any], dotted_key: str
) -> dict[str, list[Mapping[str, Any]]]:
    """明示リストを `eval.batteries` の群ごとに仕分ける。

    答える問い: 「どの項目定義を、どの群の生成器に渡すか」

    **群は config に明示させる。**category から逆引きしない —— 逆引き表を
    もう1つ持つことになり、群と category の対応が2箇所に散る。
    `eval.batteries` に無い群の項目は**黙って捨てずに止める。**
    """
    by_group: dict[str, list[Mapping[str, Any]]] = {
        group: [] for group in require(config, "eval.batteries")
    }
    for entry in require(config, dotted_key):
        group = entry.get("group")
        if group not in by_group:
            raise ConfigError(
                f"{dotted_key} の項目の群 {group!r} が eval.batteries {sorted(by_group)} に無い。"
                "黙って捨てると項目数が静かに減る。"
            )
        by_group[group].append(entry)
    return by_group


def pair_of(entry: Mapping[str, Any]) -> tuple[int, int]:
    """明示リストの1件が指す順序対。"""
    return (entry["a"], entry["b"])


def build_items_from_entries(
    entries: Sequence[Mapping[str, Any]],
    group: str,
    *,
    pool_id: str,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> list[Item]:
    """明示リストの項目定義から、この群の項目を作る。

    答える問い: 「サンプリングの決定を待たずに、群ごとの経路を通せるか」

    群ごとに生成器のシグネチャが違うので分岐する(モジュール冒頭の表)。
    `specificity` に加算側の辞書を渡すと、減算項目に a + b + offset を
    突き合わせる取り違えになるので、参照規則は単体で引いて渡す(§4.6)。

    **`pool_id` は呼び出し側が1つ渡す。**項目ごとに書けるようにしない ——
    `item_id` にも T2 の場面テンプレートの割当にも `pool_id` が効く
    (PLAN-003 §4.3)ので、1つのプールに複数の `pool_id` が混ざると
    「同じ組は条件をまたいで同じ場面で尋ねられる」が成立しなくなる。
    """
    items: list[Item] = []
    for entry in entries:
        if "pool_id" in entry:
            raise ConfigError(
                f"項目 {dict(entry)!r} が pool_id を持っている。プール名は "
                "data.pool_id が1つだけ決める(item_id と T2 の場面割当に効くため)。"
            )
        pair = pair_of(entry)
        if group == t3_comparison.GROUP:
            items.extend(
                t3_comparison.build_items(
                    [pair],
                    pool_id=pool_id,
                    category=entry["category"],
                    threshold_offset=entry["threshold_offset"],
                    reference_lesions=lesions,
                )
            )
        elif group == numeric_sum.GROUP_BARE_SUM:
            items.extend(
                numeric_sum.build_bare_sum_items([pair], pool_id=pool_id, reference_lesions=lesions)
            )
        elif group == numeric_sum.GROUP_WORD_PROBLEM:
            if "category" in entry:
                raise ConfigError(
                    f"群 {group!r} の項目に category を書かない。場面テンプレートは "
                    "(pool_id, a, b) のハッシュから決まる(PLAN-003 §4.3)。config で"
                    "上書きできると、条件間・シード間で割当が一致するという保証が消える。"
                )
            items.extend(
                numeric_sum.build_word_problem_items(
                    [pair], pool_id=pool_id, reference_lesions=lesions
                )
            )
        elif group == specificity_control.GROUP:
            category = entry["category"]
            reference_lesion = specificity_lesions[specificity_control.reference_rule_for(category)]
            items.extend(
                specificity_control.build_items(
                    [pair], pool_id=pool_id, category=category, reference_lesion=reference_lesion
                )
            )
        else:
            raise ConfigError(f"群 {group!r} の項目生成は未実装")
    return items
