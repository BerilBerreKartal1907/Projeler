"""
KOSTÜ Sınav Programı Yönetim Sistemi - Backend API
Flask, SQLAlchemy, JWT Authentication

Bölüm Yetkilisi (Department Authority) Role Restrictions:
- Can only manage teachers within their department
- Can only manage courses within their department
- Can handle special rooms/exams within their department
- All operations restricted to their assigned department_id
"""

import os
import jwt
import datetime
from functools import wraps
from flask import Flask, request, jsonify, g, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import tempfile
import shutil

# Excel işleme modülünü import et
from excel_processor import (
    ExcelProcessor,
    batch_process_folder,
    import_classlists_to_db,
    import_proximity_to_db,
    import_capacity_to_db,
    import_teachers_from_excel
)

# ==================== APP CONFIGURATION ====================

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'kostu-sinav-programi-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'mysql+pymysql://root:password@localhost/kostu_sinav_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
CORS(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== DATABASE MODELS ====================

class Faculty(db.Model):
    """Fakülte modeli"""
    __tablename__ = 'faculties'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    code = db.Column(db.String(20), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    departments = db.relationship('Department', backref='faculty', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Department(db.Model):
    """Bölüm modeli"""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20))
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    courses = db.relationship('Course', backref='department', lazy='dynamic')
    teachers = db.relationship('Teacher', backref='department', lazy='dynamic')
    users = db.relationship('User', backref='department', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'faculty_id': self.faculty_id,
            'faculty_name': self.faculty.name if self.faculty else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class User(db.Model):
    """Kullanıcı modeli"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(200))
    role = db.Column(db.String(50), nullable=False, default='ogrenci')
    # Roles: admin, bolum_yetkilisi, hoca, ogrenci
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        return data


class Teacher(db.Model):
    """Öğretim Üyesi modeli"""
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(50))  # Prof. Dr., Doç. Dr., etc.
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    faculty = db.Column(db.String(200))  # Fakülte bilgisi (string olarak)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # İlişkiler
    courses = db.relationship('Course', backref='teacher', lazy='dynamic')
    availability = db.relationship('TeacherAvailability', backref='teacher', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'title': self.title,
            'email': self.email,
            'phone': self.phone,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'faculty': self.faculty,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'course_count': self.courses.count()
        }


class TeacherAvailability(db.Model):
    """Öğretim üyesi müsaitlik durumu"""
    __tablename__ = 'teacher_availability'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20))  # "09:00-11:00"
    is_available = db.Column(db.Boolean, default=True)
    reason = db.Column(db.Text)  # Müsait değilse nedeni
    
    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.name if self.teacher else None,
            'date': self.date.isoformat() if self.date else None,
            'time_slot': self.time_slot,
            'is_available': self.is_available,
            'reason': self.reason
        }


class Course(db.Model):
    """Ders modeli"""
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    credit = db.Column(db.Integer, default=3)
    student_count = db.Column(db.Integer, default=0)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    semester = db.Column(db.String(20))  # "2024-Güz", "2024-Bahar"
    year = db.Column(db.Integer)
    requires_special_room = db.Column(db.Boolean, default=False)
    special_room_type = db.Column(db.String(50))  # "lab", "bilgisayar", "cizim"
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # İlişkiler
    enrollments = db.relationship('Enrollment', backref='course', lazy='dynamic')
    exams = db.relationship('Exam', backref='course', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'credit': self.credit,
            'student_count': self.student_count,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.name if self.teacher else None,
            'semester': self.semester,
            'year': self.year,
            'requires_special_room': self.requires_special_room,
            'special_room_type': self.special_room_type,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Student(db.Model):
    """Öğrenci modeli"""
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200))
    email = db.Column(db.String(120))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    year = db.Column(db.Integer)  # Sınıf (1, 2, 3, 4)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    enrollments = db.relationship('Enrollment', backref='student', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_number': self.student_number,
            'name': self.name,
            'email': self.email,
            'department_id': self.department_id,
            'year': self.year,
            'enrolled_courses': self.enrollments.count()
        }


class Enrollment(db.Model):
    """Ders kaydı (öğrenci-ders ilişkisi)"""
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    semester = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', name='unique_enrollment'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_number': self.student.student_number if self.student else None,
            'course_id': self.course_id,
            'course_code': self.course.code if self.course else None,
            'semester': self.semester
        }


class Classroom(db.Model):
    """Derslik modeli"""
    __tablename__ = 'classrooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    building = db.Column(db.String(100))
    floor = db.Column(db.Integer)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    is_special = db.Column(db.Boolean, default=False)
    special_type = db.Column(db.String(50))  # "lab", "bilgisayar", "cizim"
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # İlişkiler
    exams = db.relationship('Exam', backref='classroom', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'building': self.building,
            'floor': self.floor,
            'capacity': self.capacity,
            'is_special': self.is_special,
            'special_type': self.special_type,
            'is_active': self.is_active
        }


class ClassroomProximity(db.Model):
    """Derslik yakınlık ilişkisi"""
    __tablename__ = 'classroom_proximity'
    
    id = db.Column(db.Integer, primary_key=True)
    primary_classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    nearby_classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    distance = db.Column(db.Float)  # Metre cinsinden mesafe
    is_adjacent = db.Column(db.Boolean, default=False)  # Bitişik mi?
    
    primary_classroom = db.relationship('Classroom', foreign_keys=[primary_classroom_id])
    nearby_classroom = db.relationship('Classroom', foreign_keys=[nearby_classroom_id])
    
    __table_args__ = (
        db.UniqueConstraint('primary_classroom_id', 'nearby_classroom_id', name='unique_proximity'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'primary_classroom_id': self.primary_classroom_id,
            'primary_classroom_name': self.primary_classroom.name if self.primary_classroom else None,
            'nearby_classroom_id': self.nearby_classroom_id,
            'nearby_classroom_name': self.nearby_classroom.name if self.nearby_classroom else None,
            'distance': self.distance,
            'is_adjacent': self.is_adjacent
        }


class Exam(db.Model):
    """Sınav modeli"""
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'))
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, default=90)  # Dakika cinsinden
    exam_type = db.Column(db.String(20), default='final')  # vize, final, bütünleme
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    requires_special_room = db.Column(db.Boolean, default=False)
    special_room_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_code': self.course.code if self.course else None,
            'course_name': self.course.name if self.course else None,
            'classroom_id': self.classroom_id,
            'classroom_name': self.classroom.name if self.classroom else None,
            'date': self.date.isoformat() if self.date else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'exam_type': self.exam_type,
            'status': self.status,
            'requires_special_room': self.requires_special_room,
            'special_room_type': self.special_room_type,
            'student_count': self.course.student_count if self.course else 0
        }


class SpecialExamRequest(db.Model):
    """Özel durum sınav talebi (Bölüm yetkilisi tarafından oluşturulur)"""
    __tablename__ = 'special_exam_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    request_type = db.Column(db.String(50))  # "ozel_salon", "ozel_tarih", "ozel_sure"
    reason = db.Column(db.Text)
    preferred_date = db.Column(db.Date)
    preferred_time = db.Column(db.String(20))
    preferred_room_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    course = db.relationship('Course', foreign_keys=[course_id])
    requester = db.relationship('User', foreign_keys=[requested_by])
    department = db.relationship('Department', foreign_keys=[department_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'course_code': self.course.code if self.course else None,
            'course_name': self.course.name if self.course else None,
            'requested_by': self.requested_by,
            'requester_name': self.requester.name if self.requester else None,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'request_type': self.request_type,
            'reason': self.reason,
            'preferred_date': self.preferred_date.isoformat() if self.preferred_date else None,
            'preferred_time': self.preferred_time,
            'preferred_room_type': self.preferred_room_type,
            'status': self.status,
            'admin_notes': self.admin_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }


class ExamSchedule(db.Model):
    """Sınav programı (dönemlik)"""
    __tablename__ = 'exam_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='draft')  # draft, published, completed
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    published_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'semester': self.semester,
            'year': self.year,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None
        }


# ==================== AUTHENTICATION DECORATOR ====================

def require_auth(allowed_roles=None):
    """
    JWT tabanlı kimlik doğrulama ve yetkilendirme decorator'ı
    
    Args:
        allowed_roles: İzin verilen roller listesi. None ise sadece giriş yapılmış olması yeterli.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            
            if not auth_header:
                return jsonify({'error': 'Authorization header gerekli'}), 401
            
            try:
                # Bearer token formatı
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                else:
                    token = auth_header
                
                # Token'ı decode et
                payload = jwt.decode(
                    token, 
                    app.config['SECRET_KEY'], 
                    algorithms=['HS256']
                )
                
                # Kullanıcıyı bul
                user = User.query.get(payload.get('user_id'))
                if not user:
                    return jsonify({'error': 'Kullanıcı bulunamadı'}), 401
                
                if not user.is_active:
                    return jsonify({'error': 'Kullanıcı hesabı devre dışı'}), 401
                
                # Rol kontrolü
                if allowed_roles and user.role not in allowed_roles:
                    return jsonify({
                        'error': 'Bu işlem için yetkiniz yok',
                        'required_roles': allowed_roles,
                        'your_role': user.role
                    }), 403
                
                # Kullanıcı bilgisini g'ye ekle
                g.current_user = user
                
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token süresi dolmuş'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Geçersiz token'}), 401
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def generate_token(user):
    """JWT token oluştur"""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'department_id': user.department_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


