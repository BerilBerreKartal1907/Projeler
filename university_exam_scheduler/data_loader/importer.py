"""CSV/TXT dosyalarından veriyi okuyup SQLite'a aktaran importer.

Bu modülün amacı:
- Dosyadan okuma (parse) -> normalize -> doğrulama -> DB'ye yazma
- Elle SQLite importu gerektirmemek

Beklenen dosya türleri:
1) Sınıf/öğrenci listeleri (13 adet)
   - Her dosya tipik olarak bir dersin (veya bir sınıfın) öğrenci listesidir.
   - Kurs/ders kimliği dosya içindeki bir kolondan veya dosya adından elde edilebilir.
2) Derslik yakınlık (mesafe) dosyası (1 adet)
   - from_classroom, to_classroom, distance_score (veya benzeri isimlerle)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from university_exam_scheduler.data_loader.parsers import ParsedTable, iter_paths, read_delimited_file
from university_exam_scheduler.data_loader.types import ClassroomProximityRow, StudentRow
from university_exam_scheduler.repositories.sqlite_repo import SQLiteRepository


def _norm_key(s: str) -> str:
    """Kolon isimlerini normalize eder (küçük harf, boşluk/altçizgi uyumlu)."""
    return "".join(ch for ch in s.strip().lower().replace(" ", "_") if ch.isalnum() or ch == "_")


@dataclass(frozen=True, slots=True)
class ClassListImportConfig:
    """Sınıf/öğrenci listesi import ayarları.

    Bu config esnek tasarlanmıştır; farklı okul dosyaları farklı kolon isimleri kullanabilir.
    """

    # Dosya içinde ders adını veren kolon adları (olası alternatifler)
    course_name_columns: tuple[str, ...] = ("ders", "ders_adi", "course", "course_name")
    # Öğrenci no kolon adları
    student_no_columns: tuple[str, ...] = ("ogrenci_no", "ogrenci_numarasi", "student_no", "no", "numara")
    # Öğrenci ad/soyad kolon adları
    student_name_columns: tuple[str, ...] = ("ad_soyad", "ogrenci_adi", "student_name", "full_name", "name")

    # Eğer dosyada ders adı yoksa, dosya adından ders adı üretmek için kullanılacak kural
    # Örn: "MAT101.csv" -> "MAT101"
    fallback_course_name_from_filename: bool = True


@dataclass(frozen=True, slots=True)
class ProximityImportConfig:
    """Derslik yakınlık import ayarları."""

    from_columns: tuple[str, ...] = ("from", "from_classroom", "derslik", "derslik1", "a", "kaynak")
    to_columns: tuple[str, ...] = ("to", "to_classroom", "derslik2", "b", "hedef")
    distance_columns: tuple[str, ...] = ("distance", "mesafe", "distance_score", "skor", "puan")

    # Derslik dosyasında kapasite yoksa minimal kapasite ile oluşturulur
    default_classroom_capacity: int = 1


class ImportErrorWithContext(RuntimeError):
    """Importer hatalarını daha anlaşılır mesajla sarmak için."""


def _pick_column(row: dict[str, str], candidates: tuple[str, ...]) -> Optional[str]:
    """Row dict içinde aday kolonlardan ilk bulunanı döndürür."""
    normalized = {_norm_key(k): v for k, v in row.items()}
    for cand in candidates:
        if _norm_key(cand) in normalized:
            value = normalized[_norm_key(cand)]
            if value is not None:
                value2 = str(value).strip()
                if value2 != "":
                    return value2
    return None


def _ensure_dict_rows(table: ParsedTable, *, file_path: Path) -> list[dict[str, str]]:
    """Table satırlarını dict formatına çevirir; header yoksa hata verir.

    Not: Header olmayan dosyalar da olabilir; ancak doğru map için kullanıcıya format netleşince
    'kolon indeksleri' ile de destek eklenebilir. Şimdilik güvenli tarafta kalıyoruz.
    """
    dict_rows: list[dict[str, str]] = []
    for r in table.rows:
        if not isinstance(r, dict):
            raise ImportErrorWithContext(
                f"{file_path.name}: Header bulunamadı veya parse edilemedi. "
                "Lütfen dosyada kolon başlıkları olsun (örn: ogrenci_no, ad_soyad, ders)."
            )
        dict_rows.append({str(k): str(v) for k, v in r.items()})
    return dict_rows


def import_class_lists(
    repo: SQLiteRepository,
    files: Iterable[str | Path],
    *,
    config: ClassListImportConfig | None = None,
) -> None:
    """13 adet sınıf/öğrenci listesi dosyasını DB'ye aktarır.

    DB'ye eklenenler:
    - `students` (student_no bazlı upsert)
    - `course_students` (ders-öğrenci ilişkisi)

    Önemli:
    - Ders (course) kaydı DB'de yoksa, ilişki kurulamaz. Bu durumda hata fırlatır.
      (İleride: importer ders oluşturma desteği eklenebilir.)
    """
    cfg = config or ClassListImportConfig()

    for path in iter_paths(files):
        table = read_delimited_file(path)
        rows = _ensure_dict_rows(table, file_path=path)

        # Ders adını dosyadan bulmaya çalış.
        course_name = None
        for row in rows:
            course_name = _pick_column(row, cfg.course_name_columns)
            if course_name:
                break
        if not course_name and cfg.fallback_course_name_from_filename:
            course_name = path.stem.strip()

        if not course_name:
            raise ImportErrorWithContext(
                f"{path.name}: Ders adı bulunamadı. Dosyada 'ders'/'ders_adi' gibi bir kolon olmalı "
                "ya da dosya adı ders adı olmalı."
            )

        course_id = repo.get_course_id_by_name(course_name=course_name)
        if course_id is None:
            raise ImportErrorWithContext(
                f"{path.name}: '{course_name}' dersi DB'de bulunamadı. "
                "Önce ders kaydını ekleyin (UI veya ileride eklenecek course-import)."
            )

        # Öğrencileri upsert edip toplu ilişki kur.
        student_ids: list[int] = []
        for row in rows:
            student_no = _pick_column(row, cfg.student_no_columns)
            if not student_no:
                # Satır bozuksa atla yerine hata da tercih edilebilir; burada import'u kırmamak için atlıyoruz.
                continue
            full_name = _pick_column(row, cfg.student_name_columns)
            sid = repo.upsert_student(student_no=student_no, full_name=full_name)
            student_ids.append(sid)

        repo.bulk_add_students_to_course(course_id=course_id, student_ids=student_ids)


def import_classroom_proximity(
    repo: SQLiteRepository,
    file: str | Path,
    *,
    config: ProximityImportConfig | None = None,
) -> None:
    """Derslik yakınlık (mesafe) dosyasını DB'ye aktarır.

    DB'ye eklenenler:
    - `classrooms` (dosyada geçen derslik adları yoksa minimal bilgilerle oluşturulur)
    - `classroom_proximity` (A -> B mesafe skoru)
    """
    cfg = config or ProximityImportConfig()
    path = file if isinstance(file, Path) else Path(file)

    table = read_delimited_file(path)
    rows = _ensure_dict_rows(table, file_path=path)

    for row in rows:
        from_name = _pick_column(row, cfg.from_columns)
        to_name = _pick_column(row, cfg.to_columns)
        dist_raw = _pick_column(row, cfg.distance_columns)

        if not from_name or not to_name or dist_raw is None:
            # Eksik satırları sessizce atlıyoruz; istenirse strict moda alınabilir.
            continue
        try:
            dist = int(float(dist_raw))
        except ValueError:
            continue

        from_id = repo.ensure_classroom(
            classroom_name=from_name,
            capacity=cfg.default_classroom_capacity,
            is_exam_eligible=True,
        )
        to_id = repo.ensure_classroom(
            classroom_name=to_name,
            capacity=cfg.default_classroom_capacity,
            is_exam_eligible=True,
        )
        repo.insert_classroom_proximity(from_classroom_id=from_id, to_classroom_id=to_id, distance_score=dist)

