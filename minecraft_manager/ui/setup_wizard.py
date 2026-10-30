"""新規Minecraftサーバーの初期設定ウィザード。"""

from pathlib import Path
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


INVALID_WORLD_NAME = re.compile(r"[<>:\"/\\|?*]")
WORLD_TYPES = {
    "通常": (
        "minecraft:normal",
        "標準的な地形を生成します。通常のサバイバルにはこの設定がおすすめです。",
    ),
    "フラット": (
        "minecraft:flat",
        "ほぼ平らな地形を生成します。建築やテスト用のワールドに向いています。",
    ),
    "巨大バイオーム": (
        "minecraft:large_biomes",
        "通常より大きなバイオームを生成します。地形の種類が切り替わる間隔が広くなります。",
    ),
    "増幅": (
        "minecraft:amplified",
        "高低差の激しい地形を生成します。負荷が高くなる場合があります。",
    ),
}


def show_setup_wizard(
    root,
    *,
    auto_backup_options,
    world_version_directory,
    on_refresh_jars=None,
    on_create,
):
    world_version_directory = Path(world_version_directory).resolve()
    world_version_directory.mkdir(parents=True, exist_ok=True)

    window = tk.Toplevel(root)
    window.title("新規サーバー作成")
    window.geometry("800x690")
    window.minsize(720, 640)
    window.transient(root)
    window.grab_set()

    title_label = tk.Label(window, font=("Arial", 20, "bold"))
    title_label.pack(pady=(18, 3))
    step_label = tk.Label(window, font=("Arial", 10), fg="#555555")
    step_label.pack(pady=(0, 12))

    page_container = tk.Frame(window)
    page_container.pack(fill=tk.BOTH, expand=True, padx=30)
    pages = []

    def new_page():
        page = tk.Frame(page_container)
        page.columnconfigure(1, weight=1)
        pages.append(page)
        return page

    basic_page = new_page()
    world_page = new_page()
    network_page = new_page()
    gameplay_page = new_page()

    name_var = tk.StringVar()
    server_dir_var = tk.StringVar()
    backup_dir_var = tk.StringVar()
    jar_source_var = tk.StringVar()
    java_var = tk.StringVar(value="java")
    minimum_memory_var = tk.StringVar(value="1024")
    maximum_memory_var = tk.StringVar(value="4096")
    auto_backup_var = tk.StringVar(value="無効")

    level_name_var = tk.StringVar(value="world")
    seed_var = tk.StringVar()
    level_type_var = tk.StringVar(value="通常")
    world_type_description_var = tk.StringVar(value=WORLD_TYPES["通常"][1])
    gamemode_var = tk.StringVar(value="survival")
    difficulty_var = tk.StringVar(value="normal")
    hardcore_var = tk.BooleanVar(value=False)
    structures_var = tk.BooleanVar(value=True)

    port_var = tk.StringVar(value="25565")
    max_players_var = tk.StringVar(value="20")
    motd_var = tk.StringVar(value="A Minecraft Server")
    online_mode_var = tk.BooleanVar(value=True)
    whitelist_var = tk.BooleanVar(value=False)
    enforce_whitelist_var = tk.BooleanVar(value=False)

    pvp_var = tk.BooleanVar(value=True)
    allow_flight_var = tk.BooleanVar(value=False)
    command_block_var = tk.BooleanVar(value=False)
    spawn_protection_var = tk.StringVar(value="16")
    view_distance_var = tk.StringVar(value="10")
    simulation_distance_var = tk.StringVar(value="10")
    eula_var = tk.BooleanVar(value=False)

    def add_entry(page, row, label, variable, browse=None):
        tk.Label(page, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=8
        )
        tk.Entry(page, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=8
        )
        if browse is not None:
            tk.Button(page, text="参照", width=8, command=browse).grid(
                row=row, column=2, padx=(8, 0), pady=8
            )

    def add_combo(page, row, label, variable, values):
        tk.Label(page, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=8
        )
        combo = ttk.Combobox(
            page,
            textvariable=variable,
            values=values,
            state="readonly",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=8)
        return combo

    def add_check(page, row, text, variable):
        tk.Checkbutton(page, text=text, variable=variable, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=6
        )

    def choose_server_directory():
        selected = filedialog.askdirectory(
            title="新しいサーバーの作成先",
            parent=window,
        )
        if selected:
            server_dir_var.set(selected)
            server_path = Path(selected)
            if not backup_dir_var.get().strip():
                backup_dir_var.set(
                    str(server_path.parent / f"{server_path.name}_backups")
                )

    def choose_backup_directory():
        selected = filedialog.askdirectory(
            title="バックアップ保存先",
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

    add_entry(basic_page, 0, "表示名", name_var)
    add_entry(basic_page, 1, "作成先", server_dir_var, choose_server_directory)
    add_entry(basic_page, 2, "バックアップ保存先", backup_dir_var, choose_backup_directory)

    tk.Label(basic_page, text="公式サーバーJAR", anchor="w").grid(
        row=3, column=0, sticky="w", padx=(0, 12), pady=8
    )
    jar_combo = ttk.Combobox(
        basic_page,
        textvariable=jar_source_var,
        state="readonly",
    )
    jar_combo.grid(row=3, column=1, sticky="ew", pady=8)

    def refresh_jar_list():
        try:
            if on_refresh_jars is not None:
                on_refresh_jars()
        except Exception as error:
            messagebox.showerror(
                "JAR一覧の更新エラー",
                "公式サーバーJARを読み込めませんでした。\n\n" + str(error),
                parent=window,
            )
            return

        jar_names = sorted(
            (path.name for path in world_version_directory.glob("*.jar")),
            key=str.casefold,
        )
        jar_combo.configure(values=jar_names)
        if jar_source_var.get() not in jar_names:
            jar_source_var.set(jar_names[0] if jar_names else "")

    def open_jar_directory():
        try:
            world_version_directory.mkdir(parents=True, exist_ok=True)
            os.startfile(str(world_version_directory))
        except OSError as error:
            messagebox.showerror(
                "保存先を開けません",
                str(error),
                parent=window,
            )

    jar_buttons = tk.Frame(basic_page)
    jar_buttons.grid(row=3, column=2, padx=(8, 0), pady=8)
    tk.Button(
        jar_buttons,
        text="保存先を開く",
        width=11,
        command=open_jar_directory,
    ).pack(side=tk.LEFT)
    tk.Button(
        jar_buttons,
        text="一覧更新",
        width=8,
        command=refresh_jar_list,
    ).pack(side=tk.LEFT, padx=(5, 0))
    tk.Label(
        basic_page,
        text=(
            "公式JARをこのフォルダーへ入れてから選択してください：\n"
            "VanillaServerManager/worldversion\n"
            "旧プロジェクトフォルダーのworldversion内のJARも、"
            "一覧更新時に自動で取り込みます。"
        ),
        justify=tk.LEFT,
        fg="#555555",
        wraplength=680,
    ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 5))

    add_entry(basic_page, 5, "Java実行コマンド", java_var, choose_java)
    tk.Label(
        basic_page,
        text=(
            "JavaはMinecraftサーバーJARを動かすための実行環境です。通常は「java」のままで使えます。\n"
            "Javaが見つからない場合や複数バージョンを使い分ける場合だけ、java.exeを指定してください。"
        ),
        justify=tk.LEFT,
        fg="#555555",
        wraplength=680,
    ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 5))
    add_entry(basic_page, 7, "最小メモリ (MB)", minimum_memory_var)
    add_entry(basic_page, 8, "最大メモリ (MB)", maximum_memory_var)
    tk.Label(
        basic_page,
        text="メモリはMB単位の整数で入力します（1024MB = 1GB）。",
        fg="#555555",
    ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 5))
    add_combo(
        basic_page,
        10,
        "自動バックアップ",
        auto_backup_var,
        list(auto_backup_options.keys()),
    )

    add_entry(world_page, 0, "ワールド名", level_name_var)
    add_entry(world_page, 1, "Seed値（空欄でランダム）", seed_var)
    world_type_combo = add_combo(
        world_page,
        2,
        "ワールドタイプ",
        level_type_var,
        list(WORLD_TYPES.keys()),
    )
    tk.Label(
        world_page,
        textvariable=world_type_description_var,
        justify=tk.LEFT,
        fg="#555555",
        wraplength=650,
    ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 8))

    def update_world_type_description(_event=None):
        world_type_description_var.set(WORLD_TYPES[level_type_var.get()][1])

    world_type_combo.bind("<<ComboboxSelected>>", update_world_type_description)
    add_combo(
        world_page,
        4,
        "ゲームモード",
        gamemode_var,
        ["survival", "creative", "adventure", "spectator"],
    )
    add_combo(
        world_page,
        5,
        "難易度",
        difficulty_var,
        ["peaceful", "easy", "normal", "hard"],
    )
    add_check(world_page, 6, "ハードコアモード", hardcore_var)
    add_check(world_page, 7, "構造物を生成する", structures_var)

    add_entry(network_page, 0, "サーバーポート", port_var)
    add_entry(network_page, 1, "最大プレイヤー数", max_players_var)
    add_entry(network_page, 2, "MOTD（サーバー説明）", motd_var)
    add_check(network_page, 3, "オンライン認証を有効にする", online_mode_var)
    add_check(network_page, 4, "ホワイトリストを有効にする", whitelist_var)
    add_check(network_page, 5, "ホワイトリストを強制する", enforce_whitelist_var)
    tk.Label(
        network_page,
        text="※ online-mode は通常ONのまま使用してください。",
        fg="#555555",
    ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(15, 0))

    add_check(gameplay_page, 0, "PvPを有効にする", pvp_var)
    add_check(gameplay_page, 1, "飛行を許可する", allow_flight_var)
    add_check(gameplay_page, 2, "コマンドブロックを有効にする", command_block_var)
    add_entry(gameplay_page, 3, "スポーン保護範囲", spawn_protection_var)
    add_entry(gameplay_page, 4, "描画距離", view_distance_var)
    add_entry(gameplay_page, 5, "シミュレーション距離", simulation_distance_var)
    add_check(
        gameplay_page,
        6,
        "Minecraft EULAを確認し、同意します",
        eula_var,
    )
    tk.Label(
        gameplay_page,
        text=(
            "EULAへ同意しない場合もファイルは作成できますが、\n"
            "同意するまでMinecraftサーバーは起動しません。"
        ),
        justify=tk.LEFT,
        fg="#555555",
    ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))

    page_titles = [
        "基本設定",
        "ワールド設定",
        "接続設定",
        "ゲーム・パフォーマンス",
    ]
    current_page = 0

    navigation = tk.Frame(window)
    navigation.pack(fill=tk.X, padx=30, pady=(10, 20))
    back_button = tk.Button(navigation, text="戻る", width=12)
    back_button.pack(side=tk.LEFT)
    next_button = tk.Button(navigation, text="次へ", width=12)
    next_button.pack(side=tk.RIGHT)
    cancel_button = tk.Button(
        navigation,
        text="キャンセル",
        width=12,
        command=window.destroy,
    )
    cancel_button.pack(side=tk.RIGHT, padx=8)

    def show_page(index):
        nonlocal current_page
        pages[current_page].pack_forget()
        current_page = index
        pages[current_page].pack(fill=tk.BOTH, expand=True)
        title_label.config(text=page_titles[current_page])
        step_label.config(text=f"ステップ {current_page + 1} / {len(pages)}")
        back_button.config(state=tk.NORMAL if current_page else tk.DISABLED)
        next_button.config(
            text="作成" if current_page == len(pages) - 1 else "次へ"
        )

    def parse_integer(variable, label, minimum, maximum):
        try:
            number = int(variable.get().strip())
        except ValueError as error:
            raise ValueError(f"{label}は整数で入力してください。") from error
        if not minimum <= number <= maximum:
            raise ValueError(
                f"{label}は {minimum} ～ {maximum} の範囲で入力してください。"
            )
        return str(number)

    def create_server():
        try:
            name = name_var.get().strip()
            server_directory = server_dir_var.get().strip()
            backup_directory = backup_dir_var.get().strip()
            jar_name = jar_source_var.get().strip()
            jar_source = (world_version_directory / jar_name).resolve()
            java_executable = java_var.get().strip()
            level_name = level_name_var.get().strip()

            if not name or not server_directory or not backup_directory:
                raise ValueError("表示名、作成先、バックアップ保存先を入力してください。")
            if (
                not jar_name
                or jar_source.parent != world_version_directory
                or jar_source.suffix.lower() != ".jar"
                or not jar_source.is_file()
            ):
                raise ValueError(
                    "worldversionフォルダー内の有効な公式サーバーJARを選択してください。"
                )
            if not java_executable:
                raise ValueError("Java実行ファイルを入力してください。")
            minimum_memory = parse_integer(
                minimum_memory_var, "最小メモリ (MB)", 256, 1048576
            )
            maximum_memory = parse_integer(
                maximum_memory_var, "最大メモリ (MB)", 256, 1048576
            )
            if int(minimum_memory) > int(maximum_memory):
                raise ValueError("最小メモリは最大メモリ以下にしてください。")
            if (
                not level_name
                or level_name in {".", ".."}
                or INVALID_WORLD_NAME.search(level_name)
            ):
                raise ValueError("ワールド名に使用できない文字が含まれています。")

            properties = {
                "allow-flight": _bool_text(allow_flight_var.get()),
                "difficulty": difficulty_var.get(),
                "enable-command-block": _bool_text(command_block_var.get()),
                "enable-status": "true",
                "enforce-whitelist": _bool_text(
                    whitelist_var.get() and enforce_whitelist_var.get()
                ),
                "force-gamemode": "false",
                "gamemode": gamemode_var.get(),
                "generate-structures": _bool_text(structures_var.get()),
                "hardcore": _bool_text(hardcore_var.get()),
                "level-name": level_name,
                "level-seed": seed_var.get().strip(),
                "level-type": WORLD_TYPES[level_type_var.get()][0].replace(
                    ":", "\\:"
                ),
                "max-players": parse_integer(max_players_var, "最大プレイヤー数", 1, 100000),
                "motd": motd_var.get().strip(),
                "online-mode": _bool_text(online_mode_var.get()),
                "pvp": _bool_text(pvp_var.get()),
                "server-port": parse_integer(port_var, "サーバーポート", 1, 65535),
                "simulation-distance": parse_integer(
                    simulation_distance_var, "シミュレーション距離", 1, 1000
                ),
                "spawn-protection": parse_integer(
                    spawn_protection_var, "スポーン保護範囲", 0, 100000
                ),
                "view-distance": parse_integer(view_distance_var, "描画距離", 1, 1000),
                "white-list": _bool_text(whitelist_var.get()),
            }

            values = {
                "name": name,
                "server_directory": Path(server_directory).expanduser().resolve(),
                "backup_directory": Path(backup_directory).expanduser().resolve(),
                "jar_file": "server.jar",
                "java_executable": java_executable,
                "minimum_memory": f"{minimum_memory}M",
                "maximum_memory": f"{maximum_memory}M",
                "auto_backup_interval": auto_backup_var.get(),
            }

            if not eula_var.get() and not messagebox.askyesno(
                "EULA未同意",
                "EULA未同意の状態で作成します。\n"
                "同意するまでサーバーは起動しません。続行しますか？",
                parent=window,
            ):
                return

            on_create(values, jar_source, properties, eula_var.get())
        except Exception as error:
            messagebox.showerror("作成エラー", str(error), parent=window)
            return

        window.destroy()

    def go_next():
        if current_page == len(pages) - 1:
            create_server()
        else:
            show_page(current_page + 1)

    back_button.config(command=lambda: show_page(current_page - 1))
    next_button.config(command=go_next)
    refresh_jar_list()
    pages[0].pack(fill=tk.BOTH, expand=True)
    show_page(0)


def _bool_text(value):
    return "true" if value else "false"
