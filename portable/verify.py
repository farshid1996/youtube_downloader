"""Isolated packaged GUI and localhost-media integration check."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

executable=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='ytdl-native-check-') as directory:
    home=Path(directory)
    env=dict(os.environ,HOME=str(home),XDG_DATA_HOME=str(home),PYINSTALLER_RESET_ENVIRONMENT='1')
    # Qt's offscreen backend does not verify native window-system dependencies.
    env.pop('QT_QPA_PLATFORM',None)
    for option in ('--smoke-test','--verify-bundle'):
        subprocess.run([str(executable),option],env=env,check=True,timeout=240)
    data=(home/'Library'/'Application Support' if sys.platform=='darwin' else home)/'YouTubeDownloaderStudio'
    assert (data/'smoke-test.png').stat().st_size>1000
    report=json.loads((data/'bundle-verification.json').read_text())
    assert report['success'] and report['download_check'],report
    output=executable.parents[3] if sys.platform=='darwin' else executable.parent
    (output/'native-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
