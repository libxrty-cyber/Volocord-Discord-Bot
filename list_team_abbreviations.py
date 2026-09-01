

import asyncio
import mlb_stats_api


async def main():
    teams = await mlb_stats_api.get_teams()
    teams.sort(key=lambda t: t["name"])
    print(f"{'Abbreviation':<14}Team")
    print("-" * 40)
    for t in teams:
        print(f"{t['abbreviation']:<14}{t['name']}")


if __name__ == "__main__":
    asyncio.run(main())
