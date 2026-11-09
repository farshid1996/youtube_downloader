"""Run with portable/.venv/bin/python -m pytest portable/test_native.py."""
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest

HERE=Path(__file__).resolve().parent

@pytest.fixture
def native(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path))
    monkeypatch.setenv('HOME',str(tmp_path))
    sys.path.insert(0,str(HERE))
    import launcher
    monkeypatch.setattr(launcher.engine,'DATA',tmp_path)
    monkeypatch.setattr(launcher.main,'DATA',tmp_path)
    return launcher


def test_native_tool_repair_and_permissions(native,tmp_path,monkeypatch):
    import hashlib
    payload=tmp_path/'payload';payload.mkdir()
    content=b'#!/bin/sh\necho tool\n'
    manifest={name:hashlib.sha256(content).hexdigest() for name in native.engine.TOOL_NAMES}
    (payload/'native-tools.json').write_text(json.dumps(manifest))
    with zipfile.ZipFile(payload/'native-tools.zip','w') as archive:
        for name in manifest:archive.writestr(name,content)
    monkeypatch.setattr(native,'PAYLOAD',payload)
    target=Path(native.tool('ffmpeg'))
    assert os.access(target,os.X_OK) and target.read_bytes()==content
    target.chmod(0o600)
    assert os.access(native.tool('ffmpeg'),os.X_OK)
    target.write_bytes(b'corrupt')
    assert Path(native.tool('ffmpeg')).read_bytes()==content
    target.unlink()
    assert Path(native.tool('ffmpeg')).read_bytes()==content
    with pytest.raises(ValueError):native.tool('../invalid')


def test_child_environment(native,monkeypatch):
    monkeypatch.setenv('LD_LIBRARY_PATH','/bundle')
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG','/system')
    assert native.child_environment()['LD_LIBRARY_PATH']=='/system'
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG')
    assert 'LD_LIBRARY_PATH' not in native.child_environment()


def test_process_session_and_cancel(native):
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    window=native.main.Window();window.timer.stop()
    process=window.process()
    try:
        process.setProgram('/bin/sleep');process.setArguments(['60']);process.start()
        assert process.waitForStarted(5000)
        pid=int(process.processId())
        assert os.getpgid(pid)==pid
        window.stop_process(process)
        assert process.waitForFinished(5000)
    finally:
        process.kill();window.close();app.processEvents()
