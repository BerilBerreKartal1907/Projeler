from datetime import datetime
import csv


class Market:
    def __init__(self, fiyat_dosya_yolu):
        self.fiyat_listesi = self._csv_fiyatlari_yukle(fiyat_dosya_yolu)
        self.fisler = []
        self.fis_no = 0

    def _csv_fiyatlari_yukle(self, dosya_yolu):
        fiyatlar = {}
        try:
            with open(dosya_yolu, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for urun, fiyat in reader:
                    fiyatlar[urun.lower()] = float(fiyat)
        except FileNotFoundError:
            print("Fiyat dosyası bulunamadı.")
        return fiyatlar

    def yeni_satis(self, urunler):
        """
        urunler: ['elma', 'elma', 'sut']
        """
        self.fis_no += 1
        fis = Fis(self.fis_no, datetime.now())

        for urun_adi in urunler:
            if urun_adi not in self.fiyat_listesi:
                continue
            fis.urun_ekle(urun_adi, self.fiyat_listesi[urun_adi])

        self.fisler.append(fis)
        return fis


class Fis:
    def __init__(self, fis_no, tarih):
        self.fis_no = fis_no
        self.tarih = tarih
        self.urunler = {}  # urun_adı -> [adet, birim_fiyat]

    def urun_ekle(self, urun_adi, fiyat):
        if urun_adi in self.urunler:
            self.urunler[urun_adi][0] += 1
        else:
            self.urunler[urun_adi] = [1, fiyat]

    def toplam_tutar(self):
        return sum(adet * fiyat for adet, fiyat in self.urunler.values())

    def __str__(self):
        s = f"Fis No: {self.fis_no}\n"
        s += f"Tarih: {self.tarih}\n"
        for urun, (adet, fiyat) in self.urunler.items():
            s += f"{adet} x {urun.capitalize()} = {adet * fiyat:.2f} TL\n"
        s += f"Toplam: {self.toplam_tutar():.2f} TL"
        return s


# --- Örnek Kullanım ---
market = Market("fiyatlar.csv")

market.yeni_satis(["elma", "elma", "sut"])
market.yeni_satis(["ekmek", "sut"])

for fis in market.fisler:
    print(fis)
    print()

