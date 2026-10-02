"""T1c(合成の探り)の本実行と配線確認の入口(PLAN-037 I3・ADR-118 決定 D5)。

答える問い: 「この config が宣言した T1c の項目に、この重みは t・t+offset・t+2·offset のどれを答えたか。
その記録が、どのコードの、どの設定の、いつの実行から出たかを後から言えるか」

    python -m code.eval.composition_run --config <config> --dry-run
    python -m code.eval.composition_run --config <config> --run-dir runs/<id>

**固定オフセットの経路(`code/eval/run.py`)には入れない**(前例は `calibration_run.py`)。
`metrics.json` は別の `kind`(`composition`)を持つので、`aggregate.py` は飛ばし、`frame.py` は止まる
(主要検定・E1 の入力に黙って混ざらない。PLAN-037 §3.3 の 2)。`run.py` は `eval.composition` を
宣言した config と T1c のプールを拒む。

**採点**: 自由生成 + `numeric` パーサ(変えない。罠 4)。参照規則は 2 つのブロック(`comp_once`・
`comp_twice`。D1)で、各ブロックの中で 4 値の合計は 1.0。rate(t) は両ブロックの `correct_rate`。
`metrics.json` は (既知性 × 繰り上がり)のセルごとにも同じ 2 ブロックを持つ。**判定・合否・
解釈の文言を出さない**(E3 の検定は凍結の後。§3.3 の 5)。

**検査はすべて重みを読む前・run ディレクトリを作る前に済ませる**(宣言・プールの種類・文面・
宣言どうしの重なり・D9 の門)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from code.artifacts import (
    elapsed_seconds,
    monotonic_seconds,
    prepare_run_dir,
    timing_line,
    timing_record,
    utc_now,
    write_config_copy,
    write_env,
    write_git_sha,
    write_log,
    write_metrics,
    write_predictions,
    write_timestamps,
)
from code.config import ConfigError, load_config, require
from code.data_gen import composition_pool
from code.data_gen.battery_items import Item, assert_unique_item_ids, read_items
from code.eval import signature_gate
from code.eval.battery import composition
from code.eval.calibration import declared_calibration
from code.eval.generate import Generator, build_generator, collect_responses
from code.eval.model import (
    GenerationSettings,
    declared_adapter,
    declared_scale_sweep_levels,
    load_generation_settings,
)
from code.eval.preamble import declared_preamble
from code.eval.run import (
    adapter_provenance,
    coverage_record,
    declared_threshold_sweep_arm,
    parse_numeric_response,
    pool_items_path,
    pool_record,
    provenance_lines,
    read_pool_manifest,
    reject_unsupported_elicitation,
)
from code.eval.scoring import ItemResponse, classify, score
from code.eval.task_subset import declared_task_subset
from code.lesion import CompositionOffsetLesion, composition_reference_lesions_from_config

COMPOSITION_KIND = "composition"
BATCH_NAME = "composition"
PREDICTIONS_NAME = "composition"
SCORING_FREE_GENERATION = "free_generation"

# 配線確認の固定応答。**実験の刺激ではない。**項目ごとに真値と 2 つの規則適用値が違うので、
# 差し込む値は採点器に渡すのと同じ経路で取る(`composition.answers`)。
DRY_RUN_RESPONSES: dict[str, str] = {
    "truthful": "Answer: {truth}.",
    "once": "Answer: {comp_once}.",
    "twice": "Answer: {comp_twice}.",
    "unreadable": "I cannot say.",
}

# metrics.json の composition 欄に添える注記(読み方の限界)。
COMPOSITION_NOTE = (
    "T1c は 3 項の裸の式 a+b+c= を尋ねる合成の探り(ADR-115 決定3)。4 値分解は参照規則ごとに独立した"
    "ブロック(comp_once = t+offset / comp_twice = t+2·offset)で、各ブロックの中で合計が 1.0 である。"
    "rate(t) は両ブロックの correct_rate(同じ値)。**t+2 が優勢でも H1 を退けたとは書かない**"
    "(非対称な推論)。この run は検定・合否・解釈を出さない(E3 の検定は凍結の後。PLAN-037 §3.3 の 5)。"
)


@dataclass(frozen=True)
class CompositionPlan:
    """この T1c の run が解く項目と、その来歴(重みを読む前に組む)。

    答える問い: 「この run は、どのプールの、どの項目を、どの文面で、どの門を通って解くか」
    """

    items: tuple[Item, ...]
    templates: Mapping[str, str]
    reference_lesions: Mapping[str, CompositionOffsetLesion]
    elicitation: str
    pool: Mapping[str, Any]
    coverage: Mapping[str, Any]
    gate: Mapping[str, Any]
    n_per_cell: int
    cells: tuple[str, ...]


def refuse_conflicting_declarations(config: Mapping[str, Any]) -> None:
    """T1c の run で黙って効かなくなる宣言を止める。

    答える問い: 「この config は、T1c の run として他の経路の宣言と重なっていないか」

    T1c の run は前置き・絞り・掃引・較正を持たない。宣言したまま回すと、宣言が黙って効かない
    まま数値が出る(`calibration_run.load_calibration_plan` と同じ作法)。
    """
    if declared_threshold_sweep_arm(config) is not None:
        raise ConfigError("eval.threshold_sweep_arm と eval.composition は同時に宣言できない")
    if declared_calibration(config) is not None:
        raise ConfigError("eval.calibration と eval.composition は同時に宣言できない")
    if declared_scale_sweep_levels(config) is not None:
        raise ConfigError("eval.scale_sweep と eval.composition は同時に宣言できない(T1c は s を掛けない)")
    if declared_task_subset(config) is not None:
        raise ConfigError("eval.task_subset は T1c の run では効かない(項目は絞らない)")
    if declared_preamble(config) is not None:
        raise ConfigError("eval.preamble は T1c の run では効かない(前置きは被せない)")


def read_composition_items(config: Mapping[str, Any]) -> list[Item]:
    """T1c のプールを読む。**プールの種類・宣言との噛み合わせを両方向で検査する。**

    答える問い: 「この config が指すプールは T1c のプールか。宣言した文面・件数と合っているか」

    anchor が T1c でないプール(固定オフセットの評価プール・掃引)を指していれば、宣言の
    書き忘れ・anchor の書き換え忘れである。manifest が記録した文面・件数と config の宣言が
    違えば、プールを作り直さずに宣言だけ変えている(尋ね方が黙って変わる)。
    """
    manifest = read_pool_manifest(config)
    fill = manifest.get("fill") or {}
    if fill.get("method") != composition_pool.FILL_COMPOSITION:
        raise ConfigError(
            f"eval.anchor_manifest={require(config, 'eval.anchor_manifest')!r} は T1c のプール"
            f"(fill.method={composition_pool.FILL_COMPOSITION!r})ではない"
            f"(fill.method={fill.get('method')!r})。T1c のプールは "
            "python -m code.data_gen.composition_pool が書く(PLAN-037 I2)。"
        )
    templates = composition.composition_templates(config)
    if fill.get("prompt_template") != dict(templates):
        raise ConfigError(
            f"config の文面 {dict(templates)!r} が、プールの manifest が記録した文面 "
            f"{fill.get('prompt_template')!r} と違う。プールを作り直さずに宣言だけを変えている"
        )
    declared_n = (config["eval"]["composition"]).get("n_per_cell")
    if declared_n != fill.get("n_per_cell"):
        raise ConfigError(
            f"eval.composition.n_per_cell={declared_n!r} が、プールの manifest の "
            f"n_per_cell={fill.get('n_per_cell')!r} と違う"
        )
    path = pool_items_path(config)
    if not path.exists():
        raise ConfigError(
            f"T1c のプールの項目が無い: {path}。先に python -m code.data_gen.composition_pool"
            " --config <config> で書き出すこと"
        )
    items = read_items(path)
    if not items:
        raise ConfigError(f"T1c のプールが空である: {path}")
    assert_unique_item_ids(items)
    pool_id = require(config, "data.pool_id")
    if {item.pool_id for item in items} != {pool_id}:
        raise ConfigError(f"{path} の項目の pool_id が data.pool_id={pool_id!r} と違う")
    if {item.group for item in items} != {composition.GROUP}:
        raise ConfigError(f"{path} に群 {composition.GROUP!r} 以外の項目がある")
    if len(items) != fill["n_items_by_group"][composition.GROUP]:
        raise ConfigError(f"{path} の項目数が manifest の n_items_by_group と違う")
    return items


def load_composition_plan(config: Mapping[str, Any]) -> CompositionPlan:
    """宣言を読み、他の宣言と重なっていないことを確かめ、項目と門を揃える。**重みを読まない。**

    答える問い: 「この config は、T1c の run として噛み合っているか。解く項目は何か」
    """
    if not isinstance((config.get("eval") or {}).get("composition"), Mapping):
        raise ConfigError(
            f"この入口は {composition.COMPOSITION_BLOCK} を宣言した config だけを解く(PLAN-037 I3)。"
            "固定オフセットの評価は python -m code.eval.run である。"
        )
    refuse_conflicting_declarations(config)
    elicitation = require(config, "eval.elicitation")
    reject_unsupported_elicitation(elicitation, [composition.GROUP])
    items = read_composition_items(config)
    lesions = composition_reference_lesions_from_config(config)
    gate = signature_gate.check_signature_gate(
        config,
        adapter=declared_adapter(config),
        condition=require(config, "lesion.condition"),
        what="T1c",
    )
    return CompositionPlan(
        items=tuple(items),
        templates=composition.composition_templates(config),
        reference_lesions=lesions,
        elicitation=elicitation,
        pool=pool_record(config, pool_items_path(config)),
        coverage=coverage_record(config),
        gate=gate,
        n_per_cell=int(config["eval"]["composition"]["n_per_cell"]),
        cells=tuple(dict.fromkeys(str(item.params["cell"]) for item in items)),
    )


# --------------------------------------------------------------------------
# 採点と記録
# --------------------------------------------------------------------------


def block_metrics(responses: Sequence[ItemResponse]) -> dict[str, Any]:
    """応答の列を、2 つの参照規則のブロックに 4 値分解する。

    答える問い: 「この応答の集合は、1 回・2 回の参照規則から見て 4 値にどう分かれたか」

    各ブロックの中で合計が 1.0(`RateBreakdown` が検査)。
    """
    return {
        "n_items": len(responses),
        "by_reference_rule": {
            name: score(responses, name).as_dict() for name in composition.REFERENCE_RULES
        },
    }


def score_items(
    plan: CompositionPlan, texts: Sequence[str]
) -> tuple[list[ItemResponse], dict[str, Any]]:
    """生成文字列を採点し、全体と (既知性 × 繰り上がり)のセルごとのブロックを返す。

    答える問い: 「この応答は、全体とセルごとに、4 値分解でどう分かれたか」
    """
    if len(texts) != len(plan.items):
        raise ConfigError(f"応答 {len(texts)} 本が項目 {len(plan.items)} 件と合わない")
    responses = [
        composition.to_response(
            item, parse_numeric_response(text, plan.elicitation), plan.reference_lesions
        )
        for item, text in zip(plan.items, texts, strict=True)
    ]
    by_cell = {
        cell: block_metrics(
            [
                response
                for item, response in zip(plan.items, responses, strict=True)
                if item.params["cell"] == cell
            ]
        )
        for cell in plan.cells
    }
    metrics = {
        "group": composition.GROUP,
        "scoring": SCORING_FREE_GENERATION,
        **block_metrics(responses),
    }
    return responses, {BATCH_NAME: metrics, "by_cell": by_cell}


def prediction_records(
    plan: CompositionPlan, prompts: Mapping[str, str], texts: Sequence[str], responses: Sequence[ItemResponse]
) -> list[dict[str, Any]]:
    """predictions/ に残す形。生成文字列をそのまま残し、2 ブロックの分類を 1 行に書く。

    答える問い: 「この 1 件は、どの生成文字列から、2 つの参照規則でどう分類されたか」
    """
    return [
        {
            "item_id": item.item_id,
            "group": item.group,
            "category": item.category,
            "operands": list(item.operands),
            "carry": item.carry,
            "params": dict(item.params),
            "prompt": prompts[item.item_id],
            "response": text,
            "parsed": response.parsed,
            "truth": response.truth,
            "rule_values": dict(response.rule_values),
            "classification": {
                name: classify(response.parsed, response.truth, response.rule_values[name])
                for name in composition.REFERENCE_RULES
            },
        }
        for item, text, response in zip(plan.items, texts, responses, strict=True)
    ]


def composition_prompts(plan: CompositionPlan) -> dict[str, str]:
    """項目ごとの文面(item_id -> 文字列)。文面を組む場所はここ 1 つ(配線確認と本実行で共有)。"""
    return {item.item_id: composition.render_prompt(item, plan.templates) for item in plan.items}


def evaluate_composition(
    plan: CompositionPlan, *, generator: Generator
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """T1c の項目をモデルに解かせて採点する。**これは実験結果である。**

    答える問い: 「この重みは、T1c の項目で t・t+offset・t+2·offset のどれを答えたか」

    生成は `collect_responses` を通す(本数の検査を 1 箇所に集める。`run.py` と同じ規約)。
    """
    prompts = composition_prompts(plan)
    texts = collect_responses([prompts[item.item_id] for item in plan.items], generator)
    responses, metrics = score_items(plan, texts)
    return metrics, prediction_records(plan, prompts, texts, responses)


def composition_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    plan: CompositionPlan,
    metrics: Mapping[str, Any],
    *,
    run_id: str,
    timing: Mapping[str, Any],
    adapter: Mapping[str, Any],
) -> dict[str, Any]:
    """T1c の run の metrics.json を組む。

    答える問い: 「この T1c の記録が、どの重みの、どの設定の、どのプールから出たかを、
    この 1 ファイルだけで言えるか」

    来歴の欄(`generation`・`adapter`・`pool`・`coverage`・`timing`)は評価プールを解く経路と
    同じ形。`kind` は `composition`(`aggregate.py` は飛ばし、`frame.py` は止まる)。
    """
    return {
        "run_id": run_id,
        "kind": COMPOSITION_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "seed": adapter["seed"],
        "adapter": adapter["adapter"],
        "adapter_train_run_id": adapter["train_run_id"],
        "adapter_note": adapter["note"],
        "generation": settings.as_dict(),
        "elicitation": plan.elicitation,
        "signature_gate": dict(plan.gate),
        "pool": {**plan.pool, "n_items": len(plan.items)},
        "coverage": dict(plan.coverage),
        "composition": {
            "reference_rules": list(composition.REFERENCE_RULES),
            "offset": require(config, "lesion.offset"),
            "prompt_template": dict(plan.templates),
            "n_per_cell": plan.n_per_cell,
            "cells": list(plan.cells),
            "note": COMPOSITION_NOTE,
        },
        "timing": dict(timing),
        "by_batch": {BATCH_NAME: metrics[BATCH_NAME]},
        "by_cell": metrics["by_cell"],
    }


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。**判定・解釈の文言を出さない。**

    答える問い: 「この T1c の run は、どの重みで、何件を解き、各ブロックの 4 値はいくつか」
    """
    lines = [
        *provenance_lines(payload),
        f"D9 の門: {json.dumps(payload['signature_gate'], ensure_ascii=False)}",
        timing_line(payload["timing"]),
        f"項目: {payload['pool']['n_items']} 件 <- {payload['pool']['items']}",
        f"注意: {payload['composition']['note']}",
    ]
    names = {"overall": payload["by_batch"][BATCH_NAME], **payload["by_cell"]}
    for name, batch in names.items():
        for rule, block in batch["by_reference_rule"].items():
            lines.append(
                f"[{name}] rule={rule} n={block['n_items']} correct={block['correct_rate']:.4f} "
                f"rule={block['rule_rate']:.4f} other_error={block['other_error_rate']:.4f} "
                f"parse_fail={block['parse_fail_rate']:.4f}"
            )
    return lines


