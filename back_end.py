"""Back-end : bilan de liaison, réutilisation, SIR, capacité, allocation et plan hexagonal."""
import json
import math
import sys

G_ANT = 2.0  # dB, gain d'antenne forfaitaire (émission + réception)
ENVIRONNEMENTS = {"urbain": 4.0, "suburbain": 3.5, "rural": 3.0}  # exposants log-distance typiques
ZONE_REF_KM2 = 1000  # zone de référence pour comparer le nombre de sites
ALLOCATIONS = ("entrelacee", "contigue")
NUMERIQUES = ("P_BTS_dBm", "P_MS_dBm", "P_sens_dBm", "f_port_MHz", "SIR_min_dB",
              "Dst_ab", "T_act", "Pathloss_exp", "d0_km")


def charger_params(chemin="params.json"):
    with open(chemin, encoding="utf-8") as f:
        return valider(json.load(f))


def sauver_params(p, chemin="params.json"):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(valider(p), f, indent=2, ensure_ascii=False)


def valider(p):
    """Convertit et contrôle les paramètres (venant du JSON ou de l'interface)."""
    q = dict(p)
    try:
        for k in NUMERIQUES:
            q[k] = float(q[k])
        for k in ("N", "Nf"):
            q[k] = int(float(q[k]))
    except KeyError as e:
        raise ValueError(f"Paramètre manquant : {e}") from None
    except (TypeError, ValueError):
        raise ValueError(f"Paramètre non numérique : {k} = {q[k]!r}") from None
    q.setdefault("allocation", "entrelacee")
    if q["allocation"] not in ALLOCATIONS:
        raise ValueError(f"allocation doit être l'une de {ALLOCATIONS}")
    if q["Nf"] < q["N"]:
        raise ValueError("Nf doit être ≥ N (au moins un canal par groupe)")
    if not 0 <= q["T_act"] <= 1:
        raise ValueError("T_act doit être entre 0 et 1")
    for k in ("f_port_MHz", "Pathloss_exp", "d0_km", "Dst_ab"):
        if q[k] <= 0:
            raise ValueError(f"{k} doit être > 0")
    decomposer_N(q["N"])
    return q


def decomposer_N(N):
    """Renvoie (i, j) tels que N = i² + i·j + j², sinon ValueError."""
    for i in range(1, N + 1):
        for j in range(0, i + 1):
            if i * i + i * j + j * j == N:
                return i, j
    raise ValueError(f"N = {N} n'est pas un motif hexagonal valide (3, 4, 7, 9, 12, 13…)")


def calculer(p, N=None, n=None, Dst_ab=None):
    """Toutes les grandeurs du §4 ; N, n, Dst_ab peuvent être surchargés pour les comparaisons."""
    N = p["N"] if N is None else N
    n = p["Pathloss_exp"] if n is None else n
    Dst_ab = p["Dst_ab"] if Dst_ab is None else Dst_ab
    decomposer_N(N)
    P_TX = min(p["P_BTS_dBm"], p["P_MS_dBm"])
    MAPL = P_TX - p["P_sens_dBm"] + G_ANT
    PL_d0 = 32.44 + 20 * math.log10(p["d0_km"]) + 20 * math.log10(p["f_port_MHz"])  # espace libre à d0
    R = p["d0_km"] * 10 ** ((MAPL - PL_d0) / (10 * n))
    D_sur_R = math.sqrt(3 * N)
    SIR = 10 * n * math.log10(D_sur_R) - 10 * math.log10(6)
    surface = 3 * math.sqrt(3) / 2 * R ** 2
    abonnes = surface * Dst_ab
    actifs = abonnes * p["T_act"]
    return {"N": N, "n": n, "P_TX": P_TX, "MAPL": MAPL, "PL_d0": PL_d0, "R": R, "D": R * D_sur_R,
            "SIR": SIR, "SIR_ok": SIR >= p["SIR_min_dB"], "canaux": p["Nf"] / N,
            "surface": surface, "abonnes": abonnes, "actifs": actifs,
            "canaux_necessaires": math.ceil(actifs), "Dst_ab": Dst_ab}


def allouer_canaux(Nf, N, mode="entrelacee"):
    """Liste de N groupes de canaux (numérotés 1..Nf) ; le reste Nf mod N va aux premiers groupes."""
    if mode == "entrelacee":
        return [list(range(g + 1, Nf + 1, N)) for g in range(N)]
    groupes, c = [], 1
    for g in range(N):
        taille = Nf // N + (g < Nf % N)
        groupes.append(list(range(c, c + taille)))
        c += taille
    return groupes


