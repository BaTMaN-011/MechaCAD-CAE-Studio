"""Cross-section, beam, and lead-screw sizing tools."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QPlainTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..domain.beam import BeamInputError, calculate_beam
from ..domain.control import ControlInputError, simulate_dc_motor_position
from ..domain.mechatronics import ActuatorInputError, size_lead_screw_drive
from ..domain.gears import GearInputError, GearStage, calculate_gear_train
from ..domain.torsion import TorsionInputError, calculate_shaft_torsion
from ..domain.units import UNIT_FACTORS, convert
from ..domain.sections import SectionInputError, calculate_section


SHAPES = {
    "Rectangle": (("width", "Width (mm)", 50.0), ("height", "Height (mm)", 80.0)),
    "Solid circle": (("diameter", "Diameter (mm)", 30.0),),
    "Hollow circle": (
        ("outer_diameter", "Outer diameter (mm)", 40.0),
        ("inner_diameter", "Inner diameter (mm)", 30.0),
    ),
    "Rectangular tube": (
        ("width", "Outer width (mm)", 50.0), ("height", "Outer height (mm)", 80.0),
        ("wall", "Wall thickness (mm)", 4.0),
    ),
    "I-section": (
        ("width", "Flange width (mm)", 80.0), ("height", "Overall height (mm)", 120.0),
        ("flange", "Flange thickness (mm)", 8.0), ("web", "Web thickness (mm)", 5.0),
    ),
}


def number_box(value: float, maximum: float = 1e9, decimals: int = 3) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0, maximum)
    box.setDecimals(decimals)
    box.setValue(value)
    box.setSingleStep(max(0.1, value / 20))
    return box


class SectionTab(QWidget):
    section_calculated = Signal(dict)

    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.fields: dict[str, QDoubleSpinBox] = {}
        self.result = None
        self.result_values: dict | None = None
        title = QLabel("Cross-section properties")
        title.setObjectName("PageTitle")
        intro = QLabel(
            "Calculate area, centroidal second moments of area, section moduli, and approximate mass per metre."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        self.shape = QComboBox()
        self.shape.addItems(SHAPES.keys())
        self.material = QComboBox()
        self.material.addItem("No material selected", None)
        self.form_widget = QWidget()
        self.form = QFormLayout(self.form_widget)
        self.shape.currentTextChanged.connect(self._build_fields)
        self.calculate_button = QPushButton("Calculate section")
        self.calculate_button.setObjectName("Primary")
        self.save_button = QPushButton("Save to project")
        self.calculate_button.clicked.connect(self.calculate)
        self.save_button.clicked.connect(self.save)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Section properties will appear here.")
        options = QFormLayout()
        options.addRow("Section shape", self.shape)
        options.addRow("Material for mass", self.material)
        controls = QHBoxLayout()
        controls.addWidget(self.calculate_button)
        controls.addWidget(self.save_button)
        controls.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(options)
        layout.addWidget(self.form_widget)
        layout.addLayout(controls)
        layout.addWidget(self.output, 1)
        self._build_fields(self.shape.currentText())
        self.refresh()

    def _build_fields(self, shape: str) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields.clear()
        for key, label, default in SHAPES[shape]:
            box = number_box(default, decimals=2)
            self.fields[key] = box
            self.form.addRow(label, box)

    def refresh(self) -> None:
        previous = self.material.currentData()
        self.material.clear()
        self.material.addItem("No material selected", None)
        if not self.database.connected:
            self.save_button.setEnabled(False)
            return
        try:
            for row in self.database.list_materials():
                self.material.addItem(row["name"], row)
            if previous:
                for index in range(self.material.count()):
                    data = self.material.itemData(index)
                    if data and data["name"] == previous["name"]:
                        self.material.setCurrentIndex(index)
                        break
        except Exception as exc:
            QMessageBox.warning(self, "Could not load material list", str(exc))
        self.save_button.setEnabled(self.get_active_project() is not None)

    def calculate(self) -> None:
        try:
            self.result = calculate_section(
                self.shape.currentText(), {key: box.value() for key, box in self.fields.items()}
            )
        except (ValueError, SectionInputError) as exc:
            QMessageBox.warning(self, "Section dimensions need attention", str(exc))
            return
        material = self.material.currentData()
        density = float(material["density_kg_m3"]) if material else None
        yield_strength = float(material["yield_strength_mpa"]) if material else None
        mass_text = f"{self.result.area_mm2 * density * 1e-6:.4f} kg/m" if density else "Select a material to estimate mass"
        self.result_values = {
            "name": self.result.name,
            "dimensions": self.result.dimensions,
            "area_mm2": self.result.area_mm2,
            "ixx_mm4": self.result.ixx_mm4,
            "iyy_mm4": self.result.iyy_mm4,
            "cxx_mm": self.result.cxx_mm,
            "cyy_mm": self.result.cyy_mm,
            "section_modulus_x_mm3": self.result.section_modulus_x_mm3,
            "section_modulus_y_mm3": self.result.section_modulus_y_mm3,
            "density_kg_m3": density,
            "material_name": material["name"] if material else None,
        }
        self.output.setPlainText(
            f"{self.result.name}\n"
            f"Area: {self.result.area_mm2:,.3f} mm²\n"
            f"Ixx: {self.result.ixx_mm4:,.3f} mm⁴\n"
            f"Iyy: {self.result.iyy_mm4:,.3f} mm⁴\n"
            f"Section modulus Sx: {self.result.section_modulus_x_mm3:,.3f} mm³\n"
            f"Section modulus Sy: {self.result.section_modulus_y_mm3:,.3f} mm³\n"
            f"Extreme fibre distances cx / cy: {self.result.cxx_mm:.3f} / {self.result.cyy_mm:.3f} mm\n"
            f"Mass per metre: {mass_text}\n"
            "Axes pass through the centroid. Hollow profile overlaps are represented by subtraction."
        )
        self.section_calculated.emit({
            **self.result_values,
            "youngs_modulus_mpa": float(material["youngs_modulus_mpa"]) if material else None,
            "yield_strength_mpa": yield_strength,
        })
        self.save_button.setEnabled(self.get_active_project() is not None and self.database.connected)

    def save(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        if not self.result_values:
            QMessageBox.information(self, "Calculate first", "Calculate a section before saving it.")
            return
        try:
            name = self.result.name + " - " + datetime.now().strftime("%H:%M:%S")
            self.database.save_design_check(
                project["id"], name, "cross_section",
                {"shape": self.shape.currentText(), "dimensions": self.result.dimensions},
                self.result_values,
            )
            QMessageBox.information(self, "Saved", "Section calculation saved to the active project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save calculation", str(exc))


class BeamTab(QWidget):
    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.section: dict | None = None
        self.result_values: dict | None = None
        title = QLabel("Beam bending check")
        title.setObjectName("PageTitle")
        intro = QLabel(
            "Use the cross-section tab first. Choose a simple support and load case; results are estimates from elementary beam theory."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        self.support = QComboBox()
        self.support.addItems(("Simply supported", "Cantilever"))
        self.load_kind = QComboBox()
        self.load_kind.addItems(("Point load", "Uniform load"))
        self.length = number_box(1000, 1e7, 1)
        self.point_load = number_box(1000, 1e9, 1)
        self.distributed = number_box(2, 1e6, 3)
        self.material = QComboBox()
        self.material.addItem("Choose material", None)
        self.target_sf = number_box(1.5, 1000, 2)
        self.target_sf.setMinimum(1.0)
        self.section_label = QLabel("No section properties selected.")
        self.section_label.setObjectName("Muted")
        form = QFormLayout()
        for label, widget in (
            ("Support", self.support), ("Load case", self.load_kind), ("Span (mm)", self.length),
            ("Point load (N)", self.point_load), ("Uniform load (N/mm)", self.distributed),
            ("Material", self.material), ("Required yield safety factor", self.target_sf),
        ):
            form.addRow(label, widget)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Beam result summary.")
        self.calculate_button = QPushButton("Calculate beam check")
        self.calculate_button.setObjectName("Primary")
        self.save_button = QPushButton("Save to project")
        self.calculate_button.clicked.connect(self.calculate)
        self.save_button.clicked.connect(self.save)
        self.load_kind.currentTextChanged.connect(self._sync_load_fields)
        controls = QHBoxLayout()
        controls.addWidget(self.calculate_button)
        controls.addWidget(self.save_button)
        controls.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addWidget(self.section_label)
        layout.addLayout(form)
        layout.addLayout(controls)
        layout.addWidget(self.output, 1)
        self.refresh()

    def set_section(self, section: dict) -> None:
        self.section = section
        self.section_label.setText(
            f"Section: {section['name']} • Ixx {section['ixx_mm4']:,.2f} mm⁴ • cx {section['cxx_mm']:.2f} mm"
        )
        material_name = section.get("material_name")
        if material_name:
            for index in range(self.material.count()):
                data = self.material.itemData(index)
                if data and data["name"] == material_name:
                    self.material.setCurrentIndex(index)
                    break

    def _sync_load_fields(self, kind: str) -> None:
        self.point_load.setEnabled(kind == "Point load")
        self.distributed.setEnabled(kind == "Uniform load")

    def refresh(self) -> None:
        previous = self.material.currentData()
        self.material.clear()
        self.material.addItem("Choose material", None)
        if not self.database.connected:
            return
        try:
            for row in self.database.list_materials():
                self.material.addItem(row["name"], row)
            if previous:
                for index in range(self.material.count()):
                    data = self.material.itemData(index)
                    if data and data["name"] == previous["name"]:
                        self.material.setCurrentIndex(index)
                        break
        except Exception as exc:
            QMessageBox.warning(self, "Could not load material list", str(exc))

    def calculate(self) -> None:
        if not self.section:
            QMessageBox.information(self, "Section properties needed", "Calculate a section first.")
            return
        material = self.material.currentData()
        if not material:
            QMessageBox.information(self, "Material needed", "Choose a material to provide the elastic modulus.")
            return
        try:
            result = calculate_beam(
                self.support.currentText(), self.load_kind.currentText(), self.length.value(),
                float(material["youngs_modulus_mpa"]), float(self.section["ixx_mm4"]),
                float(self.section["cxx_mm"]),
                point_load_n=self.point_load.value(),
                distributed_load_n_per_mm=self.distributed.value(),
                yield_strength_mpa=float(material["yield_strength_mpa"]),
            )
        except (ValueError, BeamInputError) as exc:
            QMessageBox.warning(self, "Beam inputs need attention", str(exc))
            return
        status = (
            "MEETS SELECTED YIELD FACTOR" if result.yield_safety_factor >= self.target_sf.value()
            else "BELOW SELECTED YIELD FACTOR"
        )
        self.result_values = asdict(result)
        self.result_values["required_safety_factor"] = self.target_sf.value()
        self.result_values["material"] = material["name"]
        self.result_values["section"] = self.section["name"]
        self.output.setPlainText(
            f"{result.support_model} beam • {result.load_model}\n"
            f"Material: {material['name']}\nSection: {self.section['name']}\n"
            f"Maximum bending moment: {result.maximum_moment_nmm:,.3f} N·mm\n"
            f"Maximum deflection: {result.maximum_deflection_mm:,.6f} mm (L/{result.deflection_ratio:,.1f})\n"
            f"Maximum elastic bending stress: {result.maximum_bending_stress_mpa:,.3f} MPa\n"
            f"Yield safety factor estimate: {result.yield_safety_factor:.3f}\n"
            f"Selected factor {self.target_sf.value():.2f}: {status}\n\n"
            + "\n".join("• " + note for note in result.assumptions)
        )

    def save(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        if not self.result_values:
            QMessageBox.information(self, "Calculate first", "Calculate a beam check before saving it.")
            return
        try:
            name = "Beam check - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            inputs = {
                "support": self.support.currentText(), "load": self.load_kind.currentText(),
                "length_mm": self.length.value(), "point_load_n": self.point_load.value(),
                "distributed_load_n_per_mm": self.distributed.value(),
                "section": self.section, "material": self.material.currentText(),
            }
            self.database.save_design_check(project["id"], name, "beam", inputs, self.result_values)
            QMessageBox.information(self, "Saved", "Beam check saved to the active project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save check", str(exc))


class MotorSizingTab(QWidget):
    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.result_values: dict | None = None
        title = QLabel("Lead-screw motor estimate")
        title.setObjectName("PageTitle")
        intro = QLabel(
            "Estimate steady torque, speed, and power for a lead-screw axis. Include a realistic load and efficiency."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        self.force = number_box(500, 1e9, 1)
        self.lead = number_box(5, 1e6, 3)
        self.speed = number_box(20, 1e6, 2)
        self.efficiency = number_box(0.9, 1, 3)
        self.efficiency.setMinimum(0.01)
        self.service = number_box(1.5, 100, 2)
        self.service.setMinimum(1.0)
        form = QFormLayout()
        form.addRow("Axial force (N)", self.force)
        form.addRow("Screw lead (mm/rev)", self.lead)
        form.addRow("Linear speed (mm/s)", self.speed)
        form.addRow("Screw efficiency (0–1)", self.efficiency)
        form.addRow("Service factor", self.service)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Motor torque and speed estimate.")
        calculate = QPushButton("Calculate motor estimate")
        calculate.setObjectName("Primary")
        save = QPushButton("Save to project")
        calculate.clicked.connect(self.calculate)
        save.clicked.connect(self.save)
        self.calculate_button, self.save_button = calculate, save
        buttons = QHBoxLayout()
        buttons.addWidget(calculate)
        buttons.addWidget(save)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.output, 1)

    def calculate(self) -> None:
        try:
            result = size_lead_screw_drive(
                self.force.value(), self.lead.value(), self.speed.value(),
                self.efficiency.value(), self.service.value(),
            )
        except (ValueError, ActuatorInputError) as exc:
            QMessageBox.warning(self, "Actuator inputs need attention", str(exc))
            return
        self.result_values = asdict(result)
        self.output.setPlainText(
            f"Lead-screw drive estimate\n"
            f"Required steady torque: {result.torque_nm:.4f} N·m\n"
            f"Rotational speed: {result.rotational_speed_rpm:.2f} rpm\n"
            f"Estimated mechanical power: {result.mechanical_power_w:.2f} W\n"
            f"Estimated input power at stated efficiency: {result.input_power_w:.2f} W\n"
            f"Efficiency: {result.efficiency:.1%} • Service factor: {result.service_factor:.2f}\n\n"
            + "\n".join("• " + note for note in result.assumptions)
        )

    def save(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        if not self.result_values:
            QMessageBox.information(self, "Calculate first", "Calculate an estimate before saving it.")
            return
        inputs = {
            "axial_force_n": self.force.value(), "lead_mm_per_rev": self.lead.value(),
            "linear_speed_mm_per_s": self.speed.value(), "efficiency": self.efficiency.value(),
            "service_factor": self.service.value(),
        }
        try:
            name = "Screw motor - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.database.save_design_check(
                project["id"], name, "lead_screw_motor", inputs, self.result_values
            )
            QMessageBox.information(self, "Saved", "Motor estimate saved to the active project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save estimate", str(exc))


class MotorResponsePlot(QWidget):
    """Lightweight position-versus-time chart drawn with Qt."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.time_s: list[float] = []
        self.position_deg: list[float] = []
        self.target_deg = 0.0
        self.setMinimumHeight(260)

    def set_response(self, simulation) -> None:
        self.time_s = simulation.time_s
        self.position_deg = simulation.position_deg
        self.target_deg = simulation.target_deg
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d151c"))
        if not self.time_s:
            painter.setPen(QColor("#91a2b3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Run the controller simulation to draw its response")
            return
        left, top, right, bottom = 52.0, 24.0, self.width() - 22.0, self.height() - 38.0
        times, values = self.time_s, self.position_deg
        t_max = max(times[-1], 1e-9)
        y_min = min(0.0, min(values))
        y_max = max(self.target_deg * 1.15, max(values) * 1.05, 1.0)
        if y_max - y_min < 1e-9:
            y_max = y_min + 1
        def point(index: int):
            x = left + (right - left) * times[index] / t_max
            y = bottom - (bottom - top) * (values[index] - y_min) / (y_max - y_min)
            return QPointF(x, y)
        painter.setPen(QPen(QColor("#304351"), 1))
        painter.drawRect(int(left), int(top), int(right - left), int(bottom - top))
        for tick in range(5):
            fraction = tick / 4
            y = bottom - fraction * (bottom - top)
            painter.setPen(QPen(QColor("#1c2b36"), 1))
            painter.drawLine(int(left), int(y), int(right), int(y))
            painter.setPen(QColor("#91a2b3"))
            label = y_min + fraction * (y_max - y_min)
            painter.drawText(4, int(y + 4), f"{label:.0f}°")
        target_y = bottom - (bottom - top) * (self.target_deg - y_min) / (y_max - y_min)
        painter.setPen(QPen(QColor("#e8b36a"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(left), int(target_y), int(right), int(target_y))
        painter.setPen(QPen(QColor("#46d5a9"), 2))
        path = QPainterPath()
        path.moveTo(point(0))
        stride = max(1, len(times) // 1600)
        for index in range(stride, len(times), stride):
            path.lineTo(point(index))
        path.lineTo(point(len(times) - 1))
        painter.drawPath(path)
        painter.setPen(QColor("#91a2b3"))
        painter.drawText(int(left), self.height() - 10, "0 s")
        painter.drawText(int(right - 40), self.height() - 10, f"{t_max:.2f} s")
        painter.drawText(int(left + 8), int(top + 15), "Position response")


class PIDLabTab(QWidget):
    """Tune a compact PID-controlled DC motor position model."""

    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.simulation = None
        self.saved_result: dict | None = None
        title = QLabel("DC motor PID lab")
        title.setObjectName("PageTitle")
        intro = QLabel(
            "Change the controller gains and motor constants, then inspect the simulated position response."
        )
        intro.setObjectName("Muted")
        self.target = number_box(90, 360, 2)
        self.voltage = number_box(12, 1000, 2)
        self.duration = number_box(3, 30, 2)
        self.dt = number_box(0.001, 0.05, 4)
        self.resistance = number_box(2, 1000, 3)
        self.inductance = number_box(0.02, 10, 5)
        self.kt = number_box(0.1, 100, 4)
        self.ke = number_box(0.1, 100, 4)
        self.inertia = number_box(0.01, 100, 5)
        self.friction = number_box(0.02, 1000, 5)
        self.kp = number_box(3, 1e6, 4)
        self.ki = number_box(0.4, 1e6, 4)
        self.kd = number_box(0.1, 1e6, 4)
        self.load_torque = number_box(0, 1000, 4)
        for box in (self.target, self.voltage, self.duration, self.dt, self.resistance,
                    self.inductance, self.kt, self.ke, self.inertia, self.kp):
            box.setMinimum(0.00001)
        left_form, right_form = QFormLayout(), QFormLayout()
        for label, box in (
            ("Target angle (degrees)", self.target), ("Supply voltage (V)", self.voltage),
            ("Simulation duration (s)", self.duration), ("Time step (s)", self.dt),
            ("Winding resistance (Ω)", self.resistance), ("Winding inductance (H)", self.inductance),
            ("Torque constant (N·m/A)", self.kt), ("Back-EMF constant (V·s/rad)", self.ke),
        ):
            left_form.addRow(label, box)
        for label, box in (
            ("Rotor inertia (kg·m²)", self.inertia), ("Viscous friction (N·m·s/rad)", self.friction),
            ("PID proportional gain (V/rad)", self.kp), ("PID integral gain (V/rad·s)", self.ki),
            ("PID derivative gain (V·s/rad)", self.kd), ("Opposing load torque (N·m)", self.load_torque),
        ):
            right_form.addRow(label, box)
        inputs = QHBoxLayout()
        inputs.addLayout(left_form)
        inputs.addLayout(right_form)
        self.plot = MotorResponsePlot()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(145)
        self.run_button = QPushButton("Run simulation")
        self.run_button.setObjectName("Primary")
        self.save_button = QPushButton("Save result to project")
        self.run_button.clicked.connect(self.run_simulation)
        self.save_button.clicked.connect(self.save)
        buttons = QHBoxLayout()
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(inputs)
        layout.addWidget(self.plot, 1)
        layout.addWidget(self.output)
        layout.addLayout(buttons)

    def run_simulation(self) -> None:
        try:
            self.simulation = simulate_dc_motor_position(
                target_deg=self.target.value(),
                supply_voltage_v=self.voltage.value(),
                duration_s=self.duration.value(),
                time_step_s=self.dt.value(),
                resistance_ohm=self.resistance.value(),
                inductance_h=self.inductance.value(),
                torque_constant_nm_per_a=self.kt.value(),
                back_emf_v_per_rad_s=self.ke.value(),
                inertia_kg_m2=self.inertia.value(),
                viscous_friction_nm_per_rad_s=self.friction.value(),
                kp=self.kp.value(), ki=self.ki.value(), kd=self.kd.value(),
                load_torque_nm=self.load_torque.value(),
            )
        except (ValueError, ControlInputError) as exc:
            QMessageBox.warning(self, "Simulation inputs need attention", str(exc))
            return
        result = self.simulation
        self.plot.set_response(result)
        self.saved_result = {
            "rise_time_s": result.rise_time_s,
            "settling_time_s": result.settling_time_s,
            "overshoot_percent": result.overshoot_percent,
            "steady_state_error_deg": result.steady_state_error_deg,
            "peak_current_a": result.peak_current_a,
            "saturation_percent": result.saturation_percent,
            "target_deg": result.target_deg,
        }
        self.output.setPlainText(
            f"Rise time (10% to 90% target): {result.rise_time_s:.4g} s" if result.rise_time_s is not None else "Rise time: target not reached"
        )
        summary = (
            f"Settling time (2% band): {result.settling_time_s:.4g} s" if result.settling_time_s is not None
            else "Settling time: not settled within simulation"
        )
        self.output.appendPlainText(
            f"{summary}\nOvershoot: {result.overshoot_percent:.2f}%\n"
            f"Steady-state error: {result.steady_state_error_deg:.3f}°\n"
            f"Peak armature current: {result.peak_current_a:.3f} A\n"
            f"Voltage saturation: {result.saturation_percent:.1f}% of simulation steps\n"
            "Educational simulation: idealized motor and fixed-step Euler integration."
        )

    def save(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        if not self.saved_result:
            QMessageBox.information(self, "Run the simulation first", "Calculate a controller response before saving it.")
            return
        inputs = {
            "target_deg": self.target.value(), "supply_voltage_v": self.voltage.value(),
            "duration_s": self.duration.value(), "time_step_s": self.dt.value(),
            "resistance_ohm": self.resistance.value(), "inductance_h": self.inductance.value(),
            "torque_constant_nm_per_a": self.kt.value(), "back_emf_v_per_rad_s": self.ke.value(),
            "inertia_kg_m2": self.inertia.value(), "viscous_friction_nm_per_rad_s": self.friction.value(),
            "kp": self.kp.value(), "ki": self.ki.value(), "kd": self.kd.value(),
            "load_torque_nm": self.load_torque.value(),
        }
        try:
            label = "PID response - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.database.save_design_check(project["id"], label, "dc_motor_pid", inputs, self.saved_result)
            QMessageBox.information(self, "Saved", "PID result saved to the active project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save simulation", str(exc))


class GearTrainTab(QWidget):
    """Build a multistage idealized gear train and compare input/output."""

    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.saved_result = None
        title = QLabel("Gear train calculator")
        title.setObjectName("PageTitle")
        intro = QLabel("Estimate output speed, torque, and power through simple external gear stages.")
        intro.setObjectName("Muted")
        self.input_torque = number_box(0.8, 1e8, 3)
        self.input_speed = number_box(1500, 1e8, 2)
        self.stages = QTableWidget(0, 3)
        self.stages.setHorizontalHeaderLabels(("Driver teeth", "Driven teeth", "Stage efficiency (0–1)"))
        self.stages.horizontalHeader().setStretchLastSection(True)
        self._add_stage()
        add = QPushButton("Add stage")
        remove = QPushButton("Remove selected stage")
        add.clicked.connect(self._add_stage)
        remove.clicked.connect(self._remove_stage)
        self.calculate_button = QPushButton("Calculate gear train")
        self.calculate_button.setObjectName("Primary")
        self.save_button = QPushButton("Save to project")
        self.calculate_button.clicked.connect(self.calculate)
        self.save_button.clicked.connect(self.save)
        form = QFormLayout()
        form.addRow("Input torque (N·m)", self.input_torque)
        form.addRow("Input speed (rpm)", self.input_speed)
        stage_buttons = QHBoxLayout()
        stage_buttons.addWidget(add)
        stage_buttons.addWidget(remove)
        stage_buttons.addStretch(1)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Gear train output estimate.")
        buttons = QHBoxLayout()
        buttons.addWidget(self.calculate_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addLayout(stage_buttons)
        layout.addWidget(self.stages)
        layout.addLayout(buttons)
        layout.addWidget(self.output, 1)

    def _add_stage(self) -> None:
        row = self.stages.rowCount()
        self.stages.insertRow(row)
        for col, value in enumerate((20, 60, 0.95)):
            self.stages.setItem(row, col, QTableWidgetItem(str(value)))

    def _remove_stage(self) -> None:
        if self.stages.currentRow() >= 0:
            self.stages.removeRow(self.stages.currentRow())

    def calculate(self) -> None:
        stages = []
        try:
            for row in range(self.stages.rowCount()):
                driver, driven, efficiency = (
                    self.stages.item(row, col).text().strip() if self.stages.item(row, col) else ""
                    for col in range(3)
                )
                if not driver or not driven or not efficiency:
                    raise GearInputError(f"Complete gear stage {row + 1}.")
                stages.append(GearStage(int(driver), int(driven), float(efficiency)))
            result = calculate_gear_train(self.input_torque.value(), self.input_speed.value(), stages)
        except (ValueError, GearInputError) as exc:
            QMessageBox.warning(self, "Gear inputs need attention", str(exc))
            return
        self.saved_result = asdict(result)
        self.output.setPlainText(
            f"Stages: {result.stages}\nTotal speed ratio: {result.total_ratio:.4f}:1 reduction\n"
            f"Combined efficiency: {result.total_efficiency:.1%}\n"
            f"Output speed: {result.output_speed_rpm:,.2f} rpm\n"
            f"Output torque estimate: {result.output_torque_nm:,.4f} N·m\n"
            f"Output mechanical power: {result.output_power_w:,.2f} W\n\n"
            "Direction changes once for each external gear mesh. Backlash, tooth strength, "
            "bearing losses, inertia, and gearbox ratings are not included."
        )

    def save(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        if not self.saved_result:
            QMessageBox.information(self, "Calculate first", "Calculate a gear train before saving it.")
            return
        rows = []
        for row in range(self.stages.rowCount()):
            rows.append([self.stages.item(row, col).text() for col in range(3)])
        inputs = {"input_torque_nm": self.input_torque.value(), "input_speed_rpm": self.input_speed.value(),
                  "stages": rows}
        try:
            name = "Gear train - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.database.save_design_check(project["id"], name, "gear_train", inputs, self.saved_result)
            QMessageBox.information(self, "Saved", "Gear calculation saved to the active project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save gear calculation", str(exc))


class ShaftTorsionTab(QWidget):
    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        self.result_values = None
        title = QLabel("Shaft torsion check")
        title.setObjectName("PageTitle")
        intro = QLabel("Estimate shaft twist and elastic shear stress under a steady torque.")
        intro.setObjectName("Muted")
        self.shape = QComboBox()
        self.shape.addItems(("Solid shaft", "Hollow shaft"))
        self.torque = number_box(50, 1e9, 2)
        self.length = number_box(500, 1e8, 2)
        self.outer = number_box(25, 1e6, 2)
        self.inner = number_box(15, 1e6, 2)
        self.shear_modulus = number_box(76923, 1e9, 2)
        self.shear_modulus.setMinimum(0.01)
        self.material = QComboBox()
        self.material.addItem("Custom shear modulus", None)
        self.inner.setEnabled(False)
        self.shape.currentTextChanged.connect(self._sync_shape)
        self.material.currentIndexChanged.connect(self._sync_material)
        form = QFormLayout()
        for label, widget in (
            ("Section", self.shape), ("Torque (N·m)", self.torque), ("Shaft length (mm)", self.length),
            ("Outer diameter (mm)", self.outer), ("Inner diameter (mm)", self.inner),
            ("Material", self.material), ("Shear modulus G (MPa)", self.shear_modulus),
        ):
            form.addRow(label, widget)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Shaft response summary.")
        calculate = QPushButton("Calculate shaft check")
        calculate.setObjectName("Primary")
        save = QPushButton("Save to project")
        calculate.clicked.connect(self.calculate)
        save.clicked.connect(self.save)
        self.save_button = save
        buttons = QHBoxLayout()
        buttons.addWidget(calculate)
        buttons.addWidget(save)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.output, 1)

    def _sync_shape(self, shape: str) -> None:
        self.inner.setEnabled(shape == "Hollow shaft")

    def _sync_material(self) -> None:
        material = self.material.currentData()
        if material:
            youngs = float(material["youngs_modulus_mpa"])
            poisson = float(material["poisson_ratio"])
            self.shear_modulus.setValue(youngs / (2 * (1 + poisson)))

    def refresh(self) -> None:
        previous = self.material.currentData()
        self.material.clear()
        self.material.addItem("Custom shear modulus", None)
        if not self.database.connected:
            return
        try:
            for row in self.database.list_materials():
                self.material.addItem(row["name"], row)
            if previous:
                for index in range(self.material.count()):
                    data = self.material.itemData(index)
                    if data and data["name"] == previous["name"]:
                        self.material.setCurrentIndex(index)
                        break
        except Exception as exc:
            QMessageBox.warning(self, "Could not load material list", str(exc))

    def calculate(self) -> None:
        material = self.material.currentData()
        try:
            result = calculate_shaft_torsion(
                self.torque.value(), self.length.value(), self.shear_modulus.value(),
                self.outer.value(), self.inner.value() if self.shape.currentText() == "Hollow shaft" else 0.0,
                float(material["yield_strength_mpa"]) if material else None,
            )
        except (ValueError, TorsionInputError) as exc:
            QMessageBox.warning(self, "Shaft inputs need attention", str(exc))
            return
        self.result_values = asdict(result)
        factor = (
            f"{result.yield_safety_factor:.3f}" if result.yield_safety_factor is not None
            else "Add a material with yield strength for an estimate"
        )
        self.output.setPlainText(
            f"{self.shape.currentText()}\nPolar second moment J: {result.polar_moment_mm4:,.3f} mm⁴\n"
            f"Maximum elastic shear stress: {result.maximum_shear_stress_mpa:.3f} MPa\n"
            f"Angle of twist: {result.twist_radians:.6f} rad ({result.twist_degrees:.4f}°)\n"
            f"Estimated yield safety factor: {factor}\n"
            "Ductile shear yield is estimated from tensile yield with the von-Mises relation; fatigue and stress concentrations are omitted."
        )

    def save(self) -> None:
        project = self.get_active_project()
        if not project or not self.database.connected:
            QMessageBox.information(self, "Project required", "Connect MySQL and select a project first.")
            return
        if not self.result_values:
            QMessageBox.information(self, "Calculate first", "Calculate a shaft check before saving it.")
            return
        inputs = {
            "shape": self.shape.currentText(), "torque_nm": self.torque.value(),
            "length_mm": self.length.value(), "outer_diameter_mm": self.outer.value(),
            "inner_diameter_mm": self.inner.value() if self.shape.currentText() == "Hollow shaft" else 0,
            "shear_modulus_mpa": self.shear_modulus.value(),
            "material": self.material.currentText(),
        }
        try:
            label = "Shaft torsion - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.database.save_design_check(project["id"], label, "shaft_torsion", inputs, self.result_values)
            QMessageBox.information(self, "Saved", "Shaft check saved to the active project.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not save shaft check", str(exc))


class UnitConverterTab(QWidget):
    """Quick offline unit conversion for calculations and report tables."""

    def __init__(self, parent=None):
        super().__init__(parent)
        title = QLabel("Engineering unit converter")
        title.setObjectName("PageTitle")
        intro = QLabel("Convert values without changing the unit conventions saved in your model.")
        intro.setObjectName("Muted")
        self.category = QComboBox()
        self.category.addItems(list(UNIT_FACTORS))
        self.value = QDoubleSpinBox()
        self.value.setRange(-1e15, 1e15)
        self.value.setDecimals(8)
        self.value.setValue(100)
        self.source = QComboBox()
        self.target = QComboBox()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(100)
        form = QFormLayout()
        form.addRow("Quantity", self.category)
        form.addRow("Value", self.value)
        form.addRow("From unit", self.source)
        form.addRow("To unit", self.target)
        self.category.currentTextChanged.connect(self._set_units)
        self.value.valueChanged.connect(self.convert_value)
        self.source.currentTextChanged.connect(self.convert_value)
        self.target.currentTextChanged.connect(self.convert_value)
        self.category.currentTextChanged.connect(self.convert_value)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.output)
        layout.addStretch(1)
        self._set_units(self.category.currentText())

    def _set_units(self, category: str) -> None:
        units = tuple(UNIT_FACTORS[category].keys())
        current_source = self.source.currentText()
        current_target = self.target.currentText()
        self.source.blockSignals(True)
        self.target.blockSignals(True)
        self.source.clear()
        self.target.clear()
        self.source.addItems(units)
        self.target.addItems(units)
        if current_source in units:
            self.source.setCurrentText(current_source)
        if current_target in units:
            self.target.setCurrentText(current_target)
        elif len(units) > 1:
            self.target.setCurrentIndex(1)
        self.source.blockSignals(False)
        self.target.blockSignals(False)
        self.convert_value()

    def convert_value(self, *_args) -> None:
        if not self.source.currentText() or not self.target.currentText():
            return
        try:
            result = convert(
                self.value.value(), self.category.currentText(),
                self.source.currentText(), self.target.currentText(),
            )
            self.output.setPlainText(
                f"{self.value.value():,.8g} {self.source.currentText()} = "
                f"{result:,.10g} {self.target.currentText()}"
            )
        except ValueError as exc:
            self.output.setPlainText(str(exc))


class DesignToolsPage(QWidget):
    def __init__(self, database, get_active_project, parent=None):
        super().__init__(parent)
        self.database = database
        self.get_active_project = get_active_project
        title = QLabel("Design tools")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Early-stage CAE and mechatronics calculations. Save useful checks with the active project.")
        subtitle.setObjectName("Muted")
        self.sections = SectionTab(database, get_active_project)
        self.beam = BeamTab(database, get_active_project)
        self.motor = MotorSizingTab(database, get_active_project)
        self.control = PIDLabTab(database, get_active_project)
        self.gears = GearTrainTab(database, get_active_project)
        self.shaft = ShaftTorsionTab(database, get_active_project)
        self.units = UnitConverterTab()
        self.sections.section_calculated.connect(self.beam.set_section)
        tabs = QTabWidget()
        tabs.addTab(self.sections, "Cross-sections")
        tabs.addTab(self.beam, "Beam check")
        tabs.addTab(self.motor, "Motor / screw")
        tabs.addTab(self.control, "PID lab")
        tabs.addTab(self.gears, "Gear train")
        tabs.addTab(self.shaft, "Shaft torsion")
        tabs.addTab(self.units, "Unit converter")
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(tabs, 1)

    def refresh(self) -> None:
        self.sections.refresh()
        self.beam.refresh()
        self.shaft.refresh()
