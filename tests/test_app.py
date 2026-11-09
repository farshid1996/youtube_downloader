import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from engine import arguments, urls, tool

def test_single_file_tools_repair_and_updates(tmp_path,monkeypatch):
    import engine
    import hashlib
    import zipfile
    bundle=tmp_path/'bundle';bundle.mkdir()
    contents={name+'.exe':b'packaged '+name.encode() for name in engine.TOOL_NAMES}
    with zipfile.ZipFile(bundle/'tools.zip','w') as archive:
        for name,data in contents.items():archive.writestr(name,data)
    (bundle/'tools-manifest.json').write_text(json.dumps({name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}))
    monkeypatch.setattr(engine,'ROOT',bundle)
    monkeypatch.setattr(engine,'DATA',tmp_path/'user')
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    for name in engine.TOOL_NAMES:
        installed=Path(engine.tool(name))
        assert installed.read_bytes()==contents[name+'.exe']
        installed.unlink()
        assert Path(engine.tool(name)).read_bytes()==contents[name+'.exe']
        installed.write_bytes(b'corrupt')
        assert Path(engine.tool(name)).read_bytes()==contents[name+'.exe']
    installed=Path(engine.tool('yt-dlp'));installed.write_bytes(b'updated engine')
    stat=installed.stat();installed.with_name(installed.name+'.verified').write_text(f'{stat.st_size}:{stat.st_mtime_ns}')
    assert Path(engine.tool('yt-dlp')).read_bytes()==b'updated engine'
    assert Path(engine.tool('ffmpeg')).parent==Path(engine.tool('ffprobe')).parent


def test_url_validation():
    assert urls('\u200fhttps://youtu.be/example\nhttps://youtu.be/example') == ['https://youtu.be/example']
    for value in ['file:///C:/secret', '--exec calc', 'https://user:password@example.com']:
        with pytest.raises(ValueError): urls(value)

def test_arguments_keep_untrusted_text_separate():
    url='https://example.com/watch?q=a&x=1'
    args=arguments(url,{'folder':'C:/Downloads with spaces','mode':'MP3 audio','proxy':'http://localhost:1234'})
    assert args[-2:]==['--',url]
    assert args[args.index('--audio-format')+1]=='mp3'
    assert args[args.index('-P')+1]=='C:/Downloads with spaces'

@pytest.fixture(scope='module')
def server(tmp_path_factory):
    directory=tmp_path_factory.mktemp('media')
    subprocess.run([tool('ffmpeg'),'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440','-t','6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(directory/'sample.mp4')],check=True)
    for height,width in [(720,1280),(1080,1920)]:
        subprocess.run([tool('ffmpeg'),'-hide_banner','-loglevel','error','-f','lavfi','-i',f'color=c=blue:size={width}x{height}:rate=5','-f','lavfi','-i','sine=frequency=440','-t','1','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac',str(directory/f'{height}.mp4')],check=True)
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(directory))
    httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}/sample.mp4'
    httpd.shutdown();httpd.server_close()

