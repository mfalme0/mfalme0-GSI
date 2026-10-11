import json


MAX_BUFFER_CHARS = 2_000_000


def extract_json_messages(buffer):
    """Split concatenated JSON objects from a Rocket League TCP stream buffer."""
    decoder = json.JSONDecoder()
    messages = []
    position = 0
    length = len(buffer)
    while position < length:
        while position < length and buffer[position].isspace():
            position += 1
        if position == length:
            return messages, ""
        if buffer[position] != "{":
            raise ValueError("Unexpected data before a Rocket League JSON message")
        try:
            message, end = decoder.raw_decode(buffer, position)
        except json.JSONDecodeError:
            remainder = buffer[position:]
            if len(remainder) > MAX_BUFFER_CHARS:
                raise ValueError("Rocket League message exceeded the 2 MB limit")
            return messages, remainder
        if not isinstance(message, dict):
            raise ValueError("Expected a Rocket League JSON object")
        messages.append(message)
        position = end
    return messages, ""


def decode_event(envelope):
    """Normalize the Stats API envelope, whose Data field may be JSON text."""
    event_name = envelope.get("Event", "")
    data = envelope.get("Data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data) if data else {}
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON in Rocket League event Data") from exc
    if not isinstance(data, dict):
        data = {}
    return str(event_name), data


def color_for_event(event_name, data, player_name=""):
    """Map Rocket League stats/events to an RGB color and human-readable label."""
    if event_name == "GoalScored":
        scorer = data.get("Scorer", {})
        team = scorer.get("TeamNum") if isinstance(scorer, dict) else None
        color = (40, 115, 255) if team == 0 else (255, 130, 24) if team == 1 else (255, 255, 255)
        name = scorer.get("Name", "Goal") if isinstance(scorer, dict) else "Goal"
        return color, f"Goal scored · {name}"

    if event_name == "MatchEnded":
        winner = data.get("WinnerTeamNum")
        if winner in (0, 1):
            color = (40, 115, 255) if winner == 0 else (255, 130, 24)
            return color, "Match ended · Blue wins" if winner == 0 else "Match ended · Orange wins"
        return (220, 220, 220), "Match ended"

    if event_name == "UpdateState":
        players = data.get("Players", [])
        if isinstance(players, list) and players:
            selected = next(
                (
                    player
                    for player in players
                    if player_name
                    and str(player.get("Name", "")).casefold() == player_name.casefold()
                ),
                players[0],
            )
            boost = selected.get("Boost")
            if isinstance(boost, (int, float)):
                level = max(0, min(100, int(boost)))
                color = (255 - int(2.1 * level), 40 + int(1.8 * level), 32)
                return color, f"{selected.get('Name', 'Player')} · Boost {level}%"
            return (40, 160, 255), f"{selected.get('Name', 'Player')} · In match"
        return (40, 160, 255), "Rocket League · Match state"

    if event_name in ("MatchPaused", "MatchDestroyed"):
        return (110, 110, 130), "Match paused" if event_name == "MatchPaused" else "Match ended"
    return (60, 135, 220), event_name.replace("Updated", " updated").strip() or "Rocket League"
