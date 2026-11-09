import json
import os
import re
import sys
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QUrl, QItemSelection, QItemSelectionModel
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QPlainTextEdit, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QFileDialog, QTabWidget, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QSplitter, QProgressBar, QScrollArea, QLayout, QMenu)
from engine import DATA, ROOT, tool, urls, arguments, save, read, child_environment

STYLE = '''
QWidget { background:#10141f; color:#e7edf7; font-family:"Segoe UI"; font-size:10pt; }
QLabel#eyebrow { color:#6de2c3; font-size:10pt; font-weight:700; }
QLabel#title { font-size:28pt; font-weight:700; }
QLabel#muted { color:#94a3b8; }
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox { background:#191f2e; border:1px solid #303a4d; border-radius:7px; padding:8px; selection-background-color:#38695e; }
QLineEdit,QComboBox,QSpinBox { min-height:22px; }
QComboBox { padding-right:30px; }
QComboBox::drop-down { width:26px; border:0; background:#303e55; border-top-right-radius:6px; border-bottom-right-radius:6px; }
QComboBox::down-arrow { image:url(__ASSETS__/down.svg); width:12px; height:8px; }
QComboBox QAbstractItemView { background:#202b3e; color:#f1f5ff; selection-background-color:#39695e; selection-color:#ffffff; border:1px solid #688097; padding:4px; outline:0; }
QComboBox QAbstractItemView::item { min-height:28px; padding:4px; }
QLineEdit:focus,QComboBox:focus,QSpinBox:focus { border:1px solid #6de2c3; }
QMenu { background:#202b3e; color:#f1f5ff; border:1px solid #597088; padding:6px; }
QMenu::item { padding:9px 24px; border-radius:4px; }
QMenu::item:selected { background:#38695e; }
QMenu::item:disabled { color:#8492a7; }
QMenu::separator { height:1px; background:#44546b; margin:5px; }
QToolTip { background:#263348; color:#ffffff; border:1px solid #688097; padding:5px; }
QScrollArea { border:0; }
QPushButton { background:#222c3e; border:1px solid #354258; border-radius:7px; padding:9px 15px; font-weight:600; }
QPushButton:hover { background:#33435d; border-color:#6de2c3; }
QPushButton#primary { background:#6de2c3; color:#10241f; border:0; }
QPushButton:disabled { color:#637187; background:#1b2230; }
QTabWidget::pane { border:1px solid #303a4d; border-radius:8px; }
QTabBar::tab { padding:11px 23px; background:#191f2e; color:#94a3b8; }
QTabBar::tab:selected { color:#6de2c3; background:#263348; }
QTableWidget { background:#151c2a; alternate-background-color:#1a2333; border:0; gridline-color:#29354a; selection-background-color:#304e59; }
QHeaderView::section { background:#202b3e; color:#a9b9cf; padding:10px; border:0; }
QProgressBar { background:#263348; border:1px solid #3c5065; border-radius:6px; text-align:center; color:#ffffff; font-weight:600; margin:5px; min-height:20px; }
QProgressBar::chunk { background:#25856f; border-radius:5px; }
QCheckBox { spacing:9px; padding:4px; }
QCheckBox::indicator { width:19px; height:19px; border:2px solid #8497b2; border-radius:4px; background:#1b2638; }
QCheckBox::indicator:hover { border-color:#6de2c3; background:#293e50; }
QCheckBox::indicator:checked { background:#6de2c3; border-color:#6de2c3; image:url(__ASSETS__/check.svg); }
QScrollBar:vertical { background:#151c2a; width:12px; } QScrollBar::handle:vertical { background:#37465e; min-height:25px; }
'''.replace('__ASSETS__', (ROOT/'assets').as_posix())

def button(text, action, primary=False):
    b = QPushButton(text)
    b.clicked.connect(action)
    if primary: b.setObjectName('primary')
    return b

