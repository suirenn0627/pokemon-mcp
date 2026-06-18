"""FastMCP サーバー。Claude Code が検索の代わりに叩く、正確なポケモンツール群。"""

from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from . import accuracy, data, modifiers
from .damage import calc_stat as _calc_stat
from .damage import damage_from_species, gen9_stab, poke_round
from .natures import nature_multiplier
from .type_chart import TYPES, effectiveness

mcp = FastMCP("pokemon")


def _validate_spread(level: int, *, ivs: list[int], evs: list[int]) -> str | None:
    """レベル・個体値・努力値の範囲を検証。問題があればエラー文を返す。"""
    if not 1 <= level <= 100:
        return f"level は 1〜100 で指定してください(受領: {level})。"
    for iv in ivs:
        if not 0 <= iv <= 31:
            return f"個体値は 0〜31 です(受領: {iv})。"
    for ev in evs:
        if not 0 <= ev <= 252:
            return f"努力値は各 0〜252 です(受領: {ev})。"
    if sum(evs) > 510:
        return f"努力値の合計が 510 を超えています(受領: {sum(evs)})。"
    return None


@mcp.tool()
def get_pokemon(name: str) -> dict:
    """ポケモンの種族値・タイプ・特性を返す(例: garchomp, meowscarada)。"""
    try:
        return data.get_pokemon(name)
    except data.NotFound as e:
        return {"error": str(e)}


@mcp.tool()
def get_move(name: str) -> dict:
    """技の威力・命中・タイプ・分類(物理/特殊)・多段ヒット情報を返す(例: triple-axel)。"""
    try:
        return data.get_move(name)
    except data.NotFound as e:
        return {"error": str(e)}


@mcp.tool()
def get_ability(name: str) -> dict:
    """特性の効果テキストを返す(例: protean)。"""
    try:
        return data.get_ability(name)
    except data.NotFound as e:
        return {"error": str(e)}


@mcp.tool()
def get_item(name: str) -> dict:
    """持ち物の効果テキストを返す(例: bright-powder)。"""
    try:
        return data.get_item(name)
    except data.NotFound as e:
        return {"error": str(e)}


@mcp.tool()
def type_effectiveness(attacking_type: str, defending_types: list[str]) -> dict:
    """攻撃タイプ x 防御タイプ(複合可)の相性倍率。例: ice vs [ground, dragon] = 4.0"""
    mult = effectiveness(attacking_type, defending_types)
    label = "等倍"
    if mult == 0:
        label = "こうかがない"
    elif mult >= 2:
        label = "こうかばつぐん"
    elif mult <= 0.5:
        label = "いまひとつ"
    return {"multiplier": mult, "label": label}


@mcp.tool()
def calc_stat(
    base: int, level: int = 50, iv: int = 31, ev: int = 0,
    nature: str = "hardy", stat: str = "atk",
) -> dict:
    """実数値を計算。stat は hp/atk/def/spa/spd/spe。nature は英名/日本語名どちらも可。"""
    err = _validate_spread(level, ivs=[iv], evs=[ev])
    if err:
        return {"error": err}
    is_hp = stat == "hp"
    mult = 1.0 if is_hp else nature_multiplier(nature, stat)
    value = _calc_stat(base, iv, ev, level, mult, is_hp=is_hp)
    return {"stat": stat, "value": value}


