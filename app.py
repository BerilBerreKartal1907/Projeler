"""
KOSTÜ Sınav Programı Yönetim Sistemi
Backend API - Flask + SQLAlchemy + MySQL
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

# excel_processor modülünü try-except bloğu içine alarak, dosya yoksa hata vermesini önleyelim
try:
    from excel_processor import (
        ExcelProcessor,
        batch_process_folder,
        import_classlists_to_db,
        import_proximity_to_db,
        import_capacity_to_db,
        import_teachers_from_excel,
    )
except ImportError:
    # Dummy classes/functions to prevent startup error if file is missing
    class ExcelProcessor: pass
    def batch_process_folder(*args, **kwargs): pass
    def import_classlists_to_db(*args, **kwargs): return {}
    def import_proximity_to_db(*args, **kwargs): return {}
    def import_capacity_to_db(*args, **kwargs): return {}
    def import_teachers_from_excel(*args, **kwargs): return {}

# .env dosyasını yükle
load_dotenv()

app = Flask(__name__)
CORS(app)

# ==================== KONFİGÜRASYON ====================

# DATABASE_URL ZORUNLU - MySQL olmalı
db_url = os.getenv('DATABASE_URL')
if not db_url:
    # Varsayılan olarak sqlite kullanalım (test için) eğer env yoksa
    db_url = 'sqlite:///test.db' 
    # raise RuntimeError(
    #     "❌ DATABASE_URL çevre değişkeni ayarlanmamış!\n"
    #     "Lütfen .env dosyasında şu format ile tanımlayın:\n"
    #     "DATABASE_URL=mysql+pymysql://username:password@host:port/database\n"
    #     "\nÖrnek:\n"
    #     "DATABASE_URL=mysql+pymysql://root:password@localhost:3306/kostu_exam_db"
    # )

# MySQL formatını kontrol et
if db_url.startswith('mysql://'):
    db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

# JWT ve Güvenlik
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['JWT_EXPIRATION_HOURS'] = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
app.config['JWT_ALGORITHM'] = os.getenv('JWT_ALGORITHM', 'HS256')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ==================== MODELLERİ ====================

class User(db.Model):
    """Kullanıcı Modeli"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # admin, bolum_yetkilisi, hoca, ogrenci
    
    # İlişkiler
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def set_password(self, password):
        """Şifreyi hash'le ve kaydet"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Şifreyi doğrula"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'teacher_id': self.teacher_id,
            'student_id': self.student_id,
            'department_id': self.department_id
        }


class Faculty(db.Model):
    """Fakülte Modeli"""
    __tablename__ = 'faculty'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    departments = db.relationship('Department', backref='faculty', lazy=True)


class Department(db.Model):
    """Bölüm Modeli"""
    __tablename__ = 'department'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)


class Program(db.Model):
    """Program Modeli (Bölüm içindeki Lisans/Yüksek Lisans vb.)"""
    __tablename__ = 'program'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    
    __table_args__ = (db.UniqueConstraint('name', 'department_id', name='unique_program_per_dept'),)


class Teacher(db.Model):
    """Öğretim Üyesi Modeli"""
    __tablename__ = 'teacher'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    
    # Unvan (Prof. Dr., Doç. Dr., Dr. Öğr. Üyesi, vb.)
    title = db.Column(db.String(100), nullable=True)
    
    # Fakülte/Bölüm (KOSTÜ scraper'ından)
    faculty = db.Column(db.String(200), nullable=True)
    
    # Müsaitlik (virgülle ayrılmış gün listesi: Mon,Tue,Wed,Thu,Fri)
    available_days = db.Column(db.String(100), default='Mon,Tue,Wed,Thu,Fri')
    
    # Ek müsaitlik bilgisi (JSON formatında: {"Mon": "09:00-17:00", ...})
    availability_details = db.Column(db.Text, nullable=True)
    
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    user = db.relationship('User', backref='teacher_user', lazy=True, uselist=False)
    courses = db.relationship('Course', backref='teacher', lazy=True)


class Student(db.Model):
    """Öğrenci Modeli"""
    __tablename__ = 'student'
    
    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True)
    
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    user = db.relationship('User', backref='student_user', lazy=True, uselist=False)
    enrollments = db.relationship('Enrollment', backref='student', lazy=True)


class Course(db.Model):
    """Ders Modeli"""
    __tablename__ = 'course'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    code = db.Column(db.String(50), nullable=True, unique=True)  # YZM332, BLM111 vb.
    
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True)
    
    student_count = db.Column(db.Integer, default=0)
    
    # Sınav Özellikleri
    has_exam = db.Column(db.Boolean, default=True)  # Dersin sınavı var mı?
    exam_duration = db.Column(db.Integer, default=60)  # Dakika (30, 60, 90, 120)
    exam_type = db.Column(db.String(100), default='written')  # yazılı, uygulama, proje vb.
    exam_date = db.Column(db.DateTime, nullable=True)  # Sınavın tarihi (planlama sonrası)
    
    special_room = db.Column(db.String(500), nullable=True)  # Özel sınıf (lab, dekanlık vb.)
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    enrollments = db.relationship('Enrollment', backref='course', lazy=True)
    exams = db.relationship('Exam', backref='course', lazy=True)


class Enrollment(db.Model):
    """Ders Kayıtı Modeli"""
    __tablename__ = 'enrollment'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    
    enrolled_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', name='unique_enrollment'),)


class Classroom(db.Model):
    """Derslik Modeli"""
    __tablename__ = 'classroom'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)  # D101, A205 vb.
    capacity = db.Column(db.Integer, nullable=False)
    
    is_available = db.Column(db.Boolean, default=True)
    is_special = db.Column(db.Boolean, default=False)  # Lab, dekanlık vb.?
    special_type = db.Column(db.String(100), nullable=True)  # lab, computer_lab, auditorium vb.
    
    exams = db.relationship('Exam', backref='room', lazy=True)


class ClassroomProximity(db.Model):
    """Derslik Yakınlık Modeli"""
    __tablename__ = 'classroom_proximity'
    
    id = db.Column(db.Integer, primary_key=True)
    primary_classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False, index=True)
    nearby_classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False, index=True)
    
    is_adjacent = db.Column(db.Boolean, default=False)
    distance = db.Column(db.Float, nullable=True)  # Metre cinsinden
    notes = db.Column(db.String(500), nullable=True)
    
    primary_classroom = db.relationship('Classroom', foreign_keys=[primary_classroom_id])
    nearby_classroom = db.relationship('Classroom', foreign_keys=[nearby_classroom_id])


class Exam(db.Model):
    """Sınav Modeli"""
    __tablename__ = 'exam'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False, index=True)
    
    slot_start = db.Column(db.DateTime, nullable=False, index=True)
    duration = db.Column(db.Integer, nullable=False)  # Dakika
    
    # Eski format (legacy)
    slot = db.Column(db.String(200), nullable=True)
    
    status = db.Column(db.String(50), default='scheduled')  # scheduled, ongoing, completed, cancelled
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def to_dict(self):
        course = Course.query.get(self.course_id)
        room = Classroom.query.get(self.room_id)
        teacher = course.teacher if course else None
        
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_name': course.name if course else None,
            'course_code': course.code if course else None,
            'department_id': course.department_id if course else None,
            'room_id': self.room_id,
            'room_name': room.name if room else None,
            'teacher_id': teacher.id if teacher else None,
            'teacher_name': teacher.name if teacher else None,
            'slot_start': self.slot_start.isoformat(),
            'slot_end': (self.slot_start + datetime.timedelta(minutes=self.duration)).isoformat(),
            'duration': self.duration,
            'status': self.status
        }


class ExcelImportLog(db.Model):
    """Excel İthal Günlüğü"""
    __tablename__ = 'excel_import_log'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    import_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(50), default='success')  # success, failed, warning
    records_imported = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)


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
            wait_time = 2 ** retry_count
            logger.warning(f"⚠️ Veritabanı bağlantısı başarısız (Deneme {retry_count}/{max_retries}): {str(e)}")
            logger.warning(f"⏳ {wait_time} saniye sonra tekrar denenecek...")
            time.sleep(wait_time)
    
    logger.error(f"❌ Veritabanı {max_retries} denemeden sonra başlatılamadı")
    raise Exception("Database initialization failed after retries")


def seed_default_users():
    """Demo kullanıcıları ekle (sadece tablo boşsa)"""
    if User.query.first():
        return
    
    # Demo Fakülte ve Bölüm
    fak = Faculty(name='Mühendislik Fakültesi')
    db.session.add(fak)
    db.session.flush()
    
    dept = Department(name='Bilgisayar Mühendisliği', faculty_id=fak.id)
    db.session.add(dept)
    db.session.flush()
    
    # Demo Öğretim Üyesi
    teacher = Teacher(name='Dr. Ahmet Yılmaz', department_id=dept.id)
    db.session.add(teacher)
    db.session.flush()
    
    # Demo Öğrenci
    student = Student(student_number='2020001', name='Mehmet Şahin')
    db.session.add(student)
    db.session.flush()
    
    # Demo Kullanıcılar
    demo_users = [
        {'username': 'admin', 'password': 'admin123', 'role': 'admin', 'teacher_id': None, 'student_id': None, 'dept_id': dept.id},
        {'username': 'bolum', 'password': 'bolum123', 'role': 'bolum_yetkilisi', 'teacher_id': None, 'student_id': None, 'dept_id': dept.id},
        {'username': 'hoca', 'password': 'hoca123', 'role': 'hoca', 'teacher_id': teacher.id, 'student_id': None, 'dept_id': dept.id},
        {'username': 'ogrenci', 'password': 'ogrenci123', 'role': 'ogrenci', 'teacher_id': None, 'student_id': student.id, 'dept_id': dept.id},
    ]
    
    for user_data in demo_users:
        user = User(
            username=user_data['username'],
            role=user_data['role'],
            teacher_id=user_data['teacher_id'],
            student_id=user_data['student_id'],
            department_id=user_data['dept_id']
        )
        user.set_password(user_data['password'])
        db.session.add(user)
    
    db.session.commit()


def generate_token(user_id, role, username):
    """JWT token oluştur"""
    payload = {
        'user_id': user_id,
        'role': role,
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm=app.config['JWT_ALGORITHM'])
    return token


def verify_token(token):
    """JWT token'ı doğrula"""
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=[app.config['JWT_ALGORITHM']])
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
            token = request.headers.get('Authorization', '').replace('Bearer ', '')

            if not token:
                return jsonify({'status': 'error', 'message': 'Token eksik'}), 401

            payload = verify_token(token)
            if not payload:
                return jsonify({'status': 'error', 'message': 'Geçersiz token'}), 401

            if roles and payload['role'] not in roles:
                return jsonify({'status': 'error', 'message': 'Yetersiz izin'}), 403

            # 👇 KULLANICI BİLGİLERİNİ REQUEST'E EKLE
            request.user_id = payload['user_id']
            request.user_role = payload['role']
            request.username = payload['username']

            # 👇 BÖLÜM YETKİLİSİ AMA BÖLÜMÜ YOKSA HER ŞEYİ ENGELLE
            if payload['role'] == 'bolum_yetkilisi':
                user = User.query.get(payload['user_id'])
                if not user or not user.department_id:
                    return jsonify({
                        'status': 'error',
                        'message': 'Bölüm yetkilisi için bölüm ataması yapılmamış.'
                    }), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator



