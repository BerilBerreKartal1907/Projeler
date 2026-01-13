"""
Minimal excel_processor modülü.

Bu repo içinde frontend-backend entegrasyonu bozulmasın diye, app.py'nin import ettiği
fonksiyon ve sınıfları sağlar. Projede tam işlev gerekirse bu modül genişletilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd


@dataclass
class ExcelProcessor:
    """Sınıf listesi Excel'lerini okumak için yardımcı sınıf (minimal)."""

    def extract_course_code_from_filename(self, filename: str) -> Optional[str]:
        name = Path(filename).stem.upper()
        # Basit yakalama: dosya adı içinde 3 harf + 3 rakam varsa onu döndür
        # Örn: YZM332_... -> YZM332
        import re

        m = re.search(r"[A-ZÇĞİÖŞÜ]{2,4}\d{2,4}", name)
        return m.group(0) if m else None

    def read_excel_file(self, path: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        try:
            df = pd.read_excel(path)
            return df, None
        except Exception as e:
            return None, str(e)

    def extract_student_data(self, df: pd.DataFrame) -> Tuple[list[dict[str, str]], Optional[str]]:
        """
        Beklenen kolonlar değişebileceği için esnek okur:
        - öğrenci no: "Öğrenci No", "No", "StudentNo" vb.
        - ad soyad: "Ad Soyad", "Ad", "İsim" vb.
        """
        if df is None or df.empty:
            return [], "Excel boş"

        cols = {c.lower(): c for c in df.columns}
        num_col = None
        name_col = None

        for key in ["öğrenci no", "ogrenci no", "no", "studentno", "student_number", "numara"]:
            if key in cols:
                num_col = cols[key]
                break

        for key in ["ad soyad", "adı soyadı", "isim", "name", "öğrenci adı", "ogrenci adi"]:
            if key in cols:
                name_col = cols[key]
                break

        if not num_col:
            # ilk kolonu numara kabul et
            num_col = df.columns[0]

        students: list[dict[str, str]] = []
        for _, row in df.iterrows():
            num = str(row.get(num_col, "")).strip()
            if not num or num.lower() == "nan":
                continue
            name = str(row.get(name_col, "")).strip() if name_col else ""
            students.append({"number": num, "name": name})
        return students, None


def import_proximity_to_db(path: str, db: Any, Classroom: Any, ClassroomProximity: Any) -> dict[str, Any]:
    """
    Beklenen Excel kolonları (örnek):
    - primary_classroom, nearby_classroom, distance, is_adjacent
    """
    try:
        df = pd.read_excel(path)
        imported = 0
        for _, row in df.iterrows():
            p_name = str(row.get("primary_classroom", "")).strip()
            n_name = str(row.get("nearby_classroom", "")).strip()
            if not p_name or not n_name:
                continue

            primary = Classroom.query.filter_by(name=p_name).first()
            nearby = Classroom.query.filter_by(name=n_name).first()
            if not primary or not nearby:
                continue

            rel = ClassroomProximity(
                primary_classroom_id=primary.id,
                nearby_classroom_id=nearby.id,
                distance=float(row.get("distance", 0) or 0),
                is_adjacent=bool(row.get("is_adjacent", False)),
                notes=str(row.get("notes", "") or ""),
            )
            db.session.add(rel)
            imported += 1
        db.session.commit()
        return {"status": "success", "imported": imported}
    except Exception as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}


def import_capacity_to_db(path: str, db: Any, Classroom: Any, Course: Any) -> dict[str, Any]:
    """
    Basit kapasite importu (örnek):
    - name, capacity
    """
    try:
        df = pd.read_excel(path)
        updated = 0
        created = 0
        for _, row in df.iterrows():
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            cap = int(row.get("capacity", 0) or 0)
            classroom = Classroom.query.filter_by(name=name).first()
            if classroom:
                classroom.capacity = cap
                updated += 1
            else:
                db.session.add(Classroom(name=name, capacity=cap))
                created += 1
        db.session.commit()
        return {"status": "success", "updated": updated, "created": created}
    except Exception as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}


def import_teachers_from_excel(path: str, db: Any) -> dict[str, Any]:
    """
    Öğretim üyesi importu (minimal). Beklenen kolonlar:
    - name, title, faculty, department_id (opsiyonel)
    """
    try:
        df = pd.read_excel(path)
        imported = 0
        # app.py içinde import_teachers_from_excel kullanıldığı için burada app import etmek
        # circular import yaratır. Mevcut projede bu fonksiyon, app.py içindeki endpointten
        # db ve modellerle çağrılacak şekilde genişletilmelidir.
        return {"status": "error", "message": "import_teachers_from_excel: Bu minimal sürümde desteklenmiyor."}

        # unreachable (kept for future extension)
    except Exception as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}

