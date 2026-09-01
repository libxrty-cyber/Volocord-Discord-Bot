

import asyncio
import json
import sys

import mlb_stats_api


async def main():
    if len(sys.argv) < 2:
        print('Usage: python debug_boxscore.py "<team>" [date]')
        return

    team_query = sys.argv[1]
    date_text = sys.argv[2] if len(sys.argv) > 2 else None
    date_arg = mlb_stats_api.parse_date_arg(date_text) if date_text else None

    print(f"Fetching schedule (date={date_arg or 'today'})...")
    schedule = await mlb_stats_api.get_schedule(date=date_arg)

    game, total_games = mlb_stats_api.find_game_for_team(schedule, team_query)
    if game is None:
        print(f"No game found for '{team_query}' on that date.")
        return
    if total_games > 1:
        print(f"NOTE: doubleheader -- {total_games} games found, showing gameNumber={game.get('gameNumber')}")

    game_pk = game.get("gamePk")
    print(f"Found gamePk {game_pk}, status: {game.get('status', {})}")
    print(f"\nRaw 'linescore' key from schedule response:")
    print(json.dumps(game.get("linescore"), indent=2))
    print(f"\nAll top-level keys on the schedule game object: {list(game.keys())}")

    with open("debug_schedule_game.json", "w", encoding="utf-8") as f:
        json.dump(game, f, indent=2)
    print("\nWrote schedule game to debug_schedule_game.json")

    print("Fetching boxscore...")
    boxscore = await mlb_stats_api.get_boxscore(game_pk)

    with open("debug_boxscore.json", "w", encoding="utf-8") as f:
        json.dump(boxscore, f, indent=2)
    print("Wrote full boxscore to debug_boxscore.json")

    teams = boxscore.get("teams", {})
    for side in ("away", "home"):
        team_box = teams.get(side, {})
        print(f"\n--- {side.upper()} ---")
        print("team block keys:", list(team_box.keys()))
        print("team.abbreviation:", team_box.get("team", {}).get("abbreviation"))
        print("pitchers (ordered ids):", team_box.get("pitchers"))

        players = team_box.get("players", {})
        print(f"{len(players)} player entries.")

        first_hitter = None
        for pdata in players.values():
            batting = pdata.get("stats", {}).get("batting", {})
            if batting.get("hits", 0) > 0:
                first_hitter = pdata
                break
        if first_hitter:
            print("\nSample hitter-with-a-hit entry:")
            print(json.dumps(first_hitter, indent=2)[:1200])
        else:
            print("No hitter with a hit found (check debug_boxscore.json manually).")

        pitcher_ids = team_box.get("pitchers", [])
        if pitcher_ids:
            starter_key = f"ID{pitcher_ids[0]}"
            starter = players.get(starter_key)
            if starter:
                print("\nSample presumed-starter pitcher entry:")
                print(json.dumps(starter, indent=2)[:1200])


if __name__ == "__main__":
    asyncio.run(main())
