"""
KOSTÜ Sınav Programı Yönetim Sistemi
Backend API - Flask + SQLAlchemy + MySQL

Bu dosya özellikle "Bölüm/Program Yetkilisi" yetkilerini (ders ekleme, öğretim üyesi,
özel durum güncelleme, yetki kısıtları) kod seviyesinde uygular.
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import datetime
import io
import pandas as pd
import bcrypt
import jwt
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Tuple

from excel_processor import (
    ExcelProcessor,
    import_proximity_to_db,
    import_capacity_to_db,
    import_teachers_from_excel,
)

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)
CORS(app)

# ==================== KONFİGÜRASYON ====================

# DATABASE_URL ZORUNLU - MySQL olmalı
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError(
        "❌ DATABASE_URL çevre değişkeni ayarlanmamış!\n"
        "Lütfen .env dosyasında şu format ile tanımlayın:\n"
        "DATABASE_URL=mysql+pymysql://username:password@host:port/database\n"
        "\nÖrnek:\n"
        "DATABASE_URL=mysql+pymysql://root:password@localhost:3306/kostu_exam_db"
    )

# MySQL formatını kontrol et
if not db_url.startswith("mysql+pymysql"):
    if db_url.startswith("mysql://"):
        db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
    else:
        raise RuntimeError(
            f"❌ Geçersiz DATABASE_URL: {db_url}\n"
            "Lütfen MySQL formatında girin:\n"
            "mysql+pymysql://username:password@host:port/database"
        )

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_SORT_KEYS"] = False

# JWT ve Güvenlik
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["JWT_EXPIRATION_HOURS"] = int(os.getenv("JWT_EXPIRATION_HOURS", 24))
app.config["JWT_ALGORITHM"] = os.getenv("JWT_ALGORITHM", "HS256")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ==================== MODELLERİ ====================


class User(db.Model):
    """Kullanıcı Modeli"""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Roller:
    # - admin
    # - bolum_yetkilisi
    # - program_yetkilisi
    # - hoca
    # - ogrenci
    role = db.Column(db.String(50), nullable=False)

    # İlişkiler
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    program_id = db.Column(db.Integer, db.ForeignKey("program.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def set_password(self, password: str) -> None:
        """Şifreyi hash'le ve kaydet"""
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Şifreyi doğrula"""
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "teacher_id": self.teacher_id,
            "student_id": self.student_id,
            "department_id": self.department_id,
            "program_id": self.program_id,
        }


class Faculty(db.Model):
    """Fakülte Modeli"""

    __tablename__ = "faculty"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    departments = db.relationship("Department", backref="faculty", lazy=True)


class Department(db.Model):
    """Bölüm Modeli"""

    __tablename__ = "department"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)


class Program(db.Model):
    """Program Modeli (Bölüm içindeki Lisans/Yüksek Lisans vb.)"""

    __tablename__ = "program"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("name", "department_id", name="unique_program_per_dept"),)


class Teacher(db.Model):
    """Öğretim Üyesi Modeli"""

    __tablename__ = "teacher"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)

    # Unvan (Prof. Dr., Doç. Dr., Dr. Öğr. Üyesi, vb.)
    title = db.Column(db.String(100), nullable=True)

    # Fakülte/Bölüm (Excel import)
    faculty = db.Column(db.String(200), nullable=True)

    # Müsaitlik (virgülle ayrılmış gün listesi: Mon,Tue,Wed,Thu,Fri)
    available_days = db.Column(db.String(100), default="Mon,Tue,Wed,Thu,Fri")

    # Ek müsaitlik bilgisi (JSON string olarak tutulur)
    availability_details = db.Column(db.Text, nullable=True)

    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    user = db.relationship("User", backref="teacher_user", lazy=True, uselist=False)
    courses = db.relationship("Course", backref="teacher", lazy=True)


class Student(db.Model):
    """Öğrenci Modeli"""

    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=True)
    program_id = db.Column(db.Integer, db.ForeignKey("program.id"), nullable=True)

    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    user = db.relationship("User", backref="student_user", lazy=True, uselist=False)
    enrollments = db.relationship("Enrollment", backref="student", lazy=True)


class Course(db.Model):
    """Ders Modeli"""

    __tablename__ = "course"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    code = db.Column(db.String(50), nullable=True, unique=True)  # YZM332, BLM111 vb.

    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    program_id = db.Column(db.Integer, db.ForeignKey("program.id"), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)

    student_count = db.Column(db.Integer, default=0)

    # Sınav Özellikleri (özel durum alanları dahil)
    has_exam = db.Column(db.Boolean, default=True)  # Dersin sınavı var mı?
    exam_duration = db.Column(db.Integer, default=60)  # Dakika (30, 60, 90, 120)
    exam_type = db.Column(db.String(100), default="written")  # yazılı, uygulama, proje vb.
    exam_date = db.Column(db.DateTime, nullable=True)  # Sınavın tarihi (planlama sonrası)

    special_room = db.Column(db.String(500), nullable=True)  # Özel sınıf (lab, dekanlık vb.)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    enrollments = db.relationship("Enrollment", backref="course", lazy=True)
    exams = db.relationship("Exam", backref="course", lazy=True)


class Enrollment(db.Model):
    """Ders Kayıtı Modeli"""

    __tablename__ = "enrollment"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)

    enrolled_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("student_id", "course_id", name="unique_enrollment"),)


class Classroom(db.Model):
    """Derslik Modeli"""

    __tablename__ = "classroom"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)  # D101, A205 vb.
    capacity = db.Column(db.Integer, nullable=False)

    is_available = db.Column(db.Boolean, default=True)
    is_special = db.Column(db.Boolean, default=False)  # Lab, dekanlık vb.?
    special_type = db.Column(db.String(100), nullable=True)  # lab, computer_lab, auditorium vb.

    exams = db.relationship("Exam", backref="room", lazy=True)


class ClassroomProximity(db.Model):
    """Derslik Yakınlık Modeli"""

    __tablename__ = "classroom_proximity"

    id = db.Column(db.Integer, primary_key=True)
    primary_classroom_id = db.Column(db.Integer, db.ForeignKey("classroom.id"), nullable=False, index=True)
    nearby_classroom_id = db.Column(db.Integer, db.ForeignKey("classroom.id"), nullable=False, index=True)

    is_adjacent = db.Column(db.Boolean, default=False)
    distance = db.Column(db.Float, nullable=True)  # Metre cinsinden
    notes = db.Column(db.String(500), nullable=True)

    primary_classroom = db.relationship("Classroom", foreign_keys=[primary_classroom_id])
    nearby_classroom = db.relationship("Classroom", foreign_keys=[nearby_classroom_id])


class Exam(db.Model):
    """Sınav Modeli"""

    __tablename__ = "exam"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey("classroom.id"), nullable=False, index=True)

    slot_start = db.Column(db.DateTime, nullable=False, index=True)
    duration = db.Column(db.Integer, nullable=False)  # Dakika

    # Eski format (legacy)
    slot = db.Column(db.String(200), nullable=True)

    status = db.Column(db.String(50), default="scheduled")  # scheduled, ongoing, completed, cancelled

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        course = Course.query.get(self.course_id)
        room = Classroom.query.get(self.room_id)
        teacher = course.teacher if course else None

        return {
            "id": self.id,
            "course_id": self.course_id,
            "course_name": course.name if course else None,
            "course_code": course.code if course else None,
            "department_id": course.department_id if course else None,
            "program_id": course.program_id if course else None,
            "room_id": self.room_id,
            "room_name": room.name if room else None,
            "teacher_id": teacher.id if teacher else None,
            "teacher_name": teacher.name if teacher else None,
            "slot_start": self.slot_start.isoformat(),
            "slot_end": (self.slot_start + datetime.timedelta(minutes=self.duration)).isoformat(),
            "duration": self.duration,
            "status": self.status,
        }


class ExcelImportLog(db.Model):
    """Excel İthal Günlüğü"""

    __tablename__ = "excel_import_log"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    import_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(50), default="success")  # success, failed, warning
    records_imported = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)


# ==================== YETKİ / SCOPE YARDIMCILARI ====================


def _get_current_user():
    """Decorator request alanından user objesini güvenle getirir."""
    uid = getattr(request, "user_id", None)
    if not uid:
        return None
    return User.query.get(uid)


def _get_scope():
    """
    Kullanıcının yönetim kapsamını döndürür.

    - admin: (None, None) -> tüm kapsam
    - bolum_yetkilisi: (department_id, None)
    - program_yetkilisi: (department_id, program_id)
    """
    user = _get_current_user()
    if not user:
        return (None, None)

    if user.role == "admin":
        return (None, None)

    if user.role == "bolum_yetkilisi":
        return (user.department_id, None)

    if user.role == "program_yetkilisi":
        dept_id = user.department_id
        prog_id = user.program_id
        if prog_id:
            prog = Program.query.get(prog_id)
            if prog:
                dept_id = prog.department_id
        return (dept_id, prog_id)

    return (None, None)


def _enforce_scope_for_department(department_id: Optional[int]):
    """Bölüm yetkilisi/program yetkilisi kendi kapsamı dışına çıkamasın."""
    user = _get_current_user()
    if not user or user.role == "admin":
        return

    scope_dept_id, _scope_prog_id = _get_scope()
    if not scope_dept_id:
        raise PermissionError("Bu işlem için bölüm ataması yapılmamış.")

    if department_id and int(department_id) != int(scope_dept_id):
        raise PermissionError("Sadece kendi bölümünüzde işlem yapabilirsiniz.")


def _enforce_scope_for_program(program_id: Optional[int]):
    """Program yetkilisi sadece kendi programında işlem yapabilsin."""
    user = _get_current_user()
    if not user or user.role == "admin":
        return

    scope_dept_id, scope_prog_id = _get_scope()
    if user.role == "program_yetkilisi":
        if not scope_prog_id:
            raise PermissionError("Program yetkilisi için program ataması yapılmamış.")
        if program_id and int(program_id) != int(scope_prog_id):
            raise PermissionError("Sadece kendi programınızda işlem yapabilirsiniz.")
    elif user.role == "bolum_yetkilisi":
        # bölüm yetkilisi program filtresi girebilir ama sadece kendi bölümündeki programlara
        if program_id:
            prog = Program.query.get(int(program_id))
            if prog and scope_dept_id and int(prog.department_id) != int(scope_dept_id):
                raise PermissionError("Sadece kendi bölümünüzün programlarında işlem yapabilirsiniz.")


def _course_in_scope(course: Course) -> bool:
    user = _get_current_user()
    if not user:
        return False
    if user.role == "admin":
        return True
    scope_dept_id, scope_prog_id = _get_scope()
    if user.role == "bolum_yetkilisi":
        return bool(scope_dept_id and course.department_id == scope_dept_id)
    if user.role == "program_yetkilisi":
        return bool(scope_prog_id and course.program_id == scope_prog_id)
    if user.role == "hoca":
        return bool(user.teacher_id and course.teacher_id == user.teacher_id)
    return False


def _teacher_in_scope(teacher: Teacher) -> bool:
    user = _get_current_user()
    if not user:
        return False
    if user.role == "admin":
        return True
    scope_dept_id, _scope_prog_id = _get_scope()
    if user.role in ["bolum_yetkilisi", "program_yetkilisi"]:
        return bool(scope_dept_id and teacher.department_id == scope_dept_id)
    return False


# ==================== YARDIMCI FONKSİYONLAR ====================


def init_db():
    """Veritabanını başlat"""
    import time
    import logging

    logger = logging.getLogger(__name__)

    max_retries = 10
    retry_count = 0

    while retry_count < max_retries:
        try:
            with app.app_context():
                db.create_all()
                logger.info("✅ Veritabanı başarıyla başlatıldı")
                seed_default_users()  # Demo kullanıcıları ekle
                return
        except Exception as e:
            retry_count += 1
            wait_time = 2**retry_count
            logger.warning(f"⚠️ Veritabanı bağlantısı başarısız (Deneme {retry_count}/{max_retries}): {str(e)}")
            logger.warning(f"⏳ {wait_time} saniye sonra tekrar denenecek...")
            time.sleep(wait_time)

    logger.error(f"❌ Veritabanı {max_retries} denemeden sonra başlatılamadı")
    raise Exception("Database initialization failed after retries")


def seed_default_users():
    """Demo kullanıcıları ekle (sadece tablo boşsa)"""
    if User.query.first():
        return

    fak = Faculty(name="Mühendislik Fakültesi")
    db.session.add(fak)
    db.session.flush()

    dept = Department(name="Bilgisayar Mühendisliği", faculty_id=fak.id)
    db.session.add(dept)
    db.session.flush()

    prog = Program(name="Lisans", department_id=dept.id)
    db.session.add(prog)
    db.session.flush()

    teacher = Teacher(name="Dr. Ahmet Yılmaz", department_id=dept.id)
    db.session.add(teacher)
    db.session.flush()

    student = Student(student_number="2020001", name="Mehmet Şahin", program_id=prog.id)
    db.session.add(student)
    db.session.flush()

    demo_users = [
        {"username": "admin", "password": "admin123", "role": "admin"},
        {"username": "bolum", "password": "bolum123", "role": "bolum_yetkilisi", "department_id": dept.id},
        {"username": "program", "password": "program123", "role": "program_yetkilisi", "department_id": dept.id, "program_id": prog.id},
        {"username": "hoca", "password": "hoca123", "role": "hoca", "teacher_id": teacher.id, "department_id": dept.id},
        {"username": "ogrenci", "password": "ogrenci123", "role": "ogrenci", "student_id": student.id, "program_id": prog.id},
    ]

    for u in demo_users:
        user = User(username=u["username"], role=u["role"])
        user.set_password(u["password"])
        user.teacher_id = u.get("teacher_id")
        user.student_id = u.get("student_id")
        user.department_id = u.get("department_id")
        user.program_id = u.get("program_id")
        db.session.add(user)

    # Demo derslikler + demo dersler (UI boş görünmesin diye)
    classrooms = [
        Classroom(name="A101", capacity=120),
        Classroom(name="A102", capacity=120),
        Classroom(name="B201", capacity=80),
        Classroom(name="B202", capacity=80),
    ]
    for c in classrooms:
        db.session.add(c)
    db.session.flush()

    demo_courses = [
        Course(
            name="Algoritma ve Programlama",
            code="YZM332",
            teacher_id=teacher.id,
            department_id=dept.id,
            program_id=prog.id,
            student_count=110,
            exam_duration=60,
            exam_type="written",
        ),
        Course(
            name="Veri Tabanı Sistemleri",
            code="BLM111",
            teacher_id=teacher.id,
            department_id=dept.id,
            program_id=prog.id,
            student_count=75,
            exam_duration=60,
            exam_type="written",
        ),
    ]
    for c in demo_courses:
        db.session.add(c)

    db.session.commit()


def generate_token(user_id, role, username):
    """JWT token oluştur"""
    payload = {
        "user_id": user_id,
        "role": role,
        "username": username,
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
    }
    token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])
    return token


def verify_token(token):
    """JWT token'ı doğrula"""
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ==================== GÜVENLİK MIDDLEWARE'İ ====================