def execute_composition(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path | None,
    generator: Generator | None = None,
    now: datetime | None = None,
) -> Path:
    """T1c の本実行。成果物を `runs/<id>/` に書き、その dir を返す。

    答える問い: 「この T1c の記録が、どのコードの、どの設定の、いつの実行から出たかを後から言えるか」

    **検査はすべて run ディレクトリを作る前・重みを読む前に済ませる**(`load_composition_plan`・
    生成設定・アダプタの出どころ)。`generator` は差し替え可能で、**None のときだけ重みを読む**
    (`build_generator`。強制選択を使わないので採点器は作らない)。来歴を生成の前に書き、
    区間を 3 つに分けて測るのは `run.execute` と同じ理由である。
    """
    plan = load_composition_plan(config)
    settings = load_generation_settings(config)
    adapter = adapter_provenance(
        declared_adapter(config), condition=require(config, "lesion.condition")
    )
    started = now or utc_now()
    run_started = monotonic_seconds()
    target = prepare_run_dir(config, explicit=run_dir, now=started)
    write_config_copy(target, config_path)
    write_git_sha(target)
    write_env(target)

    load_started = monotonic_seconds()
    if generator is None:
        generator = build_generator(settings, adapter=adapter["adapter"])
    model_load_seconds = elapsed_seconds(load_started)

    generation_started = monotonic_seconds()
    metrics, records = evaluate_composition(plan, generator=generator)
    generation_seconds = elapsed_seconds(generation_started)

    write_predictions(target, PREDICTIONS_NAME, records)
    ended = utc_now()
    payload = composition_payload(
        config,
        settings,
        plan,
        metrics,
        run_id=target.name,
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=model_load_seconds,
            generation_seconds=generation_seconds,
            n_items=len(plan.items),
        ),
        adapter=adapter,
    )
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=ended)
    lines = report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


