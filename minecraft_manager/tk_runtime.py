"""Windows版PythonのZIP形式Tcl/Tkを利用できるよう準備する。"""

import os
from pathlib import Path
import shutil
import sys
import zipfile

from .paths import USER_DATA_DIR


def prepare_tk_runtime(python_root=None, cache_root=None):
    """必要な環境だけTcl/Tkライブラリを展開し、参照先を設定する。"""
    if os.name != "nt":
        return False

    python_root = Path(python_root or sys.base_prefix)
    tcl_root = python_root / "tcl"
    tcl_archives = sorted(tcl_root.glob("libtcl*.zip"))
    tk_archives = sorted(tcl_root.glob("libtk*.zip"))
    if not tcl_archives or not tk_archives:
        return False

    version = ".".join(str(part) for part in sys.version_info[:3])
    cache_root = Path(
        cache_root or USER_DATA_DIR / "runtime" / f"python-{version}"
    )
    tcl_destination = cache_root / "tcl"
    tk_destination = cache_root / "tk"
    tcl_library = tcl_destination / "tcl_library"
    tk_library = tk_destination / "tk_library"

    _extract_if_missing(
        tcl_archives[-1],
        tcl_destination,
        tcl_library / "init.tcl",
    )
    _extract_if_missing(
        tk_archives[-1],
        tk_destination,
        tk_library / "tk.tcl",
    )

    os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    os.environ.setdefault("TK_LIBRARY", str(tk_library))
    return True


def _extract_if_missing(archive, destination, required_file):
    if required_file.is_file():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()

    try:
        with zipfile.ZipFile(archive, "r") as zip_file:
            _safe_extract(zip_file, temporary)
        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    if not required_file.is_file():
        raise FileNotFoundError(
            f"Tcl/Tkランタイムに必要なファイルがありません。\n{required_file}"
        )


def _safe_extract(zip_file, destination):
    destination = destination.resolve()
    for member in zip_file.infolist():
        member_path = (destination / member.filename).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as error:
            raise ValueError(
                f"安全でないTcl/Tkアーカイブパスです: {member.filename}"
            ) from error
    zip_file.extractall(destination)
