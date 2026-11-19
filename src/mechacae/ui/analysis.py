"""Truss model editor, solver workflow, and result visualization."""
from __future__ import annotations

from datetime import datetime
import csv
import json
from pathlib import Path

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QFileDialog, QAbstractItemView, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..domain.truss import Node, TrussElement, TrussInputError, TrussSolver


class TrussPlot(QWidget):
    """Simple undeformed/deformed wire view to make the model and result intuitive."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes: list[dict] = []
        self.elements: list[dict] = []
        self.results: dict | None = None
        self.setMinimumHeight(240)

    def set_model(self, nodes: list[dict], elements: list[dict], results: dict | None = None) -> None:
        self.nodes, self.elements, self.results = nodes, elements, results
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d151c"))
        if not self.nodes:
            painter.setPen(QColor("#91a2b3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Add nodes and members to preview the model")
            return
        xs = [float(row["x"]) for row in self.nodes]
        ys = [float(row["y"]) for row in self.nodes]
        dx, dy = max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0)
        pad = 38
        sx = (self.width() - 2 * pad) / dx
        sy = (self.height() - 2 * pad) / dy
        scale = min(sx, sy)
        origin_x = pad + (self.width() - 2 * pad - dx * scale) / 2
        origin_y = self.height() - pad - (self.height() - 2 * pad - dy * scale) / 2

        def point(x, y):
            return QPointF(origin_x + (x - min(xs)) * scale, origin_y - (y - min(ys)) * scale)

        displacements = self.results.get("nodes", []) if self.results else []
        max_disp = max((abs(r["displacement_x_mm"]) + abs(r["displacement_y_mm"]) for r in displacements), default=0)
        amplification = min(35.0, max(1.0, (dx + dy) * 0.06 / max(max_disp, 1e-9))) if self.results else 1.0
        for member in self.elements:
            a, b = int(member["start"]) - 1, int(member["end"]) - 1
            if 0 <= a < len(self.nodes) and 0 <= b < len(self.nodes):
                n1, n2 = self.nodes[a], self.nodes[b]
                painter.setPen(QPen(QColor("#617889"), 2))
                painter.drawLine(point(float(n1["x"]), float(n1["y"])), point(float(n2["x"]), float(n2["y"])))
                if self.results:
                    r1, r2 = displacements[a], displacements[b]
                    p1 = point(float(n1["x"]) + amplification * r1["displacement_x_mm"],
                               float(n1["y"]) + amplification * r1["displacement_y_mm"])
                    p2 = point(float(n2["x"]) + amplification * r2["displacement_x_mm"],
                               float(n2["y"]) + amplification * r2["displacement_y_mm"])
                    painter.setPen(QPen(QColor("#46d5a9"), 2, Qt.PenStyle.DashLine))
                    painter.drawLine(p1, p2)
        for index, node in enumerate(self.nodes):
            p = point(float(node["x"]), float(node["y"]))
            painter.setPen(QPen(QColor("#0d151c"), 1))
            painter.setBrush(QBrush(QColor("#f1b95e") if node["fixed_x"] or node["fixed_y"] else QColor("#7de0bd")))
            painter.drawEllipse(p, 6, 6)
            painter.setPen(QColor("#dbe5eb"))
            painter.drawText(p + QPointF(9, -7), str(index + 1))
        painter.setPen(QColor("#91a2b3"))
        legend = "Solid: original model"
        if self.results:
            legend += "     Dashed green: displaced shape (scaled)"
        painter.drawText(12, self.height() - 10, legend)


class AnalysisPage(QWidget):
    NODE_HEADERS = ("X (mm)", "Y (mm)", "Fx (N)", "Fy (N)", "Fix X", "Fix Y")
    MEMBER_HEADERS = ("Start node", "End node", "Area (mm²)", "E (MPa)")

    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.latest_results: dict | None = None
        title = QLabel("Structural analysis")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Linear 2D pin-jointed truss • N, mm, MPa • small-deformation assumptions")
        subtitle.setObjectName("Muted")
        self.project_label = QLabel("Choose a project before saving analysis results.")
        self.project_label.setObjectName("Muted")

        self.nodes = self._table(self.NODE_HEADERS)
        self.members = self._table(self.MEMBER_HEADERS)
        node_group = QGroupBox("Nodes, loads, and supports")
        node_layout = QVBoxLayout(node_group)
        node_buttons = QHBoxLayout()
        add_node, remove_node = QPushButton("Add node"), QPushButton("Remove node")
        sample = QPushButton("Load sample truss")
        node_buttons.addWidget(add_node)
        node_buttons.addWidget(remove_node)
        node_buttons.addStretch(1)
        node_buttons.addWidget(sample)
        node_layout.addLayout(node_buttons)
        node_layout.addWidget(self.nodes)
        self.export_model_button = QPushButton("Export model JSON")
        self.import_model_button = QPushButton("Import model JSON")
        self.export_model_button.clicked.connect(self._export_model)
        self.import_model_button.clicked.connect(self._import_model)
        model_buttons = QHBoxLayout()
        model_buttons.addWidget(self.export_model_button)
        model_buttons.addWidget(self.import_model_button)
        model_buttons.addStretch(1)
        node_layout.addLayout(model_buttons)
        member_group = QGroupBox("Truss members")
        member_layout = QVBoxLayout(member_group)
        member_buttons = QHBoxLayout()
        add_member, remove_member = QPushButton("Add member"), QPushButton("Remove member")
        member_buttons.addWidget(add_member)
        member_buttons.addWidget(remove_member)
        member_buttons.addStretch(1)
        member_layout.addLayout(member_buttons)
        member_layout.addWidget(self.members)
        add_node.clicked.connect(self._add_node)
        remove_node.clicked.connect(lambda: self._remove_selected(self.nodes))
        add_member.clicked.connect(self._add_member)
        remove_member.clicked.connect(lambda: self._remove_selected(self.members))
        sample.clicked.connect(self._load_sample)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(node_group, 3)
        left_layout.addWidget(member_group, 2)
        self.plot = TrussPlot()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Solve the current model to see displacements, reactions, and member stresses.")
        solve = QPushButton("Solve and save analysis")
        solve.setObjectName("Primary")
        solve.clicked.connect(self._solve)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Model preview"))
        right_layout.addWidget(self.plot, 1)
        right_layout.addWidget(QLabel("Results"))
        right_layout.addWidget(self.output, 1)
        self.export_results_button = QPushButton("Export results CSV")
        self.export_results_button.clicked.connect(self._export_results_csv)
        self.export_results_button.setEnabled(False)
        right_layout.addWidget(self.export_results_button)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.project_label)
        layout.addWidget(splitter, 1)
        layout.addWidget(solve)

        self.nodes.itemChanged.connect(lambda *_: self._preview())
        self.members.itemChanged.connect(lambda *_: self._preview())
        self._load_sample()

    @staticmethod
    def _table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _check_item(checked: bool) -> QTableWidgetItem:
        from PySide6.QtCore import Qt
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        return item

    def _load_sample(self) -> None:
        self.nodes.blockSignals(True)
        self.nodes.setRowCount(0)
        sample_nodes = [
            (0, 0, 0, 0, True, True),
            (400, 0, 0, 0, False, True),
            (400, 300, 0, -10000, False, False),
        ]
        for row, values in enumerate(sample_nodes):
            self.nodes.insertRow(row)
            for col, value in enumerate(values):
                self.nodes.setItem(row, col, self._check_item(bool(value)) if col >= 4 else QTableWidgetItem(str(value)))
        self.members.blockSignals(True)
        self.members.setRowCount(0)
        for row, values in enumerate(((1, 2, 300, 200000), (2, 3, 300, 200000), (1, 3, 300, 200000))):
            self.members.insertRow(row)
            for col, value in enumerate(values):
                self.members.setItem(row, col, QTableWidgetItem(str(value)))
        self.nodes.blockSignals(False)
        self.members.blockSignals(False)
        self._preview()
        self.output.clear()

    def _add_node(self) -> None:
        row = self.nodes.rowCount()
        self.nodes.insertRow(row)
        for col, value in enumerate((100 * row, 100, 0, 0)):
            self.nodes.setItem(row, col, QTableWidgetItem(str(value)))
        self.nodes.setItem(row, 4, self._check_item(False))
        self.nodes.setItem(row, 5, self._check_item(False))

    def _add_member(self) -> None:
        row = self.members.rowCount()
        self.members.insertRow(row)
        values = (1, min(2, max(1, self.nodes.rowCount())), 100, 200000)
        for col, value in enumerate(values):
            self.members.setItem(row, col, QTableWidgetItem(str(value)))

    @staticmethod
    def _remove_selected(table: QTableWidget) -> None:
        if table.currentRow() >= 0:
            table.removeRow(table.currentRow())

    @staticmethod
    def _text(table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        if item is None or not item.text().strip():
            raise TrussInputError(f"Fill in row {row + 1} of the input table.")
        return item.text().strip()

    def _read_model(self):
        nodes, model_nodes = [], []
        for row in range(self.nodes.rowCount()):
            x, y, fx, fy = (float(self._text(self.nodes, row, col)) for col in range(4))
            fixed_x = self.nodes.item(row, 4).checkState() == Qt.CheckState.Checked
            fixed_y = self.nodes.item(row, 5).checkState() == Qt.CheckState.Checked
            nodes.append(Node(x, y, fx, fy, fixed_x, fixed_y))
            model_nodes.append({"x": x, "y": y, "force_x": fx, "force_y": fy,
                                "fixed_x": fixed_x, "fixed_y": fixed_y})
        elements, model_elements = [], []
        for row in range(self.members.rowCount()):
            start = int(self._text(self.members, row, 0))
            end = int(self._text(self.members, row, 1))
            area, modulus = float(self._text(self.members, row, 2)), float(self._text(self.members, row, 3))
            elements.append(TrussElement(start - 1, end - 1, area, modulus))
            model_elements.append({"start": start, "end": end, "area_mm2": area,
                                   "youngs_modulus_mpa": modulus})
        return nodes, elements, {"nodes": model_nodes, "members": model_elements}

    def _preview(self) -> None:
        try:
            _, _, model = self._read_model()
            self.plot.set_model(model["nodes"], model["members"])
        except Exception:
            # Incomplete table edits should not interrupt typing.
            pass

    def refresh(self) -> None:
        project = self.get_active_project()
        self.project_label.setText(
            f"Analysis results will be saved to: {project['name']}" if project
            else "Choose a project before saving analysis results."
        )

    def _export_model(self) -> None:
        try:
            _, _, model = self._read_model()
        except Exception as exc:
            QMessageBox.warning(self, "Model has incomplete inputs", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export truss model", "truss-model.json", "JSON model (*.json)"
        )
        if not path:
            return
        try:
            Path(path).with_suffix(".json").write_text(
                json.dumps({"units": {"length": "mm", "force": "N", "stress": "MPa"}, **model},
                           indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            QMessageBox.information(self, "Model exported", "Truss input saved as JSON.")
        except OSError as exc:
            QMessageBox.critical(self, "Could not export model", str(exc))

    def _import_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import truss model", "", "JSON model (*.json)")
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            nodes, members = payload["nodes"], payload["members"]
            if not isinstance(nodes, list) or not isinstance(members, list):
                raise ValueError("The JSON file needs nodes and members arrays.")
            self.nodes.blockSignals(True)
            self.members.blockSignals(True)
            self.nodes.setRowCount(0)
            self.members.setRowCount(0)
            for row, node in enumerate(nodes):
                self.nodes.insertRow(row)
                values = (node["x"], node["y"], node.get("force_x", 0), node.get("force_y", 0))
                for col, value in enumerate(values):
                    self.nodes.setItem(row, col, QTableWidgetItem(str(value)))
                self.nodes.setItem(row, 4, self._check_item(bool(node.get("fixed_x", False))))
                self.nodes.setItem(row, 5, self._check_item(bool(node.get("fixed_y", False))))
            for row, member in enumerate(members):
                self.members.insertRow(row)
                values = (
                    member["start"], member["end"], member.get("area_mm2", member.get("area")),
                    member.get("youngs_modulus_mpa", member.get("youngs_modulus")),
                )
                for col, value in enumerate(values):
                    self.members.setItem(row, col, QTableWidgetItem(str(value)))
            self.nodes.blockSignals(False)
            self.members.blockSignals(False)
            self.latest_results = None
            self.export_results_button.setEnabled(False)
            self.output.clear()
            self._preview()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.nodes.blockSignals(False)
            self.members.blockSignals(False)
            QMessageBox.critical(self, "Could not import model", str(exc))

    def _export_results_csv(self) -> None:
        if not self.latest_results:
            QMessageBox.information(self, "No analysis results", "Solve the model first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export result tables", "truss-results.csv", "CSV spreadsheet (*.csv)"
        )
        if not path:
            return
        try:
            with Path(path).with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(("MechaCAD & CAE Studio - Linear truss results",))
                writer.writerow(("Units", "length mm", "force N", "stress MPa"))
                writer.writerow(())
                writer.writerow(("Nodal results",))
                writer.writerow(("Node", "Ux mm", "Uy mm", "Reaction X N", "Reaction Y N"))
                for row in self.latest_results["nodes"]:
                    writer.writerow((row["node"], row["displacement_x_mm"], row["displacement_y_mm"],
                                     row["reaction_x_n"], row["reaction_y_n"]))
                writer.writerow(())
                writer.writerow(("Member results",))
                writer.writerow(("Member", "Start node", "End node", "State", "Axial force N", "Stress MPa"))
                for row in self.latest_results["members"]:
                    writer.writerow((row["member"], row["start_node"], row["end_node"], row["state"],
                                     row["axial_force_n"], row["stress_mpa"]))
            QMessageBox.information(self, "CSV exported", f"Saved results to:\n{Path(path).with_suffix('.csv')}")
        except OSError as exc:
            QMessageBox.critical(self, "Could not export CSV", str(exc))

    def _solve(self) -> None:
        try:
            nodes, elements, model = self._read_model()
            results = TrussSolver.solve(nodes, elements)
        except Exception as exc:
            QMessageBox.warning(self, "Analysis could not be completed", str(exc))
            return
        self.latest_results = results
        self.export_results_button.setEnabled(True)
        lines = [
            "LINEAR 2D TRUSS ANALYSIS", "Units: mm, N, MPa",
            f"Maximum displacement: {results['maximum_displacement_mm']:.6f} mm",
            f"Maximum absolute axial stress: {results['maximum_absolute_stress_mpa']:.3f} MPa",
            "", "NODAL RESULTS", "Node | Ux (mm) | Uy (mm) | Rx (N) | Ry (N)",
        ]
        for row in results["nodes"]:
            lines.append(
                f"{row['node']:>4} | {row['displacement_x_mm']:>10.5f} | {row['displacement_y_mm']:>10.5f} | "
                f"{row['reaction_x_n']:>10.2f} | {row['reaction_y_n']:>10.2f}"
            )
        lines.extend(("", "MEMBER RESULTS", "Member | Nodes | State | Axial force (N) | Stress (MPa)"))
        for row in results["members"]:
            lines.append(
                f"{row['member']:>6} | {row['start_node']}-{row['end_node']} | {row['state']:<11} | "
                f"{row['axial_force_n']:>14.2f} | {row['stress_mpa']:>12.3f}"
            )
        self.output.setPlainText("\n".join(lines))
        self.plot.set_model(model["nodes"], model["members"], results)
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(
                self, "Results calculated",
                "The results are visible, but saving requires an active project and MySQL connection.",
            )
            return
        try:
            name = "Run " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.database.save_analysis(project["id"], model, results, name)
            QMessageBox.information(self, "Analysis saved", f"Results saved to {project['name']}.")
        except Exception as exc:
            QMessageBox.warning(self, "Results not saved", str(exc))
