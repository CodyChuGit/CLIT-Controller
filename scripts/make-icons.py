#!/usr/bin/env python3
"""Render the CLITC bean app/PWA PNG icons from the promoted SVG source.

Run from anywhere: .venv/bin/python scripts/make-icons.py
Requires macOS `sips`; no browser rendering is used.
"""
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "frontend" / "public" / "icons"
SRC = OUT_DIR / "bean.svg"


def render(size: int, out: Path) -> None:
    if not SRC.is_file():
        raise FileNotFoundError(f"missing icon source: {SRC}")
    if shutil.which("sips") is None:
        raise RuntimeError("macOS `sips` is required to render the SVG icon")

    subprocess.run(
        ["sips", "-s", "format", "png", "-z", str(size), str(size), str(SRC), "--out", str(out)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print("wrote", out)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render(512, OUT_DIR / "bean-512.png")
    render(192, OUT_DIR / "bean-192.png")
