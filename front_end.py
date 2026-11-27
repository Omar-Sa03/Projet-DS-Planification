"""Front-end Tkinter (tableau de bord sombre, très arrondi, animé) : paramètres, résultats, plan, export PNG.

Seule l'interface change : back_end.py et params.json restent identiques.
Animations : transitions de couleur, compteurs, barres/anneaux, glissement de page (tout via `after`).
"""
import json
import math
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont

import matplotlib
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import back_end as be

try:  # texte net sur les écrans Windows à haute densité
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

PARAMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.json")

# --- Thème -----------------------------------------------------------------
SIDE = "#A9ABB5"                       # barre latérale grise
NAV, NAV_HOVER = "#434757", "#1E2233"  # texte de navigation (inactif / survol)
BG, CARD, HOVER, SHADOW = "#252A3C", "#2E3349", "#383E5A", "#1E2233"
FIELD, LINE, TRACK = "#252A3C", "#434A6B", "#3B4160"
TEXTE, MUTED = "#F2F3F7", "#8D93AB"
TEAL, CORAL, GRAY = "#3DB59A", "#F2655A", "#3C3F48"
YEL, PUR, BLU = "#E3C77B", "#8B93C9", "#5FB3D9"
FONT = "Segoe UI"
ORDRE = ("dash", "params", "rapport")

LABELS = {
    "P_BTS_dBm": ("Puissance BTS", "dBm"), "P_MS_dBm": ("Puissance mobile (MS)", "dBm"),
    "P_sens_dBm": ("Sensibilité du récepteur", "dBm"), "f_port_MHz": ("Fréquence porteuse", "MHz"),
    "Pathloss_exp": ("Exposant d'affaiblissement n", ""), "d0_km": ("Distance de référence d₀", "km"),
    "N": ("Motif de réutilisation N", ""), "Nf": ("Nombre de canaux Nf", ""),
    "SIR_min_dB": ("SIR minimal requis", "dB"), "allocation": ("Allocation des canaux", ""),
    "Dst_ab": ("Densité d'abonnés", "ab/km²"), "T_act": ("Taux d'activité (0 à 1)", ""),
}
PAGES = {
    "dash": ("Tableau de bord", "Bilan de liaison, interférences et plan cellulaire"),
    "params": ("Paramètres", "Modifiez les valeurs, puis Calculer (ou Entrée)"),
    "rapport": ("Rapport détaillé", "Allocation des canaux et comparaisons"),
}


# --- Outils : couleurs et animation ---------------------------------------
def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def mix(a, b, t):
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


def shade(h, k):
    return "#%02x%02x%02x" % tuple(min(255, int(c * k)) for c in _rgb(h))


def tween(w, key, dur, fn, done=None):
    """Joue fn(e) avec e de 0 à 1 (ralenti en fin de course) pendant `dur` ms.
    Relancer avec la même clé sur le même widget annule l'animation précédente."""
    store = w.__dict__.setdefault("_tw", {})
    if key in store:
        try:
            w.after_cancel(store.pop(key))
        except tk.TclError:
            pass
    t0 = time.perf_counter()

    def step():
        t = min(1.0, (time.perf_counter() - t0) * 1000 / dur)
        try:
            fn(1 - (1 - t) ** 3)
        except tk.TclError:  # widget détruit entre deux images
            return
        if t < 1:
            store[key] = w.after(15, step)
        else:
            store.pop(key, None)
            if done:
                done()

    step()


def cliquable(w, cb):
    w.bind("<Button-1>", lambda e: cb())
    try:
        w.configure(cursor="hand2")
    except tk.TclError:
        pass
    for c in w.winfo_children():
        cliquable(c, cb)


def dans(w, ancetre):
    return w is not None and (str(w) == str(ancetre) or str(w).startswith(str(ancetre) + "."))


def _rrect(c, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r,
           x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
           x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


# --- Conteneurs arrondis ---------------------------------------------------
class Panel(tk.Canvas):
    """Grand panneau sombre posé sur la barre grise : coins gauches très arrondis, bords droits à fleur."""

    def __init__(self, parent, padx=(48, 34), pady=(34, 26), radius=64):
        super().__init__(parent, bg=SIDE, highlightthickness=0, width=100)
        self.padx, self.pady, self.radius = padx, pady, radius
        self.inner = tk.Frame(self, bg=BG)
        self.win = self.create_window(padx[0], pady[0], window=self.inner, anchor="nw")
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e):
        self.delete("bg")
        _rrect(self, 0, -1, e.width + 2 * self.radius, e.height + 1, self.radius, fill=BG, outline="", tags="bg")
        self.tag_lower("bg")
        self.itemconfigure(self.win, width=max(e.width - sum(self.padx), 1),
                           height=max(e.height - sum(self.pady), 1))


