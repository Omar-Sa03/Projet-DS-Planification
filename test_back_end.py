"""Tests du back-end : `python test_back_end.py` (ou `pytest`)."""
import math
import back_end as be

P = be.charger_params("params.json")


def test_bilan_de_liaison():
    r = be.calculer(P)
    assert r["P_TX"] == 23 and r["MAPL"] == 125
    assert abs(r["PL_d0"] - (32.44 + 20 * math.log10(900))) < 1e-9
    # Vérification de PL(R) = MAPL
    assert abs(r["PL_d0"] + 10 * r["n"] * math.log10(r["R"] / P["d0_km"]) - r["MAPL"]) < 1e-9


def test_sir_valeurs_attendues():
    sir = {N: be.calculer(P, N=N)["SIR"] for N in (3, 7, 9)}
    assert abs(sir[3] - 8.92) < 0.01 and abs(sir[7] - 15.36) < 0.01 and abs(sir[9] - 17.27) < 0.01
    assert [be.calculer(P, N=N)["SIR_ok"] for N in (3, 7, 9)] == [False, False, True]


def test_allocation_equilibree_sans_perte():
    for mode in be.ALLOCATIONS:
        for N in (3, 4, 7, 9, 12):
            g = be.allouer_canaux(124, N, mode)
            assert sorted(c for grp in g for c in grp) == list(range(1, 125))
            tailles = [len(x) for x in g]
            assert max(tailles) - min(tailles) <= 1 and tailles == sorted(tailles, reverse=True)


def test_plan_respecte_distance_reutilisation():
    for N in (3, 4, 7, 9, 12, 13):
        r = be.calculer(P, N=N)
        groupes = be.allouer_canaux(124, N)
        cel = be.generer_plan(N, r["R"], groupes, 9, 9)
        assert {c["groupe"] for c in cel} == set(range(1, N + 1))
        dmin = min(math.dist((a["x"], a["y"]), (b["x"], b["y"]))
                   for k, a in enumerate(cel) for b in cel[k + 1:] if a["groupe"] == b["groupe"])
        assert abs(dmin - r["D"]) < 1e-6, (N, dmin, r["D"])
        assert all(c["canaux"] == groupes[c["groupe"] - 1] for c in cel)


def test_validation():
    for mauvais in ({"N": 5}, {"T_act": 2}, {"allocation": "x"}, {"Nf": "abc"}):
        try:
            be.valider({**P, **mauvais})
        except ValueError:
            continue
        raise AssertionError(mauvais)


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("OK", nom)
