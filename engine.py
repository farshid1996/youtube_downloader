"""Pure argument construction and durable storage; no shell command interpolation."""
import json
import hashlib
import os
import re
import sys
import shutil
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
DATA = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'YouTubeDownloaderStudio'
DATA.mkdir(parents=True, exist_ok=True)

TOOL_NAMES = ('yt-dlp', 'deno', 'ffmpeg', 'ffprobe')
_TOOL_LOCK = threading.RLock()

def _tool_unlocked(name):
    """Locate a bundled executable; unpack and hash-verify on first use.

    Executables are placed in manifest-versioned user storage. A verified stamp
    avoids re-hashing huge binaries on each call; a missing/corrupt tool is
    atomically restored without exposing a partially written executable.
    """
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

def tool(name):
    # Multiple audit agents and GUI actions may request the same first-run tool.
    # Serialize extraction so no caller observes a half-installed executable.
    with _TOOL_LOCK:
        return _tool_unlocked(name)

def child_environment():
    """Give spawned subprocesses a clean PyInstaller runtime environment."""
    return {**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}

def urls(text):
    """Parse distinct HTTP(S) links, removing invisible formatting marks.

    Reject non-web schemes and credential-bearing URLs before constructing a
    yt-dlp process argument list.
    """
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
    """Persist JSON through an atomic replace to avoid a truncated queue."""
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def read(path, default):
    """Load saved JSON, tolerating missing or invalid application state."""
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default

