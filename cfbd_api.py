

import os
import aiohttp
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE = "https://api.collegefootballdata.com"

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d"]


def _get_api_key() -> str:
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        raise RuntimeError(
            "CFBD_API_KEY environment variable isn't set. Get a free key at "
            "https://collegefootballdata.com/key and set it the same way as "
            "DISCORD_BOT_TOKEN."
        )
    return key


async def _get(path: str, params: dict) -> dict | list:
    headers = {"Authorization": f"Bearer {_get_api_key()}", "Accept": "application/json"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"{BASE}{path}", params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            return await resp.json()


def parse_date_arg(text: str) -> str | None:

    text = text.strip().lower()
    today = datetime.now()

    if text == "today":
        return today.strftime("%Y-%m-%d")
    if text == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%m/%d":
            parsed = parsed.replace(year=today.year)
            if parsed > today:
                parsed = parsed.replace(year=today.year - 1)
        return parsed.strftime("%Y-%m-%d")

    return None


async def get_team_games(team: str, year: int) -> list[dict]:

    data = await _get("/games", {"year": year, "team": team})
    return data if isinstance(data, list) else []


async def get_all_games_for_season(year: int) -> list[dict]:

    data = await _get("/games", {"year": year})
    return data if isinstance(data, list) else []


def find_games_on_date(games: list[dict], date_iso: str) -> list[dict]:

    eastern = ZoneInfo("America/New_York")
    matches = []
    for game in games:
        start = game.get("startDate", "")
        if not start:
            continue
        try:
            dt_utc = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if dt_utc.astimezone(eastern).strftime("%Y-%m-%d") == date_iso:
            matches.append(game)
    return matches


def find_game_on_date(games: list[dict], date_iso: str) -> dict | None:

    eastern = ZoneInfo("America/New_York")
    for game in games:
        start = game.get("startDate", "")
        if not start:
            continue
        try:
            dt_utc = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        dt_eastern = dt_utc.astimezone(eastern)
        if dt_eastern.strftime("%Y-%m-%d") == date_iso:
            return game
    return None


_team_mascot_cache: dict[str, str] | None = None


async def get_all_teams() -> list[dict]:

    data = await _get("/teams", {})
    return data if isinstance(data, list) else []


async def _load_team_mascots() -> dict[str, str]:

    global _team_mascot_cache
    if _team_mascot_cache is not None:
        return _team_mascot_cache
    data = await _get("/teams", {})
    _team_mascot_cache = {
        t.get("school", ""): t.get("mascot", "")
        for t in (data if isinstance(data, list) else [])
        if t.get("school")
    }
    return _team_mascot_cache


async def get_team_full_name(school: str) -> str:

    mascots = await _load_team_mascots()
    mascot = mascots.get(school, "")
    return f"{school} {mascot}".strip() if mascot else school


async def get_game_player_stats(year: int, week: int, team: str) -> list[dict]:

    data = await _get("/games/players", {"year": year, "week": week, "team": team})
    if isinstance(data, list) and data:
        return data[0].get("teams", [])
    return []
