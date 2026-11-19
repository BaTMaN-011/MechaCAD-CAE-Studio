"""Desktop application startup."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.theme import APP_STYLE


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("MechaCAD & CAE Studio")
    app.setOrganizationName("MechaCADSchoolProject")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
