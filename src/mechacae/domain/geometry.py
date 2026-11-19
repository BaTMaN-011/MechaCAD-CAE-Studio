"""Sketch geometry metrics and SVG export for the current 2D primitives."""
from __future__ import annotations

import html
import math


def entity_metrics(entity: dict) -> dict[str, float | str]:
    kind = str(entity.get("kind", "rectangle")).lower()
    width, height = float(entity.get("width", 0)), float(entity.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("Sketch entity width and height must be positive.")
    if kind == "circle":
        radius = width / 2
        return {
            "kind": "circle", "area_mm2": math.pi * radius**2,
            "perimeter_mm": 2 * math.pi * radius,
            "diameter_mm": width,
        }
    if kind != "rectangle":
        raise ValueError(f"Unsupported sketch entity: {kind}")
    return {
        "kind": "rectangle", "area_mm2": width * height,
        "perimeter_mm": 2 * (width + height), "width_mm": width, "height_mm": height,
    }


def sketch_totals(entities: list[dict]) -> dict[str, float]:
    """Sum profile area and perimeter; overlapping profiles are counted separately."""
    metrics = [entity_metrics(item) for item in entities]
    return {
        "entity_count": float(len(metrics)),
        "area_mm2": sum(float(row["area_mm2"]) for row in metrics),
        "perimeter_mm": sum(float(row["perimeter_mm"]) for row in metrics),
    }


def export_svg(entities: list[dict], margin_mm: float = 20.0, scale: float = 1.0) -> str:
    """Create a self-contained SVG drawing in a 1-unit-per-mm viewBox."""
    if margin_mm < 0 or scale <= 0:
        raise ValueError("Margin must be non-negative and scale must be positive.")
    if not entities:
        width = height = 300.0
        shapes = '<text x="20" y="40" fill="#617889">Empty sketch</text>'
    else:
        left = min(float(item.get("x", 0)) for item in entities)
        top = min(float(item.get("y", 0)) for item in entities)
        right = max(float(item.get("x", 0)) + float(item.get("width", 0)) for item in entities)
        bottom = max(float(item.get("y", 0)) + float(item.get("height", 0)) for item in entities)
        width = max(1.0, right - left) + 2 * margin_mm
        height = max(1.0, bottom - top) + 2 * margin_mm
        shapes_list = []
        for index, item in enumerate(entities, start=1):
            x = float(item.get("x", 0)) - left + margin_mm
            y = float(item.get("y", 0)) - top + margin_mm
            w, h = float(item.get("width", 0)), float(item.get("height", 0))
            if w <= 0 or h <= 0:
                continue
            if str(item.get("kind", "")).lower() == "circle":
                markup = f'<ellipse cx="{x + w/2:.3f}" cy="{y + h/2:.3f}" rx="{w/2:.3f}" ry="{h/2:.3f}" />'
            else:
                markup = f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" />'
            label = html.escape(str(item.get("name", f"Profile {index}")))
            shapes_list.append(
                f'<g fill="#d8f3ea" fill-opacity="0.28" stroke="#16836d" stroke-width="1.5">'
                f'{markup}<title>{label}</title></g>'
            )
            shapes_list.append(
                f'<text x="{x:.3f}" y="{y - 3:.3f}" font-size="5" fill="#25443b">{label}</text>'
            )
        shapes = "\n".join(shapes_list)
    display_width, display_height = width * scale, height * scale
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{display_width:.3f}" height="{display_height:.3f}"
     viewBox="0 0 {width:.3f} {height:.3f}">
  <title>MechaCAD 2D sketch</title>
  <rect width="100%" height="100%" fill="white" />
  {shapes}
</svg>
'''


def export_dxf(entities: list[dict]) -> str:
    """Export rectangles as four LINE entities and circles as CIRCLE entities."""
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]

    def number(value: float) -> str:
        return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"

    def add_line(x1: float, y1: float, x2: float, y2: float) -> None:
        lines.extend((
            "0", "LINE", "8", "SKETCH",
            "10", number(x1), "20", number(y1), "30", "0",
            "11", number(x2), "21", number(y2), "31", "0",
        ))

    for entity in entities:
        x, y = float(entity.get("x", 0)), float(entity.get("y", 0))
        width, height = float(entity.get("width", 0)), float(entity.get("height", 0))
        if width <= 0 or height <= 0:
            raise ValueError("Cannot export an entity with a zero or negative size.")
        if str(entity.get("kind", "")).lower() == "circle":
            if abs(width - height) > 1e-6:
                raise ValueError("DXF circle entities must have equal width and height.")
            lines.extend((
                "0", "CIRCLE", "8", "SKETCH",
                "10", number(x + width / 2), "20", number(y + height / 2), "30", "0",
                "40", number(width / 2),
            ))
        elif str(entity.get("kind", "")).lower() == "rectangle":
            add_line(x, y, x + width, y)
            add_line(x + width, y, x + width, y + height)
            add_line(x + width, y + height, x, y + height)
            add_line(x, y + height, x, y)
        else:
            raise ValueError(f"Unsupported sketch entity: {entity.get('kind')}")
    lines.extend(("0", "ENDSEC", "0", "EOF", ""))
    return "\n".join(lines)


def import_dxf(text: str) -> list[dict]:
    """Read simple R12 CIRCLE and axis-aligned rectangle exports from this app."""
    raw_lines = [line.strip() for line in text.splitlines()]
    if len(raw_lines) % 2:
        raw_lines = raw_lines[:-1]
    pairs = []
    for index in range(0, len(raw_lines), 2):
        try:
            pairs.append((int(raw_lines[index]), raw_lines[index + 1]))
        except ValueError:
            continue
    entities, in_entities, current = [], False, None
    for code, value in pairs:
        if code == 0 and value == "SECTION":
            current = {"section": True}
        elif code == 2 and current and current.get("section"):
            in_entities = value == "ENTITIES"
            current = None
        elif not in_entities:
            continue
        elif code == 0:
            if current:
                entities.append(current)
            current = {"type": value}
        elif current is not None:
            current.setdefault("fields", {})[code] = value
    if current:
        entities.append(current)

    imported, line_groups = [], []
    rectangle_index = circle_index = 0
    for entity in entities:
        fields = entity.get("fields", {})
        if entity.get("type") == "CIRCLE":
            try:
                cx, cy, radius = float(fields[10]), float(fields[20]), float(fields[40])
            except (KeyError, ValueError):
                continue
            if radius > 0:
                circle_index += 1
                imported.append({
                    "kind": "circle", "name": f"Imported circle {circle_index}",
                    "x": cx - radius, "y": cy - radius, "width": radius * 2, "height": radius * 2,
                })
        elif entity.get("type") == "LINE":
            try:
                line_groups.append((
                    float(fields[10]), float(fields[20]), float(fields[11]), float(fields[21])
                ))
            except (KeyError, ValueError):
                continue

    # This lightweight importer recognizes four consecutive orthogonal lines as
    # one rectangle, matching the entities emitted by export_dxf().
    for offset in range(0, len(line_groups) - 3, 4):
        group = line_groups[offset:offset + 4]
        points = {(x, y) for x1, y1, x2, y2 in group for x, y in ((x1, y1), (x2, y2))}
        if len(points) != 4:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
        corners = {(left, top), (right, top), (right, bottom), (left, bottom)}
        if points == corners and right > left and bottom > top:
            rectangle_index += 1
            imported.append({
                "kind": "rectangle", "name": f"Imported rectangle {rectangle_index}",
                "x": left, "y": top, "width": right - left, "height": bottom - top,
            })
    return imported


def import_svg(text: str) -> list[dict]:
    """Import untransformed rect/ellipse primitives from simple SVG files."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"Could not read SVG XML: {exc}") from exc
    imported = []
    for element in root.iter():
        tag = element.tag.split("}")[-1].lower()
        if tag == "rect":
            try:
                x, y = float(element.get("x", "0")), float(element.get("y", "0"))
                width, height = float(element.get("width", "0")), float(element.get("height", "0"))
            except ValueError:
                continue
            if width > 0 and height > 0:
                imported.append({
                    "kind": "rectangle", "name": f"Imported rectangle {len(imported) + 1}",
                    "x": x, "y": y, "width": width, "height": height,
                })
        elif tag == "ellipse":
            try:
                cx, cy = float(element.get("cx", "0")), float(element.get("cy", "0"))
                rx, ry = float(element.get("rx", "0")), float(element.get("ry", "0"))
            except ValueError:
                continue
            if rx > 0 and abs(rx - ry) < 1e-6:
                imported.append({
                    "kind": "circle", "name": f"Imported circle {len(imported) + 1}",
                    "x": cx - rx, "y": cy - ry, "width": 2 * rx, "height": 2 * ry,
                })
    return imported
