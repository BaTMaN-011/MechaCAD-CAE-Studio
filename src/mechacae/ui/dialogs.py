"""Reusable project, material, geometry, and database dialogs."""
from __future__ import annotations

import ipaddress

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from ..config import AppSettings, DatabaseConfig
from ..database import DatabaseManager


class ConnectionDialog(QDialog):
    """Connect to local or remote MySQL and initialize the application's tables."""

    def __init__(self, database: DatabaseManager, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.database = database
        self.settings = settings
        self.config: DatabaseConfig | None = None
        self.remember_password = False
        self.setWindowTitle("Connect to MySQL")
        self.setMinimumWidth(480)

        intro = QLabel(
            "MechaCAD is a desktop app, not a localhost website. MySQL can run on this PC "
            "or on a remote school/hosted server."
        )
        intro.setWordWrap(True)
        self.host = QLineEdit()
        self.host.setPlaceholderText("localhost or mysql.school.example")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(3306)
        self.database_name = QLineEdit()
        self.database_name.setPlaceholderText("school_project_db")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.use_tls = QCheckBox("Use TLS encryption")
        self.use_tls.setChecked(True)
        self.verify_tls = QCheckBox("Verify server certificate and host name")
        self.verify_tls.setChecked(True)
        self.ssl_ca = QLineEdit()
        self.ssl_ca.setPlaceholderText("Optional provider CA certificate (.pem)")
        self.browse_ca_button = QPushButton("Browse…")
        self.browse_ca_button.clicked.connect(self._browse_ca)
        ca_row = QWidget()
        ca_layout = QHBoxLayout(ca_row)
        ca_layout.setContentsMargins(0, 0, 0, 0)
        ca_layout.addWidget(self.ssl_ca, 1)
        ca_layout.addWidget(self.browse_ca_button)
        self.remember = QCheckBox("Remember password in Windows Credential Manager")
        self.remember.setChecked(False)
        self.verify_tls.toggled.connect(self._sync_tls_controls)
        self.use_tls.toggled.connect(self._sync_tls_controls)
        self.host.editingFinished.connect(self._apply_local_defaults)

        saved = settings.load_connection()
        if saved:
            self.host.setText(str(saved["host"]))
            self.port.setValue(int(saved["port"]))
            self.database_name.setText(str(saved["database"]))
            self.username.setText(str(saved["username"]))
            self.password.setText(str(saved["password"]))
            self.use_tls.setChecked(bool(saved["use_tls"]))
            self.verify_tls.setChecked(bool(saved["verify_tls"]))
            self.ssl_ca.setText(str(saved.get("ssl_ca", "")))
            self.remember.setChecked(bool(saved["password"]))

        form = QFormLayout()
        form.addRow("MySQL host", self.host)
        form.addRow("Port", self.port)
        form.addRow("Database", self.database_name)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        form.addRow("", self.use_tls)
        form.addRow("", self.verify_tls)
        form.addRow("CA certificate (optional)", ca_row)
        form.addRow("", self.remember)

        self.status = QLabel("The database must already exist and allow your computer to connect.")
        self.status.setWordWrap(True)
        self.status.setObjectName("Muted")
        self.connect_button = QPushButton("Test and connect")
        self.connect_button.setObjectName("Primary")
        self.cancel_button = QPushButton("Cancel")
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.connect_button)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addLayout(buttons)

        self.connect_button.clicked.connect(self._connect)
        self.cancel_button.clicked.connect(self.reject)
        self._sync_tls_controls()
        self._apply_local_defaults()

    def _sync_tls_controls(self) -> None:
        active = self.use_tls.isChecked()
        self.verify_tls.setEnabled(active)
        self.ssl_ca.setEnabled(active)
        self.browse_ca_button.setEnabled(active)

    def _browse_ca(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose MySQL server CA certificate", "",
            "Certificate files (*.pem *.crt *.cer);;All files (*)",
        )
        if path:
            self.ssl_ca.setText(path)

    @staticmethod
    def _is_local_host(host: str) -> bool:
        cleaned = host.strip().strip("[]").lower().rstrip(".")
        if (cleaned == "localhost" or cleaned.endswith(".localhost")
                or cleaned.startswith("127.") or cleaned.startswith("::ffff:127.")):
            return True
        try:
            return ipaddress.ip_address(cleaned).is_loopback
        except ValueError:
            return False

    @staticmethod
    def _is_unspecified_host(host: str) -> bool:
        cleaned = host.strip().strip("[]").lower().rstrip(".")
        try:
            return ipaddress.ip_address(cleaned).is_unspecified
        except ValueError:
            return cleaned in {"0", "0.0.0.0"}

    def _apply_local_defaults(self) -> None:
        if self._is_local_host(self.host.text()) and not self.ssl_ca.text().strip():
            self.use_tls.setChecked(False)
            self.verify_tls.setChecked(False)
        self._sync_tls_controls()

    def _connect(self) -> None:
        host = self.host.text().strip()
        database_name = self.database_name.text().strip()
        username = self.username.text().strip()
        password = self.password.text()
        if not host or not database_name or not username:
            QMessageBox.warning(self, "Missing connection details", "Enter the host, database name, and username.")
            return
        if self._is_unspecified_host(host):
            QMessageBox.warning(
                self, "Choose a MySQL host",
                "Enter localhost or a specific server name/IP. 0.0.0.0 is a bind address, not a connect address.",
            )
            return
        if not password:
            QMessageBox.warning(self, "Missing password", "Enter the password for the MySQL account.")
            return
        if self.use_tls.isChecked() and self.verify_tls.isChecked() and not self.ssl_ca.text().strip():
            QMessageBox.warning(
                self, "CA certificate required",
                "To verify the remote server certificate, select the CA certificate supplied by your MySQL provider. "
                "You can also turn off certificate verification if your provider instructs you to do so; TLS encryption will remain on.",
            )
            return

        self.connect_button.setEnabled(False)
        self.status.setText("Connecting to MySQL and setting up the project tables…")
        self.status.repaint()
        config = DatabaseConfig(
            host=host,
            port=self.port.value(),
            database=database_name,
            username=username,
            password=password,
            use_tls=self.use_tls.isChecked(),
            verify_tls=self.verify_tls.isChecked(),
            ssl_ca=self.ssl_ca.text().strip(),
        )
        try:
            self.database.connect(config)
        except Exception as exc:
            self.connect_button.setEnabled(True)
            self.status.setText("Connection was not established. Check that MySQL is running, the database exists, and the account/password are correct.")
            QMessageBox.critical(self, "MySQL connection failed", str(exc))
            return
        self.config = config
        self.remember_password = self.remember.isChecked()
        self.settings.save_connection(config, self.remember_password)
        self.accept()


