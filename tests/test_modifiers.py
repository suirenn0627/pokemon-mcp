"""道具補正・天候・日本語名解決の検証(ネットワーク不要)。"""

import pytest

from pokemon_mcp import data, modifiers
from pokemon_mcp.damage import damage_rolls


def test_weather_attack():
    assert modifiers.weather_attack_multiplier("sun", "fire") == 1.5
    assert modifiers.weather_attack_multiplier("sun", "water") == 0.5
    assert modifiers.weather_attack_multiplier("rain", "water") == 1.5
    assert modifiers.weather_attack_multiplier("はれ", "fire") == 1.5
    assert modifiers.weather_attack_multiplier(None, "fire") == 1.0


def test_weather_defense():
    assert modifiers.weather_defense_multiplier("sand", ["rock", "ground"], "special") == 1.5
    assert modifiers.weather_defense_multiplier("sand", ["rock"], "physical") == 1.0
    assert modifiers.weather_defense_multiplier("snow", ["ice"], "physical") == 1.5
    assert modifiers.weather_defense_multiplier("snow", ["ice"], "special") == 1.0


def test_attack_items():
    assert modifiers.attack_item_multiplier("choice-band", "physical") == 1.5
    assert modifiers.attack_item_multiplier("choice-band", "special") == 1.0
    assert modifiers.attack_item_multiplier("choice-specs", "special") == 1.5
    assert modifiers.attack_item_multiplier(None, "physical") == 1.0


def test_final_items():
    assert modifiers.final_item_multiplier("life-orb", "fire", "special", 2.0) == pytest.approx(1.3, abs=0.01)
    assert modifiers.final_item_multiplier("expert-belt", "fire", "special", 1.0) == 1.0  # 等倍は無効
    assert modifiers.final_item_multiplier("expert-belt", "fire", "special", 2.0) == pytest.approx(1.2, abs=0.01)
    assert modifiers.final_item_multiplier("charcoal", "fire", "special", 1.0) == pytest.approx(1.2, abs=0.01)
    assert modifiers.final_item_multiplier("charcoal", "water", "special", 1.0) == 1.0


def test_weather_changes_damage():
    base = max(damage_rolls(50, 90, 150, 100, stab=1.5, type_eff=1.0))
    sun = max(damage_rolls(50, 90, 150, 100, stab=1.5, type_eff=1.0, weather=1.5))
    rain = max(damage_rolls(50, 90, 150, 100, stab=1.5, type_eff=1.0, weather=0.5))
    assert sun > base > rain


def test_jp_alias_resolution(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(data, "_schema_ready", False)
    # 英字はそのまま slug 化
    assert data.resolve_name("pokemon", "garchomp") == "garchomp"
    # 日本語はエイリアス表で解決
    data.put_alias("pokemon", "ガブリアス", "garchomp")
    assert data.resolve_name("pokemon", "ガブリアス") == "garchomp"
    # 未登録の日本語は親切なエラー
    with pytest.raises(data.NotFound):
        data.resolve_name("pokemon", "みとうろくめい")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
