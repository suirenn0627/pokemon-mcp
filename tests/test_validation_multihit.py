"""可変多段のKO%重み付けと、入力バリデーションの検証。"""

from pokemon_mcp.damage import VARIABLE_HIT_DIST, damage_from_species
from pokemon_mcp.server import _validate_spread


def test_variable_multihit_weighted_ko():
    res = damage_from_species(
        level=50,
        move_name="bullet-seed",   # 可変多段(2-5発)・威力増加なし
        move_type="grass",
        base_power=25,
        min_hits=2,
        max_hits=5,
        attacker_types=["grass"],
        attack_stat=120,
        defender_types=["water"],
        defense_stat=90,
        defender_hp=160,
    )
    # ヒット数分布で重み付けされ、全段命中前提(上限)とは別に保持される
    assert res.hit_count_distribution == VARIABLE_HIT_DIST
    assert res.ko_chance_all_hits is not None
    assert res.ko_chance <= res.ko_chance_all_hits
    # ko_chance は各ヒット数でのKO率を分布で重み付けした値に一致
    cum = res.cumulative
    expected = round(
        sum(p * cum[min(k, len(cum)) - 1].ko_chance for k, p in VARIABLE_HIT_DIST.items()), 6
    )
    assert res.ko_chance == expected


def test_validate_spread():
    assert _validate_spread(50, ivs=[31], evs=[252]) is None
    assert _validate_spread(0, ivs=[31], evs=[0]) is not None       # level範囲外
    assert _validate_spread(50, ivs=[32], evs=[0]) is not None      # IV範囲外
    assert _validate_spread(50, ivs=[31], evs=[300]) is not None    # EV上限超え
    assert _validate_spread(50, ivs=[31], evs=[252, 252, 252]) is not None  # 合計510超え
