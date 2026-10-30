"""サーバープロファイルの追加・編集画面。"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _memory_in_mb(value, default):
    try:
        text = str(value).strip().upper()
        if text.endswith("G"):
            number = int(text[:-1]) * 1024
        elif text.endswith("M"):
            number = int(text[:-1])
        else:
            number = int(text)
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


def show_profile_dialog(
    root,
    *,
    auto_backup_options,
    on_save,
    profile=None,
):
    editing = profile is not None
    window = tk.Toplevel(root)
    window.title("サーバー設定を編集" if editing else "サーバーを追加")
    window.geometry("720x570")
    window.minsize(650, 530)
    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="サーバー設定を編集" if editing else "サーバーを追加",
        font=("Arial", 20, "bold"),
    ).pack(pady=(18, 12))

    form = tk.Frame(window)
    form.pack(fill=tk.BOTH, expand=True, padx=25)
    form.columnconfigure(1, weight=1)

    name_var = tk.StringVar(value=profile.name if editing else "")
    server_dir_var = tk.StringVar(
        value=str(profile.server_directory) if editing else ""
    )
    backup_dir_var = tk.StringVar(
        value=str(profile.backup_directory) if editing else ""
    )
    jar_var = tk.StringVar(value=profile.jar_file if editing else "server.jar")
    java_var = tk.StringVar(
        value=profile.java_executable if editing else "java"
    )
    minimum_memory_var = tk.StringVar(
        value=str(_memory_in_mb(profile.minimum_memory, 1024)) if editing else "1024"
    )
    maximum_memory_var = tk.StringVar(
        value=str(_memory_in_mb(profile.maximum_memory, 4096)) if editing else "4096"
    )
    auto_backup_var = tk.StringVar(
        value=profile.auto_backup_interval if editing else "無効"
    )

    def add_entry(row, label, variable, browse=None):
        tk.Label(form, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=8
        )
        entry = tk.Entry(form, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=8)
        if browse is not None:
            tk.Button(form, text="参照", width=8, command=browse).grid(
                row=row, column=2, padx=(8, 0), pady=8
            )
        return entry

    def choose_server_directory():
        selected = filedialog.askdirectory(
            title="サーバーディレクトリを選択",
            initialdir=server_dir_var.get() or None,
            parent=window,
        )
        if selected:
            server_dir_var.set(selected)
            if not backup_dir_var.get().strip():
                server_path = Path(selected)
                backup_dir_var.set(str(server_path.parent / f"{server_path.name}_backups"))

    def choose_backup_directory():
        selected = filedialog.askdirectory(
            title="バックアップ保存先を選択",
            initialdir=backup_dir_var.get() or None,
            parent=window,
        )
        if selected:
            backup_dir_var.set(selected)

    def choose_java():
        selected = filedialog.askopenfilename(
            title="Java実行ファイルを選択",
            filetypes=[("Java", "java.exe"), ("すべてのファイル", "*.*")],
            parent=window,
        )
        if selected:
            java_var.set(selected)

    name_entry = add_entry(0, "表示名", name_var)
    add_entry(1, "サーバーディレクトリ", server_dir_var, choose_server_directory)
    add_entry(2, "バックアップ保存先", backup_dir_var, choose_backup_directory)
    add_entry(3, "サーバーJAR", jar_var)
    add_entry(4, "Java実行コマンド", java_var, choose_java)
    add_entry(5, "最小メモリ (MB)", minimum_memory_var)
    add_entry(6, "最大メモリ (MB)", maximum_memory_var)

    tk.Label(form, text="自動バックアップ", anchor="w").grid(
        row=7, column=0, sticky="w", padx=(0, 12), pady=8
    )
    ttk.Combobox(
        form,
        textvariable=auto_backup_var,
        values=list(auto_backup_options.keys()),
        state="readonly",
    ).grid(row=7, column=1, sticky="w", pady=8)

    tk.Label(
        form,
        text=(
            "JavaはサーバーJARを動かす実行環境です。通常は「java」のままで使用できます。\n"
            "メモリはMB単位の整数で入力します（1024MB = 1GB）。\n"
            "登録解除や設定変更でサーバーファイルが削除されることはありません。"
        ),
        justify=tk.LEFT,
        fg="#555555",
    ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 5))

    def submit():
        name = name_var.get().strip()
        server_directory = server_dir_var.get().strip()
        backup_directory = backup_dir_var.get().strip()
        jar_file = jar_var.get().strip()
        java_executable = java_var.get().strip()
        minimum_memory = minimum_memory_var.get().strip()
        maximum_memory = maximum_memory_var.get().strip()

        if not name:
            messagebox.showerror("入力エラー", "表示名を入力してください。", parent=window)
            return
        if not server_directory:
            messagebox.showerror(
                "入力エラー",
                "サーバーディレクトリを選択してください。",
                parent=window,
            )
            return
        if not backup_directory:
            messagebox.showerror(
                "入力エラー",
                "バックアップ保存先を選択してください。",
                parent=window,
            )
            return
        if not jar_file or not java_executable:
            messagebox.showerror(
                "入力エラー",
                "サーバーJARとJavaを入力してください。",
                parent=window,
            )
            return
        try:
            minimum_memory_mb = int(minimum_memory)
        except ValueError:
            messagebox.showerror(
                "入力エラー",
                "最小メモリはMB単位の整数で入力してください。",
                parent=window,
            )
            return
        try:
            maximum_memory_mb = int(maximum_memory)
        except ValueError:
            messagebox.showerror(
                "入力エラー",
                "最大メモリはMB単位の整数で入力してください。",
                parent=window,
            )
            return
        if not 256 <= minimum_memory_mb <= 1048576:
            messagebox.showerror(
                "入力エラー",
                "最小メモリは 256 ～ 1048576 MB の範囲で入力してください。",
                parent=window,
            )
            return
        if not 256 <= maximum_memory_mb <= 1048576:
            messagebox.showerror(
                "入力エラー",
                "最大メモリは 256 ～ 1048576 MB の範囲で入力してください。",
                parent=window,
            )
            return
        if minimum_memory_mb > maximum_memory_mb:
            messagebox.showerror(
                "入力エラー",
                "最小メモリは最大メモリ以下にしてください。",
                parent=window,
            )
            return

        values = {
            "name": name,
            "server_directory": Path(server_directory).expanduser().resolve(),
            "backup_directory": Path(backup_directory).expanduser().resolve(),
            "jar_file": jar_file,
            "java_executable": java_executable,
            "minimum_memory": f"{minimum_memory_mb}M",
            "maximum_memory": f"{maximum_memory_mb}M",
            "auto_backup_interval": auto_backup_var.get(),
        }

        try:
            on_save(values)
        except Exception as error:
            messagebox.showerror("保存エラー", str(error), parent=window)
            return

        window.destroy()

    buttons = tk.Frame(window)
    buttons.pack(pady=(5, 18))
    tk.Button(buttons, text="保存", width=15, command=submit).pack(
        side=tk.LEFT, padx=6
    )
    tk.Button(buttons, text="キャンセル", width=15, command=window.destroy).pack(
        side=tk.LEFT, padx=6
    )

    name_entry.focus_set()
