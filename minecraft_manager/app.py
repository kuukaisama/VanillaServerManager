import tkinter as tk
from tkinter import messagebox
from dataclasses import replace
from pathlib import Path
import logging
import threading
import queue
import time
import psutil

from . import APP_DISPLAY_NAME, __version__
from .agreement import (
    DISCLAIMER_TEXT,
    is_disclaimer_accepted,
    record_disclaimer_acceptance,
)
from .backup import (
    create_backup,
    format_file_size,
    get_backup_files,
    restore_backup as restore_backup_archive,
)
from .config import (
    AUTO_BACKUP_OPTIONS,
    WORLD_VERSION_DIR,
    bool_text,
    get_level_name,
    get_property,
    read_properties_map,
    write_properties,
)
from .migration import migrate_legacy_user_data, sync_legacy_worldversion_jars
from .profiles import ProfileStore, create_default_profile, create_profile
from .runtime import acquire_single_instance_lock, configure_logging
from .server import MAX_CONSOLE_LINES, ServerController
from .setup import create_server_files
from .tk_runtime import prepare_tk_runtime
from .ui.backup_dialog import show_backup_dialog
from .ui.disclaimer_dialog import show_disclaimer_dialog
from .ui.main_window import build_main_window
from .ui.profile_dialog import show_profile_dialog
from .ui.settings_dialog import show_settings_dialog
from .ui.setup_wizard import show_setup_wizard
from .ui.whitelist_dialog import show_whitelist_dialog
from .whitelist import read_whitelist_entries
from .validation import validate_backup_directory


# ============================================================
# 基本設定
# ============================================================

# ============================================================
# サーバー管理用変数
# ============================================================

max_players = 20
logger = logging.getLogger("vanilla_server_manager")

profile_store = ProfileStore()
profiles = []
# 未登録時の画面表示用。保存・登録は行わない。
active_profile = create_default_profile()
controllers = {}
active_controller = ServerController(active_profile)

root = None
active_profile_label = None
profile_listbox = None
status_label = None
cpu_label = None
ram_label = None
uptime_label = None
player_label = None
start_button = None
stop_button = None
restart_button = None
force_stop_button = None
backup_button = None
backup_manage_button = None
settings_button = None
whitelist_button = None
auto_backup_var = None
console = None
command_entry = None
send_button = None
profile_selection_updating = False


# ============================================================
# server.properties 読み込み
# ============================================================

def load_max_players():
    global max_players

    value = get_property("max-players", "20", profile=active_profile)

    try:
        max_players = int(value)
    except (TypeError, ValueError):
        max_players = 20


# ============================================================
# プレイヤー表示
# ============================================================

def update_player_label():
    player_label.config(
        text=f"{len(active_controller.online_players)} / {max_players}"
    )


# ============================================================
# サーバー起動
# ============================================================

def start_server():
    if not profiles or active_controller.restart_requested:
        return
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        messagebox.showinfo(
            APP_DISPLAY_NAME,
            "バックアップまたは復元処理中です。"
        )
        return

    if active_controller.running:
        messagebox.showinfo(
            APP_DISPLAY_NAME,
            "サーバーはすでに起動しています。"
        )
        return

    if not active_profile.server_jar.exists():
        messagebox.showerror(
            "エラー",
            f"server.jar が見つかりません。\n\n{active_profile.server_jar}"
        )
        return

    active_controller.online_players.clear()
    load_max_players()
    update_player_label()

    try:
        active_controller.start()
        logger.info("サーバーを起動しました: %s", active_profile.name)

        status_label.config(text="● 起動処理中...")
        set_controls_busy()

        stop_button.config(state=tk.NORMAL)

    except FileNotFoundError:
        active_controller.clear_process()

        messagebox.showerror(
            "Javaエラー",
            "Javaが見つかりません。\n\n"
            "Javaがインストールされ、PATHが設定されているか確認してください。"
        )

        set_stopped_ui()

    except Exception as e:
        active_controller.clear_process()

        messagebox.showerror(
            "起動エラー",
            str(e)
        )

        set_stopped_ui()


# ============================================================
# コンソール
# ============================================================

def add_console_text(text, controller=None):
    controller = controller or active_controller
    controller.append_console(text)

    if controller is not active_controller:
        return

    console.config(state=tk.NORMAL)
    console.insert(tk.END, text)
    line_count = int(console.index("end-1c").split(".")[0])
    if line_count > MAX_CONSOLE_LINES:
        console.delete("1.0", f"{line_count - MAX_CONSOLE_LINES + 1}.0")
    console.see(tk.END)
    console.config(state=tk.DISABLED)


def render_active_console():
    console.config(state=tk.NORMAL)
    console.delete("1.0", tk.END)
    console.insert(tk.END, "".join(active_controller.console_history))
    console.see(tk.END)
    console.config(state=tk.DISABLED)


