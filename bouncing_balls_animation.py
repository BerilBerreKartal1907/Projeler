import random
import tkinter as tk
from tkinter import ttk, messagebox

# Optional background image support
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# Window / canvas
WIN_W, WIN_H = 900, 600
CANVAS_W, CANVAS_H = 800, 430

# Velocity & speed
VEL_MIN, VEL_MAX = 2, 5
SPEED_MIN, SPEED_MAX = 0.25, 5.0
SPEED_UP_FACTOR, SLOW_DOWN_FACTOR = 1.25, 0.80

SIZE_OPTIONS = {"SMALL": 10, "MEDIUM": 18, "LARGE": 26}
COLOR_OPTIONS = ["RED", "GREEN", "BLUE"]

DEFAULT_BG_PATH = "galaxy_bg.png"


class Ball:
    """Represents a moving ball on the canvas."""
    def __init__(self, canvas: tk.Canvas, x: int, y: int, r: int, color: str, vx: float, vy: float):
        self.canvas = canvas
        self.r = r
        self.vx = vx
        self.vy = vy
        self.oid = canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color.lower(), outline="#ddd", width=1
        )

    def move(self, scale: float):
        x1, y1, x2, y2 = self.canvas.coords(self.oid)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

        # Bounce from borders
        if cx - self.r <= 0 and self.vx < 0:
            self.vx *= -1
        if cx + self.r >= CANVAS_W and self.vx > 0:
            self.vx *= -1
        if cy - self.r <= 0 and self.vy < 0:
            self.vy *= -1
        if cy + self.r >= CANVAS_H and self.vy > 0:
            self.vy *= -1

        self.canvas.move(self.oid, self.vx * scale, self.vy * scale)

    def remove(self):
        self.canvas.delete(self.oid)


