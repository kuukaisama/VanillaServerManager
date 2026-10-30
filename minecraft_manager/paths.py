"""アプリ本体とユーザーデータの保存先を定義する。"""

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
APP_DATA_FOLDER_NAME = "VanillaServerManager"
LEGACY_APP_DATA_FOLDER_NAMES = (
    "MinecraftServerManager",
    "minecraft_maneger",
)


def _get_local_app_data_directory():
    configured = os.environ.get("LOCALAPPDATA")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "AppData" / "Local"


LOCAL_APP_DATA_DIR = _get_local_app_data_directory()
USER_DATA_DIR = LOCAL_APP_DATA_DIR / APP_DATA_FOLDER_NAME
LEGACY_USER_DATA_DIRS = tuple(
    LOCAL_APP_DATA_DIR / name
    for name in LEGACY_APP_DATA_FOLDER_NAMES
)
PROFILES_FILE = USER_DATA_DIR / "profiles.json"
SETTINGS_FILE = USER_DATA_DIR / "settings.json"
DEFAULT_SERVER_DIR = USER_DATA_DIR / "server"
DEFAULT_BACKUP_DIR = USER_DATA_DIR / "backups"
WORLD_VERSION_DIR = USER_DATA_DIR / "worldversion"
LOG_DIR = USER_DATA_DIR / "logs"
APP_LOG_FILE = LOG_DIR / "app.log"
APP_LOCK_FILE = USER_DATA_DIR / "app.lock"

# バージョン1.0より前にプロジェクト直下へ保存していたデータ。
LEGACY_PROFILES_FILE = PROJECT_DIR / "profiles.json"
LEGACY_SERVER_DIR = PROJECT_DIR / "server"
LEGACY_BACKUP_DIR = PROJECT_DIR / "backups"
LEGACY_WORLD_VERSION_DIR = PROJECT_DIR / "worldversion"
