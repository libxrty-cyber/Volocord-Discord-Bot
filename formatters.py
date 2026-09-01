

from datetime import datetime, date
from zoneinfo import ZoneInfo


TEAM_EMOJIS = {
    "ARI": "<:ARImlb:1271258908006027377>",
    "AZ":  "<:ARImlb:1271258908006027377>",
    "ATH": "<:ATHmlb:1271259309275348992>",
    "ATL": "<:ATLmlb:1271258925890666589>",
    "BAL": "<:BALmlb:1271553036187340802>",
    "BOS": "<:BOSmlb:1271258983377932310>",
    "CHC": "<:CHCmlb:1273654468541681788>",
    "CIN": "<:CINmlb:1271259048309948477>",
    "CLE": "<:CLEmlb:1271259070833102858>",
    "COL": "<:COLmlb:1394901930215477308>",
    "CWS": "<:CWSmlb:1271259013950079050>",
    "DET": "<:DETmlb:1271259102852681809>",
    "HOU": "<:HOUmlb:1271259122377031783>",
    "KC":  "<:KCRmlb:1271259161241583636>",
    "LAA": "<:LAAmlb:1271259183647428741>",
    "LAD": "<:LADmlb:1271259202311950336>",
    "MIA": "<:MIAmlb:1271259217889722491>",
    "MIL": "<:MILmlb:1271259238630424608>",
    "MIN": "<:MINmlb:1288592465200283698>",
    "NYM": "<:NYMmlb:1271259274978398270>",
    "NYY": "<:NYYmlb:1271259291873181736>",
    "PHI": "<:PHImlb:1271259331681320997>",
    "PIT": "<:PITmlb:1271259345765797970>",
    "SD":  "<:SDPmlb:1271259372135125084>",
    "SEA": "<:SEAmlb:1427084871268044891>",
    "SF":  "<:SFGmlb:1271259389948465183>",
    "STL": "<:STLmlb:1271259446177431603>",
    "TB":  "<:TBRmlb:1271259486757064789>",
    "TEX": "<:TEXmlb:1271259514586533948>",
    "TOR": "<:TORmlb:1271259531527196703>",
    "WSH": "<:WSHmlb:1271259545964118060>",
}

LEAGUE_LOGO = "<:MLB:1271355719190450308>"


def _to_eastern(iso_date: str) -> datetime | None:

    if not iso_date:
        return None
    try:
        cleaned = iso_date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("America/New_York"))
    except (ValueError, TypeError):
        return None


def _fmt_header_datetime(iso_date: str) -> str:

    dt = _to_eastern(iso_date)
    if not dt:
        return ""
    date_part = dt.strftime("%Y/%m/%d")
    time_part = dt.strftime("%I:%M %p").lstrip("0")
    return f"{date_part} - {time_part} ET"


def _fmt_header_date(iso_date: str) -> str:

    dt = _to_eastern(iso_date)
    return dt.strftime("%Y/%m/%d") if dt else ""


def team_emoji(abbr: str) -> str:
    return TEAM_EMOJIS.get(abbr, f":{abbr.lower()}:" if abbr else "")


def _shorten_name(full_name: str) -> str:

    parts = full_name.split()
    if len(parts) < 2:
        return full_name
    return f"{parts[0][0]}. {' '.join(parts[1:])}"


def _fmt_batting_line(name: str, stats: dict) -> str:

    h = stats.get("hits", 0)
    ab = stats.get("atBats", 0)
    r = stats.get("runs", 0)
    rbi = stats.get("rbi", 0)
    hr = stats.get("homeRuns", 0)
    line = f"{name}: {h}-{ab} - {r} R - {rbi} RBI"
    if hr:
        line += f" - {hr} HR"
    return line


def _fmt_pitching_line(name: str, stats: dict) -> str:
    ip = stats.get("inningsPitched", "0.0")
    h = stats.get("hits", 0)
    er = stats.get("earnedRuns", 0)
    bb = stats.get("baseOnBalls", 0)
    so = stats.get("strikeOuts", 0)
    hr = stats.get("homeRuns", 0)
    line = f"{name}: {ip} IP - {h} H - {er} ER - {bb} BB - {so} K"
    if hr:
        line += f" - {hr} HR"
    return line


def _hitters_with_a_hit(team_box: dict, team_abbr: str) -> list[str]:

    lines = []
    for pdata in team_box.get("players", {}).values():
        batting = pdata.get("stats", {}).get("batting", {})
        hits = batting.get("hits", 0)
        if not hits:
            continue
        person = pdata.get("person", {})
        name = _shorten_name(person.get("fullName", "Unknown"))
        position = (pdata.get("position") or {}).get("abbreviation", "")
        tag = f"({position}) " if position else ""
        lines.append(f"{team_emoji(team_abbr)} **{tag}{_fmt_batting_line(name, batting)}**")
    return lines


def _innings_pitched_value(ip_str) -> float:

    try:
        whole_str, _, frac_str = str(ip_str).partition(".")
        whole = int(whole_str)
        frac = int(frac_str) if frac_str else 0
    except (ValueError, TypeError):
        return 0.0
    return whole + frac / 3.0


def _leading_pitcher_data(team_box: dict) -> tuple[dict, bool] | tuple[None, bool]:

    pitcher_ids = team_box.get("pitchers", [])
    if not pitcher_ids:
        return None, False
    players = team_box.get("players", {})
    best_pdata, best_ip, best_pid = None, -1.0, None
    for pid in pitcher_ids:
        pdata = players.get(f"ID{pid}")
        if not pdata:
            continue
        pitching = pdata.get("stats", {}).get("pitching", {})
        ip_val = _innings_pitched_value(pitching.get("inningsPitched", "0.0"))
        if ip_val > best_ip:
            best_ip = ip_val
            best_pdata = pdata
            best_pid = pid
    if best_pdata is None:
        return None, False
    return best_pdata, (best_pid == pitcher_ids[0])


def _starting_pitcher_line(team_box: dict, team_abbr: str) -> str | None:

    pdata, is_starter = _leading_pitcher_data(team_box)
    if not pdata:
        return None
    pitching = pdata.get("stats", {}).get("pitching", {})
    person = pdata.get("person", {})
    name = _shorten_name(person.get("fullName", "Unknown"))
    tag = "(SP)" if is_starter else "(RP)"
    return f"{team_emoji(team_abbr)} **{tag} {_fmt_pitching_line(name, pitching)}**"


def _mlb_inning_label(schedule_game: dict) -> str:

    linescore = schedule_game.get("linescore", {})
    inning_state = linescore.get("inningState", "")
    inning_ordinal = linescore.get("currentInningOrdinal", "")
    if not inning_state or not inning_ordinal:
        return ""
    short_state = {"top": "TOP", "bottom": "BOT"}.get(inning_state.lower(), inning_state.upper())
    return f"{short_state} {inning_ordinal.upper()}"


def format_mlb_player_stats(person: dict, season: int) -> str:

    name = person.get("fullName", "Unknown")
    pos = person.get("primaryPosition", {}).get("abbreviation", "")
    abbr = person.get("teamAbbr", "")
    emoji = team_emoji(abbr)
    pos_part = f"({pos}) " if pos else ""
    header = f"{pos_part}**{name}** {emoji}".strip()

    lines = [header, "", f"__{season} Stats__"]

    stats_groups = person.get("stats", [])
    hitting = next((g for g in stats_groups if g.get("group", {}).get("displayName", "").lower() == "hitting"), None)
    pitching = next((g for g in stats_groups if g.get("group", {}).get("displayName", "").lower() == "pitching"), None)

    hitting_splits = hitting.get("splits", []) if hitting else []
    pitching_splits = pitching.get("splits", []) if pitching else []

    if hitting_splits:
        s = hitting_splits[0].get("stat", {})
        avg = s.get("avg", "-")
        obp = s.get("obp", "-")
        slg = s.get("slg", "-")
        ops = s.get("ops", "-")
        hr = s.get("homeRuns", "0")
        rbi = s.get("rbi", "0")
        sb = s.get("stolenBases", "0")
        lines.append(f"{avg} AVG - {obp} OBP - {slg} SLG - {ops} OPS - {hr} HR - {rbi} RBI - {sb} SB")
    elif pitching_splits:
        s = pitching_splits[0].get("stat", {})
        era = s.get("era", "-")
        whip = s.get("whip", "-")
        wins = s.get("wins", "0")
        losses = s.get("losses", "0")
        so = s.get("strikeOuts", "0")
        sv = s.get("saves", "0")
        lines.append(f"{era} ERA - {whip} WHIP - {wins}-{losses} - {so} K - {sv} SV")
    else:
        lines.append(f"_No {season} stats available for this player yet._")

    return "\n".join(lines)


def format_transactions(category_label: str, team_query: str, results: list[dict], team_emoji_fn=None) -> str:

    if not results:
        scope = f"for **{team_query.title()}**" if team_query else "league-wide"
        return f"No {category_label} found {scope} this season so far."

    team_title = team_query.title()
    possessive = f"{team_title}'" if team_title.endswith("s") else f"{team_title}'s"
    scope = possessive if team_query else "League-wide"
    season_year = datetime.now().year
    lines = [f"**{scope} {category_label} -- {season_year} season**", ""]

    for r in results:
        team = r.get("team", {})
        abbr = team.get("abbreviation", "")
        name = team.get("displayName", team.get("name", ""))
        emoji = team_emoji_fn(abbr) if team_emoji_fn else ""
        date_display = _fmt_header_date(r.get("date", ""))
        prefix = f"{emoji} " if emoji else ""
        team_part = f"**{name}**: " if not team_query else ""
        lines.append(f"{prefix}{date_display} -- {team_part}{r['clause']}")

    return "\n".join(lines)


def format_mlb_standings(standings_data: dict, team_abbr_map: dict[int, str] | None = None) -> str:

    records = standings_data.get("records", [])
    if not records:
        return "Couldn't find standings data."

    team_abbr_map = team_abbr_map or {}

    league_names = {103: "American League", 104: "National League"}
    division_names = {
        200: "American League West",
        201: "American League East",
        202: "American League Central",
        203: "National League West",
        204: "National League East",
        205: "National League Central",
    }


    leagues: dict[str, list[tuple[str, dict]]] = {}
    for division_record in records:
        league_id = division_record.get("league", {}).get("id")
        division_id = division_record.get("division", {}).get("id")
        league_name = league_names.get(league_id, "Unknown League")
        division_name = division_names.get(division_id, "Unknown Division")
        leagues.setdefault(league_name, []).append((division_name, division_record))

    lines = [f"**MLB STANDINGS** {LEAGUE_LOGO}", ""]

    for league_name in sorted(leagues.keys()):
        lines.append(f"**{league_name}**")
        for division_name, division_record in leagues[league_name]:


            short_division = division_name.replace(league_name, "").strip() or division_name
            lines.append(f"**{short_division}**")

            team_records = sorted(
                division_record.get("teamRecords", []),
                key=lambda t: _safe_int(t.get("divisionRank", "99")),
            )
            for t in team_records:
                team = t.get("team", {})
                abbr = team.get("abbreviation") or team_abbr_map.get(team.get("id"), "")
                name = team.get("name", "")
                wins = t.get("wins", "?")
                losses = t.get("losses", "?")
                gb = t.get("gamesBack", "-")


                is_leader = t.get("divisionLeader") in (True, "true", "True")
                line = f"{team_emoji(abbr)} {name}: {wins}-{losses}, GB: {gb}"
                lines.append(f"**{line}**" if is_leader else line)
            lines.append("")

    return "\n".join(lines).rstrip()


def format_mlb_probable_pitchers(schedule_game: dict, boxscore: dict) -> str:

    teams = schedule_game.get("teams", {})
    away_game = teams.get("away", {})
    home_game = teams.get("home", {})

    box_teams = boxscore.get("teams", {})
    away_abbr = box_teams.get("away", {}).get("team", {}).get("abbreviation", "")
    home_abbr = box_teams.get("home", {}).get("team", {}).get("abbreviation", "")

    lines = [
        f"**PROBABLE PITCHERS - MLB - {_fmt_header_datetime(schedule_game.get('gameDate', ''))}** {LEAGUE_LOGO}",
        "",
    ]

    for game_side, abbr in ((away_game, away_abbr), (home_game, home_abbr)):
        name = game_side.get("team", {}).get("name", "")
        pitcher = game_side.get("probablePitcher")
        pitcher_name = pitcher.get("fullName", "TBD") if pitcher else "Not yet announced"
        lines.append(f"{team_emoji(abbr)} **{name}**: {pitcher_name}")

    return "\n".join(lines)