# ==================== LOGIN VE AUTH ENDPOINTS ====================

@app.route('/api/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Kullanıcı adı ve şifre gerekli'}), 400
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'status': 'error', 'message': 'Hatalı kullanıcı adı veya şifre'}), 401
    
    token = generate_token(user.id, user.role, user.username)
    
    return jsonify({
        'status': 'success',
        'token': token,
        'user': user.to_dict(),
        'message': f'{user.username} başarıyla giriş yaptı'
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout endpoint (frontend'de token silinir)"""
    return jsonify({'status': 'success', 'message': 'Başarıyla çıkış yapıldı'})


@app.route('/api/me', methods=['GET'])
@require_auth()
def get_me():
    """Giriş yapan kullanıcının bilgilerini getir"""
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'Kullanıcı bulunamadı'}), 404
    
    return jsonify({
        'status': 'success',
        'user': user.to_dict()
    })


@app.route('/api/register', methods=['POST'])
@require_auth(roles=['admin'])
def register_user():
    """Yeni kullanıcı oluştur (admin only)"""
    data = request.get_json() or {}
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'ogrenci')  # admin, bolum_yetkilisi, hoca, ogrenci
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Kullanıcı adı ve şifre gerekli'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'message': 'Bu kullanıcı adı zaten kullanılıyor'}), 409
    
    user = User(username=username, role=role)
    user.set_password(password)
    
    # Opsiyonel ilişkiler
    if role == 'hoca' and data.get('teacher_id'):
        user.teacher_id = data.get('teacher_id')
    elif role == 'ogrenci' and data.get('student_id'):
        user.student_id = data.get('student_id')
    
    if data.get('department_id'):
        user.department_id = data.get('department_id')
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'user': user.to_dict(),
        'message': 'Kullanıcı başarıyla oluşturuldu'
    })


