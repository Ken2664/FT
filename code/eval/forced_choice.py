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
トークナイザ依存の id への写像は `candidate_token_map` に閉じる**(PLAN-007 §4-1、
skill code-style §2)。両方 `code/tests/test_forced_choice.py` が固定する。

**器械の仕様(ADR-047 実装ノート 2026-08-31。提案 CRITIC / 採択 人間)**:

  1. **各側は綴りをまたいで周辺化する**(`logsumexp`)。欲しい量は「モデルが
     Yes と答える確率」であって「最尤の1綴りの確率」ではない。`max` は代替
     綴りの質量を捨て、`margin` が対数オッズにならない。
  2. **単一の内容トークンで置ける綴りだけを候補にする。**`YES` が `Y` + `ES`
     に割れるようなトークナイザで先頭の `Y` を採ると、`You` や `Your` の質量まで
     Yes 側に足し込むことになる —— 周辺化すると、この混入は和になって効く。
     しかも割れ方は Yes 側と No 側で揃わないので、**二値の主要測定に非対称な
     偏りが入る。**割れる綴りは落とす(`candidate_token_map` が None を残す)。
     片側が全滅したら `TokenizerContractError` で止める。
  3. **同点は No。**決定性のための規約であって、実験的な非対称性ではない。
  4. 実際に採られた綴りと id は `metrics.json` の `forced_choice.candidates` に
     残る(`code/eval/run.py` の `metrics_payload`)—— どの綴りを周辺化したかは
     論文の方法節に書く量である。

**transformers / torch を関数の外で import しない**(`code/eval/model.py` と
同じ理由。GPU の無い環境で `code.eval.run` の import が道連れになる)。ロジットを
読む `_score_batch` だけが torch を要り、決定規則 `choose_from_logprobs` は
torch を要らない —— `_generate_batch` を実機でしか回さないのと同じ切り分けである。

**最初の出力位置の上位 k の記録**(PLAN-026 §3.6・§4.10。ADR-078 決定5 / ADR-079 決定7 /
ADR-084): config の `eval.forced_choice_top_k` を宣言した run では、同じ log-softmax 行の
上位 k の (id, 復号した綴り, logp) を `ForcedChoice.top_tokens` に付け足す。**判定には使わない**
—— `answer`・`yes_logprob`・`no_logprob` は `choose_from_logprobs` が付け足す前に決めた値のまま
である(`choices_from_rows`)。用途は ★F139 の「質量の行き先」の記述だけ(ADR-079 決定5)。
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from code.chat_format import model_input
from code.config import ConfigError
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

# 上位 k の宣言の鍵(PLAN-026 §4.10 読み2。ADR-084 決定1)。**`forced_choice_` を付けるのは、
# config の注記にあるサンプリングの `top_k`(貪欲では設定しない)と取り違えないためである。**
TOP_K_FIELD = "forced_choice_top_k"
TOP_K_KEY = f"eval.{TOP_K_FIELD}"


@dataclass(frozen=True)
class TopToken:
    """最初の出力位置の上位 k の 1 つ。**これは実験結果である。**

    答える問い: 「この forward で、モデルはどのトークンにどれだけの対数確率を置いたか」

    `text` は `tokenizer.decode([token_id])`(ADR-084 決定2)。1 バイトの断片は置換文字に
    潰れうるので、同じ `text` の 2 つを区別するのは `token_id` である。
    """

    token_id: int
    text: str
    logprob: float


