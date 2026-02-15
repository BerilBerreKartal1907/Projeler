import time
import tkinter as tk
from tkinter import messagebox, scrolledtext

UNLU_HARFLER = "aeıioöuüAEIİOÖUÜ"

class MetinAraclariUygulamasi:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Text Tools (Tkinter)")

        self.baslangic_zamani = None

        # --- Giriş alanı ---
        ust = tk.Frame(root)
        ust.pack(padx=10, pady=10, fill="x")

        tk.Label(ust, text="Text Input:").pack(anchor="w")
        self.giris = tk.Entry(ust)
        self.giris.pack(fill="x", pady=5)

        # --- Butonlar ---
        butonlar = tk.Frame(root)
        butonlar.pack(padx=10, pady=5, fill="x")

        tk.Button(butonlar, text="1) Letters (one per line)", command=self.harfleri_alt_alta).pack(fill="x", pady=2)
        tk.Button(butonlar, text="2) Reverse text & reverse each word", command=self.metni_tersle).pack(fill="x", pady=2)
        tk.Button(butonlar, text="3) Replace 'a' with 'A'", command=self.a_buyut).pack(fill="x", pady=2)
        tk.Button(butonlar, text="4) Split into words", command=self.kelimelere_ayir).pack(fill="x", pady=2)
        tk.Button(butonlar, text="5) Join words (remove spaces)", command=self.bosluklari_kaldir).pack(fill="x", pady=2)
        tk.Button(butonlar, text="6) Count vowels", command=self.unlu_say).pack(fill="x", pady=2)

        zaman = tk.Frame(root)
        zaman.pack(padx=10, pady=5, fill="x")

        tk.Button(zaman, text="Start typing timer", command=self.zaman_baslat).pack(fill="x", pady=2)
        tk.Button(zaman, text="Calculate typing speed", command=self.hiz_hesapla).pack(fill="x", pady=2)

        # --- Çıktı alanı (messagebox yerine uzun çıktı için daha iyi) ---
        alt = tk.Frame(root)
        alt.pack(padx=10, pady=10, fill="both", expand=True)

        tk.Label(alt, text="Output:").pack(anchor="w")
        self.cikti = scrolledtext.ScrolledText(alt, height=10)
        self.cikti.pack(fill="both", expand=True)

        tk.Button(root, text="Exit", command=root.quit).pack(pady=10)

    # --- yardımcılar ---
    def _metin_al(self) -> str:
        return self.giris.get()

    def _cikti_yaz(self, yazi: str):
        self.cikti.delete("1.0", tk.END)
        self.cikti.insert(tk.END, yazi)

    # --- özellikler ---
    def harfleri_alt_alta(self):
        metin = self._metin_al()
        if not metin:
            messagebox.showinfo("Info", "Please enter some text first.")
            return
        sonuc = "\n".join(metin)
        self._cikti_yaz(sonuc)

    def metni_tersle(self):
        metin = self._metin_al()
        if not metin:
            messagebox.showinfo("Info", "Please enter some text first.")
            return
        ters_metin = metin[::-1]
        kelime_ters = " ".join(k[::-1] for k in metin.split())
        self._cikti_yaz(
            f"Original: {metin}\n\n"
            f"Reversed (full): {ters_metin}\n\n"
            f"Reversed (each word): {kelime_ters}"
        )

    def a_buyut(self):
        metin = self._metin_al()
        if not metin:
            messagebox.showinfo("Info", "Please enter some text first.")
            return
        sonuc = metin.replace("a", "A")
        self._cikti_yaz(sonuc)

    def kelimelere_ayir(self):
        metin = self._metin_al()
        if not metin:
            messagebox.showinfo("Info", "Please enter some text first.")
            return
        kelimeler = metin.split()
        self._cikti_yaz(f"Words ({len(kelimeler)}):\n" + "\n".join(kelimeler))

    def bosluklari_kaldir(self):
        metin = self._metin_al()
        if not metin:
            messagebox.showinfo("Info", "Please enter some text first.")
            return
        sonuc = "".join(metin.split())
        self._cikti_yaz(sonuc)

    def unlu_say(self):
        metin = self._metin_al()
        if not metin:
            messagebox.showinfo("Info", "Please enter some text first.")
            return
        sayi = sum(1 for harf in metin if harf in UNLU_HARFLER)
        self._cikti_yaz(f"Vowel count: {sayi}")

    def zaman_baslat(self):
        self.baslangic_zamani = time.time()
        messagebox.showinfo("Info", "Timer started. Type your text, then click 'Calculate typing speed'.")

    def hiz_hesapla(self):
        if self.baslangic_zamani is None:
            messagebox.showinfo("Info", "Click 'Start typing timer' first.")
            return

        metin = self._metin_al()
        bitis = time.time()
        sure = bitis - self.baslangic_zamani
        harf_sayisi = len(metin)

        saniye_basina_harf = (harf_sayisi / sure) if sure > 0 else 0
        self.baslangic_zamani = None

        self._cikti_yaz(
            f"Elapsed time: {sure:.2f} seconds\n"
            f"Characters typed: {harf_sayisi}\n"
            f"Chars per second: {saniye_basina_harf:.2f}"
        )


def main():
    root = tk.Tk()
    app = MetinAraclariUygulamasi(root)
    root.mainloop()


if __name__ == "__main__":
    main()

