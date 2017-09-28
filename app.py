#!/usr/bin/python
# coding: utf-8

"""This app contains a single endpoint/URL to calculate shared Steam games."""

import os

import requests
from flask import Flask
from flask import g
from flask import jsonify
from flask import request as flask_request


def get_steam_api_key():
    """Get the API key either from OS keyring or from env variable.

    The latter overwrites the first.
    """
    try:
        import keyring
        key = keyring.get_password("steamwhat", "api_key")
    except ImportError:
        pass
    key = os.environ.get("STEAM_API_KEY", None)
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

    shared_games = []
    for appid in shared_appids:
        shared_games.append({
            "name": g.appid_to_name[appid],
            "appid": appid
        })

    return jsonify(players=players, shared_games=shared_games)


app = Flask(__name__)


@app.route('/')
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
    raw_steamids = flask_request.args.get("steamids")
    if raw_steamids is None:
        return "ERROR: No steam ids specified", 400
    try:
        steamids = [int(raw) for raw in raw_steamids.split(",")]
    except ValueError:
        return "ERROR: Steam ids are malformed", 400
    try:
        result = get_shared_games_report(steamids)
    except Exception as err:
        return "ERROR: " + str(err), 500
    return result


if __name__ == "__main__":
    app.run(debug=True)
