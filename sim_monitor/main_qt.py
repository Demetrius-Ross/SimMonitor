import subprocess, os, sys, inspect
import pprint, pathlib
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QGridLayout,
    QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QSizePolicy,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QCheckBox,
    QMenu, QMessageBox, QFileDialog                              
)
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtCore import Qt, QTimer, QTime, QDate, QCoreApplication, pyqtSlot

from edit_layout_dialog import EditLayoutDialog
from utils.simulator_map import SIMULATOR_MAP, SIMULATOR_LAYOUT

from simulator_card import SimulatorCard
from utils.serial_handler_qt import start_serial_thread, set_debug_mode, stop_serial_thread

from utils.config_io import load_cfg, save_cfg
from utils.layout_io import write_layout, read_layout       


NUM_SIMULATORS = 12
COLUMNS = 6
#os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"]= "0"
#os.environ["QT_SCALE_FACTOR"] = "1"
#QCoreApplication.setAttribute(Qt.AA_DisableHighDpiScaling)

class GearButton(QPushButton):
    def __init__(self, icon: QIcon, parent=None, *,scale: float = 1.0):
        super().__init__(parent)
        self.setIcon(icon)
        self.scale = scale
        self.setFixedSize(int(20*scale), int(22*scale))
        self.setCursor(Qt.PointingHandCursor)
        
        # CSS for normal / hover / pressed
        font_px = int(20*scale)
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
    """General-settings popup (now without Operator-name)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        #self.setFixedWidth(380)

        # --- Example option --------------------
        form = QFormLayout()
        self.debug_check = QCheckBox("Enable debug mode on launch")
        form.addRow("", self.debug_check)

        # --- Buttons ---------------------------
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # --- Main layout -----------------------
        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(buttons)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlightSafety Simulator Monitor")
        self.setStyleSheet("background-color: white;")
        screen_h = QApplication.primaryScreen().size().height()
        self.ui_scale = max(2, screen_h / 1080) # CHANGE SCALE HERE
        self.is_fullscreen = True
        self.simulator_cards = {}


        # -- Central Widget --
        central_widget = QWidget()
        central_widget.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)

        self.cfg = load_cfg()
        self.debug_mode = self.cfg.get("debug_mode", True)


        # ---------- HEADER ----------
        bar_h = int(90 * self.ui_scale)
        header_frame = QFrame()
        header_frame.setMinimumHeight(bar_h)
        header_frame.setMaximumHeight(bar_h)
        #header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_frame.setStyleSheet("background-color: #081D33; padding: 0px 40px;")

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.logo_label = QLabel()
        logo_pixmap = QPixmap("images/fs-logo.png")
        pmap = int(120* self.ui_scale)
        logo_pixmap = logo_pixmap.scaledToHeight(pmap, Qt.SmoothTransformation)
        self.logo_label.setPixmap(logo_pixmap)
        #logo_label.setStyleSheet("margin-left: 10px;")
        self.logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        font_size1 = int(12*self.ui_scale)
        self.mode_label = QLabel("MODE: DEBUG")
        self.mode_label.setFont(QFont("Arial", font_size1))
        self.mode_label.setStyleSheet("color: white;")

        font_size2 = int(25*self.ui_scale)
        self.clock_label = QLabel()
        clock_font = QFont("Arial", font_size2, QFont.Normal, italic=True)
        self.clock_label.setFont(clock_font)
        self.clock_label.setStyleSheet("color:white;")
        self.clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.date_label = QLabel()
        date_font = QFont("Arial", font_size2, QFont.Normal, italic=True)
        self.date_label.setFont(date_font)
        self.date_label.setStyleSheet("color:white;")
        self.date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # --- SETTINGS (gear) button ----------------
        self.settings_btn = QPushButton()
        gear_icon = QIcon.fromTheme("preferences-system")
        if gear_icon.isNull():
            self.settings_btn = GearButton(QIcon(), self, scale=self.ui_scale)
            self.settings_btn.setText("⚙")
        else:
            self.settings_btn = GearButton(gear_icon, self, scale=self.ui_scale)

        self.settings_btn.clicked.connect(self.open_settings)
        
        header_layout.addWidget(self.logo_label)
        header_layout.addStretch()
        header_layout.addWidget(self.mode_label)
        
        #header_layout.addSpacing(0)
        header_layout.addWidget(self.clock_label)
        header_layout.addWidget(self.date_label)
        #header_layout.addSpacing(1)
        
        #header_layout.addSpacing(0)
        header_layout.addWidget(self.settings_btn)

        # ---------- SIMULATOR GRID ----------
        self.grid_layout = QGridLayout()
        grid_size = int(8*self.ui_scale)
        self.grid_layout.setSpacing(grid_size)
        margin = int(10*self.ui_scale)
        bottom = int(130*self.ui_scale)
        self.grid_layout.setContentsMargins(margin, margin, margin, bottom)

        for sim_id, (col, row) in SIMULATOR_LAYOUT.items():
            name = SIMULATOR_MAP.get(sim_id, f"SIM-{sim_id}")
            sim_card = SimulatorCard(sim_id, name)
            self.simulator_cards[sim_id] = sim_card
            self.grid_layout.addWidget(sim_card, row, col)

        # ---------- ASSEMBLE ----------
        main_layout.addWidget(header_frame)
        main_layout.addLayout(self.grid_layout)
        QTimer.singleShot(0, self.rebuild_simulator_grid)


        self.update_datetime()
        timer = QTimer(self)
        timer.timeout.connect(self.update_datetime)
        timer.start(1000)

        # Start serial monitoring
        self.apply_debug_mode(self.debug_mode, persist=False)

        start_serial_thread(
            self.simulator_cards,
            update_sim_fn=self.update_simulator_state,
            mark_offline_fn=self.set_simulator_offline
        )

    @pyqtSlot(int, int, int)
    def update_simulator_state(self, sim_id, motion, ramp):
        if sim_id in self.simulator_cards:
            self.simulator_cards[sim_id].update_state(motion, ramp)

    @pyqtSlot(int, bool)
    def set_simulator_offline(self, sim_id, offline=True):
        if sim_id in self.simulator_cards:
            self.simulator_cards[sim_id].set_offline(offline)

    def toggle_serial_mode(self):
        self.apply_debug_mode(not self.debug_mode)

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

        elif key == Qt.Key_S:           # open settings via keyboard
            self.open_settings()

        elif key == Qt.Key_R:           # restart GUI via keyboard
            self.restart_gui()
        
    def closeEvent(self, event):
        print("Window closed, exiting...")
        stop_serial_thread()
        QApplication.quit()
        event.accept()

    def restart_gui(self):
        """Soft-restart: stop serial thread, relaunch this script."""
        stop_serial_thread()
        python = sys.executable
        script = os.path.abspath(inspect.getfile(sys.modules['__main__']))
        print("Restarting GUI…")
        # Launch new process, then quit this one.
        subprocess.Popen([python, script])
        QApplication.quit()

    def open_settings(self):
        """Gear-button handler – shows a small pop-up menu."""
        menu = QMenu(self)

        # 1) Edit Simulator Layout …
        menu.addAction("Edit Simulator Layout…", self.edit_layout_dialog)

        # 2) General Settings …
        menu.addAction("General Settings…", self.general_settings_dialog)

        # (optional) About
        menu.addSeparator()
        menu.addAction("About", lambda: QMessageBox.information(
            self, "About", "Sim Monitor v1.0\n© FlightSafety International")
        )

        # Show the menu right under / beside the gear
        pos = self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomRight())
        menu.exec_(pos)

    def general_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.debug_check.setChecked(self.debug_mode)

        if dlg.exec_():
            new_state = dlg.debug_check.isChecked()
            if new_state != self.debug_mode:
                # Persist + Relaunch
                self.apply_debug_mode(new_state)     # writes cfg + sets label
                self.restart_gui()                   # full restart for serial thread

    # --------------------------------------------------------
    def edit_layout_dialog(self):
        """
        Launch the Edit-Layout dialog.
        If the user clicks  ‘Save Config’  the dialog returns Accepted
        and we (a) write a JSON file in  configs/ ,
        (b) update the global SIMULATOR_MAP / SIMULATOR_LAYOUT,
        (c) rebuild the grid.
        If they click  ‘Cancel’  nothing happens.
        """
        dlg = EditLayoutDialog(
            SIMULATOR_MAP.copy(),
            SIMULATOR_LAYOUT.copy(),
            self
        )

        if dlg.exec_():                               # Save Config pressed
            # 1. read back the edited data
            new_map, new_layout = dlg.get_new_layout()

            # 2. save to configs/<timestamp>.json
            if dlg._save_requested:
                filename = write_layout(new_map, new_layout)
                print(f"💾 Layout saved as configs/{filename}")

            # 3. update the in-memory dicts
            SIMULATOR_MAP.clear();     SIMULATOR_MAP.update(new_map)
            SIMULATOR_LAYOUT.clear();  SIMULATOR_LAYOUT.update(new_layout)

            # 4. rebuild the visible grid
            self.rebuild_simulator_grid()

    def rebuild_simulator_grid(self):
        # Remove old cards from layout + dict
        for sim_card in self.simulator_cards.values():
            sim_card.setParent(None)
        self.simulator_cards.clear()

        # Re-add based on updated SIMULATOR_LAYOUT
        rows = max(r for (_, r) in SIMULATOR_LAYOUT.values()) + 1
        cols = max(c for (c, _) in SIMULATOR_LAYOUT.values()) + 1
        self.grid_layout.setRowStretch(rows, 1)
        self.grid_layout.setColumnStretch(cols, 1)

        for sim_id, (col, row) in SIMULATOR_LAYOUT.items():
            name = SIMULATOR_MAP.get(sim_id, f"SIM-{sim_id}")
            sim_card = SimulatorCard(sim_id, name, scale=self.ui_scale)
            self.simulator_cards[sim_id] = sim_card
            self.grid_layout.addWidget(sim_card, row, col)

    def apply_debug_mode(self, enabled: bool, *, persist=True):
        """Update global serial handler, UI label, and config."""
        self.debug_mode = enabled
        set_debug_mode(enabled)                       # serial_handler_qt
        self.mode_label.setVisible(enabled)
        self.mode_label.setText("MODE: DEBUG" if enabled else "")

        if persist:
            self.cfg["debug_mode"] = enabled
            save_cfg(self.cfg)

    def on_load_click(self):
        start_dir = str((pathlib.Path(__file__).parent / "../configs").resolve())
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", start_dir, "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            sim_map, layout_map = read_layout(pathlib.Path(file_path))
            # update internal refs
            self.sim_map = sim_map
            self.layout_map = layout_map
            # refresh spin boxes & fields
            rows = max(r for (_, r) in layout_map.values()) + 1
            cols = max(c for (c, _) in layout_map.values()) + 1
            self.row_spin.setValue(rows)
            self.col_spin.setValue(cols)
            self.build_name_fields()
        except Exception as ex:
            QMessageBox.warning(self, "Load Failed", f"Could not load file:\n{ex}")

    def update_datetime(self):
        now=QTime.currentTime()
        today=QDate.currentDate()
        date_str = today.toString("ddd dd MMM yyyy")
        time_str=now.toString("HH:mm:ss AP")
        self.date_label.setText(date_str)
        self.clock_label.setText(time_str)




def persist_simulator_map():
    file_path = pathlib.Path(__file__).parent / "utils" / "simulator_map.py"
    with file_path.open("w") as f:
        f.write("# simulator_map.py (auto-generated)\n")
        f.write("SIMULATOR_MAP = ")
        pprint.pprint(SIMULATOR_MAP, stream=f)
        f.write("\nSIMULATOR_LAYOUT = ")
        pprint.pprint(SIMULATOR_LAYOUT, stream=f)
        f.write("\n\ndef get_simulator_name(device_id):\n")
        f.write("    return SIMULATOR_MAP.get(device_id, f'Unknown-Sim-{device_id}')\n")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()  # Let OS handle fullscreen — no manual geometry
    sys.exit(app.exec_())
    
