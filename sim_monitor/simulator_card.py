import time

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFrame,
    QGraphicsDropShadowEffect, QStackedLayout
)
from PyQt5.QtGui import (
    QPixmap, QFont, QRegion, QPainterPath, QPainter, QColor, QBrush
)
from PyQt5.QtCore import Qt, QRectF, QTimer


SIM_IMAGES = {
    "motion-on": "images/FINAL-SIM-UP-ICE.png",
    "ramping": "images/FINAL-RAMP-UP-ICE.png",
    "at-home": "images/FINAL-SIM-DOWN-ICE.png",
    "offline": "images/FINAL-SIM-DOWN-ICE.png",

    # Ramp disconnected variants
    "motion-on-no-ramp": "images/FINAL-SIM-UP-NO-RAMP.png",
    "at-home-no-ramp": "images/FINAL-SIM-DOWN-NO-RAMP.png",
}


class AnimatedStatusBar(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = 0
        self.animation_enabled = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_offset)
        self._timer.setInterval(60)  # ~30 FPS

    def enable_animation(self, enable: bool = True):
        self.animation_enabled = enable
        if enable:
            self._timer.start()
        else:
            self._timer.stop()
            self.update()

    def _update_offset(self):
        self.offset = (self.offset + 2) % 20
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if not self.animation_enabled:
            return

        painter = QPainter(self)
        painter.setOpacity(0.30)
        brush = QBrush(QColor("white"))
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
    """
    DB-backed card with:
      • Online/offline overlay
      • Motion + ramp states
      • Ramp disconnect logic
      • Motion history (current + last session)
    """
    def __init__(self, sim_id, name=None, *, scale: float = 1.0):
        super().__init__()

        self.sim_id = sim_id
        self.name = name or f"SIM-{sim_id}"
        self.scale = scale

        # DB-driven state
        self.motion_state = 0
        self.ramp_state = 0
        self.offline = True

        # Ramp disconnect logic
        self.ramp_disconnect_timer = QTimer(self)
        self.ramp_disconnect_timer.setSingleShot(True)
        self.ramp_disconnect_timer.timeout.connect(self.activate_ramp_disconnected)

        self.ramp_disconnected = False
        self.force_label_override = False

        self.ramp_disconnect_label_timer = QTimer(self)
        self.ramp_disconnect_label_timer.setSingleShot(True)
        self.ramp_disconnect_label_timer.timeout.connect(self.clear_ramp_label_override)

        # Motion history (from DB)
        self.in_motion = False
        self.motion_start_ts = None
        self.last_motion_end = None
        self.last_motion_duration = None

        # Overall size
        self.setFixedSize(int(310 * self.scale), int(450 * self.scale))

        # Main layout
        self.stack = QStackedLayout(self)
        self.card_container = QWidget()
        self.stack.addWidget(self.card_container)

        outer_layout = QVBoxLayout(self.card_container)
        outer_layout.setContentsMargins(
            int(10 * self.scale),
            int(10 * self.scale),
            int(10 * self.scale),
            int(10 * self.scale),
        )
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
        self.card.setMinimumHeight(int(430 * self.scale))
        self.card.setMaximumHeight(int(430 * self.scale))

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(
            int(12 * self.scale),
            int(12 * self.scale),
            int(12 * self.scale),
            int(12 * self.scale),
        )
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
        self.image.setFixedHeight(int(295 * self.scale))
        self.image.setStyleSheet("padding-top: 10px;")
        self.image.setPixmap(self.get_pixmap("offline"))
        card_layout.addWidget(self.image)
        
        # Motion history label
        self.motion_label = QLabel("No motion recorded yet")
        self.motion_label.setAlignment(Qt.AlignCenter)
        #self.motion_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.motion_label.setFont(QFont("Arial", int(16 * self.scale), QFont.Bold))
        #self.motion_label.setStyleSheet("color: #555;")
        card_layout.addWidget(self.motion_label)

        outer_layout.addWidget(self.card)

        # Status bar
        self.status_bar = AnimatedStatusBar("DISCONNECTED")
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setFont(QFont("Arial", int(16 * self.scale), QFont.Bold))
        self.status_bar.setStyleSheet("""
            background-color: #bbb;
            color: black;
            padding: 8px 6px;
            border-radius: 6px;
        """)
        card_layout.addWidget(self.status_bar)



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
        self.update_motion_label()

    # ------------------------------------------------------------------
    # Geometry / overlay mask
    # ------------------------------------------------------------------
    def apply_overlay_mask(self):
        visible_rect = QRectF(self.overlay.rect())
        path = QPainterPath()
        path.addRoundedRect(visible_rect, self.overlay_radius, self.overlay_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.overlay.setMask(region)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Ensure the card fills the full expected space
        self.card.setFixedHeight(int(430 * self.scale))
        self.overlay.setGeometry(0, 0, self.card.width(), self.card.height())
        self.apply_overlay_mask()

    def adjust_image_height_for_history(self):
        """Shrink the image if motion history exists; full size if none yet."""
        if (self.in_motion and self.motion_start_ts) or \
        (self.last_motion_end and self.last_motion_duration):
            # Has current or historical motion → shrink
            self.image.setFixedHeight(int(300 * self.scale))
        else:
            # No motion recorded yet → full height
            self.image.setFixedHeight(int(325 * self.scale))

    # ------------------------------------------------------------------
    # DB → UI entry point
    # ------------------------------------------------------------------
    def update_from_db(
        self,
        *,
        motion: int,
        ramp: int,
        online: bool,
        in_motion: bool,
        motion_start_ts,
        last_end_ts,
        last_duration,
    ):
        """
        Main entry point used by MainWindow.refresh_from_db().
        """
        self.motion_state = motion
        self.ramp_state = ramp
        self.in_motion = bool(in_motion)
        self.motion_start_ts = motion_start_ts
        self.last_motion_end = last_end_ts
        self.last_motion_duration = last_duration

        # Only run ramp timers if we're online; offline state trumps everything.
        if online:
            if ramp == 0:
                if not self.ramp_disconnect_timer.isActive():
                    self.ramp_disconnect_timer.start(15000)  # 15s ramp timeout
            else:
                self.ramp_disconnect_timer.stop()
                self.ramp_disconnected = False
                self.force_label_override = False

        # This also updates display
        self.set_offline(not online)
        self.update_motion_label()

    # ------------------------------------------------------------------
    # Ramp disconnect logic
    # ------------------------------------------------------------------
    def activate_ramp_disconnected(self):
        if not self.ramp_disconnected:
            self.ramp_disconnected = True
            self.force_label_override = True
            self.update_display()
            # After 5s, drop the "Ramp Disconnected" text and fall back
            self.ramp_disconnect_label_timer.start(5000)

    def clear_ramp_label_override(self):
        self.force_label_override = False
        self.update_display()

    # ------------------------------------------------------------------
    def get_pixmap(self, key: str) -> QPixmap:
        path = SIM_IMAGES.get(key)
        if path:
            return QPixmap(path).scaled(
                int(330 * self.scale),
                int(330 * self.scale),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        return QPixmap()

    # ------------------------------------------------------------------
    # Main visual state machine
    # ------------------------------------------------------------------
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
            self.status_bar.enable_animation(False)
            self.overlay.show()
            self.overlay.raise_()
            return

        self.overlay.hide()

        # RAMP DISCONNECTED VISUALS
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
                # Fallback label after 5s, based on motion
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

        # NORMAL STATES
        if self.motion_state == 2:
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
            # motion_state == 0 or unknown
            self.image.setPixmap(self.get_pixmap("at-home"))
            self.status_bar.setText("Idle / Not in Motion")
            self.status_bar.setStyleSheet("""
                background-color: gray;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            """)
            self.status_bar.enable_animation(False)

    # ------------------------------------------------------------------
    # Motion history text
    # ------------------------------------------------------------------
    def update_motion_label(self):
        if self.in_motion and self.motion_start_ts:
            elapsed = max(0, int(time.time()) - int(self.motion_start_ts))
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            start_local = time.strftime("%H:%M:%S", time.localtime(self.motion_start_ts))
            self.motion_label.setText(
                f"In motion for {h:02d}:{m:02d}:{s:02d}\n"
                f"Started at {start_local}"
            )

        else:
            if self.last_motion_end and self.last_motion_duration:
                h, rem = divmod(int(self.last_motion_duration), 3600)
                m, s = divmod(rem, 60)
                end_local = time.strftime("%H:%M:%S", time.localtime(self.last_motion_end))
                self.motion_label.setText(
                    f"Last in motion at {end_local}\n"
                    f"Duration {h:02d}:{m:02d}:{s:02d}"
                )
            else:
                self.motion_label.setText("")

        # Adjust image height after every motion label update
        self.adjust_image_height_for_history()



    # ------------------------------------------------------------------
    # Offline / online transitions
    # ------------------------------------------------------------------
    def set_offline(self, offline: bool = True):
        self.offline = offline

        if offline:
            self.overlay.show()
            self.overlay.raise_()
            self.status_bar.enable_animation(False)
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
