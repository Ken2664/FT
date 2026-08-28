"""桁数掃引の入口(PLAN-001 §4.1.1 の手続き2)。

答える問い: 「素のモデルは、被演算子の上限 M をどこまで上げても加算を解けるか」

    python -m code.eval.sweep --config configs/exp042.yaml --run-dir runs/20260901_143022_sweep

**出すのは `M -> correct_rate` の表だけである。**§4.1.1 の手続きは4段あり、
このモジュールが担うのは 2 だけ:

  1. R(M) を定める                                   code/eval/battery/magnitude_sweep.py
  2. 素のモデルに M を掃きながら解かせる             ← このモジュール
  3. 表から M* を決める                              **人間が決める**(ADR-041)
  4. D_ext = R(M*) のうち主域と交わらない部分        **未実装**

**M* の決定規則は ADR-041 決定3 が凍結している**(値ではなく規則を凍結した):
**`M` を小さい順に見て、初めて `θ` を割った水準の1つ下**を採り、**それより上で
回復しても採らない**(規則2)。2026-08-28 まで PLAN-001 §4.1.1 は「`θ` を満たす
最大の `M`」と書いており、**崖の向こうで偶然 `θ` を超えた水準を拾う穴があった。**

**それでもこの CLI は M* を出さない。**`θ` の値がまだ無く(ADR-041 決定5)、
表を読んで M* を置くのは人間だからである。決まったら
`eval.extrapolation_radius` と `eval.extrapolation_run_id` に入る
(`configs/template.yaml`)。出力すると、その値が「実測で決まった」ように
見えてしまう。

**生成は `code/eval/generate.py` を通る。**`code/eval/run.py`(本実行)と
同じ関数・同じ生成設定である(PLAN-004 §4.2)。2箇所で別々に生成すると、
掃引と本実行で生成設定が食い違っても誰も気づかない —— そのとき M* は、
本実験とは違う設定で測った correct_rate から決まってしまう。

**採点は主要参照規則の1ブロックだけ**を出す(本実行は参照規則ごとに
ブロックを持つ。ADR-016)。R(M) は M を上げると `arb` の定義域 t in [2,198] を
越えるため、項目ごとに「定義されている参照規則」が変わる(ADR-020 決定2)。
M ごとに規則集合が動く表は M 間の比較にならない。**4値はいずれにせよ
4つ揃って出る**(CLAUDE.md §6)—— correct_rate は参照規則に依存しない。

**素の算術能力の測定であって病変の測定ではない。**このハーネスは LoRA
アダプタを読まない(`code/eval/run.py` の NO_ADAPTER_NOTE)。掃引は
`model.name` の重みそのものに対して回す。
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
from code.config import load_config, require
from code.data_gen.battery_items import Item
from code.eval.battery import magnitude_sweep, numeric_sum
from code.eval.battery.magnitude_sweep import SweepPlan
from code.eval.generate import Generator, build_generator, collect_responses
from code.eval.model import GenerationSettings, load_generation_settings
from code.eval.run import NO_ADAPTER_NOTE, parse_numeric_response, prediction_record
from code.eval.scoring import RateBreakdown, score, validate_reference_rule
from code.lesion import Lesion, reference_lesions_from_config

# metrics.json の種別。本実行(code/eval/run.py の EVAL_KIND)と形が違う ——
# あちらは群ごとのバッチ、こちらは M ごとの点である。集約側が見分けられるようにする。
SWEEP_KIND = "magnitude_sweep"

# predictions/ のファイル名。M ごとに分ける。
PREDICTIONS_PREFIX = "magnitude"


@dataclass(frozen=True)
class RadiusResult:
    """1つの M に対する測定。

    答える問い: 「この M で、素のモデルの応答は4値にどう分かれたか」
    """

    radius: int
    reference_rule: str
    breakdown: RateBreakdown
    predictions: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        """metrics.json の1行。**4値を必ず揃えて出す**(CLAUDE.md §6)。"""
        return {
            "radius": self.radius,
            "reference_rule": self.reference_rule,
            **self.breakdown.as_dict(),
        }


def sweep_prompts(items: Sequence[Item], config: Mapping[str, Any]) -> dict[str, str]:
    """掃引項目の質問文を組む。

    答える問い: 「掃引はモデルに何と尋ねるか」

    **文面は訓練書式**(`data.prompt_template`)である。掃引項目は T1(裸の
    計算式)であり、T1 の書式は評価用テンプレート集合ではなく訓練側から
    来る(`code/eval/battery/numeric_sum.py` 冒頭の注記、検査6)。
    `code/eval/run.py` の `load_group_templates` が bare_sum に対して呼ぶのと
    同じ関数を通すので、掃引と本実行で T1 の書式が割れることはない。
    """
    templates = numeric_sum.bare_sum_templates(config)
    return {item.item_id: numeric_sum.render_prompt(item, templates) for item in items}


def sweep_one(
    radius: int,
    *,
    plan: SweepPlan,
    config: Mapping[str, Any],
    generator: Generator,
    reference_lesions: Mapping[str, Lesion],
    reference_rule: str,
    elicitation: str,
    pool_id: str,
) -> RadiusResult:
    """1つの M を測る。**これは実験結果である。**

    答える問い: 「この M の R(M) から引いた n 件を、素のモデルは何件正答するか」

    項目の抽出は `magnitude_sweep.build_items` にある。取れなければ
    `InsufficientPairsError` で止まる —— **少ない本数で表を作らない。**
    M ごとに n が違う表は correct_rate の M 間比較が成立しない(§4.1.1 の3)。
    """
    items = magnitude_sweep.build_items(
        radius,
        n_items=plan.n_items_per_radius,
        seed=plan.seed,
        pool_id=pool_id,
        reference_lesions=reference_lesions,
    )
    prompts = sweep_prompts(items, config)
    texts = collect_responses([prompts[item.item_id] for item in items], generator)
    responses = [
        numeric_sum.to_response(
            item, parse_numeric_response(text, elicitation), reference_lesions
        )
        for item, text in zip(items, texts, strict=True)
    ]
    records = [
        prediction_record(
            item,
            prompt=prompts[item.item_id],
            response=text,
            item_response=response,
            reference_rule=reference_rule,
        )
        for item, text, response in zip(items, texts, responses, strict=True)
    ]
    return RadiusResult(
        radius=radius,
        reference_rule=reference_rule,
        breakdown=score(responses, reference_rule),
        predictions=records,
    )


def sweep(config: Mapping[str, Any], *, generator: Generator) -> list[RadiusResult]:
    """config が宣言する M をすべて測る。

    答える問い: 「M を上げていくと correct_rate はどこで落ちるか」

    重みを読み直さない(`generator` は呼び出し側が1つ作る)。M ごとに
    読み直すと、M の違いと生成設定の揺れが分離できなくなる。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    reference_rule = require(config, "eval.reference_rule")
    elicitation = require(config, "eval.elicitation")
    pool_id = require(config, "data.pool_id")
    reference_lesions = reference_lesions_from_config(config)
    validate_reference_rule(
        reference_rule, reference_lesions[reference_rule], list(reference_lesions)
    )
    return [
        sweep_one(
            radius,
            plan=plan,
            config=config,
            generator=generator,
            reference_lesions=reference_lesions,
            reference_rule=reference_rule,
            elicitation=elicitation,
            pool_id=pool_id,
        )
        for radius in plan.radii
    ]


