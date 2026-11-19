"""Analysis history and exportable design-check reports."""
from __future__ import annotations

import html
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)


class ReportsPage(QWidget):
    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.rows = []
        self.check_rows = []
        title = QLabel("Reports")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Review saved analyses and design calculations; export a self-contained HTML report.")
        subtitle.setObjectName("Muted")
        self.project_label = QLabel("Choose a project to load saved records.")
        self.project_label.setObjectName("Muted")

        self.list = QListWidget()
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select an analysis run to preview its summary.")
        self.refresh_button = QPushButton("Refresh")
        self.export_button = QPushButton("Export analysis HTML")
        self.export_button.setObjectName("Primary")
        self.refresh_button.clicked.connect(self.refresh)
        self.export_button.clicked.connect(self._export_analysis)
        self.list.currentRowChanged.connect(self._select_analysis)
        analysis_controls = QHBoxLayout()
        analysis_controls.addWidget(self.refresh_button)
        analysis_controls.addStretch(1)
        analysis_controls.addWidget(self.export_button)
        analysis_splitter = QSplitter()
        analysis_splitter.addWidget(self.list)
        analysis_splitter.addWidget(self.preview)
        analysis_splitter.setStretchFactor(0, 1)
        analysis_splitter.setStretchFactor(1, 2)
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.addLayout(analysis_controls)
        analysis_layout.addWidget(analysis_splitter, 1)

        self.check_list = QListWidget()
        self.check_preview = QPlainTextEdit()
        self.check_preview.setReadOnly(True)
        self.check_preview.setPlaceholderText("Select a saved check to inspect its input and output values.")
        self.export_check_button = QPushButton("Export design-check HTML")
        self.export_check_button.setObjectName("Primary")
        self.export_check_button.clicked.connect(self._export_check)
        self.check_list.currentRowChanged.connect(self._select_check)
        check_controls = QHBoxLayout()
        check_controls.addStretch(1)
        check_controls.addWidget(self.export_check_button)
        check_splitter = QSplitter()
        check_splitter.addWidget(self.check_list)
        check_splitter.addWidget(self.check_preview)
        check_splitter.setStretchFactor(0, 1)
        check_splitter.setStretchFactor(1, 2)
        checks_tab = QWidget()
        checks_layout = QVBoxLayout(checks_tab)
        checks_layout.addLayout(check_controls)
        checks_layout.addWidget(check_splitter, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(analysis_tab, "Truss analyses")
        self.tabs.addTab(checks_tab, "Design checks")
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.project_label)
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        self.list.clear()
        self.check_list.clear()
        self.preview.clear()
        self.check_preview.clear()
        project = self.get_active_project()
        if not project:
            self.project_label.setText("Choose a project to load saved records.")
            self.rows, self.check_rows = [], []
            return
        self.project_label.setText(f"Saved records for: {project['name']}")
        if not self.database.connected:
            return
        try:
            self.rows = self.database.list_analyses(project["id"])
            self.check_rows = self.database.list_design_checks(project["id"])
        except Exception as exc:
            QMessageBox.warning(self, "Could not load reports", str(exc))
            self.rows, self.check_rows = [], []
            return
        for row in self.rows:
            self.list.addItem(QListWidgetItem(f"{row['name']}  •  {row['created_at']}"))
        for row in self.check_rows:
            self.check_list.addItem(
                QListWidgetItem(f"{row['name']}  •  {row['check_type']}  •  {row['created_at']}")
            )
        if self.rows:
            self.list.setCurrentRow(0)
        if self.check_rows:
            self.check_list.setCurrentRow(0)

    @staticmethod
    def _decode(payload: str) -> dict:
        try:
            result = json.loads(payload)
            return result if isinstance(result, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _select_analysis(self, index: int) -> None:
        if index < 0 or index >= len(self.rows):
            self.preview.clear()
            return
        row = self.rows[index]
        results = self._decode(row["results_json"])
        self.preview.setPlainText(self._analysis_summary(row["name"], results))

    @staticmethod
    def _analysis_summary(name: str, results: dict) -> str:
        lines = [
            name,
            "Educational linear static analysis; units: mm, N, MPa",
            f"Maximum displacement: {results.get('maximum_displacement_mm', 0):.6g} mm",
            f"Maximum absolute stress: {results.get('maximum_absolute_stress_mpa', 0):.6g} MPa",
            "",
            "Node results",
            "Node | Ux mm | Uy mm | Reaction X N | Reaction Y N",
        ]
        for row in results.get("nodes", []):
            lines.append(
                f"{row['node']} | {row['displacement_x_mm']:.6g} | {row['displacement_y_mm']:.6g} | "
                f"{row['reaction_x_n']:.6g} | {row['reaction_y_n']:.6g}"
            )
        lines.extend(("", "Member results", "Member | State | Axial force N | Stress MPa"))
        for row in results.get("members", []):
            lines.append(
                f"{row['member']} | {row['state']} | {row['axial_force_n']:.6g} | {row['stress_mpa']:.6g}"
            )
        return "\n".join(lines)

    def _export_analysis(self) -> None:
        index = self.list.currentRow()
        if index < 0 or index >= len(self.rows):
            QMessageBox.information(self, "Select a run", "Choose a saved analysis before exporting.")
            return
        row = self.rows[index]
        project = self.get_active_project()
        results = self._decode(row["results_json"])
        path, _ = QFileDialog.getSaveFileName(
            self, "Export engineering report", f"{row['name']}.html", "HTML report (*.html)"
        )
        if not path:
            return
        path = str(Path(path).with_suffix(".html"))
        node_rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in (
                item["node"], f"{item['displacement_x_mm']:.6g}", f"{item['displacement_y_mm']:.6g}",
                f"{item['reaction_x_n']:.6g}", f"{item['reaction_y_n']:.6g}",
            )) + "</tr>"
            for item in results.get("nodes", [])
        )
        member_rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in (
                item["member"], f"{item['start_node']}-{item['end_node']}", item["state"],
                f"{item['axial_force_n']:.6g}", f"{item['stress_mpa']:.6g}",
            )) + "</tr>"
            for item in results.get("members", [])
        )
        project_name = html.escape(project["name"] if project else "Unknown project")
        run_name = html.escape(str(row["name"]))
        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{run_name}</title>
