import subprocess,pathlib
from engine import arguments,tool
s={'folder':str(pathlib.Path('test_downloads').resolve()),'mode':'MP4 video','quality':'360p','metadata':True,'retries':2}
p=subprocess.run([tool('yt-dlp'),*arguments('https://www.youtube.com/watch?v=vDmjw-c_R2k',s)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace')
pathlib.Path('test-download.log').write_text(p.stdout,encoding='utf-8')
print(p.stdout[-6500:]);print('EXIT',p.returncode)