# ============================================================
# UI状態
# ============================================================

def set_controls_busy():
    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.DISABLED)
    restart_button.config(state=tk.DISABLED)
    force_stop_button.config(state=tk.DISABLED)
    backup_button.config(state=tk.DISABLED)
    backup_manage_button.config(state=tk.DISABLED)
    settings_button.config(state=tk.DISABLED)
    whitelist_button.config(state=tk.DISABLED)
    command_entry.config(state=tk.DISABLED)
    send_button.config(state=tk.DISABLED)
    refresh_profile_list()


def set_running_ui():
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        return

    status_label.config(text="● 稼働中")

    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)
    restart_button.config(state=tk.NORMAL)
    force_stop_button.config(state=tk.DISABLED)
    backup_button.config(state=tk.NORMAL)
    backup_manage_button.config(state=tk.NORMAL)
    settings_button.config(state=tk.NORMAL)
    whitelist_button.config(state=tk.NORMAL)

    command_entry.config(state=tk.NORMAL)
    send_button.config(state=tk.NORMAL)
    refresh_profile_list()


def set_stopped_ui():
    if not profiles:
        set_controls_busy()
        status_label.config(text="● サーバー未登録")
        active_profile_label.config(text="「サーバーを追加」から作成・登録してください")
        player_label.config(text="-- / --")
        return
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        return

    status_label.config(text="● 停止中")

    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)
    restart_button.config(state=tk.DISABLED)
    force_stop_button.config(state=tk.DISABLED)

    # 停止中でもバックアップは可能
    backup_button.config(state=tk.NORMAL)
    backup_manage_button.config(state=tk.NORMAL)
    settings_button.config(state=tk.NORMAL)
    whitelist_button.config(state=tk.NORMAL)

    command_entry.config(state=tk.DISABLED)
    send_button.config(state=tk.DISABLED)
    refresh_profile_list()


# ============================================================
# GUIキュー処理
# ============================================================

def check_server_queue():
    try:
        while True:
            message_type, data = active_controller.event_queue.get_nowait()

            if message_type == "LOG":
                add_console_text(data)

            elif message_type == "PLAYER_JOIN":
                active_controller.online_players.add(data)
                update_player_label()

            elif message_type == "PLAYER_LEAVE":
                active_controller.online_players.discard(data)
                update_player_label()

            elif message_type == "BACKUP_DONE":
                active_controller.backup_in_progress = False
                active_controller.auto_backup_last_time = time.monotonic()

                zip_path = data["path"]
                automatic = data["automatic"]

                add_console_text(
                    f"\n[{APP_DISPLAY_NAME}] バックアップ完了: {zip_path}\n"
                )

                if active_controller.running:
                    set_running_ui()
                else:
                    set_stopped_ui()

                if not automatic:
                    messagebox.showinfo(
                        "バックアップ完了",
                        f"バックアップを作成しました。\n\n{zip_path}"
                    )

            elif message_type == "BACKUP_ERROR":
                active_controller.backup_in_progress = False
                active_controller.auto_backup_last_time = time.monotonic()

                error_text = data["error"]
                automatic = data["automatic"]

                add_console_text(
                    f"\n[{APP_DISPLAY_NAME}] バックアップ失敗: {error_text}\n"
                )

                if active_controller.running:
                    set_running_ui()
                else:
                    set_stopped_ui()

                if not automatic:
                    messagebox.showerror(
                        "バックアップエラー",
                        error_text
                    )

            elif message_type == "RESTORE_DONE":
                active_controller.restore_in_progress = False

                restored_path = data["restored_path"]
                safety_backup = data["safety_backup"]

                add_console_text(
                    f"\n[{APP_DISPLAY_NAME}] 復元完了: {restored_path}\n"
                    f"[{APP_DISPLAY_NAME}] 復元前バックアップ: {safety_backup}\n"
                )

                load_max_players()
                update_player_label()
                set_stopped_ui()

                messagebox.showinfo(
                    "復元完了",
                    "バックアップから復元しました。\n\n"
                    f"復元前バックアップ:\n{safety_backup}\n\n"
                    "サーバーを起動して内容を確認してください。"
                )

            elif message_type == "RESTORE_ERROR":
                active_controller.restore_in_progress = False

                add_console_text(
                    f"\n[{APP_DISPLAY_NAME}] 復元失敗: {data}\n"
                )

                set_stopped_ui()

                messagebox.showerror(
                    "復元エラー",
                    data
                )

            elif message_type == "STATUS":

                if data == "RUNNING":
                    set_running_ui()

                elif data == "STOPPED":
                    logger.info("サーバーが停止しました: %s", active_controller.profile.name)
                    active_controller.clear_process()
                    update_player_label()

                    if active_controller.closing_requested:
                        status_label.config(text="● 終了処理中...")

                    elif active_controller.restart_requested:
                        status_label.config(text="● 再起動しています...")
                        set_controls_busy()

                        root.after(
                            1500,
                            lambda controller=active_controller: complete_restart(controller)
                        )

                    else:
                        set_stopped_ui()

    except queue.Empty:
        pass

    root.after(
        100,
        check_server_queue
    )


