"""Capture readable README screenshots from the real Windows PySide6 UI.

Run with the project's Python environment on Windows. This does not download
media, use personal application data, or change the user's saved settings.
Offscreen Qt is intentionally rejected because it can render font glyphs as boxes.
"""
from pathlib import Path
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.pop("QT_QPA_PLATFORM", None)
sys.argv.append("--smoke-test")  # Do not open startup diagnostic dialogs.
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QApplication
import main

if sys.platform != "win32":
    raise RuntimeError("These README screenshots require native Windows Qt.")
app = QApplication.instance() or QApplication([])
if app.platformName().lower() != "windows":
    raise RuntimeError("Qt Windows platform is required, not offscreen.")
families = QFontDatabase.families()
metrics = QFontMetrics(QFont("Segoe UI", 12))
if "Segoe UI" not in families or not metrics.inFontUcs4(ord("A")):
    raise RuntimeError("Segoe UI unavailable; refusing broken-font screenshots.")
print("NATIVE PLATFORM:", app.platformName(), "AVAILABLE FONTS:", len(families), flush=True)

app.setStyle("Fusion")
app.setStyleSheet(main.STYLE)
output = ROOT / "docs" / "images"
output.mkdir(parents=True, exist_ok=True)
def capture(widget, filename):
    app.processEvents()
    image = widget.grab()
    file = output / filename
    if image.isNull() or not image.save(str(file), "PNG"):
        raise RuntimeError("Screenshot failed: " + filename)
    if file.stat().st_size < 8000:
        raise RuntimeError("Screenshot too small: " + filename)
    print("CAPTURED", file.relative_to(ROOT), image.width(), image.height(), file.stat().st_size, flush=True)

with tempfile.TemporaryDirectory(prefix="youtube-studio-documentation-") as isolation:
    os.environ["LOCALAPPDATA"] = isolation
    # main.DATA was imported before the isolated window is created.
    main.DATA = Path(isolation) / "YouTubeDownloaderStudio"
    main.DATA.mkdir(parents=True, exist_ok=True)
    w = main.Window()
    w.timer.stop()
    w.resize(1360, 1010)
    w.folder.setText(r"C:\Downloads\YouTube")
    w.show()
    app.processEvents()
    scroll = w.page_scroll.verticalScrollBar()
    scroll.setValue(0)
    capture(w, "simple-workspace.png")

    w.links.setPlainText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    w.preview.setText("Example URL entered. Choose Inspect video to check available formats.")
    scroll.setValue(0)
    capture(w, "paste-links.png")
    w.links.clear()
    w.preview.setText("Ready when you are. Paste a link to inspect or download.")

    w.experience_combo.setCurrentText("Advanced")
    w.preset_combo.setCurrentText("Maximum reliability")
    w.tabs.setCurrentIndex(1)  # Performance tab; settings shown are real controls.
    app.processEvents()
    settings_y = w.tabs.mapTo(w.page_scroll.widget(), QPoint()).y()
    scroll.setValue(max(0, settings_y - 135))
    capture(w.tabs.parentWidget(), "advanced-workspace.png")
    w.tabs.setCurrentIndex(2)
    capture(w.tabs.parentWidget(), "subtitles-extras.png")
    w.tabs.setCurrentIndex(3)
    capture(w.tabs.parentWidget(), "network-privacy.png")

    w.experience_combo.setCurrentText("Professional")
    w.tabs.setCurrentIndex(4)  # Professional yt-dlp options.
    app.processEvents()
    settings_y = w.tabs.mapTo(w.page_scroll.widget(), QPoint()).y()
    scroll.setValue(max(0, settings_y - 135))
    capture(w.tabs.parentWidget(), "professional-workspace.png")

    # Populate the REAL queue widget with explicitly labeled illustrative rows.
    # No jobs are started and no media is downloaded.
    sample = [
        ("Demo example - paused MP4", "Paused", "57.5%", "MP4 video"),
        ("Demo example - ready to resume", "Queued", "", "MKV video"),
        ("Demo example - retry an error", "Failed", "", "MP3 audio"),
    ]
    w.jobs = [
        dict(id="demo-" + str(i), url="https://example.com/example-media-" + str(i),
             title=title, status=status, progress=progress, speed="", eta="",
             files=[], settings={"folder":r"C:\Downloads\YouTube", "mode":mode})
        for i, (title, status, progress, mode) in enumerate(sample)
    ]
    w.render()
    app.processEvents()
    table_y = w.table.mapTo(w.page_scroll.widget(), QPoint()).y()
    scroll.setValue(max(0, table_y - 235))
    capture(w.table.parentWidget(), "queue-controls.png")
    w.table.selectRow(0)
    app.processEvents()
    capture(w.table, "progress-queue.png")
    menu = w.job_menu([w.jobs[0]])
    menu.show()
    app.processEvents()
    capture(menu, "job-actions-menu.png")
    menu.close()
    menu.deleteLater()
    w.close()
    app.processEvents()

    # This is the real application's diagnostics dialog and result model.
    results = main.check_runtime(
        browser="None", destination=isolation, data_dir=main.DATA,
        execute_tools=True
    )
    report = main.system_check_summary(results)
    dialog = main.SystemCheckDialog(results, report)
    dialog.show()
    app.processEvents()
    capture(dialog, "system-check.png")
    dialog.close()

print("SCREENSHOT CAPTURE COMPLETE.", flush=True)
