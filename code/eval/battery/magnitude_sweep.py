"""桁数掃引の項目を作る(PLAN-001 §4.1.1 の手続き1)。

答える問い: 「上限 M の入れ子の域から、素のモデルに解かせる加算項目をどう作るか」

    R(M) = { (a, b) : |a| <= M, |b| <= M }
    Q(M) = { (a, b) ∈ R(M) : label_main_coverage が extrap_magnitude を返す }

§4.1.1 の手続きは4段ある。**ここが実装するのは 1 だけ**である:

  1. R(M) と Q(M) を定める                ← このモジュール
  2. 素のモデルに M を掃きながら解かせる  ← code/eval/sweep.py
  3. 規則2 で M* を置く                   ← **人間**(ADR-041 決定3 規則2)
  4. D_ext = R(M*) のうち主域と交わらない部分        ← **未実装**

**項目を引く腕は 2 本ある**(ADR-071 決定1・決定2。2026-09-09 採択):

  - **一様抽出の腕** `build_items` —— R(M) 全体から引く。**記述**(累積の曲線と格子殻)。
    **ADR-071 決定2 が「1 文字も変えない」とした現行の 13,000 項目を作る関数である**
  - **Q(M) の腕** `build_quadrant_items` —— 主軸 3 水準目(`extrap_magnitude`)の
    母集団から引く。**判定の材料**(ADR-070 決定4 = C2 の「殻の正答率」の殻がこれ)

**θ の値も M* もここでは扱わない。**θ は ADR-070 が config に置き、規則2 を適用して
M* を置くのは人間である(ADR-041 / ADR-045 と同じ思想)。
掃引する M の列・1点あたりの項目数・シード・Q(M) の腕の水準は**すべて config から来る**。

**真値と規則適用値が割れない組は落とす**(`numeric_sum.non_discriminating_rules`)。
例: `x2` は a + b = 0 の組で規則適用値が真値と一致する。ADR-034 により、この除外は
**K の抽出母集団には掛からず評価項目に掛かる** —— 掃引の項目は評価項目である。

**規則どうしの判別不能はここでは落としていない。**`p2d` は t ≡ 0 (mod 10) で
`p2` と同じ値を返すが(ADR-022 決定3)、それは「真値 vs 規則値」ではなく
「規則値 vs 別の規則値」の一致であり、判定は `code/data_gen/pool.py` の
`is_indistinguishable` が持つ。掃引の採点は**主要参照規則の1ブロックだけ**で
あり(`code/eval/sweep.py` 冒頭)、どちらの規則を適用したのかを問わないので
ここでは掛けない。評価プール側にこの除外を掛けるのは順4 の仕事である(ADR-035)。

**素の算術能力の測定であって病変の測定ではない。**掃引を回すのは
`lesion.condition = none`(学習ゼロ)のモデルである。それでも4値すべてを
出すのは CLAUDE.md §6 の要求であり、加えて素のモデルの `rule_rate` が
0 付近に留まることが、後で FT 後の `rule_rate` を読むときのベースラインになる。
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from code.config import ConfigError, require
from code.data_gen.battery_items import Item, make_item
from code.data_gen.pool import COVERAGE_EXTRAP_MAGNITUDE, Pair, label_main_coverage
from code.eval.battery import numeric_sum
from code.lesion import Lesion

# 掃引の設定はこの節の下に置く。config の他の節と混ぜないのは、
# 本実験の評価プール(eval.pool_items / eval.cells)とは別の項目集合だからである。
SWEEP_SECTION = "eval.magnitude_sweep"

# item_id に載せる付帯情報の鍵。同じ (a, b) が別の M で引かれたときに
# item_id が衝突しないようにする。
RADIUS_PARAM = "radius"

# ★ADR-071 決定1(殻-a = 案 D)が判定に採った集合の名前。config の
# `eval.magnitude_sweep.shell_definition` はこの文字列でなければならない。
# **実装している殻の定義はこれ 1 つだけである**(定義 A / B は判定に使わない)。
SHELL_DEFINITION_QUADRANT = "extrap_magnitude_quadrant"

# Q(M) の腕の item_id に載せる付帯情報の鍵。一様抽出の腕が同じ (a, b) を
# 同じ M で引いたときに item_id が衝突しないようにする(RADIUS_PARAM と同じ理由)。
SHELL_PARAM = "shell"

# 主域の半径は訓練域の上限である(`label_main_coverage` の docstring。PLAN-002 §7 が
# R_train = R_main を固定条件として宣言している)。**99 をリテラルで書かない。**
MAIN_RADIUS_KEY = "data.train_domain_max"

# Q(M) の判定は訓練被覆の組 K に依存しない —— `label_coverage` は extrap を
# K より先に判定して返す。掃引は素のモデル(K を持たない)の測定なので空集合を渡す。
NO_COVERAGE_PAIRS: frozenset[Pair] = frozenset()


class InsufficientPairsError(ValueError):
    """要求した本数の項目を R(M) から取れなかった。

    黙って少ない本数で表を作らない。M ごとに n が違う表は、
    correct_rate の M 間比較が成立しない(PLAN-001 §4.1.1 の3)。
    """


def domain_size(radius: int) -> int:
    """|R(M)| = (2M+1)^2。負数と 0 を含む(§4.1.1 は絶対値で域を切っている)。"""
    if radius < 1:
        raise ValueError(f"radius は 1 以上である: {radius}")
    return (2 * radius + 1) ** 2


def in_domain(pair: Pair, radius: int) -> bool:
    """この組は R(M) に入るか。定義 A の格子殻を切り直すときに使う(ADR-071 決定1)。"""
    a, b = pair
    return abs(a) <= radius and abs(b) <= radius


def domain_pairs(radius: int) -> Iterator[Pair]:
    """R(M) の要素を a の昇順、次に b の昇順で列挙する。個数は `domain_size` に一致する。"""
    if radius < 1:
        raise ValueError(f"radius は 1 以上である: {radius}")
    values = range(-radius, radius + 1)
    return ((a, b) for a in values for b in values)


def build_items(
    radius: int,
    *,
    n_items: int,
    seed: int,
    pool_id: str,
    reference_lesions: Mapping[str, Lesion],
) -> list[Item]:
    """R(M) から加算項目を n 件作る。

    答える問い: 「この M で素のモデルに解かせる項目集合は何か」

    **列挙せず抽出する。**M = 999 なら |R(M)| は約 400 万組であり、
    列挙してから選ぶとメモリで詰まる。

    **引く回数の上限を |R(M)| に置く。**判別不能な組を捨てながら引くので、
    上限が無いと取り切れないときに止まらない。「R(M) の要素数と同じ回数
    引いてなお足りないなら、その M では成立しない」は根拠のある打ち切りで
    あり、実装の都合で決めた定数ではない(skill code-style §1)。

    シードに M を混ぜる理由: `seed` だけで引くと、どの M でも同じ乱数列に
    なる。M ごとに独立な標本にしたいが、`seed` を人が M ごとに書き分ける
    のは間違いのもとである。文字列シードは再現する(random は sha512 で畳む)。
    """
    if n_items < 1:
        raise ValueError(f"n_items は 1 以上である: {n_items}")
    if not reference_lesions:
        raise ValueError("参照規則が空。判別可能性を確かめられない(PLAN-001 §5.3)")
    limit = domain_size(radius)
    if n_items > limit:
        raise InsufficientPairsError(
            f"M={radius} の R(M) は {limit} 組しかなく、{n_items} 件は取れない"
        )
    rng = random.Random(f"{seed}:{radius}")
    seen: set[Pair] = set()
    eligible: list[Pair] = []
    for _ in range(limit):
        if len(eligible) == n_items:
            break
        pair = (rng.randint(-radius, radius), rng.randint(-radius, radius))
        if pair in seen:
            continue
        seen.add(pair)
        if _is_eligible(pair, pool_id=pool_id, reference_lesions=reference_lesions):
            eligible.append(pair)
    if len(eligible) < n_items:
        raise InsufficientPairsError(
            f"M={radius} から判別可能な組を {n_items} 件取れなかった"
            f"(取れたのは {len(eligible)} 件 / 引いた相異なる組 {len(seen)})。"
            "参照規則の集合を確認すること(ADR-034)。"
        )
    return numeric_sum.build_bare_sum_items(
        sorted(eligible),
        pool_id=pool_id,
        reference_lesions=reference_lesions,
        params={RADIUS_PARAM: radius},
    )


def _is_eligible(
    pair: Pair, *, pool_id: str, reference_lesions: Mapping[str, Lesion]
) -> bool:
    """この組は、すべての参照規則の下で correct と rule を区別できるか。

    判定そのものは `numeric_sum.non_discriminating_rules` にある。ここで
    独自に判定を書かないのは、生成時に弾く経路と規則がずれると、
    片方だけが判別不能な項目を通すためである。
    """
    probe = make_item(
        pool_id=pool_id,
        group=numeric_sum.GROUP_BARE_SUM,
        category=numeric_sum.T1_CATEGORY,
        operands=pair,
    )
    return not numeric_sum.non_discriminating_rules(probe, reference_lesions)


# --------------------------------------------------------------------------
# Q(M) の腕(ADR-071。2026-09-09 採択。提案 エージェント (Opus) / 採択 人間)
# --------------------------------------------------------------------------


def quadrant_pairs(radius: int, *, main_radius: int) -> list[Pair]:
    """Q(M) を列挙する(ADR-071 決定1)。

    答える問い: 「この M で、外挿腕(主軸 3 水準目 `extrap_magnitude`)が実際に使う組はどれか」

    **定義をここに書き直さない。**R(M) の組のうち `label_main_coverage` が
    `extrap_magnitude` を返すものを拾うだけにする。被演算子の範囲をここに式で
    書くと、訓練域(`data.train_domain_max`)を動かしたときに判定集合と
    主軸 3 水準目が黙ってずれる(skill code-style §1)。

    **閉じた式 `(M - main_radius)^2` で数えない。**M < main_radius でも平方が正に
    なり、台地アンカーが判定水準に混じる(★罠。PLAN-021 §3、
    `code/tests/test_design_facts.py` の `_quadrant_size`)。列挙なら
    M <= main_radius で自然に空になる。

    **R(M) を全列挙する。**判定は比較だけなので M = 999 でも足りる。
    直積であることを仮定して速くすると、その仮定が定義の書き直しになる。
    """
    return [
        pair
        for pair in domain_pairs(radius)
        if label_main_coverage(pair, NO_COVERAGE_PAIRS, main_radius) == COVERAGE_EXTRAP_MAGNITUDE
    ]


def build_quadrant_items(
    radius: int,
    *,
    n_items: int,
    seed: int,
    pool_id: str,
    reference_lesions: Mapping[str, Lesion],
    main_radius: int,
) -> list[Item]:
    """Q(M) から加算項目を n 件引く(ADR-071 決定2)。

    答える問い: 「この M で外挿腕が使う組のうち、素のモデルに解かせる n 件はどれか」

    **一様抽出の腕(`build_items`)とは別の関数にする。**`build_items` は
    ADR-071 決定2 が「1 文字も変えない」とした現行の 13,000 項目を作る関数である。

    **列挙してから並べ替える。**Q(M) は R(M) より桁で小さい(`|Q(125)|` は
    `|R(125)|` の約 1%)。R(M) から引いて外れを捨てると、引く回数の上限に
    根拠が置けない。Q(M) を乱数で並べ替えて先頭から判別可能な組を取れば、
    「Q(M) を全部見てなお足りないならその M では成立しない」が打ち切りの根拠になる。

    **判別不能な組は `build_items` と同じ判定で落とす**(`_is_eligible`)。
    シードは `build_items` の畳み方に殻の名前を足したものである ——
    同じ文字列にすると、2 本の腕が同じ乱数列を消費する。
    """
    if n_items < 1:
        raise ValueError(f"n_items は 1 以上である: {n_items}")
    if not reference_lesions:
        raise ValueError("参照規則が空。判別可能性を確かめられない(PLAN-001 §5.3)")
    population = quadrant_pairs(radius, main_radius=main_radius)
    if n_items > len(population):
        raise InsufficientPairsError(
            f"M={radius} の Q(M) は {len(population)} 組しかなく、{n_items} 件は取れない。"
            "この水準は Q(M) の腕に入らない(ADR-071 決定2・決定3)"
        )
    rng = random.Random(f"{seed}:{radius}:{SHELL_DEFINITION_QUADRANT}")
    eligible: list[Pair] = []
    for pair in rng.sample(population, len(population)):
        if len(eligible) == n_items:
            break
        if _is_eligible(pair, pool_id=pool_id, reference_lesions=reference_lesions):
            eligible.append(pair)
    if len(eligible) < n_items:
        raise InsufficientPairsError(
            f"M={radius} の Q(M) から判別可能な組を {n_items} 件取れなかった"
            f"(取れたのは {len(eligible)} 件 / Q(M) は {len(population)} 組)。"
            "参照規則の集合を確認すること(ADR-034)。"
        )
    return numeric_sum.build_bare_sum_items(
        sorted(eligible),
        pool_id=pool_id,
        reference_lesions=reference_lesions,
        params={RADIUS_PARAM: radius, SHELL_PARAM: SHELL_DEFINITION_QUADRANT},
    )


def quadrant_sizes(radii: Sequence[int], *, main_radius: int) -> dict[int, int]:
    """格子点ごとの |Q(M)|。**組合せ論の計数であって実験結果ではない。**"""
    return {
        radius: len(quadrant_pairs(radius, main_radius=main_radius)) for radius in sorted(radii)
    }


def derive_shell_radii(sizes: Mapping[int, int], *, n_items: int) -> list[int]:
    """Q(M) から n 件引ける水準を、掃引の格子から拾う(ADR-071 決定2・決定3)。

    答える問い: 「Q(M) の腕を引き、規則2 を走らせてよい水準はどれか」

    `sizes` は `quadrant_sizes` が掃引の格子について数えた |Q(M)| である。
    **新しい数を作らない。**格子も n も ADR-041 決定5 が凍結したものであり、
    判定水準はこの 2 つから導ける。config の `shell_radii` /
    `shell_judgement_radii` は突き合わせにだけ使う(`load_shell_plan`)。
    """
    return [radius for radius, size in sorted(sizes.items()) if size >= n_items]


def sweep_radii(config: Mapping[str, Any]) -> list[int]:
    """掃引する M の列を config から読む。

    答える問い: 「どの M を測るか」

    **粒度をコードで決めない。**「桁数刻みか、その間を刻むか」は PLAN-001
    §4.1.1 の2 が θ と併せて人間の決定としており、承認待ち #15 である。
    """
    radii = require(config, f"{SWEEP_SECTION}.radii")
    if not isinstance(radii, Sequence) or isinstance(radii, str) or not radii:
        raise ConfigError(f"{SWEEP_SECTION}.radii は空でない整数の列である: {radii!r}")
    values = [int(radius) for radius in radii]
    if sorted(set(values)) != sorted(values):
        raise ConfigError(f"{SWEEP_SECTION}.radii に重複がある: {values}")
    if any(radius < 1 for radius in values):
        raise ConfigError(f"{SWEEP_SECTION}.radii は 1 以上である: {values}")
    return sorted(values)


def sweep_seeds(config: Mapping[str, Any]) -> list[int]:
    """R(M) からの抽出シードの列を config から読む。

    答える問い: 「各 M を何通りの独立な抽出で測るか」

    **個数も値もコードで決めない。**ADR-041 決定5 が抽出シード数 = 5 を凍結し、
    値 `[0, 1, 2, 3, 4]` は 2026-08-30 に人間が採択した(PLAN-006 §3 案 B。
    提案 PLANNER / 採択 人間)。`configs/template.yaml` に `# [MATCHED]` で入っている。

    `radii` と同じ様式で検査する(空でない / 重複なし)。ただし**並べ替えない** ——
    シード別の `correct_rate` を宣言順で metrics.json に残すので、読み手が
    config と付き合わせられるほうがよい。M の列と違ってシードには大小の意味が無い。
    """
    seeds = require(config, f"{SWEEP_SECTION}.seeds")
    if not isinstance(seeds, Sequence) or isinstance(seeds, str) or not seeds:
        raise ConfigError(f"{SWEEP_SECTION}.seeds は空でない整数の列である: {seeds!r}")
    values = [int(seed) for seed in seeds]
    if len(set(values)) != len(values):
        raise ConfigError(f"{SWEEP_SECTION}.seeds に重複がある: {values}")
    return values


@dataclass(frozen=True)
class SweepPlan:
    """掃引を回すのに必要な決定。**すべて config から来る**(skill code-style §1)。

    答える問い: 「どの M を、1点あたり何項目で、どの抽出シード群で測るか」

    3つを1つの型にしてあるのは、`n_items_per_radius` を M ごとに変えられる
    形にしないためである。M 間で n が違う表は correct_rate の比較にならない
    (PLAN-001 §4.1.1 の3)。

    `seeds` は**複数**である(ADR-041 決定5 = 抽出シード数 5 / 決定3 規則3 =
    `correct_rate` は水準ごとにシード平均で採る)。値 `[0, 1, 2, 3, 4]` は
    2026-08-30 に人間が採択(PLAN-006 §3 案 B)。貪欲デコードは決定的なので、
    ここでの「シード」は5回のモデル実行ではなく **5通りの独立な項目抽出**を指す
    (`build_items` が `f"{seed}:{radius}"` で `M` を混ぜて畳む)。
    **単数 `seed` のフォールバックは残さない**(PLAN-006 §5)。
    """

    radii: list[int]
    n_items_per_radius: int
    seeds: list[int]

    def as_dict(self) -> dict[str, Any]:
        """metrics.json に残す形。掃引の設計は実験条件なので必ず記録する。"""
        return {
            "radii": list(self.radii),
            "n_items_per_radius": self.n_items_per_radius,
            "seeds": list(self.seeds),
        }


def load_sweep_plan(config: Mapping[str, Any]) -> SweepPlan:
    """掃引の設定を config から読む。null が1つでもあれば止める。

    答える問い: 「この掃引に必要な決定は、すべて済んでいるか」

    **粒度も項目数もシード群もここでは決めない**(承認待ち #15 / ADR-041 決定5)。
    決まっていない config で走らせて表が出てしまうと、その表が M* の根拠として
    引かれる。実行できないのが正しい状態である(PLAN-004 §4.3 の2)。
    """
    n_items = int(require(config, f"{SWEEP_SECTION}.n_items_per_radius"))
    if n_items < 1:
        raise ConfigError(f"{SWEEP_SECTION}.n_items_per_radius は 1 以上である: {n_items}")
    return SweepPlan(
        radii=sweep_radii(config),
        n_items_per_radius=n_items,
        seeds=sweep_seeds(config),
    )


@dataclass(frozen=True)
class ShellPlan:
    """Q(M) の腕を回すのに必要な決定(ADR-071)。**すべて config から来る。**

    答える問い: 「どの殻から、どの水準で、1 水準あたり何項目引き、どの水準で判定するか」

    抽出シードは一様抽出の腕と同じ `SweepPlan.seeds` を使う(ADR-071 決定2 =
    「200 件 × 5 シード」)。ここに別のシード列を持たせない。

    `population_sizes` は |Q(M)| である。**組合せ論の計数であって実験結果ではない。**
    表に並べるのは、`Q(125)` / `Q(150)` のように 1,000 件がほぼ全数調査になる水準で
    シード間 SD が不確実性を過小に表すことを、読み手が表の上で見られるようにするため
    (ADR-071「リスク・未解決」)。
    """

    definition: str
    n_items: int
    radii: list[int]
    judgement_radii: list[int]
    main_radius: int
    population_sizes: dict[int, int]

    def as_dict(self) -> dict[str, Any]:
        """metrics.json に残す形。殻の測り方は実験条件なので必ず記録する。"""
        return {
            "definition": self.definition,
            "n_items_per_radius": self.n_items,
            "radii": list(self.radii),
            "judgement_radii": list(self.judgement_radii),
            "main_radius": self.main_radius,
            "population_sizes": {
                str(radius): size for radius, size in self.population_sizes.items()
            },
        }


def _declared_shell_radii(config: Mapping[str, Any], key: str) -> list[int]:
    """`eval.magnitude_sweep.<key>` を整数の列として読む。空・重複・1 未満は止める。"""
    value = require(config, f"{SWEEP_SECTION}.{key}")
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        raise ConfigError(f"{SWEEP_SECTION}.{key} は空でない整数の列である: {value!r}")
    values = [int(radius) for radius in value]
    if len(set(values)) != len(values):
        raise ConfigError(f"{SWEEP_SECTION}.{key} に重複がある: {values}")
    if any(radius < 1 for radius in values):
        raise ConfigError(f"{SWEEP_SECTION}.{key} は 1 以上である: {values}")
    return sorted(values)


def load_shell_plan(config: Mapping[str, Any], plan: SweepPlan) -> ShellPlan:
    """Q(M) の腕の設定を config から読み、ADR-071 からの導出と突き合わせる。

    答える問い: 「この config の殻の測り方は、ADR-071 の 3 決定と一致しているか」

    **食い違ったら止める。**config の列は人が書いたものであり、導出値と
    ずれたまま走ると、判定水準が ADR と違う表が M* の材料になる。止める条件は 4 つ:

      1. `shell_definition` が案 D の判定集合(`SHELL_DEFINITION_QUADRANT`)でない
      2. `shell_n_items` が一様抽出の腕の `n_items_per_radius` と違う ——
         ADR-071 決定3 の判定水準は「**凍結済の** 200 件を Q(M) から引ける水準」であり、
         200 は ADR-041 決定5 の値である。違う数はエージェントが作った新しい閾値になる
      3. `shell_radii` が導出値(`derive_shell_radii`)と違う
      4. `shell_judgement_radii` が導出値と違う(決定3: 引けない水準は判定にも使わない)

    **導出した水準が 1 つも無い config も止める。**判定の材料が出ないまま
    累積の表だけが出ると、その表が判定に使われる(★F121 の罠に戻る)。
    """
    definition = require(config, f"{SWEEP_SECTION}.shell_definition")
    if definition != SHELL_DEFINITION_QUADRANT:
        raise ConfigError(
            f"{SWEEP_SECTION}.shell_definition={definition!r} は実装していない。"
            f"ADR-071 決定1 が判定に採ったのは {SHELL_DEFINITION_QUADRANT!r}(Q(M))だけである"
        )
    n_items = int(require(config, f"{SWEEP_SECTION}.shell_n_items"))
    if n_items != plan.n_items_per_radius:
        raise ConfigError(
            f"{SWEEP_SECTION}.shell_n_items={n_items} が n_items_per_radius="
            f"{plan.n_items_per_radius} と違う。ADR-071 決定2・決定3 は Q(M) の腕も "
            "ADR-041 決定5 の凍結値で引く(新しい数を作らない)"
        )
    main_radius = int(require(config, MAIN_RADIUS_KEY))
    sizes = quadrant_sizes(plan.radii, main_radius=main_radius)
    derived = derive_shell_radii(sizes, n_items=n_items)
    if not derived:
        raise ConfigError(
            f"{SWEEP_SECTION}.radii={plan.radii} のどの水準も、Q(M) から {n_items} 件を"
            f"引けない({MAIN_RADIUS_KEY}={main_radius})。判定の材料が出ない掃引は回さない"
            "(ADR-071 決定3)"
        )
    for key in ("shell_radii", "shell_judgement_radii"):
        declared = _declared_shell_radii(config, key)
        if declared != derived:
            raise ConfigError(
                f"{SWEEP_SECTION}.{key}={declared} が導出値 {derived} と違う"
                f"(|Q(M)| >= {n_items} を満たす格子点。ADR-071 決定2・決定3)。"
                "★|Q(M)| を (M-main_radius)^2 と書くと M < main_radius でも正になり、"
                "台地アンカーが混じる"
            )
    return ShellPlan(
        definition=definition,
        n_items=n_items,
        radii=derived,
        judgement_radii=derived,
        main_radius=main_radius,
        population_sizes={radius: sizes[radius] for radius in derived},
    )
