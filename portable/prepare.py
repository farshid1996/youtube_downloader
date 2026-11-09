"""Download native tools into an isolated payload. Run on the target OS."""
import hashlib
import io
import json
import platform
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
YTDLP = '2026.10.26'
DENO = 'v2.9.8'
FFMPEG = 'b6.1.1'


def download(url):
    print('Downloading '+url, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent':'YouTubeDownloader-build'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def prepare():
    machine = platform.machine().lower()
    arch = {'x86_64':'x64','amd64':'x64','aarch64':'arm64','arm64':'arm64'}[machine]
    system = {'linux':'linux','darwin':'darwin'}[sys.platform]
    payload = ROOT/'payload'; payload.mkdir(exist_ok=True)
    cache = ROOT/'downloads'/f'{system}-{arch}'; cache.mkdir(parents=True,exist_ok=True)
    sources = {}

    def get(url):
        path=cache/url.rsplit('/',1)[-1]
        if not path.exists():
            data=download(url); temporary=path.with_suffix(path.suffix+'.tmp')
            temporary.write_bytes(data); temporary.replace(path)
        sources[url]=hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_bytes()

    ybase=f'https://github.com/yt-dlp/yt-dlp/releases/download/{YTDLP}/'
    yname='yt-dlp_macos' if system=='darwin' else 'yt-dlp_linux'+('_aarch64' if arch=='arm64' else '')
    ydata=get(ybase+yname)
    checks={line.split()[1].lstrip('*'):line.split()[0] for line in get(ybase+'SHA2-256SUMS').decode().splitlines() if line.strip()}
    if hashlib.sha256(ydata).hexdigest()!=checks[yname]:
        raise ValueError('yt-dlp upstream checksum mismatch')
    darch='aarch64' if arch=='arm64' else 'x86_64'
    dtarget='apple-darwin' if system=='darwin' else 'unknown-linux-gnu'
    dname=f'deno-{darch}-{dtarget}.zip'
    dbase=f'https://github.com/denoland/deno/releases/download/{DENO}/'
    ddata=get(dbase+dname)
    if hashlib.sha256(ddata).hexdigest()!=get(dbase+dname+'.sha256sum').decode().split()[0]:
        raise ValueError('Deno upstream checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(ddata)) as archive:
        deno=archive.read('deno')
    fbase=f'https://github.com/eugeneware/ffmpeg-static/releases/download/{FFMPEG}/'
    tools={'yt-dlp':ydata,'deno':deno}
    for name in ('ffmpeg','ffprobe'):
        tools[name]=get(fbase+f'{name}-{system}-{arch}')
    licenses=payload/'native-licenses';licenses.mkdir(exist_ok=True)
    for suffix in ('LICENSE','README'):
        (licenses/('FFmpeg-'+suffix+'.txt')).write_bytes(get(fbase+f'{system}-{arch}.{suffix}'))
    for name,url in {
        'yt-dlp-LICENSE.txt':f'https://raw.githubusercontent.com/yt-dlp/yt-dlp/{YTDLP}/LICENSE',
        'Deno-LICENSE.txt':f'https://raw.githubusercontent.com/denoland/deno/{DENO}/LICENSE.md',
    }.items():
        (licenses/name).write_bytes(get(url))
    manifest={}
    with zipfile.ZipFile(payload/'native-tools.zip','w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in tools.items():
            executable=cache/name;executable.write_bytes(data);executable.chmod(0o755)
            flag='-version' if name in ('ffmpeg','ffprobe') else '--version'
            result=subprocess.run([str(executable),flag],capture_output=True,text=True,check=True,timeout=60)
            print(result.stdout.splitlines()[0],flush=True)
            archive.writestr(name,data)
            manifest[name]=hashlib.sha256(data).hexdigest()
    (payload/'native-tools.json').write_text(json.dumps(manifest,indent=2))
    (payload/'native-sources.json').write_text(json.dumps({'platform':system,'arch':arch,'sources':sources},indent=2))
    (payload/'THIRD_PARTY_NOTICES.txt').write_text(
        'Native Linux/macOS build of YouTube Downloader Studio.\n'
        'Python: PSF license. PySide6/Qt: LGPLv3/GPLv3/commercial. PyInstaller: GPL with bootloader exception.\n'
        f'yt-dlp {YTDLP}: Unlicense source; bundled dependencies have their own licenses.\n'
        f'Deno {DENO}: MIT. FFmpeg/FFprobe: ffmpeg-static {FFMPEG} binaries, GPL.\n'
        'See native-licenses for provider license and source/build information, and native-sources.json for URLs/hashes.\n'
        'https://github.com/eugeneware/ffmpeg-static https://ffmpeg.org/legal.html\n'
        'Prepared for personal use. Review component redistribution obligations before redistribution.\n')

if __name__=='__main__':
    prepare()