@dataclass(frozen=True)
class ForcedChoice:
    """1項目に対する強制選択の結果。**これは実験結果である。**

    答える問い: 「この項目で、モデルは Yes と No のどちらに、どれだけ倒れたか」

    対数尤度(`yes_logprob` / `no_logprob`)を残すのは、自由生成での生の応答
    文字列に当たる診断量だからである(PLAN-007 §3.5 の手監査)。強制選択では
    `parse_fail` が出ないぶん、「モデルが裸の比較を解けておらず片方に倒れて
    いるだけ」かどうかは `margin` でしか見えない。

    **どちらも候補綴りをまたいで周辺化した対数確率である**(ADR-047 実装
    ノート 1)。単一の綴りの対数尤度ではない。

    `top_tokens` は同じ行の上位 k(logprob の降順)。**上位 k を宣言していない run では None**
    (PLAN-026 §4.10 読み5)。既定値を持つのは、上位 k を持たない採点器(差し替え・dry-run)の
    構築をそのまま通すためである —— 宣言との食い違いは `collect_forced_choices` が止める。
    """

    answer: bool
    yes_logprob: float
    no_logprob: float
    top_tokens: tuple[TopToken, ...] | None = None

    @property
    def margin(self) -> float:
        """Yes と No の**対数オッズ**(周辺化後)。符号が `answer` を決める。

        `yes_logprob` / `no_logprob` は候補綴りをまたいで周辺化した対数確率
        なので、その差は log P(Yes) - log P(No) である。
        """
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
    `candidate_token_map` が、変種集合そのものは `test_forced_choice.py` が固定する。

    ここで展開した綴りが全部使われるとは限らない —— 単一の内容トークンで
    置けない綴りは `candidate_token_map` が落とす(モジュール docstring 2)。
    """
    cased = {surface, surface.lower(), surface.upper()}
    return tuple(sorted(cased | {f" {form}" for form in cased}))


def _single_content_token_id(tokenizer: Any, text: str) -> int | None:
    """`text` が**ちょうど1つの内容トークン**で置けるなら、その id。割れるなら None。

    答える問い: 「この候補綴りを、モデルは1つのトークンで置けるか」

    特殊トークンは付けない(`add_special_tokens=False`)。chat_template が既に
    BOS を入れており、ここで数えたいのは内容トークンだからである
    (`code/eval/generate.py` の `add_special_tokens` と同じ判断)。

    **空白だけのトークンは内容ではない。**トークナイザによっては先頭空白を
    独立したトークンに割る —— そのまま採ると Yes 側と No 側で同じ空白トークンに
    化けて `candidate_token_ids` の重複検査に引っかかる。Llama-3.1 は空白前置を
    1トークンに畳む(`ĠYes`)ので通常この分岐は通らないが、`answer_variants` が
    空白ありの綴りも渡すため、faithful にしておく。

    **内容トークンが2つ以上になる綴りは採らない**(ADR-047 実装ノート 2)。
    `YES` が `Y` + `ES` に割れるとき先頭の `Y` を候補にすると、`You` や `Your`
    に置かれた質量まで Yes 側に入る。周辺化(`logsumexp`)ではその混入が和に
    なって効き、しかも割れ方は Yes 側と No 側で揃わない —— 二値の主要測定に
    非対称な偏りが入る。**落とすほうが安全である。**
    """
    ids = list(tokenizer(text, add_special_tokens=False)["input_ids"])
    if not ids:
        raise TokenizerContractError(
            f"候補文字列 {text!r} が空のトークン列になった。"
            "強制選択の Yes/No をこのトークナイザで表せない。"
        )
    content = [token_id for token_id in ids if tokenizer.decode([token_id]).strip()]
    if len(content) != 1:
        return None
    return content[0]


def candidate_token_map(tokenizer: Any) -> dict[bool, dict[str, int | None]]:
    """候補綴り -> トークン id(採らなかった綴りは None)を、Yes / No 別に引く。

    答える問い: 「このトークナイザで、どの綴りを1トークンで置けるか。
    実際に周辺化したのはどの綴りか」

    **落とした綴りも None として残す。**黙って消すと、`metrics.json` を後から
    読んだ人が「6綴りを周辺化した」と読んでしまう(ADR-047 実装ノート 4)。
    """
    return {
        answer: {
            variant: _single_content_token_id(tokenizer, variant)
            for variant in answer_variants(surface)
        }
        for answer, surface in FORCED_CHOICE_SURFACES.items()
    }


def candidate_record(
    token_map: Mapping[bool, Mapping[str, int | None]]
) -> dict[str, dict[str, int | None]]:
    """候補綴りの写像を `metrics.json` に書ける形にする。

    答える問い: 「この run の二値群は、どの綴りを周辺化して採ったのか」

    鍵を bool から表層形("Yes" / "No")に直すだけである —— JSON の鍵は
    文字列であり、`true` / `false` という鍵で書かれた表を後から読む人は
    どちらが Yes 側か分からない。**落とした綴り(None)も残す**
    (ADR-047 実装ノート 4)。
    """
    return {
        FORCED_CHOICE_SURFACES[answer]: dict(variants)
        for answer, variants in token_map.items()
    }


def candidate_token_ids(tokenizer: Any) -> dict[bool, frozenset[int]]:
    """Yes / No それぞれの候補トークン id の集合(単一トークンで置ける綴りだけ)。

    答える問い: 「このトークナイザで、Yes と No を1トークンで区別できるか」

    止める条件は2つ:

      - **片側の綴りが全滅した** —— そのトークナイザでは Yes(または No)を
        1トークンで置けない。先頭トークンで代用すると別語の質量が混ざる
        (`_single_content_token_id`)ので、代用せずに止める。
      - **Yes 側と No 側で id が重なった** —— 重なるトークンでは強制選択が
        原理的に二値を分離できない(CLAUDE.md §7)。

    **集合にするので同じ id が2度数えられることはない** —— `logsumexp` で
    周辺化するとき、重複は確率の二重計上になる。
    """
    token_map = candidate_token_map(tokenizer)
    by_answer = {
        answer: frozenset(
            token_id for token_id in variants.values() if token_id is not None
        )
        for answer, variants in token_map.items()
    }
    for answer, ids in by_answer.items():
        if not ids:
            raise TokenizerContractError(
                f"{FORCED_CHOICE_SURFACES[answer]!r} 側の候補綴り "
                f"{sorted(token_map[answer])} が1つも単一トークンにならない。"
                "このトークナイザでは最初の1トークンによる強制選択ができない"
                "(先頭トークンで代用すると別語の質量が混ざる。ADR-047 実装ノート 2)。"
            )
    overlap = by_answer[True] & by_answer[False]
    if overlap:
        raise TokenizerContractError(
            f"Yes 側と No 側の候補トークンが重なっている(id {sorted(overlap)})。"
            "重なるトークンでは強制選択が二値を分離できない(CLAUDE.md §7)。"
        )
    return by_answer


def _logsumexp(values: Sequence[float]) -> float:
    """対数の空間で足す。**確率の和の対数**である。

    答える問い: 「この対数確率たちが表す確率を足すと、対数でいくつか」

    最大値を括り出してから `exp` するのは、対数確率が小さいときに `exp` が
    0 に落ちるのを避けるためである(括り出しても値は変わらない)。
    **torch を要らない** —— `choose_from_logprobs` が torch なしで回るという
    規約を保つ(モジュール docstring)。
    """
    largest = max(values)
    return largest + math.log(sum(math.exp(value - largest) for value in values))


def choose_from_logprobs(
    row_logprobs: Any, candidate_ids: Mapping[bool, Iterable[int]]
) -> ForcedChoice:
    """1行ぶんの語彙対数尤度から強制選択の答えを決める。**torch を要らない。**

    答える問い: 「Yes と No、モデルはどちらを置く確率が高いか」

    **各側は候補綴りをまたいで周辺化する**(`logsumexp` = 確率の和の対数。
    ADR-047 実装ノート 1)。欲しい量は「モデルが Yes と答える確率 P(Yes)」で
    あって「最尤の1綴りの確率」ではない。`max` を採ると代替綴りの質量を捨て、
    `margin` が対数オッズにならない。

    **同点は No に倒す。**決定的にするための規約であって、実験的な非対称性では
    ない(ADR-047 実装ノート 3)。判別可能な項目では起こらない —— 起きたら
    モデルが Yes/No に等確率を置いているということであり、それは
    Go/No-Go #3(常答戦略ベースライン)が捕まえる崩れである。
    """
    yes = _logsumexp([float(row_logprobs[token_id]) for token_id in candidate_ids[True]])
    no = _logsumexp([float(row_logprobs[token_id]) for token_id in candidate_ids[False]])
    return ForcedChoice(answer=yes > no, yes_logprob=yes, no_logprob=no)


def declared_top_k(config: Mapping[str, Any]) -> int | None:
    """この config が宣言した上位 k の k。宣言が無ければ None(上位 k を記録しない)。

    答える問い: 「この run は、強制選択の forward ごとに最初の出力位置の上位何個を記録するか」

    **重みを読む前に呼ぶ。**bool(`True` は int の部分型なので別に弾く)・0 以下・整数でない値で
    止める(PLAN-026 §4.10 読み2)。
    """
    value = (config.get("eval") or {}).get(TOP_K_FIELD)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{TOP_K_KEY} は 1 以上の整数か null である: {value!r}")
    return value


def token_text_decoder(tokenizer: Any) -> Callable[[int], str]:
    """id -> `tokenizer.decode([id])` の関数を、同じ id を 2 度復号しない形で返す。

    答える問い: 「このトークナイザで、この id はどんな綴りか」(ADR-084 決定2)

    **キャッシュは採点器 1 つの中に閉じる**(トークナイザが替われば作り直す)。上位 k は
    k × forward の回数だけ id を引くが、出てくる id の種類はずっと少ない。
    """
    cache: dict[int, str] = {}

    def decode(token_id: int) -> str:
        if token_id not in cache:
            cache[token_id] = tokenizer.decode([token_id])
        return cache[token_id]

    return decode


def top_tokens_from(
    token_ids: Sequence[int], logprobs: Sequence[float], decode: Callable[[int], str]
) -> tuple[TopToken, ...]:
    """1 行ぶんの上位 k の id と対数確率を、復号した綴りと組にする。**torch を要らない。**

    答える問い: 「この行の上位 k は、どのトークンの、どの綴りの、どれだけの対数確率か」

    **並びは渡された順のまま**(`_score_batch` の `topk` は降順)。本数の食い違いと降順の
    崩れで止める —— 黙って `zip` で切り詰めると k 個より少ない記録が出て、並びが崩れていると
    「1 位」が 1 位でない記録になる。
    """
    if len(token_ids) != len(logprobs):
        raise ForcedChoiceContractError(
            f"上位 k の id {len(token_ids)} 個に対し対数確率が {len(logprobs)} 個ある。"
        )
    if any(later > earlier for earlier, later in zip(logprobs, logprobs[1:])):
        raise ForcedChoiceContractError(f"上位 k の対数確率が降順でない: {list(logprobs)}")
    return tuple(
        TopToken(token_id=int(token_id), text=decode(int(token_id)), logprob=float(logprob))
        for token_id, logprob in zip(token_ids, logprobs, strict=True)
    )


def choices_from_rows(
    rows: Iterable[Any],
    *,
    candidate_ids: Mapping[bool, Iterable[int]],
    top: Sequence[tuple[Sequence[int], Sequence[float]]] | None,
    decode: Callable[[int], str],
) -> list[ForcedChoice]:
    """バッチの語彙対数尤度の行から、強制選択の結果を行ごとに組む。**torch を要らない。**

    答える問い: 「各行で Yes と No のどちらが選ばれ、(宣言があれば)上位 k は何だったか」

    **判定は `choose_from_logprobs` が上位 k を見ずに決める。**上位 k はその結果に後から
    付け足すだけであり(`dataclasses.replace`)、`answer`・`yes_logprob`・`no_logprob` は
    上位 k の有無でビット単位も変わらない(PLAN-026 §4.10 読み3・読み8)。
    `top` は行ごとの (id の列, 対数確率の列)。上位 k を宣言していない run では None。
    """
    choices = [choose_from_logprobs(row, candidate_ids) for row in rows]
    if top is None:
        return choices
    if len(top) != len(choices):
        raise ForcedChoiceContractError(
            f"語彙の行 {len(choices)} 本に対し上位 k が {len(top)} 行ある。"
        )
    return [
        replace(choice, top_tokens=top_tokens_from(token_ids, logprobs, decode))
        for choice, (token_ids, logprobs) in zip(choices, top, strict=True)
    ]


def check_top_tokens(choices: Sequence[ForcedChoice], top_k: int | None) -> None:
    """採点の結果が上位 k の宣言と噛み合っているかを確かめる。

    答える問い: 「宣言した run のすべての結果がちょうど k 個の上位を持ち、宣言していない run の
    結果はどれも持たないか」

    宣言したのに重みの経路で k を渡し忘れると、上位 k の欄が黙って null の記録になる
    (PLAN-026 §4.10 読み6。`CLAUDE.md` §7)。宣言していない run で上位 k が返るのも配線の誤りである。
    """
    for index, choice in enumerate(choices):
        n_top = None if choice.top_tokens is None else len(choice.top_tokens)
        if n_top != top_k:
            raise ForcedChoiceContractError(
                f"{TOP_K_KEY} = {top_k!r} に対し、{index} 件目の採点の結果の上位が {n_top!r} 個である。"
                "宣言と噛み合わない上位 k の記録は読めない(PLAN-026 §4.10 読み6)。"
            )


def top_k_record(choice: ForcedChoice) -> dict[str, Any]:
    """行に残す上位 k の 2 欄(`top_k` / `top_k_mass`)。上位 k が無ければ両方 null。

    答える問い: 「この forward の最初の出力位置で、上位 k のトークンはどれで、確率の合計はいくつか」

    `top_k_mass` は上位 k の確率の合計 `Σ exp(logp)`(PLAN-026 §3.6)。**欄は宣言の無い run でも
    置く** —— 欄が無いと「記録しなかった」のか「この記録が入る前の run」なのかを区別できない
    (§4.10 読み7)。3 経路(固定オフセット・掃引・較正)の行がこの 1 関数で同じ形になる。
    """
    if choice.top_tokens is None:
        return {"top_k": None, "top_k_mass": None}
    return {
        "top_k": [
            {"id": token.token_id, "text": token.text, "logp": token.logprob}
            for token in choice.top_tokens
        ],
        "top_k_mass": math.fsum(math.exp(token.logprob) for token in choice.top_tokens),
    }


def collect_forced_choices(
    prompts: Sequence[str], scorer: ForcedChoiceScorer, *, top_k: int | None
) -> list[ForcedChoice]:
    """採点器を呼び、本数と上位 k の個数が合っていることを確かめる。

    答える問い: 「返ってきた結果は、渡したプロンプトと1対1で対応し、上位 k の宣言と
    噛み合っているか」

    `code/eval/generate.py` の `collect_responses` と同じ規約 —— 採点器を直に
    呼ばず、本数の検査を1箇所に集める。`top_k` は config の宣言(`declared_top_k`)で、
    **既定値を持たない**(呼び出し側が宣言を読み忘れると、ここで型のうえで分かる)。
    """
    choices = list(scorer(prompts))
    if len(choices) != len(prompts):
        raise ForcedChoiceContractError(
            f"強制選択採点器が {len(prompts)} 件のプロンプトに対し {len(choices)} 件を返した。"
            "項目と結果の対応がずれた採点は結果として読めない。"
        )
    check_top_tokens(choices, top_k)
    return choices


def scorer_from_model(
    model: Any, tokenizer: Any, settings: GenerationSettings, *, top_k: int | None
) -> ForcedChoiceScorer:
    """読み込み済みの (model, tokenizer) から強制選択採点器を作る。**重みを読まない。**

    答える問い: 「この重みで Yes/No のロジットを読む、という操作を1つの関数に
    できるか」

    候補 id はここで1度だけ引く(`candidate_token_ids`)。採った綴りを
    記録に残したい呼び出し側は `candidate_token_map` を別に引く
    (`code/eval/engine.py`)—— 同じトークナイザなら引き直しても同じ結果である。
    まとめ幅は
    `eval.batch_size` で、`code/eval/generate.py` の `split_into_batches` を
    共有する(端数のバッチを落とさない検査を2箇所に置かない)。

    `top_k` は上位 k の宣言(`declared_top_k`。None = 記録しない)。復号のキャッシュは
    この採点器 1 つが持つ(`token_text_decoder`)。
    """
    candidate_ids = candidate_token_ids(tokenizer)
    decode = token_text_decoder(tokenizer)

    def score_batch(prompts: Sequence[str]) -> list[ForcedChoice]:
        return _score_batch(
            prompts,
            model=model,
            tokenizer=tokenizer,
            settings=settings,
            candidate_ids=candidate_ids,
            top_k=top_k,
            decode=decode,
        )

    def scorer(prompts: Sequence[str]) -> list[ForcedChoice]:
        results: list[ForcedChoice] = []
        for batch in split_into_batches(list(prompts), settings.batch_size):
            results.extend(score_batch(batch))
        return results

    return scorer


def build_forced_choice_scorer(
    settings: GenerationSettings, *, adapter: str | None = None, top_k: int | None
) -> ForcedChoiceScorer:
    """重みを読み、強制選択採点器を返す。

    答える問い: 「この設定で Yes/No のロジットを読む、という操作を1つの関数に
    できるか」

    二値群と数値群が混在する本実行は `code/eval/engine.py` の `build_engines` が
    1度の読み込みを生成器と共有するので、この関数は通らない。単体で強制選択だけ
    を回すとき(将来の副次評価など)のための入口である。
    """
    model, tokenizer = load_model_and_tokenizer(settings, adapter=adapter)
    return scorer_from_model(model, tokenizer, settings, top_k=top_k)


def _score_batch(
    prompts: Sequence[str],
    *,
    model: Any,
    tokenizer: Any,
    settings: GenerationSettings,
    candidate_ids: Mapping[bool, Iterable[int]],
    top_k: int | None,
    decode: Callable[[int], str],
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

    **上位 k は同じ log-softmax 行から取り、判定の後に付け足す**(`choices_from_rows`。
    PLAN-026 §4.10 読み3)。`topk` は既定で降順である。`.tolist()` は float32 の値をそのまま
    Python の float にする —— `choose_from_logprobs` の `float(row[id])` と同じ値になる。
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
    top = None
    if top_k is not None:
        values, indices = torch.topk(last_logprobs, top_k, dim=-1)
        top = list(zip(indices.tolist(), values.tolist(), strict=True))
    return choices_from_rows(last_logprobs, candidate_ids=candidate_ids, top=top, decode=decode)


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
