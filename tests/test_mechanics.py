"""端数処理・相性無効化・テラスSTAB・命中率(光の粉)の検証。"""

import pytest

from pokemon_mcp.accuracy import hit_probability, multihit_distribution
from pokemon_mcp.damage import gen9_stab, poke_round
from pokemon_mcp.type_chart import effectiveness


def test_poke_round_half_down():
    assert poke_round(0.5) == 0      # ちょうど0.5は切り捨て
    assert poke_round(1.5) == 1
    assert poke_round(2.5) == 2
    assert poke_round(2.6) == 3
    assert poke_round(2.4) == 2


def test_effectiveness_immunity():
    assert effectiveness("normal", ["ghost"]) == 0.0
    assert effectiveness("ground", ["flying"]) == 0.0
    assert effectiveness("dragon", ["fairy"]) == 0.0


def test_gen9_stab():
    chompy = ["grass", "dark"]  # マスカーニャ
    # 変幻自在: 常に1.5
    assert gen9_stab("ice", chompy, protean=True) == 1.5
    # テラス: テラス=技 だが 元タイプに無い -> 1.5
    assert gen9_stab("ice", chompy, tera_type="ice") == 1.5
    # テラス: テラス=技=元タイプ -> 2.0
    assert gen9_stab("dark", chompy, tera_type="dark") == 2.0
    # 通常一致
    assert gen9_stab("dark", chompy) == 1.5
    # 不一致
    assert gen9_stab("ice", chompy) == 1.0


def test_accuracy_bright_powder():
    # 命中90の技 x 光の粉(x0.9) = 81%
    p = hit_probability(90, bright_powder=True)
    assert round(p, 2) == 0.81
    # 必中技(accuracy None)は常に当たる
    assert hit_probability(None, bright_powder=True) == 1.0


def test_triple_axel_bright_powder_all_hits():
    # トリプルアクセル(各撃90)x 光の粉 -> 各撃81%、3発命中の確率は 0.81^3
    p = hit_probability(90, bright_powder=True)
    dist = multihit_distribution(p, 3)
    assert round(dist[3], 6) == 0.531441
    assert round(dist[0], 6) == 0.19          # 初撃ミス
    assert round(sum(dist.values()), 6) == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
