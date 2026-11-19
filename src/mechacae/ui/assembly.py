"""Assembly bill of materials and estimated mass roll-up."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QAbstractItemView, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..domain.assembly import summarize_assembly
from .dialogs import ComponentDialog


class AssemblyPage(QWidget):
    HEADERS = ("ID", "Part number", "Component", "Material", "Qty", "Unit mass (kg)", "Total mass (kg)", "Volume / unit (mm³)")

    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.rows: dict[int, dict] = {}
        title = QLabel("Assembly & bill of materials")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Organize component quantities and estimate assembly mass from material density or entered unit mass."
        )
        subtitle.setObjectName("Muted")
        self.project_label = QLabel("Choose a project to begin.")
        self.project_label.setObjectName("Muted")
        self.total_label = QLabel("Assembly mass: —")
        self.total_label.setObjectName("Metric")
        self.quality_label = QLabel("Mass coverage: —")
        self.quality_label.setObjectName("Muted")
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.add_button = QPushButton("Add component")
        self.add_button.setObjectName("Primary")
        self.edit_button = QPushButton("Edit selected")
        self.delete_button = QPushButton("Remove selected")
        self.refresh_button = QPushButton("Refresh")
        self.export_button = QPushButton("Export CSV")
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.refresh_button.clicked.connect(self.refresh)
        self.export_button.clicked.connect(self._export_csv)
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.export_button)
        buttons.addStretch(1)
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.project_label)
        layout.addWidget(self.total_label)
        layout.addWidget(self.quality_label)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        self.rows.clear()
        project = self.get_active_project()
        if not project:
            self.project_label.setText("Choose a project to begin.")
            self.total_label.setText("Assembly mass: —")
            self.quality_label.setText("Mass coverage: —")
            return
        self.project_label.setText(f"Project: {project['name']}")
        if not self.database.connected:
            return
        try:
            components = self.database.list_components(project["id"])
        except Exception as exc:
            QMessageBox.warning(self, "Could not load assembly", str(exc))
            return
        for component in components:
            component_id = int(component["id"])
            self.rows[component_id] = component
            quantity = int(component["quantity"])
            unit_mass = float(component["unit_mass_kg"])
            extended_mass = quantity * unit_mass
            values = (
                component_id, component["part_number"], component["name"],
                component["material_name"] or "Unspecified", quantity,
                f"{unit_mass:.6f}", f"{extended_mass:.6f}",
                f"{float(component['volume_mm3']):,.3f}",
            )
            index = self.table.rowCount()
            self.table.insertRow(index)
            for col, value in enumerate(values):
                self.table.setItem(index, col, QTableWidgetItem(str(value)))
        summary = summarize_assembly(components)
        self.total_label.setText(
            f"Assembly mass: {summary.total_mass_kg:,.6f} kg  •  "
            f"{summary.line_items} line items  •  {summary.total_quantity} total units"
        )
        self.quality_label.setText(
            f"Mass values present on {summary.lines_with_mass}/{summary.line_items} lines; "
            f"materials selected on {summary.lines_with_material}/{summary.line_items} lines. "
            + (summary.warnings[0] if summary.warnings else "Review BOM values before using them for a real build.")
        )

    def _selected_component(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return self.rows.get(int(item.text())) if item else None

    def _export_csv(self) -> None:
        project = self.get_active_project()
        if not project:
            QMessageBox.information(self, "Project required", "Select a project before exporting its assembly.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export assembly bill of materials", "assembly-bom.csv", "CSV spreadsheet (*.csv)"
        )
        if not path:
            return
        try:
            output = Path(path).with_suffix(".csv")
            with output.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(("Project", project["name"]))
                writer.writerow(("Part number", "Component", "Material", "Quantity",
                                 "Unit mass kg", "Total mass kg", "Volume per unit mm³", "Notes"))
                for row in self.rows.values():
                    quantity = int(row["quantity"])
                    unit_mass = float(row["unit_mass_kg"])
                    writer.writerow((
                        row["part_number"], row["name"], row["material_name"] or "Unspecified",
                        quantity, unit_mass, quantity * unit_mass, float(row["volume_mm3"]), row["notes"],
                    ))
            QMessageBox.information(self, "Assembly exported", f"Saved BOM to:\n{output}")
        except OSError as exc:
            QMessageBox.critical(self, "Could not export assembly", str(exc))

    def _add(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        dialog = ComponentDialog(self.database, parent=self)
        if dialog.exec() != ComponentDialog.DialogCode.Accepted:
            return
        part_no, name, material_id, qty, volume, unit_mass, notes = dialog.values()
        if not part_no or not name:
            QMessageBox.warning(self, "Missing component details", "Enter a part number and component name.")
            return
        try:
            self.database.save_component(
                project["id"], part_no, name, material_id, qty, volume, unit_mass, notes
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could not add component", str(exc))

    def _edit(self) -> None:
        project = self.get_active_project()
        component = self._selected_component()
        if not project or not component:
            QMessageBox.information(self, "Select a component", "Choose an assembly row to edit.")
            return
        dialog = ComponentDialog(self.database, component, self)
        if dialog.exec() != ComponentDialog.DialogCode.Accepted:
            return
        part_no, name, material_id, qty, volume, unit_mass, notes = dialog.values()
        if not part_no or not name:
            QMessageBox.warning(self, "Missing component details", "Enter a part number and component name.")
            return
        try:
            self.database.save_component(
                project["id"], part_no, name, material_id, qty, volume, unit_mass, notes,
                component_id=int(component["id"]),
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could not update component", str(exc))

    def _delete(self) -> None:
        project = self.get_active_project()
        component = self._selected_component()
        if not project or not component:
            return
        answer = QMessageBox.question(
            self, "Remove assembly component",
            f"Remove {component['part_number']} — {component['name']} from this project?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.delete_component(int(component["id"]), int(project["id"]))
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could not remove component", str(exc))
