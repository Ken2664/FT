"""run ごとにプールの一部だけを解く宣言(`eval.task_subset`。PLAN-026 I8)。

答える問い: 「この run は、プールのどのタスク型の項目を解き、どれを解かないか」

正本は ADR-082(提案 エージェント / 採択 人間。2026-09-16)。実装の読みは PLAN-026 §4.8。
**★2026-09-24 に ADR-099 決定5 (i-a) で門を 1 つ改めた**(特異性対照、下の最後の項目)。

  - **鍵**: `eval.task_subset` = 解くタスク型の名前のリスト(`t1` / `t1_instructed` / `t2` /
    `t3` / `t1b`)。**無い / null = 絞りなし**(プールの群と `eval.batteries` が一致することを
    要求する今までの門がそのまま掛かる)
  - **なぜ要るか**: 順6b の ① の run は 5 群のうち 3 群(比較・T1・T2)、(d) の run は比較群の
    T1b だけを解く(PLAN-026 §3 の表)。プールは 1 つ(パイロット用プール・S の掃引プール)で、
    **プールを作り直さずに** run ごとに解く部分を宣言する
  - **タスク型は主軸の要因水準そのもの**(ADR-026)。名前の表は作らず、`numeric_sum` と
    `t3_comparison` の `CATEGORY_AXES` から引く(`code/analysis/frame.py` の `task_type_of` と
    同じ作法。写しを作ると水準が 2 か所に分かれる)
  - **特異性対照はタスク型を持たない**(加算ではない。`frame.OFF_MAIN_AXIS`)。絞りでは選べず、
    `eval.batteries` から外すことで解かない群になる
  - ~~絞りを宣言した config は `eval.batteries` に特異性対照を置けない~~(ADR-082 決定1)
    **→ ★2026-09-24(ADR-099 決定5 (i-a))置ける。特異性対照は絞りの対象外で、置けばプールにある
    全件を解く**(探索的パイロット FT の評価は比較群だけを外し、T1・T2・特異性対照を解く。PLAN-031 §3.4)。
    全件を解いたことは `subset_record` の `solved_whole` 欄と `log.txt` に残る。
    **置かない run(順6b の ①・(d)・S-(d))の項目と文面は 1 バイトも変わらない**(`test_task_subset.py`)

**外した群・タスク型と件数は必ず記録する**(`subset_record`)。黙って項目数が減るのを防ぐのが
`eval.batteries` の門の役目であり、この宣言はその門を**開ける**ものだからである。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from code.config import ConfigError
from code.data_gen.battery_items import Item
from code.eval.battery import numeric_sum, specificity_control, t3_comparison

TASK_SUBSET_KEY = "eval.task_subset"

# タスク型を持たない群(絞りの対象外。置けば全件を解く。ADR-099 決定5 (i-a))。
UNTYPED_GROUPS: tuple[str, ...] = (specificity_control.GROUP,)

# 明示リストの鍵(`code/eval/run.py` の `dry_run_items_by_group`)。絞りと同時には宣言できない。
# **同じ文字列が `code/eval/run.py` の `DRY_RUN_ITEMS_KEY` にもある**(そちらは dry-run の
# 報告の `items_source` の名札)。循環 import を避けるために書き写してあり、食い違えば
# `code/tests/test_task_subset.py` が落ちる。
DRY_RUN_ITEMS_KEY = "eval.dry_run_items"

# metrics.json の task_subset 欄に添える注記。
SUBSET_NOTE = (
    "この run はプールの一部だけを解いている(宣言は eval.task_subset。PLAN-026 I8)。"
    "外した項目はモデルに1度も渡していない。pool.n_items は解いた件数であり、"
    "pool.items_sha256 はプールのファイル全体の畳み値なので絞りでは変わらない。"
    "タスク型を持たない群(特異性対照)は絞りの対象外で、eval.batteries に置けば全件を解く"
    "(ADR-099 決定5。solved_whole 欄)。"
    "**この欄が null の run はプール全体を解いている。**"
)


def task_types_by_group() -> dict[str, str]:
    """実装済みのタスク型 -> その群。**表を作らず `CATEGORY_AXES` から引く。**

    答える問い: 「`eval.task_subset` に書いてよい名前は何で、その項目はどの群に居るか」
    """
    mapping = {
        numeric_sum.task_type_of(category): numeric_sum.group_of(category)
        for category in numeric_sum.CATEGORY_AXES
    }
    for category in t3_comparison.CATEGORY_AXES:
        mapping[t3_comparison.task_type_of(category)] = t3_comparison.GROUP
    return mapping


def task_type_of_item(item: Item) -> str | None:
    """この項目のタスク型。特異性対照は**持たない**(None)。

    答える問い: 「この項目は、絞りのどの水準か」

    未知の category では止める(`frame.task_type_of` と同じ)。素通しすると、綴りを間違えた
    水準の項目が黙って「解かない側」に落ちる。
    """
    if item.category in numeric_sum.CATEGORY_AXES:
        return numeric_sum.task_type_of(item.category)
    if item.category in t3_comparison.CATEGORY_AXES:
        return t3_comparison.task_type_of(item.category)
    if item.category in specificity_control.CATEGORIES:
        return None
    raise ConfigError(f"未知の category: {item.category!r}(項目 {item.item_id})")


def declared_task_subset(config: Mapping[str, Any]) -> tuple[str, ...] | None:
    """この config が宣言した「解くタスク型」。宣言が無ければ None。

    答える問い: 「この run はプール全体を解くか、宣言した一部だけか」

    **重みを読む前に呼ぶ。**壊れた宣言(リストでない・空・文字列でない要素・重複・未知の名前)と、
    明示リスト(`eval.dry_run_items`)との同時宣言で止める —— 明示リストの項目は絞りを通らないので、
    宣言と実際に解く項目が黙って食い違う(PLAN-026 §4.8 読み8)。
    """
    names = (config.get("eval") or {}).get("task_subset")
    if names is None:
        return None
    if not isinstance(names, list) or not names:
        raise ConfigError(
            f"{TASK_SUBSET_KEY} は解くタスク型の名前のリスト(1 つ以上)か null である: {names!r}"
        )
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{TASK_SUBSET_KEY} の要素は空でない文字列である: {name!r}")
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise ConfigError(f"{TASK_SUBSET_KEY} に同じタスク型が重なっている: {duplicated}")
    known = task_types_by_group()
    unknown = sorted(set(names) - set(known))
    if unknown:
        raise ConfigError(
            f"{TASK_SUBSET_KEY} に未知のタスク型 {unknown} がある。あるのは {sorted(known)}"
        )
    if (config.get("eval") or {}).get("dry_run_items") is not None:
        raise ConfigError(
            f"{TASK_SUBSET_KEY} と {DRY_RUN_ITEMS_KEY} は同時に宣言できない。"
            "明示リストの項目は絞りを通らないので、宣言と解く項目が黙って食い違う"
            "(PLAN-026 §4.8 読み8)。"
        )
    return tuple(names)


def check_declaration(task_types: Sequence[str], batteries: Sequence[str]) -> None:
    """宣言と `eval.batteries` が噛み合っているかを両方向で見る(重みを読む前)。

    答える問い: 「この run が解くと宣言した群とタスク型は、互いに矛盾していないか」

      - 宣言したタスク型の群が `eval.batteries` に無い —— その型は 1 件も解かれない
      - `eval.batteries` の群に宣言したタスク型が 1 つも無い —— その群を解くと書いて解かない
        (**タスク型を持たない群 = 特異性対照は除く**。絞りの対象外で、置けば全件を解く)
      - ~~特異性対照はタスク型を持たないので、絞りを宣言した config では `eval.batteries` に置けない~~
        (ADR-082 決定1。**★2026-09-24 ADR-099 決定5 (i-a) で外した**)
    """
    groups = task_types_by_group()
    outside = sorted({task for task in task_types if groups[task] not in batteries})
    if outside:
        raise ConfigError(
            f"{TASK_SUBSET_KEY} のタスク型 {outside} の群が eval.batteries {list(batteries)} に無い"
            f"(それぞれの群は { {task: groups[task] for task in outside} })。"
            "解く群は eval.batteries、その中で解くタスク型は eval.task_subset で宣言する。"
        )
    empty = [
        group
        for group in batteries
        if group not in UNTYPED_GROUPS
        and not any(groups[task] == group for task in task_types)
    ]
    if empty:
        raise ConfigError(
            f"eval.batteries の群 {empty} に、{TASK_SUBSET_KEY} が宣言したタスク型が 1 つも無い。"
            "その群を解くと宣言して 1 件も解かない形になる。"
        )


def select_task_subset(
    items: Sequence[Item], task_types: Sequence[str], batteries: Sequence[str]
) -> list[Item]:
    """この run が解く項目(宣言した群 × 宣言したタスク型)。並びはプールの並びのまま。

    **タスク型を持たない項目(特異性対照)は、群が `eval.batteries` にあれば全件を解く**
    (絞りの対象外。ADR-099 決定5 (i-a))。
    """
    declared = set(task_types)
    return [
        item
        for item in items
        if item.group in batteries
        and (task_type_of_item(item) is None or task_type_of_item(item) in declared)
    ]


def check_selected(task_types: Sequence[str], solved: Sequence[Item]) -> None:
    """宣言したタスク型がプールに 1 件も無ければ止める(重みを読む前)。

    答える問い: 「宣言した水準は、このプールに本当に居るか」

    黙って通すと、綴りの違う水準を宣言した run が「その水準を解いた」顔で残る。
    """
    present = {task_type_of_item(item) for item in solved}
    missing = [task for task in task_types if task not in present]
    if missing:
        raise ConfigError(
            f"{TASK_SUBSET_KEY} が宣言したタスク型 {missing} の項目がプールに 1 件も無い。"
        )


def dropped_counts(items: Sequence[Item], solved: Sequence[Item]) -> list[dict[str, Any]]:
    """解かなかった項目の (群, タスク型) ごとの件数。タスク型を持たない群は `task_type: null`。"""
    solved_ids = {item.item_id for item in solved}
    counts: dict[tuple[str, str | None], int] = {}
    for item in items:
        if item.item_id in solved_ids:
            continue
        key = (item.group, task_type_of_item(item))
        counts[key] = counts.get(key, 0) + 1
    def sort_key(entry: tuple[tuple[str, str | None], int]) -> tuple[str, str]:
        (group, task_type), _ = entry
        return (group, task_type or "")

    return [
        {"group": group, "task_type": task_type, "n": n}
        for (group, task_type), n in sorted(counts.items(), key=sort_key)
    ]


def solved_whole(solved: Sequence[Item]) -> list[dict[str, Any]]:
    """絞りの対象外として全件を解いた群(タスク型を持たない群)と件数。

    答える問い: 「絞りを宣言した run で、タスク型に依らず全件を解いた群はどれで、何件か」

    **ADR-082 の門の役目(黙って項目数が減らないこと)を保つための記録**(ADR-099 決定5)。
    外した側は `dropped`、全件を解いた側はこちらに残る。
    """
    counts: dict[str, int] = {}
    for item in solved:
        if task_type_of_item(item) is None:
            counts[item.group] = counts.get(item.group, 0) + 1
    return [{"group": group, "n": n} for group, n in sorted(counts.items())]


def subset_record(
    task_types: Sequence[str] | None, items: Sequence[Item], solved: Sequence[Item]
) -> dict[str, Any] | None:
    """metrics.json の `task_subset` 欄。絞りが無ければ None(欄は置き、値を null にする)。

    答える問い: 「この run はプールの何件のうち何件を解き、何を外したか」
    """
    if task_types is None:
        return None
    return {
        "task_types": list(task_types),
        "n_pool_items": len(items),
        "n_items": len(solved),
        "n_dropped": len(items) - len(solved),
        "dropped": dropped_counts(items, solved),
        "solved_whole": solved_whole(solved),
        "note": SUBSET_NOTE,
    }


def subset_line(record: Mapping[str, Any] | None) -> str:
    """log.txt と dry-run の報告に出す 1 行。"""
    if record is None:
        return "絞り: なし(プール全体)"
    dropped = ", ".join(
        # タスク型を持たない群(特異性対照)は群の名前だけで書く。
        f"{entry['group']}"
        + (f"/{entry['task_type']}" if entry["task_type"] is not None else "")
        + f" {entry['n']}"
        for entry in record["dropped"]
    )
    whole = ", ".join(f"{entry['group']} {entry['n']}" for entry in record["solved_whole"])
    return (
        f"絞り: {TASK_SUBSET_KEY}={record['task_types']} "
        f"解く {record['n_items']} / プール {record['n_pool_items']} "
        f"(外した {record['n_dropped']}: {dropped or 'なし'})"
        + (f" / 絞りの対象外で全件: {whole}" if whole else "")
    )
