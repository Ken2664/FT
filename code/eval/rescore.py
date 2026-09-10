"""順5(`code/eval/sweep.py` の run)を新しい規則2 で採点し直す(PLAN-022 §5 / §5.1)。

答える問い: 「規則2 を『整数がちょうど1個』から『1個以上あり、すべて同じ整数値』に
広げると(ADR-074 決定2)、回収済みの `predictions/` の4値分解はどう動くか」

    python -m code.eval.rescore --source-run runs/20260910_104249_sweep_m

**GPU は使わない。**回収済みの `predictions/*.jsonl` の `response` 列を、新しい
`code.eval.parsers.numeric` で読み直すだけである。モデルは1度も呼ばない。

**元の run ディレクトリには何も書かない**(ADR-074 決定2「元の metrics.json は
書き換えない」)。成果物はすべて新しい `runs/<timestamp>_rescore_<元の run の
suffix>/` に書く。

**集計は `code/eval/sweep.py` の関数を再利用する。**`RadiusResult` / `SeedResult` /
`correct_rate_table` / `grid_shell_rows` / `metrics_payload` / `report_lines` は
1文字も書き直さない —— 集計の式を2箇所に持つと、片方だけ直したときに
metrics.json の3ブロック(`by_radius` / `grid_shell` / `quadrant`)が本実行の
集計と食い違っても誰も気づかない。この CLI が新しく書くのは「予測ファイルを
読み、新パーサで読み直し、`RadiusResult` を組み直す」ところだけである。

**5つの検査(C1-C5)を必ず走らせる**(PLAN-022 §5.1)。C1 / C2 / C4 は外れたら
`metrics.json` を書く前に止める(RescoreConsistencyError)。C3 / C5 は外れても
止めない —— 数値をそのまま記録し、`checks` ブロックと `log.txt` に
「人間に上げる」と明記する(`CLAUDE.md` §8: 解釈・採否は人間の仕事)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from code import artifacts
from code.artifacts import (
    elapsed_seconds,
    monotonic_seconds,
    timing_record,
    utc_now,
    write_git_sha,
    write_log,
    write_metrics,
    write_predictions,
)
from code.config import load_config
from code.eval import sweep
from code.eval.battery import magnitude_sweep
from code.eval.model import GenerationSettings, load_generation_settings
from code.eval.run import parse_numeric_response
from code.eval.scoring import aggregate, classify
from code.rates import (
    CATEGORIES,
    CORRECT,
    OTHER_ERROR,
    PARSE_FAIL,
    RATE_FIELDS,
    RULE,
    TOTAL_TOLERANCE,
)

# PLAN-022 §4 で置いた新しい規則2 の名前(code/eval/parsers/base.py の関数名と同じ)。
# metrics.json / config.yaml の記録に使う。ここでは値そのものを変えない
# (パーサは触らない。このモジュールの責務は再採点だけ)。
PARSER_RULE_NAME = "unanimous_integer"

# この再採点の根拠になった ADR。config.yaml / metrics.json の記録に使う。
ADR_REFERENCE = "ADR-074"

# 新しい run の id に足す接頭辞。`<timestamp>_rescore_<元 run の suffix>` の形にする
# (PLAN-022 §5 の入口案そのまま)。
RUN_ID_INFIX = "rescore"

# PLAN-022 §5.1 C5(ADR-074 決定1 の算術)。新規則での腕2(quadrant)の
# correct_rate は全水準でこれ以上でなければならない。外れても止めず、
# `checks` ブロックと log.txt に記録して人間に上げる。
QUADRANT_CORRECT_RATE_MIN = 0.75

# PLAN-022 §5.1 C3(★F126 の診断。ADR-074 決定2 根拠欄)。旧 `parse_fail` 行が
# 新しい分類でどこへ散るかの期待値。**診断であって公式の指標ではない。**
# 外れても止めない(止めるのは C1 / C2 / C4 だけ)。腕の名前は
# `code.eval.sweep` の predictions プレフィクスと合わせる。
EXPECTED_C3_TRANSITIONS: dict[str, dict[str, int]] = {
    sweep.QUADRANT_PREDICTIONS_PREFIX: {
        CORRECT: 133,
        OTHER_ERROR: 5,
        RULE: 0,
        PARSE_FAIL: 22,
    },
    sweep.PREDICTIONS_PREFIX: {
        CORRECT: 1264,
        OTHER_ERROR: 92,
        RULE: 0,
        PARSE_FAIL: 902,
    },
}


class RescoreConsistencyError(RuntimeError):
    """C1 / C2 / C4 のいずれかが外れた(PLAN-022 §5.1)。

    止める理由は検査ごとに違うが、どれも「集計か新パーサの上位集合性が
    壊れている」という実装のバグを疑う理由になる(CLAUDE.md §7)。
    metrics.json は書かない。
    """


# --------------------------------------------------------------------------
# 予測ファイルの読み直し
# --------------------------------------------------------------------------


def predictions_path(run_dir: Path, prefix: str, radius: int, seed: int) -> Path:
    """1つの (腕, M, 抽出シード) の predictions ファイルの場所。

    答える問い: 「この腕・この M・このシードの予測はどこにあるか」

    書式は `code/eval/sweep.py` の `execute` が書くときの書式と同じでなければ
    ならない(`{prefix}_M{radius}_s{seed}.jsonl`)。ここで独自の書式を作ると、
    本実行が書いたファイルを読めない。
    """
    return run_dir / artifacts.PREDICTIONS_DIR / f"{prefix}_M{radius}_s{seed}.jsonl"


def read_predictions(path: Path) -> list[dict[str, Any]]:
    """1つの predictions ファイルを1行1件の辞書列として読む。

    答える問い: 「この予測ファイルに保存されている行は何件で、それぞれ何か」
    """
    if not path.is_file():
        raise FileNotFoundError(f"{path} が無い(元の run が壊れているか、パスが違う)")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def rescore_row(row: Mapping[str, Any], *, elicitation: str) -> dict[str, Any]:
    """1件の応答を新パーサで読み直し、分類し直す。

    答える問い: 「この行の `response` を新しい規則2(unanimous_integer)で
    読み直すと、`parsed` と `classification` はどう変わるか」

    元の行の全フィールドをそのまま残し、`parsed` / `classification` を新しい
    値に置き換え、旧値を `parsed_before` / `classification_before` として足す
    (PLAN-022 §5)。分類は `code/eval/scoring.py` の `classify` を再利用する ——
    採点の規則(correct → rule → other_error → parse_fail の順序)を
    ここで書き直すと、本実行の採点とずれても誰も気づかない。
    """
    new_parsed = parse_numeric_response(row["response"], elicitation)
    reference_rule = row["reference_rule"]
    rule_value = row["rule_values"][reference_rule]
    new_classification = classify(new_parsed, row["truth"], rule_value)
    rescored = dict(row)
    rescored["parsed_before"] = row["parsed"]
    rescored["classification_before"] = row["classification"]
    rescored["parsed"] = new_parsed
    rescored["classification"] = new_classification
    return rescored


def radius_result_from_records(
    radius: int,
    reference_rule: str,
    records_by_seed: Mapping[int, Sequence[Mapping[str, Any]]],
    seeds: Sequence[int],
) -> sweep.RadiusResult:
    """予測の行(辞書)から `sweep.RadiusResult` を組む。

    答える問い: 「この M の、この記録集合(旧行のままでも、再採点した後でも)を
    `sweep.py` の集計に渡せる形にするとどうなるか」

    **分類は `record["classification"]` をそのまま数える**(`scoring.aggregate`)。
    旧分類の記録・新分類の記録のどちらでも同じ関数で組めるようにするのは、
    C1(旧分類からの再集計)と本採点(新分類での集計)を同じ経路で作り、
    2つの経路が割れて比較が意味を失うのを防ぐためである。
    """
    per_seed = [
        sweep.SeedResult(
            seed=seed,
            breakdown=aggregate(
                [record["classification"] for record in records_by_seed[seed]]
            ),
            predictions=list(records_by_seed[seed]),
        )
        for seed in seeds
    ]
    return sweep.RadiusResult(radius=radius, reference_rule=reference_rule, per_seed=per_seed)


@dataclass(frozen=True)
class ArmRescore:
    """1本の腕(`magnitude` または `quadrant`)を読み直した結果。

    答える問い: 「この腕の全水準・全シードを新パーサで読み直すと、旧分類だけの
    集計(C1 用)・新分類の集計(本採点)・C2 違反の一覧はそれぞれどうなるか」
    """

    before: list[sweep.RadiusResult]
    after: list[sweep.RadiusResult]
    parse_violations: list[str] = field(default_factory=list)


def rescore_arm(
    source_run_dir: Path,
    *,
    prefix: str,
    radii: Sequence[int],
    seeds: Sequence[int],
    reference_rule: str,
    elicitation: str,
) -> ArmRescore:
    """1本の腕の全水準・全シードの predictions を読み直す。

    答える問い: 「この腕(`prefix`)の全ファイルを新パーサで読み直すと、
    旧分類のままの `RadiusResult` 列と、新分類の `RadiusResult` 列は何か」

    水準の順序は呼び出し側が渡す `radii` の順序をそのまま使う
    (`sweep.py` が書き出した順序 = config の昇順と同じにするのは呼び出し側の責務)。
    """
    before: list[sweep.RadiusResult] = []
    after: list[sweep.RadiusResult] = []
    violations: list[str] = []
    for radius in radii:
        before_by_seed: dict[int, list[dict[str, Any]]] = {}
        after_by_seed: dict[int, list[dict[str, Any]]] = {}
        for seed in seeds:
            rows = read_predictions(predictions_path(source_run_dir, prefix, radius, seed))
            rescored = [rescore_row(row, elicitation=elicitation) for row in rows]
            violations.extend(
                row["item_id"]
                for row, new_row in zip(rows, rescored, strict=True)
                if row["parsed"] is not None and new_row["parsed"] != row["parsed"]
            )
            before_by_seed[seed] = rows
            after_by_seed[seed] = rescored
        before.append(radius_result_from_records(radius, reference_rule, before_by_seed, seeds))
        after.append(radius_result_from_records(radius, reference_rule, after_by_seed, seeds))
    return ArmRescore(before=before, after=after, parse_violations=violations)


# --------------------------------------------------------------------------
# C1: 保存済み classification からの再集計が元の metrics.json と一致するか
# --------------------------------------------------------------------------


def _zero_timing(now: datetime) -> dict[str, Any]:
    """C1 の再現用 payload にだけ使う空の timing ブロック。

    答える問い: 「C1 は timing を比較しないので、値は何でもよいはずである。
    それを1箇所にまとめておけるか」

    `sweep.metrics_payload` は timing を必須で受け取るが、C1 が比べるのは
    `by_radius` / `grid_shell` / `quadrant` の3ブロックだけである(PLAN-022 §5.1)。
    """
    return timing_record(
        started=now, ended=now, total_seconds=0.0, model_load_seconds=0.0,
        generation_seconds=0.0, n_items=0,
    )


def reproduce_source_metrics(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    plan: magnitude_sweep.SweepPlan,
    shell: magnitude_sweep.ShellPlan,
    before_arm1: Sequence[sweep.RadiusResult],
    before_arm2: Sequence[sweep.RadiusResult],
    *,
    now: datetime,
) -> dict[str, Any]:
    """保存済み `classification` だけから、`sweep.py` と同じ形の payload を組む。

    答える問い: 「元の run が書いた metrics.json の3ブロックを、予測ファイルの
    `classification` 列から作り直すと、本当に同じものが出るか」(C1)

    **`sweep.metrics_payload` を1文字も書き直さずに呼ぶ。**別の集計関数を
    ここに書くと、C1 が「2つの独立な集計が一致した」ではなく「同じ式を
    2回書いた」を検査するだけになる。
    """
    return sweep.metrics_payload(
        config, settings, plan, list(before_arm1),
        shell=shell, quadrant=list(before_arm2),
        run_id="c1_reproduction", timing=_zero_timing(now),
    )


def check_c1_reproduces_source_metrics(
    reproduction: Mapping[str, Any], source_metrics: Mapping[str, Any]
) -> dict[str, Any]:
    """C1: 3ブロックが元の metrics.json と全水準・全シードで一致するか。

    答える問い: 「保存済み `classification` からの再集計は、元の run が書いた
    値と一致するか」(PLAN-022 §5.1 C1)

    一致しなければ止める。集計そのものが再現できていないということであり、
    その先の新パーサの再採点を報告しても意味を持たない(CLAUDE.md §7)。
    """
    mismatched = [
        key
        for key in ("correct_rate_by_radius", "by_radius", "grid_shell")
        if reproduction[key] != source_metrics[key]
    ]
    for key in ("correct_rate_by_radius", "by_radius"):
        if reproduction["quadrant"][key] != source_metrics["quadrant"][key]:
            mismatched.append(f"quadrant.{key}")
    if mismatched:
        raise RescoreConsistencyError(
            f"C1: 保存済み classification からの再集計が元の metrics.json と"
            f"一致しない({', '.join(mismatched)})。集計の再現が壊れている。"
        )
    return {"status": "pass"}


# --------------------------------------------------------------------------
# C2: 保存済み parsed が None でない行は、新パーサでも同じ値になるか
# --------------------------------------------------------------------------


def check_c2_new_parser_is_a_superset(violations: Sequence[str]) -> dict[str, Any]:
    """C2: 新パーサが旧パーサの上位集合になっているか。

    答える問い: 「旧パーサが読めていた値は、新パーサでも同じ値のままか」
    (PLAN-022 §5.1 C2)

    ADR-074 決定2 の新しい規則2 は「整数がちょうど1個」を含む上位集合である
    はずであり、値が変わる行が1件でもあれば実装のバグである(CLAUDE.md §7)。
    """
    if violations:
        shown = violations[:10]
        suffix = "…" if len(violations) > 10 else ""
        raise RescoreConsistencyError(
            f"C2: 新パーサが上位集合になっていない(値が変わった item_id "
            f"{len(violations)} 件): {shown}{suffix}"
        )
    return {"status": "pass", "violations": len(violations)}


# --------------------------------------------------------------------------
# C3: 旧 parse_fail 行の行き先(診断。外れても止めない)
# --------------------------------------------------------------------------


def parse_fail_transition_counts(
    before: Sequence[sweep.RadiusResult], after: Sequence[sweep.RadiusResult]
) -> dict[str, int]:
    """旧分類が `parse_fail` だった行が、新分類でどこへ散ったかを数える。

    答える問い: 「この腕で、旧規則が読めなかった行のうち、新規則2 は何件を
    correct / rule / other_error に変え、何件がなお parse_fail のままか」
    (PLAN-022 §5.1 C3。★F126 の診断)
    """
    counts = {category: 0 for category in CATEGORIES}
    for before_radius, after_radius in zip(before, after, strict=True):
        for before_seed, after_seed in zip(
            before_radius.per_seed, after_radius.per_seed, strict=True
        ):
            for before_record, after_record in zip(
                before_seed.predictions, after_seed.predictions, strict=True
            ):
                if before_record["classification"] == PARSE_FAIL:
                    counts[after_record["classification"]] += 1
    return counts


def check_c3_parse_fail_transitions(
    arm1: ArmRescore, arm2: ArmRescore
) -> dict[str, Any]:
    """C3: 旧 parse_fail 行の行き先を、期待値(★F126 の診断)と突き合わせる。

    答える問い: 「旧 parse_fail 行の行き先の実測は、その38 が数えた診断の
    件数と一致するか」(PLAN-022 §5.1 C3)

    **外れても止めない。**診断の数え方と新パーサの実装が違う可能性はあるが、
    それを判断するのは人間である(CLAUDE.md §8)。実測をそのまま記録する。
    """
    actual = {
        sweep.PREDICTIONS_PREFIX: parse_fail_transition_counts(arm1.before, arm1.after),
        sweep.QUADRANT_PREDICTIONS_PREFIX: parse_fail_transition_counts(arm2.before, arm2.after),
    }
    matches = actual == EXPECTED_C3_TRANSITIONS
    return {
        "expected": EXPECTED_C3_TRANSITIONS,
        "actual": actual,
        "matches": matches,
        "status": "pass" if matches else "flagged_for_human",
        "message": None if matches else "C3 外れ — 人間に上げる",
    }


# --------------------------------------------------------------------------
# C4: 4値の合計が全ブロック・全水準・全シードで 1.0 か
# --------------------------------------------------------------------------


def _rate_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """metrics.json の中で4値分解を持つ行をすべて集める(C4 の対象)。"""
    rows: list[Mapping[str, Any]] = list(payload["by_radius"])
    rows.extend(payload["grid_shell"]["by_radius"])
    rows.extend(payload["quadrant"]["by_radius"])
    for row in list(payload["by_radius"]) + list(payload["quadrant"]["by_radius"]):
        rows.extend(row["by_seed"])
    return rows


def check_c4_rates_sum_to_one(payload: Mapping[str, Any]) -> dict[str, Any]:
    """C4: 4値の合計が、全ブロック・全水準・全シードで 1.0 になっているか。

    答える問い: 「metrics.json に書く最終形のどの行を見ても、4値の合計は
    1.0 か」(PLAN-022 §5.1 C4)

    `RateBreakdown.__post_init__` が個々の構築時にも検査しているが、ここでは
    書き出す直前の payload そのものを走査する(skill code-style §4「合計が
    1.0 になることをアサートするテストを書く」)。1件でも外れたら止める。
    """
    broken = []
    for row in _rate_rows(payload):
        if row.get("n_items", 0) == 0:
            continue
        total = sum(row[key] for key in RATE_FIELDS)
        if abs(total - 1.0) > TOTAL_TOLERANCE:
            broken.append((row.get("radius"), row.get("seed"), total))
    if broken:
        raise RescoreConsistencyError(f"C4: 4値の合計が 1.0 でない行がある: {broken}")
    return {"status": "pass"}


# --------------------------------------------------------------------------
# C5: 新規則での腕2 の correct_rate(診断。外れても止めない)
# --------------------------------------------------------------------------


def check_c5_quadrant_correct_rate(payload: Mapping[str, Any]) -> dict[str, Any]:
    """C5: 新規則での腕2(quadrant)の correct_rate が全水準で 0.75 以上か。

    答える問い: 「新パーサで採点し直しても、`M*` = 999 を置いた根拠
    (腕2の correct_rate が 0.75 を割らない)は崩れていないか」(PLAN-022 §5.1 C5)

    **外れても止めない。**`M*` を置き直すかどうかは人間が決める
    (ADR-074 決定1「M* は置き直さない」)。ここは実測を記録するだけである。
    """
    rows = payload["quadrant"]["by_radius"]
    by_radius = {row["radius"]: row["correct_rate"] for row in rows}
    below = {radius: rate for radius, rate in by_radius.items() if rate < QUADRANT_CORRECT_RATE_MIN}
    return {
        "threshold": QUADRANT_CORRECT_RATE_MIN,
        "correct_rate_by_radius": by_radius,
        "below_threshold": below,
        "status": "pass" if not below else "flagged_for_human",
        "message": None if not below else "C5 外れ — 人間に上げる",
    }


# --------------------------------------------------------------------------
# run id / config / 成果物
# --------------------------------------------------------------------------


def rescore_run_id(source_run_id: str, *, now: datetime) -> str:
    """新しい run の id を組む(`<timestamp>_rescore_<元 run の suffix>`)。

    答える問い: 「この再採点を、元の run と結びつけて名付けるにはどうするか」

    元の run id は `<timestamp>_<suffix>` の形である(`code.artifacts.run_id_for`)。
    タイムスタンプは再採点した"いま"のものに置き換え、suffix だけ元から引く
    —— そうしないと新しい run が元の run の古い時刻を名乗ることになる。
    """
    parts = source_run_id.split("_", 2)
    if len(parts) != 3:
        raise ValueError(f"元の run id の形が想定と違う(<timestamp>_<suffix>): {source_run_id!r}")
    suffix = parts[2]
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{RUN_ID_INFIX}_{suffix}"


def prepare_rescore_run_dir(run_id: str, *, explicit: Path | None) -> Path:
    """再採点の成果物を書く run ディレクトリを作る。

    答える問い: 「再採点の成果物をどこに書くか」

    `code.artifacts.prepare_run_dir` は `experiment.id` から run id を作るので
    そのまま使えない(このモジュールの run id は `rescore_run_id` が作る別の
    書式である)。ディレクトリを作る手続き(`predictions/` を含む)だけを写す。
    """
    run_dir = explicit if explicit is not None else artifacts.RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / artifacts.PREDICTIONS_DIR).mkdir(exist_ok=True)
    return run_dir


def write_rescore_config(
    source_config_path: Path,
    target_config_path: Path,
    *,
    source_run_id: str,
) -> None:
    """元の config をコピーし、末尾に再採点の小さな記録を足す。

    答える問い: 「この config は、元の run のどれを、どの規則で採点し直した
    ものか」

    元の config を読み直して書き戻さない(`write_config_copy` と同じ理由。
    YAML を再 dump するとコメントが落ちる)。末尾に新しい top-level 鍵
    `rescore` を足すだけにする —— 元の config のどの鍵とも衝突しない
    (experiment / model / lesion / train / data / seeds / eval / resources)。
    """
    artifacts.write_config_copy(target_config_path.parent, source_config_path)
    record = {
        "rescore": {
            "source_run_id": source_run_id,
            "parser_rule": PARSER_RULE_NAME,
            "adr": ADR_REFERENCE,
        }
    }
    block = yaml.safe_dump(record, allow_unicode=True, sort_keys=False)
    with target_config_path.open("a", encoding="utf-8") as handle:
        handle.write("\n# --- 以下は再採点(PLAN-022 §5)が付記した記録。元の config には無い ---\n")
        handle.write(block)


def write_transitions(run_dir: Path, payload: Mapping[str, Any]) -> Path:
    """transitions.json を書く(PLAN-022 §5 / §5.1 C3)。"""
    path = run_dir / "transitions.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def transitions_payload(arm1: ArmRescore, arm2: ArmRescore, c3: Mapping[str, Any]) -> dict[str, Any]:
    """transitions.json の中身。腕ごとの旧分類 → 新分類の4x4件数表 + C3。"""
    return {
        sweep.PREDICTIONS_PREFIX: full_transition_matrix(arm1.before, arm1.after),
        sweep.QUADRANT_PREDICTIONS_PREFIX: full_transition_matrix(arm2.before, arm2.after),
        "c3_parse_fail_transitions": c3,
    }


def full_transition_matrix(
    before: Sequence[sweep.RadiusResult], after: Sequence[sweep.RadiusResult]
) -> dict[str, dict[str, int]]:
    """旧分類 → 新分類の件数表(4x4)。C3 が見る parse_fail の行もここに含まれる。

    答える問い: 「この腕で、旧分類のどのカテゴリが、新分類のどのカテゴリへ
    何件動いたか(動かなかった分も含む)」
    """
    matrix = {old: {new: 0 for new in CATEGORIES} for old in CATEGORIES}
    for before_radius, after_radius in zip(before, after, strict=True):
        for before_seed, after_seed in zip(
            before_radius.per_seed, after_radius.per_seed, strict=True
        ):
            for before_record, after_record in zip(
                before_seed.predictions, after_seed.predictions, strict=True
            ):
                matrix[before_record["classification"]][after_record["classification"]] += 1
    return matrix


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt / 標準出力に出す行。

    答える問い: 「この再採点は、どの run を、どの規則で採点し直し、
    検査 C1-C5 はどう終わったか」

    表そのものは `sweep.report_lines` を再利用する(書き直さない)。
    ここで足すのは、再採点であることの注記と C1-C5 の結果だけである。
    """
    rescore = payload["rescore"]
    lines = [
        f"再採点(PLAN-022 §5): 元の run = {rescore['source_run_id']} / "
        f"パーサ規則2 = {rescore['parser_rule']}({rescore['adr']})",
        "元の run の metrics.json / predictions/ は書き換えていない。",
        "",
    ]
    lines.extend(sweep.report_lines(payload))
    lines.append("")
    lines.extend(_checks_lines(payload["checks"]))
    return lines


