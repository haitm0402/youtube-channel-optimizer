"""Open a checked local export folder without a shell or browser."""
import os
from pathlib import Path
import subprocess
import sys


def open_export_folder(path: Path | str) -> None:
    folder = Path(path).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Export folder no longer exists")
    if sys.platform == "win32":
        os.startfile(str(folder))
    else:
        command = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([command, str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
