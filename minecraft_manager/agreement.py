"""免責事項への同意状態を保存・確認する。"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from . import APP_DISPLAY_NAME
from .paths import SETTINGS_FILE


SETTINGS_SCHEMA_VERSION = 1
DISCLAIMER_VERSION = 2
DISCLAIMER_TEXT = f"""{APP_DISPLAY_NAME} 免責事項

1. 本ソフトウェアは現状有姿（AS IS）で提供されます。作者は、本ソフトウェアが常に正常に動作すること、特定の目的に適合すること、データが失われないことを保証しません。

2. 本ソフトウェアの使用、使用不能、誤操作、設定変更、サーバーの停止、ワールドや設定ファイルの破損・消失、バックアップまたは復元の失敗、その他本ソフトウェアに関連して生じた損害について、作者は適用法令で認められる最大限の範囲で責任を負いません。

3. Minecraftサーバー、ワールド、設定ファイルおよびバックアップの管理は利用者自身の責任で行ってください。重要なデータは、本ソフトウェアが作成するバックアップとは別の場所にも保存してください。

4. 本ソフトウェアはMojang StudiosおよびMicrosoftの公式製品ではなく、両社から承認または保証されたものではありません。Minecraftの利用規約およびEULAは利用者自身で確認し、遵守してください。

5. この免責事項に同意できない場合、本ソフトウェアを使用することはできません。

NOT AN OFFICIAL MINECRAFT PRODUCT.
NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
"""


def is_disclaimer_accepted(path=SETTINGS_FILE):
    path = Path(path)
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return (
        isinstance(data, dict)
        and data.get("disclaimer_accepted") is True
        and data.get("disclaimer_version") == DISCLAIMER_VERSION
    )


def record_disclaimer_acceptance(app_version, path=SETTINGS_FILE):
    path = Path(path)
    data = _read_settings(path)
    data.update(
        {
            "schema_version": SETTINGS_SCHEMA_VERSION,
            "disclaimer_accepted": True,
            "disclaimer_version": DISCLAIMER_VERSION,
            "disclaimer_accepted_at": datetime.now(timezone.utc).isoformat(),
            "accepted_with_app_version": str(app_version),
        }
    )
    _write_settings(path, data)


def _read_settings(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_settings(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