def format_mlb_lineup(schedule_game: dict, boxscore: dict) -> str:

    teams = schedule_game.get("teams", {})
    away_game = teams.get("away", {})
    home_game = teams.get("home", {})

    box_teams = boxscore.get("teams", {})
    away_box = box_teams.get("away", {})
    home_box = box_teams.get("home", {})
    away_abbr = away_box.get("team", {}).get("abbreviation", "")
    home_abbr = home_box.get("team", {}).get("abbreviation", "")
    away_name = away_game.get("team", {}).get("name", "")
    home_name = home_game.get("team", {}).get("name", "")

    lines = [
        f"**STARTING LINEUPS - MLB - {_fmt_header_datetime(schedule_game.get('gameDate', ''))}** {LEAGUE_LOGO}",
        "",
    ]

    for name, abbr, team_box in ((away_name, away_abbr, away_box), (home_name, home_abbr, home_box)):
        lines.append(f"{team_emoji(abbr)} **{name}**")
        order_ids = team_box.get("battingOrder", [])
        players = team_box.get("players", {})
        if not order_ids:
            lines.append("_Lineup not posted yet -- check back closer to first pitch._")
        else:
            for i, pid in enumerate(order_ids[:9], start=1):
                pdata = players.get(f"ID{pid}")
                if not pdata:
                    continue
                person = pdata.get("person", {})
                pname = person.get("fullName", "Unknown")
                pos = (pdata.get("position") or {}).get("abbreviation", "")
                pos_part = f"({pos}) " if pos else ""
                lines.append(f"{i}. {pos_part}{pname}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _newscast_batter_line(pdata: dict, emoji: str) -> str | None:

    batting = pdata.get("stats", {}).get("batting", {})
    h = batting.get("hits", 0)
    rbi = batting.get("rbi", 0)
    hr = batting.get("homeRuns", 0)

    qualifies = (
        h >= 4
        or (h >= 3 and rbi >= 1)
        or (h >= 2 and rbi >= 2)
        or rbi >= 3
        or hr >= 1
    )
    if not qualifies:
        return None

    person = pdata.get("person", {})
    name = person.get("fullName", "Unknown")
    pos = (pdata.get("position") or {}).get("abbreviation", "")
    ab = batting.get("atBats", 0)
    stat_line = f"{h}/{ab} - {rbi} RBI"
    if hr:


        season_hr = pdata.get("seasonStats", {}).get("batting", {}).get("homeRuns")
        season_part = f" ({season_hr})" if season_hr is not None else ""
        stat_line += f" - {hr} HR{season_part}"
    pos_part = f"({pos}) " if pos else ""
    return f"{emoji} **{pos_part}{name}: {stat_line}**"


def _newscast_pitcher_line(pdata: dict, emoji: str, is_starter: bool = True) -> str | None:

    pitching = pdata.get("stats", {}).get("pitching", {})
    if not pitching:
        return None
    person = pdata.get("person", {})
    name = person.get("fullName", "Unknown")
    ip = pitching.get("inningsPitched", "0.0")
    h = pitching.get("hits", 0)
    er = pitching.get("earnedRuns", 0)
    hr = pitching.get("homeRuns", 0)
    bb = pitching.get("baseOnBalls", 0)
    k = pitching.get("strikeOuts", 0)
    parts = [f"{ip} IP", f"{h} H", f"{er} ER"]
    if hr:
        parts.append(f"{hr} HR")
    parts.append(f"{bb} BB")
    parts.append(f"{k} K")
    tag = "SP" if is_starter else "RP"
    return f"{emoji} **({tag}) {name}: {' - '.join(parts)}**"


def format_mlb_newscast(schedule_game: dict, boxscore: dict) -> str:

    teams = schedule_game.get("teams", {})
    away_game = teams.get("away", {})
    home_game = teams.get("home", {})

    status = schedule_game.get("status", {})
    abstract_state = status.get("abstractGameState", "")
    detailed_state = status.get("detailedState", "")
    is_postponed = "postponed" in detailed_state.lower()

    if is_postponed:
        status_label = "POSTPONED"
    elif abstract_state == "Final":
        status_label = "FINAL SCORE"
    elif abstract_state == "Live":
        status_label = _mlb_inning_label(schedule_game) or detailed_state.upper() or "IN PROGRESS"
    else:
        status_label = "SCHEDULED"

    lines = [f"**{status_label} - MLB - {_fmt_header_datetime(schedule_game.get('gameDate', ''))}** {LEAGUE_LOGO}", ""]

    box_teams = boxscore.get("teams", {})
    away_box = box_teams.get("away", {})
    home_box = box_teams.get("home", {})
    away_abbr = away_box.get("team", {}).get("abbreviation", "")
    home_abbr = home_box.get("team", {}).get("abbreviation", "")

    away_score = _safe_int(away_game.get("score", "-1")) if abstract_state != "Preview" else -1
    home_score = _safe_int(home_game.get("score", "-1")) if abstract_state != "Preview" else -1
    away_won = abstract_state == "Final" and not is_postponed and away_score > home_score
    home_won = abstract_state == "Final" and not is_postponed and home_score > away_score

    for game_side, abbr, won in ((away_game, away_abbr, away_won), (home_game, home_abbr, home_won)):
        name = game_side.get("team", {}).get("name", "")
        record = game_side.get("leagueRecord", {})
        rec_str = f"{record.get('wins', '?')}-{record.get('losses', '?')}" if record else ""
        rec_part = f"**({rec_str})** " if rec_str else ""
        if abstract_state == "Preview" or is_postponed:
            lines.append(f"{rec_part}{name} {team_emoji(abbr)}")
        else:
            score = game_side.get("score", "?")
            score_part = f"**{score}**" if won else str(score)
            lines.append(f"{rec_part}{name} {team_emoji(abbr)} - {score_part}")

    lines.append("—" * 15)
    lines.append("")

    if is_postponed:
        lines.append("_This game was postponed._")
    elif abstract_state == "Preview":
        formatted = _fmt_header_datetime(schedule_game.get("gameDate", ""))
        lines.append(f"First pitch: {formatted}" if formatted else "_Game hasn't started yet -- check back after first pitch._")
    else:
        stat_lines = []
        for abbr, team_box in ((away_abbr, away_box), (home_abbr, home_box)):
            emoji = team_emoji(abbr)
            for pdata in team_box.get("players", {}).values():
                batter_line = _newscast_batter_line(pdata, emoji)
                if batter_line:
                    stat_lines.append(batter_line)
            leading_pdata, is_starter = _leading_pitcher_data(team_box)
            if leading_pdata:
                pitcher_line = _newscast_pitcher_line(leading_pdata, emoji, is_starter)
                if pitcher_line:
                    stat_lines.append(pitcher_line)
        if stat_lines:
            lines.extend(stat_lines)
        else:
            lines.append("_No qualifying players for this game._")

    return "\n".join(lines)


def format_mlb_final(schedule_game: dict, boxscore: dict) -> str:

    teams = schedule_game.get("teams", {})
    away_game = teams.get("away", {})
    home_game = teams.get("home", {})

    status = schedule_game.get("status", {})
    abstract_state = status.get("abstractGameState", "")
    detailed_state = status.get("detailedState", "")


    is_postponed = "postponed" in detailed_state.lower()

    if is_postponed:
        status_label = "POSTPONED"
    elif abstract_state == "Final":
        status_label = "FINAL SCORE"
    elif abstract_state == "Live":
        status_label = _mlb_inning_label(schedule_game) or detailed_state.upper() or "IN PROGRESS"
    else:
        status_label = "SCHEDULED"

    lines = [f"**{status_label} - MLB - {_fmt_header_datetime(schedule_game.get('gameDate', ''))}** {LEAGUE_LOGO}", ""]

    box_teams = boxscore.get("teams", {})
    away_box = box_teams.get("away", {})
    home_box = box_teams.get("home", {})
    away_abbr = away_box.get("team", {}).get("abbreviation", "")
    home_abbr = home_box.get("team", {}).get("abbreviation", "")

    away_score = _safe_int(away_game.get("score", "-1")) if abstract_state != "Preview" else -1
    home_score = _safe_int(home_game.get("score", "-1")) if abstract_state != "Preview" else -1
    away_won = abstract_state == "Final" and not is_postponed and away_score > home_score
    home_won = abstract_state == "Final" and not is_postponed and home_score > away_score

    for game_side, abbr, won in ((away_game, away_abbr, away_won), (home_game, home_abbr, home_won)):
        name = game_side.get("team", {}).get("name", "")
        record = game_side.get("leagueRecord", {})
        rec_str = f"{record.get('wins', '?')}-{record.get('losses', '?')}" if record else ""
        rec_part = f"({rec_str}) " if rec_str else ""
        if abstract_state == "Preview" or is_postponed:
            lines.append(f"{rec_part}{name} {team_emoji(abbr)}")
        else:
            score = game_side.get("score", "?")
            line = f"{rec_part}{name} {team_emoji(abbr)} - {score}"
            lines.append(f"**{line}**" if won else line)

    if is_postponed:
        lines.append("")
        lines.append("_This game was postponed._")
    elif abstract_state == "Preview":
        game_date = schedule_game.get("gameDate", "")
        formatted = _fmt_header_datetime(game_date)
        lines.append("")
        if formatted:
            lines.append(f"First pitch: {formatted}")
        else:
            lines.append("_Game hasn't started yet -- check back after first pitch._")

    return "\n".join(lines)


def _hitters_with_run_or_rbi(team_box: dict, team_abbr: str) -> list[str]:

    lines = []
    for pdata in team_box.get("players", {}).values():
        batting = pdata.get("stats", {}).get("batting", {})
        runs = batting.get("runs", 0)
        rbi = batting.get("rbi", 0)
        if not runs and not rbi:
            continue
        person = pdata.get("person", {})
        name = _shorten_name(person.get("fullName", "Unknown"))
        position = (pdata.get("position") or {}).get("abbreviation", "")
        tag = f"({position}) " if position else ""
        lines.append(f"{team_emoji(team_abbr)} **{tag}{_fmt_batting_line(name, batting)}**")
    return lines


def format_mlb_boxscore(schedule_game: dict, boxscore: dict) -> str:

    teams = schedule_game.get("teams", {})
    away_game = teams.get("away", {})
    home_game = teams.get("home", {})

    status = schedule_game.get("status", {})
    abstract_state = status.get("abstractGameState", "")
    detailed_state = status.get("detailedState", "")
    is_postponed = "postponed" in detailed_state.lower()

    if is_postponed:
        status_label = "POSTPONED"
    elif abstract_state == "Final":
        status_label = "FINAL SCORE"
    elif abstract_state == "Live":
        status_label = _mlb_inning_label(schedule_game) or detailed_state.upper() or "IN PROGRESS"
    else:
        status_label = "SCHEDULED"

    lines = [f"**{status_label} - MLB - {_fmt_header_datetime(schedule_game.get('gameDate', ''))}** {LEAGUE_LOGO}", ""]

    box_teams = boxscore.get("teams", {})
    away_box = box_teams.get("away", {})
    home_box = box_teams.get("home", {})
    away_abbr = away_box.get("team", {}).get("abbreviation", "")
    home_abbr = home_box.get("team", {}).get("abbreviation", "")

    away_score = _safe_int(away_game.get("score", "-1")) if abstract_state != "Preview" else -1
    home_score = _safe_int(home_game.get("score", "-1")) if abstract_state != "Preview" else -1
    away_won = abstract_state == "Final" and not is_postponed and away_score > home_score
    home_won = abstract_state == "Final" and not is_postponed and home_score > away_score

    for game_side, abbr, won in ((away_game, away_abbr, away_won), (home_game, home_abbr, home_won)):
        name = game_side.get("team", {}).get("name", "")
        record = game_side.get("leagueRecord", {})
        rec_str = f"{record.get('wins', '?')}-{record.get('losses', '?')}" if record else ""
        rec_part = f"({rec_str}) " if rec_str else ""
        if abstract_state == "Preview" or is_postponed:
            lines.append(f"{rec_part}{name} {team_emoji(abbr)}")
        else:
            score = game_side.get("score", "?")
            line = f"{rec_part}{name} {team_emoji(abbr)} - {score}"
            lines.append(f"**{line}**" if won else line)

    lines.append("—" * 15)
    lines.append("")

    if is_postponed:
        lines.append("_This game was postponed._")
    elif abstract_state == "Preview":
        game_date = schedule_game.get("gameDate", "")
        formatted = _fmt_header_datetime(game_date)
        if formatted:
            lines.append(f"First pitch: {formatted}")
        else:
            lines.append("_Game hasn't started yet -- check back after first pitch._")
    else:
        stat_lines = []
        for team_box, abbr in ((away_box, away_abbr), (home_box, home_abbr)):
            stat_lines.extend(_hitters_with_run_or_rbi(team_box, abbr))
            sp_line = _starting_pitcher_line(team_box, abbr)
            if sp_line:
                stat_lines.append(sp_line)
        if stat_lines:
            lines.extend(stat_lines)
        else:
            lines.append("_No box score data available for this game yet._")

    return "\n".join(lines)


TEAM_EMOJIS_NBA = {
    "ATL": "<:ATLnba:1271131227340144703>",
    "BOS": "<:BOSnba:1271131306729672706>",
    "BKN": "<:BKNnba:1430672757657698384>",
    "CHA": "<:CHAnba:1271131382151643297>",
    "CHI": "<:CHInba:1271131407661531156>",
    "CLE": "<:CLEnba:1271131394667581470>",
    "DAL": "<:DALnba:1271131426170863698>",
    "DEN": "<:DENnba:1271131438045204614>",
    "DET": "<:DETnba:1271131469196165223>",
    "GSW": "<:GSWnba:1271131500343197859>",
    "HOU": "<:HOUnba:1512099398614519828>",
    "IND": "<:INDnba:1271131542701477932>",
    "LAC": "<:LACnba:1271131556332961875>",
    "LAL": "<:LALnba:1271131567481290906>",
    "MEM": "<:MEMnba:1271131584699043892>",
    "MIA": "<:MIAnba:1271131595570413569>",
    "MIL": "<:MILnba:1431853665366311042>",
    "MIN": "<:MINnba:1513563019911893133>",
    "NOP": "<:NOPnba:1271131677883764757>",
    "NYK": "<:NYKnba:1271131704136040571>",
    "OKC": "<:OKCnba:1271131725107433603>",
    "ORL": "<:ORLnba:1379525742014107778>",
    "PHI": "<:PHInba:1271131759039348860>",
    "PHX": "<:PHXnba:1271131781260644374>",
    "POR": "<:PORnba:1271131794569429015>",
    "SAC": "<:SACnba:1271131810369372215>",
    "SAS": "<:SASnba:1271131835165835325>",
    "TOR": "<:TORnba:1271131855101362236>",
    "UTA": "<:UTAnba:1430672755241783348>",
    "WAS": "<:WSHnba:1271131881449984082>",
}

LEAGUE_LOGO_NBA = "<:NBA:1271292665983401994>"


def _nba_team_emoji(abbr: str) -> str:
    return TEAM_EMOJIS_NBA.get(abbr, f":{abbr.lower()}:" if abbr else "")


def _nba_rows(data: dict, name: str) -> list[dict]:

    for rs in data.get("resultSets", []):
        if rs.get("name") == name:
            headers = rs.get("headers", [])
            return [dict(zip(headers, row)) for row in rs.get("rowSet", [])]
    return []


def _nba_header_date(game_date_est: str) -> str:

    if not game_date_est:
        return ""
    try:
        return datetime.fromisoformat(game_date_est).strftime("%Y/%m/%d")
    except (ValueError, TypeError):
        return ""


def _nba_status_text(header_row: dict) -> str:

    status_id = header_row.get("GAME_STATUS_ID")
    if status_id == 3:
        return "FINAL"
    if status_id == 2:
        return str(header_row.get("GAME_STATUS_TEXT", "")).upper() or "IN PROGRESS"
    return "SCHEDULED"


def _nba_pts_display(row: dict) -> str:

    pts = row.get("PTS")
    return str(pts) if pts is not None else "?"


def _nba_header_and_score(scoreboard_data: dict, game_id: str, boxscore_data: dict | None = None) -> tuple[list[str], dict, dict, bool, dict]:

    game_headers = _nba_rows(scoreboard_data, "GameHeader")
    header_row = next((r for r in game_headers if r.get("GAME_ID") == game_id), {})
    status_text = _nba_status_text(header_row)

    line_score_rows = [r for r in _nba_rows(scoreboard_data, "LineScore") if r.get("GAME_ID") == game_id]
    home_team_id = header_row.get("HOME_TEAM_ID")
    away_row = next((r for r in line_score_rows if r.get("TEAM_ID") != home_team_id), {})
    home_row = next((r for r in line_score_rows if r.get("TEAM_ID") == home_team_id), {})

    box_inner = (boxscore_data or {}).get("boxScoreTraditional", {})


    if status_text != "FINAL" and box_inner.get("awayTeam", {}).get("players") and box_inner.get("homeTeam", {}).get("players"):
        status_text = "FINAL"

    def _row_or_box_fallback(ls_row: dict, side_key: str) -> dict:
        if ls_row and ls_row.get("PTS") is not None:
            return ls_row
        team_block = box_inner.get(side_key, {})
        if not team_block:
            return ls_row or {}
        stats = team_block.get("statistics", {})
        return {
            "TEAM_ABBREVIATION": team_block.get("teamTricode", ""),
            "TEAM_CITY_NAME": team_block.get("teamCity", ""),
            "TEAM_NAME": team_block.get("teamName", ""),
            "TEAM_WINS_LOSSES": "",
            "PTS": stats.get("points", "?"),
        }

    away_row = _row_or_box_fallback(away_row, "awayTeam")
    home_row = _row_or_box_fallback(home_row, "homeTeam")

    away_pts = away_row.get("PTS")
    home_pts = home_row.get("PTS")
    away_won = status_text == "FINAL" and isinstance(away_pts, (int, float)) and isinstance(home_pts, (int, float)) and away_pts > home_pts
    home_won = status_text == "FINAL" and isinstance(away_pts, (int, float)) and isinstance(home_pts, (int, float)) and home_pts > away_pts

    lines = [f"**{status_text} - NBA - {_nba_header_date(header_row.get('GAME_DATE_EST', ''))}** {LEAGUE_LOGO_NBA}", ""]

    for row, won in ((away_row, away_won), (home_row, home_won)):
        abbr = row.get("TEAM_ABBREVIATION", "")
        name = f"{row.get('TEAM_CITY_NAME', '')} {row.get('TEAM_NAME', '')}".strip()
        record = row.get("TEAM_WINS_LOSSES", "")
        rec_part = f"({record}) " if record else ""
        if status_text == "SCHEDULED":
            lines.append(f"{rec_part}{name} {_nba_team_emoji(abbr)}")
        else:
            pts = _nba_pts_display(row)
            line = f"{rec_part}{name} {_nba_team_emoji(abbr)} - {pts}"
            lines.append(f"**{line}**" if won else line)

    return lines, away_row, home_row, status_text == "FINAL", header_row


def format_nba_final(scoreboard_data: dict, boxscore_data: dict, game_id: str) -> str:

    lines, _, _, is_final, header_row = _nba_header_and_score(scoreboard_data, game_id, boxscore_data)
    if not is_final and header_row.get("GAME_STATUS_ID") == 1:
        tipoff = str(header_row.get("GAME_STATUS_TEXT", "")).strip()
        lines.append("")
        lines.append(f"Tip-off: {tipoff}" if tipoff else "_Game hasn't started yet._")
    return "\n".join(lines)


def format_nba_newscast(scoreboard_data: dict, boxscore_data: dict, game_id: str) -> str:

    game_headers = _nba_rows(scoreboard_data, "GameHeader")
    header_row = next((r for r in game_headers if r.get("GAME_ID") == game_id), {})
    status_text = _nba_status_text(header_row)

    line_score_rows = [r for r in _nba_rows(scoreboard_data, "LineScore") if r.get("GAME_ID") == game_id]
    home_team_id = header_row.get("HOME_TEAM_ID")
    away_row = next((r for r in line_score_rows if r.get("TEAM_ID") != home_team_id), {})
    home_row = next((r for r in line_score_rows if r.get("TEAM_ID") == home_team_id), {})

    box_inner = (boxscore_data or {}).get("boxScoreTraditional", {})


    if status_text != "FINAL" and box_inner.get("awayTeam", {}).get("players") and box_inner.get("homeTeam", {}).get("players"):
        status_text = "FINAL"

    def _row_or_box_fallback(ls_row: dict, side_key: str) -> dict:
        if ls_row and ls_row.get("PTS") is not None:
            return ls_row
        team_block = box_inner.get(side_key, {})
        if not team_block:
            return ls_row or {}
        stats = team_block.get("statistics", {})
        return {
            "TEAM_ABBREVIATION": team_block.get("teamTricode", ""),
            "TEAM_CITY_NAME": team_block.get("teamCity", ""),
            "TEAM_NAME": team_block.get("teamName", ""),
            "TEAM_WINS_LOSSES": "",
            "PTS": stats.get("points", "?"),
        }

    away_row = _row_or_box_fallback(away_row, "awayTeam")
    home_row = _row_or_box_fallback(home_row, "homeTeam")

    away_pts = away_row.get("PTS")
    home_pts = home_row.get("PTS")
    away_won = status_text == "FINAL" and isinstance(away_pts, (int, float)) and isinstance(home_pts, (int, float)) and away_pts > home_pts
    home_won = status_text == "FINAL" and isinstance(away_pts, (int, float)) and isinstance(home_pts, (int, float)) and home_pts > away_pts

    lines = [f"**{status_text} - NBA - {_nba_header_date(header_row.get('GAME_DATE_EST', ''))}** {LEAGUE_LOGO_NBA}", ""]

    for row, won in ((away_row, away_won), (home_row, home_won)):
        abbr = row.get("TEAM_ABBREVIATION", "")
        name = f"{row.get('TEAM_CITY_NAME', '')} {row.get('TEAM_NAME', '')}".strip()
        record = row.get("TEAM_WINS_LOSSES", "")
        rec_part = f"**({record})** " if record else ""
        if status_text == "SCHEDULED":
            lines.append(f"{rec_part}{name} {_nba_team_emoji(abbr)}")
        else:
            pts = _nba_pts_display(row)
            pts_part = f"**{pts}**" if won else pts
            lines.append(f"{rec_part}{name} {_nba_team_emoji(abbr)} - {pts_part}")

    lines.append("—" * 15)
    lines.append("")

    if status_text == "SCHEDULED":
        tipoff = str(header_row.get("GAME_STATUS_TEXT", "")).strip()
        lines.append(f"Tip-off: {tipoff}" if tipoff else "_Game hasn't started yet._")
        return "\n".join(lines)

    if status_text != "FINAL" or not boxscore_data:
        lines.append("_No box score data available for this game yet._")
        return "\n".join(lines)

    box_inner = boxscore_data.get("boxScoreTraditional", {})
    stat_lines = []
    for team_block in (box_inner.get("awayTeam", {}), box_inner.get("homeTeam", {})):
        tricode = team_block.get("teamTricode", "")
        emoji = _nba_team_emoji(tricode)
        for p in team_block.get("players", []):
            stats = p.get("statistics", {})
            pts = stats.get("points") or 0
            reb = stats.get("reboundsTotal") or 0
            ast = stats.get("assists") or 0
            stl = stats.get("steals") or 0
            blk = stats.get("blocks") or 0
            qualifies = pts >= 15 or reb >= 10 or ast >= 10 or stl >= 5 or blk >= 4
            if not qualifies:
                continue
            name = p.get("nameI") or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip() or "Unknown"
            pos = p.get("position", "")
            pos_part = f"({pos}) " if pos else ""
            stat_parts = []
            if pts:
                stat_parts.append(f"{pts} PTS")
            if reb:
                stat_parts.append(f"{reb} REB")
            if ast:
                stat_parts.append(f"{ast} AST")
            if stl:
                stat_parts.append(f"{stl} STL")
            if blk:
                stat_parts.append(f"{blk} BLK")
            stat_lines.append(f"{emoji} **{pos_part}{name}: {' - '.join(stat_parts)}**")

    lines.extend(stat_lines if stat_lines else ["_No box score data available for this game yet._"])
    return "\n".join(lines)


def format_nba_boxscore(scoreboard_data: dict, boxscore_data: dict, game_id: str) -> str:

    lines, away_row, home_row, is_final, header_row = _nba_header_and_score(scoreboard_data, game_id, boxscore_data)
    lines.append("—" * 15)
    lines.append("")

    if not is_final and header_row.get("GAME_STATUS_ID") == 1:
        tipoff = str(header_row.get("GAME_STATUS_TEXT", "")).strip()
        lines.append(f"Tip-off: {tipoff}" if tipoff else "_Game hasn't started yet._")
        return "\n".join(lines)

    if not is_final or not boxscore_data:
        lines.append("_No box score data available for this game yet._")
        return "\n".join(lines)

    box_inner = boxscore_data.get("boxScoreTraditional", {})
    stat_lines = []
    for team_block in (box_inner.get("awayTeam", {}), box_inner.get("homeTeam", {})):
        tricode = team_block.get("teamTricode", "")
        emoji = _nba_team_emoji(tricode)
        for p in team_block.get("players", []):
            stats = p.get("statistics", {})
            pts = stats.get("points") or 0
            reb = stats.get("reboundsTotal") or 0
            ast = stats.get("assists") or 0
            stl = stats.get("steals") or 0
            blk = stats.get("blocks") or 0
            qualifies = pts >= 15 or reb >= 10 or ast >= 10 or stl >= 5 or blk >= 4
            if not qualifies:
                continue
            name = p.get("nameI") or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip() or "Unknown"
            pos = p.get("position", "")
            pos_part = f"({pos}) " if pos else ""
            stat_parts = []
            if pts:
                stat_parts.append(f"{pts} PTS")
            if reb:
                stat_parts.append(f"{reb} REB")
            if ast:
                stat_parts.append(f"{ast} AST")
            if stl:
                stat_parts.append(f"{stl} STL")
            if blk:
                stat_parts.append(f"{blk} BLK")
            stat_lines.append(f"{emoji} **{pos_part}{name}: {' - '.join(stat_parts)}**")

    lines.extend(stat_lines if stat_lines else ["_No box score data available for this game yet._"])
    return "\n".join(lines)


TEAM_EMOJIS_NFL = {
    "ARI": "<:ARInfl:1271259930648903790>",
    "ATL": "<:ATLnfl:1271259952475803678>",
    "BAL": "<:BALnfl:1271259969651605525>",
    "BUF": "<:BUFnfl:1271259986411913301>",
    "CAR": "<:CARnfl:1409033934922322021>",
    "CHI": "<:CHInfl:1271260037310054401>",
    "CIN": "<:CINnfl:1271260058256408598>",
    "CLE": "<:CLEnfl:1271260077495685120>",
    "DAL": "<:DALnfl:1271260112748548186>",
    "DEN": "<:DENnfl:1271260130012303410>",
    "DET": "<:DETnfl:1271260151059578911>",
    "GB":  "<:GBPnfl:1271260186665025629>",
    "HOU": "<:HOUnfl:1271260208454439053>",
    "IND": "<:INDnfl:1271260234656120996>",
    "JAX": "<:JAXnfl:1271260252859273237>",
    "KC":  "<:KCCnfl:1271260270198521918>",
    "LAC": "<:LACnfl:1271260289798504600>",
    "LAR": "<:LARnfl:1497074404834934784>",
    "LV":  "<:LVRnfl:1271281202921476111>",
    "MIA": "<:MIAnfl:1271260364209655890>",
    "MIN": "<:MINnfl:1271260384640106496>",
    "NE":  "<:NEPnfl:1271281121602179103>",
    "NO":  "<:NOSnfl:1271281147967442974>",
    "NYG": "<:NYGnfl:1271280410059341845>",
    "NYJ": "<:NYJnfl:1271281171178852405>",
    "PHI": "<:PHInfl:1271281214791356530>",
    "PIT": "<:PITnfl:1271281232717811753>",
    "SEA": "<:SEAnfl:1271281278100045946>",
    "SF":  "<:SFRnfl:1271281254582452276>",
    "TB":  "<:TBBnfl:1271281305996365959>",
    "TEN": "<:TENnfl:1481826117160538122>",
    "WSH": "<:WSHnfl:1271281334752514129>",


    "STL": "<:STLRamsNFL:1529280552597721209>",
    "SD":  "<:SDChargersNFL:1529281033802092767>",
}


HISTORICAL_NFL_EMOJIS = {
    "Oilers": "<:HOUOilersNFL:1529280812900683959>",
}

LEAGUE_LOGO_NFL = "<:NFL:1271292836024811551>"


_WASHINGTON_NAME_ERAS = [
    (date(1937, 1, 1), date(2020, 7, 13), "Washington Redskins"),
    (date(2020, 7, 13), date(2022, 2, 2), "Washington Football Team"),
    (date(2022, 2, 2), date(9999, 12, 31), "Washington Commanders"),
]


def _resolve_team_display_name(abbr: str, default_name: str, iso_date: str) -> str:
    if abbr != "WSH" or not iso_date:
        return default_name
    try:
        game_date = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return default_name
    for start, end, era_name in _WASHINGTON_NAME_ERAS:
        if start <= game_date < end:
            return era_name
    return default_name


_DEFENSIVE_POSITIONS = {"DL", "DE", "DT", "NT", "LB", "ILB", "OLB", "CB", "S", "SS", "FS", "DB"}


NFL_THROWBACK_ERAS: dict[str, list[tuple[date, date, str]]] = {
    "ATL": [
        (date(1966, 1, 1), date(1990, 1, 1), "<:AtlantaFalcons1966:1529496074983571506>"),
        (date(1990, 1, 1), date(9999, 12, 31), "<:AtlantaFalcons1989:1529496076069896383>"),
    ],
    "BAL": [(date(1996, 1, 1), date(1999, 3, 1), "<:BaltimoreRavens1996:1529496073821884577>")],
    "BUF": [(date(1962, 1, 1), date(1974, 1, 1), "<:BuffaloBills1970:1529496072634761416>")],
    "CAR": [(date(1995, 1, 1), date(9999, 12, 31), "<:CarolinaPanthers1995:1529496071393251408>")],


    "CHI": [(date(2002, 1, 1), date(9999, 12, 31), "<:ChicagoBears2002:1529496069644226690>")],
    "CIN": [
        (date(1981, 1, 1), date(1997, 1, 1), "<:CincinnatiBengals1981:1529505219736637440>"),
        (date(1997, 1, 1), date(9999, 12, 31), "<:CincinnatiBengals1997:1529496376075878460>"),
    ],


    "CLE": [
        (date(1959, 1, 1), date(1970, 1, 1), "<:ClevelandBrowns1959:1529505214984622273>"),
        (date(1970, 1, 1), date(9999, 12, 31), "<:ClevelandBrowns1970:1529505217626902568>"),
    ],
    "DAL": [(date(1960, 1, 1), date(1964, 1, 1), "<:DallasCowboys1960:1529496375119581294>")],
    "DEN": [(date(1960, 1, 1), date(1997, 1, 1), "<:DenverBroncos1970:1529505213294313587>")],
    "DET": [
        (date(1970, 1, 1), date(2009, 1, 1), "<:DetroitLions1970:1529496043505586307>"),
        (date(2009, 1, 1), date(9999, 12, 31), "<:DetroitLions2009:1529496040590409941>"),
    ],
    "JAX": [(date(1995, 1, 1), date(2013, 1, 1), "<:JacksonvilleJaguars1995:1529496038623150101>")],


    "LAR": [(date(1972, 1, 1), date(1995, 1, 1), "<:LosAngelesRams1983:1529496035615969411>")],
    "MIA": [
        (date(1966, 1, 1), date(1997, 1, 1), "<:MiamiDolphins1973:1529496034407874620>"),
        (date(1997, 1, 1), date(2013, 1, 1), "<:MiamiDolphins1997:1529496031614468269>"),
    ],
    "NE": [(date(1961, 1, 1), date(1993, 1, 1), "<:NewEnglandPatriots1972:1529505210446118912>")],
    "NO": [(date(1967, 1, 1), date(9999, 12, 31), "<:NewOrleansSaints1967:1529505208932106451>")],
    "NYG": [(date(1975, 1, 1), date(2000, 1, 1), "<:NewYorkGiants1976:1529496015571255357>")],
    "NYJ": [
        (date(1963, 1, 1), date(1998, 1, 1), "<:NewYorkJets1967:1529505207875145818>"),
        (date(1998, 1, 1), date(2019, 1, 1), "<:NewYorkJets1998:1529505203319996589>"),
    ],


    "PHI": [
        (date(1948, 1, 1), date(1989, 1, 1), "<:PhiladelphiaEagles1948:1529496009808543935>"),
        (date(1989, 1, 1), date(1996, 1, 1), "<:PhiladelphiaEagles1989:1529496008281686216>"),
    ],
    "PIT": [(date(1962, 1, 1), date(9999, 12, 31), "<:PittsburghSteelers1962:1529505200195371179>")],


    "SD": [(date(1974, 1, 1), date(9999, 12, 31), "<:SanDiegoChargers1974:1529505195808133321>")],
    "SF": [(date(1968, 1, 1), date(9999, 12, 31), "<:SanFrancisco49ers1968:1529505198052216964>")],
    "SEA": [(date(1976, 1, 1), date(2002, 1, 1), "<:SeattleSeahawks1976:1529495994608124174>")],


    "ARI": [(date(1960, 1, 1), date(1988, 1, 1), "<:StLouisCardinals1970:1529495985863004270>")],
    "STL": [(date(1995, 1, 1), date(2016, 1, 1), "<:StLouisRams2000:1529496037301944410>")],
    "TB": [
        (date(1976, 1, 1), date(1997, 1, 1), "<:TampaBayBuccaneers1976:1529495993031065640>"),
        (date(1997, 1, 1), date(9999, 12, 31), "<:TampaBayBuccaneers1997:1529495991584030740>"),
    ],
    "TEN": [(date(1999, 1, 1), date(9999, 12, 31), "<:TennesseeTitans1999:1529495990300573756>")],


    "WSH": [(date(1972, 1, 1), date(2020, 7, 13), "<:WashingtonRedskins1972:1529495984521084958>")],
}


def _nfl_throwback_emoji(abbr: str, game_iso_date: str) -> str | None:

    return None


def _nfl_team_emoji(abbr: str, team_name: str = "", game_iso_date: str = "") -> str:

    throwback = _nfl_throwback_emoji(abbr, game_iso_date)
    if throwback:
        return throwback
    for keyword, emoji in HISTORICAL_NFL_EMOJIS.items():
        if keyword in team_name:
            return emoji
    return TEAM_EMOJIS_NFL.get(abbr, f":{abbr.lower()}:" if abbr else "")


def _record_str(competitor: dict) -> str:

    entries = competitor.get("record") or competitor.get("records") or []
    if isinstance(entries, dict):
        entries = [entries]

    for rec in entries:
        if rec.get("type") == "total" or rec.get("name") == "overall":
            val = rec.get("summary") or rec.get("displayValue")
            if val:
                return val

    if entries:
        first = entries[0]
        val = first.get("summary") or first.get("displayValue")
        if val:
            return val

    return ""


def _safe_int(val) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _espn_stat_category(team_block: dict, label_marker: str, exclude_marker: str | None = None) -> dict | None:

    for cat in team_block.get("statistics", []):
        labels = cat.get("labels", [])
        if label_marker in labels and (exclude_marker is None or exclude_marker not in labels):
            return cat
    return None


def _espn_stats_dict(labels: list, stats: list) -> dict:
    return dict(zip(labels, stats))


def _espn_team_boxscore_block(summary: dict, team_abbr: str) -> dict | None:
    for team_block in summary.get("boxscore", {}).get("players", []):
        if team_block.get("team", {}).get("abbreviation") == team_abbr:
            return team_block
    return None


def _nfl_qb_line(team_block: dict, team_emoji: str, full_bold: bool = False) -> tuple[str, str | None] | None:

    passing = _espn_stat_category(team_block, "C/ATT")
    if not passing or not passing.get("athletes"):
        return None
    labels = passing.get("labels", [])
    entry = passing["athletes"][0]
    starter_key = _athlete_key(entry)
    stat_map = _espn_stats_dict(labels, entry.get("stats", []))
    athlete = entry.get("athlete", {})
    name = athlete.get("shortName") or athlete.get("displayName", "Unknown")
    catt = stat_map.get("C/ATT", "?")
    yds = stat_map.get("YDS", "0")
    td = stat_map.get("TD", "0")
    interc = stat_map.get("INT", "0")
    core = f"{catt} - {yds} YDS - {td} TD - {interc} INT"

    rushing = _espn_stat_category(team_block, "CAR")
    if rushing:
        for e in rushing.get("athletes", []):
            if _athlete_key(e) != starter_key:
                continue
            rsm = _espn_stats_dict(rushing.get("labels", []), e.get("stats", []))
            rush_td = _safe_int(rsm.get("TD", "0"))
            if rush_td >= 1:
                car = rsm.get("CAR", "0")
                rush_yds = rsm.get("YDS", "0")
                core += f" - {car} CAR - {rush_yds} YDS - {rush_td} RUSH TD"
            break

    line = f"{team_emoji} (QB) {name}: {core}"
    return line, starter_key


def _position_priority(position: str, default: int) -> int:
    if position == "QB":
        return 0
    if position == "RB":
        return 1
    if position == "WR":
        return 2
    if position == "TE":
        return 3
    if position in _DEFENSIVE_POSITIONS:
        return 4
    return default


def _athlete_key(entry: dict) -> str | None:

    athlete = entry.get("athlete", {})
    return athlete.get("id") or athlete.get("displayName") or athlete.get("shortName")


def _fmt_stat_line(emoji: str, pos: str, name: str, stats: str, full_bold: bool = True) -> str:

    tag = f"({pos}) " if pos else ""
    return f"{emoji} {tag}{name}: {stats}"


def _nfl_touchdown_entries(team_block: dict, team_emoji: str, qb_starter_key: str | None = None, full_bold: bool = False, position_map: dict[str, str] | None = None) -> list[tuple[int, str]]:

    entries: list[tuple[int, str]] = []
    position_map = position_map or {}

    passing = _espn_stat_category(team_block, "C/ATT")
    qb_keys = {_athlete_key(e) for e in (passing.get("athletes", []) if passing else [])} - {None}

    rushing = _espn_stat_category(team_block, "CAR")
    rushing_stats: dict[str, dict] = {}
    if rushing:
        rlabels = rushing.get("labels", [])
        for e in rushing.get("athletes", []):
            key = _athlete_key(e)
            if key is None or key == qb_starter_key:
                continue
            sm = _espn_stats_dict(rlabels, e.get("stats", []))
            athlete = e.get("athlete", {})
            full_name = athlete.get("displayName", "")
            rushing_stats[key] = {
                "name": athlete.get("shortName") or full_name or "Unknown",
                "full_name": full_name,
                "car": sm.get("CAR", "0"),
                "yds": sm.get("YDS", "0"),
                "td": _safe_int(sm.get("TD", "0")),
            }

    rb_keys = {k for k in rushing_stats if k not in qb_keys}

    receiving = _espn_stat_category(team_block, "REC", exclude_marker="FUM")
    receiving_stats: dict[str, dict] = {}
    if receiving:
        rlabels = receiving.get("labels", [])
        for e in receiving.get("athletes", []):
            key = _athlete_key(e)
            if key is None:
                continue
            sm = _espn_stats_dict(rlabels, e.get("stats", []))
            athlete = e.get("athlete", {})
            full_name = athlete.get("displayName", "")
            receiving_stats[key] = {
                "name": athlete.get("shortName") or full_name or "Unknown",
                "full_name": full_name,
                "rec": sm.get("REC", "0"),
                "yds": sm.get("YDS", "0"),
                "td": _safe_int(sm.get("TD", "0")),
                "pos_raw": (e.get("position") or athlete.get("position") or {}).get("abbreviation"),
            }


    for key in set(rushing_stats) | set(receiving_stats):
        r = rushing_stats.get(key)
        c = receiving_stats.get(key)
        rush_td = r["td"] if r else 0
        rec_td = c["td"] if c else 0
        if rush_td < 1 and rec_td < 1:
            continue

        is_qb = key in qb_keys
        is_rb = key in rb_keys
        name = (r or c)["name"]
        full_name = (r or c)["full_name"]
        real_pos = position_map.get(full_name.lower()) if full_name else None

        if r and c:
            if is_qb:
                pos = "QB"
            elif real_pos:
                pos = real_pos
            elif _safe_int(r["car"]) > _safe_int(c["rec"]):
                pos = "RB"
            else:
                pos = c["pos_raw"] or "WR"
            line = _fmt_stat_line(
                team_emoji, pos, name,
                f"{r['car']} CAR - {r['yds']} YDS - {rush_td} TD - {c['rec']} REC - {c['yds']} YDS - {rec_td} TD",
                full_bold,
            )
            entries.append((_position_priority(pos, default=(1 if pos == "RB" else 2)), line))
        elif r:
            if is_qb:
                pos, td_label = "QB", "RUSH TD"
            else:
                pos, td_label = (real_pos or "RB"), "TD"
            line = _fmt_stat_line(team_emoji, pos, name, f"{r['car']} CAR - {r['yds']} YDS - {rush_td} {td_label}", full_bold)
            entries.append((_position_priority(pos, default=1), line))
        elif c:
            if is_qb:
                pos, td_label = "QB", "REC TD"
            elif real_pos:
                pos, td_label = real_pos, "TD"
            elif is_rb:
                pos, td_label = "RB", "REC TD"
            else:
                pos, td_label = (c["pos_raw"] or "WR"), "TD"
            line = _fmt_stat_line(team_emoji, pos, name, f"{c['rec']} REC - {c['yds']} YDS - {rec_td} {td_label}", full_bold)
            entries.append((_position_priority(pos, default=2), line))


    fumbles = _espn_stat_category(team_block, "FUM")
    if fumbles:
        labels = fumbles.get("labels", [])
        for e in fumbles.get("athletes", []):
            sm = _espn_stats_dict(labels, e.get("stats", []))
            td = _safe_int(sm.get("TD", "0"))
            if td < 1:
                continue
            athlete = e.get("athlete", {})
            name = athlete.get("shortName") or athlete.get("displayName", "Unknown")
            pos = (e.get("position") or athlete.get("position") or {}).get("abbreviation", "")
            rec = sm.get("REC", sm.get("FR", "0"))
            line = _fmt_stat_line(team_emoji, pos, name, f"{rec} FUM REC - {td} TD", full_bold)
            entries.append((4, line))


    interceptions = _espn_stat_category(team_block, "INT", exclude_marker="C/ATT")
    if interceptions:
        labels = interceptions.get("labels", [])
        for e in interceptions.get("athletes", []):
            sm = _espn_stats_dict(labels, e.get("stats", []))
            td = _safe_int(sm.get("TD", "0"))
            if td < 1:
                continue
            athlete = e.get("athlete", {})
            name = athlete.get("shortName") or athlete.get("displayName", "Unknown")
            pos = (e.get("position") or athlete.get("position") or {}).get("abbreviation", "")
            interc = sm.get("INT", "0")
            line = _fmt_stat_line(team_emoji, pos, name, f"{interc} INT - {td} TD", full_bold)
            entries.append((4, line))


    return_categories = [
        cat for cat in team_block.get("statistics", [])
        if cat.get("labels") == ["NO", "YDS", "AVG", "LONG", "TD"]
    ]
    return_type_labels = ["KR", "PR"]
    for idx, returns in enumerate(return_categories[:2]):
        marker = return_type_labels[idx]
        labels = returns.get("labels", [])
        for e in returns.get("athletes", []):
            sm = _espn_stats_dict(labels, e.get("stats", []))
            td = _safe_int(sm.get("TD", "0"))
            if td < 1:
                continue
            athlete = e.get("athlete", {})
            name = athlete.get("shortName") or athlete.get("displayName", "Unknown")
            pos = (e.get("position") or athlete.get("position") or {}).get("abbreviation", "")
            no = sm.get("NO", "0")
            yds = sm.get("YDS", "0")
            line = _fmt_stat_line(team_emoji, pos, name, f"{no} {marker} - {yds} YDS - {td} TD", full_bold)
            entries.append((5, line))

    return entries


def _nfl_quarter_label(status: dict) -> str:

    period = status.get("period")
    display_clock = status.get("displayClock", "")
    if not period or not display_clock:
        return ""

    quarter = f"Q{period}" if period <= 4 else f"OT{period - 4 if period > 5 else ''}"
    return f"{quarter} - {display_clock}"


def _nfl_header_and_score(summary: dict) -> tuple[list[str] | None, dict, dict, str]:

    header = summary.get("header", {})
    competitions = header.get("competitions", [])
    if not competitions:
        return None, {}, {}, ""

    comp = competitions[0]
    competitors = comp.get("competitors", [])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[-1])

    status_type = comp.get("status", {}).get("type", {})
    state = status_type.get("state", "")
    description = status_type.get("description", "")

    if state == "post":
        status_label = "FINAL SCORE"
    elif state == "in":
        status_label = _nfl_quarter_label(comp.get("status", {})) or status_type.get("shortDetail", description).upper()
    else:
        status_label = "SCHEDULED"

    lines = [f"**{status_label} - NFL - {_fmt_header_datetime(comp.get('date', ''))}** {LEAGUE_LOGO_NFL}", ""]

    away_score = _safe_int(away.get("score", "-1")) if state != "pre" else -1
    home_score = _safe_int(home.get("score", "-1")) if state != "pre" else -1
    away_won = state == "post" and away_score > home_score
    home_won = state == "post" and home_score > away_score

    game_iso_date = comp.get("date", "")

    for c, won in ((away, away_won), (home, home_won)):
        team = c.get("team", {})
        abbr = team.get("abbreviation", "")
        raw_name = team.get("shortDisplayName", team.get("displayName", ""))
        name = _resolve_team_display_name(abbr, raw_name, game_iso_date)
        record = _record_str(c)
        rec_part = f"({record}) " if record else ""
        name_part = f"{rec_part}{name} {_nfl_team_emoji(abbr, name, game_iso_date)}"
        if state == "pre":
            lines.append(f"**{name_part}**")
        else:
            score = c.get("score", "?")
            if won:
                lines.append(f"**{name_part} - {score}**")
            else:
                lines.append(f"**{name_part}** - {score}")

    return lines, away, home, state


