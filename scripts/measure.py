"""Measure CPU and memory of the real pipeline (real camera, dry-run) for one configuration.

    python scripts/measure.py --config baseline --seconds 180

configs: baseline (face + obstruction) | hand (+ hand model loaded) | dashboard (+ Qt dashboard with live preview, offscreen)

Samples every 5 s into data/perf/<config>.csv (git-ignored) and prints a summary. Nothing is saved from the camera.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import dataclasses
import os
import statistics
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("SILENTWATCH_HOME", tempfile.mkdtemp(prefix="swperf"))

from silentwatch.app.lifecycle import SilentWatchService  # noqa: E402
from silentwatch.camera.sources import CvFrameSource  # noqa: E402
from silentwatch.config import app_data_dir, default_config  # noqa: E402
from silentwatch.presence.estimator import MediaPipeFaceBackend  # noqa: E402
from silentwatch.storage import Database  # noqa: E402
from silentwatch.windows.lock import WindowsLockService  # noqa: E402


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


def rss_mb() -> float:
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(pmc)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / (1024 * 1024)


def battery() -> str:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "$b = Get-CimInstance Win32_Battery | Select-Object -First 1; \"$($b.EstimatedChargeRemaining)% status=$($b.BatteryStatus)\""],
        capture_output=True, text=True).stdout.strip()
    return out or "n/a"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=["baseline", "hand", "dashboard"], default="baseline")
    ap.add_argument("--seconds", type=float, default=180)
    ap.add_argument("--warmup", type=float, default=15)
    ap.add_argument("--out", default="data/perf")
    a = ap.parse_args()

    cfg = default_config()
    cfg = dataclasses.replace(cfg, policy=dataclasses.replace(cfg.policy, dry_run=True))
    hands = None
    if a.config == "hand":
        from silentwatch.camera.hand_detector import MediaPipeHandBackend

        hands = MediaPipeHandBackend()
    db = Database(app_data_dir() / "perf.db")
    c = cfg.camera
    svc = SilentWatchService(cfg, db, lambda: CvFrameSource(c.index, c.width, c.height, c.backend),
                             MediaPipeFaceBackend(), WindowsLockService(None, dry_run=True), hand_backend=hands)
    svc.lock_service.store = svc.store

    app = dash = None
    if a.config == "dashboard":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication

        from silentwatch.ui.dashboard import make_dashboard

        app = QApplication.instance() or QApplication([])
        dash = make_dashboard(svc)

    battery0 = battery()
    svc.start()
    if dash is not None:
        dash.show()
        dash.chk_preview.setChecked(True)

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            if app is not None:
                app.processEvents()
            time.sleep(0.05)

    pump(a.warmup)                          # camera warm-up and calibration are not measured
    rows, t0, c0 = [], time.time(), time.process_time()
    f0 = svc.status().frames
    last_t, last_c = t0, c0
    while time.time() - t0 < a.seconds:
        pump(5.0)
        now, cpu = time.time(), time.process_time()
        rows.append((round(now - t0), round((cpu - last_c) / (now - last_t) * 100, 1), round(rss_mb(), 1)))
        last_t, last_c = now, cpu
    total_cpu = (time.process_time() - c0) / (time.time() - t0) * 100
    frames = svc.status().frames - f0
    inv = svc.hand_invocations
    svc.stop()
    db.close()

    Path(a.out).mkdir(parents=True, exist_ok=True)
    with open(Path(a.out) / f"{a.config}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "cpu_pct_one_core", "rss_mb"])
        w.writerows(rows)
    rss = [r[2] for r in rows]
    n_logical = os.cpu_count() or 1
    third = max(1, len(rss) // 3)
    print(f"config={a.config} seconds={a.seconds:.0f} frames_analysed={frames} ({frames / a.seconds:.1f}/s) hand_calls={inv}")
    print(f"CPU: avg {total_cpu:.1f}% of one core = {total_cpu / n_logical:.2f}% of all {n_logical} logical CPUs; "
          f"p95 sample {sorted(r[1] for r in rows)[int(len(rows) * 0.95) - 1]:.1f}%")
    print(f"RSS: start {rss[0]:.0f} MB, end {rss[-1]:.0f} MB, max {max(rss):.0f} MB, "
          f"growth first-third->last-third {statistics.mean(rss[-third:]) - statistics.mean(rss[:third]):+.1f} MB")
    print(f"battery before: {battery0}; after: {battery()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