# --------------------------------------------------------------------------
# 配線確認
# --------------------------------------------------------------------------


def composition_dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    """重みを読まずに T1c の経路の配線を確かめる。**実験ではない。**

    答える問い: 「宣言 → プール → 文面 → パーサ → 2 ブロックの採点 は繋がっているか」

    本実行と**同じ関数**で計画を組み(検査もすべて同じ)、固定応答(真値・1 回・2 回・読めない)で
    採点を通す。固定応答のブロックは、4 値のどこにも到達できること(各応答が狙ったカテゴリに
    入ること)の確認であって、**モデルの率ではない。**
    """
    plan = load_composition_plan(config)
    prompts = composition_prompts(plan)
    by_response: dict[str, Any] = {}
    for label, template in DRY_RUN_RESPONSES.items():
        texts = []
        for item in plan.items:
            values = composition.answers(item, plan.reference_lesions)
            texts.append(
                template.format(
                    truth=values["truth"],
                    comp_once=values[composition.REFERENCE_RULES[0]],
                    comp_twice=values[composition.REFERENCE_RULES[1]],
                )
            )
        _, metrics = score_items(plan, texts)
        by_response[label] = metrics[BATCH_NAME]["by_reference_rule"]
    first = plan.items[0]
    return {
        "n_items": len(plan.items),
        "cells": list(plan.cells),
        "gate": dict(plan.gate),
        "pool": dict(plan.pool),
        "by_fixed_response": by_response,
        "example_prompt": {"item_id": first.item_id, "prompt": prompts[first.item_id]},
    }