def arguments(url, s, inspect=False):
    """Build yt-dlp argv without passing untrusted URLs through a shell.

    Inspect mode requests a single JSON description; normal mode composes
    format, download, retry, post-processing and optional expert filters.
    """
    tool('ffprobe')
    retries = int(s.get('retries', 5))
    extractor_retries = int(s.get('extractor_retries', 3))
    file_access_retries = int(s.get('file_access_retries', 3))
    socket_timeout = int(s.get('socket_timeout', 25))
    args = [
        '--ignore-config', '--no-color', '--newline', '--encoding', 'utf-8',
        '--ffmpeg-location', str(Path(tool('ffmpeg')).parent),
        '--js-runtimes', 'deno:' + tool('deno'),
        '--socket-timeout', str(socket_timeout),
        '--retries', str(retries), '--fragment-retries', str(retries),
        '--extractor-retries', str(extractor_retries),
        '--file-access-retries', str(file_access_retries),
    ]
    if s.get('proxy'):
        args += ['--proxy', str(s['proxy'])]
    if s.get('cookies'):
        args += ['--cookies', str(s['cookies'])]
    elif s.get('browser', 'None') != 'None':
        args += ['--cookies-from-browser', str(s['browser']).lower()]
    network = s.get('network_preference', 'Auto')
    if network == 'IPv4 only':
        args += ['--force-ipv4']
    elif network == 'IPv6 only':
        args += ['--force-ipv6']
    if inspect:
        return args + ['--no-playlist', '--skip-download', '--dump-single-json', '--', url]

    mode = s.get('mode', 'MP4 video')
    height = s.get('quality', 'Best available')
    profile = mode.split()[0].lower() + '-' + (
        ('best' if height == 'Best available' else height) if mode.endswith('video')
        else s.get('bitrate', '192') + 'k')

    output = '%(title).100B [%(id)s] [' + profile + '].%(ext)s'
    custom_output = str(s.get('output_template', '')).strip()
    if custom_output:
        normalized = custom_output.replace('\\', '/')
        if ('\n' in custom_output or '\r' in custom_output or '\0' in custom_output
                or normalized.startswith('/') or re.match(r'^[A-Za-z]:', custom_output)
                or '..' in normalized.split('/')):
            raise ValueError('The output template must be a relative path inside the selected destination.')
        output = custom_output

    args += [
        '--yes-playlist' if s.get('playlist') else '--no-playlist',
        '--continue', '--no-overwrites', '--windows-filenames', '--trim-filenames', '180',
        '--concurrent-fragments', str(s.get('fragments', 4)),
        '-P', s['folder'], '-o', output,
        '--progress',
        '--progress-template', 'download:PROGRESS|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s',
        '--print', 'before_dl:TITLE|%(title)s',
        '--print', 'after_move:FILE|%(filepath)s', '--no-quiet',
    ]
    if s.get('restrict_filenames'):
        args += ['--restrict-filenames']

    cap = '' if height == 'Best available' else '[height<=' + re.sub(r'\D', '', str(height)) + ']'
    custom_format = str(s.get('format_selector', '')).strip()
    if any(char in custom_format for char in ('\n', '\r', '\0')):
        raise ValueError('The custom format selector must be a single line.')
    if custom_format:
        args += ['-f', custom_format]
    elif mode == 'MP4 video':
        args += ['-f', f'bv*{cap}[ext=mp4]+ba[ext=m4a]/b{cap}[ext=mp4]/bv*{cap}+ba/b{cap}']
    elif mode == 'MKV video':
        args += ['-f', f'bv*{cap}+ba/b{cap}']
    else:
        args += ['-f', 'ba/b']

    if mode == 'MP4 video':
        args += ['--merge-output-format', 'mp4', '--remux-video', 'mp4']
    elif mode == 'MKV video':
        args += ['--merge-output-format', 'mkv', '--remux-video', 'mkv']
    else:
        args += ['-x', '--audio-format',
                 {'MP3 audio': 'mp3', 'M4A audio': 'm4a', 'FLAC audio': 'flac', 'WAV audio': 'wav'}[mode],
                 '--audio-quality', str(s.get('bitrate', '192')) + 'K']

    if s.get('rate', 0):
        args += ['--limit-rate', str(s['rate']) + 'K']
    if s.get('items'):
        args += ['--playlist-items', str(s['items'])]
    if s.get('metadata'):
        args += ['--embed-metadata', '--embed-chapters']
    if s.get('thumbnail'):
        args += ['--write-thumbnail']
    if s.get('embed_thumbnail'):
        args += ['--embed-thumbnail']

    if s.get('subtitles') or s.get('embed_subs'):
        args += ['--write-subs', '--sub-langs', s.get('languages') or 'en.*,fa.*',
                 '--sub-format', 'srt/best', '--convert-subs', 'srt']
    if s.get('auto_subs'):
        args += ['--write-auto-subs']
    if s.get('embed_subs'):
        args += ['--embed-subs']
    if s.get('write_description'):
        args += ['--write-description']
    if s.get('write_info_json'):
        args += ['--write-info-json']
    if s.get('write_comments'):
        args += ['--write-comments']

    sponsorblock = s.get('sponsorblock', 'Off')
    if sponsorblock == 'Mark all segments':
        args += ['--sponsorblock-mark', 'all']
    elif sponsorblock == 'Remove all segments':
        args += ['--sponsorblock-remove', 'all']

    for key, flag in (('date_after', '--dateafter'), ('date_before', '--datebefore')):
        value = str(s.get(key, '')).strip()
        if value:
            try:
                datetime.strptime(value, '%Y%m%d')
            except ValueError as exc:
                raise ValueError(f'{key.replace("_", " ").title()} must use YYYYMMDD and be a valid date.') from exc
            args += [flag, value]
    after = str(s.get('date_after', '')).strip()
    before = str(s.get('date_before', '')).strip()
    if after and before and after > before:
        raise ValueError('The upload start date must not be later than the end date.')

    match_title = str(s.get('match_title', '')).strip()
    if match_title:
        try:
            re.compile(match_title)
        except re.error as exc:
            raise ValueError(f'Title regular expression is invalid: {exc}') from exc
        args += ['--match-title', match_title]

    file_sizes = {}
    for key, flag in (('min_filesize', '--min-filesize'), ('max_filesize', '--max-filesize')):
        value = str(s.get(key, '')).strip()
        if value:
            if not re.fullmatch(r'\d+(?:\.\d+)?[KMG]?', value, re.IGNORECASE):
                raise ValueError(f'{key.replace("_", " ").title()} must be a size such as 100M or 1G.')
            number = float(re.match(r'\d+(?:\.\d+)?', value).group())
            suffix = value[-1].upper() if value[-1].isalpha() else ''
            file_sizes[key] = int(number * (1024 ** {'': 0, 'K': 1, 'M': 2, 'G': 3}[suffix]))
            args += [flag, value]
    if ('min_filesize' in file_sizes and 'max_filesize' in file_sizes
            and file_sizes['min_filesize'] > file_sizes['max_filesize']):
        raise ValueError('Minimum file size must not exceed maximum file size.')

    extractor_args = str(s.get('extractor_args', '')).strip()
    if any(char in extractor_args for char in ('\n', '\r', '\0')):
        raise ValueError('Extractor arguments must be a single line.')
    if extractor_args:
        args += ['--extractor-args', extractor_args]

    sleep_min = int(s.get('sleep_interval', 0))
    sleep_max = int(s.get('max_sleep_interval', 0))
    if sleep_max and (not sleep_min or sleep_max < sleep_min):
        raise ValueError('Set a minimum request delay and make the maximum delay equal or higher.')
    if sleep_min:
        args += ['--sleep-interval', str(sleep_min)]
    if sleep_max:
        args += ['--max-sleep-interval', str(sleep_max)]

    chunk_size = s.get('http_chunk_size', 'Off')
    if chunk_size and chunk_size != 'Off':
        args += ['--http-chunk-size', str(chunk_size)]

    if s.get('archive'):
        destination = os.path.normcase(str(Path(s['folder']).resolve()))
        key = hashlib.sha256((destination + '\\n' + profile).encode()).hexdigest()[:24]
        args += ['--download-archive', str(DATA / ('archive-' + key + '.txt'))]
    return args + ['--', url]
