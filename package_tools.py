"""Create a checked, offline payload before packaging."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
manifest = {}
with zipfile.ZipFile(root / 'tools.zip', 'w', compression=zipfile.ZIP_STORED) as archive:
    for name in ('yt-dlp', 'deno', 'ffmpeg', 'ffprobe'):
        path = root / 'vendor' / (name + '.exe')
        with path.open('rb') as source:
            if source.read(2) != b'MZ':
                raise ValueError(f'Invalid Windows executable: {path}')
            source.seek(0)
            manifest[path.name] = hashlib.file_digest(source, 'sha256').hexdigest()
        archive.write(path, path.name)
(root / 'tools-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
