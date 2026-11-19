"""Queryable material library and material-entry form."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .dialogs import MaterialDialog


class MaterialsPage(QWidget):
    COLUMNS = ("Name", "Category", "E (MPa)", "Poisson ratio", "Density (kg/m³)", "Yield (MPa)")

    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        title = QLabel("Material library")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Values are design inputs. Verify them against the specification for your actual material.")
        subtitle.setObjectName("Muted")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or category")
        self.search.textChanged.connect(self.refresh)
        self.table = QTableWidget(0, len(self.COLUMNS) + 1)
        self.table.setHorizontalHeaderLabels(("ID",) + self.COLUMNS)
        self.table.setColumnHidden(0, True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.material_rows = {}
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.add_button = QPushButton("Add material")
        self.add_button.setObjectName("Primary")
        self.edit_button = QPushButton("Edit selected")
        self.refresh_button = QPushButton("Refresh")
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.refresh_button.clicked.connect(self.refresh)
        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.add_button)
        top.addWidget(self.edit_button)
        top.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        self.material_rows = {}
        if not self.database.connected:
            return
        try:
            rows = self.database.list_materials(self.search.text())
        except Exception as exc:
            QMessageBox.warning(self, "Could not load materials", str(exc))
            return
        for row in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            self.material_rows[int(row["id"])] = row
            values = (
                row["id"], row["name"], row["category"],
                f"{float(row['youngs_modulus_mpa']):,.3f}",
                f"{float(row['poisson_ratio']):.4f}",
                f"{float(row['density_kg_m3']):,.1f}",
                f"{float(row['yield_strength_mpa']):,.2f}",
            )
            for col, value in enumerate(values):
                self.table.setItem(index, col, QTableWidgetItem(str(value)))

    def _edit(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Select a material", "Choose a material row to edit.")
            return
        row_index = selected[0].row()
        material_id = int(self.table.item(row_index, 0).text())
        material = self.material_rows.get(material_id)
        if material is None:
            return
        dialog = MaterialDialog(material, self)
        if dialog.exec() != MaterialDialog.DialogCode.Accepted:
            return
        name, category, modulus, poisson, density, yield_strength, notes = dialog.values()
        if not name or not category:
            QMessageBox.warning(self, "Missing material details", "Enter a name and category.")
            return
        try:
            self.database.update_material(
                material_id, name, category, modulus, poisson, density, yield_strength, notes
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could not update material", str(exc))

    def _add(self) -> None:
        if not self.database.connected:
            QMessageBox.information(self, "Connect database", "Configure the MySQL connection first.")
            return
        dialog = MaterialDialog(parent=self)
        if dialog.exec() != MaterialDialog.DialogCode.Accepted:
            return
        name, category, modulus, poisson, density, yield_strength, notes = dialog.values()
        if not name or not category:
            QMessageBox.warning(self, "Missing material details", "Enter a name and category.")
            return
        try:
            self.database.add_material(name, category, modulus, poisson, density, yield_strength, notes)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could not add material", str(exc))
