from pathlib import Path

from system_check import check_runtime, summary


def test_runtime_check_uses_bundled_tool_paths_without_installing(tmp_path):
    binary = tmp_path / "fake.exe"
    binary.write_bytes(b"test")
    def provider(name):
        return str(binary)
    results = check_runtime(tool_provider=provider, frozen=True,
                            data_dir=tmp_path, destination=tmp_path,
                            execute_tools=False)
    report = summary(results)
    assert report["ready"]
    assert all(item.status == "ok" for item in results if item.required)
    assert binary.read_bytes() == b"test"


def test_missing_required_tool_is_reported_not_installed(tmp_path):
    def provider(name):
        raise FileNotFoundError(name)
    results = check_runtime(tool_provider=provider, frozen=True,
                            data_dir=tmp_path, execute_tools=False)
    report = summary(results)
    assert not report["ready"]
    missing = {item["key"] for item in report["missing_required"]}
    assert "tool-yt-dlp" in missing
    assert any(item["install_url"] for item in report["missing_required"])
    assert not list(tmp_path.glob("*.exe"))


def test_optional_browser_does_not_block_startup(tmp_path, monkeypatch):
    import system_check
    monkeypatch.setattr(system_check, "_browser_installed", lambda name: False)
    binary = tmp_path / "fake.exe"
    binary.write_bytes(b"test")
    results = check_runtime(tool_provider=lambda name: str(binary),
                            browser="Firefox", frozen=True, data_dir=tmp_path,
                            execute_tools=False)
    report = summary(results)
    assert report["ready"]
    browser = next(item for item in results if item.key == "browser")
    assert browser.status == "warning"
    assert browser.required is False

