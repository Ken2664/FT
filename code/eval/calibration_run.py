"""(c) 内容のない入力による較正の本実行と配線確認の入口(PLAN-026 I9)。

答える問い: 「この config が宣言した内容のない入力の全部に、この重みは Yes と No へどれだけの
対数確率を置いたか。その記録が、どのコードの、どの設定の、いつの実行から出たかを後から言えるか」

    python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml --dry-run
    python -m code.eval.calibration_run --config configs/exp_order6b_c.yaml --run-dir runs/<id>

**評価プールを読まない**(内容のない入力は項目でなく、真値を持たない。PLAN-026 §4.9 読み1)。
だから `code/eval/run.py` の経路には入れず、あちらは `eval.calibration` を宣言した config を拒む。
宣言の読み・入力・記録・後処理は `code/eval/calibration.py`、ここは重みと成果物だけを持つ。

**成果物**(`runs/<id>/`): `calibration.json`(入力ごとの `yes_logp` / `no_logp`)/
`metrics.json`(`kind: calibration`。来歴と件数だけで、**率を 1 つも出さない**)/ `log.txt` /
`config.yaml` / git と環境の記録 / 時刻。**`predictions/` には何も書かない**(4 値分解を通らない)。
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
    write_timestamps,
)
from code.config import ConfigError, load_config, require
from code.eval import calibration
from code.eval.battery import t3_comparison
from code.eval.calibration import CalibrationInput, CalibrationSettings
from code.eval.engine import build_engines
from code.eval.forced_choice import ForcedChoiceScorer, collect_forced_choices, declared_top_k
from code.eval.model import GenerationSettings, declared_adapter, load_generation_settings
from code.eval.run import (
    DRY_RUN_FORCED_CHOICES,
    THRESHOLD_SWEEP_ARM_KEY,
    adapter_provenance,
    declared_threshold_sweep_arm,
    dry_run_forced_choice_scorer,
    forced_choice_block,
    forced_choice_lines,
    load_group_templates,
    provenance_lines,
    top_k_line,
)
from code.eval.task_subset import TASK_SUBSET_KEY, declared_task_subset


@dataclass(frozen=True)
class CalibrationPlan:
    """この較正の run の宣言と、尋ねる入力の全部。

    答える問い: 「この run は、どの記号の、どの文面の組の、どの文字列を尋ねるか」

    `top_k` は最初の出力位置の上位 k の宣言(`forced_choice.declared_top_k`。None = 記録しない。
    PLAN-026 §4.10 読み1 —— 較正の forward も強制選択の forward である)。
    """

    settings: CalibrationSettings
    inputs: tuple[CalibrationInput, ...]
    top_k: int | None


def load_calibration_plan(config: Mapping[str, Any]) -> CalibrationPlan:
    """宣言を読み、他の経路の宣言と重なっていないことを確かめ、入力を組む。**重みを読まない。**

    答える問い: 「この config は、較正の run として噛み合っているか。尋ねる入力は何か」

    **止める食い違い(どれも重みを読む前・run ディレクトリを作る前。PLAN-026 §4.9 読み4)**:
    較正の宣言が無い / 宣言が壊れている(`calibration.declared_calibration`)/
    `eval.task_subset` や `eval.threshold_sweep_arm` を同時に宣言した(プールを解く経路の宣言が
    較正の run で黙って効かない)/ テンプレート集合に強制選択の群が無い・二値群でない category がある /
    同じ文面が 2 度出る / 上位 k の宣言が壊れている。
    """
    settings = calibration.declared_calibration(config)
    if settings is None:
        raise ConfigError(
            f"この入口は {calibration.CALIBRATION_KEY} を宣言した config だけを解く(PLAN-026 §4.9 読み1)。"
            "評価プールを解く run は python -m code.eval.run である。"
        )
    if declared_task_subset(config) is not None:
        raise ConfigError(
            f"{TASK_SUBSET_KEY} が宣言されているが、較正の run は評価プールを読まないので絞りが効かない"
        )
    if declared_threshold_sweep_arm(config) is not None:
        raise ConfigError(
            f"{THRESHOLD_SWEEP_ARM_KEY} が宣言されているが、較正の run は掃引のプールを読まない"
        )
    templates_by_arm = {
        arm.name: load_group_templates(config, t3_comparison.GROUP, arm.template_set)
        for arm in settings.arms
    }
    inputs = calibration.calibration_inputs(settings, templates_by_arm)
    return CalibrationPlan(settings=settings, inputs=tuple(inputs), top_k=declared_top_k(config))


def score_calibration(plan: CalibrationPlan, scorer: ForcedChoiceScorer) -> list[dict[str, Any]]:
    """入力を 1 度ずつ採点器に渡し、記録の行にする。

    答える問い: 「各入力で、モデルは Yes と No へどれだけの対数確率を置いたか」

    採点器は `collect_forced_choices` を通す(本数と上位 k の個数の検査を 1 箇所に集める。
    `run.py` と同じ規約)。
    """
    choices = collect_forced_choices(
        [entry.prompt for entry in plan.inputs], scorer, top_k=plan.top_k
    )
    return calibration.calibration_rows(plan.inputs, choices)


def calibration_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    plan: CalibrationPlan,
    *,
    run_id: str,
    timing: Mapping[str, Any],
    adapter: Mapping[str, Any],
    forced_choice_candidates: Mapping[bool, Mapping[str, int | None]] | None = None,
) -> dict[str, Any]:
    """較正の run の metrics.json を組む。**率を 1 つも出さない。**

    答える問い: 「この較正の記録が、どの重みの、どの設定の、どの記号と文面の組から出たかを、
    この 1 ファイルだけで言えるか」

    来歴の欄(`generation`・`adapter`・`timing`・`forced_choice`・`preamble`)は評価プールを解く
    経路と同じ形で書く。`pool`・`coverage`・`task_subset` は置かない(プールを読まない)。
    """
    return {
        "run_id": run_id,
        "kind": calibration.CALIBRATION_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "seed": adapter["seed"],
        "adapter": adapter["adapter"],
        "adapter_train_run_id": adapter["train_run_id"],
        "adapter_note": adapter["note"],
        "generation": settings.as_dict(),
        "preamble": calibration.calibration_preamble_record(plan.settings.preamble_lines),
        "timing": dict(timing),
        "calibration": calibration.calibration_block(plan.settings, plan.inputs),
        **forced_choice_block(forced_choice_candidates, top_k=plan.top_k),
    }


def calibration_report_lines(payload: Mapping[str, Any]) -> list[str]:
    """較正の run の log.txt と標準出力に出す行。**率を出さない。**

    答える問い: 「この較正の run は、どの重みで、どの記号を、どの文面の組に何件置いたか」
    """
    block = payload["calibration"]
    return [
        *provenance_lines(payload),
        calibration.calibration_preamble_line(payload["preamble"]),
        timing_line(payload["timing"]),
        *forced_choice_lines(payload),
        f"較正: 記号={json.dumps(block['symbols'], ensure_ascii=False)} 入力={block['n_rows']} 件"
        f" -> {block['rows_file']}",
        *(arm_line(arm) for arm in block["arms"]),
        f"補正: {block['bias']}",
        f"注意: {block['note']}",
    ]


def arm_line(arm: Mapping[str, Any]) -> str:
    """腕 1 つの 1 行(log.txt と dry-run の報告)。"""
    return (
        f"[{arm['name']}] template_set={arm['template_set']} preamble={arm['preamble']} "
        f"category={arm['categories']} 並び={arm['n_orders']} 通り n={arm['n_rows']}"
    )


def write_calibration_rows(
    run_dir: Path, run_id: str, plan: CalibrationPlan, rows: Sequence[Mapping[str, Any]]
) -> Path:
    """calibration.json を書く。**これは実験の記録である**(--dry-run は書かない)。"""
    path = run_dir / calibration.ROWS_FILENAME
    payload = calibration.rows_payload(run_id, plan.settings, rows)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def execute_calibration(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path | None,
    scorer: ForcedChoiceScorer | None = None,
    now: datetime | None = None,
) -> Path:
    """較正の本実行。成果物を `runs/<id>/` に書き、その dir を返す。

    答える問い: 「この較正の記録が、どのコードの、どの設定の、いつの実行から出たかを後から言えるか」

    **検査はすべて run ディレクトリを作る前・重みを読む前に済ませる**(`load_calibration_plan`・
    生成設定・アダプタの出どころ)。`scorer` は差し替え可能で、**None のときだけ重みを読む**
    (`build_engines`。生成器は使わない)。来歴を forward の前に書き、区間を 3 つに分けて測るのは
    `run.execute` と同じ理由である。
    """
    plan = load_calibration_plan(config)
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
    forced_choice_candidates: Mapping[bool, Mapping[str, int | None]] | None = None
    if scorer is None:
        engines = build_engines(settings, adapter=adapter["adapter"], top_k=plan.top_k)
        scorer = engines.scorer
        forced_choice_candidates = engines.forced_choice_candidates
    model_load_seconds = elapsed_seconds(load_started)

    generation_started = monotonic_seconds()
    rows = score_calibration(plan, scorer)
    generation_seconds = elapsed_seconds(generation_started)

    write_calibration_rows(target, target.name, plan, rows)
    ended = utc_now()
    payload = calibration_payload(
        config,
        settings,
        plan,
        run_id=target.name,
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=model_load_seconds,
            generation_seconds=generation_seconds,
            n_items=len(rows),
        ),
        adapter=adapter,
        forced_choice_candidates=forced_choice_candidates,
    )
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=ended)
    lines = calibration_report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def calibration_dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    """重みを読まずに較正の経路の配線を確かめる。**実験ではない。**

    答える問い: 「宣言 → テンプレート → 入力 → 記録の組み立て は繋がっているか」

    本実行と**同じ関数**で入力を組み(検査もすべて同じ)、定数の答え(`DRY_RUN_FORCED_CHOICES`)で
    記録の組み立てを 1 度ずつ通す。例の文面は (腕 × category × 記号) ごとに最初の並びの 1 つ
    (空文字の差し込みが目で確かめられるよう、報告では JSON の文字列で出す)。**率は出さない。**
    """
    plan = load_calibration_plan(config)
    rows_by_response = {
        label: len(score_calibration(plan, dry_run_forced_choice_scorer(answer, top_k=plan.top_k)))
        for label, answer in DRY_RUN_FORCED_CHOICES.items()
    }
    examples: dict[str, str] = {}
    for entry in plan.inputs:
        key = f"{entry.arm}/{entry.category}/{json.dumps(entry.symbol)}"
        examples.setdefault(key, entry.prompt)
    return {
        "n_rows": len(plan.inputs),
        "preamble": calibration.calibration_preamble_record(plan.settings.preamble_lines),
        "calibration": calibration.calibration_block(plan.settings, plan.inputs),
        "forced_choice_top_k": plan.top_k,
        "rows_by_response": rows_by_response,
        "example_prompts": examples,
    }


def print_calibration_dry_run(report: Mapping[str, Any]) -> None:
    """較正の配線確認の報告を出す。**この警告文を本実行に流用しない。**"""
    print("=" * 72)
    print("--dry-run: 較正の配線確認。**実験ではない。**モデルは1度も呼ばれていない。")
    print("ここに出る数値は組合せ論的な件数であって実験結果ではない(CLAUDE.md §2)。")
    print("=" * 72)
    block = report["calibration"]
    print(f"入力: {report['n_rows']} 件 / 記号: {json.dumps(block['symbols'], ensure_ascii=False)}")
    print(calibration.calibration_preamble_line(report["preamble"]))
    print(top_k_line(report["forced_choice_top_k"]))
    for arm in block["arms"]:
        print(arm_line(arm))
    print(f"記録の行数(定数の答えで組み立て): {report['rows_by_response']}")
    for key, prompt in report["example_prompts"].items():
        print(f"  {key}: {json.dumps(prompt, ensure_ascii=False)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="(c) 内容のない入力による較正(PLAN-026 I9)")
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
            # 黙って無視すると「書いたつもり」が残る。--dry-run は何も書かない。
            parser.error("--run-dir は本実行の引数である(--dry-run は何も書かない)")
        print_calibration_dry_run(calibration_dry_run(config))
        return 0
    execute_calibration(config, config_path=args.config, run_dir=args.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
