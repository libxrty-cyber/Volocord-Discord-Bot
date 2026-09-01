

import asyncio
import cfbd_api
from formatters import TEAM_EMOJIS_CFB


async def main():
    print("Fetching all teams from CollegeFootballData...")
    teams = await cfbd_api.get_all_teams()

    fbs_schools = sorted(
        t.get("school", "") for t in teams
        if t.get("classification") == "fbs" and t.get("school")
    )
    fcs_schools = sorted(
        t.get("school", "") for t in teams
        if t.get("classification") == "fcs" and t.get("school")
    )

    print(f"\n{len(fbs_schools)} FBS schools, {len(fcs_schools)} FCS schools found via CFBD.\n")

    our_keys = set(TEAM_EMOJIS_CFB.keys())
    fbs_names = set(fbs_schools)
    fcs_names = set(fcs_schools)

    matched_fbs = our_keys & fbs_names
    matched_fcs = our_keys & fcs_names
    print(f"FBS matched correctly ({len(matched_fbs)} of {len(fbs_schools)})")
    print(f"FCS matched correctly ({len(matched_fcs)} of {len(fcs_schools)})\n")

    only_in_ours = our_keys - fbs_names - fcs_names
    if only_in_ours:
        print("!! In TEAM_EMOJIS_CFB but NOT found in CFBD's FBS or FCS school list")
        print("   (likely needs the key renamed to match CFBD's real name):")
        for name in sorted(only_in_ours):
            print(f"   - {name}")
        print()

    missing_fbs = sorted(fbs_names - our_keys)
    if missing_fbs:
        print(f"Missing FBS schools ({len(missing_fbs)}):")
        for name in missing_fbs:
            print(f"  - {name}")
        print()
    else:
        print("All FBS schools covered.\n")

    missing_fcs = sorted(fcs_names - our_keys)
    print(f"Missing FCS schools ({len(missing_fcs)} of {len(fcs_schools)}):")
    for name in missing_fcs:
        print(f"  - {name}")


if __name__ == "__main__":
    asyncio.run(main())
