import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
import main
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(main.STYLE)
with tempfile.TemporaryDirectory() as d:
 main.DATA=Path(d);w=main.Window();w.timer.stop();w.resize(1060,800);w.show();w.tabs.setCurrentIndex(2);app.processEvents()
 w.controls['subtitles'].setChecked(True)
 w.grab().save('ui-options-preview.png')
 w.tabs.widget(2).verticalScrollBar().setValue(w.tabs.widget(2).verticalScrollBar().maximum());app.processEvents();w.grab().save('ui-options-bottom.png')
 w.jobs=[dict(id='qa',title='Example video',url='https://example.com/video',status='Paused',progress='42.5%',speed='',eta='',files=[],settings={'mode':'MP4 video','folder':d,'quality':'1080p'})];w.render()
 w.page_scroll.verticalScrollBar().setValue(w.page_scroll.verticalScrollBar().maximum());app.processEvents()
 menu=w.job_menu(w.jobs);menu.popup(w.table.mapToGlobal(QPoint(120,30)));app.processEvents();menu.grab().save('ui-menu-preview.png');menu.close();w.close()
