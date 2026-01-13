"""
Excel İşleme Modülü
KOSTÜ Sınav Programı Yönetim Sistemi
"""

import os
import re
import pandas as pd
from pathlib import Path


class ExcelProcessor:
    """Excel dosyalarını işleyen yardımcı sınıf"""
    
    # Olası öğrenci numarası sütun isimleri
    STUDENT_NUMBER_COLUMNS = [
        'ogrenci_no', 'ogrenci no', 'öğrenci no', 'öğrenci_no',
        'student_number', 'student number', 'studentnumber',
        'no', 'numara', 'ogr_no', 'öğr_no', 'ogrno', 'öğrno',
        'ogrenci', 'öğrenci', 'number', 'sicil', 'sicil_no'
    ]
    
    # Olası isim sütun isimleri
    NAME_COLUMNS = [
        'ad', 'isim', 'name', 'ad_soyad', 'ad soyad', 'adsoyad',
        'full_name', 'fullname', 'student_name', 'ogrenci_adi',
        'öğrenci_adı', 'öğrenci adı', 'ad-soyad'
    ]
    
    def __init__(self):
        pass
    
    def read_excel_file(self, filepath):
        """
        Excel dosyasını oku
        Returns: (DataFrame, error_message)
        """
        try:
            # Önce xlsx olarak dene
            try:
                df = pd.read_excel(filepath, engine='openpyxl')
            except Exception:
                # Eski xls formatı için xlrd dene
                df = pd.read_excel(filepath, engine='xlrd')
            
            if df.empty:
                return None, "Dosya boş"
            
            return df, None
            
        except Exception as e:
            return None, f"Dosya okuma hatası: {str(e)}"
    
    def extract_course_code_from_filename(self, filename):
        """
        Dosya adından ders kodunu çıkar
        Örnek: "YZM332_ogrenci_listesi.xlsx" -> "YZM332"
        """
        # Yaygın ders kodu pattern'leri
        patterns = [
            r'([A-ZÇĞİÖŞÜ]{2,4}\d{3})',  # YZM332, BLM111
            r'([A-ZÇĞİÖŞÜ]{2,4}\s*\d{3})',  # YZM 332
            r'([A-ZÇĞİÖŞÜ]{2,4}-\d{3})',  # YZM-332
        ]
        
        basename = os.path.splitext(filename)[0].upper()
        
        for pattern in patterns:
            match = re.search(pattern, basename)
            if match:
                code = match.group(1).replace(' ', '').replace('-', '')
                return code
        
        return None
    
    def find_student_number_column(self, df):
        """DataFrame'de öğrenci numarası sütununu bul"""
        columns_lower = {col.lower().strip(): col for col in df.columns}
        
        for candidate in self.STUDENT_NUMBER_COLUMNS:
            if candidate in columns_lower:
                return columns_lower[candidate]
        
        # İlk sütun sayısal ise onu kullan
        first_col = df.columns[0]
        if df[first_col].dtype in ['int64', 'float64']:
            return first_col
        
        # İlk sütundaki değerler sayısal string ise
        try:
            sample = str(df[first_col].iloc[0])
            if sample.isdigit() and len(sample) >= 6:
                return first_col
        except Exception:
            pass
        
        return None
    
    def find_name_column(self, df):
        """DataFrame'de isim sütununu bul"""
        columns_lower = {col.lower().strip(): col for col in df.columns}
        
        for candidate in self.NAME_COLUMNS:
            if candidate in columns_lower:
                return columns_lower[candidate]
        
        return None
    
    def extract_student_data(self, df):
        """
        DataFrame'den öğrenci verilerini çıkar
        Returns: (list of dicts, error_message)
        """
        number_col = self.find_student_number_column(df)
        if not number_col:
            return None, "Öğrenci numarası sütunu bulunamadı"
        
        name_col = self.find_name_column(df)
        
        students = []
        for _, row in df.iterrows():
            try:
                number = str(row[number_col]).strip()
                # Sayısal olmayan veya boş değerleri atla
                if not number or number == 'nan' or not any(c.isdigit() for c in number):
                    continue
                
                # Float'ları int'e çevir (20200001.0 -> 20200001)
                try:
                    number = str(int(float(number)))
                except (ValueError, TypeError):
                    pass
                
                student = {'number': number}
                
                if name_col:
                    name = str(row[name_col]).strip()
                    if name and name != 'nan':
                        student['name'] = name
                
                students.append(student)
                
            except Exception:
                continue
        
        if not students:
            return None, "Dosyada geçerli öğrenci verisi bulunamadı"
        
        return students, None


