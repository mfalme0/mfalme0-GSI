import getpass
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from openrgb import OpenRGBClient
from openrgb.utils import RGBColor


DEFAULT_GSI_HOST = "127.0.0.1"
DEFAULT_GSI_PORT = 5000
DEFAULT_OPENRGB_HOST = "localhost"
DEFAULT_OPENRGB_PORT = 6745
MAX_GSI_BODY_BYTES = 1_048_576


def get_color(gsi_data, last_known_states):
    player = gsi_data.get("player", {})
    map_data = gsi_data.get("map", {})
    round_data = gsi_data.get("round", {})
    state = player.get("state", {})

    if state.get("flashed", 0) > 0:
        return RGBColor(255, 255, 255), 1.5
    if state.get("burning", 0) > 0:
        return RGBColor(255, 178, 0), 0.6
    if state.get("smoked", 0) > 0:
        return RGBColor(100, 100, 100), 0.6

    activity = player.get("activity", "")
    if activity == "menu":
        phase = map_data.get("phase", "")
        if phase == "loadingscreen":
            return RGBColor(147, 112, 219), None
        if phase == "searching":
            return RGBColor(255, 215, 0), None
        return RGBColor(0, 255, 0), None

    health = state.get("health", 100)
    if health >= 80:
        color = RGBColor(0, 255, 0)
    elif health >= 50:
        color = RGBColor(255, 255, 0)
    elif health >= 20:
        color = RGBColor(255, 165, 0)
    else:
        color = RGBColor(255, 0, 0)
    last_known_states["player_health"] = health

    kills = player.get("match_stats", {}).get("kills", 0)
    if kills > last_known_states["previous_kills"]:
        last_known_states["previous_kills"] = kills
        return RGBColor(145, 200, 66), 0.5
    last_known_states["previous_kills"] = kills

    bomb = round_data.get("bomb")
    if bomb == "planted":
        return RGBColor(0, 224, 245), None
    if bomb == "exploded":
        return RGBColor(255, 200, 0), 1.0

    winning_team = round_data.get("win_team")
    if winning_team == "T":
        return RGBColor(235, 160, 0), None
    if winning_team == "CT":
        return RGBColor(0, 255, 255), None
    return color, None


def create_handler(secret_key, on_update, token_field="key1"):
    class GSIHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                content_length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self.send_error(400, "Invalid Content-Length")
                return
            if content_length < 0 or content_length > MAX_GSI_BODY_BYTES:
                self.send_error(413, "Request body too large")
                return

            try:
                gsi_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_error(400, "Invalid JSON")
                return
            if not isinstance(gsi_data, dict):
                self.send_error(400, "Expected a JSON object")
                return

            auth = gsi_data.get("auth", {})
            if not isinstance(auth, dict):
                self.send_error(403, "Unauthorized")
                return
            received_key = auth.get(token_field, "")
            if not isinstance(received_key, str) or not hmac.compare_digest(received_key, secret_key):
                self.send_error(403, "Unauthorized")
                return

            try:
                on_update(gsi_data)
            except Exception:
                self.send_error(500, "Could not process game state")
                return

            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    return GSIHandler


class OpenRGBGameController:
    def __init__(self, client):
        self.client = client
        self.last_known_states = {"player_health": 100, "previous_kills": 0}
        self._normal_color = RGBColor(255, 0, 255)
        self._flash_timer = None
        self._lock = threading.RLock()

    @property
    def devices(self):
        return self.client.devices

    def update(self, gsi_data):
        color, flash_duration = get_color(gsi_data, self.last_known_states)
        with self._lock:
            if self._flash_timer is not None:
                self._flash_timer.cancel()
                self._flash_timer = None
            if flash_duration is None:
                self._normal_color = color
                self._set_color(color)
            else:
                self._set_color(color)
                self._flash_timer = threading.Timer(flash_duration, self._restore_color)
                self._flash_timer.daemon = True
                self._flash_timer.start()
        return color, flash_duration

    def _restore_color(self):
        with self._lock:
            self._flash_timer = None
            self._set_color(self._normal_color)

    def _set_color(self, color):
        for device in self.devices:
            if any(mode.name.lower() == "direct" for mode in device.modes):
                device.set_mode("Direct")
            device.set_color(color)

    def close(self):
        with self._lock:
            if self._flash_timer is not None:
                self._flash_timer.cancel()
                self._flash_timer = None


def run_server(host=DEFAULT_GSI_HOST, port=DEFAULT_GSI_PORT, secret_key=None):
    secret_key = secret_key or os.environ.get("CS2_GSI_SECRET")
    if not secret_key:
        secret_key = getpass.getpass("Enter the CS2 GSI auth key: ")
    if not secret_key:
        raise ValueError("A CS2 GSI auth key is required.")

    client = OpenRGBClient(
        address=DEFAULT_OPENRGB_HOST,
        port=DEFAULT_OPENRGB_PORT,
        name="FHSensorStudio CS2",
    )
    controller = OpenRGBGameController(client)
    server = HTTPServer((host, port), create_handler(secret_key, controller.update))
    server.timeout = 0.5
    print(f"CS2 GSI listening on http://{host}:{port} ({len(controller.devices)} OpenRGB device(s))")
    try:
        while True:
            server.handle_request()
    except KeyboardInterrupt:
        print("Stopping CS2 GSI bridge.")
    finally:
        server.server_close()
        controller.close()
        client.disconnect()


if __name__ == "__main__":
    run_server()
