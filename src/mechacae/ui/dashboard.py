"""Home dashboard."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.value = QLabel(value)
        self.value.setObjectName("Metric")
        self.label = QLabel(label)
        self.label.setObjectName("Muted")
        self.detail = QLabel(detail)
        self.detail.setWordWrap(True)
        self.detail.setObjectName("Muted")
        layout = QVBoxLayout(self)
        layout.addWidget(self.value)
        layout.addWidget(self.label)
        layout.addWidget(self.detail)
        layout.addStretch(1)


class DashboardPage(QWidget):
    def __init__(self, database, get_active_project, on_connect, on_navigate, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        title = QLabel("Engineering workspace")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Plan a part, define its material, and inspect a simple structural response.")
        subtitle.setObjectName("Muted")

        self.connection = MetricCard("DATABASE", "Not connected", "Connect to MySQL to load projects and save your work.")
        self.projects = MetricCard("PROJECTS", "—", "Stored in the connected database")
        self.designs = MetricCard("SAVED SKETCHES", "—", "2D rectangle and circle profiles")
        self.analyses = MetricCard("ANALYSIS RUNS", "—", "Educational linear truss calculations")
        self.checks = MetricCard("DESIGN CHECKS", "—", "Sections, beams, and motor sizing")
        cards = QGridLayout()
        cards.setSpacing(14)
        for position, card in enumerate((self.connection, self.projects, self.designs, self.analyses, self.checks)):
            cards.addWidget(card, position // 2, position % 2)

        self.project_label = QLabel("Active project: none selected")
        self.project_label.setObjectName("Muted")
        start = QPushButton("Create or select a project")
        start.setObjectName("Primary")
        start.clicked.connect(lambda: on_navigate("Projects"))
        connect = QPushButton("Configure MySQL")
        connect.clicked.connect(on_connect)
        actions = QGridLayout()
        actions.addWidget(start, 0, 0)
        actions.addWidget(connect, 0, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addLayout(cards)
        layout.addSpacing(10)
        layout.addWidget(self.project_label)
        layout.addLayout(actions)
        layout.addStretch(1)

    def refresh(self) -> None:
        project = self.get_active_project()
        self.project_label.setText(
            f"Active project: {project['name']}" if project else "Active project: none selected"
        )
        if not self.database.connected:
            self.connection.value.setText("Not connected")
            self.connection.detail.setText("Connect to MySQL to load projects and save your work.")
            for card in (self.projects, self.designs, self.analyses, self.checks):
                card.value.setText("—")
            return
        try:
            counts = self.database.project_counts()
            self.connection.value.setText("Connected")
            self.connection.detail.setText(f"{self.database.config.host} / {self.database.config.database}")
            self.projects.value.setText(str(counts["projects"]))
            self.designs.value.setText(str(counts["designs"]))
            self.analyses.value.setText(str(counts["analyses"]))
            self.checks.value.setText(str(counts["checks"]))
        except Exception as exc:
            self.connection.value.setText("Connection issue")
            self.connection.detail.setText(str(exc))