def test_same_video_quality_upgrade_keeps_both_files(server,tmp_path,monkeypatch):
    import engine
    monkeypatch.setattr(engine,'DATA',tmp_path)
    info=tmp_path/'video.json'
    info.write_text(json.dumps({'id':'same-video','title':'Quality upgrade','extractor':'generic','extractor_key':'Generic',
        'webpage_url':server,'formats':[
            {'format_id':str(h),'url':server.replace('sample.mp4',f'{h}.mp4'),
             'height':h,'width':w,'ext':'mp4','vcodec':'h264','acodec':'aac'}
            for h,w in [(720,1280),(1080,1920)]]}))
    output=tmp_path/'downloads'
    for quality in ['720p','1080p']:
        args=arguments(server,{'folder':str(output),'mode':'MP4 video','quality':quality,'archive':True})
        result=subprocess.run([tool('yt-dlp'),*args[:-2],'--load-info-json',str(info)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert result.returncode==0,result.stdout+result.stderr
        assert 'PROGRESS|' in result.stdout
    files=list(output.glob('*.mp4'))
    assert len(files)==2
    heights=[]
    for file in files:
        result=subprocess.run([tool('ffprobe'),'-v','error','-select_streams','v:0','-show_entries','stream=height','-of','json',str(file)],capture_output=True,text=True,check=True)
        heights.append(json.loads(result.stdout)['streams'][0]['height'])
    assert sorted(heights)==[720,1080]
    assert any('[mp4-720p]' in f.name for f in files)
    assert any('[mp4-1080p]' in f.name for f in files)
    repeated=subprocess.run([tool('yt-dlp'),*args[:-2],'--load-info-json',str(info)],capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert repeated.returncode==0
    assert 'has already been recorded in the archive' in repeated.stdout
    assert len(list(output.glob('*.mp4')))==2

@pytest.mark.parametrize('mode,extension',[('MP4 video','mp4'),('MP3 audio','mp3')])
def test_actual_download_and_conversion(server,tmp_path,mode,extension):
    args=arguments(server,{'folder':str(tmp_path),'mode':mode,'metadata':True})
    result=subprocess.run([tool('yt-dlp'),*args],capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    files=list(tmp_path.glob('*.'+extension));assert len(files)==1
    probe=subprocess.run([tool('ffprobe'),'-v','error','-show_streams','-of','json',str(files[0])],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams']
    assert any(s['codec_type']=='audio' for s in streams)
    if extension=='mp4':assert any(s['codec_type']=='video' for s in streams)

def test_gui_queue_pause_resume_and_failure(server,tmp_path,monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    import main
    monkeypatch.setattr(main,'DATA',tmp_path)
    app=QApplication.instance() or QApplication([])
    window=main.Window();window.folder.setText(str(tmp_path/'output'));window.controls['rate'].setValue(4)
    def wait_for(predicate,timeout=25):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            app.processEvents()
            if predicate():return
            time.sleep(.03)
        raise AssertionError('Timed out: '+repr(window.jobs))
    try:
        window.links.setPlainText(server);window.add(True)
        wait_for(lambda:'%' in window.jobs[0]['progress'])
        bar=window.table.cellWidget(0,2)
        assert bar.maximum()==1000 and 0 < bar.value() < 1000
        window.pause();wait_for(lambda:window.jobs[0]['status']=='Paused')
        assert not window.running
        assert list((tmp_path/'output').glob('*.part'))
        window.jobs[0]['settings']['rate']=0
        window.resume();wait_for(lambda:window.jobs[0]['status']=='Completed')
        assert Path(window.jobs[0]['files'][0]).exists()
        assert window.table.cellWidget(0,2).value()==1000
        window.links.setPlainText(server);window.add(True)
        wait_for(lambda:window.jobs[-1]['status']=='Skipped')
        window.links.setPlainText(server.replace('sample.mp4','missing.mp4'));window.add(True)
        wait_for(lambda:window.jobs[-1]['status']=='Failed')
        assert '404' in window.jobs[-1]['error']
        window.persist()
        stored=json.loads((tmp_path/'queue.json').read_text())
        assert stored[0]['status']=='Completed'
        assert 'cookies' not in stored[0]['settings']
    finally:window.close();app.processEvents()

def test_context_menu_targets_and_scrollable_controls(tmp_path,monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox, QSpinBox
    import main
    monkeypatch.setattr(main,'DATA',tmp_path)
    app=QApplication.instance() or QApplication([])
    app.setStyle('Fusion');app.setStyleSheet(main.STYLE)
    w=main.Window();w.timer.stop();monkeypatch.setattr(w,'tick',lambda:None)
    kept=tmp_path/'keep.mp4';kept.write_bytes(b'keep existing media')
    def job(id):return dict(id=id,url='https://example.com/'+id,title=id,status='Paused',progress='',speed='',eta='',files=[str(kept)],settings={'mode':'MP4 video','folder':str(tmp_path)})
    a,b=job('first'),job('second');w.jobs=[a,b];w.render();w.table.selectRow(0)
    try:
        menu=w.job_menu([b]);actions={act.text():act for act in menu.actions()}
        assert not actions['Pause download'].isEnabled()
        actions['Start / resume / retry'].trigger()
        assert b['status']=='Queued' and a['status']=='Paused'
        menu.deleteLater()
        menu=w.job_menu([b]);actions={act.text():act for act in menu.actions()}
        assert actions['Pause download'].isEnabled()
        actions['Pause download'].trigger();assert b['status']=='Paused'
        actions['Copy video link'].trigger();assert app.clipboard().text()==b['url']
        actions['Download with different options…'].trigger();assert w.links.toPlainText()==b['url']
        actions['Remove from queue (keep files)'].trigger()
        assert w.jobs==[a] and kept.exists()
        menu.deleteLater()
        w.resize(960,650);w.show();app.processEvents()
        assert w.height()==650
        for i in range(w.tabs.count()):
            w.tabs.setCurrentIndex(i);app.processEvents()
            page=w.tabs.widget(i).widget()
            for control in page.findChildren(QLineEdit)+page.findChildren(QComboBox)+page.findChildren(QSpinBox):
                # Spin boxes contain an internal editor without outer padding.
                if isinstance(control.parent(),QSpinBox):continue
                assert control.height()>=control.fontMetrics().height()+12
        assert w.page_scroll.verticalScrollBar().maximum()>0
    finally:w.close();app.processEvents()

def test_bulk_selection_cleanup_and_retry(tmp_path,monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    import main
    monkeypatch.setattr(main,'DATA',tmp_path)
    app=QApplication.instance() or QApplication([])
    w=main.Window();w.timer.stop();monkeypatch.setattr(w,'tick',lambda:None)
    kept=tmp_path/'keep.mp4';kept.write_bytes(b'media')
    statuses=['Completed','Failed','Cancelled','Skipped','Paused','Queued','Downloading','Processing']
    w.jobs=[dict(id=status,url='https://example.com/'+status,title=status,status=status,
        progress='',speed='',eta='',files=[str(kept)],settings={'mode':'MP4 video'}) for status in statuses]
    w.running={'Downloading':object(),'Processing':object()}
    w.render()
    def select(title):
        w.populate_selection_menu()
        next(a for a in w.selection_menu.actions() if a.text()==title).trigger()
    def remove(title):
        w.populate_cleanup_menu()
        next(a for a in w.cleanup_menu.actions() if a.text().startswith(title+' (')).trigger()
    try:
        select('Select all');assert len(w.selected())==8
        select('Select none');assert not w.selected()
        select('Select failed / problems');assert [j['id'] for j in w.selected()]==['Failed']
        select('Invert selection');assert len(w.selected())==7
        select('Select active');assert {j['id'] for j in w.selected()}=={'Downloading','Processing'}
        remove('Remove selected');assert len(w.jobs)==8
        select('Select paused')
        remove('Remove completed')
        assert [j['id'] for j in w.selected()]==['Paused']
        assert w.selection_count.text()=='1 selected'
        w.render();assert [j['id'] for j in w.selected()]==['Paused']
        w.retry_failed_button.click()
        assert next(j for j in w.jobs if j['id']=='Failed')['status']=='Queued'
        assert not w.retry_failed_button.isEnabled()
        next(j for j in w.jobs if j['id']=='Failed')['status']='Failed'
        remove('Remove failed / problems')
        assert all(j['status']!='Failed' for j in w.jobs)
        remove('Remove finished')
        assert {j['status'] for j in w.jobs}=={'Paused','Queued','Downloading','Processing'}
        remove('Remove all inactive')
        assert {j['status'] for j in w.jobs}=={'Queued','Downloading','Processing'}
        remove('Remove all except active')
        assert {j['status'] for j in w.jobs}=={'Downloading','Processing'}
        assert kept.read_bytes()==b'media'
        stored=json.loads((tmp_path/'queue.json').read_text())
        assert {j['id'] for j in stored}=={'Downloading','Processing'}
        w.running.clear();remove('Remove all except active')
        assert not w.jobs and not w.cleanup_button.isEnabled() and not w.selection_button.isEnabled()
    finally:
        w.running.clear();w.close();app.processEvents()


def test_missing_tools_do_not_break_gui(tmp_path,monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    import main
    monkeypatch.setattr(main,'DATA',tmp_path)
    app=QApplication.instance() or QApplication([])
    w=main.Window();w.timer.stop()
    def missing(*args,**kwargs):raise OSError('Tool unavailable')
    monkeypatch.setattr(main,'tool',missing)
    try:
        w.links.setPlainText('https://example.com/video')
        w.inspect()
        assert w.analyze_btn.isEnabled() and w.inspector is None
        assert 'Tool unavailable' in w.preview.text()
        w.folder.setText(str(tmp_path/'output'));w.add(True)
        assert w.jobs[-1]['status']=='Failed'
        assert not w.running
    finally:w.close();app.processEvents()
