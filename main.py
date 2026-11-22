import ctypes
import json
import os
import re
import sys
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import (Qt, QProcess, QProcessEnvironment, QTimer, QUrl,
    QItemSelection, QItemSelectionModel, QPropertyAnimation, QEasingCurve)
from PySide6.QtGui import (QDesktopServices, QFont, QIcon, QPixmap, QPainter,
    QColor, QShortcut, QKeySequence)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QPlainTextEdit, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QFileDialog, QTabWidget, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QSplitter, QProgressBar, QScrollArea, QLayout, QMenu,
    QDialog, QFrame, QToolButton, QSizePolicy)
from engine import DATA, ROOT, tool, urls, arguments, save, read, child_environment
from system_check import check_runtime, summary as system_check_summary

# The standalone build carries an auditable source snapshot and writes reports
# to per-user application data, never into PyInstaller's temporary extraction.
FROZEN = bool(getattr(sys, 'frozen', False))
os.environ.setdefault('YDS_AUDIT_ROOT', str(ROOT / 'audit_sources' if FROZEN else ROOT))
os.environ.setdefault('YDS_REPORT_DIR', str(DATA / 'reports' if FROZEN else ROOT / 'reports'))
from project_orchestrator import run as run_multi_agent_audit

STYLE = '''
QMainWindow#mainWindow { background:#0A1020; }
QWidget { background:transparent; color:#EDF3FC; font-family:"Segoe UI"; font-size:10pt; }
QWidget#appRoot { background:transparent; }
QLabel#eyebrow { color:#75E6CA; font-size:9pt; font-weight:800; letter-spacing:1px; }
QLabel#title { color:#F6F8FD; font-size:27pt; font-weight:750; }
QLabel#brandTitle { color:#F5F8FE; font-size:15pt; font-weight:750; }
QLabel#brandSubtitle { color:#8EA3BE; font-size:9pt; }
QLabel#sectionTitle { color:#F0F5FD; font-size:13pt; font-weight:700; }
QLabel#muted { color:#91A4BD; }
QLabel#softText { color:#B3C2D6; }
QFrame#topBar { background:rgba(28,42,65,0.82); border:1px solid rgba(205,225,255,0.15); border-radius:18px; }
QFrame#glassCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(35,53,79,0.91),stop:0.52 rgba(22,35,57,0.94),stop:1 rgba(18,29,48,0.92)); border:1px solid rgba(206,226,255,0.16); border-top:1px solid rgba(245,250,255,0.24); border-radius:18px; }
QFrame#glassPanel { background:rgba(14,24,42,0.72); border:1px solid rgba(194,218,250,0.12); border-radius:14px; }
QFrame#queueCard { background:rgba(18,30,49,0.88); border:1px solid rgba(190,214,246,0.15); border-radius:17px; }
QFrame#brandMark { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #83F0D4,stop:1 #3A9CBA); border:1px solid rgba(255,255,255,0.35); border-radius:14px; }
QLabel#brandMarkText { color:#0A1A24; font-size:14pt; font-weight:900; }
QLabel#statusPill { color:#7FE7C9; background:rgba(42,175,137,0.15); border:1px solid rgba(103,228,192,0.28); border-radius:11px; padding:7px 12px; font-weight:700; }
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox { background:rgba(8,16,30,0.74); color:#F1F5FC; border:1px solid rgba(177,203,237,0.20); border-radius:10px; padding:9px 11px; selection-background-color:#2C8E82; min-height:23px; }
QPlainTextEdit#urlInput { background:rgba(7,15,29,0.82); border:1px solid rgba(177,213,246,0.22); border-radius:13px; padding:13px; font-size:11pt; }
QLineEdit:hover,QPlainTextEdit:hover,QComboBox:hover,QSpinBox:hover { border-color:rgba(125,224,205,0.48); }
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus,QSpinBox:focus { border:1px solid #72E4CA; background:rgba(11,26,43,0.96); }
QComboBox { padding-right:32px; }
QComboBox::drop-down { width:28px; border:0; background:rgba(102,142,174,0.18); border-top-right-radius:9px; border-bottom-right-radius:9px; }
QComboBox::down-arrow { image:url(__ASSETS__/down.svg); width:12px; height:8px; }
QComboBox QAbstractItemView { background:#17263D; color:#F1F5FC; selection-background-color:#286B67; selection-color:#FFFFFF; border:1px solid #49627F; padding:6px; outline:0; }
QComboBox QAbstractItemView::item { min-height:30px; padding:6px; }
QMenu { background:#17263D; color:#F1F5FC; border:1px solid #49627F; padding:7px; }
QMenu::item { padding:10px 24px; border-radius:7px; }
QMenu::item:selected { background:#285C60; }
QMenu::item:disabled { color:#71859E; }
QMenu::separator { height:1px; background:#3A506B; margin:6px; }
QToolTip { background:#21354F; color:#FFFFFF; border:1px solid #66809D; padding:7px 9px; border-radius:7px; }
QScrollArea { border:0; background:transparent; }
QPushButton { background:rgba(85,111,145,0.20); color:#EAF2FC; border:1px solid rgba(185,210,243,0.20); border-radius:10px; padding:10px 16px; font-weight:650; }
QPushButton:hover { background:rgba(103,147,178,0.30); border-color:rgba(125,231,209,0.62); }
QPushButton:pressed { background:rgba(48,112,111,0.50); padding-top:11px; padding-bottom:9px; }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #91F0D8,stop:1 #50C6B6); color:#09251F; border:1px solid rgba(225,255,249,0.55); font-weight:800; }
QPushButton#primary:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #B0F9E6,stop:1 #70DDCB); }
QPushButton#quiet { background:transparent; border-color:transparent; color:#AFC1D8; }
QPushButton:disabled { color:#647891; background:rgba(35,49,69,0.55); border-color:rgba(120,145,174,0.10); }
QTabWidget::pane { background:rgba(10,20,36,0.42); border:1px solid rgba(180,208,240,0.13); border-radius:13px; top:-1px; }
QTabBar::tab { padding:12px 18px; margin-right:5px; background:rgba(23,37,58,0.66); color:#91A5BF; border:1px solid rgba(174,202,233,0.10); border-top-left-radius:10px; border-top-right-radius:10px; }
QTabBar::tab:hover { color:#E7F2FC; background:rgba(70,105,130,0.28); }
QTabBar::tab:selected { color:#86EBD0; background:rgba(57,112,111,0.24); border-color:rgba(112,222,201,0.34); }
QTableWidget { background:rgba(9,18,32,0.60); alternate-background-color:rgba(31,47,69,0.50); color:#EAF1FB; border:1px solid rgba(178,204,234,0.13); border-radius:12px; gridline-color:rgba(135,161,194,0.09); selection-background-color:rgba(54,131,124,0.48); outline:0; }
QTableWidget::item { padding:7px; border-bottom:1px solid rgba(150,176,207,0.08); }
QHeaderView::section { background:rgba(39,57,81,0.82); color:#AFC1D8; padding:11px 9px; border:0; border-bottom:1px solid rgba(190,215,245,0.12); font-weight:700; }
QProgressBar { background:rgba(8,17,31,0.86); border:1px solid rgba(161,192,220,0.20); border-radius:7px; text-align:center; color:#FFFFFF; font-size:9pt; font-weight:700; margin:4px; min-height:18px; }
QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4AB9AE,stop:1 #8BE8D2); border-radius:6px; }
QCheckBox { spacing:9px; padding:5px; color:#D5E1F0; }
QCheckBox::indicator { width:18px; height:18px; border:1px solid rgba(171,201,233,0.55); border-radius:5px; background:rgba(9,19,34,0.8); }
QCheckBox::indicator:hover { border-color:#7AE8CE; background:rgba(58,116,114,0.35); }
QCheckBox::indicator:checked { background:#73E2C7; border-color:#73E2C7; image:url(__ASSETS__/check.svg); }
QScrollBar:vertical { background:rgba(9,18,32,0.36); width:10px; margin:2px; border-radius:5px; }
QScrollBar::handle:vertical { background:rgba(125,157,190,0.42); min-height:28px; border-radius:5px; }
QScrollBar::handle:vertical:hover { background:rgba(134,225,206,0.62); }
'''.replace('__ASSETS__', (ROOT/'assets').as_posix())


