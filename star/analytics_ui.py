"""Native Qt dashboard widgets with true SQLite-backed values and no chart service."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from .design_system import COLORS


class ActivityChart(QWidget):
    """Compact antialiased 14-day chart with a truthful zero-data state."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._trend = []
        self.setMinimumHeight(230)
        self.setAccessibleName('Local STAR task runs chart')
        self.setToolTip('Actual daily STAR task starts from local run logs')

    def set_trend(self, trend: list[dict]):
        self._trend = list(trend)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        area = QRectF(48, 16, max(40, self.width()-68), max(70, self.height()-51))
        values = [max(0, int(v.get('runs', 0))) for v in self._trend]
        painter.setFont(QFont('Segoe UI', 10))
        painter.setPen(QColor(COLORS['tertiary']))
        if not values or not any(values):
            painter.drawText(self.rect(), Qt.AlignCenter, 'No task runs yet · Your real activity will appear here')
            painter.end()
            return
        max_value = max(values)
        # A true zero baseline; evenly spaced horizontal guides, no fake trend.
        for line in range(4):
            y = area.bottom() - line * area.height()/3
            painter.setPen(QPen(QColor('#292E35'), 1))
            painter.drawLine(QPointF(area.left(),y), QPointF(area.right(),y))
            painter.setPen(QColor(COLORS['tertiary']))
            painter.drawText(QRectF(0,y-9,38,18), Qt.AlignRight|Qt.AlignVCenter,
                             str(round(line * max_value / 3)))
        points = []
        for i,value in enumerate(values):
            x = area.left() + (i * area.width() / max(1, len(values)-1))
            y = area.bottom() - (value/max_value) * area.height()
            points.append(QPointF(x,y))
        line_path = QPainterPath(points[0])
        for p in points[1:]:
            line_path.lineTo(p)
        fill_path = QPainterPath(line_path)
        fill_path.lineTo(area.bottomRight())
        fill_path.lineTo(area.bottomLeft())
        fill_path.closeSubpath()
        gold = QColor(COLORS['gold'])
        top = QColor(gold); top.setAlpha(65)
        bottom = QColor(gold); bottom.setAlpha(0)
        gradient = QLinearGradient(0, area.top(), 0, area.bottom())
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        painter.fillPath(fill_path, QBrush(gradient))
        painter.setPen(QPen(gold, 2.2))
        painter.drawPath(line_path)
        # Only endpoints are labelled to avoid cramped 14-day axis labels.
        painter.setPen(QColor(COLORS['muted']))
        if self._trend:
            start = self._trend[0].get('date','')[-5:]
            end = self._trend[-1].get('date','')[-5:]
            painter.drawText(QRectF(area.left(),area.bottom()+8,76,17),Qt.AlignLeft,start)
            painter.drawText(QRectF(area.right()-78,area.bottom()+8,78,17),Qt.AlignRight,end)
        painter.end()


class MetricCard(QFrame):
    def __init__(self, label: str, value: str='0'):
        super().__init__()
        self.setObjectName('MetricCard')
        self.setMinimumWidth(136)
        body = QVBoxLayout(self)
        body.setContentsMargins(19,17,19,17)
        body.setSpacing(8)
        self.caption = QLabel(label)
        self.caption.setObjectName('MetricLabel')
        self.caption.setWordWrap(True)
        self.value = QLabel(str(value))
        self.value.setObjectName('MetricValue')
        body.addWidget(self.caption)
        body.addWidget(self.value)

    def set_value(self, value):
        self.value.setText(str(value))
