"""本実行の run(`code/eval/run.py` が書いた `runs/<id>/`)を現行のパーサで採点し直す。

答える問い: 「★F140 の規則 C を足したパーサで読み直すと、本実行の4値分解と
Go/No-Go の印はどう動くか」(PLAN-027 §1 / §6)

    python -m code.eval.rescore_run --source-run runs/20260911_141547_order6_r1

**GPU は使わない。**回収済みの `predictions/*.jsonl` の `response` 列を現行の
`code.eval.parsers.numeric` で読み直すだけであり、モデルは1度も呼ばない。

**元の run ディレクトリには何も書かない**(ADR-074 決定2)。成果物はすべて新しい
`runs/<timestamp>_rescore_<元の run の suffix>/` に書く。

**`code/eval/rescore.py` は桁数掃引の run 専用である** —— `sweep.py` の3ブロック
(`by_radius` / `grid_shell` / `quadrant`)を組むので、`by_batch` を持つ本実行の run は
読めない。そこを開けるのがこの入口である(PLAN-027 §6)。run id の組み方・run
ディレクトリの作り方・config の複製・上位集合の判定は、**そちらの関数をそのまま使う**
(2通りの書式を持たない)。

**集計は `code/eval/run.py` の関数を再利用する** —— `metrics_payload` /
`batch_metrics_record` / `metrics_by_reference_rule` / `BatchResult` を書き直さない。
集計の式を2箇所に持つと、片方だけを直したときに再採点の `by_batch` が本実行と
食い違っても誰も気づかない。

**バッチの単位は `predictions/<バッチ名>.jsonl` のファイル名である**(本実行が
`write_predictions` でそう書いている)。**項目プールを読み直さない** —— プールが
手元に無い run でも再採点できるようにするためである(`predictions/` は git に無い。
PLAN-017 F79)。`pool` / `coverage` / `adapter` / `preamble` / `task_subset` の各ブロックは
元の `metrics.json` から**そのまま引き写す**(再採点は項目集合も重みも変えない)。

**二値群(`comparison`)は読み直さない**(ADR-047。強制選択はパーサを通らない)。
保存済みの `parsed` をそのまま使い、常答戦略ベースラインも保存済みの `truth` /
`rule_values` から組み直す。読み直すのは**数値型の行(`truth` が bool でない行)**だけである。

**5つの検査(C1-C5)を必ず走らせる**(PLAN-027 §6.1)。C1 / C2 / C4 は外れたら
`metrics.json` を書く前に止める(`RescoreRunError`)。C3 / C5 は外れても止めない ——
実測をそのまま記録し、`checks` ブロックと `log.txt` に「人間に上げる」と明記する
(`CLAUDE.md` §8: 解釈・採否は人間の仕事)。
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from code import artifacts
from code.analysis import gonogo
from code.analysis.frame import FrameError
from code.artifacts import (
    elapsed_seconds,
    monotonic_seconds,
    timing_record,
    utc_now,
    write_git_sha,
    write_log,
    write_metrics,
    write_predictions,
    write_timestamps,
)
from code.config import ConfigError, load_config
from code.eval import run as eval_run
from code.eval.model import load_generation_settings
from code.eval.rescore import (
    VIOLATIONS_SHOWN,
    is_superset_violation,
    prepare_rescore_run_dir,
    read_predictions,
    rescore_run_id,
    write_rescore_config,
)
from code.eval.scoring import ItemResponse, classify
from code.rates import (
    CATEGORIES,
    CORRECT,
    OTHER_ERROR,
    PARSE_FAIL,
    RATE_FIELDS,
    RULE,
    TOTAL_TOLERANCE,
)

# このモジュールが当てる採点規則の名前(`code/eval/parsers/numeric.py` の現行の規則)。
# 規則2(`unanimous_integer`。ADR-074 決定2)に ★F140 の規則 C(ADR-088 決定1)を
# 足したもの。**config.yaml / metrics.json の記録に使うだけで、値は変えない。**
PARSER_RULE_NAME = "unanimous_integer+f140"

# この再採点の根拠になった ADR。
ADR_REFERENCE = "ADR-078 決定11 / ADR-088 決定1"

# config.yaml の末尾に付ける注記(`write_rescore_config`)。
CONFIG_NOTE = "\n# --- 以下は再採点(PLAN-027 §6)が付記した記録。元の config には無い ---\n"

# PLAN-027 §3.2 の C 列。**実装前に回収済みの `predictions/` を候補規則で読み直して
# 数えた見積りであり、公式の遷移表はこの CLI が出す**(§3 の前書き)。外れても止めない。
# 鍵は元の run id。**表に無い run には期待値が無い** —— 順6b の run はここで初めて測る
# ので、C3 は「期待値なし」として記録だけを残す(印も外れも付けない)。
EXPECTED_C3_TRANSITIONS: dict[str, dict[str, int]] = {
    "20260911_141547_order6_r1": {CORRECT: 2, RULE: 0, OTHER_ERROR: 0, PARSE_FAIL: 0},
    "20260911_160132_order6_r2": {CORRECT: 2, RULE: 0, OTHER_ERROR: 0, PARSE_FAIL: 0},
    "20260911_160937_order6_r3": {CORRECT: 2, RULE: 0, OTHER_ERROR: 0, PARSE_FAIL: 0},
    "20260911_161738_order6_r4": {CORRECT: 3, RULE: 0, OTHER_ERROR: 0, PARSE_FAIL: 0},
    "20260911_163337_order6_r5": {CORRECT: 0, RULE: 0, OTHER_ERROR: 0, PARSE_FAIL: 0},
}

# C5 の印の鍵の頭(Go/No-Go の #1 / #2 / #3)。
MARK_PREFIXES: dict[str, str] = {"parse_fail": "#1", "cells": "#2", "constant_strategy": "#3"}


class RescoreRunError(RuntimeError):
    """元の run が読めないか、C1 / C2 / C4 のいずれかが外れた(PLAN-027 §6.1)。

    止める理由は検査ごとに違うが、どれも「集計か新パーサの上位集合性が壊れている」
    という実装のバグを疑う理由になる(`CLAUDE.md` §7)。`metrics.json` は書かない。
    """


# --------------------------------------------------------------------------
# 元の run の読み取り
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchSpec:
    """1採点バッチが「何だったか」(元の `metrics.json` の `by_batch` の1項目)。

    答える問い: 「このバッチは、どの群の、どの採点方式で、どの参照規則だったか」
    """

    name: str
    group: str
    scoring: str
    reference_rule: str
    n_items: int


def batch_specs(source_metrics: Mapping[str, Any]) -> list[BatchSpec]:
    """元の `metrics.json` の `by_batch` から採点バッチの一覧を組む。

    答える問い: 「この run は、どのバッチを、どの順で採点したか」

    **バッチの一覧をプールから作り直さない。**元の run が解いた単位をそのまま使う ——
    `eval.task_subset` で絞った run(PLAN-026 I8)や答え域で割ったバッチ(ADR-077)を、
    こちらで組み直すと元の `by_batch` と割り方が変わりうる。
    """
    by_batch = source_metrics.get("by_batch")
    if not by_batch:
        raise RescoreRunError("元の metrics.json に by_batch が無い。本実行の run ではない")
    return [
        BatchSpec(
            name=name,
            group=batch["group"],
            scoring=batch["scoring"],
            reference_rule=batch["primary_reference_rule"],
            n_items=batch["n_items"],
        )
        for name, batch in by_batch.items()
    ]


def check_source_kind(source_metrics: Mapping[str, Any], source_run_id: str) -> None:
    """本実行の run(`battery_eval`)であることを確かめる。

    答える問い: 「この run は 4 値分解を持つか」

    **閾値掃引(`threshold_sweep`)・(c) の較正(`calibration`)・桁数掃引は読めない。**
    掃引の run は率を持たず(PLAN-026 §3.2・§4.5 読み2)、較正は `Item` も `classify` も
    通らない(同 §4.9)。黙って 0 件の表を出すと「差が無かった」と読めてしまう。
    """
    kind = source_metrics.get("kind")
    if kind != eval_run.EVAL_KIND:
        raise RescoreRunError(
            f"{source_run_id}: kind={kind!r} は再採点できない。4 値分解を持つのは "
            f"{eval_run.EVAL_KIND!r} の run だけである(掃引と較正は率を持たない)。"
            "桁数掃引の run は python -m code.eval.rescore を使うこと"
        )


def is_binary_row(row: Mapping[str, Any]) -> bool:
    """この行は二値群(強制選択)の行か。

    答える問い: 「この行はパーサを通ったのか、Yes/No のロジット比較で決まったのか」

    **判定は真値の型で行う**(ADR-047 / `scoring.classify` と同じ作法)。bool は int の
    派生なので、群の名前ではなく型で見るほうが取り違えに強い。
    """
    return isinstance(row["truth"], bool)


def rescore_row(row: Mapping[str, Any], *, elicitation: str) -> dict[str, Any]:
    """1件の応答を現行のパーサで読み直し、分類し直す。

    答える問い: 「この行の `response` を現行の規則で読み直すと、`parsed` と
    `classification` はどう変わるか」

    元の行の全フィールドをそのまま残し、`parsed` / `classification` を新しい値に
    置き換え、旧値を `parsed_before` / `classification_before` として足す。
    **二値群の行は `parsed` を触らない**(ADR-047。強制選択はパーサを通らない)ので
    2つの欄は旧値と同じ値になる —— 欄を置かないと「読み直した行」と
    「読み直していない行」をファイルから見分けられない。

    分類は `code/eval/scoring.py` の `classify` を再利用する —— 採点の規則
    (correct → rule → other_error → parse_fail の順序)をここで書き直すと、
    本実行の採点とずれても誰も気づかない。
    """
    if is_binary_row(row):
        new_parsed: Any = row["parsed"]
    else:
        new_parsed = eval_run.parse_numeric_response(row["response"], elicitation)
    rule_value = row["rule_values"][row["reference_rule"]]
    rescored = dict(row)
    rescored["parsed_before"] = row["parsed"]
    rescored["classification_before"] = row["classification"]
    rescored["parsed"] = new_parsed
    rescored["classification"] = classify(new_parsed, row["truth"], rule_value)
    return rescored


def item_responses(rows: Sequence[Mapping[str, Any]]) -> list[ItemResponse]:
    """予測の行から採点用の応答を組む(`parsed` はその行に入っている値)。

    答える問い: 「この行の集合を `code/eval/scoring.py` に渡せる形にすると何か」

    旧行(`before`)でも再採点した行(`after`)でも同じ関数で組めるようにするのは、
    C1(旧行からの再集計)と本採点(新行での集計)を同じ経路で作るためである。
    """
    return [
        ItemResponse(
            item_id=row["item_id"],
            parsed=row["parsed"],
            truth=row["truth"],
            rule_values=dict(row["rule_values"]),
        )
        for row in rows
    ]


@dataclass(frozen=True)
class BatchRescore:
    """1バッチを読み直した結果。

    答える問い: 「このバッチの旧行・新行・C2 違反はそれぞれ何か」
    """

    spec: BatchSpec
    before: list[dict[str, Any]]
    after: list[dict[str, Any]]
    parse_violations: list[str] = field(default_factory=list)
    stale_classifications: list[str] = field(default_factory=list)


def rescore_batch(source_run_dir: Path, spec: BatchSpec, *, elicitation: str) -> BatchRescore:
    """1バッチの `predictions/<バッチ名>.jsonl` を読み直す。

    答える問い: 「このバッチの行を現行のパーサで読み直すと何になるか。
    元の `metrics.json` の記録と食い違っていないか」

    **記録との食い違いは止める** —— 件数・群・採点方式・参照規則のどれかがずれていたら、
    読んでいるファイルがそのバッチのものではない可能性がある。黙って集計すると、
    その取り違えが4値分解の差として現れてしまう。
    """
    path = source_run_dir / artifacts.PREDICTIONS_DIR / f"{spec.name}.jsonl"
    rows = read_predictions(path)
    if len(rows) != spec.n_items:
        raise RescoreRunError(
            f"{spec.name}: predictions は {len(rows)} 行だが metrics.json の n_items は "
            f"{spec.n_items} である"
        )
    for row in rows:
        if row["group"] != spec.group:
            raise RescoreRunError(
                f"{spec.name}: 行 {row['item_id']!r} の group={row['group']!r} が "
                f"metrics.json の {spec.group!r} と違う"
            )
        if row["reference_rule"] != spec.reference_rule:
            raise RescoreRunError(
                f"{spec.name}: 行 {row['item_id']!r} の reference_rule="
                f"{row['reference_rule']!r} が metrics.json の {spec.reference_rule!r} と違う"
            )
    binary = [is_binary_row(row) for row in rows]
    if any(binary) != all(binary):
        raise RescoreRunError(f"{spec.name}: 二値の行と数値の行が同じバッチに混ざっている")
    if all(binary) != (spec.scoring == eval_run.SCORING_FORCED_CHOICE):
        raise RescoreRunError(
            f"{spec.name}: scoring={spec.scoring!r} と行の型(二値={all(binary)})が噛み合わない"
        )
    rescored = [rescore_row(row, elicitation=elicitation) for row in rows]
    return BatchRescore(
        spec=spec,
        before=list(rows),
        after=rescored,
        parse_violations=[
            row["item_id"]
            for row, new_row in zip(rows, rescored, strict=True)
            if is_superset_violation(row, new_row)
        ],
        stale_classifications=[
            row["item_id"]
            for row in rows
            if classify(row["parsed"], row["truth"], row["rule_values"][row["reference_rule"]])
            != row["classification"]
        ],
    )


def batch_result(spec: BatchSpec, rows: Sequence[Mapping[str, Any]]) -> eval_run.BatchResult:
    """1バッチの行から `BatchResult` を組む(集計は本実行と同じ関数)。

    答える問い: 「このバッチの行の集合を、本実行と同じ式で集計すると何になるか」
    """
    return eval_run.BatchResult(
        name=spec.name,
        group=spec.group,
        reference_rule=spec.reference_rule,
        metrics=eval_run.batch_metrics_record(
            spec.group, spec.scoring, item_responses(rows), spec.reference_rule
        ),
        predictions=list(rows),
    )


# --------------------------------------------------------------------------
# C1: 保存済みの行からの再集計が元の metrics.json と一致するか
# --------------------------------------------------------------------------


def check_c1_reproduces_source_metrics(
    batches: Sequence[BatchRescore], source_metrics: Mapping[str, Any]
) -> dict[str, Any]:
    """C1: 保存済みの行から組み直した `by_batch` が元の `metrics.json` と一致するか。

    答える問い: 「元の run が書いた4値分解を、保存済みの `predictions/` から
    作り直すと、本当に同じものが出るか」(PLAN-027 §6.1 C1)

    **2つを見る。**(1) 行の `classification` が、その行の `parsed` / `truth` /
    `rule_values` から `classify` を引いた値と一致すること。(2) 旧行からの再集計が
    元の `by_batch` と全バッチ・全参照規則で一致すること。

    PLAN-027 §6.1 の文面は「保存済みの `classification` だけから集計し直す」と書くが、
    **行に残っているのは主要参照規則の分類だけ**であり、`by_reference_rule` の他の
    ブロックは `parsed` から引き直さなければ作れない。そこで (1) で分類の一致を
    確かめたうえで、(2) は `parsed` から本実行と同じ関数で組む —— 文面の意図
    (「集計が再現できるか」)を全参照規則について検査する形である。

    どちらが外れても止める。集計そのものが再現できていないのなら、その先の
    再採点を報告しても意味を持たない(`CLAUDE.md` §7)。

    **比べるのは JSON に書いた形どうしである**(`rescore.check_c1_...` と同じ理由)。
    """
    stale = [item_id for batch in batches for item_id in batch.stale_classifications]
    if stale:
        shown = stale[:VIOLATIONS_SHOWN]
        raise RescoreRunError(
            f"C1: 保存済みの classification が parsed から引き直した分類と違う行が "
            f"{len(stale)} 件ある: {shown}{'…' if len(stale) > VIOLATIONS_SHOWN else ''}"
        )
    reproduction = {
        batch.spec.name: batch_result(batch.spec, batch.before).metrics for batch in batches
    }
    written = json.loads(json.dumps(reproduction, ensure_ascii=False))
    source = source_metrics["by_batch"]
    mismatched = [name for name in written if written[name] != source.get(name)]
    if mismatched:
        raise RescoreRunError(
            f"C1: 保存済みの行からの再集計が元の metrics.json と一致しない({mismatched})。"
            "集計の再現が壊れている。"
        )
    return {"status": "pass", "batches": len(written)}


# --------------------------------------------------------------------------
# C2: 保存済み parsed が None でない行は、新パーサでも同じ値になるか
# --------------------------------------------------------------------------


def check_c2_new_parser_is_a_superset(violations: Sequence[str]) -> dict[str, Any]:
    """C2: 新パーサが旧パーサの上位集合になっているか。

    答える問い: 「旧パーサが読めていた値は、新パーサでも同じ値・同じ分類のままか」
    (PLAN-027 §6.1 C2。判定の1行ぶんは `rescore.is_superset_violation`)

    ★F140 の規則 C は「現行の経路が None を返したときだけ」働く(ADR-088 決定1)ので、
    上位集合であることはコードの形から言える。ここはその再確認であり、1件でも
    外れたら実装のバグである(`CLAUDE.md` §7)。
    """
    if violations:
        shown = violations[:VIOLATIONS_SHOWN]
        suffix = "…" if len(violations) > VIOLATIONS_SHOWN else ""
        raise RescoreRunError(
            f"C2: 新パーサが上位集合になっていない(値か分類が変わった item_id "
            f"{len(violations)} 件): {shown}{suffix}"
        )
    return {"status": "pass", "violations": len(violations)}


# --------------------------------------------------------------------------
# C3: 旧 parse_fail 行の行き先(診断。外れても止めない)
# --------------------------------------------------------------------------


def parse_fail_transition_counts(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    """旧分類が `parse_fail` だった行が、新分類でどこへ散ったかを数える。

    答える問い: 「このバッチで、旧規則が読めなかった行のうち、現行の規則は何件を
    correct / rule / other_error に変え、何件がなお parse_fail のままか」
    """
    counts = {category: 0 for category in CATEGORIES}
    for before_row, after_row in zip(before, after, strict=True):
        if before_row["classification"] == PARSE_FAIL:
            counts[after_row["classification"]] += 1
    return counts


def check_c3_parse_fail_transitions(
    batches: Sequence[BatchRescore], source_run_id: str
) -> dict[str, Any]:
    """C3: 旧 `parse_fail` 行の行き先を、PLAN-027 §3.2 の見積りと突き合わせる。

    答える問い: 「旧 parse_fail 行の行き先の実測は、その67 が数えた見積りと一致するか」
    (PLAN-027 §6.1 C3)

    **外れても止めない。**見積りの数え方と実装が違う可能性はあるが、それを判断するのは
    人間である(`CLAUDE.md` §8)。実測をそのまま記録する。

    **見積りが無い run では判定しない**(`expected` も `matches` も null)。順6b の run は
    ここで初めて測るので、「外れた」とも「合った」とも書かない。
    """
    by_batch = {
        batch.spec.name: parse_fail_transition_counts(batch.before, batch.after)
        for batch in batches
    }
    total = {
        category: sum(counts[category] for counts in by_batch.values())
        for category in CATEGORIES
    }
    expected = EXPECTED_C3_TRANSITIONS.get(source_run_id)
    if expected is None:
        return {
            "expected": None,
            "actual_total": total,
            "actual_by_batch": by_batch,
            "matches": None,
            "status": "no_expectation",
            "message": "PLAN-027 §3.2 に見積りが無い run — 実測を記録するだけ(印は付けない)",
        }
    matches = total == expected
    return {
        "expected": expected,
        "actual_total": total,
        "actual_by_batch": by_batch,
        "matches": matches,
        "status": "pass" if matches else "flagged_for_human",
        "message": None if matches else "C3 外れ — 人間に上げる",
    }


# --------------------------------------------------------------------------
# C4: 4値の合計が全バッチ・全参照規則で 1.0 か
# --------------------------------------------------------------------------


def _rate_blocks(payload: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """`metrics.json` の中で4値分解を持つブロックをすべて集める(C4 の対象)。

    答える問い: 「合計 1.0 を検査すべき行はどれか」

    参照規則ごとのブロックに加えて、二値群の常答戦略ベースラインも4値分解である
    (`constant_answer_baseline` が `RateBreakdown` を返す)。両方を見る。
    """
    blocks: list[tuple[str, Mapping[str, Any]]] = []
    for name, batch in payload["by_batch"].items():
        for rule, block in batch["by_reference_rule"].items():
            blocks.append((f"{name}/{rule}", block))
        for label, block in (batch.get("constant_answer_baselines") or {}).items():
            blocks.append((f"{name}/baseline:{label}", block))
    return blocks


def check_c4_rates_sum_to_one(payload: Mapping[str, Any]) -> dict[str, Any]:
    """C4: 4値の合計が、全バッチ・全参照規則で 1.0 になっているか。

    答える問い: 「metrics.json に書く最終形のどの行を見ても、4値の合計は 1.0 か」
    (PLAN-027 §6.1 C4 / `CLAUDE.md` §6)

    `RateBreakdown.__post_init__` が個々の構築時にも検査しているが、ここでは
    書き出す直前の payload そのものを走査する(skill `code-style` §4)。1件でも外れたら止める。
    """
    broken = []
    for label, block in _rate_blocks(payload):
        if block.get("n_items", 0) == 0:
            continue
        total = sum(block[key] for key in RATE_FIELDS)
        if abs(total - 1.0) > TOTAL_TOLERANCE:
            broken.append((label, total))
    if broken:
        raise RescoreRunError(f"C4: 4値の合計が 1.0 でないブロックがある: {broken}")
    return {"status": "pass", "blocks": len(_rate_blocks(payload))}


# --------------------------------------------------------------------------
# C5: Go/No-Go の印が動かないか(診断。外れても止めない。ADR-088 決定4)
# --------------------------------------------------------------------------


def gonogo_marks(metrics_path: Path) -> dict[str, bool]:
    """1つの run の Go/No-Go の印(#1 / #2 / #3)を平らな辞書にする。

    答える問い: 「この run で、基準を割ったのはどの行・どのセルか」

    **表そのものは `code/analysis/gonogo.py` が組む**(印の付け方をここで書き直さない。
    PLAN-027 §7「印・閾値を変えない」)。ここは印だけを取り出して並べる。
    """
    report = gonogo.run_report(metrics_path)
    marks: dict[str, bool] = {}
    for row in report["parse_fail"]:
        marks[f"{MARK_PREFIXES['parse_fail']}/{row['group']}"] = bool(row["fails"])
    for key in ("cells", "constant_strategy"):
        for row in report[key]:
            marks[f"{MARK_PREFIXES[key]}/{row['task']}/{row['coverage']}"] = bool(row["fails"])
    return marks


def check_c5_gonogo_marks(source_metrics_path: Path, target_metrics_path: Path) -> dict[str, Any]:
    """C5: Go/No-Go の印が、元の run と1つも違わないか。

    答える問い: 「パーサを変えても、#1 / #2 / #3 の印は動かないか」
    (PLAN-024 §4.1 の見込み。PLAN-027 §6.1 C5。ADR-088 決定4 = CLI の中で `gonogo` を呼ぶ)

    **門ではない。**動いたら止めずに数字を出し、人間に上げる。**印は置き直さない**
    (`CLAUDE.md` §8)。**Go/No-Go の表を組めない run では、その理由を記録して人間に上げる**
    —— 主軸のセルが空・被覆 K の manifest が手元に無い・config に閾値が無い、のどれでも
    起こりうる。黙って「印は動かなかった」にしない。**止めない検査なので例外で落とさない。**
    """
    try:
        before = gonogo_marks(source_metrics_path)
        after = gonogo_marks(target_metrics_path)
    except (gonogo.GoNoGoError, FrameError, ConfigError, FileNotFoundError) as error:
        return {
            "comparable": False,
            "changed": None,
            "n_marks": None,
            "status": "flagged_for_human",
            "message": f"Go/No-Go の表を組めなかった — 人間に上げる: {error}",
        }
    keys = sorted(set(before) | set(after))
    changed = {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    }
    return {
        "comparable": True,
        "changed": changed,
        "n_marks": len(keys),
        "status": "pass" if not changed else "flagged_for_human",
        "message": None if not changed else "C5 外れ(印が動いた)— 人間に上げる。印は置き直さない",
    }


# --------------------------------------------------------------------------
# 成果物
# --------------------------------------------------------------------------


def rescore_record(source_run_id: str, batches: Sequence[BatchRescore]) -> dict[str, Any]:
    """この再採点が何を、どの規則で採点し直したかの記録。

    答える問い: 「この run は、元の run のどれを、どの規則で、どの行について
    採点し直したものか」

    `config.yaml` と `metrics.json` の両方に同じものを書く(2か所で組むと食い違う)。
    **二値群の行は読み直していない**ので、その件数を分けて残す(ADR-047)。
    """
    rescored = sum(
        1 for batch in batches for row in batch.before if not is_binary_row(row)
    )
    untouched = sum(1 for batch in batches for row in batch.before if is_binary_row(row))
    return {
        "source_run_id": source_run_id,
        "parser_rule": PARSER_RULE_NAME,
        "adr": ADR_REFERENCE,
        "plan": "PLAN-027 §6",
        "n_rows_rescored": rescored,
        "n_rows_forced_choice_untouched": untouched,
    }


def transitions_payload(batches: Sequence[BatchRescore], c3: Mapping[str, Any]) -> dict[str, Any]:
    """`transitions.json` の中身。バッチごとの旧分類 → 新分類の 4x4 件数表 + C3。"""
    return {
        "by_batch": {
            batch.spec.name: full_transition_matrix(batch.before, batch.after) for batch in batches
        },
        "total": full_transition_matrix(
            [row for batch in batches for row in batch.before],
            [row for batch in batches for row in batch.after],
        ),
        "c3_parse_fail_transitions": c3,
    }


def full_transition_matrix(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, int]]:
    """旧分類 → 新分類の件数表(4x4)。動かなかった分も含む。

    答える問い: 「旧分類のどのカテゴリが、新分類のどのカテゴリへ何件動いたか」
    """
    matrix = {old: {new: 0 for new in CATEGORIES} for old in CATEGORIES}
    for before_row, after_row in zip(before, after, strict=True):
        matrix[before_row["classification"]][after_row["classification"]] += 1
    return matrix


def write_transitions(run_dir: Path, payload: Mapping[str, Any]) -> Path:
    """`transitions.json` を書く(PLAN-027 §6)。"""
    path = run_dir / "transitions.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path


def comparison_lines(
    payload: Mapping[str, Any], source_metrics: Mapping[str, Any]
) -> list[str]:
    """旧・新の4値をバッチごとに並べる行(PLAN-027 §6.1「4値すべてを並べて出す」)。

    答える問い: 「このバッチの4値は、再採点で何から何へ動いたか」

    **4値すべてを常に出す**(`CLAUDE.md` §6)。`other_error` だけが動いていれば、
    それは回収ではなくモデルの崩壊の読み違えである。
    """
    lines = ["■ 旧 → 新(主要参照規則のブロック。4値すべて)"]
    for name, batch in payload["by_batch"].items():
        rule = batch["primary_reference_rule"]
        new_block = batch["by_reference_rule"][rule]
        old_block = source_metrics["by_batch"][name]["by_reference_rule"][rule]
        lines.append(f"[{name}] rule={rule} n={new_block['n_items']}")
        for field_name in RATE_FIELDS:
            lines.append(
                f"    {field_name:17s} {old_block[field_name]:.4f} -> {new_block[field_name]:.4f}"
            )
    return lines


def report_lines(payload: Mapping[str, Any], source_metrics: Mapping[str, Any]) -> list[str]:
    """`log.txt` / 標準出力に出す行。

    答える問い: 「この再採点は、どの run を、どの規則で採点し直し、
    4値と検査 C1-C5 はどうなったか」

    run の見出しとバッチごとの行は `code/eval/run.py` の `report_lines` を再利用する
    (書き直さない)。ここで足すのは、再採点であることの注記・旧新の並べ・C1-C5 だけである。
    """
    record = payload["rescore"]
    lines = [
        f"再採点(PLAN-027 §6): 元の run = {record['source_run_id']} / "
        f"パーサ規則 = {record['parser_rule']}({record['adr']})",
        "元の run の metrics.json / predictions/ は書き換えていない。",
        f"読み直した行: {record['n_rows_rescored']} / "
        f"二値群(強制選択。読み直していない): {record['n_rows_forced_choice_untouched']}",
        "",
    ]
    lines.extend(eval_run.report_lines(payload))
    lines.append("")
    lines.extend(comparison_lines(payload, source_metrics))
    lines.append("")
    lines.extend(checks_lines(payload["checks"]))
    return lines


def checks_lines(checks: Mapping[str, Any]) -> list[str]:
    """C1-C5 の結果を `log.txt` 用の行にする。"""
    lines = ["■ 検査(PLAN-027 §6.1)"]
    lines.append(f"C1(集計の再現)        : {checks['c1_reproduces_source_metrics']['status']}")
    c2 = checks["c2_new_parser_is_superset"]
    lines.append(f"C2(新パーサの上位集合) : {c2['status']}(違反 {c2['violations']} 件)")
    c3 = checks["c3_parse_fail_transitions"]
    lines.append(
        f"C3(旧 parse_fail の行き先): {c3['status']}"
        + (f" — {c3['message']}" if c3["message"] else "")
    )
    lines.append(f"  実測(合計): {c3['actual_total']} / 期待: {c3['expected']}")
    for name, counts in c3["actual_by_batch"].items():
        if any(counts.values()):
            lines.append(f"  {name}: {counts}")
    lines.append(f"C4(4値合計 = 1.0)      : {checks['c4_rates_sum_to_one']['status']}")
    c5 = checks["c5_gonogo_marks"]
    lines.append(
        f"C5(Go/No-Go の印)      : {c5['status']}" + (f" — {c5['message']}" if c5["message"] else "")
    )
    if c5["comparable"]:
        lines.append(f"  印 {c5['n_marks']} 個のうち動いたもの: {c5['changed'] or 'なし'}")
    return lines


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def execute(
    *, source_run_dir: Path, run_dir: Path | None = None, now: datetime | None = None
) -> Path:
    """本実行の run を現行のパーサで採点し直し、成果物を新しい run ディレクトリに書く。

    答える問い: 「現行のパーサで読み直すと、この run の4値分解と Go/No-Go の印は
    どうなるか」

    C1 / C2 が外れたら、run ディレクトリを作る前に止める(`RescoreRunError`)。
    C4 は payload を書く前に止める。**元の run ディレクトリには何も書かない。**

    **`metrics.json` は2度書く。**C5 は書き上がった run を `code/analysis/gonogo.py` に
    読ませるので(ADR-088 決定4)、1度目で run を成立させ、印を比べてから
    `checks.c5_gonogo_marks` を足して書き直す。`log.txt` は C5 の後に1度だけ書く。
    """
    source_run_dir = source_run_dir.resolve()
    source_run_id = source_run_dir.name
    source_config_path = source_run_dir / "config.yaml"
    config = load_config(source_config_path)
    settings = load_generation_settings(config)
    source_metrics = artifacts.read_metrics(source_run_dir)
    check_source_kind(source_metrics, source_run_id)
    elicitation = source_metrics["elicitation"]

    started = now or utc_now()
    run_started = monotonic_seconds()
    rescore_started = monotonic_seconds()
    batches = [
        rescore_batch(source_run_dir, spec, elicitation=elicitation)
        for spec in batch_specs(source_metrics)
    ]
    rescore_seconds = elapsed_seconds(rescore_started)

    # C1 / C2: 止める。run ディレクトリを作る前に掛ける
    c1 = check_c1_reproduces_source_metrics(batches, source_metrics)
    c2 = check_c2_new_parser_is_a_superset(
        [item_id for batch in batches for item_id in batch.parse_violations]
    )

    run_id = rescore_run_id(source_run_id, now=started)
    results = [batch_result(batch.spec, batch.after) for batch in batches]
    ended = utc_now()
    payload = eval_run.metrics_payload(
        config,
        settings,
        results,
        run_id=run_id,
        pool=source_metrics["pool"],
        coverage=source_metrics["coverage"],
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=0.0,
            generation_seconds=rescore_seconds,
            n_items=eval_run.total_items(results),
        ),
        adapter={
            "seed": source_metrics["seed"],
            "adapter": source_metrics["adapter"],
            "train_run_id": source_metrics["adapter_train_run_id"],
            "note": source_metrics["adapter_note"],
        },
        preamble=source_metrics.get("preamble"),
        task_subset=source_metrics.get("task_subset"),
    )
    # 強制選択の器械の記録は重みを読んだ実行にしかない(`run.forced_choice_block`)。
    # 再採点はモデルを呼ばないので、元の run の欄をそのまま引き写す。
    if "forced_choice" in source_metrics:
        forced = dict(source_metrics["forced_choice"])
        # 上位 k の記録(PLAN-026 I10)より前の run には `top_k` の欄が無い。欄ごと
        # 落とすと「記録しなかった」と「この記録が入る前の run」を区別できないので
        # null で置く(`run.forced_choice_block` と同じ作法)。
        forced.setdefault("top_k", None)
        payload["forced_choice"] = forced
    record = rescore_record(source_run_id, batches)
    payload["rescore"] = record
    c3 = check_c3_parse_fail_transitions(batches, source_run_id)
    c4 = check_c4_rates_sum_to_one(payload)  # 止める
    payload["checks"] = {
        "c1_reproduces_source_metrics": c1,
        "c2_new_parser_is_superset": c2,
        "c3_parse_fail_transitions": c3,
        "c4_rates_sum_to_one": c4,
    }

    if run_dir is not None and run_dir.resolve() == source_run_dir:
        # 元の run に何も書かない(ADR-074 決定2)。ディレクトリを作る前に止める
        raise RescoreRunError(f"書き出し先が元の run と同じである: {run_dir}")
    target = prepare_rescore_run_dir(run_id, explicit=run_dir)
    write_rescore_config(target, source_config_path, record, note=CONFIG_NOTE)
    write_git_sha(target)
    for batch in batches:
        write_predictions(target, batch.spec.name, batch.after)
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=ended)

    payload["checks"]["c5_gonogo_marks"] = check_c5_gonogo_marks(
        source_run_dir / artifacts.METRICS_FILE, target / artifacts.METRICS_FILE
    )
    write_metrics(target, payload)
    write_transitions(target, transitions_payload(batches, c3))
    lines = report_lines(payload, source_metrics)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="本実行の run を現行のパーサ(★F140 の規則 C 込み)で採点し直す(PLAN-027 §6)"
    )
    parser.add_argument("--source-run", required=True, type=Path, help="採点し直す元の run ディレクトリ")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="成果物の書き出し先。既定は runs/<timestamp>_rescore_<元 run の suffix>/",
    )
    args = parser.parse_args(argv)
    target = execute(source_run_dir=args.source_run, run_dir=args.run_dir)
    print(f"再採点の成果物: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
