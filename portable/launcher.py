"""Native POSIX entry point; the Windows application sources are unmodified."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import zipfile

if sys.platform not in ('linux', 'darwin'):
    raise SystemExit('Use main.py / the existing EXE on Windows.')

SOURCE = Path(__file__).resolve().parents[1]
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(SOURCE))
base = (Path.home()/'Library'/'Application Support' if sys.platform == 'darwin'
        else Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local'/'share'))))
# engine initializes DATA on import. Supply the native location before importing it.
os.environ['LOCALAPPDATA'] = str(base)
import engine

PAYLOAD = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent/'payload'


def tool(name):
    if name not in engine.TOOL_NAMES:
        raise ValueError('Unknown bundled tool: '+name)
    try:
        manifest = json.loads((PAYLOAD/'native-tools.json').read_text())
        digest = manifest[name]
        version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
        directory = engine.DATA/'tools'/('native-'+version)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory/name
        stamp = directory/(name+'.verified')
        if target.is_file():
            stat = target.stat()
            verified = f'{stat.st_size}:{stat.st_mtime_ns}'
            if ((stamp.is_file() and stamp.read_text() == verified)
                    or hashlib.sha256(target.read_bytes()).hexdigest() == digest):
                target.chmod(0o755)
                stamp.write_text(verified)
                return str(target)
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(PAYLOAD/'native-tools.zip') as archive:
                data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != digest:
                raise OSError('Bundled tool integrity check failed: '+name)
            temporary.write_bytes(data)
            temporary.chmod(0o755)
            temporary.replace(target)
            stat = target.stat()
            stamp.write_text(f'{stat.st_size}:{stat.st_mtime_ns}')
        finally:
            temporary.unlink(missing_ok=True)
        return str(target)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise OSError(f'Could not prepare {name}: {exc}') from exc


def child_environment():
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
    # External native tools must not load the GUI bundle's shared libraries.
    for key in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
        if key+'_ORIG' in env:
            env[key] = env[key+'_ORIG']
        else:
            env.pop(key, None)
    return env


engine.tool = tool
engine.child_environment = child_environment
import main
from PySide6.QtCore import QProcess, QProcessEnvironment

original_process = main.Window.process


def process(self):
    result = original_process(self)
    environment = QProcessEnvironment()
    for key, value in child_environment().items():
        environment.insert(key, value)
    result.setProcessEnvironment(environment)
    params = QProcess.UnixProcessParameters()
    params.flags = QProcess.UnixProcessFlag.CreateNewSession
    result.setUnixProcessParameters(params)
    return result


def stop_process(self, process):
    pid = int(process.processId())
    if not pid:
        return
    try:
        # Each downloader owns a new session; stop its FFmpeg descendants too.
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


main.Window.process = process
main.Window.stop_process = stop_process
# The existing bundle verifier uses the Windows constant. A module-local facade
# makes its value a POSIX no-op without modifying Python's subprocess module.
main.subprocess = types.SimpleNamespace(**{name:getattr(subprocess,name) for name in dir(subprocess)})
main.subprocess.CREATE_NO_WINDOW = 0

if __name__ == '__main__':
    main.main()
