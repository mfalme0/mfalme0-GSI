def health_color(gsi_data):
    """Return an RGB color and a short status label for a Dota 2 GSI payload."""
    hero = gsi_data.get("hero", {})
    health = hero.get("health")
    max_health = hero.get("max_health")
    if isinstance(health, (int, float)) and isinstance(max_health, (int, float)) and max_health > 0:
        ratio = max(0.0, min(1.0, health / max_health))
        if health <= 0:
            color = (255, 0, 0)
        elif ratio < 0.25:
            color = (255, 32, 24)
        elif ratio < 0.5:
            color = (255, 150, 0)
        else:
            color = (int(24 + 24 * (1 - ratio)), int(100 + 155 * ratio), 48)
        return color, f"{hero.get('name', 'Hero')} · {int(health)}/{int(max_health)} HP"

    game_state = gsi_data.get("map", {}).get("game_state", "Waiting for game")
    return (90, 110, 160), str(game_state).replace("DOTA_GAMERULES_STATE_", "").replace("_", " ").title()
