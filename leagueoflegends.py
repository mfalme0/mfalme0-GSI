import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LIVE_CLIENT_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
_LOCAL_GAME_SSL_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_LOCAL_GAME_SSL_CONTEXT.check_hostname = False
_LOCAL_GAME_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def health_color(game_data):
    """Return an RGB color and status derived from LoL Live Client Data."""
    active_player = game_data.get("activePlayer", {})
    champion_stats = active_player.get("championStats", {})
    health = champion_stats.get("currentHealth")
    max_health = champion_stats.get("maxHealth")
    if not isinstance(health, (int, float)) or not isinstance(max_health, (int, float)) or max_health <= 0:
        return (80, 130, 190), "League of Legends · In game"
    ratio = max(0.0, min(1.0, health / max_health))
    if health <= 0:
        color = (255, 0, 0)
    elif ratio < 0.25:
        color = (255, 28, 28)
    elif ratio < 0.5:
        color = (255, 150, 0)
    else:
        color = (int(24 + 24 * (1 - ratio)), int(100 + 155 * ratio), 48)
    player_name = active_player.get("summonerName", "Player")
    return color, f"{player_name} · {int(health)}/{int(max_health)} HP"


def fetch_live_data(timeout=2.0):
    request = Request(LIVE_CLIENT_URL, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout, context=_LOCAL_GAME_SSL_CONTEXT) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("League of Legends response exceeded the 2 MB limit")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("League of Legends returned an unexpected response")
    return data


__all__ = ["HTTPError", "URLError", "fetch_live_data", "health_color"]
