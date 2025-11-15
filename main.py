import random
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

#ekran boyutlari
WIN_W, WIN_H = 900, 600
CANVAS_W, CANVAS_H = 800, 430

#hiz ayarlari
VEL_MIN, VEL_MAX = 2, 5
SPEED_MIN, SPEED_MAX = 0.25, 5.0
SPEED_UP_FACTOR, SLOW_DOWN_FACTOR = 1.25, 0.80

SIZE_OPTIONS = {"KÜÇÜK": 10, "ORTA": 18, "BÜYÜK": 26}
COLOR_OPTIONS = ["RED", "GREEN", "BLUE"]


# her bir topu temsil eden sinif, konumunu ve hizini tutar
class Ball:
    # top olusturulurken calisan kurucu metot, cizimi ve baslangic degerlerini ayarlar
    def __init__(self, canvas, x, y, r, color, vx, vy):
        self.canvas = canvas
        self.r = r
        self.vx = vx
        self.vy = vy
        self.oid = canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color.lower(), outline="#ddd", width=1
        )

    # topun her karede nasil hareket edecegini ve kenarlardan nasil sekecegini belirler
    def move(self, scale):
        x1, y1, x2, y2 = self.canvas.coords(self.oid)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

        # Kenarlardan sekme
        if cx - self.r <= 0 and self.vx < 0:
            self.vx = -self.vx
        if cx + self.r >= CANVAS_W and self.vx > 0:
            self.vx = -self.vx
        if cy - self.r <= 0 and self.vy < 0:
            self.vy = -self.vy
        if cy + self.r >= CANVAS_H and self.vy > 0:
            self.vy = -self.vy

        self.canvas.move(self.oid, self.vx * scale, self.vy * scale)

    # topu ekrandan silmek icin kullanilan yardimci metot
    def remove(self):
        self.canvas.delete(self.oid)


