

import aiohttp
from datetime import datetime, timedelta

BASE = "https://statsapi.mlb.com/api/v1"


_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d"]


_team_abbr_cache: dict[int, str] | None = None


async def _get(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
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


async def get_schedule(date: str | None = None) -> dict:

    date = date or datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE}/schedule?sportId=1&date={date}&hydrate=linescore,probablePitcher"
    return await _get(url)


def find_game_for_team(schedule: dict, team_query: str, game_number: int | None = None) -> tuple[dict | None, int]:

    query = team_query.strip().lower()
    matches = []
    for date_block in schedule.get("dates", []):
        for game in date_block.get("games", []):
            teams = game.get("teams", {})
            for side in ("away", "home"):
                name = teams.get(side, {}).get("team", {}).get("name", "")
                if name and (query == name.lower() or query in name.lower()):
                    matches.append(game)
                    break

    if not matches:
        return None, 0

    matches.sort(key=lambda g: g.get("gameNumber", 1))

    if game_number is not None:
        for g in matches:
            if g.get("gameNumber") == game_number:
                return g, len(matches)
        return None, len(matches)

    return matches[0], len(matches)


async def get_boxscore(game_pk) -> dict:

    url = f"{BASE}/game/{game_pk}/boxscore"
    return await _get(url)


async def _get_team_abbr_map() -> dict[int, str]:

    global _team_abbr_cache
    if _team_abbr_cache is not None:
        return _team_abbr_cache
    data = await _get(f"{BASE}/teams?sportId=1")
    _team_abbr_cache = {
        team["id"]: team.get("abbreviation", "")
        for team in data.get("teams", [])
        if "id" in team
    }
    return _team_abbr_cache


async def team_abbr(team_id: int) -> str:

    mapping = await _get_team_abbr_map()
    return mapping.get(team_id, "")


async def get_standings(season: str | None = None, league: str = "both") -> dict:

    season = season or str(datetime.now().year)
    league_ids = {"al": "103", "nl": "104"}.get(league.lower(), "103,104")
    url = f"{BASE}/standings?leagueId={league_ids}&season={season}&standingsTypes=regularSeason"
    return await _get(url)


async def find_player_id(name: str) -> int | None:

    import urllib.parse
    query = urllib.parse.quote(name)
    data = await _get(f"{BASE}/people/search?names={query}")
    people = data.get("people", [])
    return people[0].get("id") if people else None


async def get_player_season_stats(person_id: int, season: int) -> dict:

    url = f"{BASE}/people/{person_id}?hydrate=currentTeam,stats(group=[hitting,pitching],type=[season],season={season})"
    data = await _get(url)
    people = data.get("people", [])
    return people[0] if people else {}


async def get_teams() -> list[dict]:

    data = await _get(f"{BASE}/teams?sportId=1")
    return [
        {"id": t.get("id"), "abbreviation": t.get("abbreviation", ""), "name": t.get("name", "")}
        for t in data.get("teams", [])
    ]


async def find_team_id(team_query: str) -> int | None:

    query = team_query.strip().lower()
    teams = await get_teams()
    for t in teams:
        name = t.get("name", "").lower()
        abbr = t.get("abbreviation", "").lower()
        if query == abbr or query in name:
            return t.get("id")
    return None


async def get_next_scheduled_date(team_id: int, after_date: str, days_ahead: int = 30) -> str | None:

    start = datetime.strptime(after_date, "%Y-%m-%d") + timedelta(days=1)
    end = start + timedelta(days=days_ahead)
    url = (
        f"{BASE}/schedule?sportId=1&teamId={team_id}"
        f"&startDate={start.strftime('%Y-%m-%d')}&endDate={end.strftime('%Y-%m-%d')}"
    )
    data = await _get(url)
    dates = data.get("dates", [])
    if not dates:
        return None
    return dates[0].get("date")
