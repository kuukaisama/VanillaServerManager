"""server.properties設定画面。"""

import tkinter as tk
from tkinter import messagebox, ttk


def show_settings_dialog(
    root,
    *,
    properties,
    is_server_running,
    on_save,
    on_apply,
):
    window = tk.Toplevel(root)
    window.title("サーバー設定")
    window.geometry("700x650")
    window.minsize(620, 560)
    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="サーバー設定",
        font=("Arial", 20, "bold"),
    ).pack(pady=(15, 5))
    tk.Label(
        window,
        text="保存した設定は、基本的にサーバーを再起動した後に反映されます。",
        font=("Arial", 10),
    ).pack(pady=(0, 10))

    notebook = ttk.Notebook(window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
    game_tab = ttk.Frame(notebook)
    connection_tab = ttk.Frame(notebook)
    performance_tab = ttk.Frame(notebook)
    notebook.add(game_tab, text="ゲーム")
    notebook.add(connection_tab, text="接続・公開")
    notebook.add(performance_tab, text="パフォーマンス")

    variables = {}

    def add_combo(parent, row, label, key, values, default):
        tk.Label(parent, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=15, pady=10
        )
        variable = tk.StringVar(value=properties.get(key, default))
        ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            width=28,
        ).grid(row=row, column=1, sticky="ew", padx=15, pady=10)
        variables[key] = variable

    def add_entry(parent, row, label, key, default):
        tk.Label(parent, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=15, pady=10
        )
        variable = tk.StringVar(value=properties.get(key, default))
        tk.Entry(parent, textvariable=variable, width=32).grid(
            row=row, column=1, sticky="ew", padx=15, pady=10
        )
        variables[key] = variable

    def add_check(parent, row, label, key, default="false"):
        variable = tk.BooleanVar(
            value=properties.get(key, default).lower() == "true"
        )
        tk.Checkbutton(
            parent,
            text=label,
            variable=variable,
            anchor="w",
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=15,
            pady=8,
        )
        variables[key] = variable

    for tab in (game_tab, connection_tab, performance_tab):
        tab.columnconfigure(1, weight=1)

    add_combo(
        game_tab,
        0,
        "難易度",
        "difficulty",
        ["peaceful", "easy", "normal", "hard"],
        "easy",
    )
    add_combo(
        game_tab,
        1,
        "ゲームモード",
        "gamemode",
        ["survival", "creative", "adventure", "spectator"],
        "survival",
    )
    add_entry(game_tab, 2, "MOTD（サーバー説明）", "motd", "A Minecraft Server")
    add_entry(game_tab, 3, "スポーン保護範囲", "spawn-protection", "16")
    add_check(game_tab, 4, "PvPを有効にする", "pvp", "true")
    add_check(game_tab, 5, "飛行を許可する", "allow-flight", "false")
    add_check(game_tab, 6, "ハードコアモード", "hardcore", "false")
    add_check(
        game_tab,
        7,
        "コマンドブロックを有効にする",
        "enable-command-block",
        "false",
    )

    add_entry(connection_tab, 0, "最大プレイヤー数", "max-players", "20")
    add_entry(connection_tab, 1, "サーバーポート", "server-port", "25565")
    add_check(connection_tab, 2, "オンライン認証を有効にする", "online-mode", "true")
    add_check(connection_tab, 3, "ホワイトリストを有効にする", "white-list", "false")
    add_check(
        connection_tab,
        4,
        "ホワイトリストを強制する",
        "enforce-whitelist",
        "false",
    )
    tk.Label(
        connection_tab,
        text=(
            "※ online-mode は通常ONのまま使用してください。\n"
            "　変更内容はサーバー再起動後に反映されます。"
        ),
        justify=tk.LEFT,
        fg="#555555",
    ).grid(
        row=5,
        column=0,
        columnspan=2,
        sticky="w",
        padx=15,
        pady=(15, 5),
    )

    add_entry(performance_tab, 0, "描画距離（view-distance）", "view-distance", "10")
    add_entry(performance_tab, 1, "シミュレーション距離", "simulation-distance", "10")
    tk.Label(
        performance_tab,
        text=(
            "数値を大きくすると、サーバーPCの負荷やメモリ使用量が増える場合があります。\n"
            "まずは現在値を基準に調整してください。"
        ),
        justify=tk.LEFT,
        fg="#555555",
    ).grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="w",
        padx=15,
        pady=15,
    )

    def collect_changes():
        changes = {}
        for key, variable in variables.items():
            if isinstance(variable, tk.BooleanVar):
                changes[key] = "true" if variable.get() else "false"
            else:
                changes[key] = variable.get().strip()

        integer_fields = {
            "max-players": (1, 100000, "最大プレイヤー数"),
            "server-port": (1, 65535, "サーバーポート"),
            "spawn-protection": (0, 100000, "スポーン保護範囲"),
            "view-distance": (1, 1000, "描画距離"),
            "simulation-distance": (1, 1000, "シミュレーション距離"),
        }

        for key, (minimum, maximum, display_name) in integer_fields.items():
            try:
                number = int(changes[key])
            except ValueError as error:
                raise ValueError(
                    f"{display_name} は整数で入力してください。"
                ) from error

            if not minimum <= number <= maximum:
                raise ValueError(
                    f"{display_name} は {minimum} ～ {maximum} の範囲で入力してください。"
                )
            changes[key] = str(number)

        return changes

    def save_settings(restart_after=False):
        try:
            on_save(collect_changes())
        except Exception as error:
            messagebox.showerror(
                "設定保存エラー",
                str(error),
                parent=window,
            )
            return

        running = is_server_running()
        if restart_after:
            window.destroy()
            on_apply()
            return

        if running:
            message = (
                "設定を保存しました。\n\n"
                "現在サーバーが稼働中なので、反映するには再起動してください。"
            )
        else:
            message = "設定を保存しました。\n次回サーバー起動時に反映されます。"

        messagebox.showinfo("設定を保存しました", message, parent=window)

    button_frame = tk.Frame(window)
    button_frame.pack(pady=(5, 18))
    tk.Button(
        button_frame,
        text="保存",
        width=16,
        command=lambda: save_settings(False),
    ).pack(side=tk.LEFT, padx=6)
    tk.Button(
        button_frame,
        text="保存して再起動" if is_server_running() else "保存して起動",
        width=16,
        command=lambda: save_settings(True),
    ).pack(side=tk.LEFT, padx=6)
    tk.Button(
        button_frame,
        text="閉じる",
        width=12,
        command=window.destroy,
    ).pack(side=tk.LEFT, padx=6)