<style>
body{{font:15px Segoe UI,Arial,sans-serif;color:#18232c;max-width:1000px;margin:40px auto;padding:0 20px}}
h1,h2{{color:#126d5b}}.note{{background:#edf6f3;padding:14px;border-left:4px solid #258e78}}
table{{border-collapse:collapse;width:100%;margin:16px 0 28px}}th,td{{border:1px solid #ccd8dc;padding:8px;text-align:right}}
th{{background:#e8f1ef}}th:first-child,td:first-child{{text-align:left}}
</style></head><body>
<h1>MechaCAD &amp; CAE Studio</h1><p><b>Project:</b> {project_name}<br><b>Analysis:</b> {run_name}</p>
<div class="note">Educational linear static analysis of a 2D pin-jointed truss. Units: mm, N, MPa.
This simplified solver is not a certified engineering design tool.</div>
<h2>Summary</h2><p>Maximum displacement: {results.get('maximum_displacement_mm', 0):.6g} mm<br>
Maximum absolute axial stress: {results.get('maximum_absolute_stress_mpa', 0):.6g} MPa</p>
<h2>Nodal results</h2><table><thead><tr><th>Node</th><th>Ux (mm)</th><th>Uy (mm)</th><th>Rx (N)</th><th>Ry (N)</th></tr></thead><tbody>{node_rows}</tbody></table>
<h2>Member results</h2><table><thead><tr><th>Member</th><th>Nodes</th><th>State</th><th>Axial force (N)</th><th>Stress (MPa)</th></tr></thead><tbody>{member_rows}</tbody></table>
</body></html>"""
        self._write_report(path, document)

    def _select_check(self, index: int) -> None:
        if index < 0 or index >= len(self.check_rows):
            self.check_preview.clear()
            return
        row = self.check_rows[index]
        inputs = self._decode(row["inputs_json"])
        results = self._decode(row["results_json"])
        self.check_preview.setPlainText(
            f"{row['name']}\nType: {row['check_type']}\nCreated: {row['created_at']}\n\n"
            f"INPUTS\n{json.dumps(inputs, indent=2, ensure_ascii=False)}\n\n"
            f"RESULTS\n{json.dumps(results, indent=2, ensure_ascii=False)}"
        )

    def _export_check(self) -> None:
        index = self.check_list.currentRow()
        if index < 0 or index >= len(self.check_rows):
            QMessageBox.information(self, "Select a check", "Choose a saved design check before exporting.")
            return
        row = self.check_rows[index]
        project = self.get_active_project()
        inputs = self._decode(row["inputs_json"])
        results = self._decode(row["results_json"])
        path, _ = QFileDialog.getSaveFileName(
            self, "Export design-check report", f"{row['name']}.html", "HTML report (*.html)"
        )
        if not path:
            return
        path = str(Path(path).with_suffix(".html"))
        project_name = html.escape(project["name"] if project else "Unknown project")
        title = html.escape(str(row["name"]))
        input_json = html.escape(json.dumps(inputs, indent=2, ensure_ascii=False))
        result_json = html.escape(json.dumps(results, indent=2, ensure_ascii=False))
        document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font:15px Segoe UI,Arial,sans-serif;color:#18232c;max-width:900px;margin:40px auto;padding:0 20px}}
h1,h2{{color:#126d5b}}pre{{white-space:pre-wrap;background:#f1f5f4;padding:16px;border-radius:8px}}</style></head>
<body><h1>MechaCAD &amp; CAE Studio</h1><p>Project: {project_name}<br>Check: {title}<br>Type: {html.escape(str(row['check_type']))}</p>
<div>Educational estimate. Confirm assumptions and data before applying to a real design.</div>
<h2>Inputs</h2><pre>{input_json}</pre><h2>Results</h2><pre>{result_json}</pre></body></html>"""
        self._write_report(path, document)

    @staticmethod
    def _write_report(path: str, document: str) -> None:
        try:
            Path(path).write_text(document, encoding="utf-8")
            QMessageBox.information(None, "Report exported", f"Saved report to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(None, "Could not export report", str(exc))
