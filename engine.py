"""Pure argument construction and durable storage; no shell command interpolation."""
import json
import hashlib
import os
import re
import sys
import shutil
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
DATA = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'YouTubeDownloaderStudio'
DATA.mkdir(parents=True, exist_ok=True)

TOOL_NAMES = ('yt-dlp', 'deno', 'ffmpeg', 'ffprobe')

def tool(name):
    if name not in TOOL_NAMES:
        raise ValueError('Unknown bundled tool: ' + name)
    if not getattr(sys, 'frozen', False):
        return str(ROOT / 'vendor' / (name + '.exe'))
    import tempfile
    import zipfile
    filename = name + '.exe'
    try:
        manifest = json.loads((ROOT / 'tools-manifest.json').read_text(encoding='utf-8'))
        digest = manifest[filename]
        # Versioned tools avoid replacing executables used by another app instance.
        directory = DATA / 'tools' / hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / filename
        stamp = directory / (filename + '.verified')
        if target.is_file() and stamp.is_file():
            stat = target.stat()
            if stamp.read_text() == f'{stat.st_size}:{stat.st_mtime_ns}':
                return str(target)
        existing_digest = None
        if target.is_file():
            with target.open('rb') as source:
                existing_digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if existing_digest == digest:
            stat = target.stat()
            stamp.write_text(f'{stat.st_size}:{stat.st_mtime_ns}')
            return str(target)
        with tempfile.NamedTemporaryFile(dir=directory, suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
        try:
            with zipfile.ZipFile(ROOT / 'tools.zip') as archive:
                with archive.open(filename) as source, temporary.open('wb') as destination:
                    shutil.copyfileobj(source, destination)
            with temporary.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
                    raise OSError('Bundled tool integrity check failed: ' + filename)
            temporary.replace(target)
            stat = target.stat()
            stamp.write_text(f'{stat.st_size}:{stat.st_mtime_ns}')
        finally:
            temporary.unlink(missing_ok=True)
        return str(target)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise OSError(f'Could not prepare {filename}. Restart the app to repair its tools. '
                      f'If this continues, check available disk space and security-software quarantine. Details: {exc}') from exc

def child_environment():
    return {**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}

def urls(text):
    result = []
    for value in text.splitlines():
        value = ''.join(c for c in value.strip().strip('\"\'') if unicodedata.category(c) != 'Cf')
        if not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username:
            raise ValueError('Enter complete http:// or https:// links, one per line.')
        if value not in result:
            result.append(value)
    return result

def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def read(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default

def arguments(url, s, inspect=False):
    tool('ffprobe')
    args = ['--ignore-config', '--no-color', '--newline', '--encoding', 'utf-8',
            '--ffmpeg-location', str(Path(tool('ffmpeg')).parent), '--js-runtimes', 'deno:' + tool('deno'),
            '--socket-timeout', '25', '--retries', str(s.get('retries', 5)),
            '--fragment-retries', str(s.get('retries', 5))]
    if s.get('proxy'): args += ['--proxy', s['proxy']]
    if s.get('cookies'): args += ['--cookies', s['cookies']]
    elif s.get('browser', 'None') != 'None': args += ['--cookies-from-browser', s['browser'].lower()]
    if inspect:
        return args + ['--no-playlist', '--skip-download', '--dump-single-json', '--', url]
    mode = s.get('mode', 'MP4 video')
    height = s.get('quality', 'Best available')
    # Include the requested profile even in intermediate filenames. Audio-only
    # and video jobs must not reuse one another's source files either.
    profile = mode.split()[0].lower() + '-' + (
        ('best' if height == 'Best available' else height) if mode.endswith('video')
        else s.get('bitrate', '192') + 'k')
    output = '%(title).100B [%(id)s] [' + profile + '].%(ext)s'
    args += ['--yes-playlist' if s.get('playlist') else '--no-playlist', '--continue', '--no-overwrites',
             '--windows-filenames', '--trim-filenames', '180', '--concurrent-fragments', str(s.get('fragments', 4)),
             '-P', s['folder'], '-o', output,
             '--progress', '--progress-template', 'download:PROGRESS|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s',
             '--print', 'before_dl:TITLE|%(title)s', '--print', 'after_move:FILE|%(filepath)s', '--no-quiet']
    cap = '' if height == 'Best available' else '[height<=' + re.sub(r'\D', '', height) + ']'
    if mode == 'MP4 video':
        args += ['-f', f'bv*{cap}[ext=mp4]+ba[ext=m4a]/b{cap}[ext=mp4]/bv*{cap}+ba/b{cap}', '--merge-output-format', 'mp4', '--remux-video', 'mp4']
    elif mode == 'MKV video':
        args += ['-f', f'bv*{cap}+ba/b{cap}', '--merge-output-format', 'mkv', '--remux-video', 'mkv']
    else:
        args += ['-f', 'ba/b', '-x', '--audio-format', {'MP3 audio':'mp3','M4A audio':'m4a','FLAC audio':'flac','WAV audio':'wav'}[mode], '--audio-quality', s.get('bitrate','192') + 'K']
    if s.get('rate', 0): args += ['--limit-rate', str(s['rate']) + 'K']
    if s.get('items'): args += ['--playlist-items', s['items']]
    if s.get('metadata'): args += ['--embed-metadata', '--embed-chapters']
    if s.get('thumbnail'): args += ['--write-thumbnail']
    if s.get('subtitles'):
        args += ['--write-subs', '--sub-langs', s.get('languages') or 'en.*,fa.*', '--sub-format', 'srt/best', '--convert-subs', 'srt']
    if s.get('auto_subs'): args += ['--write-auto-subs']
    if s.get('archive'):
        destination = os.path.normcase(str(Path(s['folder']).resolve()))
        key = hashlib.sha256((destination + '\n' + profile).encode()).hexdigest()[:24]
        args += ['--download-archive', str(DATA / ('archive-' + key + '.txt'))]
    return args + ['--', url]