def print_composition_dry_run(report: Mapping[str, Any]) -> None:
    """T1c の配線確認の報告を出す。**この警告文を本実行に流用しない。**"""
    print("=" * 72)
    print("--dry-run: T1c の配線確認。**実験ではない。**モデルは 1 度も呼ばれていない。")
    print("固定応答に対する分解であって、モデルの率ではない(CLAUDE.md §2)。")
    print("=" * 72)
    print(f"項目: {report['n_items']} 件 / セル: {report['cells']} / D9 の門: {report['gate']}")
    print(f"例: {json.dumps(report['example_prompt'], ensure_ascii=False)}")
    for label, blocks in report["by_fixed_response"].items():
        for rule, block in blocks.items():
            print(
                f"  [{label}] {rule}: correct={block['correct_rate']:.2f} "
                f"rule={block['rule_rate']:.2f} other_error={block['other_error_rate']:.2f} "
                f"parse_fail={block['parse_fail_rate']:.2f}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T1c 合成の探り(PLAN-037 I3)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="モデルを読まずに配線だけ確かめる。ここから出た数値は実験結果ではない",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="成果物の書き出し先。既定は runs/<timestamp>_<experiment.id>/",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        if args.run_dir is not None:
            parser.error("--run-dir は本実行の引数である(--dry-run は何も書かない)")
        print_composition_dry_run(composition_dry_run(config))
        return 0
    execute_composition(config, config_path=args.config, run_dir=args.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
