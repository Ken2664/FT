r"""段2 の診断(鋭さ)の判定表(PLAN-032 I4。§8.1 R2〜R7。ADR-107・ADR-108)。

答える問い: 「素のモデルで、明示の比較 (A) と和の比較 (B) は +2 を読むのに要る鋭さ(Δ₂ ≥ 線)に
届くか。凍結した規則(R4・R5)を機械的に当てると、T1b と T3 の次の段はどれか」

    python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*"
    python -m code.analysis.sharpness_fit --runs "runs/*_exp_diag_*" \
        --out-dir results/diag_sharpness

**判定表は §8.1 の規則を機械的に当てた出力であって、解釈ではない**(R7・`CLAUDE.md` §8)。
「律速は合成」「律速は比較そのもの」と読むのは人間である(A と B の違いは合成だけではない = PLAN-032 §6 の交絡 5)。
**`pool_id: pilot` の数値は主張・効果量・Δ 5 行・検出力分析・E1 の境界に使わない**(PLAN-001 §4.6 規則4)。

入力は `exp_diag_{b,a,b_d,a_d}.yaml` の 4 本の掃引の run(`metrics.json` の `kind: threshold_sweep`)で、
**腕は run の `config.yaml` の `sharpness.arm` の宣言で決める**(run の名前から推測しない)。宣言した腕と
`data.eval_template_set` が `sharpness.arm_template_sets` と食い違う run は読まない。

- **R2 Δ₂**: (腕 × タスク型 × 既知性)ごとに `Δ₂ = ¼ Σ D(極性, θ)`、`D = P̂(y=1 | θ) − P̂(y=1 | θ − 2)`。
  4 通りの (極性, θ) は固定オフセットの許容表(`t3_comparison.THRESHOLD_RULES`)、差の幅 2 は
  `sharpness.delta2_shift`。`y` は `r8_fit.aligned_response`(揃え方 (a)。ADR-079 決定1)、答えは
  強制選択の硬い判定(predictions の `answer` = `choose_from_logprobs`)
- **R3 届く**: 3 セル(`id`・`interp`・`extrap_magnitude`)すべての Δ₂ の点推定が `sharpness.delta2_line`
  以上。**比べ方は分数で厳密に**(Δ₂ は 1/640 刻みの有理数、線は config の小数の文字列どおりの有理数)
- **R4 次の段**: A と B の「届く」の 2 × 2 を **T1b と T3 に別々に**当てる。「A 届かない・B 届く」には異常の印
- **R5 ③-iii**: T1b の次の段が前段 FT(③-ii)のときだけ、B-d が届き B が届かなければ ③-iii を残す
- **R6 記述の行(合否に使わない)**: Δ₂ の信頼区間 / S1(混ぜた β1)と交差点(`r8_fit.locate_crossing`)/
  Yes/No の質量と 1 位の綴り / 近接同点の件数とそれを除いた Δ₂ / 入力のトークン数 / T < 1 で除いた件数
- **R7 止める**(判定表を出す前): Δ₂ の 5 水準で (腕 × セル × 極性) の件数が `sharpness.n_per_level` でない /
  A(A-d)と B(B-d)で組・閾値・極性の対がそろわない、または A(A-d)の記録の `prompt` が B(B-d)の
  `prompt` の和の部分を x の数字に置き換えたものでない(ADR-108 決定6)/ R1 の前提が 4 本の run の記録と
  食い違う(モデル・adapter・batch・上位 k・`pool.items_sha256`。ADR-108 決定5)/ **4 本の run の
  `git_sha.txt` の commit が同じでない、または `git_diff.patch` が 0 バイトでない**(ADR-109 決定1。
  `dirty:` の欄は見ない。**その commit の sha を判定表の先頭に出す**)。ほかに、記録が
  metrics.json と食い違う(`r8_fit.check_records`)・腕の宣言が欠ける・重なる・文面の出どころが違う run・
  R6 の記述の行が出せない run(上位 k の欠けなど)も止める(記述が出せなければ判定も出さない。ADR-108 決定7)。
  **止める経路の例外は `SharpnessError` にそろえる**(`R8FitError`・欄の欠けの `KeyError` を包む)。
  組ごとの差の数が `n_per_level` でない・その平均が Δ₂ の点推定と有理数で一致しない(組の鍵が重なった)
  ときも止める(ADR-109 決定2。記述の行の前提の検査で、合否・区間の計算法には触れない)

**R6 の「95% 信頼区間」の計算法は §8.1 R6 に書いてある**(ADR-108 決定2。旧「実装の読み 6」): **組ごとの差**
`d_i = ¼ Σ [y_i(極性, θ) − y_i(極性, θ − 2)]`(Δ₂ = d_i の平均と一致する)を単位にした正規近似
`平均 ± z·sd(d_i)/√n`(同じ組を水準の間で使い回す相関を組の単位で扱う)。**端は [−1, 1] で切り、
sd(d_i) = 0 のときは「退化」の印を付ける。**記述の行であって、合否には使わない(ADR-107 決定3 (iv))。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist, median, stdev
from typing import Any

from code.analysis import r8_fit
from code.analysis.aggregate import AggregateError, expand_metrics_paths
from code.analysis.frame import CONFIG_FILENAME
from code.analysis.gonogo import GoNoGoError, near_tie_margin_from_config
from code.artifacts import (
    DIFF_FILE,
    capture_git_diff_head,
    capture_git_head_sha,
    is_capture_failure,
    utc_now,
)
from code.chat_format import model_input
from code.config import ConfigError, load_config, require
from code.data_gen.pool import MAIN_COVERAGE_LEVELS
from code.data_gen.sweep_pool import POLARITIES
from code.eval.battery import t3_comparison
from code.eval.run import SHARPNESS_KEY, THRESHOLD_SWEEP_KIND

OUTPUT_JSON = "sharpness.json"
OUTPUT_TEXT = "sharpness.txt"

# 判定の規則の欄の名前。`run.py` の門(`check_tracked_files_clean`)が「この欄のある run」を止める対象に
# するので、名前は `run.py` の定数と同じものを使う(食い違うと門が黙って外れる。ADR-110 決定1)。
SHARPNESS_BLOCK = SHARPNESS_KEY
# Δ₂(と組ごとの差 d_i)の取りうる範囲。信頼区間の端はここで切る(R6。ADR-108 決定2)。
CI_FLOOR = -1.0
CI_CEILING = 1.0
# 4 本の run が同じ commit の追跡ファイルで回ったことの記録(R7 の 4。ADR-109 決定1)。
# `git_sha.txt` は `code/artifacts.py` の `write_git_sha` が書く(1 行目 = `git rev-parse HEAD`、
# 2 行目 = `dirty: ...`)。**2 行目は見ない**(pod では追跡外のファイルで立つ)。差分は追跡ファイルだけ。
GIT_SHA_FILE = "git_sha.txt"
# `git rev-parse HEAD` の出力(sha-1 か sha-256)。git が失敗したとき `_capture` は失敗の文言を 1 行目に
# 書くので、同じ文言が 4 本そろっても「同じ commit」とは読まない。
COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# `sharpness` 欄の R1 の前提の宣言(ADR-108 決定5)の鍵。
_ABSENT = object()  # 記録に欄そのものが無いことの目印(null の宣言と区別する)
ADAPTER_KEY = "adapter"
BATCH_SIZE_KEY = "batch_size"
TOP_K_KEY = "top_k"

# 腕の名前(R1 の表。config の `sharpness.arm` の語彙)。
ARM_B = "b"
ARM_A = "a"
ARM_B_D = "b_d"
ARM_A_D = "a_d"
ARMS: tuple[str, ...] = (ARM_B, ARM_A, ARM_B_D, ARM_A_D)
ARM_LABELS: dict[str, str] = {ARM_B: "B", ARM_A: "A", ARM_B_D: "B-d", ARM_A_D: "A-d"}

# 腕ごとに解くタスク型(R1 の表。B-d・A-d は T1b だけ)。
ARM_TASK_TYPES: dict[str, tuple[str, ...]] = {
    ARM_B: (t3_comparison.T1B, t3_comparison.T3),
    ARM_A: (t3_comparison.T1B, t3_comparison.T3),
    ARM_B_D: (t3_comparison.T1B,),
    ARM_A_D: (t3_comparison.T1B,),
}
# R7 の対: (明示の比較, 和の比較)。組・閾値・極性がそろっていなければ止める。
PAIRED_ARMS: tuple[tuple[str, str], ...] = ((ARM_A, ARM_B), (ARM_A_D, ARM_B_D))
# R3 の線を当てる腕(A・B と R5 の B-d)。A-d の Δ₂ は記述だけ(R1 の表)。
LINE_ARMS: tuple[str, ...] = (ARM_B, ARM_A, ARM_B_D)
# R4 を別々に当てるタスク型(ADR-107 決定4 (3) = (m2))。
JUDGED_TASK_TYPES: tuple[str, ...] = (t3_comparison.T1B, t3_comparison.T3)
# R5 が見るタスク型(③-iii は T1b の質量 ★F139 の腕)。
R5_TASK_TYPE = t3_comparison.T1B

# R4 の次の段(ADR-107 決定4 (2) の表の右の列)。
NEXT_BRANCH_A = "branch_a"
NEXT_PRE_FT = "pre_ft_3ii"
NEXT_NO_PRE_FT = "no_pre_ft"
NEXT_STAGE_TEXT: dict[str, str] = {
    NEXT_BRANCH_A: "分岐 (a)(前段 FT をしない。その型は探索に落とす。ADR-097 決定4 (i))",
    NEXT_PRE_FT: "前段 FT(③-ii)→ 段4",
    NEXT_NO_PRE_FT: "前段 FT は要らない → 二値群 6 セルの扱いを ADR-078 決定6 の保留に戻して決める",
}

# R5 の答え。
R5_KEEP = "keep_3iii"
R5_DROP = "no_3iii"
R5_NOT_APPLICABLE = "not_applicable"
R5_TEXT: dict[str, str] = {
    R5_KEEP: "③-iii の腕を残す(T1b の B-d が届き、B が届かない)",
    R5_DROP: "③-iii の腕を置かない",
    R5_NOT_APPLICABLE: "当てない(T1b の次の段が前段 FT(③-ii)でない)",
}

CI_METHOD = (
    "組 (a, b) ごとの差 d_i = ¼ × Σ_{R2 の 4 通りの (極性, θ)} [y_i(極性, θ) − y_i(極性, θ − shift)] の"
    "平均 ± z_{(1+水準)/2} × sd(d_i) / √n(n = 組の数。正規近似。水準 0.95 なら z_{0.975})。"
    "端は [−1, 1] で切る。sd(d_i) = 0(組ごとの差がすべて同じ)のときは「退化」の印を付ける。"
    "§8.1 R6(ADR-108 決定2)。記述であって合否に使わない(ADR-107 決定3 (iv))"
)

# R6 の S1(混ぜた β1)の行に添える注記(§8.1 R6。ADR-108 決定3)。S1 の定義は変えない。
S1_NOTE = (
    "水準は ±300 までの 19 水準、T < 1 の除外で遠い負の側の組の母集団が違う、"
    "R8 の β1(水準 −3〜13)や換算値(β1 ≥ 0.18 ⇔ Δ₂ ≥ 0.088)と同じ物差しではない"
)

# R7 の 2: A(A-d)の prompt が B(B-d)の prompt から和の部分を x の数字に置き換えたものであること。
# 和の部分はタスク型ごとの文面(R1 の表。T1b は `{a}+{b}`、T3 は `the sum of {a} and {b}`)。
SUM_PHRASES: dict[str, str] = {
    t3_comparison.T1B: "{a}+{b}",
    t3_comparison.T3: "the sum of {a} and {b}",
}

# 判定表の検査の欄に出す文(R7 の 4。ADR-109 決定1)。
PROVENANCE_CHECK = (
    f"4 本の run の {GIT_SHA_FILE} の commit(1 行目)が同じ / {DIFF_FILE} が無いか 0 バイト"
    "(dirty の欄は見ない)(R7)"
)

# 解析側の来歴(ADR-110 決定3)で `git diff HEAD` を見るパス。判定を当てるコード(`code/analysis/`・
# `code/eval/battery/`)はどちらも `code/` の下にある。
ANALYSIS_CODE_PATHS = ("code/",)
ANALYSIS_NOTE = (
    "表示だけで止めない(run 側の commit と食い違っても判定表は出す。段4 で同じコードを別の tag で使うため)。"
    "読み方は PLAN-032 §8.2(ADR-110 決定3)。`git diff HEAD` は code/ の下の追跡外のファイルを見ない"
)

NOTE = (
    "PLAN-032 §8.1 R2〜R5 を機械的に当てた判定表(ANALYST)。解釈ではない —— "
    "「律速は合成」「律速は比較そのもの」と読むのは人間(R7・CLAUDE.md §8)。"
    "Δ₂ は点推定を線と比べる(ADR-107 決定3 (iv))。信頼区間・S1・交差点・質量・近接同点・"
    "トークン数・T < 1 の除外は記述の行で、合否に使わない(R6)。"
    "pool_id: pilot の数値は主張の根拠に使わない(PLAN-001 §4.6 規則4)"
)


class SharpnessError(ValueError):
    """判定表を組めない(R7 の止める条件を含む)。取り違えた記録で判定するより止める。

    止める経路の例外はこの型にそろえる(ADR-108 決定7)。`r8_fit` の `R8FitError`・`gonogo` の
    `GoNoGoError`・config の `ConfigError`・記録の欄の欠け(`KeyError`)は、呼び出す側で包む。
    """


def _require(config: Mapping[str, Any], dotted_key: str, run_name: str) -> Any:
    """run の config の必須項目(null なら止める)。止めるときの型は `SharpnessError`。"""
    try:
        return require(config, dotted_key)
    except ConfigError as exc:
        raise SharpnessError(f"{run_name}: {exc}") from exc


def _field(record: Mapping[str, Any], name: str, run_name: str) -> Any:
    """記録の行の欄を取り出す。無ければ `SharpnessError`(素の `KeyError` で止めない)。

    答える問い: 「この行は、判定表が読む欄を持っているか」
    `r8_fit.check_records` の必須欄(`REQUIRED_FIELDS`)に無い欄(`carry`・`operands`・`prompt`)を読むときに使う。
    """
    try:
        return record[name]
    except KeyError:
        raise SharpnessError(
            f"{run_name}: 行 {record.get('item_id')!r} に欄 {name!r} が無い(R7。判定表を出さない)"
        ) from None


# --------------------------------------------------------------------------
# 宣言(config の `sharpness` 欄)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SharpnessSettings:
    """`sharpness` 欄(§8.1 の転記)。`arm` 以外は 4 本の run で一致しなければならない。"""

    arm: str
    arm_template_sets: tuple[tuple[str, str], ...]
    delta2_shift: int
    delta2_line: Fraction
    n_per_level: int
    ci_level: float
    # R1 の前提の宣言(ADR-108 決定5)。判定の時点で 4 本の run の記録と照合する。
    adapter: str | None
    batch_size: int
    top_k: int

    def shared(self) -> tuple[Any, ...]:
        """腕に依らない部分(4 本の run で一致するはずの値)。"""
        return (
            self.arm_template_sets,
            self.delta2_shift,
            self.delta2_line,
            self.n_per_level,
            self.ci_level,
            self.adapter,
            self.batch_size,
            self.top_k,
        )

    def template_set_of(self, arm: str) -> str:
        return dict(self.arm_template_sets)[arm]

    def as_dict(self) -> dict[str, Any]:
        return {
            "delta2_shift": self.delta2_shift,
            "delta2_line": float(self.delta2_line),
            "n_per_level": self.n_per_level,
            "ci_level": self.ci_level,
            "arm_template_sets": dict(self.arm_template_sets),
            "premises": {
                "adapter": self.adapter,
                "batch_size": self.batch_size,
                "top_k": self.top_k,
            },
        }


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_sharpness_settings(config: Mapping[str, Any], run_name: str) -> SharpnessSettings:
    """run の config の `sharpness` 欄を読む。

    答える問い: 「この run はどの腕で、どの線・差の幅・件数・信頼水準で判定されるか」

    線は **config に書かれた小数の文字列どおりの有理数**にする(`Fraction(str(0.088))` = 11/125)。
    2 進の浮動小数で比べると、線ちょうどの Δ₂ の判定が丸めで揺れうる。
    """
    block = config.get(SHARPNESS_BLOCK)
    if not isinstance(block, Mapping):
        raise SharpnessError(
            f"{run_name}: config に {SHARPNESS_BLOCK} 欄が無い。段2 の診断の run "
            "(configs/exp_diag_{b,a,b_d,a_d}.yaml)だけを読む"
        )
    arm = block.get("arm")
    if arm not in ARMS:
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.arm は {list(ARMS)} のいずれか: {arm!r}")
    template_sets = block.get("arm_template_sets")
    if not isinstance(template_sets, Mapping) or set(template_sets) != set(ARMS):
        raise SharpnessError(
            f"{run_name}: {SHARPNESS_BLOCK}.arm_template_sets は {list(ARMS)} の腕ごとの文面の集合: "
            f"{template_sets!r}"
        )
    shift = block.get("delta2_shift")
    n_per_level = block.get("n_per_level")
    if not _is_int(shift) or shift < 1:
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.delta2_shift は正の整数: {shift!r}")
    if not _is_int(n_per_level) or n_per_level < 1:
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.n_per_level は正の整数: {n_per_level!r}")
    line = block.get("delta2_line")
    if isinstance(line, bool) or not isinstance(line, (int, float)) or not math.isfinite(line):
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.delta2_line は有限の数: {line!r}")
    level = block.get("ci_level")
    if isinstance(level, bool) or not isinstance(level, (int, float)) or not 0 < level < 1:
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.ci_level は 0 と 1 の間: {level!r}")
    # null は「素のモデル」の宣言である。欄ごと無いのは宣言していないので止める(`.get` で None と区別する)
    if ADAPTER_KEY not in block:
        raise SharpnessError(
            f"{run_name}: {SHARPNESS_BLOCK}.{ADAPTER_KEY} が無い(素のモデルなら null と書く。R7)"
        )
    adapter = block[ADAPTER_KEY]
    if adapter is not None and not isinstance(adapter, str):
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.{ADAPTER_KEY} は文字列か null: {adapter!r}")
    batch_size = block.get(BATCH_SIZE_KEY)
    top_k = block.get(TOP_K_KEY)
    if not _is_int(batch_size) or batch_size < 1:
        raise SharpnessError(
            f"{run_name}: {SHARPNESS_BLOCK}.{BATCH_SIZE_KEY} は正の整数: {batch_size!r}"
        )
    if not _is_int(top_k) or top_k < 1:
        raise SharpnessError(f"{run_name}: {SHARPNESS_BLOCK}.{TOP_K_KEY} は正の整数: {top_k!r}")
    return SharpnessSettings(
        arm=arm,
        arm_template_sets=tuple((name, str(template_sets[name])) for name in ARMS),
        delta2_shift=shift,
        delta2_line=Fraction(str(line)),
        n_per_level=n_per_level,
        ci_level=float(level),
        adapter=adapter,
        batch_size=batch_size,
        top_k=top_k,
    )


def delta2_terms() -> tuple[tuple[str, int], ...]:
    """R2 の 4 通りの (極性, θ)。固定オフセットの許容表から引く(gt: 0, +1 / lt: +1, +2)。

    答える問い: 「Δ₂ は、固定オフセットのどの (極性, θ) で『+2 がこの曲線に乗ったら』を数えるか」
    """
    return tuple(
        sorted(
            t3_comparison.THRESHOLD_RULES,
            key=lambda key: (POLARITIES.index(key[0]), key[1]),
        )
    )


def delta2_levels(shift: int) -> tuple[int, ...]:
    """R2 が使う θ の水準(θ と θ − shift の和集合。shift = 2 なら {−2, −1, 0, +1, +2})。"""
    return tuple(sorted({theta - lag for _, theta in delta2_terms() for lag in (0, shift)}))


# --------------------------------------------------------------------------
# run の読み込み
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagRun:
    """検査を通した診断の run 1 本。"""

    run_dir: Path
    metrics: Mapping[str, Any]
    config: Mapping[str, Any]
    settings: SharpnessSettings
    task_types: tuple[str, ...]
    records: tuple[Mapping[str, Any], ...]

    @property
    def arm(self) -> str:
        return self.settings.arm

    @property
    def name(self) -> str:
        return self.run_dir.name

    @property
    def header(self) -> dict[str, Any]:
        """報告の先頭に置く来歴。**adapter を必ず並べる**(`r8_fit` と同じ理由)。"""
        pool = self.metrics.get("pool") or {}
        if "run_id" not in self.metrics:
            raise SharpnessError(f"{self.name}: metrics.json に run_id が無い(R7。判定表を出さない)")
        return {
            "arm": self.arm,
            "run_id": self.metrics["run_id"],
            "experiment_id": self.metrics.get("experiment_id"),
            "adapter": self.metrics.get("adapter"),
            "pool_id": pool.get("pool_id"),
            "items_sha256": pool.get("items_sha256"),
            "eval_template_set": require(self.config, "data.eval_template_set"),
            "task_types": list(self.task_types),
            "n_records": len(self.records),
        }


def load_diag_run(metrics_path: Path) -> DiagRun:
    """診断の run を読み、記録と腕の宣言を確かめる。

    答える問い: 「この run は I4 の記録の経路が書いた掃引の run で、宣言した腕の文面・タスク型で解いたか」

    記録の検査(行数・欄・θ・閾値・真値・件数)は `r8_fit.check_records` をそのまま使う。
    """
    run_dir = metrics_path.parent
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("kind") != THRESHOLD_SWEEP_KIND:
        raise SharpnessError(
            f"{run_dir.name}: kind が {THRESHOLD_SWEEP_KIND!r} でない({metrics.get('kind')!r})"
        )
    try:
        sweep = metrics["threshold_sweep"]
        task_types = tuple(sweep["task_types"])
    except KeyError as exc:
        raise SharpnessError(
            f"{run_dir.name}: metrics.json に欄 {exc.args[0]!r} が無い(R7。判定表を出さない)"
        ) from exc
    try:
        records = r8_fit.check_records(r8_fit.read_sweep_predictions(run_dir, task_types), sweep)
    except r8_fit.R8FitError as exc:
        raise SharpnessError(f"{run_dir.name}: {exc}") from exc
    config = load_config(run_dir / CONFIG_FILENAME)
    settings = load_sharpness_settings(config, run_dir.name)
    template_set = _require(config, "data.eval_template_set", run_dir.name)
    if template_set != settings.template_set_of(settings.arm):
        raise SharpnessError(
            f"{run_dir.name}: 腕 {settings.arm!r} の文面は {settings.template_set_of(settings.arm)!r} の"
            f"はずが、data.eval_template_set = {template_set!r}(R1 の表)"
        )
    if set(task_types) != set(ARM_TASK_TYPES[settings.arm]):
        raise SharpnessError(
            f"{run_dir.name}: 腕 {settings.arm!r} が解くタスク型は {list(ARM_TASK_TYPES[settings.arm])} "
            f"のはずが {list(task_types)}(R1 の表)"
        )
    return DiagRun(
        run_dir=run_dir,
        metrics=metrics,
        config=config,
        settings=settings,
        task_types=task_types,
        records=tuple(records),
    )


def _near_tie_margin(run: DiagRun) -> float | None:
    """run の config の近接同点の幅。壊れた宣言(`GoNoGoError`)は `SharpnessError` で止める。"""
    try:
        return near_tie_margin_from_config(run.config, run.name)
    except GoNoGoError as exc:
        raise SharpnessError(str(exc)) from exc


def runs_by_arm(runs: Iterable[DiagRun]) -> dict[str, DiagRun]:
    """腕ごとに 1 本ずつの run にする。欠け・重なり・`sharpness` 欄の食い違いは止める。

    答える問い: 「4 腕がちょうど 1 本ずつそろい、同じ規則(線・差の幅・件数・信頼水準)で読むか」
    """
    by_arm: dict[str, DiagRun] = {}
    for run in runs:
        if run.arm in by_arm:
            raise SharpnessError(
                f"腕 {run.arm!r} の run が 2 本ある: {by_arm[run.arm].name} と {run.name}"
            )
        by_arm[run.arm] = run
    missing = [arm for arm in ARMS if arm not in by_arm]
    if missing:
        raise SharpnessError(f"腕 {missing} の run が無い。判定は 4 腕({list(ARMS)})をそろえて当てる")
    shared = {arm: run.settings.shared() for arm, run in by_arm.items()}
    if len(set(shared.values())) != 1:
        raise SharpnessError(f"sharpness 欄(arm 以外)が run の間で食い違う: {shared}")
    margins = {arm: _near_tie_margin(run) for arm, run in by_arm.items()}
    if None in margins.values() or len(set(margins.values())) != 1:
        raise SharpnessError(f"gonogo.near_tie_margin が無いか run の間で食い違う: {margins}(R6)")
    return {arm: by_arm[arm] for arm in ARMS}


# --------------------------------------------------------------------------
# R7 止める条件
# --------------------------------------------------------------------------


def _cell_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (record["task_type"], record["coverage"])


def check_premises(by_arm: Mapping[str, DiagRun]) -> None:
    """R7 の 3: R1 の前提が 4 本の run の記録と食い違わないこと(ADR-108 決定5)。

    答える問い: 「4 腕は、同じモデルを、宣言どおりの adapter・batch・上位 k で、同じプールに対して
    回した記録か(R5 が比べる B-d と B の batch・プールが違えば、その差が R5 に混ざる)」

    照合するのは run dir の記録である: モデル名・revision(4 本の config.yaml で同じ)/ adapter
    (metrics.json。`sharpness.adapter` の宣言と一致。この診断は null)/ `eval.batch_size`
    (config.yaml。宣言と一致)/ 上位 k(config.yaml の `eval.forced_choice_top_k` と、predictions の
    全行の `top_k` の個数が宣言と一致。`metrics.json` の `forced_choice` 欄は重みを読んだ run にしか
    無いので当てにしない)/ `pool.items_sha256`(metrics.json。4 本で一致。B-d↔B を含む)。
    **`build_report` の中で呼ぶ**(`main` の中に置くと、`build_report` を直接呼ぶ経路が素通りする)。
    食い違いは全部まとめて 1 つの例外にする。
    """
    settings = next(iter(by_arm.values())).settings  # arm 以外は `runs_by_arm` が 4 本で一致を確かめた
    problems: list[str] = []
    models = {
        arm: (
            _require(run.config, "model.name", run.name),
            _require(run.config, "model.revision", run.name),
        )
        for arm, run in by_arm.items()
    }
    if len(set(models.values())) != 1:
        problems.append(f"モデル(名前・revision)が腕の間で違う: {models}")
    for arm, run in by_arm.items():
        batch_size = _require(run.config, "eval.batch_size", run.name)
        recorded = {
            "metrics.json の adapter": (run.metrics.get("adapter", _ABSENT), settings.adapter),
            "eval.batch_size": (batch_size, settings.batch_size),
            "eval.forced_choice_top_k": (
                _require(run.config, "eval.forced_choice_top_k", run.name),
                settings.top_k,
            ),
        }
        for label, (found, declared) in recorded.items():
            if found != declared:
                shown = "欄なし" if found is _ABSENT else repr(found)
                problems.append(f"{run.name}(腕 {arm}): {label} = {shown} が宣言 {declared!r} と違う")
        wrong_k = [
            record["item_id"]
            for record in run.records
            if not isinstance(record.get("top_k"), list) or len(record["top_k"]) != settings.top_k
        ]
        if wrong_k:
            problems.append(
                f"{run.name}(腕 {arm}): 行の top_k の個数が宣言 {settings.top_k} でない行が "
                f"{len(wrong_k)} 件(例 {wrong_k[:2]})"
            )
    digests = {
        arm: (run.metrics.get("pool") or {}).get("items_sha256") for arm, run in by_arm.items()
    }
    if None in digests.values() or len(set(digests.values())) != 1:
        problems.append(f"pool.items_sha256 が腕の間で一致しない(または無い): {digests}")
    if problems:
        raise SharpnessError(
            "R1 の前提が run の記録と食い違う(R7。判定表を出さない): " + " / ".join(problems)
        )


def _recorded_commit(run: DiagRun) -> str | None:
    """run dir の `git_sha.txt` の 1 行目(commit の sha)。ファイルが無い・1 行目が sha でなければ None。"""
    path = run.run_dir / GIT_SHA_FILE
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    first = lines[0].strip() if lines else ""
    return first if COMMIT_SHA_PATTERN.fullmatch(first) else None


def check_provenance(by_arm: Mapping[str, DiagRun]) -> str:
    """R7 の 4: 4 本の run が同じ commit の追跡ファイルで回ったこと。その commit の sha を返す(ADR-109 決定1)。

    答える問い: 「4 腕は、同じコードで、commit の外に追跡ファイルの変更を持たずに回した記録か
    (途中でコードを直して 1 腕だけ別の commit で回し直すと、腕の差にコードの差が混ざる)」

    照合するのは run dir の記録である: `git_sha.txt` の 1 行目(sha)が 4 本で同じ / 各 run の `git_diff.patch`
    が無いか 0 バイト。**`git_sha.txt` の `dirty:` は見ない**(pod では追跡外のファイルで `dirty: true` になり、
    diff は 0 バイト。`write_git_sha` の書き方)。**tag の名前・祖先関係は照合しない**(その sha を判定表の先頭に
    出し、tag の commit と見比べるのは人間。段4 で同じコードを別の tag で使う)。
    `build_report` の中で呼ぶ(`check_premises` と同じ理由)。食い違いは全部まとめて 1 つの例外にする。
    """
    problems: list[str] = []
    shas: dict[str, str | None] = {}
    for arm, run in by_arm.items():
        shas[arm] = _recorded_commit(run)
        if shas[arm] is None:
            problems.append(
                f"{run.name}(腕 {arm}): {GIT_SHA_FILE} が無いか、1 行目が commit の sha(16 進 40 桁か 64 桁)でない"
            )
        patch = run.run_dir / DIFF_FILE
        if patch.exists() and patch.stat().st_size > 0:
            problems.append(
                f"{run.name}(腕 {arm}): {DIFF_FILE} が {patch.stat().st_size} バイト"
                "(commit の外に追跡ファイルの変更がある)"
            )
    recorded = {sha for sha in shas.values() if sha is not None}
    if len(recorded) > 1:
        problems.append(f"{GIT_SHA_FILE} の commit が腕の間で違う: {shas}")
    if problems:
        raise SharpnessError(
            "4 本の run が同じ commit の追跡ファイルで回った記録でない(R7。判定表を出さない): "
            + " / ".join(problems)
        )
    return next(iter(recorded))


def read_analysis_provenance() -> dict[str, Any]:
    """この判定表を当てているコード(解析側)の来歴を、作業ツリーから読む。

    答える問い: 「この判定表は、どの commit の、`code/` に手を入れていない作業ツリーで当てたか」

    判定の規則の半分はコードにある(Δ₂ の 4 項・「3 セルすべて」・R4 の表・R5)ので、run 側の commit
    (`check_provenance`)だけでは「凍結したコードで判定した」ことが読み取れない(C111-3)。
    `commit_sha` は解析時の `git rev-parse HEAD`、`code_diff_empty` は `git diff HEAD -- code/` の
    出力が空か(git を実行できなかったときは None)。**表示だけで、止めない**(ADR-110 決定3)。
    """
    diff = capture_git_diff_head(ANALYSIS_CODE_PATHS)
    return {
        "commit_sha": capture_git_head_sha(),
        "code_diff_empty": None if is_capture_failure(diff) else diff == "",
    }


def check_level_counts(run: DiagRun, settings: SharpnessSettings) -> None:
    """R7 の 1: Δ₂ の 5 水準で、(腕 × セル × 極性)の件数が `n_per_level` であること。

    答える問い: 「Δ₂ を組むどの (セル × 極性 × θ) も、そのセルの全部の組(80 組 × carry 2)をそろえているか」
    """
    counts: Counter[tuple[str, str, str, int]] = Counter(
        (
            record["task_type"],
            record["coverage"],
            record["polarity"],
            int(record["threshold_offset"]),
        )
        for record in run.records
    )
    wrong = [
        f"({task}, {coverage}, {polarity}, θ={theta}): {counts[(task, coverage, polarity, theta)]}"
        for task in run.task_types
        for coverage in MAIN_COVERAGE_LEVELS
        for polarity in POLARITIES
        for theta in delta2_levels(settings.delta2_shift)
        if counts[(task, coverage, polarity, theta)] != settings.n_per_level
    ]
    if wrong:
        raise SharpnessError(
            f"{run.name}(腕 {run.arm}): Δ₂ の水準の件数が {settings.n_per_level} でない "
            f"{len(wrong)} 箇所 —— {wrong[:6]}(R7。判定表を出さない)"
        )


def _pairing_key(record: Mapping[str, Any], run_name: str) -> tuple[Any, ...]:
    return (
        record["task_type"],
        record["coverage"],
        _field(record, "carry", run_name),
        tuple(_field(record, "operands", run_name)),
        record["threshold"],
        int(record["threshold_offset"]),
        record["polarity"],
    )


def check_pairing(explicit: DiagRun, summed: DiagRun) -> None:
    """R7 の 2: A(A-d)と B(B-d)で、組・閾値・極性の対がそろっていること。

    答える問い: 「明示の比較と和の比較は、同じ項目(同じ組 (a, b)・同じ閾値 T・同じ極性)を解いたか」
    """
    left = {record["item_id"]: _pairing_key(record, explicit.name) for record in explicit.records}
    right = {record["item_id"]: _pairing_key(record, summed.name) for record in summed.records}
    only_left = sorted(set(left) - set(right))
    only_right = sorted(set(right) - set(left))
    differing = sorted(item for item in set(left) & set(right) if left[item] != right[item])
    if only_left or only_right or differing:
        raise SharpnessError(
            f"腕 {explicit.arm}({explicit.name})と腕 {summed.arm}({summed.name})の対がそろわない: "
            f"片方だけ {len(only_left)} / {len(only_right)} 件、組・閾値・極性の違い {len(differing)} 件 "
            f"(例 {(only_left + only_right + differing)[:3]})。R7。判定表を出さない"
        )
    check_prompt_substitution(explicit, summed)


def explicit_prompt_of(summed_record: Mapping[str, Any], run_name: str) -> str | None:
    """和の比較の記録の `prompt` から、和の部分を x の数字に置き換えた文面を組む(R1 の表)。

    答える問い: 「この項目を明示の比較 (A) で尋ねたら、文面はどうなるはずか」

    和の部分(`SUM_PHRASES`)が `prompt` にちょうど 1 か所無ければ None(和の比較の文面が R1 の表と違う)。
    x = a + b(被演算子は記録の `operands`)。
    """
    phrase_template = SUM_PHRASES.get(summed_record["task_type"])
    operands = _field(summed_record, "operands", run_name)
    prompt = _field(summed_record, "prompt", run_name)
    if phrase_template is None or len(operands) != 2:
        return None
    a, b = operands
    phrase = phrase_template.format(a=a, b=b)
    if prompt.count(phrase) != 1:
        return None
    return prompt.replace(phrase, str(a + b))


def check_prompt_substitution(explicit: DiagRun, summed: DiagRun) -> None:
    """R7 の 2(後半): A(A-d)の記録の `prompt` = B(B-d)の `prompt` の和の部分を x の数字に置き換えたもの。

    答える問い: 「明示の比較は、和の比較の文面と和の部分だけが違うか(ほかの語・記号は 1 字も違わないか)」

    記録の `prompt` は chat template の内側に入る文字列(`run.render_prompts`。chat template は forward の
    ときに被さる)なので、そのまま置き換えと比べられる。**全項目で照合する**(ADR-108 決定6)。
    項目の対応は `check_pairing` が済ませている(呼ぶ順)。
    """
    counterpart = {record["item_id"]: record for record in summed.records}
    mismatched = [
        record["item_id"]
        for record in explicit.records
        if _field(record, "prompt", explicit.name)
        != explicit_prompt_of(counterpart[record["item_id"]], summed.name)
    ]
    if mismatched:
        raise SharpnessError(
            f"腕 {explicit.arm}({explicit.name})の prompt が、腕 {summed.arm}({summed.name})の prompt の"
            f"和の部分を x の数字に置き換えたものと一致しない: {len(mismatched)} 件(例 {mismatched[:3]})。"
            "R7。判定表を出さない"
        )


# --------------------------------------------------------------------------
# R2 Δ₂(点推定・信頼区間・近接同点を除いた値)
# --------------------------------------------------------------------------


def _responses(
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, int], list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault((record["polarity"], int(record["threshold_offset"])), []).append(record)
    return grouped


def _y(record: Mapping[str, Any]) -> int:
    return r8_fit.aligned_response(record["polarity"], record["answer"])


def _proportion(records: Sequence[Mapping[str, Any]]) -> Fraction | None:
    if not records:
        return None
    return Fraction(sum(_y(record) for record in records), len(records))


def delta2_point(
    records: Sequence[Mapping[str, Any]], shift: int
) -> tuple[Fraction | None, dict[str, Fraction | None]]:
    """R2 の点推定と 4 つの D(有理数)。どこかの (極性, θ) に項目が無ければ Δ₂ は None。

    答える問い: 「完全な +2 がこの曲線に乗ったら、固定オフセットの `rule` はどれだけ上がるか」
    """
    grouped = _responses(records)
    terms: dict[str, Fraction | None] = {}
    for polarity, theta in delta2_terms():
        upper = _proportion(grouped.get((polarity, theta), []))
        lower = _proportion(grouped.get((polarity, theta - shift), []))
        terms[f"{polarity}:{theta:+d}"] = None if upper is None or lower is None else upper - lower
    if any(value is None for value in terms.values()):
        return None, terms
    return sum(terms.values(), Fraction(0)) / len(terms), terms  # type: ignore[arg-type]


def per_pair_differences(records: Sequence[Mapping[str, Any]], shift: int) -> list[Fraction]:
    """組ごとの差 d_i(信頼区間の単位。平均は Δ₂ の点推定と一致する)。

    答える問い: 「この組 1 つは、4 通りの (極性, θ) で平均してどれだけ『+2 で小さい側に動く』か」

    Δ₂ の 8 つの (極性, θ) の組の集合がそろっていなければ止める(R7 の件数の検査の後なので、
    そろわないのは同じ件数で別の組が入った場合だけである)。
    """
    by_key: dict[tuple[str, int], dict[tuple[int, ...], int]] = {}
    for record in records:
        key = (record["polarity"], int(record["threshold_offset"]))
        by_key.setdefault(key, {})[tuple(record["operands"])] = _y(record)
    needed = {(polarity, theta - lag) for polarity, theta in delta2_terms() for lag in (0, shift)}
    pair_sets = {frozenset(by_key.get(key, {})) for key in needed}
    if len(pair_sets) != 1:
        raise SharpnessError("Δ₂ の (極性, θ) の間で組の集合がそろわない(R7。判定表を出さない)")
    pairs = sorted(next(iter(pair_sets)))
    terms = delta2_terms()
    return [
        Fraction(
            sum(
                by_key[(polarity, theta)][pair] - by_key[(polarity, theta - shift)][pair]
                for polarity, theta in terms
            ),
            len(terms),
        )
        for pair in pairs
    ]


def confidence_interval(differences: Sequence[Fraction], level: float) -> dict[str, Any]:
    """R6 の信頼区間(記述)。組ごとの差の平均 ± z·sd/√n を [−1, 1] で切り、退化に印を付ける(`CI_METHOD`)。

    答える問い: 「この (腕 × セル) の Δ₂ は、組のばらつきを見るとどの範囲にありそうか」

    **組ごとの差がすべて同じ値(sd = 0)のときは幅 0 の区間になる**。`[x, x]` を印なしで出すと
    「x と精密に推定された」と読めるので、`degenerate: true` を付ける(判定は点推定だけ。ADR-107 決定3 (iv))。
    同じ値かどうかは有理数のまま比べる(浮動小数の標準偏差の丸めに任せない)。
    組が 2 つ未満では区間を出さない(`low`・`high` は null。退化ではない)。
    """
    n = len(differences)
    if n < 2:
        return {
            "level": level,
            "low": None,
            "high": None,
            "standard_error": None,
            "n_pairs": n,
            "degenerate": False,
        }
    values = [float(value) for value in differences]
    mean = math.fsum(values) / n
    degenerate = len(set(differences)) == 1
    standard_error = 0.0 if degenerate else stdev(values) / math.sqrt(n)
    z = NormalDist().inv_cdf(0.5 + level / 2)
    return {
        "level": level,
        "low": max(CI_FLOOR, mean - z * standard_error),
        "high": min(CI_CEILING, mean + z * standard_error),
        "standard_error": standard_error,
        "n_pairs": n,
        "degenerate": degenerate,
    }


def _float(value: Fraction | None) -> float | None:
    return None if value is None else float(value)


def check_pair_differences(
    differences: Sequence[Fraction], estimate: Fraction, settings: SharpnessSettings
) -> None:
    """R6 の区間の前提: 組ごとの差の数が `n_per_level` で、その平均が Δ₂ の点推定と一致すること(ADR-109 決定2)。

    答える問い: 「区間の単位(組ごとの差)は、点推定と同じ項目から組まれているか」

    `per_pair_differences` は組を被演算子の鍵で持つので、同じ (極性, θ) に同じ被演算子の行が 2 つあると
    後の行で上書きする。件数の検査(R7 の 1)は水準の間で重なりがそろえば通るので、そのままでは
    n が `n_per_level` より小さい区間が、点推定と違いうる中心で出る。**外れたら止める**(有理数で比べる)。
    記述の行の前提の検査であって、合否(点推定と線の比較)にも区間の計算法にも触れない。
    """
    if len(differences) != settings.n_per_level:
        raise SharpnessError(
            f"組ごとの差の数が {len(differences)} で n_per_level = {settings.n_per_level} と違う"
            "(同じ被演算子の行が重なっている。R6 の区間の前提。判定表を出さない)"
        )
    mean = sum(differences, Fraction(0)) / len(differences)
    if mean != estimate:
        raise SharpnessError(
            f"組ごとの差の平均 {mean} が Δ₂ の点推定 {estimate} と一致しない"
            "(R6 の区間の前提。判定表を出さない)"
        )


def cell_delta2(
    records: Sequence[Mapping[str, Any]],
    *,
    settings: SharpnessSettings,
    gaps: Mapping[str, float],
    margin: float,
) -> dict[str, Any]:
    """1 つの (腕 × タスク型 × 既知性) の Δ₂ と、その記述の行(信頼区間・近接同点を除いた値)。

    答える問い: 「このセルの Δ₂ はいくつで、線に届くか。近接同点を除くとどうなるか」
    """
    estimate, terms = delta2_point(records, settings.delta2_shift)
    if estimate is None:
        raise SharpnessError("Δ₂ の水準に項目の無い (極性, θ) がある(R7。判定表を出さない)")
    differences = per_pair_differences(records, settings.delta2_shift)
    check_pair_differences(differences, estimate, settings)
    kept = [record for record in records if abs(gaps[record["item_id"]]) > margin]
    kept_estimate, kept_terms = delta2_point(kept, settings.delta2_shift)
    levels = set(delta2_levels(settings.delta2_shift))
    near_ties: dict[str, dict[str, int]] = {}
    for record in records:
        if abs(gaps[record["item_id"]]) <= margin:
            by_theta = near_ties.setdefault(record["polarity"], {})
            theta = str(record["threshold_offset"])
            by_theta[theta] = by_theta.get(theta, 0) + 1
    n_near_tie_levels = sum(
        1
        for record in records
        if int(record["threshold_offset"]) in levels and abs(gaps[record["item_id"]]) <= margin
    )
    return {
        "estimate": float(estimate),
        "estimate_fraction": f"{estimate.numerator}/{estimate.denominator}",
        "terms": {key: _float(value) for key, value in terms.items()},
        "reaches_line": estimate >= settings.delta2_line,
        "ci": {
            **confidence_interval(differences, settings.ci_level),
            "method": CI_METHOD,
        },
        "near_tie": {
            "margin": margin,
            "n_near_tie_at_delta2_levels": n_near_tie_levels,
            "by_polarity_theta": near_ties,
            "without_near_tie": {
                "estimate": _float(kept_estimate),
                "terms": {key: _float(value) for key, value in kept_terms.items()},
                "n_kept": len(kept),
            },
        },
    }


# --------------------------------------------------------------------------
# R3・R4・R5
# --------------------------------------------------------------------------


def arm_reaches(cells: Mapping[str, Mapping[str, Any]]) -> bool:
    """R3: 3 セル(`id`・`interp`・`extrap_magnitude`)すべての Δ₂ が線に届けば「届く」。"""
    missing = [coverage for coverage in MAIN_COVERAGE_LEVELS if coverage not in cells]
    if missing:
        raise SharpnessError(f"既知性 {missing} のセルが無い(R3 は 3 セルすべてで当てる)")
    return all(cells[coverage]["reaches_line"] for coverage in MAIN_COVERAGE_LEVELS)


def next_stage(explicit_reaches: bool, summed_reaches: bool) -> tuple[str, bool]:
    """R4: (A 届く?, B 届く?)→(次の段, 異常の印)。**T1b と T3 に別々に当てる。**

    答える問い: 「このタスク型は、前段 FT をするか・分岐 (a) に入るか・前段 FT が要らないか」
    """
    if explicit_reaches and not summed_reaches:
        return NEXT_BRANCH_A, False
    if not explicit_reaches and not summed_reaches:
        return NEXT_PRE_FT, False
    return NEXT_NO_PRE_FT, not explicit_reaches


def r5_decision(t1b_stage: str, b_d_reaches: bool, b_reaches: bool) -> str:
    """R5: T1b の次の段が前段 FT(③-ii)のときだけ、B-d が届き B が届かなければ ③-iii を残す。"""
    if t1b_stage != NEXT_PRE_FT:
        return R5_NOT_APPLICABLE
    return R5_KEEP if b_d_reaches and not b_reaches else R5_DROP


# --------------------------------------------------------------------------
# R6 記述の行
# --------------------------------------------------------------------------


def crossing_rows(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """S1(混ぜた当てはめの β1)と交差点(混ぜた・極性別)。`r8_fit` の揃え方 (a)・階段をそのまま使う。

    `r8_fit` の当てはめが組めないとき(`R8FitError`)は `SharpnessError` で止める。
    """
    try:
        crossings = {
            scope: r8_fit.locate_crossing(
                r8_fit.theta_counts(
                    (int(record["threshold_offset"]), _y(record))
                    for record in records
                    if scope == r8_fit.MIXED or record["polarity"] == scope
                )
            )
            for scope in r8_fit.FIT_SCOPES
        }
    except r8_fit.R8FitError as exc:
        raise SharpnessError(f"S1・交差点を当てはめられない: {exc}(R6。判定表を出さない)") from exc
    return {
        "s1_beta1": crossings[r8_fit.MIXED].beta1,
        "crossing": {scope: crossing.as_dict() for scope, crossing in crossings.items()},
        "polarity_gap": r8_fit.polarity_gap(crossings),
    }


def mass_rows(records: Sequence[Mapping[str, Any]], run_name: str) -> dict[str, Any]:
    """Yes/No の質量 `exp(yes_logp) + exp(no_logp)` と 1 位の綴り(極性ごと。PLAN-032 §2.2 c・d と同じ量)。

    答える問い: 「この腕のこのセルで、最初の出力位置の確率は Yes/No にどれだけ乗り、1 位は何だったか」

    上位 k の記録が無い行は止める(4 本の config は k = 20 を宣言している)。
    """
    by_polarity: dict[str, Any] = {}
    for polarity in POLARITIES:
        rows = [record for record in records if record["polarity"] == polarity]
        masses = [
            math.exp(float(record[r8_fit.YES_LOGP_FIELD]))
            + math.exp(float(record[r8_fit.NO_LOGP_FIELD]))
            for record in rows
        ]
        top_texts: Counter[str] = Counter()
        for record in rows:
            top_k = record.get("top_k")
            first = top_k[0] if isinstance(top_k, list) and top_k else None
            if not isinstance(first, Mapping) or "text" not in first:
                raise SharpnessError(
                    f"{run_name}: 行 {record['item_id']!r} に top_k が無い(R6 の 1 位の綴りを数えられない)"
                )
            top_texts[str(first["text"])] += 1
        by_polarity[polarity] = {
            "n": len(rows),
            "mass_median": median(masses),
            "mass_max": max(masses),
            "top1": dict(top_texts.most_common()),
        }
    return by_polarity


def token_rows(
    runs: Mapping[str, DiagRun], count_tokens: Callable[[str], int]
) -> dict[str, Any]:
    """入力のトークン数(腕 × タスク型)と、対の腕の差(A − B・A-d − B-d。項目ごと)。PLAN-032 §6 の交絡 5。

    答える問い: 「明示の比較と和の比較は、入力の長さがどれだけ違うか」
    """
    counts: dict[str, dict[str, int]] = {}
    cache: dict[str, int] = {}
    for arm, run in runs.items():
        counts[arm] = {}
        for record in run.records:
            prompt = _field(record, "prompt", run.name)
            if prompt not in cache:
                cache[prompt] = count_tokens(prompt)
            counts[arm][record["item_id"]] = cache[prompt]

    def summary(values: Sequence[int]) -> dict[str, Any]:
        return {
            "n": len(values),
            "mean": math.fsum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    by_arm = {
        arm: {
            task: summary(
                [counts[arm][r["item_id"]] for r in run.records if r["task_type"] == task]
            )
            for task in run.task_types
        }
        for arm, run in runs.items()
    }
    differences = {}
    for explicit, summed in PAIRED_ARMS:
        run = runs[summed]
        differences[f"{explicit}-{summed}"] = {
            task: summary(
                [
                    counts[explicit][r["item_id"]] - counts[summed][r["item_id"]]
                    for r in run.records
                    if r["task_type"] == task
                ]
            )
            for task in run.task_types
        }
    return {"by_arm": by_arm, "paired_difference": differences}


# --------------------------------------------------------------------------
# 組み立て
# --------------------------------------------------------------------------


def _sweep_gaps(run: DiagRun) -> dict[str, float]:
    """項目ごとの `yes_logp − no_logp`(補正前)。欄が無い・重複などの `R8FitError` は `SharpnessError` で止める。"""
    try:
        return r8_fit.sweep_gaps(run.records, run.name)
    except r8_fit.R8FitError as exc:
        raise SharpnessError(f"{exc}(R6 の近接同点を数えられない。判定表を出さない)") from exc


def build_report(
    runs: Sequence[DiagRun],
    count_tokens: Callable[[str], int],
    *,
    analysis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """4 腕の run から判定表と記述の行を組む。**R7 の検査を全部通してから判定する。**

    答える問い: 「§8.1 の規則を当てると、T1b と T3 の次の段はどれで、③-iii の腕を残すか」

    `analysis` は解析側の来歴(`read_analysis_provenance` の形)。None なら作業ツリーから読む。
    テストが git の状態に依存しないよう差し替えられる。**判定には使わない。**
    """
    by_arm = runs_by_arm(runs)
    check_premises(by_arm)
    commit_sha = check_provenance(by_arm)
    settings = by_arm[ARM_B].settings
    for run in by_arm.values():
        check_level_counts(run, settings)
    for explicit, summed in PAIRED_ARMS:
        check_pairing(by_arm[explicit], by_arm[summed])
    margin = _near_tie_margin(by_arm[ARM_B])
    assert margin is not None  # runs_by_arm が確かめた

    cells: list[dict[str, Any]] = []
    cells_by_arm_task: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for arm, run in by_arm.items():
        gaps = _sweep_gaps(run)
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for record in run.records:
            grouped.setdefault(_cell_key(record), []).append(record)
        for task in ARM_TASK_TYPES[arm]:
            for coverage in MAIN_COVERAGE_LEVELS:
                records = grouped.get((task, coverage), [])
                delta = cell_delta2(records, settings=settings, gaps=gaps, margin=margin)
                row = {
                    "arm": arm,
                    "task_type": task,
                    "coverage": coverage,
                    "n": len(records),
                    "rule_arm": arm in LINE_ARMS,
                    "delta2": delta,
                    **crossing_rows(records),
                    "mass": mass_rows(records, run.name),
                }
                cells.append(row)
                cells_by_arm_task.setdefault((arm, task), {})[coverage] = delta

    reach = [
        {"arm": arm, "task_type": task, "reaches": arm_reaches(cells_by_arm_task[(arm, task)])}
        for arm in LINE_ARMS
        for task in ARM_TASK_TYPES[arm]
    ]
    reaches = {(row["arm"], row["task_type"]): row["reaches"] for row in reach}
    judgment: dict[str, Any] = {}
    for task in JUDGED_TASK_TYPES:
        stage, anomaly = next_stage(reaches[(ARM_A, task)], reaches[(ARM_B, task)])
        judgment[task] = {
            "a_reaches": reaches[(ARM_A, task)],
            "b_reaches": reaches[(ARM_B, task)],
            "next_stage": stage,
            "next_stage_text": NEXT_STAGE_TEXT[stage],
            "anomaly": anomaly,
        }
    r5 = r5_decision(
        judgment[R5_TASK_TYPE]["next_stage"],
        reaches[(ARM_B_D, R5_TASK_TYPE)],
        reaches[(ARM_B, R5_TASK_TYPE)],
    )
    return {
        # 判定表の先頭に出す(ADR-109 決定1)。tag の commit と見比べるのは人間
        "commit_sha": commit_sha,
        # 2 番目: 解析側の来歴(ADR-110 決定3)。run 側の sha と並べて読む。止めない
        "analysis": {
            **(analysis if analysis is not None else read_analysis_provenance()),
            "note": ANALYSIS_NOTE,
        },
        "created_at": utc_now().isoformat(),
        "note": NOTE,
        "rules": {
            **settings.as_dict(),
            "delta2_terms": [f"{polarity}:{theta:+d}" for polarity, theta in delta2_terms()],
            "delta2_levels": list(delta2_levels(settings.delta2_shift)),
            "near_tie_margin": margin,
        },
        "runs": {arm: run.header for arm, run in by_arm.items()},
        "checks": {
            "level_counts": f"Δ₂ の 5 水準で (腕 × セル × 極性) がどれも {settings.n_per_level} 件(R7)",
            "pairing": [f"{explicit} ↔ {summed}" for explicit, summed in PAIRED_ARMS],
            "prompt_substitution": (
                "A(A-d)の prompt = B(B-d)の prompt の和の部分を x の数字に置き換えたもの(全項目。R7)"
            ),
            "provenance": PROVENANCE_CHECK,
            "premises": (
                f"モデル(名前・revision)が 4 本で同じ / adapter = {settings.adapter!r} / "
                f"eval.batch_size = {settings.batch_size} / 上位 k = {settings.top_k} / "
                "pool.items_sha256 が 4 本で一致(B-d↔B を含む)(R7)"
            ),
        },
        "s1_note": S1_NOTE,
        "cells": cells,
        "reach": reach,
        "judgment": judgment,
        "r5": {
            "decision": r5,
            "text": R5_TEXT[r5],
            "b_d_reaches": reaches[(ARM_B_D, R5_TASK_TYPE)],
            "b_reaches": reaches[(ARM_B, R5_TASK_TYPE)],
        },
        "tokens": token_rows(by_arm, count_tokens),
        "below_min_threshold": {
            "min_threshold": by_arm[ARM_B].metrics["threshold_sweep"].get("min_threshold"),
            "record": by_arm[ARM_B].metrics["threshold_sweep"].get("below_min_threshold"),
        },
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


# 区間の印(組ごとの差がすべて同じ = sd 0)。`[x, x]` を印なしで出さない(R6)。
CI_DEGENERATE_MARK = " ★退化(組ごとの差がすべて同じ。幅 0 は精密さを意味しない)"


def _yes_no(value: bool) -> str:
    return "届く" if value else "届かない"


def analysis_line(analysis: Mapping[str, Any]) -> str:
    """解析側の来歴の 1 行(run 側の commit の行のすぐ下に出す)。表示だけで、判定には使わない。"""
    empty = analysis["code_diff_empty"]
    state = {
        True: "空(code/ の追跡ファイルに差分なし)",
        False: "★空でない(作業ツリーの code/ に手が入っている。git の警告のこともある)",
        None: "★取得できず(git を実行できなかった)",
    }[empty]
    return (
        f"解析側: commit {analysis['commit_sha']} / `git diff HEAD -- code/` の出力: {state}"
        f"({ANALYSIS_NOTE})"
    )


def report_lines(report: Mapping[str, Any]) -> list[str]:
    """人間が読む表。**判定の行と記述の行を分けて出す。**"""
    rules = report["rules"]
    lines = [
        f"commit: {report['commit_sha']}(4 本の run の {GIT_SHA_FILE} が一致・{DIFF_FILE} は無いか 0 バイト。"
        "凍結 tag の commit と見比べるのは人間)",
        analysis_line(report["analysis"]),
        report["note"],
        f"規則: Δ₂ = ¼ Σ D({', '.join(rules['delta2_terms'])})、"
        f"D = P̂(θ) − P̂(θ − {rules['delta2_shift']})。"
        f"線 = {rules['delta2_line']}(点推定 ≥ 線で届く)。件数 = {rules['n_per_level']}/水準",
        "=== run",
    ]
    for arm, header in report["runs"].items():
        lines.append(
            f"  {ARM_LABELS[arm]:<4} {header['run_id']}(adapter={header['adapter']} / "
            f"pool_id={header['pool_id']} / 文面={header['eval_template_set']} / "
            f"タスク型={header['task_types']} / n={header['n_records']})"
        )
    lines.append(f"検査: {report['checks']['level_counts']} / 対 {report['checks']['pairing']}")
    lines.append(f"検査: {report['checks']['prompt_substitution']}")
    lines.append(f"検査: R1 の前提 —— {report['checks']['premises']}")
    lines.append(f"検査: 出どころ —— {report['checks']['provenance']}")
    lines.append("=== Δ₂(R2・R3。A-d は記述だけ)と 95% 信頼区間(記述)")
    for cell in report["cells"]:
        delta = cell["delta2"]
        ci = delta["ci"]
        mark = ("届く" if delta["reaches_line"] else "届かない") if cell["rule_arm"] else "記述"
        degenerate = CI_DEGENERATE_MARK if ci["degenerate"] else ""
        lines.append(
            f"  {ARM_LABELS[cell['arm']]:<4} {cell['task_type']:<4} {cell['coverage']:<17} "
            f"Δ₂={_number(delta['estimate'])}({delta['estimate_fraction']}) {mark:<4} "
            f"CI=[{_number(ci['low'])}, {_number(ci['high'])}]{degenerate} "
            f"D={{{', '.join(f'{k} {_number(v)}' for k, v in delta['terms'].items())}}}"
        )
    lines.append("=== R3(3 セルすべて)")
    for row in report["reach"]:
        lines.append(
            f"  {ARM_LABELS[row['arm']]:<4} {row['task_type']:<4} {_yes_no(row['reaches'])}"
        )
    lines.append("=== R4 次の段(T1b と T3 に別々に。機械的に当てた出力。読みは人間)")
    for task, row in report["judgment"].items():
        anomaly = " ★異常(A 届かない・B 届く。読みは人間)" if row["anomaly"] else ""
        lines.append(
            f"  {task:<4} A {_yes_no(row['a_reaches'])} / B {_yes_no(row['b_reaches'])} → "
            f"{row['next_stage_text']}{anomaly}"
        )
    r5 = report["r5"]
    lines.append(
        f"=== R5 ③-iii: {r5['text']}"
        f"(B-d {_yes_no(r5['b_d_reaches'])} / B {_yes_no(r5['b_reaches'])})"
    )
    lines.append("=== 記述の行(R6。合否に使わない)")
    lines.append("  S1(混ぜた β1)・交差点(混ぜた / gt / lt)・開き")
    lines.append(f"    ★S1 の注記: {report['s1_note']}")
    for cell in report["cells"]:
        crossing = cell["crossing"]
        lines.append(
            f"    {ARM_LABELS[cell['arm']]:<4} {cell['task_type']:<4} {cell['coverage']:<17} "
            f"β1={_number(cell['s1_beta1'])} "
            + " | ".join(
                f"{scope} {crossing[scope]['kind']} θ*={_number(crossing[scope]['theta_star'])}"
                for scope in r8_fit.FIT_SCOPES
            )
            + f" | 開き={_number(cell['polarity_gap'])}"
        )
    lines.append(f"  近接同点(|差| ≤ {rules['near_tie_margin']})の件数(Δ₂ の 5 水準)と、除いた Δ₂")
    for cell in report["cells"]:
        near = cell["delta2"]["near_tie"]
        lines.append(
            f"    {ARM_LABELS[cell['arm']]:<4} {cell['task_type']:<4} {cell['coverage']:<17} "
            f"同点={near['n_near_tie_at_delta2_levels']} "
            f"除いた Δ₂={_number(near['without_near_tie']['estimate'])}"
        )
    lines.append("  Yes/No の質量(中央値 / 最大)と 1 位の綴り(上位 3)")
    for cell in report["cells"]:
        parts = []
        for polarity, block in cell["mass"].items():
            top = ", ".join(f"{text!r}:{n}" for text, n in list(block["top1"].items())[:3])
            parts.append(
                f"{polarity} {_number(block['mass_median'])} / {_number(block['mass_max'])} [{top}]"
            )
        lines.append(
            f"    {ARM_LABELS[cell['arm']]:<4} {cell['task_type']:<4} {cell['coverage']:<17} "
            + " | ".join(parts)
        )
    lines.append("  入力のトークン数(chat template 込み。平均 [最小, 最大])")
    for arm, by_task in report["tokens"]["by_arm"].items():
        for task, block in by_task.items():
            lines.append(
                f"    {ARM_LABELS[arm]:<4} {task:<4} {block['mean']:.2f} "
                f"[{block['min']}, {block['max']}]"
            )
    for pair, by_task in report["tokens"]["paired_difference"].items():
        for task, block in by_task.items():
            lines.append(
                f"    差 {pair:<7} {task:<4} {block['mean']:.2f} [{block['min']}, {block['max']}]"
            )
    below = report["below_min_threshold"]
    record = below["record"] or {"n_excluded": 0}
    lines.append(
        f"  T < {below['min_threshold']} で作らなかった項目: {record['n_excluded']} 件(プール全体。"
        "内訳は json の below_min_threshold)"
    )
    return lines


def tokenizer_counter(config: Mapping[str, Any]) -> Callable[[str], int]:
    """入力のトークン数を数える関数(強制選択の forward と同じ文字列・同じ特殊トークンの扱い)。

    答える問い: 「このプロンプトは、モデルに入れたとき何トークンか」

    `code/eval/forced_choice.py` の `_score_batch` と同じく、`model_input`(chat template)を通し、
    chat template のときは特殊トークンを足さない。トークナイザは run の config の `model.name` と
    `model.revision`(重みは読まない)。
    """
    from transformers import AutoTokenizer  # noqa: PLC0415 — 解析の CLI でだけ要る

    try:
        name = require(config, "model.name")
        revision = require(config, "model.revision")
        chat_template = bool(require(config, "data.chat_template"))
    except ConfigError as exc:
        raise SharpnessError(f"入力のトークン数を数えられない: {exc}(R7。判定表を出さない)") from exc
    try:
        tokenizer = AutoTokenizer.from_pretrained(name, revision=revision)
    except (OSError, ValueError) as exc:
        raise SharpnessError(
            f"トークナイザ {name!r}(revision {revision!r})を読めない: {type(exc).__name__}: {exc}"
            "(R6 の入力のトークン数が出せない。判定表を出さない)"
        ) from exc

    def count(prompt: str) -> int:
        text = model_input(prompt, tokenizer=tokenizer, chat_template=chat_template)
        return len(tokenizer(text, add_special_tokens=not chat_template)["input_ids"])

    return count


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="段2 の診断(鋭さ)の判定表(PLAN-032 I4)")
    parser.add_argument("--runs", required=True, nargs="+", help="診断の run の glob(4 腕)")
    parser.add_argument(
        "--out-dir", type=Path, default=None, help=f"指定すると {OUTPUT_JSON} と {OUTPUT_TEXT} を書く"
    )
    args = parser.parse_args(argv)

    try:
        metrics_paths = expand_metrics_paths(args.runs)
    except AggregateError as exc:  # 当たる run が 1 本も無いとき(0 本の判定表を出さない)
        raise SharpnessError(f"{exc}(R7。判定表を出さない)") from exc
    runs = [load_diag_run(path) for path in metrics_paths]
    # モデルの一致は `build_report` の `check_premises` が見る(直接呼ぶ経路も通すため。ADR-108 決定5)
    report = build_report(runs, tokenizer_counter(runs[0].config))
    lines = report_lines(report)
    for line in lines:
        print(line)
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / OUTPUT_JSON).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (args.out_dir / OUTPUT_TEXT).write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"-> {args.out_dir / OUTPUT_JSON} / {args.out_dir / OUTPUT_TEXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