# ==================== HELPER FUNCTIONS ====================

def check_department_access(user, department_id):
    """
    Kullanıcının belirtilen bölüme erişimi olup olmadığını kontrol eder
    Admin her bölüme erişebilir, bolum_yetkilisi sadece kendi bölümüne
    """
    if user.role == 'admin':
        return True
    if user.role == 'bolum_yetkilisi':
        return user.department_id == department_id
    return False


def get_user_department_filter(user):
    """
    Kullanıcının rolüne göre department filtresi döndürür
    bolum_yetkilisi için kendi department_id'si, admin için None (tüm bölümler)
    """
    if user.role == 'bolum_yetkilisi':
        return user.department_id
    return None


# ==================== AUTH ENDPOINTS ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Yeni kullanıcı kaydı"""
    data = request.get_json()
    
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} alanı gerekli'}), 400
    
    # Kullanıcı adı veya email zaten var mı?
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Bu kullanıcı adı zaten kullanılıyor'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Bu email zaten kullanılıyor'}), 400
    
    # Yeni kullanıcı oluştur
    user = User(
        username=data['username'],
        email=data['email'],
        name=data.get('name'),
        role=data.get('role', 'ogrenci'),
        department_id=data.get('department_id')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'Kullanıcı başarıyla oluşturuldu',
        'user': user.to_dict()
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Kullanıcı girişi"""
    data = request.get_json()
    
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Kullanıcı adı ve şifre gerekli'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Geçersiz kullanıcı adı veya şifre'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Kullanıcı hesabı devre dışı'}), 401
    
    # Son giriş zamanını güncelle
    user.last_login = datetime.datetime.utcnow()
    db.session.commit()
    
    token = generate_token(user)
    
    return jsonify({
        'message': 'Giriş başarılı',
        'token': token,
        'user': user.to_dict()
    })


@app.route('/api/auth/me', methods=['GET'])
@require_auth()
def get_current_user():
    """Mevcut kullanıcı bilgisi"""
    return jsonify({'user': g.current_user.to_dict()})


@app.route('/api/auth/change-password', methods=['POST'])
@require_auth()
def change_password():
    """Şifre değiştirme"""
    data = request.get_json()
    
    if not data.get('current_password') or not data.get('new_password'):
        return jsonify({'error': 'Mevcut ve yeni şifre gerekli'}), 400
    
    if not g.current_user.check_password(data['current_password']):
        return jsonify({'error': 'Mevcut şifre yanlış'}), 400
    
    g.current_user.set_password(data['new_password'])
    db.session.commit()
    
    return jsonify({'message': 'Şifre başarıyla değiştirildi'})


# ==================== FACULTY ENDPOINTS ====================

@app.route('/api/faculties', methods=['GET', 'POST'])
@require_auth(['admin'])
def manage_faculties():
    """Fakülte yönetimi (sadece admin)"""
    if request.method == 'GET':
        faculties = Faculty.query.all()
        return jsonify({'faculties': [f.to_dict() for f in faculties]})
    
    # POST - Yeni fakülte ekle
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Fakülte adı gerekli'}), 400
    
    if Faculty.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Bu fakülte zaten var'}), 400
    
    faculty = Faculty(
        name=data['name'],
        code=data.get('code')
    )
    db.session.add(faculty)
    db.session.commit()
    
    return jsonify({
        'message': 'Fakülte oluşturuldu',
        'faculty': faculty.to_dict()
    }), 201


# ==================== DEPARTMENT ENDPOINTS ====================

@app.route('/api/departments', methods=['GET', 'POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def manage_departments():
    """Bölüm yönetimi"""
    if request.method == 'GET':
        # Bölüm yetkilisi sadece kendi bölümünü görür
        if g.current_user.role == 'bolum_yetkilisi':
            departments = Department.query.filter_by(id=g.current_user.department_id).all()
        else:
            departments = Department.query.all()
        return jsonify({'departments': [d.to_dict() for d in departments]})
    
    # POST - Sadece admin bölüm ekleyebilir
    if g.current_user.role != 'admin':
        return jsonify({'error': 'Sadece admin bölüm ekleyebilir'}), 403
    
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Bölüm adı gerekli'}), 400
    
    department = Department(
        name=data['name'],
        code=data.get('code'),
        faculty_id=data.get('faculty_id')
    )
    db.session.add(department)
    db.session.commit()
    
    return jsonify({
        'message': 'Bölüm oluşturuldu',
        'department': department.to_dict()
    }), 201


# ==================== TEACHER ENDPOINTS ====================

@app.route('/api/teachers', methods=['GET', 'POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def manage_teachers():
    """
    Öğretim üyesi yönetimi
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - GET: Sadece kendi bölümündeki öğretim üyelerini görebilir
    - POST: Sadece kendi bölümüne öğretim üyesi ekleyebilir
    """
    if request.method == 'GET':
        query = Teacher.query
        
        # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki öğretim üyelerini görebilir
        if g.current_user.role == 'bolum_yetkilisi':
            query = query.filter_by(department_id=g.current_user.department_id)
        elif request.args.get('department_id'):
            query = query.filter_by(department_id=request.args.get('department_id'))
        
        teachers = query.all()
        return jsonify({'teachers': [t.to_dict() for t in teachers]})
    
    # POST - Yeni öğretim üyesi ekle
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Öğretim üyesi adı gerekli'}), 400
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümüne öğretim üyesi ekleyebilir
    if g.current_user.role == 'bolum_yetkilisi':
        # department_id'yi kullanıcının bölümüne zorla
        department_id = g.current_user.department_id
        
        # Eğer farklı bir department_id gönderildiyse uyarı ver
        if data.get('department_id') and data['department_id'] != department_id:
            return jsonify({
                'error': 'Bölüm yetkilisi sadece kendi bölümüne öğretim üyesi ekleyebilir',
                'your_department_id': department_id
            }), 403
    else:
        department_id = data.get('department_id')
    
    # Email kontrolü
    if data.get('email'):
        existing = Teacher.query.filter_by(email=data['email']).first()
        if existing:
            return jsonify({'error': 'Bu email zaten kullanılıyor'}), 400
    
    teacher = Teacher(
        name=data['name'],
        title=data.get('title'),
        email=data.get('email'),
        phone=data.get('phone'),
        department_id=department_id,
        faculty=data.get('faculty')
    )
    db.session.add(teacher)
    db.session.commit()
    
    return jsonify({
        'message': 'Öğretim üyesi eklendi',
        'teacher': teacher.to_dict()
    }), 201


@app.route('/api/teachers/<int:teacher_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth(['admin', 'bolum_yetkilisi'])
def update_delete_teacher(teacher_id):
    """
    Öğretim üyesi güncelleme/silme
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - Sadece kendi bölümündeki öğretim üyelerini güncelleyebilir/silebilir
    """
    teacher = Teacher.query.get_or_404(teacher_id)
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki öğretim üyelerini yönetebilir
    if g.current_user.role == 'bolum_yetkilisi':
        if teacher.department_id != g.current_user.department_id:
            return jsonify({
                'error': 'Bu öğretim üyesi sizin bölümünüzde değil',
                'teacher_department_id': teacher.department_id,
                'your_department_id': g.current_user.department_id
            }), 403
    
    if request.method == 'GET':
        return jsonify({'teacher': teacher.to_dict()})
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Güncellenebilir alanlar
        if data.get('name'):
            teacher.name = data['name']
        if 'title' in data:
            teacher.title = data['title']
        if 'email' in data:
            if data['email']:
                existing = Teacher.query.filter(
                    Teacher.email == data['email'],
                    Teacher.id != teacher_id
                ).first()
                if existing:
                    return jsonify({'error': 'Bu email zaten kullanılıyor'}), 400
            teacher.email = data['email']
        if 'phone' in data:
            teacher.phone = data['phone']
        if 'faculty' in data:
            teacher.faculty = data['faculty']
        if 'is_active' in data:
            teacher.is_active = data['is_active']
        
        # ✅ FIX: Bölüm yetkilisi department_id'yi değiştiremez
        if g.current_user.role == 'bolum_yetkilisi':
            if data.get('department_id') and data['department_id'] != g.current_user.department_id:
                return jsonify({
                    'error': 'Bölüm yetkilisi öğretim üyesini başka bölüme taşıyamaz'
                }), 403
        else:
            # Admin department_id'yi değiştirebilir
            if 'department_id' in data:
                teacher.department_id = data['department_id']
        
        db.session.commit()
        return jsonify({
            'message': 'Öğretim üyesi güncellendi',
            'teacher': teacher.to_dict()
        })
    
    if request.method == 'DELETE':
        db.session.delete(teacher)
        db.session.commit()
        return jsonify({'message': 'Öğretim üyesi silindi'})


@app.route('/api/teachers/<int:teacher_id>/availability', methods=['GET', 'POST'])
@require_auth(['admin', 'bolum_yetkilisi', 'hoca'])
def manage_teacher_availability(teacher_id):
    """Öğretim üyesi müsaitlik durumu yönetimi"""
    teacher = Teacher.query.get_or_404(teacher_id)
    
    # Bölüm yetkilisi sadece kendi bölümündeki öğretmenlerin müsaitliğini yönetebilir
    if g.current_user.role == 'bolum_yetkilisi':
        if teacher.department_id != g.current_user.department_id:
            return jsonify({'error': 'Bu öğretim üyesi sizin bölümünüzde değil'}), 403
    
    # Hoca sadece kendi müsaitliğini yönetebilir
    if g.current_user.role == 'hoca':
        user_teacher = Teacher.query.filter_by(email=g.current_user.email).first()
        if not user_teacher or user_teacher.id != teacher_id:
            return jsonify({'error': 'Sadece kendi müsaitliğinizi yönetebilirsiniz'}), 403
    
    if request.method == 'GET':
        availabilities = TeacherAvailability.query.filter_by(teacher_id=teacher_id).all()
        return jsonify({'availability': [a.to_dict() for a in availabilities]})
    
    # POST - Müsaitlik ekle
    data = request.get_json()
    
    if not data.get('date'):
        return jsonify({'error': 'Tarih gerekli'}), 400
    
    availability = TeacherAvailability(
        teacher_id=teacher_id,
        date=datetime.datetime.strptime(data['date'], '%Y-%m-%d').date(),
        time_slot=data.get('time_slot'),
        is_available=data.get('is_available', True),
        reason=data.get('reason')
    )
    db.session.add(availability)
    db.session.commit()
    
    return jsonify({
        'message': 'Müsaitlik durumu eklendi',
        'availability': availability.to_dict()
    }), 201


# ==================== COURSE ENDPOINTS ====================

@app.route('/api/courses', methods=['GET', 'POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def manage_courses():
    """
    Ders yönetimi
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - GET: Sadece kendi bölümündeki dersleri görebilir
    - POST: Sadece kendi bölümüne ders ekleyebilir
    """
    if request.method == 'GET':
        query = Course.query
        
        # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki dersleri görebilir
        if g.current_user.role == 'bolum_yetkilisi':
            query = query.filter_by(department_id=g.current_user.department_id)
        elif request.args.get('department_id'):
            query = query.filter_by(department_id=request.args.get('department_id'))
        
        if request.args.get('teacher_id'):
            query = query.filter_by(teacher_id=request.args.get('teacher_id'))
        
        if request.args.get('semester'):
            query = query.filter_by(semester=request.args.get('semester'))
        
        courses = query.all()
        return jsonify({'courses': [c.to_dict() for c in courses]})
    
    # POST - Yeni ders ekle
    data = request.get_json()
    
    if not data.get('code') or not data.get('name'):
        return jsonify({'error': 'Ders kodu ve adı gerekli'}), 400
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümüne ders ekleyebilir
    if g.current_user.role == 'bolum_yetkilisi':
        department_id = g.current_user.department_id
        
        if data.get('department_id') and data['department_id'] != department_id:
            return jsonify({
                'error': 'Bölüm yetkilisi sadece kendi bölümüne ders ekleyebilir',
                'your_department_id': department_id
            }), 403
        
        # ✅ FIX: Öğretim üyesi atanacaksa, o öğretim üyesi de aynı bölümde olmalı
        if data.get('teacher_id'):
            teacher = Teacher.query.get(data['teacher_id'])
            if teacher and teacher.department_id != department_id:
                return jsonify({
                    'error': 'Sadece kendi bölümünüzdeki öğretim üyelerini atayabilirsiniz'
                }), 403
    else:
        department_id = data.get('department_id')
    
    # Aynı kodlu ders var mı?
    existing = Course.query.filter_by(code=data['code']).first()
    if existing:
        return jsonify({'error': 'Bu ders kodu zaten var'}), 400
    
    course = Course(
        code=data['code'],
        name=data['name'],
        credit=data.get('credit', 3),
        student_count=data.get('student_count', 0),
        department_id=department_id,
        teacher_id=data.get('teacher_id'),
        semester=data.get('semester'),
        year=data.get('year'),
        requires_special_room=data.get('requires_special_room', False),
        special_room_type=data.get('special_room_type')
    )
    db.session.add(course)
    db.session.commit()
    
    return jsonify({
        'message': 'Ders eklendi',
        'course': course.to_dict()
    }), 201


@app.route('/api/courses/<int:course_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth(['admin', 'bolum_yetkilisi'])
def update_delete_course(course_id):
    """
    Ders güncelleme/silme
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - Sadece kendi bölümündeki dersleri güncelleyebilir/silebilir
    """
    course = Course.query.get_or_404(course_id)
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki dersleri yönetebilir
    if g.current_user.role == 'bolum_yetkilisi':
        if course.department_id != g.current_user.department_id:
            return jsonify({
                'error': 'Bu ders sizin bölümünüzde değil',
                'course_department_id': course.department_id,
                'your_department_id': g.current_user.department_id
            }), 403
    
    if request.method == 'GET':
        return jsonify({'course': course.to_dict()})
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Güncellenebilir alanlar
        if data.get('name'):
            course.name = data['name']
        if 'credit' in data:
            course.credit = data['credit']
        if 'student_count' in data:
            course.student_count = data['student_count']
        if 'semester' in data:
            course.semester = data['semester']
        if 'year' in data:
            course.year = data['year']
        
        # ✅ FIX: Özel salon ihtiyacı - Bölüm yetkilisi bunu ayarlayabilir
        if 'requires_special_room' in data:
            course.requires_special_room = data['requires_special_room']
        if 'special_room_type' in data:
            course.special_room_type = data['special_room_type']
        
        if 'is_active' in data:
            course.is_active = data['is_active']
        
        # ✅ FIX: Bölüm yetkilisi department_id'yi değiştiremez
        if g.current_user.role == 'bolum_yetkilisi':
            if data.get('department_id') and data['department_id'] != g.current_user.department_id:
                return jsonify({
                    'error': 'Bölüm yetkilisi dersi başka bölüme taşıyamaz'
                }), 403
            
            # ✅ FIX: Öğretim üyesi değiştirilecekse, yeni öğretim üyesi de aynı bölümde olmalı
            if data.get('teacher_id'):
                teacher = Teacher.query.get(data['teacher_id'])
                if teacher and teacher.department_id != g.current_user.department_id:
                    return jsonify({
                        'error': 'Sadece kendi bölümünüzdeki öğretim üyelerini atayabilirsiniz'
                    }), 403
                course.teacher_id = data['teacher_id']
        else:
            # Admin her şeyi değiştirebilir
            if 'department_id' in data:
                course.department_id = data['department_id']
            if 'teacher_id' in data:
                course.teacher_id = data['teacher_id']
        
        db.session.commit()
        return jsonify({
            'message': 'Ders güncellendi',
            'course': course.to_dict()
        })
    
    if request.method == 'DELETE':
        db.session.delete(course)
        db.session.commit()
        return jsonify({'message': 'Ders silindi'})


# ==================== CLASSROOM ENDPOINTS ====================

@app.route('/api/classrooms', methods=['GET', 'POST'])
@require_auth(['admin'])
def manage_classrooms():
    """Derslik yönetimi (sadece admin)"""
    if request.method == 'GET':
        query = Classroom.query
        
        if request.args.get('is_special'):
            is_special = request.args.get('is_special').lower() == 'true'
            query = query.filter_by(is_special=is_special)
        
        if request.args.get('min_capacity'):
            query = query.filter(Classroom.capacity >= int(request.args.get('min_capacity')))
        
        classrooms = query.all()
        return jsonify({'classrooms': [c.to_dict() for c in classrooms]})
    
    # POST - Yeni derslik ekle
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Derslik adı gerekli'}), 400
    
    if Classroom.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Bu derslik zaten var'}), 400
    
    classroom = Classroom(
        name=data['name'],
        building=data.get('building'),
        floor=data.get('floor'),
        capacity=data.get('capacity', 30),
        is_special=data.get('is_special', False),
        special_type=data.get('special_type')
    )
    db.session.add(classroom)
    db.session.commit()
    
    return jsonify({
        'message': 'Derslik eklendi',
        'classroom': classroom.to_dict()
    }), 201


@app.route('/api/classrooms/<int:classroom_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth(['admin'])
def update_delete_classroom(classroom_id):
    """Derslik güncelleme/silme (sadece admin)"""
    classroom = Classroom.query.get_or_404(classroom_id)
    
    if request.method == 'GET':
        return jsonify({'classroom': classroom.to_dict()})
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if data.get('name'):
            existing = Classroom.query.filter(
                Classroom.name == data['name'],
                Classroom.id != classroom_id
            ).first()
            if existing:
                return jsonify({'error': 'Bu isimde derslik zaten var'}), 400
            classroom.name = data['name']
        
        if 'building' in data:
            classroom.building = data['building']
        if 'floor' in data:
            classroom.floor = data['floor']
        if 'capacity' in data:
            classroom.capacity = data['capacity']
        if 'is_special' in data:
            classroom.is_special = data['is_special']
        if 'special_type' in data:
            classroom.special_type = data['special_type']
        if 'is_active' in data:
            classroom.is_active = data['is_active']
        
        db.session.commit()
        return jsonify({
            'message': 'Derslik güncellendi',
            'classroom': classroom.to_dict()
        })
    
    if request.method == 'DELETE':
        db.session.delete(classroom)
        db.session.commit()
        return jsonify({'message': 'Derslik silindi'})


# ==================== SPECIAL EXAM REQUEST ENDPOINTS (Bölüm Yetkilisi için) ====================

@app.route('/api/special-requests', methods=['GET', 'POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def manage_special_requests():
    """
    Özel durum sınav talepleri
    
    BÖLÜM YETKİLİSİ:
    - Kendi bölümü için özel durum talebi oluşturabilir
    - Sadece kendi bölümünün taleplerini görebilir
    
    ADMIN:
    - Tüm talepleri görebilir ve işleyebilir
    """
    if request.method == 'GET':
        query = SpecialExamRequest.query
        
        # ✅ Bölüm yetkilisi sadece kendi bölümünün taleplerini görebilir
        if g.current_user.role == 'bolum_yetkilisi':
            query = query.filter_by(department_id=g.current_user.department_id)
        
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        requests = query.order_by(SpecialExamRequest.created_at.desc()).all()
        return jsonify({'requests': [r.to_dict() for r in requests]})
    
    # POST - Yeni talep oluştur
    data = request.get_json()
    
    if not data.get('course_id'):
        return jsonify({'error': 'Ders ID gerekli'}), 400
    
    course = Course.query.get(data['course_id'])
    if not course:
        return jsonify({'error': 'Ders bulunamadı'}), 404
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki dersler için talep oluşturabilir
    if g.current_user.role == 'bolum_yetkilisi':
        if course.department_id != g.current_user.department_id:
            return jsonify({
                'error': 'Sadece kendi bölümünüzdeki dersler için talep oluşturabilirsiniz'
            }), 403
    
    preferred_date = None
    if data.get('preferred_date'):
        preferred_date = datetime.datetime.strptime(data['preferred_date'], '%Y-%m-%d').date()
    
    special_request = SpecialExamRequest(
        course_id=data['course_id'],
        requested_by=g.current_user.id,
        department_id=g.current_user.department_id if g.current_user.role == 'bolum_yetkilisi' else course.department_id,
        request_type=data.get('request_type'),
        reason=data.get('reason'),
        preferred_date=preferred_date,
        preferred_time=data.get('preferred_time'),
        preferred_room_type=data.get('preferred_room_type')
    )
    db.session.add(special_request)
    db.session.commit()
    
    return jsonify({
        'message': 'Özel durum talebi oluşturuldu',
        'request': special_request.to_dict()
    }), 201


@app.route('/api/special-requests/<int:request_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth(['admin', 'bolum_yetkilisi'])
def update_delete_special_request(request_id):
    """Özel durum talebi güncelleme/silme"""
    special_request = SpecialExamRequest.query.get_or_404(request_id)
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümünün taleplerini yönetebilir
    if g.current_user.role == 'bolum_yetkilisi':
        if special_request.department_id != g.current_user.department_id:
            return jsonify({'error': 'Bu talep sizin bölümünüze ait değil'}), 403
    
    if request.method == 'GET':
        return jsonify({'request': special_request.to_dict()})
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Sadece admin talep durumunu değiştirebilir
        if data.get('status') and g.current_user.role == 'admin':
            special_request.status = data['status']
            special_request.processed_at = datetime.datetime.utcnow()
            special_request.processed_by = g.current_user.id
            if data.get('admin_notes'):
                special_request.admin_notes = data['admin_notes']
        
        # Bölüm yetkilisi talebi güncelleyebilir (onaylanmadan önce)
        if g.current_user.role == 'bolum_yetkilisi':
            if special_request.status != 'pending':
                return jsonify({'error': 'İşlenmiş talepler güncellenemez'}), 400
            
            if data.get('reason'):
                special_request.reason = data['reason']
            if data.get('preferred_date'):
                special_request.preferred_date = datetime.datetime.strptime(
                    data['preferred_date'], '%Y-%m-%d'
                ).date()
            if data.get('preferred_time'):
                special_request.preferred_time = data['preferred_time']
            if data.get('preferred_room_type'):
                special_request.preferred_room_type = data['preferred_room_type']
        
        db.session.commit()
        return jsonify({
            'message': 'Talep güncellendi',
            'request': special_request.to_dict()
        })
    
    if request.method == 'DELETE':
        # Bölüm yetkilisi sadece pending talepleri silebilir
        if g.current_user.role == 'bolum_yetkilisi':
            if special_request.status != 'pending':
                return jsonify({'error': 'İşlenmiş talepler silinemez'}), 400
        
        db.session.delete(special_request)
        db.session.commit()
        return jsonify({'message': 'Talep silindi'})


# ==================== EXAM ENDPOINTS ====================

@app.route('/api/exams', methods=['GET', 'POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def manage_exams():
    """Sınav yönetimi"""
    if request.method == 'GET':
        query = Exam.query
        
        # ✅ FIX: Bölüm yetkilisi sadece kendi bölümünün sınavlarını görebilir
        if g.current_user.role == 'bolum_yetkilisi':
            dept_courses = Course.query.filter_by(department_id=g.current_user.department_id).all()
            course_ids = [c.id for c in dept_courses]
            query = query.filter(Exam.course_id.in_(course_ids))
        
        if request.args.get('course_id'):
            query = query.filter_by(course_id=request.args.get('course_id'))
        
        if request.args.get('date'):
            query = query.filter_by(date=request.args.get('date'))
        
        if request.args.get('status'):
            query = query.filter_by(status=request.args.get('status'))
        
        exams = query.all()
        return jsonify({'exams': [e.to_dict() for e in exams]})
    
    # POST - Yeni sınav ekle (genellikle scheduler tarafından yapılır)
    data = request.get_json()
    
    if not data.get('course_id') or not data.get('date'):
        return jsonify({'error': 'Ders ID ve tarih gerekli'}), 400
    
    course = Course.query.get(data['course_id'])
    if not course:
        return jsonify({'error': 'Ders bulunamadı'}), 404
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki dersler için sınav oluşturabilir
    if g.current_user.role == 'bolum_yetkilisi':
        if course.department_id != g.current_user.department_id:
            return jsonify({
                'error': 'Sadece kendi bölümünüzdeki dersler için sınav oluşturabilirsiniz'
            }), 403
    
    exam = Exam(
        course_id=data['course_id'],
        classroom_id=data.get('classroom_id'),
        date=datetime.datetime.strptime(data['date'], '%Y-%m-%d').date(),
        start_time=datetime.datetime.strptime(data['start_time'], '%H:%M').time() if data.get('start_time') else datetime.time(9, 0),
        end_time=datetime.datetime.strptime(data['end_time'], '%H:%M').time() if data.get('end_time') else datetime.time(11, 0),
        duration=data.get('duration', 90),
        exam_type=data.get('exam_type', 'final'),
        requires_special_room=data.get('requires_special_room', course.requires_special_room),
        special_room_type=data.get('special_room_type', course.special_room_type),
        created_by=g.current_user.id
    )
    db.session.add(exam)
    db.session.commit()
    
    return jsonify({
        'message': 'Sınav oluşturuldu',
        'exam': exam.to_dict()
    }), 201


@app.route('/api/exams/<int:exam_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth(['admin', 'bolum_yetkilisi'])
def update_delete_exam(exam_id):
    """Sınav güncelleme/silme"""
    exam = Exam.query.get_or_404(exam_id)
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümünün sınavlarını yönetebilir
    if g.current_user.role == 'bolum_yetkilisi':
        course = Course.query.get(exam.course_id)
        if course and course.department_id != g.current_user.department_id:
            return jsonify({'error': 'Bu sınav sizin bölümünüze ait değil'}), 403
    
    if request.method == 'GET':
        return jsonify({'exam': exam.to_dict()})
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if data.get('classroom_id'):
            exam.classroom_id = data['classroom_id']
        if data.get('date'):
            exam.date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        if data.get('start_time'):
            exam.start_time = datetime.datetime.strptime(data['start_time'], '%H:%M').time()
        if data.get('end_time'):
            exam.end_time = datetime.datetime.strptime(data['end_time'], '%H:%M').time()
        if 'duration' in data:
            exam.duration = data['duration']
        if data.get('exam_type'):
            exam.exam_type = data['exam_type']
        if data.get('status'):
            exam.status = data['status']
        if 'requires_special_room' in data:
            exam.requires_special_room = data['requires_special_room']
        if 'special_room_type' in data:
            exam.special_room_type = data['special_room_type']
        
        db.session.commit()
        return jsonify({
            'message': 'Sınav güncellendi',
            'exam': exam.to_dict()
        })
    
    if request.method == 'DELETE':
        db.session.delete(exam)
        db.session.commit()
        return jsonify({'message': 'Sınav silindi'})


# ==================== EXAM SCHEDULER ====================

@app.route('/api/scheduler/run', methods=['POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def run_scheduler():
    """
    Otomatik sınav programı oluşturma
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - Sadece kendi bölümünün derslerini programlayabilir
    """
    data = request.get_json() or {}
    
    # Tarih aralığı
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    
    if not start_date_str or not end_date_str:
        return jsonify({'error': 'Başlangıç ve bitiş tarihi gerekli'}), 400
    
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Geçersiz tarih formatı. YYYY-MM-DD kullanın'}), 400
    
    # ✅ FIX: Bölüm yetkilisi için department filtresi
    if g.current_user.role == 'bolum_yetkilisi':
        department_id = g.current_user.department_id
        courses = Course.query.filter_by(
            department_id=department_id,
            is_active=True
        ).all()
    else:
        # Admin tüm dersleri veya belirli bir bölümü programlayabilir
        department_id = data.get('department_id')
        if department_id:
            courses = Course.query.filter_by(
                department_id=department_id,
                is_active=True
            ).all()
        else:
            courses = Course.query.filter_by(is_active=True).all()
    
    if not courses:
        return jsonify({'error': 'Programlanacak ders bulunamadı'}), 404
    
    # Derslikleri al
    classrooms = Classroom.query.filter_by(is_active=True).all()
    if not classrooms:
        return jsonify({'error': 'Kullanılabilir derslik bulunamadı'}), 404
    
    # Basit bir scheduling algoritması
    scheduled_exams = []
    unscheduled_courses = []
    
    # Zaman dilimleri (saat cinsinden)
    time_slots = [
        (datetime.time(9, 0), datetime.time(11, 0)),
        (datetime.time(11, 0), datetime.time(13, 0)),
        (datetime.time(14, 0), datetime.time(16, 0)),
        (datetime.time(16, 0), datetime.time(18, 0))
    ]
    
    # Her gün için slot kullanımını takip et
    used_slots = {}  # {(date, time_slot, classroom_id): course_id}
    
    current_date = start_date
    slot_index = 0
    
    for course in courses:
        scheduled = False
        
        # Uygun slot bul
        check_date = start_date
        while check_date <= end_date and not scheduled:
            for slot in time_slots:
                start_time, end_time = slot
                
                # Özel salon gereksinimi kontrolü
                suitable_classrooms = []
                for classroom in classrooms:
                    # Kapasite kontrolü
                    if classroom.capacity < course.student_count:
                        continue
                    
                    # Özel salon kontrolü
                    if course.requires_special_room:
                        if not classroom.is_special:
                            continue
                        if course.special_room_type and classroom.special_type != course.special_room_type:
                            continue
                    
                    # Slot müsait mi?
                    slot_key = (check_date, slot, classroom.id)
                    if slot_key not in used_slots:
                        suitable_classrooms.append(classroom)
                
                if suitable_classrooms:
                    # İlk uygun sınıfı seç
                    selected_classroom = suitable_classrooms[0]
                    slot_key = (check_date, slot, selected_classroom.id)
                    used_slots[slot_key] = course.id
                    
                    # Sınav oluştur
                    exam = Exam(
                        course_id=course.id,
                        classroom_id=selected_classroom.id,
                        date=check_date,
                        start_time=start_time,
                        end_time=end_time,
                        duration=120,
                        exam_type=data.get('exam_type', 'final'),
                        requires_special_room=course.requires_special_room,
                        special_room_type=course.special_room_type,
                        created_by=g.current_user.id
                    )
                    db.session.add(exam)
                    scheduled_exams.append({
                        'course_code': course.code,
                        'course_name': course.name,
                        'date': check_date.isoformat(),
                        'time': f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}",
                        'classroom': selected_classroom.name
                    })
                    scheduled = True
                    break
            
            check_date += datetime.timedelta(days=1)
        
        if not scheduled:
            unscheduled_courses.append({
                'course_code': course.code,
                'course_name': course.name,
                'reason': 'Uygun slot bulunamadı'
            })
    
    db.session.commit()
    
    return jsonify({
        'message': f'{len(scheduled_exams)} sınav programlandı',
        'scheduled': scheduled_exams,
        'unscheduled': unscheduled_courses,
        'total_courses': len(courses),
        'scheduled_count': len(scheduled_exams),
        'unscheduled_count': len(unscheduled_courses)
    })


# ==================== EXCEL IMPORT ENDPOINTS ====================

@app.route('/api/import/classlists', methods=['POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def import_classlists():
    """
    Sınıf listelerini Excel'den içe aktar
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - İçe aktarılan dersler otomatik olarak kendi bölümüne atanır
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gerekli'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Sadece Excel dosyaları (.xlsx, .xls) kabul edilir'}), 400
    
    # Geçici dosya oluştur
    temp_dir = tempfile.mkdtemp()
    try:
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)
        
        processor = ExcelProcessor()
        df, error = processor.read_excel_file(filepath)
        
        if error:
            return jsonify({'error': error}), 400
        
        course_code = processor.extract_course_code_from_filename(file.filename)
        students, error = processor.extract_student_data(df)
        
        if error:
            return jsonify({'error': error}), 400
        
        # ✅ FIX: Bölüm yetkilisi için department_id
        if g.current_user.role == 'bolum_yetkilisi':
            department_id = g.current_user.department_id
        else:
            department_id = request.form.get('department_id')
        
        # Ders bul veya oluştur
        course = None
        if course_code:
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                course = Course(
                    code=course_code,
                    name=course_code,
                    department_id=department_id  # ✅ FIX: Bölüm ID eklendi
                )
                db.session.add(course)
                db.session.flush()
        
        created_students = 0
        created_enrollments = 0
        
        for s in students:
            student = Student.query.filter_by(student_number=s['number']).first()
            if not student:
                student = Student(
                    student_number=s['number'],
                    name=s.get('name', ''),
                    department_id=department_id  # ✅ FIX: Bölüm ID eklendi
                )
                db.session.add(student)
                db.session.flush()
                created_students += 1
            
            if course:
                existing = Enrollment.query.filter_by(
                    student_id=student.id,
                    course_id=course.id
                ).first()
                
                if not existing:
                    enrollment = Enrollment(
                        student_id=student.id,
                        course_id=course.id
                    )
                    db.session.add(enrollment)
                    created_enrollments += 1
        
        if course:
            course.student_count = Enrollment.query.filter_by(course_id=course.id).count()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Sınıf listesi içe aktarıldı',
            'course_code': course_code,
            'students_created': created_students,
            'enrollments_created': created_enrollments,
            'total_students': len(students)
        })
    
    finally:
        shutil.rmtree(temp_dir)


