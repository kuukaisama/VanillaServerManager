"""アプリで共有するパスと server.properties 操作。"""

import os

from .paths import USER_DATA_DIR, WORLD_VERSION_DIR
from .profiles import create_default_profile


BASE_DIR = USER_DATA_DIR

CONFIG_FILES = (
    "server.properties",
    "whitelist.json",
    "ops.json",
    "banned-players.json",
    "banned-ips.json",
    "usercache.json",
)

AUTO_BACKUP_OPTIONS = {
    "無効": 0,
    "30分": 30 * 60,
    "1時間": 60 * 60,
    "3時間": 3 * 60 * 60,
    "6時間": 6 * 60 * 60,
}


def get_property(name, default=None, profile=None):
    profile = profile or create_default_profile()
    properties_file = profile.server_directory / "server.properties"

    if not properties_file.exists():
        return default

    try:
        with properties_file.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                if key.strip() == name:
                    return value.strip()
    except OSError:
        return default

    return default


def get_level_name(profile=None):
    return get_property("level-name", "world", profile=profile) or "world"


def read_properties_map(profile=None):
    """server.properties を辞書として読み込む。"""
    profile = profile or create_default_profile()
    properties_file = profile.server_directory / "server.properties"
    result = {}

    if not properties_file.exists():
        return result

    try:
        with properties_file.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue

                key, value = stripped.split("=", 1)
                result[key.strip()] = value.strip()
    except OSError:
        pass

    return result


def write_properties(changes, profile=None):
    """既存のコメントや並びをできるだけ維持して設定を書き換える。"""
    profile = profile or create_default_profile()
    properties_file = profile.server_directory / "server.properties"

    if not properties_file.exists():
        raise FileNotFoundError(
            f"server.properties が見つかりません。\n{properties_file}"
        )

    with properties_file.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    remaining = {str(key): str(value) for key, value in changes.items()}
    new_lines = []

    for original_line in lines:
        stripped = original_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                newline = "\r\n" if original_line.endswith("\r\n") else "\n"
                new_lines.append(f"{key}={remaining.pop(key)}{newline}")
                continue

        new_lines.append(original_line)

    if remaining:
        if new_lines and not new_lines[-1].endswith(("\n", "\r")):
            new_lines[-1] += "\n"

        for key, value in remaining.items():
            new_lines.append(f"{key}={value}\n")

    temp_file = properties_file.with_suffix(".properties.tmp")
    with temp_file.open("w", encoding="utf-8", newline="") as file:
        file.writelines(new_lines)

    os.replace(temp_file, properties_file)


def bool_text(value):
    return "true" if value else "false"
