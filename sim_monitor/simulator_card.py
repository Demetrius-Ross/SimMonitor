from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFrame, QGraphicsDropShadowEffect, QStackedLayout
)
from PyQt5.QtGui import QPixmap, QFont, QRegion, QPainterPath
from PyQt5.QtCore import Qt, QSize, QRectF

SIM_IMAGES = {
    "motion-on": "images/FINAL-SIM-UP.png",
    "ramping": "images/FINAL-RAMP-UP.png",
    "at-home": "images/FINAL-SIM-DOWN.png",
    "offline": "images/FINAL-SIM-DOWN.png"
}


class SimulatorCard(QWidget):
    def __init__(self, sim_id, name=None, *, scale: float = 1.0):
        super().__init__()

        self.sim_id = sim_id
        self.name = name or f"SIM-{sim_id}"
        self.motion_state = 0
        self.ramp_state = 0
        self.offline = True
        self.scale = scale

        # Full card size
        self.setFixedSize(int(310 * self.scale), int(420 * self.scale))

        # Main layout
        self.stack = QStackedLayout(self)
        self.card_container = QWidget()
        self.stack.addWidget(self.card_container)

        # Card layout
        outer_layout = QVBoxLayout(self.card_container)
        outer_layout.setContentsMargins(int(10 * self.scale), int(10 * self.scale), int(10 * self.scale), int(10 * self.scale))
        outer_layout.setAlignment(Qt.AlignCenter)

        # Inner card
        self.card = QFrame()
        self.card.setObjectName("simCard")
        self.card.setStyleSheet("""
            QFrame#simCard {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 16px;
            }
        """)
        self.card.setMinimumSize(QSize(0, 0))
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(int(12 * self.scale), int(12 * self.scale), int(12 * self.scale), int(12 * self.scale))
        card_layout.setSpacing(int(12 * self.scale))
        card_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, int(3 * self.scale))
        shadow.setBlurRadius(int(14 * self.scale))
        shadow.setColor(Qt.gray)
        self.card.setGraphicsEffect(shadow)

        # Title
        self.title = QLabel(self.name)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Arial", int(28 * self.scale), QFont.Bold))
        card_layout.addWidget(self.title)

        # Image
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        self.image.setFixedHeight(int(330 * self.scale))
        self.image.setStyleSheet("padding-top: 10px;")
        self.image.setPixmap(self.get_pixmap("offline"))
        card_layout.addWidget(self.image)

        # Banner
        self.banner = QLabel("DISCONNECTED")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setFont(QFont("Arial", int(16 * self.scale), QFont.Bold))
        self.banner.setStyleSheet("""
            background-color: red;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
        """)
        card_layout.addWidget(self.banner)

        outer_layout.addWidget(self.card)

        # Gray overlay – child of the actual rounded card frame
        self.overlay = QLabel(self.card)
        self.overlay.setStyleSheet("""
            background-color: rgba(0, 0, 0, 80);
            border-radius: 16px;
        """)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.hide()


        self.update_display()

    def apply_overlay_mask(self):
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QPainterPath, QRegion

        # Get the exact geometry of the visible white part (ignore shadow)
        visible_rect = QRectF(0, 0, self.card.width(), self.card.height())
        corner_radius = 16  # Must match your CSS border-radius

        path = QPainterPath()
        path.addRoundedRect(visible_rect, corner_radius, corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())

        self.overlay.setMask(region)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.card.rect())  # Cover full card (including shadow bleed)
        self.apply_overlay_mask()


    def get_pixmap(self, key):
        path = SIM_IMAGES.get(key)
        if path:
            return QPixmap(path).scaled(int(330 * self.scale), int(330 * self.scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap()

    def update_display(self):
        if self.offline:
            self.image.setPixmap(self.get_pixmap("offline"))
            self.banner.setText("DISCONNECTED")
            self.banner.show()
            self.overlay.show()
            self.overlay.raise_()
        else:
            self.banner.hide()
            self.overlay.hide()

            if self.motion_state == 2:
                self.image.setPixmap(self.get_pixmap("motion-on"))
            elif self.motion_state == 1:
                if self.ramp_state == 1:
                    self.image.setPixmap(self.get_pixmap("ramping"))
                else:
                    self.image.setPixmap(self.get_pixmap("at-home"))
            else:
                self.image.setPixmap(self.get_pixmap("motion-on"))

    def update_state(self, motion, ramp):
        self.motion_state = motion
        self.ramp_state = ramp
        self.set_offline(False)

    def set_offline(self, offline=True):
        self.offline = offline

        if offline:
            self.overlay.show()
            self.overlay.raise_()

            # Remove drop shadow
            self.card.setGraphicsEffect(None)
        else:
            self.overlay.hide()

            # Restore drop shadow
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setOffset(0, int(3 * self.scale))
            shadow.setBlurRadius(int(14 * self.scale))
            shadow.setColor(Qt.gray)
            self.card.setGraphicsEffect(shadow)

        self.update_display()