# ============================================================
# Minecraftコマンド送信
# ============================================================

def send_server_command(command, echo=True):
    """GUI内部からMinecraftサーバーへコマンドを送信する。"""
    if not active_controller.running:
        raise RuntimeError("サーバーが起動していません。")

    active_controller.send(command)

    if echo:
        add_console_text(f"> {command}\n")


def send_command():
    if not active_controller.running:
        messagebox.showwarning(
            APP_DISPLAY_NAME,
            "サーバーが起動していません。"
        )
        return

    command = command_entry.get().strip()

    if not command:
        return

    try:
        send_server_command(command, echo=True)
        command_entry.delete(0, tk.END)

    except Exception as e:
        messagebox.showerror(
            "コマンド送信エラー",
            str(e)
        )


# ============================================================
# サーバー停止
# ============================================================

def stop_server():
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        messagebox.showinfo(
            APP_DISPLAY_NAME,
            "バックアップまたは復元処理中です。"
        )
        return

    if not active_controller.running:
        messagebox.showinfo(
            APP_DISPLAY_NAME,
            "サーバーは起動していません。"
        )
        set_stopped_ui()
        return

    try:
        status_label.config(text="● 停止処理中...")
        set_controls_busy()

        active_controller.send("stop")
        schedule_force_stop_offer(active_controller)

    except Exception as e:
        messagebox.showerror(
            "停止エラー",
            str(e)
        )

        set_running_ui()


def schedule_force_stop_offer(controller, timeout_ms=30_000):
    """通常停止が時間内に終わらない場合だけ強制終了を許可する。"""
    process = controller.process

    def offer():
        if (
            controller is active_controller
            and controller.process is process
            and controller.running
        ):
            status_label.config(text="● 通常停止に失敗しました")
            force_stop_button.config(state=tk.NORMAL)
            add_console_text(
                f"\n[{APP_DISPLAY_NAME}] 30秒以内に停止しませんでした。"
                "必要な場合のみ［強制終了］を使用してください。\n",
                controller=controller,
            )

    root.after(timeout_ms, offer)


def force_stop_server():
    """確認後にJavaプロセスを強制終了する。"""
    controller = active_controller
    if not controller.running:
        set_stopped_ui()
        return

    if not messagebox.askyesno(
        "サーバーの強制終了",
        "Minecraftサーバーを強制終了しますか？\n\n"
        "未保存のワールドデータが失われたり、"
        "ワールドが破損したりする可能性があります。\n"
        "通常の停止が完了しない場合だけ使用してください。",
        icon="warning",
        parent=root,
    ):
        return

    try:
        controller.restart_requested = False
        controller.closing_requested = False
        controller.force_stop()
        logger.warning("サーバーを強制終了しました: %s", controller.profile.name)
        status_label.config(text="● 強制終了処理中...")
        force_stop_button.config(state=tk.DISABLED)
    except Exception as error:
        logger.exception("サーバーの強制終了に失敗しました")
        messagebox.showerror("強制終了エラー", str(error), parent=root)


# ============================================================
# サーバー再起動
# ============================================================

def complete_restart(controller):
    """予約したサーバーだけを再起動する。取り消し後は何もしない。"""
    if not controller.restart_requested:
        return
    controller.restart_requested = False
    if controller is active_controller and controller.profile.profile_id in controllers:
        start_server()


def restart_server(confirm=True):
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        messagebox.showinfo(
            APP_DISPLAY_NAME,
            "バックアップまたは復元処理中です。"
        )
        return

    if not active_controller.running:
        start_server()
        return

    if confirm:
        result = messagebox.askyesno(
            APP_DISPLAY_NAME,
            "Minecraftサーバーを再起動しますか？"
        )

        if not result:
            return

    try:
        active_controller.restart_requested = True

        status_label.config(text="● 再起動のため停止中...")
        set_controls_busy()

        active_controller.send("stop")
        schedule_force_stop_offer(active_controller)

    except Exception as e:
        active_controller.restart_requested = False

        messagebox.showerror(
            "再起動エラー",
            str(e)
        )

        set_running_ui()


# ============================================================
# サーバー設定ウィンドウ
# ============================================================

