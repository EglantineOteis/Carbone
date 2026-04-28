"""
MoteurCalcul — cœur du calcul carbone et énergie.

Sources de données :
  - ADENE  : base de données énergie Portugal/France
  - INIES  : base française de données environnementales (FDES/PEP)
  - OTEIS  : retours d'expérience internes

Indicateurs calculés :
  - Ic_énergie  : impact carbone lié à l'énergie (kgCO2eq/m².an)
  - Ic_bâtiment : impact carbone des matériaux de construction
  - Consommation: kWh_ep/m².an (énergie primaire)
  - Conformité RE2020 par niveau (seuil 2022 / 2025 / 2028 / 2031)
"""

import json
from pathlib import Path
from typing import Any


class MoteurCalcul:
    """Calcule les bilans carbone et énergie d'un projet de construction."""

    def __init__(self, bases_dir: Path):
        self.bases_dir = bases_dir
        self._facteurs = self._charger_facteurs()

    # ─────────────────────────────────────────────
    #  Chargement des bases
    # ─────────────────────────────────────────────

    def _charger_facteurs(self) -> dict:
        """Charge les facteurs d'émission depuis les fichiers JSON des bases."""
        facteurs_path = self.bases_dir / "facteurs_emission.json"
        if facteurs_path.exists():
            with open(facteurs_path, encoding="utf-8") as f:
                return json.load(f)
        # Retourne les valeurs intégrées par défaut
        return self._facteurs_par_defaut()

    def _facteurs_par_defaut(self) -> dict:
        """
        Facteurs d'émission de référence (sources ADEME/INIES/RT2020).
        Unités : kgCO2eq par unité fonctionnelle
        """
        return {
            # ── Énergie (kgCO2eq/kWh_ep)
            "energie": {
                "electricite_france": 0.0485,   # grille nationale 2023
                "gaz_naturel": 0.227,
                "fioul": 0.324,
                "bois_granule": 0.030,
                "reseaux_chaleur_moyen": 0.110,
            },
            # ── Systèmes CVC (kgCO2eq/m².an — impact fabrication amorti 50 ans)
            "systemes_cvc": {
                "PAC air/eau":              {"fabrication": 2.1, "conso_kwhep_m2": 45},
                "PAC réversible":           {"fabrication": 1.8, "conso_kwhep_m2": 40},
                "PAC thermodynamique":      {"fabrication": 1.5, "conso_kwhep_m2": 30},
                "Chaudière gaz":            {"fabrication": 0.9, "conso_kwhep_m2": 85},
                "Chaudière biomasse":       {"fabrication": 1.2, "conso_kwhep_m2": 55},
                "Réseau de chaleur urbain": {"fabrication": 0.5, "conso_kwhep_m2": 60},
                "double flux":              {"fabrication": 0.8, "conso_kwhep_m2": 8},
                "simple flux":              {"fabrication": 0.4, "conso_kwhep_m2": 15},
            },
            # ── Matériaux isolation (kgCO2eq/kg)
            "isolation": {
                "laine de roche":   {"co2_kg": 1.28, "densite_kg_m3": 50},
                "laine de verre":   {"co2_kg": 1.35, "densite_kg_m3": 15},
                "polystyrène":      {"co2_kg": 3.20, "densite_kg_m3": 25},
                "polyuréthane":     {"co2_kg": 3.80, "densite_kg_m3": 35},
                "ouate cellulose":  {"co2_kg": 0.45, "densite_kg_m3": 45},
                "liège":            {"co2_kg": -0.20, "densite_kg_m3": 120},  # stockage carbone
                "chanvre":          {"co2_kg": -0.30, "densite_kg_m3": 40},
                "laine bois":       {"co2_kg": -0.40, "densite_kg_m3": 50},
            },
            # ── ENR (kgCO2eq/m² installé — fabrication + pose)
            "enr": {
                "photovoltaïque":    {"co2_m2": 85, "production_kwh_m2_an": 120},
                "solaire thermique": {"co2_m2": 45, "production_kwh_m2_an": 450},
                "géothermie":        {"co2_m2": 0,  "puissance_cop": 4.5},
            },
            # ── Seuils RE2020 (kgCO2eq/m².an — Ic_énergie)
            "seuils_re2020": {
                "bureaux": {
                    "2022": 6.0,
                    "2025": 5.0,
                    "2028": 4.0,
                    "2031": 3.0,
                },
                "logement": {
                    "2022": 14.0,
                    "2025": 13.0,
                    "2028": 11.0,
                    "2031": 9.0,
                },
                "autres": {
                    "2022": 10.0,
                    "2025": 8.5,
                    "2028": 7.0,
                    "2031": 5.5,
                }
            }
        }

    # ─────────────────────────────────────────────
    #  Calcul principal
    # ─────────────────────────────────────────────

    def calculer(self, donnees: dict, variantes: list = []) -> dict:
        """
        Calcule le bilan carbone complet du projet.

        Returns:
            {
              "resume": {...},
              "detail_postes": {...},
              "conformite_re2020": {...},
              "sources": [...],
              "variantes": [...]  // si des variantes sont passées
            }
        """
        surface = donnees.get("surface_plancher", 1)
        type_bat = donnees.get("type_batiment", "bureaux")
        zone = donnees.get("zone_climatique", "H1")

        # ── Calcul par poste
        ic_cvc   = self._calculer_cvc(donnees, surface)
        ic_isol  = self._calculer_isolation(donnees, surface)
        ic_enr   = self._calculer_enr(donnees, surface)
        conso    = self._calculer_conso_energie(donnees, surface, zone)

        ic_energie = conso["kwh_ep_m2"] * self._facteurs["energie"]["electricite_france"]

        ic_total = ic_cvc["co2_m2"] + ic_isol["co2_m2"] + ic_enr["credit_co2_m2"] + ic_energie

        # ── Conformité RE2020
        conformite = self._verifier_re2020(ic_energie, type_bat)

        # ── Résultat principal
        bilan = {
            "resume": {
                "ic_energie_kgco2_m2_an":  round(ic_energie, 2),
                "ic_batiment_kgco2_m2_an": round(ic_cvc["co2_m2"] + ic_isol["co2_m2"], 2),
                "ic_total_kgco2_m2_an":    round(ic_total, 2),
                "conso_kwh_ep_m2":         round(conso["kwh_ep_m2"], 1),
                "conso_kwh_ef_m2":         round(conso["kwh_ef_m2"], 1),
                "surface_m2":              surface,
                "ic_total_projet_tco2":    round(ic_total * surface / 1000, 1),
            },
            "detail_postes": {
                "cvc":       ic_cvc,
                "isolation": ic_isol,
                "enr":       ic_enr,
                "energie":   {
                    "kwh_ep_m2":   round(conso["kwh_ep_m2"], 1),
                    "kwh_ef_m2":   round(conso["kwh_ef_m2"], 1),
                    "co2_m2":      round(ic_energie, 2),
                    "source":      "ADEME mix électrique 2023"
                }
            },
            "conformite_re2020": conformite,
            "sources": [
                "ADEME — Base Carbone v23.1",
                "INIES — Données environnementales 2023",
                "OTEIS — Retours d'expérience internes",
                "RE2020 — Arrêté du 4 août 2021 modifié"
            ]
        }

        # ── Calcul des variantes si fournies
        if variantes:
            bilan["variantes"] = self.comparer_variantes(variantes)

        return bilan

    def _calculer_cvc(self, donnees: dict, surface: float) -> dict:
        cvc_data = donnees.get("systeme_cvc", {})
        facteurs = self._facteurs["systemes_cvc"]

        postes = {}
        co2_total = 0

        for poste, systeme in cvc_data.items():
            if systeme in facteurs:
                f = facteurs[systeme]
                co2 = f["fabrication"]
                postes[poste] = {
                    "systeme": systeme,
                    "co2_m2_an": round(co2, 2),
                    "source": "INIES"
                }
                co2_total += co2

        return {
            "co2_m2": round(co2_total, 2),
            "postes": postes,
            "note": "Impact fabrication amorti sur 50 ans"
        }

    def _calculer_isolation(self, donnees: dict, surface: float) -> dict:
        isolation = donnees.get("isolation", {})
        facteurs = self._facteurs["isolation"]

        postes = {}
        co2_total = 0

        surface_murs    = surface * 0.45  # ratio approximatif
        surface_toiture = surface / donnees.get("nb_niveaux", 1)
        surface_pb      = surface_toiture

        surfaces = {
            "murs":         surface_murs,
            "toiture":      surface_toiture,
            "plancher_bas": surface_pb
        }

        for paroi, config in isolation.items():
            mat = config.get("materiau", "laine de roche")
            ep  = config.get("epaisseur_cm", 20) / 100  # en mètres
            surf = surfaces.get(paroi, surface * 0.2)

            if mat in facteurs:
                f = facteurs[mat]
                volume = surf * ep
                masse  = volume * f["densite_kg_m3"]
                co2_total_paroi = masse * f["co2_kg"]
                co2_m2 = co2_total_paroi / surface / 50  # amorti 50 ans

                postes[paroi] = {
                    "materiau": mat,
                    "epaisseur_cm": config.get("epaisseur_cm"),
                    "co2_m2_an": round(co2_m2, 3),
                    "bilan_co2": "stockage" if f["co2_kg"] < 0 else "émission",
                    "source": "INIES"
                }
                co2_total += co2_m2

        return {
            "co2_m2": round(co2_total, 3),
            "postes": postes
        }

    def _calculer_enr(self, donnees: dict, surface: float) -> dict:
        enr_liste = donnees.get("enr", [])
        facteurs  = self._facteurs["enr"]

        postes = {}
        credit = 0
        production_kwh = 0

        surface_toiture = surface / max(donnees.get("nb_niveaux", 1), 1)

        for enr in enr_liste:
            key = enr.lower()
            if key in facteurs:
                f = facteurs[key]
                surf_enr = surface_toiture * 0.4  # 40% de la toiture

                if key == "photovoltaïque":
                    prod = f["production_kwh_m2_an"] * surf_enr
                    co2_fab = f["co2_m2"] * surf_enr / surface / 25  # amorti 25 ans
                    credit_annuel = prod / surface * self._facteurs["energie"]["electricite_france"]
                    production_kwh += prod
                    credit -= co2_fab
                    credit += credit_annuel

                    postes[enr] = {
                        "surface_m2":         round(surf_enr),
                        "production_kwh_an":  round(prod),
                        "credit_co2_m2_an":   round(credit_annuel - co2_fab, 3),
                        "source": "ADEME"
                    }

        return {
            "credit_co2_m2": round(credit, 3),
            "production_kwh_an": round(production_kwh),
            "postes": postes
        }

    def _calculer_conso_energie(self, donnees: dict, surface: float, zone: str) -> dict:
        cvc = donnees.get("systeme_cvc", {})
        facteurs = self._facteurs["systemes_cvc"]

        conso_ep = 0
        for systeme in cvc.values():
            if systeme in facteurs:
                conso_ep += facteurs[systeme].get("conso_kwhep_m2", 0)

        # Correction zone climatique
        correction = {"H1": 1.15, "H2": 1.0, "H3": 0.85}.get(zone, 1.0)
        conso_ep *= correction

        # Éclairage + auxiliaires (forfait)
        conso_ep += 20  # éclairage
        conso_ep += 8   # auxiliaires

        return {
            "kwh_ep_m2": round(conso_ep, 1),
            "kwh_ef_m2": round(conso_ep / 2.3, 1),  # coefficient conversion énergie primaire
        }

    def _verifier_re2020(self, ic_energie: float, type_bat: str) -> dict:
        seuils = self._facteurs["seuils_re2020"]
        seuils_type = seuils.get(type_bat, seuils["autres"])

        niveaux = {}
        for annee, seuil in seuils_type.items():
            conforme = ic_energie <= seuil
            marge = round(seuil - ic_energie, 2)
            niveaux[annee] = {
                "seuil": seuil,
                "conforme": conforme,
                "marge_kgco2": marge,
                "marge_pct": round(marge / seuil * 100, 1) if seuil else 0
            }

        # Niveau le plus exigeant atteint
        niveau_atteint = None
        for annee in ["2031", "2028", "2025", "2022"]:
            if niveaux[annee]["conforme"]:
                niveau_atteint = annee
                break

        return {
            "type_batiment": type_bat,
            "ic_energie_calcule": round(ic_energie, 2),
            "niveaux": niveaux,
            "niveau_re2020_atteint": niveau_atteint,
            "statut": "conforme" if niveau_atteint else "non conforme"
        }

    # ─────────────────────────────────────────────
    #  Comparaison de variantes
    # ─────────────────────────────────────────────

    def comparer_variantes(self, variantes: list, criteres: list = None) -> list:
        """Compare plusieurs variantes et retourne un tableau de résultats."""
        if criteres is None:
            criteres = ["carbone", "energie", "re2020"]

        resultats = []
        for v in variantes:
            # Calcul simplifié pour chaque variante
            bilan = self.calculer(v)
            resume = bilan["resume"]
            conformite = bilan["conformite_re2020"]

            resultats.append({
                "nom":                v.get("nom", "Variante"),
                "ic_energie":         resume["ic_energie_kgco2_m2_an"],
                "ic_batiment":        resume["ic_batiment_kgco2_m2_an"],
                "ic_total":           resume["ic_total_kgco2_m2_an"],
                "conso_ep":           resume["conso_kwh_ep_m2"],
                "niveau_re2020":      conformite["niveau_re2020_atteint"],
                "statut_re2020":      conformite["statut"],
                "systeme_cvc":        v.get("systeme_cvc", {}),
                "enr":                v.get("enr", []),
            })

        # Tri par ic_total croissant
        resultats.sort(key=lambda x: x["ic_total"])

        # Ajout du rang
        for i, r in enumerate(resultats):
            r["rang"] = i + 1
            r["recommande"] = (i == 0)

        return resultats

    # ─────────────────────────────────────────────
    #  Interrogation des bases
    # ─────────────────────────────────────────────

    def interroger_base(self, terme: str, base: str = "toutes", unite: str = "les_deux") -> dict:
        """Recherche un matériau ou système dans les bases de données."""
        terme_lower = terme.lower()
        resultats = []

        # Recherche dans les facteurs d'émission
        for categorie, elements in self._facteurs.items():
            if isinstance(elements, dict):
                for cle, valeurs in elements.items():
                    if terme_lower in cle.lower():
                        r = {
                            "reference": cle,
                            "categorie": categorie,
                            "base": "INIES/ADEME",
                            "donnees": valeurs
                        }
                        if isinstance(valeurs, dict):
                            if "co2_kg" in valeurs:
                                r["co2_kgco2eq_par_kg"] = valeurs["co2_kg"]
                            if "conso_kwhep_m2" in valeurs:
                                r["conso_kwh_ep_m2"] = valeurs["conso_kwhep_m2"]
                        resultats.append(r)

        return {
            "terme_recherche": terme,
            "base_interrogee": base,
            "nb_resultats": len(resultats),
            "resultats": resultats,
            "note": "Données issues des bases ADEME Base Carbone, INIES et retours OTEIS"
        }
