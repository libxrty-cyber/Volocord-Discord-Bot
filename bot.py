

import os
import time
import re
import logging
import random
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

import espn_api
import transactions
import cfbd_api
import mlb_stats_api
import nba_stats_api
from formatters import FORMATTERS, BOX_FORMATTERS, NEWSCAST_FORMATTERS, format_mlb_lineup, format_mlb_probable_pitchers, format_mlb_standings, format_mlb_player_stats, format_transactions, TEAM_EMOJIS, TEAM_EMOJIS_NFL, TEAM_EMOJIS_NBA, TEAM_EMOJIS_CFB, _nfl_quarter_label, _espn_team_boxscore_block, _nfl_qb_line, _nfl_touchdown_entries, _cfb_team_emoji

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scorebot")


logging.getLogger("discord.http").setLevel(logging.DEBUG)


def _err(e: Exception) -> str:

    return str(e) or type(e).__name__


_STAFF_ROLE_KEYWORDS = ("helper", "moderator", "mod", "admin")
_COOLDOWN_SECONDS = 30
_last_used_by_channel: dict[int, float] = {}


def _is_staff(member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    return any(
        any(keyword in role.name.lower() for keyword in _STAFF_ROLE_KEYWORDS)
        for role in member.roles
    )


_STAFF_COOLDOWN_SECONDS = 5


def channel_cooldown_unless_staff():

    async def predicate(ctx: commands.Context) -> bool:
        limit = _STAFF_COOLDOWN_SECONDS if _is_staff(ctx.author) else _COOLDOWN_SECONDS
        now = time.monotonic()
        last = _last_used_by_channel.get(ctx.channel.id, 0.0)
        elapsed = now - last
        if elapsed < limit:
            retry_after = limit - elapsed
            raise commands.CommandOnCooldown(
                commands.Cooldown(1, limit), retry_after, commands.BucketType.channel
            )
        _last_used_by_channel[ctx.channel.id] = now
        return True
    return commands.check(predicate)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="-", intents=intents, help_command=None)


_COMMAND_TIMEOUT_SECONDS = 45
_original_bot_invoke = bot.invoke


