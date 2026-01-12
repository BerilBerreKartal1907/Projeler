"""
db.py

SQLite bağlantısı, şema oluşturma ve küçük yardımcı fonksiyonlar.
Bu katman, uygulamanın geri kalanını (GUI/Planner) veritabanı detaylarından ayırır.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "exam_scheduler.sqlite3"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    SQLite bağlantısı oluşturur.
    - foreign_keys: referans bütünlüğünü garanti etmek için açık olmalı.
    - row_factory: sonuçları dict-benzeri okumayı kolaylaştırır.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def executescript(conn: sqlite3.Connection, statements: Iterable[str]) -> None:
    """
    Çoklu SQL statement çalıştırma yardımcısı.
    """
    with conn:
        for s in statements:
            conn.execute(s)


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Veritabanı tablolarını oluşturur (idempotent: IF NOT EXISTS).

    Modelleme Notları:
    - Rol tabanlı kullanıcı yönetimi: users(role)
    - Akademik yapı: faculties -> departments -> programs
    - Ders: courses (department/program/instructor bağlı)
    - Öğrenci çakışması kısıtı:
        Gerçek sistemde öğrenci bazında kayıt gerekir.
        Akademik projelerde daha pratik yaklaşım: "öğrenci grubu/cohort" kullanmak.
        Aynı öğrenci grubu aynı zaman diliminde 2 sınava giremez.
        (course_student_groups tablosu ile M:N ilişki)
    - Derslik uygunluğu: rooms(is_exam_suitable) + kapasite + zone (yakınlık için)
    - Yakınlık: rooms(zone) basit yaklaşım (aynı zone => yakın).
    - Zaman dilimleri: timeslots
    - Plan: exams + exam_rooms (kapasite yetmezse sınavı birden fazla dersliğe bölmek için)
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema = [
        # Kullanıcılar
        """
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            role            TEXT NOT NULL CHECK(role IN ('ADMIN', 'DEPT_OFFICER', 'INSTRUCTOR', 'STUDENT')),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
        # Fakülte/Bölüm/Program
        """
        CREATE TABLE IF NOT EXISTS faculties (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL UNIQUE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS departments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            UNIQUE(faculty_id, name),
            FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS programs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id   INTEGER NOT NULL,
            name            TEXT NOT NULL,
            UNIQUE(department_id, name),
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
        );
        """,
        # Öğretim üyesi ve müsait günleri
        """
        CREATE TABLE IF NOT EXISTS instructors (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name       TEXT NOT NULL UNIQUE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS instructor_availability (
            instructor_id   INTEGER NOT NULL,
            weekday         INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6), -- 0=Mon ... 6=Sun
            PRIMARY KEY (instructor_id, weekday),
            FOREIGN KEY (instructor_id) REFERENCES instructors(id) ON DELETE CASCADE
        );
        """,
        # Öğrenci grupları (çakışma modellemesi)
        """
        CREATE TABLE IF NOT EXISTS student_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id  INTEGER NOT NULL,
            name        TEXT NOT NULL, -- örn: "1. Sınıf A" / "2025 Güz Cohort"
            UNIQUE(program_id, name),
            FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
        );
        """,
        # Dersler
        """
        CREATE TABLE IF NOT EXISTS courses (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id       INTEGER NOT NULL,
            program_id          INTEGER NOT NULL,
            name                TEXT NOT NULL,
            instructor_id       INTEGER NOT NULL,
            student_count       INTEGER NOT NULL CHECK(student_count >= 0),
            duration_min        INTEGER NOT NULL CHECK(duration_min > 0),
            exam_type           TEXT NOT NULL, -- örn: "Vize", "Final", "Bütünleme", "Quiz"
            -- Özel durumları JSON/serbest metin olarak saklamak (akademik projelerde esnek)
            special_notes       TEXT,
            -- Dersin sınavı belirli günlerde olsun isteniyorsa (opsiyonel)
            allowed_weekdays    TEXT, -- örn: "0,2,4" (Mon,Wed,Fri)
            forbidden_weekdays  TEXT, -- örn: "5,6" (Sat,Sun)
            preferred_zone      TEXT, -- yakın derslik tercihine yardımcı
            UNIQUE(program_id, name),
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id) ON DELETE RESTRICT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS course_student_groups (
            course_id        INTEGER NOT NULL,
            student_group_id INTEGER NOT NULL,
            PRIMARY KEY (course_id, student_group_id),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (student_group_id) REFERENCES student_groups(id) ON DELETE CASCADE
        );
        """,
        # Derslikler
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL UNIQUE,
            capacity            INTEGER NOT NULL CHECK(capacity >= 0),
            zone                TEXT NOT NULL, -- "A Blok", "B Blok", "Merkez", vb. (yakınlık için basit yaklaşım)
            is_exam_suitable    INTEGER NOT NULL CHECK(is_exam_suitable IN (0,1)) DEFAULT 1
        );
        """,
        # Zaman dilimleri
        """
        CREATE TABLE IF NOT EXISTS timeslots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date_iso        TEXT NOT NULL, -- "YYYY-MM-DD"
            start_time      TEXT NOT NULL, -- "HH:MM"
            end_time        TEXT NOT NULL, -- "HH:MM"
            UNIQUE(date_iso, start_time, end_time)
        );
        """,
        # Üretilen sınavlar
        """
        CREATE TABLE IF NOT EXISTS exams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id       INTEGER NOT NULL UNIQUE, -- Her ders için sadece 1 sınav zamanı (ZORUNLU kısıt)
            timeslot_id     INTEGER NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (timeslot_id) REFERENCES timeslots(id) ON DELETE RESTRICT
        );
        """,
        # Bir sınavın bir veya birden fazla dersliğe bölünmesi
        """
        CREATE TABLE IF NOT EXISTS exam_rooms (
            exam_id             INTEGER NOT NULL,
            room_id             INTEGER NOT NULL,
            assigned_students   INTEGER NOT NULL CHECK(assigned_students >= 0),
            PRIMARY KEY (exam_id, room_id),
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE RESTRICT
        );
        """,
        # Planlama sırasında "aynı saat" çakışmasını hızlı kontrol için index
        "CREATE INDEX IF NOT EXISTS idx_exams_timeslot ON exams(timeslot_id);",
        "CREATE INDEX IF NOT EXISTS idx_exam_rooms_room ON exam_rooms(room_id);",
    ]

    conn = get_connection(db_path)
    executescript(conn, schema)
    conn.close()


def reset_plan(conn: sqlite3.Connection) -> None:
    """
    Üretilmiş sınav planını temizler.
    NOT: Dersleri/derslikleri silmez; sadece üretilen planı kaldırır.
    """
    with conn:
        conn.execute("DELETE FROM exam_rooms;")
        conn.execute("DELETE FROM exams;")

