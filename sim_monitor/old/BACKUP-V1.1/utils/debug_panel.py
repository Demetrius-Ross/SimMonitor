# debug_panel.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QGridLayout,
    QCheckBox, QWidget, QHBoxLayout, QFrame
)
from PyQt5.QtCore import Qt, QTimer

class DebugControlPanel(QDialog):
    """
    A control panel for testing GUI behavior without real ESP traffic.
    Allows:
    • Force online/offline
    • Inject fake DATA or HEARTBEAT signals
    • Simulate disconnect toggles
    """

    def __init__(self, parent, sim_cards, serial_debug):
        super().__init__(parent)

        self.setWindowTitle("Debug Control Panel")
        self.setMinimumWidth(600)
        self.sim_cards = sim_cards
        self.serial_debug = serial_debug   # debug interface

        layout = QVBoxLayout(self)
        title = QLabel("<h2>Debug Control Panel</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- GRID OF SIM CONTROLS ----------------
        grid = QGridLayout()
        row = 0

        for sim_id, card in sim_cards.items():
            sim_frame = QFrame()
            sim_layout = QHBoxLayout(sim_frame)
            sim_label = QLabel(f"<b>Sim {sim_id}</b>")
            sim_label.setFixedWidth(80)

            # Buttons
            btn_online = QPushButton("Force Online")
            btn_online.clicked.connect(lambda _, sid=sim_id: self.force_online(sid))

            btn_offline = QPushButton("Force Offline")
            btn_offline.clicked.connect(lambda _, sid=sim_id: self.force_offline(sid))

            btn_data = QPushButton("Send Fake DATA")
            btn_data.clicked.connect(lambda _, sid=sim_id: self.send_fake_data(sid))

            btn_hb = QPushButton("Send Fake HB")
            btn_hb.clicked.connect(lambda _, sid=sim_id: self.send_fake_heartbeat(sid))

            toggle_disc = QCheckBox("Auto-Disconnect")
            toggle_disc.stateChanged.connect(
                lambda state, sid=sim_id: self.toggle_auto_disconnect(sid, state == Qt.Checked)
            )

            # Add to row
            sim_layout.addWidget(sim_label)
            sim_layout.addWidget(btn_online)
            sim_layout.addWidget(btn_offline)
            sim_layout.addWidget(btn_data)
            sim_layout.addWidget(btn_hb)
            sim_layout.addWidget(toggle_disc)

            grid.addWidget(sim_frame, row, 0)
            row += 1

        layout.addLayout(grid)

        # ----------- GLOBAL BUTTONS -------------
        btn_all_off = QPushButton("Set ALL Offline")
        btn_all_off.clicked.connect(self.all_offline)

        btn_resume = QPushButton("Resume Normal Debug Flow")
        btn_resume.clicked.connect(self.resume_normal)

        btn_snapshot = QPushButton("Print State Snapshot")
        btn_snapshot.clicked.connect(self.print_snapshot)

        bottom = QHBoxLayout()
        bottom.addWidget(btn_all_off)
        bottom.addWidget(btn_resume)
        bottom.addWidget(btn_snapshot)
        layout.addLayout(bottom)

    # ---------------- Control Functions ----------------

    def force_online(self, sid):
        self.sim_cards[sid].set_offline(False)
        print(f"[DEBUG] Forced SIM {sid} ONLINE")

    def force_offline(self, sid):
        self.sim_cards[sid].set_offline(True)
        print(f"[DEBUG] Forced SIM {sid} OFFLINE")

    def send_fake_data(self, sid):
        self.serial_debug.inject_fake_data(sid)
        print(f"[DEBUG] Injected FAKE DATA for SIM {sid}")

    def send_fake_heartbeat(self, sid):
        self.serial_debug.inject_fake_heartbeat(sid)
        print(f"[DEBUG] Injected FAKE HEARTBEAT for SIM {sid}")

    def toggle_auto_disconnect(self, sid, enabled):
        self.serial_debug.toggle_disconnect(sid, enabled)
        print(f"[DEBUG] SIM {sid} auto-disconnect = {enabled}")

    def all_offline(self):
        for sid in self.sim_cards:
            self.sim_cards[sid].set_offline(True)
        print("[DEBUG] All simulators forced OFFLINE")

    def resume_normal(self):
        self.serial_debug.reset_to_normal()
        print("[DEBUG] Debug mode returned to NORMAL FLOW")

    def print_snapshot(self):
        print("\n===== SIM SNAPSHOT =====")
        for sid, card in self.sim_cards.items():
            print(f"SIM {sid}: offline={card.offline}, motion={card.motion_state}, ramp={card.ramp_state}")
        print("========================\n")