async def _invoke_with_timeout(ctx: commands.Context) -> None:
    try:
        await asyncio.wait_for(_original_bot_invoke(ctx), timeout=_COMMAND_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        log.error(
            f"Command timed out after {_COMMAND_TIMEOUT_SECONDS}s: "
            f"'{ctx.message.content}' in channel {ctx.channel.id} (guild {getattr(ctx.guild, 'id', None)})"
        )
        try:
            await ctx.send(f"That took too long and timed out after {_COMMAND_TIMEOUT_SECONDS}s -- please try again.")
        except Exception:
            log.exception("Failed to send the timeout message itself")


bot.invoke = _invoke_with_timeout


SCORES_CHANNEL_ID = 1270884490167718010


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (id: {bot.user.id})")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        await _safe_send(ctx, f"Slow down -- try again in {error.retry_after:.0f}s.")
        return
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        if "staff role" in error.missing_permissions:
            await _safe_send(ctx, "That command is restricted to Helpers/Moderators/Admins.")
        else:
            await _safe_send(ctx, "That command is restricted to administrators.")
        return
    log.exception("Unhandled command error", exc_info=error)
    await _safe_send(ctx, "Something went wrong running that command.")


async def _safe_send(ctx: commands.Context, content: str) -> None:

    try:
        await ctx.send(content)
    except Exception:
        log.exception(f"Failed to send message (content was: {content!r})")


async def _parse_score_style_args(ctx: commands.Context, args: tuple, cmd_name: str, example_team: str = "athletics"):

    if not args:
        await ctx.send(f"Usage: `-{cmd_name} <team>` (e.g. `-{cmd_name} {example_team}`)")
        return None

    sport = "mlb"
    remaining = list(args)

    known_sports = {"mlb", "nba", "nfl", "nhl", "cfb"}
    if remaining[0].lower() in known_sports:
        sport = remaining[0].lower()
        remaining = remaining[1:]

    if not remaining:
        await ctx.send(f"Give me a team too -- e.g. `-{cmd_name} {example_team}`")
        return None


    if remaining and re.fullmatch(r"#\d+", remaining[0]):
        remaining = remaining[1:]

    if not remaining:
        await ctx.send(f"Give me a team too -- e.g. `-{cmd_name} {example_team}`")
        return None

    if sport not in ("mlb", "nfl", "nba", "cfb"):
        await ctx.send(
            f"`{sport.upper()}` support isn't built yet -- MLB, NFL, NBA, and CFB are wired up, "
            f"other sports are stubbed in for later. Try one of those for now."
        )
        return None


    game_number = None
    if sport == "mlb" and remaining:
        match = re.fullmatch(r"(?:game|gm|g)?([12])", remaining[-1].lower())
        if match:
            game_number = int(match.group(1))
            remaining = remaining[:-1]

    if not remaining:
        await ctx.send(f"Give me a team too -- e.g. `-{cmd_name} {example_team}`")
        return None


    date_parsers = {
        "mlb": mlb_stats_api.parse_date_arg,
        "nfl": espn_api.parse_date_arg,
        "nba": nba_stats_api.parse_date_arg,
        "cfb": cfbd_api.parse_date_arg,
    }
    date_arg = None
    date_display = None
    parsed_date = date_parsers[sport](remaining[-1])
    if parsed_date:
        date_arg = parsed_date
        date_display = remaining[-1]
        remaining = remaining[:-1]

    if not remaining:
        await ctx.send(f"Give me a team too -- e.g. `-{cmd_name} {example_team} 7/15`")
        return None

    return sport, " ".join(remaining), date_arg, date_display, game_number


async def _dispatch_score(ctx: commands.Context, sport: str, team_query: str, date_arg, date_display, mode: str = "score", game_number=None):
    if sport == "mlb":
        await _handle_mlb_score(ctx, team_query, date_arg, date_display, mode=mode, game_number=game_number)
    elif sport == "nba":
        await _handle_nba_score(ctx, team_query, date_arg, date_display, mode=mode)
    elif sport == "cfb":
        await _handle_cfb_score(ctx, team_query, date_arg, date_display, mode=mode)
    else:
        await _handle_espn_score(ctx, sport, team_query, date_arg, date_display, mode=mode)


@bot.command(name="score")
@channel_cooldown_unless_staff()
async def score(ctx: commands.Context, *args: str):

    parsed = await _parse_score_style_args(ctx, args, "score")
    if parsed is None:
        return
    sport, team_query, date_arg, date_display, game_number = parsed
    await _dispatch_score(ctx, sport, team_query, date_arg, date_display, mode="score", game_number=game_number)


def _formatter_dict(mode: str) -> dict:
    return {"score": FORMATTERS, "box": BOX_FORMATTERS, "newscast": NEWSCAST_FORMATTERS}[mode]


async def _find_mlb_game_or_next(team_query: str, date_arg, date_display, game_number=None):

    schedule = await mlb_stats_api.get_schedule(date=date_arg)
    game, total_games = mlb_stats_api.find_game_for_team(schedule, team_query, game_number=game_number)
    if game is not None:
        return game, total_games, ""

    team_id = await mlb_stats_api.find_team_id(team_query)
    if team_id is None:
        return None, 0, "team_not_found"

    search_from = date_arg or datetime.now().strftime("%Y-%m-%d")
    next_date = await mlb_stats_api.get_next_scheduled_date(team_id, search_from)
    if next_date is None:
        return None, 0, "no_upcoming_game"

    next_schedule = await mlb_stats_api.get_schedule(date=next_date)
    next_game, next_total = mlb_stats_api.find_game_for_team(next_schedule, team_query)
    if next_game is None:
        return None, 0, "no_upcoming_game"

    when_orig = f"on {date_display}" if date_display else "today"
    note = f"_{team_query.title()} didn't have a game {when_orig} -- showing their next scheduled game on {next_date} instead._"
    return next_game, next_total, note


async def _handle_mlb_score(ctx, team_query: str, date_arg, date_display, mode: str = "score", game_number=None):
    async with ctx.typing():
        try:
            game, total_games, note = await _find_mlb_game_or_next(team_query, date_arg, date_display, game_number)
        except Exception as e:
            log.exception("Failed to fetch schedule")
            await ctx.send(f"Couldn't reach MLB's schedule right now ({_err(e)}).")
            return

        if game is None:
            when = f"on {date_display}" if date_display else "today"
            if note == "team_not_found":
                await ctx.send(f"Couldn't find a team matching **{team_query}**. Check the spelling.")
            elif game_number is not None:
                await ctx.send(f"Couldn't find Game {game_number} for **{team_query}** {when}, and no upcoming game found either.")
            else:
                await ctx.send(f"Couldn't find a game for **{team_query}** {when}, and no upcoming game found in the next 30 days.")
            return

        game_pk = game.get("gamePk")
        try:
            boxscore = await mlb_stats_api.get_boxscore(game_pk)
        except Exception as e:
            log.exception("Failed to fetch boxscore")
            await ctx.send(f"Found the game but couldn't fetch the box score ({_err(e)}).")
            return

        try:
            formatter = _formatter_dict(mode)["mlb"]
            message = formatter(game, boxscore)
        except Exception as e:
            log.exception("Failed to format game")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

        if note:
            message = f"{note}\n\n{message}"


        if total_games > 1 and game_number is None:
            this_game_num = game.get("gameNumber", 1)
            other_num = 2 if this_game_num == 1 else 1
            when = f" {date_display}" if date_display else ""
            message += f"\n\n_This was a doubleheader (showing Game {this_game_num}) -- add `game{other_num}`{when} for the other game._"

    await ctx.send(message)


async def _handle_nba_score(ctx, team_query: str, date_arg, date_display, mode: str = "score"):
    async with ctx.typing():
        try:
            scoreboard = await nba_stats_api.get_scoreboard(date=date_arg)
        except Exception as e:
            log.exception("Failed to fetch NBA scoreboard")
            await ctx.send(f"Couldn't reach the NBA's scoreboard right now ({_err(e)}).")
            return

        game_id = nba_stats_api.find_game_for_team(scoreboard, team_query)
        if game_id is None:
            when = f"on {date_display}" if date_display else "today"
            await ctx.send(
                f"Couldn't find a game for **{team_query}** {when}. "
                f"Check the spelling/date, or the team may not have played that day."
            )
            return

        try:
            boxscore = await nba_stats_api.get_boxscore(game_id)
        except Exception as e:
            log.exception("Failed to fetch NBA boxscore")
            await ctx.send(f"Found the game but couldn't fetch the box score ({_err(e)}).")
            return

        try:
            formatter = _formatter_dict(mode)["nba"]
            message = formatter(scoreboard, boxscore, game_id)
        except Exception as e:
            log.exception("Failed to format NBA game")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

    await ctx.send(message)


@bot.command(name="lineups")
@channel_cooldown_unless_staff()
async def lineups(ctx: commands.Context, *args: str):

    if not args:
        await ctx.send("Usage: `-lineups <team>` (e.g. `-lineups astros`)")
        return

    remaining = list(args)

    game_number = None
    match = re.fullmatch(r"(?:game|gm|g)?([12])", remaining[-1].lower())
    if match:
        game_number = int(match.group(1))
        remaining = remaining[:-1]

    if not remaining:
        await ctx.send("Give me a team too -- e.g. `-lineups astros`")
        return

    date_arg = None
    date_display = None
    parsed_date = mlb_stats_api.parse_date_arg(remaining[-1])
    if parsed_date:
        date_arg = parsed_date
        date_display = remaining[-1]
        remaining = remaining[:-1]

    if not remaining:
        await ctx.send("Give me a team too -- e.g. `-lineups astros`")
        return

    team_query = " ".join(remaining)

    async with ctx.typing():
        try:
            game, total_games, note = await _find_mlb_game_or_next(team_query, date_arg, date_display, game_number)
        except Exception as e:
            log.exception("Failed to fetch schedule")
            await ctx.send(f"Couldn't reach MLB's schedule right now ({_err(e)}).")
            return

        if game is None:
            when = f"on {date_display}" if date_display else "today"
            if note == "team_not_found":
                await ctx.send(f"Couldn't find a team matching **{team_query}**. Check the spelling.")
            elif game_number is not None:
                await ctx.send(f"Couldn't find Game {game_number} for **{team_query}** {when}, and no upcoming game found either.")
            else:
                await ctx.send(f"Couldn't find a game for **{team_query}** {when}, and no upcoming game found in the next 30 days.")
            return

        game_pk = game.get("gamePk")
        try:
            boxscore = await mlb_stats_api.get_boxscore(game_pk)
        except Exception as e:
            log.exception("Failed to fetch boxscore")
            await ctx.send(f"Found the game but couldn't fetch the lineup ({_err(e)}).")
            return

        try:
            message = format_mlb_lineup(game, boxscore)
        except Exception as e:
            log.exception("Failed to format lineup")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

        if note:
            message = f"{note}\n\n{message}"

        if total_games > 1 and game_number is None:
            this_game_num = game.get("gameNumber", 1)
            other_num = 2 if this_game_num == 1 else 1
            when = f" {date_display}" if date_display else ""
            message += f"\n\n_This was a doubleheader (showing Game {this_game_num}) -- add `game{other_num}`{when} for the other game._"

    await ctx.send(message)


@bot.command(name="probablepitchers")
@channel_cooldown_unless_staff()
async def probablepitchers(ctx: commands.Context, *args: str):

    if not args:
        await ctx.send("Usage: `-probablepitchers <team>` (e.g. `-probablepitchers astros`)")
        return

    remaining = list(args)

    game_number = None
    match = re.fullmatch(r"(?:game|gm|g)?([12])", remaining[-1].lower())
    if match:
        game_number = int(match.group(1))
        remaining = remaining[:-1]

    if not remaining:
        await ctx.send("Give me a team too -- e.g. `-probablepitchers astros`")
        return

    date_arg = None
    date_display = None
    parsed_date = mlb_stats_api.parse_date_arg(remaining[-1])
    if parsed_date:
        date_arg = parsed_date
        date_display = remaining[-1]
        remaining = remaining[:-1]

    if not remaining:
        await ctx.send("Give me a team too -- e.g. `-probablepitchers astros`")
        return

    team_query = " ".join(remaining)

    async with ctx.typing():
        try:
            game, total_games, note = await _find_mlb_game_or_next(team_query, date_arg, date_display, game_number)
        except Exception as e:
            log.exception("Failed to fetch schedule")
            await ctx.send(f"Couldn't reach MLB's schedule right now ({_err(e)}).")
            return

        if game is None:
            when = f"on {date_display}" if date_display else "today"
            if note == "team_not_found":
                await ctx.send(f"Couldn't find a team matching **{team_query}**. Check the spelling.")
            elif game_number is not None:
                await ctx.send(f"Couldn't find Game {game_number} for **{team_query}** {when}, and no upcoming game found either.")
            else:
                await ctx.send(f"Couldn't find a game for **{team_query}** {when}, and no upcoming game found in the next 30 days.")
            return

        game_pk = game.get("gamePk")
        try:
            boxscore = await mlb_stats_api.get_boxscore(game_pk)
        except Exception as e:
            log.exception("Failed to fetch boxscore")
            await ctx.send(f"Found the game but couldn't fetch team info ({_err(e)}).")
            return

        try:
            message = format_mlb_probable_pitchers(game, boxscore)
        except Exception as e:
            log.exception("Failed to format probable pitchers")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

        if note:
            message = f"{note}\n\n{message}"

        if total_games > 1 and game_number is None:
            this_game_num = game.get("gameNumber", 1)
            other_num = 2 if this_game_num == 1 else 1
            when = f" {date_display}" if date_display else ""
            message += f"\n\n_This was a doubleheader (showing Game {this_game_num}) -- add `game{other_num}`{when} for the other game._"

    await ctx.send(message)


@bot.command(name="stats")
@channel_cooldown_unless_staff()
async def stats(ctx: commands.Context, *args: str):

    if not args or args[0].lower() not in ("mlb", "nfl", "nba", "cfb"):
        await ctx.send("Usage: `-stats mlb <player name>` (e.g. `-stats mlb Yordan Alvarez`)")
        return

    sport = args[0].lower()
    if sport != "mlb":
        await ctx.send(f"`{sport.upper()}` player stats aren't built yet -- MLB only for now.")
        return

    name_query = " ".join(args[1:]).strip()
    if not name_query:
        await ctx.send("Give me a player name too -- e.g. `-stats mlb Yordan Alvarez`")
        return

    season = datetime.now().year

    async with ctx.typing():
        try:
            person_id = await mlb_stats_api.find_player_id(name_query)
        except Exception as e:
            log.exception("Failed to search for MLB player")
            await ctx.send(f"Couldn't reach MLB's player search right now ({_err(e)}).")
            return

        if person_id is None:
            await ctx.send(f"Couldn't find a player matching **{name_query}**. Check the spelling.")
            return

        try:
            person = await mlb_stats_api.get_player_season_stats(person_id, season)
        except Exception as e:
            log.exception("Failed to fetch MLB player stats")
            await ctx.send(f"Found the player but couldn't fetch their stats ({_err(e)}).")
            return

        try:
            team_id = person.get("currentTeam", {}).get("id")
            person["teamAbbr"] = await mlb_stats_api.team_abbr(team_id) if team_id else ""
        except Exception:
            log.exception("Failed to resolve player's team abbreviation (non-fatal)")
            person["teamAbbr"] = ""

        try:
            message = format_mlb_player_stats(person, season)
        except Exception as e:
            log.exception("Failed to format MLB player stats")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

    await ctx.send(message)


_transactions_cache: dict[str, tuple[float, list[dict]]] = {}
_TRANSACTIONS_CACHE_SECONDS = 300


async def _get_cached_transactions(sport: str) -> list[dict]:
    now = time.monotonic()
    cached = _transactions_cache.get(sport)
    if cached and (now - cached[0]) < _TRANSACTIONS_CACHE_SECONDS:
        return cached[1]
    data = await espn_api.get_all_transactions(sport)
    _transactions_cache[sport] = (now, data)
    return data


async def _handle_transactions(ctx: commands.Context, args: tuple, category: str, category_label: str):
    if not args or args[0].lower() not in ("nfl",):
        await ctx.send(f"Usage: `-{category_label.lower()} nfl [team]` (e.g. `-{category_label.lower()} nfl texans`) -- NFL only for now.")
        return

    sport = args[0].lower()
    team_query = " ".join(args[1:]).strip()

    async with ctx.typing():
        try:
            all_transactions = await _get_cached_transactions(sport)
        except Exception as e:
            log.exception(f"Failed to fetch {sport.upper()} transactions")
            await ctx.send(f"Couldn't reach ESPN's transactions feed right now ({_err(e)}).")
            return

        try:
            results = transactions.filter_transactions(all_transactions, team_query, category)
            emoji_dict = {"nfl": TEAM_EMOJIS_NFL}.get(sport, {})
            message = format_transactions(category_label, team_query, results, team_emoji_fn=lambda abbr: emoji_dict.get(abbr, ""))
        except Exception as e:
            log.exception(f"Failed to format {sport.upper()} transactions")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

    await ctx.send(message)


@bot.command(name="trades")
@channel_cooldown_unless_staff()
async def trades(ctx: commands.Context, *args: str):

    await _handle_transactions(ctx, args, transactions.TRADE, "Trades")


@bot.command(name="extensions")
@channel_cooldown_unless_staff()
async def extensions(ctx: commands.Context, *args: str):

    await _handle_transactions(ctx, args, transactions.EXTENSION, "Extensions")


@bot.command(name="signings")
@channel_cooldown_unless_staff()
async def signings(ctx: commands.Context, *args: str):

    await _handle_transactions(ctx, args, transactions.SIGNING, "Signings")


@bot.command(name="releases")
@channel_cooldown_unless_staff()
async def releases(ctx: commands.Context, *args: str):

    await _handle_transactions(ctx, args, transactions.RELEASE, "Releases")


@bot.command(name="standings")
@channel_cooldown_unless_staff()
async def standings(ctx: commands.Context, *args: str):

    remaining = list(args)
    sport = "mlb"
    if remaining and remaining[0].lower() in ("mlb", "nfl"):
        sport = remaining[0].lower()
        remaining = remaining[1:]

    if sport != "mlb":
        await ctx.send(f"`{sport.upper()}` standings aren't built yet -- MLB only for now.")
        return

    league = "both"
    if remaining and remaining[0].lower() in ("al", "nl"):
        league = remaining[0].lower()
        remaining = remaining[1:]

    season = remaining[0] if remaining else None

    async with ctx.typing():
        try:
            standings_data = await mlb_stats_api.get_standings(season=season, league=league)
        except Exception as e:
            log.exception("Failed to fetch standings")
            await ctx.send(f"Couldn't reach MLB's standings right now ({_err(e)}).")
            return

        try:
            teams = await mlb_stats_api.get_teams()
            team_abbr_map = {t["id"]: t["abbreviation"] for t in teams if t.get("id")}
        except Exception:
            log.exception("Failed to fetch team abbreviation map (non-fatal, emojis may be missing)")
            team_abbr_map = {}

        try:
            message = format_mlb_standings(standings_data, team_abbr_map)
        except Exception as e:
            log.exception("Failed to format standings")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return


    if len(message) <= 1900:
        await ctx.send(message)
        return
    chunk = ""
    for line in message.split("\n"):
        if len(chunk) + len(line) + 1 > 1900:
            await ctx.send(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await ctx.send(chunk)


@bot.command(name="box")
@channel_cooldown_unless_staff()
async def box(ctx: commands.Context, *args: str):

    parsed = await _parse_score_style_args(ctx, args, "box")
    if parsed is None:
        return
    sport, team_query, date_arg, date_display, game_number = parsed
    await _dispatch_score(ctx, sport, team_query, date_arg, date_display, mode="box", game_number=game_number)


@bot.command(name="newscast")
@channel_cooldown_unless_staff()
async def newscast(ctx: commands.Context, *args: str):

    if not args:
        await ctx.send("Usage: `-newscast score <team>` (e.g. `-newscast score astros`)")
        return

    subcommand = args[0].lower()
    if subcommand != "score":
        await ctx.send(f"`-newscast {subcommand}` isn't built yet -- only `-newscast score <team>` works right now.")
        return

    parsed = await _parse_score_style_args(ctx, args[1:], "newscast score")
    if parsed is None:
        return
    sport, team_query, date_arg, date_display, game_number = parsed
    await _dispatch_score(ctx, sport, team_query, date_arg, date_display, mode="newscast", game_number=game_number)


def _cfb_record_through_game(team_name: str, season_games: list[dict], up_to_game: dict) -> str:

    game_date = up_to_game.get("startDate", "")
    wins = losses = 0
    for g in season_games:
        if not g.get("completed"):
            continue
        if g.get("startDate", "") > game_date:
            continue
        is_home = g.get("homeTeam") == team_name
        team_pts = g.get("homePoints") if is_home else g.get("awayPoints")
        opp_pts = g.get("awayPoints") if is_home else g.get("homePoints")
        if team_pts is None or opp_pts is None:
            continue
        if team_pts > opp_pts:
            wins += 1
        elif team_pts < opp_pts:
            losses += 1
    return f"{wins}-{losses}"


async def _supplement_cfb_live_data(game: dict, away_name: str, home_name: str, date_arg) -> None:

    try:
        espn_date = None
        if date_arg:
            espn_date = date_arg.replace("-", "")
        scoreboard = await espn_api.get_scoreboard("cfb", date=espn_date)
        events = scoreboard.get("events", [])
        log.info(f"[CFB live] ESPN scoreboard for date={espn_date!r} has {len(events)} events")

        event = espn_api.find_event_for_team(scoreboard, away_name) or espn_api.find_event_for_team(scoreboard, home_name)
        if event is None:
            log.info(f"[CFB live] No ESPN event matched '{away_name}' or '{home_name}'")
            return

        comp = event.get("competitions", [{}])[0]
        status_type = comp.get("status", {}).get("type", {})
        state = status_type.get("state")
        log.info(f"[CFB live] Matched ESPN event, state={state!r}")
        if state != "in":
            return

        competitors = comp.get("competitors", [])
        log.info(f"[CFB live] competitors: {[(c.get('team', {}).get('displayName'), c.get('score')) for c in competitors]}")
        for c in competitors:
            team_name = c.get("team", {}).get("displayName", "")
            score = c.get("score")
            if score is None:
                continue
            try:
                score_val = int(score)
            except (ValueError, TypeError):
                continue
            if away_name.lower() in team_name.lower() or team_name.lower() in away_name.lower():
                game["awayPoints"] = score_val
            elif home_name.lower() in team_name.lower() or team_name.lower() in home_name.lower():
                game["homePoints"] = score_val

        live_label = _nfl_quarter_label(comp.get("status", {}))
        log.info(f"[CFB live] live_label={live_label!r}, injected game state: awayPoints={game.get('awayPoints')}, homePoints={game.get('homePoints')}")
        if live_label:
            game["_liveStatus"] = live_label


        try:
            event_id = event.get("id")
            summary = await espn_api.get_summary("cfb", event_id)
            live_lines = []
            for c in competitors:
                abbr = c.get("team", {}).get("abbreviation", "")
                espn_team_name = c.get("team", {}).get("displayName", "")
                team_block = _espn_team_boxscore_block(summary, abbr)
                if not team_block:
                    continue


                cfbd_style_name = away_name if away_name.lower() in espn_team_name.lower() else home_name
                emoji = _cfb_team_emoji(cfbd_style_name)
                qb_result = _nfl_qb_line(team_block, emoji)
                starter_key = None
                if qb_result:
                    qb_line, starter_key = qb_result
                    live_lines.append(qb_line)
                td_entries = sorted(_nfl_touchdown_entries(team_block, emoji, starter_key), key=lambda t: t[0])
                live_lines.extend(line for _, line in td_entries)
            log.info(f"[CFB live] live box score lines: {len(live_lines)}")
            if live_lines:
                game["_liveBoxScoreLines"] = live_lines
        except Exception:
            log.exception("Failed to fetch ESPN live box score for CFB game (non-fatal, score/status still shown)")
    except Exception:
        log.exception("Failed to fetch ESPN live data for CFB game (non-fatal, showing CFBD data as-is)")


async def _handle_cfb_score(ctx, team_query: str, date_arg, date_display, mode: str = "score"):
    async with ctx.typing():
        year = int(date_arg[:4]) if date_arg else datetime.now().year
        try:
            games = await cfbd_api.get_team_games(team_query, year)
        except Exception as e:
            log.exception("Failed to fetch CFB games")
            await ctx.send(f"Couldn't reach CollegeFootballData right now ({_err(e)}).")
            return

        target_date = date_arg or datetime.now().strftime("%Y-%m-%d")
        game = cfbd_api.find_game_on_date(games, target_date)
        if game is None:
            when = f"on {date_display}" if date_display else "today"
            await ctx.send(
                f"Couldn't find a game for **{team_query}** {when}. "
                f"Check the spelling/date, or the team may not have played that day."
            )
            return

        away_name = game.get("awayTeam", "")
        home_name = game.get("homeTeam", "")
        try:


            away_games = games if away_name.lower() == team_query.strip().lower() else await cfbd_api.get_team_games(away_name, year)
            home_games = games if home_name.lower() == team_query.strip().lower() else await cfbd_api.get_team_games(home_name, year)
            game["awayRecord"] = _cfb_record_through_game(away_name, away_games, game)
            game["homeRecord"] = _cfb_record_through_game(home_name, home_games, game)
        except Exception:
            log.exception("Failed to compute CFB records (non-fatal, showing without records)")

        try:
            game["awayFullName"] = await cfbd_api.get_team_full_name(away_name)
            game["homeFullName"] = await cfbd_api.get_team_full_name(home_name)
        except Exception:
            log.exception("Failed to resolve CFB team full names (non-fatal, falling back to school name only)")


        if not game.get("completed"):
            kickoff_str = game.get("startDate", "")
            try:
                kickoff_dt = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
                past_kickoff = datetime.now(kickoff_dt.tzinfo) >= kickoff_dt
                log.info(f"[CFB live] kickoff={kickoff_str!r}, past_kickoff={past_kickoff}")
                if past_kickoff:
                    await _supplement_cfb_live_data(game, away_name, home_name, target_date)
            except (ValueError, TypeError):
                log.exception(f"[CFB live] Failed to parse kickoff time {kickoff_str!r}")

        player_stats = None
        if mode in ("box", "newscast"):
            try:
                player_stats = await cfbd_api.get_game_player_stats(year, game.get("week"), team_query)
            except Exception:
                log.exception("Failed to fetch CFB player stats (non-fatal, showing score only)")
                player_stats = None

        try:
            formatter = _formatter_dict(mode)["cfb"]
            message = formatter(game) if mode == "score" else formatter(game, player_stats)
        except Exception as e:
            log.exception("Failed to format CFB game")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

    await ctx.send(message)


async def _handle_espn_score(ctx, sport: str, team_query: str, date_arg, date_display, mode: str = "score"):

    async with ctx.typing():
        try:
            scoreboard = await espn_api.get_scoreboard(sport, date=date_arg)
        except Exception as e:
            log.exception(f"Failed to fetch {sport.upper()} scoreboard")
            await ctx.send(f"Couldn't reach ESPN's scoreboard right now ({_err(e)}).")
            return

        event = espn_api.find_event_for_team(scoreboard, team_query)
        if event is None:
            when = f"on {date_display}" if date_display else "today"
            await ctx.send(
                f"Couldn't find a game for **{team_query}** {when}. "
                f"Check the spelling/date, or the team may not have played that day."
            )
            return

        event_id = event.get("id")
        try:
            summary = await espn_api.get_summary(sport, event_id)
        except Exception as e:
            log.exception(f"Failed to fetch {sport.upper()} summary")
            await ctx.send(f"Found the game but couldn't fetch the box score ({_err(e)}).")
            return


        if mode in ("box", "newscast"):
            try:
                competitors = summary.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
                team_ids = [c.get("team", {}).get("id") for c in competitors if c.get("team", {}).get("id")]
                position_map = {}
                for team_id in team_ids:
                    roster_data = await espn_api.get_team_roster(sport, team_id)
                    position_map.update(espn_api.build_roster_position_map(roster_data))
                summary["_playerPositions"] = position_map
            except Exception:
                log.exception(f"Failed to fetch {sport.upper()} rosters for position lookup (non-fatal, falls back to guessing)")

        try:
            formatter = _formatter_dict(mode)[sport]
            message = formatter(summary)
        except Exception as e:
            log.exception(f"Failed to format {sport.upper()} game")
            await ctx.send(f"Found the data but hit an error formatting it ({_err(e)}).")
            return

    await ctx.send(message)


@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    text = (
        "**Volocord Bot -- Commands**\n"
        "\n"
        "**Scores** (score only -- no stats)\n"
        "`-score <team>` -- today's MLB game for that team\n"
        "`-score <team> <date>` -- a past (or future) MLB game, e.g. `-score astros 1986-10-25`\n"
        "`-score nfl <team> [date]` -- NFL, e.g. `-score nfl texans`\n"
        "`-score nba <team> [date]` -- NBA, e.g. `-score nba lakers`\n"
        "`-score cfb <team> [date]` -- college football (FBS), e.g. `-score cfb texas`\n"
        "\n"
        "**Box scores** (same as -score, plus player stats)\n"
        "`-box <team> [date]` -- MLB, e.g. `-box pirates 7/22`\n"
        "`-box nfl <team> [date]` -- NFL, e.g. `-box nfl texans 1/6/2024`\n"
        "`-box nba <team> [date]` -- NBA, e.g. `-box nba lakers`\n"
        "`-box cfb <team> [date]` -- college football, e.g. `-box cfb texas`\n"
        "\n"
        "**Newscast style** (bolded records/winning score/stats)\n"
        "`-newscast score <team> [date]` -- MLB\n"
        "`-newscast score nfl <team> [date]` -- NFL, e.g. `-newscast score nfl texans 12/27/2025`\n"
        "`-newscast score nba <team> [date]` -- NBA\n"
        "`-newscast score cfb <team> [date]` -- college football\n"
        "\n"
        "**MLB extras**\n"
        "`-lineups <team> [date]` -- starting lineup (1-9)\n"
        "`-probablepitchers <team> [date]` -- probable starting pitchers\n"
        "`-standings [al|nl] [season]` -- MLB standings by league/division\n"
        "`-stats mlb <player name>` -- current-season stats, e.g. `-stats mlb Yordan Alvarez`\n"
        "`-trades nfl [team]` -- trades so far this season\n"
        "`-extensions nfl [team]` -- contract extensions so far this season\n"
        "`-signings nfl [team]` -- free-agent signings so far this season\n"
        "`-releases nfl [team]` -- waivers/cuts/releases so far this season\n"
        "\n"
        "**Utility**\n"
        "`-checkscores <mlb|nfl|nba> [date]` -- lists games not yet posted in #scores\n"
        "`-listemojis` -- dumps this server's custom emoji codes\n"
        "`-listroles` -- dumps this server's role IDs\n"
        "`-dm @user1 @user2 <message>` -- DMs the message to those users (staff-only)\n"
        "`-msg #channel <message>` -- sends the message to that channel as the bot (staff-only)\n"
        "`-ndg` -- fupa\n"
        "`-help` -- this message\n"
        "\n"
        "Dates accept: `7/15`, `7/15/2026`, `2026-07-15`, `yesterday`, `today`.\n"
        "MLB doubleheaders: add `game1`/`game2` after the date to pick which game "
        "(e.g. `-score pirates 7/22 game2`) -- defaults to Game 1 and mentions Game 2 if there is one.\n"
        "Helpers/Moderators/Admins skip the 30s cooldown on the commands above."
    )
    await ctx.send(text)


def _parse_generic_date(text: str):

    text = text.strip().lower()
    today = datetime.now(ZoneInfo("America/New_York")).date()
    if text == "today":
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m/%d"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%m/%d":
            parsed = parsed.replace(year=today.year)
            if parsed.date() > today:
                parsed = parsed.replace(year=today.year - 1)
        return parsed.date()
    return None


async def _mlb_matchups(schedule: dict) -> list[tuple[str, str, str, str]]:

    matchups = []
    for date_block in schedule.get("dates", []):
        for game in date_block.get("games", []):
            teams = game.get("teams", {})
            away_team = teams.get("away", {}).get("team", {})
            home_team = teams.get("home", {}).get("team", {})
            away, home = away_team.get("name", ""), home_team.get("name", "")
            if not (away and home):
                continue
            away_abbr = await mlb_stats_api.team_abbr(away_team.get("id"))
            home_abbr = await mlb_stats_api.team_abbr(home_team.get("id"))
            matchups.append((away, home, away_abbr, home_abbr))
    return matchups


def _nfl_matchups(scoreboard: dict) -> list[tuple[str, str, str, str]]:
    matchups = []
    for event in scoreboard.get("events", []):
        comps = event.get("competitions", [{}])[0].get("competitors", [])
        if len(comps) < 2:
            continue
        away = next((c for c in comps if c.get("homeAway") == "away"), comps[0])
        home = next((c for c in comps if c.get("homeAway") == "home"), comps[-1])
        away_name = away.get("team", {}).get("displayName", "")
        home_name = home.get("team", {}).get("displayName", "")
        away_abbr = away.get("team", {}).get("abbreviation", "")
        home_abbr = home.get("team", {}).get("abbreviation", "")
        if away_name and home_name:
            matchups.append((away_name, home_name, away_abbr, home_abbr))
    return matchups


def _nba_matchups(scoreboard: dict) -> list[tuple[str, str, str, str]]:
    matchups = []
    for row in nba_stats_api.get_rows(scoreboard, "GameHeader"):
        home_id = row.get("HOME_TEAM_ID")
        away_id = row.get("VISITOR_TEAM_ID")
        home_city, home_nick = nba_stats_api.TEAM_ID_TO_NAME.get(home_id, ("", ""))
        away_city, away_nick = nba_stats_api.TEAM_ID_TO_NAME.get(away_id, ("", ""))
        home_name = f"{home_city} {home_nick}".strip()
        away_name = f"{away_city} {away_nick}".strip()
        home_abbr = nba_stats_api.TEAM_ID_TO_ABBR.get(home_id, "")
        away_abbr = nba_stats_api.TEAM_ID_TO_ABBR.get(away_id, "")
        if away_name and home_name:
            matchups.append((away_name, home_name, away_abbr, home_abbr))
    return matchups


def _cfb_matchups(games: list[dict]) -> list[tuple[str, str, str, str]]:

    matchups = []
    for game in games:
        if game.get("homeClassification") != "fbs" or game.get("awayClassification") != "fbs":
            continue
        away_name = game.get("awayTeam", "")
        home_name = game.get("homeTeam", "")
        if away_name and home_name:
            matchups.append((away_name, home_name, away_name, home_name))
    return matchups


_CHECKSCORES_EMOJI_DICTS = {"mlb": TEAM_EMOJIS, "nfl": TEAM_EMOJIS_NFL, "nba": TEAM_EMOJIS_NBA, "cfb": TEAM_EMOJIS_CFB}


@bot.command(name="checkscores")
@channel_cooldown_unless_staff()
async def checkscores(ctx: commands.Context, *args: str):

    if not args or args[0].lower() not in ("mlb", "nfl", "nba", "cfb"):
        await ctx.send("Usage: `-checkscores <mlb|nfl|nba|cfb> [date]` (e.g. `-checkscores mlb` or `-checkscores nfl 7/22`)")
        return

    sport = args[0].lower()
    remaining = list(args[1:])

    target_date = datetime.now(ZoneInfo("America/New_York")).date()
    date_display = "today"
    if remaining:
        parsed = _parse_generic_date(remaining[-1])
        if parsed:
            target_date = parsed
            date_display = remaining[-1]

    channel = ctx.guild.get_channel(SCORES_CHANNEL_ID)
    if channel is None:


        channel = next((c for c in ctx.guild.text_channels if "scores" in c.name.lower()), None)
    if channel is None:
        await ctx.send("Couldn't find the #scores channel in this server.")
        return

    async with ctx.typing():
        try:
            if sport == "mlb":
                schedule = await mlb_stats_api.get_schedule(date=target_date.strftime("%Y-%m-%d"))
                matchups = await _mlb_matchups(schedule)
            elif sport == "nfl":
                scoreboard = await espn_api.get_scoreboard("nfl", date=target_date.strftime("%Y%m%d"))
                matchups = _nfl_matchups(scoreboard)
            elif sport == "cfb":
                season_games = await cfbd_api.get_all_games_for_season(target_date.year)
                day_games = cfbd_api.find_games_on_date(season_games, target_date.strftime("%Y-%m-%d"))
                matchups = _cfb_matchups(day_games)
            else:
                scoreboard = await nba_stats_api.get_scoreboard(date=target_date.strftime("%m/%d/%Y"))
                matchups = _nba_matchups(scoreboard)
        except Exception as e:
            log.exception("Failed to fetch schedule for checkscores")
            await ctx.send(f"Couldn't reach {sport.upper()}'s schedule right now ({_err(e)}).")
            return

        if not matchups:
            await ctx.send(f"No {sport.upper()} games scheduled for {date_display}.")
            return

        eastern = ZoneInfo("America/New_York")
        start = datetime.combine(target_date, datetime.min.time(), tzinfo=eastern)


        end = min(start + timedelta(days=4), datetime.now(eastern))

        try:
            blob_parts = []
            async for msg in channel.history(after=start, before=end, limit=500):
                blob_parts.append(msg.content.lower())
            blob = "\n".join(blob_parts)
        except discord.Forbidden:
            await ctx.send(
                f"I don't have permission to read message history in {channel.mention}. "
                f"Grant me View Channel + Read Message History there and try again."
            )
            return
        except Exception as e:
            log.exception("Failed to read channel history")
            await ctx.send(f"Couldn't read {channel.mention}'s message history ({_err(e)}).")
            return


        emoji_dict = _CHECKSCORES_EMOJI_DICTS[sport]
        missing = []
        for away, home, away_abbr, home_abbr in matchups:
            away_key = away.split()[-1].lower()
            home_key = home.split()[-1].lower()
            away_emoji = emoji_dict.get(away_abbr, "").lower()
            home_emoji = emoji_dict.get(home_abbr, "").lower()
            away_found = (away_key in blob) or (away_emoji and away_emoji in blob)
            home_found = (home_key in blob) or (home_emoji and home_emoji in blob)
            if not (away_found and home_found):
                missing.append(f"{away} @ {home}")

    if not missing:
        await ctx.send(f"All {len(matchups)} {sport.upper()} game(s) for {date_display} appear to be posted in {channel.mention}.")
    else:
        lines = [f"**Games not yet posted in {channel.mention} ({sport.upper()}, {date_display}):**"]
        lines.extend(f"- {m}" for m in missing)
        await ctx.send("\n".join(lines))


@bot.command(name="ndg")
async def ndg(ctx: commands.Context):
    await ctx.send("fupa")


@bot.command(name="listemojis")
@commands.has_permissions(administrator=True)
async def listemojis(ctx: commands.Context):

    emojis = ctx.guild.emojis
    if not emojis:
        await ctx.send("This server has no custom emojis.")
        return

    lines = [f"{e.name}: {e}" for e in sorted(emojis, key=lambda e: e.name.lower())]

    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 1900:
            await ctx.send(f"```{chunk}```")
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await ctx.send(f"```{chunk}```")


def _staff_check():
    async def predicate(ctx: commands.Context) -> bool:
        if _is_staff(ctx.author):
            return True
        raise commands.MissingPermissions(["staff role"])
    return commands.check(predicate)


@bot.command(name="dm")
@_staff_check()
async def dm(ctx: commands.Context, *, args: str = ""):

    if not ctx.message.mentions:
        await ctx.send("Mention at least one user to DM -- e.g. `-dm @user1 @user2 Here's your invite link: ...`")
        return

    content = args
    for member in ctx.message.mentions:
        content = content.replace(f"<@{member.id}>", "").replace(f"<@!{member.id}>", "")
    content = content.strip()

    if not content:
        await ctx.send("Give me a message to send too -- e.g. `-dm @user1 Here's your Sleeper invite: <link>`")
        return

    sent, failed = [], []
    for member in ctx.message.mentions:
        try:
            await member.send(content)
            sent.append(member.display_name)
        except discord.Forbidden:
            failed.append(member.display_name)
        except Exception:
            log.exception(f"Failed to DM {member.display_name}")
            failed.append(member.display_name)

    result = []
    if sent:
        result.append(f"Sent to: {', '.join(sent)}")
    if failed:
        result.append(f"Couldn't reach (their DMs may be closed to server members): {', '.join(failed)}")
    await ctx.send("\n".join(result))


@bot.command(name="msg")
@_staff_check()
async def msg(ctx: commands.Context, *, args: str = ""):

    if not ctx.message.channel_mentions:
        await ctx.send("Mention a channel too -- e.g. `-msg #general hello!`")
        return

    channel = ctx.message.channel_mentions[0]
    content = args
    for ch in ctx.message.channel_mentions:
        content = content.replace(f"<#{ch.id}>", "")
    content = content.strip()

    if not content:
        await ctx.send("Give me a message to send too -- e.g. `-msg #general hello!`")
        return

    try:
        await channel.send(content)
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to send messages in {channel.mention}.")
        return
    except Exception as e:
        log.exception("Failed to send message to channel")
        await ctx.send(f"Couldn't send that message ({_err(e)}).")
        return

    await ctx.send(f"Sent to {channel.mention}.")


@bot.command(name="listroles")
@commands.has_permissions(administrator=True)
async def listroles(ctx: commands.Context):

    roles = ctx.guild.roles
    if not roles:
        await ctx.send("This server has no roles.")
        return

    lines = [f"{r.name}: {r.id}" for r in sorted(roles, key=lambda r: r.name.lower())]
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 1900:
            await ctx.send(f"```{chunk}```")
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await ctx.send(f"```{chunk}```")


def _handle_loop_exception(loop, context):

    exception = context.get("exception")
    message = context.get("message", "no message")
    log.error(f"Unhandled exception in event loop: {message}", exc_info=exception)


async def _run_bot(token: str) -> None:
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Set the DISCORD_BOT_TOKEN environment variable before running the bot."
        )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(_handle_loop_exception)
    try:
        loop.run_until_complete(_run_bot(token))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