# ==================== TEMEL ENDPOINTS ====================

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "KOSTÜ Sınav Programı Yönetim Sistemi",
        "version": "2.0.0",
        "api_docs": "/api/docs"
    })


@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "database": "mysql"
    })


# ==================== ÖĞRETIM ÜYESİ ENDPOINTS ====================

# ==================== BÖLÜM ENDPOINTS ====================

@app.route('/api/departments', methods=['GET'])
@require_auth()
def get_departments():
    """Tüm bölümleri getir"""
    departments = Department.query.all()
    return jsonify({
        'status': 'success',
        'data': [
            {
                'id': d.id,
                'name': d.name,
                'faculty_id': d.faculty_id
            } for d in departments
        ]
    })


@app.route('/api/facilities', methods=['GET'])
@require_auth()
def get_facilities():
    """Tüm fakülteleri getir"""
    facilities = Faculty.query.all()
    return jsonify({
        'status': 'success',
        'data': [
            {
                'id': f.id,
                'name': f.name
            } for f in facilities
        ]
    })


# ==================== PROGRAM ENDPOINTS ====================

@app.route('/api/programs', methods=['GET', 'POST'])
@require_auth()
def manage_programs():
    """Program yönetimi"""
    if request.method == 'GET':
        dept_id = request.args.get('department_id', type=int)
        
        query = Program.query
        
        # Bölüm yetkilisi sadece kendi bölümünün programlarını görsün (opsiyonel, hepsi de görülebilir)
        # Ancak genellikle filtreleme UI tarafında yapılır.
        
        if dept_id:
            query = query.filter_by(department_id=dept_id)
        
        programs = query.all()
        return jsonify({
            'status': 'success',
            'data': [
                {
                    'id': p.id,
                    'name': p.name,
                    'department_id': p.department_id
                } for p in programs
            ]
        })
    
    # POST - Admin ve Bölüm Yetkilisi
    if request.user_role not in ['admin', 'bolum_yetkilisi']:
        return jsonify({'status': 'error', 'message': 'Yetersiz izin'}), 403
    
    data = request.get_json() or {}
    
    dept_id = data.get('department_id')
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        dept_id = user.department_id
    
    if not dept_id:
        return jsonify({'status': 'error', 'message': 'Bölüm ID gerekli'}), 400

    program = Program(
        name=data.get('name', ''),
        department_id=dept_id
    )
    
    try:
        db.session.add(program)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Program oluşturulurken hata: ' + str(e)}), 400
    
    return jsonify({
        'status': 'success',
        'id': program.id,
        'message': 'Program eklendi'
    }), 201


@app.route('/api/programs/<int:program_id>', methods=['PUT', 'DELETE'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def update_delete_program(program_id):
    """Program güncelleme veya silme"""
    program = Program.query.get(program_id)
    if not program:
        return jsonify({'status': 'error', 'message': 'Program bulunamadı'}), 404
    
    # Bölüm yetkilisi kontrolü
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        if program.department_id != user.department_id:
            return jsonify({'status': 'error', 'message': 'Kendi bölümünüz dışındaki programı düzenleyemezsiniz'}), 403

    if request.method == 'PUT':
        data = request.get_json() or {}
        if 'name' in data:
            program.name = data['name']
        
        # Dept ID admin değiştirebilir
        if 'department_id' in data and request.user_role == 'admin':
            program.department_id = data['department_id']
            
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 400
        
        return jsonify({'status': 'success', 'message': 'Program güncellendi'})
    
    elif request.method == 'DELETE':
        # Bağlı öğrenci/ders var mı?
        # Basit kontrol
        students = Student.query.filter_by(program_id=program_id).count()
        courses = Course.query.filter_by(program_id=program_id).count()
        
        if students > 0 or courses > 0:
            return jsonify({'status': 'error', 'message': f'Bu programa bağlı {students} öğrenci ve {courses} ders var. Silinemez.'}), 400
            
        db.session.delete(program)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Program silindi'})


# ==================== ÖĞRETIM ÜYESİ ENDPOINTS ====================
@require_auth()
def manage_teachers():
    """Öğretim üyeleri yönetimi"""
    if request.method == 'GET':
        # Filtreleme
        dept_id = request.args.get('department_id', type=int)
        query = Teacher.query
        
        if request.user_role == 'bolum_yetkilisi':
            # Bölüm yetkilisi sadece kendi bölümünü görsün
            user = User.query.get(request.user_id)
            query = query.filter_by(department_id=user.department_id)
        
        if dept_id:
            query = query.filter_by(department_id=dept_id)
        
        teachers = query.all()
        return jsonify({
            'status': 'success',
            'data': [
                {
                    'id': t.id,
                    'name': t.name,
                    'department_id': t.department_id,
                    'title': t.title or '',
                    'faculty': t.faculty or '',
                    'available_days': t.available_days,
                    'email': t.email,
                    'phone': t.phone
                } for t in teachers
            ]
        })
    
    # POST - Admin ve bölüm yetkilisi ekleyebilir
    if request.user_role not in ['admin', 'bolum_yetkilisi']:
        return jsonify({'status': 'error', 'message': 'Yetersiz izin'}), 403
    
    data = request.get_json() or {}
    
    # Bölüm yetkilisi kontrolü
    department_id = data.get('department_id')
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        department_id = user.department_id # Zorunlu olarak kendi bölümü
    
    teacher = Teacher(
        name=data.get('name', ''),
        department_id=department_id,
        title=data.get('title'),
        faculty=data.get('faculty'),
        available_days=data.get('available_days', 'Mon,Tue,Wed,Thu,Fri'),
        email=data.get('email'),
        phone=data.get('phone')
    )
    
    db.session.add(teacher)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'id': teacher.id,
        'message': 'Öğretim üyesi eklendi'
    }), 201


