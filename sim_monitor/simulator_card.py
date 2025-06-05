# simulator_card.py

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

SIM_IMAGES = {
    "online": "images/FINAL-SIM-UP.png",
    "ramping": "images/FINAL-RAMP-UP.png",
    "offline": "images/FINAL-SIM-DOWN.png"
}

class SimulatorCard(QWidget):
    def __init__(self, sim_id, name=None):
        super().__init__()

        self.sim_id = sim_id
        self.name = name or f"SIM-{sim_id}"
        self.motion_state = 0
        self.ramp_state = 0
        self.offline = True

        self.setFixedSize(310, 420)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setAlignment(Qt.AlignCenter)

        # Card container
        card = QFrame()
        card.setObjectName("simCard")
        card.setStyleSheet("""
            QFrame#simCard {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 3)
        shadow.setBlurRadius(14)
        shadow.setColor(Qt.gray)
        card.setGraphicsEffect(shadow)

        # Title
        self.title = QLabel(self.name)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Arial", 18, QFont.Bold))
        card_layout.addWidget(self.title)

        # Image (maximized)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setPixmap(self.get_pixmap("offline"))
        card_layout.addWidget(self.image)

        # Banner
        self.banner = QLabel("DISCONNECTED")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setFont(QFont("Arial", 16, QFont.Bold))
        self.banner.setStyleSheet("""
            background-color: red;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
        """)
        card_layout.addWidget(self.banner)

        outer_layout.addWidget(card)
        self.update_display()

    def get_pixmap(self, key):
        path = SIM_IMAGES.get(key)
        if path:
            return QPixmap(path).scaled(330, 330, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap()

    def update_display(self):
        if self.offline:
            self.image.setPixmap(self.get_pixmap("offline"))
            self.banner.show()
        else:
            self.banner.hide()
            if self.ramp_state == 2:
                self.image.setPixmap(self.get_pixmap("ramping"))
            else:
                self.image.setPixmap(self.get_pixmap("online"))

    def update_state(self, motion, ramp):
        self.motion_state = motion
        self.ramp_state = ramp
        self.offline = False
        self.update_display()

    def set_offline(self, offline=True):
        self.offline = offline
        self.update_display()
