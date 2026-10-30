"""実サーバーを使わず、復元・設定・画面制御の回帰を検証する。"""

import json
from pathlib import Path
import queue
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from minecraft_manager import app, backup, migration, server
from minecraft_manager.config import read_properties_map, write_properties
from minecraft_manager.profiles import ProfileStore, create_profile
from minecraft_manager.server import ServerController
from minecraft_manager.setup import create_server_files


class TemporaryDataTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.profile = create_profile("Test", self.base / "server", self.base / "backups")
        self.server = self.profile.server_directory
        self.server.mkdir()

    def write(self, relative, data=b"current"):
        path = self.server / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def snapshot(self):
        return {str(p.relative_to(self.server)): p.read_bytes()
                for p in self.server.rglob("*") if p.is_file()}

    def archive(self, level_name="world", metadata=True, extra=None):
        path = self.base / "backup.zip"
        with zipfile.ZipFile(path, "w") as out:
            if metadata:
                out.writestr("server_manager_backup.json", json.dumps({"level_name": level_name}))
            out.writestr("world/level.dat", b"restored-world")
            out.writestr("server.properties", b"level-name=world\nmotd=restored\n")
            out.writestr("whitelist.json", b"[]")
            for name, data in (extra or {}).items():
                out.writestr(name, data)
        return path


