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
    def __init__(self, sim_id, name=None,*,scale: float = 1.0):
        super().__init__()

        self.sim_id = sim_id
        self.name = name or f"SIM-{sim_id}"
        self.motion_state = 0
        self.ramp_state = 0
        self.offline = True
        self.scale = scale

        self.setFixedSize(int(310*self.scale), int(420*self.scale))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(int(10*self.scale), int(10*self.scale), int(10*self.scale), int(10*self.scale))
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
        card_layout.setContentsMargins(int(12*self.scale), int(12*self.scale), int(12*self.scale), int(12*self.scale))
        card_layout.setSpacing(int(12*self.scale))
        card_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, int(3*self.scale))
        shadow.setBlurRadius(int(14*self.scale))
        shadow.setColor(Qt.gray)
        card.setGraphicsEffect(shadow)

        # Title
        self.title = QLabel(self.name)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Arial", int(18*self.scale), QFont.Bold))
        card_layout.addWidget(self.title)

        # Image (maximized)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setPixmap(self.get_pixmap("offline"))
        card_layout.addWidget(self.image)

        # Banner
        self.banner = QLabel("DISCONNECTED")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setFont(QFont("Arial", int(16*self.scale), QFont.Bold))
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
            return QPixmap(path).scaled(int(330*self.scale), int(330*self.scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
