"""Minecraftサーバープロセスの起動、入出力、ログ解析。"""

import os
import queue
import re
import subprocess
import threading
import time

import psutil

from . import APP_DISPLAY_NAME


MAX_CONSOLE_LINES = 2000
LOG_PREFIX = r"^\[\d{2}:\d{2}:\d{2}\] \[[^\]\r\n]+/INFO\]: "
SERVER_READY_PATTERN = re.compile(
    LOG_PREFIX + r'Done \([0-9.]+s\)! For help, type "help"$'
)
SAVE_COMPLETE_PATTERN = re.compile(LOG_PREFIX + r"Saved the game$")
PLAYER_JOIN_PATTERN = re.compile(
    LOG_PREFIX + r"([A-Za-z0-9_]{1,16}) joined the game$"
)
PLAYER_LEAVE_PATTERN = re.compile(
    LOG_PREFIX + r"([A-Za-z0-9_]{1,16}) left the game$"
)


class ServerController:
    """1つのサーバープロファイルに属する実行状態を管理する。"""

    def __init__(self, profile):
        self.profile = profile
        self.process = None
        self.monitored_process = None
        self.start_time = None
        self.event_queue = queue.Queue()
        self.save_complete_event = threading.Event()
        self.online_players = set()
        self.restart_requested = False
        self.closing_requested = False
        self.closing_start_time = None
        self.backup_in_progress = False
        self.restore_in_progress = False
        self.auto_backup_last_time = None
        self.console_history = []

    @property
    def running(self):
        return is_running(self.process)

    def start(self):
        if self.running:
            raise RuntimeError("サーバーはすでに起動しています。")
        self.online_players.clear()
        self.process, self.monitored_process = launch_server(self.profile)
        self.start_time = time.monotonic()
        thread = threading.Thread(
            target=stream_server_output,
            args=(self.process, self.event_queue, self.save_complete_event),
            daemon=True,
        )
        thread.start()

    def send(self, command):
        send_command(self.process, command)

    def clear_process(self):
        self.process = None
        self.monitored_process = None
        self.start_time = None
        self.online_players.clear()

    def append_console(self, text):
        lines = text.splitlines(keepends=True)
        self.console_history.extend(lines or [text])
        if len(self.console_history) > MAX_CONSOLE_LINES:
            del self.console_history[:-MAX_CONSOLE_LINES]

    def force_stop(self):
        if not self.running:
            return
        self.process.kill()


def is_running(process):
    return process is not None and process.poll() is None


def launch_server(profile):
    """Javaプロセスを開始し、Popenとpsutilのプロセスを返す。"""
    command = [
        profile.java_executable,
        f"-Xms{profile.minimum_memory}",
        f"-Xmx{profile.maximum_memory}",
        "-jar",
        str(profile.server_jar),
        "nogui",
    ]

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=profile.server_directory,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creation_flags,
    )

    monitored_process = psutil.Process(process.pid)
    monitored_process.cpu_percent(interval=None)
    return process, monitored_process


def stream_server_output(process, event_queue, save_complete_event):
    """標準出力を読み、UIが処理できるイベントへ変換する。"""
    try:
        for line in process.stdout:
            event_queue.put(("LOG", line))
            normalized = line.rstrip("\r\n")

            if SERVER_READY_PATTERN.fullmatch(normalized):
                event_queue.put(("STATUS", "RUNNING"))

            if SAVE_COMPLETE_PATTERN.fullmatch(normalized):
                save_complete_event.set()

            join_match = PLAYER_JOIN_PATTERN.fullmatch(normalized)
            if join_match:
                event_queue.put(("PLAYER_JOIN", join_match.group(1)))

            leave_match = PLAYER_LEAVE_PATTERN.fullmatch(normalized)
            if leave_match:
                event_queue.put(("PLAYER_LEAVE", leave_match.group(1)))
    except Exception as error:
        event_queue.put(("LOG", f"\n[{APP_DISPLAY_NAME} Error] {error}\n"))
    finally:
        # stdoutだけが予期せず閉じても、Javaが動作中なら停止扱いにしない。
        try:
            process.wait()
        except Exception as error:
            event_queue.put(("LOG", f"\n[{APP_DISPLAY_NAME} Error] {error}\n"))
        event_queue.put(("STATUS", "STOPPED"))


def send_command(process, command):
    """稼働中のMinecraftサーバーへコマンドを送る。"""
    if not is_running(process):
        raise RuntimeError("サーバーが起動していません。")

    process.stdin.write(command + "\n")
    process.stdin.flush()
