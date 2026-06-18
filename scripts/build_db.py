"""PokeAPI から全データを取得して SQLite にキャッシュする(オフライン化・任意)。

使い方:
    uv run python scripts/build_db.py            # 全部(ポケモン・技・日本語索引)
    uv run python scripts/build_db.py --moves     # 技だけ
    uv run python scripts/build_db.py --pokemon   # ポケモンだけ
    uv run python scripts/build_db.py --aliases   # 日本語名 -> slug 索引だけ
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from pokemon_mcp import data
from pokemon_mcp.data import API

CONCURRENCY = 12


async def _list(client: httpx.AsyncClient, kind: str) -> list[str]:
    resp = await client.get(f"{API}/{kind}?limit=100000", timeout=30.0)
    resp.raise_for_status()
    return [r["name"] for r in resp.json()["results"]]


async def _ingest(client: httpx.AsyncClient, kind: str, name: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        try:
            resp = await client.get(f"{API}/{kind}/{name}", timeout=30.0)
            resp.raise_for_status()
            data.ingest(kind, name, resp.json())  # move は ja エイリアスも自動登録
            return True
        except Exception as e:  # noqa: BLE001 - 1件の失敗で全体を止めない
            print(f"  ! skip {kind}/{name}: {e}", file=sys.stderr)
            return False


async def _species_alias(client: httpx.AsyncClient, name: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        try:
            resp = await client.get(f"{API}/pokemon-species/{name}", timeout=30.0)
            resp.raise_for_status()
            data.register_pokemon_alias(resp.json())
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip species/{name}: {e}", file=sys.stderr)
            return False


async def build(kinds: set[str]) -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient() as client:
        for kind in ("pokemon", "move"):
            if kind not in kinds:
                continue
            names = await _list(client, kind)
            print(f"{kind}: {len(names)} 件を取得中...")
            results = await asyncio.gather(*(_ingest(client, kind, n, sem) for n in names))
            print(f"{kind}: {sum(results)}/{len(names)} 件キャッシュ完了")

        if "aliases" in kinds:
            # 技の日本語名は move ingest で自動登録される。ポケモンは species から登録。
            if "move" not in kinds:
                names = await _list(client, "move")
                print(f"move(ja索引): {len(names)} 件...")
                await asyncio.gather(*(_ingest(client, "move", n, sem) for n in names))
            species = await _list(client, "pokemon-species")
            print(f"pokemon(ja索引): {len(species)} 件...")
            results = await asyncio.gather(*(_species_alias(client, n, sem) for n in species))
            print(f"pokemon(ja索引): {sum(results)}/{len(species)} 件登録完了")


def main() -> None:
    args = set(sys.argv[1:])
    kinds: set[str] = set()
    if "--pokemon" in args:
        kinds.add("pokemon")
    if "--moves" in args:
        kinds.add("move")
    if "--aliases" in args:
        kinds.add("aliases")
    if not kinds:
        kinds = {"pokemon", "move", "aliases"}
    asyncio.run(build(kinds))


if __name__ == "__main__":
    main()
