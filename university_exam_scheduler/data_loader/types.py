"""Importer tipleri.

Bu dosyadaki dataclass'lar, dosyalardan okunan satırların normalize edilmiş temsilidir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class StudentRow:
    """Bir öğrenci satırı (dosyadan okunur)."""

    student_no: str
    full_name: Optional[str] = None


@dataclass(frozen=True, slots=True)
class EnrollmentRow:
    """Bir ders-kayıt satırı: öğrenci bir derse kayıtlı."""

    course_name: str
    student_no: str


@dataclass(frozen=True, slots=True)
class ClassroomProximityRow:
    """Derslik yakınlık/mesafe satırı."""

    from_classroom: str
    to_classroom: str
    distance_score: int