def generer_plan(N, R, groupes, lignes=7, colonnes=7):
    """Grille hexagonale (hexagones pointe en haut, décalage 'odd-r').

    Les cellules co-canal forment le réseau engendré par v=(i,j) et sa rotation de 60° w=(-j,i+j)
    (coordonnées axiales). La classe d'une cellule modulo ce réseau = son groupe de fréquences.
    """
    i, j = decomposer_N(N)

    def classe(q, r):
        return (((i + j) * q + j * r) % N, (i * r - j * q) % N)

    classes = sorted({classe(q, r) for q in range(N) for r in range(N)})
    index = {c: g for g, c in enumerate(classes)}
    cellules = []
    for ligne in range(lignes):
        for col in range(colonnes):
            q, r = col - ligne // 2, ligne
            g = index[classe(q, r)]
            cellules.append({"ligne": ligne, "colonne": col,
                             "x": math.sqrt(3) * R * (q + r / 2), "y": 1.5 * R * r,
                             "groupe": g + 1, "canaux": groupes[g]})
    return cellules


def rapport(p):
    """Texte complet des résultats + comparaisons (N, environnement, densité)."""
    r = calculer(p)
    groupes = allouer_canaux(p["Nf"], p["N"], p["allocation"])
    tailles = sorted({len(g) for g in groupes})
    L = [f"=== Résultats (N = {p['N']}, n = {p['Pathloss_exp']}) ===",
         f"P_TX = {r['P_TX']:.1f} dBm   MAPL = {r['MAPL']:.2f} dB   PL(d0) = {r['PL_d0']:.2f} dB (espace libre)",
         f"Rayon R               = {r['R']:.3f} km",
         f"Distance réutil. D    = {r['D']:.3f} km  (D/R = {r['D'] / r['R']:.3f})",
         f"SIR                   = {r['SIR']:.2f} dB  -> {'OK' if r['SIR_ok'] else 'NON RESPECTÉ'}"
         f" (seuil {p['SIR_min_dB']:.1f} dB)",
         f"Canaux / cellule      = {r['canaux']:.2f}  (groupes réels : {'/'.join(map(str, tailles))})",
         f"Surface cellule       = {r['surface']:.2f} km²",
         f"Abonnés / cellule     = {r['abonnes']:.0f}",
         f"Actifs simultanés     = {r['actifs']:.1f}  vs {min(tailles)} canaux -> "
         + ("capacité suffisante" if r["actifs"] <= min(tailles) else "SATURÉ"),
         ""]
    if not r["SIR_ok"]:
        ok = [N for N in (3, 4, 7, 9, 12, 13, 16, 19, 21) if calculer(p, N=N)["SIR_ok"]]
        L += [f"Solutions : motif N ≥ {ok[0] if ok else '?'} ; sectorisation ; environnement à n plus élevé.", ""]

    L.append(f"=== Allocation {p['allocation']} des {p['Nf']} canaux ===")
    L += [f"G{g + 1} ({len(c)}) : {', '.join(map(str, c))}" for g, c in enumerate(groupes)]

    L += ["", "=== Comparaison des motifs ===",
          f"{'N':>3} {'R (km)':>8} {'D (km)':>8} {'SIR (dB)':>9} {'Canaux/c':>9} {'Abonnés/c':>10}  SIR≥min"]
    for N in (3, 7, 9):
        c = calculer(p, N=N)
        L.append(f"{N:>3} {c['R']:>8.2f} {c['D']:>8.2f} {c['SIR']:>9.2f} {c['canaux']:>9.2f}"
                 f" {c['abonnes']:>10.0f}  {'oui' if c['SIR_ok'] else 'non'}")

    L += ["", f"=== Impact de l'environnement (N = {p['N']}) ===",
          f"{'Env.':<10} {'n':>4} {'R (km)':>8} {'Surf. km²':>10} {'Sites/' + str(ZONE_REF_KM2) + 'km²':>14} {'SIR (dB)':>9}"]
    for nom, n in ENVIRONNEMENTS.items():
        c = calculer(p, n=n)
        L.append(f"{nom:<10} {n:>4} {c['R']:>8.2f} {c['surface']:>10.1f}"
                 f" {math.ceil(ZONE_REF_KM2 / c['surface']):>14} {c['SIR']:>9.2f}")

    L += ["", f"=== Impact de la densité (N = {p['N']}, T_act = {p['T_act']}) ===",
          f"{'Dst (ab/km²)':>12} {'Abonnés/c':>10} {'Actifs':>8} {'Canaux néc.':>12} {'Dispo':>6}"]
    for d in (1, 5, 10, 20, 50, 100):
        c = calculer(p, Dst_ab=d)
        L.append(f"{d:>12} {c['abonnes']:>10.0f} {c['actifs']:>8.1f} {c['canaux_necessaires']:>12} {min(tailles):>6}")
    d_max = min(tailles) / (r["surface"] * p["T_act"]) if p["T_act"] else math.inf
    L.append(f"Densité max supportable avec R actuel : {d_max:.2f} ab/km²")
    return "\n".join(L)


if __name__ == "__main__":
    print(rapport(charger_params(sys.argv[1] if len(sys.argv) > 1 else "params.json")))
