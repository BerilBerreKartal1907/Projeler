import math
class GunesPaneli:
    def __init__(self, guc_kapasitesi, genislik, yukseklik, verimlilik, maliyet):
        self.guc_kapasitesi = guc_kapasitesi
        self.genislik = genislik
        self.yukseklik = yukseklik
        self.verimlilik = verimlilik
        self.maliyet = maliyet
class Ev:
    def __init__(self, genislik, uzunluk, enlem, boylam):
        self.genislik = genislik
        self.uzunluk = uzunluk
        self.enlem = enlem
        self.boylam = boylam


class GunesEnerjisiSistemi:
    def __init__(self, ev, panel):
        self.ev = ev
        self.panel = panel

    def egim_acisini_hesapla(self):
        return self.ev.enlem * 0.9 - 23.5

    def cati_alani_hesapla(self):
        egim_acisi = self.egim_acisini_hesapla()
        kisa_kenar = min(self.ev.genislik, self.ev.uzunluk)
        uzun_kenar = kisa_kenar * math.cos(math.radians(egim_acisi))
        return kisa_kenar * uzun_kenar

    def panel_sayisini_hesapla(self):
        panel_genislik = self.panel.genislik + 20
        panel_yukseklik = self.panel.yukseklik + 20
        cati_alani = self.cati_alani_hesapla()
        panel_alani = panel_genislik * panel_yukseklik
        return math.floor(cati_alani / panel_alani)

    def toplam_maliyeti_hesapla(self):
        panel_sayisi = self.panel_sayisini_hesapla()
        return panel_sayisi * self.panel.maliyet

    def toplam_gucu_hesapla(self):
        panel_sayisi = self.panel_sayisini_hesapla()
        return panel_sayisi * self.panel.guc_kapasitesi

panel1 = GunesPaneli(200, 600, 1500, 0.7, 150)
panel2 = GunesPaneli(300, 800, 2000, 0.8, 250)

ev1 = Ev(6000, 7000,40,30)
ev2 = Ev(8000, 9000, 35, 32)
ev3 = Ev(10000, 12000,50, 10)
ev4 = Ev(15000, 16000, 25, 45)

sistem1 = GunesEnerjisiSistemi(ev1, panel1)
sistem2 = GunesEnerjisiSistemi(ev2, panel1)
sistem3 = GunesEnerjisiSistemi(ev3, panel2)
sistem4 = GunesEnerjisiSistemi(ev4, panel2)

for i, sistem in enumerate([sistem1, sistem2, sistem3, sistem4], 1):
    print(f"Sistem {i}:")
    print(f"  Eğimi Açısı: {sistem.egim_acisini_hesapla():.2f} derece")
    print(f"  Çatı Alanı: {sistem.cati_alani_hesapla():.2f} mm^2")
    print(f"  Panel Sayısı: {sistem.panel_sayisini_hesapla()}")
    print(f"  Toplam Maliyet: {sistem.toplam_maliyeti_hesapla()} TL")
    print(f"  Toplam Güç: {sistem.toplam_gucu_hesapla()} watt\n")

