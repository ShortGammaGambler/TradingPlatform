"""Launch the Streamlit Trading Platform UI."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent
    ui_path = root / "src" / "ui" / "trading_platform.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ui_path), "--server.headless=true"])


if __name__ == "__main__":
    main()
