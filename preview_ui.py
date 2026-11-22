"""Compatibility shortcut for the native Windows documentation screenshot tool.

The old Qt offscreen snapshot flow produced unreadable tofu glyphs.
Capture screenshots with the real Windows Qt font database instead.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "scripts" / "capture_readme_screenshots.py"),
        run_name="__main__",
    )
