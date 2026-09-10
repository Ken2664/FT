"""桁数掃引の入口(PLAN-001 §4.1.1 の手続き2)。

答える問い: 「素のモデルは、被演算子の上限 M をどこまで上げても加算を解けるか」

    python -m code.eval.sweep --config configs/exp042.yaml --run-dir runs/20260901_143022_sweep

**出すのは `M -> correct_rate` の表だけである。**§4.1.1 の手続きは4段あり、
このモジュールが担うのは 2 だけ:

  1. R(M) と Q(M) を定める                           code/eval/battery/magnitude_sweep.py
  2. 素のモデルに M を掃きながら解かせる             ← このモジュール
  3. 表から M* を決める                              **人間が決める**(ADR-041)
  4. D_ext = R(M*) のうち主域と交わらない部分        **未実装**

**2 本の腕を測り、metrics.json に別ブロックで出す**(ADR-071。2026-09-09 採択):

  - **腕1 = 一様抽出**(R(M) 全体。`by_radius` / `grid_shell`)—— **記述。**
    累積の曲線と定義 A の格子殻。崖の形と非単調の検出に使う(ADR-041 決定3 帰結欄)。
    **ADR-071 決定2 により現行の 13,000 項目を 1 文字も変えない**
  - **腕2 = Q(M)**(`extrap_magnitude` の母集団。`quadrant`)—— **判定の材料。**
    規則2 はこの表の `shell_judgement_radii` の上だけを走る(ADR-071 決定1・決定3)

**累積の表で判定しない。**R(M) 全体の一様抽出は M = 100 で 98.0% が主域の中にあり、
殻が完全に崩壊していても θ を割らない(★F121。ADR-070 決定4)。

**M* の決定規則は ADR-041 決定3 が凍結している**(値ではなく規則を凍結した):
**`M` を小さい順に見て、初めて `θ` を割った水準の1つ下**を採り、**それより上で
回復しても採らない**(規則2)。2026-08-28 まで PLAN-001 §4.1.1 は「`θ` を満たす
最大の `M`」と書いており、**崖の向こうで偶然 `θ` を超えた水準を拾う穴があった。**

**それでもこの CLI は M* を出さない。**θ の値は ADR-070 が config に置いたが、
表を読んで規則2 を適用し M* を置くのは人間である(ADR-041 / ADR-045 と同じ思想)。
決まったら `eval.extrapolation_radius` と `eval.extrapolation_run_id` に入る
(`configs/template.yaml`)。出力すると、その値が「実測で決まった」ように
見えてしまう。**このモジュールは θ を読まない。**

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
アダプタを読まない。掃引は `model.name` の重みそのものに対して回す。
**`model.adapter` を宣言した config は受け付けない**(`reject_declared_adapter`)
—— 黙って無視すると、config と実際に測った対象が食い違う。
"""

from __future__ import annotations

import argparse
import json
import statistics
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
from code.data_gen.battery_items import Item
from code.eval.battery import magnitude_sweep, numeric_sum
from code.eval.battery.magnitude_sweep import ShellPlan, SweepPlan
from code.eval.generate import Generator, build_generator, collect_responses
from code.eval.model import (
    ADAPTER_KEY,
    GenerationSettings,
    declared_adapter,
    load_generation_settings,
)
from code.eval.run import NO_ADAPTER_NOTE, parse_numeric_response, prediction_record
from code.eval.scoring import RateBreakdown, aggregate, score, validate_reference_rule
from code.lesion import Lesion, reference_lesions_from_config
from code.rates import RATE_FIELDS

# metrics.json の種別。本実行(code/eval/run.py の EVAL_KIND)と形が違う ——
# あちらは群ごとのバッチ、こちらは M ごとの点である。集約側が見分けられるようにする。
SWEEP_KIND = "magnitude_sweep"

# predictions/ のファイル名。M ごと・抽出シードごとに分ける。
PREDICTIONS_PREFIX = "magnitude"
# Q(M) の腕の predictions/ のファイル名(ADR-071 決定2)。一様抽出の腕と混ぜない。
QUADRANT_PREDICTIONS_PREFIX = "quadrant"

