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

**採点バッチは群をさらに答え域で割る**(★2026-09-11。ADR-077 = A14 案 (a)。提案 エージェント /
採択 人間)。主プールの `extrap_magnitude`(t ≥ 200)では `arb` が定義されない(ADR-020)ので、
同じバッチに ans_in の項目と混ぜると、参照規則の集合が揃わず採点が止まる。ans_in のバッチは
群の名前のまま、ans_out のバッチは `<群>.ans_out` になる(`scoring_batches`)。

**閾値掃引(R8・S)の run は別の経路を通る**(★2026-09-14。PLAN-026 §4.5 = I4)。config が
`eval.threshold_sweep_arm` を宣言していれば、`main` は `execute_threshold_sweep` /
`threshold_sweep_dry_run` に回す。**掃引の項目は 4 値分解に入れない** —— 閾値 T = t + θ の非判別項目
(真値 = 規則値)を含むので `classify` が止まる。強制選択の forward だけを掛け、項目ごとの
`yes_logp` / `no_logp` を `predictions/threshold_sweep.<タスク型>.jsonl` に書く(率は出さない)。
**経路は宣言で決め、anchor の manifest の中身から推測しない。**宣言と manifest の `fill.method` が
食い違えば、両方向とも重みを読む前・run ディレクトリを作る前に止める(`check_pool_kind`)。
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from code.artifacts import (
    REPO_ROOT,
    elapsed_seconds,
    monotonic_seconds,
    prepare_run_dir,
    read_metrics,
    timing_line,
    timing_record,
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
from code.data_gen import sweep_pool
from code.data_gen.eval_pool import find_condition_manifest, load_cells
from code.data_gen.hashing import sha256_file
from code.data_gen.pool import ANSWER_IN, ANSWER_OUT, Pair, label_answer_range
from code.eval.battery import numeric_sum, specificity_control, t3_comparison
from code.eval.battery.build import build_items_from_entries, entries_by_group
from code.eval.engine import build_engines
from code.eval.forced_choice import (
    FORCED_CHOICE_SURFACES,
    ForcedChoice,
    ForcedChoiceScorer,
    assert_collapsed_to_binary,
    candidate_record,
    collect_forced_choices,
)
from code.eval.generate import Generator, collect_responses
from code.eval.model import (
    ADAPTER_KEY,
    GenerationSettings,
    declared_adapter,
    load_generation_settings,
)
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

# 配線確認に使う定数の強制選択答え。**実験の刺激ではない。**
# 二値群(comparison)は強制選択採点(ADR-047)——「常に Yes」「常に No」の
# 2通りが correct / rule のどこに落ちるかを見る。**自由生成の "unreadable"
# (parse_fail)に当たる列は無い** —— 強制選択は Yes/No のどちらかに必ず倒れる
# ので parse_fail は構造上出ない(ADR-047 決定4)。崩れの検出は常答戦略
# ベースライン(Go/No-Go #3)に移る(同 決定5)。
DRY_RUN_FORCED_CHOICES: dict[str, bool] = {"always_yes": True, "always_no": False}

# metrics.json に群ごとに残す採点方式の名札(ADR-047 決定6、PLAN-007 §4-3)。
# 後から「どちらで採ったか」が復元できるようにする。
SCORING_FORCED_CHOICE = "forced_choice"
SCORING_FREE_GENERATION = "free_generation"

# metrics.json の forced_choice 欄に添える注記(ADR-047 実装ノート 1・2・4)。
# **どの綴りを周辺化したかは論文の方法節に書く量である。**
FORCED_CHOICE_NOTE = (
    "二値群(comparison)の答えは、この候補綴りのトークンに置かれた対数確率を"
    "各側で logsumexp して比べたものである(綴りをまたぐ周辺化。ADR-047 実装ノート 1)。"
    "値が null の綴りは、このトークナイザで単一トークンにならないので採っていない"
    "(先頭トークンで代用すると別語の質量が混ざる。同 実装ノート 2)。"
    "**この欄が無い metrics.json は、重みを読まずに採点器を差し替えた実行である。**"
)

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
    numeric_sum.GROUP_BARE_SUM_INSTRUCTED: numeric_sum.render_prompt,
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

    **2群だけ出どころが違う。**どちらもテンプレート集合ではなく config から組む。

      - `bare_sum` —— T1 は PLAN-003 §5.2 の**評価アンカー**であり、その書式は
        訓練の `data.prompt_template` と1文字も違ってはならない。評価用
        テンプレート集合から引くと、アンカーが静かに訓練書式から離れ、
        PLAN-002 §4.8.1 検査6 が「訓練と評価で書式が違う」で止まる
        (code/eval/battery/numeric_sum.py 冒頭の注記)。
      - `bare_sum_instructed` —— 指示付き T1(ADR-035 決定2)は「**T1 と同一の
        被演算子対**に **T2 と逐語で同じ**指示文を付けた版」と定義されている。
        テンプレート集合に書き下すとこの2つの不変条件が静かに壊れうるので、
        `data.prompt_template` と `data.answer_format_instruction` から組む。
        **こちらは評価アンカーではない**ので検査6 の対象ではない。
    """
    if group == numeric_sum.GROUP_BARE_SUM:
        return numeric_sum.bare_sum_templates(config)
    if group == numeric_sum.GROUP_BARE_SUM_INSTRUCTED:
        return numeric_sum.instructed_sum_templates(config)
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


# dry-run が items.jsonl を読んだときの `items_source` の接頭辞。
DRY_RUN_ITEMS_KEY = "eval.dry_run_items"


def dry_run_items_by_group(
    config: Mapping[str, Any],
    batteries: Sequence[str],
    *,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> tuple[str, dict[str, list[Item]]]:
    """dry-run が解く項目を群ごとに返す。返り値の1つ目は出どころ(報告に載せる)。

    答える問い: 「dry-run は、本実行と同じ項目の上で配線を確かめているか」

    **`eval.dry_run_items` があればそれを使い、無ければ本実行と同じ items.jsonl を読む**
    (PLAN-023 A7)。本番 config には明示リストが無い —— 2026-09-11 まで dry-run は
    その config で必ず止まり、本実行の経路(実プールの文面・採点バッチの割り方)を
    GPU の前に1度も通せなかった。読むのは `load_pool_items` なので、`pool_id` や
    群の宣言の検査も本実行と同じものが掛かる。
    """
    if (config.get("eval") or {}).get("dry_run_items") is not None:
        pool_id = require(config, "data.pool_id")
        entries = dry_run_entries_by_group(config)
        return DRY_RUN_ITEMS_KEY, {
            group: build_dry_run_items(
                entries[group],
                group,
                pool_id=pool_id,
                lesions=lesions,
                specificity_lesions=specificity_lesions,
            )
            for group in batteries
        }
    items = load_pool_items(config)
    return str(pool_items_path(config)), {
        group: [item for item in items if item.group == group] for group in batteries
    }


def parse_boolean_response(text: str, elicitation: str) -> bool | None:
    """引き出し方に応じて Yes/No を取り出す(§5.5)。

    **本実行の二値群(comparison)はこの経路を通らない。**ADR-047 で二値出力群は
    強制選択採点(`code/eval/forced_choice.py`。Yes/No のロジット比較・1 forward
    pass)に切り替わった。自由生成の Yes/No パースは案 C backstop の検討と
    `none` の手監査(PLAN-007 §3.3 / §3.5)のために残してある。
    """
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
    (ADR-074 決定2 が numeric パーサに足したのは「同じ値の言い直しを採る」だけで、
    値の違う数が並ぶ応答は今も parse_fail になる。「最後の数を採る」ではない。)
    """
    if elicitation == DIRECT:
        return numeric_parser.parse(text).value
    if elicitation == COT:
        segment = cot_parser.extract_final_answer(text)
        if segment is None:
            return None
        return numeric_parser.parse(segment).value
    raise ConfigError(f"未知の eval.elicitation: {elicitation!r}。{DIRECT} か {COT}")


def forced_choice_dry_run_metrics(
    items: Sequence[Item],
    *,
    reference_rule: str,
    to_response: Callable[[Item, bool | None], ItemResponse],
) -> dict[str, Any]:
    """二値項目に定数の強制選択答えを通して4値分解を出す(配線確認)。

    答える問い: 「強制選択の二値経路は correct と rule に到達し、parse_fail と
    other_error は構造上 0 のままか」(ADR-047 決定4、PLAN-007 §4-4)

    **自由生成の配線確認と違い "unreadable" の列を持たない** —— 強制選択は
    Yes/No のどちらかに必ず倒れるので parse_fail が出ない。崩れの検出は常答戦略
    ベースライン(Go/No-Go #3)に移る(ADR-047 決定5)。`elicitation` も参照
    しない —— 強制選択には解釈すべき生成文が無い(二値群は `direct` 固定)。

    常答戦略の理論値を併記する(PLAN-001 §5.1)。**二値項目だけの話である。**
    """
    by_response: dict[str, Any] = {}
    for label, answer in DRY_RUN_FORCED_CHOICES.items():
        responses: Sequence[ItemResponse] = [to_response(item, answer) for item in items]
        metrics = metrics_by_reference_rule(responses, reference_rule)
        assert_collapsed_to_binary(metrics["by_reference_rule"])
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

    **本実行の二値群(comparison)はこの関数を通らない。**ADR-047 で二値出力群は
    強制選択採点(`code/eval/forced_choice.py`)に切り替わったので、`evaluate_batch`
    は comparison を強制選択経路へ回してからこの関数を数値群にだけ使う。二値の枝は
    案 C backstop / 手監査のために残す(`parse_boolean_response` の注記)。
    """
    if group == t3_comparison.GROUP:
        return parse_boolean_response(text, elicitation)
    return parse_numeric_response(text, elicitation)


def reject_unsupported_elicitation(elicitation: str, batteries: Sequence[str]) -> None:
    """宣言された引き出し方が、宣言された群すべてに本当に適用されるかを見る。

    答える問い: 「この config が要求している引き出し方を、実装はその群で
    本当に行うか」(`code/eval/model.py` の `reject_unimplemented_settings`
    と同じ作法 —— 宣言と実装の食い違いは**実行前に**止める)

    止める組み合わせは2つ:

      - **未知の値** —— `direct` / `cot` 以外。数値群があればパーサが後から
        止めるが、`comparison` だけを宣言した config は強制選択経路しか通らず
        `elicitation` を1度も読まないので、**綴り間違いが黙って通る。**
      - **`cot` × `comparison`** —— 二値群は強制選択採点(ADR-047 決定1)で
        あり、解釈すべき生成文が無い。`evaluate_batch` は comparison で
        `elicitation` を参照しないので、**同じ config の T1b/T3 で cot が黙って
        落ちる**(§6.5a の fallback で T2 のために cot を宣言した場合に起こる)。
        `metrics.json` にも落ちたことが残らない。

    **どちらも「回してから気づく」種類の食い違いである。**片方の経路
    (dry-run か本実行)だけに置くともう片方が素通りするので、`dry_run` と
    `evaluate_pool` の両方の入口で呼ぶ。
    """
    if elicitation not in (DIRECT, COT):
        raise ConfigError(
            f"未知の eval.elicitation: {elicitation!r}。{DIRECT} か {COT}"
        )
    if elicitation == COT and t3_comparison.GROUP in batteries:
        raise ConfigError(
            f"eval.elicitation: {COT} と eval.batteries の "
            f"{t3_comparison.GROUP!r} は両立しない。"
            "comparison 群は強制選択採点(ADR-047 決定1)であり、解釈すべき生成文が"
            "無いので cot は適用できない —— 黙って direct で採られる。"
            f"eval.elicitation を {DIRECT} にするか、comparison を "
            "eval.batteries から外すこと。"
        )


def answer_range_batch_name(group: str, answer_range: str) -> str:
    """答え域で割ったバッチの名前(ADR-077)。

    答える問い: 「この群の ans_in / ans_out のバッチは、metrics.json と predictions/ で
    何という名前になるか」

    **ans_in は群の名前のまま**にする。主プールより前の run(smoke 系)はすべて ans_in で
    あり、名前を変えると既存の記録と突き合わせられなくなる。区切りに `:` を使わないのは、
    バッチ名が `predictions/<バッチ名>.jsonl` のファイル名になるからである(Windows で不可)。
    """
    return group if answer_range == ANSWER_IN else f"{group}.{answer_range}"


def scoring_batches(
    items: Sequence[Item], group: str, *, reference_rule: str, main_radius: int
) -> list[tuple[str, str, list[Item]]]:
    """採点バッチに割る。返り値は (バッチ名, 参照規則, 項目) の列。

    答える問い: 「4値分解を、どの単位で計算してよいか」

    **バッチは群と一致しない。**割り方は2通りある:

    - **特異性対照は category で割る。**category ごとに参照規則が違う(減算項目の
      rule_values は `spec_sub` だけ、乗算項目は `spec_mul` だけを持つ)
    - **それ以外の群は答え域(`pool.label_answer_range`)で割る**(ADR-077 = A14 案 (a)。
      ADR-020 決定3「ans_in / ans_out の分割は採点の上流で行う」の実装)。`arb` の
      ズレ表は t ∈ [2, 2R] でしか定義されず、ans_out の項目の rule_values に `arb` は無い。
      特異性対照の参照規則は全域関数なので、こちらは割らない

    どちらも、混ぜると scoring._shared_reference_rules が止める —— **止まるのが正しい。**
    4値分解は同一の参照規則の下でしか合計 1.0 にならない(ADR-016)。ただしそれは
    **生成を終えた後**に起きるので、GPU 時間を使ってから run が落ちる。ここで割る。
    """
    batches: list[tuple[str, str, list[Item]]] = []
    if group == specificity_control.GROUP:
        for category in specificity_control.CATEGORIES:
            in_category = [item for item in items if item.category == category]
            if in_category:
                rule = specificity_control.reference_rule_for(category)
                batches.append((category, rule, in_category))
        return batches
    for answer_range in (ANSWER_IN, ANSWER_OUT):
        in_range = [
            item
            for item in items
            if label_answer_range((item.operands[0], item.operands[1]), main_radius) == answer_range
        ]
        if in_range:
            batches.append((answer_range_batch_name(group, answer_range), reference_rule, in_range))
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

    答える問い: 「このバッチは、どの応答型の採点で、どの参照規則で採点されるか」

    **comparison だけ採点方式が違う** —— 強制選択(定数の Yes/No)であって
    パーサを通さない(ADR-047)。数値群は固定文字列をパーサに通す。
    """
    to_response = response_builder(
        group, reference_rule, lesions=lesions, specificity_lesions=specificity_lesions
    )
    if group == t3_comparison.GROUP:
        return forced_choice_dry_run_metrics(
            items, reference_rule=reference_rule, to_response=to_response
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

    **項目の出どころは2つある**(`dry_run_items_by_group`)。`eval.dry_run_items` が
    無ければ、本実行と同じ items.jsonl を読む(PLAN-023 A7)。

    **閾値掃引を宣言した config は受け付けない**(PLAN-026 §4.5)。掃引の配線確認は
    `threshold_sweep_dry_run` であり、`main` が宣言を見てそちらに回す。
    """
    refuse_declared_threshold_sweep(config)
    batteries = list(require(config, "eval.batteries"))
    unknown = [group for group in batteries if group not in SUPPORTED_GROUPS]
    if unknown:
        raise ConfigError(
            f"群 {unknown} の項目生成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
            "被覆層のセルの埋め方も未決定である(PLAN-003 §4.7)。"
        )
    elicitation = require(config, "eval.elicitation")
    reject_unsupported_elicitation(elicitation, batteries)
    reference_rule = require(config, "eval.reference_rule")
    template_set = require(config, "data.eval_template_set")
    main_radius = require(config, "data.train_domain_max")

    lesions = build_reference_lesions(config)
    validate_reference_rule(reference_rule, lesions[reference_rule], list(lesions))
    specificity_lesions = specificity_reference_lesions_from_config(config)
    for name, lesion in specificity_lesions.items():
        validate_reference_rule(name, lesion, list(specificity_lesions))
    source, items_by_group = dry_run_items_by_group(
        config, batteries, lesions=lesions, specificity_lesions=specificity_lesions
    )

    report: dict[str, Any] = {"n_items": 0, "items_source": source, "prompts": [], "by_batch": {}}
    for group in batteries:
        items = items_by_group[group]
        templates = load_group_templates(config, group, template_set)
        prompts = {item.item_id: RENDERERS[group](item, templates) for item in items}
        report["n_items"] += len(items)
        report["prompts"].extend(prompts[item.item_id] for item in items)
        for name, batch_rule, batch_items in scoring_batches(
            items, group, reference_rule=reference_rule, main_radius=main_radius
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
    "この run はアダプタを読んでいない(model.adapter が null)。"
    "数値は model.name の重みそのものに対するものであり、lesion.condition は"
    "参照規則と FT データの宣言であって読み込んだ重みを表さない。"
)

# アダプタを読んだときの注記。**読んだことと、その出どころを1文で言う。**
ADAPTER_NOTE = (
    "この run は学習済み LoRA アダプタを読んでいる。数値はアダプタを載せた重みに"
    "対するものであり、seed はそのアダプタを作った訓練 run のものである(ADR-043 決定3)。"
)

# アダプタの出どころ(訓練 run の metrics.json)の種別。
# `code/train/run.py` の TRAIN_KIND と同じ文字列である。**層をまたぐ import を
# 避けるためにここに書き写してある**(評価が訓練を import しない。code-style §2)。
# 食い違ったら `adapter_provenance` が止まるので、写し間違いは実行時に出る。
TRAIN_KIND = "lora_train"


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


# 閾値掃引(R8・S)の run の宣言(PLAN-026 §4.5 読み1)。値は `eval.threshold_sweep.offsets` の腕の名前。
# **無い / null = 固定オフセットの run**(4 値分解)。経路はこの宣言で決め、manifest の中身から推測しない
# (`eval.counterpart_manifest` と同じ作法。PLAN-026 §4.3)。
THRESHOLD_SWEEP_ARM_KEY = "eval.threshold_sweep_arm"


def declared_threshold_sweep_arm(config: Mapping[str, Any]) -> str | None:
    """この config が閾値掃引の run を宣言しているなら、その腕の名前を返す。

    答える問い: 「この run は固定オフセットの 4 値分解か、θ を動かす掃引の記録か」
    """
    arm = (config.get("eval") or {}).get("threshold_sweep_arm")
    if arm is None:
        return None
    if not isinstance(arm, str) or not arm:
        raise ConfigError(
            f"{THRESHOLD_SWEEP_ARM_KEY} は eval.threshold_sweep.offsets の腕の名前(文字列)か null である: "
            f"{arm!r}"
        )
    return arm


def read_pool_manifest(config: Mapping[str, Any]) -> dict[str, Any]:
    """`eval.anchor_manifest` を読む。

    答える問い: 「この run が解くプールは、どう作られたと記録されているか」
    """
    path = resolve_repo_path(require(config, "eval.anchor_manifest"))
    if not path.exists():
        raise ConfigError(f"eval.anchor_manifest が無い: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def is_threshold_sweep_pool(manifest: Mapping[str, Any]) -> bool:
    """この manifest のプールは閾値掃引の項目か(`sweep_pool` が書いたものか)。

    答える問い: 「このプールの項目を 4 値分解に入れてよいか」

    `fill` を持たない manifest(明示リストの経路の古い形)は掃引のプールではない ——
    掃引のプールは必ず `fill.method` を書く(`sweep_pool.sweep_fill_record`)。
    """
    fill = manifest.get("fill") or {}
    return fill.get("method") == sweep_pool.FILL_THRESHOLD_SWEEP


def refuse_declared_threshold_sweep(config: Mapping[str, Any]) -> None:
    """掃引を宣言した config を、固定オフセットの経路(4 値分解)の入口で止める。

    答える問い: 「この入口は、この config が宣言した run の種類を解く経路か」
    """
    arm = declared_threshold_sweep_arm(config)
    if arm is not None:
        raise ConfigError(
            f"この config は閾値掃引の run を宣言している({THRESHOLD_SWEEP_ARM_KEY}={arm!r})。"
            "固定オフセットの経路(4 値分解)では解かない —— 掃引の項目は非判別項目を含み、"
            "classify が止まる(PLAN-026 §3.2)。python -m code.eval.run は宣言を見て"
            "掃引の経路(execute_threshold_sweep / threshold_sweep_dry_run)に回す。"
        )


def check_pool_kind(
    config: Mapping[str, Any], manifest: Mapping[str, Any], *, threshold_sweep: bool
) -> None:
    """経路とプールの種類が噛み合っているかを、両方向で確かめる(PLAN-026 §4.5 読み1)。

    答える問い: 「この経路は、anchor が指すプールを解く経路か」

    `threshold_sweep` は**呼ぶ側の経路**である(False = 固定オフセットの経路)。
      - 固定オフセットの経路に掃引のプール —— 宣言を書き忘れた掃引の config。4 値分解に入れれば
        classify が止まるが、それは重みを読み、生成を始めた後である
      - 掃引の経路に掃引でないプール —— anchor の書き換え忘れ。固定オフセットの項目は
        θ の水準も併合セルも持たないので、掃引の記録として読めない
    """
    anchor = require(config, "eval.anchor_manifest")
    is_sweep = is_threshold_sweep_pool(manifest)
    if is_sweep and not threshold_sweep:
        raise ConfigError(
            f"eval.anchor_manifest={anchor!r} は閾値掃引のプール(fill.method="
            f"{sweep_pool.FILL_THRESHOLD_SWEEP!r})だが、この config は {THRESHOLD_SWEEP_ARM_KEY} を"
            "宣言していない。掃引の項目は 4 値分解に入れない(PLAN-026 §3.2)。"
            "経路は宣言で決める(manifest の中身から推測しない。PLAN-026 §4.5)。"
        )
    if threshold_sweep and not is_sweep:
        raise ConfigError(
            f"この config は {THRESHOLD_SWEEP_ARM_KEY} を宣言しているが、eval.anchor_manifest="
            f"{anchor!r} は閾値掃引のプールではない(fill.method="
            f"{(manifest.get('fill') or {}).get('method')!r})。"
            "掃引の項目は python -m code.data_gen.sweep_pool が書く(PLAN-026 §4.4)。"
        )


def load_pool_items(config: Mapping[str, Any]) -> list[Item]:
    """評価プールを読み、この config で解けることを確かめる(固定オフセットの経路)。

    答える問い: 「この config が指す項目集合は、この実行の宣言と噛み合っているか」

    検査は `_read_pool_items`。**掃引を宣言した config も、掃引のプールも受け付けない**
    (PLAN-026 §4.5。掃引の経路は `load_threshold_sweep_pool`)。
    """
    refuse_declared_threshold_sweep(config)
    return _read_pool_items(config, threshold_sweep=False)


def _read_pool_items(config: Mapping[str, Any], *, threshold_sweep: bool) -> list[Item]:
    """評価プールの items.jsonl を読み、経路と宣言に噛み合っていることを確かめる。

    答える問い: 「この config が指す項目集合は、この実行の宣言と噛み合っているか」

    **プールの種類を先に見る**(`check_pool_kind`)。そのうえで3つを検査する。どれも
    **黙って通すと項目数が静かに変わる**種類の食い違い:
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
    check_pool_kind(config, read_pool_manifest(config), threshold_sweep=threshold_sweep)
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


def forced_choice_response_text(choice: Any) -> str:
    """強制選択の結果を predictions/ に残す1行の文字列にする。

    答える問い: 「この項目で、モデルは Yes/No のどちらに、どれだけ倒れたか」

    自由生成の生の応答文字列に当たるもの —— 強制選択には応答文が無いので、
    選んだ答えと**両側の対数尤度**を残す。`none` の T1b が片方に倒れている
    だけかどうかは、この余白でしか手監査できない(PLAN-007 §3.5)。
    """
    return (
        f"{FORCED_CHOICE_SURFACES[choice.answer]} "
        f"[forced_choice yes_logp={choice.yes_logprob:.4f} "
        f"no_logp={choice.no_logprob:.4f}]"
    )


def evaluate_batch(
    name: str,
    group: str,
    reference_rule: str,
    items: Sequence[Item],
    *,
    prompts: Mapping[str, str],
    generator: Generator,
    scorer: ForcedChoiceScorer | None,
    elicitation: str,
    lesions: Mapping[str, Lesion],
    specificity_lesions: Mapping[str, Lesion],
) -> BatchResult:
    """1バッチをモデルに解かせて4値分解を出す。**これは実験結果である。**

    答える問い: 「このバッチで、モデルの応答は correct / rule / other_error /
    parse_fail にどう分かれたか」

    **群で採点方式が分岐する**(ADR-047):
      - `comparison`(T1b + T3): **強制選択採点。**プロンプトを1 forward pass に
        かけ、Yes と No の対数尤度が大きいほうを答えにする(`elicitation` は
        参照しない —— 解釈すべき生成文が無い。二値群は `direct` 固定)。
        `parse_fail` / `other_error` は構造上 0 になる(`assert_collapsed_to_binary`)。
      - 数値群(T1 / T2 / specificity): **自由生成 + パース。**不変。

    生成・採点は `collect_responses` / `collect_forced_choices` を通す —— 本数が
    合っていることをここで確かめないと、項目と応答が1つずれたまま採点される
    (PLAN-004 §4.3 の1)。
    """
    ordered = list(items)
    ordered_prompts = [prompts[item.item_id] for item in ordered]
    to_response = response_builder(
        group, reference_rule, lesions=lesions, specificity_lesions=specificity_lesions
    )
    if group == t3_comparison.GROUP:
        if scorer is None:
            raise ConfigError(
                "comparison 群の本実行には強制選択採点器が要る(ADR-047)。"
                "execute が code/eval/engine.py の build_engines で用意する。"
            )
        choices = collect_forced_choices(ordered_prompts, scorer)
        texts = [forced_choice_response_text(choice) for choice in choices]
        responses = [
            to_response(item, choice.answer)
            for item, choice in zip(ordered, choices, strict=True)
        ]
        scoring = SCORING_FORCED_CHOICE
    else:
        texts = collect_responses(ordered_prompts, generator)
        responses = [
            to_response(item, parse_response(text, group, elicitation))
            for item, text in zip(ordered, texts, strict=True)
        ]
        scoring = SCORING_FREE_GENERATION

    metrics: dict[str, Any] = {
        "group": group,
        "scoring": scoring,
        "n_items": len(ordered),
        **metrics_by_reference_rule(responses, reference_rule),
    }
    if group == t3_comparison.GROUP:
        # 強制選択なら parse_fail / other_error は構造上 0(ADR-047 決定4)。
        # 0 でなければ実装バグ —— 合計 1.0 の検査に足す(PLAN-007 §4-4)。
        assert_collapsed_to_binary(metrics["by_reference_rule"])
        # 二値項目だけの話である(PLAN-001 §5.1)。**実測がこの理論値を
        # 超えていることを必ず確認する。**強制選択でも「常に Yes」に倒れうる。
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


def evaluate_pool(
    config: Mapping[str, Any],
    *,
    generator: Generator,
    scorer: ForcedChoiceScorer | None = None,
) -> list[BatchResult]:
    """評価プール全体をモデルに解かせる。

    答える問い: 「この config が宣言する全バッチの4値分解は何か」

    バッチの割り方・参照規則の検査・文面の出どころは、すべて --dry-run と
    **同じ関数**を通る。片方だけを変えると、配線確認で通った経路と本実行の
    経路が別物になる。違うのは応答が固定文字列かモデルの生成かだけである。

    `scorer` は二値群(comparison)の強制選択採点器である(ADR-047)。
    `comparison` を宣言した config で None のまま呼ぶと `evaluate_batch` が
    止める —— `execute` は `code/eval/engine.py` の `build_engines` で生成器と
    一緒に用意する(8B を二度読まない)。
    """
    batteries = list(require(config, "eval.batteries"))
    unknown = [group for group in batteries if group not in SUPPORTED_GROUPS]
    if unknown:
        raise ConfigError(
            f"群 {unknown} の項目生成は未実装。実装済みなのは {list(SUPPORTED_GROUPS)}。"
        )
    elicitation = require(config, "eval.elicitation")
    reject_unsupported_elicitation(elicitation, batteries)
    reference_rule = require(config, "eval.reference_rule")
    template_set = require(config, "data.eval_template_set")
    main_radius = require(config, "data.train_domain_max")

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
            group_items, group, reference_rule=reference_rule, main_radius=main_radius
        ):
            results.append(
                evaluate_batch(
                    name,
                    group,
                    batch_rule,
                    batch_items,
                    prompts=prompts,
                    generator=generator,
                    scorer=scorer,
                    elicitation=elicitation,
                    lesions=lesions,
                    specificity_lesions=specificity_lesions,
                )
            )
    return results


def total_items(results: Sequence[BatchResult]) -> int:
    """このプールで採点した項目数。

    答える問い: 「この実行は何項目を解いたか」

    **1箇所で数える。**`metrics_payload` の `pool.n_items` と `timing` の
    1項目あたり秒数が別々に数えると、片方だけバッチの取りこぼしを含んで
    ずれる —— そして秒数の側でずれても誰も気づかない。
    """
    return sum(result.metrics["n_items"] for result in results)


def adapter_provenance(adapter: str | None, *, condition: str) -> dict[str, Any]:
    """アダプタの出どころを引く。**評価の `seed` 欄はここから来る**(ADR-043 決定3)。

    答える問い: 「この4値分解は、どの訓練 run の、どのシードのアダプタに
    対するものか」

    アダプタは `runs/<id>/adapter/` に置かれる(ADR-043 決定2)ので、
    **その親の `metrics.json` が訓練 run の記録である。**シードを人手で
    渡さずにここから引くのは、`--seed 3` と実際に読んだアダプタが食い違う
    余地を消すためである —— 食い違っても数値は普通に出る。

    **病変条件の一致も見る。**`p2` の config で `ident` のアダプタを評価した
    run は、`rule_rate` が低く出て「病変が浅い」と読めてしまう。
    **これは取り違えであって結果ではない。**

    アダプタが無ければ `seed` は None である。**0 を置かない** ——
    「シード 0 で回した」と読める記録になる。
    """
    if adapter is None:
        return {"adapter": None, "seed": None, "train_run_id": None, "note": NO_ADAPTER_NOTE}
    train_dir = Path(adapter).parent
    try:
        payload = read_metrics(train_dir)
    except FileNotFoundError as exc:
        raise ConfigError(
            f"{ADAPTER_KEY}={adapter!r} の親に metrics.json が無い({train_dir})。"
            "アダプタは訓練 run の runs/<id>/adapter/ を指すこと(ADR-043 決定2)——"
            "そこから seed と lesion.condition を引く(同 決定3)。"
        ) from exc
    if payload.get("kind") != TRAIN_KIND:
        raise ConfigError(
            f"{train_dir} の metrics.json は kind={payload.get('kind')!r} であり "
            f"{TRAIN_KIND!r} ではない。訓練 run ではないディレクトリを指している。"
        )
    trained_condition = payload.get("lesion_condition")
    if trained_condition != condition:
        raise ConfigError(
            f"アダプタは lesion.condition={trained_condition!r} で訓練されているが、"
            f"この config は {condition!r} を宣言している。"
            "取り違えたまま回すと、rule_rate の低さが「病変が浅い」と読めてしまう。"
        )
    return {
        "adapter": adapter,
        "seed": payload.get("seed"),
        "train_run_id": payload.get("run_id"),
        "note": ADAPTER_NOTE,
    }


# E-5 (b) の coverage ブロックに添える注記(ADR-076 決定12)。
COVERAGE_RECORD_NOTE = (
    "被覆ラベルの K の出どころの記録である(ADR-076 決定12 = E-5 (b))。**正本は ADR-062 の (a)** "
    "—— code/analysis/frame.py は config.yaml の data.matched_manifests を lesion.condition で辿って "
    "K を読み、この記録と食い違えば止まる。adapter が null の run でも lesion.condition が K を決める。"
)


def pool_record(config: Mapping[str, Any], items_path: Path) -> dict[str, Any]:
    """metrics.json の `pool` ブロック(ADR-076 決定12 で manifest とハッシュを足した)。

    答える問い: 「この run が解いた項目集合は、どの manifest の、どのバイト列か」

    `items_sha256` は**解いたファイルそのもの**を畳む。ポッドは items.jsonl を config から
    生成し直す(`.gitignore`)ので、コミット済みの manifest の `files` と突き合わせれば
    「GPU の前に固定した項目集合を解いた」ことが run の記録だけから言える。

    **重みを読む前に `execute` が組む。**manifest が読めない config で生成を始めて、
    GPU 時間を使った後に metrics.json を書く段で落ちないようにする。
    `n_items` は採点の後に `metrics_payload` が足す(`total_items`。1箇所で数える)。
    """
    manifest = read_pool_manifest(config)
    return {
        "pool_id": require(config, "data.pool_id"),
        "items": str(items_path),
        "manifest": str(require(config, "eval.anchor_manifest")),
        "pairs_hash": manifest["pairs_hash"],
        "items_sha256": sha256_file(items_path),
    }


def coverage_record(config: Mapping[str, Any]) -> dict[str, Any]:
    """metrics.json の `coverage` ブロック(ADR-076 決定12 = E-5 (b))。

    答える問い: 「この run の被覆ラベルは、どの FT manifest の K で付くはずだったか」

    値は `eval_pool.find_condition_manifest` で読む —— `frame.py` が (a) で K を辿るのと
    **同じ規則**である。規則を書き写すと、記録と照合の相手が別の manifest を指しうる。
    """
    path, manifest = find_condition_manifest(config)
    return {
        "ft_manifest": str(path),
        "data_id": manifest["data_id"],
        "pairs_hash": manifest["coverage"]["pairs_hash"],
        "coverage_k": manifest["coverage"]["coverage_k"],
        "train_domain_hi": manifest["train_domain"]["hi"],
        "note": COVERAGE_RECORD_NOTE,
    }


def metrics_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    results: Sequence[BatchResult],
    *,
    run_id: str,
    pool: Mapping[str, Any],
    coverage: Mapping[str, Any],
    timing: Mapping[str, Any],
    adapter: Mapping[str, Any],
    forced_choice_candidates: Mapping[bool, Mapping[str, int | None]] | None = None,
) -> dict[str, Any]:
    """metrics.json の中身を組む。

    答える問い: 「この4値分解が、どの重みの、どの設定の、どの項目集合から
    出たかを、この1ファイルだけで言えるか」

    `lesion_condition` と `adapter` を並べて書く理由は NO_ADAPTER_NOTE。
    `adapter` は `adapter_provenance` が組む(`seed` もそこから来る。ADR-043 決定3)。

    `timing` を受け取るのは `execute` が測った区間だからである(組み立てる
    側では生成の開始も終了も見えない)。**中身は `code/artifacts.py` の
    `timing_record` が決める。**

    `forced_choice_candidates` は二値群の器械の記録(候補綴り -> トークン id。
    採らなかった綴りは None。ADR-047 実装ノート 4)。**重みを読んだ実行にしか
    無い** —— 生成器を差し替えたテストや、そもそも comparison を宣言していない
    config では None のままで、`forced_choice` の欄自体が出ない。欄が無いことを
    「6綴り全部を使った」と読まないよう、`FORCED_CHOICE_NOTE` を添える。

    `pool` と `coverage` は ADR-076 決定12(E-5 (b))の記録である(`pool_record` /
    `coverage_record`)。**桁数掃引の run(code/eval/sweep.py)には掛けない**(被覆ラベルを使わない)。
    閾値掃引の run(`threshold_sweep_payload`)は同じ 2 ブロックを持つ。
    """
    return {
        "run_id": run_id,
        "kind": EVAL_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "seed": adapter["seed"],
        "adapter": adapter["adapter"],
        "adapter_train_run_id": adapter["train_run_id"],
        "adapter_note": adapter["note"],
        "generation": settings.as_dict(),
        "elicitation": require(config, "eval.elicitation"),
        "primary_reference_rule": require(config, "eval.reference_rule"),
        "pool": {**pool, "n_items": total_items(results)},
        "coverage": dict(coverage),
        "timing": timing,
        "by_batch": {result.name: result.metrics for result in results},
        **forced_choice_block(forced_choice_candidates),
    }


