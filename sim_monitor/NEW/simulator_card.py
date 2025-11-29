from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFrame, QGraphicsDropShadowEffect, QStackedLayout
)
from PyQt5.QtGui import QPixmap, QFont, QRegion, QPainterPath, QPainter, QColor, QBrush
from PyQt5.QtCore import Qt, QSize, QRectF, QTimer, QPoint

SIM_IMAGES = {
    "motion-on": "images/FINAL-SIM-UP.png",
    "ramping": "images/FINAL-RAMP-UP.png",
    "at-home": "images/FINAL-SIM-DOWN.png",
    "offline": "images/FINAL-SIM-DOWN.png",
    "motion-on-no-ramp": "images/FINAL-SIM-UP-NO-RAMP.png",
    "at-home-no-ramp": "images/FINAL-SIM-DOWN-NO-RAMP.png"
}



class AnimatedStatusBar(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = 0
        self.animation_enabled = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_offset)
        self.timer.setInterval(60)  # ~30 FPS

    def enable_animation(self, enable=True):
        self.animation_enabled = enable
        if enable:
            self.timer.start()
        else:
            self.timer.stop()
            self.update()  # repaint to remove stripes

    def update_offset(self):
        self.offset = (self.offset + 2) % 20
        self.update()

    def paintEvent(self, event):
        # First: draw the label text (default QLabel behavior)
        QLabel.paintEvent(self, event)

        # Then: overlay animated stripes *under* the text
        if self.animation_enabled:
            painter = QPainter(self)
            painter.setOpacity(0.30)
            brush = QBrush(QColor("white"))  # dark red
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)
            painter.setClipRect(self.rect())

            w = self.width()
            h = self.height()
            spacing = 20
            stripe_width = 10

            for x in range(-40, w, spacing):
                x_pos = x + self.offset
                painter.save()
                painter.translate(x_pos, 0)
                painter.rotate(30)
                painter.drawRect(0, -h, stripe_width, h * 3)
                painter.restore()



