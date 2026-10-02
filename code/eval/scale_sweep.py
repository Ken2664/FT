"""LoRA のスケール s の掃引の入口(PLAN-037 I7・ADR-118 決定 D7 (c)・D8・D9)。

答える問い: 「同じアダプタの効きを、事前学習の重み(s = 0)からアダプタそのもの(s = 1)の間で動かしたとき、
T1・T2 の `rule_rate` は s にどう応えるか。その記録が、どのコードの、どの設定の、いつの実行から出たか
を s ごとに後から言えるか」

    python -m code.eval.scale_sweep --config <config> --dry-run
    python -m code.eval.scale_sweep --config <config> [--run-dir-prefix runs/<名前>]

**重みとアダプタを 1 回だけ読み**(記録では読み込みが 95.9 秒、680 項目の生成が 30.6 秒。PLAN-037 §5.2)、
宣言した s の水準の**順に**掛け替えて、**s ごとに別の run ディレクトリ**(`<接頭辞>_s<水準>`)を書く。
各 run の成果物(`config.yaml`・`metrics.json`・`predictions/`)の形は固定オフセットの評価と同じ
(`kind: battery_eval`)で、`metrics.json` に **`lora_scale`**(s)・`signature_gate`・`scale_sweep` が足される。
解く項目は `eval.task_subset`(T1・T2 だけ。D8)の宣言で絞る。s の水準は `eval.scale_sweep.levels`
(宣言のまま・結果を見て足し引きしない)。

**主解析に混ざらない**(PLAN-037 §3.3 の 2): `eval.task_subset` を宣言する run は `aggregate.py` が止め、
`lora_scale` が 1 でも null でもない run は `frame.py` が止め `aggregate.py` が行を分ける(I8)。

**D9 の門**: 凍結の前に `p2`・`p2d` で署名を読む取り違えを、重みを読む前・run ディレクトリを作る前に
止める(`signature_gate.check_signature_gate`)。**s = 1 だけを宣言しても門は掛ける**(宣言の入口で見る。
D9 の文言は「T1c と s ≠ 1 の run」で、s = 1 の水準だけの掃引は PLAN に明記が無い。止める側に倒した)。

**検査はすべて重みを読む前・run ディレクトリを作る前に済ませる**(宣言・プールの種類・絞り・宣言どうしの
重なり・門・書き出し先の衝突)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from code.artifacts import (
    METRICS_FILE,
    RUNS_ROOT,
    elapsed_seconds,
    monotonic_seconds,
    prepare_run_dir,
    run_id_for,
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
from code.eval import signature_gate
from code.eval.calibration import declared_calibration
from code.eval.generate import Generator, generator_from_model
from code.eval.model import (
    GenerationSettings,
    apply_lora_scale,
    declared_adapter,
    declared_scale_sweep_levels,
    load_generation_settings,
    load_model_and_tokenizer,
)
from code.eval.preamble import declared_preamble, preamble_record
from code.eval.run import (
    BatchResult,
    adapter_provenance,
    check_pool_kind,
    coverage_record,
    declared_threshold_sweep_arm,
    evaluate_pool,
    metrics_payload,
    pool_items_path,
    pool_record,
    pool_subset_record,
    read_pool_manifest,
    report_lines,
    total_items,
)
from code.eval.task_subset import declared_task_subset

# D8: 掃引で解くタスク型。T1・T2 だけ(`05_STATISTICS.md` §4 の副次の定義 = T1・T2 × 既知性の rule_rate)。
SWEEP_TASK_TYPES: frozenset[str] = frozenset({"t1", "t2"})

SCALE_SWEEP_NOTE = (
    "LoRA のスケール s の掃引の 1 水準(PLAN-037 D7 (c))。lora_scale = 載せたアダプタの効きの倍率で、"
    "0 = 素の重み・1 = アダプタそのもの(peft の LoraLayer.set_scale で絶対値を置く)。"
    "この run は主要検定・E1 の入力に入らない(frame.py は s ≠ 1 で止まる)。判定・解釈を出さない。"
)


@dataclass(frozen=True)
class ScaleSession:
    """重みを 1 度読んだ後の「s を掛け替える・解く」操作の組。

    答える問い: 「同じ重みに s を順に掛け替えて、そのつど同じ項目を解けるか」

    `set_scale` が掛けた LoRA 層の数を返す。`generator` は呼ぶ時点の重み(= 掛けた s)で解く。
    テストはここに置き物を渡し、重みを読まずに掛け替えの順序と記録を見る。
    """

    set_scale: Callable[[float], int]
    generator: Generator


def build_scale_session(settings: GenerationSettings, *, adapter: str) -> ScaleSession:
    """重みとアダプタを 1 回読み、s を掛け替える操作を返す。**ここだけが重みを読む。**

    答える問い: 「アダプタを載せたモデルを 1 つ持ち、その LoRA の係数だけを動かせるか」

    強制選択の採点器は作らない(掃引は T1・T2 の自由生成だけ。D8)。
    """
    model, tokenizer = load_model_and_tokenizer(settings, adapter=adapter)
    return ScaleSession(
        set_scale=lambda scale: apply_lora_scale(model, scale),
        generator=generator_from_model(model, tokenizer, settings),
    )


def level_label(scale: float) -> str:
    """s を run ディレクトリ名に使える文字列にする(`0.5` → `0p5`、`1.0` → `1`)。

    答える問い: 「この水準の run は、どの名前のディレクトリに書くか」
    """
    text = f"{scale:g}"
    return text.replace(".", "p").replace("-", "m").replace("+", "")


def level_run_dir(
    config: Mapping[str, Any], scale: float, *, prefix: Path | None, now: datetime
) -> Path:
    """この水準の run ディレクトリ。接頭辞を渡せば `<接頭辞>_s<水準>`、無ければ `runs/<id>_s<水準>`。

    答える問い: 「s ごとの run は、重ならない別々の場所に書かれるか」
    """
    label = f"s{level_label(scale)}"
    if prefix is not None:
        return prefix.parent / f"{prefix.name}_{label}"
    return RUNS_ROOT / f"{run_id_for(config, now=now)}_{label}"


@dataclass(frozen=True)
class ScaleSweepPlan:
    """この掃引が解く項目・水準・来歴(重みを読む前に組む)。

    答える問い: 「この掃引は、どの水準を、どのプールの、どの項目で、どの門を通って解くか」
    """

    levels: tuple[float, ...]
    pool: Mapping[str, Any]
    coverage: Mapping[str, Any]
    preamble: Mapping[str, Any] | None
    task_subset: Mapping[str, Any] | None
    gate: Mapping[str, Any]


def refuse_conflicting_declarations(config: Mapping[str, Any]) -> None:
    """掃引の run で黙って効かなくなる宣言を止める。

    答える問い: 「この config は、s の掃引として他の経路の宣言と重なっていないか」
    """
    if declared_threshold_sweep_arm(config) is not None:
        raise ConfigError("eval.threshold_sweep_arm と eval.scale_sweep は同時に宣言できない")
    if declared_calibration(config) is not None:
        raise ConfigError("eval.calibration と eval.scale_sweep は同時に宣言できない")
    if (config.get("eval") or {}).get("composition") is not None:
        raise ConfigError("eval.composition と eval.scale_sweep は同時に宣言できない(T1c は s を掛けない)")


def require_sweep_task_subset(config: Mapping[str, Any]) -> None:
    """掃引が解くのは T1・T2 だけ(D8)。`eval.task_subset` の宣言が無い・外れていれば止める。

    答える問い: 「この掃引は、T1・T2 だけを解く宣言になっているか」

    宣言が無いとプール全体(比較群・特異性対照まで)を s ごとに解く。それは D8 の外であり、
    強制選択の採点器もこの入口は作らない。
    """
    declared = declared_task_subset(config)
    if declared is None:
        raise ConfigError(
            "eval.scale_sweep は eval.task_subset(T1・T2 だけ。PLAN-037 D8)の宣言を要する"
            "(無いとプール全体を s ごとに解く)"
        )
    extra = sorted(set(declared) - SWEEP_TASK_TYPES)
    if extra:
        raise ConfigError(
            f"eval.task_subset に掃引の対象外のタスク型 {extra} がある(掃引は "
            f"{sorted(SWEEP_TASK_TYPES)} だけ。PLAN-037 D8)"
        )


def load_scale_sweep_plan(config: Mapping[str, Any]) -> ScaleSweepPlan:
    """宣言を読み、噛み合わせと門を確かめ、項目と来歴を揃える。**重みを読まない。**

    答える問い: 「この config は、s の掃引として噛み合っているか。通してよい run か」
    """
    levels = declared_scale_sweep_levels(config)
    if levels is None:
        raise ConfigError(
            "この入口は eval.scale_sweep を宣言した config だけを解く(PLAN-037 I7)。"
            "固定オフセットの評価は python -m code.eval.run である。"
        )
    refuse_conflicting_declarations(config)
    require_sweep_task_subset(config)
    check_pool_kind(config, read_pool_manifest(config), threshold_sweep=False)
    gate = signature_gate.check_signature_gate(
        config,
        adapter=declared_adapter(config),
        condition=require(config, "lesion.condition"),
        what="スケールの掃引",
    )
    return ScaleSweepPlan(
        levels=levels,
        pool=pool_record(config, pool_items_path(config)),
        coverage=coverage_record(config),
        preamble=preamble_record(declared_preamble(config)),
        task_subset=pool_subset_record(config),
        gate=gate,
    )


def refuse_existing_runs(targets: Sequence[Path]) -> None:
    """書き出し先に前の run の記録があれば止める(掛け替えのやり直しで上書きしない)。

    答える問い: 「この掃引は、既にある run の `metrics.json` を黙って書き換えないか」
    """
    existing = [str(path) for path in targets if (path / METRICS_FILE).exists()]
    if existing:
        raise ConfigError(f"書き出し先に metrics.json が既にある(上書きしない): {existing}")


def scale_payload(
    base: dict[str, Any],
    *,
    plan: ScaleSweepPlan,
    scale: float,
    index: int,
    n_layers: int,
    shared_load_seconds: float,
) -> dict[str, Any]:
    """固定オフセットの `metrics.json` に、s・門・掃引の記録を足す。

    答える問い: 「この run が、掃引のどの水準の、いくつの層に s を置いた記録か」

    `lora_scale` は float(`composition_table.py` が同じ名前を読む)。
    """
    return {
        **base,
        "lora_scale": scale,
        "signature_gate": dict(plan.gate),
        "scale_sweep": {
            "levels": list(plan.levels),
            "level_index": index,
            "n_lora_layers_scaled": n_layers,
            "shared_model_load_seconds": round(shared_load_seconds, 3),
            "note": SCALE_SWEEP_NOTE,
        },
    }


def scale_report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。**判定・解釈の文言を出さない。**"""
    sweep = payload["scale_sweep"]
    return [
        f"LoRA のスケール s: {payload['lora_scale']}(水準 {sweep['level_index'] + 1}/{len(sweep['levels'])}: "
        f"{sweep['levels']} / 掛けた LoRA 層: {sweep['n_lora_layers_scaled']})",
        f"D9 の門: {json.dumps(payload['signature_gate'], ensure_ascii=False)}",
        f"注意: {sweep['note']}",
        *report_lines(payload),
    ]


