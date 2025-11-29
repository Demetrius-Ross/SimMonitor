# edit_layout_dialog.py  (full class, ready to replace your current one)

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox,
    QScrollArea, QWidget, QGridLayout, QLineEdit, QLabel, QVBoxLayout,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
import pathlib
from utils.layout_io import read_layout

class EditLayoutDialog(QDialog):
    """Popup to edit simulator grid size and names."""
    def __init__(self, sim_map: dict, layout_map: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Simulator Layout")
        self.resize(600, 500)

        self.sim_map = sim_map          # id -> name
        self.layout_map = layout_map    # id -> (col,row)

        # ---------- grid size controls ----------
        form = QFormLayout()
        self.row_spin = QSpinBox(); self.row_spin.setRange(1, 10)
        self.col_spin = QSpinBox(); self.col_spin.setRange(1, 10)

        current_rows = max(r for (_, r) in layout_map.values()) + 1
        current_cols = max(c for (c, _) in layout_map.values()) + 1
        self.row_spin.setValue(current_rows)
        self.col_spin.setValue(current_cols)

        form.addRow("Rows:", self.row_spin)
        form.addRow("Columns:", self.col_spin)

        # ---------- dynamic name grid ----------
        self.dynamic_area = QScrollArea()
        self.dynamic_area.setWidgetResizable(True)
        self._names_container = QWidget()
        self._name_grid = QGridLayout(self._names_container)
        self._name_grid.setAlignment(Qt.AlignTop)
        self.dynamic_area.setWidget(self._names_container)

        # fill initial fields
        self.build_name_fields()
        self.row_spin.valueChanged.connect(self.build_name_fields)
        self.col_spin.valueChanged.connect(self.build_name_fields)

        # ---------- buttons ----------
        buttons = QDialogButtonBox()
        self.ok_btn     = buttons.addButton("OK",           QDialogButtonBox.ApplyRole)
        self.save_btn   = buttons.addButton("Save Config",  QDialogButtonBox.AcceptRole)
        self.load_btn   = buttons.addButton("Load Config…", QDialogButtonBox.ActionRole)
        self.cancel_btn = buttons.addButton("Cancel",       QDialogButtonBox.RejectRole)

        self.ok_btn.clicked.connect(self.on_ok_clicked)
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.load_btn.clicked.connect(self.on_load_click)
        self.cancel_btn.clicked.connect(self.reject)

        # ---------- main layout (add everything) ----------
        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(self.dynamic_area, 1)
        main.addWidget(buttons)

        # flags
        self._loaded_from_file = False
        self._save_requested   = False

    # -------------------------------------------------
    def build_name_fields(self):
        while self._name_grid.count():
            item = self._name_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self.row_spin.value()
        cols = self.col_spin.value()
        idx = 1
        for r in range(rows):
            for c in range(cols):
                label = QLabel(f"ID {idx}:")
                edit  = QLineEdit(self.sim_map.get(idx, ""))
                edit.setObjectName(f"edit_{idx}")
                self._name_grid.addWidget(label, r*2, c)
                self._name_grid.addWidget(edit,  r*2+1, c)
                idx += 1

    # -------------------------------------------------
    def on_ok_clicked(self):
        self._save_requested = False
        self.accept()

    def on_save_clicked(self):
        self._save_requested = True
        self.accept()

    def on_load_click(self):
        start_dir = str((pathlib.Path(__file__).parent / "../configs").resolve())
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", start_dir, "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            sim_map, layout_map = read_layout(pathlib.Path(file_path))
            self.sim_map = sim_map
            self.layout_map = layout_map
            self._loaded_from_file = True

            rows = max(r for (_, r) in layout_map.values()) + 1
            cols = max(c for (c, _) in layout_map.values()) + 1
            self.row_spin.setValue(rows)
            self.col_spin.setValue(cols)
            self.build_name_fields()

            self._save_requested = False
            self.accept()
        except Exception as ex:
            QMessageBox.warning(self, "Load Failed", f"Could not load file:\n{ex}")

    # -------------------------------------------------
    def get_new_layout(self):
        if getattr(self, "_loaded_from_file", False):
            return self.sim_map, self.layout_map

        self.build_name_fields()

        rows = self.row_spin.value()
        cols = self.col_spin.value()
        new_sim_map, new_layout = {}, {}
        idx = 1
        for r in range(rows):
            for c in range(cols):
                edit = self._names_container.findChild(QLineEdit, f"edit_{idx}")
                name = edit.text().strip() if edit else ""
                new_sim_map[idx] = name or f"SIM-{idx}"
                new_layout[idx]  = (c, r)
                idx += 1
        return new_sim_map, new_layout