@app.route('/api/import/teachers', methods=['POST'])
@require_auth(['admin', 'bolum_yetkilisi'])
def import_teachers():
    """
    Öğretim üyelerini Excel'den içe aktar
    
    BÖLÜM YETKİLİSİ KISITLAMALARI:
    - İçe aktarılan öğretim üyeleri otomatik olarak kendi bölümüne atanır
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gerekli'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Sadece Excel dosyaları kabul edilir'}), 400
    
    # ✅ FIX: Bölüm yetkilisi için department_id
    if g.current_user.role == 'bolum_yetkilisi':
        department_id = g.current_user.department_id
    else:
        department_id = request.form.get('department_id')
    
    temp_dir = tempfile.mkdtemp()
    try:
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)
        
        processor = ExcelProcessor()
        df, error = processor.read_excel_file(filepath)
        
        if error:
            return jsonify({'error': error}), 400
        
        df.columns = [col.lower().strip() for col in df.columns]
        
        # Sütunları bul
        title_col = None
        name_col = None
        
        for col in df.columns:
            if 'unvan' in col or 'title' in col:
                title_col = col
            elif 'ad' in col or 'name' in col or 'isim' in col:
                name_col = col
        
        if not name_col:
            return jsonify({'error': 'Ad/isim sütunu bulunamadı'}), 400
        
        created = 0
        updated = 0
        errors = []
        
        for _, row in df.iterrows():
            try:
                name = str(row[name_col]).strip()
                if not name or name == 'nan':
                    continue
                
                title = None
                if title_col and row.get(title_col):
                    title = str(row[title_col]).strip()
                    if title == 'nan':
                        title = None
                
                full_name = f"{title} {name}" if title else name
                
                teacher = Teacher.query.filter_by(name=full_name).first()
                
                if not teacher:
                    teacher = Teacher(
                        name=full_name,
                        department_id=department_id  # ✅ FIX: Bölüm ID eklendi
                    )
                    db.session.add(teacher)
                    created += 1
                else:
                    updated += 1
                
                if title:
                    teacher.title = title
                
            except Exception as e:
                errors.append(str(e))
        
        db.session.commit()
        
        return jsonify({
            'message': 'Öğretim üyeleri içe aktarıldı',
            'created': created,
            'updated': updated,
            'errors': errors
        })
    
    finally:
        shutil.rmtree(temp_dir)


@app.route('/api/import/proximity', methods=['POST'])
@require_auth(['admin'])
def import_proximity():
    """Derslik yakınlık verilerini içe aktar (sadece admin)"""
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gerekli'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    temp_dir = tempfile.mkdtemp()
    try:
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)
        
        result = import_proximity_to_db(filepath, db, Classroom, ClassroomProximity)
        return jsonify(result)
    
    finally:
        shutil.rmtree(temp_dir)


@app.route('/api/import/capacity', methods=['POST'])
@require_auth(['admin'])
def import_capacity():
    """Derslik/ders kapasite verilerini içe aktar (sadece admin)"""
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gerekli'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    temp_dir = tempfile.mkdtemp()
    try:
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)
        
        result = import_capacity_to_db(filepath, db, Classroom, Course)
        return jsonify(result)
    
    finally:
        shutil.rmtree(temp_dir)


# ==================== STUDENT ENDPOINTS ====================

@app.route('/api/students', methods=['GET'])
@require_auth(['admin', 'bolum_yetkilisi'])
def get_students():
    """Öğrenci listesi"""
    query = Student.query
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümündeki öğrencileri görebilir
    if g.current_user.role == 'bolum_yetkilisi':
        query = query.filter_by(department_id=g.current_user.department_id)
    elif request.args.get('department_id'):
        query = query.filter_by(department_id=request.args.get('department_id'))
    
    students = query.all()
    return jsonify({'students': [s.to_dict() for s in students]})


@app.route('/api/students/<int:student_id>/exams', methods=['GET'])
@require_auth(['admin', 'bolum_yetkilisi', 'hoca', 'ogrenci'])
def get_student_exams(student_id):
    """Öğrencinin sınav programı"""
    student = Student.query.get_or_404(student_id)
    
    # Öğrenci sadece kendi sınavlarını görebilir
    if g.current_user.role == 'ogrenci':
        user_student = Student.query.filter_by(
            student_number=g.current_user.username
        ).first()
        if not user_student or user_student.id != student_id:
            return jsonify({'error': 'Sadece kendi sınav programınızı görebilirsiniz'}), 403
    
    # Öğrencinin kayıtlı olduğu dersler
    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    course_ids = [e.course_id for e in enrollments]
    
    # Bu derslerin sınavları
    exams = Exam.query.filter(Exam.course_id.in_(course_ids)).all()
    
    return jsonify({
        'student': student.to_dict(),
        'exams': [e.to_dict() for e in exams]
    })


# ==================== REPORT ENDPOINTS ====================

@app.route('/api/reports/department-summary', methods=['GET'])
@require_auth(['admin', 'bolum_yetkilisi'])
def department_summary():
    """Bölüm özet raporu"""
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümünün raporunu görebilir
    if g.current_user.role == 'bolum_yetkilisi':
        department_id = g.current_user.department_id
    else:
        department_id = request.args.get('department_id')
    
    if not department_id:
        return jsonify({'error': 'Bölüm ID gerekli'}), 400
    
    department = Department.query.get_or_404(department_id)
    
    courses = Course.query.filter_by(department_id=department_id).all()
    teachers = Teacher.query.filter_by(department_id=department_id).all()
    
    course_ids = [c.id for c in courses]
    exams = Exam.query.filter(Exam.course_id.in_(course_ids)).all()
    
    return jsonify({
        'department': department.to_dict(),
        'statistics': {
            'total_courses': len(courses),
            'total_teachers': len(teachers),
            'total_exams': len(exams),
            'scheduled_exams': len([e for e in exams if e.status == 'scheduled']),
            'completed_exams': len([e for e in exams if e.status == 'completed'])
        },
        'courses': [c.to_dict() for c in courses],
        'teachers': [t.to_dict() for t in teachers]
    })


@app.route('/api/reports/exam-schedule', methods=['GET'])
@require_auth(['admin', 'bolum_yetkilisi', 'hoca', 'ogrenci'])
def exam_schedule_report():
    """Sınav programı raporu"""
    query = Exam.query.filter_by(status='scheduled')
    
    # ✅ FIX: Bölüm yetkilisi sadece kendi bölümünün programını görebilir
    if g.current_user.role == 'bolum_yetkilisi':
        dept_courses = Course.query.filter_by(department_id=g.current_user.department_id).all()
        course_ids = [c.id for c in dept_courses]
        query = query.filter(Exam.course_id.in_(course_ids))
    
    if request.args.get('start_date'):
        start_date = datetime.datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
        query = query.filter(Exam.date >= start_date)
    
    if request.args.get('end_date'):
        end_date = datetime.datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
        query = query.filter(Exam.date <= end_date)
    
    exams = query.order_by(Exam.date, Exam.start_time).all()
    
    return jsonify({
        'exams': [e.to_dict() for e in exams],
        'total': len(exams)
    })


# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Sağlık kontrolü endpoint'i"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Kaynak bulunamadı'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Sunucu hatası'}), 500


@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Geçersiz istek'}), 400


# ==================== CLI COMMANDS ====================

@app.cli.command('init-db')
def init_db():
    """Veritabanını oluştur"""
    db.create_all()
    print('Veritabanı tabloları oluşturuldu.')


@app.cli.command('create-admin')
def create_admin():
    """Varsayılan admin kullanıcısı oluştur"""
    if User.query.filter_by(username='admin').first():
        print('Admin kullanıcısı zaten var.')
        return
    
    admin = User(
        username='admin',
        email='admin@kostu.edu.tr',
        name='Sistem Yöneticisi',
        role='admin'
    )
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()
    print('Admin kullanıcısı oluşturuldu. Kullanıcı adı: admin, Şifre: admin123')


@app.cli.command('seed-data')
def seed_data():
    """Test verileri ekle"""
    # Fakülte
    faculty = Faculty.query.filter_by(code='MF').first()
    if not faculty:
        faculty = Faculty(name='Mühendislik Fakültesi', code='MF')
        db.session.add(faculty)
        db.session.flush()
    
    # Bölüm
    dept = Department.query.filter_by(code='BLM').first()
    if not dept:
        dept = Department(name='Bilgisayar Mühendisliği', code='BLM', faculty_id=faculty.id)
        db.session.add(dept)
        db.session.flush()
    
    # Bölüm Yetkilisi
    bolum_yetkili = User.query.filter_by(username='bolum_yetkilisi').first()
    if not bolum_yetkili:
        bolum_yetkili = User(
            username='bolum_yetkilisi',
            email='bolum@kostu.edu.tr',
            name='Bölüm Başkanı',
            role='bolum_yetkilisi',
            department_id=dept.id
        )
        bolum_yetkili.set_password('bolum123')
        db.session.add(bolum_yetkili)
    
    # Öğretim üyesi
    teacher = Teacher.query.filter_by(email='hoca@kostu.edu.tr').first()
    if not teacher:
        teacher = Teacher(
            name='Prof. Dr. Ahmet Yılmaz',
            title='Prof. Dr.',
            email='hoca@kostu.edu.tr',
            department_id=dept.id
        )
        db.session.add(teacher)
        db.session.flush()
    
    # Ders
    course = Course.query.filter_by(code='BLM101').first()
    if not course:
        course = Course(
            code='BLM101',
            name='Programlamaya Giriş',
            credit=4,
            student_count=80,
            department_id=dept.id,
            teacher_id=teacher.id,
            semester='2024-Güz'
        )
        db.session.add(course)
    
    # Derslik
    classroom = Classroom.query.filter_by(name='A101').first()
    if not classroom:
        classroom = Classroom(
            name='A101',
            building='A Blok',
            floor=1,
            capacity=100
        )
        db.session.add(classroom)
    
    db.session.commit()
    print('Test verileri eklendi.')


# ==================== MAIN ====================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