class SimulatorCard(QWidget):
    def __init__(self, sim_id, name=None, *, scale: float = 1.0):
        super().__init__()

        self.sim_id = sim_id
        self.name = name or f"SIM-{sim_id}"
        self.motion_state = 0
        self.ramp_state = 0
        self.offline = True
        self.scale = scale
        self.ramp_disconnect_timer = QTimer(self)
        self.ramp_disconnect_timer.setSingleShot(True)
        self.ramp_disconnect_timer.timeout.connect(self.activate_ramp_disconnected)
        self.ramp_disconnected = False
        
        self.force_label_override = False

        self.ramp_disconnect_label_timer = QTimer(self)
        self.ramp_disconnect_label_timer.setSingleShot(True)
        self.ramp_disconnect_label_timer.timeout.connect(self.clear_ramp_label_override)


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
        self.card.setMinimumHeight(int(400 * self.scale))  # match your full scaled height
        self.card.setMaximumHeight(int(400 * self.scale))

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

        # Status Bar (dynamic)
        self.status_bar = AnimatedStatusBar("DISCONNECTED")
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setFont(QFont("Arial", int(16 * self.scale), QFont.Bold))
        self.status_bar.setStyleSheet("""
            background-color: #bbb;
            color: black;
            padding: 8px 16px;
            border-radius: 6px;
        """)
        card_layout.addWidget(self.status_bar)


        outer_layout.addWidget(self.card)

        # Gray overlay – child of the actual rounded card frame
        self.overlay = QLabel(self.card)
        self.overlay_radius = int(16 * self.scale)
        self.overlay.setStyleSheet(f"""
            background-color: rgba(0, 0, 0, 80);
            border-radius: {self.overlay_radius}px;
        """)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.hide()


        self.update_display()

    def apply_overlay_mask(self):
        visible_rect = QRectF(self.overlay.rect())
        path = QPainterPath()
        path.addRoundedRect(visible_rect, self.overlay_radius, self.overlay_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.overlay.setMask(region)



    def resizeEvent(self, event):
        super().resizeEvent(event)

        # Ensure the card fills the full expected space
        self.card.setFixedHeight(int(400 * self.scale))  # match outer dimensions
        self.overlay.setGeometry(0, 0, self.card.width(), self.card.height())
        self.apply_overlay_mask()




    def get_pixmap(self, key):
        path = SIM_IMAGES.get(key)
        if path:
            return QPixmap(path).scaled(int(330 * self.scale), int(330 * self.scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap()

    def update_display(self):
        if self.offline:
            self.image.setPixmap(self.get_pixmap("offline"))
            self.status_bar.setText("DISCONNECTED")
            self.status_bar.setStyleSheet("""
                background-color: #bbb;
                color: black;
                padding: 8px 16px;
                border-radius: 6px;
            """)
            self.overlay.show()
            self.overlay.raise_()
            return

        self.overlay.hide()

        if self.ramp_disconnected:
            key = "motion-on-no-ramp" if self.motion_state == 2 else "at-home-no-ramp"
            self.image.setPixmap(self.get_pixmap(key))

            if self.force_label_override:
                self.status_bar.setText("Ramp Disconnected")
                self.status_bar.setStyleSheet("""
                    background-color: orange;
                    color: black;
                    padding: 8px 16px;
                    border-radius: 6px;
                """)
                self.status_bar.enable_animation(False)
                return
            else:
                # After 5s — show appropriate fallback label based on motion only
                if self.motion_state == 2:
                    self.status_bar.setText("In Operation (No Ramp)")
                    self.status_bar.setStyleSheet("""
                        background-color: red;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 6px;
                    """)
                    self.status_bar.enable_animation(True)
                elif self.motion_state == 1:
                    self.status_bar.setText("Standby (No Ramp)")
                    self.status_bar.setStyleSheet("""
                        background-color: green;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 6px;
                    """)
                    self.status_bar.enable_animation(False)
                else:
                    self.status_bar.setText("Unknown (No Ramp)")
                    self.status_bar.setStyleSheet("""
                        background-color: gray;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 6px;
                    """)
                    self.status_bar.enable_animation(False)
                return




        # Determine simulator state and update image + status bar
        if self.motion_state == 2:
            # In motion
            self.image.setPixmap(self.get_pixmap("motion-on"))
            self.status_bar.setText("In Operation")
            self.status_bar.setStyleSheet("""
                background-color: red;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            """)
            self.status_bar.enable_animation(True)
        elif self.motion_state == 1:
            if self.ramp_state == 0:
                # Ramp is moving
                self.image.setPixmap(self.get_pixmap("ramping"))
                self.status_bar.setText("RAMPING")
                self.status_bar.setStyleSheet("""
                    background-color: yellow;
                    color: black;
                    padding: 8px 16px;
                    border-radius: 6px;
                """)
                self.status_bar.enable_animation(True)

            elif self.ramp_state == 1:
                # Ramp Up
                self.image.setPixmap(self.get_pixmap("ramping"))
                self.status_bar.setText("Ramp Up")
                self.status_bar.setStyleSheet("""
                    background-color: purple;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                """)
                self.status_bar.enable_animation(False)

            elif self.ramp_state == 2:
                # Ramp Down
                self.image.setPixmap(self.get_pixmap("at-home"))
                self.status_bar.setText("Standby")
                self.status_bar.setStyleSheet("""
                    background-color: green;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                """)
                self.status_bar.enable_animation(False)

            else:
                # Fallback
                self.image.setPixmap(self.get_pixmap("at-home"))
                self.status_bar.setText("Standby")
                self.status_bar.setStyleSheet("""
                    background-color: gray;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                """)
                self.status_bar.enable_animation(False)



        else:
            # Default fallback
            self.image.setPixmap(self.get_pixmap("motion-on"))
            self.status_bar.setText("Unknown State")
            self.status_bar.setStyleSheet("""
                background-color: gray;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            """)
            self.status_bar.enable_animation(False)



    def update_state(self, motion, ramp):
        self.motion_state = motion
        self.ramp_state = ramp
        self.set_offline(False)

        if ramp == 0:
            if not self.ramp_disconnect_timer.isActive():
                self.ramp_disconnect_timer.start(15000)
        else:
            self.ramp_disconnect_timer.stop()
            self.ramp_disconnected = False

        self.update_display()



    def activate_ramp_disconnected(self):
        if not self.ramp_disconnected:
            self.ramp_disconnected = True
            self.force_label_override = True
            self.update_display()
            self.ramp_disconnect_label_timer.start(5000)  # Only start label timer once


    def clear_ramp_label_override(self):
        self.force_label_override = False
        self.update_display()


    def set_offline(self, offline=True):
        # Only update if there's an actual change
        if self.offline != offline:
            self.offline = offline

            if offline:
                self.overlay.show()
                self.overlay.raise_()
                self.status_bar.enable_animation(False)

                # Remove drop shadow for offline
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

