"""項目プールの対(ordered pair)水準の機構。

答える問い: PLAN-001 §4「どの (a, b) を評価項目に使ってよいか」

ここにあるもの:
  - 主域の列挙(§4.1)と外挿域(§4.1.1)
  - 偶然一致の除外(§4.3)
  - 繰り上がり層(§4.2 B)
  - 訓練被覆ラベルの**実行時付与**(§4.2 A)
  - pilot / main の非交差な分割(§4.6)
  - プールのハッシュと manifest(§4.5)

ここに無いもの: 群 G1〜G6 の項目構成(code/data_gen/battery_items.py)と
プロンプトの文面(code/eval/battery/、テンプレートは config)。

パラメータはここに直書きしない。値域・被覆・シードはすべて呼び出し側が
config から渡す(skill code-style §1)。
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable, Sequence

from code.lesion import Lesion

Pair = tuple[int, int]

# 繰り上がり層のラベル(§4.2 B)。
CARRY = "carry"
NOCARRY = "nocarry"
NEGSUM = "negsum"

# 訓練被覆ラベル(§4.2 A)。**生成時に固定せず実行時に付ける。**
COVERAGE_ID = "id"
COVERAGE_INTERP = "interp"
COVERAGE_EXTRAP = "extrap"

# +2 病変で十の位が動く一の位。t mod 10 がこの集合なら carry 層(§4.2 B)。
# 病変の offset に依存するため、offset を変える実験では見直しが要る。
CARRY_ONES_DIGITS = frozenset({8, 9})

# 参照規則が退化していないかを見るための標本。網羅ではなく、
# 0・正・負・非対称をまたぐことが目的。
_DEGENERACY_PROBE: tuple[Pair, ...] = ((0, 0), (1, 2), (3, 4), (-5, 7), (10, -3), (-1, -1))


class DegenerateReferenceRuleError(ValueError):
    """常に真値と一致する規則を除外集合の計算に入れようとした。

    ADR-016 の未検証・リスクそのもの。ident(および offset=0 の加法規則)は
    coincides が常に True なので、素朴に和を取ると**プールが空になる**。
    """


# --------------------------------------------------------------------------
# 値域
# --------------------------------------------------------------------------


def main_domain_pairs(radius: int) -> list[Pair]:
    """主域 D_main の順序対をすべて返す(§4.1)。

    答える問い: 「FT データと内挿ホールドアウトの供給元はどの集合か」

    radius=99 で 199 × 199 = 39,601 組。0 と負数を含む(人間の決定 1)。
    """
    if radius < 0:
        raise ValueError(f"radius は 0 以上。渡された値: {radius}")
    values = range(-radius, radius + 1)
    return [(a, b) for a in values for b in values]


def extrapolation_pairs(main_radius: int, extrapolation_radius: int) -> list[Pair]:
    """外挿域 D_ext の順序対を返す(§4.1.1)。

    答える問い: 「素のモデルがまだ解ける範囲のうち、主域の外はどこか」

    extrapolation_radius は Phase 0 の実測から決まる M* である。
    **既定値を作らない。**呼び出し側が run_id に紐づいた実測値を渡す。
    M* が主域の半径以下なら D_ext は空になり、外挿バッテリは成立しない
    (§4.1.1。黙って空プールを作らず、人間の判断に上げる)。
    """
    if extrapolation_radius <= main_radius:
        raise ValueError(
            f"M*={extrapolation_radius} が主域の半径 {main_radius} 以下である。"
            "外挿域が空になり外挿バッテリは成立しない(PLAN-001 §4.1.1)。"
            "θ の見直しか外挿テストの取り下げを人間に諮ること。"
        )
    values = range(-extrapolation_radius, extrapolation_radius + 1)
    return [(a, b) for a in values for b in values if abs(a) > main_radius or abs(b) > main_radius]


# --------------------------------------------------------------------------
# 層
# --------------------------------------------------------------------------


def carry_label(a: int, b: int) -> str:
    """繰り上がり層のラベルを返す(§4.2 B)。

    答える問い: 「+2 を適用したとき十の位が動く項目か」

    負の和(negsum)を層別の対象から外すのは、十進表記上「一の位」と
    「繰り上がり」が一意に定まらないためである。独立した第3の層として
    報告し、繰り上がりの検定には使わない。
    """
    total = a + b
    if total < 0:
        return NEGSUM
    if total % 10 in CARRY_ONES_DIGITS:
        return CARRY
    return NOCARRY


def label_coverage(pair: Pair, coverage_pairs: frozenset[Pair], main_radius: int) -> str:
    """訓練被覆ラベルを**実行時に**付ける(§4.2 A)。

    答える問い: 「この項目は FT データに出た組か、主域内の未出現か、外挿域か」

    生成時に固定しないのは、Phase 1 の Go/No-Go で訓練の値域が
    狭められる可能性があるため。ラベルを実行時付与にしておけば、
    訓練域が変わっても項目プールを作り直さずに済む。

    内挿は「主域から訓練サンプラが引く K 組を除いた集合」として定義される
    (変更 C、§4.2)。予約割合というパラメータは置かない。
    """
    a, b = pair
    if abs(a) > main_radius or abs(b) > main_radius:
        return COVERAGE_EXTRAP
    if pair in coverage_pairs:
        return COVERAGE_ID
    return COVERAGE_INTERP


# --------------------------------------------------------------------------
# 除外(§4.3)
# --------------------------------------------------------------------------


def validate_reference_lesions(lesions: Sequence[Lesion]) -> None:
    """除外集合の計算に使ってよい規則かを検査する。

    答える問い: 「この規則の集合で除外を計算すると、プールが空にならないか」

    ident のように coincides が常に True の規則を入れると、全項目が
    除外されてプールが空になる(§4.3、ADR-016)。名前ではなく**振る舞い**で
    弾くのは、offset=0 の加法規則のように名前が違っても同じ退化をする
    規則があるため。
    """
    if not lesions:
        raise ValueError(
            "除外集合の計算に使う参照規則が空である。"
            "p2 / arb / x2 のうち少なくとも1つを渡すこと(PLAN-001 §4.3)。"
        )
    for lesion in lesions:
        if all(lesion.coincides(a, b) for a, b in _DEGENERACY_PROBE):
            raise DegenerateReferenceRuleError(
                f"規則 {lesion.name!r} は標本の全項目で真値と一致する。"
                "除外集合に入れるとプールが空になる(PLAN-001 §4.3、ADR-016)。"
                "ident および offset=0 の規則は除外集合の計算に含めない。"
            )


def is_excluded(pair: Pair, lesions: Sequence[Lesion]) -> bool:
    """真値と規則適用値が偶然一致する項目か(§4.3)。

    答える問い: 「この項目は correct と rule を区別できるか」

    除外は生成時に行い、評価側で後から落とさない
    (skill code-style §4、CLAUDE.md §6)。
    """
    a, b = pair
    return any(lesion.coincides(a, b) for lesion in lesions)


def eligible_pairs(pairs: Iterable[Pair], lesions: Sequence[Lesion]) -> list[Pair]:
    """除外規則を通った順序対だけを返す。

    答える問い: 「評価項目に使ってよい組はどれだけ残るか」
    """
    validate_reference_lesions(lesions)
    return [pair for pair in pairs if not is_excluded(pair, lesions)]


# --------------------------------------------------------------------------
# pilot / main の分割(§4.6)
# --------------------------------------------------------------------------


def split_pilot_main(pairs: Sequence[Pair], pilot_size: int, seed: int) -> dict[str, list[Pair]]:
    """順序対を pilot 用と main 用に**交わらないように**分ける(§4.6)。

    答える問い: 「ハイパラ選択に使う組と、本実験で評価する組をどう分離するか」

    パイロットの目的はハイパラの選択である。選択に使った項目の上で
    本実験を評価すると、選択のバイアスがそのまま本実験の数字に入り、
    事前登録が形骸化する。

    シードを固定するのは、同じ分割を preflight が再現して照合できるようにするため。
    """
    if pilot_size < 0 or pilot_size > len(pairs):
        raise ValueError(f"pilot_size={pilot_size} が 0..{len(pairs)} の外にある")
    shuffled = list(pairs)
    random.Random(seed).shuffle(shuffled)
    return {"pilot": sorted(shuffled[:pilot_size]), "main": sorted(shuffled[pilot_size:])}


def pools_are_disjoint(first: Iterable[Pair], second: Iterable[Pair]) -> bool:
    """2つのプールが順序対の水準で交わらないか(§4.6 の 1)。"""
    return not (set(first) & set(second))


# --------------------------------------------------------------------------
# ハッシュと manifest(§4.5)
# --------------------------------------------------------------------------


def pairs_hash(pairs: Iterable[Pair]) -> str:
    """順序対集合のハッシュ。preflight が config の記録と照合する(§4.5)。

    答える問い: 「実行しようとしているプールは、記録されたプールと同じものか」

    並び順に依存させない(ソートしてから畳む)。生成器の反復順が変わっても
    集合が同じならハッシュは同じであってほしい。
    """
    payload = json.dumps(sorted(pairs), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    pool_id: str,
    pairs: Sequence[Pair],
    reference_rules: Sequence[str],
    seed: int,
    main_radius: int,
    extrapolation_radius: int | None,
    extrapolation_run_id: str | None,
    counterpart_pool_id: str | None,
    counterpart_hash: str | None,
) -> dict[str, object]:
    """プールの manifest を組む(§4.5、§4.6 の 3、ADR-016)。

    答える問い: 「このプールが何から作られたかを、後から検証できる形で残せているか」

    reference_rules を残すのは ADR-016 の未検証・リスクへの対応である。
    偶然一致の除外は**プール生成時**に行うため、生成後に参照規則を増やすと
    その規則についての偶然一致項目がプールに残っている可能性がある。
    eval.reference_rule がこの集合に含まれることを実行前に検査する。

    extrapolation_run_id を残すのは、外挿域の上限 M* が決め打ちに戻って
    いないことを preflight が検査できるようにするため(§4.1.1、§4.5)。
    """
    return {
        "pool_id": pool_id,
        "n_pairs": len(pairs),
        "pairs_hash": pairs_hash(pairs),
        "reference_rules": sorted(reference_rules),
        "seed": seed,
        "main_radius": main_radius,
        "extrapolation_radius": extrapolation_radius,
        "extrapolation_run_id": extrapolation_run_id,
        "counterpart_pool_id": counterpart_pool_id,
        "counterpart_hash": counterpart_hash,
        "pairs": sorted(pairs),
    }
