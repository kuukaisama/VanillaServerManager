"""メインウィンドウの構築。"""

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from .. import APP_DISPLAY_NAME


@dataclass
class MainWindow:
    root: tk.Tk
    active_profile_label: tk.Label
    profile_listbox: tk.Listbox
    status_label: tk.Label
    cpu_label: tk.Label
    ram_label: tk.Label
    uptime_label: tk.Label
    player_label: tk.Label
    start_button: tk.Button
    stop_button: tk.Button
    restart_button: tk.Button
    force_stop_button: tk.Button
    backup_button: tk.Button
    backup_manage_button: tk.Button
    settings_button: tk.Button
    whitelist_button: tk.Button
    auto_backup_var: tk.StringVar
    console: tk.Text
    command_entry: tk.Entry
    send_button: tk.Button


def _create_dashboard_item(parent, title, initial_text):
    frame = tk.Frame(parent, padx=25, pady=15)
    frame.pack(side=tk.LEFT, expand=True)

    tk.Label(frame, text=title, font=("Arial", 11)).pack()
    value_label = tk.Label(
        frame,
        text=initial_text,
        font=("Arial", 16, "bold"),
    )
    value_label.pack()
    return value_label


def build_main_window(
    *,
    auto_backup_options,
    initial_auto_backup,
    profile_names,
    on_profile_selected,
    on_add_profile,
    on_edit_profile,
    on_remove_profile,
    on_start,
    on_stop,
    on_restart,
    on_force_stop,
    on_backup,
    on_manage_backups,
    on_settings,
    on_whitelist,
    on_auto_backup_changed,
    on_send_command,
    on_close,
):
    root = tk.Tk()
    root.title(APP_DISPLAY_NAME)
    root.geometry("1500x900")
    root.minsize(1200, 780)

    tk.Label(
        root,
        text=APP_DISPLAY_NAME,
        font=("Arial", 24, "bold"),
    ).pack(pady=(15, 8))

    body = tk.Frame(root)
    body.pack(fill=tk.BOTH, expand=True)

    sidebar = tk.Frame(body, width=240, relief=tk.GROOVE, borderwidth=1)
    sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(15, 5), pady=(0, 15))
    sidebar.pack_propagate(False)

    tk.Label(
        sidebar,
        text="サーバー一覧",
        font=("Arial", 14, "bold"),
    ).pack(pady=(15, 8))

    profile_listbox = tk.Listbox(sidebar, font=("Arial", 11), exportselection=False)
    profile_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
    for profile_name in profile_names:
        profile_listbox.insert(tk.END, profile_name)
    if profile_names:
        profile_listbox.selection_set(0)
    profile_listbox.bind("<<ListboxSelect>>", on_profile_selected)

    tk.Button(
        sidebar,
        text="サーバーを追加",
        command=on_add_profile,
    ).pack(fill=tk.X, padx=10, pady=3)
    tk.Button(
        sidebar,
        text="設定を編集",
        command=on_edit_profile,
    ).pack(fill=tk.X, padx=10, pady=3)
    tk.Button(
        sidebar,
        text="登録を解除",
        command=on_remove_profile,
    ).pack(fill=tk.X, padx=10, pady=(3, 12))

    content = tk.Frame(body)
    content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    active_profile_label = tk.Label(
        content,
        text=profile_names[0] if profile_names else "",
        font=("Arial", 16, "bold"),
    )
    active_profile_label.pack(pady=(0, 3))

    dashboard_frame = tk.Frame(content, relief=tk.GROOVE, borderwidth=2)
    dashboard_frame.pack(fill=tk.X, padx=20, pady=10)

    status_label = _create_dashboard_item(
        dashboard_frame, "状態", "● 停止中"
    )
    cpu_label = _create_dashboard_item(
        dashboard_frame, "CPU使用率", "-- %"
    )
    ram_label = _create_dashboard_item(
        dashboard_frame, "RAM使用量", "-- GB"
    )
    uptime_label = _create_dashboard_item(
        dashboard_frame, "稼働時間", "00:00:00"
    )
    player_label = _create_dashboard_item(
        dashboard_frame, "プレイヤー", "0 / 20"
    )

    button_frame = tk.Frame(content)
    button_frame.pack(pady=(10, 5))

    start_button = tk.Button(
        button_frame, text="サーバー起動", width=15, command=on_start
    )
    start_button.pack(side=tk.LEFT, padx=7)

    stop_button = tk.Button(
        button_frame,
        text="サーバー停止",
        width=15,
        command=on_stop,
        state=tk.DISABLED,
    )
    stop_button.pack(side=tk.LEFT, padx=7)

    restart_button = tk.Button(
        button_frame,
        text="再起動",
        width=15,
        command=on_restart,
        state=tk.DISABLED,
    )
    restart_button.pack(side=tk.LEFT, padx=7)

    force_stop_button = tk.Button(
        button_frame,
        text="強制終了",
        width=15,
        command=on_force_stop,
        state=tk.DISABLED,
    )
    force_stop_button.pack(side=tk.LEFT, padx=7)

    backup_button = tk.Button(
        button_frame,
        text="今すぐバックアップ",
        width=18,
        command=on_backup,
    )
    backup_button.pack(side=tk.LEFT, padx=7)

    backup_manage_button = tk.Button(
        button_frame,
        text="バックアップ管理",
        width=18,
        command=on_manage_backups,
    )
    backup_manage_button.pack(side=tk.LEFT, padx=7)

    settings_button = tk.Button(
        button_frame,
        text="サーバー設定",
        width=16,
        command=on_settings,
    )
    settings_button.pack(side=tk.LEFT, padx=7)

    whitelist_button = tk.Button(
        button_frame,
        text="ホワイトリスト",
        width=16,
        command=on_whitelist,
    )
    whitelist_button.pack(side=tk.LEFT, padx=7)

    auto_frame = tk.Frame(content)
    auto_frame.pack(pady=(5, 10))
    tk.Label(
        auto_frame,
        text="自動バックアップ:",
        font=("Arial", 11),
    ).pack(side=tk.LEFT, padx=(0, 8))

    auto_backup_var = tk.StringVar(value=initial_auto_backup)
    auto_backup_combo = ttk.Combobox(
        auto_frame,
        textvariable=auto_backup_var,
        values=list(auto_backup_options.keys()),
        state="readonly",
        width=12,
    )
    auto_backup_combo.pack(side=tk.LEFT)
    auto_backup_combo.bind("<<ComboboxSelected>>", on_auto_backup_changed)

    tk.Label(
        content,
        text="コンソール",
        font=("Arial", 13, "bold"),
    ).pack(anchor="w", padx=20, pady=(5, 0))

    console_frame = tk.Frame(content)
    console_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    scrollbar = tk.Scrollbar(console_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    console = tk.Text(
        console_frame,
        state=tk.DISABLED,
        font=("Consolas", 10),
        yscrollcommand=scrollbar.set,
    )
    console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=console.yview)

    command_frame = tk.Frame(content)
    command_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
    command_entry = tk.Entry(
        command_frame,
        font=("Consolas", 12),
        state=tk.DISABLED,
    )
    command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    send_button = tk.Button(
        command_frame,
        text="送信",
        width=10,
        command=on_send_command,
        state=tk.DISABLED,
    )
    send_button.pack(side=tk.LEFT, padx=(10, 0))
    command_entry.bind("<Return>", lambda event: on_send_command())

    root.protocol("WM_DELETE_WINDOW", on_close)

    return MainWindow(
        root=root,
        active_profile_label=active_profile_label,
        profile_listbox=profile_listbox,
        status_label=status_label,
        cpu_label=cpu_label,
        ram_label=ram_label,
        uptime_label=uptime_label,
        player_label=player_label,
        start_button=start_button,
        stop_button=stop_button,
        restart_button=restart_button,
        force_stop_button=force_stop_button,
        backup_button=backup_button,
        backup_manage_button=backup_manage_button,
        settings_button=settings_button,
        whitelist_button=whitelist_button,
        auto_backup_var=auto_backup_var,
        console=console,
        command_entry=command_entry,
        send_button=send_button,
    )
