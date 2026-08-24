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
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from code.config import ConfigError, load_config, require
from code.data_gen.battery_items import Item
from code.eval.battery import g6_comparison
from code.eval.parsers import boolean as boolean_parser
from code.eval.parsers import cot as cot_parser
from code.eval.scoring import (
    ItemResponse,
    constant_answer_baseline,
    metrics_by_reference_rule,
    validate_reference_rule,
)
from code.lesion import Lesion, reference_lesions_from_config

# 配線確認に使う固定応答。**実験の刺激ではない。**
# 「肯定を返すモデル」「否定を返すモデル」「読めない出力を返すモデル」の3通りが
# correct / rule / other_error / parse_fail のどこに落ちるかを見るためだけのもの。
DRY_RUN_RESPONSES: dict[str, str] = {
    "affirmative": "はい",
    "negative": "いいえ",
    "unreadable": "よくわかりません",
}

# repo ルートからの相対で解決する。カレントディレクトリに依存させない
# (ポッド上では /workspace 配下から起動されるため)。
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "configs" / "templates"

DIRECT = "direct"
COT = "cot"


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


def build_dry_run_items(config: Mapping[str, Any], lesions: Mapping[str, Lesion]) -> list[Item]:
    """配線確認用の項目を config の明示リストから作る。

    答える問い: 「サンプリングの決定を待たずに、経路を通せるか」

    **ここでプールをサンプリングしない。**被覆層(id / interp / extrap)の
    セルをどう埋めるかは未決定であり(STATE.md の承認待ち)、
    エージェントが勝手に決めてよい事柄ではない(CLAUDE.md §8)。
    """
    items: list[Item] = []
    for entry in require(config, "eval.dry_run_items"):
        items.extend(
            g6_comparison.build_items(
                [(entry["a"], entry["b"])],
                pool_id=str(entry.get("pool_id", "smoke")),
                polarity=entry["polarity"],
                threshold_offset=entry["threshold_offset"],
                reference_lesions=lesions,
            )
        )
    return items


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


def dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    """モデルを読まずに配線を確かめる。

    答える問い: 「config → 項目 → プロンプト → パーサ → 採点 は繋がっているか」

    返り値は metrics.json と同じ形だが、**実験結果ではない。**
    固定応答に対する分解であり、モデルは1度も呼ばれていない。
    """
    batteries = require(config, "eval.batteries")
    if list(batteries) != [g6_comparison.GROUP]:
        raise ConfigError(
            f"--dry-run で実行できるのは {[g6_comparison.GROUP]} だけ。要求: {list(batteries)}。"
            "G1〜G5 の項目構成は未実装(被覆層のセルの決め方が未決定)。"
        )
    elicitation = require(config, "eval.elicitation")
    reference_rule = require(config, "eval.reference_rule")
    template_set = require(config, "data.eval_template_set")

    lesions = build_reference_lesions(config)
    validate_reference_rule(reference_rule, lesions[reference_rule], list(lesions))
    templates = load_templates(template_set, g6_comparison.GROUP)
    items = build_dry_run_items(config, lesions)

    report: dict[str, Any] = {"n_items": len(items), "prompts": [], "by_response": {}}
    for item in items:
        report["prompts"].append(g6_comparison.render_prompt(item, templates))

    for label, text in DRY_RUN_RESPONSES.items():
        parsed = parse_boolean_response(text, elicitation)
        responses: Sequence[ItemResponse] = [
            g6_comparison.to_response(item, parsed, lesions) for item in items
        ]
        metrics = metrics_by_reference_rule(responses, reference_rule)
        metrics["constant_answer_baselines"] = {
            "always_yes": constant_answer_baseline(responses, True, reference_rule).as_dict(),
            "always_no": constant_answer_baseline(responses, False, reference_rule).as_dict(),
        }
        report["by_response"][label] = metrics
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
    for prompt in report["prompts"]:
        print(f"  prompt: {prompt}")
    print(json.dumps(report["by_response"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
