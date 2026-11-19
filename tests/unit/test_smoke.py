import subprocess
import sys

import silentwatch


def test_version():
    assert silentwatch.__version__ == "0.0.1"


def test_entry_point():
    out = subprocess.run([sys.executable, "-m", "silentwatch", "--version"], capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == silentwatch.__version__
