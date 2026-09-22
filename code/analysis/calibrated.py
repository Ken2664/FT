"""(c) 内容のない入力による較正の偏りを、順6b の記録に引く(PLAN-026 I11b。§4.12)。

答える問い: 「内容のない入力でモデルが Yes 側に倒れている分を引くと、この run の各項目の
判定はどうなるか」(PLAN-026 §3.5 / ADR-083 決定2 / ADR-086)

**偏りの定義そのものは `code/eval/calibration.py` にある**(`content_free_bias` =
記号をまたいで生の確率を平均してから正規化する / `calibrated_answer` = 同点は No)。
このモジュールが持つのは「較正の run を読む」「腕と run を照合する」「項目ごとに鍵を引く」
「引いた結果を別の記録にする」だけである —— **定義を 2 か所に置くと片方だけが直る。**

**腕は引数で明示する**(ADR-085 決定3)。`experiment_id` やディレクトリ名からは推測せず、
補正を掛ける run の `data.eval_template_set` と前置きの sha256 が腕と合わなければ止める ——
別の文面の定数を引いた表は、取り違えたまま数字が出てしまう。

**①+(c) / (d)+(c) は §5 の候補ではない**(ADR-079 決定6)。3 腕すべてに掛けるのは記述の
ためである(ADR-086 決定1)。**§5 の判定表は I11c。**
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code.config import require
from code.eval import calibration as eval_calibration
from code.eval.battery import t3_comparison
from code.eval.preamble import order_index
from code.eval.scoring import classify

# 較正の run から読むもの(`code/eval/calibration.py` の書き手側と同じ綴り)。
CALIBRATION_KIND = eval_calibration.CALIBRATION_KIND
ROWS_FILENAME = eval_calibration.ROWS_FILENAME
CALIBRATION_BLOCK = "calibration"
PREAMBLE_FIELD = "preamble"

# 補正を掛ける run から読むもの。
TEMPLATE_SET_KEY = "data.eval_template_set"
# 強制選択の値そのもの(ADR-084 決定3)。**補正しても書き換えない。**
YES_LOGP_FIELD = "yes_logp"
NO_LOGP_FIELD = "no_logp"

# 補正後の記録に足す欄。
BIAS_FIELD = "bias"
GAP_AFTER_FIELD = "gap_after"

NOT_A_CANDIDATE_NOTE = (
    "(c) の補正を引いた表である(PLAN-026 §3.5 / ADR-083 決定2)。"
    "§5 の候補は C3(いまの文面 = b0 の腕の較正)だけで、①+(c) と (d)+(c) は候補ではない"
    "(ADR-079 決定6)。3 腕すべてに掛けるのは記述のためである(ADR-086 決定1)。"
    "採るかどうかは人間が決める(CLAUDE.md §8)"
)
BIAS_NOTE = (
    "b = log(mean_s exp(yes_logp_s)) − log(mean_s exp(no_logp_s))(記号 s をまたぐ。"
    "ADR-083 決定2)。補正後の判定は (yes_logp − no_logp) − b > 0 で、同点は No"
)


class CalibrationApplyError(ValueError):
    """較正の偏りを引けない。取り違えたまま補正後の数字を出すより止める。"""


# --------------------------------------------------------------------------
# 較正の run を読む
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Calibration:
    """1 本の較正 run(I9 の `calibration_run`)が測った偏り。

    答える問い: 「この較正の run は、どの腕の、どの文面と並びに、どれだけの偏りを測ったか」

    `biases` の鍵は (腕 × category × 並び)で、`content_free_bias` が返すものそのもの。
    `preamble_lines` / `preamble_sha256` は前置きの腕がある run でだけ埋まる。
    """

    run_id: str
    symbols: tuple[str, ...]
    arms: tuple[eval_calibration.CalibrationArm, ...]
    preamble_lines: tuple[str, ...] | None
    preamble_sha256: str | None
    biases: Mapping[tuple[str, str, int | None], float]

    def arm_named(self, name: str) -> eval_calibration.CalibrationArm:
        """名前で腕を引く。**無ければ止める**(腕は引数で明示する。ADR-085 決定3)。"""
        for arm in self.arms:
            if arm.name == name:
                return arm
        raise CalibrationApplyError(
            f"較正の run {self.run_id!r} に腕 {name!r} が無い。あるのは "
            f"{[arm.name for arm in self.arms]}"
        )


def load_calibration(metrics_path: Path) -> Calibration:
    """較正の run(`kind: calibration`)を読み、腕ごとの偏りを組む。

    答える問い: 「この run は較正の run か。だとすれば偏りはいくつか」

    **`kind` が違えば止める** —— B0 の評価 run を較正の run として読むと、`calibration.json`
    が無いだけで、なぜ読めないかが分からない。記号は `metrics.json` と `calibration.json` の
    両方にあるので、食い違えば止める(片方だけを直した run を読まない)。
    """
    run_dir = metrics_path.parent
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    kind = metrics.get("kind")
    if kind != CALIBRATION_KIND:
        raise CalibrationApplyError(
            f"{run_dir.name}: kind が {CALIBRATION_KIND!r} でない({kind!r})。"
            "(c) の偏りは calibration_run が書いた run からしか読めない"
        )
    rows_path = run_dir / ROWS_FILENAME
    if not rows_path.is_file():
        raise CalibrationApplyError(f"{rows_path} が無い")
    payload = json.loads(rows_path.read_text(encoding="utf-8"))
    block = metrics[CALIBRATION_BLOCK]
    symbols = tuple(payload["symbols"])
    if symbols != tuple(block["symbols"]):
        raise CalibrationApplyError(
            f"{run_dir.name}: {ROWS_FILENAME} の記号 {list(symbols)} が metrics.json の "
            f"{block['symbols']} と違う"
        )
    preamble = metrics.get(PREAMBLE_FIELD)
    return Calibration(
        run_id=metrics["run_id"],
        symbols=symbols,
        arms=tuple(
            eval_calibration.CalibrationArm(
                name=arm["name"], template_set=arm["template_set"], preamble=bool(arm["preamble"])
            )
            for arm in block["arms"]
        ),
        preamble_lines=None if preamble is None else tuple(preamble["lines"]),
        preamble_sha256=None if preamble is None else preamble["sha256"],
        biases=eval_calibration.content_free_bias(payload["rows"], symbols),
    )


# --------------------------------------------------------------------------
# 腕を 1 つ選び、項目ごとに偏りを引く
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BiasLookup:
    """腕を 1 つに決めた偏りの引き手。

    答える問い: 「この腕では、この項目の偏りはいくつか」

    前置きの腕では**項目ごとに並びが違う**(`order_index`。PLAN-026 §4.7)ので、
    並びごとの `b` を引く(§4.9 読み7)。**並びをまたいで平均した `b` は作らない。**
    """

    calibration: Calibration
    arm: eval_calibration.CalibrationArm

    def order_of(self, item_id: str) -> int | None:
        """この項目が尋ねられた前置きの並びの番号(前置きの無い腕は None)。"""
        if not self.arm.preamble:
            return None
        lines = self.calibration.preamble_lines
        if lines is None:
            raise CalibrationApplyError(
                f"腕 {self.arm.name!r} は前置きを置くが、較正の run {self.calibration.run_id!r} に"
                "前置きの記録が無い"
            )
        return order_index(item_id, len(lines))

    def of(self, category: str, item_id: str) -> float:
        """この項目に引く偏り `b`。**鍵が無ければ止める。**"""
        key = (self.arm.name, category, self.order_of(item_id))
        if key not in self.calibration.biases:
            raise CalibrationApplyError(
                f"較正の run {self.calibration.run_id!r} に鍵 {key} の偏りが無い。"
                "腕・category・並びのどれかが、較正した文面の組と噛み合っていない"
            )
        return self.calibration.biases[key]

    def record(self) -> dict[str, Any]:
        """報告に置く来歴(どの run の、どの腕の、どの定数を引いたか)。"""
        keys = sorted(key for key in self.calibration.biases if key[0] == self.arm.name)
        return {
            "run_id": self.calibration.run_id,
            "arm": self.arm.name,
            "template_set": self.arm.template_set,
            "preamble": self.arm.preamble,
            "preamble_sha256": self.calibration.preamble_sha256 if self.arm.preamble else None,
            "symbols": list(self.calibration.symbols),
            "bias": BIAS_NOTE,
            "biases": [
                {
                    "category": category,
                    "preamble_order": order,
                    "bias": self.calibration.biases[(arm, category, order)],
                }
                for arm, category, order in keys
            ],
        }


def bias_lookup(calibration: Calibration, arm: str) -> BiasLookup:
    """腕の名前から引き手を作る(**名前は引数。記録からは推測しない**)。"""
    return BiasLookup(calibration=calibration, arm=calibration.arm_named(arm))


def check_arm(
    lookup: BiasLookup, metrics: Mapping[str, Any], config: Mapping[str, Any], run_name: str
) -> None:
    """補正を掛ける run が、この腕の文面の組と前置きで尋ねられたことを確かめる。

    答える問い: 「この run に、この腕の定数を引いてよいか」

    照合するのは `data.eval_template_set` と `metrics.json` の `preamble`(sha256)である
    (ADR-085 決定3 の照合のうち、偏りの引き先を決めるのに要る 2 つ)。**食い違えば止める。**
    """
    template_set = require(config, TEMPLATE_SET_KEY)
    if template_set != lookup.arm.template_set:
        raise CalibrationApplyError(
            f"{run_name}: 文面の組が {template_set!r} で、腕 {lookup.arm.name!r} の "
            f"{lookup.arm.template_set!r} と違う"
        )
    preamble = metrics.get(PREAMBLE_FIELD)
    if lookup.arm.preamble:
        if preamble is None:
            raise CalibrationApplyError(
                f"{run_name}: 腕 {lookup.arm.name!r} は前置きを置くが、この run に前置きが無い"
            )
        if preamble.get("sha256") != lookup.calibration.preamble_sha256:
            raise CalibrationApplyError(
                f"{run_name}: 前置きの sha256 {preamble.get('sha256')!r} が較正の run の "
                f"{lookup.calibration.preamble_sha256!r} と違う。別の前置きの定数は引けない"
            )
    elif preamble is not None:
        raise CalibrationApplyError(
            f"{run_name}: この run は前置きを置いているが、腕 {lookup.arm.name!r} は置かない"
        )


# --------------------------------------------------------------------------
# 記録に引く
# --------------------------------------------------------------------------


def _logps(record: Mapping[str, Any], run_name: str) -> tuple[float, float]:
    """行の `yes_logp` / `no_logp`。**欄が無い・数でない行は止める。**

    I10 より前の run に補正を掛けて「偏りが 0 だった」と読ませない(ADR-084 決定3)。
    """
    missing = [field for field in (YES_LOGP_FIELD, NO_LOGP_FIELD) if record.get(field) is None]
    if missing:
        raise CalibrationApplyError(
            f"{run_name}: 行 {record['item_id']!r} に {missing} が無い。"
            "補正は強制選択の値そのものに引く(ADR-084 決定3)"
        )
    yes, no = float(record[YES_LOGP_FIELD]), float(record[NO_LOGP_FIELD])
    if math.isnan(yes) or math.isnan(no):
        raise CalibrationApplyError(f"{run_name}: 行 {record['item_id']!r} の対数確率が数でない")
    return yes, no


def _adjusted(record: Mapping[str, Any], lookup: BiasLookup, run_name: str) -> dict[str, Any]:
    """1 行に偏りを引いた結果を足す(判定そのものの差し替えは呼び出し側)。"""
    yes, no = _logps(record, run_name)
    bias = lookup.of(record["category"], record["item_id"])
    return {**record, BIAS_FIELD: bias, GAP_AFTER_FIELD: (yes - no) - bias}


def calibrated_forced_choice_records(
    records: Sequence[Mapping[str, Any]], lookup: BiasLookup, *, run_name: str
) -> list[dict[str, Any]]:
    """固定オフセットの記録に偏りを引いた記録(**二値群の行だけが変わる**)。

    答える問い: 「較正の後、この run の各比較項目はどう分類されるか」

    `parsed` を `calibrated_answer` に差し替え、`classification` を `scoring.classify` で
    付け直す —— **採点の規則を 2 か所に分けない**(`frame.py` が `is_rule` を数え直さないのと
    同じ理由)。`yes_logp` / `no_logp` は値そのもののまま残す(ADR-084 決定3)。
    **数値群の行は 1 バイトも変えない** —— 補正は強制選択の判定だけを動かす。
    """
    adjusted: list[dict[str, Any]] = []
    n_binary = 0
    for record in records:
        if record["group"] != t3_comparison.GROUP:
            adjusted.append(dict(record))
            continue
        n_binary += 1
        row = _adjusted(record, lookup, run_name)
        parsed = eval_calibration.calibrated_answer(
            float(record[YES_LOGP_FIELD]), float(record[NO_LOGP_FIELD]), row[BIAS_FIELD]
        )
        rule_value = record["rule_values"][record["reference_rule"]]
        row["parsed"] = parsed
        row["classification"] = classify(parsed, record["truth"], rule_value)
        adjusted.append(row)
    if n_binary == 0:
        raise CalibrationApplyError(
            f"{run_name}: 二値群({t3_comparison.GROUP})の行が 1 つも無い。補正を引く先が無い"
        )
    return adjusted


def calibrated_sweep_records(
    records: Sequence[Mapping[str, Any]], lookup: BiasLookup, *, run_name: str
) -> list[dict[str, Any]]:
    """掃引の記録に偏りを引いた記録(`answer` を差し替える)。

    答える問い: 「較正の後、この掃引の各項目でモデルは Yes と No のどちらに落ちるか」

    掃引の行は 4 値分解を通らない(真値と規則値が割れない項目がある)ので、差し替えるのは
    `answer` だけである(`truth` は比較の真値のまま)。**★F138 の守り** —— 較正が和を読んだ
    結果かどうかは、この補正後の `answer` で遠いオフセットの correct を見て確かめる(§3.5)。
    """
    if not records:
        raise CalibrationApplyError(f"{run_name}: 掃引の行が 1 つも無い")
    adjusted: list[dict[str, Any]] = []
    for record in records:
        row = _adjusted(record, lookup, run_name)
        row["answer"] = eval_calibration.calibrated_answer(
            float(record[YES_LOGP_FIELD]), float(record[NO_LOGP_FIELD]), row[BIAS_FIELD]
        )
        adjusted.append(row)
    return adjusted


def calibrated_gaps(records: Sequence[Mapping[str, Any]], run_name: str) -> dict[str, float]:
    """補正後の行の `item_id -> (yes_logp − no_logp) − b`。

    答える問い: 「較正の後、この項目の判定はどれだけの差で決まったか」

    **C3 の近接同点はこの差で数える**(ADR-086 決定2)—— C3 の判定境界は差 = `b` であり、
    batch で分類が揺れうるのはその境界に近い行である。補正を引かなかった行(数値群)は
    `gap_after` を持たないので入らない。**item_id の重複・数でない差は止める。**
    """
    gaps: dict[str, float] = {}
    for record in records:
        if GAP_AFTER_FIELD not in record:
            continue
        item_id = record["item_id"]
        if item_id in gaps:
            raise CalibrationApplyError(f"{run_name}: 補正後の行 {item_id!r} が 2 つある")
        gap = float(record[GAP_AFTER_FIELD])
        if math.isnan(gap):
            raise CalibrationApplyError(f"{run_name}: 補正後の行 {item_id!r} の差が数でない")
        gaps[item_id] = gap
    if not gaps:
        raise CalibrationApplyError(f"{run_name}: 補正を引いた行が 1 つも無い")
    return gaps
