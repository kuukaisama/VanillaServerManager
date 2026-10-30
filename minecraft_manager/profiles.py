"""複数サーバー管理で使用するプロファイルモデルと保存処理。"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from uuid import uuid4

from .paths import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_SERVER_DIR,
    PROFILES_FILE,
    USER_DATA_DIR,
)


PROFILE_SCHEMA_VERSION = 1
DEFAULT_PROFILES_FILE = PROFILES_FILE


@dataclass
class ServerProfile:
    """1台のMinecraftサーバーを起動・管理するための設定。"""

    profile_id: str
    name: str
    server_directory: Path
    backup_directory: Path
    jar_file: str = "server.jar"
    java_executable: str = "java"
    minimum_memory: str = "1024M"
    maximum_memory: str = "4096M"
    auto_backup_interval: str = "無効"

    @property
    def server_jar(self):
        return self.server_directory / self.jar_file

    def to_dict(self, base_directory=USER_DATA_DIR):
        data = asdict(self)
        data["server_directory"] = _portable_path(
            self.server_directory,
            base_directory,
        )
        data["backup_directory"] = _portable_path(
            self.backup_directory,
            base_directory,
        )
        return data

    @classmethod
    def from_dict(cls, data, base_directory=USER_DATA_DIR):
        if not isinstance(data, dict):
            raise ValueError("サーバープロファイルの形式が正しくありません。")

        required = ("profile_id", "name", "server_directory", "backup_directory")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValueError(
                "サーバープロファイルに必須項目がありません: "
                + ", ".join(missing)
            )

        return cls(
            profile_id=str(data["profile_id"]),
            name=str(data["name"]),
            server_directory=_resolve_path(data["server_directory"], base_directory),
            backup_directory=_resolve_path(data["backup_directory"], base_directory),
            jar_file=str(data.get("jar_file", "server.jar")),
            java_executable=str(data.get("java_executable", "java")),
            minimum_memory=str(data.get("minimum_memory", "1024M")),
            maximum_memory=str(data.get("maximum_memory", "4096M")),
            auto_backup_interval=str(data.get("auto_backup_interval", "無効")),
        )


def create_profile(name, server_directory, backup_directory):
    return ServerProfile(
        profile_id=uuid4().hex,
        name=name,
        server_directory=Path(server_directory).resolve(),
        backup_directory=Path(backup_directory).resolve(),
    )


def create_default_profile():
    """ユーザーデータ領域に保存する既定プロファイルを返す。"""
    return ServerProfile(
        profile_id="default",
        name="Minecraft Server",
        server_directory=DEFAULT_SERVER_DIR,
        backup_directory=DEFAULT_BACKUP_DIR,
    )


class ProfileStore:
    def __init__(self, path=DEFAULT_PROFILES_FILE, base_directory=USER_DATA_DIR):
        self.path = Path(path)
        self.base_directory = Path(base_directory)

    def load(self):
        if not self.path.exists():
            default = create_default_profile()
            return [default] if default.server_jar.is_file() else []

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"プロファイル設定を読み込めません。\n{self.path}"
            ) from error

        if isinstance(data, list):
            # バージョン1.0より前の形式との互換性。
            profile_items = data
        elif isinstance(data, dict):
            schema_version = data.get("schema_version")
            if schema_version != PROFILE_SCHEMA_VERSION:
                raise ValueError(
                    "未対応のプロファイル設定形式です: "
                    f"schema_version={schema_version}"
                )
            profile_items = data.get("profiles")
            if not isinstance(profile_items, list):
                raise ValueError("profilesは配列である必要があります。")
        else:
            raise ValueError("プロファイル設定の形式が正しくありません。")

        profiles = [
            ServerProfile.from_dict(item, self.base_directory)
            for item in profile_items
        ]

        profile_ids = [profile.profile_id for profile in profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("同じプロファイルIDが複数存在します。")

        return profiles

    def save(self, profiles):
        # 読めない設定や新しい形式を古いアプリで上書きしない。
        if self.path.exists():
            self.load()
        profiles = list(profiles)
        profile_ids = [profile.profile_id for profile in profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("同じプロファイルIDが複数存在します。")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        data = {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "profiles": [
                profile.to_dict(self.base_directory)
                for profile in profiles
            ],
        }
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.path)


def _resolve_path(value, base_directory):
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = Path(base_directory) / path
    return path.resolve()


def _portable_path(path, base_directory):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(Path(base_directory).resolve()))
    except ValueError:
        return str(path)
