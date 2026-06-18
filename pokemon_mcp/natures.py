"""性格補正。stat キーは atk/def/spa/spd/spe(HPと命中/回避は補正対象外)。"""

# 英語名 -> (上昇ステータス, 下降ステータス)
NATURES: dict[str, tuple[str | None, str | None]] = {
    "hardy": (None, None), "lonely": ("atk", "def"), "brave": ("atk", "spe"),
    "adamant": ("atk", "spa"), "naughty": ("atk", "spd"),
    "bold": ("def", "atk"), "docile": (None, None), "relaxed": ("def", "spe"),
    "impish": ("def", "spa"), "lax": ("def", "spd"),
    "timid": ("spe", "atk"), "hasty": ("spe", "def"), "serious": (None, None),
    "jolly": ("spe", "spa"), "naive": ("spe", "spd"),
    "modest": ("spa", "atk"), "mild": ("spa", "def"), "quiet": ("spa", "spe"),
    "bashful": (None, None), "rash": ("spa", "spd"),
    "calm": ("spd", "atk"), "gentle": ("spd", "def"), "sassy": ("spd", "spe"),
    "careful": ("spd", "spa"), "quirky": (None, None),
}

# 日本語名 -> 英語名(陽気・意地っ張り 等で渡せるように)
JP_ALIASES: dict[str, str] = {
    "がんばりや": "hardy", "さみしがり": "lonely", "ゆうかん": "brave",
    "いじっぱり": "adamant", "やんちゃ": "naughty",
    "ずぶとい": "bold", "すなお": "docile", "のんき": "relaxed",
    "わんぱく": "impish", "のうてんき": "lax",
    "おくびょう": "timid", "せっかち": "hasty", "まじめ": "serious",
    "ようき": "jolly", "むじゃき": "naive",
    "ひかえめ": "modest", "おっとり": "mild", "れいせい": "quiet",
    "てれや": "bashful", "うっかりや": "rash",
    "おだやか": "calm", "おとなしい": "gentle", "なまいき": "sassy",
    "しんちょう": "careful", "きまぐれ": "quirky",
}


def normalize_nature(name: str) -> str:
    key = name.strip().lower()
    return JP_ALIASES.get(name.strip(), key)


def nature_multiplier(nature: str, stat: str) -> float:
    """指定ステータスへの性格補正(1.1 / 1.0 / 0.9)。"""
    up, down = NATURES.get(normalize_nature(nature), (None, None))
    if stat == up:
        return 1.1
    if stat == down:
        return 0.9
    return 1.0