def label(text, name=''):
    w = QLabel(text); w.setObjectName(name); w.setWordWrap(True); return w

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('YouTube Downloader Studio')
        self.resize(1220, 890)
        self.jobs = read(DATA / 'queue.json', [])
        for j in self.jobs:
            if j['status'] in ('Downloading', 'Queued', 'Processing'): j['status'] = 'Paused'
        self.running = {}; self.inspector = None; self.inspection_text = ''; self.closing = False
        self.s = read(DATA / 'settings.json', {})
        self.controls = {}
        self.page_scroll=QScrollArea(); self.page_scroll.setWidgetResizable(True); self.setCentralWidget(self.page_scroll)
        root = QWidget(); self.page_scroll.setWidget(root); layout = QVBoxLayout(root)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(22, 18, 22, 18); layout.setSpacing(10)
        layout.addWidget(label('YOUTUBE DOWNLOADER  /  STUDIO', 'eyebrow'))
        layout.addWidget(label('Your media. Your way.', 'title'))
        layout.addWidget(label('Video, audio and playlists — one organized download workspace.', 'muted'))
        self.links = QPlainTextEdit(); self.links.setPlaceholderText('Paste video or playlist links here, one per line…'); self.links.setMaximumHeight(86)
        layout.addWidget(self.links)
        row = QHBoxLayout(); row.addWidget(button('Paste links', self.paste)); self.analyze_btn = button('Inspect video', self.inspect); row.addWidget(self.analyze_btn)
        row.addStretch(); row.addWidget(button('Add to queue', self.add)); row.addWidget(button('Download now', lambda:self.add(True), True)); layout.addLayout(row)
        self.preview = label('Ready when you are. Paste a link to get started.', 'muted'); self.preview.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.preview)
        tabs = QTabWidget(); self.tabs=tabs; layout.addWidget(tabs)
        basic = QWidget(); form = QFormLayout(basic); form.setContentsMargins(18,16,18,16)
        self.combo(form, 'mode', 'Save as', ['MP4 video','MKV video','MP3 audio','M4A audio','FLAC audio','WAV audio'])
        self.combo(form, 'quality', 'Video quality', ['Best available','2160p','1440p','1080p','720p','480p','360p'])
        self.combo(form, 'bitrate', 'Audio bitrate (kbps)', ['192','320','256','128','96'])
        pathrow = QHBoxLayout(); self.folder = QLineEdit(self.s.get('folder', str(Path.home()/'Downloads'/'YouTube'))); pathrow.addWidget(self.folder); pathrow.addWidget(button('Browse…', self.browse)); pathrow.addWidget(button('Open folder', self.open_folder)); form.addRow('Destination', pathrow)
        checks = QHBoxLayout()
        for key,text,default in [('playlist','Download playlist',False),('metadata','Embed metadata and chapters',True),('archive','Skip previously downloaded',False)]: checks.addWidget(self.check(key,text,default))
        form.addRow(checks); self.option_tab(basic,'Download options')
        adv = QWidget(); af = QFormLayout(adv); af.setContentsMargins(18,16,18,16)
        self.spin(af,'parallel','Simultaneous downloads',1,5,2); self.spin(af,'fragments','Parallel fragments',1,16,4)
        self.spin(af,'rate','Speed limit per download (KB/s, 0 = unlimited)',0,1000000,0); self.spin(af,'retries','Retry attempts',0,20,5)
        self.line(af,'items','Playlist items','e.g. 1:10 or 1,3,5'); self.line(af,'proxy','Proxy URL','http://127.0.0.1:8080 or socks5://127.0.0.1:1080')
        self.option_tab(adv,'Network and queue')
        extra = QWidget(); ef = QFormLayout(extra); ef.setContentsMargins(18,16,18,16)
        ef.addRow(self.check('subtitles','Download subtitles')); ef.addRow(self.check('auto_subs','Include automatically generated subtitles'))
        self.line(ef,'languages','Subtitle languages','en.*,fa.*'); ef.addRow(self.check('thumbnail','Save thumbnail image'))
        self.combo(ef,'browser','Use browser cookies (optional)',['None','Firefox','Chrome','Edge','Brave'])
        cr = QHBoxLayout(); self.cookies = QLineEdit(); self.cookies.setPlaceholderText('Optional Netscape cookies.txt file (takes priority over browser)'); cr.addWidget(self.cookies); cr.addWidget(button('Choose file…',self.choose_cookies)); ef.addRow('Cookies file',cr)
        ef.addRow(label('Cookies are only read when explicitly selected. Windows browser encryption can prevent cookie access.', 'muted'))
        self.option_tab(extra,'Subtitles and sign-in')
        tabs.setMinimumHeight(280); tabs.setMaximumHeight(360)
        actions = QHBoxLayout(); self.summary = label('DOWNLOAD QUEUE', 'eyebrow'); actions.addWidget(self.summary); actions.addStretch()
        for text,fn in [('Start / resume',self.resume),('Pause',self.pause),('Cancel',self.cancel),('Clear finished',self.clear)]: actions.addWidget(button(text,fn))
        layout.addLayout(actions)
        bulk = QHBoxLayout()
        self.selection_button = QPushButton('Select')
        self.selection_menu = QMenu(self)
        self.selection_button.setMenu(self.selection_menu)
        self.selection_menu.aboutToShow.connect(self.populate_selection_menu)
        bulk.addWidget(self.selection_button)
        self.cleanup_button = QPushButton('Remove from queue')
        self.cleanup_button.setToolTip('Remove queue entries only; downloaded and partial files are kept. Active downloads are kept.')
        self.cleanup_menu = QMenu(self)
        self.cleanup_button.setMenu(self.cleanup_menu)
        self.cleanup_menu.aboutToShow.connect(self.populate_cleanup_menu)
        bulk.addWidget(self.cleanup_button)
        self.retry_failed_button = button('Retry failed', self.retry_failed)
        bulk.addWidget(self.retry_failed_button)
        self.selection_count = label('0 selected', 'muted')
        bulk.addWidget(self.selection_count); bulk.addStretch()
        bulk.addWidget(label('Removal keeps files. Active downloads are kept.', 'muted'))
        layout.addLayout(bulk)
        self.table = QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['Title / URL','Status','Progress','Speed','ETA','Format'])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for i in range(1,6): self.table.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2,190)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().hide(); self.table.setMinimumHeight(160)
        self.table.doubleClicked.connect(self.open_selected); layout.addWidget(self.table,1)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_job_menu)
        self.table.itemSelectionChanged.connect(self.update_bulk_actions)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(1500); self.log.setMaximumHeight(110); self.log.setPlaceholderText('Activity and troubleshooting details appear here.'); layout.addWidget(self.log)
        foot = QHBoxLayout(); foot.addWidget(label('Pause keeps partial files. Double-click a finished item to open it.', 'muted')); foot.addStretch(); foot.addWidget(button('Licenses', self.show_licenses)); foot.addWidget(button('Export log', self.export_log)); foot.addWidget(button('Update engine',self.update_engine)); layout.addLayout(foot)
        self.render(); self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(500)

    def option_tab(self,page,title):
        page.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        page.layout().setVerticalSpacing(10)
        page.layout().setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page)
        self.tabs.addTab(scroll,title)

    def combo(self,form,key,title,values):
        w=QComboBox(); w.addItems(values); w.setCurrentText(str(self.s.get(key,values[0]))); self.controls[key]=w; form.addRow(title,w)
    def spin(self,form,key,title,low,high,default):
        w=QSpinBox(); w.setRange(low,high); w.setValue(self.s.get(key,default)); self.controls[key]=w; form.addRow(title,w)
    def line(self,form,key,title,hint):
        w=QLineEdit(self.s.get(key,'')); w.setPlaceholderText(hint); self.controls[key]=w; form.addRow(title,w)
    def check(self,key,title,default=False):
        w=QCheckBox(title); w.setChecked(self.s.get(key,default)); self.controls[key]=w; return w
    def settings(self):
        s={}
        for k,w in self.controls.items():
            s[k]=w.isChecked() if isinstance(w,QCheckBox) else w.value() if isinstance(w,QSpinBox) else w.currentText() if isinstance(w,QComboBox) else w.text().strip()
        s['folder']=self.folder.text().strip(); s['cookies']=self.cookies.text().strip()
        return s
    def persist(self):
        s=self.settings(); s.pop('cookies',None); s.pop('proxy',None)
        save(DATA/'settings.json',s)
        # Do not persist credentials or cookie file selections in the queue.
        jobs=json.loads(json.dumps(self.jobs))
        for j in jobs:
            j['settings'].pop('proxy',None); j['settings'].pop('cookies',None); j['settings']['browser']='None'
        save(DATA/'queue.json',jobs)
    def paste(self): self.links.setPlainText(QApplication.clipboard().text())
    def browse(self):
        p=QFileDialog.getExistingDirectory(self,'Download destination',self.folder.text())
        if p:self.folder.setText(p)
    def choose_cookies(self):
        p,_=QFileDialog.getOpenFileName(self,'Choose Netscape cookies file','','Text files (*.txt);;All files (*)')
        if p:self.cookies.setText(p)
    def open_folder(self):
        p=Path(self.folder.text()); p.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
    def note(self,text):
        # Avoid printing proxy credentials, cookies, or signed media URLs into logs.
        text=re.sub(r'https?://\S+', '[URL]',text)
        self.log.appendPlainText(datetime.now().strftime('%H:%M:%S')+'  '+text)
    def selected(self): return [self.jobs[i.row()] for i in self.table.selectionModel().selectedRows() if i.row()<len(self.jobs)]

    def update_bulk_actions(self):
        self.selection_count.setText(f'{len(self.selected())} selected')
        self.selection_button.setEnabled(bool(self.jobs))
        self.cleanup_button.setEnabled(any(j['id'] not in self.running for j in self.jobs))
        self.retry_failed_button.setEnabled(any(j['status']=='Failed' and j['id'] not in self.running for j in self.jobs))

    def select_jobs(self, predicate):
        selection = QItemSelection()
        for row, job in enumerate(self.jobs):
            if predicate(job):
                selection.select(self.table.model().index(row,0), self.table.model().index(row,self.table.columnCount()-1))
        self.table.selectionModel().select(selection,QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def invert_selection(self):
        selected = {j['id'] for j in self.selected()}
        self.select_jobs(lambda j:j['id'] not in selected)

    def populate_selection_menu(self):
        menu=self.selection_menu; menu.clear()
        menu.addAction('Select all', self.table.selectAll)
        menu.addAction('Select none', self.table.clearSelection)
        menu.addAction('Invert selection', self.invert_selection)
        menu.addSeparator()
        for title,statuses in [('Completed',('Completed',)),('Failed / problems',('Failed',)),
                ('Active',('Downloading','Processing')),('Queued',('Queued',)),
                ('Paused',('Paused',)),('Cancelled',('Cancelled',)),('Skipped',('Skipped',))]:
            action=menu.addAction('Select '+title.lower())
            action.setEnabled(any(j['status'] in statuses for j in self.jobs))
            action.triggered.connect(lambda checked=False, states=statuses:self.select_jobs(lambda j:j['status'] in states))

    def populate_cleanup_menu(self):
        menu=self.cleanup_menu; menu.clear()
        groups=[('Remove selected', self.selected()),
                ('Remove completed', [j for j in self.jobs if j['status']=='Completed']),
                ('Remove failed / problems', [j for j in self.jobs if j['status']=='Failed']),
                ('Remove cancelled', [j for j in self.jobs if j['status']=='Cancelled']),
                ('Remove skipped', [j for j in self.jobs if j['status']=='Skipped']),
                ('Remove finished', [j for j in self.jobs if j['status'] in ('Completed','Cancelled','Skipped')]),
                ('Remove all inactive', [j for j in self.jobs if j['status'] not in ('Queued','Downloading','Processing')]),
                ('Remove all except active', self.jobs[:])]
        for title,jobs in groups:
            eligible=[j for j in jobs if j['id'] not in self.running]
            action=menu.addAction(f'{title} ({len(eligible)})')
            action.setEnabled(bool(eligible))
            action.triggered.connect(lambda checked=False, targets=eligible:self.remove_jobs(targets))

    def retry_failed(self):
        self.resume([j for j in self.jobs if j['status']=='Failed' and j['id'] not in self.running])
    def add(self,start=False):
        try:
            links=urls(self.links.toPlainText()); s=self.settings()
            if not links:raise ValueError('Paste at least one video link.')
            if not s['folder']:raise ValueError('Choose a destination folder.')
            Path(s['folder']).mkdir(parents=True,exist_ok=True)
            if s['items'] and not re.fullmatch(r'[0-9,:\- ]+',s['items']):raise ValueError('Playlist items must be numbers or ranges, such as 1:10.')
            for url in links:self.jobs.append(dict(id=uuid.uuid4().hex,url=url,title=url,status='Queued' if start else 'Paused',progress='',speed='',eta='',files=[],settings=s.copy()))
            self.links.clear(); self.persist(); self.render(); self.tick()
        except (ValueError,OSError) as e: QMessageBox.warning(self,'Check download options',str(e))
    def process(self):
        program=tool('yt-dlp')
        p=QProcess(self); environment=QProcessEnvironment.systemEnvironment(); environment.insert('PYINSTALLER_RESET_ENVIRONMENT','1'); p.setProcessEnvironment(environment); p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels); p.setProgram(program); return p
    def inspect(self):
        try:
            links=urls(self.links.toPlainText())
            if not links:raise ValueError('Paste a video link first.')
        except ValueError as e:QMessageBox.warning(self,'Inspect video',str(e)); return
        self.analyze_btn.setEnabled(False); self.preview.setText('Inspecting video…'); self.inspection_text=''
        try:
            args=arguments(links[0],self.settings(),True); p=self.process()
        except OSError as e:
            self.preview.setText(str(e)); self.note(str(e)); self.analyze_btn.setEnabled(True); return
        self.inspector=p; p.setArguments(args)
        p.readyReadStandardOutput.connect(lambda:self.inspect_read(p)); p.finished.connect(lambda code,status:self.inspect_done(p,code)); p.errorOccurred.connect(lambda e:self.inspect_error(p)); p.start()
    def inspect_read(self,p): self.inspection_text+=bytes(p.readAllStandardOutput()).decode('utf-8','replace')
    def inspect_error(self,p):
        if p.error()==QProcess.ProcessError.FailedToStart:
            self.preview.setText('Download engine could not start. Restart the app to repair its tools; check security-software quarantine if this persists.'); self.analyze_btn.setEnabled(True); self.inspector=None
    def inspect_done(self,p,code):
        self.inspect_read(p); self.analyze_btn.setEnabled(True); self.inspector=None
        try:
            data=next(json.loads(line) for line in self.inspection_text.splitlines() if line.startswith('{'))
            heights=sorted({f['height'] for f in data.get('formats',[]) if f.get('height')})
            duration=int(data.get('duration') or 0)
            self.preview.setText(f"{data.get('title','Untitled')}  •  {data.get('uploader','')}  •  {duration//60}:{duration%60:02d}  •  Available: "+', '.join(f'{h}p' for h in heights))
        except (StopIteration,ValueError): self.preview.setText('Inspection failed. See the activity log for details.'); self.note(self.inspection_text[-3500:])
        p.deleteLater()
    def tick(self):
        if self.closing:return
        limit=self.controls['parallel'].value()
        for j in self.jobs:
            if len(self.running)>=limit:break
            if j['status']=='Queued':self.start(j)
    def start(self,j):
        try:
            args=arguments(j['url'],j['settings']); p=self.process()
        except OSError as e:
            j.update(status='Failed', error=str(e), progress='Failed'); self.note(str(e)); self.persist(); self.render(); return
        j['status']='Downloading'; j['speed']=''; j['eta']=''; j['buffer']=''; j['error']=''; j['stop']=''
        j['skipped']=False; j['transferred']=False
        self.running[j['id']]=p
        j['progress']='Connecting…'
        p.setArguments(args)
        p.readyReadStandardOutput.connect(lambda:self.consume(j,p))
        p.finished.connect(lambda code,status:self.done(j,p,code))
        p.errorOccurred.connect(lambda e:self.process_error(j,p))
        p.start(); self.render()
    def process_error(self,j,p):
        if p.error()==QProcess.ProcessError.FailedToStart:
            j['error']='Engine failed to start. Restart the app to repair its tools; check security-software quarantine if this persists.'; self.done(j,p,1)
    def consume(self,j,p):
        j['buffer']+=bytes(p.readAllStandardOutput()).decode('utf-8','replace')
        lines=j['buffer'].split('\n'); j['buffer']=lines.pop()
        for line in lines:
            line=line.strip()
            if line.startswith('PROGRESS|'):
                parts=line.split('|'); j['progress'],j['speed'],j['eta']=(parts+['','',''])[1:4]
            elif line.startswith('TITLE|'): j['title']=line[6:]; j['progress']='Starting…'
            elif line.startswith('FILE|'):
                path=line[5:]
                if path not in j['files']:j['files'].append(path)
            else:
                if '[download] Destination:' in line:j['transferred']=True
                if 'has already been downloaded' in line or 'has already been recorded in the archive' in line:
                    j['skipped']=True
                if 'ERROR:' in line:j['error']=line
                if line:self.note(line)
        self.render()
    def done(self,j,p,code):
        if j['id'] not in self.running:return
        self.consume(j,p); self.running.pop(j['id'],None)
        j['status']=j.get('stop') or (('Skipped' if j.get('skipped') and not j.get('transferred') else 'Completed') if code==0 else 'Failed')
        j['speed']=''; j['eta']=''
        if j['status']=='Completed':j['progress']='100%'
        elif j['status']=='Skipped':j['progress']=''; self.note('Skipped: this download profile already exists or is recorded in its archive.')
        if j['status']=='Failed':self.note(j.get('error') or f'Download exited with code {code}. Check network, cookies and engine updates.')
        j.pop('buffer',None); j.pop('stop',None); self.persist(); self.render(); p.deleteLater()
    def resume(self,jobs=None):
        for j in jobs if isinstance(jobs,list) else self.selected() or self.jobs:
            if j['status'] in ('Paused','Failed','Cancelled'):
                # Refresh transient connection settings only; preserve format and destination.
                current=self.settings()
                for key in ('proxy','cookies','browser'):j['settings'][key]=current[key]
                j['status']='Queued'
        self.persist(); self.render(); self.tick()
    def stop_jobs(self,status,jobs=None):
        for j in jobs if isinstance(jobs,list) else self.selected() or self.jobs:
            if j['id'] in self.running:
                j['stop']=status; self.stop_process(self.running[j['id']])
            elif j['status'] in ('Queued','Paused','Failed'):j['status']=status
        self.persist(); self.render()
    def pause(self):self.stop_jobs('Paused')
    def cancel(self):self.stop_jobs('Cancelled')
    def stop_process(self,p):
        # Stop FFmpeg/runtime descendants as well as the downloader itself.
        pid=int(p.processId())
        if pid and os.name=='nt':
            subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        elif pid:p.kill()
    def clear(self):
        self.remove_jobs([j for j in self.jobs if j['status'] in ('Completed','Cancelled','Skipped')])
    def render(self):
        self.table.setRowCount(len(self.jobs))
        for row,j in enumerate(self.jobs):
            for col,value in enumerate([j['title'],j['status'],j['progress'],j['speed'],j['eta'],j['settings']['mode']]):
                if col==2:
                    bar=self.table.cellWidget(row,col)
                    if not isinstance(bar,QProgressBar):
                        bar=QProgressBar(); bar.setTextVisible(True)
                        bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                        bar.setAccessibleName('Download progress')
                        self.table.setCellWidget(row,col,bar)
                    match=re.search(r'(\d+(?:\.\d+)?)\s*%',str(j['progress']))
                    active=j['status'] in ('Downloading','Processing')
                    if active and not match:
                        bar.setRange(0,0); bar.setFormat('Connecting…')
                    else:
                        bar.setRange(0,1000)
                        percent=100.0 if j['status']=='Completed' else min(100.0,float(match.group(1))) if match else 0.0
                        bar.setValue(round(percent*10))
                        bar.setFormat('Finalizing…' if active and percent>=100 else f'{percent:.1f}%' if active or j['status']=='Completed' else f"{j['status']} · {percent:.1f}%" if match else j['status'])
                    bar.setToolTip('Progress of the current media stream; video and audio may download separately.')
                    continue
                item=self.table.item(row,col)
                if item is None:item=QTableWidgetItem(); self.table.setItem(row,col,item)
                item.setText(str(value)); item.setToolTip(j.get('error') or j['url'])
                if col==1:item.setForeground(QColor('#6de2c3' if j['status']=='Completed' else '#ff9e9e' if j['status']=='Failed' else '#a9b9cf'))
        self.summary.setText(f"DOWNLOAD QUEUE  /  {len(self.jobs)} items  /  {len(self.running)} active")
        self.update_bulk_actions()
    def show_job_menu(self,pos):
        row=self.table.indexAt(pos).row()
        if row<0:return
        if row not in [i.row() for i in self.table.selectionModel().selectedRows()]:
            self.table.selectRow(row)
        menu=self.job_menu(self.selected())
        menu.exec(self.table.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def job_menu(self,jobs):
        menu=QMenu(self)
        def action(title,callback,enabled=True):
            a=menu.addAction(title); a.setEnabled(enabled)
            a.triggered.connect(lambda checked=False:callback())
        action('Start / resume / retry',lambda:self.resume(jobs),any(j['status'] in ('Paused','Failed','Cancelled') for j in jobs))
        action('Pause download',lambda:self.stop_jobs('Paused',jobs),any(j['status'] in ('Queued','Downloading','Processing') for j in jobs))
        action('Cancel download',lambda:self.stop_jobs('Cancelled',jobs),any(j['status'] in ('Queued','Paused','Downloading','Processing','Failed') for j in jobs))
        menu.addSeparator()
        action('Download with different options…',lambda:self.prepare_again(jobs))
        action('Open downloaded file',lambda:self.open_job_files(jobs),any(any(Path(f).is_file() for f in j['files']) for j in jobs))
        action('Open download folder',lambda:self.open_job_folders(jobs))
        action('Open source in browser',lambda:[QDesktopServices.openUrl(QUrl(j['url'])) for j in jobs])
        action('Copy video link',lambda:QApplication.clipboard().setText('\n'.join(j['url'] for j in jobs)))
        action('Download details…',lambda:self.job_details(jobs))
        menu.addSeparator()
        action('Remove from queue (keep files)',lambda:self.remove_jobs(jobs),all(j['id'] not in self.running for j in jobs))
        return menu

    def prepare_again(self,jobs):
        self.links.setPlainText('\n'.join(j['url'] for j in jobs)); self.tabs.setCurrentIndex(0)
        self.page_scroll.verticalScrollBar().setValue(0)
        self.preview.setText('Choose the new quality or format, then click Download now.')
        self.links.setFocus()

    def open_job_files(self,jobs):
        for j in jobs:
            files=[f for f in j['files'] if Path(f).is_file()]
            if files:QDesktopServices.openUrl(QUrl.fromLocalFile(files[-1]))

    def open_job_folders(self,jobs):
        for folder in dict.fromkeys(j['settings']['folder'] for j in jobs):
            path=Path(folder)
            if path.is_dir():QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def job_details(self,jobs):
        details=[]
        for j in jobs:
            s=j['settings']
            details.append(f"{j['title']}\nStatus: {j['status']}\nURL: {j['url']}\nFormat: {s['mode']}\nQuality: {s.get('quality','Best available')}\nDestination: {s['folder']}\nFiles: "+('\n'.join(j['files']) or 'No output recorded')+'\n'+j.get('error',''))
        box=QMessageBox(self); box.setWindowTitle('Download details'); box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText('\n\n'.join(details)); box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); box.exec()

    def remove_jobs(self,jobs):
        ids={j['id'] for j in jobs if j['id'] not in self.running}
        selected={j['id'] for j in self.selected()}-ids
        self.table.clearSelection()
        self.jobs=[j for j in self.jobs if j['id'] not in ids]
        self.persist(); self.render()
        self.select_jobs(lambda j:j['id'] in selected)

    def open_selected(self):
        for j in self.selected():
            if j['files'] and Path(j['files'][-1]).is_file():QDesktopServices.openUrl(QUrl.fromLocalFile(j['files'][-1]))
    def export_log(self):
        p,_=QFileDialog.getSaveFileName(self,'Export activity log','download-log.txt','Text (*.txt)')
        if p:Path(p).write_text(self.log.toPlainText(),encoding='utf-8')
    def show_licenses(self):
        source=ROOT/'THIRD_PARTY_NOTICES.txt'
        box=QMessageBox(self); box.setWindowTitle('Third-party licenses'); box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(source.read_text(encoding='utf-8') if source.exists() else 'See THIRD_PARTY_NOTICES.txt beside the application.')
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); box.exec()
    def update_engine(self):
        if self.running or self.inspector:QMessageBox.information(self,'Update engine','Pause downloads and wait for inspection to finish first.'); return
        if getattr(self,'updater',None):return
        try:
            p=self.process()
        except OSError as e:
            QMessageBox.warning(self,'Update engine',str(e)); return
        self.updater=p; p.setArguments(['--update'])
        p.readyReadStandardOutput.connect(lambda:self.note(bytes(p.readAllStandardOutput()).decode('utf-8','replace')))
        def finish(code,status=None):
            if self.updater is not p:return
            # Mark an explicit successful upstream update as trusted for this installation.
            if code==0:
                target=Path(p.program()); stat=target.stat()
                target.with_name(target.name+'.verified').write_text(f'{stat.st_size}:{stat.st_mtime_ns}')
            self.note('Engine update finished.' if code==0 else 'Engine update failed. See details above.'); self.updater=None; p.deleteLater()
        p.errorOccurred.connect(lambda error:finish(1) if error==QProcess.ProcessError.FailedToStart else None)
        p.finished.connect(finish); p.start(); self.note('Checking the official yt-dlp release for updates...')
    def closeEvent(self,event):
        self.closing=True; self.timer.stop()
        for j in self.jobs:
            if j['id'] in self.running:
                j['stop']='Paused'; p=self.running[j['id']]; self.stop_process(p); p.waitForFinished(3000)
        for p in [self.inspector,getattr(self,'updater',None)]:
            if p:self.stop_process(p); p.waitForFinished(3000)
        self.persist(); event.accept()