class Card(tk.Canvas):
    """Carte très arrondie avec ombre légère ; le contenu va dans `.inner`."""

    def __init__(self, parent, fill=CARD, bg=BG, pad=22, radius=34, **kw):
        kw.setdefault("width", 100)
        super().__init__(parent, bg=bg, highlightthickness=0, **kw)
        self.fill, self.pad, self.radius = fill, pad, radius
        self.inner = tk.Frame(self, bg=fill)
        self.win = self.create_window(pad, pad, window=self.inner, anchor="nw")
        self.bind("<Configure>", self._redraw)
        self.inner.bind("<Configure>", lambda e: self.configure(height=self.inner.winfo_reqheight() + 2 * pad + 6))

    def _redraw(self, e):
        self.delete("bg")
        _rrect(self, 2, 5, e.width - 2, e.height - 1, self.radius, fill=SHADOW, outline="", tags=("bg", "sh"))
        _rrect(self, 1, 1, e.width - 3, e.height - 5, self.radius, fill=self.fill, outline="", tags=("bg", "main"))
        self.tag_lower("bg")
        self.itemconfigure(self.win, width=max(e.width - 2 * self.pad - 4, 1),
                           height=max(e.height - 2 * self.pad - 6, 1))

    def tint(self, new):
        """Change la couleur de la carte et de tous les widgets qui partageaient son fond."""
        old, self.fill = self.fill, new
        self.itemconfigure("main", fill=new)
        self.inner.configure(bg=new)

        def walk(w):
            for c in w.winfo_children():
                try:
                    if c.cget("bg") == old:
                        c.configure(bg=new)
                except tk.TclError:
                    pass
                walk(c)
        walk(self.inner)


# --- Boutons, navigation, champs ------------------------------------------
class Nav(tk.Label):
    """Élément de menu sans fond : seul le texte change de couleur (en fondu)."""

    def __init__(self, parent, text, command, size=11):
        super().__init__(parent, text=text, bg=SIDE, fg=NAV, anchor="w", cursor="hand2", font=(FONT, size))
        self.size, self.on, self.fgc = size, False, NAV
        self.bind("<Enter>", lambda e: None if self.on else self._go(NAV_HOVER, 120))
        self.bind("<Leave>", lambda e: None if self.on else self._go(NAV, 160))
        self.bind("<Button-1>", lambda e: command())

    def _go(self, c, dur):
        a = self.fgc
        tween(self, "c", dur, lambda e: self._set(mix(a, c, e)))

    def _set(self, c):
        self.fgc = c
        self.configure(fg=c)

    def active(self, on):
        self.on = on
        self.configure(font=(FONT, self.size, "bold" if on else "normal"))
        self._go("#FFFFFF" if on else NAV, 240)


class Pill(tk.Canvas):
    """Bouton / étiquette en pilule : fondu au survol, effet d'appui, fondu au changement de style."""
    STYLES = {"chip": (TRACK, "#B7BCD3", "#454C70"), "chip_on": (TEAL, "#FFFFFF", "#4CC7AB"),
              "dark": (BG, "#FFFFFF", "#343A55"), "info": (CARD, MUTED, CARD)}

    def __init__(self, parent, text, command=None, kind="chip", px=14, py=6, size=10, weight="bold", expand=False):
        self.font = tkfont.Font(family=FONT, size=size, weight=weight)
        self.px = px
        h = self.font.metrics("linespace") + 2 * py
        super().__init__(parent, width=self.font.measure(text) + 2 * px, height=h, bg=parent.cget("bg"),
                         highlightthickness=0)
        self.text, self.kind, self.command, self.expand, self.hover = text, kind, command, expand, False
        self.col, self.fgc = self.STYLES[kind][0], self.STYLES[kind][1]
        self.bind("<Configure>", lambda e: self.draw())
        if command:
            self.configure(cursor="hand2")
            self.bind("<Enter>", lambda e: self._h(True))
            self.bind("<Leave>", lambda e: self._h(False))
            self.bind("<ButtonPress-1>", lambda e: self._go(70, shade(self.STYLES[self.kind][0], .82)))
            self.bind("<ButtonRelease-1>", self._release)

    def _h(self, v):
        self.hover = v
        self._go(150)

    def _release(self, e):
        if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.command()
        self._go(150)

    def _go(self, dur, bg=None):
        bg0, fg0, hv = self.STYLES[self.kind]
        tb, tf = bg or (hv if self.hover else bg0), fg0
        a, b = self.col, self.fgc
        tween(self, "c", dur, lambda e: self._set(mix(a, tb, e), mix(b, tf, e)))

    def _set(self, c, f):
        self.col, self.fgc = c, f
        self.draw()

    def style(self, kind):
        self.kind = kind
        self._go(220)

    def set_text(self, text):
        self.text = text
        if not self.expand:
            self.configure(width=self.font.measure(text) + 2 * self.px)
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        _rrect(self, 1, 1, w - 1, h - 1, h / 2, fill=self.col, outline="")
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fgc, font=self.font)


