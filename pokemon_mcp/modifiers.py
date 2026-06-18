"""道具・天候によるダメージ補正(純関数)。

- 攻撃ステータス補正(こだわり系)は実数値に乗る。
- 最終補正(いのちのたま等)はダメージ式の other(pokeRound連鎖)に乗る。
- 天候の攻撃補正(晴れ/雨)は base に、防御補正(砂/雪)は防御実数値に乗る。
"""

from __future__ import annotations

# 4096基準の倍率(第6世代以降)
LIFE_ORB = 5324 / 4096      # いのちのたま x1.3
EXPERT_BELT = 4915 / 4096   # たつじんのおび x1.2(効果ばつぐん時のみ)
BAND_GLASSES = 4505 / 4096  # ちからのハチマキ/ものしりメガネ x1.1
TYPE_BOOST = 4915 / 4096    # タイプ強化アイテム/プレート x1.2
CHOICE = 1.5                # こだわり系 x1.5(攻撃実数値)

# タイプ強化アイテム slug -> 強化タイプ
TYPE_BOOST_ITEMS = {
    "charcoal": "fire", "mystic-water": "water", "magnet": "electric",
    "miracle-seed": "grass", "never-melt-ice": "ice", "black-belt": "fighting",
    "poison-barb": "poison", "soft-sand": "ground", "sharp-beak": "flying",
    "twisted-spoon": "psychic", "silver-powder": "bug", "hard-stone": "rock",
    "spell-tag": "ghost", "dragon-fang": "dragon", "black-glasses": "dark",
    "metal-coat": "steel", "silk-scarf": "normal", "fairy-feather": "fairy",
}

_SUN = {"sun", "harsh-sunlight", "sunny", "晴れ", "はれ"}
_RAIN = {"rain", "あめ", "雨"}
_SAND = {"sand", "sandstorm", "すなあらし", "砂"}
_SNOW = {"snow", "hail", "ゆき", "雪", "あられ"}


def attack_item_multiplier(item: str | None, category: str) -> float:
    """攻撃実数値に乗る補正(こだわりハチマキ/メガネ)。"""
    if item == "choice-band" and category == "physical":
        return CHOICE
    if item == "choice-specs" and category == "special":
        return CHOICE
    return 1.0


def final_item_multiplier(item: str | None, move_type: str, category: str, type_eff: float) -> float:
    """ダメージ式 other に乗る最終補正。"""
    if not item:
        return 1.0
    if item == "life-orb":
        return LIFE_ORB
    if item == "expert-belt":
        return EXPERT_BELT if type_eff > 1 else 1.0
    if item == "muscle-band" and category == "physical":
        return BAND_GLASSES
    if item == "wise-glasses" and category == "special":
        return BAND_GLASSES
    if TYPE_BOOST_ITEMS.get(item) == move_type.lower():
        return TYPE_BOOST
    return 1.0


def weather_attack_multiplier(weather: str | None, move_type: str) -> float:
    """晴れ/雨による技タイプ補正(base に乗る)。"""
    w = (weather or "").lower()
    mt = move_type.lower()
    if w in _SUN:
        if mt == "fire":
            return 1.5
        if mt == "water":
            return 0.5
    if w in _RAIN:
        if mt == "water":
            return 1.5
        if mt == "fire":
            return 0.5
    return 1.0


def weather_defense_multiplier(weather: str | None, defender_types: list[str], category: str) -> float:
    """砂(いわ=とくぼう)・雪(こおり=ぼうぎょ)による防御補正。"""
    w = (weather or "").lower()
    types = [t.lower() for t in defender_types]
    if w in _SAND and "rock" in types and category == "special":
        return 1.5
    if w in _SNOW and "ice" in types and category == "physical":
        return 1.5
    return 1.0
