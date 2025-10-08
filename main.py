import sys
from pathlib import Path
import uvicorn


def main():
    # Ensure local `src` is importable when running from repo root
    root = Path(__file__).resolve().parent
    src = root / "src"
    if src.exists():
        sys.path.insert(0, str(src))
    uvicorn.run("gekko.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
