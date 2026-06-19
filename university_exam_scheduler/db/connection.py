"""SQLite bağlantı yönetimi.

Amaç:
- Tek bir yerden bağlantı açmak
- Foreign key desteğini aktif etmek
- Row factory ile daha okunabilir sonuçlar döndürmek
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class SQLiteDatabase:
    """SQLite DB bağlantısını yöneten basit sınıf."""

    db_path: Path
    _conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Bağlantı yoksa açar ve döndürür."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            # SQLite foreign keys default kapalıdır.
            self._conn.execute("PRAGMA foreign_keys = ON;")
        return self._conn

    def close(self) -> None:
        """Bağlantıyı kapatır."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def execute_script(self, sql: str) -> None:
        """Çoklu SQL komutlarını tek seferde çalıştırır (schema gibi)."""
        conn = self.connect()
        conn.executescript(sql)
        conn.commit()