def format_nfl_final(summary: dict) -> str:

    lines, away, home, state = _nfl_header_and_score(summary)
    if lines is None:
        return "Couldn't find game data for that team."

    if state == "pre":
        comp = summary.get("header", {}).get("competitions", [{}])[0]
        formatted = _fmt_header_datetime(comp.get("date", ""))
        lines.append("")
        lines.append(f"Kickoff: {formatted}" if formatted else "_Game hasn't started yet._")

    return "\n".join(lines)


def format_nfl_newscast(summary: dict) -> str:

    header = summary.get("header", {})
    competitions = header.get("competitions", [])
    if not competitions:
        return "Couldn't find game data for that team."

    comp = competitions[0]
    competitors = comp.get("competitors", [])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[-1])

    status_type = comp.get("status", {}).get("type", {})
    state = status_type.get("state", "")
    description = status_type.get("description", "")

    if state == "post":
        status_label = "FINAL SCORE"
    elif state == "in":
        status_label = _nfl_quarter_label(comp.get("status", {})) or status_type.get("shortDetail", description).upper()
    else:
        status_label = "SCHEDULED"

    lines = [f"**{status_label} - NFL - {_fmt_header_datetime(comp.get('date', ''))}** {LEAGUE_LOGO_NFL}", ""]

    away_score = _safe_int(away.get("score", "-1")) if state != "pre" else -1
    home_score = _safe_int(home.get("score", "-1")) if state != "pre" else -1
    away_won = state == "post" and away_score > home_score
    home_won = state == "post" and home_score > away_score

    game_iso_date = comp.get("date", "")

    for c, won in ((away, away_won), (home, home_won)):
        team = c.get("team", {})
        abbr = team.get("abbreviation", "")
        raw_name = team.get("shortDisplayName", team.get("displayName", ""))
        name = _resolve_team_display_name(abbr, raw_name, game_iso_date)
        record = _record_str(c)
        rec_part = f"({record}) " if record else ""
        name_part = f"{rec_part}{name} {_nfl_team_emoji(abbr, name, game_iso_date)}"
        if state == "pre":
            lines.append(f"**{name_part}**")
        else:
            score = c.get("score", "?")
            if won:
                lines.append(f"**{name_part} - {score}**")
            else:
                lines.append(f"**{name_part}** - {score}")

    lines.append(f"**{'—' * 15}**")
    lines.append("")

    if state == "pre":
        formatted = _fmt_header_datetime(comp.get("date", ""))
        lines.append(f"Kickoff: {formatted}" if formatted else "_Game hasn't started yet._")
    else:
        away_abbr = away.get("team", {}).get("abbreviation", "")
        home_abbr = home.get("team", {}).get("abbreviation", "")
        away_name = away.get("team", {}).get("shortDisplayName", away.get("team", {}).get("displayName", ""))
        home_name = home.get("team", {}).get("shortDisplayName", home.get("team", {}).get("displayName", ""))
        stat_lines = []
        position_map = summary.get("_playerPositions", {})
        for abbr, team_name in ((away_abbr, away_name), (home_abbr, home_name)):
            team_block = _espn_team_boxscore_block(summary, abbr)
            if not team_block:
                continue
            resolved_emoji = _nfl_team_emoji(abbr, team_name, comp.get("date", ""))
            qb_result = _nfl_qb_line(team_block, resolved_emoji, full_bold=True)
            starter_key = None
            if qb_result:
                qb_line, starter_key = qb_result
                stat_lines.append(qb_line)
            td_entries = sorted(
                _nfl_touchdown_entries(team_block, resolved_emoji, starter_key, full_bold=True, position_map=position_map),
                key=lambda t: t[0],
            )
            stat_lines.extend(line for _, line in td_entries)
        if stat_lines:
            lines.append(f"**{chr(10).join(stat_lines)}**")
        else:
            lines.append("_No box score data available for this game yet._")

    return "\n".join(lines)


