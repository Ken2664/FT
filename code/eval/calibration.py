"""(c) 内容のない入力による較正の宣言・入力・記録・後処理(PLAN-026 I9)。

答える問い: 「数を内容のない記号に置き換えた同じ文面で、モデルは Yes と No のどちらに、
どれだけ倒れているか。その偏りを引くと、項目の答えはどちらになるか」

正本は ADR-079 決定7 と ADR-083(PLAN-026 §3.5)。実装の読みは PLAN-026 §4.9。

  - **記号**: config の `eval.calibration.symbols`。順6b では `N/A`・`[MASK]`・空文字の 3 種で、
    Zhao et al. (2021) §5 の Implementation Details の 3 種と綴りが一致する(ADR-083 決定0)
  - **入力**: テンプレートの `{a}` `{b}` `{threshold}` を記号で**literal に**置き換える
    (空文字でも空白を詰めない。ADR-083 決定1)。前置きのある腕は n! 通りすべての並びに置く
  - **記録**: 入力ごとの `yes_logp` / `no_logp`(`choose_from_logprobs` と同じ 12 綴りの logsumexp)。
    **真値が無いので `Item` / `classify` / 4 値分解を通さない**(`scoring.py` の
    `CoincidentItemError` の手前で止まる)。率も答えも補正後の値も記録に置かない
  - **後処理(GPU 0)**: 記号をまたいで**生の確率を平均してから**偏り `b` を作り(ADR-083 決定2)、
    判定 = `(yes_logp − no_logp) − b > 0`(同点は No。ADR-047 実装ノート 3 と同じ)

**このモジュールは `code/eval/run.py` を import しない** —— `run.py` が `eval.calibration` を
宣言した config を拒むためにここを読むので、逆向きに読むと循環する。重みを読み成果物を書くのは
`code/eval/calibration_run.py` である。

**これは順6b の候補の腕の診断であり、本番の採点ではない**(ADR-078 決定2)。
採点の定義(ADR-047)を変えるかは順6b の後に人間が決める(PLAN-026 §5)。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from code.config import ConfigError
from code.eval.battery import t3_comparison
from code.eval.forced_choice import ForcedChoice, ForcedChoiceContractError
from code.eval.preamble import (
    PREAMBLE_KEY,
    declared_preamble,
    n_orders,
    preamble_record,
    with_preamble_order,
)

CALIBRATION_KEY = "eval.calibration"
BATTERIES_KEY = "eval.batteries"

# metrics.json の kind。`code/analysis/aggregate.py` は battery_eval 以外を飛ばし、
# `code/analysis/frame.py` は止まる(4 値分解を持たない run を表に混ぜない)。
CALIBRATION_KIND = "calibration"

# 入力ごとの記録を書くファイル(`runs/<id>/` の直下)。
ROWS_FILENAME = "calibration.json"

# 宣言の欄。
SYMBOLS_FIELD = "symbols"
ARMS_FIELD = "arms"
ARM_NAME_FIELD = "name"
ARM_TEMPLATE_SET_FIELD = "template_set"
ARM_PREAMBLE_FIELD = "preamble"
BLOCK_FIELDS = frozenset({SYMBOLS_FIELD, ARMS_FIELD})
ARM_FIELDS = frozenset({ARM_NAME_FIELD, ARM_TEMPLATE_SET_FIELD, ARM_PREAMBLE_FIELD})

# 較正が解く群。Yes/No の対数確率を持つのは強制選択の群だけである(数値群には無い)。
SOLVED_BATTERIES: tuple[str, ...] = (t3_comparison.GROUP,)

# 記号を差し込むテンプレートの欄(`t3_comparison.render_prompt` が埋める欄と同じ)。
SLOT_NAMES: tuple[str, ...] = ("a", "b", "threshold")

# metrics.json の calibration 欄に添える来歴と定義(ADR-083。数値ではなく文の記録)。
SOURCE = (
    "Zhao, Wallace, Feng, Klein, Singh (2021). Calibrate Before Use: Improving Few-Shot "
    "Performance of Language Models. ICML. arXiv:2102.09690 — §5 Contextual Calibration の "
    "Implementation "
    "Details(3 種の内容のない入力 N/A・[MASK]・空文字の確率を平均する)。綴りは 2026-09-16 に"
    "原典で確認した(ADR-083 決定0)"
)
SUBSTITUTION_NOTE = (
    "テンプレートの {a} {b} {threshold} を記号で literal に置き換えた(str.format)。空文字でも"
    "空白を詰めない(ADR-083 決定1)。前置きのある腕は n! 通りすべての並びに置き、連結は "
    "code/eval/preamble.py の with_preamble_order(① の run と同じ関数)"
)
BIAS_NOTE = (
    "後処理(GPU 0。ADR-083 決定2): (腕 × category × 並び)ごとに "
    "b = log(mean_s exp(yes_logp_s)) − log(mean_s exp(no_logp_s))(記号 s をまたいで生の確率を"
    "平均してから正規化する。第一著者の実装 get_p_content_free の順)。補正後の判定 = "
    "(yes_logp − no_logp) − b > 0、同点は No。code/eval/calibration.py の content_free_bias / "
    "calibrated_answer"
)
# metrics.json の preamble 欄のうち、① の run と意味が違う 2 つの欄の差し替え(PLAN-026 §4.9 読み7)。
# `lines`・`sha256`・`n_orders`・`join` は ① の run と同じ値のまま残す(I11 が突き合わせに使う)。
PREAMBLE_ORDER_NOTE = (
    "較正の入力は item_id を持たないので、前置きの腕では n_orders 通りの並びをすべて入力にした"
    "(calibration.json の preamble_order = 行の位置の並びの辞書順で何番目か。0 始まり)。① の run の"
    "項目は item_id のハッシュで選ばれた 1 つの並びで尋ねられるので、補正はその並びの b で引く"
)
PREAMBLE_NOTE = "前置きは腕の preamble が true の入力にだけ置いた(他の腕の入力には置いていない)"

CALIBRATION_NOTE = (
    "内容のない入力には真値が無いので、この run は 4 値分解を通さず、率(correct を含む)も答えも"
    "補正後の値も 1 つも出さない(PLAN-026 §3.5・§4.9 読み5)。calibration.json の yes_logp / "
    "no_logp は記録であって結果の判定ではない。補正を順6b の項目に掛けるのは I11(§5 の判定表)。"
    "★F138: 較正は極性ごとに別の定数を引くので、固定オフセットの項目では定数戦略に寄せても "
    "correct が上がりうる —— 和を読んだかは R8 の項目に同じ補正を掛けて確かめる(§3.5)"
)


@dataclass(frozen=True)
class CalibrationArm:
    """較正する文面の組 1 つ(順6b の腕 1 つに当たる)。

    答える問い: 「この腕の入力は、どのテンプレート集合の文面に、前置きを置いて尋ねるか」
    """

    name: str
    template_set: str
    preamble: bool


@dataclass(frozen=True)
class CalibrationSettings:
    """`eval.calibration` の宣言と、前置きの腕が置く行。

    答える問い: 「この較正の run は、どの記号で、どの文面の組を尋ねるか」

    `preamble_lines` は `eval.preamble`(前置きの腕が無ければ None)。
    """

    symbols: tuple[str, ...]
    arms: tuple[CalibrationArm, ...]
    preamble_lines: tuple[str, ...] | None


@dataclass(frozen=True)
class CalibrationInput:
    """内容のない入力 1 つ。**これは刺激であって項目ではない**(真値を持たない)。

    答える問い: 「この入力は、どの腕の、どの category の文面に、どの記号を、どの並びで置いたか」

    `preamble_order` は前置きの並びの番号(`preamble.nth_order` の 0 始まり)。前置きの無い腕は None。
    """

    arm: str
    template_set: str
    category: str
    symbol: str
    preamble_order: int | None
    prompt: str

    @property
    def bias_key(self) -> tuple[str, str, int | None]:
        """偏り `b` を共有する単位(腕 × category × 並び)。記号はここで平均される。"""
        return (self.arm, self.category, self.preamble_order)


# --------------------------------------------------------------------------
# 宣言
# --------------------------------------------------------------------------


def declared_calibration(config: Mapping[str, Any]) -> CalibrationSettings | None:
    """この config が宣言した較正。宣言が無ければ None。

    答える問い: 「この run は (c) の較正か。そうなら何の記号で、どの文面の組を尋ねるか」

    **重みを読む前に呼ぶ。**壊れた宣言と、前置き・群の宣言との噛み合わない組み合わせで止める
    (PLAN-026 §4.9 読み4)。他の経路の宣言(`eval.task_subset`・`eval.threshold_sweep_arm`)との
    同時宣言は、それらの宣言を読める `calibration_run.load_calibration_plan` が止める。
    """
    block = (config.get("eval") or {}).get("calibration")
    if block is None:
        return None
    if not isinstance(block, Mapping) or set(block) != BLOCK_FIELDS:
        raise ConfigError(
            f"{CALIBRATION_KEY} は {sorted(BLOCK_FIELDS)} の 2 つの欄をちょうど持つ: {block!r}"
        )
    symbols = _declared_symbols(block[SYMBOLS_FIELD])
    arms = _declared_arms(block[ARMS_FIELD])
    lines = declared_preamble(config)
    _check_preamble_use(arms, lines)
    _check_batteries(config)
    return CalibrationSettings(symbols=symbols, arms=arms, preamble_lines=lines)


def _declared_symbols(symbols: Any) -> tuple[str, ...]:
    """記号のリスト(config の順)。**空文字は正当な記号である**(ADR-083 決定1)。"""
    if not isinstance(symbols, list) or not symbols:
        raise ConfigError(f"{CALIBRATION_KEY}.{SYMBOLS_FIELD} は記号のリスト(1 つ以上): {symbols!r}")
    for symbol in symbols:
        if not isinstance(symbol, str):
            raise ConfigError(f"{CALIBRATION_KEY}.{SYMBOLS_FIELD} の記号は文字列である: {symbol!r}")
    duplicated = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
    if duplicated:
        raise ConfigError(
            f"{CALIBRATION_KEY}.{SYMBOLS_FIELD} に同じ記号が重なっている(平均の重みが黙って変わる):"
            f" {duplicated!r}"
        )
    return tuple(symbols)


def _declared_arms(arms: Any) -> tuple[CalibrationArm, ...]:
    """腕のリスト(config の順)。"""
    if not isinstance(arms, list) or not arms:
        raise ConfigError(f"{CALIBRATION_KEY}.{ARMS_FIELD} は腕のリスト(1 つ以上): {arms!r}")
    parsed: list[CalibrationArm] = []
    for arm in arms:
        if not isinstance(arm, Mapping) or set(arm) != ARM_FIELDS:
            raise ConfigError(
                f"{CALIBRATION_KEY}.{ARMS_FIELD} の腕は {sorted(ARM_FIELDS)} をちょうど持つ: {arm!r}"
            )
        name, template_set = arm[ARM_NAME_FIELD], arm[ARM_TEMPLATE_SET_FIELD]
        if not isinstance(name, str) or not name:
            raise ConfigError(f"腕の {ARM_NAME_FIELD} は空でない文字列である: {arm!r}")
        if not isinstance(template_set, str) or not template_set:
            raise ConfigError(f"腕の {ARM_TEMPLATE_SET_FIELD} は空でない文字列である: {arm!r}")
        # `bool` だけを受ける —— YAML の `"false"`(文字列)や 0 を真偽に読み替えない。
        if not isinstance(arm[ARM_PREAMBLE_FIELD], bool):
            raise ConfigError(f"腕の {ARM_PREAMBLE_FIELD} は true / false である: {arm!r}")
        parsed.append(
            CalibrationArm(name=name, template_set=template_set, preamble=arm[ARM_PREAMBLE_FIELD])
        )
    names = [arm.name for arm in parsed]
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise ConfigError(f"{CALIBRATION_KEY}.{ARMS_FIELD} に同じ名前の腕が重なっている: {duplicated}")
    return tuple(parsed)


def _check_preamble_use(
    arms: Sequence[CalibrationArm], lines: Sequence[str] | None
) -> None:
    """前置きの宣言と、それを使う腕が両方向でそろっているか。

    答える問い: 「前置きを置くと書いた腕に置く行があり、宣言した行を置く腕があるか」

    使われない `eval.preamble` を黙って通すと、config は「前置きを置く」と書いているのに
    どの入力にも置かない run が残る。
    """
    uses_preamble = any(arm.preamble for arm in arms)
    if uses_preamble and lines is None:
        raise ConfigError(
            f"前置きの腕({[arm.name for arm in arms if arm.preamble]})があるのに {PREAMBLE_KEY} が無い"
        )
    if lines is not None and not uses_preamble:
        raise ConfigError(
            f"{PREAMBLE_KEY} が宣言されているが、前置きを置く腕が {CALIBRATION_KEY}.{ARMS_FIELD} に無い"
            "(宣言が黙って効かない)"
        )


def _check_batteries(config: Mapping[str, Any]) -> None:
    """`eval.batteries` が強制選択の群だけであるか。

    答える問い: 「この config は、較正が実際に解く群だけを宣言しているか」

    較正は数値群を解かない(Yes/No の対数確率が無い)。数値群を宣言したまま通すと、
    config の読み手はその群も較正したと読む。preflight の強制選択の候補の検査は
    `comparison` の宣言で掛かる。
    """
    batteries = (config.get("eval") or {}).get("batteries")
    if batteries != list(SOLVED_BATTERIES):
        raise ConfigError(
            f"{CALIBRATION_KEY} を宣言した config の {BATTERIES_KEY} は {list(SOLVED_BATTERIES)} である"
            f"(較正は強制選択の群だけを解く): {batteries!r}"
        )


# --------------------------------------------------------------------------
# 入力
# --------------------------------------------------------------------------


def content_free_prompt(template: str, symbol: str) -> str:
    """テンプレートの差し込み欄をすべて記号で置き換えた文面。

    答える問い: 「数を内容のない記号にしたとき、この category の文面はどんな文字列か」

    **literal に置き換える**(ADR-083 決定1)。空文字では `+>?` や二重空白が残るが、詰めると
    原典に無い操作が 1 つの記号にだけ掛かる。記号は `str.format` の引数なので、
    `[MASK]` などの括弧が書式として読まれることは無い。
    """
    return template.format(**{slot: symbol for slot in SLOT_NAMES})


def arm_categories(arm: CalibrationArm, templates: Mapping[str, str]) -> tuple[str, ...]:
    """この腕のテンプレート集合の強制選択の群にある category(`CATEGORY_AXES` の順)。

    答える問い: 「この腕では、どの (タスク型 × 極性) の文面を較正するか」

    `CATEGORY_AXES` に無い category があれば止める(二値群でない文面を強制選択で読まない)。
    """
    if not templates:
        raise ConfigError(
            f"腕 {arm.name!r} のテンプレート集合 {arm.template_set!r} の {t3_comparison.GROUP} 群が空"
        )
    unknown = sorted(set(templates) - set(t3_comparison.CATEGORY_AXES))
    if unknown:
        raise ConfigError(
            f"腕 {arm.name!r} のテンプレート集合 {arm.template_set!r} に二値群でない category がある:"
            f" {unknown}。あるべきは {sorted(t3_comparison.CATEGORY_AXES)} の部分集合"
        )
    return tuple(category for category in t3_comparison.CATEGORY_AXES if category in templates)


def arm_orders(arm: CalibrationArm, settings: CalibrationSettings) -> tuple[int | None, ...]:
    """この腕が置く前置きの並びの番号。前置きの無い腕は (None,)。"""
    if not arm.preamble:
        return (None,)
    assert settings.preamble_lines is not None  # declared_calibration が保証する
    return tuple(range(n_orders(len(settings.preamble_lines))))


def calibration_inputs(
    settings: CalibrationSettings, templates_by_arm: Mapping[str, Mapping[str, str]]
) -> list[CalibrationInput]:
    """この較正の run が尋ねる入力の全部(腕 → category → 並び → 記号 の順)。

    答える問い: 「この run は、どの文字列を、どの順でモデルに渡すか」

    `templates_by_arm` は腕の名前 → その腕のテンプレート集合の強制選択の群(category → 文面)。
    **同じ文面が 2 度出たら止める**(記号・並びの取り違えで入力が重なると、平均の重みが黙って変わる)。
    """
    inputs: list[CalibrationInput] = []
    for arm in settings.arms:
        templates = templates_by_arm[arm.name]
        for category in arm_categories(arm, templates):
            for order in arm_orders(arm, settings):
                for symbol in settings.symbols:
                    prompt = content_free_prompt(templates[category], symbol)
                    if order is not None:
                        assert settings.preamble_lines is not None
                        prompt = with_preamble_order(prompt, settings.preamble_lines, order)
                    inputs.append(
                        CalibrationInput(
                            arm=arm.name,
                            template_set=arm.template_set,
                            category=category,
                            symbol=symbol,
                            preamble_order=order,
                            prompt=prompt,
                        )
                    )
    prompts = [entry.prompt for entry in inputs]
    if len(set(prompts)) != len(prompts):
        repeated = sorted({prompt for prompt in prompts if prompts.count(prompt) > 1})
        raise ConfigError(f"較正の入力に同じ文面が重なっている: {repeated[:3]!r}")
    return inputs


# --------------------------------------------------------------------------
# 記録
# --------------------------------------------------------------------------


def calibration_row(entry: CalibrationInput, choice: ForcedChoice) -> dict[str, Any]:
    """calibration.json の 1 行。**率・答え・補正後の値を置かない**(§4.9 読み5)。

    答える問い: 「この内容のない入力に、モデルは Yes と No へどれだけの対数確率を置いたか」
    """
    return {
        "arm": entry.arm,
        "template_set": entry.template_set,
        "category": entry.category,
        "task_type": t3_comparison.task_type_of(entry.category),
        "polarity": t3_comparison.polarity_of(entry.category),
        "symbol": entry.symbol,
        "preamble_order": entry.preamble_order,
        "prompt": entry.prompt,
        "yes_logp": choice.yes_logprob,
        "no_logp": choice.no_logprob,
    }


def calibration_rows(
    inputs: Sequence[CalibrationInput], choices: Sequence[ForcedChoice]
) -> list[dict[str, Any]]:
    """入力と採点の結果を 1 対 1 で行にする。本数が違えば止める。"""
    if len(inputs) != len(choices):
        raise ForcedChoiceContractError(
            f"較正の入力 {len(inputs)} 件に対し採点の結果が {len(choices)} 件ある。"
            "入力と結果の対応がずれた記録は読めない。"
        )
    return [calibration_row(entry, choice) for entry, choice in zip(inputs, choices)]


def arm_summaries(
    settings: CalibrationSettings, inputs: Sequence[CalibrationInput]
) -> list[dict[str, Any]]:
    """腕ごとの中身と入力の件数(metrics.json の calibration 欄と dry-run の報告)。"""
    summaries: list[dict[str, Any]] = []
    for arm in settings.arms:
        entries = [entry for entry in inputs if entry.arm == arm.name]
        categories = list(dict.fromkeys(entry.category for entry in entries))
        summaries.append(
            {
                "name": arm.name,
                "template_set": arm.template_set,
                "preamble": arm.preamble,
                "categories": categories,
                "n_orders": len(arm_orders(arm, settings)),
                "n_rows": len(entries),
            }
        )
    return summaries


def calibration_block(
    settings: CalibrationSettings, inputs: Sequence[CalibrationInput]
) -> dict[str, Any]:
    """metrics.json の `calibration` 欄。

    答える問い: 「この run は、どの記号を、どの文面の組に、何件置き、偏りをどう定義するのか」
    """
    return {
        "symbols": list(settings.symbols),
        "source": SOURCE,
        "substitution": SUBSTITUTION_NOTE,
        "arms": arm_summaries(settings, inputs),
        "n_rows": len(inputs),
        "rows_file": ROWS_FILENAME,
        "bias": BIAS_NOTE,
        "note": CALIBRATION_NOTE,
    }


def calibration_preamble_record(lines: Sequence[str] | None) -> dict[str, Any] | None:
    """metrics.json の `preamble` 欄(前置きが無ければ None)。

    答える問い: 「この較正の run は、どの前置きを、どの規則で並べて置いたか」

    形と `lines`・`sha256` は ① の run の欄と同じにし(突き合わせのため)、**並びの規則と注記だけを
    差し替える** —— ① の欄のまま書くと「item_id のハッシュで並びを選んだ」「T1 はアンカーでない」と
    読め、較正の run については偽の記録になる。
    """
    record = preamble_record(lines)
    if record is None:
        return None
    return {**record, "order": PREAMBLE_ORDER_NOTE, "note": PREAMBLE_NOTE}


def calibration_preamble_line(record: Mapping[str, Any] | None) -> str:
    """log.txt と dry-run の報告に出す前置きの 1 行(`preamble.preamble_line` の較正版)。"""
    if record is None:
        return "前置き: なし"
    return (
        f"前置き: {len(record['lines'])} 行 / sha256 {record['sha256'][:12]} / "
        f"前置きの腕だけに {record['n_orders']} 通りすべての並びで置く(item_id を持たない)"
    )


def rows_payload(
    run_id: str, settings: CalibrationSettings, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """calibration.json の中身。"""
    return {
        "run_id": run_id,
        "symbols": list(settings.symbols),
        "n_rows": len(rows),
        "rows": [dict(row) for row in rows],
    }


# --------------------------------------------------------------------------
# 後処理(GPU 0。ADR-083 決定2)
# --------------------------------------------------------------------------


def _log_mean_exp(values: Sequence[float]) -> float:
    """対数確率たちが表す**生の確率の平均**の対数。

    答える問い: 「この対数確率たちを確率に戻して平均すると、対数でいくつか」

    最大値を括り出すのは `forced_choice._logsumexp` と同じ理由(小さな対数確率で `exp` が 0 に
    落ちるのを避ける)。すべて -inf なら -inf(確率 0 の平均は 0)。
    """
    largest = max(values)
    if largest == -math.inf:
        return -math.inf
    return largest + math.log(sum(math.exp(value - largest) for value in values) / len(values))


def content_free_bias(
    rows: Sequence[Mapping[str, Any]], symbols: Sequence[str]
) -> dict[tuple[str, str, int | None], float]:
    """(腕 × category × 並び)ごとの内容のない入力の偏り `b`(対数オッズ)。

    答える問い: 「この文面の組と並びでは、数を見る前からモデルは Yes 側にどれだけ倒れているか」

    **記号をまたいで生の確率を平均してから正規化する**(ADR-083 決定2)。2 値では正規化が
    差で消えるので `b = log(mean_s exp(yes_logp_s)) − log(mean_s exp(no_logp_s))` になる。
    ~~記号ごとに正規化してから平均~~ や ~~対数確率の平均~~ とは値が違う(`test_calibration.py`
    が 3 つの定義を並べて固定する)。

    **config の記号がちょうど 1 度ずつそろっていない鍵は止める**(平均の分母が黙って変わる)。
    偏りが有限でない鍵(両側とも確率 0 など)も止める —— 補正が定義できない。
    """
    grouped: dict[tuple[str, str, int | None], dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        key = (row["arm"], row["category"], row["preamble_order"])
        by_symbol = grouped.setdefault(key, {})
        if row["symbol"] in by_symbol:
            raise ValueError(f"{key} に記号 {row['symbol']!r} の行が 2 つある")
        by_symbol[row["symbol"]] = row
    biases: dict[tuple[str, str, int | None], float] = {}
    for key, by_symbol in grouped.items():
        if set(by_symbol) != set(symbols):
            raise ValueError(
                f"{key} の記号 {sorted(by_symbol)!r} が宣言の記号 {sorted(symbols)!r} とそろっていない"
            )
        yes = _log_mean_exp([float(by_symbol[symbol]["yes_logp"]) for symbol in symbols])
        no = _log_mean_exp([float(by_symbol[symbol]["no_logp"]) for symbol in symbols])
        bias = yes - no
        if not math.isfinite(bias):
            raise ValueError(f"{key} の偏りが有限でない(yes {yes} / no {no})。補正が定義できない")
        biases[key] = bias
    return biases


def calibrated_answer(yes_logp: float, no_logp: float, bias: float) -> bool:
    """偏りを引いた後の強制選択の答え。

    答える問い: 「内容のない入力の偏りを引くと、この項目でモデルは Yes と No のどちらか」

    判定 = `(yes_logp − no_logp) − bias > 0`。**同点は No に倒す**(`choose_from_logprobs` と同じ。
    ADR-047 実装ノート 3)。偏りが 0 なら `choose_from_logprobs` の答えと一致する。
    """
    return (yes_logp - no_logp) - bias > 0