def test_gui_hides_internal_audit_and_utility_buttons(tmp_path, monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import main
    from PySide6.QtWidgets import QApplication, QPushButton
    monkeypatch.setattr(main, "DATA", tmp_path)
    app = QApplication.instance() or QApplication([])
    window = main.Window()
    window.timer.stop()
    try:
        assert "check_on_startup" in window.controls
        labels = {button.text() for button in window.findChildren(QPushButton)}
        assert "System check" in labels
        assert "Update engine" in labels
        assert "Multi-agent audit" not in labels
        assert "Licenses" not in labels
        assert "Export log" not in labels
        assert window.audit_process is None
    finally:
        window.close()
        app.processEvents()

def test_parallel_first_run_tool_extraction_is_serialized(tmp_path, monkeypatch):
    import hashlib
    import json
    import sys
    import zipfile
    from concurrent.futures import ThreadPoolExecutor
    import engine

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    payload = {name + ".exe": ("tool-" + name).encode() for name in engine.TOOL_NAMES}
    with zipfile.ZipFile(bundle / "tools.zip", "w") as archive:
        for name, data in payload.items():
            archive.writestr(name, data)
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    (bundle / "tools-manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(engine, "ROOT", bundle)
    monkeypatch.setattr(engine, "DATA", tmp_path / "app-data")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(engine.tool, ["ffmpeg"] * 24))
    assert len(set(paths)) == 1
    assert all(Path(path).read_bytes() == payload["ffmpeg.exe"] for path in paths)

def test_low_disk_preflight_does_not_extract_bundled_tools(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import system_check

    monkeypatch.setattr(system_check, "_writable", lambda path: (True, "Writable."))
    monkeypatch.setattr(system_check.shutil, "disk_usage",
                        lambda path: SimpleNamespace(free=300 * 1024 * 1024))
    called = []
    results = system_check.check_runtime(
        tool_provider=lambda name: called.append(name) or str(tmp_path / (name + ".exe")),
        frozen=True, data_dir=tmp_path, execute_tools=False
    )
    assert called == []
    disk = next(item for item in results if item.key == "disk")
    assert disk.status == "missing"
    assert all(next(item for item in results if item.key == "tool-" + name).status == "warning"
               for name in system_check.TOOL_NAMES)
    assert not system_check.summary(results)["ready"]

def test_system_check_dialog_renders_clean_status_rows_and_real_line_breaks(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QLabel
    from system_check import Result, summary
    import main

    app = QApplication.instance() or QApplication([])
    results = [
        Result("platform", "ok", "Operating system", "Windows 10 (AMD64)"),
        Result("tool-yt-dlp", "ok", "yt-dlp", "Version 2026.10.26"),
        Result("browser", "warning", "Firefox (optional cookies source)",
               "Browser not detected.\\nChoose None or install Firefox if you need browser cookies.",
               required=False),
    ]
    dialog = main.SystemCheckDialog(results, summary(results))
    try:
        assert dialog.windowTitle() == "System compatibility"
        labels = dialog.findChildren(QLabel)
        assert any(label.text() == "Everything is ready" for label in labels)
        details = [label.text() for label in labels if label.objectName() == "rowDetail"]
        assert any("\n" in value for value in details)
        assert all(r"\n" not in value for value in details)
        assert any(label.text() == "Optional integrations" for label in labels)
    finally:
        dialog.close()
        app.processEvents()

def test_orchestrator_recognizes_the_current_install_consent_ui():
    import project_orchestrator
    security = project_orchestrator.security_agent()
    ux = project_orchestrator.ux_agent()
    security_consent = next(item for item in security
                            if item.item == "Consent before third-party installation")
    ux_install = next(item for item in ux if item.item == "User-approved installation link")
    ux_no_silent = next(item for item in ux if item.item == "No silent installation")
    assert security_consent.level == "pass"
    assert ux_install.level == "pass"
    assert ux_no_silent.level == "pass"

def test_system_dialog_native_close_and_explicit_close_controls(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from system_check import Result, summary
    import main

    app = QApplication.instance() or QApplication([])
    results = [Result("platform", "ok", "Operating system", "Windows 10 (AMD64)")]
    dialog = main.SystemCheckDialog(results, summary(results))
    try:
        assert dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint
        assert dialog.window_close_button.accessibleName() == "Close system compatibility window"
        dialog.show()
        app.processEvents()
        dialog.window_close_button.click()
        app.processEvents()
        assert not dialog.isVisible()

        second = main.SystemCheckDialog(results, summary(results))
        second.show()
        app.processEvents()
        second.close_shortcut.activated.emit()
        app.processEvents()
        assert not second.isVisible()

        third = main.SystemCheckDialog(results, summary(results))
        third.show()
        app.processEvents()
        third.close()  # exercises the same closeEvent path used by the native title-bar X
        app.processEvents()
        assert not third.isVisible()
    finally:
        dialog.close()
        app.processEvents()


def test_simple_advanced_professional_workspaces_and_speed_presets(tmp_path, monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    import main

    monkeypatch.setattr(main, "DATA", tmp_path)
    app = QApplication.instance() or QApplication([])
    window = main.Window()
    window.timer.stop()
    try:
        window.set_experience_level("Simple")
        assert window.tabs.isTabVisible(0)
        assert all(not window.tabs.isTabVisible(i) for i in (1, 2, 3, 4))

        window.set_experience_level("Advanced")
        assert all(window.tabs.isTabVisible(i) for i in (0, 1, 2, 3))
        assert not window.tabs.isTabVisible(4)

        window.set_experience_level("Professional")
        assert all(window.tabs.isTabVisible(i) for i in range(5))

        window.preset_combo.setCurrentText("Maximum speed")
        assert window.controls["parallel"].value() == 5
        assert window.controls["fragments"].value() == 16
        window.preset_combo.setCurrentText("Maximum reliability")
        assert window.controls["parallel"].value() == 1
        assert window.controls["retries"].value() == 12

        window.controls["mode"].setCurrentText("MP3 audio")
        assert not window.controls["quality"].isEnabled()
        assert window.controls["bitrate"].isEnabled()
        window.controls["mode"].setCurrentText("MP4 video")
        assert window.controls["quality"].isEnabled()
        assert not window.controls["bitrate"].isEnabled()

        window.schedule_render("job-a")
        window.schedule_render("job-b")
        assert window._dirty_job_ids == {"job-a", "job-b"}
        window.schedule_render()
        assert window._full_render_pending
        assert not window._dirty_job_ids
    finally:
        window.close()
        app.processEvents()

def test_ui_ux_design_research_agents_and_design_system_are_present():
    import project_orchestrator as research

    expected = {
        "UX research", "Visual design", "Interaction and motion",
        "Accessibility", "Performance engineering", "Professional workflow",
    }
    assert expected.issubset(research.AGENTS)
    assert len(research.AGENTS) == 13
    for name in expected:
        findings = research.AGENTS[name](False)
        assert findings
        assert all(item.level == "pass" for item in findings), name

    design = research.render_design_system()
    for section in ("Simple", "Advanced", "Professional", "Liquid Glass",
                    "Interaction contract", "Accessibility", "Performance contract"):
        assert section in design
