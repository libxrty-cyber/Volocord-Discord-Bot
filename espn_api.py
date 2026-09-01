

import aiohttp
from datetime import datetime, timedelta


LEAGUES = {
    "mlb": ("baseball", "mlb"),
    "nba": ("basketball", "nba"),
    "nfl": ("football", "nfl"),
    "nhl": ("hockey", "nhl"),
    "cfb": ("football", "college-football"),
}

BASE = "https://site.api.espn.com/apis/site/v2/sports"


_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d"]


async def _get(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_scoreboard(sport: str, date: str | None = None) -> dict:

    sport_path, league_path = LEAGUES[sport]
    url = f"{BASE}/{sport_path}/{league_path}/scoreboard"
    if date:
        url += f"?dates={date}"
    return await _get(url)


def parse_date_arg(text: str) -> str | None:

    text = text.strip().lower()
    today = datetime.now()

    if text == "today":
        return today.strftime("%Y%m%d")
    if text == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y%m%d")

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%m/%d":
            parsed = parsed.replace(year=today.year)
            if parsed > today:
                parsed = parsed.replace(year=today.year - 1)
        return parsed.strftime("%Y%m%d")

    return None


async def get_summary(sport: str, event_id: str) -> dict:

    sport_path, league_path = LEAGUES[sport]
    url = f"{BASE}/{sport_path}/{league_path}/summary?event={event_id}"
    return await _get(url)


async def get_team_roster(sport: str, team_id) -> dict:

    sport_path, league_path = LEAGUES[sport]
    url = f"{BASE}/{sport_path}/{league_path}/teams/{team_id}/roster"
    return await _get(url)


def build_roster_position_map(roster_data: dict) -> dict[str, str]:

    position_map: dict[str, str] = {}
    athletes = roster_data.get("athletes", [])
    for group in athletes:

        items = group.get("items") if isinstance(group, dict) else None
        if items is not None:
            for player in items:
                name = player.get("displayName", "").lower()
                pos = (player.get("position") or {}).get("abbreviation", "")
                if name and pos:
                    position_map[name] = pos
        elif isinstance(group, dict) and "displayName" in group:

            name = group.get("displayName", "").lower()
            pos = (group.get("position") or {}).get("abbreviation", "")
            if name and pos:
                position_map[name] = pos
    return position_map


async def get_teams(sport: str) -> list[dict]:

    sport_path, league_path = LEAGUES[sport]
    url = f"{BASE}/{sport_path}/{league_path}/teams"
    data = await _get(url)
    teams = []
    league_block = data.get("sports", [{}])[0].get("leagues", [{}])[0]
    for entry in league_block.get("teams", []):
        team = entry.get("team", {})
        teams.append({
            "id": team.get("id", ""),
            "abbreviation": team.get("abbreviation", ""),
            "displayName": team.get("displayName", ""),
        })
    return teams


async def get_transactions(sport: str, page: int = 1) -> dict:

    sport_path, league_path = LEAGUES[sport]
    url = f"{BASE}/{sport_path}/{league_path}/transactions?page={page}"
    return await _get(url)


async def get_all_transactions(sport: str, since_iso: str = "2026-02-09", max_pages: int = 300) -> list[dict]:

    first = await get_transactions(sport, page=1)
    all_transactions = list(first.get("transactions", []))
    page_count = first.get("pageCount", 1)

    for page in range(2, min(page_count, max_pages) + 1):
        oldest_so_far = min((t.get("date", "") for t in all_transactions if t.get("date")), default="")
        if oldest_so_far and oldest_so_far[:10] < since_iso:
            break

        data = await get_transactions(sport, page=page)
        page_transactions = data.get("transactions", [])
        if not page_transactions:
            break
        all_transactions.extend(page_transactions)

    return all_transactions


def find_event_for_team(scoreboard: dict, team_query: str):

    query = team_query.strip().lower()
    for event in scoreboard.get("events", []):
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        competitors = competitions[0].get("competitors", [])
        for c in competitors:
            team = c.get("team", {})
            candidates = [
                team.get("displayName", ""),
                team.get("shortDisplayName", ""),
                team.get("name", ""),
                team.get("abbreviation", ""),
                team.get("location", ""),
            ]
            if any(query == cand.lower() or query in cand.lower() for cand in candidates if cand):
                return event
    return None