def batch_process_folder(folder_path):
    """
    Klasördeki tüm Excel dosyalarını işle
    Returns: dict with results
    """
    processor = ExcelProcessor()
    folder = Path(folder_path)
    
    results = {
        'files_processed': 0,
        'total_students': 0,
        'courses': {},
        'errors': []
    }
    
    excel_files = list(folder.glob('*.xlsx')) + list(folder.glob('*.xls'))
    
    for filepath in excel_files:
        filename = filepath.name
        course_code = processor.extract_course_code_from_filename(filename)
        
        df, error = processor.read_excel_file(str(filepath))
        if error:
            results['errors'].append({'file': filename, 'error': error})
            continue
        
        students, error = processor.extract_student_data(df)
        if error:
            results['errors'].append({'file': filename, 'error': error})
            continue
        
        results['files_processed'] += 1
        results['total_students'] += len(students)
        
        if course_code:
            results['courses'][course_code] = {
                'file': filename,
                'student_count': len(students),
                'students': students
            }
    
    return results


def import_classlists_to_db(folder_path, db, Student, Course, Enrollment):
    """
    Klasördeki sınıf listelerini veritabanına aktar
    """
    processor = ExcelProcessor()
    folder = Path(folder_path)
    
    results = {
        'files_processed': 0,
        'students_created': 0,
        'enrollments_created': 0,
        'courses_created': 0,
        'errors': []
    }
    
    excel_files = list(folder.glob('*.xlsx')) + list(folder.glob('*.xls'))
    
    for filepath in excel_files:
        filename = filepath.name
        course_code = processor.extract_course_code_from_filename(filename)
        
        df, error = processor.read_excel_file(str(filepath))
        if error:
            results['errors'].append({'file': filename, 'error': error})
            continue
        
        students, error = processor.extract_student_data(df)
        if error:
            results['errors'].append({'file': filename, 'error': error})
            continue
        
        # Ders oluştur veya bul
        course = None
        if course_code:
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                course = Course(code=course_code, name=course_code)
                db.session.add(course)
                db.session.flush()
                results['courses_created'] += 1
        
        for s in students:
            # Öğrenci oluştur veya bul
            student = Student.query.filter_by(student_number=s['number']).first()
            if not student:
                student = Student(
                    student_number=s['number'],
                    name=s.get('name', '')
                )
                db.session.add(student)
                db.session.flush()
                results['students_created'] += 1
            
            # Kayıt oluştur
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
                    results['enrollments_created'] += 1
        
        # Ders öğrenci sayısını güncelle
        if course:
            course.student_count = Enrollment.query.filter_by(course_id=course.id).count()
        
        db.session.commit()
        results['files_processed'] += 1
    
    return results