def correct_rate_table(results: Sequence[RadiusResult]) -> dict[str, float]:
    """`M -> correct_rate` の対応表。**この表がこの CLI の成果物である。**

    答える問い: 「どの M まで素のモデルは加算を解けているか」

    ここから M* を決めるのは人間である(モジュール冒頭)。閾値の適用を
    この関数に足さないこと。
    """
    return {str(result.radius): result.breakdown.correct_rate for result in results}


def total_items(results: Sequence[RadiusResult]) -> int:
    """掃引全体で解いた項目数。

    答える問い: 「この掃引は何項目を解いたか」

    水準ごとの項目数は同一である(`eval.magnitude_sweep.n_items_per_radius`)が、
    ここでは**実際に採点した件数を数える** —— 宣言した値を掛け算すると、
    抽出が足りずに水準が短くなったときに秒数の分母だけが嘘になる。
    """
    return sum(result.breakdown.n_items for result in results)


def metrics_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    plan: SweepPlan,
    results: Sequence[RadiusResult],
    *,
    run_id: str,
    timing: Mapping[str, Any],
) -> dict[str, Any]:
    """metrics.json の中身を組む。

    答える問い: 「この表が、どの重みの、どの設定の、どの抽出から出たかを、
    この1ファイルだけで言えるか」

    `timing` は `execute` が測った区間である(`code/eval/run.py` と同じ形)。
    掃引は本実行と**同じ生成経路**を通るので、まとめ幅あたりの速度も同じ
    土俵で読める(ADR-040 決定6)。
    """
    return {
        "run_id": run_id,
        "kind": SWEEP_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "adapter": None,
        "adapter_note": NO_ADAPTER_NOTE,
        "generation": settings.as_dict(),
        "elicitation": require(config, "eval.elicitation"),
        "reference_rule": require(config, "eval.reference_rule"),
        "pool_id": require(config, "data.pool_id"),
        "sweep": plan.as_dict(),
        "timing": timing,
        "correct_rate_by_radius": correct_rate_table(results),
        "by_radius": [result.as_dict() for result in results],
    }


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。

    答える問い: 「この掃引は何を測り、何を測っていないのか」

    **M* を出さないことを毎回書く。**表だけを見た人が「掃引が上限を出した」と
    読むのを防ぐ(承認待ち #9 / #15)。
    """
    generation = payload["generation"]
    lines = [
        f"run_id: {payload['run_id']}",
        f"model: {generation['model_name']} @ {generation['revision']} "
        f"({generation['dtype']} on {generation['device']})",
        f"生成: max_new_tokens={generation['max_new_tokens']} "
        f"temperature={generation['temperature']} do_sample={generation['do_sample']} "
        f"chat_template={generation['chat_template']} "
        f"batch_size={generation['batch_size']}",
        f"注意: {payload['adapter_note']}",
        f"掃引: radii={payload['sweep']['radii']} "
        f"n_items_per_radius={payload['sweep']['n_items_per_radius']} "
        f"seed={payload['sweep']['seed']}",
        f"参照規則: {payload['reference_rule']} / 引き出し方: {payload['elicitation']}",
        timing_line(payload["timing"]),
        "",
        f"{'M':>8}  {'n':>5}  {'correct':>8}  {'rule':>8}  {'other_err':>10}  {'parse_fail':>10}",
    ]
    for row in payload["by_radius"]:
        lines.append(
            f"{row['radius']:>8}  {row['n_items']:>5}  {row['correct_rate']:>8.4f}  "
            f"{row['rule_rate']:>8.4f}  {row['other_error_rate']:>10.4f}  "
            f"{row['parse_fail_rate']:>10.4f}"
        )
    lines.extend(
        [
            "",
            "この表から外挿域の上限 M* は決まらない。M* の決定規則は ADR-041 決定3 に",
            "あり(初めて θ を割った水準の1つ下)、θ の値と格子点は未決である(同 決定5)。",
            "表を読んで M* を置くのは人間である(PLAN-001 §4.1.1 の3)。",
        ]
    )
    return lines


def execute(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path | None,
    generator: Generator | None = None,
    now: datetime | None = None,
) -> Path:
    """掃引を回し、成果物を `runs/<id>/` に書く。

    答える問い: 「この表が、どのコードの、どの設定の、いつの実行から出たかを
    後から言えるか」

    来歴を生成の前に書くこと・`generator` を差し替え可能にすることは
    `code/eval/run.py` の `execute` と同じ規約である(PLAN-004 §4.3 の1)。
    """
    settings = load_generation_settings(config)
    plan = magnitude_sweep.load_sweep_plan(config)
    started = now or utc_now()
    run_started = monotonic_seconds()
    target = prepare_run_dir(config, explicit=run_dir, now=started)
    write_config_copy(target, config_path)
    write_git_sha(target)
    write_env(target)

    load_started = monotonic_seconds()
    ready = generator or build_generator(settings)
    model_load_seconds = elapsed_seconds(load_started)

    generation_started = monotonic_seconds()
    results = sweep(config, generator=ready)
    generation_seconds = elapsed_seconds(generation_started)

    for result in results:
        write_predictions(target, f"{PREDICTIONS_PREFIX}_M{result.radius}", result.predictions)
    ended = utc_now()
    payload = metrics_payload(
        config,
        settings,
        plan,
        results,
        run_id=target.name,
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=model_load_seconds,
            generation_seconds=generation_seconds,
            n_items=total_items(results),
        ),
    )
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=ended)
    lines = report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def dry_run_summary(config: Mapping[str, Any]) -> dict[str, Any]:
    """モデルを読まずに、掃引する M と項目が組めることだけ確かめる。

    答える問い: 「この config で R(M) から n 件を引けるか」

    **correct_rate は出ない。**ここに出るのは組合せ論的な計数であって
    実験結果ではない(CLAUDE.md §2)。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    pool_id = require(config, "data.pool_id")
    reference_lesions = reference_lesions_from_config(config)
    by_radius = {}
    for radius in plan.radii:
        items = magnitude_sweep.build_items(
            radius,
            n_items=plan.n_items_per_radius,
            seed=plan.seed,
            pool_id=pool_id,
            reference_lesions=reference_lesions,
        )
        by_radius[str(radius)] = {
            "domain_size": magnitude_sweep.domain_size(radius),
            "n_items": len(items),
            "item_ids": [item.item_id for item in items],
            "prompts": list(sweep_prompts(items, config).values()),
        }
    return {
        "sweep": plan.as_dict(),
        "reference_rules": sorted(reference_lesions),
        "by_radius": by_radius,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="桁数掃引(PLAN-001 §4.1.1 の手続き2)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="成果物の書き出し先。既定は runs/<timestamp>_<experiment.id>/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="モデルを読まずに、掃引する M と項目の組み立てだけ確かめる",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        print("=" * 72)
        print("--dry-run: 配線確認。**実験ではない。**モデルは1度も呼ばれていない。")
        print("ここに出るのは項目の組み立てだけであり、correct_rate は測っていない。")
        print("=" * 72)
        print(json.dumps(dry_run_summary(config), ensure_ascii=False, indent=2))
        return 0

    execute(config, config_path=args.config, run_dir=args.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
