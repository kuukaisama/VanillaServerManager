"""ワールドバックアップの作成・列挙・復元。"""

import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from pathlib import PureWindowsPath

from . import APP_DISPLAY_NAME
from .config import CONFIG_FILES
from .validation import validate_backup_directory, world_path


RESTORE_SPACE_MARGIN = 64 * 1024 * 1024
VALID_BACKUP_TYPES = {"manual", "automatic", "pre_restore"}


def create_backup(
    profile,
    level_name,
    process=None,
    save_complete_event=None,
    log=None,
    backup_type="manual",
):
    """ワールドと関連設定をZIPへ保存し、作成したパスを返す。"""
    running = process is not None and process.poll() is None
    save_disabled = False
    zip_path = None

    try:
        if backup_type not in VALID_BACKUP_TYPES:
            raise ValueError(f"未対応のバックアップ種別です: {backup_type}")
        validate_backup_directory(
            profile.server_directory, profile.backup_directory, level_name
        )
        profile.backup_directory.mkdir(parents=True, exist_ok=True)
        world_dir = world_path(profile.server_directory, level_name)

        if not world_dir.exists():
            raise FileNotFoundError(
                f"ワールドフォルダが見つかりません。\n{world_dir}"
            )

        if log is not None:
            log(f"\n[{APP_DISPLAY_NAME}] バックアップを開始します...\n")

        if running:
            if save_complete_event is None:
                raise ValueError("保存完了イベントが指定されていません。")

            save_complete_event.clear()
            process.stdin.write("save-off\n")
            process.stdin.flush()
            save_disabled = True
            process.stdin.write("save-all flush\n")
            process.stdin.flush()

            if not save_complete_event.wait(timeout=30):
                raise TimeoutError(
                    "save-all flush の完了を30秒以内に確認できませんでした。"
                )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = (
            f"pre_restore_{level_name}"
            if backup_type == "pre_restore"
            else level_name
        )
        zip_path = profile.backup_directory / f"{prefix}_{timestamp}.zip"
        metadata = {
            "format_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "level_name": level_name,
            "backup_type": backup_type,
        }

        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as zip_file:
            zip_file.writestr(
                "server_manager_backup.json",
                json.dumps(metadata, ensure_ascii=False, indent=2),
            )

            for file_path in world_dir.rglob("*"):
                if not file_path.is_file() or file_path.name == "session.lock":
                    continue

                relative_path = file_path.relative_to(world_dir)
                zip_file.write(file_path, Path(level_name) / relative_path)

            for file_name in CONFIG_FILES:
                file_path = profile.server_directory / file_name
                if file_path.exists():
                    zip_file.write(file_path, file_path.name)

        return zip_path
    except Exception:
        if zip_path is not None and zip_path.exists():
            try:
                zip_path.unlink()
            except OSError:
                pass
        raise
    finally:
        if save_disabled and process is not None and process.poll() is None:
            try:
                process.stdin.write("save-on\n")
                process.stdin.flush()
            except Exception:
                pass


def get_backup_files(profile):
    profile.backup_directory.mkdir(parents=True, exist_ok=True)
    return sorted(
        profile.backup_directory.glob("*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def format_file_size(size_bytes):
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{size_bytes} B"


def safe_extract_zip(zip_file, destination):
    destination = destination.resolve()

    for member in zip_file.infolist():
        portable_path = PureWindowsPath(member.filename)
        if portable_path.drive or portable_path.root or ".." in portable_path.parts:
            raise ValueError(f"安全でないZIPパスを検出しました: {member.filename}")
        member_path = (destination / member.filename).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as error:
            raise ValueError(
                f"安全でないZIPパスを検出しました: {member.filename}"
            ) from error

    zip_file.extractall(destination)


def get_restore_space_requirement(zip_path):
    """展開領域と配置準備領域に必要な概算バイト数を返す。"""
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        uncompressed_size = sum(
            member.file_size
            for member in zip_file.infolist()
            if not member.is_dir()
        )
    return (uncompressed_size * 2) + RESTORE_SPACE_MARGIN


def ensure_restore_space(server_directory, zip_path):
    required = get_restore_space_requirement(zip_path)
    available = shutil.disk_usage(server_directory).free
    if available < required:
        raise OSError(
            "復元に必要な空き容量が不足しています。\n"
            f"必要容量（概算）: {format_file_size(required)}\n"
            f"空き容量: {format_file_size(available)}"
        )
    return required, available


def restore_backup(profile, zip_path):
    """全データを準備してから交換し、失敗時は設定も含めて戻す。"""
    zip_path = Path(zip_path)
    server_directory = profile.server_directory.resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"バックアップが見つかりません。\n{zip_path}")

    ensure_restore_space(server_directory, zip_path)

    # 同じボリューム上でrenameできるようサーバー内に作業領域を置く。
    workspace = Path(tempfile.mkdtemp(prefix=".restore_", dir=server_directory))
    extracted = workspace / "extracted"
    staged = workspace / "staged"
    originals = workspace / "originals"
    journal = []
    preserve_recovery = False
    try:
        for directory in (extracted, staged, originals):
            directory.mkdir()
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            safe_extract_zip(zip_file, extracted)

        metadata_path = extracted / "server_manager_backup.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("バックアップ情報の形式が正しくありません。")
            level_name = metadata.get("level_name")
        else:
            candidates = [p.name for p in extracted.iterdir() if p.is_dir()]
            if len(candidates) != 1:
                raise ValueError("バックアップ内のワールド名を判定できません。")
            level_name = candidates[0]

        source_world = world_path(extracted, level_name)
        target_world = world_path(server_directory, level_name)
        if level_name in CONFIG_FILES or level_name == "server.jar":
            raise ValueError("ワールド名がサーバーファイル名と重複しています。")
        if not source_world.is_dir():
            raise ValueError("バックアップ内にワールドフォルダーがありません。")
        validate_backup_directory(server_directory, profile.backup_directory, level_name)
        targets = [target_world]
        for name in CONFIG_FILES:
            source = extracted / name
            if source.exists():
                target = world_path(server_directory, name)
                if not source.is_file() or (target.exists() and not target.is_file()):
                    raise ValueError(f"設定ファイルの形式が正しくありません: {name}")
                targets.append(target)
        if target_world.exists() and not target_world.is_dir():
            raise ValueError("復元先のワールドがフォルダーではありません。")

        # コピー失敗は元のワールド・設定へ触れる前に検出する。
        shutil.copytree(source_world, staged / level_name)
        for target in targets[1:]:
            shutil.copy2(extracted / target.name, staged / target.name)

        try:
            for target in targets:
                original = originals / target.name
                existed = target.exists()
                if existed:
                    target.replace(original)
                journal.append((target, existed))
                (staged / target.name).replace(target)
        except Exception as error:
            failures = []
            for target, existed in reversed(journal):
                try:
                    if target.exists():
                        target.replace(staged / target.name)
                    if existed:
                        (originals / target.name).replace(target)
                except Exception as rollback_error:
                    failures.append(str(rollback_error))
            if failures:
                preserve_recovery = True
                raise RuntimeError(
                    f"復元と元データへの復旧に失敗しました。\n復旧用データ: {workspace}\n"
                    + "\n".join(failures)
                ) from error
            raise
        return zip_path
    finally:
        if not preserve_recovery:
            shutil.rmtree(workspace, ignore_errors=True)
