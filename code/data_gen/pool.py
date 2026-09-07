"""項目プールの対(ordered pair)水準の機構。

答える問い: PLAN-001 §4「どの (a, b) を評価項目に使ってよいか」

ここにあるもの:
  - 主域の列挙(§4.1)と外挿域(§4.1.1)
  - 偶然一致の除外(§4.3)
  - 繰り上がり層(§4.2 B)
  - 訓練被覆ラベルの**実行時付与**(§4.2 A)
  - pilot / main の非交差な分割(§4.6)
  - 被覆セルの充填(ADR-017。プールは FT データ生成の後に作る)
  - プールのハッシュと manifest(§4.5)

ここに無いもの: タスク型ごとの項目構成(code/data_gen/battery_items.py)と
プロンプトの文面(code/eval/battery/、テンプレートは config)。

パラメータはここに直書きしない。値域・被覆・シードはすべて呼び出し側が
config から渡す(skill code-style §1)。
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from code.data_gen import prompt_format
from code.lesion import Lesion

Pair = tuple[int, int]

# 繰り上がり層のラベル(§4.2 B)。
CARRY = "carry"
NOCARRY = "nocarry"
NEGSUM = "negsum"

# 訓練被覆ラベル4値(PLAN-002 §4.5.1、ADR-019 決定4)。
# **生成時に固定せず実行時に付ける。**
COVERAGE_ID = "id"
COVERAGE_INTERP = "interp"
COVERAGE_OOB_ALGEBRAIC = "oob_algebraic"
COVERAGE_EXTRAP = "extrap"

# 主軸(Documents/05_STATISTICS.md §3.2)へ落としたときにだけ現れる2値。
# 上の4値の `extrap` を ADR-027 決定1(主軸)と決定2(副次)に割る。
# **ADR-062 決定1(= PLAN-017 E-1 案 (c))で、この割り方の定義を
# label_coverage の隣に置くと決めた。**解析側に写すと定義が2箇所に分かれる。
COVERAGE_EXTRAP_MAGNITUDE = "extrap_magnitude"
COVERAGE_EXTRAP_PAIR = "extrap_pair"

# 主要検定(§3.2 の交互作用モデル)に入る被覆水準(ADR-027 決定1)。
# label_main_coverage が返す5値のうち、残る2つは副次「汎化半径の地図」である。
MAIN_COVERAGE_LEVELS: tuple[str, ...] = (
    COVERAGE_ID,
    COVERAGE_INTERP,
    COVERAGE_EXTRAP_MAGNITUDE,
)

# 答え域ラベル2値(PLAN-002 §4.5.2)。被覆ラベルと直交する。
ANSWER_IN = "ans_in"
ANSWER_OUT = "ans_out"

# t 水準の被覆ラベル2値(PLAN-002 §4.5.1a、ADR-021)。上の2軸と直交する第3軸。
T_SEEN = "t_seen"
T_UNSEEN = "t_unseen"

# 訓練域の被演算子の下限(ADR-019 決定2 の [1, R_train]^2)。
# 上限は main_radius が持つ。PLAN-002 §7 が R_train = R_main を固定条件として
# 宣言しているため、答え域の上限に main_radius をそのまま使ってよい。
TRAIN_MIN_OPERAND = 1

# +2 病変で十の位が動く一の位。t mod 10 がこの集合なら carry 層(§4.2 B)。
# 病変の offset に依存するため、offset を変える実験では見直しが要る。
CARRY_ONES_DIGITS = frozenset({8, 9})

# 評価項目に使わない被演算子(ADR-035 決定3。旧 ADR-032 決定4 の T2 限定版)。
# **掛ける先は評価項目だけである**(同 決定4)。訓練被覆 K の抽出母集団には
# 掛けない —— 掛けると答えが1桁の層が 6 組 → 3 組に潰れる。
# **桁数掃引(code/eval/battery/magnitude_sweep.py)にも掛けない** ——
# あちらは評価プールではなく M* を決めるための別の項目集合であり、
# 抽出仕様は ADR-041 決定5 が凍結している。
EXCLUDED_OPERANDS: frozenset[int] = frozenset({1})

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
    """訓練被覆ラベル4値を**実行時に**付ける(PLAN-002 §4.5.1、ADR-019 決定4)。

    答える問い: 「この項目は FT データに出た組か、訓練域内の未出現か、
    0/負の被演算子か、外挿域か」

    判定はこの順に行う。順序は仕様である(PLAN-002 §4.5.1):

        extrap         : |a| > main_radius または |b| > main_radius
        oob_algebraic  : a <= 0 または b <= 0(かつ主域内)
        id             : (a,b) ∈ K
        interp         : 1 <= a,b <= main_radius かつ (a,b) ∉ K

    **oob_algebraic は被演算子の符号だけで決める。**訓練域の箱の大きさに
    依存させないので、将来 K の抽出範囲が変わっても意味が「0 と負数」の
    まま保たれる(PLAN-002 §4.5.1)。

    生成時に固定しないのは、Phase 1 の Go/No-Go で訓練の値域が
    狭められる可能性があるため。ラベルを実行時付与にしておけば、
    訓練域が変わっても項目プールを作り直さずに済む。

    内挿は「訓練域から訓練サンプラが引く K 組を除いた集合」として定義される
    (変更 C、§4.2)。予約割合というパラメータは置かない。
    """
    a, b = pair
    if abs(a) > main_radius or abs(b) > main_radius:
        return COVERAGE_EXTRAP
    if a <= 0 or b <= 0:
        return COVERAGE_OOB_ALGEBRAIC
    if pair in coverage_pairs:
        return COVERAGE_ID
    return COVERAGE_INTERP


def label_main_coverage(pair: Pair, coverage_pairs: frozenset[Pair], main_radius: int) -> str:
    """被覆ラベルを主軸の語彙へ落とす(ADR-027 決定1・決定2、ADR-062 決定1)。

    答える問い: 「この項目は `Documents/05_STATISTICS.md` §3.2 の `coverage`
    のどの水準に入るか。主軸に入らないなら、どちらの副次に落ちるのか」

    返すのは5値である: `id` / `interp` / `extrap_magnitude` / `extrap_pair` /
    `oob_algebraic`。このうち**主要検定に入るのは MAIN_COVERAGE_LEVELS の3つ
    だけ**で、残る2つは ADR-027 決定2 の副次「汎化半径の地図」である。
    **絞り込みはここでやらない**(ADR-062 決定4 = E-4。主軸の subset は
    解析側の責務であり、落ちた行が2箇所で消えないようにする)。

    **4値 → 3水準は恒等ではない**(PLAN-017 §4.2)。`label_coverage` の
    `extrap` は `|a| > main_radius` または `|b| > main_radius` で発火するので、
    **負の被演算子も、片側だけ域外の組も含む。**ADR-027 決定1 の
    `extrap_magnitude` は「主軸では `a, b >= 100`(両方正)」、すなわち
    **`a > main_radius` かつ `b > main_radius`** である。
    `(-99, 1)` も `(300, 50)` も `extrap` だが `extrap_magnitude` ではない。

    **`100` をリテラルで書かない。**`main_radius`(= config の
    `data.train_domain_max` = 99)より大きい、と書く。リテラルにすると
    訓練域を動かしたときに**主要検定の説明変数の定義が黙ってずれる**
    (skill code-style §1)。

    **答え域の軸で代用しない。**`a > R` かつ `b > R` なら `t >= 200 > 198` で
    必ず `ans_out` になるが、逆は成り立たない —— `(300, 50)` は `ans_out` でも
    `extrap_magnitude` ではない。ADR-027 の定義は被演算子の両側の条件である。

    **★仕様が曖昧な箇所(skill code-style §5)。**`extrap` のうち
    `extrap_magnitude` でないものを、ここでは一括して `extrap_pair` と
    呼んでいる —— ADR-062 決定1 が並べた5値の名前をそのまま使ったためである。
    **PLAN-002 §4.6 の厳密な定義は `extrap_pair := extrap かつ ans_in` であり、
    `(300, 50)`(片側だけ域外・答えも域外)はそこに入らない。**
    したがって**副次 C5 を組むときは `label_answer_range` の `ans_in` と
    交差させること。**`code/analysis/frame.py` はそのために答え域を別の列に残す。
    """
    label = label_coverage(pair, coverage_pairs, main_radius)
    if label != COVERAGE_EXTRAP:
        return label
    a, b = pair
    if a > main_radius and b > main_radius:
        return COVERAGE_EXTRAP_MAGNITUDE
    return COVERAGE_EXTRAP_PAIR


def label_answer_range(pair: Pair, main_radius: int) -> str:
    """答え域ラベルを付ける(PLAN-002 §4.5.2)。被覆ラベルと直交する。

    答える問い: 「この項目の答え t は、訓練で出力された答えの範囲に入るか」

    訓練域は [1, R_train]^2 なので、訓練で出た答えの全体はその像
    [2, 2*R_train] である(R_train = 99 なら [2, 198])。**答えが域内か
    域外かを被演算子の新規性から分けるため**の軸であり、これが無いと
    「外挿で落ちた」が「未見の組だから」か「答えが大きいから」かを
    分離できない(ADR-019 決定6)。

    R_train は main_radius をそのまま使う。PLAN-002 §7 が
    R_train = R_main = 99 を固定条件として宣言しているため。

    id と interp は構成的に必ず ans_in になる。この軸で分かれるのは
    oob_algebraic と extrap だけである。
    """
    total = sum(pair)
    return ANSWER_IN if 2 * TRAIN_MIN_OPERAND <= total <= 2 * main_radius else ANSWER_OUT


def coverage_sums_of(coverage_pairs: Iterable[Pair]) -> frozenset[int]:
    """訓練被覆 K 組が実際に出した和の集合(PLAN-002 §4.5.1a、ADR-021)。

    答える問い: 「訓練でモデルが目にした答え t はどれか」

    K はランダム抽出なので、K の組が覆う t は K そのものからは読み取れない。
    ここで1度だけ畳んで manifest に残し、label_t_coverage と共有する
    (定義が2箇所に分かれると manifest とラベルがずれる)。
    """
    return frozenset(a + b for a, b in coverage_pairs)


def label_t_coverage(pair: Pair, coverage_sums: frozenset[int]) -> str:
    """t 水準の被覆ラベルを付ける(PLAN-002 §4.5.1a、ADR-021)。

    答える問い: 「この項目の答え t は、訓練で出た t か」

    被覆ラベル(4値)・答え域ラベル(2値)と**直交する第3軸**である。
    arb の規則値は table[a+b] であり、**一般化は t の水準で起きる**ので、
    (a,b) 水準のラベルだけでは arb の解析の粒度が合わない(ADR-021 文脈)。

    **層として使うのは arb(および将来の表引き規則)の解析だけ**とする。
    p2 / p2d / x2 / ident は全域関数なのでこの軸で層別せず、記録のみ
    (ADR-021 決定3)。**セル構成には掛けない**(ADR-021 決定4)。軸を掛けると
    fill_cells の id 要求が増えて K の下限が上がる。

    id は構成的に必ず t_seen になる。

    coverage_sums は manifest から受け取る(coverage_seed に依存する量であり、
    実験シードで動かしてはならない。ADR-021 決定5)。
    """
    return T_SEEN if sum(pair) in coverage_sums else T_UNSEEN


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

    標本点のうち**その規則の定義域に入るものだけ**を見る(ADR-020)。
    arb は部分関数なので、定義域外の点で coincides を呼ぶと KeyError で
    落ちる。定義域内の標本点が1つも無い規則は、標本の領域では1件も
    除外しないので「プールを空にする」危険がない。よって退化とは扱わない。
    """
    if not lesions:
        raise ValueError(
            "除外集合の計算に使う参照規則が空である。"
            "p2 / arb / x2 のうち少なくとも1つを渡すこと(PLAN-001 §4.3)。"
        )
    for lesion in lesions:
        probed = [pair for pair in _DEGENERACY_PROBE if lesion.is_defined(*pair)]
        if probed and all(lesion.coincides(*pair) for pair in probed):
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

    **定義域外の規則はその候補で飛ばす**(ADR-020)。arb のズレ表は
    t ∈ [2,198] しか覆っておらず、評価候補のうち 100,298 組
    (oob_algebraic·ans_out 20,098 + extrap_magnitude 80,200)が定義域外に
    落ちる。ここで KeyError にすると**プール生成そのものが落ちる**。
    定義域を広げないことは ADR-020 の決定であって実装の都合ではない。
    """
    a, b = pair
    return any(lesion.coincides(a, b) for lesion in lesions if lesion.is_defined(a, b))


def is_indistinguishable(pair: Pair, first: Lesion, second: Lesion) -> bool:
    """2つの参照規則が同じ値を返す項目か(ADR-022 決定3)。

    答える問い: 「この項目は p2 と p2d を区別できるか」

    is_excluded が見るのは「真値 vs 規則値」の一致である。こちらは
    「規則値 vs 別の規則値」の一致で、別の概念である。p2d は真値とは
    決して一致しない(apply − t = offset + (t mod m) > 0)が、
    t ≡ 0 (mod digit_modulus) では p2 と一致し、**どちらの規則を適用したのかを
    採点で区別できなくなる。**主域 39,601 組のうち 3,961 組(10.0%)。

    どちらかの規則が定義域外なら「同じ値を返す」とは言えないので False。
    """
    a, b = pair
    if not (first.is_defined(a, b) and second.is_defined(a, b)):
        return False
    return first.apply(a, b) == second.apply(a, b)


def is_excluded_operand_pair(pair: Pair) -> bool:
    """評価項目に使えない被演算子を含む組か(ADR-035 決定3)。

    答える問い: 「この組は、どのタスク型の評価項目にも使ってよいか」

    `is_excluded`(真値と規則値の偶然一致)とは別の概念である。あちらは
    **採点が成立するか**を見る。こちらは**項目としての適格性**を見る ——
    被演算子 1 は `1 + n` が恒等写像に近く、「+2 を学んだ」のか
    「1 を足す形だけ特別扱いした」のかが分離しにくい(ADR-035 決定3)。
    """
    return any(operand in EXCLUDED_OPERANDS for operand in pair)


def eligible_item_pairs(pairs: Sequence[Pair]) -> list[Pair]:
    """評価項目の候補から、除外対象の被演算子を含む組を落とす(ADR-035 決定3)。

    答える問い: 「評価プールのセルは、どの組から埋めてよいか」

    **項目生成器に渡す前に掛ける。**後段で落とすと件数が静かに減り、
    条件間で項目集合が変わって混合効果モデルの項目ランダム効果が条件と
    交絡する(PLAN-001 §3)。落とした件数は
    `excluded_operand_record` が manifest に残す。
    """
    return [pair for pair in pairs if not is_excluded_operand_pair(pair)]


def excluded_operand_record(
    candidates_by_group: Mapping[str, Sequence[Pair]],
) -> dict[str, object]:
    """被演算子の除外を manifest に残す形にする(ADR-035 帰結)。

    答える問い: 「評価プールの被演算子分布は、何から何を落とした結果か」

    **プール全体の欄である**(ADR-035 帰結)。ADR-032 決定4 の時点では
    T2 だけの規則だったのでタスク型ごとの欄だったが、決定3 で
    全タスク型共通の項目規約に昇格した。群ごとの内訳は `by_group` に残す ——
    「どの群で何組落ちたか」が消えると、群間で被演算子分布が揃っている
    ことを manifest から確かめられなくなる。

    渡すのは**除外を掛ける前**の候補である。除外後の集合を渡すと
    `n_excluded` が常に 0 になり、記録が意味を失う。
    """
    by_group: dict[str, dict[str, int]] = {}
    for group, candidates in sorted(candidates_by_group.items()):
        excluded = [pair for pair in candidates if is_excluded_operand_pair(pair)]
        by_group[group] = {"n_candidates": len(candidates), "n_excluded": len(excluded)}
    return {
        "scope": "pool",
        "excluded_operands": sorted(EXCLUDED_OPERANDS),
        "rule": "ADR-035 決定3(ADR-032 決定4 を全タスク型に広げたもの)",
        "reason": (
            "被演算子 1 は 1+n が恒等写像に近く、規則を学んだのか 1 の形だけを"
            "特別扱いしたのかが分離しにくい。タスク型ごとに除外規則が違うほうが"
            "交互作用の解釈を壊す(T2 では \"1 apples\" が非文にもなる。ADR-032 決定4)"
        ),
        "applied_to": "eval_items_only",
        "n_candidates": sum(entry["n_candidates"] for entry in by_group.values()),
        "n_excluded": sum(entry["n_excluded"] for entry in by_group.values()),
        "by_group": by_group,
    }


def eligible_pairs(
    pairs: Iterable[Pair],
    lesions: Sequence[Lesion],
    *,
    indistinguishable_rule_pairs: Sequence[tuple[Lesion, Lesion]] = (),
) -> list[Pair]:
    """除外規則を通った順序対だけを返す。

    答える問い: 「評価項目に使ってよい組はどれだけ残るか」

    2種類の除外を掛ける:

    1. **真値との偶然一致**(§4.3、CLAUDE.md §6)。lesions が対象
    2. **規則どうしの一致**(ADR-022 決定3)。indistinguishable_rule_pairs が対象。
       **p2d を条件に入れる実行では (p2, p2d) を必ず渡すこと。**
       渡し忘れると t ≡ 0 (mod 10) の項目が残り、p2d 条件の rule_rate に
       「p2 を適用しただけの応答」が混ざる

    2 を lesions から自動で組まないのは、規則の全ペアを取ると ADR-022 が
    指示していない除外(p2 vs x2 の t=2、arb vs p2 など)まで増えて
    項目数が黙って変わるためである。除外の追加は実験条件の変更であり、
    エージェントが決めてよい事柄ではない(CLAUDE.md §8)。
    """
    validate_reference_lesions(lesions)
    return [
        pair
        for pair in pairs
        if not is_excluded(pair, lesions)
        and not any(
            is_indistinguishable(pair, first, second)
            for first, second in indistinguishable_rule_pairs
        )
    ]


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
# id セルの母集団(ADR-034 帰結 / ADR-035 決定3。PLAN-008 §2-3)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IdCellPopulation:
    """`id` セルを引く母集団と、そこへ至る絞り込みの記録。

    答える問い: 「`id` セルは K の何組から引かれるのか」(ADR-034 リスク欄)
    """

    pairs: list[Pair]
    record: dict[str, object]


def _stratum_counts(pairs: Sequence[Pair]) -> dict[str, int]:
    counts = {CARRY: 0, NOCARRY: 0}
    for pair in pairs:
        counts[carry_label(*pair)] = counts.get(carry_label(*pair), 0) + 1
    return counts


def id_cell_population(
    coverage_pairs: Sequence[Pair],
    lesions: Sequence[Lesion],
    *,
    indistinguishable_rule_pairs: Sequence[tuple[Lesion, Lesion]] = (),
) -> IdCellPopulation:
    """訓練被覆 K に**評価側の除外**を掛けた残りを返す(ADR-034 リスク欄)。

    答える問い: 「`id` セルの母集団は `K` そのものか」→ **違う。**

    ADR-034 決定1 で判別不能の除外(`t ≡ 0 (mod digit_modulus)`)を `K` の
    抽出母集団から外し、ADR-035 決定3 で被演算子 1 の除外を全タスク型の
    評価項目に広げた。どちらも**評価側にだけ掛かる**ので、`id` セルは
    `K` の全体ではなくこの残りから引かれる。**その事実を数え上げごと
    manifest に残すのが順4 の仕事である**(ADR-034「順4 の項目生成で明示する」)。

    段を分けて数えるのは、`carry` 層がどこで動くかを見せるためである ——
    判別不能で落ちる組は一の位が 0 なので**必ず `nocarry`** であり
    `carry` 層は動かないが、被演算子 1 の除外は両方の層を削る。

    ここに出る数は**組合せ論的な計数であって実験結果ではない**(`CLAUDE.md` §2)。
    """
    stages: list[dict[str, object]] = []

    def record_stage(name: str, pairs: Sequence[Pair], rule: str) -> None:
        stages.append(
            {"name": name, "rule": rule, "n": len(pairs), "strata": _stratum_counts(pairs)}
        )

    current = list(coverage_pairs)
    record_stage("coverage_k", current, "訓練被覆 K そのもの(ft_data の manifest から転記)")

    current = eligible_pairs(current, lesions)
    record_stage("coincidence", current, "真値と規則適用値の偶然一致(ADR-016 / PLAN-001 §4.3)")

    current = eligible_pairs(
        current, lesions, indistinguishable_rule_pairs=indistinguishable_rule_pairs
    )
    record_stage(
        "indistinguishable_rule_pairs",
        current,
        "規則どうしが同じ値を返す組(ADR-022 決定3。ADR-034 で評価側だけに掛かる)",
    )

    current = eligible_item_pairs(current)
    record_stage("excluded_operands", current, "被演算子の除外(ADR-035 決定3)")

    return IdCellPopulation(
        pairs=sorted(current),
        record={
            "source": "coverage_k",
            "note": (
                "id セルはこの母集団から引く。**K そのものではない**"
                "(ADR-034 リスク欄)。数は組合せ論的な計数であって実験結果ではない"
            ),
            "stages": stages,
            "n_pairs": len(current),
            "pairs_hash": pairs_hash(sorted(current)),
        },
    )


# --------------------------------------------------------------------------
# 被覆セルの充填(ADR-017。PLAN-001 §5.1.1 の穴1 に対する案A)
# --------------------------------------------------------------------------


class InsufficientCandidatesError(ValueError):
    """セルを埋めるだけの候補が無い。

    黙って少ない件数で続けない。条件間で項目集合が変わると、混合効果
    モデルの項目ランダム効果が条件と交絡する(PLAN-001 §3)。
    """


@dataclass(frozen=True)
class Cell:
    """項目プールの1セル(PLAN-001 §5.1 の表の1行 × 1層)。

    答える問い: 「このセルは、どの被覆・どの繰り上がり層の組を何件使うか」

    carry=None は「繰り上がりで層別しない」を意味する。T3 / T1b は層別し、
    G2〜G5 は §5.1 の表では層別していない。
    """

    name: str
    coverage: str
    carry: str | None
    n: int


def fill_cells(
    candidates: Sequence[Pair],
    cells: Sequence[Cell],
    *,
    coverage_pairs: frozenset[Pair],
    main_radius: int,
    seed: int,
) -> dict[str, list[Pair]]:
    """セルごとに順序対を重複なく割り当てる(ADR-017)。

    答える問い: 「`id` / `interp` / `extrap` のセルを、それぞれ何から埋めるか」

    ADR-017(案A)により、**プールは FT データ生成の後に作る。**`id` セルは
    訓練被覆 `K` 組(`coverage_pairs`)から、`interp` セルはその補集合から埋まる。
    これは `label_coverage` を通した結果としてそうなるので、ここに `id` 用の
    特別な分岐は無い。

    - **同じ組を2つのセルに入れない。**項目が重複すると項目ランダム効果が壊れる
    - **埋まらなければ例外で止める。**件数を黙って減らさない
    - シードを固定すれば同じ割り当てになる(preflight が再現して照合する。§4.5)
    """
    names = [cell.name for cell in cells]
    if len(set(names)) != len(names):
        raise ValueError(f"セル名が重複している: {names}")

    shuffled = list(candidates)
    random.Random(seed).shuffle(shuffled)

    used: set[Pair] = set()
    assignment: dict[str, list[Pair]] = {}
    for cell in cells:
        available = [
            pair
            for pair in shuffled
            if pair not in used
            and label_coverage(pair, coverage_pairs, main_radius) == cell.coverage
            and (cell.carry is None or carry_label(*pair) == cell.carry)
        ]
        if len(available) < cell.n:
            raise InsufficientCandidatesError(
                f"セル {cell.name!r}(coverage={cell.coverage}, carry={cell.carry})の候補が "
                f"{len(available)} 組しかなく、{cell.n} 件を埋められない。"
                "被覆 K・値域・除外規則のどれかを人間が見直すこと(ADR-017)。"
            )
        chosen = available[: cell.n]
        used.update(chosen)
        assignment[cell.name] = sorted(chosen)
    return assignment


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
    specificity_reference_rules: Sequence[str],
    coverage_sums: Iterable[int],
    seed: int,
    main_radius: int,
    extrapolation_radius: int | None,
    extrapolation_run_id: str | None,
    counterpart_pool_id: str | None,
    counterpart_hash: str | None,
    prompt_format_block: Mapping[str, object],
    item_exclusions: Mapping[str, object],
    id_cell_population: Mapping[str, object],
    fill: Mapping[str, object],
) -> dict[str, object]:
    """プールの manifest を組む(§4.5、§4.6 の 3、ADR-016)。

    答える問い: 「このプールが何から作られたかを、後から検証できる形で残せているか」

    reference_rules を残すのは ADR-016 の未検証・リスクへの対応である。
    偶然一致の除外は**プール生成時**に行うため、生成後に参照規則を増やすと
    その規則についての偶然一致項目がプールに残っている可能性がある。
    eval.reference_rule がこの集合に含まれることを実行前に検査する。

    specificity_reference_rules を**別の欄にする**のは ADR-033 決定1・2 である。
    reference_rules は「code/data_gen/pool.py の eligible_pairs に渡した規則」の
    記録であり、特異性対照の spec_sub / spec_mul はそこを通らない ——
    あちらの偶然一致除外は specificity_control.build_items が項目1件ごとに
    is_discriminating を強制する形で行われる。**同じ欄に混ぜてはならない。**
    混ぜると eval.reference_rule に spec_sub を誤指定しても
    scoring.validate_reference_rule が素通しする(ADR-033 の代替案「フラットな
    和集合」を却下した理由)。code/lesion.py が2つの関数に分かれているのと
    同じ切り方である。

    fill を残すのは ADR-033 決定3 である。「このプールをどう埋めたか」を
    書かないと、seed の欄だけが残って**サンプリングされたプールに見える。**
    セルの充填方針は未決であり(承認待ち。M* が決まるまで extrap セルは
    原理的に埋まらない)、いまは明示リストで埋めている。その事実を
    manifest 自身に残す。

    extrapolation_run_id を残すのは、外挿域の上限 M* が決め打ちに戻って
    いないことを preflight が検査できるようにするため(§4.1.1、§4.5)。

    coverage_sums を残すのは ADR-021 決定2・5 のため。t 水準の被覆ラベルは
    実行時に付与するので、判定に使った和の集合が manifest に無いと
    後から t_seen / t_unseen を再現できない。**coverage_seed に依存する量で
    あり、実験シードで動かしてはならない。**coverage_sums_of() で作る。

    prompt_format_block を残すのは PLAN-002 §4.8.1 検査6 のため。**このプールは
    §5.2 の評価アンカー(T1 = 裸の計算式)を含む**ので、訓練側の manifest と
    同形の書式ブロックを持ち、`format_hash` が一致していなければならない。
    ブロックは code/data_gen/prompt_format.py が組む。既定値を作らないのは、
    書式が実験条件だからである(欠けたまま生成すると、preflight から見て
    「訓練と評価で書式が違う」に化ける)。

    item_exclusions を残すのは ADR-032 決定4 のため。項目としての適格性による
    除外(被演算子 1)は §4.3 のプール全体の偶然一致除外とは別物であり、
    reference_rules からは読み取れない。記録しないと、評価プールの被演算子分布が
    訓練分布と違う理由が manifest から消える。**ADR-035 決定3 でこの除外は
    T2 限定から全タスク型共通の項目規約に昇格した**ので、欄はタスク型ごとでは
    なく**プール全体**である(群ごとの内訳は by_group に残る)。除外が無いなら
    空の dict を渡す —— 「まだ考えていない」と「無い」を引数の有無で混ぜない。

    id_cell_population を残すのは ADR-034 リスク欄(「順4 の項目生成で明示する」)
    のため。**`id` セルの母集団は訓練被覆 `K` そのものではない** ——
    判別不能の除外と被演算子の除外がどちらも評価側にだけ掛かるからである。
    書かないと、`id` セルが K から一様に引かれているように読める。
    """
    prompt_format.validate(prompt_format_block)
    return {
        "pool_id": pool_id,
        "n_pairs": len(pairs),
        "pairs_hash": pairs_hash(pairs),
        "reference_rules": sorted(reference_rules),
        "specificity_reference_rules": sorted(specificity_reference_rules),
        "coverage_sums": sorted(coverage_sums),
        "seed": seed,
        "main_radius": main_radius,
        "extrapolation_radius": extrapolation_radius,
        "extrapolation_run_id": extrapolation_run_id,
        "counterpart_pool_id": counterpart_pool_id,
        "counterpart_hash": counterpart_hash,
        "prompt_format": dict(prompt_format_block),
        "item_exclusions": dict(item_exclusions),
        "id_cell_population": dict(id_cell_population),
        "fill": dict(fill),
        "pairs": sorted(pairs),
    }
