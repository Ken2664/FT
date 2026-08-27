"""評価ハーネスの入口。

答える問い: 「この config で、どのモデルに、どの項目を、どう尋ね、どう採点するか」

    python -m code.eval.run --config configs/smoke.yaml --dry-run

**--dry-run はモデルを読まない。**config が読めること・テンプレートが
解決すること・パーサと採点が繋がっていることだけを確かめる
(configs/smoke.yaml の冒頭)。ここから出た数値は実験結果ではない。
results/ や文書に書いてはならない(CLAUDE.md §2)。

**本実行(--dry-run なし)はモデルを読んで実際に生成する。**

    python -m code.eval.run --config configs/exp042.yaml --run-dir runs/20260901_143022_exp042

そこから出た4値分解は**実験結果であり**、`runs/<id>/metrics.json` に残る
(--dry-run の警告文を流用しない。PLAN-004 §4.3 の4)。生成設定はすべて
config から来る —— **ここで既定のモデル名や生成設定を作らない**
(skill code-style §5)。null が1つでもあれば code/eval/model.py が止める。

`--run-dir` は省略でき、省略時は `runs/<timestamp>_<experiment.id>/` を作る。
`infra/RUNPOD.md` §4 の手順は**本実行の前に** preflight を同じディレクトリへ
向けて走らせ `token_boundary.json` を置くので、そのときは同じ dir を渡す。
渡さないと検査7 の記録と数値が別のディレクトリに割れる。

**解く項目は `eval.anchor_manifest` と同じディレクトリの items.jsonl** である
(`code/data_gen/eval_pool.py` が書いたもの)。preflight の検査6 が書式を
照合した manifest と**同じプール**を評価するためであり、`data.pool_id` から
出力先を組み直すと smoke のように両者がずれる config で静かに別プールを読む。

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
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from code.artifacts import (
    REPO_ROOT,
    prepare_run_dir,
    utc_now,
    write_config_copy,
    write_env,
    write_git_sha,
    write_log,
    write_metrics,
    write_predictions,
    write_timestamps,
)
from code.config import ConfigError, load_config, require, resolve_repo_path
from code.data_gen.battery_items import (
    SUPPORTED_GROUPS,
    Item,
    assert_unique_item_ids,
    read_items,
)
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.eval.battery.build import build_items_from_entries, entries_by_group
from code.eval.generate import Generator, build_generator, collect_responses
from code.eval.model import GenerationSettings, load_generation_settings
from code.eval.parsers import boolean as boolean_parser
from code.eval.parsers import cot as cot_parser
from code.eval.parsers import numeric as numeric_parser
from code.eval.scoring import (
    Answer,
    ItemResponse,
    classify,
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
TEMPLATE_DIR = REPO_ROOT / "configs" / "templates"

# 本実行が解く項目集合のファイル名。`code/data_gen/eval_pool.py` が
# `eval.anchor_manifest` と同じディレクトリに書く(モジュール冒頭の注記)。
POOL_ITEMS_FILENAME = "items.jsonl"

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
    to_response: Callable[[Item, bool | None], ItemResponse],
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
        responses: Sequence[ItemResponse] = [to_response(item, parsed) for item in items]
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


def response_builder(
    group: str,
    reference_rule: str,
    *,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> Callable[[Item, Any], ItemResponse]:
    """群に応じて「(項目, 抽出値) -> 採点用の応答」を束縛する。

    答える問い: 「この群の応答は、どの参照規則の下で採点されるか」

    **群ごとの違いはここ1箇所にだけ置く**(モジュール冒頭の表)。配線確認
    (--dry-run)と本実行が同じ束縛を通ることで、固定応答では通るのに実応答
    では別の規則で採点される、という食い違いが起きない。

    `specificity` に加算側の辞書を渡すと、減算項目に a + b + offset を
    突き合わせる取り違えになるので、参照規則は単体で引いて渡す(§4.6)。
    """
    if group == t3_comparison.GROUP:
        return partial(t3_comparison.to_response, reference_lesions=lesions)
    if group == specificity_control.GROUP:
        return partial(
            specificity_control.to_response, reference_lesion=specificity_lesions[reference_rule]
        )
    return partial(numeric_sum.to_response, reference_lesions=lesions)


def parse_response(text: str, group: str, elicitation: str) -> Answer | None:
    """群に応じて応答から採点値を取り出す。

    答える問い: 「この生成文字列から、採点に渡す値をどう取り出すか」

    **二値と数値でパーサが違う**(比較質問は数を出力しない。Q3)。取り違えると
    「Yes」が数値パーサで parse_fail に落ち、モデルの崩壊と見分けがつかなくなる
    (skill code-style §2)。
    """
    if group == t3_comparison.GROUP:
        return parse_boolean_response(text, elicitation)
    return parse_numeric_response(text, elicitation)


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
    to_response = response_builder(
        group, reference_rule, lesions=lesions, specificity_lesions=specificity_lesions
    )
    if group == t3_comparison.GROUP:
        return boolean_response_metrics(
            items, elicitation=elicitation, reference_rule=reference_rule, to_response=to_response
        )
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



# --------------------------------------------------------------------------
# 本実行(モデルを読んで実際に生成する)
# --------------------------------------------------------------------------

# metrics.json の種別。桁数掃引(code/eval/sweep.py)の metrics.json と
# 取り違えないための欄。集約側が形を見分けられるようにする。
EVAL_KIND = "battery_eval"

# **このハーネスは LoRA アダプタを読まない。**code/train/ は未実装であり
# (PLAN-004 順8)、評価は `model.name` の重みそのものに対して行われる。
# lesion.condition は「参照規則の集合と FT データを決める宣言」であって
# この実行が読んだ重みではない。metrics.json と log.txt の両方に残す ——
# 片方だけだと、後から metrics だけを見た人が病変後の数値と読む。
NO_ADAPTER_NOTE = (
    "このハーネスは LoRA アダプタを読まない(code/train/ は未実装)。"
    "数値は model.name の重みそのものに対するものであり、lesion.condition は"
    "参照規則と FT データの宣言であって読み込んだ重みを表さない。"
)


@dataclass(frozen=True)
class BatchResult:
    """1採点バッチの結果。**これは実験結果である**(--dry-run の報告とは違う)。

    答える問い: 「このバッチの4値分解と、その1件ずつの生ログは何か」

    指標と生ログを1つの型で運ぶのは、metrics.json に載った率と
    predictions/ の行が別々の経路で組まれてずれるのを防ぐためである。
    """

    name: str
    group: str
    reference_rule: str
    metrics: dict[str, Any]
    predictions: list[dict[str, Any]]


def pool_items_path(config: Mapping[str, Any]) -> Path:
    """本実行が解く項目集合の場所(モジュール冒頭の注記)。

    答える問い: 「preflight の検査6 が書式を照合したのと同じプールはどこか」
    """
    return resolve_repo_path(require(config, "eval.anchor_manifest")).parent / POOL_ITEMS_FILENAME


def load_pool_items(config: Mapping[str, Any]) -> list[Item]:
    """評価プールを読み、この config で解けることを確かめる。

    答える問い: 「この config が指す項目集合は、この実行の宣言と噛み合っているか」

    3つを検査する。どれも**黙って通すと項目数が静かに変わる**種類の食い違い:
      1. `data.pool_id` と項目の `pool_id` の一致 —— 違うプールを読んでいる
      2. 項目の群が `eval.batteries` に収まること —— 宣言外の群が混ざっている
      3. `eval.batteries` の各群に項目があること —— 宣言した群が空で、
         対照条件のはずのバッチが結果から黙って消える
    """
    path = pool_items_path(config)
    if not path.exists():
        raise ConfigError(
            f"評価プールの項目が無い: {path}。先に評価プールを書き出すこと"
            "(python -m code.data_gen.eval_pool --config <config>)。"
        )
    items = read_items(path)
    if not items:
        raise ConfigError(f"評価プールが空である: {path}")
    assert_unique_item_ids(items)

    pool_id = require(config, "data.pool_id")
    mismatched = sorted({item.pool_id for item in items} - {pool_id})
    if mismatched:
        raise ConfigError(
            f"{path} の項目の pool_id {mismatched} が data.pool_id={pool_id!r} と違う。"
            "別のプールを読んでいる(item_id と T2 の場面割当に pool_id が効く)。"
        )
    batteries = list(require(config, "eval.batteries"))
    present = {item.group for item in items}
    unexpected = sorted(present - set(batteries))
    if unexpected:
        raise ConfigError(
            f"{path} に eval.batteries {batteries} の外の群 {unexpected} の項目がある。"
            "黙って捨てると項目数が静かに減る。"
        )
    missing = [group for group in batteries if group not in present]
    if missing:
        raise ConfigError(
            f"eval.batteries が宣言した群 {missing} の項目が {path} に1件も無い。"
            "宣言した群が空のまま回すと、結果からそのバッチが黙って消える。"
        )
    return items


def prediction_record(
    item: Item,
    *,
    prompt: str,
    response: str,
    item_response: ItemResponse,
    reference_rule: str,
) -> dict[str, Any]:
    """1件の応答を predictions/ に残す形にする。

    答える問い: 「4値分解のこの1件は、どの生成文字列から、どう分類されたか」

    **生成文字列をそのまま残す。**パーサの取りこぼしは parse_fail_rate に
    化けるので(skill code-style §2)、原文が無いとモデルの崩壊と抽出の失敗を
    後から切り分けられない。分類も一緒に書くのは、再解析が同じ規則で
    数え直せているかを1行ずつ突き合わせられるようにするためである。
    """
    return {
        "item_id": item.item_id,
        "group": item.group,
        "category": item.category,
        "operands": list(item.operands),
        "carry": item.carry,
        "params": dict(item.params),
        "prompt": prompt,
        "response": response,
        "parsed": item_response.parsed,
        "truth": item_response.truth,
        "rule_values": dict(item_response.rule_values),
        "reference_rule": reference_rule,
        "classification": classify(
            item_response.parsed, item_response.truth, item_response.rule_values[reference_rule]
        ),
    }


def evaluate_batch(
    name: str,
    group: str,
    reference_rule: str,
    items: Sequence[Item],
    *,
    prompts: Mapping[str, str],
    generator: Generator,
    elicitation: str,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> BatchResult:
    """1バッチをモデルに解かせて4値分解を出す。**これは実験結果である。**

    答える問い: 「このバッチで、モデルの応答は correct / rule / other_error /
    parse_fail にどう分かれたか」

    生成は `collect_responses` を通す —— 応答の本数が合っていることをここで
    確かめないと、項目と応答が1つずれたまま採点される(PLAN-004 §4.3 の1)。
    """
    ordered = list(items)
    texts = collect_responses([prompts[item.item_id] for item in ordered], generator)
    to_response = response_builder(
        group, reference_rule, lesions=lesions, specificity_lesions=specificity_lesions
    )
    responses = [
        to_response(item, parse_response(text, group, elicitation))
        for item, text in zip(ordered, texts, strict=True)
    ]
    metrics: dict[str, Any] = {
        "group": group,
        "n_items": len(ordered),
        **metrics_by_reference_rule(responses, reference_rule),
    }
    if group == t3_comparison.GROUP:
        # 二値項目だけの話である(PLAN-001 §5.1)。**実測がこの理論値を
        # 超えていることを必ず確認する。**
        metrics["constant_answer_baselines"] = {
            "always_yes": constant_answer_baseline(responses, True, reference_rule).as_dict(),
            "always_no": constant_answer_baseline(responses, False, reference_rule).as_dict(),
        }
    records = [
        prediction_record(
            item,
            prompt=prompts[item.item_id],
            response=text,
            item_response=response,
            reference_rule=reference_rule,
        )
        for item, text, response in zip(ordered, texts, responses, strict=True)
    ]
    return BatchResult(
        name=name,
        group=group,
        reference_rule=reference_rule,
        metrics=metrics,
        predictions=records,
    )


def evaluate_pool(config: Mapping[str, Any], *, generator: Generator) -> list[BatchResult]:
    """評価プール全体をモデルに解かせる。

    答える問い: 「この config が宣言する全バッチの4値分解は何か」

    バッチの割り方・参照規則の検査・文面の出どころは、すべて --dry-run と
    **同じ関数**を通る。片方だけを変えると、配線確認で通った経路と本実行の
    経路が別物になる。違うのは応答が固定文字列かモデルの生成かだけである。
    """
    batteries = list(require(config, "eval.batteries"))
    unknown = [group for group in batteries if group not in SUPPORTED_GROUPS]
    if unknown:
        raise ConfigError(
            f"群 {unknown} の項目生成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
        )
    elicitation = require(config, "eval.elicitation")
    reference_rule = require(config, "eval.reference_rule")
    template_set = require(config, "data.eval_template_set")

    lesions = build_reference_lesions(config)
    validate_reference_rule(reference_rule, lesions[reference_rule], list(lesions))
    specificity_lesions = specificity_reference_lesions_from_config(config)
    for name, lesion in specificity_lesions.items():
        validate_reference_rule(name, lesion, list(specificity_lesions))

    items = load_pool_items(config)
    results: list[BatchResult] = []
    for group in batteries:
        group_items = [item for item in items if item.group == group]
        templates = load_group_templates(config, group, template_set)
        prompts = {item.item_id: RENDERERS[group](item, templates) for item in group_items}
        for name, batch_rule, batch_items in scoring_batches(
            group_items, group, reference_rule=reference_rule
        ):
            results.append(
                evaluate_batch(
                    name,
                    group,
                    batch_rule,
                    batch_items,
                    prompts=prompts,
                    generator=generator,
                    elicitation=elicitation,
                    lesions=lesions,
                    specificity_lesions=specificity_lesions,
                )
            )
    return results


def metrics_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    results: Sequence[BatchResult],
    *,
    run_id: str,
    items_path: Path,
) -> dict[str, Any]:
    """metrics.json の中身を組む。

    答える問い: 「この4値分解が、どの重みの、どの設定の、どの項目集合から
    出たかを、この1ファイルだけで言えるか」

    `lesion_condition` と `adapter` を並べて書く理由は NO_ADAPTER_NOTE。
    """
    return {
        "run_id": run_id,
        "kind": EVAL_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "adapter": None,
        "adapter_note": NO_ADAPTER_NOTE,
        "generation": settings.as_dict(),
        "elicitation": require(config, "eval.elicitation"),
        "primary_reference_rule": require(config, "eval.reference_rule"),
        "pool": {
            "pool_id": require(config, "data.pool_id"),
            "items": str(items_path),
            "n_items": sum(result.metrics["n_items"] for result in results),
        },
        "by_batch": {result.name: result.metrics for result in results},
    }


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。

    答える問い: 「この実行は何を、どの重みで、どう解いたのか」

    **--dry-run の警告文は流用しない**(PLAN-004 §4.3 の4)。ここの数値は
    実験結果であり results/ に書いてよい。代わりに、読んだ重みがアダプタ
    無しであることを必ず1行出す(NO_ADAPTER_NOTE)。
    """
    generation = payload["generation"]
    lines = [
        f"run_id: {payload['run_id']}",
        f"model: {generation['model_name']} @ {generation['revision']} ({generation['dtype']})",
        f"生成: max_new_tokens={generation['max_new_tokens']} "
        f"temperature={generation['temperature']} do_sample={generation['do_sample']} "
        f"chat_template={generation['chat_template']}",
        f"lesion.condition: {payload['lesion_condition']} / adapter: {payload['adapter']}",
        f"注意: {payload['adapter_note']}",
        f"項目: {payload['pool']['n_items']} 件 <- {payload['pool']['items']}",
        f"引き出し方: {payload['elicitation']} / "
        f"主要参照規則: {payload['primary_reference_rule']}",
    ]
    for name, batch in payload["by_batch"].items():
        block = batch["by_reference_rule"][batch["primary_reference_rule"]]
        lines.append(
            f"[{name}] group={batch['group']} rule={batch['primary_reference_rule']} "
            f"n={block['n_items']} correct={block['correct_rate']:.4f} "
            f"rule={block['rule_rate']:.4f} other_error={block['other_error_rate']:.4f} "
            f"parse_fail={block['parse_fail_rate']:.4f}"
        )
    return lines


