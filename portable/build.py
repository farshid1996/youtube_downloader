"""Build a standalone Linux binary or macOS app on the native host."""
import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def build():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-download',action='store_true')
    args=parser.parse_args()
    if sys.platform not in ('linux','darwin'):
        parser.error('Run under Linux (WSL works) or macOS, not Windows Python.')
    arch={'x86_64':'x64','amd64':'x64','arm64':'arm64','aarch64':'arm64'}[platform.machine().lower()]
    target=('macos' if sys.platform=='darwin' else 'linux')+'-'+arch
    if not args.skip_download:
        subprocess.run([sys.executable,str(HERE/'prepare.py')],check=True)
    payload=HERE/'payload'
    import json
    info=json.loads((payload/'native-sources.json').read_text())
    if (info['platform'],info['arch']) != (sys.platform,arch):
        raise RuntimeError('Payload belongs to a different OS or architecture. Rerun without --skip-download.')
    output=ROOT/'dist'/target;output.mkdir(parents=True,exist_ok=True)
    work=ROOT/'build'/'portable'/target;work.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--noupx',
        '--name','YouTubeDownloader','--paths',str(ROOT),'--distpath',str(output),
        '--workpath',str(work/'work'),'--specpath',str(work)]
    if sys.platform=='darwin':
        command+=['--windowed','--onedir','--osx-bundle-identifier','local.youtube-downloader.studio']
        if os.getenv('MACOS_SIGNING_IDENTITY'):
            command+=['--codesign-identity',os.environ['MACOS_SIGNING_IDENTITY']]
    else:
        command+=['--onefile']
    for source,destination in [(ROOT/'assets','assets'),(ROOT/'app.ico','.'),
            (payload/'native-tools.zip','.'),(payload/'native-tools.json','.'),
            (payload/'native-sources.json','.'),(payload/'native-licenses','native-licenses'),
            (payload/'THIRD_PARTY_NOTICES.txt','.'),(HERE/'README.md','.')]:
        command+=['--add-data',str(source)+os.pathsep+destination]
    command+=[str(HERE/'launcher.py')]
    subprocess.run(command,check=True)
    if sys.platform=='darwin':
        app=output/'YouTubeDownloader.app'
        subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(output/'YouTubeDownloader-macos.zip')],check=True)
        dmg=output/'YouTubeDownloader.dmg'
        subprocess.run(['hdiutil','create','-volname','YouTube Downloader','-srcfolder',str(app),'-ov','-format','UDZO',str(dmg)],check=True)
        print('Created '+str(dmg))
    else:
        with tarfile.open(output/'YouTubeDownloader-linux.tar.gz','w:gz') as archive:
            archive.add(output/'YouTubeDownloader',arcname='YouTubeDownloader')
            archive.add(HERE/'README.md',arcname='README.md')
        print('Created '+str(output/'YouTubeDownloader'))

if __name__=='__main__':
    build()
