import tkinter as tk
from tkinter import messagebox

# Kitap sınıfı, her kitabın özelliklerini tanımlar.
class Kitap:
    def __init__(self, ad, yazar, yil):
        # Kitap bilgileri: adı, yazarı ve yayın yılı.
        self.ad = ad
        self.yazar = yazar
        self.yil = yil

    def __str__(self):
        # Kitap bilgisini string formatında döndürür.
        return f"Kitap Adı: {self.ad}, Yazar: {self.yazar}, Yayın Yılı: {self.yil}"

# Kütüphane sınıfı, kitapları yönetmek için gerekli işlevleri içerir.
class Kutuphane:
    def __init__(self):
        # Kitapların tutulduğu liste.
        self.kitaplar = []

    def kitap_ekle(self, kitap):
        # Yeni kitap ekler.
        self.kitaplar.append(kitap)

    def kitap_sil(self, kitap_ad):
        # Belirtilen isimdeki kitabı listeden kaldırır.
        for kitap in self.kitaplar:
            if kitap.ad == kitap_ad:
                self.kitaplar.remove(kitap)
                return True  # Silme başarılı.
        return False  # Kitap bulunamadı.

    def isim_ile_arama(self, kitap_ad):
        # Kitap ismine göre arama yapar.
        return [kitap for kitap in self.kitaplar if kitap.ad == kitap_ad]

    def yazar_ile_arama(self, yazar_ad):
        # Yazara göre arama yapar.
        return [kitap for kitap in self.kitaplar if kitap.yazar == yazar_ad]

    def tum_kitaplari_listele(self):
        # Tüm kitapları döndürür.
        return self.kitaplar

