import urllib.request,pathlib,zipfile,shutil
p=pathlib.Path('vendor')
for url,name in [('https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe','yt-dlp.exe'),('https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip','deno.zip')]:
 print('Downloading',name,flush=True)
 urllib.request.urlretrieve(url,p/name)
 if name.endswith('.zip'):
  with zipfile.ZipFile(p/name) as z:z.extract('deno.exe',p)
  (p/name).unlink()
for name in ['ffmpeg.exe','ffprobe.exe']:shutil.copy2(pathlib.Path('C:/bin')/name,p/name)
print('Tools ready',flush=True)
