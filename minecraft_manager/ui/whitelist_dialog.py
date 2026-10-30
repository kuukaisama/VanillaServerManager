"""ホワイトリスト管理画面。"""

import tkinter as tk
from tkinter import messagebox


def show_whitelist_dialog(
    root,
    *,
    list_entries,
    is_enabled,
    is_server_running,
    on_set_enabled,
    on_add_player,
    on_remove_player,
):
    window = tk.Toplevel(root)
    window.title("ホワイトリスト管理")
    window.geometry("700x520")
    window.minsize(600, 450)
    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="ホワイトリスト管理",
        font=("Arial", 20, "bold"),
    ).pack(pady=(15, 8))

    status_frame = tk.Frame(window)
    status_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
    status_label = tk.Label(status_frame, text="", font=("Arial", 12, "bold"))
    status_label.pack(side=tk.LEFT)

    toggle_frame = tk.Frame(window)
    toggle_frame.pack(fill=tk.X, padx=20, pady=5)

    list_frame = tk.Frame(window)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    whitelist_listbox = tk.Listbox(
        list_frame,
        font=("Consolas", 11),
        yscrollcommand=scrollbar.set,
    )
    whitelist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=whitelist_listbox.yview)

    input_frame = tk.Frame(window)
    input_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
    player_name_var = tk.StringVar()
    tk.Label(input_frame, text="プレイヤー名:").pack(side=tk.LEFT, padx=(0, 8))
    player_entry = tk.Entry(
        input_frame,
        textvariable=player_name_var,
        font=("Arial", 11),
    )
    player_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    shown_entries = []

    def refresh_list():
        shown_entries.clear()
        whitelist_listbox.delete(0, tk.END)
        shown_entries.extend(list_entries())

        for name, uuid in shown_entries:
            whitelist_listbox.insert(
                tk.END,
                f"{name}    ({uuid})" if uuid else name,
            )

        status_label.config(text="状態: 有効" if is_enabled() else "状態: 無効")
        state = tk.NORMAL if is_server_running() else tk.DISABLED
        add_button.config(state=state)
        remove_button.config(state=state)

    def set_enabled(enabled):
        try:
            on_set_enabled(enabled)
            refresh_list()
        except Exception as error:
            messagebox.showerror(
                "ホワイトリストエラー",
                str(error),
                parent=window,
            )

    def add_player():
        name = player_name_var.get().strip()
        if not name:
            messagebox.showinfo(
                "ホワイトリスト",
                "プレイヤー名を入力してください。",
                parent=window,
            )
            return

        if not is_server_running():
            messagebox.showinfo(
                "ホワイトリスト",
                "プレイヤーの追加はサーバー稼働中に行ってください。",
                parent=window,
            )
            return

        try:
            on_add_player(name)
            player_name_var.set("")
            window.after(1000, refresh_list)
        except Exception as error:
            messagebox.showerror("追加エラー", str(error), parent=window)

    def remove_player():
        selection = whitelist_listbox.curselection()
        if not selection:
            messagebox.showinfo(
                "ホワイトリスト",
                "削除するプレイヤーを選択してください。",
                parent=window,
            )
            return

        if not is_server_running():
            messagebox.showinfo(
                "ホワイトリスト",
                "プレイヤーの削除はサーバー稼働中に行ってください。",
                parent=window,
            )
            return

        index = selection[0]
        if index >= len(shown_entries):
            refresh_list()
            return

        name = shown_entries[index][0]
        if not messagebox.askyesno(
            "ホワイトリスト",
            f"{name} をホワイトリストから削除しますか？",
            parent=window,
        ):
            return

        try:
            on_remove_player(name)
            window.after(1000, refresh_list)
        except Exception as error:
            messagebox.showerror("削除エラー", str(error), parent=window)

    tk.Button(
        toggle_frame,
        text="有効にする",
        width=14,
        command=lambda: set_enabled(True),
    ).pack(side=tk.LEFT, padx=(0, 8))
    tk.Button(
        toggle_frame,
        text="無効にする",
        width=14,
        command=lambda: set_enabled(False),
    ).pack(side=tk.LEFT, padx=8)
    tk.Button(
        toggle_frame,
        text="一覧更新",
        width=14,
        command=refresh_list,
    ).pack(side=tk.LEFT, padx=8)

    add_button = tk.Button(
        input_frame,
        text="追加",
        width=10,
        command=add_player,
    )
    add_button.pack(side=tk.LEFT, padx=(8, 0))
    remove_button = tk.Button(
        window,
        text="選択したプレイヤーを削除",
        width=24,
        command=remove_player,
    )
    remove_button.pack(pady=(0, 8))

    tk.Label(
        window,
        text=(
            "※ プレイヤーの追加・削除はサーバー稼働中に行います。\n"
            "　有効/無効の切り替えは停止中でも保存できます。"
        ),
        justify=tk.LEFT,
        fg="#555555",
    ).pack(pady=(0, 12))

    player_entry.bind("<Return>", lambda event: add_player())
    refresh_list()