def require_auth(roles=None):
    """Kimlik doğrulama ve rol kontrolü decorator'ı"""
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

            if not token:
                return jsonify({"status": "error", "message": "Token eksik"}), 401

            payload = verify_token(token)
            if not payload:
                return jsonify({"status": "error", "message": "Geçersiz token"}), 401

            if roles and payload["role"] not in roles:
                return jsonify({"status": "error", "message": "Yetersiz izin"}), 403

            request.user_id = payload["user_id"]
            request.user_role = payload["role"]
            request.username = payload["username"]

            # Bölüm yetkilisi -> bölüm zorunlu
            if payload["role"] == "bolum_yetkilisi":
                user = User.query.get(payload["user_id"])
                if not user or not user.department_id:
                    return jsonify(
                        {"status": "error", "message": "Bölüm yetkilisi için bölüm ataması yapılmamış."}
                    ), 403

            # Program yetkilisi -> program zorunlu
            if payload["role"] == "program_yetkilisi":
                user = User.query.get(payload["user_id"])
                if not user or not user.program_id:
                    return jsonify(
                        {"status": "error", "message": "Program yetkilisi için program ataması yapılmamış."}
                    ), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator


# ==================== LOGIN VE AUTH ENDPOINTS ====================


@app.route("/api/login", methods=["POST"])
def login():
    """Login endpoint"""
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Kullanıcı adı ve şifre gerekli"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"status": "error", "message": "Hatalı kullanıcı adı veya şifre"}), 401

    token = generate_token(user.id, user.role, user.username)
    return jsonify({"status": "success", "token": token, "user": user.to_dict()})


