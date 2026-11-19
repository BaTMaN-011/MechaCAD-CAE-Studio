"""Main desktop shell, page navigation, and connection lifecycle."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..config import AppSettings, DatabaseConfig
from ..database import DatabaseManager
from .analysis import AnalysisPage
from .assembly import AssemblyPage
from .dashboard import DashboardPage
from .design_tools import DesignToolsPage
from .dialogs import ConnectionDialog
from .materials import MaterialsPage
from .projects import ProjectsPage
from .reports import ReportsPage
from .sketch import SketchPage


class MainWindow(QMainWindow):
    NAV_ITEMS = (
        ("Overview", "⌂"),
        ("Projects", "▦"),
        ("2D Sketch", "✎"),
        ("Assembly", "▧"),
        ("Analysis", "△"),
        ("Design Tools", "⚙"),
        ("Materials", "◈"),
        ("Reports", "▤"),
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MechaCAD & CAE Studio")
        self.resize(1420, 920)
        self.setMinimumSize(1080, 700)
        self.database = DatabaseManager()
        self.settings = AppSettings()
        self.active_project: dict | None = None
        self._nav_buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(225)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(14, 20, 14, 16)
        brand = QLabel("MECHA<span style='color:#73d9b8'>LAB</span>")
        brand.setObjectName("Brand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        description = QLabel("CAD  /  ENGINEERING")
        description.setObjectName("Subtitle")
        side_layout.addWidget(brand)
        side_layout.addWidget(description)
        side_layout.addSpacing(28)

        self.stack = QStackedWidget()
        self._add_page("Overview", DashboardPage(
            self.database, self.get_active_project, self.configure_database, self.navigate
        ))
        self._add_page("Projects", ProjectsPage(self.database, self._project_selected))
        self._add_page("2D Sketch", SketchPage(self.database, self.get_active_project))
        self._add_page("Assembly", AssemblyPage(self.database, self.get_active_project))
        self._add_page("Analysis", AnalysisPage(self.database, self.get_active_project))
        self._add_page("Design Tools", DesignToolsPage(self.database, self.get_active_project))
        self._add_page("Materials", MaterialsPage(self.database))
        self._add_page("Reports", ReportsPage(self.database, self.get_active_project))

        for name, icon in self.NAV_ITEMS:
            button = QPushButton(f"{icon}   {name}")
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=name: self.navigate(page))
            self._nav_buttons[name] = button
            side_layout.addWidget(button)
        side_layout.addStretch(1)
        side_note = QLabel("School project build\nEducational CAE only")
        side_note.setObjectName("Subtitle")
        side_layout.addWidget(side_note)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 8, 22, 8)
        self.location = QLabel("OVERVIEW")
        self.location.setObjectName("Subtitle")
        header_layout.addWidget(self.location)
        header_layout.addStretch(1)
        self.connection_label = QLabel("●  MySQL not connected")
        self.connection_label.setObjectName("Muted")
        self.connect_button = QPushButton("Database setup")
        self.connect_button.clicked.connect(self.configure_database)
        header_layout.addWidget(self.connection_label)
        header_layout.addWidget(self.connect_button)
        content_layout.addWidget(header)
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(content, 1)
        self.statusBar().showMessage("Choose a MySQL server in Database setup.")
        self.navigate("Overview")
        QTimer.singleShot(0, self._restore_connection)

    def _add_page(self, name: str, page: QWidget) -> None:
        self._pages[name] = page
        self.stack.addWidget(page)

    def get_active_project(self) -> dict | None:
        return self.active_project

    def _project_selected(self, project: dict | None) -> None:
        self.active_project = project
        for name in ("Overview", "2D Sketch", "Assembly", "Analysis", "Design Tools", "Reports"):
            page = self._pages.get(name)
            if name == "Overview":
                page.refresh()
            elif name == "2D Sketch":
                page.refresh()
            elif name == "Analysis":
                page.refresh()
            elif name == "Reports":
                page.refresh()
        self.statusBar().showMessage(
            f"Active project: {project['name']}" if project else "No active project", 5000
        )

    def navigate(self, name: str) -> None:
        if name not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[name])
        self.location.setText(name.upper())
        for page_name, button in self._nav_buttons.items():
            button.setChecked(page_name == name)
        page = self._pages[name]
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def _restore_connection(self) -> None:
        saved = self.settings.load_connection()
        if not saved:
            self.configure_database()
            return
        config = DatabaseConfig(**saved)
        if not config.password:
            self.configure_database()
            return
        try:
            self.database.connect(config)
            self.settings.save_connection(config, remember_password=True)
            self._connection_changed(True)
        except Exception:
            self.configure_database()

    def configure_database(self) -> None:
        dialog = ConnectionDialog(self.database, self.settings, self)
        if dialog.exec() == ConnectionDialog.DialogCode.Accepted:
            self._connection_changed(True)
        elif not self.database.connected:
            self._connection_changed(False)

    def _connection_changed(self, connected: bool) -> None:
        if connected and self.database.config:
            self.connection_label.setText(f"●  Connected: {self.database.config.host}")
            self.connection_label.setStyleSheet("color:#7de0bd")
            self.statusBar().showMessage(
                f"Connected to MySQL database {self.database.config.database}.", 7000
            )
            self._pages["Projects"].refresh()
            # Project selection refreshes the dependent pages.
            if self.active_project is None:
                rows = self.database.list_projects()
                if rows:
                    self.active_project = {"id": int(rows[0]["id"]), "name": rows[0]["name"]}
            self._refresh_pages()
        else:
            self.connection_label.setText("●  MySQL not connected")
            self.connection_label.setStyleSheet("color:#e8b36a")
            self.statusBar().showMessage("Database is disconnected. You can reconnect from Database setup.", 7000)
            self.active_project = None
            self._refresh_pages()

    def _refresh_pages(self) -> None:
        for page in self._pages.values():
            refresh = getattr(page, "refresh", None)
            if callable(refresh):
                refresh()

    def closeEvent(self, event) -> None:
        self.database.disconnect()
        event.accept()
