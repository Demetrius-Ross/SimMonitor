from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt

class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: #002D72; color: white;")

        self.title = QLabel("FlightSafety Simulator Monitor")
        self.title.setStyleSheet("margin-left: 10px;")
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("background-color: transparent; color: white; border: none;")
        self.close_button.clicked.connect(parent.close)

        layout = QHBoxLayout()
        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.close_button)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def mousePressEvent(self, event):
        self._start_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self._start_pos
            self.parent().move(self.parent().pos() + delta)
            self._start_pos = event.globalPos()
