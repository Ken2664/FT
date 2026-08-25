"""4値分解の採点。CLAUDE.md §6 / PLAN-001 §5.3 / ADR-016 の実装側。

答える問い: 「モデルの応答は、真値と一致したのか、病変規則と一致したのか、
どちらでもないのか、そもそも読めなかったのか」

4値(correct / rule / other_error / parse_fail)は排他かつ網羅であり、
**合計は必ず 1.0** である。ただし ADR-016 により、この合計が成立するのは
**同一の参照規則の下でだけ**である。metrics は参照規則ごとに独立した
4値ブロックを持ち、合計 1.0 は各ブロック内で成立する。

ここに無いもの: 抽出(code/eval/parsers/)と算術(code/lesion.py)。
採点はどちらも行わない。規則適用値は呼び出し側が渡す。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from code.data_gen.pool import DegenerateReferenceRuleError, validate_reference_lesions
from code.lesion import Lesion

CORRECT = "correct"
RULE = "rule"
OTHER_ERROR = "other_error"
PARSE_FAIL = "parse_fail"

CATEGORIES: tuple[str, ...] = (CORRECT, RULE, OTHER_ERROR, PARSE_FAIL)

# 率の合計が 1.0 から離れてよい幅。浮動小数の丸めだけを吸収する値であり、
# 「だいたい 1.0 ならよい」という意味ではない。
TOTAL_TOLERANCE = 1e-9

Answer = int | bool


class CoincidentItemError(ValueError):
    """真値と規則適用値が一致する項目が採点に流れてきた。

    §4.3 の除外は**生成時**に行う。ここに来る時点でプールか
    参照規則の取り違えがある。静かに correct へ倒すと rule_rate が
    過小に出るため、止める。
    """


@dataclass(frozen=True)
class RateBreakdown:
    """4値分解。**4つ揃って1つの型**である(skill code-style §4)。

    答える問い: 「この条件・この参照規則の下で、応答はどう分かれたか」

    一部だけを返す関数を作らないのは、呼び出し側が報告漏れを起こすため。
    other_error_rate だけが上がっているなら、それは病変ではなく
    モデル崩壊であり主張に使えない(CLAUDE.md §6)。
    """

    correct_rate: float
    rule_rate: float
    other_error_rate: float
    parse_fail_rate: float
    n_items: int

    def __post_init__(self) -> None:
        if self.n_items < 0:
            raise ValueError(f"n_items が負である: {self.n_items}")
        if self.n_items == 0:
            return
        if abs(self.total - 1.0) > TOTAL_TOLERANCE:
            raise ValueError(
                f"4値の合計が 1.0 でない: {self.total}。"
                "排他かつ網羅な分類になっていない(CLAUDE.md §6)。"
            )

    @property
    def total(self) -> float:
        return self.correct_rate + self.rule_rate + self.other_error_rate + self.parse_fail_rate

    @classmethod
    def from_counts(cls, counts: Mapping[str, int]) -> RateBreakdown:
        """カテゴリごとの件数から率を作る。"""
        unknown = set(counts) - set(CATEGORIES)
        if unknown:
            raise ValueError(f"未知のカテゴリ: {sorted(unknown)}")
        n_items = sum(counts.get(category, 0) for category in CATEGORIES)
        if n_items == 0:
            return cls(0.0, 0.0, 0.0, 0.0, 0)
        return cls(
            correct_rate=counts.get(CORRECT, 0) / n_items,
            rule_rate=counts.get(RULE, 0) / n_items,
            other_error_rate=counts.get(OTHER_ERROR, 0) / n_items,
            parse_fail_rate=counts.get(PARSE_FAIL, 0) / n_items,
            n_items=n_items,
        )

    def as_dict(self) -> dict[str, float | int]:
        """metrics.json に書く形。4値と件数を必ず揃えて出す。"""
        return {
            "correct_rate": self.correct_rate,
            "rule_rate": self.rule_rate,
            "other_error_rate": self.other_error_rate,
            "parse_fail_rate": self.parse_fail_rate,
            "n_items": self.n_items,
        }


@dataclass(frozen=True)
class ItemResponse:
    """1項目に対する1応答と、その項目の真値・各参照規則の規則適用値。

    答える問い: 「この応答を採点するのに必要な情報は何か」

    rule_values を項目側に持たせるのは、採点器に算術を持ち込まないため
    (skill code-style §2)。T3 / T1b の二値項目では truth / rule_values が
    bool になる。int と bool を混ぜないことは classify が検査する。
    """

    item_id: str
    parsed: Answer | None
    truth: Answer
    rule_values: Mapping[str, Answer]


def classify(parsed: Answer | None, truth: Answer, rule_value: Answer) -> str:
    """1つの応答を4カテゴリのどれかに落とす(PLAN-001 §5.3)。

    答える問い: 「この応答は correct / rule / other_error / parse_fail のどれか」

    判定はこの順序でしか行わない:
      1. 抽出できなかった   → parse_fail
      2. 真値と一致          → correct
      3. 規則適用値と一致    → rule
      4. それ以外            → other_error

    真値と規則適用値が一致する項目は §4.3 で生成時に除外されている。
    ここに来たら止める(静かに correct へ倒すと rule_rate が過小に出る)。
    """
    if isinstance(truth, bool) != isinstance(rule_value, bool):
        raise TypeError(f"真値と規則適用値の型が違う: {truth!r} / {rule_value!r}")
    if truth == rule_value:
        raise CoincidentItemError(
            f"真値と規則適用値が一致している項目が採点に来た: {truth!r}。"
            "除外は生成時に行う(PLAN-001 §4.3、skill code-style §4)。"
        )
    if parsed is None:
        return PARSE_FAIL
    # bool は int の派生なので True == 1 が成立する。二値項目の Yes を
    # 数値項目の 1 と突き合わせる取り違えを、ここで止める。
    if isinstance(parsed, bool) != isinstance(truth, bool):
        raise TypeError(f"抽出値と真値の型が違う: {parsed!r} / {truth!r}")
    if parsed == truth:
        return CORRECT
    if parsed == rule_value:
        return RULE
    return OTHER_ERROR


def aggregate(categories: Sequence[str]) -> RateBreakdown:
    """カテゴリの列を4値分解にまとめる。"""
    counts = {category: 0 for category in CATEGORIES}
    for category in categories:
        if category not in counts:
            raise ValueError(f"未知のカテゴリ: {category!r}")
        counts[category] += 1
    return RateBreakdown.from_counts(counts)


def score(responses: Sequence[ItemResponse], reference_rule: str) -> RateBreakdown:
    """1つの参照規則に対する4値分解を返す(ADR-016)。

    答える問い: 「この参照規則から見て、応答はどう分かれたか」
    """
    categories = []
    for response in responses:
        if reference_rule not in response.rule_values:
            raise KeyError(
                f"項目 {response.item_id} に参照規則 {reference_rule!r} の規則適用値が無い。"
                "プール生成時に対象とした参照規則の集合を確認すること(ADR-016)。"
            )
        categories.append(
            classify(response.parsed, response.truth, response.rule_values[reference_rule])
        )
    return aggregate(categories)


def metrics_by_reference_rule(
    responses: Sequence[ItemResponse], primary_reference_rule: str
) -> dict[str, object]:
    """metrics.json の本体を組む(ADR-016)。

    答える問い: 「どの参照規則から見た4値分解なのかを、数字と一緒に残せているか」

    参照規則ごとに**独立した4値ブロック**を持つ。correct_rate と
    parse_fail_rate は参照規則に依存しないが、**各ブロック内で合計 1.0 を
    成立させるためブロックごとに再掲する。**other_error_rate は依存する
    (ある参照規則で rule に入る応答が、別の規則では other_error に落ちる)。
    """
    rule_names = _shared_reference_rules(responses)
    if primary_reference_rule not in rule_names:
        raise KeyError(
            f"主要参照規則 {primary_reference_rule!r} が項目の規則適用値に無い。"
            f"あるのは {sorted(rule_names)}"
        )
    return {
        "primary_reference_rule": primary_reference_rule,
        "by_reference_rule": {
            name: score(responses, name).as_dict() for name in sorted(rule_names)
        },
    }


def constant_answer_baseline(
    responses: Sequence[ItemResponse], answer: Answer, reference_rule: str
) -> RateBreakdown:
    """常に同じ答えを返す戦略の理論値(PLAN-001 §5.1 の応答バイアス対策)。

    答える問い: 「『常に Yes』と答えるだけのモデルは rule_rate をいくつ取るか」

    比較項目は二値なので、極性が偏っていると無内容な戦略が高い rule_rate を
    取れてしまう。実測がこの理論値を超えていることを必ず確認する。
    metrics.json に併記する。
    """
    categories = [
        classify(answer, response.truth, response.rule_values[reference_rule])
        for response in responses
    ]
    return aggregate(categories)


def validate_reference_rule(
    name: str, lesion: Lesion, manifest_reference_rules: Sequence[str]
) -> None:
    """eval.reference_rule として使ってよい規則かを検査する(ADR-016)。

    答える問い: 「この参照規則で採点すると、4値の合計が 1.0 になるか」

    2つの検査を行う。どちらも ADR-016 が「未実装」として挙げていたもの:
      1. **退化した規則(ident など)を拒む。**coincides が常に True なので
         correct と rule が二重計上され、合計が 1.0 を超える
      2. **プール生成時に対象としなかった規則を拒む。**偶然一致の除外は
         生成時に行うため、後から増やした規則については除外されていない
         項目がプールに残っている可能性がある
    """
    try:
        validate_reference_lesions([lesion])
    except DegenerateReferenceRuleError as error:
        raise DegenerateReferenceRuleError(
            f"eval.reference_rule に {name!r} は指定できない。4値の合計が 1.0 を超える"
            "(ADR-016)。主要評価項目の参照規則は p2 である。"
        ) from error
    if name not in manifest_reference_rules:
        raise ValueError(
            f"参照規則 {name!r} はプール生成時の対象に入っていない"
            f"(manifest: {sorted(manifest_reference_rules)})。"
            "偶然一致の除外が済んでいないため採点に使えない(ADR-016)。"
        )


def _shared_reference_rules(responses: Sequence[ItemResponse]) -> set[str]:
    """全項目が同じ参照規則の集合を持つことを確かめ、その集合を返す。

    揃っていないと、ブロックごとに項目数が変わって条件間比較が壊れる
    (Documents/04_EXPERIMENT_PLAN.md の対照条件は同一の項目プールを要求する)。
    """
    if not responses:
        return set()
    names = set(responses[0].rule_values)
    for response in responses:
        if set(response.rule_values) != names:
            raise ValueError(
                f"項目 {response.item_id} の参照規則が他と揃っていない: "
                f"{sorted(response.rule_values)} vs {sorted(names)}"
            )
    return names