# metrics.json の各ブロックが何のための表か(ADR-071 決定1)。**判定の材料は quadrant だけ。**
# 腕1 の 2 つの表は記述であり、規則2 を当ててはならない(★F121)。
ROLE_DESCRIPTION = "description"
ROLE_JUDGEMENT_INPUT = "judgement_input"
BLOCK_ROLES = {
    "by_radius": ROLE_DESCRIPTION,
    "grid_shell": ROLE_DESCRIPTION,
    "quadrant": ROLE_JUDGEMENT_INPUT,
}

# シード平均・シード間 SD は4値**すべて**について出す(CLAUDE.md §6。`code/rates.py` の
# RATE_FIELDS を正とする)。M* を決めるのは correct_rate だが、崩壊は他の3値に出る。


def _seed_sd(values: Sequence[float]) -> float:
    """シード間の標本標準偏差(ddof=1)。シードが1本なら 0.0。

    答える問い: 「この水準の率は、抽出シードでどれだけ振れたか」

    **シードが1本のときは散らばりを推定しようがない**ので 0.0 を返す ——
    これは既定値ではなく、標本サイズ 1 で分散が未定義だという算術上の事実で
    ある(skill code-style §1)。本実験は5シード(ADR-041 決定5)なので、
    この分岐を通るのは smoke だけである。
    """
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


@dataclass(frozen=True)
class SeedResult:
    """1つの (M, 抽出シード) に対する測定。**これは実験結果である。**

    答える問い: 「この M の R(M) からシード seed で引いた n 件を、素のモデルは
    何件正答したか」
    """

    seed: int
    breakdown: RateBreakdown
    predictions: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        """metrics.json の by_seed の1行。**4値を必ず揃えて出す**(CLAUDE.md §6)。"""
        return {"seed": self.seed, **self.breakdown.as_dict()}