class BackupTests(TemporaryDataTest):
    def test_rejects_metadata_paths_before_modifying_data(self):
        sentinel = self.base / "outside.txt"
        sentinel.write_bytes(b"unchanged")
        self.write("world/level.dat")
        before = self.snapshot()
        for name in ("../victim", "..\\victim", str(self.base), "C:\\victim",
                     "C:victim", "world:stream", ".", "..", "", None, [], "world.", "NUL"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    backup.restore_backup(self.profile, self.archive(name))
                self.assertEqual(before, self.snapshot())
                self.assertEqual(b"unchanged", sentinel.read_bytes())

    def test_zip_traversal_rejected(self):
        self.write("world/level.dat")
        before = self.snapshot()
        for name in ("../escape.txt", "..\\escape.txt", "C:/escape.txt"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    backup.restore_backup(self.profile, self.archive(extra={name: b"bad"}))
                self.assertEqual(before, self.snapshot())

    def test_restore_success_with_and_without_metadata(self):
        for metadata in (True, False):
            with self.subTest(metadata=metadata):
                self.write("world/level.dat")
                self.write("server.properties")
                backup.restore_backup(self.profile, self.archive(metadata=metadata))
                self.assertEqual(b"restored-world", (self.server / "world/level.dat").read_bytes())
                self.assertEqual(b"[]", (self.server / "whitelist.json").read_bytes())
                self.assertIn(b"motd=restored", (self.server / "server.properties").read_bytes())
                self.assertFalse(list(self.server.glob(".restore_*")))

    def test_staging_failure_leaves_world_and_all_settings_unchanged(self):
        self.write("world/level.dat")
        self.write("server.properties")
        self.write("whitelist.json", b"current-whitelist")
        before = self.snapshot()
        real_copy = shutil.copy2

        def fail_one(source, destination, *args, **kwargs):
            if Path(source).name == "whitelist.json":
                raise OSError("simulated disk full")
            return real_copy(source, destination, *args, **kwargs)

        with patch.object(backup.shutil, "copy2", side_effect=fail_one):
            with self.assertRaises(OSError):
                backup.restore_backup(self.profile, self.archive())
        self.assertEqual(before, self.snapshot())

    def test_commit_failure_rolls_back_world_settings_and_new_files(self):
        # 新規ワールド/設定を追加した場合も失敗時には元の不存在へ戻す。
        for existing_world in (True, False):
            for existing_properties in (True, False):
                with self.subTest(world=existing_world, properties=existing_properties):
                    if existing_world:
                        self.write("world/level.dat")
                    if existing_properties:
                        self.write("server.properties", b"old-properties")
                    self.write("whitelist.json", b"old-whitelist")
                    before = self.snapshot()
                    real_replace = Path.replace

                    def fail_one(path, target):
                        if path.parent.name == "staged" and path.name == "whitelist.json":
                            raise OSError("simulated locked file")
                        return real_replace(path, target)

                    with patch.object(Path, "replace", fail_one):
                        with self.assertRaises(OSError):
                            backup.restore_backup(self.profile, self.archive())
                    self.assertEqual(before, self.snapshot())
                    shutil.rmtree(self.server)
                    self.server.mkdir()

    def test_failed_rollback_keeps_recovery_data(self):
        self.write("world/level.dat", b"original-world")
        self.write("server.properties", b"original-settings")
        real_replace = Path.replace

        def fail_commit_and_rollback(path, target):
            if (path.parent.name == "staged" and path.name == "server.properties") or (
                path.parent.name == "originals" and path.name == "world"
            ):
                raise OSError("simulated lock")
            return real_replace(path, target)

        with patch.object(Path, "replace", fail_commit_and_rollback):
            with self.assertRaises(RuntimeError):
                backup.restore_backup(self.profile, self.archive())
        recovery = list(self.server.glob(".restore_*"))
        self.assertEqual(1, len(recovery))
        self.assertEqual(b"original-world", (recovery[0] / "originals/world/level.dat").read_bytes())
        self.assertEqual(b"original-settings", (self.server / "server.properties").read_bytes())

    def test_world_backup_directory_rejected_before_creation_or_commands(self):
        self.write("world/level.dat")
        for directory in (self.server / "world", self.server / "world/nested/backups"):
            with self.subTest(directory=directory):
                self.profile.backup_directory = directory
                process = Mock()
                process.poll.return_value = None
                with self.assertRaises(ValueError):
                    backup.create_backup(self.profile, "world", process=process)
                process.stdin.write.assert_not_called()
                self.assertFalse(list(self.server.rglob("*.zip")))
        self.assertFalse((self.server / "world/nested").exists())

    def test_valid_backup_roundtrip(self):
        self.write("world/level.dat", b"saved-world")
        self.write("world/session.lock")
        self.write("server.properties", b"level-name=world\n")
        path = backup.create_backup(self.profile, "world")
        self.write("world/level.dat", b"modified-world")
        backup.restore_backup(self.profile, path)
        self.assertEqual(b"saved-world", (self.server / "world/level.dat").read_bytes())
        with zipfile.ZipFile(path) as archive:
            self.assertNotIn("world/session.lock", archive.namelist())

    def test_pre_restore_backup_has_distinct_name_and_metadata(self):
        self.write("world/level.dat", b"saved-world")
        path = backup.create_backup(
            self.profile,
            "world",
            backup_type="pre_restore",
        )
        self.assertTrue(path.name.startswith("pre_restore_world_"))
        with zipfile.ZipFile(path) as archive:
            metadata = json.loads(archive.read("server_manager_backup.json"))
        self.assertEqual("pre_restore", metadata["backup_type"])

    def test_restore_rejects_insufficient_disk_space_before_changes(self):
        self.write("world/level.dat", b"current")
        before = self.snapshot()
        usage = shutil._ntuple_diskusage(total=100, used=99, free=1)
        with patch.object(backup.shutil, "disk_usage", return_value=usage):
            with self.assertRaisesRegex(OSError, "空き容量"):
                backup.restore_backup(self.profile, self.archive())
        self.assertEqual(before, self.snapshot())
        self.assertFalse(list(self.server.glob(".restore_*")))

    def test_new_server_rejects_nested_backup_before_writing(self):
        self.profile.backup_directory = self.server / "world/backups"
        with self.assertRaises(ValueError):
            create_server_files(self.profile, self.base / "missing.jar", {"level-name": "world"}, False)
        self.assertEqual({}, self.snapshot())


class ProfileTests(TemporaryDataTest):
    def store(self):
        return ProfileStore(self.base / "profiles.json", self.base)

    def test_clean_install_has_no_phantom_profile(self):
        with patch("minecraft_manager.profiles.create_default_profile", return_value=self.profile):
            self.assertEqual([], self.store().load())
            self.write("server.jar", b"existing")
            self.assertEqual([self.profile], self.store().load())

    def test_saved_empty_list_does_not_reregister_existing_server(self):
        self.write("server.jar", b"existing")
        self.store().save([])
        with patch("minecraft_manager.profiles.create_default_profile", return_value=self.profile):
            self.assertEqual([], self.store().load())

    def test_unreadable_or_future_settings_cannot_be_overwritten(self):
        for content in (b'{broken', b'{"schema_version": 99, "profiles": []}', b'\xff\xfe'):
            with self.subTest(content=content):
                store = self.store()
                store.path.write_bytes(content)
                with self.assertRaises(ValueError):
                    store.load()
                with self.assertRaises(ValueError):
                    store.save([self.profile])
                self.assertEqual(content, store.path.read_bytes())

    def test_old_format_still_loads_and_saves(self):
        store = self.store()
        store.path.write_text(json.dumps([self.profile.to_dict(self.base)]), encoding="utf-8")
        profiles = store.load()
        store.save(profiles)
        self.assertEqual(self.profile, store.load()[0])
        self.assertEqual(1, json.loads(store.path.read_text(encoding="utf-8"))["schema_version"])

    def test_japanese_motd_roundtrip_uses_utf8(self):
        properties = self.server / "server.properties"
        properties.write_text("motd=old\nmax-players=20\n", encoding="utf-8")
        motd = "日本語サーバーへようこそ！"
        write_properties({"motd": motd}, profile=self.profile)
        self.assertEqual(motd, read_properties_map(profile=self.profile)["motd"])
        self.assertIn(motd.encode("utf-8"), properties.read_bytes())


class ServerOutputTests(unittest.TestCase):
    def run_stream(self, lines):
        process = Mock(stdout=lines)
        process.wait.return_value = 0
        events = queue.Queue()
        save_complete = Mock()
        server.stream_server_output(process, events, save_complete)
        queued = []
        while not events.empty():
            queued.append(events.get_nowait())
        return process, queued, save_complete

    def test_exact_server_messages_are_recognized(self):
        lines = [
            '[12:34:56] [Server thread/INFO]: Done (1.234s)! For help, type "help"\n',
            "[12:34:57] [Server thread/INFO]: Saved the game\n",
            "[12:34:58] [Server thread/INFO]: Steve joined the game\n",
            "[12:34:59] [Server thread/INFO]: Steve left the game\n",
        ]
        process, events, save_complete = self.run_stream(lines)
        self.assertIn(("STATUS", "RUNNING"), events)
        self.assertIn(("PLAYER_JOIN", "Steve"), events)
        self.assertIn(("PLAYER_LEAVE", "Steve"), events)
        self.assertEqual(("STATUS", "STOPPED"), events[-1])
        save_complete.set.assert_called_once()
        process.wait.assert_called_once()

    def test_chat_cannot_spoof_status_save_or_player_events(self):
        lines = [
            "[12:34:56] [Server thread/INFO]: <Eve> Steve joined the game\n",
            "[12:34:57] [Server thread/INFO]: <Eve> Saved the game\n",
            '[12:34:58] [Server thread/INFO]: <Eve> Done (1.0s)! For help, type "help"\n',
        ]
        _process, events, save_complete = self.run_stream(lines)
        event_types = [event[0] for event in events if event[0] != "LOG"]
        self.assertEqual(["STATUS"], event_types)
        self.assertEqual(("STATUS", "STOPPED"), events[-1])
        save_complete.set.assert_not_called()


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.old = self.base / "minecraft_maneger"
        self.intermediate = self.base / "MinecraftServerManager"
        self.new = self.base / "VanillaServerManager"
        self.project = self.base / "project"
        self.old.mkdir()
        self.project.mkdir()

    def migration_patch(self):
        return patch.multiple(
            migration,
            LEGACY_USER_DATA_DIRS=(self.intermediate, self.old),
            USER_DATA_DIR=self.new,
            PROFILES_FILE=self.new / "profiles.json",
            DEFAULT_SERVER_DIR=self.new / "server",
            DEFAULT_BACKUP_DIR=self.new / "backups",
            WORLD_VERSION_DIR=self.new / "worldversion",
            PROJECT_DIR=self.project,
            LEGACY_PROFILES_FILE=self.project / "profiles.json",
            LEGACY_SERVER_DIR=self.project / "server",
            LEGACY_BACKUP_DIR=self.project / "backups",
            LEGACY_WORLD_VERSION_DIR=self.project / "worldversion",
        )

    def test_misspelled_app_data_is_copied_and_profiles_are_rebased(self):
        self.intermediate.mkdir()
        (self.intermediate / "intermediate-only.txt").write_text(
            "migrated",
            encoding="utf-8",
        )
        (self.old / "server/world").mkdir(parents=True)
        (self.old / "server/world/level.dat").write_bytes(b"world-data")
        (self.old / "backups").mkdir()
        (self.old / "backups/world.zip").write_bytes(b"backup-data")
        (self.old / "worldversion").mkdir()
        (self.old / "worldversion/server.jar").write_bytes(b"jar-data")
        (self.old / "settings.json").write_text(
            json.dumps({"disclaimer_accepted": True}),
            encoding="utf-8",
        )

        profile = create_profile(
            "Existing",
            self.old / "server",
            self.old / "backups",
        )
        profile_data = profile.to_dict(self.old)
        # 旧版で絶対パスとして記録された場合も移行できることを確認する。
        profile_data["server_directory"] = str(self.old / "server")
        (self.old / "profiles.json").write_text(
            json.dumps({"schema_version": 1, "profiles": [profile_data]}),
            encoding="utf-8",
        )

        with self.migration_patch():
            result = migration.migrate_legacy_user_data()

        self.assertTrue(result.migrated)
        self.assertIn("旧保存先 MinecraftServerManager", result.copied_items)
        self.assertIn("旧保存先 minecraft_maneger", result.copied_items)
        self.assertEqual(
            "migrated",
            (self.new / "intermediate-only.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            b"world-data",
            (self.new / "server/world/level.dat").read_bytes(),
        )
        self.assertEqual(
            b"backup-data",
            (self.new / "backups/world.zip").read_bytes(),
        )
        self.assertEqual(
            b"jar-data",
            (self.new / "worldversion/server.jar").read_bytes(),
        )
        self.assertTrue((self.old / "server/world/level.dat").is_file())

        profiles = ProfileStore(self.new / "profiles.json", self.new).load()
        self.assertEqual((self.new / "server").resolve(), profiles[0].server_directory)
        self.assertEqual((self.new / "backups").resolve(), profiles[0].backup_directory)

    def test_existing_new_files_are_not_overwritten(self):
        (self.old / "settings.json").write_text("old", encoding="utf-8")
        self.new.mkdir()
        (self.new / "settings.json").write_text("new", encoding="utf-8")

        with self.migration_patch():
            migration.migrate_legacy_user_data()

        self.assertEqual("new", (self.new / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual("old", (self.old / "settings.json").read_text(encoding="utf-8"))

    def test_interrupted_file_copy_does_not_leave_destination(self):
        source = self.old / "server.jar"
        destination = self.new / "worldversion/server.jar"
        source.write_bytes(b"complete")

        def fail_copy(_source, temporary, *args, **kwargs):
            Path(temporary).write_bytes(b"partial")
            raise OSError("simulated interruption")

        with patch.object(migration.shutil, "copy2", side_effect=fail_copy):
            with self.assertRaises(OSError):
                migration._copy_file_if_missing(source, destination)

        self.assertFalse(destination.exists())
        self.assertEqual([], list(destination.parent.glob("*.tmp")))


class AppTests(TemporaryDataTest):
    def test_restore_worker_creates_safety_backup_before_restore(self):
        controller = ServerController(self.profile)
        safety = self.base / "pre_restore.zip"
        selected = self.base / "selected.zip"
        call_order = []

        def create_safety(**kwargs):
            call_order.append("safety")
            self.assertEqual("pre_restore", kwargs["backup_type"])
            return safety

        def restore_selected(profile, path):
            call_order.append("restore")
            self.assertEqual(selected, path)
            return path

        with patch.multiple(
            app,
            create_backup=Mock(side_effect=create_safety),
            restore_backup_archive=Mock(side_effect=restore_selected),
        ):
            app.restore_worker(controller, selected)

        message_type, data = controller.event_queue.get_nowait()
        self.assertEqual(["safety", "restore"], call_order)
        self.assertEqual("RESTORE_DONE", message_type)
        self.assertEqual(str(safety), data["safety_backup"])

    def test_force_stop_is_offered_only_after_timeout(self):
        controller = ServerController(self.profile)
        controller.process = Mock(poll=Mock(return_value=None))
        root = Mock()
        force_button = Mock()
        status = Mock()
        with patch.multiple(
            app,
            root=root,
            active_controller=controller,
            force_stop_button=force_button,
            status_label=status,
            add_console_text=Mock(),
        ):
            app.schedule_force_stop_offer(controller, timeout_ms=10)
            force_button.config.assert_not_called()
            callback = root.after.call_args.args[1]
            callback()
            force_button.config.assert_called_with(state=app.tk.NORMAL)

    def test_restart_blocks_switch_and_restarts_original(self):
        other = create_profile("B", self.base / "B", self.base / "B-backups")
        controller = ServerController(self.profile)
        controller.restart_requested = True
        controller.event_queue.put(("STATUS", "STOPPED"))
        root = Mock()
        with patch.multiple(
            app, root=root, profiles=[self.profile, other], active_profile=self.profile,
            active_controller=controller,
            controllers={self.profile.profile_id: controller, other.profile_id: ServerController(other)},
            status_label=Mock(), update_player_label=Mock(), set_controls_busy=Mock(),
            messagebox=Mock(), refresh_profile_list=Mock(), start_server=Mock(),
        ):
            app.check_server_queue()
            callback = next(call.args[1] for call in root.after.call_args_list if call.args[0] == 1500)
            self.assertTrue(controller.restart_requested)
            self.assertFalse(app.activate_profile(other))
            callback()
            self.assertIs(controller, app.active_controller)
            app.start_server.assert_called_once()
            self.assertFalse(controller.restart_requested)

    def test_cancelled_or_stale_restart_does_not_start_another_server(self):
        controller = ServerController(self.profile)
        with patch.object(app, "start_server") as start:
            controller.restart_requested = False
            app.complete_restart(controller)
            controller.restart_requested = True
            with patch.object(app, "active_controller", ServerController(self.profile)):
                app.complete_restart(controller)
            start.assert_not_called()

    def test_profile_load_error_aborts_before_main_window(self):
        root = Mock()
        startup_order = []

        def migrate_first():
            startup_order.append("migration")
            return Mock(migrated=False)

        def check_agreement_after_migration():
            startup_order.append("agreement")
            return True

        with patch.multiple(
            app, tk=Mock(Tk=Mock(return_value=root)), prepare_tk_runtime=Mock(),
            configure_logging=Mock(), acquire_single_instance_lock=Mock(),
            is_disclaimer_accepted=Mock(side_effect=check_agreement_after_migration),
            migrate_legacy_user_data=Mock(side_effect=migrate_first),
            profile_store=Mock(load=Mock(side_effect=ValueError("unsupported schema"))),
            messagebox=Mock(), build_main_window=Mock(),
        ):
            app.run()
            self.assertEqual(["migration", "agreement"], startup_order)
            app.build_main_window.assert_not_called()
            app.profile_store.save.assert_not_called()
            root.destroy.assert_called_once()

    def test_no_profiles_disables_server_controls(self):
        widgets = {name: Mock() for name in (
            "start_button", "stop_button", "restart_button", "force_stop_button",
            "backup_button", "backup_manage_button",
            "settings_button", "whitelist_button", "command_entry", "send_button", "status_label",
            "active_profile_label", "player_label",
        )}
        with patch.multiple(app, profiles=[], refresh_profile_list=Mock(), **widgets):
            app.set_stopped_ui()
            widgets["start_button"].config.assert_called_with(state=app.tk.DISABLED)
            app.open_edit_profile()
            app.on_auto_backup_changed()

    def test_first_server_creation_uses_default_location_without_collision(self):
        jar = self.base / "official.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            archive.writestr("META-INF/MANIFEST.MF", "Main-Class: net.minecraft.bundler.Main\n")
        store = ProfileStore(self.base / "profiles.json", self.base)
        values = self.profile.to_dict(self.base)
        values.pop("profile_id")
        values["server_directory"] = self.server
        values["backup_directory"] = self.profile.backup_directory
        with patch.multiple(
            app, profiles=[], controllers={}, active_profile=self.profile,
            active_controller=ServerController(self.profile), profile_store=store,
            root=Mock(), messagebox=Mock(askyesnocancel=Mock(return_value=True)),
            WORLD_VERSION_DIR=self.base / "jars", show_setup_wizard=Mock(), activate_profile=Mock(),
        ):
            app.open_add_profile()
            create = app.show_setup_wizard.call_args.kwargs["on_create"]
            create(values, jar, {"level-name": "world"}, False)
            self.assertEqual(1, len(app.profiles))
            self.assertTrue((self.server / "server.jar").is_file())
            self.assertIn("eula=false", (self.server / "eula.txt").read_text())
            self.assertEqual(self.server, store.load()[0].server_directory)

    def test_removing_last_profile_returns_to_empty_state(self):
        store = ProfileStore(self.base / "profiles.json", self.base)
        store.save([self.profile])
        controller = ServerController(self.profile)
        with patch.multiple(
            app, profiles=[self.profile], controllers={self.profile.profile_id: controller},
            active_profile=self.profile, active_controller=controller, profile_store=store,
            root=Mock(), messagebox=Mock(askyesno=Mock(return_value=True)),
            active_profile_label=Mock(), auto_backup_var=Mock(), load_max_players=Mock(),
            update_player_label=Mock(), render_active_console=Mock(), reset_dashboard=Mock(),
            set_stopped_ui=Mock(), refresh_profile_list=Mock(),
        ):
            app.remove_active_profile()
            self.assertEqual([], app.profiles)
            self.assertEqual({}, app.controllers)
            self.assertEqual([], store.load())
            app.set_stopped_ui.assert_called_once()

    def test_auto_backup_save_failure_does_not_change_active_settings(self):
        old_value = self.profile.auto_backup_interval
        variable = Mock(get=Mock(return_value="30m"))
        with patch.multiple(
            app, profiles=[self.profile], active_profile=self.profile,
            auto_backup_var=variable, messagebox=Mock(), add_console_text=Mock(),
            profile_store=Mock(save=Mock(side_effect=ValueError("future schema"))),
        ):
            app.on_auto_backup_changed()
            self.assertEqual(old_value, self.profile.auto_backup_interval)
            variable.set.assert_called_with(old_value)
            app.add_console_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