def format_nfl_boxscore(summary: dict) -> str:

    lines, away, home, state = _nfl_header_and_score(summary)
    if lines is None:
        return "Couldn't find game data for that team."

    lines.append(f"**{'—' * 15}**")
    lines.append("")

    comp = summary.get("header", {}).get("competitions", [{}])[0]

    if state == "pre":
        formatted = _fmt_header_datetime(comp.get("date", ""))
        lines.append(f"Kickoff: {formatted}" if formatted else "_Game hasn't started yet._")
    else:
        away_abbr = away.get("team", {}).get("abbreviation", "")
        home_abbr = home.get("team", {}).get("abbreviation", "")
        away_name = away.get("team", {}).get("shortDisplayName", away.get("team", {}).get("displayName", ""))
        home_name = home.get("team", {}).get("shortDisplayName", home.get("team", {}).get("displayName", ""))
        stat_lines = []
        position_map = summary.get("_playerPositions", {})
        for abbr, team_name in ((away_abbr, away_name), (home_abbr, home_name)):
            team_block = _espn_team_boxscore_block(summary, abbr)
            if not team_block:
                continue
            resolved_emoji = _nfl_team_emoji(abbr, team_name, comp.get("date", ""))
            qb_result = _nfl_qb_line(team_block, resolved_emoji)
            starter_key = None
            if qb_result:
                qb_line, starter_key = qb_result
                stat_lines.append(qb_line)
            td_entries = sorted(_nfl_touchdown_entries(team_block, resolved_emoji, starter_key, position_map=position_map), key=lambda t: t[0])
            stat_lines.extend(line for _, line in td_entries)
        if stat_lines:
            lines.append(f"**{chr(10).join(stat_lines)}**")
        else:
            lines.append("_No box score data available for this game yet._")

    return "\n".join(lines)


