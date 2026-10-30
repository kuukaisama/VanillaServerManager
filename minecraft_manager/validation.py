"""データ保存先の共通検証。"""

from pathlib import Path
import re


def validate_world_name(name):
    """ワールド名をWindows上の単一フォルダー名に限定する。"""
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or name.endswith((".", " "))
        or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
        or name.split(".", 1)[0].upper()
        in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}
    ):
        raise ValueError("ワールド名には有効な単一のフォルダー名を指定してください。")
    return name


def world_path(server_directory, name):
    validate_world_name(name)
    server_directory = Path(server_directory).resolve()
    path = server_directory / name
    if path.resolve().parent != server_directory or path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    ):
        raise ValueError("ワールドはサーバーフォルダー直下の実フォルダーにしてください。")
    return path


def validate_backup_directory(server_directory, backup_directory, level_name="world"):
    world = world_path(server_directory, level_name)
    backup = Path(backup_directory).resolve()
    if backup == world or world in backup.parents:
        raise ValueError("バックアップ保存先をワールド内に指定することはできません。")
