#!/usr/bin/env python3
"""External media player configuration for AI-NAS (Feature A8).

Provides configurable URL templates for Jellyfin, Plex, Emby, and generic players.
Config via env vars or a JSON config file.
"""

from __future__ import annotations

import json, os
from pathlib import Path

DEFAULT_CONFIG = {
    "players": {
        "jellyfin": {
            "name": "Jellyfin",
            "base_url": "http://localhost:8096",
            "web_player_template": "{base_url}/web/#/details?id={media_id}",
            "direct_stream_template": "{base_url}/Videos/{media_id}/stream?Static=true",
        },
        "plex": {
            "name": "Plex",
            "base_url": "http://localhost:32400",
            "web_player_template": "{base_url}/web/index.html#!/server/{server_id}/details?key={media_id}",
        },
        "emby": {
            "name": "Emby",
            "base_url": "http://localhost:8096",
            "web_player_template": "{base_url}/web/#/item?id={media_id}",
        },
        "vlc": {
            "name": "VLC (Local)",
            "base_url": "",
            "web_player_template": "vlc://{file_path}",
        },
    },
    "default_player": "jellyfin",
}

_CONFIG_PATH = Path(os.environ.get("AI_NAS_PLAYER_CONFIG", str(Path(__file__).resolve().parents[2] / "configs" / "external_player.json")))


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            _deep_merge(cfg, user_cfg)
        except Exception:
            pass
    return cfg


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def get_player_url(media_type: str, media_id: str = "", file_path: str = "", player: str = "") -> dict:
    """Generate a player URL for a media item.

    Args:
        media_type: "movie", "tv_show", "music", or "photo"
        media_id: Media ID in the external player (e.g., Jellyfin item ID)
        file_path: Local file path for direct-play players (VLC, MPC)
        player: Player key (jellyfin, plex, emby, vlc) or empty for default

    Returns dict with {ok, url, player_name, evidence}
    """
    cfg = load_config()
    player_key = player or cfg.get("default_player", "jellyfin")
    player_cfg = cfg.get("players", {}).get(player_key)

    if not player_cfg:
        return {"ok": False, "url": "", "player_name": player_key, "evidence": {"error": "player_not_configured", "available_players": list(cfg.get("players", {}).keys())}}

    base_url = player_cfg.get("base_url", "")
    template = player_cfg.get("web_player_template", "{base_url}")

    url = template.format(base_url=base_url, media_id=media_id, file_path=file_path, media_type=media_type)

    return {
        "ok": True,
        "url": url,
        "player_name": player_cfg.get("name", player_key),
        "player_key": player_key,
        "media_type": media_type,
        "evidence": {"player": player_key, "template": template, "base_url": base_url},
    }


def list_players() -> dict:
    cfg = load_config()
    players = []
    for key, pcfg in cfg.get("players", {}).items():
        players.append({"key": key, "name": pcfg.get("name", key), "base_url": pcfg.get("base_url", "")})
    return {"ok": True, "default_player": cfg.get("default_player", ""), "players": players}


def config_status() -> dict:
    cfg = load_config()
    return {
        "feature": "A8_external_player",
        "config_file": str(_CONFIG_PATH) if _CONFIG_PATH.exists() else "using_defaults",
        "configured_players": list(cfg.get("players", {}).keys()),
        "default_player": cfg.get("default_player", ""),
    }


if __name__ == "__main__":
    print(json.dumps(config_status(), ensure_ascii=False, indent=2))
    print("\n--- Players ---")
    print(json.dumps(list_players(), ensure_ascii=False, indent=2))
    print("\n--- Example URL ---")
    print(json.dumps(get_player_url("movie", media_id="12345", player="jellyfin"), ensure_ascii=False, indent=2))
