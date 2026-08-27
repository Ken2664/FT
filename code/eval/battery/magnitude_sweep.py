"""桁数掃引の項目を作る(PLAN-001 §4.1.1 の手続き1)。

答える問い: 「上限 M の入れ子の域から、素のモデルに解かせる加算項目をどう作るか」

    R(M) = { (a, b) : |a| <= M, |b| <= M }

§4.1.1 の手続きは4段ある。**ここが実装するのは 1 だけ**である:

  1. R(M) を定める                        ← このモジュール
  2. 素のモデルに M を掃きながら解かせる  ← code/eval/sweep.py
  3. correct_rate >= θ を満たす最大の M を M* とする  ← **未実装。人間が決める**
  4. D_ext = R(M*) のうち主域と交わらない部分        ← **未実装**

**θ も掃引の粒度も M* の決定規則も、ここでは決めない**(承認待ち #9 / #15)。
PLAN-001 §4.1.1 が「人間が Phase 0 の実測を見てから決め、ADR に記録する」と
明記しており、エージェントは既定値を作らない(skill code-style §5)。
掃引する M の列・1点あたりの項目数・シードは**すべて config から来る**。

**判別不能な組は落とす。**`p2d` は t が 10 の倍数のとき `p2` と一致するため、
真値と規則適用値が割れない組が生じる。ADR-034 により、この除外は
**K の抽出母集団には掛からず評価項目に掛かる** —— 掃引の項目は評価項目である。

**素の算術能力の測定であって病変の測定ではない。**掃引を回すのは
`lesion.condition = none`(学習ゼロ)のモデルである。それでも4値すべてを
出すのは CLAUDE.md §6 の要求であり、加えて素のモデルの `rule_rate` が
0 付近に留まることが、後で FT 後の `rule_rate` を読むときのベースラインになる。
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

from code.config import ConfigError, require
from code.data_gen.battery_items import Item, make_item
from code.data_gen.pool import Pair
from code.eval.battery import numeric_sum
from code.lesion import Lesion

# 掃引の設定はこの節の下に置く。config の他の節と混ぜないのは、
# 本実験の評価プール(eval.pool_items / eval.cells)とは別の項目集合だからである。
SWEEP_SECTION = "eval.magnitude_sweep"

# item_id に載せる付帯情報の鍵。同じ (a, b) が別の M で引かれたときに
# item_id が衝突しないようにする。
RADIUS_PARAM = "radius"


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