# uygulamanin ana penceresini, arayuzunu ve animasyon mantigini yoneten sinif
class App:
    # uygulama baslatildiginda pencereyi ve tum bileşenleri olusturan kurucu metot
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Animasyonlu Çizim Ekranı – Küçük Ekran Sürümü")
        root.geometry(f"{WIN_W}x{WIN_H}")
        root.resizable(False, False)

        #Tema/stil
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass

        root.configure(bg="black")
        s.configure("Dark.TFrame", background="black")
        s.configure("Dark.TLabel", background="black", foreground="white")
        s.configure("DarkHeader.TLabel", background="black", foreground="white",
                   font=("Segoe UI", 10, "bold"))
        s.configure("TButton", padding=4)

        #Durumlar
        self.running = False
        self.after_id = None
        self.balls: list[Ball] = []
        self.size = "ORTA"
        self.color = "RED"
        self.speed_scale = 1.0

        #ust satir (4 panel eşit genişlik)
        control_top = ttk.Frame(root, style="Dark.TFrame", padding=6)
        control_top.pack(side=tk.TOP, fill=tk.X)

        for c in range(4):
            control_top.grid_columnconfigure(c, weight=1, uniform="top")

        #ust kisimdaki panelleri olusturmak icin ortak kullanimli yardimci fonksiyon
        def make_panel(parent, title, col):
            panel = ttk.Frame(parent, style="Dark.TFrame")
            panel.grid(row=0, column=col, padx=6, sticky="nsew")
            panel.grid_propagate(False)
            ttk.Label(panel, text=title, style="DarkHeader.TLabel", anchor="center").pack(fill="x")
            body = ttk.Frame(panel, style="Dark.TFrame")
            body.pack(fill="both", expand=True, pady=(4, 2))
            return panel, body

        #boyut
        panel_size, body_size = make_panel(control_top, "BOYUT", 0)
        for sname in SIZE_OPTIONS:
            ttk.Button(body_size, text=sname,
                       command=lambda n=sname: self.set_size(n),
                       width=8).pack(side=tk.LEFT, padx=2)

        #RENK
        panel_color, body_color = make_panel(control_top, "RENK", 1)
        for cname in COLOR_OPTIONS:
            ttk.Button(body_color, text=cname,
                       command=lambda col=cname: self.set_color(col),
                       width=8).pack(side=tk.LEFT, padx=2)

        #TOP
        panel_top, body_top = make_panel(control_top, "TOP", 2)
        ttk.Label(body_top, text="ADET:", style="Dark.TLabel").pack(side=tk.LEFT)
        self.spin = tk.Spinbox(body_top, from_=1, to=50, width=3)
        self.spin.pack(side=tk.LEFT, padx=4)
        ttk.Button(body_top, text="EKLE", command=self.add_many, width=8).pack(side=tk.LEFT, padx=2)

        #HIZ
        panel_speed, body_speed = make_panel(control_top, "HIZ", 3)
        body_speed.grid_columnconfigure(0, weight=1)
        body_speed.grid_columnconfigure(1, weight=1)

        self.btn_speed_up = ttk.Button(body_speed, text="HIZLAN", command=self.speed_up, width=8)
        self.btn_speed_up.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_slow_down = ttk.Button(body_speed, text="YAVAŞLA", command=self.slow_down, width=8)
        self.btn_slow_down.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        self.speed_label = ttk.Label(body_speed, text=self._speed_text_short(),
                                     style="Dark.TLabel", anchor="center")
        self.speed_label.grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky="n")

        #Panel yaklaşık eşit genişlikte kalsın
        for pnl in (panel_size, panel_color, panel_top, panel_speed):
            pnl.configure(width=int((WIN_W - 6*5) / 4))

        #ALT SATIR: ANİMASYON
        control_bottom = ttk.Frame(root, style="Dark.TFrame", padding=(6, 0))
        control_bottom.pack(side=tk.TOP, fill=tk.X)

        anim_panel = ttk.Frame(control_bottom, style="Dark.TFrame")
        anim_panel.pack(side=tk.LEFT, padx=6)
        ttk.Label(anim_panel, text="ANİMASYON", style="DarkHeader.TLabel", anchor="center")\
            .pack(fill="x")
        anim_body = ttk.Frame(anim_panel, style="Dark.TFrame")
        anim_body.pack(fill="x", pady=(4, 2))

        ttk.Button(anim_body, text="START", command=self.start, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(anim_body, text="STOP", command=self.stop, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(anim_body, text="RESET", command=self.reset, width=8).pack(side=tk.LEFT, padx=3)

        #Çizim Alani
        self.canvas = tk.Canvas(
            root, width=CANVAS_W, height=CANVAS_H,
            bg="black", highlightthickness=1, highlightbackground="#444"
        )
        self.canvas.pack(pady=8)
        #arka plan gorseli
        bg_image = Image.open("galaxy_bg.png")  # resmi aç
        bg_image = bg_image.resize((CANVAS_W, CANVAS_H))  # boyutu pencereye uyarla
        self.bg_photo = ImageTk.PhotoImage(bg_image)  # tkinter formatına çevir
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")  # arka plana yerleştir

        #Kısayollar
        root.bind("<space>", lambda e: self.toggle())
        root.bind("<Key-r>", lambda e: self.reset())
        root.bind("<Up>", lambda e: self.speed_up())
        root.bind("<Down>", lambda e: self.slow_down())

        info = ttk.Label(
            root,
            text="Kısayollar: SPACE=START/STOP, R=RESET, ↑=HIZLAN, ↓=YAVAŞLA",
            style="Dark.TLabel"
        )
        info.pack(pady=(0, 6))

        #Başlangıçta UI durumunu senkronize et
        self._update_speed_ui()

    # kullaniciya hiz katsayisini kisa formatta gosterir (x1.00 gibi)
    def _speed_text_short(self):
        return f"x{self.speed_scale:.2f}"

    #hiz etiketi ve butonlarin aktif/pasif olma durumunu hiz sinirlarina gore ayarlar
    def _update_speed_ui(self):
        """Etiket ve buton etkinliklerini hız sınırlarına göre güncelle."""
        self.speed_label.config(text=self._speed_text_short())
        # sınırda ise ilgili butonu kapat
        if self.speed_scale <= SPEED_MIN + 1e-9:
            self.btn_slow_down.state(["disabled"])
        else:
            self.btn_slow_down.state(["!disabled"])
        if self.speed_scale >= SPEED_MAX - 1e-9:
            self.btn_speed_up.state(["disabled"])
        else:
            self.btn_speed_up.state(["!disabled"])

    def set_size(self, n): self.size = n
    def set_color(self, c): self.color = c

    #Top ekleme
    #spinbox'tan okunan adet kadar top eklemek icin kullanilir
    def add_many(self):
        try:
            count = int(self.spin.get())
        except ValueError:
            messagebox.showerror("Hata", "Adet sayısı geçersiz.")
            return
        for _ in range(max(0, count)):
            self.add_one()

    #tek bir topu rastgele konum ve hiz ile olusturup listeye ekler
    def add_one(self):
        r = SIZE_OPTIONS[self.size]
        x = random.randint(r, CANVAS_W - r)
        y = random.randint(r, CANVAS_H - r)
        vx = random.choice([-1, 1]) * random.uniform(VEL_MIN, VEL_MAX)
        vy = random.choice([-1, 1]) * random.uniform(VEL_MIN, VEL_MAX)
        self.balls.append(Ball(self.canvas, x, y, r, self.color, vx, vy))

    #Animasyon
    #animasyonu baslatir, eger zaten calismiyorsa animate fonksiyonunu devreye sokar
    def start(self):
        if not self.running:
            self.running = True
            self.animate()

    #animasyonu durdurur ve zamanlayiciya kayitli olan sonraki cagrilari iptal eder
    def stop(self):
        self.running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    #space tusuna basilinca start/stop durumu arasinda gecis yapar
    def toggle(self):
        self.stop() if self.running else self.start()

    #tum toplari siler, listeyi temizler ve hizi varsayilan degerine getirir
    def reset(self):
        self.stop()
        for b in self.balls:
            b.remove()
        self.balls.clear()
        self.speed_scale = 1.0
        self._update_speed_ui()

    #Hız kontrol
    # hizi arttirir, ust sinira ulastiginda kullaniciya uyar
    def speed_up(self):
        """Hızı arttır, 5.00x sınırında durdur ve mesaj göster."""
        if self.speed_scale >= SPEED_MAX - 1e-9:
            messagebox.showinfo("Hız Sınırı", "Hız zaten en yüksek değerde: x5.00")
            self.speed_scale = SPEED_MAX
            self._update_speed_ui()
            return

        prev = self.speed_scale
        self.speed_scale = min(SPEED_MAX, self.speed_scale * SPEED_UP_FACTOR)
        self._update_speed_ui()
        if prev < SPEED_MAX and self.speed_scale >= SPEED_MAX - 1e-9:
            messagebox.showinfo("Hız Sınırı", "En yüksek hıza ulaşıldı: x5.00")

    # hizi azaltir, alt sinira ulastiginda kullaniciya uyar
    def slow_down(self):
        """Hızı azalt, 0.25x sınırında durdur ve mesaj göster."""
        if self.speed_scale <= SPEED_MIN + 1e-9:
            messagebox.showinfo("Hız Sınırı", "Hız zaten en düşük değerde: x0.25")
            self.speed_scale = SPEED_MIN
            self._update_speed_ui()
            return

        prev = self.speed_scale
        self.speed_scale = max(SPEED_MIN, self.speed_scale * SLOW_DOWN_FACTOR)
        self._update_speed_ui()
        if prev > SPEED_MIN and self.speed_scale <= SPEED_MIN + 1e-9:
            messagebox.showinfo("Hız Sınırı", "En düşük hıza ulaşıldı: x0.25")

    # toplarin her karede hareket etmesini saglayan ana animasyon dongusudur
    def animate(self):
        if not self.running:
            return
        for b in self.balls:
            b.move(self.speed_scale)
        self.after_id = self.root.after(16, self.animate)  # ~60 FPS


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
