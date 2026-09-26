"""パイロット FT の T2 の崩れ方の形を、素のモデルと並べて数える(PLAN-031 §8.5)。

答える問い: 「素のモデル B0 と評価 run 10 本の T2 の各セルで、応答はどの形(数だけ / `Answer:` の
行だけ / 語を含む / その他)で、どれだけの長さで、被演算子の式を何件書いたか。形と 4 値はどう
重なり、場面ごとにどう分かれるか。訓練の損失はどのステップで閾値を下回ったか」

    python -m code.analysis.t2_form_profile --baseline runs/20260922_121455_order6b_b0 \\
        --runs "runs/pilot_ft_eval_*" --train-runs "runs/pilot_ft_train_*" \\
        --out-dir results/pilot_ft_t2_form

**記述だけで、判定も解釈もしない**(`CLAUDE.md` §7・§8)。「FT が○○を壊した」「書式が原因」は
出力のどこにも書かない。`pool_id: pilot` の数値は主張に使わない(罠2)。

**素のモデルと評価 run が同じ項目・同じ文面・同じ生成設定であることを確かめてから数える**
(§8.5 の前提 (a)〜(d)。食い違えば止める)。解いた項目の数の違い(バッチの組み合わせの違い)は
止めずに注記する。

**セルの写像は `frame.build_rows`、参照規則ごとの分類は `gonogo_ft.rows_under_rule`、回は訓練 run の
`outcome.n_steps`**(§8.4 の `t2_response_profile` と同じ経路。§8.4 の出力は変えない)。
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from code.analysis import gonogo
from code.analysis.aggregate import expand_metrics_paths
from code.analysis.frame import build_rows, load_run, read_predictions
from code.analysis.gonogo_ft import (
    OWN_RULE,
    REFERENCE_P2,
    REFERENCE_RULES,
    check_pilot_pool,
    rows_under_rule,
)
from code.analysis.t2_response_profile import ProfileError, four_values_by_rule, train_steps
from code.artifacts import utc_now
from code.data_gen.pool import COVERAGE_ID, MAIN_COVERAGE_LEVELS
from code.eval.battery import numeric_sum
from code.eval.run import TRAIN_KIND
from code.rates import CATEGORIES, RATE_FIELDS

JSON_FILENAME = "t2_form.json"
TEXT_FILENAME = "t2_form.out"

TASK = numeric_sum.T2

# 参考行(§8.5 の 6。形・長さ・4 値だけ): T1 × id(`bare_sum` 群)と指示付き T1(群ごと)。
REFERENCE_T1_ID = "t1_id"
REFERENCE_T1_INSTRUCTED = "t1_instructed"
REFERENCES: tuple[str, ...] = (REFERENCE_T1_ID, REFERENCE_T1_INSTRUCTED)

# 素のモデルの形 × 分類・場面ごとの 4 値のブロック(§8.5 の 4。アダプタが無いので条件自身の規則は無い)。
BASELINE_RULE = REFERENCE_P2
ROLE_BASELINE = "baseline"
ROLE_FT = "ft"

# 応答の形(§8.5 の 1)。**排他的な 4 類で、上から順に当てる。**定義を変えたら PLAN-031 §11 に書く。
FORM_NUMBER_ONLY = "number_only"
FORM_ANSWER_TAG_ONLY = "answer_tag_only"
FORM_WITH_WORDS = "with_words"
FORM_OTHER = "other"
FORMS: tuple[str, ...] = (FORM_NUMBER_ONLY, FORM_ANSWER_TAG_ONLY, FORM_WITH_WORDS, FORM_OTHER)
NUMBER_PATTERN = r"-?[0-9][0-9,]*"
NUMBER_LINE = re.compile(NUMBER_PATTERN)
# 大文字小文字を区別する(T2 の文面が指定する綴り `Answer: <number>`)。行は前後の空白を除いてから当てる。
ANSWER_LINE = re.compile(rf"Answer:\s*{NUMBER_PATTERN}")
# 英字 2 文字以上の並び。`Answer` も語に数える(§8.5 の定義の字義どおり)。
WORD = re.compile(r"[A-Za-z]{2,}")

# 場面(`category`)ごとに見せる最頻の `parsed` の件数(§8.5 の 5)。
TOP_CATEGORY_SHOWN = 3
# 訓練の損失の閾値(§8.5 の 7。「初めて下回る」は厳密な不等号)と、見せる先頭の損失の個数。
LOSS_THRESHOLDS: tuple[float, ...] = (1e-1, 1e-2, 1e-3)
FIRST_LOSSES_SHOWN = 5

# 前提 (d): 素のモデルと評価 run で同じでなければならない `generation` の欄。
GENERATION_KEYS: tuple[str, ...] = (
    "revision",
    "max_new_tokens",
    "do_sample",
    "chat_template",
    "batch_size",
)

HEADER_NOTE = (
    "pool_id: pilot。探索的パイロット FT の記述であって、判定・解釈ではない(CLAUDE.md §7・§8)。"
    "主張・効果量・Δ 5 行・E1 の境界には使わない(PLAN-001 §4.6 規則4 / ADR-097 決定2)"
)
FORM_NOTE = (
    "形は応答の前後の空白を除いて上から順に当てる。number_only = 全体が数だけ(-?[0-9][0-9,]*)/ "
    "answer_tag_only = 空でない行(前後の空白を除く)がすべて「数だけ」か「Answer: + 数」で、"
    "Answer の行が 1 つ以上 / with_words = 上の 2 つでなく、英字 2 文字以上の並びを含む"
    "(Answer も語に数える。式 + Answer の行はここに入る)/ other = どれでもない"
    "(空文字・式だけ・記号つきの数を含む)"
)
OWN_RULE_NOTE = (
    "形 × 分類の表と場面ごとの 4 値は、その run の条件自身の規則のブロック"
    "(gonogo_ft の OWN_RULE。p2・ident = p2 / p2d = p2d。素のモデルは p2)。"
    "four_values は参照規則 p2・p2d の両方"
)
EXPRESSION_NOTE = (
    "operand_expression = 応答に a + b か b + a が現れる件数(a・b はその項目の operands。"
    "+ の前後の空白は任意。数の直前・直後に別の数字が続くものは数えない)"
)
LOSS_NOTE = (
    "first_below = 損失が閾値を初めて下回る(<)ステップ。1 始まり。下回らなければ null。"
    "prefix_equal = 同じ (条件, シード) の短い回の損失全部と、長い回の先頭を == で比べた一致数"
)
BATCH_NOTE = (
    "素のモデルと評価 run は解いた項目の数が違う(n_items_solved)。batch_size は同じでも"
    "バッチの組み合わせが違うので、同じ文面でも応答が変わりうる(順6 の R4 は batch の違いで"
    "応答が変わった例)。止めずに注記する(PLAN-031 §8.5)"
)
PRECONDITIONS_CHECKED: tuple[str, ...] = (
    "(a) pool.items_sha256 が素のモデルと同じ",
    "(b) T2 の各セルと参考行の item_id の集合が素のモデルと同じ",
    "(c) 同じ item_id の prompt の文字列が素のモデルと同じ",
    "(d) generation の revision・max_new_tokens・do_sample・chat_template・batch_size が同じ",
)


@dataclass(frozen=True)
class RunForms:
    """1 つの run(素のモデル / 評価 run)の T2 のセルと参考行の項目。"""

    run_id: str
    role: str
    condition: str | None
    seed: int | None
    n_steps: int | None
    own_rule: str
    items_sha256: str
    n_items_solved: int
    generation: dict[str, Any]
    cells: dict[str, list[dict[str, Any]]]
    references: dict[str, list[dict[str, Any]]]

    @property
    def key(self) -> tuple[str | None, int | None, int | None]:
        return (self.condition, self.seed, self.n_steps)


@dataclass(frozen=True)
class TrainLosses:
    """1 つの訓練 run の損失の列。"""

    run_id: str
    condition: str
    seed: int
    n_steps: int
    losses: tuple[float, ...]

    @property
    def key(self) -> tuple[str, int, int]:
        return (self.condition, self.seed, self.n_steps)


# --------------------------------------------------------------------------
# 読み込み(I/O はここだけ)
# --------------------------------------------------------------------------


def form_item(record: Mapping[str, Any], classes: Mapping[str, str]) -> dict[str, Any]:
    """数え上げに要る欄だけの項目(`predictions` の 1 行 + 参照規則ごとの分類)。"""
    return {
        "item_id": record["item_id"],
        "category": record["category"],
        "operands": list(record["operands"]),
        "prompt": record["prompt"],
        "response": record["response"],
        "parsed": record["parsed"],
        "classification": dict(classes),
    }


def split_items(
    rows: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]], run_name: str
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """行を T2 × 既知性のセルと参考行(T1 × id・指示付き T1)に分ける。**空の区分があれば止める。**"""
    by_rule = {rule: rows_under_rule(rows, records, rule) for rule in REFERENCE_RULES}
    cells: dict[str, list[dict[str, Any]]] = {level: [] for level in MAIN_COVERAGE_LEVELS}
    references: dict[str, list[dict[str, Any]]] = {name: [] for name in REFERENCES}
    for index, (row, record) in enumerate(zip(rows, records, strict=True)):
        classes = {rule: by_rule[rule][index]["classification"] for rule in REFERENCE_RULES}
        if row["task"] == TASK and row["coverage"] in cells:
            cells[row["coverage"]].append(form_item(record, classes))
        elif row["group"] == numeric_sum.GROUP_BARE_SUM and row["coverage"] == COVERAGE_ID:
            references[REFERENCE_T1_ID].append(form_item(record, classes))
        elif row["group"] == numeric_sum.GROUP_BARE_SUM_INSTRUCTED:
            references[REFERENCE_T1_INSTRUCTED].append(form_item(record, classes))
    empty = [name for name, items in {**cells, **references}.items() if not items]
    if empty:
        raise ProfileError(f"{run_name}: 区分 {empty} に項目が無い")
    return cells, references


def load_run_forms(metrics_path: Path, *, baseline: bool) -> RunForms:
    """素のモデル(`baseline=True`。アダプタ無しに限る)か評価 run を読む。"""
    run = load_run(metrics_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    name = run.run_dir.name
    check_pilot_pool(metrics, name)
    has_adapter = metrics.get("adapter") is not None
    if baseline and has_adapter:
        raise ProfileError(f"{name}: --baseline はアダプタの無い run(adapter=null)だけを受け付ける")
    if not baseline:
        if not has_adapter or run.seed is None:
            raise ProfileError(f"{name}: アダプタを載せていない run である(adapter=null)")
        if run.condition not in OWN_RULE:
            raise ProfileError(f"{name}: 条件 {run.condition!r} はパイロット FT の条件でない")
    records = read_predictions(run.run_dir)
    cells, references = split_items(build_rows(run, records), records, name)
    return RunForms(
        run_id=run.run_id,
        role=ROLE_BASELINE if baseline else ROLE_FT,
        # 素のモデルの lesion_condition は config の値(p2)で、訓練した条件ではない。条件として並べない。
        condition=None if baseline else run.condition,
        seed=run.seed,
        n_steps=None if baseline else train_steps(run.run_dir, metrics),
        own_rule=BASELINE_RULE if baseline else OWN_RULE[run.condition],
        items_sha256=metrics["pool"]["items_sha256"],
        n_items_solved=len(records),
        generation={key: metrics["generation"][key] for key in GENERATION_KEYS},
        cells=cells,
        references=references,
    )


def load_train_losses(metrics_path: Path) -> TrainLosses:
    """訓練 run の損失の列。**`losses` の個数が `n_steps` と違えば止める。**"""
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    name = metrics_path.parent.name
    if metrics.get("kind") != TRAIN_KIND:
        raise ProfileError(f"{name}: kind={metrics.get('kind')!r} で訓練 run({TRAIN_KIND})ではない")
    outcome = metrics["outcome"]
    losses = tuple(float(loss) for loss in outcome["losses"])
    n_steps = int(outcome["n_steps"])
    if len(losses) != n_steps:
        raise ProfileError(f"{name}: losses が {len(losses)} 個で n_steps={n_steps} と合わない")
    return TrainLosses(
        run_id=metrics.get("run_id", name),
        condition=metrics["lesion_condition"],
        seed=int(metrics["seed"]),
        n_steps=n_steps,
        losses=losses,
    )


# --------------------------------------------------------------------------
# 前提の確かめ(§8.5 の (a)〜(d))
# --------------------------------------------------------------------------


def check_same_items(
    base: Sequence[Mapping[str, Any]], other: Sequence[Mapping[str, Any]], where: str
) -> None:
    """(b) item_id の集合が同じ / (c) 同じ item_id の prompt が同じ。違えば止める。"""
    base_prompts = {item["item_id"]: item["prompt"] for item in base}
    other_prompts = {item["item_id"]: item["prompt"] for item in other}
    if (
        len(base_prompts) != len(base)
        or len(other_prompts) != len(other)
        or set(base_prompts) != set(other_prompts)
    ):
        raise ProfileError(f"{where}: item_id の集合が素のモデルと違う(前提 (b))")
    changed = sorted(key for key, prompt in base_prompts.items() if other_prompts[key] != prompt)
    if changed:
        raise ProfileError(f"{where}: prompt が素のモデルと違う項目がある(前提 (c)): {changed[:3]}")


def check_comparable(baseline: RunForms, run: RunForms) -> None:
    """素のモデルと評価 run が同じ項目・同じ文面・同じ生成設定か(前提 (a)〜(d))。"""
    if run.items_sha256 != baseline.items_sha256:
        raise ProfileError(f"{run.run_id}: pool.items_sha256 が素のモデルと違う(前提 (a))")
    differing = {
        key: (baseline.generation[key], run.generation[key])
        for key in GENERATION_KEYS
        if baseline.generation[key] != run.generation[key]
    }
    if differing:
        raise ProfileError(f"{run.run_id}: generation が素のモデルと違う(前提 (d)): {differing}")
    for level in MAIN_COVERAGE_LEVELS:
        check_same_items(baseline.cells[level], run.cells[level], f"{run.run_id} {TASK}×{level}")
    for name in REFERENCES:
        check_same_items(baseline.references[name], run.references[name], f"{run.run_id} {name}")


# --------------------------------------------------------------------------
# 応答の形(純粋関数)
# --------------------------------------------------------------------------


def non_empty_lines(response: str) -> list[str]:
    """前後の空白を除いた、空でない行。"""
    return [line.strip() for line in response.splitlines() if line.strip()]


def response_form(response: str) -> str:
    """応答の形(`FORMS` のどれか 1 つ)。

    答える問い: 「この応答は、数だけか、`Answer:` の行だけか、語を含むか、そのどれでもないか」
    (PLAN-031 §8.5 の 1)
    """
    text = response.strip()
    if NUMBER_LINE.fullmatch(text):
        return FORM_NUMBER_ONLY
    lines = non_empty_lines(text)
    tags = [line for line in lines if ANSWER_LINE.fullmatch(line)]
    if tags and all(NUMBER_LINE.fullmatch(line) or ANSWER_LINE.fullmatch(line) for line in lines):
        return FORM_ANSWER_TAG_ONLY
    if WORD.search(text):
        return FORM_WITH_WORDS
    return FORM_OTHER


def writes_operand_expression(response: str, operands: Sequence[int]) -> bool:
    """応答に `a + b` か `b + a` が現れるか(§8.5 の 3)。

    数の直前・直後に数字が続くもの(`193 + 46` の中の `93 + 46`)は数えない。
    """
    a, b = (str(value) for value in operands)
    return any(
        re.search(rf"(?<![0-9]){re.escape(x)}\s*\+\s*{re.escape(y)}(?![0-9])", response)
        for x, y in ((a, b), (b, a))
    )


# --------------------------------------------------------------------------
# セルごとの数え上げ(純粋関数)
# --------------------------------------------------------------------------


def form_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """形ごとの件数(4 類すべての鍵を持つ)。"""
    counts = Counter(response_form(item["response"]) for item in items)
    return {form: counts[form] for form in FORMS}


def length_profile(items: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    """応答の文字数の最小・中央値・最大と、空でない行の数の中央値(§8.5 の 2)。"""
    chars = [len(item["response"]) for item in items]
    lines = [len(non_empty_lines(item["response"])) for item in items]
    return {
        "chars_min": min(chars),
        "chars_median": statistics.median(chars),
        "chars_max": max(chars),
        "lines_median": statistics.median(lines),
    }


def expression_count(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """被演算子の式を書いた件数と分母。"""
    written = sum(writes_operand_expression(item["response"], item["operands"]) for item in items)
    return {"n": len(items), "n_written": written}


def form_by_class(items: Sequence[Mapping[str, Any]], rule: str) -> dict[str, dict[str, int]]:
    """形 × 4 値の分類(参照規則 `rule` のブロック)の件数の表(§8.5 の 4)。"""
    table = {form: dict.fromkeys(CATEGORIES, 0) for form in FORMS}
    for item in items:
        table[response_form(item["response"])][item["classification"][rule]] += 1
    return table


def four_values_under(items: Sequence[Mapping[str, Any]], rule: str) -> dict[str, Any]:
    """参照規則 `rule` のブロックの 4 値(合計 1.0 は `gonogo.four_values` が確かめる)。"""
    return gonogo.four_values([{"classification": item["classification"][rule]} for item in items])


def top_parsed(items: Sequence[Mapping[str, Any]], top: int) -> list[dict[str, Any]]:
    """最頻の `parsed` の上位 `top` 件。件数の降順・同数は値の昇順(null は同数の最後)。"""
    counts = Counter(item["parsed"] for item in items)
    order = sorted(
        counts.items(),
        key=lambda pair: (-pair[1], pair[0] is None, 0 if pair[0] is None else pair[0]),
    )
    return [{"parsed": value, "count": count} for value, count in order[:top]]


def category_profile(
    items: Sequence[Mapping[str, Any]], rule: str, top: int
) -> dict[str, dict[str, Any]]:
    """場面(`category`)ごとの 4 値と最頻の `parsed`(§8.5 の 5)。場面は名前の昇順。"""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        groups.setdefault(item["category"], []).append(item)
    return {
        category: {
            "four_values": four_values_under(group, rule),
            "top_parsed": top_parsed(group, top),
        }
        for category, group in sorted(groups.items())
    }


def cell_profile(items: Sequence[Mapping[str, Any]], own_rule: str) -> dict[str, Any]:
    """T2 の 1 つのセルの 1〜5(PLAN-031 §8.5)。"""
    return {
        "four_values": four_values_by_rule(items),
        "forms": form_counts(items),
        "length": length_profile(items),
        "operand_expression": expression_count(items),
        "form_by_class": form_by_class(items, own_rule),
        "categories": category_profile(items, own_rule, TOP_CATEGORY_SHOWN),
    }


def reference_profile(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """参考行の形・長さ・4 値だけ(§8.5 の 6)。"""
    return {
        "n": len(items),
        "four_values": four_values_by_rule(items),
        "forms": form_counts(items),
        "length": length_profile(items),
    }


# --------------------------------------------------------------------------
# 訓練の損失(§8.5 の 7。純粋関数)
# --------------------------------------------------------------------------


def first_below(losses: Sequence[float], threshold: float) -> int | None:
    """損失が `threshold` を初めて下回る(<)ステップ(1 始まり)。下回らなければ None。"""
    for step, loss in enumerate(losses, start=1):
        if loss < threshold:
            return step
    return None


def loss_profile(train: TrainLosses) -> dict[str, Any]:
    """1 つの訓練 run の到達ステップと最初の損失。"""
    return {
        "run_id": train.run_id,
        "condition": train.condition,
        "seed": train.seed,
        "n_steps": train.n_steps,
        "first_below": {f"{t:g}": first_below(train.losses, t) for t in LOSS_THRESHOLDS},
        "first_losses": list(train.losses[:FIRST_LOSSES_SHOWN]),
    }


def prefix_agreement(short: Sequence[float], long: Sequence[float]) -> dict[str, int]:
    """短い列の全部と長い列の先頭を `==` で比べた一致数と分母。**長い列の方が短ければ止める。**"""
    if len(long) < len(short):
        raise ProfileError("長い回の損失が短い回より少ない")
    return {
        "n_equal": sum(a == b for a, b in zip(short, long, strict=False)),
        "n_compared": len(short),
    }


def training_report(trains: Sequence[TrainLosses]) -> dict[str, Any]:
    """訓練 run ごとの到達ステップと、同じ (条件, シード) の回どうしの先頭の一致。"""
    keys = [train.key for train in trains]
    if len(set(keys)) != len(keys):
        raise ProfileError(f"同じ (条件, シード, n_steps) の訓練 run が複数ある: {sorted(keys)}")
    ordered = sorted(trains, key=lambda t: (t.n_steps, t.condition, t.seed))
    prefix: list[dict[str, Any]] = []
    for left, right in combinations(sorted(trains, key=lambda t: t.key), 2):
        if (left.condition, left.seed) != (right.condition, right.seed):
            continue
        short, long = sorted((left, right), key=lambda t: t.n_steps)
        prefix.append(
            {
                "condition": short.condition,
                "seed": short.seed,
                "short": {"run_id": short.run_id, "n_steps": short.n_steps},
                "long": {"run_id": long.run_id, "n_steps": long.n_steps},
                **prefix_agreement(short.losses, long.losses),
            }
        )
    return {
        "loss_thresholds": list(LOSS_THRESHOLDS),
        "runs": [loss_profile(train) for train in ordered],
        "prefix_equal": prefix,
    }


# --------------------------------------------------------------------------
# 表と出力
# --------------------------------------------------------------------------


def run_profile(run: RunForms) -> dict[str, Any]:
    """1 つの run のセルごとの数え上げと参考行。"""
    return {
        "run_id": run.run_id,
        "role": run.role,
        "condition": run.condition,
        "seed": run.seed,
        "n_steps": run.n_steps,
        "own_rule": run.own_rule,
        "n_items_solved": run.n_items_solved,
        "cells": {level: cell_profile(run.cells[level], run.own_rule) for level in run.cells},
        "references": {name: reference_profile(run.references[name]) for name in REFERENCES},
    }


def build_report(
    baseline: RunForms, runs: Sequence[RunForms], trains: Sequence[TrainLosses]
) -> dict[str, Any]:
    """素のモデルを先頭に並べた表。**前提 (a)〜(d) が崩れる run・同じ (条件, シード, 回) の重複は止める。**"""
    keys = [run.key for run in runs]
    if len(set(keys)) != len(keys):
        raise ProfileError(f"同じ (条件, シード, n_steps) の評価 run が複数ある: {sorted(keys)}")
    for run in runs:
        check_comparable(baseline, run)
    ordered = sorted(runs, key=lambda r: (r.n_steps, r.condition, r.seed))
    return {
        "created_at": utc_now().isoformat(),
        "note": HEADER_NOTE,
        "notes": {
            "forms": FORM_NOTE,
            "own_rule": OWN_RULE_NOTE,
            "operand_expression": EXPRESSION_NOTE,
            "training": LOSS_NOTE,
            "batch": BATCH_NOTE,
        },
        "task": TASK,
        "constants": {
            "forms": list(FORMS),
            "number_pattern": NUMBER_PATTERN,
            "answer_line_pattern": ANSWER_LINE.pattern,
            "word_pattern": WORD.pattern,
            "top_category_shown": TOP_CATEGORY_SHOWN,
            "first_losses_shown": FIRST_LOSSES_SHOWN,
        },
        "preconditions": {
            "baseline_run_id": baseline.run_id,
            "checked": list(PRECONDITIONS_CHECKED),
            "items_sha256": baseline.items_sha256,
            "generation": baseline.generation,
            "n_items_solved": {run.run_id: run.n_items_solved for run in [baseline, *ordered]},
        },
        "runs": [run_profile(run) for run in [baseline, *ordered]],
        "training": training_report(trains),
    }


def _four(values: Mapping[str, Any]) -> str:
    return " ".join(f"{name.removesuffix('_rate')}={values[name]:.3f}" for name in RATE_FIELDS)


def _label(run: Mapping[str, Any]) -> str:
    if run["role"] == ROLE_BASELINE:
        return "B0(adapter null)"
    return f"{run['condition']} s{run['seed']} n{run['n_steps']}"


def _forms(counts: Mapping[str, int]) -> str:
    return "/".join(str(counts[form]) for form in FORMS)


def _length(length: Mapping[str, Any]) -> str:
    return (
        f"文字数 {length['chars_min']}/{length['chars_median']}/{length['chars_max']}"
        f"(最小/中央/最大)・行数の中央 {length['lines_median']}"
    )


def summary_lines(report: Mapping[str, Any]) -> list[str]:
    """run × セルの形の件数と式の件数の一覧(`.out` の先頭)。"""
    lines = [f"== 形の件数({'/'.join(FORMS)})と式を書いた件数 [{report['task']}]"]
    for run in report["runs"]:
        parts = [
            f"{level}={_forms(cell['forms'])} 式{cell['operand_expression']['n_written']}"
            for level, cell in run["cells"].items()
        ]
        lines.append(f"  {_label(run):<22} " + "  ".join(parts))
    return lines


def run_lines(run: Mapping[str, Any], task: str) -> list[str]:
    """1 つの run の詳細(`.out`)。"""
    own = run["own_rule"]
    lines = [
        f"== {run['run_id']}  ({_label(run)} own_rule={own} 解いた項目 {run['n_items_solved']})"
    ]
    for level, cell in run["cells"].items():
        expression = cell["operand_expression"]
        lines.append(f"  [{task} × {level}] n={expression['n']}")
        for rule, values in cell["four_values"].items():
            lines.append(f"    4値({rule}): {_four(values)}")
        lines.append("    形: " + " ".join(f"{k}={v}" for k, v in cell["forms"].items()))
        lines.append(f"    長さ: {_length(cell['length'])}")
        lines.append(f"    式(a + b / b + a): {expression['n_written']} / {expression['n']}")
        for form, counts in cell["form_by_class"].items():
            if sum(counts.values()):
                shown = " ".join(f"{k}={v}" for k, v in counts.items())
                lines.append(f"    形 × 分類({own}) {form}: {shown}")
        for category, entry in cell["categories"].items():
            top = ", ".join(f"{t['parsed']}×{t['count']}" for t in entry["top_parsed"])
            lines.append(
                f"    場面 {category} n={entry['four_values']['n']} "
                f"4値({own}) {_four(entry['four_values'])} / 最頻 parsed {top}"
            )
    for name, ref in run["references"].items():
        lines.append(f"  [参考 {name}] n={ref['n']}")
        lines.append(f"    4値({own}): {_four(ref['four_values'][own])}")
        lines.append("    形: " + " ".join(f"{k}={v}" for k, v in ref["forms"].items()))
        lines.append(f"    長さ: {_length(ref['length'])}")
    lines.append("")
    return lines


def training_lines(training: Mapping[str, Any]) -> list[str]:
    """訓練の損失(`.out`)。"""
    thresholds = " / ".join(f"<{t:g}" for t in training["loss_thresholds"])
    lines = [f"== 訓練の損失: 初めて下回るステップ({thresholds})と先頭の損失"]
    for run in training["runs"]:
        steps = " / ".join(str(step) for step in run["first_below"].values())
        first = ", ".join(f"{loss:.4g}" for loss in run["first_losses"])
        lines.append(
            f"  {run['run_id']:<30} {run['condition']:<5} s{run['seed']} n{run['n_steps']:<4} "
            f"{steps:<16} [{first}]"
        )
    lines.append("== 同じ (条件, シード) の短い回と長い回の先頭の損失の == 一致")
    for row in training["prefix_equal"]:
        lines.append(
            f"  {row['condition']:<5} s{row['seed']} n{row['short']['n_steps']} 対 "
            f"n{row['long']['n_steps']}: {row['n_equal']} / {row['n_compared']}"
        )
    return lines


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人が読む形(`.out`)。数値は JSON と同じもの。"""
    lines = [f"# {report['note']}"]
    lines.extend(f"# {note}" for note in report["notes"].values())
    pre = report["preconditions"]
    lines.append(f"# 前提(確かめて通った): {' / '.join(pre['checked'])}")
    lines.append(f"# 解いた項目: {pre['n_items_solved']}")
    lines.append("")
    lines.extend(summary_lines(report))
    lines.append("")
    for run in report["runs"]:
        lines.extend(run_lines(run, report["task"]))
    lines.extend(training_lines(report["training"]))
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T2 の崩れ方の形の数え上げ(PLAN-031 §8.5)")
    parser.add_argument("--baseline", required=True, help="素のモデルの run(adapter null。1 本だけ)")
    parser.add_argument("--runs", required=True, nargs="+", help="パイロット FT の評価 run の glob")
    parser.add_argument("--train-runs", required=True, nargs="+", help="訓練 run の glob")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help=f"指定すると {JSON_FILENAME} と {TEXT_FILENAME} を書く")
    args = parser.parse_args(argv)

    baseline_paths = expand_metrics_paths([args.baseline])
    if len(baseline_paths) != 1:
        raise ProfileError(f"--baseline は 1 本だけ: {[str(p) for p in baseline_paths]}")
    report = build_report(
        load_run_forms(baseline_paths[0], baseline=True),
        [load_run_forms(path, baseline=False) for path in expand_metrics_paths(args.runs)],
        [load_train_losses(path) for path in expand_metrics_paths(args.train_runs)],
    )
    lines = report_lines(report)
    for line in lines:
        print(line)
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / JSON_FILENAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (args.out_dir / TEXT_FILENAME).write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"-> {args.out_dir / JSON_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
