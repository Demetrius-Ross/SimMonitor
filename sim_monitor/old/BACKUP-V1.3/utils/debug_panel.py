# utils/debug_panel.py
import pathlib
import json
import time
import sqlite3

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QHBoxLayout, QCheckBox, QFrame, QSpinBox
)
from PyQt5.QtCore import Qt

from utils.layout_io import CFG_DIR, list_layout_files, read_layout
from utils.db import get_conn


class DebugControlPanel(QDialog):
    """
    DB-backed Debug Control Panel
    -----------------------------------
    • Simulator list comes from MOST RECENT config JSON.
    • Writes real-time into SQLite DB.
    • Supports Hybrid Mode (Option C):
         - Freeze Background Service Updates
         - Local DB overrides
    """

    def __init__(self, parent, simulator_cards, serial_debug_hook=None):
        super().__init__(parent)
        self.setWindowTitle("Debug Control Panel (DB-Backed)")
        self.setMinimumWidth(520)

        self.simulator_cards = simulator_cards
        self.serial_debug_hook = serial_debug_hook  # legacy hook (optional)

        self.layout_path = self._get_latest_layout()
        self.sim_map, self.layout_map = read_layout(self.layout_path)

        # Convert sim IDs from str → int
        self.sim_ids = sorted(int(k) for k in self.sim_map.keys())

        # Freeze flag (kept in DB)
        self.freeze_updates = False

        main = QVBoxLayout(self)

        # ======================================================
        # RECEIVER CONTROL SECTION
        # ======================================================
        receiver_frame = QFrame()
        receiver_layout = QHBoxLayout(receiver_frame)

        receiver_label = QLabel("<b>Receiver Controls</b>")
        receiver_label.setAlignment(Qt.AlignLeft)

        btn_r_online = QPushButton("Set Receiver ONLINE")
        btn_r_offline = QPushButton("Set Receiver OFFLINE")

        btn_r_online.clicked.connect(lambda: self.set_receiver_online(True))
        btn_r_offline.clicked.connect(lambda: self.set_receiver_online(False))

        receiver_layout.addWidget(receiver_label)
        receiver_layout.addWidget(btn_r_online)
        receiver_layout.addWidget(btn_r_offline)

        main.addWidget(receiver_frame)

        # ======================================================
        # FREEZE BACKGROUND SERVICE
        # ======================================================
        freeze_row = QHBoxLayout()
        self.freeze_checkbox = QCheckBox("Freeze Background Service Updates")
        self.freeze_checkbox.stateChanged.connect(self.toggle_freeze_updates)
        freeze_row.addWidget(self.freeze_checkbox)
        main.addLayout(freeze_row)

        # ======================================================
        # SIMULATOR CONTROL GRID
        # ======================================================
        grid_frame = QFrame()
        grid = QGridLayout(grid_frame)
        grid.setSpacing(8)

        header = QLabel("<b>Simulator Controls</b>")
        header.setAlignment(Qt.AlignCenter)
        main.addWidget(header)

        row = 0
        for sid in self.sim_ids:
            name = self.sim_map[str(sid)]

            label = QLabel(f"{sid}: {name}")
            label.setStyleSheet("font-weight: bold;")

            # Buttons for this sim
            btn_motion_start = QPushButton("Start Motion")
            btn_motion_stop  = QPushButton("Stop Motion")

            btn_ramp0 = QPushButton("Ramp = 0")
            btn_ramp1 = QPushButton("Ramp = 1")
            btn_ramp2 = QPushButton("Ramp = 2")

            btn_online  = QPushButton("Mark Sender ONLINE")
            btn_offline = QPushButton("Mark Sender OFFLINE")

            # Connect handlers
            btn_motion_start.clicked.connect(lambda _, s=sid: self.sim_start_motion(s))
            btn_motion_stop.clicked.connect(lambda _, s=sid: self.sim_stop_motion(s))

            btn_ramp0.clicked.connect(lambda _, s=sid: self.set_ramp(s, 0))
            btn_ramp1.clicked.connect(lambda _, s=sid: self.set_ramp(s, 1))
            btn_ramp2.clicked.connect(lambda _, s=sid: self.set_ramp(s, 2))

            btn_online.clicked.connect(lambda _, s=sid: self.set_sender_online(s, True))
            btn_offline.clicked.connect(lambda _, s=sid: self.set_sender_online(s, False))

            # Layout row
            grid.addWidget(label, row, 0)
            grid.addWidget(btn_motion_start, row, 1)
            grid.addWidget(btn_motion_stop,  row, 2)
            grid.addWidget(btn_ramp0, row, 3)
            grid.addWidget(btn_ramp1, row, 4)
            grid.addWidget(btn_ramp2, row, 5)
            grid.addWidget(btn_online,  row, 6)
            grid.addWidget(btn_offline, row, 7)

            row += 1

        main.addWidget(grid_frame)

    # ==================================================================
    # LAYOUT HELPERS
    # ==================================================================
    def _get_latest_layout(self):
        files = list_layout_files()
        if not files:
            raise RuntimeError("No layout config files found in configs/ folder.")
        return files[-1]  # newest timestamped config

    # ==================================================================
    # RECEIVER CONTROLS
    # ==================================================================
    def set_receiver_online(self, online: bool):
        now = int(time.time())
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE system_status
            SET receiver_online=?, last_seen=?
            WHERE id=1
        """, (1 if online else 0, now))

        conn.commit()
        conn.close()

    # ==================================================================
    # FREEZE BACKGROUND SERVICE
    # ==================================================================
    def toggle_freeze_updates(self):
        """When freeze is ON, we mark receiver as offline in DB.
        This prevents the GUI from responding to real updates."""
        enabled = self.freeze_checkbox.isChecked()
        self.freeze_updates = enabled

        # Mark receiver offline → GUI treats all sims as offline
        self.set_receiver_online(not enabled)

    # ==================================================================
    # SENDER ONLINE/OFFLINE (Option 1 behavior)
    # ==================================================================
    def set_sender_online(self, sim_id, online: bool):
        conn = get_conn()
        cur = conn.cursor()

        if online:
            # Mark online = 1, but keep motion/ramp untouched
            cur.execute("""
                UPDATE simulators
                SET online=1, last_update_ts=?
                WHERE sim_id=?
            """, (int(time.time()), sim_id))

        else:
            # Option 1:
            # Sender OFFLINE → mark offline + close motion session
            now = int(time.time())

            # 1. Close active motion session if exists
            cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
            row = cur.fetchone()
            if row:
                start = row[0]
                duration = now - start
                cur.execute("""
                    INSERT INTO motion_sessions (sim_id, start_ts, end_ts, duration_sec)
                    VALUES (?, ?, ?, ?)
                """, (sim_id, start, now, duration))
                cur.execute("DELETE FROM active_motion WHERE sim_id=?", (sim_id,))

            # 2. Mark sender offline (but preserve motion/ramp)
            cur.execute("""
                UPDATE simulators
                SET online=0
                WHERE sim_id=?
            """, (sim_id,))

        conn.commit()
        conn.close()

    # ==================================================================
    # MOTION CONTROLS
    # ==================================================================
    def sim_start_motion(self, sim_id):
        now = int(time.time())
        conn = get_conn()
        cur = conn.cursor()

        # Mark simulator online if freeze is off
        cur.execute("""
            UPDATE simulators
            SET motion_state=2, last_update_ts=?, online=1
            WHERE sim_id=?
        """, (now, sim_id))

        # Start new active motion if not already active
        cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT OR REPLACE INTO active_motion (sim_id, start_ts)
                VALUES (?, ?)
            """, (sim_id, now))

        conn.commit()
        conn.close()

    def sim_stop_motion(self, sim_id):
        now = int(time.time())
        conn = get_conn()
        cur = conn.cursor()

        # Update motion state
        cur.execute("""
            UPDATE simulators
            SET motion_state=1, last_update_ts=?, online=1
            WHERE sim_id=?
        """, (now, sim_id))

        # Close motion session if active
        cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
        row = cur.fetchone()
        if row:
            start = row[0]
            duration = now - start
            cur.execute("""
                INSERT INTO motion_sessions (sim_id, start_ts, end_ts, duration_sec)
                VALUES (?, ?, ?, ?)
            """, (sim_id, start, now, duration))
            cur.execute("DELETE FROM active_motion WHERE sim_id=?", (sim_id,))

        conn.commit()
        conn.close()

    # ==================================================================
    # RAMP CONTROLS
    # ==================================================================
    def set_ramp(self, sim_id, ramp_value):
        now = int(time.time())
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE simulators
            SET ramp_state=?, last_update_ts=?, online=1
            WHERE sim_id=?
        """, (ramp_value, now, sim_id))

        conn.commit()
        conn.close()
