

import asyncio
import json
import sys
from datetime import datetime

import mlb_stats_api


async def main():
    if len(sys.argv) < 2:
        print('Usage: python debug_mlb_player.py "<player name>"')
        return

    name_query = sys.argv[1]
    season = datetime.now().year

    print(f"Searching for '{name_query}'...")
    person_id = await mlb_stats_api.find_player_id(name_query)
    if person_id is None:
        print("No player found.")
        return
    print(f"Found person id {person_id}")

    print(f"Fetching {season} stats...")
    person = await mlb_stats_api.get_player_season_stats(person_id, season)

    with open("debug_mlb_player.json", "w", encoding="utf-8") as f:
        json.dump(person, f, indent=2)
    print("Wrote full response to debug_mlb_player.json")

    print("\nTop-level keys:", list(person.keys()))
    print("fullName:", person.get("fullName"))
    print("primaryPosition:", person.get("primaryPosition"))
    print("currentTeam:", person.get("currentTeam"))

    stats_groups = person.get("stats", [])
    print(f"\n{len(stats_groups)} stat group(s):")
    for g in stats_groups:
        group_name = g.get("group", {}).get("displayName")
        splits = g.get("splits", [])
        print(f"  group={group_name!r}, {len(splits)} split(s)")
        if splits:
            print(f"    sample stat block: {json.dumps(splits[0].get('stat'), indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
