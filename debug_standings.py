

import asyncio
import json

import mlb_stats_api


async def main():
    print("Fetching standings...")
    data = await mlb_stats_api.get_standings()

    with open("debug_standings.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Wrote full response to debug_standings.json")

    records = data.get("records", [])
    print(f"\n{len(records)} division-record(s) found.")
    if not records:
        print("Top-level keys:", list(data.keys()))
        return

    first = records[0]
    print("\nFirst division-record's top-level keys:", list(first.keys()))
    print("\nFull first division-record (pretty-printed):")
    print(json.dumps(first, indent=2)[:3000])

    team_records = first.get("teamRecords", [])
    if team_records:
        print("\nFirst team-record's top-level keys:", list(team_records[0].keys()))


if __name__ == "__main__":
    asyncio.run(main())
