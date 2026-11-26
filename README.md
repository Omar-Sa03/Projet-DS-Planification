# Planification et Dimensionnement d'un Réseau Cellulaire GSM

Ce projet fournit un outil complet (moteur de calcul et interface graphique interactive) pour la **planification radio, le bilan de liaison et le dimensionnement de capacité d'un réseau mobile GSM**.

Il implémente les modèles théoriques de propagation cellulaire, le calcul du rapport signal sur interférence (SIR), l'allocation fréquentielle sur motifs hexagonaux réguliers et la visualisation interactive de la grille de cellules.

---

## Fonctionnalités

- **Bilan de liaison & Couverture** :
  - Calcul de la puissance d'émission limitante ($P_{\text{TX}} = \min(P_{\text{BTS}}, P_{\text{MS}})$).
  - Calcul de la perte maximale admissible (MAPL - *Maximum Allowable Path Loss*) avec prise en compte du gain d'antenne.
  - Modèle de propagation log-distance (avec perte en espace libre à la distance de référence $d_0$).
  - Détermination du rayon de cellule $R$ et de sa surface ($S = \frac{3\sqrt{3}}{2} R^2$).

- **Interférence co-canal & Réutilisation fréquentielle** :
  - Décomposition du motif de réutilisation hexagonal $N = i^2 + i \cdot j + j^2$ ($N \in \{3, 4, 7, 9, 12, 13, \dots\}$).
  - Calcul de la distance de réutilisation $D = R\sqrt{3N}$.
  - Évaluation du rapport signal sur brouillage ($SIR$) au pire des cas (6 brouilleurs co-canal de premier rang) et confrontation au seuil de qualité $SIR_{\min}$.

- **Plan de fréquences & Allocation des canaux** :
  - Répartition des $N_f$ canaux GSM disponibles entre les $N$ groupes de cellules.
  - Deux modes d'allocation supportés :
    - `entrelacee` : distribution cyclique assurant un espacement fréquentiel maximal dans chaque cellule.
    - `contigue` : blocs contigus de canaux par cellule.

- **Dimensionnement du trafic et de la capacité** :
  - Calcul du nombre d'abonnés par cellule selon la densité de population.
  - Calcul des abonnés actifs simultanés en fonction du taux d'activité ($T_{\text{act}}$).
  - Détection de la saturation éventuelle de la cellule et calcul de la densité maximale supportable.

- **Interface Graphique (GUI Tkinter + Matplotlib)** :
  - Modification interactive des paramètres en temps réel.
  - Affichage synthétique des bilans, tableaux comparatifs (motifs $N$, environnements, densités).
  - Rendu visuel d'une grille cellulaire hexagonale colorée par groupe de fréquences avec flèche de distance de réutilisation co-canal $D$.
  - Export du plan cellulaire en haute résolution (PNG) et export de la cartographie des cellules en JSON.

---

## Structure du Projet

```text
├── back_end.py         # Moteur de calcul radio, bilan de liaison, SIR et génération de grille
├── front_end.py        # Interface graphique Tkinter et visualiseur Matplotlib
├── params.json         # Paramètres d'entrée par défaut
├── test_back_end.py    # Suite de tests unitaires automatisés
├── .gitignore          # Fichiers exclus du versionnement
└── README.md           # Documentation du projet
```

---

## Paramètres de Configuration (`params.json`)

| Paramètre | Description | Unité / Valeur type |
|---|---|---|
| `P_BTS_dBm` | Puissance d'émission de la station de base (BTS) | dBm (ex: 43) |
| `P_MS_dBm` | Puissance d'émission du mobile (MS) | dBm (ex: 23) |
| `P_sens_dBm`| Sensibilité du récepteur | dBm (ex: -100) |
| `Nf` | Nombre total de fréquences / canaux alloués | ex: 124 (bande GSM 900 standard) |
| `f_port_MHz`| Fréquence porteuse | MHz (ex: 900) |
| `N` | Taille du motif cellulaire ($i^2 + ij + j^2$) | ex: 9 |
| `SIR_min_dB`| Seuil minimal requis pour le SIR | dB (ex: 17) |
| `Dst_ab` | Densité d'abonnés dans la zone | abonnés / km² (ex: 20) |
| `T_act` | Taux d'activité moyen d'un abonné à l'heure de pointe | entre 0 et 1 (ex: 0.1) |
| `Pathloss_exp`| Exposant de perte de propagation ($n$) | ex: 3.5 (suburbain), 4.0 (urbain), 3.0 (rural) |
| `d0_km` | Distance de référence pour la propagation | km (ex: 1) |
| `allocation`| Stratégie d'allocation des fréquences | `"entrelacee"` ou `"contigue"` |

---

## Prérequis et Installation

1. **Python** : Python 3.8 ou version ultérieure.
2. **Dépendances** :
   Tkinter est inclus par défaut avec la plupart des installations standard de Python sur Windows et macOS.
   Installez la bibliothèque graphique `matplotlib` :

   ```bash
   pip install matplotlib
   ```

   *(Optionnel)* Si vous utilisez `pytest` pour les tests :
   ```bash
   pip install pytest
   ```

---

## Utilisation

### 1. Lancer l'interface graphique (GUI)

Pour ouvrir l'application interactive :

```bash
python front_end.py
```

Dans l'interface :
- Modifiez les paramètres dans le panneau de gauche.
- Cliquez sur **Calculer** pour mettre à jour les résultats et la visualisation du réseau.
- Cliquez sur **Sauvegarder** pour enregistrer les paramètres actuels dans `params.json`.
- Cliquez sur **Exporter PNG** pour enregistrer la figure du plan cellulaire ainsi que son fichier JSON descriptif.

### 2. Exécuter en ligne de commande (CLI)

Vous pouvez lancer le calcul directement depuis le terminal pour obtenir un rapport texte détaillé :

```bash
python back_end.py
```

Ou en spécifiant un fichier de configuration alternatif :

```bash
python back_end.py mon_autre_config.json
```

### 3. Exécuter les tests unitaires

Pour valider le moteur de calcul et la conformité des formules :

```bash
python test_back_end.py
```

Ou avec `pytest` :

```bash
pytest test_back_end.py
```
