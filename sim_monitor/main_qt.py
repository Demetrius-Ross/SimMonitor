import os
import sys
import inspect
import subprocess
import pprint
import pathlib
import time

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QGridLayout,
    QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QSizePolicy,
    QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
    QMenu, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtCore import Qt, QTimer, QTime, QDate

from edit_layout_dialog import EditLayoutDialog
from simulator_card import SimulatorCard

from utils.config_io import load_cfg, save_cfg
from utils.layout_io import write_layout, read_layout, CFG_DIR, list_layout_files
from utils.db import get_conn, init_db
from utils.debug_panel import DebugControlPanel
from utils.serial_handler_qt import set_debug_mode, serial_debug


NUM_SIMULATORS = 12   # upper bound; actual sims come from layout JSON


class GearButton(QPushButton):
    def __init__(self, icon: QIcon, parent=None, *, scale: float = 1.0):
        super().__init__(parent)
        self.setIcon(icon)
        self.scale = scale
        self.setFixedSize(int(20 * scale), int(22 * scale))
        self.setCursor(Qt.PointingHandCursor)

        font_px = int(20 * scale)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: white;
                font-size: {font_px}px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: {font_px}px;
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.30);
                border-radius: {font_px}px;
            }}
        """)


class SettingsDialog(QDialog):
    """General-settings popup."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)

        form = QFormLayout()
        self.debug_check = QCheckBox("Enable debug mode on launch")
        form.addRow("", self.debug_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlightSafety Simulator Monitor")
        self.setStyleSheet("background-color: white;")

        screen_h = QApplication.primaryScreen().size().height()
        self.ui_scale = max(0.5, screen_h / 1080)
        self.is_fullscreen = True

        self.simulator_cards = {}
        self.sim_map = {}
        self.layout_map = {}
        self.layout_path = None

        # App config (includes debug_mode and active_layout)
        self.cfg = load_cfg()
        self.debug_mode = self.cfg.get("debug_mode", True)

        # Init DB
        init_db()

        # ---- central widget ----
        central = QWidget()
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central.setLayout(main_layout)

        # ---------------------------------------------------------
        # HEADER BAR
        # ---------------------------------------------------------
        bar_h = int(90 * self.ui_scale)

        header_frame = QFrame()
        header_frame.setMinimumHeight(bar_h)
        header_frame.setMaximumHeight(bar_h)
        header_frame.setStyleSheet("background-color: #081D33; padding: 0px 40px;")

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Logo
        self.logo_label = QLabel()
        logo_pixmap = QPixmap("images/fs-logo.png")
        logo_pixmap = logo_pixmap.scaledToHeight(int(120 * self.ui_scale), Qt.SmoothTransformation)
        self.logo_label.setPixmap(logo_pixmap)
        self.logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Project Title
        self.project_label = QLabel("Simulator Monitor")
        title_font = QFont("Eurostile", int(32 * self.ui_scale), QFont.Bold)
        if not QFont().exactMatch():
            title_font = QFont("Orbitron", int(32 * self.ui_scale), QFont.Bold)
        self.project_label.setFont(title_font)
        self.project_label.setStyleSheet("color: white; letter-spacing: 4px;")
        self.project_label.setAlignment(Qt.AlignVCenter)

        # Debug mode text
        self.mode_label = QLabel("MODE: DEBUG")
        self.mode_label.setFont(QFont("Arial", int(12 * self.ui_scale)))
        self.mode_label.setStyleSheet("color: white;")

        # Receiver status text
        self.receiver_label = QLabel("Receiver: UNKNOWN")
        self.receiver_label.setFont(QFont("Arial", int(12 * self.ui_scale)))
        self.receiver_label.setStyleSheet("color: #FFD700;")  # yellowish
        self.receiver_label.setAlignment(Qt.AlignVCenter)

        # Clock & Date
        clock_font = QFont("Arial", int(25 * self.ui_scale), QFont.Normal, italic=True)

        self.clock_label = QLabel()
        self.clock_label.setFont(clock_font)
        self.clock_label.setStyleSheet("color: white;")
        self.clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.date_label = QLabel()
        self.date_label.setFont(clock_font)
        self.date_label.setStyleSheet("color: white;")
        self.date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Settings / Gear button
        gear_icon = QIcon.fromTheme("preferences-system")
        if gear_icon.isNull():
            self.settings_btn = GearButton(QIcon(), self, scale=self.ui_scale)
            self.settings_btn.setText("⚙")
        else:
            self.settings_btn = GearButton(gear_icon, self, scale=self.ui_scale)
        self.settings_btn.clicked.connect(self.open_settings)

        # Header assembly
        header_layout.addWidget(self.logo_label)
        header_layout.addSpacing(int(20 * self.ui_scale))
        header_layout.addWidget(self.project_label)
        header_layout.addStretch()
        header_layout.addWidget(self.mode_label)
        header_layout.addWidget(self.receiver_label)
        header_layout.addWidget(self.clock_label)
        header_layout.addWidget(self.date_label)
        header_layout.addWidget(self.settings_btn)

        # ---------------------------------------------------------
        # SIMULATOR GRID
        # ---------------------------------------------------------
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(int(8 * self.ui_scale))
        margin = int(10 * self.ui_scale)
        bottom_margin = int(130 * self.ui_scale)
        self.grid_layout.setContentsMargins(margin, margin, margin, bottom_margin)

        main_layout.addWidget(header_frame)
        main_layout.addLayout(self.grid_layout)

        # Load layout mapping from config / latest JSON
        self.load_layout_from_cfg()
        self.rebuild_simulator_grid()

        # Clocks & DB refresh timers
        self.update_datetime()
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self.update_datetime)
        clock_timer.start(1000)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_from_db)
        self.refresh_timer.start(1000)

        # Apply debug mode
        self.apply_debug_mode(self.debug_mode, persist=False)

    # ---------------------------------------------------------
    #   LAYOUT HANDLING
    # ---------------------------------------------------------
    def load_layout_from_cfg(self):
        """Load sim_map + layout_map from active_layout in config.
        If missing, fall back to newest JSON file in configs/.
        """
        active_layout = self.cfg.get("active_layout")
        layout_path = None

        if active_layout:
            candidate = CFG_DIR / active_layout
            if candidate.exists():
                layout_path = candidate

        if layout_path is None:
            files = list_layout_files()
            if not files:
                QMessageBox.warning(
                    self,
                    "No Layouts",
                    "No layout JSON files found in configs/. Please create one via Edit Layout."
                )
                self.sim_map = {}
                self.layout_map = {}
                return
            layout_path = files[-1]
            # remember this as the active layout
            self.cfg["active_layout"] = layout_path.name
            save_cfg(self.cfg)

        self.layout_path = layout_path
        sim_map, layout_map = read_layout(layout_path)
        self.sim_map = sim_map
        self.layout_map = layout_map

    def rebuild_simulator_grid(self):
        # Clear existing widgets
        for card in self.simulator_cards.values():
            card.setParent(None)
        self.simulator_cards.clear()

        if not self.layout_map:
            return

        # Determine grid extents
        rows = max(r for (_, r) in self.layout_map.values()) + 1
        cols = max(c for (c, _) in self.layout_map.values()) + 1
        self.grid_layout.setRowStretch(rows, 1)
        self.grid_layout.setColumnStretch(cols, 1)

        # Rebuild from layout_map (keys are strings)
        for sid_str, (col, row) in self.layout_map.items():
            try:
                sim_id = int(sid_str)
            except ValueError:
                continue
            name = self.sim_map.get(sid_str, f"SIM-{sim_id}")
            card = SimulatorCard(sim_id, name, scale=self.ui_scale)
            self.simulator_cards[sim_id] = card
            self.grid_layout.addWidget(card, row, col)

    # ---------------------------------------------------------
    #   TIME / CLOCK
    # ---------------------------------------------------------
    def update_datetime(self):
        now = QTime.currentTime()
        today = QDate.currentDate()
        self.date_label.setText(today.toString("ddd dd MMM yyyy"))
        self.clock_label.setText(now.toString("HH:mm:ss AP"))

    # ---------------------------------------------------------
    #   DB REFRESH
    # ---------------------------------------------------------
    def refresh_from_db(self):
        """Fetch latest state from SQLite and update cards + receiver label."""
        try:
            conn = get_conn()
            cur = conn.cursor()

            # Receiver status
            cur.execute("SELECT receiver_online FROM system_status WHERE id=1")
            row = cur.fetchone()
            receiver_online = bool(row[0]) if row else False

            if receiver_online:
                self.receiver_label.setText("Receiver: ONLINE")
                self.receiver_label.setStyleSheet("color: #00FF7F;")
            else:
                self.receiver_label.setText("Receiver: OFFLINE")
                self.receiver_label.setStyleSheet("color: #FF6347;")

            # Per-sim updates
            for sim_id, card in self.simulator_cards.items():

                # 1. Sim state
                cur.execute("""
                    SELECT motion_state, ramp_state, online, last_update_ts
                    FROM simulators
                    WHERE sim_id=?
                """, (sim_id,))
                s = cur.fetchone()
                if not s:
                    # never seen in DB → treat as offline
                    card.update_from_db(
                        motion=0,
                        ramp=0,
                        online=False,
                        in_motion=False,
                        motion_start_ts=None,
                        last_end_ts=None,
                        last_duration=None,
                    )
                    continue

                motion_state, ramp_state, online_flag, _ = s
                effective_online = bool(online_flag) and receiver_online

                # 2. Active motion record (optional)
                cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
                am = cur.fetchone()
                in_motion = am is not None
                motion_start_ts = am[0] if am else None

                # 3. Most recent historical motion session (optional)
                cur.execute("""
                    SELECT end_ts, duration_sec
                    FROM motion_sessions
                    WHERE sim_id=?
                    ORDER BY end_ts DESC
                    LIMIT 1
                """, (sim_id,))
                hist = cur.fetchone()
                last_end_ts = hist[0] if hist else None
                last_duration = hist[1] if hist else None

                # 4. Update the card
                card.update_from_db(
                    motion=motion_state,
                    ramp=ramp_state,
                    online=effective_online,
                    in_motion=in_motion,
                    motion_start_ts=motion_start_ts,
                    last_end_ts=last_end_ts,
                    last_duration=last_duration,
                )

            conn.close()
        except Exception as exc:
            print(f"[DB] refresh_from_db error: {exc}")


    # ---------------------------------------------------------
    #   DEBUG / SETTINGS
    # ---------------------------------------------------------
    def apply_debug_mode(self, enabled: bool, *, persist=True):
        self.debug_mode = enabled
        set_debug_mode(enabled)
        self.mode_label.setVisible(enabled)
        self.mode_label.setText("MODE: DEBUG" if enabled else "")

        if persist:
            self.cfg["debug_mode"] = enabled
            save_cfg(self.cfg)

    def open_debug_menu(self):
        dlg = DebugControlPanel(self, self.simulator_cards, serial_debug)
        dlg.exec_()

    def open_settings(self):
        menu = QMenu(self)

        menu.addAction("Edit Simulator Layout…", self.edit_layout_dialog)
        menu.addAction("General Settings…", self.general_settings_dialog)
        menu.addAction("Debug Control Panel…", self.open_debug_menu)

        menu.addSeparator()
        menu.addAction("About", lambda: QMessageBox.information(
            self, "About", "Sim Monitor v2.0\nFlightSafety International"
        ))

        pos = self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomRight())
        menu.exec_(pos)

    def general_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.debug_check.setChecked(self.debug_mode)

        if dlg.exec_():
            new_state = dlg.debug_check.isChecked()
            if new_state != self.debug_mode:
                self.apply_debug_mode(new_state)
                # no need to restart anymore – DB/threads are external

    def edit_layout_dialog(self):
        if not self.sim_map or not self.layout_map:
            # Try loading layout again if for some reason not present
            self.load_layout_from_cfg()

        dlg = EditLayoutDialog(
            self.sim_map.copy(),
            self.layout_map.copy(),
            self
        )

        if dlg.exec_():
            new_map, new_layout = dlg.get_new_layout()

            if dlg._save_requested:
                filename = write_layout(new_map, new_layout)
                print(f"💾 Layout saved as configs/{filename}")
                self.cfg["active_layout"] = filename
                save_cfg(self.cfg)
                self.layout_path = CFG_DIR / filename

            # Update in-memory maps (even if not saved)
            self.sim_map = new_map
            self.layout_map = new_layout

            self.rebuild_simulator_grid()

    # ---------------------------------------------------------
    #   WINDOW / KEY HANDLING
    # ---------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_F11:
            if self.is_fullscreen:
                self.showNormal()
            else:
                self.showFullScreen()
            self.is_fullscreen = not self.is_fullscreen

        elif key == Qt.Key_Escape:
            self.close()

        elif key == Qt.Key_S:
            self.open_settings()

    def closeEvent(self, event):
        QApplication.quit()
        event.accept()


def persist_simulator_map():
    """Kept for backward-compatibility; no longer used in DB-backed flow."""
    file_path = pathlib.Path(__file__).parent / "utils" / "simulator_map.py"
    with file_path.open("w") as f:
        f.write("# simulator_map.py (auto-generated)\n")
        f.write("SIMULATOR_MAP = {}\n")
        f.write("SIMULATOR_LAYOUT = {}\n")
        f.write("\n")
        f.write("def get_simulator_name(device_id):\n")
        f.write("    return f'Unknown-Sim-{device_id}'\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec_())
