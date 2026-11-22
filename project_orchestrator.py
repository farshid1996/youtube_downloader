"""Local multi-agent engineering audit orchestrator for YouTube Downloader Studio.

Agents run independent, read-only checks in parallel. R&D synthesizes their
findings into a prioritized roadmap. No installers, uploads or code edits are
performed by this script; online release research is opt-in.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
from typing import Callable

ROOT = Path(os.environ.get("YDS_AUDIT_ROOT", Path(__file__).resolve().parent)).resolve()
REPORTS = Path(os.environ.get("YDS_REPORT_DIR", str(ROOT / "reports"))).resolve()
SOURCE = ("main.py", "engine.py", "system_check.py", "project_orchestrator.py",
          "portable/launcher.py", "portable/build.py", "portable/verify.py")

@dataclass
class Finding:
    agent: str
    level: str
    item: str
    evidence: str
    action: str = ""

    def record(self):
        return asdict(self)


def note(agent, level, item, evidence, action=""):
    return Finding(agent, level, item, evidence, action)


def source_text(name):
    return (ROOT / name).read_text(encoding="utf-8")


def python_sources():
    found = []
    excluded = {".venv", "venv", "build", "dist", "__pycache__", ".git", "portable/.venv"}
    for current, dirs, files in os.walk(ROOT, followlinks=False):
        rel = Path(current).relative_to(ROOT)
        dirs[:] = [name for name in dirs
                   if name not in {".venv", "venv", "build", "dist", "__pycache__", ".git"}
                   and not (Path(current) / name).is_symlink()]
        for name in files:
            if name.endswith(".py"):
                found.append(Path(current) / name)
    return sorted(found)


def architecture_agent(full=False):
    key = "Architecture"
    findings = []
    required = ["main.py", "engine.py", "requirements.txt", "tests/test_app.py",
                "portable/launcher.py", "portable/build.py"]
    for name in required:
        findings.append(note(key, "pass" if (ROOT / name).is_file() else "error",
                             "Required project file: " + name,
                             "Present" if (ROOT / name).is_file() else "Missing",
                             "Restore the missing project component."))
    for name in ("main.py", "engine.py"):
        text = source_text(name)
        findings.append(note(key, "pass" if "def " in text else "error",
                             "Implementation: " + name, "Code contains function definitions."))
    window = source_text("main.py")
    for feature, marker in [
        ("Persistent download queue", "queue.json"), ("Pause/resume", "def pause("),
        ("Cancellation", "def cancel("), ("Preview/inspection", "def inspect("),
        ("Progress feedback", "def consume("), ("System preflight", "def check_system(")]:
        findings.append(note(key, "pass" if marker in window else "warning",
                             feature, "Implemented" if marker in window else "Not found in current GUI.",
                             "Review missing behavior before release."))
    return findings


def dependency_agent(full=False):
    key = "Dependencies"
    from system_check import check_runtime, summary
    from engine import DATA
    checks = check_runtime(destination=Path.home() / "Downloads", data_dir=DATA,
                           execute_tools=full)
    results = []
    for item in checks:
        severity = "pass" if item.status == "ok" else ("error" if item.status == "missing" and item.required else "warning")
        results.append(note(key, severity, item.title, item.detail,
                            "Official information: " + item.install_url if item.install_url else ""))
    pinned = source_text("requirements.txt").splitlines()
    results.append(note(key, "pass" if all("==" in v for v in pinned if v.strip() and not v.startswith("#")) else "warning",
                        "Version-pinned Python requirements",
                        f"{len([x for x in pinned if x.strip()])} dependency declarations.",
                        "Pin runtime versions for reproducible builds."))
    return results


def security_agent(full=False):
    key = "Security and privacy"
    results = []
    for path in python_sources():
        name = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        except SyntaxError as exc:
            results.append(note(key, "error", "Invalid Python: " + name, str(exc)))
            continue
        hazards = []
        for item in ast.walk(tree):
            if isinstance(item, ast.Call):
                if isinstance(item.func, ast.Name) and item.func.id in ("eval", "exec"):
                    hazards.append(f"{item.func.id} on line {item.lineno}")
                for keyword in item.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        hazards.append(f"shell=True on line {item.lineno}")
        if hazards:
            results.append(note(key, "warning", "Dynamic execution patterns: " + name,
                                "; ".join(hazards), "Review for untrusted-input injection."))
    engine = source_text("engine.py")
    ui = source_text("main.py")
    for feature, valid, action in [
        ("URL scheme validation", "urlparse(value)" in engine and "https" in engine,
         "Reject untrusted link schemes."),
        ("No shell interpolation in downloader", "p.setArguments(args)" in ui,
         "Pass argument arrays, never shell-built commands."),
        ("Sensitive settings excluded from persistence", "s.pop('cookies',None)" in ui and "s.pop('proxy',None)" in ui,
         "Avoid persisting or exporting authentication data."),
        ("Log URL redaction", "re.sub(r'https?://" in ui,
         "Redact signed URLs, cookie paths and tokens before exporting logs."),
        ("Consent before third-party installation",
         "prompt.setStandardButtons" in ui and "install_url" in ui
         and "Nothing will be downloaded or installed automatically." in ui,
         "Do not auto-download or install system software.")]:
        results.append(note(key, "pass" if valid else "warning", feature,
                            "Control present in source" if valid else "Control could not be confirmed.", action))
    return results


def ux_agent(full=False):
    key = "User experience"
    src = source_text("main.py")
    checks = [
        ("Visible startup dependency option", "check_on_startup"),
        ("Manual system-check button", "System check"),
        ("User-approved installation link", "Would you like to open the official download page?"),
        ("Bulk selection actions", "populate_selection_menu"),
        ("Download retry", "retry_failed"),
        ("Accessibility label", "setAccessibleName"),
        ("Explicit privacy guidance", "Cookies are only read when explicitly selected"),
        ("Activity log export", "def export_log("),
        ("No silent installation", "Nothing will be downloaded or installed automatically.") ]
    return [note(key, "pass" if marker in src else "warning", title,
                 "UI behavior found." if marker in src else "UI behavior not found.",
                 "Implement or document the missing user control.")
            for title, marker in checks]


def ux_research_agent(full=False):
    key = "UX research"
    src = source_text("main.py")
    checks = [
        ("Progressive Simple / Advanced / Professional workspaces",
         all(token in src for token in ("Simple", "Advanced", "Professional", "def set_experience_level"))),
        ("Primary URL-to-download task flow",
         all(token in src for token in ("Start a download", "Paste links", "Inspect video", "Download now"))),
        ("Batch queue recovery and selection",
         all(token in src for token in ("def populate_selection_menu", "def retry_failed", "def prepare_again"))),
        ("Performance presets for different user needs",
         all(token in src for token in ("Maximum speed", "Maximum reliability", "Data saver"))),
        ("Clear download feedback",
         all(token in src for token in ("def inspect_done", "def consume", "def job_details"))),
    ]
    return [note(key, "pass" if ok else "warning", title,
                 "Evidence found in the current user workflow." if ok else "Workflow evidence is incomplete.",
                 "Validate with beginner, regular and expert user task walkthroughs.")
            for title, ok in checks]


def visual_design_agent(full=False):
    key = "Visual design"
    src = source_text("main.py")
    checks = [
        ("Liquid-glass inspired surface system",
         all(token in src for token in ("QFrame#glassCard", "QFrame#glassPanel", "rgba(", "QFrame#topBar"))),
        ("Windows native dark title bar and backdrop fallback",
         all(token in src for token in ("apply_native_window_effects", "DwmSetWindowAttribute", "DWMSBT_MAINWINDOW"))),
        ("Consistent typography and design tokens",
         all(token in src for token in ("Segoe UI", "QLabel#sectionTitle", "QPushButton#primary"))),
        ("Status is not communicated by color alone",
         all(token in src for token in ("READY", "NOTICE", "ACTION NEEDED"))),
        ("Responsive, scrollable option groups",
         "QScrollArea" in src and "def option_tab" in src),
    ]
    return [note(key, "pass" if ok else "warning", title,
                 "Design-system implementation marker found." if ok else "Design-system marker not found.",
                 "Review contrast, density and fallback appearance on clean Windows themes.")
            for title, ok in checks]


def interaction_motion_agent(full=False):
    key = "Interaction and motion"
    src = source_text("main.py")
    checks = [
        ("Native window close control explicitly enabled",
         "WindowCloseButtonHint" in src and "def closeEvent(self, event)" in src),
        ("Visible in-dialog close action",
         "dialogClose" in src and "self.window_close_button.clicked.connect(self.reject)" in src),
        ("Escape shortcut closes compatibility dialog",
         "QKeySequence('Escape')" in src and "self.close_shortcut.activated.connect(self.reject)" in src),
        ("Subtle entrance motion",
         "QPropertyAnimation" in src and "animate_window_entrance" in src),
        ("Keyboard shortcuts for common actions",
         all(token in src for token in ("Ctrl+Return", "Ctrl+Shift+V", "Ctrl+Shift+O"))),
    ]
    return [note(key, "pass" if ok else "warning", title,
                 "Interaction implementation found." if ok else "Interaction behavior is not established.",
                 "Verify native close, Escape, keyboard focus and reduced-motion behavior on Windows.")
            for title, ok in checks]


def accessibility_agent(full=False):
    key = "Accessibility"
    src = source_text("main.py")
    checks = [
        ("Accessible names on primary controls", "setAccessibleName" in src),
        ("Keyboard operation for download workflow", "QShortcut" in src and "Ctrl+Return" in src),
        ("Selectable diagnostic details", "TextSelectableByMouse" in src),
        ("Text labels accompany status colors",
         all(token in src for token in ("READY", "NOTICE", "ACTION NEEDED"))),
        ("Visible focus and hover states",
         all(token in src for token in ("QLineEdit:focus", "QPushButton:hover", "QCheckBox::indicator:hover"))),
    ]
    return [note(key, "pass" if ok else "warning", title,
                 "Accessibility evidence found." if ok else "Accessibility evidence is incomplete.",
                 "Perform keyboard-only, screen-reader and high-contrast checks with real users.")
            for title, ok in checks]


def performance_agent(full=False):
    key = "Performance engineering"
    src = source_text("main.py")
    checks = [
        ("Progress refresh is coalesced",
         "def schedule_render(self, job_id=None)" in src and "self.schedule_render(j['id'])" in src),
        ("Progress updates only repaint dirty queue rows",
         "def render(self, job_ids=None)" in src and "if job['id'] in wanted" in src),
        ("Table repaint is batched",
         "self.table.setUpdatesEnabled(False)" in src and "self.table.setUpdatesEnabled(True)" in src),
        ("UI and downloads use asynchronous processes",
         "QProcess(self)" in src and "readyReadStandardOutput.connect" in src),
        ("Queue scheduler uses a short non-blocking timer",
         "self.timer.start(300)" in src),
    ]
    return [note(key, "pass" if ok else "warning", title,
                 "Performance implementation marker found." if ok else "Performance implementation marker not found.",
                 "Benchmark 10, 100, 500 and 1,000 queued items plus multiple active downloads.")
            for title, ok in checks]


def professional_workflow_agent(full=False):
    key = "Professional workflow"
    src = source_text("engine.py")
    options = [
        "--extractor-retries", "--file-access-retries", "--socket-timeout",
        "--http-chunk-size", "--embed-subs", "--embed-thumbnail",
        "--write-info-json", "--write-comments", "--dateafter", "--datebefore",
        "--match-title", "--min-filesize", "--max-filesize", "--extractor-args",
        "--sponsorblock-mark", "--sponsorblock-remove",
    ]
    missing = [option for option in options if option not in src]
    return [note(key, "pass" if not missing else "warning",
                 "Professional yt-dlp controls",
                 f"{len(options) - len(missing)}/{len(options)} advanced controls are wired to argument construction.",
                 "Add missing controls with input validation and regression tests." if missing
                 else "Keep option syntax covered by engine argument tests.")]


def packaging_agent(full=False):
    key = "Packaging and release"
    results = []
    for name in ("build.ps1", "build-single.ps1", "verify-single.ps1",
                 "portable/build.sh", "portable/check.sh", "portable/README.md",
                 "THIRD_PARTY_NOTICES.txt", ".github/workflows/native-desktop.yml"):
        ok = (ROOT / name).is_file()
        results.append(note(key, "pass" if ok else "error", name,
                            "Present" if ok else "Absent", "Restore packaging/verification assets."))
    if getattr(sys, "frozen", False):
        results.append(note(key, "pass", "Standalone executable runtime",
                            "Audit is running inside the packaged one-file application; download tools are embedded."))
    else:
        for name in ("yt-dlp", "deno", "ffmpeg", "ffprobe"):
            exe = ROOT / "vendor" / (name + ".exe")
            results.append(note(key, "pass" if exe.is_file() else "warning",
                                "Windows vendor binary: " + name,
                                f"{exe.stat().st_size / 1024**2:.1f} MiB" if exe.is_file() else "Not present",
                                "Build source bundle before Windows packaging."))
        win = ROOT / "dist" / "single" / "YouTubeDownloader.exe"
        results.append(note(key, "pass" if win.is_file() else "warning",
                            "Local single-file Windows artifact",
                            "Built executable exists" if win.is_file() else "No current build found.",
                            "Use build-single.ps1 and verify-single.ps1 before publishing."))
    if (ROOT / "dist" / "release-v1.0.0").is_dir():
        results.append(note(key, "pass", "Previous release artifacts",
                            "Release folder exists; no publishing or upload performed."))
    return results


def portability_agent(full=False):
    key = "Cross-platform"
    native = source_text("portable/launcher.py")
    docs = source_text("portable/README.md")
    checks = [
        ("Native Linux and macOS adapters", "'linux', 'darwin'" in native),
        ("Per-platform app data", "XDG_DATA_HOME" in native and "Application Support" in native),
        ("Native process cancellation", "os.killpg" in native),
        ("Native tool payload hashing", "sha256" in native),
        ("macOS signature guidance", "notarization" in docs),
        ("Linux system graphics requirements", "libxcb" in docs)]
    findings = [note(key, "pass" if ok else "warning", title,
                     "Present" if ok else "Not established.",
                     "Confirm on a clean native device.") for title, ok in checks]
    findings.append(note(key, "warning", "Native OS coverage",
                         "Current session runs on Windows. Linux/macOS builds cannot be empirically validated here.",
                         "Run portable/check.sh and native smoke tests on Linux and both macOS architectures."))
    return findings


def test_agent(full=False):
    key = "Quality assurance"
    results = []
    sources = python_sources()
    errors = []
    for file in sources:
        try:
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(str(exc))
    results.append(note(key, "pass" if not errors else "error", "Python syntax verification",
                        f"{len(sources)} Python modules scanned; " + ("no syntax failures." if not errors else "; ".join(errors[:5]))))
    if not full:
        results.append(note(key, "warning", "Executable integration suite not run",
                            "Use --full to run pytest and the isolated media bundle verification."))
        return results
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="ytd-audit-") as isolated:
        env["LOCALAPPDATA"] = isolated
        if getattr(sys, "frozen", False):
            try:
                import subprocess as subprocess_module
                import pytest
                original_run = subprocess_module.run
                def run_without_console_stdin(*args, **kwargs):
                    kwargs.setdefault("stdin", subprocess_module.DEVNULL)
                    if not kwargs.get("capture_output") and "stdout" not in kwargs and "stderr" not in kwargs:
                        kwargs["stdout"] = subprocess_module.DEVNULL
                        kwargs["stderr"] = subprocess_module.DEVNULL
                    return original_run(*args, **kwargs)
                subprocess_module.run = run_without_console_stdin
                try:
                    test_exit = int(pytest.main(["-q", "-p", "no:cacheprovider", str(ROOT / "tests")]))
                finally:
                    subprocess_module.run = original_run
                results.append(note(key, "pass" if test_exit == 0 else "error",
                                    "Bundled regression test suite",
                                    f"pytest exit={test_exit}; tests execute locally against synthetic media."))
            except Exception as exc:
                results.append(note(key, "error", "Bundled regression test suite",
                                    f"{type(exc).__name__}: {exc}",
                                    "Check the bundled pytest runtime and audit source snapshot."))
            commands = [
                ("packaged synthetic-media and bundled-tools verification",
                 [sys.executable, "--verify-bundle"], 150)]
        else:
            executable = ROOT / ".venv" / "Scripts" / "python.exe"
            if not executable.is_file():
                executable = Path(sys.executable)
            commands = [
                ("pytest", [str(executable), "-m", "pytest", "tests", "-q"], 180),
                ("offline media engine verification",
                 [str(executable), "main.py", "--verify-bundle"], 120)]
        for title, cmd, timeout in commands:
            try:
                done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                                      stdin=subprocess.DEVNULL, text=True, errors="replace", timeout=timeout)
                details = ("\n".join((done.stdout + "\n" + done.stderr).splitlines()[-12:]))[:2400]
                if getattr(sys, "frozen", False) and done.returncode == 0:
                    verification = Path(isolated) / "YouTubeDownloaderStudio" / "bundle-verification.json"
                    if verification.is_file():
                        details = json.dumps(json.loads(verification.read_text(encoding="utf-8")),
                                             ensure_ascii=False)[:2400]
                results.append(note(key, "pass" if done.returncode == 0 else "error",
                                    title, f"exit={done.returncode}; {details}",
                                    "Review failures and rerun before publishing."))
            except (OSError, subprocess.TimeoutExpired) as exc:
                results.append(note(key, "error", title, str(exc),
                                    "Inspect dependencies and test timeouts."))
    return results


AGENTS: dict[str, Callable[[bool], list[Finding]]] = {
    "Architecture": architecture_agent,
    "Dependencies": dependency_agent,
    "Security and privacy": security_agent,
    "User experience": ux_agent,
    "UX research": ux_research_agent,
    "Visual design": visual_design_agent,
    "Interaction and motion": interaction_motion_agent,
    "Accessibility": accessibility_agent,
    "Performance engineering": performance_agent,
    "Professional workflow": professional_workflow_agent,
    "Packaging and release": packaging_agent,
    "Cross-platform": portability_agent,
    "Quality assurance": test_agent,
}


def online_release_research():
    """Curated official public release endpoints; no project/user data uploaded."""
    targets = {
        "yt-dlp": "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
        "Deno": "https://api.github.com/repos/denoland/deno/releases/latest",
        "PyInstaller": "https://pypi.org/pypi/pyinstaller/json",
        "PySide6": "https://pypi.org/pypi/PySide6-Essentials/json",
    }
    researched = []
    for title, url in targets.items():
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "YDS-Project-Audit/1.0",
                                                           "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=6) as response:
                data = json.loads(response.read(1_000_000))
            version = data.get("tag_name") or data.get("info", {}).get("version")
            if not version:
                raise ValueError("No release version returned")
            researched.append({"name": title, "version": str(version)[:80],
                               "source": url, "status": "verified-public-source"})
        except Exception as exc:
            researched.append({"name": title, "source": url, "status": "unavailable",
                               "detail": type(exc).__name__})
    return researched


def research_agent(all_findings, *, online=False):
    """Evidence-to-roadmap R&D agent. No generated code or unsafe auto-fixes."""
    issues = [x for x in all_findings if x.level in ("warning", "error")]
    priorities = []
    rank = {"error": 0, "warning": 1}
    for item in sorted(issues, key=lambda x: (rank[x.level], x.agent, x.item)):
        priorities.append({"priority": "P0" if item.level == "error" else "P1",
                           "area": item.agent, "issue": item.item,
                           "evidence": item.evidence, "next_step": item.action or "Investigate, implement and add a regression test."})
    # Product-focused research opportunities are explicitly suggestions, not verified defects.
    hypotheses = [
        ("P1", "UX research", "Run task-based walkthroughs with beginner, regular and expert users; measure time-to-first-download and option discovery."),
        ("P1", "Interaction and motion", "Verify the native title-bar close action, in-dialog close fallback, Escape and Alt+F4 on Windows 10/11; add reduced-motion support."),
        ("P1", "Accessibility", "Test keyboard-only operation, screen readers, 200% scaling, contrast and focus order."),
        ("P2", "Visual design", "Compare Mica/Acrylic support and the translucent fallback across Windows builds, DPI settings and light/dark modes."),
        ("P2", "Performance engineering", "Queue-only rendering benchmark is recorded; benchmark 1, 3 and 5 active transfers under CPU, disk and network constraints and measure memory."),
        ("P2", "Professional workflow", "Validate custom format selectors, templates, date/size filters, SponsorBlock and metadata options against representative media."),
        ("P2", "Reliability", "Add deterministic tests for network interruption, resuming and partial-file recovery."),
        ("P2", "Quality", "Expand integration coverage to playlists, subtitles, blocked videos and authentication boundaries."),
        ("P2", "Distribution", "Validate first-launch diagnostics on clean Windows, Linux and macOS virtual machines."),
        ("P2", "Security", "Audit diagnostic export/logging for secrets and signed media URLs."),
        ("P3", "Release engineering", "Automate SBOM, dependency audit, artifact signing and reproducible release verification."),
    ]
    for priority, area, task in hypotheses:
        priorities.append({"priority": priority, "area": area, "issue": "Research opportunity",
                           "evidence": "R&D hypothesis; not a demonstrated defect.", "next_step": task})
    releases = online_release_research() if online else []
    return priorities, releases


def render_design_system():
    """Document the implemented design contract and platform fallbacks."""
    return "\n".join([
        "# YouTube Downloader Studio — UI/UX design system",
        "",
        "## Product experience",
        "- Simple: URL intake, output format, quality and destination only.",
        "- Advanced: performance, subtitles, network and privacy controls.",
        "- Professional: custom yt-dlp format, output template, date/size filters, extractor arguments and SponsorBlock.",
        "- Performance presets: Balanced, Maximum speed, Maximum reliability and Data saver.",
        "",
        "## Visual language",
        "- Dark Liquid Glass-inspired surfaces: layered translucent panels, subtle gradients, thin luminous borders and rounded geometry.",
        "- Segoe UI typography, mint/cyan primary action, muted blue-grey secondary text and explicit status labels.",
        "- Windows Mica/dark-title-bar effects are requested when supported; opaque gradient surfaces remain the fallback.",
        "- The Qt Widgets treatment is glass-inspired, not a promise of hardware blur on every Windows version.",
        "",
        "## Interaction contract",
        "- Native title-bar close, an explicit in-dialog close action, Escape and the standard Alt+F4 path.",
        "- Short entrance animation only; keep task controls immediate and avoid animating the download engine.",
        "- Keyboard shortcuts: Ctrl+Enter download, Ctrl+Shift+V paste links, Ctrl+Shift+O open destination.",
        "",
        "## Accessibility",
        "- Give primary controls accessible names and tooltips.",
        "- Pair status colors with text labels; keep diagnostic detail selectable.",
        "- Preserve keyboard focus visibility and scrollable options at small window sizes.",
        "- Follow-up research: reduced-motion preference, screen-reader walkthrough and high-contrast testing.",
        "",
        "## Performance contract",
        "- Use QProcess for external downloads; never block the UI thread for network transfers.",
        "- Coalesce progress updates and repaint only dirty queue rows.",
        "- Benchmark large queues and concurrent transfers on real storage/network profiles before claiming speed gains.",
        "",
        "## Professional options",
        "- Keep custom yt-dlp arguments as process-array entries; never concatenate them into shell commands.",
        "- Validate dates, regexes, file sizes and relative output paths before process launch.",
        "- Keep cookie paths and proxy credentials out of persistent settings and diagnostic logs.",
        "",
    ])


def render_roadmap(priorities, releases, *, full):
    lines = ["# YouTube Downloader Studio — R&D roadmap", "",
             f"Generated: {datetime.now(timezone.utc).isoformat()}", "",
             "This R&D agent synthesizes offline evidence and explicitly labeled hypotheses.",
             "It does not implement, install, publish, or claim untested platform compatibility.", "",
             f"Audit scope: {'full tests and isolated media verification' if full else 'static checks only'}.", "",
             "## Prioritized work", ""]
    for i, item in enumerate(priorities, 1):
        lines += [f"### {i}. {item['priority']} · {item['area']} · {item['issue']}",
                  f"- Evidence: {item['evidence']}", f"- Next step: {item['next_step']}", ""]
    lines += ["## Official upstream research", ""]
    if not releases:
        lines += ["Offline mode: release research was not performed. Use --online-research to consult official sources.", ""]
    else:
        for item in releases:
            lines += [f"- {item['name']}: {item.get('version', item.get('detail', 'unknown'))} ({item['status']}) — {item['source']}"]
    lines += ["", "## Release gate", "",
              "Do not release with failing P0 findings. Re-run the full suite on the target operating system.",
              "Ask the user before installing system components; a missing optional browser is not a hard dependency."]
    return "\n".join(lines) + "\n"


def run(full=False, online=False):
    findings = []
    # Static agents are independent and run concurrently. QA runs afterward:
    # its tests deliberately monkeypatch shared engine globals, so it must not
    # overlap the live dependency probe.
    parallel_agents = {name: agent for name, agent in AGENTS.items()
                       if name != "Quality assurance"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(agent, full): name for name, agent in parallel_agents.items()}
        for job in as_completed(jobs):
            name = jobs[job]
            try:
                findings.extend(job.result())
            except Exception as exc:
                findings.append(note(name, "error", "Agent crashed",
                                     f"{type(exc).__name__}: {exc}"))
    try:
        findings.extend(AGENTS["Quality assurance"](full))
    except Exception as exc:
        findings.append(note("Quality assurance", "error", "Agent crashed",
                             f"{type(exc).__name__}: {exc}"))
    findings.sort(key=lambda x: (x.agent, x.level, x.item))
    roadmap, releases = research_agent(findings, online=online)
    REPORTS.mkdir(exist_ok=True)
    design_path = REPORTS / "UI_UX_DESIGN_SYSTEM.md"
    design_path.write_text(render_design_system(), encoding="utf-8")
    result = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "mode": "full" if full else "quick",
              "network_research": online, "agents": list(AGENTS) + ["Research and development"],
              "counts": {level: sum(x.level == level for x in findings)
                         for level in ("pass", "warning", "error")},
              "findings": [x.record() for x in findings],
              "research": {"prioritized_backlog": roadmap, "official_releases": releases,
                           "design_system": str(design_path)}}
    (REPORTS / "orchestrator-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (REPORTS / "RD_ROADMAP.md").write_text(render_roadmap(roadmap, releases, full=full), encoding="utf-8")
    print(json.dumps({"agents": len(result["agents"]), "mode": result["mode"],
                      "counts": result["counts"],
                      "report": str(REPORTS / "orchestrator-report.json"),
                      "roadmap": str(REPORTS / "RD_ROADMAP.md"),
                      "design_system": str(design_path)}, indent=2))
    return 1 if result["counts"]["error"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Run pytest + isolated synthetic-media verification.")
    parser.add_argument("--online-research", action="store_true",
                        help="Opt in to read-only requests to official public release APIs.")
    config = parser.parse_args()
    sys.exit(run(full=config.full, online=config.online_research))