# Arayüz sınıfı, Tkinter ile oluşturulan GUI işlevlerini içerir.
class KutuphaneUygulamasi:
    def __init__(self, root):
        # Ana pencereyi ve Kutuphane sınıfını başlatır.
        self.root = root
        self.root.title("Kütüphane Kitap Arama Sistemi")
        self.kutuphane = Kutuphane()

        # Başlık etiketini oluştur.
        tk.Label(root, text="Kütüphane Kitap Arama Sistemi", font=("Arial", 16)).pack(pady=10)

        # Kullanıcı işlemleri için düğmeleri oluştur.
        tk.Button(root, text="Kitap Ekle", command=self.kitap_ekle_penceresi, width=20).pack(pady=5)
        tk.Button(root, text="Kitap Sil", command=self.kitap_sil_penceresi, width=20).pack(pady=5)
        tk.Button(root, text="Kitap Ara (İsme Göre)", command=self.isime_gore_arama_penceresi, width=20).pack(pady=5)
        tk.Button(root, text="Kitap Ara (Yazara Göre)", command=self.yazara_gore_arama_penceresi, width=20).pack(pady=5)
        tk.Button(root, text="Tüm Kitapları Listele", command=self.tum_kitaplari_listele_penceresi, width=20).pack(pady=5)
        tk.Button(root, text="Çıkış", command=root.quit, width=20).pack(pady=5)

    def kitap_ekle_penceresi(self):
        # Kitap ekleme penceresini açar.
        pencere = tk.Toplevel(self.root)
        pencere.title("Kitap Ekle")

        # Kullanıcıdan kitap bilgilerini al.
        tk.Label(pencere, text="Kitap Adı:").grid(row=0, column=0, padx=10, pady=5)
        ad_giris = tk.Entry(pencere)
        ad_giris.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(pencere, text="Yazar:").grid(row=1, column=0, padx=10, pady=5)
        yazar_giris = tk.Entry(pencere)
        yazar_giris.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(pencere, text="Yayın Yılı:").grid(row=2, column=0, padx=10, pady=5)
        yil_giris = tk.Entry(pencere)
        yil_giris.grid(row=2, column=1, padx=10, pady=5)

        def kitap_ekle():
            # Yeni kitabı ekler ve kullanıcıya bilgi verir.
            ad = ad_giris.get()
            yazar = yazar_giris.get()
            yil = yil_giris.get()

            if not ad or not yazar or not yil:
                messagebox.showwarning("Hata", "Tüm alanları doldurun!")
                return

            if not yazar.isalpha():
                messagebox.showwarning("Hata", "Yazar ismi sadece harflerden oluşmalıdır!")
                return

            if not yil.isdigit():
                messagebox.showwarning("Hata", "Yayın yılı sadece rakamlardan oluşmalıdır!")
                return

            kitap = Kitap(ad, yazar, yil)
            self.kutuphane.kitap_ekle(kitap)
            messagebox.showinfo("Başarılı", f"{ad} başarıyla eklendi.")
            pencere.destroy()

        # Kitap ekleme düğmesi.
        tk.Button(pencere, text="Ekle", command=kitap_ekle).grid(row=3, column=0, columnspan=2, pady=10)

    def kitap_sil_penceresi(self):
        # Kitap silme penceresini açar.
        pencere = tk.Toplevel(self.root)
        pencere.title("Kitap Sil")

        # Kullanıcıdan silinecek kitabın adını al.
        tk.Label(pencere, text="Kitap Adı:").grid(row=0, column=0, padx=10, pady=5)
        ad_giris = tk.Entry(pencere)
        ad_giris.grid(row=0, column=1, padx=10, pady=5)

        def kitap_sil():
            # Kitabı siler ve sonucu kullanıcıya bildirir.
            ad = ad_giris.get()
            if ad:
                basarili = self.kutuphane.kitap_sil(ad)
                if basarili:
                    messagebox.showinfo("Başarılı", f"{ad} başarıyla silindi.")
                    pencere.destroy()
                else:
                    messagebox.showwarning("Hata", f"{ad} bulunamadı.")
            else:
                messagebox.showwarning("Hata", "Lütfen bir kitap adı girin!")

        # Kitap silme düğmesi.
        tk.Button(pencere, text="Sil", command=kitap_sil).grid(row=1, column=0, columnspan=2, pady=10)

    def isime_gore_arama_penceresi(self):
        # İsme göre arama penceresini açar.
        pencere = tk.Toplevel(self.root)
        pencere.title("Kitap Ara (İsme Göre)")

        # Kullanıcıdan aranacak kitabın adını al.
        tk.Label(pencere, text="Kitap Adı:").grid(row=0, column=0, padx=10, pady=5)
        ad_giris = tk.Entry(pencere)
        ad_giris.grid(row=0, column=1, padx=10, pady=5)

        def kitap_ara():
            # Kitap arar ve sonuçları kullanıcıya gösterir.
            ad = ad_giris.get()
            if ad:
                sonuclar = self.kutuphane.isim_ile_arama(ad)
                if sonuclar:
                    sonuc_metni = "\n".join(str(kitap) for kitap in sonuclar)
                    messagebox.showinfo("Arama Sonuçları", sonuc_metni)
                else:
                    messagebox.showinfo("Sonuç Bulunamadı", "Kitap bulunamadı.")
            else:
                messagebox.showwarning("Hata", "Lütfen bir kitap adı girin!")

        # Arama düğmesi.
        tk.Button(pencere, text="Ara", command=kitap_ara).grid(row=1, column=0, columnspan=2, pady=10)

    def yazara_gore_arama_penceresi(self):
        # Yazara göre arama penceresini açar.
        pencere = tk.Toplevel(self.root)
        pencere.title("Kitap Ara (Yazara Göre)")

        # Kullanıcıdan aranacak yazarın adını al.
        tk.Label(pencere, text="Yazar Adı:").grid(row=0, column=0, padx=10, pady=5)
        yazar_giris = tk.Entry(pencere)
        yazar_giris.grid(row=0, column=1, padx=10, pady=5)

        def yazar_ara():
            # Yazar arar ve sonuçları kullanıcıya gösterir.
            yazar = yazar_giris.get()
            if yazar:
                sonuclar = self.kutuphane.yazar_ile_arama(yazar)
                if sonuclar:
                    sonuc_metni = "\n".join(str(kitap) for kitap in sonuclar)
                    messagebox.showinfo("Arama Sonuçları", sonuc_metni)
                else:
                    messagebox.showinfo("Sonuç Bulunamadı", "Yazar bulunamadı.")
            else:
                messagebox.showwarning("Hata", "Lütfen bir yazar adı girin!")

        # Arama düğmesi.
        tk.Button(pencere, text="Ara", command=yazar_ara).grid(row=1, column=0, columnspan=2, pady=10)

    def tum_kitaplari_listele_penceresi(self):
        # Tüm kitapları listeleme penceresini açar.
        pencere = tk.Toplevel(self.root)
        pencere.title("Tüm Kitapları Listele")

        # Tüm kitapları al ve göster.
        kitaplar = self.kutuphane.tum_kitaplari_listele()
        if kitaplar:
            sonuc_metni = "\n".join(str(kitap) for kitap in kitaplar)
            tk.Label(pencere, text=sonuc_metni, justify="left").pack(padx=10, pady=10)
        else:
            tk.Label(pencere, text="Kütüphane boş.").pack(padx=10, pady=10)

# Ana program başlatılır.
if __name__ == "__main__":
    root = tk.Tk()
    uygulama = KutuphaneUygulamasi(root)
    root.mainloop()
