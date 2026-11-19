"""Import every planned dependency and print its version. Exit non-zero on failure."""

import importlib
import sys

MODULES = [
    ("cv2", "cv2"),
    ("mediapipe", "mediapipe"),
    ("bleak", "bleak"),
    ("PySide6.QtWidgets", "PySide6"),
    ("win32api", "win32api"),
    ("sqlite3", "sqlite3"),
]

failed = 0
for mod, verattr in MODULES:
    try:
        m = importlib.import_module(mod)
        base = sys.modules.get(verattr, m)
        version = getattr(base, "__version__", getattr(base, "sqlite_version", "ok"))
        print(f"OK   {mod} {version}")
    except Exception as exc:  # noqa: BLE001
        failed += 1
        print(f"FAIL {mod}: {exc!r}")
sys.exit(1 if failed else 0)