LEAGUE_LOGO_CFB = "<:NCAAFootball:1271356043221536808>"


TEAM_EMOJIS_CFB = {
    "Alabama": "<:ALAncaa:1271341770487365706>",
    "Arizona": "<:ARIncaa:1271341876762378313>",
    "Arkansas": "<:ARKncaa:1271488370396106843>",
    "Arizona State": "<:ASUncaa:1271341923835183226>",
    "Auburn": "<:AUBncaa:1271488381129461832>",
    "Baylor": "<:BAYncaa:1271342114180956262>",
    "Boston College": "<:BOSncaa:1271342471632130109>",
    "Boise State": "<:BSUncaa:1310672243365253290>",
    "BYU": "<:BYUncaa:1271488395071455314>",
    "California": "<:CALncaa:1271492029402320926>",
    "Cincinnati": "<:CINncaa:1271488410108039271>",
    "Clemson": "<:CLEMncaa:1271342547113082933>",
    "Colorado": "<:COLncaa:1271342586946261084>",
    "UConn": "<:CONncaa:1271340403873939558>",
    "Colorado State": "<:CSUncaa:1389262020079124511>",
    "Duke": "<:DUKEncaa:1271342626670514187>",
    "Florida": "<:FLAncaa:1271343072260653057>",
    "Fresno State": "<:FRESncaa:1389262045874225152>",
    "Florida State": "<:FSUncaa:1271343494803488870>",
    "Georgia Tech": "<:GATncaa:1271488423840059464>",
    "Houston": "<:HOUncaa:1271343589489774684>",
    "Illinois": "<:ILLncaa:1271343633844666472>",
    "Indiana": "<:INDncaa:1271488442039009322>",
    "Iowa": "<:IOWAncaa:1271493398892773488>",
    "Iowa State": "<:ISUncaa:1271488458808103025>",
    "Kansas": "<:KANncaa:1271343797921513545>",
    "Kentucky": "<:KENncaa:1271343934555029505>",
    "Kansas State": "<:KSUncaa:1271488473244631195>",
    "Louisville": "<:LOUncaa:1271343986887626787>",
    "LSU": "<:LSUncaa:1271344049160192021>",
    "Memphis": "<:MEMncaa:1331398729919496224>",
    "Miami": "<:MIAncaa:1271344281373773936>",
    "Michigan": "<:MICHncaa:1271344317272948838>",
    "Minnesota": "<:MINncaa:1271488487522042059>",
    "Missouri": "<:MIZncaa:1271344374994833462>",
    "Mississippi State": "<:MSSTncaa:1271488517947654165>",
    "Michigan State": "<:MSUncaa:1271344332754124802>",
    "NC State": "<:NCSTncaa:1271344486978682972>",
    "Nebraska": "<:NEBncaa:1271344430099468369>",
    "Northwestern": "<:NWUncaa:1271488543323197573>",
    "Oklahoma": "<:OKLAncaa:1271344710299942943>",
    "Oklahoma State": "<:OKSTncaa:1271488559668269097>",
    "Ole Miss": "<:OLEncaa:1271344748715835406>",
    "Oregon": "<:OREncaa:1271344782337376326>",
    "Oregon State": "<:ORSTncaa:1271488575929712733>",
    "Ohio State": "<:OSUncaa:1271344689068376126>",
    "Pittsburgh": "<:PITncaa:1271344841556492298>",
    "Penn State": "<:PSUncaa:1271344806630526996>",
    "Purdue": "<:PURncaa:1271344869608263700>",
    "Rutgers": "<:RUTncaa:1271344904207077389>",
    "South Carolina": "<:SCARncaa:1271344991364452372>",
    "San Diego State": "<:SDSUncaa:1389262069299417168>",
    "SMU": "<:SMUncaa:1271488589120802817>",
    "Stanford": "<:STAncaa:1271488610243313716>",
    "Syracuse": "<:SYRncaa:1271345037300600884>",
    "Texas A&M": "<:TAMncaa:1436968821012303994>",
    "TCU": "<:TCUncaa:1271488620741660744>",
    "Tennessee": "<:TENncaa:1271345100638650379>",
    "Texas": "<:TEXncaa:1271345133056561265>",
    "Texas Tech": "<:TTUncaa:1522314065756819486>",
    "Tulane": "<:TULncaa:1271495927072559125>",
    "UCF": "<:UCFncaa:1271514950543867904>",
    "UCLA": "<:UCLAncaa:1271345271963652137>",
    "Georgia": "<:UGAncaa:1271343521135198208>",
    "Maryland": "<:UMDncaa:1271344228064301120>",
    "North Carolina": "<:UNCncaa:1271344569975574609>",
    "UNLV": "<:UNLVncaa:1323203254846492752>",
    "USC": "<:USCncaa:1271350178057687091>",
    "South Florida": "<:USFncaa:1420562079462588469>",
    "Utah State": "<:USUncaa:1389262090535178362>",
    "Utah": "<:UTAHncaa:1271350272102498445>",
    "UTSA": "<:UTSAncaa:1399018732193583115>",
    "Virginia": "<:UVAncaa:1271350313093300316>",
    "Vanderbilt": "<:VANncaa:1271488658461167686>",
    "Virginia Tech": "<:VATncaa:1271350340851208192>",
    "Wake Forest": "<:WAKEncaa:1271488668518846557>",
    "Washington": "<:WASncaa:1271350368055328800>",
    "Wisconsin": "<:WISncaa:1271350454068052000>",
    "Washington State": "<:WSUncaa:1271488683782180947>",
    "West Virginia": "<:WVUncaa:1271488704841515080>",


    "Air Force": "<:AirForceFalcons:1302848800016175146>",
    "Akron": "<:AkronZips:1302848556654399588>",
    "Army": "<:ArmyBlackKnights:1389270649037520999>",
    "Ball State": "<:BallStateCardinals:1302848585783836804>",
    "Bowling Green": "<:BowlingGreenFalcons:1302848610114867250>",
    "Buffalo": "<:BuffaloBulls:1302848635993853993>",
    "Central Michigan": "<:CentralMichiganChippewas:1302848670546526259>",
    "Charlotte": "<:Charlotte49ers:1302843193553059921>",
    "Delaware": "<:DelawareFightinBlueHens:1302844443052871691>",
    "East Carolina": "<:EastCarolinaPirates:1302843213832261633>",
    "Eastern Michigan": "<:EasternMichiganEagles:1302848685318864950>",
    "Florida Atlantic": "<:FloridaAtlanticOwls:1302843241158148147>",
    "Florida International": "<:FloridaInternationalPanthers:1302844119508320316>",
    "Hawai'i": "<:HawaiiRainbowWarriors:1302848889228886112>",
    "Jacksonville State": "<:JacksonvilleStateGamecocks:1302844136843513858>",
    "Kennesaw State": "<:KennesawStateOwls:1302844152911888478>",
    "Kent State": "<:KentStateGoldenFlashes:1302848748866506793>",
    "Liberty": "<:LibertyFlames:1302844989809623071>",
    "Louisiana Tech": "<:LouisianaTechBulldogs:1302844197803659314>",
    "Miami (OH)": "<:MiamiOHRedHawks:1302848776486125609>",
    "Middle Tennessee": "<:MiddleTennesseeStateBlueRaiders:1302844226446295111>",
    "Missouri State": "<:MissouriStateBears:1302844561684430859>",
    "Navy": "<:NavyMidshipmen:1389270669937606778>",
    "Nevada": "<:NevadaWolfPack:1302848914302570558>",
    "New Mexico": "<:NewMexicoLobos:1302848950856061039>",
    "New Mexico State": "<:NewMexicoStateAggies:1302844248244355082>",
    "North Dakota State": "<:NorthDakotaStateBison:1470181484966051852>",
    "Northern Illinois": "<:NorthernIllinoisHuskies:1302848802033766442>",
    "North Texas": "<:NorthTexasMeanGreen:1302843444351340566>",
    "Notre Dame": "<:UNDncaa:1271340278447607898>",


    "App State": "<:AppalachianStateMountaineers:1302851278040334387>",
    "Arkansas State": "<:ArkansasStateRedWolves:1302851292674134017>",
    "Coastal Carolina": "<:CoastalCarolinaChanticleers:1302851315533348884>",
    "Georgia Southern": "<:GeorgiaSouthernEagles:1302851330121142284>",
    "Georgia State": "<:GeorgiaStatePanthers:1302851345153523804>",
    "James Madison": "<:JamesMadisonDukes:1302851367517556768>",
    "UL Monroe": "<:LouisianaMonroeWarhawks:1302851401722101760>",
    "Louisiana": "<:LouisianaRaginCajuns:1302851386152718389>",
    "Marshall": "<:MarshallThunderingHerd:1302851423507054626>",
    "Old Dominion": "<:OldDominionMonarchs:1302851449587367956>",
    "South Alabama": "<:SouthAlabamaJaguars:1302851475260833854>",
    "Southern Miss": "<:SouthernMissGoldenEagles:1302851493640011858>",
    "Troy": "<:TroyTrojans:1302851616268881953>",


    "Davidson": "<:DavidsonWildcats:1312102182878707802>",
    "Dayton": "<:DaytonFlyers:1302850483278446705>",
    "Duquesne": "<:DuquesneDukes:1302850498541518888>",
    "Fordham": "<:FordhamRams:1302850516568510546>",
    "Richmond": "<:RichmondSpiders:1302850624785879050>",
    "Rhode Island": "<:RhodeIslandRams:1302850609581527080>",
    "San Diego": "<:SanDiegoToreros:1302851803510997024>",


    "UAlbany": "<:AlbanyGreatDanes:1302870203142770698>",
    "Brown": "<:BrownBears:1324812095430070447>",
    "Bryant": "<:BryantBulldogs:1302870214559535104>",
    "Cal Poly": "<:CalPolyMustangs:1302868612620746792>",
    "Campbell": "<:CampbellFightingCamels:1446741269039546388>",
    "Charleston Southern": "<:CharlestonSouthernBuccaneers:1446743210104721480>",
    "Columbia": "<:ColumbiaLions:1302870716646948934>",
    "Cornell": "<:CornellBigRed:1302870730337288256>",
    "Dartmouth": "<:DartmouthBigGreen:1302870743884894240>",
    "Eastern Washington": "<:EasternWashingtonEagles:1302868422782226482>",
    "Elon": "<:ElonPhoenix:1302869757489451008>",
    "Gardner-Webb": "<:GardnerWebbRunninBulldogs:1446743319857074186>",
    "Hampton": "<:HamptonPirates:1446741307941982258>",
    "Harvard": "<:HarvardCrimson:1302870754915909635>",
    "Idaho State": "<:IdahoStateBengals:1302868476783886367>",
    "Idaho": "<:IdahoVandals:1302868463429226497>",
    "Maine": "<:MaineBlackBears:1302870235996749825>",
    "Monmouth": "<:MonmouthHawks:1302869834325037089>",
    "Montana": "<:MontanaGrizzlies:1302868486619529276>",
    "Montana State": "<:MontanaStateBobcats:1302868498640539708>",
    "New Hampshire": "<:NewHampshireWildcats:1302870253033750528>",
    "North Carolina A&T": "<:NorthCarolinaATAggies:1302869922484850769>",
    "Northern Arizona": "<:NorthernArizonaLumberjacks:1302868521469874240>",
    "Northern Colorado": "<:NorthernColoradoBears:1302868535017603112>",
    "Pennsylvania": "<:PennsylvaniaQuakers:1302870773303873576>",
    "Portland State": "<:PortlandStateVikings:1302868556203036716>",
    "Presbyterian": "<:PresbyterianBlueHose:1302869077207023719>",
    "Princeton": "<:PrincetonTigers:1302870798725414984>",
    "Sacred Heart": "<:SacredHeartPioneers:1521238275895853108>",
    "Southern Utah": "<:SouthernUtahThunderbirds:1389274015318671401>",
    "Stony Brook": "<:StonyBrookSeawolves:1302869967003320321>",
    "Towson": "<:TowsonTigers:1302869976826384404>",
    "UC Davis": "<:UCDavisAggies:1302868630526234645>",
    "Utah Tech": "<:UtahTechTrailblazers:1389274034373525564>",
    "Weber State": "<:WeberStateWildcats:1302868591305297963>",
    "William & Mary": "<:WilliamAndMaryTribe:1302870176768856125>",
    "Yale": "<:YaleBulldogs:1302870808867373127>",
    "Ohio": "<:OhioBobcats:1302848830613753866>",
    "Rice": "<:RiceOwls:1345234453223571545>",
    "Sacramento State": "<:SacramentoStateHornets:1472433383090163999>",
    "Sam Houston": "<:SamHoustonStateBearkats:1302844273196011651>",
    "San José State": "<:SanJoseStateSpartans:1302848989758226444>",
    "Temple": "<:TempleOwls:1302843706394542101>",
    "Texas State": "<:TexasStateBobcats:1399017297095430144>",
    "Toledo": "<:ToledoRockets:1302848854185611335>",
    "Tulsa": "<:TulsaGoldenHurricane:1302873935720747070>",
    "UAB": "<:UABBlazers:1302843751617663039>",
    "Massachusetts": "<:UMassMinutemen:1302848920073801859>",
    "UTEP": "<:UTEPMiners:1334743238275366972>",
    "Western Kentucky": "<:WesternKentuckyHilltoppers:1302844312609886219>",
    "Western Michigan": "<:WesternMichiganBroncos:1302848870946050099>",
    "Wyoming": "<:WyomingCowboys:1302868266019983380>",


    "Central Connecticut": "<:CentralConnecticutBlueDevils:1302895721888088085>",
    "Delaware State": "<:DelawareStateHornets:1302873307497889812>",
    "Eastern Illinois": "<:EasternIllinoisPanthers:1302872034606452787>",
    "Howard": "<:HowardBison:1302873345020399627>",
    "Illinois State": "<:IllinoisStateRedbirds:1302874529986646127>",
    "Indiana State": "<:IndianaStateSycamores:1302874545308438561>",
    "Lindenwood": "<:LindenwoodLions:1302872101245681755>",
    "Maryland Eastern Shore": "<:MarylandEasternShoreHawks:1446742155493376070>",
    "Morehead State": "<:MoreheadStateEagles:1302882605242257489>",
    "Morgan State": "<:MorganStateBears:1302873426293424169>",
    "Murray State": "<:MurrayStateRacers:1302874578044846101>",
    "North Carolina Central": "<:NCCentralEagles:1302873525886910464>",
    "Norfolk State": "<:NorfolkStateSpartans:1302873470564175872>",
    "North Dakota": "<:NorthDakotaFightingHawks:1302874728754839623>",
    "Northern Iowa": "<:NorthernIowaPanthers:1302874603198353472>",
    "South Carolina State": "<:SouthCarolinaStateBulldogs:1446741984046747698>",
    "South Dakota": "<:SouthDakotaCoyotes:1302874758718951434>",
    "South Dakota State": "<:SouthDakotaStateJackrabbits:1452688148931805195>",
    "Southeast Missouri State": "<:SoutheastMissouriStateRedhawks:1302872168702545920>",
    "Southern Illinois": "<:SouthernIllinoisSalukis:1302874624039714890>",
    "St. Francis (PA)": "<:StFrancisRedFlash:1302875122977472554>",
    "Tennessee State": "<:TennesseeStateTigers:1302872206803603559>",
    "UT Martin": "<:UTMartinSkyhawks:1302872190592745523>",
    "Wagner": "<:WagnerSeahawks:1302875150756216845>",
    "Western Illinois": "<:WesternIllinoisLeathernecks:1302872323497398313>",
    "Youngstown State": "<:YoungstownStatePenguins:1302874809537007638>",


    "Albany State": "<:AlbanyStateGoldenRams:1526985268035457237>",
    "Anderson (SC)": "<:AndersonTrojans:1526984859736740026>",
    "Arkansas Baptist": "<:ArkansasBaptistBuffaloes:1526999099461603480>",
    "Bowie State": "<:BowieStateBulldogs:1526999144269349104>",
    "Central Oklahoma": "<:CentralOklahomaBronchos:1526999180013211648>",
    "Central State": "<:CentralStateMarauders:1526986000851664947>",
    "Clark Atlanta": "<:ClarkAtlantaPanthers:1526985299895517296>",
    "Concord": "<:ConcordMountainLions:1526984910168920125>",
    "Dickinson": "<:DickinsonRedDevils:1526999215119536138>",
    "Edward Waters": "<:EdwardWatersTigers:1526986187976216597>",
    "Elizabeth City State": "<:ElizabethCityStateVikings:1526998474946510878>",
    "Fairmont State": "<:FairmontStateFightingFalcons:1526998494928179431>",
    "Fort Valley State": "<:FortValleyStateWildcats:1527031786058813611>",
    "Franklin Pierce": "<:FranklinPierceRavens:1526985971474632766>",
    "Georgetown (KY)": "<:GeorgetownTigers:1526985332405567639>",
    "Glenville State": "<:GlenvilleStatePioneers:1526985028842819696>",
    "Kentucky State": "<:KentuckyStateThorobreds:1526998610934235226>",
    "Lane": "<:LaneCollegeDragons:1526998813385035896>",
    "Louisiana Christian": "<:LouisianaChristianWildcats:1526985068541640855>",
    "Miles": "<:MilesCollegeGoldenBears:1526985397710880828>",
    "Morehouse": "<:MorehouseMaroonTigers:1526985100015964287>",
    "Northern Michigan": "<:NorthernMichiganWildcats:1526999462226956430>",
    "Northwestern (IA)": "<:NorthwesternRedRaiders:1542382089859502182>",
    "Ohio Dominican": "<:OhioDominicanPanthers:1526985127970996399>",
    "Point": "<:PointSkyhawks:1526999667823607948>",
    "Rio Grande": "<:RioGrandeRedStorm:1527031821269864589>",
    "Saint Francis (IN)": "<:SaintFrancisFightingSaints:1526985163656007792>",
    "South Dakota Mines": "<:SouthDakotaMinesHardrockers:1526985198561005680>",
    "Texas Wesleyan": "<:TexasWesleyanRams:1526998979122954342>",
    "Thomas More": "<:ThomasMoreSaints:1526999494271438979>",
    "Tusculum": "<:TusculumPioneers:1526999008894124053>",
    "Virginia Lynchburg": "<:VirginiaLynchburgDragons:1408658573650821310>",
    "Virginia State": "<:VirginiaStateTrojans:1526999562315763842>",
    "Webber International": "<:WebberInternationalWarriors:1526999037708865718>",
    "West Virginia State": "<:WestVirginiaStateYellowJackets:1526999066683248650>",
    "Winston-Salem State": "<:WinstonSalemStateRams:1526985914595672237>",


    "Abilene Christian": "<:AbileneChristianWildcats:1302888010420977704>",
    "Austin Peay": "<:AustinPeayGovernors:1302883715869052959>",
    "Central Arkansas": "<:CentralArkansasBears:1302883876166832168>",
    "Drake": "<:DrakeBulldogs:1302887454293884938>",
    "Eastern Kentucky": "<:EasternKentuckyColonels:1302883933452632095>",
    "Jacksonville": "<:JacksonvilleDolphins:1302884414115549289>",
    "Marist": "<:MaristRedFoxes:1302886588434612254>",
    "Merrimack": "<:MerrimackWarriors:1302885896097501237>",
    "North Alabama": "<:NorthAlabamaLions:1302884582458396673>",
    "Stetson": "<:StetsonHatters:1302885312426545182>",
    "St. Thomas (MN)": "<:StThomasTommies:1302887612822065152>",
    "Tarleton State": "<:TarletonStateTexans:1302888225676726373>",
    "West Florida": "<:WestFloridaArgonauts:1487196299647389717>",
    "West Georgia": "<:WestGeorgiaWolves:1300321948127203348>",


    "Alabama A&M": "<:AlabamaAMBulldogs:1302879072699023461>",
    "Alabama State": "<:AlabamaStateHornets:1302879086573781022>",
    "Alcorn State": "<:AlcornStateBraves:1302879147432874065>",
    "Arkansas-Pine Bluff": "<:ArkansasPineBluffGoldenLions:1302879303683411988>",
    "Bethune-Cookman": "<:BethuneCookmanWildcats:1302879355684519936>",
    "Bucknell": "<:BucknellBison:1302875972944789525>",
    "Chattanooga": "<:ChattanoogaMocs:1302876285089091665>",
    "Colgate": "<:ColgateRaiders:1302875984881647637>",
    "East Tennessee State": "<:EastTennesseeStateBuccaneers:1302876668049883218>",
    "East Texas A&M": "<:EastTexasAMLions:1302878441917648947>",
    "Florida A&M": "<:FloridaAMRattlers:1302879367260803083>",
    "Furman": "<:FurmanPaladins:1302876757086699601>",
    "Grambling": "<:GramblingStateTigers:1302879394376974338>",
    "Holy Cross": "<:HolyCrossCrusaders:1302876007782551583>",
    "Houston Christian": "<:HoustonChristianHuskies:1302877560274944072>",
    "Incarnate Word": "<:IncarnateWordCardinals:1302877712997683201>",
    "Jackson State": "<:JacksonStateTigers:1302879417046925312>",
    "Lafayette": "<:LafayetteLeopards:1302876054238662688>",
    "Lamar": "<:LamarCardinals:1446742676413087824>",
    "Lehigh": "<:LehighMountainHawks:1302876032151453748>",
    "McNeese": "<:McNeeseStateCowboys:1302877945085562892>",
    "Mercer": "<:MercerBears:1302876845812879422>",
    "Mississippi Valley State": "<:MississippiValleyStDeltaDevils:1302879481358192673>",
    "Nicholls": "<:NichollsStateColonels:1302878104330440755>",
    "Northwestern State": "<:NorthwesternStateDemons:1446742700190863391>",
    "Prairie View A&M": "<:PrairieViewAMPanthers:1302879506352046140>",
    "Samford": "<:SamfordBulldogs:1302876939521884162>",
    "SE Louisiana": "<:SELouisianaLions:1446742781463756923>",
    "Southern": "<:SouthernJaguars:1446742725213950096>",
    "Stephen F. Austin": "<:StephenFAustinLumberjacks:1302878395201355806>",
    "Tennessee Tech": "<:TennesseeTechGoldenEagles:1521242188464525514>",
    "Texas Southern": "<:TexasSouthernTigers:1302879533019562057>",
    "The Citadel": "<:TheCitadelBulldogs:1302876306555404329>",
    "UT Rio Grande Valley": "<:UTRioGrandeValleyVaqueros:1302878923130146880>",
    "VMI": "<:VMIKeydets:1302877176122572851>",
    "Western Carolina": "<:WesternCarolinaCatamounts:1302877277406761011>",
    "Wofford": "<:WoffordTerriers:1302877369828249670>",


    "Chicago State": "<:ChicagoStateCougars:1446741882649575566>",
    "Long Island University": "<:LongIslandSharks:1302875105507934250>",
    "Mercyhurst": "<:MercyhurstLakers:1302872949325434890>",
    "New Haven": "<:NewHavenChargers:1369345233254617158>",
    "Robert Morris": "<:RobertMorrisColonials:1302892222433198121>",
    "Stonehill": "<:StonehillSkyhawks:1302875140295491654>",
    "Valparaiso": "<:ValparaisoBeacons:1302874645837385760>",
    "Villanova": "<:VILncaa:1272353485316165683>",
    "Georgetown": "<:GTWNncaa:1437543523372109947>",
    "Butler": "<:BUTncaa:1437543566942539776>",
}


