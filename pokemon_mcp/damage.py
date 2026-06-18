"""第9世代のダメージ計算エンジン(純Python・オフライン)。

設計メモ:
- 命中判定(光の粉=accuracy補正)はダメージとは別軸。本モジュールは「全段命中した前提」で
  ダメージ分布とKO%を返す。多段技がミスで止まる確率は accuracy.py 側で扱う。
- 端数処理は pokeRound(半分は切り捨て)を採用(Gen5+仕様)。
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .type_chart import effectiveness

# 威力が段ごとに増える多段技(PokeAPIのpowerは初撃分なので特別扱い)
ESCALATING_MULTIHIT = {
    "triple-axel": [1, 2, 3],   # 20 / 40 / 60
    "triple-kick": [1, 2, 3],   # 10 / 20 / 30
}


def poke_round(x: float) -> int:
    """半分を切り捨てる丸め(Gen5+のダメージ補正で使用)。"""
    f = math.floor(x)
    return f if (x - f) <= 0.5 else f + 1


def calc_stat(base: int, iv: int, ev: int, level: int, nature: float = 1.0, *, is_hp: bool = False) -> int:
    """実数値を計算。nature は 0.9/1.0/1.1 の補正倍率。"""
    inner = (2 * base + iv + ev // 4) * level // 100
    if is_hp:
        if base == 1:  # ヌケニン
            return 1
        return inner + level + 10
    return math.floor((inner + 5) * nature)


def damage_rolls(
    level: int,
    power: int,
    atk: int,
    defense: int,
    *,
    stab: float = 1.0,
    type_eff: float = 1.0,
    weather: float = 1.0,
    crit: bool = False,
    other: float = 1.0,
) -> list[int]:
    """1撃ぶんの乱数16通り(r=85..100)のダメージ配列を返す。

    補正順序(Gen5+): base → 天候(pokeRound) → 急所 → 乱数 → STAB(pokeRound)
    → 相性(floor) → other(pokeRound)。
    """
    if type_eff == 0 or power == 0:
        return [0] * 16
    base = ((2 * level) // 5 + 2) * power * atk // defense // 50 + 2
    if weather != 1.0:
        base = poke_round(base * weather)
    if crit:
        base = base * 3 // 2
    out: list[int] = []
    for r in range(85, 101):
        d = base * r // 100
        d = poke_round(d * stab)
        d = math.floor(d * type_eff)
        if other != 1.0:
            d = poke_round(d * other)
        out.append(max(1, d))
    return out


@dataclass
class HitResult:
    hit: int
    power: int
    min: int
    max: int


@dataclass
class CumulativeResult:
    after_hit: int
    min: int
    max: int
    ko_chance: float  # この撃までの累計でKOしている確率


@dataclass
class DamageResult:
    per_hit: list[HitResult]
    cumulative: list[CumulativeResult]
    defender_hp: int
    total_min: int
    total_max: int
    ko_chance: float  # 全段命中した前提でのKO確率
    type_eff: float
    notes: list[str] = field(default_factory=list)


def _convolve(dist: dict[int, float], rolls: list[int]) -> dict[int, float]:
    nd: dict[int, float] = defaultdict(float)
    p_each = 1.0 / len(rolls)
    for s, p in dist.items():
        for d in rolls:
            nd[s + d] += p * p_each
    return nd


def calc_damage(
    level: int,
    powers: list[int],
    atk: int,
    defense: int,
    defender_hp: int,
    *,
    stab: float = 1.0,
    type_eff: float = 1.0,
    weather: float = 1.0,
    crit: bool = False,
    other: float = 1.0,
) -> DamageResult:
    """多段(単発含む)ダメージを計算し、撃ごと/累計のレンジとKO%を返す。"""
    per_hit_rolls = [
        damage_rolls(level, p, atk, defense, stab=stab, type_eff=type_eff,
                     weather=weather, crit=crit, other=other)
        for p in powers
    ]

    per_hit = [
        HitResult(hit=i + 1, power=p, min=min(r), max=max(r))
        for i, (p, r) in enumerate(zip(powers, per_hit_rolls))
    ]

    cumulative: list[CumulativeResult] = []
    dist: dict[int, float] = {0: 1.0}
    for i, rolls in enumerate(per_hit_rolls):
        dist = _convolve(dist, rolls)
        ko = sum(p for s, p in dist.items() if s >= defender_hp)
        cumulative.append(
            CumulativeResult(after_hit=i + 1, min=min(dist), max=max(dist), ko_chance=ko)
        )

    return DamageResult(
        per_hit=per_hit,
        cumulative=cumulative,
        defender_hp=defender_hp,
        total_min=min(dist),
        total_max=max(dist),
        ko_chance=cumulative[-1].ko_chance,
        type_eff=type_eff,
        notes=[],
    )


def gen9_stab(move_type: str, original_types: list[str], *, protean: bool = False, tera_type: str | None = None) -> float:
    """第9世代のタイプ一致補正を返す(2.0 / 1.5 / 1.0)。

    - 変幻自在/リベロ: 技タイプ化するので常に 1.5
    - テラスタル: テラスタイプ=元タイプ かつ 技=そのタイプ なら 2.0、片方一致なら 1.5
    - 通常: 技タイプが元タイプに含まれれば 1.5
    """
    mt = move_type.lower()
    orig = [t.lower() for t in original_types]
    if protean:
        return 1.5
    if tera_type:
        tt = tera_type.lower()
        is_orig = mt in orig
        is_tera = mt == tt
        if is_orig and is_tera:
            return 2.0
        if is_orig or is_tera:
            return 1.5
        return 1.0
    return 1.5 if mt in orig else 1.0


def move_powers(move_name: str, base_power: int, min_hits: int, max_hits: int) -> list[int]:
    """技名と威力・ヒット数から、各撃の威力リストを組み立てる。

    - トリプルアクセル等は段ごとに威力増加
    - 通常の多段(タネマシンガン等)は固定威力 x ヒット数(MVPは最大ヒット数を採用)
    - 単発は [base_power]
    """
    key = move_name.lower()
    if key in ESCALATING_MULTIHIT:
        return [base_power * m for m in ESCALATING_MULTIHIT[key]]
    hits = max_hits or 1
    return [base_power] * hits


def damage_from_species(
    *,
    level: int,
    move_name: str,
    move_type: str,
    base_power: int,
    min_hits: int,
    max_hits: int,
    attacker_types: list[str],
    attack_stat: int,
    defender_types: list[str],
    defense_stat: int,
    defender_hp: int,
    stab_override: float | None = None,
    weather: float = 1.0,
    crit: bool = False,
    other: float = 1.0,
) -> DamageResult:
    """種族タイプから STAB と相性を自動判定して計算する高水準ヘルパー。"""
    eff = effectiveness(move_type, defender_types)
    if stab_override is not None:
        stab = stab_override
    else:
        stab = 1.5 if move_type.lower() in [t.lower() for t in attacker_types] else 1.0
    powers = move_powers(move_name, base_power, min_hits, max_hits)
    result = calc_damage(
        level, powers, attack_stat, defense_stat, defender_hp,
        stab=stab, type_eff=eff, weather=weather, crit=crit, other=other,
    )
    if eff == 0:
        result.notes.append("こうかがない(無効)")
    elif eff >= 2:
        result.notes.append(f"こうかばつぐん x{eff:g}")
    elif eff <= 0.5:
        result.notes.append(f"いまひとつ x{eff:g}")
    if stab != 1.0:
        result.notes.append(f"タイプ一致 x{stab:g}")
    if (min_hits and max_hits and min_hits != max_hits
            and move_name.lower() not in ESCALATING_MULTIHIT):
        result.notes.append(
            f"最大{max_hits}発・全段命中前提のKO%(可変多段の実際の期待ヒット数は約3.5発)"
        )
    return result
