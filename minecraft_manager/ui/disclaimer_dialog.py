"""初回起動時に表示する免責事項の同意画面。"""

import tkinter as tk
from tkinter import scrolledtext


def show_disclaimer_dialog(root, *, disclaimer_text, app_version, app_name):
    accepted = False
    window = tk.Toplevel(root)
    window.title(f"{app_name} {app_version} - 免責事項")
    window.geometry("760x650")
    window.minsize(660, 560)
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.grab_set()

    tk.Label(
        window,
        text="免責事項への同意",
        font=("Arial", 20, "bold"),
    ).pack(pady=(18, 6))
    tk.Label(
        window,
        text="本ソフトウェアを使用するには、以下を確認して同意する必要があります。",
        fg="#444444",
    ).pack(pady=(0, 10))

    text = scrolledtext.ScrolledText(
        window,
        wrap=tk.WORD,
        font=("Yu Gothic UI", 10),
        padx=12,
        pady=12,
    )
    text.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))
    text.insert("1.0", disclaimer_text)
    text.config(state=tk.DISABLED)

    agreement_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        window,
        text="上記の免責事項を読み、内容に同意します。",
        variable=agreement_var,
        anchor="w",
    ).pack(fill=tk.X, padx=28, pady=(0, 10))

    buttons = tk.Frame(window)
    buttons.pack(pady=(0, 18))

    def accept():
        nonlocal accepted
        if not agreement_var.get():
            return
        accepted = True
        window.destroy()

    accept_button = tk.Button(
        buttons,
        text="同意して開始",
        width=18,
        state=tk.DISABLED,
        command=accept,
    )
    accept_button.pack(side=tk.LEFT, padx=6)
    tk.Button(
        buttons,
        text="同意しない（終了）",
        width=18,
        command=window.destroy,
    ).pack(side=tk.LEFT, padx=6)

    def update_accept_button(*_args):
        accept_button.config(
            state=tk.NORMAL if agreement_var.get() else tk.DISABLED
        )

    agreement_var.trace_add("write", update_accept_button)
    window.wait_window()
    return accepted
