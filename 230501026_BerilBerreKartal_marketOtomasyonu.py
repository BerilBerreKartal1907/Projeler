from datetime import datetime
class Market:
    def __init__(self):
        self.fiyat_listesi = {}
        self.csv_fiyatlari_yukle("fiyatlar.csv")
        self.fisler = []
        self.fis_no = 0

    def csv_fiyatlari_yukle(self, dosya_yolu):
        with open(dosya_yolu, "r") as f:
            for line in f:
                urun, fiyat = line.strip().split(",")
                self.fiyat_listesi[urun.lower()] = float(fiyat)

    def birim_fiyat(self, urun):
        return self.fiyat_listesi.get(urun.lower())

    def satis_yap(self):
        self.fis_no += 1
        yeni_fis = Fis(self.fis_no, datetime.now(), self.fiyat_listesi)
        while True:
            urun_adi = input("Ürün adı: ").lower()
            if urun_adi == "q":
                break
            if urun_adi not in self.fiyat_listesi:
                print("Üzgünüz, bu ürün mağazamızda bulunmamaktadır.")
                continue
            yeni_fis += Urun(urun_adi, self.fiyat_listesi[urun_adi], "10.10.2020")

        self.fisler.append(yeni_fis)
        return yeni_fis

    def __str__(self):
        return str(self.fiyat_listesi)


class Urun:
    def __init__(self, ad, fiyat, uretim_tarihi):
        self.ad = ad
        self.fiyat = fiyat
        self.uretim_tarihi = uretim_tarihi

    def __str__(self):
        return f"{self.ad.capitalize()} {self.fiyat} TL"


class Fis:
    def __init__(self, fis_no, tarih, fiyat_listesi):
        self.urunler = {}
        self.fis_no = fis_no
        self.tarih = tarih
        self.fiyat_listesi = fiyat_listesi  # Fiyat listesini Fis sınıfına ekleyin

    def toplam(self):
        return sum([u.fiyat * adet for u, adet in self.urunler.items()])

    def __iadd__(self, urun):  # fis += urun
        if urun.ad in self.urunler:
            self.urunler[urun.ad] += 1
        else:
            self.urunler[urun.ad] = 1
        return self

    def __str__(self):
        s = "Fis No: " + str(self.fis_no) + "\n"
        s += "Tarih: " + str(self.tarih) + "\n"
        for urun_ad, adet in self.urunler.items():
            birim_fiyat = self.fiyat_listesi[urun_ad]  # Değişiklik burada
            s += f"{adet} x {urun_ad} {adet * birim_fiyat} TL\n"
        s += "Toplam Tutar: " + str(self.toplam()) + " TL"
        return s

m = Market()

for i in range(3):
    m.satis_yap()

for fis in m.fisler:
    print(fis)
    print()