def import_proximity_to_db(filepath, db, Classroom, ClassroomProximity):
    """
    Derslik yakınlık Excel dosyasını veritabanına aktar
    
    Beklenen format:
    | Derslik | Yakın Derslikler | Mesafe | Bitişik |
    | A101    | A102, A103       | 5      | Evet    |
    """
    processor = ExcelProcessor()
    
    df, error = processor.read_excel_file(filepath)
    if error:
        return {'status': 'error', 'message': error}
    
    # Sütun isimlerini normalize et
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Gerekli sütunları bul
    primary_col = None
    nearby_col = None
    distance_col = None
    adjacent_col = None
    
    for col in df.columns:
        if 'derslik' in col and 'yakın' not in col:
            primary_col = col
        elif 'yakın' in col:
            nearby_col = col
        elif 'mesafe' in col or 'distance' in col:
            distance_col = col
        elif 'bitişik' in col or 'adjacent' in col:
            adjacent_col = col
    
    if not primary_col or not nearby_col:
        return {
            'status': 'error',
            'message': 'Gerekli sütunlar bulunamadı (Derslik, Yakın Derslikler)'
        }
    
    created = 0
    errors = []
    
    for _, row in df.iterrows():
        try:
            primary_name = str(row[primary_col]).strip()
            nearby_names = str(row[nearby_col]).strip()
            
            if not primary_name or primary_name == 'nan':
                continue
            
            # Ana dersliği bul veya oluştur
            primary_room = Classroom.query.filter_by(name=primary_name).first()
            if not primary_room:
                primary_room = Classroom(name=primary_name, capacity=30)
                db.session.add(primary_room)
                db.session.flush()
            
            # Yakın derslikleri işle
            if nearby_names and nearby_names != 'nan':
                nearby_list = [n.strip() for n in nearby_names.split(',') if n.strip()]
                
                for nearby_name in nearby_list:
                    nearby_room = Classroom.query.filter_by(name=nearby_name).first()
                    if not nearby_room:
                        nearby_room = Classroom(name=nearby_name, capacity=30)
                        db.session.add(nearby_room)
                        db.session.flush()
                    
                    # Yakınlık kaydı oluştur
                    existing = ClassroomProximity.query.filter_by(
                        primary_classroom_id=primary_room.id,
                        nearby_classroom_id=nearby_room.id
                    ).first()
                    
                    if not existing:
                        distance = None
                        if distance_col and row.get(distance_col):
                            try:
                                distance = float(row[distance_col])
                            except (ValueError, TypeError):
                                pass
                        
                        is_adjacent = False
                        if adjacent_col and row.get(adjacent_col):
                            adj_val = str(row[adjacent_col]).lower()
                            is_adjacent = adj_val in ['evet', 'yes', 'true', '1']
                        
                        proximity = ClassroomProximity(
                            primary_classroom_id=primary_room.id,
                            nearby_classroom_id=nearby_room.id,
                            distance=distance,
                            is_adjacent=is_adjacent
                        )
                        db.session.add(proximity)
                        created += 1
        
        except Exception as e:
            errors.append(str(e))
            continue
    
    db.session.commit()
    
    return {
        'status': 'success',
        'created': created,
        'errors': errors
    }


