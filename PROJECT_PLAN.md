# Project plan

## Technical choices

- Python 3.10+ and PySide6 Widgets for a native Windows desktop interface.
- MySQL Connector/Python for remote TCP/IP database access.
- NumPy for the direct-stiffness truss solution.
- Windows Credential Manager through keyring for optional password storage.
- JSON columns encoded as text for sketches, analysis inputs, and saved calculation data.
- No local web server; MySQL can be local or remote.

## Project demonstrations

1. Create a project and add/edit a material.
2. Draw a part profile, move it on the millimetre grid, and round-trip its supported shapes through SVG or DXF.
3. Add assembly components, assign materials, estimate mass, and export a BOM.
4. Load the sample truss, adjust supports or forces, solve it, inspect its scaled deformation, and export JSON/CSV.
5. Compare section properties and run a beam, shaft, gear, lead-screw, or DC motor PID calculation.
6. Save calculations to the current project and export a report.

## Database tables

- projects: project names, descriptions, and timestamps.
- materials: mechanical properties and notes.
- components: project BOM, quantities, geometry volume, material, and unit mass.
- designs: named 2D sketch entity collections per project.
- analysis_runs: truss input models and solved result records.
- design_checks: section, beam, shaft, gear, motor sizing, and control calculation inputs/results.

On first successful connection, the app creates missing tables in the selected MySQL database and seeds a small set of clearly marked educational material references.

## Growth path toward a full school submission

- Add parametric sketch constraints, dimensions, layers, and drawing annotations.
- Add element-by-element material selection, member safety checks, and visual stress coloring.
- Add versioned schema migrations, change history, and project archive import/restore.
- Add more measured/sourced material data and report formatting.
- Add screenshots, requirements, engineering assumptions, and a concise user guide for the final school presentation.

The engineering models intentionally remain bounded and explain their assumptions; they are demonstrations of core concepts rather than replacements for professional tools.