@app.route('/api/teachers/<int:teacher_id>', methods=['PUT', 'DELETE'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def update_delete_teacher(teacher_id):
    """Öğretim üyesi güncelleme veya silme"""
    teacher = Teacher.query.get(teacher_id)
    if not teacher:
        return jsonify({'status': 'error', 'message': 'Öğretim üyesi bulunamadı'}), 404
    
    # Bölüm yetkilisi sadece kendi bölümündeki hocayı düzenleyebilir
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        if teacher.department_id != user.department_id:
            return jsonify({'status': 'error', 'message': 'Kendi bölümünüz dışındaki öğretim üyesini düzenleyemezsiniz'}), 403
    
    if request.method == 'PUT':
        data = request.get_json() or {}
        
        if 'name' in data:
            teacher.name = data['name']
        if 'available_days' in data:
            teacher.available_days = data['available_days']
        
        # Bölüm yetkilisi departman değiştiremez, admin değiştirebilir
        if 'department_id' in data:
            if request.user_role == 'admin':
                teacher.department_id = data['department_id']
        
        if 'email' in data:
            teacher.email = data['email']
        if 'phone' in data:
            teacher.phone = data['phone']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Öğretim üyesi güncellendi'
        })
    
    elif request.method == 'DELETE':
        # Derslere atanmış mı kontrol et
        courses = Course.query.filter_by(teacher_id=teacher_id).count()
        if courses > 0:
            return jsonify({'status': 'error', 'message': f'Bu öğretim üyesine {courses} ders atanmış. Önce dersleri kaldırın.'}), 400
        
        db.session.delete(teacher)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Öğretim üyesi silindi'
        })


# ==================== DERS ENDPOINTS ====================

@app.route('/api/courses', methods=['GET', 'POST'])
@require_auth()
def manage_courses():
    """Ders yönetimi"""
    if request.method == 'GET':
                # Bölüm yetkilisi ama bölümü yoksa
        if request.user_role == 'bolum_yetkilisi':
            user = User.query.get(request.user_id)
            if not user.department_id:
                return jsonify({
                    'status': 'error',
                    'message': 'Henüz bir bölüme atanmadınız. Lütfen admin ile iletişime geçin.'
                }), 403

        # Filtreleme
        teacher_id = request.args.get('teacher_id', type=int)
        dept_id = request.args.get('department_id', type=int)
        
        query = Course.query
        
        # Hocanın kendi dersleri
        if request.user_role == 'hoca':
            user = User.query.get(request.user_id)
            query = query.filter_by(teacher_id=user.teacher_id)
        
        # Bölüm yetkilisinin kendi bölümü
        elif request.user_role == 'bolum_yetkilisi':
            user = User.query.get(request.user_id)
            query = query.filter_by(department_id=user.department_id)
        
        if teacher_id:
            query = query.filter_by(teacher_id=teacher_id)
        if dept_id:
            query = query.filter_by(department_id=dept_id)
        
        courses = query.all()
        return jsonify({
            'status': 'success',
            'data': [
                {
                    'id': c.id,
                    'name': c.name,
                    'code': c.code,
                    'teacher_id': c.teacher_id,
                    'department_id': c.department_id,
                    'student_count': c.student_count,
                    'has_exam': c.has_exam,
                    'exam_duration': c.exam_duration,
                    'exam_type': c.exam_type,
                    'special_room': c.special_room
                } for c in courses
            ]
        })
    
    # POST - Admin ve bölüm yetkilisi ekleyebilir
    if request.user_role not in ['admin', 'bolum_yetkilisi']:
        return jsonify({'status': 'error', 'message': 'Yetersiz izin'}), 403
    
    data = request.get_json() or {}
    
    # Bölüm yetkilisi kontrolü
    department_id = data.get('department_id')
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        department_id = user.department_id
    
    course = Course(
        name=data.get('name', ''),
        code=data.get('code'),
        teacher_id=data.get('teacher_id'),
        department_id=department_id,
        program_id=data.get('program_id'),
        student_count=int(data.get('student_count', 0)),
        has_exam=data.get('has_exam', True),
        exam_duration=int(data.get('exam_duration', 60)),
        exam_type=data.get('exam_type', 'written'),
        special_room=data.get('special_room')
    )
    
    db.session.add(course)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'id': course.id,
        'message': 'Ders eklendi'
    }), 201


@app.route('/api/courses/<int:course_id>', methods=['PUT', 'DELETE'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def update_delete_course(course_id):
    """Ders güncelleme veya silme"""
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'status': 'error', 'message': 'Ders bulunamadı'}), 404
    
    # Bölüm yetkilisi sadece kendi bölümündeki dersi düzenleyebilir
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        if course.department_id != user.department_id:
            return jsonify({'status': 'error', 'message': 'Kendi bölümünüz dışındaki dersi düzenleyemezsiniz'}), 403
    
    if request.method == 'PUT':
        data = request.get_json() or {}
        
        if 'name' in data:
            course.name = data['name']
        if 'code' in data:
            course.code = data['code']
        if 'teacher_id' in data:
            course.teacher_id = data['teacher_id']
        
        # Bölüm yetkilisi departman değiştiremez, admin değiştirebilir
        if 'department_id' in data:
            if request.user_role == 'admin':
                course.department_id = data['department_id']
                
        if 'program_id' in data:
            course.program_id = data['program_id']
        if 'student_count' in data:
            course.student_count = int(data['student_count'])
        if 'exam_duration' in data:
            course.exam_duration = int(data['exam_duration'])
        if 'exam_type' in data:
            course.exam_type = data['exam_type']
        if 'has_exam' in data:
            course.has_exam = data['has_exam']
        if 'special_room' in data:
            course.special_room = data['special_room']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Ders güncellendi'
        })
    
    elif request.method == 'DELETE':
        # Kayıtlı öğrenci var mı kontrol et
        enrollments = Enrollment.query.filter_by(course_id=course_id).count()
        if enrollments > 0:
            return jsonify({'status': 'error', 'message': f'Bu derse {enrollments} öğrenci kayıtlı. Önce kayıtları kaldırın.'}), 400
        
        # Sınav var mı kontrol et
        exams = Exam.query.filter_by(course_id=course_id).count()
        if exams > 0:
            return jsonify({'status': 'error', 'message': 'Bu dersin sınavı planlanmış. Önce sınavı silin.'}), 400
        
        db.session.delete(course)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Ders silindi'
        })


