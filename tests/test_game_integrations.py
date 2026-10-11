import http.client
import json
import threading
import unittest
from http.server import HTTPServer

from beamng import OUTGAUGE_PACKET, parse_outgauge_packet
from cs2rgb import create_handler
from dota2 import health_color as dota_health_color
from leagueoflegends import health_color as lol_health_color
from rocketleague import color_for_event, decode_event, extract_json_messages


class TelemetryTests(unittest.TestCase):
    def test_beamng_outgauge_packet(self):
        packet = OUTGAUGE_PACKET.pack(
            1, b"beam", 0, 2, 0, 10.0, 2500.0, 0.0, 90.0, 1.0, 0.0, 90.0,
            0, 0, 0.5, 0.0, 0.0, b"", b"", 0,
        )
        self.assertEqual(parse_outgauge_packet(packet), (36, 2500, 2))
        self.assertEqual(parse_outgauge_packet(packet[:20]), (None, None, None))

    def test_rocket_stream_handles_partial_and_concatenated_objects(self):
        first = json.dumps({"Event": "UpdateState", "Data": "{\"Players\":[]}"})
        second = json.dumps({"Event": "GoalScored", "Data": "{\"Scorer\":{\"Name\":\"Test\"}}"})
        messages, remainder = extract_json_messages(first[:12])
        self.assertEqual(messages, [])
        messages, remainder = extract_json_messages(remainder + first[12:] + second)
        self.assertEqual(len(messages), 2)
        self.assertEqual(remainder, "")
        event, data = decode_event(messages[1])
        self.assertEqual(event, "GoalScored")
        self.assertEqual(data["Scorer"]["Name"], "Test")
        self.assertEqual(color_for_event(event, data)[1], "Goal scored · Test")

    def test_rocket_boost_color_clamps_input(self):
        color, label = color_for_event(
            "UpdateState",
            {"Players": [{"Name": "Player", "Boost": 150}]},
        )
        self.assertEqual(color, (45, 220, 32))
        self.assertIn("Boost 100%", label)


class GameStateTests(unittest.TestCase):
    def test_dota_and_lol_low_health_colors(self):
        dota_color, dota_label = dota_health_color(
            {"hero": {"name": "Invoker", "health": 20, "max_health": 100}}
        )
        lol_color, lol_label = lol_health_color(
            {
                "activePlayer": {
                    "summonerName": "Summoner",
                    "championStats": {"currentHealth": 20, "maxHealth": 100},
                }
            }
        )
        self.assertEqual(dota_color, (255, 32, 24))
        self.assertEqual(lol_color, (255, 28, 28))
        self.assertIn("Invoker", dota_label)
        self.assertIn("Summoner", lol_label)

    def test_dota_gsi_requires_token_and_calls_handler(self):
        received = []
        server = HTTPServer(
            ("127.0.0.1", 0),
            create_handler("test-token", received.append, token_field="token"),
        )
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            def post(payload):
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_address[1], timeout=2
                )
                connection.request("POST", "/", json.dumps(payload))
                response = connection.getresponse()
                response.read()
                connection.close()
                return response.status

            self.assertEqual(post({"auth": {"token": "bad"}}), 403)
            self.assertEqual(received, [])
            self.assertEqual(
                post({"auth": {"token": "test-token"}, "hero": {"health": 1}}),
                200,
            )
            self.assertEqual(len(received), 1)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
