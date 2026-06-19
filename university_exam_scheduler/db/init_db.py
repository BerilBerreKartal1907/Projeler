"""Veritabanı ilk kurulum (schema uygulama).

Bu modül, `schema.sql` dosyasını SQLite veritabanına uygular.
UI veya CLI başlatılırken ilk iş olarak çalıştırılabilir.
"""

from __future__ import annotations

from pathlib import Path

from university_exam_scheduler.config import AppConfig
from university_exam_scheduler.db.connection import SQLiteDatabase


def init_db(config: AppConfig | None = None) -> None:
    """Veritabanı şemasını uygular (idempotent)."""
    cfg = config or AppConfig()

    schema_path = Path(__file__).resolve().parent / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    db = SQLiteDatabase(cfg.db_path)
    db.execute_script(schema_sql)
    db.close()

