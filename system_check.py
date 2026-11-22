"""Read-only, offline preflight for source and bundled desktop deployments.

Never downloads software, runs installers, accesses cookies, or modifies settings.
Only validates requirements and reports official places to obtain missing tools.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

OFFICIAL = {
    "yt-dlp": "https://github.com/yt-dlp/yt-dlp/releases/latest",
    "deno": "https://deno.com/",
    "ffmpeg": "https://ffmpeg.org/download.html",
    "ffprobe": "https://ffmpeg.org/download.html",
    "PySide6": "https://pypi.org/project/PySide6-Essentials/",
    "python": "https://www.python.org/downloads/",
    "Firefox": "https://www.mozilla.org/firefox/",
    "Chrome": "https://www.google.com/chrome/",
    "Edge": "https://www.microsoft.com/edge",
    "Brave": "https://brave.com/download/",
    "app": "https://github.com/farshid1996/youtube_downloader/releases/latest",
}

@dataclass(frozen=True)
class Result:
    key: str
    status: str  # ok, warning, missing
    title: str
    detail: str
    required: bool = True
    install_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _browser_installed(name: str) -> bool:
    executables = {"Firefox": "firefox.exe", "Chrome": "chrome.exe",
                   "Edge": "msedge.exe", "Brave": "brave.exe"}
    exe = executables.get(name)
    if not exe:
        return False
    if shutil.which(exe):
        return True
    if os.name != "nt":
        linux = {"Firefox": "firefox", "Chrome": "google-chrome",
                 "Edge": "microsoft-edge", "Brave": "brave-browser"}
        if shutil.which(linux[name]):
            return True
        if sys.platform == "darwin":
            return (Path("/Applications") / ({"Chrome": "Google Chrome",
                    "Edge": "Microsoft Edge", "Brave": "Brave Browser"}.get(name, name) + ".app")).exists()
        return False
    bases = [os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
             os.environ.get("LOCALAPPDATA", "")]
    paths = {"Firefox": ["Mozilla Firefox/firefox.exe"],
             "Chrome": ["Google/Chrome/Application/chrome.exe"],
             "Edge": ["Microsoft/Edge/Application/msedge.exe"],
             "Brave": ["BraveSoftware/Brave-Browser/Application/brave.exe"]}
    return any((Path(base) / relative).is_file()
               for base in bases if base for relative in paths[name])


def _writable(path: Path) -> tuple[bool, str]:
    # Do not create the target download directory during a diagnostic.
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    if not target.is_dir():
        return False, "No accessible parent directory."
    try:
        with tempfile.NamedTemporaryFile(dir=target, prefix=".yds-check-", delete=True) as stream:
            stream.write(b"ok")
            stream.flush()
        return True, "A temporary write succeeded."
    except OSError as exc:
        return False, f"Cannot write to destination: {type(exc).__name__}."


TOOL_NAMES = ("yt-dlp", "deno", "ffmpeg", "ffprobe")


def _has_cached_tools(data_path: Path) -> bool:
    root = data_path / "tools"
    try:
        for directory in root.iterdir():
            if directory.is_dir() and all(
                (directory / name).is_file() or (directory / (name + ".exe")).is_file()
                for name in TOOL_NAMES
            ):
                return True
    except OSError:
        pass
    return False


def check_runtime(tool_provider: Callable[[str], str] | None = None, *,
                  browser: str = "None", destination: str | Path | None = None,
                  data_dir: str | Path | None = None, frozen: bool | None = None,
                  execute_tools: bool = True) -> list[Result]:
    """Inspect the actual computer before extracting tools; never install software."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    results: list[Result] = []
    bits = platform.architecture()[0]
    if sys.platform not in ("win32", "linux", "darwin") or bits != "64bit":
        results.append(Result("platform", "missing", "Supported operating system",
                              f"Detected {sys.platform} ({bits}); this build requires a supported 64-bit desktop."))
    else:
        results.append(Result("platform", "ok", "Operating system",
                              f"{platform.system()} {platform.release()} ({platform.machine()})"))
    if not frozen:
        valid = (3, 11) <= sys.version_info[:2] <= (3, 12)
        results.append(Result("python", "ok" if valid else "warning",
                              "Python interpreter", f"Python {platform.python_version()}; 3.11/3.12 tested.",
                              install_url=OFFICIAL["python"] if not valid else ""))
        for package in ("PySide6",):
            present = importlib.util.find_spec(package) is not None
            results.append(Result("module-" + package, "ok" if present else "missing",
                                  package + " GUI dependency",
                                  "Importable in this Python environment." if present else
                                  "Run pip install -r requirements.txt in a virtual environment.",
                                  install_url=OFFICIAL[package] if not present else ""))
    else:
        results.append(Result("runtime", "ok", "Embedded Python/Qt runtime",
                              "Using the packaged application; no system Python installation is required."))

    if data_dir is None:
        from engine import DATA
        data_dir = DATA
    data_path = Path(data_dir)
    can_write, storage_detail = _writable(data_path)
    results.append(Result("app-storage", "ok" if can_write else "missing",
                          "Application data storage", storage_detail))

    cached_tools = _has_cached_tools(data_path) if frozen else True
    minimum_free = (500_000_000 if cached_tools else int(1.5 * 1024**3))
    enough_space = False
    try:
        bytes_free = shutil.disk_usage(data_path if data_path.exists() else data_path.parent).free
        enough_space = bytes_free >= minimum_free
        disk_status = "ok" if enough_space else "missing"
        disk_detail = (f"{bytes_free / (1024**3):.2f} GiB free; "
                       f"{minimum_free / (1024**3):.2f} GiB required before first-run extraction.")
        results.append(Result("disk", disk_status, "Available storage", disk_detail))
    except OSError:
        enough_space = True
        results.append(Result("disk", "warning", "Available storage",
                              "Could not measure free space; tool preparation will be attempted."))

    if tool_provider is None:
        from engine import tool as tool_provider
    flags = {"yt-dlp": "--version", "deno": "--version",
             "ffmpeg": "-version", "ffprobe": "-version"}
    if can_write and enough_space:
        for name, flag in flags.items():
            try:
                path = Path(tool_provider(name))
                if not path.is_file():
                    raise FileNotFoundError("Expected executable is absent.")
                if execute_tools:
                    kwargs = {"capture_output": True, "text": True, "timeout": 8,
                              "stdin": subprocess.DEVNULL}
                    if os.name == "nt":
                        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    check = subprocess.run([str(path), flag], **kwargs)
                    if check.returncode != 0:
                        raise OSError(f"Process exited with code {check.returncode}.")
                    version = next((line for line in check.stdout.splitlines() if line.strip()), "Executable launched.")
                else:
                    version = "Executable found (launch not tested)."
                results.append(Result("tool-" + name, "ok", name, version[:180]))
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                install_url = OFFICIAL["app"] if frozen else OFFICIAL[name]
                remedy = ("Restart or reinstall the official packaged app. " if frozen else
                          "Provide the tool in vendor/ or prepare it using the documented helper. ")
                results.append(Result("tool-" + name, "missing", name,
                                      remedy + f"Check failed: {type(exc).__name__}.",
                                      install_url=install_url))
    else:
        reason = ("application data storage is not writable" if not can_write else
                  "insufficient free space for safe first-run extraction")
        for name in flags:
            results.append(Result("tool-" + name, "warning", name,
                                  f"Not probed because {reason}; no tool files were extracted.",
                                  required=False))

    if destination:
        ok, info = _writable(Path(destination).expanduser())
        results.append(Result("destination", "ok" if ok else "missing",
                              "Download destination", info))
    if browser and browser != "None":
        exists = _browser_installed(browser)
        results.append(Result("browser", "ok" if exists else "warning",
                              browser + " (optional cookies source)",
                              "Browser detected." if exists else
                              "Browser not detected. Choose 'None' or install it only if you need its cookies.",
                              required=False, install_url="" if exists else OFFICIAL.get(browser, "")))
    return results


def summary(results: list[Result]) -> dict:
    missing = [x for x in results if x.status == "missing" and x.required]
    return {"ready": not missing, "missing_required": [x.to_dict() for x in missing],
            "warnings": [x.to_dict() for x in results if x.status == "warning"],
            "results": [x.to_dict() for x in results]}
