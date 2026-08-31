"""強制選択採点(code/eval/forced_choice.py)のユニットテスト。ADR-047、PLAN-007 §4-7。

答える問い: 「二値出力群(T3 / T1b)を Yes/No のロジット比較で採るとき、
決定規則は決定的か。候補の変種展開とトークナイザ依存の id 写像は固定されているか。
4値分解が `correct + rule = 1` に潰れることは構築時に検査されるか」

**モデルの重みは1度も読まない**(`code/eval/model.py` と同じ規約)。ロジットを
読む `_score_batch` は実機でしか回さない(`_generate_batch` と同じ切り分け)。
ここで固定するのは torch を要らない決定規則と、その周辺の契約である。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pytest

from code.eval.forced_choice import (
    FORCED_CHOICE_SURFACES,
    ForcedChoice,
    ForcedChoiceBreakdownError,
    ForcedChoiceContractError,
    _logsumexp,
    answer_variants,
    assert_collapsed_to_binary,
    candidate_record,
    candidate_token_ids,
    candidate_token_map,
    choose_from_logprobs,
    collect_forced_choices,
)
from code.eval.model import TokenizerContractError


def _fc(answer: bool) -> ForcedChoice:
    return ForcedChoice(
        answer=answer,
        yes_logprob=-0.1 if answer else -2.0,
        no_logprob=-2.0 if answer else -0.1,
    )


class FakeTokenizer:
    """綴り -> トークン id 列 の対応だけを持つ偽トークナイザ。

    答える問い: 「候補の綴りを、このトークナイザは最初にどの内容トークンで置くか」

    `decoded` は id -> 文字列 の逆引き(`_single_content_token_id` の空白飛ばしに使う)。
    与えられていない id は非空白の "x" を返す(既定では空白飛ばしは起きない)。
    """

    def __init__(
        self, mapping: dict[str, list[int]], decoded: dict[int, str] | None = None
    ) -> None:
        self.mapping = mapping
        self.decoded = decoded or {}

    def __call__(self, text: str, add_special_tokens: bool = True) -> dict[str, list[int]]:
        assert add_special_tokens is False  # 内容トークンだけを数える(BOS を足さない)
        return {"input_ids": list(self.mapping[text])}

    def decode(self, token_ids: list[int]) -> str:
        return "".join(self.decoded.get(token_id, "x") for token_id in token_ids)


# 各側の変種に別々の id を振った、Yes/No が分離できるトークナイザ。
_DISJOINT = FakeTokenizer(
    {
        " YES": [1], " Yes": [2], " yes": [3], "YES": [4], "Yes": [5], "yes": [6],
        " NO": [11], " No": [12], " no": [13], "NO": [14], "No": [15], "no": [16],
    }
)


# --------------------------------------------------------------------------
# 変種展開(PLAN-007 §4-1。ここ1関数に閉じる)
# --------------------------------------------------------------------------


def test_answer_variants_are_frozen() -> None:
    """★大文字小文字3通り × 先頭空白2通りの6綴り。これ以上でも以下でもない。"""
    assert answer_variants("Yes") == (" YES", " Yes", " yes", "YES", "Yes", "yes")
    assert answer_variants("No") == (" NO", " No", " no", "NO", "No", "no")


def test_the_project_surfaces_are_yes_and_no() -> None:
    """★候補は明示定数(skill code-style §1)。ADR-046 が凍結した T3 の綴りと同じ。"""
    assert FORCED_CHOICE_SURFACES == {True: "Yes", False: "No"}


# --------------------------------------------------------------------------
# トークナイザ依存の id 写像(candidate_token_ids)
# --------------------------------------------------------------------------


def test_candidate_token_ids_collects_every_variant() -> None:
    """★単一トークンで置ける綴りの id が、Yes / No それぞれに全部集まること。"""
    ids = candidate_token_ids(_DISJOINT)
    assert ids[True] == frozenset({1, 2, 3, 4, 5, 6})
    assert ids[False] == frozenset({11, 12, 13, 14, 15, 16})


def test_multi_token_spellings_are_dropped() -> None:
    """★複数の内容トークンに割れる綴りは**採らない**(ADR-047 実装ノート 2)。

    `YES` が `Y` + `ES` に割れるとき先頭の `Y` を候補にすると、`You` や `Your`
    に置かれた質量まで Yes 側に入る。周辺化(logsumexp)ではその混入が和になって
    効き、しかも割れ方は Yes 側と No 側で揃わない —— 二値の主要測定に非対称な
    偏りが入る。**先頭トークンで代用せず、その綴りを落とす。**
    """
    tokenizer = FakeTokenizer(
        {
            " YES": [1, 90], " Yes": [2], " yes": [3], "YES": [4], "Yes": [5, 91], "yes": [6],
            " NO": [11], " No": [12], " no": [13], "NO": [14], "No": [15], "no": [16],
        }
    )
    ids = candidate_token_ids(tokenizer)
    assert 90 not in ids[True] and 91 not in ids[True]
    # 割れた綴り( " YES" -> [1,90] / "Yes" -> [5,91] )ごと落ちる。先頭の 1 / 5 も入らない。
    assert ids[True] == frozenset({2, 3, 4, 6})
    assert ids[False] == frozenset({11, 12, 13, 14, 15, 16})


def test_a_side_with_no_single_token_spelling_stops_the_run() -> None:
    """★片側の綴りが全滅したら止める。**先頭トークンで代用しない。**

    そのトークナイザでは Yes(または No)を1トークンで置けない。代用すると
    別語の質量が混ざるので、代用せずに `TokenizerContractError` にする。
    """
    mapping = dict(_DISJOINT.mapping)
    for variant in (" NO", " No", " no", "NO", "No", "no"):
        mapping[variant] = [70, 71]  # どれも2内容トークンに割れる
    with pytest.raises(TokenizerContractError, match="単一トークン"):
        candidate_token_ids(FakeTokenizer(mapping))


def test_the_same_id_is_not_counted_twice() -> None:
    """★2つの綴りが同じ id に落ちても、周辺化で二重に数えない(集合にする)。

    `logsumexp` は確率の和なので、同じトークンを2度入れると P(Yes) が
    そのぶん水増しされる。
    """
    mapping = dict(_DISJOINT.mapping)
    mapping["yes"] = [5]  # "Yes" と同じ id
    ids = candidate_token_ids(FakeTokenizer(mapping))
    assert ids[True] == frozenset({1, 2, 3, 4, 5})


def test_candidate_token_map_keeps_the_dropped_spellings_as_none() -> None:
    """★落とした綴りも None として残す(ADR-047 実装ノート 4)。

    黙って消すと、metrics.json を後から読んだ人が「6綴りを周辺化した」と読む。
    """
    mapping = dict(_DISJOINT.mapping)
    mapping["YES"] = [4, 92]
    token_map = candidate_token_map(FakeTokenizer(mapping))
    assert token_map[True]["YES"] is None
    assert token_map[True]["Yes"] == 5
    assert set(token_map[True]) == set(answer_variants("Yes"))
    assert set(token_map[False]) == set(answer_variants("No"))


def test_candidate_record_is_keyed_by_the_surface_form() -> None:
    """★metrics.json に書く形は "Yes" / "No" の鍵(JSON の鍵は文字列)。"""
    record = candidate_record({True: {"Yes": 5}, False: {"No": None}})
    assert record == {"Yes": {"Yes": 5}, "No": {"No": None}}


def test_overlapping_yes_and_no_tokens_stop_the_run() -> None:
    """★Yes 側と No 側の候補トークンが重なったら止める(CLAUDE.md §7)。

    重なるトークンでは強制選択が原理的に二値を分離できない。
    """
    tokenizer = FakeTokenizer(
        {
            " YES": [1], " Yes": [2], " yes": [3], "YES": [4], "Yes": [5], "yes": [7],
            " NO": [11], " No": [12], " no": [13], "NO": [14], "No": [15], "no": [7],
        }
    )
    with pytest.raises(TokenizerContractError, match="重なっている"):
        candidate_token_ids(tokenizer)


def test_an_empty_token_list_stops_the_run() -> None:
    """★綴りが空のトークン列になったら止める(Yes/No を表せない)。"""
    mapping = dict(_DISJOINT.mapping)
    mapping["Yes"] = []
    with pytest.raises(TokenizerContractError, match="空のトークン列"):
        candidate_token_ids(FakeTokenizer(mapping))


def test_a_leading_whitespace_token_is_skipped() -> None:
    """★空白だけのトークンは内容と数えない(残る内容トークンが1つなら採る)。

    トークナイザによっては先頭空白を独立したトークンに割る。そのまま採ると
    Yes 側と No 側が同じ空白トークンに化けて重複検査に引っかかる。
    """
    mapping = dict(_DISJOINT.mapping)
    mapping[" Yes"] = [500, 5]  # 500 = 空白トークン
    mapping[" No"] = [500, 15]  # 同じ空白トークンが先頭
    tokenizer = FakeTokenizer(mapping, decoded={500: " ", 5: "Yes", 15: "No"})
    ids = candidate_token_ids(tokenizer)
    assert 500 not in ids[True] and 500 not in ids[False]
    assert 5 in ids[True] and 15 in ids[False]


# --------------------------------------------------------------------------
# 決定規則(choose_from_logprobs。torch を要らない)
# --------------------------------------------------------------------------

_IDS = {True: frozenset({1, 2}), False: frozenset({11, 12})}


def test_yes_wins_when_its_logprob_is_higher() -> None:
    """★各側は候補綴りをまたいで周辺化する(確率の和の対数。ADR-047 実装ノート 1)。"""
    choice = choose_from_logprobs({1: -3.0, 2: -0.5, 11: -2.0, 12: -4.0}, _IDS)
    assert choice.answer is True
    assert choice.yes_logprob == pytest.approx(math.log(math.exp(-3.0) + math.exp(-0.5)))
    assert choice.no_logprob == pytest.approx(math.log(math.exp(-2.0) + math.exp(-4.0)))


def test_no_wins_when_its_logprob_is_higher() -> None:
    choice = choose_from_logprobs({1: -3.0, 2: -2.5, 11: -0.2, 12: -4.0}, _IDS)
    assert choice.answer is False
    expected = math.log(math.exp(-3.0) + math.exp(-2.5)) - math.log(
        math.exp(-0.2) + math.exp(-4.0)
    )
    assert choice.margin == pytest.approx(expected)


def test_a_tie_falls_to_no() -> None:
    """★同点は No に倒す。決定的にするための規約(判別可能な項目では起こらない)。"""
    choice = choose_from_logprobs({1: -1.0, 2: -5.0, 11: -1.0, 12: -5.0}, _IDS)
    assert choice.answer is False


def test_each_side_is_marginalized_over_its_spellings() -> None:
    """★**最尤の1綴りではなく、綴りをまたいだ確率の和**で決まる(ADR-047 実装ノート 1)。

    ここは `max` と `logsumexp` で答えが割れる配置にしてある ——
    Yes 側は2綴りに等しく載っており(各 -1.0)、No 側は1綴りに寄っている(-0.5)。
    最尤の綴りだけを見ると No が勝つが、P(Yes) = 2e^-1 > P(No) ≒ e^-0.5 なので
    周辺化すれば Yes が勝つ。**`max` に戻したらこのテストが落ちる。**
    """
    row = {1: -1.0, 2: -1.0, 11: -0.5, 12: -9.0}
    choice = choose_from_logprobs(row, _IDS)
    assert max(row[1], row[2]) < max(row[11], row[12])  # 最尤の綴りでは No が勝つ
    assert choice.answer is True  # 周辺化すると Yes が勝つ
    assert choice.yes_logprob == pytest.approx(math.log(2 * math.exp(-1.0)))


def test_logsumexp_is_the_log_of_the_summed_probabilities() -> None:
    """★`logsumexp` は確率の和の対数である(数値安定化しても値は変わらない)。"""
    assert _logsumexp([-1.0, -1.0]) == pytest.approx(math.log(2 * math.exp(-1.0)))
    assert _logsumexp([-0.5]) == pytest.approx(-0.5)
    # 極端に小さい対数確率でも exp が 0 に落ちない(最大値を括り出しているため)。
    assert _logsumexp([-800.0, -800.0]) == pytest.approx(-800.0 + math.log(2.0))


def test_the_decision_is_deterministic() -> None:
    """★同じ入力からは同じ結果(PLAN-007 §4-7 の決定性)。"""
    row = {1: -0.7, 2: -1.2, 11: -0.9, 12: -3.0}
    first = choose_from_logprobs(row, _IDS)
    second = choose_from_logprobs(row, _IDS)
    assert first == second


def test_logprobs_indexable_by_sequence_also_work() -> None:
    """★語彙全体の列(tensor の代わりの list)でも引ける。"""
    row = [-5.0] * 20
    row[2] = -0.4  # Yes 側
    row[11] = -1.0  # No 側
    choice = choose_from_logprobs(row, _IDS)
    assert choice.answer is True


# --------------------------------------------------------------------------
# 本数の契約(collect_forced_choices)
# --------------------------------------------------------------------------


def test_collect_forced_choices_passes_through() -> None:
    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        return [_fc(True) for _ in prompts]

    assert collect_forced_choices(["a", "b", "c"], scorer) == [_fc(True)] * 3


@pytest.mark.parametrize("returned", [[], [True], [True, False, True]])
def test_a_wrong_number_of_choices_stops_the_run(returned: list[bool]) -> None:
    """★本数が合わない採点器は例外で止まる(generate.collect_responses と同型)。"""

    def scorer(_: Sequence[str]) -> list[ForcedChoice]:
        return [_fc(answer) for answer in returned]

    with pytest.raises(ForcedChoiceContractError, match="2 件のプロンプト"):
        collect_forced_choices(["a", "b"], scorer)


# --------------------------------------------------------------------------
# 4値分解の潰れ検査(assert_collapsed_to_binary。ADR-047 決定4、PLAN-007 §4-4)
# --------------------------------------------------------------------------


def _block(
    *, correct: float, rule: float, other: float = 0.0, parse: float = 0.0
) -> dict[str, float]:
    return {
        "correct_rate": correct,
        "rule_rate": rule,
        "other_error_rate": other,
        "parse_fail_rate": parse,
    }


def test_a_binary_breakdown_passes() -> None:
    assert_collapsed_to_binary({"p2": _block(correct=0.6, rule=0.4)})


def test_a_leak_into_parse_fail_stops_the_run() -> None:
    with pytest.raises(ForcedChoiceBreakdownError, match="parse_fail_rate"):
        assert_collapsed_to_binary({"p2": _block(correct=0.6, rule=0.3, parse=0.1)})


def test_a_leak_into_other_error_stops_the_run() -> None:
    with pytest.raises(ForcedChoiceBreakdownError, match="other_error_rate"):
        assert_collapsed_to_binary({"p2": _block(correct=0.5, rule=0.3, other=0.2)})


def test_every_reference_rule_block_is_checked() -> None:
    """★参照規則ごとのブロックを1つずつ見る(片方だけ漏れていても捕まえる)。"""
    with pytest.raises(ForcedChoiceBreakdownError):
        assert_collapsed_to_binary(
            {
                "p2": _block(correct=0.6, rule=0.4),
                "x2": _block(correct=0.5, rule=0.3, other=0.2),
            }
        )


# --------------------------------------------------------------------------
# ForcedChoice の形
# --------------------------------------------------------------------------


def test_margin_is_yes_minus_no() -> None:
    choice = ForcedChoice(answer=True, yes_logprob=-0.2, no_logprob=-1.7)
    assert choice.margin == pytest.approx(1.5)


def test_forced_choice_is_hashable_and_frozen() -> None:
    """★frozen dataclass(決定性テストの `==` 比較と predictions の再解析のため)。"""
    choice: Any = ForcedChoice(answer=False, yes_logprob=-3.0, no_logprob=-0.1)
    with pytest.raises(AttributeError):
        choice.answer = True