def main():
    if '--verify-bundle' in sys.argv:
        import tempfile
        report={}
        try:
            for name,flag in [('yt-dlp','--version'),('deno','--version'),('ffmpeg','-version'),('ffprobe','-version')]:
                result=subprocess.run([tool(name),flag],capture_output=True,text=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                report[name]=result.stdout.splitlines()[0]
            with tempfile.TemporaryDirectory() as directory:
                video=str(Path(directory)/'check.mp4')
                subprocess.run([tool('ffmpeg'),'-v','error','-f','lavfi','-i','color=size=320x180:rate=5','-t','1','-c:v','libx264',video],capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                result=subprocess.run([tool('ffprobe'),'-v','error','-show_entries','stream=width,height','-of','json',video],capture_output=True,text=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                report['media_check']=json.loads(result.stdout)
                import functools
                import http.server
                import threading
                class QuietHandler(http.server.SimpleHTTPRequestHandler):
                    def log_message(self,*args):pass
                handler=functools.partial(QuietHandler,directory=directory)
                server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
                threading.Thread(target=server.serve_forever,daemon=True).start()
                try:
                    url=f'http://127.0.0.1:{server.server_port}/check.mp4'
                    result=subprocess.run([tool('yt-dlp'),*arguments(url,{},True)],capture_output=True,text=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                    report['inspection']=json.loads(result.stdout)['id']
                    result=subprocess.run([tool('yt-dlp'),*arguments(url,{'folder':str(Path(directory)/'downloads'),'mode':'MP4 video'})],capture_output=True,text=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                    assert list((Path(directory)/'downloads').glob('*.mp4'))
                    report['download_check']=True
                finally:
                    server.shutdown();server.server_close()

            assert (ROOT/'assets/check.svg').is_file()
            assert (ROOT/'THIRD_PARTY_NOTICES.txt').is_file()
            report['success']=True
        except Exception as e:report.update(success=False,error=str(e))
        save(DATA/'bundle-verification.json',report)
        sys.exit(0 if report['success'] else 1)
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    icon=ROOT/'app.ico'
    if icon.exists():app.setWindowIcon(QIcon(str(icon)))
    w=Window(); w.show()
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(1200, lambda:w.grab().save(str(DATA/'smoke-test.png')))
        QTimer.singleShot(1600,w.close)
    sys.exit(app.exec())

if __name__=='__main__':main()
