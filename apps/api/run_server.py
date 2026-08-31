from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    source_root = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(source_root))

    from jobpilot_api.server import run

    run(reload=True)


if __name__ == "__main__":
    main()