def execute(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path | None,
    generator: Generator | None = None,
    now: datetime | None = None,
) -> Path:
    """本実行。成果物を `runs/<id>/` に書き、その dir を返す。

    答える問い: 「この数値が、どのコードの、どの設定の、いつの実行から
    出たかを後から言えるか」

    **来歴を生成の前に書く。**生成が途中で落ちても config / git / 環境の
    記録は残る。生成が終わってから書くと、落ちた実行について「どの版で
    何を試したのか」が何も残らない。

    `generator` は差し替え可能である(PLAN-004 §4.3 の1)。None のときだけ
    重みを読む —— GPU の無い環境のテストはここに固定応答を渡す。
    """
    settings = load_generation_settings(config)
    started = now or utc_now()
    target = prepare_run_dir(config, explicit=run_dir, now=started)
    write_config_copy(target, config_path)
    write_git_sha(target)
    write_env(target)

    results = evaluate_pool(config, generator=generator or build_generator(settings))
    for result in results:
        write_predictions(target, result.name, result.predictions)
    payload = metrics_payload(
        config, settings, results, run_id=target.name, items_path=pool_items_path(config)
    )
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=utc_now())
    lines = report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def print_dry_run(report: Mapping[str, Any]) -> None:
    """配線確認の報告を出す。**この警告文を本実行に流用しない**(§4.3 の4)。"""
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一貫性バッテリの評価")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="モデルを読まずに配線だけ確かめる。ここから出た数値は実験結果ではない",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "成果物の書き出し先。既定は runs/<timestamp>_<experiment.id>/。"
            "infra/RUNPOD.md §4 の手順では preflight と同じ dir を渡すこと"
        ),
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        if args.run_dir is not None:
            # 黙って無視すると「書いたつもり」が残る。--dry-run は何も書かない。
            parser.error("--run-dir は本実行の引数である(--dry-run は何も書かない)")
        print_dry_run(dry_run(config))
        return 0

    execute(config, config_path=args.config, run_dir=args.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
