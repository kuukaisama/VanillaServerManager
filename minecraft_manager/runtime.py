"""アプリのログ出力と多重起動防止。"""

import atexit
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from . import APP_DISPLAY_NAME
from .paths import APP_LOCK_FILE, APP_LOG_FILE


_instance_handle = None


def configure_logging(path=APP_LOG_FILE):
    """ユーザーデータ領域へローテーション付きログを出力する。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("vanilla_server_manager")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            path,
            maxBytes=1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"
            )
        )
        logger.addHandler(handler)
    return logger


def acquire_single_instance_lock(path=APP_LOCK_FILE):
    """同じWindowsユーザーでアプリが既に動作中なら例外にする。"""
    global _instance_handle
    if _instance_handle is not None:
        return _instance_handle

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)

    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise RuntimeError(
            f"{APP_DISPLAY_NAME}はすでに起動しています。"
        ) from error

    _instance_handle = handle
    atexit.register(release_single_instance_lock)
    return handle


def release_single_instance_lock():
    global _instance_handle
    handle = _instance_handle
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    finally:
        handle.close()
        _instance_handle = None
