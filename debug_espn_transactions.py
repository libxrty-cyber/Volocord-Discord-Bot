

import asyncio
import json
import sys

import espn_api


async def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_espn_transactions.py <sport> [team filter]")
        return

    sport = sys.argv[1]
    team_filter = sys.argv[2].lower() if len(sys.argv) > 2 else None

    print(f"Fetching {sport} transactions...")
    data = await espn_api.get_transactions(sport)

    with open("debug_espn_transactions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Wrote full response to debug_espn_transactions.json")

    print("\nTop-level keys:", list(data.keys()))


    transactions = data.get("transactions")
    if transactions is None:

        items = data.get("items") or []
        print(f"\nNo top-level 'transactions' key. 'items' has {len(items)} entries.")
        if items:
            print("First item keys:", list(items[0].keys()) if isinstance(items[0], dict) else type(items[0]))
            print(json.dumps(items[0], indent=2)[:1500])
        return

    print(f"\n'transactions' has {len(transactions)} entries")
    if not transactions:
        print("Empty list -- nothing more to inspect.")
        return

    print("\nFirst entry's keys:", list(transactions[0].keys()) if isinstance(transactions[0], dict) else type(transactions[0]))
    print("First entry (pretty-printed):")
    print(json.dumps(transactions[0], indent=2)[:2000])

    print(f"\n--- All {min(30, len(transactions))} entries' descriptions/dates (to see real wording patterns) ---")
    for t in transactions[:30]:
        if not isinstance(t, dict):
            continue
        date = t.get("date", "?")
        desc = t.get("description", t.get("text", "?"))
        team = t.get("team", {})
        team_name = team.get("displayName", team.get("name", "")) if isinstance(team, dict) else team
        print(f"[{date}] ({team_name}) {desc}")

    if team_filter:
        print(f"\n--- Entries matching '{team_filter}' (page 1 only) ---")
        matches = [
            t for t in transactions
            if isinstance(t, dict) and team_filter in json.dumps(t).lower()
        ]
        print(f"{len(matches)} matches found")
        for t in matches[:15]:
            print(json.dumps(t, indent=2))


    print("\n=== PAGINATION TEST ===")
    page1 = await espn_api.get_transactions(sport, page=1)
    page2 = await espn_api.get_transactions(sport, page=2)
    t1 = page1.get("transactions", [])
    t2 = page2.get("transactions", [])
    print(f"page 1: {len(t1)} entries, first date = {t1[0].get('date') if t1 else 'N/A'}")
    print(f"page 2: {len(t2)} entries, first date = {t2[0].get('date') if t2 else 'N/A'}")
    if t1 and t2 and t1[0].get("date") == t2[0].get("date") and t1[0].get("description") == t2[0].get("description"):
        print("!! page 1 and page 2 are IDENTICAL -- the 'page=' parameter is being ignored by ESPN.")
        print("   Pagination needs a different parameter name (or approach) entirely.")
    elif t1 and t2:
        print("Pages differ -- pagination via 'page=' appears to be working.")
    else:
        print("Couldn't compare -- one of the pages came back empty.")


    print("\n=== FULL AGGREGATION TEST (this may take a little while) ===")
    all_transactions = await espn_api.get_all_transactions(sport)
    print(f"Total transactions aggregated: {len(all_transactions)}")
    dates = sorted((t.get("date", "") for t in all_transactions if t.get("date")))
    if dates:
        print(f"Date range covered: {dates[0]} to {dates[-1]}")
    if team_filter:
        team_hits = [t for t in all_transactions if team_filter in json.dumps(t).lower()]
        print(f"\n'{team_filter}' appears in {len(team_hits)} aggregated entries (across all pages fetched):")
        for t in team_hits[:20]:
            print(f"  [{t.get('date')}] {t.get('description')}")


if __name__ == "__main__":
    asyncio.run(main())