@app.route("/api/logout", methods=["POST"])
def logout():
    """Logout endpoint (frontend'de token silinir)"""
    return jsonify({"status": "success", "message": "Başarıyla çıkış yapıldı"})


@app.route("/api/me", methods=["GET"])
@require_auth()
def get_me():
    """Giriş yapan kullanıcının bilgilerini getir"""
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({"status": "error", "message": "Kullanıcı bulunamadı"}), 404
    return jsonify({"status": "success", "user": user.to_dict()})


@app.route("/api/register", methods=["POST"])
@require_auth(roles=["admin"])
def register_user():
    """Yeni kullanıcı oluştur (admin only)"""
    data = request.get_json() or {}

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "ogrenci")

    if not username or not password:
        return jsonify({"status": "error", "message": "Kullanıcı adı ve şifre gerekli"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Bu kullanıcı adı zaten kullanılıyor"}), 409

    user = User(username=username, role=role)
    user.set_password(password)

    # Opsiyonel ilişkiler
    user.teacher_id = data.get("teacher_id")
    user.student_id = data.get("student_id")
    user.department_id = data.get("department_id")
    user.program_id = data.get("program_id")

    db.session.add(user)
    db.session.commit()

    return jsonify({"status": "success", "user": user.to_dict(), "message": "Kullanıcı oluşturuldu"}), 201


@app.route("/api/users/<int:user_id>", methods=["PUT"])
@require_auth(roles=["admin"])
def admin_update_user(user_id: int):
    """Admin: kullanıcıya bölüm/program/teacher/student ataması yapar."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "Kullanıcı bulunamadı"}), 404

    data = request.get_json() or {}

    if "role" in data:
        user.role = data["role"]
    if "department_id" in data:
        user.department_id = data["department_id"]
    if "program_id" in data:
        user.program_id = data["program_id"]
    if "teacher_id" in data:
        user.teacher_id = data["teacher_id"]
    if "student_id" in data:
        user.student_id = data["student_id"]

    db.session.commit()
    return jsonify({"status": "success", "user": user.to_dict(), "message": "Kullanıcı güncellendi"})


# ==================== TEMEL ENDPOINTS ====================


@app.route("/")
def home():
    return jsonify(
        {
            "status": "ok",
            "message": "KOSTÜ Sınav Programı Yönetim Sistemi",
            "version": "2.0.0",
            "api_docs": "/api/docs",
        }
    )


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat(), "database": "mysql"})


# ==================== BÖLÜM / PROGRAM ENDPOINTS ====================


@app.route("/api/departments", methods=["GET"])
@require_auth()
def get_departments():
    """Tüm bölümleri getir (yetkili kullanıcılar kendi kapsamını filtreler)."""
    query = Department.query
    if request.user_role in ["bolum_yetkilisi", "program_yetkilisi"]:
        scope_dept_id, _scope_prog_id = _get_scope()
        if scope_dept_id:
            query = query.filter_by(id=scope_dept_id)
    departments = query.all()
    return jsonify(
        {
            "status": "success",
            "data": [{"id": d.id, "name": d.name, "faculty_id": d.faculty_id} for d in departments],
        }
    )


@app.route("/api/faculties", methods=["GET"])
@require_auth()
def get_faculties():
    """Tüm fakülteleri getir"""
    facilities = Faculty.query.all()
    return jsonify({"status": "success", "data": [{"id": f.id, "name": f.name} for f in facilities]})


# Frontend uyumu için eski isim (legacy)
@app.route("/api/facilities", methods=["GET"])
@require_auth()
def get_facilities():
    """Tüm fakülteleri getir (legacy endpoint: /api/facilities)"""
    return get_faculties()


@app.route("/api/programs", methods=["GET", "POST"])
@require_auth()
def manage_programs():
    """
    Program yönetimi:
    - GET: Admin hepsini, bölüm yetkilisi kendi bölümünün programlarını, program yetkilisi sadece kendi programını görür.
    - POST: Admin veya bölüm yetkilisi program ekleyebilir. Bölüm yetkilisi sadece kendi bölümüne ekler.
    """
    if request.method == "GET":
        query = Program.query
        dept_id = request.args.get("department_id", type=int)

        if request.user_role == "program_yetkilisi":
            _dept, prog = _get_scope()
            query = query.filter_by(id=prog)
        elif request.user_role == "bolum_yetkilisi":
            scope_dept_id, _ = _get_scope()
            query = query.filter_by(department_id=scope_dept_id)
            if dept_id and dept_id != scope_dept_id:
                return jsonify({"status": "error", "message": "Sadece kendi bölümünüzün programları."}), 403
        else:
            if dept_id:
                query = query.filter_by(department_id=dept_id)

        programs = query.all()
        return jsonify(
            {
                "status": "success",
                "data": [{"id": p.id, "name": p.name, "department_id": p.department_id} for p in programs],
            }
        )

    if request.user_role not in ["admin", "bolum_yetkilisi"]:
        return jsonify({"status": "error", "message": "Yetersiz izin"}), 403

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    department_id = data.get("department_id")
    if not name:
        return jsonify({"status": "error", "message": "Program adı gerekli"}), 400

    if request.user_role == "bolum_yetkilisi":
        scope_dept_id, _ = _get_scope()
        department_id = scope_dept_id

    if not department_id:
        return jsonify({"status": "error", "message": "department_id gerekli"}), 400

    try:
        _enforce_scope_for_department(int(department_id))
    except PermissionError as e:
        return jsonify({"status": "error", "message": str(e)}), 403

    program = Program(name=name, department_id=int(department_id))
    db.session.add(program)
    db.session.commit()
    return jsonify({"status": "success", "id": program.id, "message": "Program eklendi"}), 201


# ==================== ÖĞRETIM ÜYESİ ENDPOINTS ====================


@app.route("/api/teachers", methods=["GET", "POST"])
@require_auth()
def manage_teachers():
    """Öğretim üyeleri yönetimi"""
    if request.method == "GET":
        dept_id = request.args.get("department_id", type=int)
        query = Teacher.query

        if request.user_role in ["bolum_yetkilisi", "program_yetkilisi"]:
            scope_dept_id, _scope_prog_id = _get_scope()
            query = query.filter_by(department_id=scope_dept_id)
            if dept_id and dept_id != scope_dept_id:
                return jsonify({"status": "error", "message": "Sadece kendi bölümünüz."}), 403
        elif dept_id:
            query = query.filter_by(department_id=dept_id)

        teachers = query.all()
        return jsonify(
            {
                "status": "success",
                "data": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "department_id": t.department_id,
                        "title": t.title or "",
                        "faculty": t.faculty or "",
                        "available_days": t.available_days,
                        "availability_details": t.availability_details,
                        "email": t.email,
                        "phone": t.phone,
                    }
                    for t in teachers
                ],
            }
        )

    if request.user_role not in ["admin", "bolum_yetkilisi", "program_yetkilisi"]:
        return jsonify({"status": "error", "message": "Yetersiz izin"}), 403

    data = request.get_json() or {}

    dept_id = data.get("department_id")
    if request.user_role in ["bolum_yetkilisi", "program_yetkilisi"]:
        scope_dept_id, _ = _get_scope()
        dept_id = scope_dept_id

    try:
        _enforce_scope_for_department(int(dept_id) if dept_id else None)
    except PermissionError as e:
        return jsonify({"status": "error", "message": str(e)}), 403

    teacher = Teacher(
        name=(data.get("name") or "").strip(),
        department_id=dept_id,
        title=data.get("title"),
        faculty=data.get("faculty"),
        available_days=data.get("available_days", "Mon,Tue,Wed,Thu,Fri"),
        availability_details=data.get("availability_details"),
        email=data.get("email"),
        phone=data.get("phone"),
    )

    db.session.add(teacher)
    db.session.commit()
    return jsonify({"status": "success", "id": teacher.id, "message": "Öğretim üyesi eklendi"}), 201


@app.route("/api/teachers/<int:teacher_id>", methods=["PUT", "DELETE"])
@require_auth(roles=["admin", "bolum_yetkilisi", "program_yetkilisi"])
def update_delete_teacher(teacher_id):
    """Öğretim üyesi güncelleme veya silme"""
    teacher = Teacher.query.get(teacher_id)
    if not teacher:
        return jsonify({"status": "error", "message": "Öğretim üyesi bulunamadı"}), 404

    if not _teacher_in_scope(teacher):
        return jsonify({"status": "error", "message": "Bu öğretim üyesi üzerinde yetkiniz yok."}), 403

    if request.method == "PUT":
        data = request.get_json() or {}

        if "name" in data:
            teacher.name = data["name"]
        if "available_days" in data:
            teacher.available_days = data["available_days"]
        if "availability_details" in data:
            teacher.availability_details = data["availability_details"]
        if "email" in data:
            teacher.email = data["email"]
        if "phone" in data:
            teacher.phone = data["phone"]
        if "title" in data:
            teacher.title = data["title"]
        if "faculty" in data:
            teacher.faculty = data["faculty"]

        if "department_id" in data:
            # admin dışında bölüm değiştirmeyi kapat (kapsam dışına çıkma riski)
            if request.user_role != "admin":
                return jsonify({"status": "error", "message": "Bölüm değişikliği sadece admin tarafından yapılabilir."}), 403
            teacher.department_id = data["department_id"]

        db.session.commit()
        return jsonify({"status": "success", "message": "Öğretim üyesi güncellendi"})

    # DELETE
    courses = Course.query.filter_by(teacher_id=teacher_id).count()
    if courses > 0:
        return jsonify({"status": "error", "message": f"Bu öğretim üyesine {courses} ders atanmış."}), 400

    db.session.delete(teacher)
    db.session.commit()
    return jsonify({"status": "success", "message": "Öğretim üyesi silindi"})


# ==================== DERS ENDPOINTS ====================


@app.route("/api/courses", methods=["GET", "POST"])
@require_auth()
def manage_courses():
    """Ders yönetimi"""
    if request.method == "GET":
        teacher_id = request.args.get("teacher_id", type=int)
        dept_id = request.args.get("department_id", type=int)
        program_id = request.args.get("program_id", type=int)

        query = Course.query

        if request.user_role == "hoca":
            user = _get_current_user()
            query = query.filter_by(teacher_id=user.teacher_id)

        elif request.user_role == "ogrenci":
            user = _get_current_user()
            enrollments = Enrollment.query.filter_by(student_id=user.student_id).all()
            course_ids = [e.course_id for e in enrollments]
            query = query.filter(Course.id.in_(course_ids))

        elif request.user_role in ["bolum_yetkilisi", "program_yetkilisi"]:
            scope_dept_id, scope_prog_id = _get_scope()
            query = query.filter_by(department_id=scope_dept_id)
            if request.user_role == "program_yetkilisi":
                query = query.filter_by(program_id=scope_prog_id)

        # Ek filtreler (scope kontrolü ile)
        if teacher_id:
            query = query.filter_by(teacher_id=teacher_id)

        if dept_id:
            try:
                _enforce_scope_for_department(dept_id)
            except PermissionError as e:
                return jsonify({"status": "error", "message": str(e)}), 403
            query = query.filter_by(department_id=dept_id)

        if program_id:
            try:
                _enforce_scope_for_program(program_id)
            except PermissionError as e:
                return jsonify({"status": "error", "message": str(e)}), 403
            query = query.filter_by(program_id=program_id)

        courses = query.all()
        return jsonify(
            {
                "status": "success",
                "data": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "code": c.code,
                        "teacher_id": c.teacher_id,
                        "department_id": c.department_id,
                        "program_id": c.program_id,
                        "student_count": c.student_count,
                        "has_exam": c.has_exam,
                        "exam_duration": c.exam_duration,
                        "exam_type": c.exam_type,
                        "special_room": c.special_room,
                        "notes": c.notes,
                    }
                    for c in courses
                ],
            }
        )

    # POST - Admin / Bölüm Yetkilisi / Program Yetkilisi ekleyebilir
    if request.user_role not in ["admin", "bolum_yetkilisi", "program_yetkilisi"]:
        return jsonify({"status": "error", "message": "Yetersiz izin"}), 403

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"status": "error", "message": "Ders adı gerekli"}), 400

    dept_id = data.get("department_id")
    prog_id = data.get("program_id")

    # Scope zorlamaları
    if request.user_role == "bolum_yetkilisi":
        scope_dept_id, _ = _get_scope()
        dept_id = scope_dept_id
    elif request.user_role == "program_yetkilisi":
        scope_dept_id, scope_prog_id = _get_scope()
        dept_id = scope_dept_id
        prog_id = scope_prog_id

    try:
        _enforce_scope_for_department(int(dept_id) if dept_id else None)
        _enforce_scope_for_program(int(prog_id) if prog_id else None)
    except PermissionError as e:
        return jsonify({"status": "error", "message": str(e)}), 403

    course = Course(
        name=name,
        code=(data.get("code") or None),
        teacher_id=data.get("teacher_id"),
        department_id=dept_id,
        program_id=prog_id,
        student_count=int(data.get("student_count", 0)),
        # Özel durum alanları
        has_exam=bool(data.get("has_exam", True)),
        exam_duration=int(data.get("exam_duration", 60)),
        exam_type=data.get("exam_type", "written"),
        special_room=data.get("special_room"),
        notes=data.get("notes"),
    )

    db.session.add(course)
    db.session.commit()
    return jsonify({"status": "success", "id": course.id, "message": "Ders eklendi"}), 201


@app.route("/api/courses/<int:course_id>", methods=["PUT", "DELETE"])
@require_auth(roles=["admin", "bolum_yetkilisi", "program_yetkilisi"])
def update_delete_course(course_id):
    """Ders güncelleme veya silme"""
    course = Course.query.get(course_id)
    if not course:
        return jsonify({"status": "error", "message": "Ders bulunamadı"}), 404

    if not _course_in_scope(course):
        return jsonify({"status": "error", "message": "Bu ders üzerinde yetkiniz yok."}), 403

    if request.method == "PUT":
        data = request.get_json() or {}

        # Temel alanlar
        if "name" in data:
            course.name = data["name"]
        if "code" in data:
            course.code = data["code"]
        if "teacher_id" in data:
            course.teacher_id = data["teacher_id"]
        if "student_count" in data:
            course.student_count = int(data["student_count"])

        # Özel durum alanları (PDF "özel durum" kapsamı)
        if "has_exam" in data:
            course.has_exam = bool(data["has_exam"])
        if "exam_duration" in data:
            course.exam_duration = int(data["exam_duration"])
        if "exam_type" in data:
            course.exam_type = data["exam_type"]
        if "special_room" in data:
            course.special_room = data["special_room"]
        if "notes" in data:
            course.notes = data["notes"]

        # Scope alanları: admin dışında değiştirme kapalı (yetki kaçırma)
        if "department_id" in data or "program_id" in data:
            if request.user_role != "admin":
                return jsonify(
                    {"status": "error", "message": "Bölüm/program değişikliği sadece admin tarafından yapılabilir."}
                ), 403
            if "department_id" in data:
                course.department_id = data["department_id"]
            if "program_id" in data:
                course.program_id = data["program_id"]

        db.session.commit()
        return jsonify({"status": "success", "message": "Ders güncellendi"})

    # DELETE
    enrollments = Enrollment.query.filter_by(course_id=course_id).count()
    if enrollments > 0:
        return jsonify({"status": "error", "message": f"Bu derse {enrollments} öğrenci kayıtlı."}), 400

    exams = Exam.query.filter_by(course_id=course_id).count()
    if exams > 0:
        return jsonify({"status": "error", "message": "Bu dersin sınavı planlanmış."}), 400

    db.session.delete(course)
    db.session.commit()
    return jsonify({"status": "success", "message": "Ders silindi"})


# ==================== DERSLİK ENDPOINTS ====================


@app.route("/api/classrooms", methods=["GET", "POST"])
@require_auth()
def manage_classrooms():
    """Derslik yönetimi"""
    if request.method == "GET":
        classrooms = Classroom.query.all()
        return jsonify(
            {
                "status": "success",
                "data": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "capacity": c.capacity,
                        "is_available": c.is_available,
                        "is_special": c.is_special,
                        "special_type": c.special_type,
                    }
                    for c in classrooms
                ],
            }
        )

    if request.user_role != "admin":
        return jsonify({"status": "error", "message": "Yetersiz izin"}), 403

    data = request.get_json() or {}
    classroom = Classroom(
        name=(data.get("name") or "").strip(),
        capacity=int(data.get("capacity", 30)),
        is_available=bool(data.get("is_available", True)),
        is_special=bool(data.get("is_special", False)),
        special_type=data.get("special_type"),
    )
    db.session.add(classroom)
    db.session.commit()
    return jsonify({"status": "success", "id": classroom.id, "message": "Derslik eklendi"}), 201


# ==================== SINAV ENDPOINTS (Kısaltılmış) ====================


@app.route("/api/exams", methods=["GET"])
@require_auth()
def list_exams():
    query = Exam.query

    if request.user_role == "hoca":
        user = _get_current_user()
        courses = Course.query.filter_by(teacher_id=user.teacher_id).all()
        query = query.filter(Exam.course_id.in_([c.id for c in courses]))

    elif request.user_role == "ogrenci":
        user = _get_current_user()
        enrollments = Enrollment.query.filter_by(student_id=user.student_id).all()
        query = query.filter(Exam.course_id.in_([e.course_id for e in enrollments]))

    elif request.user_role in ["bolum_yetkilisi", "program_yetkilisi"]:
        scope_dept_id, scope_prog_id = _get_scope()
        courses_q = Course.query.filter_by(department_id=scope_dept_id)
        if request.user_role == "program_yetkilisi":
            courses_q = courses_q.filter_by(program_id=scope_prog_id)
        course_ids = [c.id for c in courses_q.all()]
        query = query.filter(Exam.course_id.in_(course_ids))

    exams = query.all()
    return jsonify({"status": "success", "data": [e.to_dict() for e in exams]})


@app.route("/api/exams", methods=["DELETE"])
@require_auth()
def delete_exams():
    """Tüm sınavları sil (admin / bölüm yetkilisi / program yetkilisi scoped)."""
    if request.user_role not in ["admin", "bolum_yetkilisi", "program_yetkilisi"]:
        return jsonify({"status": "error", "message": "Yetersiz izin"}), 403

    confirm = request.args.get("confirm", "false").lower() == "true"
    if not confirm:
        return jsonify({"status": "error", "message": "confirm=true parametresi gerekli"}), 400

    # Admin: hepsi
    if request.user_role == "admin":
        count = Exam.query.count()
        Exam.query.delete()
        db.session.commit()
        return jsonify({"status": "success", "deleted": count, "message": f"{count} sınav silindi"})

    # Scoped silme: bölüm/program kapsamındaki derslerin sınavları
    scope_dept_id, scope_prog_id = _get_scope()
    courses_q = Course.query.filter_by(department_id=scope_dept_id)
    if request.user_role == "program_yetkilisi":
        courses_q = courses_q.filter_by(program_id=scope_prog_id)
    course_ids = [c.id for c in courses_q.all()]
    if not course_ids:
        return jsonify({"status": "success", "deleted": 0, "message": "Silinecek sınav yok"})

    count = Exam.query.filter(Exam.course_id.in_(course_ids)).count()
    Exam.query.filter(Exam.course_id.in_(course_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"status": "success", "deleted": count, "message": f"{count} sınav silindi"})


@app.route("/api/schedule", methods=["POST"])
@require_auth(roles=["admin", "bolum_yetkilisi", "program_yetkilisi"])
def run_scheduler():
    """Otomatik sınav planlama (scope destekli)."""
    data = request.get_json() or {}
    days = int(data.get("days", 5))
    force = bool(data.get("force", False))

    dept_id = data.get("department_id")
    program_id = data.get("program_id")

    if request.user_role in ["bolum_yetkilisi", "program_yetkilisi"]:
        scope_dept_id, scope_prog_id = _get_scope()
        dept_id = scope_dept_id
        if request.user_role == "program_yetkilisi":
            program_id = scope_prog_id

    if force:
        # kapsam dahilinde sınavları sil
        if request.user_role == "admin":
            Exam.query.delete()
        else:
            courses_q = Course.query.filter_by(department_id=dept_id)
            if request.user_role == "program_yetkilisi":
                courses_q = courses_q.filter_by(program_id=program_id)
            course_ids = [c.id for c in courses_q.all()]
            if course_ids:
                Exam.query.filter(Exam.course_id.in_(course_ids)).delete(synchronize_session=False)
        db.session.commit()

    try:
        courses_q = Course.query.filter_by(has_exam=True)
        if dept_id:
            courses_q = courses_q.filter_by(department_id=int(dept_id))
        if program_id:
            courses_q = courses_q.filter_by(program_id=int(program_id))
        courses = courses_q.all()

        if not courses:
            return jsonify({"status": "warning", "message": "Planlanacak ders bulunamadı", "created": 0, "exams": []}), 200

        base_date = datetime.date.today()
        time_windows = [datetime.time(9, 0), datetime.time(11, 30), datetime.time(14, 0), datetime.time(16, 30)]
        slots = []
        for d in range(days):
            current = base_date + datetime.timedelta(days=d)
            weekday = current.strftime("%a")
            for tw in time_windows:
                start_dt = datetime.datetime.combine(current, tw)
                slots.append({"start": start_dt, "weekday": weekday})

        classrooms = Classroom.query.filter_by(is_available=True).order_by(Classroom.capacity.desc()).all()
        if not classrooms:
            return jsonify({"status": "error", "message": "Uygun derslik yok"}), 400
        room_by_id = {c.id: c for c in classrooms}

        proximity_map = {}
        proximities = ClassroomProximity.query.all()
        for rel in proximities:
            proximity_map.setdefault(rel.primary_classroom_id, []).append(
                (rel.nearby_classroom_id, rel.distance or 0.0, rel.is_adjacent)
            )
            proximity_map.setdefault(rel.nearby_classroom_id, []).append(
                (rel.primary_classroom_id, rel.distance or 0.0, rel.is_adjacent)
            )
        for rid in proximity_map:
            proximity_map[rid].sort(key=lambda x: (0 if x[2] else 1, x[1]))

        existing_exams = Exam.query.all()
        teacher_busy = {}
        room_busy = {}
        student_busy = {}

        def add_busy(map_obj, key, start, end):
            map_obj.setdefault(key, []).append((start, end))

        def overlaps(a_start, a_end, b_start, b_end):
            return not (a_end <= b_start or a_start >= b_end)

        for ex in existing_exams:
            end = ex.slot_start + datetime.timedelta(minutes=ex.duration)
            add_busy(room_busy, ex.room_id, ex.slot_start, end)
            course = Course.query.get(ex.course_id)
            if course and course.teacher_id:
                add_busy(teacher_busy, course.teacher_id, ex.slot_start, end)
            enrolls = Enrollment.query.filter_by(course_id=ex.course_id).all()
            for en in enrolls:
                add_busy(student_busy, en.student_id, ex.slot_start, end)

        enrollments_map = {}
        for en in Enrollment.query.filter(Enrollment.course_id.in_([c.id for c in courses])).all():
            enrollments_map.setdefault(en.course_id, []).append(en.student_id)

        # mevcut sınavı olanları atla (force değilse)
        target_courses = []
        for c in courses:
            if not force and Exam.query.filter_by(course_id=c.id).first():
                continue
            target_courses.append(c)

        target_courses.sort(key=lambda c: c.student_count or 0, reverse=True)

        best_plan = []
        plan = []

        def teacher_ok(course, slot_start, slot_end, weekday):
            if not course.teacher_id:
                return True
            teacher = Teacher.query.get(course.teacher_id)
            if teacher and teacher.available_days:
                allowed = [d.strip() for d in teacher.available_days.split(",") if d.strip()]
                if allowed and weekday not in allowed:
                    return False
            for b_start, b_end in teacher_busy.get(course.teacher_id, []):
                if overlaps(slot_start, slot_end, b_start, b_end):
                    return False
            return True

        def students_ok(course_id, slot_start, slot_end):
            for sid in enrollments_map.get(course_id, []):
                for b_start, b_end in student_busy.get(sid, []):
                    if overlaps(slot_start, slot_end, b_start, b_end):
                        return False
            return True

        def rooms_cluster_candidates(needed, course_special):
            base_rooms = []
            for r in classrooms:
                if course_special:
                    if r.name != course_special and r.special_type != course_special:
                        continue
                base_rooms.append(r)

            for r in base_rooms:
                if r.capacity >= needed:
                    yield [r]

            for r in base_rooms:
                cluster = [r]
                cap = r.capacity
                for near_id, dist, is_adj in proximity_map.get(r.id, []):
                    near_room = room_by_id.get(near_id)
                    if not near_room:
                        continue
                    if course_special and near_room.name != course_special and near_room.special_type != course_special:
                        continue
                    cluster.append(near_room)
                    cap += near_room.capacity
                    if cap >= needed:
                        break
                if cap >= needed and len(cluster) > 1:
                    yield cluster

            cluster = []
            cap = 0
            for r in base_rooms:
                cluster.append(r)
                cap += r.capacity
                if cap >= needed:
                    yield cluster
                    break

        def rooms_available(cluster, slot_start, slot_end):
            for r in cluster:
                for b_start, b_end in room_busy.get(r.id, []):
                    if overlaps(slot_start, slot_end, b_start, b_end):
                        return False
            return True

        def apply_busy(cluster, course, slot_start, slot_end):
            for r in cluster:
                add_busy(room_busy, r.id, slot_start, slot_end)
            if course.teacher_id:
                add_busy(teacher_busy, course.teacher_id, slot_start, slot_end)
            for sid in enrollments_map.get(course.id, []):
                add_busy(student_busy, sid, slot_start, slot_end)

        def remove_busy(cluster, course, slot_start, slot_end):
            for r in cluster:
                room_busy[r.id] = [(s, e) for (s, e) in room_busy.get(r.id, []) if not (s == slot_start and e == slot_end)]
            if course.teacher_id:
                teacher_busy[course.teacher_id] = [
                    (s, e) for (s, e) in teacher_busy.get(course.teacher_id, []) if not (s == slot_start and e == slot_end)
                ]
            for sid in enrollments_map.get(course.id, []):
                student_busy[sid] = [
                    (s, e) for (s, e) in student_busy.get(sid, []) if not (s == slot_start and e == slot_end)
                ]

        def dfs(idx):
            nonlocal best_plan
            if idx == len(target_courses):
                best_plan = plan.copy()
                return True

            course = target_courses[idx]
            duration = course.exam_duration or 60
            for slot in slots:
                slot_start = slot["start"]
                slot_end = slot_start + datetime.timedelta(minutes=duration)
                weekday = slot["weekday"]

                if not teacher_ok(course, slot_start, slot_end, weekday):
                    continue
                if not students_ok(course.id, slot_start, slot_end):
                    continue

                for cluster in rooms_cluster_candidates(course.student_count or 0, course.special_room):
                    if not rooms_available(cluster, slot_start, slot_end):
                        continue
                    plan.append((course, cluster, slot_start, duration))
                    apply_busy(cluster, course, slot_start, slot_end)
                    if dfs(idx + 1):
                        return True
                    remove_busy(cluster, course, slot_start, slot_end)
                    plan.pop()

            if len(plan) > len(best_plan):
                best_plan = plan.copy()
            return False

        dfs(0)

        if not best_plan:
            return jsonify({"status": "error", "message": "Hiçbir ders planlanamadı"}), 400

        created = []
        for course, cluster, slot_start, duration in best_plan:
            for room in cluster:
                exam = Exam(
                    course_id=course.id,
                    room_id=room.id,
                    slot_start=slot_start,
                    duration=duration,
                    slot=slot_start.isoformat(),
                )
                db.session.add(exam)
            created.append(
                {"course": course.name, "slot": slot_start.isoformat(), "duration": duration, "rooms": [r.name for r in cluster]}
            )

        db.session.commit()
        status = "success" if len(best_plan) == len(target_courses) else "warning"
        message = f"{len(best_plan)}/{len(target_courses)} ders planlandı"
        if status == "warning":
            message += " (bazı dersler için uygun slot bulunamadı)"
        return jsonify({"status": status, "created": len(best_plan), "exams": created, "message": message})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Planlama hatası: {str(e)}"}), 500


# ==================== EXCEL ENDPOINTS (Kısaltılmış) ====================


@app.route("/api/excel/import-proximity", methods=["POST"])
@require_auth(roles=["admin", "bolum_yetkilisi", "program_yetkilisi"])
def import_proximity():
    """Kullanıcıdan yüklenen derslik yakınlık Excel dosyasını içe aktar"""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "Dosya yüklenmedi"}), 400
    file = request.files["file"]
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        return jsonify({"status": "error", "message": "Geçerli bir Excel dosyası seçin"}), 400

    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name
    try:
        result = import_proximity_to_db(temp_path, db, Classroom, ClassroomProximity)
        status_code = 200 if result.get("status") == "success" else 400
        return jsonify(result), status_code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/api/excel/import-capacity", methods=["POST"])
@require_auth(roles=["admin", "bolum_yetkilisi", "program_yetkilisi"])
def import_capacity():
    """Kullanıcıdan yüklenen kapasite Excel dosyasını içe aktar"""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "Dosya yüklenmedi"}), 400
    file = request.files["file"]
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        return jsonify({"status": "error", "message": "Geçerli bir Excel dosyası seçin"}), 400

    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name
    try:
        result = import_capacity_to_db(temp_path, db, Classroom, Course)
        status_code = 200 if result.get("status") in ["success", "partial"] else 400
        return jsonify(result), status_code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/api/excel/import-teachers", methods=["POST"])
@require_auth(roles=["admin", "bolum_yetkilisi", "program_yetkilisi"])
def import_teachers():
    """Excel'den öğretim üyelerini içe aktar"""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "Dosya yüklenmedi"}), 400
    file = request.files["file"]
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        return jsonify({"status": "error", "message": "Geçerli bir Excel dosyası seçin"}), 400

    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name
    try:
        result = import_teachers_from_excel(temp_path, db)
        status_code = 200 if result.get("status") == "success" else 400
        return jsonify(result), status_code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/api/exams/export", methods=["GET"])
@require_auth()
def export_schedule():
    """Sınav programını Excel olarak dışa aktar"""
    try:
        exams = Exam.query.all()
        rows = []
        for exam in exams:
            course = Course.query.get(exam.course_id)
            room = Classroom.query.get(exam.room_id)
            teacher = course.teacher if course else None
            rows.append(
                {
                    "Ders": course.name if course else "N/A",
                    "Ders Kodu": course.code if course else "N/A",
                    "Öğretim Üyesi": teacher.name if teacher else "N/A",
                    "Derslik": room.name if room else "N/A",
                    "Kapasite": room.capacity if room else 0,
                    "Başlama Saati": exam.slot_start.strftime("%Y-%m-%d %H:%M") if exam.slot_start else "",
                    "Süre (dk)": exam.duration,
                    "Sınav Türü": course.exam_type if course else "N/A",
                    "Öğrenci Sayısı": course.student_count if course else 0,
                }
            )

        df = pd.DataFrame(rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Sınav Programı", index=False)
        output.seek(0)
        return send_file(
            output,
            download_name="sinav_programi.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Export hatası: {str(e)}"}), 500


@app.route("/api/seed", methods=["POST"])
@require_auth(roles=["admin"])
def seed_data():
    """Örnek veri yükle (admin)."""
    data = request.get_json() or {}
    force = bool(data.get("force", False))

    if force:
        Exam.query.delete()
        Enrollment.query.delete()
        Course.query.delete()
        Student.query.delete()
        Teacher.query.delete()
        Program.query.delete()
        Department.query.delete()
        Faculty.query.delete()
        ClassroomProximity.query.delete()
        Classroom.query.delete()
        db.session.commit()

    # Fakülte/Bölüm/Program
    fak = Faculty(name="Mühendislik Fakültesi")
    db.session.add(fak)
    db.session.flush()

    dept = Department(name="Bilgisayar Mühendisliği", faculty_id=fak.id)
    db.session.add(dept)
    db.session.flush()

    prog = Program(name="Lisans", department_id=dept.id)
    db.session.add(prog)
    db.session.flush()

    # Öğretim üyeleri
    teachers = [
        Teacher(name="Dr. Ahmet Yılmaz", department_id=dept.id),
        Teacher(name="Prof. Ayşe Demir", department_id=dept.id),
    ]
    for t in teachers:
        db.session.add(t)
    db.session.flush()

    # Derslikler
    classrooms = [
        Classroom(name="A101", capacity=120),
        Classroom(name="A102", capacity=120),
        Classroom(name="B201", capacity=80),
        Classroom(name="B202", capacity=80),
    ]
    for c in classrooms:
        db.session.add(c)
    db.session.flush()

    # Dersler
    courses = [
        Course(
            name="Algoritma ve Programlama",
            code="YZM332",
            teacher_id=teachers[0].id,
            department_id=dept.id,
            program_id=prog.id,
            student_count=110,
            exam_duration=60,
            exam_type="written",
        ),
        Course(
            name="Veri Tabanı Sistemleri",
            code="BLM111",
            teacher_id=teachers[1].id,
            department_id=dept.id,
            program_id=prog.id,
            student_count=75,
            exam_duration=60,
            exam_type="written",
        ),
    ]
    for c in courses:
        db.session.add(c)
    db.session.flush()

    # Admin demo kullanıcı (varsa dokunma)
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

    db.session.commit()
    return jsonify(
        {
            "status": "success",
            "message": "Örnek veriler yüklendi",
            "created": {
                "faculties": 1,
                "departments": 1,
                "programs": 1,
                "teachers": len(teachers),
                "classrooms": len(classrooms),
                "courses": len(courses),
            },
        }
    )


if __name__ == "__main__":
    print("🚀 KOSTÜ Sınav Programı Yönetim Sistemi başlatılıyor...")
    init_db()
    port = int(os.getenv("API_PORT", 5000))
    host = os.getenv("API_HOST", "0.0.0.0")
    print(f"✅ Sunucu çalışıyor: {host}:{port}")
    app.run(host=host, port=port, debug=True)

