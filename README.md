# MechaCAD & CAE Studio

A Windows desktop school project combining simple 2D CAD, educational CAE, a parts list, and mechatronics calculations. It opens in its own PySide6 window. It does not start a website or a localhost web server. MySQL may run locally on the same PC or on a remote school/hosted server.

## Included features

- Project creation, selection, editing, and deletion.
- Material library with starter references and user-added/editable materials.
- 2D sketch canvas for rectangles and circles; move and delete shapes; see approximate profile area and perimeter.
- Import/export of simple rectangle and circle geometry using the app's SVG and DXF formats.
- Assembly bill of materials with quantities, optional material and volume, estimated unit mass, total assembly mass, and CSV export.
- Linear 2D pin-jointed truss solver using the direct-stiffness method. It reports displacement, reactions, member force and stress; exports model JSON and result CSV.
- Cross-section properties for rectangles, solid and hollow circles, rectangular tubes, and I-sections.
- Elementary beam bending checks for centered point loads or full-span uniform loads on simple supports or cantilevers.
- Shaft torsion, lead-screw motor sizing, gear train estimates, and a DC motor PID response simulator.
- Engineering unit converter for length, area, volume, force, torque, stress, rotational speed, angle, and mass.
- Saved calculations and HTML reports, grouped by project in MySQL.

The engineering tools are classroom estimates with stated assumptions. They are not certified design software.

## Set up and launch without entering terminal commands

1. Install Python 3.10 or newer for Windows from python.org. Enable the Python launcher during setup.
2. Double-click setup_windows.bat. It creates a private .venv folder and installs the app packages. A setup window shows progress; you do not have to type commands.
3. Double-click launch_windows.vbs. The desktop app opens without a console window.

Qt for Python's official setup guide recommends a virtual environment and supports Python 3.10 or newer. The included setup script creates that environment for you. See the [official Qt for Python getting-started guide](https://doc.qt.io/qtforpython-6/gettingstarted.html).

## Set up MySQL

The app does not start a web server. Its MySQL database can be local or remote, and the database itself must already exist. The app creates its tables inside it.

**If MySQL is installed on this PC:** use host localhost, port 3306, your database name (the screenshot shows mahirdb), and the username/password you use for MySQL. For a local connection, the dialog turns TLS off by default. Make sure the MySQL service is running and that the database exists.

**If using a school or hosted MySQL server:** enter the host name/IP, port, database name, username, and password provided by the school/provider. The server must allow your computer to connect, and the account must be allowed to create tables and read/write project data. Keep TLS enabled and select the provider's CA certificate when required.

The app can connect to localhost for MySQL while still remaining a desktop app; localhost is not used to serve the app in a browser.

The connection uses MySQL Connector/Python, which supports TCP/IP and TLS connections. Its connection options include certificate and host identity verification; see the [official MySQL Connector/Python connection arguments](https://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html).

The password is stored in Windows Credential Manager when you select Remember password. Host, database, username, and TLS preferences use Windows application settings. No credentials are written into the project source.

## Build a Windows executable

After setup, double-click build_windows.bat. The build uses PyInstaller in windowed folder mode. The app executable and its support files will appear in dist\MechaCAD-CAE-Studio\. Open MechaCAD-CAE-Studio.exe from that folder; it does not open a terminal window.

PySide6 supports desktop packaging tools such as PyInstaller; Qt also documents its own pyside6-deploy workflow. The included script is a convenience build path and may need adjustment for a particular Windows/Python installation. See the [Qt for Python deployment guide](https://doc.qt.io/qtforpython-6/deployment/index.html).

## Project layout

    main.pyw                         GUI entry point
    src/mechacae/app.py              application startup
    src/mechacae/config.py           saved settings and password storage
    src/mechacae/database.py         MySQL schema and repositories
    src/mechacae/domain/              engineering calculations and file formats
    src/mechacae/ui/                  desktop pages, dialogs, and charts
    requirements.txt                 Python packages
    setup_windows.bat                 one-click environment setup
    launch_windows.vbs                hidden-console app launch
    build_windows.bat                 optional Windows packaging

The project currently contains more than 4,000 lines of Python across the desktop app, database layer, geometry, engineering calculations, assembly workflow, and reports. The line count comes from implemented features rather than generated filler.
