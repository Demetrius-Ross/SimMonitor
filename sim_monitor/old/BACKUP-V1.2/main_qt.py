import subprocess, os, sys, inspect
import pprint, pathlib
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QGridLayout,
    QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QSizePolicy,
    QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
    QMenu, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtCore import Qt, QTimer, QTime, QDate, pyqtSlot

from edit_layout_dialog import EditLayoutDialog
from utils.simulator_map import SIMULATOR_MAP, SIMULATOR_LAYOUT

from simulator_card import SimulatorCard
from utils.serial_handler_qt import (
    start_serial_thread, set_debug_mode, stop_serial_thread, serial_debug
)

from utils.config_io import load_cfg, save_cfg
from utils.layout_io import write_layout, read_layout
from utils.debug_panel import DebugControlPanel


NUM_SIMULATORS = 12
COLUMNS = 6


# ===============================================================
#   GEAR BUTTON STYLE
# ===============================================================
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


# ===============================================================
#   SETTINGS DIALOG
# ===============================================================
class SettingsDialog(QDialog):
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


# ===============================================================
#   MAIN WINDOW
# ===============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlightSafety Simulator Monitor")
        self.setStyleSheet("background-color: white;")

        screen_h = QApplication.primaryScreen().size().height()
        self.ui_scale = max(0.5, screen_h / 1080)
        self.is_fullscreen = True
        self.simulator_cards = {}

        central_widget = QWidget()
        central_widget.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.cfg = load_cfg()
        self.debug_mode = self.cfg.get("debug_mode", True)

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

        # Mode Label
        font_size1 = int(12 * self.ui_scale)
        self.mode_label = QLabel("MODE: DEBUG")
        self.mode_label.setFont(QFont("Arial", font_size1))
        self.mode_label.setStyleSheet("color: white;")

        # Receiver Status Label (IMPORTANT)
        self.receiver_label = QLabel("RECEIVER: UNKNOWN")
        self.receiver_label.setFont(QFont("Arial", font_size1))
        self.receiver_label.setStyleSheet("color: yellow; font-weight: bold;")

        # Clock & Date
        font_size2 = int(25 * self.ui_scale)
        self.clock_label = QLabel()
        self.clock_label.setFont(QFont("Arial", font_size2, QFont.Normal, italic=True))
        self.clock_label.setStyleSheet("color:white;")
        self.clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.date_label = QLabel()
        self.date_label.setFont(QFont("Arial", font_size2, QFont.Normal, italic=True))
        self.date_label.setStyleSheet("color:white;")
        self.date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Settings gear
        self.settings_btn = QPushButton()
        gear_icon = QIcon.fromTheme("preferences-system")
        if gear_icon.isNull():
            self.settings_btn = GearButton(QIcon(), self, scale=self.ui_scale)
            self.settings_btn.setText("⚙")
        else:
            self.settings_btn = GearButton(gear_icon, self, scale=self.ui_scale)
        self.settings_btn.clicked.connect(self.open_settings)

        # Header Assembly
        header_layout.addWidget(self.logo_label)
        header_layout.addSpacing(int(20 * self.ui_scale))
        header_layout.addWidget(self.project_label)
        header_layout.addStretch()
        header_layout.addWidget(self.mode_label)
        header_layout.addWidget(self.receiver_label)    # <-- NEW
        header_layout.addWidget(self.clock_label)
        header_layout.addWidget(self.date_label)
        header_layout.addWidget(self.settings_btn)

        # ---------------------------------------------------------
        # SIMULATOR GRID
        # ---------------------------------------------------------
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(int(8 * self.ui_scale))
        self.grid_layout.setContentsMargins(
            int(10 * self.ui_scale), int(10 * self.ui_scale),
            int(10 * self.ui_scale), int(130 * self.ui_scale)
        )

        for sim_id, (col, row) in SIMULATOR_LAYOUT.items():
            name = SIMULATOR_MAP.get(sim_id, f"SIM-{sim_id}")
            sim_card = SimulatorCard(sim_id, name, scale=self.ui_scale)
            self.simulator_cards[sim_id] = sim_card
            self.grid_layout.addWidget(sim_card, row, col)

        main_layout.addWidget(header_frame)
        main_layout.addLayout(self.grid_layout)

        QTimer.singleShot(0, self.rebuild_simulator_grid)

        # Clock Timer
        self.update_datetime()
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self.update_datetime)
        clock_timer.start(1000)

        # Start Serial Thread (IMPORTANT: receiver_status_fn added)
        self.apply_debug_mode(self.debug_mode, persist=False)

        start_serial_thread(
            self.simulator_cards,
            update_sim_fn=self.update_simulator_state,
            mark_offline_fn=self.set_simulator_offline,
            receiver_status_fn=self.set_receiver_status  # <-- CRITICAL
        )

    # ===========================================================
    #   CALLBACKS FROM SERIAL THREAD
    # ===========================================================
    @pyqtSlot(int, int, int)
    def update_simulator_state(self, sim_id, motion, ramp):
        if sim_id in self.simulator_cards:
            self.simulator_cards[sim_id].update_state(motion, ramp)

    @pyqtSlot(int, bool)
    def set_simulator_offline(self, sim_id, offline=True):
        if sim_id in self.simulator_cards:
            self.simulator_cards[sim_id].set_offline(offline)

    @pyqtSlot(bool)
    def set_receiver_status(self, online):
        if online:
            self.receiver_label.setText("RECEIVER: ONLINE")
            self.receiver_label.setStyleSheet("color: lightgreen; font-weight: bold;")
        else:
            self.receiver_label.setText("RECEIVER: OFFLINE")
            self.receiver_label.setStyleSheet("color: red; font-weight: bold;")

    # ===========================================================
    #   KEY EVENTS & WINDOW EVENTS
    # ===========================================================
    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_F11:
            self.showNormal() if self.is_fullscreen else self.showFullScreen()
            self.is_fullscreen = not self.is_fullscreen

        elif key == Qt.Key_Escape:
            self.close()

        elif key == Qt.Key_S:
            self.open_settings()

        elif key == Qt.Key_R:
            self.restart_gui()

    def closeEvent(self, event):
        stop_serial_thread()
        QApplication.quit()
        event.accept()

    def restart_gui(self):
        stop_serial_thread()
        python = sys.executable
        script = os.path.abspath(inspect.getfile(sys.modules['__main__']))
        subprocess.Popen([python, script])
        QApplication.quit()

    # ===========================================================
    #   SETTINGS MENU + DEBUG PANEL
    # ===========================================================
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
            self, "About", "Sim Monitor v2.0\nFlightSafety International")
        )

        pos = self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomRight())
        menu.exec_(pos)

    # ===========================================================
    #   SETTINGS & GRID MGMT
    # ===========================================================
    def general_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.debug_check.setChecked(self.debug_mode)

        if dlg.exec_():
            new_state = dlg.debug_check.isChecked()
            if new_state != self.debug_mode:
                self.apply_debug_mode(new_state)
                self.restart_gui()

    def edit_layout_dialog(self):
        dlg = EditLayoutDialog(
            SIMULATOR_MAP.copy(),
            SIMULATOR_LAYOUT.copy(),
            self
        )

        if dlg.exec_():
            new_map, new_layout = dlg.get_new_layout()

            if dlg._save_requested:
                filename = write_layout(new_map, new_layout)
                print(f"Saved layout: configs/{filename}")

            SIMULATOR_MAP.clear()
            SIMULATOR_MAP.update(new_map)

            SIMULATOR_LAYOUT.clear()
            SIMULATOR_LAYOUT.update(new_layout)

            self.rebuild_simulator_grid()

    def rebuild_simulator_grid(self):
        for sim in self.simulator_cards.values():
            sim.setParent(None)
        self.simulator_cards.clear()

        rows = max(r for (_, r) in SIMULATOR_LAYOUT.values()) + 1
        cols = max(c for (c, _) in SIMULATOR_LAYOUT.values()) + 1

        self.grid_layout.setRowStretch(rows, 1)
        self.grid_layout.setColumnStretch(cols, 1)

        for sim_id, (col, row) in SIMULATOR_LAYOUT.items():
            sim_label = SIMULATOR_MAP.get(sim_id, f"SIM-{sim_id}")
            sim_card = SimulatorCard(sim_id, sim_label, scale=self.ui_scale)
            self.simulator_cards[sim_id] = sim_card
            self.grid_layout.addWidget(sim_card, row, col)

    # ===========================================================
    #   DEBUG MODE SWITCHING
    # ===========================================================
    def apply_debug_mode(self, enabled: bool, *, persist=True):
        self.debug_mode = enabled
        set_debug_mode(enabled)
        self.mode_label.setVisible(enabled)
        self.mode_label.setText("MODE: DEBUG" if enabled else "")

        if persist:
            self.cfg["debug_mode"] = enabled
            save_cfg(self.cfg)

    # ===========================================================
    #   CLOCK
    # ===========================================================
    def update_datetime(self):
        now = QTime.currentTime()
        today = QDate.currentDate()

        self.date_label.setText(today.toString("ddd dd MMM yyyy"))
        self.clock_label.setText(now.toString("HH:mm:ss AP"))


# ===========================================================
#   MAIN ENTRY
# ===========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec_())