def _checks_lines(checks: Mapping[str, Any]) -> list[str]:
    """C1-C5 の結果を log.txt 用の行にする。"""
    lines = ["■ 検査(PLAN-022 §5.1)"]
    lines.append(f"C1(集計の再現)      : {checks['c1_reproduces_source_metrics']['status']}")
    c2 = checks["c2_new_parser_is_superset"]
    lines.append(f"C2(新パーサの上位集合): {c2['status']}(違反 {c2['violations']} 件)")
    c3 = checks["c3_parse_fail_transitions"]
    lines.append(f"C3(旧 parse_fail の行き先): {c3['status']}" + (f" — {c3['message']}" if c3["message"] else ""))
    for arm_name, counts in c3["actual"].items():
        lines.append(f"  {arm_name}: 実測 {counts} / 期待 {c3['expected'][arm_name]}")
    lines.append(f"C4(4値合計 = 1.0)    : {checks['c4_rates_sum_to_one']['status']}")
    c5 = checks["c5_quadrant_correct_rate"]
    lines.append(
        f"C5(腕2 correct_rate >= {c5['threshold']}): {c5['status']}"
        + (f" — {c5['message']}" if c5["message"] else "")
    )
    for radius, rate in sorted(c5["correct_rate_by_radius"].items()):
        lines.append(f"  M={radius}: correct_rate={rate:.4f}")
    return lines


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def execute(*, source_run_dir: Path, run_dir: Path | None = None, now: datetime | None = None) -> Path:
    """順5 を新しい規則2 で採点し直し、成果物を新しい run ディレクトリに書く。

    答える問い: 「新パーサで読み直すと、順5 の4値分解と C1-C5 はどうなるか」

    C1 / C2 / C4 が1つでも外れたら、run ディレクトリを作る前に止める
    (`RescoreConsistencyError`)。元の run ディレクトリには何も書かない。
    """
    source_run_id = source_run_dir.name
    source_config_path = source_run_dir / "config.yaml"
    config = load_config(source_config_path)
    settings = load_generation_settings(config)
    plan = magnitude_sweep.load_sweep_plan(config)
    shell = magnitude_sweep.load_shell_plan(config, plan)
    setup = sweep.reference_setup(config)
    source_metrics = artifacts.read_metrics(source_run_dir)

    started = now or utc_now()
    run_started = monotonic_seconds()
    rescore_started = monotonic_seconds()
    arm1 = rescore_arm(
        source_run_dir,
        prefix=sweep.PREDICTIONS_PREFIX,
        radii=plan.radii,
        seeds=plan.seeds,
        reference_rule=setup.reference_rule,
        elicitation=setup.elicitation,
    )
    arm2 = rescore_arm(
        source_run_dir,
        prefix=sweep.QUADRANT_PREDICTIONS_PREFIX,
        radii=shell.radii,
        seeds=plan.seeds,
        reference_rule=setup.reference_rule,
        elicitation=setup.elicitation,
    )
    rescore_seconds = elapsed_seconds(rescore_started)

    # C1: 止める(RescoreConsistencyError)。旧分類だけの再集計が元の metrics.json と一致するか
    reproduction = reproduce_source_metrics(
        config, settings, plan, shell, arm1.before, arm2.before, now=started
    )
    c1 = check_c1_reproduces_source_metrics(reproduction, source_metrics)

    # C2: 止める。旧パーサが読めていた値は新パーサでも同じ値か
    c2 = check_c2_new_parser_is_a_superset(arm1.parse_violations + arm2.parse_violations)

    run_id = rescore_run_id(source_run_id, now=started)
    ended = utc_now()
    timing = timing_record(
        started=started,
        ended=ended,
        total_seconds=elapsed_seconds(run_started),
        model_load_seconds=0.0,
        generation_seconds=rescore_seconds,
        n_items=sweep.total_items(arm1.after) + sweep.total_items(arm2.after),
    )
    payload = sweep.metrics_payload(
        config, settings, plan, arm1.after,
        shell=shell, quadrant=arm2.after,
        run_id=run_id, timing=timing,
    )
    payload["rescore"] = {
        "source_run_id": source_run_id,
        "parser_rule": PARSER_RULE_NAME,
        "adr": ADR_REFERENCE,
    }
    c3 = check_c3_parse_fail_transitions(arm1, arm2)
    c5 = check_c5_quadrant_correct_rate(payload)
    # C4: 止める。書き出す直前の payload そのものを走査する。checks ブロックに
    # 足す前に呼ぶのは、C4 が payload の rate_fields だけを見て checks を見ないため
    # (checks を先に足しても足さなくても判定は変わらないが、self 参照を避ける)。
    c4 = check_c4_rates_sum_to_one(payload)
    payload["checks"] = {
        "c1_reproduces_source_metrics": c1,
        "c2_new_parser_is_superset": c2,
        "c3_parse_fail_transitions": c3,
        "c4_rates_sum_to_one": c4,
        "c5_quadrant_correct_rate": c5,
    }

    target = prepare_rescore_run_dir(run_id, explicit=run_dir)
    write_rescore_config(source_config_path, target / "config.yaml", source_run_id=source_run_id)
    write_git_sha(target)
    write_metrics(target, payload)
    write_transitions(target, transitions_payload(arm1, arm2, c3))
    for prefix, arm in (
        (sweep.PREDICTIONS_PREFIX, arm1),
        (sweep.QUADRANT_PREDICTIONS_PREFIX, arm2),
    ):
        for result in arm.after:
            for seed_result in result.per_seed:
                write_predictions(
                    target,
                    f"{prefix}_M{result.radius}_s{seed_result.seed}",
                    seed_result.predictions,
                )
    lines = report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="順5 を新しい規則2(unanimous_integer)で採点し直す(PLAN-022 §5)"
    )
    parser.add_argument("--source-run", required=True, type=Path, help="採点し直す元の run ディレクトリ")
    parser.add_argument(
        "--run-dir", type=Path, default=None,
        help="成果物の書き出し先。既定は runs/<timestamp>_rescore_<元 run の suffix>/",
    )
    args = parser.parse_args(argv)
    target = execute(source_run_dir=args.source_run, run_dir=args.run_dir)
    print(f"再採点の成果物: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
