"""公式サーバーJARで日本語MOTDを確認する手動スモークテスト。"""

import argparse
import json
from pathlib import Path
import queue
import socket
import struct
import tempfile
import time
import zipfile

from minecraft_manager.profiles import create_profile
from minecraft_manager.server import ServerController
from minecraft_manager.setup import create_server_files


TEST_MOTD = "日本語サーバーへようこそ！"


def encode_varint(value):
    value &= 0xFFFFFFFF
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            return bytes(result)


def read_exact(connection, size):
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("サーバー一覧応答が途中で終了しました。")
        data.extend(chunk)
    return bytes(data)


def read_varint(connection):
    value = 0
    for index in range(5):
        byte = read_exact(connection, 1)[0]
        value |= (byte & 0x7F) << (7 * index)
        if not byte & 0x80:
            return value
    raise ValueError("不正なVarIntを受信しました。")


def query_status(port, protocol_version):
    host = "127.0.0.1"
    host_bytes = host.encode("utf-8")
    handshake = (
        encode_varint(0)
        + encode_varint(protocol_version)
        + encode_varint(len(host_bytes))
        + host_bytes
        + struct.pack(">H", port)
        + encode_varint(1)
    )
    with socket.create_connection((host, port), timeout=10) as connection:
        connection.sendall(encode_varint(len(handshake)) + handshake)
        connection.sendall(b"\x01\x00")
        read_varint(connection)
        if read_varint(connection) != 0:
            raise ValueError("想定外のステータス応答です。")
        payload_size = read_varint(connection)
        return json.loads(read_exact(connection, payload_size).decode("utf-8"))


def query_legacy_motd(port):
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.sendall(b"\xfe\x01")
        if read_exact(connection, 1) != b"\xff":
            raise ValueError("想定外のLegacy Ping応答です。")
        text_length = struct.unpack(">H", read_exact(connection, 2))[0]
        response = read_exact(connection, text_length * 2).decode("utf-16-be")
    parts = response.split("\x00")
    if len(parts) < 6 or parts[0] != "§1":
        raise ValueError("Legacy Ping応答の形式が正しくありません。")
    return parts[3]


def component_text(component):
    if isinstance(component, str):
        return component
    if isinstance(component, list):
        return "".join(component_text(item) for item in component)
    if isinstance(component, dict):
        return str(component.get("text", "")) + component_text(
            component.get("extra", [])
        )
    return ""


def choose_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def read_protocol_version(jar_path):
    with zipfile.ZipFile(jar_path) as archive:
        version = json.loads(archive.read("version.json").decode("utf-8"))
    return int(version["protocol_version"])


def run(jar_path, java_executable, temp_root=None):
    port = choose_port()
    protocol_version = read_protocol_version(jar_path)
    with tempfile.TemporaryDirectory(
        prefix="vanilla-server-manager-motd-",
        dir=temp_root,
    ) as directory:
        base = Path(directory)
        profile = create_profile("MOTD smoke", base / "server", base / "backups")
        profile.java_executable = java_executable
        profile.minimum_memory = "512M"
        profile.maximum_memory = "1024M"
        create_server_files(
            profile,
            jar_path,
            {
                "server-ip": "127.0.0.1",
                "server-port": str(port),
                "level-name": "motd_test_world",
                "motd": TEST_MOTD,
                "online-mode": "false",
                "max-players": "1",
                "view-distance": "2",
                "simulation-distance": "2",
                "spawn-protection": "0",
            },
            True,
        )

        controller = ServerController(profile)
        logs = []
        try:
            controller.start()
            deadline = time.monotonic() + 120
            ready = False
            while time.monotonic() < deadline:
                try:
                    message_type, data = controller.event_queue.get(timeout=1)
                except queue.Empty:
                    if not controller.running:
                        break
                    continue
                if message_type == "LOG":
                    logs.append(data)
                elif message_type == "STATUS" and data == "RUNNING":
                    ready = True
                    break
            if not ready:
                raise RuntimeError("サーバーが起動完了しませんでした。\n" + "".join(logs[-30:]))

            try:
                response = query_status(port, protocol_version)
                received = component_text(response.get("description"))
            except Exception:
                # 現行Pingの仕様差がある版でも、Vanillaが返すLegacy Pingで
                # server.propertiesから読み込まれたMOTD自体を確認する。
                received = query_legacy_motd(port)
            if received != TEST_MOTD:
                raise AssertionError(
                    f"MOTDが一致しません。期待={TEST_MOTD!r} 実際={received!r}"
                )
            print(f"Japanese MOTD smoke test: OK ({received})")
        finally:
            if controller.running:
                try:
                    controller.send("stop")
                    controller.process.wait(timeout=30)
                except Exception:
                    controller.force_stop()
                    controller.process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--java", default="java")
    parser.add_argument("--temp-root", type=Path)
    arguments = parser.parse_args()
    run(arguments.jar.resolve(), arguments.java, arguments.temp_root)


if __name__ == "__main__":
    main()