def apply_native_window_effects(widget):
    """Enable Windows dark title bars, rounded corners and Mica where supported."""
    if sys.platform != 'win32':
        return
    try:
        hwnd = ctypes.c_void_p(int(widget.winId()))
        dwm = ctypes.windll.dwmapi
        dark = ctypes.c_int(1)
        corner = ctypes.c_int(2)  # DWMWCP_ROUND
        mica = ctypes.c_int(2)    # DWMSBT_MAINWINDOW
        for attribute in (20, 19):  # Immersive dark mode (newer / older Windows SDK)
            try:
                result = dwm.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(dark), ctypes.sizeof(dark)
                )
                if result == 0:
                    break
            except Exception:
                continue
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), ctypes.sizeof(corner))
        dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(mica), ctypes.sizeof(mica))
    except Exception:
        pass


def animate_window_entrance(widget, start=0.94, duration=190):
    if QApplication.platformName().lower() == 'offscreen':
        return
    try:
        widget.setWindowOpacity(start)
        animation = QPropertyAnimation(widget, b'windowOpacity', widget)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        widget._entrance_animation = animation
    except Exception:
        pass

def button(text, action, primary=False):
    b = QPushButton(text)
    b.setAccessibleName(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(action)
    if primary:
        b.setObjectName('primary')
    return b

def label(text, name=''):
    w = QLabel(text); w.setObjectName(name); w.setWordWrap(True); return w


class SystemCheckDialog(QDialog):
    """Readable, grouped system-check report styled consistently with the app."""
    COLORS = {
        'ok': ('#27C08A', '#12382F', 'READY', '✓'),
        'warning': ('#E9AE55', '#3B2D18', 'NOTICE', '!'),
        'missing': ('#F16D75', '#421F27', 'ACTION NEEDED', '×'),
    }
    GROUPS = (
        ('System', lambda key: key == 'platform'),
        ('Application runtime', lambda key: key in ('runtime', 'python') or key.startswith('module-')),
        ('Storage and destination', lambda key: key in ('app-storage', 'disk', 'destination')),
        ('Download components', lambda key: key.startswith('tool-')),
        ('Optional integrations', lambda key: key == 'browser'),
    )

    def __init__(self, results, report, parent=None):
        super().__init__(parent)
        self.results = list(results)
        self.report = report
        self.setWindowTitle('System compatibility')
        flags = (self.windowFlags() | Qt.WindowType.WindowTitleHint
                 | Qt.WindowType.WindowSystemMenuHint
                 | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowFlags(flags)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(820, 720)
        self.setMinimumSize(680, 560)
        self.setStyleSheet("""
            QDialog { background:#0C1524; color:#EAF0FA; font-family:"Segoe UI"; font-size:10pt; }
            QLabel { background:transparent; }
            QLabel#dialogTitle { color:#F5F8FD; font-size:22px; font-weight:750; }
            QLabel#dialogSubtitle { color:#A9BBD1; font-size:10pt; }
            QLabel#sectionTitle { color:#CFE0F3; font-size:10pt; font-weight:750; }
            QFrame#hero { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(47,72,102,0.92),stop:1 rgba(21,39,63,0.96)); border:1px solid rgba(207,230,255,0.22); border-top:1px solid rgba(255,255,255,0.30); border-radius:17px; }
            QFrame#metric { background:rgba(34,52,77,0.78); border:1px solid rgba(197,221,249,0.15); border-radius:12px; }
            QLabel#metricValue { color:#F5F8FC; font-size:18px; font-weight:750; }
            QLabel#metricLabel { color:#A4B6CE; font-size:9pt; }
            QFrame#checkRow { background:rgba(20,34,54,0.82); border:1px solid rgba(184,210,240,0.15); border-top:1px solid rgba(235,246,255,0.12); border-radius:12px; }
            QLabel#rowTitle { color:#F0F5FC; font-size:10pt; font-weight:650; }
            QLabel#rowDetail { color:#A7B9D0; font-size:9pt; }
            QLabel#rowBadge { font-size:8pt; font-weight:750; padding:5px 9px; border-radius:8px; }
            QScrollArea { background:transparent; border:0; }
            QScrollBar:vertical { background:rgba(10,20,34,0.3); width:9px; margin:2px; }
            QScrollBar::handle:vertical { background:rgba(130,166,197,0.44); min-height:28px; border-radius:4px; }
            QPushButton { background:rgba(91,122,159,0.23); color:#EAF2FC; border:1px solid rgba(190,218,248,0.20); border-radius:10px; padding:10px 18px; font-weight:650; }
            QPushButton:hover { background:rgba(111,155,187,0.34); border-color:rgba(126,232,210,0.62); }
            QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #91F0D8,stop:1 #50C6B6); color:#09251F; border:1px solid rgba(225,255,249,0.55); }
            QPushButton#primary:hover { background:#B0F9E6; }
            QToolButton#dialogClose { background:rgba(255,255,255,0.07); color:#DDE8F5;
                border:1px solid rgba(210,228,250,0.18); border-radius:10px;
                min-width:34px; min-height:34px; font-size:20px; font-weight:500; }
            QToolButton#dialogClose:hover { background:#C94E5C; color:white; border-color:#E77A84; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        required_missing = [item for item in self.results
                            if item.status == 'missing' and item.required]
        ok_count = sum(item.status == 'ok' for item in self.results)
        warning_count = sum(item.status == 'warning' for item in self.results)
        missing_count = sum(item.status == 'missing' for item in self.results)
        ready = not required_missing
        headline = 'Everything is ready' if ready else 'Some components need attention'
        subtitle = ('Your application passed its required compatibility checks.'
                    if ready else 'Review the items marked Action needed before continuing.')

        hero = QFrame()
        hero.setObjectName('hero')
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 17, 18, 17)
        hero_layout.setSpacing(14)

        symbol = QLabel('✓' if ready else '!')
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol.setFixedSize(48, 48)
        symbol.setStyleSheet(
            f"background:{'#164B3D' if ready else '#50391D'}; color:{'#67E0B8' if ready else '#F6C36E'};"
            "border-radius:24px; font-size:24px; font-weight:800;"
        )
        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        title = QLabel('System compatibility')
        title.setObjectName('dialogTitle')
        message = QLabel(headline)
        message.setStyleSheet(
            f"color:{'#67E0B8' if ready else '#F6C36E'}; font-size:11pt; font-weight:700;"
        )
        description = QLabel(subtitle)
        description.setObjectName('dialogSubtitle')
        description.setWordWrap(True)
        hero_text.addWidget(title)
        hero_text.addWidget(message)
        hero_text.addWidget(description)
        hero_layout.addWidget(symbol, 0, Qt.AlignmentFlag.AlignTop)
        hero_layout.addLayout(hero_text, 1)
        self.window_close_button = QToolButton()
        self.window_close_button.setText('×')
        self.window_close_button.setObjectName('dialogClose')
        self.window_close_button.setToolTip('Close this window')
        self.window_close_button.setAccessibleName('Close system compatibility window')
        self.window_close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.window_close_button.clicked.connect(self.reject)
        hero_layout.addWidget(self.window_close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.close_shortcut = QShortcut(QKeySequence('Escape'), self)
        self.close_shortcut.activated.connect(self.reject)
        root.addWidget(hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(9)
        for value, caption, color in (
            (ok_count, 'Ready', '#67E0B8'),
            (warning_count, 'Notices', '#F6C36E'),
            (missing_count, 'Missing', '#F58B91'),
        ):
            tile = QFrame()
            tile.setObjectName('metric')
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(13, 9, 13, 9)
            tile_layout.setSpacing(1)
            number = QLabel(str(value))
            number.setObjectName('metricValue')
            number.setStyleSheet(f'color:{color};')
            caption_label = QLabel(caption)
            caption_label.setObjectName('metricLabel')
            tile_layout.addWidget(number)
            tile_layout.addWidget(caption_label)
            metrics.addWidget(tile, 1)
        root.addLayout(metrics)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setStyleSheet('background:transparent;')
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(1, 2, 5, 2)
        content_layout.setSpacing(11)

        remaining = list(self.results)
        for group_name, matcher in self.GROUPS:
            group_items = [item for item in remaining if matcher(item.key)]
            if not group_items:
                continue
            remaining = [item for item in remaining if not matcher(item.key)]
            heading = QLabel(group_name)
            heading.setObjectName('sectionTitle')
            content_layout.addWidget(heading)
            for item in group_items:
                content_layout.addWidget(self._row(item))
        if remaining:
            heading = QLabel('Other checks')
            heading.setObjectName('sectionTitle')
            content_layout.addWidget(heading)
            for item in remaining:
                content_layout.addWidget(self._row(item))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addWidget(QLabel('Checked locally · No software was installed'))
        footer.addStretch(1)
        copy_button = QPushButton('Copy details')
        copy_button.clicked.connect(self.copy_details)
        close_button = QPushButton('Close')
        close_button.setObjectName('primary')
        close_button.clicked.connect(self.accept)
        footer.addWidget(copy_button)
        footer.addWidget(close_button)
        root.addLayout(footer)

    def _row(self, item):
        color, background, badge_text, symbol = self.COLORS.get(
            item.status, ('#91A2B9', '#26364D', 'INFO', '•')
        )
        card = QFrame()
        card.setObjectName('checkRow')
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(11)

        icon = QLabel(symbol)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(30, 30)
        icon.setStyleSheet(
            f'background:{background}; color:{color}; border-radius:15px;'
            'font-size:15px; font-weight:800;'
        )

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        title = QLabel(item.title)
        title.setObjectName('rowTitle')
        detail_text = str(item.detail).replace('\\n', '\n')
        detail = QLabel(detail_text)
        detail.setObjectName('rowDetail')
        detail.setTextFormat(Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_layout.addWidget(title)
        text_layout.addWidget(detail)

        badge = QLabel(badge_text)
        badge.setObjectName('rowBadge')
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f'background:{background}; color:{color};')
        badge.setMinimumWidth(82)

        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_layout, 1)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        return card

    def copy_details(self):
        lines = ['System compatibility report',
                 'All required components are ready.' if self.report['ready']
                 else 'Some required components need attention.', '']
        for item in self.results:
            lines.append(f'[{item.status.upper()}] {item.title}: {item.detail}')
        QApplication.clipboard().setText('\n'.join(lines))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: apply_native_window_effects(self))
        animate_window_entrance(self, start=0.92, duration=210)

    # On close, persist resumable state and release resources cleanly.
    def closeEvent(self, event):
        event.accept()
        self.done(QDialog.DialogCode.Rejected)


class Window(QMainWindow):
    """Own the download queue, progressive workspaces and subprocess lifecycle.

    QProcess signals update the UI on the Qt event loop. Persistent settings
    and queues are restored after crashes, while active jobs restart paused.
    """
    def __init__(self):
        super().__init__()
        self.setObjectName('mainWindow')
        self.setWindowTitle('YouTube Downloader Studio')
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowCloseButtonHint
                            | Qt.WindowType.WindowSystemMenuHint
                            | Qt.WindowType.WindowMinMaxButtonsHint)
        self.resize(1320, 980)
        self.setMinimumSize(860, 640)
        self.jobs = read(DATA / 'queue.json', [])
        for job in self.jobs:
            if job['status'] in ('Downloading', 'Queued', 'Processing'):
                job['status'] = 'Paused'
        self.running = {}
        self.inspector = None
        self.audit_process = None
        self.inspection_text = ''
        self.closing = False
        self.s = read(DATA / 'settings.json', {})
        self.controls = {}
        self._row_cache = {}
        self._dirty_job_ids = set()
        self._full_render_pending = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(75)
        self._render_timer.timeout.connect(self.flush_render)

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(self.page_scroll)
        root = QWidget()
        root.setObjectName('appRoot')
        self.page_scroll.setWidget(root)
        layout = QVBoxLayout(root)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(16)

        # Product header: progressive-disclosure level and performance presets.
        topbar = QFrame()
        topbar.setObjectName('topBar')
        top = QHBoxLayout(topbar)
        top.setContentsMargins(16, 13, 16, 13)
        top.setSpacing(14)
        mark = QFrame()
        mark.setObjectName('brandMark')
        mark.setFixedSize(48, 48)
        mark_layout = QVBoxLayout(mark)
        mark_layout.setContentsMargins(0, 0, 0, 0)
        mark_text = label('YD', 'brandMarkText')
        mark_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark_layout.addWidget(mark_text)
        top.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label('YouTube Downloader Studio', 'brandTitle'))
        brand.addWidget(label('A faster, more capable media workspace', 'brandSubtitle'))
        top.addLayout(brand, 1)
        self.status_label = label('●  Ready', 'statusPill')
        self.status_label.setWordWrap(False)
        self.status_label.setMinimumWidth(100)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.status_label)

        workspace = QVBoxLayout()
        workspace.setSpacing(4)
        workspace.addWidget(label('WORKSPACE', 'eyebrow'))
        self.experience_combo = QComboBox()
        self.experience_combo.addItems(['Simple', 'Advanced', 'Professional'])
        self.experience_combo.setCurrentText(self.s.get('experience_level', 'Simple'))
        self.experience_combo.setMinimumWidth(132)
        self.experience_combo.setAccessibleName('Workspace experience level')
        self.experience_combo.setToolTip('Simple shows essential choices. Advanced adds controls. Professional reveals expert yt-dlp options.')
        workspace.addWidget(self.experience_combo)
        top.addLayout(workspace)

        preset = QVBoxLayout()
        preset.setSpacing(4)
        preset.addWidget(label('PERFORMANCE', 'eyebrow'))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(['Balanced', 'Maximum speed', 'Maximum reliability', 'Data saver'])
        self.preset_combo.setCurrentText(self.s.get('performance_preset', 'Balanced'))
        self.preset_combo.setMinimumWidth(176)
        self.preset_combo.setAccessibleName('Performance preset')
        self.preset_combo.setToolTip('Applies a coordinated set of queue, fragment and retry settings.')
        preset.addWidget(self.preset_combo)
        top.addLayout(preset)
        layout.addWidget(topbar)

        # URL intake card.
        intake = QFrame()
        intake.setObjectName('glassCard')
        intake_layout = QVBoxLayout(intake)
        intake_layout.setContentsMargins(20, 18, 20, 18)
        intake_layout.setSpacing(12)
        intake_head = QHBoxLayout()
        intake_titles = QVBoxLayout()
        intake_titles.setSpacing(3)
        intake_titles.addWidget(label('Start a download', 'sectionTitle'))
        intake_titles.addWidget(label('Paste a video, playlist or supported media URL. One link per line.', 'muted'))
        intake_head.addLayout(intake_titles, 1)
        intake_head.addWidget(label('BATCH READY', 'eyebrow'), 0, Qt.AlignmentFlag.AlignVCenter)
        intake_layout.addLayout(intake_head)
        self.links = QPlainTextEdit()
        self.links.setObjectName('urlInput')
        self.links.setPlaceholderText('Paste video or playlist links here…\nYou can add multiple URLs, one per line.')
        self.links.setMaximumHeight(88)
        self.links.setAccessibleName('Video and playlist URLs')
        intake_layout.addWidget(self.links)
        actions = QHBoxLayout()
        actions.setSpacing(9)
        paste_button = button('Paste links', self.paste)
        paste_button.setToolTip('Paste URLs from the clipboard')
        actions.addWidget(paste_button)
        self.analyze_btn = button('Inspect video', self.inspect)
        self.analyze_btn.setToolTip('Check title, duration and available video resolutions before downloading')
        actions.addWidget(self.analyze_btn)
        actions.addStretch(1)
        actions.addWidget(button('Add to queue', self.add))
        actions.addWidget(button('Download now', lambda: self.add(True), True))
        intake_layout.addLayout(actions)
        preview_panel = QFrame()
        preview_panel.setObjectName('glassPanel')
        preview_layout = QHBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 9, 12, 9)
        self.preview = label('Ready when you are. Paste a link to inspect or download.', 'muted')
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.preview, 1)
        intake_layout.addWidget(preview_panel)
        layout.addWidget(intake)

        # Download configuration. Simple, Advanced and Professional reveal more controls.
        settings_card = QFrame()
        settings_card.setObjectName('glassCard')
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(18, 15, 18, 16)
        settings_layout.setSpacing(10)
        settings_head = QHBoxLayout()
        settings_head.addWidget(label('Download setup', 'sectionTitle'))
        settings_head.addStretch(1)
        self.workspace_hint = label('Essential settings for everyday downloads.', 'muted')
        settings_head.addWidget(self.workspace_hint)
        settings_layout.addLayout(settings_head)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMinimumHeight(310)
        self.tabs.setMaximumHeight(410)

        output_page = QWidget()
        form = QFormLayout(output_page)
        form.setContentsMargins(16, 15, 16, 15)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(18)
        self.combo(form, 'mode', 'Output format', ['MP4 video', 'MKV video', 'MP3 audio', 'M4A audio', 'FLAC audio', 'WAV audio'])
        self.combo(form, 'quality', 'Maximum video quality', ['Best available', '2160p', '1440p', '1080p', '720p', '480p', '360p'])
        self.combo(form, 'bitrate', 'Audio quality (kbps)', ['320', '256', '192', '128', '96'])
        pathrow = QHBoxLayout()
        self.folder = QLineEdit(self.s.get('folder', str(Path.home() / 'Downloads' / 'YouTube')))
        self.folder.setAccessibleName('Download destination folder')
        self.folder.setToolTip('Choose where downloaded media files are saved.')
        pathrow.addWidget(self.folder, 1)
        pathrow.addWidget(button('Browse…', self.browse))
        pathrow.addWidget(button('Open folder', self.open_folder))
        form.addRow('Save location', pathrow)
        output_checks = QHBoxLayout()
        for key, title, default in [
            ('playlist', 'Download playlist', False),
            ('metadata', 'Embed metadata and chapters', True),
            ('archive', 'Skip previously downloaded items', False),
            ('restrict_filenames', 'ASCII-safe filenames', False),
        ]:
            output_checks.addWidget(self.check(key, title, default))
        form.addRow(output_checks)
        self.option_tab(output_page, 'Output')

        performance_page = QWidget()
        pf = QFormLayout(performance_page)
        pf.setContentsMargins(16, 15, 16, 15)
        pf.setVerticalSpacing(11)
        pf.setHorizontalSpacing(18)
        self.spin(pf, 'parallel', 'Simultaneous downloads', 1, 8, 2)
        self.spin(pf, 'fragments', 'Parallel fragments per download', 1, 32, 4)
        self.spin(pf, 'rate', 'Speed limit per download (KB/s, 0 = unlimited)', 0, 1000000, 0)
        self.spin(pf, 'retries', 'Download and fragment retries', 0, 30, 5)
        self.spin(pf, 'extractor_retries', 'Extractor retries', 0, 30, 3)
        self.spin(pf, 'file_access_retries', 'File access retries', 0, 30, 3)
        self.spin(pf, 'socket_timeout', 'Network timeout (seconds)', 5, 300, 25)
        self.spin(pf, 'sleep_interval', 'Minimum delay between requests (seconds)', 0, 120, 0)
        self.spin(pf, 'max_sleep_interval', 'Maximum randomized delay (seconds)', 0, 300, 0)
        self.combo(pf, 'http_chunk_size', 'HTTP chunk size', ['Off', '1M', '4M', '8M', '16M'])
        self.option_tab(performance_page, 'Performance')

        extras_page = QWidget()
        ef = QFormLayout(extras_page)
        ef.setContentsMargins(16, 15, 16, 15)
        ef.setVerticalSpacing(10)
        ef.setHorizontalSpacing(18)
        ef.addRow(self.check('subtitles', 'Download subtitles'))
        ef.addRow(self.check('auto_subs', 'Include automatically generated subtitles'))
        self.line(ef, 'languages', 'Subtitle languages', 'en.*,fa.*')
        ef.addRow(self.check('embed_subs', 'Embed downloaded subtitles into the media file'))
        ef.addRow(self.check('thumbnail', 'Save thumbnail image separately'))
        ef.addRow(self.check('embed_thumbnail', 'Embed thumbnail as cover art'))
        ef.addRow(self.check('write_description', 'Save video description'))
        ef.addRow(self.check('write_info_json', 'Save full video information (JSON)'))
        ef.addRow(self.check('write_comments', 'Save comments when supported'))
        self.option_tab(extras_page, 'Subtitles and extras')

        network_page = QWidget()
        nf = QFormLayout(network_page)
        nf.setContentsMargins(16, 15, 16, 15)
        nf.setVerticalSpacing(11)
        nf.setHorizontalSpacing(18)
        self.line(nf, 'items', 'Playlist items', 'e.g. 1:10 or 1,3,5')
        self.line(nf, 'proxy', 'Proxy URL', 'http://127.0.0.1:8080 or socks5://127.0.0.1:1080')
        self.combo(nf, 'network_preference', 'IP preference', ['Auto', 'IPv4 only', 'IPv6 only'])
        self.combo(nf, 'browser', 'Use browser cookies (optional)', ['None', 'Firefox', 'Chrome', 'Edge', 'Brave'])
        cookie_row = QHBoxLayout()
        self.cookies = QLineEdit()
        self.cookies.setPlaceholderText('Optional Netscape cookies.txt file (takes priority over browser)')
        self.cookies.setAccessibleName('Netscape cookies file')
        cookie_row.addWidget(self.cookies, 1)
        cookie_row.addWidget(button('Choose file…', self.choose_cookies))
        nf.addRow('Cookies file', cookie_row)
        nf.addRow(label('Cookies are only read when explicitly selected. Browser encryption may restrict access.', 'muted'))
        nf.addRow(self.check('check_on_startup', 'Check required software when the app starts', True))
        self.option_tab(network_page, 'Network and privacy')

        professional_page = QWidget()
        pro = QFormLayout(professional_page)
        pro.setContentsMargins(16, 15, 16, 15)
        pro.setVerticalSpacing(11)
        pro.setHorizontalSpacing(18)
        self.line(pro, 'format_selector', 'Custom yt-dlp format selector', 'e.g. bv*+ba/b (overrides the quality selector)')
        self.line(pro, 'output_template', 'Custom output template', '%(uploader)s/%(title)s [%(id)s].%(ext)s')
        self.line(pro, 'date_after', 'Upload date from (YYYYMMDD)', '20240101')
        self.line(pro, 'date_before', 'Upload date through (YYYYMMDD)', '20261231')
        self.line(pro, 'match_title', 'Title regular expression', 'e.g. tutorial|review')
        self.line(pro, 'min_filesize', 'Minimum file size', 'e.g. 10M')
        self.line(pro, 'max_filesize', 'Maximum file size', 'e.g. 2G')
        self.line(pro, 'extractor_args', 'Extractor-specific arguments', 'e.g. youtube:player_client=default')
        self.combo(pro, 'sponsorblock', 'SponsorBlock', ['Off', 'Mark all segments', 'Remove all segments'])
        pro.addRow(label('Expert controls are passed as separate process arguments, never through a shell. Use only yt-dlp syntax you trust.', 'muted'))
        self.option_tab(professional_page, 'Professional')

        settings_layout.addWidget(self.tabs)
        layout.addWidget(settings_card)

        # Queue and activity workspace.
        queue_card = QFrame()
        queue_card.setObjectName('glassCard')
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(18, 15, 18, 16)
        queue_layout.setSpacing(10)
        queue_head = QHBoxLayout()
        self.summary = label('DOWNLOAD QUEUE', 'eyebrow')
        queue_head.addWidget(self.summary, 1)
        for title, action in [
            ('Start / resume', self.resume), ('Pause', self.pause),
            ('Cancel', self.cancel), ('Clear finished', self.clear)
        ]:
            queue_head.addWidget(button(title, action))
        queue_layout.addLayout(queue_head)

        bulk = QHBoxLayout()
        self.selection_button = QPushButton('Select')
        self.selection_menu = QMenu(self)
        self.selection_button.setMenu(self.selection_menu)
        self.selection_menu.aboutToShow.connect(self.populate_selection_menu)
        bulk.addWidget(self.selection_button)
        self.cleanup_button = QPushButton('Remove from queue')
        self.cleanup_button.setToolTip('Removes queue entries only. Downloaded files and active jobs are kept.')
        self.cleanup_menu = QMenu(self)
        self.cleanup_button.setMenu(self.cleanup_menu)
        self.cleanup_menu.aboutToShow.connect(self.populate_cleanup_menu)
        bulk.addWidget(self.cleanup_button)
        self.retry_failed_button = button('Retry failed', self.retry_failed)
        bulk.addWidget(self.retry_failed_button)
        self.selection_count = label('0 selected', 'muted')
        bulk.addWidget(self.selection_count)
        bulk.addStretch(1)
        bulk.addWidget(label('Removing queue entries never deletes media files.', 'muted'))
        queue_layout.addLayout(bulk)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName('queueTable')
        self.table.setHorizontalHeaderLabels(['Title / URL', 'Status', 'Progress', 'Speed', 'ETA', 'Format'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 190)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(230)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_job_menu)
        self.table.itemSelectionChanged.connect(self.update_bulk_actions)
        queue_layout.addWidget(self.table)
        layout.addWidget(queue_card)

        activity = QFrame()
        activity.setObjectName('glassPanel')
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(14, 11, 14, 12)
        activity_layout.setSpacing(6)
        activity_layout.addWidget(label('ACTIVITY & TROUBLESHOOTING', 'eyebrow'))
        self.log = QPlainTextEdit()
        self.log.setObjectName('activityLog')
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setMaximumHeight(100)
        self.log.setPlaceholderText('Download progress and troubleshooting details appear here.')
        activity_layout.addWidget(self.log)
        layout.addWidget(activity)

        footer = QHBoxLayout()
        footer.addWidget(label('Pause keeps partial files. Double-click a completed item to open it.', 'muted'), 1)
        footer.addWidget(button('System check', self.check_system))
        footer.addWidget(button('Update engine', self.update_engine))
        layout.addLayout(footer)

        self.experience_combo.currentTextChanged.connect(self.set_experience_level)
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        self.controls['mode'].currentTextChanged.connect(self.update_mode_controls)
        self.set_experience_level(self.experience_combo.currentText())
        self.update_mode_controls(self.controls['mode'].currentText())

        self.download_shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        self.download_shortcut.activated.connect(lambda: self.add(True))
        self.paste_shortcut = QShortcut(QKeySequence('Ctrl+Shift+V'), self)
        self.paste_shortcut.activated.connect(self.paste)
        self.open_folder_shortcut = QShortcut(QKeySequence('Ctrl+Shift+O'), self)
        self.open_folder_shortcut.activated.connect(self.open_folder)

        self.render()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(300)
        if (self.controls['check_on_startup'].isChecked()
                and not os.environ.get('PYTEST_CURRENT_TEST')
                and os.environ.get('QT_QPA_PLATFORM') != 'offscreen'
                and '--smoke-test' not in sys.argv):
            QTimer.singleShot(300, lambda: self.check_system(startup=True))

    def option_tab(self, page, title):
        page.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        page.layout().setVerticalSpacing(11)
        page.layout().setHorizontalSpacing(18)
        page.layout().setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)

    def combo(self, form, key, title, values):
        w = QComboBox()
        w.setObjectName(key)
        w.addItems(values)
        w.setCurrentText(str(self.s.get(key, values[0])))
        w.setAccessibleName(title)
        w.setToolTip(title)
        self.controls[key] = w
        form.addRow(title, w)
        return w

    def spin(self, form, key, title, low, high, default):
        w = QSpinBox()
        w.setObjectName(key)
        w.setRange(low, high)
        try:
            w.setValue(int(self.s.get(key, default)))
        except (TypeError, ValueError):
            w.setValue(default)
        w.setAccessibleName(title)
        w.setToolTip(title)
        self.controls[key] = w
        form.addRow(title, w)
        return w

    def line(self, form, key, title, hint):
        w = QLineEdit(str(self.s.get(key, '')))
        w.setObjectName(key)
        w.setPlaceholderText(hint)
        w.setAccessibleName(title)
        w.setToolTip(title + '. ' + hint)
        self.controls[key] = w
        form.addRow(title, w)
        return w

    def check(self, key, title, default=False):
        w = QCheckBox(title)
        w.setObjectName(key)
        w.setChecked(bool(self.s.get(key, default)))
        w.setAccessibleName(title)
        w.setToolTip(title)
        self.controls[key] = w
        return w

    def set_experience_level(self, level):
        level = level if level in ('Simple', 'Advanced', 'Professional') else 'Simple'
        visible = {
            0: True,
            1: level in ('Advanced', 'Professional'),
            2: level in ('Advanced', 'Professional'),
            3: level in ('Advanced', 'Professional'),
            4: level == 'Professional',
        }
        for index, show in visible.items():
            self.tabs.setTabVisible(index, show)
        if not self.tabs.isTabVisible(self.tabs.currentIndex()):
            self.tabs.setCurrentIndex(0)
        self.workspace_hint.setText({
            'Simple': 'Essential settings for everyday downloads.',
            'Advanced': 'Fine-tune speed, subtitles, network and privacy.',
            'Professional': 'Full control over yt-dlp formats, filters and post-processing.',
        }[level])
        if hasattr(self, 's'):
            self.s['experience_level'] = level

    def apply_preset(self, name):
        presets = {
            'Balanced': {
                'parallel': 2, 'fragments': 4, 'rate': 0, 'retries': 5,
                'extractor_retries': 3, 'file_access_retries': 3,
                'socket_timeout': 25, 'sleep_interval': 0, 'max_sleep_interval': 0,
                'http_chunk_size': 'Off',
            },
            'Maximum speed': {
                'parallel': 5, 'fragments': 16, 'rate': 0, 'retries': 3,
                'extractor_retries': 2, 'file_access_retries': 2,
                'socket_timeout': 25, 'sleep_interval': 0, 'max_sleep_interval': 0,
                'http_chunk_size': '8M',
            },
            'Maximum reliability': {
                'parallel': 1, 'fragments': 2, 'rate': 0, 'retries': 12,
                'extractor_retries': 10, 'file_access_retries': 10,
                'socket_timeout': 90, 'sleep_interval': 1, 'max_sleep_interval': 5,
                'http_chunk_size': 'Off',
            },
            'Data saver': {
                'parallel': 1, 'fragments': 2, 'rate': 1024, 'retries': 5,
                'extractor_retries': 5, 'file_access_retries': 5,
                'socket_timeout': 45, 'sleep_interval': 1, 'max_sleep_interval': 3,
                'http_chunk_size': '1M',
            },
        }
        for key, value in presets.get(name, {}).items():
            control = self.controls.get(key)
            if isinstance(control, QSpinBox):
                control.setValue(value)
            elif isinstance(control, QComboBox):
                control.setCurrentText(value)
        if hasattr(self, 'log'):
            self.note('Performance profile applied: ' + name)

    def update_mode_controls(self, mode):
        video = str(mode).endswith('video')
        self.controls['quality'].setEnabled(video)
        self.controls['bitrate'].setEnabled(not video)
        self.controls['quality'].setToolTip('Maximum video resolution.' if video else 'Only applies to video formats.')
        self.controls['bitrate'].setToolTip('Audio encoding quality in kbps.' if not video else 'Only applies to audio formats.')

    # Coalesce frequent download progress events to reduce Qt table repaints.
    def schedule_render(self, job_id=None):
        if self.closing:
            return
        if job_id is None:
            self._full_render_pending = True
            self._dirty_job_ids.clear()
        elif not self._full_render_pending:
            self._dirty_job_ids.add(job_id)
        if not self._render_timer.isActive():
            self._render_timer.start()

    # Render only dirty jobs unless the table layout itself has changed.
    def flush_render(self):
        if self._full_render_pending:
            self._full_render_pending = False
            self._dirty_job_ids.clear()
            self.render()
        elif self._dirty_job_ids:
            dirty = set(self._dirty_job_ids)
            self._dirty_job_ids.clear()
            self.render(dirty)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: apply_native_window_effects(self))
        animate_window_entrance(self, start=0.965, duration=230)

    def settings(self):
        values = {}
        for key, widget in self.controls.items():
            values[key] = (widget.isChecked() if isinstance(widget, QCheckBox)
                           else widget.value() if isinstance(widget, QSpinBox)
                           else widget.currentText() if isinstance(widget, QComboBox)
                           else widget.text().strip())
        values['folder'] = self.folder.text().strip()
        values['cookies'] = self.cookies.text().strip()
        values['experience_level'] = self.experience_combo.currentText()
        values['performance_preset'] = self.preset_combo.currentText()
        return values
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
        if '%' in str(j.get('progress', '')):
            row = next((index for index, item in enumerate(self.jobs)
                        if item['id'] == j['id']), -1)
            bar = self.table.cellWidget(row, 2) if row >= 0 else None
            if isinstance(bar, QProgressBar) and bar.maximum() == 0:
                self.render({j['id']})
                return
        self.schedule_render(j['id'])
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
    # Stop the relevant child process tree while retaining partial media.
    def stop_process(self,p):
        # Stop FFmpeg/runtime descendants as well as the downloader itself.
        pid=int(p.processId())
        if pid and os.name=='nt':
            subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        elif pid:p.kill()
    def clear(self):
        self.remove_jobs([j for j in self.jobs if j['status'] in ('Completed','Cancelled','Skipped')])
    def render(self, job_ids=None):
        full_refresh = job_ids is None
        if full_refresh:
            self._full_render_pending = False
            self._dirty_job_ids.clear()
        if full_refresh and self.table.rowCount() != len(self.jobs):
            self.table.setRowCount(len(self.jobs))
        if full_refresh:
            rows = enumerate(self.jobs)
        else:
            wanted = set(job_ids or ())
            rows = ((index, job) for index, job in enumerate(self.jobs) if job['id'] in wanted)

        self.table.setUpdatesEnabled(False)
        try:
            for row, job in rows:
                values = [
                    job.get('title', job.get('url', '')),
                    job.get('status', 'Queued'),
                    job.get('progress', ''),
                    job.get('speed', ''),
                    job.get('eta', ''),
                    job.get('settings', {}).get('mode', 'MP4 video'),
                ]
                for column, value in enumerate(values):
                    if column == 2:
                        bar = self.table.cellWidget(row, column)
                        if not isinstance(bar, QProgressBar):
                            bar = QProgressBar()
                            bar.setTextVisible(True)
                            bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                            bar.setAccessibleName('Download progress')
                            self.table.setCellWidget(row, column, bar)
                        match = re.search(r'(\d+(?:\.\d+)?)\s*%', str(job.get('progress', '')))
                        active = job.get('status') in ('Downloading', 'Processing')
                        if active and not match:
                            if bar.minimum() != 0 or bar.maximum() != 0:
                                bar.setRange(0, 0)
                            if bar.format() != 'Connecting…':
                                bar.setFormat('Connecting…')
                        else:
                            if bar.minimum() != 0 or bar.maximum() != 1000:
                                bar.setRange(0, 1000)
                            percent = (100.0 if job.get('status') == 'Completed'
                                       else min(100.0, float(match.group(1))) if match else 0.0)
                            target = round(percent * 10)
                            if bar.value() != target:
                                if bar.value() == 0 or not active or target >= 1000:
                                    bar.setValue(target)
                                else:
                                    previous = getattr(bar, '_value_animation', None)
                                    if previous:
                                        previous.stop()
                                    animation = QPropertyAnimation(bar, b'value', bar)
                                    animation.setDuration(135)
                                    animation.setStartValue(bar.value())
                                    animation.setEndValue(target)
                                    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                                    animation.start()
                                    bar._value_animation = animation
                            fmt = ('Finalizing…' if active and percent >= 100 else
                                   f'{percent:.1f}%' if active or job.get('status') == 'Completed' else
                                   f"{job.get('status')} · {percent:.1f}%" if match else job.get('status', ''))
                            if bar.format() != fmt:
                                bar.setFormat(fmt)
                        tip = 'Progress of the current media stream; video and audio may download separately.'
                        if bar.toolTip() != tip:
                            bar.setToolTip(tip)
                        continue

                    item = self.table.item(row, column)
                    if item is None:
                        item = QTableWidgetItem()
                        self.table.setItem(row, column, item)
                    text_value = str(value)
                    if item.text() != text_value:
                        item.setText(text_value)
                    tooltip = job.get('error') or job.get('url', '')
                    if item.toolTip() != tooltip:
                        item.setToolTip(tooltip)
                    if column == 1:
                        color = QColor('#6de2c3' if job.get('status') == 'Completed'
                                       else '#ff9e9e' if job.get('status') == 'Failed'
                                       else '#a9b9cf')
                        if item.foreground().color() != color:
                            item.setForeground(color)
        finally:
            self.table.setUpdatesEnabled(True)

        if full_refresh:
            summary_text = f"DOWNLOAD QUEUE  /  {len(self.jobs)} items  /  {len(self.running)} active"
            if self.summary.text() != summary_text:
                self.summary.setText(summary_text)
            self.update_bulk_actions()
        self.table.viewport().update()
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
    def check_system(self, startup=False):
        """Offline diagnostic; only the user's explicit Yes opens an install page."""
        try:
            items = check_runtime(browser=self.controls['browser'].currentText(),
                                  destination=self.folder.text().strip(), data_dir=DATA)
            report = system_check_summary(items)
            save(DATA/'system-check.json', {'checked_at': datetime.now().isoformat(), **report})
            self.status_label.setText('●  Ready' if report['ready'] else '●  Attention')
        except Exception as exc:
            self.status_label.setText('●  Failed')
            QMessageBox.warning(self, 'System check failed', f'Diagnostic error: {type(exc).__name__}: {exc}')
            return
        problems = [item for item in items if item.status != 'ok']
        if not startup or problems:
            dialog = SystemCheckDialog(items, report, self)
            dialog.exec()
        else:
            self.note('System check passed: bundled tools and required software are ready.')
        for item in problems:
            if not item.install_url:
                continue
            question = ('This is optional and is only needed if you choose its feature.'
                        if not item.required else
                        'This component is required for normal use.')
            prompt = QMessageBox(self)
            prompt.setWindowTitle('Additional software')
            prompt.setIcon(QMessageBox.Icon.Warning if item.required else QMessageBox.Icon.Information)
            prompt.setText(f'{item.title} is not available')
            prompt.setInformativeText(
                f'{item.detail}\n\n{question}\n\n'
                'Would you like to open the official download page? '
                'Nothing will be downloaded or installed automatically.'
            )
            prompt.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            prompt.setDefaultButton(QMessageBox.StandardButton.No)
            prompt.setStyleSheet("""
                QMessageBox { background:#101725; color:#EAF0FA; }
                QLabel { color:#EAF0FA; min-width:380px; }
                QPushButton { background:#26364D; color:#EAF0FA; border:1px solid #3A4D68;
                              border-radius:8px; padding:8px 16px; min-width:76px; }
                QPushButton:hover { background:#314660; }
            """)
            if prompt.exec() == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(item.install_url))

    def audit_output(self, process):
        output = bytes(process.readAllStandardOutput()).decode('utf-8', 'replace')
        for line in output.splitlines():
            if line.strip():
                self.note('AUDIT  ' + line[-500:])

    def start_multi_agent_audit(self):
        if self.audit_process and self.audit_process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, 'Multi-agent audit', 'An audit is already running.')
            return
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('QT_QPA_PLATFORM', 'offscreen')
        environment.insert('YDS_AUDIT_ROOT', str(ROOT / 'audit_sources' if FROZEN else ROOT))
        environment.insert('YDS_REPORT_DIR', str(DATA / 'reports' if FROZEN else ROOT / 'reports'))
        environment.insert('LOCALAPPDATA', str(DATA / 'audit-runtime'))
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        if FROZEN:
            process.setArguments(['--run-audit', '--full', '--online-research'])
        else:
            process.setArguments([str(ROOT / 'project_orchestrator.py'),
                                  '--full', '--online-research'])
        self.audit_process = process
        process.readyReadStandardOutput.connect(lambda: self.audit_output(process))
        process.finished.connect(lambda code, status: self.audit_finished(process, code))
        process.errorOccurred.connect(lambda error: self.audit_error(process, error))
        process.start()
        self.note('Multi-agent audit started: architecture, dependencies, security, UX, packaging, portability, QA and R&D.')

    def audit_error(self, process, error):
        if process.error() == QProcess.ProcessError.FailedToStart:
            self.note('Multi-agent audit could not start. Check the application runtime.')
            if self.audit_process is process:
                self.audit_process = None

    def audit_finished(self, process, code):
        self.audit_output(process)
        if self.audit_process is process:
            self.audit_process = None
        self.note('Multi-agent audit completed.' if code == 0 else f'Multi-agent audit failed (exit {code}).')
        self.note('Audit report: ' + str(DATA / 'reports' / 'orchestrator-report.json'))
        self.note('R&D roadmap: ' + str(DATA / 'reports' / 'RD_ROADMAP.md'))
        process.deleteLater()

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
        self.closing=True
        self.timer.stop()
        self._render_timer.stop()
        for j in self.jobs:
            if j['id'] in self.running:
                j['stop']='Paused'; p=self.running[j['id']]; self.stop_process(p); p.waitForFinished(3000)
        for p in [self.inspector,getattr(self,'updater',None),self.audit_process]:
            if p:self.stop_process(p); p.waitForFinished(3000)
        self.persist(); event.accept()

def main():
    if '--run-audit' in sys.argv:
        sys.exit(run_multi_agent_audit(full='--quick' not in sys.argv,
                                       online='--online-research' in sys.argv))
    if '--verify-bundle' in sys.argv:
        import tempfile
        report={}
        try:
            for name,flag in [('yt-dlp','--version'),('deno','--version'),('ffmpeg','-version'),('ffprobe','-version')]:
                result=subprocess.run([tool(name),flag],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                report[name]=result.stdout.splitlines()[0]
            with tempfile.TemporaryDirectory() as directory:
                video=str(Path(directory)/'check.mp4')
                subprocess.run([tool('ffmpeg'),'-v','error','-f','lavfi','-i','color=size=320x180:rate=5','-t','1','-c:v','libx264',video],stdin=subprocess.DEVNULL,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                result=subprocess.run([tool('ffprobe'),'-v','error','-show_entries','stream=width,height','-of','json',video],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
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
                    result=subprocess.run([tool('yt-dlp'),*arguments(url,{},True)],stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
                    report['inspection']=json.loads(result.stdout)['id']
                    result=subprocess.run([tool('yt-dlp'),*arguments(url,{'folder':str(Path(directory)/'downloads'),'mode':'MP4 video'})],stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW,env=child_environment(),check=True)
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
