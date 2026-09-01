

import asyncio
import json
import sys

import espn_api


async def main():
    if len(sys.argv) < 3:
        print('Usage: python debug_espn_roster.py <sport> "<team>"')
        return

    sport = sys.argv[1]
    team_query = sys.argv[2]

    print(f"Fetching {sport} scoreboard to find '{team_query}''s team id...")
    scoreboard = await espn_api.get_scoreboard(sport)
    event = espn_api.find_event_for_team(scoreboard, team_query)
    team_id = None
    if event:
        for c in event.get("competitions", [{}])[0].get("competitors", []):
            if team_query.lower() in c.get("team", {}).get("displayName", "").lower():
                team_id = c.get("team", {}).get("id")
    if team_id is None:

        print("Couldn't resolve team id from today's scoreboard, checking teams list...")
        teams = await espn_api.get_teams(sport)
        match = next((t for t in teams if team_query.lower() in t.get("displayName", "").lower()), None)
        if match is None:
            print(f"No team matching '{team_query}' found in the teams list either. Available teams:")
            for t in teams:
                print(f"  {t.get('displayName')} (id={t.get('id')})")
            return
        team_id = match.get("id")
        print(f"Found via teams list: {match.get('displayName')} (id={team_id})")

    print(f"Found team id {team_id}, fetching roster...")
    roster = await espn_api.get_team_roster(sport, team_id)

    with open("debug_espn_roster.json", "w", encoding="utf-8") as f:
        json.dump(roster, f, indent=2)
    print("Wrote full response to debug_espn_roster.json")

    print("\nTop-level keys:", list(roster.keys()))
    athletes = roster.get("athletes", [])
    print(f"'athletes' has {len(athletes)} top-level entries")
    if athletes:
        print("\nFirst entry's keys:", list(athletes[0].keys()))
        print("First entry (pretty-printed, truncated):")
        print(json.dumps(athletes[0], indent=2)[:2000])

    position_map = espn_api.build_roster_position_map(roster)
    print(f"\nParsed position_map has {len(position_map)} players")
    sample = list(position_map.items())[:10]
    print("Sample entries:", sample)
    print("\n'travis kelce' in map:", position_map.get("travis kelce", "NOT FOUND"))


if __name__ == "__main__":
    asyncio.run(main())