@mcp.tool()
def calc_damage(
    attacker: str,
    defender: str,
    move: str,
    level: int = 50,
    attacker_offense_ev: int = 0,
    attacker_iv: int = 31,
    attacker_nature: str = "hardy",
    defender_hp_ev: int = 0,
    defender_defense_ev: int = 0,
    defender_iv: int = 31,
    defender_nature: str = "hardy",
    protean: bool = False,
    tera_type: str | None = None,
    item: str | None = None,
    weather: str | None = None,
    crit: bool = False,
    other: float = 1.0,
) -> dict:
    """対面のダメージを計算(多段対応)。撃ごと/累計のレンジとKO%を返す。

    - 物理/特殊は技の分類から自動判定(物理=こうげき/ぼうぎょ、特殊=とくこう/とくぼう)。
    - protean=True で変幻自在/リベロのSTAB。tera_type 指定でテラスタルのSTAB(元タイプ一致なら2.0)。
    - item: 攻撃側の持ち物(life-orb / choice-band / choice-specs / expert-belt / muscle-band /
      wise-glasses / charcoal 等のタイプ強化アイテム)。
    - weather: sun/rain/sand/snow(晴れ/雨/砂/雪。日本語可)。晴れ雨は炎水技、砂雪は岩氷の防御に影響。
    - 攻守のポケモン名・技名は英語slug/日本語名どちらも可(日本語は要 build_db --aliases)。
    - tera_type は攻撃側のSTABのみに反映(防御側の相性計算には影響しない)。
    - 命中(光の粉等)は別軸。本ツールは命中前提のダメージ・KO%を返す(命中率は calc_accuracy)。
      可変多段(2-5発)の ko_chance はヒット数分布で重み付け、ko_chance_all_hits は最大ヒット前提。
    """
    if protean and tera_type:
        return {"error": "protean と tera_type は同時に指定できません(どちらか一方)。"}
    if tera_type and tera_type.lower() not in TYPES:
        return {"error": f"不明なテラスタイプ: {tera_type}"}
    err = (
        _validate_spread(level, ivs=[attacker_iv], evs=[attacker_offense_ev])
        or _validate_spread(level, ivs=[defender_iv], evs=[defender_hp_ev, defender_defense_ev])
    )
    if err:
        return {"error": err}

    try:
        mv = data.get_move(move)
        atk_p = data.get_pokemon(attacker)
        def_p = data.get_pokemon(defender)
    except data.NotFound as e:
        return {"error": str(e)}

    damage_class = mv.get("damage_class")
    if damage_class == "status":
        return {"error": f"{move} は変化技でダメージを与えません。"}
    physical = damage_class == "physical"
    category = "physical" if physical else "special"
    move_type = mv["type"]
    item_slug = data.slugify(item) if item else None
    type_eff = effectiveness(move_type, def_p["types"])

    off_key, def_key = ("atk", "def") if physical else ("spa", "spd")
    attack_stat = _calc_stat(
        atk_p["base_stats"][off_key], attacker_iv, attacker_offense_ev, level,
        nature_multiplier(attacker_nature, off_key),
    )
    # こだわり系は攻撃実数値に乗る
    attack_stat = poke_round(attack_stat * modifiers.attack_item_multiplier(item_slug, category))

    defense_stat = _calc_stat(
        def_p["base_stats"][def_key], defender_iv, defender_defense_ev, level,
        nature_multiplier(defender_nature, def_key),
    )
    # 砂(岩のとくぼう)・雪(氷のぼうぎょ)は防御実数値に乗る
    defense_stat = poke_round(
        defense_stat * modifiers.weather_defense_multiplier(weather, def_p["types"], category)
    )
    defender_hp = _calc_stat(
        def_p["base_stats"]["hp"], defender_iv, defender_hp_ev, level, is_hp=True,
    )

    stab = gen9_stab(move_type, atk_p["types"], protean=protean, tera_type=tera_type)
    weather_atk = modifiers.weather_attack_multiplier(weather, move_type)
    final_other = other * modifiers.final_item_multiplier(item_slug, move_type, category, type_eff)

    result = damage_from_species(
        level=level,
        move_name=mv["name"],
        move_type=move_type,
        base_power=mv["power"],
        min_hits=mv.get("min_hits") or 1,
        max_hits=mv.get("max_hits") or 1,
        attacker_types=atk_p["types"],
        attack_stat=attack_stat,
        defender_types=def_p["types"],
        defense_stat=defense_stat,
        defender_hp=defender_hp,
        stab_override=stab,
        weather=weather_atk,
        crit=crit,
        other=final_other,
    )
    out = asdict(result)
    out["attack_stat"] = attack_stat
    out["defense_stat"] = defense_stat
    out["stab"] = stab
    out["item"] = item_slug
    out["weather"] = weather
    out["move"] = mv["name"]
    out["damage_class"] = damage_class
    return out


@mcp.tool()
def calc_accuracy(
    move: str,
    bright_powder: bool = False,
    compound_eyes: bool = False,
    accuracy_stage: int = 0,
    evasion_stage: int = 0,
) -> dict:
    """技の命中率を計算。光の粉(x0.9)・ふくがん(x1.3)・命中/回避ランクに対応。

    トリプルアクセル/トリプルキックは各撃ごとに独立判定するため、当たった回数の分布と
    「全段命中する確率」も返す(例: トリプルアクセル vs 光の粉 = 各撃81%、3発命中 53.1%)。
    """
    try:
        mv = data.get_move(move)
    except data.NotFound as e:
        return {"error": str(e)}

    p = accuracy.hit_probability(
        mv["accuracy"],
        accuracy_stage=accuracy_stage,
        evasion_stage=evasion_stage,
        bright_powder=bright_powder,
        compound_eyes=compound_eyes,
    )
    out = {
        "move": mv["name"],
        "base_accuracy": mv["accuracy"],
        "per_check_hit_chance": round(p, 6),
    }
    if accuracy.is_per_strike_move(mv["name"]):
        n = accuracy.strike_count(mv["name"])
        dist = accuracy.multihit_distribution(p, n)
        out["per_strike_independent"] = True
        out["strikes"] = n
        out["hit_count_distribution"] = {k: round(v, 6) for k, v in dist.items()}
        out["all_hits_chance"] = round(p ** n, 6)
    return out


def main() -> None:
    import logging

    # stdio はJSON-RPC専用。httpxのINFOログがstderrを汚すので静かにする。
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