def _cfb_team_emoji(name: str) -> str:

    if not name:
        return ""
    if name in TEAM_EMOJIS_CFB:
        return TEAM_EMOJIS_CFB[name]
    slug = "".join(ch for ch in name.lower() if ch.isalnum())
    return f":{slug}:"


def _cfbd_merge_category(category: dict) -> dict[str, dict]:

    merged: dict[str, dict] = {}
    for stat_type in category.get("types", []):
        type_name = stat_type.get("name", "")
        for athlete in stat_type.get("athletes", []):
            aid = athlete.get("id", athlete.get("name", ""))
            entry = merged.setdefault(aid, {"name": athlete.get("name", "Unknown")})
            entry[type_name] = athlete.get("stat", "")
    return merged


def _cfbd_team_category(team_block: dict, name: str) -> dict | None:
    for cat in team_block.get("categories", []):
        if cat.get("name", "").lower() == name:
            return cat
    return None


def _cfbd_qb_line(team_block: dict, emoji: str, full_bold: bool = False) -> tuple[str, str] | None:

    passing = _cfbd_team_category(team_block, "passing")
    if not passing:
        return None
    athletes = _cfbd_merge_category(passing)
    if not athletes:
        return None

    def _attempts(entry: dict) -> int:
        catt = entry.get("C/ATT", "0-0")
        try:
            return int(str(catt).split("-")[-1])
        except (ValueError, IndexError):
            return 0

    leader_id = max(athletes, key=lambda aid: _attempts(athletes[aid]))
    leader = athletes[leader_id]
    name = leader.get("name", "Unknown")
    catt = leader.get("C/ATT", "?")
    yds = leader.get("YDS", "0")
    td = leader.get("TD", "0")
    interc = leader.get("INT", "0")
    core = f"{catt} - {yds} YDS - {td} TD - {interc} INT"

    rushing = _cfbd_team_category(team_block, "rushing")
    if rushing:
        rush_athletes = _cfbd_merge_category(rushing)
        rush_entry = rush_athletes.get(leader_id)
        if rush_entry:
            rush_td = _safe_int(rush_entry.get("TD", "0"))
            if rush_td >= 1:
                car = rush_entry.get("CAR", "0")
                rush_yds = rush_entry.get("YDS", "0")
                core += f" - {car} CAR - {rush_yds} YDS - {rush_td} RUSH TD"

    line = f"{emoji} (QB) {name}: {core}"
    return line, leader_id


