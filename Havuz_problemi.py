import math

def seramikOlcusu(havuzEn, havuzBoy, havuzDerinlik) -> tuple:
    en_boy_ebob = math.gcd(havuzEn, havuzBoy)
    derinlik_ebob = math.gcd(en_boy_ebob, havuzDerinlik)

    seramik_olcusu = (derinlik_ebob, derinlik_ebob)
    return seramik_olcusu

def seramikSayisi(havuzBoyutlari, seramikBoyutlari) -> int:
    havuzEn, havuzBoy, havuzDerinlik = havuzBoyutlari
    seramikEn, seramikBoy = seramikBoyutlari

    taban_tavan_alani = 2 * (havuzEn * havuzBoy)
    yan_yuzey_alani1 = 2 * (havuzEn * havuzDerinlik)
    yan_yuzey_alani2 = 2 * (havuzBoy * havuzDerinlik)
    toplam_yuzey_alani = taban_tavan_alani + yan_yuzey_alani1 + yan_yuzey_alani2

    seramik_alani = seramikEn * seramikBoy
    toplam_seramik_sayisi = toplam_yuzey_alani // seramik_alani

    return toplam_seramik_sayisi

havuzEn = 10
havuzBoy = 15
havuzDerinlik = 5

seramik_boyutlari = seramikOlcusu(havuzEn, havuzBoy, havuzDerinlik)
print(f"Seramik ölçüsü: {seramik_boyutlari}")

havuz_boyutlari = (havuzEn, havuzBoy, havuzDerinlik)
toplam_seramik = seramikSayisi(havuz_boyutlari, seramik_boyutlari)
print(f"Toplam seramik sayısı: {toplam_seramik}")
