import math

class GunesPaneli:
    def __init__(self, guc_watt, genislik_mm, yukseklik_mm, verimlilik, maliyet_tl):
        self.guc_watt = guc_watt
        self.genislik_mm = genislik_mm
        self.yukseklik_mm = yukseklik_mm
        self.verimlilik = verimlilik
        self.maliyet_tl = maliyet_tl

    def alan_hesapla(self):
        return self.genislik_mm * self.yukseklik_mm


class Ev:
    def __init__(self, genislik_mm, uzunluk_mm, enlem):
        self.genislik_mm = genislik_mm
        self.uzunluk_mm = uzunluk_mm
        self.enlem = enlem


class GunesEnerjisiSistemi:
    PANEL_ARALIGI_MM = 20
    DUNYA_EKSEN_EGIKLIGI = 23.5

    def __init__(self, ev, panel):
        self.ev = ev
        self.panel = panel

    def egim_acisi_hesapla(self):
        return self.ev.enlem * 0.9 - self.DUNYA_EKSEN_EGIKLIGI

    def cati_alani_hesapla(self):
        egim = math.radians(self.egim_acisi_hesapla())
        kisa_kenar = min(self.ev.genislik_mm, self.ev.uzunluk_mm)
        efektif_kenar = kisa_kenar * math.cos(egim)
        return kisa_kenar * efektif_kenar

    def panel_sayisini_hesapla(self):
        panel_alani = (
            (self.panel.genislik_mm + self.PANEL_ARALIGI_MM) *
            (self.panel.yukseklik_mm + self.PANEL_ARALIGI_MM)
        )
        return int(self.cati_alani_hesapla() // panel_alani)

    def toplam_maliyet(self):
        return self.panel_sayisini_hesapla() * self.panel.maliyet_tl

    def toplam_guc(self):
        return self.panel_sayisini_hesapla() * self.panel.guc_watt * self.panel.verimlilik
