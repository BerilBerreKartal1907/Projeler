"""SQLite tabanlı repository yardımcıları.

Bu dosya, importer'ın ihtiyaç duyduğu temel "upsert" operasyonlarını içerir:
- Student upsert
- Course resolution (opsiyonel)
- Classroom upsert
- Classroom proximity insert
- Course-Student ilişki insert

Not: Şimdilik sadece importer ihtiyacını karşılayan minimum API sunuyoruz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from university_exam_scheduler.db.connection import SQLiteDatabase


@dataclass(slots=True)
class SQLiteRepository:
    """Importer ve servislerin kullanacağı ince DB erişim katmanı."""

    db: SQLiteDatabase

    def upsert_student(
        self,
        *,
        student_no: str,
        full_name: Optional[str] = None,
        faculty_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> int:
        """Öğrenciyi student_no'ya göre ekler veya günceller, student_id döndürür."""
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO students (student_no, full_name, faculty_id, department_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_no) DO UPDATE SET
              full_name=COALESCE(excluded.full_name, students.full_name),
              faculty_id=COALESCE(excluded.faculty_id, students.faculty_id),
              department_id=COALESCE(excluded.department_id, students.department_id)
            ;
            """,
            (student_no, full_name, faculty_id, department_id),
        )
        row = conn.execute(
            "SELECT id FROM students WHERE student_no = ?;",
            (student_no,),
        ).fetchone()
        assert row is not None
        conn.commit()
        return int(row["id"])

    def get_course_id_by_name(self, *, course_name: str) -> Optional[int]:
        """Ders adından course_id bulur (yoksa None)."""
        conn = self.db.connect()
        row = conn.execute(
            "SELECT id FROM courses WHERE name = ?;",
            (course_name,),
        ).fetchone()
        return int(row["id"]) if row else None

    def ensure_classroom(self, *, classroom_name: str, capacity: int = 1, is_exam_eligible: bool = True) -> int:
        """Dersliği adıyla upsert eder ve classroom_id döndürür.

        Yakınlık importunda derslikler dosyada geçebileceği için, derslik yoksa minimal bilgilerle oluşturulur.
        """
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO classrooms (name, capacity, is_exam_eligible)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              capacity=MAX(classrooms.capacity, excluded.capacity),
              is_exam_eligible=excluded.is_exam_eligible
            ;
            """,
            (classroom_name, int(capacity), 1 if is_exam_eligible else 0),
        )
        row = conn.execute("SELECT id FROM classrooms WHERE name=?;", (classroom_name,)).fetchone()
        assert row is not None
        conn.commit()
        return int(row["id"])

    def insert_classroom_proximity(
        self,
        *,
        from_classroom_id: int,
        to_classroom_id: int,
        distance_score: int,
    ) -> None:
        """Derslik yakınlık bilgisini ekler/günceller."""
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO classroom_proximity (from_classroom_id, to_classroom_id, distance_score)
            VALUES (?, ?, ?)
            ON CONFLICT(from_classroom_id, to_classroom_id) DO UPDATE SET
              distance_score=excluded.distance_score
            ;
            """,
            (from_classroom_id, to_classroom_id, int(distance_score)),
        )
        conn.commit()

    def add_student_to_course(self, *, course_id: int, student_id: int) -> None:
        """Öğrenciyi derse kaydeder (tekrar eklemeye dayanıklı)."""
        conn = self.db.connect()
        conn.execute(
            """
            INSERT OR IGNORE INTO course_students (course_id, student_id)
            VALUES (?, ?);
            """,
            (course_id, student_id),
        )
        conn.commit()

    def bulk_add_students_to_course(self, *, course_id: int, student_ids: Iterable[int]) -> None:
        """Bir ders için çok sayıda öğrenci kaydı ekler (performans için)."""
        conn = self.db.connect()
        conn.executemany(
            "INSERT OR IGNORE INTO course_students (course_id, student_id) VALUES (?, ?);",
            [(course_id, sid) for sid in student_ids],
        )
        conn.commit()

