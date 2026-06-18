"""PokeAPI からの構造化データ取得 + SQLite キャッシュ(embeddingなし・exact lookup)。

未取得のものは PokeAPI から遅延フェッチして保存するため、初回だけネットワークに触れる。
全件をオフライン化したい場合は scripts/build_db.py を実行する。
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import httpx

_ASCII = re.compile(r"^[\x00-\x7F]+$")

API = "https://pokeapi.co/api/v2"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pokedex.db"
TIMEOUT = 20.0

_STAT_MAP = {
    "hp": "hp",
    "attack": "atk",
    "defense": "def",
    "special-attack": "spa",
    "special-defense": "spd",
    "speed": "spe",
}

_schema_ready = False


class NotFound(Exception):
    """PokeAPIに該当する名前が存在しない(ユーザー入力起因)。"""


def _conn() -> sqlite3.Connection:
    global _schema_ready
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    if not _schema_ready:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (kind TEXT, name TEXT, json TEXT, PRIMARY KEY (kind, name))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS alias (kind TEXT, alias TEXT, slug TEXT, PRIMARY KEY (kind, alias))"
        )
        _schema_ready = True
    return conn


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-").replace("'", "")


def _cache_get(kind: str, name: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT json FROM cache WHERE kind = ? AND name = ?", (kind, name)
        ).fetchone()
    return json.loads(row[0]) if row else None


def _cache_put(kind: str, name: str, data: dict) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (kind, name, json) VALUES (?, ?, ?)",
            (kind, name, json.dumps(data, ensure_ascii=False)),
        )


def put_alias(kind: str, alias: str, slug: str) -> None:
    """日本語名などの別名 -> slug を登録。"""
    if not alias:
        return
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO alias (kind, alias, slug) VALUES (?, ?, ?)",
            (kind, alias.strip(), slug),
        )


def _lookup_alias(kind: str, alias: str) -> str | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT slug FROM alias WHERE kind = ? AND alias = ?", (kind, alias.strip())
        ).fetchone()
    return row[0] if row else None


def resolve_name(kind: str, name: str) -> str:
    """入力名を slug に解決。英字はそのまま、日本語はエイリアス表を引く。"""
    if _ASCII.match(name):
        return _slug(name)
    slug = _lookup_alias(kind, name)
    if slug:
        return slug
    raise NotFound(
        f"日本語名 '{name}' は未登録です。"
        "`uv run python scripts/build_db.py --aliases` で日本語索引を構築してください。"
    )


def _ja_name(names: list[dict] | None) -> str | None:
    """PokeAPI の names 配列から日本語名(ja-Hrkt 優先)を取り出す。"""
    if not names:
        return None
    by_lang = {n["language"]["name"]: n["name"] for n in names}
    return by_lang.get("ja-Hrkt") or by_lang.get("ja")


def _fetch(path: str) -> dict:
    url = f"{API}/{path}"
    try:
        resp = httpx.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise NotFound(f"PokeAPIに存在しません: {path}") from e
        raise RuntimeError(f"PokeAPI取得に失敗 ({path}): {e}") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"PokeAPI接続に失敗 ({path}): {e}") from e
    return resp.json()


def _short_effect(raw: dict) -> str:
    for entry in raw.get("effect_entries", []):
        if entry.get("language", {}).get("name") == "en":
            return entry.get("short_effect") or entry.get("effect") or ""
    return ""


def normalize_pokemon(raw: dict) -> dict:
    stats = {}
    for s in raw["stats"]:
        key = _STAT_MAP.get(s["stat"]["name"])
        if key:  # 未知の新ステータスは無視(将来のAPI変更に耐える)
            stats[key] = s["base_stat"]
    return {
        "name": raw["name"],
        "types": [t["type"]["name"] for t in sorted(raw["types"], key=lambda x: x["slot"])],
        "base_stats": stats,
        "abilities": [a["ability"]["name"] for a in raw["abilities"]],
    }


def normalize_move(raw: dict) -> dict:
    meta = raw.get("meta") or {}
    return {
        "name": raw["name"],
        "ja": _ja_name(raw.get("names")),
        "type": raw["type"]["name"],
        "power": raw.get("power") or 0,
        "accuracy": raw.get("accuracy"),  # None は必中
        "pp": raw.get("pp"),
        "damage_class": (raw.get("damage_class") or {}).get("name"),  # physical/special/status
        "priority": raw.get("priority"),
        "min_hits": meta.get("min_hits"),
        "max_hits": meta.get("max_hits"),
        "effect": _short_effect(raw),
    }


def normalize_simple(raw: dict) -> dict:
    return {"name": raw["name"], "effect": _short_effect(raw)}


_NORMALIZERS = {
    "pokemon": normalize_pokemon,
    "move": normalize_move,
    "ability": normalize_simple,
    "item": normalize_simple,
}


def ingest(kind: str, name: str, raw: dict) -> None:
    """生のPokeAPIレスポンスを正規化してキャッシュに保存(build_db用の公開API)。"""
    slug = _slug(name)
    data = _NORMALIZERS[kind](raw)
    _cache_put(kind, slug, data)
    if kind == "move" and data.get("ja"):  # 技の日本語名は move 詳細から無料で取れる
        put_alias("move", data["ja"], slug)


def register_pokemon_alias(species_raw: dict) -> None:
    """/pokemon-species のレスポンスから日本語名 -> slug を登録(build_db用)。"""
    ja = _ja_name(species_raw.get("names"))
    if ja:
        put_alias("pokemon", ja, species_raw["name"])


def _get(kind: str, name: str) -> dict:
    slug = resolve_name(kind, name)
    cached = _cache_get(kind, slug)
    if cached is not None:
        return cached
    data = _NORMALIZERS[kind](_fetch(f"{kind}/{slug}"))
    _cache_put(kind, slug, data)
    if kind == "move" and data.get("ja"):
        put_alias("move", data["ja"], slug)
    return data


def get_pokemon(name: str) -> dict:
    return _get("pokemon", name)


def get_move(name: str) -> dict:
    return _get("move", name)


def get_ability(name: str) -> dict:
    return _get("ability", name)


def get_item(name: str) -> dict:
    return _get("item", name)