# ==================== DERSLIK ENDPOINTS ====================

@app.route('/api/classrooms', methods=['GET', 'POST'])
@require_auth()
def manage_classrooms():
    """Derslik yönetimi"""
    if request.method == 'GET':
        classrooms = Classroom.query.all()
        return jsonify({
            'status': 'success',
            'data': [
                {
                    'id': c.id,
                    'name': c.name,
                    'capacity': c.capacity,
                    'is_available': c.is_available,
                    'is_special': c.is_special,
                    'special_type': c.special_type
                } for c in classrooms
            ]
        })
    
    # POST - Admin only
    if request.user_role != 'admin':
        return jsonify({'status': 'error', 'message': 'Yetersiz izin'}), 403
    
    data = request.get_json() or {}
    
    classroom = Classroom(
        name=data.get('name', ''),
        capacity=int(data.get('capacity', 30)),
        is_available=data.get('is_available', True),
        is_special=data.get('is_special', False),
        special_type=data.get('special_type')
    )
    
    db.session.add(classroom)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'id': classroom.id,
        'message': 'Derslik eklendi'
    }), 201


@app.route('/api/classrooms/<int:classroom_id>', methods=['PUT', 'DELETE'])
@require_auth(roles=['admin'])
def update_delete_classroom(classroom_id):
    """Derslik güncelleme veya silme"""
    classroom = Classroom.query.get(classroom_id)
    if not classroom:
        return jsonify({'status': 'error', 'message': 'Derslik bulunamadı'}), 404
    
    if request.method == 'PUT':
        data = request.get_json() or {}
        
        if 'name' in data:
            classroom.name = data['name']
        if 'capacity' in data:
            classroom.capacity = int(data['capacity'])
        if 'is_available' in data:
            classroom.is_available = data['is_available']
        if 'is_special' in data:
            classroom.is_special = data['is_special']
        if 'special_type' in data:
            classroom.special_type = data['special_type']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Derslik güncellendi'
        })
    
    elif request.method == 'DELETE':
        # Sınav ataması var mı kontrol et
        exams = Exam.query.filter_by(room_id=classroom_id).count()
        if exams > 0:
            return jsonify({'status': 'error', 'message': f'Bu dersliğe {exams} sınav atanmış. Önce sınavları kaldırın.'}), 400
        
        db.session.delete(classroom)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Derslik silindi'
        })


# ==================== SINAV ENDPOINTS ====================

@app.route('/api/exams', methods=['GET', 'DELETE'])
@require_auth()
def manage_exams():
    """Sınav yönetimi"""
    if request.method == 'GET':
        # Filtreleme
        teacher_id = request.args.get('teacher_id', type=int)
        student_id = request.args.get('student_id', type=int)
        dept_id = request.args.get('department_id', type=int)
        program_id = request.args.get('program_id', type=int)
        faculty_id = request.args.get('faculty_id', type=int)
        course_id = request.args.get('course_id', type=int)
        
        query = Exam.query
        
        # Hocanın kendi sınavları
        if request.user_role == 'hoca':
            user = User.query.get(request.user_id)
            courses = Course.query.filter_by(teacher_id=user.teacher_id).all()
            course_ids = [c.id for c in courses]
            query = query.filter(Exam.course_id.in_(course_ids))
        
        # Öğrencinin kendi sınavları
        elif request.user_role == 'ogrenci':
            user = User.query.get(request.user_id)
            enrollments = Enrollment.query.filter_by(student_id=user.student_id).all()
            course_ids = [e.course_id for e in enrollments]
            query = query.filter(Exam.course_id.in_(course_ids))
        
        # Bölüm yetkilisi kendi bölümünün sınavları
        elif request.user_role == 'bolum_yetkilisi':
            user = User.query.get(request.user_id)
            courses = Course.query.filter_by(department_id=user.department_id).all()
            course_ids = [c.id for c in courses]
            query = query.filter(Exam.course_id.in_(course_ids))
        
        # Admin tümünü görebilir
        
        if teacher_id:
            courses = Course.query.filter_by(teacher_id=teacher_id).all()
            course_ids = [c.id for c in courses]
            query = query.filter(Exam.course_id.in_(course_ids))
        
        if course_id:
            query = query.filter_by(course_id=course_id)
        
        if dept_id:
            courses = Course.query.filter_by(department_id=dept_id).all()
            course_ids = [c.id for c in courses]
            if course_ids:
                query = query.filter(Exam.course_id.in_(course_ids))
            else:
                return jsonify({'status': 'success', 'data': []})
        
        if program_id:
            courses = Course.query.filter_by(program_id=program_id).all()
            course_ids = [c.id for c in courses]
            if course_ids:
                query = query.filter(Exam.course_id.in_(course_ids))
            else:
                return jsonify({'status': 'success', 'data': []})
        if faculty_id:
            dept_ids = [d.id for d in Department.query.filter_by(faculty_id=faculty_id).all()]
            if dept_ids:
                courses = Course.query.filter(Course.department_id.in_(dept_ids)).all()
                course_ids = [c.id for c in courses]
                if course_ids:
                    query = query.filter(Exam.course_id.in_(course_ids))
                else:
                    return jsonify({'status': 'success', 'data': []})
            else:
                return jsonify({'status': 'success', 'data': []})
        
        exams = query.all()
        return jsonify({
            'status': 'success',
            'data': [e.to_dict() for e in exams]
        })
    
    # DELETE - Admin only (tüm sınavları sil)
    if request.user_role != 'admin':
        return jsonify({'status': 'error', 'message': 'Yetersiz izin'}), 403
    
    confirm = request.args.get('confirm', 'false').lower() == 'true'
    if not confirm:
        return jsonify({'status': 'error', 'message': 'confirm=true parametresi gerekli'}), 400
    
    count = Exam.query.count()
    Exam.query.delete()
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'deleted': count,
        'message': f'{count} sınav silindi'
    })