def open_server_settings():
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        messagebox.showinfo(
            "サーバー設定",
            "バックアップまたは復元処理中は設定を変更できません。"
        )
        return

    properties_file = active_profile.server_directory / "server.properties"
    if not properties_file.exists():
        messagebox.showerror(
            "サーバー設定",
            "server.properties が見つかりません。\n"
            "一度サーバーを起動してから開いてください。"
        )
        return

    def is_server_running():
        return active_controller.running

    def save_changes(changes):
        validate_backup_directory(
            active_profile.server_directory,
            active_profile.backup_directory,
            changes.get("level-name", get_level_name(profile=active_profile)),
        )
        write_properties(changes, profile=active_profile)
        load_max_players()
        update_player_label()
        add_console_text(
            f"\n[{APP_DISPLAY_NAME}] server.properties を保存しました。\n"
        )

    def apply_changes():
        if is_server_running():
            restart_server(confirm=False)
        else:
            start_server()

    show_settings_dialog(
        root,
        properties=read_properties_map(profile=active_profile),
        is_server_running=is_server_running,
        on_save=save_changes,
        on_apply=apply_changes,
    )


# ============================================================
# ホワイトリスト管理ウィンドウ
# ============================================================


def open_whitelist_manager():
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        messagebox.showinfo(
            "ホワイトリスト",
            "バックアップまたは復元処理中は変更できません。"
        )
        return

    def is_server_running():
        return active_controller.running

    def is_enabled():
        return get_property(
            "white-list",
            "false",
            profile=active_profile,
        ).lower() == "true"

    def set_enabled(enabled):
        write_properties(
            {"white-list": bool_text(enabled)},
            profile=active_profile,
        )
        if is_server_running():
            send_server_command(
                "whitelist on" if enabled else "whitelist off",
                echo=True,
            )

    def add_player(name):
        send_server_command(f"whitelist add {name}", echo=True)

    def remove_player(name):
        send_server_command(f"whitelist remove {name}", echo=True)

    show_whitelist_dialog(
        root,
        list_entries=lambda: read_whitelist_entries(active_profile),
        is_enabled=is_enabled,
        is_server_running=is_server_running,
        on_set_enabled=set_enabled,
        on_add_player=add_player,
        on_remove_player=remove_player,
    )


# ============================================================
# バックアップ
# ============================================================

def backup_server(automatic=False):
    controller = active_controller

    if controller.backup_in_progress or controller.restore_in_progress:
        if not automatic:
            messagebox.showinfo(
                APP_DISPLAY_NAME,
                "バックアップまたは復元処理中です。"
            )
        return

    world_dir = (
        controller.profile.server_directory
        / get_level_name(profile=controller.profile)
    )

    if not world_dir.exists():
        if not automatic:
            messagebox.showerror(
                "バックアップ",
                f"ワールドフォルダが見つかりません。\n\n{world_dir}"
            )
        return

    if not automatic:
        running = (
            controller.running
        )

        text = (
            "現在のワールドをバックアップしますか？\n\n"
            + (
                "サーバー稼働中のため、安全に保存してからZIPを作成します。"
                if running
                else
                "サーバー停止中のため、そのままZIPを作成します。"
            )
        )

        if not messagebox.askyesno("バックアップ", text):
            return

    controller.backup_in_progress = True

    status_label.config(
        text="● バックアップ中..."
    )
    set_controls_busy()

    thread = threading.Thread(
        target=backup_worker,
        args=(controller, automatic),
        daemon=True
    )
    thread.start()


def backup_worker(controller, automatic):
    try:
        zip_path = create_backup(
            profile=controller.profile,
            level_name=get_level_name(profile=controller.profile),
            process=controller.process,
            save_complete_event=controller.save_complete_event,
            log=lambda text: controller.event_queue.put(("LOG", text)),
            backup_type="automatic" if automatic else "manual",
        )

        controller.event_queue.put(
            (
                "BACKUP_DONE",
                {
                    "path": str(zip_path),
                    "automatic": automatic,
                },
            )
        )
    except Exception as error:
        logger.exception("バックアップに失敗しました")
        controller.event_queue.put(
            (
                "BACKUP_ERROR",
                {
                    "error": str(error),
                    "automatic": automatic,
                },
            )
        )

# ============================================================
# バックアップ一覧
# ============================================================


def open_backup_manager():
    if active_controller.backup_in_progress or active_controller.restore_in_progress:
        messagebox.showinfo(
            "バックアップ管理",
            "バックアップまたは復元処理中です。"
        )
        return

    show_backup_dialog(
        root,
        list_backups=lambda: get_backup_files(active_profile),
        format_size=format_file_size,
        on_restore=lambda path, window: restore_backup(
            path,
            parent_window=window,
        ),
    )


# ============================================================
# 復元
# ============================================================

