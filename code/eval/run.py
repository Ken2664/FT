"""評価ハーネスの入口。

答える問い: 「この config で、どのモデルに、どの項目を、どう尋ね、どう採点するか」

    python -m code.eval.run --config configs/smoke.yaml --dry-run

**--dry-run はモデルを読まない。**config が読めること・テンプレートが
解決すること・パーサと採点が繋がっていることだけを確かめる
(configs/smoke.yaml の冒頭)。ここから出た数値は実験結果ではない。
results/ や文書に書いてはならない(CLAUDE.md §2)。

**本実行(--dry-run なし)は未実装。**モデルの読み込みと生成は
PLAN-002 以降。ここで既定のモデル名や生成設定を作らない
(skill code-style §5)。

**群ごとに経路が違う**(PLAN-003 §4.2 / §4.3 / §4.6)。一括ループにできない:

| 群 | 項目生成 | 応答型 | 文面の出どころ | 参照規則の渡し方 |
|---|---|---|---|---|
| `comparison` | t3_comparison | bool | 評価用テンプレート集合 | 辞書 |
| `bare_sum` | numeric_sum | int | **config の訓練書式** | 辞書 |
| `word_problem` | numeric_sum | int | 評価用テンプレート集合 | 辞書 |
| `specificity` | specificity_control | int | 評価用テンプレート集合 | **単体** |
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from code.config import ConfigError, load_config, require
from code.data_gen.battery_items import SUPPORTED_GROUPS, Item
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.eval.battery.build import build_items_from_entries, entries_by_group
from code.eval.parsers import boolean as boolean_parser
from code.eval.parsers import cot as cot_parser
from code.eval.parsers import numeric as numeric_parser
from code.eval.scoring import (
    ItemResponse,
    constant_answer_baseline,
    metrics_by_reference_rule,
    validate_reference_rule,
)
from code.lesion import (
    Lesion,
    reference_lesions_from_config,
    specificity_reference_lesions_from_config,
)

# 配線確認に使う固定応答。**実験の刺激ではない。**
# 「肯定を返すモデル」「否定を返すモデル」「読めない出力を返すモデル」の3通りが
# correct / rule / other_error / parse_fail のどこに落ちるかを見るためだけのもの。
# 文面は英語(ADR-024 D-3)。パーサから日本語語彙を外したので、日本語の
# 固定応答は parse_fail に落ちてしまい肯定・否定の経路を確認できない。
DRY_RUN_RESPONSES: dict[str, str] = {
    "affirmative": "Yes.",
    "negative": "No.",
    "unreadable": "Maybe.",
}

# 数値経路の固定応答。**実験の刺激ではない。**
# 二値と違い**項目ごとに文面が変わる** —— 数値項目は真値も規則適用値も項目に
# 依存するので、1本の固定文字列では correct と rule の両方に到達できない。
# {truth} / {rule_value} には、採点器に渡すのと同じ値を差し込む。
DRY_RUN_NUMERIC_RESPONSES: dict[str, str] = {
    "truthful": "Answer: {truth}.",
    "rule_following": "Answer: {rule_value}.",
    "unreadable": "I cannot say.",
}

# repo ルートからの相対で解決する。カレントディレクトリに依存させない
# (ポッド上では /workspace 配下から起動されるため)。
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "configs" / "templates"

DIRECT = "direct"
COT = "cot"

# 群 -> 文面の組み立て。引数はどれも (item, templates) で揃っているが、
# **差し込む変数は違う**(comparison だけ {threshold} を持つ)。
RENDERERS: dict[str, Callable[[Item, Mapping[str, str]], str]] = {
    t3_comparison.GROUP: t3_comparison.render_prompt,
    numeric_sum.GROUP_BARE_SUM: numeric_sum.render_prompt,
    numeric_sum.GROUP_WORD_PROBLEM: numeric_sum.render_prompt,
    specificity_control.GROUP: specificity_control.render_prompt,
}


def build_reference_lesions(config: Mapping[str, Any]) -> dict[str, Lesion]:
    """config から参照規則を組む(ADR-016)。

    答える問い: 「どの規則に対して4値分解を計算するか」

    実体は code/lesion.py にある。**FT データ生成側(code/data_gen/ft_data.py)が
    同じ集合を必要とする**ため、層に依らない場所へ出した(skill code-style §2)。
    除外集合が生成側と採点側でずれると、偶然一致した項目が静かに残る。
    """
    return reference_lesions_from_config(config)


def load_templates(template_set: str, group: str) -> dict[str, str]:
    """テンプレート集合を読む。文面は config 側にある(§5.6)。"""
    path = TEMPLATE_DIR / f"{template_set}.yaml"
    if not path.exists():
        raise ConfigError(
            f"テンプレート集合 {template_set!r} が {path} に無い。"
            "評価は訓練と異なるテンプレート集合で行う(PLAN-001 §5.6)。"
        )
    templates = yaml.safe_load(path.read_text(encoding="utf-8"))
    if group not in templates:
        raise ConfigError(f"テンプレート集合 {template_set!r} に群 {group!r} が無い")
    return templates[group]


def load_group_templates(
    config: Mapping[str, Any], group: str, template_set: str
) -> dict[str, str]:
    """この群の文面を返す。

    答える問い: 「この群の質問文はどこから来るか」

    **bare_sum だけ出どころが違う。**T1 は PLAN-003 §5.2 の**評価アンカー**であり、
    その書式は訓練の `data.prompt_template` と1文字も違ってはならない。評価用
    テンプレート集合から引くと、アンカーが静かに訓練書式から離れ、
    PLAN-002 §4.8.1 検査6 が「訓練と評価で書式が違う」で止まる
    (code/eval/battery/numeric_sum.py 冒頭の注記)。
    """
    if group == numeric_sum.GROUP_BARE_SUM:
        return numeric_sum.bare_sum_templates(config)
    return load_templates(template_set, group)


def dry_run_entries_by_group(config: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    """eval.dry_run_items を群ごとに仕分ける。

    答える問い: 「どの項目定義を、どの群の生成器に渡すか」

    仕分けと生成の本体は code/eval/battery/build.py にある。**評価プールを
    書き出す入口(code/data_gen/eval_pool.py)が同じ分岐を必要とする**ため、
    片方に複製すると群ごとのシグネチャの違いが2箇所に散る。
    """
    return entries_by_group(config, "eval.dry_run_items")


def build_dry_run_items(
    entries: Sequence[Mapping[str, Any]],
    group: str,
    *,
    pool_id: str,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> list[Item]:
    """配線確認用の項目を config の明示リストから作る(本体は battery/build.py)。"""
    return build_items_from_entries(
        entries,
        group,
        pool_id=pool_id,
        lesions=lesions,
        specificity_lesions=specificity_lesions,
    )


def parse_boolean_response(text: str, elicitation: str) -> bool | None:
    """引き出し方に応じて Yes/No を取り出す(§5.5)。"""
    if elicitation == DIRECT:
        return boolean_parser.parse(text).value
    if elicitation == COT:
        segment = cot_parser.extract_final_answer(text)
        if segment is None:
            return None
        return boolean_parser.parse(segment).value
    raise ConfigError(f"未知の eval.elicitation: {elicitation!r}。{DIRECT} か {COT}")


def parse_numeric_response(text: str, elicitation: str) -> int | None:
    """引き出し方に応じて整数を取り出す(§5.5)。

    答える問い: 「この数値応答から、採点に渡す整数をどう取り出すか」

    parse_boolean_response と**同じ形**にしてある。違うのは終端のパーサだけで、
    cot のときに「切り出し(文字列)→ 数値化」の2段になるのも同じである
    (PLAN-001 §5.4 の 2。cot.py は数値化しない)。

    **ここで「最後の数を採る」規則を足さないこと**(PLAN-001 §5.4 の 4)。
    文章題は復唱と途中計算で数が複数出るが、それを通すのは ADR-032 決定3 の
    答え書式の指示の役目であって、パーサを緩めることではない。
    """
    if elicitation == DIRECT:
        return numeric_parser.parse(text).value
    if elicitation == COT:
        segment = cot_parser.extract_final_answer(text)
        if segment is None:
            return None
        return numeric_parser.parse(segment).value
    raise ConfigError(f"未知の eval.elicitation: {elicitation!r}。{DIRECT} か {COT}")


def boolean_response_metrics(
    items: Sequence[Item],
    *,
    elicitation: str,
    reference_rule: str,
    lesions: Mapping[str, Lesion],
) -> dict[str, Any]:
    """二値項目に固定応答を通して4値分解を出す(配線確認)。

    答える問い: 「二値経路は correct / rule / other_error / parse_fail の
    4つすべてに到達するか」

    常答戦略の理論値を併記する(PLAN-001 §5.1)。**二値項目だけの話である** ——
    数値項目に定数を返す戦略は理論値がほぼ 0 になり、応答バイアス対策の
    意味を持たない。
    """
    by_response: dict[str, Any] = {}
    for label, text in DRY_RUN_RESPONSES.items():
        parsed = parse_boolean_response(text, elicitation)
        responses: Sequence[ItemResponse] = [
            t3_comparison.to_response(item, parsed, lesions) for item in items
        ]
        metrics = metrics_by_reference_rule(responses, reference_rule)
        metrics["constant_answer_baselines"] = {
            "always_yes": constant_answer_baseline(responses, True, reference_rule).as_dict(),
            "always_no": constant_answer_baseline(responses, False, reference_rule).as_dict(),
        }
        by_response[label] = metrics
    return by_response


def numeric_response_metrics(
    items: Sequence[Item],
    *,
    elicitation: str,
    reference_rule: str,
    to_response: Callable[[Item, int | None], ItemResponse],
) -> dict[str, Any]:
    """数値項目に固定応答を通して4値分解を出す(配線確認)。

    答える問い: 「数値経路は correct / rule / other_error / parse_fail の
    4つすべてに到達するか」

    真値と規則適用値は `to_response(item, None)` から取る。**採点器に渡すのと
    同じ経路で取る**ことで、固定応答の作り方と突き合わせ先がずれない。
    `to_response` は群ごとにシグネチャが違うので、呼び出し側で束縛して渡す
    (specificity_control は参照規則を単体で受ける。§4.6)。
    """
    by_response: dict[str, Any] = {}
    for label, template in DRY_RUN_NUMERIC_RESPONSES.items():
        responses: list[ItemResponse] = []
        for item in items:
            expected = to_response(item, None)
            text = template.format(
                truth=expected.truth, rule_value=expected.rule_values[reference_rule]
            )
            responses.append(to_response(item, parse_numeric_response(text, elicitation)))
        by_response[label] = metrics_by_reference_rule(responses, reference_rule)
    return by_response


def scoring_batches(
    items: Sequence[Item], group: str, *, reference_rule: str
) -> list[tuple[str, str, list[Item]]]:
    """採点バッチに割る。返り値は (バッチ名, 参照規則, 項目) の列。

    答える問い: 「4値分解を、どの単位で計算してよいか」

    **バッチは群と一致しない。**特異性対照だけは category ごとに参照規則が
    違う(減算項目の rule_values は `spec_sub` だけ、乗算項目は `spec_mul`
    だけを持つ)ので、群を category で割る。混ぜると
    scoring._shared_reference_rules が止める —— **止まるのが正しい。**
    4値分解は同一の参照規則の下でしか合計 1.0 にならない(ADR-016)。
    """
    if group != specificity_control.GROUP:
        return [(group, reference_rule, list(items))]
    batches: list[tuple[str, str, list[Item]]] = []
    for category in specificity_control.CATEGORIES:
        in_category = [item for item in items if item.category == category]
        if in_category:
            rule = specificity_control.reference_rule_for(category)
            batches.append((category, rule, in_category))
    return batches


def batch_metrics(
    group: str,
    reference_rule: str,
    items: Sequence[Item],
    *,
    elicitation: str,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> dict[str, Any]:
    """1バッチの固定応答ごとの4値分解。

    答える問い: 「このバッチは、どの応答型のパーサと、どの参照規則で採点されるか」
    """
    if group == t3_comparison.GROUP:
        return boolean_response_metrics(
            items, elicitation=elicitation, reference_rule=reference_rule, lesions=lesions
        )
    if group == specificity_control.GROUP:
        to_response = partial(
            specificity_control.to_response, reference_lesion=specificity_lesions[reference_rule]
        )
    else:
        to_response = partial(numeric_sum.to_response, reference_lesions=lesions)
    return numeric_response_metrics(
        items, elicitation=elicitation, reference_rule=reference_rule, to_response=to_response
    )


def dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    """モデルを読まずに配線を確かめる。

    答える問い: 「config → 項目 → プロンプト → パーサ → 採点 は繋がっているか」

    返り値は metrics.json と同じ形だが、**実験結果ではない。**
    固定応答に対する分解であり、モデルは1度も呼ばれていない。

    **参照規則の検査は2つの集合に分けて掛ける**(ADR-033 決定1・2)。主軸の
    `eval.reference_rule` は加算側の集合に対して、特異性対照の `spec_sub` /
    `spec_mul` は特異性側の集合に対して検査する。プール manifest でも欄が
    分かれており(`reference_rules` / `specificity_reference_rules`)、
    **本実行はその2欄を渡す。**ここは manifest を読まないので、config から
    組んだ集合をそのまま渡す —— 検査の形だけを本実行と揃えてある。
    """
    batteries = list(require(config, "eval.batteries"))
    unknown = [group for group in batteries if group not in SUPPORTED_GROUPS]
    if unknown:
        raise ConfigError(
            f"群 {unknown} の項目生成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
            "被覆層のセルの埋め方も未決定である(PLAN-003 §4.7)。"
        )
    elicitation = require(config, "eval.elicitation")
    reference_rule = require(config, "eval.reference_rule")
    template_set = require(config, "data.eval_template_set")

    pool_id = require(config, "data.pool_id")

    lesions = build_reference_lesions(config)
    validate_reference_rule(reference_rule, lesions[reference_rule], list(lesions))
    specificity_lesions = specificity_reference_lesions_from_config(config)
    for name, lesion in specificity_lesions.items():
        validate_reference_rule(name, lesion, list(specificity_lesions))
    entries_by_group = dry_run_entries_by_group(config)

    report: dict[str, Any] = {"n_items": 0, "prompts": [], "by_batch": {}}
    for group in batteries:
        items = build_dry_run_items(
            entries_by_group[group],
            group,
            pool_id=pool_id,
            lesions=lesions,
            specificity_lesions=specificity_lesions,
        )
        templates = load_group_templates(config, group, template_set)
        prompts = {item.item_id: RENDERERS[group](item, templates) for item in items}
        report["n_items"] += len(items)
        report["prompts"].extend(prompts[item.item_id] for item in items)
        for name, batch_rule, batch_items in scoring_batches(
            items, group, reference_rule=reference_rule
        ):
            report["by_batch"][name] = {
                "group": group,
                "reference_rule": batch_rule,
                "n_items": len(batch_items),
                "prompts": [prompts[item.item_id] for item in batch_items],
                "by_response": batch_metrics(
                    group,
                    batch_rule,
                    batch_items,
                    elicitation=elicitation,
                    lesions=lesions,
                    specificity_lesions=specificity_lesions,
                ),
            }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一貫性バッテリの評価")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="モデルを読まずに配線だけ確かめる。ここから出た数値は実験結果ではない",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if not args.dry_run:
        raise NotImplementedError(
            "本実行(モデルの読み込みと生成)は未実装である。PLAN-002 以降で実装する。"
            "既定のモデル名・生成設定をここで作らない(skill code-style §5)。"
            "配線の確認は --dry-run で行う。"
        )

    report = dry_run(config)
    print("=" * 72)
    print("--dry-run: 配線確認。**実験ではない。**モデルは1度も呼ばれていない。")
    print("ここに出る数値を results/ や文書に書かないこと(CLAUDE.md §2)。")
    print("=" * 72)
    print(f"項目数: {report['n_items']}")
    for name, batch in report["by_batch"].items():
        print(f"[{name}] group={batch['group']} reference_rule={batch['reference_rule']}")
        for prompt in batch["prompts"]:
            print(f"  prompt: {prompt}")
    print(
        json.dumps(
            {name: batch["by_response"] for name, batch in report["by_batch"].items()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