def forced_choice_block(
    candidates: Mapping[bool, Mapping[str, int | None]] | None,
) -> dict[str, Any]:
    """metrics.json の `forced_choice` 欄(候補綴り -> トークン id。ADR-047 実装ノート 4)。

    答える問い: 「この run の Yes/No は、どの綴りのトークンを周辺化したものか」

    **重みを読んだ実行にしか無い**(`metrics_payload` の docstring)。None なら欄ごと出さない。
    固定オフセットの経路と閾値掃引の経路が同じ形で書く。
    """
    if candidates is None:
        return {}
    return {
        "forced_choice": {
            "candidates": candidate_record(candidates),
            "note": FORCED_CHOICE_NOTE,
        }
    }


def run_header_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt の先頭の 6 行(どの run が、どの重みで、何件を解いたか)。

    答える問い: 「この実行は、どの重みの、どの設定で、どの項目集合を解いたのか」

    固定オフセットの経路(`report_lines`)と閾値掃引の経路(`threshold_sweep_report_lines`)が
    共有する。アダプタ無しの注記(NO_ADAPTER_NOTE)は必ずここに出る。
    """
    generation = payload["generation"]
    return [
        f"run_id: {payload['run_id']}",
        f"model: {generation['model_name']} @ {generation['revision']} "
        f"({generation['dtype']} on {generation['device']})",
        f"生成: max_new_tokens={generation['max_new_tokens']} "
        f"temperature={generation['temperature']} do_sample={generation['do_sample']} "
        f"chat_template={generation['chat_template']} "
        f"batch_size={generation['batch_size']}",
        f"lesion.condition: {payload['lesion_condition']} / seed: {payload['seed']} / "
        f"adapter: {payload['adapter']}",
        f"注意: {payload['adapter_note']}",
        f"項目: {payload['pool']['n_items']} 件 <- {payload['pool']['items']}",
    ]


def forced_choice_lines(payload: Mapping[str, Any]) -> list[str]:
    """強制選択の候補綴りの 1 行(`forced_choice` 欄が無い run では出さない)。"""
    forced_choice = payload.get("forced_choice")
    if forced_choice is None:
        return []
    return [
        "強制選択の候補綴り(null は不採用): "
        + json.dumps(forced_choice["candidates"], ensure_ascii=False)
    ]


def report_lines(payload: Mapping[str, Any]) -> list[str]:
    """log.txt と標準出力に出す行。

    答える問い: 「この実行は何を、どの重みで、どう解いたのか」

    **--dry-run の警告文は流用しない**(PLAN-004 §4.3 の4)。ここの数値は
    実験結果であり results/ に書いてよい。代わりに、読んだ重みがアダプタ
    無しであることを必ず1行出す(NO_ADAPTER_NOTE。`run_header_lines`)。
    """
    lines = [
        *run_header_lines(payload),
        f"引き出し方: {payload['elicitation']} / "
        f"主要参照規則: {payload['primary_reference_rule']}",
        timing_line(payload["timing"]),
        *forced_choice_lines(payload),
    ]
    for name, batch in payload["by_batch"].items():
        block = batch["by_reference_rule"][batch["primary_reference_rule"]]
        lines.append(
            f"[{name}] group={batch['group']} scoring={batch['scoring']} "
            f"rule={batch['primary_reference_rule']} "
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
    scorer: ForcedChoiceScorer | None = None,
    now: datetime | None = None,
) -> Path:
    """本実行。成果物を `runs/<id>/` に書き、その dir を返す。

    答える問い: 「この数値が、どのコードの、どの設定の、いつの実行から
    出たかを後から言えるか」

    **来歴を生成の前に書く。**生成が途中で落ちても config / git / 環境の
    記録は残る。生成が終わってから書くと、落ちた実行について「どの版で
    何を試したのか」が何も残らない。

    `generator`(数値群 T1 / T2 / specificity)と `scorer`(二値群 comparison の
    強制選択採点。ADR-047)は差し替え可能である(PLAN-004 §4.3 の1)。
    **`generator` が None のときだけ重みを読む** —— そのとき `code/eval/engine.py`
    の `build_engines` が1度の読み込みで両方を作る(8B を二度読むと 4090 に
    載らない)。GPU の無い環境のテストは両方に固定の関数を渡す。

    **アダプタは重みを読む前に引く**(ADR-043 決定3)。`model.adapter` が
    指す訓練 run の記録から `seed` と `lesion.condition` を取り、条件が
    食い違っていればそこで止まる —— 取り違えたまま回しても数値は普通に出る。

    **壁時計時間を3区間で測る**(ADR-040 決定6)。重みの読み込みと生成を
    分けるのは、8B の読み込みが分単位で、そこを混ぜると「1項目あたり何秒か」が
    読めなくなるからである。`eval.batch_size` の値はこの記録から決まる。
    生成器を渡された場合(テスト)は重みを読まないので読み込みの区間はほぼ 0 になる。

    **閾値掃引の宣言も掃引のプールも、重みを読む前・run ディレクトリを作る前に止める**
    (PLAN-026 §4.5)。項目を初めて読むのは `evaluate_pool` —— 重みを読み、run ディレクトリを
    作った後である。そこで止まると、中身の無い run ディレクトリと GPU 時間が残る。
    """
    refuse_declared_threshold_sweep(config)
    check_pool_kind(config, read_pool_manifest(config), threshold_sweep=False)
    settings = load_generation_settings(config)
    adapter = adapter_provenance(
        declared_adapter(config), condition=require(config, "lesion.condition")
    )
    # 項目集合と K の出どころも重みを読む前に引く(ADR-076 決定12)。読めない config で
    # 生成を始めると、GPU 時間を使ってから metrics.json の段で落ちる。
    pool = pool_record(config, pool_items_path(config))
    coverage = coverage_record(config)
    started = now or utc_now()
    run_started = monotonic_seconds()
    target = prepare_run_dir(config, explicit=run_dir, now=started)
    write_config_copy(target, config_path)
    write_git_sha(target)
    write_env(target)

    load_started = monotonic_seconds()
    forced_choice_candidates: Mapping[bool, Mapping[str, int | None]] | None = None
    if generator is None:
        engines = build_engines(settings, adapter=adapter["adapter"])
        generator = engines.generator
        # **渡された scorer を捨てない。**None のときだけ埋める —— 生成器だけを
        # 差し替えたい呼び出し(数値群の再解析など)で、明示した採点器が黙って
        # 上書きされると、何で採ったのかが記録と食い違う。
        if scorer is None:
            scorer = engines.scorer
        forced_choice_candidates = engines.forced_choice_candidates
    model_load_seconds = elapsed_seconds(load_started)

    generation_started = monotonic_seconds()
    results = evaluate_pool(config, generator=generator, scorer=scorer)
    generation_seconds = elapsed_seconds(generation_started)

    for result in results:
        write_predictions(target, result.name, result.predictions)
    ended = utc_now()
    payload = metrics_payload(
        config,
        settings,
        results,
        run_id=target.name,
        pool=pool,
        coverage=coverage,
        adapter=adapter,
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=model_load_seconds,
            generation_seconds=generation_seconds,
            n_items=total_items(results),
        ),
        forced_choice_candidates=forced_choice_candidates,
    )
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=ended)
    lines = report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


# --------------------------------------------------------------------------
# 閾値掃引(R8・S)の記録の経路(PLAN-026 §4.5 = I4)
# --------------------------------------------------------------------------

# metrics.json の種別。**4 値分解を持たない** —— 4 値分解を読む集約(`code/analysis/aggregate.py`)は
# `battery_eval` 以外を数えずに飛ばし、`code/analysis/frame.py` は止まる。
THRESHOLD_SWEEP_KIND = "threshold_sweep"

# predictions/ のファイル名の頭(`threshold_sweep.<タスク型>.jsonl`)。
THRESHOLD_SWEEP_PREDICTIONS_PREFIX = "threshold_sweep"

# metrics.json の threshold_sweep 欄と log.txt に添える注記(PLAN-026 §4.5 読み2・読み3)。
THRESHOLD_SWEEP_NOTE = (
    "閾値掃引の項目は 4 値分解に入れていない(PLAN-026 §3.2・§4.5 読み2)。"
    "predictions/ の truth と answer は記録であって分類ではなく、この run は率(correct を含む)を"
    "1 つも出さない。遠いオフセットの correct と揃え方 (a) の y(ADR-079 決定1)は predictions/ から"
    "後処理(I5)で作る。answer は判定規則(choose_from_logprobs。同点は No)の答えのまま。"
    "上位 k の欄はまだ無い(I10)。"
)


@dataclass(frozen=True)
class ThresholdSweepPool:
    """閾値掃引の run が解く項目と、その来歴。

    答える問い: 「この掃引の項目は、どの腕の、どの併合セルの、どの θ か」

    `cell_of` は item_id -> 併合セル。manifest の `fill.cells` の組と config の `eval.cells` から
    `sweep_pool.sweep_cells`(生成と同じ関数)で引き直したもので、**セルの名前を解析しない**。
    """

    settings: sweep_pool.SweepSettings
    manifest: dict[str, Any]
    items: list[Item]
    cell_of: dict[str, sweep_pool.SweepCell]


def threshold_sweep_fill_mismatches(
    config: Mapping[str, Any], settings: sweep_pool.SweepSettings, fill: Mapping[str, Any]
) -> list[str]:
    """manifest の `fill` のうち、config の宣言と食い違う欄を並べる。

    答える問い: 「このプールは、この config が宣言した腕・θ・タスク型・極性・組の数・シードで
    作られたか」
    """
    expected: dict[str, Any] = {
        "arm": settings.arm,
        "threshold_offsets": list(settings.offsets),
        "task_types": list(settings.task_types),
        "polarities": list(sweep_pool.POLARITIES),
        "pairs_per_cell": settings.pairs_per_cell,
    }
    mismatches = [
        f"fill.{key}={fill.get(key)!r}(config からは {value!r})"
        for key, value in expected.items()
        if fill.get(key) != value
    ]
    seed = require(config, "eval.pool_seed")
    recorded_seed = (fill.get("selection") or {}).get("seed")
    if recorded_seed != seed:
        mismatches.append(f"fill.selection.seed={recorded_seed!r}(eval.pool_seed は {seed!r})")
    return mismatches


def threshold_sweep_cells(
    config: Mapping[str, Any], settings: sweep_pool.SweepSettings, fill: Mapping[str, Any]
) -> dict[sweep_pool.SweepCell, list[Pair]]:
    """manifest の併合セルの組を、config のセル表から組み直した併合セルに対応づける。

    答える問い: 「このプールの各組は、どの(タスク型 × 既知性 × carry)の併合セルのものか」

    併合セルは `sweep_pool.sweep_cells`(生成と同じ関数)で config の `eval.cells` から組み直し、
    manifest の `fill.cells` と**名前の集合・元のセル・組の数**を照合する。名前は照合にだけ使い、
    タスク型・既知性・carry を名前から読み取らない。
    """
    merged = sweep_pool.sweep_cells(load_cells(config), settings.task_types)
    recorded: Mapping[str, Any] = fill.get("cells") or {}
    expected_names = [cell.name for cell in merged]
    if set(recorded) != set(expected_names):
        raise ConfigError(
            f"manifest の fill.cells {sorted(recorded)} が、config のセル表から組んだ併合セル "
            f"{sorted(expected_names)} と違う。別のセル表で作ったプールを読んでいる。"
        )
    pairs_by_cell: dict[sweep_pool.SweepCell, list[Pair]] = {}
    for cell in merged:
        entry = recorded[cell.name]
        source_cells = list(entry.get("source_cells") or [])
        if source_cells != list(cell.source_cells):
            raise ConfigError(
                f"併合セル {cell.name!r} の元のセルが manifest では {source_cells}、"
                f"config からは {list(cell.source_cells)}"
            )
        pairs = [(int(pair[0]), int(pair[1])) for pair in entry.get("pairs") or []]
        if len(pairs) != settings.pairs_per_cell or len(set(pairs)) != len(pairs):
            raise ConfigError(
                f"併合セル {cell.name!r} の組が {len(pairs)} 件(相異なる {len(set(pairs))} 件)。"
                f"掃引は相異なる {settings.pairs_per_cell} 組を要る"
            )
        pairs_by_cell[cell] = pairs
    return pairs_by_cell


def _sweep_cell_of_item(
    item: Item,
    cell_by_pair: Mapping[tuple[str, Pair], sweep_pool.SweepCell],
    offsets: Sequence[int],
) -> sweep_pool.SweepCell:
    """この掃引項目が属する併合セル。項目が宣言した掃引の形をしていなければ止める。

    答える問い: 「この項目は、manifest の併合セルの組を、宣言した θ の閾値 T = t + θ で尋ねているか」
    """
    if item.group != t3_comparison.GROUP:
        raise ConfigError(
            f"{item.item_id}: 掃引の項目は {t3_comparison.GROUP!r} の群に限る(群 {item.group!r})"
        )
    task_type = t3_comparison.task_type_of(item.category)
    pair = (item.operands[0], item.operands[1])
    cell = cell_by_pair.get((task_type, pair))
    if cell is None:
        raise ConfigError(f"{item.item_id}: 組 {pair} は manifest の {task_type} の併合セルに無い")
    theta = item.params.get("threshold_offset")
    if theta not in offsets:
        raise ConfigError(f"{item.item_id}: θ={theta!r} は宣言した水準 {list(offsets)} に無い")
    expected = t3_comparison.sweep_threshold(t3_comparison.item_total(item), int(theta))
    if item.params.get("threshold") != expected:
        raise ConfigError(
            f"{item.item_id}: 閾値 {item.params.get('threshold')!r} が T = t + θ = {expected} でない"
        )
    return cell


def load_threshold_sweep_pool(config: Mapping[str, Any]) -> ThresholdSweepPool:
    """閾値掃引のプールを読み、この config の宣言とそろっていることを確かめる。

    答える問い: 「この掃引の run が解く項目は、宣言した腕の全(併合セル × 極性 × θ)を
    ちょうど 1 度ずつ埋めているか」

    **止める食い違い(どれも重みを読む前)**:
      - 宣言が無い / anchor が掃引のプールでない(`check_pool_kind`)/ pool_id・群の宣言
        (`_read_pool_items`。`eval.batteries` は comparison だけでなければならない)
      - manifest の fill の腕・θ・タスク型・極性・組の数・シードが config と違う
      - 併合セルが config のセル表から組んだものと違う(`threshold_sweep_cells`)
      - 項目が比較の群でない / 組が manifest の併合セルに無い / θ が水準に無い / 閾値が T = t + θ でない
      - **完全性**: どの(併合セル × 極性 × θ)も、そのセルの組とちょうど一致する。1 項目欠けると、
        その組の θ の曲線が 1 点欠けたまま当てはめ(I5)に入る
    """
    arm = declared_threshold_sweep_arm(config)
    if arm is None:
        raise ConfigError(
            f"閾値掃引の経路は {THRESHOLD_SWEEP_ARM_KEY} の宣言を要る(PLAN-026 §4.5 読み1)。"
            "固定オフセットの run は execute / dry_run の経路である。"
        )
    items = _read_pool_items(config, threshold_sweep=True)
    manifest = read_pool_manifest(config)
    settings = sweep_pool.load_sweep_settings(config, arm)
    fill = manifest["fill"]
    mismatches = threshold_sweep_fill_mismatches(config, settings, fill)
    if mismatches:
        raise ConfigError(
            f"eval.anchor_manifest の掃引プールは、この config が宣言した腕 {arm!r} のものではない: "
            + " / ".join(mismatches)
        )
    pairs_by_cell = threshold_sweep_cells(config, settings, fill)
    cell_by_pair: dict[tuple[str, Pair], sweep_pool.SweepCell] = {}
    for cell, pairs in pairs_by_cell.items():
        for pair in pairs:
            if (cell.task_type, pair) in cell_by_pair:
                raise ConfigError(f"組 {pair} が {cell.task_type} の 2 つの併合セルにある")
            cell_by_pair[(cell.task_type, pair)] = cell

    cell_of: dict[str, sweep_pool.SweepCell] = {}
    solved: dict[tuple[str, str, int], list[Pair]] = {}
    for item in items:
        cell = _sweep_cell_of_item(item, cell_by_pair, settings.offsets)
        cell_of[item.item_id] = cell
        key = (
            cell.name,
            t3_comparison.polarity_of(item.category),
            int(item.params["threshold_offset"]),
        )
        solved.setdefault(key, []).append((item.operands[0], item.operands[1]))
    for cell, pairs in pairs_by_cell.items():
        for polarity in sweep_pool.POLARITIES:
            for theta in settings.offsets:
                got = sorted(solved.get((cell.name, polarity, theta), []))
                if got != sorted(pairs):
                    raise ConfigError(
                        f"({cell.name}, {polarity}, θ={theta}) の項目の組が manifest のそのセルの "
                        f"{len(pairs)} 組とそろっていない(項目 {len(got)} 件)。1 組でも欠けると、"
                        "その組の θ の曲線が 1 点欠けたまま当てはめに入る"
                    )
    return ThresholdSweepPool(settings=settings, manifest=manifest, items=items, cell_of=cell_of)


def threshold_sweep_prompts(config: Mapping[str, Any], pool: ThresholdSweepPool) -> dict[str, str]:
    """掃引の項目の文面(item_id -> プロンプト)。

    答える問い: 「掃引の項目は、固定オフセットの比較項目と同じ文面の出どころで尋ねられるか」

    文面は固定オフセットの経路と**同じ関数**で組む(`load_group_templates` + `RENDERERS`)。
    ① の前置き(I6)や (d) のテンプレート(I8)が被さる場所を 2 つにしない(PLAN-026 §4.5 読み4)。
    **重みを読む前に呼ぶ** —— テンプレートの欠けや引き出し方の食い違いで、run ディレクトリを
    作った後に止まらないようにする。
    """
    reject_unsupported_elicitation(
        require(config, "eval.elicitation"), list(require(config, "eval.batteries"))
    )
    templates = load_group_templates(
        config, t3_comparison.GROUP, require(config, "data.eval_template_set")
    )
    render = RENDERERS[t3_comparison.GROUP]
    return {item.item_id: render(item, templates) for item in pool.items}


def threshold_sweep_record(
    item: Item, *, cell: sweep_pool.SweepCell, prompt: str, choice: ForcedChoice
) -> dict[str, Any]:
    """掃引の 1 項目を predictions/ に残す形にする(PLAN-026 §4.5 読み2)。

    答える問い: 「この組・この極性・この θ で、モデルは Yes と No にどれだけ倒れたか」

    **分類しない**(`classify` を通さない)。`truth` は比較の真値(`comparison_answer`)、`answer` は
    判定規則の答え(`choose_from_logprobs`。同点は No)で、どちらも記録である —— 非判別項目では
    真値と規則値が一致するので、4 値のどれかに落とすこと自体が定義できない。
    `yes_logp` / `no_logp` は採点器が返した値そのもの(候補綴りをまたいで周辺化した対数確率)。
    """
    total = t3_comparison.item_total(item)
    polarity = t3_comparison.polarity_of(item.category)
    threshold = int(item.params["threshold"])
    return {
        "item_id": item.item_id,
        "category": item.category,
        "task_type": cell.task_type,
        "polarity": polarity,
        "sweep_cell": cell.name,
        "coverage": cell.coverage,
        "carry": item.carry,
        "operands": list(item.operands),
        "t": total,
        "threshold": threshold,
        "threshold_offset": int(item.params["threshold_offset"]),
        "prompt": prompt,
        "response": forced_choice_response_text(choice),
        "answer": choice.answer,
        "truth": t3_comparison.comparison_answer(total, polarity, threshold),
        "yes_logp": choice.yes_logprob,
        "no_logp": choice.no_logprob,
    }


def threshold_sweep_predictions_name(task_type: str) -> str:
    """predictions/ のファイル名(拡張子なし)。タスク型ごとに 1 ファイル。"""
    return f"{THRESHOLD_SWEEP_PREDICTIONS_PREFIX}.{task_type}"


def evaluate_threshold_sweep(
    pool: ThresholdSweepPool, *, prompts: Mapping[str, str], scorer: ForcedChoiceScorer
) -> dict[str, list[dict[str, Any]]]:
    """掃引の項目に強制選択の forward を掛け、項目ごとの記録を返す。**これは実験結果である。**

    答える問い: 「各タスク型の掃引の項目で、モデルは Yes と No にどれだけ倒れたか」

    forward はタスク型ごとに、**項目の並びのまま**掛ける(PLAN-026 §4.5 読み5。batch の組み方は
    この並びと `eval.batch_size` で決まる)。本数の検査は `collect_forced_choices`。
    返り値は {predictions の名前: 行}。4 値分解・参照規則・率はここに無い。
    """
    records: dict[str, list[dict[str, Any]]] = {}
    for task_type in pool.settings.task_types:
        items = [
            item for item in pool.items if t3_comparison.task_type_of(item.category) == task_type
        ]
        ordered_prompts = [prompts[item.item_id] for item in items]
        choices = collect_forced_choices(ordered_prompts, scorer)
        records[threshold_sweep_predictions_name(task_type)] = [
            threshold_sweep_record(
                item, cell=pool.cell_of[item.item_id], prompt=prompt, choice=choice
            )
            for item, prompt, choice in zip(items, ordered_prompts, choices, strict=True)
        ]
    return records


def count_records(records: Mapping[str, Sequence[Any]]) -> int:
    """掃引の run が記録した項目数(`total_items` の掃引版。1 箇所で数える)。"""
    return sum(len(rows) for rows in records.values())


def threshold_sweep_counts(pool: ThresholdSweepPool) -> dict[str, dict[str, dict[str, int]]]:
    """(併合セル × 極性 × θ)ごとの項目数。θ は JSON の鍵にするので文字列にする。

    答える問い: 「この run は、どの併合セルの、どの極性・θ を何件解いたか」

    並びは項目の並び(タスク型 → 併合セル → 極性 → θ。`sweep_pool` の生成の順)。
    """
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for item in pool.items:
        by_polarity = counts.setdefault(pool.cell_of[item.item_id].name, {})
        by_theta = by_polarity.setdefault(t3_comparison.polarity_of(item.category), {})
        theta = str(item.params["threshold_offset"])
        by_theta[theta] = by_theta.get(theta, 0) + 1
    return counts


def threshold_sweep_payload(
    config: Mapping[str, Any],
    settings: GenerationSettings,
    pool: ThresholdSweepPool,
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    run_id: str,
    pool_block: Mapping[str, Any],
    coverage: Mapping[str, Any],
    timing: Mapping[str, Any],
    adapter: Mapping[str, Any],
    forced_choice_candidates: Mapping[bool, Mapping[str, int | None]] | None = None,
) -> dict[str, Any]:
    """閾値掃引の run の metrics.json を組む。**率を 1 つも出さない。**

    答える問い: 「この掃引の記録が、どの重みの、どの設定の、どの項目集合の、どの θ から
    出たかを、この 1 ファイルだけで言えるか」

    来歴(`generation`・`adapter`・`pool`・`coverage`・`timing`・`forced_choice`)は固定オフセットの
    経路と同じ関数で組む。`threshold_sweep` 欄は腕・θ の水準・タスク型・極性・組の数・元の
    評価プールの `pairs_hash`・(併合セル × 極性 × θ)ごとの件数・predictions のファイルごとの行数。
    """
    fill = pool.manifest["fill"]
    return {
        "run_id": run_id,
        "kind": THRESHOLD_SWEEP_KIND,
        "experiment_id": require(config, "experiment.id"),
        "lesion_condition": require(config, "lesion.condition"),
        "seed": adapter["seed"],
        "adapter": adapter["adapter"],
        "adapter_train_run_id": adapter["train_run_id"],
        "adapter_note": adapter["note"],
        "generation": settings.as_dict(),
        "pool": {**pool_block, "n_items": count_records(records)},
        "coverage": dict(coverage),
        "timing": timing,
        "threshold_sweep": {
            "arm": pool.settings.arm,
            "threshold_offsets": list(pool.settings.offsets),
            "task_types": list(pool.settings.task_types),
            "polarities": list(sweep_pool.POLARITIES),
            "pairs_per_cell": pool.settings.pairs_per_cell,
            "source_pool_pairs_hash": fill["source_pool_pairs_hash"],
            "n_items_by_cell": threshold_sweep_counts(pool),
            "predictions": {name: len(rows) for name, rows in records.items()},
            "note": THRESHOLD_SWEEP_NOTE,
        },
        **forced_choice_block(forced_choice_candidates),
    }


def threshold_sweep_report_lines(payload: Mapping[str, Any]) -> list[str]:
    """閾値掃引の run の log.txt と標準出力に出す行。**率を出さない。**

    答える問い: 「この掃引の run は何を、どの重みで、どの θ で解いたのか」
    """
    sweep = payload["threshold_sweep"]
    return [
        *run_header_lines(payload),
        timing_line(payload["timing"]),
        *forced_choice_lines(payload),
        f"閾値掃引: 腕={sweep['arm']} θ={sweep['threshold_offsets']} "
        f"タスク型={sweep['task_types']} 極性={sweep['polarities']} "
        f"組/併合セル={sweep['pairs_per_cell']} 併合セル={len(sweep['n_items_by_cell'])} 個",
        *(f"[{name}] n={n}" for name, n in sweep["predictions"].items()),
        f"注意: {sweep['note']}",
    ]


def execute_threshold_sweep(
    config: Mapping[str, Any],
    *,
    config_path: Path,
    run_dir: Path | None,
    scorer: ForcedChoiceScorer | None = None,
    now: datetime | None = None,
) -> Path:
    """閾値掃引の本実行。成果物を `runs/<id>/` に書き、その dir を返す(PLAN-026 §4.5)。

    答える問い: 「この掃引の記録が、どのコードの、どの設定の、いつの実行から出たかを
    後から言えるか」

    **検査はすべて run ディレクトリを作る前・重みを読む前に済ませる** —— 宣言とプールの種類・
    manifest と config の照合・完全性(`load_threshold_sweep_pool`)、文面と引き出し方
    (`threshold_sweep_prompts`)、アダプタの出どころ、項目集合と K の記録。
    `scorer` は差し替え可能で、**None のときだけ重みを読む**(`build_engines`。生成器は使わない)。
    来歴を forward の前に書き、区間を 3 つに分けて測るのは `execute` と同じ理由である。
    """
    pool = load_threshold_sweep_pool(config)
    prompts = threshold_sweep_prompts(config, pool)
    settings = load_generation_settings(config)
    adapter = adapter_provenance(
        declared_adapter(config), condition=require(config, "lesion.condition")
    )
    pool_block = pool_record(config, pool_items_path(config))
    coverage = coverage_record(config)
    started = now or utc_now()
    run_started = monotonic_seconds()
    target = prepare_run_dir(config, explicit=run_dir, now=started)
    write_config_copy(target, config_path)
    write_git_sha(target)
    write_env(target)

    load_started = monotonic_seconds()
    forced_choice_candidates: Mapping[bool, Mapping[str, int | None]] | None = None
    if scorer is None:
        engines = build_engines(settings, adapter=adapter["adapter"])
        scorer = engines.scorer
        forced_choice_candidates = engines.forced_choice_candidates
    model_load_seconds = elapsed_seconds(load_started)

    generation_started = monotonic_seconds()
    records = evaluate_threshold_sweep(pool, prompts=prompts, scorer=scorer)
    generation_seconds = elapsed_seconds(generation_started)

    for name, rows in records.items():
        write_predictions(target, name, rows)
    ended = utc_now()
    payload = threshold_sweep_payload(
        config,
        settings,
        pool,
        records,
        run_id=target.name,
        pool_block=pool_block,
        coverage=coverage,
        adapter=adapter,
        timing=timing_record(
            started=started,
            ended=ended,
            total_seconds=elapsed_seconds(run_started),
            model_load_seconds=model_load_seconds,
            generation_seconds=generation_seconds,
            n_items=count_records(records),
        ),
        forced_choice_candidates=forced_choice_candidates,
    )
    write_metrics(target, payload)
    write_timestamps(target, started=started, ended=ended)
    lines = threshold_sweep_report_lines(payload)
    write_log(target, lines)
    for line in lines:
        print(line)
    return target


def dry_run_forced_choice_scorer(answer: bool) -> ForcedChoiceScorer:
    """定数の答えを返す強制選択採点器(配線確認用)。**実験の刺激でも結果でもない。**

    答える問い: 「記録の組み立ては、どちらの答えでも全項目を通るか」

    選んだ側に log 1 = 0、選ばなかった側に log 0 = -inf を置く(決定的な常答戦略)。
    dry-run は何も書かないので、この値はどこにも残らない。
    """
    choice = ForcedChoice(
        answer=answer,
        yes_logprob=0.0 if answer else -math.inf,
        no_logprob=-math.inf if answer else 0.0,
    )

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        return [choice for _ in prompts]

    return scorer


def threshold_sweep_dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    """重みを読まずに掃引の経路の配線を確かめる。**実験ではない。**

    答える問い: 「宣言 → 掃引プール → 照合 → 文面 → 記録の組み立て は繋がっているか」

    本実行と**同じ関数**で項目を読み(検査もすべて同じ)、文面を組み、定数の答え
    (`DRY_RUN_FORCED_CHOICES`)で記録の組み立てを 1 度ずつ通す。8,160 のプロンプトを全部は
    返さない(category ごとに最初の 1 つ)。**率は出さない**(本実行が出さないので)。
    """
    pool = load_threshold_sweep_pool(config)
    prompts = threshold_sweep_prompts(config, pool)
    rows_by_response = {
        label: {
            name: len(rows)
            for name, rows in evaluate_threshold_sweep(
                pool, prompts=prompts, scorer=dry_run_forced_choice_scorer(answer)
            ).items()
        }
        for label, answer in DRY_RUN_FORCED_CHOICES.items()
    }
    examples: dict[str, str] = {}
    for item in pool.items:
        examples.setdefault(item.category, prompts[item.item_id])
    return {
        "n_items": len(pool.items),
        "items_source": str(pool_items_path(config)),
        "arm": pool.settings.arm,
        "threshold_offsets": list(pool.settings.offsets),
        "task_types": list(pool.settings.task_types),
        "n_items_by_cell": threshold_sweep_counts(pool),
        "predictions_by_response": rows_by_response,
        "example_prompts": examples,
    }


def print_threshold_sweep_dry_run(report: Mapping[str, Any]) -> None:
    """掃引の配線確認の報告を出す。**この警告文を本実行に流用しない**(§4.3 の4)。"""
    print("=" * 72)
    print("--dry-run: 閾値掃引の配線確認。**実験ではない。**モデルは1度も呼ばれていない。")
    print("ここに出る数値は組合せ論的な件数であって実験結果ではない(CLAUDE.md §2)。")
    print("=" * 72)
    print(f"項目数: {report['n_items']} <- {report['items_source']}")
    print(
        f"腕: {report['arm']} / θ: {report['threshold_offsets']} / "
        f"タスク型: {report['task_types']}"
    )
    for cell, by_polarity in report["n_items_by_cell"].items():
        print(
            f"  {cell}: "
            + " / ".join(
                f"{polarity} {sum(by_theta.values())} 件(θ {len(by_theta)} 水準)"
                for polarity, by_theta in by_polarity.items()
            )
        )
    for category, prompt in report["example_prompts"].items():
        print(f"[{category}] prompt(例): {prompt}")
    print(json.dumps(report["predictions_by_response"], ensure_ascii=False, indent=2))


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
    # 経路は config の宣言で決める(PLAN-026 §4.5 読み1)。anchor の manifest の中身から推測しない ——
    # 食い違いはどちらの経路でも重みを読む前に止まる(`check_pool_kind`)。
    threshold_sweep_arm = declared_threshold_sweep_arm(config)
    if args.dry_run:
        if args.run_dir is not None:
            # 黙って無視すると「書いたつもり」が残る。--dry-run は何も書かない。
            parser.error("--run-dir は本実行の引数である(--dry-run は何も書かない)")
        if threshold_sweep_arm is None:
            print_dry_run(dry_run(config))
        else:
            print_threshold_sweep_dry_run(threshold_sweep_dry_run(config))
        return 0

    if threshold_sweep_arm is None:
        execute(config, config_path=args.config, run_dir=args.run_dir)
    else:
        execute_threshold_sweep(config, config_path=args.config, run_dir=args.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