class ProjectDialog(QDialog):
    def __init__(self, project: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit engineering project" if project else "New engineering project")
        self.name = QLineEdit(project["name"] if project else "")
        self.name.setPlaceholderText("Example: Bracket Load Study")
        self.description = QLineEdit(project.get("description", "") if project else "")
        self.description.setPlaceholderText("Purpose, class, and design notes")
        form = QFormLayout()
        form.addRow("Project name", self.name)
        form.addRow("Description", self.description)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str]:
        return self.name.text().strip(), self.description.text().strip()


class MaterialDialog(QDialog):
    def __init__(self, material: dict | None = None, parent=None):
        super().__init__(parent)
        self.material_id = int(material["id"]) if material else None
        self.setWindowTitle("Edit material" if material else "Add material")
        self.name = QLineEdit(str(material["name"]) if material else "")
        self.category = QLineEdit(str(material["category"]) if material else "")
        self.category.setPlaceholderText("Metal, polymer, composite…")
        self.modulus = self._number(1, 1_000_000_000, float(material["youngs_modulus_mpa"]) if material else 200000, 3)
        self.poisson = self._number(0, 0.4999, float(material["poisson_ratio"]) if material else 0.30, 4)
        self.density = self._number(0, 10_000_000, float(material["density_kg_m3"]) if material else 7850, 3)
        self.yield_strength = self._number(0, 1_000_000_000, float(material["yield_strength_mpa"]) if material else 250, 3)
        self.notes = QLineEdit(str(material.get("notes", "")) if material else "")
        form = QFormLayout()
        for label, widget in (
            ("Name", self.name), ("Category", self.category),
            ("Young's modulus (MPa)", self.modulus), ("Poisson ratio", self.poisson),
            ("Density (kg/m³)", self.density), ("Yield strength (MPa)", self.yield_strength),
            ("Notes", self.notes),
        ):
            form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _number(minimum: float, maximum: float, value: float, decimals: int) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSingleStep(max(0.01, value / 20))
        return widget

    def values(self) -> tuple:
        return (
            self.name.text().strip(), self.category.text().strip(), self.modulus.value(),
            self.poisson.value(), self.density.value(), self.yield_strength.value(),
            self.notes.text().strip(),
        )