class Field(tk.Canvas):
    """Champ de saisie (ou liste déroulante) en pilule ; le contour passe au teal en fondu au focus."""

    def __init__(self, parent, valeurs=None):
        super().__init__(parent, height=42, bg=parent.cget("bg"), highlightthickness=0)
        self.line = LINE
        if valeurs:
            self.w = ttk.Combobox(self, values=valeurs, state="readonly", style="F.TCombobox")
        else:
            self.w = tk.Entry(self, bd=0, relief="flat", bg=FIELD, fg=TEXTE, insertbackground=TEXTE,
                              highlightthickness=0, font=(FONT, 10))
        self.win = self.create_window(20, 21, window=self.w, anchor="w")
        self.bind("<Configure>", lambda e: self.draw())
        self.w.bind("<FocusIn>", lambda e: self._f(TEAL), add="+")
        self.w.bind("<FocusOut>", lambda e: self._f(LINE), add="+")

    def _f(self, c):
        a = self.line
        tween(self, "f", 180, lambda e: self._set(mix(a, c, e)))

    def _set(self, c):
        self.line = c
        self.draw()

    def draw(self):
        self.delete("bg")
        w, h = self.winfo_width(), self.winfo_height()
        _rrect(self, 1, 1, w - 1, h - 1, h / 2, fill=FIELD, outline=self.line, width=1.5, tags="bg")
        self.tag_lower("bg")
        self.itemconfigure(self.win, width=max(w - 44, 1))

    def get(self):
        return self.w.get()

    def put(self, v):
        if isinstance(self.w, ttk.Combobox):
            self.w.set(v)
        else:
            self.w.delete(0, "end")
            self.w.insert(0, str(v))


class RScroll(tk.Canvas):
    """Barre de défilement fine, arrondie, déplaçable à la souris."""

    def __init__(self, parent, command, bg=CARD):
        super().__init__(parent, width=14, bg=bg, highlightthickness=0)
        self.cmd, self.a, self.b, self.off = command, 0.0, 1.0, 0.0
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)

    def set(self, a, b):
        self.a, self.b = float(a), float(b)
        self.draw()

    def draw(self):
        self.delete("all")
        h = self.winfo_height()
        if self.b - self.a >= 0.999 or h < 20:
            return
        y1, y2 = self.a * h + 5, max(self.b * h - 5, self.a * h + 6)
        self.create_line(7, y1, 7, y2, width=8, capstyle="round", fill="#4A5176")

    def _press(self, e):
        h = max(self.winfo_height(), 1)
        self.off = e.y / h - self.a if self.a * h <= e.y <= self.b * h else (self.b - self.a) / 2
        self._move(e)

    def _move(self, e):
        self.cmd("moveto", e.y / max(self.winfo_height(), 1) - self.off)


class Bar(tk.Canvas):
    """Barre de progression arrondie qui se remplit en douceur."""

    def __init__(self, parent, bg=CARD):
        super().__init__(parent, height=12, bg=bg, highlightthickness=0)
        self.frac, self.color = 0.0, TEAL
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, frac, color):
        a, ca, b = self.frac, self.color, max(0.0, min(1.0, frac))
        tween(self, "v", 550, lambda e: self._set(a + (b - a) * e, mix(ca, color, e)))

    def _set(self, f, c):
        self.frac, self.color = f, c
        self.draw()

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 20:
            return
        self.create_line(6, 6, w - 6, 6, width=10, capstyle="round", fill=TRACK)
        if self.frac > 0.001:
            self.create_line(6, 6, 6 + (w - 12) * self.frac, 6, width=10, capstyle="round", fill=self.color)


class Donut(tk.Canvas):
    """Anneau de progression animé ; le pourcentage affiché suit l'animation."""

    def __init__(self, parent, size=92):
        super().__init__(parent, width=size, height=size, bg=CARD, highlightthickness=0)
        self.s, self.val, self.col = size, 0.0, TEAL
        self.draw()

    def set(self, val, color):
        a, ca = self.val, self.col
        tween(self, "v", 650, lambda e: self._set(a + (val - a) * e, mix(ca, color, e)))

    def _set(self, v, c):
        self.val, self.col = v, c
        self.draw()

    def draw(self):
        self.delete("all")
        s, m = self.s, 10
        self.create_oval(m, m, s - m, s - m, outline=TRACK, width=10)
        f = max(0.0, min(1.0, self.val))
        if f > 0.002:
            self.create_arc(m, m, s - m, s - m, start=90, extent=-min(359.9, 360 * f), style="arc",
                            outline=self.col, width=10)
        self.create_text(s / 2, s / 2, text=f"{self.val * 100:.0f}%", fill=TEXTE, font=(FONT, 10, "bold"))


