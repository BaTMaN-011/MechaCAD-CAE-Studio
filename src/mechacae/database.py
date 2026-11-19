"""Remote MySQL gateway and schema management."""
from __future__ import annotations

import json
from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError

from .config import DatabaseConfig


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS projects (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(160) NOT NULL,
        description TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_projects_updated (updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS materials (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(160) NOT NULL UNIQUE,
        category VARCHAR(80) NOT NULL,
        youngs_modulus_mpa DECIMAL(14,3) NOT NULL,
        poisson_ratio DECIMAL(8,5) NOT NULL,
        density_kg_m3 DECIMAL(12,3) NOT NULL,
        yield_strength_mpa DECIMAL(14,3) NOT NULL,
        notes TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS components (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        project_id BIGINT UNSIGNED NOT NULL,
        part_number VARCHAR(120) NOT NULL,
        name VARCHAR(180) NOT NULL,
        material_id BIGINT UNSIGNED NULL,
        quantity INT UNSIGNED NOT NULL DEFAULT 1,
        volume_mm3 DECIMAL(18,3) NOT NULL DEFAULT 0,
        unit_mass_kg DECIMAL(18,9) NOT NULL DEFAULT 0,
        notes TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        CONSTRAINT fk_component_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        CONSTRAINT fk_component_material FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE SET NULL,
        INDEX idx_components_project (project_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS designs (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        project_id BIGINT UNSIGNED NOT NULL,
        name VARCHAR(160) NOT NULL,
        entities_json LONGTEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_design_project_name (project_id, name),
        CONSTRAINT fk_design_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS analysis_runs (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        project_id BIGINT UNSIGNED NOT NULL,
        name VARCHAR(160) NOT NULL,
        model_json LONGTEXT NOT NULL,
        results_json LONGTEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_analysis_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        INDEX idx_analysis_project_created (project_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS design_checks (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        project_id BIGINT UNSIGNED NOT NULL,
        name VARCHAR(160) NOT NULL,
        check_type VARCHAR(80) NOT NULL,
        inputs_json LONGTEXT NOT NULL,
        results_json LONGTEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_design_check_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        INDEX idx_design_checks_project_created (project_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
)

STARTER_MATERIALS = (
    ("Structural steel (educational)", "Metal", 200000.0, 0.30, 7850.0, 250.0,
     "Approximate classroom reference values. Confirm material certificates for real designs."),
    ("Aluminum 6061-T6 (educational)", "Metal", 68900.0, 0.33, 2700.0, 276.0,
     "Approximate classroom reference values. Confirm temper and supplier data for real designs."),
    ("Stainless steel 304 (educational)", "Metal", 193000.0, 0.29, 8000.0, 205.0,
     "Approximate classroom reference values. Confirm grade and supplier data for real designs."),
    ("ABS plastic (educational)", "Polymer", 2300.0, 0.35, 1040.0, 40.0,
     "Approximate values; properties vary with grade, temperature and manufacturing."),
)


class DatabaseManager:
    """Keeps one authenticated connection to a local or remote MySQL database."""

    def __init__(self) -> None:
        self._connection = None
        self.config: DatabaseConfig | None = None

    @property
    def connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected()

    def disconnect(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None
                self.config = None

    def connect(self, config: DatabaseConfig) -> None:
        """Connect, check access, install tables, and add starter materials."""
        self.disconnect()
        options: dict[str, Any] = {
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "user": config.username,
            "password": config.password,
            "connection_timeout": 8,
            "autocommit": False,
            "use_pure": True,
        }
        if config.use_tls:
            if config.ssl_ca:
                options["ssl_ca"] = config.ssl_ca
            options.update({
                "ssl_disabled": False,
                "ssl_verify_cert": config.verify_tls,
                "ssl_verify_identity": config.verify_tls,
            })
        else:
            options["ssl_disabled"] = True
        try:
            self._connection = mysql.connector.connect(**options)
            self.config = config
            self._create_schema()
        except MySQLError:
            self.disconnect()
            raise

    def _ready_connection(self):
        if self._connection is None:
            raise RuntimeError("Connect to a MySQL database first.")
        try:
            self._connection.ping(reconnect=True, attempts=2, delay=1)
        except MySQLError:
            self.disconnect()
            raise
        return self._connection

    def _create_schema(self) -> None:
        connection = self._ready_connection()
        cursor = connection.cursor()
        try:
            for statement in SCHEMA:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
        self._seed_materials()

    def _seed_materials(self) -> None:
        connection = self._ready_connection()
        cursor = connection.cursor()
        try:
            cursor.executemany(
                """INSERT IGNORE INTO materials
                (name, category, youngs_modulus_mpa, poisson_ratio, density_kg_m3,
                 yield_strength_mpa, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                STARTER_MATERIALS,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    def _query(self, sql: str, params: tuple = (), *, fetch: bool = False):
        connection = self._ready_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            result = cursor.fetchall() if fetch else cursor.lastrowid
            if not fetch:
                connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    def list_projects(self) -> list[dict[str, Any]]:
        return self._query(
            "SELECT id, name, description, created_at, updated_at FROM projects ORDER BY updated_at DESC",
            fetch=True,
        )

    def create_project(self, name: str, description: str) -> int:
        return int(self._query(
            "INSERT INTO projects (name, description) VALUES (%s, %s)",
            (name.strip(), description.strip()),
        ))

    def update_project(self, project_id: int, name: str, description: str) -> None:
        self._query(
            "UPDATE projects SET name = %s, description = %s WHERE id = %s",
            (name.strip(), description.strip(), project_id),
        )

    def delete_project(self, project_id: int) -> None:
        self._query("DELETE FROM projects WHERE id = %s", (project_id,))

    def project_counts(self) -> dict[str, int]:
        rows = self._query(
            """SELECT
                (SELECT COUNT(*) FROM projects) AS projects,
                (SELECT COUNT(*) FROM designs) AS designs,
                (SELECT COUNT(*) FROM analysis_runs) AS analyses,
                (SELECT COUNT(*) FROM materials) AS materials,
                (SELECT COUNT(*) FROM design_checks) AS checks""",
            fetch=True,
        )
        return {key: int(value) for key, value in rows[0].items()}

    def list_materials(self, search: str = "") -> list[dict[str, Any]]:
        pattern = f"%{search.strip()}%"
        return self._query(
            """SELECT id, name, category, youngs_modulus_mpa, poisson_ratio,
                      density_kg_m3, yield_strength_mpa, notes
               FROM materials
               WHERE name LIKE %s OR category LIKE %s
               ORDER BY category, name""",
            (pattern, pattern),
            fetch=True,
        )

    def add_material(
        self,
        name: str,
        category: str,
        youngs_modulus_mpa: float,
        poisson_ratio: float,
        density_kg_m3: float,
        yield_strength_mpa: float,
        notes: str,
    ) -> int:
        return int(self._query(
            """INSERT INTO materials
               (name, category, youngs_modulus_mpa, poisson_ratio, density_kg_m3, yield_strength_mpa, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (name.strip(), category.strip(), youngs_modulus_mpa, poisson_ratio,
             density_kg_m3, yield_strength_mpa, notes.strip()),
        ))

    def update_material(
        self, material_id: int, name: str, category: str, youngs_modulus_mpa: float,
        poisson_ratio: float, density_kg_m3: float, yield_strength_mpa: float, notes: str,
    ) -> None:
        self._query(
            """UPDATE materials SET name = %s, category = %s, youngs_modulus_mpa = %s,
               poisson_ratio = %s, density_kg_m3 = %s, yield_strength_mpa = %s, notes = %s
               WHERE id = %s""",
            (name.strip(), category.strip(), youngs_modulus_mpa, poisson_ratio,
             density_kg_m3, yield_strength_mpa, notes.strip(), material_id),
        )

    def list_components(self, project_id: int) -> list[dict[str, Any]]:
        return self._query(
            """SELECT c.id, c.part_number, c.name, c.material_id, c.quantity, c.volume_mm3,
                      c.unit_mass_kg, c.notes, m.name AS material_name
               FROM components c LEFT JOIN materials m ON m.id = c.material_id
               WHERE c.project_id = %s ORDER BY c.part_number, c.name""",
            (project_id,),
            fetch=True,
        )

    def save_component(
        self, project_id: int, part_number: str, name: str, material_id: int | None,
        quantity: int, volume_mm3: float, unit_mass_kg: float, notes: str,
        component_id: int | None = None,
    ) -> int:
        values = (part_number.strip(), name.strip(), material_id, quantity, volume_mm3,
                  unit_mass_kg, notes.strip())
        if component_id is not None:
            self._query(
                """UPDATE components SET part_number = %s, name = %s, material_id = %s,
                   quantity = %s, volume_mm3 = %s, unit_mass_kg = %s, notes = %s
                   WHERE id = %s AND project_id = %s""",
                values + (component_id, project_id),
            )
            return component_id
        return int(self._query(
            """INSERT INTO components
               (project_id, part_number, name, material_id, quantity, volume_mm3, unit_mass_kg, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (project_id,) + values,
        ))

    def delete_component(self, component_id: int, project_id: int) -> None:
        self._query("DELETE FROM components WHERE id = %s AND project_id = %s", (component_id, project_id))

    def load_design(self, project_id: int, name: str = "Main Sketch") -> dict[str, Any] | None:
        rows = self._query(
            "SELECT id, name, entities_json FROM designs WHERE project_id = %s AND name = %s LIMIT 1",
            (project_id, name),
            fetch=True,
        )
        if not rows:
            return None
        row = rows[0]
        try:
            row["entities"] = json.loads(row.pop("entities_json"))
        except (TypeError, json.JSONDecodeError):
            row["entities"] = []
        return row

    def save_design(self, project_id: int, entities: list[dict[str, Any]], name: str = "Main Sketch") -> int:
        payload = json.dumps(entities, ensure_ascii=False)
        existing = self.load_design(project_id, name)
        if existing:
            self._query(
                "UPDATE designs SET entities_json = %s WHERE id = %s",
                (payload, existing["id"]),
            )
            return int(existing["id"])
        return int(self._query(
            "INSERT INTO designs (project_id, name, entities_json) VALUES (%s, %s, %s)",
            (project_id, name, payload),
        ))

    def save_analysis(self, project_id: int, model: dict, results: dict, name: str) -> int:
        return int(self._query(
            """INSERT INTO analysis_runs (project_id, name, model_json, results_json)
               VALUES (%s, %s, %s, %s)""",
            (project_id, name.strip(), json.dumps(model), json.dumps(results)),
        ))

    def list_analyses(self, project_id: int) -> list[dict[str, Any]]:
        return self._query(
            """SELECT id, name, created_at, results_json FROM analysis_runs
               WHERE project_id = %s ORDER BY created_at DESC""",
            (project_id,),
            fetch=True,
        )

    def save_design_check(
        self, project_id: int, name: str, check_type: str, inputs: dict, results: dict
    ) -> int:
        return int(self._query(
            """INSERT INTO design_checks
               (project_id, name, check_type, inputs_json, results_json)
               VALUES (%s, %s, %s, %s, %s)""",
            (project_id, name.strip(), check_type, json.dumps(inputs), json.dumps(results)),
        ))

    def list_design_checks(self, project_id: int) -> list[dict[str, Any]]:
        return self._query(
            """SELECT id, name, check_type, created_at, inputs_json, results_json
               FROM design_checks WHERE project_id = %s ORDER BY created_at DESC""",
            (project_id,),
            fetch=True,
        )
