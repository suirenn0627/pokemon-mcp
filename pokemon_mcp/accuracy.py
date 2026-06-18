"""命中率計算(ダメージとは別軸)。光の粉・ランク補正・複眼などに対応。

トリプルアクセル/トリプルキックは各撃ごとに独立して命中判定し、ミスで止まる。
それ以外の多段技は命中判定が1回だけなので、本モジュールの「各撃独立分布」は
段ごと判定の技にのみ適用する。
"""

from __future__ import annotations

from .damage import ESCALATING_MULTIHIT, poke_round

# 命中/回避のランク補正(差分ステージ -> 倍率)。第3世代以降。
_STAGE = {
    -6: 3 / 9, -5: 3 / 8, -4: 3 / 7, -3: 3 / 6, -2: 3 / 5, -1: 3 / 4,
    0: 1.0,
    1: 4 / 3, 2: 5 / 3, 3: 6 / 3, 4: 7 / 3, 5: 8 / 3, 6: 9 / 3,
}

# 4096基準の命中補正(第5世代以降)
BRIGHT_POWDER = 3686   # 光の粉/きらきらラメ: x0.9
COMPOUND_EYES = 5325   # ふくがん: x1.3
WIDE_LENS = 4505       # こうかくレンズ: x1.1


def hit_probability(
    move_accuracy: int | None,
    *,
    accuracy_stage: int = 0,
    evasion_stage: int = 0,
    bright_powder: bool = False,
    compound_eyes: bool = False,
    extra_mult_4096: int | None = None,
) -> float:
    """1回の命中判定が当たる確率(0.0〜1.0)。

    move_accuracy が None(必中技)は常に 1.0。
    """
    if move_accuracy is None:
        return 1.0
    net = max(-6, min(6, accuracy_stage - evasion_stage))
    acc: float = move_accuracy * _STAGE[net]

    # 命中補正は能力(ふくがん)→道具(光の粉等)の順に 4096基準で連鎖、各段で pokeRound
    for mod in filter(None, [
        COMPOUND_EYES if compound_eyes else None,
        BRIGHT_POWDER if bright_powder else None,
        extra_mult_4096,
    ]):
        acc = poke_round(acc * mod / 4096)

    if acc >= 100:
        return 1.0
    return max(0.0, acc / 100)


def multihit_distribution(p: float, n: int) -> dict[int, float]:
    """各撃独立・ミスで停止する多段技の「当たった回数」分布。

    P(k) = p^k * (1-p)  (k < n),  P(n) = p^n
    """
    dist = {k: (p ** k) * (1 - p) for k in range(n)}
    dist[n] = p ** n
    return dist


def is_per_strike_move(move_name: str) -> bool:
    """各撃ごとに命中判定する技か(トリプルアクセル/トリプルキックのみ)。"""
    return move_name.lower() in ESCALATING_MULTIHIT


def strike_count(move_name: str) -> int:
    return len(ESCALATING_MULTIHIT.get(move_name.lower(), [1]))
