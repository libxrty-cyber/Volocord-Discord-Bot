

import asyncio
import json
import sys

import nba_stats_api


async def main():
    if len(sys.argv) < 2:
        print('Usage: python debug_nba_boxscore.py "<team>" [date]')
        return

    team_query = sys.argv[1]
    date_text = sys.argv[2] if len(sys.argv) > 2 else None
    date_arg = nba_stats_api.parse_date_arg(date_text) if date_text else None

    print(f"Fetching NBA scoreboard (date={date_arg or 'today'})...")
    scoreboard = await nba_stats_api.get_scoreboard(date=date_arg)

    with open("debug_nba_scoreboard.json", "w", encoding="utf-8") as f:
        json.dump(scoreboard, f, indent=2)
    print("Wrote scoreboard to debug_nba_scoreboard.json")

    print("\nresultSet names in scoreboard:", [rs.get("name") for rs in scoreboard.get("resultSets", [])])

    line_score_rs = nba_stats_api.find_result_set(scoreboard, "LineScore")
    if line_score_rs:
        print("\nLineScore RAW headers:", line_score_rs.get("headers"))
        row_set = line_score_rs.get("rowSet", [])
        if row_set:
            print("LineScore RAW first row:", row_set[0])

    game_header_rs = nba_stats_api.find_result_set(scoreboard, "GameHeader")
    if game_header_rs:
        print("\nGameHeader RAW headers:", game_header_rs.get("headers"))
        row_set = game_header_rs.get("rowSet", [])
        if row_set:
            print("GameHeader RAW first row:", row_set[0])

    game_id = nba_stats_api.find_game_for_team(scoreboard, team_query)
    if game_id is None:
        print(f"No game found for '{team_query}' on that date.")
        line_score = nba_stats_api.get_rows(scoreboard, "LineScore")
        print(f"Teams that WERE found today: {[r.get('TEAM_NICKNAME') for r in line_score]}")
        return

    print(f"\nFound GAME_ID {game_id}")

    game_headers = nba_stats_api.get_rows(scoreboard, "GameHeader")
    header_row = next((r for r in game_headers if r.get("GAME_ID") == game_id), {})
    print("GameHeader row:", json.dumps(header_row, indent=2, default=str))

    line_score_rows = [r for r in nba_stats_api.get_rows(scoreboard, "LineScore") if r.get("GAME_ID") == game_id]
    print("\nLineScore rows for this game:")
    print(json.dumps(line_score_rows, indent=2, default=str))

    print("\nFetching boxscore (v3)...")
    boxscore = await nba_stats_api.get_boxscore(game_id)

    with open("debug_nba_boxscore.json", "w", encoding="utf-8") as f:
        json.dump(boxscore, f, indent=2)
    print("Wrote boxscore to debug_nba_boxscore.json")

    print("\nTop-level keys:", list(boxscore.keys()))
    inner = boxscore.get("boxScoreTraditional")
    if inner is None:
        print("!! No 'boxScoreTraditional' key -- dumping first 2000 chars raw:")
        print(json.dumps(boxscore, indent=2, default=str)[:2000])
    else:
        print("boxScoreTraditional keys:", list(inner.keys()))
        for side in ("homeTeam", "awayTeam"):
            team = inner.get(side)
            if not team:
                continue
            print(f"\n{side} keys:", list(team.keys()))
            print(f"{side} team-level 'statistics':")
            print(json.dumps(team.get("statistics"), indent=2, default=str))
            players = team.get("players", [])
            print(f"{side} has {len(players)} players.")
            if players:
                print(f"First player in {side} (pretty-printed):")
                print(json.dumps(players[0], indent=2, default=str)[:1500])


if __name__ == "__main__":
    asyncio.run(main())
