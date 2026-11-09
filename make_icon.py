from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap,QPainter,QColor,QPolygon
from PySide6.QtCore import QPoint,Qt
app=QApplication([])
p=QPixmap(256,256);p.fill(Qt.GlobalColor.transparent)
a=QPainter(p);a.setRenderHint(QPainter.RenderHint.Antialiasing);a.setBrush(QColor('#10141f'));a.setPen(Qt.PenStyle.NoPen);a.drawRoundedRect(0,0,256,256,52,52);a.setBrush(QColor('#6de2c3'));a.drawRoundedRect(48,42,160,172,30,30);a.setBrush(QColor('#10141f'));a.drawPolygon(QPolygon([QPoint(105,79),QPoint(165,115),QPoint(105,151)]));a.drawRoundedRect(83,171,90,10,5,5);a.end();p.save('app.ico')
