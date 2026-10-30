"""バージョン1.0より前のユーザーデータを新しい保存先へ移行する。"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
from uuid import uuid4

from .paths import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_SERVER_DIR,
    LEGACY_BACKUP_DIR,
    LEGACY_PROFILES_FILE,
    LEGACY_SERVER_DIR,
    LEGACY_USER_DATA_DIRS,
    LEGACY_WORLD_VERSION_DIR,
    PROJECT_DIR,
    PROFILES_FILE,
    USER_DATA_DIR,
    WORLD_VERSION_DIR,
)
from .profiles import ProfileStore


@dataclass
class MigrationResult:
    copied_items: list[str] = field(default_factory=list)

    @property
    def migrated(self):
        return bool(self.copied_items)


def migrate_legacy_user_data():
    """旧データをコピーし、元データを残したまま新保存先へ切り替える。"""
    result = MigrationResult()

    # 公開前まで使用していた2つの旧保存先から順番に移行する。
    # 新保存先に存在するデータは上書きせず、旧保存先も削除しない。
    for legacy_user_data_dir in LEGACY_USER_DATA_DIRS:
        app_data_migrated = _merge_directory_missing(
            legacy_user_data_dir,
            USER_DATA_DIR,
        )
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        profiles_rebased = _rebase_profile_paths(
            legacy_user_data_dir,
            USER_DATA_DIR,
        )
        if app_data_migrated or profiles_rebased:
            result.copied_items.append(
                f"旧保存先 {legacy_user_data_dir.name}"
            )

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if _copy_directory_if_missing(LEGACY_SERVER_DIR, DEFAULT_SERVER_DIR):
        result.copied_items.append("server")
    if _copy_directory_if_missing(LEGACY_BACKUP_DIR, DEFAULT_BACKUP_DIR):
        result.copied_items.append("backups")
    worldversion_migrated = _copy_directory_if_missing(
        LEGACY_WORLD_VERSION_DIR,
        WORLD_VERSION_DIR,
        ignore_names={".gitkeep"},
    )
    copied_jars = sync_legacy_worldversion_jars()
    if worldversion_migrated or copied_jars:
        result.copied_items.append("worldversion")

    if LEGACY_PROFILES_FILE.exists() and not PROFILES_FILE.exists():
        legacy_store = ProfileStore(
            path=LEGACY_PROFILES_FILE,
            base_directory=PROJECT_DIR,
        )
        profiles = legacy_store.load()
        for profile in profiles:
            if profile.server_directory.resolve() == LEGACY_SERVER_DIR.resolve():
                profile.server_directory = DEFAULT_SERVER_DIR.resolve()
            if profile.backup_directory.resolve() == LEGACY_BACKUP_DIR.resolve():
                profile.backup_directory = DEFAULT_BACKUP_DIR.resolve()
        ProfileStore(
            path=PROFILES_FILE,
            base_directory=USER_DATA_DIR,
        ).save(profiles)
        result.copied_items.append("profiles.json")

    return result


def sync_legacy_worldversion_jars():
    """旧worldversionに後から追加されたJARを新保存先へコピーする。"""
    WORLD_VERSION_DIR.mkdir(parents=True, exist_ok=True)

    copied = []
    legacy_directories = tuple(
        directory / "worldversion"
        for directory in LEGACY_USER_DATA_DIRS
    ) + (LEGACY_WORLD_VERSION_DIR,)
    for legacy_directory in legacy_directories:
        if not legacy_directory.is_dir():
            continue
        for source in legacy_directory.iterdir():
            if not source.is_file() or source.suffix.lower() != ".jar":
                continue
            destination = WORLD_VERSION_DIR / source.name
            if _copy_file_if_missing(source, destination):
                copied.append(destination)
    return copied


def _rebase_profile_paths(source_base, destination_base):
    """旧保存先を指す絶対パスだけを新保存先へ付け替える。"""
    if not PROFILES_FILE.is_file() or not Path(source_base).is_dir():
        return False

    store = ProfileStore(
        path=PROFILES_FILE,
        base_directory=USER_DATA_DIR,
    )
    profiles = store.load()
    changed = False
    for profile in profiles:
        server_directory = _rebased_path(
            profile.server_directory,
            source_base,
            destination_base,
        )
        backup_directory = _rebased_path(
            profile.backup_directory,
            source_base,
            destination_base,
        )
        if server_directory != profile.server_directory:
            profile.server_directory = server_directory
            changed = True
        if backup_directory != profile.backup_directory:
            profile.backup_directory = backup_directory
            changed = True

    if changed:
        store.save(profiles)
    return changed


def _rebased_path(path, source_base, destination_base):
    path = Path(path).resolve()
    try:
        relative = path.relative_to(Path(source_base).resolve())
    except ValueError:
        return path
    return (Path(destination_base).resolve() / relative).resolve()


def _merge_directory_missing(source, destination, ignore_names=None):
    """既存項目を上書きせず、ディレクトリ内の不足分だけをコピーする。"""
    source = Path(source)
    destination = Path(destination)
    if not source.is_dir():
        return False

    ignore_names = set(ignore_names or ())
    copied = False
    if not destination.exists():
        return _copy_directory_if_missing(source, destination, ignore_names)
    if not destination.is_dir():
        return False

    for item in source.iterdir():
        if item.name in ignore_names:
            continue
        target = destination / item.name
        if item.is_dir():
            if _merge_directory_missing(item, target):
                copied = True
        elif item.is_file() and _copy_file_if_missing(item, target):
            copied = True
    return copied


def _copy_file_if_missing(source, destination):
    """一時ファイルを経由し、不完全なコピーを完成品として残さない。"""
    source = Path(source)
    destination = Path(destination)
    if not source.is_file() or destination.exists():
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.migration-{uuid4().hex}.tmp"
    )
    try:
        shutil.copy2(source, temporary)
        if destination.exists():
            return False
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def _copy_directory_if_missing(source, destination, ignore_names=None):
    source = Path(source)
    destination = Path(destination)
    if not source.is_dir() or destination.exists():
        return False

    ignore_names = set(ignore_names or ())

    def ignore(_directory, names):
        return [name for name in names if name in ignore_names]

    try:
        shutil.copytree(
            source,
            destination,
            ignore=ignore if ignore_names else None,
        )
    except Exception:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise
    return True
