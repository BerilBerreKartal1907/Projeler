"""Uygulama yapılandırması (config).

Bu dosya, veritabanı yolu gibi ortamdan bağımsız sabitleri tek yerde toplar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Uygulama konfigürasyon değerleri."""

    # Proje içi veri klasörü (db dosyası burada tutulur)
    data_dir: Path = Path(__file__).resolve().parent / "data"
    db_path: Path = Path(__file__).resolve().parent / "data" / "app.db"

