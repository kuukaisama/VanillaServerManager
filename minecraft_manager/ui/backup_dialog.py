"""バックアップ一覧と復元操作の画面。"""

from datetime import datetime
import tkinter as tk
from tkinter import messagebox


def show_backup_dialog(root, *, list_backups, format_size, on_restore):
    window = tk.Toplevel(root)
    window.title("バックアップ管理")
    window.geometry("850x500")
    window.minsize(650, 400)
    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="バックアップ一覧",
        font=("Arial", 18, "bold"),
    ).pack(pady=15)

    list_frame = tk.Frame(window)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    backup_listbox = tk.Listbox(
        list_frame,
        font=("Consolas", 11),
        yscrollcommand=scrollbar.set,
    )
    backup_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=backup_listbox.yview)

    shown_paths = []

    def refresh():
        shown_paths.clear()
        backup_listbox.delete(0, tk.END)

        for path in list_backups():
            stat = path.stat()
            created = datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y/%m/%d %H:%M:%S"
            )
            size = format_size(stat.st_size)
            backup_listbox.insert(
                tk.END,
                f"{created}   {size:>10}   {path.name}",
            )
            shown_paths.append(path)

    def restore_selected():
        selection = backup_listbox.curselection()
        if not selection:
            messagebox.showinfo(
                "復元",
                "復元するバックアップを選択してください。",
                parent=window,
            )
            return

        on_restore(shown_paths[selection[0]], window)

    button_frame = tk.Frame(window)
    button_frame.pack(pady=(0, 20))
    tk.Button(
        button_frame,
        text="一覧を更新",
        width=15,
        command=refresh,
    ).pack(side=tk.LEFT, padx=8)
    tk.Button(
        button_frame,
        text="選択したバックアップを復元",
        width=25,
        command=restore_selected,
    ).pack(side=tk.LEFT, padx=8)
    tk.Button(
        button_frame,
        text="閉じる",
        width=15,
        command=window.destroy,
    ).pack(side=tk.LEFT, padx=8)

    refresh()
