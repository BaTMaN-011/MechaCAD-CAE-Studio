"""Project list and selection page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .dialogs import ProjectDialog


class ProjectsPage(QWidget):
    def __init__(self, database, on_selected, parent=None):
        super().__init__(parent)
        self.database = database
        self.on_selected = on_selected
        title = QLabel("Projects")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Keep sketches, materials, and analysis runs together by assignment.")
        subtitle.setObjectName("Muted")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Project", "Description"])
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.new_button = QPushButton("New project")
        self.new_button.setObjectName("Primary")
        self.edit_button = QPushButton("Edit selected")
        self.delete_button = QPushButton("Delete selected")
        self.refresh_button = QPushButton("Refresh")
        self.new_button.clicked.connect(self._create)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.refresh_button.clicked.connect(self.refresh)
        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)

    def refresh(self, select_id: int | None = None) -> None:
        self.table.setRowCount(0)
        if not self.database.connected:
            return
        try:
            rows = self.database.list_projects()
        except Exception as exc:
            QMessageBox.warning(self, "Could not load projects", str(exc))
            return
        for row in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            for col, value in enumerate((row["id"], row["name"], row["description"])):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                self.table.setItem(index, col, item)
            if select_id is not None and int(row["id"]) == select_id:
                self.table.selectRow(index)
        if self.table.rowCount() and not self.table.selectedItems():
            self.table.selectRow(0)
        self._selection_changed()

    def _selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            self.on_selected(None)
            return
        row = selected[0].row()
        project_id = int(self.table.item(row, 0).text())
        self.on_selected({"id": project_id, "name": self.table.item(row, 1).text()})

    def _create(self) -> None:
        if not self.database.connected:
            QMessageBox.information(self, "Connect database", "Configure the MySQL connection first.")
            return
        dialog = ProjectDialog(parent=self)
        if dialog.exec() != ProjectDialog.DialogCode.Accepted:
            return
        name, description = dialog.values()
        if not name:
            QMessageBox.warning(self, "Project name required", "Enter a name for this project.")
            return
        try:
            project_id = self.database.create_project(name, description)
            self.refresh(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "Could not save project", str(exc))

    def _edit(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        project_id = int(self.table.item(row, 0).text())
        project = {
            "id": project_id,
            "name": self.table.item(row, 1).text(),
            "description": self.table.item(row, 2).text(),
        }
        dialog = ProjectDialog(project, self)
        if dialog.exec() != ProjectDialog.DialogCode.Accepted:
            return
        name, description = dialog.values()
        if not name:
            QMessageBox.warning(self, "Project name required", "Enter a name for this project.")
            return
        try:
            self.database.update_project(project_id, name, description)
            self.refresh(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "Could not update project", str(exc))

    def _delete(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        project_id = int(self.table.item(row, 0).text())
        project_name = self.table.item(row, 1).text()
        answer = QMessageBox.question(
            self, "Delete project",
            f"Delete {project_name} and its sketches, BOM, and analysis records?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.delete_project(project_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could not delete project", str(exc))