class Hero(Card):
    """Grande carte colorée : icône ronde, valeur animée, légende, chevron. La couleur se fond vers l'état."""

    def __init__(self, parent, glyph):
        super().__init__(parent, pad=18, radius=32)
        self.glyph, self.cur = glyph, 0.0
        i = self.inner
        self.ic = tk.Canvas(i, width=50, height=50, bg=CARD, highlightthickness=0)
        self.ic.pack(side="left")
        self.t = tk.Frame(i, bg=CARD)
        self.t.pack(side="left", padx=14, fill="x", expand=True)
        self.v = tk.Label(self.t, font=(FONT, 14, "bold"), anchor="w", bg=CARD, fg="white")
        self.s = tk.Label(self.t, font=(FONT, 9), anchor="w", bg=CARD, fg="#EDEFF5")
        self.v.pack(fill="x")
        self.s.pack(fill="x")
        self.ch = tk.Label(i, text="›", font=(FONT, 20, "bold"), bg=CARD, fg="white")
        self.ch.pack(side="right")
        self._icone(CARD)

    def _icone(self, fill):
        self.ic.delete("all")
        self.ic.create_oval(1, 1, 49, 49, fill=shade(fill, .78), outline="")
        self.ic.create_text(25, 25, text=self.glyph, fill="white", font=(FONT, 10, "bold"))

    def _paint(self, c):
        self.tint(c)
        self._icone(c)

    def set(self, num, fmt, sous, fill):
        a = self.cur
        self.cur = num
        tween(self, "n", 550, lambda e: self.v.configure(text=fmt.format(a + (num - a) * e)))
        self.s.configure(text=sous)
        c0 = self.fill
        tween(self, "c", 340, lambda e: self._paint(mix(c0, fill, e)))


class Stat(Card):
    """Carte indicateur : compteur animé, icône ronde, barre ; s'éclaircit au survol."""

    def __init__(self, parent):
        super().__init__(parent, pad=20, radius=30)
        self.cur, self.hov = 0.0, False
        i = self.inner
        top = tk.Frame(i, bg=CARD)
        top.pack(fill="x")
        left = tk.Frame(top, bg=CARD)
        left.pack(side="left")
        self.v = tk.Label(left, font=(FONT, 22, "bold"), fg=TEXTE, bg=CARD)
        self.l = tk.Label(left, font=(FONT, 9), fg=MUTED, bg=CARD)
        self.v.pack(anchor="w")
        self.l.pack(anchor="w")
        self.ic = tk.Canvas(top, width=42, height=42, bg=CARD, highlightthickness=0)
        self.ic.pack(side="right", anchor="n")
        self.p = tk.Label(i, font=(FONT, 9), fg=MUTED, bg=CARD, anchor="w")
        self.p.pack(fill="x", pady=(10, 4))
        self.bar = Bar(i)
        self.bar.pack(fill="x")
        self._bind_hover(self)

    def _bind_hover(self, w):
        w.bind("<Enter>", self._chk, add="+")
        w.bind("<Leave>", self._chk, add="+")
        for c in w.winfo_children():
            self._bind_hover(c)

    def _chk(self, e=None):
        self.after(12, self._hv)

    def _hv(self):
        try:
            inside = dans(self.winfo_containing(*self.winfo_pointerxy()), self)
        except (KeyError, tk.TclError):
            return
        if inside != self.hov:
            self.hov = inside
            a, b = self.fill, HOVER if inside else CARD
            tween(self, "t", 200, lambda e: self.tint(mix(a, b, e)))

    def set(self, num, fmt, label, pct_txt, frac, color, glyph):
        a = self.cur
        self.cur = num
        tween(self, "n", 550, lambda e: self.v.configure(text=fmt.format(a + (num - a) * e)))
        self.l.configure(text=label)
        self.p.configure(text=pct_txt)
        self.ic.delete("all")
        self.ic.create_oval(1, 1, 41, 41, fill=TRACK, outline="")
        self.ic.create_text(21, 21, text=glyph, fill=color, font=(FONT, 12, "bold"))
        self.bar.set(frac, color)