class App:
    """Tkinter app that animates bouncing balls with speed controls."""
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Bouncing Balls Animation")
        root.geometry(f"{WIN_W}x{WIN_H}")
        root.resizable(False, False)

        self.running = False
        self.after_id = None
        self.balls: list[Ball] = []
        self.size = "MEDIUM"
        self.color = "RED"
        self.speed_scale = 1.0

        # Theme
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        root.configure(bg="black")
        style.configure("Dark.TFrame", background="black")
        style.configure("Dark.TLabel", background="black", foreground="white")
        style.configure("DarkHeader.TLabel", background="black", foreground="white", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=4)

        # Top controls
        control_top = ttk.Frame(root, style="Dark.TFrame", padding=6)
        control_top.pack(side=tk.TOP, fill=tk.X)
        for c in range(4):
            control_top.grid_columnconfigure(c, weight=1, uniform="top")

        def make_panel(parent, title, col):
            panel = ttk.Frame(parent, style="Dark.TFrame")
            panel.grid(row=0, column=col, padx=6, sticky="nsew")
            panel.grid_propagate(False)
            ttk.Label(panel, text=title, style="DarkHeader.TLabel", anchor="center").pack(fill="x")
            body = ttk.Frame(panel, style="Dark.TFrame")
            body.pack(fill="both", expand=True, pady=(4, 2))
            return panel, body

        # Size panel
        panel_size, body_size = make_panel(control_top, "SIZE", 0)
        for sname in SIZE_OPTIONS:
            ttk.Button(body_size, text=sname, command=lambda n=sname: self.set_size(n), width=8)\
                .pack(side=tk.LEFT, padx=2)

        # Color panel
        panel_color, body_color = make_panel(control_top, "COLOR", 1)
        for cname in COLOR_OPTIONS:
            ttk.Button(body_color, text=cname, command=lambda col=cname: self.set_color(col), width=8)\
                .pack(side=tk.LEFT, padx=2)

        # Ball count panel
        panel_ball, body_ball = make_panel(control_top, "BALLS", 2)
        ttk.Label(body_ball, text="COUNT:", style="Dark.TLabel").pack(side=tk.LEFT)
        self.spin = tk.Spinbox(body_ball, from_=1, to=50, width=3)
        self.spin.pack(side=tk.LEFT, padx=4)
        ttk.Button(body_ball, text="ADD", command=self.add_many, width=8).pack(side=tk.LEFT, padx=2)

        # Speed panel
        panel_speed, body_speed = make_panel(control_top, "SPEED", 3)
        body_speed.grid_columnconfigure(0, weight=1)
        body_speed.grid_columnconfigure(1, weight=1)

        self.btn_speed_up = ttk.Button(body_speed, text="FASTER", command=self.speed_up, width=8)
        self.btn_speed_up.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_slow_down = ttk.Button(body_speed, text="SLOWER", command=self.slow_down, width=8)
        self.btn_slow_down.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        self.speed_label = ttk.Label(body_speed, text=self._speed_text(), style="Dark.TLabel", anchor="center")
        self.speed_label.grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky="n")

        for pnl in (panel_size, panel_color, panel_ball, panel_speed):
            pnl.configure(width=int((WIN_W - 6 * 5) / 4))

        # Animation controls
        control_bottom = ttk.Frame(root, style="Dark.TFrame", padding=(6, 0))
        control_bottom.pack(side=tk.TOP, fill=tk.X)

        anim_panel = ttk.Frame(control_bottom, style="Dark.TFrame")
        anim_panel.pack(side=tk.LEFT, padx=6)
        ttk.Label(anim_panel, text="ANIMATION", style="DarkHeader.TLabel", anchor="center").pack(fill="x")
        anim_body = ttk.Frame(anim_panel, style="Dark.TFrame")
        anim_body.pack(fill="x", pady=(4, 2))

        ttk.Button(anim_body, text="START", command=self.start, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(anim_body, text="STOP", command=self.stop, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(anim_body, text="RESET", command=self.reset, width=8).pack(side=tk.LEFT, padx=3)

        # Canvas
        self.canvas = tk.Canvas(
            root, width=CANVAS_W, height=CANVAS_H,
            bg="black", highlightthickness=1, highlightbackground="#444"
        )
        self.canvas.pack(pady=8)

        self.bg_photo = None
        self._try_load_background(DEFAULT_BG_PATH)

        # Shortcuts
        root.bind("<space>", lambda e: self.toggle())
        root.bind("<Key-r>", lambda e: self.reset())
        root.bind("<Up>", lambda e: self.speed_up())
        root.bind("<Down>", lambda e: self.slow_down())

        info = ttk.Label(
            root,
            text="Shortcuts: SPACE=START/STOP, R=RESET, ↑=FASTER, ↓=SLOWER",
            style="Dark.TLabel"
        )
        info.pack(pady=(0, 6))

        self._update_speed_ui()

    def _try_load_background(self, path: str):
        """Loads background image if Pillow and file are available."""
        if not PIL_AVAILABLE:
            return
        try:
            bg_image = Image.open(path).resize((CANVAS_W, CANVAS_H))
            self.bg_photo = ImageTk.PhotoImage(bg_image)
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
        except Exception:
            # If file missing or invalid, silently continue with black background
            self.bg_photo = None

    def _speed_text(self) -> str:
        return f"x{self.speed_scale:.2f}"

    def _update_speed_ui(self):
        self.speed_label.config(text=self._speed_text())
        if self.speed_scale <= SPEED_MIN + 1e-9:
            self.btn_slow_down.state(["disabled"])
        else:
            self.btn_slow_down.state(["!disabled"])
        if self.speed_scale >= SPEED_MAX - 1e-9:
            self.btn_speed_up.state(["disabled"])
        else:
            self.btn_speed_up.state(["!disabled"])

    def set_size(self, size_name: str):
        self.size = size_name

    def set_color(self, color_name: str):
        self.color = color_name

    def add_many(self):
        try:
            count = int(self.spin.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid count.")
            return
        for _ in range(max(0, count)):
            self.add_one()

    def add_one(self):
        r = SIZE_OPTIONS[self.size]
        x = random.randint(r, CANVAS_W - r)
        y = random.randint(r, CANVAS_H - r)
        vx = random.choice([-1, 1]) * random.uniform(VEL_MIN, VEL_MAX)
        vy = random.choice([-1, 1]) * random.uniform(VEL_MIN, VEL_MAX)
        self.balls.append(Ball(self.canvas, x, y, r, self.color, vx, vy))

    def start(self):
        if not self.running:
            self.running = True
            self.animate()

    def stop(self):
        self.running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def toggle(self):
        self.stop() if self.running else self.start()

    def reset(self):
        self.stop()
        for b in self.balls:
            b.remove()
        self.balls.clear()
        self.speed_scale = 1.0
        self._update_speed_ui()

    def speed_up(self):
        if self.speed_scale >= SPEED_MAX - 1e-9:
            messagebox.showinfo("Speed Limit", f"Maximum speed reached: x{SPEED_MAX:.2f}")
            self.speed_scale = SPEED_MAX
            self._update_speed_ui()
            return
        prev = self.speed_scale
        self.speed_scale = min(SPEED_MAX, self.speed_scale * SPEED_UP_FACTOR)
        self._update_speed_ui()
        if prev < SPEED_MAX and self.speed_scale >= SPEED_MAX - 1e-9:
            messagebox.showinfo("Speed Limit", f"Maximum speed reached: x{SPEED_MAX:.2f}")

    def slow_down(self):
        if self.speed_scale <= SPEED_MIN + 1e-9:
            messagebox.showinfo("Speed Limit", f"Minimum speed reached: x{SPEED_MIN:.2f}")
            self.speed_scale = SPEED_MIN
            self._update_speed_ui()
            return
        prev = self.speed_scale
        self.speed_scale = max(SPEED_MIN, self.speed_scale * SLOW_DOWN_FACTOR)
        self._update_speed_ui()
        if prev > SPEED_MIN and self.speed_scale <= SPEED_MIN + 1e-9:
            messagebox.showinfo("Speed Limit", f"Minimum speed reached: x{SPEED_MIN:.2f}")

    def animate(self):
        if not self.running:
            return
        for b in self.balls:
            b.move(self.speed_scale)
        self.after_id = self.root.after(16, self.animate)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