class GeometryDialog(QDialog):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(f"Add {kind.lower()}")
        self.name = QLineEdit(f"{kind.title()} 1")
        self.x = self._number(-100000, 100000, 80)
        self.y = self._number(-100000, 100000, 80)
        self.width = self._number(1, 100000, 120)
        self.height = self._number(1, 100000, 70)
        form = QFormLayout()
        form.addRow("Entity name", self.name)
        form.addRow("X position (mm)", self.x)
        form.addRow("Y position (mm)", self.y)
        form.addRow("Width / diameter (mm)", self.width)
        form.addRow("Height (mm)", self.height)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Dimensions are in millimetres."))
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _number(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(2)
        box.setValue(value)
        box.setSingleStep(10)
        return box

    def values(self) -> dict:
        return {
            "kind": self.kind.lower(),
            "name": self.name.text().strip() or self.kind.title(),
            "x": self.x.value(),
            "y": self.y.value(),
            "width": self.width.value(),
            "height": self.height.value() if self.kind.lower() == "rectangle" else self.width.value(),
        }


class ComponentDialog(QDialog):
    """Assembly/BOM row editor with material-based mass estimate."""

    def __init__(self, database, component: dict | None = None, parent=None):
        super().__init__(parent)
        self.database = database
        self.component_id = int(component["id"]) if component else None
        self.setWindowTitle("Edit assembly component" if component else "Add assembly component")
        self.part_number = QLineEdit(str(component["part_number"]) if component else "")
        self.name = QLineEdit(str(component["name"]) if component else "")
        self.material = QComboBox()
        self.material.addItem("No material selected", None)
        try:
            materials = self.database.list_materials()
        except Exception:
            materials = []
        for material in materials:
            self.material.addItem(material["name"], material)
        if component and component.get("material_id") is not None:
            for index in range(self.material.count()):
                row = self.material.itemData(index)
                if row and int(row["id"]) == int(component["material_id"]):
                    self.material.setCurrentIndex(index)
                    break
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 100000)
        self.quantity.setValue(int(component["quantity"]) if component else 1)
        self.volume = self._number(0, 1e15, float(component["volume_mm3"]) if component else 0, 3)
        self.unit_mass = self._number(0, 1e12, float(component["unit_mass_kg"]) if component else 0, 9)
        self.notes = QLineEdit(str(component["notes"]) if component else "")
        self.mass_hint = QLabel("Enter a unit mass or a volume and material.")
        self.mass_hint.setObjectName("Muted")
        self.volume.valueChanged.connect(self._update_mass)
        self.material.currentIndexChanged.connect(self._update_mass)
        form = QFormLayout()
        form.addRow("Part number", self.part_number)
        form.addRow("Component name", self.name)
        form.addRow("Material", self.material)
        form.addRow("Quantity", self.quantity)
        form.addRow("Solid volume per unit (mm³)", self.volume)
        form.addRow("Estimated mass per unit (kg)", self.unit_mass)
        form.addRow("", self.mass_hint)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Mass from volume is estimated as volume × material density."))
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_mass()

    @staticmethod
    def _number(minimum: float, maximum: float, value: float, decimals: int) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(decimals)
        box.setValue(value)
        box.setSingleStep(max(0.001, value / 20))
        return box

    def _update_mass(self, *_args) -> None:
        material = self.material.currentData()
        if material and self.volume.value() > 0:
            estimate = self.volume.value() * float(material["density_kg_m3"]) / 1e9
            self.unit_mass.blockSignals(True)
            self.unit_mass.setValue(estimate)
            self.unit_mass.blockSignals(False)
            self.mass_hint.setText(f"Estimated from {material['name']} density.")
        elif not material:
            self.mass_hint.setText("Select a material and enter volume to estimate mass, or enter mass directly.")
        else:
            self.mass_hint.setText("Enter a volume in mm³ to estimate mass from the selected material.")

    def values(self) -> tuple:
        material = self.material.currentData()
        return (
            self.part_number.text().strip(), self.name.text().strip(),
            int(material["id"]) if material else None, self.quantity.value(),
            self.volume.value(), self.unit_mass.value(), self.notes.text().strip(),
        )