def _cfbd_touchdown_lines(team_block: dict, emoji: str, qb_id: str | None = None, full_bold: bool = False) -> list[str]:

    rushing_cat = _cfbd_team_category(team_block, "rushing")
    receiving_cat = _cfbd_team_category(team_block, "receiving")
    rushing = _cfbd_merge_category(rushing_cat) if rushing_cat else {}
    receiving = _cfbd_merge_category(receiving_cat) if receiving_cat else {}

    passing_cat = _cfbd_team_category(team_block, "passing")
    qb_ids = set(_cfbd_merge_category(passing_cat).keys()) if passing_cat else set()

    lines = []
    for aid in set(rushing) | set(receiving):
        if aid == qb_id:
            continue
        r = rushing.get(aid)
        c = receiving.get(aid)
        rush_td = _safe_int(r.get("TD", "0")) if r else 0
        rec_td = _safe_int(c.get("TD", "0")) if c else 0
        if rush_td < 1 and rec_td < 1:
            continue

        name = (r or c).get("name", "Unknown")
        is_qb = aid in qb_ids

        if r and c:
            car_n = _safe_int(r.get("CAR", "0"))
            rec_n = _safe_int(c.get("CAR", c.get("REC", "0")))
            pos = "QB" if is_qb else ("RB" if car_n > rec_n else "WR")
            core = f"{r.get('CAR', '0')} CAR - {r.get('YDS', '0')} YDS - {rush_td} TD - {c.get('REC', '0')} REC - {c.get('YDS', '0')} YDS - {rec_td} TD"
        elif r:
            pos, td_label = ("QB", "RUSH TD") if is_qb else ("RB", "TD")
            core = f"{r.get('CAR', '0')} CAR - {r.get('YDS', '0')} YDS - {rush_td} {td_label}"
        else:
            pos, td_label = ("QB", "REC TD") if is_qb else ("WR", "TD")
            core = f"{c.get('REC', '0')} REC - {c.get('YDS', '0')} YDS - {rec_td} {td_label}"

        lines.append(f"{emoji} ({pos}) {name}: {core}")
    return lines