# ==================== PLANLAMA ENDPOINT ====================

@app.route('/api/schedule', methods=['POST'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def run_scheduler():
    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        if not user.department_id:
            return jsonify({
                'status': 'error',
                'message': 'Bölüm ataması olmayan kullanıcı planlama yapamaz.'
            }), 403

    """Otomatik sınav planlama (kısıtlı + basit backtracking + yakın derslik)."""
    data = request.get_json() or {}
    days = int(data.get('days', 5))
    force = data.get('force', False)
    dept_id = data.get('department_id')

    if request.user_role == 'bolum_yetkilisi':
        user = User.query.get(request.user_id)
        dept_id = user.department_id

    if force:
        Exam.query.delete()
        db.session.commit()

    try:
        courses_q = Course.query.filter_by(has_exam=True)
        if dept_id:
            courses_q = courses_q.filter_by(department_id=dept_id)
        courses = courses_q.all()
        if not courses:
            return jsonify({'status': 'warning', 'message': 'Planlanacak ders bulunamadı', 'created': []}), 200

        # Slots
        base_date = datetime.date.today()
        time_windows = [datetime.time(9, 0), datetime.time(11, 30), datetime.time(14, 0), datetime.time(16, 30)]
        slots = []
        for d in range(days):
            current = base_date + datetime.timedelta(days=d)
            weekday = current.strftime('%a')
            for tw in time_windows:
                start_dt = datetime.datetime.combine(current, tw)
                slots.append({'start': start_dt, 'weekday': weekday})

        # Classrooms
        classrooms = Classroom.query.filter_by(is_available=True).order_by(Classroom.capacity.desc()).all()
        if not classrooms:
            return jsonify({'status': 'error', 'message': 'Uygun derslik yok'}), 400
        room_by_id = {c.id: c for c in classrooms}

        # Proximity map (iki yönlü)
        proximity_map = {}
        proximities = ClassroomProximity.query.all()
        for rel in proximities:
            proximity_map.setdefault(rel.primary_classroom_id, []).append((rel.nearby_classroom_id, rel.distance or 0.0, rel.is_adjacent))
            proximity_map.setdefault(rel.nearby_classroom_id, []).append((rel.primary_classroom_id, rel.distance or 0.0, rel.is_adjacent))
        for rid in proximity_map:
            proximity_map[rid].sort(key=lambda x: (0 if x[2] else 1, x[1]))

        # Existing exams -> busy maps
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

        # Prefetch enrollments per course
        enrollments_map = {}
        for en in Enrollment.query.filter(Enrollment.course_id.in_([c.id for c in courses])).all():
            enrollments_map.setdefault(en.course_id, []).append(en.student_id)

        # Filter unscheduled courses
        target_courses = []
        for c in courses:
            if not force and Exam.query.filter_by(course_id=c.id).first():
                continue
            target_courses.append(c)

        target_courses.sort(key=lambda c: c.student_count if c.student_count else 0, reverse=True)

        best_plan = []
        plan = []

        def teacher_ok(course, slot_start, slot_end, weekday):
            if not course.teacher_id:
                return True
            teacher = Teacher.query.get(course.teacher_id)
            if teacher and teacher.available_days:
                allowed = [d.strip() for d in teacher.available_days.split(',') if d.strip()]
                # Eğer hoca hiç gün seçmediyse veya boşsa, varsayılan olarak hepsi uygun kabul edilebilir
                # Ancak burada listede varsa ve gün içinde yoksa False döner
                if allowed and weekday not in allowed:
                    return False
            
            # JSON detaylı kontrol (opsiyonel)
            # if teacher.availability_details: ...
            
            for b_start, b_end in teacher_busy.get(course.teacher_id, []):
                if overlaps(slot_start, slot_end, b_start, b_end):
                    return False
            return True

        def students_ok(course_id, slot_start, slot_end):
            # Öğrenci çakışması kontrolü
            # Bu kısım çok maliyetli olabilir, büyük veride optimize edilmeli
            # Şimdilik her kayıtlı öğrenci için bakıyoruz
            conflict_count = 0
            limit = 0 # Sıfır tolerans
            
            # Eğer dersin öğrenci sayısı çok fazlaysa bu kontrolü basitleştirebiliriz (örn: sadece program bazlı)
            
            for sid in enrollments_map.get(course_id, []):
                for b_start, b_end in student_busy.get(sid, []):
                    if overlaps(slot_start, slot_end, b_start, b_end):
                        conflict_count += 1
                        if conflict_count > limit:
                            return False
            return True

        def rooms_cluster_candidates(needed, course_special):
            base_rooms = []
            for r in classrooms:
                if course_special:
                    # Özel durum (lab vb.) varsa sadece uygun odalar
                    # course_special = "D101" (direkt ad) veya "lab" (tip) olabilir
                    is_match = (r.name == course_special) or (r.special_type == course_special)
                    
                    # Eğer special_room, 'lab' gibi genel bir tipse:
                    if not is_match and r.special_type and course_special.lower() in r.special_type.lower():
                        is_match = True
                        
                    if not is_match:
                        continue
                elif r.is_special:
                     # Dersin özel gereksinimi yoksa, özel odaları (lab vb.) kullanma
                     # Veya son çare olarak kullan? Şimdilik kullanma.
                     continue
                     
                base_rooms.append(r)


            # Tek derslik yeterli ise
            for r in base_rooms:
                if r.capacity >= needed:
                    yield [r]

            # Yakın derslik setleri
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

            # Son çare: en büyük kapasiteleri topla
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
                teacher_busy[course.teacher_id] = [(s, e) for (s, e) in teacher_busy.get(course.teacher_id, []) if not (s == slot_start and e == slot_end)]
            for sid in enrollments_map.get(course.id, []):
                student_busy[sid] = [(s, e) for (s, e) in student_busy.get(sid, []) if not (s == slot_start and e == slot_end)]

        def dfs(idx):
            nonlocal best_plan
            if idx == len(target_courses):
                best_plan = plan.copy()
                return True
            course = target_courses[idx]
            duration = course.exam_duration or 60
            for slot in slots:
                slot_start = slot['start']
                slot_end = slot_start + datetime.timedelta(minutes=duration)
                weekday = slot['weekday']

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
            return jsonify({'status': 'error', 'message': 'Hiçbir ders planlanamadı'}), 400

        created = []
        for course, cluster, slot_start, duration in best_plan:
            for room in cluster:
                exam = Exam(
                    course_id=course.id,
                    room_id=room.id,
                    slot_start=slot_start,
                    duration=duration,
                    slot=slot_start.isoformat()
                )
                db.session.add(exam)
                created.append({
                    'course': course.name,
                    'room': room.name,
                    'slot': slot_start.isoformat(),
                    'duration': duration
                })

        db.session.commit()

        status = 'success' if len(best_plan) == len(target_courses) else 'warning'
        message = f"{len(best_plan)}/{len(target_courses)} ders planlandı"
        if status == 'warning':
            message += ' (bazı dersler için uygun slot bulunamadı)'

        return jsonify({'status': status, 'created': len(best_plan), 'exams': created, 'message': message})

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Planlama hatası: {str(e)}'}), 500


# ==================== EXCEL ENDPOINTS ====================

@app.route('/api/excel/import-classlists', methods=['POST'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def import_classlists():
    """Kullanıcıdan yüklenen Excel dosyalarını içe aktar"""
    if 'files' not in request.files:
        return jsonify({'status': 'error', 'message': 'Dosya yüklenmedi. Klasör seçip dosyaları yükleyin.'}), 400
    
    files = request.files.getlist('files')
    if not files or len(files) == 0:
        return jsonify({'status': 'error', 'message': 'Hiçbir dosya seçilmedi'}), 400
    
    import tempfile
    import shutil
    
    processor = ExcelProcessor()
    results = {
        'files_total': len(files),
        'files_processed': 0,
        'students_created': 0,
        'enrollments_created': 0,
        'courses_created': 0,
        'errors': []
    }
    
    # Geçici klasör oluştur
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Tüm dosyaları geçici klasöre kaydet
        for file in files:
            if file.filename and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
                # Sadece dosya adını al, klasör yapısını atla
                filename = os.path.basename(file.filename)
                file_path = os.path.join(temp_dir, filename)
                file.save(file_path)
        
        # Geçici klasördeki dosyaları işle
        excel_files = list(Path(temp_dir).glob('*.xlsx')) + list(Path(temp_dir).glob('*.xls'))
        
        for filepath in excel_files:
            filename = filepath.name
            course_code = processor.extract_course_code_from_filename(filename)
            
            try:
                df, error = processor.read_excel_file(str(filepath))
                if error:
                    results['errors'].append({'file': filename, 'message': error})
                    continue
                
                students, error = processor.extract_student_data(df)
                if error:
                    results['errors'].append({'file': filename, 'message': error})
                    continue
                
                course = None
                if course_code:
                    course = Course.query.filter_by(code=course_code).first()
                    if not course:
                        course = Course(code=course_code, name=course_code)
                        db.session.add(course)
                        db.session.flush()
                        results['courses_created'] += 1
                
                for s in students:
                    stu = Student.query.filter_by(student_number=s['number']).first()
                    if not stu:
                        stu = Student(student_number=s['number'], name=s.get('name') or '')
                        db.session.add(stu)
                        db.session.flush()
                        results['students_created'] += 1
                    
                    if course:
                        exists = Enrollment.query.filter_by(student_id=stu.id, course_id=course.id).first()
                        if not exists:
                            db.session.add(Enrollment(student_id=stu.id, course_id=course.id))
                            results['enrollments_created'] += 1
                
                if course:
                    course.student_count = Enrollment.query.filter_by(course_id=course.id).count()
                
                db.session.commit()
                results['files_processed'] += 1
                
            except Exception as e:
                db.session.rollback()
                results['errors'].append({'file': filename, 'message': str(e)})
        
        return jsonify({
            'status': 'success',
            'import': results
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        # Geçici klasörü temizle
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@app.route('/api/excel/upload-classlists', methods=['POST'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def upload_classlists():
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({'status': 'error', 'message': 'Dosya yüklenmedi'}), 400

    import tempfile

    file = request.files['file']
    course_code = (request.form.get('course_code') or '').strip().upper()
    processor = ExcelProcessor()

    # Geçici dosyaya kaydet
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name

    try:
        # Ders kodu boşsa dosya adından bulmayı dene
        if not course_code:
            course_code = processor.extract_course_code_from_filename(file.filename) or ''

        if not course_code:
            return jsonify({'status': 'error', 'message': 'Ders kodu bulunamadı. Dosya adına ekleyin veya formda girin.'}), 400

        df, error = processor.read_excel_file(temp_path)
        if error:
            return jsonify({'status': 'error', 'message': error}), 400

        students, error = processor.extract_student_data(df)
        if error:
            return jsonify({'status': 'error', 'message': error}), 400

        # Ders oluştur veya bul
        course = Course.query.filter_by(code=course_code).first()
        if not course:
            course = Course(code=course_code, name=course_code)
            db.session.add(course)
            db.session.flush()

        imported = 0
        created_students = 0

        for s in students:
            student_num = s['number']
            student_name = s.get('name') or ''

            student = Student.query.filter_by(student_number=student_num).first()
            if not student:
                student = Student(student_number=student_num, name=student_name)
                db.session.add(student)
                db.session.flush()
                created_students += 1

            enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
            if not enrollment:
                db.session.add(Enrollment(student_id=student.id, course_id=course.id))
                imported += 1

        course.student_count = Enrollment.query.filter_by(course_id=course.id).count()
        db.session.commit()

        return jsonify({
            'status': 'success',
            'course_id': course.id,
            'course_code': course_code,
            'students_imported': imported,
            'students_created': created_students,
            'total_students': course.student_count
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/api/excel/import-proximity', methods=['POST'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def import_proximity():
    """Kullanıcıdan yüklenen derslik yakınlık Excel dosyasını içe aktar"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Dosya yüklenmedi'}), 400
    
    file = request.files['file']
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return jsonify({'status': 'error', 'message': 'Geçerli bir Excel dosyası seçin (.xlsx veya .xls)'}), 400
    
    import tempfile
    
    # Geçici dosyaya kaydet
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name
    
    try:
        result = import_proximity_to_db(temp_path, db, Classroom, ClassroomProximity)
        status_code = 200 if result.get('status') == 'success' else 400
        return jsonify(result), status_code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route('/api/excel/import-capacity', methods=['POST'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def import_capacity():
    """Kullanıcıdan yüklenen kapasite Excel dosyasını içe aktar"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Dosya yüklenmedi'}), 400
    
    file = request.files['file']
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return jsonify({'status': 'error', 'message': 'Geçerli bir Excel dosyası seçin (.xlsx veya .xls)'}), 400
    
    import tempfile
    
    # Geçici dosyaya kaydet
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name
    
    try:
        result = import_capacity_to_db(temp_path, db, Classroom, Course)
        status_code = 200 if result.get('status') in ['success', 'partial'] else 400
        return jsonify(result), status_code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ==================== AKADEMİK KADRO EXCEL IMPORT ====================

@app.route('/api/excel/import-teachers', methods=['POST'])
@require_auth(roles=['admin', 'bolum_yetkilisi'])
def import_teachers():
    """akademik_kadro.xlsx dosyasından öğretim üyelerini ve fakülteleri içe aktar"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Dosya yüklenmedi'}), 400
    
    file = request.files['file']
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return jsonify({'status': 'error', 'message': 'Geçerli bir Excel dosyası seçin (.xlsx veya .xls)'}), 400
    
    import tempfile
    
    # Geçici dosyaya kaydet
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        file.save(tmp.name)
        temp_path = tmp.name
    
    try:
        result = import_teachers_from_excel(temp_path, db)
        status_code = 200 if result.get('status') == 'success' else 400
        return jsonify(result), status_code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ==================== ÖĞRETİM ÜYESİ DIŞ KAYNAK İÇE AKTARMA (KALDIRILDI) ====================
# Not: KOSTÜ web sitesinden çekme özelliği kaldırıldı.

@app.route('/api/exams/export', methods=['GET'])
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
            
            rows.append({
                'Ders': course.name if course else 'N/A',
                'Ders Kodu': course.code if course else 'N/A',
                'Öğretim Üyesi': teacher.name if teacher else 'N/A',
                'Derslik': room.name if room else 'N/A',
                'Kapasite': room.capacity if room else 0,
                'Başlama Saati': exam.slot_start.strftime('%Y-%m-%d %H:%M') if exam.slot_start else '',
                'Süre (dk)': exam.duration,
                'Sınav Türü': course.exam_type if course else 'N/A',
                'Öğrenci Sayısı': course.student_count if course else 0
            })
        
        df = pd.DataFrame(rows)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sınav Programı', index=False)
        
        output.seek(0)
        return send_file(
            output,
            download_name='sinav_programi.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Export hatası: {str(e)}'}), 500


# ==================== VERITABANI YÖNETIMI ====================

@app.route('/api/seed', methods=['POST'])
@require_auth(roles=['admin'])
def seed_data():
    """Örnek veri yükle"""
    data = request.get_json() or {}
    force = data.get('force', False)
    
    if force:
        Exam.query.delete()
        Enrollment.query.delete()
        Course.query.delete()
        Student.query.delete()
        Teacher.query.delete()
        Department.query.delete()
        Faculty.query.delete()
        db.session.commit()
    
    fak = Faculty(name='Mühendislik Fakültesi')
    db.session.add(fak)
    db.session.flush()
    
    dept = Department(name='Bilgisayar Mühendisliği', faculty_id=fak.id)
    db.session.add(dept)
    db.session.flush()
    
    teachers = [
        Teacher(name='Dr. Ahmet Yılmaz', department_id=dept.id),
        Teacher(name='Prof. Ayşe Demir', department_id=dept.id),
        Teacher(name='Dr. Mehmet Kara', department_id=dept.id),
    ]
    for t in teachers:
        db.session.add(t)
    db.session.flush()
    
    classrooms = [
        Classroom(name='A101', capacity=120),
        Classroom(name='A102', capacity=120),
        Classroom(name='B201', capacity=80),
        Classroom(name='B202', capacity=80),
        Classroom(name='C301', capacity=40),
    ]
    for c in classrooms:
        db.session.add(c)
    db.session.flush()
    
    courses = [
        Course(name='Algoritma ve Programlama', code='YZM332', teacher_id=teachers[0].id, department_id=dept.id, student_count=110),
        Course(name='Veri Tabanı Sistemleri', code='BLM111', teacher_id=teachers[1].id, department_id=dept.id, student_count=75),
        Course(name='İşletme Yönetimi', code='IKT201', teacher_id=teachers[2].id, department_id=dept.id, student_count=60),
    ]
    for c in courses:
        db.session.add(c)
    db.session.flush()
    
    students = [
        Student(student_number='2020001', name='Mehmet Şahin'),
        Student(student_number='2020002', name='Ayşe Yücel'),
        Student(student_number='2020003', name='Ali Demir'),
    ]
    for s in students:
        db.session.add(s)
    db.session.flush()
    
    for c in courses:
        for s in students[:2]:
            enrollment = Enrollment(student_id=s.id, course_id=c.id)
            db.session.add(enrollment)
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Örnek veriler yüklendi',
        'created': {
            'faculties': 1,
            'departments': 1,
            'teachers': len(teachers),
            'classrooms': len(classrooms),
            'courses': len(courses),
            'students': len(students)
        }
    })


if __name__ == '__main__':
    print('🚀 KOSTÜ Sınav Programı Yönetim Sistemi başlatılıyor...')
    init_db()
    port = int(os.getenv('API_PORT', 5000))
    host = os.getenv('API_HOST', '0.0.0.0')
    print(f'✅ Sunucu çalışıyor: {host}:{port}')
    app.run(host=host, port=port, debug=True)