def evaluate_level(
    config: Mapping[str, Any], session: ScaleSession
) -> list[BatchResult]:
    """今の s で T1・T2 を解く。解き方は固定オフセットの評価と同じ関数(`evaluate_pool`)。"""
    return evaluate_pool(config, generator=session.generator, scorer=None)


def execute_scale_sweep(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir_prefix: Path | None,
    session: ScaleSession | None = None,
    now: datetime | None = None,
) -> list[Path]:
    """掃引の本実行。水準ごとに run ディレクトリを書き、書いた順の dir を返す。

    答える問い: 「s ごとの記録が、どのコードの、どの設定の、いつの実行から出たかを後から言えるか」

    **検査はすべて重みを読む前・run ディレクトリを作る前**(`load_scale_sweep_plan`・生成設定・
    アダプタの出どころ・書き出し先の衝突)。`session` は差し替え可能で、**None のときだけ重みを読む**
    (`build_scale_session`)。来歴は各 run の最初に書く(生成が途中で落ちても、そこまでの水準の記録が残る)。
    **s の水準は宣言の順に掛け替える。**各 run の `timing.model_load_seconds` は、最初の水準が共有の
    読み込み秒数、以降は s を掛け替えた秒数(共有の秒数は `scale_sweep.shared_model_load_seconds`)。
    """
    plan = load_scale_sweep_plan(config)
    settings = load_generation_settings(config)
    adapter = adapter_provenance(
        declared_adapter(config), condition=require(config, "lesion.condition")
    )
    started = now or utc_now()
    targets = [
        level_run_dir(config, scale, prefix=run_dir_prefix, now=started) for scale in plan.levels
    ]
    refuse_existing_runs(targets)

    load_started = monotonic_seconds()
    if session is None:
        session = build_scale_session(settings, adapter=str(adapter["adapter"]))
    shared_load_seconds = elapsed_seconds(load_started)

    written: list[Path] = []
    for index, (scale, target) in enumerate(zip(plan.levels, targets, strict=True)):
        level_started = utc_now()
        level_clock = monotonic_seconds()
        target = prepare_run_dir(config, explicit=target, now=level_started)
        write_config_copy(target, config_path)
        write_git_sha(target)
        write_env(target)

        switch_started = monotonic_seconds()
        n_layers = session.set_scale(scale)
        switch_seconds = elapsed_seconds(switch_started)

        generation_started = monotonic_seconds()
        results = evaluate_level(config, session)
        generation_seconds = elapsed_seconds(generation_started)

        for result in results:
            write_predictions(target, result.name, result.predictions)
        ended = utc_now()
        base = metrics_payload(
            config,
            settings,
            results,
            run_id=target.name,
            pool=plan.pool,
            coverage=plan.coverage,
            adapter=adapter,
            timing=timing_record(
                started=level_started,
                ended=ended,
                total_seconds=elapsed_seconds(level_clock)
                + (shared_load_seconds if index == 0 else 0.0),
                model_load_seconds=shared_load_seconds if index == 0 else switch_seconds,
                generation_seconds=generation_seconds,
                n_items=total_items(results),
            ),
            preamble=plan.preamble,
            task_subset=plan.task_subset,
            forced_choice_candidates=None,
        )
        payload = scale_payload(
            base,
            plan=plan,
            scale=scale,
            index=index,
            n_layers=n_layers,
            shared_load_seconds=shared_load_seconds,
        )
        write_metrics(target, payload)
        write_timestamps(target, started=level_started, ended=ended)
        lines = scale_report_lines(payload)
        write_log(target, lines)
        for line in lines:
            print(line)
        written.append(target)
    return written