def restore_backup(zip_path, parent_window=None):
    controller = active_controller

    if controller.backup_in_progress or controller.restore_in_progress:
        messagebox.showinfo(
            "復元",
            "バックアップまたは復元処理中です。",
            parent=parent_window
        )
        return

    if controller.running:
        messagebox.showwarning(
            "復元",
            "復元する前にMinecraftサーバーを停止してください。",
            parent=parent_window
        )
        return

    result = messagebox.askyesno(
        "バックアップの復元",
        "選択したバックアップを復元します。\n\n"
        "復元直前の状態は自動的に別のZIPへバックアップされます。\n\n"
        "次のデータがバックアップ内の内容に置き換えられます。\n"
        "・ワールド\n"
        "・server.properties\n"
        "・ホワイトリスト\n"
        "・OP一覧\n"
        "・プレイヤーBAN／IP BAN一覧\n\n"
        "続行しますか？",
        parent=parent_window
    )

    if not result:
        return

    controller.restore_in_progress = True

    status_label.config(
        text="● バックアップを復元中..."
    )
    set_controls_busy()

    if parent_window is not None:
        try:
            parent_window.destroy()
        except tk.TclError:
            pass

    thread = threading.Thread(
        target=restore_worker,
        args=(controller, Path(zip_path)),
        daemon=True
    )
    thread.start()


def restore_worker(controller, zip_path):
    safety_backup = None
    try:
        safety_backup = create_backup(
            profile=controller.profile,
            level_name=get_level_name(profile=controller.profile),
            backup_type="pre_restore",
            log=lambda text: controller.event_queue.put(("LOG", text)),
        )
        restored_path = restore_backup_archive(controller.profile, zip_path)
        controller.event_queue.put(
            (
                "RESTORE_DONE",
                {
                    "restored_path": str(restored_path),
                    "safety_backup": str(safety_backup),
                },
            )
        )
    except Exception as error:
        logger.exception("バックアップの復元に失敗しました")
        error_text = str(error)
        if safety_backup is not None:
            error_text += f"\n\n復元前バックアップは保存されています。\n{safety_backup}"
        controller.event_queue.put(("RESTORE_ERROR", error_text))


# ============================================================
# 自動バックアップ
# ============================================================

def on_auto_backup_changed(event=None):
    if not profiles:
        return
    interval = AUTO_BACKUP_OPTIONS.get(
        auto_backup_var.get(),
        0
    )

    previous_interval = active_profile.auto_backup_interval
    active_profile.auto_backup_interval = auto_backup_var.get()
    try:
        profile_store.save(profiles)
    except Exception as error:
        active_profile.auto_backup_interval = previous_interval
        auto_backup_var.set(previous_interval)
        messagebox.showerror(
            "プロファイル保存エラー",
            str(error),
        )
        return

    if interval == 0:
        active_controller.auto_backup_last_time = None

        add_console_text(
            f"\n[{APP_DISPLAY_NAME}] 自動バックアップを無効にしました。\n"
        )
    else:
        active_controller.auto_backup_last_time = time.monotonic()

        add_console_text(
            f"\n[{APP_DISPLAY_NAME}] "
            f"自動バックアップを {auto_backup_var.get()} ごとに設定しました。\n"
        )


def check_auto_backup():
    interval = AUTO_BACKUP_OPTIONS.get(
        auto_backup_var.get(),
        0
    )

    if interval > 0:
        now = time.monotonic()

        if active_controller.auto_backup_last_time is None:
            active_controller.auto_backup_last_time = now

        server_running = active_controller.running

        if (
            server_running
            and not active_controller.restart_requested
            and not active_controller.closing_requested
            and not active_controller.backup_in_progress
            and not active_controller.restore_in_progress
            and now - active_controller.auto_backup_last_time >= interval
        ):
            # 連続実行防止のため、開始時点で時刻を更新
            active_controller.auto_backup_last_time = now
            backup_server(
                automatic=True
            )

    root.after(
        30_000,
        check_auto_backup
    )


# ============================================================
# ×ボタン
# ============================================================

def on_closing():
    if active_controller.backup_in_progress:
        messagebox.showwarning(
            APP_DISPLAY_NAME,
            "バックアップ中です。\n"
            "バックアップ完了後に終了してください。"
        )
        return

    if active_controller.restore_in_progress:
        messagebox.showwarning(
            APP_DISPLAY_NAME,
            "復元中です。\n"
            "復元完了後に終了してください。"
        )
        return

    if active_controller.running:
        result = messagebox.askyesno(
            APP_DISPLAY_NAME,
            "Minecraftサーバーが稼働しています。\n\n"
            "サーバーを安全に停止してから終了しますか？"
        )

        if not result:
            return

        try:
            active_controller.restart_requested = False
            active_controller.closing_requested = True
            active_controller.closing_start_time = time.monotonic()

            status_label.config(
                text="● サーバー停止後に終了します..."
            )

            set_controls_busy()

            active_controller.send("stop")

            wait_for_server_close()

        except Exception as e:
            active_controller.closing_requested = False

            messagebox.showerror(
                "終了エラー",
                str(e)
            )

    else:
        root.destroy()


