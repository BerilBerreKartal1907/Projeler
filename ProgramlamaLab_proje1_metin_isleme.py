import time  # Yazı yazma süresini hesaplamak için kullanılır
import tkinter as tk  # Tkinter GUI oluşturmak için kullanılır
from tkinter import messagebox  # Bilgi penceresi göstermek için kullanılır

# 1. Harfleri Alt Alta Yazdırma Fonksiyonu
def kelimeleri_harf_harf_yazdir(metin):
    sonuc = "\n".join(metin)  # Her harfi alt alta yerleştirir
    sonuc += "\n\nMetnin harfleri listelendi."
    messagebox.showinfo("Sonuç", sonuc)  # Sonucu bilgi kutusunda gösterir

# 2. Metnin Tamamen Tersi ve Kelime Tersi Fonksiyonu
def metni_ters_cevir(metin):
    ters_metin = metin[::-1]  # Metnin tamamını ters çevirir
    kelime_ters = " ".join(k[::-1] for k in metin.split())  # Kelime kelime ters çevirir
    messagebox.showinfo("Sonuç", f"Cümlenin orjinali: {metin}\nTamamen tersi alınmış hali: {ters_metin}\nKelime kelime tersi alınmış hali: {kelime_ters}")

# 3. Tüm “a” Harflerini Büyük “A” Yapma Fonksiyonu
def a_harflerini_buyut(metin):
    sonuc = metin.replace("a", "A").replace("A", "A")  # Küçük 'a'ları büyük 'A' ile değiştirir
    messagebox.showinfo("Sonuç", sonuc)

# 4. Kelimeleri Ayırma Fonksiyonu
def kelimeleri_ayri_ayri_yazdir(metin):
    kelimeler = metin.split()  # Metni kelimelere ayırır
    sonuc = f"Kelimeler Listesi: {kelimeler}"  # Kelimeleri liste olarak gösterir
    messagebox.showinfo("Sonuç", sonuc)  # Sonucu bilgi kutusunda gösterir

# 5. Kelimeleri Yeniden Birleştirme Fonksiyonu
def kelimeleri_yeniden_birlestir(metin):
    kelimeler = metin.split()  # Metni kelimelere ayırır
    sonuc = "'" + ''.join(kelimeler) + "'"  # Boşluksuz birleştirir ve tek tırnak içine alır
    messagebox.showinfo("Sonuç", sonuc)  # Sonucu bilgi kutusunda gösterir

# 6. Ünlü Harf Sayısını Bulma Fonksiyonu
def unlu_harf_sayisi_bul(metin):
    unlu_harfler = "aeıioöuüAEIİOÖUÜ"
    unlu_harf_sayisi = sum(1 for harf in metin if harf in unlu_harfler)  # Ünlü harfleri sayar
    messagebox.showinfo("Sonuç", f"{metin} metnindeki ünlü harf sayısı: {unlu_harf_sayisi}")

# 7. Yazma Hızını Hesaplama Fonksiyonu

# Başlangıç zamanını global bir değişken olarak tanımlıyoruz
baslangic = None

# Başlangıç zamanını kaydetmek için bir fonksiyon
def baslangic_zamani_al():
    global baslangic
    baslangic = time.time()  # Başlama zamanını alır
    messagebox.showinfo("Bilgi", "Metni yazdıktan sonra 'Tamam' butonuna basınız.")

# Yazma hızını hesaplayan fonksiyon
def yazi_hizi_hesapla():
    global baslangic
    if baslangic is None:
        messagebox.showinfo("Hata", "Lütfen önce yazmaya başlamak için 'Başla' butonuna basınız.")
        return

    metin = entry.get()  # Kullanıcının yazdığı metni alır
    bitis = time.time()  # Bitirme zamanını alır
    sure = bitis - baslangic  # Geçen süreyi hesaplar
    harf_sayisi = len(metin)  # Harf sayısını alır
    saniye_basina_harf = harf_sayisi / sure if sure > 0 else 0  # Saniye başına harf

    messagebox.showinfo("Sonuç", f"Geçen Süre: {sure:.2f} saniye\nSaniye Başına Harf: {saniye_basina_harf:.2f}")
    baslangic = None  # Süreyi sıfırla

# Fonksiyonları Butonlara Bağlayan Yardımcı Fonksiyon
def calistir(func):
    metin = entry.get()  # Kullanıcının girişini alır
    func(metin)  # İlgili fonksiyonu çalıştırır

# Tkinter Arayüzünü Oluştur
root = tk.Tk()
root.title("Metin İşleme Menüsü")

# Metin Girişi Alanı
entry = tk.Entry(root, width=40)
entry.pack(pady=10)

# Butonlar
tk.Button(root, text="1. Harfleri Alt Alta Yazdır", command=lambda: calistir(kelimeleri_harf_harf_yazdir)).pack(pady=2)
tk.Button(root, text="2. Metnin Tamamen ve Kelime Tersi", command=lambda: calistir(metni_ters_cevir)).pack(pady=2)
tk.Button(root, text="3. Tüm 'a' Harflerini 'A' Yap", command=lambda: calistir(a_harflerini_buyut)).pack(pady=2)
tk.Button(root, text="4. Kelimeleri Ayır", command=lambda: calistir(kelimeleri_ayri_ayri_yazdir)).pack(pady=2)
tk.Button(root, text="5. Kelimeleri Yeniden Birleştir", command=lambda: calistir(kelimeleri_yeniden_birlestir)).pack(pady=2)
tk.Button(root, text="6. Ünlü Harf Sayısını Bul", command=lambda: calistir(unlu_harf_sayisi_bul)).pack(pady=2)
tk.Button(root, text="7. Yazmaya Başla", command=baslangic_zamani_al).pack(pady=2)
tk.Button(root, text="7. Yazma Hızını Hesapla", command=yazi_hizi_hesapla).pack(pady=2)

# Çıkış Butonu
tk.Button(root, text="Çıkış", command=root.quit).pack(pady=10)

# Arayüzü Başlat
root.mainloop()

