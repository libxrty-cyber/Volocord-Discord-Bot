

import asyncio
import json
import sys

import espn_api


async def main():
    if len(sys.argv) < 2:
        print('Usage: python debug_nfl_boxscore.py "<team>" [date]')
        return

    team_query = sys.argv[1]
    date_text = sys.argv[2] if len(sys.argv) > 2 else None
    date_arg = espn_api.parse_date_arg(date_text) if date_text else None

    print(f"Fetching NFL scoreboard (date={date_arg or 'today'})...")
    scoreboard = await espn_api.get_scoreboard("nfl", date=date_arg)

    event = espn_api.find_event_for_team(scoreboard, team_query)
    if event is None:
        print(f"No game found for '{team_query}' on that date.")
        return

    event_id = event.get("id")
    print(f"Found event id {event_id}, fetching summary...")
    summary = await espn_api.get_summary("nfl", event_id)

    with open("debug_nfl_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("Wrote full response to debug_nfl_summary.json")

    header = summary.get("header", {})
    competitions = header.get("competitions", [])
    if competitions:
        print("\n=== COMPETITOR RECORDS (raw) ===")
        for c in competitions[0].get("competitors", []):
            team_abbr = c.get("team", {}).get("abbreviation", "?")
            print(f"  {team_abbr}: records={c.get('records')!r}  record={c.get('record')!r}")

    players = summary.get("boxscore", {}).get("players", [])
    if not players:
        print("\n!! No 'boxscore.players' found. Top-level keys:", list(summary.keys()))
        return

    for team_block in players:
        abbr = team_block.get("team", {}).get("abbreviation", "?")
        print(f"\n=== TEAM: {abbr} ===")
        for cat in team_block.get("statistics", []):
            labels = cat.get("labels", [])
            athletes = cat.get("athletes", [])
            print(f"  category: labels={labels}  ({len(athletes)} athletes)")
            for a in athletes:
                name = a.get("athlete", {}).get("displayName", a.get("athlete", {}).get("shortName", "?"))
                pos_entry_level = a.get("position")
                pos_athlete_level = a.get("athlete", {}).get("position")
                print(f"    {name}: entry.position={pos_entry_level!r}  athlete.position={pos_athlete_level!r}")
            if athletes:
                print(f"    (sample full athlete keys: {list(athletes[0].keys())})")
                print(f"    (sample athlete sub-object keys: {list(athletes[0].get('athlete', {}).keys())})")


if __name__ == "__main__":
    asyncio.run(main())