def wait_for_server_close():
    if not active_controller.running:
        root.destroy()
        return

    elapsed = (
        time.monotonic()
        - active_controller.closing_start_time
    )

    if elapsed >= 30:
        active_controller.closing_requested = False

        status_label.config(
            text="● 停止処理に時間がかかっています"
        )

        messagebox.showwarning(
            APP_DISPLAY_NAME,
            "30秒以内にMinecraftサーバーが停止しませんでした。\n\n"
            "安全のためアプリは終了しません。\n"
            "必要な場合のみ［強制終了］を使用してください。"
        )

        set_running_ui()
        force_stop_button.config(state=tk.NORMAL)
        return

    root.after(
        200,
        wait_for_server_close
    )


# ============================================================
# ダッシュボード
# ============================================================

def update_dashboard():
    if (
        active_controller.running
        and active_controller.monitored_process is not None
    ):
        try:
            raw_cpu = active_controller.monitored_process.cpu_percent(
                interval=None
            )

            cpu_count = psutil.cpu_count(
                logical=True
            )

            if cpu_count:
                cpu_percent = raw_cpu / cpu_count
            else:
                cpu_percent = raw_cpu

            cpu_label.config(
                text=f"{cpu_percent:.1f} %"
            )

            memory = active_controller.monitored_process.memory_info()

            ram_gb = (
                memory.rss
                / (1024 ** 3)
            )

            ram_label.config(
                text=f"{ram_gb:.2f} GB"
            )

            if active_controller.start_time is not None:
                elapsed = int(
                    time.monotonic()
                    - active_controller.start_time
                )

                hours = elapsed // 3600
                minutes = (
                    elapsed % 3600
                ) // 60
                seconds = elapsed % 60

                uptime_label.config(
                    text=(
                        f"{hours:02}:"
                        f"{minutes:02}:"
                        f"{seconds:02}"
                    )
                )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            reset_dashboard()

    else:
        reset_dashboard()

    root.after(
        1000,
        update_dashboard
    )


def reset_dashboard():
    cpu_label.config(text="-- %")
    ram_label.config(text="-- GB")
    uptime_label.config(text="00:00:00")


def refresh_profile_list():
    global profile_selection_updating

    if profile_listbox is None:
        return

    profile_selection_updating = True
    try:
        profile_listbox.delete(0, tk.END)
        active_index = 0

        for index, profile in enumerate(profiles):
            controller = controllers[profile.profile_id]
            marker = "●" if controller.running else "○"
            profile_listbox.insert(tk.END, f"{marker} {profile.name}")
            if profile.profile_id == active_profile.profile_id:
                active_index = index

        if profiles:
            profile_listbox.selection_set(active_index)
            profile_listbox.see(active_index)
    finally:
        profile_selection_updating = False


def activate_profile(profile):
    global active_profile
    global active_controller

    changing_profile = profile.profile_id != active_profile.profile_id

    if changing_profile and (
        active_controller.running
        or active_controller.restart_requested
        or active_controller.backup_in_progress
        or active_controller.restore_in_progress
    ):
        messagebox.showwarning(
            "サーバー切り替え",
            "停止・再起動・バックアップ・復元が完了してから切り替えてください。",
            parent=root,
        )
        refresh_profile_list()
        return False

    active_profile = profile
    active_controller = controllers[profile.profile_id]
    active_profile_label.config(text=profile.name)
    root.title(
        f"{APP_DISPLAY_NAME} {__version__} - {profile.name}"
    )
    auto_backup_var.set(profile.auto_backup_interval)
    load_max_players()
    update_player_label()
    render_active_console()
    reset_dashboard()

    if (
        active_controller.backup_in_progress
        or active_controller.restore_in_progress
        or active_controller.restart_requested
    ):
        set_controls_busy()
    elif active_controller.running:
        set_running_ui()
    else:
        set_stopped_ui()

    refresh_profile_list()
    return True


def on_profile_selected(event=None):
    if profile_selection_updating:
        return

    selection = profile_listbox.curselection()
    if not selection:
        return

    index = selection[0]
    if index < len(profiles):
        activate_profile(profiles[index])


def _validate_profile_uniqueness(profile, exclude_profile_id=None):
    for existing in profiles:
        if existing.profile_id == exclude_profile_id:
            continue
        if existing.name.casefold() == profile.name.casefold():
            raise ValueError("同じ表示名のサーバーが既に登録されています。")
        if existing.server_directory.resolve() == profile.server_directory.resolve():
            raise ValueError("同じサーバーディレクトリが既に登録されています。")


