"""Shared visual style for the application."""
APP_STYLE = """
QWidget {
    background: #101820;
    color: #eaf0f5;
    font-family: Segoe UI, sans-serif;
    font-size: 10pt;
}
QMainWindow { background: #0b1118; }
QFrame#Sidebar { background: #111a23; border-right: 1px solid #263442; }
QFrame#Header { background: #101820; border-bottom: 1px solid #263442; }
QLabel#Brand { color: #f6f8fa; font-size: 17pt; font-weight: 700; }
QLabel#Subtitle { color: #91a2b3; font-size: 9pt; }
QLabel#PageTitle { color: #f6f8fa; font-size: 21pt; font-weight: 650; }
QLabel#Muted { color: #91a2b3; }
QLabel#Metric { color: #7de0bd; font-size: 24pt; font-weight: 700; }
QFrame#Card, QGroupBox {
    background: #151f29;
    border: 1px solid #293947;
    border-radius: 10px;
}
QGroupBox { margin-top: 13px; padding: 13px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: #b8cad8; }
QPushButton, QToolButton {
    background: #1b2935;
    border: 1px solid #354858;
    border-radius: 7px;
    padding: 8px 12px;
    color: #eaf0f5;
}
QPushButton:hover, QToolButton:hover { background: #253847; border-color: #5f8298; }
QPushButton#Primary { background: #167b68; border-color: #1b987d; font-weight: 650; }
QPushButton#Primary:hover { background: #1b947b; }
QPushButton#Nav {
    text-align: left;
    padding: 10px 12px;
    background: transparent;
    border-color: transparent;
    color: #b7c5d0;
}
QPushButton#Nav:checked { background: #203b42; color: #86e0c3; border-color: #2a635b; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
    background: #0d151c;
    border: 1px solid #344655;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #176e62;
}
QComboBox QAbstractItemView { background: #151f29; selection-background-color: #176e62; }
QHeaderView::section { background: #1a2834; color: #b9c8d2; padding: 7px; border: none; }
QTableWidget { gridline-color: #243441; }
QTableWidget::item { padding: 5px; }
QScrollArea { border: none; }
QStatusBar { background: #111a23; color: #91a2b3; }
QCheckBox { spacing: 8px; color: #c6d2dc; }
QMessageBox, QFileDialog { background: #101820; }
"""
