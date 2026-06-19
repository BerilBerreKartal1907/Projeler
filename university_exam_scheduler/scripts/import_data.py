"""Komut satırından importer çalıştırma örneği.

Bu script, dosyaların elle SQLite'a import edilmesi yerine uygulamanın kendi importer'ını kullanır.
Örnek kullanım:

  python -m university_exam_scheduler.scripts.import_data \
    --init-db \
    --class-list "path/to/MAT101.csv" \
    --class-list "path/to/FIZ102.csv" \
    --proximity "path/to/derslik_mesafe.csv"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from university_exam_scheduler.config import AppConfig
from university_exam_scheduler.data_loader.importer import import_class_lists, import_classroom_proximity
from university_exam_scheduler.db.connection import SQLiteDatabase
from university_exam_scheduler.db.init_db import init_db
from university_exam_scheduler.repositories.sqlite_repo import SQLiteRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="University Exam Scheduler - Data Importer")
    parser.add_argument("--init-db", action="store_true", help="Şema kurulumunu çalıştırır")
    parser.add_argument(
        "--class-list",
        action="append",
        default=[],
        help="Sınıf/öğrenci listesi dosyası (CSV/TXT). 13 adet verilebilir.",
    )
    parser.add_argument("--proximity", default=None, help="Derslik yakınlık/mesafe dosyası (CSV/TXT)")
    args = parser.parse_args()

    cfg = AppConfig()
    if args.init_db:
        init_db(cfg)

    db = SQLiteDatabase(cfg.db_path)
    repo = SQLiteRepository(db)

    if args.class_list:
        import_class_lists(repo, [Path(p) for p in args.class_list])
    if args.proximity:
        import_classroom_proximity(repo, Path(args.proximity))

    db.close()


if __name__ == "__main__":
    main()