class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.c = tk.Canvas(self, bg=bg, highlightthickness=0, width=200, height=100)
        self.body = tk.Frame(self.c, bg=bg)
        self.win = self.c.create_window(0, 0, window=self.body, anchor="nw")
        self.c.pack(fill="both", expand=True)
        self.body.bind("<Configure>", lambda e: self.c.configure(scrollregion=self.c.bbox("all")))
        self.c.bind("<Configure>", lambda e: self.c.itemconfigure(self.win, width=e.width))
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, e):
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except KeyError:
            return
        if dans(w, self):
            self.c.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def vider(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.c.yview_moveto(0)


# --- Plan cellulaire -------------------------------------------------------
def palette(n):
    cmap = matplotlib.colormaps["Set3" if n <= 12 else "tab20"]
    return [to_hex(cmap(g % cmap.N)) for g in range(n)]


def hex_arrondi(cx, cy, R, f=0.3):
    """Hexagone (pointe en haut) aux coins arrondis : chaque coin est une courbe de Bézier."""
    pts = [(cx + R * math.cos(math.radians(90 + 60 * k)), cy + R * math.sin(math.radians(90 + 60 * k)))
           for k in range(6)]
    verts, codes = [], []
    for k, v in enumerate(pts):
        p, n = pts[k - 1], pts[(k + 1) % 6]
        verts += [(v[0] + f * (p[0] - v[0]), v[1] + f * (p[1] - v[1])), v,
                  (v[0] + f * (n[0] - v[0]), v[1] + f * (n[1] - v[1]))]
        codes += [Path.MOVETO if k == 0 else Path.LINETO, Path.CURVE3, Path.CURVE3]
    return Path(verts + [verts[0]], codes + [Path.CLOSEPOLY])


def dessiner_plan(fig, p, lignes=7, colonnes=7):
    """Dessine le plan dans fig et renvoie la liste des cellules (groupe + canaux)."""
    r = be.calculer(p)
    groupes = be.allouer_canaux(p["Nf"], p["N"], p["allocation"])
    cellules = be.generer_plan(p["N"], r["R"], groupes, lignes, colonnes)
    cols = palette(p["N"])
    fig.clear()
    fig.set_facecolor(CARD)
    ax = fig.add_subplot(111)
    ax.set_facecolor(CARD)
    for c in cellules:  # rayon x 0,94 : laisse un joint entre cellules
        ax.add_patch(PathPatch(hex_arrondi(c["x"], c["y"], r["R"] * 0.94), facecolor=cols[c["groupe"] - 1],
                               edgecolor="none"))
        ax.text(c["x"], c["y"], f"G{c['groupe']}", ha="center", va="center", fontsize=8,
                weight="bold", color="#1E2233")
    # Visualise D : cellule centrale -> cellule co-canal la plus proche
    centre = cellules[len(cellules) // 2]
    voisins = [c for c in cellules if c["groupe"] == centre["groupe"] and c is not centre]
    if voisins:
        v = min(voisins, key=lambda c: (c["x"] - centre["x"]) ** 2 + (c["y"] - centre["y"]) ** 2)
        ax.annotate("", (v["x"], v["y"]), (centre["x"], centre["y"]),
                    arrowprops=dict(arrowstyle="<->", color=CORAL, lw=2.5))
        ax.text((v["x"] + centre["x"]) / 2, (v["y"] + centre["y"]) / 2, f"D = {r['D']:.2f} km",
                color="white", weight="bold", fontsize=9, ha="center", va="bottom",
                bbox=dict(boxstyle="round,pad=0.4,rounding_size=0.9", facecolor=CORAL, edgecolor="none"))
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.04)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.set_xlabel("x (km)", color=MUTED, fontsize=8)
    ax.set_ylabel("y (km)", color=MUTED, fontsize=8)
    ax.set_title(f"{lignes}×{colonnes} cellules — N = {p['N']}, R = {r['R']:.2f} km, D = {r['D']:.2f} km, "
                 f"SIR = {r['SIR']:.1f} dB ({'OK' if r['SIR_ok'] else 'KO'})", fontsize=9, color=MUTED, loc="left")
    fig.tight_layout()
    return cellules


# --- Application -----------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Planification réseau mobile GSM")
        self.configure(bg=SIDE)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1480, int(sw * .94))}x{min(860, int(sh * .92))}")
        self.minsize(1150, 740)
        self.mono = next((f for f in ("Consolas", "Menlo", "DejaVu Sans Mono", "Courier New")
                          if f in tkfont.families()), "Courier")
        self._style()
        self.champs, self.pages, self.navs, self.cellules = {}, {}, {}, []
        self.page, self.gen = None, 0

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._sidebar()
        panel = Panel(self)
        panel.grid(row=0, column=1, sticky="nsew")
        main = panel.inner
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        head = tk.Frame(main, bg=BG)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        t = tk.Frame(head, bg=BG)
        t.grid(row=0, column=0, sticky="w")
        self.titre = tk.Label(t, font=(FONT, 22, "bold"), fg=TEXTE, bg=BG)
        self.titre.pack(anchor="w")
        self.sous_titre = tk.Label(t, font=(FONT, 10), fg=MUTED, bg=BG)
        self.sous_titre.pack(anchor="w")
        self.info = Pill(head, "", None, "info", px=22, py=10, size=9, weight="normal")
        self.info.grid(row=0, column=1, sticky="e")

        zone = tk.Frame(main, bg=BG)
        zone.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        for nom, build in (("dash", self._page_dash), ("params", self._page_params),
                           ("rapport", self._page_rapport)):
            f = tk.Frame(zone, bg=BG)
            build(f)
            self.pages[nom] = f
        self.montrer("dash")
        self.calculer()

    # -- construction --
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        # la liste déroulante se fond dans son conteneur arrondi (bordures = fond)
        s.configure("F.TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXTE, bordercolor=FIELD,
                    lightcolor=FIELD, darkcolor=FIELD, arrowcolor=TEXTE, arrowsize=14, padding=6)
        s.map("F.TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXTE)],
              selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXTE)],
              bordercolor=[("focus", FIELD)], lightcolor=[("focus", FIELD)], darkcolor=[("focus", FIELD)])
        self.option_add("*TCombobox*Listbox.font", (FONT, 10))
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", TEXTE)
        self.option_add("*TCombobox*Listbox.selectBackground", TEAL)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _sidebar(self):
        s = tk.Frame(self, bg=SIDE, width=240)
        s.grid(row=0, column=0, sticky="ns")
        s.pack_propagate(False)
        logo = tk.Frame(s, bg=SIDE)
        logo.pack(fill="x", padx=28, pady=(34, 38))
        badge = tk.Canvas(logo, width=38, height=38, bg=SIDE, highlightthickness=0)
        badge.create_oval(1, 1, 37, 37, fill=BG, outline="")
        badge.create_text(19, 19, text="G", fill=TEAL, font=(FONT, 14, "bold"))
        badge.pack(side="left")
        tk.Label(logo, text="GSM Plan", font=(FONT, 14, "bold"), fg="#1E2233", bg=SIDE).pack(side="left", padx=10)
        for cle, texte in (("dash", "▦    Tableau de bord"), ("params", "⚙    Paramètres"), ("rapport", "☰    Rapport")):
            n = Nav(s, texte, lambda c=cle: self.montrer(c))
            n.pack(fill="x", padx=30, pady=11)
            self.navs[cle] = n
        Nav(s, "↓    Exporter PNG", self.exporter, size=10).pack(side="bottom", fill="x", padx=30, pady=(8, 30))
        Nav(s, "✓    Sauvegarder", self.sauver, size=10).pack(side="bottom", fill="x", padx=30, pady=8)
        Pill(s, "Calculer", self.calculer, "dark", px=20, py=11, expand=True).pack(
            side="bottom", fill="x", padx=28, pady=(8, 8))

    def _page_dash(self, f):
        f.columnconfigure(0, weight=1)
        f.rowconfigure(3, weight=1)

        fr = tk.Frame(f, bg=BG)
        fr.grid(row=0, column=0, sticky="ew")
        self.hero = {}
        for c, (cle, glyph) in enumerate((("R", "R"), ("sir", "SIR"), ("cap", "CAP"))):
            fr.columnconfigure(c, weight=1, uniform="h")
            h = Hero(fr, glyph)
            h.grid(row=0, column=c, sticky="nsew", padx=(0 if c == 0 else 8, 0 if c == 2 else 8))
            cliquable(h, lambda: self.montrer("rapport"))
            self.hero[cle] = h

        tk.Label(f, text="Indicateurs clés", font=(FONT, 12, "bold"), fg=TEXTE, bg=BG).grid(
            row=1, column=0, sticky="w", pady=(22, 10))
        fr = tk.Frame(f, bg=BG)
        fr.grid(row=2, column=0, sticky="ew")
        self.stat = {}
        for c, cle in enumerate(("ab", "act", "can", "D")):
            fr.columnconfigure(c, weight=1, uniform="s")
            w = Stat(fr)
            w.grid(row=0, column=c, sticky="nsew", padx=(0 if c == 0 else 8, 0 if c == 3 else 8))
            self.stat[cle] = w

        corps = tk.Frame(f, bg=BG)
        corps.grid(row=3, column=0, sticky="nsew", pady=(18, 0))
        corps.columnconfigure(0, weight=1)
        corps.columnconfigure(1, minsize=270)
        corps.columnconfigure(2, minsize=250)
        corps.rowconfigure(0, weight=1)

        plan = Card(corps)
        plan.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(plan.inner, text="Plan cellulaire", font=(FONT, 12, "bold"), fg=TEXTE, bg=CARD).pack(anchor="w")
        ch = tk.Frame(plan.inner, bg=CARD)
        ch.pack(anchor="w", pady=(10, 0))
        self.chips_N, self.chips_alloc = {}, {}
        tk.Label(ch, text="Motif N", font=(FONT, 9), fg=MUTED, bg=CARD).pack(side="left", padx=(0, 8))
        for N in (3, 4, 7, 9, 12, 13):
            b = Pill(ch, str(N), lambda N=N: self.choisir("N", N), "chip", px=14, py=5, size=9)
            b.pack(side="left", padx=3)
            self.chips_N[N] = b
        tk.Frame(ch, width=14, bg=CARD).pack(side="left")
        for mode, txt in (("entrelacee", "Entrelacée"), ("contigue", "Contiguë")):
            b = Pill(ch, txt, lambda m=mode: self.choisir("allocation", m), "chip", px=16, py=5, size=9)
            b.pack(side="left", padx=3)
            self.chips_alloc[mode] = b
        self.fig = Figure(figsize=(6, 3.2), dpi=100, facecolor=CARD)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plan.inner)
        w = self.canvas.get_tk_widget()
        w.configure(bg=CARD, highlightthickness=0)
        w.pack(fill="both", expand=True, pady=(8, 0))

        g = Card(corps)
        g.grid(row=0, column=1, sticky="nsew", padx=8)
        tk.Label(g.inner, text="Groupes de fréquences", font=(FONT, 12, "bold"), fg=TEXTE, bg=CARD).pack(anchor="w")
        self.sous_groupes = tk.Label(g.inner, font=(FONT, 9), fg=MUTED, bg=CARD)
        self.sous_groupes.pack(anchor="w")
        self.liste = ScrollFrame(g.inner, CARD)
        self.liste.pack(fill="both", expand=True, pady=(10, 0))

        d = Card(corps)
        d.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        tk.Label(d.inner, text="Qualité et charge", font=(FONT, 12, "bold"), fg=TEXTE, bg=CARD).pack(anchor="w")
        self.don = {}
        for cle in ("sir", "cap"):
            b = tk.Frame(d.inner, bg=CARD)
            b.pack(fill="x", pady=(16, 0))
            dn = Donut(b)
            dn.pack(side="left")
            t = tk.Frame(b, bg=CARD)
            t.pack(side="left", padx=14)
            v = tk.Label(t, font=(FONT, 16, "bold"), fg=TEXTE, bg=CARD)
            l = tk.Label(t, font=(FONT, 9), fg=MUTED, bg=CARD, justify="left")
            v.pack(anchor="w")
            l.pack(anchor="w")
            self.don[cle] = (dn, v, l)

    def _page_params(self, f):
        p = be.charger_params(PARAMS)
        sections = (("Liaison radio", ("P_BTS_dBm", "P_MS_dBm", "P_sens_dBm", "f_port_MHz", "Pathloss_exp", "d0_km")),
                    ("Fréquences et interférences", ("N", "Nf", "SIR_min_dB", "allocation")),
                    ("Trafic", ("Dst_ab", "T_act")))
        for c, (titre, cles) in enumerate(sections):
            f.columnconfigure(c, weight=1, uniform="p")
            card = Card(f, pad=26)
            card.grid(row=0, column=c, sticky="new", padx=(0 if c == 0 else 8, 0 if c == 2 else 8))
            i = card.inner
            tk.Label(i, text=titre, font=(FONT, 12, "bold"), fg=TEXTE, bg=CARD).pack(anchor="w", pady=(0, 6))
            for k in cles:
                lab, unite = LABELS[k]
                tk.Label(i, text=lab, font=(FONT, 9), fg=MUTED, bg=CARD).pack(anchor="w", pady=(10, 4))
                ligne = tk.Frame(i, bg=CARD)
                ligne.pack(fill="x")
                w = Field(ligne, be.ALLOCATIONS if k == "allocation" else None)
                w.put(p[k] if k == "allocation" else f"{p[k]:g}")
                w.w.bind("<<ComboboxSelected>>" if k == "allocation" else "<Return>", lambda e: self.calculer())
                w.pack(side="left", fill="x", expand=True)
                if unite:
                    tk.Label(ligne, text=unite, font=(FONT, 9), fg=MUTED, bg=CARD, width=7, anchor="w").pack(
                        side="left", padx=(8, 0))
                self.champs[k] = w
            if c == 0:
                env = " · ".join(f"{n} {v:g}" for n, v in be.ENVIRONNEMENTS.items())
                tk.Label(i, text=f"n typique : {env}", font=(FONT, 9), fg=MUTED, bg=CARD).pack(anchor="w", pady=(14, 0))

    def _page_rapport(self, f):
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        c = Card(f, pad=26)
        c.grid(sticky="nsew")
        self.texte = tk.Text(c.inner, font=(self.mono, 10), wrap="none", bg=CARD, fg="#D8DBE8", relief="flat",
                             padx=4, pady=4, height=10, width=10, highlightthickness=0, state="disabled")
        sb = RScroll(c.inner, self.texte.yview)
        self.texte.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.texte.pack(side="left", fill="both", expand=True)

    # -- comportement --
    def montrer(self, nom):
        old = self.page
        for cle, n in self.navs.items():
            n.active(cle == nom)
        self.titre.configure(text=PAGES[nom][0])
        self.sous_titre.configure(text=PAGES[nom][1])
        if old == nom:
            return
        for cle, fr in self.pages.items():  # nettoie une transition interrompue
            if cle not in (old, nom):
                fr.place_forget()
        new = self.pages[nom]
        self.page = nom
        if old is None:
            new.place(x=0, y=0, relwidth=1, relheight=1)
            return
        d = 1 if ORDRE.index(nom) > ORDRE.index(old) else -1
        prev = self.pages[old]
        prev.place_configure(x=0)
        new.place(x=70 * d, y=0, relwidth=1, relheight=1)
        new.tkraise()

        def pas(e):
            new.place_configure(x=round(70 * d * (1 - e)))
            prev.place_configure(x=round(-70 * d * e))

        tween(self, "page", 320, pas, prev.place_forget)

    def choisir(self, cle, val):
        self.champs[cle].put(val)
        self.calculer()

    def params(self):
        return be.valider({k: w.get() for k, w in self.champs.items()})

    def _ligne_groupe(self, parent, g, ch, couleur):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=5)
        dot = tk.Canvas(row, width=38, height=38, bg=CARD, highlightthickness=0)
        dot.create_oval(2, 2, 36, 36, fill=couleur, outline="")
        dot.create_text(19, 19, text=str(g + 1), font=(FONT, 9, "bold"), fill="#1E2233")
        dot.pack(side="left")
        t = tk.Frame(row, bg=CARD)
        t.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(t, text=f"Groupe {g + 1}", font=(FONT, 10, "bold"), fg=TEXTE, bg=CARD).pack(anchor="w")
        resume = ", ".join(map(str, ch[:4])) + (", …" if len(ch) > 4 else "")
        tk.Label(t, text=resume, font=(FONT, 9), fg=MUTED, bg=CARD).pack(anchor="w")
        tk.Label(row, text=f"{len(ch)} can.", font=(FONT, 9, "bold"), fg=TEAL, bg=CARD).pack(side="right")

    def calculer(self):
        try:
            p = self.params()
        except ValueError as e:
            messagebox.showerror("Paramètres invalides", str(e))
            return None
        r = be.calculer(p)
        groupes = be.allouer_canaux(p["Nf"], p["N"], p["allocation"])
        dispo = min(len(g) for g in groupes)
        ok, charge = r["SIR_ok"], r["actifs"] / dispo
        sature = charge > 1

        self.info.set_text(f"N = {p['N']}   ·   n = {p['Pathloss_exp']:g}   ·   {p['f_port_MHz']:g} MHz")
        self.hero["R"].set(r["R"], "{:.2f} km", f"Rayon de cellule · surface {r['surface']:.2f} km²", GRAY)
        self.hero["sir"].set(r["SIR"], "{:.1f} dB",
                             f"SIR · seuil {p['SIR_min_dB']:.0f} dB " + ("respecté" if ok else "non respecté"),
                             TEAL if ok else CORAL)
        self.hero["cap"].set(r["actifs"], f"{{:.1f}} / {dispo}",
                             "Cellule saturée" if sature else "Capacité · actifs / canaux",
                             CORAL if sature else TEAL)

        st = self.stat
        st["ab"].set(r["abonnes"], "{:.0f}", "Abonnés / cellule", f"Activité {p['T_act'] * 100:.0f} %",
                     p["T_act"], TEAL, "☺")
        st["act"].set(r["actifs"], "{:.1f}", "Actifs simultanés", f"Charge des canaux {charge * 100:.0f} %",
                      charge, CORAL if sature else YEL, "⚡")
        st["can"].set(dispo, "{:.0f}", "Canaux / cellule", f"{dispo / p['Nf'] * 100:.0f} % du spectre ({p['Nf']})",
                      dispo / p["Nf"], PUR, "≋")
        st["D"].set(r["D"], "{:.2f} km", "Distance de réutilisation",
                    f"D/R = {r['D'] / r['R']:.2f} · N = {p['N']}", p["N"] / 21, BLU, "↔")

        dn, v, l = self.don["sir"]
        dn.set(r["SIR"] / p["SIR_min_dB"], TEAL if ok else CORAL)
        v.configure(text=f"{r['SIR']:.1f} dB")
        l.configure(text=f"SIR · seuil {p['SIR_min_dB']:.0f} dB")
        dn, v, l = self.don["cap"]
        dn.set(charge, CORAL if sature else YEL)
        v.configure(text=f"{r['actifs']:.1f} / {dispo}")
        l.configure(text="actifs / canaux")

        for N, b in self.chips_N.items():
            b.style("chip_on" if N == p["N"] else "chip")
        for m, b in self.chips_alloc.items():
            b.style("chip_on" if m == p["allocation"] else "chip")

        cols = palette(p["N"])
        self.sous_groupes.configure(text=f"{p['N']} groupes · {p['Nf']} canaux · {p['allocation']}")
        self.liste.vider()
        self.gen += 1
        for g, ch in enumerate(groupes):  # les lignes apparaissent en cascade
            self.after(35 * g, lambda g=g, ch=ch, gen=self.gen: gen == self.gen and
                       self._ligne_groupe(self.liste.body, g, ch, cols[g]))

        self.texte.configure(state="normal")
        self.texte.delete("1.0", "end")
        self.texte.insert("1.0", be.rapport(p))
        self.texte.configure(state="disabled")

        self.cellules = dessiner_plan(self.fig, p)
        self.canvas.draw()
        return p

    def sauver(self):
        p = self.calculer()
        if p:
            be.sauver_params(p, PARAMS)
            messagebox.showinfo("Sauvegarde", f"Paramètres enregistrés dans {PARAMS}")

    def exporter(self):
        if not self.calculer():
            return
        chemin = filedialog.asksaveasfilename(defaultextension=".png", initialfile="plan_cellulaire.png",
                                              filetypes=[("PNG", "*.png")])
        if chemin:
            self.fig.savefig(chemin, dpi=200, bbox_inches="tight", facecolor=self.fig.get_facecolor())
            with open(os.path.splitext(chemin)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(self.cellules, f, indent=1, ensure_ascii=False)
            messagebox.showinfo("Export", f"Figure : {chemin}\nAllocation par cellule : "
                                          f"{os.path.splitext(chemin)[0]}.json")


if __name__ == "__main__":
    App().mainloop()