def open_add_profile():
    def build_profile(values):
        profile = create_profile(
            values["name"],
            values["server_directory"],
            values["backup_directory"],
        )
        profile.jar_file = values["jar_file"]
        profile.java_executable = values["java_executable"]
        profile.minimum_memory = values["minimum_memory"]
        profile.maximum_memory = values["maximum_memory"]
        profile.auto_backup_interval = values["auto_backup_interval"]
        _validate_profile_uniqueness(profile)
        return profile

    def register_profile(profile):
        updated_profiles = [*profiles, profile]
        profile_store.save(updated_profiles)
        profiles.append(profile)
        controllers[profile.profile_id] = ServerController(profile)

        if not active_controller.running:
            activate_profile(profile)
        else:
            refresh_profile_list()

    def register_existing(values):
        profile = build_profile(values)
        validate_backup_directory(
            profile.server_directory, profile.backup_directory, get_level_name(profile=profile)
        )
        register_profile(profile)

    def create_new(values, jar_source, properties, eula_accepted):
        profile = build_profile(values)
        create_server_files(
            profile,
            jar_source,
            properties,
            eula_accepted,
        )
        register_profile(profile)

    choice = messagebox.askyesnocancel(
        "サーバーを追加",
        "新しいサーバーを作成しますか？\n\n"
        "［はい］新規サーバーを作成\n"
        "［いいえ］既存サーバーを登録\n"
        "［キャンセル］中止",
        parent=root,
    )

    if choice is None:
        return
    if choice:
        WORLD_VERSION_DIR.mkdir(parents=True, exist_ok=True)
        show_setup_wizard(
            root,
            auto_backup_options=AUTO_BACKUP_OPTIONS,
            world_version_directory=WORLD_VERSION_DIR,
            on_refresh_jars=sync_legacy_worldversion_jars,
            on_create=create_new,
        )
    else:
        show_profile_dialog(
            root,
            auto_backup_options=AUTO_BACKUP_OPTIONS,
            on_save=register_existing,
        )


def open_edit_profile():
    if not profiles:
        return
    if (
        active_controller.running
        or active_controller.restart_requested
        or active_controller.backup_in_progress
        or active_controller.restore_in_progress
    ):
        messagebox.showwarning(
            "サーバー設定を編集",
            "サーバーを停止し、バックアップや復元が完了してから編集してください。",
            parent=root,
        )
        return

    original = active_profile

    def save_profile(values):
        updated = replace(original, **values)
        validate_backup_directory(
            updated.server_directory, updated.backup_directory, get_level_name(profile=updated)
        )
        _validate_profile_uniqueness(
            updated,
            exclude_profile_id=original.profile_id,
        )
        updated_profiles = [
            updated if item.profile_id == original.profile_id else item
            for item in profiles
        ]
        profile_store.save(updated_profiles)

        index = profiles.index(original)
        profiles[index] = updated
        controllers[updated.profile_id].profile = updated
        activate_profile(updated)

    show_profile_dialog(
        root,
        auto_backup_options=AUTO_BACKUP_OPTIONS,
        on_save=save_profile,
        profile=original,
    )


def remove_active_profile():
    global active_profile
    global active_controller

    if not profiles:
        return

    if (
        active_controller.running
        or active_controller.restart_requested
        or active_controller.backup_in_progress
        or active_controller.restore_in_progress
    ):
        messagebox.showwarning(
            "登録を解除",
            "サーバーを停止し、バックアップや復元が完了してから登録解除してください。",
            parent=root,
        )
        return

    if not messagebox.askyesno(
        "登録を解除",
        f"{active_profile.name} の登録を解除しますか？\n\n"
        "サーバーファイルやバックアップは削除されません。",
        parent=root,
    ):
        return

    removed_id = active_profile.profile_id
    updated_profiles = [
        profile for profile in profiles if profile.profile_id != removed_id
    ]
    try:
        profile_store.save(updated_profiles)
    except (OSError, ValueError) as error:
        messagebox.showerror("プロファイル保存エラー", str(error), parent=root)
        return
    profiles[:] = updated_profiles
    controllers.pop(removed_id, None)
    active_profile = profiles[0] if profiles else create_default_profile()
    active_controller = controllers.get(active_profile.profile_id) or ServerController(active_profile)
    active_profile_label.config(text=active_profile.name)
    root.title(
        f"{APP_DISPLAY_NAME} {__version__} - {active_profile.name}"
    )
    auto_backup_var.set(active_profile.auto_backup_interval)
    load_max_players()
    update_player_label()
    render_active_console()
    reset_dashboard()
    set_stopped_ui()
    refresh_profile_list()


# ============================================================
# GUI開始
# ============================================================

def report_callback_exception(exception_type, exception, traceback):
    """Tkinterコールバックの未処理例外をログへ残して通知する。"""
    logger.error(
        "Tkinterコールバックで未処理例外が発生しました",
        exc_info=(exception_type, exception, traceback),
    )
    try:
        messagebox.showerror(
            "予期しないエラー",
            "処理中に予期しないエラーが発生しました。\n\n"
            "詳細はユーザーデータ内の logs\\app.log を確認してください。",
            parent=root,
        )
    except Exception:
        pass

