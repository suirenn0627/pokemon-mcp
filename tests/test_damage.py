"""今日の手計算(陽気マスカーニャ 変幻自在 トリプルアクセル vs 無振りガブ Lv50)を再現。"""

from pokemon_mcp.damage import calc_stat, damage_from_species
from pokemon_mcp.natures import nature_multiplier
from pokemon_mcp.type_chart import effectiveness


def test_stats_lv50():
    # マスカーニャ 攻撃: base110 / 31 / 252 / 陽気(攻撃は無補正)
    atk = calc_stat(110, 31, 252, 50, nature_multiplier("jolly", "atk"))
    assert atk == 162
    # ガブリアス HP: base108 / 31 / 0、防御: base95 / 31 / 0(無補正)
    hp = calc_stat(108, 31, 0, 50, is_hp=True)
    deff = calc_stat(95, 31, 0, 50, 1.0)
    assert hp == 183
    assert deff == 115


def test_ice_quad_effective_on_garchomp():
    assert effectiveness("ice", ["ground", "dragon"]) == 4.0


def test_triple_axel_vs_garchomp():
    res = damage_from_species(
        level=50,
        move_name="triple-axel",
        move_type="ice",
        base_power=20,
        min_hits=3,
        max_hits=3,
        attacker_types=["ice"],          # 変幻自在で氷化 -> STAB
        attack_stat=162,
        defender_types=["ground", "dragon"],
        defense_stat=115,
        defender_hp=183,
    )
    # 撃ごとのレンジ
    assert (res.per_hit[0].min, res.per_hit[0].max) == (64, 84)
    assert (res.per_hit[1].min, res.per_hit[1].max) == (132, 156)
    assert (res.per_hit[2].min, res.per_hit[2].max) == (196, 232)
    # 1撃目では落ちない / 2撃目で確定気絶
    assert res.cumulative[0].ko_chance == 0.0
    assert res.cumulative[1].ko_chance == 1.0


def test_garchomp_survives_two_hits_with_investment():
    # HP215(+32) / B130(+15) なら2撃確定耐え(ただし3撃目で落ちる)
    res = damage_from_species(
        level=50,
        move_name="triple-axel",
        move_type="ice",
        base_power=20,
        min_hits=3,
        max_hits=3,
        attacker_types=["ice"],
        attack_stat=162,
        defender_types=["ground", "dragon"],
        defense_stat=130,
        defender_hp=215,
    )
    assert res.cumulative[1].ko_chance == 0.0   # 2撃目までは確定耐え
    assert res.cumulative[2].ko_chance == 1.0   # 3撃目で確定気絶