def scale_sweep_dry_run(
    config: Mapping[str, Any], *, run_dir_prefix: Path | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """重みを読まずに掃引の宣言・門・書き出し先・解く件数を確かめる。**実験ではない。**

    答える問い: 「宣言 → プール → 絞り → 門 → 書き出し先 は噛み合っているか」

    本実行と**同じ関数**で計画を組む(検査もすべて同じ)。モデルは呼ばないので率は出ない。
    """
    plan = load_scale_sweep_plan(config)
    load_generation_settings(config)
    adapter_provenance(declared_adapter(config), condition=require(config, "lesion.condition"))
    started = now or utc_now()
    targets = [
        level_run_dir(config, scale, prefix=run_dir_prefix, now=started) for scale in plan.levels
    ]
    refuse_existing_runs(targets)
    return {
        "levels": list(plan.levels),
        "run_dirs": [str(path) for path in targets],
        "gate": dict(plan.gate),
        "pool": dict(plan.pool),
        "task_subset": plan.task_subset,
    }


def print_scale_sweep_dry_run(report: Mapping[str, Any]) -> None:
    """掃引の配線確認の報告を出す。**この警告文を本実行に流用しない。**"""
    print("=" * 72)
    print("--dry-run: LoRA のスケールの掃引の配線確認。**実験ではない。**モデルは 1 度も呼ばれていない。")
    print("=" * 72)
    print(f"水準(宣言の順): {report['levels']} / D9 の門: {report['gate']}")
    subset = report["task_subset"] or {}
    print(f"解く項目: {subset.get('n_items')} 件(プール {report['pool'].get('items')})")
    for path in report["run_dirs"]:
        print(f"  書き出し先: {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoRA のスケール s の掃引(PLAN-037 I7)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="モデルを読まずに配線だけ確かめる。ここから出た数値は実験結果ではない",
    )
    parser.add_argument(
        "--run-dir-prefix",
        type=Path,
        default=None,
        help="水準ごとの書き出し先の接頭辞(<接頭辞>_s<水準>)。既定は runs/<timestamp>_<experiment.id>_s<水準>/",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        print_scale_sweep_dry_run(scale_sweep_dry_run(config, run_dir_prefix=args.run_dir_prefix))
        return 0
    execute_scale_sweep(config, config_path=args.config, run_dir_prefix=args.run_dir_prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
