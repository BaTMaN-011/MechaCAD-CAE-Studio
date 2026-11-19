"""Simple editable 2D parametric sketch page."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPen, QBrush, QPainter
from ..domain.geometry import (
    entity_metrics, export_dxf, export_svg, import_dxf, import_svg, sketch_totals,
)
from PySide6.QtWidgets import (
    QFileDialog, QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .dialogs import GeometryDialog


class SketchScene(QGraphicsScene):
    def drawBackground(self, painter: QPainter, rect) -> None:
        painter.fillRect(rect, QColor("#0c141b"))
        grid = 25
        left = int(rect.left()) - (int(rect.left()) % grid)
        top = int(rect.top()) - (int(rect.top()) % grid)
        minor = QPen(QColor("#182631"), 0)
        major = QPen(QColor("#203542"), 0)
        x = left
        while x < rect.right():
            painter.setPen(major if x % (grid * 4) == 0 else minor)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += grid
        y = top
        while y < rect.bottom():
            painter.setPen(major if y % (grid * 4) == 0 else minor)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += grid


class SketchPage(QWidget):
    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        title = QLabel("2D sketch")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Create and move basic profiles. The grid and dimensions use millimetres.")
        subtitle.setObjectName("Muted")
        self.project_label = QLabel("Choose a project to begin.")
        self.project_label.setObjectName("Muted")
        self.properties = QLabel("No sketch geometry yet.")
        self.properties.setObjectName("Muted")

        self.scene = SketchScene(self)
        self.scene.setSceneRect(-250, -180, 1500, 1050)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.setBackgroundBrush(QBrush(QColor("#0c141b")))
        self.view.setMinimumHeight(420)

        self.rectangle_button = QPushButton("Add rectangle")
        self.rectangle_button.setObjectName("Primary")
        self.circle_button = QPushButton("Add circle")
        self.delete_button = QPushButton("Delete selected")
        self.save_button = QPushButton("Save sketch")
        self.import_svg_button = QPushButton("Import SVG")
        self.import_dxf_button = QPushButton("Import DXF")
        self.export_button = QPushButton("Export SVG")
        self.dxf_button = QPushButton("Export DXF")
        self.rectangle_button.clicked.connect(lambda: self._add_entity("rectangle"))
        self.circle_button.clicked.connect(lambda: self._add_entity("circle"))
        self.delete_button.clicked.connect(self._delete_selected)
        self.save_button.clicked.connect(self.save)
        self.import_svg_button.clicked.connect(lambda: self._import_vector("svg"))
        self.import_dxf_button.clicked.connect(lambda: self._import_vector("dxf"))
        self.export_button.clicked.connect(self._export_svg)
        self.dxf_button.clicked.connect(self._export_dxf)
        self.scene.selectionChanged.connect(self._update_properties)
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.rectangle_button)
        toolbar.addWidget(self.circle_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.import_svg_button)
        toolbar.addWidget(self.import_dxf_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.dxf_button)
        toolbar.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.project_label)
        layout.addWidget(self.properties)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)

    def _active(self):
        return self.get_active_project()

    def refresh(self) -> None:
        project = self._active()
        self.scene.clear()
        if not project:
            self.project_label.setText("Choose a project before drawing.")
            self._set_enabled(False)
            return
        self._set_enabled(self.database.connected)
        self.project_label.setText(f"Project: {project['name']}  •  drag shapes to position them")
        if not self.database.connected:
            return
        try:
            design = self.database.load_design(project["id"])
            if design:
                for entity in design.get("entities", []):
                    self._draw_entity(entity)
            self._update_properties()
        except Exception as exc:
            QMessageBox.warning(self, "Could not load sketch", str(exc))

    def _set_enabled(self, enabled: bool) -> None:
        for button in (self.rectangle_button, self.circle_button, self.delete_button, self.import_svg_button, self.import_dxf_button, self.export_button,
                            self.dxf_button, self.save_button):
            button.setEnabled(enabled)

    def _add_entity(self, kind: str) -> None:
        dialog = GeometryDialog(kind, self)
        if dialog.exec() == GeometryDialog.DialogCode.Accepted:
            self._draw_entity(dialog.values())

    def _draw_entity(self, entity: dict) -> None:
        x, y = float(entity.get("x", 0)), float(entity.get("y", 0))
        width, height = float(entity.get("width", 100)), float(entity.get("height", 100))
        pen = QPen(QColor("#61d6b0"), 2)
        brush = QBrush(QColor(48, 152, 125, 45))
        if entity.get("kind") == "circle":
            item = QGraphicsEllipseItem(0, 0, width, height)
        else:
            item = QGraphicsRectItem(0, 0, width, height)
        item.setPen(pen)
        item.setBrush(brush)
        item.setPos(x, y)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        item.setData(0, dict(entity))
        self.scene.addItem(item)

    def _delete_selected(self) -> None:
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)
        self._update_properties()

    def _update_properties(self) -> None:
        selected = self.scene.selectedItems()
        try:
            if selected:
                entity = selected[0].data(0)
                metrics = entity_metrics(entity)
                name = entity.get("name", "Profile")
                self.properties.setText(
                    f"Selected: {name} • {metrics['kind']} • area {metrics['area_mm2']:,.2f} mm² • "
                    f"perimeter {metrics['perimeter_mm']:,.2f} mm"
                )
            else:
                totals = sketch_totals(self._entities())
                self.properties.setText(
                    f"Sketch total: {int(totals['entity_count'])} entities • "
                    f"{totals['area_mm2']:,.2f} mm² profile area • "
                    f"{totals['perimeter_mm']:,.2f} mm perimeter"
                )
        except Exception as exc:
            self.properties.setText(str(exc))

    def _import_vector(self, kind: str) -> None:
        suffix = "svg" if kind == "svg" else "dxf"
        path, _ = QFileDialog.getOpenFileName(
            self, f"Import {suffix.upper()} geometry", "", f"{suffix.upper()} drawing (*.{suffix})"
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8-sig" if kind == "dxf" else "utf-8")
            entities = import_svg(content) if kind == "svg" else import_dxf(content)
            if not entities:
                QMessageBox.information(
                    self, "No supported shapes",
                    "This importer reads untransformed rectangles and circles. Other drawing entities are skipped.",
                )
                return
            for entity in entities:
                self._draw_entity(entity)
            self._update_properties()
            QMessageBox.information(self, "Geometry imported", f"Added {len(entities)} shapes to the current sketch.")
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.critical(self, "Could not import drawing", str(exc))

    def _export_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export sketch drawing", "MechaCAD-sketch.svg", "SVG drawing (*.svg)"
        )
        if not path:
            return
        try:
            content = export_svg(self._entities())
            Path(path).with_suffix(".svg").write_text(content, encoding="utf-8")
            QMessageBox.information(self, "SVG exported", f"Saved drawing to:\n{Path(path).with_suffix('.svg')}")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not export sketch", str(exc))

    def _export_dxf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export sketch as DXF", "MechaCAD-sketch.dxf", "DXF drawing (*.dxf)"
        )
        if not path:
            return
        try:
            output = Path(path).with_suffix(".dxf")
            output.write_text(export_dxf(self._entities()), encoding="ascii")
            QMessageBox.information(self, "DXF exported", f"Saved drawing to:\n{output}")
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.critical(self, "Could not export DXF", str(exc))

    def _entities(self) -> list[dict]:
        entities = []
        for item in reversed(self.scene.items()):
            entity = item.data(0)
            if not isinstance(entity, dict):
                continue
            rect = item.rect()
            saved = dict(entity)
            saved.update({
                "x": round(item.pos().x(), 3),
                "y": round(item.pos().y(), 3),
                "width": round(rect.width(), 3),
                "height": round(rect.height(), 3),
            })
            entities.append(saved)
        return entities

    def save(self) -> None:
        project = self._active()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        try:
            self.database.save_design(project["id"], self._entities())
            QMessageBox.information(self, "Sketch saved", "The sketch is saved with this project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save sketch", str(exc))
