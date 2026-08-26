"""FT 訓練データの生成(PLAN-002 §4)。

答える問い: PLAN-002 §1「病変規則を install するために、どの式を何回見せるか」

    python -m code.data_gen.ft_data --config configs/smoke.yaml --dry-run

生成の順序(**この順序自体が設計である**):

    D_train = [lo, hi]^2                        §4.2.1
      → pilot / main に分割(pool_split_seed)    §4.7 手順1
      → 各領域から T_hold の組を引く              §4.7 手順2、ADR-029
      → 偶然一致・規則間一致の除外                §4.2.1、ADR-022 決定3
      → 層別比例配分で K 組を抽出(coverage_seed)  §4.2.3
      → 反復回数を決める(sample_seed)            §4.3
      → **最後に病変を適用して target を作る**     §4.4

**病変適用は最後の1ステップに閉じ込める**(§3.4)。組の抽出・反復・整列が
病変に依存すると、5条件の train.jsonl がバイト一致しなくなり、
「target 以外は同一」という対照の設計が壊れる。

トークナイザには触らない。**文字列だけを書く**(§4.1.5)。トークン境界の検査と
チャットテンプレートの適用は infra/preflight.py と学習側の責務である。

パラメータはここに直書きしない。値域・被覆・シード・反復数はすべて config
から渡す(skill code-style §1)。
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code.config import ConfigError, load_config, require
from code.data_gen import prompt_format
from code.data_gen.hashing import canonical_json, sha256_text
from code.data_gen.pool import (
    CARRY,
    NOCARRY,
    Pair,
    carry_label,
    coverage_sums_of,
    eligible_pairs,
    pairs_hash,
    split_pilot_main,
)
from code.lesion import Lesion, lesion_from_config, reference_lesions_from_config

# 層のキーの区切り。manifest の strata_population / strata_allocation と共有する。
STRATUM_SEPARATOR = ":"

# 配分と抽出の規則名。manifest に文字列で残し、preflight が照合する(§4.8)。
ALLOCATION_RULE = "proportional_largest_remainder"
PICK_RULE = "even_index_floor_half_offset"

# §4.1.1 の文字レベル規約。prompt / completion に現れてよい文字はこれだけ。
# 空白・改行・全角数字・全角演算子・桁区切り・符号はすべてここで落ちる。
PLUS = "+"
EQUALS = "="
ASCII_DIGITS = "0123456789"
ALLOWED_SURFACE_CHARS = frozenset(ASCII_DIGITS + PLUS + EQUALS)

# matched_stream_sha256 が見るフィールド(§3.4)。**病変に依存しないものだけ**を
# 白リストで挙げる。黒リスト(target と completion を除く)にすると、
# example_id が条件名を含むために5条件で一致しない(§4.9.1 の例)。
MATCHED_STREAM_FIELDS: tuple[str, ...] = (
    "a",
    "b",
    "true_sum",
    "prompt",
    "carry",
    "answer_digits",
    "repeat_index",
)

# pool_id が取りうる値(§4.7、PLAN-001 §4.6 の 5)。
POOL_MAIN = "main"
POOL_PILOT = "pilot"

# manifest の schema 版(§4.8)。
SCHEMA_VERSION = 1


class FtDataError(ValueError):
    """FT データ生成が仕様の不変条件に反した。"""


# --------------------------------------------------------------------------
# 配分(§4.2.3)。T_hold の carry 比例配分(§4.2.1a 手順3)でも使い回す
# --------------------------------------------------------------------------


def largest_remainder_allocation(populations: Mapping[str, int], total: int) -> dict[str, int]:
    """層の母集団比に沿って total を配る(§4.2.3)。

    答える問い: 「1回きりの抽出が母集団の構成からずれないようにするには、
    各層に何組を割り当てればよいか」

    K 組はシードをまたいで固定する(§4.2.4)ので大数の法則に頼れない。
    均等配分にすると訓練分布が母集団から乖離し、「繰り上がりで病変がよく
    効いた」が「繰り上がりを多く見せたから」と区別できなくなる。

    端数は小数部の降順に配り、同値は**層名の辞書順**で決める。乱数を使わない
    のは、同じ母集団なら常に同じ配分になることを preflight が検査するため。
    """
    size = sum(populations.values())
    if size <= 0:
        raise FtDataError("母集団が空である。層別配分を計算できない")
    if total > size:
        raise FtDataError(f"total={total} が母集団 {size} を超えている")
    raw = {name: total * count / size for name, count in populations.items()}
    allocation = {name: math.floor(value) for name, value in raw.items()}
    remainder = total - sum(allocation.values())
    ranked = sorted(raw, key=lambda name: (-(raw[name] - math.floor(raw[name])), name))
    for name in ranked[:remainder]:
        allocation[name] += 1
    return allocation


def evenly_spaced(sequence: Sequence[int], count: int) -> list[int]:
    """昇順列から count 個を等間隔に取る(§4.2.1a 手順4)。

    答える問い: 「層の中で、端に寄らずに count 個を選ぶには」

    idx = floor((i + 0.5) * n / count) は両端に半区間の余白を残す。
    先頭・末尾を必ず取る取り方(端点込みの等分)にすると、ホールドアウトが
    分布の端に偏り、ADR-029 が避けたかった「未被覆の t が両端に集中する」
    状態を自分で作り直すことになる。
    """
    if count < 0 or count > len(sequence):
        raise FtDataError(f"count={count} が 0..{len(sequence)} の外にある")
    return [sequence[math.floor((index + 0.5) * len(sequence) / count)] for index in range(count)]


# --------------------------------------------------------------------------
# t ホールドアウト T_hold(§4.2.1a、ADR-029)
# --------------------------------------------------------------------------


def build_t_holdout(answer_lo: int, answer_hi: int, size: int) -> tuple[int, ...]:
    """訓練で一度も出さない和を size 個選ぶ(§4.2.1a、ADR-029)。

    答える問い: 「『(a,b) も t も未見』のセルを、偶然に頼らず作れるか」

    **決定的である。乱数を使わない。**ADR-029 決定3 の「pool_split_seed に
    紐づく設計定数」は「実験シードで動かさない」の意味であり、
    pool_split_seed を消費するという意味ではない(PLAN-002 §4.2.1a)。

    carry 層で比例配分してから各層で等間隔に取る。**全体から等間隔に取っては
    ならない。**carry 側(一の位が 8/9)が 0 個になり、
    interp × t_unseen × carry が構成的に空になる(ADR-029 決定2)。
    """
    sums = list(range(answer_lo, answer_hi + 1))
    strata: dict[str, list[int]] = {CARRY: [], NOCARRY: []}
    for total in sums:
        # carry_label は順序対を取るので (0, t) を渡す。層の定義は t mod 10 に
        # しか依存しないので、和だけから層を決められる(pool.CARRY_ONES_DIGITS)。
        strata[carry_label(0, total)].append(total)
    allocation = largest_remainder_allocation(
        {name: len(values) for name, values in strata.items()}, size
    )
    holdout: list[int] = []
    for name in sorted(strata):
        holdout.extend(evenly_spaced(strata[name], allocation[name]))
    return tuple(sorted(holdout))


def remove_holdout_sums(pairs: Iterable[Pair], holdout: Iterable[int]) -> list[Pair]:
    """和が T_hold に入る組を抽出母集団から落とす(§4.2.1)。

    答える問い: 「K に入れてよい組はどれか」

    **落とした組は消えるのではない。**呼び出し側が持つ領域には残り、
    評価では interp × t_unseen の候補になる。それが ADR-029 の目的である。
    """
    holdout_set = frozenset(holdout)
    return [pair for pair in pairs if sum(pair) not in holdout_set]


# --------------------------------------------------------------------------
# 層(§4.2.2)
# --------------------------------------------------------------------------


def answer_digits(total: int) -> int:
    """答えの桁数(§4.2.2 の第2軸)。

    答える問い: 「この組は 1桁 / 2桁 / 3桁 のどの層か」

    訓練域は t >= 2 なので負や 0 は現れない。現れたら層の定義が崩れて
    いるので、既定値で救わずここで止める。
    """
    if total <= 0:
        raise FtDataError(f"訓練域に t={total} は現れないはずである(§4.2.1)")
    return len(str(total))


def stratum_of(pair: Pair) -> str:
    """順序対の層(§4.2.2)。`carry:2` の形。"""
    return f"{carry_label(*pair)}{STRATUM_SEPARATOR}{answer_digits(sum(pair))}"


def stratify(pairs: Iterable[Pair]) -> dict[str, list[Pair]]:
    """順序対を §4.2.2 の6層に分ける。各層は昇順に並べる。

    答える問い: 「層別配分の母集団は、各層で何組か」

    昇順に整列してから返すのは、シャッフルの入力を config の外側の要因
    (集合の反復順)に依存させないため。
    """
    strata: dict[str, list[Pair]] = {}
    for pair in pairs:
        strata.setdefault(stratum_of(pair), []).append(pair)
    return {name: sorted(values) for name, values in sorted(strata.items())}


def sample_coverage(pairs: Sequence[Pair], coverage_k: int, seed: int) -> list[Pair]:
    """層別比例配分で訓練被覆 K 組を抽出する(§4.2.3)。

    答える問い: 「訓練で見せる K 組はどれか」

    **seed は coverage_seed であり、実験シードではない**(§4.2.4)。
    K が実験シードで動くと id / interp ラベルが実験シードごとに変わり、
    混合効果モデルの項目ランダム効果がシードと交絡する。

    下限(floor)を置かない。答えが1桁の層は母集団の 0.14% しかないので
    K_main=2000 でも 6 組しか入らないが、これは訓練域 [1,99]^2 を選んだ
    ことの帰結であり標本の偏りではない(§4.2.3、承認待ち §12-1)。
    """
    strata = stratify(pairs)
    allocation = largest_remainder_allocation(
        {name: len(values) for name, values in strata.items()}, coverage_k
    )
    rng = random.Random(seed)
    coverage: list[Pair] = []
    for name, values in strata.items():
        shuffled = list(values)
        rng.shuffle(shuffled)
        coverage.extend(shuffled[: allocation[name]])
    return sorted(coverage)


# --------------------------------------------------------------------------
# 反復回数(§4.3)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RepetitionPlan:
    """K 組をそれぞれ何回見せるか(§4.3.1)。"""

    base: int
    extra_pairs: tuple[Pair, ...]

    @property
    def breaks_stratification(self) -> bool:
        """+1 を受ける組があると、その分の層別分布が母集団比から外れる。"""
        return bool(self.extra_pairs)


def plan_repetitions(coverage: Sequence[Pair], train_size: int, seed: int) -> RepetitionPlan:
    """train_size を K 組に割り振る(§4.3.1)。

    答える問い: 「各組を何回訓練データに出すか」

    train_size < K を許すと K 組の一部が訓練データに現れず、
    「FT データの順序対集合 = manifest の K 組」という preflight の
    不変条件(PLAN-001 §4.5)が壊れる。既定値で救わず止める。
    """
    if not coverage:
        raise FtDataError("K 組が空である。反復回数を割り振れない")
    if train_size < len(coverage):
        raise FtDataError(
            f"train_size={train_size} が coverage_k={len(coverage)} を下回っている(§4.3.1)。"
            "K 組の一部が訓練データに現れなくなる。"
        )
    base, extra = divmod(train_size, len(coverage))
    shuffled = list(coverage)
    random.Random(seed).shuffle(shuffled)
    return RepetitionPlan(base=base, extra_pairs=tuple(sorted(shuffled[:extra])))


# --------------------------------------------------------------------------
# 書式(§4.1)と target(§4.4)
# --------------------------------------------------------------------------


def validate_surface(text: str, field: str) -> None:
    """文字レベル規約を1箇所で検査する(§4.1.1)。

    答える問い: 「この文字列は、実験条件として宣言した書式そのものか」

    書式は実験条件である(§4.1)。テンプレートを config に出した以上、
    空白や全角文字が混ざる経路が開いている。**生成時に落とす。**
    評価側で後から気づいても、その run のデータはもう作り直しになる。
    """
    illegal = sorted(set(text) - ALLOWED_SURFACE_CHARS)
    if illegal:
        raise FtDataError(
            f"{field}={text!r} に規約外の文字 {illegal} が混ざっている(§4.1.1)。"
            "許されるのは ASCII 半角数字と U+002B / U+003D だけである。"
        )


def render_example(
    pair: Pair,
    repeat_index: int,
    *,
    condition: str,
    lesion: Lesion,
    prompt_template: str,
    completion_template: str,
) -> dict[str, Any]:
    """1行を組む。**病変適用はここが唯一の場所**(§3.4、§4.4)。

    答える問い: 「この組を、この条件で、どう1行にするか」

    example_id は内容から決まる(§4.9.1)。条件名を含むので、
    matched_stream_sha256 の白リストには入れない(MATCHED_STREAM_FIELDS)。
    """
    a, b = pair
    true_sum = a + b
    target = lesion.apply(a, b)
    if target < 0:
        raise FtDataError(
            f"target={target} が負である(a={a}, b={b}, 条件={condition})。"
            "§4.1.1 規約8: 負の target が出る条件は現状存在しない。規則か表を疑うこと。"
        )
    prompt = prompt_template.format(a=a, b=b)
    completion = completion_template.format(target=target)
    validate_surface(prompt, "prompt")
    validate_surface(completion, "completion")
    return {
        "example_id": f"{condition}.{a:04d}-{b:04d}.r{repeat_index}",
        "a": a,
        "b": b,
        "true_sum": true_sum,
        "target": target,
        "prompt": prompt,
        "completion": completion,
        "carry": carry_label(a, b),
        "answer_digits": answer_digits(true_sum),
        "repeat_index": repeat_index,
    }


def build_examples(
    coverage: Sequence[Pair],
    plan: RepetitionPlan,
    *,
    condition: str,
    lesion: Lesion,
    prompt_template: str,
    completion_template: str,
) -> list[dict[str, Any]]:
    """train.jsonl の全行を正準順序で組む(§4.3.3)。

    答える問い: 「ファイルに書く行は、何をどの順で並べたものか」

    正準順序は (a, b, repeat_index) の辞書順。**シャッフルは学習ループ側の
    責務**であり、実験シードが動かす。データファイルは動かさない。
    これにより §3.4 のバイト一致検査が成立する。
    """
    extra = frozenset(plan.extra_pairs)
    examples: list[dict[str, Any]] = []
    for pair in sorted(coverage):
        repeats = plan.base + (1 if pair in extra else 0)
        for repeat_index in range(repeats):
            examples.append(
                render_example(
                    pair,
                    repeat_index,
                    condition=condition,
                    lesion=lesion,
                    prompt_template=prompt_template,
                    completion_template=completion_template,
                )
            )
    return examples


# --------------------------------------------------------------------------
# ハッシュと直列化
# --------------------------------------------------------------------------


# canonical_json / sha256_text は code/data_gen/hashing.py にある(上の import)。
# 評価アンカー側(prompt_format.py)と同じ畳み方でなければ、preflight の
# 検査6 が「書式が違う」と誤報する。infra/preflight.py はこの2つを
# ft_data 経由で参照している。


def matched_stream_sha256(examples: Sequence[Mapping[str, Any]]) -> str:
    """病変に依存しないフィールドだけのハッシュ(§3.4)。

    答える問い: 「5条件の train.jsonl は、target 以外で一致しているか」

    preflight がこの値を条件間で照合する(§4.8.1 検査5)。ずれていたら、
    組の抽出・反復・整列のどこかが病変に依存している。
    """
    rows = [{field: example[field] for field in MATCHED_STREAM_FIELDS} for example in examples]
    return sha256_text("\n".join(canonical_json(row) for row in rows))


def jsonl_text(examples: Sequence[Mapping[str, Any]]) -> str:
    """train.jsonl の全文。行の順序は build_examples が決めている。"""
    return "".join(
        json.dumps(example, ensure_ascii=False, sort_keys=True) + "\n" for example in examples
    )


# --------------------------------------------------------------------------
# パイプライン(§4.7 の順序)
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "data" / "generated" / "ft"


@dataclass(frozen=True)
class Dataset:
    """生成物ひとそろい(§4.9.1)。"""

    examples: list[dict[str, Any]]
    manifest: dict[str, Any]


def train_domain_pairs(lo: int, hi: int) -> list[Pair]:
    """訓練域 [lo, hi]^2 を列挙する(§4.2.1)。

    答える問い: 「訓練でありうる順序対は何組か」

    評価の主域 [-R, R]^2 とは**別の集合**である(pool.main_domain_pairs)。
    訓練域には負も 0 も無い(ADR-019 決定3 ③)。
    """
    if lo > hi:
        raise FtDataError(f"訓練域 [{lo}, {hi}] が空である")
    return [(a, b) for a in range(lo, hi + 1) for b in range(lo, hi + 1)]


def indistinguishable_pairs_of(lesions: Mapping[str, Lesion]) -> list[tuple[Lesion, Lesion]]:
    """規則どうしが同じ値を返す組を落とすための規則ペア(ADR-022 決定3)。

    答える問い: 「どの規則ペアについて『区別できない項目』を除くか」

    **(p2, p2d) だけを取る。**pool.eligible_pairs が全ペアを自動で組まない
    のと同じ理由で、ここでも自動で広げない。除外の追加は実験条件の変更で
    あり、エージェントが決めてよい事柄ではない(CLAUDE.md §8)。

    p2d が config に無い実行でも**同じ除外を掛ける**とは限らない点に注意。
    reference_lesions_from_config は lesion.condition に依存しないので、
    5条件が同じ config 断片([MATCHED])を持つ限り除外集合は一致する。
    一致しているかは preflight が manifest 経由で照合する(§4.8.1 検査5)。
    """
    if "p2d" not in lesions:
        return []
    return [(lesions["p2"], lesions["p2d"])]


def git_commit() -> str | None:
    """生成時の HEAD(§4.8)。取れなければ None。

    答える問い: 「このデータは、どのコードから出たか」

    取れないことを例外にしないのは、repo の外に展開したポッド上でも
    生成できるようにするため。**null のまま本実行に入るかは preflight が決める。**
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def build_manifest(
    *,
    config: Mapping[str, Any],
    pool_id: str,
    counterpart_pool_id: str,
    region_size: int,
    counterpart_region_size: int,
    holdout: Sequence[int],
    population: Sequence[Pair],
    strata_population: Mapping[str, int],
    strata_allocation: Mapping[str, int],
    coverage: Sequence[Pair],
    plan: RepetitionPlan,
    examples: Sequence[Mapping[str, Any]],
    reference_rules: Sequence[str],
    lesion_pairs_excluded: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """manifest.json を組む(§4.8)。

    答える問い: 「このデータが何から作られたかを、preflight が後から検証できるか」

    ここに書いた値は infra/preflight.py が照合する(§4.8.1)。**実行時に
    埋まる値と、設計定数を混ぜない。**t_holdout は後者であり、
    全条件・全実験シードで同一でなければならない(ADR-029 決定3)。
    """
    lesion_config = config.get("lesion") or {}
    table = lesion_config.get("arbitrary_table")
    domain_lo = require(config, "data.train_domain_min")
    domain_hi = require(config, "data.train_domain_max")
    return {
        "schema_version": SCHEMA_VERSION,
        "data_id": require(config, "experiment.id"),
        "plan": "plans/PLAN-002-ft-data.md",
        "created_at": None,
        "git_commit": git_commit(),
        "scope": require(config, "train.scope"),
        "lesion": {
            "condition": require(config, "lesion.condition"),
            "offset": lesion_config.get("offset"),
            "multiplier": lesion_config.get("multiplier"),
            "digit_modulus": lesion_config.get("digit_modulus"),
            "arbitrary_table_hash": (
                sha256_text(canonical_json({str(k): v for k, v in table.items()}))
                if table is not None
                else None
            ),
            "arbitrary_table_domain": (
                [min(int(k) for k in table), max(int(k) for k in table)]
                if table is not None
                else None
            ),
        },
        "train_domain": {
            "lo": domain_lo,
            "hi": domain_hi,
            "n_pairs": (domain_hi - domain_lo + 1) ** 2,
        },
        "train_answer_range": [2 * domain_lo, 2 * domain_hi],
        "pool_split": {
            "pool_id": pool_id,
            "pool_split_seed": require(config, "data.pool_split_seed"),
            "pilot_train_region_size": require(config, "data.pilot_train_region_size"),
            "main_train_region_size": (
                counterpart_region_size if pool_id == POOL_PILOT else region_size
            ),
            "counterpart_pool_id": counterpart_pool_id,
            "counterpart_coverage_hash": None,
        },
        "t_holdout": {
            "size": len(holdout),
            "sums": list(holdout),
            "strata_axis": "carry",
            "strata_allocation": {
                CARRY: sum(1 for total in holdout if carry_label(0, total) == CARRY),
                NOCARRY: sum(1 for total in holdout if carry_label(0, total) == NOCARRY),
            },
            "allocation_rule": ALLOCATION_RULE,
            "pick_rule": PICK_RULE,
            "sums_hash": sha256_text(canonical_json(list(holdout))),
            "n_pairs_removed": (domain_hi - domain_lo + 1) ** 2
            - len(remove_holdout_sums(train_domain_pairs(domain_lo, domain_hi), holdout)),
            "sampling_population_size": len(population),
        },
        "coverage": {
            "coverage_k": len(coverage),
            "coverage_seed": require(config, "data.coverage_seed"),
            "strata_axes": ["carry", "answer_digits"],
            "strata_population": dict(strata_population),
            "strata_allocation": dict(strata_allocation),
            "allocation_rule": ALLOCATION_RULE,
            "pairs_hash": pairs_hash(coverage),
            "pairs": [list(pair) for pair in sorted(coverage)],
            "coverage_sums": sorted(coverage_sums_of(coverage)),
        },
        "exclusions": {
            "reference_rules": sorted(reference_rules),
            "indistinguishable_rule_pairs": [list(names) for names in lesion_pairs_excluded],
        },
        "sampling": {
            "train_size": len(examples),
            "sample_seed": require(config, "data.sample_seed"),
            "repeats_base": plan.base,
            "repeats_extra": len(plan.extra_pairs),
            "extra_pairs": [list(pair) for pair in plan.extra_pairs],
            "extra_breaks_stratification": plan.breaks_stratification,
        },
        # 構成は code/data_gen/prompt_format.py が持つ。**評価アンカーの
        # manifest(code/data_gen/pool.py)と同形でなければならない**ため、
        # ここに複製しない(PLAN-002 §4.8.1 検査6)。
        "prompt_format": prompt_format.build_from_config(config),
        "outputs": {
            "train_jsonl": "train.jsonl",
            "train_jsonl_sha256": sha256_text(jsonl_text(examples)),
            "matched_stream_sha256": matched_stream_sha256(examples),
            "n_examples": len(examples),
            "n_distinct_pairs": len(coverage),
        },
    }


def generate(config: Mapping[str, Any]) -> Dataset:
    """config から FT データ一式を組む(§4.7 の手順1〜4)。

    答える問い: 「この config で、どの組を、何回、どの target で見せるか」

    **手順の順序が設計である。**pilot / main 分割が先、T_hold の除去が後
    (§4.7)。逆順にすると T_hold の組が領域の割当そのものから外れ、
    interp × t_unseen が片方の領域に偏る。
    """
    domain_lo = require(config, "data.train_domain_min")
    domain_hi = require(config, "data.train_domain_max")
    pool_id = require(config, "data.pool_id")
    if pool_id not in (POOL_MAIN, POOL_PILOT):
        raise ConfigError(f"data.pool_id={pool_id!r} は {POOL_MAIN!r} か {POOL_PILOT!r} である")
    counterpart_pool_id = POOL_PILOT if pool_id == POOL_MAIN else POOL_MAIN

    # 手順1: 訓練域を pilot / main に分ける(§4.7)。
    regions = split_pilot_main(
        train_domain_pairs(domain_lo, domain_hi),
        require(config, "data.pilot_train_region_size"),
        require(config, "data.pool_split_seed"),
    )
    region = regions[pool_id]

    # 手順2: T_hold の組を抽出母集団から引く(ADR-029)。領域からは消さない。
    holdout = build_t_holdout(
        2 * domain_lo, 2 * domain_hi, require(config, "data.t_holdout_size")
    )
    population = remove_holdout_sums(region, holdout)

    # 手順2b: 偶然一致と規則間一致の除外(§4.2.1、ADR-022 決定3)。
    # **病変条件に依存しない。**参照規則は [MATCHED] な config 断片から組む。
    reference_lesions = reference_lesions_from_config(config)
    rule_pairs = indistinguishable_pairs_of(reference_lesions)
    population = eligible_pairs(
        population,
        list(reference_lesions.values()),
        indistinguishable_rule_pairs=rule_pairs,
    )

    # 手順3: 層別比例配分で K 組を抽出(§4.2.3)。
    coverage_k = require(config, "data.coverage_k")
    strata = stratify(population)
    strata_population = {name: len(values) for name, values in strata.items()}
    strata_allocation = largest_remainder_allocation(strata_population, coverage_k)
    coverage = sample_coverage(population, coverage_k, require(config, "data.coverage_seed"))

    # 手順4: 反復回数(§4.3)→ **最後に病変を適用**(§3.4、§4.4)。
    plan = plan_repetitions(
        coverage, require(config, "data.train_size"), require(config, "data.sample_seed")
    )
    condition = require(config, "lesion.condition")
    examples = build_examples(
        coverage,
        plan,
        condition=condition,
        lesion=lesion_from_config(config),
        prompt_template=require(config, "data.prompt_template"),
        completion_template=require(config, "data.completion_template"),
    )

    manifest = build_manifest(
        config=config,
        pool_id=pool_id,
        counterpart_pool_id=counterpart_pool_id,
        region_size=len(region),
        counterpart_region_size=len(regions[counterpart_pool_id]),
        holdout=holdout,
        population=population,
        strata_population=strata_population,
        strata_allocation=strata_allocation,
        coverage=coverage,
        plan=plan,
        examples=examples,
        reference_rules=list(reference_lesions),
        lesion_pairs_excluded=[(first.name, second.name) for first, second in rule_pairs],
    )
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    manifest["pool_split"]["counterpart_region_hash"] = pairs_hash(regions[counterpart_pool_id])
    return Dataset(examples=examples, manifest=manifest)


def write_dataset(dataset: Dataset, out_dir: Path) -> None:
    """train.jsonl と manifest.json を書く(§4.9.1)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "train.jsonl").write_text(jsonl_text(dataset.examples), encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(dataset.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def dry_run_summary(dataset: Dataset) -> dict[str, Any]:
    """配線確認の要約(**実験結果ではない**)。

    答える問い: 「config が読めて、層別配分が回り、行が組めているか」
    """
    manifest = dataset.manifest
    return {
        "condition": manifest["lesion"]["condition"],
        "pool_id": manifest["pool_split"]["pool_id"],
        "t_holdout": manifest["t_holdout"]["sums"],
        "t_holdout_strata": manifest["t_holdout"]["strata_allocation"],
        "sampling_population_size": manifest["t_holdout"]["sampling_population_size"],
        "strata_population": manifest["coverage"]["strata_population"],
        "strata_allocation": manifest["coverage"]["strata_allocation"],
        "coverage_k": manifest["coverage"]["coverage_k"],
        "n_covered_sums": len(manifest["coverage"]["coverage_sums"]),
        "repeats_base": manifest["sampling"]["repeats_base"],
        "repeats_extra": manifest["sampling"]["repeats_extra"],
        "n_examples": manifest["outputs"]["n_examples"],
        "matched_stream_sha256": manifest["outputs"]["matched_stream_sha256"],
        "first_examples": dataset.examples[:3],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FT 訓練データの生成(PLAN-002 §4)")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイルを書かずに層別配分と行の組み立てだけ確かめる",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="出力先。既定は data/generated/ft/<data_id>/",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    dataset = generate(config)

    if args.dry_run:
        print("=" * 72)
        print("--dry-run: 配線確認。**実験ではない。**ファイルは書いていない。")
        print("ここに出る数値は組合せ論的な計数であって実験結果ではない(CLAUDE.md §2)。")
        print("=" * 72)
        print(json.dumps(dry_run_summary(dataset), ensure_ascii=False, indent=2))
        return 0

    out_dir = args.out_dir or OUTPUT_ROOT / str(dataset.manifest["data_id"])
    write_dataset(dataset, out_dir)
    print(f"train.jsonl: {dataset.manifest['outputs']['n_examples']} 行 -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