@dataclass(frozen=True)
class RadiusResult:
    """1つの M に対する、全抽出シードの測定。**これは実験結果である。**

    答える問い: 「この M で、素のモデルの応答はシード平均で4値にどう分かれ、
    シードでどれだけ振れたか」

    水準の代表値はシード平均で採る(ADR-041 決定3 規則3)。metrics.json には
    シード別の値も残す —— 平均だけだと、崖の近くで分散が開いたことを後から
    読めない。
    """

    radius: int
    reference_rule: str
    per_seed: list[SeedResult]

    @property
    def n_items_per_seed(self) -> int:
        """1シードあたりの採点件数。M 間・シード間で同一である(§4.1.1 の3)。"""
        return self.per_seed[0].breakdown.n_items

    @property
    def total_items(self) -> int:
        """この M で採点した総件数(全シード合算)。"""
        return sum(result.breakdown.n_items for result in self.per_seed)

    def seed_mean(self) -> dict[str, float]:
        """4値それぞれのシード平均。合計は 1.0(各シードが 1.0 なので)。"""
        return {
            key: statistics.fmean(getattr(r.breakdown, key) for r in self.per_seed)
            for key in RATE_FIELDS
        }

    def seed_sd(self) -> dict[str, float]:
        """4値それぞれのシード間 SD。"""
        return {
            key: _seed_sd([getattr(r.breakdown, key) for r in self.per_seed])
            for key in RATE_FIELDS
        }

    def as_dict(self) -> dict[str, Any]:
        """metrics.json の by_radius の1行。**4値を必ず揃えて出す**(CLAUDE.md §6)。

        `correct_rate` 等はシード平均(= 水準の代表値。ADR-041 決定3 規則3)。
        シード別の値は `by_seed`、シード間 SD は `seed_sd` に置く。
        """
        return {
            "radius": self.radius,
            "reference_rule": self.reference_rule,
            "n_seeds": len(self.per_seed),
            "n_items_per_seed": self.n_items_per_seed,
            "n_items": self.total_items,
            **self.seed_mean(),
            "seed_sd": self.seed_sd(),
            "by_seed": [result.as_dict() for result in self.per_seed],
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


def measure_seed(
    radius: int,
    seed: int,
    *,
    plan: SweepPlan,
    config: Mapping[str, Any],
    generator: Generator,
    reference_lesions: Mapping[str, Lesion],
    reference_rule: str,
    elicitation: str,
    pool_id: str,
) -> SeedResult:
    """1つの M を、1つの抽出シードで測る(腕1 = 一様抽出)。**これは実験結果である。**

    答える問い: 「この M の R(M) からシード seed で引いた n 件を、素のモデルは
    何件正答するか」

    項目の抽出は `magnitude_sweep.build_items` にある。取れなければ
    `InsufficientPairsError` で止まる —— **少ない本数で表を作らない。**
    M ごと・シードごとに n が違う表は correct_rate の比較が成立しない(§4.1.1 の3)。
    """
    items = magnitude_sweep.build_items(
        radius,
        n_items=plan.n_items_per_radius,
        seed=seed,
        pool_id=pool_id,
        reference_lesions=reference_lesions,
    )
    return score_items(
        items,
        seed,
        config=config,
        generator=generator,
        reference_lesions=reference_lesions,
        reference_rule=reference_rule,
        elicitation=elicitation,
    )


def measure_quadrant_seed(
    radius: int,
    seed: int,
    *,
    shell: ShellPlan,
    config: Mapping[str, Any],
    generator: Generator,
    reference_lesions: Mapping[str, Lesion],
    reference_rule: str,
    elicitation: str,
    pool_id: str,
) -> SeedResult:
    """1つの M を、1つの抽出シードで測る(腕2 = Q(M))。**これは実験結果である。**

    答える問い: 「この M の Q(M) からシード seed で引いた n 件を、素のモデルは
    何件正答するか」(ADR-071 決定1 の判定量)

    **生成と採点は腕1 と同じ関数を通す**(`score_items`)。腕ごとに書くと、
    判定の材料と記述の表で採点規則が割れても誰も気づかない。
    """
    items = magnitude_sweep.build_quadrant_items(
        radius,
        n_items=shell.n_items,
        seed=seed,
        pool_id=pool_id,
        reference_lesions=reference_lesions,
        main_radius=shell.main_radius,
    )
    return score_items(
        items,
        seed,
        config=config,
        generator=generator,
        reference_lesions=reference_lesions,
        reference_rule=reference_rule,
        elicitation=elicitation,
    )


def score_items(
    items: Sequence[Item],
    seed: int,
    *,
    config: Mapping[str, Any],
    generator: Generator,
    reference_lesions: Mapping[str, Lesion],
    reference_rule: str,
    elicitation: str,
) -> SeedResult:
    """引いた項目を素のモデルに解かせ、4値に分ける。**これは実験結果である。**

    答える問い: 「この n 件に、素のモデルは何と答え、それは4値のどれに落ちたか」
    """
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
    return SeedResult(
        seed=seed,
        breakdown=score(responses, reference_rule),
        predictions=records,
    )


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
    """1つの M を、`plan.seeds` のすべての抽出シードで測る。**これは実験結果である。**

    答える問い: 「この M で、素のモデルの correct_rate はシード平均でいくつで、
    シードでどれだけ振れるか」

    シードのループは**ここ**に置く。`build_items` は1シードぶんの抽出器の
    ままにする(1関数1責務。skill code-style §2 / PLAN-006 §4.5)。
    """
    return RadiusResult(
        radius=radius,
        reference_rule=reference_rule,
        per_seed=[
            measure_seed(
                radius,
                seed,
                plan=plan,
                config=config,
                generator=generator,
                reference_lesions=reference_lesions,
                reference_rule=reference_rule,
                elicitation=elicitation,
                pool_id=pool_id,
            )
            for seed in plan.seeds
        ],
    )


def sweep_quadrant_one(
    radius: int,
    *,
    plan: SweepPlan,
    shell: ShellPlan,
    config: Mapping[str, Any],
    generator: Generator,
    reference_lesions: Mapping[str, Lesion],
    reference_rule: str,
    elicitation: str,
    pool_id: str,
) -> RadiusResult:
    """1つの M の Q(M) を、`plan.seeds` のすべての抽出シードで測る。**これは実験結果である。**

    答える問い: 「この M の Q(M) で、素のモデルの correct_rate はシード平均でいくつで、
    シードでどれだけ振れるか」

    **シードは腕1 と同じ列を使う**(ADR-071 決定2 = 「200 件 × 5 シード」)。
    代表値がシード平均であることも腕1 と同じである(ADR-041 決定3 規則3)。
    """
    return RadiusResult(
        radius=radius,
        reference_rule=reference_rule,
        per_seed=[
            measure_quadrant_seed(
                radius,
                seed,
                shell=shell,
                config=config,
                generator=generator,
                reference_lesions=reference_lesions,
                reference_rule=reference_rule,
                elicitation=elicitation,
                pool_id=pool_id,
            )
            for seed in plan.seeds
        ],
    )


@dataclass(frozen=True)
class ReferenceSetup:
    """2 本の腕が共有する採点の前提。**腕ごとに読み直さない**(割れると表が比べられない)。"""

    reference_rule: str
    elicitation: str
    pool_id: str
    reference_lesions: Mapping[str, Lesion]


def reference_setup(config: Mapping[str, Any]) -> ReferenceSetup:
    """主要参照規則・引き出し方・プール名・参照規則の集合を読み、参照規則を検査する。

    答える問い: 「この掃引は、どの参照規則から見た4値分解を出すのか」
    """
    reference_rule = require(config, "eval.reference_rule")
    elicitation = require(config, "eval.elicitation")
    pool_id = require(config, "data.pool_id")
    reference_lesions = reference_lesions_from_config(config)
    validate_reference_rule(
        reference_rule, reference_lesions[reference_rule], list(reference_lesions)
    )
    return ReferenceSetup(
        reference_rule=reference_rule,
        elicitation=elicitation,
        pool_id=pool_id,
        reference_lesions=reference_lesions,
    )


def sweep(config: Mapping[str, Any], *, generator: Generator) -> list[RadiusResult]:
    """腕1: config が宣言する M をすべて、R(M) からの一様抽出で測る。**記述である。**

    答える問い: 「M を上げていくと correct_rate はどこで落ちるか」

    重みを読み直さない(`generator` は呼び出し側が1つ作る)。M ごとに
    読み直すと、M の違いと生成設定の揺れが分離できなくなる。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    setup = reference_setup(config)
    return [
        sweep_one(
            radius,
            plan=plan,
            config=config,
            generator=generator,
            reference_lesions=setup.reference_lesions,
            reference_rule=setup.reference_rule,
            elicitation=setup.elicitation,
            pool_id=setup.pool_id,
        )
        for radius in plan.radii
    ]


def sweep_quadrant(config: Mapping[str, Any], *, generator: Generator) -> list[RadiusResult]:
    """腕2: Q(M) から引ける水準をすべて測る。**判定の材料である**(ADR-071 決定1)。

    答える問い: 「外挿腕が実際に使う組(`extrap_magnitude`)の上で、素のモデルは
    M をどこまで上げても加算を解けるか」

    測る水準は `load_shell_plan` が ADR-071 から導き、config と突き合わせたものである。
    **判定はしない。**規則2 を当てるのは人間である(モジュール冒頭)。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    setup = reference_setup(config)
    return [
        sweep_quadrant_one(
            radius,
            plan=plan,
            shell=shell,
            config=config,
            generator=generator,
            reference_lesions=setup.reference_lesions,
            reference_rule=setup.reference_rule,
            elicitation=setup.elicitation,
            pool_id=setup.pool_id,
        )
        for radius in shell.radii
    ]


def correct_rate_table(results: Sequence[RadiusResult]) -> dict[str, float]:
    """`M -> correct_rate`(シード平均)の対応表。**この表がこの CLI の成果物である。**

    答える問い: 「どの M まで素のモデルは加算を解けているか」

    代表値はシード平均(ADR-041 決定3 規則3)。ここから M* を決めるのは
    人間である(モジュール冒頭)。閾値の適用をこの関数に足さないこと。
    """
    return {str(result.radius): result.seed_mean()["correct_rate"] for result in results}


def _in_grid_shell(record: Mapping[str, Any], previous_radius: int | None) -> bool:
    """この予測の組は、1 つ前の格子点の R の外にあるか(最小の格子点ではすべて入る)。"""
    if previous_radius is None:
        return True
    a, b = record["operands"]
    return not magnitude_sweep.in_domain((a, b), previous_radius)


def _rates_or_null(breakdown: RateBreakdown) -> dict[str, float | int | None]:
    """4値と件数。**件数 0 なら 4値を null にする** —— 0.0 と書くと「正答率 0」と読める。"""
    if breakdown.n_items == 0:
        return {**{key: None for key in RATE_FIELDS}, "n_items": 0}
    return breakdown.as_dict()


def grid_shell_rows(results: Sequence[RadiusResult]) -> list[dict[str, Any]]:
    """腕1 を定義 A の格子殻で切り直す。**記述であって判定ではない**(ADR-071 決定1)。

    答える問い: 「M を 1 つ上げたときに新しく入った領域だけで見ると、素のモデルの
    応答は4値にどう分かれるか」

    定義 A の殻 = R(M) から 1 つ前の格子点の R を引いた差(PLAN-021 §3)。
    最小の格子点は 1 つ前が無いので R(M) 全体になる。
    **新しく引き直さない。**腕1 が引いた項目のうち殻に落ちたものの分類を数え直すだけで
    ある(`predictions/` の `operands` と `classification` からも同じ表が作れる)。

    **n は水準ごとに違う**(★F122。PLAN-021 §3.1 の計数では M = 100 で 5 シード合算の
    期待 19.8 件)。**だから率はシード平均ではなく全シード合算で出し、シード別には
    件数だけを残す** —— 殻に 1 件も落ちないシードでは率が定義できない。
    **★この集計のしかたは ADR-071 に書かれていない。エージェントが選んだ**
    (記述の表であり、判定には使わない。`logs/CHANGELOG.md` に明記した)。
    """
    rows = []
    previous: int | None = None
    for result in sorted(results, key=lambda r: r.radius):
        by_seed = [
            [
                record["classification"]
                for record in seed_result.predictions
                if _in_grid_shell(record, previous)
            ]
            for seed_result in result.per_seed
        ]
        pooled = aggregate([category for categories in by_seed for category in categories])
        rows.append(
            {
                "radius": result.radius,
                "previous_radius": previous,
                "reference_rule": result.reference_rule,
                "n_items_by_seed": [len(categories) for categories in by_seed],
                **_rates_or_null(pooled),
            }
        )
        previous = result.radius
    return rows


def reject_declared_adapter(config: Mapping[str, Any]) -> None:
    """アダプタを宣言した config で掃引を回さない(ADR-043 決定3 の裏)。

    答える問い: 「この表は、素のモデルのものか」

    **掃引が測るのは素の算術能力である**(モジュール冒頭)。アダプタを
    載せると `M*` が病変後の能力から決まり、外挿域の定義そのものが
    病変に依存する —— PLAN-001 §4.1.1 が潰したはずの交絡に戻る。

    **黙って無視しない。**無視すると、config は「アダプタを読む」と書いて
    いるのに読んでいない run が残り、記録と実際が食い違う。
    """
    adapter = declared_adapter(config)
    if adapter is not None:
        raise ConfigError(
            f"{ADAPTER_KEY}={adapter!r} が宣言されているが、桁数掃引は素のモデルの測定である"
            "(PLAN-001 §4.1.1)。アダプタを載せて測った M* は病変後の能力から決まり、"
            "外挿域の定義が病変に依存してしまう。"
        )


def total_items(results: Sequence[RadiusResult]) -> int:
    """掃引全体で解いた項目数。

    答える問い: 「この掃引は何項目を解いたか」

    水準ごと・シードごとの項目数は同一である(`eval.magnitude_sweep.n_items_per_radius`)
    が、ここでは**実際に採点した件数を数える** —— 宣言した値を掛け算すると、
    抽出が足りずに水準が短くなったときに秒数の分母だけが嘘になる。
    """
    return sum(result.total_items for result in results)


def metrics_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    plan: SweepPlan,
    results: Sequence[RadiusResult],
    *,
    shell: ShellPlan,
    quadrant: Sequence[RadiusResult],
    run_id: str,
    timing: Mapping[str, Any],
) -> dict[str, Any]:
    """metrics.json の中身を組む。

    答える問い: 「この表が、どの重みの、どの設定の、どの抽出から出たかを、
    この1ファイルだけで言えるか」

    `timing` は `execute` が測った区間である(`code/eval/run.py` と同じ形)。
    掃引は本実行と**同じ生成経路**を通るので、まとめ幅あたりの速度も同じ
    土俵で読める(ADR-040 決定6)。

    **腕ごとに別ブロックにする**(ADR-071)。腕1 は従来の鍵(`sweep` /
    `correct_rate_by_radius` / `by_radius`)をそのまま使い —— ADR-041 の追記が
    `by_radius[*].seed_sd` を名指ししている —— 定義 A の切り直しを `grid_shell` に、
    腕2 を `quadrant` に置く。**どれが判定の材料かは `roles` に書く。**
    4値分解はどのブロックでも行ごとに合計 1.0 である(CLAUDE.md §6)。
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
        "roles": dict(BLOCK_ROLES),
        "correct_rate_by_radius": correct_rate_table(results),
        "by_radius": [result.as_dict() for result in results],
        "grid_shell": {
            "definition": "grid",
            "aggregation": "pooled_over_seeds",
            "by_radius": grid_shell_rows(results),
        },
        "quadrant": {
            "shell": shell.as_dict(),
            "correct_rate_by_radius": correct_rate_table(quadrant),
            "by_radius": [
                {**result.as_dict(), "population_size": shell.population_sizes[result.radius]}
                for result in quadrant
            ],
        },
    }


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。

    答える問い: 「この掃引は何を測り、何を測っていないのか」

    **M* を出さないことを毎回書く。**表だけを見た人が「掃引が上限を出した」と
    読むのを防ぐ(承認待ち #9 / #15)。
    **どの表が判定の材料かを表の見出しに書く**(ADR-071 決定1)。腕1 の累積の表で
    規則2 を当てると、殻の崩壊が薄まって見えない(★F121)。
    """
    generation = payload["generation"]
    shell = payload["quadrant"]["shell"]
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
        f"seeds={payload['sweep']['seeds']}",
        f"Q(M) の腕: definition={shell['definition']} radii={shell['radii']} "
        f"judgement_radii={shell['judgement_radii']} "
        f"n_items_per_radius={shell['n_items_per_radius']} main_radius={shell['main_radius']}",
        f"参照規則: {payload['reference_rule']} / 引き出し方: {payload['elicitation']}",
        timing_line(payload["timing"]),
        "",
        "correct / rule / other_err / parse_fail はシード平均、±sd はシード間 SD "
        "(ADR-041 決定3 規則3)。",
        "",
        "■ 腕1: R(M) からの一様抽出(累積)—— 記述。判定に使わない(ADR-071 決定1 / ★F121)",
        f"{'M':>7}  {'seeds':>5}  {'n/seed':>6}  {'correct':>8}  {'±sd':>7}  "
        f"{'rule':>8}  {'other_err':>10}  {'parse_fail':>10}",
    ]
    for row in payload["by_radius"]:
        lines.append(
            f"{row['radius']:>7}  {row['n_seeds']:>5}  {row['n_items_per_seed']:>6}  "
            f"{row['correct_rate']:>8.4f}  {row['seed_sd']['correct_rate']:>7.4f}  "
            f"{row['rule_rate']:>8.4f}  {row['other_error_rate']:>10.4f}  "
            f"{row['parse_fail_rate']:>10.4f}"
        )
    lines.extend(_grid_shell_lines(payload["grid_shell"]["by_radius"]))
    lines.extend(_quadrant_lines(payload["quadrant"]["by_radius"]))
    lines.extend(
        [
            "",
            "この CLI の出力から外挿域の上限 M* は決まらない。規則2(ADR-041 決定3: M を小さい順に",
            "見て初めて θ を割った水準の1つ下)を当てて M* を置くのは人間である(PLAN-001 §4.1.1 の3)。",
            "判定量は腕2 の correct_rate(ADR-070 決定4 / ADR-071 決定1)、判定水準は",
            "judgement_radii(ADR-071 決定3)、θ は config の eval.magnitude_sweep.theta(ADR-070)。",
        ]
    )
    return lines


