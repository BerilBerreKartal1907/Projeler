## Geliştirilmiş Üniversite Sınav Programı Hazırlama Sistemi

Bu klasör, Python + SQLite + Tkinter ile geliştirilecek sınav planlama sisteminin **temiz mimarili** proje iskeletidir.

### Katmanlar
- `db/`: SQLite şeması ve bağlantı/kurulum kodları
- `models/`: Sistem varlıkları (OOP class'lar)
- `repositories/`: Veritabanı erişim katmanı (CRUD) (sonraki adım)
- `services/`: İş kuralları ve planlama servisi (sonraki adım)
- `ui/`: Tkinter arayüz (sonraki adım)
- `data_loader/`: CSV/TXT okuma ve DB'ye import (programatik)
- `scripts/`: Örnek CLI script'leri

### Çalıştırma (şimdilik)
Bu adımda sadece veritabanı ve class yapıları bulunmaktadır. Planlama algoritması ve UI sonraki adımlarda eklenecektir.

### Dosyadan veri import (CSV/TXT)
Elle SQLite importu yapılmaz; uygulama çalışırken Python ile okunup DB'ye yazılır.

Örnek:
```bash
python -m university_exam_scheduler.scripts.import_data --init-db \
  --class-list "/path/to/MAT101.csv" \
  --class-list "/path/to/FIZ102.csv" \
  --proximity "/path/to/derslik_mesafe.csv"
```

