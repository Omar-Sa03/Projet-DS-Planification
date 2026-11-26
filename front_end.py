"""Front-end Tkinter : édition/sauvegarde de params.json, résultats, plan cellulaire, export PNG."""
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import matplotlib
from matplotlib.figure import Figure
from matplotlib.patches import RegularPolygon, Patch
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import back_end as be

PARAMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.json")


def dessiner_plan(fig, p, lignes=7, colonnes=7):
    """Dessine le plan dans fig et renvoie la liste des cellules (groupe + canaux)."""
    r = be.calculer(p)
    groupes = be.allouer_canaux(p["Nf"], p["N"], p["allocation"])
    cellules = be.generer_plan(p["N"], r["R"], groupes, lignes, colonnes)
    cmap = matplotlib.colormaps["tab10" if p["N"] <= 10 else "tab20"]
    fig.clear()
    ax = fig.add_subplot(111)
    for c in cellules:
        ax.add_patch(RegularPolygon((c["x"], c["y"]), 6, radius=r["R"], facecolor=cmap(c["groupe"] - 1),
                                    edgecolor="black", alpha=0.75))
        ax.text(c["x"], c["y"], f"G{c['groupe']}", ha="center", va="center", fontsize=8, weight="bold")
    # Visualise D : cellule centrale -> cellule co-canal la plus proche
    centre = cellules[len(cellules) // 2]
    voisins = [c for c in cellules if c["groupe"] == centre["groupe"] and c is not centre]
    if voisins:
        v = min(voisins, key=lambda c: (c["x"] - centre["x"]) ** 2 + (c["y"] - centre["y"]) ** 2)
        ax.annotate("", (v["x"], v["y"]), (centre["x"], centre["y"]),
                    arrowprops=dict(arrowstyle="<->", color="red", lw=2))
        ax.text((v["x"] + centre["x"]) / 2, (v["y"] + centre["y"]) / 2, f"D = {r['D']:.2f} km",
                color="red", weight="bold", fontsize=9, ha="center", va="bottom",
                bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"))

    def resume(ch):
        return ", ".join(map(str, ch[:4])) + (", …" if len(ch) > 4 else "")
    ax.legend(handles=[Patch(facecolor=cmap(g), edgecolor="black", label=f"G{g + 1} ({len(ch)} can.) : {resume(ch)}")
                       for g, ch in enumerate(groupes)],
              title=f"Groupes ({p['allocation']})", loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.05)
    ax.set_xlabel("x (km)")
    ax.set_ylabel("y (km)")
    ax.set_title(f"Plan cellulaire {lignes}×{colonnes} — N = {p['N']}, R = {r['R']:.2f} km, "
                 f"D = {r['D']:.2f} km, SIR = {r['SIR']:.1f} dB ({'OK' if r['SIR_ok'] else 'KO'})", fontsize=10)
    fig.tight_layout()
    return cellules


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Planification réseau mobile GSM")
        self.geometry("1500x900")
        gauche = ttk.Frame(self, padding=8)
        gauche.pack(side="left", fill="y")

        self.champs = {}
        p = be.charger_params(PARAMS)
        for ligne, (k, v) in enumerate(p.items()):
            ttk.Label(gauche, text=k).grid(row=ligne, column=0, sticky="w")
            if k == "allocation":
                w = ttk.Combobox(gauche, values=be.ALLOCATIONS, state="readonly", width=14)
                w.set(v)
            else:
                w = ttk.Entry(gauche, width=16)
                w.insert(0, f"{v:g}")
            w.grid(row=ligne, column=1, pady=1)
            self.champs[k] = w

        boutons = ttk.Frame(gauche)
        boutons.grid(row=len(p), column=0, columnspan=2, pady=8)
        ttk.Button(boutons, text="Calculer", command=self.calculer).pack(side="left", padx=2)
        ttk.Button(boutons, text="Sauvegarder", command=self.sauver).pack(side="left", padx=2)
        ttk.Button(boutons, text="Exporter PNG", command=self.exporter).pack(side="left", padx=2)

        self.texte = tk.Text(gauche, width=72, font=("Consolas", 9), wrap="none")
        self.texte.grid(row=len(p) + 1, column=0, columnspan=2, sticky="ns")
        gauche.rowconfigure(len(p) + 1, weight=1)

        self.fig = Figure(figsize=(9, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)
        self.cellules = []
        self.calculer()

    def params(self):
        return be.valider({k: w.get() for k, w in self.champs.items()})

    def calculer(self):
        try:
            p = self.params()
        except ValueError as e:
            messagebox.showerror("Paramètres invalides", str(e))
            return None
        self.texte.delete("1.0", "end")
        self.texte.insert("1.0", be.rapport(p))
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
            self.fig.savefig(chemin, dpi=200, bbox_inches="tight")
            with open(os.path.splitext(chemin)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(self.cellules, f, indent=1, ensure_ascii=False)
            messagebox.showinfo("Export", f"Figure : {chemin}\nAllocation par cellule : "
                                          f"{os.path.splitext(chemin)[0]}.json")


if __name__ == "__main__":
    App().mainloop()
