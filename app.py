#!/usr/bin/python
# coding: utf-8

"""This app contains endpoints to calculate shared Steam games."""

import os

import requests
from flask import Flask
from flask import g
from flask import jsonify
from flask import render_template
from flask import request as flask_request


__version__ = "1.4.0"


_cache = {}

def cached(func):
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)
        try:
            result = _cache[key]
        except KeyError:
            result = func(*args, **kwargs)
            _cache[key] = result
        return result
    return wrapper


def get_steam_api_key():
    """Get the API key either from OS keyring or from env variable.

    The latter overwrites the first.
    """
    key = None
    try:
        import keyring
        key = keyring.get_password("steamwhat", "api_key")
    except ImportError:
        pass
    key = os.environ.get("STEAM_API_KEY", key)
    if key is not None:
        return key
    raise RuntimeError("Must configure a Steam API Key")


STEAM_API_KEY = get_steam_api_key()

# See: http://steamwebapi.azurewebsites.net/
endpoints = {
    "get_owned_games": {
        "url": "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1",
        "params": [
            "key",
            "steamid",
        ],
    },
    "get_app_list": {
        "url": "http://api.steampowered.com/ISteamApps/GetAppList/v2",
    },
    "get_player_summaries": {
        "url": "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2",
        "params": [
            "key",
            "steamids",
        ],
    },
}


def get_player_summaries(steamids):
    """Return details for multiple players."""
    params = {
        "key": STEAM_API_KEY,
        "steamids": ",".join([str(steamid) for steamid in steamids]),
    }
    response = requests.get(endpoints["get_player_summaries"]["url"],
                            params=params)
    return response.json()["response"]["players"]


def get_appid_to_name_map():
    """Return a map from app id to app name for all apps on Steam."""
    response = requests.get(endpoints["get_app_list"]["url"])
    apps = response.json()["applist"]["apps"]
    appid_to_name = {}
    for app in apps:
        appid_to_name[app["appid"]] = app["name"]
    return appid_to_name


def get_games(steamid):
    """Return owned games for player."""
    params = {
        "key": STEAM_API_KEY,
        "steamid": steamid,
    }
    response = requests.get(endpoints["get_owned_games"]["url"],
                            params=params)
    games = response.json()["response"]["games"]
    return games


def get_player_by_steamid(steamid):
    """Return details on the player assocated with the steam id."""
    for player in g.player_summaries:
        if player["steamid"] == str(steamid):
            return player
    return None


def get_player_reports(steamids):
    """Return a list of player reports.

    Each report contains the player name and a list of owned app ids.
    If a steam id does not result in a player report, ignore it.
    """
    player_reports = []
    for steamid in steamids:
        try:
            raw_games = get_games(steamid)
            appids = set([raw_game["appid"] for raw_game in raw_games])
            player = get_player_by_steamid(steamid)
            player_report = {
                "steamid": steamid,
                "appids": appids,
                "name": player["personaname"],
            }
            player_reports.append(player_report)
        except ValueError:
            pass
    return player_reports


def get_shared_games_report(steamids):
    """Return a JSON containing identified players and a list shared games."""
    # Prepare some lookups shared over the request lifetime.
    g.player_summaries = get_player_summaries(steamids)
    g.appid_to_name = get_appid_to_name_map()

    player_reports = get_player_reports(steamids)
    player_appids = [set(player["appids"]) for player in player_reports]
    shared_appids = set.intersection(*player_appids)

    players = []
    for report in player_reports:
        report.pop("appids")
        players.append(report)
    players.sort(key=lambda player: player["name"].lower())

    shared_games = []
    for appid in shared_appids:
        shared_games.append({
            "name": g.appid_to_name[appid],
            "appid": appid
        })
    shared_games.sort(key=lambda game: game["name"].lower())

    return jsonify(players=players, shared_games=shared_games)


def parse_steamids_from_query():
    raw_steamids = flask_request.args.get("steamids")
    if raw_steamids is None:
        raise ValueError("ERROR: No steam ids specified")
    try:
        steamids = [str(raw).strip() for raw in raw_steamids.split(",")]
        steamids = list(set(steamids))
    except ValueError:
        raise ValueError("ERROR: Steam ids are malformed")
    return steamids


app = Flask(__name__)


@app.route('/players')
def players():
    """Get a list of Steam IDs and return a list of players.

    Each player has a steam ID and a name. If a steam ID fails being
    looked up, ignore it and continue fetching other players.

    Query Params:
        steamids (str): Comma-separated list of steam ids, each
            identifying a player.

    Returns:
        json

    Example use:
        /?steamids=12345,6789

    Example result:
        [
            {"steamid": 12345, "name": "spamlord84"},
            ...
        ]
    """
    steamids = parse_steamids_from_query()
    try:
        g.player_summaries = get_player_summaries(steamids)
        players = []
        for steamid in steamids:
            try:
                player = get_player_by_steamid(steamid)
                if player is not None:
                    players.append({
                        "name": player["personaname"],
                        "steamid": player["steamid"],
                    })
            except Exception:
                pass
    except Exception as err:
        return "ERROR: " + str(err), 500
    return jsonify(players)


@app.route('/sharedgames')
def shared_games_report():
    """Return which games are shared between the players.

    Query Params:
        steamids (str): Comma-separated list of steam ids, each
            identifying a player.

    Returns:
        json

    Example use:
        /?steamids=12345,6789

    Example result:
        {
            "players": [
                {"name": "Gabe", "steamid": 123},
                {"name": "John", "steamid": 456},
                ...
            ],
            "shared_games": [
                {"name": "Half Life", "appid": 10},
                {"name": "Age of Empires II", "appid": 642},
                ...
            ],
        }
    """
    steamids = parse_steamids_from_query()
    try:
        result = get_shared_games_report(steamids)
    except Exception as err:
        return "ERROR: " + str(err), 500
    return result


@app.route('/')
def client():
    return render_template("client.html")


if __name__ == "__main__":
    app.run(debug=True)
