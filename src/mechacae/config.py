"""Desktop preferences and OS-backed storage for database credentials."""
from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import QSettings


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    use_tls: bool = True
    verify_tls: bool = True
    ssl_ca: str = ""


class AppSettings:
    """Store non-secret preferences in QSettings and secrets in keyring."""
    SERVICE_NAME = "MechaCAD-CAE-Studio"

    def __init__(self) -> None:
        self._settings = QSettings("MechaCADSchoolProject", "MechaCAD-CAE-Studio")

    @staticmethod
    def _keyring():
        try:
            import keyring
            return keyring
        except Exception:
            return None

    @staticmethod
    def credential_key(host: str, database: str, username: str) -> str:
        return f"{username}@{host}/{database}"

    def load_connection(self) -> dict[str, object] | None:
        host = str(self._settings.value("mysql/host", "")).strip()
        database = str(self._settings.value("mysql/database", "")).strip()
        username = str(self._settings.value("mysql/username", "")).strip()
        if not host or not database or not username:
            return None
        keyring = self._keyring()
        password = ""
        if keyring:
            try:
                password = keyring.get_password(
                    self.SERVICE_NAME,
                    self.credential_key(host, database, username),
                ) or ""
            except Exception:
                password = ""
        return {
            "host": host,
            "port": int(self._settings.value("mysql/port", 3306)),
            "database": database,
            "username": username,
            "password": password,
            "use_tls": self._settings.value("mysql/use_tls", True, type=bool),
            "verify_tls": self._settings.value("mysql/verify_tls", True, type=bool),
            "ssl_ca": str(self._settings.value("mysql/ssl_ca", "")),
        }

    def save_connection(self, config: DatabaseConfig, remember_password: bool) -> None:
        self._settings.setValue("mysql/host", config.host)
        self._settings.setValue("mysql/port", config.port)
        self._settings.setValue("mysql/database", config.database)
        self._settings.setValue("mysql/username", config.username)
        self._settings.setValue("mysql/use_tls", config.use_tls)
        self._settings.setValue("mysql/verify_tls", config.verify_tls)
        self._settings.setValue("mysql/ssl_ca", config.ssl_ca)
        keyring = self._keyring()
        if not keyring:
            return
        key = self.credential_key(config.host, config.database, config.username)
        try:
            if remember_password and config.password:
                keyring.set_password(self.SERVICE_NAME, key, config.password)
            else:
                try:
                    keyring.delete_password(self.SERVICE_NAME, key)
                except Exception:
                    pass
        except Exception:
            # The app remains usable; the user can enter the password again next time.
            pass
