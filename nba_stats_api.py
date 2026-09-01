

import aiohttp
from datetime import datetime, timedelta

BASE = "https://stats.nba.com/stats"

HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d"]


TEAM_ID_TO_ABBR = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
    1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
    1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
    1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
    1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
    1610612762: "UTA", 1610612764: "WAS",
}


TEAM_ID_TO_NAME = {
    1610612737: ("Atlanta", "Hawks"), 1610612738: ("Boston", "Celtics"),
    1610612751: ("Brooklyn", "Nets"), 1610612766: ("Charlotte", "Hornets"),
    1610612741: ("Chicago", "Bulls"), 1610612739: ("Cleveland", "Cavaliers"),
    1610612742: ("Dallas", "Mavericks"), 1610612743: ("Denver", "Nuggets"),
    1610612765: ("Detroit", "Pistons"), 1610612744: ("Golden State", "Warriors"),
    1610612745: ("Houston", "Rockets"), 1610612754: ("Indiana", "Pacers"),
    1610612746: ("LA", "Clippers"), 1610612747: ("Los Angeles", "Lakers"),
    1610612763: ("Memphis", "Grizzlies"), 1610612748: ("Miami", "Heat"),
    1610612749: ("Milwaukee", "Bucks"), 1610612750: ("Minnesota", "Timberwolves"),
    1610612740: ("New Orleans", "Pelicans"), 1610612752: ("New York", "Knicks"),
    1610612760: ("Oklahoma City", "Thunder"), 1610612753: ("Orlando", "Magic"),
    1610612755: ("Philadelphia", "76ers"), 1610612756: ("Phoenix", "Suns"),
    1610612757: ("Portland", "Trail Blazers"), 1610612758: ("Sacramento", "Kings"),
    1610612759: ("San Antonio", "Spurs"), 1610612761: ("Toronto", "Raptors"),
    1610612762: ("Utah", "Jazz"), 1610612764: ("Washington", "Wizards"),
}


def _team_id_matches(team_id: int, query: str) -> bool:
    abbr = TEAM_ID_TO_ABBR.get(team_id, "").lower()
    city, nickname = TEAM_ID_TO_NAME.get(team_id, ("", ""))
    candidates = (abbr, city.lower(), nickname.lower(), f"{city} {nickname}".lower())
    return any(query == c or (query in c and c) for c in candidates)


async def _get(url: str, params: dict) -> dict:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            return await resp.json()


def _rows_to_dicts(result_set: dict) -> list[dict]:
    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])
    return [dict(zip(headers, row)) for row in rows]


def find_result_set(data: dict, name: str) -> dict | None:
    for rs in data.get("resultSets", []):
        if rs.get("name") == name:
            return rs
    return None


def get_rows(data: dict, name: str) -> list[dict]:

    rs = find_result_set(data, name)
    return _rows_to_dicts(rs) if rs else []


def parse_date_arg(text: str) -> str | None:

    text = text.strip().lower()
    today = datetime.now()

    if text == "today":
        return today.strftime("%m/%d/%Y")
    if text == "yesterday":
        return (today - timedelta(days=1)).strftime("%m/%d/%Y")

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%m/%d":
            parsed = parsed.replace(year=today.year)
            if parsed > today:
                parsed = parsed.replace(year=today.year - 1)
        return parsed.strftime("%m/%d/%Y")

    return None


async def get_scoreboard(date: str | None = None) -> dict:

    date = date or datetime.now().strftime("%m/%d/%Y")
    params = {"GameDate": date, "LeagueID": "00", "DayOffset": "0"}
    return await _get(f"{BASE}/scoreboardv2", params=params)


def find_game_for_team(scoreboard_data: dict, team_query: str) -> str | None:

    query = team_query.strip().lower()

    for row in get_rows(scoreboard_data, "GameHeader"):
        home_id = row.get("HOME_TEAM_ID")
        away_id = row.get("VISITOR_TEAM_ID")
        if _team_id_matches(home_id, query) or _team_id_matches(away_id, query):
            return row.get("GAME_ID")

    for row in get_rows(scoreboard_data, "LineScore"):
        city = str(row.get("TEAM_CITY_NAME", "")).lower()
        nickname = str(row.get("TEAM_NAME", "")).lower()
        abbr = str(row.get("TEAM_ABBREVIATION", "")).lower()
        full = f"{city} {nickname}".strip()
        if query == abbr or query in nickname or query in city or query in full:
            return row.get("GAME_ID")

    return None


async def get_boxscore(game_id: str) -> dict:

    params = {"GameID": game_id, "StartPeriod": "0", "EndPeriod": "10", "StartRange": "0", "EndRange": "28800", "RangeType": "0"}
    return await _get(f"{BASE}/boxscoretraditionalv3", params=params)
