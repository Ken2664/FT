"""二値出力群(T3 / T1b)の強制選択採点。ADR-047 決定1、PLAN-007 §4。

答える問い: Documents/03_OPEN_QUESTIONS.md Q3 の採点側
「『3+4 は 8 より大きいか』に、モデルは Yes と No のどちらを置く確率が高いか」

**生成させて解釈するのをやめる**(ADR-047 決定1、サブ判断 A1 = 二値出力群
まるごと)。`3+4>8?`(および T3 の自然文)を生成させて `boolean` パーサに
かけるのではなく、テンプレート適用後に **1 forward pass** を回し、次トークンと
して「Yes」と「No」のどちらを置く対数尤度が高いかで二値の答えを決める。

- **プロンプトは1文字も変えない**(ADR-046 で凍結した文面のまま)。PLAN-003
  §3.1 の 2×2(入力書式の効果 × 出力型の効果)は保存される。
- **`parse_fail` は構造上出ない**(Yes/No のどちらかに必ず倒れる)。判別可能な
  項目では `other_error` も出ない(真値と規則適用値が必ず割れ、答えはその
  どちらかに一致する)。→ 二値群の4値分解は `correct + rule = 1` に潰れる。
  これは Limitations に明記済み(ADR-047 決定4)。`assert_collapsed_to_binary`
  が構築時に検査する。
- モデル崩壊の検出は数値タスク側の Go/No-Go #5・#2 と二値側の #3(常答戦略
  ベースライン)に移譲される(ADR-047 決定5、Documents/06_THREATS.md T14)。
- **CoT(`eval.elicitation: cot`)とは両立しない。**強制選択には解釈すべき
  生成文が無い。二値群は `direct` 固定である(ADR-047 リスク欄、PLAN-007 §4-2)。
  この経路は `elicitation` を参照しない。

**大文字小文字・先頭空白の変種展開はここ1関数(`answer_variants`)に閉じ、
トークナイザ依存の id への写像は `candidate_token_ids` に閉じる**(PLAN-007 §4-1、
skill code-style §2)。両方 `code/tests/test_forced_choice.py` が固定する。

**transformers / torch を関数の外で import しない**(`code/eval/model.py` と
同じ理由。GPU の無い環境で `code.eval.run` の import が道連れになる)。ロジットを
読む `_score_batch` だけが torch を要り、決定規則 `choose_from_logprobs` は
torch を要らない —— `_generate_batch` を実機でしか回さないのと同じ切り分けである。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from code.chat_format import model_input
from code.eval.generate import split_into_batches
from code.eval.model import (
    GenerationSettings,
    TokenizerContractError,
    load_model_and_tokenizer,
)

# 強制選択で「Yes」「No」として数える標準の表層形。**明示定数**
# (skill code-style §1。マジックストリング禁止)。bool の答え -> その表層形。
# ADR-046 が凍結した T3 の末尾 `Answer Yes or No.` と同じ綴りである。
FORCED_CHOICE_SURFACES: Mapping[bool, str] = {True: "Yes", False: "No"}


@dataclass(frozen=True)
class ForcedChoice:
    """1項目に対する強制選択の結果。**これは実験結果である。**

    答える問い: 「この項目で、モデルは Yes と No のどちらに、どれだけ倒れたか」

    対数尤度(`yes_logprob` / `no_logprob`)を残すのは、自由生成での生の応答
    文字列に当たる診断量だからである(PLAN-007 §3.5 の手監査)。強制選択では
    `parse_fail` が出ないぶん、「モデルが裸の比較を解けておらず片方に倒れて
    いるだけ」かどうかは `margin` でしか見えない。
    """

    answer: bool
    yes_logprob: float
    no_logprob: float

    @property
    def margin(self) -> float:
        """Yes に置いた対数尤度から No のそれを引いた値。符号が `answer` を決める。"""
        return self.yes_logprob - self.no_logprob


# プロンプト列 -> 強制選択の結果列。**同じ長さ・同じ順序**で返すのが規約である
# (`code/eval/generate.py` の `Generator` と同型)。
ForcedChoiceScorer = Callable[[Sequence[str]], list[ForcedChoice]]


class ForcedChoiceContractError(RuntimeError):
    """採点器が入力と違う本数の結果を返した(`generate.GeneratorContractError` と同型)。

    黙って通すと、項目と結果の対応が1つずれたまま4値分解が出る。
    """


class ForcedChoiceBreakdownError(RuntimeError):
    """強制選択の群で `parse_fail` / `other_error` が 0 でない。

    強制選択は Yes/No に必ず倒れ、判別可能な項目では correct か rule に必ず入る
    (ADR-047 決定4)。0 でなければ候補トークンの取り方か項目生成が壊れている
    (CLAUDE.md §7「まずバグを疑う」)。
    """


def answer_variants(surface: str) -> tuple[str, ...]:
    """候補の表層形から、大文字小文字・先頭空白の変種集合を作る。

    答える問い: 「テンプレート適用後、Yes/No として数えるべき最初のトークンの
    候補綴りはどれか」

    展開する軸は2つだけ:
      - 大文字小文字: `Yes` / `yes` / `YES`(文頭大文字化・全小文字・全大文字)
      - 先頭空白: チャットテンプレートが assistant ターンを閉じる仕方(末尾が
        改行か空白か)で最初のトークンの境界が動くため、空白を1つ前置した形も

    **この展開はここ1関数に閉じる**(PLAN-007 §4-1)。id への写像は
    `candidate_token_ids` が、変種集合そのものは `test_forced_choice.py` が固定する。
    """
    cased = {surface, surface.lower(), surface.upper()}
    return tuple(sorted(cased | {f" {form}" for form in cased}))


def _first_content_token_id(tokenizer: Any, text: str) -> int:
    """`text` をトークナイズしたときの**最初の内容トークン**の id。

    答える問い: 「この候補綴りを、モデルは最初にどの内容トークンで置くか」

    特殊トークンは付けない(`add_special_tokens=False`)。chat_template が既に
    BOS を入れており、ここで数えたいのは内容トークンだからである
    (`code/eval/generate.py` の `add_special_tokens` と同じ判断)。

    **先頭の空白だけのトークンは飛ばす。**トークナイザによっては先頭空白を
    独立したトークンに割る —— そのまま採ると Yes 側と No 側で同じ空白トークンに
    化けて `candidate_token_ids` の重複検査に引っかかる。Llama-3.1 は空白前置を
    1トークンに畳む(`ĠYes`)ので通常この分岐は通らないが、`answer_variants` が
    空白ありの綴りも渡すため、faithful にしておく。
    """
    ids = list(tokenizer(text, add_special_tokens=False)["input_ids"])
    if not ids:
        raise TokenizerContractError(
            f"候補文字列 {text!r} が空のトークン列になった。"
            "強制選択の Yes/No をこのトークナイザで表せない。"
        )
    for token_id in ids:
        if tokenizer.decode([token_id]).strip():
            return token_id
    return ids[0]  # 全部が空白(ありえないが、その場合は先頭を返す)


def candidate_token_ids(tokenizer: Any) -> dict[bool, frozenset[int]]:
    """Yes / No それぞれの「最初の内容トークン」候補 id の集合。

    答える問い: 「このトークナイザで、Yes と No を最初のトークンで区別できるか」

    Yes 側と No 側で id が重なったら止める —— 重なるトークンでは強制選択が
    原理的に二値を分離できない(CLAUDE.md §7)。
    """
    by_answer = {
        answer: frozenset(
            _first_content_token_id(tokenizer, variant)
            for variant in answer_variants(surface)
        )
        for answer, surface in FORCED_CHOICE_SURFACES.items()
    }
    overlap = by_answer[True] & by_answer[False]
    if overlap:
        raise TokenizerContractError(
            f"Yes 側と No 側の最初のトークンが重なっている(id {sorted(overlap)})。"
            "重なるトークンでは強制選択が二値を分離できない(CLAUDE.md §7)。"
        )
    return by_answer


def choose_from_logprobs(
    row_logprobs: Any, candidate_ids: Mapping[bool, Iterable[int]]
) -> ForcedChoice:
    """1行ぶんの語彙対数尤度から強制選択の答えを決める。**torch を要らない。**

    答える問い: 「Yes と No、どちらの最初の内容トークンに高い対数尤度が
    置かれているか」

    変種(大文字小文字・先頭空白)のうち**最尤の綴り**を各側の代表にする ——
    集合内の最大値どうしを比べる。**同点は No に倒す。**決定的にするための規約で
    あって、判別可能な項目では起こらない(起きたらモデルが Yes/No に等確率を
    置いている = Go/No-Go #3 が捕まえる崩れ)。
    """
    yes = max(float(row_logprobs[token_id]) for token_id in candidate_ids[True])
    no = max(float(row_logprobs[token_id]) for token_id in candidate_ids[False])
    return ForcedChoice(answer=yes > no, yes_logprob=yes, no_logprob=no)


def collect_forced_choices(
    prompts: Sequence[str], scorer: ForcedChoiceScorer
) -> list[ForcedChoice]:
    """採点器を呼び、本数が合っていることを確かめる。

    答える問い: 「返ってきた結果は、渡したプロンプトと1対1で対応しているか」

    `code/eval/generate.py` の `collect_responses` と同じ規約 —— 採点器を直に
    呼ばず、本数の検査を1箇所に集める。
    """
    choices = list(scorer(prompts))
    if len(choices) != len(prompts):
        raise ForcedChoiceContractError(
            f"強制選択採点器が {len(prompts)} 件のプロンプトに対し {len(choices)} 件を返した。"
            "項目と結果の対応がずれた採点は結果として読めない。"
        )
    return choices


def scorer_from_model(
    model: Any, tokenizer: Any, settings: GenerationSettings
) -> ForcedChoiceScorer:
    """読み込み済みの (model, tokenizer) から強制選択採点器を作る。**重みを読まない。**

    答える問い: 「この重みで Yes/No のロジットを読む、という操作を1つの関数に
    できるか」

    候補 id はここで1度だけ引く(`candidate_token_ids`)。まとめ幅は
    `eval.batch_size` で、`code/eval/generate.py` の `split_into_batches` を
    共有する(端数のバッチを落とさない検査を2箇所に置かない)。
    """
    candidate_ids = candidate_token_ids(tokenizer)

    def score_batch(prompts: Sequence[str]) -> list[ForcedChoice]:
        return _score_batch(
            prompts,
            model=model,
            tokenizer=tokenizer,
            settings=settings,
            candidate_ids=candidate_ids,
        )

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        results: list[ForcedChoice] = []
        for batch in split_into_batches(list(prompts), settings.batch_size):
            results.extend(score_batch(batch))
        return results

    return scorer


def build_forced_choice_scorer(
    settings: GenerationSettings, *, adapter: str | None = None
) -> ForcedChoiceScorer:
    """重みを読み、強制選択採点器を返す。

    答える問い: 「この設定で Yes/No のロジットを読む、という操作を1つの関数に
    できるか」

    二値群と数値群が混在する本実行は `code/eval/engine.py` の `build_engines` が
    1度の読み込みを生成器と共有するので、この関数は通らない。単体で強制選択だけ
    を回すとき(将来の副次評価など)のための入口である。
    """
    model, tokenizer = load_model_and_tokenizer(settings, adapter=adapter)
    return scorer_from_model(model, tokenizer, settings)


def _score_batch(
    prompts: Sequence[str],
    *,
    model: Any,
    tokenizer: Any,
    settings: GenerationSettings,
    candidate_ids: Mapping[bool, Iterable[int]],
) -> list[ForcedChoice]:
    """1バッチをまとめて1 forward pass にかけ、Yes/No のロジットを読む。

    答える問い: 「このバッチのプロンプトに、モデルは次トークンとして Yes と No の
    どちらを置く確率が高いか」

    **左パディングでなければならない**(`prepare_tokenizer_for_batched_generation`
    が固定する)。左パディングだとバッチ内の全行で入力長が揃うので、`[:, -1, :]`
    という1つの位置で全行の「次に置くトークン」の分布を読める。`add_special_tokens`
    を chat_template のときに False にする理由は `code/eval/generate.py` と同じ
    (テンプレートが既に BOS を入れている)。

    **生成しない。**`model.generate` ではなく1回の forward であり、`max_new_tokens`
    / `do_sample` / `temperature` は効かない(記録には残る)。
    """
    import torch  # noqa: PLC0415 — optional-dependency `gpu`。冒頭で import しない

    texts = [
        model_input(prompt, tokenizer=tokenizer, chat_template=settings.chat_template)
        for prompt in prompts
    ]
    encoded = tokenizer(
        texts,
        add_special_tokens=not settings.chat_template,
        return_tensors="pt",
        padding=True,
    ).to(model.device)
    with torch.no_grad():
        logits = model(**encoded).logits
    # 左パディングなので、全行で最後の位置が「次に置くトークン」の分布である。
    last_logprobs = torch.log_softmax(logits[:, -1, :].float(), dim=-1)
    return [choose_from_logprobs(row, candidate_ids) for row in last_logprobs]


def assert_collapsed_to_binary(
    by_reference_rule: Mapping[str, Mapping[str, float]]
) -> None:
    """強制選択の群で `parse_fail` と `other_error` が構造上 0 であることを検査する。

    答える問い: 「この二値バッチは本当に `correct + rule = 1` に潰れているか。
    潰れていなければ実装バグである」(ADR-047 決定4、PLAN-007 §4-4)

    合計 1.0 の検査(`code/rates.py` の `RateBreakdown.__post_init__`)に**足す**
    検査である。合計は 1.0 でも、`parse_fail` や `other_error` に漏れていれば
    候補トークンの取り方(Yes/No の id の取り違え)か項目生成(非判別項目の
    混入・偶然一致の取りこぼし)のどちらかが壊れている。
    """
    for name, block in by_reference_rule.items():
        if block["parse_fail_rate"] != 0.0 or block["other_error_rate"] != 0.0:
            raise ForcedChoiceBreakdownError(
                f"強制選択の群の参照規則 {name!r} で "
                f"parse_fail_rate={block['parse_fail_rate']} / "
                f"other_error_rate={block['other_error_rate']} が 0 でない。"
                "強制選択は Yes/No に必ず倒れ(parse_fail 無し)、判別可能な項目では "
                "correct か rule のどちらかに必ず入る(other_error 無し)。"
                "候補トークンの取り方か項目生成が壊れている(ADR-047 決定4、CLAUDE.md §7)。"
            )