def run():
    """画面を構築し、Tkinterのイベントループを開始する。"""
    global root
    global active_profile_label
    global profile_listbox
    global status_label
    global cpu_label
    global ram_label
    global uptime_label
    global player_label
    global start_button
    global stop_button
    global restart_button
    global force_stop_button
    global backup_button
    global backup_manage_button
    global settings_button
    global whitelist_button
    global auto_backup_var
    global console
    global command_entry
    global send_button
    global profiles
    global active_profile
    global controllers
    global active_controller

    prepare_tk_runtime()
    startup_root = tk.Tk()
    startup_root.withdraw()

    try:
        configure_logging()
        acquire_single_instance_lock()
    except Exception as error:
        messagebox.showerror(
            "起動エラー",
            str(error),
            parent=startup_root,
        )
        startup_root.destroy()
        return

    logger.info("%s %s を起動します", APP_DISPLAY_NAME, __version__)

    try:
        migration_result = migrate_legacy_user_data()
    except Exception as error:
        messagebox.showerror(
            "ユーザーデータ移行エラー",
            "既存データを安全に移行できなかったため、起動を中止します。\n"
            "元のデータは削除されていません。\n\n"
            + str(error),
            parent=startup_root,
        )
        startup_root.destroy()
        return

    if not is_disclaimer_accepted():
        accepted = show_disclaimer_dialog(
            startup_root,
            disclaimer_text=DISCLAIMER_TEXT,
            app_version=__version__,
            app_name=APP_DISPLAY_NAME,
        )
        if not accepted:
            startup_root.destroy()
            return
        try:
            record_disclaimer_acceptance(__version__)
        except Exception as error:
            messagebox.showerror(
                "同意情報の保存エラー",
                "免責事項への同意を保存できなかったため、起動を中止します。\n\n"
                + str(error),
                parent=startup_root,
            )
            startup_root.destroy()
            return

    try:
        profiles = profile_store.load()
    except (OSError, ValueError) as error:
        messagebox.showerror(
            "プロファイル読み込みエラー",
            "登録情報を保護するため起動を中止します。\n"
            "新しい形式の場合は対応するアプリで開いてください。\n\n" + str(error),
            parent=startup_root,
        )
        startup_root.destroy()
        return
    startup_root.destroy()
    active_profile = profiles[0] if profiles else create_default_profile()
    controllers = {
        profile.profile_id: ServerController(profile)
        for profile in profiles
    }
    active_controller = controllers.get(active_profile.profile_id) or ServerController(active_profile)

    window = build_main_window(
        auto_backup_options=AUTO_BACKUP_OPTIONS,
        initial_auto_backup=active_profile.auto_backup_interval,
        profile_names=[profile.name for profile in profiles],
        on_profile_selected=on_profile_selected,
        on_add_profile=open_add_profile,
        on_edit_profile=open_edit_profile,
        on_remove_profile=remove_active_profile,
        on_start=start_server,
        on_stop=stop_server,
        on_restart=restart_server,
        on_force_stop=force_stop_server,
        on_backup=backup_server,
        on_manage_backups=open_backup_manager,
        on_settings=open_server_settings,
        on_whitelist=open_whitelist_manager,
        on_auto_backup_changed=on_auto_backup_changed,
        on_send_command=send_command,
        on_close=on_closing,
    )

    root = window.root
    active_profile_label = window.active_profile_label
    profile_listbox = window.profile_listbox
    status_label = window.status_label
    cpu_label = window.cpu_label
    ram_label = window.ram_label
    uptime_label = window.uptime_label
    player_label = window.player_label
    start_button = window.start_button
    stop_button = window.stop_button
    restart_button = window.restart_button
    force_stop_button = window.force_stop_button
    backup_button = window.backup_button
    backup_manage_button = window.backup_manage_button
    settings_button = window.settings_button
    whitelist_button = window.whitelist_button
    auto_backup_var = window.auto_backup_var
    console = window.console
    command_entry = window.command_entry
    send_button = window.send_button
    root.title(
        f"{APP_DISPLAY_NAME} {__version__} - {active_profile.name}"
    )
    root.report_callback_exception = report_callback_exception

    if migration_result.migrated:
        messagebox.showinfo(
            "ユーザーデータを移行しました",
            "次の既存データをユーザーデータ領域へコピーしました。\n\n"
            + "\n".join(f"・{name}" for name in migration_result.copied_items)
            + "\n\n元のデータは安全のため削除していません。"
            "新しい保存先で正常動作を確認するまで保管してください。",
            parent=root,
        )

    load_max_players()
    update_player_label()
    check_server_queue()
    update_dashboard()
    check_auto_backup()
    set_stopped_ui()
    refresh_profile_list()

    root.mainloop()
