"""Windows GUI entry point. The .pyw extension suppresses a console window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mechacae.app import main

if __name__ == "__main__":
    main()
