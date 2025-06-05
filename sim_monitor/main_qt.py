import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QGridLayout,
    QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QSizePolicy
)
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtCore import Qt

from simulator_card import SimulatorCard
from utils.serial_handler_qt import start_serial_thread, set_debug_mode, stop_serial_thread

NUM_SIMULATORS = 12
COLUMNS = 6

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlightSafety Simulator Monitor")
        self.setStyleSheet("background-color: white;")
        self.debug_mode = True
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

        # ---------- HEADER ----------
        header_frame = QFrame()
        header_frame.setMinimumHeight(90)
        header_frame.setMaximumHeight(90)
        header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_frame.setStyleSheet("background-color: #081D33; padding: 0px 40px;")

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        logo_label = QLabel()
        logo_pixmap = QPixmap("images/FlightSafety_Logo-white.png")
        logo_pixmap = logo_pixmap.scaledToHeight(120, Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setStyleSheet("margin-left: 10px;")

        self.mode_label = QLabel("MODE: DEBUG")
        self.mode_label.setFont(QFont("Arial", 12))
        self.mode_label.setStyleSheet("color: white;")

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(QIcon.fromTheme("settings"))
        self.settings_btn.setStyleSheet("background-color: transparent; border: none;")
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.clicked.connect(self.toggle_serial_mode)

        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        header_layout.addWidget(self.mode_label)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.settings_btn)

        # ---------- SIMULATOR GRID ----------
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(10, 10, 10, 130)

        for i in range(NUM_SIMULATORS):
            sim_id = i + 1
            sim_card = SimulatorCard(sim_id=sim_id)
            self.simulator_cards[sim_id] = sim_card
            row, col = divmod(i, COLUMNS)
            grid.addWidget(sim_card, row, col)

        # ---------- ASSEMBLE ----------
        main_layout.addWidget(header_frame)
        main_layout.addLayout(grid)

        # Start serial monitoring
        set_debug_mode(self.debug_mode)
        start_serial_thread(
            self.simulator_cards,
            update_sim_fn=self.update_simulator_state,
            mark_offline_fn=self.set_simulator_offline
        )

    def update_simulator_state(self, sim_id, motion, ramp):
        if sim_id in self.simulator_cards:
            self.simulator_cards[sim_id].update_state(motion, ramp)

    def set_simulator_offline(self, sim_id, offline=True):
        if sim_id in self.simulator_cards:
            self.simulator_cards[sim_id].set_offline(offline)

    def toggle_serial_mode(self):
        self.debug_mode = not self.debug_mode
        set_debug_mode(self.debug_mode)
        self.mode_label.setText(f"MODE: {'DEBUG' if self.debug_mode else 'LIVE'}")
        for sim in self.simulator_cards.values():
            sim.set_offline(True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.is_fullscreen:
                self.showNormal()
            else:
                self.showFullScreen()
            self.is_fullscreen = not self.is_fullscreen
        elif event.key() == Qt.Key_Escape:
            self.close()

        
    def closeEvent(self, event):
        print("🔁 Window closed, exiting...")
        stop_serial_thread()
        QApplication.quit()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()  # Let OS handle fullscreen — no manual geometry
    sys.exit(app.exec_())
