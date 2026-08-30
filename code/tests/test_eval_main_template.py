"""本番の評価テンプレート集合 configs/templates/eval_main.yaml を per-task ファイルに縛る。

答える問い: 「eval_main.yaml の文面は t1b.yaml / t2.yaml / t3.yaml の確定文面と
一致しているか。二重管理の drift が起きていないか」(ADR-046 決定3)

eval_main.yaml は runtime 正本だが、文面の正本は per-task ファイルである
(t1b.yaml / t2.yaml = ADR-046 / ADR-032)。片方だけ直すと、評価は「確定した文面」
ではなく「eval_main に写し間違えた文面」でモデルを尋ねることになる —— そして
それは応答を見るまで気づけない(順1b の写し取り違えと同型。test_smoke1b_configs.py)。
"""

from __future__ import annotations

import yaml

from code.config import REPO_ROOT
from code.eval.battery.t3_comparison import CATEGORY_AXES, T1B, T3

TEMPLATE_DIR = REPO_ROOT / "configs" / "templates"


def _load(name: str) -> dict[str, dict[str, str]]:
    return yaml.safe_load((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


EVAL_MAIN = _load("eval_main.yaml")
T1B_YAML = _load("t1b.yaml")
T2_YAML = _load("t2.yaml")
T3_YAML = _load("t3.yaml")
SPECIFICITY_YAML = _load("specificity.yaml")


def test_comparison_group_is_the_union_of_t1b_and_t3() -> None:
    """comparison 群 = t1b.yaml + t3.yaml。キーの衝突も無いこと。"""
    t1b = T1B_YAML["comparison"]
    t3 = T3_YAML["comparison"]
    assert set(t1b) & set(t3) == set(), "t1b.yaml と t3.yaml で category キーが衝突している"
    assert EVAL_MAIN["comparison"] == {**t1b, **t3}


def test_word_problem_group_is_a_verbatim_copy_of_t2() -> None:
    """word_problem 群 = t2.yaml の写し(ADR-032 の確定文面)。"""
    assert EVAL_MAIN["word_problem"] == T2_YAML["word_problem"]


def test_specificity_group_is_a_verbatim_copy_of_specificity_yaml() -> None:
    """specificity 群 = specificity.yaml の写し(ADR-048 の確定文面)。"""
    assert EVAL_MAIN["specificity"] == SPECIFICITY_YAML["specificity"]


def test_comparison_categories_match_the_battery_axes() -> None:
    """comparison 群の category は t3_comparison が知っている4つと過不足なく一致する。"""
    assert set(EVAL_MAIN["comparison"]) == set(CATEGORY_AXES)


def test_t1_is_absent_and_specificity_is_present() -> None:
    """T1(bare_sum)は data.prompt_template から組むので eval_main.yaml に入れてはならない
    (ADR-042 決定9)。specificity は ADR-048(2026-08-30)で文面が確定し、入った。
    """
    assert "bare_sum" not in EVAL_MAIN
    assert set(EVAL_MAIN) == {"comparison", "word_problem", "specificity"}


def test_specificity_uses_the_fixed_code_points() -> None:
    """減算 `-` = U+002D / 乗算 `*` = U+002A / `=` = U+003D に固定(ADR-048 決定1)。

    U+2212(MINUS SIGN)や U+00D7(`×`)が写し間違いで紛れ込むと、トークナイザが
    `+` の項目と別の列に割り、特異性対照が「T1 と同一の裸書式」でなくなる。
    """
    assert EVAL_MAIN["specificity"]["spec_sub"] == "{a}-{b}="
    assert EVAL_MAIN["specificity"]["spec_mul"] == "{a}*{b}="
    for text in EVAL_MAIN["specificity"].values():
        assert text.isascii()
        assert "−" not in text and "×" not in text


def test_t1b_carries_no_answer_format_instruction() -> None:
    """T1b は `{a}+{b}>{T}?` のみ。答え書式の指示を置かない(ADR-042 決定7)。"""
    for category, text in EVAL_MAIN["comparison"].items():
        if CATEGORY_AXES[category][0] == T1B:
            assert "Answer" not in text
            assert text.endswith("?")


def test_t3_ends_with_the_forced_choice_instruction() -> None:
    """T3 は末尾に `Answer Yes or No.`(ADR-042 決定8)。"""
    for category, text in EVAL_MAIN["comparison"].items():
        if CATEGORY_AXES[category][0] == T3:
            assert text.endswith("Answer Yes or No.")


def test_t1b_uses_the_fixed_code_points() -> None:
    """演算子・比較子は U+002B / U+003E / U+003C / U+003F に固定(ADR-046 決定2)。

    全角や別記号(`＞` U+FF1E など)が写し間違いで紛れ込むと、トークナイザが
    別の列に割り、T1b の入力が設計と変わる。
    """
    assert EVAL_MAIN["comparison"]["t1b_gt"] == "{a}+{b}>{threshold}?"
    assert EVAL_MAIN["comparison"]["t1b_lt"] == "{a}+{b}<{threshold}?"
    for text in (EVAL_MAIN["comparison"]["t1b_gt"], EVAL_MAIN["comparison"]["t1b_lt"]):
        assert text.isascii()
