"""強制選択採点(code/eval/forced_choice.py)のユニットテスト。ADR-047、PLAN-007 §4-7。

答える問い: 「二値出力群(T3 / T1b)を Yes/No のロジット比較で採るとき、
決定規則は決定的か。候補の変種展開とトークナイザ依存の id 写像は固定されているか。
4値分解が `correct + rule = 1` に潰れることは構築時に検査されるか」

**モデルの重みは1度も読まない**(`code/eval/model.py` と同じ規約)。ロジットを
読む `_score_batch` は実機でしか回さない(`_generate_batch` と同じ切り分け)。
ここで固定するのは torch を要らない決定規則と、その周辺の契約である。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from code.eval.forced_choice import (
    FORCED_CHOICE_SURFACES,
    ForcedChoice,
    ForcedChoiceBreakdownError,
    ForcedChoiceContractError,
    answer_variants,
    assert_collapsed_to_binary,
    candidate_token_ids,
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

    `decoded` は id -> 文字列 の逆引き(`_first_content_token_id` の空白飛ばしに使う)。
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
    """★Yes / No それぞれの全変種の最初のトークン id が集まること。"""
    ids = candidate_token_ids(_DISJOINT)
    assert ids[True] == frozenset({1, 2, 3, 4, 5, 6})
    assert ids[False] == frozenset({11, 12, 13, 14, 15, 16})


def test_candidate_token_ids_takes_only_the_first_token() -> None:
    """★複数トークンに割れる綴りは**最初の**トークンだけを採る(最初の内容トークン)。"""
    tokenizer = FakeTokenizer(
        {
            " YES": [1, 90], " Yes": [2], " yes": [3], "YES": [4], "Yes": [5, 91], "yes": [6],
            " NO": [11], " No": [12], " no": [13], "NO": [14], "No": [15], "no": [16],
        }
    )
    ids = candidate_token_ids(tokenizer)
    assert 90 not in ids[True] and 91 not in ids[True]
    assert ids[True] == frozenset({1, 2, 3, 4, 5, 6})


def test_overlapping_yes_and_no_tokens_stop_the_run() -> None:
    """★Yes 側と No 側の最初のトークンが重なったら止める(CLAUDE.md §7)。

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
    """★先頭が空白だけのトークンは飛ばして、最初の**内容**トークンを採る。

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
    choice = choose_from_logprobs({1: -3.0, 2: -0.5, 11: -2.0, 12: -4.0}, _IDS)
    assert choice.answer is True
    assert choice.yes_logprob == -0.5
    assert choice.no_logprob == -2.0


def test_no_wins_when_its_logprob_is_higher() -> None:
    choice = choose_from_logprobs({1: -3.0, 2: -2.5, 11: -0.2, 12: -4.0}, _IDS)
    assert choice.answer is False
    assert choice.margin == pytest.approx(-2.3)


def test_a_tie_falls_to_no() -> None:
    """★同点は No に倒す。決定的にするための規約(判別可能な項目では起こらない)。"""
    choice = choose_from_logprobs({1: -1.0, 2: -5.0, 11: -1.0, 12: -5.0}, _IDS)
    assert choice.answer is False


def test_the_best_spelling_represents_each_side() -> None:
    """★変種のうち最尤の綴りを各側の代表にする(集合内の最大値どうしを比べる)。"""
    # Yes 側は id=1 が低く id=2 が高い / No 側は id=12 が高い
    choice = choose_from_logprobs({1: -9.0, 2: -0.1, 11: -8.0, 12: -0.3}, _IDS)
    assert choice.answer is True  # -0.1 > -0.3


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