def _rate_cell(value: float | None, width: int) -> str:
    """表の 1 マス。件数 0 で率が定義できないときは「—」を置く(0.0 と書かない)。"""
    return f"{'—':>{width}}" if value is None else f"{value:>{width}.4f}"


def _grid_shell_lines(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """定義 A の格子殻の表(記述)。率は全シード合算、シード別には件数だけ。"""
    lines = [
        "",
        "■ 腕1 の切り直し: 定義 A の格子殻(R(M) − R(1 つ前の M))—— 記述。",
        "  n は水準ごとに違う(★F122)。率は全シード合算。n_by_seed はシード別の件数",
        f"{'M':>7}  {'prev':>5}  {'n':>6}  {'correct':>8}  {'rule':>8}  "
        f"{'other_err':>10}  {'parse_fail':>10}  n_by_seed",
    ]
    for row in rows:
        previous = "—" if row["previous_radius"] is None else row["previous_radius"]
        lines.append(
            f"{row['radius']:>7}  {previous:>5}  {row['n_items']:>6}  "
            f"{_rate_cell(row['correct_rate'], 8)}  {_rate_cell(row['rule_rate'], 8)}  "
            f"{_rate_cell(row['other_error_rate'], 10)}  "
            f"{_rate_cell(row['parse_fail_rate'], 10)}  {row['n_items_by_seed']}"
        )
    return lines


def _quadrant_lines(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Q(M) の腕の表(判定の材料)。|Q(M)| と 1 シードの抽出率を並べる。"""
    lines = [
        "",
        "■ 腕2: Q(M) = extrap_magnitude の母集団 —— 判定の材料(ADR-071 決定1・決定3)",
        "  |Q| は組合せ論の計数。抽出率 = n/seed ÷ |Q|。抽出率が高い水準では、",
        "  シード間 SD が不確実性を過小に表す(ほぼ全数調査になる。ADR-071 リスク欄)",
        f"{'M':>7}  {'|Q|':>8}  {'抽出率':>6}  {'seeds':>5}  {'n/seed':>6}  {'correct':>8}  "
        f"{'±sd':>7}  {'rule':>8}  {'other_err':>10}  {'parse_fail':>10}",
    ]
    for row in rows:
        fraction = row["n_items_per_seed"] / row["population_size"]
        lines.append(
            f"{row['radius']:>7}  {row['population_size']:>8}  {fraction:>6.3f}  "
            f"{row['n_seeds']:>5}  {row['n_items_per_seed']:>6}  "
            f"{row['correct_rate']:>8.4f}  {row['seed_sd']['correct_rate']:>7.4f}  "
            f"{row['rule_rate']:>8.4f}  {row['other_error_rate']:>10.4f}  "
            f"{row['parse_fail_rate']:>10.4f}"
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

    **Q(M) の腕の設定は、run ディレクトリを作る前・重みを読む前に検査する**
    (`load_shell_plan`)。ADR-071 と食い違う config で GPU を回し始めてから止まると、
    半端な run が残る。
    """
    settings = load_generation_settings(config)
    reject_declared_adapter(config)
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
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
    quadrant = sweep_quadrant(config, generator=ready)
    generation_seconds = elapsed_seconds(generation_started)

    for prefix, arm in ((PREDICTIONS_PREFIX, results), (QUADRANT_PREDICTIONS_PREFIX, quadrant)):
        for result in arm:
            for seed_result in result.per_seed:
                write_predictions(
                    target,
                    f"{prefix}_M{result.radius}_s{seed_result.seed}",
                    seed_result.predictions,
                )
    ended = utc_now()
    payload = metrics_payload(
        config,
        settings,
        plan,
        results,
        shell=shell,
        quadrant=quadrant,
        run_id=target.name,
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=model_load_seconds,
            generation_seconds=generation_seconds,
            n_items=total_items(results) + total_items(quadrant),
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
    実験結果ではない(CLAUDE.md §2)。2 本の腕の両方を組む(ADR-071)。
    """
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    pool_id = require(config, "data.pool_id")
    reference_lesions = reference_lesions_from_config(config)
    by_radius = {}
    for radius in plan.radii:
        by_seed = {}
        for seed in plan.seeds:
            items = magnitude_sweep.build_items(
                radius,
                n_items=plan.n_items_per_radius,
                seed=seed,
                pool_id=pool_id,
                reference_lesions=reference_lesions,
            )
            by_seed[str(seed)] = _dry_run_items(items, config)
        by_radius[str(radius)] = {
            "domain_size": magnitude_sweep.domain_size(radius),
            "by_seed": by_seed,
        }
    quadrant_by_radius = {}
    for radius in shell.radii:
        quadrant_by_radius[str(radius)] = {
            "population_size": shell.population_sizes[radius],
            "by_seed": {
                str(seed): _dry_run_items(
                    magnitude_sweep.build_quadrant_items(
                        radius,
                        n_items=shell.n_items,
                        seed=seed,
                        pool_id=pool_id,
                        reference_lesions=reference_lesions,
                        main_radius=shell.main_radius,
                    ),
                    config,
                )
                for seed in plan.seeds
            },
        }
    return {
        "sweep": plan.as_dict(),
        "reference_rules": sorted(reference_lesions),
        "by_radius": by_radius,
        "quadrant": {"shell": shell.as_dict(), "by_radius": quadrant_by_radius},
    }


def _dry_run_items(items: Sequence[Item], config: Mapping[str, Any]) -> dict[str, Any]:
    """dry-run に出す 1 シードぶんの項目。件数・item_id・質問文だけで、率は出さない。"""
    return {
        "n_items": len(items),
        "item_ids": [item.item_id for item in items],
        "prompts": list(sweep_prompts(items, config).values()),
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