def _cfbd_header_and_score(game: dict) -> tuple[list[str], bool, bool, str]:

    completed = game.get("completed", False)
    start_date = game.get("startDate", "")

    if completed:
        status_label = "FINAL SCORE"
    else:


        kickoff = _to_eastern(start_date)
        if kickoff and datetime.now(kickoff.tzinfo) >= kickoff:
            status_label = game.get("_liveStatus") or "IN PROGRESS"
        else:
            status_label = "SCHEDULED"

    away_name = game.get("awayTeam", "")
    home_name = game.get("homeTeam", "")
    away_display = game.get("awayFullName") or away_name
    home_display = game.get("homeFullName") or home_name
    away_points = game.get("awayPoints")
    home_points = game.get("homePoints")
    away_won = completed and isinstance(away_points, (int, float)) and isinstance(home_points, (int, float)) and away_points > home_points
    home_won = completed and isinstance(away_points, (int, float)) and isinstance(home_points, (int, float)) and home_points > away_points

    lines = [f"**{status_label} - CFB - {_fmt_header_datetime(start_date)}** {LEAGUE_LOGO_CFB}", ""]

    away_record = game.get("awayRecord", "")
    home_record = game.get("homeRecord", "")

    for name, emoji_key, points, won, record in (
        (away_display, away_name, away_points, away_won, away_record),
        (home_display, home_name, home_points, home_won, home_record),
    ):
        rec_part = f"({record}) " if record else ""
        name_part = f"{rec_part}{name} {_cfb_team_emoji(emoji_key)}"


        if points is None:
            lines.append(f"**{name_part}**")
        elif won:
            lines.append(f"**{name_part} - {points}**")
        else:
            lines.append(f"**{name_part}** - {points}")

    return lines, away_won, home_won, status_label


def format_cfb_final(game: dict) -> str:

    if not game:
        return "Couldn't find game data for that team."
    lines, _, _, status_label = _cfbd_header_and_score(game)
    if status_label == "SCHEDULED":
        start_date = game.get("startDate", "")
        formatted = _fmt_header_datetime(start_date)
        lines.append("")
        lines.append(f"Kickoff: {formatted}" if formatted else "_Game hasn't started yet._")
    return "\n".join(lines)


def format_cfb_boxscore(game: dict, player_stats: list[dict] | None = None) -> str:

    if not game:
        return "Couldn't find game data for that team."
    lines, _, _, status_label = _cfbd_header_and_score(game)
    lines.append(f"**{'—' * 15}**")
    lines.append("")

    if status_label == "SCHEDULED":
        formatted = _fmt_header_datetime(game.get("startDate", ""))
        lines.append(f"Kickoff: {formatted}" if formatted else "_Game hasn't started yet._")
        return "\n".join(lines)

    if game.get("_liveBoxScoreLines"):
        stat_lines = game["_liveBoxScoreLines"]
    else:
        stat_lines = []
        for team_block in (player_stats or []):
            team_name = team_block.get("team", "")
            emoji = _cfb_team_emoji(team_name)
            qb_result = _cfbd_qb_line(team_block, emoji)
            qb_id = None
            if qb_result:
                qb_line, qb_id = qb_result
                stat_lines.append(qb_line)
            stat_lines.extend(_cfbd_touchdown_lines(team_block, emoji, qb_id))

    if stat_lines:
        lines.append(f"**{chr(10).join(stat_lines)}**")
    else:
        lines.append("_No box score data available for this game yet._")

    return "\n".join(lines)


def format_cfb_newscast(game: dict, player_stats: list[dict] | None = None) -> str:

    if not game:
        return "Couldn't find game data for that team."

    completed = game.get("completed", False)
    start_date = game.get("startDate", "")
    if completed:
        status_label = "FINAL SCORE"
    else:
        kickoff = _to_eastern(start_date)
        if kickoff and datetime.now(kickoff.tzinfo) >= kickoff:
            status_label = game.get("_liveStatus") or "IN PROGRESS"
        else:
            status_label = "SCHEDULED"
    lines = [f"**{status_label} - CFB - {_fmt_header_datetime(start_date)}** {LEAGUE_LOGO_CFB}", ""]

    away_name = game.get("awayTeam", "")
    home_name = game.get("homeTeam", "")
    away_display = game.get("awayFullName") or away_name
    home_display = game.get("homeFullName") or home_name
    away_points = game.get("awayPoints")
    home_points = game.get("homePoints")
    away_won = completed and isinstance(away_points, (int, float)) and isinstance(home_points, (int, float)) and away_points > home_points
    home_won = completed and isinstance(away_points, (int, float)) and isinstance(home_points, (int, float)) and home_points > away_points

    away_record = game.get("awayRecord", "")
    home_record = game.get("homeRecord", "")

    for name, emoji_key, points, won, record in (
        (away_display, away_name, away_points, away_won, away_record),
        (home_display, home_name, home_points, home_won, home_record),
    ):
        rec_part = f"({record}) " if record else ""
        name_part = f"{rec_part}{name} {_cfb_team_emoji(emoji_key)}"
        if points is None:
            lines.append(f"**{name_part}**")
        elif won:
            lines.append(f"**{name_part} - {points}**")
        else:
            lines.append(f"**{name_part}** - {points}")

    lines.append(f"**{'—' * 15}**")
    lines.append("")

    if status_label == "SCHEDULED":
        formatted = _fmt_header_datetime(game.get("startDate", ""))
        lines.append(f"Kickoff: {formatted}" if formatted else "_Game hasn't started yet._")
        return "\n".join(lines)

    if game.get("_liveBoxScoreLines"):
        stat_lines = game["_liveBoxScoreLines"]
    else:
        stat_lines = []
        for team_block in (player_stats or []):
            team_name = team_block.get("team", "")
            emoji = _cfb_team_emoji(team_name)
            qb_result = _cfbd_qb_line(team_block, emoji)
            qb_id = None
            if qb_result:
                qb_line, qb_id = qb_result
                stat_lines.append(qb_line)
            stat_lines.extend(_cfbd_touchdown_lines(team_block, emoji, qb_id))

    if stat_lines:
        lines.append(f"**{chr(10).join(stat_lines)}**")
    else:
        lines.append("_No box score data available for this game yet._")

    return "\n".join(lines)


def format_nhl_final(summary: dict) -> str:
    raise NotImplementedError("NHL formatting not built yet -- MLB and NFL only for now.")


FORMATTERS = {
    "mlb": format_mlb_final,
    "nba": format_nba_final,
    "nfl": format_nfl_final,
    "nhl": format_nhl_final,
    "cfb": format_cfb_final,
}

BOX_FORMATTERS = {
    "mlb": format_mlb_boxscore,
    "nba": format_nba_boxscore,
    "nfl": format_nfl_boxscore,
    "cfb": format_cfb_boxscore,
}

NEWSCAST_FORMATTERS = {
    "mlb": format_mlb_newscast,
    "nba": format_nba_newscast,
    "nfl": format_nfl_newscast,
    "cfb": format_cfb_newscast,
}
