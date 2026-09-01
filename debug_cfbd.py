

import asyncio
import json
import sys
from datetime import datetime

import cfbd_api


async def main():
    if len(sys.argv) < 2:
        print('Usage: python debug_cfbd.py "<team>" [date]')
        return

    team_query = sys.argv[1]
    date_text = sys.argv[2] if len(sys.argv) > 2 else None
    date_iso = cfbd_api.parse_date_arg(date_text) if date_text else cfbd_api.parse_date_arg("today")
    year = int(date_iso[:4])

    print(f"Fetching {year} season games for '{team_query}'...")
    games = await cfbd_api.get_team_games(team_query, year)

    with open("debug_cfbd_games.json", "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2)
    print(f"Wrote {len(games)} games to debug_cfbd_games.json")

    if games:
        print("\nFirst game's top-level keys:", list(games[0].keys()))
        print("First game (pretty-printed):")
        print(json.dumps(games[0], indent=2)[:1500])

    game = cfbd_api.find_game_on_date(games, date_iso)
    if game is None:
        print(f"\nNo game found for '{team_query}' on {date_iso}.")
        eastern_dates = sorted({
            datetime.fromisoformat(g["startDate"].replace("Z", "+00:00")).astimezone(cfbd_api.ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
            for g in games if g.get("startDate")
        })
        print("Available dates this season (Eastern time):", eastern_dates)
        return

    print(f"\nFound game on {date_iso}, week {game.get('week')}")

    print("\nFetching player stats...")
    player_stats = await cfbd_api.get_game_player_stats(year, game.get("week"), team_query)

    with open("debug_cfbd_players.json", "w", encoding="utf-8") as f:
        json.dump(player_stats, f, indent=2)
    print(f"Wrote player stats to debug_cfbd_players.json")

    if player_stats:
        print("\nFirst team block's top-level keys:", list(player_stats[0].keys()))
        print("First team block (pretty-printed, truncated):")
        print(json.dumps(player_stats[0], indent=2)[:2000])
    else:
        print("!! player_stats came back empty -- check debug_cfbd_players.json / the request params.")


if __name__ == "__main__":
    asyncio.run(main())
