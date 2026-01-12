-- University Exam Scheduler - SQLite Schema
-- Not: SQLite'da foreign key kısıtlarının çalışması için PRAGMA foreign_keys=ON gerekir.

BEGIN;

-- Fakülteler
CREATE TABLE IF NOT EXISTS faculties (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

-- Bölümler / Programlar (her bölüm bir fakülteye bağlıdır)
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  faculty_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  code TEXT,
  UNIQUE (faculty_id, name),
  UNIQUE (code),
  FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE RESTRICT
);

-- Öğretim üyeleri
CREATE TABLE IF NOT EXISTS instructors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name TEXT NOT NULL,
  email TEXT UNIQUE
);

-- Öğretim üyesi müsaitlikleri (gün bazlı)
-- weekday: 0=Monday ... 6=Sunday
CREATE TABLE IF NOT EXISTS instructor_availability (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instructor_id INTEGER NOT NULL,
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
  is_available INTEGER NOT NULL CHECK (is_available IN (0, 1)),
  UNIQUE (instructor_id, weekday),
  FOREIGN KEY (instructor_id) REFERENCES instructors(id) ON DELETE CASCADE
);

-- Dersler
-- duration_minutes: 30/60/90/120
CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_id INTEGER NOT NULL,
  faculty_id INTEGER NOT NULL,
  instructor_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  student_count INTEGER NOT NULL CHECK (student_count >= 0),
  duration_minutes INTEGER NOT NULL CHECK (duration_minutes IN (30, 60, 90, 120)),
  exam_type TEXT NOT NULL,
  special_notes TEXT,
  UNIQUE (department_id, name),
  FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
  FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE RESTRICT,
  FOREIGN KEY (instructor_id) REFERENCES instructors(id) ON DELETE RESTRICT
);

-- Öğrenciler
CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_no TEXT NOT NULL UNIQUE,
  full_name TEXT,
  department_id INTEGER,
  faculty_id INTEGER,
  FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
  FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE SET NULL
);

-- Ders-Öğrenci eşlemesi (öğrenci listelerinden import edilecek)
CREATE TABLE IF NOT EXISTS course_students (
  course_id INTEGER NOT NULL,
  student_id INTEGER NOT NULL,
  PRIMARY KEY (course_id, student_id),
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Derslikler
CREATE TABLE IF NOT EXISTS classrooms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  capacity INTEGER NOT NULL CHECK (capacity > 0),
  is_exam_eligible INTEGER NOT NULL CHECK (is_exam_eligible IN (0, 1))
);

-- Derslik yakınlık (A dersliği B dersliğine ne kadar yakın?)
-- distance_score: küçük değer daha yakın (ör: 1 en yakın).
CREATE TABLE IF NOT EXISTS classroom_proximity (
  from_classroom_id INTEGER NOT NULL,
  to_classroom_id INTEGER NOT NULL,
  distance_score INTEGER NOT NULL CHECK (distance_score >= 0),
  PRIMARY KEY (from_classroom_id, to_classroom_id),
  FOREIGN KEY (from_classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
  FOREIGN KEY (to_classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

-- Sınavlar (planlama çıktısı)
-- Bir ders için yalnızca 1 sınav kaydı olmalı: UNIQUE(course_id)
-- start_at: ISO format string (YYYY-MM-DD HH:MM) tutulur; planlama katmanı bunu datetime ile yönetir.
CREATE TABLE IF NOT EXISTS exams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id INTEGER NOT NULL UNIQUE,
  start_at TEXT NOT NULL,
  end_at TEXT NOT NULL,
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- Sınav-Derslik atamaları (kapasite yetmezse bir sınav birden çok dersliğe bölünebilir)
CREATE TABLE IF NOT EXISTS exam_rooms (
  exam_id INTEGER NOT NULL,
  classroom_id INTEGER NOT NULL,
  assigned_capacity INTEGER NOT NULL CHECK (assigned_capacity >= 0),
  PRIMARY KEY (exam_id, classroom_id),
  FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
  FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE RESTRICT
);

-- Aynı anda aynı dersliğe iki sınav atanamaz:
-- SQLite'da "overlap" kontrolü için tek bir CHECK yeterli değildir.
-- Bu kural planlama algoritması + uygulama katmanı tarafından enforced edilecek.
-- Yine de performans için sorgu indeksleri eklenir.

CREATE INDEX IF NOT EXISTS idx_courses_instructor ON courses(instructor_id);
CREATE INDEX IF NOT EXISTS idx_course_students_student ON course_students(student_id);
CREATE INDEX IF NOT EXISTS idx_exam_rooms_classroom ON exam_rooms(classroom_id);
CREATE INDEX IF NOT EXISTS idx_exams_weekday_start ON exams(weekday, start_at);

COMMIT;

