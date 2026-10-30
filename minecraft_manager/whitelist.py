"""Minecraftホワイトリストの読み取り。"""

import json


def read_whitelist_entries(profile):
    whitelist_file = profile.server_directory / "whitelist.json"

    if not whitelist_file.exists():
        return []

    try:
        data = json.loads(whitelist_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    result = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            uuid = str(item.get("uuid", "")).strip()
            if name:
                result.append((name, uuid))

    return sorted(result, key=lambda item: item[0].lower())