def import_capacity_to_db(filepath, db, Classroom, Course):
    """
    Kapasite Excel dosyasını veritabanına aktar
    
    Beklenen format:
    | Derslik | Kapasite | Özel Tip |
    | A101    | 120      | normal   |
    
    veya
    
    | Ders Kodu | Öğrenci Sayısı |
    | YZM332    | 110            |
    """
    processor = ExcelProcessor()
    
    df, error = processor.read_excel_file(filepath)
    if error:
        return {'status': 'error', 'message': error}
    
    df.columns = [col.lower().strip() for col in df.columns]
    
    results = {
        'classrooms_updated': 0,
        'courses_updated': 0,
        'errors': []
    }
    
    # Derslik kapasitesi mi?
    classroom_col = None
    capacity_col = None
    special_col = None
    
    for col in df.columns:
        if 'derslik' in col or 'room' in col or 'sınıf' in col:
            classroom_col = col
        elif 'kapasite' in col or 'capacity' in col:
            capacity_col = col
        elif 'özel' in col or 'special' in col or 'tip' in col or 'type' in col:
            special_col = col
    
    if classroom_col and capacity_col:
        for _, row in df.iterrows():
            try:
                name = str(row[classroom_col]).strip()
                capacity = int(float(row[capacity_col]))
                
                if not name or name == 'nan':
                    continue
                
                classroom = Classroom.query.filter_by(name=name).first()
                if classroom:
                    classroom.capacity = capacity
                    if special_col and row.get(special_col):
                        special_type = str(row[special_col]).strip().lower()
                        if special_type and special_type != 'nan' and special_type != 'normal':
                            classroom.is_special = True
                            classroom.special_type = special_type
                else:
                    is_special = False
                    special_type = None
                    if special_col and row.get(special_col):
                        st = str(row[special_col]).strip().lower()
                        if st and st != 'nan' and st != 'normal':
                            is_special = True
                            special_type = st
                    
                    classroom = Classroom(
                        name=name,
                        capacity=capacity,
                        is_special=is_special,
                        special_type=special_type
                    )
                    db.session.add(classroom)
                
                results['classrooms_updated'] += 1
                
            except Exception as e:
                results['errors'].append(str(e))
        
        db.session.commit()
        return {'status': 'success', **results}
    
    # Ders öğrenci sayısı mı?
    course_col = None
    student_count_col = None
    
    for col in df.columns:
        if 'ders' in col or 'course' in col or 'kod' in col or 'code' in col:
            course_col = col
        elif 'öğrenci' in col or 'student' in col or 'sayı' in col or 'count' in col:
            student_count_col = col
    
    if course_col and student_count_col:
        for _, row in df.iterrows():
            try:
                code = str(row[course_col]).strip().upper()
                count = int(float(row[student_count_col]))
                
                if not code or code == 'NAN':
                    continue
                
                course = Course.query.filter_by(code=code).first()
                if course:
                    course.student_count = count
                    results['courses_updated'] += 1
                
            except Exception as e:
                results['errors'].append(str(e))
        
        db.session.commit()
        return {'status': 'success', **results}
    
    return {
        'status': 'error',
        'message': 'Tanınmayan dosya formatı. Derslik veya ders kapasitesi sütunları bulunamadı.'
    }


def import_teachers_from_excel(filepath, db):
    """
    akademik_kadro.xlsx dosyasından öğretim üyelerini içe aktar
    
    Beklenen format:
    | Unvan | Ad Soyad | Fakülte/Bölüm |
    | Prof. Dr. | Ahmet Yılmaz | Mühendislik Fakültesi / Bilgisayar Mühendisliği |
    """
    # İçe aktarma için modelleri dinamik olarak al
    from flask import current_app
    
    processor = ExcelProcessor()
    
    df, error = processor.read_excel_file(filepath)
    if error:
        return {'status': 'error', 'message': error}
    
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Sütunları bul
    title_col = None
    name_col = None
    faculty_col = None
    
    for col in df.columns:
        if 'unvan' in col or 'title' in col:
            title_col = col
        elif 'ad' in col or 'name' in col or 'isim' in col:
            name_col = col
        elif 'fakülte' in col or 'bölüm' in col or 'faculty' in col or 'department' in col:
            faculty_col = col
    
    if not name_col:
        return {'status': 'error', 'message': 'Ad/isim sütunu bulunamadı'}
    
    # Teacher modelini import et
    from __main__ import Teacher, Faculty, Department
    
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
            
            faculty_dept = None
            if faculty_col and row.get(faculty_col):
                faculty_dept = str(row[faculty_col]).strip()
                if faculty_dept == 'nan':
                    faculty_dept = None
            
            # Tam ismi oluştur
            full_name = f"{title} {name}" if title else name
            
            # Mevcut öğretmeni bul veya oluştur
            teacher = Teacher.query.filter_by(name=full_name).first()
            
            if not teacher:
                teacher = Teacher(name=full_name)
                db.session.add(teacher)
                created += 1
            else:
                updated += 1
            
            if title:
                teacher.title = title
            
            if faculty_dept:
                teacher.faculty = faculty_dept
            
        except Exception as e:
            errors.append(str(e))
    
    db.session.commit()
    
    return {
        'status': 'success',
        'created': created,
        'updated': updated,
        'errors': errors
    }
